# Electron Startup Progress - Design Document

> Version: 1.0.0 | Date: 2026-07-16 | Status: Approved for implementation
> Level: Dynamic | Plan: `docs/01-plan/features/electron-startup-progress.plan.md`

---

## 1. Overview

### 1.1 Purpose

Implement an Electron-owned startup state machine and one-window overlay. The
overlay is static HTML so it paints before the React bundle, while Electron main
remains the authoritative owner of readiness, timeout, retry, and locally logged
state transitions.

### 1.2 Design Goals

- Separate user-interface readiness from the existing strict production-data
  performance metric.
- Reuse current health/data/dashboard responses and add no HTTP/device request.
- Report backend progress through a machine-readable, allowlisted stdout contract.
- Fail visibly and recoverably instead of exposing an infinite spinner.
- Preserve context isolation and a fixed, minimal preload API.
- Make the state machine and parser deterministic under unit tests.

## 2. Architecture

### 2.1 System Architecture

```text
Electron main process
  startupCoordinator.js
    - monotonic progress/state
    - readiness gates
    - 30-second deadline
    - bounded backend line parser
  startupIpc.js
    - exact-document trust and renderer-generation checks
    - bounded startup event/action capabilities
  backendProcessLifecycle.js
    - serialized retry and close confirmation
    - graceful drain with forced tree-kill fallback
  main.js
    - backend ownership/restart
    - renderer-event allowlist
    - trusted-frame IPC handlers
    - state broadcast
      |
      v fixed IPC snapshot/events/actions
preload.js (context isolation boundary)
      |
      v
frontend/index.html startup overlay
      ^
      | existing renderer readiness events
React dashboard + existing polling

Embedded backend stdout
  SFL_STARTUP_PROGRESS {"stage":"..."}
      |
      +---- parsed by Electron main only
```

The dashboard is never placed in a hidden second BrowserWindow. It renders behind
the overlay, so existing animation-frame paint signals remain trustworthy and
there is no hidden-window throttling or cross-window focus race.

### 2.2 Startup Coordinator

`startupCoordinator.js` is a pure CommonJS module with no Electron dependency.
It receives a monotonic `now`, timer functions, and an `onChange` callback.

Flat state contract:

```text
schema_version: electron-startup-state-v1
session_id: string
sequence: integer
status: loading | ready | degraded | timeout | error
phase: allowlisted phase string
message: fixed Korean UI message
progress: integer 0..100
elapsed_ms: finite non-negative number
backend_health_ready: boolean
data_snapshot_ready: boolean
data_running: boolean
dashboard_paint_ready: boolean
can_retry / can_continue_offline / can_exit: boolean
reason: bounded allowlisted reason string or null
```

All state values originate from code-owned constants. Backend stdout provides
only an allowlisted stage identifier; it cannot supply user-visible text,
progress, IPC names, actions, paths, or raw error details.

#### Progress milestones

| Milestone | Progress | Message |
|-----------|----------|---------|
| Electron ready | 10 | 프로그램 환경을 준비하고 있습니다. |
| Backend spawn started | 15 | 백엔드 프로세스를 시작하고 있습니다. |
| Backend spawned | 22 | 백엔드 초기화를 기다리고 있습니다. |
| Lifespan begin | 28 | 백엔드 서비스를 초기화하고 있습니다. |
| CSV logger | 34 | 데이터 기록 서비스를 준비하고 있습니다. |
| Config sync/watch | 42 / 48 | 설비 설정을 불러오고 있습니다. |
| PLC service | 58 | 설비 통신 서비스를 준비하고 있습니다. |
| Metrics/memory | 64 / 70 | 상태 진단 서비스를 준비하고 있습니다. |
| SPOT poll/lifespan complete | 74 / 78 | 센서 서비스를 준비하고 있습니다. |
| Dashboard paint | 82 | 대시보드 화면을 구성하고 있습니다. |
| Backend health | 90 | 백엔드 연결을 확인했습니다. |
| First data snapshot | 96 | 첫 설비 데이터를 확인했습니다. |
| Ready/degraded | 100 | 준비가 완료되었습니다. |

