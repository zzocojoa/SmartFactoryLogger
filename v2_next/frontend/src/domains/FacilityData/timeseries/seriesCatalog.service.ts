import { TIME_SERIES_CATALOG } from './seriesCatalog';
import { filterVisibleCatalog, groupCatalogByAxis } from './seriesCatalog.math';

export const getSeriesCatalog = () => TIME_SERIES_CATALOG;

export const getVisibleSeriesCatalog = () => filterVisibleCatalog(TIME_SERIES_CATALOG);

export const getCatalogByAxis = () => groupCatalogByAxis(TIME_SERIES_CATALOG);
