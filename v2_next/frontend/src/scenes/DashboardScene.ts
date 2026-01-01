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

const GRID_COLUMNS = 60;
const LEGACY_GRID_COLUMNS = 24;
const GRID_SCALE = GRID_COLUMNS / LEGACY_GRID_COLUMNS;
const LAYOUT_STORAGE_KEY = 'grafana_scene_layout_v1';
const LAYOUT_COLS_KEY = 'grafana_scene_layout_cols';

const scaleLayoutMap = (layout: SavedLayoutMap, scale: number): SavedLayoutMap => {
  const scaled: SavedLayoutMap = {};
  Object.entries(layout).forEach(([key, item]) => {
    if (!item) {
      return;
    }
    scaled[key] = {
      ...item,
      x: item.x === undefined ? item.x : Math.max(0, Math.round(item.x * scale)),
      width: item.width === undefined ? item.width : Math.max(1, Math.round(item.width * scale)),
    };
  });
  return scaled;
};

const getLayoutMaxExtent = (layout: SavedLayoutMap): number => {
  let maxExtent = 0;
  Object.values(layout).forEach((item) => {
    if (!item) {
      return;
    }
    const x = item.x ?? 0;
    const width = item.width ?? 0;
    if (x + width > maxExtent) {
      maxExtent = x + width;
    }
  });
  return maxExtent;
};

const normalizeSavedLayout = (layout: SavedLayoutMap): SavedLayoutMap => {
  const rawCols = localStorage.getItem(LAYOUT_COLS_KEY);
  const savedCols = rawCols ? Number(rawCols) : Number.NaN;
  const maxExtent = getLayoutMaxExtent(layout);
  const isLegacy = maxExtent > 0 && maxExtent <= LEGACY_GRID_COLUMNS;

  if (savedCols === GRID_COLUMNS) {
    return layout;
  }

  if (savedCols === LEGACY_GRID_COLUMNS || (!Number.isFinite(savedCols) && isLegacy)) {
    const scaled = scaleLayoutMap(layout, GRID_SCALE);
    localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(scaled));
    localStorage.setItem(LAYOUT_COLS_KEY, String(GRID_COLUMNS));
    return scaled;
  }

  if (!Number.isFinite(savedCols) && maxExtent > 0) {
    localStorage.setItem(LAYOUT_COLS_KEY, String(GRID_COLUMNS));
  }

  return layout;
};

const loadSavedLayout = (defaults: Array<{ key: string }>): SavedLayoutMap => {
  const savedLayoutJson = localStorage.getItem(LAYOUT_STORAGE_KEY);
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
      return normalizeSavedLayout(legacyMap);
    }

    if (parsed && typeof parsed === 'object') {
      return normalizeSavedLayout(parsed as SavedLayoutMap);
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
  renderEnv: () => React.ReactNode,
  renderCamera: () => React.ReactNode,
  renderNotice: () => React.ReactNode
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
      isDraggable: false,
      isResizable: false,
      children: children,
    }),
  });
}
