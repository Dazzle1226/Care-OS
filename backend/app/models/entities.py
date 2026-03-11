from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(32), default="caregiver", nullable=False)
    locale: Mapped[str] = mapped_column(String(32), default="zh-CN", nullable=False)
    identifier: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    families: Mapped[list["Family"]] = relationship(back_populates="owner")


class Family(Base):
    __tablename__ = "families"

    family_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    owner: Mapped[User | None] = relationship(back_populates="families")
    child_profile: Mapped["ChildProfile | None"] = relationship(back_populates="family", uselist=False)
    support_networks: Mapped[list["SupportNetwork"]] = relationship(back_populates="family")
    checkins: Mapped[list["DailyCheckin"]] = relationship(back_populates="family")
    incidents: Mapped[list["IncidentLog"]] = relationship(back_populates="family")
    plans: Mapped[list["Plan48h"]] = relationship(back_populates="family")
    reviews: Mapped[list["Review"]] = relationship(back_populates="family")
    training_feedbacks: Mapped[list["TrainingTaskFeedback"]] = relationship(back_populates="family")
    training_skill_states: Mapped[list["TrainingSkillState"]] = relationship(back_populates="family")
    training_plan_cycles: Mapped[list["TrainingPlanCycle"]] = relationship(back_populates="family")
    daily_training_tasks: Mapped[list["DailyTrainingTask"]] = relationship(back_populates="family")
    training_adjustments: Mapped[list["TrainingAdjustmentLog"]] = relationship(back_populates="family")
    weekly_reports: Mapped[list["WeeklyReport"]] = relationship(back_populates="family")
    report_feedbacks: Mapped[list["ReportFeedback"]] = relationship(back_populates="family")


class ChildProfile(Base):
    __tablename__ = "child_profiles"

    child_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), unique=True, index=True)

    age_band: Mapped[str] = mapped_column(String(16), nullable=False)
    language_level: Mapped[str] = mapped_column(String(32), nullable=False)
    sensory_flags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    triggers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    soothing_methods: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    donts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    school_context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    high_friction_scenarios: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    family: Mapped[Family] = relationship(back_populates="child_profile")


class SupportNetwork(Base):
    __tablename__ = "support_networks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    contact_name: Mapped[str] = mapped_column(String(64), nullable=False)
    relation: Mapped[str] = mapped_column(String(64), nullable=False)
    availability_slots: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    family: Mapped[Family] = relationship(back_populates="support_networks")


