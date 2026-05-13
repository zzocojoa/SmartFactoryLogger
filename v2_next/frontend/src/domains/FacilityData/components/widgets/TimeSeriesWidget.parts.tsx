import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type uPlot from 'uplot';
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

type TooltipBounds = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type TooltipPosition = {
  x: number;
  y: number;
};

const clampNumber = (value: number, min: number, max: number): number => {
  return Math.min(Math.max(value, min), max);
};

const buildClampedTooltipPosition = (
  left: number,
  top: number,
  tooltipWidth: number,
  tooltipHeight: number,
  bounds: TooltipBounds
): TooltipPosition => {
  const padding = 8;
  const requestedX = left + 20;
  const requestedY = top;
  const minX = bounds.left + padding;
  const minY = bounds.top + padding;
  const maxX = bounds.left + bounds.width - tooltipWidth - padding;
  const maxY = bounds.top + bounds.height - tooltipHeight - padding;

  return {
    x: clampNumber(requestedX, minX, Math.max(minX, maxX)),
    y: clampNumber(requestedY, minY, Math.max(minY, maxY)),
  };
};

const buildWrapperLocalTooltipPosition = (
  cursorLeft: number,
  cursorTop: number,
  tooltipWidth: number,
  tooltipHeight: number,
  plotRect: TooltipBounds,
  wrapperRect: TooltipBounds
): TooltipPosition => {
  const plotLeft = plotRect.left - wrapperRect.left;
  const plotTop = plotRect.top - wrapperRect.top;

  return buildClampedTooltipPosition(
    plotLeft + cursorLeft,
    plotTop + cursorTop,
    tooltipWidth,
    tooltipHeight,
    {
      left: 0,
      top: 0,
      width: wrapperRect.width,
      height: wrapperRect.height,
    }
  );
};

