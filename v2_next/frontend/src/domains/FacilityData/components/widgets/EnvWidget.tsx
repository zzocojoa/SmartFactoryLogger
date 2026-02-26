/**
 * Env Widget - 환경 온도/습도 표시
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React from 'react';
import { FactoryDataContext } from '../../context/FactoryDataContext';
import { useLastValidNumber } from '../../../../shared/hooks/useLastValidNumber';
import { isThresholdHit } from '../../../../shared/utils/thresholds';
import { formatNumber, formatTime } from '../../../../shared/utils/formatters';
import { mapEnvTempLevel, mapEnvPreLevel, getEnvTempState, getEnvHumidityState } from '../../../../shared/utils/stateMappers';
import { LABELS, SPOT_UNIT } from '../../../../shared/constants/uiText';

export function EnvComponent() {
  const { data, lastDataAt, thresholds } = React.useContext(FactoryDataContext);
  const envTempValue = useLastValidNumber(data?.At_Temp);
  const envHumidityValue = useLastValidNumber(data?.At_Pre);
  const tempRaw = data?.At_Temp;
  const humidityRaw = data?.At_Pre;
  const tempDisplay = envTempValue ?? tempRaw ?? NaN;
  const humidityDisplay = envHumidityValue ?? humidityRaw ?? NaN;
  const missing = !Number.isFinite(tempRaw) || !Number.isFinite(humidityRaw);
  const computed = data?.Computed;
  const tempState = mapEnvTempLevel(computed?.env_temp_level) ?? getEnvTempState(tempDisplay);
  const humidityState = mapEnvPreLevel(computed?.env_pre_level) ?? getEnvHumidityState(humidityDisplay);
  const computedThresholds = computed?.thresholds;
  const tempThresholdHit = computedThresholds?.at_temp ?? isThresholdHit(thresholds, 'at_temp', envTempValue);
  const humidityThresholdHit =
    computedThresholds?.at_pre ?? isThresholdHit(thresholds, 'at_pre', envHumidityValue);
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
      {missing && (
        <div className="missing-note">
          마지막 갱신 {formatTime(lastDataAt)}
        </div>
      )}
    </div>
  );
}
