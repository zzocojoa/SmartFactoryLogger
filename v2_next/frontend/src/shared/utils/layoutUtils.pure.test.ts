import { describe, expect, it } from 'vitest';
import { buildLayoutMapFromArray } from './layoutUtils.pure';

describe('buildLayoutMapFromArray', () => {
  it('keeps the legacy seventh array entry mapped to timeseries', () => {
    const layout = buildLayoutMapFromArray([
      { x: 0, y: 0, width: 1, height: 1, type: 'kpi' },
      { x: 1, y: 0, width: 1, height: 1, type: 'spot' },
      { x: 2, y: 0, width: 1, height: 1, type: 'temps' },
      { x: 3, y: 0, width: 1, height: 1, type: 'camera' },
      { x: 4, y: 0, width: 1, height: 1, type: 'molds' },
      { x: 5, y: 0, width: 1, height: 1, type: 'env' },
      { x: 0, y: 18, width: 60, height: 8, type: 'timeseries' },
    ]);

    expect(layout.timeseries).toMatchObject({
      type: 'timeseries',
      y: 18,
      width: 60,
    });
    expect(layout.operatorMetadata).toBeUndefined();
  });
});
