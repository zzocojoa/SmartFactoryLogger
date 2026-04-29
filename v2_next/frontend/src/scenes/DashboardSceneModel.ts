export type WidgetType = 'kpi' | 'spot' | 'temps' | 'camera' | 'molds' | 'env' | 'notice' | 'timeseries' | 'markdown';

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
] as const;

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

  return keys.reduce<DashboardItem[]>((acc, key) => {
    const defaultItem = defaultItemMap.get(key);
    const saved = savedMap[key];

    if (!defaultItem && !saved) {
      return acc;
    }

    const type: WidgetType = saved?.type ?? defaultItem?.type ?? 'markdown';
    const title: string = saved?.title ?? defaultItem?.title ?? 'Widget';
    const properties: Record<string, unknown> = saved?.properties ?? defaultItem?.properties ?? {};
    const x: number = saved?.x ?? defaultItem?.x ?? 0;
    const y: number = saved?.y ?? defaultItem?.y ?? 0;
    const width: number = saved?.width ?? defaultItem?.width ?? 10;
    const height: number = saved?.height ?? defaultItem?.height ?? 4;

    acc.push({
      key,
      type,
      title,
      x,
      y,
      width,
      height,
      properties,
    });
    return acc;
  }, []);
};
