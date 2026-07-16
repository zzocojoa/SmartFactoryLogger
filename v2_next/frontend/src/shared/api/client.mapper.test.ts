import { describe, expect, it } from 'vitest';

import { resolveApiBaseUrl } from './client.mapper';

describe('resolveApiBaseUrl', () => {
  it('preserves an explicit environment override', () => {
    expect(
      resolveApiBaseUrl('https://example.invalid', { protocol: 'file:' }, true)
    ).toBe('https://example.invalid');
  });

  it('uses the IPv4 loopback address for the packaged file protocol', () => {
    expect(resolveApiBaseUrl(undefined, { protocol: 'file:' }, true)).toBe(
      'http://127.0.0.1:8000'
    );
  });

  it('normalizes the non-window localhost fallback to IPv4 loopback', () => {
    expect(
      resolveApiBaseUrl(
        undefined,
        { protocol: 'http:', origin: 'http://localhost:8000' },
        false
      )
    ).toBe('http://127.0.0.1:8000');
  });

  it('keeps browser-hosted development requests relative', () => {
    expect(
      resolveApiBaseUrl(
        undefined,
        { protocol: 'http:', origin: 'http://localhost:3000' },
        true
      )
    ).toBe('');
  });
});
