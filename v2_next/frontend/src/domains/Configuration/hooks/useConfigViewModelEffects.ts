import { useEffect } from 'react';
import type { MutableRefObject } from 'react';
import { configService } from '../api/configService';
import type { ConfigSnapshot } from '../types';

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
  useEffect(() => {
    if (!settingsOpen) return;

    void loadSettings();
    void fetchCentralStatus();

    const poll = async () => {
      if (settingsLoading) return;
      try {
        const data = await configService.getConfig();
        const fingerprint = buildSettingsFingerprint(data);
        if (!settingsFingerprintRef.current) {
          settingsFingerprintRef.current = fingerprint;
          return;
        }
        if (fingerprint === settingsFingerprintRef.current) return;

        if (hasSettingsChanges) {
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

    const interval = window.setInterval(poll, 5000);
    return () => window.clearInterval(interval);
  }, [settingsOpen, loadSettings]);
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
