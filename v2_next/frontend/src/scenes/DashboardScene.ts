import {
  EmbeddedScene,
  SceneGridLayout,
  SceneGridItem,
} from '@grafana/scenes';
import { ReactWidget } from './ReactWidgetObject';
import React from 'react';

type SavedLayoutItem = {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
};

type SavedLayoutMap = Record<string, SavedLayoutItem>;

const loadSavedLayout = (defaults: Array<{ key: string }>): SavedLayoutMap => {
  const savedLayoutJson = localStorage.getItem('grafana_scene_layout_v1');
  if (!savedLayoutJson) {
    return {};
  }

  try {
    const parsed = JSON.parse(savedLayoutJson) as SavedLayoutMap | SavedLayoutItem[];
    if (Array.isArray(parsed)) {
      const legacyMap: SavedLayoutMap = {};
      defaults.forEach((item, index) => {
        if (parsed[index]) {
          legacyMap[item.key] = parsed[index];
        }
      });
      return legacyMap;
    }

    if (parsed && typeof parsed === 'object') {
      return parsed;
    }
  } catch (e) {
    console.error('Failed to parse saved layout', e);
  }

  return {};
};

export function getDashboardScene(
  renderKpi: () => React.ReactNode,
  renderSpot: () => React.ReactNode,
  renderTemps: () => React.ReactNode,
  renderMolds: () => React.ReactNode,
  renderCamera: () => React.ReactNode,
  renderNotice: () => React.ReactNode
) {
  const defaultChildren = [
    { key: 'kpi', x: 0, y: 0, width: 6, height: 8, body: new ReactWidget({ title: 'Process KPI', renderWidget: renderKpi }) },
    { key: 'spot', x: 6, y: 0, width: 10, height: 4, body: new ReactWidget({ title: 'SPOT Temperature', renderWidget: renderSpot }) },
    { key: 'temps', x: 6, y: 4, width: 10, height: 4, body: new ReactWidget({ title: 'Secondary Temps', renderWidget: renderTemps }) },
    { key: 'molds', x: 16, y: 0, width: 8, height: 8, body: new ReactWidget({ title: 'Mold Zones', renderWidget: renderMolds }) },
    { key: 'camera', x: 0, y: 8, width: 12, height: 10, body: new ReactWidget({ title: 'SPOT Camera', renderWidget: renderCamera }) },
    { key: 'notice', x: 12, y: 8, width: 12, height: 10, body: new ReactWidget({ title: 'Notice', renderWidget: renderNotice }) },
  ];

  const savedLayout = loadSavedLayout(defaultChildren);

  // Merge saved layout
  const children = defaultChildren.map((item) => {
    const saved = savedLayout[item.key];
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
      isDraggable: true,
      isResizable: true,
      children: children,
    }),
  });
}
