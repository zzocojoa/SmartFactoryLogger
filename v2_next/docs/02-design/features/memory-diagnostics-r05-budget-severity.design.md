# Memory Diagnostics R05 Budget Severity Design

## 1. Summary

`memory-diagnostics-r05-budget-severity`는 collector별 budget을 적용해 위험도를 계산한다. 운영자는 큰 항목뿐 아니라 위험한 항목을 먼저 봐야 한다.

## 2. Files

- `backend/Observability/memory_service.py`
- `frontend/src/shared/types.ts`
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`
- backend budget tests
- frontend MemorySection tests

## 3. Budget Table

초기 default budget은 backend에 둔다.

```python
DEFAULT_MEMORY_BUDGETS = {
    "facility.plc_history": {
        "warn_bytes": 150 * 1024 * 1024,
        "critical_bytes": 300 * 1024 * 1024,
        "warn_growth_per_min": 32 * 1024 * 1024,
    },
    "facility.csv_logger": {
        "warn_items_ratio": 0.70,
        "critical_items_ratio": 0.90,
        "warn_growth_per_min": 16 * 1024 * 1024,
    },
    "spot.live_cache": {
        "warn_bytes": 10 * 1024 * 1024,
        "critical_bytes": 50 * 1024 * 1024,
    },
}
```

## 4. Backend Design

Normalize 후 `_apply_budget(item, previous)`를 호출한다. Output fields:

```text
severity: ok | warn | critical
severity_reasons: string[]
budget: object | null
```

Size threshold가 critical이면 critical, warn이면 warn이다. queue ratio threshold는 `items`와 capacity metadata를 활용한다.

## 5. Frontend Design

MemorySection table은 severity column을 추가한다. 기본 정렬은 다음 순서다.

```text
critical > warn > ok
delta_bytes desc
bytes desc
```

## 6. Tests

- warn bytes threshold
- critical bytes threshold
- CSV queue ratio threshold
- severity-first sort order

## 7. Analyze Evidence

bkit analyze는 budget table, `_apply_budget`, collector item fields, UI severity sorting을 확인해야 한다.

