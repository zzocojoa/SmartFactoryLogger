/**
 * Data Grid Utility Functions
 * - Text search
 * - Date range filter
 * - Sorting
 */

export interface FilterState {
    searchQuery: string;
    dateRange: { from: string; to: string } | null;
    sortColumn: string | null;
    sortDirection: 'asc' | 'desc';
}

/**
 * Detect date column from data headers
 * Looks for common Korean date column names
 */
export function detectDateColumn(row: Record<string, any> | undefined): string | null {
    if (!row) return null;
    
    const keys = Object.keys(row);
    
    // Priority 1: Exact match for common date column names
    const exactPatterns = ['의뢰일자', '발주일자', '작성일', '등록일', '날짜', '일자', '일시'];
    for (const pattern of exactPatterns) {
        const found = keys.find(k => k === pattern);
        if (found) return found;
    }
    
    // Priority 2: Contains date-related Korean text
    const containsPatterns = ['일자', '일시', '날짜', 'date', 'Date'];
    for (const pattern of containsPatterns) {
        const found = keys.find(k => k.includes(pattern));
        if (found) return found;
    }
    
    // Priority 3: Look for YYYY-MM-DD pattern in values
    for (const key of keys) {
        const value = String(row[key] || '');
        if (/^\d{4}-\d{2}-\d{2}/.test(value)) {
            return key;
        }
    }
    
    return null;
}


/**
 * Apply all filters to data
 */
export function applyFilters(data: any[], state: FilterState): any[] {
    let result = [...data];
    
    // 1. Text Search (case-insensitive, all columns)
    if (state.searchQuery.trim()) {
        const query = state.searchQuery.toLowerCase().trim();
        result = result.filter(row =>
            Object.values(row).some(value =>
                String(value ?? '').toLowerCase().includes(query)
            )
        );
    }
    
    // 2. Date Range Filter
    if (state.dateRange && data.length > 0) {
        const dateCol = detectDateColumn(data[0]);
        if (dateCol) {
            result = result.filter(row => {
                const dateValue = String(row[dateCol] || '').substring(0, 10); // YYYY-MM-DD
                return dateValue >= state.dateRange!.from && dateValue <= state.dateRange!.to;
            });
        }
    }
    
    // 3. Sorting
    if (state.sortColumn) {
        result.sort((a, b) => {
            const aVal = String(a[state.sortColumn!] ?? '');
            const bVal = String(b[state.sortColumn!] ?? '');
            const cmp = aVal.localeCompare(bVal, 'ko', { numeric: true });
            return state.sortDirection === 'asc' ? cmp : -cmp;
        });
    }
    
    return result;
}

/**
 * Debounce helper
 */
export function debounce<T extends (...args: any[]) => void>(
    func: T,
    wait: number
): (...args: Parameters<T>) => void {
    let timeout: NodeJS.Timeout | null = null;
    return (...args: Parameters<T>) => {
        if (timeout) clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}
