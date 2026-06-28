# Report: memory-diagnostics-r01-collector-contract

> Date: 2026-06-28 KST | Parent: `memory-diagnostics-hardening`

## Summary

- Feature: `memory-diagnostics-r01-collector-contract`
- Rank: 1
- Status: completed
- Match rate: 100%
- Scope: MemoryService collector common runtime contract and optional UI rendering

r01은 collector 실행 자체가 sampler/API 장애로 확산되지 않도록 공통 runtime contract를 추가했다. 변경은 additive이며 기존 memory endpoint field는 제거하지 않았다.

## Completed Items

- `MemoryService`에 collector runtime state를 추가했다.
- collector별 latency, status, last ok/error timestamp, error count, stale, source를 backend item에 추가했다.
- collector 예외는 전체 sampler 실패 대신 per-collector `status=error` item으로 격리된다.
- slow collector는 `status=slow`로 표시된다.
- hard timeout 또는 thread kill 없이 previous `last_value` cache reuse 정책을 적용했다.
- cache reuse output은 `status=stale`와 note로 새 실행 결과와 구분된다.
- `stale=true`는 `_collector_stale_after_sec`를 넘은 마지막 성공 기준으로만 계산된다.
- backend growth payload도 새 runtime fields를 전달한다.
- frontend type은 새 fields를 optional로 받는다.
- `MemorySection` growth table은 status와 latency를 표시한다.
- 구버전 payload는 field 누락 시 fallback으로 렌더링된다.

## Files Changed

- `backend/Observability/memory_service.py`: collector runtime state, latency/status/stale/error/cache reuse contract.
- `backend/tests/test_memory_service.py`: exception isolation, latency, slow threshold, stale state, cache reuse tests.
- `frontend/src/shared/types.ts`: optional collector runtime fields.
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`: status/latency optional rendering.
- `frontend/src/App.css`: memory growth table grid width/columns.
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.test.tsx`: old payload compatibility and runtime field rendering tests.
- `docs/03-analysis/memory-diagnostics-r01-collector-contract.analysis.md`: PDCA check analysis.

## Engineering Assessment

- Risk level: high, operational diagnostics path.
- Compatibility impact: additive API/UI fields only. Existing fields remain.
- Security impact: no secrets, credentials, file contents, PLC commands, or arbitrary IPC added. Collector exception notes are sanitized to exception type only.
- Rollback path: revert `MemoryService` runtime state/normalize changes and UI columns; existing collectors and endpoints continue to exist.
- Migration risk: none. No DB, CSV schema, or config migration.
- Observability impact: operators can now distinguish collector failures, slow collectors, stale results, and cached reuse.
- Operational failure mode: failed collectors produce isolated error rows; sampler loop continues.

## Validation

- `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_memory_service`: 14 passed.
- `npm --prefix frontend run test -- MemorySection.test.tsx`: 2 passed.
- `npm --prefix frontend run typecheck`: passed.
- `git diff --check`: passed.
- `npm run health`: passed.
  - frontend typecheck passed
  - frontend lint passed
  - frontend tests: 167 passed
  - backend ruff passed
  - backend mypy passed
  - backend tests: 311 passed

## Review

- bkit pre-write/post-write checks were run for modified source/test/docs files.
- bkit analyze guidance was run and this analysis records 100% match rate.
- gstack-style pre-landing review equivalent was performed against the r01 diff.
- UI smoke equivalent is covered by `MemorySection.test.tsx`.

## Remaining Risk

- Real production slow-collector behavior still depends on future heavier collectors. r01 provides the safety contract, but r02/r03 must validate PLC/CSV collector behavior under production-like load.
- The UI shows runtime status in the existing settings table only. No full browser/manual visual QA was run because this was a narrow optional-rendering change and Vitest render coverage verified the affected UI path.

## Next Action

Proceed with `memory-diagnostics-r02-plc-history` Do implementation next. `.pdca-status.json` now records r01 as completed and r02 as active.
