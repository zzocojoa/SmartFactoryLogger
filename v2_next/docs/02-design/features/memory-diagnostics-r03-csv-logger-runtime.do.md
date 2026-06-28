# Memory Diagnostics R03 CSV Logger Runtime Do Checklist

## 1. Rule

- [ ] `memory-diagnostics-r02-plc-history` Report 완료를 확인한다.
- [ ] 완료 전에는 `memory-diagnostics-r04-spot-cache`를 구현하지 않는다.

## 2. Implementation

- [ ] `CSVLoggerService`에 `_drop_count`를 추가한다.
- [ ] `_last_drop_at`을 추가한다.
- [ ] `_last_enqueue_at`을 추가한다.
- [ ] `_last_write_at`을 추가한다.
- [ ] `_payload_bytes_ema`를 추가한다.
- [ ] `_runtime_lock`을 추가한다.
- [ ] `_estimate_factory_data_bytes()`를 추가한다.
- [ ] enqueue path에서 last enqueue timestamp를 갱신한다.
- [ ] enqueue path에서 payload bytes EMA를 갱신한다.
- [ ] queue full path에서 drop count를 증가시킨다.
- [ ] queue full path에서 last drop timestamp를 갱신한다.
- [ ] writer flush 완료 시 last write timestamp를 갱신한다.
- [ ] `get_runtime_state()`에 `queue_maxsize`를 추가한다.
- [ ] `get_runtime_state()`에 queue ratio를 추가한다.
- [ ] `get_runtime_state()`에 `drop_count`를 추가한다.
- [ ] `get_runtime_state()`에 `last_drop_at`을 추가한다.
- [ ] `get_runtime_state()`에 `last_enqueue_at`을 추가한다.
- [ ] `get_runtime_state()`에 `last_write_at`을 추가한다.
- [ ] `get_runtime_state()`에 `payload_bytes_ema`를 추가한다.
- [ ] `get_runtime_state()`에 `writer_lag_sec`를 추가한다.
- [ ] `get_runtime_state()`에 estimated queue bytes를 추가한다.
- [ ] `_collect_csv_logger()` bytes 계산을 estimated queue bytes 중심으로 바꾼다.
- [ ] note에 queue/drop/lag를 포함한다.

## 3. Tests

- [ ] full queue drop count test를 추가한다.
- [ ] payload bytes EMA test를 추가한다.
- [ ] writer lag test를 추가한다.
- [ ] estimated queue bytes scaling test를 추가한다.

## 4. Validation

- [ ] targeted CSVLoggerService tests를 실행한다.
- [ ] `npm run health`를 실행한다.
- [ ] `git diff --check`를 실행한다.
- [ ] gstack review를 실행하거나 equivalent pre-landing review를 남긴다.

## 5. PDCA Close Gate

- [ ] analysis 문서를 작성한다.
- [ ] bkit analyze match rate가 90% 이상이다.
- [ ] gap iterate를 완료한다.
- [ ] report 문서를 작성한다.
- [ ] 다음 feature 시작 가능 상태로 status를 갱신한다.
