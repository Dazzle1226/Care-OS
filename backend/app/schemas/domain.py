from __future__ import annotations

from datetime import date as date_type, datetime as datetime_type
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


HighFrictionPreset = Literal[
    "transition_now",
    "bedtime_push",
    "homework_push",
    "outing_exit",
    "meltdown_now",
    "wakeup_stall",
    "meal_conflict",
    "screen_off",
    "bath_resistance",
    "waiting_public",
]
TrainingAreaKey = Literal[
    "emotion_regulation",
    "communication",
    "social_interaction",
    "sensory_regulation",
    "transition_flexibility",
    "daily_living",
    "waiting_tolerance",
    "task_initiation",
    "bedtime_routine",
    "simple_compliance",
]
TrainingCompletionStatus = Literal["done", "partial", "missed"]
TrainingChildResponse = Literal["engaged", "accepted", "resistant", "overloaded"]
TrainingDifficultyRating = Literal["too_easy", "just_right", "too_hard"]
TrainingSkillStage = Literal["stabilize", "practice", "generalize", "maintain"]
TrainingLoadLevel = Literal["light", "standard", "adaptive"]
TrainingTaskStatus = Literal["pending", "scheduled", "done", "partial", "missed"]
TrainingHelpfulness = Literal["helpful", "neutral", "not_helpful"]
TrainingObstacleTag = Literal[
    "none",
    "too_hard",
    "refused",
    "parent_overloaded",
    "wrong_timing",
    "sensory_overload",
    "unclear_steps",
]
TrainingReminderStatus = Literal["none", "scheduled", "due"]

FRICTION_PRESET_DEFAULTS: dict[HighFrictionPreset, dict[str, Any]] = {
    "transition_now": {
        "scenario": "transition",
        "child_state": "transition_block",
        "sensory_overload_level": "medium",
        "transition_difficulty": 8.0,
        "meltdown_count": 1,
        "caregiver_stress": 7.0,
        "caregiver_fatigue": 7.0,
        "caregiver_sleep_quality": 4.0,
        "support_available": "none",
        "confidence_to_follow_plan": 5.0,
        "env_changes": ["切换任务"],
    },
    "bedtime_push": {
        "scenario": "bedtime",
        "child_state": "emotional_wave",
        "sensory_overload_level": "light",
        "transition_difficulty": 7.0,
        "meltdown_count": 1,
        "caregiver_stress": 7.0,
        "caregiver_fatigue": 8.0,
        "caregiver_sleep_quality": 3.0,
        "support_available": "one",
        "confidence_to_follow_plan": 4.0,
        "env_changes": ["睡前切换"],
    },
    "homework_push": {
        "scenario": "homework",
        "child_state": "conflict",
        "sensory_overload_level": "light",
        "transition_difficulty": 6.0,
        "meltdown_count": 1,
        "caregiver_stress": 7.0,
        "caregiver_fatigue": 6.0,
        "caregiver_sleep_quality": 4.0,
        "support_available": "one",
        "confidence_to_follow_plan": 4.0,
        "env_changes": ["学习任务"],
    },
    "outing_exit": {
        "scenario": "outing",
        "child_state": "sensory_overload",
        "sensory_overload_level": "medium",
        "transition_difficulty": 7.0,
        "meltdown_count": 1,
        "caregiver_stress": 7.0,
        "caregiver_fatigue": 6.0,
        "caregiver_sleep_quality": 5.0,
        "support_available": "one",
        "confidence_to_follow_plan": 4.0,
        "env_changes": ["外出", "人多"],
    },
    "meltdown_now": {
        "scenario": "meltdown",
        "child_state": "meltdown",
        "sensory_overload_level": "heavy",
        "transition_difficulty": 9.0,
        "meltdown_count": 3,
        "caregiver_stress": 9.0,
        "caregiver_fatigue": 8.0,
        "caregiver_sleep_quality": 4.0,
        "support_available": "one",
        "confidence_to_follow_plan": 2.0,
        "env_changes": ["持续升级"],
    },
    "wakeup_stall": {
        "scenario": "transition",
        "child_state": "transition_block",
        "sensory_overload_level": "light",
        "transition_difficulty": 7.0,
        "meltdown_count": 0,
        "caregiver_stress": 6.0,
        "caregiver_fatigue": 7.0,
        "caregiver_sleep_quality": 4.0,
        "support_available": "one",
        "confidence_to_follow_plan": 5.0,
        "env_changes": ["起床"],
    },
    "meal_conflict": {
        "scenario": "transition",
        "child_state": "conflict",
        "sensory_overload_level": "light",
        "transition_difficulty": 6.0,
        "meltdown_count": 1,
        "caregiver_stress": 6.0,
        "caregiver_fatigue": 6.0,
        "caregiver_sleep_quality": 5.0,
        "support_available": "one",
        "confidence_to_follow_plan": 5.0,
        "env_changes": ["吃饭"],
    },
    "screen_off": {
        "scenario": "transition",
        "child_state": "conflict",
        "sensory_overload_level": "medium",
        "transition_difficulty": 8.0,
        "meltdown_count": 1,
        "caregiver_stress": 7.0,
        "caregiver_fatigue": 6.0,
        "caregiver_sleep_quality": 5.0,
        "support_available": "none",
        "confidence_to_follow_plan": 4.0,
        "env_changes": ["关屏"],
    },
    "bath_resistance": {
        "scenario": "bedtime",
        "child_state": "sensory_overload",
        "sensory_overload_level": "medium",
        "transition_difficulty": 7.0,
        "meltdown_count": 1,
        "caregiver_stress": 7.0,
        "caregiver_fatigue": 7.0,
        "caregiver_sleep_quality": 4.0,
        "support_available": "one",
        "confidence_to_follow_plan": 4.0,
        "env_changes": ["洗澡"],
    },
    "waiting_public": {
        "scenario": "outing",
        "child_state": "emotional_wave",
        "sensory_overload_level": "medium",
        "transition_difficulty": 8.0,
        "meltdown_count": 1,
        "caregiver_stress": 7.0,
        "caregiver_fatigue": 6.0,
        "caregiver_sleep_quality": 5.0,
        "support_available": "one",
        "confidence_to_follow_plan": 4.0,
        "env_changes": ["等待", "排队"],
    },
}