Progress is `max(previous, milestone)` so out-of-order events never move the bar
backward. `sequence` increases only on an observable state change.

#### Readiness rules

```text
normal ready = backend health + timestamped Running snapshot + RAF dashboard paint
degraded ready = backend health + timestamped Offline/Error snapshot + RAF dashboard paint
strict operational ready = unchanged existing health + Running live data + paint + 2 RAF
```

An `Initializing` snapshot does not satisfy either UI or strict readiness. A
timestamp must be finite/positive, `Time` non-empty, and `Status` non-empty.

The coordinator may recover from `timeout` to `ready` or `degraded` when late
gates arrive. Once `ready`, `degraded`, or user-dismissed, a later backend exit
does not reopen the startup overlay; existing runtime status UI owns post-startup
failures.

### 2.3 Backend Progress Contract

Backend helper:

```text
_emit_embedded_startup_progress(stage)
```

- Emits only when `SFL_EMBEDDED_ELECTRON=1`.
- Accepts only a frozen stage set.
- Writes exactly one compact JSON object after `SFL_STARTUP_PROGRESS `.
- Uses `flush=True` to avoid pipe buffering.
- Emits no duration, file path, address, device value, exception, or log text.
- Unknown stage calls are ignored.

Stages:

```text
lifespan_begin
csv_logger_ready
config_sync_ready
config_watch_ready
plc_service_ready
comm_metrics_ready
memory_service_ready
spot_poll_ready
lifespan_complete
```

Main uses a per-process parser. It accepts arbitrary Buffer fragmentation, splits
on CR/LF, limits each line and retained remainder, validates a plain JSON object,
and ignores malformed/unknown events. Generic backend stdout logging remains,
but structured lines are not forwarded to the renderer.

### 2.4 IPC Boundary

Main handlers/channels are fixed:

| Direction | Channel | Contract |
|-----------|---------|----------|
| renderer -> main | `sfl:get-startup-state` | no arguments, returns flat state |
| main -> renderer | `sfl:startup-state-changed` | flat state broadcast |
| renderer -> main | `sfl:retry-startup` | no arguments, serialized owned-backend restart |
| renderer -> main | `sfl:continue-startup-offline` | no arguments, terminal degraded dismissal |
| renderer -> main | `sfl:exit-startup` | no arguments, app quit |

Every renderer-origin request is accepted only when `event.sender` is the active
main window's `webContents`, `senderFrame` is the owned main frame, and its URL
normalizes to the exact canonical local document URL. Stateful events must also
carry the `performance.timeOrigin` registered by the current preload generation,
so events left over from a reloaded renderer cannot satisfy fresh gates. The
preload exposes concrete methods, not an arbitrary `send`, `invoke`, or channel
parameter. Subscription returns an unsubscribe closure and strips the Electron
event object.

### 2.5 Backend Retry Ownership

`main.js` owns one `backendProcess` and one `backendRestartPromise`.

1. Ignore or return the active promise for duplicate clicks.
2. Mark the current child PID as an expected exit.
3. POST the per-launch authenticated local control endpoint and wait for the
   backend to drain writers and close.
4. If graceful shutdown fails or exceeds 10 seconds, force-terminate the owned
   process tree and still require its close event.
5. Reset coordinator and arm a fresh 30-second deadline.
6. Clear per-document event counters/generation and reload the renderer so readiness
   one-shots are measured again.
7. Start exactly one replacement process with a fresh stdout parser.

The control token is generated in Electron main for each launch, passed only in
the owned backend child environment, compared in constant time by embedded mode,
and never exposed through preload, startup state, or logs. Standalone backend
compatibility remains unchanged.

An unexpected spawn error/close before UI handoff enters `error`. Expected retry
or application shutdown exits never produce an error overlay.

### 2.6 Startup Overlay

`frontend/index.html` contains the overlay before `#root` and before the module
entry. It uses the existing `backend/assets/splash.png`, copied into
`frontend/dist/assets/splash.png` by a deterministic post-build Node script.

The inline controller:

