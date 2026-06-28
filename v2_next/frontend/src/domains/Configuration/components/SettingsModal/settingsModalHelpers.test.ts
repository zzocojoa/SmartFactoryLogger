import { describe, expect, it } from 'vitest';

import type { FrontendMemorySnapshot, MemoryDetailsResponse } from '../../../../shared/types';
import { buildObservabilitySummary } from './settingsModalHelpers';

const emptyMemoryDetails = (): MemoryDetailsResponse => ({
  backend_top_consumers: [],
  backend_growth: [],
  collector_history: [],
  leak_suspects: [],
  latest_gc_snapshot: null,
  latest_tracemalloc_diff: [],
});

const emptyFrontendMemory = (): FrontendMemorySnapshot => ({
  captured_at: 1,
  support: {
    mode: 'unsupported',
    supported: false,
    exactness: 'unavailable',
  },
  top_consumers: [],
  growth: [],
  alerts: [],
  last_refresh_at: 1,
  history: [],
});

describe('buildObservabilitySummary', () => {
  it('keeps the first-screen summary normal when operational signals are clean', () => {
    const summary = buildObservabilitySummary({
      health: {
        running: true,
        thread_alive: true,
        last_update: 1,
        driver_connected: true,
        mode: 'REAL',
        comm: {
          extruder: { connected: true },
          ls_plc: { connected: true },
          spot: { read_failures: 0, last_success_time: 1 },
        },
      },
      stats: {
        uptime_sec: 60,
        total_requests: 10,
        avg_latency_ms: 12,
        error_count: 0,
        last: { latency_ms: 12, path: '/api/data', status: 200, timestamp: 1 },
        window: {
          window_sec: 60,
          request_count: 10,
          error_count: 0,
          error_rate: 0,
          avg_latency_ms: 12,
          p95_latency_ms: 30,
        },
        errors: { queue_size: 0 },
      },
      observabilityErrors: null,
      backendMemoryDetails: {
        ...emptyMemoryDetails(),
        backend_top_consumers: [{
          name: 'facility.csv_logger',
          kind: 'queue',
          exactness: 'estimated',
          bytes: 0,
          queue_size: 0,
          queue_maxsize: 1000,
          queue_ratio: 0,
          drop_count: 0,
          writer_lag_sec: 0,
          severity: 'ok',
        }],
      },
      frontendMemory: emptyFrontendMemory(),
      memoryBusy: false,
      frontErrorCount: 0,
      spotImageError: null,
    });

    expect(summary.status).toBe('정상');
    expect(summary.detail).toContain('즉시 조치 신호가 없습니다');
    expect(summary.cards.find((card) => card.key === 'communication')?.evidence).toContain('EX 정상');
    expect(summary.cards.find((card) => card.key === 'csv')?.evidence).toContain('queue 0/1000');
  });

  it('surfaces HTTP and backend error queues as actionable operator text', () => {
    const summary = buildObservabilitySummary({
      health: null,
      stats: {
        uptime_sec: 60,
        total_requests: 20,
        avg_latency_ms: 900,
        error_count: 4,
        total_http_5xx_count: 1,
        last: { latency_ms: 900, path: '/api/spot/proxy_image', status: 500, timestamp: 1 },
        window: {
          window_sec: 60,
          request_count: 20,
          error_count: 4,
          http_error_count: 4,
          http_5xx_count: 1,
          error_rate: 0.2,
          avg_latency_ms: 300,
          p95_latency_ms: 900,
        },
        errors: {
          queue_size: 3,
          last_error_at: 1,
          last_error_source: 'backend',
          last_error_message: 'sample',
        },
      },
      observabilityErrors: null,
      backendMemoryDetails: emptyMemoryDetails(),
      frontendMemory: null,
      memoryBusy: false,
      frontErrorCount: 0,
      spotImageError: null,
    });

    expect(summary.status).toBe('조치 필요');
    expect(summary.cards.find((card) => card.key === 'http')?.action).toBe(
      '대시보드 응답 지연. 서버 부하 또는 이미지 요청 확인.'
    );
    expect(summary.cards.find((card) => card.key === 'errors')?.action).toBe(
      '최근 오류가 누적됨. 상세 진단에서 원인 확인.'
    );
  });

  it('parses CSV collector queue drop and lag evidence', () => {
    const summary = buildObservabilitySummary({
      health: null,
      stats: null,
      observabilityErrors: null,
      backendMemoryDetails: {
        ...emptyMemoryDetails(),
        backend_growth: [{
          name: 'facility.csv_logger',
          kind: 'queue',
          exactness: 'estimated',
          bytes: 4096,
          delta_bytes: 0,
          share_ratio: 0,
          items: 8,
          items_capacity: 100,
          items_ratio: 0.08,
          note: 'queue=8/100 drop=2 lag=12.5s',
        }],
      },
      frontendMemory: null,
      memoryBusy: false,
      frontErrorCount: 0,
      spotImageError: null,
    });

    const csvCard = summary.cards.find((card) => card.key === 'csv');

    expect(csvCard?.status).toBe('조치 필요');
    expect(csvCard?.evidence).toBe('queue 8/100, drop 2, lag 12.5s');
    expect(csvCard?.action).toBe('저장 속도가 수집 속도를 따라가지 못함. 디스크, 경로, 권한 확인.');
  });
});
