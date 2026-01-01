import React, { useEffect, useMemo, useState, useRef } from 'react';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import axios from 'axios';
import { FactoryData, SpotConfig } from './types';
import './App.css';
import { initScenesRuntime } from './scenes/ScenesRuntime';
import { getDashboardScene } from './scenes/DashboardScene';
import { SceneGridItemLike, SceneGridLayout } from '@grafana/scenes';
import {
  APP_TITLE,
  NOTICE_BODY_PREFIX,
  NOTICE_BODY_SUFFIX,
  NOTICE_FOOTER,
  NOTICE_TEMP_THRESHOLD,
  NOTICE_TITLE,
  SPOT_UNIT,
} from './constants/uiText';

const API_BASE = 'http://localhost:8000';

const SPOT_WARN_TEMP = 580;
const SPOT_NORMAL_MIN = 480;
const SPOT_HIGH_MIN = 540;
const SPOT_MAX_TEMP = 600;
const SPEED_MAX = 8;
const PRESS_MAX = 180;
const PRESS_RUNNING_THRESHOLD = 20;
const ALERT_HOLD_MS = 2000;
const ALERT_HOLD_LONG_MS = 5000;

type LayoutEntry = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type LayoutMap = Record<string, LayoutEntry>;

const buildLayoutMap = (children: SceneGridItemLike[]): LayoutMap => {
  const next: LayoutMap = {};
  children.forEach((child) => {
    const key = child.state.key;
    const { x, y, width, height } = child.state;
    if (!key || x === undefined || y === undefined || width === undefined || height === undefined) {
      return;
    }
    next[key] = { x, y, width, height };
  });
  return next;
};

const clampNumber = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const useLastValidNumber = (value: number | null | undefined) => {
  const lastRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      lastRef.current = value;
    }
  }, [value]);

  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  return lastRef.current;
};

const useSustainedFlag = (condition: boolean, durationMs: number) => {
  const [active, setActive] = useState(false);
  const sinceRef = useRef<number | null>(null);

  useEffect(() => {
    const now = Date.now();
    if (condition) {
      if (sinceRef.current === null) {
        sinceRef.current = now;
      }
      if (!active && now - sinceRef.current >= durationMs) {
        setActive(true);
      }
    } else {
      sinceRef.current = null;
      if (active) {
        setActive(false);
      }
    }
  }, [condition, durationMs, active]);

  return active;
};

type ThresholdLevel = 'normal' | 'warn' | 'danger';

const useThresholdLevel = (value: number, warnThreshold: number, dangerThreshold: number, holdMs: number) => {
  const [level, setLevel] = useState<ThresholdLevel>('normal');
  const warnSinceRef = useRef<number | null>(null);
  const dangerSinceRef = useRef<number | null>(null);

  useEffect(() => {
    if (!Number.isFinite(value)) {
      warnSinceRef.current = null;
      dangerSinceRef.current = null;
      return;
    }

    const now = Date.now();

    if (value >= dangerThreshold) {
      if (dangerSinceRef.current === null) {
        dangerSinceRef.current = now;
      }
      warnSinceRef.current = null;
      if (now - dangerSinceRef.current >= holdMs && level !== 'danger') {
        setLevel('danger');
      }
      return;
    }

    dangerSinceRef.current = null;

    if (value >= warnThreshold) {
      if (warnSinceRef.current === null) {
        warnSinceRef.current = now;
      }
      if (level === 'danger') {
        setLevel('warn');
      }
      if (now - warnSinceRef.current >= holdMs && level !== 'warn') {
        setLevel('warn');
      }
      return;
    }

    warnSinceRef.current = null;
    if (level !== 'normal') {
      setLevel('normal');
    }
  }, [value, warnThreshold, dangerThreshold, holdMs, level]);

  return level;
};

const formatTime = (timestamp: number | null) => {
  if (!timestamp) {
    return '--:--:--';
  }
  const date = new Date(timestamp);
  return date.toTimeString().slice(0, 8);
};

const formatNumber = (value: number, decimals: number) => {
  if (!Number.isFinite(value)) {
    return '--';
  }
  return value.toFixed(decimals);
};

const formatInteger = (value: number) => {
  if (!Number.isFinite(value)) {
    return '--';
  }
  return Math.round(value).toString();
};

