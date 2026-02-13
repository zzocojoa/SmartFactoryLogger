import { useCallback, useEffect, useMemo, useState } from 'react';
import { debounce } from '../../../utils/dataGridUtils';
import type { DataGridToolbarModel, DataGridToolbarProps } from '../types/DataGridToolbar.types';
import {
  buildRangeFromChange,
  buildRangeToChange,
  exportToCSV,
  toolbarButtonStyle,
  toolbarInputStyle,
} from '../utils/DataGridToolbar.utils';

export const useDataGridToolbarModel = (props: DataGridToolbarProps): DataGridToolbarModel => {
  const {
    searchQuery,
    onSearchChange,
    dateRange,
    onDateRangeChange,
    data = [],
    pageName = 'export',
  } = props;

  const [localSearch, setLocalSearch] = useState(searchQuery);

  const debouncedSearch = useMemo(
    () => debounce((value: string) => onSearchChange(value), 300),
    [onSearchChange]
  );

  useEffect(() => {
    setLocalSearch(searchQuery);
  }, [searchQuery]);

  const handleSearchInput = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const value = event.target.value;
      setLocalSearch(value);
      debouncedSearch(value);
    },
    [debouncedSearch]
  );

  const handleFromDateChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      onDateRangeChange(buildRangeFromChange(dateRange, event.target.value));
    },
    [dateRange, onDateRangeChange]
  );

  const handleToDateChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      onDateRangeChange(buildRangeToChange(dateRange, event.target.value));
    },
    [dateRange, onDateRangeChange]
  );

  const handleDateRangeReset = useCallback(() => {
    onDateRangeChange(null);
  }, [onDateRangeChange]);

  const handleCsvExport = useCallback(() => {
    exportToCSV(data, pageName);
  }, [data, pageName]);

  return {
    localSearch,
    inputStyle: toolbarInputStyle,
    buttonStyle: toolbarButtonStyle,
    handleSearchInput,
    handleFromDateChange,
    handleToDateChange,
    handleDateRangeReset,
    handleCsvExport,
    canResetDateRange: Boolean(dateRange),
    isCsvExportDisabled: data.length === 0,
  };
};
