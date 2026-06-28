# Gap Analysis: memory-diagnostics-r01-collector-contract

> Date: 2026-06-28 KST | Design: `docs/02-design/features/memory-diagnostics-r01-collector-contract.design.md`

---

## Match Rate: 100%

## Summary

`memory-diagnostics-r01-collector-contract` 설계의 핵심 항목은 모두 구현됐다. 변경은 collector 공통 실행 계약과 optional UI 표시로 제한했고, `memory-diagnostics-r02-plc-history` 이후 기능은 구현하지 않았다.

계산 기준: 설계/Do checklist에서 r01 범위로 정의된 18개 구현 항목 중 18개 완료.

## Implemented Items

- [x] `MemoryService`에 `_collector_runtime_state`를 추가했다.
- [x] `_collector_latency_warn_ms = 250.0`을 추가했다.
- [x] `_collector_stale_after_sec = 60.0`을 추가했다.
- [x] `_run_collectors()`에서 collector 호출 latency를 `time.perf_counter()`로 측정한다.
- [x] 정상 collector item에 `latency_ms`를 추가한다.
- [x] 정상 collector item에 `status=ok|slow`를 추가한다.
- [x] error collector item에 `status=error`를 추가한다.
- [x] collector별 `last_ok_at`, `last_error_at`, `error_count`, `last_latency_ms`, `last_value`, `last_value_at`을 저장한다.
- [x] `stale`은 마지막 성공 시간이 stale threshold를 넘었는지 기준으로 계산한다.
- [x] item에 `source=backend`를 추가한다.
- [x] hard timeout이나 thread kill 없이 slow collector의 previous value reuse 정책을 구현했다.
- [x] previous cache reuse item은 `status=stale`와 note `cached previous collector result`로 새 실행 결과와 구분된다.
- [x] 기존 collector item field인 `name`, `kind`, `exactness`, `bytes`, `items`, `note`를 유지했다.
- [x] backend growth payload에도 runtime fields를 additive로 전달한다.
- [x] frontend shared type에 runtime fields를 optional로 추가했다.
- [x] `MemorySection` growth table에 status/latency 표시를 추가했다.
- [x] 구버전 payload에는 fallback `--` 표시가 적용되어 crash 없이 렌더링된다.
- [x] backend/frontend targeted tests와 full health가 통과했다.

## Missing Items

- [x] 없음.

## Changed Items

- [x] cache reuse item은 `status=stale`로 표시하지만 `stale=true`는 threshold 초과 시에만 켜지도록 했다. 설계의 "status 또는 note/source metadata로 구분" 요구를 만족하면서 `stale` boolean의 의미를 운영상 더 정확하게 유지하기 위한 조정이다.

## Review Evidence

- Manual pre-landing review: r01 범위, failure isolation, stale/cache semantics, UI backward compatibility를 확인했고 blocking issue 없음.
- UI smoke equivalent: `MemorySection.test.tsx`가 old payload 렌더링과 optional status/latency 표시를 검증한다.

## Validation Evidence

- `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_memory_service`: 14 passed.
- `npm --prefix frontend run test -- MemorySection.test.tsx`: 2 passed.
- `npm --prefix frontend run typecheck`: passed.
- `git diff --check`: passed.
- `npm run health`: frontend typecheck, frontend lint, 167 frontend tests, backend ruff, backend mypy, 311 backend tests passed.

## Recommendations

1. r01은 report 단계로 진행한다.
2. 다음 구현은 `memory-diagnostics-r02-plc-history`로 이동하되, PLC history collector 구현 전 별도 bkit pre-write check를 다시 실행한다.

## Next Steps

- [x] Report 문서를 작성한다.
- [x] r01 feature를 completed/report 상태로 갱신한다.
- [ ] r02는 다음 순위 작업에서 시작한다.
