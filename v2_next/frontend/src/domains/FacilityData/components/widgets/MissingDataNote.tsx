import React from 'react';
import { selectLastDataAtSecond, useDashboardStore } from '../../../../store/useDashboardStore';
import { formatTime } from '../../../../shared/utils/formatters';

export const MissingDataNote = React.memo(function MissingDataNote() {
  const lastDataAtSecond = useDashboardStore(selectLastDataAtSecond);
  const lastDataAt = lastDataAtSecond === null ? null : lastDataAtSecond * 1000;

  return (
    <div className="missing-note">
      마지막 갱신 {formatTime(lastDataAt)}
    </div>
  );
});
