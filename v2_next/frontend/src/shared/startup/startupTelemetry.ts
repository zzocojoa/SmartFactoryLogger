import type {
  FactoryData,
  HealthSnapshot,
  SmartFactoryStartupEventName,
  SmartFactoryStartupEventPayload,
  SmartFactoryStartupEventResult,
} from '../types';

type OperationalReadyState = {
  backendHealthReady: boolean;
  liveDataReady: boolean;
  dashboardPaintReady: boolean;
  dashboardSurface: DashboardReadySurface | null;
  operationalReadyScheduled: boolean;
  operationalReadyRecorded: boolean;
  timeoutRecorded: boolean;
  timeoutId: number | null;
  firstFrameId: number | null;
  secondFrameId: number | null;
};

type StartupTelemetryWindow = Window & {
  __SF_STARTUP_EVENT_KEYS__?: Set<string>;
  __SF_OPERATIONAL_READY_STATE__?: OperationalReadyState;
};

type DashboardReadySurface = 'native' | 'scene';
type DashboardReadyStrategy = 'raf' | 'timeout-fallback' | 'timeout-no-raf';

const DASHBOARD_READY_FALLBACK_MS = 5000;
export const OPERATIONAL_READY_TIMEOUT_MS = 30000;
const OPERATIONAL_READY_GATES = [
  'backend_health',
  'live_data',
  'dashboard_paint',
] as const;

const getStartupEventKeys = (): Set<string> => {
  const startupWindow = window as StartupTelemetryWindow;
  if (!startupWindow.__SF_STARTUP_EVENT_KEYS__) {
    startupWindow.__SF_STARTUP_EVENT_KEYS__ = new Set<string>();
  }
  return startupWindow.__SF_STARTUP_EVENT_KEYS__;
};

const getOperationalReadyState = (): OperationalReadyState => {
  const startupWindow = window as StartupTelemetryWindow;
  if (!startupWindow.__SF_OPERATIONAL_READY_STATE__) {
    startupWindow.__SF_OPERATIONAL_READY_STATE__ = {
      backendHealthReady: false,
      liveDataReady: false,
      dashboardPaintReady: false,
      dashboardSurface: null,
      operationalReadyScheduled: false,
      operationalReadyRecorded: false,
      timeoutRecorded: false,
      timeoutId: null,
      firstFrameId: null,
      secondFrameId: null,
    };
  }
  return startupWindow.__SF_OPERATIONAL_READY_STATE__;
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

const getMissingOperationalReadyGates = (state: OperationalReadyState): string[] => {
  const missing: string[] = [];
  if (!state.backendHealthReady) {
    missing.push('backend_health');
  }
  if (!state.liveDataReady) {
    missing.push('live_data');
  }
  if (!state.dashboardPaintReady) {
    missing.push('dashboard_paint');
  }
  if (missing.length === 0 && !state.operationalReadyRecorded) {
    missing.push('operational_paint');
  }
  return missing;
};

const maybeScheduleOperationalReady = (): void => {
  const state = getOperationalReadyState();
  if (
    state.operationalReadyRecorded ||
    state.operationalReadyScheduled ||
    !state.backendHealthReady ||
    !state.liveDataReady ||
    !state.dashboardPaintReady ||
    typeof window.requestAnimationFrame !== 'function'
  ) {
    return;
  }

  state.operationalReadyScheduled = true;
  state.firstFrameId = window.requestAnimationFrame(() => {
    state.secondFrameId = window.requestAnimationFrame(() => {
      if (state.operationalReadyRecorded) {
        return;
      }

      state.operationalReadyRecorded = true;
      if (state.timeoutId !== null) {
        window.clearTimeout(state.timeoutId);
        state.timeoutId = null;
      }
      recordStartupEventOnce(
        'renderer.dashboard-operational-ready',
        'renderer.dashboard-operational-ready',
        {
          ready_strategy: 'raf',
          required_gates: OPERATIONAL_READY_GATES.join(','),
          surface: state.dashboardSurface,
          route: resolveRoute(),
        }
      );
    });
  });
};

export const armDashboardOperationalReadyTimeout = (): void => {
  if (!window.smartFactoryElectron?.recordStartupEvent) {
    return;
  }

  const state = getOperationalReadyState();
  if (state.timeoutId !== null || state.operationalReadyRecorded || state.timeoutRecorded) {
    return;
  }

  state.timeoutId = window.setTimeout(() => {
    state.timeoutId = null;
    if (state.operationalReadyRecorded || state.timeoutRecorded) {
      return;
    }

    state.timeoutRecorded = true;
    recordStartupEventOnce(
      'renderer.dashboard-operational-timeout',
      'renderer.dashboard-operational-timeout',
      {
        missing_gates: getMissingOperationalReadyGates(state).join(','),
        timeout_ms: OPERATIONAL_READY_TIMEOUT_MS,
        route: resolveRoute(),
      }
    );
  }, OPERATIONAL_READY_TIMEOUT_MS);
};

export const markBackendHealthReady = (health: HealthSnapshot | null): boolean => {
  if (!health) {
    return false;
  }

  const state = getOperationalReadyState();
  if (state.backendHealthReady) {
    return false;
  }

  state.backendHealthReady = true;
  recordStartupEventOnce(
    'renderer.backend-health-ready',
    'renderer.backend-health-ready',
    {
      running: health.running,
      driver_connected: health.driver_connected,
      runtime_kind: health.runtime_kind ?? null,
    }
  );
  maybeScheduleOperationalReady();
  return true;
};

export const isOperationalFactoryData = (data: FactoryData | null): data is FactoryData => {
  if (!data) {
    return false;
  }

  const timestampMs = data.timestamp_ms;
  return (
    typeof timestampMs === 'number' &&
    Number.isFinite(timestampMs) &&
    timestampMs > 0 &&
    typeof data.Time === 'string' &&
    data.Time.trim().length > 0 &&
    typeof data.Status === 'string' &&
    data.Status.trim().length > 0 &&
    data.Status.trim().toLowerCase() !== 'initializing'
  );
};

export const markFirstLiveDataReady = (data: FactoryData | null): boolean => {
  if (!isOperationalFactoryData(data)) {
    return false;
  }

  const state = getOperationalReadyState();
  if (state.liveDataReady) {
    return false;
  }

  state.liveDataReady = true;
  recordStartupEventOnce(
    'renderer.first-live-data',
    'renderer.first-live-data',
    {
      status: data.Status,
      timestamp_present: true,
    }
  );
  maybeScheduleOperationalReady();
  return true;
};

const markDashboardPaintReady = (surface: DashboardReadySurface): void => {
  const state = getOperationalReadyState();
  if (!state.dashboardPaintReady) {
    state.dashboardPaintReady = true;
    state.dashboardSurface = surface;
  }
  maybeScheduleOperationalReady();
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

    if (readyStrategy === 'raf') {
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
        timeoutId = null;
      }
      markDashboardPaintReady(surface);
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
