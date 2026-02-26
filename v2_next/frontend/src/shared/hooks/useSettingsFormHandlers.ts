import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { 
  SettingsFormState, 
  ConnectionTargetKey, 
  PathHealthState, 
  PathHealthResult,
  ConfigSnapshot,
  ConnectionTestResult,
  CentralSyncResult
} from '../types';

export interface UseSettingsFormHandlersOptions {
  settingsForm: SettingsFormState | null;
  settingsBaseline: SettingsFormState | null;
  settingsOpen: boolean;
  settingsReady: boolean;
  validationErrors: Record<string, string>;
  isSettingsFieldDirty: (key: keyof SettingsFormState) => boolean;
  updateSettingsField: (key: keyof SettingsFormState, value: any) => void;
  runConnectionTest: (payload: any) => Promise<void>;
  checkPathsHealth: (payload: any) => Promise<any>;
  createPath: (path: string) => Promise<boolean>;
  modal: any;
  setSettingsError: (msg: string | null) => void;
  setPathHealth: React.Dispatch<React.SetStateAction<PathHealthState>>;
  pathHealth: PathHealthState;
}

export function useSettingsFormHandlers({
  settingsForm,
  settingsBaseline,
  settingsOpen,
  settingsReady,
  validationErrors,
  isSettingsFieldDirty,
  updateSettingsField,
  runConnectionTest,
  checkPathsHealth,
  createPath,
  modal,
  setSettingsError,
  setPathHealth,
  pathHealth,
}: UseSettingsFormHandlersOptions) {
  const [connectionTestBusy, setConnectionTestBusy] = useState<Record<string, boolean>>({});
  const [pathCheckBusy, setPathCheckBusy] = useState(false);
  const [activeSettingsSection, setActiveSettingsSection] = useState('settings-summary');
  const settingsScrollRef = useRef<HTMLDivElement>(null);
  const settingsSectionRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const isManualScrollingRef = useRef(false);
  const manualScrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const runPathHealthCheck = useCallback(
    async (paths?: Array<{ key: 'log' | 'snapshot'; path: string }>) => {
      if (!settingsReady || !settingsForm) return;
      
      const now = Date.now();
      const targets = paths ?? [
        { key: 'log', path: settingsForm.logPath },
        { key: 'snapshot', path: settingsForm.snapshotPath },
      ];

      const payload: Array<{ key: string; path: string }> = [];
      const localResults: PathHealthState = {};

      targets.forEach((item) => {
        const trimmed = item.path.trim();
        if (!trimmed) {
          localResults[item.key] = {
            status: 'ERROR',
            exists: false,
            writable: false,
            is_dir: false,
            is_network: false,
            latency_ms: null,
            message: '경로 없음',
            checked_at: now,
          };
          return;
        }
        payload.push({ key: item.key, path: trimmed });
      });

      if (payload.length === 0) {
        setPathHealth((prev) => ({ ...prev, ...localResults }));
        return;
      }

      setPathCheckBusy(true);
      try {
        const data = await checkPathsHealth(payload);
        const results = data?.results ?? {};
        const merged: PathHealthState = { ...localResults };
        Object.entries(results).forEach(([key, val]) => {
          if (key === 'log' || key === 'snapshot') {
            const value = val as PathHealthResult;
            merged[key] = {
              status: value.status ?? 'UNKNOWN',
              exists: Boolean(value.exists),
              writable: Boolean(value.writable),
              is_dir: Boolean(value.is_dir),
              is_network: Boolean(value.is_network),
              latency_ms: value.latency_ms ?? null,
              message: value.message ?? '',
              checked_at: now,
            };
          }
        });
        setPathHealth((prev) => ({ ...prev, ...merged }));
      } catch (error) {
        console.error('Path health check failed', error);
      } finally {
        setPathCheckBusy(false);
      }
    },
    [settingsReady, settingsForm, checkPathsHealth, setPathHealth]
  );

  const handleConnectionTest = async (target: ConnectionTargetKey) => {
    if (!settingsForm) return;
    
    if (target === 'extruder' && (validationErrors.extruderIp || validationErrors.extruderPort)) {
      setSettingsError('Extruder IP/Port 형식을 확인하세요.');
      return;
    }
    if (target === 'ls_plc' && (validationErrors.lsIp || validationErrors.lsPort)) {
      setSettingsError('LS PLC IP/Port 형식을 확인하세요.');
      return;
    }
    if (target === 'spot' && validationErrors.spotIp) {
      setSettingsError('SPOT IP 형식을 확인하세요.');
      return;
    }

    const toInt = (value: string) => {
      const parsed = parseInt(value, 10);
      return isFinite(parsed) ? parsed : null;
    };

    const payload: any = {};
    if (target === 'extruder') {
      payload.extruder = {
        ip: settingsForm.extruderIp.trim() || undefined,
        port: toInt(settingsForm.extruderPort),
      };
    } else if (target === 'ls_plc') {
      payload.ls_plc = {
        ip: settingsForm.lsIp.trim() || undefined,
        port: toInt(settingsForm.lsPort),
      };
    } else if (target === 'spot') {
      const ip = settingsForm.spotIp.trim();
      payload.spot = {
        ip: ip || undefined,
        url: ip ? `http://${ip}/image.jpg` : undefined,
      };
    }

    setConnectionTestBusy((prev) => ({ ...prev, [target]: true }));
    try {
      await runConnectionTest(payload);
    } catch (error) {
      console.error('Connection test failed', error);
    } finally {
      setConnectionTestBusy((prev) => ({ ...prev, [target]: false }));
    }
  };

  const handleCreatePath = useCallback(
    async (path: string) => {
      const trimmed = path.trim();
      if (!trimmed) {
        setSettingsError('경로가 비어 있습니다.');
        return;
      }
      try {
        await createPath(trimmed);
        await runPathHealthCheck();
      } catch (error) {
        console.error('Path create failed', error);
        setSettingsError('폴더 생성에 실패했습니다.');
      }
    },
    [createPath, runPathHealthCheck, setSettingsError]
  );

  const registerSettingsSection = useCallback(
    (id: string) => (element: HTMLDivElement | null) => {
      settingsSectionRefs.current[id] = element;
    },
    []
  );

  useEffect(() => {
    if (!settingsOpen) return;

    const options = {
      root: settingsScrollRef.current,
      rootMargin: '-10% 0px -80% 0px', // Detect items near the top
      threshold: 0,
    };

    const observer = new IntersectionObserver((entries) => {
      if (isManualScrollingRef.current) return;

      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          setActiveSettingsSection(entry.target.id);
        }
      });
    }, options);

    const refs = settingsSectionRefs.current;
    Object.values(refs).forEach((el) => {
      if (el) observer.observe(el);
    });

    return () => {
      Object.values(refs).forEach((el) => {
        if (el) observer.unobserve(el);
      });
      observer.disconnect();
    };
  }, [settingsOpen]);

  const scrollToSettingsSection = useCallback(
    (id: string) => {
      const target = settingsSectionRefs.current[id];
      if (!target) return;
      
      isManualScrollingRef.current = true;
      if (manualScrollTimeoutRef.current) clearTimeout(manualScrollTimeoutRef.current);
      manualScrollTimeoutRef.current = setTimeout(() => {
        isManualScrollingRef.current = false;
      }, 1000); // Wait for smooth scroll to finish

      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveSettingsSection(id);
    },
    []
  );

  return {
    connectionTestBusy,
    pathCheckBusy,
    activeSettingsSection,
    settingsScrollRef,
    registerSettingsSection,
    scrollToSettingsSection,
    runPathHealthCheck,
    handleConnectionTest,
    handleCreatePath,
    setActiveSettingsSection,
  };
}
