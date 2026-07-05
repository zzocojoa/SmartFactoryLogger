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

### Batch D: modulePreload Experiment Result

Measurement date: 2026-07-05 KST

Experiment:

- Temporarily removed `build.modulePreload: false` from `frontend/vite.config.ts`
  and kept the existing manual chunks.
- `npm --prefix frontend run build` generated three
  `rel="modulepreload"` links in `index.html`.
- A fresh NSIS installer was built and installed. Installer SHA256:
  `D36EB43BE978D012CA7B687BA7BFF3499FFB24C02859B2CF67FB91E7F83D185F`.
- The installed frontend `index.html` contained three modulepreload links.
  Installed frontend `index.html` SHA256:
  `B741517E51F9A85F078D9A9AE942EB01F7840A9008D127F92651DBB180BEFB92`.
- The installed Electron launcher exe SHA256 stayed
  `B812BC91D14E1E2A8A54990C4A46DA1A7A630C3EA47A9939E7640D34F4C79100`;
  this is expected because this experiment changes packaged frontend
  resources, not the launcher binary.

| Sample | Status | dashboard_ready_elapsed_ms | `load-file-start` -> `index-boot` ms | `ready-to-show` -> `dashboard-ready` ms | cleanup.ok | ready_strategy | surface |
|--------|--------|----------------------------|--------------------------------------|-----------------------------------------|------------|----------------|---------|
| 1 | PASS | 859.5 | 470.6 | 189.8 | true | raf | native |
| 2 | PASS | 618.0 | 317.7 | 130.3 | true | raf | native |
| 3 | PASS | 645.7 | 354.3 | 122.9 | true | raf | native |
| 4 | PASS | 620.1 | 311.0 | 99.8 | true | raf | native |
| 5 | PASS | 638.6 | 336.5 | 127.6 | true | raf | native |

Batch D summary:

- PASS samples: 5/5
- Cleanup success: 5/5
- Median `dashboard_ready_elapsed_ms`: 638.6 ms
- p95 `dashboard_ready_elapsed_ms`: 859.5 ms
- Median `electron.load-file-start` -> `renderer.index-boot`: 336.5 ms
- p95 `electron.load-file-start` -> `renderer.index-boot`: 470.6 ms
- Chunk recovery / chunk-load / `did-fail-load` matches during the batch: 0

Decision:

- Rejected. Batch C median for the dominant segment was 323.5 ms. Batch D was
  336.5 ms, a 13.0 ms regression instead of the required 50 ms improvement.
- The code experiment was rolled back by restoring `modulePreload: false`.
- After rejection, the restored baseline frontend was rebuilt, repackaged, and
  reinstalled. The restored installed frontend `index.html` had 0 modulepreload
  links and SHA256
  `50CC9675ACD76E0C19D7D3594E8A1F16DFB4C9E7F45700B591490974E92AE026`.
- Do not ship the modulepreload change without stronger evidence from a
  different implementation or a larger sample set.

### Batch E Candidate: Settings Modal Entry Split

Implementation date: 2026-07-05 KST

Candidate:

- Keep `frontend/vite.config.ts` `modulePreload: false`.
- Split `SettingsModalContainer` out of the initial `App` module graph with
  `React.lazy`.
- Load the settings modal chunk only after `settingsOpen=true`.

Why this candidate:

- Batch C and D both point to `electron.load-file-start` ->
  `renderer.index-boot` as the first optimization target.
- Settings is not part of the initial dashboard surface, but the closed modal
  container imported the large settings form graph into the initial `App`
  module.
- This is a smaller compatibility risk than changing preload behavior because
  it preserves existing manual chunking and only defers a user-opened modal.

Build-only evidence:

- Baseline frontend build before the split produced `App-CgQn970h.js` at
  317.58 kB.
- Post-change frontend build produced `SettingsModalContainer-h2XaJKXG.js` at
  128.52 kB and reduced the initial `App` chunk to `App-CYxoG87f.js` at
  189.00 kB.
- This is build-only evidence. Installed-app startup improvement is not proven
  until a fresh NSIS artifact is measured.

Acceptance gate before merge:

- `npm --prefix frontend run typecheck`
- `npm --prefix frontend run lint`
- `npm --prefix frontend run test -- App.localStorage startupTelemetry useMemoryViewModel`
- `npm --prefix frontend run build`
- Fresh NSIS build/install and at least five startup samples using
  `scripts/measure_nsis_startup_render.ps1`
