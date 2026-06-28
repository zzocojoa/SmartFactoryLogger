# Gap Analysis: memory-diagnostics-r06-leak-slope

> Date: 2026-06-28 KST | Design: `docs/02-design/features/memory-diagnostics-r06-leak-slope.design.md`

---

## Match Rate: 100%

## Summary

`memory-diagnostics-r06-leak-slope`의 설계 항목을 실제 `memory_service.py`, frontend MemorySection, backend/frontend tests 기준으로 대조했다. Rolling process/collector history 기반 slope, monotonic ratio, baseline increase 조건이 구현됐고 API/UI에는 `leak_suspects`만 노출한다. UI 문구는 “누수 의심”으로 제한되어 확정 표현을 사용하지 않는다.

계산 기준: 설계/Do checklist의 구현 항목 19개 중 19개 충족.

## Implemented Items

- [x] `_calc_slope_bytes_per_min()`을 추가했다.
- [x] 최소 sample count가 4 미만이면 slope는 0을 반환한다.
- [x] x축을 첫 timestamp 기준 minutes 단위로 normalize한다.
- [x] least squares slope를 사용한다.
- [x] monotonic ratio helper를 추가했다.
- [x] process `rss_bytes` series를 분석한다.
- [x] process `uss_bytes` series를 분석한다.
- [x] process `private_bytes` series를 분석한다.
- [x] collector history에서 name별 `bytes` series를 분석한다.
- [x] 최소 샘플 미달 시 `leak_suspects`는 빈 result를 반환한다.
- [x] slope threshold는 `warn_growth_per_min` budget과 연결했다.
- [x] monotonic ratio `>= 0.75` 조건을 적용했다.
- [x] baseline 대비 latest `>= 1.20x` 조건을 적용했다.
- [x] `self._latest_leak_suspects`를 추가했다.
- [x] `_apply_snapshot()` 이후 trend analysis를 호출한다.
- [x] `/api/memory/details` 응답에 `leak_suspects`를 추가했다.
- [x] frontend shared type에 `MemoryLeakSuspect`를 추가했다.
- [x] UI에 “누수 의심” 섹션을 추가했다.
- [x] UI와 payload classification은 `leak_suspect`로 제한하고 확정 표현을 쓰지 않는다.

## Missing Items

- [x] 없음.

## Changed Items

- [x] process memory fields용 growth budget key를 `DEFAULT_MEMORY_BUDGETS`에 추가했다. collector budget과 같은 threshold source를 사용하기 위한 additive 확장이다.
- [x] leak suspect output은 alert가 아니라 details payload의 diagnostic list다. r06 범위는 notification 전송이 아니다.
- [x] UI smoke evidence는 screenshot 대신 `MemorySection.test.tsx` DOM render test로 남겼다. repo에 `qa:screenshots` script가 없고 r06 UI 변경은 component render wording에 한정된다.

## Validation Evidence

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
- `bkit_pdca_analyze(memory-diagnostics-r06-leak-slope)`: executed and returned analysis template/guidance.

## Operational Assessment

- Rollback path: remove `leak_suspects` calculation/output and the UI section. Existing process and collector history storage remains.
- Observability impact: steady growth can be separated from one-shot spikes before operators inspect raw series manually.
- Migration risk: none. No DB, CSV schema, or config migration.
- Security impact: no secret-bearing fields added; output is numeric trend metadata.
- Test coverage gap: thresholds are default heuristics and still require production calibration.
- Operational failure mode: insufficient history or missing budget returns no suspect rather than producing a false positive.

## Recommendations

1. r06 can proceed to report because match rate is 100% and validation gates passed.
2. r07 should start only after `.pdca-status.json` records r06 completed and r07 active/do.

## Next Steps

- [x] Write r06 report.
- [x] Mark r06 completed after report.
- [ ] Activate `memory-diagnostics-r07-gc-snapshot`.
