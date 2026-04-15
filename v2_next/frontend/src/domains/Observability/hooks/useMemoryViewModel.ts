import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { systemService } from '../api/systemService';
import type {
  FrontendErrorEntry,
  FrontendMemorySnapshot,
  FrontendMemorySupport,
  MemoryActionState,
  MemoryAlertItem,
  MemoryCollectorDeltaItem,
  MemoryCollectorItem,
  MemoryDetailsResponse,
  MemoryStateResponse,
  MemoryTabLeaderState,
  ObservabilityErrorsResponse,
  SettingsFormState,
  SpotPollingDiagnostics,
} from '../../../shared/types';
import { getAIDiagnostics } from '../../../AI/state/aiDiagnostics';
import { safeGetItem, safeRemoveItem, safeSetItem } from '../../../shared/utils/safeStorage';

const HISTORY_LIMIT = 360;
const COLLECTOR_HISTORY_LIMIT = 12;
const MEMORY_EXPORT_PATH_KEY = 'memory_export_path_v1';
const MEMORY_LEADER_KEY = 'memory_tab_leader_v2';
const MEMORY_SUMMARY_BROADCAST_KEY = 'memory_tab_summary_v2';
const REFRESH_INTERVAL_MS = 15000;
const LEADER_HEARTBEAT_MS = 4000;
const LEADER_TAKEOVER_MS = 30000;
const DELTA_WINDOW_SEC = 60;
const BACKEND_GROWTH_WARN_BYTES = 64 * 1024 * 1024;
const FRONTEND_GROWTH_WARN_BYTES = 32 * 1024 * 1024;
const GROWTH_WARN_RATIO = 0.2;
const PROFILER_LONG_RUNNING_SEC = 600;

interface UserAgentSpecificMemory {
  bytes: number;
  breakdown?: Array<{ bytes: number; attribution?: Array<{ scope: string }> }>;
}

interface PerformanceMemoryShape {
  usedJSHeapSize: number;
  totalJSHeapSize: number;
  jsHeapSizeLimit: number;
}

interface ExtendedPerformance extends Performance {
  memory?: PerformanceMemoryShape;
  measureUserAgentSpecificMemory?: () => Promise<UserAgentSpecificMemory>;
}

interface CollectorHistoryEntry {
  captured_at: number;
  items: MemoryCollectorItem[];
}

interface MemoryLeaderLock {
  tab_id: string;
  updated_at: number;
}

interface MemorySummaryBroadcast {
  tab_id: string;
  summary: MemoryStateResponse;
  sent_at: number;
}

interface MemoryDiagnosticsState {
  lastSummaryAt: number | null;
  lastDetailsAt: number | null;
  lastExportMetaAt: number | null;
  summaryRequestCount: number;
  detailsRequestCount: number;
  lastSummaryReason: string | null;
}

interface MemoryViewModelParams {
  enabled: boolean;
  seriesStats: { count: number; windowMs: number; maxPoints: number | null };
  timeSeriesAllFrame: unknown | null;
  layoutSnapshot: unknown | null;
  observabilityErrors: ObservabilityErrorsResponse | null;
  frontErrors: FrontendErrorEntry[];
  spotImageUrl: string;
  spotDiagnostics: SpotPollingDiagnostics;
  settingsForm: SettingsFormState | null;
  settingsPending: unknown;
  externalConfigPending: unknown;
}

interface UseMemoryViewModel {
  backendMemory: MemoryStateResponse | null;
  backendMemoryDetails: MemoryDetailsResponse | null;
  frontendMemory: FrontendMemorySnapshot | null;
  memorySummaryBusy: boolean;
  memoryDetailsBusy: boolean;
  memoryRefreshInFlight: boolean;
  profilerStartBusy: boolean;
  profilerStopBusy: boolean;
  memoryExportBusy: boolean;
  memoryExportPath: string | null;
  memoryRefreshIntervalMs: number;
  memoryLeader: MemoryTabLeaderState | null;
  memoryActionState: MemoryActionState;
  lastExportAt: number | null;
  lastSummaryAt: number | null;
  lastDetailsAt: number | null;
  lastExportMetaAt: number | null;
  summaryRequestCount: number;
  detailsRequestCount: number;
  lastSummaryReason: string | null;
  refreshMemory: () => Promise<void>;
  startMemoryProfiler: () => Promise<void>;
  stopMemoryProfiler: () => Promise<void>;
  captureMemorySnapshot: () => Promise<void>;
  exportMemory: () => Promise<string | null>;
  openMemoryExportFile: () => Promise<void>;
  openMemoryExportFolder: () => Promise<void>;
  copyMemoryExportPath: () => Promise<void>;
}

const estimateStringBytes = (value: string | null | undefined): number => {
  if (!value) {
    return 0;
  }
  return value.length * 2;
};

const estimateSerializedBytes = (value: unknown): number => {
  if (value == null) {
    return 0;
  }
  try {
    return JSON.stringify(value).length * 2;
  } catch {
    return 0;
  }
};

const estimateStructuredBytes = (value: unknown): number => {
  if (value == null) {
    return 0;
  }
  if (typeof value === 'string') {
    return estimateStringBytes(value);
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return 8;
  }
  return estimateSerializedBytes(value);
};

const readStorageBytes = (storage: Storage | null): number => {
  if (!storage) {
    return 0;
  }
  let total = 0;
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (!key) {
      continue;
    }
    total += estimateStringBytes(key) + estimateStringBytes(storage.getItem(key));
  }
  return total;
};

const buildCollector = (
  name: string,
  kind: string,
  bytes: number,
  items: number | null,
  note: string | null
): MemoryCollectorItem => ({
  name,
  kind,
  exactness: 'estimated',
  bytes,
  items,
  note,
});

