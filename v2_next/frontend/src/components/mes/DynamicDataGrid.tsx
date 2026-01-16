import React, { useMemo, useCallback, useRef, useEffect } from 'react';
import { FixedSizeList as List, ListChildComponentProps, areEqual } from 'react-window';
import AutoSizer from 'react-virtualized-auto-sizer';

interface DynamicDataGridProps {
    data: any[];
    sortColumn?: string | null;
    sortDirection?: 'asc' | 'desc';
    onSort?: (column: string) => void;
    startIndex?: number;
}

// Row component extracted to prevent re-creation
// We use a custom interface for itemData
interface ItemData {
    items: any[];
    headers: string[];
    columnWidths: number[];
    startIndex: number;
}

const Row = React.memo(({ index, style, data }: ListChildComponentProps<ItemData>) => {
    const { items, headers, columnWidths, startIndex } = data;
    const rowData = items[index];
    
    return (
        <div style={{ 
            ...style, 
            display: 'flex', 
            borderBottom: '1px solid var(--border-color)', 
            alignItems: 'center', 
            background: index % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent',
        }}>
            {/* Index Column */}
            <div style={{
                flex: `0 0 50px`,
                width: '50px',
                textAlign: 'center',
                padding: '8px',
                boxSizing: 'border-box',
                borderRight: '1px solid var(--border-color)',
                color: 'var(--text-secondary)',
                fontSize: '0.85rem'
            }}>
                {startIndex + index}
            </div>

            {/* Data Columns */}
            {headers.map((header, colIndex) => (
                <div key={header} style={{
                    flex: `0 0 ${columnWidths[colIndex]}px`,
                    width: `${columnWidths[colIndex]}px`,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    padding: '8px',
                    boxSizing: 'border-box',
                    borderRight: '1px solid var(--border-color)',
                }} title={String(rowData[header])}>
                    {String(rowData[header] ?? '')}
                </div>
            ))}
        </div>
    );
}, areEqual);

export const DynamicDataGrid: React.FC<DynamicDataGridProps> = ({ 
    data, 
    sortColumn, 
    sortDirection = 'asc',
    onSort,
    startIndex = 1
}) => {
    // 1. Extract Headers from first row
    const headers = useMemo(() => {
        if (!data || data.length === 0) return [];
        return Object.keys(data[0]);
    }, [data]);

    // Refs for scroll and header sync
    const listRef = useRef<List<any>>(null);
    const headerRef = useRef<HTMLDivElement>(null);
    const outerRef = useRef<HTMLDivElement | null>(null); // Mutable ref for scroll sync

    // Effect to reset scroll position when data changes (e.g., changing tabs or pages)
    useEffect(() => {
        if (listRef.current) {
            listRef.current.scrollTo(0);
        }
        if (headerRef.current) {
            headerRef.current.scrollLeft = 0;
        }
    }, [data]);

    // Cleanup scroll listener if component unmounts
    // Using a state variable to trigger re-run when outerRef is assigned
    const [outerElement, setOuterElement] = React.useState<HTMLDivElement | null>(null);

    // Callback ref to capture when List's outer element is mounted
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
    }, [outerElement]); // Re-run when outerElement changes


    // 2. Base Column Widths (Minimums)
    const { baseColumnWidths, totalBaseWidth } = useMemo(() => {
        if (headers.length === 0) return { baseColumnWidths: [], totalBaseWidth: 0 };

        const widths = headers.map(header => {
            // Updated heuristic for tighter fit
            const estimated = header.length * 13 + 40; 
            return Math.max(100, estimated);
        });

        const total = widths.reduce((sum, w) => sum + w, 0);
        return { baseColumnWidths: widths, totalBaseWidth: total };
    }, [headers]);

    // Sort icon helper
    const getSortIcon = (header: string) => {
        if (sortColumn !== header) return ' ';
        return sortDirection === 'asc' ? ' ▲' : ' ▼';
    };

    if (data.length === 0) {
        return <div style={{ padding: '2rem', color: 'var(--text-secondary)' }}>No data available to display.</div>;
    }

const SCROLLBAR_WIDTH = 24; // Increased buffer to prevent horizontal scroll
const NUMBER_COL_WIDTH = 50; // Use const for consistency

    return (
        <div style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <AutoSizer>
                {({ height, width }) => {
                    // 3. Calculate Responsive Widths
                    // Check if vertical scrollbar is needed
                    const totalRowHeight = data.length * 40;
                    const bodyHeight = height - 40;
                    const hasVerticalScroll = totalRowHeight > bodyHeight;
                    
                    // Subtract scrollbar width AND Number column width from available space
                    const availableSpace = hasVerticalScroll ? width - SCROLLBAR_WIDTH : width;
                    const availableForColumns = availableSpace - NUMBER_COL_WIDTH;

                    // If available width > content width, distribute extra space
                    let finalColumnWidths = baseColumnWidths;
                    let finalTotalDataWidth = totalBaseWidth;

                    if (availableForColumns > totalBaseWidth) {
                        const extraSpace = availableForColumns - totalBaseWidth;
                        const bonusPerColumn = Math.floor(extraSpace / baseColumnWidths.length);
                        finalColumnWidths = baseColumnWidths.map(w => w + bonusPerColumn);
                        // Recalculate total width to match exactly the sum of floored widths
                        finalTotalDataWidth = finalColumnWidths.reduce((sum, w) => sum + w, 0); 
                    }

                    const totalScrollWidth = finalTotalDataWidth + NUMBER_COL_WIDTH;

                    // Prepare itemData for Row
                    const itemData: ItemData = {
                        items: data,
                        headers,
                        columnWidths: finalColumnWidths,
                        startIndex
                    };

                    return (
                        <div style={{ height, width, display: 'flex', flexDirection: 'column' }}>
                             {/* Header */}
                             <div 
                                 ref={headerRef}
                                 style={{ 
                                     flex: '0 0 40px', 
                                     width: '100%',
                                     background: 'var(--bg-secondary)', 
                                     borderBottom: '1px solid var(--border-color)', 
                                     color: 'var(--text-primary)', 
                                     fontWeight: 600,
                                     overflowX: 'hidden', // Hide header scrollbar
                                     overflowY: 'hidden',
                                     // scrollbarWidth: 'thin' // No longer needed
                                 }}
                             >
                                <div style={{ display: 'flex', width: totalScrollWidth, height: '100%', alignItems: 'center' }}>
                                    {/* Number Header */}
                                    <div style={{
                                        flex: `0 0 ${NUMBER_COL_WIDTH}px`,
                                        width: `${NUMBER_COL_WIDTH}px`,
                                        textAlign: 'center',
                                        padding: '8px',
                                        boxSizing: 'border-box',
                                        borderRight: '1px solid var(--border-color)',
                                        color: 'var(--text-secondary)'
                                    }}>
                                        No.
                                    </div>

                                    {/* Data Headers */}
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
                                            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                {header}
                                            </span>
                                            <span style={{ 
                                                fontSize: '0.7rem', 
                                                color: sortColumn === header ? 'var(--accent-main)' : 'transparent',
                                                minWidth: '12px'
                                            }}>
                                                {getSortIcon(header)}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Body */}
                            <div style={{ flex: 1 }}>
                                <List
                                    ref={listRef}
                                    outerRef={outerRefCallback} // Use callback ref for scroll sync
                                    height={bodyHeight}
                                    itemCount={data.length}
                                    itemSize={40}
                                    width={width}
                                    itemData={itemData}
                                >
                                    {Row}
                                </List>
                            </div>
                        </div>
                    );
                }}
            </AutoSizer>
        </div>
    );
};

