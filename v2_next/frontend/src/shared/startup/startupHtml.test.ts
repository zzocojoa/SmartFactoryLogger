import { readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

const readIndexHtml = (): string => readFileSync(resolve(process.cwd(), 'index.html'), 'utf8');

describe('startup HTML telemetry marker', () => {
  it('runs before the retained favicon and the app module entry', () => {
    const indexHtml = readIndexHtml();

    const markerIndex = indexHtml.indexOf('renderer.index-html-inline-script');
    const faviconIndex = indexHtml.indexOf('rel="icon" href="/favicon.ico"');
    const moduleEntryIndex = indexHtml.indexOf('src="/src/index.tsx"');

    expect(markerIndex).toBeGreaterThan(-1);
    expect(faviconIndex).toBeGreaterThan(-1);
    expect(moduleEntryIndex).toBeGreaterThan(-1);
    expect(markerIndex).toBeLessThan(faviconIndex);
    expect(markerIndex).toBeLessThan(moduleEntryIndex);
  });

  it('omits CRA-era PWA resources from the startup head', () => {
    const indexHtml = readIndexHtml();

    expect(indexHtml.match(/rel="icon"/g) ?? []).toHaveLength(1);
    expect(indexHtml).not.toContain('rel="manifest"');
    expect(indexHtml).not.toContain('apple-touch-icon');
    expect(indexHtml).not.toContain('href="/logo192.png"');
  });
});
