export interface DashboardPollingLeaderLock {
  tab_id: string;
  updated_at: number;
}

export interface DashboardPollingLeaderState {
  tab_id: string;
  mode: 'leader' | 'follower' | 'recovering' | 'standalone';
  leader_tab_id: string | null;
  last_broadcast_at: number | null;
}

const buildTabId = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `dashboard-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

export const readOrCreateDashboardTabId = (storageKey: string): string => {
  if (typeof window === 'undefined') {
    return buildTabId();
  }
  const stored = window.sessionStorage.getItem(storageKey);
  if (stored) {
    return stored;
  }
  const nextTabId = buildTabId();
  window.sessionStorage.setItem(storageKey, nextTabId);
  return nextTabId;
};

export const readDashboardLeaderLock = (storageKey: string): DashboardPollingLeaderLock | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as DashboardPollingLeaderLock;
  } catch {
    return null;
  }
};

export const writeDashboardLeaderLock = (
  storageKey: string,
  payload: DashboardPollingLeaderLock
): void => {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(storageKey, JSON.stringify(payload));
};

export const clearDashboardLeaderLock = (storageKey: string, tabId: string): void => {
  if (typeof window === 'undefined') {
    return;
  }
  const currentLock = readDashboardLeaderLock(storageKey);
  if (currentLock?.tab_id !== tabId) {
    return;
  }
  window.localStorage.removeItem(storageKey);
};
