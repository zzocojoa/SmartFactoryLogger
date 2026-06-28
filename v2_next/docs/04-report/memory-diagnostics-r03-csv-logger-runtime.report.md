# Report: memory-diagnostics-r03-csv-logger-runtime

> Date: 2026-06-28 KST | Parent: `memory-diagnostics-hardening`

## Summary

- Feature: `memory-diagnostics-r03-csv-logger-runtime`
- Rank: 3
- Status: completed
- Match rate: 100%
- Scope: CSV logger queue/drop/lag runtime counters and `facility.csv_logger` collector bytes/note improvement

r03 adds runtime observability for CSV writer backlog without changing CSV file schema, queue capacity, writer batching policy, or retry behavior. The change is additive and keeps `facility.csv_logger` as the compatibility collector name.

## Completed Items

- Added CSV logger runtime counters for drop count, last drop, last enqueue, last successful write, and payload bytes EMA.
- Updated enqueue path to record payload estimate and drop metadata.
- Updated flush success path to record last write timestamp.
- Extended `get_runtime_state()` with queue maxsize, queue ratio, writer lag, payload bytes EMA, and estimated queue bytes.
- Changed `facility.csv_logger` collector bytes to use `estimated_queue_bytes + mapping overhead`.
- Changed collector note to `queue=<size>/<max> drop=<count> lag=<seconds>`.
- Added targeted backend tests for queue full drop, payload EMA, writer lag, queue byte scaling, and collector note/bytes.

## Files Changed

- `backend/FacilityData/repository.py`: CSV logger runtime counters, payload byte estimate, writer lag, runtime state fields.
- `backend/app.py`: `facility.csv_logger` collector bytes and note calculation.
- `backend/tests/test_csv_logger_runtime.py`: r03 runtime counter and collector regression tests.
- `docs/03-analysis/memory-diagnostics-r03-csv-logger-runtime.analysis.md`: gap analysis and match rate evidence.

## Engineering Assessment

- Risk level: medium, because CSV logging is production-impacting.
- Compatibility impact: additive runtime fields only. CSV file schema and queue maxsize are unchanged.
- Security impact: no secrets, credentials, raw file contents, URLs, or control commands added.
- Rollback path: revert runtime counter additions and restore `_collect_csv_logger()` to previous mapping estimate.
- Migration risk: none. No DB, CSV schema, or config migration.
- Observability impact: operators can distinguish queue backlog, queue saturation, writer lag, and dropped samples.
- Operational failure mode: if queue is full, behavior remains drop-and-warn; now it also records drop counters.
- Test coverage gap: no production-duration backlog test. Local tests cover deterministic queue full, lag, EMA, scaling, and collector output.

## Validation

- `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_csv_logger_runtime`: 6 passed.
- `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_memory_service backend.tests.test_data_history_api`: 22 passed for completed r01/r02 recheck.
- `npm run health`: passed.
  - frontend typecheck passed.
  - frontend lint passed.
  - frontend tests: 167 passed.
  - backend ruff passed.
  - backend mypy passed.
  - backend tests: 321 passed.
- `git diff --check`: passed with LF/CRLF warnings only.
- `bkit_pdca_analyze memory-diagnostics-r03-csv-logger-runtime`: executed; manual implementation comparison recorded 100% match.

## Review

- bkit pre-write checks were run for source, app collector, and test/doc files.
- bkit post-write checks were run for modified source and test files.
- Completed r01/r02 were rechecked against actual code and targeted tests before continuing r03.

## Next Action

Activate `memory-diagnostics-r04-spot-cache` in `.pdca-status.json` and continue with r04 Do implementation.
