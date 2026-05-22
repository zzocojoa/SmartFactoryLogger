import type { FactoryData } from '../../../shared/types';
import { TIME_SERIES_CATALOG } from './seriesCatalog';
import type { TimeSeriesKey } from './seriesCatalog';
import type { SeriesSample } from './seriesSampling.types';

export const normalizeTimestamp = (value?: string | null, fallbackMs: number = Date.now()): number => {
  if (!value) {
    return fallbackMs;
  }
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return fallbackMs;
  }
  return parsed;
};

const buildSeriesValues = (data: FactoryData): Record<TimeSeriesKey, number | null> => {
  const values = {} as Record<TimeSeriesKey, number | null>;

  for (const meta of TIME_SERIES_CATALOG) {
    const raw = data[meta.key];
    values[meta.key] = typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
  }

  return values;
};

export const buildSeriesSampleAt = (data: FactoryData, timestampMs: number): SeriesSample => {
  const values = buildSeriesValues(data);
  return { timestampMs, values };
};

export const buildSeriesSample = (data: FactoryData, fallbackMs: number = Date.now()): SeriesSample => {
  const timestampMs = normalizeTimestamp(data.Time, fallbackMs);
  return buildSeriesSampleAt(data, timestampMs);
};
