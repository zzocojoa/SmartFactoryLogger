# Memory Diagnostics R04 SPOT Cache Design

## 1. Summary

`memory-diagnostics-r04-spot-cache`는 SPOT static image cache와 live image cache를 분리한다. `app.py`가 private cache dict를 직접 읽는 구조를 줄이고, `spot_api.py`의 public summary function을 사용한다.

## 2. Files

- `backend/FacilityData/drivers/spot_api.py`
- `backend/app.py`
- backend SPOT cache tests

## 3. Public Summary API

`spot_api.py`에 다음 함수를 추가한다.

```python
def get_image_cache_memory_summary() -> dict[str, Any]:
    ...
```

Required fields:

- `image_bytes`
- `image_age_sec`
- `image_cache_state`
- `image_failure_count`
- `image_next_retry_at`
- `live_image_bytes`
- `live_image_age_sec`
- `live_image_url_present`
- `live_image_failure_count`
- `live_image_next_retry_at`
- `total_bytes`

## 4. Security Design

`live_image_url` 원문은 반환하지 않는다. 필요한 경우 boolean `live_image_url_present` 또는 redacted host만 사용한다. Export에도 raw URL을 저장하지 않는다.

## 5. Collector Design

`backend/app.py`에 두 collector를 추가한다.

```text
spot.image_cache
spot.live_cache
```

Both use `exactness="exact"`. `spot.cache`는 compatibility alias로 유지할지 제거할지 PR에서 명시한다.

## 6. Tests

- image cache bytes are exact
- live cache bytes are exact
- retry/failure fields are present
- raw live URL is not exposed

## 7. Analyze Evidence

bkit analyze는 public summary function, app collector split, private dict 접근 제거 또는 축소, raw URL 미노출을 확인해야 한다.
