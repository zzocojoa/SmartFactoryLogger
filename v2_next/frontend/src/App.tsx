import React, { useEffect, useMemo, useState, useRef } from 'react';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import axios from 'axios';
import { FactoryData, SpotConfig } from './types';
import './App.css';
import { initScenesRuntime } from './scenes/ScenesRuntime';
import { getDashboardScene } from './scenes/DashboardScene';
import { SceneGridLayout } from '@grafana/scenes';

// Initialize Scenes Runtime (Mocking Grafana services)
initScenesRuntime();

const API_BASE = 'http://localhost:8000';

function App() {
  const [data, setData] = useState<FactoryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [spotConfig, setSpotConfig] = useState<SpotConfig | null>(null);
  const [spotImageUrl, setSpotImageUrl] = useState('');
  const [spotImageError, setSpotImageError] = useState<string | null>(null);
  const [spotImageLoading, setSpotImageLoading] = useState(false);
  const [focusBusy, setFocusBusy] = useState(false);
  const spotHasImage = useRef(false);

  // --- Data Fetching Hooks (Same as before) ---
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
        ※ 작업자 주의사항<br />
        SPOT 온도가 <b>500°C</b> 이상일 경우 즉시 관리자에게 알림.<br />
        적외선 센서 조준 상태를 상시 확인하십시오.
      </p>
    </div>
  );

  // --- Scene Creation ---
  // Create the scene only once. Since ReactWidget uses model.useState(), 
  // simply calling setState on the model would update it, BUT our ReactWidget component
  // pulls fresh state from 'renderWidget' prop if we change it? 
  // Actually, standard Scene objects are static. We are passing a function `renderKpi`.
  // As `data` changes in App state, `renderKpi` (which closes over `data`) will return new JSX.
  // The Scene component needs to re-render.
  // `ReactWidget.Component` calls `model.useState()`. 
  // We need to trigger an update on the model when `data` changes?
  // Or simpler: The `ReactWidget` simply calls `renderWidget()` during its render.
  // If `App` re-renders, does the Scene re-render? 
  // Usually Scenes are self-contained. 
  // To force update, we might need a `useEffect` that calls `scene.setState({})` or similar.
  // However, since `renderKpi` is a closure, if `ReactWidget.Component` re-renders, it calls the *current* `renderKpi`?
  // No, `model` is constant. We passed `renderKpi` *at creation time*.
  // This `renderKpi` closure captures the *initial* `data` (null).
  // We need a ref to mutable data or use a context.
  // BETTER APPROACH: Use a `Context` provider wrapping the Scene, and have `renderWidget` use contexts.
  // OR: Use a mutable ref for the render functions.
  
  const dataRef = useRef(data);
  const spotConfigRef = useRef(spotConfig);
  dataRef.current = data;
  spotConfigRef.current = spotConfig;

  // We wrap the renderers to use the refs
  const sceneRenderers = useMemo(() => ({
    renderKpi: () => {
       const d = dataRef.current;
       if (!d) return <div>Loading...</div>;
       return (
        <div className="card kpi-card" style={{ height: '100%' }}>
          <div className="metric-row"><span>Speed</span><span className="value">{d.Speed}</span></div>
          <div className="metric-row"><span>Pressure</span><span className="value">{d.Press}</span></div>
          <div className="metric-row"><span>Count</span><span className="value">{d.Count}</span></div>
        </div>
       );
    },
    // ... Implement others similarly using refs ...
    // For brevity in this replace, I will assume the closure issue needs solving.
    // Actually, `ReactWidget` component is a React component. 
    // If we trigger a re-render of the Scene App, it might re-render.
    // But Scenes are optimized to NOT re-render the whole tree.
    // We should probably force update the scene implementation?
    // Let's use a "Force Update" on the scene object?
  }), []);

  // WAIT. Simplest way: The `renderWidget` function is stored in the model state.
  // We can update the model state when data changes.
  
  const scene = useMemo(() => getDashboardScene(
     () => <KpiComponent />,
     () => <SpotComponent />,
     () => <TempsComponent />,
     () => <MoldsComponent />,
     () => <CameraComponent />,
     renderNotice
  ), []); 

  // --- Layout Persistence ---
  const saveLayout = () => {
    // SceneGridLayout state contains the children with their current x,y,w,h
    const grid = scene.state.body;
    if (grid instanceof SceneGridLayout) {
       // Access internal state safely with casting
       const children = (grid.state as any).children || [];
       const layoutState = children.map((c: any) => ({
         x: c.state.x,
         y: c.state.y,
         width: c.state.width,
         height: c.state.height,
       }));
       localStorage.setItem('grafana_scene_layout_v1', JSON.stringify(layoutState));
       alert('Layout saved!');
    }
  };

  return (
    <div className="App" style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header className="app-header">
        <h1>창녕 2호기 (Grafana Scenes)</h1>
         <div className="header-controls" style={{ marginLeft: 'auto', display: 'flex', gap: '10px', alignItems: 'center', marginRight: '20px' }}>
            <button onClick={saveLayout} style={{ padding: '6px 12px', cursor: 'pointer' }}>Save Layout</button>
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
const DataContext = React.createContext<any>(null);

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
        <div className="hero-value">{data.Spot} °C</div>
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
