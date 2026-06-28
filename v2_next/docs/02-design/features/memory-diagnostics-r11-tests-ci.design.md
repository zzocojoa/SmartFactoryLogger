# Memory Diagnostics R11 Tests CI Design

## 1. Summary

`memory-diagnostics-r11-tests-ci`는 앞선 10개 순위의 회귀 방지 장치다. memory diagnostics는 장애 대응 기능이므로 테스트가 health script에 포함되어야 한다.

## 2. Files

- backend unittest locations
- frontend test locations
- `package.json` only if script wiring is missing
- memory diagnostics report docs

## 3. Backend Test Matrix

Required tests:

- `test_memory_collector_exception_does_not_break_sampler`
- `test_memory_collector_latency_is_recorded`
- `test_plc_history_collector_estimates_without_holding_lock`
- `test_csv_logger_drop_count_increments_on_full_queue`
- `test_spot_live_cache_collector_reports_live_bytes`
- `test_budget_severity_warn_and_critical`
- `test_leak_slope_detects_monotonic_growth`
- `test_gc_snapshot_returns_before_after_delta`
- `test_profiler_start_stop_idempotent`
- `test_export_payload_schema_v2_contains_runtime_and_analysis`

## 4. Frontend Test Matrix

Required tests:

- unsupported browser memory is unavailable
- storage collector exactness is estimated-enumerated
- critical severity sorts before size
- Electron process metrics render when present
- leak suspects and GC delta render

## 5. CI Design

Existing `npm run health` must execute all relevant backend and frontend tests. Do not add a parallel test path that CI can skip silently.

## 6. Evidence Design

Final report must record:

- health result
- targeted test result
- export v2 redaction result
- production evidence still missing, if any

## 7. Analyze Evidence

bkit analyze는 tests existence, package script coverage, schema regression behavior, final report readiness를 확인해야 한다.