const sortCollectors = (items: MemoryCollectorItem[]): MemoryCollectorItem[] => {
  return [...items].sort((left, right) => right.bytes - left.bytes);
};

const sortGrowth = (items: MemoryCollectorDeltaItem[]): MemoryCollectorDeltaItem[] => {
  return [...items].sort((left, right) => {
    if (right.delta_bytes !== left.delta_bytes) {
      return right.delta_bytes - left.delta_bytes;
    }
    return right.bytes - left.bytes;
  });
};

const readBrowserMemorySupport = async (): Promise<FrontendMemorySupport> => {
  if (typeof window === 'undefined') {
    return { mode: 'unsupported', supported: false };
  }
  const perf = performance as ExtendedPerformance;
  if (typeof perf.measureUserAgentSpecificMemory === 'function') {
    try {
      const result = await perf.measureUserAgentSpecificMemory();
      return {
        mode: 'uasm',
        supported: true,
        used_bytes: result.bytes,
        breakdown: (result.breakdown ?? []).map((item) => ({
          name: item.attribution?.map((entry) => entry.scope).join(', ') || 'unknown',
          bytes: item.bytes,
        })),
      };
    } catch {
      return { mode: 'unsupported', supported: false };
    }
  }
  if (perf.memory) {
    return {
      mode: 'performance-memory',
      supported: true,
      used_bytes: perf.memory.usedJSHeapSize,
      total_bytes: perf.memory.totalJSHeapSize,
      limit_bytes: perf.memory.jsHeapSizeLimit,
    };
  }
  return { mode: 'unsupported', supported: false };
};

const findHistoryPointAtOrBefore = <T extends { captured_at: number }>(
  history: T[],
  threshold: number
): T | null => {
  return [...history].reverse().find((item) => item.captured_at <= threshold) ?? null;
};

const buildCollectorGrowth = (
  currentCollectors: MemoryCollectorItem[],
  previousCollectors: MemoryCollectorItem[]
): MemoryCollectorDeltaItem[] => {
  const currentMap = new Map(currentCollectors.map((item) => [item.name, item]));
  const previousMap = new Map(previousCollectors.map((item) => [item.name, item]));
  const totalBytes = currentCollectors.reduce((sum, item) => sum + item.bytes, 0);
  const names = new Set<string>([
    ...currentCollectors.map((item) => item.name),
    ...previousCollectors.map((item) => item.name),
  ]);
  return sortGrowth(
    Array.from(names).map((name) => {
      const currentItem = currentMap.get(name);
      const previousItem = previousMap.get(name);
      const currentBytes = currentItem?.bytes ?? 0;
      const previousBytes = previousItem?.bytes ?? 0;
      const sourceItem = currentItem ?? previousItem;
      return {
        name,
        kind: sourceItem?.kind ?? 'unknown',
        exactness: sourceItem?.exactness ?? 'estimated',
        bytes: currentBytes,
        delta_bytes: currentBytes - previousBytes,
        share_ratio: totalBytes > 0 ? currentBytes / totalBytes : 0,
        items: sourceItem?.items ?? null,
        note: sourceItem?.note ?? null,
      };
    })
  ).slice(0, 12);
};

const buildFrontendAlerts = (
  backendMemory: MemoryStateResponse | null,
  frontendSnapshot: FrontendMemorySnapshot,
  refreshError: string | null
): MemoryAlertItem[] => {
  const alerts: MemoryAlertItem[] = [];
  const latestFrontendPoint = frontendSnapshot.history[frontendSnapshot.history.length - 1] ?? null;
  if (!frontendSnapshot.support.supported) {
    alerts.push({
      key: 'memory-api-unsupported',
      severity: 'warn',
      title: 'Memory API unsupported',
      detail: '브라우저 메모리 API를 지원하지 않아 앱 추정치만 표시합니다.',
    });
  }
  if (latestFrontendPoint) {
    const previousFrontendPoint = findHistoryPointAtOrBefore(
      frontendSnapshot.history,
      latestFrontendPoint.captured_at - DELTA_WINDOW_SEC
    );
    if (previousFrontendPoint) {
      const appDelta = latestFrontendPoint.app_bytes - previousFrontendPoint.app_bytes;
      const heapDelta = (latestFrontendPoint.heap_used_bytes ?? 0) - (previousFrontendPoint.heap_used_bytes ?? 0);
      const appRatio = previousFrontendPoint.app_bytes > 0 ? appDelta / previousFrontendPoint.app_bytes : 0;
      const heapRatio =
        (previousFrontendPoint.heap_used_bytes ?? 0) > 0
          ? heapDelta / (previousFrontendPoint.heap_used_bytes ?? 1)
          : 0;
      if (
        appDelta >= FRONTEND_GROWTH_WARN_BYTES ||
        heapDelta >= FRONTEND_GROWTH_WARN_BYTES ||
        appRatio >= GROWTH_WARN_RATIO ||
        heapRatio >= GROWTH_WARN_RATIO
      ) {
        alerts.push({
          key: 'frontend-growth',
          severity: 'warn',
          title: 'Frontend growth',
          detail: `1분 증가량 app ${Math.round(appDelta / 1024 / 1024)}MB / heap ${Math.round(heapDelta / 1024 / 1024)}MB`,
        });
      }
    }
  }
  if (backendMemory?.history?.length) {
    const latestBackendPoint = backendMemory.history[backendMemory.history.length - 1];
    const previousBackendPoint = findHistoryPointAtOrBefore(
      backendMemory.history,
      latestBackendPoint.captured_at - DELTA_WINDOW_SEC
    );
    if (previousBackendPoint) {
      const backendDelta = latestBackendPoint.rss_bytes - previousBackendPoint.rss_bytes;
      const backendRatio = previousBackendPoint.rss_bytes > 0 ? backendDelta / previousBackendPoint.rss_bytes : 0;
      if (backendDelta >= BACKEND_GROWTH_WARN_BYTES || backendRatio >= GROWTH_WARN_RATIO) {
        alerts.push({
          key: 'backend-growth',
          severity: 'warn',
          title: 'Backend growth',
          detail: `RSS 1분 증가량 ${Math.round(backendDelta / 1024 / 1024)}MB`,
        });
      }
    }
  }
  if (backendMemory?.profiler?.enabled && backendMemory.profiler.started_at) {
    const startedAtMs = Date.parse(backendMemory.profiler.started_at);
    if (!Number.isNaN(startedAtMs)) {
      const runtimeSec = Math.max(0, Math.floor(Date.now() / 1000 - startedAtMs / 1000));
      if (runtimeSec >= PROFILER_LONG_RUNNING_SEC) {
        alerts.push({
          key: 'profiler-long-running',
          severity: 'info',
          title: 'Profiler long-running',
          detail: `상세 추적이 ${Math.floor(runtimeSec / 60)}분 이상 활성화돼 있습니다.`,
        });
      }
    }
  }
  if (refreshError) {
    alerts.push({
      key: 'backend-stale',
      severity: 'error',
      title: 'Backend stale',
      detail: refreshError,
    });
  }
  return alerts;
};

