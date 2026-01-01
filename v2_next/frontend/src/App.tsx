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

function App() {
  const [data, setData] = useState<FactoryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [spotConfig, setSpotConfig] = useState<SpotConfig | null>(null);
  const [spotImageUrl, setSpotImageUrl] = useState('');
  const [spotImageError, setSpotImageError] = useState<string | null>(null);
  const [spotImageLoading, setSpotImageLoading] = useState(false);
  const [focusBusy, setFocusBusy] = useState(false);
  const [layoutSaveMessage, setLayoutSaveMessage] = useState<string | null>(null);
  const scenesRuntimeRef = useRef(false);
  const spotHasImage = useRef(false);
  const saveMessageTimerRef = useRef<number | null>(null);

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
    if (!spotConfig || !spotConfig.image_url) return;
    const refreshMs = Math.max(500, Math.round(spotConfig.refresh_interval * 1000));
    const updateImage = () => {
      const separator = spotConfig.image_url.includes('?') ? '&' : '?';
      if (!spotHasImage.current) setSpotImageLoading(true);
      setSpotImageError(null);
      setSpotImageUrl(`${spotConfig.image_url}${separator}t=${Date.now()}`);
    };
    updateImage();
    const timer = setInterval(updateImage, refreshMs);
    return () => clearInterval(timer);
  }, [spotConfig]);

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
  const renderNotice = () => (
    <div className="card" style={{ height: '100%' }}>
      <p style={{ color: '#aaa', fontSize: '0.9rem', lineHeight: 1.5 }}>
        {NOTICE_TITLE}<br />
        {NOTICE_BODY_PREFIX}<b>{NOTICE_TEMP_THRESHOLD}</b>{NOTICE_BODY_SUFFIX}<br />
        {NOTICE_FOOTER}
      </p>
    </div>
  );

  // --- Scene Creation ---
  // Scene is created once; widget data is read from DataContext.
  const scene = useMemo(() => getDashboardScene(
     () => <KpiComponent />,
     () => <SpotComponent />,
     () => <TempsComponent />,
     () => <MoldsComponent />,
     () => <CameraComponent />,
     renderNotice
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

  // --- Layout Persistence ---
  const saveLayout = () => {
    if (Object.keys(layoutRef.current).length === 0) {
      const grid = scene.state.body;
      if (grid instanceof SceneGridLayout) {
        layoutRef.current = buildLayoutMap(grid.state.children);
      }
    }
    localStorage.setItem('grafana_scene_layout_v1', JSON.stringify(layoutRef.current));
    setLayoutSaveMessage('Saved');
    if (saveMessageTimerRef.current !== null) {
      window.clearTimeout(saveMessageTimerRef.current);
    }
    saveMessageTimerRef.current = window.setTimeout(() => {
      setLayoutSaveMessage(null);
      saveMessageTimerRef.current = null;
    }, 2000);
  };

  return (
    <div className="App" style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header className="app-header">
        <h1>{APP_TITLE}</h1>
         <div className="header-controls" style={{ marginLeft: 'auto', display: 'flex', gap: '10px', alignItems: 'center', marginRight: '20px' }}>
            <button onClick={saveLayout} style={{ padding: '6px 12px', cursor: 'pointer' }}>
              {layoutSaveMessage ?? 'Save Layout'}
            </button>
            <div className="status-badge" style={{ backgroundColor: connected ? '#4ec9b0' : '#f14c4c' }}>
                {connected ? 'Running' : 'Offline'}
            </div>
         </div>
      </header>
      <div style={{ flexGrow: 1 }}>
        {/* Pass data via context to the scene? 
            Actually, wrapping the Scene Component in a Context Provider works!
            The ReactWidget will be rendered *inside* this provider.
        */}
        <DataContext.Provider value={{ data, spotConfig, spotImageUrl, spotImageLoading, spotImageError, requestFocus }}>
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
  requestFocus: (steps: number) => void;
};

const DataContext = React.createContext<DataContextValue>({
  data: null,
  spotConfig: null,
  spotImageUrl: '',
  spotImageLoading: false,
  spotImageError: null,
  requestFocus: () => undefined,
});

const KpiComponent = () => {
  const { data } = React.useContext(DataContext);
  if (!data) return <div>Loading...</div>;
  return (
      <div className="card kpi-card" style={{ height: '100%' }}>
        <div className="metric-row"><span>Speed</span><span className="value">{data.Speed}</span></div>
        <div className="metric-row"><span>Pressure</span><span className="value">{data.Press}</span></div>
        <div className="metric-row"><span>Count</span><span className="value">{data.Count}</span></div>
      </div>
  );
};

const SpotComponent = () => {
    const { data } = React.useContext(DataContext);
    if (!data) return <div>Loading...</div>;
    return (
      <div className="card spot-card" style={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <div className="hero-value">{data.Spot} {SPOT_UNIT}</div>
        <div className={`status-indicator ${data.Spot > 500 ? 'hot' : 'normal'}`}>
          {data.Spot > 500 ? 'HIGH TEMP' : 'NORMAL'}
        </div>
      </div>
    );
};

const TempsComponent = () => {
    const { data } = React.useContext(DataContext);
    if (!data) return <div>Loading...</div>;
    return (
      <div className="card" style={{ height: '100%' }}>
        <div className="grid-2">
          <div>CF: <b>{data.Temp_F}</b></div>
          <div>CB: <b>{data.Temp_B}</b></div>
          <div>BT: <b>{data.Billet_Temp}</b></div>
          <div>BL: <b>{data.Billet_Length}</b></div>
        </div>
      </div>
    );
};

const MoldsComponent = () => {
    const { data } = React.useContext(DataContext);
    if (!data) return <div>Loading...</div>;
    return (
      <div className="card" style={{ height: '100%' }}>
        <div className="mold-grid">
          <div>M1: {data.Mold1}</div>
          <div>M2: {data.Mold2}</div>
          <div>M3: {data.Mold3}</div>
          <div>M4: {data.Mold4}</div>
          <div>M5: {data.Mold5}</div>
          <div>M6: {data.Mold6}</div>
        </div>
      </div>
    );
};

const CameraComponent = () => {
    const { spotConfig, spotImageUrl, spotImageLoading, spotImageError, requestFocus } = React.useContext(DataContext);
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
    
    return (
      <div className="card camera-card" style={{ height: '100%', position: 'relative' }}>
        <div className="camera-frame">
          {spotImageUrl && (
            <img
              className="camera-image"
              src={spotImageUrl}
              alt="SPOT Camera"
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            />
          )}
          <svg className="camera-overlay" viewBox={`0 0 ${spotConfig.widget_width} ${spotConfig.widget_height}`} preserveAspectRatio="none" style={{position:'absolute', top:0, left:0, width:'100%', height:'100%' }}>
            {lines.map((line, idx) => (
              <g key={idx}>
                <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} stroke="black" strokeWidth={thick + 2} strokeDasharray="4 4" />
                <line x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} stroke={color} strokeWidth={thick} strokeDasharray="4 4" />
              </g>
            ))}
            <circle cx={cx} cy={cy} r={3} stroke="black" strokeWidth={3} fill="none" />
            <circle cx={cx} cy={cy} r={3} stroke={color} strokeWidth={1} fill="none" />
          </svg>
          {(spotImageLoading || spotImageError || !spotImageUrl) && (
            <div className={`camera-status ${spotImageError ? 'error' : ''}`} style={{position:'absolute', top:'50%', left:'50%', transform:'translate(-50%, -50%)', color:'white', background:'rgba(0,0,0,0.7)', padding:'4px'}}>
              {spotImageError ? spotImageError : 'Connecting...'}
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
