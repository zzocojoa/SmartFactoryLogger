import { describe, expect, it } from 'vitest';
import { getPresetById } from '../shared/constants/layoutPresets';
import { DEFAULT_ROW_HEIGHT } from '../shared/constants/logic';
import {
  resolveDashboardItems,
  type DashboardItem,
  type SavedLayoutMap,
} from './DashboardSceneModel';

const itemsOverlap = (a: DashboardItem, b: DashboardItem): boolean => {
  const aRight = a.x + a.width;
  const bRight = b.x + b.width;
  const aBottom = a.y + a.height;
  const bBottom = b.y + b.height;
  return a.x < bRight && aRight > b.x && a.y < bBottom && aBottom > b.y;
};

const expectNoOverlappingItems = (items: DashboardItem[]): void => {
  items.forEach((item, index) => {
    items.slice(index + 1).forEach((nextItem) => {
      expect(itemsOverlap(item, nextItem), `${item.key} overlaps ${nextItem.key}`).toBe(false);
    });
  });
};

describe('resolveDashboardItems', () => {
  it('gives fresh dashboard cards enough vertical space for their readings and controls', () => {
    const items = resolveDashboardItems(null);
    const minimumPixels: Record<string, number> = {
      spot: 240, temps: 160, molds: 240, env: 160, operatorMetadata: 360, timeseries: 320,
    };
    for (const [key, minimum] of Object.entries(minimumPixels)) {
      const item = items.find((entry) => entry.key === key);
      expect(item, key).toBeDefined();
      // Twenty-pixel tracks plus the four-pixel gaps used by the native grid.
      expect(item!.height * DEFAULT_ROW_HEIGHT + (item!.height - 1) * 4, key)
        .toBeGreaterThanOrEqual(minimum);
    }
    expectNoOverlappingItems(items);
    expect(Object.fromEntries(items.map(({ key, properties: _properties, ...item }) => [key, item])))
      .toEqual(getPresetById('16:9')!.layout);
  });

  it('does not replace a complete operator-saved layout with the fresh dashboard geometry', () => {
    const saved: SavedLayoutMap = {
      spot: { x: 0, y: 0, width: 30, height: 18, type: 'spot', title: 'Saved temperature' },
      camera: { x: 0, y: 18, width: 30, height: 20, type: 'camera', title: 'Saved camera' },
      operatorMetadata: { x: 30, y: 0, width: 30, height: 18, type: 'operatorMetadata', title: 'Saved work' },
      timeseries: { x: 0, y: 38, width: 60, height: 14, type: 'timeseries', title: 'Saved chart' },
    };
    const before = JSON.parse(JSON.stringify(saved));
    const items = resolveDashboardItems(saved);
    expect(items).toHaveLength(Object.keys(saved).length);
    for (const item of items) expect(item).toMatchObject({ key: item.key, ...saved[item.key] });
    expect(saved).toEqual(before);
    expectNoOverlappingItems(items);
  });

  it('adds required operator metadata when a saved layout does not include it', () => {
    const savedLayout: SavedLayoutMap = {
      kpi: { x: 0, y: 0, width: 15, height: 18, type: 'kpi', title: 'KPI' },
      timeseries: { x: 0, y: 18, width: 60, height: 8, type: 'timeseries', title: 'Trend' },
    };

    const items = resolveDashboardItems(savedLayout);

    expect(items.find((item) => item.type === 'operatorMetadata')).toMatchObject({
      key: 'operatorMetadata',
      type: 'operatorMetadata',
      width: 20,
      height: 16,
    });
  });

  it('does not add a duplicate when a saved layout already has an operator metadata widget by type', () => {
    const savedLayout: SavedLayoutMap = {
      'operatorMetadata-1700000000000': {
        x: 0,
        y: 0,
        width: 20,
        height: 6,
        type: 'operatorMetadata',
        title: 'Work Info',
      },
    };

    const items = resolveDashboardItems(savedLayout);
    const operatorItems = items.filter((item) => item.type === 'operatorMetadata');

    expect(operatorItems).toHaveLength(1);
    expect(operatorItems[0].key).toBe('operatorMetadata-1700000000000');
    expect(operatorItems[0].height).toBe(16);
  });

  it('pushes saved overlapping widgets below the required operator metadata height', () => {
    const savedLayout: SavedLayoutMap = {
      operatorMetadata: { x: 40, y: 12, width: 20, height: 6, type: 'operatorMetadata', title: 'Work Info' },
      timeseries: { x: 0, y: 18, width: 60, height: 8, type: 'timeseries', title: 'Trend' },
    };

    const items = resolveDashboardItems(savedLayout);
    const operatorItem = items.find((item) => item.type === 'operatorMetadata');
    const timeSeriesItem = items.find((item) => item.type === 'timeseries');

    expect(operatorItem).toMatchObject({
      height: 16,
      y: 12,
    });
    expect(timeSeriesItem).toMatchObject({
      y: 28,
    });
  });

  it('cascades pushed widgets below secondary saved layout overlaps', () => {
    const savedLayout: SavedLayoutMap = {
      operatorMetadata: { x: 40, y: 12, width: 20, height: 6, type: 'operatorMetadata', title: 'Work Info' },
      timeseries: { x: 0, y: 18, width: 60, height: 8, type: 'timeseries', title: 'Trend' },
      memo: { x: 0, y: 28, width: 60, height: 4, type: 'markdown', title: 'Memo' },
    };

    const items = resolveDashboardItems(savedLayout);
    const timeSeriesItem = items.find((item) => item.type === 'timeseries');
    const memoItem = items.find((item) => item.key === 'memo');

    expect(timeSeriesItem).toMatchObject({
      y: 28,
    });
    expect(memoItem).toMatchObject({
      y: 36,
    });
    expectNoOverlappingItems(items);
  });

  it('moves operator metadata below earlier custom overlaps before cascading following widgets', () => {
    const savedLayout: SavedLayoutMap = {
      customHeader: { x: 40, y: 8, width: 20, height: 8, type: 'markdown', title: 'Custom Header' },
      operatorMetadata: { x: 40, y: 12, width: 20, height: 6, type: 'operatorMetadata', title: 'Work Info' },
      timeseries: { x: 0, y: 18, width: 60, height: 8, type: 'timeseries', title: 'Trend' },
    };

    const items = resolveDashboardItems(savedLayout);
    const customHeaderItem = items.find((item) => item.key === 'customHeader');
    const operatorItem = items.find((item) => item.type === 'operatorMetadata');
    const timeSeriesItem = items.find((item) => item.type === 'timeseries');

    expect(customHeaderItem).toMatchObject({
      y: 8,
    });
    expect(operatorItem).toMatchObject({
      y: 16,
      height: 16,
    });
    expect(timeSeriesItem).toMatchObject({
      y: 32,
    });
    expectNoOverlappingItems(items);
  });

  it('places the required operator metadata widget below the layout when its default slot is occupied', () => {
    const savedLayout: SavedLayoutMap = {
      blocking: { x: 40, y: 12, width: 20, height: 6, type: 'markdown', title: 'Blocking' },
      timeseries: { x: 0, y: 18, width: 60, height: 8, type: 'timeseries', title: 'Trend' },
    };

    const items = resolveDashboardItems(savedLayout);
    const operatorItem = items.find((item) => item.type === 'operatorMetadata');

    expect(operatorItem).toMatchObject({
      key: 'operatorMetadata',
      y: 26,
    });
  });
});
