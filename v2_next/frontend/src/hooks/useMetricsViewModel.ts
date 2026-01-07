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

  // Polling Effect
  useEffect(() => {
    let timer: number | null = null;
    let cancelled = false;
    let inFlight = false;

    const tick = async () => {
      if (cancelled || inFlight) return;
      inFlight = true;

      const t0 = performance.now();
      try {
        const latest = await metricService.getLatest();
        const t1 = performance.now();

        if (cancelled) return;

        const sampleTimestamp = Date.now();
        setData(latest);
        setConnected(true);
        setLastDataAt(sampleTimestamp);
        setLatencyMs(Math.round(t1 - t0));

        seriesBufferRef.current.append(buildSeriesSample(latest, sampleTimestamp));
      } catch (err) {
        if (!cancelled) {
          console.error('API Error', err);
          setConnected(false);
          setLatencyMs(null);
        }
      } finally {
        inFlight = false;
      }
    };

    tick();
    timer = window.setInterval(tick, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (timer) window.clearInterval(timer);
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
