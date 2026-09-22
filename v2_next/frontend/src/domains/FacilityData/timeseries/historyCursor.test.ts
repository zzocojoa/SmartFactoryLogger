import { describe, expect, it } from 'vitest';
import type { FactoryData } from '../../../shared/types';
import { buildSeriesSampleAt } from './seriesSampling';
import { SeriesBuffer } from './seriesBuffer';

const instance = 'a'.repeat(32);
const sample = (sequence: number, timestampMs: number, id = instance) => buildSeriesSampleAt({
  Time: new Date(timestampMs).toISOString(), Status: 'Running', Spot: sequence,
  history_instance_id: id, history_sequence: sequence,
} as FactoryData, timestampMs);

describe('history identity in the actual series buffer', () => {
  it('keeps equal UTC acquisitions and deduplicates repeated live/history identities', () => {
    const buffer = new SeriesBuffer(100_000, 10);
    buffer.append(sample(1, 60_000));
    buffer.append(sample(2, 60_000));
    buffer.appendHistory([sample(1, 60_000), sample(2, 60_000), sample(3, 59_000)]);
    expect(buffer.getSamples().map(s => s.values.Spot)).toEqual([3, 1, 2]);
    expect(buffer.getHistoryCursor()).toBe(`${instance}:3`);
  });

  it('advances cursor through reversed UTC and preserves it after display trimming', () => {
    const buffer = new SeriesBuffer(100_000, 2);
    buffer.append(sample(1, 60_000));
    buffer.append(sample(2, 1_000));
    buffer.appendHistory([sample(3, 2_000)]);
    expect(buffer.getHistoryCursor()).toBe(`${instance}:3`);
    expect(buffer.getLatestTimestampMs()).toBe(60_000);
    buffer.appendHistory([sample(1, 60_000)]);
    expect(buffer.getHistoryCursor()).toBe(`${instance}:3`);
  });

  it('clears old generation when a new backend publishes at the same UTC', () => {
    const buffer = new SeriesBuffer(100_000, 10);
    buffer.append(sample(50, 1_000));
    buffer.append(sample(1, 1_000, 'b'.repeat(32)));
    expect(buffer.getSamples().map(s => s.values.Spot)).toEqual([1]);
    expect(buffer.getHistoryCursor()).toBe(`${'b'.repeat(32)}:1`);
    buffer.clear();
    expect(buffer.getHistoryCursor()).toBeNull();
  });
});
