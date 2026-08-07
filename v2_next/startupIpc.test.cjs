'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');

const {
  createStartupIpcHandlers,
  isTrustedStartupSender,
} = require('./startupIpc');

function createHarness(overrides = {}) {
  const mainFrame = { url: 'file:///C:/SmartFactory/frontend/index.html#/dashboard' };
  const webContents = { mainFrame };
  const mainWindow = { isDestroyed: () => false, webContents };
  const state = {
    can_retry: true,
    can_continue_offline: true,
    can_exit: true,
  };
  const accepted = [];
  const logs = [];
  let restartCount = 0;
  let recoveredCount = 0;
  let quitCount = 0;
  const handlers = createStartupIpcHandlers({
    getMainWindow: () => mainWindow,
    getExpectedDocumentUrl: () => 'file:///C:/SmartFactory/frontend/index.html',
    allowedEventNames: new Set([
      'renderer.preload-start',
      'renderer.splash-first-paint',
      'renderer.dashboard-ready',
      'renderer.backend-health-ready',
      'renderer.first-data-snapshot',
      'renderer.index-render',
    ]),
    eventCounts: new Map(),
    maxEventsPerName: 2,
    coordinator: {
      getState: () => ({ ...state }),
      handleRendererEvent: (name, payload) => {
        accepted.push({ name, payload });
        return payload.valid === true;
      },
      continueOffline: () => true,
    },
    sanitizePayload: (payload) => ({ valid: payload?.valid === true }),
    normalizeRejectedEventName: (name) => String(name),
    logStartupEvent: (name, payload) => logs.push({ name, payload }),
    recheckBackendHealth: async () => false,
    recoverHealthyBackend: async () => {
      recoveredCount += 1;
    },
    restartBackend: async () => {
      restartCount += 1;
      return true;
    },
    quitApplication: () => {
      quitCount += 1;
    },
    ...overrides,
  });

  return {
    handlers,
    trustedEvent: { sender: webContents, senderFrame: mainFrame },
    mainWindow,
    mainFrame,
    webContents,
    state,
    accepted,
    logs,
    getRestartCount: () => restartCount,
    getRecoveredCount: () => recoveredCount,
    getQuitCount: () => quitCount,
  };
}

test('startup IPC trusts only the expected main document and frame', () => {
  const harness = createHarness();
  assert.equal(isTrustedStartupSender(
    harness.trustedEvent,
    harness.mainWindow,
    'file:///C:/SmartFactory/frontend/index.html'
  ), true);
  assert.equal(isTrustedStartupSender(
    { sender: harness.webContents, senderFrame: { url: 'file:///C:/tmp/other.html' } },
    harness.mainWindow,
    'file:///C:/SmartFactory/frontend/index.html'
  ), false);
  assert.equal(isTrustedStartupSender(
    { sender: harness.webContents, senderFrame: { url: 'https://example.test/' } },
    harness.mainWindow,
    'file:///C:/SmartFactory/frontend/index.html'
  ), false);
  assert.equal(isTrustedStartupSender(
    { sender: {}, senderFrame: harness.mainFrame },
    harness.mainWindow,
    'file:///C:/SmartFactory/frontend/index.html'
  ), false);
});

test('startup event handler enforces allowlist, semantic payload, and event limits', async () => {
  const harness = createHarness();
  assert.deepEqual(
    await harness.handlers.recordStartupEvent(harness.trustedEvent, 'renderer.unknown', {}),
    { ok: false, reason: 'invalid_event' }
  );
  assert.deepEqual(
    await harness.handlers.recordStartupEvent(
      harness.trustedEvent,
      'renderer.backend-health-ready',
      { valid: false }
    ),
    { ok: false, reason: 'invalid_payload' }
  );
  assert.deepEqual(
    await harness.handlers.recordStartupEvent(
      harness.trustedEvent,
      'renderer.backend-health-ready',
      { valid: true, ignored: 'bounded by sanitizer' }
    ),
    { ok: true }
  );
  assert.deepEqual(
    await harness.handlers.recordStartupEvent(
      harness.trustedEvent,
      'renderer.backend-health-ready',
      { valid: true }
    ),
    { ok: false, reason: 'event_limit' }
  );
  assert.deepEqual(harness.accepted.at(-1), {
    name: 'renderer.backend-health-ready',
    payload: { valid: true },
  });
});

test('informational startup events remain observable without satisfying a state gate', async () => {
  const harness = createHarness();
  assert.deepEqual(
    await harness.handlers.recordStartupEvent(
      harness.trustedEvent,
      'renderer.index-render',
      { valid: false }
    ),
    { ok: true }
  );
  assert.equal(harness.accepted.length, 0);
  assert.equal(harness.logs.at(-1).name, 'renderer.index-render');
});

