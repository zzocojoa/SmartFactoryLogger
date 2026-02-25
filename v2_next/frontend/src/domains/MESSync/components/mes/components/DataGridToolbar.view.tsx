import React from 'react';
import { PageSizeSelector } from '../PageSizeSelector';
import type { DataGridToolbarViewProps } from '../types/DataGridToolbar.types';
import {
  clearDateButtonStyle,
  csvExportButtonStyle,
  toolbarContainerStyle,
  toolbarGroupStyle,
  toolbarIconStyle,
  toolbarSpacerStyle,
  totalCountStyle,
} from '../utils/DataGridToolbar.utils';

export const DataGridToolbarView: React.FC<DataGridToolbarViewProps> = ({
  dateRange,
  pageSize,
  onPageSizeChange,
  totalCount,
  model,
}) => {
  const {
    localSearch,
    inputStyle,
    buttonStyle,
    handleSearchInput,
    handleFromDateChange,
    handleToDateChange,
    handleDateRangeReset,
    handleCsvExport,
    canResetDateRange,
    isCsvExportDisabled,
  } = model;

  return (
    <div style={toolbarContainerStyle}>
      <div style={toolbarGroupStyle}>
        <span style={toolbarIconStyle}>🔎</span>
        <input
          type="text"
          placeholder="검색.."
          value={localSearch}
          onChange={handleSearchInput}
          style={{ ...inputStyle, width: '200px' }}
        />
      </div>

      <div style={toolbarGroupStyle}>
        <span style={toolbarIconStyle}>📅</span>
        <input type="date" value={dateRange?.from || ''} onChange={handleFromDateChange} style={inputStyle} />
        <span style={{ color: 'var(--text-secondary)' }}>~</span>
        <input type="date" value={dateRange?.to || ''} onChange={handleToDateChange} style={inputStyle} />
        {canResetDateRange && (
          <button onClick={handleDateRangeReset} style={clearDateButtonStyle(buttonStyle)}>
            초기화
          </button>
        )}
      </div>

      <div style={toolbarSpacerStyle} />

      <button
        onClick={handleCsvExport}
        disabled={isCsvExportDisabled}
        style={csvExportButtonStyle(buttonStyle, isCsvExportDisabled)}
      >
        📤 CSV 내보내기
      </button>

      <PageSizeSelector pageSize={pageSize} onPageSizeChange={onPageSizeChange} />

      <div style={totalCountStyle}>{totalCount.toLocaleString()} Records</div>
    </div>
  );
};
