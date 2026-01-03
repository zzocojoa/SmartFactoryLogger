import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import { initScenesRuntime } from './scenes/ScenesRuntime';

console.log("Index.tsx: Booting...");

initScenesRuntime();
console.log("Index.tsx: Scenes Runtime Initialized.");

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

console.log("Index.tsx: Rendering App...");
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

reportWebVitals();
