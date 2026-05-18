import { useMemo } from 'react';
import type { SpotImageResponseMetadata } from '../../FacilityData/api/spotService.types';
import type { HealthSnapshot, StatsSnapshot, SpotConfig, CommChannelMetrics } from '../../../shared/types';
import { CommBadge, buildCommBadge, buildSpotCommBadge, getCameraStatus } from '../../../shared/utils/commBadge';
import {
  calcRecoverySec,
  formatOptionalNumber,
  formatOptionalSeconds,
  formatTime,
  formatTimeFromSec,
} from '../../../shared/utils/formatters';
import * as LOGIC from '../../../shared/constants/logic';

const {
  STATUS_WARN_MS,
  STATUS_OFFLINE_MS,
  STATUS_ERROR_RATE_WARN,
  STATUS_P95_WARN_MS,
  STATUS_RECENT_ERROR_MS,
} = LOGIC;

/* ─── Types ────────────────────────────────────────────────── */

export interface StatusPanelInput {
  health: HealthSnapshot | null;
  stats: StatsSnapshot | null;
  nowTick: number;
  lastDataAt: number | null;
  connected: boolean;
  dataPollingDegraded: boolean;
  dataPollingIntervalMs: number;
  dataPollingFailureCount: number;
  healthPollingDegraded: boolean;
  healthPollingIntervalMs: number;
  healthPollingFailureCount: number;
  statsPollingDegraded: boolean;
  statsPollingIntervalMs: number;
  statsPollingFailureCount: number;
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotImageError: string | null;
  spotLastSuccessAt: number | null;
  spotImageMetadata: SpotImageResponseMetadata | null;
  settingsBaseline: any;
}

export type StatusPanelSource = Omit<
  StatusPanelInput,
  | 'nowTick'
  | 'lastDataAt'
  | 'connected'
  | 'dataPollingDegraded'
  | 'dataPollingIntervalMs'
  | 'dataPollingFailureCount'
>;

export interface StatusPanelOutput {
  // Status badge
  statusLabel: string;
  statusClass: string;
  statusTitle: string;

  // Text values for header
  lastUpdateText: string;
  avgLatencyText: string;
  errorCountText: string;
  errorQueueText: string;
  errorQueueTitle: string;
  latencyText: string;
  ageText: string;

  // Comm badges (for header)
  commSnapshot: any;
  commBadges: CommBadge[];
  commDetail: any;
  commSummaryItems: any[];

  // Window stats
  statsWindow: any;
  windowErrorRate: number | null;
  hasWindowIssue: boolean;
  windowP95Text: string;

  // Error queue
  errorQueueSize: number | null;
  lastErrorAt: number | null;

  // Camera
  cameraStatus: { type: string; title: string; detail?: string } | null;
}

/* ─── Hook ─────────────────────────────────────────────────── */

