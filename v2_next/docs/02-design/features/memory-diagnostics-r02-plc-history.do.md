# Memory Diagnostics R02 PLC History Do Checklist

## 1. Rule

- [x] `memory-diagnostics-r01-collector-contract` Report completion confirmed.
- [x] No r03 implementation was included in this feature.

## 2. Implementation

- [x] Added `PLCService.get_history_memory_summary(sample_size=128)`.
- [x] Read history count while holding `history_lock`.
- [x] Read max samples while holding `history_lock`.
- [x] Read oldest/newest timestamp while holding `history_lock`.
- [x] Copied only a bounded sample list while holding `history_lock`.
- [x] Ran `estimate_size_bytes()` outside `history_lock`.
- [x] Calculated `sampled_bytes`.
- [x] Calculated `estimated_bytes`.
- [x] Calculated `avg_bytes_per_sample`.
- [x] Calculated `fill_ratio`.
- [x] Implemented empty history zero-safe response.
- [x] Added `_collect_plc_history()` in `backend/app.py`.
- [x] Registered `facility.plc_history` in `_register_memory_collectors()`.
- [x] Included count, max, fill ratio, and average bytes in collector note.

## 3. Tests

- [x] Added summary count/estimated bytes test.
- [x] Added empty history test.
- [x] Added lock-outside size estimate test.
- [x] Added collector registration test.

## 4. Validation

- [x] Ran targeted PLC/history tests: `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_data_history_api`.
- [x] Ran memory service regression tests: `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_memory_service`.
- [x] Ran `npm run health`.
- [x] Ran `git diff --check`.

## 5. PDCA Close Gate

- [x] Wrote `docs/03-analysis/memory-diagnostics-r02-plc-history.analysis.md`.
- [x] bkit analyze match rate is 100%.
- [x] No iterate pass required.
- [x] Wrote `docs/04-report/memory-diagnostics-r02-plc-history.report.md`.
- [x] Status is ready to move to `memory-diagnostics-r03-csv-logger-runtime`.

