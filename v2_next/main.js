const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const kill = require('tree-kill');
const fs = require('fs');

let mainWindow;
let backendProcess;

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

// Global Error Handling
process.on('uncaughtException', (error) => {
  log(`UNCAUGHT EXCEPTION: ${error.message}\n${error.stack}`);
  dialog.showErrorBox('Critical Error', `An error occurred: ${error.message}\nCheck log at: ${logPath}`);
});

log(`--- App Starting (isPackaged: ${app.isPackaged}) ---`);
log(`Executable Path: ${process.executablePath}`);
log(`App Path: ${app.getAppPath()}`);

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    title: "창녕 2호기 Smart Factory",
    autoHideMenuBar: true,
  });

  let indexPath;
  if (app.isPackaged) {
    // extraResources/frontend/dist/index.html
    indexPath = path.join(process.resourcesPath, 'frontend', 'dist', 'index.html');
  } else {
    indexPath = path.join(__dirname, 'frontend', 'dist', 'index.html');
  }
  
  log(`Loading index.html from: ${indexPath}`);
  
  if (!fs.existsSync(indexPath)) {
    log(`ERROR: index.html not found at: ${indexPath}`);
    dialog.showErrorBox('File Not Found', `index.html was not found at:\n${indexPath}`);
  }

  mainWindow.loadFile(indexPath).catch(err => {
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
    backendPath = path.join(process.resourcesPath, 'backend', 'backend_server.exe');
  } else {
    backendPath = 'python';
    args = ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000'];
  }

  log(`Target backend path: ${backendPath}`);
  
  if (isPackaged && !fs.existsSync(backendPath)) {
    log(`ERROR: Backend binary NOT FOUND at ${backendPath}`);
    dialog.showErrorBox('Backend Error', `Backend executable not found at:\n${backendPath}`);
    return;
  }

  const spawnOptions = {
    cwd: isPackaged ? path.join(process.resourcesPath, 'backend') : __dirname,
    shell: true,
    windowsVerbatimArguments: true
  };

  try {
    log(`Spawning backend from: ${backendPath}`);
    log(`Arguments: ${JSON.stringify(args)}`);
    log(`CWD: ${spawnOptions.cwd}`);
    
    backendProcess = spawn(`"${backendPath}"`, args, spawnOptions);

    backendProcess.on('spawn', () => {
      log(`Backend process spawned successfully (PID: ${backendProcess.pid})`);
    });

    backendProcess.stdout.on('data', (data) => {
      log(`Backend STDOUT: ${data.toString().trim()}`);
    });

    backendProcess.stderr.on('data', (data) => {
      log(`Backend STDERR: ${data.toString().trim()}`);
    });

    backendProcess.on('error', (err) => {
      log(`Failed to start backend process: ${err.message}`);
    });

    backendProcess.on('close', (code) => {
      log(`Backend process exited with code ${code}`);
    });
  } catch (err) {
    log(`CRITICAL: Failed to spawn: ${err.message}`);
  }
}

app.whenReady().then(() => {
  log("App ready, starting backend and window...");
  startBackend();
  createWindow();

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
