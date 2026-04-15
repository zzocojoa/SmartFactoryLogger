import { SeriesSample } from './seriesSampling';
import { trimSeriesSamples } from './seriesBuffer.service';

export class SeriesBuffer {
  private samples: SeriesSample[] = [];
  private windowMs: number;
  private maxPoints?: number;

  constructor(windowMs: number, maxPoints?: number) {
    this.windowMs = windowMs;
    this.maxPoints = maxPoints;
  }

  setWindowMs(windowMs: number) {
    this.windowMs = windowMs;
    this.samples = trimSeriesSamples(this.samples, Date.now(), this.windowMs, this.maxPoints);
  }

  setMaxPoints(maxPoints?: number) {
    this.maxPoints = maxPoints;
    this.samples = trimSeriesSamples(this.samples, Date.now(), this.windowMs, this.maxPoints);
  }

  append(sample: SeriesSample) {
    this.samples = trimSeriesSamples(
      [...this.samples, sample],
      sample.timestampMs,
      this.windowMs,
      this.maxPoints,
    );
  }

  getSamples() {
    return this.samples;
  }

  getStats() {
    return {
      count: this.samples.length,
      windowMs: this.windowMs,
      maxPoints: this.maxPoints ?? null,
    };
  }

  clear() {
    this.samples = [];
  }
}
