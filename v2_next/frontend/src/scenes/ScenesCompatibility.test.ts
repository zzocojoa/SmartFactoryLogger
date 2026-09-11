import { afterAll, describe, expect, it, vi } from 'vitest';
// jsdom has no display media query API. Keep the real Grafana/Scenes modules;
// supply only the browser primitive uPlot needs at module initialization.
vi.hoisted(() => {
  vi.stubGlobal('matchMedia', (media: string) => ({
    media, matches: false, onchange: null,
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
    dispatchEvent: () => true,
  }));
  vi.stubGlobal('IntersectionObserver', class {
    observe() {} unobserve() {} disconnect() {}
  });
});
afterAll(() => vi.unstubAllGlobals());
import { GRID_CELL_HEIGHT, GRID_COLUMN_COUNT, PanelBuilders, PanelOptionsBuilders, SceneGridItem, SceneGridLayout, VizConfigBuilders } from '@grafana/scenes';
import { defaultTableOptions } from '@grafana/schema';
import { getDashboardScene } from './DashboardScene';
import { ReactWidget } from './ReactWidgetObject';
import { buildLayoutMap } from '../shared/utils/layoutUtils';

describe('pinned Scenes runtime compatibility', () => {
  it('loads the patched grid constants from the installed ESM package', () => {
    expect(GRID_COLUMN_COUNT).toBe(60);
    expect(GRID_CELL_HEIGHT).toBe(20);
  });
  it('uses the real schema table defaults in all three public builders', () => {
    expect(PanelOptionsBuilders.table().build()).toEqual(defaultTableOptions);
    expect(PanelBuilders.table().build().state.options).toEqual(defaultTableOptions);
    expect(VizConfigBuilders.table().build().options).toEqual(defaultTableOptions);
    const changed = PanelOptionsBuilders.table().setOption('showHeader', false).build();
    expect(changed.showHeader).toBe(false);
    expect(defaultTableOptions.showHeader).toBe(true);
  });

  it('preserves grid edits and widget metadata across the existing layout round trip', () => {
    const scene = getDashboardScene({ markdown: () => null });
    const grid = scene.state.body as SceneGridLayout;
    expect(grid.state.isDraggable).toBe(false);
    expect(grid.state.isResizable).toBe(false);
    expect(grid.state.children).toHaveLength(8);
    grid.setState({ isDraggable: true, isResizable: true });
    const item = grid.state.children.find((entry) => entry.state.key === 'operatorMetadata') as SceneGridItem;
    // Non-overlapping geometry: collision resolution is a separate existing model policy.
    item.setState({ x: 40, y: 12, width: 19, height: 16 });
    const body = item.state.body;
    if (!(body instanceof ReactWidget)) throw new Error('Expected the real metadata widget');
    body.setState({ title: '작업 정보 검증' });
    const saved = buildLayoutMap(grid.state.children);
    expect(saved.operatorMetadata).toMatchObject({ x: 40, y: 12, width: 19, height: 16, title: '작업 정보 검증', type: 'operatorMetadata' });
    const restored = getDashboardScene({ markdown: () => null }, JSON.parse(JSON.stringify(saved)));
    expect(buildLayoutMap((restored.state.body as SceneGridLayout).state.children)).toEqual(saved);
    expect((restored.state.body as SceneGridLayout).state.isDraggable).toBe(false);
  });
});
