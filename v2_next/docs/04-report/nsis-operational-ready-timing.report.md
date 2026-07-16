# NSIS Operational Ready Timing Report

> Version: 1.0.6 | Date: 2026-07-16 | Status: Act 8 Source Verified / Package Pending
> Feature: `nsis-operational-ready-timing`

## 1. Summary

- Added a separate full operator-wait metric without redefining the existing
  visual dashboard-ready baseline.
- Operational-ready now requires backend health, a positive timestamped
  `Status=Running` factory snapshot, a confirmed dashboard paint, and two final
  animation frames.
- Added process-session correlation and a fail-closed PowerShell cold-start
  measurement bundled in the installed application's `resources/qa` directory.
- Server evidence exposed a QA launcher defect: the 30-second renderer diagnostic
  marker prematurely terminated a caller-requested 90-second measurement.
- Patched the launcher to retain that marker while waiting for true readiness
  until the external deadline.
- Server logs proved the Act 2 backend stayed in FastAPI application startup
  while initial memory diagnostics overlapped slow physical-device reads.
- Moved the first memory snapshot into the existing sampler thread and added
  per-stage lifespan timing without changing memory content or cadence.
- Reproduced a Windows IPv6-first `localhost` delay: IPv4 health responded in
  `16.2 ms`, while `localhost` took `2052.2 ms` after `::1` failed.
- Changed only packaged/local fallback API resolution to explicit
  `127.0.0.1`; environment overrides and browser development remain unchanged.
- Installer SHA `0437A378...` and Act 5 SHA `ABA6ED160B...` are superseded by
  the later server-evidence iterations.
- Packaged MOCK live-data timing passed at 8.2266 seconds launcher-observed.
- Development-PC hardware mode correctly timed out with only `live_data`
  missing; it no longer counts a timestamped error snapshot as ready.
- The Act 5 server package rendered the dashboard at `1,583.4 ms`, while the
  frozen backend did not finish Uvicorn startup until about 43 seconds after
  Electron launch. Neither renderer health nor live-data polling recovered by
  the 90-second caller deadline.
- The two readiness requests previously had no request timeout. Since each
  recursive retry is scheduled only after its current promise settles, a
  pre-listen pending request could suppress every later retry.
- Act 6 bounds `/health` and `/api/data` requests to two seconds and keeps
  health on the five-second base interval until its first success. Existing
  post-success outage backoff and device polling are unchanged.
- The Act 6 server package matched every expected hash and Uvicorn became ready
  about 63 seconds after Electron launch, but the renderer did not recover its
  health or live-data gates during the remaining caller budget.
- Act 7 keeps the existing packaged health and live-data pollers temporarily
  owned until their respective first successful readiness results, even when
  the document is hidden or a stale dashboard leader lock exists. Normal
  visibility and leader behavior resumes after success.
- Built the clean Act 7 NSIS from commit `81356ab...`; installer SHA is
  `E771FDA7...`, and packaged MOCK operational-ready passed at `8,568.5 ms`.

## 2. Engineering Assessment

- Risk level: medium. The change affects startup lifecycle concurrency,
  observability, and release identity but does not change device polling, CSV
  data, or dashboard layout.
- Trade-off: operational-ready is intentionally stricter than visual-ready. A
  disconnected PLC returns timeout evidence instead of a misleading fast PASS.
- Compatibility: existing `renderer.dashboard-ready`, `/health`, `/api/data`,
  frontend polling, backend schemas, and NSIS install behavior remain compatible.
- Network compatibility: packaged requests still target the same local backend
  port and endpoints; only hostname resolution is made deterministic.
- Security: startup IPC remains allowlisted and flat-scalar sanitized. Session
  IDs are bounded local correlation identifiers and contain no secret or device
  data. Added-line sensitive scan found zero hits.
- Observability: at most five additional bounded startup events are written per
  process. Timeout names the missing gate and never substitutes a success event.
- Backend observability: each synchronous lifespan stage records elapsed time;
  no sensor value, credential, or device URL is added.
- Migration: none.
- Operational failure mode: unavailable hardware yields
  `OPERATIONAL_TIMEOUT` only at the caller deadline when the internal diagnostic
  marker was observed; the script then cleans up the launched process tree unless
  `-KeepRunning` is explicitly supplied.
