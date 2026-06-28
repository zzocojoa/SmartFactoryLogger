# Memory Diagnostics R07 GC Snapshot Do Checklist

## 1. Rule

- [ ] `memory-diagnostics-r06-leak-slope` Report 완료를 확인한다.
- [ ] 완료 전에는 `memory-diagnostics-r08-electron-memory`를 구현하지 않는다.

## 2. Implementation

- [ ] `MemoryService.capture_gc_snapshot()`을 추가한다.
- [ ] before process sample을 캡처한다.
- [ ] `gc.collect(0)`을 호출한다.
- [ ] `gc.collect(1)`을 호출한다.
- [ ] `gc.collect(2)`를 호출한다.
- [ ] GC latency를 측정한다.
- [ ] after process sample을 캡처한다.
- [ ] rss delta를 계산한다.
- [ ] uss delta를 계산한다.
- [ ] private delta를 계산한다.
- [ ] `self._last_gc_snapshot`을 저장한다.
- [ ] `POST /api/memory/gc` endpoint를 추가한다.
- [ ] UI에 GC 비교 버튼을 추가한다.
- [ ] UI에 GC 결과 panel을 추가한다.
- [ ] export inclusion 준비를 남긴다.

## 3. Tests

- [ ] GC snapshot before/after/delta test를 추가한다.
- [ ] endpoint failure handling test를 추가한다.
- [ ] UI GC delta rendering test를 추가한다.
- [ ] sampler no-auto-GC guard test를 추가한다.

## 4. Validation

- [ ] targeted GC tests를 실행한다.
- [ ] frontend tests를 실행한다.
- [ ] `npm run health`를 실행한다.
- [ ] `git diff --check`를 실행한다.
- [ ] UI smoke 또는 equivalent evidence를 남긴다.

## 5. PDCA Close Gate

- [ ] analysis 문서를 작성한다.
- [ ] bkit analyze match rate가 90% 이상이다.
- [ ] iterate 필요 시 재분석한다.
- [ ] report 문서를 작성한다.
- [ ] 다음 feature 시작 가능 상태로 status를 갱신한다.
