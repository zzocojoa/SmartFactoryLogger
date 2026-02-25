export interface DateRange {
  from: string;
  to: string;
}

export interface FilterState {
  searchQuery: string;
  dateRange: DateRange | null;
  sortColumn: string | null;
  sortDirection: 'asc' | 'desc';
}
