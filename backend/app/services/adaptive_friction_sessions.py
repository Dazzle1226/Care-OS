from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agents.coordinator import CoordinationResult, CoordinatorAgent
from app.agents.emotion import EmotionAgent
from app.agents.friction import FrictionAgent
from app.agents.safety import SafetyAgent, SafetyDecision
from app.agents.signal import SignalAgent
from app.core.time import utc_now
from app.models import AdaptiveSession, DailyCheckin, DecisionTrace, EvidenceSelectionLog, Family, IncidentLog, Review, SessionEvent
from app.schemas.domain import (
    AdaptiveSessionRead,
    AgentProposal,
    ContextSignalRead,
    CoordinationDecision,
    CriticReview,
    DecisionGraphStageRun,
    DecisionTraceRead,
    EmotionAssessment,
    ExecutionState,
    FrictionSupportPlan,
    GoalSpec,
    PlanRevision,
    PlanRevisionDiff,
    ReplanTrigger,
    RetrievalEvidenceBundle,
    SessionEventRead,
    SignalOutput,
    TaskNode,
    V3FrictionSessionCloseRequest,
    V3FrictionSessionCloseResponse,
    V3FrictionSessionConfirmRequest,
    V3FrictionSessionConfirmResponse,
    V3FrictionSessionEventRequest,
    V3FrictionSessionEventResponse,
    V3FrictionSessionStartRequest,
    V3FrictionSessionStartResponse,
    V3FrictionSessionTraceResponse,
)
from app.services.evidence_critic import EvidenceCritic
from app.services.decision_state import build_decision_state
from app.services.multimodal_ingestion import MultimodalIngestionService
from app.services.policy_learning import PolicyLearningService
from app.services.retrieval import RetrievalService

GRAPH_VERSION = "v3"
GRAPH_STAGES = [
    "context_ingestion",
    "context_fusion",
    "signal_eval",
    "emotion_eval",
    "goal_interpretation",
    "evidence_recall",
    "candidate_generation",
    "safety_critic",
    "evidence_critic",
    "coordination",
    "policy_adjust_hint",
    "task_decomposition",
    "candidate_simulation",
    "critic_reflection",
    "executor",
    "replanner",
    "finalizer",
]


@dataclass(slots=True)
class AdaptiveRunResult:
    signal: SignalOutput
    emotion: EmotionAssessment
    support: FrictionSupportPlan
    coordination: CoordinationDecision
    proposals: list[AgentProposal]
    evidence_bundle: RetrievalEvidenceBundle
    safety: SafetyDecision
    safety_review: CriticReview
    evidence_review: CriticReview
    trace_id: int
    stage_runs: list[DecisionGraphStageRun]
    changed_fields: list[str]
    final_status: str
    final_reason: str
    fused_context: str
    context_signals: list[ContextSignalRead]
    plan_revision: PlanRevision
    active_task: TaskNode | None
    critic_verdicts: list[CriticReview]
    replan_reason: str | None
    revision_diff: PlanRevisionDiff
    parent_trace_id: int | None


