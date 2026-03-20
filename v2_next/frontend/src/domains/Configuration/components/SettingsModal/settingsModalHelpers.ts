/**
 * Settings Modal UI helpers - extracted from App.tsx (Phase 12)
 * Pure functions for badge/label formatting in the settings modal.
 */
import type { ConnectionTestResult, PathHealthResult, CentralSyncResult } from '../../../../shared/types';
import { formatTime } from '../../../../shared/utils/formatters';

// ─── Connection Test Badges ───────────────────────────────────────

export const getTestBadge = (result?: ConnectionTestResult) => {
  if (!result) {
    return { label: '미실행', className: 'idle' };
  }
  return result.ok
    ? { label: '성공', className: 'ok' }
    : { label: '실패', className: 'error' };
};

export const formatTestTime = (result?: ConnectionTestResult) => {
  if (!result) {
    return '미실행';
  }
  return new Date(result.tested_at).toLocaleTimeString();
};

// ─── Path Health Badges ───────────────────────────────────────────

export const getPathBadge = (result?: PathHealthResult) => {
  if (!result) {
    return { label: '미검사', className: 'idle' };
  }
  if (result.status === 'OK') {
    return { label: '정상', className: 'ok' };
  }
  if (result.status === 'WARN') {
    return { label: '경고', className: 'warn' };
  }
  if (result.status === 'ERROR') {
    return { label: '오류', className: 'error' };
  }
  return { label: '미확인', className: 'idle' };
};

export const formatPathCheckTime = (result?: PathHealthResult) => {
  if (!result?.checked_at) {
    return '미검사';
  }
  return new Date(result.checked_at).toLocaleTimeString();
};

export const formatPathMessage = (result?: PathHealthResult) => {
  if (!result) {
    return '경로 상태를 확인하세요.';
  }
  const map: Record<string, string> = {
    'Path not found (creatable)': '경로 없음(생성 가능)',
    'Not a directory': '디렉터리가 아님',
    'Write permission denied': '쓰기 권한 없음',
    'Invalid path format': '경로 형식이 올바르지 않습니다.',
    'Network drive unavailable': '네트워크 드라이브가 연결되어 있지 않습니다.',
    'Network path latency': '네트워크 경로 지연',
    OK: '정상',
  };
  return map[result.message] ?? result.message;
};

// ─── Central Sync Badges ──────────────────────────────────────────

export const getCentralBadge = (status?: string, configured?: boolean) => {
  if (configured === false) {
    return { label: '미설정', className: 'idle' };
  }
  if (configured === undefined) {
    return { label: '확인 중', className: 'idle' };
  }
  if (!status) {
    return { label: '미확인', className: 'idle' };
  }
  if (status === 'APPLIED') {
    return { label: '적용', className: 'ok' };
  }
  if (status === 'NO_CHANGE') {
    return { label: '변경 없음', className: 'ok' };
  }
  if (status === 'SKIPPED') {
    return { label: '보류', className: 'warn' };
  }
  if (status === 'FAILED') {
    return { label: '실패', className: 'error' };
  }
  if (status === 'DISABLED') {
    return { label: '미설정', className: 'idle' };
  }
  return { label: status, className: 'idle' };
};

export const formatCentralTime = (result?: CentralSyncResult) => {
  if (!result?.at) {
    return '미실행';
  }
  return formatTime(result.at * 1000);
};
