import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type uPlot from 'uplot';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import type { FactoryData, ThresholdKey, ThresholdState } from '../../../../shared/types';
import { LABELS } from '../../../../shared/constants/uiText';
import { THRESHOLD_LABELS } from '../../../../shared/utils/thresholds';
import { SERIES_COLORS, TIME_SERIES_CATALOG } from '../../timeseries/seriesCatalog';
import type { TimeSeriesKey, TimeSeriesMeta } from '../../timeseries/seriesCatalog';
import type { SeriesFrame } from '../../timeseries/seriesDataFrames';
import type { SeriesFrameField } from '../../timeseries/seriesDataFrames.types';

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
export const TIME_SERIES_DIMMED_ALPHA = 0.26;
const DEFAULT_CHART_PIXEL_WIDTH = 800;
const MIN_RENDER_POINTS = 300;
const MAX_RENDER_POINTS = 4000;
const RENDER_POINTS_PER_PIXEL = 2;
const SPEED_SERIES_KEY: TimeSeriesKey = 'Speed';
const SPEED_RIGHT_SCALE_KEY = 'speedRight';
type TimeWindowRange = [number, number];
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

export const getActiveTimeSeriesMetas = (activeSeries: Record<string, boolean>): TimeSeriesMeta[] => {
  return TIME_SERIES_CATALOG.filter((meta) => activeSeries[meta.key] ?? !HIDDEN_BY_DEFAULT_SERIES.has(meta.key));
};

const buildChartSeriesSignature = (metas: readonly TimeSeriesMeta[]): string => {
  return metas.map((meta) => meta.key).join(',');
};

const getFieldBySeriesKey = (timeSeriesAllFrame: SeriesFrame, key: TimeSeriesKey): SeriesFrameField => {
  const field = timeSeriesAllFrame.fields.find((candidate) => candidate.name === key);

  if (field === undefined) {
    throw new Error(`Time series field was not found: key=${key}`);
  }

  return field;
};

const buildRenderPointLimit = (chartPixelWidth: number): number => {
  const finiteWidth = Number.isFinite(chartPixelWidth) && chartPixelWidth > 0 ? chartPixelWidth : DEFAULT_CHART_PIXEL_WIDTH;
  const widthLimit = Math.floor(finiteWidth * RENDER_POINTS_PER_PIXEL);
  return Math.max(MIN_RENDER_POINTS, Math.min(MAX_RENDER_POINTS, widthLimit));
};

const getNumericDataSeries = (uPlotData: uPlot.AlignedData): Array<Array<number | null>> => {
  const dataSeries: Array<Array<number | null>> = [];

  for (let seriesIndex = 1; seriesIndex < uPlotData.length; seriesIndex += 1) {
    const values = uPlotData[seriesIndex] as Array<number | null>;

    if (values.some((value) => typeof value === 'number' && Number.isFinite(value))) {
      dataSeries.push(values);
    }
  }

  return dataSeries;
};

const buildBucketExtremaIndices = (
  dataSeries: Array<Array<number | null>>,
  startIndex: number,
  endIndex: number
): number[] => {
  const selectedIndices = new Set<number>();

  dataSeries.forEach((values) => {
    let minIndex = -1;
    let maxIndex = -1;
    let minValue = Number.POSITIVE_INFINITY;
    let maxValue = Number.NEGATIVE_INFINITY;

    for (let index = startIndex; index < endIndex; index += 1) {
      const value = values[index];

      if (typeof value !== 'number' || !Number.isFinite(value)) {
        continue;
      }

      if (value < minValue) {
        minValue = value;
        minIndex = index;
      }

      if (value > maxValue) {
        maxValue = value;
        maxIndex = index;
      }
    }

    if (minIndex !== -1) {
      selectedIndices.add(minIndex);
    }

    if (maxIndex !== -1) {
      selectedIndices.add(maxIndex);
    }
  });

  if (selectedIndices.size === 0) {
    return [Math.floor((startIndex + endIndex - 1) / 2)];
  }

  return Array.from(selectedIndices).sort((left, right) => left - right);
};

