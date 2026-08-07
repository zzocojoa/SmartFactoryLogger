'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
  createRotatingFileLogger,
  isMatchingBackendHealth,
  installSingleInstanceGuard,
} = require('./electronRuntimeSafety');

test('backend health recovery requires the authenticated child process identity', () => {
  const expectedIdentity = {
    processId: 4321,
    generationId: 'generation-123',
  };
  assert.equal(isMatchingBackendHealth({
    running: true,
    backend_process_id: 4321,
    backend_generation_id: 'generation-123',
  }, expectedIdentity), true);
  assert.equal(isMatchingBackendHealth({
    running: true,
    backend_process_id: 9999,
    backend_generation_id: 'generation-123',
  }, expectedIdentity), false);
  assert.equal(isMatchingBackendHealth({
    running: true,
    backend_process_id: 4321,
    backend_generation_id: 'stale-generation',
  }, expectedIdentity), false);
  assert.equal(isMatchingBackendHealth({ running: true }, expectedIdentity), false);
  assert.equal(isMatchingBackendHealth({
    running: false,
    backend_process_id: 4321,
    backend_generation_id: 'generation-123',
  }, expectedIdentity), false);
});

test('secondary Electron launch exits without creating another runtime', () => {
  const events = [];
  let quitCount = 0;
  const fakeApp = {
    requestSingleInstanceLock: () => false,
    quit: () => {
      quitCount += 1;
    },
    on: () => assert.fail('secondary instance must not install the primary handler'),
  };

  assert.equal(installSingleInstanceGuard(fakeApp, {
    getMainWindow: () => null,
    logEvent: (name, payload) => events.push({ name, payload }),
  }), false);
  assert.equal(quitCount, 1);
  assert.deepEqual(events, [{
    name: 'electron.single-instance-lock-denied',
    payload: {},
  }]);
});

test('primary Electron instance restores and focuses its window on a second launch', () => {
  const handlers = new Map();
  const calls = [];
  const fakeWindow = {
    isDestroyed: () => false,
    isMinimized: () => true,
    restore: () => calls.push('restore'),
    show: () => calls.push('show'),
    focus: () => calls.push('focus'),
  };
  const fakeApp = {
    requestSingleInstanceLock: () => true,
    quit: () => assert.fail('primary instance must remain active'),
    on: (name, handler) => handlers.set(name, handler),
  };

  assert.equal(installSingleInstanceGuard(fakeApp, {
    getMainWindow: () => fakeWindow,
    logEvent: () => undefined,
  }), true);
  handlers.get('second-instance')();
  assert.deepEqual(calls, ['restore', 'show', 'focus']);
});

test('primary Electron instance records a second launch when no window is available', () => {
  const handlers = new Map();
  const events = [];
  let deferredFocusCount = 0;
  const fakeApp = {
    requestSingleInstanceLock: () => true,
    on: (name, handler) => handlers.set(name, handler),
  };

  assert.equal(installSingleInstanceGuard(fakeApp, {
    getMainWindow: () => null,
    logEvent: (name, payload) => events.push({ name, payload }),
    deferWindowFocus: () => {
      deferredFocusCount += 1;
    },
  }), true);
  handlers.get('second-instance')();

  assert.equal(deferredFocusCount, 1);
  assert.deepEqual(events, [
    { name: 'electron.single-instance-lock-acquired', payload: {} },
    {
      name: 'electron.second-instance-redirected',
      payload: { window_available: false },
    },
  ]);
});

test('primary Electron instance defers focus while its startup window is hidden', () => {
  const handlers = new Map();
  const calls = [];
  const events = [];
  let deferredFocusCount = 0;
  const fakeWindow = {
    isDestroyed: () => false,
    isMinimized: () => false,
    restore: () => calls.push('restore'),
    show: () => calls.push('show'),
    focus: () => calls.push('focus'),
  };
  const fakeApp = {
    requestSingleInstanceLock: () => true,
    on: (name, handler) => handlers.set(name, handler),
  };

  assert.equal(installSingleInstanceGuard(fakeApp, {
    getMainWindow: () => fakeWindow,
    canShowWindow: () => false,
    deferWindowFocus: () => {
      deferredFocusCount += 1;
    },
    logEvent: (name, payload) => events.push({ name, payload }),
  }), true);
  handlers.get('second-instance')();

  assert.deepEqual(calls, []);
  assert.equal(deferredFocusCount, 1);
  assert.equal(events.at(-1).name, 'electron.second-instance-focus-deferred');
});

