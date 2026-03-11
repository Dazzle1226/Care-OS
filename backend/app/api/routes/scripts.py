from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.coach import CoachAgent
from app.agents.friction import FrictionAgent
from app.agents.plan import PlanAgent
from app.agents.safety import SafetyAgent
from app.agents.signal import SignalAgent
from app.api.deps import get_current_user
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

    script = PlanAgent().generate_script(
        db=db,
        family=family,
        scenario=payload.scenario,
        intensity=payload.intensity,
        free_text=payload.free_text,
    )

    profile_donts = family.child_profile.donts if family.child_profile else []
    safety = SafetyAgent().validate_script(
        script=script,
        profile_donts=profile_donts,
        explicit_high_risk=payload.high_risk_selected,
        free_text=payload.free_text,
    )

    db.add(
        IncidentLog(
            family_id=payload.family_id,
            ts=datetime.utcnow(),
            scenario=payload.scenario,
            intensity=payload.intensity,
            triggers=[],
            selected_resources=payload.resources,
            high_risk_flag=payload.high_risk_selected,
            notes=payload.free_text,
        )
    )
    db.commit()

    if safety.blocked:
        return ScriptGenerateResponse(blocked=True, safety_block=safety.block)

    return ScriptGenerateResponse(blocked=False, script=script)


@router.post("/friction-support", response_model=FrictionSupportGenerateResponse)
def generate_friction_support(
    payload: FrictionSupportGenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FrictionSupportGenerateResponse:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    signal = SignalAgent().evaluate(db=db, family_id=payload.family_id)
    support = FrictionAgent().generate_support(db=db, family=family, signal=signal, payload=payload)

    profile_donts = family.child_profile.donts if family.child_profile else []
    safety = SafetyAgent().validate_friction_support(
        support=support,
        profile_donts=profile_donts,
        explicit_high_risk=payload.high_risk_selected,
        free_text=payload.free_text,
    )
    if safety.blocked:
        return FrictionSupportGenerateResponse(blocked=True, risk=signal, safety_block=safety.block)

    incident = IncidentLog(
        family_id=payload.family_id,
        ts=datetime.utcnow(),
        scenario=_friction_incident_scenario(payload),
        intensity=_friction_intensity(payload),
        triggers=[payload.child_state, *payload.env_changes[:2]],
        selected_resources={
            "base_scenario": payload.scenario,
            "source_card_ids": support.source_card_ids,
            "respite_title": support.respite_suggestion.title,
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
        risk=signal,
        support=support,
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

    updated_weights = CoachAgent().update_preference_weights(db=db, family_id=payload.family_id)
    db.commit()

    return FrictionSupportFeedbackResponse(
        review_id=review.id,
        incident_id=payload.incident_id,
        outcome_score=score,
        updated_weights=updated_weights,
        next_adjustment=next_adjustment,
    )
