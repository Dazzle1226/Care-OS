export type RiskLevel = 'green' | 'yellow' | 'red';

export interface SignalOutput {
  risk_level: RiskLevel;
  reasons: string[];
  trigger_48h: boolean;
  confidence: number;
}

export interface CheckinRecord {
  checkin_id: number;
  date: string;
  child_sleep_hours: number;
  child_sleep_quality: number;
  sleep_issues: string[];
  meltdown_count: number;
  child_mood_state: 'stable' | 'sensitive' | 'anxious' | 'low_energy' | 'irritable';
  physical_discomforts: string[];
  aggressive_behaviors: string[];
  negative_emotions: string[];
  transition_difficulty: number;
  sensory_overload_level: 'none' | 'light' | 'medium' | 'heavy';
  caregiver_stress: number;
  caregiver_sleep_quality: number;
  support_available: 'none' | 'one' | 'two_plus';
  today_activities: string[];
  today_learning_tasks: string[];
}

export interface DailyActionPlan {
  headline: string;
  summary: string;
  three_step_action: string[];
  parent_phrase: string;
  meltdown_fallback: string[];
  respite_suggestion: string;
  plan_overview: string[];
}

export interface CheckinResponse {
  checkin_id: number;
  checkin: CheckinRecord;
  risk: SignalOutput;
  today_one_thing: string;
  action_plan: DailyActionPlan;
}

export interface CheckinTodayStatus {
  family_id: number;
  date: string;
  needs_checkin: boolean;
  checkin?: CheckinRecord;
  risk?: SignalOutput;
  today_one_thing?: string;
  action_plan?: DailyActionPlan;
}

export interface PlanMessage {
  target: 'teacher' | 'family' | 'supporter';
  text: string;
}

export interface RespiteSlot {
  duration_minutes: 15 | 30 | 60;
  resource: string;
  handoff_card: Record<string, unknown>;
}

export interface PlanActionItem {
  card_id: string;
  step: string;
  script: string;
  donts: string[];
  escalate_when: string[];
}

export interface Plan48hResponse {
  today_cut_list: string[];
  priority_scenarios: string[];
  respite_slots: RespiteSlot[];
  messages: PlanMessage[];
  exit_card_3steps: string[];
  tomorrow_plan: string[];
  action_steps: PlanActionItem[];
  citations: string[];
  safety_flags: string[];
}

export interface SafetyBlockResponse {
  block_reason: string;
  environment_checklist: string[];
  emergency_guidance: string[];
  emergency_contact_template: string;
}

export type ChildEmotionState = 'calm' | 'fragile' | 'escalating' | 'meltdown_risk';

export interface MicroRespiteOption {
  option_id: string;
  title: string;
  summary: string;
  fit_reason: string;
  duration_minutes: number;
  child_focus: string;
  parent_focus: string;
  setup_steps: string[];
  instructions: string[];
  safety_notes: string[];
  support_plan: string;
  source_card_ids: string[];
  low_stimulation_only: boolean;
  requires_manual_review: boolean;
}

export interface MicroRespitePlan {
  headline: string;
  context_summary: string;
  low_stimulation_only: boolean;
  safety_notes: string[];
  options: MicroRespiteOption[];
  feedback_prompt: string;
}

export interface MicroRespiteGenerateResponse {
  blocked: boolean;
  risk?: SignalOutput;
  plan?: MicroRespitePlan;
  safety_block?: SafetyBlockResponse;
}

export interface MicroRespiteFeedbackResponse {
  review_id: number;
  incident_id: number;
  outcome_score: number;
  updated_weights: Record<string, number>;
  next_hint: string;
}

export interface PlanGenerateResponse {
  blocked: boolean;
  plan_id?: number;
  risk?: SignalOutput;
  plan?: Plan48hResponse;
  safety_block?: SafetyBlockResponse;
}

export interface ScriptResponse {
  steps: string[];
  script_line: string;
  donts: string[];
  exit_plan: string[];
  citations: string[];
}

export interface ScriptGenerateResponse {
  blocked: boolean;
  script?: ScriptResponse;
  safety_block?: SafetyBlockResponse;
}

export type FrictionScenario = 'transition' | 'bedtime' | 'homework' | 'outing' | 'meltdown';
export type FrictionChildState =
  | 'emotional_wave'
  | 'sensory_overload'
  | 'conflict'
  | 'meltdown'
  | 'transition_block';

export interface FrictionSupportStep {
  title: string;
  action: string;
  parent_script: string;
  why_it_fits: string;
}

export interface FrictionRespiteSuggestion {
  title: string;
  summary: string;
  duration_minutes: number;
  support_plan: string;
}

