import React, { useEffect, useRef, useLayoutEffect } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';

interface UPlotChartProps {
    data: uPlot.AlignedData;
    options: uPlot.Options;
    height?: number;
    className?: string; // For additional styling
    onCreate?: (u: uPlot) => void;
}

export const UPlotChart: React.FC<UPlotChartProps> = ({ data, options, height = 300, className, onCreate }) => {
    const chartRef = useRef<HTMLDivElement>(null);
    const uPlotRef = useRef<uPlot | null>(null);

    // Initial Create
    useLayoutEffect(() => {
        if (!chartRef.current) return;
        
        // Initial size (will be updated by ResizeObserver)
        const initWidth = chartRef.current.clientWidth || 800;
        
        // Merge options with dynamic width/height
        const finalOptions: uPlot.Options = { 
            ...options, 
            width: initWidth,
            height: height 
        };
        
        const u = new uPlot(finalOptions, data, chartRef.current);
        uPlotRef.current = u;
        if (onCreate) onCreate(u);

        const ro = new ResizeObserver(entries => {
            if (!uPlotRef.current) return;
            const entry = entries[0];
            // Use contentRect for precise content box size
            const width = entry.contentRect.width;
            const height = entry.contentRect.height;
            if (width <= 0 || height <= 0) return;
            uPlotRef.current.setSize({ width, height });
        });
        ro.observe(chartRef.current);

        return () => {
            if (uPlotRef.current) {
                uPlotRef.current.destroy();
                uPlotRef.current = null;
            }
            ro.disconnect();
        };
    }, []); // Empty deps: Recreating uPlot is expensive. Options should be stable.

    // Data Update
    useEffect(() => {
        if (uPlotRef.current) {
            uPlotRef.current.setData(data);
        }
    }, [data]);

    return (
        <div 
            ref={chartRef} 
            className={className} 
            style={{ width: '100%', height: '100%', position: 'relative' }} 
        />
    );
};