const cloneFrontendSnapshot = (
  snapshot: FrontendMemorySnapshot,
  alerts: MemoryAlertItem[],
  refreshError: string | null,
  diagnostics: MemoryDiagnosticsState,
  lastExportAt: number | null
): FrontendMemorySnapshot => ({
  ...snapshot,
  alerts,
  refresh_error: refreshError,
  last_export_at: lastExportAt,
  last_summary_at: diagnostics.lastSummaryAt,
  last_details_at: diagnostics.lastDetailsAt,
  last_export_meta_at: diagnostics.lastExportMetaAt,
  summary_request_count: diagnostics.summaryRequestCount,
  details_request_count: diagnostics.detailsRequestCount,
  last_summary_reason: diagnostics.lastSummaryReason,
});

const readLeaderLock = (): MemoryLeaderLock | null => {
  try {
    const raw = window.localStorage.getItem(MEMORY_LEADER_KEY);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as MemoryLeaderLock;
  } catch {
    return null;
  }
};

const writeLeaderLock = (payload: MemoryLeaderLock): void => {
  window.localStorage.setItem(MEMORY_LEADER_KEY, JSON.stringify(payload));
};

const clearLeaderLock = (tabId: string): void => {
  const current = readLeaderLock();
  if (current?.tab_id === tabId) {
    safeRemoveItem(MEMORY_LEADER_KEY);
  }
};

const readSummaryBroadcast = (raw: string | null): MemorySummaryBroadcast | null => {
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as MemorySummaryBroadcast;
  } catch {
    return null;
  }
};