export function useStatusPanel(input: StatusPanelInput): StatusPanelOutput {
  const {
    health,
    stats,
    nowTick,
    lastDataAt,
    connected,
    dataPollingDegraded,
    dataPollingIntervalMs,
    dataPollingFailureCount,
    healthPollingDegraded,
    healthPollingIntervalMs,
    healthPollingFailureCount,
    statsPollingDegraded,
    statsPollingIntervalMs,
    statsPollingFailureCount,
    spotConfig,
    spotImageUrl,
    spotImageLoading,
    spotImageError,
    spotLastSuccessAt,
    spotImageMetadata,
    settingsBaseline,
  } = input;

  // --- Age & timing ---
  const ageMs = lastDataAt ? Math.max(0, nowTick - lastDataAt) : null;
  const lastUpdateMs = health?.last_update ? health.last_update * 1000 : null;
  const healthAgeMs = lastUpdateMs ? Math.max(0, nowTick - lastUpdateMs) : null;
  const driverSnapshotAgeMs =
    health?.driver_snapshot_age_sec !== null && health?.driver_snapshot_age_sec !== undefined
      ? Math.max(0, health.driver_snapshot_age_sec * 1000)
      : null;
  const effectiveAgeMs = driverSnapshotAgeMs ?? ((healthAgeMs !== null && ageMs !== null)
    ? Math.min(healthAgeMs, ageMs)
    : (healthAgeMs ?? ageMs));
  const parsedWarnMs = settingsBaseline?.statusWarnMs ? parseInt(settingsBaseline.statusWarnMs, 10) : NaN;
  const parsedOfflineMs = settingsBaseline?.statusOfflineMs ? parseInt(settingsBaseline.statusOfflineMs, 10) : NaN;
  const dynWarnMs = Number.isFinite(parsedWarnMs) ? parsedWarnMs : STATUS_WARN_MS;
  const dynOfflineMs = Number.isFinite(parsedOfflineMs) ? parsedOfflineMs : STATUS_OFFLINE_MS;

  // --- Window stats ---
  const statsWindow = stats?.window;
  const windowRequestCount = statsWindow?.request_count ?? 0;
  const windowErrorRate = statsWindow?.error_rate ?? null;
  const windowErrorCount = statsWindow?.http_error_count ?? statsWindow?.error_count ?? null;
  const windowP95 = statsWindow?.p95_latency_ms ?? null;
  const errorQueueSize = stats?.errors?.queue_size ?? null;
  const lastErrorAt = stats?.errors?.last_error_at ?? null;
  const sourceCounts = stats?.errors?.source_counts ?? {};
  const lastErrorAgeMs = lastErrorAt ? Math.max(0, nowTick - lastErrorAt * 1000) : null;
  const hasRecentError =
    lastErrorAgeMs !== null && lastErrorAgeMs <= STATUS_RECENT_ERROR_MS;
  const hasWindowIssue =
    windowRequestCount >= 5 &&
    ((windowErrorRate !== null && windowErrorRate >= STATUS_ERROR_RATE_WARN) ||
      (windowP95 !== null && windowP95 >= STATUS_P95_WARN_MS) ||
      (windowErrorCount !== null && windowErrorCount >= 3));

  // --- Comm severity ---
  const commSeverity = (() => {
    const comm = health?.comm;
    if (!comm) return 'idle';
    const states = [
      buildCommBadge('EX', comm.extruder, nowTick).state,
      buildCommBadge('LS', comm.ls_plc, nowTick).state,
    ];
    if (states.includes('error')) return 'error';
    if (states.includes('warn')) return 'warn';
    return 'ok';
  })();

  // --- Status label & class ---
  let statusLabel = 'Offline';
  let statusClass = 'status-offline';
  if (effectiveAgeMs !== null) {
    if (effectiveAgeMs <= dynWarnMs) {
      statusLabel = 'Running';
      statusClass = 'status-ok';
    } else if (effectiveAgeMs <= dynOfflineMs) {
      statusLabel = 'Warning';
      statusClass = 'status-warn';
    }
  } else if (connected) {
    statusLabel = 'Running';
    statusClass = 'status-ok';
  }
  if (health && (!health.running || !health.thread_alive)) {
    statusLabel = 'Offline';
    statusClass = 'status-offline';
  } else if (health && !health.driver_connected && statusLabel === 'Running') {
    statusLabel = 'Warning';
    statusClass = 'status-warn';
  } else if (statusLabel === 'Running') {
    if (commSeverity === 'error' || commSeverity === 'warn' || hasWindowIssue || hasRecentError) {
      statusLabel = 'Warning';
      statusClass = 'status-warn';
    }
  }

  // --- Text values ---
  const latencyMs = stats?.last?.latency_ms ?? null;
  const latencyText = latencyMs === null ? '--' : `${latencyMs}ms`;
  const ageText = ageMs === null ? '--' : `${Math.round(ageMs)}ms`;
  const avgLatencyText =
    stats?.avg_latency_ms === null || stats?.avg_latency_ms === undefined
      ? '--'
      : `${Math.round(stats.avg_latency_ms)}ms`;
  const windowHttpErrorCount = statsWindow?.http_error_count ?? statsWindow?.error_count ?? null;
  const errorCountText = windowHttpErrorCount === null || windowHttpErrorCount === undefined
    ? '--'
    : `${windowHttpErrorCount}`;
  const windowP95Text = windowP95 === null || windowP95 === undefined ? '--' : `${Math.round(windowP95)}ms`;
  const errorQueueText = errorQueueSize === null ? '--' : `${errorQueueSize}`;
  const lastUpdateText = lastUpdateMs ? formatTime(lastUpdateMs) : '--:--:--';
  const sourceSummaryText = Object.entries(sourceCounts).length
    ? Object.entries(sourceCounts)
        .map(([source, count]) => `${source} ${count}`)
        .join(', ')
    : '--';
  const degradedPollingParts: string[] = [];
  if (dataPollingDegraded) {
    degradedPollingParts.push(`data ${dataPollingIntervalMs}ms x${dataPollingFailureCount}`);
  }
  if (healthPollingDegraded) {
    degradedPollingParts.push(`health ${healthPollingIntervalMs}ms x${healthPollingFailureCount}`);
  }
  if (statsPollingDegraded) {
    degradedPollingParts.push(`stats ${statsPollingIntervalMs}ms x${statsPollingFailureCount}`);
  }
  const degradedPollingText = degradedPollingParts.length
    ? `Polling ${degradedPollingParts.join(', ')}`
    : 'Polling normal';
  const windowSummaryText = statsWindow
    ? `Win ${statsWindow.window_sec}s req ${statsWindow.request_count}, err ${windowHttpErrorCount ?? '--'}, 4xx ${statsWindow.http_4xx_count ?? '--'}, 5xx ${statsWindow.http_5xx_count ?? '--'}, p95 ${windowP95Text}`
    : 'Win --';
  const errorSummaryText = lastErrorAt
    ? `ErrQ ${errorQueueText}, last ${formatTimeFromSec(lastErrorAt)}, src ${sourceSummaryText}`
    : `ErrQ ${errorQueueText}, src ${sourceSummaryText}`;
  const errorQueueTitle = `Queue ${errorQueueText} | Sources ${sourceSummaryText}`;
  const statusTitle = health
    ? `Mode ${health.mode} | Driver ${health.driver_connected ? 'OK' : 'Down'} | Thread ${health.thread_alive ? 'Alive' : 'Stopped'} | Last ${lastUpdateText} | Avg ${avgLatencyText} | Errors ${errorCountText} | Latency ${latencyText} | Age ${ageText} | ${windowSummaryText} | ${errorSummaryText} | ${degradedPollingText}`
    : `Last ${lastUpdateText} | Avg ${avgLatencyText} | Errors ${errorCountText} | Latency ${latencyText} | Age ${ageText} | ${windowSummaryText} | ${errorSummaryText} | ${degradedPollingText}`;

  // --- Comm badges ---
  const commSnapshot = health?.comm;
  const commBadges = useMemo(() => {
    const comm = commSnapshot;
    if (!comm) return [];
    const refreshMs = spotConfig ? Math.max(500, Math.round(spotConfig.refresh_interval * 1000)) : null;
    return [
      buildCommBadge('EX', comm.extruder, nowTick),
      buildCommBadge('LS', comm.ls_plc, nowTick),
      buildSpotCommBadge('SPOT', comm.spot, nowTick, refreshMs),
    ];
  }, [commSnapshot, nowTick, spotConfig]);

  const commDetail = useMemo(() => {
    const refreshMs = spotConfig ? Math.max(500, Math.round(spotConfig.refresh_interval * 1000)) : null;
    return {
      extruder: {
        metrics: commSnapshot?.extruder,
        badge: buildCommBadge('EX', commSnapshot?.extruder, nowTick),
      },
      ls_plc: {
        metrics: commSnapshot?.ls_plc,
        badge: buildCommBadge('LS', commSnapshot?.ls_plc, nowTick),
      },
      spot: {
        metrics: commSnapshot?.spot,
        badge: buildSpotCommBadge('SPOT', commSnapshot?.spot, nowTick, refreshMs),
        refreshMs,
      },
    };
  }, [commSnapshot, nowTick, spotConfig]);

  const commSummaryItems = useMemo(() => {
    const list = [
      { label: 'Extruder', metrics: commDetail.extruder.metrics, badge: commDetail.extruder.badge },
      { label: 'LS PLC', metrics: commDetail.ls_plc.metrics, badge: commDetail.ls_plc.badge },
      { label: 'SPOT', metrics: commDetail.spot.metrics, badge: commDetail.spot.badge },
    ];
    return list.map((item) => {
      const recoverySec = calcRecoverySec(item.metrics);
      const channelMetrics =
        item.metrics && 'backoff_sec' in item.metrics ? (item.metrics as CommChannelMetrics) : undefined;
      return {
        ...item,
        lastError: formatTimeFromSec(item.metrics?.last_error_time ?? null),
        lastOk: formatTimeFromSec(item.metrics?.last_success_time ?? null),
        recovery: formatOptionalSeconds(recoverySec),
        recoveryCount: formatOptionalNumber(channelMetrics?.recovery_count),
        totalDowntime: formatOptionalSeconds(channelMetrics?.total_downtime_sec ?? null),
        currentDowntime: formatOptionalSeconds(channelMetrics?.current_downtime_sec ?? null),
        lastDisconnect: formatTimeFromSec(channelMetrics?.last_disconnect_time ?? null),
        lastRecoveryAt: formatTimeFromSec(channelMetrics?.last_recovery_at ?? null),
      };
    });
  }, [commDetail]);

  // --- Camera status ---
  const cameraStatus = getCameraStatus({
    spotConfig,
    spotImageUrl,
    spotImageLoading,
    spotImageError,
    spotLastSuccessAt,
    spotImageMetadata,
  });

  return {
    statusLabel,
    statusClass,
    statusTitle,
    lastUpdateText,
    avgLatencyText,
    errorCountText,
    errorQueueText,
    errorQueueTitle,
    latencyText,
    ageText,
    commSnapshot,
    commBadges,
    commDetail,
    commSummaryItems,
    statsWindow,
    windowErrorRate,
    hasWindowIssue,
    windowP95Text,
    errorQueueSize,
    lastErrorAt,
    cameraStatus,
  };
}
