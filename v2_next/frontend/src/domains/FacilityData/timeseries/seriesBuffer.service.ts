import type { SeriesSample } from './seriesSampling';

const compareSeriesSampleTimestamp = (first: SeriesSample, second: SeriesSample): number =>
  first.timestampMs - second.timestampMs;

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

export const getLatestSeriesSampleTimestampMs = (samples: readonly SeriesSample[]): number | null => {
  if (!samples.length) {
    return null;
  }
  return samples.reduce<number>((latestTimestampMs, sample) => Math.max(latestTimestampMs, sample.timestampMs), samples[0].timestampMs);
};

export const filterUniqueSeriesSamplesByTimestamp = (
  currentSamples: readonly SeriesSample[],
  incomingSamples: readonly SeriesSample[],
): SeriesSample[] => {
  const knownTimestamps = new Set<number>(currentSamples.map((sample) => sample.timestampMs));
  const uniqueSamples: SeriesSample[] = [];

  for (const sample of incomingSamples) {
    if (knownTimestamps.has(sample.timestampMs)) {
      continue;
    }
    knownTimestamps.add(sample.timestampMs);
    uniqueSamples.push(sample);
  }

  return uniqueSamples;
};

export const areSeriesSamplesChronological = (samples: readonly SeriesSample[]): boolean => {
  for (let index = 1; index < samples.length; index += 1) {
    if (samples[index].timestampMs < samples[index - 1].timestampMs) {
      return false;
    }
  }
  return true;
};

export const sortSeriesSamplesByTimestamp = (samples: readonly SeriesSample[]): SeriesSample[] =>
  [...samples].sort(compareSeriesSampleTimestamp);
