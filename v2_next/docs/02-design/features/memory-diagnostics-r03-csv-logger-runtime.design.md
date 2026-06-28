# Memory Diagnostics R03 CSV Logger Runtime Design

## 1. Summary

`memory-diagnostics-r03-csv-logger-runtime`는 CSV logger queue backlog, drop, writer lag를 메모리 진단 항목으로 만든다. 기존 `facility.csv_logger` collector는 유지하되 bytes 계산을 queue backlog 중심으로 개선한다.

## 2. Files

- `backend/FacilityData/repository.py`
- `backend/app.py`
- backend CSVLoggerService tests

## 3. Runtime Fields

`CSVLoggerService.__init__()`에 다음 필드를 추가한다.

```python
self._drop_count = 0
self._last_drop_at: float | None = None
self._last_enqueue_at: float | None = None
self._last_write_at: float | None = None
self._payload_bytes_ema: float | None = None
self._runtime_lock = threading.Lock()
```

## 4. Enqueue Design

- `enqueue()` 진입 시 `time.time()`을 기록한다.
- `_estimate_factory_data_bytes(data)`는 `len(data.model_dump_json()) * 2`를 우선 사용한다.
- estimate 실패 시 1024 bytes fallback을 사용한다.
- queue full이면 drop count와 last drop timestamp를 lock 안에서 갱신한다.

## 5. Writer Design

writer loop에서 batch flush가 끝난 시점에 `_last_write_at`을 갱신한다. `get_runtime_state()`는 queue size, maxsize, ratio, estimated queue bytes, writer lag를 반환한다.

## 6. Collector Design

`get_runtime_state()` must expose these exact field names so `backend/app.py` and tests do not drift:

```text
queue_size
queue_maxsize
queue_ratio
drop_count
last_drop_at
last_enqueue_at
last_write_at
writer_lag_sec
payload_bytes_ema
estimated_queue_bytes
```

`_collect_csv_logger()`는 `estimated_queue_bytes + mapping overhead`를 bytes로 사용한다. Note format:

```text
queue=<size>/<max> drop=<count> lag=<seconds>s
```

## 7. Tests

- full queue increments drop count
- payload bytes EMA is updated on enqueue
- writer lag is null before first write
- estimated queue bytes scales with queue size

## 8. Analyze Evidence

bkit analyze는 runtime counters, enqueue/drop path, writer timestamp update, `get_runtime_state()` fields, collector note/bytes calculation을 확인해야 한다.