const buildPlotRectFromCanvasBbox = (plot: uPlot, wrapperRect: TooltipBounds): TooltipBounds => {
  const pixelRatio = window.devicePixelRatio;

  return {
    left: wrapperRect.left + plot.bbox.left / pixelRatio,
    top: wrapperRect.top + plot.bbox.top / pixelRatio,
    width: plot.bbox.width / pixelRatio,
    height: plot.bbox.height / pixelRatio,
  };
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
  const [showAllSeries, setShowAllSeries] = useState<boolean>(false);
  const legendSeries = showAllSeries ? TIME_SERIES_CATALOG : LEGEND_SERIES;
  const hiddenActiveSeriesCount: number = Array.from(HIDDEN_BY_DEFAULT_SERIES).filter((key) => activeSeries[key]).length;
  const showHiddenActiveSeriesCount: boolean = !showAllSeries && hiddenActiveSeriesCount > 0;

  return (
    <div className="timeseries-legend" style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
      {legendSeries.map((meta) => {
        const isActive = activeSeries[meta.key];
        const color = SERIES_COLORS[meta.key] || '#888';

        return (
          <button
            key={meta.key}
            className={`timeseries-legend-button ${isActive ? 'active' : 'inactive'}`}
            aria-pressed={isActive}
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
              className="timeseries-legend-dot"
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: isActive ? color : 'var(--text-muted)',
              }}
            />
            <span className="timeseries-legend-label">{meta.label}</span>
            <span className="timeseries-legend-value" style={{ fontWeight: 600, marginLeft: '4px' }}>
              {formatCurrentValue(factoryData, meta.key)}
            </span>
          </button>
        );
      })}
      <button
        className={`timeseries-legend-button timeseries-legend-more ${showAllSeries ? 'active' : 'inactive'}`}
        aria-expanded={showAllSeries}
        onClick={() => setShowAllSeries((current) => !current)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '2px 8px',
          borderRadius: '12px',
          border: '1px solid var(--border-muted)',
          background: showAllSeries ? 'var(--bg-card)' : 'transparent',
          fontSize: '11px',
          color: showAllSeries ? 'var(--text-primary)' : 'var(--text-muted)',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
          opacity: showAllSeries ? 1 : 0.75,
        }}
      >
        <span>{showAllSeries ? '기본 범례' : '더 보기'}</span>
        {showHiddenActiveSeriesCount ? <span>(활성 {hiddenActiveSeriesCount})</span> : null}
      </button>
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
      className="timeseries-header"
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '6px 8px',
        borderBottom: '1px solid var(--border-muted)',
        background: 'var(--bg-card-muted)',
      }}
    >
      <TimeSeriesLegend activeSeries={activeSeries} onToggleSeries={onToggleSeries} />

      <div
        className="timeseries-controls"
        role="toolbar"
        aria-label="타임 시리즈 제어"
        title="타임 시리즈 제어"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}
      >
        <div className="series-group timeseries-window-group" role="group" aria-label="표시 시간 범위" title="표시 시간 범위">
          {SERIES_WINDOW_OPTIONS.map((min) => (
            <button
              key={min}
              className={`status-action ${seriesWindowMin === min ? 'active' : ''}`}
              aria-pressed={seriesWindowMin === min}
              title={`${min}분 보기`}
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
          className="series-density-badge timeseries-density-badge"
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
        <div
          className="timeseries-controls-divider"
          aria-hidden="true"
          style={{ width: '1px', height: '16px', background: 'var(--border-muted)', margin: '0 4px' }}
        />
        <button
          className={`status-action timeseries-pause-button ${seriesPaused ? 'warn' : ''}`}
          aria-pressed={seriesPaused}
          title={seriesPaused ? '실시간 업데이트 재개' : '실시간 업데이트 일시정지'}
          onClick={() => setSeriesPaused((prev) => !prev)}
        >
          {seriesPaused ? 'Paused' : 'Live'}
        </button>
        <label
          className="timeseries-threshold-label"
          title={LABELS.THRESHOLDS}
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
          <input
            type="checkbox"
            aria-label={LABELS.THRESHOLDS}
            checked={showThresholds}
            onChange={(event) => setShowThresholds(event.target.checked)}
          />
          {LABELS.THRESHOLDS}
        </label>
        <div
          className="timeseries-controls-divider"
          aria-hidden="true"
          style={{ width: '1px', height: '16px', background: 'var(--border-muted)', margin: '0 4px' }}
        />
        <button
          className={`status-action timeseries-snapshot-button ${snapshotLoading ? 'loading' : ''}`}
          onClick={onSnapshot}
          disabled={snapshotLoading}
          aria-busy={snapshotLoading}
          aria-label="전체 대시보드 스냅샷 저장"
          title="전체 대시보드 스냅샷 저장"
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

type ThresholdDrawState = {
  showThresholds: boolean;
  thresholds: ThresholdState | null;
};

export const TimeSeriesChart = React.memo(function TimeSeriesChart({
  activeSeries,
  mode,
  showThresholds,
  thresholds,
  timeSeriesAllFrame,
  onCreate,
}: TimeSeriesChartProps) {
  const chartWrapperRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const thresholdDrawStateRef = useRef<ThresholdDrawState>({ showThresholds, thresholds });
  const [uPlotInst, setUPlotInst] = useState<uPlot | null>(null);
  thresholdDrawStateRef.current = { showThresholds, thresholds };

  const thresholdRevision = useMemo(() => buildThresholdRevision(thresholds), [thresholds]);
  const handleCreate = useCallback((createdUPlotInst: uPlot): void => {
    setUPlotInst(createdUPlotInst);
    onCreate(createdUPlotInst);
  }, [onCreate]);

  useEffect(() => {
    if (uPlotInst === null) {
      return;
    }

    uPlotInst.redraw(false, false);
  }, [showThresholds, thresholdRevision, uPlotInst]);

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
            const thresholdDrawState = thresholdDrawStateRef.current;

            if (!thresholdDrawState.showThresholds || thresholdDrawState.thresholds === null || !thresholdDrawState.thresholds.masterOn) {
              return;
            }

            const { ctx } = plot;
            const { left, top, width, height } = plot.bbox;

            ctx.save();
            ctx.beginPath();

            THRESHOLD_KEYS.forEach((key) => {
              const entry = thresholdDrawState.thresholds?.entries[key];
              const color = getThresholdColor(key);

              if (entry === undefined || !entry.enabled || entry.value === null || color === null) {
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

            const tooltip = tooltipRef.current;
            const chartWrapper = chartWrapperRef.current;

            if (tooltip === null || chartWrapper === null) {
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
            const wrapperRect = chartWrapper.getBoundingClientRect();
            const plotRect = plot.over?.getBoundingClientRect() ?? buildPlotRectFromCanvasBbox(plot, wrapperRect);
            const tooltipPosition = buildWrapperLocalTooltipPosition(
              left,
              top,
              tooltip.offsetWidth,
              tooltip.offsetHeight,
              plotRect,
              wrapperRect
            );
            tooltip.style.transform = `translate(${tooltipPosition.x}px, ${tooltipPosition.y}px)`;
          },
        ],
      },
    };
  }, [activeSeries, mode]);

  if (uPlotData === null) {
    return (
      <div style={{ color: 'var(--text-muted)', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        Waiting for data...
      </div>
    );
  }

  return (
    <div ref={chartWrapperRef} style={{ position: 'relative', height: '100%', width: '100%' }}>
      <UPlotChart
        key={mode}
        data={uPlotData}
        options={uPlotOptions}
        height={400}
        className="uplot-container"
        onCreate={handleCreate}
      />
      <div ref={tooltipRef} className="uplot-tooltip" style={{ top: 0, left: 0 }} />
    </div>
  );
});
