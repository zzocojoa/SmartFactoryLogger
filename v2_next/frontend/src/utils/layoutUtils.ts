import { SceneGridItemLike, SceneObjectBase } from '@grafana/scenes';
import { CURRENT_LAYOUT_COLS } from '../constants/logic';
import type { WidgetType } from '../scenes/DashboardScene';
import type { LayoutMap } from '../types';

export type { NormalizeLayoutResult } from './layoutUtils.types';
export {
  buildLayoutMapFromArray,
  buildLayoutMapFromObject,
  coerceLayoutEntry,
  getLayoutMaxExtent,
  normalizeLayoutMap,
  scaleLayoutMap,
} from './layoutUtils.pure';

export const buildLayoutMap = (
  children: (SceneGridItemLike | SceneObjectBase)[] | undefined
): LayoutMap => {
  const next: LayoutMap = {};
  const SCENE_TO_USER = CURRENT_LAYOUT_COLS / 24;

  if (!children || !Array.isArray(children)) {
    console.warn('buildLayoutMap: Invalid children', children);
    return next;
  }

  children.forEach((child) => {
    const state = (child as any).state;
    if (!state) return;

    const { x, y, width, height, body, key } = state;
    if (!key) return;

    const metadata: { type?: WidgetType; title?: string; properties?: any } = {};

    if (body && body.state) {
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
