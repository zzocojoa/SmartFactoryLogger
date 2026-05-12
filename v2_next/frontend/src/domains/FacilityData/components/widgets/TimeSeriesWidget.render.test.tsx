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
import type { TimeSeriesKey } from '../../timeseries/seriesCatalog';
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
const MOLD_SERIES_KEYS: readonly TimeSeriesKey[] = ['Mold1', 'Mold2', 'Mold3', 'Mold4', 'Mold5', 'Mold6'];

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

const renderTimeSeriesWidgets = (widgetCount: number): void => {
  const widgetIndexes: number[] = Array.from({ length: widgetCount }, (_value, index) => index);

  render(
    <TestUIProvider>
      {widgetIndexes.map((index) => (
        <Suspense key={index} fallback={<div>loading chart</div>}>
          <TimeSeriesWidget />
        </Suspense>
      ))}
    </TestUIProvider>
  );
};

const renderTimeSeriesWidget = (): void => {
  renderTimeSeriesWidgets(1);
};

const seedTimeSeriesData = (spotValue: number): void => {
  useDashboardStore.setState({
    data: buildFactoryData(spotValue),
    timeSeriesAllFrame: buildSeriesFrame(spotValue),
    thresholds: buildThresholdStateFromConfig(),
    lastDataAt: 1,
    intervalSec: 0.2,
  });
};

const getCatalogSeriesIndex = (key: TimeSeriesKey): number => {
  const catalogIndex = TIME_SERIES_CATALOG.findIndex((meta) => meta.key === key);

  if (catalogIndex === -1) {
    throw new Error(`Unknown series key: ${key}`);
  }

  return catalogIndex + 1;
};

const getCatalogSeriesLabel = (key: TimeSeriesKey): string => {
  const meta = TIME_SERIES_CATALOG.find((seriesMeta) => seriesMeta.key === key);

  if (meta === undefined) {
    throw new Error(`Unknown series key: ${key}`);
  }

  return meta.label;
};

const getLatestUPlotProps = (): UPlotChartMockProps => {
  const latestCall = mockUPlotChartRender.mock.calls[mockUPlotChartRender.mock.calls.length - 1];

  if (latestCall === undefined) {
    throw new Error('UPlotChart was not rendered');
  }

  return latestCall[0];
};

const getUPlotPropsAtIndex = (renderIndex: number): UPlotChartMockProps => {
  const call = mockUPlotChartRender.mock.calls[renderIndex];

  if (call === undefined) {
    throw new Error(`UPlotChart render call was not found: ${renderIndex}`);
  }

  return call[0];
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

const getButtonByText = (text: string | RegExp): HTMLButtonElement => {
  const button = screen.getByText(text).closest('button');

  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`Button was not found: ${text}`);
  }

  return button;
};

const expectHiddenActiveSeriesState = (button: HTMLButtonElement): void => {
  expect(button).toHaveTextContent('더 보기(활성 1)');
  expect(button).toHaveAccessibleName('더 보기 (활성 1)');
};

const buildTooltipPlot = (cursorLeft: number, cursorTop: number, spotValue: number): uPlot => {
  return {
    bbox: { left: 80, top: 40, width: 420, height: 180 },
    cursor: { left: cursorLeft, top: cursorTop, idx: 0 },
    data: [[1_777_660_800], [spotValue]],
    over: {
      getBoundingClientRect: () => ({ left: 90, top: 60, width: 420, height: 180 }),
    },
    series: [
      { show: true, stroke: '#aaa', label: 'Time' },
      { show: true, stroke: '#f00', label: 'Spot' },
    ],
  } as unknown as uPlot;
};

const buildHiddenTooltipPlot = (cursorLeft: number, cursorTop: number): uPlot => {
  return {
    bbox: { left: 80, top: 40, width: 420, height: 180 },
    cursor: { left: cursorLeft, top: cursorTop, idx: null },
    data: [[1_777_660_800], [null]],
    over: {
      getBoundingClientRect: () => ({ left: 90, top: 60, width: 420, height: 180 }),
    },
    series: [
      { show: true, stroke: '#aaa', label: 'Time' },
      { show: true, stroke: '#f00', label: 'Spot' },
    ],
  } as unknown as uPlot;
};

