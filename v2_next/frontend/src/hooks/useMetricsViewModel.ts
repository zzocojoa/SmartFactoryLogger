import { useState, useCallback, useRef, useMemo } from 'react';
import type { FactoryData } from '../types';
import { SeriesBuffer } from '../timeseries/seriesBuffer';
import type { SeriesSample } from '../timeseries/seriesSampling';
import { buildGroupedFrames, buildTimeSeriesFrame, SeriesFrame } from '../timeseries/seriesDataFrames';
import { TIME_SERIES_CATALOG } from '../timeseries/seriesCatalog';
import { buildSeriesThresholds } from '../timeseries/seriesThresholds';
import { filterSeriesSamplesByWindow } from './useMetricsViewModel.selectors';
import { useMetricsPollingEffects } from './useMetricsViewModelEffects';
import type { UseMetricsViewModel, UseMetricsViewModelParams } from './useMetricsViewModel.types';

const SERIES_WINDOW_MS = 60 * 60 * 1000; // 1 hour
const SERIES_MAX_POINTS = 36000; // 10 pts/sec for 1 hour (Safe buffer for high freq)
const POLL_INTERVAL_MS = 500;

export const useMetricsViewModel = (params: UseMetricsViewModelParams): UseMetricsViewModel => {
  const { seriesPaused, seriesWindowMin, showThresholds, thresholdConfig } = params;
  
  const [data, setData] = useState<FactoryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastDataAt, setLastDataAt] = useState<number | null>(null);
  
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const seriesBufferRef = useRef<SeriesBuffer>(new SeriesBuffer(SERIES_WINDOW_MS, SERIES_MAX_POINTS));
  const frozenFramesRef = useRef<Record<string, SeriesFrame> | null>(null);
  const frozenAllFrameRef = useRef<SeriesFrame | null>(null);

  useMetricsPollingEffects({
    pollIntervalMs: POLL_INTERVAL_MS,
    seriesBufferRef,
    setData,
    setConnected,
    setLastDataAt,
    setLatencyMs,
  });

  // Time Series Thresholds
  const timeSeriesThresholds = useMemo(() => 
    showThresholds ? buildSeriesThresholds(thresholdConfig) : undefined
  , [thresholdConfig, showThresholds]);

  // Time Series Frames (grouped)
  const timeSeriesFrames = useMemo<Record<string, SeriesFrame> | null>(() => {
    if (seriesPaused) {
      return frozenFramesRef.current;
    }
    const samples = seriesBufferRef.current.getSamples();
    if (!samples.length) {
      return null;
    }
    
    const filteredSamples = filterSeriesSamplesByWindow(samples, seriesWindowMin);
    
    if (filteredSamples.length === 0) return null;

    const result = buildGroupedFrames(filteredSamples, TIME_SERIES_CATALOG, timeSeriesThresholds);
    frozenFramesRef.current = result;
    return result;
  }, [data, timeSeriesThresholds, seriesPaused, seriesWindowMin]); // data triggers recalc on new poll

  // Time Series All Frame (for Grafana Scenes)
  const timeSeriesAllFrame = useMemo<SeriesFrame | null>(() => {
    if (seriesPaused) {
        return frozenAllFrameRef.current;
    }

    const samples = seriesBufferRef.current.getSamples();
    if (!samples.length) {
      return null;
    }

    const filteredSamples = filterSeriesSamplesByWindow(samples, seriesWindowMin);
    
    if (filteredSamples.length === 0) return null;

    const result = buildTimeSeriesFrame(filteredSamples, TIME_SERIES_CATALOG, timeSeriesThresholds);
    frozenAllFrameRef.current = result;
    return result;
  }, [data, timeSeriesThresholds, seriesWindowMin, seriesPaused]);

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
