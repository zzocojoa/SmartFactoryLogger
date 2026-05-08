import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import type { DashboardLeaderState, FactoryData } from '../../../shared/types';
import { SeriesBuffer } from '../timeseries/seriesBuffer';
import { buildIncrementalTimeSeriesFrame, buildTimeSeriesFrame } from '../timeseries/seriesDataFrames';
import type { IncrementalSeriesFrameCache, SeriesFrame } from '../timeseries/seriesDataFrames';
import { TIME_SERIES_CATALOG } from '../timeseries/seriesCatalog';
import { buildSeriesThresholds } from '../timeseries/seriesThresholds';
import { filterSeriesSamplesByWindow, getSeriesSamplesWindowRange } from './useMetricsViewModel.selectors';
import { useMetricsPollingEffects } from './useMetricsViewModelEffects';
import type { UseMetricsViewModel, UseMetricsViewModelParams } from './useMetricsViewModel.types';
import { useDashboardStore } from '../../../store/useDashboardStore';

const SERIES_WINDOW_MS = 60 * 60 * 1000; // 1시간
const SERIES_MAX_POINTS = 36000; // 1시간 동안 초당 10포인트를 보관
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
  const incrementalAllFrameCacheRef = useRef<IncrementalSeriesFrameCache | null>(null);

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

  // 시계열 임계값
  const timeSeriesThresholds = useMemo(() => 
    showThresholds ? buildSeriesThresholds(thresholdConfig) : undefined
  , [thresholdConfig, showThresholds]);

  // Grafana Scenes용 전체 시계열 프레임
  const timeSeriesAllFrame = useMemo<SeriesFrame | null>(() => {
    if (!timeSeriesFrameActive) {
      return frozenAllFrameRef.current;
    }
    if (seriesPaused) {
        return frozenAllFrameRef.current;
    }
    const snapshot = seriesBufferRef.current.getSnapshot();
    if (!snapshot.samples.length) {
      return null;
    }

    if (!snapshot.chronological) {
      const filteredSamples = filterSeriesSamplesByWindow(snapshot.samples, seriesWindowMin);
      if (!filteredSamples.length) {
        return null;
      }
      incrementalAllFrameCacheRef.current = null;
      const result = buildTimeSeriesFrame(filteredSamples, TIME_SERIES_CATALOG, timeSeriesThresholds);
      frozenAllFrameRef.current = result;
      return result;
    }

    const range = getSeriesSamplesWindowRange(snapshot.samples, seriesWindowMin, Date.now());
    if (range.startIndex >= range.endIndex) {
      return null;
    }

    const result = buildIncrementalTimeSeriesFrame({
      snapshot,
      range,
      previousCache: incrementalAllFrameCacheRef.current,
      metas: TIME_SERIES_CATALOG,
      thresholdsByKey: timeSeriesThresholds,
    });
    incrementalAllFrameCacheRef.current = result.cache;
    frozenAllFrameRef.current = result.frame;
    return result.frame;
  }, [seriesFrameTick, timeSeriesThresholds, seriesPaused, seriesWindowMin, timeSeriesFrameActive]);

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
