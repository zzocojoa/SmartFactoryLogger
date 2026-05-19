import React, { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import type { MutableRefObject, ReactNode } from 'react';
import { CameraComponent } from '../domains/FacilityData/components/widgets/CameraWidget';
import { KpiComponent } from '../domains/FacilityData/components/widgets/KpiWidget';
import { SpotComponent } from '../domains/FacilityData/components/widgets/SpotWidget';
import { CURRENT_LAYOUT_COLS, DEFAULT_ROW_HEIGHT } from '../shared/constants/logic';
import type { LayoutMap } from '../shared/types';
import {
  type DashboardItem,
  resolveDashboardItems,
} from './DashboardSceneModel';
import { ProfilerProbe } from '../shared/profiling/reactRenderProfiler';

const TempsComponent = React.lazy(() => import('../domains/FacilityData/components/widgets/TempsWidget').then(m => ({ default: m.TempsComponent })));
const MoldsComponent = React.lazy(() => import('../domains/FacilityData/components/widgets/MoldsWidget').then(m => ({ default: m.MoldsComponent })));
const EnvComponent = React.lazy(() => import('../domains/FacilityData/components/widgets/EnvWidget').then(m => ({ default: m.EnvComponent })));
const TimeSeriesWidget = React.lazy(() => import('../domains/FacilityData/components/widgets/TimeSeriesWidget').then(m => ({ default: m.TimeSeriesWidget })));
const ReactMarkdown = React.lazy(() => import('react-markdown').then(m => ({ default: m.default })));

type NativeDashboardSurfaceProps = {
  layoutSnapshotLayout: LayoutMap | null;
  layoutRef: MutableRefObject<LayoutMap>;
  onSpotImageLoaded: () => void;
  onSpotImageError: () => void;
  requestFocus: (steps: number) => void;
  focusBusy: boolean;
  onTimeSeriesVisible: () => void;
};

type NativeWidgetProps = {
  item: DashboardItem;
  children: ReactNode;
};

type DeferredWidgetContentProps = {
  item: DashboardItem;
  renderContent: () => ReactNode;
  onTimeSeriesVisible: () => void;
};

const WIDGET_FALLBACK_TEXT = 'Loading...';
const DEFERRED_WIDGET_TYPES = new Set<DashboardItem['type']>(['timeseries']);
const GRID_GAP_PX = 4;
const WIDGET_PLACEHOLDER_CLASS_NAME = 'native-widget-placeholder';
const TIMESERIES_PLACEHOLDER_CLASS_NAME = `${WIDGET_PLACEHOLDER_CLASS_NAME} timeseries-card`;

const resolveNativeGridItemClassName = (itemType: DashboardItem['type']): string => {
  if (itemType === 'timeseries') {
    return 'native-grid-item native-grid-item-timeseries';
  }

  return 'native-grid-item';
};

const buildLayoutMapFromItems = (items: DashboardItem[]): LayoutMap => {
  return items.reduce<LayoutMap>((acc, item) => {
    acc[item.key] = {
      x: item.x,
      y: item.y,
      width: item.width,
      height: item.height,
      type: item.type,
      title: item.title,
      properties: item.properties,
    };
    return acc;
  }, {});
};

const NativeWidget = ({ item, children }: NativeWidgetProps): JSX.Element => {
  return (
    <div
      className={resolveNativeGridItemClassName(item.type)}
      style={{
        gridColumn: `${item.x + 1} / span ${item.width}`,
        gridRow: `${item.y + 1} / span ${item.height}`,
        minHeight: item.type === 'timeseries' ? undefined : 0,
      }}
    >
      <div className="scene-react-widget" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div className="panel-header grid-drag-handle-dashboard-grid">
          <span className="panel-title-text">{item.title}</span>
        </div>
        <div className="panel-content" style={{ flex: 1, position: 'relative', overflow: 'visible' }}>
          {children}
        </div>
      </div>
    </div>
  );
};

const resolvePlaceholderClassName = (item: DashboardItem): string => {
  if (item.type === 'timeseries') {
    return TIMESERIES_PLACEHOLDER_CLASS_NAME;
  }

  return WIDGET_PLACEHOLDER_CLASS_NAME;
};

const DeferredWidgetContent = ({ item, renderContent, onTimeSeriesVisible }: DeferredWidgetContentProps): JSX.Element => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [shouldRender, setShouldRender] = useState(!DEFERRED_WIDGET_TYPES.has(item.type));

  useEffect(() => {
    if (shouldRender && item.type === 'timeseries') {
      onTimeSeriesVisible();
    }
  }, [item.type, onTimeSeriesVisible, shouldRender]);

  useEffect(() => {
    if (shouldRender) {
      return;
    }

    const container = containerRef.current;
    if (!container) {
      return;
    }

    if (typeof IntersectionObserver === 'undefined') {
      setShouldRender(true);
      return;
    }

    let observer: IntersectionObserver | null = null;
    const startObserver = (): void => {
      if (observer) {
        return;
      }
      observer = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShouldRender(true);
          observer?.disconnect();
        }
      });
      observer.observe(container);
    };

    startObserver();
    window.addEventListener('scroll', startObserver, { passive: true, once: true });
    window.addEventListener('wheel', startObserver, { passive: true, once: true });
    window.addEventListener('touchmove', startObserver, { passive: true, once: true });

    return () => {
      window.removeEventListener('scroll', startObserver);
      window.removeEventListener('wheel', startObserver);
      window.removeEventListener('touchmove', startObserver);
      observer?.disconnect();
    };
  }, [shouldRender]);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
      {shouldRender ? renderContent() : <div className={resolvePlaceholderClassName(item)} aria-label={`${item.title} 대기`} />}
    </div>
  );
};

