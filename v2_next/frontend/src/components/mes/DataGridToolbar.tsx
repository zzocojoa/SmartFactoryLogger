import React, { useState, useCallback, useEffect } from 'react';
import { PageSizeSelector } from './PageSizeSelector';
import { debounce } from '../../utils/dataGridUtils';

interface DataGridToolbarProps {
    searchQuery: string;
    onSearchChange: (query: string) => void;
    dateRange: { from: string; to: string } | null;
    onDateRangeChange: (range: { from: string; to: string } | null) => void;
    pageSize: number;
    onPageSizeChange: (size: number) => void;
    totalCount: number;
    data?: any[]; // For CSV export
    pageName?: string; // For filename
}

// CSV Export Helper
function exportToCSV(data: any[], filename: string) {
    if (!data || data.length === 0) return;
    
    const headers = Object.keys(data[0]);
    const csvRows = [
        headers.join(','),
        ...data.map(row => 
            headers.map(h => {
                const val = String(row[h] ?? '').replace(/"/g, '""');
                return `"${val}"`;
            }).join(',')
        )
    ];
    
    const blob = new Blob(['\uFEFF' + csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}_${new Date().toISOString().slice(0,10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
}

export const DataGridToolbar: React.FC<DataGridToolbarProps> = ({
    searchQuery,
    onSearchChange,
    dateRange,
    onDateRangeChange,
    pageSize,
    onPageSizeChange,
    totalCount,
    data = [],
    pageName = 'export',
}) => {
    const [localSearch, setLocalSearch] = useState(searchQuery);

    // Debounced search
    const debouncedSearch = useCallback(
        debounce((value: string) => onSearchChange(value), 300),
        [onSearchChange]
    );

    const handleSearchInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = e.target.value;
        setLocalSearch(value);
        debouncedSearch(value);
    };

    // Sync local state when prop changes
    useEffect(() => {
        setLocalSearch(searchQuery);
    }, [searchQuery]);

    const inputStyle: React.CSSProperties = {
        padding: '6px 10px',
        borderRadius: '4px',
        border: '1px solid var(--border-color)',
        background: 'var(--bg-secondary)',
        color: 'var(--text-primary)',
        fontSize: '0.85rem',
    };

    const buttonStyle: React.CSSProperties = {
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

    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            padding: '0.75rem 1.5rem',
            background: 'var(--bg-tertiary, rgba(255,255,255,0.03))',
            borderBottom: '1px solid var(--border-color)',
            flexWrap: 'wrap',
        }}>
            {/* Search Input */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '1rem' }}>🔍</span>
                <input
                    type="text"
                    placeholder="검색..."
                    value={localSearch}
                    onChange={handleSearchInput}
                    style={{ ...inputStyle, width: '200px' }}
                />
            </div>

            {/* Date Range */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '1rem' }}>📅</span>
                <input
                    type="date"
                    value={dateRange?.from || ''}
                    onChange={(e) => onDateRangeChange({
                        from: e.target.value,
                        to: dateRange?.to || e.target.value
                    })}
                    style={inputStyle}
                />
                <span style={{ color: 'var(--text-secondary)' }}>~</span>
                <input
                    type="date"
                    value={dateRange?.to || ''}
                    onChange={(e) => onDateRangeChange({
                        from: dateRange?.from || e.target.value,
                        to: e.target.value
                    })}
                    style={inputStyle}
                />
                {dateRange && (
                    <button
                        onClick={() => onDateRangeChange(null)}
                        style={{
                            ...buttonStyle,
                            padding: '4px 8px',
                            fontSize: '0.75rem',
                        }}
                    >
                        초기화
                    </button>
                )}
            </div>

            {/* Spacer */}
            <div style={{ flex: 1 }} />

            {/* CSV Export Button */}
            <button
                onClick={() => exportToCSV(data, pageName)}
                disabled={data.length === 0}
                style={{
                    ...buttonStyle,
                    opacity: data.length === 0 ? 0.5 : 1,
                    cursor: data.length === 0 ? 'not-allowed' : 'pointer',
                }}
            >
                📥 CSV 내보내기
            </button>

            {/* Page Size & Count */}
            <PageSizeSelector pageSize={pageSize} onPageSizeChange={onPageSizeChange} />
            <div style={{ 
                background: 'var(--accent-main)', 
                color: '#fff', 
                padding: '4px 8px', 
                borderRadius: '4px', 
                fontSize: '0.8rem', 
                fontWeight: 600 
            }}>
                {totalCount.toLocaleString()} Records
            </div>
        </div>
    );
};