- Accept only if installed-app median for `electron.load-file-start` ->
  `renderer.index-boot` improves versus Batch C without chunk-load failures,
  settings modal regressions, or cleanup failures.

Batch E installed-app measurement:

- Measurement date: 2026-07-05 KST
- Fresh NSIS installer: `smart-factory-logger-v2 Setup 1.0.11.exe`
- Installer SHA256:
  `A9317B5C98F20B9814267BDB1F22F4B74A2E3F93A2CA5246FE361393FD9FA6CB`
- Build-only split evidence before measurement:
  `SettingsModalContainer-h2XaJKXG.js` 128.52 kB and `App-CYxoG87f.js`
  189.00 kB.

Sanitized Batch E samples:

| Run | Status | `dashboard_ready_elapsed_ms` | `electron.load-file-start` -> `renderer.index-boot` ms | Event count | Cleanup |
|-----|--------|------------------------------|--------------------------------------------------------|-------------|---------|
| 1 | PASS | 1645.5 | 1134.5 | 16 | true |
| 2 | PASS | 637.0 | 330.3 | 16 | true |
| 3 | PASS | 625.5 | 325.8 | 16 | true |
| 4 | PASS | 660.0 | 358.2 | 16 | true |
| 5 | PASS | 685.2 | 367.9 | 16 | true |

Batch E summary:

- PASS samples: 5/5
- Cleanup success: 5/5
- Median `dashboard_ready_elapsed_ms`: 660.0 ms
- p95 `dashboard_ready_elapsed_ms`: 1645.5 ms
- Median `electron.load-file-start` -> `renderer.index-boot`: 358.2 ms
- p95 `electron.load-file-start` -> `renderer.index-boot`: 1134.5 ms
- p95 method: nearest-rank over five samples
- Chunk recovery / chunk-load / `did-fail-load` matches during the current
  batch: 0

Decision:

- Rejected. Batch C median for the dominant segment was 323.5 ms. Batch E was
  358.2 ms, a 34.7 ms regression instead of the required 50 ms improvement.
- Batch E p95 for the same segment was 1134.5 ms versus Batch C p95 365.1 ms.
  The first fresh-install run dominated that tail, but it still fails the
  acceptance gate.
- The Settings modal entry split code was rolled back. Keep this as a
  docs-only failed experiment record.
- Do not ship this split without a different implementation and a larger
  installed-app sample set.

### Batch F: Renderer Startup Breakdown Instrumentation

Measurement date: 2026-07-05 KST

Candidate:

- Instrument startup only. Do not apply another optimization yet.
- Add renderer milestones for App lazy import, App module evaluation, App render,
  native dashboard surface lazy import, native surface module evaluation, native
  surface render, and actual metrics polling interval resolution.
- Extend `scripts/measure_nsis_startup_render.ps1` to return a
  `startup_intervals` object so repeated installed-app runs can be compared
  without post-processing raw local paths or process ids.

Fresh NSIS artifact:

- Installer: `smart-factory-logger-v2 Setup 1.0.11.exe`
- Installer SHA256:
  `BC42E43A2F56B7ADF4FE950556F526FE002274F8292CF0D45C7A9507980D2165`

Sanitized Batch F samples:

| Run | Status | dashboard ms | `load-file` -> `index-boot` ms | App import ms | App module eval ms | App render ms | Native import ms | Native render ms | Surface paint gap ms | Polling interval ms | Events | Cleanup |
|-----|--------|--------------|--------------------------------|---------------|--------------------|---------------|------------------|------------------|----------------------|---------------------|--------|---------|
| 1 | PASS | 659.8 | 343.6 | 44.7 | 41.4 | 49.4 | 9.1 | 27.3 | 48.8 | 500 | 27 | true |
| 2 | PASS | 681.7 | 341.0 | 44.2 | 41.9 | 49.3 | 8.6 | 31.3 | 49.9 | 500 | 27 | true |
| 3 | PASS | 650.7 | 322.7 | 42.7 | 41.7 | 53.2 | 6.7 | 32.7 | 50.1 | 500 | 27 | true |
| 4 | PASS | 711.8 | 347.9 | 44.9 | 41.4 | 52.7 | 8.0 | 36.9 | 52.2 | 500 | 27 | true |
| 5 | PASS | 692.3 | 354.5 | 42.7 | 41.6 | 48.9 | 8.8 | 24.9 | 51.1 | 500 | 27 | true |

Batch F summary:

