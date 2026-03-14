from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.time import utc_now
from app.db.base import Base
from app.db.vector import FlexibleVector


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(32), default="caregiver", nullable=False)
    locale: Mapped[str] = mapped_column(String(32), default="zh-CN", nullable=False)
    identifier: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    families: Mapped[list["Family"]] = relationship(back_populates="owner")


class Family(Base):
    __tablename__ = "families"

    family_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

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
    decision_traces: Mapped[list["DecisionTrace"]] = relationship(back_populates="family")
    policy_weights: Mapped[list["FamilyPolicyWeight"]] = relationship(back_populates="family")
    multimodal_ingestions: Mapped[list["MultimodalIngestion"]] = relationship(back_populates="family")
    adaptive_sessions: Mapped[list["AdaptiveSession"]] = relationship(back_populates="family")
    benchmark_runs: Mapped[list["BenchmarkRun"]] = relationship(back_populates="family")
    knowledge_documents: Mapped[list["KnowledgeDocument"]] = relationship(back_populates="family")
    knowledge_chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="family")
    retrieval_runs: Mapped[list["RetrievalRun"]] = relationship(back_populates="family")


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
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    family: Mapped[Family] = relationship(back_populates="checkins")


class IncidentLog(Base):
    __tablename__ = "incident_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
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
    start_ts: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
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
    embedding: Mapped[list[float]] = mapped_column(FlexibleVector(256), default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    evidence_units: Mapped[list["EvidenceUnit"]] = relationship(back_populates="card")


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

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
    last_assessed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    family: Mapped[Family] = relationship(back_populates="training_adjustments")


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"
    __table_args__ = (UniqueConstraint("family_id", "week_start", name="uq_weekly_report_family_week"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    export_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    family: Mapped[Family] = relationship(back_populates="report_feedbacks")


class DecisionTrace(Base):
    __tablename__ = "decision_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int | None] = mapped_column(ForeignKey("families.family_id"), nullable=True, index=True)
    chain: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    final_status: Mapped[str] = mapped_column(String(16), nullable=False)
    graph_version: Mapped[str] = mapped_column(String(16), default="v1", nullable=False)
    stage_order_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    stage_runs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    entry_signal_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    request_context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    signal_result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    retrieval_bundle_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    candidate_output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    safety_review_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evidence_review_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reranker_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    corpus_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieval_stage_timings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_tree_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    execution_state_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    revision_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_trace_id: Mapped[int | None] = mapped_column(ForeignKey("decision_traces.id"), nullable=True, index=True)
    replan_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    family: Mapped[Family | None] = relationship(back_populates="decision_traces")


class AdaptiveSession(Base):
    __tablename__ = "adaptive_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incident_logs.id"), nullable=True, index=True)
    chain: Mapped[str] = mapped_column(String(32), default="friction_support", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False, index=True)
    current_state_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_state_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    active_plan_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    next_check_in_hint: Mapped[str] = mapped_column(Text, default="3 分钟后确认是否更稳定。", nullable=False)
    last_trace_id: Mapped[int | None] = mapped_column(ForeignKey("decision_traces.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    family: Mapped[Family] = relationship(back_populates="adaptive_sessions")
    events: Mapped[list["SessionEvent"]] = relationship(back_populates="session")


class SessionEvent(Base):
    __tablename__ = "session_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("adaptive_sessions.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    event_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ingestion_id: Mapped[int | None] = mapped_column(ForeignKey("multimodal_ingestions.id"), nullable=True, index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    replanned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    session: Mapped[AdaptiveSession] = relationship(back_populates="events")


class FamilyPolicyWeight(Base):
    __tablename__ = "family_policy_weights"
    __table_args__ = (
        UniqueConstraint("family_id", "target_kind", "target_key", name="uq_family_policy_weight_target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    target_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recent_outcome_avg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_feedback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    family: Mapped[Family] = relationship(back_populates="policy_weights")


class GlobalPolicyPrior(Base):
    __tablename__ = "global_policy_priors"
    __table_args__ = (
        UniqueConstraint("target_kind", "target_key", name="uq_global_policy_prior_target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    target_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class SegmentPolicyPrior(Base):
    __tablename__ = "segment_policy_priors"
    __table_args__ = (
        UniqueConstraint("segment_key", "target_kind", "target_key", name="uq_segment_policy_prior_target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    target_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class MultimodalIngestion(Base):
    __tablename__ = "multimodal_ingestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.family_id"), index=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    content_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    raw_excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    normalized_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    manual_review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    meta_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    family: Mapped[Family] = relationship(back_populates="multimodal_ingestions")
    signals: Mapped[list["ContextSignalFrame"]] = relationship(back_populates="ingestion")


class ContextSignalFrame(Base):
    __tablename__ = "context_signal_frames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingestion_id: Mapped[int] = mapped_column(ForeignKey("multimodal_ingestions.id"), index=True)
    signal_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signal_label: Mapped[str] = mapped_column(String(128), nullable=False)
    signal_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    ingestion: Mapped[MultimodalIngestion] = relationship(back_populates="signals")


class EvidenceUnit(Base):
    __tablename__ = "evidence_units"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("strategy_cards.card_id"), index=True)
    unit_kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    unit_key: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    dimensions_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(FlexibleVector(256), default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    card: Mapped[StrategyCard] = relationship(back_populates="evidence_units")


class EvidenceSelectionLog(Base):
    __tablename__ = "evidence_selection_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[int | None] = mapped_column(ForeignKey("decision_traces.id"), nullable=True, index=True)
    family_id: Mapped[int | None] = mapped_column(ForeignKey("families.family_id"), nullable=True, index=True)
    evidence_unit_id: Mapped[str] = mapped_column(ForeignKey("evidence_units.id"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int | None] = mapped_column(ForeignKey("families.family_id"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scope: Mapped[str] = mapped_column(String(32), default="global", nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), default="v1", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    family: Mapped[Family | None] = relationship(back_populates="knowledge_documents")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="document")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    family_id: Mapped[int | None] = mapped_column(ForeignKey("families.family_id"), nullable=True, index=True)
    card_id: Mapped[str | None] = mapped_column(ForeignKey("strategy_cards.card_id"), nullable=True, index=True)
    evidence_unit_id: Mapped[str | None] = mapped_column(ForeignKey("evidence_units.id"), nullable=True, index=True)
    chunk_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    family_scope: Mapped[str] = mapped_column(String(32), default="shared", nullable=False, index=True)
    segment_scope: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    knowledge_version: Mapped[str] = mapped_column(String(64), default="v1", nullable=False, index=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")
    family: Mapped[Family | None] = relationship(back_populates="knowledge_chunks")
    embeddings: Mapped[list["ChunkEmbedding"]] = relationship(back_populates="chunk")


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("knowledge_chunks.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_json: Mapped[list[float]] = mapped_column(FlexibleVector(256), default=list, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    rebuild_version: Mapped[str] = mapped_column(String(64), default="v1", nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    chunk: Mapped[KnowledgeChunk] = relationship(back_populates="embeddings")


class RetrievalRun(Base):
    __tablename__ = "retrieval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int | None] = mapped_column(ForeignKey("families.family_id"), nullable=True, index=True)
    trace_id: Mapped[int | None] = mapped_column(ForeignKey("decision_traces.id"), nullable=True, index=True)
    intent: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    query_plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    selected_sources_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    selected_chunk_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    hard_filtered_reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    knowledge_versions_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    feature_attribution_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    personalization_applied_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    retrieval_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reranker_model: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    corpus_version: Mapped[str] = mapped_column(String(64), default="v1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    family: Mapped[Family | None] = relationship(back_populates="retrieval_runs")
    candidates: Mapped[list["RetrievalCandidate"]] = relationship(back_populates="run")


class RetrievalCandidate(Base):
    __tablename__ = "retrieval_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("retrieval_runs.id"), index=True)
    card_id: Mapped[str | None] = mapped_column(ForeignKey("strategy_cards.card_id"), nullable=True, index=True)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_chunks.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="strategy_card", nullable=False, index=True)
    total_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    dense_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sparse_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    profile_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    history_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    policy_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    safety_penalty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    filter_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    feature_attribution_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    run: Mapped[RetrievalRun] = relationship(back_populates="candidates")


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int | None] = mapped_column(ForeignKey("families.family_id"), nullable=True, index=True)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    family: Mapped[Family | None] = relationship(back_populates="benchmark_runs")
    metrics: Mapped[list["BenchmarkMetric"]] = relationship(back_populates="run")


class BenchmarkMetric(Base):
    __tablename__ = "benchmark_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("benchmark_runs.id"), index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    run: Mapped[BenchmarkRun] = relationship(back_populates="metrics")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int | None] = mapped_column(ForeignKey("families.family_id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
