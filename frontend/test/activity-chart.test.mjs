import assert from 'node:assert/strict';
import test from 'node:test';
import { activityBuckets } from '../.test-build/src/cases/ActivityChart.mjs';
import { resultTitle } from '../.test-build/src/cases/EvidenceResults.mjs';

test('activity chart counts event instants in UTC, includes zero days and excludes missing times', () => {
  const buckets = activityBuckets([{ observed_at_utc: '2026-01-01T23:30:00-02:00' }, { observed_at_utc: '2026-01-02T02:00:00Z' }, { observed_at_utc: '2026-01-04T00:00:00Z' }, {}, { observed_at_utc: 'invalid' }]);
  assert.deepEqual(buckets.map(b => [b.from, b.count]), [['2026-01-02', 2], ['2026-01-03', 0], ['2026-01-04', 1]]);
});
test('large time spans use at most 30 buckets without losing totals', () => {
  const buckets = activityBuckets([{ observed_at_utc: '2000-01-01T00:00:00Z' }, { observed_at_utc: '2026-01-01T00:00:00Z' }]);
  assert.ok(buckets.length <= 30); assert.equal(buckets.reduce((sum, b) => sum + b.count, 0), 2);
});
test('detections do not claim identity and transcript status is readable', () => {
  assert.match(resultTitle({kind:'image.detection',raw_value:'person:face [classifier]'}), /Face region · identity unknown/);
  assert.equal(resultTitle({kind:'transcript.status',normalized_value:'no_audio'}), 'No audio track');
});
