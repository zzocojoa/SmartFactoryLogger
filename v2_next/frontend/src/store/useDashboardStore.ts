import { create } from 'zustand';
import type { FactoryData, SpotConfig, ThresholdState } from '../shared/types';
import type { SeriesFrame } from '../domains/FacilityData/timeseries/seriesDataFrames';

interface DashboardState {
  // FactoryDataContext
  data: FactoryData | null;
  thresholds: ThresholdState | null;
  lastDataAt: number | null;
  intervalSec: number;
  timeSeriesFrames: Record<string, SeriesFrame> | null;
  timeSeriesAllFrame: SeriesFrame | null;
  
  // SpotContext
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotImageError: string | null;
  spotLastSuccessAt: number | null;
  spotAlertActive: boolean;

  // Actions
  setData: (data: FactoryData | null, lastDataAt: number | null) => void;
  setThresholds: (thresholds: ThresholdState) => void;
  setIntervalSec: (intervalSec: number) => void;
  setTimeSeriesData: (frames: Record<string, SeriesFrame> | null, allFrame: SeriesFrame | null) => void;
  
  setSpotConfig: (config: SpotConfig | null) => void;
  setSpotImageState: (url: string, loading: boolean, error: string | null, lastSuccessAt: number | null) => void;
  setSpotAlertActive: (active: boolean) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  data: null,
  thresholds: null,
  lastDataAt: null,
  intervalSec: 0.2,
  timeSeriesFrames: null,
  timeSeriesAllFrame: null,

  spotConfig: null,
  spotImageUrl: '',
  spotImageLoading: false,
  spotImageError: null,
  spotLastSuccessAt: null,
  spotAlertActive: false,

  setData: (data, lastDataAt) => set({ data, lastDataAt }),
  setThresholds: (thresholds) => set({ thresholds }),
  setIntervalSec: (intervalSec) => set({ intervalSec }),
  setTimeSeriesData: (timeSeriesFrames, timeSeriesAllFrame) => set({ timeSeriesFrames, timeSeriesAllFrame }),
  
  setSpotConfig: (spotConfig) => set({ spotConfig }),
  setSpotImageState: (spotImageUrl, spotImageLoading, spotImageError, spotLastSuccessAt) => set((state) => ({
    spotImageUrl,
    spotImageLoading,
    spotImageError,
    spotLastSuccessAt: spotLastSuccessAt !== null ? spotLastSuccessAt : state.spotLastSuccessAt
  })),
  setSpotAlertActive: (spotAlertActive) => set({ spotAlertActive }),
}));
