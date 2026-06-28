# Memory Diagnostics R08 Electron Memory Plan

## 1. Summary

- Feature: `memory-diagnostics-r08-electron-memory`
- Parent roadmap: `memory-diagnostics-hardening`
- Rank: 8
- Dependency: `memory-diagnostics-r07-gc-snapshot` Report 완료

## 2. Business Goal

Python backend 메모리와 Electron main, renderer, GPU/utility process 메모리를 분리해서 전체 desktop app 메모리 문제를 정확히 판단한다.

## 3. Scope

- `main.js`에 제한된 IPC handler 추가
- `preload.js` 추가
- `window.smartFactoryElectron.getMemory()` bridge 추가
- frontend snapshot에 Electron memory 추가
- Memory UI에서 process type별 memory 표시
- packaged build에 `preload.js` 포함 확인

## 4. Out Of Scope

- arbitrary IPC bridge
- Electron process 제어 기능
- backend process spawn 구조 변경
- GPU process 튜닝

## 5. Acceptance Criteria

- renderer는 직접 Electron API를 호출하지 않는다.
- preload는 `getMemory()` 하나만 노출한다.
- `app.getAppMetrics()`와 `process.getProcessMemoryInfo()` 결과가 snapshot에 포함된다.
- Electron API가 없는 browser mode에서도 frontend가 정상 동작한다.

## 6. Validation Gate

- preload API surface test 통과
- frontend Electron unavailable fallback test 통과
- packaged build smoke 확인
- gstack QA 또는 equivalent UI smoke 완료
- bkit analyze match rate 90% 이상

## 7. Rollback

preload 설정과 IPC handler를 제거하면 browser/backend-only memory 진단으로 돌아간다. backend API는 영향을 받지 않는다.

