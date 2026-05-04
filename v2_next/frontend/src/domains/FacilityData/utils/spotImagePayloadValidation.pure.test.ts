import type { SpotImageResponseMetadata } from '../api/spotService.types';
import {
  SpotImagePayloadValidationCode,
  SpotImagePayloadValidationError,
  validateSpotImagePayload,
} from './spotImagePayloadValidation.pure';

const createMetadata = (overrides: Partial<SpotImageResponseMetadata> = {}): SpotImageResponseMetadata => {
  return {
    status: 'ok',
    raw_status: 'ok',
    cache_status: 'fresh',
    raw_cache_status: 'fresh',
    proxy_state: 'ok',
    raw_proxy_state: 'ok',
    source: 'camera',
    age_sec: 4,
    max_stale_age_sec: 60,
    captured_at: 1_700_000_004_000,
    retry_after_sec: null,
    received_at: 1_700_000_004_120,
    latency_ms: 12,
    ...overrides,
  };
};

const makePaddedPayload = (body: number[], minLength = 32): Uint8Array => {
  const nextBody = [...body];
  while (nextBody.length < minLength) {
    nextBody.push(0);
  }
  return new Uint8Array(nextBody);
};

const createValidJpegBytes = (length = 16): Uint8Array => {
  const bytes = new Uint8Array(Math.max(length, 16));
  bytes[0] = 0xff;
  bytes[1] = 0xd8;
  bytes[bytes.length - 2] = 0xff;
  bytes[bytes.length - 1] = 0xd9;
  return bytes;
};

const toBytes = (value: string): Uint8Array =>
  Uint8Array.from(value.split('').map((char) => char.charCodeAt(0)));
const buildHeaders = (contentType: string | null, contentLength: number | null): Headers => {
  const headers = new Headers({
    'X-Spot-Image-Age': '4',
  });
  if (contentType !== null) {
    headers.set('content-type', contentType);
  }
  if (contentLength !== null) {
    headers.set('content-length', String(contentLength));
  }
  return headers;
};

const expectPayloadValidationError = ({
  bytes,
  status,
  headers,
  metadata,
  requestUrl,
  receivedAt,
  expectedCode,
  expectedMessagePart,
}: {
  bytes: Uint8Array;
  status: number;
  headers: Headers;
  metadata: SpotImageResponseMetadata;
  requestUrl: string;
  receivedAt: number;
  expectedCode: SpotImagePayloadValidationCode;
  expectedMessagePart: string;
}): void => {
  try {
    validateSpotImagePayload({
      bytes,
      status,
      headers,
      metadata,
      requestUrl,
      receivedAt,
    });
  } catch (error) {
    const validationError = error as SpotImagePayloadValidationError;
    expect(validationError.code).toBe(expectedCode);
    expect(validationError.message).toContain(expectedMessagePart);
    return;
  }
  throw new Error('Expected SpotImagePayloadValidationError');
};

