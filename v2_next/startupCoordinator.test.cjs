'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');

const {
  BACKEND_PROGRESS_PREFIX,
  StartupCoordinator,
  createBackendProgressParser,
} = require('./startupCoordinator');

function createHarness(timeoutMs = 30_000) {
  let now = 1_000;
  let nextTimerId = 1;
  const timers = new Map();
  const states = [];
  const coordinator = new StartupCoordinator({
    sessionId: 'test-session',
    timeoutMs,
    now: () => now,
    setTimer: (callback) => {
      const id = nextTimerId++;
      timers.set(id, callback);
      return id;
    },
    clearTimer: (id) => {
      timers.delete(id);
    },
    onChange: (state) => states.push(state),
  });

  return {
    coordinator,
    states,
    advance: (elapsedMs) => {
      now += elapsedMs;
    },
    fireTimers: () => {
      const callbacks = [...timers.values()];
      timers.clear();
      callbacks.forEach((callback) => callback());
    },
    timerCount: () => timers.size,
  };
}

function markPaint(coordinator) {
  coordinator.handleRendererEvent('renderer.dashboard-ready', { ready_strategy: 'raf' });
}

test('normal startup reaches ready once with monotonic progress', () => {
  const harness = createHarness();
  harness.coordinator.start();
  markPaint(harness.coordinator);
  harness.coordinator.handleBackendStage('config_sync_ready');
  harness.coordinator.handleRendererEvent('renderer.backend-health-ready', { running: true });
  harness.coordinator.handleRendererEvent('renderer.first-data-snapshot', {
    status: 'Running',
    timestamp_present: true,
  });

  const state = harness.coordinator.getState();
  assert.equal(state.status, 'ready');
  assert.equal(state.progress, 100);
  assert.equal(state.backend_health_ready, true);
  assert.equal(state.data_snapshot_ready, true);
  assert.equal(state.data_running, true);
  assert.equal(state.dashboard_paint_ready, true);
  assert.equal(harness.timerCount(), 0);

  const progresses = harness.states.map((item) => item.progress);
  assert.deepEqual(progresses, [...progresses].sort((left, right) => left - right));
  assert.equal(harness.coordinator.handleBackendStage('lifespan_complete'), false);
  assert.equal(harness.coordinator.getState().sequence, state.sequence);
});

for (const dataStatus of ['Offline', 'Error']) {
  test(`timestamped ${dataStatus} data reveals a degraded dashboard without claiming running`, () => {
    const harness = createHarness();
    harness.coordinator.start();
    harness.coordinator.handleRendererEvent('renderer.backend-health-ready', { running: true });
    harness.coordinator.handleRendererEvent('renderer.first-data-snapshot', {
      status: dataStatus,
      timestamp_present: true,
    });
    markPaint(harness.coordinator);

    const state = harness.coordinator.getState();
    assert.equal(state.status, 'degraded');
    assert.equal(state.phase, 'degraded_ready');
    assert.equal(state.data_snapshot_ready, true);
    assert.equal(state.data_running, false);
    assert.equal(state.progress, 100);
  });
}

test('initializing and unverified snapshots do not satisfy the UI gate', () => {
  const harness = createHarness();
  harness.coordinator.start();

  assert.equal(harness.coordinator.handleRendererEvent('renderer.first-data-snapshot', {
    status: 'Initializing',
    timestamp_present: true,
  }), false);
  assert.equal(harness.coordinator.handleRendererEvent('renderer.first-data-snapshot', {
    status: 'Offline',
    timestamp_present: false,
  }), false);
  assert.equal(harness.coordinator.getState().data_snapshot_ready, false);
});

test('renderer readiness gates reject semantically invalid payloads', () => {
  const harness = createHarness();
  harness.coordinator.start();

  assert.equal(harness.coordinator.handleRendererEvent('renderer.backend-health-ready', {}), false);
  assert.equal(harness.coordinator.handleRendererEvent('renderer.backend-health-ready', {
    running: false,
  }), false);
  assert.equal(harness.coordinator.handleRendererEvent('renderer.dashboard-ready', {
    ready_strategy: 'timer',
  }), false);
  assert.equal(harness.coordinator.handleRendererEvent('renderer.first-data-snapshot', {
    status: 'Unexpected',
    timestamp_present: true,
  }), false);
  assert.equal(harness.coordinator.getState().backend_health_ready, false);
  assert.equal(harness.coordinator.getState().dashboard_paint_ready, false);
  assert.equal(harness.coordinator.getState().data_snapshot_ready, false);
});

test('timeout exposes recovery actions and late gates can still recover', () => {
  const harness = createHarness(100);
  harness.coordinator.start();
  harness.advance(100);
  harness.fireTimers();

  let state = harness.coordinator.getState();
  assert.equal(state.status, 'timeout');
  assert.equal(state.can_retry, true);
  assert.equal(state.can_continue_offline, true);
  assert.equal(state.can_exit, true);

  harness.coordinator.handleRendererEvent('renderer.backend-health-ready', { running: true });
  harness.coordinator.handleRendererEvent('renderer.first-live-data', {
    status: 'Running',
    timestamp_present: true,
  });
  markPaint(harness.coordinator);
  state = harness.coordinator.getState();
  assert.equal(state.status, 'ready');
  assert.equal(state.progress, 100);
});

