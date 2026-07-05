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

void recordPreloadStartupEvent('renderer.preload-start', {
  document_ready_state: globalThis.document?.readyState ?? null,
}).catch(() => undefined);

contextBridge.exposeInMainWorld('smartFactoryElectron', {
  getMemory: () => ipcRenderer.invoke('sfl:get-electron-memory'),
  recordStartupEvent: (name, payload) => recordPreloadStartupEvent(name, payload),
});

void recordPreloadStartupEvent('renderer.preload-bridge-exposed', {
  document_ready_state: globalThis.document?.readyState ?? null,
}).catch(() => undefined);
