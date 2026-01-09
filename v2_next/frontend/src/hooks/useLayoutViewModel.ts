import { useState, useCallback, useEffect, useRef } from 'react';
import { layoutService, localLayoutService } from '../api/layoutService';
import {
  LayoutSnapshot,
  LayoutSlotSummary,
  LayoutMap,
  LayoutSlotsResponse,
  LayoutEntry
} from '../types';
import { DEFAULT_DASHBOARD_ITEMS } from '../scenes/DashboardScene';
import {
  buildLayoutMapFromArray,
  buildLayoutMapFromObject,
  normalizeLayoutMap
} from '../utils/layoutUtils';
import {
  LAYOUT_STORAGE_KEY,
  LAYOUT_BACKUP_KEY,
  CURRENT_LAYOUT_COLS,
  StorageMode
} from '../constants/logic';
import { LayoutPresetId, getPresetById } from '../constants/layoutPresets';

const LAYOUT_COLS_KEY = 'grafana_scene_layout_cols';
const CURRENT_LAYOUT_VERSION = 'v2';

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
  updateWidget: (key: string, updates: Partial<LayoutEntry>) => void;
  deleteWidget: (key: string) => void;
  addWidget: (type: string, title?: string) => void;
  fetchLayoutSlots: () => Promise<void>;
  readLegacyLayoutSnapshot: () => LayoutSnapshot | null;
}

