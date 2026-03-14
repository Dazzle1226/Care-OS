from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agents.friction import FrictionAgent
from app.agents.plan import PlanAgent, PlanContext
from app.agents.safety import SafetyAgent, SafetyDecision
from app.agents.signal import SignalAgent
from app.models import DailyCheckin, DecisionTrace, EvidenceSelectionLog, Family, RetrievalRun
from app.schemas.domain import (
    CriticReview,
    DecisionGraphStageRun,
    DecisionTraceRead,
    EvidenceGapGuidance,
    FrictionSupportGenerateRequest,
    FrictionSupportPlan,
    Plan48hGenerateRequest,
    Plan48hResponse,
    RetrievalEvidenceBundle,
    ScriptGenerateRequest,
    ScriptResponse,
)
from app.services.evidence_critic import EvidenceCritic
from app.services.multimodal_ingestion import MultimodalIngestionService
from app.services.policy_learning import PolicyLearningService
from app.services.retrieval import RetrievalService

GRAPH_VERSION = "v2"
GRAPH_STAGES = [
    "context_ingestion",
    "signal_eval",
    "evidence_recall",
    "candidate_generation",
    "safety_critic",
    "evidence_critic",
    "policy_adjust_hint",
    "finalizer",
]

MISSING_DIMENSION_LABELS = {
    "scenario": "场景细节还不够完整",
    "profile": "孩子画像还不够完整",
    "safety": "安全边界覆盖还不够完整",
    "execution": "执行反馈还不够完整",
}


@dataclass(slots=True)
class OrchestratedPlanResult:
    signal: Any
    plan: Plan48hResponse
    evidence_bundle: RetrievalEvidenceBundle
    safety: SafetyDecision
    safety_review: CriticReview
    evidence_review: CriticReview
    trace_id: int
    fallback_reason: str | None
    stage_runs: list[DecisionGraphStageRun]
    final_status: str
    final_reason: str
    insufficient_evidence: bool


@dataclass(slots=True)
class OrchestratedScriptResult:
    script: ScriptResponse
    evidence_bundle: RetrievalEvidenceBundle
    safety: SafetyDecision
    safety_review: CriticReview
    evidence_review: CriticReview
    trace_id: int
    fallback_reason: str | None
    stage_runs: list[DecisionGraphStageRun]
    final_status: str
    final_reason: str
    insufficient_evidence: bool


@dataclass(slots=True)
class OrchestratedFrictionResult:
    signal: Any
    support: FrictionSupportPlan
    evidence_bundle: RetrievalEvidenceBundle
    safety: SafetyDecision
    safety_review: CriticReview
    evidence_review: CriticReview
    trace_id: int
    stage_runs: list[DecisionGraphStageRun]
    final_status: str
    final_reason: str
    insufficient_evidence: bool