FRICTION_PRESET_LABELS: dict[HighFrictionPreset, str] = {
    "transition_now": "过渡",
    "bedtime_push": "睡前",
    "homework_push": "作业",
    "outing_exit": "外出",
    "meltdown_now": "崩溃",
    "wakeup_stall": "起床",
    "meal_conflict": "吃饭",
    "screen_off": "关屏",
    "bath_resistance": "洗澡",
    "waiting_public": "等待",
}
ReviewChildStateAfter = Literal["settled", "partly_settled", "still_escalating"]
ReviewCaregiverStateAfter = Literal["calmer", "same", "more_overloaded"]
StrategyDecision = Literal["continue", "pause", "replace"]


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
    core_difficulties: list[str] = Field(default_factory=list, max_length=10)
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
    supporter_availability: list[str] = Field(default_factory=list, max_length=8)
    supporter_independent_care: Literal["can_alone", "needs_handoff", "cannot_alone", "unknown"] | None = None
    major_incident_notes: str = Field(default="", max_length=300)
    emergency_contacts: list[str] = Field(default_factory=list, max_length=8)


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
    core_difficulties: list[str] = Field(default_factory=list, max_length=10)
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
    supporter_availability: list[str] = Field(default_factory=list, max_length=8)
    supporter_independent_care: Literal["can_alone", "needs_handoff", "cannot_alone", "unknown"] | None = None
    major_incident_notes: str = Field(default="", max_length=300)
    emergency_contacts: list[str] = Field(default_factory=list, max_length=8)


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
    icon: Literal["support", "handoff"]
    title: str
    summary: str
    one_liner: str
    quick_actions: list[str] = Field(min_length=2, max_length=3)
    sections: list["OnboardingSupportCardSection"] = Field(min_length=6, max_length=7)


class OnboardingSupportCardSection(StrictModel):
    key: str
    title: str
    items: list[str] = Field(min_length=1, max_length=3)


class OnboardingSetupResponse(StrictModel):
    family: FamilyRead
    profile: ChildProfileRead
    snapshot: OnboardingSnapshot
    support_cards: list[OnboardingSupportCard] = Field(min_length=2, max_length=2)


class CheckinCreate(StrictModel):
    family_id: int
    date: date_type | None = None
    child_sleep_hours: float = Field(ge=0, le=12)
    child_sleep_quality: float | None = Field(default=None, ge=0, le=10)
    sleep_issues: list[str] = Field(default_factory=list, max_length=8)
    meltdown_count: int = Field(ge=0, le=3)
    child_mood_state: Literal["stable", "sensitive", "anxious", "low_energy", "irritable"] = "stable"
    physical_discomforts: list[str] = Field(default_factory=list, max_length=8)
    aggressive_behaviors: list[str] = Field(default_factory=list, max_length=8)
    negative_emotions: list[str] = Field(default_factory=list, max_length=8)
    transition_difficulty: float | None = Field(default=None, ge=0, le=10)
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
    child_sleep_quality: float | None
    sleep_issues: list[str] = Field(default_factory=list)
    meltdown_count: int
    child_mood_state: Literal["stable", "sensitive", "anxious", "low_energy", "irritable"]
    physical_discomforts: list[str] = Field(default_factory=list)
    aggressive_behaviors: list[str] = Field(default_factory=list)
    negative_emotions: list[str] = Field(default_factory=list)
    transition_difficulty: float | None
    sensory_overload_level: Literal["none", "light", "medium", "heavy"]
    caregiver_stress: float
    caregiver_sleep_quality: float
    support_available: Literal["none", "one", "two_plus"]
    today_activities: list[str] = Field(default_factory=list)
    today_learning_tasks: list[str] = Field(default_factory=list)


class TodayReminderItem(StrictModel):
    eyebrow: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class TodayFocusResponse(StrictModel):
    today_one_thing: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    reminders: list[TodayReminderItem] = Field(min_length=2, max_length=2)


class DailyActionPlan(StrictModel):
    headline: str
    summary: str
    reminders: list[TodayReminderItem] = Field(min_length=2, max_length=2)
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


class CandidateScore(StrictModel):
    card_id: str
    title: str
    total_score: float
    semantic_score: float
    lexical_score: float
    scenario_match: float
    profile_fit: float
    historical_effect: float
    policy_weight: float = 0
    execution_cost_bonus: float
    risk_penalty: float
    taboo_conflict_penalty: float
    selected: bool = False
    why_selected: list[str] = Field(default_factory=list, max_length=3)
    why_not_selected: list[str] = Field(default_factory=list, max_length=3)
    selected_chunk_ids: list[str] = Field(default_factory=list, max_length=4)
    hard_filter_tags: list[str] = Field(default_factory=list, max_length=4)
    personalization_notes: list[str] = Field(default_factory=list, max_length=3)


class RetrievalQueryPlan(StrictModel):
    intent: Literal["plan", "script", "friction", "report"]
    scenario: str
    intensity: str
    family_id: int
    profile_facets: list[str] = Field(default_factory=list, max_length=10)
    recent_context_signals: list[str] = Field(default_factory=list, max_length=10)
    hard_exclusions: list[str] = Field(default_factory=list, max_length=8)
    time_window: str = "recent"
    raw_query_text: str = ""


class RetrievalFeatureAttribution(StrictModel):
    target_id: str
    target_kind: Literal["card", "chunk", "family_memory"]
    summary: str
    contribution: float


class RetrievalTraceCandidateRead(StrictModel):
    candidate_id: int
    source_type: str
    card_id: str | None = None
    chunk_id: int | None = None
    title: str
    total_score: float
    dense_score: float
    sparse_score: float
    profile_score: float
    history_score: float
    policy_score: float
    safety_penalty: float
    selected: bool = False
    filter_reason: str = ""
    feature_attribution: list[dict[str, Any]] = Field(default_factory=list)


class RetrievalSelectedSource(StrictModel):
    source_id: str
    source_type: str
    title: str
    scope: Literal["global", "segment", "family"] = "global"


class RetrievalEvidenceBundle(StrictModel):
    selected_card_ids: list[str] = Field(default_factory=list, max_length=3)
    selected_evidence_unit_ids: list[str] = Field(default_factory=list, max_length=8)
    selected_chunk_ids: list[str] = Field(default_factory=list, max_length=12)
    candidate_scores: list[CandidateScore] = Field(default_factory=list)
    selection_reasons: list[str] = Field(default_factory=list, max_length=4)
    rejected_reasons: list[str] = Field(default_factory=list, max_length=4)
    counter_evidence: list[str] = Field(default_factory=list, max_length=4)
    coverage_scores: dict[str, float] = Field(default_factory=dict)
    confidence_score: float = Field(ge=0, le=1)
    insufficient_evidence: bool = False
    missing_dimensions: list[str] = Field(default_factory=list, max_length=4)
    ranking_summary: str
    query_plan: RetrievalQueryPlan | None = None
    selected_sources: list[RetrievalSelectedSource] = Field(default_factory=list)
    feature_attribution: list[RetrievalFeatureAttribution] = Field(default_factory=list)
    personalization_applied: list[str] = Field(default_factory=list, max_length=6)
    hard_filtered_reasons: list[str] = Field(default_factory=list, max_length=6)
    coverage_gaps: list[str] = Field(default_factory=list, max_length=6)
    knowledge_versions: list[str] = Field(default_factory=list, max_length=6)
    retrieval_latency_ms: int = Field(default=0, ge=0)
    retrieval_run_id: int | None = None


