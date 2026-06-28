/**
 * Settings Modal UI helpers - extracted from App.tsx (Phase 12)
 * Pure functions for badge/label formatting in the settings modal.
 */
import type {
  CentralSyncResult,
  CommChannelMetrics,
  CommSpotMetrics,
  ConnectionTestResult,
  FrontendMemorySnapshot,
  HealthSnapshot,
  MemoryCollectorDeltaItem,
  MemoryCollectorItem,
  MemoryDetailsResponse,
  ObservabilityErrorsResponse,
  PathHealthResult,
  StatsSnapshot,
} from '../../../../shared/types';
import { STATUS_ERROR_RATE_WARN, STATUS_P95_WARN_MS } from '../../../../shared/constants/logic';
import { formatOptionalNumber, formatOptionalSeconds, formatTime, formatTimeFromSec } from '../../../../shared/utils/formatters';

interface StatusBadge {
  label: string;
  className: 'idle' | 'ok' | 'warn' | 'error';
}

// ─── Connection Test Badges ───────────────────────────────────────

export const getTestBadge = (result?: ConnectionTestResult): StatusBadge => {
  if (!result) {
    return { label: '미실행', className: 'idle' };
  }
  return result.ok
    ? { label: '성공', className: 'ok' }
    : { label: '실패', className: 'error' };
};

export const formatTestTime = (result?: ConnectionTestResult): string => {
  if (!result) {
    return '미실행';
  }
  return new Date(result.tested_at).toLocaleTimeString();
};

// ─── Path Health Badges ───────────────────────────────────────────

export const getPathBadge = (result?: PathHealthResult): StatusBadge => {
  if (!result) {
    return { label: '미검사', className: 'idle' };
  }
  if (result.status === 'OK') {
    return { label: '정상', className: 'ok' };
  }
  if (result.status === 'WARN') {
    return { label: '경고', className: 'warn' };
  }
  if (result.status === 'ERROR') {
    return { label: '오류', className: 'error' };
  }
  return { label: '미확인', className: 'idle' };
};

export const formatPathCheckTime = (result?: PathHealthResult): string => {
  if (!result?.checked_at) {
    return '미검사';
  }
  return new Date(result.checked_at).toLocaleTimeString();
};

export const formatPathMessage = (result?: PathHealthResult): string => {
  if (!result) {
    return '경로 상태를 확인하세요.';
  }
  const map: Record<string, string> = {
    'Path not found (creatable)': '경로 없음(생성 가능)',
    'Not a directory': '디렉터리가 아님',
    'Write permission denied': '쓰기 권한 없음',
    'Invalid path format': '경로 형식이 올바르지 않습니다.',
    'Network drive unavailable': '네트워크 드라이브가 연결되어 있지 않습니다.',
    'Network path latency': '네트워크 경로 지연',
    OK: '정상',
  };
  return map[result.message] ?? result.message;
};

// ─── Central Sync Badges ──────────────────────────────────────────

export const getCentralBadge = (status?: string, configured?: boolean): StatusBadge => {
  if (configured === false) {
    return { label: '미설정', className: 'idle' };
  }
  if (configured === undefined) {
    return { label: '확인 중', className: 'idle' };
  }
  if (!status) {
    return { label: '미확인', className: 'idle' };
  }
  if (status === 'APPLIED') {
    return { label: '적용', className: 'ok' };
  }
  if (status === 'NO_CHANGE') {
    return { label: '변경 없음', className: 'ok' };
  }
  if (status === 'SKIPPED') {
    return { label: '보류', className: 'warn' };
  }
  if (status === 'FAILED') {
    return { label: '실패', className: 'error' };
  }
  if (status === 'DISABLED') {
    return { label: '미설정', className: 'idle' };
  }
  return { label: status, className: 'idle' };
};

export const formatCentralTime = (result?: CentralSyncResult): string => {
  if (!result?.at) {
    return '미실행';
  }
  return formatTime(result.at * 1000);
};

export type ObservabilitySummarySeverity = 'ok' | 'warn' | 'error';

export interface ObservabilitySummaryCard {
  key: string;
  title: string;
  severity: ObservabilitySummarySeverity;
  status: string;
  evidence: string;
  action: string;
}

export interface ObservabilitySummary {
  severity: ObservabilitySummarySeverity;
  status: string;
  detail: string;
  action: string;
  cards: ObservabilitySummaryCard[];
}

interface BuildObservabilitySummaryInput {
  health: HealthSnapshot | null;
  stats: StatsSnapshot | null;
  observabilityErrors: ObservabilityErrorsResponse | null;
  backendMemoryDetails: MemoryDetailsResponse | null;
  frontendMemory: FrontendMemorySnapshot | null;
  memoryBusy: boolean;
  frontErrorCount: number;
  spotImageError: string | null;
}