test('Electron logger rejects unsafe rotation bounds', () => {
  assert.throws(
    () => createRotatingFileLogger({ logPath: '' }),
    /logPath must be a non-empty string/
  );
  assert.throws(
    () => createRotatingFileLogger({ logPath: 'debug.log', maxBytes: 0 }),
    /maxBytes must be a positive safe integer/
  );
  assert.throws(
    () => createRotatingFileLogger({ logPath: 'debug.log', maxBackups: -1 }),
    /maxBackups must be a non-negative safe integer/
  );
});

test('Electron logger rotates oversized local logs and bounds retained backups', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'sfl-electron-log-'));
  const logPath = path.join(directory, 'debug_electron.log');
  try {
    fs.writeFileSync(logPath, 'x'.repeat(64), 'utf8');
    fs.writeFileSync(`${logPath}.1`, 'older-one', 'utf8');
    fs.writeFileSync(`${logPath}.2`, 'older-two', 'utf8');
    const logger = createRotatingFileLogger({
      logPath,
      maxBytes: 48,
      maxBackups: 2,
      consoleTarget: { log: () => undefined, error: () => undefined },
    });

    logger.log('new-session');

    assert.match(fs.readFileSync(logPath, 'utf8'), /new-session/);
    assert.equal(fs.readFileSync(`${logPath}.1`, 'utf8'), 'x'.repeat(64));
    assert.equal(fs.readFileSync(`${logPath}.2`, 'utf8'), 'older-one');
    assert.equal(fs.existsSync(`${logPath}.3`), false);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('Electron logger supports rotation without retaining backups', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'sfl-electron-log-zero-'));
  const logPath = path.join(directory, 'debug_electron.log');
  try {
    fs.writeFileSync(logPath, 'x'.repeat(64), 'utf8');
    const logger = createRotatingFileLogger({
      logPath,
      maxBytes: 48,
      maxBackups: 0,
      consoleTarget: { log: () => undefined, error: () => undefined },
    });

    logger.log('new-session');

    assert.match(fs.readFileSync(logPath, 'utf8'), /new-session/);
    assert.equal(fs.existsSync(`${logPath}.1`), false);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('Electron logger reports file write failures without crashing the caller', () => {
  const errors = [];
  const logger = createRotatingFileLogger({
    logPath: 'debug_electron.log',
    fsImpl: {
      statSync: () => ({ size: 0 }),
      appendFileSync: () => {
        throw new Error('disk unavailable');
      },
    },
    consoleTarget: {
      log: () => assert.fail('failed writes must not be reported as successful'),
      error: (...args) => errors.push(args),
    },
  });

  assert.doesNotThrow(() => logger.log('shutdown-start'));
  assert.equal(errors.length, 1);
  assert.match(String(errors[0][1]), /disk unavailable/);
});

test('shutdown evidence collector prioritizes the packaged Electron userData path', () => {
  const collector = fs.readFileSync(
    path.join(__dirname, 'scripts', 'collect_nsis_startup_trace.ps1'),
    'utf8'
  );
  const primary = collector.indexOf('smart-factory-logger-v2\\debug_electron.log');
  const legacy = collector.indexOf('SmartFactoryLogger\\debug_electron.log');

  assert.notEqual(primary, -1);
  assert.notEqual(legacy, -1);
  assert.ok(primary < legacy);
  assert.doesNotMatch(collector, /return \$candidates \| Sort-Object -Unique/);
  assert.match(collector, /"\$candidate\.1"/);
  assert.match(collector, /"\$candidate\.3"/);
  assert.match(collector, /log_paths = \$observedLogPaths\.ToArray\(\)/);
  assert.match(collector, /Sort-Object timestamp, event/);
  assert.match(collector, /session_id = \[string\]\$payload\.session_id/);
  assert.match(collector, /electron\.single-instance-lock-denied/);
  assert.match(collector, /electron\.single-instance-lock-acquired/);
  assert.match(collector, /-SessionId \$startupSessionId/);
  assert.match(collector, /\$launchedSessionPrefix = "\$\(\$process\.Id\)-"/);
  assert.match(collector, /-SessionIdPrefix \$launchedSessionPrefix/);
});
