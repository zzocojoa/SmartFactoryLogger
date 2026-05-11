import React, { useCallback, useEffect, useState } from 'react';
import uPlot from 'uplot';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import { useTheme } from '../../../../shared/hooks/useThemeContext';
import { SnapshotContext } from '../../context/SnapshotContext';
import { UIContext } from '../../context/UIContext';
import { TIME_SERIES_CATALOG } from '../../timeseries/seriesCatalog';
import {
  buildInitialActiveSeries,
  TimeSeriesChart,
  TimeSeriesHeader,
} from './TimeSeriesWidget.parts';

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

  useEffect(() => {
    if (uPlotInst === null) {
      return;
    }

    TIME_SERIES_CATALOG.forEach((meta, catalogIndex) => {
      uPlotInst.setSeries(catalogIndex + 1, { show: activeSeries[meta.key] });
    });
  }, [activeSeries, uPlotInst]);

  const toggleSeries = useCallback((key: string) => {
    const catalogIndex = TIME_SERIES_CATALOG.findIndex((meta) => meta.key === key);

    if (catalogIndex === -1) {
      return;
    }

    setActiveSeries((prev) => ({ ...prev, [key]: !prev[key] }));
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
        showThresholds={showThresholds}
        snapshotLoading={snapshotLoading}
        onSnapshot={handleSnapshot}
        onToggleSeries={toggleSeries}
        setSeriesPaused={setSeriesPaused}
        setSeriesWindowMin={setSeriesWindowMin}
        setShowThresholds={setShowThresholds}
      />

      <div style={{ flexGrow: 1, minHeight: 0 }}>
        <TimeSeriesChart
          activeSeries={activeSeries}
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
