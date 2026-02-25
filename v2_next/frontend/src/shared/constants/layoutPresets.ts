/**
 * Layout Presets for different screen aspect ratios
 */

import type { LayoutMap } from '../types';
import { pickPresetById, pickRecommendedPreset } from './layoutPresets.selectors';
import type { LayoutPreset, LayoutPresetId } from './layoutPresets.types';

export type { LayoutPreset, LayoutPresetId } from './layoutPresets.types';

/**
 * Standard 16:9 layout (Default - 1920x1080, etc.)
 * Balanced layout with all widgets visible
 */
const PRESET_16_9: LayoutMap = {
  kpi: { x: 0, y: 0, width: 15, height: 18, type: 'kpi', title: '공정 KPI' },
  spot: { x: 15, y: 0, width: 25, height: 4, type: 'spot', title: 'SPOT 온도' },
  temps: { x: 15, y: 4, width: 25, height: 4, type: 'temps', title: '보조 온도' },
  camera: { x: 15, y: 8, width: 25, height: 10, type: 'camera', title: 'SPOT 카메라' },
  molds: { x: 40, y: 0, width: 20, height: 8, type: 'molds', title: '몰드 존' },
  env: { x: 40, y: 8, width: 20, height: 4, type: 'env', title: '환경' },
  timeseries: { x: 0, y: 18, width: 60, height: 8, type: 'timeseries', title: '타임 시리즈' },
};

/**
 * Ultrawide 21:9 layout (2560x1080, 3440x1440, etc.)
 * Wider layout utilizing horizontal space
 */
const PRESET_21_9: LayoutMap = {
  kpi: { x: 0, y: 0, width: 12, height: 16, type: 'kpi', title: '공정 KPI' },
  spot: { x: 12, y: 0, width: 16, height: 4, type: 'spot', title: 'SPOT 온도' },
  temps: { x: 12, y: 4, width: 16, height: 4, type: 'temps', title: '보조 온도' },
  camera: { x: 12, y: 8, width: 16, height: 8, type: 'camera', title: 'SPOT 카메라' },
  molds: { x: 28, y: 0, width: 16, height: 8, type: 'molds', title: '몰드 존' },
  env: { x: 28, y: 8, width: 16, height: 4, type: 'env', title: '환경' },
  timeseries: { x: 44, y: 0, width: 16, height: 16, type: 'timeseries', title: '타임 시리즈' },
};

/**
 * Classic 4:3 layout (1024x768, 1280x960, etc.)
 * Stacked layout for narrower screens
 */
const PRESET_4_3: LayoutMap = {
  kpi: { x: 0, y: 0, width: 30, height: 12, type: 'kpi', title: '공정 KPI' },
  spot: { x: 30, y: 0, width: 30, height: 4, type: 'spot', title: 'SPOT 온도' },
  temps: { x: 30, y: 4, width: 30, height: 4, type: 'temps', title: '보조 온도' },
  camera: { x: 30, y: 8, width: 30, height: 8, type: 'camera', title: 'SPOT 카메라' },
  molds: { x: 0, y: 12, width: 30, height: 6, type: 'molds', title: '몰드 존' },
  env: { x: 30, y: 16, width: 30, height: 4, type: 'env', title: '환경' },
  timeseries: { x: 0, y: 18, width: 60, height: 8, type: 'timeseries', title: '타임 시리즈' },
};

/**
 * Compact layout for smaller screens or tablets
 * Simplified layout with essential widgets
 */
const PRESET_COMPACT: LayoutMap = {
  kpi: { x: 0, y: 0, width: 60, height: 8, type: 'kpi', title: '공정 KPI' },
  spot: { x: 0, y: 8, width: 30, height: 4, type: 'spot', title: 'SPOT 온도' },
  temps: { x: 30, y: 8, width: 30, height: 4, type: 'temps', title: '보조 온도' },
  timeseries: { x: 0, y: 12, width: 60, height: 8, type: 'timeseries', title: '타임 시리즈' },
};

export const LAYOUT_PRESETS: LayoutPreset[] = [
  {
    id: '16:9',
    name: '16:9 일반',
    description: '표준 모니터 (1920x1080 등)',
    layout: PRESET_16_9,
  },
  {
    id: '21:9',
    name: '21:9 울트라와이드',
    description: '울트라와이드 모니터 (2560x1080, 3440x1440 등)',
    layout: PRESET_21_9,
  },
  {
    id: '4:3',
    name: '4:3 클래식',
    description: '구형 모니터 (1024x768, 1280x960 등)',
    layout: PRESET_4_3,
  },
  {
    id: 'compact',
    name: '컴팩트',
    description: '작은 화면 또는 태블릿용 간소화 레이아웃',
    layout: PRESET_COMPACT,
  },
];

/**
 * Get a preset by its ID
 */
export function getPresetById(id: LayoutPresetId): LayoutPreset | undefined {
  return pickPresetById(LAYOUT_PRESETS, id);
}

/**
 * Get the recommended preset based on detected aspect ratio
 */
export function getRecommendedPreset(aspectRatio: string): LayoutPreset {
  return pickRecommendedPreset(LAYOUT_PRESETS, aspectRatio);
}
