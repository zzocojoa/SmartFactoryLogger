import { describe, expect, it } from 'vitest';
import { buildSpotStatusBadges, getCameraStatus } from './commBadge';
import type { SpotConfig, SpotTemperatureHealth } from '../types';

const freshObservation: SpotTemperatureHealth = {
  diagnostics_available: true, spot_poll_status: 'success', spot_raw_validity: 'valid_temperature',
  spot_source_freshness: 'fresh', temperature_status_shadow: 'ok', spot_cache_status: 'fresh',
  temperature_value_origin: 'current_observation', cache_fallback_allowed: true,
  spot_snapshot_age_ms: 100, spot_value_age_ms: 100,
  spot_poll_freshness_threshold_sec: 3, spot_cache_expiry_threshold_sec: 10,
};
const classify = (patch: Partial<SpotTemperatureHealth> = {}, elapsed = 0) => buildSpotStatusBadges({
  observation: { ...freshObservation, ...patch }, metrics: { last_success_time: 1, read_failures: 20 },
  receipt: { receivedAtMonotonicMs: 1000, ageAtReceiptMs: 0 }, monotonicNowMs: 1000 + elapsed,
});

describe('SPOT communication and temperature classification', () => {
  it.each(['spot_poll_status', 'spot_raw_validity', 'spot_source_freshness',
    'temperature_status_shadow', 'temperature_value_origin', 'spot_cache_status'] as const)('keeps malformed %s diagnostic details renderable while showing UNKNOWN', key => {
    const badges = classify({[key]: {code: 'invalid'}} as unknown as Partial<SpotTemperatureHealth>);
    expect(badges.commBadge.text).toBe('SPOT UNKNOWN');
    expect(badges.temperatureBadge.text).toBe('Temp UNKNOWN');
    expect(badges.details.every(({value}) => typeof value === 'string')).toBe(true);
  });

  it.each([
    ['valid_temperature', null, 'OK'],
    ['invalid_sentinel', 'temperature_under_range', 'UNDER_RANGE'],
    ['invalid_sentinel', 'temperature_over_range', 'OVER_RANGE'],
    ['invalid_sentinel', 'unclassified_device_status', 'INVALID'],
    ['empty_body', null, 'INVALID'], ['parse_error', null, 'INVALID'],
    ['out_of_range', null, 'INVALID'], ['verified_no_target', null, 'NO_TARGET'],
  ] as const)('keeps fresh %s communication OK regardless of old valid-temperature success', (raw, code, expected) => {
    const badges = classify({ spot_raw_validity: raw, spot_device_status_code: code });
    expect(badges.commBadge.text).toBe('SPOT OK');
    expect(badges.temperatureBadge.text).toBe(`Temp ${expected}`);
  });

  it.each(['timeout', 'connection_error', 'http_error'] as const)('prioritizes latest %s over recent success and recovers after success', (poll) => {
    const params = { metrics: { last_success_time: 999, last_error_time: 1000, read_failures: 2 },
      receipt: { receivedAtMonotonicMs: 0, ageAtReceiptMs: 0 }, monotonicNowMs: 100 };
    const failure = buildSpotStatusBadges({ ...params, observation: { ...freshObservation, spot_poll_status: poll,
      spot_raw_validity: 'not_received', temperature_value_origin: 'none', spot_cache_status: 'available_not_used' } });
    expect(failure.commBadge.text).toBe('SPOT DOWN');
    expect(failure.temperatureBadge.text).toBe('Temp SOURCE_ERROR');
    expect(buildSpotStatusBadges({ ...params, observation: freshObservation }).commBadge.text).toBe('SPOT OK');
  });

  it('shows permitted cached temperature only through its TTL, independently of DOWN', () => {
    const cache = { spot_poll_status: 'timeout', spot_raw_validity: 'not_received',
      temperature_value_origin: 'cached_observation', spot_cache_status: 'reused', spot_value_age_ms: 9000 } as const;
    expect(classify(cache, 1000).temperatureBadge.text).toBe('Temp CACHED');
    const expired = classify(cache, 1001);
    expect(expired.commBadge.text).toBe('SPOT DOWN');
    expect(expired.temperatureBadge.text).toBe('Temp STALE');
    expect(classify({ ...cache, cache_fallback_allowed: false }).temperatureBadge.text).toBe('Temp SOURCE_ERROR');
    expect(classify({ ...cache, spot_cache_status: 'available_not_used' }).temperatureBadge.text).toBe('Temp SOURCE_ERROR');
  });

  it('ages stopped snapshots, uses the minimum 5s, and honors backend stale immediately', () => {
    expect(classify({}, 4900).commBadge.text).toBe('SPOT OK');
    expect(classify({}, 4901).commBadge.text).toBe('SPOT STALE');
    expect(classify({ spot_source_freshness: 'stale' }).commBadge.text).toBe('SPOT STALE');
    expect(classify({ spot_poll_freshness_threshold_sec: 10 }, 9000).commBadge.text).toBe('SPOT OK');
    const cached = classify({ spot_source_freshness: 'stale', temperature_value_origin: 'cached_observation', spot_cache_status: 'reused' });
    expect(cached.temperatureBadge.text).toBe('Temp CACHED');
  });

  it.each([
    { spot_poll_status: 'future_poll' }, { spot_raw_validity: 'future_raw' },
    { spot_source_freshness: 'unknown' }, { temperature_value_origin: 'future_origin' },
    { spot_cache_status: 'future_cache' }, { temperature_status_shadow: 'future_shadow' },
    { spot_snapshot_age_ms: -1 }, { spot_snapshot_age_ms: NaN }, { spot_snapshot_age_ms: null },
    { spot_value_age_ms: -1 }, { spot_poll_freshness_threshold_sec: Infinity },
    { spot_poll_freshness_threshold_sec: 0 }, { spot_cache_expiry_threshold_sec: -1 },
    { diagnostics_available: false },
  ])('does not promote invalid diagnostics to OK: %j', (invalid) => {
    const badges = classify(invalid as Partial<SpotTemperatureHealth>);
    expect(badges.commBadge.text).toBe('SPOT UNKNOWN');
    expect(badges.temperatureBadge.text).toBe('Temp UNKNOWN');
  });

  it('uses WAIT/CONFIG for startup and UNKNOWN for absent observations/receipt', () => {
    expect(classify({ spot_poll_status: 'not_attempted', spot_snapshot_age_ms: null, spot_source_freshness: 'unknown' }).commBadge.text).toBe('SPOT WAIT');
    expect(classify({ spot_poll_status: 'config_missing' }).commBadge.text).toBe('SPOT CONFIG');
    expect(buildSpotStatusBadges({ monotonicNowMs: 0 }).commBadge.text).toBe('SPOT UNKNOWN');
    expect(buildSpotStatusBadges({ observation: freshObservation, monotonicNowMs: 0 }).commBadge.text).toBe('SPOT UNKNOWN');
  });

  it('includes delayed receipt age and API delay details without inventing a SPOT timeout', () => {
    const result = buildSpotStatusBadges({ observation: freshObservation, apiDegraded: true,
      receipt: { receivedAtMonotonicMs: 1000, ageAtReceiptMs: 6000 }, monotonicNowMs: 1000 });
    expect(result.commBadge.text).toBe('SPOT STALE');
    expect(result.commBadge.title).toContain('health API 갱신 지연');
    expect(result.temperatureBadge.title).toContain('poll success');
    expect(buildSpotStatusBadges({ observation: freshObservation,
      receipt: { receivedAtMonotonicMs: 1000, ageAtReceiptMs: null }, monotonicNowMs: 1000 }).commBadge.text).toBe('SPOT UNKNOWN');
  });
});

