import type { SeriesSample } from '../timeseries/seriesSampling';

export const filterSeriesSamplesByWindow = (samples: SeriesSample[], seriesWindowMin: number): SeriesSample[] => {
  const cutoff = Date.now() - (seriesWindowMin * 60 * 1000);
  return samples.filter((sample) => sample.timestampMs >= cutoff);
};
