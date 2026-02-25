import React from 'react';

interface PaginationProps {
    currentPage: number;
    totalPages: number;
    onPageChange: (page: number) => void;
}

export const Pagination: React.FC<PaginationProps> = ({ currentPage, totalPages, onPageChange }) => {
    if (totalPages <= 1) return null;

    // Generate page numbers to show
    const getPageNumbers = (): (number | string)[] => {
        const pages: (number | string)[] = [];
        const maxVisible = 7;
        
        if (totalPages <= maxVisible) {
            for (let i = 1; i <= totalPages; i++) pages.push(i);
        } else {
            // Always show first page
            pages.push(1);
            
            if (currentPage > 3) pages.push('...');
            
            // Show pages around current
            const start = Math.max(2, currentPage - 1);
            const end = Math.min(totalPages - 1, currentPage + 1);
            for (let i = start; i <= end; i++) pages.push(i);
            
            if (currentPage < totalPages - 2) pages.push('...');
            
            // Always show last page
            pages.push(totalPages);
        }
        return pages;
    };

    const buttonStyle: React.CSSProperties = {
        padding: '6px 12px',
        border: '1px solid var(--border-color)',
        background: 'var(--bg-secondary)',
        color: 'var(--text-primary)',
        cursor: 'pointer',
        borderRadius: '4px',
        fontSize: '0.85rem',
        transition: 'all 0.2s',
    };

    const activeStyle: React.CSSProperties = {
        ...buttonStyle,
        background: 'var(--accent-main)',
        borderColor: 'var(--accent-main)',
        color: '#fff',
    };

    const disabledStyle: React.CSSProperties = {
        ...buttonStyle,
        opacity: 0.5,
        cursor: 'not-allowed',
    };

    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
            <button
                style={currentPage === 1 ? disabledStyle : buttonStyle}
                onClick={() => currentPage > 1 && onPageChange(currentPage - 1)}
                disabled={currentPage === 1}
            >
                ◀ 이전
            </button>

            {getPageNumbers().map((page, idx) => (
                typeof page === 'number' ? (
                    <button
                        key={idx}
                        style={page === currentPage ? activeStyle : buttonStyle}
                        onClick={() => onPageChange(page)}
                    >
                        {page}
                    </button>
                ) : (
                    <span key={idx} style={{ padding: '0 4px', color: 'var(--text-secondary)' }}>...</span>
                )
            ))}

            <button
                style={currentPage === totalPages ? disabledStyle : buttonStyle}
                onClick={() => currentPage < totalPages && onPageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
            >
                다음 ▶
            </button>
        </div>
    );
};
