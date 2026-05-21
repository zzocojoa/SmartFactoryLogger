import type { FactoryData } from '../../../shared/types';
import type { SeriesSample } from './seriesSampling.types';
import {
  buildSeriesSample as buildSeriesSampleMath,
  buildSeriesSampleAt as buildSeriesSampleAtMath,
} from './seriesSampling.math';

export const buildSeriesSample = (data: FactoryData, fallbackMs: number = Date.now()): SeriesSample =>
  buildSeriesSampleMath(data, fallbackMs);

export const buildSeriesSampleAt = (data: FactoryData, timestampMs: number): SeriesSample =>
  buildSeriesSampleAtMath(data, timestampMs);
