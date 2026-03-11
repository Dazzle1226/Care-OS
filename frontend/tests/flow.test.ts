import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createActionFlowContext,
  getActionSourceLabel,
  getScenarioLabel,
  normalizeScenario
} from '../src/lib/flow.ts';

test('normalizeScenario falls back to transition for unsupported values', () => {
  assert.equal(normalizeScenario('bedtime'), 'bedtime');
  assert.equal(normalizeScenario('meltdown'), 'transition');
  assert.equal(normalizeScenario('unknown'), 'transition');
});

test('createActionFlowContext trims strings and removes duplicate hints', () => {
  const context = createActionFlowContext({
    source: 'scripts',
    scenario: 'meltdown',
    title: '  先稳住现场  ',
    summary: '  只做一步  ',
    cardIds: [' CARD-1 ', 'CARD-1', '', 'CARD-2'],
    suggestedTriggers: [' 噪音 ', '噪音', '等待', ''],
    suggestedFollowup: '  继续保留提前预告  '
  });

  assert.deepEqual(context.cardIds, ['CARD-1', 'CARD-2']);
  assert.deepEqual(context.suggestedTriggers, ['噪音', '等待']);
  assert.equal(context.scenario, 'transition');
  assert.equal(context.title, '先稳住现场');
  assert.equal(context.summary, '只做一步');
  assert.equal(context.suggestedFollowup, '继续保留提前预告');
});

test('label helpers stay readable for navigation and review badges', () => {
  assert.equal(getActionSourceLabel('today'), '今日行动');
  assert.equal(getActionSourceLabel('plan'), '长期训练跟踪');
  assert.equal(getScenarioLabel('outing'), '外出');
  assert.equal(getScenarioLabel('meltdown'), '失控升级');
  assert.equal(getScenarioLabel('理发店'), '理发店');
});
