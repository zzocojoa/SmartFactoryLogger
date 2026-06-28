# Completion Report: memory-diagnostics-r02-plc-history

## Summary

- Feature: `memory-diagnostics-r02-plc-history`
- Parent roadmap: `memory-diagnostics-hardening`
- Rank: 2
- Status: completed
- Match rate: 100%

R02 adds direct memory diagnostics for `PLCService.history`, the highest-probability resident buffer in the backend. The collector is bounded, read-only, and designed not to hold `history_lock` while estimating object size.

## Completed Items

- Added `PLCService.get_history_memory_summary(sample_size=128)`.
- Added bounded sample copy from `self.history`.
- Kept `estimate_size_bytes()` outside `history_lock`.
- Added zero-safe empty history handling.
- Added `_collect_plc_history()` in `backend/app.py`.
- Registered `facility.plc_history`.
- Added tests for summary estimation, empty history, lock behavior, and collector registration.

## Quality Metrics

- bkit match rate: 100%
- Targeted backend history tests: passed
- MemoryService regression tests: passed
- `npm run health`: passed
- `git diff --check`: passed with line-ending warnings only

## Operational Notes

- Rollback path: unregister `facility.plc_history` and remove `get_history_memory_summary()`.
- Migration risk: none. No DB, CSV, config, or PLC retention policy changes.
- Observability impact: Memory details now show `facility.plc_history` size, item count, fill ratio, and average bytes per sample.
- Failure mode: if the collector fails, R01 collector isolation reports an error item and the sampler continues.
- Production evidence gap: idle/local tests verify behavior, but production-like one-hour history fill still needs evidence before final budget thresholds are tuned.

## Next Step

Start `memory-diagnostics-r03-csv-logger-runtime` and implement CSV logger queue/drop/lag diagnostics only.

