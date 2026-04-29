import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import type { DashboardLeaderState, FactoryData } from '../../../shared/types';
import { SeriesBuffer } from '../timeseries/seriesBuffer';
import type { SeriesSample } from '../timeseries/seriesSampling';
import { buildTimeSeriesFrame, SeriesFrame } from '../timeseries/seriesDataFrames';
import { TIME_SERIES_CATALOG } from '../timeseries/seriesCatalog';
import { buildSeriesThresholds } from '../timeseries/seriesThresholds';
import { filterSeriesSamplesByWindow } from './useMetricsViewModel.selectors';
import { useMetricsPollingEffects } from './useMetricsViewModelEffects';
import type { UseMetricsViewModel, UseMetricsViewModelParams } from './useMetricsViewModel.types';
import { useDashboardStore } from '../../../store/useDashboardStore';

const SERIES_WINDOW_MS = 60 * 60 * 1000; // 1 hour
const SERIES_MAX_POINTS = 36000; // 10 pts/sec for 1 hour (Safe buffer for high freq)
const POLL_INTERVAL_MS = 500;
const TIME_SERIES_FRAME_INTERVAL_MS = 1000;

export const useMetricsViewModel = (params: UseMetricsViewModelParams): UseMetricsViewModel => {
  const { seriesPaused, seriesWindowMin, showThresholds, thresholdConfig, timeSeriesFrameActive } = params;
  
  const [data, setData] = useState<FactoryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastDataAt, setLastDataAt] = useState<number | null>(null);
  const [seriesFrameTick, setSeriesFrameTick] = useState(0);
  
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [pollingDegraded, setPollingDegraded] = useState(false);
  const [pollingIntervalMs, setPollingIntervalMs] = useState(POLL_INTERVAL_MS);
  const [pollingFailureCount, setPollingFailureCount] = useState(0);
  const [dashboardLeaderState, setDashboardLeaderState] = useState<DashboardLeaderState | null>(null);
  const [pollingPausedByVisibility, setPollingPausedByVisibility] = useState(false);
  const seriesBufferRef = useRef<SeriesBuffer>(new SeriesBuffer(SERIES_WINDOW_MS, SERIES_MAX_POINTS));
  const frozenAllFrameRef = useRef<SeriesFrame | null>(null);

  const setDashboardData = useDashboardStore(state => state.setData);

  useMetricsPollingEffects({
    pollIntervalMs: POLL_INTERVAL_MS,
    seriesBufferRef,
    setData,
    setConnected,
    setLastDataAt,
    setLatencyMs,
    setPollingDegraded,
    setPollingIntervalMs,
    setPollingFailureCount,
    setDashboardLeaderState,
    setPollingPausedByVisibility,
  });

  useEffect(() => {
    setDashboardData(data, lastDataAt);
  }, [data, lastDataAt, setDashboardData]);

  useEffect(() => {
    if (!timeSeriesFrameActive || seriesPaused) {
      return;
    }

    setSeriesFrameTick(Date.now());
    const timerId = window.setInterval(() => {
      setSeriesFrameTick(Date.now());
    }, TIME_SERIES_FRAME_INTERVAL_MS);

    return () => window.clearInterval(timerId);
  }, [seriesPaused, timeSeriesFrameActive]);

  // Time Series Thresholds
  const timeSeriesThresholds = useMemo(() => 
    showThresholds ? buildSeriesThresholds(thresholdConfig) : undefined
  , [thresholdConfig, showThresholds]);

  const filteredSeriesSamples = useMemo<SeriesSample[] | null>(() => {
    if (!timeSeriesFrameActive) {
      return null;
    }

    const samples = seriesBufferRef.current.getSamples();
    if (!samples.length) {
      return null;
    }

    const filteredSamples = filterSeriesSamplesByWindow(samples, seriesWindowMin);
    if (!filteredSamples.length) {
      return null;
    }

    return filteredSamples;
  }, [seriesFrameTick, seriesWindowMin, timeSeriesFrameActive]);

  // Time Series All Frame (for Grafana Scenes)
  const timeSeriesAllFrame = useMemo<SeriesFrame | null>(() => {
    if (!timeSeriesFrameActive) {
      return frozenAllFrameRef.current;
    }
    if (seriesPaused) {
        return frozenAllFrameRef.current;
    }
    if (!filteredSeriesSamples) {
      return null;
    }

    const result = buildTimeSeriesFrame(filteredSeriesSamples, TIME_SERIES_CATALOG, timeSeriesThresholds);
    frozenAllFrameRef.current = result;
    return result;
  }, [filteredSeriesSamples, timeSeriesThresholds, seriesPaused]);

  const getSeriesSamples = useCallback(() => {
    return seriesBufferRef.current.getSamples();
  }, []);

  const getSeriesStats = useCallback(() => {
    return seriesBufferRef.current.getStats();
  }, []);

  return {
    data,
    connected,
    lastDataAt,
    latencyMs,
    pollingDegraded,
    pollingIntervalMs,
    pollingFailureCount,
    dashboardLeaderState,
    pollingPausedByVisibility,
    timeSeriesAllFrame,
    getSeriesSamples,
    getSeriesStats,
  };
};
