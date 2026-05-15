/**
 * Molds Widget - 금형 온도 6채널 표시
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React from 'react';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import { formatNumber, formatTime } from '../../../../shared/utils/formatters';
import { mapMoldLevel, getMoldState } from '../../../../shared/utils/stateMappers';

export const MoldsComponent = React.memo(function MoldsComponent() {
  const hasData = useDashboardStore(state => state.data !== null);
  const moldValue1 = useDashboardStore(state => state.data?.Mold1);
  const moldValue2 = useDashboardStore(state => state.data?.Mold2);
  const moldValue3 = useDashboardStore(state => state.data?.Mold3);
  const moldValue4 = useDashboardStore(state => state.data?.Mold4);
  const moldValue5 = useDashboardStore(state => state.data?.Mold5);
  const moldValue6 = useDashboardStore(state => state.data?.Mold6);
  const computedMoldLevel1 = useDashboardStore(state => state.data?.Computed?.mold_levels?.Mold1);
  const computedMoldLevel2 = useDashboardStore(state => state.data?.Computed?.mold_levels?.Mold2);
  const computedMoldLevel3 = useDashboardStore(state => state.data?.Computed?.mold_levels?.Mold3);
  const computedMoldLevel4 = useDashboardStore(state => state.data?.Computed?.mold_levels?.Mold4);
  const computedMoldLevel5 = useDashboardStore(state => state.data?.Computed?.mold_levels?.Mold5);
  const computedMoldLevel6 = useDashboardStore(state => state.data?.Computed?.mold_levels?.Mold6);
  const lastDataAt = useDashboardStore(state => {
    const mold1 = state.data?.Mold1;
    const mold2 = state.data?.Mold2;
    const mold3 = state.data?.Mold3;
    const mold4 = state.data?.Mold4;
    const mold5 = state.data?.Mold5;
    const mold6 = state.data?.Mold6;
    return !Number.isFinite(mold1) ||
      !Number.isFinite(mold2) ||
      !Number.isFinite(mold3) ||
      !Number.isFinite(mold4) ||
      !Number.isFinite(mold5) ||
      !Number.isFinite(mold6)
      ? state.lastDataAt
      : null;
  });
  if (!hasData) return <div>Loading...</div>;
  const missing =
    !Number.isFinite(moldValue1) ||
    !Number.isFinite(moldValue2) ||
    !Number.isFinite(moldValue3) ||
    !Number.isFinite(moldValue4) ||
    !Number.isFinite(moldValue5) ||
    !Number.isFinite(moldValue6);
  const mold1 = mapMoldLevel(computedMoldLevel1) ?? getMoldState(moldValue1 ?? 0).className;
  const mold2 = mapMoldLevel(computedMoldLevel2) ?? getMoldState(moldValue2 ?? 0).className;
  const mold3 = mapMoldLevel(computedMoldLevel3) ?? getMoldState(moldValue3 ?? 0).className;
  const mold4 = mapMoldLevel(computedMoldLevel4) ?? getMoldState(moldValue4 ?? 0).className;
  const mold5 = mapMoldLevel(computedMoldLevel5) ?? getMoldState(moldValue5 ?? 0).className;
  const mold6 = mapMoldLevel(computedMoldLevel6) ?? getMoldState(moldValue6 ?? 0).className;
  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="mold-grid">
        <div className={`mold-tile ${mold1}`}>
          <span className="mold-label">Mold 1</span>
          <span className="mold-value">{formatNumber(moldValue1 ?? NaN, 1)}</span>
        </div>
        <div className={`mold-tile ${mold2}`}>
          <span className="mold-label">Mold 2</span>
          <span className="mold-value">{formatNumber(moldValue2 ?? NaN, 1)}</span>
        </div>
        <div className={`mold-tile ${mold3}`}>
          <span className="mold-label">Mold 3</span>
          <span className="mold-value">{formatNumber(moldValue3 ?? NaN, 1)}</span>
        </div>
        <div className={`mold-tile ${mold4}`}>
          <span className="mold-label">Mold 4</span>
          <span className="mold-value">{formatNumber(moldValue4 ?? NaN, 1)}</span>
        </div>
        <div className={`mold-tile ${mold5}`}>
          <span className="mold-label">Mold 5</span>
          <span className="mold-value">{formatNumber(moldValue5 ?? NaN, 1)}</span>
        </div>
        <div className={`mold-tile ${mold6}`}>
          <span className="mold-label">Mold 6</span>
          <span className="mold-value">{formatNumber(moldValue6 ?? NaN, 1)}</span>
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
