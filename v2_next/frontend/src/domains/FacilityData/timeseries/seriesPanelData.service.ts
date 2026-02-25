import { LoadingState, PanelData } from '@grafana/data';
import { MutableDataFrame } from '@grafana/data';
import { buildTimeRangeFromSamples } from './seriesPanelData.math';
import type { SeriesSample } from './seriesSampling.types';

export const buildPanelData = (
  frame: MutableDataFrame,
  samples: SeriesSample[],
  windowMs: number
): PanelData => {
  const timeRange = buildTimeRangeFromSamples(samples, windowMs);
  return {
    state: LoadingState.Done,
    series: [frame],
    timeRange,
  };
};
