import React, { useEffect, useRef, useState } from 'react';
import { Responsive, useContainerWidth, cloneLayout, type Compactor } from 'react-grid-layout';
import axios from 'axios';
import { FactoryData, SpotConfig } from './types';
import './App.css';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const API_BASE = 'http://localhost:8000';
const GRID_ROW_HEIGHT = 15; // Much finer vertical control
const GRID_MARGIN = 8; // Tighter margins
const GRID_PADDING = 12;
const GRID_MAX_ROWS = 2000;
// Double again for ultra-fine control (48 cols for lg)
const GRID_COLS_BY_BREAKPOINT = { lg: 48, md: 40, sm: 24, xs: 16, xxs: 8 };

const ResponsiveGridLayout = Responsive;

// Default Layouts (Scaled x2 from previous 12-col layout)
const commonLayoutProps = {
  resizeHandles: ['s', 'e', 'w', 'se'],
};

const defaultLayouts = {
  lg: [
    { i: 'kpi', x: 0, y: 0, w: 12, h: 16, minW: 8, minH: 12, ...commonLayoutProps },
    { i: 'spot', x: 12, y: 0, w: 20, h: 8, minW: 12, minH: 8, ...commonLayoutProps },
    { i: 'temps', x: 12, y: 8, w: 20, h: 8, minW: 12, minH: 8, ...commonLayoutProps },
    { i: 'molds', x: 32, y: 0, w: 16, h: 16, minW: 12, minH: 12, ...commonLayoutProps },
    { i: 'camera', x: 0, y: 16, w: 24, h: 20, minW: 16, minH: 12, ...commonLayoutProps },
    { i: 'notice', x: 24, y: 16, w: 24, h: 20, minW: 12, minH: 12, ...commonLayoutProps },
  ],
  md: [ // Scaled for 40 cols
    { i: 'kpi', x: 0, y: 0, w: 12, h: 16, ...commonLayoutProps },
    { i: 'spot', x: 12, y: 0, w: 16, h: 8, ...commonLayoutProps },
    { i: 'temps', x: 12, y: 8, w: 16, h: 8, ...commonLayoutProps },
    { i: 'molds', x: 28, y: 0, w: 12, h: 16, ...commonLayoutProps },
    { i: 'camera', x: 0, y: 16, w: 20, h: 20, ...commonLayoutProps },
    { i: 'notice', x: 20, y: 16, w: 20, h: 20, ...commonLayoutProps },
  ],
  sm: [ // Scaled for 24 cols
    { i: 'kpi', x: 0, y: 0, w: 24, h: 12, ...commonLayoutProps },
    { i: 'spot', x: 0, y: 12, w: 24, h: 8, ...commonLayoutProps },
    { i: 'temps', x: 0, y: 20, w: 24, h: 8, ...commonLayoutProps },
    { i: 'molds', x: 0, y: 28, w: 24, h: 16, ...commonLayoutProps },
    { i: 'camera', x: 0, y: 44, w: 24, h: 20, ...commonLayoutProps },
    { i: 'notice', x: 0, y: 64, w: 24, h: 20, ...commonLayoutProps },
  ]
};

const LAYOUT_STORAGE_KEY = 'sfl_v2_layouts_v5';
const freeformCompactor: Compactor = {
  type: null,
  allowOverlap: true,
  compact: (layout) => cloneLayout(layout),
};
const LAYOUT_ORDER_BY_BREAKPOINT: Record<string, string[]> = Object.keys(defaultLayouts).reduce((acc, bp) => {
  acc[bp] = defaultLayouts[bp as keyof typeof defaultLayouts].map((item: any) => item.i);
  return acc;
}, {} as Record<string, string[]>);

