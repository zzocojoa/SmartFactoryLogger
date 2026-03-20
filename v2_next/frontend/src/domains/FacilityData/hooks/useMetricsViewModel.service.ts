import { metricService } from '../api/metricService';

let sharedPollingWorker: Worker | null = null;
let sharedPollingWorkerRefCount = 0;

export const createPollingWorker = (): Worker => {
  if (sharedPollingWorker === null) {
    sharedPollingWorker = new Worker(new URL('../workers/polling.worker.ts', import.meta.url), { type: 'module' });
  }
  sharedPollingWorkerRefCount += 1;
  return sharedPollingWorker;
};

export const releasePollingWorker = (worker: Worker): void => {
  if (sharedPollingWorker === null) {
    worker.terminate();
    return;
  }
  if (worker !== sharedPollingWorker) {
    worker.terminate();
    return;
  }
  sharedPollingWorkerRefCount = Math.max(0, sharedPollingWorkerRefCount - 1);
  if (sharedPollingWorkerRefCount > 0) {
    return;
  }
  sharedPollingWorker.terminate();
  sharedPollingWorker = null;
};

export const startPollingWorker = (worker: Worker, intervalMs: number): void => {
  worker.postMessage({ type: 'START', payload: { interval: intervalMs } });
};

export const stopPollingWorker = (worker: Worker): void => {
  worker.postMessage({ type: 'STOP' });
};

export const fetchLatestMetricOnMainThreadWithLatency = async () => {
  const startedAt = performance.now();
  const data = await metricService.getLatest();
  const endedAt = performance.now();
  return {
    data,
    latency: endedAt - startedAt,
    timestamp: Date.now(),
  };
};
