# Memory Diagnostics R02 PLC History Plan

## 1. Summary

- Feature: `memory-diagnostics-r02-plc-history`
- Parent roadmap: `memory-diagnostics-hardening`
- Rank: 2
- Dependency: `memory-diagnostics-r01-collector-contract` Report 완료

## 2. Business Goal

PLC history deque는 상시 resident buffer 후보 중 가장 크다. 현재 최신 PLC scalar만 계측하므로, 1시간 history가 실제로 얼마나 메모리를 점유하는지 `/api/memory/details`와 UI에서 확인할 수 있어야 한다.

## 3. Scope

- `PLCService.get_history_memory_summary(sample_size=128)` 추가
- lock 안에서는 count, bounds, bounded sample copy만 수행
- lock 밖에서 `estimate_size_bytes()` 실행
- `facility.plc_history` collector 등록
- Backend growth table에 count, fill ratio, average bytes per sample 노출

## 4. Out Of Scope

- PLC history retention 정책 변경
- `HISTORY_MAX_SAMPLES` 변경
- `/api/data/history` 응답 구조 변경
- PLC loop 주기 변경

## 5. Acceptance Criteria

- `facility.plc_history`가 backend collector로 등록된다.
- history count, max samples, oldest/newest timestamp, sample size, estimated bytes, average bytes, fill ratio가 반환된다.
- `history_lock`을 잡은 상태에서 recursive size estimate를 수행하지 않는다.
- empty history에서도 zero-safe response를 반환한다.

## 6. Validation Gate

- PLCService summary unit test 통과
- lock-held section 검증 테스트 통과
- collector registration test 통과
- `npm run health` 통과
- bkit analyze match rate 90% 이상

## 7. Rollback

문제가 생기면 `_register_memory_collectors()`에서 `facility.plc_history` 등록만 제거한다. PLC history 저장 로직은 변경하지 않으므로 데이터 손실 rollback은 필요 없다.
