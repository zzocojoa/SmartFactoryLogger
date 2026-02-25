import { useState, useCallback } from 'react';
import type {
  LayoutEntry,
  LayoutMap,
  LayoutSnapshot,
  LayoutSlotSummary,
} from '../../../shared/types';
import { DEFAULT_DASHBOARD_ITEMS } from '../../../scenes/DashboardScene';
import {
  buildLayoutMapFromArray,
  buildLayoutMapFromObject,
  normalizeLayoutMap,
} from '../../../shared/utils/layoutUtils';
import {
  CURRENT_LAYOUT_COLS,
  LAYOUT_BACKUP_KEY,
  LAYOUT_STORAGE_KEY,
  StorageMode,
} from '../../../shared/constants/logic';
import { getPresetById, type LayoutPresetId } from '../../../shared/constants/layoutPresets';
import {
  deleteLocalLayout,
  deleteServerLayout,
  fetchLayoutSlotsByMode,
  fetchLocalLayoutSnapshot,
  fetchServerLayoutSnapshot,
  persistLayoutStorageMode,
  readLayoutStorageMode,
  restoreLocalLayout,
  restoreServerLayout,
  saveLocalLayout,
  saveServerLayout,
} from './useLayoutViewModel.service';
import { resolveDefaultWidgetSpec } from './useLayoutViewModel.selectors';
import { useLayoutViewModelEffects } from './useLayoutViewModelEffects';
import type { UseLayoutViewModel } from './useLayoutViewModel.types';

const LAYOUT_COLS_KEY = 'grafana_scene_layout_cols';
const CURRENT_LAYOUT_VERSION = 'v2';