const buildDownsampledIndices = (uPlotData: uPlot.AlignedData, maxPoints: number): number[] => {
  const timeValues = uPlotData[0];
  const pointCount = timeValues.length;

  if (pointCount <= maxPoints) {
    return Array.from(timeValues, (_value, index) => index);
  }

  const dataSeries = getNumericDataSeries(uPlotData);

  if (dataSeries.length === 0) {
    const step = pointCount <= 1 ? 1 : (pointCount - 1) / (maxPoints - 1);
    const selectedIndices = new Set<number>([0, pointCount - 1]);

    for (let index = 1; index < maxPoints - 1; index += 1) {
      selectedIndices.add(Math.round(index * step));
    }

    return Array.from(selectedIndices).sort((left, right) => left - right);
  }

  const maxIndicesPerBucket = Math.max(1, dataSeries.length * 2);
  const bucketCount = Math.max(1, Math.floor((maxPoints - 2) / maxIndicesPerBucket));
  const bucketSize = (pointCount - 2) / bucketCount;
  const selectedIndices = new Set<number>([0, pointCount - 1]);

  for (let bucketIndex = 0; bucketIndex < bucketCount; bucketIndex += 1) {
    const startIndex = Math.max(1, Math.floor(1 + bucketIndex * bucketSize));
    const endIndex = Math.min(pointCount - 1, Math.floor(1 + (bucketIndex + 1) * bucketSize));
    const safeEndIndex = Math.max(startIndex + 1, endIndex);

    buildBucketExtremaIndices(dataSeries, startIndex, safeEndIndex).forEach((index) => {
      selectedIndices.add(index);
    });
  }

  return Array.from(selectedIndices).sort((left, right) => left - right).slice(0, maxPoints);
};

const downsampleUPlotData = (uPlotData: uPlot.AlignedData, maxPoints: number): uPlot.AlignedData => {
  const selectedIndices = buildDownsampledIndices(uPlotData, maxPoints);

  if (selectedIndices.length === uPlotData[0].length) {
    return uPlotData;
  }

  return uPlotData.map((values) => selectedIndices.map((index) => values[index] ?? null)) as uPlot.AlignedData;
};

const assertAlignedUPlotData = (uPlotData: uPlot.AlignedData): void => {
  const pointCount = uPlotData[0].length;

  uPlotData.forEach((values, seriesIndex) => {
    if (values.length !== pointCount) {
      throw new Error(`Time series aligned data length mismatch: seriesIndex=${seriesIndex}, expected=${pointCount}, actual=${values.length}.`);
    }
  });
};

const isChronologicalUPlotData = (uPlotData: uPlot.AlignedData): boolean => {
  const timeValues = uPlotData[0];

  for (let index = 1; index < timeValues.length; index += 1) {
    const previousValue = timeValues[index - 1];
    const currentValue = timeValues[index];

    if (typeof previousValue === 'number' && typeof currentValue === 'number' && currentValue < previousValue) {
      return false;
    }
  }

  return true;
};

const sortUPlotDataByTime = (uPlotData: uPlot.AlignedData): uPlot.AlignedData => {
  if (isChronologicalUPlotData(uPlotData)) {
    return uPlotData;
  }

  const sortedIndices = Array.from(uPlotData[0], (_value, index) => index).sort((leftIndex, rightIndex) => {
    const leftValue = uPlotData[0][leftIndex];
    const rightValue = uPlotData[0][rightIndex];
    const leftTime = typeof leftValue === 'number' && Number.isFinite(leftValue) ? leftValue : Number.POSITIVE_INFINITY;
    const rightTime = typeof rightValue === 'number' && Number.isFinite(rightValue) ? rightValue : Number.POSITIVE_INFINITY;

    if (leftTime === rightTime) {
      return leftIndex - rightIndex;
    }

    return leftTime - rightTime;
  });

  return uPlotData.map((values) => sortedIndices.map((index) => values[index] ?? null)) as uPlot.AlignedData;
};

