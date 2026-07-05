import type {
  SmartFactoryStartupEventName,
  SmartFactoryStartupEventPayload,
  SmartFactoryStartupEventResult,
} from '../types';

type StartupTelemetryWindow = Window & {
  __SF_STARTUP_EVENT_KEYS__?: Set<string>;
};

type DashboardReadySurface = 'native' | 'scene';
type DashboardReadyStrategy = 'raf' | 'timeout-fallback' | 'timeout-no-raf';

const DASHBOARD_READY_FALLBACK_MS = 5000;

const getStartupEventKeys = (): Set<string> => {
  const startupWindow = window as StartupTelemetryWindow;
  if (!startupWindow.__SF_STARTUP_EVENT_KEYS__) {
    startupWindow.__SF_STARTUP_EVENT_KEYS__ = new Set<string>();
  }
  return startupWindow.__SF_STARTUP_EVENT_KEYS__;
};

const resolveRoute = (): string => {
  const hash = window.location.hash || '';
  return hash || window.location.pathname || '/';
};

const createRendererTimingPayload = (
  payload: SmartFactoryStartupEventPayload = {}
): SmartFactoryStartupEventPayload => {
  if (
    typeof payload.renderer_time_origin_ms === 'number' &&
    typeof payload.renderer_now_ms === 'number' &&
    typeof payload.renderer_epoch_ms === 'number'
  ) {
    return payload;
  }

  if (
    typeof window.performance?.now !== 'function' ||
    typeof window.performance.timeOrigin !== 'number'
  ) {
    return payload;
  }

  const rendererNowMs = window.performance.now();
  return {
    ...payload,
    renderer_time_origin_ms: Math.round(window.performance.timeOrigin * 10) / 10,
    renderer_now_ms: Math.round(rendererNowMs * 10) / 10,
    renderer_epoch_ms: Math.round((window.performance.timeOrigin + rendererNowMs) * 10) / 10,
  };
};

export const recordStartupEvent = async (
  name: SmartFactoryStartupEventName,
  payload?: SmartFactoryStartupEventPayload
): Promise<SmartFactoryStartupEventResult & { skipped?: string }> => {
  const bridge = window.smartFactoryElectron;
  if (!bridge?.recordStartupEvent) {
    return { ok: false, skipped: 'bridge_unavailable' };
  }

  try {
    return await bridge.recordStartupEvent(name, createRendererTimingPayload(payload));
  } catch (error) {
    console.warn('Startup telemetry event failed', error);
    return { ok: false, reason: 'invoke_failed' };
  }
};

export const recordStartupEventOnce = (
  key: string,
  name: SmartFactoryStartupEventName,
  payload?: SmartFactoryStartupEventPayload
): void => {
  const recordedKeys = getStartupEventKeys();
  if (recordedKeys.has(key)) {
    return;
  }

  recordedKeys.add(key);
  void recordStartupEvent(name, payload);
};

export const recordDashboardReadyAfterPaint = (
  surface: DashboardReadySurface,
  payload: SmartFactoryStartupEventPayload = {}
): (() => void) => {
  let cancelled = false;
  let firstFrameId: number | null = null;
  let secondFrameId: number | null = null;
  let timeoutId: number | null = null;

  const recordReady = (readyStrategy: DashboardReadyStrategy): void => {
    if (cancelled) {
      return;
    }

    recordStartupEventOnce('renderer.dashboard-ready', 'renderer.dashboard-ready', {
      surface,
      route: resolveRoute(),
      ready_state: document.readyState,
      ready_strategy: readyStrategy,
      ...payload,
    });
  };

  if (typeof window.requestAnimationFrame === 'function') {
    timeoutId = window.setTimeout(() => recordReady('timeout-fallback'), DASHBOARD_READY_FALLBACK_MS);
    firstFrameId = window.requestAnimationFrame(() => {
      secondFrameId = window.requestAnimationFrame(() => recordReady('raf'));
    });
  } else {
    timeoutId = window.setTimeout(() => recordReady('timeout-no-raf'), 0);
  }

  return () => {
    cancelled = true;
    if (firstFrameId !== null) {
      window.cancelAnimationFrame(firstFrameId);
    }
    if (secondFrameId !== null) {
      window.cancelAnimationFrame(secondFrameId);
    }
    if (timeoutId !== null) {
      window.clearTimeout(timeoutId);
    }
  };
};