const getSpeedState = (speed: number) => {
  if (speed >= 8) {
    return { label: '매우빠름', className: 'speed-very-fast' };
  }
  if (speed >= 6) {
    return { label: '빠름', className: 'speed-fast' };
  }
  if (speed >= 4) {
    return { label: '보통', className: 'speed-normal' };
  }
  if (speed >= 2) {
    return { label: '저속', className: 'speed-slow' };
  }
  return { label: '매우저속', className: 'speed-very-slow' };
};

const getPressState = (press: number) => {
  if (press >= 180) {
    return { label: '높음', className: 'press-high' };
  }
  if (press >= 126) {
    return { label: '보통', className: 'press-normal' };
  }
  return { label: '낮음', className: 'press-low' };
};

type SpotState = {
  label: string;
  statusClass: string;
  fillClass: string;
  warning: boolean;
};

const getSpotState = (temp: number, warningActive: boolean): SpotState => {
  if (!Number.isFinite(temp)) {
    return {
      label: '저온',
      statusClass: 'spot-status-low',
      fillClass: 'spot-fill-low',
      warning: false,
    };
  }
  if (temp >= SPOT_WARN_TEMP && warningActive) {
    return {
      label: '경고',
      statusClass: 'spot-status-warning',
      fillClass: 'spot-fill-warning',
      warning: true,
    };
  }
  if (temp >= SPOT_HIGH_MIN) {
    return {
      label: '고온',
      statusClass: 'spot-status-high',
      fillClass: 'spot-fill-high',
      warning: false,
    };
  }
  if (temp >= SPOT_NORMAL_MIN) {
    return {
      label: '보통',
      statusClass: 'spot-status-normal',
      fillClass: 'spot-fill-normal',
      warning: false,
    };
  }
  return {
    label: '저온',
    statusClass: 'spot-status-low',
    fillClass: 'spot-fill-low',
    warning: false,
  };
};

const getMoldState = (value: number) => {
  if (!Number.isFinite(value)) {
    return { className: 'mold-muted' };
  }
  return value >= 100 ? { className: 'mold-alert' } : { className: 'mold-normal' };
};

const getEnvTempState = (value: number) => {
  if (!Number.isFinite(value)) {
    return { label: '미확인', className: 'env-muted' };
  }
  if (value >= 28) {
    return { label: '더움', className: 'env-hot' };
  }
  if (value < 10) {
    return { label: '추움', className: 'env-cold' };
  }
  return { label: '쾌적', className: 'env-comfort' };
};

const getEnvHumidityState = (value: number) => {
  if (!Number.isFinite(value)) {
    return { label: '미확인', className: 'env-muted' };
  }
  if (value >= 60) {
    return { label: '다습', className: 'env-humid' };
  }
  if (value < 30) {
    return { label: '건조', className: 'env-dry' };
  }
  return { label: '쾌적', className: 'env-comfort' };
};

const calcPercent = (value: number, max: number) => {
  if (!Number.isFinite(value) || max <= 0) {
    return 0;
  }
  return Math.round((clampNumber(value, 0, max) / max) * 100);
};

const getCameraStatus = (params: {
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotImageError: string | null;
  spotLastSuccessAt: number | null;
}) => {
  const { spotConfig, spotImageUrl, spotImageLoading, spotImageError, spotLastSuccessAt } = params;
  if (!spotConfig) {
    return null;
  }
  const refreshMs = Math.max(500, Math.round(spotConfig.refresh_interval * 1000));
  const now = Date.now();
  const delayMs = spotLastSuccessAt ? now - spotLastSuccessAt : null;

  if (spotImageError) {
    return { type: 'error', title: spotImageError, detail: '' };
  }
  if (!spotImageUrl || spotImageLoading || spotLastSuccessAt === null) {
    return { type: 'loading', title: '카메라 연결 중', detail: '' };
  }
  if (delayMs !== null && delayMs > refreshMs * 5) {
    return { type: 'danger', title: '이미지 수신 지연', detail: `지연 ${Math.round(delayMs / 1000)}초` };
  }
  if (delayMs !== null && delayMs > refreshMs * 2) {
    return { type: 'warn', title: '이미지 지연 감지', detail: `지연 ${Math.round(delayMs / 1000)}초` };
  }
  return null;
};

