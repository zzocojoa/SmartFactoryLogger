import { layoutService, localLayoutService } from '../api/layoutService';
import type { LayoutMap } from '../../../shared/types';
import type { StorageMode } from '../../../shared/constants/logic';

export const readLayoutStorageMode = (): StorageMode => localLayoutService.getStorageMode();

export const persistLayoutStorageMode = (mode: StorageMode): void => {
  localLayoutService.setStorageMode(mode);
};

export const fetchLayoutSlotsByMode = async (mode: StorageMode) => {
  if (mode === 'local') {
    const slots = await localLayoutService.getLayoutList();
    return { slots, activeId: null as string | null };
  }
  const data = await layoutService.getLayouts();
  return { slots: data?.slots ?? [], activeId: data?.active_id ?? null };
};

export const fetchLocalLayoutSnapshot = () => localLayoutService.getLocalLayout();
export const fetchServerLayoutSnapshot = () => layoutService.getLayoutSnapshot();
export const saveServerLayout = (payload: {
  name: string;
  layout: LayoutMap;
  cols: string | number;
  version: string;
}) => layoutService.saveLayout(payload);
export const saveLocalLayout = (layout: LayoutMap, name: string, cols: number) =>
  localLayoutService.saveLocalLayout(layout, name, cols);
export const restoreServerLayout = (slotId: string) => layoutService.restoreLayout(slotId);
export const restoreLocalLayout = (slotId: string) => localLayoutService.restoreLocalLayout(slotId);
export const deleteServerLayout = (slotId: string) => layoutService.deleteLayout(slotId);
export const deleteLocalLayout = (slotId: string) => localLayoutService.deleteLocalLayout(slotId);
