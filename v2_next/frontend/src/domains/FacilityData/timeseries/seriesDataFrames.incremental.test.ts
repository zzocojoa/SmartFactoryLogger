import type { ThresholdsConfig } from '@grafana/data';
import { SeriesBuffer } from './seriesBuffer';
import { buildIncrementalTimeSeriesFrame, buildTimeSeriesFrame } from './seriesDataFrames';
import type {
  IncrementalSeriesFrameCache,
  IncrementalSeriesFrameResult,
  SeriesFrame,
  SeriesFrameSampleRange,
} from './seriesDataFrames.types';
import type { TimeSeriesKey, TimeSeriesMeta } from './seriesCatalog';
import type { SeriesSample } from './seriesSampling';

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

const buildSample = (timestampMs: number, spotValue: number, pressValue: number): SeriesSample => ({
  timestampMs,
  values: buildValues({ Spot: spotValue, Press: pressValue }),
});

const getFieldValues = (frame: SeriesFrame, fieldName: string): Array<number | null> => {
  const field = frame.fields.find((candidate) => candidate.name === fieldName);
  if (!field) {
    throw new Error(`Expected frame field "${fieldName}" to exist.`);
  }
  return field.values;
};

const appendSamples = (buffer: SeriesBuffer, samples: readonly SeriesSample[]): void => {
  for (const sample of samples) {
    buffer.append(sample);
  }
};

const buildRange = (buffer: SeriesBuffer): SeriesFrameSampleRange => ({
  startIndex: 0,
  endIndex: buffer.getSnapshot().samples.length,
});

const buildIncrementalResultForRange = (
  buffer: SeriesBuffer,
  range: SeriesFrameSampleRange,
  previousCache: IncrementalSeriesFrameCache | null,
  thresholdsByKey: Partial<Record<TimeSeriesKey, ThresholdsConfig>> | undefined,
): IncrementalSeriesFrameResult =>
  buildIncrementalTimeSeriesFrame({
    snapshot: buffer.getSnapshot(),
    range,
    previousCache,
    metas: TEST_METAS,
    thresholdsByKey,
  });

const buildIncrementalResult = (
  buffer: SeriesBuffer,
  previousCache: IncrementalSeriesFrameCache | null,
  thresholdsByKey: Partial<Record<TimeSeriesKey, ThresholdsConfig>> | undefined,
): IncrementalSeriesFrameResult =>
  buildIncrementalResultForRange(buffer, buildRange(buffer), previousCache, thresholdsByKey);

