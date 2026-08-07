'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
  createRotatingFileLogger,
  installSingleInstanceGuard,
} = require('./electronRuntimeSafety');

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
});