describe('validateSpotImagePayload', () => {
  const receivedAt = 1_700_000_004_120;
  it('accepts a valid jpeg payload', () => {
    const bytes = createValidJpegBytes();
    const headers = buildHeaders('image/jpeg', bytes.length);
    const metadata = createMetadata();
    const result = validateSpotImagePayload({
      bytes,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
    });
    expect(result.format).toBe('jpeg');
    expect(result.mimeType).toBe('image/jpeg');
    expect(result.byteLength).toBe(bytes.length);
  });

  it('accepts a valid png payload', () => {
    const bytes = makePaddedPayload([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00], 40);
    const headers = buildHeaders('image/png', bytes.length);
    const metadata = createMetadata({ captured_at: 1_700_000_004_116 });
    const result = validateSpotImagePayload({
      bytes,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
    });
    expect(result.format).toBe('png');
    expect(result.ageSec).toBe(4);
  });

  it('accepts a valid gif payload and falls back to format signature', () => {
    const bytes = makePaddedPayload([0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 0x00, 0x00], 32);
    const headers = buildHeaders(null, bytes.length);
    const metadata = createMetadata({ age_sec: null, captured_at: 1_700_000_004_110 });
    const result = validateSpotImagePayload({
      bytes,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
    });
    expect(result.format).toBe('gif');
    expect(result.mimeType).toBe('image/gif');
  });

  it('accepts image age header in milliseconds', () => {
    const bytes = createValidJpegBytes();
    const headers = buildHeaders('image/jpeg', bytes.length);
    const metadata = createMetadata({
      age_sec: 15_000,
      captured_at: null,
    });
    const result = validateSpotImagePayload({
      bytes,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
    });
    expect(result.ageSec).toBe(15);
  });

  it('rejects plain text payload as non-image', () => {
    const bytes = makePaddedPayload(Array.from(toBytes('<plain>not an image</plain>')), 32);
    const headers = buildHeaders('text/plain', bytes.length);
    const metadata = createMetadata();
    expectPayloadValidationError({
      bytes,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
      expectedCode: 'invalid-image-format',
      expectedMessagePart: 'Payload does not match',
    });
  });

  it('rejects tiny payloads', () => {
    const bytes = new Uint8Array([0xff, 0xd8, 0xd9]);
    const headers = buildHeaders('image/jpeg', bytes.length);
    const metadata = createMetadata();
    expectPayloadValidationError({
      bytes,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
      expectedCode: 'invalid-size',
      expectedMessagePart: 'Payload length is',
    });
  });

  it('rejects content-length mismatch', () => {
    const bytes = makePaddedPayload([0xff, 0xd8, 0x11, 0x22, 0xff, 0xd9], 32);
    const headers = buildHeaders('image/jpeg', bytes.length - 1);
    const metadata = createMetadata();
    expectPayloadValidationError({
      bytes,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
      expectedCode: 'invalid-array-length',
      expectedMessagePart: 'Content-Length mismatch',
    });
  });

  it('rejects html payload even with binary prefix', () => {
    const bytes = makePaddedPayload([0xff, 0xd8, 0x11, 0x22, ...Array.from(toBytes('<html><body>oops</body></html>'))], 48);
    const headers = buildHeaders('text/html', bytes.length);
    const metadata = createMetadata();
    expectPayloadValidationError({
      bytes,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
      expectedCode: 'invalid-image-format',
      expectedMessagePart: 'Payload looks like HTML',
    });
  });

  it('rejects payloads with future timestamp', () => {
    const bytes = createValidJpegBytes();
    const headers = buildHeaders('image/jpeg', bytes.length);
    const metadata = createMetadata({ captured_at: 1_700_000_094_120, age_sec: 0 });
    expectPayloadValidationError({
      bytes,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
      expectedCode: 'invalid-timestamp',
      expectedMessagePart: 'future',
    });
  });

  it('rejects non-bytes payload input', () => {
    const metadata = createMetadata();
    const headers = buildHeaders('image/jpeg', 16);
    expectPayloadValidationError({
      bytes: null as unknown as Uint8Array,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
      expectedCode: 'invalid-type',
      expectedMessagePart: 'Payload type must be Uint8Array',
    });
  });

  it('rejects age timestamp inconsistency', () => {
    const bytes = createValidJpegBytes();
    const headers = buildHeaders('image/jpeg', bytes.length);
    const metadata = createMetadata({ age_sec: 0, captured_at: 1_699_999_998_120 });
    expectPayloadValidationError({
      bytes,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
      expectedCode: 'invalid-timestamp',
      expectedMessagePart: 'inconsistent',
    });
  });

  it('rejects missing image timing metadata', () => {
    const bytes = createValidJpegBytes();
    const headers = buildHeaders('image/jpeg', bytes.length);
    const metadata = createMetadata({ age_sec: null, captured_at: null });
    expectPayloadValidationError({
      bytes,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
      expectedCode: 'invalid-timestamp',
      expectedMessagePart: 'Both',
    });
  });

  it('rejects unsupported content type', () => {
    const bytes = createValidJpegBytes();
    const headers = buildHeaders('application/json', bytes.length);
    const metadata = createMetadata();
    expectPayloadValidationError({
      bytes,
      status: 200,
      headers,
      metadata,
      requestUrl: '/spot-image',
      receivedAt,
      expectedCode: 'invalid-mime-type',
      expectedMessagePart: 'Unsupported content type',
    });
  });
});
