from __future__ import annotations

from typing import Any

from app.schemas.domain import CriticReview, RetrievalEvidenceBundle


class EvidenceCritic:
    def review(
        self,
        candidate_output: Any,
        evidence_bundle: RetrievalEvidenceBundle | None,
        *,
        fallback_used: bool = False,
    ) -> CriticReview:
        reasons: list[str] = []
        citations = list(getattr(candidate_output, "citations", []) or [])
        selected_card_ids = set(evidence_bundle.selected_card_ids if evidence_bundle else [])

        if not citations:
            reasons.append("候选结果缺少 citations。")
        if evidence_bundle is None:
            reasons.append("缺少检索证据包，无法解释排序来源。")
        else:
            if not evidence_bundle.candidate_scores:
                reasons.append("证据包缺少候选评分。")
            if not evidence_bundle.selection_reasons:
                reasons.append("证据包缺少入选理由。")
            if not evidence_bundle.rejected_reasons:
                reasons.append("证据包缺少排除理由。")
            if not evidence_bundle.selected_evidence_unit_ids:
                reasons.append("证据包缺少证据单元。")
            if not evidence_bundle.selected_chunk_ids:
                reasons.append("证据包缺少知识块选择。")
            if not evidence_bundle.coverage_scores:
                reasons.append("证据包缺少覆盖度评估。")
            if evidence_bundle.coverage_scores.get("safety", 0.0) < 0.5:
                reasons.append("证据包未覆盖 safety 维度。")
            if not evidence_bundle.query_plan:
                reasons.append("证据包缺少 query plan。")
            if not evidence_bundle.selected_sources:
                reasons.append("证据包缺少来源摘要。")

        if selected_card_ids and any(card_id not in selected_card_ids for card_id in citations):
            reasons.append("输出引用与检索入选卡片不一致。")

        blocked = bool(reasons)
        if blocked:
            decision = "block"
        elif fallback_used:
            decision = "fallback_ok"
        elif evidence_bundle is not None and evidence_bundle.insufficient_evidence:
            decision = "needs_clarification"
        else:
            decision = "pass"

        if not blocked and evidence_bundle is not None and evidence_bundle.insufficient_evidence:
            summary = f"证据链通过，但当前仍缺少 {', '.join(evidence_bundle.missing_dimensions[:3])} 维度覆盖。"
        else:
            summary = "证据链完整，可解释性通过。" if not blocked else "证据链不完整，已阻断输出。"
        issue_type = None
        if blocked:
            if any("不一致" in reason for reason in reasons):
                issue_type = "citation_mismatch"
            elif any("覆盖" in reason for reason in reasons):
                issue_type = "insufficient_coverage"
            else:
                issue_type = "missing_evidence"
        return CriticReview(
            critic="evidence",
            decision=decision,  # type: ignore[arg-type]
            blocked=blocked,
            issue_type=issue_type,
            reasons=reasons[:5],
            summary=summary,
        )
