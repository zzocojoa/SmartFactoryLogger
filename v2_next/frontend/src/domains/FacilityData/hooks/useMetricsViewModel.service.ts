export const createPollingWorker = (): Worker => {
  return new Worker(new URL('../workers/polling.worker.ts', import.meta.url), { type: 'module' });
};

export const startPollingWorker = (worker: Worker, intervalMs: number): void => {
  worker.postMessage({ type: 'START', payload: { interval: intervalMs } });
};

export const stopPollingWorker = (worker: Worker): void => {
  worker.postMessage({ type: 'STOP' });
};
