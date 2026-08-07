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
  if (!child?.pid) {
    return Promise.resolve({ stopped: true, reason: 'already_exited' });
  }

  if (hasProcessExited(child)) {
    const exitCode = child.exitCode ?? null;
    const signalCode = child.signalCode ?? null;
    if (exitCode === 0 && signalCode === null) {
      return Promise.resolve({
        stopped: true,
        reason: 'already_exited',
        exitCode,
        signalCode,
        forced: false,
      });
    }
    const error = new Error(
      `Backend exited before shutdown completed (code=${exitCode}, signal=${signalCode}).`
    );
    error.exitCode = exitCode;
    error.signalCode = signalCode;
    return Promise.reject(error);
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

    const finish = (reason, details = {}) => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      resolve({ stopped: true, reason, ...details });
    };

    const fail = (error) => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      reject(error);
    };

    function onClose(exitCode, signalCode) {
      if (forcing) {
        finish('forced_close', {
          exitCode: exitCode ?? null,
          signalCode: signalCode ?? null,
          forced: true,
        });
        return;
      }
      if (exitCode === 0 && !signalCode) {
        finish('close', {
          exitCode: 0,
          signalCode: null,
          forced: false,
        });
        return;
      }
      const error = new Error(
        `Backend PID ${child.pid} exited during graceful shutdown ` +
        `(code=${exitCode ?? 'null'}, signal=${signalCode ?? 'null'}).`
      );
      error.exitCode = exitCode ?? null;
      error.signalCode = signalCode ?? null;
      fail(error);
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
          finish('forced_exit_confirmed', {
            exitCode: child.exitCode ?? null,
            signalCode: child.signalCode ?? null,
            forced: true,
          });
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
      Promise.resolve()
        .then(() => requestGracefulStop())
        .catch((error) => {
          if (!settled) {
            const message = error instanceof Error ? error.message : String(error);
            log(`Backend graceful shutdown request failed for PID ${child.pid}: ${message}`);
          }
        });
    }
  });
}

function isVerifiedGracefulShutdownResult(result) {
  return Boolean(
    result?.stopped === true &&
    result.forced !== true &&
    (result.reason === 'close' || result.reason === 'already_exited') &&
    result.exitCode === 0 &&
    (result.signalCode === null || result.signalCode === undefined)
  );
}

function createBackendCloseoutGate() {
  let closeoutRequired = false;

  return {
    markBackendStarted() {
      closeoutRequired = true;
    },
    assertCanExitWithoutProcess() {
      if (closeoutRequired) {
        throw new Error(
          'Backend process exited before a graceful shutdown closeout was verified.'
        );
      }
    },
    acceptShutdownResult(result) {
      if (!isVerifiedGracefulShutdownResult(result)) {
        const reason = String(result?.reason ?? 'unknown');
        throw new Error(
          `Backend shutdown did not verify a graceful closeout (reason=${reason}).`
        );
      }
      closeoutRequired = false;
      return result;
    },
    isCloseoutRequired() {
      return closeoutRequired;
    },
  };
}

function createCloseoutVerifiedStop(options = {}) {
  const { stopProcess, closeoutGate } = options;
  if (typeof stopProcess !== 'function') {
    throw new TypeError('stopProcess must be a function.');
  }
  if (!closeoutGate || typeof closeoutGate.acceptShutdownResult !== 'function') {
    throw new TypeError('closeoutGate must accept shutdown results.');
  }

  return async (child) => {
    const result = await stopProcess(child);
    closeoutGate.acceptShutdownResult(result);
    return result;
  };
}

function createApplicationShutdownController(options) {
  const {
    setQuitting,
    prepareShutdown = () => undefined,
    shutdown,
    quitApplication,
    onFailure = () => undefined,
  } = options;

  if (typeof setQuitting !== 'function') {
    throw new TypeError('setQuitting must be a function.');
  }
  if (typeof shutdown !== 'function') {
    throw new TypeError('shutdown must be a function.');
  }
  if (typeof quitApplication !== 'function') {
    throw new TypeError('quitApplication must be a function.');
  }

  let activeShutdown = null;
  let shutdownComplete = false;

  const beginShutdown = () => {
    if (shutdownComplete) {
      return Promise.resolve(true);
    }
    if (activeShutdown) {
      return activeShutdown;
    }

    setQuitting(true);
    const shutdownAttempt = (async () => {
      try {
        prepareShutdown();
        await shutdown();
        shutdownComplete = true;
        quitApplication();
        return true;
      } catch (error) {
        shutdownComplete = false;
        setQuitting(false);
        onFailure(error);
        return false;
      }
    })();
    activeShutdown = shutdownAttempt;
    const releaseFailedAttempt = () => {
      if (!shutdownComplete && activeShutdown === shutdownAttempt) {
        activeShutdown = null;
      }
    };
    void shutdownAttempt.then(releaseFailedAttempt, releaseFailedAttempt);
    return shutdownAttempt;
  };

  const handleCloseRequest = (event) => {
    if (shutdownComplete) {
      return false;
    }
    if (!event || typeof event.preventDefault !== 'function') {
      throw new TypeError('close event must support preventDefault.');
    }
    event.preventDefault();
    void beginShutdown();
    return true;
  };

  return {
    beginShutdown,
    handleCloseRequest,
    isComplete: () => shutdownComplete,
  };
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
  createApplicationShutdownController,
  createBackendCloseoutGate,
  createBackendRestartController,
  createCloseoutVerifiedStop,
  hasProcessExited,
  isProcessMissingError,
  isVerifiedGracefulShutdownResult,
  stopProcessTree,
};
