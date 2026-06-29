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

  it('treats backend real_plc retry interval fields as normal when the channels are connected', () => {
    const summary = buildObservabilitySummary({
      health: {
        running: true,
        thread_alive: true,
        last_update: 1000,
        driver_connected: true,
        mode: 'REAL',
        comm: {
          extruder: {
            connected: true,
            connect_attempts: 1,
            connect_failures: 0,
            read_failures: 0,
            invalid_responses: 0,
            skipped_reads: 0,
            backoff_count: 0,
            backoff_sec: 1.0,
            next_retry_at: 0.0,
            last_error: null,
            last_error_time: null,
            last_success_time: 1000,
            last_recovery_sec: null,
            recovery_count: 0,
            total_downtime_sec: 0,
            current_downtime_sec: 0,
            last_disconnect_time: null,
            last_recovery_at: null,
            merge_blocks: true,
            merge_failures: 0,
          },
          ls_plc: {
            connected: true,
            connect_attempts: 1,
            connect_failures: 0,
            read_failures: 0,
            invalid_responses: 0,
            backoff_count: 0,
            backoff_sec: 1.0,
            next_retry_at: 0.0,
            last_error: null,
            last_error_time: null,
            last_success_time: 1000,
            last_recovery_sec: null,
            recovery_count: 0,
            total_downtime_sec: 0,
            current_downtime_sec: 0,
            last_disconnect_time: null,
            last_recovery_at: null,
          },
          spot: { read_failures: 0, last_success_time: 1000 },
        },
      },
      stats: {
        uptime_sec: 60,
        total_requests: 10,
        avg_latency_ms: 12,
        error_count: 0,
        last: { latency_ms: 12, path: '/api/data', status: 200, timestamp: 1000 },
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
      nowSec: 1000,
    });

    expect(summary.status).toBe('정상');
    expect(summary.cards.find((card) => card.key === 'communication')?.status).toBe('정상');
    expect(summary.cards.find((card) => card.key === 'communication')?.evidence).toContain('EX 정상');
    expect(summary.cards.find((card) => card.key === 'recovery')?.status).toBe('정상');
    expect(summary.cards.find((card) => card.key === 'recovery')?.evidence).toContain('대기 0s');
  });

  it('keeps active retry windows actionable when next_retry_at is in the future', () => {
    const summary = buildObservabilitySummary({
      health: {
        running: true,
        thread_alive: true,
        last_update: 1000,
        driver_connected: true,
        mode: 'REAL',
        comm: {
          extruder: {
            connected: true,
            connect_failures: 0,
            read_failures: 0,
            invalid_responses: 0,
            backoff_count: 1,
            backoff_sec: 1.0,
            next_retry_at: 1003,
            recovery_count: 0,
            current_downtime_sec: 0,
          },
          ls_plc: {
            connected: true,
            connect_failures: 0,
            read_failures: 0,
            invalid_responses: 0,
            backoff_count: 0,
            backoff_sec: 1.0,
            next_retry_at: 0,
            recovery_count: 0,
            current_downtime_sec: 0,
          },
          spot: { read_failures: 0, last_success_time: 1000 },
        },
      },
      stats: {
        uptime_sec: 60,
        total_requests: 10,
        avg_latency_ms: 12,
        error_count: 0,
        last: { latency_ms: 12, path: '/api/data', status: 200, timestamp: 1000 },
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
      backendMemoryDetails: emptyMemoryDetails(),
      frontendMemory: emptyFrontendMemory(),
      memoryBusy: false,
      frontErrorCount: 0,
      spotImageError: null,
      nowSec: 1000,
    });

    expect(summary.status).toBe('조치 필요');
    expect(summary.cards.find((card) => card.key === 'communication')?.status).toBe('주의');
    expect(summary.cards.find((card) => card.key === 'communication')?.evidence).toContain('대기 3s');
    expect(summary.cards.find((card) => card.key === 'recovery')?.status).toBe('조치 필요');
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

  it('surfaces the dominant 5xx polling route in the HTTP summary', () => {
    const summary = buildObservabilitySummary({
      health: null,
      stats: {
        uptime_sec: 60,
        total_requests: 24,
        avg_latency_ms: 12,
        error_count: 3,
        total_http_5xx_count: 3,
        last: { latency_ms: 10, path: '/api/spot/live_image', status: 503, timestamp: 1 },
        window: {
          window_sec: 60,
          request_count: 24,
          error_count: 3,
          http_error_count: 3,
          http_5xx_count: 3,
          error_rate: 0.125,
          avg_latency_ms: 12,
          p95_latency_ms: 20,
        },
        polling: {
          window_sec: 60,
          paths: {
            '/api/spot/live_image': {
              count: 20,
              requests_per_sec: 0.333,
              avg_latency_ms: 9,
              error_rate: 0.15,
              http_4xx_count: 0,
              http_5xx_count: 3,
              unique_clients: 1,
              top_clients: [{ client: '127.0.0.1', count: 20 }],
            },
          },
        },
      },
      observabilityErrors: null,
      backendMemoryDetails: emptyMemoryDetails(),
      frontendMemory: null,
      memoryBusy: false,
      frontErrorCount: 0,
      spotImageError: null,
    });

    const httpCard = summary.cards.find((card) => card.key === 'http');

    expect(httpCard?.evidence).toContain('route /api/spot/live_image 3건');
    expect(httpCard?.action).toBe('5xx 발생 route를 기준으로 SPOT live/proxy 또는 해당 API handler를 확인.');
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
