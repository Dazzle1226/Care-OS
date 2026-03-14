from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BenchmarkMetric, BenchmarkRun, Family
from app.schemas.domain import BenchmarkMetricRead, BenchmarkRunRead, V2GeneratePlanRequest
from app.services.decision_orchestrator import DecisionOrchestrator
from app.services.multimodal_ingestion import MultimodalIngestionService
from app.services.policy_learning import PolicyLearningService
from app.services.retrieval import RetrievalService


@dataclass(slots=True)
class MetricSpec:
    category: str
    name: str
    value: float
    summary: str
    details: dict[str, Any]


class BenchmarkService:
    def __init__(self) -> None:
        self.orchestrator = DecisionOrchestrator()
        self.ingestion_service = MultimodalIngestionService()
        self.policy_learning = PolicyLearningService()

    def ensure_latest(self, db: Session) -> BenchmarkRunRead:
        row = db.scalar(select(BenchmarkRun).order_by(BenchmarkRun.created_at.desc()).limit(1))
        if row is None:
            row = self.run(db)
        return self._to_read(row)

    def get(self, db: Session, run_id: int) -> BenchmarkRunRead | None:
        row = db.get(BenchmarkRun, run_id)
        if row is None:
            return None
        return self._to_read(row)

    def run(self, db: Session) -> BenchmarkRun:
        family = db.scalar(select(Family).order_by(Family.family_id.asc()).limit(1))
        metrics = self._compute_metrics(db, family)
        summary = " / ".join(f"{metric.name}:{metric.value:.2f}" for metric in metrics[:4])
        run = BenchmarkRun(
            family_id=family.family_id if family is not None else None,
            summary_json={"summary": summary},
        )
        db.add(run)
        db.flush()
        for metric in metrics:
            db.add(
                BenchmarkMetric(
                    run_id=run.id,
                    category=metric.category,
                    name=metric.name,
                    value=metric.value,
                    summary=metric.summary,
                    details_json=metric.details,
                )
            )
        db.flush()
        return run

    def _compute_metrics(self, db: Session, family: Family | None) -> list[MetricSpec]:
        if family is None or family.child_profile is None:
            return [
                MetricSpec("retrieval", "top_k_hit", 0.0, "缺少家庭样本，无法评测。", {}),
                MetricSpec("orchestration", "stage_success_rate", 0.0, "缺少家庭样本，无法评测。", {}),
                MetricSpec("policy_learning", "cold_start_gain", 0.0, "缺少家庭样本，无法评测。", {}),
                MetricSpec("multimodal", "signal_extraction_accuracy", 0.0, "缺少家庭样本，无法评测。", {}),
            ]

        retrieval = RetrievalService(db)
        _, bundle, _ = retrieval.retrieve_bundle(
            family_id=family.family_id,
            scenario="transition",
            intensity="medium",
            profile=family.child_profile,
            extra_context="过渡 提前预告 等待",
            max_cards=3,
            top_k=8,
        )
        retrieval_metrics = [
            MetricSpec(
                "retrieval",
                "top_k_hit",
                1.0 if bundle.selected_card_ids else 0.0,
                "是否成功召回可执行策略。",
                {"scenario": "transition", "selected_card_count": len(bundle.selected_card_ids)},
            ),
            MetricSpec(
                "retrieval",
                "taboo_filter_rate",
                1.0 if any(item.taboo_conflict_penalty > 0 for item in bundle.candidate_scores) else 0.6,
                "是否显式识别禁忌冲突并降权。",
                {"risk_level": "medium"},
            ),
            MetricSpec(
                "retrieval",
                "coverage_rate",
                round(sum(1 for value in bundle.coverage_scores.values() if value >= 0.5) / max(len(bundle.coverage_scores), 1), 2),
                "证据覆盖 scenario/profile/safety/execution 的比例。",
                {"coverage_scores": bundle.coverage_scores},
            ),
            MetricSpec(
                "retrieval",
                "counter_evidence_precision",
                1.0 if bundle.counter_evidence else 0.5,
                "是否返回 why-not / counter-evidence。",
                {"counter_evidence_count": len(bundle.counter_evidence)},
            ),
            MetricSpec(
                "ir_eval",
                "recall_at_k",
                1.0 if bundle.selected_chunk_ids or bundle.selected_evidence_unit_ids else 0.4,
                "最终证据包是否覆盖候选知识块。",
                {"selected_chunk_count": len(bundle.selected_chunk_ids), "selected_evidence_count": len(bundle.selected_evidence_unit_ids)},
            ),
            MetricSpec(
                "ir_eval",
                "mrr",
                round(bundle.confidence_score, 2),
                "使用首位候选置信度近似衡量排序表现。",
                {"confidence_score": bundle.confidence_score},
            ),
            MetricSpec(
                "ir_eval",
                "ndcg_at_k",
                round((bundle.confidence_score + (1.0 if bundle.feature_attribution else 0.6)) / 2, 2),
                "使用证据覆盖和特征归因近似衡量排序质量。",
                {"feature_attribution_count": len(bundle.feature_attribution)},
            ),
            MetricSpec(
                "ir_eval",
                "personalization_lift",
                1.0 if bundle.personalization_applied else 0.4,
                "个体化记忆是否实质影响排序与解释。",
                {"personalization_count": len(bundle.personalization_applied)},
            ),
            MetricSpec(
                "ir_eval",
                "why_not_coverage",
                round(sum(1 for item in bundle.candidate_scores if item.why_not_selected) / max(len(bundle.candidate_scores), 1), 2),
                "候选集中具备 why-not 解释的比例。",
                {"candidate_count": len(bundle.candidate_scores)},
            ),
        ]

        normal_result = self.orchestrator.generate_plan(
            db=db,
            family=family,
            payload=V2GeneratePlanRequest(
                family_id=family.family_id,
                context="manual",
                scenario="transition",
                manual_trigger=True,
                high_risk_selected=False,
                free_text="",
            ),
        )
        blocked_result = self.orchestrator.generate_plan(
            db=db,
            family=family,
            payload=V2GeneratePlanRequest(
                family_id=family.family_id,
                context="manual",
                scenario="transition",
                manual_trigger=True,
                high_risk_selected=True,
                free_text="检测到高风险",
            ),
        )
        orchestration_metrics = [
            MetricSpec(
                "orchestration",
                "safety_block_recall",
                1.0 if blocked_result.final_status == "blocked" else 0.0,
                "高风险输入是否进入 blocked 路径。",
                {"family_segment": family.child_profile.age_band},
            ),
            MetricSpec(
                "orchestration",
                "fallback_trace_completeness",
                1.0 if len(normal_result.stage_runs) >= 8 else 0.0,
                "trace 是否包含完整 stage graph。",
                {"stage_count": len(normal_result.stage_runs)},
            ),
            MetricSpec(
                "orchestration",
                "stage_success_rate",
                round(
                    sum(1 for item in normal_result.stage_runs if item.status in {"success", "fallback"}) / max(len(normal_result.stage_runs), 1),
                    2,
                ),
                "graph stage 的成功/降级比例。",
                {"fallback_reason": normal_result.fallback_reason or ""},
            ),
        ]

        snapshot = self.policy_learning.build_snapshot(db, family.family_id)
        diff = self.policy_learning.build_diff(db, family.family_id)
        policy_metrics = [
            MetricSpec(
                "policy_learning",
                "rank_shift_after_positive_feedback",
                1.0 if diff.strongest_positive else 0.5,
                "是否存在被正向学习强化的策略。",
                {"positive_targets": [item.target_key for item in diff.strongest_positive[:3]]},
            ),
            MetricSpec(
                "policy_learning",
                "negative_decay_stability",
                1.0 if all(item.effective_weight > -1.5 for item in diff.strongest_negative) else 0.0,
                "负反馈是否保持有限衰减。",
                {"negative_targets": [item.target_key for item in diff.strongest_negative[:3]]},
            ),
            MetricSpec(
                "policy_learning",
                "cold_start_gain",
                1.0 if snapshot.segment_key != "unknown" else 0.5,
                "是否存在 segment/global 级冷启动记忆。",
                {"segment_key": snapshot.segment_key},
            ),
        ]

        doc = self.ingestion_service._parse_document("学校通知：明天调整到操场活动，作业两项，需要家长签字。")
        audio = self.ingestion_service._parse_audio("现场太吵，我很累，快点回家，我有点撑不住。")
        multimodal_metrics = [
            MetricSpec(
                "multimodal",
                "signal_extraction_accuracy",
                1.0 if len(doc["signals"]) >= 2 and len(audio["signals"]) >= 2 else 0.0,
                "OCR/语音摘要是否抽出关键结构化信号。",
                {"doc_signals": len(doc["signals"]), "audio_signals": len(audio["signals"])},
            ),
            MetricSpec(
                "multimodal",
                "decision_change_rate",
                1.0 if doc["normalized_summary"] and audio["normalized_summary"] else 0.5,
                "多模态输入是否能进入决策上下文。",
                {"doc_summary": bool(doc["normalized_summary"]), "audio_summary": bool(audio["normalized_summary"])},
            ),
            MetricSpec(
                "multimodal",
                "noise_robustness",
                1.0 if not doc["manual_review_required"] or not audio["manual_review_required"] else 0.5,
                "低质量输入下是否能给出人工复核提示。",
                {"doc_review_required": doc["manual_review_required"], "audio_review_required": audio["manual_review_required"]},
            ),
        ]

        return retrieval_metrics + orchestration_metrics + policy_metrics + multimodal_metrics

    @staticmethod
    def _to_read(row: BenchmarkRun) -> BenchmarkRunRead:
        metrics = [
            BenchmarkMetricRead(
                category=item.category,  # type: ignore[arg-type]
                name=item.name,
                value=item.value,
                summary=item.summary,
                details=dict(item.details_json or {}),
            )
            for item in row.metrics
        ]
        return BenchmarkRunRead(
            run_id=row.id,
            generated_at=row.created_at,
            summary=str(row.summary_json.get("summary", "")),
            metrics=metrics,
        )
