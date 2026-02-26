/**
 * Temps Widget - 컨테이너/빌렛 온도 표시
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React from 'react';
import { FactoryDataContext } from '../../context/FactoryDataContext';
import { useLastValidNumber } from '../../../../shared/hooks/useLastValidNumber';
import { useThresholdLevel } from '../../../../shared/hooks/useThresholdLevel';
import { isThresholdHit } from '../../../../shared/utils/thresholds';
import { formatNumber, formatTime } from '../../../../shared/utils/formatters';
import { ALERT_HOLD_MS } from '../../../../shared/constants/logic';
import { LABELS, SPOT_UNIT } from '../../../../shared/constants/uiText';

export function TempsComponent() {
  const { data, lastDataAt, thresholds } = React.useContext(FactoryDataContext);
  const missing =
    !Number.isFinite(data?.Temp_F) ||
    !Number.isFinite(data?.Temp_B) ||
    !Number.isFinite(data?.Billet_Temp) ||
    !Number.isFinite(data?.Billet_Length);
  const tempFValue = useLastValidNumber(data?.Temp_F);
  const tempBValue = useLastValidNumber(data?.Temp_B);
  const billetTempValue = useLastValidNumber(data?.Billet_Temp);
  const billetLengthValue = useLastValidNumber(data?.Billet_Length);
  const tempFLevel = useThresholdLevel(tempFValue ?? NaN, 350, 450, ALERT_HOLD_MS);
  const tempBLevel = useThresholdLevel(tempBValue ?? NaN, 350, 450, ALERT_HOLD_MS);
  const billetTempLevel = useThresholdLevel(billetTempValue ?? NaN, 440, 480, ALERT_HOLD_MS);
  const computedThresholds = data?.Computed?.thresholds;
  const tempFThresholdHit = computedThresholds?.temp_f ?? isThresholdHit(thresholds, 'temp_f', tempFValue);
  const tempBThresholdHit = computedThresholds?.temp_b ?? isThresholdHit(thresholds, 'temp_b', tempBValue);
  const billetTempThresholdHit =
    computedThresholds?.billet_temp ?? isThresholdHit(thresholds, 'billet_temp', billetTempValue);
  const billetLengthThresholdHit =
    computedThresholds?.billet ?? isThresholdHit(thresholds, 'billet', billetLengthValue);

  if (!data) return <div>Loading...</div>;
  const tempFClass = [
    tempFLevel === 'danger' ? 'temp-danger' : tempFLevel === 'warn' ? 'temp-warn' : '',
    tempFThresholdHit ? 'temp-threshold' : '',
  ]
    .filter(Boolean)
    .join(' ');
  const tempBClass = [
    tempBLevel === 'danger' ? 'temp-danger' : tempBLevel === 'warn' ? 'temp-warn' : '',
    tempBThresholdHit ? 'temp-threshold' : '',
  ]
    .filter(Boolean)
    .join(' ');
  const billetTempClass = [
    billetTempLevel === 'danger' ? 'temp-danger' : billetTempLevel === 'warn' ? 'temp-warn' : '',
    billetTempThresholdHit ? 'temp-threshold' : '',
  ]
    .filter(Boolean)
    .join(' ');
  const billetLengthClass = billetLengthThresholdHit ? 'temp-threshold' : '';
  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="temp-grid">
        <div className={`temp-tile ${tempFClass}`}>
          <div className="temp-header">
            <span className="temp-label">{LABELS.CONTAINER_FRONT}</span>
            {tempFThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
          </div>
          <div className="temp-value-row">
            <span className="temp-value">{formatNumber(data.Temp_F ?? NaN, 1)}</span>
            <span className="temp-unit">{SPOT_UNIT}</span>
          </div>
        </div>
        <div className={`temp-tile ${tempBClass}`}>
          <div className="temp-header">
            <span className="temp-label">{LABELS.CONTAINER_BACK}</span>
            {tempBThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
          </div>
          <div className="temp-value-row">
            <span className="temp-value">{formatNumber(data.Temp_B ?? NaN, 1)}</span>
            <span className="temp-unit">{SPOT_UNIT}</span>
          </div>
        </div>
        <div className={`temp-tile ${billetTempClass}`}>
          <div className="temp-header">
            <span className="temp-label">{LABELS.BILLET_TEMP}</span>
            {billetTempThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
          </div>
          <div className="temp-value-row">
            <span className="temp-value">{formatNumber(data.Billet_Temp ?? NaN, 1)}</span>
            <span className="temp-unit">{SPOT_UNIT}</span>
          </div>
        </div>
        <div className={`temp-tile ${billetLengthClass}`}>
          <div className="temp-header">
            <span className="temp-label">{LABELS.BILLET_LEN}</span>
            {billetLengthThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
          </div>
          <div className="temp-value-row">
            <span className="temp-value">{formatNumber(data.Billet_Length ?? NaN, 1)}</span>
            <span className="temp-unit">mm</span>
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
