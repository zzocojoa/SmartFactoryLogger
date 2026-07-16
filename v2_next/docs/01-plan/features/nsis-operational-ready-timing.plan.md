# NSIS Operational Ready Timing Plan

> Version: 1.1.0 | Date: 2026-07-16 | Status: Completed / Server Verified
> Level: Dynamic

---

## 1. Overview

### 1.1 Purpose

Measure the full operator wait from launching the NSIS-installed executable until
the packaged backend responds, the dashboard receives its first non-initial live
factory snapshot, and that data has had an opportunity to paint in the dashboard.

### 1.2 Background

The existing `renderer.dashboard-ready` metric measures the Electron main-module
clock through the first dashboard surface paint. It intentionally does not wait
for backend health or live `/api/data`. A dashboard can therefore be counted as
ready while it still shows `Loading` or `Offline`. Operations need a separate,
strict metric that distinguishes visual shell readiness from usable live-data
readiness without changing the existing startup baseline.

### 1.3 Related Documents

- `docs/01-plan/features/nsis-startup-render-performance.plan.md`
- `docs/02-design/features/nsis-startup-render-performance.design.md`
- `docs/03-analysis/nsis-startup-render-performance.analysis.md`
- `docs/V2/05_운영_배포/build_commit_provenance.md`

## 2. Goals

### 2.1 Primary Goals

- Preserve the existing visual `renderer.dashboard-ready` metric and baseline.
- Record the first successful backend `/health` response in the renderer startup
  timeline.
- Reject synthetic, offline, and error snapshots and record only the first
  `/api/data` response with `Status=Running` and an authoritative positive
  `timestamp_ms`.
- Emit one `renderer.dashboard-operational-ready` event only after backend
  response, live data, and a confirmed animation-frame paint are all complete.
- Add a session identifier so a measurement script cannot mix startup events
  from different Electron processes.
- Provide a PowerShell cold-start measurement that reports both the monotonic
  main clock and the launcher-observed wall-clock duration.
- Keep the backend HTTP lifecycle responsive while the first memory diagnostics
  snapshot observes concurrently initializing physical-device workers.
- Use an explicit IPv4 loopback API base in the packaged renderer so Windows
  IPv6-first `localhost` resolution cannot hide an otherwise-ready backend.
- Bound pre-listen `/health` and `/api/data` requests and keep health at its
  base retry interval until the first success so delayed Uvicorn startup can
  recover within the caller measurement budget.
- During packaged cold start, keep the existing health and live-data pollers
  active until their respective first successful readiness result even when
  the Electron document is hidden or a stale dashboard leader lock exists.
- Remove the server-proven PyInstaller one-file extraction delay by packaging
  the backend as one-dir while preserving the installed executable path.
- Verify the complete installed backend bundle before timing, not only the
  launcher EXE, and bind the bundle to the clean build commit.
- Build a clean PyInstaller backend and NSIS installer from the verified commit.

### 2.2 Non-Goals

- Do not change PLC or SPOT polling intervals, CSV schemas, or device protocol
  behavior.
- Do not make SPOT image completion a blocking operational-ready gate in this
  feature; image readiness remains separately observable.
- Do not change the current dashboard layout or loading UI.
- Do not upload startup telemetry or expose arbitrary Electron IPC.
- Publish this installer as version `1.0.14` so it cannot be confused with the
  previously server-validated `1.0.13` package.

## 3. Scope

### 3.1 In Scope

- Electron startup session correlation and renderer event allowlist updates.
- Renderer readiness coordinator for backend, live data, and paint gates.
- Backend-ready instrumentation from the existing health polling response.
- Live-data instrumentation from the existing metrics polling response.
- Frontend types and unit/contract tests.
- A new packaged operational-ready PowerShell measurement script.
- Non-blocking initial memory diagnostics collection and backend lifecycle-stage
  timing logs.
- Packaged renderer API-base resolution and its unit contract.
- Bounded operational polling transport and first-success retry recovery.
- Packaged startup polling ownership that survives pre-success visibility and
  stale-leader transitions without changing the normal post-success policy.
- PyInstaller one-dir packaging, Electron/portable resource mapping, and exact
  backend bundle integrity verification.
- Physical-server cold-start validation with backend health, real Running data,
  dashboard paint, and full operational-ready elapsed time recorded separately.
- PDCA analysis/report documents and clean package hashes.

### 3.2 Out of Scope

- Broad startup optimization beyond removing the server-proven synchronous
  diagnostics blocker.
- Long-duration device stability validation unrelated to startup readiness.
- Requiring every optional sensor field to be finite before the dashboard is
  considered usable.
- Changes to the application's user-visible feature set beyond the package
  identity bump from `1.0.13` to `1.0.14`.

## 4. Requirements

