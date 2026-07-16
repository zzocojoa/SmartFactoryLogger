# Gap Analysis: NSIS Operational Ready Timing

> Date: 2026-07-16 | Design: `docs/02-design/features/nsis-operational-ready-timing.design.md`
> Act 2 build commit: `b848755b118852df4cf1a1cc1f6c13160618c7df`
> Act iteration: 7 | Replacement package ready; server validation pending

---

## Match Rate: 100% (candidate package; server validation pending)

The implementation matches the runtime readiness design. Act 3 made the frozen
backend responsive, but package reproduction showed that the `file:` renderer
still called `localhost`. On the target Windows resolver this attempts IPv6
`::1` first while Uvicorn listens on IPv4, delaying each request by about two
seconds. Act 5 used explicit IPv4 loopback for packaged renderer requests, but
server evidence then showed pre-listen requests could remain pending. Act 6
bounds both readiness requests and preserves base health retry cadence until
the first response. The Act 6 server run proved the backend eventually became
ready, but the renderer still did not recover. Act 7 keeps packaged readiness
polling ownership until health and operational data have each first succeeded,
even across hidden visibility and stale dashboard leader state.

## Summary

- The original visual `renderer.dashboard-ready` event remains unchanged.
- Every main/renderer startup log has one process-unique `session_id`.
- Backend response, live `Status=Running` data, and paint are independent gates.
- `Initializing`, `Offline`, and `Error` snapshots cannot satisfy live readiness,
  even when they carry a positive timestamp.
- Operational ready is emitted once after all gates and two final animation
  frames; timeout reports missing gates and never fabricates success.
- Packaged API calls use `127.0.0.1`; explicit environment overrides and
  browser-relative development calls remain unchanged.
- `/health` and `/api/data` polling requests terminate within two seconds, and
  health remains on its five-second base interval before first success.
- Packaged health and live-data pollers cannot be suppressed by hidden
  visibility or a stale leader lock before their first readiness success;
  normal pause and leader behavior resumes afterward.
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
| FR-12 explicit packaged IPv4 base | PASS | Mapper contract and final bundle scan |
| FR-13 bounded pre-listen recovery | PASS | Transport contract and fake-timer first-success retry test |
| FR-14 packaged lifecycle recovery | PASS SOURCE | Hidden/stale-lock hook tests; server package validation pending |

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
| AC-12 | PASS | packaged bundle contains IPv4 loopback and no localhost literal |
| AC-13 | PENDING SERVER | source/package contracts PASS; physical recovery run pending |
| AC-14 | PENDING SERVER | focused lifecycle regressions PASS; replacement package pending |

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

### Act 5: packaged renderer IPv6-first localhost delay

The Act 3 frozen backend itself reached `/health` and `/api/data` in about
`6.64 s`, but the renderer did not satisfy either gate. Direct reproduction on
the same package showed:

```text
127.0.0.1 /health: 200 in 16.2 ms
localhost /health: 200 in 2052.2 ms
[::1] /health: connection failure in 2036.7 ms
listener: 0.0.0.0:8000 (IPv4)
```

Windows resolves `localhost` to `::1` before `127.0.0.1`. The renderer therefore
paid the failed IPv6 connection delay on each poll. The packaged `file:` API
base now resolves directly to `http://127.0.0.1:8000`; no backend binding,
endpoint, timeout, or polling interval changed.

### Act 6: pre-listen requests suppressed later retries

The Act 5 physical-server run rendered the dashboard at `1,583.4 ms`, but both
backend and data gates remained absent at the 90-second caller deadline. Backend
logs showed Uvicorn eventually listening about 43 seconds after Electron launch
with no fatal Python or Windows Application crash.

Both readiness transports had no request timeout. The health timer and data
worker schedule their next iteration only after the current promise settles, so
a request opened while Uvicorn was unavailable could suppress every later
attempt. Act 6 adds a two-second timeout only to `/health` and `/api/data` and
keeps health on the five-second base interval until its first success. Existing
post-success health backoff, data worker cadence, and device polling are
unchanged.