export const useLayoutViewModel = (): UseLayoutViewModel => {
  const [layoutEditing, setLayoutEditing] = useState(false);
  const [layoutSnapshot, setLayoutSnapshot] = useState<LayoutSnapshot | null>(null);
  const [layoutSlots, setLayoutSlots] = useState<LayoutSlotSummary[]>([]);
  const [layoutActiveId, setLayoutActiveId] = useState<string | null>(null);
  const [layoutLoadError, setLayoutLoadError] = useState<string | null>(null);
  const [layoutSaveMessage, setLayoutSaveMessage] = useState<string | null>(null);
  const [layoutSaveError, setLayoutSaveError] = useState<string | null>(null);
  const [storageMode, setStorageModeState] = useState<StorageMode>(() => readLayoutStorageMode());

  const setStorageMode = useCallback((mode: StorageMode) => {
    setStorageModeState(mode);
    persistLayoutStorageMode(mode);
  }, []);

  const readLegacyLayoutSnapshot = useCallback((): LayoutSnapshot | null => {
    try {
      const raw = localStorage.getItem(LAYOUT_STORAGE_KEY);
      if (!raw) {
        return null;
      }

      const parsed = JSON.parse(raw);
      let layout: LayoutMap = {};
      if (Array.isArray(parsed)) {
        layout = buildLayoutMapFromArray(parsed);
      } else if (parsed && typeof parsed === 'object') {
        layout = buildLayoutMapFromObject(parsed as Record<string, unknown>);
      }

      if (Object.keys(layout).length === 0) {
        return null;
      }

      return {
        layout,
        cols: localStorage.getItem(LAYOUT_COLS_KEY),
        version: 'v1',
      };
    } catch (error) {
      console.error('Legacy layout parse failed', error);
      return null;
    }
  }, []);

  const migrateLegacyLayout = useCallback(async (): Promise<LayoutSnapshot | null> => {
    const legacy = readLegacyLayoutSnapshot();
    if (!legacy) {
      return null;
    }

    const normalized = normalizeLayoutMap(legacy.layout, legacy.cols ?? null);
    const payload = {
      name: 'Legacy Layout',
      layout: normalized.layout,
      cols: normalized.cols ?? CURRENT_LAYOUT_COLS,
      version: CURRENT_LAYOUT_VERSION,
    };

    try {
      const data = await saveServerLayout(payload);
      localStorage.removeItem(LAYOUT_STORAGE_KEY);
      localStorage.removeItem(LAYOUT_COLS_KEY);
      localStorage.removeItem(LAYOUT_BACKUP_KEY);
      return {
        layout: payload.layout,
        cols: payload.cols,
        version: payload.version,
        updated_at: data?.updated_at ?? null,
      };
    } catch (error) {
      console.error('Legacy layout migration failed', error);
      return {
        layout: payload.layout,
        cols: payload.cols,
        version: payload.version,
      };
    }
  }, [readLegacyLayoutSnapshot]);

  const fetchLayoutSlots = useCallback(async () => {
    try {
      const { slots, activeId } = await fetchLayoutSlotsByMode(storageMode);
      setLayoutSlots(slots);
      setLayoutActiveId(activeId);
    } catch (error) {
      console.error('Layout slots load failed', error);
      setLayoutSlots([]);
      setLayoutActiveId(null);
    }
  }, [storageMode]);

  const loadLayoutSnapshot = useCallback(async () => {
    setLayoutLoadError(null);

    if (storageMode === 'local') {
      const localSnapshot = await fetchLocalLayoutSnapshot();
      if (localSnapshot?.layout) {
        const normalized = normalizeLayoutMap(localSnapshot.layout, localSnapshot.cols ?? null);
        setLayoutSnapshot({
          ...localSnapshot,
          layout: normalized.layout,
          cols: normalized.cols,
        });
        await fetchLayoutSlots();
        return;
      }
    }

    try {
      const snapshot = await fetchServerLayoutSnapshot();
      if (snapshot?.layout) {
        const normalized = normalizeLayoutMap(snapshot.layout, snapshot.cols ?? null);
        setLayoutSnapshot({
          ...snapshot,
          layout: normalized.layout,
          cols: normalized.cols,
        });
      } else {
        setLayoutSnapshot(null);
      }
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 404) {
        const migrated = await migrateLegacyLayout();
        setLayoutSnapshot(migrated);
      } else {
        console.error('Layout load failed', error);
        setLayoutLoadError('레이아웃을 불러오지 못했습니다.');
      }
    } finally {
      await fetchLayoutSlots();
    }
  }, [fetchLayoutSlots, migrateLegacyLayout, storageMode]);

  const handleSaveLayout = async (name: string, newLayout?: LayoutMap) => {
    const layoutToSave = newLayout ?? layoutSnapshot?.layout;
    if (!layoutToSave) return;

    setLayoutSaveError(null);
    setLayoutSaveMessage(null);

    try {
      const cols = layoutSnapshot?.cols ?? CURRENT_LAYOUT_COLS;

      if (storageMode === 'local') {
        const colsNum = typeof cols === 'string' ? parseInt(cols, 10) : cols;
        const success = await saveLocalLayout(layoutToSave, name, colsNum);
        if (!success) {
          throw new Error('Failed to save client layout');
        }

        setLayoutSnapshot((prev) =>
          prev
            ? { ...prev, layout: layoutToSave }
            : {
                layout: layoutToSave,
                cols: CURRENT_LAYOUT_COLS.toString(),
                version: CURRENT_LAYOUT_VERSION,
              }
        );

        setLayoutSaveMessage(`레이아웃 '${name}' 저장 완료 (로컬)`);
        await fetchLayoutSlots();
        return;
      }

      await saveServerLayout({
        name,
        layout: layoutToSave,
        cols,
        version: layoutSnapshot?.version ?? CURRENT_LAYOUT_VERSION,
      });

      setLayoutSnapshot((prev) =>
        prev
          ? { ...prev, layout: layoutToSave }
          : {
              layout: layoutToSave,
              cols: CURRENT_LAYOUT_COLS.toString(),
              version: CURRENT_LAYOUT_VERSION,
            }
      );

      setLayoutSaveMessage(`레이아웃 '${name}' 서버 저장 완료`);
      await fetchLayoutSlots();
    } catch (error) {
      console.error('Layout save failed', error);
      setLayoutSaveError('레이아웃 저장 실패');
    }
  };

  const handleRestoreLayout = async (slotId: string) => {
    setLayoutSaveError(null);
    setLayoutSaveMessage(null);
    try {
      if (storageMode === 'local') {
        const snapshot = await restoreLocalLayout(slotId);
        if (!snapshot) {
          throw new Error('Snapshot not found');
        }
        const normalized = normalizeLayoutMap(snapshot.layout, snapshot.cols ?? null);
        setLayoutSnapshot({
          ...snapshot,
          layout: normalized.layout,
          cols: normalized.cols,
        });
        setLayoutSaveMessage('레이아웃 불러오기 완료');
        return;
      }

      await restoreServerLayout(slotId);
      setLayoutSaveMessage('레이아웃 불러오기 완료');
      await loadLayoutSnapshot();
    } catch (error) {
      console.error('Layout restore failed', error);
      setLayoutSaveError('레이아웃 불러오기 실패');
    }
  };

  const handleDeleteLayout = async (slotId: string) => {
    try {
      if (storageMode === 'local') {
        await deleteLocalLayout(slotId);
      } else {
        await deleteServerLayout(slotId);
      }
      await fetchLayoutSlots();
    } catch (error) {
      console.error('Layout delete failed', error);
      setLayoutSaveError('레이아웃 삭제 실패');
    }
  };

  const updateWidget = useCallback((key: string, updates: Partial<LayoutEntry>) => {
    setLayoutSnapshot((prev) => {
      if (!prev) return null;
      const nextLayout = { ...prev.layout };
      if (nextLayout[key]) {
        nextLayout[key] = { ...nextLayout[key], ...updates };
      }
      return { ...prev, layout: nextLayout };
    });
  }, []);

  const deleteWidget = useCallback((key: string) => {
    setLayoutSnapshot((prev) => {
      if (!prev) return null;
      const nextLayout = { ...prev.layout };
      delete nextLayout[key];
      return { ...prev, layout: nextLayout };
    });
  }, []);

  const addWidget = useCallback((type: string, title?: string) => {
    const newKey = `${type}-${Date.now()}`;
    const defaults = resolveDefaultWidgetSpec(type, DEFAULT_DASHBOARD_ITEMS);

    setLayoutSnapshot((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        layout: {
          ...prev.layout,
          [newKey]: {
            x: 0,
            y: 0,
            width: defaults.width,
            height: defaults.height,
            type: type as LayoutEntry['type'],
            title: title ?? defaults.title,
          },
        },
      };
    });
  }, []);

  const applyPreset = useCallback((presetId: LayoutPresetId) => {
    const preset = getPresetById(presetId);
    if (!preset) {
      console.error(`Preset not found: ${presetId}`);
      return;
    }

    setLayoutSnapshot((prev) => ({
      layout: preset.layout,
      cols: String(CURRENT_LAYOUT_COLS),
      version: CURRENT_LAYOUT_VERSION,
      updated_at: prev?.updated_at,
    }));
    setLayoutSaveMessage(`프리셋 '${preset.name}' 적용`);
  }, []);

  useLayoutViewModelEffects({ loadLayoutSnapshot });

  return {
    layoutSnapshot,
    layoutSlots,
    layoutActiveId,
    layoutEditing,
    layoutLoadError,
    layoutSaveMessage,
    layoutSaveError,
    storageMode,
    setLayoutEditing,
    setStorageMode,
    loadLayoutSnapshot,
    handleSaveLayout,
    handleRestoreLayout,
    handleDeleteLayout,
    applyPreset,
    updateWidget,
    deleteWidget,
    addWidget,
    fetchLayoutSlots,
    readLegacyLayoutSnapshot,
  };
};
