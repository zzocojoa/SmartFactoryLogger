'use strict';

const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const test = require('node:test');

const {
  createBackendRestartController,
  stopProcessTree,
} = require('./backendProcessLifecycle');

function createChild(pid = 1234) {
  const child = new EventEmitter();
  child.pid = pid;
  child.exitCode = null;
  child.signalCode = null;
  return child;
}

test('graceful termination resolves only after the child close event', async () => {
  const child = createChild();
  let gracefulRequests = 0;
  const resultPromise = stopProcessTree(child, {
    killTree: () => assert.fail('force kill must not run after graceful close'),
    requestGracefulStop: async () => {
      gracefulRequests += 1;
    },
    graceMs: 50,
    forceCloseMs: 50,
  });
  child.exitCode = 0;
  child.emit('close', 0);
  assert.deepEqual(await resultPromise, { stopped: true, reason: 'close' });
  assert.equal(gracefulRequests, 1);
});

test('graceful request failure escalates to SIGKILL and still waits for close', async () => {
  const child = createChild();
  const signals = [];
  const resultPromise = stopProcessTree(child, {
    killTree: (_pid, signal, callback) => {
      signals.push(signal);
      callback(null);
      setImmediate(() => {
        child.signalCode = 'SIGKILL';
        child.emit('close', null, 'SIGKILL');
      });
    },
    requestGracefulStop: async () => {
      throw new Error('backend endpoint unavailable');
    },
    graceMs: 5,
    forceCloseMs: 50,
  });
  assert.deepEqual(await resultPromise, { stopped: true, reason: 'close' });
  assert.deepEqual(signals, ['SIGKILL']);
});

test('forced termination errors reject instead of permitting replacement', async () => {
  const child = createChild();
  await assert.rejects(
    stopProcessTree(child, {
      killTree: (_pid, _signal, callback) => callback(new Error('forced access denied')),
      requestGracefulStop: async () => {
        throw new Error('backend endpoint unavailable');
      },
      graceMs: 5,
      forceCloseMs: 5,
    }),
    /forced stop failed/
  );
});

test('a confirmed missing process is a successful idempotent stop', async () => {
  const child = createChild();
  const error = new Error('no such process');
  error.code = 'ESRCH';
  const result = await stopProcessTree(child, {
    killTree: (_pid, _signal, callback) => callback(error),
    requestGracefulStop: async () => undefined,
    graceMs: 5,
  });
  assert.deepEqual(result, { stopped: true, reason: 'missing_after_force' });
});

test('successful SIGKILL callback without process close is rejected', async () => {
  const child = createChild();
  await assert.rejects(
    stopProcessTree(child, {
      killTree: (_pid, _signal, callback) => callback(null),
      requestGracefulStop: async () => undefined,
      graceMs: 5,
      forceCloseMs: 5,
    }),
    /did not close/
  );
});

test('concurrent retry requests share one stop and one replacement spawn', async () => {
  const previous = createChild();
  const replacement = createChild(4321);
  let current = previous;
  let releaseStop;
  let stopCount = 0;
  let startCount = 0;
  const controller = createBackendRestartController({
    getProcess: () => current,
    setProcess: (value) => {
      current = value;
    },
    stopProcess: async () => {
      stopCount += 1;
      await new Promise((resolve) => {
        releaseStop = resolve;
      });
    },
    startProcess: () => {
      startCount += 1;
      current = replacement;
      return replacement;
    },
  });

  const first = controller.restart();
  const second = controller.restart();
  assert.equal(first, second);
  releaseStop();
  assert.equal(await first, true);
  assert.equal(stopCount, 1);
  assert.equal(startCount, 1);
  assert.equal(current, replacement);
});

test('quitting during an active stop aborts the replacement spawn', async () => {
  const previous = createChild();
  let current = previous;
  let quitting = false;
  let releaseStop;
  let startCount = 0;
  const controller = createBackendRestartController({
    getProcess: () => current,
    setProcess: (value) => {
      current = value;
    },
    stopProcess: async () => new Promise((resolve) => {
      releaseStop = resolve;
    }),
    startProcess: () => {
      startCount += 1;
      return createChild(4321);
    },
    isQuitting: () => quitting,
  });

  const restarting = controller.restart();
  quitting = true;
  releaseStop();
  assert.equal(await restarting, false);
  assert.equal(startCount, 0);
  assert.equal(current, null);
});
