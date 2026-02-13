import type { DynamicDataGridLayout } from '../types/DynamicDataGrid.types';

export const GRID_ROW_HEIGHT = 40;
export const GRID_HEADER_HEIGHT = 40;
export const GRID_NUMBER_COLUMN_WIDTH = 50;
export const GRID_SCROLLBAR_WIDTH = 24;

export const extractHeaders = (data: any[]): string[] => {
  if (!data || data.length === 0) {
    return [];
  }

  return Object.keys(data[0]);
};

export const calculateBaseColumnWidths = (headers: string[]) => {
  if (headers.length === 0) {
    return {
      baseColumnWidths: [] as number[],
      totalBaseWidth: 0,
    };
  }

  const baseColumnWidths = headers.map((header) => {
    const estimatedWidth = header.length * 13 + 40;
    return Math.max(100, estimatedWidth);
  });

  return {
    baseColumnWidths,
    totalBaseWidth: baseColumnWidths.reduce((sum, width) => sum + width, 0),
  };
};

export const resolveSortIcon = (
  header: string,
  sortColumn?: string | null,
  sortDirection: 'asc' | 'desc' = 'asc'
) => {
  if (sortColumn !== header) {
    return ' ';
  }

  return sortDirection === 'asc' ? '^' : 'v';
};

export const calculateResponsiveLayout = ({
  width,
  height,
  rowCount,
  baseColumnWidths,
  totalBaseWidth,
}: {
  width: number;
  height: number;
  rowCount: number;
  baseColumnWidths: number[];
  totalBaseWidth: number;
}): DynamicDataGridLayout => {
  const bodyHeight = height - GRID_HEADER_HEIGHT;
  const totalRowHeight = rowCount * GRID_ROW_HEIGHT;
  const hasVerticalScroll = totalRowHeight > bodyHeight;
  const availableSpace = hasVerticalScroll ? width - GRID_SCROLLBAR_WIDTH : width;
  const availableForColumns = availableSpace - GRID_NUMBER_COLUMN_WIDTH;

  let finalColumnWidths = baseColumnWidths;
  let finalTotalDataWidth = totalBaseWidth;

  if (baseColumnWidths.length > 0 && availableForColumns > totalBaseWidth) {
    const extraSpace = availableForColumns - totalBaseWidth;
    const bonusPerColumn = Math.floor(extraSpace / baseColumnWidths.length);

    finalColumnWidths = baseColumnWidths.map((columnWidth) => columnWidth + bonusPerColumn);
    finalTotalDataWidth = finalColumnWidths.reduce((sum, widthValue) => sum + widthValue, 0);
  }

  return {
    bodyHeight,
    finalColumnWidths,
    finalTotalDataWidth,
    totalScrollWidth: finalTotalDataWidth + GRID_NUMBER_COLUMN_WIDTH,
  };
};
