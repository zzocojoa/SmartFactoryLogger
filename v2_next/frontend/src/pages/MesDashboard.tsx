import React, { useState, useEffect, useMemo } from 'react';
import { AuthGuard } from '../components/mes/AuthGuard';
import { PageSidebar, PageItem } from '../components/mes/PageSidebar';
import { DynamicDataGrid } from '../components/mes/DynamicDataGrid';
import { Pagination } from '../components/mes/Pagination';
import { DataGridToolbar } from '../components/mes/DataGridToolbar';
import { StatsContainer } from '../components/mes/StatsContainer';
import { applyFilters, FilterState } from '../utils/dataGridUtils';

const MesDashboardContent: React.FC = () => {
    const [selectedPage, setSelectedPage] = useState<string | null>(null);
    const [pages, setPages] = useState<PageItem[]>([]);
    const [isMenuLoading, setIsMenuLoading] = useState(true);
    
    // UI State
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);

    // Data states
    const [data, setData] = useState<any[]>([]);
    const [meta, setMeta] = useState<{ collected_at?: string, record_count?: number } | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Pagination states
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(50);

    // Filter states
    const [searchQuery, setSearchQuery] = useState('');
    const [dateRange, setDateRange] = useState<{ from: string; to: string } | null>(null);

    // Sort states
    const [sortColumn, setSortColumn] = useState<string | null>(null);
    const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

    // Fetch Menu
    useEffect(() => {
        const fetchPages = async () => {
            try {
                const response = await fetch('http://localhost:8000/api/mes/pages');
                if (!response.ok) throw new Error('Failed to load menu');
                const menuData: PageItem[] = await response.json();
                setPages(menuData);
                
                // Auto-select first page if none selected and pages exist
                if (menuData.length > 0 && !selectedPage) {
                    setSelectedPage(menuData[0].key);
                }
            } catch (err) {
                console.error(err);
            } finally {
                setIsMenuLoading(false);
            }
        };
        fetchPages();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Get Current Page Name (Korean)
    const currentPageName = useMemo(() => {
        if (!selectedPage) return 'Select a Report';
        const page = pages.find(p => p.key === selectedPage);
        return page ? page.name : selectedPage;
    }, [selectedPage, pages]);

    useEffect(() => {
        if (!selectedPage) return;

        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const response = await fetch(`http://localhost:8000/api/mes/data/${selectedPage}`);
                if (!response.ok) {
                    if (response.status === 404) throw new Error('No data found');
                    throw new Error('Failed to load data');
                }
                const result = await response.json();
                
                // Result has { data: [...], record_count, collected_at, hash_val }
                setData(result.data || []);
                setMeta({
                    collected_at: result.collected_at,
                    record_count: result.record_count
                });
                // Reset to first page when data changes
                setCurrentPage(1);
            } catch (err: any) {
                setError(err.message || 'Error loading data');
                setData([]);
                setMeta(null);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [selectedPage]);

    // Apply filters and sorting
    const filteredData = useMemo(() => {
        const filterState: FilterState = {
            searchQuery,
            dateRange,
            sortColumn,
            sortDirection
        };
        return applyFilters(data, filterState);
    }, [data, searchQuery, dateRange, sortColumn, sortDirection]);

    // Pagination calculations (based on filtered data)
    const totalPages = Math.ceil(filteredData.length / pageSize);
    const paginatedData = useMemo(() => {
        const startIdx = (currentPage - 1) * pageSize;
        return filteredData.slice(startIdx, startIdx + pageSize);
    }, [filteredData, currentPage, pageSize]);

    // Handle page size change - reset to first page
    const handlePageSizeChange = (newSize: number) => {
        setPageSize(newSize);
        setCurrentPage(1);
    };

    // Handle filter changes - reset to first page
    const handleSearchChange = (query: string) => {
        setSearchQuery(query);
        setCurrentPage(1);
    };

    const handleDateRangeChange = (range: { from: string; to: string } | null) => {
        setDateRange(range);
        setCurrentPage(1);
    };

    // Handle sort column click
    const handleSort = (column: string) => {
        if (sortColumn === column) {
            // Toggle direction or clear
            if (sortDirection === 'asc') {
                setSortDirection('desc');
            } else {
                // Clear sort
                setSortColumn(null);
                setSortDirection('asc');
            }
        } else {
            // New column, start with asc
            setSortColumn(column);
            setSortDirection('asc');
        }
    };

    return (
        <div style={{ display: 'flex', height: '100vh', width: '100vw', paddingTop: 'env(safe-area-inset-top)' }}>
            <PageSidebar 
                selectedPage={selectedPage} 
                onSelectPage={setSelectedPage} 
                pageItems={pages}
                loading={isMenuLoading}
                isOpen={isSidebarOpen}
            />
            
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg-primary)' }}>
                {/* Header */}
                <header style={{ 
                    padding: '1rem 1.5rem', 
                    borderBottom: '1px solid var(--border-color)', 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    background: 'var(--bg-secondary)' 
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <button 
                            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                            style={{
                                background: 'transparent',
                                border: 'none',
                                color: 'var(--text-secondary)',
                                cursor: 'pointer',
                                padding: '4px',
                                display: 'flex',
                                alignItems: 'center',
                                borderRadius: '4px',
                                transition: 'all 0.2s',
                            }}
                            onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
                            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                        >
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                {/* Simple Hamburger / Menu Icon */}
                                <line x1="3" y1="12" x2="21" y2="12"></line>
                                <line x1="3" y1="6" x2="21" y2="6"></line>
                                <line x1="3" y1="18" x2="21" y2="18"></line>
                            </svg>
                        </button>
                    
                        <div>
                            <h1 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text-primary)' }}>
                                {currentPageName}
                            </h1>
                            {meta?.collected_at && (
                                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px', display: 'block' }}>
                                    Collected: {new Date(meta.collected_at).toLocaleString()}
                                </span>
                            )}
                        </div>
                    </div>
                </header>

                {/* Stats Widgets */}
                <StatsContainer data={filteredData} />

                {/* Toolbar - Search, Filter, Page Size */}
                <DataGridToolbar
                    searchQuery={searchQuery}
                    onSearchChange={handleSearchChange}
                    dateRange={dateRange}
                    onDateRangeChange={handleDateRangeChange}
                    pageSize={pageSize}
                    onPageSizeChange={handlePageSizeChange}
                    totalCount={filteredData.length}
                    data={filteredData}
                    pageName={selectedPage || 'export'}
                />



                {/* Content */}
                <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
                    {loading && (
                        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.5)', zIndex: 10 }}>
                            <div className="spinner"></div> 
                        </div>
                    )}
                    
                    {error ? (
                        <div style={{ padding: '2rem', color: 'var(--state-danger)', textAlign: 'center' }}>
                            {error}
                        </div>
                    ) : (
                        <DynamicDataGrid 
                            data={paginatedData} 
                            sortColumn={sortColumn}
                            sortDirection={sortDirection}
                            onSort={handleSort}
                            startIndex={(currentPage - 1) * pageSize + 1}
                        />
                    )}
                </div>

                {/* Footer - Pagination */}
                {filteredData.length > 0 && (
                    <footer style={{ 
                        padding: '0.75rem 1.5rem', 
                        borderTop: '1px solid var(--border-color)', 
                        background: 'var(--bg-secondary)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center'
                    }}>
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                            {((currentPage - 1) * pageSize) + 1} - {Math.min(currentPage * pageSize, filteredData.length)} / {filteredData.length.toLocaleString()}건
                        </span>
                        <Pagination 
                            currentPage={currentPage} 
                            totalPages={totalPages} 
                            onPageChange={setCurrentPage} 
                        />
                    </footer>
                )}

            </div>
        </div>
    );
};

export const MesDashboard: React.FC = () => {
    return (
        <AuthGuard>
            <MesDashboardContent />
        </AuthGuard>
    );
};

