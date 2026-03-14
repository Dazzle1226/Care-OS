from __future__ import annotations

from typing import Any

from app.schemas.domain import (
    ContextSignalRead,
    CoordinationDecision,
    DecisionGraphStageRun,
    DecisionStateRead,
    EmotionAssessment,
    RetrievalEvidenceBundle,
    SignalOutput,
)


def build_decision_state(
    *,
    session_id: int,
    family_id: int,
    chain: str,
    state_version: int,
    latest_inputs: dict[str, Any],
    context_signals: list[ContextSignalRead],
    risk_assessment: SignalOutput | None,
    emotion_assessment: EmotionAssessment | None,
    retrieval_bundle: RetrievalEvidenceBundle | None,
    coordination: CoordinationDecision | None,
    active_plan_summary: dict[str, Any],
    used_memory_signals: list[str],
    adaptation_history: list[str],
    trace_summary: list[DecisionGraphStageRun],
) -> DecisionStateRead:
    return DecisionStateRead(
        session_id=session_id,
        family_id=family_id,
        chain=chain,  # type: ignore[arg-type]
        state_version=state_version,
        latest_inputs=latest_inputs,
        context_signals=context_signals,
        risk_assessment=risk_assessment,
        emotion_assessment=emotion_assessment,
        retrieval_bundle=retrieval_bundle,
        coordination=coordination,
        active_plan_summary=active_plan_summary,
        used_memory_signals=used_memory_signals[:6],
        adaptation_history=adaptation_history[-8:],
        trace_summary=trace_summary,
    )
