import React, { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import type { MutableRefObject, ReactNode } from 'react';
import { CameraComponent } from '../domains/FacilityData/components/widgets/CameraWidget';
import { KpiComponent } from '../domains/FacilityData/components/widgets/KpiWidget';
import { SpotComponent } from '../domains/FacilityData/components/widgets/SpotWidget';
import { CURRENT_LAYOUT_COLS } from '../shared/constants/logic';
import type { LayoutMap } from '../shared/types';
import {
  type DashboardItem,
  resolveDashboardItems,
} from './DashboardSceneModel';

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
};

type NativeWidgetProps = {
  item: DashboardItem;
  children: ReactNode;
};

type DeferredWidgetContentProps = {
  item: DashboardItem;
  renderContent: () => ReactNode;
};

const WIDGET_FALLBACK_TEXT = 'Loading...';
const DEFERRED_WIDGET_TYPES = new Set<DashboardItem['type']>(['timeseries']);

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
      className="native-grid-item"
      style={{
        gridColumn: `${item.x + 1} / span ${item.width}`,
        gridRow: `${item.y + 1} / span ${item.height}`,
        minHeight: 0,
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

const DeferredWidgetContent = ({ item, renderContent }: DeferredWidgetContentProps): JSX.Element => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [shouldRender, setShouldRender] = useState(!DEFERRED_WIDGET_TYPES.has(item.type));

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
      {shouldRender ? renderContent() : <div className="native-widget-placeholder" aria-label={`${item.title} 대기`} />}
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
    return <KpiComponent />;
  }

  if (item.type === 'spot') {
    return <SpotComponent />;
  }

  if (item.type === 'temps') {
    return <TempsComponent />;
  }

  if (item.type === 'camera') {
    return (
      <CameraComponent
        onSpotImageLoaded={onSpotImageLoaded}
        onSpotImageError={onSpotImageError}
        requestFocus={requestFocus}
        focusBusy={focusBusy}
      />
    );
  }

  if (item.type === 'molds') {
    return <MoldsComponent />;
  }

  if (item.type === 'env') {
    return <EnvComponent />;
  }

  if (item.type === 'timeseries') {
    return <TimeSeriesWidget />;
  }

  return <NativeMarkdown item={item} />;
};

export const NativeDashboardSurface = ({
  layoutSnapshotLayout,
  layoutRef,
  onSpotImageLoaded,
  onSpotImageError,
  requestFocus,
  focusBusy,
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
        gridAutoRows: 'var(--grid-row-height)',
        gap: '4px',
        padding: '4px',
        alignItems: 'stretch',
      }}
    >
      {items.map(item => (
        <NativeWidget key={item.key} item={item}>
          <DeferredWidgetContent
            item={item}
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
