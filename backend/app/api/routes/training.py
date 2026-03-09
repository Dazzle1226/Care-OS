from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.training import TrainingAgent
from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import Family, TrainingTaskFeedback, User
from app.schemas.domain import (
    TrainingPlanGenerateRequest,
    TrainingPlanResponse,
    TrainingTaskFeedbackRequest,
    TrainingTaskFeedbackResponse,
)

router = APIRouter(prefix="/training", tags=["training"])


def _get_family_or_404(db: Session, family_id: int) -> Family:
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    return family


@router.get("/current/{family_id}", response_model=TrainingPlanResponse)
def get_current_training_plan(
    family_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TrainingPlanResponse:
    family = _get_family_or_404(db, family_id)
    try:
        return TrainingAgent().generate_plan(db=db, family=family)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generate", response_model=TrainingPlanResponse)
def generate_training_plan(
    payload: TrainingPlanGenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TrainingPlanResponse:
    family = _get_family_or_404(db, payload.family_id)
    try:
        return TrainingAgent().generate_plan(db=db, family=family, extra_context=payload.extra_context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/feedback", response_model=TrainingTaskFeedbackResponse)
def submit_training_feedback(
    payload: TrainingTaskFeedbackRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TrainingTaskFeedbackResponse:
    family = _get_family_or_404(db, payload.family_id)
    feedback = TrainingTaskFeedback(
        family_id=payload.family_id,
        date=payload.date or date_type.today(),
        task_key=payload.task_key,
        task_title=payload.task_title,
        area_key=payload.area_key,
        completion_status=payload.completion_status,
        child_response=payload.child_response,
        difficulty_rating=payload.difficulty_rating,
        effect_score=payload.effect_score,
        parent_confidence=payload.parent_confidence,
        notes=payload.notes,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    agent = TrainingAgent()
    try:
        plan = agent.generate_plan(db=db, family=family)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TrainingTaskFeedbackResponse(
        feedback_id=feedback.id,
        next_adjustment=agent.next_adjustment(
            completion_status=payload.completion_status,
            child_response=payload.child_response,
            difficulty_rating=payload.difficulty_rating,
            effect_score=payload.effect_score,
        ),
        progress_summary=plan.recent_feedback_summary,
        plan=plan,
    )
