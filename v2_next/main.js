const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const path = require('path');
const { pathToFileURL } = require('url');
const { randomBytes } = require('crypto');
const { spawn } = require('child_process');
const kill = require('tree-kill');
const fs = require('fs');
const v8 = require('v8');
const {
  StartupCoordinator,
  createBackendProgressParser,
} = require('./startupCoordinator');
const {
  createApplicationShutdownController,
  createBackendCloseoutGate,
  createBackendRestartController,
  createCloseoutVerifiedStop,
  stopProcessTree,
} = require('./backendProcessLifecycle');
const {
  buildBackendProgressEnvironment,
  createBackendProgressFileTransport,
} = require('./backendStartupProgress');
const {
  createStartupIpcHandlers,
  isTrustedStartupSender,
  normalizeDocumentUrl,
} = require('./startupIpc');
const { createBackendControlIpcHandlers } = require('./backendControlIpc');
const {
  requestBackendConnectionTest: sendBackendConnectionTest,
  requestBackendGracefulShutdown: sendBackendGracefulShutdown,
  requestBackendHealth: sendBackendHealth,
} = require('./backendControlClient');
const {
  createRotatingFileLogger,
  isMatchingBackendHealth,
  installSingleInstanceGuard,
} = require('./electronRuntimeSafety');

