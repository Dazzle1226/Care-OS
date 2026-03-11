from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyTrainingTask, Family
from app.schemas.domain import TrainingDashboardResponse, TrainingDomainDetailResponse
from app.services.training_adjustments import apply_feedback_adjustment, derive_feedback_metrics
from app.services.training_analytics import build_training_dashboard, build_training_domain_detail
from app.services.training_assessment import assess_training_needs, load_assessment_inputs
from app.services.training_planner import persist_training_cycle


class TrainingSystemService:
    def get_dashboard(
        self,
        db: Session,
        family: Family,
        extra_context: str = "",
        force_regenerate: bool = False,
    ) -> TrainingDashboardResponse:
        profile = family.child_profile
        if profile is None:
            raise ValueError("Family profile not found")

        checkins, incidents, reviews, feedbacks = load_assessment_inputs(db=db, family_id=family.family_id)
        assessment = assess_training_needs(
            family=family,
            profile=profile,
            checkins=checkins,
            incidents=incidents,
            reviews=reviews,
            feedbacks=feedbacks,
            extra_context=extra_context,
        )
        cycle = persist_training_cycle(
            db=db,
            family=family,
            assessment=assessment,
            extra_context=extra_context,
            force_new=force_regenerate,
        )
        db.flush()
        return build_training_dashboard(db=db, family=family, cycle=cycle)

    def get_domain_detail(self, db: Session, family: Family, area_key: str) -> TrainingDomainDetailResponse:
        return build_training_domain_detail(db=db, family=family, area_key=area_key)

    def get_task_or_404(self, db: Session, family_id: int, task_instance_id: int) -> DailyTrainingTask:
        task = db.scalar(
            select(DailyTrainingTask).where(
                DailyTrainingTask.id == task_instance_id,
                DailyTrainingTask.family_id == family_id,
            )
        )
        if task is None:
            raise ValueError("Training task not found")
        return task

    def schedule_reminder(self, task: DailyTrainingTask, remind_at: datetime | None = None) -> None:
        task.reminder_at = remind_at or (datetime.utcnow() + timedelta(minutes=90))
        task.reminder_status = "scheduled"

    def clear_reminder(self, task: DailyTrainingTask) -> None:
        task.reminder_at = None
        task.reminder_status = "none"

    def derive_feedback(self, completion_status: str, child_response: str, helpfulness: str, obstacle_tag: str, notes: str):
        return derive_feedback_metrics(
            completion_status=completion_status,
            child_response=child_response,
            helpfulness=helpfulness,
            obstacle_tag=obstacle_tag,
            notes=notes,
        )

    def apply_feedback(self, db: Session, family: Family, task: DailyTrainingTask, feedback):
        return apply_feedback_adjustment(db=db, family=family, task=task, feedback=feedback)
