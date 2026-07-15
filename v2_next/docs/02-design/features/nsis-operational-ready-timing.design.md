# NSIS Operational Ready Timing Design

> Version: 1.0.0 | Date: 2026-07-15 | Status: Final
> Level: Dynamic | Plan: `docs/01-plan/features/nsis-operational-ready-timing.plan.md`

---

## 1. Overview

### 1.1 Purpose

Add a second, strict startup metric for the operator-visible usable state. The
existing `renderer.dashboard-ready` event continues to measure visual shell
paint. The new `renderer.dashboard-operational-ready` event measures the point
at which the backend has responded, a real timestamped factory snapshot exists,
and the dashboard has painted after all required gates were observed.

### 1.2 Design Goals

- Reuse existing `/health` and `/api/data` polling responses; issue no new HTTP
  requests and change no polling interval.
- Keep gate arrival order irrelevant and event emission one-shot under React
  StrictMode.
- Reject the backend's synthetic `Initializing` snapshot deterministically.
- Correlate each log event to one Electron process and one cold-start sample.
- Fail closed on timeout, contaminated process state, or missing milestones.
- Generate a separately identifiable `1.0.14` installer from a clean commit.

## 2. Architecture

### 2.1 System Architecture

```text
PowerShell launcher
  -> Electron main (startup_session_id + monotonic elapsed_ms)
       -> preload constrained IPC bridge
            -> renderer readiness coordinator
                 <- /health result from App/useSystemViewModel
                 <- /api/data result from MetricsDataController
                 <- dashboard paint from Native/Scene surface
            -> allowlisted IPC event
       -> debug_electron.log
  <- session-correlated operational-ready measurement JSON
```

No backend endpoint or response schema changes. Electron main remains the sole
owner of the monotonic startup clock so renderer and main milestones share one
elapsed timeline.

### 2.2 Component Design

#### Electron main

- Create `startupSessionId` once at module evaluation from process ID, epoch,
  and a bounded random suffix.
- Add `session_id` to the top-level JSON of every `STARTUP` log entry.
- Allow only the three new renderer event names:
  `renderer.backend-health-ready`, `renderer.first-live-data`,
  `renderer.dashboard-operational-ready`, plus the timeout evidence event
  `renderer.dashboard-operational-timeout`.
- Continue payload scalar/key/length sanitization and per-name event limits.

#### Renderer readiness coordinator

Store one coordinator object on `window` for StrictMode-safe lifecycle:

```text
backendHealthReady: boolean
liveDataReady: boolean
dashboardPaintReady: boolean
operationalReadyScheduled: boolean
operationalReadyRecorded: boolean
timeoutRecorded: boolean
timeoutId / requestAnimationFrame IDs
```

Public operations:

- `armDashboardOperationalReadyTimeout()` starts one 30-second diagnostic
  deadline when the renderer boots.
- `markBackendHealthReady(health)` accepts the first non-null successful health
  response and emits the backend gate event without sensor values.
- `markFirstLiveDataReady(data)` accepts data only when `timestamp_ms` is finite
  and positive, `Time` is non-empty, and `Status` is not `Initializing`.
- `recordDashboardReadyAfterPaint(...)` preserves the visual event and marks the
  paint gate only for the real two-frame `raf` strategy. Its 5-second fallback
  remains visual telemetry but cannot satisfy operational readiness.
- When all gates are true, the coordinator waits two more animation frames and
  emits operational-ready once. This ensures the final-arriving state update has
  had a paint opportunity, regardless of gate order.
- At 30 seconds, emit the comma-delimited missing gate names. Timeout never
  emits or substitutes operational-ready. A later recovery may still emit the
  true event, but the measurement classifies any pre-ready timeout as failure.

### 2.3 Data Flow

1. PowerShell verifies no `smart-factory` or `SmartFactoryBackend` process is
   running, records launcher UTC, and starts the installed executable.
2. Electron creates a session ID and logs process/window/backend milestones.
3. Renderer arms the operational timeout during index boot.
4. Existing system polling returns `/health`; `App` marks the backend gate.
5. Existing metrics polling returns `/api/data`; `MetricsDataController` marks
   the data gate only if `isOperationalFactoryData` passes.
6. Native or scene dashboard completes two frames; the `raf` path marks paint.
7. The coordinator observes all gates, waits two frames, and emits the final
   event through the constrained preload bridge.
8. The measurement script reads only events after launch with the selected
   process session ID, validates milestones, and writes structured JSON.

## 3. Data Model

### 3.1 Startup Log Entry

```json
{
  "event": "renderer.dashboard-operational-ready",
  "session_id": "<bounded process-unique identifier>",
  "elapsed_ms": 1234.5,
  "payload": {
    "ready_strategy": "raf",
    "required_gates": "backend_health,live_data,dashboard_paint"
  }
}
```

`session_id` is local correlation metadata, not an authentication token. It is
bounded and contains no machine name, user name, sensor value, or network data.

### 3.2 Gate Events

