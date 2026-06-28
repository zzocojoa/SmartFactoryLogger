# Memory Diagnostics R02 PLC History Design

## 1. Summary

`memory-diagnostics-r02-plc-history`는 `PLCService.history` deque의 resident memory를 bounded sampling으로 추정한다. lock 경합을 줄이기 위해 lock 안에서는 sample copy만 수행하고, size estimate는 lock 밖에서 실행한다.

## 2. Files

- `backend/FacilityData/service.py`
- `backend/app.py`
- backend PLCService tests
- backend memory collector registration tests

## 3. Service API

`PLCService`에 public method를 추가한다.

```python
def get_history_memory_summary(self, sample_size: int = 128) -> dict[str, Any]:
    ...
```

Returned fields:

- `count`
- `max_samples`
- `oldest_timestamp_ms`
- `newest_timestamp_ms`
- `sample_size`
- `sampled_bytes`
- `estimated_bytes`
- `avg_bytes_per_sample`
- `fill_ratio`

## 4. Locking Design

- `history_lock` 안에서 `count`, `max_samples`, bounds, bounded sample list를 만든다.
- `estimate_size_bytes(sample_items)`는 lock 밖에서 실행한다.
- `sample_size`가 count보다 크면 전체 history를 복사한다.
- count가 크면 `count // sample_size` step으로 최대 sample_size만 복사한다.

## 5. Collector Design

`backend/app.py`에 `_collect_plc_history()`를 추가하고 `_register_memory_collectors()`에서 등록한다.

Collector name:

```text
facility.plc_history
```

Collector kind:

```text
deque
```

Note는 count, max, fill ratio, average bytes per sample을 포함한다.

## 6. Tests

- summary estimates bytes from bounded sample
- empty history returns zero-safe fields
- estimate_size_bytes is not called while lock is held
- collector registration includes `facility.plc_history`

## 7. Analyze Evidence

bkit analyze는 service method 존재, lock 밖 size estimate, app collector 등록, note/detail field를 확인해야 한다.

