import { buildCheckinPayload, type CheckinFormPayload, type CheckinFormValues } from './checkinPayload.ts';
import type { CheckinRecord, CheckinTodayStatus } from './types.ts';

export type DemoScenarioId = 'stable' | 'watch' | 'high';

export interface QuickActionDefinition {
  id: 'script' | 'respite' | 'lowStim';
  title: string;
  description: string;
  detailTitle: string;
  detailBody: string;
  steps: string[];
  ctaLabel?: string;
  ctaTarget?: 'scripts' | 'review';
}

export interface DailyFlowScenario {
  id: DemoScenarioId;
  label: string;
  description: string;
  greeting: string;
  helper: string;
  riskLabel: string;
  lowStimulus: boolean;
  primaryTitle: string;
  primaryBody: string;
  primaryChecklist: string[];
  preventiveTitle: string;
  preventiveBody: string;
  preventiveSuggestions: string[];
  quickActions: QuickActionDefinition[];
}

const scenarioMap: Record<DemoScenarioId, DailyFlowScenario> = {
  stable: {
    id: 'stable',
    label: '平稳日',
    description: '状态平稳，系统只保留最小推进。',
    greeting: '先签到，系统会把今天最值得先做的一件事推出来。',
    helper: '今天不需要看很多，页面只会保留一条清晰的行动线。',
    riskLabel: '稳定推进',
    lowStimulus: false,
    primaryTitle: '今日主任务：把最关键的一次过渡做得更顺',
    primaryBody: '今天整体可推进，但不要把任务铺开。只盯住最容易卡住的那一次切换，先做顺它。',
    primaryChecklist: ['只提前说一次接下来要做什么', '把开始动作压到一个最小单位', '完成后立刻收尾，不追加要求'],
    preventiveTitle: '先做一件预防动作',
    preventiveBody: '今天只留一条提醒，目的是让节奏一直维持平稳。',
    preventiveSuggestions: ['关键过渡前提前两分钟预告，语句保持固定。'],
    quickActions: []
  },
  watch: {
    id: 'watch',
    label: '需要留意',
    description: '今天有明显卡点，需要先稳住过渡。',
    greeting: '系统会带着你走，不需要自己判断接下来点哪里。',
    helper: '签到后先给出主任务，再补 1 到 2 条预防动作，最后只留一个入口。',
    riskLabel: '需要留意',
    lowStimulus: false,
    primaryTitle: '今日主任务：先把今天最难的过渡单独做完',
    primaryBody: '今天最值得优先处理的不是把事做完，而是把最容易拉扯的切换点先做平。',
    primaryChecklist: ['先删掉不必要解释', '只给一个离开或开始指令', '过渡结束后先停，不立刻进入下一项'],
    preventiveTitle: '执行前先减一次负荷',
    preventiveBody: '今天先做两条预防动作，会比现场卡住后再救火更省力。',
    preventiveSuggestions: [
      '把环境中的声响和旁人提醒先降下来，只保留一个说话的人。',
      '把退出点提前说清，例如“做完这一小段就停”。'
    ],
    quickActions: [
      {
        id: 'script',
        title: '查看过渡脚本',
        description: '需要时立刻打开一句句可说的话。',
        detailTitle: '高摩擦脚本入口已就位',
        detailBody: '如果孩子开始拖住、拒绝或情绪升高，不要临场组织长句，直接切去脚本支持。',
        steps: ['先用一句短提示接住当前状态', '再给唯一下一步，不追加条件', '如果继续升级，立即切换到退路脚本'],
        ctaLabel: '去高摩擦支援',
        ctaTarget: 'scripts'
      }
    ]
  },
  high: {
    id: 'high',
    label: '高压力日',
    description: '今天先减负，不追求推进完整计划。',
    greeting: '今天界面会更安静，系统只保留最必要的动作。',
    helper: '签到后不会给一堆建议，而是先压低刺激，再给两个直接入口。',
    riskLabel: '高压力日',
    lowStimulus: true,
    primaryTitle: '今日主任务：先保住稳定，不要把所有任务都做完',
    primaryBody: '今天最值得优先处理的是减负。先把要求降到最低，只保留一个必须完成的动作，其余全部延后。',
    primaryChecklist: ['删掉可推迟任务', '只保留一句固定提示', '准备好随时退出当前流程'],
    preventiveTitle: '先做明显的减负动作',
    preventiveBody: '今天的预防不是“更努力”，而是先给孩子和家长一起降载。',
    preventiveSuggestions: ['把今天流程压缩成最小版本，减少声音、减少选择、减少催促。'],
    quickActions: [
      {
        id: 'respite',
        title: '开始微喘息',
        description: '先给照护者留 90 秒恢复窗口。',
        detailTitle: '微喘息已经准备好',
        detailBody: '先把孩子放进已知安全的最小活动，再给自己 90 秒把呼吸、肩颈和语速降下来。',
        steps: ['先停下额外对话', '做三次慢呼气', '回到现场后只重复一句提示']
      },
      {
        id: 'lowStim',
        title: '进入低刺激模式',
        description: '把界面和行动都切到更克制的状态。',
        detailTitle: '低刺激模式已启动',
        detailBody: '现在先减少页面信息密度，也同步减少现场语言、光线和动作切换。',
        steps: ['把今天目标压到一件事', '把声音和指令数量减半', '需要时再打开高摩擦入口'],
        ctaLabel: '去高摩擦支援',
        ctaTarget: 'scripts'
      }
    ]
  }
};

function hasTaggedItems(items: string[] | undefined, emptyLabel: string) {
  return Array.isArray(items) && items.some((item) => item && item !== emptyLabel);
}