test('accepted splash paint event releases the bounded backend-start capability', async () => {
  const acceptedEvents = [];
  const harness = createHarness({
    onAcceptedEvent: (name) => acceptedEvents.push(name),
  });
  assert.deepEqual(await harness.handlers.recordStartupEvent(
    harness.trustedEvent,
    'renderer.splash-first-paint',
    {}
  ), { ok: true });
  assert.deepEqual(acceptedEvents, ['renderer.splash-first-paint']);
});

test('stateful events must belong to the current renderer document generation', async () => {
  let generation = null;
  const harness = createHarness({
    getRendererGeneration: () => generation,
    setRendererGeneration: (value) => {
      generation = value;
    },
    sanitizePayload: (payload) => ({
      valid: payload?.valid === true,
      renderer_time_origin_ms: payload?.renderer_time_origin_ms,
    }),
  });

  assert.deepEqual(await harness.handlers.recordStartupEvent(
    harness.trustedEvent,
    'renderer.preload-start',
    { renderer_time_origin_ms: 100 }
  ), { ok: true });
  assert.deepEqual(await harness.handlers.recordStartupEvent(
    harness.trustedEvent,
    'renderer.backend-health-ready',
    { valid: true, renderer_time_origin_ms: 100 }
  ), { ok: true });

  generation = null;
  assert.deepEqual(await harness.handlers.recordStartupEvent(
    harness.trustedEvent,
    'renderer.first-data-snapshot',
    { valid: true, renderer_time_origin_ms: 100 }
  ), { ok: false, reason: 'invalid_generation' });
});

test('privileged startup actions reject forged senders and unavailable actions', async () => {
  const harness = createHarness();
  const forged = { sender: {}, senderFrame: harness.mainFrame };
  assert.deepEqual(
    await harness.handlers.retryStartup(forged),
    { ok: false, reason: 'untrusted_sender' }
  );
  harness.state.can_retry = false;
  assert.deepEqual(
    await harness.handlers.retryStartup(harness.trustedEvent),
    { ok: false, reason: 'not_available' }
  );
  assert.equal(harness.getRestartCount(), 0);
});

test('trusted privileged startup actions call their bounded capabilities', async () => {
  const harness = createHarness();
  assert.deepEqual(await harness.handlers.retryStartup(harness.trustedEvent), { ok: true });
  assert.deepEqual(
    await harness.handlers.continueStartupOffline(harness.trustedEvent),
    { ok: true }
  );
  assert.deepEqual(await harness.handlers.exitStartup(harness.trustedEvent), { ok: true });
  assert.equal(harness.getRestartCount(), 1);
  assert.equal(harness.getQuitCount(), 1);
});

test('retry preserves a backend that becomes healthy during the bounded recheck', async () => {
  const harness = createHarness({
    recheckBackendHealth: async () => true,
  });

  assert.deepEqual(
    await harness.handlers.retryStartup(harness.trustedEvent),
    { ok: true, recovered: true, restarted: false }
  );
  assert.equal(harness.getRestartCount(), 0);
  assert.equal(harness.getRecoveredCount(), 1);
});

test('retry does not stop a backend after renderer gates recover concurrently', async () => {
  let harness;
  harness = createHarness({
    recheckBackendHealth: async () => {
      harness.state.can_retry = false;
      return false;
    },
  });

  assert.deepEqual(
    await harness.handlers.retryStartup(harness.trustedEvent),
    { ok: true, recovered: true, restarted: false }
  );
  assert.equal(harness.getRestartCount(), 0);
  assert.equal(harness.getRecoveredCount(), 0);
});

test('retry does not reset startup when health recovers after renderer gates complete', async () => {
  let harness;
  harness = createHarness({
    recheckBackendHealth: async () => {
      harness.state.can_retry = false;
      return true;
    },
  });

  assert.deepEqual(
    await harness.handlers.retryStartup(harness.trustedEvent),
    { ok: true, recovered: true, restarted: false }
  );
  assert.equal(harness.getRestartCount(), 0);
  assert.equal(harness.getRecoveredCount(), 0);
});

test('retry exposes a bounded failure instead of starting through a stop error', async () => {
  const harness = createHarness({
    restartBackend: async () => {
      throw new Error('termination denied');
    },
  });
  assert.deepEqual(
    await harness.handlers.retryStartup(harness.trustedEvent),
    { ok: false, reason: 'backend_stop_failed' }
  );
  assert.equal(harness.logs.at(-1).name, 'backend.restart-failed');
});