class DailyCheckin(Base):
    __tablename__ = "daily_checkins"
    __table_args__ = (UniqueConstraint("family_id", "date", name="uq_daily_checkin_family_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    child_sleep_hours: Mapped[float] = mapped_column(Float, nullable=False)
    meltdown_count: Mapped[int] = mapped_column(Integer, nullable=False)
    transition_difficulty: Mapped[float] = mapped_column(Float, nullable=False)
    sensory_overload_level: Mapped[str] = mapped_column(String(16), nullable=False)
    caregiver_stress: Mapped[float] = mapped_column(Float, nullable=False)
    caregiver_sleep_hours: Mapped[float] = mapped_column(Float, nullable=False)
    support_available: Mapped[str] = mapped_column(String(32), nullable=False)
    env_changes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    family: Mapped[Family] = relationship(back_populates="checkins")


class IncidentLog(Base):
    __tablename__ = "incident_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    intensity: Mapped[str] = mapped_column(String(16), nullable=False)
    triggers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    selected_resources: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans_48h.plan_id"), nullable=True)
    high_risk_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    family: Mapped[Family] = relationship(back_populates="incidents")


class Plan48h(Base):
    __tablename__ = "plans_48h"

    plan_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    start_ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    actions_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    respite_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    messages_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    safety_flags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    citations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), default="plan-agent", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    family: Mapped[Family] = relationship(back_populates="plans")
    card_uses: Mapped[list["PlanCardUse"]] = relationship(back_populates="plan")


class StrategyCard(Base):
    __tablename__ = "strategy_cards"

    card_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    scenario_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    conditions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    steps_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    scripts_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    donts_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    escalate_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    cost_level: Mapped[str] = mapped_column(String(16), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_tag: Mapped[str] = mapped_column(String(32), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PlanCardUse(Base):
    __tablename__ = "plan_card_uses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans_48h.plan_id"), index=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("strategy_cards.card_id"), index=True)
    order_idx: Mapped[int] = mapped_column(Integer, nullable=False)

    plan: Mapped[Plan48h] = relationship(back_populates="card_uses")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident_logs.id"), index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    card_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    outcome_score: Mapped[int] = mapped_column(Integer, nullable=False)
    child_state_after: Mapped[str] = mapped_column(String(32), default="partly_settled", nullable=False)
    caregiver_state_after: Mapped[str] = mapped_column(String(32), default="same", nullable=False)
    recommendation: Mapped[str] = mapped_column(String(16), default="continue", nullable=False)
    response_action: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    followup_action: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    family: Mapped[Family] = relationship(back_populates="reviews")


class TrainingTaskFeedback(Base):
    __tablename__ = "training_task_feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    task_instance_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    task_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_title: Mapped[str] = mapped_column(String(128), nullable=False)
    area_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    completion_status: Mapped[str] = mapped_column(String(16), nullable=False)
    child_response: Mapped[str] = mapped_column(String(16), nullable=False)
    difficulty_rating: Mapped[str] = mapped_column(String(16), nullable=False)
    effect_score: Mapped[float] = mapped_column(Float, nullable=False)
    parent_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    helpfulness: Mapped[str] = mapped_column(String(16), default="neutral", nullable=False)
    obstacle_tag: Mapped[str] = mapped_column(String(32), default="none", nullable=False)
    safety_pause: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    family: Mapped[Family] = relationship(back_populates="training_feedbacks")


class TrainingSkillState(Base):
    __tablename__ = "training_skill_states"
    __table_args__ = (UniqueConstraint("family_id", "area_key", name="uq_training_skill_state_family_area"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    area_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    priority_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority_rank: Mapped[int] = mapped_column(Integer, default=99, nullable=False)
    current_stage: Mapped[str] = mapped_column(String(16), default="stabilize", nullable=False)
    current_difficulty: Mapped[str] = mapped_column(String(16), default="starter", nullable=False)
    recommended_time: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    recommended_scene: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    best_method: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    reason_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    risk_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    weekly_sessions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    effectiveness_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_assessed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_adjusted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    meta_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    family: Mapped[Family] = relationship(back_populates="training_skill_states")


class TrainingPlanCycle(Base):
    __tablename__ = "training_plan_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    cycle_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    load_level: Mapped[str] = mapped_column(String(16), default="standard", nullable=False)
    weekly_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    top_area_keys: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    family: Mapped[Family] = relationship(back_populates="training_plan_cycles")
    daily_tasks: Mapped[list["DailyTrainingTask"]] = relationship(back_populates="cycle")


class DailyTrainingTask(Base):
    __tablename__ = "daily_training_tasks"
    __table_args__ = (UniqueConstraint("cycle_id", "order_idx", name="uq_daily_training_task_cycle_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("training_plan_cycles.id"), index=True)
    task_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    order_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    area_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_status: Mapped[str] = mapped_column(String(16), default="none", nullable=False)
    feedback_submitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    task_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    family: Mapped[Family] = relationship(back_populates="daily_training_tasks")
    cycle: Mapped[TrainingPlanCycle] = relationship(back_populates="daily_tasks")


class TrainingAdjustmentLog(Base):
    __tablename__ = "training_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    area_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_instance_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    feedback_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    trigger: Mapped[str] = mapped_column(String(64), default="manual", nullable=False)
    before_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    after_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    family: Mapped[Family] = relationship(back_populates="training_adjustments")


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"
    __table_args__ = (UniqueConstraint("family_id", "week_start", name="uq_weekly_report_family_week"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    export_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    family: Mapped[Family] = relationship(back_populates="weekly_reports")


class ReportFeedback(Base):
    __tablename__ = "report_feedbacks"
    __table_args__ = (
        UniqueConstraint(
            "family_id",
            "period_type",
            "period_start",
            "target_kind",
            "target_key",
            name="uq_report_feedback_target",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target_key: Mapped[str] = mapped_column(String(128), nullable=False)
    target_label: Mapped[str] = mapped_column(String(128), nullable=False)
    feedback_value: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    family: Mapped[Family] = relationship(back_populates="report_feedbacks")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int | None] = mapped_column(ForeignKey("families.family_id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
