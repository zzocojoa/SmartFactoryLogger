import { readFileSync } from 'fs';
import { resolve } from 'path';

import { afterEach, describe, expect, it, vi } from 'vitest';

const readIndexHtml = (): string => readFileSync(resolve(process.cwd(), 'index.html'), 'utf8');

const installStartupMarkup = (): string => {
  const parsed = new DOMParser().parseFromString(readIndexHtml(), 'text/html');
  const controller = Array.from(parsed.scripts).find((script) =>
    script.textContent?.includes('var overlay = document.getElementById("sfl-startup-overlay")')
  );
  document.documentElement.innerHTML = parsed.documentElement.innerHTML;
  return controller?.textContent ?? '';
};

afterEach(() => {
  vi.useRealTimers();
  Reflect.deleteProperty(window, 'smartFactoryElectron');
  document.documentElement.innerHTML = '<head></head><body></body>';
});

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

  it('captures navigation timing fields in the inline marker', () => {
    const indexHtml = readIndexHtml();

    expect(indexHtml).toContain('getEntriesByType("navigation")');
    expect(indexHtml).toContain('navigation_response_end_to_inline_ms');
    expect(indexHtml).toContain('navigation_dom_interactive_ms');
    expect(indexHtml).not.toContain('window.location.href');
  });

  it('omits CRA-era PWA resources from the startup head', () => {
    const indexHtml = readIndexHtml();

    expect(indexHtml.match(/rel="icon"/g) ?? []).toHaveLength(1);
    expect(indexHtml).not.toContain('rel="manifest"');
    expect(indexHtml).not.toContain('apple-touch-icon');
    expect(indexHtml).not.toContain('href="/logo192.png"');
  });

  it('renders a blocking startup overlay before the app module', () => {
    const indexHtml = readIndexHtml();
    const overlayIndex = indexHtml.indexOf('id="sfl-startup-overlay"');
    const moduleEntryIndex = indexHtml.indexOf('src="/src/index.tsx"');

    expect(overlayIndex).toBeGreaterThan(-1);
    expect(overlayIndex).toBeLessThan(moduleEntryIndex);
    expect(indexHtml).toContain('src="./assets/splash.png"');
    expect(indexHtml).toContain('role="progressbar"');
    expect(indexHtml).toContain('aria-live="polite"');
    expect(indexHtml).toContain('renderer.splash-first-paint');
    expect(indexHtml).toContain('ready_strategy: "double-raf"');
  });

  it('uses only the constrained startup bridge and does not render backend logs', () => {
    const indexHtml = readIndexHtml();

    expect(indexHtml).toContain('bridge.getStartupState()');
    expect(indexHtml).toContain('bridge.onStartupStateChanged(renderState)');
    expect(indexHtml).toContain('runAction(bridge.retryStartup)');
    expect(indexHtml).toContain('runAction(bridge.continueStartupOffline)');
    expect(indexHtml).toContain('runAction(bridge.exitStartup)');
    expect(indexHtml).toContain('message.textContent = state.message');
    expect(indexHtml).not.toContain('Backend STDOUT');
    expect(indexHtml).not.toContain('Backend STDERR');
    expect(indexHtml).not.toContain('innerHTML = state');
  });

  it('subscribes before snapshot, rejects stale state, and cleans up after handoff', async () => {
    vi.useFakeTimers();
    const controllerSource = installStartupMarkup();
    const listeners: Array<(state: unknown) => void> = [];
    const snapshotResolvers: Array<(state: unknown) => void> = [];
    const unsubscribe = vi.fn();
    const bridge = {
      getStartupState: vi.fn(() => new Promise((resolve) => {
        snapshotResolvers.push(resolve);
      })),
      onStartupStateChanged: vi.fn((nextListener: (state: unknown) => void) => {
        listeners.push(nextListener);
        return unsubscribe;
      }),
      retryStartup: vi.fn(),
      continueStartupOffline: vi.fn(),
      exitStartup: vi.fn(),
    };
    Object.defineProperty(window, 'smartFactoryElectron', {
      configurable: true,
      value: bridge,
    });
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      callback(0);
      return 1;
    });

    new Function('window', 'document', controllerSource)(window, document);
    expect(bridge.onStartupStateChanged).toHaveBeenCalledBefore(bridge.getStartupState);

    listeners[0]({
      schema_version: 'electron-startup-state-v1',
      sequence: 5,
      status: 'timeout',
      progress: 80,
      phase: 'startup_timeout',
      message: 'timeout',
      can_retry: true,
      can_continue_offline: true,
      can_exit: true,
    });
    snapshotResolvers[0]({
      schema_version: 'electron-startup-state-v1',
      sequence: 4,
      status: 'loading',
      progress: 30,
      phase: 'stale',
      message: 'stale',
    });
    await Promise.resolve();
    expect(document.getElementById('sfl-startup-message')?.textContent).toBe('timeout');
    expect((document.getElementById('sfl-startup-actions') as HTMLElement).hidden).toBe(false);

    listeners[0]({
      schema_version: 'electron-startup-state-v1',
      sequence: 6,
      status: 'ready',
      progress: 100,
      phase: 'ready',
      message: 'ready',
    });
    vi.runAllTimers();
    expect((document.getElementById('sfl-startup-overlay') as HTMLElement).hidden).toBe(true);
    expect((document.getElementById('root') as HTMLElement).inert).toBe(false);
    expect(unsubscribe).toHaveBeenCalledTimes(1);
  });

  it('dismisses the static overlay when the Electron bridge is unavailable', () => {
    const controllerSource = installStartupMarkup();
    new Function('window', 'document', controllerSource)(window, document);

    expect((document.getElementById('sfl-startup-overlay') as HTMLElement).hidden).toBe(true);
    expect((document.getElementById('root') as HTMLElement).inert).toBe(false);
  });
});
