# Memory Diagnostics R08 Electron Memory Design

## 1. Summary

`memory-diagnostics-r08-electron-memory`는 packaged desktop app의 process memory를 분해한다. Renderer는 Node/Electron API에 직접 접근하지 않고 preload bridge만 사용한다.

## 2. Files

- `main.js`
- `preload.js`
- `package.json`
- `frontend/src/shared/types.ts`
- `frontend/src/domains/Observability/hooks/useMemoryViewModel.ts`
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`

## 3. Electron Main Design

`main.js`:

- `ipcMain` import
- BrowserWindow `webPreferences.preload` 설정
- `ipcMain.handle('sfl:get-electron-memory', async () => ...)` 추가
- `process.getProcessMemoryInfo()`와 `app.getAppMetrics()` 반환

## 4. Preload Design

`preload.js`:

```javascript
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('smartFactoryElectron', {
  getMemory: () => ipcRenderer.invoke('sfl:get-electron-memory'),
});
```

arbitrary channel invoke는 노출하지 않는다.

## 5. Frontend Design

`window.smartFactoryElectron?.getMemory()`가 있으면 frontend memory snapshot에 `electron` field를 추가한다. 없는 경우 browser dev mode로 보고 unavailable 처리한다.

## 6. Packaging Design

Frontend shared types must include `ElectronMemorySnapshot` and an Electron `ProcessMetric` compatible shape. Keep process type, pid, CPU, and memory fields typed without exposing arbitrary IPC data.

`package.json` build files에 `preload.js`가 포함되어야 한다.

## 7. Tests

- Electron unavailable fallback
- preload exposes only allowed API
- MemorySection renders process metrics
- packaged smoke confirms preload inclusion

## 8. Analyze Evidence

bkit analyze는 `main.js` IPC handler, `preload.js`, package inclusion, frontend type/snapshot/UI rendering을 확인해야 한다.
