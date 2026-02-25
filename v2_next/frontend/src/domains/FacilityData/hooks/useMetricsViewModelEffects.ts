import { useEffect } from 'react';
import type { Dispatch, MutableRefObject, SetStateAction } from 'react';
import type { FactoryData } from '../../../shared/types';
import { buildSeriesSample } from '../timeseries/seriesSampling';
import type { SeriesBuffer } from '../timeseries/seriesBuffer';
import type { WorkerDataPayload, WorkerOutboundMessage } from '../workers/polling.worker.types';
import { createPollingWorker, startPollingWorker, stopPollingWorker } from './useMetricsViewModel.service';

interface UseMetricsPollingEffectsParams {
  pollIntervalMs: number;
  seriesBufferRef: MutableRefObject<SeriesBuffer>;
  setData: Dispatch<SetStateAction<FactoryData | null>>;
  setConnected: Dispatch<SetStateAction<boolean>>;
  setLastDataAt: Dispatch<SetStateAction<number | null>>;
  setLatencyMs: Dispatch<SetStateAction<number | null>>;
}

const handleWorkerDataMessage = (
  payload: WorkerDataPayload,
  params: Omit<UseMetricsPollingEffectsParams, 'pollIntervalMs' | 'seriesBufferRef'> & {
    seriesBufferRef: MutableRefObject<SeriesBuffer>;
  }
) => {
  const { data, timestamp, latency } = payload;
  params.setData(data);
  params.setConnected(true);
  params.setLastDataAt(timestamp);
  params.setLatencyMs(Math.round(latency));
  params.seriesBufferRef.current.append(buildSeriesSample(data, timestamp));
};

export const useMetricsPollingEffects = ({
  pollIntervalMs,
  seriesBufferRef,
  setData,
  setConnected,
  setLastDataAt,
  setLatencyMs,
}: UseMetricsPollingEffectsParams) => {
  useEffect(() => {
    const worker = createPollingWorker();

    worker.onmessage = (event: MessageEvent<WorkerOutboundMessage>) => {
      const { type, payload } = event.data;
      if (type === 'DATA') {
        handleWorkerDataMessage(payload, {
          seriesBufferRef,
          setData,
          setConnected,
          setLastDataAt,
          setLatencyMs,
        });
        return;
      }

      console.error('API Error (Worker)', payload.message);
      setConnected(false);
      setLatencyMs(null);
    };

    startPollingWorker(worker, pollIntervalMs);

    return () => {
      stopPollingWorker(worker);
      worker.terminate();
    };
  }, [pollIntervalMs, seriesBufferRef, setConnected, setData, setLastDataAt, setLatencyMs]);
};
