import type { FixedSizeList as List } from 'react-window';

export interface DynamicDataGridProps {
  data: any[];
  sortColumn?: string | null;
  sortDirection?: 'asc' | 'desc';
  onSort?: (column: string) => void;
  startIndex?: number;
}

export interface DynamicDataGridItemData {
  items: any[];
  headers: string[];
  columnWidths: number[];
  startIndex: number;
}

export interface DynamicDataGridLayout {
  bodyHeight: number;
  finalColumnWidths: number[];
  finalTotalDataWidth: number;
  totalScrollWidth: number;
}

export interface DynamicDataGridModel {
  hasData: boolean;
  headers: string[];
  baseColumnWidths: number[];
  totalBaseWidth: number;
  listRef: React.RefObject<List<any>>;
  headerRef: React.RefObject<HTMLDivElement>;
  outerRefCallback: (node: HTMLDivElement | null) => void;
  getSortIcon: (header: string, sortColumn?: string | null, sortDirection?: 'asc' | 'desc') => string;
  createItemData: (columnWidths: number[]) => DynamicDataGridItemData;
}

export interface DynamicDataGridViewProps extends DynamicDataGridProps {
  model: DynamicDataGridModel;
}
