'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');

const {
  MAX_CONNECTION_TEST_PAYLOAD_BYTES,
  createBackendControlIpcHandlers,
  serializeConnectionTestPayload,
} = require('./backendControlIpc');

test('connection-test IPC accepts only the trusted main renderer', async () => {
  const requests = [];
  const trustedEvent = { trusted: true };
  const handlers = createBackendControlIpcHandlers({
    isTrustedSender: (event) => event === trustedEvent,
    requestConnectionTest: async (body) => {
      requests.push(body);
      return { results: { spot: { ok: true } } };
    },
  });

  await assert.rejects(
    handlers.testConnection({ trusted: false }, { spot: { url: 'http://spot.invalid' } }),
    /untrusted sender/
  );
  assert.deepEqual(
    await handlers.testConnection(trustedEvent, { spot: { url: 'http://spot.invalid' } }),
    { results: { spot: { ok: true } } }
  );
  assert.deepEqual(requests, ['{"spot":{"url":"http://spot.invalid"}}']);
});

test('connection-test IPC bounds and validates renderer payloads', () => {
  assert.throws(() => serializeConnectionTestPayload(null), /must be an object/);
  assert.throws(() => serializeConnectionTestPayload([]), /must be an object/);
  assert.throws(
    () => serializeConnectionTestPayload({
      spot: { url: 'x'.repeat(MAX_CONNECTION_TEST_PAYLOAD_BYTES) },
    }),
    /too large/
  );
});
