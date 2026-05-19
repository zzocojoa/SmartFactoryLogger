import { create } from 'zustand';
import type { DashboardLeaderState, FactoryData, SpotConfig, ThresholdState } from '../shared/types';
import type { SpotImageResponseMetadata } from '../domains/FacilityData/api/spotService.types';
import type { SeriesFrame } from '../domains/FacilityData/timeseries/seriesDataFrames';
import { buildThresholdStateFromConfig } from '../shared/utils/thresholds';

export interface DashboardKpiSlice {
  hasData: boolean;
  speed: number | null | undefined;
  press: number | null | undefined;
  count: number | null | undefined;
  endPos: number | null | undefined;
  computedSpeedLevel: string | undefined;
  computedPressLevel: string | undefined;
  computedJamLevel: string | undefined;
  computedSpeedThresholdHit: boolean | undefined;
  computedPressThresholdHit: boolean | undefined;
  computedCountThresholdHit: boolean | undefined;
  computedEndPosThresholdHit: boolean | undefined;
  missing: boolean;
  thresholdMasterOn: boolean;
  thresholdSpeedEnabled: boolean;
  thresholdSpeedValue: number | null;
  thresholdPressEnabled: boolean;
  thresholdPressValue: number | null;
  thresholdCountEnabled: boolean;
  thresholdCountValue: number | null;
  thresholdEndPosEnabled: boolean;
  thresholdEndPosValue: number | null;
}

export interface DashboardSpotSlice {
  dataReady: boolean;
  spotRaw: number | null | undefined;
  computedSpotLevel: string | undefined;
  computedSpotThresholdHit: boolean | undefined;
  missing: boolean;
  thresholdMasterOn: boolean;
  thresholdSpotEnabled: boolean;
  thresholdSpotValue: number | null;
  spotAlertActive: boolean;
}

export interface DashboardEnvSlice {
  tempRaw: number | null | undefined;
  humidityRaw: number | null | undefined;
  computedEnvTempLevel: string | undefined;
  computedEnvPreLevel: string | undefined;
  computedTempThresholdHit: boolean | undefined;
  computedHumidityThresholdHit: boolean | undefined;
  missing: boolean;
  thresholdMasterOn: boolean;
  thresholdAtTempEnabled: boolean;
  thresholdAtTempValue: number | null;
  thresholdAtPreEnabled: boolean;
  thresholdAtPreValue: number | null;
}

export interface DashboardTempsSlice {
  hasData: boolean;
  tempF: number | null | undefined;
  tempB: number | null | undefined;
  billetTemp: number | null | undefined;
  billetLength: number | null | undefined;
  computedTempFThresholdHit: boolean | undefined;
  computedTempBThresholdHit: boolean | undefined;
  computedBilletTempThresholdHit: boolean | undefined;
  computedBilletLengthThresholdHit: boolean | undefined;
  missing: boolean;
  thresholdMasterOn: boolean;
  thresholdTempFEnabled: boolean;
  thresholdTempFValue: number | null;
  thresholdTempBEnabled: boolean;
  thresholdTempBValue: number | null;
  thresholdBilletTempEnabled: boolean;
  thresholdBilletTempValue: number | null;
  thresholdBilletLengthEnabled: boolean;
  thresholdBilletLengthValue: number | null;
}

export interface DashboardMoldsSlice {
  hasData: boolean;
  moldValue1: number | null | undefined;
  moldValue2: number | null | undefined;
  moldValue3: number | null | undefined;
  moldValue4: number | null | undefined;
  moldValue5: number | null | undefined;
  moldValue6: number | null | undefined;
  computedMoldLevel1: string | undefined;
  computedMoldLevel2: string | undefined;
  computedMoldLevel3: string | undefined;
  computedMoldLevel4: string | undefined;
  computedMoldLevel5: string | undefined;
  computedMoldLevel6: string | undefined;
  missing: boolean;
}

interface DashboardTimeSeriesState {
  timeSeriesAllFrame: SeriesFrame | null;
  thresholds: ThresholdState;
  intervalSec: number;
}

interface DashboardSeriesStats {
  count: number;
  windowMs: number;
  maxPoints: number | null;
}

