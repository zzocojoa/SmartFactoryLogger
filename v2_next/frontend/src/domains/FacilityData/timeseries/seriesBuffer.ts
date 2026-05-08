import type { SeriesSample } from './seriesSampling';
import { countTrimmedSeriesSamples } from './seriesBuffer.service';
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
    if (this.lastTimestampMs !== null && bufferedSample.timestampMs < this.lastTimestampMs && this.chronological) {
      this.chronological = false;
      this.generation += 1;
    }
    this.samples.push(bufferedSample);
    this.nextSequence += 1;
    this.lastTimestampMs = bufferedSample.timestampMs;
    this.trimHead(bufferedSample.timestampMs);
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
