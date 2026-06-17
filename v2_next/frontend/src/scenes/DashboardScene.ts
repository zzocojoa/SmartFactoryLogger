import {
  EmbeddedScene,
  SceneGridItem,
  SceneGridLayout,
} from '@grafana/scenes';
import React from 'react';
import { CURRENT_LAYOUT_COLS } from '../shared/constants/logic';
import {
  type DashboardItem,
  resolveDashboardItems,
  type SavedLayoutMap,
  type WidgetType,
} from './DashboardSceneModel';
import { ReactWidget } from './ReactWidgetObject';

export type WidgetRenderer = (item: DashboardItem, model: ReactWidget) => React.ReactNode;
export type WidgetRegistry = Record<string, WidgetRenderer>;

export type { DashboardItem, SavedLayoutItem, SavedLayoutMap, WidgetType } from './DashboardSceneModel';

export function getDashboardScene(
  registry: WidgetRegistry,
  savedLayout?: SavedLayoutMap | null
) {
  const items = resolveDashboardItems(savedLayout ?? null);

  const children = items.map((item) => {
    const render =
      registry[item.type] ||
      registry.markdown ||
      ((_item: DashboardItem, _model: ReactWidget) =>
        React.createElement('div', null, `Unknown widget type: ${item.type}`));

    return new SceneGridItem({
      key: item.key,
      x: item.x,
      y: item.y,
      width: Math.max(1, item.width),
      height: item.height,
      body: new ReactWidget({
        key: item.key,
        title: item.title,
        type: item.type,
        properties: item.properties,
        renderWidget: (model) =>
          render(
            {
              ...item,
              title: typeof model.state.title === 'string' ? model.state.title : item.title,
              type: typeof model.state.type === 'string' ? (model.state.type as WidgetType) : item.type,
              properties: model.state.properties ?? item.properties,
            },
            model
          ),
      }),
    });
  });

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
