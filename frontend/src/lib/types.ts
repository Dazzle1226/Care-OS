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
  child_sleep_quality: number | null;
  sleep_issues: string[];
  meltdown_count: number;
  child_mood_state: 'stable' | 'sensitive' | 'anxious' | 'low_energy' | 'irritable';
  physical_discomforts: string[];
  aggressive_behaviors: string[];
  negative_emotions: string[];
  transition_difficulty: number | null;
  sensory_overload_level: 'none' | 'light' | 'medium' | 'heavy';
  caregiver_stress: number;
  caregiver_sleep_quality: number;
  support_available: 'none' | 'one' | 'two_plus';
  today_activities: string[];
  today_learning_tasks: string[];
}

export interface TodayReminderItem {
  eyebrow: string;
  title: string;
  body: string;
}

export interface DailyActionPlan {
  headline: string;
  summary: string;
  reminders: TodayReminderItem[];
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

export interface SafetyBlockResponse {
  severity: 'high_risk' | 'conflict' | 'quality';
  block_reason: string;
  safe_next_steps: string[];
  do_not_do: string[];
  say_this_now: string;
  exit_plan: string[];
  help_now: string[];
  low_stim_recommended: boolean;
  conflict_explanation?: string | null;
  alternatives: string[];
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

export interface FrictionLowStimMode {
  active: boolean;
  headline: string;
  actions: string[];
}

export interface FrictionCrisisCard {
  title: string;
  badges: string[];
  first_do: string[];
  donts: string[];
  say_this: string[];
  exit_plan: string[];
  help_now: string[];
}

export interface FrictionRespiteSuggestion {
  title: string;
  summary: string;
  duration_minutes: number;
  support_plan: string;
}

export interface FrictionSupportPlan {
  preset_label: string;
  headline: string;
  situation_summary: string;
  child_signals: string[];
  caregiver_signals: string[];
  action_plan: FrictionSupportStep[];
  donts: string[];
  say_this: string[];
  voice_guidance: string[];
  exit_plan: string[];
  low_stim_mode: FrictionLowStimMode;
  crisis_card: FrictionCrisisCard;
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
  | 'daily_living'
  | 'waiting_tolerance'
  | 'task_initiation'
  | 'bedtime_routine'
  | 'simple_compliance';

export type TrainingCompletionStatus = 'done' | 'partial' | 'missed';
export type TrainingChildResponse = 'engaged' | 'accepted' | 'resistant' | 'overloaded';
export type TrainingDifficultyRating = 'too_easy' | 'just_right' | 'too_hard';
export type TrainingSkillStage = 'stabilize' | 'practice' | 'generalize' | 'maintain';
export type TrainingLoadLevel = 'light' | 'standard' | 'adaptive';
export type TrainingTaskStatus = 'pending' | 'scheduled' | 'done' | 'partial' | 'missed';
export type TrainingHelpfulness = 'helpful' | 'neutral' | 'not_helpful';
export type TrainingObstacleTag =
  | 'none'
  | 'too_hard'
  | 'refused'
  | 'parent_overloaded'
  | 'wrong_timing'
  | 'sensory_overload'
  | 'unclear_steps';
export type TrainingReminderStatus = 'none' | 'scheduled' | 'due';

export interface TrainingGoal {
  title: string;
  target: string;
  success_marker: string;
}

export interface TrainingFeedbackRecord {
  feedback_id: number;
  date: string;
  task_instance_id?: number | null;
  task_key: string;
  task_title: string;
  area_key: TrainingAreaKey;
  completion_status: TrainingCompletionStatus;
  child_response: TrainingChildResponse;
  difficulty_rating: TrainingDifficultyRating;
  helpfulness: TrainingHelpfulness;
  obstacle_tag: TrainingObstacleTag;
  safety_pause: boolean;
  effect_score: number;
  parent_confidence: number;
  notes: string;
}

export interface TrainingPriorityDomainCard {
  area_key: TrainingAreaKey;
  title: string;
  priority_label: 'high' | 'medium';
  priority_score: number;
  recommended_reason: string;
  current_stage: TrainingSkillStage;
  current_difficulty: 'starter' | 'build' | 'advance';
  weekly_sessions_count: number;
  has_today_task: boolean;
  current_status: string;
  improvement_value: string;
}

export interface DailyTrainingTask {
  task_instance_id: number;
  area_key: TrainingAreaKey;
  area_title: string;
  title: string;
  today_goal: string;
  training_scene: string;
  schedule_hint: string;
  steps: string[];
  parent_script: string;
  duration_minutes: number;
  difficulty: 'starter' | 'build' | 'advance';
  materials: string[];
  fallback_plan: string;
  coaching_tip: string;
  status: TrainingTaskStatus;
  reminder_status: TrainingReminderStatus;
  reminder_at?: string | null;
  feedback_ready: boolean;
  highlight: boolean;
}

export interface TrainingTrendPoint {
  label: string;
  completed_count: number;
  task_count: number;
  completion_rate: number;
}

export interface TrainingMethodInsight {
  title: string;
  summary: string;
  evidence_count: number;
  effectiveness_score: number;
}

export interface TrainingProgressOverview {
  streak_days: number;
  weekly_completion_count: number;
  seven_day_completion_rate: number;
  recent_trend: TrainingTrendPoint[];
  best_method_summary: string;
}

export interface TrainingAdjustmentLogItem {
  adjustment_id: number;
  area_key: TrainingAreaKey;
  title: string;
  summary: string;
  trigger: string;
  before_state: Record<string, unknown>;
  after_state: Record<string, unknown>;
  created_at: string;
}

export interface TrainingDashboardSummary {
  week_completed_count: number;
  priority_domain_count: number;
  streak_days: number;
  current_load_level: TrainingLoadLevel;
  summary_text: string;
}

export interface TrainingDashboard {
  family_id: number;
  summary: TrainingDashboardSummary;
  priority_domains: TrainingPriorityDomainCard[];
  today_tasks: DailyTrainingTask[];
  progress_overview: TrainingProgressOverview;
  method_insights: TrainingMethodInsight[];
  recent_adjustments: TrainingAdjustmentLogItem[];
  safety_alert?: string | null;
}

export interface TrainingDomainProgress {
  current_stage: TrainingSkillStage;
  current_difficulty: 'starter' | 'build' | 'advance';
  weekly_sessions_count: number;
  total_completed_count: number;
  recent_completion_rate: number;
  recent_effective_rate: number;
}

export interface TrainingDomainDetail {
  family_id: number;
  area_key: TrainingAreaKey;
  title: string;
  current_stage: TrainingSkillStage;
  current_difficulty: 'starter' | 'build' | 'advance';
  importance_summary: string;
  related_daily_challenges: string[];
  reason_for_priority: string[];
  current_risks: string[];
  short_term_goal: TrainingGoal;
  medium_term_goal: TrainingGoal;
  training_principles: string[];
  suggested_scenarios: string[];
  parent_steps: string[];
  script_examples: string[];
  fallback_options: string[];
  cautions: string[];
  progress: TrainingDomainProgress;
  recent_feedbacks: TrainingFeedbackRecord[];
  adjustment_logs: TrainingAdjustmentLogItem[];
}

export interface TrainingFeedbackResponse {
  feedback_id: number;
  adjustment_summary: string;
  safety_alert?: string | null;
  dashboard: TrainingDashboard;
}

export interface TrainingReminderResponse {
  task_instance_id: number;
  reminder_status: TrainingReminderStatus;
  remind_at?: string | null;
  dashboard: TrainingDashboard;
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
  core_difficulties?: string[];
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
  supporter_availability?: string[];
  supporter_independent_care?: 'can_alone' | 'needs_handoff' | 'cannot_alone' | 'unknown';
  major_incident_notes?: string;
  emergency_contacts?: string[];
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
  icon: 'support' | 'handoff';
  title: string;
  summary: string;
  one_liner: string;
  quick_actions: string[];
  sections: OnboardingSupportCardSection[];
}

export interface OnboardingSupportCardSection {
  key: string;
  title: string;
  items: string[];
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

export interface ReplayStep {
  label: string;
  value: string;
}

export interface ReplayItem {
  incident_id: number;
  scenario: string;
  happened_at?: string | null;
  recommendation: 'continue' | 'pause' | 'replace';
  strategy_titles: string[];
  timeline: ReplayStep[];
  next_improvement: string;
}

export interface StrategyInsight {
  target_key: string;
  title: string;
  summary: string;
  evidence_count: number;
  avg_outcome: number;
  success_rate: number;
  fit_rate: number;
  applicability: 'high' | 'medium' | 'low';
  recommendation: 'continue' | 'pause' | 'replace';
  why_ranked: string[];
}

export interface ActionSuggestion {
  target_key: string;
  title: string;
  summary: string;
  rationale: string;
  recommendation: 'continue' | 'pause' | 'replace';
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

export interface TrendDeltaItem {
  title: string;
  summary: string;
  current_value: number;
  previous_value: number;
  direction: 'up' | 'down' | 'flat';
  unit: string;
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
  week_over_week: TrendDeltaItem[];
  task_completion_score: number;
  task_summary: string;
  completed_tasks: TaskEffectItem[];
  partial_tasks: TaskEffectItem[];
  retry_tasks: TaskEffectItem[];
  caregiver_summary: string;
  caregiver_stress_avg: number;
  caregiver_stress_peak: number;
  caregiver_sleep_avg: number;
  strategy_ranking_summary: string;
  strategy_top3: StrategyInsight[];
  replay_items: ReplayItem[];
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
  strategy_ranking_summary: string;
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
