# Memory Diagnostics R07 GC Snapshot Design

## 1. Summary

`memory-diagnostics-r07-gc-snapshot`는 수동 GC 전후 process memory 비교를 제공한다. 자동 sampler path에는 GC 호출을 넣지 않는다.

## 2. Files

- `backend/Observability/memory_service.py`
- `backend/app.py`
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`
- frontend memory API hook files
- backend and frontend tests

## 3. Backend Design

`MemoryService.capture_gc_snapshot()`를 추가한다.

Returned fields:

- `captured_at`
- `latency_ms`
- `collected`
- `before`
- `after`
- `delta`

`delta`는 `rss_bytes`, `uss_bytes`, `private_bytes`를 포함한다. nullable value는 safe delta helper로 처리한다.

## 4. API Design

`backend/app.py`에 endpoint 추가:

```text
POST /api/memory/gc
```

실패 시 error log를 남기고 HTTP 500을 반환한다.

## 5. Frontend Design

Profiler controls 근처에 GC 비교 버튼을 추가한다. 실행 중 loading state와 latest result panel을 둔다. UI는 delta가 음수, 0, 양수일 때 모두 읽히도록 표시한다.

## 6. Tests

- GC snapshot returns before/after/delta
- endpoint failure returns 500
- UI renders delta and latency
- sampler does not call GC automatically

## 7. Analyze Evidence

bkit analyze는 manual endpoint, service method, `self._last_gc_snapshot`, UI button/result, export inclusion 준비를 확인해야 한다.
