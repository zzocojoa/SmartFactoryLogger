import { createRequire } from 'node:module';
import { dateTimeFormat, dateTimeForTimeZone } from '@grafana/data';
import moment from 'moment';
import timezone from 'moment-timezone';
import { describe, expect, it } from 'vitest';
import { buildTimeRangeFromSamples } from '../../domains/FacilityData/timeseries/seriesPanelData.math';
import { buildSeriesSampleAt } from '../../domains/FacilityData/timeseries/seriesSampling';
import type { FactoryData } from '../types';

const requireModule = createRequire(import.meta.url);

describe('Moment security upgrade compatibility', () => {
  it('shares the fixed Moment instance with Grafana and the browser timezone bundle', () => {
    const momentEntry = requireModule.resolve('moment');
    for (const consumer of ['@grafana/data', '@grafana/ui', 'moment-timezone']) {
      const consumerRequire = createRequire(requireModule.resolve(consumer));
      expect(consumerRequire.resolve('moment')).toBe(momentEntry);
    }
    expect(timezone).toBe(moment);
  });

  it('preserves numeric telemetry timestamps through the production time-range builder', () => {
    const timestampMs = Date.parse('2026-09-30T00:00:00.123Z');
    const data: FactoryData = {
      Time: '2026-09-30T00:00:00.123Z', Status: 'Running',
      Speed: 0, Press: 0, Count: 0, EndPos: null, Billet_Length: null,
      Spot: 500, Temp_F: null, Temp_B: null, Billet_Temp: null,
      Mold1: null, Mold2: null, Mold3: null, Mold4: null, Mold5: null, Mold6: null,
      At_Temp: null, At_Pre: null,
    };
    const range = buildTimeRangeFromSamples([
      buildSeriesSampleAt(data, timestampMs),
      buildSeriesSampleAt(data, timestampMs + 1000),
    ], 60000);
    expect(range.from.valueOf()).toBe(timestampMs);
    expect(range.to.valueOf()).toBe(timestampMs + 1000);
    expect(range.raw.from).toBe(range.from);
    expect(dateTimeFormat(range.from, { timeZone: 'utc', format: 'YYYY-MM-DD HH:mm:ss.SSS' }))
      .toBe('2026-09-30 00:00:00.123');
    expect(dateTimeFormat(range.from, { timeZone: 'Asia/Seoul', format: 'YYYY-MM-DD HH:mm:ss.SSS' }))
      .toBe('2026-09-30 09:00:00.123');
  });

  it('preserves Grafana timezone conversion across a DST transition', () => {
    const before = dateTimeForTimeZone('America/New_York', Date.parse('2026-03-08T06:59:59Z'));
    const after = dateTimeForTimeZone('America/New_York', Date.parse('2026-03-08T07:00:00Z'));
    expect(before.format('HH:mm:ss Z')).toBe('01:59:59 -05:00');
    expect(after.format('HH:mm:ss Z')).toBe('03:00:00 -04:00');
    expect(after.diff(before)).toBe(1000);
  });

  it('retains valid string locale selection and restores the shared locale', () => {
    const previousLocale = moment.locale();
    try {
      expect(moment.locale('en')).toBe('en');
      expect(moment.utc('2026-09-30T00:00:00Z').format('YYYY-MM-DD')).toBe('2026-09-30');
    } finally {
      moment.locale(previousLocale);
    }
  });
});
