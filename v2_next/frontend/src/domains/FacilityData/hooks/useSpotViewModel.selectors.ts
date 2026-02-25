export const resolveSpotRefreshMs = (refreshIntervalSec: number): number => {
  return Math.max(500, Math.round(refreshIntervalSec * 1000));
};

export const resolveSpotImageErrorMessage = (): string => '?대?吏 ?섏떊 ?ㅽ뙣';

export const resolveSpotImageLoadErrorMessage = (): string => '?대?吏 濡쒕뱶 ?ㅽ뙣';

export const resolveEffectiveSpotImageAt = (
  capturedAtHeader: string | null,
  ageHeader: string | null,
  receivedAt: number
): number => {
  const capturedAt = capturedAtHeader ? Number(capturedAtHeader) : NaN;
  const ageSec = ageHeader ? Number(ageHeader) : NaN;
  if (Number.isFinite(ageSec)) {
    return receivedAt - Math.max(0, ageSec * 1000);
  }
  if (Number.isFinite(capturedAt)) {
    return capturedAt;
  }
  return receivedAt;
};