class AdaptiveFrictionSessionService:
    def __init__(self) -> None:
        self.signal_agent = SignalAgent()
        self.emotion_agent = EmotionAgent()
        self.friction_agent = FrictionAgent()
        self.safety_agent = SafetyAgent()
        self.evidence_critic = EvidenceCritic()
        self.coordinator_agent = CoordinatorAgent()
        self.ingestion_service = MultimodalIngestionService()
        self.policy_learning = PolicyLearningService()

    def start(self, db: Session, family: Family, payload: V3FrictionSessionStartRequest) -> V3FrictionSessionStartResponse:
        result = self._run_cycle(
            db=db,
            family=family,
            payload=payload,
            ingestion_ids=payload.ingestion_ids,
        )
        if result.safety.blocked:
            return V3FrictionSessionStartResponse(
                blocked=True,
                decision_state=None,
                risk=result.signal,
                emotion=result.emotion,
                safety_block=result.safety.block,
                evidence_bundle=result.evidence_bundle,
                trace_id=result.trace_id,
                trace_summary=result.stage_runs,
                plan_revision=result.plan_revision,
                active_task=result.active_task,
                task_tree=result.plan_revision.task_tree,
                execution_state=result.plan_revision.execution_state,
                replan_reason=result.replan_reason,
                critic_verdicts=result.critic_verdicts,
                revision_diff=result.revision_diff,
            )

        incident = IncidentLog(
            family_id=family.family_id,
            ts=utc_now(),
            scenario=(payload.custom_scenario.strip() or payload.scenario),
            intensity=self._incident_intensity(payload, result.emotion),
            triggers=[payload.child_state, *payload.env_changes[:2]],
            selected_resources={
                "source_card_ids": result.support.source_card_ids,
                "selected_mode": result.coordination.active_mode,
                "replan_triggers": result.coordination.replan_triggers,
                "ingestion_ids": payload.ingestion_ids,
            },
            high_risk_flag=payload.high_risk_selected,
            notes=payload.free_text,
        )
        db.add(incident)
        db.flush()

        session = AdaptiveSession(
            family_id=family.family_id,
            incident_id=incident.id,
            chain="friction_support",
            status="active",
            current_state_version=1,
            current_state_json=self._build_state_payload(payload, payload.ingestion_ids, result),
            active_plan_summary_json={
                "mode": result.coordination.active_mode,
                "summary": result.coordination.summary,
                "now_step": result.coordination.now_step,
                "now_script": result.coordination.now_script,
                "next_if_not_working": result.coordination.next_if_not_working,
            },
            next_check_in_hint="执行 3 分钟后确认是否更稳定；如果仍升级，直接点“换更轻的”或“需要交接”。",
            last_trace_id=result.trace_id,
        )
        db.add(session)
        db.flush()

        return V3FrictionSessionStartResponse(
            blocked=False,
            session=self._session_read(session),
            decision_state=self._decision_state_from_session(session),
            risk=result.signal,
            emotion=result.emotion,
            support=result.support,
            coordination=result.coordination,
            evidence_bundle=result.evidence_bundle,
            trace_id=result.trace_id,
            trace_summary=result.stage_runs,
            plan_revision=result.plan_revision,
            active_task=result.active_task,
            task_tree=result.plan_revision.task_tree,
            execution_state=result.plan_revision.execution_state,
            replan_reason=result.replan_reason,
            critic_verdicts=result.critic_verdicts,
            revision_diff=result.revision_diff,
        )

    def add_event(
        self,
        db: Session,
        family: Family,
        session: AdaptiveSession,
        payload: V3FrictionSessionEventRequest,
    ) -> V3FrictionSessionEventResponse:
        state = dict(session.current_state_json)
        base_payload = V3FrictionSessionStartRequest.model_validate(state["payload"])
        ingestion_ids = list(state.get("ingestion_ids", []))
        prefer_lighter = bool(state.get("prefer_lighter", False))
        prefer_handoff = bool(state.get("prefer_handoff", False))
        previous_risk = SignalOutput.model_validate(state["risk"])
        previous_emotion = EmotionAssessment.model_validate(state["emotion"])
        previous_support = FrictionSupportPlan.model_validate(state["support"])
        previous_coordination = CoordinationDecision.model_validate(state["coordination"])
        previous_plan_revision = PlanRevision.model_validate(state["plan_revision"])

        if payload.ingestion_id is not None and payload.ingestion_id not in ingestion_ids:
            ingestion_ids.append(payload.ingestion_id)
        if payload.raw_text.strip():
            merged_text = " ".join(part for part in [base_payload.free_text, payload.raw_text.strip()] if part)
            base_payload.free_text = merged_text[:500]
        if payload.event_kind == "request_lighter":
            prefer_lighter = True
        if payload.event_kind == "request_handoff":
            prefer_handoff = True
        if payload.event_kind == "support_arrived":
            prefer_handoff = True
        if payload.event_kind in {"request_lighter", "caregiver_overloaded"}:
            prefer_lighter = True

        rerun = self._should_rerun(session, payload)
        changed_fields: list[str] = []
        if rerun:
            result = self._run_cycle(
                db=db,
                family=family,
                payload=base_payload,
                ingestion_ids=ingestion_ids,
                replan_event=payload,
                prefer_lighter=prefer_lighter,
                prefer_handoff=prefer_handoff,
                previous_risk=previous_risk,
                previous_emotion=previous_emotion,
                previous_support=previous_support,
                previous_coordination=previous_coordination,
                previous_plan_revision=previous_plan_revision,
                parent_trace_id=session.last_trace_id,
            )
            changed_fields = result.changed_fields
            rerun = bool(changed_fields) or payload.event_kind in {
                "request_lighter",
                "request_handoff",
                "no_improvement",
                "caregiver_overloaded",
                "child_escalating",
                "support_arrived",
                "new_context_ingested",
            }
        else:
            result = None

        event = SessionEvent(
            session_id=session.id,
            source_type=payload.source_type,
            event_kind=payload.event_kind,
            raw_text=payload.raw_text.strip(),
            ingestion_id=payload.ingestion_id,
            payload_json={"ingestion_ids": ingestion_ids},
            replanned=bool(rerun and result is not None),
        )
        db.add(event)
        db.flush()

        if result is not None and rerun:
            session.current_state_version += 1
            next_state = self._build_state_payload(base_payload, ingestion_ids, result)
            next_state["adaptation_history"] = [
                *list(state.get("adaptation_history", [])),
                result.replan_reason or "根据现场变化调整了当前方案。",
            ][-8:]
            session.current_state_json = next_state
            session.active_plan_summary_json = {
                "mode": result.coordination.active_mode,
                "summary": result.coordination.summary,
                "now_step": result.coordination.now_step,
                "now_script": result.coordination.now_script,
                "next_if_not_working": result.coordination.next_if_not_working,
            }
            session.next_check_in_hint = "已按最新状态调整。先执行当前一步，3 分钟后再确认是否需要继续减负。"
            session.last_trace_id = result.trace_id
            db.flush()
            return V3FrictionSessionEventResponse(
                session=self._session_read(session),
                event=self._event_read(event),
                replanned=True,
                changed_fields=changed_fields,
                decision_state=self._decision_state_from_session(session),
                risk=result.signal,
                emotion=result.emotion,
                support=result.support,
                coordination=result.coordination,
                evidence_bundle=result.evidence_bundle,
                trace_id=result.trace_id,
                trace_summary=result.stage_runs,
                plan_revision=result.plan_revision,
                active_task=result.active_task,
                task_tree=result.plan_revision.task_tree,
                execution_state=result.plan_revision.execution_state,
                replan_reason=result.replan_reason,
                critic_verdicts=result.critic_verdicts,
                revision_diff=result.revision_diff,
            )

        return V3FrictionSessionEventResponse(
            session=self._session_read(session),
            event=self._event_read(event),
            replanned=False,
            changed_fields=[],
            decision_state=self._decision_state_from_session(session),
            risk=previous_risk,
            emotion=previous_emotion,
            support=previous_support,
            coordination=previous_coordination,
            evidence_bundle=RetrievalEvidenceBundle.model_validate(state["evidence_bundle"]),
            trace_id=state.get("trace_id"),
            trace_summary=[DecisionGraphStageRun.model_validate(item) for item in state.get("trace_summary", [])],
            plan_revision=PlanRevision.model_validate(state["plan_revision"]),
            active_task=TaskNode.model_validate(state["active_task"]) if state.get("active_task") else None,
            task_tree=[TaskNode.model_validate(item) for item in state.get("task_tree", [])],
            execution_state=ExecutionState.model_validate(state["execution_state"]),
            replan_reason=state.get("replan_reason"),
            critic_verdicts=[CriticReview.model_validate(item) for item in state.get("critic_verdicts", [])],
            revision_diff=PlanRevisionDiff.model_validate(state["revision_diff"]),
        )

    def confirm(
        self,
        db: Session,
        family: Family,
        session: AdaptiveSession,
        payload: V3FrictionSessionConfirmRequest,
    ) -> V3FrictionSessionConfirmResponse:
        event_kind = "confirm"
        if payload.action in {"lighter", "handoff"}:
            event_payload = V3FrictionSessionEventRequest(
                source_type="user_action",
                event_kind="request_lighter" if payload.action == "lighter" else "request_handoff",
                raw_text=payload.note,
            )
            event_response = self.add_event(db=db, family=family, session=session, payload=event_payload)
            return V3FrictionSessionConfirmResponse(
                session=event_response.session,
                decision_state=event_response.decision_state,
                coordination=event_response.coordination or CoordinationDecision.model_validate(session.current_state_json["coordination"]),
                support=event_response.support or FrictionSupportPlan.model_validate(session.current_state_json["support"]),
                trace_id=event_response.trace_id,
                trace_summary=event_response.trace_summary,
                plan_revision=event_response.plan_revision,
                active_task=event_response.active_task,
                task_tree=event_response.task_tree,
                execution_state=event_response.execution_state,
                replan_reason=event_response.replan_reason,
                critic_verdicts=event_response.critic_verdicts,
                revision_diff=event_response.revision_diff,
            )

        event = SessionEvent(
            session_id=session.id,
            source_type="user_action",
            event_kind=event_kind,
            raw_text=payload.note.strip() or payload.action,
            payload_json={"action": payload.action},
            replanned=False,
        )
        db.add(event)
        db.flush()
        state = session.current_state_json
        return V3FrictionSessionConfirmResponse(
            session=self._session_read(session),
            decision_state=self._decision_state_from_session(session),
            coordination=CoordinationDecision.model_validate(state["coordination"]),
            support=FrictionSupportPlan.model_validate(state["support"]),
            trace_id=state.get("trace_id"),
            trace_summary=[DecisionGraphStageRun.model_validate(item) for item in state.get("trace_summary", [])],
            plan_revision=PlanRevision.model_validate(state["plan_revision"]),
            active_task=TaskNode.model_validate(state["active_task"]) if state.get("active_task") else None,
            task_tree=[TaskNode.model_validate(item) for item in state.get("task_tree", [])],
            execution_state=ExecutionState.model_validate(state["execution_state"]),
            replan_reason=state.get("replan_reason"),
            critic_verdicts=[CriticReview.model_validate(item) for item in state.get("critic_verdicts", [])],
            revision_diff=PlanRevisionDiff.model_validate(state["revision_diff"]),
        )

    def close(
        self,
        db: Session,
        family: Family,
        session: AdaptiveSession,
        payload: V3FrictionSessionCloseRequest,
    ) -> V3FrictionSessionCloseResponse:
        state = session.current_state_json
        current_support = FrictionSupportPlan.model_validate(state["support"])
        current_emotion = EmotionAssessment.model_validate(state["emotion"])
        current_coordination = CoordinationDecision.model_validate(state["coordination"])
        incident_id = session.incident_id
        if incident_id is None:
            raise ValueError("Adaptive session missing incident")

        outcome_score = self._outcome_score(payload.effectiveness, payload.child_state_after, payload.caregiver_state_after)
        review = Review(
            incident_id=incident_id,
            family_id=family.family_id,
            card_ids=current_support.source_card_ids,
            outcome_score=outcome_score,
            child_state_after=payload.child_state_after,
            caregiver_state_after=payload.caregiver_state_after,
            recommendation="continue" if outcome_score >= 1 else "pause" if outcome_score == 0 else "replace",
            response_action=current_coordination.active_mode,
            notes=payload.notes,
            followup_action=current_coordination.next_if_not_working,
        )
        db.add(review)
        db.flush()

        self.policy_learning.record_review(
            db=db,
            family_id=family.family_id,
            outcome_score=outcome_score,
            card_ids=current_support.source_card_ids,
            scenario=(state["payload"].get("custom_scenario") or state["payload"]["scenario"]),
            response_action=current_coordination.active_mode,
        )
        self.policy_learning.record_adaptive_feedback(
            db=db,
            family_id=family.family_id,
            outcome_score=outcome_score,
            emotion_pattern=f"{current_emotion.child_emotion}|{current_emotion.caregiver_emotion}",
            overload_trigger=f"{current_emotion.child_overload_level}|{current_emotion.caregiver_overload_level}",
            handoff_pattern=current_support.handoff_messages[1].text if len(current_support.handoff_messages) > 1 else "",
            adjustment_key=current_coordination.active_mode,
        )
        updated_weights = self.policy_learning.rebuild_card_weights(db=db, family_id=family.family_id)

        event = SessionEvent(
            session_id=session.id,
            source_type="system",
            event_kind="close",
            raw_text=payload.notes.strip() or payload.effectiveness,
            payload_json={
                "effectiveness": payload.effectiveness,
                "child_state_after": payload.child_state_after,
                "caregiver_state_after": payload.caregiver_state_after,
            },
            replanned=False,
        )
        db.add(event)

        session.status = "closed"
        session.next_check_in_hint = "本次会话已关闭。系统会把有效做法和交接方式记到下次推荐里。"
        state["adaptation_history"] = [
            *list(state.get("adaptation_history", [])),
            payload.notes.strip() or "本次高摩擦会话已结束并完成学习写回。",
        ][-8:]
        session.current_state_json = state
        db.flush()

        learning_summary = [
            f"情绪模式已记录：{current_emotion.child_emotion} / {current_emotion.caregiver_emotion}",
            f"本次更有效的调整模式：{current_coordination.active_mode}",
        ]
        if payload.caregiver_state_after == "calmer":
            learning_summary.append("系统会在类似情境下更早减负。")
        if payload.child_state_after == "settled":
            learning_summary.append("当前方案会继续保持较高优先级。")

        return V3FrictionSessionCloseResponse(
            session=self._session_read(session),
            decision_state=self._decision_state_from_session(session),
            learning_summary=learning_summary[:5],
            updated_weights=updated_weights,
        )

    def get_trace(self, db: Session, session: AdaptiveSession) -> V3FrictionSessionTraceResponse:
        if session.last_trace_id is None:
            raise ValueError("Adaptive session missing trace")
        row = db.get(DecisionTrace, session.last_trace_id)
        if row is None:
            raise ValueError("Decision trace not found")
        trace = DecisionTraceRead(
            trace_id=row.id,
            family_id=row.family_id,
            chain=row.chain,  # type: ignore[arg-type]
            final_status=row.final_status,  # type: ignore[arg-type]
            graph_version=row.graph_version,
            stage_order=list(row.stage_order_json),
            stage_runs=[DecisionGraphStageRun.model_validate(item) for item in row.stage_runs_json],
            entry_signal_ids=list(row.entry_signal_ids_json),
            request_context=row.request_context_json,
            signal_result=row.signal_result_json,
            retrieval_bundle=RetrievalEvidenceBundle.model_validate(row.retrieval_bundle_json) if row.retrieval_bundle_json else None,
            candidate_output=row.candidate_output_json,
            safety_review=CriticReview.model_validate(row.safety_review_json) if row.safety_review_json else None,
            evidence_review=CriticReview.model_validate(row.evidence_review_json) if row.evidence_review_json else None,
            fallback_reason=row.fallback_reason,
            final_reason=row.final_reason,
            plan_tree=[TaskNode.model_validate(item) for item in row.plan_tree_json],
            execution_state=ExecutionState.model_validate(row.execution_state_json) if row.execution_state_json else None,
            revision_no=row.revision_no,
            parent_trace_id=row.parent_trace_id,
            replan_reason=row.replan_reason,
            created_at=row.created_at,
        )
        events = [
            self._event_read(item)
            for item in db.scalars(select(SessionEvent).where(SessionEvent.session_id == session.id).order_by(SessionEvent.created_at.asc())).all()
        ]
        return V3FrictionSessionTraceResponse(
            session=self._session_read(session),
            decision_state=self._decision_state_from_session(session),
            trace=trace,
            events=events,
        )

    def _run_cycle(
        self,
        *,
        db: Session,
        family: Family,
        payload: V3FrictionSessionStartRequest,
        ingestion_ids: list[int],
        replan_event: V3FrictionSessionEventRequest | None = None,
        prefer_lighter: bool = False,
        prefer_handoff: bool = False,
        previous_risk: SignalOutput | None = None,
        previous_emotion: EmotionAssessment | None = None,
        previous_support: FrictionSupportPlan | None = None,
        previous_coordination: CoordinationDecision | None = None,
        previous_plan_revision: PlanRevision | None = None,
        parent_trace_id: int | None = None,
    ) -> AdaptiveRunResult:
        stage_runs: list[DecisionGraphStageRun] = []
        merged_context, valid_ingestion_ids = self.ingestion_service.merge_context(db, ingestion_ids)
        stage_runs.append(
            self._stage(
                "context_ingestion",
                lambda: {"ingestion_ids": valid_ingestion_ids, "summary": merged_context},
                input_ref=",".join(str(item) for item in ingestion_ids),
                status="success" if valid_ingestion_ids else "skipped",
            )
        )
        fused_context, context_signals, memory_hints = self._fuse_context(db, family, payload, valid_ingestion_ids, merged_context)
        stage_runs.append(
            self._stage(
                "context_fusion",
                lambda: {"summary": fused_context, "context_signals": [item.model_dump() for item in context_signals]},
                input_ref=f"family:{family.family_id}",
            )
        )

        signal = self.signal_agent.evaluate(db=db, family_id=family.family_id)
        stage_runs.append(self._stage("signal_eval", lambda: signal.model_dump(), input_ref=f"family:{family.family_id}"))

        emotion = self.emotion_agent.assess(payload=payload, fused_text=fused_context, historical_patterns=memory_hints)
        stage_runs.append(self._stage("emotion_eval", lambda: emotion.model_dump(), input_ref="fused-context"))

        trigger = self._build_replan_trigger(
            payload=replan_event or payload,
            ingestion_ids=valid_ingestion_ids,
            previous_plan_revision=previous_plan_revision,
        )

        state = self.friction_agent._derive_state(payload, signal)
        selected_cards, bundle, _ = RetrievalService(db).retrieve_bundle(
            family_id=family.family_id,
            scenario=state.retrieval_scenario,
            intensity=state.intensity,
            profile=family.child_profile,
            extra_context=fused_context,
            max_cards=3,
        )
        stage_runs.append(
            self._stage(
                "evidence_recall",
                lambda: {
                    "selected_card_ids": bundle.selected_card_ids,
                    "selected_evidence_unit_ids": bundle.selected_evidence_unit_ids,
                    "insufficient_evidence": bundle.insufficient_evidence,
                },
                input_ref=state.retrieval_scenario,
                status="fallback" if bundle.insufficient_evidence else "success",
                fallback_used=bundle.insufficient_evidence,
            )
        )
        support = self.friction_agent.generate_support(
            db=db,
            family=family,
            signal=signal,
            payload=payload,
            cards=selected_cards,
            evidence_bundle=bundle,
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
            free_text=fused_context,
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

        coordination = self.coordinator_agent.coordinate(
            support=support,
            emotion=emotion,
            safety=safety,
            evidence_review=evidence_review,
            support_available=payload.support_available,
            prefer_lighter=prefer_lighter,
            prefer_handoff=prefer_handoff,
        )
        if trigger.trigger_type in {"support_arrived", "user_requests_handoff"} and coordination.decision.active_mode != "blocked":
            adapted_support, changed_fields = self.coordinator_agent._adapt_support(coordination.support, "handoff")
            coordination = CoordinationResult(
                support=adapted_support,
                decision=coordination.decision.model_copy(
                    update={
                        "active_mode": "handoff",
                        "summary": adapted_support.situation_summary,
                        "now_step": adapted_support.action_plan[0].action,
                        "now_script": adapted_support.action_plan[0].parent_script,
                        "next_if_not_working": adapted_support.exit_plan[0],
                    }
                ),
                proposals=coordination.proposals,
                changed_fields=changed_fields,
            )
        elif trigger.trigger_type in {"caregiver_overloaded", "user_requests_lighter"} and coordination.decision.active_mode not in {"blocked", "handoff"}:
            adapted_support, changed_fields = self.coordinator_agent._adapt_support(coordination.support, "lighter")
            coordination = CoordinationResult(
                support=adapted_support,
                decision=coordination.decision.model_copy(
                    update={
                        "active_mode": "lighter",
                        "summary": adapted_support.situation_summary,
                        "now_step": adapted_support.action_plan[0].action,
                        "now_script": adapted_support.action_plan[0].parent_script,
                        "next_if_not_working": adapted_support.exit_plan[0],
                    }
                ),
                proposals=coordination.proposals,
                changed_fields=changed_fields,
            )
        stage_runs.append(
            self._stage(
                "coordination",
                lambda: coordination.decision.model_dump(),
                input_ref="multi-agent",
                status="blocked" if coordination.decision.active_mode == "blocked" else "success",
            )
        )

        goal = self._build_goal_spec(payload=payload, signal=signal, emotion=emotion, active_mode=coordination.decision.active_mode)
        stage_runs.append(
            self._stage(
                "goal_interpretation",
                lambda: {
                    "goal": goal.model_dump(),
                    "trigger": trigger.model_dump(),
                },
                input_ref="friction-session",
            )
        )

        task_tree = self._build_task_tree(
            support=coordination.support,
            coordination=coordination.decision,
            trigger=trigger,
            compact=False,
        )
        stage_runs.append(
            self._stage(
                "task_decomposition",
                lambda: {
                    "task_ids": [item.task_id for item in task_tree],
                    "fallback_edges": {item.task_id: item.fallback_task_ids for item in task_tree if item.fallback_task_ids},
                },
                input_ref="runtime-planner",
            )
        )
        active_task = self._select_active_task(task_tree, coordination.decision.active_mode)
        stage_runs.append(
            self._stage(
                "candidate_simulation",
                lambda: {
                    "active_task_id": active_task.task_id if active_task else None,
                    "active_mode": coordination.decision.active_mode,
                },
                input_ref="task-tree",
            )
        )
        plan_review = self._review_task_tree(
            task_tree=task_tree,
            active_task=active_task,
            emotion=emotion,
            evidence_bundle=bundle,
            coordination=coordination.decision,
        )
        stage_runs.append(self._critic_stage("critic_reflection", plan_review))

        planner_retry_count = 0
        if plan_review.decision == "revise" and not safety_review.blocked:
            planner_retry_count = 1
            task_tree = self._build_task_tree(
                support=coordination.support,
                coordination=coordination.decision,
                trigger=trigger,
                compact=True,
            )
            active_task = self._select_active_task(task_tree, coordination.decision.active_mode)
            stage_runs.append(
                self._stage(
                    "replanner",
                    lambda: {
                        "trigger": trigger.trigger_type,
                        "retry_count": planner_retry_count,
                        "active_task_id": active_task.task_id if active_task else None,
                    },
                    input_ref="critic_reflection",
                    retry_count=planner_retry_count,
                )
            )
        else:
            stage_runs.append(
                self._stage(
                    "replanner",
                    lambda: {
                        "trigger": trigger.trigger_type,
                        "retry_count": planner_retry_count,
                        "active_task_id": active_task.task_id if active_task else None,
                    },
                    input_ref="critic_reflection",
                    status="skipped" if previous_plan_revision is None else "success",
                    retry_count=planner_retry_count,
                )
            )

        revision_diff = self._build_revision_diff(previous_plan_revision, task_tree, trigger, active_task)
        execution_state = self._build_execution_state(
            previous_plan_revision=previous_plan_revision,
            coordination=coordination.decision,
            trigger=trigger,
            active_task=active_task,
            revision_diff=revision_diff,
        )
        plan_revision = PlanRevision(
            revision_no=(previous_plan_revision.revision_no + 1) if previous_plan_revision else 1,
            parent_revision_no=previous_plan_revision.revision_no if previous_plan_revision else None,
            goal=goal,
            task_tree=task_tree,
            execution_state=execution_state,
            critic_verdicts=[safety_review, evidence_review, plan_review],
            revision_diff=revision_diff,
        )
        projected_support = self._project_support_for_runtime(coordination.support, active_task, execution_state)
        updated_coordination = coordination.decision.model_copy(
            update={
                "active_mode": execution_state.active_mode,
                "now_step": active_task.instructions[0] if active_task else coordination.decision.now_step,
                "now_script": active_task.say_this[0] if active_task and active_task.say_this else coordination.decision.now_script,
                "next_if_not_working": self._next_step_hint(task_tree, active_task, coordination.decision.next_if_not_working),
                "summary": projected_support.situation_summary,
            }
        )
        stage_runs.append(
            self._stage(
                "executor",
                lambda: {
                    "active_task_id": execution_state.active_task_id,
                    "active_mode": execution_state.active_mode,
                    "latest_critic_verdicts": execution_state.latest_critic_verdicts,
                },
                input_ref="plan-revision",
                retry_count=planner_retry_count,
            )
        )

        changed_fields = self._changed_fields(
            previous_risk,
            previous_emotion,
            previous_support,
            previous_coordination,
            signal,
            emotion,
            CoordinationResult(
                support=projected_support,
                decision=updated_coordination,
                proposals=coordination.proposals,
                changed_fields=coordination.changed_fields,
            ),
        )
        final_status, final_reason = self._finalize(
            safety_review=safety_review,
            evidence_review=evidence_review,
            bundle=bundle,
            stage_runs=stage_runs,
        )
        trace_id = self._persist_trace(
            db=db,
            family_id=family.family_id,
            request_context={
                **payload.model_dump(),
                "ingestion_ids": valid_ingestion_ids,
                "prefer_lighter": prefer_lighter,
                "prefer_handoff": prefer_handoff,
            },
            signal_result=signal.model_dump(),
            retrieval_bundle=bundle,
            candidate_output={
                "support": projected_support.model_dump(),
                "emotion": emotion.model_dump(),
                "coordination": updated_coordination.model_dump(),
                "agent_proposals": [item.model_dump() for item in coordination.proposals],
                "plan_revision": plan_revision.model_dump(),
            },
            safety_review=safety_review,
            evidence_review=evidence_review,
            final_status=final_status,
            final_reason=final_reason,
            stage_runs=stage_runs,
            entry_signal_ids=valid_ingestion_ids,
            plan_tree=task_tree,
            execution_state=execution_state,
            revision_no=plan_revision.revision_no,
            parent_trace_id=parent_trace_id,
            replan_reason=revision_diff.summary,
        )
        return AdaptiveRunResult(
            signal=signal,
            emotion=emotion,
            support=projected_support,
            coordination=updated_coordination,
            proposals=coordination.proposals,
            evidence_bundle=bundle,
            safety=safety,
            safety_review=safety_review,
            evidence_review=evidence_review,
            trace_id=trace_id,
            stage_runs=stage_runs,
            changed_fields=changed_fields,
            final_status=final_status,
            final_reason=final_reason,
            fused_context=fused_context,
            context_signals=context_signals,
            plan_revision=plan_revision,
            active_task=active_task,
            critic_verdicts=[safety_review, evidence_review, plan_review],
            replan_reason=revision_diff.summary,
            revision_diff=revision_diff,
            parent_trace_id=parent_trace_id,
        )

    def _fuse_context(
        self,
        db: Session,
        family: Family,
        payload: V3FrictionSessionStartRequest,
        ingestion_ids: list[int],
        merged_context: str,
    ) -> tuple[str, list[ContextSignalRead], list[str]]:
        signals: list[ContextSignalRead] = []
        for ingestion_id in ingestion_ids:
            item = self.ingestion_service.get(db, ingestion_id)
            if item is None:
                continue
            signals.extend(item.context_signals[:2])

        latest_checkin = db.scalar(
            select(DailyCheckin).where(DailyCheckin.family_id == family.family_id).order_by(desc(DailyCheckin.date)).limit(1)
        )
        checkin_summary = ""
        if latest_checkin is not None:
            checkin_summary = (
                f"最近签到：孩子升级 {latest_checkin.meltdown_count} 次，"
                f"感官 {latest_checkin.sensory_overload_level}，家长压力 {latest_checkin.caregiver_stress:g}/10。"
            )
        profile = family.child_profile
        profile_summary = ""
        if profile is not None:
            profile_summary = (
                f"档案触发器：{'、'.join(profile.triggers[:3]) or '未记录'}；"
                f"有效安抚：{'、'.join(profile.soothing_methods[:3]) or '未记录'}；"
                f"禁忌：{'、'.join(profile.donts[:2]) or '未记录'}。"
            )
        memory_diff = self.policy_learning.build_diff(db, family.family_id)
        memory_hints = [item.target_key for item in memory_diff.strongest_positive[:2] if item.target_kind in {"handoff_pattern", "emotion_pattern"}]
        memory_summary = f"家庭历史偏好：{'、'.join(memory_hints)}。" if memory_hints else ""
        fused_context = " ".join(
            part for part in [payload.free_text, merged_context, checkin_summary, profile_summary, memory_summary] if part
        ).strip()
        return fused_context, signals[:6], memory_hints

    def _build_state_payload(
        self,
        payload: V3FrictionSessionStartRequest,
        ingestion_ids: list[int],
        result: AdaptiveRunResult,
    ) -> dict[str, Any]:
        return {
            "payload": payload.model_dump(),
            "ingestion_ids": ingestion_ids,
            "risk": result.signal.model_dump(),
            "emotion": result.emotion.model_dump(),
            "support": result.support.model_dump(),
            "coordination": result.coordination.model_dump(),
            "evidence_bundle": result.evidence_bundle.model_dump(),
            "trace_id": result.trace_id,
            "trace_summary": [item.model_dump() for item in result.stage_runs],
            "plan_revision": result.plan_revision.model_dump(),
            "active_task": result.active_task.model_dump() if result.active_task else None,
            "task_tree": [item.model_dump() for item in result.plan_revision.task_tree],
            "execution_state": result.plan_revision.execution_state.model_dump(),
            "critic_verdicts": [item.model_dump() for item in result.critic_verdicts],
            "replan_reason": result.replan_reason,
            "revision_diff": result.revision_diff.model_dump(),
            "context_signals": [item.model_dump() for item in result.context_signals],
            "used_memory_signals": self._used_memory_signals(result),
            "adaptation_history": [],
            "prefer_lighter": result.coordination.active_mode == "lighter",
            "prefer_handoff": result.coordination.active_mode == "handoff",
        }

    def _should_rerun(self, session: AdaptiveSession, payload: V3FrictionSessionEventRequest) -> bool:
        if payload.event_kind in {
            "request_lighter",
            "request_handoff",
            "no_improvement",
            "caregiver_overloaded",
            "child_escalating",
            "support_arrived",
            "new_context_ingested",
        }:
            return True
        if payload.ingestion_id is not None:
            return True
        if payload.event_kind == "status_check":
            age_seconds = max(0, int((utc_now() - session.updated_at).total_seconds()))
            return age_seconds >= 180 or any(token in payload.raw_text for token in ("还是", "仍然", "没改善"))
        return bool(payload.raw_text.strip())

    def _build_replan_trigger(
        self,
        *,
        payload: V3FrictionSessionStartRequest | V3FrictionSessionEventRequest,
        ingestion_ids: list[int],
        previous_plan_revision: PlanRevision | None,
    ) -> ReplanTrigger:
        if previous_plan_revision is None:
            return ReplanTrigger(
                trigger_type="session_start",
                source_event="session_start",
                summary="首次进入高摩擦会话，先建立一版可执行任务树。",
            )

        event_kind = getattr(payload, "event_kind", "text_update")
        raw_text = getattr(payload, "raw_text", "").strip()
        if event_kind == "request_lighter":
            return ReplanTrigger(
                trigger_type="user_requests_lighter",
                source_event=event_kind,
                summary="用户要求更轻方案，系统压缩任务树并下调执行负担。",
            )
        if event_kind == "request_handoff":
            return ReplanTrigger(
                trigger_type="user_requests_handoff",
                source_event=event_kind,
                summary="用户明确请求交接，系统切到 handoff 子树。",
            )
        if event_kind == "support_arrived":
            return ReplanTrigger(
                trigger_type="support_arrived",
                source_event=event_kind,
                summary="新的支持者已到场，系统允许切换到交接路径。",
            )
        if event_kind == "caregiver_overloaded" or any(token in raw_text for token in ("撑不住", "跟不上", "太累")):
            return ReplanTrigger(
                trigger_type="caregiver_overloaded",
                source_event=event_kind,
                summary="照护者负荷继续升高，任务树压缩为更轻的一步。",
            )
        if event_kind == "child_escalating" or any(token in raw_text for token in ("升级", "尖叫", "躺地", "打人")):
            return ReplanTrigger(
                trigger_type="child_escalating",
                source_event=event_kind,
                summary="孩子升级或接近失控，系统中止推进分支并切回共调节/退场。",
            )
        if getattr(payload, "ingestion_id", None) is not None or event_kind == "new_context_ingested":
            return ReplanTrigger(
                trigger_type="new_context_ingested",
                source_event=event_kind,
                summary="新上下文已并入，会基于最新线索刷新受影响任务。",
            )
        return ReplanTrigger(
            trigger_type="no_improvement",
            source_event=event_kind,
            summary="当前动作暂未见效，系统切到明确 fallback 或 exit 路径。",
        )

    @staticmethod
    def _build_goal_spec(
        *,
        payload: V3FrictionSessionStartRequest,
        signal: SignalOutput,
        emotion: EmotionAssessment,
        active_mode: str,
    ) -> GoalSpec:
        scenario = payload.custom_scenario.strip() or payload.scenario
        return GoalSpec(
            goal_id=f"friction-{scenario}",
            title=f"{scenario}高摩擦时刻先稳住现场",
            success_definition="孩子和照护者都回到可继续执行、可退场或可交接的状态。",
            constraints=[
                f"风险等级 {signal.risk_level}",
                f"孩子过载 {emotion.child_overload_level}",
                f"家长过载 {emotion.caregiver_overload_level}",
                f"当前模式 {active_mode}",
            ],
        )

    def _build_task_tree(
        self,
        *,
        support: FrictionSupportPlan,
        coordination: CoordinationDecision,
        trigger: ReplanTrigger,
        compact: bool,
    ) -> list[TaskNode]:
        active_kind = "stabilize"
        if coordination.active_mode == "handoff":
            active_kind = "handoff"
        elif coordination.active_mode == "blocked":
            active_kind = "exit"

        primary_script = support.say_this[0] if support.say_this else support.action_plan[0].parent_script
        primary_node = TaskNode(
            task_id="task-now",
            parent_task_id=None,
            goal=support.action_plan[0].action,
            kind=active_kind,  # type: ignore[arg-type]
            priority=1.0,
            status="active",
            preconditions=["先减少额外刺激", "只保留一位沟通者"],
            success_signals=["孩子开始跟随一个动作", "照护者能继续执行当前一步"],
            failure_signals=["3 分钟后仍无改善", "孩子继续升级", "照护者表示跟不上"],
            fallback_task_ids=["task-fallback", "task-exit"],
            instructions=[support.action_plan[0].action, *support.low_stim_mode.actions[:1]][:2],
            say_this=[primary_script],
            citations=support.citations,
            why_now=support.action_plan[0].why_it_fits,
            depth=0,
        )
        fallback_node = TaskNode(
            task_id="task-fallback",
            parent_task_id="task-now",
            goal=support.low_stim_mode.actions[0],
            kind="co_regulate",
            priority=0.8,
            status="active" if coordination.active_mode == "lighter" else "pending",
            preconditions=["当前一步仍无改善"],
            success_signals=["孩子刺激下降", "现场语言量能继续降低"],
            failure_signals=["孩子继续升级", "需要他人接手"],
            fallback_task_ids=["task-exit"],
            instructions=support.low_stim_mode.actions[: min(2, len(support.low_stim_mode.actions))],
            say_this=support.say_this[:1] or [primary_script],
            citations=support.citations,
            why_now="这是当前最轻的一条可执行路径。",
            depth=1,
        )
        handoff_text = support.handoff_messages[1].text if len(support.handoff_messages) > 1 else support.handoff_messages[0].text
        handoff_node = TaskNode(
            task_id="task-handoff",
            parent_task_id="task-now",
            goal="发起交接并让支持者接手下一步。",
            kind="handoff",
            priority=0.7,
            status="active" if coordination.active_mode == "handoff" else "pending",
            preconditions=["有支持者可接手"],
            success_signals=["已明确谁接手", "主照护者负荷下降"],
            failure_signals=["无人接手", "交接后仍升级"],
            fallback_task_ids=["task-exit"],
            instructions=["用最短一句话发起交接", "说明孩子此刻更需要哪种支持"],
            say_this=[handoff_text],
            citations=support.citations,
            why_now="当前局面更适合减少正面对抗，先把支持接住。",
            depth=1,
        )
        exit_node = TaskNode(
            task_id="task-exit",
            parent_task_id="task-now",
            goal=support.exit_plan[0],
            kind="exit",
            priority=0.9,
            status="active" if coordination.active_mode == "blocked" else "pending",
            preconditions=["当前策略无法继续安全执行"],
            success_signals=["孩子离开高刺激现场", "对抗不再继续加码"],
            failure_signals=["出现高风险", "需要外部帮助"],
            fallback_task_ids=[],
            instructions=support.exit_plan[:2],
            say_this=support.crisis_card.say_this[:1] or support.say_this[:1],
            citations=support.citations,
            why_now="保留清晰退场路径，避免现场卡死。",
            depth=1,
        )
        observe_node = TaskNode(
            task_id="task-observe",
            parent_task_id="task-now",
            goal="观察 2-3 分钟并判断是否继续、减负或退场。",
            kind="observe",
            priority=0.5,
            status="pending",
            preconditions=["已经执行当前一步"],
            success_signals=["孩子更稳定", "照护者能继续跟住"],
            failure_signals=["没有改善", "出现新的升级线索"],
            fallback_task_ids=["task-fallback", "task-handoff", "task-exit"],
            instructions=[support.feedback_prompt],
            say_this=["我先看 2-3 分钟，再决定要继续、减轻还是交接。"],
            citations=support.citations,
            why_now=f"当前触发：{trigger.summary}",
            depth=1,
        )

        task_tree = [primary_node, fallback_node, handoff_node, exit_node, observe_node]
        if compact:
            keep = {"task-now", "task-fallback", "task-handoff", "task-exit"}
            task_tree = [item for item in task_tree if item.task_id in keep]
            primary_node.instructions = primary_node.instructions[:1]
            fallback_node.instructions = fallback_node.instructions[:1]
        return task_tree

    @staticmethod
    def _select_active_task(task_tree: list[TaskNode], active_mode: str) -> TaskNode | None:
        preferred_task_id = {
            "continue": "task-now",
            "lighter": "task-fallback",
            "handoff": "task-handoff",
            "blocked": "task-exit",
        }.get(active_mode, "task-now")
        for item in task_tree:
            if item.task_id == preferred_task_id:
                return item
        return task_tree[0] if task_tree else None

    @staticmethod
    def _review_task_tree(
        *,
        task_tree: list[TaskNode],
        active_task: TaskNode | None,
        emotion: EmotionAssessment,
        evidence_bundle: RetrievalEvidenceBundle,
        coordination: CoordinationDecision,
    ) -> CriticReview:
        reasons: list[str] = []
        if len(task_tree) > 5:
            reasons.append("当前任务树过密，现场不宜同时暴露太多分支。")
        if not any(item.kind == "exit" for item in task_tree):
            reasons.append("当前任务树缺少明确 exit 路径。")
        if active_task is None:
            reasons.append("当前没有可执行的 active task。")
        elif emotion.caregiver_overload_level == "high" and len(active_task.instructions) > 1:
            reasons.append("照护者负荷偏高，当前第一步仍然偏重。")
        if evidence_bundle.insufficient_evidence and coordination.active_mode == "continue":
            reasons.append("证据仍有缺口时，不宜保持完整推进模式。")

        if reasons:
            return CriticReview(
                critic="plan",
                decision="revise",
                blocked=False,
                issue_type="plan_quality",
                reasons=reasons[:5],
                summary="计划结构需要压缩后再执行。",
            )
        return CriticReview(
            critic="plan",
            decision="pass",
            blocked=False,
            reasons=[],
            summary="任务树结构可执行。",
        )

    @staticmethod
    def _build_revision_diff(
        previous_plan_revision: PlanRevision | None,
        task_tree: list[TaskNode],
        trigger: ReplanTrigger,
        active_task: TaskNode | None,
    ) -> PlanRevisionDiff:
        previous_ids = {item.task_id for item in previous_plan_revision.task_tree} if previous_plan_revision else set()
        new_ids = {item.task_id for item in task_tree}
        return PlanRevisionDiff(
            trigger=trigger,
            affected_task_ids=sorted(new_ids if not previous_ids else previous_ids | new_ids)[:6],
            dropped_task_ids=sorted(previous_ids - new_ids)[:6],
            added_task_ids=sorted(new_ids - previous_ids)[:6],
            active_task_before=previous_plan_revision.execution_state.active_task_id if previous_plan_revision else None,
            active_task_after=active_task.task_id if active_task else None,
            summary=trigger.summary,
        )

    @staticmethod
    def _build_execution_state(
        *,
        previous_plan_revision: PlanRevision | None,
        coordination: CoordinationDecision,
        trigger: ReplanTrigger,
        active_task: TaskNode | None,
        revision_diff: PlanRevisionDiff,
    ) -> ExecutionState:
        completed_task_ids = list(previous_plan_revision.execution_state.completed_task_ids) if previous_plan_revision else []
        failed_task_ids = list(previous_plan_revision.execution_state.failed_task_ids) if previous_plan_revision else []
        dropped_task_ids = list(previous_plan_revision.execution_state.dropped_task_ids) if previous_plan_revision else []
        if previous_plan_revision and previous_plan_revision.execution_state.active_task_id and trigger.trigger_type != "session_start":
            if trigger.trigger_type in {"no_improvement", "caregiver_overloaded", "child_escalating"}:
                failed_task_ids.append(previous_plan_revision.execution_state.active_task_id)
            elif trigger.trigger_type == "support_arrived":
                completed_task_ids.append(previous_plan_revision.execution_state.active_task_id)
        dropped_task_ids.extend(revision_diff.dropped_task_ids)
        latest_critic_verdicts = []
        if trigger.trigger_type in {"caregiver_overloaded", "user_requests_lighter"}:
            latest_critic_verdicts.append("已切到更轻的一步。")
        if trigger.trigger_type in {"child_escalating", "no_improvement"}:
            latest_critic_verdicts.append("已保留 fallback / exit 路径。")
        if trigger.trigger_type in {"support_arrived", "user_requests_handoff"}:
            latest_critic_verdicts.append("已切到交接分支。")
        return ExecutionState(
            active_task_id=active_task.task_id if active_task else None,
            completed_task_ids=list(dict.fromkeys(completed_task_ids))[:8],
            failed_task_ids=list(dict.fromkeys(failed_task_ids))[:8],
            dropped_task_ids=list(dict.fromkeys(dropped_task_ids))[:8],
            latest_event=trigger,
            active_mode=coordination.active_mode,
            latest_critic_verdicts=latest_critic_verdicts[:4],
        )

    @staticmethod
    def _project_support_for_runtime(
        support: FrictionSupportPlan,
        active_task: TaskNode | None,
        execution_state: ExecutionState,
    ) -> FrictionSupportPlan:
        if active_task is None:
            return support
        current_step = support.action_plan[0].model_copy(
            update={
                "title": "现在先做这一步",
                "action": active_task.instructions[0],
                "parent_script": active_task.say_this[0],
                "why_it_fits": active_task.why_now,
            }
        )
        mode_labels = {
            "continue": "按当前路径推进",
            "lighter": "已压缩成更轻的一步",
            "handoff": "已切换到交接模式",
            "blocked": "当前仅保留安全退场",
        }
        return support.model_copy(
            update={
                "headline": f"{support.headline} · {mode_labels.get(execution_state.active_mode, '继续观察')}",
                "situation_summary": f"{support.situation_summary} 当前 active task：{active_task.goal}",
                "action_plan": [current_step, *support.action_plan[1:]],
                "feedback_prompt": "执行当前这一步后，告诉我是否有改善；系统会基于任务树切下一条路径。",
            }
        )

    @staticmethod
    def _next_step_hint(task_tree: list[TaskNode], active_task: TaskNode | None, fallback: str) -> str:
        if active_task is None or not active_task.fallback_task_ids:
            return fallback
        next_task = next((item for item in task_tree if item.task_id == active_task.fallback_task_ids[0]), None)
        if next_task is None:
            return fallback
        return next_task.instructions[0]

    def _changed_fields(
        self,
        previous_risk: SignalOutput | None,
        previous_emotion: EmotionAssessment | None,
        previous_support: FrictionSupportPlan | None,
        previous_coordination: CoordinationDecision | None,
        signal: SignalOutput,
        emotion: EmotionAssessment,
        coordination: CoordinationResult,
    ) -> list[str]:
        changed: list[str] = []
        if previous_risk is None or previous_risk.risk_level != signal.risk_level:
            changed.append("risk")
        if previous_emotion is None or previous_emotion.child_overload_level != emotion.child_overload_level:
            changed.append("child_overload")
        if previous_emotion is None or previous_emotion.caregiver_overload_level != emotion.caregiver_overload_level:
            changed.append("caregiver_overload")
        if previous_coordination is None or previous_coordination.active_mode != coordination.decision.active_mode:
            changed.append("coordination")
        if previous_support is None or previous_support.action_plan[0].action != coordination.support.action_plan[0].action:
            changed.append("support")
        return changed

    def _session_read(self, session: AdaptiveSession) -> AdaptiveSessionRead:
        return AdaptiveSessionRead(
            session_id=session.id,
            incident_id=session.incident_id,
            family_id=session.family_id,
            chain=session.chain,  # type: ignore[arg-type]
            status=session.status,  # type: ignore[arg-type]
            current_state_version=session.current_state_version,
            active_plan_summary=session.active_plan_summary_json,
            next_check_in_hint=session.next_check_in_hint,
            last_trace_id=session.last_trace_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    def _event_read(self, event: SessionEvent) -> SessionEventRead:
        return SessionEventRead(
            event_id=event.id,
            source_type=event.source_type,  # type: ignore[arg-type]
            event_kind=event.event_kind,  # type: ignore[arg-type]
            raw_text=event.raw_text,
            ingestion_id=event.ingestion_id,
            replanned=event.replanned,
            created_at=event.created_at,
        )

    def _decision_state_from_session(self, session: AdaptiveSession):
        state = dict(session.current_state_json or {})
        return build_decision_state(
            session_id=session.id,
            family_id=session.family_id,
            chain=session.chain,
            state_version=session.current_state_version,
            latest_inputs=dict(state.get("payload", {})),
            context_signals=[ContextSignalRead.model_validate(item) for item in state.get("context_signals", [])],
            risk_assessment=SignalOutput.model_validate(state["risk"]) if state.get("risk") else None,
            emotion_assessment=EmotionAssessment.model_validate(state["emotion"]) if state.get("emotion") else None,
            retrieval_bundle=RetrievalEvidenceBundle.model_validate(state["evidence_bundle"]) if state.get("evidence_bundle") else None,
            coordination=CoordinationDecision.model_validate(state["coordination"]) if state.get("coordination") else None,
            active_plan_summary=dict(session.active_plan_summary_json or {}),
            used_memory_signals=list(state.get("used_memory_signals", [])),
            adaptation_history=list(state.get("adaptation_history", [])),
            trace_summary=[DecisionGraphStageRun.model_validate(item) for item in state.get("trace_summary", [])],
        )

    def _used_memory_signals(self, result: AdaptiveRunResult) -> list[str]:
        hints = [
            *result.evidence_bundle.personalization_applied[:2],
            *result.coordination.weight_summary[:2],
        ]
        return list(dict.fromkeys(item for item in hints if item))[:6]

    def _persist_trace(
        self,
        *,
        db: Session,
        family_id: int,
        request_context: dict[str, Any],
        signal_result: dict[str, Any],
        retrieval_bundle: RetrievalEvidenceBundle,
        candidate_output: dict[str, Any],
        safety_review: CriticReview,
        evidence_review: CriticReview,
        final_status: str,
        final_reason: str,
        stage_runs: list[DecisionGraphStageRun],
        entry_signal_ids: list[int],
        plan_tree: list[TaskNode],
        execution_state: ExecutionState,
        revision_no: int,
        parent_trace_id: int | None,
        replan_reason: str | None,
    ) -> int:
        row = DecisionTrace(
            family_id=family_id,
            chain="friction_support",
            final_status=final_status,
            graph_version=GRAPH_VERSION,
            stage_order_json=list(GRAPH_STAGES),
            stage_runs_json=[item.model_dump() for item in stage_runs],
            entry_signal_ids_json=entry_signal_ids,
            request_context_json=request_context,
            signal_result_json=signal_result,
            retrieval_bundle_json=retrieval_bundle.model_dump(),
            candidate_output_json=candidate_output,
            safety_review_json=safety_review.model_dump(),
            evidence_review_json=evidence_review.model_dump(),
            fallback_reason=None,
            final_reason=final_reason,
            plan_tree_json=[item.model_dump() for item in plan_tree],
            execution_state_json=execution_state.model_dump(),
            revision_no=revision_no,
            parent_trace_id=parent_trace_id,
            replan_reason=replan_reason,
        )
        db.add(row)
        db.flush()
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
        db.flush()
        return row.id

    def _finalize(
        self,
        *,
        safety_review: CriticReview,
        evidence_review: CriticReview,
        bundle: RetrievalEvidenceBundle,
        stage_runs: list[DecisionGraphStageRun],
    ) -> tuple[str, str]:
        if safety_review.blocked:
            final_status = "blocked"
            final_reason = safety_review.summary
        elif evidence_review.blocked:
            final_status = "blocked"
            final_reason = evidence_review.summary
        else:
            final_status = "success"
            final_reason = (
                "会话式多 Agent 决策完成，但证据仍建议继续澄清。"
                if evidence_review.decision == "needs_clarification"
                else "会话式多 Agent 决策完成。"
            )
        stage_runs.append(
            self._stage(
                "finalizer",
                lambda: {
                    "final_status": final_status,
                    "final_reason": final_reason,
                    "insufficient_evidence": bundle.insufficient_evidence,
                },
                input_ref="graph",
                status=final_status if final_status == "blocked" else "success",
            )
        )
        return final_status, final_reason

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

    @staticmethod
    def _incident_intensity(payload: V3FrictionSessionStartRequest, emotion: EmotionAssessment) -> str:
        if payload.high_risk_selected or emotion.child_overload_level == "high":
            return "heavy"
        if emotion.caregiver_overload_level == "high" or payload.transition_difficulty >= 7:
            return "medium"
        return "light"

    @staticmethod
    def _outcome_score(effectiveness: str, child_state_after: str, caregiver_state_after: str) -> int:
        score = {"helpful": 2, "somewhat": 1, "not_helpful": -1}[effectiveness]
        if child_state_after == "still_escalating":
            score -= 1
        if caregiver_state_after == "more_overloaded":
            score -= 1
        return max(-2, min(2, score))