export const useLayoutViewModel = (): UseLayoutViewModel => {
  const [layoutEditing, setLayoutEditing] = useState(false);
  const [layoutSnapshot, setLayoutSnapshot] = useState<LayoutSnapshot | null>(null);
  const [layoutSlots, setLayoutSlots] = useState<LayoutSlotSummary[]>([]);
  const [layoutActiveId, setLayoutActiveId] = useState<string | null>(null);
  const [layoutLoadError, setLayoutLoadError] = useState<string | null>(null);
  
  const [layoutSaveMessage, setLayoutSaveMessage] = useState<string | null>(null);
  const [layoutSaveError, setLayoutSaveError] = useState<string | null>(null);
  
  // Storage mode: 'local' (browser localStorage) or 'server' (API)
  const [storageMode, setStorageModeState] = useState<StorageMode>(() => localLayoutService.getStorageMode());
  
  const setStorageMode = useCallback((mode: StorageMode) => {
    setStorageModeState(mode);
    localLayoutService.setStorageMode(mode);
  }, []);

  // Helper: Read Legacy
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
      const cols = localStorage.getItem(LAYOUT_COLS_KEY);
      return {
        layout,
        cols,
        version: 'v1',
      };
    } catch (error) {
      console.error('Legacy layout parse failed', error);
      return null;
    }
  }, []);

  // Helper: Migrate Legacy
  const migrateLegacyLayout = useCallback(async () => {
    const legacy = readLegacyLayoutSnapshot();
    if (!legacy) {
      return null;
    }
    const normalized = normalizeLayoutMap(legacy.layout, legacy.cols ?? null);
    const payload = {
      name: '이전 레이아웃',
      layout: normalized.layout,
      cols: normalized.cols ?? CURRENT_LAYOUT_COLS,
      version: CURRENT_LAYOUT_VERSION,
    };
    try {
      const data = await layoutService.saveLayout(payload);
      localStorage.removeItem(LAYOUT_STORAGE_KEY);
      localStorage.removeItem(LAYOUT_COLS_KEY);
      localStorage.removeItem(LAYOUT_BACKUP_KEY);
      return {
        layout: payload.layout,
        cols: payload.cols,
        version: payload.version,
        updated_at: data?.updated_at ?? null,
      } as LayoutSnapshot;
    } catch (error) {
      console.error('Legacy layout migration failed', error);
      return {
        layout: payload.layout,
        cols: payload.cols,
        version: payload.version,
      } as LayoutSnapshot;
    }
  }, [readLegacyLayoutSnapshot]);

  const fetchLayoutSlots = useCallback(async () => {
    try {
      if (storageMode === 'local') {
          const slots = await localLayoutService.getLayoutList();
          // Map local slots to match server slot structure if needed
          // The local list API returns { id, name, updated_at } which is sufficient
          setLayoutSlots(slots);
          setLayoutActiveId(null); // Local mode doesn't track "active slot ID" persistantly in the same way
      } else {
          const data = await layoutService.getLayouts();
          setLayoutSlots(data?.slots ?? []);
          setLayoutActiveId(data?.active_id ?? null);
      }
    } catch (error) {
      console.error('Layout slots load failed', error);
      setLayoutSlots([]);
      setLayoutActiveId(null);
    }
  }, [storageMode]);

  const loadLayoutSnapshot = useCallback(async () => {
    setLayoutLoadError(null);
    
    // In local mode, try local storage first
    if (storageMode === 'local') {
      const localSnapshot = await localLayoutService.getLocalLayout();
      if (localSnapshot && localSnapshot.layout) {
        const normalized = normalizeLayoutMap(localSnapshot.layout, localSnapshot.cols ?? null);
        setLayoutSnapshot({
          ...localSnapshot,
          layout: normalized.layout,
          cols: normalized.cols,
        });
        // Still fetch server slots for reference (but don't apply them)
        await fetchLayoutSlots();
        return;
      }
    }
    
    // Server mode or no local layout found
    try {
      const snapshot = await layoutService.getLayoutSnapshot();
      if (snapshot && snapshot.layout) {
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
        setLayoutLoadError('레이아웃 로드 실패');
      }
    } finally {
      await fetchLayoutSlots();
    }
  }, [storageMode, fetchLayoutSlots, migrateLegacyLayout]);

  const handleSaveLayout = async (name: string, newLayout?: LayoutMap) => {
    const layoutToSave = newLayout ?? layoutSnapshot?.layout;
    if (!layoutToSave) return;

    setLayoutSaveError(null);
    setLayoutSaveMessage(null);
    
    try {
      const cols = layoutSnapshot?.cols ?? CURRENT_LAYOUT_COLS;
      
      if (storageMode === 'local') {
        // Save to server via client API
        const colsNum = typeof cols === 'string' ? parseInt(cols, 10) : cols;
        const success = await localLayoutService.saveLocalLayout(layoutToSave, name, colsNum);
        
        if (success) {
          setLayoutSnapshot((prev) => prev ? { ...prev, layout: layoutToSave } : {
            layout: layoutToSave,
            cols: CURRENT_LAYOUT_COLS.toString(),
            version: CURRENT_LAYOUT_VERSION,
          });
          
          setLayoutSaveMessage(`레이아웃 '${name}' 저장 완료 (이 PC)`);
          await fetchLayoutSlots();
        } else {
          throw new Error('Failed to save client layout');
        }
      } else {
        // Save to server
        const payload = {
          name,
          layout: layoutToSave,
          cols,
          version: layoutSnapshot?.version ?? CURRENT_LAYOUT_VERSION
        };
        await layoutService.saveLayout(payload);

        setLayoutSnapshot((prev) => prev ? { ...prev, layout: layoutToSave } : {
          layout: layoutToSave,
          cols: CURRENT_LAYOUT_COLS.toString(),
          version: CURRENT_LAYOUT_VERSION,
        });

        setLayoutSaveMessage(`레이아웃 '${name}' 서버 저장 완료`);
        await fetchLayoutSlots();
      }
    } catch (err) {
      console.error('Layout save failed', err);
      setLayoutSaveError('레이아웃 저장 실패');
    }
  };

  const handleRestoreLayout = async (slotId: string) => {
      setLayoutSaveError(null);
      setLayoutSaveMessage(null);
      try {
          if (storageMode === 'local') {
              const snapshot = await localLayoutService.restoreLocalLayout(slotId);
              if (snapshot) {
                  // Apply restored layout
                   const normalized = normalizeLayoutMap(snapshot.layout, snapshot.cols ?? null);
                    setLayoutSnapshot({
                        ...snapshot,
                        layout: normalized.layout,
                        cols: normalized.cols,
                    });
                  setLayoutSaveMessage('레이아웃 불러오기 완료');
              } else {
                  throw new Error('Snapshot not found');
              }
          } else {
            await layoutService.restoreLayout(slotId);
            setLayoutSaveMessage('레이아웃 불러오기 완료');
            await loadLayoutSnapshot(); // Reload active
          }
      } catch (err) {
          console.error('Layout restore failed', err);
          setLayoutSaveError('레이아웃 불러오기 실패');
      }
  };

  const handleDeleteLayout = async (slotId: string) => {
      try {
          if (storageMode === 'local') {
              await localLayoutService.deleteLocalLayout(slotId);
          } else {
              await layoutService.deleteLayout(slotId);
          }
          await fetchLayoutSlots();
      } catch (err) {
          console.error('Layout delete failed', err);
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
      return {
        ...prev,
        layout: nextLayout
      };
    });
  }, []);

  const deleteWidget = useCallback((key: string) => {
    setLayoutSnapshot((prev) => {
      if (!prev) return null;
      const nextLayout = { ...prev.layout };
      delete nextLayout[key];
      return {
        ...prev,
        layout: nextLayout
      };
    });
  }, []);

  const addWidget = useCallback((type: string, title?: string) => {
    const newKey = `${type}-${Date.now()}`;
    // Find default properties if available
    const defaultItem = DEFAULT_DASHBOARD_ITEMS.find(item => item.key === type);
    const defaultTitle = defaultItem?.title ?? (type === 'markdown' ? 'New Memo' : '새 위젯');
    const defaultWidth = defaultItem?.width ?? 20;
    const defaultHeight = defaultItem?.height ?? 6;

    setLayoutSnapshot((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        layout: {
          ...prev.layout,
          [newKey]: {
            x: 0,
            y: 0,
            width: defaultWidth,
            height: defaultHeight,
            type: type as LayoutEntry['type'],
            title: title ?? defaultTitle,
          },
        },
      };
    });
  }, []);

  // Apply a preset layout
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
    
    setLayoutSaveMessage(`프리셋 '${preset.name}' 적용됨`);
    console.log(`[Layout] Applied preset: ${preset.name}`);
  }, []);

  // Initial Load
  useEffect(() => {
    loadLayoutSnapshot();
  }, [loadLayoutSnapshot]);

  // Refresh slots on specific triggers if needed (handled by actions mostly)
  
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
    readLegacyLayoutSnapshot
  };
};
