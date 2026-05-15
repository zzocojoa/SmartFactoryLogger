import React, { Suspense } from 'react';
import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi, type MockedFunction } from 'vitest';
import type uPlot from 'uplot';
import type { FactoryData, ThresholdState } from '../../../../shared/types';
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
  configKey?: string;
  resetScalesKey?: string | number;
  onCreate?: (uPlotInst: uPlot) => void;
};

type MockSetSeriesOptions = {
  focus?: boolean;
  show?: boolean;
};

type MockUPlotSeries = Partial<uPlot.Series> & {
  alpha?: number;
  width?: number;
};

type MockUPlotScales = {
  x: {
    min: number;
    max: number;
  };
};

type MockUPlotInstance = {
  setSeries: MockedFunction<(seriesIndex: number | null, options: MockSetSeriesOptions) => void>;
  redraw: MockedFunction<(rebuildPaths?: boolean, recalcAxes?: boolean) => void>;
  options: uPlot.Options;
  series: MockUPlotSeries[];
  scales: MockUPlotScales;
};

type MockThresholdContext = {
  save: MockedFunction<() => void>;
  beginPath: MockedFunction<() => void>;
  setLineDash: MockedFunction<(segments: number[]) => void>;
  moveTo: MockedFunction<(x: number, y: number) => void>;
  lineTo: MockedFunction<(x: number, y: number) => void>;
  stroke: MockedFunction<() => void>;
  fillText: MockedFunction<(text: string, x: number, y: number) => void>;
  restore: MockedFunction<() => void>;
  lineWidth: number;
  strokeStyle: string | CanvasGradient | CanvasPattern;
  fillStyle: string | CanvasGradient | CanvasPattern;
  font: string;
  textAlign: CanvasTextAlign;
  textBaseline: CanvasTextBaseline;
};

type ThresholdDrawPlotFixture = {
  plot: uPlot;
  context: MockThresholdContext;
  valToPos: MockedFunction<(value: number, scaleKey: string, canvasPixels: boolean) => number>;
};

const mocks = vi.hoisted(() => ({
  uPlotChartRender: vi.fn<(props: UPlotChartMockProps) => void>(),
  uPlotChartCreate: vi.fn<(instance: MockUPlotInstance) => void>(),
}));

const mockUPlotChartRender = mocks.uPlotChartRender;
const mockUPlotChartCreate = mocks.uPlotChartCreate;
const MOLD_SERIES_KEYS: readonly TimeSeriesKey[] = ['Mold1', 'Mold2', 'Mold3', 'Mold4', 'Mold5', 'Mold6'];
const SPEED_RIGHT_SCALE_KEY = 'speedRight';