export function inferScenarioFromCheckin(checkin: CheckinFormPayload): DemoScenarioId {
  let score = 0;

  if (checkin.sensory_overload_level === 'heavy') score += 3;
  else if (checkin.sensory_overload_level === 'medium') score += 2;
  else if (checkin.sensory_overload_level === 'light') score += 1;

  if (checkin.meltdown_count >= 3) score += 4;
  else if (checkin.meltdown_count >= 2) score += 3;
  else if (checkin.meltdown_count === 1) score += 1;

  const transitionDifficulty = checkin.transition_difficulty ?? 4;
  if (transitionDifficulty >= 8) score += 3;
  else if (transitionDifficulty >= 6) score += 2;
  else if (transitionDifficulty >= 4) score += 1;

  if (checkin.caregiver_stress >= 8) score += 3;
  else if (checkin.caregiver_stress >= 6) score += 2;

  if (checkin.support_available === 'none') score += 2;
  else if (checkin.support_available === 'one') score += 1;

  if (checkin.child_sleep_hours <= 5) score += 2;
  else if (checkin.child_sleep_hours <= 6) score += 1;

  if (checkin.caregiver_sleep_quality <= 4) score += 2;
  else if (checkin.caregiver_sleep_quality <= 6) score += 1;

  if (checkin.child_mood_state === 'irritable' || checkin.child_mood_state === 'anxious') score += 2;
  else if (checkin.child_mood_state === 'sensitive' || checkin.child_mood_state === 'low_energy') score += 1;

  if (hasTaggedItems(checkin.negative_emotions, '无明显负面情绪')) score += 1;
  if (hasTaggedItems(checkin.aggressive_behaviors, '无明显过激行为')) score += 1;
  if (hasTaggedItems(checkin.physical_discomforts, '无明显不适')) score += 1;

  if (checkin.today_activities.length > 0) score += 1;
  if (checkin.today_learning_tasks.length > 0) score += 1;

  const isHighRisk =
    checkin.meltdown_count >= 2 ||
    transitionDifficulty >= 8 ||
    (checkin.sensory_overload_level === 'heavy' && checkin.support_available === 'none') ||
    (checkin.caregiver_stress >= 8 && checkin.support_available === 'none') ||
    score >= 13;

  if (isHighRisk) return 'high';
  if (score >= 5) return 'watch';
  return 'stable';
}

export function getDailyFlowScenario(id: DemoScenarioId): DailyFlowScenario {
  return scenarioMap[id];
}

export function buildCheckinSummary(checkin: CheckinFormPayload): string[] {
  const sleepLabel =
    checkin.child_sleep_hours <= 5 ? '昨晚睡眠明显不足' : checkin.child_sleep_hours <= 7 ? '昨晚睡眠一般' : '昨晚睡眠相对稳定';

  const moodLabelMap = {
    stable: '孩子今天整体平稳',
    sensitive: '孩子今天偏敏感',
    anxious: '孩子今天更焦虑',
    low_energy: '孩子今天能量偏低',
    irritable: '孩子今天明显烦躁'
  } as const;

  const transitionDifficulty = checkin.transition_difficulty ?? 4;
  const transitionLabel =
    transitionDifficulty >= 8 ? '今天过渡很可能成为高摩擦时刻' : transitionDifficulty >= 6 ? '今天过渡需要提前托住' : '今天过渡阻力相对可控';

  const caregiverLabel =
    checkin.caregiver_stress >= 8 ? '家长今天几乎没有余量' : checkin.caregiver_stress >= 6 ? '家长今天接近上限' : '家长今天还有一点余量';

  const supportLabelMap = {
    none: '今天主要需要自己扛',
    one: '今天大概率只有 1 位支持者',
    two_plus: '今天有接力空间'
  } as const;

  return [sleepLabel, moodLabelMap[checkin.child_mood_state], transitionLabel, caregiverLabel, supportLabelMap[checkin.support_available]];
}

export function toCheckinInitialValues(checkin: CheckinFormPayload | null): Partial<CheckinFormValues> | undefined {
  if (!checkin) return undefined;
  const { date: _date, ...initialValues } = checkin;
  return initialValues;
}

export function toCheckinPayloadFromRecord(checkin: CheckinRecord): CheckinFormPayload {
  return buildCheckinPayload({
    ...checkin,
    date: checkin.date,
  });
}

function dedupeStrings(values: Array<string | null | undefined>) {
  return values
    .map((item) => (item ?? '').trim())
    .filter(Boolean)
    .filter((item, index, list) => list.indexOf(item) === index);
}

export function buildDailyFlowContent(
  status: Pick<CheckinTodayStatus, 'today_one_thing' | 'action_plan'> | null,
  scenario: DailyFlowScenario | null
) {
  const reminders = status?.action_plan?.reminders ?? [];
  const backendSuggestions = dedupeStrings(reminders.map((item) => item.title || item.body)).slice(0, 3);
  const fallbackChecklist = scenario?.primaryChecklist ?? [];
  const fallbackSuggestions = scenario?.preventiveSuggestions ?? [];

  return {
    priorityTitle: status?.today_one_thing?.trim() || scenario?.primaryTitle || '',
    priorityBody: status?.action_plan?.summary?.trim() || scenario?.primaryBody || '',
    priorityChecklist: dedupeStrings([
      ...(status?.action_plan?.three_step_action ?? []),
      ...fallbackChecklist,
    ]).slice(0, 3),
    preventiveTitle: status?.action_plan?.headline?.trim() || scenario?.preventiveTitle || '',
    preventiveBody: status?.action_plan?.parent_phrase?.trim() || scenario?.preventiveBody || '',
    preventiveSuggestions: backendSuggestions.length > 0 ? backendSuggestions : fallbackSuggestions,
  };
}