export interface FrictionSupportPlan {
  headline: string;
  situation_summary: string;
  child_signals: string[];
  caregiver_signals: string[];
  action_plan: FrictionSupportStep[];
  voice_guidance: string[];
  exit_plan: string[];
  respite_suggestion: FrictionRespiteSuggestion;
  personalized_strategies: string[];
  school_message: string;
  feedback_prompt: string;
  citations: string[];
  source_card_ids: string[];
}

export interface FrictionSupportGenerateResponse {
  blocked: boolean;
  incident_id?: number;
  risk?: SignalOutput;
  support?: FrictionSupportPlan;
  safety_block?: SafetyBlockResponse;
}

export interface FrictionSupportFeedbackResponse {
  review_id: number;
  incident_id: number;
  outcome_score: number;
  updated_weights: Record<string, number>;
  next_adjustment: string;
}

export type TrainingAreaKey =
  | 'emotion_regulation'
  | 'communication'
  | 'social_interaction'
  | 'sensory_regulation'
  | 'transition_flexibility'
  | 'daily_living';

export type TrainingCompletionStatus = 'done' | 'partial' | 'missed';
export type TrainingChildResponse = 'engaged' | 'accepted' | 'resistant' | 'overloaded';
export type TrainingDifficultyRating = 'too_easy' | 'just_right' | 'too_hard';

export interface TrainingGoal {
  title: string;
  target: string;
  success_marker: string;
}

export interface TrainingFocusArea {
  area_key: TrainingAreaKey;
  title: string;
  priority_score: number;
  urgency: 'urgent' | 'high' | 'watch';
  why_now: string[];
  profile_signals: string[];
  recent_signals: string[];
  long_term_value: string;
}

export interface TrainingTask {
  task_key: string;
  title: string;
  area_key: TrainingAreaKey;
  duration_minutes: number;
  schedule_hint: string;
  objective: string;
  materials: string[];
  steps: string[];
  parent_script: string;
  coaching_tip: string;
  success_signals: string[];
  fallback_plan: string;
  difficulty: 'starter' | 'build' | 'advance';
}

export interface TrainingAdjustment {
  title: string;
  suggestion: string;
  reason: string;
}

export interface TrainingProgressItem {
  label: string;
  value: number;
  target: number;
  summary: string;
}

export interface TrainingFeedbackRecord {
  feedback_id: number;
  date: string;
  task_key: string;
  task_title: string;
  area_key: TrainingAreaKey;
  completion_status: TrainingCompletionStatus;
  child_response: TrainingChildResponse;
  difficulty_rating: TrainingDifficultyRating;
  effect_score: number;
  parent_confidence: number;
  notes: string;
}

export interface TrainingPlan {
  family_id: number;
  child_summary: string;
  plan_summary: string;
  primary_need: string;
  load_level: 'light' | 'standard' | 'adaptive';
  focus_areas: TrainingFocusArea[];
  short_term_goals: TrainingGoal[];
  long_term_goals: TrainingGoal[];
  daily_tasks: TrainingTask[];
  guidance: string[];
  adjustments: TrainingAdjustment[];
  progress: TrainingProgressItem[];
  recent_feedback_summary: string;
  recent_feedbacks: TrainingFeedbackRecord[];
}

export interface TrainingFeedbackResponse {
  feedback_id: number;
  next_adjustment: string;
  progress_summary: string;
  plan: TrainingPlan;
}

export interface FamilyRead {
  family_id: number;
  name: string;
  timezone: string;
  owner_user_id?: number;
}

export type OnboardingGender = 'male' | 'female' | 'other';
export type OnboardingCaregiver = 'parents' | 'grandparents' | 'relative' | 'other';
export type OnboardingDiagnosis = 'asd' | 'none' | 'under_assessment' | 'other';
export type OnboardingCommunication = 'none' | 'single_word' | 'short_sentence' | 'fluent';
export type OnboardingSchoolType = 'mainstream' | 'special' | 'home' | 'other';

export interface OnboardingSetupPayload {
  use_sample?: boolean;
  family_name?: string;
  timezone?: string;
  child_name?: string;
  child_age?: number;
  child_gender?: OnboardingGender;
  primary_caregiver?: OnboardingCaregiver;
  diagnosis_status?: OnboardingDiagnosis;
  diagnosis_notes?: string;
  communication_level?: OnboardingCommunication;
  coexisting_conditions?: string[];
  family_members?: string[];
  interests?: string[];
  likes?: string[];
  dislikes?: string[];
  triggers?: string[];
  sensory_flags?: string[];
  soothing_methods?: string[];
  taboo_behaviors?: string;
  sleep_challenges?: string[];
  food_preferences?: string[];
  allergies?: string[];
  medical_needs?: string[];
  medications?: string[];
  health_conditions?: string[];
  behavior_patterns?: string[];
  behavior_risks?: string[];
  emotion_patterns?: string[];
  learning_needs?: string[];
  school_type?: OnboardingSchoolType;
  social_training?: string[];
  school_notes?: string;
  high_friction_scenarios?: string[];
  parent_schedule?: string[];
  parent_stressors?: string[];
  parent_support_actions?: string[];
  parent_emotional_supports?: string[];
  available_supporters?: string[];
}