test('backend failure is actionable before handoff and ignored after handoff', () => {
  const failedHarness = createHarness();
  failedHarness.coordinator.start();
  assert.equal(failedHarness.coordinator.failBackend('spawn_error'), true);
  assert.equal(failedHarness.coordinator.getState().status, 'error');
  assert.equal(failedHarness.coordinator.getState().can_retry, true);
  const failedSequence = failedHarness.coordinator.getState().sequence;
  assert.equal(failedHarness.coordinator.failBackend('duplicate_close'), false);
  assert.equal(failedHarness.coordinator.getState().sequence, failedSequence);

  const readyHarness = createHarness();
  readyHarness.coordinator.start();
  readyHarness.coordinator.handleRendererEvent('renderer.backend-health-ready', { running: true });
  readyHarness.coordinator.handleRendererEvent('renderer.first-live-data', {
    status: 'Running',
    timestamp_present: true,
  });
  markPaint(readyHarness.coordinator);
  assert.equal(readyHarness.coordinator.failBackend('late_close'), false);
  assert.equal(readyHarness.coordinator.getState().status, 'ready');
});

test('reset invalidates the old deadline and creates a fresh loading state', () => {
  const harness = createHarness(100);
  harness.coordinator.start();
  markPaint(harness.coordinator);
  const previousSequence = harness.coordinator.getState().sequence;
  harness.advance(25);
  harness.coordinator.reset('manual_retry');

  const state = harness.coordinator.getState();
  assert.equal(state.status, 'loading');
  assert.equal(state.phase, 'electron_ready');
  assert.equal(state.backend_health_ready, false);
  assert.equal(state.dashboard_paint_ready, false);
  assert.equal(state.sequence > previousSequence, true);
  assert.equal(harness.timerCount(), 1);

  harness.coordinator.handleRendererEvent('renderer.backend-health-ready', { running: true });
  harness.coordinator.handleRendererEvent('renderer.first-live-data', {
    status: 'Running',
    timestamp_present: true,
  });
  assert.equal(harness.coordinator.getState().status, 'loading');
  markPaint(harness.coordinator);
  assert.equal(harness.coordinator.getState().status, 'ready');
});

test('strict live-data fallback rejects an unverified renderer payload', () => {
  const harness = createHarness();
  harness.coordinator.start();

  assert.equal(harness.coordinator.handleRendererEvent('renderer.first-live-data', {}), false);
  assert.equal(harness.coordinator.handleRendererEvent('renderer.first-live-data', {
    status: 'Offline',
    timestamp_present: true,
  }), false);
  assert.equal(harness.coordinator.getState().data_snapshot_ready, false);
});

test('manual offline continuation is terminal and clears the deadline', () => {
  const harness = createHarness();
  harness.coordinator.start();
  assert.equal(harness.coordinator.continueOffline(), true);
  assert.equal(harness.coordinator.getState().status, 'degraded');
  assert.equal(harness.coordinator.getState().phase, 'continued_offline');
  assert.equal(harness.timerCount(), 0);
});

test('backend progress parser accepts fragmented and coalesced lines', () => {
  const stages = [];
  const rejected = [];
  const parser = createBackendProgressParser({
    onStage: (stage) => stages.push(stage),
    onRejected: (reason) => rejected.push(reason),
  });

  parser.push('ordinary log\nSFL_STARTUP_PRO');
  parser.push('GRESS {"stage":"lifespan_begin"}\r\n');
  parser.push(`${BACKEND_PROGRESS_PREFIX}{"stage":"csv_logger_ready"}\n`);
  parser.push(`${BACKEND_PROGRESS_PREFIX}{"stage":"config_sync_ready"}`);
  parser.flush();

  assert.deepEqual(stages, ['lifespan_begin', 'csv_logger_ready', 'config_sync_ready']);
  assert.deepEqual(rejected, []);
});

test('backend progress parser rejects malformed, unknown, extra-key, and oversized input', () => {
  const stages = [];
  const rejected = [];
  const parser = createBackendProgressParser({
    onStage: (stage) => stages.push(stage),
    onRejected: (reason) => rejected.push(reason),
  });

  parser.push(`${BACKEND_PROGRESS_PREFIX}{broken}\n`);
  parser.push(`${BACKEND_PROGRESS_PREFIX}{"stage":"unknown"}\n`);
  parser.push(`${BACKEND_PROGRESS_PREFIX}{"stage":"lifespan_begin","message":"unsafe"}\n`);
  parser.push('x'.repeat(8_193));

  assert.deepEqual(stages, []);
  assert.deepEqual(rejected, ['invalid_json', 'invalid_payload', 'invalid_payload', 'buffer_overflow']);
  assert.equal(parser.getBufferedLength(), 0);
});
