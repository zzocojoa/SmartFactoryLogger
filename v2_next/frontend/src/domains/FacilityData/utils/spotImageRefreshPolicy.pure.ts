export const DEFAULT_SPOT_IMAGE_REFRESH_INTERVAL_SECONDS = 3;
export const MIN_SPOT_IMAGE_REFRESH_INTERVAL_SECONDS = 1;
export const MAX_SPOT_IMAGE_REFRESH_INTERVAL_SECONDS = 10;
export const MIN_SPOT_OPERATOR_IMAGE_REFRESH_INTERVAL_SECONDS = 0.25;

export const normalizeSpotImageRefreshIntervalSeconds = (
  configuredInterval: unknown
): number => {
  if (
    typeof configuredInterval !== 'number' ||
    !Number.isFinite(configuredInterval) ||
    configuredInterval <= 0
  ) {
    return DEFAULT_SPOT_IMAGE_REFRESH_INTERVAL_SECONDS;
  }

  return Math.min(
    MAX_SPOT_IMAGE_REFRESH_INTERVAL_SECONDS,
    Math.max(MIN_SPOT_IMAGE_REFRESH_INTERVAL_SECONDS, configuredInterval)
  );
};

export const resolveSpotImageRefreshIntervalMs = (configuredInterval: unknown): number =>
  normalizeSpotImageRefreshIntervalSeconds(configuredInterval) * 1_000;

export const resolveSpotOperatorImageRefreshIntervalMs = (
  serverInterval: unknown,
  fallbackConfiguredInterval: unknown
): number => {
  if (
    typeof serverInterval === 'number' &&
    Number.isFinite(serverInterval) &&
    serverInterval > 0
  ) {
    return Math.max(MIN_SPOT_OPERATOR_IMAGE_REFRESH_INTERVAL_SECONDS, serverInterval) * 1_000;
  }
  return resolveSpotImageRefreshIntervalMs(fallbackConfiguredInterval);
};
