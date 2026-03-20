/* eslint-disable no-restricted-globals */
import { toDataMessage, toErrorMessage } from './polling.worker.mapper';
import type { WorkerInboundMessage } from './polling.worker.types';
import { fetchLatestMetricWithLatency } from './transport/polling.worker.transport';

const ctx: Worker = self as any;

const BACKOFF_MULTIPLIERS = [1, 2, 4, 10];

let timer: number | null = null;
let baseIntervalMs = 500;
let currentIntervalMs = 500;
let consecutiveFailures = 0;
let isRunning = false;

const clearTimer = () => {
  if (timer !== null) {
    clearTimeout(timer);
    timer = null;
  }
};

const resolveIntervalMs = (requestedIntervalMs: number, failureCount: number) => {
  if (failureCount <= 0) {
    return requestedIntervalMs;
  }
  const multiplierIndex = Math.min(failureCount, BACKOFF_MULTIPLIERS.length) - 1;
  const multiplier = BACKOFF_MULTIPLIERS[multiplierIndex];
  return requestedIntervalMs * multiplier;
};

const scheduleNext = () => {
  if (!isRunning) {
    return;
  }
  clearTimer();
  timer = self.setTimeout(tick, currentIntervalMs);
};

const tick = async () => {
  try {
    const payload = await fetchLatestMetricWithLatency();
    consecutiveFailures = 0;
    currentIntervalMs = baseIntervalMs;
    ctx.postMessage(
      toDataMessage({
        ...payload,
        poll_interval_ms: currentIntervalMs,
        failure_count: consecutiveFailures,
      })
    );
  } catch (err: any) {
    consecutiveFailures += 1;
    currentIntervalMs = resolveIntervalMs(baseIntervalMs, consecutiveFailures);
    ctx.postMessage(
      toErrorMessage({
        message: err?.message || 'Fetch failed',
        poll_interval_ms: currentIntervalMs,
        failure_count: consecutiveFailures,
      })
    );
  } finally {
    scheduleNext();
  }
};

ctx.onmessage = (e: MessageEvent<WorkerInboundMessage>) => {
  const { type, payload } = e.data;

  if (type === 'START') {
    if (payload?.interval) {
      baseIntervalMs = payload.interval;
    }
    currentIntervalMs = baseIntervalMs;
    consecutiveFailures = 0;
    isRunning = true;
    clearTimer();
    tick();
  } else if (type === 'STOP') {
    isRunning = false;
    clearTimer();
  }
};
