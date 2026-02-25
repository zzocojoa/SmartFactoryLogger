import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FixedSizeList as List } from 'react-window';
import type {
  DynamicDataGridItemData,
  DynamicDataGridModel,
  DynamicDataGridProps,
} from '../types/DynamicDataGrid.types';
import { calculateBaseColumnWidths, extractHeaders, resolveSortIcon } from '../utils/DynamicDataGrid.utils';

export const useDynamicDataGridModel = ({
  data,
  startIndex = 1,
}: DynamicDataGridProps): DynamicDataGridModel => {
  const headers = useMemo(() => extractHeaders(data), [data]);
  const { baseColumnWidths, totalBaseWidth } = useMemo(
    () => calculateBaseColumnWidths(headers),
    [headers]
  );

  const listRef = useRef<List<any>>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const outerRef = useRef<HTMLDivElement | null>(null);
  const [outerElement, setOuterElement] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTo(0);
    }

    if (headerRef.current) {
      headerRef.current.scrollLeft = 0;
    }
  }, [data]);

  const outerRefCallback = useCallback((node: HTMLDivElement | null) => {
    outerRef.current = node;
    setOuterElement(node);
  }, []);

  useEffect(() => {
    const handleHorizontalScroll = () => {
      if (headerRef.current && outerElement) {
        headerRef.current.scrollLeft = outerElement.scrollLeft;
      }
    };

    if (outerElement) {
      outerElement.addEventListener('scroll', handleHorizontalScroll);
    }

    return () => {
      if (outerElement) {
        outerElement.removeEventListener('scroll', handleHorizontalScroll);
      }
    };
  }, [outerElement]);

  const createItemData = useCallback(
    (columnWidths: number[]): DynamicDataGridItemData => ({
      items: data,
      headers,
      columnWidths,
      startIndex,
    }),
    [data, headers, startIndex]
  );

  const getSortIcon = useCallback(
    (header: string, sortColumn?: string | null, sortDirection: 'asc' | 'desc' = 'asc') =>
      resolveSortIcon(header, sortColumn, sortDirection),
    []
  );

  return {
    hasData: data.length > 0,
    headers,
    baseColumnWidths,
    totalBaseWidth,
    listRef,
    headerRef,
    outerRefCallback,
    getSortIcon,
    createItemData,
  };
};
