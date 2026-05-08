import React, { Suspense } from 'react';
import '@testing-library/jest-dom';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import type { FactoryData } from '../../../../shared/types';
import { buildThresholdStateFromConfig } from '../../../../shared/utils/thresholds';
import { useDashboardStore } from '../../../../store/useDashboardStore';
import type { SeriesFrame } from '../../timeseries/seriesDataFrames';
import { TimeSeriesWidget } from './TimeSeriesWidget';

const mockUPlotChartRender = jest.fn();

jest.mock('../UPlotChart', () => ({
  UPlotChart: (props: unknown) => {
    mockUPlotChartRender(props);
    return <div data-testid="uplot-chart" />;
  },
}));

jest.mock('../../../../shared/hooks/useThemeContext', () => ({
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

const buildSeriesFrame = (): SeriesFrame => ({
  fields: [
    {
      name: 'Time',
      type: 'time',
      values: [1_777_660_800_000],
    },
    {
      name: 'Spot',
      type: 'number',
      values: [11],
    },
  ],
});

const renderTimeSeriesWidget = (): void => {
  render(
    <Suspense fallback={<div>loading chart</div>}>
      <TimeSeriesWidget />
    </Suspense>
  );
};

describe('TimeSeriesWidget render', () => {
  afterEach(() => {
    cleanup();
    mockUPlotChartRender.mockClear();
    useDashboardStore.setState({
      data: null,
      timeSeriesAllFrame: null,
      thresholds: buildThresholdStateFromConfig(),
      lastDataAt: null,
      intervalSec: 0.2,
    });
  });

  it('updates legend values without rerendering chart when only store data changes', async () => {
    const timeSeriesAllFrame = buildSeriesFrame();
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
});
