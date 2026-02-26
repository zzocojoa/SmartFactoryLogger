import { useState, useCallback } from 'react';

export interface UseObservabilityHandlersOptions {
  fetchHealth: () => Promise<any>;
  fetchStats: () => Promise<any>;
  exportObservability: (includeFrontendLogs?: boolean) => Promise<string | null>;
  clearObservabilityErrors: () => Promise<void>;
  openExportFile: () => Promise<void>;
  openExportFolder: () => Promise<void>;
  lastExportPath: string | null;
  modal: any;
  pushNotification: (title: string, message: string, level: 'info' | 'warn' | 'error') => void;
}

export function useObservabilityHandlers({
  fetchHealth,
  fetchStats,
  exportObservability,
  clearObservabilityErrors,
  openExportFile,
  openExportFolder,
  lastExportPath,
  modal,
  pushNotification,
}: UseObservabilityHandlersOptions) {
  const [diagnosisBusy, setDiagnosisBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);

  const formatOptionalNumber = (val: any) => (val != null ? val : 'n/a');
  const formatTimeFromSec = (sec: any) =>
    sec ? new Date(sec * 1000).toLocaleTimeString() : 'n/a';

  const handleDiagnosis = async () => {
    if (diagnosisBusy) return;
    setDiagnosisBusy(true);
    try {
      const [snapshot, statsSnapshot] = await Promise.all([fetchHealth(), fetchStats()]);
      if (!snapshot) {
        throw new Error('Health check failed');
      }
      const lastUpdate = snapshot.last_update
        ? new Date(snapshot.last_update * 1000).toLocaleString()
        : 'n/a';
      const windowStats = statsSnapshot?.window;
      const errorSummary = statsSnapshot?.errors;
      const windowLine = windowStats
        ? `Window ${windowStats.window_sec}s: req ${windowStats.request_count}, err ${windowStats.error_count}, p95 ${formatOptionalNumber(windowStats.p95_latency_ms)}ms`
        : 'Window: n/a';
      const errorLine = errorSummary
        ? `ErrorQ ${errorSummary.queue_size}, Last ${formatTimeFromSec(errorSummary.last_error_at)}`
        : 'ErrorQ: n/a';
      const detail = [
        `Mode: ${snapshot.mode}`,
        `Driver: ${snapshot.driver_connected ? 'OK' : 'Down'}`,
        `Thread: ${snapshot.thread_alive ? 'Alive' : 'Stopped'}`,
        `Last Update: ${lastUpdate}`,
        windowLine,
        errorLine,
      ].join('\n');
      await modal.alert(detail);
    } catch (error) {
      console.error('Diagnosis failed', error);
      await modal.alert('Diagnosis failed.');
    } finally {
      setDiagnosisBusy(false);
    }
  };

  const handleExportObservability = async () => {
    if (exportBusy) return;
    setExportBusy(true);
    try {
      const path = await exportObservability(true);
      if (!path) {
        throw new Error('Export path missing');
      }
      await modal.alert(`지표 내보내기 완료:\n${path}`);
    } catch (error) {
      console.error('Observability export failed', error);
      await modal.alert('지표 내보내기 실패.');
    } finally {
      setExportBusy(false);
    }
  };

  const handleOpenObservabilityExportFile = async () => {
    if (!lastExportPath) return;
    try {
      await openExportFile();
    } catch (error) {
      console.error('Open export file failed', error);
      await modal.alert('내보낸 파일 열기 실패.');
    }
  };

  const handleOpenObservabilityExportFolder = async () => {
    if (!lastExportPath) return;
    try {
      await openExportFolder();
    } catch (error) {
      console.error('Open export folder failed', error);
      await modal.alert('내보낸 폴더 열기 실패.');
    }
  };

  const handleCopyObservabilityExportPath = async () => {
    if (!lastExportPath) return;
    try {
      await navigator.clipboard.writeText(lastExportPath);
      await modal.alert('내보낸 경로를 복사했습니다.');
    } catch (error) {
      console.error('Copy export path failed', error);
      await modal.alert('경로 복사 실패');
    }
  };

  const handleClearObservabilityErrors = async () => {
    if (!(await modal.confirm('에러 큐를 비우면 복구할 수 없습니다. 비우시겠습니까?'))) {
      return;
    }
    try {
      await clearObservabilityErrors();
    } catch (error) {
      console.error('Observability clear failed', error);
      await modal.alert('에러 큐 비우기 실패.');
    }
  };

  return {
    diagnosisBusy,
    exportBusy,
    handleDiagnosis,
    handleExportObservability,
    handleOpenObservabilityExportFile,
    handleOpenObservabilityExportFolder,
    handleCopyObservabilityExportPath,
    handleClearObservabilityErrors,
  };
}
