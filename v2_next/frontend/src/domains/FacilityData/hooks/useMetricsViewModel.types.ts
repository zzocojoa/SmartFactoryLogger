import type { DashboardLeaderState, FactoryData, ThresholdState } from '../../../shared/types';
import type { SeriesSample } from '../timeseries/seriesSampling';
import type { SeriesFrame } from '../timeseries/seriesDataFrames';

export interface UseMetricsViewModelParams {
  seriesPaused: boolean;
  seriesWindowMin: number;
  showThresholds: boolean;
  thresholdConfig: ThresholdState;
  timeSeriesFrameActive: boolean;
}

export interface UseMetricsViewModel {
  data: FactoryData | null;
  connected: boolean;
  lastDataAt: number | null;
  latencyMs: number | null;
  pollingDegraded: boolean;
  pollingIntervalMs: number;
  pollingFailureCount: number;
  dashboardLeaderState: DashboardLeaderState | null;
  pollingPausedByVisibility: boolean;
  timeSeriesAllFrame: SeriesFrame | null;
  getSeriesSamples: () => SeriesSample[];
  getSeriesStats: () => { count: number; windowMs: number; maxPoints: number | null };
}