| Event | Required payload | Acceptance rule |
|-------|------------------|-----------------|
| `renderer.backend-health-ready` | `running`, `driver_connected` | first successful parsed `/health` response |
| `renderer.first-live-data` | `status`, `timestamp_present` | positive finite timestamp, non-empty time, non-initial status |
| `renderer.dashboard-ready` | existing payload | visual compatibility; only `raf` marks paint gate |
| `renderer.dashboard-operational-timeout` | `missing_gates`, `timeout_ms` | diagnostic only |
| `renderer.dashboard-operational-ready` | `ready_strategy`, `required_gates` | all gates + two frames, exactly once |

### 3.3 Measurement Artifact

```text
status
exe_path / process_id / startup_session_id
started_at_utc / operational_ready_timestamp_utc
backend_health_ready_elapsed_ms
first_live_data_elapsed_ms
dashboard_ready_elapsed_ms
operational_ready_elapsed_ms
launcher_observed_operational_ready_ms
ready_strategy / missing_milestones / contamination
cleanup / events
```

## 4. API Specification

### 4.1 Existing Endpoints

| Method | Endpoint | Usage |
|--------|----------|-------|
| GET | `/health` | Existing successful response satisfies backend gate |
| GET | `/api/data` | Existing timestamped real snapshot satisfies data gate |

No endpoint, request, response, CSV, or persistence migration is introduced.

### 4.2 Renderer IPC Contract

The existing `sfl:record-startup-event` IPC handler is extended only by the new
allowlist entries. Payloads remain flat primitive maps, limited to 16 keys, key
length 64, and string length 200. Unknown names and excess repeats are rejected.

## 5. Implementation Plan

### 5.1 Files

| File | Change |
|------|--------|
| `main.js` | session ID and event allowlist |
| `frontend/src/shared/types.ts` | new renderer event names |
| `frontend/src/shared/startup/startupTelemetry.ts` | gate coordinator and validators |
| `frontend/src/shared/startup/startupTelemetry.test.ts` | gate/order/timeout/one-shot tests |
| `frontend/src/index.tsx` | arm timeout during renderer boot |
| `frontend/src/App.tsx` | mark first successful health response |
| `frontend/src/domains/FacilityData/components/MetricsDataController.tsx` | mark first valid live snapshot |
| `backend/tests/test_electron_startup_timing_contract.py` | main/renderer wiring contract |
| `scripts/measure_nsis_operational_ready.ps1` | cold-start session-correlated measurement |
| root/frontend package manifests | version `1.0.14` |

### 5.2 Implementation Order

1. Add shared event types, coordinator, and unit tests.
2. Wire existing health/data/paint responses without adding requests.
3. Add main-process session correlation and bridge contract tests.
4. Add PowerShell cold-start measurement and parser self-check.
5. Run focused then full checks and correct gaps.
6. Commit the complete source/docs, confirm clean status, build frontend,
   PyInstaller, and NSIS, then record SHA-256 evidence.

## 6. Test Plan

### 6.1 Unit Tests

- Bridge unavailable remains a harmless no-op.
- Health and live-data gate events are emitted exactly once.
- Missing/zero/NaN/infinite timestamp, blank time, and `Initializing` status are
  rejected; a real timestamped snapshot is accepted.
- Every permutation of the three gates produces one operational-ready event
  only after two frames.
- Visual timeout fallback does not satisfy paint.
- Operational timeout records exact missing gates and never fabricates ready.

### 6.2 Contract and Integration Tests

- Electron allowlist includes all required events and still sanitizes payloads.
- `App`, controller, and index contain their expected readiness call sites.
- PowerShell script parses under strict mode and a synthetic log fixture proves
  session correlation, milestone PASS, timeout FAIL, and contamination FAIL.
- Existing frontend startup tests, full frontend test/typecheck/lint, backend
  ruff/mypy/unittest, and `git diff --check` pass.

### 6.3 Packaging Verification

- Git working tree is clean before PyInstaller provenance generation.
- Bundled build commit equals clean source HEAD.
- Installer filename reports `Setup 1.0.14.exe`.
- SHA-256 is recorded for installer and packaged backend.
- Measurement script is included as a QA resource when required by packaging.

## 7. Security and Operations

- No secrets, credentials, URLs, raw data values, or arbitrary payload objects
  enter startup telemetry.
- No new renderer privilege or generic IPC channel is added.
- Failure mode is explicit: timeout/missing gate returns non-zero and preserves
  diagnostic events; it cannot report PASS.
- Observability impact is local startup log growth of at most five bounded events
  per process.
- Migration risk is none.
- Rollback is one joint revert of event names, coordinator/call sites, tests,
  script, and version metadata; the existing visual-ready metric remains usable.

## 8. Requirement Traceability

| Requirement | Design section | Validation |
|-------------|----------------|------------|
| FR-01 | 2.2 renderer coordinator | existing startup unit tests |
| FR-02 | 2.2 Electron main | main contract + script fixture |
| FR-03 | 2.3 step 4 | health one-shot unit/contract test |
| FR-04 | 2.2 validator | invalid/valid data matrix |
| FR-05 | 2.2 coordinator | gate permutation/frame tests |
| FR-06 | 2.2 timeout | fake-timer timeout tests |
| FR-07 | 3.3 | PowerShell fixture/parser test |
| FR-08 | 2.3 step 1 | process contamination test |
| FR-09 | 6.3 | clean build and SHA evidence |
| FR-10 | 6.3 | manifest and artifact-name checks |

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-07-15 | Final implementation design | Codex |
