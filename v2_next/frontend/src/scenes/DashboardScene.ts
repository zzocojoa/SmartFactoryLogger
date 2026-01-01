import {
  EmbeddedScene,
  SceneGridLayout,
  SceneGridItem,
  SceneFlexLayout,
  SceneFlexItem,
} from '@grafana/scenes';
import { ReactWidget } from './ReactWidgetObject';
import React from 'react';

export function getDashboardScene(
  renderKpi: () => React.ReactNode,
  renderSpot: () => React.ReactNode,
  renderTemps: () => React.ReactNode,
  renderMolds: () => React.ReactNode,
  renderCamera: () => React.ReactNode,
  renderNotice: () => React.ReactNode
) {
  const savedLayoutJson = localStorage.getItem('grafana_scene_layout_v1');
  let savedLayout: any[] = [];
  if (savedLayoutJson) {
      try {
          savedLayout = JSON.parse(savedLayoutJson);
      } catch (e) {
          console.error("Failed to parse saved layout", e);
      }
  }

  const defaultChildren = [
    { x: 0, y: 0, width: 6, height: 8, body: new ReactWidget({ title: 'Process KPI', renderWidget: renderKpi }) },
    { x: 6, y: 0, width: 10, height: 4, body: new ReactWidget({ title: 'SPOT Temperature', renderWidget: renderSpot }) },
    { x: 6, y: 4, width: 10, height: 4, body: new ReactWidget({ title: 'Secondary Temps', renderWidget: renderTemps }) },
    { x: 16, y: 0, width: 8, height: 8, body: new ReactWidget({ title: 'Mold Zones', renderWidget: renderMolds }) },
    { x: 0, y: 8, width: 12, height: 10, body: new ReactWidget({ title: 'SPOT Camera', renderWidget: renderCamera }) },
    { x: 12, y: 8, width: 12, height: 10, body: new ReactWidget({ title: 'Notice', renderWidget: renderNotice }) },
  ];

  // Merge saved layout
  const children = defaultChildren.map((item, index) => {
     if (savedLayout[index]) {
         return new SceneGridItem({
             ...item,
             x: savedLayout[index].x ?? item.x,
             y: savedLayout[index].y ?? item.y,
             width: savedLayout[index].width ?? item.width,
             height: savedLayout[index].height ?? item.height,
         });
     }
     return new SceneGridItem(item);
  });

  return new EmbeddedScene({
    body: new SceneGridLayout({
      key: 'dashboard-grid',
      isDraggable: true,
      isResizable: true,
      children: children,
    }),
  });
}
