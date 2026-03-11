import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildCheckinCircles,
  buildProgressMoments,
  buildTrainingPlanEntries,
  computeDomainProgressPercent,
  summarizeCurrentSituation
} from '../src/lib/trainingTracking.ts';
import type { TrainingDomainDetail, TrainingPriorityDomainCard } from '../src/lib/types.ts';

const priorityDomain: TrainingPriorityDomainCard = {
  area_key: 'communication',
  title: '功能性沟通',
  priority_label: 'high',
  priority_score: 92,
  recommended_reason: '先把表达需求练起来。',
  current_stage: 'practice',
  current_difficulty: 'build',
  weekly_sessions_count: 3,
  has_today_task: true,
  current_status: '本周正在推进',
  improvement_value: '愿意表达需求的次数开始增加'
};

const detail: TrainingDomainDetail = {
  family_id: 1,
  area_key: 'communication',
  title: '功能性沟通',
  current_stage: 'practice',
  current_difficulty: 'build',
  importance_summary: '先让孩子更容易表达需求。',
  related_daily_challenges: ['要东西时拉扯'],
  reason_for_priority: ['能减少升级冲突'],
  current_risks: ['着急时会直接哭闹'],
  short_term_goal: {
    title: '短期目标',
    target: '本周先在 3 个场景里用句式表达需求',
    success_marker: '能在提醒下说出或指向目标'
  },
  medium_term_goal: {
    title: '中期目标',
    target: '两周后在家里能主动表达',
    success_marker: '大部分时候能主动表达需求'
  },
  training_principles: ['先给脚手架', '一次只练一句'],
  suggested_scenarios: ['点心时间', '拿玩具时'],
  parent_steps: ['先停 2 秒等孩子表达', '立刻回应正确表达', '结束时复述一次'],
  script_examples: ['你可以说：我要饼干。', '先指一指也可以。'],
  fallback_options: ['先退回到指物或图片表达'],
  cautions: ['不要连问多个问题'],
  progress: {
    current_stage: 'practice',
    current_difficulty: 'build',
    weekly_sessions_count: 3,
    total_completed_count: 11,
    recent_completion_rate: 68,
    recent_effective_rate: 74
  },
  recent_feedbacks: [
    {
      feedback_id: 12,
      date: '2026-03-10',
      task_instance_id: 22,
      task_key: 'ask-snack',
      task_title: '点心前先表达',
      area_key: 'communication',
      completion_status: 'done',
      child_response: 'engaged',
      difficulty_rating: 'just_right',
      helpfulness: 'helpful',
      obstacle_tag: 'none',
      safety_pause: false,
      effect_score: 82,
      parent_confidence: 8,
      notes: '今天只提醒一次就开口了'
    }
  ],
  adjustment_logs: []
};

test('computeDomainProgressPercent prefers detailed progress when available', () => {
  const percent = computeDomainProgressPercent(priorityDomain, detail);
  assert.equal(percent, 84);
});

test('buildTrainingPlanEntries puts todays task first and generates a date schedule', () => {
  const entries = buildTrainingPlanEntries(
    detail,
    {
      task_instance_id: 3,
      area_key: 'communication',
      area_title: '功能性沟通',
      title: '今天先练说出需求',
      today_goal: '在点心前说出想要的东西',
      training_scene: '点心时间',
      schedule_hint: '晚饭前',
      steps: ['先停一下', '等待表达', '立刻回应'],
      parent_script: '你可以说：我要饼干。',
      duration_minutes: 8,
      difficulty: 'build',
      materials: ['点心', '图片卡'],
      fallback_plan: '先退到指卡片。',
      coaching_tip: '孩子一表达就马上给结果。',
      status: 'pending',
      reminder_status: 'none',
      feedback_ready: false,
      highlight: true
    },
    '2026-03-11'
  );

  assert.equal(entries.length, 6);
  assert.equal(entries[0].date, '2026-03-11');
  assert.equal(entries[0].source, 'today_task');
  assert.equal(entries[1].date, '2026-03-13');
  assert.match(entries[2].title, /第 3 次练习/);
});

test('progress helpers expose recent moments and current summary', () => {
  const moments = buildProgressMoments(detail);
  const circles = buildCheckinCircles([
    { label: '周一', completed_count: 1, task_count: 2, completion_rate: 50 },
    { label: '周二', completed_count: 0, task_count: 1, completion_rate: 0 }
  ]);

  assert.equal(moments[0].effect_score, 82);
  assert.equal(circles[0].completed, true);
  assert.equal(circles[1].completed, false);
  assert.equal(summarizeCurrentSituation(detail), '今天只提醒一次就开口了');
});
