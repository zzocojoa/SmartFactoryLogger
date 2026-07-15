# NSIS Operational Ready Timing Plan

> Version: 1.0.2 | Date: 2026-07-16 | Status: Act Iteration 3
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
- PDCA analysis/report documents and clean package hashes.

### 3.2 Out of Scope

- Server-PC real-device execution of the generated installer.
- Broad startup optimization beyond removing the server-proven synchronous
  diagnostics blocker.
- Requiring every optional sensor field to be finite before the dashboard is
  considered usable.
- Changes to the application's user-visible feature set beyond the package
  identity bump from `1.0.13` to `1.0.14`.

## 4. Requirements

### 4.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | Keep `renderer.dashboard-ready` behavior and existing measurement compatibility. | High | Pending |
| FR-02 | Add a process-unique startup session ID to every Electron startup log event. | High | Pending |
| FR-03 | Record backend readiness after the first successful `/health` response. | High | Pending |
| FR-04 | Record live-data readiness only for `Status=Running` `FactoryData` with finite positive `timestamp_ms`. | High | Pending |
| FR-05 | Emit operational ready once, after all three gates and two animation frames. | High | Pending |
| FR-06 | A timeout must report missing gates and must never be counted as operational ready. | High | Pending |
| FR-07 | Measurement output must include session ID, per-gate elapsed values, main-clock total, launcher-observed total, ready strategy, diagnostic-budget status, and cleanup result; the caller's `TimeoutSec` is the terminal measurement budget. | High | Pending |
| FR-08 | Measurement must fail when an existing app/backend process could contaminate a cold-start sample. | High | Pending |
| FR-09 | Generate a clean PyInstaller backend and NSIS installer with SHA-256 evidence. | High | Pending |
| FR-10 | Set root and frontend package identity consistently to `1.0.14`. | High | Pending |
| FR-11 | The first memory diagnostics snapshot must run immediately in its sampler thread and must not block FastAPI startup or `/health`. | High | Pending |

### 4.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Compatibility | Existing startup event names and `measure_nsis_startup_render.ps1` remain usable. | Existing and new tests |
| Correctness | Synthetic startup data cannot satisfy the live-data gate. | Unit tests with initializing and timestamped snapshots |
| Security | Renderer may emit only allowlisted primitive, bounded telemetry payloads. | Electron bridge contract tests |
| Observability | A failed operational startup identifies the missing gate without fabricating success. | Timeout unit/script tests |
| Performance | Instrumentation does not introduce network requests or change polling intervals. | Code review and startup smoke check |
| Availability | A slow initial memory collector cannot delay FastAPI startup completion. | Blocking-collector regression test and packaged server run |
| Packaging | PyInstaller build must fail closed on dirty or changed Git source. | Provenance gate and clean build log |

## 5. Success Criteria

- [ ] `[AC-01]` Existing visual-ready tests and packaged metric remain compatible.
- [ ] `[AC-02]` Backend health event is recorded exactly once after a successful
  health response.
- [ ] `[AC-03]` `Status=Initializing/Offline/Error`, missing timestamps, zero
  timestamps, NaN, and infinite timestamps do not satisfy live-data readiness.
- [ ] `[AC-04]` A valid timestamped snapshot records first-live-data exactly once.
- [ ] `[AC-05]` Operational ready is independent of gate arrival order, waits for
  two animation frames, and is recorded exactly once.
- [ ] `[AC-06]` Timeout evidence names missing gates and is never accepted as
  operational ready.
- [ ] `[AC-07]` The measurement script correlates one startup session, rejects
  contaminated runs, continues after the 30-second diagnostic event until the
  caller timeout, and returns structured PASS/FAIL JSON.
- [ ] `[AC-08]` Frontend typecheck, lint, focused/full tests, backend checks, and
  PowerShell parser checks pass.
- [ ] `[AC-09]` Clean frontend, PyInstaller, and NSIS builds pass; installer and
  backend SHA-256 values are recorded.
- [ ] `[AC-10]` The generated installer filename and installed application
  metadata identify version `1.0.14` consistently.
- [ ] `[AC-11]` `MemoryService.start()` returns before a deliberately blocked
  initial collector completes, while that collector still starts immediately.

## 6. Schedule

| Phase | Target Date | Status |
|-------|------------|--------|
| Plan | 2026-07-15 | Complete |
| Design | 2026-07-15 | In Progress |
| Implementation | 2026-07-15 | Pending |
| Check / Act | 2026-07-16 | Pending |
| Report / Package | 2026-07-16 | Pending |

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
| Initial memory diagnostics blocks `/health` while hardware worker calls are slow | High | High | Run the first snapshot immediately on the existing sampler thread and log each lifespan startup stage duration. |
| Dirty package records unverifiable source | High | Medium | Commit first and use the existing fail-closed provenance gate. |

## 8. Architecture Considerations

- Electron main remains the only owner of the monotonic startup clock.
- Renderer gate state is local to the renderer startup session and contains no
  sensor values beyond bounded status metadata.
- `timestamp_ms` is authoritative because `PLCService` adds it only when a real
  driver snapshot is composed; the synthetic startup object has no timestamp.
- Operational readiness is an additional metric, not a redefinition of visual
  readiness.
- No persistent schema or migration is required.
- Rollback is a joint revert of the new event allowlist, readiness coordinator,
  call sites, tests, and measurement script. Existing visual timing remains.

## 9. Next Steps

1. Finalize the technical design and state machine.
2. Implement event correlation, readiness gates, and tests.
3. Run gap analysis and correct all blocking gaps.
4. Commit the verified source so the provenance build gate can run.
5. Generate and hash the new backend and NSIS installer.

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-07-15 | Initial final plan | Codex |
| 1.0.1 | 2026-07-16 | Clarified launcher timeout authority after server Act evidence | Codex |
| 1.0.2 | 2026-07-16 | Added Act 3 non-blocking startup requirement from server logs | Codex |
