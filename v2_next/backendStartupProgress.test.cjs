'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
  BACKEND_PROGRESS_PREFIX,
  createAuthenticatedProgressParser,
  createBackendProgressFileTransport,
} = require('./backendStartupProgress');

test('progress file transport rejects a missing root directory', () => {
  assert.throws(
    () => createBackendProgressFileTransport({ rootDir: '  ' }),
    /rootDir is required/
  );
});

test('authenticated progress parser accepts only allowlisted stages with the launch token', () => {
  const stages = [];
  const rejected = [];
  const parser = createAuthenticatedProgressParser({
    expectedToken: 'trusted-token',
    onStage: (stage) => stages.push(stage),
    onRejected: (reason) => rejected.push(reason),
  });

  parser.push(`${BACKEND_PROGRESS_PREFIX}{"stage":"lifespan_begin","token":"trusted-token"}\n`);
  parser.push(`${BACKEND_PROGRESS_PREFIX}{"stage":"config_sync_ready","token":"wrong"}\n`);
  parser.push(`${BACKEND_PROGRESS_PREFIX}{"stage":"unknown","token":"trusted-token"}\n`);

  assert.deepEqual(stages, ['lifespan_begin']);
  assert.deepEqual(rejected, ['invalid_payload', 'invalid_payload']);
});

test('progress file transport reads fragmented appends and removes its private file', () => {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sfl-progress-'));
  const stages = [];
  const rejected = [];
  let pollCallback = null;
  let cleared = false;
  const transport = createBackendProgressFileTransport({
    rootDir,
    sessionId: 'session/with unsafe chars',
    token: 'trusted-token',
    nonce: 'fixednonce',
    onStage: (stage) => stages.push(stage),
    onRejected: (reason) => rejected.push(reason),
    setTimer: (callback) => {
      pollCallback = callback;
      return 7;
    },
    clearTimer: (timerId) => {
      assert.equal(timerId, 7);
      cleared = true;
    },
  });

  try {
    assert.equal(path.dirname(transport.filePath), rootDir);
    assert.equal(transport.environment.SFL_STARTUP_PROGRESS_TOKEN, 'trusted-token');
    fs.appendFileSync(
      transport.filePath,
      `${BACKEND_PROGRESS_PREFIX}{"stage":"lifespan_begin","token":"trusted-token"}`
    );
    pollCallback();
    assert.deepEqual(stages, []);
    fs.appendFileSync(transport.filePath, '\n');
    pollCallback();
    assert.deepEqual(stages, ['lifespan_begin']);
    assert.deepEqual(rejected, []);
  } finally {
    transport.close();
    assert.equal(cleared, true);
    assert.equal(fs.existsSync(transport.filePath), false);
    fs.rmSync(rootDir, { recursive: true, force: true });
  }
});
