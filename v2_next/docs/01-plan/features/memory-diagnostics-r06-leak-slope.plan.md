# Memory Diagnostics R06 Leak Slope Plan

## 1. Summary

- Feature: `memory-diagnostics-r06-leak-slope`
- Parent roadmap: `memory-diagnostics-hardening`
- Rank: 6
- Dependency: `memory-diagnostics-r05-budget-severity` Report 완료

## 2. Business Goal

일시적인 spike와 지속적인 메모리 증가를 구분한다. process history와 collector history를 활용해 slope와 monotonic ratio를 계산하고, 결과는 leak 확정이 아니라 `leak_suspect`로 표시한다.

## 3. Scope

- `_calc_slope_bytes_per_min()` 추가
- process `rss_bytes`, `uss_bytes`, `private_bytes` slope 분석
- collector별 bytes series slope 분석
- monotonic ratio와 baseline 대비 증가율 계산
- `/api/memory/details`에 `leak_suspects` 추가
- UI에 누수 의심 섹션 추가

## 4. Out Of Scope

- leak 확정 판정
- 자동 GC 실행
- heap object ownership 분석
- 장기 production threshold 최종화

## 5. Acceptance Criteria

- 최소 샘플 미달 시 빈 result를 반환한다.
- steady growth fixture는 leak suspect로 잡힌다.
- one-shot spike fixture는 leak suspect로 잡히지 않는다.
- UI 문구는 "누수 의심"으로 제한한다.

## 6. Validation Gate

- slope calculation unit test 통과
- monotonic growth detection test 통과
- spike false-positive 방지 test 통과
- frontend rendering test 통과
- bkit analyze match rate 90% 이상

## 7. Rollback

trend analysis 호출과 UI leak suspect section을 제거한다. 기존 process/collector history 저장은 유지한다.
