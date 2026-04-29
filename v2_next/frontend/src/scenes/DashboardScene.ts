import {
  EmbeddedScene,
  SceneGridLayout,
  SceneGridItem,
} from '@grafana/scenes';
import { ReactWidget } from './ReactWidgetObject';
import React from 'react';
import { CURRENT_LAYOUT_COLS } from '../shared/constants/logic';
import {
  DEFAULT_DASHBOARD_ITEMS,
  type DashboardItem,
  type SavedLayoutMap,
  type WidgetType,
} from './DashboardSceneModel';

export type WidgetRenderer = (item: DashboardItem, model: ReactWidget) => React.ReactNode;
export type WidgetRegistry = Record<string, WidgetRenderer>;

export type { DashboardItem, SavedLayoutItem, SavedLayoutMap, WidgetType } from './DashboardSceneModel';

export function getDashboardScene(
  registry: WidgetRegistry,
  savedLayout?: SavedLayoutMap | null
) {
  const savedMap = savedLayout ?? {};
  const allKeys = savedLayout
    ? Object.keys(savedMap).filter(k => k !== 'notice')
    : DEFAULT_DASHBOARD_ITEMS.reduce<string[]>((acc, i) => {
        if (i.key !== 'notice') acc.push(i.key);
        return acc;
      }, []);
  
  const defaultItemMap = new Map(DEFAULT_DASHBOARD_ITEMS.map(i => [i.key, i]));

  const children = allKeys.map(key => {
    const defaultItem = defaultItemMap.get(key);
    const saved = savedMap[key];
    
    if (!defaultItem && !saved) return null; // Should not happen
    
    const type = saved?.type || defaultItem?.type || 'markdown';
    const title = saved?.title || defaultItem?.title || '새 위젯';
    const properties = saved?.properties || defaultItem?.properties || {};
    
    const xBase = saved?.x ?? defaultItem?.x ?? 0;
    const y = saved?.y ?? defaultItem?.y ?? 0;
    const wBase = saved?.width ?? defaultItem?.width ?? 10;
    const h = saved?.height ?? defaultItem?.height ?? 4;
    
    const x = xBase;
    const width = Math.max(1, wBase);

    const item: DashboardItem = {
      key,
      type,
      title,
      x: xBase,
      y,
      width: wBase,
      height: h,
      properties,
    };

    const render = registry[type] || registry['markdown'] || ((_item: DashboardItem, _model: ReactWidget) => React.createElement('div', null, `Unknown widget type: ${type}`));

    return new SceneGridItem({
      key,
      x,
      y,
      width,
      height: h,
      body: new ReactWidget({
        key,
        title,
        type,
        properties,
        renderWidget: (m) =>
          render(
            {
              ...item,
              title: typeof m.state.title === 'string' ? m.state.title : item.title,
              type: typeof m.state.type === 'string' ? (m.state.type as WidgetType) : item.type,
              properties: m.state.properties ?? item.properties,
            },
            m
          )
      })
    });
  }).filter(Boolean) as SceneGridItem[];

  const gridLayoutState = {
    key: 'dashboard-grid',
    isDraggable: false,
    isResizable: false,
    cols: CURRENT_LAYOUT_COLS,
    children,
  } as ConstructorParameters<typeof SceneGridLayout>[0] & { cols: number };

  return new EmbeddedScene({
    body: new SceneGridLayout(gridLayoutState),
  });
}
