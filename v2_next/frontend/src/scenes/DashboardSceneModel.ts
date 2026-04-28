export type WidgetType = 'kpi' | 'spot' | 'temps' | 'camera' | 'molds' | 'env' | 'notice' | 'timeseries' | 'markdown';

export interface DashboardItem {
  key: string;
  type: WidgetType;
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
  properties?: any;
}

export type SavedLayoutItem = {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  type?: WidgetType;
  title?: string;
  properties?: any;
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
