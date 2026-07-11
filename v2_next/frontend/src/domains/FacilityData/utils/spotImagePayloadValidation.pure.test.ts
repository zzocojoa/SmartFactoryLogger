import { describe, expect, it } from 'vitest';
import type { SpotImageResponseMetadata } from '../api/spotService.types';
import {
  SpotImagePayloadValidationError,
  isSpotImagePayloadRejectionCode,
  validateSpotImagePayload,
} from './spotImagePayloadValidation.pure';

const RECEIVED_AT = 1_700_000_005_000;

const metadata = (): SpotImageResponseMetadata => ({
  source: 'upstream',
  captured_at: RECEIVED_AT - 10,
  received_at: RECEIVED_AT,
  latency_ms: 10,
});

const jpegBytes = (): Uint8Array => {
  const bytes = new Uint8Array(20);
  bytes[0] = 0xff;
  bytes[1] = 0xd8;
  bytes[18] = 0xff;
  bytes[19] = 0xd9;
  return bytes;
};

const validate = (bytes: Uint8Array, headers: Headers = new Headers({ 'content-type': 'image/jpeg' })) =>
  validateSpotImagePayload({
    bytes,
    status: 200,
    headers,
    metadata: metadata(),
    receivedAt: RECEIVED_AT,
    requestUrl: '/api/spot/image.jpg',
  });

describe('SPOT JPEG payload validation', () => {
  it('accepts a JPEG response from the official image bridge', () => {
    const result = validate(jpegBytes());
    expect(result.format).toBe('jpeg');
    expect(result.mimeType).toBe('image/jpeg');
    expect(result.capturedAt).toBe(RECEIVED_AT - 10);
  });

  it('rejects PNG because the SPOT guide image resource is JPEG', () => {
    const png = new Uint8Array(20);
    png.set([0x89, 0x50, 0x4e, 0x47]);
    expect(() => validate(png, new Headers({ 'content-type': 'image/png' }))).toThrow(
      SpotImagePayloadValidationError
    );
  });

  it('rejects an HTML response', () => {
    const html = new TextEncoder().encode('<!doctype html><body>not jpeg</body>');
    expect(() => validate(html, new Headers({ 'content-type': 'text/html' }))).toThrow(
      SpotImagePayloadValidationError
    );
  });

  it('rejects a mismatched content length', () => {
    expect(() =>
      validate(jpegBytes(), new Headers({ 'content-type': 'image/jpeg', 'content-length': '99' }))
    ).toThrow(SpotImagePayloadValidationError);
  });

  it('requires a request URL for audit logging', () => {
    expect(() =>
      validateSpotImagePayload({
        bytes: jpegBytes(),
        status: 200,
        headers: new Headers({ 'content-type': 'image/jpeg' }),
        metadata: metadata(),
        receivedAt: RECEIVED_AT,
        requestUrl: '',
      })
    ).toThrow(SpotImagePayloadValidationError);
  });

  it('recognizes only backend payload rejection codes', () => {
    expect(isSpotImagePayloadRejectionCode('invalid-image-html')).toBe(true);
    expect(isSpotImagePayloadRejectionCode('empty-body')).toBe(true);
    expect(isSpotImagePayloadRejectionCode('upstream-timeout')).toBe(false);
  });
});
