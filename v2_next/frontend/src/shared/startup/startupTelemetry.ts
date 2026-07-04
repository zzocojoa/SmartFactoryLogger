import type {
  SmartFactoryStartupEventName,
  SmartFactoryStartupEventPayload,
  SmartFactoryStartupEventResult,
} from '../types';

type StartupTelemetryWindow = Window & {
  __SF_STARTUP_EVENT_KEYS__?: Set<string>;
};

type DashboardReadySurface = 'native' | 'scene';

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

export const recordStartupEvent = async (
  name: SmartFactoryStartupEventName,
  payload?: SmartFactoryStartupEventPayload
): Promise<SmartFactoryStartupEventResult & { skipped?: string }> => {
  const bridge = window.smartFactoryElectron;
  if (!bridge?.recordStartupEvent) {
    return { ok: false, skipped: 'bridge_unavailable' };
  }

  try {
    return await bridge.recordStartupEvent(name, payload);
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

  const recordReady = (): void => {
    if (cancelled) {
      return;
    }

    recordStartupEventOnce('renderer.dashboard-ready', 'renderer.dashboard-ready', {
      surface,
      route: resolveRoute(),
      ready_state: document.readyState,
      ...payload,
    });
  };

  if (typeof window.requestAnimationFrame === 'function') {
    firstFrameId = window.requestAnimationFrame(() => {
      secondFrameId = window.requestAnimationFrame(recordReady);
    });
  } else {
    timeoutId = window.setTimeout(recordReady, 0);
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