const NativeMarkdown = ({ item }: { item: DashboardItem }): JSX.Element => {
  const content = typeof item.properties?.content === 'string' ? item.properties.content : '';

  return (
    <div className="scene-react-widget card" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="notice-content markdown-body" style={{ flex: 1, overflow: 'auto' }}>
        <Suspense fallback={<div className="widget-loading">{WIDGET_FALLBACK_TEXT}</div>}>
          <ReactMarkdown>{content}</ReactMarkdown>
        </Suspense>
      </div>
    </div>
  );
};

const renderWidget = (
  item: DashboardItem,
  onSpotImageLoaded: () => void,
  onSpotImageError: () => void,
  requestFocus: (steps: number) => void,
  focusBusy: boolean
): JSX.Element => {
  if (item.type === 'kpi') {
    return <ProfilerProbe id="Widget:kpi"><KpiComponent /></ProfilerProbe>;
  }

  if (item.type === 'spot') {
    return <ProfilerProbe id="Widget:spot"><SpotComponent /></ProfilerProbe>;
  }

  if (item.type === 'temps') {
    return <ProfilerProbe id="Widget:temps"><TempsComponent /></ProfilerProbe>;
  }

  if (item.type === 'camera') {
    return (
      <ProfilerProbe id="Widget:camera">
        <CameraComponent
          onSpotImageLoaded={onSpotImageLoaded}
          onSpotImageError={onSpotImageError}
          requestFocus={requestFocus}
          focusBusy={focusBusy}
        />
      </ProfilerProbe>
    );
  }

  if (item.type === 'molds') {
    return <ProfilerProbe id="Widget:molds"><MoldsComponent /></ProfilerProbe>;
  }

  if (item.type === 'env') {
    return <ProfilerProbe id="Widget:env"><EnvComponent /></ProfilerProbe>;
  }

  if (item.type === 'timeseries') {
    return <ProfilerProbe id="Widget:timeseries"><TimeSeriesWidget /></ProfilerProbe>;
  }

  return <ProfilerProbe id="Widget:markdown"><NativeMarkdown item={item} /></ProfilerProbe>;
};

const NativeDashboardSurfaceComponent = ({
  layoutSnapshotLayout,
  layoutRef,
  onSpotImageLoaded,
  onSpotImageError,
  requestFocus,
  focusBusy,
  onTimeSeriesVisible,
}: NativeDashboardSurfaceProps): JSX.Element => {
  const items = useMemo(() => resolveDashboardItems(layoutSnapshotLayout), [layoutSnapshotLayout]);

  useEffect(() => {
    layoutRef.current = buildLayoutMapFromItems(items);
  }, [items, layoutRef]);

  return (
    <div
      className="native-dashboard-grid"
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${CURRENT_LAYOUT_COLS}, minmax(0, 1fr))`,
        gridAutoRows: `${DEFAULT_ROW_HEIGHT}px`,
        gap: `${GRID_GAP_PX}px`,
        padding: 0,
        alignItems: 'stretch',
      }}
    >
      {items.map(item => (
        <NativeWidget key={item.key} item={item}>
          <DeferredWidgetContent
            key={`${item.key}:${item.type}`}
            item={item}
            onTimeSeriesVisible={onTimeSeriesVisible}
            renderContent={() => (
              <Suspense fallback={<div className="widget-loading">{WIDGET_FALLBACK_TEXT}</div>}>
                {renderWidget(item, onSpotImageLoaded, onSpotImageError, requestFocus, focusBusy)}
              </Suspense>
            )}
          />
        </NativeWidget>
      ))}
    </div>
  );
};

export const NativeDashboardSurface = React.memo(NativeDashboardSurfaceComponent);
