import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockValues = vi.hoisted(() => ({
  getMemoryDetails: vi.fn(),
  getAIDiagnostics: vi.fn(() => ({
    estimatedBytes: 512,
    messageCount: 1,
    toolCount: 0,
  })),
}));

vi.mock('../api/systemService', () => ({
  systemService: {
    getMemoryDetails: mockValues.getMemoryDetails,
  },
}));

vi.mock('../../../AI/state/aiDiagnostics', () => ({
  getAIDiagnostics: mockValues.getAIDiagnostics,
}));

import {
  buildFrontendAlerts,
  readBrowserMemorySupport,
  readElectronMemorySnapshot,
  useMemoryViewModel,
} from './useMemoryViewModel';
import type { FrontendMemorySnapshot } from '../../../shared/types';

const emptyMemoryDetails = {
  backend_top_consumers: [],
  backend_growth: [],
  collector_history: [],
  leak_suspects: [],
  latest_gc_snapshot: null,
  latest_tracemalloc_diff: [],
};

const buildParams = (): Parameters<typeof useMemoryViewModel>[0] => ({
  enabled: false,
  seriesStats: { count: 3, windowMs: 60000, maxPoints: 120 },
  timeSeriesAllFrame: null,
  layoutSnapshot: null,
  observabilityErrors: null,
  frontErrors: [],
  spotImageUrl: '',
  spotDiagnostics: {
    in_flight: false,
    refresh_interval_ms: null,
    fetch_count: 0,
    error_count: 0,
    automatic_retry_count: 0,
    consecutive_retry_attempt: 0,
    automatic_retry_pending: false,
    automatic_retry_exhausted: false,
    next_retry_scheduled_at: null,
    last_failure_retryable: null,
    last_fetch_started_at: null,
    last_fetch_completed_at: null,
    last_fetch_latency_ms: null,
    next_fetch_scheduled_at: null,
    last_fetch_reason: null,
  },
  settingsForm: null,
  settingsPending: null,
  externalConfigPending: null,
});

beforeEach(() => {
  mockValues.getMemoryDetails.mockResolvedValue(emptyMemoryDetails);
  window.localStorage.clear();
  window.sessionStorage.clear();
});

afterEach(() => {
  delete window.smartFactoryElectron;
  const perf = performance as Performance & {
    memory?: unknown;
    measureUserAgentSpecificMemory?: unknown;
  };
  delete perf.memory;
  delete perf.measureUserAgentSpecificMemory;
  vi.clearAllMocks();
});

describe('readElectronMemorySnapshot', () => {
  it('returns a browser fallback when the Electron bridge is unavailable', async () => {
    delete window.smartFactoryElectron;

    const snapshot = await readElectronMemorySnapshot();

    expect(snapshot.supported).toBe(false);
    expect(snapshot.source).toBe('browser');
    expect(snapshot.process).toBeNull();
    expect(snapshot.metrics).toEqual([]);
    expect(snapshot.error).toBeNull();
  });

  it('invokes the constrained Electron memory bridge when available', async () => {
    const getMemory = vi.fn().mockResolvedValue({
      supported: true,
      source: 'electron',
      captured_at: 1790000000,
      process: { privateBytes: 1024, workingSetSize: 2048 },
      metrics: [
        {
          pid: 123,
          type: 'renderer',
          memory: { privateBytes: 4096 },
          cpu: { percentCPUUsage: 1.25 },
        },
      ],
      v8_heap: { used_heap_size: 1024 * 1024 },
      error: null,
    });
    window.smartFactoryElectron = { getMemory, recordStartupEvent: vi.fn() };

    const snapshot = await readElectronMemorySnapshot();

    expect(getMemory).toHaveBeenCalledOnce();
    expect(snapshot.supported).toBe(true);
    expect(snapshot.source).toBe('electron');
    expect(snapshot.process?.privateBytes).toBe(1024);
    expect(snapshot.metrics).toHaveLength(1);
    expect(snapshot.metrics[0].type).toBe('renderer');
  });
});

describe('frontend memory exactness', () => {
  it('marks browser memory API support as observed', async () => {
    Object.defineProperty(performance, 'memory', {
      configurable: true,
      value: {
        usedJSHeapSize: 4 * 1024 * 1024,
        totalJSHeapSize: 8 * 1024 * 1024,
        jsHeapSizeLimit: 64 * 1024 * 1024,
      },
    });

    const support = await readBrowserMemorySupport();

    expect(support.supported).toBe(true);
    expect(support.mode).toBe('performance-memory');
    expect(support.exactness).toBe('observed');
  });

  it('marks unsupported browser memory unavailable and storage exactness estimated-enumerated', async () => {
    window.localStorage.setItem('memory-key', 'x'.repeat(128));
    window.sessionStorage.setItem('memory-session-key', 'y'.repeat(64));
    const { result } = renderHook(() => useMemoryViewModel(buildParams()));

    await act(async () => {
      await result.current.refreshMemory();
    });

    const snapshot = result.current.frontendMemory;
    const collectors = new Map((snapshot?.top_consumers ?? []).map((item) => [item.name, item]));

    expect(snapshot?.support.exactness).toBe('unavailable');
    expect(collectors.get('frontend.browser_heap')?.exactness).toBe('unavailable');
    expect(collectors.get('frontend.local_storage')?.exactness).toBe('estimated-enumerated');
    expect(collectors.get('frontend.session_storage')?.exactness).toBe('estimated-enumerated');
    expect(collectors.get('frontend.series_buffer')?.exactness).toBe('estimated');
  });

  it('downgrades estimated app growth while preserving observed heap growth warnings', () => {
    const baseSnapshot: FrontendMemorySnapshot = {
      captured_at: 61,
      support: { mode: 'unsupported', supported: false, exactness: 'unavailable' },
      top_consumers: [],
      growth: [],
      alerts: [],
      last_refresh_at: 61000,
      history: [
        { captured_at: 0, app_bytes: 1024, heap_used_bytes: null, heap_total_bytes: null },
        { captured_at: 61, app_bytes: 80 * 1024 * 1024, heap_used_bytes: null, heap_total_bytes: null },
      ],
    };

    const estimatedAlerts = buildFrontendAlerts(null, baseSnapshot, null);
    const observedAlerts = buildFrontendAlerts(
      null,
      {
        ...baseSnapshot,
        support: { mode: 'performance-memory', supported: true, exactness: 'observed' },
        history: [
          { captured_at: 0, app_bytes: 1024, heap_used_bytes: 1024, heap_total_bytes: 4096 },
          {
            captured_at: 61,
            app_bytes: 80 * 1024 * 1024,
            heap_used_bytes: 80 * 1024 * 1024,
            heap_total_bytes: 96 * 1024 * 1024,
          },
        ],
      },
      null
    );

    expect(estimatedAlerts).toContainEqual(
      expect.objectContaining({ key: 'frontend-estimated-growth', severity: 'info' })
    );
    expect(estimatedAlerts).not.toContainEqual(
      expect.objectContaining({ key: 'frontend-growth', severity: 'warn' })
    );
    expect(observedAlerts).toContainEqual(
      expect.objectContaining({ key: 'frontend-growth', severity: 'warn' })
    );
  });
});
