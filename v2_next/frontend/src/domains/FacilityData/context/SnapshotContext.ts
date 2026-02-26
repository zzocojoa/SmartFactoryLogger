/**
 * SnapshotContext: 대시보드 및 위젯 스냅샷 캡처 기능을 관리하는 Context
 */
import React from 'react';

export type SnapshotContextValue = {
  handleSnapshot: () => void;
  snapshotLoading: boolean;
};

export const SnapshotContext = React.createContext<SnapshotContextValue>({
  handleSnapshot: () => undefined,
  snapshotLoading: false,
});
