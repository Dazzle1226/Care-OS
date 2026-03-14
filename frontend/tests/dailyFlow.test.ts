import assert from 'node:assert/strict';
import test from 'node:test';

import { defaultCheckinFormValues } from '../src/lib/checkinPayload.ts';
import {
  buildDailyFlowContent,
  buildCheckinSummary,
  getDailyFlowScenario,
  inferScenarioFromCheckin,
  toCheckinPayloadFromRecord,
  toCheckinInitialValues
} from '../src/lib/dailyFlow.ts';

test('inferScenarioFromCheckin keeps low-load answers in stable flow', () => {
  const scenario = inferScenarioFromCheckin({
    ...defaultCheckinFormValues,
    date: '2026-03-12',
    child_sleep_hours: 9,
    child_mood_state: 'stable',
    sensory_overload_level: 'none',
    transition_difficulty: 2,
    caregiver_stress: 3,
    support_available: 'two_plus',
    caregiver_sleep_quality: 8
  });

  assert.equal(scenario, 'stable');
});

test('inferScenarioFromCheckin routes moderate strain into watch flow', () => {
  const scenario = inferScenarioFromCheckin({
    ...defaultCheckinFormValues,
    date: '2026-03-12',
    child_sleep_hours: 6,
    child_mood_state: 'sensitive',
    sensory_overload_level: 'medium',
    transition_difficulty: 6,
    caregiver_stress: 6,
    support_available: 'one',
    today_activities: ['学校活动'],
    today_learning_tasks: ['学校作业']
  });

  assert.equal(scenario, 'watch');
  assert.equal(getDailyFlowScenario(scenario).quickActions.length, 1);
});

test('inferScenarioFromCheckin escalates to high flow for meltdown-heavy answers', () => {
  const scenario = inferScenarioFromCheckin({
    ...defaultCheckinFormValues,
    date: '2026-03-12',
    child_sleep_hours: 4,
    child_mood_state: 'irritable',
    sensory_overload_level: 'heavy',
    meltdown_count: 2,
    transition_difficulty: 9,
    caregiver_stress: 9,
    support_available: 'none',
    caregiver_sleep_quality: 3
  });

  assert.equal(scenario, 'high');
  assert.equal(getDailyFlowScenario(scenario).lowStimulus, true);
});

test('buildCheckinSummary converts original checkin answers into collapsed summary copy', () => {
  const summary = buildCheckinSummary({
    ...defaultCheckinFormValues,
    date: '2026-03-12',
    child_sleep_hours: 5,
    child_mood_state: 'anxious',
    transition_difficulty: 8,
    caregiver_stress: 8,
    support_available: 'none'
  });

  assert.deepEqual(summary, [
    '昨晚睡眠明显不足',
    '孩子今天更焦虑',
    '今天过渡很可能成为高摩擦时刻',
    '家长今天几乎没有余量',
    '今天主要需要自己扛'
  ]);
});

test('toCheckinInitialValues strips date when reopening modal', () => {
  const initialValues = toCheckinInitialValues({
    ...defaultCheckinFormValues,
    date: '2026-03-12'
  });

  assert.equal(initialValues?.child_sleep_hours, defaultCheckinFormValues.child_sleep_hours);
  assert.equal('date' in (initialValues ?? {}), false);
});

test('toCheckinPayloadFromRecord keeps saved today checkin reusable for reopening', () => {
  const payload = toCheckinPayloadFromRecord({
    checkin_id: 7,
    date: '2026-03-12',
    child_sleep_hours: 6,
    child_sleep_quality: 5,
    sleep_issues: ['入睡慢'],
    meltdown_count: 1,
    child_mood_state: 'sensitive',
    physical_discomforts: ['无明显不适'],
    aggressive_behaviors: ['无明显过激行为'],
    negative_emotions: ['焦虑'],
    transition_difficulty: 7,
    sensory_overload_level: 'medium',
    caregiver_stress: 6,
    caregiver_sleep_quality: 5,
    support_available: 'one',
    today_activities: ['学校活动'],
    today_learning_tasks: ['学校作业']
  });

  assert.equal(payload.date, '2026-03-12');
  assert.equal(payload.transition_difficulty, 7);
  assert.deepEqual(payload.today_learning_tasks, ['学校作业']);
});

test('buildDailyFlowContent prefers previously generated today plan content when available', () => {
  const scenario = getDailyFlowScenario('watch');
  const content = buildDailyFlowContent(
    {
      today_one_thing: '先把出门前那一次过渡单独做好',
      action_plan: {
        headline: '先减掉多余指令',
        summary: '今天优先保住那次最容易卡住的切换，不追求把所有任务一次做完。',
        reminders: [
          { eyebrow: '先降刺激', title: '说话只留一个人', body: '先别多人同时提醒。' },
          { eyebrow: '先留退路', title: '提前说清结束点', body: '做完这一小段就停。' }
        ],
        three_step_action: ['先停长解释', '只给一个下一步', '做完先收尾'],
        parent_phrase: '现在先做这一小步，做完我们就停一下。',
        meltdown_fallback: [],
        respite_suggestion: '',
        plan_overview: []
      }
    },
    scenario
  );

  assert.equal(content.priorityTitle, '先把出门前那一次过渡单独做好');
  assert.equal(content.preventiveTitle, '先减掉多余指令');
  assert.deepEqual(content.priorityChecklist, ['先停长解释', '只给一个下一步', '做完先收尾']);
  assert.deepEqual(content.preventiveSuggestions, ['说话只留一个人', '提前说清结束点']);
});