- PASS samples: 5/5
- Cleanup success: 5/5
- Required renderer breakdown milestones: 5/5 complete
- Median `dashboard_ready_elapsed_ms`: 681.7 ms
- p95 `dashboard_ready_elapsed_ms`: 711.8 ms
- Median `electron.load-file-start` -> `renderer.index-boot`: 343.6 ms
- p95 `electron.load-file-start` -> `renderer.index-boot`: 354.5 ms
- Median App import: 44.2 ms
- Median App import start -> App module evaluated: 41.6 ms
- Median App module evaluated -> App import end: 2.3 ms
- Median App render: 49.4 ms
- Median native surface import: 8.6 ms
- Median native surface render: 31.3 ms
- Median native surface render end -> dashboard ready: 50.1 ms
- Median `renderer.index-render` -> `renderer.dashboard-ready`: 152.2 ms
- Metrics polling interval recorded by the dashboard controller: 500 ms
- p95 method: nearest-rank over five samples

Decision:

- Optimization is still on hold. Batch F proves the new milestones work, but it
  does not identify a single safe optimization candidate with enough measured
  headroom to claim a 50 ms installed-app improvement.
- The dominant measured interval remains `electron.load-file-start` ->
  `renderer.index-boot`: Batch C median 323.5 ms versus Batch F median
  343.6 ms. Batch F is an instrumentation branch, not an optimization branch,
  so this should be treated as continued evidence that pre-`index-boot` asset
  loading / entry bootstrap needs finer measurement, not as an improvement.
- App import/module evaluation is now visible at about 44.2 ms median, with most
  of that in App module evaluation. App render is about 49.4 ms median. Native
  surface import and render are smaller at about 8.6 ms and 31.3 ms median.
- Do not retry modulepreload or Settings modal entry split from this evidence.
  The next optimization attempt should wait until either pre-`index-boot`
  asset/bootstrap work is measured more directly or a candidate can show a
  larger installed-app median headroom than this Batch F breakdown.

### Batch G: Independent PR Verification

Measurement date: 2026-07-05 KST

Verification scope:

- Independently rebuild the frontend production bundle and local NSIS installer
  from commit `d054533be2796ec2c3b737c49352f4914d3248dd`.
- Fresh-install the generated NSIS artifact and run
  `scripts/measure_nsis_startup_render.ps1` five times against the installed
  executable.
- Verify `status=PASS`, `cleanup.ok=true`, and
  `startup_intervals.missing_required_milestones=[]` for every sample.
- Record only sanitized timing summaries here. Raw local paths and process ids
  remain in uncommitted temporary measurement files.

Fresh NSIS artifact:

- Installer: `smart-factory-logger-v2 Setup 1.0.11.exe`
- Installer SHA256:
  `0EC058095B518EADAC10B7FBB138635AD3BB37A9DBDE49A135CCE430427025E7`

Sanitized Batch G samples:

| Run | Status | dashboard ms | `load-file` -> `index-boot` ms | App import ms | App module eval ms | App render ms | Native import ms | Native render ms | Surface paint gap ms | Polling interval ms | Events | Missing milestones | Cleanup |
|-----|--------|--------------|--------------------------------|---------------|--------------------|---------------|------------------|------------------|----------------------|---------------------|--------|--------------------|---------|
| 1 | PASS | 1357.2 | 902.5 | 82.4 | 79.1 | 142.5 | 47.8 | 82.1 | 10.2 | 500 | 27 | 0 | true |
| 2 | PASS | 726.8 | 383.5 | 45.2 | 44.0 | 55.1 | 10.8 | 31.7 | 57.1 | 500 | 27 | 0 | true |
| 3 | PASS | 669.6 | 350.4 | 41.2 | 39.5 | 43.4 | 8.5 | 24.9 | 45.0 | 500 | 27 | 0 | true |
| 4 | PASS | 699.1 | 361.5 | 44.2 | 43.0 | 49.2 | 8.3 | 28.0 | 56.5 | 500 | 27 | 0 | true |
| 5 | PASS | 642.7 | 331.5 | 38.8 | 37.9 | 45.2 | 8.6 | 23.4 | 47.9 | 500 | 27 | 0 | true |

Batch G summary:

- PASS samples: 5/5
- Cleanup success: 5/5
- Required renderer breakdown milestones: 5/5 complete
- `missing_required_milestones=[]`: 5/5
- Median `dashboard_ready_elapsed_ms`: 699.1 ms
- p95 `dashboard_ready_elapsed_ms`: 1357.2 ms
- Median `electron.load-file-start` -> `renderer.index-boot`: 361.5 ms
- p95 `electron.load-file-start` -> `renderer.index-boot`: 902.5 ms
- Median App import: 44.2 ms
- Median App import start -> App module evaluated: 43.0 ms
- Median App render: 49.2 ms
- Median native surface import: 8.6 ms
- Median native surface render: 28.0 ms
- Median native surface render end -> dashboard ready: 47.9 ms
- Metrics polling interval recorded by the dashboard controller: 500 ms
- p95 method: nearest-rank over five samples

