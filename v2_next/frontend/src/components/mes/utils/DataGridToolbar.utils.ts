import type React from 'react';
import type { DataGridDateRange } from '../types/DataGridToolbar.types';

export const toolbarContainerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '16px',
  padding: '0.75rem 1.5rem',
  background: 'var(--bg-tertiary, rgba(255,255,255,0.03))',
  borderBottom: '1px solid var(--border-color)',
  flexWrap: 'wrap',
};

export const toolbarGroupStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
};

export const toolbarIconStyle: React.CSSProperties = {
  fontSize: '1rem',
};

export const toolbarInputStyle: React.CSSProperties = {
  padding: '6px 10px',
  borderRadius: '4px',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-secondary)',
  color: 'var(--text-primary)',
  fontSize: '0.85rem',
};

export const toolbarButtonStyle: React.CSSProperties = {
  padding: '6px 12px',
  borderRadius: '4px',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-secondary)',
  color: 'var(--text-primary)',
  fontSize: '0.85rem',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
  transition: 'all 0.2s',
};

export const toolbarSpacerStyle: React.CSSProperties = {
  flex: 1,
};

export const totalCountStyle: React.CSSProperties = {
  background: 'var(--accent-main)',
  color: '#fff',
  padding: '4px 8px',
  borderRadius: '4px',
  fontSize: '0.8rem',
  fontWeight: 600,
};

export const clearDateButtonStyle = (
  baseButtonStyle: React.CSSProperties
): React.CSSProperties => ({
  ...baseButtonStyle,
  padding: '4px 8px',
  fontSize: '0.75rem',
});

export const csvExportButtonStyle = (
  baseButtonStyle: React.CSSProperties,
  disabled: boolean
): React.CSSProperties => ({
  ...baseButtonStyle,
  opacity: disabled ? 0.5 : 1,
  cursor: disabled ? 'not-allowed' : 'pointer',
});

export const buildRangeFromChange = (
  range: DataGridDateRange | null,
  from: string
): DataGridDateRange => ({
  from,
  to: range?.to || from,
});

export const buildRangeToChange = (
  range: DataGridDateRange | null,
  to: string
): DataGridDateRange => ({
  from: range?.from || to,
  to,
});

export const exportToCSV = (data: any[], filename: string) => {
  if (!data || data.length === 0) {
    return;
  }

  const headers = Object.keys(data[0]);
  const csvRows = [
    headers.join(','),
    ...data.map((row) =>
      headers
        .map((header) => {
          const value = String(row[header] ?? '').replace(/"/g, '""');
          return `"${value}"`;
        })
        .join(',')
    ),
  ];

  const blob = new Blob(['\uFEFF' + csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = url;
  link.download = `${filename}_${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();

  URL.revokeObjectURL(url);
};
