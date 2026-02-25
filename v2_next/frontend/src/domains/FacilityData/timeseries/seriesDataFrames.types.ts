import type { MutableDataFrame } from '@grafana/data';
import type { SeriesAxisGroup } from './seriesCatalog';

export type SeriesFrame = MutableDataFrame;

export type SeriesAxisIdMap = Record<SeriesAxisGroup, string>;
export type SeriesAxisLabelMap = Record<SeriesAxisGroup, string>;
