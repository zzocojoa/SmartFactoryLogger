import type { SeriesSample } from './seriesSampling';

export interface SeriesBufferState {
  samples: SeriesSample[];
  windowMs: number;
  maxPoints?: number;
}

export interface SeriesBufferSnapshot {
  samples: readonly SeriesSample[];
  firstSequence: number;
  nextSequence: number;
  generation: number;
  chronological: boolean;
}
