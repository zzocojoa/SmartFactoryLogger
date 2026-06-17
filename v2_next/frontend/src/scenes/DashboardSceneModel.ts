export type WidgetType = 'kpi' | 'spot' | 'temps' | 'camera' | 'molds' | 'env' | 'operatorMetadata' | 'notice' | 'timeseries' | 'markdown';

export interface DashboardItem {
  key: string;
  type: WidgetType;
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
  properties?: Record<string, unknown>;
}

export type SavedLayoutItem = {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  type?: WidgetType;
  title?: string;
  properties?: Record<string, unknown>;
};

export type SavedLayoutMap = Record<string, SavedLayoutItem>;

export const DEFAULT_DASHBOARD_ITEMS: DashboardItem[] = [
  { key: 'kpi', type: 'kpi', title: '\uACF5\uC815 KPI', x: 0, y: 0, width: 15, height: 18 },
  { key: 'spot', type: 'spot', title: 'SPOT \uC628\uB3C4', x: 15, y: 0, width: 25, height: 4 },
  { key: 'temps', type: 'temps', title: '\uBCF4\uC870 \uC628\uB3C4', x: 15, y: 4, width: 25, height: 4 },
  { key: 'camera', type: 'camera', title: 'SPOT \uCE74\uBA54\uB77C', x: 15, y: 8, width: 25, height: 10 },
  { key: 'molds', type: 'molds', title: '\uBAB0\uB4DC \uC874', x: 40, y: 0, width: 20, height: 8 },
  { key: 'env', type: 'env', title: '\uD658\uACBD', x: 40, y: 8, width: 20, height: 4 },
  { key: 'operatorMetadata', type: 'operatorMetadata', title: '\uC791\uC5C5 \uC815\uBCF4', x: 40, y: 12, width: 20, height: 6 },
  { key: 'timeseries', type: 'timeseries', title: '\uD0C0\uC784 \uC2DC\uB9AC\uC988', x: 0, y: 18, width: 60, height: 8 },
];

export const DASHBOARD_LAYOUT_KEYS = [
  'kpi',
  'spot',
  'temps',
  'camera',
  'molds',
  'env',
  'timeseries',
  'operatorMetadata',
] as const;

const OPERATOR_CHECK_TITLE = 'OPERATOR CHECK';
const LEGACY_MEMO_TITLES = new Set<string>(['new memo']);
const REQUIRED_DASHBOARD_ITEM_KEYS = ['operatorMetadata'] as const;

export const normalizeDashboardItemTitle = (
  title: string,
  type: WidgetType
): string => {
  if (type === 'markdown' && LEGACY_MEMO_TITLES.has(title.trim().toLowerCase())) {
    return OPERATOR_CHECK_TITLE;
  }

  return title;
};

const resolveDashboardItemFromKey = (
  key: string,
  savedMap: SavedLayoutMap,
  defaultItemMap: Map<string, DashboardItem>
): DashboardItem | null => {
  const defaultItem = defaultItemMap.get(key);
  const saved = savedMap[key];

  if (!defaultItem && !saved) {
    return null;
  }

  const type: WidgetType = saved?.type ?? defaultItem?.type ?? 'markdown';
  const rawTitle: string = saved?.title ?? defaultItem?.title ?? 'Widget';
  const title: string = normalizeDashboardItemTitle(rawTitle, type);
  const properties: Record<string, unknown> = saved?.properties ?? defaultItem?.properties ?? {};
  const x: number = saved?.x ?? defaultItem?.x ?? 0;
  const y: number = saved?.y ?? defaultItem?.y ?? 0;
  const width: number = saved?.width ?? defaultItem?.width ?? 10;
  const height: number = saved?.height ?? defaultItem?.height ?? 4;

  return {
    key,
    type,
    title,
    x,
    y,
    width,
    height,
    properties,
  };
};

const rectanglesOverlap = (a: DashboardItem, b: DashboardItem): boolean => {
  const aRight = a.x + a.width;
  const bRight = b.x + b.width;
  const aBottom = a.y + a.height;
  const bBottom = b.y + b.height;
  return a.x < bRight && aRight > b.x && a.y < bBottom && aBottom > b.y;
};

const getLayoutBottom = (items: DashboardItem[]): number => {
  return items.reduce((bottom, item) => Math.max(bottom, item.y + item.height), 0);
};

const uniquifyRequiredItemKey = (key: string, items: DashboardItem[]): string => {
  if (!items.some(item => item.key === key)) {
    return key;
  }

  let suffix = 1;
  let nextKey = `${key}-required`;
  while (items.some(item => item.key === nextKey)) {
    suffix += 1;
    nextKey = `${key}-required-${suffix}`;
  }
  return nextKey;
};

const placeRequiredDashboardItem = (
  requiredItem: DashboardItem,
  items: DashboardItem[]
): DashboardItem => {
  const nextItem: DashboardItem = {
    ...requiredItem,
    key: uniquifyRequiredItemKey(requiredItem.key, items),
    properties: requiredItem.properties ?? {},
  };

  if (!items.some(item => rectanglesOverlap(item, nextItem))) {
    return nextItem;
  }

  return {
    ...nextItem,
    y: getLayoutBottom(items),
  };
};

export const ensureRequiredDashboardItems = (items: DashboardItem[]): DashboardItem[] => {
  const nextItems = [...items];
  const defaultItemMap: Map<string, DashboardItem> = new Map(DEFAULT_DASHBOARD_ITEMS.map(item => [item.key, item]));

  REQUIRED_DASHBOARD_ITEM_KEYS.forEach((key) => {
    const requiredItem = defaultItemMap.get(key);
    if (!requiredItem) {
      return;
    }

    if (nextItems.some(item => item.type === requiredItem.type)) {
      return;
    }

    nextItems.push(placeRequiredDashboardItem(requiredItem, nextItems));
  });

  return nextItems;
};

export const resolveDashboardItems = (savedLayout: SavedLayoutMap | null): DashboardItem[] => {
  const savedMap: SavedLayoutMap = savedLayout ?? {};
  const defaultItemMap: Map<string, DashboardItem> = new Map(DEFAULT_DASHBOARD_ITEMS.map(item => [item.key, item]));
  const keys: string[] = savedLayout
    ? Object.keys(savedMap).filter(key => key !== 'notice')
    : DEFAULT_DASHBOARD_ITEMS.reduce<string[]>((acc, item) => {
        if (item.key !== 'notice') {
          acc.push(item.key);
        }
        return acc;
      }, []);

  const items = keys.reduce<DashboardItem[]>((acc, key) => {
    const item = resolveDashboardItemFromKey(key, savedMap, defaultItemMap);
    if (item) {
      acc.push(item);
    }
    return acc;
  }, []);

  return ensureRequiredDashboardItems(items);
};
