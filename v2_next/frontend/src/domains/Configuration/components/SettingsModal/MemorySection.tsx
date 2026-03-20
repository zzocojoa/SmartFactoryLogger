import React, { useMemo, useState } from 'react';
import type {
  BackendMemorySample,
  FrontendMemorySnapshot,
  HealthSnapshot,
  MemoryActionState,
  MemoryAlertItem,
  MemoryCollectorDeltaItem,
  MemoryCollectorItem,
  MemoryDetailsResponse,
  MemoryStateResponse,
  MemoryTabLeaderState,
  TracemallocDiffItem,
} from '../../../../shared/types';

interface MemorySectionProps {
  sectionRef?: (el: HTMLDivElement | null) => void;
  health: HealthSnapshot | null;
  backendMemory: MemoryStateResponse | null;
  backendMemoryDetails: MemoryDetailsResponse | null;
  frontendMemory: FrontendMemorySnapshot | null;
  memorySummaryBusy: boolean;
  memoryDetailsBusy: boolean;
  memoryRefreshInFlight: boolean;
  memoryRefreshIntervalMs: number;
  profilerStartBusy: boolean;
  profilerStopBusy: boolean;
  memoryExportBusy: boolean;
  memoryExportPath: string | null;
  memoryLeader: MemoryTabLeaderState | null;
  memoryActionState: MemoryActionState;
  lastExportAt: number | null;
  lastSummaryAt: number | null;
  lastDetailsAt: number | null;
  lastExportMetaAt: number | null;
  summaryRequestCount: number;
  detailsRequestCount: number;
  lastSummaryReason: string | null;
  onRefresh: () => void;
  onStartProfiler: () => void;
  onStopProfiler: () => void;
  onSnapshot: () => void;
  onExport: () => void;
  onOpenFile: () => void;
  onOpenFolder: () => void;
  onCopyPath: () => void;
}

type SortMode = 'delta' | 'size';

interface FrontendHistorySample {
  captured_at: number;
  app_bytes: number;
  heap_used_bytes?: number | null;
  heap_total_bytes?: number | null;
}

interface HistoryRow {
  key: string;
  capturedAt: number | null;
  backendRss: number | null;
  backendDelta: number | null;
  frontendApp: number | null;
  frontendAppDelta: number | null;
  frontendHeap: number | null;
  frontendHeapDelta: number | null;
}

const HISTORY_LIMIT = 12;
const DELTA_WINDOW_SEC = 60;
const BACKEND_GROWTH_WARN_BYTES = 64 * 1024 * 1024;
const FRONTEND_GROWTH_WARN_BYTES = 32 * 1024 * 1024;
const GROWTH_WARN_RATIO = 0.2;
const PROFILER_LONG_RUNNING_SEC = 600;

const formatBytes = (value: number | null | undefined): string => {
  if (value == null) {
    return '--';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let current = value;
  let unitIndex = 0;
  while (current >= 1024 && unitIndex < units.length - 1) {
    current /= 1024;
    unitIndex += 1;
  }
  return `${current.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
};

const formatDeltaBytes = (value: number | null | undefined): string => {
  if (value == null) {
    return '--';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${formatBytes(Math.abs(value))}`.replace(/^(\+?)(.+)$/, (_, prefix, body) =>
    `${value < 0 ? '-' : prefix}${body}`
  );
};

const formatPercent = (value: number | null | undefined): string => {
  if (value == null || Number.isNaN(value)) {
    return '--';
  }
  return `${(value * 100).toFixed(value >= 0.1 ? 1 : 2)}%`;
};

const formatExactness = (value: string | null | undefined): string => {
  if (!value) {
    return '--';
  }
  if (value === 'exact') {
    return 'exact';
  }
  if (value === 'estimated') {
    return 'estimated';
  }
  return value;
};

const formatItems = (value: number | null | undefined): string => {
  if (value == null) {
    return '--';
  }
  return value.toLocaleString();
};

const formatTimestampSec = (value: number | null | undefined): string => {
  if (!value) {
    return '--';
  }
  return new Date(value * 1000).toLocaleTimeString();
};

const formatTimestampMs = (value: number | null | undefined): string => {
  if (!value) {
    return '--';
  }
  return new Date(value).toLocaleTimeString();
};

const formatIsoTimestamp = (value: string | null | undefined): string => {
  if (!value) {
    return '--';
  }
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return value;
  }
  return new Date(parsed).toLocaleString();
};

