import type { ThresholdsConfig } from '@grafana/data';
import type { SeriesBufferSnapshot } from './seriesBuffer.types';
import type { SeriesAxisGroup } from './seriesCatalog';
import type { TimeSeriesKey, TimeSeriesMeta } from './seriesCatalog';

export type SeriesFieldType = 'time' | 'number';

export type SeriesFieldConfig = {
  displayName: string;
  unit?: string;
  thresholds?: ThresholdsConfig;
  custom: {
    axisId: string;
    axisLabel: string;
  };
};

export type SeriesFrameField = {
  name: string;
  type: SeriesFieldType;
  values: Array<number | null>;
  config?: SeriesFieldConfig;
};

export type SeriesFrame = {
  fields: SeriesFrameField[];
};

export type SeriesAxisIdMap = Record<SeriesAxisGroup, string>;
export type SeriesAxisLabelMap = Record<SeriesAxisGroup, string>;

export interface SeriesFrameSampleRange {
  startIndex: number;
  endIndex: number;
}

export interface IncrementalSeriesFrameCache {
  frame: SeriesFrame;
  firstSequence: number;
  nextSequence: number;
  generation: number;
  chronological: boolean;
  metas: readonly TimeSeriesMeta[];
}

export interface IncrementalSeriesFrameParams {
  snapshot: SeriesBufferSnapshot;
  range: SeriesFrameSampleRange;
  previousCache: IncrementalSeriesFrameCache | null;
  metas: readonly TimeSeriesMeta[];
  thresholdsByKey: Partial<Record<TimeSeriesKey, ThresholdsConfig>> | undefined;
}

export interface IncrementalSeriesFrameResult {
  frame: SeriesFrame;
  cache: IncrementalSeriesFrameCache;
}
