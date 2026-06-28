# Implementation Report: memory-diagnostics-hardening

> Date: 2026-06-28 | Child Ranks Completed: 11/11

## Summary
The memory diagnostics hardening roadmap completed all ranked child features from R01 through R11. The result is a bounded, read-only diagnostics surface covering backend collectors, PLC history, CSV logger runtime, SPOT cache split, severity budgets, leak-slope suspicion, manual GC snapshots, Electron process memory, frontend exactness, export v2 redaction, and health/CI regression guardrails.

## Engineering Assessment
- Risk level: Medium overall because diagnostics export and operational memory signals can expose sensitive runtime context if mishandled.
- Main trade-off: The diagnostics payloads are richer and larger, but existing export fields remain additive for compatibility.
- Compatibility impact: Additive API/UI changes; legacy export summary/details fields are retained.
- Security implications: Export v2 applies recursive key-based redaction and sanitizes runtime argv. Electron preload exposes only the constrained memory bridge.
- Rollback path: Revert the memory diagnostics feature set by rank, starting with export/UI changes, while leaving independent tests as evidence until rollback is complete.
- Observability impact: Operators can inspect collector status/latency, memory severity, leak suspects, GC deltas, frontend exactness, and Electron process memory from the existing memory UI/export path.
- Migration risk: Low. No database migration or persistent data format migration is required.
- Operational failure mode: Diagnostics are local snapshots and heuristics; they identify leak suspects, not confirmed leak root causes.

## Completed Child Features
- R01 `memory-diagnostics-r01-collector-contract`: collector runtime contract and soft safety metadata.
- R02 `memory-diagnostics-r02-plc-history`: bounded PLC history memory summary collector.
- R03 `memory-diagnostics-r03-csv-logger-runtime`: CSV logger runtime/drop/lag memory collector.
- R04 `memory-diagnostics-r04-spot-cache`: SPOT image/live cache split with URL-safe summaries.
- R05 `memory-diagnostics-r05-budget-severity`: memory budget and severity model.
- R06 `memory-diagnostics-r06-leak-slope`: slope-based leak suspect detection.
- R07 `memory-diagnostics-r07-gc-snapshot`: manual GC before/after snapshot endpoint and UI.
- R08 `memory-diagnostics-r08-electron-memory`: constrained Electron memory bridge and UI display.
- R09 `memory-diagnostics-r09-frontend-exactness`: frontend exactness classification and alert confidence.
- R10 `memory-diagnostics-r10-export-v2`: forensic export v2 schema with recursive redaction.
- R11 `memory-diagnostics-r11-tests-ci`: health/CI guardrails for memory diagnostics regressions.

## PR Inclusion Policy
- Decision: keep PDCA roadmap, analysis, report, and `.pdca-status.json` changes in a separate docs PR from `codex/memory-diagnostics-pdca-docs`.
- Merge gate: the docs PR must merge only after `codex/memory-diagnostics-backend-core` and `codex/memory-diagnostics-frontend-ui` are merged, or this report and `.pdca-status.json` must be revised to match any changed code PR scope.
- Code PR scope: `codex/memory-diagnostics-backend-core` owns backend collectors, API contracts, Electron main/preload packaging, and backend tests. `codex/memory-diagnostics-frontend-ui` owns renderer types, UI, view model, settings controls, and frontend tests.
- Docs PR scope: all memory diagnostics PDCA documents stay together because the child reports summarize cross-branch evidence and the roadmap completion status depends on both code PRs.

| Rank | Code branch evidence | Merge dependency |
| --- | --- | --- |
| R01 collector contract | `codex/memory-diagnostics-backend-core` | backend core PR |
| R02 PLC history | `codex/memory-diagnostics-backend-core` | backend core PR |
| R03 CSV logger runtime | `codex/memory-diagnostics-backend-core` | backend core PR |
| R04 SPOT cache | `codex/memory-diagnostics-backend-core` | backend core PR |
| R05 budget severity | `codex/memory-diagnostics-backend-core`, `codex/memory-diagnostics-frontend-ui` | both code PRs |
| R06 leak slope | `codex/memory-diagnostics-backend-core`, `codex/memory-diagnostics-frontend-ui` | both code PRs |
| R07 GC snapshot | `codex/memory-diagnostics-backend-core`, `codex/memory-diagnostics-frontend-ui` | both code PRs |
| R08 Electron memory | `codex/memory-diagnostics-backend-core`, `codex/memory-diagnostics-frontend-ui` | both code PRs |
| R09 frontend exactness | `codex/memory-diagnostics-frontend-ui` | frontend UI PR |
| R10 export v2 | `codex/memory-diagnostics-backend-core`, `codex/memory-diagnostics-frontend-ui` | both code PRs |
| R11 tests and CI | `codex/memory-diagnostics-backend-core`, `codex/memory-diagnostics-frontend-ui` | both code PRs |

## PDCA Status Reader Contract
- `.pdca-status.json` intentionally does not define a root-level `currentPhase`.
- Automation must read `features[primaryFeature].phase` for the canonical primary feature phase.
- Automation must read `features[featureName].phase` for per-feature status.
- `pipeline.currentPhase` is a session cursor and must not override `features.*.phase`.
- `recovery.currentPhase` is optional future recovery metadata; readers may use it only when a recovery block exists.

## Validation
- R10 targeted backend export tests: passed, 27 tests.
- R10 sanitized export smoke: passed, no raw password/live image URL remained in JSON output.
- R11 targeted backend memory suite: passed, 31 tests.
- R11 targeted frontend memory tests: passed, 2 files and 12 tests.
- Final `npm run health`: passed, including frontend typecheck/lint/tests and backend ruff/mypy/tests.
- Final `git diff --check`: passed with CRLF conversion warnings only.
- PR inclusion audit: docs-only branch `codex/memory-diagnostics-pdca-docs` now records the code branch mapping and merge gate for `.pdca-status.json` and child report consistency.
- PDCA status reader audit: automation guidance now documents that root-level `currentPhase` is not part of the schema and readers must use `features.*.phase`, with `pipeline.currentPhase` as cursor-only metadata.

## Production Evidence Gap
Local automated validation is complete. Long-running production soak evidence on the real workstation is still needed to confirm alert thresholds, leak-slope signal quality, and operator usefulness under live workload.

## Next Action
Merge the backend core and frontend UI code PRs first, then merge this docs PR after confirming the rank-to-branch mapping above still matches the final PR diffs. After docs merge, run a production soak with export capture before and after an operating shift.