- Renderer recovery failure mode: a readiness request that exceeds two seconds
  is aborted and counted as the existing poll failure, allowing the existing
  timer/worker loop to continue rather than remaining pending.
- Lifecycle recovery failure mode: before first readiness success, packaged
  polling ignores only hidden visibility and stale leader ownership. Browser
  multi-tab behavior and all post-success pause/leader semantics are unchanged.
- Rollback Act 7: revert commit `81356ab`, rebuild backend/NSIS from a clean
  commit, and continue using the unchanged visual-ready metric while preserving
  the prior bounded-request behavior if desired.

## 3. Files Changed

| File | Purpose |
|------|---------|
| `main.js` | Startup session ID and new renderer event allowlist |
| `frontend/src/shared/startup/startupTelemetry.ts` | Readiness coordinator, data predicate, timeout |
| `frontend/src/shared/startup/startupTelemetry.test.ts` | Invalid data, gate order, frame, timeout tests |
| `frontend/src/shared/types.ts` | New startup event names |
| `frontend/src/index.tsx` | Arm operational startup timeout |
| `frontend/src/App.tsx` | Reuse first successful health response |
| `frontend/src/domains/FacilityData/components/MetricsDataController.tsx` | Reuse first Running data snapshot |
| `scripts/measure_nsis_operational_ready.ps1` | Cold-start measurement and self-test |
| `backend/tests/test_data_history_api.py` | Electron/readiness/package contracts |
| `backend/Observability/memory_service.py` | Immediate initial snapshot on sampler thread |
| `backend/app.py` | Per-stage lifespan startup elapsed logs |
| `backend/tests/test_memory_service.py` | Blocking-collector non-blocking-start regression |
| `frontend/src/shared/api/client.mapper.ts` | Explicit packaged IPv4 loopback API base |
| `frontend/src/shared/api/client.mapper.test.ts` | Packaged, override, and development API-base contracts |
| `frontend/src/shared/api/pollingRequest.ts` | Two-second local readiness request bound |
| `frontend/src/shared/api/transport/systemService.transport.ts` | Bounded `/health` request |
| `frontend/src/shared/api/transport/metricService.transport.ts` | Bounded `/api/data` request |
| `frontend/src/domains/Observability/hooks/useSystemViewModelEffects.ts` | Five-second health retry until first success |
| `frontend/src/domains/Observability/hooks/useSystemViewModelEffects.test.ts` | Hidden/stale-lock packaged health recovery regression |
| `frontend/src/domains/FacilityData/hooks/useMetricsViewModelEffects.ts` | Packaged data polling ownership until first Running snapshot |
| `frontend/src/domains/FacilityData/hooks/useMetricsViewModelEffects.test.ts` | Initializing and post-success hidden-pause regressions |
| focused frontend tests | Transport wiring and delayed-start recovery contracts |
| `backend/version.py` | Runtime version `1.0.14` |
| root/frontend package manifests | NSIS/frontend version and bundled QA script |
| `CHANGELOG.md` | Release notes |
| PDCA plan/design/analysis/report | Traceability and evidence |

## 4. Validation

### Automated checks

- Focused readiness tests: `18 passed`
- Frontend: `29 test files`, `223 tests` passed
- Frontend typecheck and lint: PASS
- Backend ruff and mypy: PASS
- Backend unittest: `485 tests` passed
- Electron/readiness contracts: `6 passed`
- PowerShell parser/self-test: PASS
- `git diff --check`: PASS
- Added-line sensitive scan: `sensitive_hits=0`
- Source MOCK lifecycle: `/health` PASS at `1,814.3 ms`; memory stage returned in
  `153.0 ms`, all other logged stages below `1 ms`
- Packaged loopback reproduction: `127.0.0.1` `16.2 ms`, `localhost`
  `2052.2 ms`, `[::1]` connection failure
- API-base contract: `4 passed`
- Final packaged MOCK operational-ready: PASS at `8,267.7 ms`; launcher
  observed `8,582.7 ms`, `ready_strategy=raf`, cleanup PASS
