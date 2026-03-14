import assert from 'node:assert/strict';
import test from 'node:test';

import { createActionFlowContext } from '../src/lib/flow.ts';
import { getHomeSurfaceRecommendation } from '../src/lib/homeSurface.ts';

test('home surface prefers setup when family profile is missing', () => {
  const recommendation = getHomeSurfaceRecommendation({
    familyId: null,
    actionContext: null,
    isTodayFlowOpen: false
  });

  assert.equal(recommendation.kind, 'setup');
  assert.equal(recommendation.ctaLabel, '去家庭页建档');
});

test('home surface prefers active today flow once the main card is opened', () => {
  const recommendation = getHomeSurfaceRecommendation({
    familyId: 12,
    actionContext: null,
    isTodayFlowOpen: true
  });

  assert.equal(recommendation.kind, 'todayFlow');
  assert.match(recommendation.summary, /大卡片/);
});

test('home surface routes retained training context to training guidance', () => {
  const recommendation = getHomeSurfaceRecommendation({
    familyId: 12,
    actionContext: createActionFlowContext({
      source: 'plan',
      scenario: 'homework',
      title: '继续训练',
      summary: '先把今天的训练重点往下推。'
    }),
    isTodayFlowOpen: false
  });

  assert.equal(recommendation.kind, 'training');
  assert.equal(recommendation.ctaLabel, '打开训练方案');
});

test('home surface routes existing non-plan context to review', () => {
  const recommendation = getHomeSurfaceRecommendation({
    familyId: 12,
    actionContext: createActionFlowContext({
      source: 'scripts',
      scenario: 'transition',
      title: '先稳住现场',
      summary: '刚才那次动作还没收尾。'
    }),
    isTodayFlowOpen: false
  });

  assert.equal(recommendation.kind, 'review');
  assert.equal(recommendation.ctaLabel, '去轻复盘');
});
