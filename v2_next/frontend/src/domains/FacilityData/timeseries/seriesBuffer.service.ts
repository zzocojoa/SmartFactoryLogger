import type { SeriesSample } from './seriesSampling';

export const countPrunedSeriesSamples = (samples: readonly SeriesSample[], nowMs: number, windowMs: number): number => {
  const cutoff = nowMs - windowMs;
  let index = 0;
  while (index < samples.length && samples[index].timestampMs < cutoff) {
    index += 1;
  }
  return index;
};

export const countCappedSeriesSamples = (sampleCount: number, maxPoints: number | undefined): number => {
  if (!maxPoints || sampleCount <= maxPoints) {
    return 0;
  }
  return sampleCount - maxPoints;
};

export const countTrimmedSeriesSamples = (
  samples: readonly SeriesSample[],
  nowMs: number,
  windowMs: number,
  maxPoints: number | undefined,
): number => {
  const prunedCount = countPrunedSeriesSamples(samples, nowMs, windowMs);
  const remainingCount = samples.length - prunedCount;
  return prunedCount + countCappedSeriesSamples(remainingCount, maxPoints);
};

export const pruneSeriesSamples = (samples: SeriesSample[], nowMs: number, windowMs: number): SeriesSample[] => {
  const index = countPrunedSeriesSamples(samples, nowMs, windowMs);
  return index > 0 ? samples.slice(index) : samples;
};

export const capSeriesSamples = (samples: SeriesSample[], maxPoints?: number): SeriesSample[] => {
  if (!maxPoints || samples.length <= maxPoints) {
    return samples;
  }
  return samples.slice(samples.length - maxPoints);
};

export const trimSeriesSamples = (
  samples: SeriesSample[],
  nowMs: number,
  windowMs: number,
  maxPoints: number | undefined,
): SeriesSample[] => {
  const prunedSamples = pruneSeriesSamples(samples, nowMs, windowMs);
  return capSeriesSamples(prunedSamples, maxPoints);
};
