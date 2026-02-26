import type { FilterState } from './dataGridUtils.types';

export function detectDateColumn(row: Record<string, any> | undefined): string | null {
  if (!row) return null;

  const keys = Object.keys(row);

  const exactPatterns = [
    '\uB0A0\uC9DC', // 날짜
    '\uBC1C\uC8FC\uC77C\uC790', // 발주일자
    '\uC791\uC131\uC77C', // 작성일
    '\uB4F1\uB85D\uC77C', // 등록일
    '\uC77C\uC790', // 일자
    '\uC77C\uC2DC', // 일시
  ];
  for (const pattern of exactPatterns) {
    const found = keys.find((key) => key === pattern);
    if (found) return found;
  }

  const containsPatterns = ['\uC77C\uC790', '\uC77C\uC2DC', '\uB0A0\uC9DC', 'date', 'Date'];
  for (const pattern of containsPatterns) {
    const found = keys.find((key) => key.includes(pattern));
    if (found) return found;
  }

  for (const key of keys) {
    const value = String(row[key] || '');
    if (/^\d{4}-\d{2}-\d{2}/.test(value)) {
      return key;
    }
  }

  return null;
}

export function applyFilters(data: any[], state: FilterState): any[] {
  let result = [...data];

  if (state.searchQuery.trim()) {
    const query = state.searchQuery.toLowerCase().trim();
    result = result.filter((row) =>
      Object.values(row).some((value) => String(value ?? '').toLowerCase().includes(query))
    );
  }

  if (state.dateRange && data.length > 0) {
    const dateCol = detectDateColumn(data[0]);
    if (dateCol) {
      result = result.filter((row) => {
        const dateValue = String(row[dateCol] || '').substring(0, 10);
        return dateValue >= state.dateRange!.from && dateValue <= state.dateRange!.to;
      });
    }
  }

  if (state.sortColumn) {
    result = [...result].sort((a, b) => {
      const aVal = String(a[state.sortColumn!] ?? '');
      const bVal = String(b[state.sortColumn!] ?? '');
      const cmp = aVal.localeCompare(bVal, 'ko', { numeric: true });
      return state.sortDirection === 'asc' ? cmp : -cmp;
    });
  }

  return result;
}

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
