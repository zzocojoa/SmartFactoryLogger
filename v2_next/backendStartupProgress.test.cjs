'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
  BACKEND_PROGRESS_PREFIX,
  MAX_PROGRESS_FILE_BYTES,
  buildBackendProgressEnvironment,
  createAuthenticatedProgressParser,
  createBackendProgressFileTransport,
} = require('./backendStartupProgress');

const TEST_TOKEN = 'a'.repeat(64);

test('backend environment removes inherited progress credentials', () => {
  const environment = buildBackendProgressEnvironment(
    {
      PATH: 'test-path',
      SFL_STARTUP_PROGRESS_PATH: 'C:\\untrusted\\progress.jsonl',
      SFL_STARTUP_PROGRESS_TOKEN: 'inherited-token',
    },
    { SFL_EMBEDDED_ELECTRON: '1' }
  );

  assert.deepEqual(environment, {
    PATH: 'test-path',
    SFL_EMBEDDED_ELECTRON: '1',
  });
});

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
    expectedToken: TEST_TOKEN,
    onStage: (stage) => stages.push(stage),
    onRejected: (reason) => rejected.push(reason),
  });

  parser.push(`${BACKEND_PROGRESS_PREFIX}{"stage":"lifespan_begin","token":"${TEST_TOKEN}"}\n`);
  parser.push(`${BACKEND_PROGRESS_PREFIX}{"stage":"config_sync_ready","token":"wrong"}\n`);
  parser.push(`${BACKEND_PROGRESS_PREFIX}{"stage":"unknown","token":"${TEST_TOKEN}"}\n`);

  assert.deepEqual(stages, ['lifespan_begin']);
  assert.deepEqual(rejected, ['invalid_payload', 'invalid_payload']);
});

test('authenticated progress parser enforces format and memory bounds', () => {
  const stages = [];
  const rejected = [];
  const parser = createAuthenticatedProgressParser({
    expectedToken: TEST_TOKEN,
    onStage: (stage) => stages.push(stage),
    onRejected: (reason) => rejected.push(reason),
  });

  parser.push('invalid-prefix\n');
  parser.push(`${BACKEND_PROGRESS_PREFIX}{not-json}\n`);
  parser.push(`${'x'.repeat(1_025)}\n`);
  parser.push('x'.repeat(MAX_PROGRESS_FILE_BYTES + 1));

  assert.deepEqual(stages, []);
  assert.deepEqual(rejected, [
    'invalid_prefix',
    'invalid_json',
    'line_too_long',
    'buffer_overflow',
  ]);
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
    token: TEST_TOKEN,
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
    assert.equal(transport.environment.SFL_STARTUP_PROGRESS_TOKEN, TEST_TOKEN);
    fs.appendFileSync(
      transport.filePath,
      `${BACKEND_PROGRESS_PREFIX}{"stage":"lifespan_begin","token":"${TEST_TOKEN}"}`
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

test('progress file transport rejects files beyond the bounded contract', () => {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sfl-progress-'));
  const stages = [];
  const rejected = [];
  const transport = createBackendProgressFileTransport({
    rootDir,
    token: TEST_TOKEN,
    nonce: 'oversized',
    onStage: (stage) => stages.push(stage),
    onRejected: (reason) => rejected.push(reason),
    setTimer: () => 9,
    clearTimer: () => undefined,
  });

  try {
    fs.appendFileSync(transport.filePath, Buffer.alloc(MAX_PROGRESS_FILE_BYTES + 1, 120));
    transport.poll();
    transport.poll();
    assert.deepEqual(stages, []);
    assert.deepEqual(rejected, ['file_too_large']);
    assert.equal(fs.existsSync(transport.filePath), false);
  } finally {
    transport.close();
    fs.rmSync(rootDir, { recursive: true, force: true });
  }
});
