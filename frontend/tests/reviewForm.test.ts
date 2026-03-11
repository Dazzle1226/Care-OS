import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildReviewScenarioDraft,
  CUSTOM_REVIEW_SCENARIO_VALUE,
  resolveReviewScenarioValue
} from '../src/lib/reviewForm.ts';

test('buildReviewScenarioDraft keeps standard scenarios as direct selections', () => {
  const draft = buildReviewScenarioDraft({
    scenario: 'bedtime',
    sourceScenario: 'bedtime'
  });

  assert.deepEqual(draft, {
    scenario: 'bedtime',
    scenarioSelection: 'bedtime',
    customScenarioName: ''
  });
});

test('buildReviewScenarioDraft restores custom scenario from action context', () => {
  const draft = buildReviewScenarioDraft({
    scenario: 'transition',
    sourceScenario: '理发店'
  });

  assert.deepEqual(draft, {
    scenario: 'transition',
    scenarioSelection: CUSTOM_REVIEW_SCENARIO_VALUE,
    customScenarioName: '理发店'
  });
});

test('resolveReviewScenarioValue returns trimmed custom names', () => {
  assert.equal(
    resolveReviewScenarioValue({
      scenario: 'transition',
      scenarioSelection: CUSTOM_REVIEW_SCENARIO_VALUE,
      customScenarioName: '  上兴趣班  '
    }),
    '上兴趣班'
  );
});