const getSetCursorHook = (props: UPlotChartMockProps): ((plot: uPlot) => void) => {
  const setCursorHook = props.options.hooks?.setCursor?.[0];

  if (setCursorHook === undefined) {
    throw new Error('setCursor hook was not found');
  }

  return setCursorHook;
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

  it('toggles live mode to paused with pressed state', async () => {
    seedTimeSeriesData(11);

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const liveButton = screen.getByRole('button', { name: 'Live' });

    fireEvent.click(liveButton);

    const pausedButton = screen.getByRole('button', { name: 'Paused' });
    expect(pausedButton).toHaveAttribute('aria-pressed', 'true');
  });

  it('keeps mold series out of the default legend and toggles them from the expanded series list', async () => {
    seedTimeSeriesData(11);

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const initialUPlotInstance = getLatestUPlotInstance();
    const moreButton = getButtonByText('더 보기');

    MOLD_SERIES_KEYS.forEach((key) => {
      expect(screen.queryByText(getCatalogSeriesLabel(key))).not.toBeInTheDocument();
    });

    expect(moreButton).toHaveAccessibleName(/더\s*보기/);

    fireEvent.click(moreButton);

    MOLD_SERIES_KEYS.forEach((key) => {
      expect(screen.getByText(getCatalogSeriesLabel(key))).toBeInTheDocument();
    });

    const mold1Button = screen.getByText(getCatalogSeriesLabel('Mold1')).closest('button');

    if (!(mold1Button instanceof HTMLButtonElement)) {
      throw new Error('Mold1 series toggle button was not found');
    }

    fireEvent.click(mold1Button);

    await waitFor(() => {
      expect(initialUPlotInstance.setSeries).toHaveBeenCalledWith(getCatalogSeriesIndex('Mold1'), { show: true });
    });
    expect(mold1Button).toHaveAttribute('aria-pressed', 'true');
  });

  it('shows hidden active mold series state after collapsing the expanded list', async () => {
    seedTimeSeriesData(11);

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');

    fireEvent.click(getButtonByText('더 보기'));
    fireEvent.click(getButtonByText(getCatalogSeriesLabel('Mold1')));
    fireEvent.click(getButtonByText('기본 범례'));

    const collapsedMoreButton = getButtonByText(/더\s*보기/);

    expectHiddenActiveSeriesState(collapsedMoreButton);
  });

  it('labels snapshot action as a whole dashboard snapshot', async () => {
    seedTimeSeriesData(11);

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const snapshotButton = screen.getByRole('button', { name: /스냅샷/ });
    const snapshotAccessibleDescription = snapshotButton.getAttribute('aria-label') ?? snapshotButton.getAttribute('title') ?? '';

    expect(snapshotButton).toHaveTextContent('스냅샷');
    expect(snapshotAccessibleDescription).toMatch(/전체\s*대시보드.*스냅샷|스냅샷.*전체\s*대시보드/);
  });

  it('creates independent tooltip containers without duplicate ids for multiple widgets', async () => {
    seedTimeSeriesData(11);

    renderTimeSeriesWidgets(2);

    const charts = await screen.findAllByTestId('uplot-chart');
    expect(charts).toHaveLength(2);

    const chartContainers: HTMLElement[] = charts.map((chart) => {
      const chartContainer = chart.parentElement;

      if (chartContainer === null) {
        throw new Error('Chart container was not found');
      }

      return chartContainer;
    });
    const tooltips: HTMLDivElement[] = chartContainers.map((chartContainer) => {
      const tooltip = chartContainer.querySelector<HTMLDivElement>('.uplot-tooltip');

      if (tooltip === null) {
        throw new Error('Tooltip element was not found');
      }

      expect(chartContainer.querySelectorAll('.uplot-tooltip')).toHaveLength(1);

      return tooltip;
    });

    tooltips.forEach((tooltip) => {
      Object.defineProperty(tooltip, 'offsetWidth', { configurable: true, value: 120 });
      Object.defineProperty(tooltip, 'offsetHeight', { configurable: true, value: 40 });
    });

    chartContainers.forEach((chartContainer) => {
      Object.defineProperty(chartContainer, 'getBoundingClientRect', {
        configurable: true,
        value: () => ({ left: 10, top: 20, width: 500, height: 260 }),
      });
    });

    const tooltipIds = Array.from(document.querySelectorAll<HTMLElement>('.uplot-tooltip'))
      .map((tooltip) => tooltip.id)
      .filter((id) => id.length > 0);

    expect(new Set(tooltipIds).size).toBe(tooltipIds.length);

    const firstSetCursorHook = getSetCursorHook(getUPlotPropsAtIndex(0));
    const secondSetCursorHook = getSetCursorHook(getUPlotPropsAtIndex(1));

    firstSetCursorHook(buildTooltipPlot(100, 80, 11));

    expect(tooltips[0].style.display).toBe('block');
    expect(tooltips[0]).toHaveTextContent('11.0');
    expect(tooltips[1].style.display).not.toBe('block');
    expect(tooltips[1]).not.toHaveTextContent('11.0');

    firstSetCursorHook(buildHiddenTooltipPlot(100, 80));
    secondSetCursorHook(buildTooltipPlot(120, 90, 22));

    expect(tooltips[0].style.display).toBe('none');
    expect(tooltips[0]).not.toHaveTextContent('22.0');
    expect(tooltips[1].style.display).toBe('block');
    expect(tooltips[1]).toHaveTextContent('22.0');
  });

  it('clamps tooltip position using wrapper-local css coordinates', async () => {
    seedTimeSeriesData(11);

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const latestUPlotProps = getLatestUPlotProps();
    const tooltip = document.querySelector<HTMLDivElement>('.uplot-tooltip');
    const setCursorHook = getSetCursorHook(latestUPlotProps);

    if (tooltip === null) {
      throw new Error('Tooltip element was not found');
    }

    Object.defineProperty(tooltip, 'offsetWidth', { configurable: true, value: 120 });
    Object.defineProperty(tooltip, 'offsetHeight', { configurable: true, value: 40 });
    const chartWrapper = tooltip.parentElement;

    if (chartWrapper === null) {
      throw new Error('Chart wrapper element was not found');
    }

    Object.defineProperty(chartWrapper, 'getBoundingClientRect', {
      configurable: true,
      value: () => ({ left: 10, top: 20, width: 500, height: 260 }),
    });

    setCursorHook(buildTooltipPlot(100, 80, 11));

    expect(tooltip.style.display).toBe('block');
    expect(tooltip.style.transform).toBe('translate(200px, 120px)');

    setCursorHook(buildTooltipPlot(405, 205, 11));

    expect(tooltip.style.display).toBe('block');
    expect(tooltip.style.transform).toBe('translate(372px, 212px)');
  });
});
