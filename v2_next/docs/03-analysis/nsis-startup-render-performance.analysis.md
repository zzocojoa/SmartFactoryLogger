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
renderer helper now includes a bounded timeout fallback for environments where
animation frames are throttled, and the script cleans up the launched process
tree by default so repeated cold-start samples are less likely to be contaminated
by a previous run.

Operational evidence now exists for a telemetry-enabled installed artifact. The
older local install first returned `TIMEOUT` with `event_count=0`, which
confirmed that stale installs are not valid baseline sources. After installing
a fresh CI artifact for this branch, `scripts/measure_nsis_startup_render.ps1`
returned `PASS`. A repeated installed-app baseline is now recorded below using
only sanitized fields; local-only runtime details are omitted.

## Repeated Cold-Start Baseline

Measurement date: 2026-07-05 KST

Installed artifact identity:

- Installed executable: `smart-factory.exe`
- Product version: `1.0.11.0`
- File version: `1.0.11`
- SHA256: `B812BC91D14E1E2A8A54990C4A46DA1A7A630C3EA47A9939E7640D34F4C79100`

Sanitized samples from `scripts/measure_nsis_startup_render.ps1` are split into
separate batches because the independent verification run found a higher
five-sample p95 than the initial run. Both batches prove measurement readiness,
but the p95 value is sample-size sensitive and should not be treated as a stable
regression threshold yet.

### Batch A: Initial Measurement

| Sample | Status | dashboard_ready_elapsed_ms | event_count | cleanup.ok | ready_strategy |
|--------|--------|----------------------------|-------------|------------|----------------|
| 1 | PASS | 709.1 | 16 | true | raf |
| 2 | PASS | 662.5 | 16 | true | raf |
| 3 | PASS | 677.6 | 16 | true | raf |
| 4 | PASS | 670.8 | 16 | true | raf |
| 5 | PASS | 666.2 | 16 | true | raf |

Batch A summary:

- PASS samples: 5/5
- Cleanup success: 5/5
- Median `dashboard_ready_elapsed_ms`: 670.8 ms
- p95 `dashboard_ready_elapsed_ms`: 709.1 ms
- p95 method: nearest-rank over five samples
- Range: 662.5 ms to 709.1 ms

### Batch B: Independent Verification

| Sample | Status | dashboard_ready_elapsed_ms | event_count | cleanup.ok | ready_strategy |
|--------|--------|----------------------------|-------------|------------|----------------|
| 1 | PASS | 707.7 | 16 | true | raf |
| 2 | PASS | 1106.5 | 16 | true | raf |
| 3 | PASS | 598.1 | 16 | true | raf |
| 4 | PASS | 583.9 | 16 | true | raf |
| 5 | PASS | 664.1 | 16 | true | raf |

Batch B summary:

- PASS samples: 5/5
- Cleanup success: 5/5
- Median `dashboard_ready_elapsed_ms`: 664.1 ms
- p95 `dashboard_ready_elapsed_ms`: 1106.5 ms
- p95 method: nearest-rank over five samples
- Range: 583.9 ms to 1106.5 ms

Baseline interpretation:

- Measurement readiness is PASS across both batches: 10/10 samples passed and
  cleanup succeeded 10/10 times.
- Median is consistent across the two batches: 670.8 ms in Batch A and
  664.1 ms in Batch B.
- p95 is not stable with five samples. Batch B includes one slower run at
  1106.5 ms, which becomes p95 under nearest-rank calculation.
- Use these batches as startup telemetry readiness evidence. Before setting a
  regression budget or judging an optimization, collect a larger cold-start
  sample set.
- Raw JSON and local-only runtime details are intentionally omitted from this
  document.

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
- [x] Frontend helper handles browser fallback, RAF timeout fallback, and
  deduplicates events.
- [x] `scripts/measure_nsis_startup_render.ps1` launches an exe, returns
  dashboard-ready elapsed time as JSON, and reports cleanup status.

## Missing Items

- None for measurement readiness. Repeated samples are captured in the baseline
  section above, but p95 remains a sample-size-sensitive value until a larger
  cold-start sample set is collected.

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
- [x] Installed-app repeated baseline Batch A: 5 PASS samples, median 670.8 ms,
  p95 709.1 ms, cleanup 5/5.
- [x] Independent verification Batch B: 5 PASS samples, median 664.1 ms, p95
  1106.5 ms, cleanup 5/5.

## Recommendations

1. Use the repeated fresh installed-app baseline as readiness evidence before
   choosing a performance optimization target.
2. Confirm future samples report successful cleanup, or intentionally use
   `-KeepRunning` only for manual observation.
3. Capture a larger cold-start sample set before setting p95-based regression
   thresholds or claiming p95 improvement.
4. Re-capture at least five cold-start samples after changing startup ordering
   or bundle composition.
5. Use the measured timeline to decide whether the bottleneck is Electron shell,
   backend spawn/readiness, static asset load, or dashboard renderer work.

## Next Steps

- [x] Build and install a fresh NSIS artifact that includes this branch, then
  collect startup baseline JSON.
- [x] Capture repeated installed-app samples and calculate median/p95 baseline.
- [x] Record independent verification batch and p95 volatility note.
- [ ] Decide the first optimization target from the slowest measured milestone.
- [ ] Re-run this analysis after the first optimization pass.
