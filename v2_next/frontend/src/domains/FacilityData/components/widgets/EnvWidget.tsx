/**
 * Env Widget - 환경 온도/습도 표시
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React from 'react';
import { useShallow } from 'zustand/react/shallow';
import { selectDashboardEnvSlice, useDashboardStore } from '../../../../store/useDashboardStore';
import { useLastValidNumber } from '../../../../shared/hooks/useLastValidNumber';
import { formatNumber } from '../../../../shared/utils/formatters';
import { mapEnvTempLevel, mapEnvPreLevel, getEnvTempState, getEnvHumidityState } from '../../../../shared/utils/stateMappers';
import { LABELS, SPOT_UNIT } from '../../../../shared/constants/uiText';
import { MissingDataNote } from './MissingDataNote';

export const EnvComponent = React.memo(function EnvComponent() {
  const {
    tempRaw,
    humidityRaw,
    computedEnvTempLevel,
    computedEnvPreLevel,
    computedTempThresholdHit,
    computedHumidityThresholdHit,
    missing,
    thresholdMasterOn,
    thresholdAtTempEnabled,
    thresholdAtTempValue,
    thresholdAtPreEnabled,
    thresholdAtPreValue,
  } = useDashboardStore(useShallow(selectDashboardEnvSlice));

  const envTempValue = useLastValidNumber(tempRaw);
  const envHumidityValue = useLastValidNumber(humidityRaw);
  const tempDisplay = envTempValue ?? tempRaw ?? NaN;
  const humidityDisplay = envHumidityValue ?? humidityRaw ?? NaN;
  const tempState = mapEnvTempLevel(computedEnvTempLevel) ?? getEnvTempState(tempDisplay);
  const humidityState = mapEnvPreLevel(computedEnvPreLevel) ?? getEnvHumidityState(humidityDisplay);
  const configTempThresholdHit =
    thresholdMasterOn &&
    thresholdAtTempEnabled &&
    thresholdAtTempValue !== null &&
    typeof envTempValue === 'number' &&
    Number.isFinite(envTempValue) &&
    envTempValue >= thresholdAtTempValue;
  const configHumidityThresholdHit =
    thresholdMasterOn &&
    thresholdAtPreEnabled &&
    thresholdAtPreValue !== null &&
    typeof envHumidityValue === 'number' &&
    Number.isFinite(envHumidityValue) &&
    envHumidityValue >= thresholdAtPreValue;
  const tempThresholdHit = computedTempThresholdHit ?? configTempThresholdHit;
  const humidityThresholdHit =
    computedHumidityThresholdHit ?? configHumidityThresholdHit;
  return (
    <div className="card env-card" style={{ height: '100%' }}>
      <div className="env-grid">
        <div className={`env-tile ${tempThresholdHit ? 'env-threshold' : ''}`}>
          <div className="env-header">
            <span className="env-label">{LABELS.ENV_TEMP}</span>
            {tempThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
          </div>
          <div className="env-value-row">
            <span className="env-value">{formatNumber(tempDisplay ?? NaN, 1)}</span>
            <span className="env-unit">{SPOT_UNIT}</span>
          </div>
          <span className={`env-badge ${tempState.className}`}>{tempState.label}</span>
        </div>
        <div className={`env-tile ${humidityThresholdHit ? 'env-threshold' : ''}`}>
          <div className="env-header">
            <span className="env-label">{LABELS.ENV_HUMID}</span>
            {humidityThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
          </div>
          <div className="env-value-row">
            <span className="env-value">{formatNumber(humidityDisplay ?? NaN, 1)}</span>
            <span className="env-unit">%</span>
          </div>
          <span className={`env-badge ${humidityState.className}`}>{humidityState.label}</span>
        </div>
      </div>
      {missing && <MissingDataNote />}
    </div>
  );
}
);
