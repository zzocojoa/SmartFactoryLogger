/**
 * KPI Widget - 속도/압력/카운트/종료위치 표시
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React from 'react';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import { useLastValidNumber } from '../../../../shared/hooks/useLastValidNumber';
import { useSustainedFlag } from '../../../../shared/hooks/useSustainedFlag';
import { calcPercent } from '../../../../shared/utils/sparkline';
import { formatNumber, formatInteger, formatTime } from '../../../../shared/utils/formatters';
import { mapSpeedLevel, mapPressLevel, getSpeedState, getPressState } from '../../../../shared/utils/stateMappers';
import {
  SPEED_MAX,
  PRESS_MAX,
  PRESS_RUNNING_THRESHOLD,
  ALERT_HOLD_MS,
  ALERT_HOLD_LONG_MS,
} from '../../../../shared/constants/logic';

export const KpiComponent = React.memo(function KpiComponent() {
  const hasData = useDashboardStore(state => state.data !== null);
  const speed = useDashboardStore(state => state.data?.Speed);
  const press = useDashboardStore(state => state.data?.Press);
  const count = useDashboardStore(state => state.data?.Count);
  const endPos = useDashboardStore(state => state.data?.EndPos);
  const computedSpeedLevel = useDashboardStore(state => state.data?.Computed?.speed_level);
  const computedPressLevel = useDashboardStore(state => state.data?.Computed?.press_level);
  const computedJamLevel = useDashboardStore(state => state.data?.Computed?.jam_level);
  const computedSpeedThresholdHit = useDashboardStore(state => state.data?.Computed?.thresholds?.speed);
  const computedPressThresholdHit = useDashboardStore(state => state.data?.Computed?.thresholds?.press);
  const computedCountThresholdHit = useDashboardStore(state => state.data?.Computed?.thresholds?.count);
  const computedEndPosThresholdHit = useDashboardStore(state => state.data?.Computed?.thresholds?.endpos);
  const lastDataAt = useDashboardStore(state => {
    const speed = state.data?.Speed;
    const press = state.data?.Press;
    return !Number.isFinite(speed) || !Number.isFinite(press) ? state.lastDataAt : null;
  });
  const thresholdMasterOn = useDashboardStore(state => state.thresholds.masterOn);
  const thresholdSpeedEnabled = useDashboardStore(state => state.thresholds.entries.speed.enabled);
  const thresholdSpeedValue = useDashboardStore(state => state.thresholds.entries.speed.value);
  const thresholdPressEnabled = useDashboardStore(state => state.thresholds.entries.press.enabled);
  const thresholdPressValue = useDashboardStore(state => state.thresholds.entries.press.value);
  const thresholdCountEnabled = useDashboardStore(state => state.thresholds.entries.count.enabled);
  const thresholdCountValue = useDashboardStore(state => state.thresholds.entries.count.value);
  const thresholdEndPosEnabled = useDashboardStore(state => state.thresholds.entries.endpos.enabled);
  const thresholdEndPosValue = useDashboardStore(state => state.thresholds.entries.endpos.value);

  const speedValue = useLastValidNumber(speed);
  const pressValue = useLastValidNumber(press);
  const countValue = useLastValidNumber(count);
  const endPosValue = useLastValidNumber(endPos);

  const missing = !Number.isFinite(speed) || !Number.isFinite(press);
  const speedForLogic = speedValue ?? speed;
  const pressForLogic = pressValue ?? press;
  const safeSpeed = (typeof speedForLogic === 'number' && Number.isFinite(speedForLogic)) ? speedForLogic : 0;
  const safePress = (typeof pressForLogic === 'number' && Number.isFinite(pressForLogic)) ? pressForLogic : 0;
  const jamCondition = safeSpeed === 0 && safePress >= PRESS_RUNNING_THRESHOLD;
  const jamWarnFallback = useSustainedFlag(jamCondition, ALERT_HOLD_MS);
  const jamDangerFallback = useSustainedFlag(jamCondition, ALERT_HOLD_LONG_MS);
  const jamLevel = computedJamLevel;
  const jamWarn = jamLevel ? jamLevel === 'warn' : jamWarnFallback;
  const jamDanger = jamLevel ? jamLevel === 'danger' : jamDangerFallback;
  const speedPercent = calcPercent(safeSpeed, SPEED_MAX);
  const pressPercent = calcPercent(safePress, PRESS_MAX);
  const speedThresholdHit =
    computedSpeedThresholdHit ??
    (thresholdMasterOn && thresholdSpeedEnabled && thresholdSpeedValue !== null && typeof speedValue === 'number' && Number.isFinite(speedValue) && speedValue >= thresholdSpeedValue);
  const pressThresholdHit =
    computedPressThresholdHit ??
    (thresholdMasterOn && thresholdPressEnabled && thresholdPressValue !== null && typeof pressValue === 'number' && Number.isFinite(pressValue) && pressValue >= thresholdPressValue);
  const countThresholdHit =
    computedCountThresholdHit ??
    (thresholdMasterOn && thresholdCountEnabled && thresholdCountValue !== null && typeof countValue === 'number' && Number.isFinite(countValue) && countValue >= thresholdCountValue);
  const endPosThresholdHit =
    computedEndPosThresholdHit ??
    (thresholdMasterOn && thresholdEndPosEnabled && thresholdEndPosValue !== null && typeof endPosValue === 'number' && Number.isFinite(endPosValue) && endPosValue >= thresholdEndPosValue);
  const thresholdWarn = speedThresholdHit || pressThresholdHit || countThresholdHit || endPosThresholdHit;

  if (!hasData) return <div>Loading...</div>;

  const kpiAlertClass = jamDanger ? 'card-danger' : jamWarn || thresholdWarn ? 'card-warning' : '';
  const speedState = mapSpeedLevel(computedSpeedLevel) ?? getSpeedState(safeSpeed);
  const pressState = mapPressLevel(computedPressLevel) ?? getPressState(safePress);

  return (
    <div className={`card kpi-card ${kpiAlertClass}`}>
      <div className="kpi-metric">
        <div className="kpi-header">
          <span className="kpi-title">속도</span>
          <div className="kpi-header-meta">
            {speedThresholdHit && <span className="threshold-badge">임계</span>}
            <span className={`kpi-state ${speedState.className}`}>{speedState.label}</span>
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{formatNumber(speed ?? NaN, 1)}</span>
          <span className="kpi-unit">mm/s</span>
        </div>
        <div className="kpi-bar">
          <div className={`kpi-bar-fill ${speedState.className}`} style={{ width: `${speedPercent}%` }} />
        </div>
      </div>

      <div className="kpi-metric">
        <div className="kpi-header">
          <span className="kpi-title">압력</span>
          <div className="kpi-header-meta">
            {pressThresholdHit && <span className="threshold-badge">임계</span>}
            <span className={`kpi-state ${pressState.className}`}>{pressState.label}</span>
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{formatNumber(press ?? NaN, 1)}</span>
          <span className="kpi-unit">bar</span>
        </div>
        <div className="kpi-bar">
          <div className={`kpi-bar-fill ${pressState.className}`} style={{ width: `${pressPercent}%` }} />
        </div>
      </div>

      <div className="kpi-secondary">
        <div className={`kpi-mini ${countThresholdHit ? 'kpi-mini-threshold' : ''}`}>
          <div className="kpi-mini-header">
            <span className="kpi-mini-label">카운트</span>
            {countThresholdHit && <span className="threshold-badge">임계</span>}
          </div>
          <span className="kpi-mini-value">{formatInteger(count ?? 0)}</span>
        </div>
        <div className={`kpi-mini ${endPosThresholdHit ? 'kpi-mini-threshold' : ''}`}>
          <div className="kpi-mini-header">
            <span className="kpi-mini-label">종료 위치</span>
            {endPosThresholdHit && <span className="threshold-badge">임계</span>}
          </div>
          <div className="kpi-mini-value-row">
            <span className="kpi-mini-value">{formatNumber(endPos ?? NaN, 1)}</span>
            <span className="kpi-mini-unit">mm</span>
          </div>
        </div>
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
