# Memory Diagnostics R09 Frontend Exactness Do Checklist

## 1. Rule

- [ ] `memory-diagnostics-r08-electron-memory` Report 완료를 확인한다.
- [ ] 완료 전에는 `memory-diagnostics-r10-export-v2`를 구현하지 않는다.

## 2. Implementation

- [ ] `MemoryExactness` type을 추가한다.
- [ ] `MemoryCollectorItem.exactness`를 확장한다.
- [ ] `buildCollector()` signature에 exactness 인자를 추가한다.
- [ ] UASM browser memory를 `observed`로 표시한다.
- [ ] `performance.memory` fallback을 `observed`로 표시한다.
- [ ] unsupported browser memory를 `unavailable`로 표시한다.
- [ ] localStorage collector를 `estimated-enumerated`로 표시한다.
- [ ] sessionStorage collector를 `estimated-enumerated`로 표시한다.
- [ ] series buffer heuristic을 `estimated`로 유지한다.
- [ ] UI exactness badge를 개선한다.
- [ ] alert reason에 low-confidence estimate를 구분한다.

- [ ] alert severity calculation does not treat `observed` and `estimated`/`unavailable` as the same confidence.

## 3. Tests

- [ ] unsupported mode unavailable test를 추가한다.
- [ ] storage collectors exactness test를 추가한다.
- [ ] heuristic collectors exactness test를 추가한다.
- [ ] exactness badge rendering test를 추가한다.

## 4. Validation

- [ ] frontend tests를 실행한다.
- [ ] frontend typecheck를 실행한다.
- [ ] `npm run health`를 실행한다.
- [ ] `git diff --check`를 실행한다.

## 5. PDCA Close Gate

- [ ] analysis 문서를 작성한다.
- [ ] bkit analyze match rate가 90% 이상이다.
- [ ] gap iterate를 완료한다.
- [ ] report 문서를 작성한다.
- [ ] 다음 feature 시작 가능 상태로 status를 갱신한다.