vi.mock('../UPlotChart', async () => {
  const ReactModule = await vi.importActual<typeof import('react')>('react');

  return {
    UPlotChart: (props: UPlotChartMockProps) => {
      mockUPlotChartRender(props);

      ReactModule.useLayoutEffect(() => {
        const series = (props.options.series ?? []).map((seriesOption) => ({ ...seriesOption })) as MockUPlotSeries[];
        const instance: MockUPlotInstance = {
          setSeries: vi.fn<(seriesIndex: number | null, options: MockSetSeriesOptions) => void>((seriesIndex, options) => {
            if (seriesIndex === null) {
              return;
            }

            series[seriesIndex] = {
              ...series[seriesIndex],
              ...options,
            };
          }),
          redraw: vi.fn<(rebuildPaths?: boolean, recalcAxes?: boolean) => void>(),
          options: props.options,
          series,
          scales: {
            x: {
              min: 1_777_660_800,
              max: 1_777_661_100,
            },
          },
        };
        mockUPlotChartCreate(instance);
        props.onCreate?.(instance as unknown as uPlot);
        return () => undefined;
      }, [props.configKey]);

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

const buildSeriesFrameWithPointCount = (
  pointCount: number,
  getValue: (key: TimeSeriesKey, index: number) => number | null
): SeriesFrame => {
  const timeValues = Array.from({ length: pointCount }, (_value, index) => 1_777_660_800_000 + index * 1000);

  return {
    fields: [
      {
        name: 'time',
        type: 'time',
        values: timeValues,
      },
      ...TIME_SERIES_CATALOG.map((meta): SeriesFrame['fields'][number] => ({
        name: meta.key,
        type: 'number',
        values: timeValues.map((_timeValue, index) => getValue(meta.key, index)),
      })),
    ],
  };
};

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

const seedTimeSeriesDataWithThresholds = (spotValue: number, thresholds: ThresholdState): void => {
  useDashboardStore.setState({
    data: buildFactoryData(spotValue),
    timeSeriesAllFrame: buildSeriesFrame(spotValue),
    thresholds,
    lastDataAt: 1,
    intervalSec: 0.2,
  });
};

const buildSpotThresholdState = (value: number, enabled: boolean): ThresholdState => {
  const baseThresholds = buildThresholdStateFromConfig();

  return {
    ...baseThresholds,
    masterOn: true,
    entries: {
      ...baseThresholds.entries,
      spot: {
        enabled,
        value,
      },
    },
  };
};

const buildSpeedAndSpotThresholdState = (speedValue: number, spotValue: number): ThresholdState => {
  const baseThresholds = buildThresholdStateFromConfig();

  return {
    ...baseThresholds,
    masterOn: true,
    entries: {
      ...baseThresholds.entries,
      speed: {
        enabled: true,
        value: speedValue,
      },
      spot: {
        enabled: true,
        value: spotValue,
      },
    },
  };
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

const getSeriesOptionByKey = (props: UPlotChartMockProps, key: TimeSeriesKey): uPlot.Series => {
  const label = getCatalogSeriesLabel(key);
  const seriesOption = props.options.series?.find((option) => option.label === label);

  if (seriesOption === undefined) {
    throw new Error(`Series option was not found: ${key}`);
  }

  return seriesOption;
};

const getSeriesOptionIndexByKey = (props: UPlotChartMockProps, key: TimeSeriesKey): number => {
  const label = getCatalogSeriesLabel(key);
  const seriesOptionIndex = props.options.series?.findIndex((option) => option.label === label) ?? -1;

  if (seriesOptionIndex === -1) {
    throw new Error(`Series option index was not found: ${key}`);
  }

  return seriesOptionIndex;
};

const getAxisOptionByScale = (props: UPlotChartMockProps, scaleKey: string): uPlot.Axis => {
  const axisOption = props.options.axes?.find((axis) => axis.scale === scaleKey);

  if (axisOption === undefined) {
    throw new Error(`Axis option was not found: ${scaleKey}`);
  }

  return axisOption;
};

const getXScaleRangeFromOptions = (options: uPlot.Options): uPlot.Range.Function => {
  const range = options.scales?.x?.range;

  if (typeof range !== 'function') {
    throw new Error('X scale range function was not found');
  }

  return range;
};

const getXScaleRange = (props: UPlotChartMockProps): uPlot.Range.Function => {
  return getXScaleRangeFromOptions(props.options);
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
      { show: true, stroke: () => '#f00', label: 'Spot' },
    ],
  } as unknown as uPlot;
};

const buildMultiSeriesTooltipPlot = (cursorLeft: number, cursorTop: number): uPlot => {
  return {
    bbox: { left: 80, top: 40, width: 420, height: 180 },
    cursor: { left: cursorLeft, top: cursorTop, idx: 0 },
    data: [[1_777_660_800], [11], [22]],
    over: {
      getBoundingClientRect: () => ({ left: 90, top: 60, width: 420, height: 180 }),
    },
    series: [
      { show: true, stroke: '#aaa', label: 'Time' },
      { show: true, stroke: () => '#f00', label: getCatalogSeriesLabel('Spot') },
      { show: true, stroke: () => '#fa0', label: getCatalogSeriesLabel('Press') },
    ],
  } as unknown as uPlot;
};

const buildDenseTooltipPlot = (cursorLeft: number, cursorTop: number): uPlot => {
  const visibleMetas = TIME_SERIES_CATALOG.filter((meta) => !MOLD_SERIES_KEYS.includes(meta.key));
  const values = visibleMetas.map((_meta, index) => 100 + index);

  return {
    bbox: { left: 80, top: 40, width: 420, height: 180 },
    cursor: { left: cursorLeft, top: cursorTop, idx: 0 },
    data: [[1_777_660_800], ...values.map((value) => [value])],
    over: {
      getBoundingClientRect: () => ({ left: 90, top: 60, width: 420, height: 180 }),
    },
    series: [
      { show: true, stroke: '#aaa', label: 'Time' },
      ...visibleMetas.map((meta) => ({ show: true, stroke: () => '#f00', label: meta.label })),
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
      { show: true, stroke: () => '#f00', label: 'Spot' },
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

const getDrawHook = (props: UPlotChartMockProps): ((plot: uPlot) => void) => {
  const drawHook = props.options.hooks?.draw?.[0];

  if (drawHook === undefined) {
    throw new Error('draw hook was not found');
  }

  return drawHook;
};

const buildThresholdDrawPlot = (): ThresholdDrawPlotFixture => {
  const context: MockThresholdContext = {
    save: vi.fn<() => void>(),
    beginPath: vi.fn<() => void>(),
    setLineDash: vi.fn<(segments: number[]) => void>(),
    moveTo: vi.fn<(x: number, y: number) => void>(),
    lineTo: vi.fn<(x: number, y: number) => void>(),
    stroke: vi.fn<() => void>(),
    fillText: vi.fn<(text: string, x: number, y: number) => void>(),
    restore: vi.fn<() => void>(),
    lineWidth: 0,
    strokeStyle: '',
    fillStyle: '',
    font: '',
    textAlign: 'left',
    textBaseline: 'alphabetic',
  };
  const valToPos = vi.fn<(value: number, scaleKey: string, canvasPixels: boolean) => number>().mockReturnValue(100);
  const plot = {
    ctx: context as unknown as CanvasRenderingContext2D,
    bbox: { left: 80, top: 40, width: 420, height: 180 },
    valToPos,
  } as unknown as uPlot;

  return { plot, context, valToPos };
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

  it('renders the uPlot chart inside the responsive time-series chart wrapper', async () => {
    seedTimeSeriesData(11);

    renderTimeSeriesWidget();

    const chart = await screen.findByTestId('uplot-chart');
    const chartWrapper = chart.closest('.timeseries-chart-wrapper');

    expect(chartWrapper).toBeInTheDocument();
    expect(chartWrapper).toContainElement(chart);
  });

  it('passes only active series and downsampled render points to uPlot', async () => {
    const pointCount = 2_000;
    const timeSeriesAllFrame = buildSeriesFrameWithPointCount(pointCount, (key, index) => (key === 'Spot' ? index : null));
    useDashboardStore.setState({
      data: buildFactoryData(11),
      timeSeriesAllFrame,
      thresholds: buildThresholdStateFromConfig(),
      lastDataAt: 1,
      intervalSec: 0.2,
    });

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const latestUPlotProps = getLatestUPlotProps();

    expect(latestUPlotProps.data).toHaveLength(TIME_SERIES_CATALOG.length - MOLD_SERIES_KEYS.length + 1);
    expect(latestUPlotProps.options.series).toHaveLength(latestUPlotProps.data.length);
    expect(latestUPlotProps.data[0].length).toBeLessThan(pointCount);
    expect(latestUPlotProps.data[0].length).toBeLessThanOrEqual(1_600);
    expect(timeSeriesAllFrame.fields[0].values).toHaveLength(pointCount);
  });

  it('caps render points even when every visible series value is null', async () => {
    const pointCount = 2_000;
    const timeSeriesAllFrame = buildSeriesFrameWithPointCount(pointCount, () => null);
    useDashboardStore.setState({
      data: buildFactoryData(11),
      timeSeriesAllFrame,
      thresholds: buildThresholdStateFromConfig(),
      lastDataAt: 1,
      intervalSec: 0.2,
    });

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const latestUPlotProps = getLatestUPlotProps();

    expect(latestUPlotProps.data[0].length).toBeLessThan(pointCount);
    expect(latestUPlotProps.data[0].length).toBeLessThanOrEqual(1_600);
  });

  it('preserves visible secondary series spikes while downsampling', async () => {
    const pointCount = 2_000;
    const pressSpikeValue = 999;
    const pressSpikeIndex = 997;
    const timeSeriesAllFrame = buildSeriesFrameWithPointCount(pointCount, (key, index) => {
      if (key === 'Spot') {
        return 500;
      }

      if (key === 'Press' && index === pressSpikeIndex) {
        return pressSpikeValue;
      }

      return key === 'Press' ? 0 : null;
    });

    useDashboardStore.setState({
      data: buildFactoryData(11),
      timeSeriesAllFrame,
      thresholds: buildThresholdStateFromConfig(),
      lastDataAt: 1,
      intervalSec: 0.2,
    });

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const latestUPlotProps = getLatestUPlotProps();
    const pressSeriesIndex = latestUPlotProps.options.series?.findIndex((series) => series.label === getCatalogSeriesLabel('Press')) ?? -1;

    expect(pressSeriesIndex).toBeGreaterThan(0);
    expect(latestUPlotProps.data[pressSeriesIndex]).toContain(pressSpikeValue);
    expect(latestUPlotProps.data[0].length).toBeLessThanOrEqual(1_600);
  });

  it('sorts projected render data by timestamp before passing it to uPlot', async () => {
    const timeSeriesAllFrame = buildSeriesFrameWithPointCount(3, (key, index) => (key === 'Spot' ? index : null));
    timeSeriesAllFrame.fields[0].values = [1_777_660_803_000, 1_777_660_801_000, 1_777_660_802_000];

    useDashboardStore.setState({
      data: buildFactoryData(11),
      timeSeriesAllFrame,
      thresholds: buildThresholdStateFromConfig(),
      lastDataAt: 1,
      intervalSec: 0.2,
    });

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const latestUPlotProps = getLatestUPlotProps();

    expect(latestUPlotProps.data[0]).toEqual([1_777_660_801, 1_777_660_802, 1_777_660_803]);
    expect(latestUPlotProps.data[getSeriesOptionIndexByKey(latestUPlotProps, 'Spot')]).toEqual([1, 2, 0]);
  });

  it('sets the x scale range from the selected time window without remounting', async () => {
    const timeSeriesAllFrame = buildSeriesFrameWithPointCount(20, (key, index) => (key === 'Spot' ? index : null));
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
    const initialUPlotProps = getLatestUPlotProps();
    const initialUPlotInstance = getLatestUPlotInstance();
    const latestTimestampSec = 1_777_660_819;

    expect(initialUPlotProps.resetScalesKey).toBe(30);
    expect(getXScaleRange(initialUPlotProps)({} as uPlot, 0, 1, 'x')).toEqual([
      latestTimestampSec - 30 * 60,
      latestTimestampSec,
    ]);

    fireEvent.click(screen.getByRole('button', { name: '5m' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '5m' })).toHaveAttribute('aria-pressed', 'true');
    });
    const fiveMinuteUPlotProps = getLatestUPlotProps();

    expect(mockUPlotChartCreate).toHaveBeenCalledTimes(initialCreateCount);
    expect(fiveMinuteUPlotProps.resetScalesKey).toBe(5);
    expect(getXScaleRangeFromOptions(initialUPlotInstance.options)({} as uPlot, 0, 1, 'x')).toEqual([
      latestTimestampSec - 5 * 60,
      latestTimestampSec,
    ]);
    expect(getXScaleRange(fiveMinuteUPlotProps)({} as uPlot, 0, 1, 'x')).toEqual([
      latestTimestampSec - 5 * 60,
      latestTimestampSec,
    ]);
  });

  it('preserves uPlot instance and zoom state when toggling thresholds', async () => {
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
    const latestUPlotProps = getLatestUPlotProps();
    const initialZoomState = { ...initialUPlotInstance.scales.x };

    expect(latestUPlotProps.options.cursor?.points).toBeUndefined();
    expect(getSeriesOptionByKey(latestUPlotProps, 'Spot')).toBeDefined();

    fireEvent.click(getLegendButtonByValue('11.0'));

    await waitFor(() => {
      expect(mockUPlotChartCreate).toHaveBeenCalledTimes(initialCreateCount + 1);
    });
    const hiddenSpotProps = getLatestUPlotProps();
    const hiddenSpotInstance = getLatestUPlotInstance();
    expect(() => getSeriesOptionByKey(hiddenSpotProps, 'Spot')).toThrow();
    expect(hiddenSpotProps.data).toHaveLength(latestUPlotProps.data.length - 1);
    hiddenSpotInstance.redraw.mockClear();
    expect(hiddenSpotInstance.redraw).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('checkbox'));

    await waitFor(() => {
      expect(hiddenSpotInstance.redraw).toHaveBeenCalledTimes(1);
    });
    expect(hiddenSpotInstance.redraw).toHaveBeenCalledWith(false, false);

    const latestUPlotInstance = getLatestUPlotInstance();
    expect(mockUPlotChartCreate).toHaveBeenCalledTimes(initialCreateCount + 1);
    expect(latestUPlotInstance).toBe(hiddenSpotInstance);
    expect(latestUPlotInstance.scales.x).toEqual(initialZoomState);
  });

  it('highlights a focused legend series without remounting the chart', async () => {
    seedTimeSeriesData(11);

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const initialCreateCount = mockUPlotChartCreate.mock.calls.length;
    const initialUPlotInstance = getLatestUPlotInstance();
    const spotSeriesIndex = getCatalogSeriesIndex('Spot');
    const pressSeriesIndex = getCatalogSeriesIndex('Press');

    initialUPlotInstance.setSeries.mockClear();
    initialUPlotInstance.redraw.mockClear();

    fireEvent.mouseEnter(getButtonByText(getCatalogSeriesLabel('Press')));

    await waitFor(() => {
      expect(initialUPlotInstance.redraw).toHaveBeenCalledWith(false, false);
    });

    expect(mockUPlotChartCreate).toHaveBeenCalledTimes(initialCreateCount);
    expect(initialUPlotInstance.series[pressSeriesIndex].width).toBe(4);
    expect(initialUPlotInstance.series[pressSeriesIndex].alpha).toBe(1);
    expect(initialUPlotInstance.series[spotSeriesIndex].width).toBe(2);
    expect(initialUPlotInstance.series[spotSeriesIndex].alpha).toBe(0.26);
    expect(initialUPlotInstance.setSeries).toHaveBeenCalledWith(pressSeriesIndex, { focus: true });
    expect(screen.getByRole('button', { name: '강조 해제' })).toBeInTheDocument();

    initialUPlotInstance.redraw.mockClear();
    fireEvent.click(screen.getByRole('button', { name: '강조 해제' }));

    await waitFor(() => {
      expect(initialUPlotInstance.setSeries).toHaveBeenCalledWith(null, { focus: true });
    });

    expect(initialUPlotInstance.series[pressSeriesIndex].width).toBe(2);
    expect(initialUPlotInstance.series[pressSeriesIndex].alpha).toBe(1);
    expect(initialUPlotInstance.series[spotSeriesIndex].alpha).toBe(1);
    expect(initialUPlotInstance.redraw).toHaveBeenCalledWith(false, false);
    expect(mockUPlotChartCreate).toHaveBeenCalledTimes(initialCreateCount);
  });

  it('moves only extrusion speed to the right y axis when enabled', async () => {
    seedTimeSeriesData(11);

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const initialCreateCount = mockUPlotChartCreate.mock.calls.length;
    const initialUPlotProps = getLatestUPlotProps();

    expect(initialUPlotProps.options.scales?.[SPEED_RIGHT_SCALE_KEY]).toBeUndefined();
    expect(getSeriesOptionByKey(initialUPlotProps, 'Speed').scale).toBe('y');
    expect(() => getAxisOptionByScale(initialUPlotProps, SPEED_RIGHT_SCALE_KEY)).toThrow();

    fireEvent.click(screen.getByRole('button', { name: '압출 속도 오른쪽 Y축' }));

    await waitFor(() => {
      expect(mockUPlotChartCreate).toHaveBeenCalledTimes(initialCreateCount + 1);
    });

    const rightAxisUPlotProps = getLatestUPlotProps();
    const speedAxis = getAxisOptionByScale(rightAxisUPlotProps, SPEED_RIGHT_SCALE_KEY);

    expect(rightAxisUPlotProps.configKey).toContain(SPEED_RIGHT_SCALE_KEY);
    expect(rightAxisUPlotProps.options.scales?.[SPEED_RIGHT_SCALE_KEY]).toEqual({ auto: true });
    expect(getSeriesOptionByKey(rightAxisUPlotProps, 'Speed').scale).toBe(SPEED_RIGHT_SCALE_KEY);
    expect(getSeriesOptionByKey(rightAxisUPlotProps, 'Spot').scale).toBe('y');
    expect(getSeriesOptionByKey(rightAxisUPlotProps, 'Press').scale).toBe('y');
    expect(speedAxis.side).toBe(1);
    expect(speedAxis.stroke).toBe('#10b981');

    fireEvent.click(screen.getByRole('button', { name: '압출 속도 오른쪽 Y축' }));

    await waitFor(() => {
      expect(mockUPlotChartCreate).toHaveBeenCalledTimes(initialCreateCount + 2);
    });

    const restoredUPlotProps = getLatestUPlotProps();
    expect(restoredUPlotProps.options.scales?.[SPEED_RIGHT_SCALE_KEY]).toBeUndefined();
    expect(getSeriesOptionByKey(restoredUPlotProps, 'Speed').scale).toBe('y');
    expect(() => getAxisOptionByScale(restoredUPlotProps, SPEED_RIGHT_SCALE_KEY)).toThrow();
  });

  it('draws speed threshold on the right y axis when speed axis is enabled', async () => {
    seedTimeSeriesDataWithThresholds(11, buildSpeedAndSpotThresholdState(3, 10));

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    fireEvent.click(screen.getByRole('button', { name: '압출 속도 오른쪽 Y축' }));

    await waitFor(() => {
      expect(getLatestUPlotProps().options.scales?.[SPEED_RIGHT_SCALE_KEY]).toEqual({ auto: true });
    });

    const drawHook = getDrawHook(getLatestUPlotProps());
    const { plot, valToPos } = buildThresholdDrawPlot();

    drawHook(plot);

    expect(valToPos).toHaveBeenCalledWith(3, SPEED_RIGHT_SCALE_KEY, true);
    expect(valToPos).toHaveBeenCalledWith(10, 'y', true);
  });

  it('redraws threshold overlay from latest threshold toggle state without remounting', async () => {
    seedTimeSeriesDataWithThresholds(11, buildSpotThresholdState(10, true));

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const initialCreateCount = mockUPlotChartCreate.mock.calls.length;
    const initialUPlotInstance = getLatestUPlotInstance();
    const drawHook = getDrawHook(getLatestUPlotProps());
    const { plot, context } = buildThresholdDrawPlot();

    drawHook(plot);

    expect(context.stroke).toHaveBeenCalledTimes(1);
    context.stroke.mockClear();
    initialUPlotInstance.redraw.mockClear();
    expect(initialUPlotInstance.redraw).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('checkbox'));

    await waitFor(() => {
      expect(initialUPlotInstance.redraw).toHaveBeenCalledTimes(1);
    });
    expect(initialUPlotInstance.redraw).toHaveBeenCalledWith(false, false);

    drawHook(plot);

    expect(mockUPlotChartCreate).toHaveBeenCalledTimes(initialCreateCount);
    expect(getLatestUPlotInstance()).toBe(initialUPlotInstance);
    expect(context.stroke).not.toHaveBeenCalled();
  });

  it('redraws threshold overlay from latest threshold value without remounting', async () => {
    seedTimeSeriesDataWithThresholds(11, buildSpotThresholdState(10, true));

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const initialCreateCount = mockUPlotChartCreate.mock.calls.length;
    const initialUPlotInstance = getLatestUPlotInstance();
    const drawHook = getDrawHook(getLatestUPlotProps());
    const { plot, context, valToPos } = buildThresholdDrawPlot();

    drawHook(plot);

    expect(valToPos).toHaveBeenCalledWith(10, 'y', true);
    valToPos.mockClear();
    context.stroke.mockClear();
    initialUPlotInstance.redraw.mockClear();

    act(() => {
      useDashboardStore.setState({
        thresholds: buildSpotThresholdState(20, true),
      });
    });

    await waitFor(() => {
      expect(initialUPlotInstance.redraw).toHaveBeenCalledTimes(1);
    });
    expect(initialUPlotInstance.redraw).toHaveBeenCalledWith(false, false);

    drawHook(plot);

    expect(mockUPlotChartCreate).toHaveBeenCalledTimes(initialCreateCount);
    expect(getLatestUPlotInstance()).toBe(initialUPlotInstance);
    expect(valToPos).toHaveBeenCalledWith(20, 'y', true);
    expect(context.stroke).toHaveBeenCalledTimes(1);
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
    const moldValue = 321;
    useDashboardStore.setState({
      data: buildFactoryData(11),
      timeSeriesAllFrame: buildSeriesFrameWithPointCount(1, (key) => (key === 'Mold1' ? moldValue : null)),
      thresholds: buildThresholdStateFromConfig(),
      lastDataAt: 1,
      intervalSec: 0.2,
    });

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const initialCreateCount = mockUPlotChartCreate.mock.calls.length;
    const initialUPlotProps = getLatestUPlotProps();
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
      expect(mockUPlotChartCreate).toHaveBeenCalledTimes(initialCreateCount + 1);
    });
    const moldEnabledProps = getLatestUPlotProps();
    const moldSeriesIndex = getSeriesOptionIndexByKey(moldEnabledProps, 'Mold1');

    expect(getSeriesOptionByKey(moldEnabledProps, 'Mold1')).toBeDefined();
    expect(moldEnabledProps.data).toHaveLength(initialUPlotProps.data.length + 1);
    expect(moldEnabledProps.data[moldSeriesIndex]).toContain(moldValue);
    expect(mold1Button).toHaveAttribute('aria-pressed', 'true');
  });

  it('shows an empty chart state when all series are hidden', async () => {
    seedTimeSeriesData(11);

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');

    TIME_SERIES_CATALOG.filter((meta) => !MOLD_SERIES_KEYS.includes(meta.key)).forEach((meta) => {
      fireEvent.click(getButtonByText(meta.label));
    });

    expect(await screen.findByText('표시할 시리즈를 선택하세요.')).toBeInTheDocument();
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
    const firstTooltipItem = tooltips[0].querySelector<HTMLElement>('.uplot-tooltip-item');
    const firstTooltipDot = tooltips[0].querySelector<HTMLElement>('.uplot-tooltip-dot');
    const firstTooltipValue = tooltips[0].querySelector<HTMLElement>('.uplot-tooltip-value');

    expect(firstTooltipItem).not.toBeNull();
    expect(firstTooltipDot).not.toBeNull();
    expect(firstTooltipValue).not.toBeNull();
    expect(firstTooltipItem?.style.getPropertyValue('--uplot-series-color')).toBe('#ef4444');
    expect(firstTooltipDot?.getAttribute('style')).toContain('background-color: #ef4444');
    expect(tooltips[1].style.display).not.toBe('block');
    expect(tooltips[1]).not.toHaveTextContent('11.0');

    firstSetCursorHook(buildHiddenTooltipPlot(100, 80));
    secondSetCursorHook(buildTooltipPlot(120, 90, 22));

    expect(tooltips[0].style.display).toBe('none');
    expect(tooltips[0]).not.toHaveTextContent('22.0');
    expect(tooltips[1].style.display).toBe('block');
    expect(tooltips[1]).toHaveTextContent('22.0');
  });

  it('moves highlighted series to the top of the tooltip', async () => {
    seedTimeSeriesData(11);

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    fireEvent.focus(getButtonByText(getCatalogSeriesLabel('Press')));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '강조 해제' })).toBeInTheDocument();
    });

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
      throw new Error('Chart wrapper was not found');
    }

    Object.defineProperty(chartWrapper, 'getBoundingClientRect', {
      configurable: true,
      value: () => ({ left: 10, top: 20, width: 500, height: 260 }),
    });

    setCursorHook(buildMultiSeriesTooltipPlot(100, 80));

    const tooltipItems = Array.from(tooltip.querySelectorAll<HTMLElement>('.uplot-tooltip-item'));
    expect(tooltipItems).toHaveLength(2);
    expect(tooltipItems[0]).toHaveTextContent(getCatalogSeriesLabel('Press'));
    expect(tooltipItems[0]).toHaveTextContent('22.0');
    expect(tooltipItems[0]).toHaveClass('is-highlighted');
    expect(tooltipItems[1]).toHaveTextContent(getCatalogSeriesLabel('Spot'));
  });

  it('uses dense tooltip layout when many active series are visible', async () => {
    seedTimeSeriesData(11);

    renderTimeSeriesWidget();

    await screen.findByTestId('uplot-chart');
    const latestUPlotProps = getLatestUPlotProps();
    const tooltip = document.querySelector<HTMLDivElement>('.uplot-tooltip');
    const setCursorHook = getSetCursorHook(latestUPlotProps);

    if (tooltip === null) {
      throw new Error('Tooltip element was not found');
    }

    Object.defineProperty(tooltip, 'offsetWidth', { configurable: true, value: 360 });
    Object.defineProperty(tooltip, 'offsetHeight', { configurable: true, value: 260 });
    const chartWrapper = tooltip.parentElement;

    if (chartWrapper === null) {
      throw new Error('Chart wrapper was not found');
    }

    Object.defineProperty(chartWrapper, 'getBoundingClientRect', {
      configurable: true,
      value: () => ({ left: 10, top: 20, width: 500, height: 420 }),
    });

    setCursorHook(buildDenseTooltipPlot(100, 80));

    const tooltipItemsContainer = tooltip.querySelector<HTMLElement>('.uplot-tooltip-items');
    const tooltipItems = Array.from(tooltip.querySelectorAll<HTMLElement>('.uplot-tooltip-item'));

    expect(tooltip.style.display).toBe('block');
    expect(tooltipItemsContainer).not.toBeNull();
    expect(tooltipItemsContainer).toHaveClass('is-dense');
    expect(tooltipItems).toHaveLength(TIME_SERIES_CATALOG.length - MOLD_SERIES_KEYS.length);
    expect(tooltip).toHaveTextContent(getCatalogSeriesLabel('Billet_Temp'));
    expect(tooltip).toHaveTextContent(getCatalogSeriesLabel('At_Temp'));
    expect(tooltip).toHaveTextContent(getCatalogSeriesLabel('At_Pre'));
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
