import { ThresholdsConfig, ThresholdsMode } from '@grafana/data';
import { TimeSeriesKey } from './seriesCatalog';

type ThresholdKey =
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

type ThresholdEntry = {
  enabled: boolean;
  value: number | null;
};

type ThresholdStateLike = {
  masterOn: boolean;
  entries: Record<ThresholdKey, ThresholdEntry>;
};

const THRESHOLD_KEY_MAP: Record<ThresholdKey, TimeSeriesKey> = {
  speed: 'Speed',
  press: 'Press',
  spot: 'Spot',
  temp_f: 'Temp_F',
  temp_b: 'Temp_B',
  billet: 'Billet_Length',
  billet_temp: 'Billet_Temp',
  at_temp: 'At_Temp',
  at_pre: 'At_Pre',
  count: 'Count',
  endpos: 'EndPos',
};

const buildThresholdConfig = (value: number): ThresholdsConfig => ({
  mode: ThresholdsMode.Absolute,
  steps: [
    { value: Number.NEGATIVE_INFINITY, color: 'green' },
    { value, color: 'red' },
  ],
});

export const buildSeriesThresholds = (
  thresholds: ThresholdStateLike
): Partial<Record<TimeSeriesKey, ThresholdsConfig>> => {
  if (!thresholds.masterOn) {
    return {};
  }
  const result: Partial<Record<TimeSeriesKey, ThresholdsConfig>> = {};
  (Object.keys(THRESHOLD_KEY_MAP) as ThresholdKey[]).forEach((key) => {
    const entry = thresholds.entries[key];
    if (!entry?.enabled) {
      return;
    }
    const value = entry.value;
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      return;
    }
    const seriesKey = THRESHOLD_KEY_MAP[key];
    result[seriesKey] = buildThresholdConfig(value);
  });
  return result;
};
