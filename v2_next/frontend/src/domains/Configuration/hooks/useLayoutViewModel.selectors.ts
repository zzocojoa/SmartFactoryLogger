import type { DashboardItem } from '../../../scenes/DashboardSceneModel';
import { normalizeDashboardItemTitle } from '../../../scenes/DashboardSceneModel';
import type { LayoutEntry } from '../../../shared/types';

export const resolveDefaultWidgetSpec = (
  type: string,
  defaultItems: DashboardItem[]
): Pick<LayoutEntry, 'title' | 'width' | 'height'> => {
  const defaultItem = defaultItems.find((item) => item.key === type);
  const rawTitle = defaultItem?.title ?? (type === 'markdown' ? 'OPERATOR CHECK' : 'Widget');
  const title = normalizeDashboardItemTitle(rawTitle, type as DashboardItem['type']);
  const width = defaultItem?.width ?? 20;
  const height = defaultItem?.height ?? 6;
  return { title, width, height };
};
