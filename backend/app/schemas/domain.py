from __future__ import annotations

from datetime import date as date_type
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


TrainingAreaKey = Literal[
    "emotion_regulation",
    "communication",
    "social_interaction",
    "sensory_regulation",
    "transition_flexibility",
    "daily_living",
]
TrainingCompletionStatus = Literal["done", "partial", "missed"]
TrainingChildResponse = Literal["engaged", "accepted", "resistant", "overloaded"]
TrainingDifficultyRating = Literal["too_easy", "just_right", "too_hard"]


class LoginRequest(StrictModel):
    identifier: str = Field(min_length=2, max_length=128)
    role: Literal["caregiver", "teacher", "supporter"] = "caregiver"
    locale: str = "zh-CN"


class LoginResponse(StrictModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user_id: int


class FamilyCreate(StrictModel):
    name: str = Field(min_length=1, max_length=128)
    timezone: str = "Asia/Shanghai"


class FamilyRead(StrictModel):
    family_id: int
    name: str
    timezone: str
    owner_user_id: int | None


class OnboardingSetupRequest(StrictModel):
    use_sample: bool = False
    family_name: str | None = Field(default=None, max_length=128)
    timezone: str = "Asia/Shanghai"
    child_name: str = Field(default="", max_length=64)
    child_age: int | None = Field(default=None, ge=0, le=12)
    child_gender: Literal["male", "female", "other"] | None = None
    primary_caregiver: Literal["parents", "grandparents", "relative", "other"] | None = None
    diagnosis_status: Literal["asd", "none", "under_assessment", "other"] | None = None
    diagnosis_notes: str = Field(default="", max_length=200)
    communication_level: Literal["none", "single_word", "short_sentence", "fluent"] | None = None
    coexisting_conditions: list[str] = Field(default_factory=list, max_length=8)
    family_members: list[str] = Field(default_factory=list, max_length=8)
    interests: list[str] = Field(default_factory=list, max_length=8)
    likes: list[str] = Field(default_factory=list, max_length=8)
    dislikes: list[str] = Field(default_factory=list, max_length=8)
    triggers: list[str] = Field(default_factory=list, max_length=8)
    sensory_flags: list[str] = Field(default_factory=list, max_length=8)
    soothing_methods: list[str] = Field(default_factory=list, max_length=8)
    taboo_behaviors: str = Field(default="", max_length=300)
    sleep_challenges: list[str] = Field(default_factory=list, max_length=8)
    food_preferences: list[str] = Field(default_factory=list, max_length=8)
    allergies: list[str] = Field(default_factory=list, max_length=8)
    medical_needs: list[str] = Field(default_factory=list, max_length=8)
    medications: list[str] = Field(default_factory=list, max_length=8)
    health_conditions: list[str] = Field(default_factory=list, max_length=8)
    behavior_patterns: list[str] = Field(default_factory=list, max_length=8)
    behavior_risks: list[str] = Field(default_factory=list, max_length=8)
    emotion_patterns: list[str] = Field(default_factory=list, max_length=8)
    learning_needs: list[str] = Field(default_factory=list, max_length=8)
    school_type: Literal["mainstream", "special", "home", "other"] | None = None
    social_training: list[str] = Field(default_factory=list, max_length=8)
    school_notes: str = Field(default="", max_length=300)
    high_friction_scenarios: list[str] = Field(default_factory=list, max_length=4)
    parent_schedule: list[str] = Field(default_factory=list, max_length=8)
    parent_stressors: list[str] = Field(default_factory=list, max_length=8)
    parent_support_actions: list[str] = Field(default_factory=list, max_length=8)
    parent_emotional_supports: list[str] = Field(default_factory=list, max_length=8)
    available_supporters: list[str] = Field(default_factory=list, max_length=8)


class ChildProfileInput(StrictModel):
    family_id: int
    family_name: str | None = Field(default=None, max_length=128)
    timezone: str = "Asia/Shanghai"
    child_name: str = Field(default="", max_length=64)
    child_age: int | None = Field(default=None, ge=0, le=12)
    child_gender: Literal["male", "female", "other"] | None = None
    primary_caregiver: Literal["parents", "grandparents", "relative", "other"] | None = None
    diagnosis_status: Literal["asd", "none", "under_assessment", "other"] | None = None
    diagnosis_notes: str = Field(default="", max_length=200)
    communication_level: Literal["none", "single_word", "short_sentence", "fluent"] = "short_sentence"
    coexisting_conditions: list[str] = Field(default_factory=list, max_length=8)
    family_members: list[str] = Field(default_factory=list, max_length=8)
    interests: list[str] = Field(default_factory=list, max_length=8)
    likes: list[str] = Field(default_factory=list, max_length=8)
    dislikes: list[str] = Field(default_factory=list, max_length=8)
    triggers: list[str] = Field(default_factory=list, max_length=8)
    sensory_flags: list[str] = Field(default_factory=list, max_length=8)
    soothing_methods: list[str] = Field(default_factory=list, max_length=8)
    taboo_behaviors: str = Field(default="", max_length=300)
    sleep_challenges: list[str] = Field(default_factory=list, max_length=8)
    food_preferences: list[str] = Field(default_factory=list, max_length=8)
    allergies: list[str] = Field(default_factory=list, max_length=8)
    medical_needs: list[str] = Field(default_factory=list, max_length=8)
    medications: list[str] = Field(default_factory=list, max_length=8)
    health_conditions: list[str] = Field(default_factory=list, max_length=8)
    behavior_patterns: list[str] = Field(default_factory=list, max_length=8)
    behavior_risks: list[str] = Field(default_factory=list, max_length=8)
    emotion_patterns: list[str] = Field(default_factory=list, max_length=8)
    learning_needs: list[str] = Field(default_factory=list, max_length=8)
    school_type: Literal["mainstream", "special", "home", "other"] | None = None
    social_training: list[str] = Field(default_factory=list, max_length=8)
    school_notes: str = Field(default="", max_length=300)
    high_friction_scenarios: list[str] = Field(default_factory=list, max_length=4)
    parent_schedule: list[str] = Field(default_factory=list, max_length=8)
    parent_stressors: list[str] = Field(default_factory=list, max_length=8)
    parent_support_actions: list[str] = Field(default_factory=list, max_length=8)
    parent_emotional_supports: list[str] = Field(default_factory=list, max_length=8)
    available_supporters: list[str] = Field(default_factory=list, max_length=8)


class ChildProfileRead(StrictModel):
    child_id: int
    family_id: int
    age_band: str
    language_level: str
    sensory_flags: list[str]
    triggers: list[str]
    soothing_methods: list[str]
    donts: list[str]
    school_context: dict[str, Any]
    high_friction_scenarios: list[str]


class OnboardingSnapshot(StrictModel):
    child_overview: list[str] = Field(default_factory=list)
    preference_summary: list[str] = Field(default_factory=list)
    health_summary: list[str] = Field(default_factory=list)
    behavior_summary: list[str] = Field(default_factory=list)
    learning_summary: list[str] = Field(default_factory=list)
    social_summary: list[str] = Field(default_factory=list)
    trigger_summary: list[str] = Field(default_factory=list)
    sensory_summary: list[str] = Field(default_factory=list)
    soothing_summary: list[str] = Field(default_factory=list)
    caregiver_pressure: list[str] = Field(default_factory=list)
    supporter_summary: list[str] = Field(default_factory=list)
    parent_support_summary: list[str] = Field(default_factory=list)
    resource_summary: list[str] = Field(default_factory=list)
    recommended_focus: str


class OnboardingSupportCard(StrictModel):
    card_id: str
    icon: Literal["child", "parent", "team"]
    title: str
    summary: str
    bullets: list[str] = Field(min_length=2, max_length=4)


class OnboardingSetupResponse(StrictModel):
    family: FamilyRead
    profile: ChildProfileRead
    snapshot: OnboardingSnapshot
    support_cards: list[OnboardingSupportCard] = Field(min_length=3, max_length=3)


class CheckinCreate(StrictModel):
    family_id: int
    date: date_type | None = None
    child_sleep_hours: float = Field(ge=0, le=12)
    child_sleep_quality: float = Field(ge=0, le=10)
    sleep_issues: list[str] = Field(default_factory=list, max_length=8)
    meltdown_count: int = Field(ge=0, le=3)
    child_mood_state: Literal["stable", "sensitive", "anxious", "low_energy", "irritable"]
    physical_discomforts: list[str] = Field(default_factory=list, max_length=8)
    aggressive_behaviors: list[str] = Field(default_factory=list, max_length=8)
    negative_emotions: list[str] = Field(default_factory=list, max_length=8)
    transition_difficulty: float = Field(ge=0, le=10)
    sensory_overload_level: Literal["none", "light", "medium", "heavy"]
    caregiver_stress: float = Field(ge=0, le=10)
    caregiver_sleep_quality: float = Field(ge=0, le=10)
    support_available: Literal["none", "one", "two_plus"]
    today_activities: list[str] = Field(default_factory=list, max_length=8)
    today_learning_tasks: list[str] = Field(default_factory=list, max_length=8)
    env_changes: list[str] = Field(default_factory=list)


class SignalOutput(StrictModel):
    risk_level: Literal["green", "yellow", "red"]
    reasons: list[str] = Field(default_factory=list, max_length=2)
    trigger_48h: bool
    confidence: float = Field(ge=0, le=1)


class CheckinResponse(StrictModel):
    checkin_id: int
    checkin: "CheckinRead"
    risk: SignalOutput
    today_one_thing: str
    action_plan: "DailyActionPlan"


class CheckinRead(StrictModel):
    checkin_id: int
    date: date_type
    child_sleep_hours: float
    child_sleep_quality: float
    sleep_issues: list[str] = Field(default_factory=list)
    meltdown_count: int
    child_mood_state: Literal["stable", "sensitive", "anxious", "low_energy", "irritable"]
    physical_discomforts: list[str] = Field(default_factory=list)
    aggressive_behaviors: list[str] = Field(default_factory=list)
    negative_emotions: list[str] = Field(default_factory=list)
    transition_difficulty: float
    sensory_overload_level: Literal["none", "light", "medium", "heavy"]
    caregiver_stress: float
    caregiver_sleep_quality: float
    support_available: Literal["none", "one", "two_plus"]
    today_activities: list[str] = Field(default_factory=list)
    today_learning_tasks: list[str] = Field(default_factory=list)


class DailyActionPlan(StrictModel):
    headline: str
    summary: str
    three_step_action: list[str] = Field(min_length=3, max_length=3)
    parent_phrase: str = Field(min_length=1)
    meltdown_fallback: list[str] = Field(min_length=3, max_length=3)
    respite_suggestion: str = Field(min_length=1)
    plan_overview: list[str] = Field(min_length=1, max_length=3)


class CheckinTodayResponse(StrictModel):
    family_id: int
    date: date_type
    needs_checkin: bool
    checkin: CheckinRead | None = None
    risk: SignalOutput | None = None
    today_one_thing: str | None = None
    action_plan: DailyActionPlan | None = None


class PlanMessage(StrictModel):
    target: Literal["teacher", "family", "supporter"]
    text: str = Field(min_length=1)


class RespiteSlot(StrictModel):
    duration_minutes: Literal[15, 30, 60]
    resource: str
    handoff_card: dict[str, Any]


class PlanActionItem(StrictModel):
    card_id: str
    step: str
    script: str
    donts: list[str] = Field(min_length=2)
    escalate_when: list[str] = Field(min_length=1)


class Plan48hResponse(StrictModel):
    today_cut_list: list[str] = Field(min_length=1, max_length=3)
    priority_scenarios: list[str] = Field(min_length=1, max_length=2)
    respite_slots: list[RespiteSlot] = Field(min_length=1)
    messages: list[PlanMessage] = Field(min_length=1)
    exit_card_3steps: list[str] = Field(min_length=3, max_length=3)
    tomorrow_plan: list[str] = Field(min_length=1)
    action_steps: list[PlanActionItem] = Field(min_length=1)
    citations: list[str] = Field(min_length=1)
    safety_flags: list[str] = Field(default_factory=list)


class Plan48hGenerateRequest(StrictModel):
    family_id: int
    context: Literal["checkin", "incident", "manual"]
    scenario: str | None = None
    manual_trigger: bool = False
    high_risk_selected: bool = False
    free_text: str = ""


class Plan48hGenerateResponse(StrictModel):
    blocked: bool = False
    plan_id: int | None = None
    risk: SignalOutput | None = None
    plan: Plan48hResponse | None = None
    safety_block: "SafetyBlockResponse | None" = None


class ScriptGenerateRequest(StrictModel):
    family_id: int
    scenario: Literal["transition", "bedtime", "homework", "outing"]
    intensity: Literal["light", "medium", "heavy"]
    resources: dict[str, Any] = Field(default_factory=dict)
    high_risk_selected: bool = False
    free_text: str = ""


class ScriptResponse(StrictModel):
    steps: list[str] = Field(min_length=3, max_length=3)
    script_line: str = Field(min_length=1)
    donts: list[str] = Field(min_length=2)
    exit_plan: list[str] = Field(min_length=1)
    citations: list[str] = Field(min_length=1)


class ScriptGenerateResponse(StrictModel):
    blocked: bool = False
    script: ScriptResponse | None = None
    safety_block: "SafetyBlockResponse | None" = None


class FrictionSupportStep(StrictModel):
    title: str = Field(min_length=1, max_length=32)
    action: str = Field(min_length=1)
    parent_script: str = Field(min_length=1)
    why_it_fits: str = Field(min_length=1)


class FrictionRespiteSuggestion(StrictModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    duration_minutes: int = Field(ge=10, le=30)
    support_plan: str = Field(min_length=1)


class FrictionSupportPlan(StrictModel):
    headline: str = Field(min_length=1)
    situation_summary: str = Field(min_length=1)
    child_signals: list[str] = Field(min_length=2, max_length=3)
    caregiver_signals: list[str] = Field(min_length=2, max_length=3)
    action_plan: list[FrictionSupportStep] = Field(min_length=3, max_length=3)
    voice_guidance: list[str] = Field(min_length=3, max_length=3)
    exit_plan: list[str] = Field(min_length=3, max_length=3)
    respite_suggestion: FrictionRespiteSuggestion
    personalized_strategies: list[str] = Field(min_length=2, max_length=4)
    school_message: str = Field(min_length=1)
    feedback_prompt: str = Field(min_length=1)
    citations: list[str] = Field(min_length=1)
    source_card_ids: list[str] = Field(min_length=1, max_length=3)


class FrictionSupportGenerateRequest(StrictModel):
    family_id: int
    scenario: Literal["transition", "bedtime", "homework", "outing", "meltdown"]
    child_state: Literal["emotional_wave", "sensory_overload", "conflict", "meltdown", "transition_block"]
    sensory_overload_level: Literal["none", "light", "medium", "heavy"]
    transition_difficulty: float = Field(ge=0, le=10)
    meltdown_count: int = Field(ge=0, le=3)
    caregiver_stress: float = Field(ge=0, le=10)
    caregiver_fatigue: float = Field(ge=0, le=10)
    caregiver_sleep_quality: float = Field(ge=0, le=10)
    support_available: Literal["none", "one", "two_plus"]
    confidence_to_follow_plan: float = Field(ge=0, le=10)
    env_changes: list[str] = Field(default_factory=list)
    free_text: str = Field(default="", max_length=500)
    high_risk_selected: bool = False


class FrictionSupportGenerateResponse(StrictModel):
    blocked: bool = False
    incident_id: int | None = None
    risk: SignalOutput | None = None
    support: FrictionSupportPlan | None = None
    safety_block: "SafetyBlockResponse | None" = None


class SafetyBlockResponse(StrictModel):
    block_reason: str
    environment_checklist: list[str] = Field(min_length=2)
    emergency_guidance: list[str] = Field(min_length=1)
    emergency_contact_template: str


class MicroRespiteGenerateRequest(StrictModel):
    family_id: int
    caregiver_stress: float = Field(ge=0, le=10)
    caregiver_sleep_quality: float = Field(ge=0, le=10)
    support_available: Literal["none", "one", "two_plus"]
    child_emotional_state: Literal["calm", "fragile", "escalating", "meltdown_risk"]
    sensory_overload_level: Literal["none", "light", "medium", "heavy"]
    transition_difficulty: float = Field(ge=0, le=10)
    meltdown_count: int = Field(ge=0, le=3)
    notes: str = Field(default="", max_length=500)
    high_risk_selected: bool = False


class MicroRespiteOption(StrictModel):
    option_id: str
    title: str
    summary: str
    fit_reason: str
    duration_minutes: int = Field(ge=10, le=30)
    child_focus: str
    parent_focus: str
    setup_steps: list[str] = Field(min_length=2, max_length=4)
    instructions: list[str] = Field(min_length=3, max_length=4)
    safety_notes: list[str] = Field(min_length=2, max_length=4)
    support_plan: str
    source_card_ids: list[str] = Field(min_length=1, max_length=3)
    low_stimulation_only: bool = False
    requires_manual_review: bool = False


class MicroRespitePlan(StrictModel):
    headline: str
    context_summary: str
    low_stimulation_only: bool = False
    safety_notes: list[str] = Field(min_length=2, max_length=4)
    options: list[MicroRespiteOption] = Field(min_length=3, max_length=3)
    feedback_prompt: str


class MicroRespiteGenerateResponse(StrictModel):
    blocked: bool = False
    risk: SignalOutput | None = None
    plan: MicroRespitePlan | None = None
    safety_block: SafetyBlockResponse | None = None


class MicroRespiteFeedbackRequest(StrictModel):
    family_id: int
    option_id: str = Field(min_length=1)
    source_card_ids: list[str] = Field(min_length=1, max_length=3)
    effectiveness: Literal["helpful", "somewhat", "not_helpful"]
    matched_expectation: bool
    notes: str = Field(default="", max_length=500)


class MicroRespiteFeedbackResponse(StrictModel):
    review_id: int
    incident_id: int
    outcome_score: int = Field(ge=-2, le=2)
    updated_weights: dict[str, float]
    next_hint: str


class FrictionSupportFeedbackRequest(StrictModel):
    family_id: int
    incident_id: int
    source_card_ids: list[str] = Field(min_length=1, max_length=3)
    effectiveness: Literal["helpful", "somewhat", "not_helpful"]
    child_state_after: Literal["settled", "partly_settled", "still_escalating"]
    caregiver_state_after: Literal["calmer", "same", "more_overloaded"]
    notes: str = Field(default="", max_length=500)


class FrictionSupportFeedbackResponse(StrictModel):
    review_id: int
    incident_id: int
    outcome_score: int = Field(ge=-2, le=2)
    updated_weights: dict[str, float]
    next_adjustment: str


class TrainingGoal(StrictModel):
    title: str = Field(min_length=1, max_length=64)
    target: str = Field(min_length=1, max_length=160)
    success_marker: str = Field(min_length=1, max_length=160)


class TrainingFocusArea(StrictModel):
    area_key: TrainingAreaKey
    title: str = Field(min_length=1, max_length=64)
    priority_score: int = Field(ge=0, le=100)
    urgency: Literal["urgent", "high", "watch"]
    why_now: list[str] = Field(min_length=2, max_length=4)
    profile_signals: list[str] = Field(default_factory=list, max_length=3)
    recent_signals: list[str] = Field(default_factory=list, max_length=3)
    long_term_value: str = Field(min_length=1, max_length=160)


class TrainingTask(StrictModel):
    task_key: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=80)
    area_key: TrainingAreaKey
    duration_minutes: int = Field(ge=5, le=30)
    schedule_hint: str = Field(min_length=1, max_length=80)
    objective: str = Field(min_length=1, max_length=160)
    materials: list[str] = Field(min_length=1, max_length=4)
    steps: list[str] = Field(min_length=3, max_length=4)
    parent_script: str = Field(min_length=1, max_length=180)
    coaching_tip: str = Field(min_length=1, max_length=180)
    success_signals: list[str] = Field(min_length=2, max_length=3)
    fallback_plan: str = Field(min_length=1, max_length=180)
    difficulty: Literal["starter", "build", "advance"]


class TrainingAdjustment(StrictModel):
    title: str = Field(min_length=1, max_length=64)
    suggestion: str = Field(min_length=1, max_length=180)
    reason: str = Field(min_length=1, max_length=180)


class TrainingProgressItem(StrictModel):
    label: str = Field(min_length=1, max_length=32)
    value: int = Field(ge=0, le=100)
    target: int = Field(ge=1, le=100)
    summary: str = Field(min_length=1, max_length=120)


class TrainingFeedbackRead(StrictModel):
    feedback_id: int
    date: date_type
    task_key: str
    task_title: str
    area_key: TrainingAreaKey
    completion_status: TrainingCompletionStatus
    child_response: TrainingChildResponse
    difficulty_rating: TrainingDifficultyRating
    effect_score: float = Field(ge=0, le=10)
    parent_confidence: float = Field(ge=0, le=10)
    notes: str = Field(default="", max_length=500)


class TrainingPlanGenerateRequest(StrictModel):
    family_id: int
    extra_context: str = Field(default="", max_length=500)


class TrainingPlanResponse(StrictModel):
    family_id: int
    child_summary: str = Field(min_length=1)
    plan_summary: str = Field(min_length=1)
    primary_need: str = Field(min_length=1, max_length=64)
    load_level: Literal["light", "standard", "adaptive"]
    focus_areas: list[TrainingFocusArea] = Field(min_length=1, max_length=3)
    short_term_goals: list[TrainingGoal] = Field(min_length=2, max_length=3)
    long_term_goals: list[TrainingGoal] = Field(min_length=2, max_length=3)
    daily_tasks: list[TrainingTask] = Field(min_length=3, max_length=3)
    guidance: list[str] = Field(min_length=3, max_length=5)
    adjustments: list[TrainingAdjustment] = Field(min_length=2, max_length=4)
    progress: list[TrainingProgressItem] = Field(min_length=3, max_length=3)
    recent_feedback_summary: str = Field(min_length=1)
    recent_feedbacks: list[TrainingFeedbackRead] = Field(default_factory=list, max_length=6)


class TrainingTaskFeedbackRequest(StrictModel):
    family_id: int
    date: date_type | None = None
    task_key: str = Field(min_length=1, max_length=64)
    task_title: str = Field(min_length=1, max_length=80)
    area_key: TrainingAreaKey
    completion_status: TrainingCompletionStatus
    child_response: TrainingChildResponse
    difficulty_rating: TrainingDifficultyRating
    effect_score: float = Field(ge=0, le=10)
    parent_confidence: float = Field(ge=0, le=10)
    notes: str = Field(default="", max_length=500)


class TrainingTaskFeedbackResponse(StrictModel):
    feedback_id: int
    next_adjustment: str
    progress_summary: str
    plan: TrainingPlanResponse


class PlanRead(StrictModel):
    plan_id: int
    family_id: int
    risk_level: str
    plan: Plan48hResponse


class ReviewCreate(StrictModel):
    family_id: int
    incident_id: int | None = None
    scenario: str = ""
    intensity: Literal["light", "medium", "heavy"] = "medium"
    triggers: list[str] = Field(default_factory=list)
    card_ids: list[str] = Field(min_length=1)
    outcome_score: int = Field(ge=-2, le=2)
    notes: str = ""
    followup_action: str = ""


class ReviewResponse(StrictModel):
    review_id: int
    incident_id: int
    updated_weights: dict[str, float]


class ReplayResponse(StrictModel):
    incident_id: int
    timeline: list[str]
    next_improvement: str


class ReportMetricPoint(StrictModel):
    label: str
    value: float = Field(ge=0)


class TaskEffectItem(StrictModel):
    title: str
    summary: str
    status: Literal["done", "partial", "retry"]
    outcome_score: int = Field(ge=-2, le=2)


class StrategyInsight(StrictModel):
    target_key: str
    title: str
    summary: str
    evidence_count: int = Field(ge=0)
    avg_outcome: float = Field(ge=-2, le=2)


class ActionSuggestion(StrictModel):
    target_key: str
    title: str
    summary: str
    rationale: str


class ReportFeedbackSummary(StrictModel):
    effective_count: int = Field(default=0, ge=0)
    not_effective_count: int = Field(default=0, ge=0)
    continue_count: int = Field(default=0, ge=0)
    adjust_count: int = Field(default=0, ge=0)


class ReportFeedbackState(StrictModel):
    target_kind: Literal["strategy", "action"]
    target_key: str
    target_label: str
    feedback: Literal["effective", "not_effective", "continue", "adjust"]


class WeeklyReportResponse(StrictModel):
    family_id: int
    week_start: date_type
    week_end: date_type
    trigger_top3: list[str]
    trigger_summary: str
    child_emotion_summary: str
    highest_risk_scenario: str
    stress_trend: list[ReportMetricPoint] = Field(default_factory=list)
    meltdown_trend: list[ReportMetricPoint] = Field(default_factory=list)
    task_completion_score: int = Field(ge=0, le=100)
    task_summary: str
    completed_tasks: list[TaskEffectItem] = Field(default_factory=list)
    partial_tasks: list[TaskEffectItem] = Field(default_factory=list)
    retry_tasks: list[TaskEffectItem] = Field(default_factory=list)
    caregiver_summary: str
    caregiver_stress_avg: float = Field(ge=0, le=10)
    caregiver_stress_peak: float = Field(ge=0, le=10)
    caregiver_sleep_avg: float = Field(ge=0, le=10)
    strategy_top3: list[StrategyInsight] = Field(default_factory=list)
    next_actions: list[ActionSuggestion] = Field(default_factory=list)
    one_thing_next_week: str
    feedback_summary: ReportFeedbackSummary
    feedback_states: list[ReportFeedbackState] = Field(default_factory=list)
    export_count: int


class ExportRequest(StrictModel):
    family_id: int
    week_start: date_type


class MonthlyTrendItem(StrictModel):
    title: str
    summary: str
    current_value: float = Field(ge=0)
    previous_value: float = Field(ge=0)
    direction: Literal["up", "down", "flat"]
    unit: str


class MonthlyHistoryPoint(StrictModel):
    label: str
    avg_stress: float = Field(ge=0, le=10)
    conflict_count: int = Field(ge=0)
    task_completion_rate: int = Field(ge=0, le=100)


class MonthlyReportResponse(StrictModel):
    family_id: int
    month_start: date_type
    month_end: date_type
    overview_summary: str
    stress_change_summary: str
    conflict_change_summary: str
    task_completion_summary: str
    long_term_trends: list[MonthlyTrendItem] = Field(default_factory=list)
    successful_methods: list[StrategyInsight] = Field(default_factory=list)
    next_month_plan: list[ActionSuggestion] = Field(default_factory=list)
    history: list[MonthlyHistoryPoint] = Field(default_factory=list)
    feedback_summary: ReportFeedbackSummary
    feedback_states: list[ReportFeedbackState] = Field(default_factory=list)


class ReportFeedbackCreate(StrictModel):
    family_id: int
    period_type: Literal["weekly", "monthly"]
    period_start: date_type
    target_kind: Literal["strategy", "action"]
    target_key: str = Field(min_length=1, max_length=128)
    target_label: str = Field(min_length=1, max_length=128)
    feedback: Literal["effective", "not_effective", "continue", "adjust"]
    note: str = Field(default="", max_length=500)


class ReportFeedbackResponse(StrictModel):
    feedback_id: int
    family_id: int
    period_type: Literal["weekly", "monthly"]
    period_start: date_type
    target_kind: Literal["strategy", "action"]
    target_key: str
    feedback: Literal["effective", "not_effective", "continue", "adjust"]
    summary: ReportFeedbackSummary


class ExportResponse(StrictModel):
    ok: bool
    export_count: int
    artifact: str


class SupportCardExportRequest(StrictModel):
    family_id: int
    format: Literal["pdf", "png"] = "pdf"


class SupportCardExportResponse(StrictModel):
    family_id: int
    format: Literal["pdf", "png"]
    content: dict[str, Any]


class RiskResponse(StrictModel):
    family_id: int
    date: date_type
    risk: SignalOutput


class StrategyCardSeed(StrictModel):
    id: str
    title: str
    scenario_tags: list[str]
    applicable_conditions: dict[str, Any]
    steps: list[str]
    scripts: dict[str, str]
    donts: list[str]
    escalate_when: list[str]
    cost_level: Literal["low", "medium", "high"]
    risk_level: Literal["low", "medium", "high"]
    evidence_tag: Literal["evidence", "expert", "practice"]


CheckinResponse.model_rebuild()
OnboardingSetupResponse.model_rebuild()
Plan48hGenerateResponse.model_rebuild()
ScriptGenerateResponse.model_rebuild()
FrictionSupportGenerateResponse.model_rebuild()
