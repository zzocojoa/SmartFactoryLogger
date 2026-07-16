'use strict';

function isProcessMissingError(error) {
  if (!error) {
    return false;
  }
  const code = typeof error.code === 'string' ? error.code.toUpperCase() : '';
  const message = String(error.message ?? error).toLowerCase();
  return (
    code === 'ESRCH' ||
    message.includes('no running instance') ||
    message.includes('not found') ||
    message.includes('no such process')
  );
}

function hasProcessExited(child) {
  return child.exitCode !== null && child.exitCode !== undefined ||
    child.signalCode !== null && child.signalCode !== undefined;
}

function stopProcessTree(child, options) {
  if (!child?.pid || hasProcessExited(child)) {
    return Promise.resolve({ stopped: true, reason: 'already_exited' });
  }

  const {
    killTree,
    requestGracefulStop,
    log = () => undefined,
    graceMs = 5_000,
    forceCloseMs = 5_000,
    setTimer = setTimeout,
    clearTimer = clearTimeout,
  } = options;

  if (typeof killTree !== 'function') {
    return Promise.reject(new TypeError('killTree must be a function.'));
  }

  return new Promise((resolve, reject) => {
    let settled = false;
    let forcing = false;
    let graceTimer = null;
    let forceCloseTimer = null;

    const cleanup = () => {
      if (graceTimer !== null) {
        clearTimer(graceTimer);
      }
      if (forceCloseTimer !== null) {
        clearTimer(forceCloseTimer);
      }
      child.removeListener('close', onClose);
    };

    const finish = (reason) => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      resolve({ stopped: true, reason });
    };

    const fail = (error) => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      reject(error);
    };

    function onClose() {
      finish('close');
    }

    const forceStop = () => {
      if (settled || forcing) {
        return;
      }
      forcing = true;
      log(`Backend graceful stop timed out for PID ${child.pid}; forcing termination.`);
      killTree(child.pid, 'SIGKILL', (error) => {
        if (settled) {
          return;
        }
        if (error) {
          if (isProcessMissingError(error)) {
            finish('missing_after_force');
            return;
          }
          fail(new Error(`Backend forced stop failed for PID ${child.pid}: ${error.message}`));
          return;
        }
        if (hasProcessExited(child)) {
          finish('forced_exit_confirmed');
          return;
        }
        forceCloseTimer = setTimer(() => {
          fail(new Error(`Backend PID ${child.pid} did not close after forced termination.`));
        }, forceCloseMs);
      });
    };

    child.once('close', onClose);
    graceTimer = setTimer(forceStop, graceMs);
    if (typeof requestGracefulStop === 'function') {
      Promise.resolve(requestGracefulStop()).catch((error) => {
        if (!settled) {
          log(`Backend graceful shutdown request failed for PID ${child.pid}: ${error.message}`);
        }
      });
    }
  });
}

function createBackendRestartController(options) {
  const {
    getProcess,
    setProcess,
    stopProcess,
    startProcess,
    beforeRestart = () => undefined,
    isQuitting = () => false,
  } = options;
  let activeRestart = null;

  const restart = () => {
    if (activeRestart) {
      return activeRestart;
    }

    activeRestart = (async () => {
      if (isQuitting()) {
        return false;
      }
      const previousProcess = getProcess();
      if (previousProcess) {
        await stopProcess(previousProcess);
      }
      if (getProcess() === previousProcess) {
        setProcess(null);
      }
      if (isQuitting()) {
        return false;
      }

      await beforeRestart();
      if (isQuitting()) {
        return false;
      }
      return Boolean(startProcess());
    })().finally(() => {
      activeRestart = null;
    });
    return activeRestart;
  };

  return {
    restart,
    waitForActiveRestart: () => activeRestart ?? Promise.resolve(false),
  };
}

module.exports = {
  createBackendRestartController,
  hasProcessExited,
  isProcessMissingError,
  stopProcessTree,
};