### Act 7: renderer lifecycle suppressed bounded retries

The Act 6 server package identity matched every expected backend, QA, and
frontend asset hash. Electron launched at `08:33:45 KST`, and the frozen Python
session entered at `08:34:08 KST`. Uvicorn completed startup around
`08:34:48 KST`, approximately 63 seconds after Electron launch. The renderer
had already emitted its 30-second diagnostic event and did not record health or
live data during the remaining measurement budget:

```text
dashboard_ready_elapsed_ms=1565
backend Python entry delay=23 s
Uvicorn application startup complete=approximately 63 s after launch
missing_gates=backend_health,live_data
final classification=BACKEND_READY_BUT_RENDERER_DID_NOT_RECOVER
```

The backend and package were therefore not the remaining fault domain. Code
inspection found that both hook lifecycles stop polling when the Electron
document is hidden or another dashboard leader lock is observed. Those policies
are correct after startup but could suppress all bounded retries before the
first readiness result. Act 7 grants temporary ownership only to the packaged
renderer: health remains pending until its first non-null result, and live data
remains pending until `isOperationalFactoryData()` accepts a `Status=Running`
snapshot. `Initializing` does not end recovery. No request, endpoint, timer
interval, device protocol, or normal post-success ownership policy changes.

## Validation Results

| Check | Result |
|-------|--------|
| Focused startup telemetry | `18 passed` |
| Frontend full suite | `29 files, 223 tests passed` |
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
| Act 5 API-base contract | `4 passed` |
| Act 5 loopback reproduction | IPv4 `16.2 ms`; localhost `2052.2 ms`; IPv6 failed |
| Act 5 packaged MOCK operational-ready | PASS at `8,267.7 ms`; launcher `8,582.7 ms` |
| Act 6 focused recovery tests | `2 files, 3 tests passed` |
| Act 6 frontend full suite | `31 files, 226 tests passed` |
| Act 6 packaged MOCK operational-ready | PASS at `20,422.1 ms`; launcher `20,724.5 ms` |
| Act 7 focused startup/lifecycle tests | `4 files, 29 tests passed` |
| Act 7 frontend full suite | `31 files, 228 tests passed` |
| Act 7 frontend typecheck/lint/build | PASS |
| Act 7 project health | backend ruff/mypy PASS; `485 tests passed` |
| Act 7 PyInstaller provenance | clean HEAD `81356abb6ca629b93cecc3b171d65806e8ce3ab6` verified before/after build |
| Act 7 NSIS electron-builder | PASS |
| Act 7 packaged MOCK operational-ready | PASS at `8,568.5 ms`; launcher `8,886.4 ms` |

## Act 7 Candidate Package Evidence

| Artifact | Evidence |
|----------|----------|
| Source/build commit | `81356abb6ca629b93cecc3b171d65806e8ce3ab6` |
| Installer | `dist/smart-factory-logger-v2 Setup 1.0.14.exe` |
| Installer bytes | `163,230,457` |
| Installer SHA-256 | `E771FDA73E729A6DFA613FC3BB0CE4D1AA2033E515403238EA1AE72C4B71E32E` |
| Backend SHA-256 | `EC937974019156EC531EC4E9B840CC2E3D28B82B891CC45691BD64FFFA321885` |
| QA script SHA-256 | `C92A160C2B60F5DDA5601F8C384A07A7F3253FDD8F0F0266F849629C76285F34` |
| Frontend index SHA-256 | `9C7411C828E1602B011734ED6F40918A9905A017DA7CD3146EB8746983391A2A` |
| Frontend entry SHA-256 | `9D8B45B69334B161EA7B551B2750A60A1AD3866C44A8309851FBE180839B3CC1` |
| Frontend app SHA-256 | `FDCA06AF669AA9EE5D2BBDAF77C6974A410EEB8752B429A46A12779049E99D0F` |
| Frontend worker SHA-256 | `27E36A9D369886C88D922D615FCBA2ACD31245F7EB1C29C98729ABD3B1B84338` |
| Source/package hash checks | backend, QA, and four frontend assets MATCH |
| Build time | `2026-07-16T09:06:45+09:00` |