class CriticReview(StrictModel):
    critic: Literal["safety", "evidence", "plan"]
    decision: Literal["pass", "revise", "clarify", "needs_clarification", "fallback_ok", "block"] = "pass"
    blocked: bool = False
    issue_type: Literal["missing_evidence", "insufficient_coverage", "citation_mismatch", "safety", "plan_quality"] | None = None
    reasons: list[str] = Field(default_factory=list, max_length=5)
    summary: str


class EvidenceGapGuidance(StrictModel):
    known_facts: list[str] = Field(default_factory=list, min_length=1, max_length=3)
    uncertain_areas: list[str] = Field(default_factory=list, min_length=1, max_length=4)
    provisional_recommendation: str = Field(min_length=1)
    recommendation_conditions: list[str] = Field(default_factory=list, min_length=2, max_length=3)
    info_to_collect: list[str] = Field(default_factory=list, min_length=2, max_length=4)
    safe_next_steps: list[str] = Field(default_factory=list, min_length=2, max_length=3)


class ContextSignalRead(StrictModel):
    signal_key: str
    signal_label: str
    signal_value: str
    confidence: float = Field(ge=0, le=1)


class MultimodalIngestionRequest(StrictModel):
    family_id: int
    source_type: Literal["document", "audio"]
    content_name: str = Field(default="", max_length=160)
    raw_text: str = Field(min_length=1, max_length=4000)


class MultimodalIngestionResponse(StrictModel):
    ingestion_id: int
    family_id: int
    source_type: Literal["document", "audio"]
    content_name: str
    raw_excerpt: str
    normalized_summary: str
    context_signals: list[ContextSignalRead] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    manual_review_required: bool = False
    created_at: datetime_type


class ContextFrameRead(StrictModel):
    summary_text: str = ""
    signal_keys: list[str] = Field(default_factory=list, max_length=10)
    signal_labels: list[str] = Field(default_factory=list, max_length=10)
    ingestion_ids: list[int] = Field(default_factory=list, max_length=8)


class EvidenceUnitRead(StrictModel):
    unit_id: str
    card_id: str
    unit_kind: Literal["step", "script", "dont", "escalate_when", "fit_condition"]
    text: str
    dimensions: list[str] = Field(default_factory=list, max_length=4)


class DecisionGraphStageRun(StrictModel):
    stage: Literal[
        "context_ingestion",
        "context_fusion",
        "goal_interpretation",
        "signal_eval",
        "emotion_eval",
        "evidence_recall",
        "task_decomposition",
        "candidate_generation",
        "candidate_simulation",
        "safety_critic",
        "evidence_critic",
        "critic_reflection",
        "executor",
        "replanner",
        "coordination",
        "policy_adjust_hint",
        "memory_learning",
        "finalizer",
    ]
    status: Literal["success", "blocked", "fallback", "skipped"]
    input_ref: str = ""
    output: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = Field(ge=0)
    fallback_used: bool = False
    retry_count: int = Field(default=0, ge=0)


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
    evidence_gap_guidance: EvidenceGapGuidance | None = None


class Plan48hGenerateRequest(StrictModel):
    family_id: int
    context: Literal["checkin", "incident", "manual"]
    scenario: str | None = None
    manual_trigger: bool = False
    high_risk_selected: bool = False
    free_text: str = ""
    include_debug: bool = False


class Plan48hGenerateResponse(StrictModel):
    blocked: bool = False
    plan_id: int | None = None
    risk: SignalOutput | None = None
    plan: Plan48hResponse | None = None
    safety_block: "SafetyBlockResponse | None" = None
    evidence_bundle: RetrievalEvidenceBundle | None = None
    decision_trace_id: int | None = None
    decision_summary: str | None = None


class ScriptGenerateRequest(StrictModel):
    family_id: int
    scenario: Literal["transition", "bedtime", "homework", "outing"]
    intensity: Literal["light", "medium", "heavy"]
    resources: dict[str, Any] = Field(default_factory=dict)
    high_risk_selected: bool = False
    free_text: str = ""
    include_debug: bool = False


class ScriptResponse(StrictModel):
    steps: list[str] = Field(min_length=3, max_length=3)
    script_line: str = Field(min_length=1)
    donts: list[str] = Field(min_length=2)
    exit_plan: list[str] = Field(min_length=1)
    citations: list[str] = Field(min_length=1)
    evidence_gap_guidance: EvidenceGapGuidance | None = None


class ScriptGenerateResponse(StrictModel):
    blocked: bool = False
    script: ScriptResponse | None = None
    safety_block: "SafetyBlockResponse | None" = None
    evidence_bundle: RetrievalEvidenceBundle | None = None
    decision_trace_id: int | None = None
    decision_summary: str | None = None


class FrictionSupportStep(StrictModel):
    title: str = Field(min_length=1, max_length=32)
    action: str = Field(min_length=1)
    parent_script: str = Field(min_length=1)
    why_it_fits: str = Field(min_length=1)


class FrictionLowStimMode(StrictModel):
    active: bool = False
    headline: str = Field(min_length=1)
    actions: list[str] = Field(min_length=3, max_length=4)


class FrictionCrisisCard(StrictModel):
    title: str = Field(min_length=1)
    badges: list[str] = Field(min_length=2, max_length=4)
    first_do: list[str] = Field(min_length=3, max_length=3)
    donts: list[str] = Field(min_length=3, max_length=3)
    say_this: list[str] = Field(min_length=2, max_length=3)
    exit_plan: list[str] = Field(min_length=3, max_length=3)
    help_now: list[str] = Field(min_length=1, max_length=2)


