/**
 * Molds Widget - 금형 온도 6채널 표시
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React from 'react';
import { useShallow } from 'zustand/react/shallow';
import { selectDashboardMoldsSlice, useDashboardStore } from '../../../../store/useDashboardStore';
import { formatNumber } from '../../../../shared/utils/formatters';
import { mapMoldLevel, getMoldState } from '../../../../shared/utils/stateMappers';
import { MissingDataNote } from './MissingDataNote';

export const MoldsComponent = React.memo(function MoldsComponent() {
  const {
    hasData,
    moldValue1,
    moldValue2,
    moldValue3,
    moldValue4,
    moldValue5,
    moldValue6,
    computedMoldLevel1,
    computedMoldLevel2,
    computedMoldLevel3,
    computedMoldLevel4,
    computedMoldLevel5,
    computedMoldLevel6,
    missing,
  } = useDashboardStore(useShallow(selectDashboardMoldsSlice));
  if (!hasData) return <div>Loading...</div>;
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
      {missing && <MissingDataNote />}
    </div>
  );
}
);
