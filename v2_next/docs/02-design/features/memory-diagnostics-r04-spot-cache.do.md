# Memory Diagnostics R04 SPOT Cache Do Checklist

## 1. Rule

- [ ] `memory-diagnostics-r03-csv-logger-runtime` Report 완료를 확인한다.
- [ ] 완료 전에는 `memory-diagnostics-r05-budget-severity`를 구현하지 않는다.

## 2. Implementation

- [ ] `spot_api.py`에 `get_image_cache_memory_summary()`를 추가한다.
- [ ] static image bytes를 계산한다.
- [ ] live image bytes를 계산한다.
- [ ] image age를 계산한다.
- [ ] live image age를 계산한다.
- [ ] image failure count를 포함한다.
- [ ] live image failure count를 포함한다.
- [ ] retry/backoff timestamp를 포함한다.
- [ ] raw live image URL 원문을 반환하지 않는다.
- [ ] `spot.image_cache` collector를 추가한다.
- [ ] `spot.live_cache` collector를 추가한다.
- [ ] 기존 `spot.cache` compatibility 정책을 명시한다.

## 3. Tests

- [ ] static image bytes test를 추가한다.
- [ ] live image bytes test를 추가한다.
- [ ] retry/failure fields test를 추가한다.
- [ ] raw live URL non-exposure test를 추가한다.

## 4. Validation

- [ ] targeted SPOT cache tests를 실행한다.
- [ ] `npm run health`를 실행한다.
- [ ] `git diff --check`를 실행한다.

## 5. PDCA Close Gate

- [ ] analysis 문서를 작성한다.
- [ ] bkit analyze match rate가 90% 이상이다.
- [ ] iterate 필요 시 재분석한다.
- [ ] report 문서를 작성한다.
- [ ] 다음 feature 시작 가능 상태로 status를 갱신한다.
