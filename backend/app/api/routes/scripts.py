from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.coach import CoachAgent
from app.api.deps import get_current_user
from app.core.time import utc_now
from app.db.base import get_db
from app.models import Family, IncidentLog, Review, User
from app.schemas.domain import (
    FrictionSupportFeedbackRequest,
    FrictionSupportFeedbackResponse,
    FrictionSupportGenerateRequest,
    FrictionSupportGenerateResponse,
    ScriptGenerateRequest,
    ScriptGenerateResponse,
)
from app.services.decision_orchestrator import DecisionOrchestrator
from app.services.policy_learning import PolicyLearningService

router = APIRouter(prefix="/scripts", tags=["scripts"])


def _friction_incident_scenario(payload: FrictionSupportGenerateRequest) -> str:
    return payload.custom_scenario.strip() or payload.scenario


def _friction_intensity(payload: FrictionSupportGenerateRequest) -> str:
    if (
        payload.low_stim_mode_requested
        or payload.quick_preset == "meltdown_now"
        or payload.child_state == "meltdown"
        or payload.sensory_overload_level == "heavy"
        or payload.meltdown_count >= 2
        or payload.caregiver_stress >= 8
    ):
        return "heavy"
    if payload.transition_difficulty >= 6 or payload.caregiver_fatigue >= 7:
        return "medium"
    return "light"


def _score_friction_feedback(
    effectiveness: str,
    child_state_after: str,
    caregiver_state_after: str,
) -> int:
    score = {
        "helpful": 2,
        "somewhat": 1,
        "not_helpful": -1,
    }[effectiveness]

    if child_state_after == "still_escalating":
        score -= 1
    if caregiver_state_after == "more_overloaded":
        score -= 1

    return max(-2, min(2, score))


def _next_adjustment(score: int, child_state_after: str, caregiver_state_after: str) -> str:
    if score >= 2:
        return "下次会继续优先当前三步顺序，并保留这组话术。"
    if score >= 0:
        if child_state_after == "still_escalating" or caregiver_state_after == "more_overloaded":
            return "下次会更早切到退场和低刺激恢复，减少口头解释。"
        return "下次会保留这个方向，但优先缩短指令并更早给过渡缓冲。"
    return "下次会降低这组策略权重，优先切换到更低刺激、可更快交接的方案。"


def _recommendation_for_feedback(score: int, caregiver_state_after: str) -> str:
    if score >= 1:
        return "continue"
    if caregiver_state_after == "more_overloaded" or score <= -1:
        return "replace"
    return "pause"


@router.post("/generate", response_model=ScriptGenerateResponse)
def generate_script(
    payload: ScriptGenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ScriptGenerateResponse:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    result = DecisionOrchestrator().generate_script(db=db, family=family, payload=payload)

    db.add(
        IncidentLog(
            family_id=payload.family_id,
            ts=utc_now(),
            scenario=payload.scenario,
            intensity=payload.intensity,
            triggers=[],
            selected_resources=payload.resources,
            high_risk_flag=payload.high_risk_selected,
            notes=payload.free_text,
        )
    )
    db.commit()

    if result.safety.blocked:
        return ScriptGenerateResponse(
            blocked=True,
            safety_block=result.safety.block,
            evidence_bundle=result.evidence_bundle if payload.include_debug else None,
            decision_trace_id=result.trace_id if payload.include_debug else None,
            decision_summary=result.safety_review.summary if payload.include_debug else None,
        )
    if result.evidence_review.blocked:
        db.commit()
        raise HTTPException(status_code=422, detail=result.evidence_review.summary)

    return ScriptGenerateResponse(
        blocked=False,
        script=result.script,
        evidence_bundle=result.evidence_bundle if payload.include_debug else None,
        decision_trace_id=result.trace_id if payload.include_debug else None,
        decision_summary=(
            "规则降级已触发，但证据链和安全审查通过。"
            if payload.include_debug and result.fallback_reason
            else (result.evidence_bundle.ranking_summary if payload.include_debug else None)
        ),
    )


@router.post("/friction-support", response_model=FrictionSupportGenerateResponse)
def generate_friction_support(
    payload: FrictionSupportGenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FrictionSupportGenerateResponse:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    result = DecisionOrchestrator().generate_friction_support(db=db, family=family, payload=payload)
    if result.safety.blocked:
        db.commit()
        return FrictionSupportGenerateResponse(
            blocked=True,
            risk=result.signal,
            safety_block=result.safety.block,
            evidence_bundle=result.evidence_bundle if payload.include_debug else None,
            decision_trace_id=result.trace_id if payload.include_debug else None,
            decision_summary=result.safety_review.summary if payload.include_debug else None,
        )
    if result.evidence_review.blocked:
        db.commit()
        raise HTTPException(status_code=422, detail=result.evidence_review.summary)

    incident = IncidentLog(
        family_id=payload.family_id,
        ts=utc_now(),
        scenario=_friction_incident_scenario(payload),
        intensity=_friction_intensity(payload),
        triggers=[payload.child_state, *payload.env_changes[:2]],
        selected_resources={
            "base_scenario": payload.scenario,
            "source_card_ids": result.support.source_card_ids,
            "respite_title": result.support.respite_suggestion.title,
        },
        high_risk_flag=payload.high_risk_selected,
        notes=payload.free_text,
    )
    db.add(incident)
    db.flush()
    db.commit()

    return FrictionSupportGenerateResponse(
        blocked=False,
        incident_id=incident.id,
        risk=result.signal,
        support=result.support,
        evidence_bundle=result.evidence_bundle if payload.include_debug else None,
        decision_trace_id=result.trace_id if payload.include_debug else None,
        decision_summary=result.evidence_bundle.ranking_summary if payload.include_debug else None,
    )


@router.post("/friction-support/feedback", response_model=FrictionSupportFeedbackResponse)
def submit_friction_support_feedback(
    payload: FrictionSupportFeedbackRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FrictionSupportFeedbackResponse:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    incident = db.get(IncidentLog, payload.incident_id)
    if incident is None or incident.family_id != payload.family_id:
        raise HTTPException(status_code=404, detail="Incident not found")

    score = _score_friction_feedback(
        effectiveness=payload.effectiveness,
        child_state_after=payload.child_state_after,
        caregiver_state_after=payload.caregiver_state_after,
    )
    next_adjustment = _next_adjustment(
        score=score,
        child_state_after=payload.child_state_after,
        caregiver_state_after=payload.caregiver_state_after,
    )

    review = Review(
        incident_id=payload.incident_id,
        family_id=payload.family_id,
        card_ids=payload.source_card_ids,
        outcome_score=score,
        child_state_after=payload.child_state_after,
        caregiver_state_after=payload.caregiver_state_after,
        recommendation=_recommendation_for_feedback(score, payload.caregiver_state_after),
        notes=payload.notes,
        followup_action=next_adjustment,
    )
    db.add(review)
    db.flush()

    PolicyLearningService().record_review(
        db=db,
        family_id=payload.family_id,
        outcome_score=score,
        card_ids=payload.source_card_ids,
        scenario=incident.scenario,
        response_action=" / ".join(payload.source_card_ids[:2]),
    )
    updated_weights = CoachAgent().update_preference_weights(db=db, family_id=payload.family_id)
    db.commit()

    return FrictionSupportFeedbackResponse(
        review_id=review.id,
        incident_id=payload.incident_id,
        outcome_score=score,
        updated_weights=updated_weights,
        next_adjustment=next_adjustment,
    )
