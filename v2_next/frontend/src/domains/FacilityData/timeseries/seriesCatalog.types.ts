import type { FactoryData } from '../../../shared/types';

export type TimeSeriesKey = Exclude<
  keyof FactoryData,
  | 'Time'
  | 'Status'
  | 'Computed'
  | 'Die_ID'
  | 'Billet_Cycle_ID'
  | 'timestamp_ms'
  | 'Product_No_operator'
  | 'Mold_No_operator'
  | 'operator_metadata_valid'
  | 'operator_metadata_missing_fields'
  | 'operator_metadata_updated_at'
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
