# Report: memory-diagnostics-r05-budget-severity

> Date: 2026-06-28 KST | Parent: `memory-diagnostics-hardening`

## Summary

- Feature: `memory-diagnostics-r05-budget-severity`
- Rank: 5
- Status: completed
- Match rate: 100%
- Scope: backend memory budgets, collector severity metadata, severity-first backend/frontend sorting

r05 adds default memory budgets and surfaces `severity`, `severity_reasons`, and `budget` on backend collector items. The MemorySection growth table now defaults to severity-first ordering and displays a severity column while keeping existing delta/size sort controls.

## Completed Items

- Added backend `DEFAULT_MEMORY_BUDGETS`.
- Added `_apply_budget()` for bytes, queue ratio, and growth-per-minute warn checks.
- Added `severity`, `severity_reasons`, and `budget` to normalized collector items and backend growth rows.
- Preserved queue ratio/capacity metadata on `facility.csv_logger`.
- Sorted backend growth by severity, then delta, then bytes.
- Added frontend shared types for severity and budget metadata.
- Added MemorySection severity column and default severity sort.
- Updated MemorySection table CSS grid for the new column.
- Added backend tests for `facility.plc_history` warn/critical, `facility.csv_logger` ratio critical, and growth severity sort.
- Added frontend DOM render test for severity-first table ordering.

## Files Changed

- `backend/Observability/memory_service.py`: budget table, severity engine, severity metadata, growth sorting.
- `backend/app.py`: `facility.csv_logger` queue ratio/capacity metadata for budget evaluation.
- `backend/tests/test_memory_service.py`: r05 backend budget/severity tests.
- `frontend/src/shared/types.ts`: memory severity/budget field types.
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`: severity column and severity-first sort.
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.test.tsx`: r05 UI render/sort regression test.
- `frontend/src/App.css`: table grid width for severity column.
- `docs/03-analysis/memory-diagnostics-r05-budget-severity.analysis.md`: gap analysis and match rate evidence.

## Engineering Assessment

- Risk level: medium, because memory diagnostics influence operational triage.
- Compatibility impact: additive fields only. Existing collector fields and sort controls remain.
- Security impact: no credentials, raw URLs, or secret-like values are introduced.
- Rollback path: remove severity sort/column and bypass `_apply_budget()` while leaving collector source data intact.
- Migration risk: none. No persistent schema or config migration.
- Observability impact: risk-bearing collectors are visible before merely large collectors.
- Operational failure mode: unknown collectors or missing budget metadata default to `severity="ok"` with `budget=null`.
- Test coverage gap: production thresholds are defaults and still need operational calibration.

## Validation

- `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_memory_service`: 17 passed.
- `npm --prefix frontend run test -- src/domains/Configuration/components/SettingsModal/MemorySection.test.tsx`: 3 passed.
- `npm run health`: passed.
  - frontend typecheck passed.
  - frontend lint passed.
  - frontend tests: 168 passed.
  - backend ruff passed.
  - backend mypy passed.
  - backend tests: 326 passed.
- `git diff --check`: passed with LF/CRLF warnings only.
- `bkit_pdca_analyze memory-diagnostics-r05-budget-severity`: executed; manual implementation comparison recorded 100% match.
- UI smoke evidence: MemorySection DOM render test validates severity column values and default severity-first row order.

## Review

- bkit pre-write checks were run for backend source, app collector metadata, backend tests, frontend types/UI/CSS/tests, and doc files.
- bkit post-write checks were run for modified source, frontend, test, and doc files.
- Completed r04 state was rechecked before r05 implementation.

## Next Action

Activate `memory-diagnostics-r06-leak-slope` in `.pdca-status.json` and continue with r06 Do implementation.
