import type { FactoryData, ThresholdState } from '../../../shared/types';
import type { SeriesSample } from '../timeseries/seriesSampling';
import type { SeriesFrame } from '../timeseries/seriesDataFrames';

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
