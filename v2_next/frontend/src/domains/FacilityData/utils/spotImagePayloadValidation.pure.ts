import type { SpotImageResponseMetadata } from '../api/spotService.types';
import { normalizeSpotImageAgeSec, normalizeSpotImageCapturedAt } from './spotImageMetadataNormalization.pure';

export type SpotImagePayloadValidationCode =
  | 'invalid-type'
  | 'invalid-size'
  | 'invalid-array-length'
  | 'invalid-image-format'
  | 'invalid-mime-type'
  | 'invalid-timestamp'
  | 'backend-payload-rejection';

export interface SpotImagePayloadValidationContext {
  requestUrl: string;
  status: number;
  contentType: string | null;
  contentLength: number | null;
  byteLength: number;
  declaredAgeSec: number | null;
  declaredCapturedAt: number | null;
}

export interface SpotImagePayloadValidationInput {
  bytes: Uint8Array | null | undefined;
  status: number;
  headers: Headers;
  metadata: SpotImageResponseMetadata;
  receivedAt: number;
  requestUrl: string;
}

export interface SpotImagePayloadValidationLog {
  event: 'spot_image_payload_rejected';
  area: 'spot-image';
  code: SpotImagePayloadValidationCode;
  reason: string;
  requestUrl: string;
  responseStatus: number;
  contentType: string | null;
  contentLengthHeader: number | null;
  byteLength: number;
  declaredAgeSec: number | null;
  declaredCapturedAt: number | null;
}

export interface SpotImagePayloadValidated {
  bytes: Uint8Array;
  byteLength: number;
  mimeType: string;
  format: 'jpeg' | 'png' | 'gif' | 'webp' | 'bmp';
  ageSec: number;
  capturedAt: number;
}

export class SpotImagePayloadValidationError extends Error {
  public readonly code: SpotImagePayloadValidationCode;
  public readonly context: SpotImagePayloadValidationContext;

  constructor(code: SpotImagePayloadValidationCode, context: SpotImagePayloadValidationContext, reason: string) {
    super(reason);
    this.name = 'SpotImagePayloadValidationError';
    this.code = code;
    this.context = context;
  }
}

const MIN_IMAGE_BYTES = 16;
const MAX_IMAGE_BYTES = 15_728_640;
const MAX_CLOCK_DRIFT_MS = 60_000;
const MILLISECONDS_PER_SECOND = 1000;

const ALLOWED_MIME_TYPES = new Set([
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/gif',
  'image/webp',
  'image/bmp',
  'image/x-ms-bmp',
]);

const FORMAT_TO_MIME: Record<string, string> = {
  jpeg: 'image/jpeg',
  png: 'image/png',
  gif: 'image/gif',
  webp: 'image/webp',
  bmp: 'image/bmp',
};

