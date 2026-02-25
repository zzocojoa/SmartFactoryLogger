import type { LayoutMap } from '../types';

export type LayoutPresetId = '16:9' | '21:9' | '4:3' | 'compact';

export interface LayoutPreset {
  id: LayoutPresetId;
  name: string;
  description: string;
  layout: LayoutMap;
}