class FrictionRespiteSuggestion(StrictModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    duration_minutes: int = Field(ge=10, le=30)
    support_plan: str = Field(min_length=1)


class FrictionSupportPlan(StrictModel):
    preset_label: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    situation_summary: str = Field(min_length=1)
    child_signals: list[str] = Field(min_length=2, max_length=3)
    caregiver_signals: list[str] = Field(min_length=2, max_length=3)
    why_this_plan: list[str] = Field(min_length=2, max_length=4)
    excluded_actions: list[str] = Field(min_length=2, max_length=4)
    action_plan: list[FrictionSupportStep] = Field(min_length=3, max_length=3)
    donts: list[str] = Field(min_length=3, max_length=4)
    say_this: list[str] = Field(min_length=2, max_length=3)
    voice_guidance: list[str] = Field(min_length=3, max_length=3)
    exit_plan: list[str] = Field(min_length=3, max_length=3)
    low_stim_mode: FrictionLowStimMode
    crisis_card: FrictionCrisisCard
    respite_suggestion: FrictionRespiteSuggestion
    personalized_strategies: list[str] = Field(min_length=2, max_length=4)
    school_message: str = Field(min_length=1)
    handoff_messages: list[PlanMessage] = Field(min_length=3, max_length=3)
    feedback_prompt: str = Field(min_length=1)
    citations: list[str] = Field(min_length=1)
    source_card_ids: list[str] = Field(min_length=1, max_length=3)
    evidence_gap_guidance: EvidenceGapGuidance | None = None


class FrictionSupportGenerateRequest(StrictModel):
    family_id: int
    quick_preset: HighFrictionPreset | None = None
    scenario: Literal["transition", "bedtime", "homework", "outing", "meltdown"] = "transition"
    custom_scenario: str = Field(default="", max_length=80)
    child_state: Literal["emotional_wave", "sensory_overload", "conflict", "meltdown", "transition_block"] = "transition_block"
    sensory_overload_level: Literal["none", "light", "medium", "heavy"] = "medium"
    transition_difficulty: float = Field(default=7, ge=0, le=10)
    meltdown_count: int = Field(default=1, ge=0, le=3)
    caregiver_stress: float = Field(default=7, ge=0, le=10)
    caregiver_fatigue: float = Field(default=7, ge=0, le=10)
    caregiver_sleep_quality: float = Field(default=4, ge=0, le=10)
    support_available: Literal["none", "one", "two_plus"] = "none"
    confidence_to_follow_plan: float = Field(default=4, ge=0, le=10)
    env_changes: list[str] = Field(default_factory=list)
    free_text: str = Field(default="", max_length=500)
    low_stim_mode_requested: bool = False
    high_risk_selected: bool = False
    include_debug: bool = False

    @model_validator(mode="after")
    def apply_quick_preset(self) -> "FrictionSupportGenerateRequest":
        if not self.quick_preset:
            return self

        defaults = FRICTION_PRESET_DEFAULTS[self.quick_preset]
        explicit_fields = self.model_fields_set
        for field_name, value in defaults.items():
            if field_name in explicit_fields:
                continue
            setattr(self, field_name, value.copy() if isinstance(value, list) else value)
        return self


class FrictionSupportGenerateResponse(StrictModel):
    blocked: bool = False
    incident_id: int | None = None
    risk: SignalOutput | None = None
    support: FrictionSupportPlan | None = None
    safety_block: "SafetyBlockResponse | None" = None
    evidence_bundle: RetrievalEvidenceBundle | None = None
    decision_trace_id: int | None = None
    decision_summary: str | None = None


class EmotionAssessment(StrictModel):
    child_emotion: Literal["calm", "fragile", "escalating", "meltdown_risk"]
    caregiver_emotion: Literal["calm", "strained", "anxious", "overloaded"]
    child_overload_level: Literal["low", "medium", "high"]
    caregiver_overload_level: Literal["low", "medium", "high"]
    confidence_drift: Literal["stable", "dropping", "critical"]
    recommended_adjustments: list[str] = Field(default_factory=list, max_length=4)
    confidence: float = Field(ge=0, le=1)
    reasoning: list[str] = Field(default_factory=list, max_length=4)


class AgentProposal(StrictModel):
    proposal_id: str = Field(min_length=1, max_length=64)
    agent_name: str = Field(min_length=1, max_length=64)
    proposal_kind: Literal["continue", "lighter", "handoff", "block"]
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    priority: float = Field(ge=0)
    rationale: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list, max_length=4)


class CoordinationDecision(StrictModel):
    selected_proposal_id: str = Field(min_length=1, max_length=64)
    alternative_proposal_ids: list[str] = Field(default_factory=list, max_length=4)
    decision_reason: str = Field(min_length=1)
    weight_summary: list[str] = Field(default_factory=list, max_length=5)
    replan_triggers: list[str] = Field(default_factory=list, max_length=5)
    active_mode: Literal["continue", "lighter", "handoff", "blocked"] = "continue"
    now_step: str = Field(min_length=1)
    now_script: str = Field(min_length=1)
    next_if_not_working: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class GoalSpec(StrictModel):
    goal_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=80)
    success_definition: str = Field(min_length=1, max_length=160)
    constraints: list[str] = Field(default_factory=list, max_length=6)


class TaskNode(StrictModel):
    task_id: str = Field(min_length=1, max_length=64)
    parent_task_id: str | None = Field(default=None, max_length=64)
    goal: str = Field(min_length=1, max_length=160)
    kind: Literal["stabilize", "co_regulate", "transition", "handoff", "exit", "observe"]
    priority: float = Field(ge=0)
    status: Literal["pending", "active", "completed", "failed", "dropped"] = "pending"
    preconditions: list[str] = Field(default_factory=list, max_length=4)
    success_signals: list[str] = Field(default_factory=list, max_length=4)
    failure_signals: list[str] = Field(default_factory=list, max_length=4)
    fallback_task_ids: list[str] = Field(default_factory=list, max_length=3)
    instructions: list[str] = Field(default_factory=list, min_length=1, max_length=3)
    say_this: list[str] = Field(default_factory=list, min_length=1, max_length=2)
    citations: list[str] = Field(default_factory=list, min_length=1, max_length=3)
    why_now: str = Field(min_length=1, max_length=160)
    depth: int = Field(default=0, ge=0, le=3)


class ReplanTrigger(StrictModel):
    trigger_type: Literal[
        "session_start",
        "no_improvement",
        "caregiver_overloaded",
        "child_escalating",
        "support_arrived",
        "user_requests_lighter",
        "user_requests_handoff",
        "new_context_ingested",
    ]
    source_event: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=200)


class ExecutionState(StrictModel):
    active_task_id: str | None = Field(default=None, max_length=64)
    completed_task_ids: list[str] = Field(default_factory=list, max_length=8)
    failed_task_ids: list[str] = Field(default_factory=list, max_length=8)
    dropped_task_ids: list[str] = Field(default_factory=list, max_length=8)
    latest_event: ReplanTrigger | None = None
    active_mode: Literal["continue", "lighter", "handoff", "blocked"] = "continue"
    latest_critic_verdicts: list[str] = Field(default_factory=list, max_length=4)