Independent verification decision:

- Merge-ready from the installed-app measurement perspective: the current
  instrumentation branch produced five PASS samples, no missing required
  renderer milestones, and successful process cleanup in all five runs.
- The first Batch G run is a cold-start outlier and keeps p95 volatile at this
  sample size. Treat the Batch G median as the primary readiness signal and keep
  p95 as a caveat until a larger sample set is collected.
- This remains an instrumentation change only. It should not be interpreted as
  a startup performance improvement.

### Batch H: Pre-index-boot Low-level Instrumentation

Measurement date: 2026-07-05 KST

Measurement scope:

- Add renderer-side timing payloads to startup events so main-process receipt
  timing can be compared with renderer clock timing.
- Add pre-`renderer.index-boot` milestones:
  `renderer.preload-start`, `renderer.preload-bridge-exposed`, and
  `renderer.index-html-inline-script`.
- Tighten the NSIS measurement gate so a run that reaches
  `renderer.dashboard-ready` but misses required milestones returns
  `status=MISSING_MILESTONES` with a non-zero exit code.
- Record only sanitized timing summaries here. Raw local paths, process ids,
  and temporary measurement output remain uncommitted.

Fresh NSIS artifact:

- Installer: `smart-factory-logger-v2 Setup 1.0.11.exe`
- Installer SHA256:
  `6E92711FFC3726D30A565030939127387866F548C0B6D5C57BB57FB393972709`

Sanitized Batch H samples:

| Run | Status | dashboard ms | `load-file` -> preload ms | preload -> bridge ms | bridge -> HTML inline ms | HTML inline -> `index-boot` ms | renderer clock preload -> boot ms | `load-file` -> `index-boot` ms | Events | Missing milestones | Cleanup |
|-----|--------|--------------|----------------------------|----------------------|--------------------------|--------------------------------|-----------------------------------|--------------------------------|--------|--------------------|---------|
| 1 | PASS | 763.1 | 166.3 | 0.9 | 217.1 | 21.0 | 239.1 | 405.3 | 30 | 0 | true |
| 2 | PASS | 708.5 | 139.7 | 1.5 | 212.7 | 21.0 | 235.2 | 374.9 | 30 | 0 | true |
| 3 | PASS | 751.6 | 162.5 | 1.0 | 208.3 | 20.1 | 229.5 | 391.9 | 30 | 0 | true |
| 4 | PASS | 666.7 | 128.1 | 0.9 | 189.1 | 21.1 | 211.1 | 339.2 | 30 | 0 | true |
| 5 | PASS | 723.4 | 141.9 | 0.8 | 202.6 | 20.1 | 223.5 | 365.4 | 30 | 0 | true |

Batch H summary:

- PASS samples: 5/5
- Cleanup success: 5/5
- Required pre-index and renderer breakdown milestones: 5/5 complete
- `missing_required_milestones=[]`: 5/5
- Median `dashboard_ready_elapsed_ms`: 723.4 ms
- p95 `dashboard_ready_elapsed_ms`: 763.1 ms
- Median `electron.load-file-start` -> `renderer.preload-start`: 141.9 ms
- Median `renderer.preload-start` -> `renderer.preload-bridge-exposed`:
  0.9 ms
- Median `renderer.preload-bridge-exposed` ->
  `renderer.index-html-inline-script`: 208.3 ms
- Median `renderer.index-html-inline-script` -> `renderer.index-boot`:
  21.0 ms
- Median renderer-clock `renderer.preload-start` ->
  `renderer.index-boot`: 229.5 ms
- Median `electron.load-file-start` -> `renderer.index-boot`: 374.9 ms
- p95 `electron.load-file-start` -> `renderer.index-boot`: 405.3 ms
- p95 method: nearest-rank over five samples

Batch H decision:

- Measurement gate passed: five installed-app samples reached dashboard ready,
  reported no missing required milestones, and cleaned up successfully.
- The dominant newly measured pre-index segment is
  `renderer.preload-bridge-exposed` -> `renderer.index-html-inline-script`
  at 208.3 ms median. This likely includes file URL HTML/resource parsing
  before the module script body starts, but this remains a measurement result,
  not a confirmed optimization target.
