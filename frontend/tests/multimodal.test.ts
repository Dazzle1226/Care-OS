import assert from 'node:assert/strict';
import test from 'node:test';

import { getAutoIncludedIngestionIds, shouldAutoIncludeIngestion } from '../src/lib/multimodal.ts';

test('shouldAutoIncludeIngestion only accepts high-confidence reviewed inputs', () => {
  assert.equal(shouldAutoIncludeIngestion({ confidence: 0.81, manual_review_required: false }), true);
  assert.equal(shouldAutoIncludeIngestion({ confidence: 0.64, manual_review_required: false }), false);
  assert.equal(shouldAutoIncludeIngestion({ confidence: 0.92, manual_review_required: true }), false);
});

test('getAutoIncludedIngestionIds keeps only ingestions eligible for v2 generation', () => {
  const ids = getAutoIncludedIngestionIds([
    { ingestion_id: 11, confidence: 0.88, manual_review_required: false },
    { ingestion_id: 12, confidence: 0.53, manual_review_required: false },
    { ingestion_id: 13, confidence: 0.9, manual_review_required: true }
  ]);

  assert.deepEqual(ids, [11]);
});
