import { FactoryData } from '../types';
import { TIME_SERIES_CATALOG, TimeSeriesKey } from './seriesCatalog';

export type SeriesSample = {
  timestampMs: number;
  values: Record<TimeSeriesKey, number | null>;
};

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

export const buildSeriesSample = (data: FactoryData, fallbackMs: number = Date.now()): SeriesSample => {
  const timestampMs = normalizeTimestamp(data.Time, fallbackMs);
  const values = {} as Record<TimeSeriesKey, number | null>;

  for (const meta of TIME_SERIES_CATALOG) {
    const raw = data[meta.key];
    values[meta.key] = typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
  }

  return { timestampMs, values };
};
