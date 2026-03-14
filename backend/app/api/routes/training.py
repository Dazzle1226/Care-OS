from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import Family, TrainingPlanCycle, TrainingTaskFeedback, User
from app.schemas.domain import (
    TrainingDashboardResponse,
    TrainingDomainDetailResponse,
    TrainingPlanGenerateRequest,
    TrainingReminderRequest,
    TrainingReminderResponse,
    TrainingTaskFeedbackRequest,
    TrainingTaskFeedbackResponse,
)
from app.services.policy_learning import PolicyLearningService
from app.services.training_system import TrainingSystemService

router = APIRouter(prefix="/training", tags=["training"])


def _get_family_or_404(db: Session, family_id: int) -> Family:
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    return family


@router.get("/current/{family_id}", response_model=TrainingDashboardResponse)
def get_current_training_plan(
    family_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TrainingDashboardResponse:
    family = _get_family_or_404(db, family_id)
    try:
        dashboard = TrainingSystemService().get_dashboard(db=db, family=family)
        db.commit()
        return dashboard
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generate", response_model=TrainingDashboardResponse)
def generate_training_plan(
    payload: TrainingPlanGenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TrainingDashboardResponse:
    family = _get_family_or_404(db, payload.family_id)
    try:
        dashboard = TrainingSystemService().get_dashboard(
            db=db,
            family=family,
            extra_context=payload.extra_context,
            force_regenerate=True,
        )
        db.commit()
        return dashboard
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/domain/{family_id}/{area_key}", response_model=TrainingDomainDetailResponse)
def get_training_domain_detail(
    family_id: int,
    area_key: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TrainingDomainDetailResponse:
    family = _get_family_or_404(db, family_id)
    try:
        return TrainingSystemService().get_domain_detail(db=db, family=family, area_key=area_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/feedback", response_model=TrainingTaskFeedbackResponse)
def submit_training_feedback(
    payload: TrainingTaskFeedbackRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TrainingTaskFeedbackResponse:
    family = _get_family_or_404(db, payload.family_id)
    service = TrainingSystemService()
    try:
        task = service.get_task_or_404(db=db, family_id=payload.family_id, task_instance_id=payload.task_instance_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    difficulty_rating, effect_score, parent_confidence, derived_safety_pause = service.derive_feedback(
        completion_status=payload.completion_status,
        child_response=payload.child_response,
        helpfulness=payload.helpfulness,
        obstacle_tag=payload.obstacle_tag,
        notes=payload.notes,
    )
    feedback = TrainingTaskFeedback(
        family_id=payload.family_id,
        date=payload.date or date_type.today(),
        task_instance_id=task.id,
        task_key=str(task.task_json.get("task_key") or f"{task.area_key}_{task.id}"),
        task_title=task.title,
        area_key=task.area_key,
        completion_status=payload.completion_status,
        child_response=payload.child_response,
        difficulty_rating=difficulty_rating,
        effect_score=effect_score,
        parent_confidence=parent_confidence,
        helpfulness=payload.helpfulness,
        obstacle_tag=payload.obstacle_tag,
        safety_pause=payload.safety_pause or derived_safety_pause,
        notes=payload.notes,
    )
    db.add(feedback)
    db.flush()
    outcome_score = 2 if effect_score >= 7 else 1 if effect_score >= 5 else 0 if effect_score >= 3 else -1 if effect_score >= 1 else -2
    PolicyLearningService().record_training_feedback(
        db=db,
        family_id=payload.family_id,
        outcome_score=outcome_score,
        area_key=task.area_key,
        task_title=task.title,
        task_date=(payload.date or date_type.today()).isoformat(),
    )
    cycle = db.get(TrainingPlanCycle, task.cycle_id)
    coordination = cycle.snapshot_json.get("coordination", {}) if cycle and isinstance(cycle.snapshot_json, dict) else {}
    emotion = coordination.get("emotion", {}) if isinstance(coordination, dict) else {}
    PolicyLearningService().record_adaptive_feedback(
        db=db,
        family_id=payload.family_id,
        outcome_score=outcome_score,
        emotion_pattern=f"{emotion.get('child_emotion', 'unknown')}|{emotion.get('caregiver_emotion', 'unknown')}",
        overload_trigger=str(payload.obstacle_tag or coordination.get("readiness_status") or "training_feedback"),
        handoff_pattern="",
        adjustment_key=f"training:{coordination.get('readiness_status', 'ready')}:{task.area_key}",
    )
    adjustment_summary, safety_alert = service.apply_feedback(db=db, family=family, task=task, feedback=feedback)
    dashboard = service.get_dashboard(db=db, family=family)
    db.commit()
    db.refresh(feedback)

    return TrainingTaskFeedbackResponse(
        feedback_id=feedback.id,
        adjustment_summary=adjustment_summary,
        safety_alert=safety_alert,
        dashboard=dashboard,
    )


@router.post("/reminder", response_model=TrainingReminderResponse)
def schedule_training_reminder(
    payload: TrainingReminderRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TrainingReminderResponse:
    family = _get_family_or_404(db, payload.family_id)
    service = TrainingSystemService()
    try:
        task = service.get_task_or_404(db=db, family_id=payload.family_id, task_instance_id=payload.task_instance_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    service.schedule_reminder(task=task, remind_at=payload.remind_at)
    dashboard = service.get_dashboard(db=db, family=family)
    db.commit()
    return TrainingReminderResponse(
        task_instance_id=task.id,
        reminder_status=task.reminder_status,
        remind_at=task.reminder_at,
        dashboard=dashboard,
    )
