# Memory Diagnostics R05 Budget Severity Do Checklist

## 1. Rule

- [ ] `memory-diagnostics-r04-spot-cache` Report 완료를 확인한다.
- [ ] 완료 전에는 `memory-diagnostics-r06-leak-slope`를 구현하지 않는다.

## 2. Implementation

- [ ] `DEFAULT_MEMORY_BUDGETS`를 추가한다.
- [ ] `facility.plc_history` bytes threshold를 추가한다.
- [ ] `facility.csv_logger` queue ratio threshold를 추가한다.
- [ ] `spot.live_cache` bytes threshold를 추가한다.
- [ ] `_apply_budget()`를 추가한다.
- [ ] collector item에 `severity`를 추가한다.
- [ ] collector item에 `severity_reasons`를 추가한다.
- [ ] collector item에 `budget` metadata를 추가한다.
- [ ] frontend shared type을 확장한다.
- [ ] MemorySection에 severity column을 추가한다.
- [ ] table 기본 정렬을 severity, delta, bytes 순서로 변경한다.

## 3. Tests

- [ ] warn bytes threshold test를 추가한다.
- [ ] critical bytes threshold test를 추가한다.
- [ ] CSV queue ratio severity test를 추가한다.
- [ ] frontend severity sort test를 추가한다.

## 4. Validation

- [ ] targeted budget tests를 실행한다.
- [ ] frontend MemorySection tests를 실행한다.
- [ ] `npm run health`를 실행한다.
- [ ] `git diff --check`를 실행한다.
- [ ] UI smoke 또는 equivalent screenshot evidence를 남긴다.

## 5. PDCA Close Gate

- [ ] analysis 문서를 작성한다.
- [ ] bkit analyze match rate가 90% 이상이다.
- [ ] gap iterate를 완료한다.
- [ ] report 문서를 작성한다.
- [ ] 다음 feature 시작 가능 상태로 status를 갱신한다.