const parseFloatHeader = (rawValue: string | null): number | null => {
  if (rawValue === null) {
    return null;
  }
  const trimmed = rawValue.trim();
  if (trimmed === '') {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
};

const parseContentType = (rawContentType: string | null): string | null => {
  if (rawContentType === null) {
    return null;
  }
  const trimmed = rawContentType.trim().toLowerCase();
  if (trimmed === '') {
    return null;
  }
  return trimmed.split(';', 1)[0];
};

const parseContentLength = (headers: Headers): number | null => {
  return parseFloatHeader(headers.get('content-length'));
};

const parseAgeSec = (ageSec: number | null): number | null => {
  if (ageSec === null || !Number.isFinite(ageSec) || ageSec < 0) {
    return null;
  }
  const normalizedAgeSec = normalizeSpotImageAgeSec(ageSec.toString());
  return normalizedAgeSec === null ? ageSec / MILLISECONDS_PER_SECOND : normalizedAgeSec;
};

const isValidContentLength = (contentLength: number): boolean => {
  return Number.isInteger(contentLength) && contentLength >= 0;
};

const isLikelyHtml = (bytes: Uint8Array): boolean => {
  const byteCount = Math.min(bytes.length, 256);
  let prefix = '';
  for (let index = 0; index < byteCount; index += 1) {
    const value = bytes[index];
    if (value === 0x09 || value === 0x0a || value === 0x0d || value === 0x20) {
      prefix += String.fromCharCode(value);
      continue;
    }
    if (value >= 0x20 && value <= 0x7e) {
      prefix += String.fromCharCode(value);
      continue;
    }
    prefix += ' ';
  }
  prefix = prefix.toLowerCase().trim();
  if (prefix === '') {
    return false;
  }
  return (
    prefix.startsWith('<!doctype html') ||
    prefix.startsWith('<html') ||
    prefix.includes('<head') ||
    prefix.includes('<body')
  );
};

const detectImageFormat = (bytes: Uint8Array): 'jpeg' | 'png' | 'gif' | 'webp' | 'bmp' | null => {
  if (bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xd8) {
    return bytes.length >= 4 && bytes[bytes.length - 2] === 0xff && bytes[bytes.length - 1] === 0xd9
      ? 'jpeg'
      : null;
  }
  if (bytes.length >= 8 && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47) {
    return 'png';
  }
  if (
    bytes.length >= 6 &&
    bytes[0] === 0x47 &&
    bytes[1] === 0x49 &&
    bytes[2] === 0x46 &&
    bytes[3] === 0x38 &&
    (bytes[4] === 0x39 || bytes[4] === 0x37) &&
    bytes[5] === 0x61
  ) {
    return 'gif';
  }
  if (
    bytes.length >= 12 &&
    bytes[0] === 0x52 &&
    bytes[1] === 0x49 &&
    bytes[2] === 0x46 &&
    bytes[3] === 0x46 &&
    bytes[8] === 0x57 &&
    bytes[9] === 0x45 &&
    bytes[10] === 0x42 &&
    bytes[11] === 0x50
  ) {
    return 'webp';
  }
  if (bytes.length >= 2 && bytes[0] === 0x42 && bytes[1] === 0x4d) {
    return 'bmp';
  }
  return null;
};

const buildValidationContext = (
  requestUrl: string,
  status: number,
  headers: Headers,
  metadata: SpotImageResponseMetadata,
  byteLength: number
): SpotImagePayloadValidationContext => {
  return {
    requestUrl,
    status,
    contentType: parseContentType(headers.get('content-type')),
    contentLength: parseContentLength(headers),
    byteLength,
    declaredAgeSec: metadata.age_sec,
    declaredCapturedAt: metadata.captured_at,
  };
};

const resolveAge = (ageSec: number | null, capturedAt: number | null, receivedAt: number): number | null => {
  if (ageSec !== null) {
    return Math.max(0, ageSec);
  }
  if (capturedAt !== null) {
    return Math.max(0, (receivedAt - capturedAt) / 1000);
  }
  return null;
};

export const isSpotImagePayloadProxyRejectionCode = (code: string | null | undefined): boolean => {
  return code === 'invalid-image-payload' || code === 'invalid-image-html' || code === 'empty-body';
};

export const buildSpotImageValidationLog = (error: SpotImagePayloadValidationError): SpotImagePayloadValidationLog => {
  return {
    event: 'spot_image_payload_rejected',
    area: 'spot-image',
    code: error.code,
    reason: error.message,
    requestUrl: error.context.requestUrl,
    responseStatus: error.context.status,
    contentType: error.context.contentType,
    contentLengthHeader: error.context.contentLength,
    byteLength: error.context.byteLength,
    declaredAgeSec: error.context.declaredAgeSec,
    declaredCapturedAt: error.context.declaredCapturedAt,
  };
};

export const toPayloadRejectionValidationCode = (detailCode: string | null | undefined): SpotImagePayloadValidationCode => {
  if (detailCode === 'invalid-image-html') {
    return 'invalid-image-format';
  }
  if (detailCode === 'invalid-image-payload') {
    return 'invalid-image-format';
  }
  return 'backend-payload-rejection';
};

export const validateSpotImagePayload = ({
  bytes,
  status,
  headers,
  metadata,
  receivedAt,
  requestUrl,
}: SpotImagePayloadValidationInput): SpotImagePayloadValidated => {
  if (!requestUrl.trim()) {
    const context = buildValidationContext(requestUrl, status, headers, metadata, bytes?.length ? bytes.length : 0);
    throw new SpotImagePayloadValidationError(
      'invalid-type',
      context,
      'requestUrl is required for validation logging'
    );
  }

  if (!Number.isFinite(receivedAt) || receivedAt <= 0) {
    const context = buildValidationContext(requestUrl, status, headers, metadata, bytes?.length ? bytes.length : 0);
    throw new SpotImagePayloadValidationError(
      'invalid-timestamp',
      context,
      `Invalid response timestamp: ${receivedAt}`
    );
  }

  if (!(bytes instanceof Uint8Array)) {
    const context = buildValidationContext(requestUrl, status, headers, metadata, 0);
    throw new SpotImagePayloadValidationError('invalid-type', context, 'Payload type must be Uint8Array');
  }

  if (bytes.byteLength < MIN_IMAGE_BYTES || bytes.byteLength > MAX_IMAGE_BYTES) {
    const context = buildValidationContext(requestUrl, status, headers, metadata, bytes.byteLength);
    throw new SpotImagePayloadValidationError(
      'invalid-size',
      context,
      `Payload length is ${bytes.byteLength} bytes`
    );
  }

  const contentLength = parseContentLength(headers);
  const rawContentLength = headers.get('content-length');
  if (rawContentLength !== null && (contentLength === null || !isValidContentLength(contentLength))) {
    const context = buildValidationContext(requestUrl, status, headers, metadata, bytes.byteLength);
    throw new SpotImagePayloadValidationError(
      'invalid-array-length',
      context,
      `Invalid Content-Length header: ${rawContentLength}`
    );
  }

  if (contentLength !== null && contentLength >= 0 && contentLength !== bytes.byteLength) {
    const context = buildValidationContext(requestUrl, status, headers, metadata, bytes.byteLength);
    throw new SpotImagePayloadValidationError(
      'invalid-array-length',
      context,
      `Content-Length mismatch: header=${contentLength}, actual=${bytes.byteLength}`
    );
  }

  const format = detectImageFormat(bytes);
  if (format === null) {
    const context = buildValidationContext(requestUrl, status, headers, metadata, bytes.byteLength);
    if (isLikelyHtml(bytes)) {
      throw new SpotImagePayloadValidationError(
        'invalid-image-format',
        context,
        'Payload looks like HTML instead of image bytes'
      );
    }
    throw new SpotImagePayloadValidationError(
      'invalid-image-format',
      context,
      'Payload does not match supported image signature'
    );
  }

  const contentType = parseContentType(headers.get('content-type'));
  if (contentType !== null && !ALLOWED_MIME_TYPES.has(contentType)) {
    const context = buildValidationContext(requestUrl, status, headers, metadata, bytes.byteLength);
    throw new SpotImagePayloadValidationError(
      'invalid-mime-type',
      context,
      `Unsupported content type: ${contentType}`
    );
  }

  const normalizedAgeSec = parseAgeSec(metadata.age_sec);
  const normalizedCapturedAt = metadata.captured_at === null ? null : normalizeSpotImageCapturedAt(metadata.captured_at.toString());
  if (normalizedAgeSec === null && normalizedCapturedAt === null) {
    const context = buildValidationContext(requestUrl, status, headers, metadata, bytes.byteLength);
    throw new SpotImagePayloadValidationError(
      'invalid-timestamp',
      context,
      'Both X-Spot-Image-Age and X-Spot-Image-At are missing or invalid'
    );
  }

  const ageSec = resolveAge(normalizedAgeSec, normalizedCapturedAt, receivedAt);
  if (ageSec === null) {
    const context = buildValidationContext(requestUrl, status, headers, metadata, bytes.byteLength);
    throw new SpotImagePayloadValidationError(
      'invalid-timestamp',
      context,
      'Unable to resolve image timestamp metadata'
    );
  }

  const capturedAt =
    normalizedCapturedAt !== null
      ? normalizedCapturedAt
      : receivedAt - ageSec * 1000;
  if (capturedAt > receivedAt + MAX_CLOCK_DRIFT_MS) {
    const context = buildValidationContext(requestUrl, status, headers, metadata, bytes.byteLength);
    throw new SpotImagePayloadValidationError(
      'invalid-timestamp',
      context,
      `Captured timestamp is too far in the future: ${capturedAt}`
    );
  }

  return {
    bytes,
    byteLength: bytes.byteLength,
    mimeType: contentType ?? FORMAT_TO_MIME[format],
    format,
    ageSec,
    capturedAt,
  };
};
