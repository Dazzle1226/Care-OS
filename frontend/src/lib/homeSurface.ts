import { getActionSourceLabel, getScenarioLabel, type ActionFlowContext } from './flow.ts';

export type HomeSurfaceKind = 'setup' | 'checkin' | 'todayFlow' | 'training' | 'review';

export interface HomeSurfaceRecommendation {
  kind: HomeSurfaceKind;
  eyebrow: string;
  title: string;
  summary: string;
  detail: string;
  ctaLabel: string;
}

export function getHomeSurfaceRecommendation(input: {
  familyId: number | null;
  actionContext: ActionFlowContext | null;
  isTodayFlowOpen: boolean;
}): HomeSurfaceRecommendation {
  const { familyId, actionContext, isTodayFlowOpen } = input;

  if (!familyId) {
    return {
      kind: 'setup',
      eyebrow: '先完成准备',
      title: '先连接家庭档案，再开始今天的判断',
      summary: '首页的大卡片会在建档后切到最需要你现在处理的内容。',
      detail: '没有家庭档案时，系统还无法根据孩子与照护者状态组织首页主路径。',
      ctaLabel: '去家庭页建档'
    };
  }

  if (isTodayFlowOpen) {
    return {
      kind: 'todayFlow',
      eyebrow: 'AI 正在带路',
      title: '现在先沿着今日行动流继续',
      summary: '签到完成后，大卡片会原地继续展开今天最值得先做的动作，不再把你丢回入口选择。',
      detail: '这是首页当前最优先的路径，先完成这条线，再决定是否进入支持、训练或复盘。',
      ctaLabel: '继续今日行动流'
    };
  }

  if (!actionContext) {
    return {
      kind: 'checkin',
      eyebrow: 'AI 推荐起点',
      title: '先做今日签到，让系统决定今天从哪里开始',
      summary: '先收一轮最短状态信号，再判断是继续行动、进入训练指导，还是留到做后复盘。',
      detail: '今天没有待续动作时，不让用户先面对一堆入口，而是先完成签到。',
      ctaLabel: '开始今日签到'
    };
  }

  if (actionContext.source === 'plan') {
    return {
      kind: 'training',
      eyebrow: 'AI 推荐训练指导',
      title: actionContext.title || '先继续今天的训练推进',
      summary: actionContext.summary || '系统保留了上一次训练脉络，适合先把计划中的重点继续推进。',
      detail: `来源：${getActionSourceLabel(actionContext.source)} · ${getScenarioLabel(
        actionContext.sourceScenario ?? actionContext.scenario
      )}`,
      ctaLabel: '打开训练方案'
    };
  }

  return {
    kind: 'review',
    eyebrow: 'AI 推荐复盘',
    title: '先回到刚才那次动作，补一个最小复盘',
    summary: actionContext.summary || '系统检测到有待承接的动作脉络，先收结果，再决定下一步。',
    detail: `待续内容：${getActionSourceLabel(actionContext.source)} · ${getScenarioLabel(
      actionContext.sourceScenario ?? actionContext.scenario
    )}`,
    ctaLabel: '去轻复盘'
  };
}