const mergeLayouts = (base: any, defaults: any) => {
  const merged: any = {};
  const defaultKeys = Object.keys(defaults);

  defaultKeys.forEach((bp) => {
    const defaultItems = defaults[bp] || [];
    const existingItems = Array.isArray(base?.[bp]) ? base[bp] : [];
    const existingMap = new Map(existingItems.map((item: any) => [item.i, item]));

    const mergedItems = defaultItems.map((def: any) => ({
      ...def,
      ...(existingMap.get(def.i) || {}),
    }));

    existingItems.forEach((item: any) => {
      if (!defaultItems.some((def: any) => def.i === item.i)) {
        mergedItems.push(item);
      }
    });

    merged[bp] = mergedItems;
  });

  Object.keys(base || {}).forEach((bp) => {
    if (!merged[bp]) {
      merged[bp] = base[bp];
    }
  });

  return merged;
};

const clampLayoutItem = (item: any, cols: number) => {
  const minW = item.minW ?? 1;
  const minH = item.minH ?? 1;
  const maxW = Math.min(item.maxW ?? cols, cols);
  const w = Math.max(minW, Math.min(item.w ?? minW, maxW));
  const h = Math.max(minH, item.h ?? minH);
  const x = Math.max(0, Math.min(item.x ?? 0, cols - w));
  const y = Math.max(0, item.y ?? 0);
  return { ...item, w, h, x, y };
};

const itemsCollide = (a: any, b: any) =>
  a.x < b.x + b.w &&
  a.x + a.w > b.x &&
  a.y < b.y + b.h &&
  a.y + a.h > b.y;

const pushDownIfOverlapping = (items: any[], focusId: string, cols: number, maxRows: number) => {
  const map = new Map(items.map((item) => [item.i, clampLayoutItem(item, cols)]));
  const focus = map.get(focusId);
  if (!focus) {
    return items.map((item) => map.get(item.i) ?? item);
  }

  const fixed = Array.from(map.values()).filter((item) => item.i !== focusId);
  const moved = { ...focus };
  let guard = 0;
  while (fixed.some((other) => itemsCollide(moved, other))) {
    moved.y += 1;
    guard += 1;
    if (moved.y + moved.h > maxRows || guard > maxRows) {
      break;
    }
  }

  map.set(focusId, moved);
  return items.map((item) => map.get(item.i) ?? item);
};



const loadLayouts = () => {
  if (typeof window === 'undefined') {
    return defaultLayouts;
  }
  try {
    const raw = window.localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (!raw) {
      return defaultLayouts;
    }
    const parsed = JSON.parse(raw);
    return mergeLayouts(parsed, defaultLayouts);
  } catch (err) {
    console.warn('Layout restore failed, using defaults.', err);
    return defaultLayouts;
  }
};