interface ChannelStatus {
  label: string;
  severity: ObservabilitySummarySeverity;
  evidence: string;
}

type CsvCollector = MemoryCollectorItem | MemoryCollectorDeltaItem;

const OBSERVABILITY_SEVERITY_RANK: Record<ObservabilitySummarySeverity, number> = {
  ok: 0,
  warn: 1,
  error: 2,
};

const mergeObservabilitySeverity = (
  ...severities: ObservabilitySummarySeverity[]
): ObservabilitySummarySeverity => {
  return severities.reduce<ObservabilitySummarySeverity>((current, next) => (
    OBSERVABILITY_SEVERITY_RANK[next] > OBSERVABILITY_SEVERITY_RANK[current] ? next : current
  ), 'ok');
};

const formatSummaryCount = (value: number | null | undefined): string => {
  return value == null ? '--' : String(value);
};

const statusTextForSeverity = (severity: ObservabilitySummarySeverity): string => {
  if (severity === 'error') {
    return '조치 필요';
  }
  if (severity === 'warn') {
    return '주의';
  }
  return '정상';
};

const buildChannelStatus = (
  label: string,
  channel: CommChannelMetrics | null | undefined,
  fallbackConnected?: boolean
): ChannelStatus => {
  if (!channel && fallbackConnected === undefined) {
    return {
      label,
      severity: 'warn',
      evidence: `${label} 미수집`,
    };
  }

  const connected = channel?.connected ?? fallbackConnected ?? null;
  const backoffSec = channel?.backoff_sec ?? 0;
  const currentDowntimeSec = channel?.current_downtime_sec ?? 0;
  const failureCount =
    (channel?.connect_failures ?? 0) +
    (channel?.read_failures ?? 0) +
    (channel?.invalid_responses ?? 0);
  const recoveryCount = channel?.recovery_count ?? 0;

  if (connected === false || currentDowntimeSec > 0) {
    return {
      label,
      severity: 'error',
      evidence: `${label} 중단 ${formatOptionalSeconds(currentDowntimeSec)}`,
    };
  }
  if (backoffSec > 0 || failureCount > 0 || recoveryCount > 0) {
    return {
      label,
      severity: 'warn',
      evidence: `${label} 실패 ${failureCount}, 복구 ${recoveryCount}, 백오프 ${formatOptionalSeconds(backoffSec)}`,
    };
  }
  return {
    label,
    severity: 'ok',
    evidence: `${label} 정상`,
  };
};

const buildSpotStatus = (
  spot: CommSpotMetrics | null | undefined,
  spotImageError: string | null
): ChannelStatus => {
  if (!spot && !spotImageError) {
    return {
      label: 'SPOT',
      severity: 'warn',
      evidence: 'SPOT 미수집',
    };
  }
  const readFailures = spot?.read_failures ?? 0;
  if (spotImageError) {
    return {
      label: 'SPOT',
      severity: 'error',
      evidence: `SPOT 이미지 오류, read 실패 ${readFailures}`,
    };
  }
  if (readFailures > 0 || spot?.last_error_time) {
    return {
      label: 'SPOT',
      severity: 'warn',
      evidence: `SPOT read 실패 ${readFailures}, 최근 성공 ${formatTimeFromSec(spot?.last_success_time)}`,
    };
  }
  return {
    label: 'SPOT',
    severity: 'ok',
    evidence: `SPOT 정상, 최근 성공 ${formatTimeFromSec(spot?.last_success_time)}`,
  };
};

const findCsvCollector = (details: MemoryDetailsResponse | null): CsvCollector | null => {
  if (!details) {
    return null;
  }
  return [
    ...details.backend_top_consumers,
    ...details.backend_growth,
  ].find((collector) => collector.name === 'facility.csv_logger') ?? null;
};

const parseCsvNoteValue = (note: string | null | undefined, key: 'queue' | 'drop' | 'lag'): string | null => {
  if (!note) {
    return null;
  }
  const match = note.match(new RegExp(`${key}=([^\\s]+)`));
  return match?.[1] ?? null;
};

