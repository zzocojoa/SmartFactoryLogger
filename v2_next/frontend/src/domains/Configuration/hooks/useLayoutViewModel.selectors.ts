import type { DashboardItem } from '../../../scenes/DashboardScene';
import type { LayoutEntry } from '../../../shared/types';

export const resolveDefaultWidgetSpec = (
  type: string,
  defaultItems: DashboardItem[]
): Pick<LayoutEntry, 'title' | 'width' | 'height'> => {
  const defaultItem = defaultItems.find((item) => item.key === type);
  const title = defaultItem?.title ?? (type === 'markdown' ? 'New Memo' : '???꾩젽');
  const width = defaultItem?.width ?? 20;
  const height = defaultItem?.height ?? 6;
  return { title, width, height };
};
