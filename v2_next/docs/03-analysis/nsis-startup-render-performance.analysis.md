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
five-sample p95 than the initial run. The first two batches prove measurement
readiness, but the p95 value is sample-size sensitive and should not be treated
as a stable regression threshold yet. Batch C extends the evidence from a single
dashboard-ready metric into a startup timeline breakdown.

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

### Batch C: Timeline Breakdown

Measurement date: 2026-07-05 KST

Execution command:

```powershell
$exe = Join-Path $env:LOCALAPPDATA 'Programs\smart-factory-logger-v2\smart-factory.exe'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\measure_nsis_startup_render.ps1 -ExePath $exe -TimeoutSec 90
```

| Sample | Status | dashboard_ready_elapsed_ms | event_count | cleanup.ok | ready_strategy | surface |
|--------|--------|----------------------------|-------------|------------|----------------|---------|
| 1 | PASS | 661.5 | 16 | true | raf | native |
| 2 | PASS | 608.3 | 16 | true | raf | native |
| 3 | PASS | 589.8 | 16 | true | raf | native |
| 4 | PASS | 627.7 | 16 | true | raf | native |
| 5 | PASS | 658.6 | 16 | true | raf | native |

Batch C summary:

- PASS samples: 5/5
- Cleanup success: 5/5
- Median `dashboard_ready_elapsed_ms`: 627.7 ms
- p95 `dashboard_ready_elapsed_ms`: 661.5 ms
- p95 method: nearest-rank over five samples
- Range: 589.8 ms to 661.5 ms

Milestone intervals below are diagnostic and not strictly additive. Backend
spawn overlaps with window creation and frontend loading. Very small negative
values around DOM and renderer IPC events are treated as event-ordering noise,
not actual negative work.

| Segment | Median ms | p95 ms | Max ms | Classification |
|---------|-----------|--------|--------|----------------|
| `electron.process-start` -> `electron.app-ready` | 76.3 | 81.5 | 81.5 | Electron shell |
| `backend.spawn-start` -> `backend.spawned` | 111.3 | 118.5 | 118.5 | Backend spawn signal |
| `electron.window-create-start` -> `electron.window-created` | 65.8 | 73.8 | 73.8 | Electron shell |
| `electron.load-file-start` -> `renderer.index-boot` | 323.5 | 365.1 | 365.1 | Static asset load / renderer bootstrap |
| `renderer.index-boot` -> `electron.webcontents-dom-ready` | 1.6 | 1.8 | 1.8 | Renderer DOM handoff |
| `electron.webcontents-dom-ready` -> `renderer.index-render` | -0.7 | -0.6 | -0.6 | IPC ordering noise, effectively 0 |
| `renderer.index-render` -> `electron.webcontents-did-finish-load` | 1.5 | 1.6 | 1.6 | Renderer load completion |
| `electron.webcontents-did-finish-load` -> `electron.window-ready-to-show` | 1.1 | 26.9 | 26.9 | Electron show readiness |
| `electron.window-ready-to-show` -> `renderer.dashboard-ready` | 118.9 | 138.2 | 138.2 | Dashboard renderer paint |

Batch C interpretation:

- The dominant measured interval is `electron.load-file-start` to
  `renderer.index-boot`: median 323.5 ms, p95 365.1 ms.
- This interval occurs before the renderer entry module records
  `renderer.index-boot`, so it is closer to file URL asset loading, module graph
  fetch/evaluation, and bootstrap startup than dashboard widget rendering.
- The second meaningful interval is `electron.window-ready-to-show` to
  `renderer.dashboard-ready`: median 118.9 ms, p95 138.2 ms.
- Backend spawn signal is median 111.3 ms, but it overlaps the UI path and the
  current dashboard-ready signal does not wait for backend readiness.
- The installed frontend resources contain about 2.7 MB of JavaScript assets and
  about 0.24 MB of CSS assets. Largest JavaScript chunks are
  `vendor-grafana-scenes`, `vendor-grafana-ui`, `vendor-grafana-data`, `App`,
  `vendor-react`, and `html2canvas.esm`.
- `frontend/vite.config.ts` currently sets `build.modulePreload` to `false`,
  and the generated `index.html` loads only the entry module directly. That makes
  module graph discovery a plausible first experiment for the dominant segment.

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
- Batch C adds a focused timeline run: 5/5 samples passed, median 627.7 ms, p95
  661.5 ms, cleanup 5/5.
- Raw JSON and local-only runtime details are intentionally omitted from this
  document.

## First Improvement Candidate

Target: static asset load / renderer bootstrap before `renderer.index-boot`.

Why this target:

- It is the largest measured startup interval in Batch C: median 323.5 ms, p95
  365.1 ms.
- It precedes dashboard rendering, so optimizing only widget paint would not
  address the largest currently visible delay.
- Backend spawn is not the first target because the measured backend spawn signal
  is smaller and overlaps with frontend loading.

Minimal change plan if optimization is approved:

1. Run a build-only experiment in `frontend/vite.config.ts` by removing the
   explicit `build.modulePreload: false` setting, while keeping the existing
   manual chunks.
2. Rebuild frontend and package/install a fresh NSIS artifact.
3. Re-run at least five installed-app startup samples with
   `scripts/measure_nsis_startup_render.ps1`.
4. Compare Batch C against the experiment, with primary attention on
   `electron.load-file-start` -> `renderer.index-boot` median and p95.
5. Accept the change only if the dominant interval drops by at least 50 ms median
   without chunk-load recovery errors, lint/type/test regressions, or cleanup
   failures.

Rollback path:

- Documentation-only rollback: `git restore docs/03-analysis/nsis-startup-render-performance.analysis.md`.
- Build experiment rollback: restore `frontend/vite.config.ts` to the current
  `modulePreload: false` behavior, rebuild/reinstall the previous artifact, or
  close/revert the PR.

Verification commands for a follow-up optimization patch:

```powershell
node --check main.js
node --check preload.js
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile('scripts\measure_nsis_startup_render.ps1', [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) { $errors | Format-List; exit 1 }
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run test -- startupTelemetry useMemoryViewModel
npm --prefix frontend run build
git diff --check
```

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
5. Start with a small module preload experiment because the measured bottleneck
   is static asset load / renderer bootstrap before `renderer.index-boot`.

## Next Steps

- [x] Build and install a fresh NSIS artifact that includes this branch, then
  collect startup baseline JSON.
- [x] Capture repeated installed-app samples and calculate median/p95 baseline.
- [x] Record independent verification batch and p95 volatility note.
- [x] Decide the first optimization target from the slowest measured milestone.
- [ ] Re-run this analysis after the first optimization pass.
