import { describe, expect, it } from 'vitest';
import {
  resolveDashboardItems,
  type SavedLayoutMap,
} from './DashboardSceneModel';

describe('resolveDashboardItems', () => {
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
      height: 6,
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
