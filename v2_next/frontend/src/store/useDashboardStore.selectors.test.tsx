import React from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { useShallow } from 'zustand/react/shallow';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { FactoryData } from '../shared/types';
import { buildThresholdStateFromConfig } from '../shared/utils/thresholds';
import {
  selectDashboardEnvSlice,
  selectDashboardKpiSlice,
  selectDashboardMoldsSlice,
  selectDashboardSpotSlice,
  selectDashboardTempsSlice,
  useDashboardStore,
} from './useDashboardStore';
import { MissingDataNote } from '../domains/FacilityData/components/widgets/MissingDataNote';
import { KpiComponent } from '../domains/FacilityData/components/widgets/KpiWidget';

const buildFactoryData = (overrides: Partial<FactoryData>): FactoryData => ({
  Time: '2026-05-19T00:00:00.000Z',
  Status: 'Running',
  Speed: 3,
  Press: 120,
  Count: 10,
  EndPos: 1015,
  Billet_Length: 0,
  Spot: 520,
  Temp_F: 430,
  Temp_B: 431,
  Billet_Temp: 300,
  Mold1: 478,
  Mold2: 480,
  Mold3: 479,
  Mold4: 478,
  Mold5: 478,
  Mold6: 478,
  At_Temp: 32,
  At_Pre: 35,
  Computed: {
    speed_level: 'normal',
    press_level: 'normal',
    jam_level: 'none',
    thresholds: {
      speed: false,
      press: false,
      spot: false,
      temp_f: false,
      temp_b: false,
      billet: false,
      billet_temp: false,
      at_temp: false,
      at_pre: false,
      count: false,
      endpos: false,
    },
  },
  ...overrides,
});

const resetDashboardStore = (): void => {
  useDashboardStore.setState({
    data: null,
    timeSeriesAllFrame: null,
    thresholds: buildThresholdStateFromConfig(),
    lastDataAt: null,
    intervalSec: 0.2,
    connected: false,
    latencyMs: null,
    pollingDegraded: false,
    pollingIntervalMs: 500,
    pollingFailureCount: 0,
    dashboardLeaderState: null,
    pollingPausedByVisibility: false,
    seriesStats: { count: 0, windowMs: 0, maxPoints: null },
    spotConfig: null,
    spotImageUrl: '',
    spotImageLoading: false,
    spotImageError: null,
    spotLastSuccessAt: null,
    spotImageMetadata: null,
    spotAlertActive: false,
  });
};

const KpiSliceProbe = React.memo(function KpiSliceProbe() {
  const kpiSlice = useDashboardStore(useShallow(selectDashboardKpiSlice));

  return <span data-testid="speed-value">{kpiSlice.speed}</span>;
});

const EnvSliceProbe = React.memo(function EnvSliceProbe() {
  const envSlice = useDashboardStore(useShallow(selectDashboardEnvSlice));

  return <span data-testid="env-value">{envSlice.tempRaw}</span>;
});

const SpotSliceProbe = React.memo(function SpotSliceProbe() {
  const spotSlice = useDashboardStore(useShallow(selectDashboardSpotSlice));

  return <span data-testid="spot-value">{spotSlice.spotRaw}</span>;
});

const TempsSliceProbe = React.memo(function TempsSliceProbe() {
  const tempsSlice = useDashboardStore(useShallow(selectDashboardTempsSlice));

  return <span data-testid="temps-value">{tempsSlice.tempF}</span>;
});

const MoldsSliceProbe = React.memo(function MoldsSliceProbe() {
  const moldsSlice = useDashboardStore(useShallow(selectDashboardMoldsSlice));

  return <span data-testid="molds-value">{moldsSlice.moldValue1}</span>;
});