interface DashboardMetricsStatus {
  connected: boolean;
  latencyMs: number | null;
  pollingDegraded: boolean;
  pollingIntervalMs: number;
  pollingFailureCount: number;
  dashboardLeaderState: DashboardLeaderState | null;
  pollingPausedByVisibility: boolean;
  seriesStats: DashboardSeriesStats;
}

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
    first.actuator_step === second.actuator_step &&
    first.focus_enabled === second.focus_enabled
  );
};

const areDashboardLeaderStatesEqual = (
  first: DashboardLeaderState | null,
  second: DashboardLeaderState | null
): boolean => {
  if (first === null || second === null) {
    return first === second;
  }
  return (
    first.tab_id === second.tab_id &&
    first.mode === second.mode &&
    first.leader_tab_id === second.leader_tab_id &&
    first.last_broadcast_at === second.last_broadcast_at
  );
};

const areSeriesStatsEqual = (first: DashboardSeriesStats, second: DashboardSeriesStats): boolean => {
  return (
    first.count === second.count &&
    first.windowMs === second.windowMs &&
    first.maxPoints === second.maxPoints
  );
};

const hasMetricsStatusChanged = (
  state: DashboardMetricsStatus,
  status: Partial<DashboardMetricsStatus>
): boolean => {
  if (status.connected !== undefined && state.connected !== status.connected) {
    return true;
  }
  if (status.latencyMs !== undefined && state.latencyMs !== status.latencyMs) {
    return true;
  }
  if (status.pollingDegraded !== undefined && state.pollingDegraded !== status.pollingDegraded) {
    return true;
  }
  if (status.pollingIntervalMs !== undefined && state.pollingIntervalMs !== status.pollingIntervalMs) {
    return true;
  }
  if (status.pollingFailureCount !== undefined && state.pollingFailureCount !== status.pollingFailureCount) {
    return true;
  }
  if (
    status.dashboardLeaderState !== undefined &&
    !areDashboardLeaderStatesEqual(state.dashboardLeaderState, status.dashboardLeaderState)
  ) {
    return true;
  }
  if (
    status.pollingPausedByVisibility !== undefined &&
    state.pollingPausedByVisibility !== status.pollingPausedByVisibility
  ) {
    return true;
  }
  if (status.seriesStats !== undefined && !areSeriesStatsEqual(state.seriesStats, status.seriesStats)) {
    return true;
  }
  return false;
};

export interface DashboardState extends DashboardMetricsStatus {
  // 공장 데이터 상태
  data: FactoryData | null;
  timeSeriesAllFrame: SeriesFrame | null;
  thresholds: ThresholdState;
  lastDataAt: number | null;
  intervalSec: number;

  // SPOT 상태
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotImageError: string | null;
  spotLastSuccessAt: number | null;
  spotImageMetadata: SpotImageResponseMetadata | null;
  spotAlertActive: boolean;

