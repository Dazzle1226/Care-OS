from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.coach import CoachAgent
from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import IncidentLog, Review, User
from app.schemas.domain import ReplayResponse, ReviewCreate, ReviewResponse

router = APIRouter(tags=["review"])


@router.post("/review", response_model=ReviewResponse)
def create_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ReviewResponse:
    incident_id = payload.incident_id
    if incident_id is None:
        incident = IncidentLog(
            family_id=payload.family_id,
            ts=datetime.utcnow(),
            scenario=payload.scenario or "transition",
            intensity=payload.intensity,
            triggers=payload.triggers,
            selected_resources={},
            high_risk_flag=False,
            notes=payload.notes,
        )
        db.add(incident)
        db.flush()
        incident_id = incident.id

    review = Review(
        incident_id=incident_id,
        family_id=payload.family_id,
        card_ids=payload.card_ids,
        outcome_score=payload.outcome_score,
        notes=payload.notes,
        followup_action=payload.followup_action,
    )
    db.add(review)
    db.flush()

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

    timeline = [
        f"触发器: {', '.join(incident.triggers) if incident.triggers else '未记录'}",
        f"策略卡: {', '.join(review.card_ids) if review else '未复盘'}",
        f"效果: {review.outcome_score if review else 'N/A'}",
        f"下次改进: {review.followup_action if review and review.followup_action else '保持低刺激并缩短指令'}",
    ]

    return ReplayResponse(
        incident_id=incident_id,
        timeline=timeline,
        next_improvement=timeline[-1].split(": ", 1)[1],
    )
