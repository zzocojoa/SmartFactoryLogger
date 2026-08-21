import { describe, expect, it } from 'vitest';
import { buildSpotImageUrl } from './spotService.mapper';

describe('SPOT image route mapping', () => {
  it('uses the budgeted operator-live application route', () => {
    expect(buildSpotImageUrl('http://127.0.0.1:8000')).toBe(
      'http://127.0.0.1:8000/api/spot/live_image.jpg'
    );
  });

  it('keeps the snapshot route as a compatibility fallback and rejects unknown paths', () => {
    expect(buildSpotImageUrl('', '/api/spot/image.jpg')).toBe('/api/spot/image.jpg');
    expect(buildSpotImageUrl('', 'https://example.invalid/image.jpg')).toBe(
      '/api/spot/live_image.jpg'
    );
  });
});
