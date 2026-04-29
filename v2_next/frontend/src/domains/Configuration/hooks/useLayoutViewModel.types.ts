import type { LayoutEntry, LayoutMap, LayoutSlotSummary, LayoutSnapshot } from '../../../shared/types';
import type { LayoutPresetId } from '../../../shared/constants/layoutPresets';
import type { StorageMode } from '../../../shared/constants/logic';

export interface UseLayoutViewModel {
  layoutSnapshot: LayoutSnapshot | null;
  layoutSlots: LayoutSlotSummary[];
  layoutActiveId: string | null;
  layoutEditing: boolean;
  layoutLoadError: string | null;
  layoutSaveMessage: string | null;
  layoutSaveError: string | null;
  storageMode: StorageMode;
  setLayoutEditing: (editing: boolean) => void;
  setStorageMode: (mode: StorageMode) => void;
  loadLayoutSnapshot: () => Promise<void>;
  handleSaveLayout: (name: string, newLayout?: LayoutMap) => Promise<void>;
  handleRestoreLayout: (slotId: string) => Promise<void>;
  handleDeleteLayout: (slotId: string) => Promise<void>;
  applyPreset: (presetId: LayoutPresetId) => void;
  updateWidget: (key: string, updates: Partial<LayoutEntry>, baseLayout?: LayoutMap) => void;
  deleteWidget: (key: string, baseLayout?: LayoutMap) => void;
  addWidget: (type: string, title?: string, baseLayout?: LayoutMap) => void;
  fetchLayoutSlots: () => Promise<void>;
  readLegacyLayoutSnapshot: () => LayoutSnapshot | null;
}
