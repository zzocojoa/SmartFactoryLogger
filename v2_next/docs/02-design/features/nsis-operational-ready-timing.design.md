# NSIS Operational Ready Timing Design

> Version: 1.0.6 | Date: 2026-07-16 | Status: Act Iteration 8
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
- Reject `Initializing`, `Offline`, and `Error` snapshots deterministically.
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
elapsed timeline. The backend lifespan must not synchronously collect the first
memory diagnostics snapshot: `MemoryService.start()` starts its sampler thread,
and that thread performs the first snapshot immediately before its first wait.
The packaged `file:` renderer resolves its API base to
`http://127.0.0.1:8000`; browser development remains relative and an explicit
`VITE_API_BASE_URL` remains authoritative. The two readiness transports bound
each local request to two seconds. Health uses the existing five-second base
interval until its first success, after which the existing outage backoff
policy resumes unchanged. Live data keeps its existing worker interval and
backoff policy; only a pending request is now bounded. During packaged startup,
the single Electron renderer remains a temporary polling owner until health has
first succeeded and an operational `Status=Running` snapshot has first arrived.
Hidden visibility and a stale dashboard leader lock therefore cannot suppress
those two readiness paths. Each path returns to the existing visibility and
leader policy immediately after its own first success.

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
  and positive, `Time` is non-empty, and normalized `Status` is exactly
  `Running`. This prevents a timestamped offline/error sample from satisfying
  the operational gate.
- `recordDashboardReadyAfterPaint(...)` preserves the visual event and marks the
  paint gate only for the real two-frame `raf` strategy. Its 5-second fallback
  remains visual telemetry but cannot satisfy operational readiness.
- When all gates are true, the coordinator waits two more animation frames and
  emits operational-ready once. This ensures the final-arriving state update has
  had a paint opportunity, regardless of gate order.
- At 30 seconds, emit the comma-delimited missing gate names. The event is a
  diagnostic budget marker and never emits or substitutes operational-ready.
  A later recovery may still emit the true event. The launcher continues until
  true readiness or its caller-supplied `TimeoutSec`; it records whether the
  30-second diagnostic budget was exceeded.

#### Backend startup availability

- Preserve the existing memory snapshot content and collection cadence.
- Move only the initial `capture_snapshot()` call from the FastAPI lifespan
  caller into `MemorySampler`; collect immediately, then wait the configured
  interval between subsequent samples.
- `MemoryService.start()` must return after thread creation even if a collector
  is blocked. Shutdown remains bounded by the existing two-second join.
- Record elapsed time for each synchronous lifespan start stage so a future
  server delay identifies the responsible service without raw device values.

#### Packaged startup polling ownership

- Detect packaged startup only through the constrained Electron preload bridge;
  browser and multi-tab development behavior is unchanged.
- Health recovery remains pending until the first non-null `/health` result.
- Live-data recovery remains pending until `isOperationalFactoryData()` accepts
  a timestamped `Status=Running` snapshot. `Initializing` never ends recovery.
- While pending, the packaged renderer may replace a stale local leader lock and
  continue the existing poller even when `document.visibilityState` is hidden.
- No additional timer, request, endpoint, or interval is introduced. After the
  first success, the existing hidden pause, leader heartbeat, and outage backoff
  behavior applies without exception.

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
   process session ID. A 30-second diagnostic event is retained but is not a
   terminal condition; the script waits for true readiness until `TimeoutSec`,
   then validates milestones and writes structured JSON.

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
| `renderer.first-live-data` | `status`, `timestamp_present` | positive finite timestamp, non-empty time, exact `Status=Running` |
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
operational_timeout_observed / diagnostic_budget_status
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
| `backend/Observability/memory_service.py` | lightweight periodic sample; expensive process details only on explicit snapshot |
| `backend/app.py` | backend lifespan stage timing and non-blocking local-address diagnostics |
| `backend/tests/test_memory_service.py` | blocking-collector and lightweight-periodic-sample regressions |
| `backend/tests/test_frontend_routing_health.py` | address-discovery readiness isolation regression |
| `frontend/src/shared/api/client.mapper.ts` | packaged IPv4 loopback API base |
| `frontend/src/shared/api/client.mapper.test.ts` | packaged and development resolution contracts |
| `frontend/src/shared/api/pollingRequest.ts` | bounded readiness request timeout |
| readiness transports and tests | timeout wiring and first-success recovery |
| `frontend/src/domains/Observability/hooks/useSystemViewModelEffects.ts` | Packaged health polling ownership until first success |
| `frontend/src/domains/FacilityData/hooks/useMetricsViewModelEffects.ts` | Packaged operational-data polling ownership until first Running snapshot |
| corresponding hook tests | Hidden-document, stale-lock, Initializing, and post-success pause regressions |
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
- Missing/zero/NaN/infinite timestamp, blank time, and
  `Initializing/Offline/Error` statuses are rejected; a timestamped `Running`
  snapshot is accepted.
- Every permutation of the three gates produces one operational-ready event
  only after two frames.
- Visual timeout fallback does not satisfy paint.
- Operational timeout records exact missing gates and never fabricates ready.

### 6.2 Contract and Integration Tests

- Electron allowlist includes all required events and still sanitizes payloads.
- `App`, controller, and index contain their expected readiness call sites.
- PowerShell script parses under strict mode and a synthetic log fixture proves
  session correlation, milestone PASS, delayed recovery after the diagnostic
  marker, timeout FAIL, and contamination FAIL.
- A collector held on a synchronization event begins immediately, while
  `MemoryService.start()` returns before the collector is released.
- Existing frontend startup tests, full frontend test/typecheck/lint, backend
  ruff/mypy/unittest, and `git diff --check` pass.
- A transport contract proves `/health` and `/api/data` receive the two-second
  bound, and a fake-timer hook test proves repeated pre-success health failures
  remain at the five-second base interval before recovery.
- Packaged hook regressions start hidden with a stale leader lock, prove health
  retries until success, prove `Initializing` does not stop data polling, and
  prove hidden polling stops after the first operational snapshot.

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
- Failure mode is explicit: absence of true readiness at the caller deadline or
  a missing required milestone returns non-zero and preserves diagnostic events;
  a diagnostic marker alone cannot fabricate PASS.
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
| FR-11 | 2.2 backend startup availability | blocking-collector regression and server package timing |
| FR-12 | 2.1 packaged API base | mapper unit test and packaged operational-ready timing |
| FR-13 | 2.1 bounded local polling | transport and first-success retry tests |
| FR-14 | 2.2 packaged startup polling ownership | hidden/stale-lock hook regressions and server package timing |
| FR-15 | 2.2 backend observability isolation | process-probe and address-discovery regressions plus server package timing |

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-07-15 | Final implementation design | Codex |
| 1.0.1 | 2026-07-16 | Made caller timeout terminal and renderer timeout diagnostic | Codex |
| 1.0.2 | 2026-07-16 | Moved initial memory snapshot off the lifespan caller contract | Codex |
| 1.0.3 | 2026-07-16 | Added packaged IPv4 loopback API contract | Codex |
| 1.0.4 | 2026-07-16 | Bounded pre-listen readiness requests and first-success health retries | Codex |
| 1.0.5 | 2026-07-16 | Kept packaged readiness pollers owned until first health and operational-data success | Codex |
| 1.0.6 | 2026-07-16 | Isolated expensive Windows process probes and hostname resolution from readiness | Codex |
