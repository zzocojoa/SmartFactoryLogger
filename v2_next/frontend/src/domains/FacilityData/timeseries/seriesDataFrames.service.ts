import type { ThresholdsConfig } from '@grafana/data';
import type { MutableDataFrame } from '@grafana/data';
import { TIME_SERIES_CATALOG } from './seriesCatalog';
import type { TimeSeriesKey, TimeSeriesMeta } from './seriesCatalog';
import { buildGroupedFrames as buildGroupedFramesMath, buildTimeSeriesFrame as buildTimeSeriesFrameMath } from './seriesDataFrames.math';
import type { SeriesSample } from './seriesSampling.types';

export const buildTimeSeriesFrame = (
  samples: SeriesSample[],
  metas: TimeSeriesMeta[] = TIME_SERIES_CATALOG,
  thresholdsByKey?: Partial<Record<TimeSeriesKey, ThresholdsConfig>>
): MutableDataFrame => buildTimeSeriesFrameMath(samples, metas, thresholdsByKey);

export const buildGroupedFrames = (
  samples: SeriesSample[],
  metas: TimeSeriesMeta[] = TIME_SERIES_CATALOG,
  thresholdsByKey?: Partial<Record<TimeSeriesKey, ThresholdsConfig>>
): Record<string, MutableDataFrame> => buildGroupedFramesMath(samples, metas, thresholdsByKey);
