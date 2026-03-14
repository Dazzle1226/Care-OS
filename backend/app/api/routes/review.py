from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.coach import CoachAgent
from app.api.deps import get_current_user
from app.core.time import utc_now
from app.db.base import get_db
from app.models import IncidentLog, Review, StrategyCard, User
from app.schemas.domain import ReplayResponse, ReviewCreate, ReviewResponse
from app.services.policy_learning import PolicyLearningService
from app.services.review_learning import (
    build_followup_action,
    build_replay_response,
    normalize_review_card_ids,
)

router = APIRouter(tags=["review"])


@router.post("/review", response_model=ReviewResponse)
def create_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ReviewResponse:
    incident_id = payload.incident_id
    incident_scenario = payload.scenario or "transition"
    if incident_id is None:
        incident = IncidentLog(
            family_id=payload.family_id,
            ts=utc_now(),
            scenario=incident_scenario,
            intensity=payload.intensity,
            triggers=payload.triggers,
            selected_resources={},
            high_risk_flag=False,
            notes=payload.notes,
        )
        db.add(incident)
        db.flush()
        incident_id = incident.id
    else:
        incident = db.get(IncidentLog, incident_id)
        if incident is not None:
            incident_scenario = incident.scenario

    normalized_card_ids = normalize_review_card_ids(payload.card_ids, payload.scenario)

    review = Review(
        incident_id=incident_id,
        family_id=payload.family_id,
        card_ids=normalized_card_ids,
        outcome_score=payload.outcome_score,
        child_state_after=payload.child_state_after,
        caregiver_state_after=payload.caregiver_state_after,
        recommendation=payload.recommendation,
        response_action=payload.response_action.strip(),
        notes=payload.notes,
        followup_action=build_followup_action(
            recommendation=payload.recommendation,
            child_state_after=payload.child_state_after,
            caregiver_state_after=payload.caregiver_state_after,
            followup_action=payload.followup_action,
        ),
    )
    db.add(review)
    db.flush()

    PolicyLearningService().record_review(
        db=db,
        family_id=payload.family_id,
        outcome_score=payload.outcome_score,
        card_ids=normalized_card_ids,
        scenario=incident_scenario,
        response_action=payload.response_action,
    )
    updated_weights = CoachAgent().update_preference_weights(db=db, family_id=payload.family_id)
    db.commit()

    return ReviewResponse(review_id=review.id, incident_id=incident_id, updated_weights=updated_weights)


@router.get("/replay/{incident_id}", response_model=ReplayResponse)
def get_replay(
    incident_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ReplayResponse:
    incident = db.get(IncidentLog, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    review = db.scalar(
        select(Review).where(Review.incident_id == incident_id).order_by(Review.created_at.desc()).limit(1)
    )

    if review is None:
        raise HTTPException(status_code=404, detail="Replay not found")

    card_ids = {card_id for card_id in review.card_ids if not card_id.startswith("manual:")}
    cards = db.scalars(select(StrategyCard).where(StrategyCard.card_id.in_(sorted(card_ids)))).all()
    card_titles = {card.card_id: card.title for card in cards}
    return build_replay_response(review=review, incident=incident, card_titles=card_titles)
