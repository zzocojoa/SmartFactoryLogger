# NSIS Startup Render Performance Plan

> Version: 1.0.0 | Date: 2026-07-04 | Status: Implemented - baseline pending
> Level: Dynamic

---

## 1. Overview

### 1.1 Purpose

Measure the elapsed time from launching the NSIS-installed executable to the
first usable dashboard render, then create a safe baseline for startup
performance improvements.

### 1.2 Background

SmartFactoryLogger V2 is shipped as a Windows Electron desktop app with a
PyInstaller-packaged FastAPI backend and React/Vite frontend assets bundled by
electron-builder NSIS. Current logs show Electron startup, backend spawn, and
frontend file loading, but they do not provide one correlated timeline from
`smart-factory.exe` launch to final dashboard render.

Without that timeline, startup improvements can regress backend readiness,
frontend routing, or operator-visible dashboard rendering without clear
evidence.

## 2. Goals

### 2.1 Primary Goals

- [x] Record a correlated startup timeline in the packaged Electron log.
- [x] Capture Electron lifecycle events: app start, app ready, backend spawn,
  window creation, file load, DOM ready, load finish, ready-to-show, and
  renderer dashboard ready.
- [x] Define "final webpage render" as a renderer event emitted after the
  dashboard surface mounts and the browser has presented at least one frame.
- [x] Keep the renderer bridge constrained to explicit startup telemetry and
  memory APIs only.
- [x] Add contract tests so the preload bridge cannot drift into arbitrary IPC.

### 2.2 Non-Goals

- Do not change installer UX, installation location, or NSIS install flow.
- Do not change backend startup ordering beyond instrumentation in this phase.
- Do not add external telemetry, network reporting, or persistent analytics.
- Do not treat this first pass as a production performance improvement without
  measured baseline data.

## 3. Scope

### 3.1 In Scope

- Electron main process startup event logging.
- A constrained preload bridge method for renderer startup events.
- Dashboard surface ready event from the React renderer.
- Source-level tests that validate IPC bridge shape and dashboard event wiring.
- A local PowerShell script that launches the installed exe, extracts the
  `renderer.dashboard-ready` elapsed time from Electron logs, and cleans up the
  launched process tree by default.
- Documentation of the measurement method and rollback path.

### 3.2 Out of Scope

- Actual NSIS rebuild and server-PC cold-start benchmark collection.
- Backend lazy loading, dependency pruning, or process startup optimization.
- Frontend chunking changes beyond any already existing Vite configuration.
- Grafana service startup tuning.

## 4. Success Criteria

- [x] `[AC-01]` Packaged Electron logs contain a monotonic startup timeline with
  `elapsed_ms` from process start for each key milestone.
- [x] `[AC-02]` Renderer emits `renderer.dashboard-ready` only through a
  constrained `window.smartFactoryElectron.recordStartupEvent(...)` bridge.
- [x] `[AC-03]` Dashboard ready is scheduled after the dashboard surface mounts
  and a browser frame has had a chance to paint.
- [x] `[AC-04]` Existing Electron memory bridge still works and remains
  constrained.
- [x] `[AC-05]` Tests cover preload IPC restrictions and frontend bridge fallback
  behavior in browser mode.
- [x] `[AC-06]` A repeatable PowerShell command can launch the installed exe,
  return dashboard-ready elapsed time as JSON, and clean up the launched process
  tree unless `-KeepRunning` is supplied.
- [ ] `[AC-07]` Installed NSIS cold-start baseline JSON is collected from an
  actual installed exe.

## 5. Schedule

| Phase | Target Date | Status |
|-------|-------------|--------|
| Plan | 2026-07-04 | Completed |
| Design | 2026-07-04 | Completed |
| Implementation | 2026-07-04 | Completed |
| Review | 2026-07-04 | In Progress |
| Installed baseline | TBD | Pending installed exe |

## 6. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| IPC bridge overexposure | Security regression | Medium | Expose one typed method and validate event names/payloads in main. |
| Measurement changes startup cost | False baseline | Medium | Keep logging synchronous path small and data payload bounded. |
| Renderer event fires too early | Misleading metric | Medium | Emit after dashboard surface mount plus `requestAnimationFrame`. |
| Browser mode breaks on missing Electron bridge | Developer workflow regression | Low | Make frontend telemetry a no-op without the bridge. |
| Packaged-only issue not caught locally | Release risk | Medium | Require NSIS rebuild and installed-app validation before claiming performance improvement. |

## 7. Architecture Considerations

- Electron `main.js` is the single owner of packaged startup timing.
- Preload keeps `contextIsolation: true` and exposes only named safe bridge
  functions.
- React renderer reports readiness but does not read filesystem paths, process
  data, or arbitrary IPC channels.
- Logs remain local in Electron `userData` under `debug_electron.log`.

## 8. Validation Plan

- Run frontend typecheck after bridge type updates.
- Run frontend unit tests that cover browser fallback and ready-event emission.
- Run backend unittest containing Electron preload/main contract checks.
- Build is optional for this first instrumentation pass; NSIS benchmark data is
  required before any optimization claim.

## 9. Rollback

Revert the Electron startup telemetry changes in `main.js`, `preload.js`,
frontend bridge types, and dashboard ready event calls. This returns startup
behavior to the previous log-only Electron flow without data migration.

## 10. References

- `package.json`
- `main.js`
- `preload.js`
- `frontend/src/App.tsx`
- `frontend/src/scenes/NativeDashboardSurface.tsx`
- `frontend/src/scenes/DashboardSceneSurface.tsx`
- `backend/tests/test_data_history_api.py`
- `scripts/measure_nsis_startup_render.ps1`
- `docs/03-review/performance-observability-baseline.review.md`
- `docs/04-deploy/spot-live-image-nsis-qa.md`
