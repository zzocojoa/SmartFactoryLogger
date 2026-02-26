import React, { Suspense, lazy } from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { initScenesRuntime } from './scenes/ScenesRuntime';
import { GlobalModalProvider } from './shared/context/GlobalModalContext';
import { ThemeProvider } from './shared/context/ThemeContext';

// Lazy Components
const App = lazy(() => import('./App'));
const Home = lazy(() => import('./pages/Home'));
const MesDashboard = lazy(() => import('./pages/MesDashboard').then(module => ({ default: module.MesDashboard })));
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

initScenesRuntime();
console.log("Index.tsx: Scenes Runtime Initialized.");

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

console.log("Index.tsx: Rendering App...");
root.render(
  <React.StrictMode>
    <GlobalModalProvider>
      <ThemeProvider>
        <BrowserRouter>
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/dashboard" element={<App />} />
              <Route path="/mes-dashboard" element={<MesDashboard />} />
            </Routes>
            <CustomDialog />
          </Suspense>
        </BrowserRouter>
      </ThemeProvider>
    </GlobalModalProvider>
  </React.StrictMode>
);
