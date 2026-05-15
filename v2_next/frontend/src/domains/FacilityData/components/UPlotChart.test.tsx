import '@testing-library/jest-dom/vitest';
import { cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import type uPlot from 'uplot';
import { UPlotChart } from './UPlotChart';

type MockUPlotInstance = {
    setData: Mock;
    setScale: Mock;
    setSize: Mock;
    destroy: Mock;
    scales: Record<string, { min?: number; max?: number }>;
};

const uPlotMocks = vi.hoisted(() => ({
    instances: [] as MockUPlotInstance[],
}));

vi.mock('uplot', () => ({
    default: vi.fn().mockImplementation(() => {
        const instance: MockUPlotInstance = {
            setData: vi.fn(),
            setScale: vi.fn(),
            setSize: vi.fn(),
            destroy: vi.fn(),
            scales: {
                x: {
                    min: 1,
                    max: 2,
                },
            },
        };

        uPlotMocks.instances.push(instance);

        return instance;
    }),
}));

class ResizeObserverMock {
    observe(): void {}
    disconnect(): void {}
}

const buildData = (): uPlot.AlignedData => [[1, 2, 3], [10, 20, 30]] as uPlot.AlignedData;

const buildOptions = (): uPlot.Options => ({
    width: 800,
    height: 300,
    series: [{}, { label: 'Spot' }],
});

describe('UPlotChart', () => {
    beforeEach(() => {
        vi.stubGlobal('ResizeObserver', ResizeObserverMock);
    });

    afterEach(() => {
        cleanup();
        vi.unstubAllGlobals();
        vi.clearAllMocks();
        uPlotMocks.instances.length = 0;
    });

    it('resets scales when resetScalesKey changes with the same data reference', () => {
        const data = buildData();
        const options = buildOptions();
        const { rerender } = render(<UPlotChart data={data} options={options} resetScalesKey={30} />);
        const instance = uPlotMocks.instances[0];

        instance.setData.mockClear();

        rerender(<UPlotChart data={data} options={options} resetScalesKey={5} />);

        expect(instance.setData).toHaveBeenCalledTimes(1);
        expect(instance.setData).toHaveBeenCalledWith(data, true);
    });
});
