import React, { useCallback, useEffect, useState } from 'react';
import uPlot from 'uplot';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import { useTheme } from '../../../../shared/hooks/useThemeContext';
import { SnapshotContext } from '../../context/SnapshotContext';
import { UIContext } from '../../context/UIContext';
import { TIME_SERIES_CATALOG } from '../../timeseries/seriesCatalog';
import type { TimeSeriesKey } from '../../timeseries/seriesCatalog';
import {
  buildInitialActiveSeries,
  TIME_SERIES_DIMMED_ALPHA,
  TimeSeriesChart,
  TimeSeriesHeader,
} from './TimeSeriesWidget.parts';

type MutableUPlotSeries = uPlot.Series & {
  alpha?: number;
};

const DEFAULT_SERIES_WIDTH = 2;
const HIGHLIGHT_SERIES_WIDTH = 4;

const applyHighlightedSeriesStyle = (
  uPlotInst: uPlot,
  activeSeries: Record<string, boolean>,
  highlightedSeriesKey: TimeSeriesKey | null
): void => {
  const highlightActive = highlightedSeriesKey !== null && activeSeries[highlightedSeriesKey] === true;

  if (!highlightActive) {
    uPlotInst.setSeries(null, { focus: true });
  }

  TIME_SERIES_CATALOG.forEach((meta, catalogIndex) => {
    const seriesIndex = catalogIndex + 1;
    const series = uPlotInst.series[seriesIndex] as MutableUPlotSeries | undefined;

    if (series === undefined) {
      return;
    }

    const isHighlighted = highlightActive && meta.key === highlightedSeriesKey;
    series.width = isHighlighted ? HIGHLIGHT_SERIES_WIDTH : DEFAULT_SERIES_WIDTH;
    series.alpha = highlightActive && !isHighlighted ? TIME_SERIES_DIMMED_ALPHA : 1;

    if (isHighlighted) {
      uPlotInst.setSeries(seriesIndex, { focus: true });
    }
  });

  uPlotInst.redraw(false, false);
};

export const TimeSeriesWidget = React.memo(function TimeSeriesWidget() {
  const timeSeriesAllFrame = useDashboardStore((state) => state.timeSeriesAllFrame);
  const thresholds = useDashboardStore((state) => state.thresholds);
  const intervalSec = useDashboardStore((state) => state.intervalSec);

  const {
    seriesWindowMin,
    setSeriesWindowMin,
    seriesPaused,
    setSeriesPaused,
    showThresholds,
    setShowThresholds,
  } = React.useContext(UIContext);

  const { handleSnapshot, snapshotLoading } = React.useContext(SnapshotContext);
  const { mode } = useTheme();
  const [uPlotInst, setUPlotInst] = useState<uPlot | null>(null);
  const [activeSeries, setActiveSeries] = useState<Record<string, boolean>>(buildInitialActiveSeries);
  const [highlightedSeriesKey, setHighlightedSeriesKey] = useState<TimeSeriesKey | null>(null);

  useEffect(() => {
    if (uPlotInst === null) {
      return;
    }

    TIME_SERIES_CATALOG.forEach((meta, catalogIndex) => {
      uPlotInst.setSeries(catalogIndex + 1, { show: activeSeries[meta.key] });
    });
  }, [activeSeries, uPlotInst]);

  useEffect(() => {
    if (uPlotInst === null) {
      return;
    }

    applyHighlightedSeriesStyle(uPlotInst, activeSeries, highlightedSeriesKey);
  }, [activeSeries, highlightedSeriesKey, uPlotInst]);

  const toggleSeries = useCallback((key: TimeSeriesKey) => {
    const catalogIndex = TIME_SERIES_CATALOG.findIndex((meta) => meta.key === key);

    if (catalogIndex === -1) {
      return;
    }

    setActiveSeries((prev) => ({ ...prev, [key]: !prev[key] }));
    setHighlightedSeriesKey((current) => (current === key && activeSeries[key] === true ? null : current));
  }, [activeSeries]);

  const highlightSeries = useCallback((key: TimeSeriesKey) => {
    if (activeSeries[key] !== true) {
      return;
    }

    setHighlightedSeriesKey(key);
  }, [activeSeries]);

  const clearHighlightedSeries = useCallback(() => {
    setHighlightedSeriesKey(null);
  }, []);

  if (timeSeriesAllFrame === null) {
    return <div style={{ color: 'white', padding: '16px' }}>Loading data...</div>;
  }

  return (
    <div className="card timeseries-card" style={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column' }}>
      <TimeSeriesHeader
        activeSeries={activeSeries}
        intervalSec={intervalSec}
        seriesPaused={seriesPaused}
        seriesWindowMin={seriesWindowMin}
        highlightedSeriesKey={highlightedSeriesKey}
        showThresholds={showThresholds}
        snapshotLoading={snapshotLoading}
        onClearHighlightedSeries={clearHighlightedSeries}
        onHighlightSeries={highlightSeries}
        onSnapshot={handleSnapshot}
        onToggleSeries={toggleSeries}
        setSeriesPaused={setSeriesPaused}
        setSeriesWindowMin={setSeriesWindowMin}
        setShowThresholds={setShowThresholds}
      />

      <div className="timeseries-chart-wrapper" style={{ flexGrow: 1, minHeight: 0 }}>
        <TimeSeriesChart
          activeSeries={activeSeries}
          highlightedSeriesKey={highlightedSeriesKey}
          mode={mode}
          showThresholds={showThresholds}
          thresholds={thresholds}
          timeSeriesAllFrame={timeSeriesAllFrame}
          onCreate={setUPlotInst}
        />
      </div>
    </div>
  );
});
