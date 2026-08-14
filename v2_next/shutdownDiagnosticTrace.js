'use strict';

const path = require('node:path');
const { Worker } = require('node:worker_threads');

const DIAGNOSTIC_ARGUMENT_PREFIX = '--sfl-shutdown-diagnostic-dir=';

function resolveShutdownDiagnosticDirectory(argv = process.argv, env = process.env) {
  const argument = argv.find((value) => (
    typeof value === 'string' && value.startsWith(DIAGNOSTIC_ARGUMENT_PREFIX)
  ));
  const configured = argument
    ? argument.slice(DIAGNOSTIC_ARGUMENT_PREFIX.length)
    : env.SFL_SHUTDOWN_DIAGNOSTIC_DIR;
  return typeof configured === 'string' && configured.trim().length > 0
    ? path.resolve(configured.trim())
    : null;
}

function sanitizeDetails(details) {
  if (!details || typeof details !== 'object' || Array.isArray(details)) {
    return {};
  }

  const sanitized = {};
  for (const [key, value] of Object.entries(details).slice(0, 24)) {
    if (value === null || typeof value === 'boolean' || typeof value === 'number') {
      sanitized[key] = value;
      continue;
    }
    if (typeof value === 'string') {
      sanitized[key] = value.slice(0, 240);
    }
  }
  return sanitized;
}

function createDisabledTrace(error = null) {
  return {
    enabled: false,
    outputPath: null,
    mark: () => null,
    waitFor: () => Promise.resolve(false),
    close: () => Promise.resolve(false),
    getLastError: () => error,
  };
}

function createShutdownDiagnosticTrace(options = {}) {
  const {
    directoryPath,
    sessionId,
    processId = process.pid,
    workerPath = path.join(__dirname, 'shutdownDiagnosticTraceWorker.js'),
    WorkerImpl = Worker,
  } = options;

  if (!directoryPath) {
    return createDisabledTrace();
  }

  const safeSessionId = String(sessionId ?? 'unknown').replace(/[^a-zA-Z0-9._-]/g, '_');
  const outputPath = path.join(
    path.resolve(directoryPath),
    `shutdown-boundary-${processId}-${safeSessionId}.jsonl`
  );

  let worker;
  try {
    worker = new WorkerImpl(workerPath, { workerData: { outputPath } });
  } catch (error) {
    return createDisabledTrace(error);
  }

  worker.unref?.();
  let sequence = 0;
  let lastError = null;
  let closed = false;
  let lastAcknowledgedSequence = 0;
  const waiters = new Map();

  const settleWaiter = (key, value) => {
    const waiter = waiters.get(key);
    if (!waiter) {
      return;
    }
    waiters.delete(key);
    clearTimeout(waiter.timer);
    waiter.resolve(value);
  };

  worker.on('message', (message) => {
    if (message?.type === 'written') {
      lastAcknowledgedSequence = Math.max(lastAcknowledgedSequence, message.sequence);
      settleWaiter(message.sequence, true);
    } else if (message?.type === 'closed') {
      closed = true;
      settleWaiter('close', true);
    }
  });
  worker.once('error', (error) => {
    lastError = error;
    for (const key of waiters.keys()) {
      settleWaiter(key, false);
    }
  });

  const waitFor = (key, timeoutMs = 2_000) => new Promise((resolve) => {
    if (key !== 'close' && Number.isInteger(key) && key <= lastAcknowledgedSequence) {
      resolve(true);
      return;
    }
    if (key === 'close' && closed) {
      resolve(true);
      return;
    }
    const timer = setTimeout(() => {
      waiters.delete(key);
      resolve(false);
    }, timeoutMs);
    waiters.set(key, { resolve, timer });
  });

  const mark = (phase, details = {}) => {
    if (closed || typeof phase !== 'string' || phase.length === 0) {
      return null;
    }
    sequence += 1;
    try {
      worker.postMessage({
        type: 'mark',
        record: {
          schema_version: 'sfl-electron-shutdown-diagnostic-v1',
          type: 'boundary',
          sequence,
          captured_at: new Date().toISOString(),
          process_id: processId,
          session_id: String(sessionId ?? ''),
          phase,
          details: sanitizeDetails(details),
        },
      });
      return sequence;
    } catch (error) {
      lastError = error;
      return null;
    }
  };

  const close = async (timeoutMs = 2_000) => {
    if (closed) {
      return true;
    }
    const completion = waitFor('close', timeoutMs);
    try {
      worker.postMessage({ type: 'close' });
    } catch (error) {
      lastError = error;
      settleWaiter('close', false);
    }
    return completion;
  };

  return {
    enabled: true,
    outputPath,
    mark,
    waitFor,
    close,
    getLastError: () => lastError,
  };
}

module.exports = {
  DIAGNOSTIC_ARGUMENT_PREFIX,
  createShutdownDiagnosticTrace,
  resolveShutdownDiagnosticDirectory,
};
