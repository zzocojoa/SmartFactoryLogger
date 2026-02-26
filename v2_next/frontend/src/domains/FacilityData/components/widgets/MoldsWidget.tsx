/**
 * Molds Widget - 금형 온도 6채널 표시
 * Phase 9 Step 2에서 App.tsx로부터 추출
 */
import React from 'react';
import { FactoryDataContext } from '../../context/FactoryDataContext';
import { formatNumber, formatTime } from '../../../../shared/utils/formatters';
import { mapMoldLevel, getMoldState } from '../../../../shared/utils/stateMappers';

export function MoldsComponent() {
  const { data, lastDataAt } = React.useContext(FactoryDataContext);
  if (!data) return <div>Loading...</div>;
  const missing =
    !Number.isFinite(data.Mold1) ||
    !Number.isFinite(data.Mold2) ||
    !Number.isFinite(data.Mold3) ||
    !Number.isFinite(data.Mold4) ||
    !Number.isFinite(data.Mold5) ||
    !Number.isFinite(data.Mold6);
  const moldLevels = data?.Computed?.mold_levels;
  const mold1 = mapMoldLevel(moldLevels?.Mold1) ?? getMoldState(data.Mold1 ?? 0).className;
  const mold2 = mapMoldLevel(moldLevels?.Mold2) ?? getMoldState(data.Mold2 ?? 0).className;
  const mold3 = mapMoldLevel(moldLevels?.Mold3) ?? getMoldState(data.Mold3 ?? 0).className;
  const mold4 = mapMoldLevel(moldLevels?.Mold4) ?? getMoldState(data.Mold4 ?? 0).className;
  const mold5 = mapMoldLevel(moldLevels?.Mold5) ?? getMoldState(data.Mold5 ?? 0).className;
  const mold6 = mapMoldLevel(moldLevels?.Mold6) ?? getMoldState(data.Mold6 ?? 0).className;
  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="mold-grid">
        <div className={`mold-tile ${mold1}`}>
          <span className="mold-label">Mold 1</span>
          <span className="mold-value">{formatNumber(data.Mold1 ?? NaN, 1)}</span>
        </div>
        <div className={`mold-tile ${mold2}`}>
          <span className="mold-label">Mold 2</span>
          <span className="mold-value">{formatNumber(data.Mold2 ?? NaN, 1)}</span>
        </div>
        <div className={`mold-tile ${mold3}`}>
          <span className="mold-label">Mold 3</span>
          <span className="mold-value">{formatNumber(data.Mold3 ?? NaN, 1)}</span>
        </div>
        <div className={`mold-tile ${mold4}`}>
          <span className="mold-label">Mold 4</span>
          <span className="mold-value">{formatNumber(data.Mold4 ?? NaN, 1)}</span>
        </div>
        <div className={`mold-tile ${mold5}`}>
          <span className="mold-label">Mold 5</span>
          <span className="mold-value">{formatNumber(data.Mold5 ?? NaN, 1)}</span>
        </div>
        <div className={`mold-tile ${mold6}`}>
          <span className="mold-label">Mold 6</span>
          <span className="mold-value">{formatNumber(data.Mold6 ?? NaN, 1)}</span>
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
