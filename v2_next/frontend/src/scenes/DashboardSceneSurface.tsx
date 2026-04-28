import React, { Suspense, useEffect, useMemo } from 'react';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import { SceneGridLayout } from '@grafana/scenes';
import { KpiComponent } from '../domains/FacilityData/components/widgets/KpiWidget';
import { SpotComponent } from '../domains/FacilityData/components/widgets/SpotWidget';
import type { LayoutMap } from '../shared/types';
import { buildLayoutMap } from '../shared/utils/layoutUtils';
import { getDashboardScene, type WidgetRegistry } from './DashboardScene';
import { initScenesRuntime } from './ScenesRuntime';

const TempsComponent = React.lazy(() => import('../domains/FacilityData/components/widgets/TempsWidget').then(m => ({ default: m.TempsComponent })));
const MoldsComponent = React.lazy(() => import('../domains/FacilityData/components/widgets/MoldsWidget').then(m => ({ default: m.MoldsComponent })));
const EnvComponent = React.lazy(() => import('../domains/FacilityData/components/widgets/EnvWidget').then(m => ({ default: m.EnvComponent })));
const CameraComponent = React.lazy(() => import('../domains/FacilityData/components/widgets/CameraWidget').then(m => ({ default: m.CameraComponent })));
const TimeSeriesWidget = React.lazy(() => import('../domains/FacilityData/components/widgets/TimeSeriesWidget').then(m => ({ default: m.TimeSeriesWidget })));
const MarkdownWidget = React.lazy(() => import('./MarkdownWidget').then(m => ({ default: m.MarkdownWidget })));

type ScenesWindow = Window & {
  __SCENES_INIT__?: boolean;
};

type DashboardSceneSurfaceProps = {
  layoutSnapshotLayout: LayoutMap | null;
  layoutEditing: boolean;
  layoutRef: React.MutableRefObject<LayoutMap>;
  onSpotImageLoaded: () => void;
  onSpotImageError: () => void;
  requestFocus: (steps: number) => void;
  focusBusy: boolean;
};

const WidgetLoadingFallback = (): JSX.Element => {
  return <div className="widget-loading">Loading...</div>;
};

const ensureScenesRuntime = (): void => {
  if (typeof window === 'undefined') {
    initScenesRuntime();
    return;
  }

  const scenesWindow: ScenesWindow = window;
  if (scenesWindow.__SCENES_INIT__) {
    return;
  }

  initScenesRuntime();
  scenesWindow.__SCENES_INIT__ = true;
};

ensureScenesRuntime();

export const DashboardSceneSurface = ({
  layoutSnapshotLayout,
  layoutEditing,
  layoutRef,
  onSpotImageLoaded,
  onSpotImageError,
  requestFocus,
  focusBusy,
}: DashboardSceneSurfaceProps): JSX.Element => {
  const scene = useMemo(() => {
    const registry: WidgetRegistry = {
      kpi: () => <KpiComponent />,
      spot: () => <SpotComponent />,
      temps: () => (
        <Suspense fallback={<WidgetLoadingFallback />}>
          <TempsComponent />
        </Suspense>
      ),
      camera: () => (
        <Suspense fallback={<WidgetLoadingFallback />}>
          <CameraComponent
            onSpotImageLoaded={onSpotImageLoaded}
            onSpotImageError={onSpotImageError}
            requestFocus={requestFocus}
            focusBusy={focusBusy}
          />
        </Suspense>
      ),
      molds: () => (
        <Suspense fallback={<WidgetLoadingFallback />}>
          <MoldsComponent />
        </Suspense>
      ),
      env: () => (
        <Suspense fallback={<WidgetLoadingFallback />}>
          <EnvComponent />
        </Suspense>
      ),
      timeseries: () => (
        <Suspense fallback={<WidgetLoadingFallback />}>
          <TimeSeriesWidget />
        </Suspense>
      ),
      markdown: (item, model) => (
        <Suspense fallback={<WidgetLoadingFallback />}>
          <MarkdownWidget item={item} model={model} />
        </Suspense>
      ),
    };
    return getDashboardScene(registry, layoutSnapshotLayout);
  }, [layoutSnapshotLayout]);

  useEffect(() => {
    const grid = scene.state.body;
    if (!(grid instanceof SceneGridLayout)) {
      return;
    }
    grid.setState({ isDraggable: layoutEditing, isResizable: layoutEditing });
  }, [scene, layoutEditing]);

  useEffect(() => {
    const grid = scene.state.body;
    if (!(grid instanceof SceneGridLayout)) {
      return;
    }

    const updateLayoutRef = (): void => {
      layoutRef.current = buildLayoutMap(grid.state.children);
    };

    updateLayoutRef();
    const sub = grid.subscribeToState(() => updateLayoutRef());
    return () => sub.unsubscribe();
  }, [scene, layoutRef]);

  const SceneRenderer = useMemo(() => {
    return <scene.Component model={scene} />;
  }, [scene]);

  return SceneRenderer;
};
