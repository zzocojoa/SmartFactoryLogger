import type { ThresholdsConfig } from '@grafana/data';
import { TIME_SERIES_CATALOG } from './seriesCatalog';
import type { TimeSeriesKey, TimeSeriesMeta } from './seriesCatalog';
import {
  appendTimeSeriesFrameSamples,
  applyTimeSeriesFrameConfig,
  buildGroupedFrames as buildGroupedFramesMath,
  buildTimeSeriesFrame as buildTimeSeriesFrameMath,
  buildTimeSeriesFrameFromRange,
  trimTimeSeriesFrameHead,
} from './seriesDataFrames.math';
import type { SeriesSample } from './seriesSampling.types';
import type {
  IncrementalSeriesFrameCache,
  IncrementalSeriesFrameParams,
  IncrementalSeriesFrameResult,
  SeriesFrame,
} from './seriesDataFrames.types';

export const buildTimeSeriesFrame = (
  samples: SeriesSample[],
  metas: TimeSeriesMeta[] = TIME_SERIES_CATALOG,
  thresholdsByKey?: Partial<Record<TimeSeriesKey, ThresholdsConfig>>
): SeriesFrame => buildTimeSeriesFrameMath(samples, metas, thresholdsByKey);

export const buildGroupedFrames = (
  samples: SeriesSample[],
  metas: TimeSeriesMeta[] = TIME_SERIES_CATALOG,
  thresholdsByKey?: Partial<Record<TimeSeriesKey, ThresholdsConfig>>
): Record<string, SeriesFrame> => buildGroupedFramesMath(samples, metas, thresholdsByKey);

const buildFullIncrementalFrame = (params: IncrementalSeriesFrameParams): IncrementalSeriesFrameResult => {
  const firstSequence = params.snapshot.firstSequence + params.range.startIndex;
  const nextSequence = params.snapshot.firstSequence + params.range.endIndex;
  const frame = buildTimeSeriesFrameFromRange(
    params.snapshot.samples,
    params.range.startIndex,
    params.range.endIndex,
    params.metas,
    params.thresholdsByKey,
  );
  return {
    frame,
    cache: {
      frame,
      firstSequence,
      nextSequence,
      generation: params.snapshot.generation,
      chronological: params.snapshot.chronological,
      metas: params.metas,
    },
  };
};

const cloneSeriesFrameWithSharedValues = (frame: SeriesFrame): SeriesFrame => ({
  fields: frame.fields.map((field) => ({ ...field })),
});

const shouldRebuildIncrementalFrame = (
  params: IncrementalSeriesFrameParams,
  firstSequence: number,
  nextSequence: number,
): boolean => {
  const previousCache = params.previousCache;
  if (!previousCache) {
    return true;
  }
  if (previousCache.generation !== params.snapshot.generation) {
    return true;
  }
  if (previousCache.chronological !== params.snapshot.chronological) {
    return true;
  }
  if (previousCache.metas !== params.metas) {
    return true;
  }
  if (firstSequence < previousCache.firstSequence) {
    return true;
  }
  if (nextSequence < previousCache.nextSequence) {
    return true;
  }
  if (previousCache.nextSequence < firstSequence) {
    return true;
  }
  return previousCache.nextSequence < params.snapshot.firstSequence;
};

export const buildIncrementalTimeSeriesFrame = (
  params: IncrementalSeriesFrameParams,
): IncrementalSeriesFrameResult => {
  const firstSequence = params.snapshot.firstSequence + params.range.startIndex;
  const nextSequence = params.snapshot.firstSequence + params.range.endIndex;
  if (shouldRebuildIncrementalFrame(params, firstSequence, nextSequence)) {
    return buildFullIncrementalFrame(params);
  }

  const previousCache = params.previousCache as IncrementalSeriesFrameCache;
  const trimCount = firstSequence - previousCache.firstSequence;
  const appendStartIndex = previousCache.nextSequence - params.snapshot.firstSequence;
  trimTimeSeriesFrameHead(previousCache.frame, trimCount);
  appendTimeSeriesFrameSamples(previousCache.frame, params.snapshot.samples, appendStartIndex, params.range.endIndex, params.metas);
  applyTimeSeriesFrameConfig(previousCache.frame, params.metas, params.thresholdsByKey);
  const frame = cloneSeriesFrameWithSharedValues(previousCache.frame);

  return {
    frame,
    cache: {
      frame,
      firstSequence,
      nextSequence,
      generation: params.snapshot.generation,
      chronological: params.snapshot.chronological,
      metas: params.metas,
    },
  };
};
