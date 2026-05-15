import React, { useEffect, useLayoutEffect, useRef } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';

interface UPlotChartProps {
    data: uPlot.AlignedData;
    options: uPlot.Options;
    configKey?: string;
    height?: number;
    className?: string;
    onCreate?: (u: uPlot) => void;
}

type PreservedScale = {
    min: number;
    max: number;
};

type PreservedScaleMap = Record<string, PreservedScale>;

const buildPreservedScales = (u: uPlot): PreservedScaleMap => {
    return Object.entries(u.scales).reduce<PreservedScaleMap>((preservedScales, [scaleKey, scale]) => {
        const min = scale.min;
        const max = scale.max;

        if (typeof min !== 'number' || typeof max !== 'number' || !Number.isFinite(min) || !Number.isFinite(max)) {
            return preservedScales;
        }

        return {
            ...preservedScales,
            [scaleKey]: {
                min,
                max,
            },
        };
    }, {});
};

export const UPlotChart: React.FC<UPlotChartProps> = ({ data, options, configKey, height = 300, className, onCreate }) => {
    const chartRef = useRef<HTMLDivElement>(null);
    const uPlotRef = useRef<uPlot | null>(null);
    const preservedScalesRef = useRef<PreservedScaleMap>({});

    useLayoutEffect(() => {
        if (!chartRef.current) {
            return undefined;
        }

        const initWidth = chartRef.current.clientWidth || 800;
        const finalOptions: uPlot.Options = {
            ...options,
            width: initWidth,
            height,
        };

        const u = new uPlot(finalOptions, data, chartRef.current);
        uPlotRef.current = u;

        Object.entries(preservedScalesRef.current).forEach(([scaleKey, scale]) => {
            if (u.scales[scaleKey] !== undefined) {
                u.setScale(scaleKey, scale);
            }
        });

        onCreate?.(u);

        const ro = new ResizeObserver((entries) => {
            if (!uPlotRef.current) {
                return;
            }

            const entry = entries[0];
            const width = entry.contentRect.width;
            const nextHeight = entry.contentRect.height;

            if (width <= 0 || nextHeight <= 0) {
                return;
            }

            uPlotRef.current.setSize({ width, height: nextHeight });
        });
        ro.observe(chartRef.current);

        return () => {
            if (uPlotRef.current) {
                preservedScalesRef.current = buildPreservedScales(uPlotRef.current);
                uPlotRef.current.destroy();
                uPlotRef.current = null;
            }

            ro.disconnect();
        };
    }, [configKey]);

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