class PlanRevisionDiff(StrictModel):
    trigger: ReplanTrigger
    affected_task_ids: list[str] = Field(default_factory=list, max_length=6)
    dropped_task_ids: list[str] = Field(default_factory=list, max_length=6)
    added_task_ids: list[str] = Field(default_factory=list, max_length=6)
    active_task_before: str | None = Field(default=None, max_length=64)
    active_task_after: str | None = Field(default=None, max_length=64)
    summary: str = Field(min_length=1, max_length=200)


class PlanRevision(StrictModel):
    revision_no: int = Field(ge=1)
    parent_revision_no: int | None = Field(default=None, ge=1)
    goal: GoalSpec
    task_tree: list[TaskNode] = Field(default_factory=list, min_length=1, max_length=12)
    execution_state: ExecutionState
    critic_verdicts: list[CriticReview] = Field(default_factory=list, max_length=4)
    revision_diff: PlanRevisionDiff


class DecisionStateRead(StrictModel):
    session_id: int
    family_id: int
    chain: Literal["friction_support", "training_support"]
    state_version: int = Field(ge=1)
    latest_inputs: dict[str, Any] = Field(default_factory=dict)
    context_signals: list[ContextSignalRead] = Field(default_factory=list, max_length=12)
    risk_assessment: SignalOutput | None = None
    emotion_assessment: EmotionAssessment | None = None
    retrieval_bundle: RetrievalEvidenceBundle | None = None
    coordination: CoordinationDecision | None = None
    active_plan_summary: dict[str, Any] = Field(default_factory=dict)
    used_memory_signals: list[str] = Field(default_factory=list, max_length=6)
    adaptation_history: list[str] = Field(default_factory=list, max_length=8)
    trace_summary: list[DecisionGraphStageRun] = Field(default_factory=list)


class AdaptiveSessionRead(StrictModel):
    session_id: int
    incident_id: int | None = None
    family_id: int
    chain: Literal["friction_support", "training_support"]
    status: Literal["active", "blocked", "closed"]
    current_state_version: int = Field(ge=1)
    active_plan_summary: dict[str, Any] = Field(default_factory=dict)
    next_check_in_hint: str = Field(min_length=1)
    last_trace_id: int | None = None
    created_at: datetime_type
    updated_at: datetime_type


class SessionEventRead(StrictModel):
    event_id: int
    source_type: Literal["text", "audio", "document", "system", "user_action"]
    event_kind: Literal[
        "text_update",
        "audio_update",
        "status_check",
        "request_lighter",
        "request_handoff",
        "no_improvement",
        "caregiver_overloaded",
        "child_escalating",
        "support_arrived",
        "new_context_ingested",
        "confirm",
        "close",
    ]
    raw_text: str
    ingestion_id: int | None = None
    replanned: bool = False
    created_at: datetime_type


class V3FrictionSessionStartRequest(FrictionSupportGenerateRequest):
    ingestion_ids: list[int] = Field(default_factory=list, max_length=4)


class V3FrictionSessionEventRequest(StrictModel):
    source_type: Literal["text", "audio", "document", "user_action"] = "text"
    event_kind: Literal[
        "text_update",
        "audio_update",
        "status_check",
        "request_lighter",
        "request_handoff",
        "no_improvement",
        "caregiver_overloaded",
        "child_escalating",
        "support_arrived",
        "new_context_ingested",
    ]
    raw_text: str = Field(default="", max_length=500)
    ingestion_id: int | None = None


class V3FrictionSessionConfirmRequest(StrictModel):
    action: Literal["continue", "lighter", "handoff", "reject"]
    note: str = Field(default="", max_length=300)


class V3FrictionSessionCloseRequest(StrictModel):
    effectiveness: Literal["helpful", "somewhat", "not_helpful"]
    child_state_after: Literal["settled", "partly_settled", "still_escalating"]
    caregiver_state_after: Literal["calmer", "same", "more_overloaded"]
    notes: str = Field(default="", max_length=500)


class V3FrictionSessionStartResponse(StrictModel):
    blocked: bool = False
    session: AdaptiveSessionRead | None = None
    decision_state: DecisionStateRead | None = None
    risk: SignalOutput | None = None
    emotion: EmotionAssessment | None = None
    support: FrictionSupportPlan | None = None
    coordination: CoordinationDecision | None = None
    safety_block: "SafetyBlockResponse | None" = None
    evidence_bundle: RetrievalEvidenceBundle | None = None
    trace_id: int | None = None
    trace_summary: list[DecisionGraphStageRun] = Field(default_factory=list)
    plan_revision: PlanRevision | None = None
    active_task: TaskNode | None = None
    task_tree: list[TaskNode] = Field(default_factory=list)
    execution_state: ExecutionState | None = None
    replan_reason: str | None = None
    critic_verdicts: list[CriticReview] = Field(default_factory=list)
    revision_diff: PlanRevisionDiff | None = None


class V3FrictionSessionEventResponse(StrictModel):
    session: AdaptiveSessionRead
    event: SessionEventRead
    replanned: bool = False
    changed_fields: list[str] = Field(default_factory=list, max_length=6)
    decision_state: DecisionStateRead | None = None
    risk: SignalOutput | None = None
    emotion: EmotionAssessment | None = None
    support: FrictionSupportPlan | None = None
    coordination: CoordinationDecision | None = None
    evidence_bundle: RetrievalEvidenceBundle | None = None
    trace_id: int | None = None
    trace_summary: list[DecisionGraphStageRun] = Field(default_factory=list)
    plan_revision: PlanRevision | None = None
    active_task: TaskNode | None = None
    task_tree: list[TaskNode] = Field(default_factory=list)
    execution_state: ExecutionState | None = None
    replan_reason: str | None = None
    critic_verdicts: list[CriticReview] = Field(default_factory=list)
    revision_diff: PlanRevisionDiff | None = None


class V3FrictionSessionConfirmResponse(StrictModel):
    session: AdaptiveSessionRead
    decision_state: DecisionStateRead | None = None
    coordination: CoordinationDecision
    support: FrictionSupportPlan
    trace_id: int | None = None
    trace_summary: list[DecisionGraphStageRun] = Field(default_factory=list)
    plan_revision: PlanRevision | None = None
    active_task: TaskNode | None = None
    task_tree: list[TaskNode] = Field(default_factory=list)
    execution_state: ExecutionState | None = None
    replan_reason: str | None = None
    critic_verdicts: list[CriticReview] = Field(default_factory=list)
    revision_diff: PlanRevisionDiff | None = None


