import type { SeriesSample } from './seriesSampling';

export const pruneSeriesSamples = (samples: SeriesSample[], nowMs: number, windowMs: number): SeriesSample[] => {
  const cutoff = nowMs - windowMs;
  let index = 0;
  while (index < samples.length && samples[index].timestampMs < cutoff) {
    index += 1;
  }
  return index > 0 ? samples.slice(index) : samples;
};

export const capSeriesSamples = (samples: SeriesSample[], maxPoints?: number): SeriesSample[] => {
  if (!maxPoints || samples.length <= maxPoints) {
    return samples;
  }
  return samples.slice(samples.length - maxPoints);
};
