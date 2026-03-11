import assert from 'node:assert/strict';
import test from 'node:test';

import { buildCheckinPayload } from '../src/lib/checkinPayload.ts';

test('buildCheckinPayload fills required fields that may be missing from partial input', () => {
  const payload = buildCheckinPayload({
    date: '2026-03-09',
    child_sleep_hours: 8,
    sensory_overload_level: 'light',
    meltdown_count: 0,
    caregiver_stress: 4,
    support_available: 'one',
    caregiver_sleep_quality: 6
  });

  assert.equal(payload.child_sleep_quality, null);
  assert.equal(payload.child_mood_state, 'stable');
  assert.equal(payload.transition_difficulty, null);
  assert.deepEqual(payload.sleep_issues, []);
  assert.deepEqual(payload.today_activities, []);
  assert.deepEqual(payload.today_learning_tasks, []);
});
