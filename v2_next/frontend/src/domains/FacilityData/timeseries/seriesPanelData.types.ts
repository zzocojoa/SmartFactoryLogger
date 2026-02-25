import type { PanelData, TimeRange } from '@grafana/data';
import type { MutableDataFrame } from '@grafana/data';
import type { SeriesSample } from './seriesSampling';

export interface PanelDataBuildParams {
  frame: MutableDataFrame;
  samples: SeriesSample[];
  windowMs: number;
}

export type PanelTimeRange = TimeRange;
export type PanelDataResult = PanelData;
