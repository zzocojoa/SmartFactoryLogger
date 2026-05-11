import React, { useMemo } from 'react';
import uPlot from 'uplot';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import type { FactoryData, ThresholdKey, ThresholdState } from '../../../../shared/types';
import { LABELS } from '../../../../shared/constants/uiText';
import { THRESHOLD_LABELS } from '../../../../shared/utils/thresholds';
import { SERIES_COLORS, TIME_SERIES_CATALOG } from '../../timeseries/seriesCatalog';
import type { TimeSeriesKey } from '../../timeseries/seriesCatalog';
import type { SeriesFrame } from '../../timeseries/seriesDataFrames';

const UPlotChart = React.lazy(() => import('../UPlotChart').then((module) => ({ default: module.UPlotChart })));

const HIDDEN_BY_DEFAULT_SERIES: ReadonlySet<TimeSeriesKey> = new Set<TimeSeriesKey>([
  'Mold1',
  'Mold2',
  'Mold3',
  'Mold4',
  'Mold5',
  'Mold6',
]);

const LEGEND_SERIES = TIME_SERIES_CATALOG.filter((meta) => !HIDDEN_BY_DEFAULT_SERIES.has(meta.key));
const SERIES_WINDOW_OPTIONS: number[] = [1, 5, 10, 30, 60];
const THRESHOLD_KEYS: ThresholdKey[] = [
  'speed',
  'press',
  'spot',
  'temp_f',
  'temp_b',
  'billet',
  'billet_temp',
  'at_temp',
  'at_pre',
  'count',
  'endpos',
];

const THRESHOLD_SERIES_KEYS: Record<ThresholdKey, TimeSeriesKey | null> = {
  speed: 'Speed',
  press: 'Press',
  spot: 'Spot',
  temp_f: 'Temp_F',
  temp_b: 'Temp_B',
  billet: 'Billet_Length',
  billet_temp: 'Billet_Temp',
  at_temp: 'At_Temp',
  at_pre: 'At_Pre',
  count: null,
  endpos: null,
};

export const buildInitialActiveSeries = (): Record<string, boolean> => {
  return TIME_SERIES_CATALOG.reduce<Record<string, boolean>>((activeSeries, meta) => {
    return {
      ...activeSeries,
      [meta.key]: !HIDDEN_BY_DEFAULT_SERIES.has(meta.key),
    };
  }, {});
};

const formatCurrentValue = (factoryData: FactoryData | null, key: TimeSeriesKey): string => {
  const value = factoryData !== null ? factoryData[key] : null;
  return typeof value === 'number' ? value.toFixed(1) : '-';
};

const buildThresholdRevision = (thresholds: ThresholdState | null): string => {
  if (thresholds === null) {
    return 'none';
  }

  const entriesRevision = THRESHOLD_KEYS.map((key) => {
    const entry = thresholds.entries[key];
    const value = entry.value !== null ? entry.value.toString() : 'null';
    return `${key}:${entry.enabled ? '1' : '0'}:${value}`;
  }).join('|');

  return `${thresholds.masterOn ? '1' : '0'}|${entriesRevision}`;
};

const getThresholdColor = (key: ThresholdKey): string | null => {
  const seriesKey = THRESHOLD_SERIES_KEYS[key];
  return seriesKey !== null ? SERIES_COLORS[seriesKey] : null;
};

type TimeSeriesLegendProps = {
  activeSeries: Record<string, boolean>;
  onToggleSeries: (key: string) => void;
};

export const TimeSeriesLegend = React.memo(function TimeSeriesLegend({
  activeSeries,
  onToggleSeries,
}: TimeSeriesLegendProps) {
  const factoryData = useDashboardStore((state) => state.data);

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
      {LEGEND_SERIES.map((meta) => {
        const isActive = activeSeries[meta.key];
        const color = SERIES_COLORS[meta.key] || '#888';

        return (
          <button
            key={meta.key}
            onClick={() => onToggleSeries(meta.key)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '2px 8px',
              borderRadius: '12px',
              border: `1px solid ${isActive ? color : 'var(--border-muted)'}`,
              background: isActive ? `${color}20` : 'transparent',
              fontSize: '11px',
              color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              opacity: isActive ? 1 : 0.6,
            }}
          >
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: isActive ? color : 'var(--text-muted)',
              }}
            />
            <span>{meta.label}</span>
            <span style={{ fontWeight: 600, marginLeft: '4px' }}>
              {formatCurrentValue(factoryData, meta.key)}
            </span>
          </button>
        );
      })}
    </div>
  );
});