class V3FrictionSessionCloseResponse(StrictModel):
    session: AdaptiveSessionRead
    decision_state: DecisionStateRead | None = None
    learning_summary: list[str] = Field(default_factory=list, max_length=5)
    updated_weights: dict[str, float] = Field(default_factory=dict)


class V3FrictionSessionTraceResponse(StrictModel):
    session: AdaptiveSessionRead
    decision_state: DecisionStateRead | None = None
    trace: DecisionTraceRead
    events: list[SessionEventRead] = Field(default_factory=list)


class V3TrainingSessionStartRequest(StrictModel):
    family_id: int
    extra_context: str = Field(default="", max_length=500)
    force_regenerate: bool = False
    ingestion_ids: list[int] = Field(default_factory=list, max_length=8)


class V3TrainingSessionEventRequest(StrictModel):
    source_type: Literal["text", "audio", "document", "user_action"] = "text"
    event_kind: Literal[
        "text_update",
        "audio_update",
        "status_check",
        "request_lighter",
        "no_improvement",
        "caregiver_overloaded",
        "new_context_ingested",
    ]
    raw_text: str = Field(default="", max_length=500)
    ingestion_id: int | None = None


class V3TrainingSessionCloseRequest(StrictModel):
    effectiveness: Literal["helpful", "somewhat", "not_helpful"]
    notes: str = Field(default="", max_length=500)


class V3TrainingSessionStartResponse(StrictModel):
    session: AdaptiveSessionRead
    decision_state: DecisionStateRead
    dashboard: TrainingDashboardResponse
    coordination: CoordinationDecision
    trace_id: int | None = None
    trace_summary: list[DecisionGraphStageRun] = Field(default_factory=list)


class V3TrainingSessionEventResponse(StrictModel):
    session: AdaptiveSessionRead
    event: SessionEventRead
    replanned: bool = False
    changed_fields: list[str] = Field(default_factory=list, max_length=6)
    decision_state: DecisionStateRead
    dashboard: TrainingDashboardResponse
    coordination: CoordinationDecision
    trace_id: int | None = None
    trace_summary: list[DecisionGraphStageRun] = Field(default_factory=list)


class V3TrainingSessionCloseResponse(StrictModel):
    session: AdaptiveSessionRead
    decision_state: DecisionStateRead
    dashboard: TrainingDashboardResponse
    learning_summary: list[str] = Field(default_factory=list, max_length=5)
    updated_weights: dict[str, float] = Field(default_factory=dict)


class SafetyBlockResponse(StrictModel):
    severity: Literal["high_risk", "conflict", "quality"] = "quality"
    block_reason: str
    safe_next_steps: list[str] = Field(min_length=3, max_length=4)
    do_not_do: list[str] = Field(min_length=2, max_length=4)
    say_this_now: str = Field(min_length=1)
    exit_plan: list[str] = Field(min_length=3, max_length=3)
    help_now: list[str] = Field(min_length=1, max_length=3)
    low_stim_recommended: bool = True
    conflict_explanation: str | None = None
    alternatives: list[str] = Field(default_factory=list, max_length=3)
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


class TrainingFeedbackRead(StrictModel):
    feedback_id: int
    date: date_type
    task_instance_id: int | None = None
    task_key: str
    task_title: str
    area_key: TrainingAreaKey
    completion_status: TrainingCompletionStatus
    child_response: TrainingChildResponse
    difficulty_rating: TrainingDifficultyRating
    helpfulness: TrainingHelpfulness = "neutral"
    obstacle_tag: TrainingObstacleTag = "none"
    safety_pause: bool = False
    effect_score: float = Field(ge=0, le=10)
    parent_confidence: float = Field(ge=0, le=10)
    notes: str = Field(default="", max_length=500)


class TrainingPriorityDomainCard(StrictModel):
    area_key: TrainingAreaKey
    title: str = Field(min_length=1, max_length=64)
    priority_label: Literal["high", "medium"]
    priority_score: int = Field(ge=0, le=100)
    recommended_reason: str = Field(min_length=1, max_length=180)
    current_stage: TrainingSkillStage
    current_difficulty: Literal["starter", "build", "advance"]
    weekly_sessions_count: int = Field(ge=0)
    has_today_task: bool
    current_status: str = Field(min_length=1, max_length=180)
    improvement_value: str = Field(min_length=1, max_length=180)
    coordination_hint: str = Field(default="", max_length=180)


class DailyTrainingTaskRead(StrictModel):
    task_instance_id: int
    area_key: TrainingAreaKey
    area_title: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=80)
    today_goal: str = Field(min_length=1, max_length=180)
    training_scene: str = Field(min_length=1, max_length=120)
    schedule_hint: str = Field(min_length=1, max_length=120)
    steps: list[str] = Field(min_length=3, max_length=5)
    parent_script: str = Field(min_length=1, max_length=180)
    duration_minutes: int = Field(ge=3, le=30)
    difficulty: Literal["starter", "build", "advance"]
    materials: list[str] = Field(default_factory=list, max_length=5)
    fallback_plan: str = Field(min_length=1, max_length=180)
    coaching_tip: str = Field(min_length=1, max_length=180)
    coordination_mode: Literal["ready", "lighter", "pause"] = "ready"
    why_today: str = Field(default="", max_length=180)
    status: TrainingTaskStatus
    reminder_status: TrainingReminderStatus
    reminder_at: datetime_type | None = None
    feedback_ready: bool = True
    highlight: bool = False


class TrainingTrendPoint(StrictModel):
    label: str = Field(min_length=1, max_length=16)
    completed_count: int = Field(ge=0)
    task_count: int = Field(ge=0)
    completion_rate: int = Field(ge=0, le=100)


class TrainingMethodInsight(StrictModel):
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=180)
    evidence_count: int = Field(ge=0)
    effectiveness_score: int = Field(ge=0, le=100)


class TrainingProgressOverview(StrictModel):
    streak_days: int = Field(ge=0)
    weekly_completion_count: int = Field(ge=0)
    seven_day_completion_rate: int = Field(ge=0, le=100)
    recent_trend: list[TrainingTrendPoint] = Field(default_factory=list, max_length=7)
    best_method_summary: str = Field(min_length=1, max_length=180)


class TrainingAdjustmentLogRead(StrictModel):
    adjustment_id: int
    area_key: TrainingAreaKey
    title: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=240)
    trigger: str = Field(min_length=1, max_length=64)
    before_state: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime_type


