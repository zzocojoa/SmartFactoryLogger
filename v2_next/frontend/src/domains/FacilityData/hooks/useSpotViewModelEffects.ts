import { useEffect } from 'react';
import type { MutableRefObject } from 'react';
import type { SpotConfig } from '../../../shared/types';
import {
  clearDashboardLeaderLock,
  readDashboardLeaderLock,
  readOrCreateDashboardTabId,
  writeDashboardLeaderLock,
} from '../../../shared/utils/dashboardPollingLeader';

const SPOT_CONFIG_TAB_ID_KEY = 'spot_config_tab_id_v1';
const SPOT_CONFIG_LEADER_KEY = 'spot_config_leader_v1';
const SPOT_CONFIG_BROADCAST_KEY = 'spot_config_broadcast_v1';
const SPOT_CONFIG_BROADCAST_CHANNEL = 'smartfactory-spot-config';
const SPOT_CONFIG_LEADER_HEARTBEAT_MS = 4000;
const SPOT_CONFIG_TAKEOVER_MS = 30000;

interface SpotConfigBroadcastPayload {
  tab_id: string;
  config: SpotConfig;
  sent_at: number;
}

interface UseSpotViewModelEffectsParams {
  config: SpotConfig | null;
  fetchInitialImage: () => Promise<void>;
  loadConfig: () => Promise<SpotConfig | null>;
  applySpotConfig: (config: SpotConfig) => void;
  prevUrlRef: MutableRefObject<string | null>;
  cancelPendingImageRetry: () => void;
  cancelNormalImageRefresh: () => void;
  resumeImageRefreshWhenVisible: () => void;
}

const readStoredSpotConfig = (): SpotConfigBroadcastPayload | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(SPOT_CONFIG_BROADCAST_KEY);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as SpotConfigBroadcastPayload;
  } catch {
    return null;
  }
};