class DecisionOrchestrator:
    def __init__(self) -> None:
        self.signal_agent = SignalAgent()
        self.plan_agent = PlanAgent()
        self.friction_agent = FrictionAgent()
        self.safety_agent = SafetyAgent()
        self.evidence_critic = EvidenceCritic()
        self.ingestion_service = MultimodalIngestionService()
        self.policy_learning = PolicyLearningService()

    def generate_plan(
        self,
        db: Session,
        family: Family,
        payload: Plan48hGenerateRequest,
        ingestion_ids: list[int] | None = None,
    ) -> OrchestratedPlanResult:
        stage_runs: list[DecisionGraphStageRun] = []
        context_frame = self._context_stage(db, stage_runs, ingestion_ids or [])

        signal_stage = self._stage(
            "signal_eval",
            lambda: self.signal_agent.evaluate(
                db=db,
                family_id=payload.family_id,
                manual_trigger=payload.manual_trigger,
            ).model_dump(),
            input_ref=f"family:{payload.family_id}",
        )
        stage_runs.append(signal_stage)
        signal = self.signal_agent.evaluate(db=db, family_id=payload.family_id, manual_trigger=payload.manual_trigger)

        latest_checkin = db.scalar(
            select(DailyCheckin).where(DailyCheckin.family_id == payload.family_id).order_by(desc(DailyCheckin.date)).limit(1)
        )
        support_hint = latest_checkin.support_available if latest_checkin else "none"
        context = PlanContext(
            family_id=payload.family_id,
            scenario=payload.scenario,
            intensity="heavy" if signal.risk_level == "red" else "medium",
            support_hint=support_hint,
            free_text=" ".join(part for part in [payload.free_text, context_frame.summary_text] if part).strip(),
        )
        selected_cards, bundle, _ = self._evidence_stage(
            db=db,
            family=family,
            scenario=context.scenario or "transition",
            intensity=context.intensity,
            extra_context=context.free_text,
            intent="plan",
            context_signal_keys=context_frame.signal_keys,
            stage_runs=stage_runs,
        )
        plan, fallback_reason = self.plan_agent.generate_48h_plan_with_meta(
            db=db,
            family=family,
            signal=signal,
            context=context,
            cards=selected_cards,
        )
        if bundle.insufficient_evidence:
            plan = plan.model_copy(
                update={"evidence_gap_guidance": self._build_evidence_gap_guidance(bundle, output_kind="plan")}
            )
        stage_runs.append(
            self._stage(
                "candidate_generation",
                lambda: {
                    "citations": plan.citations,
                    "fallback_reason": fallback_reason,
                },
                input_ref="plan-agent",
                status="fallback" if fallback_reason else "success",
                fallback_used=bool(fallback_reason),
            )
        )
        safety = self.safety_agent.validate_plan(
            plan=plan,
            profile_donts=family.child_profile.donts if family.child_profile else [],
            explicit_high_risk=payload.high_risk_selected,
            free_text=context.free_text,
        )
        safety_review = self._build_safety_review(safety)
        stage_runs.append(self._critic_stage("safety_critic", safety_review))
        evidence_review = self.evidence_critic.review(plan, bundle, fallback_used=bool(fallback_reason))
        stage_runs.append(self._critic_stage("evidence_critic", evidence_review))
        policy_diff = self.policy_learning.build_diff(db, family.family_id)
        stage_runs.append(
            self._stage(
                "policy_adjust_hint",
                lambda: {
                    "strongest_positive": [item.target_key for item in policy_diff.strongest_positive[:3]],
                    "strongest_negative": [item.target_key for item in policy_diff.strongest_negative[:3]],
                },
                input_ref=f"family:{family.family_id}",
            )
        )
        final_status, final_reason = self._finalize(safety_review, evidence_review, fallback_reason, bundle, stage_runs)
        trace_id = self._persist_trace(
            db=db,
            family_id=family.family_id,
            chain="plan48h",
            final_status=final_status,
            request_context=payload.model_dump(),
            signal_result=signal.model_dump(),
            retrieval_bundle=bundle,
            candidate_output=plan.model_dump(),
            safety_review=safety_review,
            evidence_review=evidence_review,
            fallback_reason=fallback_reason,
            final_reason=final_reason,
            stage_runs=stage_runs,
            entry_signal_ids=context_frame.ingestion_ids,
        )
        return OrchestratedPlanResult(
            signal=signal,
            plan=plan,
            evidence_bundle=bundle,
            safety=safety,
            safety_review=safety_review,
            evidence_review=evidence_review,
            trace_id=trace_id,
            fallback_reason=fallback_reason,
            stage_runs=stage_runs,
            final_status=final_status,
            final_reason=final_reason,
            insufficient_evidence=bundle.insufficient_evidence,
        )

    def generate_script(
        self,
        db: Session,
        family: Family,
        payload: ScriptGenerateRequest,
        ingestion_ids: list[int] | None = None,
    ) -> OrchestratedScriptResult:
        stage_runs: list[DecisionGraphStageRun] = []
        context_frame = self._context_stage(db, stage_runs, ingestion_ids or [])
        selected_cards, bundle, _ = self._evidence_stage(
            db=db,
            family=family,
            scenario=payload.scenario,
            intensity=payload.intensity,
            extra_context=" ".join(part for part in [payload.free_text, context_frame.summary_text] if part).strip(),
            intent="script",
            context_signal_keys=context_frame.signal_keys,
            stage_runs=stage_runs,
        )
        script, fallback_reason = self.plan_agent.generate_script_with_meta(
            db=db,
            family=family,
            scenario=payload.scenario,
            intensity=payload.intensity,
            free_text=" ".join(part for part in [payload.free_text, context_frame.summary_text] if part).strip(),
            cards=selected_cards,
        )
        if bundle.insufficient_evidence:
            script = script.model_copy(
                update={"evidence_gap_guidance": self._build_evidence_gap_guidance(bundle, output_kind="script")}
            )
        stage_runs.append(
            self._stage(
                "candidate_generation",
                lambda: {"citations": script.citations, "fallback_reason": fallback_reason},
                input_ref="script-agent",
                status="fallback" if fallback_reason else "success",
                fallback_used=bool(fallback_reason),
            )
        )
        safety = self.safety_agent.validate_script(
            script=script,
            profile_donts=family.child_profile.donts if family.child_profile else [],
            explicit_high_risk=payload.high_risk_selected,
            free_text=" ".join(part for part in [payload.free_text, context_frame.summary_text] if part).strip(),
        )
        safety_review = self._build_safety_review(safety)
        stage_runs.append(self._critic_stage("safety_critic", safety_review))
        evidence_review = self.evidence_critic.review(script, bundle, fallback_used=bool(fallback_reason))
        stage_runs.append(self._critic_stage("evidence_critic", evidence_review))
        policy_diff = self.policy_learning.build_diff(db, family.family_id)
        stage_runs.append(
            self._stage(
                "policy_adjust_hint",
                lambda: {
                    "strongest_positive": [item.target_key for item in policy_diff.strongest_positive[:3]],
                    "strongest_negative": [item.target_key for item in policy_diff.strongest_negative[:3]],
                },
                input_ref=f"family:{family.family_id}",
            )
        )
        final_status, final_reason = self._finalize(safety_review, evidence_review, fallback_reason, bundle, stage_runs)
        trace_id = self._persist_trace(
            db=db,
            family_id=family.family_id,
            chain="script",
            final_status=final_status,
            request_context=payload.model_dump(),
            signal_result={},
            retrieval_bundle=bundle,
            candidate_output=script.model_dump(),
            safety_review=safety_review,
            evidence_review=evidence_review,
            fallback_reason=fallback_reason,
            final_reason=final_reason,
            stage_runs=stage_runs,
            entry_signal_ids=context_frame.ingestion_ids,
        )
        return OrchestratedScriptResult(
            script=script,
            evidence_bundle=bundle,
            safety=safety,
            safety_review=safety_review,
            evidence_review=evidence_review,
            trace_id=trace_id,
            fallback_reason=fallback_reason,
            stage_runs=stage_runs,
            final_status=final_status,
            final_reason=final_reason,
            insufficient_evidence=bundle.insufficient_evidence,
        )

    def generate_friction_support(
        self,
        db: Session,
        family: Family,
        payload: FrictionSupportGenerateRequest,
        ingestion_ids: list[int] | None = None,
    ) -> OrchestratedFrictionResult:
        stage_runs: list[DecisionGraphStageRun] = []
        context_frame = self._context_stage(db, stage_runs, ingestion_ids or [])

        signal_stage = self._stage(
            "signal_eval",
            lambda: self.signal_agent.evaluate(db=db, family_id=payload.family_id).model_dump(),
            input_ref=f"family:{payload.family_id}",
        )
        stage_runs.append(signal_stage)
        signal = self.signal_agent.evaluate(db=db, family_id=payload.family_id)

        state = self.friction_agent._derive_state(payload, signal)
        context = " ".join(
            [
                self.friction_agent.child_state_labels[payload.child_state],
                self.friction_agent.sensory_labels[payload.sensory_overload_level],
                " ".join(payload.env_changes[:3]),
                payload.free_text,
                context_frame.summary_text,
            ]
        ).strip()
        selected_cards, bundle, _ = self._evidence_stage(
            db=db,
            family=family,
            scenario=state.retrieval_scenario,
            intensity=state.intensity,
            extra_context=context,
            intent="friction",
            context_signal_keys=context_frame.signal_keys,
            stage_runs=stage_runs,
        )
        support = self.friction_agent.generate_support(
            db=db,
            family=family,
            signal=signal,
            payload=payload,
            cards=selected_cards,
            evidence_bundle=bundle,
        )
        if bundle.insufficient_evidence:
            support = support.model_copy(
                update={"evidence_gap_guidance": self._build_evidence_gap_guidance(bundle, output_kind="friction")}
            )
        stage_runs.append(
            self._stage(
                "candidate_generation",
                lambda: {"citations": support.citations, "headline": support.headline},
                input_ref="friction-agent",
            )
        )
        safety = self.safety_agent.validate_friction_support(
            support=support,
            profile_donts=family.child_profile.donts if family.child_profile else [],
            explicit_high_risk=payload.high_risk_selected,
            free_text=context,
        )
        safety_review = self._build_safety_review(safety)
        stage_runs.append(self._critic_stage("safety_critic", safety_review))
        evidence_review = self.evidence_critic.review(support, bundle)
        stage_runs.append(self._critic_stage("evidence_critic", evidence_review))
        policy_diff = self.policy_learning.build_diff(db, family.family_id)
        stage_runs.append(
            self._stage(
                "policy_adjust_hint",
                lambda: {
                    "strongest_positive": [item.target_key for item in policy_diff.strongest_positive[:3]],
                    "strongest_negative": [item.target_key for item in policy_diff.strongest_negative[:3]],
                },
                input_ref=f"family:{family.family_id}",
            )
        )
        final_status, final_reason = self._finalize(safety_review, evidence_review, None, bundle, stage_runs)
        trace_id = self._persist_trace(
            db=db,
            family_id=family.family_id,
            chain="friction_support",
            final_status=final_status,
            request_context=payload.model_dump(),
            signal_result=signal.model_dump(),
            retrieval_bundle=bundle,
            candidate_output=support.model_dump(),
            safety_review=safety_review,
            evidence_review=evidence_review,
            fallback_reason=None,
            final_reason=final_reason,
            stage_runs=stage_runs,
            entry_signal_ids=context_frame.ingestion_ids,
        )
        return OrchestratedFrictionResult(
            signal=signal,
            support=support,
            evidence_bundle=bundle,
            safety=safety,
            safety_review=safety_review,
            evidence_review=evidence_review,
            trace_id=trace_id,
            stage_runs=stage_runs,
            final_status=final_status,
            final_reason=final_reason,
            insufficient_evidence=bundle.insufficient_evidence,
        )

    def get_trace(self, db: Session, trace_id: int) -> DecisionTraceRead | None:
        row = db.get(DecisionTrace, trace_id)
        if row is None:
            return None
        bundle = RetrievalEvidenceBundle.model_validate(row.retrieval_bundle_json) if row.retrieval_bundle_json else None
        safety_review = CriticReview.model_validate(row.safety_review_json) if row.safety_review_json else None
        evidence_review = CriticReview.model_validate(row.evidence_review_json) if row.evidence_review_json else None
        stage_runs = [DecisionGraphStageRun.model_validate(item) for item in row.stage_runs_json]
        return DecisionTraceRead(
            trace_id=row.id,
            family_id=row.family_id,
            chain=row.chain,  # type: ignore[arg-type]
            final_status=row.final_status,  # type: ignore[arg-type]
            graph_version=row.graph_version,
            stage_order=list(row.stage_order_json),
            stage_runs=stage_runs,
            entry_signal_ids=list(row.entry_signal_ids_json),
            request_context=row.request_context_json,
            signal_result=row.signal_result_json,
            retrieval_bundle=bundle,
            candidate_output=row.candidate_output_json,
            safety_review=safety_review,
            evidence_review=evidence_review,
            provider_name=row.provider_name,
            embedding_model=row.embedding_model,
            reranker_model=row.reranker_model,
            corpus_version=row.corpus_version,
            retrieval_stage_timings=row.retrieval_stage_timings_json,
            fallback_reason=row.fallback_reason,
            final_reason=row.final_reason,
            created_at=row.created_at,
        )

    def _context_stage(
        self,
        db: Session,
        stage_runs: list[DecisionGraphStageRun],
        ingestion_ids: list[int],
    ):
        context_frame = self.ingestion_service.merge_context_frame(db, ingestion_ids)
        stage_runs.append(
            self._stage(
                "context_ingestion",
                lambda: {
                    "ingestion_ids": context_frame.ingestion_ids,
                    "summary": context_frame.summary_text,
                    "signals": context_frame.signal_keys,
                },
                input_ref=",".join(str(item) for item in ingestion_ids),
                status="success" if context_frame.ingestion_ids else "skipped",
            )
        )
        return context_frame

    def _evidence_stage(
        self,
        db: Session,
        family: Family,
        scenario: str,
        intensity: str,
        extra_context: str,
        intent: str,
        context_signal_keys: list[str],
        stage_runs: list[DecisionGraphStageRun],
    ) -> tuple[list[Any], RetrievalEvidenceBundle, list[Any]]:
        retrieval = RetrievalService(db)
        selected_cards, bundle, ranked_cards = retrieval.retrieve_bundle(
            family_id=family.family_id,
            scenario=scenario,
            intensity=intensity,
            profile=family.child_profile,
            extra_context=extra_context,
            max_cards=3,
            intent=intent,
            context_signal_keys=context_signal_keys,
        )
        stage_runs.append(
            self._stage(
                "evidence_recall",
                lambda: {
                    "selected_card_ids": bundle.selected_card_ids,
                    "selected_evidence_unit_ids": bundle.selected_evidence_unit_ids,
                    "selected_chunk_ids": bundle.selected_chunk_ids,
                    "insufficient_evidence": bundle.insufficient_evidence,
                },
                input_ref=scenario,
                status="fallback" if bundle.insufficient_evidence else "success",
                fallback_used=bundle.insufficient_evidence,
            )
        )
        return selected_cards, bundle, ranked_cards

    def _persist_trace(
        self,
        db: Session,
        family_id: int | None,
        chain: str,
        final_status: str,
        request_context: dict[str, Any],
        signal_result: dict[str, Any],
        retrieval_bundle: RetrievalEvidenceBundle | None,
        candidate_output: dict[str, Any],
        safety_review: CriticReview,
        evidence_review: CriticReview,
        fallback_reason: str | None,
        final_reason: str,
        stage_runs: list[DecisionGraphStageRun],
        entry_signal_ids: list[int],
    ) -> int:
        row = DecisionTrace(
            family_id=family_id,
            chain=chain,
            final_status=final_status,
            graph_version=GRAPH_VERSION,
            stage_order_json=list(GRAPH_STAGES),
            stage_runs_json=[item.model_dump() for item in stage_runs],
            entry_signal_ids_json=entry_signal_ids,
            request_context_json=request_context,
            signal_result_json=signal_result,
            retrieval_bundle_json=retrieval_bundle.model_dump() if retrieval_bundle is not None else {},
            candidate_output_json=candidate_output,
            safety_review_json=safety_review.model_dump(),
            evidence_review_json=evidence_review.model_dump(),
            provider_name=None,
            embedding_model=None,
            reranker_model=None,
            corpus_version=(retrieval_bundle.knowledge_versions[0] if retrieval_bundle and retrieval_bundle.knowledge_versions else None),
            retrieval_stage_timings_json={
                "retrieval_latency_ms": retrieval_bundle.retrieval_latency_ms if retrieval_bundle else 0,
                "selected_card_count": len(retrieval_bundle.selected_card_ids) if retrieval_bundle else 0,
                "selected_chunk_count": len(retrieval_bundle.selected_chunk_ids) if retrieval_bundle else 0,
                "fallback_cause": fallback_reason or "",
            },
            fallback_reason=fallback_reason,
            final_reason=final_reason,
        )
        db.add(row)
        db.flush()

        if retrieval_bundle is not None:
            for unit_id in retrieval_bundle.selected_evidence_unit_ids:
                db.add(
                    EvidenceSelectionLog(
                        trace_id=row.id,
                        family_id=family_id,
                        evidence_unit_id=unit_id,
                        score=1.0,
                        selected=True,
                    )
                )
            if retrieval_bundle.retrieval_run_id is not None:
                retrieval_run = db.get(RetrievalRun, retrieval_bundle.retrieval_run_id)
                if retrieval_run is not None:
                    retrieval_run.trace_id = row.id
                    row.provider_name = retrieval_run.embedding_provider or ("rule_fallback" if fallback_reason else None)
                    row.embedding_model = retrieval_run.embedding_model or None
                    row.reranker_model = retrieval_run.reranker_model or None
                    row.corpus_version = retrieval_run.corpus_version or row.corpus_version
                    row.retrieval_stage_timings_json = {
                        "retrieval_latency_ms": retrieval_run.retrieval_latency_ms,
                        "selected_card_count": len(retrieval_bundle.selected_card_ids),
                        "selected_chunk_count": len(retrieval_bundle.selected_chunk_ids),
                        "fallback_cause": fallback_reason or "",
                    }
        db.flush()
        return row.id

    def _finalize(
        self,
        safety_review: CriticReview,
        evidence_review: CriticReview,
        fallback_reason: str | None,
        bundle: RetrievalEvidenceBundle,
        stage_runs: list[DecisionGraphStageRun],
    ) -> tuple[str, str]:
        if safety_review.blocked:
            final_status = "blocked"
            final_reason = safety_review.summary
        elif evidence_review.blocked:
            final_status = "blocked"
            final_reason = evidence_review.summary
        elif fallback_reason:
            final_status = "fallback"
            final_reason = "候选生成已降级到规则路径，但仍保留证据链和 critic 结果。"
        else:
            final_status = "success"
            final_reason = "决策图执行完成。"
        if bundle.insufficient_evidence and final_status == "success":
            final_reason = "决策图执行完成，但证据覆盖仍不充分。"
        stage_runs.append(
            self._stage(
                "finalizer",
                lambda: {
                    "final_status": final_status,
                    "final_reason": final_reason,
                    "insufficient_evidence": bundle.insufficient_evidence,
                },
                input_ref="graph",
                status=final_status if final_status in {"blocked", "fallback"} else "success",
                fallback_used=bool(fallback_reason),
            )
        )
        return final_status, final_reason

    @staticmethod
    def _build_evidence_gap_guidance(
        bundle: RetrievalEvidenceBundle,
        *,
        output_kind: str,
    ) -> EvidenceGapGuidance:
        source_titles = [source.title for source in bundle.selected_sources[:2] if source.title]
        known_facts = [
            f"当前建议仍引用了 {len(bundle.selected_card_ids)} 张命中策略卡：{', '.join(bundle.selected_card_ids[:3])}。"
        ]
        if bundle.selection_reasons:
            known_facts.append(bundle.selection_reasons[0])
        elif source_titles:
            known_facts.append(f"当前主要参考来源：{', '.join(source_titles)}。")
        coverage_ok = [name for name, score in bundle.coverage_scores.items() if score >= 0.5]
        if coverage_ok:
            known_facts.append(f"目前至少覆盖了 {', '.join(coverage_ok[:2])} 维度。")

        uncertain_areas = [
            MISSING_DIMENSION_LABELS.get(name, f"{name} 维度证据不足") for name in bundle.missing_dimensions[:4]
        ]
        if not uncertain_areas:
            uncertain_areas = ["当前证据覆盖不完整，需要补充更多上下文。"]

        if output_kind == "plan":
            provisional_recommendation = "先执行当前计划里最低刺激、最容易回退的一步，不要同时推进多个新要求。"
            safe_next_steps = [
                "先只保留一个优先场景，观察半天到一天。",
                "记录哪一步最顺、哪一步最卡住。",
                "一旦负荷继续上升，立刻切回退出卡，不继续加码。",
            ]
        elif output_kind == "script":
            provisional_recommendation = "先按当前脚本的第一步用最短句尝试一次，阻力上升就立即切到退场方案。"
            safe_next_steps = [
                "只读出一句当前脚本，不连续追问。",
                "观察 1 到 2 分钟是否出现放松、接受或继续升级。",
                "若继续升级，直接执行 exit_plan，不强行完成原目标。",
            ]
        else:
            provisional_recommendation = "先按当前支持方案完成降刺激和交接，不并行处理多个目标。"
            safe_next_steps = [
                "先执行 action_plan 的第一步和第一条交接话术。",
                "只盯一个目标：先降刺激或先完成交接。",
                "如果孩子或照护者继续升级，直接进入 crisis_card 或退场步骤。",
            ]

        info_to_collect: list[str] = []
        for name in bundle.missing_dimensions[:4]:
            if name == "scenario":
                info_to_collect.append("补充触发前 10 分钟发生了什么、现场有哪些变化。")
            elif name == "profile":
                info_to_collect.append("补充孩子当下能接受的提示方式、禁忌和安抚偏好。")
            elif name == "safety":
                info_to_collect.append("确认是否出现自伤、他伤、逃跑或其他高风险信号。")
            elif name == "execution":
                info_to_collect.append("记录执行后 5 到 10 分钟内，哪一步有效、哪一步无效。")
            else:
                info_to_collect.append(f"补充与 {name} 维度相关的现场信息。")
        if len(info_to_collect) < 2:
            info_to_collect.append("补充这次情境和过往类似情境的差异。")
        if len(info_to_collect) < 2:
            info_to_collect.append("补充执行后的反馈，便于收敛到更明确建议。")

        return EvidenceGapGuidance(
            known_facts=known_facts[:3],
            uncertain_areas=uncertain_areas[:4],
            provisional_recommendation=provisional_recommendation,
            recommendation_conditions=[
                "只在当前没有高风险信号时继续普通建议。",
                "每次只改一个变量，优先选择可回退动作。",
                "一旦负荷明显上升，优先保安全而不是完成任务。",
            ],
            info_to_collect=info_to_collect[:4],
            safe_next_steps=safe_next_steps,
        )

    @staticmethod
    def _build_safety_review(safety: SafetyDecision) -> CriticReview:
        if safety.blocked and safety.block is not None:
            return CriticReview(
                critic="safety",
                decision="block",
                blocked=True,
                reasons=[safety.block.block_reason],
                summary="安全审查未通过，已阻断输出。",
            )
        return CriticReview(
            critic="safety",
            decision="pass",
            blocked=False,
            reasons=[],
            summary="安全审查通过。",
        )

    @staticmethod
    def _critic_stage(stage: str, review: CriticReview) -> DecisionGraphStageRun:
        return DecisionGraphStageRun(
            stage=stage,  # type: ignore[arg-type]
            status="blocked" if review.blocked else "success",
            input_ref=review.critic,
            output=review.model_dump(),
            latency_ms=0,
            fallback_used=review.decision == "fallback_ok",
            retry_count=0,
        )

    @staticmethod
    def _stage(
        stage: str,
        fn,
        *,
        input_ref: str,
        status: str = "success",
        fallback_used: bool = False,
        retry_count: int = 0,
    ) -> DecisionGraphStageRun:
        start = perf_counter()
        output = fn()
        latency_ms = int((perf_counter() - start) * 1000)
        return DecisionGraphStageRun(
            stage=stage,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            input_ref=input_ref,
            output=output,
            latency_ms=max(0, latency_ms),
            fallback_used=fallback_used,
            retry_count=retry_count,
        )
