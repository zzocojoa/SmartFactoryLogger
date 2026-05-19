/**
 * Temps Widget - 컨테이너/빌렛 온도 표시
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React from 'react';
import { useShallow } from 'zustand/react/shallow';
import { selectDashboardTempsSlice, useDashboardStore } from '../../../../store/useDashboardStore';
import { useLastValidNumber } from '../../../../shared/hooks/useLastValidNumber';
import { useThresholdLevel } from '../../../../shared/hooks/useThresholdLevel';
import { formatNumber } from '../../../../shared/utils/formatters';
import { ALERT_HOLD_MS } from '../../../../shared/constants/logic';
import { LABELS, SPOT_UNIT } from '../../../../shared/constants/uiText';
import { MissingDataNote } from './MissingDataNote';

export const TempsComponent = React.memo(function TempsComponent() {
  const {
    hasData,
    tempF,
    tempB,
    billetTemp,
    billetLength,
    computedTempFThresholdHit,
    computedTempBThresholdHit,
    computedBilletTempThresholdHit,
    computedBilletLengthThresholdHit,
    missing,
    thresholdMasterOn,
    thresholdTempFEnabled,
    thresholdTempFValue,
    thresholdTempBEnabled,
    thresholdTempBValue,
    thresholdBilletTempEnabled,
    thresholdBilletTempValue,
    thresholdBilletLengthEnabled,
    thresholdBilletLengthValue,
  } = useDashboardStore(useShallow(selectDashboardTempsSlice));

  const tempFValue = useLastValidNumber(tempF);
  const tempBValue = useLastValidNumber(tempB);
  const billetTempValue = useLastValidNumber(billetTemp);
  const billetLengthValue = useLastValidNumber(billetLength);
  const tempFLevel = useThresholdLevel(tempFValue ?? NaN, 350, 450, ALERT_HOLD_MS);
  const tempBLevel = useThresholdLevel(tempBValue ?? NaN, 350, 450, ALERT_HOLD_MS);
  const billetTempLevel = useThresholdLevel(billetTempValue ?? NaN, 440, 480, ALERT_HOLD_MS);
  const tempFThresholdHit =
    computedTempFThresholdHit ??
    (thresholdMasterOn && thresholdTempFEnabled && thresholdTempFValue !== null && typeof tempFValue === 'number' && Number.isFinite(tempFValue) && tempFValue >= thresholdTempFValue);
  const tempBThresholdHit =
    computedTempBThresholdHit ??
    (thresholdMasterOn && thresholdTempBEnabled && thresholdTempBValue !== null && typeof tempBValue === 'number' && Number.isFinite(tempBValue) && tempBValue >= thresholdTempBValue);
  const billetTempThresholdHit =
    computedBilletTempThresholdHit ??
    (thresholdMasterOn && thresholdBilletTempEnabled && thresholdBilletTempValue !== null && typeof billetTempValue === 'number' && Number.isFinite(billetTempValue) && billetTempValue >= thresholdBilletTempValue);
  const billetLengthThresholdHit =
    computedBilletLengthThresholdHit ??
    (thresholdMasterOn && thresholdBilletLengthEnabled && thresholdBilletLengthValue !== null && typeof billetLengthValue === 'number' && Number.isFinite(billetLengthValue) && billetLengthValue >= thresholdBilletLengthValue);

  if (!hasData) return <div>Loading...</div>;
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
            <span className="temp-value">{formatNumber(tempF ?? NaN, 1)}</span>
            <span className="temp-unit">{SPOT_UNIT}</span>
          </div>
        </div>
        <div className={`temp-tile ${tempBClass}`}>
          <div className="temp-header">
            <span className="temp-label">{LABELS.CONTAINER_BACK}</span>
            {tempBThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
          </div>
          <div className="temp-value-row">
            <span className="temp-value">{formatNumber(tempB ?? NaN, 1)}</span>
            <span className="temp-unit">{SPOT_UNIT}</span>
          </div>
        </div>
        <div className={`temp-tile ${billetTempClass}`}>
          <div className="temp-header">
            <span className="temp-label">{LABELS.BILLET_TEMP}</span>
            {billetTempThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
          </div>
          <div className="temp-value-row">
            <span className="temp-value">{formatNumber(billetTemp ?? NaN, 1)}</span>
            <span className="temp-unit">{SPOT_UNIT}</span>
          </div>
        </div>
        <div className={`temp-tile ${billetLengthClass}`}>
          <div className="temp-header">
            <span className="temp-label">{LABELS.BILLET_LEN}</span>
            {billetLengthThresholdHit && <span className="threshold-badge">{LABELS.THRESHOLD}</span>}
          </div>
          <div className="temp-value-row">
            <span className="temp-value">{formatNumber(billetLength ?? NaN, 1)}</span>
            <span className="temp-unit">mm</span>
          </div>
        </div>
      </div>
      {missing && <MissingDataNote />}
    </div>
  );
}
);
