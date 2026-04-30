import type { SceneGridItemLike, SceneObjectBase } from '@grafana/scenes';
import type { WidgetType } from '../../scenes/DashboardSceneModel';
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
      x: x ?? 0,
      y: y ?? 0,
      width: width ?? 1,
      height: height ?? 1,
      ...metadata,
    };
  });
  return next;
};
