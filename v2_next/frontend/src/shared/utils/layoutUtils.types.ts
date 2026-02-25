import type { LayoutMap } from '../types';

export interface NormalizeLayoutResult {
  layout: LayoutMap;
  cols: number;
  scaled: boolean;
}
