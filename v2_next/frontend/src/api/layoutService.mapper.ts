import type { StorageMode } from '../constants/logic';
import type { LayoutMap } from '../types';
import type { ClientLayoutSavePayload } from './layoutService.types';

export function generateUUIDv4(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function resolveStorageMode(rawMode: string | null): StorageMode {
  return rawMode === 'server' ? 'server' : 'local';
}

export function buildClientLayoutPayload(
  layout: LayoutMap,
  name: string,
  cols: number
): ClientLayoutSavePayload {
  return {
    layout,
    cols,
    version: 'v2',
    name,
  };
}