- Act 6 focused recovery tests: `2 files`, `3 tests` passed
- Act 6 frontend: `31 test files`, `226 tests` passed
- Act 6 typecheck and lint: PASS
- Act 7 focused startup/lifecycle tests: `4 files`, `29 tests` passed
- Act 7 frontend full suite: `31 files`, `228 tests` passed
- Act 7 typecheck, lint, and production build: PASS
- Act 7 project health: backend ruff/mypy PASS, `485 tests` passed
- Act 7 packaged MOCK operational-ready: PASS at `8,568.5 ms`; launcher
  `8,886.4 ms`, zero missing milestones, cleanup PASS

### Package checks

- Frontend production build: PASS
- PyInstaller one-file backend: PASS
- Provenance before/after build:
  `81356abb6ca629b93cecc3b171d65806e8ce3ab6`
- electron-builder NSIS: PASS
- Backend source/package SHA match: PASS
- QA script source/package SHA match: PASS
- Runtime version: `1.0.14`, runtime kind: `frozen`

### Act 7 candidate artifact

| Artifact | Value |
|----------|-------|
| Installer | `dist/smart-factory-logger-v2 Setup 1.0.14.exe` |
| Built at | `2026-07-16 09:06:45 KST` |
| Size | `163,230,457 bytes` |
| SHA-256 | `E771FDA73E729A6DFA613FC3BB0CE4D1AA2033E515403238EA1AE72C4B71E32E` |
| Backend SHA-256 | `EC937974019156EC531EC4E9B840CC2E3D28B82B891CC45691BD64FFFA321885` |
| QA script SHA-256 | `C92A160C2B60F5DDA5601F8C384A07A7F3253FDD8F0F0266F849629C76285F34` |
| Frontend index SHA-256 | `9C7411C828E1602B011734ED6F40918A9905A017DA7CD3146EB8746983391A2A` |
| Frontend entry SHA-256 | `9D8B45B69334B161EA7B551B2750A60A1AD3866C44A8309851FBE180839B3CC1` |
| Frontend app SHA-256 | `FDCA06AF669AA9EE5D2BBDAF77C6974A410EEB8752B429A46A12779049E99D0F` |
| Frontend worker SHA-256 | `27E36A9D369886C88D922D615FCBA2ACD31245F7EB1C29C98729ABD3B1B84338` |
| Build commit | `81356abb6ca629b93cecc3b171d65806e8ce3ab6` |

Backend, QA, and the four recorded frontend assets match their packaged copies.
Packaged MOCK cold start: dashboard `513.3 ms`, backend health `7,544.0 ms`,
first Running data `8,488.3 ms`, operational-ready `8,568.5 ms`, launcher
observed `8,886.4 ms`, `ready_strategy=raf`, diagnostic budget PASS, zero
missing milestones, and cleanup PASS.

### Act 6 candidate artifact (superseded)

| Artifact | Value |
|----------|-------|
| Installer | `dist/smart-factory-logger-v2 Setup 1.0.14.exe` |
| Built at | `2026-07-16 08:24:22 KST` |
| Size | `163,230,938 bytes` |
| SHA-256 | `39165C1EDBD05F1ADA9E9CE36A036AE31E46A2CBDAD4BCD63AD22940341D7FB9` |
| Backend SHA-256 | `14657B890352662C6972A73C926A83BB5A416A0F5EB00D193289AFE3FD1B1A63` |
| QA script SHA-256 | `C92A160C2B60F5DDA5601F8C384A07A7F3253FDD8F0F0266F849629C76285F34` |
| Build commit | `46c0f2cc13a205db27590ca72429f61c2cf344b0` |

Backend and QA source/package hashes match. The unpacked application and worker
bundles contain the two-second bound; the frontend contains the IPv4 loopback
base and no `http://localhost:8000` literal.

Packaged MOCK cold start: dashboard `5,651.7 ms`, backend health `20,243.3 ms`,
live data `20,305.9 ms`, operational-ready `20,422.1 ms`, launcher observed
`20,724.5 ms`, `ready_strategy=raf`, diagnostic budget PASS, zero missing
milestones, cleanup PASS.

The physical server proved this package can still stop renderer polling before
Uvicorn becomes ready; it is retained as root-cause evidence and is not a final
acceptance candidate.

