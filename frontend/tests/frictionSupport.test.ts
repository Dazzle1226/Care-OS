import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildFrictionActionContext,
  hasSchoolCollaborationMessage,
  normalizeFrictionScenario
} from '../src/lib/frictionSupport.ts';
import type { FrictionSupportGenerateResponse } from '../src/lib/types.ts';

function buildResult(): FrictionSupportGenerateResponse {
  return {
    blocked: false,
    incident_id: 12,
    support: {
      preset_label: '过渡',
      headline: '先稳住现场',
      situation_summary: '先减要求，再给一个可接受出口。',
      child_signals: ['拉扯', '哭闹'],
      caregiver_signals: ['着急'],
      action_plan: [
        {
          title: '先停一下',
          action: '把要求降到一步',
          parent_script: '先停一下',
          why_it_fits: '先降低对抗'
        }
      ],
      donts: ['不要追问'],
      say_this: ['先停一下'],
      voice_guidance: ['先停一下'],
      exit_plan: ['退到安静处'],
      low_stim_mode: {
        active: false,
        headline: '先减刺激',
        actions: ['降低声音']
      },
      crisis_card: {
        title: '危机卡',
        badges: ['先稳住'],
        first_do: ['后退半步'],
        donts: ['不要拉扯'],
        say_this: ['我先陪你'],
        exit_plan: ['去走廊'],
        help_now: ['叫另一位家长']
      },
      respite_suggestion: {
        title: '换手 5 分钟',
        summary: '另一位家长先接手。',
        duration_minutes: 5,
        support_plan: '你先离开现场喝水。'
      },
      personalized_strategies: ['先给二选一'],
      school_message: '今天先降要求。',
      feedback_prompt: '做完后记结果和下次要保留的一件事。',
      citations: ['CARD-1'],
      source_card_ids: ['CARD-1']
    }
  };
}

test('buildFrictionActionContext forwards the review prompt and preserves source scenario', () => {
  const context = buildFrictionActionContext(buildResult(), { scenario: 'meltdown', sourceScenario: 'meltdown' });

  assert.ok(context);
  assert.equal(context?.source, 'scripts');
  assert.equal(context?.scenario, 'transition');
  assert.equal(context?.sourceScenario, 'meltdown');
  assert.equal(context?.suggestedFollowup, '做完后记结果和下次要保留的一件事。');
  assert.deepEqual(context?.suggestedTriggers, ['拉扯', '哭闹']);
});

test('hasSchoolCollaborationMessage ignores blank content', () => {
  assert.equal(hasSchoolCollaborationMessage('  '), false);
  assert.equal(hasSchoolCollaborationMessage('\n今天先降要求。'), true);
});

test('normalizeFrictionScenario clamps unknown values to transition', () => {
  assert.equal(normalizeFrictionScenario('outing'), 'outing');
  assert.equal(normalizeFrictionScenario('unknown'), 'transition');
  assert.equal(normalizeFrictionScenario(undefined), 'transition');
});

test('buildFrictionActionContext preserves a custom source scenario label', () => {
  const context = buildFrictionActionContext(buildResult(), { scenario: 'bedtime', sourceScenario: '理发店' });

  assert.ok(context);
  assert.equal(context?.scenario, 'bedtime');
  assert.equal(context?.sourceScenario, '理发店');
});

test('buildFrictionActionContext falls back to preset label for standard presets', () => {
  const context = buildFrictionActionContext(buildResult(), { scenario: 'transition' });

  assert.ok(context);
  assert.equal(context?.scenario, 'transition');
  assert.equal(context?.sourceScenario, '过渡');
});
