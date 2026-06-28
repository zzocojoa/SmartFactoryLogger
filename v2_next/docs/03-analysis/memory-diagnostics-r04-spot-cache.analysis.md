# Gap Analysis: memory-diagnostics-r04-spot-cache

> Date: 2026-06-28 KST | Design: `docs/02-design/features/memory-diagnostics-r04-spot-cache.design.md`

---

## Match Rate: 100%

## Summary

`memory-diagnostics-r04-spot-cache`의 설계 항목을 실제 `spot_api.py`, `app.py`, backend tests 기준으로 대조했다. SPOT static image cache와 live image cache가 public summary API와 별도 memory collector로 분리됐고, raw live URL은 memory summary와 collector output에 포함되지 않는다.

계산 기준: 설계/Do checklist의 구현 항목 18개 중 18개 충족.

## Implemented Items

- [x] `spot_api.py`에 public `get_image_cache_memory_summary()`를 추가했다.
- [x] static image cache bytes를 exact `image_bytes`로 계산한다.
- [x] live image cache bytes를 exact `live_image_bytes`로 계산한다.
- [x] static image cache age를 `image_age_sec`로 계산한다.
- [x] live image cache age를 `live_image_age_sec`로 계산한다.
- [x] static image cache state/status를 `image_cache_state`/`image_cache_status`로 반환한다.
- [x] live image cache state를 `live_image_cache_state`로 반환한다.
- [x] static image failure count를 `image_failure_count`로 반환한다.
- [x] live image failure count를 `live_image_failure_count`로 반환한다.
- [x] static image retry/backoff fields를 `image_next_retry_at`, `image_retry_after_sec`, `image_current_backoff_sec`로 반환한다.
- [x] live image retry/backoff fields를 `live_image_next_retry_at`, `live_image_retry_after_sec`, `live_image_current_backoff_sec`로 반환한다.
- [x] raw live image URL 대신 boolean `live_image_url_present`만 반환한다.
- [x] `total_bytes`는 static/live image bytes 합으로 계산한다.
- [x] `spot.image_cache` memory collector를 등록했다.
- [x] `spot.live_cache` memory collector를 등록했다.
- [x] 두 split collector 모두 `exactness="exact"`로 image bytes만 보고한다.
- [x] 기존 `spot.cache`는 compatibility alias로 유지한다.
- [x] static/live bytes, retry/failure fields, raw live URL 미노출, split collector 등록 테스트를 추가했다.

## Missing Items

- [x] 없음.

## Changed Items

- [x] `spot.cache`는 제거하지 않고 compatibility alias로 유지했다. 기존 API/collector consumer를 깨지 않기 위한 additive 변경이다.
- [x] split collector의 `bytes`는 metadata overhead를 더하지 않고 image payload bytes만 보고한다. 설계의 exactness 요구를 지키기 위한 선택이다.
- [x] failure/retry state는 collector `note`에 포함했다. 현재 memory collector contract가 details field를 표준화하지 않아 기존 result shape을 유지했다.

## Validation Evidence

- `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_spot_api`: 66 passed.
- `npm run health`: passed.
  - frontend typecheck passed.
  - frontend lint passed.
  - frontend tests: 167 passed.
  - backend ruff passed.
  - backend mypy passed.
  - backend tests: 323 passed.
- `git diff --check`: passed with LF/CRLF warnings only.
- `bkit_pdca_analyze(memory-diagnostics-r04-spot-cache)`: executed and returned analysis template/guidance.

## Operational Assessment

- Rollback path: remove `spot.image_cache`/`spot.live_cache` registrations and revert `spot.cache` to the previous `_img_cache` direct byte calculation.
- Observability impact: operators can distinguish static image cache memory from live frame cache memory.
- Migration risk: none. No DB, CSV schema, or config migration.
- Security impact: raw live URL is not returned by `get_image_cache_memory_summary()` or memory collectors.
- Test coverage gap: no browser/UI smoke was run because r04 changes backend collector/API internals only.
- Operational failure mode: cache reads remain read-only; fetch, retry, backoff, and cache eviction behavior are unchanged.

## Recommendations

1. r04 can proceed to report because match rate is 100% and validation gates passed.
2. r05 should start only after `.pdca-status.json` records r04 completed and r05 active/do.

## Next Steps

- [x] Write r04 report.
- [x] Mark r04 completed after report.
- [ ] Activate `memory-diagnostics-r05-budget-severity`.