const buildVisibleUPlotData = (
  timeSeriesAllFrame: SeriesFrame,
  metas: readonly TimeSeriesMeta[],
  chartPixelWidth: number
): uPlot.AlignedData => {
  const timeField = timeSeriesAllFrame.fields[0];

  if (timeField === undefined || timeField.type !== 'time') {
    throw new Error('Time series frame must include a time field at index 0.');
  }

  const projectedData = [
    timeField.values.map((value) => (value ?? 0) / 1000),
    ...metas.map((meta) => getFieldBySeriesKey(timeSeriesAllFrame, meta.key).values),
  ] as uPlot.AlignedData;

  assertAlignedUPlotData(projectedData);

  return downsampleUPlotData(sortUPlotDataByTime(projectedData), buildRenderPointLimit(chartPixelWidth));
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

const getSeriesScaleKey = (key: TimeSeriesKey, speedRightAxisEnabled: boolean): string => {
  return speedRightAxisEnabled && key === SPEED_SERIES_KEY ? SPEED_RIGHT_SCALE_KEY : 'y';
};

const getThresholdScaleKey = (key: ThresholdKey, speedRightAxisEnabled: boolean): string => {
  return speedRightAxisEnabled && key === 'speed' ? SPEED_RIGHT_SCALE_KEY : 'y';
};

const getTooltipSeriesColor = (seriesIndex: number, series: uPlot.Series, chartSeriesMetas: readonly TimeSeriesMeta[]): string => {
  const meta = chartSeriesMetas[seriesIndex - 1];

  if (meta !== undefined) {
    return SERIES_COLORS[meta.key] ?? '#888';
  }

  return typeof series.stroke === 'string' ? series.stroke : '#888';
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

export const buildTimeWindowRange = (
  uPlotData: uPlot.AlignedData | null,
  seriesWindowMin: number
): TimeWindowRange | null => {
  const timeValues = uPlotData?.[0] as ArrayLike<number | null> | undefined;
  const windowSec = seriesWindowMin * 60;

  if (timeValues === undefined || timeValues.length === 0 || !Number.isFinite(windowSec) || windowSec <= 0) {
    return null;
  }

  const latestValue = timeValues[timeValues.length - 1];

  if (typeof latestValue !== 'number' || !Number.isFinite(latestValue)) {
    return null;
  }

  return [latestValue - windowSec, latestValue];
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
  highlightedSeriesKey: TimeSeriesKey | null;
  onClearHighlightedSeries: () => void;
  onHighlightSeries: (key: TimeSeriesKey) => void;
  onToggleSeries: (key: TimeSeriesKey) => void;
};

export const TimeSeriesLegend = React.memo(function TimeSeriesLegend({
  activeSeries,
  highlightedSeriesKey,
  onClearHighlightedSeries,
  onHighlightSeries,
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
        const isHighlighted = highlightedSeriesKey === meta.key && isActive;
        const color = SERIES_COLORS[meta.key] || '#888';

        return (
          <button
            key={meta.key}
            className={`timeseries-legend-button ${isActive ? 'active' : 'inactive'} ${isHighlighted ? 'highlighted' : ''}`}
            aria-pressed={isActive}
            aria-current={isHighlighted ? 'true' : undefined}
            onClick={() => onToggleSeries(meta.key)}
            onFocus={() => onHighlightSeries(meta.key)}
            onMouseEnter={() => onHighlightSeries(meta.key)}
            style={{
              '--timeseries-series-color': color,
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
            } as React.CSSProperties}
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
      {highlightedSeriesKey !== null ? (
        <button
          className="timeseries-legend-button timeseries-highlight-clear"
          type="button"
          onClick={onClearHighlightedSeries}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            padding: '2px 8px',
            borderRadius: '12px',
            border: '1px solid var(--border-muted)',
            background: 'transparent',
            fontSize: '11px',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
        >
          강조 해제
        </button>
      ) : null}
    </div>
  );
});

type TimeSeriesHeaderProps = {
  activeSeries: Record<string, boolean>;
  highlightedSeriesKey: TimeSeriesKey | null;
  intervalSec: number;
  seriesPaused: boolean;
  seriesWindowMin: number;
  speedRightAxisEnabled: boolean;
  showThresholds: boolean;
  snapshotLoading: boolean;
  onClearHighlightedSeries: () => void;
  onHighlightSeries: (key: TimeSeriesKey) => void;
  onSnapshot: () => void;
  onToggleSeries: (key: TimeSeriesKey) => void;
  setSeriesPaused: React.Dispatch<React.SetStateAction<boolean>>;
  setSeriesWindowMin: (min: number) => void;
  setSpeedRightAxisEnabled: React.Dispatch<React.SetStateAction<boolean>>;
  setShowThresholds: (show: boolean) => void;
};

export const TimeSeriesHeader = React.memo(function TimeSeriesHeader({
  activeSeries,
  highlightedSeriesKey,
  intervalSec,
  seriesPaused,
  seriesWindowMin,
  speedRightAxisEnabled,
  showThresholds,
  snapshotLoading,
  onClearHighlightedSeries,
  onHighlightSeries,
  onSnapshot,
  onToggleSeries,
  setSeriesPaused,
  setSeriesWindowMin,
  setSpeedRightAxisEnabled,
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
      <TimeSeriesLegend
        activeSeries={activeSeries}
        highlightedSeriesKey={highlightedSeriesKey}
        onClearHighlightedSeries={onClearHighlightedSeries}
        onHighlightSeries={onHighlightSeries}
        onToggleSeries={onToggleSeries}
      />

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
        <button
          className={`status-action timeseries-speed-axis-button ${speedRightAxisEnabled ? 'active' : ''}`}
          aria-label="압출 속도 오른쪽 Y축"
          aria-pressed={speedRightAxisEnabled}
          title={speedRightAxisEnabled ? '압출 속도를 왼쪽 Y축으로 표시' : '압출 속도만 오른쪽 Y축으로 표시'}
          onClick={() => setSpeedRightAxisEnabled((current) => !current)}
        >
          속도 Y2
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
  highlightedSeriesKey: TimeSeriesKey | null;
  mode: string;
  seriesWindowMin: number;
  showThresholds: boolean;
  speedRightAxisEnabled: boolean;
  thresholds: ThresholdState | null;
  timeSeriesAllFrame: SeriesFrame | null;
  onCreate: (uPlotInst: uPlot | null) => void;
};

type ThresholdDrawState = {
  showThresholds: boolean;
  speedRightAxisEnabled: boolean;
  thresholds: ThresholdState | null;
};

export const TimeSeriesChart = React.memo(function TimeSeriesChart({
  activeSeries,
  highlightedSeriesKey,
  mode,
  seriesWindowMin,
  showThresholds,
  speedRightAxisEnabled,
  thresholds,
  timeSeriesAllFrame,
  onCreate,
}: TimeSeriesChartProps) {
  const chartWrapperRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const thresholdDrawStateRef = useRef<ThresholdDrawState>({ showThresholds, speedRightAxisEnabled, thresholds });
  const highlightedSeriesKeyRef = useRef<TimeSeriesKey | null>(highlightedSeriesKey);
  const timeWindowRangeRef = useRef<TimeWindowRange | null>(null);
  const [uPlotInst, setUPlotInst] = useState<uPlot | null>(null);
  const [chartPixelWidth, setChartPixelWidth] = useState<number>(DEFAULT_CHART_PIXEL_WIDTH);
  thresholdDrawStateRef.current = { showThresholds, speedRightAxisEnabled, thresholds };
  highlightedSeriesKeyRef.current = highlightedSeriesKey;

  const chartSeriesMetas = useMemo<TimeSeriesMeta[]>(() => getActiveTimeSeriesMetas(activeSeries), [activeSeries]);
  const chartSeriesSignature = useMemo<string>(() => buildChartSeriesSignature(chartSeriesMetas), [chartSeriesMetas]);
  const showSpeedRightAxis = speedRightAxisEnabled && chartSeriesMetas.some((meta) => meta.key === SPEED_SERIES_KEY);
  const thresholdRevision = useMemo(() => buildThresholdRevision(thresholds), [thresholds]);
  const handleCreate = useCallback((createdUPlotInst: uPlot): void => {
    setUPlotInst(createdUPlotInst);
    onCreate(createdUPlotInst);
  }, [onCreate]);

  useEffect(() => {
    if (chartSeriesMetas.length > 0) {
      return;
    }

    setUPlotInst(null);
    onCreate(null);
  }, [chartSeriesMetas.length, onCreate]);

  useEffect(() => {
    const chartWrapper = chartWrapperRef.current;

    if (chartWrapper === null) {
      return undefined;
    }

    const updateChartPixelWidth = (): void => {
      const nextWidth = chartWrapper.clientWidth || chartWrapper.getBoundingClientRect().width || DEFAULT_CHART_PIXEL_WIDTH;
      setChartPixelWidth((currentWidth) => (Math.round(currentWidth) === Math.round(nextWidth) ? currentWidth : nextWidth));
    };

    updateChartPixelWidth();

    if (typeof ResizeObserver === 'undefined') {
      return undefined;
    }

    const resizeObserver = new ResizeObserver(updateChartPixelWidth);
    resizeObserver.observe(chartWrapper);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

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

    return buildVisibleUPlotData(timeSeriesAllFrame, chartSeriesMetas, chartPixelWidth);
  }, [chartPixelWidth, chartSeriesMetas, timeSeriesAllFrame]);
  timeWindowRangeRef.current = buildTimeWindowRange(uPlotData, seriesWindowMin);

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
          range: (_plot, initMin, initMax) => timeWindowRangeRef.current ?? [initMin, initMax],
        },
        y: {
          auto: true,
        },
        ...(showSpeedRightAxis ? {
          [SPEED_RIGHT_SCALE_KEY]: {
            auto: true,
          },
        } : {}),
      },
      series: [
        {
          label: 'Time',
          value: (_u, value) => (value == null ? '-' : new Date(value * 1000).toLocaleTimeString()),
          stroke: axisColor,
        },
        ...chartSeriesMetas.map((meta) => ({
          label: meta.label,
          scale: getSeriesScaleKey(meta.key, showSpeedRightAxis),
          stroke: SERIES_COLORS[meta.key] || '#888',
          width: 2,
          points: { show: false },
          show: true,
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
        ...(showSpeedRightAxis ? [
          {
            scale: SPEED_RIGHT_SCALE_KEY,
            side: 1,
            size: 56,
            stroke: SERIES_COLORS[SPEED_SERIES_KEY],
            grid: { show: false },
            ticks: { show: true, stroke: SERIES_COLORS[SPEED_SERIES_KEY], width: 1 },
            values: (_u: uPlot, values: number[]) => values.map((value) => value.toFixed(1)),
          },
        ] : []),
      ],
      legend: {
        show: false,
      },
      focus: {
        alpha: TIME_SERIES_DIMMED_ALPHA,
      },
      cursor: {
        drag: { x: true, y: true },
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
              const seriesKey = THRESHOLD_SERIES_KEYS[key];

              if (
                entry === undefined ||
                !entry.enabled ||
                entry.value === null ||
                color === null ||
                (seriesKey !== null && !chartSeriesMetas.some((meta) => meta.key === seriesKey))
              ) {
                return;
              }

              const scaleKey = getThresholdScaleKey(key, thresholdDrawState.speedRightAxisEnabled);
              const yPos = plot.valToPos(entry.value, scaleKey, true);

              if (!Number.isFinite(yPos) || yPos < top || yPos > top + height) {
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
            const highlightedSeriesIndex = highlightedSeriesKeyRef.current === null
              ? null
              : chartSeriesMetas.findIndex((meta) => meta.key === highlightedSeriesKeyRef.current) + 1;
            const tooltipSeriesIndices = [...activeSeriesIndices].sort((leftSeriesIndex, rightSeriesIndex) => {
              if (leftSeriesIndex === highlightedSeriesIndex) {
                return -1;
              }

              if (rightSeriesIndex === highlightedSeriesIndex) {
                return 1;
              }

              return leftSeriesIndex - rightSeriesIndex;
            });
            const useDenseTooltip = tooltipSeriesIndices.length > 8;
            const itemsHtml = tooltipSeriesIndices.map((seriesIndex) => {
              const series = plot.series[seriesIndex];
              const value = plot.data[seriesIndex][idx];
              const valueText = typeof value === 'number' ? value.toFixed(1) : '-';
              const color = getTooltipSeriesColor(seriesIndex, series, chartSeriesMetas);
              const isHighlighted = seriesIndex === highlightedSeriesIndex;

              return `
                <div class="uplot-tooltip-item ${isHighlighted ? 'is-highlighted' : ''}" style="--uplot-series-color: ${color}">
                  <div class="uplot-tooltip-label">
                    <div class="uplot-tooltip-dot" style="background-color: ${color}"></div>
                    <span>${series.label}</span>
                  </div>
                  <span class="uplot-tooltip-value">${valueText}</span>
                </div>
              `;
            }).join('');

            tooltip.innerHTML = `
              <div class="uplot-tooltip-time">${timeLabel}</div>
              <div class="uplot-tooltip-items ${useDenseTooltip ? 'is-dense' : ''}">${itemsHtml}</div>
            `;
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
  }, [chartSeriesMetas, mode, showSpeedRightAxis]);

  if (uPlotData === null) {
    return (
      <div style={{ color: 'var(--text-muted)', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        Waiting for data...
      </div>
    );
  }

  if (chartSeriesMetas.length === 0) {
    return (
      <div style={{ color: 'var(--text-muted)', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        표시할 시리즈를 선택하세요.
      </div>
    );
  }

  return (
    <div ref={chartWrapperRef} style={{ position: 'relative', height: '100%', width: '100%' }}>
      <UPlotChart
        configKey={`${mode}:${showSpeedRightAxis ? SPEED_RIGHT_SCALE_KEY : 'singleY'}:${chartSeriesSignature}`}
        data={uPlotData}
        options={uPlotOptions}
        resetScalesKey={seriesWindowMin}
        height={400}
        className="uplot-container"
        onCreate={handleCreate}
      />
      <div ref={tooltipRef} className="uplot-tooltip" style={{ top: 0, left: 0 }} />
    </div>
  );
});