  // 상태 갱신 함수
  setData: (data: FactoryData | null, lastDataAt: number | null) => void;
  setTimeSeriesFrame: (timeSeriesAllFrame: SeriesFrame | null) => void;
  setThresholds: (thresholds: ThresholdState) => void;
  setIntervalSec: (intervalSec: number) => void;
  setTimeSeriesState: (timeSeriesState: DashboardTimeSeriesState) => void;
  setMetricsStatus: (status: Partial<DashboardMetricsStatus>) => void;
  
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

export const selectDashboardKpiSlice = (state: DashboardState): DashboardKpiSlice => {
  const speed = state.data?.Speed;
  const press = state.data?.Press;
  return {
    hasData: state.data !== null,
    speed,
    press,
    count: state.data?.Count,
    endPos: state.data?.EndPos,
    computedSpeedLevel: state.data?.Computed?.speed_level,
    computedPressLevel: state.data?.Computed?.press_level,
    computedJamLevel: state.data?.Computed?.jam_level,
    computedSpeedThresholdHit: state.data?.Computed?.thresholds?.speed,
    computedPressThresholdHit: state.data?.Computed?.thresholds?.press,
    computedCountThresholdHit: state.data?.Computed?.thresholds?.count,
    computedEndPosThresholdHit: state.data?.Computed?.thresholds?.endpos,
    missing: !Number.isFinite(speed) || !Number.isFinite(press),
    thresholdMasterOn: state.thresholds.masterOn,
    thresholdSpeedEnabled: state.thresholds.entries.speed.enabled,
    thresholdSpeedValue: state.thresholds.entries.speed.value,
    thresholdPressEnabled: state.thresholds.entries.press.enabled,
    thresholdPressValue: state.thresholds.entries.press.value,
    thresholdCountEnabled: state.thresholds.entries.count.enabled,
    thresholdCountValue: state.thresholds.entries.count.value,
    thresholdEndPosEnabled: state.thresholds.entries.endpos.enabled,
    thresholdEndPosValue: state.thresholds.entries.endpos.value,
  };
};

export const selectDashboardSpotSlice = (state: DashboardState): DashboardSpotSlice => {
  const spotRaw = state.data?.Spot;
  return {
    dataReady: state.data !== null,
    spotRaw,
    computedSpotLevel: state.data?.Computed?.spot_level,
    computedSpotThresholdHit: state.data?.Computed?.thresholds?.spot,
    missing: !Number.isFinite(spotRaw),
    thresholdMasterOn: state.thresholds.masterOn,
    thresholdSpotEnabled: state.thresholds.entries.spot.enabled,
    thresholdSpotValue: state.thresholds.entries.spot.value,
    spotAlertActive: state.spotAlertActive,
  };
};

export const selectDashboardEnvSlice = (state: DashboardState): DashboardEnvSlice => {
  const tempRaw = state.data?.At_Temp;
  const humidityRaw = state.data?.At_Pre;
  return {
    tempRaw,
    humidityRaw,
    computedEnvTempLevel: state.data?.Computed?.env_temp_level,
    computedEnvPreLevel: state.data?.Computed?.env_pre_level,
    computedTempThresholdHit: state.data?.Computed?.thresholds?.at_temp,
    computedHumidityThresholdHit: state.data?.Computed?.thresholds?.at_pre,
    missing: !Number.isFinite(tempRaw) || !Number.isFinite(humidityRaw),
    thresholdMasterOn: state.thresholds.masterOn,
    thresholdAtTempEnabled: state.thresholds.entries.at_temp.enabled,
    thresholdAtTempValue: state.thresholds.entries.at_temp.value,
    thresholdAtPreEnabled: state.thresholds.entries.at_pre.enabled,
    thresholdAtPreValue: state.thresholds.entries.at_pre.value,
  };
};

export const selectDashboardTempsSlice = (state: DashboardState): DashboardTempsSlice => {
  const tempF = state.data?.Temp_F;
  const tempB = state.data?.Temp_B;
  const billetTemp = state.data?.Billet_Temp;
  const billetLength = state.data?.Billet_Length;
  return {
    hasData: state.data !== null,
    tempF,
    tempB,
    billetTemp,
    billetLength,
    computedTempFThresholdHit: state.data?.Computed?.thresholds?.temp_f,
    computedTempBThresholdHit: state.data?.Computed?.thresholds?.temp_b,
    computedBilletTempThresholdHit: state.data?.Computed?.thresholds?.billet_temp,
    computedBilletLengthThresholdHit: state.data?.Computed?.thresholds?.billet,
    missing:
      !Number.isFinite(tempF) ||
      !Number.isFinite(tempB) ||
      !Number.isFinite(billetTemp) ||
      !Number.isFinite(billetLength),
    thresholdMasterOn: state.thresholds.masterOn,
    thresholdTempFEnabled: state.thresholds.entries.temp_f.enabled,
    thresholdTempFValue: state.thresholds.entries.temp_f.value,
    thresholdTempBEnabled: state.thresholds.entries.temp_b.enabled,
    thresholdTempBValue: state.thresholds.entries.temp_b.value,
    thresholdBilletTempEnabled: state.thresholds.entries.billet_temp.enabled,
    thresholdBilletTempValue: state.thresholds.entries.billet_temp.value,
    thresholdBilletLengthEnabled: state.thresholds.entries.billet.enabled,
    thresholdBilletLengthValue: state.thresholds.entries.billet.value,
  };
};

export const selectDashboardMoldsSlice = (state: DashboardState): DashboardMoldsSlice => {
  const moldValue1 = state.data?.Mold1;
  const moldValue2 = state.data?.Mold2;
  const moldValue3 = state.data?.Mold3;
  const moldValue4 = state.data?.Mold4;
  const moldValue5 = state.data?.Mold5;
  const moldValue6 = state.data?.Mold6;
  return {
    hasData: state.data !== null,
    moldValue1,
    moldValue2,
    moldValue3,
    moldValue4,
    moldValue5,
    moldValue6,
    computedMoldLevel1: state.data?.Computed?.mold_levels?.Mold1,
    computedMoldLevel2: state.data?.Computed?.mold_levels?.Mold2,
    computedMoldLevel3: state.data?.Computed?.mold_levels?.Mold3,
    computedMoldLevel4: state.data?.Computed?.mold_levels?.Mold4,
    computedMoldLevel5: state.data?.Computed?.mold_levels?.Mold5,
    computedMoldLevel6: state.data?.Computed?.mold_levels?.Mold6,
    missing:
      !Number.isFinite(moldValue1) ||
      !Number.isFinite(moldValue2) ||
      !Number.isFinite(moldValue3) ||
      !Number.isFinite(moldValue4) ||
      !Number.isFinite(moldValue5) ||
      !Number.isFinite(moldValue6),
  };
};

export const selectLastDataAtSecond = (state: DashboardState): number | null => {
  if (state.lastDataAt === null) {
    return null;
  }
  return Math.floor(state.lastDataAt / 1000);
};

export const useDashboardStore = create<DashboardState>((set) => ({
  data: null,
  timeSeriesAllFrame: null,
  thresholds: buildThresholdStateFromConfig(),
  lastDataAt: null,
  intervalSec: 0.2,

  connected: false,
  latencyMs: null,
  pollingDegraded: false,
  pollingIntervalMs: 500,
  pollingFailureCount: 0,
  dashboardLeaderState: null,
  pollingPausedByVisibility: false,
  seriesStats: { count: 0, windowMs: 0, maxPoints: null },

  spotConfig: null,
  spotImageUrl: '',
  spotImageLoading: false,
  spotImageError: null,
  spotLastSuccessAt: null,
  spotImageMetadata: null,
  spotAlertActive: false,

  setData: (data, lastDataAt) => set((state) => {
    if (state.data === data && state.lastDataAt === lastDataAt) {
      return state;
    }
    return { data, lastDataAt };
  }),
  setTimeSeriesFrame: (timeSeriesAllFrame) => set((state) => {
    if (state.timeSeriesAllFrame === timeSeriesAllFrame) {
      return state;
    }
    return { timeSeriesAllFrame };
  }),
  setThresholds: (thresholds) => set((state) => {
    if (state.thresholds === thresholds) {
      return state;
    }
    return { thresholds };
  }),
  setIntervalSec: (intervalSec) => set((state) => {
    if (state.intervalSec === intervalSec) {
      return state;
    }
    return { intervalSec };
  }),
  setTimeSeriesState: (timeSeriesState) => set((state) => {
    if (
      state.timeSeriesAllFrame === timeSeriesState.timeSeriesAllFrame &&
      state.thresholds === timeSeriesState.thresholds &&
      state.intervalSec === timeSeriesState.intervalSec
    ) {
      return state;
    }
    return {
      timeSeriesAllFrame: timeSeriesState.timeSeriesAllFrame,
      thresholds: timeSeriesState.thresholds,
      intervalSec: timeSeriesState.intervalSec,
    };
  }),
  setMetricsStatus: (status) => set((state) => {
    if (!hasMetricsStatusChanged(state, status)) {
      return state;
    }
    return status;
  }),
  
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
  setSpotAlertActive: (spotAlertActive) => set((state) => {
    if (state.spotAlertActive === spotAlertActive) {
      return state;
    }
    return { spotAlertActive };
  }),
}));
