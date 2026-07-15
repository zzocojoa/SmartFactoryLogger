# Gap Analysis: NSIS Operational Ready Timing

> Date: 2026-07-16 | Design: `docs/02-design/features/nsis-operational-ready-timing.design.md`
> Act 2 build commit: `b848755b118852df4cf1a1cc1f6c13160618c7df`
> Act iteration: 3 | Source complete; replacement packaging pending

---

## Match Rate: 100% (source; replacement package pending)

The implementation matches the runtime readiness design. The second server run
honored the 90-second launcher budget and exposed a different blocker: Uvicorn
remained in application startup while the synchronous initial memory snapshot
overlapped long-running physical-device workers. Act 3 moves that first snapshot
onto the existing sampler thread and records per-stage lifespan timing.

## Summary

- The original visual `renderer.dashboard-ready` event remains unchanged.
- Every main/renderer startup log has one process-unique `session_id`.
- Backend response, live `Status=Running` data, and paint are independent gates.
- `Initializing`, `Offline`, and `Error` snapshots cannot satisfy live readiness,
  even when they carry a positive timestamp.
- Operational ready is emitted once after all gates and two final animation
  frames; timeout reports missing gates and never fabricates success.
- The PowerShell measurement rejects pre-existing processes and multiple startup
  sessions, and reports both Electron monotonic and launcher wall-clock time.
- Root, frontend, backend, and NSIS artifact identity is `1.0.14`.
- Initial memory diagnostics still begins immediately, but cannot block FastAPI
  startup or `/health` availability.

## Requirement Results

| Requirement | Result | Evidence |
|-------------|--------|----------|
| FR-01 visual compatibility | PASS | Existing startup tests and full frontend suite pass |
| FR-02 session correlation | PASS | `startupSessionId` is attached to every main log entry |
| FR-03 backend readiness | PASS | `markBackendHealthReady(health)` records first response once |
| FR-04 real live-data readiness | PASS | Exact normalized `Status=Running`, non-empty time, positive finite timestamp |
| FR-05 gate/paint state machine | PASS | Two gate-order tests and final two-frame assertion |
| FR-06 fail-closed timeout | PASS | Missing-gate test plus packaged error-snapshot timeout |
| FR-07 structured measurement | PASS | Caller timeout remains authoritative; delayed recovery classification added |
| FR-08 contamination rejection | PASS | Process and multi-session classification contract |
| FR-09 clean package | PASS | Clean PyInstaller provenance and replacement NSIS verified |
| FR-10 version identity | PASS | Root/frontend/backend all `1.0.14`; artifact filename matches |
| FR-11 non-blocking initial memory snapshot | PASS | Blocking-collector regression plus source runtime stage timing |

## Acceptance Criteria

| AC | Result | Evidence |
|----|--------|----------|
| AC-01 | PASS | `renderer.dashboard-ready` tests remain green |
| AC-02 | PASS | backend gate is one-shot under duplicated health input |
| AC-03 | PASS | invalid timestamp and Initializing/Offline/Error matrix rejected |
| AC-04 | PASS | timestamped Running snapshot records once |
| AC-05 | PASS | backend-data-paint and paint-data-backend order tests pass |
| AC-06 | PASS | 30-second timeout names missing gates and emits no ready event |
| AC-07 | PASS | parser/session/milestone/delayed-recovery/failure self-test PASS |
| AC-08 | PASS | full health, parser, diff, and sensitive scan pass |
| AC-09 | PASS | Act 2 clean PyInstaller/NSIS hashes and bundled-resource equality verified |
| AC-10 | PASS | `Setup 1.0.14.exe` plus runtime health `app_version=1.0.14` |
| AC-11 | PASS | sampler collector starts immediately and `start()` returns before release |

## Act Iteration

The first packaged run exposed a correctness gap:

```text
driver_connected=false
data_status=Error
data_timestamp_ms=positive
operational_ready=incorrect PASS at 8.3206 s
```

The live-data predicate was tightened from “non-initial timestamped response” to
exact normalized `Status=Running`. Unit cases for `Offline` and `Error` were
added, full health was rerun, and the package was rebuilt from a new clean
commit. The superseded installer SHA `FF5DED...` must not be deployed.

Final negative-path packaged evidence on the development PC:

```text
status=OPERATIONAL_TIMEOUT
dashboard_ready_elapsed_ms=604.1
backend_health_ready_elapsed_ms=7943.0
first_live_data_elapsed_ms=null
missing_gates=live_data
cleanup_ok=true
remaining_processes=0
```

This proves that a timestamped error snapshot no longer produces a false PASS.

Final positive-path packaged evidence with backend `V2_MODE=MOCK`:

```text
status=PASS
dashboard_ready_elapsed_ms=636.9
first_live_data_elapsed_ms=7080.7
backend_health_ready_elapsed_ms=7983.8
operational_ready_elapsed_ms=8009.6
launcher_observed_operational_ready_ms=8226.6
ready_strategy=raf
health_mode=MOCK
driver_connected=true
data_status=Running
```

The data gate arrived before the health gate, confirming order independence in
an actual packaged runtime. MOCK timing validates the package and state machine;
it is not a substitute for the server-PC physical-device timing.

### Act 2: server timeout-budget mismatch

The first physical-server run of installer SHA `591C268D...` produced:

```text
dashboard_ready_elapsed_ms=1658.7
renderer.dashboard-operational-timeout=31195.2
missing_gates=backend_health,live_data
launcher TimeoutSec=90
script exit at approximately 34 seconds
```

