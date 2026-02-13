import type { ThresholdsConfig } from '@grafana/data';
import type { TimeSeriesKey } from './seriesCatalog';
import { THRESHOLD_KEY_MAP, buildThresholdConfig } from './seriesThresholds.math';
import type {
  ThresholdBySeriesKey,
  ThresholdKey,
  ThresholdStateLike,
} from './seriesThresholds.types';

export const buildSeriesThresholds = (
  thresholds: ThresholdStateLike
): Partial<Record<TimeSeriesKey, ThresholdsConfig>> => {
  if (!thresholds.masterOn) {
    return {};
  }

  const result: ThresholdBySeriesKey = {};
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
