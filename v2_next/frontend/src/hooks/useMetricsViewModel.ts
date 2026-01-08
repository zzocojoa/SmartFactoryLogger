import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { metricService } from '../api/metricService';
import { FactoryData } from '../types';
import { SeriesBuffer } from '../timeseries/seriesBuffer';
import { SeriesSample, buildSeriesSample } from '../timeseries/seriesSampling';
import { buildGroupedFrames, buildTimeSeriesFrame, SeriesFrame } from '../timeseries/seriesDataFrames';
import { TIME_SERIES_CATALOG } from '../timeseries/seriesCatalog';
import { buildSeriesThresholds } from '../timeseries/seriesThresholds';
import { ThresholdState } from '../types';

const SERIES_WINDOW_MS = 60 * 60 * 1000; // 1 hour
const SERIES_MAX_POINTS = 7200; // ~2 pts/sec for 1 hour
const POLL_INTERVAL_MS = 500;

export interface UseMetricsViewModelParams {
  seriesPaused: boolean;
  seriesWindowMin: number;
  showThresholds: boolean;
  thresholdConfig: ThresholdState;
}

export interface UseMetricsViewModel {
  data: FactoryData | null;
  connected: boolean;
  lastDataAt: number | null;
  latencyMs: number | null;
  timeSeriesFrames: Record<string, SeriesFrame> | null;
  timeSeriesAllFrame: SeriesFrame | null;
  
  getSeriesSamples: () => SeriesSample[];
}

export const useMetricsViewModel = (params: UseMetricsViewModelParams): UseMetricsViewModel => {
  const { seriesPaused, seriesWindowMin, showThresholds, thresholdConfig } = params;
  
  const [data, setData] = useState<FactoryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastDataAt, setLastDataAt] = useState<number | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  
  const seriesBufferRef = useRef<SeriesBuffer>(new SeriesBuffer(SERIES_WINDOW_MS, SERIES_MAX_POINTS));

  // Web Worker Polling Effect
  useEffect(() => {
    // Create worker instance (Vite syntax)
    const worker = new Worker(new URL('../workers/polling.worker.ts', import.meta.url), { type: 'module' });
    
    worker.onmessage = (e) => {
        const { type, payload } = e.data;
        if (type === 'DATA') {
            const { data: newData, timestamp, latency } = payload;
            
            // Batch updates
            setData(newData);
            setConnected(true);
            setLastDataAt(timestamp);
            setLatencyMs(Math.round(latency));
            
            // Append to series buffer
            seriesBufferRef.current.append(buildSeriesSample(newData, timestamp));
        } else if (type === 'ERROR') {
            console.error('API Error (Worker)', payload.message);
            setConnected(false);
            setLatencyMs(null);
        }
    };

    // Start polling
    worker.postMessage({ type: 'START', payload: { interval: POLL_INTERVAL_MS } });

    // Cleanup
    return () => {
        worker.postMessage({ type: 'STOP' });
        worker.terminate();
    };
  }, []);

  // Time Series Thresholds
  const timeSeriesThresholds = useMemo(() => 
    showThresholds ? buildSeriesThresholds(thresholdConfig) : undefined
  , [thresholdConfig, showThresholds]);

  // Time Series Frames (grouped)
  const timeSeriesFrames = useMemo<Record<string, SeriesFrame> | null>(() => {
    if (seriesPaused) {
      // When paused, still return frames but don't update
      // This requires storing the last frames - simplified: just compute
    }
    const samples = seriesBufferRef.current.getSamples();
    if (!samples.length) {
      return null;
    }
    return buildGroupedFrames(samples, TIME_SERIES_CATALOG, timeSeriesThresholds);
  }, [data, timeSeriesThresholds, seriesPaused]); // data triggers recalc on new poll

  // Time Series All Frame (for Grafana Scenes)
  const timeSeriesAllFrame = useMemo<SeriesFrame | null>(() => {
    const samples = seriesBufferRef.current.getSamples();
    if (!samples.length) {
      return null;
    }
    return buildTimeSeriesFrame(samples, TIME_SERIES_CATALOG, timeSeriesThresholds);
  }, [data, timeSeriesThresholds]);

  const getSeriesSamples = useCallback(() => {
    return seriesBufferRef.current.getSamples();
  }, []);

  return {
    data,
    connected,
    lastDataAt,
    latencyMs,
    timeSeriesFrames,
    timeSeriesAllFrame,
    getSeriesSamples
  };
};
