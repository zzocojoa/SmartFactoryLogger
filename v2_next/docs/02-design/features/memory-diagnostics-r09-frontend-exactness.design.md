# Memory Diagnostics R09 Frontend Exactness Design

## 1. Summary

`memory-diagnostics-r09-frontend-exactness`는 frontend memory collector의 신뢰도를 명시한다. observed, estimated-enumerated, estimated, unavailable을 구분한다.

## 2. Files

- `frontend/src/shared/types.ts`
- `frontend/src/domains/Observability/hooks/useMemoryViewModel.ts`
- `frontend/src/domains/Configuration/components/SettingsModal/MemorySection.tsx`
- frontend tests

## 3. Type Design

```ts
export type MemoryExactness =
  | 'exact'
  | 'observed'
  | 'estimated'
  | 'estimated-enumerated'
  | 'unavailable';
```

`MemoryCollectorItem.exactness`는 이 type을 사용한다.

## 4. Collector Design

- `measureUserAgentSpecificMemory()` result: `observed`
- `performance.memory` result: `observed`
- localStorage/sessionStorage enumeration: `estimated-enumerated`
- series/app buffer heuristic: `estimated`
- unsupported browser memory: `unavailable`

## 5. Alert Design

low-confidence estimated 항목은 alert reason에서 신뢰도 한계를 표시한다. severity 자체를 과장하지 않는다.

Alert severity confidence weighting prioritizes `observed` measurements. `estimated` and `unavailable` values must be labeled or down-weighted so they do not look as reliable as observed heap measurements.

## 6. Tests

- unsupported browser memory is unavailable
- storage collectors are estimated-enumerated
- heuristic collectors remain estimated
- UI exactness badge renders all values

## 7. Analyze Evidence

bkit analyze는 type definition, buildCollector signature, collector별 exactness assignment, UI exactness rendering을 확인해야 한다.
