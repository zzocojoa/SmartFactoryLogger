import React from 'react';

export interface PageItem {
    key: string;
    name: string;
    category: string;
}

interface PageSidebarProps {
    selectedPage: string | null;
    onSelectPage: (page: string) => void;
    pageItems: PageItem[];
    loading?: boolean;
    error?: string | null;
}

export const PageSidebar: React.FC<PageSidebarProps & { isOpen: boolean }> = ({ 
    selectedPage, 
    onSelectPage, 
    pageItems, 
    loading = false, 
    error = null,
    isOpen 
}) => {
    // Grouping Logic
    const groupedPages = React.useMemo(() => {
        const groups: Record<string, PageItem[]> = {};
        pageItems.forEach(item => {
            if (!groups[item.category]) {
                groups[item.category] = [];
            }
            groups[item.category].push(item);
        });
        return groups;
    }, [pageItems]);

    const categoryKeys = React.useMemo(() => {
        const keys = new Set(pageItems.map(p => p.category));
        return Array.from(keys);
    }, [pageItems]);

    // Accordion State with Persistence
    const [expandedCategories, setExpandedCategories] = React.useState<Set<string>>(() => {
        try {
            const saved = localStorage.getItem('mes_sidebar_expanded_categories');
            if (saved) {
                return new Set(JSON.parse(saved));
            }
        } catch (e) {
            // Ignore parse errors
        }
        return new Set(); // Default: All Closed
    });

    // Save state on change
    React.useEffect(() => {
        try {
            localStorage.setItem('mes_sidebar_expanded_categories', JSON.stringify(Array.from(expandedCategories)));
        } catch (e) {
            console.error('Failed to save sidebar state', e);
        }
    }, [expandedCategories]);

    const toggleCategory = (category: string) => {
        setExpandedCategories(prev => {
            const next = new Set(prev);
            if (next.has(category)) {
                next.delete(category);
            } else {
                next.add(category);
            }
            return next;
        });
    };

    return (
        <div style={{
            width: isOpen ? '250px' : '0px',
            background: 'var(--bg-secondary)',
            borderRight: '1px solid var(--border-color)',
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            overflow: 'hidden',
            whiteSpace: 'nowrap',
            willChange: 'width',
            position: 'relative' 
        }}>
            <div style={{ 
                padding: '1.5rem', 
                borderBottom: '1px solid var(--border-color)',
                opacity: isOpen ? 1 : 0,
                transition: 'opacity 0.2s',
                transitionDelay: isOpen ? '0.1s' : '0s' 
            }}>
                <h3 style={{ margin: 0, color: 'var(--text-primary)', fontSize: '1.1rem' }}>
                    MES Reports
                </h3>
            </div>
            
            <div style={{ 
                flex: 1, 
                overflowY: 'auto', 
                padding: '1rem',
                opacity: isOpen ? 1 : 0,
                transition: 'opacity 0.2s',
                transitionDelay: isOpen ? '0.1s' : '0s'
            }}>
                {loading && <div style={{ color: 'var(--text-secondary)' }}>Loading...</div>}
                {error && <div style={{ color: 'var(--state-danger)' }}>{error}</div>}
                
                {!loading && pageItems.length === 0 && (
                     <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                         No pages found.
                     </div>
                )}

                {categoryKeys.map(category => {
                    const isExpanded = expandedCategories.has(category);
                    return (
                        <div key={category} style={{ marginBottom: '0.5rem' }}>
                            {/* Accordion Header */}
                            <div 
                                onClick={() => toggleCategory(category)}
                                style={{
                                    color: 'var(--accent-main)',
                                    fontSize: '0.85rem',
                                    fontWeight: 'bold',
                                    textTransform: 'uppercase',
                                    marginBottom: '0.5rem',
                                    padding: '0.5rem',
                                    borderLeft: '2px solid var(--accent-main)',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between', // Align icon to right
                                    userSelect: 'none',
                                    background: 'transparent',
                                    transition: 'background 0.2s'
                                }}
                                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
                                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                            >
                                <span>{category}</span>
                                {/* Chevron Icon */}
                                <svg 
                                    width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                                    style={{
                                        transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                                        transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                        opacity: 0.7
                                    }}
                                >
                                    <path d="M6 9l6 6 6-6" />
                                </svg>
                            </div>

                            {/* Accordion Content */}
                            <div style={{
                                maxHeight: isExpanded ? '500px' : '0px', // Arbitrary max height for animation
                                overflow: 'hidden',
                                transition: 'max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s',
                                opacity: isExpanded ? 1 : 0,
                            }}>
                                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                                    {groupedPages[category].map(item => (
                                        <li key={item.key} style={{ marginBottom: '0.2rem' }}>
                                            <button
                                                onClick={() => onSelectPage(item.key)}
                                                style={{
                                                    width: '100%',
                                                    textAlign: 'left',
                                                    padding: '8px 15px',
                                                    background: selectedPage === item.key ? 'rgba(74, 222, 128, 0.1)' : 'transparent',
                                                    color: selectedPage === item.key ? 'var(--accent-main)' : 'var(--text-secondary)',
                                                    border: 'none',
                                                    borderRadius: '4px',
                                                    cursor: 'pointer',
                                                    transition: 'all 0.2s',
                                                    fontWeight: selectedPage === item.key ? 600 : 400,
                                                    fontSize: '0.9rem',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    paddingLeft: '1.5rem' // Indent sub-items
                                                }}
                                            >
                                                <span style={{ marginRight: '8px', opacity: 0.7 }}>•</span>
                                                {item.name}
                                            </button>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    );
                })}
            </div>
            
            <div style={{ 
                padding: '1rem', 
                borderTop: '1px solid var(--border-color)', 
                fontSize: '0.8rem', 
                color: 'var(--text-secondary)',
                opacity: isOpen ? 1 : 0,
                transition: 'opacity 0.2s'
            }}>
                Smart Factory MES
            </div>
        </div>
    );
};
