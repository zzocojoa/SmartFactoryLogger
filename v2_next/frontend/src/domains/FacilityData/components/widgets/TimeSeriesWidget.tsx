/**
 * TimeSeriesWidget - uPlot 기반 시계열 차트 위젯
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React, { useMemo, useRef, useState } from 'react';
import uPlot from 'uplot';
import { FactoryDataContext } from '../../context/FactoryDataContext';
import { UIContext } from '../../context/UIContext';
import { SnapshotContext } from '../../context/SnapshotContext';
import { useTheme } from '../../../../shared/hooks/useThemeContext';
import { TIME_SERIES_CATALOG, SERIES_COLORS } from '../../timeseries/seriesCatalog';
import { THRESHOLD_LABELS } from '../../../../shared/utils/thresholds';
import type { ThresholdKey } from '../../../../shared/types';
import { LABELS } from '../../../../shared/constants/uiText';
const UPlotChart = React.lazy(() => import('../UPlotChart').then(m => ({ default: m.UPlotChart })));

const AIChatbot = React.lazy(() => import('../../../../AI/components/AIChatbot').then(m => ({ default: m.AIChatbot })));

  /* Chart Colors for Threshold Lines */
  const THRESHOLD_LINE_COLORS: Partial<Record<ThresholdKey, string>> = {
    speed: 'var(--color-speed)',
    press: 'var(--color-press)',
    spot: 'var(--color-spot)',
    temp_f: 'var(--color-temp-f)',
    temp_b: 'var(--color-temp-b)',
    billet: 'var(--color-billet-len)',
    billet_temp: 'var(--color-billet-temp)',
    at_temp: 'var(--color-env-temp)',
    at_pre: 'var(--color-env-pre)',
  };

