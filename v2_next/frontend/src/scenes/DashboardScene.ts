import {
  EmbeddedScene,
  SceneGridLayout,
  SceneGridItem,
  PanelBuilders,
  SceneDataNode,
} from '@grafana/scenes';
import { ReactWidget } from './ReactWidgetObject';
import React from 'react';

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

export type WidgetRenderer = (item: DashboardItem) => React.ReactNode;
export type WidgetRegistry = Record<string, WidgetRenderer>;

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
  { key: 'kpi', type: 'kpi', title: '공정 KPI', x: 0, y: 0, width: 15, height: 18 },
  { key: 'spot', type: 'spot', title: 'SPOT 온도', x: 15, y: 0, width: 25, height: 4 },
  { key: 'temps', type: 'temps', title: '보조 온도', x: 15, y: 4, width: 25, height: 4 },
  { key: 'camera', type: 'camera', title: 'SPOT 카메라', x: 15, y: 8, width: 25, height: 10 },
  { key: 'molds', type: 'molds', title: '몰드 존', x: 40, y: 0, width: 20, height: 8 },
  { key: 'env', type: 'env', title: '환경', x: 40, y: 8, width: 20, height: 4 },
  { key: 'notice', type: 'notice', title: '작업자 확인', x: 40, y: 12, width: 20, height: 6 },
  { key: 'timeseries', type: 'timeseries', title: '타임 시리즈', x: 0, y: 18, width: 60, height: 8 },
];

export const DASHBOARD_LAYOUT_KEYS = [
  'kpi',
  'spot',
  'temps',
  'camera',
  'molds',
  'env',
  'notice',
  'timeseries',
] as const;

export function getDashboardScene(
  registry: WidgetRegistry,
  savedLayout?: SavedLayoutMap | null
) {
  const savedMap = savedLayout ?? {};
  
  // If a saved layout exists, we use it as the source of truth for which widgets to display.
  // We do NOT automatically merge defaults, otherwise a user cannot delete a default widget.
  const allKeys = savedLayout 
    ? Object.keys(savedMap) 
    : DEFAULT_DASHBOARD_ITEMS.map(i => i.key);
  
  // Scale factor: 60 (User) -> 24 (Scene) = 0.4
  const SCALE_TO_SCENE = 24 / 60;

  const children = allKeys.map(key => {
    const defaultItem = DEFAULT_DASHBOARD_ITEMS.find(i => i.key === key);
    const saved = savedMap[key];
    
    if (!defaultItem && !saved) return null; // Should not happen
    
    const type = saved?.type || defaultItem?.type || 'markdown';
    const title = saved?.title || defaultItem?.title || '새 위젯';
    const properties = saved?.properties || defaultItem?.properties || {};
    
    const xBase = saved?.x ?? defaultItem?.x ?? 0;
    const y = saved?.y ?? defaultItem?.y ?? 0;
    const wBase = saved?.width ?? defaultItem?.width ?? 10;
    const h = saved?.height ?? defaultItem?.height ?? 4;
    
    const x = Math.round(xBase * SCALE_TO_SCENE);
    const width = Math.max(1, Math.round(wBase * SCALE_TO_SCENE));

    const item: DashboardItem = {
       key, type, title, x: xBase, y, width: wBase, height: h, properties
    };

    const render = registry[type] || registry['markdown'] || (() => React.createElement('div', null, `Unknown widget type: ${type}`));

    return new SceneGridItem({
      key,
      x,
      y,
      width,
      height: h,
      body: new ReactWidget({
        title,
        type,
        properties,
        renderWidget: () => render(item)
      })
    });
  }).filter(Boolean) as SceneGridItem[];

  return new EmbeddedScene({
    body: new SceneGridLayout({
      key: 'dashboard-grid',
      isDraggable: false,
      isResizable: false,
      // @ts-ignore: Force 60 columns support if engine allows
      cols: 60,
      children: children,
    }),
  });
}
