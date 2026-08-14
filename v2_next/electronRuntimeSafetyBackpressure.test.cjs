'use strict';

const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

function waitForExit(child, timeoutMs) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve({ timedOut: true }), timeoutMs);
    child.once('exit', (code, signal) => {
      clearTimeout(timer);
      resolve({ timedOut: false, code, signal });
    });
  });
}

test('packaged-safe Electron logging returns when stdout is backpressured', {
  skip: process.platform !== 'win32',
}, async (t) => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'sfl-console-backpressure-'));
  const child = spawn(process.execPath, [
    path.join(__dirname, 'electronRuntimeSafetyBackpressure.fixture.cjs'),
    directory,
  ], {
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });
  t.after(() => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill();
    }
    fs.rmSync(directory, { recursive: true, force: true });
  });

  // Deliberately do not consume stdout. A synchronous Windows pipe write will
  // fill the pipe and expose a main-thread console logging dependency.
  const result = await waitForExit(child, 2_000);
  const traceFile = fs.readdirSync(directory)
    .find((name) => name.endsWith('.jsonl'));
  const rows = traceFile
    ? fs.readFileSync(path.join(directory, traceFile), 'utf8').trim().split(/\r?\n/)
    : [];
  const lastRow = rows.length > 0 ? JSON.parse(rows.at(-1)) : null;

  assert.equal(
    result.timedOut,
    false,
    `logger blocked with last diagnostic phase=${lastRow?.phase ?? lastRow?.type ?? 'missing'}`
  );
  assert.equal(result.code, 0);
});
