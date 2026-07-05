const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const kill = require('tree-kill');
const fs = require('fs');
const v8 = require('v8');

const startupOriginNs = process.hrtime.bigint();
const STARTUP_RENDERER_EVENT_NAMES = new Set([
  'renderer.index-boot',
  'renderer.index-render',
  'renderer.app-import-start',
  'renderer.app-module-evaluated',
  'renderer.app-import-end',
  'renderer.app-render-start',
  'renderer.polling-interval-resolved',
  'renderer.app-render-end',
  'renderer.native-surface-import-start',
  'renderer.native-surface-module-evaluated',
  'renderer.native-surface-import-end',
  'renderer.native-surface-render-start',
  'renderer.native-surface-render-end',
  'renderer.dashboard-ready',
]);
const STARTUP_PAYLOAD_MAX_KEYS = 16;
const STARTUP_PAYLOAD_MAX_KEY_LENGTH = 64;
const STARTUP_PAYLOAD_MAX_STRING_LENGTH = 200;
const MAX_RENDERER_STARTUP_EVENTS_PER_NAME = 4;

let mainWindow;
let backendProcess;
const rendererStartupEventCounts = new Map();

// Robust Logging
let logPath;
try {
  const userDataPath = app.getPath('userData');
  if (!fs.existsSync(userDataPath)) {
    fs.mkdirSync(userDataPath, { recursive: true });
  }
  logPath = path.join(userDataPath, 'debug_electron.log');
} catch (e) {
  // Fallback to temp dir if userData is not available
  logPath = path.join(app.getPath('temp'), 'debug_electron.log');
}

function log(msg) {
  try {
    const timestamp = new Date().toISOString();
    const formattedMsg = `[${timestamp}] ${msg}\n`;
    fs.appendFileSync(logPath, formattedMsg);
    console.log(msg);
  } catch (e) {
    console.error("Failed to write to log file:", e);
  }
}

function getStartupElapsedMs() {
  return Number(process.hrtime.bigint() - startupOriginNs) / 1_000_000;
}

function sanitizeStartupScalar(value) {
  if (value === null) {
    return null;
  }

  if (typeof value === 'string') {
    return value.length > STARTUP_PAYLOAD_MAX_STRING_LENGTH
      ? `${value.slice(0, STARTUP_PAYLOAD_MAX_STRING_LENGTH)}...`
      : value;
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : undefined;
  }

  if (typeof value === 'boolean') {
    return value;
  }

  return undefined;
}

function sanitizeStartupPayload(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return {};
  }

  const sanitized = {};
  for (const [key, value] of Object.entries(payload).slice(0, STARTUP_PAYLOAD_MAX_KEYS)) {
    if (!key || key.length > STARTUP_PAYLOAD_MAX_KEY_LENGTH) {
      continue;
    }

    const sanitizedValue = sanitizeStartupScalar(value);
    if (sanitizedValue !== undefined) {
      sanitized[key] = sanitizedValue;
    }
  }

  return sanitized;
}

function logStartupEvent(eventName, payload) {
  const entry = {
    event: eventName,
    elapsed_ms: Math.round(getStartupElapsedMs() * 10) / 10,
  };
  const sanitizedPayload = sanitizeStartupPayload(payload);
  if (Object.keys(sanitizedPayload).length > 0) {
    entry.payload = sanitizedPayload;
  }
  log(`STARTUP ${JSON.stringify(entry)}`);
}

function normalizeRejectedStartupEventName(value) {
  if (typeof value === 'string') {
    return value.slice(0, STARTUP_PAYLOAD_MAX_STRING_LENGTH);
  }
  return typeof value;
}

// Global Error Handling
process.on('uncaughtException', (error) => {
  log(`UNCAUGHT EXCEPTION: ${error.message}\n${error.stack}`);
  dialog.showErrorBox('Critical Error', `An error occurred: ${error.message}\nCheck log at: ${logPath}`);
});

logStartupEvent('electron.process-start', { is_packaged: app.isPackaged });
log(`--- App Starting (isPackaged: ${app.isPackaged}) ---`);
log(`Executable Path: ${process.executablePath}`);
log(`App Path: ${app.getAppPath()}`);

function resolvePreloadPath() {
  return path.join(__dirname, 'preload.js');
}

function cloneProcessMetric(metric) {
  return {
    pid: metric.pid,
    type: metric.type,
    name: metric.name,
    serviceName: metric.serviceName,
    creationTime: metric.creationTime,
    cpu: metric.cpu,
    memory: metric.memory,
    sandboxed: metric.sandboxed,
    integrityLevel: metric.integrityLevel,
  };
}

async function captureElectronMemory() {
  try {
    return {
      supported: true,
      source: 'electron',
      captured_at: Date.now() / 1000,
      process: await process.getProcessMemoryInfo(),
      metrics: app.getAppMetrics().map(cloneProcessMetric),
      v8_heap: v8.getHeapStatistics(),
      error: null,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      supported: false,
      source: 'electron',
      captured_at: Date.now() / 1000,
      process: null,
      metrics: [],
      v8_heap: null,
      error: message,
    };
  }
}

function registerMemoryIpcHandlers() {
  ipcMain.handle('sfl:get-electron-memory', async () => captureElectronMemory());
}