function App() {
  const [data, setData] = useState<FactoryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastDataAt, setLastDataAt] = useState<number | null>(null);
  const [spotConfig, setSpotConfig] = useState<SpotConfig | null>(null);
  const [spotImageUrl, setSpotImageUrl] = useState('');
  const [spotImageError, setSpotImageError] = useState<string | null>(null);
  const [spotImageLoading, setSpotImageLoading] = useState(false);
  const [spotLastSuccessAt, setSpotLastSuccessAt] = useState<number | null>(null);
  const [focusBusy, setFocusBusy] = useState(false);
  const [layoutEditing, setLayoutEditing] = useState(false);
  const [layoutSaveMessage, setLayoutSaveMessage] = useState<string | null>(null);
  const [layoutSaveError, setLayoutSaveError] = useState<string | null>(null);
  const scenesRuntimeRef = useRef(false);
  const spotHasImage = useRef(false);
  const saveMessageTimerRef = useRef<number | null>(null);
  const lastSpotValue = useLastValidNumber(data?.Spot);
  const spotAlertActive = useSustainedFlag(
    lastSpotValue !== null && lastSpotValue >= SPOT_WARN_TEMP,
    ALERT_HOLD_MS
  );

  // --- Data Fetching Hooks (Same as before) ---
  useEffect(() => {
    if (scenesRuntimeRef.current) {
      return;
    }
    scenesRuntimeRef.current = true;
    initScenesRuntime();
  }, []);

  useEffect(() => {
    return () => {
      if (saveMessageTimerRef.current !== null) {
        window.clearTimeout(saveMessageTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await axios.get<FactoryData>(`${API_BASE}/api/data`);
        setData(res.data);
        setConnected(true);
        setLastDataAt(Date.now());
      } catch (err) {
        console.error('API Error', err);
        setConnected(false);
      }
    };
    const interval = setInterval(fetchData, 500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const fetchSpotConfig = async () => {
      try {
        const res = await axios.get<SpotConfig>(`${API_BASE}/api/spot/config`);
        setSpotConfig(res.data);
      } catch (err) {
        console.error('SPOT config error', err);
      }
    };
    fetchSpotConfig();
  }, []);

  useEffect(() => {
    if (!spotConfig?.image_url) {
      return;
    }
    spotHasImage.current = false;
    setSpotLastSuccessAt(null);
    setSpotImageError(null);
  }, [spotConfig?.image_url]);

  useEffect(() => {
    if (!spotConfig || !spotConfig.image_url) return;
    const refreshMs = Math.max(500, Math.round(spotConfig.refresh_interval * 1000));
    const updateImage = () => {
      const separator = spotConfig.image_url.includes('?') ? '&' : '?';
      if (!spotHasImage.current) setSpotImageLoading(true);
      setSpotImageUrl(`${spotConfig.image_url}${separator}t=${Date.now()}`);
    };
    updateImage();
    const timer = setInterval(updateImage, refreshMs);
    return () => clearInterval(timer);
  }, [spotConfig]);

  const handleSpotImageLoaded = () => {
    spotHasImage.current = true;
    setSpotImageLoading(false);
    setSpotImageError(null);
    setSpotLastSuccessAt(Date.now());
  };

  const handleSpotImageError = (message = '이미지 수신 실패') => {
    setSpotImageLoading(false);
    setSpotImageError(message);
  };

  const requestFocus = async (steps: number) => {
    if (!spotConfig?.focus_enabled || focusBusy) return;
    setFocusBusy(true);
    try {
      await axios.post(`${API_BASE}/api/spot/focus`, null, { params: { steps } });
    } catch (err) {
      console.error('SPOT focus error', err);
    } finally {
      setFocusBusy(false);
    }
  };

  // --- Widget Renderers ---
  // --- Scene Creation ---
  // Scene is created once; widget data is read from DataContext.
  const scene = useMemo(() => getDashboardScene(
     () => <KpiComponent />,
     () => <SpotComponent />,
     () => <TempsComponent />,
     () => <MoldsComponent />,
     () => <EnvComponent />,
     () => <CameraComponent />,
     () => <NoticeComponent />
  ), []); 

  const layoutRef = useRef<LayoutMap>({});

  useEffect(() => {
    const grid = scene.state.body;
    if (!(grid instanceof SceneGridLayout)) {
      return;
    }

    const updateLayoutRef = () => {
      layoutRef.current = buildLayoutMap(grid.state.children);
    };

    updateLayoutRef();
    const sub = grid.subscribeToState(() => updateLayoutRef());
    return () => sub.unsubscribe();
  }, [scene]);

  useEffect(() => {
    const grid = scene.state.body;
    if (!(grid instanceof SceneGridLayout)) {
      return;
    }
    grid.setState({ isDraggable: layoutEditing, isResizable: layoutEditing });
  }, [scene, layoutEditing]);

  // --- Layout Persistence ---
  const saveLayout = () => {
    if (!layoutEditing) {
      return;
    }
    if (Object.keys(layoutRef.current).length === 0) {
      const grid = scene.state.body;
      if (grid instanceof SceneGridLayout) {
        layoutRef.current = buildLayoutMap(grid.state.children);
      }
    }
    try {
      localStorage.setItem('grafana_scene_layout_v1', JSON.stringify(layoutRef.current));
      localStorage.setItem('grafana_scene_layout_cols', '60');
      setLayoutSaveError(null);
      setLayoutSaveMessage('저장됨');
    } catch (error) {
      console.error('Layout save failed', error);
      setLayoutSaveError('저장 실패');
      return;
    }
    if (saveMessageTimerRef.current !== null) {
      window.clearTimeout(saveMessageTimerRef.current);
    }
    saveMessageTimerRef.current = window.setTimeout(() => {
      setLayoutSaveMessage(null);
      saveMessageTimerRef.current = null;
    }, 2000);
  };

  return (
    <div className={`App ${layoutEditing ? 'layout-editing' : ''}`} style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header className="app-header">
        <h1>{APP_TITLE}</h1>
         <div className="header-controls">
            <button
              onClick={() => setLayoutEditing((prev) => !prev)}
              className={`edit-toggle ${layoutEditing ? 'active' : ''}`}
            >
              {layoutEditing ? '편집 완료' : '편집 모드'}
            </button>
            <button
              onClick={saveLayout}
              className="save-layout"
              disabled={!layoutEditing}
              aria-disabled={!layoutEditing}
            >
              {layoutSaveMessage ?? '레이아웃 저장'}
            </button>
            {layoutSaveError && (
              <div className="save-error">
                <span>{layoutSaveError}</span>
                <button onClick={saveLayout} className="retry-button">
                  재시도
                </button>
              </div>
            )}
            <div className="status-badge" style={{ backgroundColor: connected ? '#4ec9b0' : '#f14c4c' }}>
                {connected ? 'Running' : 'Offline'}
            </div>
         </div>
      </header>
      <div className="scene-container" style={{ flexGrow: 1 }}>
        {/* Pass data via context to the scene? 
            Actually, wrapping the Scene Component in a Context Provider works!
            The ReactWidget will be rendered *inside* this provider.
        */}
        <DataContext.Provider
          value={{
            data,
            spotConfig,
            spotImageUrl,
            spotImageLoading,
            spotImageError,
            spotLastSuccessAt,
            spotAlertActive,
            lastDataAt,
            onSpotImageLoaded: handleSpotImageLoaded,
            onSpotImageError: handleSpotImageError,
            requestFocus,
          }}
        >
           <scene.Component model={scene} />
        </DataContext.Provider>
      </div>
    </div>
  );
}

// --- Context & Components ---
// Define Context to pass data into the Scene's ReactWidgets
type DataContextValue = {
  data: FactoryData | null;
  spotConfig: SpotConfig | null;
  spotImageUrl: string;
  spotImageLoading: boolean;
  spotImageError: string | null;
  spotLastSuccessAt: number | null;
  spotAlertActive: boolean;
  lastDataAt: number | null;
  onSpotImageLoaded: () => void;
  onSpotImageError: (message?: string) => void;
  requestFocus: (steps: number) => void;
};

const DataContext = React.createContext<DataContextValue>({
  data: null,
  spotConfig: null,
  spotImageUrl: '',
  spotImageLoading: false,
  spotImageError: null,
  spotLastSuccessAt: null,
  spotAlertActive: false,
  lastDataAt: null,
  onSpotImageLoaded: () => undefined,
  onSpotImageError: () => undefined,
  requestFocus: () => undefined,
});

const KpiComponent = () => {
  const { data, lastDataAt } = React.useContext(DataContext);
  const speedValue = useLastValidNumber(data?.Speed);
  const pressValue = useLastValidNumber(data?.Press);
  if (!data) return <div>Loading...</div>;
  const missing = !Number.isFinite(data.Speed) || !Number.isFinite(data.Press);
  const speedForLogic = speedValue ?? data.Speed;
  const pressForLogic = pressValue ?? data.Press;
  const safeSpeed = Number.isFinite(speedForLogic) ? speedForLogic : 0;
  const safePress = Number.isFinite(pressForLogic) ? pressForLogic : 0;
  const jamCondition = safeSpeed === 0 && safePress >= PRESS_RUNNING_THRESHOLD;
  const jamWarn = useSustainedFlag(jamCondition, ALERT_HOLD_MS);
  const jamDanger = useSustainedFlag(jamCondition, ALERT_HOLD_LONG_MS);
  const kpiAlertClass = jamDanger ? 'card-danger' : jamWarn ? 'card-warning' : '';
  const speedState = getSpeedState(safeSpeed);
  const pressState = getPressState(safePress);
  const speedPercent = calcPercent(safeSpeed, SPEED_MAX);
  const pressPercent = calcPercent(safePress, PRESS_MAX);
  return (
    <div className={`card kpi-card ${kpiAlertClass}`} style={{ height: '100%' }}>
      <div className="kpi-metric">
        <div className="kpi-header">
          <span className="kpi-title">속도</span>
          <span className={`kpi-state ${speedState.className}`}>{speedState.label}</span>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{formatNumber(data.Speed, 1)}</span>
          <span className="kpi-unit">mm/s</span>
        </div>
        <div className="kpi-bar">
          <div className={`kpi-bar-fill ${speedState.className}`} style={{ width: `${speedPercent}%` }} />
        </div>
      </div>

      <div className="kpi-metric">
        <div className="kpi-header">
          <span className="kpi-title">압력</span>
          <span className={`kpi-state ${pressState.className}`}>{pressState.label}</span>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{formatNumber(data.Press, 1)}</span>
          <span className="kpi-unit">bar</span>
        </div>
        <div className="kpi-bar">
          <div className={`kpi-bar-fill ${pressState.className}`} style={{ width: `${pressPercent}%` }} />
        </div>
      </div>

      <div className="kpi-secondary">
        <div className="kpi-mini">
          <span className="kpi-mini-label">카운트</span>
          <span className="kpi-mini-value">{formatInteger(data.Count)}</span>
        </div>
        <div className="kpi-mini">
          <span className="kpi-mini-label">종료 위치</span>
          <div className="kpi-mini-value-row">
            <span className="kpi-mini-value">{formatNumber(data.EndPos, 1)}</span>
            <span className="kpi-mini-unit">mm</span>
          </div>
        </div>
      </div>
      {missing && (
        <div className="missing-note">
          마지막 갱신 {formatTime(lastDataAt)}
        </div>
      )}
    </div>
  );
};

const SpotComponent = () => {
    const { data, spotAlertActive, lastDataAt } = React.useContext(DataContext);
    if (!data) return <div>Loading...</div>;
    const missing = !Number.isFinite(data.Spot);
    const spotValue = useLastValidNumber(data.Spot);
    const spotDisplayValue = Number.isFinite(spotValue ?? NaN) ? spotValue! : data.Spot;
    const spotState = getSpotState(spotDisplayValue, spotAlertActive);
    const spotPercent = calcPercent(spotDisplayValue, SPOT_MAX_TEMP);
    return (
      <div className={`card spot-card ${spotState.warning ? 'spot-danger' : 'spot-normal'}`} style={{ height: '100%' }}>
        <div className="spot-gauge">
          <svg viewBox="0 0 200 120" className="spot-gauge-svg" aria-hidden="true">
            <path
              className="spot-gauge-track"
              d="M20 100 A80 80 0 0 1 180 100"
              pathLength={100}
            />
            <path
              className={`spot-gauge-fill ${spotState.fillClass}`}
              d="M20 100 A80 80 0 0 1 180 100"
              pathLength={100}
              strokeDasharray={`${spotPercent} 100`}
            />
          </svg>
          <div className="spot-value">
            <span className="spot-value-number">{formatNumber(spotDisplayValue, 1)}</span>
            <span className="spot-unit">{SPOT_UNIT}</span>
          </div>
        </div>
        <div className="spot-status-row">
          <span className={`spot-status ${spotState.statusClass}`}>
            {spotState.label}
          </span>
          {spotState.warning && (
            <span className="spot-alert-icon" aria-label="SPOT 경고">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 3L2 21h20L12 3zm0 5.5c.6 0 1 .4 1 1v5c0 .6-.4 1-1 1s-1-.4-1-1v-5c0-.6.4-1 1-1zm0 9c.7 0 1.3.6 1.3 1.3S12.7 20 12 20s-1.3-.6-1.3-1.3S11.3 17.5 12 17.5z" />
              </svg>
            </span>
          )}
        </div>
        {missing && (
          <div className="missing-note">
            마지막 갱신 {formatTime(lastDataAt)}
          </div>
        )}
      </div>
    );
};

const TempsComponent = () => {
    const { data, lastDataAt } = React.useContext(DataContext);
    if (!data) return <div>Loading...</div>;
    const missing =
      !Number.isFinite(data.Temp_F) ||
      !Number.isFinite(data.Temp_B) ||
      !Number.isFinite(data.Billet_Temp) ||
      !Number.isFinite(data.Billet_Length);
    const tempFLevel = useThresholdLevel(data.Temp_F, 350, 450, ALERT_HOLD_MS);
    const tempBLevel = useThresholdLevel(data.Temp_B, 350, 450, ALERT_HOLD_MS);
    const billetTempLevel = useThresholdLevel(data.Billet_Temp, 440, 480, ALERT_HOLD_MS);
    const tempFClass = tempFLevel === 'danger' ? 'temp-danger' : tempFLevel === 'warn' ? 'temp-warn' : '';
    const tempBClass = tempBLevel === 'danger' ? 'temp-danger' : tempBLevel === 'warn' ? 'temp-warn' : '';
    const billetTempClass = billetTempLevel === 'danger' ? 'temp-danger' : billetTempLevel === 'warn' ? 'temp-warn' : '';
    return (
      <div className="card" style={{ height: '100%' }}>
        <div className="temp-grid">
          <div className={`temp-tile ${tempFClass}`}>
            <span className="temp-label">콘테이너 앞</span>
            <div className="temp-value-row">
              <span className="temp-value">{formatNumber(data.Temp_F, 1)}</span>
              <span className="temp-unit">{SPOT_UNIT}</span>
            </div>
          </div>
          <div className={`temp-tile ${tempBClass}`}>
            <span className="temp-label">콘테이너 뒤</span>
            <div className="temp-value-row">
              <span className="temp-value">{formatNumber(data.Temp_B, 1)}</span>
              <span className="temp-unit">{SPOT_UNIT}</span>
            </div>
          </div>
          <div className={`temp-tile ${billetTempClass}`}>
            <span className="temp-label">빌렛 온도</span>
            <div className="temp-value-row">
              <span className="temp-value">{formatNumber(data.Billet_Temp, 1)}</span>
              <span className="temp-unit">{SPOT_UNIT}</span>
            </div>
          </div>
          <div className="temp-tile">
            <span className="temp-label">빌렛 길이</span>
            <div className="temp-value-row">
              <span className="temp-value">{formatNumber(data.Billet_Length, 1)}</span>
              <span className="temp-unit">mm</span>
            </div>
          </div>
        </div>
        {missing && (
          <div className="missing-note">
            마지막 갱신 {formatTime(lastDataAt)}
          </div>
        )}
      </div>
    );
};

const MoldsComponent = () => {
    const { data, lastDataAt } = React.useContext(DataContext);
    if (!data) return <div>Loading...</div>;
    const missing =
      !Number.isFinite(data.Mold1) ||
      !Number.isFinite(data.Mold2) ||
      !Number.isFinite(data.Mold3) ||
      !Number.isFinite(data.Mold4) ||
      !Number.isFinite(data.Mold5) ||
      !Number.isFinite(data.Mold6);
    const mold1 = getMoldState(data.Mold1);
    const mold2 = getMoldState(data.Mold2);
    const mold3 = getMoldState(data.Mold3);
    const mold4 = getMoldState(data.Mold4);
    const mold5 = getMoldState(data.Mold5);
    const mold6 = getMoldState(data.Mold6);
    return (
      <div className="card" style={{ height: '100%' }}>
        <div className="mold-grid">
          <div className={`mold-tile ${mold1.className}`}>
            <span className="mold-label">Mold 1</span>
            <span className="mold-value">{formatNumber(data.Mold1, 1)}</span>
          </div>
          <div className={`mold-tile ${mold2.className}`}>
            <span className="mold-label">Mold 2</span>
            <span className="mold-value">{formatNumber(data.Mold2, 1)}</span>
          </div>
          <div className={`mold-tile ${mold3.className}`}>
            <span className="mold-label">Mold 3</span>
            <span className="mold-value">{formatNumber(data.Mold3, 1)}</span>
          </div>
          <div className={`mold-tile ${mold4.className}`}>
            <span className="mold-label">Mold 4</span>
            <span className="mold-value">{formatNumber(data.Mold4, 1)}</span>
          </div>
          <div className={`mold-tile ${mold5.className}`}>
            <span className="mold-label">Mold 5</span>
            <span className="mold-value">{formatNumber(data.Mold5, 1)}</span>
          </div>
          <div className={`mold-tile ${mold6.className}`}>
            <span className="mold-label">Mold 6</span>
            <span className="mold-value">{formatNumber(data.Mold6, 1)}</span>
          </div>
        </div>
        {missing && (
          <div className="missing-note">
            마지막 갱신 {formatTime(lastDataAt)}
          </div>
        )}
      </div>
    );
};

const EnvComponent = () => {
    const { data, lastDataAt } = React.useContext(DataContext);
    if (!data) return <div>Loading...</div>;
    const missing = !Number.isFinite(data.At_Temp) || !Number.isFinite(data.At_Pre);
    const tempState = getEnvTempState(data.At_Temp);
    const humidityState = getEnvHumidityState(data.At_Pre);
    return (
      <div className="card env-card" style={{ height: '100%' }}>
        <div className="env-grid">
          <div className="env-tile">
            <span className="env-label">환경 온도</span>
            <div className="env-value-row">
              <span className="env-value">{formatNumber(data.At_Temp, 1)}</span>
              <span className="env-unit">{SPOT_UNIT}</span>
            </div>
            <span className={`env-badge ${tempState.className}`}>{tempState.label}</span>
          </div>
          <div className="env-tile">
            <span className="env-label">환경 습도</span>
            <div className="env-value-row">
              <span className="env-value">{formatNumber(data.At_Pre, 1)}</span>
              <span className="env-unit">%</span>
            </div>
            <span className={`env-badge ${humidityState.className}`}>{humidityState.label}</span>
          </div>
        </div>
        {missing && (
          <div className="missing-note">
            마지막 갱신 {formatTime(lastDataAt)}
          </div>
        )}
      </div>
    );
};

const NoticeComponent = () => {
    const {
      spotConfig,
      spotImageUrl,
      spotImageLoading,
      spotImageError,
      spotLastSuccessAt,
      spotAlertActive,
    } = React.useContext(DataContext);

    const cameraStatus = getCameraStatus({
      spotConfig,
      spotImageUrl,
      spotImageLoading,
      spotImageError,
      spotLastSuccessAt,
    });

    let noticeLevel: 'normal' | 'warning' | 'danger' = 'normal';
    if (spotAlertActive || cameraStatus?.type === 'danger' || cameraStatus?.type === 'error') {
      noticeLevel = 'danger';
    } else if (cameraStatus?.type === 'warn' || cameraStatus?.type === 'loading') {
      noticeLevel = 'warning';
    }

    const noticeClass = noticeLevel === 'danger' ? 'card-danger' : noticeLevel === 'warning' ? 'card-warning' : '';
    const noticeMessages: string[] = [];

    if (spotAlertActive) {
      noticeMessages.push(`SPOT 온도 ${SPOT_WARN_TEMP}${SPOT_UNIT} 이상 감지`);
    }
    if (cameraStatus) {
      const detail = cameraStatus.detail ? ` (${cameraStatus.detail})` : '';
      noticeMessages.push(`SPOT 카메라 ${cameraStatus.title}${detail}`);
    }

    return (
      <div className={`card notice-card ${noticeClass}`} style={{ height: '100%' }}>
        <div className="notice-header">
          <span className="notice-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M12 3L2 21h20L12 3zm0 5.5c.6 0 1 .4 1 1v5c0 .6-.4 1-1 1s-1-.4-1-1v-5c0-.6.4-1 1-1zm0 9c.7 0 1.3.6 1.3 1.3S12.7 20 12 20s-1.3-.6-1.3-1.3S11.3 17.5 12 17.5z" />
            </svg>
          </span>
          <span className="notice-title">{NOTICE_TITLE}</span>
        </div>
        <div className="notice-body">
          {noticeMessages.length > 0 && (
            <ul className="notice-list">
              {noticeMessages.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          )}
          <p className="notice-line">
            {NOTICE_BODY_PREFIX}<b>{NOTICE_TEMP_THRESHOLD}</b>{NOTICE_BODY_SUFFIX}
          </p>
          <p className="notice-line">{NOTICE_FOOTER}</p>
        </div>
      </div>
    );
};

const CameraComponent = () => {
    const {
      spotConfig,
      spotImageUrl,
      spotImageLoading,
      spotImageError,
      spotLastSuccessAt,
      onSpotImageLoaded,
      onSpotImageError,
      requestFocus,
    } = React.useContext(DataContext);
    if (!spotConfig) return <div>Loading Config...</div>;
    
    // Crosshair logic
    const clamp = (val: number, min: number, max: number) => Math.min(max, Math.max(min, val));
    const cx = clamp(spotConfig.crosshair_x, 0, 1) * spotConfig.widget_width;
    const cy = clamp(spotConfig.crosshair_y, 0, 1) * spotConfig.widget_height;
    const arm = Math.max(1, spotConfig.crosshair_size);
    const gap = Math.max(0, spotConfig.crosshair_gap);
    const thick = Math.max(1, spotConfig.crosshair_thickness);
    const color = spotConfig.crosshair_color || 'lime';

    const lines = [
      { x1: cx - gap, y1: cy, x2: cx - arm, y2: cy },
      { x1: cx + gap, y1: cy, x2: cx + arm, y2: cy },
      { x1: cx, y1: cy - gap, x2: cx, y2: cy - arm },
      { x1: cx, y1: cy + gap, x2: cx, y2: cy + arm },
    ];

    const cameraStatus = getCameraStatus({
      spotConfig,
      spotImageUrl,
      spotImageLoading,
      spotImageError,
      spotLastSuccessAt,
    });
    
    return (
      <div className="card camera-card" style={{ height: '100%', position: 'relative' }}>
        <div className="camera-frame">
          {spotImageUrl && (
            <img
              className="camera-image"
              src={spotImageUrl}
              alt="SPOT Camera"
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              onLoad={onSpotImageLoaded}
              onError={() => onSpotImageError()}
            />
          )}
          <svg className="camera-crosshair" viewBox={`0 0 ${spotConfig.widget_width} ${spotConfig.widget_height}`} preserveAspectRatio="none" style={{position:'absolute', top:0, left:0, width:'100%', height:'100%' }}>
            {lines.map((line, idx) => (
              <g key={idx}>
                <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} stroke="black" strokeWidth={thick + 2} strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
                <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} stroke={color} strokeWidth={thick} strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
              </g>
            ))}
            <circle cx={cx} cy={cy} r={3} stroke="black" strokeWidth={3} fill="none" vectorEffect="non-scaling-stroke" />
            <circle cx={cx} cy={cy} r={3} stroke={color} strokeWidth={1} fill="none" vectorEffect="non-scaling-stroke" />
          </svg>
          {cameraStatus && (
            <div className={`camera-overlay ${cameraStatus.type}`}>
              {cameraStatus.type === 'loading' && <span className="camera-spinner" aria-hidden="true" />}
              <div className="camera-status-text">
                <div className="camera-status-title">{cameraStatus.title}</div>
                {cameraStatus.detail && <div className="camera-status-detail">{cameraStatus.detail}</div>}
              </div>
            </div>
          )}
        </div>
        <div className="camera-controls" style={{marginTop: '4px'}}>
           <button onClick={() => requestFocus(-10)}>FOCUS -</button>
           <button onClick={() => requestFocus(10)}>FOCUS +</button>
        </div>
      </div>
    );
};

export default App;