class TrainingDashboardSummary(StrictModel):
    week_completed_count: int = Field(ge=0)
    priority_domain_count: int = Field(ge=0, le=3)
    streak_days: int = Field(ge=0)
    current_load_level: TrainingLoadLevel
    readiness_status: Literal["ready", "lighter", "pause"] = "ready"
    readiness_reason: str = Field(min_length=1, max_length=240)
    recommended_action: str = Field(min_length=1, max_length=180)
    summary_text: str = Field(min_length=1, max_length=240)


class TrainingDomainProgress(StrictModel):
    current_stage: TrainingSkillStage
    current_difficulty: Literal["starter", "build", "advance"]
    weekly_sessions_count: int = Field(ge=0)
    total_completed_count: int = Field(ge=0)
    recent_completion_rate: int = Field(ge=0, le=100)
    recent_effective_rate: int = Field(ge=0, le=100)


class TrainingDomainDetailResponse(StrictModel):
    family_id: int
    area_key: TrainingAreaKey
    title: str = Field(min_length=1, max_length=64)
    current_stage: TrainingSkillStage
    current_difficulty: Literal["starter", "build", "advance"]
    importance_summary: str = Field(min_length=1, max_length=180)
    related_daily_challenges: list[str] = Field(min_length=2, max_length=4)
    reason_for_priority: list[str] = Field(min_length=2, max_length=4)
    current_risks: list[str] = Field(min_length=1, max_length=3)
    short_term_goal: TrainingGoal
    medium_term_goal: TrainingGoal
    training_principles: list[str] = Field(min_length=3, max_length=5)
    suggested_scenarios: list[str] = Field(min_length=2, max_length=4)
    parent_steps: list[str] = Field(min_length=3, max_length=5)
    script_examples: list[str] = Field(min_length=2, max_length=3)
    fallback_options: list[str] = Field(min_length=2, max_length=3)
    cautions: list[str] = Field(min_length=2, max_length=4)
    progress: TrainingDomainProgress
    recent_feedbacks: list[TrainingFeedbackRead] = Field(default_factory=list, max_length=6)
    adjustment_logs: list[TrainingAdjustmentLogRead] = Field(default_factory=list, max_length=6)


class TrainingDashboardResponse(StrictModel):
    family_id: int
    summary: TrainingDashboardSummary
    priority_domains: list[TrainingPriorityDomainCard] = Field(min_length=1, max_length=3)
    today_tasks: list[DailyTrainingTaskRead] = Field(default_factory=list, max_length=3)
    progress_overview: TrainingProgressOverview
    method_insights: list[TrainingMethodInsight] = Field(default_factory=list, max_length=3)
    recent_adjustments: list[TrainingAdjustmentLogRead] = Field(default_factory=list, max_length=5)
    safety_alert: str | None = None


class TrainingPlanGenerateRequest(StrictModel):
    family_id: int
    extra_context: str = Field(default="", max_length=500)


class TrainingTaskFeedbackRequest(StrictModel):
    family_id: int
    date: date_type | None = None
    task_instance_id: int
    completion_status: TrainingCompletionStatus
    child_response: TrainingChildResponse
    helpfulness: TrainingHelpfulness
    obstacle_tag: TrainingObstacleTag = "none"
    safety_pause: bool = False
    notes: str = Field(default="", max_length=500)


class TrainingTaskFeedbackResponse(StrictModel):
    feedback_id: int
    adjustment_summary: str
    safety_alert: str | None = None
    dashboard: TrainingDashboardResponse


class TrainingReminderRequest(StrictModel):
    family_id: int
    task_instance_id: int
    remind_at: datetime_type | None = None


class TrainingReminderResponse(StrictModel):
    task_instance_id: int
    reminder_status: TrainingReminderStatus
    remind_at: datetime_type | None = None
    dashboard: TrainingDashboardResponse


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
    card_ids: list[str] = Field(default_factory=list)
    outcome_score: int = Field(ge=-2, le=2)
    child_state_after: ReviewChildStateAfter = "partly_settled"
    caregiver_state_after: ReviewCaregiverStateAfter = "same"
    recommendation: StrategyDecision = "continue"
    response_action: str = Field(default="", max_length=300)
    notes: str = Field(default="", max_length=500)
    followup_action: str = Field(default="", max_length=180)


class ReviewResponse(StrictModel):
    review_id: int
    incident_id: int
    updated_weights: dict[str, float]


class ReplayStep(StrictModel):
    label: str = Field(min_length=1, max_length=16)
    value: str = Field(min_length=1, max_length=200)


class ReplayResponse(StrictModel):
    incident_id: int
    scenario: str
    happened_at: datetime_type | None = None
    recommendation: StrategyDecision
    strategy_titles: list[str] = Field(default_factory=list, max_length=3)
    timeline: list[ReplayStep] = Field(min_length=4, max_length=4)
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
    success_rate: int = Field(ge=0, le=100)
    fit_rate: int = Field(ge=0, le=100)
    applicability: Literal["high", "medium", "low"]
    recommendation: StrategyDecision
    why_ranked: list[str] = Field(min_length=2, max_length=3)


class ActionSuggestion(StrictModel):
    target_key: str
    title: str
    summary: str
    rationale: str
    recommendation: StrategyDecision = "continue"


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


class TrendDeltaItem(StrictModel):
    title: str
    summary: str
    current_value: float = Field(ge=0)
    previous_value: float = Field(ge=0)
    direction: Literal["up", "down", "flat"]
    unit: str


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
    week_over_week: list[TrendDeltaItem] = Field(default_factory=list, max_length=3)
    task_completion_score: int = Field(ge=0, le=100)
    task_summary: str
    completed_tasks: list[TaskEffectItem] = Field(default_factory=list)
    partial_tasks: list[TaskEffectItem] = Field(default_factory=list)
    retry_tasks: list[TaskEffectItem] = Field(default_factory=list)
    caregiver_summary: str
    caregiver_stress_avg: float = Field(ge=0, le=10)
    caregiver_stress_peak: float = Field(ge=0, le=10)
    caregiver_sleep_avg: float = Field(ge=0, le=10)
    strategy_ranking_summary: str
    strategy_top3: list[StrategyInsight] = Field(default_factory=list)
    replay_items: list[ReplayResponse] = Field(default_factory=list, max_length=3)
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
    strategy_ranking_summary: str
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


