import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MutableRefObject } from 'react';
import type { FactoryData } from '../../../shared/types';
import type { WorkerOutboundMessage } from '../workers/polling.worker.types';
import { SeriesBuffer } from '../timeseries/seriesBuffer';
import { buildSeriesSample } from '../timeseries/seriesSampling';
import { useMetricsPollingEffects } from './useMetricsViewModelEffects';

const mocks = vi.hoisted(() => ({
  createPollingWorker: vi.fn<() => Worker>(),
  fetchLatestMetricOnMainThreadWithLatency: vi.fn(),
  fetchMetricHistorySinceOnMainThreadWithLatency: vi.fn(),
  releasePollingWorker: vi.fn(),
  startPollingWorker: vi.fn(),
  stopPollingWorker: vi.fn(),
}));

vi.mock('./useMetricsViewModel.service', () => ({
  createPollingWorker: mocks.createPollingWorker,
  fetchLatestMetricOnMainThreadWithLatency: mocks.fetchLatestMetricOnMainThreadWithLatency,
  fetchMetricHistorySinceOnMainThreadWithLatency: mocks.fetchMetricHistorySinceOnMainThreadWithLatency,
  releasePollingWorker: mocks.releasePollingWorker,
  startPollingWorker: mocks.startPollingWorker,
  stopPollingWorker: mocks.stopPollingWorker,
}));

const buildFactoryData = (timestampMs: number, spotValue: number, sampleTimestampMs?: number): FactoryData => ({
  Time: new Date(timestampMs).toISOString(),
  Status: 'Running',
  timestamp_ms: sampleTimestampMs ?? null,
  Speed: 1,
  Press: 2,
  Count: 3,
  EndPos: 4,
  Billet_Length: 5,
  Die_ID: null,
  Billet_Cycle_ID: null,
  Spot: spotValue,
  Temp_F: 6,
  Temp_B: 7,
  Billet_Temp: 8,
  Mold1: 9,
  Mold2: 10,
  Mold3: 11,
  Mold4: 12,
  Mold5: 13,
  Mold6: 14,
  At_Temp: 15,
  At_Pre: 16,
});

const buildHistoryResponse = (
  samples: Array<{ timestamp_ms: number; data: FactoryData }>,
  truncated = false
) => ({
  samples,
  oldest_timestamp_ms: samples[0]?.timestamp_ms ?? null,
  newest_timestamp_ms: samples[samples.length - 1]?.timestamp_ms ?? null,
  history_instance_id: 'test-history',
  truncated,
});

const setVisibilityState = (visibilityState: DocumentVisibilityState): void => {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => visibilityState,
  });
};

const renderPollingEffects = (seriesBufferRef: MutableRefObject<SeriesBuffer>) =>
  renderHook(() =>
    useMetricsPollingEffects({
      pollIntervalMs: 500,
      seriesBufferRef,
      setData: vi.fn(),
      setConnected: vi.fn(),
      setLastDataAt: vi.fn(),
      setLatencyMs: vi.fn(),
      setPollingDegraded: vi.fn(),
      setPollingIntervalMs: vi.fn(),
      setPollingFailureCount: vi.fn(),
      setDashboardLeaderState: vi.fn(),
      setPollingPausedByVisibility: vi.fn(),
    })
  );

