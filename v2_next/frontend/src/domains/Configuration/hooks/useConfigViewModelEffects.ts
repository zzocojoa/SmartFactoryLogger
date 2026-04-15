import { useEffect, useRef } from 'react';
import type { MutableRefObject } from 'react';
import { configService } from '../api/configService';
import type { ConfigSnapshot } from '../types';

const CONFIG_AUTO_REFRESH_MS = 15000;

interface UseConfigAutoRefreshEffectParams {
  settingsOpen: boolean;
  settingsLoading: boolean;
  loadSettings: () => Promise<void>;
  fetchCentralStatus: () => Promise<void>;
  hasSettingsChanges: boolean;
  buildSettingsFingerprint: (snapshot: ConfigSnapshot) => string;
  applySettingsSnapshot: (snapshot: ConfigSnapshot) => void;
  showSettingsToast: (message: string, level: 'ok' | 'warn' | 'error') => void;
  settingsFingerprintRef: MutableRefObject<string | null>;
  settingsExternalNotifyRef: MutableRefObject<string | null>;
  setExternalConfigPending: (value: ConfigSnapshot | null) => void;
  setExternalConfigPendingAt: (value: number | null) => void;
}

export const useConfigAutoRefreshEffect = ({
  settingsOpen,
  settingsLoading,
  loadSettings,
  fetchCentralStatus,
  hasSettingsChanges,
  buildSettingsFingerprint,
  applySettingsSnapshot,
  showSettingsToast,
  settingsFingerprintRef,
  settingsExternalNotifyRef,
  setExternalConfigPending,
  setExternalConfigPendingAt,
}: UseConfigAutoRefreshEffectParams) => {
  const settingsLoadingRef = useRef(settingsLoading);
  const hasSettingsChangesRef = useRef(hasSettingsChanges);

  useEffect(() => {
    settingsLoadingRef.current = settingsLoading;
  }, [settingsLoading]);

  useEffect(() => {
    hasSettingsChangesRef.current = hasSettingsChanges;
  }, [hasSettingsChanges]);

  useEffect(() => {
    if (!settingsOpen) return;

    let disposed = false;

    const isVisible = (): boolean =>
      typeof document === 'undefined' || document.visibilityState === 'visible';

    const loadInitialState = async (): Promise<void> => {
      if (disposed) {
        return;
      }
      await loadSettings();
      if (!isVisible()) {
        return;
      }
      await fetchCentralStatus();
    };

    const poll = async () => {
      if (disposed || settingsLoadingRef.current || !isVisible()) return;
      try {
        const data = await configService.getConfig();
        const fingerprint = buildSettingsFingerprint(data);
        if (!settingsFingerprintRef.current) {
          settingsFingerprintRef.current = fingerprint;
          return;
        }
        if (fingerprint === settingsFingerprintRef.current) return;

        if (hasSettingsChangesRef.current) {
          if (settingsExternalNotifyRef.current !== fingerprint) {
            showSettingsToast('?ㅼ젙 ?뚯씪???몃??먯꽌 蹂寃쎈릺?덉뒿?덈떎. (媛깆떊 蹂대쪟)', 'warn');
            settingsExternalNotifyRef.current = fingerprint;
            setExternalConfigPending(data);
            setExternalConfigPendingAt(Date.now());
          }
          return;
        }

        applySettingsSnapshot(data);
        settingsFingerprintRef.current = fingerprint;
        settingsExternalNotifyRef.current = null;
        setExternalConfigPending(null);
        setExternalConfigPendingAt(null);
      } catch (error) {
        console.error('Settings auto-refresh failed', error);
      }
    };

    const handleVisibility = (): void => {
      if (!isVisible()) {
        return;
      }
      void fetchCentralStatus();
      if (!hasSettingsChangesRef.current) {
        void poll();
      }
    };

    void loadInitialState();

    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibility);
    }

    const interval = window.setInterval(() => {
      void poll();
    }, CONFIG_AUTO_REFRESH_MS);

    return () => {
      disposed = true;
      window.clearInterval(interval);
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', handleVisibility);
      }
    };
  }, [
    settingsOpen,
    loadSettings,
    fetchCentralStatus,
    buildSettingsFingerprint,
    applySettingsSnapshot,
    showSettingsToast,
    settingsFingerprintRef,
    settingsExternalNotifyRef,
    setExternalConfigPending,
    setExternalConfigPendingAt,
  ]);
};

interface UseConfigInfoAutoDismissEffectParams {
  settingsInfo: string | null;
  setSettingsInfo: (value: string | null) => void;
}

export const useConfigInfoAutoDismissEffect = ({
  settingsInfo,
  setSettingsInfo,
}: UseConfigInfoAutoDismissEffectParams) => {
  useEffect(() => {
    if (!settingsInfo) return;
    const timer = setTimeout(() => {
      setSettingsInfo(null);
    }, 3000);
    return () => clearTimeout(timer);
  }, [settingsInfo, setSettingsInfo]);
};
