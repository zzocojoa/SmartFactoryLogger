import { dateTime, LoadingState, PanelData, TimeRange } from '@grafana/data';
import { MutableDataFrame } from '@grafana/data';
import { SeriesSample } from './seriesSampling';

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

export const buildPanelData = (
  frame: MutableDataFrame,
  samples: SeriesSample[],
  windowMs: number
): PanelData => {
  const timeRange = buildTimeRangeFromSamples(samples, windowMs);
  return {
    state: LoadingState.Done,
    series: [frame],
    timeRange,
  };
};
