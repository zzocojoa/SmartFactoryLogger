import { describe, expect, it } from 'vitest';
import { CURRENT_LAYOUT_COLS } from './logic';
import { getPresetById } from './layoutPresets';
import type { LayoutPreset, LayoutPresetId } from './layoutPresets.types';
import type { LayoutEntry } from '../types';

const getRequiredPreset = (id: LayoutPresetId): LayoutPreset => {
  const preset = getPresetById(id);

  if (preset === undefined) {
    throw new Error(`Layout preset was not found: ${id}`);
  }

  return preset;
};

type NamedLayoutEntry = LayoutEntry & {
  key: string;
};

const buildNamedLayoutEntries = (preset: LayoutPreset): NamedLayoutEntry[] => {
  return Object.entries(preset.layout).map(([key, entry]) => ({
    key,
    ...entry,
  }));
};

const getRight = (entry: LayoutEntry): number => {
  return entry.x + entry.width;
};

const getBottom = (entry: LayoutEntry): number => {
  return entry.y + entry.height;
};

const entriesOverlap = (first: LayoutEntry, second: LayoutEntry): boolean => {
  return first.x < getRight(second) && getRight(first) > second.x && first.y < getBottom(second) && getBottom(first) > second.y;
};

describe('layoutPresets', () => {
  it('keeps every 21:9 widget inside the grid bounds', () => {
    const preset = getRequiredPreset('21:9');
    const layoutEntries = buildNamedLayoutEntries(preset);

    layoutEntries.forEach((entry) => {
      expect(entry.x).toBeGreaterThanOrEqual(0);
      expect(entry.y).toBeGreaterThanOrEqual(0);
      expect(getRight(entry)).toBeLessThanOrEqual(CURRENT_LAYOUT_COLS);
      expect(entry.width).toBeGreaterThan(0);
      expect(entry.height).toBeGreaterThan(0);
    });
  });

  it('does not overlap any pair of 21:9 widgets', () => {
    const preset = getRequiredPreset('21:9');
    const layoutEntries = buildNamedLayoutEntries(preset);

    layoutEntries.forEach((entry, index) => {
      layoutEntries.slice(index + 1).forEach((nextEntry) => {
        expect(entriesOverlap(entry, nextEntry), `${entry.key} overlaps ${nextEntry.key}`).toBe(false);
      });
    });
  });

  it('keeps the 21:9 time series chart full-width below a fully used top area', () => {
    const preset = getRequiredPreset('21:9');
    const layoutEntries = buildNamedLayoutEntries(preset);
    const timeSeriesLayout = preset.layout.timeseries;
    const topLayoutEntries = layoutEntries.filter((entry) => entry.key !== 'timeseries');
    const topArea = topLayoutEntries.reduce<number>((sum, entry) => sum + entry.width * entry.height, 0);
    const topBandArea = CURRENT_LAYOUT_COLS * timeSeriesLayout.y;
    const topMaxBottom = Math.max(...topLayoutEntries.map(getBottom));

    expect(timeSeriesLayout.x).toBe(0);
    expect(timeSeriesLayout.y).toBe(topMaxBottom);
    expect(timeSeriesLayout.width).toBe(CURRENT_LAYOUT_COLS);
    expect(timeSeriesLayout.height).toBeGreaterThanOrEqual(8);
    expect(topArea).toBe(topBandArea);

    expect(preset.layout.kpi.x + preset.layout.kpi.width).toBe(12);
    expect(getBottom(preset.layout.camera)).toBe(timeSeriesLayout.y);
    expect(getBottom(preset.layout.env)).toBe(timeSeriesLayout.y);
    expect(getRight(preset.layout.molds)).toBe(CURRENT_LAYOUT_COLS);
  });
});
