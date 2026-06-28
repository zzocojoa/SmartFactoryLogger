# Gap Analysis: memory-diagnostics-r05-budget-severity

> Date: 2026-06-28 KST | Design: `docs/02-design/features/memory-diagnostics-r05-budget-severity.design.md`

---

## Match Rate: 100%

## Summary

`memory-diagnostics-r05-budget-severity`의 설계 항목을 실제 `memory_service.py`, `app.py`, frontend type/UI, backend/frontend tests 기준으로 대조했다. Backend default budget table, collector item severity metadata, CSV queue ratio 판정, backend growth severity-first sort, frontend severity column/default sort가 구현되어 있다.

계산 기준: 설계/Do checklist의 구현 항목 18개 중 18개 충족.

## Implemented Items

- [x] `DEFAULT_MEMORY_BUDGETS`를 backend memory service에 추가했다.
- [x] `facility.plc_history` warn/critical bytes threshold를 추가했다.
- [x] `facility.csv_logger` warn/critical items ratio threshold를 추가했다.
- [x] `spot.live_cache` warn/critical bytes threshold를 추가했다.
- [x] `_apply_budget()`를 추가했다.
- [x] collector item에 `severity`를 추가했다.
- [x] collector item에 `severity_reasons`를 추가했다.
- [x] collector item에 `budget` metadata를 추가했다.
- [x] collector item에 `items_ratio`, `items_capacity`, `growth_bytes_per_min` metadata를 보존한다.
- [x] `facility.csv_logger` collector output에 queue ratio/capacity metadata를 추가했다.
- [x] backend growth payload에도 severity/budget metadata를 전파한다.
- [x] backend growth sorting을 `critical > warn > ok`, `delta_bytes desc`, `bytes desc` 순서로 변경했다.
- [x] frontend shared type에 `MemorySeverity`, `MemoryBudget`, budget fields를 추가했다.
- [x] MemorySection에 severity column을 추가했다.
- [x] MemorySection 기본 sort mode를 `severity`로 변경했다.
- [x] MemorySection severity sort는 severity, delta, bytes 순서로 정렬한다.
- [x] CSS grid에 severity column width를 추가해 table layout을 유지했다.
- [x] backend/frontend targeted tests를 추가했다.

## Missing Items

- [x] 없음.

## Changed Items

- [x] `app.py`에 r05 범위 외 파일 변경이 1개 포함됐다. 이유는 `facility.csv_logger` queue ratio/capacity가 실제 collector result에 없으면 운영 데이터에서 ratio severity를 계산할 수 없기 때문이다.
- [x] growth threshold는 `growth_bytes_per_min` metadata를 기반으로 warn 판정까지 구현했다. 현재 설계에는 critical growth threshold가 없으므로 critical로 승격하지 않는다.
- [x] UI smoke evidence는 screenshot 대신 `MemorySection.test.tsx` DOM render test로 남겼다. repo에 `qa:screenshots` script가 없고 r05 UI 변경은 component table render/sort에 한정된다.

## Validation Evidence

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
- `bkit_pdca_analyze(memory-diagnostics-r05-budget-severity)`: executed and returned analysis template/guidance.

## Operational Assessment

- Rollback path: keep collector source data and disable `_apply_budget()`/frontend severity sort, returning to size/delta-only table behavior.
- Observability impact: risk-bearing collectors now surface explicit `ok`, `warn`, `critical` severity and reasons.
- Migration risk: none. No DB, CSV schema, or config migration.
- Security impact: no secret-bearing fields added; budget metadata is static numeric threshold data.
- Test coverage gap: threshold values are initial defaults and not calibrated against production baselines.
- Operational failure mode: if budget metadata is missing, collector severity defaults to `ok` and existing table rendering remains compatible.

## Recommendations

1. r05 can proceed to report because match rate is 100% and validation gates passed.
2. r06 should start only after `.pdca-status.json` records r05 completed and r06 active/do.

## Next Steps

- [x] Write r05 report.
- [x] Mark r05 completed after report.
- [ ] Activate `memory-diagnostics-r06-leak-slope`.
