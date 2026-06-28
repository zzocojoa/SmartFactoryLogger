# Memory Diagnostics R04 SPOT Cache Plan

## 1. Summary

- Feature: `memory-diagnostics-r04-spot-cache`
- Parent roadmap: `memory-diagnostics-hardening`
- Rank: 4
- Dependency: `memory-diagnostics-r03-csv-logger-runtime` Report 완료

## 2. Business Goal

SPOT 일반 image cache와 live frame cache를 분리해 어느 쪽이 메모리를 차지하는지 확인한다. 현재 `spot.cache`는 `_img_cache["data"]`만 직접 보므로 live image 원인을 놓칠 수 있다.

## 3. Scope

- `spot_api.py`에 public `get_image_cache_memory_summary()` 추가
- static image cache와 live image cache bytes 분리
- failure count, retry/backoff state 요약
- `spot.image_cache`, `spot.live_cache` collector 등록
- private cache dict 직접 접근 축소

## 4. Out Of Scope

- SPOT image fetch 정책 변경
- retry/backoff 알고리즘 변경
- live image URL 원문 export
- 이미지 압축 또는 cache eviction 구현

## 5. Acceptance Criteria

- `spot.image_cache`와 `spot.live_cache`가 별도 collector로 노출된다.
- static image bytes와 live image bytes가 exact 값으로 표시된다.
- live URL 원문은 UI/export에 저장하지 않는다.
- failure/retry 상태가 note 또는 detail field로 확인된다.

## 6. Validation Gate

- SPOT static/live cache unit test 통과
- raw live URL 미노출 테스트 통과
- `npm run health` 통과
- bkit analyze match rate 90% 이상

## 7. Rollback

새 collector 등록을 제거하고 기존 `spot.cache` collector로 되돌린다. SPOT 제어 동작과 image fetch 경로는 변경하지 않는다.

