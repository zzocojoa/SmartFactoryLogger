'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { parentPort, workerData } = require('node:worker_threads');

const outputPath = workerData.outputPath;

function append(record) {
  fs.appendFileSync(outputPath, `${JSON.stringify(record)}\n`, 'utf8');
}

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
append({
  schema_version: 'sfl-electron-shutdown-diagnostic-v1',
  type: 'trace.worker-ready',
  captured_at: new Date().toISOString(),
  worker_thread_id: require('node:worker_threads').threadId,
});
parentPort.postMessage({ type: 'ready' });

parentPort.on('message', (message) => {
  if (message?.type === 'mark') {
    append(message.record);
    parentPort.postMessage({ type: 'written', sequence: message.record.sequence });
    return;
  }

  if (message?.type === 'close') {
    append({
      schema_version: 'sfl-electron-shutdown-diagnostic-v1',
      type: 'trace.closed',
      captured_at: new Date().toISOString(),
    });
    parentPort.postMessage({ type: 'closed' });
    parentPort.close();
  }
});
