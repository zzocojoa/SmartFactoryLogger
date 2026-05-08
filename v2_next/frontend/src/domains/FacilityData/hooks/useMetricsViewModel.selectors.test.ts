import {
  filterSeriesSamplesByWindow,
  getSeriesSamplesWindowRange,
} from './useMetricsViewModel.selectors';
import type { TimeSeriesKey } from '../timeseries/seriesCatalog';
import type { SeriesSample } from '../timeseries/seriesSampling';

const buildValues = (
  overrides: Partial<Record<TimeSeriesKey, number | null>>
): Record<TimeSeriesKey, number | null> => ({
  Spot: null,
  Press: null,
  Temp_F: null,
  Temp_B: null,
  Speed: null,
  EndPos: null,
  Count: null,
  Billet_Length: null,
  Mold1: null,
  Mold2: null,
  Mold3: null,
  Mold4: null,
  Mold5: null,
  Mold6: null,
  Billet_Temp: null,
  At_Temp: null,
  At_Pre: null,
  ...overrides,
});

const buildSample = (timestampMs: number, spotValue: number): SeriesSample => ({
  timestampMs,
  values: buildValues({ Spot: spotValue }),
});

const getTimestamps = (samples: SeriesSample[]): number[] =>
  samples.map((sample) => sample.timestampMs);

interface SelectorWindowCase {
  label: string;
  seriesWindowMin: number;
  nowMs: number;
  cutoffMs: number;
}

const selectorWindowCases: SelectorWindowCase[] = [
  {
    label: '1m',
    seriesWindowMin: 1,
    nowMs: 3_600_000,
    cutoffMs: 3_540_000,
  },
  {
    label: '5m',
    seriesWindowMin: 5,
    nowMs: 3_600_000,
    cutoffMs: 3_300_000,
  },
  {
    label: '30m',
    seriesWindowMin: 30,
    nowMs: 3_600_000,
    cutoffMs: 1_800_000,
  },
  {
    label: '60m',
    seriesWindowMin: 60,
    nowMs: 3_600_000,
    cutoffMs: 0,
  },
];

describe('filterSeriesSamplesByWindow', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it.each(selectorWindowCases)(
    'includes samples exactly on the $label cutoff boundary',
    ({ seriesWindowMin, nowMs, cutoffMs }: SelectorWindowCase) => {
      const samples: SeriesSample[] = [
        buildSample(cutoffMs - 1, 1),
        buildSample(cutoffMs, 2),
        buildSample(nowMs, 3),
      ];

      const result = filterSeriesSamplesByWindow(samples, seriesWindowMin, nowMs);

      expect(getTimestamps(result)).toEqual([cutoffMs, nowMs]);
    }
  );

  it('filters out-of-order fallback samples without relying on sorted input', () => {
    const samples: SeriesSample[] = [
      buildSample(70_000, 1),
      buildSample(39_999, 2),
      buildSample(100_000, 3),
      buildSample(40_000, 4),
    ];

    const result = filterSeriesSamplesByWindow(samples, 1, 100_000);

    expect(getTimestamps(result)).toEqual([70_000, 100_000, 40_000]);
    expect(result.map((sample) => sample.values.Spot)).toEqual([1, 3, 4]);
  });

  it('keeps duplicate timestamps within the window in input order', () => {
    const samples: SeriesSample[] = [
      buildSample(40_000, 1),
      buildSample(40_000, 2),
      buildSample(70_000, 3),
    ];

    const result = filterSeriesSamplesByWindow(samples, 1, 100_000);

    expect(getTimestamps(result)).toEqual([40_000, 40_000, 70_000]);
    expect(result.map((sample) => sample.values.Spot)).toEqual([1, 2, 3]);
  });

  it('returns an empty array when no samples are inside the window', () => {
    const samples: SeriesSample[] = [
      buildSample(1_000, 1),
      buildSample(39_999, 2),
    ];

    const result = filterSeriesSamplesByWindow(samples, 1, 100_000);

    expect(result).toEqual([]);
  });

  it('uses the provided frame time instead of the current wall clock', () => {
    jest.spyOn(Date, 'now').mockReturnValue(100_001);
    const samples: SeriesSample[] = [
      buildSample(40_000, 1),
      buildSample(100_000, 2),
    ];

    const result = filterSeriesSamplesByWindow(samples, 1, 100_000);

    expect(getTimestamps(result)).toEqual([40_000, 100_000]);
  });
});

describe('getSeriesSamplesWindowRange', () => {
  it.each(selectorWindowCases)(
    'returns a range that starts at the $label cutoff boundary',
    ({ seriesWindowMin, nowMs, cutoffMs }: SelectorWindowCase) => {
      const samples: SeriesSample[] = [
        buildSample(cutoffMs - 1, 1),
        buildSample(cutoffMs, 2),
        buildSample(nowMs, 3),
      ];

      const result = getSeriesSamplesWindowRange(samples, seriesWindowMin, nowMs);

      expect(result).toEqual({
        startIndex: 1,
        endIndex: 3,
        cutoffMs,
      });
    }
  );

  it('keeps duplicate cutoff timestamps inside the selected range', () => {
    const samples: SeriesSample[] = [
      buildSample(39_999, 1),
      buildSample(40_000, 2),
      buildSample(40_000, 3),
      buildSample(70_000, 4),
    ];

    const result = getSeriesSamplesWindowRange(samples, 1, 100_000);

    expect(result).toEqual({
      startIndex: 1,
      endIndex: 4,
      cutoffMs: 40_000,
    });
    expect(getTimestamps(samples.slice(result.startIndex, result.endIndex))).toEqual([
      40_000,
      40_000,
      70_000,
    ]);
  });

  it('returns an empty range when the entire sample set is before the window', () => {
    const samples: SeriesSample[] = [
      buildSample(1_000, 1),
      buildSample(39_999, 2),
    ];

    const result = getSeriesSamplesWindowRange(samples, 1, 100_000);

    expect(result).toEqual({
      startIndex: 2,
      endIndex: 2,
      cutoffMs: 40_000,
    });
  });
});
