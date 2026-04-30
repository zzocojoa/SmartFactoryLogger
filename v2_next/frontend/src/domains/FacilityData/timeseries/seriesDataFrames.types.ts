import type { ThresholdsConfig } from '@grafana/data';
import type { SeriesAxisGroup } from './seriesCatalog';

export type SeriesFieldType = 'time' | 'number';

export type SeriesFieldConfig = {
  displayName: string;
  unit?: string;
  thresholds?: ThresholdsConfig;
  custom: {
    axisId: string;
    axisLabel: string;
  };
};

export type SeriesFrameField = {
  name: string;
  type: SeriesFieldType;
  values: Array<number | null>;
  config?: SeriesFieldConfig;
};

export type SeriesFrame = {
  fields: SeriesFrameField[];
};

export type SeriesAxisIdMap = Record<SeriesAxisGroup, string>;
export type SeriesAxisLabelMap = Record<SeriesAxisGroup, string>;