const config: SpotConfig = {
  image_url: '/api/spot/image.jpg',
  refresh_interval: 3,
  crosshair_x: 0.5,
  crosshair_y: 0.5,
  crosshair_color: 'lime',
  crosshair_thickness: 2,
  crosshair_size: 20,
  crosshair_gap: 5,
  widget_width: 512,
  widget_height: 288,
  focus_step: 5,
  actuator_step: 5,
  focus_enabled: true,
};

describe('getCameraStatus', () => {
  it('shows loading until the first image is displayed', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: '',
      spotImageLoading: true,
      spotImageError: null,
      spotLastSuccessAt: null,
    });
    expect(status?.type).toBe('loading');
  });

  it('returns no overlay after a successful display', () => {
    expect(
      getCameraStatus({
        spotConfig: config,
        spotImageUrl: 'blob:spot-image',
        spotImageLoading: false,
        spotImageError: null,
        spotLastSuccessAt: Date.now(),
      })
    ).toBeNull();
  });

  it('shows the image error without cache or stale severity states', () => {
    const status = getCameraStatus({
      spotConfig: config,
      spotImageUrl: 'blob:previous-image',
      spotImageLoading: false,
      spotImageError: 'SPOT 이미지 표시에 실패했습니다.',
      spotLastSuccessAt: Date.now(),
    });
    expect(status?.type).toBe('error');
    expect(status?.title).toContain('실패');
  });

  it('returns null before SPOT config is available', () => {
    expect(
      getCameraStatus({
        spotConfig: null,
        spotImageUrl: '',
        spotImageLoading: false,
        spotImageError: null,
        spotLastSuccessAt: null,
      })
    ).toBeNull();
  });
});
