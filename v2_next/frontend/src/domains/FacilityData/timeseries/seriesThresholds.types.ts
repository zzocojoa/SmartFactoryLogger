import type { ThresholdsConfig } from '@grafana/data';
import type { TimeSeriesKey } from './seriesCatalog';

export type ThresholdKey =
  | 'speed'
  | 'press'
  | 'spot'
  | 'temp_f'
  | 'temp_b'
  | 'billet'
  | 'billet_temp'
  | 'at_temp'
  | 'at_pre'
  | 'count'
  | 'endpos';

export type ThresholdEntry = {
  enabled: boolean;
  value: number | null;
};

export type ThresholdStateLike = {
  masterOn: boolean;
  entries: Record<ThresholdKey, ThresholdEntry>;
};

export type ThresholdBySeriesKey = Partial<Record<TimeSeriesKey, ThresholdsConfig>>;
