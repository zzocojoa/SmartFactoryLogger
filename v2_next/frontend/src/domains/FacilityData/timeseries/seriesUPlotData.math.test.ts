import { describe, expect, it } from 'vitest';
import type uPlot from 'uplot';
import type { SeriesFrame } from './seriesDataFrames';
import {
  buildDownsampledIndices,
  buildRenderPointLimit,
  buildTimeWindowRange,
  buildVisibleUPlotData,
} from './seriesUPlotData.math';
import type { TimeSeriesMeta } from './seriesCatalog';

const TEST_METAS: TimeSeriesMeta[] = [
  {
    key: 'Spot',
    label: 'Spot',
    source: 'SPOT',
    axis: 'temperature',
    group: 'temperature',
    unit: 'C',
    visibleByDefault: true,
    decimals: 1,
    legacyKey: 'Temperature',
  },
  {
    key: 'Press',
    label: 'Press',
    source: 'Extruder',
    axis: 'process',
    group: 'process',
    unit: 'bar',
    visibleByDefault: true,
    decimals: 1,
    legacyKey: 'Press',
  },
];

const buildFrame = (): SeriesFrame => ({
  fields: [
    {
      name: 'time',
      type: 'time',
      values: [3_000, 1_000, 2_000],
    },
    {
      name: 'Spot',
      type: 'number',
      values: [30, 10, 20],
    },
    {
      name: 'Press',
      type: 'number',
      values: [300, 100, 200],
    },
  ],
});

describe('series uPlot data helpers', () => {
  it('sorts projected frame data by timestamp and converts time to seconds', () => {
    const uPlotData = buildVisibleUPlotData(buildFrame(), TEST_METAS, 800);

    expect(uPlotData).toEqual([
      [1, 2, 3],
      [10, 20, 30],
      [100, 200, 300],
    ]);
  });

  it('keeps first, last, and bucket extrema when downsampling', () => {
    const uPlotData = [
      [0, 1, 2, 3, 4, 5],
      [0, 10, 2, 3, 4, 5],
    ] as uPlot.AlignedData;

    expect(buildDownsampledIndices(uPlotData, 4)).toEqual([0, 1, 2, 5]);
  });

  it('preserves the newest point when extrema selection exceeds the point limit', () => {
    const uPlotData = [
      [0, 1, 2, 3, 4, 5],
      [0, 10, 2, 3, 4, 5],
      [0, 5, 6, 30, 1, 5],
    ] as uPlot.AlignedData;

    expect(buildDownsampledIndices(uPlotData, 4)).toEqual([0, 1, 2, 5]);
  });

  it('builds bounded render point limits from chart width', () => {
    expect(buildRenderPointLimit(100)).toBe(300);
    expect(buildRenderPointLimit(800)).toBe(1600);
    expect(buildRenderPointLimit(10_000)).toBe(4000);
    expect(buildRenderPointLimit(Number.NaN)).toBe(1600);
  });

  it('builds a trailing time window from the latest plotted point', () => {
    const uPlotData = [[10, 20, 30], [1, 2, 3]] as uPlot.AlignedData;

    expect(buildTimeWindowRange(uPlotData, 1)).toEqual([-30, 30]);
    expect(buildTimeWindowRange(uPlotData, 0)).toBeNull();
    expect(buildTimeWindowRange(null, 1)).toBeNull();
  });
});
