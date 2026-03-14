from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.coach import CoachAgent
from app.agents.respite import RespiteAgent
from app.agents.safety import SafetyAgent
from app.agents.signal import SignalAgent
from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import Family, IncidentLog, Review, User
from app.schemas.domain import (
    MicroRespiteFeedbackRequest,
    MicroRespiteFeedbackResponse,
    MicroRespiteGenerateRequest,
    MicroRespiteGenerateResponse,
)
from app.services.policy_learning import PolicyLearningService

router = APIRouter(prefix="/respite", tags=["respite"])


def _score_feedback(effectiveness: str, matched_expectation: bool) -> int:
    base = {
        "helpful": 2,
        "somewhat": 1,
        "not_helpful": -1,
    }[effectiveness]
    if not matched_expectation:
        base -= 1 if base >= 0 else 1
    return max(-2, min(2, base))


def _next_hint(score: int) -> str:
    if score >= 2:
        return "下次会更优先推荐这类微喘息，并优先保留当前时长。"
    if score >= 0:
        return "下次会保留这类建议，但会优先尝试更短时长或更简单版本。"
    return "下次会降低这类建议权重，优先切换到更低刺激或更可交接的方案。"


def _child_state_after(effectiveness: str) -> str:
    return {
        "helpful": "settled",
        "somewhat": "partly_settled",
        "not_helpful": "still_escalating",
    }[effectiveness]


def _caregiver_state_after(effectiveness: str, matched_expectation: bool) -> str:
    if effectiveness == "helpful":
        return "calmer"
    if effectiveness == "somewhat" or matched_expectation:
        return "same"
    return "more_overloaded"


def _recommendation(score: int) -> str:
    if score >= 1:
        return "continue"
    if score == 0:
        return "pause"
    return "replace"


@router.post("/generate", response_model=MicroRespiteGenerateResponse)
def generate_micro_respite(
    payload: MicroRespiteGenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MicroRespiteGenerateResponse:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    signal = SignalAgent().evaluate(db=db, family_id=payload.family_id)
    plan = RespiteAgent().generate_plan(db=db, family=family, signal=signal, payload=payload)

    profile_donts = family.child_profile.donts if family.child_profile else []
    safety = SafetyAgent().validate_respite_plan(
        plan=plan,
        profile_donts=profile_donts,
        explicit_high_risk=payload.high_risk_selected,
        free_text=payload.notes,
        support_available=payload.support_available,
    )
    if safety.blocked:
        return MicroRespiteGenerateResponse(blocked=True, risk=signal, safety_block=safety.block)

    return MicroRespiteGenerateResponse(blocked=False, risk=signal, plan=plan)


@router.post("/feedback", response_model=MicroRespiteFeedbackResponse)
def submit_micro_respite_feedback(
    payload: MicroRespiteFeedbackRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MicroRespiteFeedbackResponse:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    score = _score_feedback(payload.effectiveness, payload.matched_expectation)
    next_hint = _next_hint(score)

    incident = IncidentLog(
        family_id=payload.family_id,
        ts=datetime.now(UTC).replace(tzinfo=None),
        scenario="respite",
        intensity="medium",
        triggers=[],
        selected_resources={"option_id": payload.option_id},
        high_risk_flag=False,
        notes=payload.notes,
    )
    db.add(incident)
    db.flush()

    review = Review(
        incident_id=incident.id,
        family_id=payload.family_id,
        card_ids=payload.source_card_ids,
        outcome_score=score,
        child_state_after=_child_state_after(payload.effectiveness),
        caregiver_state_after=_caregiver_state_after(payload.effectiveness, payload.matched_expectation),
        recommendation=_recommendation(score),
        notes=payload.notes,
        followup_action=next_hint,
    )
    db.add(review)
    db.flush()

    PolicyLearningService().record_review(
        db=db,
        family_id=payload.family_id,
        outcome_score=score,
        card_ids=payload.source_card_ids,
        scenario="respite",
        response_action=payload.option_id,
    )
    updated_weights = CoachAgent().update_preference_weights(db=db, family_id=payload.family_id)
    db.commit()

    return MicroRespiteFeedbackResponse(
        review_id=review.id,
        incident_id=incident.id,
        outcome_score=score,
        updated_weights=updated_weights,
        next_hint=next_hint,
    )