class DecisionTraceRead(StrictModel):
    trace_id: int
    family_id: int | None = None
    chain: Literal["plan48h", "script", "friction_support"]
    final_status: Literal["success", "blocked", "fallback"]
    graph_version: str = "v1"
    stage_order: list[str] = Field(default_factory=list)
    stage_runs: list[DecisionGraphStageRun] = Field(default_factory=list)
    entry_signal_ids: list[int] = Field(default_factory=list)
    request_context: dict[str, Any] = Field(default_factory=dict)
    signal_result: dict[str, Any] = Field(default_factory=dict)
    retrieval_bundle: RetrievalEvidenceBundle | None = None
    candidate_output: dict[str, Any] = Field(default_factory=dict)
    safety_review: CriticReview | None = None
    evidence_review: CriticReview | None = None
    provider_name: str | None = None
    embedding_model: str | None = None
    reranker_model: str | None = None
    corpus_version: str | None = None
    retrieval_stage_timings: dict[str, Any] = Field(default_factory=dict)
    fallback_reason: str | None = None
    final_reason: str | None = None
    plan_tree: list[TaskNode] = Field(default_factory=list)
    execution_state: ExecutionState | None = None
    revision_no: int | None = None
    parent_trace_id: int | None = None
    replan_reason: str | None = None
    created_at: datetime_type


class FamilyPolicyWeightRead(StrictModel):
    family_id: int
    target_kind: Literal[
        "card",
        "chunk",
        "scenario",
        "method",
        "timing",
        "handoff_pattern",
        "emotion_pattern",
        "overload_trigger",
        "successful_adjustment",
        "failed_adjustment",
    ]
    target_key: str
    weight: float
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    recent_outcome_avg: float
    usage_count: int = Field(ge=0)
    last_feedback_at: datetime_type | None = None


class PolicyMemoryItemRead(StrictModel):
    target_kind: Literal[
        "card",
        "evidence_unit",
        "scenario",
        "method",
        "timing",
        "handoff_pattern",
        "emotion_pattern",
        "overload_trigger",
        "successful_adjustment",
        "failed_adjustment",
    ]
    target_key: str
    global_weight: float
    segment_weight: float
    family_weight: float
    effective_weight: float
    source_evidence_count: int = Field(default=0, ge=0)
    recent_effect_window: str = "lifetime"
    top_supporting_chunk_ids: list[str] = Field(default_factory=list, max_length=3)


class PolicyMemorySnapshotRead(StrictModel):
    family_id: int
    segment_key: str
    generated_at: datetime_type
    items: list[PolicyMemoryItemRead] = Field(default_factory=list)


class PolicyMemoryDiffRead(StrictModel):
    family_id: int
    segment_key: str
    strongest_positive: list[PolicyMemoryItemRead] = Field(default_factory=list, max_length=5)
    strongest_negative: list[PolicyMemoryItemRead] = Field(default_factory=list, max_length=5)


class BenchmarkMetricRead(StrictModel):
    category: Literal["retrieval", "orchestration", "policy_learning", "multimodal", "ir_eval"]
    name: str
    value: float = Field(ge=0, le=1)
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class BenchmarkRunRead(StrictModel):
    run_id: int
    generated_at: datetime_type
    summary: str
    metrics: list[BenchmarkMetricRead] = Field(default_factory=list)


class KnowledgeIngestionRequest(StrictModel):
    family_id: int | None = None
    source_type: Literal["strategy_card", "review_summary", "expert_rule", "multimodal_summary", "policy_note"]
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    scope: Literal["global", "segment", "family"] = "global"
    scope_key: str = Field(default="", max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeIngestionResponse(StrictModel):
    document_id: int
    chunk_ids: list[int] = Field(default_factory=list)
    source_type: str
    scope: str
    version: str


class KnowledgeReindexResponse(StrictModel):
    corpus_version: str
    processed_chunks: int = Field(ge=0)
    embedding_provider: str
    embedding_model: str
    job_id: str | None = None
    job_status: Literal["accepted", "running", "completed", "failed"] = "completed"
    message: str = ""


class KnowledgeReindexJobRead(StrictModel):
    job_id: str
    job_status: Literal["accepted", "running", "completed", "failed"]
    corpus_version: str
    processed_chunks: int = Field(ge=0)
    embedding_provider: str = ""
    embedding_model: str = ""
    message: str = ""


class RetrievalTraceRead(StrictModel):
    trace: DecisionTraceRead
    retrieval_run_id: int | None = None
    selected_sources: list[RetrievalSelectedSource] = Field(default_factory=list)
    hard_filtered_reasons: list[str] = Field(default_factory=list)
    feature_attribution: list[RetrievalFeatureAttribution] = Field(default_factory=list)
    candidates: list[RetrievalTraceCandidateRead] = Field(default_factory=list)


class V2GeneratePlanRequest(Plan48hGenerateRequest):
    ingestion_ids: list[int] = Field(default_factory=list, max_length=4)


class V2GenerateScriptRequest(ScriptGenerateRequest):
    ingestion_ids: list[int] = Field(default_factory=list, max_length=4)


class V2GenerateFrictionSupportRequest(FrictionSupportGenerateRequest):
    ingestion_ids: list[int] = Field(default_factory=list, max_length=4)


class V2PlanGenerateResponse(StrictModel):
    blocked: bool = False
    plan_id: int | None = None
    risk: SignalOutput | None = None
    plan: Plan48hResponse | None = None
    safety_block: "SafetyBlockResponse | None" = None
    trace_id: int
    stage_summaries: list[DecisionGraphStageRun] = Field(default_factory=list)
    fallback_summary: str | None = None
    insufficient_evidence: bool = False
    evidence_bundle: RetrievalEvidenceBundle | None = None


class V2ScriptGenerateResponse(StrictModel):
    blocked: bool = False
    script: ScriptResponse | None = None
    safety_block: "SafetyBlockResponse | None" = None
    trace_id: int
    stage_summaries: list[DecisionGraphStageRun] = Field(default_factory=list)
    fallback_summary: str | None = None
    insufficient_evidence: bool = False
    evidence_bundle: RetrievalEvidenceBundle | None = None


class V2FrictionSupportGenerateResponse(StrictModel):
    blocked: bool = False
    incident_id: int | None = None
    risk: SignalOutput | None = None
    support: FrictionSupportPlan | None = None
    safety_block: "SafetyBlockResponse | None" = None
    trace_id: int
    stage_summaries: list[DecisionGraphStageRun] = Field(default_factory=list)
    fallback_summary: str | None = None
    insufficient_evidence: bool = False
    evidence_bundle: RetrievalEvidenceBundle | None = None


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
V2PlanGenerateResponse.model_rebuild()
V2ScriptGenerateResponse.model_rebuild()
V2FrictionSupportGenerateResponse.model_rebuild()
