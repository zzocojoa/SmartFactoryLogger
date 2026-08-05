'use strict';

const MAX_CONNECTION_TEST_PAYLOAD_BYTES = 16 * 1024;

function serializeConnectionTestPayload(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('Connection test payload must be an object.');
  }
  const serialized = JSON.stringify(payload);
  if (Buffer.byteLength(serialized, 'utf8') > MAX_CONNECTION_TEST_PAYLOAD_BYTES) {
    throw new Error('Connection test payload is too large.');
  }
  return serialized;
}

function createBackendControlIpcHandlers(options) {
  const {
    isTrustedSender,
    requestConnectionTest,
  } = options;

  return {
    testConnection: async (event, payload) => {
      if (!isTrustedSender(event)) {
        throw new Error('Connection test IPC rejected an untrusted sender.');
      }
      return requestConnectionTest(serializeConnectionTestPayload(payload));
    },
  };
}

module.exports = {
  MAX_CONNECTION_TEST_PAYLOAD_BYTES,
  createBackendControlIpcHandlers,
  serializeConnectionTestPayload,
};
