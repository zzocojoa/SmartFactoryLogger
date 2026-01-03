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

  // Scale factor: 60 (User) -> 24 (Scene) = 0.4
  const SCALE_TO_SCENE = 24 / 60;

  // Merge saved layout
  const children = defaultChildren.map((item) => {
    const saved = savedMap[item.key];
    const base = saved || item;

    // Apply scaling and rounding to fit integer grid
    const x = Math.round((base.x ?? item.x) * SCALE_TO_SCENE);
    const y = base.y ?? item.y; // Height is row-based, no scaling needed usually unless ratio changed
    const width = Math.round((base.width ?? item.width) * SCALE_TO_SCENE);
    const height = base.height ?? item.height;

    // Ensure minimum width of 1 column in scene (approx 2.5 in user grid)
    const safeWidth = Math.max(1, width);

    return new SceneGridItem({
      ...item,
      x,
      y,
      width: safeWidth,
      height,
    });
  });

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
