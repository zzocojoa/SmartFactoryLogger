'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
  createShutdownDiagnosticTrace,
  resolveShutdownDiagnosticDirectory,
} = require('./shutdownDiagnosticTrace');

test('shutdown diagnostic directory prefers an explicit launch argument', () => {
  const result = resolveShutdownDiagnosticDirectory(
    ['smart-factory.exe', '--sfl-shutdown-diagnostic-dir=C:\\trace-argument'],
    { SFL_SHUTDOWN_DIAGNOSTIC_DIR: 'C:\\trace-environment' }
  );
  assert.equal(result, path.resolve('C:\\trace-argument'));
});

test('shutdown diagnostic trace is disabled unless explicitly configured', () => {
  const trace = createShutdownDiagnosticTrace({ directoryPath: null });
  assert.equal(trace.enabled, false);
  assert.equal(trace.mark('ignored'), null);
});

test('shutdown diagnostic worker persists ordered boundary records', async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'sfl-shutdown-trace-'));
  const trace = createShutdownDiagnosticTrace({
    directoryPath: directory,
    sessionId: 'session:test',
    processId: 4321,
  });

  try {
    assert.equal(trace.enabled, true);
    const first = trace.mark('logger.console-start', { pid: 4321 });
    const second = trace.mark('backend.request-end-complete', { token: 'test-only' });
    assert.equal(await trace.waitFor(first), true);
    assert.equal(await trace.waitFor(second), true);
    assert.equal(await trace.close(), true);

    const rows = fs.readFileSync(trace.outputPath, 'utf8')
      .trim()
      .split(/\r?\n/)
      .map((line) => JSON.parse(line));
    const boundaries = rows.filter((row) => row.type === 'boundary');
    assert.deepEqual(boundaries.map((row) => row.sequence), [1, 2]);
    assert.deepEqual(boundaries.map((row) => row.phase), [
      'logger.console-start',
      'backend.request-end-complete',
    ]);
    assert.equal(boundaries[0].session_id, 'session:test');
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('Electron main drains the optional diagnostic trace before app quit', () => {
  const mainSource = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
  const closeIndex = mainSource.indexOf('await shutdownDiagnosticTrace.close(2_000)');
  const quitIndex = mainSource.indexOf('app.quit()', closeIndex);

  assert.notEqual(closeIndex, -1);
  assert.ok(quitIndex > closeIndex);
});
