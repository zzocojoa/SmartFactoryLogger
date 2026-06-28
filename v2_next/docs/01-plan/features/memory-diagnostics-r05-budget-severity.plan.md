# Memory Diagnostics R05 Budget Severity Plan

## 1. Summary

- Feature: `memory-diagnostics-r05-budget-severity`
- Parent roadmap: `memory-diagnostics-hardening`
- Rank: 5
- Dependency: `memory-diagnostics-r04-spot-cache` Report 완료

## 2. Business Goal

운영자가 size와 delta를 직접 해석하지 않아도 위험 항목을 먼저 볼 수 있게 한다. collector별 budget을 기준으로 `ok`, `warn`, `critical` severity를 계산하고 UI 기본 정렬에 반영한다.

## 3. Scope

- backend default memory budget table 추가
- collector item normalize 후 budget 적용
- bytes threshold, items ratio, growth threshold 판정 기반 마련
- frontend shared type에 severity/budget field 추가
- MemorySection 기본 정렬을 severity 우선으로 변경

## 4. Out Of Scope

- 사용자 설정 UI에서 threshold 편집
- production threshold 최종 보정
- alert notification 전송
- 외부 monitoring 연동

## 5. Acceptance Criteria

- `facility.plc_history`가 200MB면 warn, 350MB면 critical로 표시된다.
- `facility.csv_logger` queue ratio threshold가 severity에 반영된다.
- `spot.live_cache` bytes threshold가 severity에 반영된다.
- Backend growth table은 critical, warn, ok 순서로 정렬된다.

## 6. Validation Gate

- warn/critical backend unit test 통과
- CSV queue ratio severity test 통과
- frontend severity sort test 통과
- `npm run health` 통과
- bkit analyze match rate 90% 이상

## 7. Rollback

severity field와 UI 정렬만 비활성화하면 기존 size/delta 기반 테이블로 돌아간다. collector 원천 데이터는 유지한다.

