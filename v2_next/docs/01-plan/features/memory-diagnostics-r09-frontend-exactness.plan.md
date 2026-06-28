# Memory Diagnostics R09 Frontend Exactness Plan

## 1. Summary

- Feature: `memory-diagnostics-r09-frontend-exactness`
- Parent roadmap: `memory-diagnostics-hardening`
- Rank: 9
- Dependency: `memory-diagnostics-r08-electron-memory` Report 완료

## 2. Business Goal

frontend memory 수치가 관측값인지, 열거 기반 추정인지, 단순 heuristic인지, 미지원인지 명확히 구분한다. 운영자가 신뢰도가 다른 값을 같은 의미로 해석하지 않게 한다.

## 3. Scope

- Alert severity confidence weighting for `observed`, `estimated`, and `unavailable`

- `MemoryExactness` type 확장
- browser memory API result를 `observed`로 표시
- storage enumeration을 `estimated-enumerated`로 표시
- app structure heuristic을 `estimated`로 표시
- unsupported mode를 `unavailable`로 표시
- UI exactness badge와 alert reason 개선

## 4. Out Of Scope

- browser memory API polyfill
- 정확한 object-level frontend heap 분석
- frontend collector sampling interval 변경
- external browser profiling 연동

## 5. Acceptance Criteria

- Alert severity must not treat unsupported or low-confidence estimated values as equally reliable observed values.

- UI exact column이 `estimated`만 반복하지 않는다.
- unsupported browser memory는 `unavailable`로 표시된다.
- local/session storage는 `estimated-enumerated`로 표시된다.
- observed heap과 heuristic estimate가 UI에서 구분된다.

## 6. Validation Gate

- useMemoryViewModel exactness tests 통과
- MemorySection exactness rendering test 통과
- frontend typecheck 통과
- `npm run health` 통과
- bkit analyze match rate 90% 이상

## 7. Rollback

exactness type과 UI badge를 기존 `estimated` 중심 표시로 되돌린다. collector 계산 자체는 변경하지 않는다.
