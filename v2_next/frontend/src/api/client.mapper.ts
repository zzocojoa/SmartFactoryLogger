import type { RuntimeLikeLocation } from './client.types';

export function resolveApiBaseUrl(
  envBaseUrl: string | undefined,
  loc: RuntimeLikeLocation,
  hasWindow: boolean
): string {
  if (envBaseUrl) {
    return envBaseUrl;
  }

  if (loc.protocol === 'file:') {
    return 'http://localhost:8000';
  }

  if (!hasWindow && loc.origin && loc.origin.includes('localhost:8000')) {
    return 'http://localhost:8000';
  }

  return '';
}
