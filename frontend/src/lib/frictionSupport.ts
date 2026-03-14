import type { ActionFlowContext } from './flow.ts';
import { sanitizeDisplayText } from './displayText.ts';
import type { FrictionScenario, FrictionSupportGenerateResponse } from './types.ts';

export const CUSTOM_FRICTION_SCENARIO_VALUE = '__custom__';

export const frictionScenarioOptions = [
  { value: 'transition', label: '过渡' },
  { value: 'bedtime', label: '睡前' },
  { value: 'homework', label: '作业' },
  { value: 'outing', label: '外出' },
  { value: 'meltdown', label: '崩溃' }
] as const satisfies ReadonlyArray<{ value: FrictionScenario; label: string }>;

function cleanList(values?: string[]) {
  if (!Array.isArray(values)) return [];
  return values
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item, index, list) => list.indexOf(item) === index);
}

export function normalizeFrictionScenario(value?: string | null): FrictionScenario {
  if (value === 'bedtime' || value === 'homework' || value === 'outing' || value === 'meltdown') {
    return value;
  }
  return 'transition';
}

export function resolveFrictionScenarioSelection(value: string): {
  scenarioSelection: FrictionScenario | typeof CUSTOM_FRICTION_SCENARIO_VALUE;
  scenario: FrictionScenario | null;
  shouldResetCustomScenarioName: boolean;
} {
  if (value === CUSTOM_FRICTION_SCENARIO_VALUE) {
    return {
      scenarioSelection: CUSTOM_FRICTION_SCENARIO_VALUE,
      scenario: null,
      shouldResetCustomScenarioName: false
    };
  }

  return {
    scenarioSelection: normalizeFrictionScenario(value),
    scenario: normalizeFrictionScenario(value),
    shouldResetCustomScenarioName: true
  };
}

function normalizeReviewScenario(value: FrictionScenario): ActionFlowContext['scenario'] {
  if (value === 'bedtime' || value === 'homework' || value === 'outing') {
    return value;
  }
  return 'transition';
}

interface FrictionActionContextInput {
  scenario: FrictionScenario;
  sourceScenario?: string;
}

export function buildFrictionActionContext(
  result: FrictionSupportGenerateResponse | null,
  input: FrictionActionContextInput
): ActionFlowContext | null {
  if (!result?.support) return null;
  const normalizedScenario = normalizeFrictionScenario(input.scenario);
  const sourceScenario = input.sourceScenario?.trim() || result.support.preset_label.trim() || normalizedScenario;

  return {
    source: 'scripts',
    scenario: normalizeReviewScenario(normalizedScenario),
    sourceScenario,
    title: sanitizeDisplayText(result.support.headline),
    summary: sanitizeDisplayText(result.support.situation_summary),
    cardIds: cleanList(result.support.source_card_ids),
    suggestedTriggers: cleanList(result.support.child_signals).slice(0, 4),
    suggestedFollowup: result.support.feedback_prompt.trim(),
    createdAt: new Date().toISOString()
  };
}

export function hasSchoolCollaborationMessage(message?: string | null) {
  return Boolean(message?.trim());
}
