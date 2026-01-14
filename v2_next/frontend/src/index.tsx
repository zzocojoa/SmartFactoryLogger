import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import Home from './pages/Home';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { initScenesRuntime } from './scenes/ScenesRuntime';
import { GlobalModalProvider } from './GlobalModalContext';
import { CustomDialog } from './components/CustomDialog';
import { ThemeProvider } from './ThemeContext';

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
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/dashboard" element={<App />} />
          </Routes>
        </BrowserRouter>
        <CustomDialog />
      </ThemeProvider>
    </GlobalModalProvider>
  </React.StrictMode>
);

