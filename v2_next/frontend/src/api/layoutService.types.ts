import type { LayoutMap, LayoutSnapshot } from '../types';

export interface LayoutSavePayload {
  name: string;
  layout: LayoutMap;
  cols: number | string;
  version?: string;
}

export interface LayoutSlotActionPayload {
  slot_id: string;
}

export interface ClientLayoutSavePayload {
  layout: LayoutMap;
  cols: number;
  version: string;
  name: string;
}

export interface ClientLayoutListItem {
  id: string;
  name: string;
  updated_at?: string | null;
  cols?: string | number | null;
}

export type LayoutSnapshotResponse = LayoutSnapshot;