type TimeSeriesHeaderProps = {
  activeSeries: Record<string, boolean>;
  intervalSec: number;
  seriesPaused: boolean;
  seriesWindowMin: number;
  showThresholds: boolean;
  snapshotLoading: boolean;
  onSnapshot: () => void;
  onToggleSeries: (key: string) => void;
  setSeriesPaused: React.Dispatch<React.SetStateAction<boolean>>;
  setSeriesWindowMin: (min: number) => void;
  setShowThresholds: (show: boolean) => void;
};

export const TimeSeriesHeader = React.memo(function TimeSeriesHeader({
  activeSeries,
  intervalSec,
  seriesPaused,
  seriesWindowMin,
  showThresholds,
  snapshotLoading,
  onSnapshot,
  onToggleSeries,
  setSeriesPaused,
  setSeriesWindowMin,
  setShowThresholds,
}: TimeSeriesHeaderProps) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '6px 8px',
        borderBottom: '1px solid var(--border-muted)',
        background: 'var(--bg-card-muted)',
        gap: '16px',
      }}
    >
      <TimeSeriesLegend activeSeries={activeSeries} onToggleSeries={onToggleSeries} />

      <div
        className="timeseries-controls"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}
      >
        <div className="series-group">
          {SERIES_WINDOW_OPTIONS.map((min) => (
            <button
              key={min}
              className={`status-action ${seriesWindowMin === min ? 'active' : ''}`}
              style={{
                minWidth: '32px',
                padding: '0 4px',
                opacity: seriesWindowMin === min ? 1 : 0.5,
                fontSize: '11px',
                height: '24px',
              }}
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
            whiteSpace: 'nowrap',
          }}
        >
          {(1 / intervalSec).toFixed(0)}pt/s
        </span>
        <div style={{ width: '1px', height: '16px', background: 'var(--border-muted)', margin: '0 4px' }} />
        <button className={`status-action ${seriesPaused ? 'warn' : ''}`} onClick={() => setSeriesPaused((prev) => !prev)}>
          {seriesPaused ? 'Pause' : 'Live'}
        </button>
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            fontSize: '11px',
            cursor: 'pointer',
            gap: '4px',
            userSelect: 'none',
            color: 'var(--text-secondary)',
          }}
        >
          <input type="checkbox" checked={showThresholds} onChange={(event) => setShowThresholds(event.target.checked)} />
          {LABELS.THRESHOLDS}
        </label>
        <div style={{ width: '1px', height: '16px', background: 'var(--border-muted)', margin: '0 4px' }} />
        <button
          className={`status-action ${snapshotLoading ? 'loading' : ''}`}
          onClick={onSnapshot}
          disabled={snapshotLoading}
          title={LABELS.SAVE_SNAPSHOT}
        >
          스냅샷
        </button>
      </div>
    </div>
  );
});

type TimeSeriesChartProps = {
  activeSeries: Record<string, boolean>;
  mode: string;
  showThresholds: boolean;
  thresholds: ThresholdState | null;
  timeSeriesAllFrame: SeriesFrame | null;
  onCreate: (uPlotInst: uPlot) => void;
};

