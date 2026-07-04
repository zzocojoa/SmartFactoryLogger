import React, { Suspense, lazy } from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import { BrowserRouter, HashRouter, Routes, Route } from 'react-router-dom';
import { GlobalModalProvider } from './shared/context/GlobalModalContext';
import { ThemeProvider } from './shared/context/ThemeContext';
import { recordStartupEvent } from './shared/startup/startupTelemetry';

const CHUNK_RECOVERY_STORAGE_KEY = 'smartfactory_chunk_recovery_v1';
const CHUNK_RECOVERY_COOLDOWN_MS = 30000;

const readChunkRecoveryAt = (): number | null => {
  try {
    const raw = window.sessionStorage.getItem(CHUNK_RECOVERY_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = Number.parseInt(raw, 10);
    return Number.isFinite(parsed) ? parsed : null;
  } catch {
    return null;
  }
};

const writeChunkRecoveryAt = (capturedAt: number): void => {
  try {
    window.sessionStorage.setItem(CHUNK_RECOVERY_STORAGE_KEY, String(capturedAt));
  } catch {
    return;
  }
};

const isChunkImportMessage = (message: string): boolean => {
  const normalized = message.toLowerCase();
  return (
    normalized.includes('chunkloaderror') ||
    normalized.includes('failed to fetch dynamically imported module') ||
    normalized.includes('importing a module script failed') ||
    normalized.includes('loading css chunk') ||
    normalized.includes('loading chunk')
  );
};

const resolveAssetUrl = (target: EventTarget | null): string | null => {
  if (target instanceof HTMLScriptElement) {
    return target.src || null;
  }
  if (target instanceof HTMLLinkElement) {
    return target.href || null;
  }
  return null;
};

const isRecoverableAssetUrl = (value: string | null): boolean => {
  if (!value) {
    return false;
  }
  return value.includes('/assets/');
};

const triggerChunkRecovery = (reason: string): void => {
  const now = Date.now();
  const lastRecoveryAt = readChunkRecoveryAt();
  if (lastRecoveryAt !== null && now - lastRecoveryAt < CHUNK_RECOVERY_COOLDOWN_MS) {
    console.error('Index.tsx: Chunk recovery cooldown active.', reason);
    return;
  }
  writeChunkRecoveryAt(now);
  const nextUrl = new URL(window.location.href);
  nextUrl.searchParams.set('__chunk_reload', String(now));
  console.warn('Index.tsx: Triggering chunk recovery reload.', reason);
  window.location.replace(nextUrl.toString());
};

const registerChunkRecoveryHandlers = (): void => {
  window.addEventListener(
    'error',
    (event: Event) => {
      const assetUrl = resolveAssetUrl(event.target);
      if (isRecoverableAssetUrl(assetUrl)) {
        triggerChunkRecovery(assetUrl ?? 'asset-load-error');
        return;
      }
      if (assetUrl) {
        console.warn('Index.tsx: Ignoring non-recoverable asset error.', assetUrl);
      }
      const errorEvent = event as ErrorEvent;
      if (typeof errorEvent.message === 'string' && isChunkImportMessage(errorEvent.message)) {
        triggerChunkRecovery(errorEvent.message);
      }
    },
    true,
  );

  window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
    const reason = event.reason;
    const message =
      reason instanceof Error
        ? reason.message
        : typeof reason === 'string'
          ? reason
          : '';
    if (!message || !isChunkImportMessage(message)) {
      return;
    }
    event.preventDefault();
    triggerChunkRecovery(message);
  });
};

// Lazy Components
const App = lazy(() => import('./App'));
const Home = lazy(() => import('./pages/Home'));
const CustomDialog = lazy(() => import('./shared/components/CustomDialog').then(module => ({ default: module.CustomDialog })));

// Loading Fallback
const LoadingFallback = () => (
  <div style={{
    display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh',
    background: '#0f172a', color: '#94a3b8', fontSize: '1.2rem'
  }}>
    Running Smart Factory Environment...
  </div>
);

console.log("Index.tsx: Booting...");
void recordStartupEvent('renderer.index-boot', {
  route: window.location.hash || window.location.pathname,
  protocol: window.location.protocol,
});

registerChunkRecoveryHandlers();

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);
const Router = window.location.protocol === 'file:' ? HashRouter : BrowserRouter;

console.log("Index.tsx: Rendering App...");
void recordStartupEvent('renderer.index-render', {
  route: window.location.hash || window.location.pathname,
  protocol: window.location.protocol,
});
root.render(
  <React.StrictMode>
    <GlobalModalProvider>
      <ThemeProvider>
        <Router>
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/dashboard" element={<App />} />
            </Routes>
            <CustomDialog />
          </Suspense>
        </Router>
      </ThemeProvider>
    </GlobalModalProvider>
  </React.StrictMode>
);
