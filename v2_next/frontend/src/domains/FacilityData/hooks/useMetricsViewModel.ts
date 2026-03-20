import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import type { DashboardLeaderState, FactoryData } from '../../../shared/types';
import { SeriesBuffer } from '../timeseries/seriesBuffer';
import type { SeriesSample } from '../timeseries/seriesSampling';
import { buildGroupedFrames, buildTimeSeriesFrame, SeriesFrame } from '../timeseries/seriesDataFrames';
import { TIME_SERIES_CATALOG } from '../timeseries/seriesCatalog';
import { buildSeriesThresholds } from '../timeseries/seriesThresholds';
import { filterSeriesSamplesByWindow } from './useMetricsViewModel.selectors';
import { useMetricsPollingEffects } from './useMetricsViewModelEffects';
import type { UseMetricsViewModel, UseMetricsViewModelParams } from './useMetricsViewModel.types';
import { useDashboardStore } from '../../../store/useDashboardStore';

const SERIES_WINDOW_MS = 60 * 60 * 1000; // 1 hour
const SERIES_MAX_POINTS = 36000; // 10 pts/sec for 1 hour (Safe buffer for high freq)
const POLL_INTERVAL_MS = 500;

export const useMetricsViewModel = (params: UseMetricsViewModelParams): UseMetricsViewModel => {
  const { seriesPaused, seriesWindowMin, showThresholds, thresholdConfig } = params;
  
  const [data, setData] = useState<FactoryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastDataAt, setLastDataAt] = useState<number | null>(null);
  
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [pollingDegraded, setPollingDegraded] = useState(false);
  const [pollingIntervalMs, setPollingIntervalMs] = useState(POLL_INTERVAL_MS);
  const [pollingFailureCount, setPollingFailureCount] = useState(0);
  const [dashboardLeaderState, setDashboardLeaderState] = useState<DashboardLeaderState | null>(null);
  const [pollingPausedByVisibility, setPollingPausedByVisibility] = useState(false);
  const seriesBufferRef = useRef<SeriesBuffer>(new SeriesBuffer(SERIES_WINDOW_MS, SERIES_MAX_POINTS));
  const frozenFramesRef = useRef<Record<string, SeriesFrame> | null>(null);
  const frozenAllFrameRef = useRef<SeriesFrame | null>(null);

  const setDashboardData = useDashboardStore(state => state.setData);
  const setDashboardTimeSeries = useDashboardStore(state => state.setTimeSeriesData);

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

  // Time Series Thresholds
  const timeSeriesThresholds = useMemo(() => 
    showThresholds ? buildSeriesThresholds(thresholdConfig) : undefined
  , [thresholdConfig, showThresholds]);

  const filteredSeriesSamples = useMemo<SeriesSample[] | null>(() => {
    const samples = seriesBufferRef.current.getSamples();
    if (!samples.length) {
      return null;
    }

    const filteredSamples = filterSeriesSamplesByWindow(samples, seriesWindowMin);
    if (!filteredSamples.length) {
      return null;
    }

    return filteredSamples;
  }, [data, seriesWindowMin]);

  // Time Series Frames (grouped)
  const timeSeriesFrames = useMemo<Record<string, SeriesFrame> | null>(() => {
    if (seriesPaused) {
      return frozenFramesRef.current;
    }
    if (!filteredSeriesSamples) {
      return null;
    }

    const result = buildGroupedFrames(filteredSeriesSamples, TIME_SERIES_CATALOG, timeSeriesThresholds);
    frozenFramesRef.current = result;
    return result;
  }, [filteredSeriesSamples, timeSeriesThresholds, seriesPaused]);

  // Time Series All Frame (for Grafana Scenes)
  const timeSeriesAllFrame = useMemo<SeriesFrame | null>(() => {
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

  useEffect(() => {
    setDashboardTimeSeries(timeSeriesFrames, timeSeriesAllFrame);
  }, [timeSeriesFrames, timeSeriesAllFrame, setDashboardTimeSeries]);

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
    timeSeriesFrames,
    timeSeriesAllFrame,
    getSeriesSamples,
    getSeriesStats,
  };
};