function registerStartupIpcHandlers() {
  ipcMain.handle('sfl:record-startup-event', async (_event, name, payload) => {
    if (typeof name !== 'string' || !STARTUP_RENDERER_EVENT_NAMES.has(name)) {
      logStartupEvent('renderer.startup-event-rejected', {
        reason: 'invalid_event',
        name: normalizeRejectedStartupEventName(name),
      });
      return { ok: false, reason: 'invalid_event' };
    }

    const nextCount = (rendererStartupEventCounts.get(name) ?? 0) + 1;
    rendererStartupEventCounts.set(name, nextCount);
    if (nextCount > MAX_RENDERER_STARTUP_EVENTS_PER_NAME) {
      logStartupEvent('renderer.startup-event-rejected', {
        reason: 'event_limit',
        name,
      });
      return { ok: false, reason: 'event_limit' };
    }

    logStartupEvent(name, payload);
    return { ok: true };
  });
}

function createWindow() {
  logStartupEvent('electron.window-create-start');
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: resolvePreloadPath(),
      nodeIntegration: false,
      contextIsolation: true,
    },
    title: "창녕 2호기 Smart Factory",
    autoHideMenuBar: true,
  });
  logStartupEvent('electron.window-created');

  let indexPath;
  if (app.isPackaged) {
    log(`Packaged resources path: ${process.resourcesPath}`);
    // extraResources/frontend/dist/index.html
    indexPath = path.join(process.resourcesPath, 'frontend', 'dist', 'index.html');
  } else {
    indexPath = path.join(__dirname, 'frontend', 'dist', 'index.html');
  }
  
  const indexExists = fs.existsSync(indexPath);
  log(`Loading index.html from: ${indexPath}`);
  log(`Frontend index exists: ${indexExists}`);
  
  if (!indexExists) {
    log(`ERROR: index.html not found at: ${indexPath}`);
    dialog.showErrorBox('File Not Found', `index.html was not found at:\n${indexPath}`);
  }

  mainWindow.once('ready-to-show', () => {
    logStartupEvent('electron.window-ready-to-show');
  });

  mainWindow.webContents.on('did-start-loading', () => {
    logStartupEvent('electron.webcontents-did-start-loading');
  });

  mainWindow.webContents.on('dom-ready', () => {
    logStartupEvent('electron.webcontents-dom-ready');
  });

  mainWindow.webContents.on('did-finish-load', () => {
    logStartupEvent('electron.webcontents-did-finish-load');
  });

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
    logStartupEvent('electron.webcontents-did-fail-load', {
      error_code: errorCode,
      error_description: errorDescription,
    });
  });

  logStartupEvent('electron.load-file-start', { index_exists: indexExists });
  mainWindow.loadFile(indexPath, { hash: '/dashboard' }).catch(err => {
    logStartupEvent('electron.load-file-error', { message: err.message });
    log(`Failed to load index.html: ${err.message}`);
    mainWindow.webContents.openDevTools();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startBackend() {
  const isPackaged = app.isPackaged;
  let backendPath;
  let args = [];

  if (isPackaged) {
    backendPath = path.join(process.resourcesPath, 'backend', 'SmartFactoryBackend.exe');
  } else {
    backendPath = 'python';
    const backendPort = process.env.BACKEND_PORT || '8000';
    args = ['-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', backendPort];
  }

  log(`Target backend path: ${backendPath}`);
  if (isPackaged) {
    log(`Packaged backend resources path: ${process.resourcesPath}`);
    log(`Backend executable exists: ${fs.existsSync(backendPath)}`);
  }
  
  if (isPackaged && !fs.existsSync(backendPath)) {
    log(`ERROR: Backend binary NOT FOUND at ${backendPath}`);
    dialog.showErrorBox('Backend Error', `Backend executable not found at:\n${backendPath}`);
    return;
  }

  const spawnOptions = {
    cwd: isPackaged ? path.join(process.resourcesPath, 'backend') : __dirname,
    shell: true,
    windowsVerbatimArguments: true,
    env: {
      ...process.env,
      SFL_EMBEDDED_ELECTRON: '1'
    }
  };

  try {
    logStartupEvent('backend.spawn-start', { is_packaged: isPackaged });
    log(`Spawning backend from: ${backendPath}`);
    log(`Arguments: ${JSON.stringify(args)}`);
    log(`CWD: ${spawnOptions.cwd}`);
    
    backendProcess = spawn(`"${backendPath}"`, args, spawnOptions);

    backendProcess.on('spawn', () => {
      logStartupEvent('backend.spawned', { pid: backendProcess.pid ?? null });
      log(`Backend process spawned successfully (PID: ${backendProcess.pid})`);
    });

    backendProcess.stdout.on('data', (data) => {
      log(`Backend STDOUT: ${data.toString().trim()}`);
    });

    backendProcess.stderr.on('data', (data) => {
      log(`Backend STDERR: ${data.toString().trim()}`);
    });

    backendProcess.on('error', (err) => {
      logStartupEvent('backend.spawn-error', { message: err.message });
      log(`Failed to start backend process: ${err.message}`);
    });

    backendProcess.on('close', (code) => {
      logStartupEvent('backend.closed', { code });
      log(`Backend process exited with code ${code}`);
    });
  } catch (err) {
    logStartupEvent('backend.spawn-exception', { message: err.message });
    log(`CRITICAL: Failed to spawn: ${err.message}`);
  }
}

app.whenReady().then(() => {
  logStartupEvent('electron.app-ready');
  log("App ready, starting backend and window...");
  registerMemoryIpcHandlers();
  registerStartupIpcHandlers();
  startBackend();
  createWindow();
  logStartupEvent('electron.ready-flow-complete');

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    if (backendProcess) {
      log("All windows closed, killing backend...");
      kill(backendProcess.pid, 'SIGTERM', (err) => {
        app.quit();
      });
    } else {
      app.quit();
    }
  }
});

app.on('quit', () => {
  if (backendProcess) {
    kill(backendProcess.pid);
  }
});