const startupOriginNs = process.hrtime.bigint();
const startupSessionId = `${process.pid}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
const backendControlToken = randomBytes(32).toString('hex');
// Software compositing avoids GPU channel setup delaying NSIS cold start render.
app.disableHardwareAcceleration();
const STARTUP_RENDERER_EVENT_NAMES = new Set([
  'renderer.preload-start',
  'renderer.preload-bridge-exposed',
  'renderer.splash-first-paint',
  'renderer.index-html-inline-script',
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
  'renderer.dashboard-paint-fallback',
  'renderer.backend-health-ready',
  'renderer.first-data-snapshot',
  'renderer.first-live-data',
  'renderer.dashboard-operational-timeout',
  'renderer.dashboard-operational-ready',
]);
const STARTUP_PAYLOAD_MAX_KEYS = 16;
const STARTUP_PAYLOAD_MAX_KEY_LENGTH = 64;
const STARTUP_PAYLOAD_MAX_STRING_LENGTH = 200;
const MAX_RENDERER_STARTUP_EVENTS_PER_NAME = 4;
const BACKEND_GRACEFUL_SHUTDOWN_MS = 390_000;
const BACKEND_CONTROL_RESPONSE_MAX_BYTES = 1024 * 1024;
const BACKEND_CONNECTION_TEST_TIMEOUT_MS = 10_000;
const BACKEND_SHUTDOWN_REQUEST_TIMEOUT_MS = 2_000;
const BACKEND_RETRY_HEALTH_GRACE_MS = 12_000;
const BACKEND_RETRY_HEALTH_REQUEST_TIMEOUT_MS = 750;
const BACKEND_RETRY_HEALTH_INTERVAL_MS = 500;
const ELECTRON_LOG_MAX_BYTES = 8 * 1024 * 1024;
const ELECTRON_LOG_MAX_BACKUPS = 3;

let mainWindow;
let backendProcess;
const backendCloseoutGate = createBackendCloseoutGate();
let backendProgressTransport;
let trustedMainDocumentUrl = null;
let trustedRendererTimeOriginMs = null;
let applicationQuitting = false;
let lastPublishedStartupState = null;
let backendStartFallbackTimer = null;
let backendStartTriggered = false;
let mainWindowReadyToShow = false;
let mainWindowShown = false;
let splashFirstPaintAccepted = false;
const expectedBackendExitPids = new Set();
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

const electronLogger = createRotatingFileLogger({
  logPath,
  maxBytes: ELECTRON_LOG_MAX_BYTES,
  maxBackups: ELECTRON_LOG_MAX_BACKUPS,
});

function log(msg) {
  electronLogger.log(msg);
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
    session_id: startupSessionId,
    elapsed_ms: Math.round(getStartupElapsedMs() * 10) / 10,
  };
  const sanitizedPayload = sanitizeStartupPayload(payload);
  if (Object.keys(sanitizedPayload).length > 0) {
    entry.payload = sanitizedPayload;
  }
  log(`STARTUP ${JSON.stringify(entry)}`);
}

function publishStartupState(state) {
  const previousState = lastPublishedStartupState;
  logStartupEvent('electron.startup-state-changed', {
    sequence: state.sequence,
    from_status: previousState?.status ?? null,
    to_status: state.status,
    from_phase: previousState?.phase ?? null,
    to_phase: state.phase,
    progress: state.progress,
    reason: state.reason,
  });
  lastPublishedStartupState = state;

  const contents = mainWindow?.webContents;
  if (!contents || contents.isDestroyed()) {
    return;
  }
  contents.send('sfl:startup-state-changed', state);
}

const startupCoordinator = new StartupCoordinator({
  sessionId: startupSessionId,
  timeoutMs: 30_000,
  now: getStartupElapsedMs,
  onChange: publishStartupState,
});

function normalizeRejectedStartupEventName(value) {
  if (typeof value === 'string') {
    return value.slice(0, STARTUP_PAYLOAD_MAX_STRING_LENGTH);
  }
  return typeof value;
}

function getStartupUrlProtocol(url) {
  if (typeof url !== 'string' || url.length === 0) {
    return null;
  }

  try {
    return new URL(url).protocol;
  } catch (_error) {
    return null;
  }
}

function createNavigationStartupPayload(details, extra = {}) {
  const protocol = getStartupUrlProtocol(details?.url);
  return {
    ...extra,
    protocol,
    is_file_url: protocol === 'file:',
    is_main_frame: Boolean(details?.isMainFrame),
    is_same_document: Boolean(details?.isSameDocument),
  };
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
  const handlers = createStartupIpcHandlers({
    getMainWindow: () => mainWindow,
    getExpectedDocumentUrl: () => trustedMainDocumentUrl,
    allowedEventNames: STARTUP_RENDERER_EVENT_NAMES,
    eventCounts: rendererStartupEventCounts,
    maxEventsPerName: MAX_RENDERER_STARTUP_EVENTS_PER_NAME,
    coordinator: startupCoordinator,
    sanitizePayload: sanitizeStartupPayload,
    normalizeRejectedEventName: normalizeRejectedStartupEventName,
    logStartupEvent,
    getRendererGeneration: () => trustedRendererTimeOriginMs,
    setRendererGeneration: (value) => {
      trustedRendererTimeOriginMs = value;
    },
    onAcceptedEvent: (name) => {
      if (name === 'renderer.splash-first-paint') {
        splashFirstPaintAccepted = true;
        maybeShowSplashAndTriggerInitialBackendStart();
      }
    },
    recheckBackendHealth: waitForBackendHealthBeforeRetry,
    recoverHealthyBackend: recoverStartupWithHealthyBackend,
    restartBackend,
    quitApplication: () => setImmediate(() => app.quit()),
  });

  ipcMain.handle('sfl:record-startup-event', handlers.recordStartupEvent);
  ipcMain.handle('sfl:get-startup-state', handlers.getStartupState);
  ipcMain.handle('sfl:retry-startup', handlers.retryStartup);
  ipcMain.handle('sfl:continue-startup-offline', handlers.continueStartupOffline);
  ipcMain.handle('sfl:exit-startup', handlers.exitStartup);
}

function resolveBackendPort() {
  const configuredPort = Number.parseInt(process.env.BACKEND_PORT || '8000', 10);
  return Number.isInteger(configuredPort) && configuredPort > 0 && configuredPort <= 65_535
    ? configuredPort
    : 8000;
}

function requestBackendConnectionTest(serializedPayload) {
  return sendBackendConnectionTest(serializedPayload, {
    controlToken: backendControlToken,
    port: resolveBackendPort(),
    maxResponseBytes: BACKEND_CONTROL_RESPONSE_MAX_BYTES,
    timeoutMs: BACKEND_CONNECTION_TEST_TIMEOUT_MS,
  });
}

function registerBackendControlIpcHandlers() {
  const handlers = createBackendControlIpcHandlers({
    isTrustedSender: (event) => isTrustedStartupSender(
      event,
      mainWindow,
      trustedMainDocumentUrl
    ),
    requestConnectionTest: requestBackendConnectionTest,
  });
  ipcMain.handle('sfl:test-connection', handlers.testConnection);
}

function createWindow() {
  logStartupEvent('electron.window-create-start');
  mainWindowReadyToShow = false;
  mainWindowShown = false;
  splashFirstPaintAccepted = false;
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
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
  trustedMainDocumentUrl = pathToFileURL(indexPath).href;
  
  const indexExists = fs.existsSync(indexPath);
  log(`Loading index.html from: ${indexPath}`);
  log(`Frontend index exists: ${indexExists}`);
  
  if (!indexExists) {
    log(`ERROR: index.html not found at: ${indexPath}`);
    dialog.showErrorBox('File Not Found', `index.html was not found at:\n${indexPath}`);
  }

  mainWindow.once('ready-to-show', () => {
    logStartupEvent('electron.window-ready-to-show');
    mainWindowReadyToShow = true;
    if (!maybeShowSplashAndTriggerInitialBackendStart()) {
      armInitialBackendStartFallback();
    }
  });

  mainWindow.webContents.on('did-start-loading', () => {
    logStartupEvent('electron.webcontents-did-start-loading');
  });

  mainWindow.webContents.on('did-start-navigation', (details) => {
    if (details?.isMainFrame) {
      logStartupEvent(
        'electron.webcontents-did-start-navigation',
        createNavigationStartupPayload(details)
      );
    }
  });

  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (normalizeDocumentUrl(url) !== normalizeDocumentUrl(trustedMainDocumentUrl)) {
      event.preventDefault();
      logStartupEvent('electron.navigation-blocked', {
        protocol: getStartupUrlProtocol(url),
      });
    }
  });
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));

  mainWindow.webContents.on('dom-ready', () => {
    logStartupEvent('electron.webcontents-dom-ready');
  });

  mainWindow.webContents.on('did-frame-finish-load', (_event, isMainFrame) => {
    if (isMainFrame) {
      logStartupEvent('electron.webcontents-did-frame-finish-load', {
        is_main_frame: true,
      });
    }
  });

  mainWindow.webContents.on('did-finish-load', () => {
    logStartupEvent('electron.webcontents-did-finish-load');
  });

  mainWindow.webContents.on('did-navigate', (_event, url, httpResponseCode) => {
    logStartupEvent('electron.webcontents-did-navigate', {
      protocol: getStartupUrlProtocol(url),
      is_file_url: getStartupUrlProtocol(url) === 'file:',
      http_response_code: httpResponseCode,
    });
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

  mainWindow.on('close', handleApplicationCloseRequest);
  mainWindow.on('closed', () => {
    mainWindowReadyToShow = false;
    mainWindowShown = false;
    mainWindow = null;
    trustedMainDocumentUrl = null;
    trustedRendererTimeOriginMs = null;
  });
}

function triggerInitialBackendStart(reason) {
  if (backendStartTriggered || applicationQuitting) {
    return false;
  }
  backendStartTriggered = true;
  if (backendStartFallbackTimer !== null) {
    clearTimeout(backendStartFallbackTimer);
    backendStartFallbackTimer = null;
  }
  logStartupEvent('backend.initial-start-triggered', { reason });
  return Boolean(startBackend());
}

function showStartupWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return false;
  }
  if (!mainWindowShown) {
    mainWindow.show();
    mainWindowShown = true;
    logStartupEvent('electron.window-shown');
  }
  return true;
}

function maybeShowSplashAndTriggerInitialBackendStart() {
  if (!mainWindowReadyToShow || !splashFirstPaintAccepted) {
    return false;
  }
  if (!showStartupWindow()) {
    return false;
  }
  return triggerInitialBackendStart('splash_first_paint');
}

function armInitialBackendStartFallback() {
  if (!mainWindowReadyToShow || backendStartTriggered || backendStartFallbackTimer !== null) {
    return;
  }
  backendStartFallbackTimer = setTimeout(() => {
    backendStartFallbackTimer = null;
    if (mainWindowReadyToShow && showStartupWindow()) {
      triggerInitialBackendStart('splash_paint_fallback_after_window_show');
    }
  }, 750);
}

function startBackend() {
  if (applicationQuitting) {
    return null;
  }
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
    startupCoordinator.failBackend('backend_binary_missing');
    return null;
  }

  let progressTransport = null;
  try {
    if (backendProgressTransport) {
      backendProgressTransport.close();
      backendProgressTransport = null;
    }
    const seenProgressStages = new Set();
    const closeProgressTransport = () => {
      if (!progressTransport) {
        return;
      }
      progressTransport.close();
      if (backendProgressTransport === progressTransport) {
        backendProgressTransport = null;
      }
      progressTransport = null;
    };
    const acceptProgressStage = (stage) => {
      if (seenProgressStages.has(stage)) {
        return;
      }
      seenProgressStages.add(stage);
      logStartupEvent('backend.startup-progress', { stage });
      startupCoordinator.handleBackendStage(stage);
      if (stage === 'lifespan_complete') {
        setImmediate(closeProgressTransport);
      }
    };
    const progressParser = createBackendProgressParser({
      onStage: acceptProgressStage,
      onRejected: (reason) => {
        logStartupEvent('backend.startup-progress-rejected', { reason, source: 'stdout' });
      },
    });
    let progressEnvironment = {};
    try {
      progressTransport = createBackendProgressFileTransport({
        rootDir: path.join(app.getPath('userData'), 'startup-progress'),
        sessionId: startupSessionId,
        onStage: acceptProgressStage,
        onRejected: (reason) => {
          logStartupEvent('backend.startup-progress-rejected', { reason, source: 'file' });
        },
      });
      backendProgressTransport = progressTransport;
      progressEnvironment = progressTransport.environment;
    } catch (_error) {
      logStartupEvent('backend.startup-progress-rejected', {
        reason: 'transport_create_failed',
        source: 'file',
      });
    }

    const spawnOptions = {
      cwd: isPackaged ? path.join(process.resourcesPath, 'backend') : __dirname,
      shell: false,
      windowsHide: true,
      env: buildBackendProgressEnvironment(process.env, {
        ...progressEnvironment,
        SFL_EMBEDDED_ELECTRON: '1',
        SFL_CONTROL_TOKEN: backendControlToken,
      }),
    };

    logStartupEvent('backend.spawn-start', { is_packaged: isPackaged });
    startupCoordinator.handleMainMilestone('backend_spawn_start');
    log(`Spawning backend from: ${backendPath}`);
    log(`Arguments: ${JSON.stringify(args)}`);
    log(`CWD: ${spawnOptions.cwd}`);
    
    const child = spawn(backendPath, args, spawnOptions);
    backendProcess = child;

    child.on('spawn', () => {
      backendCloseoutGate.markBackendStarted();
      logStartupEvent('backend.spawned', { pid: child.pid ?? null });
      startupCoordinator.handleMainMilestone('backend_spawned');
      log(`Backend process spawned successfully (PID: ${child.pid})`);
    });

    child.stdout?.on('data', (data) => {
      progressParser.push(data);
      log(`Backend STDOUT: ${data.toString().trim()}`);
    });

    child.stderr?.on('data', (data) => {
      log(`Backend STDERR: ${data.toString().trim()}`);
    });

    child.on('error', (err) => {
      closeProgressTransport();
      logStartupEvent('backend.spawn-error', { message: err.message });
      log(`Failed to start backend process: ${err.message}`);
      if (!expectedBackendExitPids.has(child.pid)) {
        startupCoordinator.failBackend('backend_spawn_error');
      }
    });

    child.on('close', (code) => {
      progressParser.flush();
      closeProgressTransport();
      logStartupEvent('backend.closed', { code });
      log(`Backend process exited with code ${code}`);
      const wasExpected = expectedBackendExitPids.delete(child.pid);
      if (backendProcess === child) {
        backendProcess = null;
      }
      if (!wasExpected && !applicationQuitting) {
        startupCoordinator.failBackend(`backend_closed_${code ?? 'unknown'}`);
      }
    });
    return child;
  } catch (err) {
    if (progressTransport) {
      progressTransport.close();
      if (backendProgressTransport === progressTransport) {
        backendProgressTransport = null;
      }
    }
    logStartupEvent('backend.spawn-exception', { message: err.message });
    log(`CRITICAL: Failed to spawn: ${err.message}`);
    startupCoordinator.failBackend('backend_spawn_exception');
    return null;
  }
}

function requestBackendGracefulShutdown() {
  return sendBackendGracefulShutdown({
    controlToken: backendControlToken,
    port: resolveBackendPort(),
    reason: applicationQuitting ? 'electron_exit' : 'electron_retry',
    timeoutMs: BACKEND_SHUTDOWN_REQUEST_TIMEOUT_MS,
  });
}

async function stopBackendProcess(child = backendProcess) {
  if (!child?.pid) {
    return { stopped: true, reason: 'no_process' };
  }

  expectedBackendExitPids.add(child.pid);
  const startedAtNs = process.hrtime.bigint();
  logStartupEvent('backend.shutdown-start', {
    pid: child.pid,
    grace_ms: BACKEND_GRACEFUL_SHUTDOWN_MS,
  });
  try {
    const result = await stopProcessTree(child, {
      killTree: kill,
      requestGracefulStop: requestBackendGracefulShutdown,
      log,
      graceMs: BACKEND_GRACEFUL_SHUTDOWN_MS,
    });
    if (result.reason === 'already_exited') {
      expectedBackendExitPids.delete(child.pid);
    }
    logStartupEvent('backend.shutdown-complete', {
      pid: child.pid,
      reason: result.reason,
      exit_code: result.exitCode ?? null,
      signal_code: result.signalCode ?? null,
      forced: result.forced === true,
      elapsed_ms: Math.round(Number(process.hrtime.bigint() - startedAtNs) / 100_000) / 10,
    });
    return result;
  } catch (error) {
    logStartupEvent('backend.shutdown-failed', {
      pid: child.pid,
      message: error instanceof Error ? error.message : String(error),
      elapsed_ms: Math.round(Number(process.hrtime.bigint() - startedAtNs) / 100_000) / 10,
    });
    throw error;
  }
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function waitForBackendHealthBeforeRetry() {
  const deadline = Date.now() + BACKEND_RETRY_HEALTH_GRACE_MS;
  let attempts = 0;
  let lastError = null;
  while (!applicationQuitting && backendProcess?.pid && Date.now() <= deadline) {
    attempts += 1;
    try {
      const health = await sendBackendHealth({
        controlToken: backendControlToken,
        port: resolveBackendPort(),
        maxResponseBytes: BACKEND_CONTROL_RESPONSE_MAX_BYTES,
        timeoutMs: BACKEND_RETRY_HEALTH_REQUEST_TIMEOUT_MS,
      });
      if (isMatchingBackendHealth(health, backendProcess.pid)) {
        logStartupEvent('backend.retry-health-recovered', { attempts });
        return true;
      }
      lastError = new Error('Backend health identity did not match the spawned process.');
    } catch (error) {
      lastError = error;
    }
    if (!startupCoordinator.getState().can_retry) {
      logStartupEvent('backend.retry-renderer-recovered', { attempts });
      return false;
    }
    const remaining = deadline - Date.now();
    if (remaining <= 0) {
      break;
    }
    await delay(Math.min(BACKEND_RETRY_HEALTH_INTERVAL_MS, remaining));
  }
  logStartupEvent('backend.retry-health-not-ready', {
    attempts,
    message: lastError instanceof Error ? lastError.message : null,
  });
  return false;
}

function resetStartupForRetry(reason) {
  rendererStartupEventCounts.clear();
  trustedRendererTimeOriginMs = null;
  startupCoordinator.reset(reason);
  const contents = mainWindow?.webContents;
  if (contents && !contents.isDestroyed()) {
    contents.reload();
  }
}

async function recoverStartupWithHealthyBackend() {
  resetStartupForRetry('retry_health_recovered');
}

const stopBackendWithVerifiedCloseout = createCloseoutVerifiedStop({
  stopProcess: stopBackendProcess,
  closeoutGate: backendCloseoutGate,
});

const backendRestartController = createBackendRestartController({
  getProcess: () => backendProcess,
  setProcess: (child) => {
    backendProcess = child;
  },
  stopProcess: stopBackendWithVerifiedCloseout,
  startProcess: startBackend,
  isQuitting: () => applicationQuitting,
  beforeRestart: async () => {
    backendCloseoutGate.assertCanExitWithoutProcess();
    logStartupEvent('backend.restart-requested');
    resetStartupForRetry('manual_retry');
  },
});

const applicationShutdownController = createApplicationShutdownController({
  setQuitting: (value) => {
    applicationQuitting = value;
  },
  prepareShutdown: () => {
    if (backendStartFallbackTimer !== null) {
      clearTimeout(backendStartFallbackTimer);
      backendStartFallbackTimer = null;
    }
    startupCoordinator.dispose();
  },
  shutdown: async () => {
    await backendRestartController.waitForActiveRestart();
    const child = backendProcess;
    if (!child?.pid) {
      backendCloseoutGate.assertCanExitWithoutProcess();
      return;
    }
    await stopBackendWithVerifiedCloseout(child);
    if (backendProcess === child) {
      backendProcess = null;
    }
  },
  quitApplication: () => app.quit(),
  onFailure: (error) => {
    const message = error instanceof Error ? error.message : String(error);
    logStartupEvent('backend.shutdown-failed', { message });
    log(`Backend shutdown failed: ${message}`);
    dialog.showErrorBox(
      'Backend Shutdown Error',
      '백엔드 프로세스를 안전하게 종료하지 못했습니다. 로그를 확인한 뒤 다시 종료하십시오.'
    );
  },
});

function handleApplicationCloseRequest(event) {
  applicationShutdownController.handleCloseRequest(event);
}

function restartBackend() {
  return backendRestartController.restart();
}

const isPrimaryInstance = installSingleInstanceGuard(app, {
  getMainWindow: () => mainWindow,
  logEvent: logStartupEvent,
});

if (isPrimaryInstance) {
  app.whenReady().then(() => {
    logStartupEvent('electron.app-ready');
    log("App ready, preparing startup window...");
    registerMemoryIpcHandlers();
    registerStartupIpcHandlers();
    registerBackendControlIpcHandlers();
    startupCoordinator.start();
    createWindow();
    logStartupEvent('electron.ready-flow-complete');

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      app.quit();
    }
  });

  app.on('before-quit', handleApplicationCloseRequest);
}