### 4.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | Keep `renderer.dashboard-ready` behavior and existing measurement compatibility. | High | Complete |
| FR-02 | Add a process-unique startup session ID to every Electron startup log event. | High | Complete |
| FR-03 | Record backend readiness after the first successful `/health` response. | High | Complete |
| FR-04 | Record live-data readiness only for `Status=Running` `FactoryData` with finite positive `timestamp_ms`. | High | Complete |
| FR-05 | Emit operational ready once, after all three gates and two animation frames. | High | Complete |
| FR-06 | A timeout must report missing gates and must never be counted as operational ready. | High | Complete |
| FR-07 | Measurement output must include session ID, per-gate elapsed values, main-clock total, launcher-observed total, ready strategy, diagnostic-budget status, and cleanup result; the caller's `TimeoutSec` is the terminal measurement budget. | High | Complete |
| FR-08 | Measurement must fail when an existing app/backend process could contaminate a cold-start sample. | High | Complete |
| FR-09 | Generate a clean PyInstaller backend and NSIS installer with SHA-256 evidence. | High | Complete |
| FR-10 | Set root and frontend package identity consistently to `1.0.14`. | High | Complete |
| FR-11 | The first memory diagnostics snapshot must run immediately in its sampler thread and must not block FastAPI startup or `/health`. | High | Complete |
| FR-12 | Packaged `file:` renderers must call the local backend through `127.0.0.1`, while explicit environment overrides and browser-relative development behavior remain unchanged. | High | Complete |
| FR-13 | Before first success, `/health` may use an eight-second bound; afterward it returns to two seconds. `/api/data` remains bounded to two seconds, and health retries at the five-second base interval until first success. | High | Complete |
| FR-14 | In packaged Electron startup, health polling must continue until the first successful health response and data polling until the first operational `Status=Running` snapshot, regardless of hidden visibility or a stale leader lock; normal visibility and leader ownership must resume after each first success. | High | Complete |
| FR-15 | Backend diagnostics, fact persistence, and address discovery must not block the event loop or FastAPI readiness. | High | Complete |
| FR-16 | Package the backend as PyInstaller one-dir while preserving `resources/backend/SmartFactoryBackend.exe`. | High | Complete |
| FR-17 | Generate and verify an exact, path-safe manifest for every backend bundle file before starting the measurement clock. | High | Complete |

### 4.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Compatibility | Existing startup event names and `measure_nsis_startup_render.ps1` remain usable. | Existing and new tests |
| Correctness | Synthetic startup data cannot satisfy the live-data gate. | Unit tests with initializing and timestamped snapshots |
| Security | Renderer may emit only allowlisted primitive, bounded telemetry payloads. | Electron bridge contract tests |
| Observability | A failed operational startup identifies the missing gate without fabricating success. | Timeout unit/script tests |
| Performance | Physical-server operational-ready is at or below 30 seconds without changing device polling intervals. | Bundled QA server artifact |
| Availability | A slow initial memory collector cannot delay FastAPI startup completion. | Blocking-collector regression test and packaged server run |
| Recovery | A local request started before Uvicorn listens cannot suspend all later startup polls. | Transport timeout and health first-success retry tests |
| Lifecycle recovery | Packaged pre-success polling cannot be paused by hidden visibility or stale leader state. | Hidden-document and stale-lock hook regression tests |
| Packaging | PyInstaller build fails closed on dirty/changed source and the installed one-dir bundle exactly matches its clean-commit manifest. | Provenance gate, manifest verifier, installed server package |

## 5. Success Criteria

- [x] `[AC-01]` Existing visual-ready tests and packaged metric remain compatible.
- [x] `[AC-02]` Backend health event is recorded exactly once after a successful
  health response.
- [x] `[AC-03]` `Status=Initializing/Offline/Error`, missing timestamps, zero
  timestamps, NaN, and infinite timestamps do not satisfy live-data readiness.
- [x] `[AC-04]` A valid timestamped snapshot records first-live-data exactly once.
- [x] `[AC-05]` Operational ready is independent of gate arrival order, waits for
  two animation frames, and is recorded exactly once.
- [x] `[AC-06]` Timeout evidence names missing gates and is never accepted as
  operational ready.
- [x] `[AC-07]` The measurement script correlates one startup session, rejects
  contaminated runs, continues after the 30-second diagnostic event until the
  caller timeout, and returns structured PASS/FAIL JSON.
- [x] `[AC-08]` Frontend typecheck, lint, focused/full tests, backend checks, and
  PowerShell parser checks pass.
- [x] `[AC-09]` Clean frontend, PyInstaller, and NSIS builds pass; installer and
  backend SHA-256 values are recorded.
- [x] `[AC-10]` The generated installer filename and installed application
  metadata identify version `1.0.14` consistently.
- [x] `[AC-11]` `MemoryService.start()` returns before a deliberately blocked
  initial collector completes, while that collector still starts immediately.
- [x] `[AC-12]` Packaged API resolution returns `http://127.0.0.1:8000`, and
  the replacement package records backend health and live data without the
  Windows `localhost -> ::1` fallback delay.
- [x] `[AC-13]` Startup health uses an eight-second bound, steady-state health
  and all data requests use two seconds, health retries every five seconds
  before first success, and the server recovers within the caller timeout.