describe('useMetricsPollingEffects', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    delete window.smartFactoryElectron;
    vi.stubGlobal('BroadcastChannel', undefined);
    mocks.createPollingWorker.mockReturnValue({} as Worker);
    mocks.fetchMetricHistorySinceOnMainThreadWithLatency.mockReset();
    mocks.fetchLatestMetricOnMainThreadWithLatency.mockReset();
    mocks.releasePollingWorker.mockReset();
    mocks.startPollingWorker.mockReset();
    mocks.stopPollingWorker.mockReset();
  });

  afterEach(() => {
    setVisibilityState('visible');
    delete window.smartFactoryElectron;
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('backfills missing history before resuming visible polling', async () => {
    setVisibilityState('hidden');
    const seriesBufferRef: MutableRefObject<SeriesBuffer> = {
      current: new SeriesBuffer(10_000, 10),
    };
    seriesBufferRef.current.append(buildSeriesSample(buildFactoryData(1_000, 10), 1_000));
    mocks.fetchMetricHistorySinceOnMainThreadWithLatency.mockResolvedValue({
      data: buildHistoryResponse([
        { timestamp_ms: 1_000, data: buildFactoryData(1_000, 100) },
        { timestamp_ms: 2_000, data: buildFactoryData(9_000, 20) },
      ]),
      latency: 3,
      timestamp: 2_500,
    });

    const { unmount } = renderPollingEffects(seriesBufferRef);

    try {
      await act(async () => {
        setVisibilityState('visible');
        document.dispatchEvent(new Event('visibilitychange'));
      });

      await waitFor(() => {
        expect(mocks.fetchMetricHistorySinceOnMainThreadWithLatency).toHaveBeenCalledWith(1_000);
      });
      await waitFor(() => {
        expect(mocks.startPollingWorker).toHaveBeenCalledWith(expect.anything(), 500);
      });

      expect(seriesBufferRef.current.getSamples().map((sample) => sample.timestampMs)).toEqual([1_000, 2_000]);
      expect(seriesBufferRef.current.getSamples().map((sample) => sample.values.Spot)).toEqual([10, 20]);
    } finally {
      unmount();
    }
  });

  it('recovers packaged startup data while hidden and a stale leader lock exists', async () => {
    setVisibilityState('hidden');
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: vi.fn(),
    };
    window.localStorage.setItem(
      'dashboard_polling_leader_v1',
      JSON.stringify({ tab_id: 'stale-tab', updated_at: Date.now() })
    );
    const worker = {} as Worker;
    mocks.createPollingWorker.mockReturnValue(worker);
    const seriesBufferRef: MutableRefObject<SeriesBuffer> = {
      current: new SeriesBuffer(10_000, 10),
    };

    const { unmount } = renderPollingEffects(seriesBufferRef);

    try {
      await waitFor(() => {
        expect(mocks.startPollingWorker).toHaveBeenCalledWith(worker, 500);
      });

      const initializingMessage: MessageEvent<WorkerOutboundMessage> = {
        data: {
          type: 'DATA',
          payload: {
            data: {
              ...buildFactoryData(1_000, 10, 1_000),
              Status: 'Initializing',
            },
            latency: 3,
            timestamp: 1_000,
            poll_interval_ms: 500,
            failure_count: 0,
          },
        },
      } as MessageEvent<WorkerOutboundMessage>;

      await act(async () => {
        worker.onmessage?.call(worker, initializingMessage);
      });

      expect(mocks.stopPollingWorker).not.toHaveBeenCalled();

      const liveMessage: MessageEvent<WorkerOutboundMessage> = {
        data: {
          type: 'DATA',
          payload: {
            data: buildFactoryData(2_000, 20, 2_000),
            latency: 3,
            timestamp: 2_000,
            poll_interval_ms: 500,
            failure_count: 0,
          },
        },
      } as MessageEvent<WorkerOutboundMessage>;

      await act(async () => {
        worker.onmessage?.call(worker, liveMessage);
      });

      expect(seriesBufferRef.current.getSamples()).toHaveLength(2);
      expect(mocks.stopPollingWorker).toHaveBeenCalledWith(worker);
    } finally {
      unmount();
    }
  });

  it('does not re-enter packaged startup recovery after operational data later goes offline', async () => {
    window.smartFactoryElectron = {
      getMemory: vi.fn(),
      recordStartupEvent: vi.fn(),
    };
    const worker = {} as Worker;
    mocks.createPollingWorker.mockReturnValue(worker);
    const seriesBufferRef: MutableRefObject<SeriesBuffer> = {
      current: new SeriesBuffer(10_000, 10),
    };

    const { unmount } = renderPollingEffects(seriesBufferRef);

    try {
      await waitFor(() => {
        expect(mocks.startPollingWorker).toHaveBeenCalledWith(worker, 500);
      });

      const buildWorkerMessage = (status: string, timestamp: number): MessageEvent<WorkerOutboundMessage> => ({
        data: {
          type: 'DATA',
          payload: {
            data: {
              ...buildFactoryData(timestamp, 20, timestamp),
              Status: status,
            },
            latency: 3,
            timestamp,
            poll_interval_ms: 500,
            failure_count: 0,
          },
        },
      } as MessageEvent<WorkerOutboundMessage>);

      await act(async () => {
        worker.onmessage?.call(worker, buildWorkerMessage('Running', 2_000));
        worker.onmessage?.call(worker, buildWorkerMessage('Offline', 3_000));
        setVisibilityState('hidden');
        document.dispatchEvent(new Event('visibilitychange'));
      });

      expect(mocks.stopPollingWorker).toHaveBeenCalledWith(worker);
    } finally {
      unmount();
    }
  });

  it('resumes visible polling when history backfill fails', async () => {
    setVisibilityState('hidden');
    const consoleWarnMock = vi.spyOn(console, 'warn').mockImplementation((): void => undefined);
    const seriesBufferRef: MutableRefObject<SeriesBuffer> = {
      current: new SeriesBuffer(10_000, 10),
    };
    seriesBufferRef.current.append(buildSeriesSample(buildFactoryData(1_000, 10), 1_000));
    mocks.fetchMetricHistorySinceOnMainThreadWithLatency.mockRejectedValue(new Error('history unavailable'));

    const { unmount } = renderPollingEffects(seriesBufferRef);

    try {
      await act(async () => {
        setVisibilityState('visible');
        document.dispatchEvent(new Event('visibilitychange'));
      });

      await waitFor(() => {
        expect(mocks.startPollingWorker).toHaveBeenCalledWith(expect.anything(), 500);
      });
      expect(consoleWarnMock).toHaveBeenCalledWith(
        'Metric history backfill failed',
        expect.objectContaining({ since_ms: 1_000 })
      );
      expect(seriesBufferRef.current.getSamples().map((sample) => sample.timestampMs)).toEqual([1_000]);
    } finally {
      unmount();
    }
  });

  it('backfills a visible follower tab without starting duplicate polling', async () => {
    setVisibilityState('hidden');
    const seriesBufferRef: MutableRefObject<SeriesBuffer> = {
      current: new SeriesBuffer(10_000, 10),
    };
    seriesBufferRef.current.append(buildSeriesSample(buildFactoryData(1_000, 10), 1_000));
    window.localStorage.setItem(
      'dashboard_polling_leader_v1',
      JSON.stringify({ tab_id: 'other-tab', updated_at: Date.now() })
    );
    mocks.fetchMetricHistorySinceOnMainThreadWithLatency.mockResolvedValue({
      data: buildHistoryResponse([{ timestamp_ms: 2_000, data: buildFactoryData(9_000, 20) }]),
      latency: 3,
      timestamp: 2_500,
    });

    const { unmount } = renderPollingEffects(seriesBufferRef);

    try {
      await act(async () => {
        setVisibilityState('visible');
        document.dispatchEvent(new Event('visibilitychange'));
      });

      await waitFor(() => {
        expect(mocks.fetchMetricHistorySinceOnMainThreadWithLatency).toHaveBeenCalledWith(1_000);
      });

      expect(mocks.startPollingWorker).not.toHaveBeenCalled();
      expect(seriesBufferRef.current.getSamples().map((sample) => sample.timestampMs)).toEqual([1_000, 2_000]);
      expect(seriesBufferRef.current.getSamples().map((sample) => sample.values.Spot)).toEqual([10, 20]);
    } finally {
      unmount();
    }
  });

  it('clears stale samples when history response says the requested range was truncated', async () => {
    setVisibilityState('hidden');
    const seriesBufferRef: MutableRefObject<SeriesBuffer> = {
      current: new SeriesBuffer(10_000, 10),
    };
    seriesBufferRef.current.append(buildSeriesSample(buildFactoryData(1_000, 10), 1_000));
    mocks.fetchMetricHistorySinceOnMainThreadWithLatency.mockResolvedValue({
      data: buildHistoryResponse([{ timestamp_ms: 5_000, data: buildFactoryData(9_000, 50) }], true),
      latency: 3,
      timestamp: 5_500,
    });

    const { unmount } = renderPollingEffects(seriesBufferRef);

    try {
      await act(async () => {
        setVisibilityState('visible');
        document.dispatchEvent(new Event('visibilitychange'));
      });

      await waitFor(() => {
        expect(mocks.fetchMetricHistorySinceOnMainThreadWithLatency).toHaveBeenCalledWith(1_000);
      });

      expect(seriesBufferRef.current.getSamples().map((sample) => sample.timestampMs)).toEqual([5_000]);
      expect(seriesBufferRef.current.getSamples().map((sample) => sample.values.Spot)).toEqual([50]);
    } finally {
      unmount();
    }
  });

  it('ignores late worker data after visibility pauses polling', async () => {
    setVisibilityState('visible');
    const worker = {} as Worker;
    mocks.createPollingWorker.mockReturnValue(worker);
    const seriesBufferRef: MutableRefObject<SeriesBuffer> = {
      current: new SeriesBuffer(10_000, 10),
    };

    const { unmount } = renderPollingEffects(seriesBufferRef);

    try {
      await waitFor(() => {
        expect(mocks.startPollingWorker).toHaveBeenCalledWith(worker, 500);
      });

      await act(async () => {
        setVisibilityState('hidden');
        document.dispatchEvent(new Event('visibilitychange'));
      });

      const lateMessage: MessageEvent<WorkerOutboundMessage> = {
        data: {
          type: 'DATA',
          payload: {
            data: buildFactoryData(2_000, 20),
            latency: 3,
            timestamp: 2_000,
            poll_interval_ms: 500,
            failure_count: 0,
          },
        },
      } as MessageEvent<WorkerOutboundMessage>;

      await act(async () => {
        worker.onmessage?.call(worker, lateMessage);
      });

      expect(seriesBufferRef.current.getSamples()).toHaveLength(0);
    } finally {
      unmount();
    }
  });

  it('uses transport timestamp for live samples instead of parsing FactoryData.Time', async () => {
    setVisibilityState('visible');
    const worker = {} as Worker;
    mocks.createPollingWorker.mockReturnValue(worker);
    const seriesBufferRef: MutableRefObject<SeriesBuffer> = {
      current: new SeriesBuffer(10_000, 10),
    };

    const { unmount } = renderPollingEffects(seriesBufferRef);

    try {
      await waitFor(() => {
        expect(mocks.startPollingWorker).toHaveBeenCalledWith(worker, 500);
      });

      const liveMessage: MessageEvent<WorkerOutboundMessage> = {
        data: {
          type: 'DATA',
          payload: {
            data: buildFactoryData(1_000, 20, 2_000),
            latency: 3,
            timestamp: 2_000,
            poll_interval_ms: 500,
            failure_count: 0,
          },
        },
      } as MessageEvent<WorkerOutboundMessage>;

      await act(async () => {
        worker.onmessage?.call(worker, liveMessage);
      });

      expect(seriesBufferRef.current.getSamples().map((sample) => sample.timestampMs)).toEqual([2_000]);
      expect(seriesBufferRef.current.getSamples().map((sample) => sample.values.Spot)).toEqual([20]);
    } finally {
      unmount();
    }
  });
});
