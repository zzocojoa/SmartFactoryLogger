'use strict';

const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const {
  createApplicationShutdownController,
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

test('native window close is held until application shutdown completes', async () => {
  let releaseShutdown;
  let shutdownCalls = 0;
  let quitCalls = 0;
  let quitting = false;
  const controller = createApplicationShutdownController({
    setQuitting: (value) => {
      quitting = value;
    },
    shutdown: async () => {
      shutdownCalls += 1;
      await new Promise((resolve) => {
        releaseShutdown = resolve;
      });
    },
    quitApplication: () => {
      quitCalls += 1;
    },
  });
  const firstEvent = {
    prevented: false,
    preventDefault() {
      this.prevented = true;
    },
  };

  assert.equal(controller.handleCloseRequest(firstEvent), true);
  assert.equal(firstEvent.prevented, true);
  assert.equal(quitting, true);
  assert.equal(shutdownCalls, 1);
  assert.equal(quitCalls, 0);

  const sharedShutdown = controller.beginShutdown();
  assert.equal(shutdownCalls, 1);
  releaseShutdown();
  assert.equal(await sharedShutdown, true);
  assert.equal(quitCalls, 1);

  const completedEvent = {
    prevented: false,
    preventDefault() {
      this.prevented = true;
    },
  };
  assert.equal(controller.handleCloseRequest(completedEvent), false);
  assert.equal(completedEvent.prevented, false);
});

test('Electron main wires native window close into the guarded shutdown path', () => {
  const mainText = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');

  assert.match(
    mainText,
    /mainWindow\.on\('close',\s*handleApplicationCloseRequest\)/
  );
  assert.match(
    mainText,
    /app\.on\('before-quit',\s*handleApplicationCloseRequest\)/
  );
});

test('failed application shutdown keeps the window open and permits a retry', async () => {
  let attempts = 0;
  let quitCalls = 0;
  const quittingStates = [];
  const failures = [];
  const controller = createApplicationShutdownController({
    setQuitting: (value) => quittingStates.push(value),
    shutdown: async () => {
      attempts += 1;
      if (attempts === 1) {
        throw new Error('closeout failed');
      }
    },
    quitApplication: () => {
      quitCalls += 1;
    },
    onFailure: (error) => failures.push(error.message),
  });

  assert.equal(await controller.beginShutdown(), false);
  assert.deepEqual(quittingStates, [true, false]);
  assert.deepEqual(failures, ['closeout failed']);
  assert.equal(quitCalls, 0);

  assert.equal(await controller.beginShutdown(), true);
  assert.deepEqual(quittingStates, [true, false, true]);
  assert.equal(attempts, 2);
  assert.equal(quitCalls, 1);
});

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
  assert.deepEqual(await resultPromise, {
    stopped: true,
    reason: 'close',
    exitCode: 0,
    signalCode: null,
    forced: false,
  });
  assert.equal(gracefulRequests, 1);
});

test('graceful non-zero backend exit rejects clean shutdown', async () => {
  const child = createChild();
  const resultPromise = stopProcessTree(child, {
    killTree: () => assert.fail('force kill must not run after backend close'),
    requestGracefulStop: async () => undefined,
    graceMs: 50,
    forceCloseMs: 50,
  });
  child.exitCode = 2;
  child.emit('close', 2, null);
  await assert.rejects(resultPromise, /code=2/);
});

test('pre-exited non-zero backend rejects clean shutdown before close is observed', async () => {
  const child = createChild();
  child.exitCode = 2;

  await assert.rejects(
    stopProcessTree(child, {
      killTree: () => assert.fail('force kill must not run for a pre-exited backend'),
      requestGracefulStop: async () => assert.fail('graceful stop must not run for a pre-exited backend'),
    }),
    /code=2/
  );
});

test('pre-exited zero backend remains an idempotent clean stop', async () => {
  const child = createChild();
  child.exitCode = 0;

  assert.deepEqual(
    await stopProcessTree(child, {
      killTree: () => assert.fail('force kill must not run for a pre-exited backend'),
      requestGracefulStop: async () => assert.fail('graceful stop must not run for a pre-exited backend'),
    }),
    {
      stopped: true,
      reason: 'already_exited',
      exitCode: 0,
      signalCode: null,
      forced: false,
    }
  );
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
  assert.deepEqual(await resultPromise, {
    stopped: true,
    reason: 'forced_close',
    exitCode: null,
    signalCode: 'SIGKILL',
    forced: true,
  });
  assert.deepEqual(signals, ['SIGKILL']);
});

test('synchronous graceful request errors stay inside the lifecycle until forced close', async () => {
  const child = createChild();
  const logs = [];
  let outerSettled = false;
  const resultPromise = stopProcessTree(child, {
    killTree: (_pid, signal, callback) => {
      assert.equal(signal, 'SIGKILL');
      callback(null);
      setImmediate(() => {
        child.signalCode = 'SIGKILL';
        child.emit('close', null, 'SIGKILL');
      });
    },
    requestGracefulStop: () => {
      throw new ReferenceError('http is not defined');
    },
    log: (message) => logs.push(message),
    graceMs: 20,
    forceCloseMs: 50,
  });
  resultPromise.then(
    () => {
      outerSettled = true;
    },
    () => {
      outerSettled = true;
    }
  );

  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(outerSettled, false);
  assert.deepEqual(await resultPromise, {
    stopped: true,
    reason: 'forced_close',
    exitCode: null,
    signalCode: 'SIGKILL',
    forced: true,
  });
  assert.equal(
    logs.some((message) => message.includes('http is not defined')),
    true
  );
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
