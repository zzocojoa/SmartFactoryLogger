# Report: memory-diagnostics-r06-leak-slope

> Date: 2026-06-28 KST | Parent: `memory-diagnostics-hardening`

## Summary

- Feature: `memory-diagnostics-r06-leak-slope`
- Rank: 6
- Status: completed
- Match rate: 100%
- Scope: process/collector rolling trend analysis and UI leak suspect display

r06 adds slope-based leak suspect detection using rolling process and collector history. It intentionally reports “누수 의심” only; it does not claim leak confirmation, trigger GC, or perform heap ownership analysis.

## Completed Items

- Added `_calc_slope_bytes_per_min()` and monotonic ratio calculation.
- Added process trend analysis for `rss_bytes`, `uss_bytes`, and `private_bytes`.
- Added collector trend analysis by collector name.
- Added suspect conditions: `slope_bytes_per_min >= warn_growth_per_min`, `monotonic_ratio >= 0.75`, and latest bytes at least 1.20x baseline.
- Added `self._latest_leak_suspects`.
- Added `leak_suspects` to `/api/memory/details`.
- Added frontend `MemoryLeakSuspect` type.
- Added MemorySection “누수 의심” section.
- Added backend tests for slope calculation, insufficient samples, steady growth detection, and spike false-positive prevention.
- Added frontend render test confirming suspect wording and no “확정” wording.

## Files Changed

- `backend/Observability/memory_service.py`: slope helper, trend analysis, `leak_suspects` API field.
- `backend/tests/test_memory_service.py`: r06 slope and leak suspect regression tests.
- `frontend/src/shared/types.ts`: `MemoryLeakSuspect` type and details response field.
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`: “누수 의심” UI section.
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.test.tsx`: r06 UI wording/render test.
- `docs/03-analysis/memory-diagnostics-r06-leak-slope.analysis.md`: gap analysis and match rate evidence.

## Engineering Assessment

- Risk level: medium, because diagnostics influence operational triage and false positives can waste response time.
- Compatibility impact: additive API field only. Existing details fields remain.
- Security impact: no credentials, URLs, or raw payloads are exposed.
- Rollback path: remove trend analysis call/output and hide the UI section.
- Migration risk: none. No persistent schema, DB, CSV, or config change.
- Observability impact: operators can see likely steady-growth suspects separate from transient spikes.
- Operational failure mode: with fewer than four samples or missing budget, no suspect is emitted.
- Test coverage gap: production threshold tuning and long-duration real workload validation are still open.

## Validation

- `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_memory_service`: 21 passed.
- `npm --prefix frontend run test -- src/domains/Configuration/components/SettingsModal/MemorySection.test.tsx`: 4 passed.
- `npm run health`: passed.
  - frontend typecheck passed.
  - frontend lint passed.
  - frontend tests: 169 passed.
  - backend ruff passed.
  - backend mypy passed.
  - backend tests: 330 passed.
- `git diff --check`: passed with LF/CRLF warnings only.
- `bkit_pdca_analyze memory-diagnostics-r06-leak-slope`: executed; manual implementation comparison recorded 100% match.
- UI smoke evidence: MemorySection DOM render test validates “누수 의심” wording and absence of “확정”.

## Review

- bkit pre-write checks were run for backend source, backend tests, frontend types/UI/tests, and doc files.
- bkit post-write checks were run for modified source, frontend, test, and doc files.
- Completed r05 state was rechecked before r06 implementation.

## Next Action

Activate `memory-diagnostics-r07-gc-snapshot` in `.pdca-status.json` and continue with r07 Do implementation.