export interface ChildProfileRead {
  child_id: number;
  family_id: number;
  age_band: string;
  language_level: string;
  sensory_flags: string[];
  triggers: string[];
  soothing_methods: string[];
  donts: string[];
  school_context: Record<string, unknown>;
  high_friction_scenarios: string[];
}

export interface OnboardingSnapshot {
  child_overview: string[];
  preference_summary: string[];
  health_summary: string[];
  behavior_summary: string[];
  learning_summary: string[];
  social_summary: string[];
  trigger_summary: string[];
  sensory_summary: string[];
  soothing_summary: string[];
  caregiver_pressure: string[];
  supporter_summary: string[];
  parent_support_summary: string[];
  resource_summary: string[];
  recommended_focus: string;
}

export interface OnboardingSupportCard {
  card_id: string;
  icon: 'child' | 'parent' | 'team';
  title: string;
  summary: string;
  bullets: string[];
}

export interface OnboardingSummary {
  family: FamilyRead;
  profile: ChildProfileRead;
  snapshot: OnboardingSnapshot;
  support_cards: OnboardingSupportCard[];
}

export type ReportTargetKind = 'strategy' | 'action';
export type FeedbackValue = 'effective' | 'not_effective' | 'continue' | 'adjust';

export interface ReportMetricPoint {
  label: string;
  value: number;
}

export interface TaskEffectItem {
  title: string;
  summary: string;
  status: 'done' | 'partial' | 'retry';
  outcome_score: number;
}

export interface StrategyInsight {
  target_key: string;
  title: string;
  summary: string;
  evidence_count: number;
  avg_outcome: number;
}

export interface ActionSuggestion {
  target_key: string;
  title: string;
  summary: string;
  rationale: string;
}

export interface ReportFeedbackSummary {
  effective_count: number;
  not_effective_count: number;
  continue_count: number;
  adjust_count: number;
}

export interface ReportFeedbackState {
  target_kind: ReportTargetKind;
  target_key: string;
  target_label: string;
  feedback: FeedbackValue;
}

export interface WeeklyReport {
  family_id: number;
  week_start: string;
  week_end: string;
  trigger_top3: string[];
  trigger_summary: string;
  child_emotion_summary: string;
  highest_risk_scenario: string;
  stress_trend: ReportMetricPoint[];
  meltdown_trend: ReportMetricPoint[];
  task_completion_score: number;
  task_summary: string;
  completed_tasks: TaskEffectItem[];
  partial_tasks: TaskEffectItem[];
  retry_tasks: TaskEffectItem[];
  caregiver_summary: string;
  caregiver_stress_avg: number;
  caregiver_stress_peak: number;
  caregiver_sleep_avg: number;
  strategy_top3: StrategyInsight[];
  next_actions: ActionSuggestion[];
  one_thing_next_week: string;
  feedback_summary: ReportFeedbackSummary;
  feedback_states: ReportFeedbackState[];
  export_count: number;
}

export interface MonthlyTrendItem {
  title: string;
  summary: string;
  current_value: number;
  previous_value: number;
  direction: 'up' | 'down' | 'flat';
  unit: string;
}

export interface MonthlyHistoryPoint {
  label: string;
  avg_stress: number;
  conflict_count: number;
  task_completion_rate: number;
}

export interface MonthlyReport {
  family_id: number;
  month_start: string;
  month_end: string;
  overview_summary: string;
  stress_change_summary: string;
  conflict_change_summary: string;
  task_completion_summary: string;
  long_term_trends: MonthlyTrendItem[];
  successful_methods: StrategyInsight[];
  next_month_plan: ActionSuggestion[];
  history: MonthlyHistoryPoint[];
  feedback_summary: ReportFeedbackSummary;
  feedback_states: ReportFeedbackState[];
}

export interface ReportFeedbackResponse {
  feedback_id: number;
  family_id: number;
  period_type: 'weekly' | 'monthly';
  period_start: string;
  target_kind: ReportTargetKind;
  target_key: string;
  feedback: FeedbackValue;
  summary: ReportFeedbackSummary;
}
