import { dateTime, TimeRange } from '@grafana/data';
import type { SeriesSample } from './seriesSampling';

export const buildTimeRangeFromSamples = (samples: SeriesSample[], windowMs: number): TimeRange => {
  const nowMs = Date.now();
  const lastMs = samples.length ? samples[samples.length - 1].timestampMs : nowMs;
  const firstMs = samples.length ? samples[0].timestampMs : Math.max(0, lastMs - windowMs);
  const from = dateTime(firstMs);
  const to = dateTime(lastMs);
  return {
    from,
    to,
    raw: { from, to },
  };
};