const buildCsvSummaryCard = (details: MemoryDetailsResponse | null): ObservabilitySummaryCard => {
  const csvCollector = findCsvCollector(details);
  if (!csvCollector) {
    return {
      key: 'csv',
      title: 'CSV 저장',
      severity: 'warn',
      status: '미수집',
      evidence: 'CSV queue/drop/lag 정보 없음',
      action: '메모리 탭에서 새로고침 후 CSV logger 상태를 확인.',
    };
  }

  const queueSize = csvCollector.queue_size ?? null;
  const queueMaxsize = csvCollector.queue_maxsize ?? csvCollector.items_capacity ?? null;
  const queueRatio = csvCollector.queue_ratio ?? csvCollector.items_ratio ?? null;
  const dropCount = csvCollector.drop_count ?? Number.parseInt(parseCsvNoteValue(csvCollector.note, 'drop') ?? '', 10);
  const writerLagSec = csvCollector.writer_lag_sec ?? null;
  const queueText =
    queueSize != null && queueMaxsize != null
      ? `${queueSize}/${queueMaxsize}`
      : parseCsvNoteValue(csvCollector.note, 'queue') ?? '--';
  const dropText = Number.isFinite(dropCount) ? String(dropCount) : parseCsvNoteValue(csvCollector.note, 'drop') ?? '--';
  const lagText = writerLagSec != null ? formatOptionalSeconds(writerLagSec) : parseCsvNoteValue(csvCollector.note, 'lag') ?? '--';
  const hasDrop = Number.isFinite(dropCount) && dropCount > 0;
  const severity = csvCollector.severity === 'critical' || hasDrop
    ? 'error'
    : csvCollector.severity === 'warn' || (queueRatio != null && queueRatio >= 0.8)
      ? 'warn'
      : 'ok';

  return {
    key: 'csv',
    title: 'CSV 저장',
    severity,
    status: statusTextForSeverity(severity),
    evidence: `queue ${queueText}, drop ${dropText}, lag ${lagText}`,
    action: hasDrop
      ? '저장 속도가 수집 속도를 따라가지 못함. 디스크, 경로, 권한 확인.'
      : severity === 'warn'
        ? 'CSV 대기열이 쌓입니다. 저장 경로와 디스크 쓰기 상태 확인.'
        : '조치 없음.',
  };
};