### Act 5 candidate artifact (superseded)

| Artifact | Value |
|----------|-------|
| Installer | `dist/smart-factory-logger-v2 Setup 1.0.14.exe` |
| Built at | `2026-07-16 01:18:18 KST` |
| Size | `163,232,993 bytes` |
| SHA-256 | `ABA6ED160BED8A43AEBB0365471E2BF2B3B85798BFE9A64A5E2C2D967386A669` |
| Backend SHA-256 | `8037F2B6B89384C41B495F0DE3C0533545388D0B1A2EE96DD7CD5EA4591FA7CD` |
| QA script SHA-256 | `C92A160C2B60F5DDA5601F8C384A07A7F3253FDD8F0F0266F849629C76285F34` |

Backend source/package and QA source/package hashes match. The final frontend
bundle contains `http://127.0.0.1:8000` and contains no
`http://localhost:8000` literal.

### Act 2 artifact, superseded for Act 3

| Artifact | Value |
|----------|-------|
| Installer | `dist/smart-factory-logger-v2 Setup 1.0.14.exe` |
| Built at | `2026-07-16 00:26:08 KST` |
| Size | `163,231,182 bytes` |
| SHA-256 | `90AEF3AFB614BC67E8ABE19ADE529386FF25A13C4F5D58E3428A6E7CE39C0441` |
| Backend SHA-256 | `5FB92C00558341DA3E7CAD6C87BEB14E36AADC6A169CAACD8882CA63A9003A43` |
| QA script SHA-256 | `C92A160C2B60F5DDA5601F8C384A07A7F3253FDD8F0F0266F849629C76285F34` |

Source/package backend hashes and source/package QA script hashes match.

This package contains the synchronous initial memory snapshot and must not be
used for final operational-ready acceptance.

### Superseded artifact

| Artifact | Value |
|----------|-------|
| Installer | `dist/smart-factory-logger-v2 Setup 1.0.14.exe` |
| Built at | `2026-07-16 00:05:13 KST` |
| Size | `163,230,747 bytes` |
| SHA-256 | `591C268D49101CAC5701B1142D2B35A8364E555962A46B5557B9C8654E4314E1` |
| Backend SHA-256 | `69385CF6AF37916478C8704B566DE050A940CBFADC51A72CC9D200E711CBC8D2` |

Installer SHA `591C268D...` contains the premature-termination QA script and is
superseded for final readiness validation. SHA `FF5DED...` is also superseded.

### Packaged runtime timing

Positive package/state-machine test (`V2_MODE=MOCK`):

| Gate | Electron elapsed |
|------|------------------|
| Dashboard visual ready | `636.9 ms` |
| First Running live data | `7,080.7 ms` |
| Backend health response | `7,983.8 ms` |
| Operational ready | `8,009.6 ms` |
| Launcher-observed operational ready | `8,226.6 ms` |

Result: PASS, `ready_strategy=raf`, zero missing milestones,
`driver_connected=true`, and process cleanup PASS. Data arrived before health,
which also proves the coordinator is order independent.

Development-PC hardware-path test:

| Field | Result |
|-------|--------|
| Dashboard visual ready | `604.1 ms` |
| Backend health response | `7,943.0 ms` |
| First Running live data | absent |
| Final status | `OPERATIONAL_TIMEOUT` |
| Missing gate | `live_data` |
| Cleanup | PASS, zero remaining processes |

This is the expected result because the physical devices are on the server
computer. It confirms the metric does not report an offline/error snapshot as
usable live data.

### Known non-blocking warning

PyInstaller reports its existing `Hidden import "tzdata" not found` warning.
No timezone code changed, all automated/package checks pass, and previous frozen
runtime behavior is preserved. Physical server timing remains the final
environment-specific validation.

### Server Act evidence

The server visual shell was ready at `1,658.7 ms`, but the renderer recorded
`missing_gates=backend_health,live_data` at `31,195.2 ms`. Although the launcher
was invoked with `TimeoutSec=90`, it terminated and cleaned up the process at
about 34 seconds. The resulting backend/GPU/network exit messages followed that
cleanup and are not independent crash evidence.

### Act 2 launcher validation