- [x] `[AC-14]` A packaged hidden renderer with a stale leader lock continues
  health polling until the first response and live-data polling until the first
  operational snapshot; `Initializing` does not end recovery, and normal hidden
  pause behavior resumes immediately after success.
- [x] `[AC-15]` The physical server records visual-ready, backend health,
  first Running data, and operational-ready as separate milestones.
- [x] `[AC-16]` The installed one-dir bundle exactly matches 1,707 manifest
  entries and the clean build commit.
- [x] `[AC-17]` Physical-server operational-ready completes within 30 seconds
  with no missing milestone, diagnostic timeout, or contaminated session.

## 6. Schedule

| Phase | Target Date | Status |
|-------|------------|--------|
| Plan | 2026-07-15 | Complete |
| Design | 2026-07-15 | Complete |
| Implementation | 2026-07-16 | Complete |
| Check / Act | 2026-07-16 | Complete |
| Report / Package | 2026-07-16 | Complete |

## 7. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Offline/error snapshot is counted as live data | High | High | Require finite positive `timestamp_ms` and exact normalized `Status=Running`. |
| Event order differs across machines | High | Medium | Use an order-independent readiness coordinator and one-shot gates. |
| `requestAnimationFrame` is throttled | Medium | Medium | Record timeout diagnostics but do not fabricate operational readiness. |
| Multiple processes mix one log timeline | High | Medium | Add a process-unique session ID and reject pre-existing processes. |
| Health response arrives before driver data | Low | High | Keep health and data as separate gates. |
| Instrumentation changes runtime behavior | Medium | Low | Reuse existing responses; add no network requests or polling changes. |
| Renderer diagnostic timeout prematurely ends a longer launcher measurement | High | Medium | Treat the 30-second event as evidence only; terminate only on true readiness, process failure, contamination, or caller timeout. |
| Repeated Windows process-handle scans starve startup and `/health` | High | High | Keep the five-second sampler on lightweight process metrics; reserve `memory_full_info`, open-file, and handle scans for explicit snapshots. |
| Local hostname resolution delays the lifespan yield | High | High | Resolve and log local access URLs on a daemon diagnostic thread after scheduling readiness. |
| IPv6-first `localhost` resolution delays each renderer request while Uvicorn listens on IPv4 | High | High | Use the explicit IPv4 loopback address only for packaged/local fallback API resolution. |
| A renderer request opened before Uvicorn listens remains pending and suppresses its recursive retry | High | High | Bound startup health to eight seconds, steady health/data to two seconds, and retain the base health interval before first success. |
| Electron visibility or a stale localStorage leader lock suppresses all retries before backend readiness | High | High | Treat the single packaged renderer as temporary polling owner until each readiness gate first succeeds, then restore the existing pause/leader policy. |
| PyInstaller one-file extraction dominates the user wait before Python starts | High | High | Use one-dir packaging and verify the backend launcher is spawned directly from the installed bundle. |
| Missing or stale one-dir dependency causes partial startup | High | Medium | Verify the exact file set, sizes, per-file hashes, aggregate hash, and clean build commit before timing. |
| Dirty package records unverifiable source | High | Medium | Commit first and use the existing fail-closed provenance gate. |

## 8. Architecture Considerations

- Electron main remains the only owner of the monotonic startup clock.
- Renderer gate state is local to the renderer startup session and contains no
  sensor values beyond bounded status metadata.
- `timestamp_ms` is authoritative because `PLCService` adds it only when a real
  driver snapshot is composed; the synthetic startup object has no timestamp.
- Operational readiness is an additional metric, not a redefinition of visual
  readiness.
- The installed backend entry path remains stable; only its dependency layout
  changes from runtime extraction to the adjacent `_internal` directory.
- The installer SHA is the release trust anchor. The bundle manifest detects
  installed-file drift but is not a substitute for code signing.
- No persistent schema or migration is required.
- Rollback is a joint revert of the new event allowlist, readiness coordinator,
  call sites, tests, and measurement script. Existing visual timing remains.

## 9. Next Steps

1. Preserve the server artifact and release hashes with the completion report.
2. Use the validated installer SHA for deployment; reject superseded packages.
3. Run long-duration device stability validation as a separate release gate.

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-07-15 | Initial final plan | Codex |
| 1.0.1 | 2026-07-16 | Clarified launcher timeout authority after server Act evidence | Codex |
| 1.0.2 | 2026-07-16 | Added Act 3 non-blocking startup requirement from server logs | Codex |
| 1.0.3 | 2026-07-16 | Added Act 5 packaged IPv4 loopback requirement from runtime reproduction | Codex |
| 1.0.4 | 2026-07-16 | Added Act 6 bounded readiness requests and first-success health retry | Codex |
| 1.0.5 | 2026-07-16 | Added Act 7 packaged pre-success polling ownership across visibility and stale locks | Codex |
| 1.0.6 | 2026-07-16 | Added Act 8 lightweight periodic memory sampling and non-blocking address discovery | Codex |
| 1.1.0 | 2026-07-16 | Added one-dir packaging, complete bundle integrity, and final physical-server operational-ready acceptance | Codex |
