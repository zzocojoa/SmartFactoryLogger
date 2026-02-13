import React from 'react';
import { FixedSizeList as List, areEqual } from 'react-window';
import type { ListChildComponentProps } from 'react-window';
import AutoSizer from 'react-virtualized-auto-sizer';
import type {
  DynamicDataGridItemData,
  DynamicDataGridViewProps,
} from '../types/DynamicDataGrid.types';
import {
  calculateResponsiveLayout,
  GRID_HEADER_HEIGHT,
  GRID_NUMBER_COLUMN_WIDTH,
  GRID_ROW_HEIGHT,
} from '../utils/DynamicDataGrid.utils';

const DynamicDataGridRow = React.memo(
  ({ index, style, data }: ListChildComponentProps<DynamicDataGridItemData>) => {
    const { items, headers, columnWidths, startIndex } = data;
    const rowData = items[index];

    return (
      <div
        style={{
          ...style,
          display: 'flex',
          borderBottom: '1px solid var(--border-color)',
          alignItems: 'center',
          background: index % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent',
        }}
      >
        <div
          style={{
            flex: `0 0 ${GRID_NUMBER_COLUMN_WIDTH}px`,
            width: `${GRID_NUMBER_COLUMN_WIDTH}px`,
            textAlign: 'center',
            padding: '8px',
            boxSizing: 'border-box',
            borderRight: '1px solid var(--border-color)',
            color: 'var(--text-secondary)',
            fontSize: '0.85rem',
          }}
        >
          {startIndex + index}
        </div>

        {headers.map((header, columnIndex) => (
          <div
            key={header}
            style={{
              flex: `0 0 ${columnWidths[columnIndex]}px`,
              width: `${columnWidths[columnIndex]}px`,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              padding: '8px',
              boxSizing: 'border-box',
              borderRight: '1px solid var(--border-color)',
            }}
            title={String(rowData[header])}
          >
            {String(rowData[header] ?? '')}
          </div>
        ))}
      </div>
    );
  },
  areEqual
);

export const DynamicDataGridView: React.FC<DynamicDataGridViewProps> = ({
  data,
  sortColumn,
  sortDirection = 'asc',
  onSort,
  model,
}) => {
  const {
    hasData,
    headers,
    baseColumnWidths,
    totalBaseWidth,
    listRef,
    headerRef,
    outerRefCallback,
    getSortIcon,
    createItemData,
  } = model;

  if (!hasData) {
    return <div style={{ padding: '2rem', color: 'var(--text-secondary)' }}>No data available to display.</div>;
  }

  return (
    <div style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <AutoSizer>
        {({ height, width }) => {
          const { bodyHeight, finalColumnWidths, totalScrollWidth } = calculateResponsiveLayout({
            width,
            height,
            rowCount: data.length,
            baseColumnWidths,
            totalBaseWidth,
          });
          const itemData = createItemData(finalColumnWidths);

          return (
            <div style={{ height, width, display: 'flex', flexDirection: 'column' }}>
              <div
                ref={headerRef}
                style={{
                  flex: `0 0 ${GRID_HEADER_HEIGHT}px`,
                  width: '100%',
                  background: 'var(--bg-secondary)',
                  borderBottom: '1px solid var(--border-color)',
                  color: 'var(--text-primary)',
                  fontWeight: 600,
                  overflowX: 'hidden',
                  overflowY: 'hidden',
                }}
              >
                <div style={{ display: 'flex', width: totalScrollWidth, height: '100%', alignItems: 'center' }}>
                  <div
                    style={{
                      flex: `0 0 ${GRID_NUMBER_COLUMN_WIDTH}px`,
                      width: `${GRID_NUMBER_COLUMN_WIDTH}px`,
                      textAlign: 'center',
                      padding: '8px',
                      boxSizing: 'border-box',
                      borderRight: '1px solid var(--border-color)',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    No.
                  </div>

                  {headers.map((header, index) => (
                    <div
                      key={header}
                      style={{
                        flex: `0 0 ${finalColumnWidths[index]}px`,
                        width: `${finalColumnWidths[index]}px`,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        padding: '8px',
                        boxSizing: 'border-box',
                        borderRight: '1px solid var(--border-color)',
                        cursor: onSort ? 'pointer' : 'default',
                        userSelect: 'none',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                      onClick={() => onSort?.(header)}
                    >
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{header}</span>
                      <span
                        style={{
                          fontSize: '0.7rem',
                          color: sortColumn === header ? 'var(--accent-main)' : 'transparent',
                          minWidth: '12px',
                        }}
                      >
                        {getSortIcon(header, sortColumn, sortDirection)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ flex: 1 }}>
                <List
                  ref={listRef}
                  outerRef={outerRefCallback}
                  height={bodyHeight}
                  itemCount={data.length}
                  itemSize={GRID_ROW_HEIGHT}
                  width={width}
                  itemData={itemData}
                >
                  {DynamicDataGridRow}
                </List>
              </div>
            </div>
          );
        }}
      </AutoSizer>
    </div>
  );
};
