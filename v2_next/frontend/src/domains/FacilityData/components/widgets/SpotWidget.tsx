/**
 * Spot Widget - SPOT 온도 게이지 + 스파크라인 표시
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import { useLastValidNumber } from '../../../../shared/hooks/useLastValidNumber';
import { buildSparklinePaths, calcPercent } from '../../../../shared/utils/sparkline';
import { isThresholdHit, getThresholdValue } from '../../../../shared/utils/thresholds';
import { formatNumber, formatTime } from '../../../../shared/utils/formatters';
import { mapSpotLevel, getSpotState } from '../../../../shared/utils/stateMappers';
import {
  SPOT_WARN_TEMP,
  SPOT_NORMAL_MIN,
  SPOT_HIGH_MIN,
  SPOT_MAX_TEMP,
  SPARKLINE_POINTS,
} from '../../../../shared/constants/logic';
import { SPOT_UNIT } from '../../../../shared/constants/uiText';

export const SpotComponent = React.memo(function SpotComponent() {
  const data = useDashboardStore(state => state.data);
  const lastDataAt = useDashboardStore(state => state.lastDataAt);
  const thresholds = useDashboardStore(state => state.thresholds);
  const spotAlertActive = useDashboardStore(state => state.spotAlertActive);

  const [sparklineValues, setSparklineValues] = useState<number[]>([]);
  const computed = data?.Computed;
  const spotInputValue = computed?.spot_level === 'idle' ? 0 : data?.Spot;
  const spotValue = useLastValidNumber(spotInputValue);

  const missing = !Number.isFinite(data?.Spot);
  const spotDisplayValue = Number.isFinite(spotValue ?? NaN) ? spotValue! : (spotInputValue ?? NaN);
  const spotState =
    mapSpotLevel(computed?.spot_level) ??
    getSpotState(spotDisplayValue, spotAlertActive, SPOT_WARN_TEMP, SPOT_HIGH_MIN, SPOT_NORMAL_MIN);
  const spotThresholdHit = computed?.thresholds?.spot ?? (thresholds ? isThresholdHit(thresholds, 'spot', spotValue) : false);
  const spotConfigThreshold = thresholds ? getThresholdValue(thresholds, 'spot') : null;
  const spotPercent = calcPercent(spotDisplayValue, SPOT_MAX_TEMP);
  const sparklineThresholds = useMemo(() => {
    const list = [SPOT_NORMAL_MIN, SPOT_HIGH_MIN, SPOT_WARN_TEMP];
    if (typeof spotConfigThreshold === 'number' && Number.isFinite(spotConfigThreshold)) {
      const exists = list.some((value) => Math.abs(value - spotConfigThreshold) < 0.01);
      if (!exists) {
        list.push(spotConfigThreshold);
      }
    }
    return list;
  }, [spotConfigThreshold]);
  const { linePath, areaPath, points, thresholdLines } = useMemo(
    () =>
      buildSparklinePaths(
        sparklineValues,
        100,
        60,
        sparklineThresholds,
        { min: SPOT_NORMAL_MIN, max: SPOT_WARN_TEMP }
      ),
    [sparklineValues, sparklineThresholds]
  );

  useEffect(() => {
    if (!Number.isFinite(spotDisplayValue)) {
      return;
    }
    setSparklineValues((prev) => {
      const next = [...prev, spotDisplayValue];
      if (next.length > SPARKLINE_POINTS) {
        next.splice(0, next.length - SPARKLINE_POINTS);
      }
      return next;
    });
  }, [spotDisplayValue]);

  if (!data) return <div>Loading...</div>;

  return (
    <div
      className={`card spot-card ${spotState.warning ? 'spot-danger' : spotThresholdHit ? 'spot-threshold' : 'spot-normal'}`}
      style={{ height: '100%' }}
    >
      <div className="spot-gauge">
        <svg viewBox="0 0 200 120" className="spot-gauge-svg" aria-hidden="true">
          <path
            className="spot-gauge-track"
            d="M20 100 A80 80 0 0 1 180 100"
            pathLength={100}
          />
          <path
            className={`spot-gauge-fill ${spotState.fillClass}`}
            d="M20 100 A80 80 0 0 1 180 100"
            pathLength={100}
            strokeDasharray={`${spotPercent} 100`}
          />
        </svg>
        <div className="spot-value">
          <span className="spot-value-number">{formatNumber(spotDisplayValue, 1)}</span>
          <span className="spot-unit">{SPOT_UNIT}</span>
        </div>
      </div>
      <div className="spot-status-row">
        <span className={`spot-status ${spotState.statusClass}`}>
          {spotState.label}
        </span>
        {spotThresholdHit && <span className="threshold-badge">임계</span>}
        {spotState.warning && (
          <span className="spot-alert-icon" aria-label="SPOT 경고">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 3L2 21h20L12 3zm0 5.5c.6 0 1 .4 1 1v5c0 .6-.4 1-1 1s-1-.4-1-1v-5c0-.6.4-1 1-1zm0 9c.7 0 1.3.6 1.3 1.3S12.7 20 12 20s-1.3-.6-1.3-1.3S11.3 17.5 12 17.5z" />
            </svg>
          </span>
        )}
      </div>
      <div className={`sparkline ${spotState.sparkClass}`}>
        <svg viewBox="0 0 100 60" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="spot-sparkline-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="var(--sparkline-color)" stopOpacity="0.35" />
              <stop offset="100%" stopColor="var(--sparkline-color)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {areaPath && <path className="sparkline-area" d={areaPath} />}
          {thresholdLines.map((line) => (
            <line
              key={`thr-${line.value}`}
              className={[
                'sparkline-threshold',
                line.value === SPOT_WARN_TEMP
                  ? 'sparkline-threshold-warn'
                  : line.value === SPOT_HIGH_MIN
                    ? 'sparkline-threshold-high'
                    : line.value === SPOT_NORMAL_MIN
                      ? 'sparkline-threshold-normal'
                      : '',
                typeof spotConfigThreshold === 'number' &&
                  Number.isFinite(spotConfigThreshold) &&
                  Math.abs(line.value - spotConfigThreshold) < 0.01
                  ? 'sparkline-threshold-config'
                  : '',
              ]
                .filter(Boolean)
                .join(' ')}
              x1={0}
              y1={line.y}
              x2={100}
              y2={line.y}
            />
          ))}
          {linePath && <path className="sparkline-path" d={linePath} />}
          {points.map((point, index) => (
            <circle
              key={`${point.x}-${point.y}-${index}`}
              className={`sparkline-dot ${index === points.length - 1 ? 'sparkline-dot-last' : ''}`}
              cx={point.x}
              cy={point.y}
              r={index === points.length - 1 ? 3 : 2}
            />
          ))}
        </svg>
      </div>
      {missing && (
        <div className="missing-note">
          마지막 갱신 {formatTime(lastDataAt)}
        </div>
      )}
    </div>
  );
}
);
