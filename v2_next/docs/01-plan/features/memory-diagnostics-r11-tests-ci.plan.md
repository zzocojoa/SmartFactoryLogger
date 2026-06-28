# Memory Diagnostics R11 Tests CI Plan

## 1. Summary

- Feature: `memory-diagnostics-r11-tests-ci`
- Parent roadmap: `memory-diagnostics-hardening`
- Rank: 11
- Dependency: `memory-diagnostics-r10-export-v2` Report 완료

## 2. Business Goal

memory diagnostics가 운영 장애 대응 기능으로 계속 신뢰 가능하도록 backend unittest, frontend vitest, export schema regression, CI health gate를 고정한다.

## 3. Scope

- MemoryService collector exception/latency/severity/slope/GC/export tests 정리
- PLC history, CSV logger, SPOT cache tests 정리
- useMemoryViewModel exactness/Electron tests 정리
- MemorySection severity/leak/GC/Electron rendering tests 정리
- `npm run health`에 자연스럽게 포함되는지 확인

## 4. Out Of Scope

- CI provider migration
- coverage percentage gate 신규 도입
- production load test 자동화
- packaged installer release

## 5. Acceptance Criteria

- 필수 backend test 목록이 존재하고 health script에서 실행된다.
- 필수 frontend test 목록이 존재하고 health script에서 실행된다.
- export schema regression이 깨지면 health가 실패한다.
- docs/report에 남은 production evidence gap이 명확히 기록된다.

## 6. Validation Gate

- `npm run health` 통과
- backend targeted memory suite 통과
- frontend memory tests 통과
- `git diff --check` 통과
- bkit analyze match rate 90% 이상
- 최종 gstack review blocking issue 없음

## 7. Rollback

테스트 추가만 되돌릴 수 있지만, 운영 진단 회귀 방지 목적상 rollback 대신 실패 테스트의 원인을 수정하는 것을 기본 전략으로 한다.
