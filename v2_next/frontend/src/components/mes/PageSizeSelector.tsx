import React from 'react';

interface PageSizeSelectorProps {
    pageSize: number;
    onPageSizeChange: (size: number) => void;
    options?: number[];
}

export const PageSizeSelector: React.FC<PageSizeSelectorProps> = ({ 
    pageSize, 
    onPageSizeChange, 
    options = [50, 100, 200] 
}) => {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>표시:</span>
            <select
                value={pageSize}
                onChange={(e) => onPageSizeChange(Number(e.target.value))}
                style={{
                    padding: '6px 10px',
                    borderRadius: '4px',
                    border: '1px solid var(--border-color)',
                    background: 'var(--bg-secondary)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                }}
            >
                {options.map(opt => (
                    <option key={opt} value={opt}>{opt}건</option>
                ))}
            </select>
        </div>
    );
};
