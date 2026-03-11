import assert from 'node:assert/strict';
import test from 'node:test';

import { createRequestGuard } from '../src/lib/requestGuard.ts';

test('request guard invalidates an older request after a newer state change', () => {
  const guard = createRequestGuard();
  const initialLoad = guard.begin();

  assert.equal(guard.isCurrent(initialLoad), true);

  guard.invalidate();

  assert.equal(guard.isCurrent(initialLoad), false);
});

test('request guard only treats the latest started request as current', () => {
  const guard = createRequestGuard();
  const first = guard.begin();
  const second = guard.begin();

  assert.equal(guard.isCurrent(first), false);
  assert.equal(guard.isCurrent(second), true);
});
