# Memory Diagnostics R08 Electron Memory Do Checklist

## 1. Rule

- [ ] `memory-diagnostics-r07-gc-snapshot` Report 완료를 확인한다.
- [ ] 완료 전에는 `memory-diagnostics-r09-frontend-exactness`를 구현하지 않는다.

## 2. Implementation

- [ ] `main.js`에 `ipcMain` import를 추가한다.
- [ ] BrowserWindow에 `preload` 경로를 설정한다.
- [ ] `preload.js`를 추가한다.
- [ ] `smartFactoryElectron.getMemory()` bridge를 추가한다.
- [ ] arbitrary IPC invoke를 노출하지 않는다.
- [ ] `sfl:get-electron-memory` handler를 추가한다.
- [ ] `process.getProcessMemoryInfo()` result를 포함한다.
- [ ] `app.getAppMetrics()` result를 포함한다.
- [ ] V8 heap stats를 가능한 경우 포함한다.
- [ ] frontend global window type을 추가한다.
- [ ] `ElectronMemorySnapshot` type을 추가한다.
- [ ] Electron `ProcessMetric` 호환 type을 추가한다.
- [ ] `useMemoryViewModel`에서 Electron memory snapshot을 수집한다.
- [ ] MemorySection에 Electron process metrics를 표시한다.
- [ ] `package.json` build files에 `preload.js` 포함을 확인한다.

## 3. Tests

- [ ] Electron unavailable fallback test를 추가한다.
- [ ] preload allowed API surface test를 추가한다.
- [ ] MemorySection Electron metrics rendering test를 추가한다.

## 4. Validation

- [ ] frontend tests를 실행한다.
- [ ] `npm run health`를 실행한다.
- [ ] packaged build 또는 equivalent smoke를 실행한다.
- [ ] gstack QA 또는 equivalent UI evidence를 남긴다.
- [ ] `git diff --check`를 실행한다.

## 5. PDCA Close Gate

- [ ] analysis 문서를 작성한다.
- [ ] bkit analyze match rate가 90% 이상이다.
- [ ] iterate 필요 시 재분석한다.
- [ ] report 문서를 작성한다.
- [ ] 다음 feature 시작 가능 상태로 status를 갱신한다.