The later `backend.closed code=1`, GPU-process exit, and network-service restart
were emitted after the script force-cleaned the launched process tree. They do
not prove a spontaneous backend crash. Root cause is the launcher's immediate
break on a diagnostic-only renderer event. The patch removes that break, waits
for true readiness until the external deadline, preserves the 30-second event,
and reports `diagnostic_budget_status`.

### Act 3: backend lifespan blocked by diagnostics

The replacement package correctly waited for the full 90-second budget, but
the physical server still returned no `/health` response. Backend logs proved:

```text
Python backend session start: 00:35:59
Uvicorn: Waiting for application startup
LS PLC reads observed: 28.80 s and 27.65 s
Extruder send timeout observed
Application startup complete: approximately 00:37:06
```

`PLCService` already performs reads on worker threads. The remaining synchronous
startup call was `MemoryService.start() -> capture_snapshot()`. Act 3 preserves
the immediate first sample but runs it inside `MemorySampler`, and adds bounded
stage elapsed logs. A source MOCK runtime reached `/health` in `1,814.3 ms`; its
startup stages were CSV `0.2 ms`, config sync `0.2 ms`, config watch `0.2 ms`,
PLC `0.6 ms`, comm metrics `0.5 ms`, memory start `153.0 ms`, and SPOT `0.0 ms`.

## Validation Results

| Check | Result |
|-------|--------|
| Focused startup telemetry | `18 passed` |
| Frontend full suite | `28 files, 219 tests passed` |
| Frontend typecheck/lint | PASS |
| Backend ruff/mypy | PASS |
| Backend unittest | `484 tests passed` |
| Act 3 focused memory service | `29 tests passed` |
| Act 3 full backend unittest | `485 tests passed` |
| Electron/source contracts | `6 passed` |
| PowerShell parser/self-test | PASS |
| 35-second forced negative path | `36.0 s`, diagnostic at `31.2727 s`, caller deadline honored |
| 90-second hardware-negative path | `91.1 s`, health `7.9722 s`, only `live_data` missing |
| Added-line sensitive scan | `0 hits` |
| `git diff --check` | PASS |
| Frontend production build | PASS |
| PyInstaller provenance | clean HEAD verified before/after packaging |
| NSIS electron-builder | PASS |
| Act 3 source MOCK `/health` | PASS at `1,814.3 ms` |

PyInstaller repeated its existing non-blocking `Hidden import "tzdata" not
found` warning. No timezone behavior was changed by this feature, and the full
health/package build completed successfully.

## Act 2 Candidate Package Evidence

| Artifact | Evidence |
|----------|----------|
| Source/build commit | `b848755b118852df4cf1a1cc1f6c13160618c7df` |
| Installer | `dist/smart-factory-logger-v2 Setup 1.0.14.exe` |
| Installer bytes | `163,231,182` |
| Installer SHA-256 | `90AEF3AFB614BC67E8ABE19ADE529386FF25A13C4F5D58E3428A6E7CE39C0441` |
| Backend SHA-256 | `5FB92C00558341DA3E7CAD6C87BEB14E36AADC6A169CAACD8882CA63A9003A43` |
| QA script SHA-256 | `C92A160C2B60F5DDA5601F8C384A07A7F3253FDD8F0F0266F849629C76285F34` |
| Backend source/package hash | MATCH |
| QA script source/package hash | MATCH |
| Build time | `2026-07-16T00:26:08+09:00` |

This package is superseded for Act 3 because it contains the synchronous initial
memory snapshot. It remains useful only as the server root-cause evidence build.

The replacement package also produced a local packaged PASS with dashboard,
backend health, live data, and true operational-ready events. A separate
90-second development hardware-path run reached backend health at `7.9722 s`,
retained the renderer diagnostic at `30.3974 s`, and failed only at the external
deadline because no physical-device `Status=Running` data was available.

## Superseded Package Evidence

| Artifact | Evidence |
|----------|----------|
| Source/build commit | `125c87d7e44fd7073497d579785ccaa27ac919af` |
| Installer | `dist/smart-factory-logger-v2 Setup 1.0.14.exe` |
| Installer bytes | `163,230,747` |
| Installer SHA-256 | `591C268D49101CAC5701B1142D2B35A8364E555962A46B5557B9C8654E4314E1` |
| Backend SHA-256 | `69385CF6AF37916478C8704B566DE050A940CBFADC51A72CC9D200E711CBC8D2` |
| Backend source/package hash | MATCH |
| QA script source/package hash | MATCH |
| Build time | `2026-07-16T00:05:13+09:00` |

This installer remains runtime-valid but its bundled QA script ends a 90-second
measurement at the 30-second diagnostic marker. It is superseded for this
feature's final operational-ready validation and must not be used for that test.

## Missing Items

- Commit Act 3 source, generate a clean replacement PyInstaller/NSIS package,
  and record its hashes.
- Run only the Act 3 installer on the server and retain a true
  operational-ready measurement artifact.

## Deviations from Design

- `backend/version.py` and `CHANGELOG.md` were added to the implementation set so
  runtime health and release identity match the installer.
- The measurement script is bundled under `resources/qa` rather than remaining
  source-only, improving server reproducibility without changing runtime code.
- The live predicate was strengthened during Act to exact `Status=Running` after
  packaged evidence proved that timestamp alone was insufficient.

## Recommendation

Do not reuse installer SHA `90AEF3AF...`. Build from the verified Act 3 commit,
verify the new installer/backend/QA hashes, then rerun the bundled launcher on
the server with the app and backend fully stopped.
