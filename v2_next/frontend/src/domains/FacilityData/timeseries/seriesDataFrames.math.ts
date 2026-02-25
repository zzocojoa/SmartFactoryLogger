import { FieldType, MutableDataFrame, ThresholdsConfig } from '@grafana/data';
import { TIME_SERIES_CATALOG } from './seriesCatalog';
import type {
  SeriesAxisGroup,
  SeriesUnit,
  TimeSeriesKey,
  TimeSeriesMeta,
} from './seriesCatalog';
import type { SeriesSample } from './seriesSampling';
import type { SeriesAxisIdMap, SeriesAxisLabelMap } from './seriesDataFrames.types';

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

export const buildTimeSeriesFrame = (
  samples: SeriesSample[],
  metas: TimeSeriesMeta[] = TIME_SERIES_CATALOG,
  thresholdsByKey?: Partial<Record<TimeSeriesKey, ThresholdsConfig>>
): MutableDataFrame => {
  const timeValues = samples.map((sample) => sample.timestampMs);
  const fields: any[] = [
    {
      name: 'time',
      type: FieldType.time,
      values: timeValues,
    },
  ];

  for (const meta of metas) {
    const values = samples.map((sample) => sample.values[meta.key] ?? null);
    const unit = resolveUnit(meta.unit);
    const thresholds = thresholdsByKey?.[meta.key];
    const config: {
      displayName: string;
      unit?: string;
      thresholds?: ThresholdsConfig;
      custom: {
        axisId: string;
        axisLabel: string;
      };
    } = {
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
    fields.push({
      name: meta.key,
      type: FieldType.number,
      values,
      config,
    });
  }

  return new MutableDataFrame({ fields });
};

export const buildGroupedFrames = (
  samples: SeriesSample[],
  metas: TimeSeriesMeta[] = TIME_SERIES_CATALOG,
  thresholdsByKey?: Partial<Record<TimeSeriesKey, ThresholdsConfig>>
): Record<string, MutableDataFrame> => {
  const groups: Record<string, TimeSeriesMeta[]> = {};
  for (const meta of metas) {
    if (!groups[meta.group]) {
      groups[meta.group] = [];
    }
    groups[meta.group].push(meta);
  }

  const frames: Record<string, MutableDataFrame> = {};
  for (const group of Object.keys(groups)) {
    frames[group] = buildTimeSeriesFrame(samples, groups[group], thresholdsByKey);
  }
  return frames;
};
