import assert from 'node:assert/strict';
import test from 'node:test';

import { getHomeActionSuggestions, getHomeReminderCards, getHomeRespiteEntry } from '../src/lib/todayFocus.ts';

test('getHomeReminderCards builds preventive suggestions from today checkin', () => {
  const reminders = getHomeReminderCards({
    needs_checkin: false,
    risk: { risk_level: 'yellow', reasons: ['过渡负荷高'], trigger_48h: false, confidence: 0.8 },
    checkin: {
      checkin_id: 1,
      date: '2026-03-10',
      child_sleep_hours: 6,
      child_sleep_quality: 5,
      sleep_issues: [],
      meltdown_count: 2,
      child_mood_state: 'anxious',
      physical_discomforts: ['无明显不适'],
      aggressive_behaviors: ['哭闹'],
      negative_emotions: ['焦虑'],
      transition_difficulty: 8,
      sensory_overload_level: 'medium',
      caregiver_stress: 8,
      caregiver_sleep_quality: 5,
      support_available: 'none',
      today_activities: ['学校活动'],
      today_learning_tasks: ['学校作业']
    },
    action_plan: {
      headline: '先做一件事',
      summary: '先处理今天最关键的卡点。',
      reminders: [
        { eyebrow: '这次最容易做偏', title: '不要加码', body: '先只给一步。' },
        { eyebrow: '现场开始卡住', title: '先减输入', body: '先安静 10 秒。' }
      ],
      three_step_action: ['一', '二', '三'],
      parent_phrase: '先做第一步。',
      meltdown_fallback: ['甲', '乙', '丙'],
      respite_suggestion: '休息 15 分钟。',
      plan_overview: ['只做一步']
    }
  });

  assert.deepEqual(reminders, [
    { eyebrow: '先减负荷', title: '今天只保留一个主任务', body: '签到显示今天更容易升级，先把最难的一件事单独做，其他任务能减就减。' },
    { eyebrow: '先降刺激', title: '开始前先把环境和话语都压低', body: '先减声音、减人、减指令长度，只说一句现在要做什么，避免一上来就讲道理或连发提醒。' },
    { eyebrow: '外出前先预告', title: '把流程和退出点提前说清', body: '今天有外出或变化安排，出门前先说顺序、等待点和结束方式，减少临场切换带来的拉扯。' }
  ]);
});

test('getHomeReminderCards falls back to stable-day preventive suggestions', () => {
  const reminders = getHomeReminderCards({
    needs_checkin: false,
    risk: { risk_level: 'green', reasons: [], trigger_48h: false, confidence: 0.9 },
    checkin: {
      checkin_id: 2,
      date: '2026-03-10',
      child_sleep_hours: 9,
      child_sleep_quality: 8,
      sleep_issues: [],
      meltdown_count: 0,
      child_mood_state: 'stable',
      physical_discomforts: ['无明显不适'],
      aggressive_behaviors: ['无明显过激行为'],
      negative_emotions: ['无明显负面情绪'],
      transition_difficulty: 3,
      sensory_overload_level: 'none',
      caregiver_stress: 3,
      caregiver_sleep_quality: 8,
      support_available: 'two_plus',
      today_activities: [],
      today_learning_tasks: []
    },
    action_plan: {
      headline: '按平时节奏推进',
      summary: '今天保持稳定。',
      reminders: [],
      three_step_action: ['一', '二', '三'],
      parent_phrase: '先做第一步。',
      meltdown_fallback: ['甲', '乙', '丙'],
      respite_suggestion: '休息 15 分钟。',
      plan_overview: ['只做一步']
    }
  });

  assert.deepEqual(reminders, [
    { eyebrow: '先做预告', title: '关键过渡提前两分钟提醒', body: '今天整体可推进，也先把切换点提前说清，通常比出事后再补救更省力。' },
    { eyebrow: '先做小步', title: '每次只推进一小段', body: '即使今天状态平稳，也先用短指令和小目标开场，能明显降低临场对抗。' },
    { eyebrow: '先看照护者', title: '家长先保留一句固定提示', body: '提前决定今天反复只说哪一句，能减少孩子和家长一起被越说越急。' }
  ]);
});

