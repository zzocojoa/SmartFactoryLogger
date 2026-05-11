import type { SeriesSample } from '../timeseries/seriesSampling';

export interface SeriesSamplesWindowRange {
  startIndex: number;
  endIndex: number;
  cutoffMs: number;
}

export const filterSeriesSamplesByWindow = (
  samples: readonly SeriesSample[],
  seriesWindowMin: number,
  nowMs: number,
): SeriesSample[] => {
  const cutoffMs = nowMs - (seriesWindowMin * 60 * 1000);
  return samples.filter((sample) => sample.timestampMs >= cutoffMs);
};

export const getSeriesSamplesWindowRange = (
  samples: readonly SeriesSample[],
  seriesWindowMin: number,
  nowMs: number,
): SeriesSamplesWindowRange => {
  const cutoffMs = nowMs - (seriesWindowMin * 60 * 1000);
  let startIndex = 0;
  while (startIndex < samples.length && samples[startIndex].timestampMs < cutoffMs) {
    startIndex += 1;
  }

  return {
    startIndex,
    endIndex: samples.length,
    cutoffMs,
  };
};
