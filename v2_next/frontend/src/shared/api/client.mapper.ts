import type { RuntimeLikeLocation } from './client.types';

const PACKAGED_API_BASE_URL = 'http://127.0.0.1:8000';

export function resolveApiBaseUrl(
  envBaseUrl: string | undefined,
  loc: RuntimeLikeLocation,
  hasWindow: boolean
): string {
  if (envBaseUrl) {
    return envBaseUrl;
  }

  if (loc.protocol === 'file:') {
    return PACKAGED_API_BASE_URL;
  }

  if (!hasWindow && loc.origin && loc.origin.includes('localhost:8000')) {
    return PACKAGED_API_BASE_URL;
  }

  return '';
}
