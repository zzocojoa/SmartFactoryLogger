import type { FactoryData } from '../../../shared/types';

export type TimeSeriesKey = Exclude<
  keyof FactoryData,
  'Time' | 'Status' | 'Computed' | 'Die_ID' | 'Billet_Cycle_ID'
>;

export type SeriesSource = 'SPOT' | 'Extruder' | 'LS_PLC';
export type SeriesAxisGroup = 'process' | 'temperature' | 'environment';
export type SeriesUnit = 'C' | 'bar' | 'mm/s' | 'mm' | '%' | 'ea';

export type TimeSeriesMeta = {
  key: TimeSeriesKey;
  label: string;
  source: SeriesSource;
  axis: SeriesAxisGroup;
  group: SeriesAxisGroup;
  unit: SeriesUnit;
  visibleByDefault: boolean;
  decimals?: number;
  legacyKey?: string;
};
