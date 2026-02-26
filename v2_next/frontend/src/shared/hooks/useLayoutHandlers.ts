import { useRef, useCallback } from 'react';
import { WidgetType, LayoutMap } from '../types';

export interface UseLayoutHandlersOptions {
  layoutEditing: boolean;
  layoutSlots: any[];
  layoutActiveId: string | null;
  handleSaveLayout: (name: string, layout: LayoutMap) => Promise<void>;
  handleRestoreLayout: (slotId: string) => Promise<void>;
  handleDeleteLayout: (slotId: string) => Promise<void>;
  addWidget: (type: WidgetType) => void;
  deleteWidget: (key: string) => void;
  updateWidget: (key: string, updates: any) => void;
  modal: any;
  pushNotification: (title: string, message: string, level: 'info' | 'warn' | 'error') => void;
  setMenuOpen: (open: boolean) => void;
  setLayoutRestoreError: (err: string | null) => void;
  setLayoutRestoreMessage: (msg: string | null) => void;
}

export function useLayoutHandlers({
  layoutEditing,
  layoutSlots,
  layoutActiveId,
  handleSaveLayout,
  handleRestoreLayout,
  handleDeleteLayout,
  addWidget,
  deleteWidget,
  updateWidget,
  modal,
  pushNotification,
  setMenuOpen,
  setLayoutRestoreError,
  setLayoutRestoreMessage,
}: UseLayoutHandlersOptions) {
  const layoutRef = useRef<LayoutMap>({});
  const lastRestoreSlotIdRef = useRef<string | null>(null);
  const restoreMessageTimerRef = useRef<number | null>(null);

  const saveLayout = async () => {
    if (!layoutEditing) return;
    
    // Note: The actual layout snapshot retrieval from SceneGridLayout 
    // should happen in App.tsx or we pass the scene/grid here.
    // For simplicity, we'll assume layoutRef is updated via App.tsx effects 
    // or we pass a getter.
    
    if (Object.keys(layoutRef.current).length === 0) {
      pushNotification('레이아웃 저장', '레이아웃 정보를 찾을 수 없습니다.', 'error');
      return;
    }

    const defaultName =
      layoutSlots.find((slot) => slot.id === layoutActiveId)?.name ??
      `레이아웃 ${Math.min(layoutSlots.length + 1, 3)}`;

    const name = await modal.prompt('레이아웃 이름을 입력하세요', defaultName);
    if (!name) {
      pushNotification('레이아웃 저장', '저장이 취소되었습니다.', 'warn');
      return;
    }

    try {
      await handleSaveLayout(name, layoutRef.current);
      pushNotification('레이아웃 저장', `저장 완료: ${name}`, 'info');
    } catch (error) {
      console.error('Layout save failed', error);
      pushNotification('레이아웃 저장 실패', '저장 실패', 'error');
    }
  };

  const restoreLayout = async (slotId?: string | null) => {
    const targetId = slotId ?? lastRestoreSlotIdRef.current;
    if (!targetId) {
      setLayoutRestoreError('복구 대상 없음');
      return;
    }
    lastRestoreSlotIdRef.current = targetId;

    if (!(await modal.confirm('선택한 레이아웃으로 복구하면 현재 배치가 사라집니다. 복구하시겠습니까?', { variant: 'warning' }))) {
      return;
    }

    try {
      await handleRestoreLayout(targetId);
      setLayoutRestoreError(null);
      setLayoutRestoreMessage('복구됨');
      
      if (restoreMessageTimerRef.current !== null) {
        window.clearTimeout(restoreMessageTimerRef.current);
      }
      restoreMessageTimerRef.current = window.setTimeout(() => {
        setLayoutRestoreMessage(null);
        restoreMessageTimerRef.current = null;
      }, 2000);
    } catch (error) {
      console.error('Layout restore failed', error);
      setLayoutRestoreError('복구 실패');
    }
  };

  const handleAddWidget = (type: WidgetType) => {
    addWidget(type);
    setMenuOpen(false);
  };

  const deleteLayoutSlot = async (slotId: string) => {
    if (!slotId) {
      setLayoutRestoreError('삭제 대상 없음');
      return;
    }
    if (!(await modal.confirm('선택한 레이아웃을 삭제하면 되돌릴 수 없습니다. 삭제하시겠습니까?', { variant: 'error' }))) {
      return;
    }
    try {
      await handleDeleteLayout(slotId);
      setLayoutRestoreError(null);
      setLayoutRestoreMessage('삭제됨');
      
      if (restoreMessageTimerRef.current !== null) {
        window.clearTimeout(restoreMessageTimerRef.current);
      }
      restoreMessageTimerRef.current = window.setTimeout(() => {
        setLayoutRestoreMessage(null);
        restoreMessageTimerRef.current = null;
      }, 2000);
    } catch (error) {
      console.error('Layout delete failed', error);
      setLayoutRestoreError('삭제 실패');
    }
  };

  const handleRemoveWidget = (key: string) => {
    deleteWidget(key);
  };

  const handleUpdateWidget = (key: string, updates: any) => {
    updateWidget(key, updates);
  };

  return {
    layoutRef,
    saveLayout,
    restoreLayout,
    handleAddWidget,
    deleteLayoutSlot,
    handleRemoveWidget,
    handleUpdateWidget,
  };
}
