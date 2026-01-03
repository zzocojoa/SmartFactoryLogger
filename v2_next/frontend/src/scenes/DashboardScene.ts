import {
  EmbeddedScene,
  SceneGridLayout,
  SceneGridItem,
} from '@grafana/scenes';
import { ReactWidget } from './ReactWidgetObject';
import React from 'react';

export type SavedLayoutItem = {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
};

export type SavedLayoutMap = Record<string, SavedLayoutItem>;

export const DASHBOARD_LAYOUT_KEYS = [
  'kpi',
  'spot',
  'temps',
  'camera',
  'molds',
  'env',
  'notice',
] as const;

export function getDashboardScene(
  renderKpi: () => React.ReactNode,
  renderSpot: () => React.ReactNode,
  renderTemps: () => React.ReactNode,
  renderMolds: () => React.ReactNode,
  renderEnv: () => React.ReactNode,
  renderCamera: () => React.ReactNode,
  renderNotice: () => React.ReactNode,
  savedLayout?: SavedLayoutMap | null
) {
  const defaultChildren = [
    { key: 'kpi', x: 0, y: 0, width: 15, height: 18, body: new ReactWidget({ title: '공정 KPI', renderWidget: renderKpi }) },
    { key: 'spot', x: 15, y: 0, width: 25, height: 4, body: new ReactWidget({ title: 'SPOT 온도', renderWidget: renderSpot }) },
    { key: 'temps', x: 15, y: 4, width: 25, height: 4, body: new ReactWidget({ title: '보조 온도', renderWidget: renderTemps }) },
    { key: 'camera', x: 15, y: 8, width: 25, height: 10, body: new ReactWidget({ title: 'SPOT 카메라', renderWidget: renderCamera }) },
    { key: 'molds', x: 40, y: 0, width: 20, height: 8, body: new ReactWidget({ title: '몰드 존', renderWidget: renderMolds }) },
    { key: 'env', x: 40, y: 8, width: 20, height: 4, body: new ReactWidget({ title: '환경', renderWidget: renderEnv }) },
    { key: 'notice', x: 40, y: 12, width: 20, height: 6, body: new ReactWidget({ title: '작업자 확인', renderWidget: renderNotice }) },
  ];

  const savedMap = savedLayout ?? {};

  // Merge saved layout
  const children = defaultChildren.map((item) => {
    const saved = savedMap[item.key];
    if (saved) {
      return new SceneGridItem({
        ...item,
        x: saved.x ?? item.x,
        y: saved.y ?? item.y,
        width: saved.width ?? item.width,
        height: saved.height ?? item.height,
      });
    }
    return new SceneGridItem(item);
  });

  return new EmbeddedScene({
    body: new SceneGridLayout({
      key: 'dashboard-grid',
      isDraggable: false,
      isResizable: false,
      children: children,
    }),
  });
}
