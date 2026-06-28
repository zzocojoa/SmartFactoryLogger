# Memory Diagnostics R03 CSV Logger Runtime Plan

## 1. Summary

- Feature: `memory-diagnostics-r03-csv-logger-runtime`
- Parent roadmap: `memory-diagnostics-hardening`
- Rank: 3
- Dependency: `memory-diagnostics-r02-plc-history` Report 완료

## 2. Business Goal

CSV writer 지연이나 queue 적체가 메모리 증가의 원인인지 확인할 수 있어야 한다. 현재 `facility.csv_logger`는 queue size와 buffer size만 보여주므로 drop count, writer lag, estimated queue bytes를 추가한다.

## 3. Scope

- `CSVLoggerService` runtime counters 추가
- enqueue 시 payload bytes EMA와 drop count 기록
- writer flush 후 last write timestamp 기록
- `get_runtime_state()`에 queue max, ratio, lag, estimated bytes 추가
- `facility.csv_logger` collector bytes 계산을 queue backlog 중심으로 변경

## 4. Out Of Scope

- CSV 파일 포맷 변경
- queue maxsize 변경
- writer batching 정책 변경
- drop 복구 또는 retry queue 구현

## 5. Acceptance Criteria

- queue full 시 `_drop_count`와 `_last_drop_at`이 증가한다.
- `estimated_queue_bytes`가 queue size와 payload bytes EMA에 비례한다.
- writer lag가 마지막 write 이후 시간으로 계산된다.
- Memory UI note/detail에서 `queue=.../... drop=... lag=...s`를 확인할 수 있다.

## 6. Validation Gate

- full queue drop counter test 통과
- writer lag test 통과
- queue bytes scaling test 통과
- `npm run health` 통과
- bkit analyze match rate 90% 이상

## 7. Rollback

runtime counter와 collector bytes 계산을 기존 mapping estimate 방식으로 되돌린다. CSV 저장 데이터와 파일 schema는 변경하지 않는다.
