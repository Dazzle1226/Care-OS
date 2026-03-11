export type SensoryLevel = 'none' | 'light' | 'medium' | 'heavy';
export type SupportLevel = 'none' | 'one' | 'two_plus';
export type MoodState = 'stable' | 'sensitive' | 'anxious' | 'low_energy' | 'irritable';

export interface CheckinFormPayload {
  date: string;
  child_sleep_hours: number;
  child_sleep_quality: number | null;
  sleep_issues: string[];
  sensory_overload_level: SensoryLevel;
  meltdown_count: number;
  child_mood_state: MoodState;
  physical_discomforts: string[];
  aggressive_behaviors: string[];
  negative_emotions: string[];
  transition_difficulty: number | null;
  caregiver_stress: number;
  support_available: SupportLevel;
  caregiver_sleep_quality: number;
  today_activities: string[];
  today_learning_tasks: string[];
}

export type CheckinFormValues = Omit<CheckinFormPayload, 'date'>;

export const defaultCheckinFormValues: CheckinFormValues = {
  child_sleep_hours: 8,
  child_sleep_quality: null,
  sleep_issues: [],
  sensory_overload_level: 'light',
  meltdown_count: 0,
  child_mood_state: 'stable',
  physical_discomforts: [],
  aggressive_behaviors: [],
  negative_emotions: [],
  transition_difficulty: null,
  caregiver_stress: 4,
  support_available: 'one',
  caregiver_sleep_quality: 6,
  today_activities: [],
  today_learning_tasks: []
};

function ensureArray(value: string[] | undefined) {
  return Array.isArray(value) ? value : [];
}

export function buildCheckinPayload(
  input: Partial<CheckinFormPayload> & Pick<CheckinFormPayload, 'date'>
): CheckinFormPayload {
  return {
    ...defaultCheckinFormValues,
    ...input,
    date: input.date,
    sleep_issues: ensureArray(input.sleep_issues),
    physical_discomforts: ensureArray(input.physical_discomforts),
    aggressive_behaviors: ensureArray(input.aggressive_behaviors),
    negative_emotions: ensureArray(input.negative_emotions),
    today_activities: ensureArray(input.today_activities),
    today_learning_tasks: ensureArray(input.today_learning_tasks)
  };
}
