import assert from 'node:assert/strict';
import test from 'node:test';

import { ApiError, isFamilyNotFoundError } from '../src/lib/api.ts';

test('isFamilyNotFoundError matches backend 404 family lookup failures', () => {
  const error = new ApiError({
    message: '404 Not Found: Family not found',
    status: 404,
    statusText: 'Not Found',
    detail: 'Family not found',
    bodyText: '{"detail":"Family not found"}'
  });

  assert.equal(isFamilyNotFoundError(error), true);
});

test('isFamilyNotFoundError ignores other API failures', () => {
  const error = new ApiError({
    message: '404 Not Found: Profile not found',
    status: 404,
    statusText: 'Not Found',
    detail: 'Profile not found',
    bodyText: '{"detail":"Profile not found"}'
  });

  assert.equal(isFamilyNotFoundError(error), false);
});