- Runs in a hidden BrowserWindow that is shown only after `ready-to-show`, so a
  blank native window is never exposed before the static splash is rendered.
- Uses two animation frames to report `renderer.splash-first-paint`; main starts
  the backend only after both the window is shown and that event is accepted.
  The 750 ms bounded fallback is armed only after the rendered window is shown,
  so slow disk or antivirus startup cannot start the backend ahead of the
  user-visible splash.
- Subscribes first, then retrieves the current snapshot; sequence checks reject
  an older snapshot that races with a newer broadcast.
- Uses `textContent` and fixed button labels only.
- Updates `aria-live`, `role=status`, and `role=progressbar` attributes.
- Disables actions while an invoke is pending.
- On `ready` or `degraded`, waits one animation frame, applies a 200 ms fade, then
  sets `hidden` and unsubscribes.
- When no Electron bridge exists, removes the overlay immediately so browser/Vite
  development behavior is unchanged.
- For `timeout` or `error`, keeps the overlay visible with retry, offline, and exit.

## 3. Data Flow

### 3.1 Normal Startup

1. Electron creates the coordinator and startup session clock.
2. Window loads local HTML; overlay paints immediately and reports a double-RAF
   first-paint handshake.
3. Main shows the rendered splash, then starts the backend after that handshake
   (or the post-show bounded fallback) and
   parses structured lifecycle progress.
4. React renders behind the overlay and emits confirmed dashboard paint.
5. Existing `/health` response emits backend-health-ready.
6. Existing `/api/data` response emits first-data-snapshot; Running data also
   continues to emit the existing first-live-data event.
7. Coordinator reaches ready and broadcasts 100%.
8. Overlay fades out; strict operational-ready continues unchanged.

### 3.2 Device-Offline Startup

1. Backend health succeeds.
2. First valid data snapshot reports Offline or Error.
3. Dashboard paint completes.
4. Coordinator records degraded readiness and hides the overlay.
5. Dashboard remains visibly Offline and existing pollers continue recovery.

### 3.3 Failure and Timeout

- Spawn error or owned backend premature exit: status `error`, actions visible.
- Missing required gates at 30 seconds: status `timeout`, missing gate names are
  logged internally, actions visible.
- Late readiness after timeout: transition to ready/degraded and dismiss.
- Manual continue: status `degraded`, phase `continued_offline`, dismiss.
- Retry: reset and one serialized backend restart.
- Exit: application shutdown and owned process-tree cleanup.

## 4. API and Type Specification

### 4.1 Renderer Event Addition

```text
renderer.first-data-snapshot
payload: status, timestamp_present
acceptance: finite positive timestamp_ms, non-empty Time and Status,
            normalized status != initializing
```

This event is added to the existing main allowlist and bounded event limit. The
existing `renderer.first-live-data` validator and payload do not change.

### 4.2 Browser Types

`SmartFactoryElectronBridge` gains the four fixed startup methods and a typed
subscription. `SmartFactoryStartupState` is flat and contains no optional raw
objects. No backend HTTP API or persistence schema changes.

## 5. File Plan

| File | Change |
|------|--------|
| `startupCoordinator.js` | pure coordinator, stage mapping, parser, state schema |
| `startupCoordinator.test.cjs` | Node state/parser/deadline tests |
| `startupIpc.js` / `startupIpc.test.cjs` | exact sender/generation validation and action tests |
| `backendProcessLifecycle.js` / `.test.cjs` | graceful/forced stop and serialized retry tests |
| `main.js` | coordinator integration, trusted IPC, state broadcast, serialized restart |
| `preload.js` | fixed state/action bridge and unsubscribe subscription |
| `package.json` | package coordinator and run Node test in health |
| `backend/app.py` | embedded structured lifecycle emitter and authenticated graceful shutdown |
| `backend/tests/test_data_history_api.py` | Electron/backend startup contract tests |
| `frontend/index.html` | immediate overlay markup/style/controller |
| `frontend/scripts/copy_startup_splash.cjs` | deterministic existing-image copy |
| `frontend/package.json` | run splash copy after Vite build |
| `frontend/src/shared/types.ts` | startup event/state/bridge types |
| `frontend/src/shared/startup/startupTelemetry.ts` | snapshot validator/one-shot event |
| `frontend/src/shared/startup/startupTelemetry.test.ts` | strict vs snapshot gate tests |
| `frontend/src/shared/startup/startupHtml.test.ts` | ordering, accessibility, action contract |
| `MetricsDataController.tsx` | mark snapshot before strict Running gate |
| PDCA documents | plan/design/analysis/report traceability |