const formatAgeFromSec = (value: number | null | undefined): string => {
  if (!value) {
    return '--';
  }
  const deltaSec = Math.max(0, Math.floor(Date.now() / 1000 - value));
  if (deltaSec < 60) {
    return `${deltaSec}s`;
  }
  if (deltaSec < 3600) {
    return `${Math.floor(deltaSec / 60)}m ${deltaSec % 60}s`;
  }
  return `${Math.floor(deltaSec / 3600)}h ${Math.floor((deltaSec % 3600) / 60)}m`;
};

const formatAgeFromMs = (value: number | null | undefined): string => {
  if (!value) {
    return '--';
  }
  const deltaSec = Math.max(0, Math.floor((Date.now() - value) / 1000));
  if (deltaSec < 60) {
    return `${deltaSec}s`;
  }
  if (deltaSec < 3600) {
    return `${Math.floor(deltaSec / 60)}m ${deltaSec % 60}s`;
  }
  return `${Math.floor(deltaSec / 3600)}h ${Math.floor((deltaSec % 3600) / 60)}m`;
};

const formatProfilerRuntime = (startedAt: string | null | undefined): string => {
  if (!startedAt) {
    return '--';
  }
  const parsed = Date.parse(startedAt);
  if (Number.isNaN(parsed)) {
    return '--';
  }
  return formatAgeFromMs(parsed);
};

const getDeltaClassName = (value: number | null | undefined): string => {
  if (value == null || value === 0) {
    return 'settings-memory-value-neutral';
  }
  return value > 0 ? 'settings-memory-value-warn' : 'settings-memory-value-ok';
};

const getAlertClassName = (severity: MemoryAlertItem['severity']): string => {
  if (severity === 'error') {
    return 'settings-memory-alert-error';
  }
  if (severity === 'warn') {
    return 'settings-memory-alert-warn';
  }
  return 'settings-memory-alert-info';
};

const getWindowDelta = <T extends { captured_at: number }>(
  history: T[],
  valueResolver: (item: T) => number | null | undefined
): number | null => {
  const latest = history[history.length - 1];
  if (!latest) {
    return null;
  }
  const previous = [...history]
    .reverse()
    .find((item) => item.captured_at <= latest.captured_at - DELTA_WINDOW_SEC);
  if (!previous) {
    return null;
  }
  const latestValue = valueResolver(latest);
  const previousValue = valueResolver(previous);
  if (latestValue == null || previousValue == null) {
    return null;
  }
  return latestValue - previousValue;
};

const getPeakValue = <T,>(history: T[], valueResolver: (item: T) => number | null | undefined): number | null => {
  const values = history
    .map((item) => valueResolver(item))
    .filter((value): value is number => value != null);
  if (!values.length) {
    return null;
  }
  return Math.max(...values);
};

const toGrowthFallback = (items: MemoryCollectorItem[]): MemoryCollectorDeltaItem[] => {
  const totalBytes = items.reduce((sum, item) => sum + item.bytes, 0);
  return items.map((item) => ({
    ...item,
    delta_bytes: 0,
    share_ratio: totalBytes > 0 ? item.bytes / totalBytes : 0,
  }));
};

const sortGrowthItems = (items: MemoryCollectorDeltaItem[], sortMode: SortMode): MemoryCollectorDeltaItem[] => {
  return [...items].sort((left, right) => {
    if (sortMode === 'size') {
      if (right.bytes !== left.bytes) {
        return right.bytes - left.bytes;
      }
      return right.delta_bytes - left.delta_bytes;
    }
    if (right.delta_bytes !== left.delta_bytes) {
      return right.delta_bytes - left.delta_bytes;
    }
    return right.bytes - left.bytes;
  });
};