test('getHomeActionSuggestions prefers three step action for homepage execution list', () => {
  const suggestions = getHomeActionSuggestions({
    needs_checkin: false,
    today_one_thing: '今天先把出门过渡做稳',
    action_plan: {
      headline: '先把最难的过渡单独做完',
      summary: '只做最关键的一步。',
      reminders: [
        { eyebrow: '提醒', title: '不要加码', body: '只保留一件事。' },
        { eyebrow: '提醒', title: '先减输入', body: '环境先安静下来。' }
      ],
      three_step_action: ['先提前两分钟预告', '再只给一个离开指令', '完成后立刻结束并肯定'],
      parent_phrase: '我们先做第一步。',
      meltdown_fallback: ['甲', '乙', '丙'],
      respite_suggestion: '休息 15 分钟。',
      plan_overview: ['只做一个过渡', '做完就收']
    }
  });

  assert.deepEqual(suggestions, ['先提前两分钟预告', '再只给一个离开指令', '完成后立刻结束并肯定']);
});

test('getHomeActionSuggestions falls back to overview and headline when action list is malformed', () => {
  const suggestions = getHomeActionSuggestions({
    needs_checkin: false,
    today_one_thing: '今天先把第一步做出来',
    action_plan: {
      headline: '先把任务第一步做出来',
      summary: '今天不追求做完。',
      reminders: [
        { eyebrow: '提醒', title: '别加量', body: '只做第一步。' },
        { eyebrow: '提醒', title: '先停顿', body: '卡住先停 10 秒。' }
      ],
      three_step_action: [' ', '', ''],
      parent_phrase: '先做第一步。',
      meltdown_fallback: ['甲', '乙', '丙'],
      respite_suggestion: '休息 15 分钟。',
      plan_overview: ['只做第一步', '做完马上收尾', '家长只重复一句提示']
    }
  });

  assert.deepEqual(suggestions, ['只做第一步', '做完马上收尾', '家长只重复一句提示']);
});

test('getHomeRespiteEntry keeps micro respite as a standalone tool before checkin', () => {
  const entry = getHomeRespiteEntry(
    {
      needs_checkin: true
    },
    true
  );

  assert.deepEqual(entry, {
    eyebrow: '额外功能',
    title: '微喘息',
    description: '这是独立功能，不会打断首页主流程。先完成今日签到，再生成更贴近当下状态的微喘息建议。',
    badge: '签到后可用'
  });
});

test('getHomeRespiteEntry escalates copy when caregiver load is high', () => {
  const entry = getHomeRespiteEntry(
    {
      needs_checkin: false,
      risk: { risk_level: 'yellow', reasons: ['家长负荷高'], trigger_48h: false, confidence: 0.8 },
      checkin: {
        checkin_id: 1,
        date: '2026-03-10',
        child_sleep_hours: 6,
        child_sleep_quality: 5,
        sleep_issues: [],
        meltdown_count: 1,
        child_mood_state: 'sensitive',
        physical_discomforts: ['无明显不适'],
        aggressive_behaviors: ['无明显过激行为'],
        negative_emotions: ['焦虑'],
        transition_difficulty: 6,
        sensory_overload_level: 'light',
        caregiver_stress: 8,
        caregiver_sleep_quality: 4,
        support_available: 'one',
        today_activities: [],
        today_learning_tasks: []
      },
      action_plan: {
        headline: '先稳住节奏',
        summary: '只做一件事。',
        reminders: [],
        three_step_action: ['一', '二', '三'],
        parent_phrase: '先做第一步。',
        meltdown_fallback: ['甲', '乙', '丙'],
        respite_suggestion: '建议安排 15 分钟自己独处，家长只保留一个最小目标。',
        plan_overview: ['只做一步']
      }
    },
    true
  );

  assert.deepEqual(entry, {
    eyebrow: '额外功能',
    title: '先给照护者留一个恢复窗口',
    description: '建议安排 15 分钟自己独处，家长只保留一个最小目标。',
    badge: '建议现在打开'
  });
});
