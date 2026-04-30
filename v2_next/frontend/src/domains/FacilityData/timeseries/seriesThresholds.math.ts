import type { ThresholdsConfig } from '@grafana/data';
import type { TimeSeriesKey } from './seriesCatalog';
import type { ThresholdKey } from './seriesThresholds.types';

const ABSOLUTE_THRESHOLD_MODE = 'absolute' as ThresholdsConfig['mode'];

export const THRESHOLD_KEY_MAP: Record<ThresholdKey, TimeSeriesKey> = {
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

export const buildThresholdConfig = (value: number): ThresholdsConfig => ({
  mode: ABSOLUTE_THRESHOLD_MODE,
  steps: [
    { value: Number.NEGATIVE_INFINITY, color: 'green' },
    { value, color: 'red' },
  ],
});