export const useMemoryViewModel = (params: MemoryViewModelParams): UseMemoryViewModel => {
  const {
    enabled,
    seriesStats,
    timeSeriesAllFrame,
    layoutSnapshot,
    observabilityErrors,
    frontErrors,
    spotImageUrl,
    spotDiagnostics,
    settingsForm,
    settingsPending,
    externalConfigPending,
  } = params;

  const tabIdRef = useRef<string>(
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `memory-tab-${Date.now()}-${Math.random().toString(16).slice(2)}`
  );
  const channelRef = useRef<BroadcastChannel | null>(null);
  const heartbeatTimerRef = useRef<number | null>(null);
  const pollingTimerRef = useRef<number | null>(null);
  const armSummaryTimerRef = useRef<(() => void) | null>(null);
  const refreshInFlightRef = useRef(false);
  const detailsInFlightRef = useRef(false);
  const exportMetaInFlightRef = useRef(false);
  const exportBusyRef = useRef(false);
  const profilerActionRef = useRef<'start' | 'stop' | null>(null);
  const executeSummarySyncRef = useRef<((reason: string) => Promise<void>) | null>(null);
  const summaryRef = useRef<MemoryStateResponse | null>(null);
  const frontendRef = useRef<FrontendMemorySnapshot | null>(null);
  const frontendHistoryRef = useRef<FrontendMemorySnapshot['history']>([]);
  const frontendCollectorHistoryRef = useRef<CollectorHistoryEntry[]>([]);
  const detailsLoadedRef = useRef(false);
  const exportMetaLoadedRef = useRef(false);
  const lastExportAtRef = useRef<number | null>(null);
  const enabledRef = useRef(enabled);
  const memoryLeaderRef = useRef<MemoryTabLeaderState | null>(null);
  const nextSummarySyncAtRef = useRef<number | null>(null);
  const summaryRequestCountRef = useRef(0);
  const detailsRequestCountRef = useRef(0);
  const lastSummaryReasonRef = useRef<string | null>(null);
  const lastSummaryAtRef = useRef<number | null>(null);
  const lastDetailsAtRef = useRef<number | null>(null);
  const lastExportMetaAtRef = useRef<number | null>(null);

  const [backendMemory, setBackendMemory] = useState<MemoryStateResponse | null>(null);
  const [backendMemoryDetails, setBackendMemoryDetails] = useState<MemoryDetailsResponse | null>(null);
  const [frontendMemory, setFrontendMemory] = useState<FrontendMemorySnapshot | null>(null);
  const [memorySummaryBusy, setMemorySummaryBusy] = useState(false);
  const [memoryDetailsBusy, setMemoryDetailsBusy] = useState(false);
  const [memoryRefreshInFlight, setMemoryRefreshInFlight] = useState(false);
  const [profilerStartBusy, setProfilerStartBusy] = useState(false);
  const [profilerStopBusy, setProfilerStopBusy] = useState(false);
  const [memoryExportBusy, setMemoryExportBusy] = useState(false);
  const [memoryExportPath, setMemoryExportPath] = useState<string | null>(() => safeGetItem(MEMORY_EXPORT_PATH_KEY));
  const [memoryLeader, setMemoryLeader] = useState<MemoryTabLeaderState | null>({
    tab_id: tabIdRef.current,
    mode: typeof window === 'undefined' ? 'standalone' : 'follower',
    leader_tab_id: null,
    last_broadcast_at: null,
  });
  const [memoryActionState, setMemoryActionState] = useState<MemoryActionState>({
    refresh: false,
    snapshot: false,
    profiler_action: null,
    export: false,
  });
  const [lastExportAt, setLastExportAt] = useState<number | null>(null);
  const [lastSummaryAt, setLastSummaryAt] = useState<number | null>(null);
  const [lastDetailsAt, setLastDetailsAt] = useState<number | null>(null);
  const [lastExportMetaAt, setLastExportMetaAt] = useState<number | null>(null);
  const [summaryRequestCount, setSummaryRequestCount] = useState(0);
  const [detailsRequestCount, setDetailsRequestCount] = useState(0);
  const [lastSummaryReason, setLastSummaryReason] = useState<string | null>(null);

  const collectorInputs = useMemo(
    () => ({
      seriesStats,
      timeSeriesAllFrame,
      layoutSnapshot,
      observabilityErrors,
      frontErrors,
      spotImageUrl,
      spotDiagnostics,
      settingsForm,
      settingsPending,
      externalConfigPending,
    }),
    [
      seriesStats,
      timeSeriesAllFrame,
      layoutSnapshot,
      observabilityErrors,
      frontErrors,
      spotImageUrl,
      spotDiagnostics,
      settingsForm,
      settingsPending,
      externalConfigPending,
    ]
  );

  const readDiagnostics = useCallback(
    (): MemoryDiagnosticsState => ({
      lastSummaryAt: lastSummaryAtRef.current,
      lastDetailsAt: lastDetailsAtRef.current,
      lastExportMetaAt: lastExportMetaAtRef.current,
      summaryRequestCount: summaryRequestCountRef.current,
      detailsRequestCount: detailsRequestCountRef.current,
      lastSummaryReason: lastSummaryReasonRef.current,
    }),
    []
  );

  const setLeaderState = useCallback((nextState: MemoryTabLeaderState): void => {
    memoryLeaderRef.current = nextState;
    setMemoryLeader(nextState);
  }, []);

  const clearSummaryTimer = useCallback((): void => {
    if (typeof window === 'undefined') {
      return;
    }
    if (pollingTimerRef.current !== null) {
      window.clearTimeout(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, []);

  const canPollSummary = useCallback((): boolean => {
    if (typeof document === 'undefined' || !enabledRef.current) {
      return false;
    }
    if (document.visibilityState === 'hidden') {
      return false;
    }
    const leaderMode = memoryLeaderRef.current?.mode;
    return leaderMode !== 'follower' && leaderMode !== 'recovering';
  }, []);

  const commitSummary = useCallback((summary: MemoryStateResponse): MemoryStateResponse => {
    summaryRef.current = summary;
    setBackendMemory(summary);
    return summary;
  }, []);

  const commitDetails = useCallback((details: MemoryDetailsResponse): MemoryDetailsResponse => {
    setBackendMemoryDetails(details);
    return details;
  }, []);

  const commitFrontend = useCallback((snapshot: FrontendMemorySnapshot): FrontendMemorySnapshot => {
    frontendHistoryRef.current = snapshot.history;
    frontendCollectorHistoryRef.current = [
      ...frontendCollectorHistoryRef.current.slice(-(COLLECTOR_HISTORY_LIMIT - 1)),
      { captured_at: snapshot.captured_at, items: snapshot.top_consumers },
    ];
    frontendRef.current = snapshot;
    setFrontendMemory(snapshot);
    return snapshot;
  }, []);

  const captureFrontendMemory = useCallback(async (): Promise<FrontendMemorySnapshot> => {
    const support = await readBrowserMemorySupport();
    const aiSnapshot = getAIDiagnostics();
    const localStorageBytes = typeof window !== 'undefined' ? readStorageBytes(window.localStorage) : 0;
    const sessionStorageBytes = typeof window !== 'undefined' ? readStorageBytes(window.sessionStorage) : 0;
    const frameCount =
      collectorInputs.timeSeriesAllFrame &&
      typeof collectorInputs.timeSeriesAllFrame === 'object' &&
      Array.isArray((collectorInputs.timeSeriesAllFrame as { fields?: unknown[] }).fields)
        ? Math.max(0, ((collectorInputs.timeSeriesAllFrame as { fields: unknown[] }).fields.length - 1))
        : 0;
    const timeSeriesBytes =
      collectorInputs.seriesStats.count * 96 + frameCount * 2048 + (collectorInputs.timeSeriesAllFrame ? 4096 : 0);
    const collectors = sortCollectors([
      buildCollector(
        'frontend.series_buffer',
        'buffer',
        collectorInputs.seriesStats.count * 96,
        collectorInputs.seriesStats.count,
        `window=${collectorInputs.seriesStats.windowMs}ms`
      ),
      buildCollector(
        'frontend.time_series_meta',
        'frame',
        timeSeriesBytes,
        frameCount,
        `frames=${frameCount} max=${collectorInputs.seriesStats.maxPoints ?? '--'}`
      ),
      buildCollector('frontend.layout_snapshot', 'layout', estimateStructuredBytes(collectorInputs.layoutSnapshot), collectorInputs.layoutSnapshot ? 1 : 0, 'saved dashboard layout'),
      buildCollector('frontend.observability_errors', 'list', estimateSerializedBytes(collectorInputs.observabilityErrors), collectorInputs.observabilityErrors?.items?.length ?? 0, 'backend error queue mirror'),
      buildCollector('frontend.browser_errors', 'list', estimateSerializedBytes(collectorInputs.frontErrors), collectorInputs.frontErrors.length, 'front error buffer'),
      buildCollector('frontend.spot_meta', 'image', estimateStringBytes(collectorInputs.spotImageUrl) + collectorInputs.spotDiagnostics.fetch_count * 24 + collectorInputs.spotDiagnostics.error_count * 24, collectorInputs.spotImageUrl ? 1 : 0, `fetch=${collectorInputs.spotDiagnostics.fetch_count} error=${collectorInputs.spotDiagnostics.error_count}`),
      buildCollector('frontend.ai_chat', 'chat', aiSnapshot.estimatedBytes, aiSnapshot.messageCount, `tools=${aiSnapshot.toolCount}`),
      buildCollector('frontend.settings_form', 'form', estimateSerializedBytes(collectorInputs.settingsForm), collectorInputs.settingsForm ? Object.keys(collectorInputs.settingsForm).length : 0, 'settings draft state'),
      buildCollector('frontend.pending_config', 'snapshot', estimateSerializedBytes({ settingsPending: collectorInputs.settingsPending, externalConfigPending: collectorInputs.externalConfigPending }), 2, 'pending config snapshots'),
      buildCollector('frontend.local_storage', 'storage', localStorageBytes, typeof window !== 'undefined' ? window.localStorage.length : 0, 'browser localStorage'),
      buildCollector('frontend.session_storage', 'storage', sessionStorageBytes, typeof window !== 'undefined' ? window.sessionStorage.length : 0, 'browser sessionStorage'),
    ]);
    const previousCollectors = frontendCollectorHistoryRef.current[frontendCollectorHistoryRef.current.length - 1]?.items ?? [];
    const appBytes = collectors.reduce((total, item) => total + item.bytes, 0);
    const capturedAt = Date.now() / 1000;
    return {
      captured_at: capturedAt,
      support,
      top_consumers: collectors.slice(0, 12),
      growth: buildCollectorGrowth(collectors, previousCollectors),
      alerts: [],
      last_refresh_at: Date.now(),
      last_export_at: lastExportAtRef.current,
      last_summary_at: lastSummaryAtRef.current,
      last_details_at: lastDetailsAtRef.current,
      last_export_meta_at: lastExportMetaAtRef.current,
      summary_request_count: summaryRequestCountRef.current,
      details_request_count: detailsRequestCountRef.current,
      last_summary_reason: lastSummaryReasonRef.current,
      refresh_error: null,
      history: [
        ...frontendHistoryRef.current.slice(-(HISTORY_LIMIT - 1)),
        {
          captured_at: capturedAt,
          app_bytes: appBytes,
          heap_used_bytes: support.used_bytes ?? null,
          heap_total_bytes: support.total_bytes ?? null,
        },
      ],
    };
  }, [collectorInputs]);

  const syncSummary = useCallback(async (reason: string): Promise<MemoryStateResponse> => {
    summaryRequestCountRef.current += 1;
    setSummaryRequestCount(summaryRequestCountRef.current);
    lastSummaryReasonRef.current = reason;
    setLastSummaryReason(reason);
    const summary = commitSummary(await systemService.getMemoryState());
    const capturedAt = Date.now();
    lastSummaryAtRef.current = capturedAt;
    setLastSummaryAt(capturedAt);
    return summary;
  }, [commitSummary]);

  const syncDetails = useCallback(async (): Promise<MemoryDetailsResponse> => {
    detailsRequestCountRef.current += 1;
    setDetailsRequestCount(detailsRequestCountRef.current);
    const details = commitDetails(await systemService.getMemoryDetails());
    const capturedAt = Date.now();
    lastDetailsAtRef.current = capturedAt;
    setLastDetailsAt(capturedAt);
    return details;
  }, [commitDetails]);

  const syncFrontend = useCallback(async (refreshError: string | null): Promise<void> => {
    const nextFrontend = await captureFrontendMemory();
    commitFrontend(
      cloneFrontendSnapshot(
        nextFrontend,
        buildFrontendAlerts(summaryRef.current, nextFrontend, refreshError),
        refreshError,
        readDiagnostics(),
        lastExportAtRef.current
      )
    );
  }, [captureFrontendMemory, commitFrontend, readDiagnostics]);

  const broadcastSummary = useCallback((summary: MemoryStateResponse): void => {
    if (typeof window === 'undefined') {
      return;
    }
    const payload: MemorySummaryBroadcast = {
      tab_id: tabIdRef.current,
      summary,
      sent_at: Date.now(),
    };
    channelRef.current?.postMessage(payload);
    window.localStorage.setItem(MEMORY_SUMMARY_BROADCAST_KEY, JSON.stringify(payload));
    setLeaderState({
      tab_id: tabIdRef.current,
      mode: memoryLeaderRef.current?.mode === 'standalone' ? 'standalone' : 'leader',
      leader_tab_id: tabIdRef.current,
      last_broadcast_at: payload.sent_at,
    });
  }, [setLeaderState]);

  const loadLatestMemoryExportPath = useCallback(async (): Promise<void> => {
    if (exportMetaInFlightRef.current) {
      return;
    }
    exportMetaInFlightRef.current = true;
    try {
      const response = await systemService.getLatestMemoryExportPath();
      const path = response.path ?? null;
      const capturedAt = Date.now();
      lastExportMetaAtRef.current = capturedAt;
      setLastExportMetaAt(capturedAt);
      setMemoryExportPath(path);
      if (path) {
        safeSetItem(MEMORY_EXPORT_PATH_KEY, path);
      }
      exportMetaLoadedRef.current = true;
      if (frontendRef.current) {
        commitFrontend(
          cloneFrontendSnapshot(
            frontendRef.current,
            buildFrontendAlerts(summaryRef.current, frontendRef.current, frontendRef.current.refresh_error ?? null),
            frontendRef.current.refresh_error ?? null,
            readDiagnostics(),
            lastExportAtRef.current
          )
        );
      }
    } catch {
      exportMetaLoadedRef.current = true;
    } finally {
      exportMetaInFlightRef.current = false;
    }
  }, [commitFrontend, readDiagnostics]);

  const loadDetails = useCallback(async (): Promise<void> => {
    if (detailsInFlightRef.current) {
      return;
    }
    detailsInFlightRef.current = true;
    setMemoryDetailsBusy(true);
    try {
      await syncDetails();
      detailsLoadedRef.current = true;
    } finally {
      detailsInFlightRef.current = false;
      setMemoryDetailsBusy(false);
    }
  }, [syncDetails]);

  const executeSummarySync = useCallback(async (reason: string): Promise<void> => {
    const leaderMode = memoryLeaderRef.current?.mode;
    if (leaderMode === 'follower' || leaderMode === 'recovering') {
      return;
    }
    if (refreshInFlightRef.current || profilerActionRef.current || exportBusyRef.current) {
      return;
    }
    refreshInFlightRef.current = true;
    setMemoryRefreshInFlight(true);
    setMemorySummaryBusy(true);
    try {
      const summary = await syncSummary(reason);
      if (memoryLeaderRef.current?.mode !== 'follower' && memoryLeaderRef.current?.mode !== 'recovering') {
        broadcastSummary(summary);
      }
      if (frontendRef.current) {
        commitFrontend(
          cloneFrontendSnapshot(
            frontendRef.current,
            buildFrontendAlerts(summary, frontendRef.current, frontendRef.current.refresh_error ?? null),
            frontendRef.current.refresh_error ?? null,
            readDiagnostics(),
            lastExportAtRef.current
          )
        );
      } else {
        await syncFrontend(null);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'backend memory refresh failed';
      if (frontendRef.current) {
        commitFrontend(
          cloneFrontendSnapshot(
            frontendRef.current,
            buildFrontendAlerts(summaryRef.current, frontendRef.current, message),
            message,
            readDiagnostics(),
            lastExportAtRef.current
          )
        );
      }
    } finally {
      refreshInFlightRef.current = false;
      setMemoryRefreshInFlight(false);
      setMemorySummaryBusy(false);
    }
  }, [broadcastSummary, commitFrontend, readDiagnostics, syncFrontend, syncSummary]);

  useEffect(() => {
    executeSummarySyncRef.current = executeSummarySync;
  }, [executeSummarySync]);

  const armSummaryTimer = useCallback((): void => {
    if (typeof window === 'undefined' || pollingTimerRef.current !== null) {
      return;
    }
    if (!enabledRef.current || nextSummarySyncAtRef.current == null) {
      return;
    }
    const delayMs = Math.max(0, nextSummarySyncAtRef.current - Date.now());
    pollingTimerRef.current = window.setTimeout(() => {
      pollingTimerRef.current = null;
      const runSummarySync = executeSummarySyncRef.current;
      if (!runSummarySync) {
        return;
      }
      if (!canPollSummary()) {
        nextSummarySyncAtRef.current = null;
        return;
      }
      const reason = lastSummaryReasonRef.current ?? 'auto-summary';
      void runSummarySync(reason).finally(() => {
        if (!canPollSummary()) {
          nextSummarySyncAtRef.current = null;
          return;
        }
        nextSummarySyncAtRef.current = Date.now() + REFRESH_INTERVAL_MS;
        lastSummaryReasonRef.current = 'auto-summary';
        setLastSummaryReason('auto-summary');
        armSummaryTimerRef.current?.();
      });
    }, delayMs);
  }, [canPollSummary]);

  useEffect(() => {
    armSummaryTimerRef.current = armSummaryTimer;
  }, [armSummaryTimer]);

  const scheduleSummarySync = useCallback(
    (reason: string, immediate: boolean): void => {
      if (typeof window === 'undefined' || !enabledRef.current) {
        return;
      }
      const now = Date.now();
      const currentNextAt = nextSummarySyncAtRef.current;
      const requestedNextAt = immediate ? now : now + REFRESH_INTERVAL_MS;
      if (currentNextAt == null) {
        nextSummarySyncAtRef.current = requestedNextAt;
      } else if (immediate) {
        nextSummarySyncAtRef.current = now;
      } else if (currentNextAt < now) {
        nextSummarySyncAtRef.current = requestedNextAt;
      }
      lastSummaryReasonRef.current = reason;
      setLastSummaryReason(reason);
      clearSummaryTimer();
      armSummaryTimerRef.current?.();
    },
    [clearSummaryTimer]
  );

  const refreshMemory = useCallback(async (): Promise<void> => {
    if (refreshInFlightRef.current) {
      return;
    }
    refreshInFlightRef.current = true;
    setMemoryRefreshInFlight(true);
    setMemorySummaryBusy(true);
    setMemoryDetailsBusy(true);
    setMemoryActionState((current) => ({ ...current, refresh: true }));
    try {
      await syncDetails();
      detailsLoadedRef.current = true;
      await syncFrontend(null);
    } catch (error) {
      await syncFrontend(error instanceof Error ? error.message : 'memory refresh failed');
      throw error;
    } finally {
      refreshInFlightRef.current = false;
      setMemoryRefreshInFlight(false);
      setMemorySummaryBusy(false);
      setMemoryDetailsBusy(false);
      setMemoryActionState((current) => ({ ...current, refresh: false }));
    }
    scheduleSummarySync('manual-refresh', true);
  }, [scheduleSummarySync, syncDetails, syncFrontend]);

  const captureMemorySnapshot = useCallback(async (): Promise<void> => {
    setMemoryActionState((current) => ({ ...current, snapshot: true }));
    setMemorySummaryBusy(true);
    setMemoryDetailsBusy(true);
    try {
      await systemService.captureMemorySnapshot();
      await syncDetails();
      detailsLoadedRef.current = true;
      await syncFrontend(null);
    } finally {
      setMemorySummaryBusy(false);
      setMemoryDetailsBusy(false);
      setMemoryActionState((current) => ({ ...current, snapshot: false }));
    }
    scheduleSummarySync('snapshot', true);
  }, [scheduleSummarySync, syncDetails, syncFrontend]);

  const runProfilerAction = useCallback(
    async (mode: 'start' | 'stop'): Promise<void> => {
      profilerActionRef.current = mode;
      setMemoryActionState((current) => ({ ...current, profiler_action: mode }));
      if (mode === 'start') {
        setProfilerStartBusy(true);
      } else {
        setProfilerStopBusy(true);
      }
      try {
        const nextProfilerState =
          mode === 'start' ? await systemService.startMemoryProfiler() : await systemService.stopMemoryProfiler();
        if (summaryRef.current) {
          commitSummary({
            ...summaryRef.current,
            profiler: nextProfilerState,
          });
        }
        await syncDetails();
        detailsLoadedRef.current = true;
        if (frontendRef.current) {
          commitFrontend(
            cloneFrontendSnapshot(
              frontendRef.current,
              buildFrontendAlerts(summaryRef.current, frontendRef.current, frontendRef.current.refresh_error ?? null),
              frontendRef.current.refresh_error ?? null,
              readDiagnostics(),
              lastExportAtRef.current
            )
          );
        }
      } finally {
        profilerActionRef.current = null;
        setProfilerStartBusy(false);
        setProfilerStopBusy(false);
        setMemoryActionState((current) => ({ ...current, profiler_action: null }));
      }
      scheduleSummarySync(`profiler-${mode}`, true);
    },
    [commitFrontend, commitSummary, readDiagnostics, scheduleSummarySync, syncDetails]
  );

  const startMemoryProfiler = useCallback(async (): Promise<void> => runProfilerAction('start'), [runProfilerAction]);
  const stopMemoryProfiler = useCallback(async (): Promise<void> => runProfilerAction('stop'), [runProfilerAction]);

  const exportMemory = useCallback(async (): Promise<string | null> => {
    if (exportBusyRef.current) {
      return memoryExportPath;
    }
    exportBusyRef.current = true;
    setMemoryExportBusy(true);
    setMemoryActionState((current) => ({ ...current, export: true }));
    try {
      if (!frontendRef.current) {
        await syncFrontend(null);
      }
      const response = await systemService.exportMemory({
        frontend: JSON.parse(JSON.stringify(frontendRef.current ?? {})) as Record<string, unknown>,
      });
      const path = response.path ?? null;
      const exportedAt = Date.now();
      lastExportAtRef.current = exportedAt;
      setLastExportAt(exportedAt);
      setMemoryExportPath(path);
      if (path) {
        safeSetItem(MEMORY_EXPORT_PATH_KEY, path);
      }
      if (frontendRef.current) {
        commitFrontend(
          cloneFrontendSnapshot(
            frontendRef.current,
            buildFrontendAlerts(summaryRef.current, frontendRef.current, frontendRef.current.refresh_error ?? null),
            frontendRef.current.refresh_error ?? null,
            readDiagnostics(),
            exportedAt
          )
        );
      }
      return path;
    } finally {
      exportBusyRef.current = false;
      setMemoryExportBusy(false);
      setMemoryActionState((current) => ({ ...current, export: false }));
    }
  }, [commitFrontend, memoryExportPath, readDiagnostics, syncFrontend]);

  const reconcileLeadership = useCallback((): void => {
    if (typeof window === 'undefined') {
      setLeaderState({
        tab_id: tabIdRef.current,
        mode: 'standalone',
        leader_tab_id: null,
        last_broadcast_at: null,
      });
      return;
    }
    if (!enabled) {
      clearLeaderLock(tabIdRef.current);
      clearSummaryTimer();
      nextSummarySyncAtRef.current = null;
      setLeaderState({
        tab_id: tabIdRef.current,
        mode: memoryLeaderRef.current?.mode === 'standalone' ? 'standalone' : 'follower',
        leader_tab_id: null,
        last_broadcast_at: memoryLeaderRef.current?.last_broadcast_at ?? null,
      });
      return;
    }
    const currentLock = readLeaderLock();
    const now = Date.now();
    const hidden = document.visibilityState === 'hidden';
    if (!currentLock || currentLock.tab_id === tabIdRef.current) {
      if (!hidden) {
        writeLeaderLock({ tab_id: tabIdRef.current, updated_at: now });
      }
      setLeaderState({
        tab_id: tabIdRef.current,
        mode: hidden ? 'follower' : 'leader',
        leader_tab_id: hidden ? null : tabIdRef.current,
        last_broadcast_at: memoryLeaderRef.current?.last_broadcast_at ?? null,
      });
      if (hidden) {
        clearSummaryTimer();
        nextSummarySyncAtRef.current = null;
      } else if (summaryRef.current == null) {
        scheduleSummarySync('leader-acquired', true);
      } else {
        scheduleSummarySync('leader-acquired', false);
      }
      return;
    }
    const lockAge = now - currentLock.updated_at;
    if (lockAge >= LEADER_TAKEOVER_MS && !hidden) {
      writeLeaderLock({ tab_id: tabIdRef.current, updated_at: now });
      setLeaderState({
        tab_id: tabIdRef.current,
        mode: 'leader',
        leader_tab_id: tabIdRef.current,
        last_broadcast_at: memoryLeaderRef.current?.last_broadcast_at ?? null,
      });
      if (summaryRef.current == null) {
        scheduleSummarySync('leader-takeover', true);
      } else {
        scheduleSummarySync('leader-takeover', false);
      }
      return;
    }
    clearSummaryTimer();
    nextSummarySyncAtRef.current = null;
    if (lockAge >= LEADER_TAKEOVER_MS) {
      setLeaderState({
        tab_id: tabIdRef.current,
        mode: 'recovering',
        leader_tab_id: currentLock.tab_id,
        last_broadcast_at: memoryLeaderRef.current?.last_broadcast_at ?? null,
      });
      return;
    }
    setLeaderState({
      tab_id: tabIdRef.current,
      mode: 'follower',
      leader_tab_id: currentLock.tab_id,
      last_broadcast_at: memoryLeaderRef.current?.last_broadcast_at ?? null,
    });
  }, [clearSummaryTimer, enabled, scheduleSummarySync, setLeaderState]);

  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  useEffect(() => {
    memoryLeaderRef.current = memoryLeader;
  }, [memoryLeader]);

  useEffect(() => {
    if (!enabled) {
      clearSummaryTimer();
      nextSummarySyncAtRef.current = null;
      return;
    }
    scheduleSummarySync('memory-tab-open', true);
    return () => {
      clearSummaryTimer();
      nextSummarySyncAtRef.current = null;
    };
  }, [clearSummaryTimer, enabled, scheduleSummarySync]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    if (typeof BroadcastChannel === 'function') {
      const channel = new BroadcastChannel('smartfactory-memory-tab');
      channelRef.current = channel;
      channel.onmessage = (event: MessageEvent<MemorySummaryBroadcast>) => {
        if (!event.data || event.data.tab_id === tabIdRef.current) {
          return;
        }
        commitSummary(event.data.summary);
        setLeaderState({
          tab_id: tabIdRef.current,
          mode: memoryLeaderRef.current?.mode === 'leader' ? 'leader' : 'follower',
          leader_tab_id: event.data.tab_id,
          last_broadcast_at: event.data.sent_at,
        });
      };
      return () => {
        channel.close();
        channelRef.current = null;
      };
    }
    return;
  }, [commitSummary, setLeaderState]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const handleStorage = (event: StorageEvent) => {
      if (event.key === MEMORY_LEADER_KEY) {
        reconcileLeadership();
        return;
      }
      if (event.key === MEMORY_SUMMARY_BROADCAST_KEY) {
        const payload = readSummaryBroadcast(event.newValue);
        if (!payload || payload.tab_id === tabIdRef.current) {
          return;
        }
        commitSummary(payload.summary);
        setLeaderState({
          tab_id: tabIdRef.current,
          mode: memoryLeaderRef.current?.mode === 'leader' ? 'leader' : 'follower',
          leader_tab_id: payload.tab_id,
          last_broadcast_at: payload.sent_at,
        });
      }
    };
    const handleVisibility = () => {
      reconcileLeadership();
    };
    window.addEventListener('storage', handleStorage);
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      window.removeEventListener('storage', handleStorage);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [commitSummary, reconcileLeadership, setLeaderState]);

  useEffect(() => {
    reconcileLeadership();
    if (typeof window === 'undefined') {
      return;
    }
    if (heartbeatTimerRef.current) {
      window.clearInterval(heartbeatTimerRef.current);
    }
    heartbeatTimerRef.current = window.setInterval(() => {
      if (memoryLeaderRef.current?.mode === 'leader') {
        writeLeaderLock({ tab_id: tabIdRef.current, updated_at: Date.now() });
      } else {
        reconcileLeadership();
      }
    }, LEADER_HEARTBEAT_MS);
    return () => {
      if (heartbeatTimerRef.current) {
        window.clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }
    };
  }, [reconcileLeadership]);

  useEffect(() => {
    if (!enabled || detailsLoadedRef.current) {
      return;
    }
    loadDetails().catch(() => undefined);
  }, [enabled, loadDetails]);

  useEffect(() => {
    if (!enabled || exportMetaLoadedRef.current) {
      return;
    }
    void loadLatestMemoryExportPath();
  }, [enabled, loadLatestMemoryExportPath]);

  useEffect(() => {
    return () => {
      clearSummaryTimer();
      if (typeof window !== 'undefined') {
        clearLeaderLock(tabIdRef.current);
      }
    };
  }, [clearSummaryTimer]);

  const openMemoryExportFile = useCallback(async (): Promise<void> => {
    await systemService.openMemoryExportFile();
  }, []);

  const openMemoryExportFolder = useCallback(async (): Promise<void> => {
    await systemService.openMemoryExportFolder();
  }, []);

  const copyMemoryExportPath = useCallback(async (): Promise<void> => {
    if (!memoryExportPath) {
      return;
    }
    await navigator.clipboard.writeText(memoryExportPath);
  }, [memoryExportPath]);

  return {
    backendMemory,
    backendMemoryDetails,
    frontendMemory,
    memorySummaryBusy,
    memoryDetailsBusy,
    memoryRefreshInFlight,
    profilerStartBusy,
    profilerStopBusy,
    memoryExportBusy,
    memoryExportPath,
    memoryRefreshIntervalMs: REFRESH_INTERVAL_MS,
    memoryLeader,
    memoryActionState,
    lastExportAt,
    lastSummaryAt,
    lastDetailsAt,
    lastExportMetaAt,
    summaryRequestCount,
    detailsRequestCount,
    lastSummaryReason,
    refreshMemory,
    startMemoryProfiler,
    stopMemoryProfiler,
    captureMemorySnapshot,
    exportMemory,
    openMemoryExportFile,
    openMemoryExportFolder,
    copyMemoryExportPath,
  };
};