export function TimeSeriesWidget() {
  const {
    data: factoryData,
    timeSeriesFrames,
    timeSeriesAllFrame,
    nowTick,
    intervalSec,
    thresholds
  } = React.useContext(FactoryDataContext);

  const {
    seriesWindowMin,
    setSeriesWindowMin,
    seriesPaused,
    setSeriesPaused,
    showThresholds,
    setShowThresholds,
  } = React.useContext(UIContext);

  const {
    handleSnapshot,
    snapshotLoading,
  } = React.useContext(SnapshotContext);

  const { mode } = useTheme();

  // Convert frames to Recharts data
  // Optimizing: Only rebuild when frames update
  // Use a ref to store the last valid data for freezing
  const lastChartDataRef = useRef<any[]>([]);

  // uPlot Instance State
  const [uPlotInst, setUPlotInst] = useState<uPlot | null>(null);
  
  // Active Series State (Tracking visibility for UI)
  // Initialize with Catalog defaults (Molds are hidden by default)
  const [activeSeries, setActiveSeries] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    TIME_SERIES_CATALOG.forEach(meta => {
        initial[meta.key] = !['Mold1','Mold2','Mold3','Mold4','Mold5','Mold6'].includes(meta.key);
    });
    return initial;
  });

  const toggleSeries = (key: string) => {
    if (!uPlotInst) return;
    
    // Find uPlot series index
    // Series 0 is Time. TIME_SERIES_CATALOG matches series 1..N
    const catIndex = TIME_SERIES_CATALOG.findIndex(m => m.key === key);
    if (catIndex === -1) return;
    
    const uPlotIndex = catIndex + 1;
    const currentShow = activeSeries[key];
    const newShow = !currentShow;
    
    // Update uPlot (Efficient, no React re-render of chart)
    uPlotInst.setSeries(uPlotIndex, { show: newShow });
    
    // Update React UI state (for Legend buttons)
    setActiveSeries(prev => ({ ...prev, [key]: newShow }));
  };

  // uPlot Data Preparation
  // Direct mapping from columnar timeSeriesAllFrame to uPlot's AlignedData (array of arrays)
  const uPlotData = useMemo<uPlot.AlignedData | null>(() => {
    if (!timeSeriesAllFrame) return null;
    
    // timeSeriesAllFrame fields are already sorted by TIME_SERIES_CATALOG
    // Field 0 is Time, others represent series in order
    // Ensure we are not passed nulls where arrays expected, though 'values' should be arrays.
    
    // We must ensure the structure is [ [time...], [series1...], [series2...] ]
    // which maps to field.values
    
    return timeSeriesAllFrame.fields.map((f, i) => {
        // Field 0 is Time (ms). uPlot prefers seconds.
        if (i === 0) {
            return f.values.map(v => (v || 0) / 1000);
        }
        return f.values;
    }) as uPlot.AlignedData;
  }, [timeSeriesAllFrame]);

  // uPlot Options
  const uPlotOptions = useMemo<uPlot.Options>(() => {
    const isDark = mode === 'dark' || document.body.getAttribute('data-theme') === 'night';
    const axisColor = isDark ? '#aaaaaa' : '#333333';

    
    return {
      title: "",
      width: 800, // Placeholder, autosized by component
      height: 400,
      mode: 1, // 1: equidistant, 2: non-equidistant
      scales: {
        x: {
          time: true,
        },
        y: {
          auto: true,
        }
      },
      series: [
        {
            label: "Time",
            value: (u, v) => v == null ? "-" : new Date(v * 1000).toLocaleTimeString(),
            stroke: axisColor,
        },
        ...TIME_SERIES_CATALOG.map(meta => ({
            label: meta.label,
            stroke: SERIES_COLORS[meta.key] || '#888',
            width: 2,
            points: { show: false }, // Disable dots for performance
            show: ['Mold1','Mold2','Mold3','Mold4','Mold5','Mold6'].includes(meta.key) ? false : true, // Hide Molds by default
            spanGaps: true,
        }))
      ],
      axes: [
        {
          scale: 'x',
          space: 50,
          stroke: axisColor,
          grid: { show: false },
          ticks: { show: true, stroke: axisColor, width: 1 },
          values: (u, vals, space) => vals.map(v => new Date(v * 1000).toLocaleTimeString('en-GB', { hour12: false }))
        },
        {
          scale: 'y',
          size: 50,
          stroke: axisColor,
          grid: { show: false },
          ticks: { show: true, stroke: axisColor, width: 1 },
          values: (u, vals, space) => vals.map(v => v.toFixed(1))
        }
      ],
      legend: {
        show: false, // Use Custom Legend
      },
      cursor: {
        drag: { x: true, y: true },
        points: { show: false }
      },
      hooks: {
        draw: [(u: uPlot) => {
          if (!showThresholds || !thresholds.masterOn) return;
          
          const { ctx } = u;
          const { left, top, width, height } = u.bbox;
          const seriesEntries = Object.keys(thresholds.entries) as ThresholdKey[];

          ctx.save();
          ctx.beginPath();
          
          seriesEntries.forEach(key => {
            const entry = thresholds.entries[key];
            const color = THRESHOLD_LINE_COLORS[key];
            
            if (!entry.enabled || entry.value === null || !color) return;

            // Resolve color variable if it starts with var(--) - uPlot Canvas won't resolve it automatically simply by fillStyle
            // Ideally we should use getComputedStyle, but for performance, we might assume hex or try simple resolution
            // Wait, SERIES_COLORS are hex, but THRESHOLD_LINE_COLORS are var(--...)
            // We need to resolve these. Or just use a fallback.
            // For now, let's assume 'color' string works if we can't resolve vars easily in canvas loop without perf hit.
            // Actually, ctx.fillStyle DOES support "var(--...)" in modern browsers? No, Canvas API does NOT support CSS variables directly.
            // We must resolve them.
            // Optimization: Variables are resolved in React style prop, but not in Canvas 2D Context.
            
            // Temporary Workaround: Use fixed colors or read from a hidden element (expensive).
            // Better: parse vars once. But they are simple. 
            // Let's use getComputedStyle(document.documentElement).getPropertyValue(...) inside the hook is ok? 
            // It will run every frame. 
            // Let's try to map keys to SERIES_COLORS if possible? 
            // Speed -> SERIES_COLORS['Speed']. 
            // Let's rely on SERIES_COLORS for mapping if keys match.
            // ThresholdKey: 'speed', 'press' ... 
            // Series Key is: 'Speed', 'Press' (Capitalized).
            
            // Mapping:
            const capKey = key.charAt(0).toUpperCase() + key.slice(1);
            let hexColor = SERIES_COLORS[capKey] || '#888888';
             // Special cases
            if (key === 'temp_f') hexColor = SERIES_COLORS['Temp_F'];
            if (key === 'temp_b') hexColor = SERIES_COLORS['Temp_B'];
            if (key === 'billet_temp') hexColor = SERIES_COLORS['Billet_Temp'];
            if (key === 'billet') hexColor = SERIES_COLORS['Billet_Length'];
            if (key === 'at_temp') hexColor = SERIES_COLORS['At_Temp'];
            if (key === 'at_pre') hexColor = SERIES_COLORS['At_Pre'];

            const yVal = entry.value!;
            // uPlot implicitly uses scale 'y' for values
            const yPos = u.valToPos(yVal, 'y', true);

            // Check if line is within visible area
            if (yPos < top || yPos > top + height) return;

            // Draw Line
            ctx.lineWidth = 1;         
            ctx.strokeStyle = hexColor;
            ctx.setLineDash([5, 5]); // Dashed line
            
            ctx.moveTo(left, yPos);
            ctx.lineTo(left + width, yPos);
            ctx.stroke();
            
            // Draw Label
            ctx.fillStyle = hexColor;
            ctx.font = "10px sans-serif";
            ctx.textAlign = "right";
            ctx.textBaseline = "bottom";
            ctx.fillText(THRESHOLD_LABELS[key] || key, left + width - 5, yPos - 2);
            
            ctx.beginPath(); // Reset path for next line
          });
          
          
          ctx.restore();
        }],
        setCursor: [(u: uPlot) => {
            if (!u.cursor) return;
            const { left, top, idx } = u.cursor;
            if (left === undefined || top === undefined) return;
            const tooltip = document.getElementById('uplot-tooltip');
            if (!tooltip) return;

            if (idx === null || idx === undefined) {
                tooltip.style.display = 'none';
                return;
            }

            // Data
            const xVal = u.data[0][idx];
            // Skip Time series (index 0)
            const activeSeriesIndices = u.series.map((s, i) => s.show ? i : -1).filter(i => i > 0);
            
            // Build HTML
            // Note: In React we usually avoid innerHTML, but for perf in 60fps hook it's acceptable/common in chart libs
            let html = `<div class="uplot-tooltip-time">${new Date(xVal * 1000).toLocaleTimeString('en-GB', { hour12: false })}</div>`;
            
            activeSeriesIndices.forEach(sIdx => {
                const s = u.series[sIdx];
                const val = u.data[sIdx][idx];
                const valStr = val != null ? val.toFixed(1) : '-';
                const color = s.stroke as string; // We know it's string
                
                html += `
                <div class="uplot-tooltip-item">
                    <div class="uplot-tooltip-label">
                        <div class="uplot-tooltip-dot" style="background-color: ${color}"></div>
                        <span>${s.label}</span>
                    </div>
                    <span class="uplot-tooltip-value">${valStr}</span>
                </div>
                `;
            });

            tooltip.innerHTML = html;
            tooltip.style.display = 'block';
            
            // Positioning
            const plotLeft = u.bbox.left;
            const plotTop = u.bbox.top;
            const container = u.root.querySelector('.u-over');
            if (!container) return;
            
            // Simple positioning: right of cursor + offset
            let cssLeft = left + 20;
            let cssTop = top;
            
            // Boundary detection could be added here
            
            tooltip.style.transform = `translate(${cssLeft}px, ${cssTop}px)`;
        }]
      }
    };
  }, [showThresholds, thresholds, mode]);

  if (!timeSeriesFrames) return <div style={{ color: 'white', padding: '16px' }}>Loading data...</div>;

  return (
    <div className="card timeseries-card" style={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Controls Header within the Widget */}
      {/* Joined Header: Legend (Left) + Controls (Right) */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '6px 8px',
        borderBottom: '1px solid var(--border-muted)',
        background: 'var(--bg-card-muted)',
        gap: '16px'
      }}>
        {/* Left: Custom Legend */}
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '6px',
        }}>
          {TIME_SERIES_CATALOG
              .filter(meta => !['Mold1', 'Mold2', 'Mold3', 'Mold4', 'Mold5', 'Mold6'].includes(meta.key))
              .map(meta => {
              const isActive = activeSeries[meta.key];
              const color = SERIES_COLORS[meta.key] || '#888';
              return (
                  <button
                      key={meta.key}
                      onClick={() => toggleSeries(meta.key)}
                      style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          border: `1px solid ${isActive ? color : 'var(--border-muted)'}`,
                          background: isActive ? `${color}20` : 'transparent', // 20 = ~12% opacity
                          fontSize: '11px',
                          color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                          opacity: isActive ? 1 : 0.6
                      }}
                  >
                      <div style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          backgroundColor: isActive ? color : 'var(--text-muted)'
                      }} />
                      <span>{meta.label}</span>
                      <span style={{ fontWeight: 600, marginLeft: '4px' }}>
                          {factoryData && typeof factoryData[meta.key] === 'number' 
                            ? (factoryData[meta.key] as number).toFixed(1) 
                            : '-'}
                      </span>
                  </button>
              );
          })}
        </div>

        {/* Right: Controls */}
        <div className="timeseries-controls" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <div className="series-group">
            {[1, 5, 10, 30, 60].map((min) => (
              <button
                key={min}
                className={`status-action ${seriesWindowMin === min ? 'active' : ''}`}
                style={{ minWidth: '32px', padding: '0 4px', opacity: seriesWindowMin === min ? 1 : 0.5, fontSize: '11px', height: '24px' }}
                onClick={() => setSeriesWindowMin(min)}
              >
                {min}m
              </button>
            ))}
          </div>
          <span
            className="series-density-badge"
            title="현재 수집 간격 기준 데이터 밀도"
            style={{
              fontSize: '10px',
              padding: '2px 8px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '10px',
              color: 'var(--text-muted)',
              whiteSpace: 'nowrap'
            }}
          >
            📊 {(1 / intervalSec).toFixed(0)}pt/s
          </span>
          <div style={{ width: '1px', height: '16px', background: 'var(--border-muted)', margin: '0 4px' }}></div>
          <button
            className={`status-action ${seriesPaused ? 'warn' : ''}`}
            onClick={() => setSeriesPaused((prev) => !prev)}
          >
            {seriesPaused ? 'Pause' : 'Live'}
          </button>
          <label style={{ display: 'flex', alignItems: 'center', fontSize: '11px', cursor: 'pointer', gap: '4px', userSelect: 'none', color: 'var(--text-secondary)' }}>
            <input
              type="checkbox"
              checked={showThresholds}
              onChange={(e) => setShowThresholds(e.target.checked)}
            />
            {LABELS.THRESHOLDS}
          </label>
          <div style={{ width: '1px', height: '16px', background: 'var(--border-muted)', margin: '0 4px' }}></div>
          <button
            className={`status-action ${snapshotLoading ? 'loading' : ''}`}
            onClick={handleSnapshot}
            disabled={snapshotLoading}
            title={LABELS.SAVE_SNAPSHOT}
          >
            스냅샷
          </button>
        </div>
      </div>

      <div style={{ flexGrow: 1, minHeight: 0 }}>
        {uPlotData ? (
          <div style={{ position: 'relative', height: '100%', width: '100%' }}>
            <UPlotChart 
                data={uPlotData} 
                options={uPlotOptions} 
                height={400} 
                className="uplot-container"
                onCreate={setUPlotInst}
            />
            <div id="uplot-tooltip" className="uplot-tooltip" style={{top: 0, left: 0}}></div>
          </div>
          ) : (
            <div style={{color: 'var(--text-muted)', display:'flex', justifyContent:'center', alignItems:'center', height:'100%'}}>
                Waiting for data...
            </div>
          )}
      </div>

      <AIChatbot />
    </div>
  );
};



