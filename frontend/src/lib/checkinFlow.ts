import type { CheckinFormValues } from './checkinPayload';

export type CheckinStepEntry = 'intro' | 'required-info';

export function getInitialCheckinStep(initialValues?: Partial<CheckinFormValues>): CheckinStepEntry {
  if (!initialValues) return 'intro';
  return Object.keys(initialValues).length > 0 ? 'required-info' : 'intro';
}
