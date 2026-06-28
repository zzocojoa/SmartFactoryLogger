# Memory Diagnostics R01 Collector Contract Plan

## 1. Summary

- Feature: `memory-diagnostics-r01-collector-contract`
- Parent roadmap: `memory-diagnostics-hardening`
- Rank: 1
- PDCA policy: 이 feature의 Report가 완료되기 전에는 2순위 구현으로 넘어가지 않는다.

## 2. Business Goal

Memory collector 자체가 운영 장애 원인이 되지 않도록 collector 실행 시간, 실패, stale 상태를 공통 계약으로 노출한다. 이후 PLC history, CSV queue, SPOT cache 같은 무거운 collector를 추가해도 sampler thread와 `/api/memory/details`가 안정적으로 유지되어야 한다.

## 3. Scope

- `backend/Observability/memory_service.py`의 collector 실행 계약 확장
- collector별 latency, status, error count, last ok/error timestamp, stale 여부 저장
- slow collector의 previous cache reuse 정책과 `last_latency_ms`, `last_value` runtime state 저장
- `/api/memory/details`의 backend collector item에 새 필드 추가
- frontend type과 MemorySection이 새 필드를 optional로 표시하도록 준비

## 4. Out Of Scope

- PLC history collector 구현
- CSV logger runtime counter 구현
- hard timeout 또는 강제 thread 중단
- export schema v2

## 5. Acceptance Criteria

- collector item에 `latency_ms`, `status`, `last_ok_at`, `last_error_at`, `error_count`, `stale`, `source`가 포함된다.
- collector 예외는 전체 sampler 실패가 아니라 해당 collector의 error item으로 격리된다.
- slow collector는 `status=slow`로 표시된다.
- stale collector는 이전 성공 상태와 별도로 stale 여부가 노출된다.
- soft timeout은 hard kill이 아니라 previous `last_value` cache reuse로 처리한다.
- 기존 payload를 받는 UI가 깨지지 않는다.

## 6. Validation Gate

- targeted MemoryService tests 통과
- frontend typecheck 통과
- `npm run health` 통과
- `git diff --check` 통과
- bkit analyze match rate 90% 이상
- gstack review에서 blocking issue 없음

## 7. Rollback

이 변경은 additive field 확장이므로 rollback은 MemoryService runtime state와 UI 표시 컬럼을 되돌리는 방식으로 한다. 기존 collector 등록과 기존 memory endpoint는 유지되어야 한다.
