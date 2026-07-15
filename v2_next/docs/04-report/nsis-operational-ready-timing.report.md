# NSIS Operational Ready Timing Report

> Version: 1.0.2 | Date: 2026-07-16 | Status: Act 3 Source Complete / Rebuild Pending
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
- Installer SHA `90AEF3AF...` is superseded; the Act 3 replacement package is
  pending a clean source commit.
- Packaged MOCK live-data timing passed at 8.2266 seconds launcher-observed.
- Development-PC hardware mode correctly timed out with only `live_data`
  missing; it no longer counts a timestamped error snapshot as ready.

## 2. Engineering Assessment

- Risk level: medium. The change affects startup lifecycle concurrency,
  observability, and release identity but does not change device polling, CSV
  data, or dashboard layout.
- Trade-off: operational-ready is intentionally stricter than visual-ready. A
  disconnected PLC returns timeout evidence instead of a misleading fast PASS.
- Compatibility: existing `renderer.dashboard-ready`, `/health`, `/api/data`,
  frontend polling, backend schemas, and NSIS install behavior remain compatible.
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
- Rollback: revert `b848755`, `125c87d7`, and `a77a3be`, restore version
  `1.0.13`, rebuild backend/NSIS from a clean commit, and continue using the
  unchanged visual-ready metric.

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
| `backend/version.py` | Runtime version `1.0.14` |
| root/frontend package manifests | NSIS/frontend version and bundled QA script |
| `CHANGELOG.md` | Release notes |
| PDCA plan/design/analysis/report | Traceability and evidence |

## 4. Validation

### Automated checks

- Focused readiness tests: `18 passed`
- Frontend: `28 test files`, `219 tests` passed
- Frontend typecheck and lint: PASS
- Backend ruff and mypy: PASS
- Backend unittest: `485 tests` passed
- Electron/readiness contracts: `6 passed`
- PowerShell parser/self-test: PASS
- `git diff --check`: PASS
- Added-line sensitive scan: `sensitive_hits=0`
- Source MOCK lifecycle: `/health` PASS at `1,814.3 ms`; memory stage returned in
  `153.0 ms`, all other logged stages below `1 ms`

### Package checks

- Frontend production build: PASS
- PyInstaller one-file backend: PASS
- Provenance before/after build:
  `b848755b118852df4cf1a1cc1f6c13160618c7df`
- electron-builder NSIS: PASS
- Backend source/package SHA match: PASS
- QA script source/package SHA match: PASS
- Runtime version: `1.0.14`, runtime kind: `frozen`

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

## 5. Next Action

Commit the Act 3 source, generate a clean PyInstaller/NSIS replacement, record
its hashes, then install only that build on the server for the 90-second
physical-device operational-ready measurement.
