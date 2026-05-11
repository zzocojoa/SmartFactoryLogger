import React, { Suspense } from 'react';
import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi, type MockedFunction } from 'vitest';
import type uPlot from 'uplot';
import type { FactoryData } from '../../../../shared/types';
import { buildThresholdStateFromConfig } from '../../../../shared/utils/thresholds';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import { UIContext } from '../../context/UIContext';
import { TIME_SERIES_CATALOG } from '../../timeseries/seriesCatalog';
import type { SeriesFrame } from '../../timeseries/seriesDataFrames';
import { TimeSeriesWidget } from './TimeSeriesWidget';

type UPlotChartMockProps = {
  data: uPlot.AlignedData;
  options: uPlot.Options;
  onCreate?: (uPlotInst: uPlot) => void;
};

type MockSetSeriesOptions = {
  show: boolean | undefined;
};

type MockUPlotInstance = {
  setSeries: MockedFunction<(seriesIndex: number, options: MockSetSeriesOptions) => void>;
};

const mocks = vi.hoisted(() => ({
  uPlotChartRender: vi.fn<(props: UPlotChartMockProps) => void>(),
  uPlotChartCreate: vi.fn<(instance: MockUPlotInstance) => void>(),
}));

const mockUPlotChartRender = mocks.uPlotChartRender;
const mockUPlotChartCreate = mocks.uPlotChartCreate;

vi.mock('../UPlotChart', async () => {
  const ReactModule = await vi.importActual<typeof import('react')>('react');

  return {
    UPlotChart: (props: UPlotChartMockProps) => {
      mockUPlotChartRender(props);

      ReactModule.useLayoutEffect(() => {
        const instance: MockUPlotInstance = {
          setSeries: vi.fn<(seriesIndex: number, options: MockSetSeriesOptions) => void>(),
        };
        mockUPlotChartCreate(instance);
        props.onCreate?.(instance as unknown as uPlot);
        return () => undefined;
      }, []);

      return ReactModule.createElement('div', { 'data-testid': 'uplot-chart' });
    },
  };
});

vi.mock('../../../../shared/hooks/useThemeContext', () => ({
  useTheme: () => ({ mode: 'dark' }),
}));

const buildFactoryData = (spotValue: number): FactoryData => ({
  Time: '2026-05-08T00:00:00.000Z',
  Status: 'OK',
  Speed: null,
  Press: null,
  Count: null,
  EndPos: null,
  Billet_Length: null,
  Spot: spotValue,
  Temp_F: null,
  Temp_B: null,
  Billet_Temp: null,
  Mold1: null,
  Mold2: null,
  Mold3: null,
  Mold4: null,
  Mold5: null,
  Mold6: null,
  At_Temp: null,
  At_Pre: null,
});

const buildSeriesFrame = (spotValue: number): SeriesFrame => ({
  fields: [
    {
      name: 'time',
      type: 'time',
      values: [1_777_660_800_000],
    },
    ...TIME_SERIES_CATALOG.map((meta): SeriesFrame['fields'][number] => ({
      name: meta.key,
      type: 'number',
      values: [meta.key === 'Spot' ? spotValue : null],
    })),
  ],
});

type TestUIProviderProps = {
  children: React.ReactNode;
};

const setLayoutEditing = (_editing: boolean): void => undefined;

const TestUIProvider = ({ children }: TestUIProviderProps): JSX.Element => {
  const [seriesWindowMin, setSeriesWindowMin] = React.useState<number>(30);
  const [seriesPaused, setSeriesPaused] = React.useState<boolean>(false);
  const [showThresholds, setShowThresholds] = React.useState<boolean>(true);

  return (
    <UIContext.Provider
      value={{
        seriesWindowMin,
        seriesPaused,
        showThresholds,
        layoutEditing: false,
        setSeriesWindowMin,
        setSeriesPaused,
        setShowThresholds,
        setLayoutEditing,
      }}
    >
      {children}
    </UIContext.Provider>
  );
};

