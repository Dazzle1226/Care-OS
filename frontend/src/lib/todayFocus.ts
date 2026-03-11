import type { CheckinRecord, CheckinTodayStatus, RiskLevel, TodayReminderItem } from './types';

interface HomeRespiteEntry {
  eyebrow: string;
  title: string;
  description: string;
  badge: string;
}

function buildReminder(eyebrow: string, title: string, body: string): TodayReminderItem {
  return { eyebrow, title, body };
}

function hasMeaningfulTag(values: string[], emptyLabel: string) {
  return values.some((item) => item !== emptyLabel);
}

function buildPreventiveSuggestions(checkin: CheckinRecord, riskLevel?: RiskLevel) {
  const suggestions: TodayReminderItem[] = [];
  const transitionDifficulty = checkin.transition_difficulty ?? 0;
  const hasExternalActivity = checkin.today_activities.some((item) =>
    ['学校活动', '医生预约', '社交活动', '外出安排', '家庭聚会', '需要长途通勤'].includes(item)
  );
  const hasStrongEmotion = checkin.negative_emotions.some((item) => ['焦虑', '恐惧', '愤怒', '社交回避'].includes(item));
  const hasPhysicalDiscomfort = hasMeaningfulTag(checkin.physical_discomforts, '无明显不适');
  const hasAggressiveBehavior = hasMeaningfulTag(checkin.aggressive_behaviors, '无明显过激行为');

  if (riskLevel === 'red' || checkin.meltdown_count >= 2 || transitionDifficulty >= 7 || hasAggressiveBehavior) {
    suggestions.push(
      buildReminder(
        '先减负荷',
        '今天只保留一个主任务',
        '签到显示今天更容易升级，先把最难的一件事单独做，其他任务能减就减。'
      )
    );
  }

  if (
    ['medium', 'heavy'].includes(checkin.sensory_overload_level) ||
    ['sensitive', 'anxious', 'irritable'].includes(checkin.child_mood_state) ||
    hasStrongEmotion
  ) {
    suggestions.push(
      buildReminder(
        '先降刺激',
        '开始前先把环境和话语都压低',
        '先减声音、减人、减指令长度，只说一句现在要做什么，避免一上来就讲道理或连发提醒。'
      )
    );
  }

  if (checkin.child_sleep_hours <= 5 || checkin.caregiver_sleep_quality <= 4 || hasPhysicalDiscomfort) {
    suggestions.push(
      buildReminder(
        '先稳节奏',
        '今天按慢半拍来推进',
        '签到里已经有睡眠或身体负荷信号，先留缓冲时间，卡住时优先休息和过渡，不追求一次做完。'
      )
    );
  }

  if (hasExternalActivity) {
    suggestions.push(
      buildReminder(
        '外出前先预告',
        '把流程和退出点提前说清',
        '今天有外出或变化安排，出门前先说顺序、等待点和结束方式，减少临场切换带来的拉扯。'
      )
    );
  }

  if (checkin.today_learning_tasks.length > 0) {
    suggestions.push(
      buildReminder(
        '任务先拆小',
        '学习或训练只先做第一步',
        '今天有学习或训练任务，先把要求缩到可马上开始的一小步，做完就停一下再决定要不要继续。'
      )
    );
  }

  if (checkin.support_available === 'none' || checkin.caregiver_stress >= 7) {
    suggestions.push(
      buildReminder(
        '先留退路',
        '开始前先想好谁来接手或何时暂停',
        '如果今天支持少或家长负荷高，先约定中断点和接手方式，避免现场已经升级了才临时想办法。'
      )
    );
  }

  if (!suggestions.length) {
    suggestions.push(
      buildReminder('先做预告', '关键过渡提前两分钟提醒', '今天整体可推进，也先把切换点提前说清，通常比出事后再补救更省力。'),
      buildReminder('先做小步', '每次只推进一小段', '即使今天状态平稳，也先用短指令和小目标开场，能明显降低临场对抗。'),
      buildReminder('先看照护者', '家长先保留一句固定提示', '提前决定今天反复只说哪一句，能减少孩子和家长一起被越说越急。')
    );
  }

  return suggestions.slice(0, 3);
}

export function getHomeReminderCards(
  status: Pick<CheckinTodayStatus, 'needs_checkin' | 'action_plan' | 'checkin' | 'risk'> | null
): TodayReminderItem[] {
  if (!status || status.needs_checkin) return [];
  if (status.checkin) {
    return buildPreventiveSuggestions(status.checkin, status.risk?.risk_level);
  }
  return status.action_plan?.reminders.slice(0, 3) ?? [];
}

function normalizeSuggestion(value: string | null | undefined) {
  return (value ?? '').trim();
}

export function getHomeActionSuggestions(
  status: Pick<CheckinTodayStatus, 'needs_checkin' | 'today_one_thing' | 'action_plan'> | null
): string[] {
  if (!status || status.needs_checkin || !status.action_plan) return [];

  const suggestions = [
    ...status.action_plan.three_step_action,
    ...status.action_plan.plan_overview,
    status.action_plan.headline,
    status.today_one_thing ?? ''
  ]
    .map(normalizeSuggestion)
    .filter(Boolean);

  return suggestions.filter((item, index) => suggestions.indexOf(item) === index).slice(0, 3);
}

export function getHomeRespiteEntry(
  status: Pick<CheckinTodayStatus, 'needs_checkin' | 'checkin' | 'risk' | 'action_plan'> | null,
  hasFamily: boolean
): HomeRespiteEntry | null {
  if (!hasFamily) return null;

  if (!status || status.needs_checkin || !status.checkin) {
    return {
      eyebrow: '额外功能',
      title: '微喘息',
      description: '这是独立功能，不会打断首页主流程。先完成今日签到，再生成更贴近当下状态的微喘息建议。',
      badge: '签到后可用'
    };
  }

  if (status.checkin.caregiver_stress >= 7 || status.checkin.caregiver_sleep_quality <= 4 || status.risk?.risk_level === 'red') {
    return {
      eyebrow: '额外功能',
      title: '先给照护者留一个恢复窗口',
      description:
        status.action_plan?.respite_suggestion ??
        '如果你也快跟不上节奏，可以单独打开微喘息，先拿到一个短时、低门槛的恢复方案。',
      badge: '建议现在打开'
    };
  }

  return {
    eyebrow: '额外功能',
    title: '需要时再打开微喘息',
    description: '当你感觉自己开始累、急、或现场需要暂时减负时，再单独打开这个入口，不会影响今天主流程。',
    badge: '独立功能'
  };
}