export const useSpotViewModelEffects = ({
  config,
  fetchInitialImage,
  loadConfig,
  applySpotConfig,
  prevUrlRef,
  cancelPendingImageRetry,
  cancelNormalImageRefresh,
  resumeImageRefreshWhenVisible,
}: UseSpotViewModelEffectsParams) => {
  useEffect(() => {
    if (!config || !config.image_url) {
      return;
    }
    void fetchInitialImage();

    return () => {
      cancelPendingImageRetry();
      cancelNormalImageRefresh();
      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current);
        prevUrlRef.current = null;
      }
    };
  }, [
    config?.image_url,
    fetchInitialImage,
    prevUrlRef,
    cancelPendingImageRetry,
    cancelNormalImageRefresh,
  ]);

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    const handleImageVisibility = (): void => {
      if (document.visibilityState === 'hidden') {
        cancelNormalImageRefresh();
        return;
      }
      resumeImageRefreshWhenVisible();
    };

    document.addEventListener('visibilitychange', handleImageVisibility);
    return () => {
      document.removeEventListener('visibilitychange', handleImageVisibility);
    };
  }, [cancelNormalImageRefresh, resumeImageRefreshWhenVisible]);

  useEffect(() => {
    let disposed = false;
    let heartbeatTimerId: number | null = null;
    let channel: BroadcastChannel | null = null;
    const tabId = readOrCreateDashboardTabId(SPOT_CONFIG_TAB_ID_KEY);
    let leaderMode: 'leader' | 'follower' | 'recovering' | 'standalone' =
      typeof window === 'undefined' ? 'standalone' : 'recovering';

    const isLeader = (): boolean => leaderMode === 'leader' || leaderMode === 'standalone';

    const applyBroadcast = (payload: SpotConfigBroadcastPayload): void => {
      if (payload.tab_id === tabId || isLeader()) {
        return;
      }
      applySpotConfig(payload.config);
      leaderMode = 'follower';
    };

    const applyStoredBroadcast = (): void => {
      const payload = readStoredSpotConfig();
      if (!payload) {
        return;
      }
      applyBroadcast(payload);
    };

    const broadcastConfig = (nextConfig: SpotConfig): void => {
      if (typeof window === 'undefined') {
        return;
      }
      const payload: SpotConfigBroadcastPayload = {
        tab_id: tabId,
        config: nextConfig,
        sent_at: Date.now(),
      };
      try {
        channel?.postMessage(payload);
      } catch {
        // Config sync can race with effect cleanup in React StrictMode.
      }
      window.localStorage.setItem(SPOT_CONFIG_BROADCAST_KEY, JSON.stringify(payload));
      leaderMode = leaderMode === 'standalone' ? 'standalone' : 'leader';
    };

    const syncLeaderConfig = async (): Promise<void> => {
      if (disposed || !isLeader()) {
        return;
      }
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        return;
      }
      const nextConfig = await loadConfig();
      if (!nextConfig) {
        return;
      }
      applySpotConfig(nextConfig);
      broadcastConfig(nextConfig);
    };

    const reconcileLeadership = (): void => {
      if (typeof window === 'undefined' || typeof document === 'undefined') {
        leaderMode = 'standalone';
        void syncLeaderConfig();
        return;
      }

      if (document.visibilityState === 'hidden') {
        clearDashboardLeaderLock(SPOT_CONFIG_LEADER_KEY, tabId);
        leaderMode = 'follower';
        applyStoredBroadcast();
        return;
      }

      const now = Date.now();
      const currentLock = readDashboardLeaderLock(SPOT_CONFIG_LEADER_KEY);
      if (!currentLock || currentLock.tab_id === tabId) {
        writeDashboardLeaderLock(SPOT_CONFIG_LEADER_KEY, { tab_id: tabId, updated_at: now });
        leaderMode = 'leader';
        void syncLeaderConfig();
        return;
      }

      const lockAge = now - currentLock.updated_at;
      if (lockAge >= SPOT_CONFIG_TAKEOVER_MS) {
        writeDashboardLeaderLock(SPOT_CONFIG_LEADER_KEY, { tab_id: tabId, updated_at: now });
        leaderMode = 'leader';
        void syncLeaderConfig();
        return;
      }

      leaderMode = 'follower';
      applyStoredBroadcast();
    };

    const handleStorage = (event: StorageEvent): void => {
      if (event.key === SPOT_CONFIG_LEADER_KEY) {
        reconcileLeadership();
        return;
      }
      if (event.key !== SPOT_CONFIG_BROADCAST_KEY || !event.newValue) {
        return;
      }
      try {
        const payload = JSON.parse(event.newValue) as SpotConfigBroadcastPayload;
        applyBroadcast(payload);
      } catch {
        return;
      }
    };

    const handleVisibility = (): void => {
      reconcileLeadership();
    };

    if (typeof BroadcastChannel === 'function') {
      channel = new BroadcastChannel(SPOT_CONFIG_BROADCAST_CHANNEL);
      channel.onmessage = (event: MessageEvent<SpotConfigBroadcastPayload>) => {
        if (!event.data) {
          return;
        }
        applyBroadcast(event.data);
      };
    }

    if (typeof window !== 'undefined') {
      window.addEventListener('storage', handleStorage);
      heartbeatTimerId = window.setInterval(() => {
        if (isLeader()) {
          writeDashboardLeaderLock(SPOT_CONFIG_LEADER_KEY, { tab_id: tabId, updated_at: Date.now() });
          void syncLeaderConfig();
          return;
        }
        reconcileLeadership();
      }, SPOT_CONFIG_LEADER_HEARTBEAT_MS);
    }

    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibility);
    }

    reconcileLeadership();

    return () => {
      disposed = true;
      if (heartbeatTimerId !== null) {
        window.clearInterval(heartbeatTimerId);
      }
      if (typeof window !== 'undefined') {
        window.removeEventListener('storage', handleStorage);
      }
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', handleVisibility);
      }
      if (channel) {
        channel.close();
      }
      clearDashboardLeaderLock(SPOT_CONFIG_LEADER_KEY, tabId);
    };
  }, [applySpotConfig, loadConfig]);
};
