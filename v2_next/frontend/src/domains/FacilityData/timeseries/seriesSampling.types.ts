import type { TimeSeriesKey } from './seriesCatalog';

export type SeriesSample = {
  timestampMs: number;
  historyInstanceId?: string;
  historySequence?: number;
  values: Record<TimeSeriesKey, number | null>;
};
