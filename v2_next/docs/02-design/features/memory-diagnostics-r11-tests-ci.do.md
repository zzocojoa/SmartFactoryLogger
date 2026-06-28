# Memory Diagnostics R11 Tests CI Do Checklist

## 1. Rule

- [ ] `memory-diagnostics-r10-export-v2` Report 완료를 확인한다.
- [ ] 이 feature는 memory diagnostics hardening의 최종 guardrail이다.

## 2. Backend Tests

- [ ] `test_memory_collector_exception_does_not_break_sampler`를 추가하거나 확인한다.
- [ ] `test_memory_collector_latency_is_recorded`를 추가하거나 확인한다.
- [ ] `test_plc_history_collector_estimates_without_holding_lock`를 추가하거나 확인한다.
- [ ] `test_csv_logger_drop_count_increments_on_full_queue`를 추가하거나 확인한다.
- [ ] `test_spot_live_cache_collector_reports_live_bytes`를 추가하거나 확인한다.
- [ ] `test_budget_severity_warn_and_critical`를 추가하거나 확인한다.
- [ ] `test_leak_slope_detects_monotonic_growth`를 추가하거나 확인한다.
- [ ] `test_gc_snapshot_returns_before_after_delta`를 추가하거나 확인한다.
- [ ] `test_profiler_start_stop_idempotent`를 추가하거나 확인한다.
- [ ] `test_export_payload_schema_v2_contains_runtime_and_analysis`를 추가하거나 확인한다.

## 3. Frontend Tests

- [ ] unsupported browser memory unavailable test를 추가하거나 확인한다.
- [ ] storage collector exactness test를 추가하거나 확인한다.
- [ ] severity sorting test를 추가하거나 확인한다.
- [ ] Electron metrics rendering test를 추가하거나 확인한다.
- [ ] leak suspects and GC delta rendering test를 추가하거나 확인한다.

## 4. CI/Health

- [ ] backend tests가 `npm run health` 경로에 포함되는지 확인한다.
- [ ] frontend tests가 `npm run health` 경로에 포함되는지 확인한다.
- [ ] export schema regression 실패 시 health가 실패하는지 확인한다.
- [ ] 별도 우회 test path를 만들지 않는다.

## 5. Validation

- [ ] `npm run health`를 실행한다.
- [ ] targeted backend memory suite를 실행한다.
- [ ] targeted frontend memory tests를 실행한다.
- [ ] `git diff --check`를 실행한다.
- [ ] 최종 gstack review를 실행한다.

## 6. PDCA Close Gate

- [ ] analysis 문서를 작성한다.
- [ ] bkit analyze match rate가 90% 이상이다.
- [ ] gap iterate를 완료한다.
- [ ] report 문서를 작성한다.
- [ ] `memory-diagnostics-hardening` 상위 로드맵의 최종 report 준비 상태를 갱신한다.
