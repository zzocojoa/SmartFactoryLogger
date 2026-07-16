'use strict';

const fs = require('fs');
const path = require('path');
const { randomBytes, timingSafeEqual } = require('crypto');

const { BACKEND_STAGE_MILESTONES } = require('./startupCoordinator');

const BACKEND_PROGRESS_PREFIX = 'SFL_STARTUP_PROGRESS ';
const DEFAULT_POLL_INTERVAL_MS = 50;
const MAX_PROGRESS_FILE_BYTES = 8_192;
const MAX_PROGRESS_LINE_LENGTH = 1_024;

function safeTokenEqual(actual, expected) {
  if (typeof actual !== 'string' || typeof expected !== 'string') {
    return false;
  }
  const actualBuffer = Buffer.from(actual, 'utf8');
  const expectedBuffer = Buffer.from(expected, 'utf8');
  return actualBuffer.length === expectedBuffer.length &&
    timingSafeEqual(actualBuffer, expectedBuffer);
}

function createAuthenticatedProgressParser(options = {}) {
  const expectedToken = String(options.expectedToken ?? '');
  const onStage = typeof options.onStage === 'function' ? options.onStage : () => undefined;
  const onRejected = typeof options.onRejected === 'function'
    ? options.onRejected
    : () => undefined;
  let buffer = '';

  const processLine = (rawLine) => {
    const line = rawLine.trim();
    if (!line) {
      return;
    }
    if (line.length > MAX_PROGRESS_LINE_LENGTH) {
      onRejected('line_too_long');
      return;
    }
    if (!line.startsWith(BACKEND_PROGRESS_PREFIX)) {
      onRejected('invalid_prefix');
      return;
    }

    let payload;
    try {
      payload = JSON.parse(line.slice(BACKEND_PROGRESS_PREFIX.length));
    } catch (_error) {
      onRejected('invalid_json');
      return;
    }

    if (
      !payload ||
      typeof payload !== 'object' ||
      Array.isArray(payload) ||
      Object.keys(payload).length !== 2 ||
      typeof payload.stage !== 'string' ||
      !Object.prototype.hasOwnProperty.call(BACKEND_STAGE_MILESTONES, payload.stage) ||
      !safeTokenEqual(payload.token, expectedToken)
    ) {
      onRejected('invalid_payload');
      return;
    }

    onStage(payload.stage);
  };

  const push = (chunk) => {
    if (chunk === null || chunk === undefined) {
      return;
    }
    buffer += Buffer.isBuffer(chunk) ? chunk.toString('utf8') : String(chunk);
    while (true) {
      const lineFeedIndex = buffer.indexOf('\n');
      if (lineFeedIndex < 0) {
        break;
      }
      const rawLine = buffer.slice(0, lineFeedIndex).replace(/\r$/, '');
      buffer = buffer.slice(lineFeedIndex + 1);
      processLine(rawLine);
    }
    if (buffer.length > MAX_PROGRESS_FILE_BYTES) {
      buffer = '';
      onRejected('buffer_overflow');
    }
  };

  const flush = () => {
    if (buffer.length > 0) {
      processLine(buffer.replace(/\r$/, ''));
      buffer = '';
    }
  };

  return { push, flush };
}

function sanitizeSessionId(value) {
  const normalized = String(value ?? '').replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 120);
  return normalized || 'startup';
}

function buildBackendProgressEnvironment(baseEnvironment = {}, overrides = {}) {
  const environment = { ...baseEnvironment };
  delete environment.SFL_STARTUP_PROGRESS_PATH;
  delete environment.SFL_STARTUP_PROGRESS_TOKEN;
  return { ...environment, ...overrides };
}

function createBackendProgressFileTransport(options = {}) {
  const rootDirValue = String(options.rootDir ?? '').trim();
  if (!rootDirValue) {
    throw new TypeError('rootDir is required.');
  }
  const rootDir = path.resolve(rootDirValue);

  const onStage = typeof options.onStage === 'function' ? options.onStage : () => undefined;
  const onRejected = typeof options.onRejected === 'function'
    ? options.onRejected
    : () => undefined;
  const pollIntervalMs = Number.isFinite(options.pollIntervalMs)
    ? Math.max(10, Math.round(options.pollIntervalMs))
    : DEFAULT_POLL_INTERVAL_MS;
  const setTimer = options.setTimer ?? setInterval;
  const clearTimer = options.clearTimer ?? clearInterval;
  const token = typeof options.token === 'string' && options.token.length > 0
    ? options.token
    : randomBytes(32).toString('hex');
  const nonce = typeof options.nonce === 'string' && options.nonce.length > 0
    ? options.nonce
    : randomBytes(8).toString('hex');
  const sessionId = sanitizeSessionId(options.sessionId);

  fs.mkdirSync(rootDir, { recursive: true });
  const filePath = path.join(rootDir, `${sessionId}-${nonce}.jsonl`);
  fs.writeFileSync(filePath, '', { flag: 'wx', mode: 0o600 });

  const parser = createAuthenticatedProgressParser({
    expectedToken: token,
    onStage,
    onRejected,
  });
  let offset = 0;
  let closed = false;
  let timer = null;

  const removeProgressFile = () => {
    try {
      fs.unlinkSync(filePath);
    } catch (error) {
      if (error?.code !== 'ENOENT') {
        onRejected('file_cleanup_failed');
      }
    }
  };

  const stopPolling = () => {
    closed = true;
    if (timer !== null) {
      clearTimer(timer);
      timer = null;
    }
  };

  const poll = () => {
    if (closed) {
      return;
    }
    let stat;
    try {
      stat = fs.statSync(filePath);
    } catch (error) {
      if (error?.code !== 'ENOENT') {
        onRejected('file_stat_failed');
      }
      return;
    }
    if (stat.size < offset) {
      offset = stat.size;
      onRejected('file_truncated');
      return;
    }
    const unreadBytes = stat.size - offset;
    if (unreadBytes === 0) {
      return;
    }
    if (stat.size > MAX_PROGRESS_FILE_BYTES || unreadBytes > MAX_PROGRESS_FILE_BYTES) {
      offset = stat.size;
      onRejected('file_too_large');
      stopPolling();
      removeProgressFile();
      return;
    }

    let descriptor = null;
    try {
      descriptor = fs.openSync(filePath, 'r');
      const chunk = Buffer.alloc(unreadBytes);
      const bytesRead = fs.readSync(descriptor, chunk, 0, unreadBytes, offset);
      offset += bytesRead;
      parser.push(chunk.subarray(0, bytesRead));
    } catch (_error) {
      onRejected('file_read_failed');
    } finally {
      if (descriptor !== null) {
        fs.closeSync(descriptor);
      }
    }
  };

  timer = setTimer(poll, pollIntervalMs);
  if (typeof timer?.unref === 'function') {
    timer.unref();
  }

  const close = () => {
    if (closed) {
      return;
    }
    poll();
    parser.flush();
    if (closed) {
      return;
    }
    stopPolling();
    removeProgressFile();
  };

  return {
    environment: {
      SFL_STARTUP_PROGRESS_PATH: filePath,
      SFL_STARTUP_PROGRESS_TOKEN: token,
    },
    filePath,
    poll,
    close,
  };
}

module.exports = {
  BACKEND_PROGRESS_PREFIX,
  MAX_PROGRESS_FILE_BYTES,
  buildBackendProgressEnvironment,
  createAuthenticatedProgressParser,
  createBackendProgressFileTransport,
};
