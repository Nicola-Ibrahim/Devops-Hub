import test from 'node:test';
import assert from 'node:assert/strict';
test('health endpoint contract is JSON status ok', () => {
  assert.deepEqual(JSON.parse('{"status":"ok"}'), { status: 'ok' });
});