export const buildObservabilitySummary = ({
  health,
  stats,
  observabilityErrors,
  backendMemoryDetails,
  frontendMemory,
  memoryBusy,
  frontErrorCount,
  spotImageError,
}: BuildObservabilitySummaryInput): ObservabilitySummary => {
  const exStatus = buildChannelStatus('EX', health?.comm?.extruder, health?.driver_connected);
  const lsStatus = buildChannelStatus('LS', health?.comm?.ls_plc, health?.thread_alive);
  const spotStatus = buildSpotStatus(health?.comm?.spot, spotImageError);
  const communicationSeverity = mergeObservabilitySeverity(exStatus.severity, lsStatus.severity, spotStatus.severity);

  const window = stats?.window ?? null;
  const windowErrorRate = window?.error_rate ?? null;
  const windowErrorCount = window?.http_error_count ?? window?.error_count ?? null;
  const windowP95 = window?.p95_latency_ms ?? null;
  const window5xx = window?.http_5xx_count ?? 0;
  const httpSeverity: ObservabilitySummarySeverity = !stats
    ? 'warn'
    : window5xx > 0
      ? 'error'
      : (window?.request_count ?? 0) >= 5 &&
        ((windowErrorRate != null && windowErrorRate >= STATUS_ERROR_RATE_WARN) ||
          (windowP95 != null && windowP95 >= STATUS_P95_WARN_MS) ||
          (windowErrorCount != null && windowErrorCount >= 3))
        ? 'warn'
        : 'ok';

  const errorQueueSize = observabilityErrors?.summary.queue_size ?? stats?.errors?.queue_size ?? 0;
  const lastErrorAt = observabilityErrors?.summary.last_error_at ?? stats?.errors?.last_error_at ?? null;
  const backendErrorSeverity: ObservabilitySummarySeverity = errorQueueSize > 0 ? 'error' : 'ok';
  const browserErrorSeverity: ObservabilitySummarySeverity = frontErrorCount > 0 ? 'warn' : 'ok';
  const errorSeverity = mergeObservabilitySeverity(backendErrorSeverity, browserErrorSeverity);

  const commChannels = [health?.comm?.extruder, health?.comm?.ls_plc];
  const backoffCount = commChannels.reduce((total, channel) => total + (channel?.backoff_count ?? 0), 0);
  const recoveryCount = commChannels.reduce((total, channel) => total + (channel?.recovery_count ?? 0), 0);
  const activeBackoffSec = commChannels.reduce((total, channel) => total + (channel?.backoff_sec ?? 0), 0);
  const recoverySeverity: ObservabilitySummarySeverity = activeBackoffSec > 0
    ? 'error'
    : backoffCount > 0 || recoveryCount > 0
      ? 'warn'
      : 'ok';

  const csvCard = buildCsvSummaryCard(backendMemoryDetails);
  const memoryAlerts = frontendMemory?.alerts ?? [];
  const memoryErrorCount = memoryAlerts.filter((alert) => alert.severity === 'error').length;
  const memoryWarnCount = memoryAlerts.filter((alert) => alert.severity === 'warn').length;
  const leakSuspectCount = backendMemoryDetails?.leak_suspects.length ?? 0;
  const memorySeverity: ObservabilitySummarySeverity = memoryErrorCount > 0
    ? 'error'
    : memoryWarnCount > 0 || leakSuspectCount > 0 || memoryBusy
      ? 'warn'
      : backendMemoryDetails || frontendMemory
        ? 'ok'
        : 'warn';

  const cards: ObservabilitySummaryCard[] = [
    {
      key: 'communication',
      title: '통신 상태',
      severity: communicationSeverity,
      status: statusTextForSeverity(communicationSeverity),
      evidence: [exStatus.evidence, lsStatus.evidence, spotStatus.evidence].join(' · '),
      action: communicationSeverity === 'error'
        ? '최근 성공 샘플이 오래됨. PLC/SPOT 연결 상태 확인.'
        : communicationSeverity === 'warn'
          ? '백오프 또는 복구 흔적이 있습니다. 통신 로그에서 반복 여부 확인.'
          : '조치 없음.',
    },
    {
      key: 'http',
      title: 'HTTP 응답',
      severity: httpSeverity,
      status: statusTextForSeverity(httpSeverity),
      evidence: `요청 ${formatSummaryCount(window?.request_count)}, 에러 ${formatSummaryCount(windowErrorCount)}, p95 ${formatOptionalNumber(windowP95)}ms`,
      action: httpSeverity === 'error'
        ? '대시보드 응답 지연. 서버 부하 또는 이미지 요청 확인.'
        : httpSeverity === 'warn'
          ? '응답 지표가 기준을 넘었습니다. Top path와 4xx/5xx 상세 확인.'
          : '조치 없음.',
    },
    {
      key: 'errors',
      title: '최근 오류',
      severity: errorSeverity,
      status: statusTextForSeverity(errorSeverity),
      evidence: `backend ${errorQueueSize}건, browser ${frontErrorCount}건, 최근 ${formatTimeFromSec(lastErrorAt)}`,
      action: errorSeverity === 'error'
        ? '최근 오류가 누적됨. 상세 진단에서 원인 확인.'
        : errorSeverity === 'warn'
          ? '브라우저 오류가 있습니다. 화면 동작과 콘솔 상세 확인.'
          : '조치 없음.',
    },
    {
      key: 'recovery',
      title: '백오프/복구',
      severity: recoverySeverity,
      status: statusTextForSeverity(recoverySeverity),
      evidence: `백오프 ${backoffCount}회, 복구 ${recoveryCount}회, 대기 ${formatOptionalSeconds(activeBackoffSec)}`,
      action: recoverySeverity === 'error'
        ? '백오프 대기 중입니다. 네트워크와 장비 전원 상태 확인.'
        : recoverySeverity === 'warn'
          ? '복구 반복이 있습니다. 통신 로그에서 동일 원인 반복 확인.'
          : '조치 없음.',
    },
    csvCard,
    {
      key: 'memory',
      title: '메모리 연결',
      severity: memorySeverity,
      status: memoryBusy ? '수집 중' : statusTextForSeverity(memorySeverity),
      evidence: `누수 의심 ${leakSuspectCount}건, 경고 ${memoryWarnCount}건, 오류 ${memoryErrorCount}건`,
      action: memorySeverity === 'error'
        ? '메모리 탭에서 오류 alert와 GC 비교를 확인.'
        : memorySeverity === 'warn'
          ? '메모리 탭에서 최신 상태와 CSV logger collector를 확인.'
          : '조치 없음.',
    },
  ];

  const severity = cards.reduce<ObservabilitySummarySeverity>(
    (current, card) => mergeObservabilitySeverity(current, card.severity),
    'ok'
  );
  const firstActionCard = cards.find((card) => card.severity === severity && severity !== 'ok');

  return {
    severity,
    status: statusTextForSeverity(severity),
    detail: severity === 'ok'
      ? '통신, HTTP, 오류, CSV, 메모리 요약에서 즉시 조치 신호가 없습니다.'
      : `${firstActionCard?.title ?? '운영 항목'} 확인이 필요합니다. ${firstActionCard?.evidence ?? ''}`,
    action: firstActionCard?.action ?? '조치 없음.',
    cards,
  };
};
