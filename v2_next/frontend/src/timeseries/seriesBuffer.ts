import { SeriesSample } from './seriesSampling';

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
    if (this.maxPoints && this.samples.length > this.maxPoints) {
      this.samples.splice(0, this.samples.length - this.maxPoints);
    }
  }

  append(sample: SeriesSample) {
    this.samples.push(sample);
    this.prune(sample.timestampMs);
    if (this.maxPoints && this.samples.length > this.maxPoints) {
      this.samples.splice(0, this.samples.length - this.maxPoints);
    }
  }

  getSamples() {
    return this.samples;
  }

  clear() {
    this.samples = [];
  }

  private prune(nowMs: number) {
    const cutoff = nowMs - this.windowMs;
    let index = 0;
    while (index < this.samples.length && this.samples[index].timestampMs < cutoff) {
      index += 1;
    }
    if (index > 0) {
      this.samples = this.samples.slice(index);
    }
  }
}
