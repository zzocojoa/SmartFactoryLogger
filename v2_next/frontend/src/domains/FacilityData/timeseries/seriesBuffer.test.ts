import { SeriesBuffer } from './seriesBuffer';
import type { TimeSeriesKey } from './seriesCatalog';
import type { SeriesSample } from './seriesSampling';

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

const getTimestamps = (samples: readonly SeriesSample[]): number[] =>
  samples.map((sample) => sample.timestampMs);

describe('SeriesBuffer', () => {
  it('appends samples in sequence and exposes live stats', () => {
    const buffer = new SeriesBuffer(10_000, 10);

    buffer.append(buildSample(1_000, 10));
    buffer.append(buildSample(2_000, 20));
    buffer.append(buildSample(3_000, 30));

    expect(getTimestamps(buffer.getSamples())).toEqual([1_000, 2_000, 3_000]);
    expect(buffer.getStats()).toMatchObject({
      count: 3,
      windowMs: 10_000,
      maxPoints: 10,
    });
    expect(buffer.getSnapshot()).toMatchObject({
      generation: 0,
      chronological: true,
      firstSequence: 0,
      nextSequence: 3,
    });
  });

  it('trims old samples by cutoff boundary and maxPoints', () => {
    const buffer = new SeriesBuffer(2_500, 3);

    buffer.append(buildSample(1_000, 10));
    buffer.append(buildSample(2_000, 20));
    buffer.append(buildSample(3_000, 30));
    buffer.append(buildSample(4_000, 40));

    expect(getTimestamps(buffer.getSamples())).toEqual([2_000, 3_000, 4_000]);
    expect(buffer.getStats().count).toBe(3);
    expect(buffer.getSnapshot()).toMatchObject({
      firstSequence: 1,
      nextSequence: 4,
    });

    buffer.append(buildSample(7_000, 70));

    expect(getTimestamps(buffer.getSamples())).toEqual([7_000]);
    expect(buffer.getStats().count).toBe(1);
    expect(buffer.getSnapshot()).toMatchObject({
      firstSequence: 4,
      nextSequence: 5,
    });
  });

  it('keeps sequence counters consistent when window and maxPoint trims combine', () => {
    const buffer = new SeriesBuffer(2_000, 2);

    buffer.append(buildSample(1_000, 10));
    buffer.append(buildSample(2_000, 20));
    buffer.append(buildSample(3_000, 30));

    expect(buffer.getSnapshot()).toMatchObject({
      firstSequence: 1,
      nextSequence: 3,
    });
    expect(getTimestamps(buffer.getSamples())).toEqual([2_000, 3_000]);

    buffer.append(buildSample(6_000, 60));

    const snapshot = buffer.getSnapshot();
    expect(getTimestamps(snapshot.samples)).toEqual([6_000]);
    expect(snapshot.firstSequence + snapshot.samples.length).toBe(snapshot.nextSequence);
  });

  it('does not expose mutable buffered samples through snapshots', () => {
    const buffer = new SeriesBuffer(10_000, 10);

    buffer.append(buildSample(1_000, 10));
    const snapshot = buffer.getSnapshot();

    expect(Object.isFrozen(snapshot.samples)).toBe(true);
    expect(Object.isFrozen(snapshot.samples[0])).toBe(true);
    expect(Object.isFrozen(snapshot.samples[0].values)).toBe(true);
    expect(() => {
      (snapshot.samples as SeriesSample[]).splice(0, 1);
    }).toThrow(TypeError);
    expect(() => {
      snapshot.samples[0].values.Spot = 99;
    }).toThrow(TypeError);
    expect(getTimestamps(buffer.getSamples())).toEqual([1_000]);
    expect(buffer.getSamples()[0].values.Spot).toBe(10);
  });

  it('clears samples and increments generation', () => {
    const buffer = new SeriesBuffer(10_000, 10);

    buffer.append(buildSample(1_000, 10));
    const generationBeforeClear = buffer.getSnapshot().generation;

    buffer.clear();

    expect(buffer.getSamples()).toEqual([]);
    expect(buffer.getStats().count).toBe(0);
    expect(buffer.getSnapshot()).toMatchObject({
      generation: generationBeforeClear + 1,
      chronological: true,
      firstSequence: 1,
      nextSequence: 1,
    });
  });

  it('marks chronological as false when an out-of-order sample is appended', () => {
    const buffer = new SeriesBuffer(10_000, 10);

    buffer.append(buildSample(2_000, 20));
    buffer.append(buildSample(1_000, 10));

    expect(getTimestamps(buffer.getSamples())).toEqual([2_000, 1_000]);
    expect(buffer.getStats().count).toBe(2);
    expect(buffer.getSnapshot()).toMatchObject({
      generation: 1,
      chronological: false,
    });
  });
});
