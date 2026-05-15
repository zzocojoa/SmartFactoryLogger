import { memo, useEffect } from 'react';
import { useDashboardStore } from '../../../store/useDashboardStore';
import type { ThresholdState } from '../../../shared/types';
import { ALERT_HOLD_MS, SPOT_WARN_TEMP } from '../../../shared/constants/logic';
import { useLastValidNumber } from '../../../shared/hooks/useLastValidNumber';
import { useSustainedFlag } from '../../../shared/hooks/useSustainedFlag';
import { useMetricsViewModel } from '../hooks/useMetricsViewModel';
import type { UseMetricsViewModel } from '../hooks/useMetricsViewModel.types';

interface MetricsDataControllerProps {
  seriesPaused: boolean;
  seriesWindowMin: number;
  showThresholds: boolean;
  thresholdConfig: ThresholdState;
  timeSeriesFrameActive: boolean;
  intervalSec: number;
  thresholdState: ThresholdState;
}

type SeriesStatsSnapshot = ReturnType<UseMetricsViewModel['getSeriesStats']>;

interface MetricsStatusState {
  connected: boolean;
  latencyMs: number | null;
  pollingDegraded: boolean;
  pollingIntervalMs: number;
  pollingFailureCount: number;
  dashboardLeaderState: UseMetricsViewModel['dashboardLeaderState'];
  pollingPausedByVisibility: boolean;
  seriesStats: SeriesStatsSnapshot;
}

const MetricsDataControllerComponent = ({
  seriesPaused,
  seriesWindowMin,
  showThresholds,
  thresholdConfig,
  timeSeriesFrameActive,
  intervalSec,
  thresholdState,
}: MetricsDataControllerProps): null => {
  const setTimeSeriesState = useDashboardStore((state) => state.setTimeSeriesState);
  const setMetricsStatus = useDashboardStore((state) => state.setMetricsStatus);
  const setSpotAlertActive = useDashboardStore((state) => state.setSpotAlertActive);

  const {
    data,
    connected,
    lastDataAt,
    latencyMs,
    pollingDegraded,
    pollingIntervalMs,
    pollingFailureCount,
    dashboardLeaderState,
    pollingPausedByVisibility,
    timeSeriesAllFrame,
    getSeriesStats,
  } = useMetricsViewModel({
    seriesPaused,
    seriesWindowMin,
    showThresholds,
    thresholdConfig,
    timeSeriesFrameActive,
  });
  const lastSpotValue = useLastValidNumber(data?.Spot);
  const spotAlertFallback = useSustainedFlag(
    lastSpotValue !== null && lastSpotValue >= SPOT_WARN_TEMP,
    ALERT_HOLD_MS
  );
  const spotAlertActive = data?.Computed?.spot_warning ?? spotAlertFallback;

  useEffect(() => {
    setTimeSeriesState({
      timeSeriesAllFrame,
      thresholds: thresholdState,
      intervalSec,
    });
  }, [intervalSec, setTimeSeriesState, thresholdState, timeSeriesAllFrame]);

  useEffect(() => {
    const metricsStatus: MetricsStatusState = {
      connected,
      latencyMs,
      pollingDegraded,
      pollingIntervalMs,
      pollingFailureCount,
      dashboardLeaderState,
      pollingPausedByVisibility,
      seriesStats: getSeriesStats(),
    };

    setMetricsStatus(metricsStatus);
  }, [
    connected,
    dashboardLeaderState,
    getSeriesStats,
    lastDataAt,
    latencyMs,
    pollingDegraded,
    pollingFailureCount,
    pollingIntervalMs,
    pollingPausedByVisibility,
    setMetricsStatus,
    timeSeriesAllFrame,
  ]);

  useEffect(() => {
    setSpotAlertActive(spotAlertActive);
  }, [setSpotAlertActive, spotAlertActive]);

  return null;
};

export const MetricsDataController = memo(MetricsDataControllerComponent);