const buildHistoryRows = (
  backendHistory: BackendMemorySample[],
  frontendHistory: FrontendHistorySample[]
): HistoryRow[] => {
  const backendSlice = backendHistory.slice(-HISTORY_LIMIT);
  const frontendSlice = frontendHistory.slice(-HISTORY_LIMIT);
  const rowCount = Math.max(backendSlice.length, frontendSlice.length);

  return Array.from({ length: rowCount }, (_, index) => {
    const backendIndex = backendSlice.length - rowCount + index;
    const frontendIndex = frontendSlice.length - rowCount + index;
    const backendItem = backendIndex >= 0 ? backendSlice[backendIndex] : null;
    const previousBackend = backendIndex > 0 ? backendSlice[backendIndex - 1] : null;
    const frontendItem = frontendIndex >= 0 ? frontendSlice[frontendIndex] : null;
    const previousFrontend = frontendIndex > 0 ? frontendSlice[frontendIndex - 1] : null;
    const capturedAt = backendItem?.captured_at ?? frontendItem?.captured_at ?? null;
    const heapValue = frontendItem?.heap_used_bytes ?? null;
    const previousHeap = previousFrontend?.heap_used_bytes ?? null;

    return {
      key: `${capturedAt ?? 'empty'}-${index}`,
      capturedAt,
      backendRss: backendItem?.rss_bytes ?? null,
      backendDelta:
        backendItem && previousBackend ? backendItem.rss_bytes - previousBackend.rss_bytes : null,
      frontendApp: frontendItem?.app_bytes ?? null,
      frontendAppDelta:
        frontendItem && previousFrontend ? frontendItem.app_bytes - previousFrontend.app_bytes : null,
      frontendHeap: heapValue,
      frontendHeapDelta:
        heapValue != null && previousHeap != null ? heapValue - previousHeap : null,
    };
  }).reverse();
};

const buildGrowthSummary = (deltaBytes: number | null, currentBytes: number | null): string => {
  if (deltaBytes == null || currentBytes == null || currentBytes <= 0) {
    return '--';
  }
  const ratio = deltaBytes / currentBytes;
  return formatPercent(ratio);
};

const ConsumerTable = ({
  title,
  items,
  sortMode,
  onSortModeChange,
}: {
  title: string;
  items: MemoryCollectorDeltaItem[];
  sortMode: SortMode;
  onSortModeChange: (mode: SortMode) => void;
}) => {
  const rows = useMemo(() => sortGrowthItems(items, sortMode).slice(0, 12), [items, sortMode]);

  return (
    <div className="settings-observability-errors settings-memory-table-shell">
      <div className="settings-comm-log-header">
        <span className="settings-comm-log-label">{title}</span>
        <div className="settings-memory-sort-group">
          <button
            type="button"
            className={`settings-memory-sort-button ${sortMode === 'delta' ? 'active' : ''}`}
            onClick={() => onSortModeChange('delta')}
          >
            delta
          </button>
          <button
            type="button"
            className={`settings-memory-sort-button ${sortMode === 'size' ? 'active' : ''}`}
            onClick={() => onSortModeChange('size')}
          >
            size
          </button>
        </div>
      </div>
      <div className="settings-memory-table">
        <div className="settings-memory-table-row settings-memory-table-head">
          <span>name</span>
          <span>size</span>
          <span>delta</span>
          <span>share</span>
          <span>items</span>
          <span>exact</span>
          <span>note</span>
        </div>
        {rows.map((item) => (
          <div key={item.name} className="settings-memory-table-row">
            <span className="settings-memory-cell-strong">{item.name}</span>
            <span>{formatBytes(item.bytes)}</span>
            <span className={getDeltaClassName(item.delta_bytes)}>{formatDeltaBytes(item.delta_bytes)}</span>
            <span>{formatPercent(item.share_ratio)}</span>
            <span>{formatItems(item.items)}</span>
            <span>{formatExactness(item.exactness)}</span>
            <span className="settings-memory-note">{item.note ?? '--'}</span>
          </div>
        ))}
        {!rows.length && <div className="settings-error-empty">데이터 없음</div>}
      </div>
    </div>
  );
};

const TracemallocList = ({ items }: { items: TracemallocDiffItem[] }) => {
  return (
    <div className="settings-observability-errors">
      <div className="settings-comm-log-header">
        <span className="settings-comm-log-label">Tracemalloc diff</span>
        <span className="settings-observability-count">{items.length}</span>
      </div>
      <div className="settings-error-list">
        {items.map((item) => (
          <div key={item.trace} className="settings-error-item">
            <div className="settings-error-head">
              <span className="settings-error-source">{item.trace}</span>
              <span className={getDeltaClassName(item.size_diff_bytes)}>{formatDeltaBytes(item.size_diff_bytes)}</span>
            </div>
            <div className="settings-error-message">
              total {formatBytes(item.size_bytes)} | count {item.count.toLocaleString()} | count diff{' '}
              {item.count_diff >= 0 ? `+${item.count_diff}` : item.count_diff}
            </div>
          </div>
        ))}
        {!items.length && <div className="settings-error-empty">Profiler idle</div>}
      </div>
    </div>
  );
};