function App() {
  const [layoutsState, setLayoutsState] = useState<any>(() => loadLayouts());
  const [data, setData] = useState<FactoryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [spotConfig, setSpotConfig] = useState<SpotConfig | null>(null);
  const [spotImageUrl, setSpotImageUrl] = useState('');
  const [spotImageError, setSpotImageError] = useState<string | null>(null);
  const [spotImageLoading, setSpotImageLoading] = useState(false);
  const [focusBusy, setFocusBusy] = useState(false);
  const [gridCols, setGridCols] = useState(GRID_COLS_BY_BREAKPOINT.lg);
  const [layoutLocked, setLayoutLocked] = useState(false);
  const [currentBreakpoint, setCurrentBreakpoint] = useState('lg');
  const currentBreakpointRef = useRef('lg');
  const lastMovedIdRef = useRef<string | null>(null);
  const lastInteractionLayoutRef = useRef<any[] | null>(null);
  const lastInteractionIdRef = useRef<string | null>(null);
  const skipNextLayoutChangeRef = useRef(false);
  const { width, containerRef, mounted } = useContainerWidth();
  const spotHasImage = useRef(false);

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

    const interval = setInterval(fetchData, 500); // 500ms polling
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
    if (!spotConfig || !spotConfig.image_url) {
      return;
    }

    const refreshMs = Math.max(500, Math.round(spotConfig.refresh_interval * 1000));
    const updateImage = () => {
      const separator = spotConfig.image_url.includes('?') ? '&' : '?';
      if (!spotHasImage.current) {
        setSpotImageLoading(true);
      }
      setSpotImageError(null);
      setSpotImageUrl(`${spotConfig.image_url}${separator}t=${Date.now()}`);
    };

    updateImage();
    const timer = setInterval(updateImage, refreshMs);
    return () => clearInterval(timer);
  }, [spotConfig]);

  const requestFocus = async (steps: number) => {
    if (!spotConfig?.focus_enabled || focusBusy) {
      return;
    }
    setFocusBusy(true);
    try {
      await axios.post(`${API_BASE}/api/spot/focus`, null, { params: { steps } });
    } catch (err) {
      console.error('SPOT focus error', err);
    } finally {
      setFocusBusy(false);
    }
  };

  const resetLayouts = () => {
    setLayoutsState(defaultLayouts);
    try {
      window.localStorage.removeItem(LAYOUT_STORAGE_KEY);
    } catch (err) {
      console.warn('Layout reset failed.', err);
    }
  };

  if (!data) return <div className="loading">Connecting to Factory...</div>;

  const buildLayouts = (layout: any, allLayouts: any, fallback: any) => {
    const base = allLayouts && Object.keys(allLayouts).length ? allLayouts : fallback;
    return {
      ...(base || {}),
      [currentBreakpointRef.current]: layout || [],
    };
  };

  const updateLayoutsState = (layout: any, allLayouts: any) => {
    if (skipNextLayoutChangeRef.current) {
      skipNextLayoutChangeRef.current = false;
      return;
    }
    setLayoutsState((prev: any) => buildLayouts(layout, allLayouts, prev));
  };

  const commitLayouts = (layout: any, allLayouts: any) => {
    skipNextLayoutChangeRef.current = true;
    setLayoutsState((prev: any) => {
      const layoutOverride =
        lastInteractionLayoutRef.current && lastInteractionIdRef.current === lastMovedIdRef.current
          ? lastInteractionLayoutRef.current
          : layout;
      const nextLayouts = buildLayouts(layoutOverride, allLayouts, prev);
      const merged = mergeLayouts(nextLayouts, defaultLayouts);
      const breakpoint = currentBreakpointRef.current;
      const cols = GRID_COLS_BY_BREAKPOINT[breakpoint as keyof typeof GRID_COLS_BY_BREAKPOINT] || GRID_COLS_BY_BREAKPOINT.lg;
      if (lastMovedIdRef.current && merged[breakpoint]) {
        merged[breakpoint] = pushDownIfOverlapping(merged[breakpoint], lastMovedIdRef.current, cols, GRID_MAX_ROWS);
      }
      try {
        window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(merged));
      } catch (err) {
        console.warn('Layout save failed.', err);
      }
      lastMovedIdRef.current = null;
      lastInteractionLayoutRef.current = null;
      lastInteractionIdRef.current = null;
      return merged;
    });
  };

  const spotCrosshair = spotConfig
    ? (() => {
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
          <svg
            className="camera-overlay"
            viewBox={`0 0 ${spotConfig.widget_width} ${spotConfig.widget_height}`}
            preserveAspectRatio="none"
          >
            {lines.map((line, idx) => (
              <g key={idx}>
                <line
                  x1={line.x1}
                  y1={line.y1}
                  x2={line.x2}
                  y2={line.y2}
                  stroke="black"
                  strokeWidth={thick + 2}
                  strokeDasharray="4 4"
                />
                <line
                  x1={line.x1}
                  y1={line.y1}
                  x2={line.x2}
                  y2={line.y2}
                  stroke={color}
                  strokeWidth={thick}
                  strokeDasharray="4 4"
                />
              </g>
            ))}
            <circle cx={cx} cy={cy} r={3} stroke="black" strokeWidth={3} fill="none" />
            <circle cx={cx} cy={cy} r={3} stroke={color} strokeWidth={1} fill="none" />
          </svg>
        );
      })()
    : null;

  return (
    <div className={`App ${layoutLocked ? 'layout-locked' : ''}`}>
      <header className="app-header">
        <h1>창녕 2호기 (V2 Web Dashboard)</h1>
        <div className="header-actions">
          <button
            type="button"
            className="layout-reset"
            onClick={resetLayouts}
          >
            배치 초기화
          </button>
          <button
            type="button"
            className={`layout-lock ${layoutLocked ? 'locked' : ''}`}
            onClick={() => setLayoutLocked(!layoutLocked)}
            aria-pressed={layoutLocked}
          >
            {layoutLocked ? '배치 잠금됨' : '배치 잠금'}
          </button>
          <div className="status-badge" style={{ backgroundColor: connected ? '#4ec9b0' : '#f14c4c' }}>
            {connected ? 'Running' : 'Offline'}
          </div>
        </div>
      </header>

      <div className="layout-container" ref={containerRef}>
        {mounted && width > 0 && (
          <ResponsiveGridLayout
            className="layout"
            width={width}
            layouts={layoutsState}
            breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
            cols={GRID_COLS_BY_BREAKPOINT}
            maxRows={GRID_MAX_ROWS}
            rowHeight={GRID_ROW_HEIGHT}
            margin={[GRID_MARGIN, GRID_MARGIN]}
            containerPadding={[GRID_PADDING, GRID_PADDING]}
            compactor={freeformCompactor}
            dragConfig={{
              enabled: !layoutLocked,
              bounded: false,
              handle: '.card-handle',
              cancel: '.no-drag,button,input,textarea,select,a,.react-resizable-handle',
              threshold: 0,
            }}
            resizeConfig={{
              enabled: !layoutLocked,
              handles: layoutLocked ? [] : ['s', 'e', 'w', 'se'],
            }}
            onLayoutChange={(layout: any, layouts: any) => {
              updateLayoutsState(layout, layouts);
            }}
            onBreakpointChange={(breakpoint: string, cols: number) => {
              setGridCols(cols);
              setCurrentBreakpoint(breakpoint);
              currentBreakpointRef.current = breakpoint;
            }}
            onResizeStart={(layout: any, oldItem: any, newItem: any, placeholder: any, e: any, element: any) => {
              console.warn('[Resize Start]', { i: newItem.i, x: newItem.x, y: newItem.y, w: newItem.w, h: newItem.h });
              lastMovedIdRef.current = newItem.i;
            }}
            onResize={(layout: any, oldItem: any, newItem: any, placeholder: any, e: any, element: any) => {
              console.warn('[Resizing]', { i: newItem.i, x: newItem.x, y: newItem.y, w: newItem.w, h: newItem.h });
              lastInteractionLayoutRef.current = layout;
              lastInteractionIdRef.current = newItem.i;
            }}
            onResizeStop={(layout: any, oldItem: any, newItem: any, placeholder: any, e: any, element: any) => {
              console.warn('[Resize Stop]', { i: newItem.i, x: newItem.x, y: newItem.y, w: newItem.w, h: newItem.h });
              commitLayouts(layout, null);
            }}
            onDragStart={(layout: any, oldItem: any, newItem: any, placeholder: any, e: any, element: any) => {
              console.warn('[Drag Start]', { i: newItem.i, x: newItem.x, y: newItem.y });
              lastMovedIdRef.current = newItem.i;
            }}
            onDrag={(layout: any, oldItem: any, newItem: any, placeholder: any, e: any, element: any) => {
              console.warn('[Dragging]', { i: newItem.i, x: newItem.x, y: newItem.y, placeholderY: placeholder?.y });
              lastInteractionLayoutRef.current = layout;
              lastInteractionIdRef.current = newItem.i;
            }}
            onDragStop={(layout: any, oldItem: any, newItem: any, placeholder: any, e: any, element: any) => {
              console.warn('[Drag Stop]', { i: newItem.i, x: newItem.x, y: newItem.y });
              lastMovedIdRef.current = newItem.i;
              commitLayouts(layout, null);
            }}
            style={
              {
                '--grid-cols': gridCols,
                '--grid-row': `${GRID_ROW_HEIGHT}px`,
                '--grid-gap': `${GRID_MARGIN}px`,
                '--grid-pad-x': `${GRID_PADDING}px`,
                '--grid-pad-y': `${GRID_PADDING}px`,
              } as React.CSSProperties
            }
          >
          <div key="kpi" className="card kpi-card">
            <h3 className="card-handle">Process KPI</h3>
            <div className="metric-row">
              <span>Speed</span>
              <span className="value">{data.Speed}</span>
            </div>
            <div className="metric-row">
              <span>Pressure</span>
              <span className="value">{data.Press}</span>
            </div>
            <div className="metric-row">
              <span>Count</span>
              <span className="value">{data.Count}</span>
            </div>
          </div>

          <div key="spot" className="card spot-card">
            <h3 className="card-handle">SPOT Temperature</h3>
            <div className="hero-value">{data.Spot} °C</div>
            <div className={`status-indicator ${data.Spot > 500 ? 'hot' : 'normal'}`}>
              {data.Spot > 500 ? 'HIGH TEMP' : 'NORMAL'}
            </div>
          </div>

          <div key="temps" className="card">
            <h3 className="card-handle">Secondary Temps</h3>
            <div className="grid-2">
              <div>
                CF: <b>{data.Temp_F}</b>
              </div>
              <div>
                CB: <b>{data.Temp_B}</b>
              </div>
              <div>
                BT: <b>{data.Billet_Temp}</b>
              </div>
              <div>
                BL: <b>{data.Billet_Length}</b>
              </div>
            </div>
          </div>

          <div key="molds" className="card">
            <h3 className="card-handle">Mold Zones</h3>
            <div className="mold-grid">
              <div>M1: {data.Mold1}</div>
              <div>M2: {data.Mold2}</div>
              <div>M3: {data.Mold3}</div>
              <div>M4: {data.Mold4}</div>
              <div>M5: {data.Mold5}</div>
              <div>M6: {data.Mold6}</div>
            </div>
          </div>

          <div key="camera" className="card camera-card">
            <h3 className="card-handle">SPOT Camera View</h3>
            <div className="camera-frame">
              {spotImageUrl && (
                <img
                  className="camera-image"
                  src={spotImageUrl}
                  alt="SPOT Camera"
                  onLoad={() => {
                    spotHasImage.current = true;
                    setSpotImageLoading(false);
                  }}
                  onError={() => {
                    setSpotImageLoading(false);
                    setSpotImageError('카메라 연결 실패');
                  }}
                />
              )}
              {spotCrosshair}
              {(spotImageLoading || spotImageError || !spotImageUrl) && (
                <div className={`camera-status ${spotImageError ? 'error' : ''}`}>
                  {spotImageError ? spotImageError : '카메라 연결 중...'}
                </div>
              )}
              {spotConfig?.focus_enabled && (
                <div className="camera-controls">
                  <button onClick={() => requestFocus(-1)} disabled={focusBusy}>
                    Focus -
                  </button>
                  <button onClick={() => requestFocus(1)} disabled={focusBusy}>
                    Focus +
                  </button>
                </div>
              )}
            </div>
          </div>

          <div key="notice" className="card notice-card">
            <h3 className="card-handle">OPERATOR CHECK</h3>
            <p className="notice-text">
              적외선 센서 조준 상태를 상시 확인하십시오. 제품 위치 변동 시 온도가 측정되지 않을 수 있습니다.
            </p>
          </div>
          </ResponsiveGridLayout>
        )}
      </div>
    </div>
  );
}

export default App;
