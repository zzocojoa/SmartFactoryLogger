import { SeriesSample } from './seriesSampling';
import { capSeriesSamples, pruneSeriesSamples } from './seriesBuffer.service';

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
    this.prune(Date.now());
  }

  setMaxPoints(maxPoints?: number) {
    this.maxPoints = maxPoints;
    this.samples = capSeriesSamples(this.samples, this.maxPoints);
  }

  append(sample: SeriesSample) {
    this.samples.push(sample);
    this.prune(sample.timestampMs);
    this.samples = capSeriesSamples(this.samples, this.maxPoints);
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

  private prune(nowMs: number) {
    this.samples = pruneSeriesSamples(this.samples, nowMs, this.windowMs);
  }
}
