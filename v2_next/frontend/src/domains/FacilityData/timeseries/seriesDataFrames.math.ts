import type { ThresholdsConfig } from '@grafana/data';
import { TIME_SERIES_CATALOG } from './seriesCatalog';
import type {
  SeriesUnit,
  TimeSeriesKey,
  TimeSeriesMeta,
} from './seriesCatalog';
import type { SeriesSample } from './seriesSampling';
import type {
  SeriesAxisIdMap,
  SeriesAxisLabelMap,
  SeriesFrame,
  SeriesFieldConfig,
  SeriesFrameField,
} from './seriesDataFrames.types';

const TIME_FIELD_TYPE = 'time';
const NUMBER_FIELD_TYPE = 'number';

const UNIT_MAP: Partial<Record<SeriesUnit, string>> = {
  C: 'celsius',
  '%': 'percent',
  bar: 'pressurebar',
  mm: 'lengthmm',
  'mm/s': 'velocitymm/s',
  ea: 'short',
};

const resolveUnit = (unit: SeriesUnit): string | undefined => UNIT_MAP[unit];

export const SERIES_AXIS_ID_MAP: SeriesAxisIdMap = {
  process: 'process',
  temperature: 'temperature',
  environment: 'environment',
};

export const SERIES_AXIS_LABEL_MAP: SeriesAxisLabelMap = {
  process: '공정',
  temperature: '온도',
  environment: '환경',
};

export const buildSeriesFieldConfig = (
  meta: TimeSeriesMeta,
  thresholdsByKey: Partial<Record<TimeSeriesKey, ThresholdsConfig>> | undefined,
): SeriesFieldConfig => {
  const unit = resolveUnit(meta.unit);
  const thresholds = thresholdsByKey?.[meta.key];
  const config: SeriesFieldConfig = {
    displayName: meta.label,
    unit,
    custom: {
      axisId: SERIES_AXIS_ID_MAP[meta.axis],
      axisLabel: SERIES_AXIS_LABEL_MAP[meta.axis],
    },
  };
  if (thresholds) {
    config.thresholds = thresholds;
  }
  return config;
};

export const applyTimeSeriesFrameConfig = (
  frame: SeriesFrame,
  metas: readonly TimeSeriesMeta[],
  thresholdsByKey: Partial<Record<TimeSeriesKey, ThresholdsConfig>> | undefined,
): SeriesFrame => {
  for (let index = 0; index < metas.length; index += 1) {
    const field = frame.fields[index + 1];
    if (field) {
      field.config = buildSeriesFieldConfig(metas[index], thresholdsByKey);
    }
  }
  return frame;
};

export const appendTimeSeriesFrameSamples = (
  frame: SeriesFrame,
  samples: readonly SeriesSample[],
  startIndex: number,
  endIndex: number,
  metas: readonly TimeSeriesMeta[],
): SeriesFrame => {
  const timeValues = frame.fields[0].values;
  for (let sampleIndex = startIndex; sampleIndex < endIndex; sampleIndex += 1) {
    const sample = samples[sampleIndex];
    timeValues.push(sample.timestampMs);
    for (let metaIndex = 0; metaIndex < metas.length; metaIndex += 1) {
      frame.fields[metaIndex + 1].values.push(sample.values[metas[metaIndex].key] ?? null);
    }
  }
  return frame;
};

export const trimTimeSeriesFrameHead = (frame: SeriesFrame, trimCount: number): SeriesFrame => {
  if (trimCount <= 0) {
    return frame;
  }

  for (const field of frame.fields) {
    field.values.splice(0, trimCount);
  }
  return frame;
};

export const buildTimeSeriesFrameFromRange = (
  samples: readonly SeriesSample[],
  startIndex: number,
  endIndex: number,
  metas: readonly TimeSeriesMeta[],
  thresholdsByKey: Partial<Record<TimeSeriesKey, ThresholdsConfig>> | undefined,
): SeriesFrame => {
  const timeValues: Array<number | null> = [];
  const fields: SeriesFrameField[] = [
    {
      name: 'time',
      type: TIME_FIELD_TYPE,
      values: timeValues,
    },
  ];

  for (const meta of metas) {
    fields.push({
      name: meta.key,
      type: NUMBER_FIELD_TYPE,
      values: [],
      config: buildSeriesFieldConfig(meta, thresholdsByKey),
    });
  }

  const frame: SeriesFrame = { fields };
  return appendTimeSeriesFrameSamples(frame, samples, startIndex, endIndex, metas);
};

export const buildTimeSeriesFrame = (
  samples: SeriesSample[],
  metas: TimeSeriesMeta[] = TIME_SERIES_CATALOG,
  thresholdsByKey?: Partial<Record<TimeSeriesKey, ThresholdsConfig>>
): SeriesFrame => buildTimeSeriesFrameFromRange(samples, 0, samples.length, metas, thresholdsByKey);

export const buildGroupedFrames = (
  samples: SeriesSample[],
  metas: TimeSeriesMeta[] = TIME_SERIES_CATALOG,
  thresholdsByKey?: Partial<Record<TimeSeriesKey, ThresholdsConfig>>
): Record<string, SeriesFrame> => {
  const groups: Record<string, TimeSeriesMeta[]> = {};
  for (const meta of metas) {
    if (!groups[meta.group]) {
      groups[meta.group] = [];
    }
    groups[meta.group].push(meta);
  }

  const frames: Record<string, SeriesFrame> = {};
  for (const group of Object.keys(groups)) {
    frames[group] = buildTimeSeriesFrame(samples, groups[group], thresholdsByKey);
  }
  return frames;
};
