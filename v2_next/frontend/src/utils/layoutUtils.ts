
import { SceneGridItemLike, SceneObjectBase } from '@grafana/scenes';
import { LayoutEntry, LayoutMap } from '../types';
import { CURRENT_LAYOUT_COLS } from '../constants/logic';
import { DASHBOARD_LAYOUT_KEYS, WidgetType } from '../scenes/DashboardScene';

const LEGACY_LAYOUT_COLS = 24;

export const coerceLayoutEntry = (entry: unknown): LayoutEntry | null => {
  if (!entry || typeof entry !== 'object') {
    return null;
  }
  const raw = entry as Record<string, unknown>;
  return {
    x: typeof raw.x === 'number' ? raw.x : 0,
    y: typeof raw.y === 'number' ? raw.y : 0,
    width: typeof raw.width === 'number' ? raw.width : 4,
    height: typeof raw.height === 'number' ? raw.height : 4,
    type: typeof raw.type === 'string' ? raw.type as WidgetType : undefined,
    title: typeof raw.title === 'string' ? raw.title : undefined,
    properties: raw.properties,
  };
};

export const buildLayoutMapFromArray = (items: unknown[]): LayoutMap => {
  const layout: LayoutMap = {};
  (DASHBOARD_LAYOUT_KEYS as unknown as string[]).forEach((key, index) => {
    const entry = coerceLayoutEntry(items[index]);
    if (entry) {
      layout[key] = entry;
    }
  });
  return layout;
};

export const buildLayoutMapFromObject = (value: Record<string, unknown>): LayoutMap => {
  const layout: LayoutMap = {};
  Object.entries(value).forEach(([key, entry]) => {
    const parsed = coerceLayoutEntry(entry);
    if (parsed) {
      layout[key] = parsed;
    }
  });
  return layout;
};

export const getLayoutMaxExtent = (layout: LayoutMap): number => {
  let maxExtent = 0;
  Object.values(layout).forEach((item) => {
    const x = item.x ?? 0;
    const width = item.width ?? 0;
    if (x + width > maxExtent) {
      maxExtent = x + width;
    }
  });
  return maxExtent;
};

export const scaleLayoutMap = (layout: LayoutMap, scale: number): LayoutMap => {
  const scaled: LayoutMap = {};
  Object.entries(layout).forEach(([key, item]) => {
    scaled[key] = {
      ...item,
      x: Math.max(0, Math.round(item.x * scale)),
      width: Math.max(1, Math.round(item.width * scale)),
    };
  });
  return scaled;
};

export const normalizeLayoutMap = (layout: LayoutMap, colsValue?: string | number | null) => {
  const savedCols =
    colsValue === undefined || colsValue === null || `${colsValue}`.trim() === ''
      ? Number.NaN
      : Number(colsValue);
  const maxExtent = getLayoutMaxExtent(layout);
  const isLegacy = maxExtent > 0 && maxExtent <= LEGACY_LAYOUT_COLS;
  if (savedCols === LEGACY_LAYOUT_COLS || (!Number.isFinite(savedCols) && isLegacy)) {
    return {
      layout: scaleLayoutMap(layout, CURRENT_LAYOUT_COLS / LEGACY_LAYOUT_COLS),
      cols: CURRENT_LAYOUT_COLS,
      scaled: true,
    };
  }
  return {
    layout,
    cols: Number.isFinite(savedCols) ? savedCols : CURRENT_LAYOUT_COLS,
    scaled: false,
  };
};

export const buildLayoutMap = (children: (SceneGridItemLike | SceneObjectBase)[] | undefined): LayoutMap => {
  const next: LayoutMap = {};
  const SCENE_TO_USER = CURRENT_LAYOUT_COLS / 24;

  if (!children || !Array.isArray(children)) {
    console.warn('buildLayoutMap: Invalid children', children);
    return next;
  }

  children.forEach((child) => {
    // Duck typing check for SceneGridItem-like state
    const state = (child as any).state;
    if (!state) return;

    const { x, y, width, height, body, key } = state;
    if (!key) return;

    const metadata: { type?: WidgetType; title?: string; properties?: any } = {};
    
    // Check body state for metadata (ReactWidget)
    if (body && body.state) {
        // We look for our specific fields
        const bodyState = body.state;
        if (bodyState.type) metadata.type = bodyState.type as WidgetType;
        if (bodyState.title) metadata.title = bodyState.title;
        if (bodyState.properties) metadata.properties = bodyState.properties;
    }

    next[key] = {
      x: Math.round((x ?? 0) * SCENE_TO_USER),
      y: y ?? 0,
      width: Math.round((width ?? 1) * SCENE_TO_USER),
      height: height ?? 1,
      ...metadata,
    };
  });
  return next;
};