export const MemorySection = ({
  sectionRef,
  health,
  backendMemory,
  backendMemoryDetails,
  frontendMemory,
  memorySummaryBusy,
  memoryDetailsBusy,
  memoryRefreshInFlight,
  memoryRefreshIntervalMs,
  profilerStartBusy,
  profilerStopBusy,
  memoryExportBusy,
  memoryExportPath,
  memoryLeader,
  memoryActionState,
  lastExportAt,
  lastSummaryAt,
  lastDetailsAt,
  lastExportMetaAt,
  summaryRequestCount,
  detailsRequestCount,
  lastSummaryReason,
  onRefresh,
  onStartProfiler,
  onStopProfiler,
  onSnapshot,
  onExport,
  onOpenFile,
  onOpenFolder,
  onCopyPath,
}: MemorySectionProps) => {
  const [backendSortMode, setBackendSortMode] = useState<SortMode>('delta');
  const [frontendSortMode, setFrontendSortMode] = useState<SortMode>('delta');

  const backendSummary = backendMemory?.summary ?? null;
  const backendHistory = backendMemory?.history ?? [];
  const frontendHistory = frontendMemory?.history ?? [];
  const profiler = backendMemory?.profiler ?? null;
  const frontendSupport = frontendMemory?.support ?? null;
  const alerts = frontendMemory?.alerts ?? [];
  const backendGrowth = backendMemoryDetails?.backend_growth?.length
    ? backendMemoryDetails.backend_growth
    : toGrowthFallback(backendMemoryDetails?.backend_top_consumers ?? []);
  const frontendGrowth = frontendMemory?.growth?.length
    ? frontendMemory.growth
    : toGrowthFallback(frontendMemory?.top_consumers ?? []);
  const historyRows = useMemo(
    () => buildHistoryRows(backendHistory, frontendHistory),
    [backendHistory, frontendHistory]
  );

  const latestFrontendPoint = frontendHistory[frontendHistory.length - 1] ?? null;
  const backendDelta1m = getWindowDelta(backendHistory, (item) => item.rss_bytes);
  const backendPeak = getPeakValue(backendHistory, (item) => item.rss_bytes);
  const frontendAppDelta1m = getWindowDelta(frontendHistory, (item) => item.app_bytes);
  const frontendAppPeak = getPeakValue(frontendHistory, (item) => item.app_bytes);
  const frontendHeapDelta1m = getWindowDelta(frontendHistory, (item) => item.heap_used_bytes ?? null);
  const frontendHeapPeak = getPeakValue(frontendHistory, (item) => item.heap_used_bytes ?? null);
  const profilerStartedAt = profiler?.started_at ?? null;
  const profilerRuntimeSec = profilerStartedAt
    ? Math.max(0, Math.floor((Date.now() - Date.parse(profilerStartedAt)) / 1000))
    : null;
  const profilerActionBusy = profilerStartBusy || profilerStopBusy;
  const backendStale = Boolean(frontendMemory?.refresh_error);
  const leaderModeLabel =
    memoryLeader?.mode === 'leader'
      ? 'leader'
      : memoryLeader?.mode === 'follower'
        ? 'follower'
        : memoryLeader?.mode === 'recovering'
          ? 'recovering'
        : 'standalone';
  const backendGrowthWarn =
    backendDelta1m != null &&
    backendSummary?.rss_bytes != null &&
    (backendDelta1m >= BACKEND_GROWTH_WARN_BYTES ||
      backendDelta1m / Math.max(backendSummary.rss_bytes - backendDelta1m, 1) >= GROWTH_WARN_RATIO);
  const frontendGrowthWarn =
    (frontendAppDelta1m != null &&
      latestFrontendPoint != null &&
      (frontendAppDelta1m >= FRONTEND_GROWTH_WARN_BYTES ||
        frontendAppDelta1m / Math.max(latestFrontendPoint.app_bytes - frontendAppDelta1m, 1) >= GROWTH_WARN_RATIO)) ||
    (frontendHeapDelta1m != null &&
      (frontendHeapDelta1m >= FRONTEND_GROWTH_WARN_BYTES ||
        frontendHeapDelta1m /
          Math.max((latestFrontendPoint?.heap_used_bytes ?? 0) - frontendHeapDelta1m, 1) >= GROWTH_WARN_RATIO));

  return (
    <div className="settings-section" id="settings-memory" ref={sectionRef}>
      <div className="settings-section-title">메모리 진단</div>

      <div className="settings-test-meta">
        <span>리더 상태: {leaderModeLabel}</span>
        <span>리더 탭: {memoryLeader?.leader_tab_id ?? '--'}</span>
        <span>자동 주기: {Math.max(1, Math.round(memoryRefreshIntervalMs / 1000))}s</span>
        <span>마지막 export: {formatTimestampMs(lastExportAt ?? null)}</span>
        <span>수집 상태: {memorySummaryBusy ? 'summary in-flight' : memoryDetailsBusy ? 'details in-flight' : 'idle'}</span>
      </div>

      <div className="settings-test-meta">
        <span>상태: {backendStale ? 'stale' : 'fresh'}</span>
        <span>수집: {memorySummaryBusy ? 'summary' : memoryDetailsBusy ? 'details' : 'idle'}</span>
        <span>Profiler: {profiler?.enabled ? (profilerActionBusy ? 'transition' : 'on') : profilerActionBusy ? 'transition' : 'off'}</span>
        <span>Export: {memoryActionState.export ? 'in-flight' : memoryExportPath ? 'ready' : 'empty'}</span>
        <span>마지막 수집: {formatTimestampMs(lastSummaryAt ?? frontendMemory?.last_refresh_at ?? null)}</span>
        <span>마지막 export: {formatTimestampMs(lastExportAt ?? null)}</span>
      </div>

      <div className="settings-test-meta">
        <span>leader: {leaderModeLabel}</span>
        <span>leader id: {memoryLeader?.leader_tab_id ?? '--'}</span>
        <span>주기: {Math.max(1, Math.round(memoryRefreshIntervalMs / 1000))}s</span>
        <span>summary req: {summaryRequestCount}</span>
        <span>details req: {detailsRequestCount}</span>
        <span>details 시각: {formatTimestampMs(lastDetailsAt ?? null)}</span>
        <span>export meta: {formatTimestampMs(lastExportMetaAt ?? null)}</span>
        <span>마지막 이유: {lastSummaryReason ?? '--'}</span>
      </div>

      <div className="settings-memory-actions">
        <button
          type="button"
          className="settings-test-button"
          onClick={onRefresh}
          disabled={memorySummaryBusy || memoryActionState.snapshot}
        >
          {memoryActionState.refresh ? '수집 중...' : '새로고침'}
        </button>
        <button
          type="button"
          className="settings-test-button"
          onClick={onStartProfiler}
          disabled={profilerActionBusy || profiler?.enabled}
        >
          {profilerStartBusy ? '시작 중...' : '상세 추적 시작'}
        </button>
        <button
          type="button"
          className="settings-test-button"
          onClick={onStopProfiler}
          disabled={profilerActionBusy || !profiler?.enabled}
        >
          {profilerStopBusy ? '중지 중...' : '상세 추적 중지'}
        </button>
        <button
          type="button"
          className="settings-test-button"
          onClick={onSnapshot}
          disabled={memoryActionState.snapshot}
        >
          즉시 snapshot
        </button>
        <button
          type="button"
          className="settings-test-button"
          onClick={onExport}
          disabled={memoryExportBusy}
        >
          {memoryExportBusy ? '내보내는 중...' : 'export'}
        </button>
      </div>

      <div className="settings-memory-summary">
        <div className="settings-test-item settings-memory-card">
          <div className="settings-memory-card-header">
            <span className="settings-memory-card-title">Backend RSS</span>
            <span className={`settings-test-badge ${backendGrowthWarn ? 'warn' : 'ok'}`}>
              {backendGrowthWarn ? 'GROWTH' : 'STABLE'}
            </span>
          </div>
          <div className="settings-memory-card-value">{formatBytes(backendSummary?.rss_bytes)}</div>
          <div className="settings-memory-card-grid">
            <span>1분 증가</span>
            <span className={getDeltaClassName(backendDelta1m)}>{formatDeltaBytes(backendDelta1m)}</span>
            <span>1분 비율</span>
            <span>{buildGrowthSummary(backendDelta1m, backendSummary?.rss_bytes ?? null)}</span>
            <span>피크</span>
            <span>{formatBytes(backendPeak)}</span>
            <span>VMS / USS</span>
            <span>
              {formatBytes(backendSummary?.vms_bytes)} / {formatBytes(backendSummary?.uss_bytes)}
            </span>
          </div>
        </div>

        <div className="settings-test-item settings-memory-card">
          <div className="settings-memory-card-header">
            <span className="settings-memory-card-title">Frontend Heap / App</span>
            <span className={`settings-test-badge ${frontendSupport?.supported ? (frontendGrowthWarn ? 'warn' : 'ok') : 'idle'}`}>
              {frontendSupport?.mode ?? 'unsupported'}
            </span>
          </div>
          <div className="settings-memory-card-value-group">
            <div>
              <div className="settings-memory-card-metric">Heap</div>
              <div className="settings-memory-card-value">{formatBytes(frontendSupport?.used_bytes ?? latestFrontendPoint?.heap_used_bytes ?? null)}</div>
            </div>
            <div>
              <div className="settings-memory-card-metric">App</div>
              <div className="settings-memory-card-value">{formatBytes(latestFrontendPoint?.app_bytes ?? null)}</div>
            </div>
          </div>
          <div className="settings-memory-card-grid">
            <span>Heap 1분 증가</span>
            <span className={getDeltaClassName(frontendHeapDelta1m)}>{formatDeltaBytes(frontendHeapDelta1m)}</span>
            <span>App 1분 증가</span>
            <span className={getDeltaClassName(frontendAppDelta1m)}>{formatDeltaBytes(frontendAppDelta1m)}</span>
            <span>Heap 피크</span>
            <span>{formatBytes(frontendHeapPeak)}</span>
            <span>App 피크</span>
            <span>{formatBytes(frontendAppPeak)}</span>
          </div>
        </div>

        <div className="settings-test-item settings-memory-card">
          <div className="settings-memory-card-header">
            <span className="settings-memory-card-title">샘플 상태</span>
            <span className={`settings-test-badge ${backendStale ? 'warn' : 'ok'}`}>
              {backendStale ? 'STALE' : 'LIVE'}
            </span>
          </div>
          <div className="settings-memory-card-grid">
            <span>Backend sample</span>
            <span>{formatAgeFromSec(backendSummary?.captured_at)}</span>
            <span>Frontend refresh</span>
            <span>{formatAgeFromMs(frontendMemory?.last_refresh_at)}</span>
            <span>자동 주기</span>
            <span>{Math.max(1, Math.round(memoryRefreshIntervalMs / 1000))}s</span>
            <span>마지막 수집</span>
            <span>{formatTimestampMs(frontendMemory?.last_refresh_at)}</span>
            <span>수집 중</span>
            <span className={memoryRefreshInFlight || memorySummaryBusy ? 'settings-memory-value-warn' : 'settings-memory-value-ok'}>
              {memoryRefreshInFlight || memorySummaryBusy ? 'summary in-flight' : memoryDetailsBusy ? 'details in-flight' : 'idle'}
            </span>
            <span>오류 상태</span>
            <span className={backendStale ? 'settings-memory-value-warn' : 'settings-memory-value-ok'}>
              {frontendMemory?.refresh_error ?? '정상'}
            </span>
          </div>
          <div className="settings-memory-runtime">
            <span>런타임 {health?.runtime_kind ?? '--'}</span>
            <span>버전 {health?.app_version ?? '--'}</span>
            <span>빌드 {health?.executable_mtime ?? '--'}</span>
          </div>
        </div>

        <div className="settings-test-item settings-memory-card">
          <div className="settings-memory-card-header">
            <span className="settings-memory-card-title">Profiler 상태</span>
            <span className={`settings-test-badge ${profiler?.enabled ? 'warn' : 'idle'}`}>
              {profiler?.enabled ? 'ON' : 'OFF'}
            </span>
          </div>
          <div className="settings-memory-card-value">
            {profiler?.enabled ? formatProfilerRuntime(profiler.started_at ?? null) : '--'}
          </div>
          <div className="settings-memory-card-grid">
            <span>시작 시각</span>
            <span>{formatIsoTimestamp(profiler?.started_at ?? null)}</span>
            <span>마지막 snapshot</span>
            <span>{formatIsoTimestamp(profiler?.last_snapshot_at ?? null)}</span>
            <span>마지막 diff</span>
            <span>{formatIsoTimestamp(profiler?.last_diff_at ?? null)}</span>
            <span>장기 실행</span>
            <span className={profilerRuntimeSec != null && profilerRuntimeSec >= PROFILER_LONG_RUNNING_SEC ? 'settings-memory-value-warn' : 'settings-memory-value-neutral'}>
              {profilerRuntimeSec != null && profilerRuntimeSec >= PROFILER_LONG_RUNNING_SEC ? '예' : '아니오'}
            </span>
          </div>
        </div>
      </div>

      <div className="settings-memory-alerts">
        {alerts.length ? (
          alerts.map((alert) => (
            <div key={alert.key} className={`settings-memory-alert ${getAlertClassName(alert.severity)}`}>
              <div className="settings-memory-alert-title">{alert.title}</div>
              <div className="settings-memory-alert-detail">{alert.detail}</div>
            </div>
          ))
        ) : (
          <div className="settings-memory-alert settings-memory-alert-stable">
            <div className="settings-memory-alert-title">경고 없음</div>
            <div className="settings-memory-alert-detail">현재 샘플 기준으로 눈에 띄는 증가 신호가 없습니다.</div>
          </div>
        )}
      </div>

      <div className="settings-memory-grid">
        <ConsumerTable
          title="Backend growth"
          items={backendGrowth}
          sortMode={backendSortMode}
          onSortModeChange={setBackendSortMode}
        />
        <ConsumerTable
          title="Frontend growth"
          items={frontendGrowth}
          sortMode={frontendSortMode}
          onSortModeChange={setFrontendSortMode}
        />
      </div>

      <div className="settings-memory-grid">
        <div className="settings-observability-errors settings-memory-table-shell">
          <div className="settings-comm-log-header">
            <span className="settings-comm-log-label">최근 12개 샘플</span>
            <span className="settings-observability-count">{historyRows.length}</span>
          </div>
          <div className="settings-memory-history">
            <div className="settings-memory-history-row settings-memory-history-head">
              <span>time</span>
              <span>backend rss</span>
              <span>rss delta</span>
              <span>frontend app</span>
              <span>app delta</span>
              <span>frontend heap</span>
              <span>heap delta</span>
            </div>
            {historyRows.map((row) => (
              <div key={row.key} className="settings-memory-history-row">
                <span>{formatTimestampSec(row.capturedAt)}</span>
                <span>{formatBytes(row.backendRss)}</span>
                <span className={getDeltaClassName(row.backendDelta)}>{formatDeltaBytes(row.backendDelta)}</span>
                <span>{formatBytes(row.frontendApp)}</span>
                <span className={getDeltaClassName(row.frontendAppDelta)}>{formatDeltaBytes(row.frontendAppDelta)}</span>
                <span>{formatBytes(row.frontendHeap)}</span>
                <span className={getDeltaClassName(row.frontendHeapDelta)}>{formatDeltaBytes(row.frontendHeapDelta)}</span>
              </div>
            ))}
            {!historyRows.length && <div className="settings-error-empty">No history yet</div>}
          </div>
        </div>

        <TracemallocList items={backendMemoryDetails?.latest_tracemalloc_diff ?? []} />
      </div>

      <div className="settings-test-item settings-memory-export">
        <div className="settings-memory-card-header">
          <span className="settings-memory-card-title">Export</span>
          <span className={`settings-test-badge ${memoryExportPath ? 'ok' : 'idle'}`}>
            {memoryExportPath ? 'READY' : 'EMPTY'}
          </span>
        </div>
        <div className="settings-memory-export-path">{memoryExportPath ?? '--'}</div>
        <div className="settings-test-message">export 상태: {memoryActionState.export ? '내보내는 중' : 'idle'}</div>
        <div className="settings-observability-actions">
          <button type="button" className="settings-test-button" onClick={onCopyPath} disabled={!memoryExportPath}>
            경로 복사
          </button>
          <button type="button" className="settings-test-button" onClick={onOpenFolder} disabled={!memoryExportPath}>
            폴더 열기
          </button>
          <button type="button" className="settings-test-button" onClick={onOpenFile} disabled={!memoryExportPath}>
            파일 열기
          </button>
        </div>
      </div>
    </div>
  );
};
