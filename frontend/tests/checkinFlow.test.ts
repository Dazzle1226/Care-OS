import assert from 'node:assert/strict';
import test from 'node:test';

import { getInitialCheckinStep } from '../src/lib/checkinFlow.ts';

test('getInitialCheckinStep keeps intro for new daily checkin', () => {
  assert.equal(getInitialCheckinStep(), 'intro');
  assert.equal(getInitialCheckinStep({}), 'intro');
});

test('getInitialCheckinStep jumps into form when editing existing checkin', () => {
  assert.equal(
    getInitialCheckinStep({
      sensory_overload_level: 'medium',
      meltdown_count: 1
    }),
    'required-info'
  );
});
