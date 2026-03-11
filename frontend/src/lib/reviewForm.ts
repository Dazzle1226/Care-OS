import type { ActionFlowContext, ReviewScenario } from './flow.ts';

export const CUSTOM_REVIEW_SCENARIO_VALUE = '__custom__';

export type ReviewScenarioSelection = ReviewScenario | typeof CUSTOM_REVIEW_SCENARIO_VALUE;

export interface ReviewScenarioDraft {
  scenario: ReviewScenario;
  scenarioSelection: ReviewScenarioSelection;
  customScenarioName: string;
}

export const reviewScenarioOptions = [
  { value: 'transition', label: '过渡' },
  { value: 'bedtime', label: '睡前' },
  { value: 'homework', label: '作业' },
  { value: 'outing', label: '外出' }
] as const satisfies ReadonlyArray<{ value: ReviewScenario; label: string }>;

function isReviewScenario(value?: string | null): value is ReviewScenario {
  return value === 'transition' || value === 'bedtime' || value === 'homework' || value === 'outing';
}

export function buildReviewScenarioDraft(
  context: Pick<ActionFlowContext, 'scenario' | 'sourceScenario'> | null
): ReviewScenarioDraft {
  const rawScenario = context?.sourceScenario?.trim() || context?.scenario;

  if (!rawScenario) {
    return {
      scenario: 'transition',
      scenarioSelection: 'transition',
      customScenarioName: ''
    };
  }

  if (isReviewScenario(rawScenario)) {
    return {
      scenario: rawScenario,
      scenarioSelection: rawScenario,
      customScenarioName: ''
    };
  }

  return {
    scenario: context?.scenario ?? 'transition',
    scenarioSelection: CUSTOM_REVIEW_SCENARIO_VALUE,
    customScenarioName: rawScenario
  };
}

export function resolveReviewScenarioValue(draft: ReviewScenarioDraft) {
  if (draft.scenarioSelection === CUSTOM_REVIEW_SCENARIO_VALUE) {
    return draft.customScenarioName.trim();
  }
  return draft.scenario;
}
