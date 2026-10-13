const { contextBridge, ipcRenderer } = require('electron');

function createRendererTimingPayload(payload = {}) {
  const timingPayload = { ...payload };
  if (
    typeof timingPayload.renderer_time_origin_ms === 'number' &&
    typeof timingPayload.renderer_now_ms === 'number' &&
    typeof timingPayload.renderer_epoch_ms === 'number'
  ) {
    return timingPayload;
  }

  const perf = globalThis.performance;
  if (
    perf &&
    typeof perf.now === 'function' &&
    typeof perf.timeOrigin === 'number'
  ) {
    const rendererNowMs = perf.now();
    timingPayload.renderer_time_origin_ms = Math.round(perf.timeOrigin * 10) / 10;
    timingPayload.renderer_now_ms = Math.round(rendererNowMs * 10) / 10;
    timingPayload.renderer_epoch_ms = Math.round((perf.timeOrigin + rendererNowMs) * 10) / 10;
  }
  return timingPayload;
}

function recordPreloadStartupEvent(name, payload) {
  return ipcRenderer.invoke('sfl:record-startup-event', name, createRendererTimingPayload(payload));
}

function onStartupStateChanged(listener) {
  if (typeof listener !== 'function') {
    return () => undefined;
  }
  const wrappedListener = (_event, state) => listener(state);
  ipcRenderer.on('sfl:startup-state-changed', wrappedListener);
  return () => ipcRenderer.removeListener('sfl:startup-state-changed', wrappedListener);
}

let shutdownRequested = false;
let shutdownAttempt = null;
const shutdownListeners = new Set();

ipcRenderer.on('sfl:prepare-shutdown', async (_event, attemptId) => {
  if (typeof attemptId !== 'string' || attemptId.length > 100) return;
  shutdownRequested = true;
  shutdownAttempt = attemptId;
  try {
    await Promise.all([...shutdownListeners].map((listener) => listener(true)));
    if (shutdownRequested && shutdownAttempt === attemptId) {
      ipcRenderer.send('sfl:renderer-shutdown-ready', { attemptId, ok: true });
    }
  } catch (_error) {
    if (shutdownRequested && shutdownAttempt === attemptId) {
      ipcRenderer.send('sfl:renderer-shutdown-ready', { attemptId, ok: false });
    }
  }
});

ipcRenderer.on('sfl:resume-after-shutdown-failure', () => {
  shutdownRequested = false;
  shutdownAttempt = null;
  for (const listener of shutdownListeners) {
    void Promise.resolve().then(() => listener(false)).catch((error) => {
      console.error('Renderer polling could not resume after shutdown failure', error);
    });
  }
});

function onShutdownStateChanged(listener) {
  if (typeof listener !== 'function') return () => undefined;
  shutdownListeners.add(listener);
  return () => shutdownListeners.delete(listener);
}

void recordPreloadStartupEvent('renderer.preload-start', {
  document_ready_state: globalThis.document?.readyState ?? null,
}).catch(() => undefined);

contextBridge.exposeInMainWorld('smartFactoryElectron', {
  getMemory: () => ipcRenderer.invoke('sfl:get-electron-memory'),
  getStartupState: () => ipcRenderer.invoke('sfl:get-startup-state'),
  onStartupStateChanged,
  isShuttingDown: () => shutdownRequested,
  onShutdownStateChanged,
  retryStartup: () => ipcRenderer.invoke('sfl:retry-startup'),
  continueStartupOffline: () => ipcRenderer.invoke('sfl:continue-startup-offline'),
  exitStartup: () => ipcRenderer.invoke('sfl:exit-startup'),
  testConnection: (payload) => ipcRenderer.invoke('sfl:test-connection', payload),
  recordStartupEvent: (name, payload) => recordPreloadStartupEvent(name, payload),
});

void recordPreloadStartupEvent('renderer.preload-bridge-exposed', {
  document_ready_state: globalThis.document?.readyState ?? null,
}).catch(() => undefined);
