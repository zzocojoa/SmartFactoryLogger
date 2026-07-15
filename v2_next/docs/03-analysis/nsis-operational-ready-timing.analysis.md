# Gap Analysis: NSIS Operational Ready Timing

> Date: 2026-07-16 | Design: `docs/02-design/features/nsis-operational-ready-timing.design.md`
> Source commit: `125c87d7e44fd7073497d579785ccaa27ac919af`

---

## Match Rate: 100%

Twenty implementation and validation checks were compared with the ten
functional requirements and ten acceptance criteria. All twenty are satisfied.
One false-positive gap was found during packaged validation and corrected in the
Act iteration before the final build.

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

## Requirement Results

| Requirement | Result | Evidence |
|-------------|--------|----------|
| FR-01 visual compatibility | PASS | Existing startup tests and full frontend suite pass |
| FR-02 session correlation | PASS | `startupSessionId` is attached to every main log entry |
| FR-03 backend readiness | PASS | `markBackendHealthReady(health)` records first response once |
| FR-04 real live-data readiness | PASS | Exact normalized `Status=Running`, non-empty time, positive finite timestamp |
| FR-05 gate/paint state machine | PASS | Two gate-order tests and final two-frame assertion |
| FR-06 fail-closed timeout | PASS | Missing-gate test plus packaged error-snapshot timeout |
| FR-07 structured measurement | PASS | Self-test and packaged PASS/FAIL JSON |
| FR-08 contamination rejection | PASS | Process and multi-session classification contract |
| FR-09 clean package | PASS | PyInstaller provenance and electron-builder NSIS pass |
| FR-10 version identity | PASS | Root/frontend/backend all `1.0.14`; artifact filename matches |

## Acceptance Criteria

| AC | Result | Evidence |
|----|--------|----------|
| AC-01 | PASS | `renderer.dashboard-ready` tests remain green |
| AC-02 | PASS | backend gate is one-shot under duplicated health input |
| AC-03 | PASS | invalid timestamp and Initializing/Offline/Error matrix rejected |
| AC-04 | PASS | timestamped Running snapshot records once |
| AC-05 | PASS | backend-data-paint and paint-data-backend order tests pass |
| AC-06 | PASS | 30-second timeout names missing gates and emits no ready event |
| AC-07 | PASS | parser/session/milestone/failure self-test PASS |
| AC-08 | PASS | full health, parser, diff, and sensitive scan pass |
| AC-09 | PASS | clean frontend/PyInstaller/NSIS build and hashes recorded |
| AC-10 | PASS | `Setup 1.0.14.exe` plus runtime health `app_version=1.0.14` |

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

## Validation Results

| Check | Result |
|-------|--------|
| Focused startup telemetry | `18 passed` |
| Frontend full suite | `28 files, 219 tests passed` |
| Frontend typecheck/lint | PASS |
| Backend ruff/mypy | PASS |
| Backend unittest | `484 tests passed` |
| Electron/source contracts | `6 passed` |
| PowerShell parser/self-test | PASS |
| Added-line sensitive scan | `0 hits` |
| `git diff --check` | PASS |
| Frontend production build | PASS |
| PyInstaller provenance | clean HEAD verified before/after packaging |
| NSIS electron-builder | PASS |

PyInstaller repeated its existing non-blocking `Hidden import "tzdata" not
found` warning. No timezone behavior was changed by this feature, and the full
health/package build completed successfully.

## Final Package Evidence

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

## Missing Items

None within the Plan scope. Physical-device timing is intentionally performed
on the server computer because the development PC has no connected PLC/SPOT
hardware. The packaged QA script is included for that final operational sample.

## Deviations from Design

- `backend/version.py` and `CHANGELOG.md` were added to the implementation set so
  runtime health and release identity match the installer.
- The measurement script is bundled under `resources/qa` rather than remaining
  source-only, improving server reproducibility without changing runtime code.
- The live predicate was strengthened during Act to exact `Status=Running` after
  packaged evidence proved that timestamp alone was insufficient.

## Recommendation

Proceed to the final PDCA report and preserve only the final `591C268D...`
installer. On the server computer, run the bundled measurement with the app and
backend fully stopped before launch; retain its JSON as physical-device timing
evidence.