describe('buildIncrementalTimeSeriesFrame', () => {
  it('matches buildTimeSeriesFrame for the first build', () => {
    const buffer = new SeriesBuffer(10_000, 10);
    const samples: SeriesSample[] = [
      buildSample(1_000, 10, 100),
      buildSample(2_000, 20, 200),
    ];
    appendSamples(buffer, samples);

    const result = buildIncrementalResult(buffer, null, undefined);

    expect(result.frame).toEqual(buildTimeSeriesFrame(samples, TEST_METAS, undefined));
  });

  it('appends one sample without rebuilding existing field values', () => {
    const buffer = new SeriesBuffer(10_000, 10);
    const initialSamples: SeriesSample[] = [
      buildSample(1_000, 10, 100),
      buildSample(2_000, 20, 200),
    ];
    appendSamples(buffer, initialSamples);
    const initialResult = buildIncrementalResult(buffer, null, undefined);
    const timeValues = getFieldValues(initialResult.frame, 'time');
    const spotValues = getFieldValues(initialResult.frame, 'Spot');
    const pressValues = getFieldValues(initialResult.frame, 'Press');

    buffer.append(buildSample(3_000, 30, 300));
    const result = buildIncrementalResult(buffer, initialResult.cache, undefined);

    expect(getFieldValues(result.frame, 'time')).toBe(timeValues);
    expect(getFieldValues(result.frame, 'Spot')).toBe(spotValues);
    expect(getFieldValues(result.frame, 'Press')).toBe(pressValues);
    expect(getFieldValues(result.frame, 'time')).toEqual([1_000, 2_000, 3_000]);
    expect(getFieldValues(result.frame, 'Spot')).toEqual([10, 20, 30]);
    expect(getFieldValues(result.frame, 'Press')).toEqual([100, 200, 300]);
  });

  it('trims the head while preserving field value references when the window shrinks', () => {
    const buffer = new SeriesBuffer(10_000, 10);
    const samples: SeriesSample[] = [
      buildSample(1_000, 10, 100),
      buildSample(2_000, 20, 200),
      buildSample(3_000, 30, 300),
      buildSample(4_000, 40, 400),
    ];
    appendSamples(buffer, samples);
    const initialResult = buildIncrementalResult(buffer, null, undefined);
    const timeValues = getFieldValues(initialResult.frame, 'time');
    const spotValues = getFieldValues(initialResult.frame, 'Spot');
    const pressValues = getFieldValues(initialResult.frame, 'Press');

    const result = buildIncrementalResultForRange(
      buffer,
      { startIndex: 2, endIndex: 4 },
      initialResult.cache,
      undefined
    );

    expect(getFieldValues(result.frame, 'time')).toBe(timeValues);
    expect(getFieldValues(result.frame, 'Spot')).toBe(spotValues);
    expect(getFieldValues(result.frame, 'Press')).toBe(pressValues);
    expect(getFieldValues(result.frame, 'time')).toEqual([3_000, 4_000]);
    expect(getFieldValues(result.frame, 'Spot')).toEqual([30, 40]);
    expect(getFieldValues(result.frame, 'Press')).toEqual([300, 400]);
  });

  it('fully rebuilds after expanding the window', () => {
    const buffer = new SeriesBuffer(10_000, 10);
    const samples: SeriesSample[] = [
      buildSample(1_000, 10, 100),
      buildSample(2_000, 20, 200),
      buildSample(3_000, 30, 300),
      buildSample(4_000, 40, 400),
    ];
    appendSamples(buffer, samples);
    const initialResult = buildIncrementalResultForRange(
      buffer,
      { startIndex: 1, endIndex: 3 },
      null,
      undefined
    );
    const timeValues = getFieldValues(initialResult.frame, 'time');
    const spotValues = getFieldValues(initialResult.frame, 'Spot');
    const pressValues = getFieldValues(initialResult.frame, 'Press');

    const result = buildIncrementalResultForRange(buffer, buildRange(buffer), initialResult.cache, undefined);

    expect(getFieldValues(result.frame, 'time')).not.toBe(timeValues);
    expect(getFieldValues(result.frame, 'Spot')).not.toBe(spotValues);
    expect(getFieldValues(result.frame, 'Press')).not.toBe(pressValues);
    expect(result.frame).toEqual(buildTimeSeriesFrame(buffer.getSamples(), TEST_METAS, undefined));
  });

  it('keeps values references stable when only thresholds change', () => {
    const buffer = new SeriesBuffer(10_000, 10);
    const samples: SeriesSample[] = [
      buildSample(1_000, 10, 100),
      buildSample(2_000, 20, 200),
    ];
    appendSamples(buffer, samples);
    const initialResult = buildIncrementalResult(buffer, null, undefined);
    const initialSpotField = initialResult.frame.fields.find((field) => field.name === 'Spot');
    const spotValues = getFieldValues(initialResult.frame, 'Spot');
    const thresholdsByKey: Partial<Record<TimeSeriesKey, ThresholdsConfig>> = {
      Spot: {
        mode: 'absolute',
        steps: [
          { color: 'green', value: null },
          { color: 'red', value: 50 },
        ],
      } as ThresholdsConfig,
    };

    const result = buildIncrementalResult(buffer, initialResult.cache, thresholdsByKey);

    expect(getFieldValues(result.frame, 'Spot')).toBe(spotValues);
    expect(initialSpotField?.config?.thresholds).toBeUndefined();
    expect(result.frame.fields.find((field) => field.name === 'Spot')?.config?.thresholds).toEqual(
      thresholdsByKey.Spot
    );
  });

  it('fully rebuilds when the catalog changes', () => {
    const buffer = new SeriesBuffer(10_000, 10);
    appendSamples(buffer, [
      buildSample(1_000, 10, 100),
      buildSample(2_000, 20, 200),
    ]);
    const initialResult = buildIncrementalResult(buffer, null, undefined);
    const spotValues = getFieldValues(initialResult.frame, 'Spot');
    const nextMetas: TimeSeriesMeta[] = [TEST_METAS[0]];

    const result = buildIncrementalTimeSeriesFrame({
      snapshot: buffer.getSnapshot(),
      range: buildRange(buffer),
      previousCache: initialResult.cache,
      metas: nextMetas,
      thresholdsByKey: undefined,
    });

    expect(getFieldValues(result.frame, 'Spot')).not.toBe(spotValues);
    expect(result.frame.fields.map((field) => field.name)).toEqual(['time', 'Spot']);
    expect(result.frame).toEqual(buildTimeSeriesFrame(buffer.getSamples(), nextMetas, undefined));
  });

  it('fully rebuilds after a buffer generation change', () => {
    const buffer = new SeriesBuffer(10_000, 10);
    const nowMs = Date.now();
    appendSamples(buffer, [
      buildSample(nowMs - 2_000, 10, 100),
      buildSample(nowMs - 1_000, 20, 200),
    ]);
    const initialResult = buildIncrementalResult(buffer, null, undefined);
    const spotValues = getFieldValues(initialResult.frame, 'Spot');

    buffer.setMaxPoints(10);
    const result = buildIncrementalResult(buffer, initialResult.cache, undefined);

    expect(getFieldValues(result.frame, 'Spot')).not.toBe(spotValues);
    expect(result.frame).toEqual(buildTimeSeriesFrame(buffer.getSamples(), TEST_METAS, undefined));
  });

  it('uses full rebuild fallback while samples are not chronological', () => {
    const buffer = new SeriesBuffer(10_000, 10);
    appendSamples(buffer, [
      buildSample(1_000, 10, 100),
      buildSample(3_000, 30, 300),
      buildSample(2_000, 20, 200),
    ]);
    const initialResult = buildIncrementalResult(buffer, null, undefined);
    const spotValues = getFieldValues(initialResult.frame, 'Spot');

    buffer.append(buildSample(4_000, 40, 400));
    const result = buildIncrementalResult(buffer, initialResult.cache, undefined);

    expect(buffer.getSnapshot().chronological).toBe(false);
    expect(getFieldValues(result.frame, 'Spot')).not.toBe(spotValues);
    expect(result.frame).toEqual(buildTimeSeriesFrame(buffer.getSamples(), TEST_METAS, undefined));
  });

  it('raises explicit range errors for invalid sample ranges', () => {
    const buffer = new SeriesBuffer(10_000, 10);
    appendSamples(buffer, [
      buildSample(1_000, 10, 100),
      buildSample(2_000, 20, 200),
    ]);

    expect(() => {
      buildIncrementalResultForRange(buffer, { startIndex: -1, endIndex: 2 }, null, undefined);
    }).toThrow(RangeError);
    expect(() => {
      buildIncrementalResultForRange(buffer, { startIndex: 0, endIndex: 3 }, null, undefined);
    }).toThrow(RangeError);
  });
});
