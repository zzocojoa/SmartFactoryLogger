# Memory Diagnostics R01 Collector Contract Design

## 1. Summary

`memory-diagnostics-r01-collector-contract`는 MemoryService collector 실행 결과의 공통 계약을 확장한다. 목표는 collector 실패와 지연을 sampler 전체 장애로 확산시키지 않고, 운영자가 느린 진단 로직 자체를 확인할 수 있게 하는 것이다.

## 2. Files

- `backend/Observability/memory_service.py`
- `frontend/src/shared/types.ts`
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`
- backend MemoryService tests
- frontend MemorySection tests

## 3. Backend Contract

Collector item은 기존 `name`, `kind`, `bytes`, `items`, `note`, `exactness`를 유지하고 다음 필드를 optional additive로 추가한다.

```text
latency_ms: number | null
status: ok | slow | error | stale
last_ok_at: ISO timestamp | null
last_error_at: ISO timestamp | null
error_count: number
stale: boolean
source: backend
```

`MemoryService`에는 다음 runtime state를 둔다.

```python
self._collector_runtime_state: dict[str, dict[str, Any]] = {}
self._collector_latency_warn_ms = 250.0
self._collector_stale_after_sec = 60.0
```

Per collector runtime state includes `last_ok_at`, `last_error_at`, `error_count`, `last_latency_ms`, `last_status`, `last_value`, and `last_value_at`.

## 4. Execution Design

- `_run_collectors()`에서 collector 호출 전후 `time.perf_counter()`로 latency를 측정한다.
- 정상 collector는 `status=ok` 또는 `status=slow`로 normalize한다.
- 실패 collector는 `status=error` item으로 격리한다.
- 이전 성공 시간이 stale threshold를 넘으면 `stale=true`를 표시한다.
- slow collector는 thread hard timeout으로 중단하지 않는다. `last_value`를 저장하고, 다음 sample에서 previous cache가 stale threshold 안에 있으면 cache reuse item을 반환할 수 있다.
- cache reuse item은 `status=stale` 또는 note/source metadata로 새 collector 실행 결과와 구분한다.
- hard timeout은 구현하지 않는다. Python thread 강제 중단은 운영 안정성보다 위험하다.

## 5. Frontend Design

- shared type은 새 필드를 optional로 받는다.
- MemorySection은 latency, status, stale을 작은 badge 또는 column으로 표시한다.
- 구버전 backend payload에는 field가 없을 수 있으므로 fallback 표시를 사용한다.

## 6. Tests

- collector exception does not break sampler
- latency is recorded
- slow threshold sets status
- stale state is exposed
- previous cache reuse is covered
- old payload renders without crash

## 7. Analyze Evidence

bkit analyze는 `backend/Observability/memory_service.py`의 runtime state, normalize result, `_run_collectors()` 변경과 MemorySection의 optional rendering을 확인해야 한다.