- `renderer.index-html-inline-script` -> `renderer.index-boot` is only
  21.0 ms median, so the previous pre-`index-boot` gap is not mostly module
  body work after the inline script.
- Renderer-clock `renderer.preload-start` -> `renderer.index-boot` is
  229.5 ms median, which helps separate renderer-side timeline from
  main-process IPC receipt timing.
- Do not restart modulepreload or Settings split work from this evidence. The
  next investigation should target lower-level HTML/resource parse or file URL
  resource loading visibility before another optimization attempt.

## Implemented Items

- [x] Electron main logs `STARTUP` JSON lines with `elapsed_ms`.
- [x] Electron lifecycle events include process start, app ready, backend spawn,
  window creation, load-file start, DOM ready, did-finish-load, and
  ready-to-show.
- [x] Renderer events include `renderer.index-boot`, `renderer.index-render`,
  App import/module/render milestones, native dashboard surface
  import/module/render milestones, metrics polling interval resolution, and
  `renderer.dashboard-ready`.
- [x] Pre-index renderer events include preload start, preload bridge exposure,
  and the inline HTML script before the module entry body starts.
- [x] Renderer startup event payloads include renderer clock timing fields for
  same-clock interval analysis.
- [x] Main process validates renderer event names and bounds primitive payloads.
- [x] Preload exposes `recordStartupEvent` without arbitrary IPC forwarding.
- [x] Existing memory bridge remains present.
- [x] Shared TypeScript types cover startup event names, payload, and result.
- [x] `NativeDashboardSurface` emits dashboard-ready after paint scheduling.
- [x] `DashboardSceneSurface` emits dashboard-ready for edit-mode scene usage.
- [x] Frontend helper handles browser fallback, RAF timeout fallback, and
  deduplicates events.
- [x] `scripts/measure_nsis_startup_render.ps1` launches an exe, returns
  dashboard-ready elapsed time and startup interval breakdowns as JSON, and
  reports cleanup status.
- [x] The NSIS measurement script fails with `MISSING_MILESTONES` when
  dashboard-ready is observed without the required startup milestone set.

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
- [x] Renderer breakdown Batch F: 5 PASS samples, median 681.7 ms, p95
  711.8 ms, cleanup 5/5, required renderer milestones 5/5 complete.
- [x] Independent PR verification Batch G: 5 PASS samples, median 699.1 ms,
  p95 1357.2 ms, cleanup 5/5,
  `startup_intervals.missing_required_milestones=[]` 5/5.
- [x] Pre-index-boot Batch H: 5 PASS samples, median 723.4 ms, p95
  763.1 ms, cleanup 5/5,
  `startup_intervals.missing_required_milestones=[]` 5/5, renderer-clock
  preload-to-boot median 229.5 ms.

## Recommendations

1. Use the repeated fresh installed-app baseline as readiness evidence before
   choosing a performance optimization target.
2. Confirm future samples report successful cleanup, or intentionally use
   `-KeepRunning` only for manual observation.
3. Capture a larger cold-start sample set before setting p95-based regression
   thresholds or claiming p95 improvement.
4. Re-capture at least five cold-start samples after changing startup ordering
   or bundle composition.
5. Do not ship the default modulepreload experiment or the Settings modal entry
   split. Both failed the installed NSIS measurement gate.
6. Keep optimization on hold until a candidate has clearer installed-app
   headroom. Batch H shows the largest newly measured pre-index segment is
   before the inline HTML script reaches the module entry body.
7. Investigate lower-level HTML/resource parse or file URL resource loading
   visibility before changing bundle composition again.

## Next Steps

- [x] Build and install a fresh NSIS artifact that includes this branch, then
  collect startup baseline JSON.
- [x] Capture repeated installed-app samples and calculate median/p95 baseline.
- [x] Record independent verification batch and p95 volatility note.
- [x] Decide the first optimization target from the slowest measured milestone.
- [x] Run the first modulepreload optimization pass and document rejection.
- [x] Select a new optimization candidate for the static asset load / renderer
  bootstrap segment.
- [x] Build and measure the Settings modal entry split in a fresh installed
  NSIS artifact.
- [x] Add renderer startup breakdown milestones and measure a fresh installed
  NSIS artifact.
- [x] Design and run a lower-level pre-`renderer.index-boot` measurement before
  choosing another optimization.
- [ ] Investigate HTML/resource parse and file URL resource loading visibility
  before the inline HTML script runs.
