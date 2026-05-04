/**
 * DataContext: 공장 데이터를 위젯 컴포넌트에 전달하는 Context
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React from 'react';
import type { FactoryData, SpotConfig, ThresholdState } from '../../../shared/types';
import type { SpotImageResponseMetadata } from '../api/spotService.types';
import type { SeriesFrame } from '../timeseries/seriesDataFrames';
import { buildThresholdStateFromConfig } from '../../../shared/utils/thresholds';

export type DataContextValue = {
  data: FactoryData | null;
  thresholds: ThresholdState;
  timeSeriesAllFrame: SeriesFrame | null;
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotImageError: string | null;
  spotLastSuccessAt: number | null;
  spotImageMetadata: SpotImageResponseMetadata | null;
  spotAlertActive: boolean;
  lastDataAt: number | null;
  onSpotImageLoaded: () => void;
  onSpotImageError: (message?: string) => void;
  requestFocus: (steps: number) => void;
  seriesWindowMin: number;
  seriesPaused: boolean;
  showThresholds: boolean;
  setSeriesWindowMin: (min: number) => void;
  setSeriesPaused: React.Dispatch<React.SetStateAction<boolean>>;
  setShowThresholds: (show: boolean) => void;
  handleSnapshot: () => void;
  snapshotLoading: boolean;
  layoutEditing: boolean;
  setLayoutEditing: (editing: boolean) => void;
  intervalSec: number;
};

export const DataContext = React.createContext<DataContextValue>({
  data: null,
  thresholds: buildThresholdStateFromConfig(),
  timeSeriesAllFrame: null,
  spotConfig: null,
  spotImageUrl: '',
  spotImageLoading: false,
  spotImageError: null,
  spotLastSuccessAt: null,
  spotImageMetadata: null,
  spotAlertActive: false,
  lastDataAt: null,
  onSpotImageLoaded: () => undefined,
  onSpotImageError: () => undefined,
  requestFocus: () => undefined,
  seriesWindowMin: 30,
  seriesPaused: false,
  showThresholds: true,
  setSeriesWindowMin: () => undefined,
  setSeriesPaused: () => undefined,
  setShowThresholds: () => undefined,
  handleSnapshot: () => undefined,
  snapshotLoading: false,
  layoutEditing: false,
  setLayoutEditing: () => { },
  intervalSec: 0.2,
});