const renderTimeSeriesWidget = (): void => {
  render(
    <TestUIProvider>
      <Suspense fallback={<div>loading chart</div>}>
        <TimeSeriesWidget />
      </Suspense>
    </TestUIProvider>
  );
};

const getCatalogSeriesIndex = (key: string): number => {
  const catalogIndex = TIME_SERIES_CATALOG.findIndex((meta) => meta.key === key);

  if (catalogIndex === -1) {
    throw new Error(`Unknown series key: ${key}`);
  }

  return catalogIndex + 1;
};

const getLatestUPlotProps = (): UPlotChartMockProps => {
  const latestCall = mockUPlotChartRender.mock.calls[mockUPlotChartRender.mock.calls.length - 1];

  if (latestCall === undefined) {
    throw new Error('UPlotChart was not rendered');
  }

  return latestCall[0];
};

const getLatestUPlotInstance = (): MockUPlotInstance => {
  const latestCall = mockUPlotChartCreate.mock.calls[mockUPlotChartCreate.mock.calls.length - 1];

  if (latestCall === undefined) {
    throw new Error('UPlotChart was not created');
  }

  return latestCall[0];
};

const getLegendButtonByValue = (valueText: string): HTMLButtonElement => {
  const button = screen.getByText(valueText).closest('button');

  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`Legend button was not found: ${valueText}`);
  }

  return button;
};

describe('TimeSeriesWidget render', () => {
  afterEach(() => {
    cleanup();
    mockUPlotChartRender.mockClear();
    mockUPlotChartCreate.mockClear();
    useDashboardStore.setState({
      data: null,
      timeSeriesAllFrame: null,
      thresholds: buildThresholdStateFromConfig(),
      lastDataAt: null,
      intervalSec: 0.2,
    });
  });

  it('updates legend values without rerendering chart when only store data changes', async () => {
    const timeSeriesAllFrame = buildSeriesFrame(11);
    useDashboardStore.setState({
      data: buildFactoryData(11),
      timeSeriesAllFrame,
      thresholds: buildThresholdStateFromConfig(),
      lastDataAt: 1,
      intervalSec: 0.2,
    });

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    expect(screen.getByText('11.0')).toBeInTheDocument();
    const initialChartRenderCount = mockUPlotChartRender.mock.calls.length;

    act(() => {
      useDashboardStore.getState().setData(buildFactoryData(22), 2);
    });

    await waitFor(() => {
      expect(screen.getByText('22.0')).toBeInTheDocument();
    });
    expect(screen.queryByText('11.0')).not.toBeInTheDocument();
    expect(mockUPlotChartRender).toHaveBeenCalledTimes(initialChartRenderCount);
  });

  it('syncs legend visibility to uPlot and preserves it after threshold remount', async () => {
    const timeSeriesAllFrame = buildSeriesFrame(11);
    useDashboardStore.setState({
      data: buildFactoryData(11),
      timeSeriesAllFrame,
      thresholds: buildThresholdStateFromConfig(),
      lastDataAt: 1,
      intervalSec: 0.2,
    });

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const initialCreateCount = mockUPlotChartCreate.mock.calls.length;
    const initialUPlotInstance = getLatestUPlotInstance();
    const spotSeriesIndex = getCatalogSeriesIndex('Spot');

    fireEvent.click(getLegendButtonByValue('11.0'));

    await waitFor(() => {
      expect(initialUPlotInstance.setSeries).toHaveBeenCalledWith(spotSeriesIndex, { show: false });
    });
    expect(mockUPlotChartCreate).toHaveBeenCalledTimes(initialCreateCount);

    fireEvent.click(screen.getByRole('checkbox'));

    await waitFor(() => {
      expect(mockUPlotChartCreate).toHaveBeenCalledTimes(initialCreateCount + 1);
    });

    const latestUPlotProps = getLatestUPlotProps();
    const latestUPlotInstance = getLatestUPlotInstance();
    expect(latestUPlotProps.options.series[spotSeriesIndex].show).toBe(false);
    expect(latestUPlotInstance.setSeries).toHaveBeenCalledWith(spotSeriesIndex, { show: false });
  });
});