export const TimeSeriesChart = React.memo(function TimeSeriesChart({
  activeSeries,
  mode,
  showThresholds,
  thresholds,
  timeSeriesAllFrame,
  onCreate,
}: TimeSeriesChartProps) {
  const uPlotData = useMemo<uPlot.AlignedData | null>(() => {
    if (timeSeriesAllFrame === null) {
      return null;
    }

    return timeSeriesAllFrame.fields.map((field, index) => {
      if (index === 0) {
        return field.values.map((value) => (value ?? 0) / 1000);
      }

      return field.values;
    }) as uPlot.AlignedData;
  }, [timeSeriesAllFrame]);

  const uPlotOptions = useMemo<uPlot.Options>(() => {
    const isDark = mode === 'dark' || document.body.getAttribute('data-theme') === 'night';
    const axisColor = isDark ? '#aaaaaa' : '#333333';

    return {
      title: '',
      width: 800,
      height: 400,
      mode: 1,
      scales: {
        x: {
          time: true,
        },
        y: {
          auto: true,
        },
      },
      series: [
        {
          label: 'Time',
          value: (_u, value) => (value == null ? '-' : new Date(value * 1000).toLocaleTimeString()),
          stroke: axisColor,
        },
        ...TIME_SERIES_CATALOG.map((meta) => ({
          label: meta.label,
          stroke: SERIES_COLORS[meta.key] || '#888',
          width: 2,
          points: { show: false },
          show: activeSeries[meta.key] ?? !HIDDEN_BY_DEFAULT_SERIES.has(meta.key),
          spanGaps: true,
        })),
      ],
      axes: [
        {
          scale: 'x',
          space: 50,
          stroke: axisColor,
          grid: { show: false },
          ticks: { show: true, stroke: axisColor, width: 1 },
          values: (_u, values) => values.map((value) => new Date(value * 1000).toLocaleTimeString('en-GB', { hour12: false })),
        },
        {
          scale: 'y',
          size: 50,
          stroke: axisColor,
          grid: { show: false },
          ticks: { show: true, stroke: axisColor, width: 1 },
          values: (_u, values) => values.map((value) => value.toFixed(1)),
        },
      ],
      legend: {
        show: false,
      },
      cursor: {
        drag: { x: true, y: true },
        points: { show: false },
      },
      hooks: {
        draw: [
          (plot: uPlot) => {
            if (!showThresholds || thresholds === null || !thresholds.masterOn) {
              return;
            }

            const { ctx } = plot;
            const { left, top, width, height } = plot.bbox;

            ctx.save();
            ctx.beginPath();

            THRESHOLD_KEYS.forEach((key) => {
              const entry = thresholds.entries[key];
              const color = getThresholdColor(key);

              if (!entry.enabled || entry.value === null || color === null) {
                return;
              }

              const yPos = plot.valToPos(entry.value, 'y', true);

              if (yPos < top || yPos > top + height) {
                return;
              }

              ctx.lineWidth = 1;
              ctx.strokeStyle = color;
              ctx.setLineDash([5, 5]);
              ctx.moveTo(left, yPos);
              ctx.lineTo(left + width, yPos);
              ctx.stroke();

              ctx.fillStyle = color;
              ctx.font = '10px sans-serif';
              ctx.textAlign = 'right';
              ctx.textBaseline = 'bottom';
              ctx.fillText(THRESHOLD_LABELS[key] || key, left + width - 5, yPos - 2);
              ctx.beginPath();
            });

            ctx.restore();
          },
        ],
        setCursor: [
          (plot: uPlot) => {
            if (!plot.cursor) {
              return;
            }

            const { left, top, idx } = plot.cursor;

            if (left === undefined || top === undefined) {
              return;
            }

            const tooltip = document.getElementById('uplot-tooltip');

            if (tooltip === null) {
              return;
            }

            if (idx === null || idx === undefined) {
              tooltip.style.display = 'none';
              return;
            }

            const xVal = plot.data[0][idx];
            const timeLabel = typeof xVal === 'number' ? new Date(xVal * 1000).toLocaleTimeString('en-GB', { hour12: false }) : '-';
            const activeSeriesIndices = plot.series.map((series, index) => (series.show ? index : -1)).filter((index) => index > 0);
            const itemsHtml = activeSeriesIndices.map((seriesIndex) => {
              const series = plot.series[seriesIndex];
              const value = plot.data[seriesIndex][idx];
              const valueText = typeof value === 'number' ? value.toFixed(1) : '-';
              const color = String(series.stroke);

              return `
                <div class="uplot-tooltip-item">
                  <div class="uplot-tooltip-label">
                    <div class="uplot-tooltip-dot" style="background-color: ${color}"></div>
                    <span>${series.label}</span>
                  </div>
                  <span class="uplot-tooltip-value">${valueText}</span>
                </div>
              `;
            }).join('');

            tooltip.innerHTML = `<div class="uplot-tooltip-time">${timeLabel}</div>${itemsHtml}`;
            tooltip.style.display = 'block';
            tooltip.style.transform = `translate(${left + 20}px, ${top}px)`;
          },
        ],
      },
    };
  }, [activeSeries, mode, showThresholds, thresholds]);

  const chartKey = useMemo(() => {
    return `${mode}:${showThresholds ? 'thresholds-on' : 'thresholds-off'}:${buildThresholdRevision(thresholds)}`;
  }, [mode, showThresholds, thresholds]);

  if (uPlotData === null) {
    return (
      <div style={{ color: 'var(--text-muted)', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        Waiting for data...
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', height: '100%', width: '100%' }}>
      <UPlotChart
        key={chartKey}
        data={uPlotData}
        options={uPlotOptions}
        height={400}
        className="uplot-container"
        onCreate={onCreate}
      />
      <div id="uplot-tooltip" className="uplot-tooltip" style={{ top: 0, left: 0 }} />
    </div>
  );
});
