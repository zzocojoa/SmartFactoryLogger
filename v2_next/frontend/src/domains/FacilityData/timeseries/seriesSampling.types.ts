import type { TimeSeriesKey } from './seriesCatalog';

export type SeriesSample = {
  timestampMs: number;
  values: Record<TimeSeriesKey, number | null>;
};
