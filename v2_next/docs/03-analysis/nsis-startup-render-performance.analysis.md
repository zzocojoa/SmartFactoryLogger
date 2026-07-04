# Gap Analysis: nsis-startup-render-performance

> Date: 2026-07-04 | Design: docs/02-design/features/nsis-startup-render-performance.design.md

---

## Match Rate: 92%

## Summary

The implementation matches the designed local startup telemetry path. Electron
main owns a monotonic startup clock, renderer startup events flow through a
constrained preload bridge, dashboard-ready is emitted after dashboard surface
mount plus animation frames, and a PowerShell script can launch an installed exe
and extract `renderer.dashboard-ready` elapsed time from the Electron log. The
script now cleans up the launched process tree by default so repeated cold-start
samples are less likely to be contaminated by a previous run.

The remaining gap is operational evidence: no installed NSIS artifact was run in
this session, so baseline median/p95 startup render time is not yet measured.

## Implemented Items

- [x] Electron main logs `STARTUP` JSON lines with `elapsed_ms`.
- [x] Electron lifecycle events include process start, app ready, backend spawn,
  window creation, load-file start, DOM ready, did-finish-load, and
  ready-to-show.
- [x] Renderer events are limited to `renderer.index-boot`,
  `renderer.index-render`, and `renderer.dashboard-ready`.
- [x] Main process validates renderer event names and bounds primitive payloads.
- [x] Preload exposes `recordStartupEvent` without arbitrary IPC forwarding.
- [x] Existing memory bridge remains present.
- [x] Shared TypeScript types cover startup event names, payload, and result.
- [x] `NativeDashboardSurface` emits dashboard-ready after paint scheduling.
- [x] `DashboardSceneSurface` emits dashboard-ready for edit-mode scene usage.
- [x] Frontend helper handles browser fallback and deduplicates events.
- [x] `scripts/measure_nsis_startup_render.ps1` launches an exe, returns
  dashboard-ready elapsed time as JSON, and reports cleanup status.

## Missing Items

- [ ] Installed NSIS exe cold-start baseline was not collected in this session.

## Changed Items (Deviations from Design)

- [x] Added `frontend/src/shared/startup/startupTelemetry.ts` as a small helper
  to avoid duplicating bridge fallback and after-paint scheduling logic.
- [x] Updated the design document to include the helper and its test.

## Verification Evidence

- [x] `node --check main.js`
- [x] `node --check preload.js`
- [x] PowerShell parser check for `scripts/measure_nsis_startup_render.ps1`
- [x] `npm --prefix frontend run typecheck`
- [x] `npm --prefix frontend run lint`
- [x] `npm --prefix frontend run test -- startupTelemetry useMemoryViewModel`
- [x] `.\\backend\\.venv\\Scripts\\python.exe -m unittest backend.tests.test_data_history_api.ElectronPreloadContractTests`
- [x] `npm --prefix frontend run build`
- [x] `git diff --check`

## Recommendations

1. Run the measurement script against a freshly installed NSIS build on the
   target Windows machine.
2. Confirm each sample reports successful cleanup, or intentionally use
   `-KeepRunning` only for manual observation.
3. Capture at least five cold-start samples before changing startup ordering or
   bundle composition.
4. Use the measured timeline to decide whether the bottleneck is Electron shell,
   backend spawn/readiness, static asset load, or dashboard renderer work.

## Next Steps

- [ ] Collect installed NSIS startup baseline JSON.
- [ ] Decide the first optimization target from the slowest measured milestone.
- [ ] Re-run this analysis after baseline collection.
