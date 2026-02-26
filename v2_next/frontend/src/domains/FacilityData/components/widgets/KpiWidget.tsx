/**
 * KPI Widget - 속도/압력/카운트/종료위치 표시
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React from 'react';
import { FactoryDataContext } from '../../context/FactoryDataContext';
import { useLastValidNumber } from '../../../../shared/hooks/useLastValidNumber';
import { useSustainedFlag } from '../../../../shared/hooks/useSustainedFlag';
import { calcPercent } from '../../../../shared/utils/sparkline';
import { isThresholdHit } from '../../../../shared/utils/thresholds';
import { formatNumber, formatInteger, formatTime } from '../../../../shared/utils/formatters';
import { mapSpeedLevel, mapPressLevel, getSpeedState, getPressState } from '../../../../shared/utils/stateMappers';
import {
  SPEED_MAX,
  PRESS_MAX,
  PRESS_RUNNING_THRESHOLD,
  ALERT_HOLD_MS,
  ALERT_HOLD_LONG_MS,
} from '../../../../shared/constants/logic';

export function KpiComponent() {
  const { data, lastDataAt, thresholds } = React.useContext(FactoryDataContext);
  const speedValue = useLastValidNumber(data?.Speed);
  const pressValue = useLastValidNumber(data?.Press);
  const countValue = useLastValidNumber(data?.Count);
  const endPosValue = useLastValidNumber(data?.EndPos);

  const missing = !Number.isFinite(data?.Speed) || !Number.isFinite(data?.Press);
  const speedForLogic = speedValue ?? data?.Speed;
  const pressForLogic = pressValue ?? data?.Press;
  const safeSpeed = (typeof speedForLogic === 'number' && Number.isFinite(speedForLogic)) ? speedForLogic : 0;
  const safePress = (typeof pressForLogic === 'number' && Number.isFinite(pressForLogic)) ? pressForLogic : 0;
  const jamCondition = safeSpeed === 0 && safePress >= PRESS_RUNNING_THRESHOLD;
  const jamWarnFallback = useSustainedFlag(jamCondition, ALERT_HOLD_MS);
  const jamDangerFallback = useSustainedFlag(jamCondition, ALERT_HOLD_LONG_MS);
  const computed = data?.Computed;
  const jamLevel = computed?.jam_level;
  const jamWarn = jamLevel ? jamLevel === 'warn' : jamWarnFallback;
  const jamDanger = jamLevel ? jamLevel === 'danger' : jamDangerFallback;
  const speedPercent = calcPercent(safeSpeed, SPEED_MAX);
  const pressPercent = calcPercent(safePress, PRESS_MAX);
  const computedThresholds = computed?.thresholds;
  const speedThresholdHit = computedThresholds?.speed ?? isThresholdHit(thresholds, 'speed', speedValue);
  const pressThresholdHit = computedThresholds?.press ?? isThresholdHit(thresholds, 'press', pressValue);
  const countThresholdHit = computedThresholds?.count ?? isThresholdHit(thresholds, 'count', countValue);
  const endPosThresholdHit = computedThresholds?.endpos ?? isThresholdHit(thresholds, 'endpos', endPosValue);
  const thresholdWarn = speedThresholdHit || pressThresholdHit || countThresholdHit || endPosThresholdHit;

  if (!data) return <div>Loading...</div>;

  const kpiAlertClass = jamDanger ? 'card-danger' : jamWarn || thresholdWarn ? 'card-warning' : '';
  const speedState = mapSpeedLevel(computed?.speed_level) ?? getSpeedState(safeSpeed);
  const pressState = mapPressLevel(computed?.press_level) ?? getPressState(safePress);

  return (
    <div className={`card kpi-card ${kpiAlertClass}`} style={{ height: '100%' }}>
      <div className="kpi-metric">
        <div className="kpi-header">
          <span className="kpi-title">속도</span>
          <div className="kpi-header-meta">
            {speedThresholdHit && <span className="threshold-badge">임계</span>}
            <span className={`kpi-state ${speedState.className}`}>{speedState.label}</span>
          </div>
        </div>
        <div className="kpi-value-row">
          <span className="kpi-value">{formatNumber(data.Speed ?? NaN, 1)}</span>
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
          <span className="kpi-value">{formatNumber(data.Press ?? NaN, 1)}</span>
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
          <span className="kpi-mini-value">{formatInteger(data.Count ?? 0)}</span>
        </div>
        <div className={`kpi-mini ${endPosThresholdHit ? 'kpi-mini-threshold' : ''}`}>
          <div className="kpi-mini-header">
            <span className="kpi-mini-label">종료 위치</span>
            {endPosThresholdHit && <span className="threshold-badge">임계</span>}
          </div>
          <div className="kpi-mini-value-row">
            <span className="kpi-mini-value">{formatNumber(data.EndPos ?? NaN, 1)}</span>
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
