# Gap Analysis: memory-diagnostics-r03-csv-logger-runtime

> Date: 2026-06-28 KST | Design: `docs/02-design/features/memory-diagnostics-r03-csv-logger-runtime.design.md`

---

## Match Rate: 100%

## Summary

`memory-diagnostics-r03-csv-logger-runtime`의 설계 항목을 실제 `CSVLoggerService`, memory collector, backend tests 기준으로 대조했다. CSV queue backlog, drop count, writer lag, payload bytes EMA, estimated queue bytes, collector note/bytes 계산이 모두 구현되어 있다.

계산 기준: 설계/Do checklist의 구현 항목 25개 중 25개 충족.

## Implemented Items

- [x] `CSVLoggerService.__init__()`에 `_drop_count`를 추가했다.
- [x] `_last_drop_at`을 추가했다.
- [x] `_last_enqueue_at`을 추가했다.
- [x] `_last_write_at`을 추가했다.
- [x] `_payload_bytes_ema`를 추가했다.
- [x] `_runtime_lock`을 추가했다.
- [x] `_estimate_factory_data_bytes()`를 추가했다.
- [x] `enqueue()`에서 last enqueue timestamp를 갱신한다.
- [x] `enqueue()`에서 payload bytes EMA를 갱신한다.
- [x] queue full path에서 drop count를 증가시킨다.
- [x] queue full path에서 last drop timestamp를 갱신한다.
- [x] v1 flush 완료 시 last write timestamp를 갱신한다.
- [x] v2 flush 완료 시 last write timestamp를 갱신한다.
- [x] `get_runtime_state()`에 `queue_maxsize`를 추가했다.
- [x] `get_runtime_state()`에 `queue_ratio`를 추가했다.
- [x] `get_runtime_state()`에 `drop_count`를 추가했다.
- [x] `get_runtime_state()`에 `last_drop_at`을 추가했다.
- [x] `get_runtime_state()`에 `last_enqueue_at`을 추가했다.
- [x] `get_runtime_state()`에 `last_write_at`을 추가했다.
- [x] `get_runtime_state()`에 `writer_lag_sec`를 추가했다.
- [x] `get_runtime_state()`에 `payload_bytes_ema`를 추가했다.
- [x] `get_runtime_state()`에 `estimated_queue_bytes`를 추가했다.
- [x] `_collect_csv_logger()` bytes 계산을 `estimated_queue_bytes + mapping overhead` 중심으로 변경했다.
- [x] `_collect_csv_logger()` note에 `queue=<size>/<max> drop=<count> lag=<seconds>`를 포함했다.
- [x] r03 전용 backend unittest를 추가했다.

## Missing Items

- [x] 없음.

## Changed Items

- [x] `writer_lag_sec`는 마지막 successful flush 이후 경과 시간으로 계산한다. 아직 성공한 flush가 없으면 `None`이며 collector note에는 `lag=n/a`로 표시한다.
- [x] payload bytes EMA는 첫 sample은 exact estimate, 이후 sample은 `0.8 old + 0.2 new`로 갱신한다. hot path 부하를 낮추기 위한 bounded 계산이다.

## Validation Evidence

- `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_csv_logger_runtime`: 6 passed.
- `npm run health`: passed.
  - frontend typecheck passed.
  - frontend lint passed.
  - frontend tests: 167 passed.
  - backend ruff passed.
  - backend mypy passed.
  - backend tests: 321 passed.
- `git diff --check`: passed with LF/CRLF warnings only.
- `bkit_pdca_analyze(memory-diagnostics-r03-csv-logger-runtime)`: executed and returned analysis template/guidance.

## Operational Assessment

- Rollback path: remove CSV runtime counters and revert `_collect_csv_logger()` to mapping estimate.
- Observability impact: `facility.csv_logger` now separates queue size, queue capacity, drop count, writer lag, and estimated queue bytes.
- Migration risk: none. CSV file schema and queue maxsize are unchanged.
- Test coverage gap: production-like writer backlog duration is not exercised; local tests cover queue full, lag state, EMA, and collector output.
- Operational failure mode: counter update failure falls back to existing enqueue/drop behavior; writer loop semantics are unchanged.

## Recommendations

1. r03 can proceed to report because match rate is 100% and validation gates passed.
2. r04 should start only after `.pdca-status.json` records r03 completed and r04 active/do.

## Next Steps

- [x] Write r03 report.
- [x] Mark r03 completed after report.
- [ ] Activate `memory-diagnostics-r04-spot-cache`.
