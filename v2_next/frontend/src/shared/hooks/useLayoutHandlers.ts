import { useRef } from 'react';
import { LayoutMap, WidgetType } from '../types';

type LayoutSlot = {
  id: string;
  name: string;
};

type ModalApi = {
  prompt: (message: string, defaultValue: string) => Promise<string | null>;
  confirm: (message: string, options: { variant: 'warning' | 'error' }) => Promise<boolean>;
};

export interface UseLayoutHandlersOptions {
  layoutEditing: boolean;
  layoutSlots: LayoutSlot[];
  layoutActiveId: string | null;
  handleSaveLayout: (name: string, layout: LayoutMap) => Promise<void>;
  handleRestoreLayout: (slotId: string) => Promise<void>;
  handleDeleteLayout: (slotId: string) => Promise<void>;
  addWidget: (type: WidgetType) => void;
  deleteWidget: (key: string) => void;
  updateWidget: (key: string, updates: unknown) => void;
  modal: ModalApi;
  pushNotification: (title: string, message: string, level: 'info' | 'warn' | 'error') => void;
  setMenuOpen: (open: boolean) => void;
  setLayoutRestoreError: (err: string | null) => void;
  setLayoutRestoreMessage: (msg: string | null) => void;
  captureCurrentLayout: () => LayoutMap;
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
  captureCurrentLayout,
}: UseLayoutHandlersOptions) {
  const layoutRef = useRef<LayoutMap>({});
  const lastRestoreSlotIdRef = useRef<string | null>(null);
  const restoreMessageTimerRef = useRef<number | null>(null);

  const clearRestoreTimer = () => {
    if (restoreMessageTimerRef.current !== null) {
      window.clearTimeout(restoreMessageTimerRef.current);
      restoreMessageTimerRef.current = null;
    }
  };

  const queueRestoreMessageClear = () => {
    clearRestoreTimer();
    restoreMessageTimerRef.current = window.setTimeout(() => {
      setLayoutRestoreMessage(null);
      restoreMessageTimerRef.current = null;
    }, 2000);
  };

  const saveLayout = async () => {
    if (!layoutEditing) {
      return;
    }

    layoutRef.current = captureCurrentLayout();

    if (Object.keys(layoutRef.current).length === 0) {
      pushNotification('레이아웃 저장', '레이아웃 정보를 찾을 수 없습니다.', 'error');
      return;
    }

    const defaultName =
      layoutSlots.find((slot) => slot.id === layoutActiveId)?.name ??
      `레이아웃 ${Math.min(layoutSlots.length + 1, 3)}`;

    const name = await modal.prompt('레이아웃 이름을 입력하세요.', defaultName);
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
      setLayoutRestoreError('복구 대상이 없습니다.');
      return;
    }

    lastRestoreSlotIdRef.current = targetId;

    const confirmed = await modal.confirm(
      '선택한 레이아웃으로 복구하면 현재 배치가 사라집니다. 복구하시겠습니까?',
      { variant: 'warning' }
    );
    if (!confirmed) {
      return;
    }

    try {
      await handleRestoreLayout(targetId);
      setLayoutRestoreError(null);
      setLayoutRestoreMessage('복구 완료');
      queueRestoreMessageClear();
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
      setLayoutRestoreError('삭제 대상이 없습니다.');
      return;
    }

    const confirmed = await modal.confirm(
      '선택한 레이아웃을 삭제하면 되돌릴 수 없습니다. 삭제하시겠습니까?',
      { variant: 'error' }
    );
    if (!confirmed) {
      return;
    }

    try {
      await handleDeleteLayout(slotId);
      setLayoutRestoreError(null);
      setLayoutRestoreMessage('삭제 완료');
      queueRestoreMessageClear();
    } catch (error) {
      console.error('Layout delete failed', error);
      setLayoutRestoreError('삭제 실패');
    }
  };

  const handleRemoveWidget = (key: string) => {
    deleteWidget(key);
  };

  const handleUpdateWidget = (key: string, updates: unknown) => {
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
