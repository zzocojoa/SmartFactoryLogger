import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

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
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close on click outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, []);

    const handleSelect = (size: number) => {
        onPageSizeChange(size);
        setIsOpen(false);
    };

    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>표시:</span>
            
            <div ref={dropdownRef} style={{ position: 'relative' }}>
                <button
                    onClick={() => setIsOpen(!isOpen)}
                    style={{
                        padding: '6px 12px',
                        borderRadius: '4px',
                        border: '1px solid var(--border-color)',
                        background: 'var(--bg-secondary)',
                        color: 'var(--text-primary)',
                        fontSize: '0.85rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        minWidth: '80px',
                        justifyContent: 'space-between',
                        transition: 'all 0.2s',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--accent-main)'}
                    onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border-color)'}
                >
                    {pageSize}건
                    {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>

                {isOpen && (
                    <div style={{
                        position: 'absolute',
                        top: '100%',
                        left: 0,
                        right: 0,
                        marginTop: '4px',
                        background: '#242731', // Dark background
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.5)',
                        zIndex: 50,
                        overflow: 'hidden'
                    }}>
                        {options.map(opt => (
                            <div
                                key={opt}
                                onClick={() => handleSelect(opt)}
                                style={{
                                    padding: '8px 12px',
                                    cursor: 'pointer',
                                    fontSize: '0.85rem',
                                    color: 'var(--text-primary)',
                                    background: pageSize === opt ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                                    transition: 'background 0.2s'
                                }}
                                onMouseEnter={(e) => {
                                    if (pageSize !== opt) e.currentTarget.style.background = 'var(--bg-hover)';
                                }}
                                onMouseLeave={(e) => {
                                    if (pageSize !== opt) e.currentTarget.style.background = 'transparent';
                                }}
                            >
                                {opt}건
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};
