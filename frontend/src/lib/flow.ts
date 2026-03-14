export type CareTab = 'today' | 'scripts' | 'plan' | 'review' | 'family';
export type ReviewScenario = 'transition' | 'bedtime' | 'homework' | 'outing';
export type ActionSource = 'today' | 'scripts' | 'plan';

export interface ActionFlowContext {
  source: ActionSource;
  scenario: ReviewScenario;
  sourceScenario?: string;
  title: string;
  summary: string;
  cardIds: string[];
  suggestedTriggers: string[];
  suggestedFollowup: string;
  createdAt: string;
}

export interface CareTabMeta {
  key: CareTab;
  label: string;
  hint: string;
}

export const careTabs: CareTabMeta[] = [
  { key: 'today', label: '首页', hint: '主入口：先让系统判断今天先做什么，再决定要不要分流' },
  { key: 'scripts', label: '高摩擦支持', hint: '次入口：已知现场卡住时，再直接进入预设和三步支援' },
  { key: 'plan', label: '训练方案', hint: '次入口：已知要看计划时，再直接查看今天任务和重点' },
  { key: 'review', label: '复盘', hint: '做完后补结果、触发器和下次保留的一件事' },
  { key: 'family', label: '家庭档案', hint: '查看关键提醒，需要时再改详细档案' }
];

const ACTION_FLOW_STORAGE_KEY = 'care_os_action_flow_context';

const sourceLabelMap: Record<ActionSource, string> = {
  today: '今日行动',
  scripts: '高摩擦支持',
  plan: '训练方案'
};

const scenarioLabelMap: Record<ReviewScenario | 'meltdown', string> = {
  transition: '过渡',
  bedtime: '睡前',
  homework: '作业',
  outing: '外出',
  meltdown: '失控升级'
};

function cleanList(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter(Boolean)
    .filter((item, index, list) => list.indexOf(item) === index);
}

export function normalizeScenario(value?: string | null): ReviewScenario {
  if (value === 'bedtime' || value === 'homework' || value === 'outing') {
    return value;
  }
  return 'transition';
}

export function getScenarioLabel(value?: string | null) {
  if (!value) return scenarioLabelMap.transition;
  return scenarioLabelMap[value as keyof typeof scenarioLabelMap] ?? (value.trim() || scenarioLabelMap.transition);
}

export function getActionSourceLabel(source: ActionSource) {
  return sourceLabelMap[source];
}

export function createActionFlowContext(
  input: {
    source: ActionSource;
    scenario?: string | null;
    sourceScenario?: string | null;
    title: string;
    summary: string;
    cardIds?: string[];
    suggestedTriggers?: string[];
    suggestedFollowup?: string;
    createdAt?: string;
  }
): ActionFlowContext {
  return {
    source: input.source,
    scenario: normalizeScenario(input.scenario),
    sourceScenario: input.sourceScenario?.trim() || input.scenario?.trim() || undefined,
    title: input.title.trim(),
    summary: input.summary.trim(),
    cardIds: cleanList(input.cardIds),
    suggestedTriggers: cleanList(input.suggestedTriggers).slice(0, 4),
    suggestedFollowup: input.suggestedFollowup?.trim() ?? '',
    createdAt: input.createdAt ?? new Date().toISOString()
  };
}

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

export function readActionFlowContext() {
  if (!canUseStorage()) return null;

  const raw = window.localStorage.getItem(ACTION_FLOW_STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<ActionFlowContext>;
    if (typeof parsed.title !== 'string' || typeof parsed.summary !== 'string' || typeof parsed.source !== 'string') {
      return null;
    }

    if (parsed.source !== 'today' && parsed.source !== 'scripts' && parsed.source !== 'plan') {
      return null;
    }

    return createActionFlowContext({
      source: parsed.source,
      scenario: parsed.scenario,
      sourceScenario: parsed.sourceScenario,
      title: parsed.title,
      summary: parsed.summary,
      cardIds: cleanList(parsed.cardIds),
      suggestedTriggers: cleanList(parsed.suggestedTriggers),
      suggestedFollowup: typeof parsed.suggestedFollowup === 'string' ? parsed.suggestedFollowup : '',
      createdAt: typeof parsed.createdAt === 'string' ? parsed.createdAt : undefined
    });
  } catch {
    return null;
  }
}

export function writeActionFlowContext(context: ActionFlowContext | null) {
  if (!canUseStorage()) return;

  if (!context) {
    window.localStorage.removeItem(ACTION_FLOW_STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(ACTION_FLOW_STORAGE_KEY, JSON.stringify(context));
}