## 6. Implementation Order

1. Implement and unit-test the pure coordinator/parser.
2. Add main/preload integration and owned-backend retry.
3. Add backend structured lifecycle events and contract tests.
4. Add first-data-snapshot telemetry while preserving strict readiness.
5. Add inline overlay, asset copy, types, and HTML tests.
6. Run focused tests, full health/build checks, and gap analysis.
7. Fix all design gaps and review findings.
8. Commit, push, and create a ready PR with rollback and validation evidence.

## 7. Test Plan

### 7.1 Coordinator and Parser

- Out-of-order milestones remain monotonic.
- All normal gate orders yield one ready state.
- Offline/Error yield degraded; Initializing yields no snapshot gate.
- Timeout exposes approved actions and can later recover.
- Backend failure before/after terminal handoff behaves correctly.
- Reset clears gates/deadline and ignores the old deadline callback.
- Fragmented and coalesced CR/LF lines parse once.
- Malformed, array, oversized, and unknown-stage messages are ignored.

### 7.2 Renderer and HTML

- Bridge unavailable fallback remains harmless.
- Snapshot event is one-shot and strict Running event remains unchanged.
- Inline overlay precedes root/module and includes local-only image.
- Accessibility roles and fixed action handlers exist.
- Ready/degraded fade path unsubscribes.
- Browser fallback removes the overlay.

### 7.3 Backend and Integration

- Emitter is silent outside embedded mode.
- Embedded emitter outputs compact flushed JSON for every allowlisted stage.
- Unknown stage cannot enter output.
- Lifespan call sites cover every designed stage.
- Main package includes coordinator and preload.
- Existing bundled operational-ready script and event names remain unchanged.

### 7.4 Commands

```text
npm run test:electron-startup
npm --prefix frontend run test -- startupTelemetry startupHtml
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
backend/.venv/Scripts/python.exe -m ruff check backend
backend/.venv/Scripts/python.exe -m mypy
node scripts/run_backend_unittest.cjs
npm run health
git diff --check
```

## 8. Security and Operations

- Startup state contains no secrets, credentials, URLs, paths, sensor values, or
  arbitrary backend messages.
- Renderer input cannot select an IPC channel or backend stage.
- Exact document URL, owned main-frame identity, renderer generation, semantic
  gate payloads, and per-event limits are validated before state changes.
- State broadcasts are sent only to the owned main window.
- Parser memory is bounded under a missing-newline or malicious-output condition.
- No HTML is generated from backend content.
- Retry is serialized and owns only the child process started by this Electron
  process. Graceful drain is attempted before Windows forced tree termination.
- Rollback has no migration cost; revert restores immediate dashboard exposure.
- Post-merge operational verification must include normal cold start, device
  Offline, forced backend exit, retry, and clean shutdown on the server computer.

## 9. Requirement Traceability

| Plan requirement | Design evidence | Test evidence |
|------------------|-----------------|---------------|
| FR-01 / FR-14 | 2.6 | startupHtml tests and build |
| FR-02 / FR-05 | 2.2 | coordinator state tests |
| FR-03 / FR-04 | 2.3 | parser and backend contract tests |
| FR-06 / FR-07 / FR-08 | 2.2, 4.1 | telemetry and coordinator tests |
| FR-09 / FR-10 | 3.3 | error, timeout, and recovery tests |
| FR-11 / FR-12 | 2.5, 3.3 | restart and manual continuation tests |
| FR-13 | 2.4 | preload and main contract tests |
| FR-15 | 2.2 | bounded transition log contract |