- Packaged self-test: PASS
- Forced unavailable-backend path: diagnostic at `31.2727 s`; launcher returned
  only after the 35-second caller deadline (`36.0 s` wall clock).
- Development hardware path with `TimeoutSec=90`: backend health at `7.9722 s`,
  diagnostic at `30.3974 s`, then `OPERATIONAL_TIMEOUT` at `91.1 s` with only
  `live_data` missing and cleanup PASS.
- Local packaged positive smoke: true operational-ready event at `8.7921 s` and
  process cleanup PASS.

### Act 3 backend startup validation

- Server root cause: Uvicorn stayed at `Waiting for application startup` while
  two PLC reads took `28.80 s` and `27.65 s` and the extruder timed out.
- Windows Application log contained no matching crash event.
- Blocking-collector contract: initial collector starts immediately and
  `MemoryService.start()` returns before the collector is released.
- Full health: frontend `28 files / 219 tests`; backend ruff/mypy PASS and
  `485 tests` PASS.
- Source MOCK runtime: `/health` at `1,814.3 ms`, `running=true`,
  `driver_connected=true`.

### Act 5 server failure and Act 6 recovery patch

- Act 5 server measurement: `OPERATIONAL_TIMEOUT`, dashboard paint
  `1,583.4 ms`, backend/data gates absent, diagnostic timeout observed, and
  cleanup PASS. A manually printed green PASS line after PowerShell throws is
  not acceptance evidence.
- Backend logs show the frozen process reached Uvicorn at about 43 seconds; no
  fatal Python or Windows Application crash was present.
- Code audit found no timeout on either readiness transport. Both recursive
  loops wait for the current promise before scheduling their next request.
- Act 6 adds only renderer-to-local-backend request bounds and pre-success
  health retry behavior. PLC, SPOT, diagnostics, CSV, and image intervals are
  unchanged.
- Focused tests, full frontend tests, typecheck, lint, and `git diff --check`
  pass. A replacement clean package and physical-server measurement remain
  required.

### Act 6 server failure and Act 7 lifecycle patch

- Installed backend, QA, and all frontend asset hashes matched the Act 6
  package; stale installation was excluded.
- Electron launched at `08:33:45 KST`, the Python backend session entered 23
  seconds later, and Uvicorn completed startup at approximately 63 seconds.
- Dashboard visual paint completed at `1,565 ms`, but neither health nor live
  data recovered after the 30-second renderer diagnostic marker. Final
  classification: `BACKEND_READY_BUT_RENDERER_DID_NOT_RECOVER`.
- Act 7 changes only the pre-success ownership conditions of the existing
  renderer pollers. It adds no request, polling interval, endpoint, PLC/SPOT
  operation, CSV field, or backend lifecycle work.
- Focused hidden/stale-lock regressions, the `31 files / 228 tests` frontend
  suite, typecheck, lint, production build, backend ruff/mypy, and all 485
  backend tests pass. A clean replacement package and physical-server
  measurement are still required.

### Act 7 delayed recovery and Act 8 backend patch

- Act 7 server telemetry proved renderer recovery remained active: health was
  recorded at `143,597 ms`, first Running data at `149,143.5 ms`, and true
  operational-ready at `149,161.7 ms`.
- Repeated lifespan logs showed `memory_service.start()` consuming
  `16.6-29.9 s`. Its five-second sampler repeated Windows full-memory,
  open-file, and handle scans, so one expensive sample could overrun the next.
- A separate uninstrumented delay of up to approximately 32 seconds occurred
  between `spot_poll` completion and the old URL log, matching synchronous local
  hostname resolution.
- Act 8 keeps periodic memory monitoring but uses lightweight process fields.
  Expensive USS/open-file/handle details remain available through explicit
  memory snapshots.
- Local-address discovery is now diagnostic-only on a daemon thread. The new
  `Lifespan startup complete` marker identifies readiness independently of DNS.
- Focused tests: `39 passed`; backend ruff and mypy: PASS; full backend suite:
  `488 tests passed`; `git diff --check`: PASS.

## 5. Next Action

Commit the Act 8 source, generate a clean provenance-verified PyInstaller/NSIS
package, and rerun the bundled 90-second physical-device operational-ready
measurement with all existing processes stopped.
