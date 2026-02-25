import type { SeriesSample } from './seriesSampling';

export interface SeriesBufferState {
  samples: SeriesSample[];
  windowMs: number;
  maxPoints?: number;
}
