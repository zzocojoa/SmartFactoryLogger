import { useState, useCallback, useEffect, useRef } from 'react';
import { layoutService } from '../api/layoutService';
import {
  LayoutSnapshot,
  LayoutSlotSummary,
  LayoutMap,
  LayoutSlotsResponse,
  LayoutEntry
} from '../types';
import {
  buildLayoutMapFromArray,
  buildLayoutMapFromObject,
  normalizeLayoutMap
} from '../utils/layoutUtils';
import {
  LAYOUT_STORAGE_KEY,
  LAYOUT_BACKUP_KEY,
  CURRENT_LAYOUT_COLS
} from '../constants/logic';

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

  setLayoutEditing: (editing: boolean) => void;
  loadLayoutSnapshot: () => Promise<void>;
  handleSaveLayout: (name: string, newLayout?: LayoutMap) => Promise<void>;
  handleRestoreLayout: (slotId: string) => Promise<void>;
  handleDeleteLayout: (slotId: string) => Promise<void>;
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
      const data = await layoutService.getLayouts();
      setLayoutSlots(data?.slots ?? []);
      setLayoutActiveId(data?.active_id ?? null);
    } catch (error) {
      console.error('Layout slots load failed', error);
      setLayoutSlots([]);
      setLayoutActiveId(null);
    }
  }, []);

  const loadLayoutSnapshot = useCallback(async () => {
    setLayoutLoadError(null);
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
  }, [fetchLayoutSlots, migrateLegacyLayout]);

  const handleSaveLayout = async (name: string, newLayout?: LayoutMap) => {
    const layoutToSave = newLayout ?? layoutSnapshot?.layout;
    if (!layoutToSave) return;

    setLayoutSaveError(null);
    setLayoutSaveMessage(null);
    
    try {
        const payload = {
            name,
            layout: layoutToSave,
            cols: layoutSnapshot?.cols ?? CURRENT_LAYOUT_COLS,
            version: layoutSnapshot?.version ?? CURRENT_LAYOUT_VERSION
        };
        await layoutService.saveLayout(payload);

        // Update local snapshot so the UI/model are in sync with what was just saved
        setLayoutSnapshot((prev) => prev ? { ...prev, layout: layoutToSave } : {
             layout: layoutToSave,
             cols: CURRENT_LAYOUT_COLS.toString(),
             version: CURRENT_LAYOUT_VERSION,
        });

        setLayoutSaveMessage(`레이아웃 '${name}' 저장 완료`);
        await fetchLayoutSlots();
    } catch (err) {
        console.error('Layout save failed', err);
        setLayoutSaveError('레이아웃 저장 실패');
    }
  };

  const handleRestoreLayout = async (slotId: string) => {
      setLayoutSaveError(null);
      setLayoutSaveMessage(null);
      try {
          await layoutService.restoreLayout(slotId);
          setLayoutSaveMessage('레이아웃 불러오기 완료');
          await loadLayoutSnapshot(); // Reload active
      } catch (err) {
          console.error('Layout restore failed', err);
          setLayoutSaveError('레이아웃 불러오기 실패');
      }
  };

  const handleDeleteLayout = async (slotId: string) => {
      try {
          await layoutService.deleteLayout(slotId);
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
    setLayoutSnapshot((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        layout: {
          ...prev.layout,
          [newKey]: {
            x: 0,
            y: 0,
            width: 20,
            height: 6,
            type: type as LayoutEntry['type'],
            title: title ?? (type === 'markdown' ? 'New Memo' : '새 위젯'),
          },
        },
      };
    });
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
    setLayoutEditing,
    loadLayoutSnapshot,
    handleSaveLayout,
    handleRestoreLayout,
    handleDeleteLayout,
    updateWidget,
    deleteWidget,
    addWidget,
    fetchLayoutSlots,
    readLegacyLayoutSnapshot
  };
};
