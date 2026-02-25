import type React from 'react';

export interface DataGridDateRange {
  from: string;
  to: string;
}

export interface DataGridToolbarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  dateRange: DataGridDateRange | null;
  onDateRangeChange: (range: DataGridDateRange | null) => void;
  pageSize: number;
  onPageSizeChange: (size: number) => void;
  totalCount: number;
  data?: any[];
  pageName?: string;
}

export interface DataGridToolbarModel {
  localSearch: string;
  inputStyle: React.CSSProperties;
  buttonStyle: React.CSSProperties;
  handleSearchInput: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleFromDateChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleToDateChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleDateRangeReset: () => void;
  handleCsvExport: () => void;
  canResetDateRange: boolean;
  isCsvExportDisabled: boolean;
}

export interface DataGridToolbarViewProps extends DataGridToolbarProps {
  model: DataGridToolbarModel;
}
