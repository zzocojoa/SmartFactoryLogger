/**
 * FactoryDataContext: 공장 핵심 데이터 및 시계열 프레임 정보를 제공하는 Context
 */
import React from 'react';
import type { FactoryData, ThresholdState } from '../../../shared/types';
import type { SeriesFrame } from '../timeseries/seriesDataFrames';
import { buildThresholdStateFromConfig } from '../../../shared/utils/thresholds';

export type FactoryDataContextValue = {
  data: FactoryData | null;
  thresholds: ThresholdState;
  lastDataAt: number | null;
  nowTick: number;
  intervalSec: number;
  timeSeriesFrames: Record<string, SeriesFrame> | null;
  timeSeriesAllFrame: SeriesFrame | null;
};

export const FactoryDataContext = React.createContext<FactoryDataContextValue>({
  data: null,
  thresholds: buildThresholdStateFromConfig(),
  lastDataAt: null,
  nowTick: Date.now(),
  intervalSec: 0.2,
  timeSeriesFrames: null,
  timeSeriesAllFrame: null,
});