describe('useDashboardStore selectors', () => {
  afterEach(() => {
    cleanup();
    resetDashboardStore();
  });

  it('does not rerender the KPI slice subscriber when only unrelated data fields change', () => {
    resetDashboardStore();
    useDashboardStore.getState().setData(buildFactoryData({ At_Temp: 32 }), 1_000);
    const onRender = vi.fn();

    render(
      <React.Profiler id="kpi-slice-probe" onRender={onRender}>
        <KpiSliceProbe />
      </React.Profiler>
    );

    expect(screen.getByTestId('speed-value').textContent).toBe('3');
    const renderCount = onRender.mock.calls.length;

    act(() => {
      useDashboardStore.getState().setData(buildFactoryData({ At_Temp: 33 }), 1_500);
    });

    expect(screen.getByTestId('speed-value').textContent).toBe('3');
    expect(onRender).toHaveBeenCalledTimes(renderCount);
  });

  it('rerenders the KPI slice subscriber when a KPI field changes', () => {
    resetDashboardStore();
    useDashboardStore.getState().setData(buildFactoryData({ Speed: 3 }), 1_000);
    const onRender = vi.fn();

    render(
      <React.Profiler id="kpi-slice-probe" onRender={onRender}>
        <KpiSliceProbe />
      </React.Profiler>
    );

    const renderCount = onRender.mock.calls.length;

    act(() => {
      useDashboardStore.getState().setData(buildFactoryData({ Speed: 4 }), 1_500);
    });

    expect(screen.getByTestId('speed-value').textContent).toBe('4');
    expect(onRender.mock.calls.length).toBeGreaterThan(renderCount);
  });

  it('does not rerender the real KPI widget when only unrelated data fields change', () => {
    resetDashboardStore();
    useDashboardStore.getState().setData(buildFactoryData({ At_Temp: 32 }), 1_000);
    const onRender = vi.fn();

    render(
      <React.Profiler id="kpi-widget" onRender={onRender}>
        <KpiComponent />
      </React.Profiler>
    );

    const renderCount = onRender.mock.calls.length;

    act(() => {
      useDashboardStore.getState().setData(buildFactoryData({ At_Temp: 33 }), 1_500);
    });

    expect(onRender).toHaveBeenCalledTimes(renderCount);
  });

  it('rerenders the real KPI widget when a KPI field changes', () => {
    resetDashboardStore();
    useDashboardStore.getState().setData(buildFactoryData({ Speed: 3 }), 1_000);
    const onRender = vi.fn();

    render(
      <React.Profiler id="kpi-widget" onRender={onRender}>
        <KpiComponent />
      </React.Profiler>
    );

    const renderCount = onRender.mock.calls.length;

    act(() => {
      useDashboardStore.getState().setData(buildFactoryData({ Speed: 4 }), 1_500);
    });

    expect(onRender.mock.calls.length).toBeGreaterThan(renderCount);
  });

  it('keeps non-KPI widget slices isolated from unrelated KPI data changes', () => {
    resetDashboardStore();
    useDashboardStore.getState().setData(buildFactoryData({ Speed: 3 }), 1_000);
    const onEnvRender = vi.fn();
    const onSpotRender = vi.fn();
    const onTempsRender = vi.fn();
    const onMoldsRender = vi.fn();

    render(
      <>
        <React.Profiler id="env-slice-probe" onRender={onEnvRender}>
          <EnvSliceProbe />
        </React.Profiler>
        <React.Profiler id="spot-slice-probe" onRender={onSpotRender}>
          <SpotSliceProbe />
        </React.Profiler>
        <React.Profiler id="temps-slice-probe" onRender={onTempsRender}>
          <TempsSliceProbe />
        </React.Profiler>
        <React.Profiler id="molds-slice-probe" onRender={onMoldsRender}>
          <MoldsSliceProbe />
        </React.Profiler>
      </>
    );

    const envRenderCount = onEnvRender.mock.calls.length;
    const spotRenderCount = onSpotRender.mock.calls.length;
    const tempsRenderCount = onTempsRender.mock.calls.length;
    const moldsRenderCount = onMoldsRender.mock.calls.length;

    act(() => {
      useDashboardStore.getState().setData(buildFactoryData({ Speed: 4 }), 1_500);
    });

    expect(onEnvRender).toHaveBeenCalledTimes(envRenderCount);
    expect(onSpotRender).toHaveBeenCalledTimes(spotRenderCount);
    expect(onTempsRender).toHaveBeenCalledTimes(tempsRenderCount);
    expect(onMoldsRender).toHaveBeenCalledTimes(moldsRenderCount);
  });

  it('rerenders each non-KPI widget slice when its own field changes', () => {
    resetDashboardStore();
    useDashboardStore.getState().setData(buildFactoryData({}), 1_000);
    const onEnvRender = vi.fn();
    const onSpotRender = vi.fn();
    const onTempsRender = vi.fn();
    const onMoldsRender = vi.fn();

    render(
      <>
        <React.Profiler id="env-slice-probe" onRender={onEnvRender}>
          <EnvSliceProbe />
        </React.Profiler>
        <React.Profiler id="spot-slice-probe" onRender={onSpotRender}>
          <SpotSliceProbe />
        </React.Profiler>
        <React.Profiler id="temps-slice-probe" onRender={onTempsRender}>
          <TempsSliceProbe />
        </React.Profiler>
        <React.Profiler id="molds-slice-probe" onRender={onMoldsRender}>
          <MoldsSliceProbe />
        </React.Profiler>
      </>
    );

    const envRenderCount = onEnvRender.mock.calls.length;
    const spotRenderCount = onSpotRender.mock.calls.length;
    const tempsRenderCount = onTempsRender.mock.calls.length;
    const moldsRenderCount = onMoldsRender.mock.calls.length;

    act(() => {
      useDashboardStore.getState().setData(
        buildFactoryData({
          At_Temp: 33,
          Spot: 521,
          Temp_F: 431,
          Mold1: 479,
        }),
        1_500
      );
    });

    expect(onEnvRender.mock.calls.length).toBeGreaterThan(envRenderCount);
    expect(onSpotRender.mock.calls.length).toBeGreaterThan(spotRenderCount);
    expect(onTempsRender.mock.calls.length).toBeGreaterThan(tempsRenderCount);
    expect(onMoldsRender.mock.calls.length).toBeGreaterThan(moldsRenderCount);
  });

  it('updates the missing data note only when the displayed second changes', () => {
    resetDashboardStore();
    useDashboardStore.setState({ lastDataAt: 1_000 });
    const onRender = vi.fn();

    render(
      <React.Profiler id="missing-data-note" onRender={onRender}>
        <MissingDataNote />
      </React.Profiler>
    );

    const renderCount = onRender.mock.calls.length;

    act(() => {
      useDashboardStore.setState({ lastDataAt: 1_500 });
    });

    expect(onRender).toHaveBeenCalledTimes(renderCount);

    act(() => {
      useDashboardStore.setState({ lastDataAt: 2_000 });
    });

    expect(onRender.mock.calls.length).toBeGreaterThan(renderCount);
  });
});
