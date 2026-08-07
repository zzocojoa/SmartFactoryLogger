'use strict';

const fs = require('node:fs');

function createRotatingFileLogger(options) {
  const {
    logPath,
    maxBytes = 8 * 1024 * 1024,
    maxBackups = 3,
    fsImpl = fs,
    consoleTarget = console,
  } = options;

  if (typeof logPath !== 'string' || logPath.length === 0) {
    throw new TypeError('logPath must be a non-empty string.');
  }
  if (!Number.isSafeInteger(maxBytes) || maxBytes <= 0) {
    throw new TypeError('maxBytes must be a positive safe integer.');
  }
  if (!Number.isSafeInteger(maxBackups) || maxBackups < 0) {
    throw new TypeError('maxBackups must be a non-negative safe integer.');
  }

  let currentBytes = 0;
  try {
    currentBytes = fsImpl.statSync(logPath).size;
  } catch (_error) {
    currentBytes = 0;
  }

  const removeIfPresent = (target) => {
    try {
      fsImpl.unlinkSync(target);
    } catch (error) {
      if (error?.code !== 'ENOENT') {
        throw error;
      }
    }
  };

  const rotate = () => {
    if (maxBackups === 0) {
      removeIfPresent(logPath);
      currentBytes = 0;
      return;
    }
    removeIfPresent(`${logPath}.${maxBackups}`);
    for (let index = maxBackups - 1; index >= 1; index -= 1) {
      const source = `${logPath}.${index}`;
      const destination = `${logPath}.${index + 1}`;
      try {
        fsImpl.renameSync(source, destination);
      } catch (error) {
        if (error?.code !== 'ENOENT') {
          throw error;
        }
      }
    }
    try {
      fsImpl.renameSync(logPath, `${logPath}.1`);
    } catch (error) {
      if (error?.code !== 'ENOENT') {
        throw error;
      }
    }
    currentBytes = 0;
  };

  const log = (message) => {
    const text = String(message);
    try {
      const formatted = `[${new Date().toISOString()}] ${text}\n`;
      const bytes = Buffer.byteLength(formatted);
      if (currentBytes > 0 && currentBytes + bytes > maxBytes) {
        rotate();
      }
      fsImpl.appendFileSync(logPath, formatted);
      currentBytes += bytes;
      consoleTarget.log(text);
    } catch (error) {
      consoleTarget.error('Failed to write to Electron log file:', error);
    }
  };

  return { log, rotate, getCurrentBytes: () => currentBytes };
}

function installSingleInstanceGuard(app, options) {
  const {
    getMainWindow,
    logEvent = () => undefined,
    canShowWindow = () => true,
    deferWindowFocus = () => undefined,
  } = options;
  const acquired = app.requestSingleInstanceLock();
  if (!acquired) {
    logEvent('electron.single-instance-lock-denied', {});
    app.quit();
    return false;
  }

  logEvent('electron.single-instance-lock-acquired', {});
  app.on('second-instance', () => {
    const window = getMainWindow();
    const available = Boolean(window && !window.isDestroyed());
    logEvent('electron.second-instance-redirected', {
      window_available: available,
    });
    if (!available) {
      deferWindowFocus();
      return;
    }
    if (!canShowWindow(window)) {
      logEvent('electron.second-instance-focus-deferred', {});
      deferWindowFocus();
      return;
    }
    if (window.isMinimized()) {
      window.restore();
    }
    window.show();
    window.focus();
  });
  return true;
}

function isMatchingBackendHealth(health, expectedIdentity) {
  const expectedPid = expectedIdentity?.processId;
  const expectedGenerationId = expectedIdentity?.generationId;
  return Boolean(
    health &&
    health.running === true &&
    Number.isSafeInteger(expectedPid) &&
    expectedPid > 0 &&
    Number.isSafeInteger(health.backend_process_id) &&
    health.backend_process_id === expectedPid &&
    typeof expectedGenerationId === 'string' &&
    expectedGenerationId.length > 0 &&
    health.backend_generation_id === expectedGenerationId
  );
}

module.exports = {
  createRotatingFileLogger,
  isMatchingBackendHealth,
  installSingleInstanceGuard,
};