Packaged MOCK cold start reached dashboard paint at `513.3 ms`, backend health
at `7,544.0 ms`, first Running data at `8,488.3 ms`, and operational-ready at
`8,568.5 ms`; launcher-observed time was `8,886.4 ms`. It completed within the
30-second diagnostic budget with zero missing milestones and cleanup PASS.

## Act 6 Candidate Package Evidence (superseded)

| Artifact | Evidence |
|----------|----------|
| Source/build commit | `46c0f2cc13a205db27590ca72429f61c2cf344b0` |
| Installer | `dist/smart-factory-logger-v2 Setup 1.0.14.exe` |
| Installer bytes | `163,230,938` |
| Installer SHA-256 | `39165C1EDBD05F1ADA9E9CE36A036AE31E46A2CBDAD4BCD63AD22940341D7FB9` |
| Backend SHA-256 | `14657B890352662C6972A73C926A83BB5A416A0F5EB00D193289AFE3FD1B1A63` |
| QA script SHA-256 | `C92A160C2B60F5DDA5601F8C384A07A7F3253FDD8F0F0266F849629C76285F34` |
| Backend source/package hash | MATCH |
| QA script source/package hash | MATCH |
| Build time | `2026-07-16T08:24:22+09:00` |

The unpacked frontend includes the two-second timeout in both the application
and polling-worker bundles, contains the explicit IPv4 loopback base, and has no
`http://localhost:8000` literal. Packaged MOCK cold start passed within the
30-second diagnostic budget with zero missing milestones and cleanup PASS.

PyInstaller repeated its existing non-blocking `Hidden import "tzdata" not
found` warning. No timezone behavior was changed by this feature, and the full
health/package build completed successfully.

This package is superseded because the physical server proved that packaged
visibility/leader lifecycle state could still suppress all post-listen retries.

## Act 5 Candidate Package Evidence (superseded)

| Artifact | Evidence |
|----------|----------|
| Source/build commit | `c6be48c4398fa4f651e93b6a47ddfaf0f0308cb4` |
| Installer | `dist/smart-factory-logger-v2 Setup 1.0.14.exe` |
| Installer bytes | `163,232,993` |
| Installer SHA-256 | `ABA6ED160BED8A43AEBB0365471E2BF2B3B85798BFE9A64A5E2C2D967386A669` |
| Backend SHA-256 | `8037F2B6B89384C41B495F0DE3C0533545388D0B1A2EE96DD7CD5EA4591FA7CD` |
| QA script SHA-256 | `C92A160C2B60F5DDA5601F8C384A07A7F3253FDD8F0F0266F849629C76285F34` |
| Backend source/package hash | MATCH |
| QA script source/package hash | MATCH |
| Build time | `2026-07-16T01:18:18+09:00` |

The final frontend bundle contains the explicit IPv4 API base and contains no
`http://localhost:8000` literal. Packaged MOCK cold-start reached dashboard
paint at `673.4 ms`, live data at `8,215.6 ms`, backend health at `8,225.5 ms`,
and operational-ready at `8,267.7 ms`. It completed within the diagnostic budget
with `ready_strategy=raf`, no missing milestone, and successful process cleanup.

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

- Run only the Act 7 installer on the server and retain a true
  operational-ready measurement artifact.

## Deviations from Design

- `backend/version.py` and `CHANGELOG.md` were added to the implementation set so
  runtime health and release identity match the installer.
- The measurement script is bundled under `resources/qa` rather than remaining
  source-only, improving server reproducibility without changing runtime code.
- The live predicate was strengthened during Act to exact `Status=Running` after
  packaged evidence proved that timestamp alone was insufficient.

## Recommendation

Use only installer SHA `E771FDA7...` for final server validation. Do not use
superseded SHA `39165C1E...`. Rerun the bundled launcher on the server with the
app and backend fully stopped.
