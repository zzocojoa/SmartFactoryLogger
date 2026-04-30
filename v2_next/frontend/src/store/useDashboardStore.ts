import { create } from 'zustand';
import type { FactoryData, SpotConfig, ThresholdState } from '../shared/types';
import type { SpotImageResponseMetadata } from '../domains/FacilityData/api/spotService.types';

interface DashboardState {
  // FactoryDataContext
  data: FactoryData | null;
  thresholds: ThresholdState | null;
  lastDataAt: number | null;
  intervalSec: number;
  
  // SpotContext
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotImageError: string | null;
  spotLastSuccessAt: number | null;
  spotImageMetadata: SpotImageResponseMetadata | null;
  spotAlertActive: boolean;

  // Actions
  setData: (data: FactoryData | null, lastDataAt: number | null) => void;
  setThresholds: (thresholds: ThresholdState) => void;
  setIntervalSec: (intervalSec: number) => void;
  
  setSpotConfig: (config: SpotConfig | null) => void;
  setSpotImageState: (
    url: string,
    loading: boolean,
    error: string | null,
    lastSuccessAt: number | null,
    metadata?: SpotImageResponseMetadata | null
  ) => void;
  setSpotAlertActive: (active: boolean) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  data: null,
  thresholds: null,
  lastDataAt: null,
  intervalSec: 0.2,

  spotConfig: null,
  spotImageUrl: '',
  spotImageLoading: false,
  spotImageError: null,
  spotLastSuccessAt: null,
  spotImageMetadata: null,
  spotAlertActive: false,

  setData: (data, lastDataAt) => set({ data, lastDataAt }),
  setThresholds: (thresholds) => set({ thresholds }),
  setIntervalSec: (intervalSec) => set({ intervalSec }),
  
  setSpotConfig: (spotConfig) => set({ spotConfig }),
  setSpotImageState: (
    spotImageUrl,
    spotImageLoading,
    spotImageError,
    spotLastSuccessAt,
    spotImageMetadata
  ) => set((state) => ({
    spotImageUrl,
    spotImageLoading,
    spotImageError,
    spotLastSuccessAt: spotLastSuccessAt !== null ? spotLastSuccessAt : state.spotLastSuccessAt,
    spotImageMetadata: spotImageMetadata !== undefined ? spotImageMetadata : state.spotImageMetadata,
  })),
  setSpotAlertActive: (spotAlertActive) => set({ spotAlertActive }),
}));
