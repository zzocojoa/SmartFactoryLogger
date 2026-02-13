import type { SeriesAxisGroup, TimeSeriesMeta } from './seriesCatalog.types';

export const groupCatalogByAxis = (catalog: TimeSeriesMeta[]): Record<SeriesAxisGroup, TimeSeriesMeta[]> => {
  return catalog.reduce(
    (acc, meta) => {
      acc[meta.axis].push(meta);
      return acc;
    },
    {
      process: [] as TimeSeriesMeta[],
      temperature: [] as TimeSeriesMeta[],
      environment: [] as TimeSeriesMeta[],
    }
  );
};

export const filterVisibleCatalog = (catalog: TimeSeriesMeta[]): TimeSeriesMeta[] =>
  catalog.filter((meta) => meta.visibleByDefault);
