/* eslint-disable no-restricted-globals */
import { toDataMessage, toErrorMessage } from './polling.worker.mapper';
import type { WorkerInboundMessage } from './polling.worker.types';
import { fetchLatestMetricWithLatency } from './transport/polling.worker.transport';

const ctx: Worker = self as any;

let timer: number | null = null;
let intervalMs = 500;

const tick = async () => {
  try {
    const payload = await fetchLatestMetricWithLatency();
    ctx.postMessage(toDataMessage(payload));
  } catch (err: any) {
    ctx.postMessage(
      toErrorMessage({
        message: err?.message || 'Fetch failed',
      })
    );
  }
};

ctx.onmessage = (e: MessageEvent<WorkerInboundMessage>) => {
  const { type, payload } = e.data;

  if (type === 'START') {
    if (payload?.interval) {
      intervalMs = payload.interval;
    }
    if (timer) clearInterval(timer);
    tick();
    timer = self.setInterval(tick, intervalMs);
  } else if (type === 'STOP') {
    if (timer) clearInterval(timer);
    timer = null;
  }
};
