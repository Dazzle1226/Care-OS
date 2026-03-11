import type {
  DailyTrainingTask,
  TrainingCompletionStatus,
  TrainingDomainDetail,
  TrainingPriorityDomainCard,
  TrainingTrendPoint
} from './types';

export interface TrainingPlanEntry {
  entry_id: string;
  date: string;
  title: string;
  focus: string;
  expected_effect: string;
  training_scene: string;
  steps: string[];
  parent_script: string;
  materials: string[];
  fallback_plan: string;
  coaching_tip: string;
  source: 'today_task' | 'suggested';
}

export interface TrainingProgressMoment {
  point_id: string;
  label: string;
  effect_score: number;
  confidence: number;
  completion_status: TrainingCompletionStatus;
  summary: string;
}

const stageBaseScore = {
  stabilize: 24,
  practice: 48,
  generalize: 74,
  maintain: 88
} as const;

const difficultyBonus = {
  starter: 0,
  build: 4,
  advance: 7
} as const;

const completionScore = {
  done: 100,
  partial: 62,
  missed: 24
} as const;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function normalizeDate(value: Date | string) {
  if (value instanceof Date) {
    return new Date(value.getFullYear(), value.getMonth(), value.getDate());
  }

  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, (month || 1) - 1, day || 1);
}

function addDays(base: Date, days: number) {
  const next = new Date(base);
  next.setDate(base.getDate() + days);
  return next;
}

function toISODate(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function sessionOffsets(count: number) {
  return [0, 2, 4, 7, 9, 11].slice(0, count);
}

export function computeDomainProgressPercent(
  domain: TrainingPriorityDomainCard,
  detail?: TrainingDomainDetail | null
) {
  if (detail) {
    const base = stageBaseScore[detail.progress.current_stage] + difficultyBonus[detail.progress.current_difficulty];
    const completion = detail.progress.recent_completion_rate * 0.2;
    const effectiveness = detail.progress.recent_effective_rate * 0.15;
    const volume = Math.min(detail.progress.weekly_sessions_count, 4) * 2.5;
    return Math.round(clamp(base + completion + effectiveness + volume, 8, 98));
  }

  const fallback =
    stageBaseScore[domain.current_stage] +
    difficultyBonus[domain.current_difficulty] +
    Math.min(domain.weekly_sessions_count, 4) * 4 +
    (domain.has_today_task ? 4 : 0);

  return Math.round(clamp(fallback, 8, 96));
}

export function buildTrainingPlanEntries(
  detail: TrainingDomainDetail,
  todayTask?: DailyTrainingTask | null,
  referenceDate: Date | string = new Date()
): TrainingPlanEntry[] {
  const baseDate = normalizeDate(referenceDate);
  const count = Math.max(4, Math.min(6, Math.max(detail.progress.weekly_sessions_count, 2) * 2));

  return sessionOffsets(count).map((offset, index) => {
    const date = toISODate(addDays(baseDate, offset));
    const useTodayTask = index === 0 ? todayTask ?? null : null;
    const stepLead = detail.parent_steps[index % detail.parent_steps.length] ?? detail.training_principles[0] ?? '先做一轮简短练习';
    const focus = useTodayTask?.today_goal ?? detail.short_term_goal.target;
    const expectedEffect = index < 2 ? detail.short_term_goal.success_marker : detail.medium_term_goal.success_marker;
    const scene = useTodayTask?.training_scene ?? detail.suggested_scenarios[index % detail.suggested_scenarios.length] ?? '家庭日常';
    const steps = useTodayTask?.steps?.length
      ? useTodayTask.steps
      : [stepLead, ...detail.parent_steps.filter((_, stepIndex) => stepIndex !== index % detail.parent_steps.length)].slice(0, 4);

    return {
      entry_id: `${detail.area_key}-${date}-${index}`,
      date,
      title: useTodayTask?.title ?? `${detail.title} · 第 ${index + 1} 次练习`,
      focus,
      expected_effect: expectedEffect,
      training_scene: scene,
      steps,
      parent_script: useTodayTask?.parent_script ?? detail.script_examples[index % detail.script_examples.length] ?? '',
      materials: useTodayTask?.materials ?? [],
      fallback_plan: useTodayTask?.fallback_plan ?? detail.fallback_options[0] ?? '如果状态变差，就把要求降到只做第一步。',
      coaching_tip: useTodayTask?.coaching_tip ?? detail.training_principles[index % detail.training_principles.length] ?? '',
      source: useTodayTask ? 'today_task' : 'suggested'
    } satisfies TrainingPlanEntry;
  });
}

export function buildProgressMoments(detail: TrainingDomainDetail): TrainingProgressMoment[] {
  return detail.recent_feedbacks
    .slice()
    .reverse()
    .slice(-6)
    .map((item) => ({
      point_id: `${item.feedback_id}`,
      label: item.date.slice(5),
      effect_score: clamp(item.effect_score, 0, 100),
      confidence: clamp(item.parent_confidence * 10, 0, 100),
      completion_status: item.completion_status,
      summary: item.notes || item.task_title
    }));
}

export function buildCheckinCircles(trend: TrainingTrendPoint[]) {
  return trend.slice(-7).map((item, index) => ({
    circle_id: `${item.label}-${index}`,
    label: item.label,
    completion_rate: clamp(item.completion_rate, 0, 100),
    completed: item.completed_count > 0
  }));
}

export function summarizeCurrentSituation(detail: TrainingDomainDetail) {
  const latest = detail.recent_feedbacks[0];
  if (latest?.notes) return latest.notes;
  if (latest) return `${latest.task_title} 最近一次反馈为 ${completionScore[latest.completion_status]} 分表现。`;
  if (detail.current_risks.length) return detail.current_risks[0];
  return detail.importance_summary;
}
