# Memory Diagnostics R06 Leak Slope Design

## 1. Summary

`memory-diagnostics-r06-leak-slope`는 rolling history를 사용해 steady growth를 leak suspect로 분류한다. 이 단계에서는 leak 확정이라는 표현을 금지한다.

## 2. Files

- `backend/Observability/memory_service.py`
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`
- backend trend analysis tests
- frontend leak suspect rendering tests

## 3. Slope Calculation

```python
def _calc_slope_bytes_per_min(points: list[tuple[float, int]]) -> float:
    ...
```

Design rules:

- sample count < 4이면 0 반환
- x축은 첫 timestamp 기준 minutes 단위로 normalize
- 단순 least squares slope 사용
- monotonic ratio는 인접 sample 중 증가한 비율

## 4. Detection Design

Process fields:

- `rss_bytes`
- `uss_bytes`
- `private_bytes`

Collector fields:

- collector name별 `bytes`

Suspect condition:

```text
slope_bytes_per_min >= warn_growth_per_min
monotonic_ratio >= 0.75
latest_bytes >= baseline_bytes * 1.20
```

## 5. API/UI Design

`/api/memory/details`에 `leak_suspects`를 추가한다. UI는 "누수 의심"으로 표시하고 확정 표현은 사용하지 않는다.

## 6. Tests

- monotonic growth detected
- spike not detected
- insufficient sample returns empty result
- UI renders leak suspect

## 7. Analyze Evidence

bkit analyze는 slope helper, trend analysis 호출 위치, `self._latest_leak_suspects`, API field, UI wording을 확인해야 한다.
