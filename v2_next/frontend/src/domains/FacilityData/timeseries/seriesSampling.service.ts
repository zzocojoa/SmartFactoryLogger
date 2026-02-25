import type { FactoryData } from '../../../shared/types';
import type { SeriesSample } from './seriesSampling.types';
import { buildSeriesSample as buildSeriesSampleMath } from './seriesSampling.math';

export const buildSeriesSample = (data: FactoryData, fallbackMs: number = Date.now()): SeriesSample =>
  buildSeriesSampleMath(data, fallbackMs);
