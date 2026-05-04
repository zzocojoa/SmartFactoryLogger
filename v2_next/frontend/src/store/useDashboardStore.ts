import { create } from 'zustand';
import type { FactoryData, SpotConfig, ThresholdState } from '../shared/types';
import type { SpotImageResponseMetadata } from '../domains/FacilityData/api/spotService.types';

const areSpotConfigsEqual = (first: SpotConfig, second: SpotConfig): boolean => {
  return (
    first.image_url === second.image_url &&
    first.refresh_interval === second.refresh_interval &&
    first.crosshair_x === second.crosshair_x &&
    first.crosshair_y === second.crosshair_y &&
    first.crosshair_color === second.crosshair_color &&
    first.crosshair_thickness === second.crosshair_thickness &&
    first.crosshair_size === second.crosshair_size &&
    first.crosshair_gap === second.crosshair_gap &&
    first.widget_width === second.widget_width &&
    first.widget_height === second.widget_height &&
    first.focus_step === second.focus_step &&
    first.focus_enabled === second.focus_enabled
  );
};

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
  
  setSpotConfig: (spotConfig) => {
    set((state) => {
      if (state.spotConfig === null && spotConfig === null) {
        return state;
      }
      if (state.spotConfig !== null && spotConfig !== null && areSpotConfigsEqual(state.spotConfig, spotConfig)) {
        return state;
      }
      return { spotConfig };
    });
  },
  setSpotImageState: (
    spotImageUrl,
    spotImageLoading,
    spotImageError,
    spotLastSuccessAt,
    spotImageMetadata
  ) => set((state) => {
    const nextSpotLastSuccessAt = spotLastSuccessAt !== null ? spotLastSuccessAt : state.spotLastSuccessAt;
    const nextSpotImageMetadata = spotImageMetadata !== undefined ? spotImageMetadata : state.spotImageMetadata;
    if (
      state.spotImageUrl === spotImageUrl &&
      state.spotImageLoading === spotImageLoading &&
      state.spotImageError === spotImageError &&
      state.spotLastSuccessAt === nextSpotLastSuccessAt &&
      state.spotImageMetadata === nextSpotImageMetadata
    ) {
      return state;
    }
    return {
      ...state,
      spotImageUrl,
      spotImageLoading,
      spotImageError,
      spotLastSuccessAt: nextSpotLastSuccessAt,
      spotImageMetadata: nextSpotImageMetadata,
    };
  }),
  setSpotAlertActive: (spotAlertActive) => set({ spotAlertActive }),
}));
