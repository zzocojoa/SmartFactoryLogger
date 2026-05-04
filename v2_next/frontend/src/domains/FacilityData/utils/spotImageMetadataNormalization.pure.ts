const MAX_CAPTURE_AGE_SEC = 60 * 60;
const MAX_CAPTURED_AT_SEC = 1_000_000_000_000;

const parseFiniteNumber = (rawValue: string | null): number | null => {
  if (rawValue === null) {
    return null;
  }
  const normalizedValue = rawValue.trim();
  if (normalizedValue === '') {
    return null;
  }
  const parsedValue = Number(normalizedValue);
  return Number.isFinite(parsedValue) ? parsedValue : null;
};

export const normalizeSpotImageAgeSec = (rawAgeSec: string | null): number | null => {
  const parsedAgeSec = parseFiniteNumber(rawAgeSec);
  if (parsedAgeSec === null || parsedAgeSec < 0) {
    return null;
  }
  if (parsedAgeSec <= MAX_CAPTURE_AGE_SEC) {
    return parsedAgeSec;
  }
  if (parsedAgeSec > MAX_CAPTURE_AGE_SEC && parsedAgeSec <= MAX_CAPTURE_AGE_SEC * 1000) {
    return parsedAgeSec / 1000;
  }
  return null;
};

export const normalizeSpotImageCapturedAt = (rawCapturedAt: string | null): number | null => {
  const parsedCapturedAt = parseFiniteNumber(rawCapturedAt);
  if (parsedCapturedAt === null || parsedCapturedAt < 0) {
    return null;
  }
  if (parsedCapturedAt > MAX_CAPTURED_AT_SEC) {
    return parsedCapturedAt;
  }
  return parsedCapturedAt * 1000;
};
