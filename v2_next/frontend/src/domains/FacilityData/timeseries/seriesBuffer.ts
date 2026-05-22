import type { SeriesSample } from './seriesSampling';
import {
  areSeriesSamplesChronological,
  countTrimmedSeriesSamples,
  filterUniqueSeriesSamplesByTimestamp,
  getLatestSeriesSampleTimestampMs,
  sortSeriesSamplesByTimestamp,
} from './seriesBuffer.service';
import type { SeriesBufferSnapshot } from './seriesBuffer.types';

const buildBufferedSeriesSample = (sample: SeriesSample): SeriesSample =>
  Object.freeze({
    timestampMs: sample.timestampMs,
    values: Object.freeze({ ...sample.values }),
  }) as SeriesSample;

export class SeriesBuffer {
  private samples: SeriesSample[] = [];
  private windowMs: number;
  private maxPoints?: number;
  private firstSequence = 0;
  private nextSequence = 0;
  private generation = 0;
  private chronological = true;
  private lastTimestampMs: number | null = null;

  constructor(windowMs: number, maxPoints?: number) {
    this.windowMs = windowMs;
    this.maxPoints = maxPoints;
  }

  setWindowMs(windowMs: number): void {
    this.windowMs = windowMs;
    this.generation += 1;
    this.trimHead(Date.now());
  }

  setMaxPoints(maxPoints?: number): void {
    this.maxPoints = maxPoints;
    this.generation += 1;
    this.trimHead(Date.now());
  }

  append(sample: SeriesSample): void {
    const bufferedSample = buildBufferedSeriesSample(sample);
    if (this.samples.some((currentSample) => currentSample.timestampMs === bufferedSample.timestampMs)) {
      return;
    }
    if (this.lastTimestampMs !== null && bufferedSample.timestampMs < this.lastTimestampMs && this.chronological) {
      this.chronological = false;
      this.generation += 1;
    }
    this.samples.push(bufferedSample);
    this.nextSequence += 1;
    this.lastTimestampMs = bufferedSample.timestampMs;
    this.trimHead(bufferedSample.timestampMs);
  }

  appendHistory(samples: readonly SeriesSample[]): number {
    const uniqueSamples = filterUniqueSeriesSamplesByTimestamp(this.samples, samples);
    if (!uniqueSamples.length) {
      return 0;
    }

    const bufferedSamples = uniqueSamples.map(buildBufferedSeriesSample);
    const canAppendChronologically =
      areSeriesSamplesChronological(bufferedSamples) &&
      (this.lastTimestampMs === null || bufferedSamples[0].timestampMs >= this.lastTimestampMs);

    if (canAppendChronologically) {
      this.samples.push(...bufferedSamples);
      this.nextSequence += bufferedSamples.length;
      this.lastTimestampMs = bufferedSamples[bufferedSamples.length - 1].timestampMs;
      this.trimHead(this.lastTimestampMs);
      return bufferedSamples.length;
    }

    this.samples = sortSeriesSamplesByTimestamp([...this.samples, ...bufferedSamples]);
    this.nextSequence += bufferedSamples.length;
    this.generation += 1;
    this.chronological = true;
    this.lastTimestampMs = this.samples[this.samples.length - 1]?.timestampMs ?? null;
    this.trimHead(this.lastTimestampMs ?? Date.now());
    return bufferedSamples.length;
  }

  getLatestTimestampMs(): number | null {
    return getLatestSeriesSampleTimestampMs(this.samples);
  }

  getSamples(): SeriesSample[] {
    return this.samples.slice();
  }

  getSnapshot(): SeriesBufferSnapshot {
    return {
      samples: Object.freeze(this.samples.slice()),
      firstSequence: this.firstSequence,
      nextSequence: this.nextSequence,
      generation: this.generation,
      chronological: this.chronological,
    };
  }

  getStats(): { count: number; windowMs: number; maxPoints: number | null } {
    return {
      count: this.samples.length,
      windowMs: this.windowMs,
      maxPoints: this.maxPoints ?? null,
    };
  }

  clear(): void {
    this.samples = [];
    this.firstSequence = this.nextSequence;
    this.generation += 1;
    this.chronological = true;
    this.lastTimestampMs = null;
  }

  private trimHead(nowMs: number): void {
    const trimCount = countTrimmedSeriesSamples(this.samples, nowMs, this.windowMs, this.maxPoints);
    if (trimCount <= 0) {
      return;
    }

    this.samples.splice(0, trimCount);
    this.firstSequence += trimCount;
  }
}
