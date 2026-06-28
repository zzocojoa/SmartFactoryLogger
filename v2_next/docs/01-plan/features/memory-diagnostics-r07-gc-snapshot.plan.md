# Memory Diagnostics R07 GC Snapshot Plan

## 1. Summary

- Feature: `memory-diagnostics-r07-gc-snapshot`
- Parent roadmap: `memory-diagnostics-hardening`
- Rank: 7
- Dependency: `memory-diagnostics-r06-leak-slope` Report 완료

## 2. Business Goal

회수 가능한 객체 증가와 retained memory 증가를 구분하기 위해 수동 GC 전후 snapshot을 제공한다. 자동 sampler에서 GC를 호출하지 않고 operator가 명시적으로 실행할 때만 비교한다.

## 3. Scope

- `MemoryService.capture_gc_snapshot()` 추가
- gen0, gen1, gen2 수동 collect
- before/after process sample과 rss/uss/private delta 계산
- `POST /api/memory/gc` endpoint 추가
- MemorySection에 GC 비교 버튼과 결과 표시
- export payload에 latest GC snapshot 포함 준비

## 4. Out Of Scope

- sampler thread에서 자동 GC 실행
- GC 튜닝
- object graph 분석
- endpoint 권한 체계 신규 설계

## 5. Acceptance Criteria

- GC snapshot은 before, after, delta, collected, latency를 반환한다.
- endpoint 실패 시 500과 backend error log를 남긴다.
- UI에서 GC delta와 latency를 확인할 수 있다.
- 자동 sampler는 GC를 호출하지 않는다.

## 6. Validation Gate

- backend GC snapshot unit test 통과
- endpoint failure handling test 통과
- frontend GC rendering test 통과
- `npm run health` 통과
- bkit analyze match rate 90% 이상

## 7. Rollback

`POST /api/memory/gc` endpoint와 UI 버튼을 제거한다. MemoryService process sample 수집 로직은 원상 유지한다.
