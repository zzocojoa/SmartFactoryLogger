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

## Production Soak Evidence
Local automated validation is complete. A comparison-ready pre/post memory evidence pass was recorded on 2026-06-28 without committing raw exports. The pre-shift artifact is an existing sanitized bundle. The post-shift artifact was generated with the same backend export builder used by `POST /api/memory/export` after user approval because the live backend API was not listening on `127.0.0.1:8000` during capture. Treat this pass as workstation post-shift evidence, not as proof that the live API path was exercised.

Artifact identity:

| Capture | Artifact | Timestamp | Size | SHA-256 |
| --- | --- | --- | ---: | --- |
| Pre-shift baseline | `sfl-memory-precheck-idle-baseline-20260628.sanitized.zip` | generated `2026-06-27T15:31:50+00:00`, mtime `2026-06-27T15:37:13.1116276Z` | 85,771 bytes | `5754b07957902d2bb9639c9a90fb9f0718b397f5d714b2f44b87fb20f0c5002c` |
| Post-shift capture | `memory_snapshot_20260628_170059.json` | generated `2026-06-28T08:00:59+00:00`, mtime `2026-06-28T08:00:59.8835050Z` | 66,404 bytes | `8fc62c81119019df586e265e5e2d19a7a3a7a03b8712eb53b83c9398cf0f6240` |

Redaction and scrub checks:

| Capture | Result |
| --- | --- |
| Pre-shift baseline | 18 zip entries, 10 JSON entries, 0 parse failures with UTF-8 BOM handling, 0 credential assignments, 0 unredacted credential assignments, 0 raw Windows path literals. The sanitized bundle still contains 11 raw URL literals in text/log entries, so the raw bundle stays outside Git and this report records only scrubbed metadata. |
| Post-shift capture | Export v2 redaction flag applied, 0 credential assignments, 0 unredacted credential assignments, 0 raw URL literals, 0 raw Windows path literals. |

Memory comparison:

| Metric | Pre-shift | Post-shift | Delta |
| --- | ---: | ---: | ---: |
| RSS | 277.70 MiB | 306.65 MiB | +28.95 MiB |
| Private bytes | 239.33 MiB | 295.12 MiB | +55.79 MiB |
| USS | 225.02 MiB | 293.08 MiB | +68.06 MiB |
| VMS | 239.33 MiB | 295.12 MiB | +55.79 MiB |
| Backend top consumers | 6 | 9 | +3 |
| Backend growth entries | 6 | 9 | +3 |
| Leak suspects | not available in baseline bundle | 0 | n/a |
| Collector runtime entries | not available in baseline bundle | 9 | n/a |

Operational interpretation:
- The committed evidence contains only artifact hashes, sizes, timestamps, redaction counts, and aggregate memory metrics.
- The post-shift capture reported no leak suspects and had 9 collector runtime entries.
- The pre-shift bundle predates some export v2 analysis fields, so leak suspect and collector runtime comparison is post-only for this evidence pass.
- For a stronger production gate, repeat the post-shift capture through the live Electron/FastAPI API while the operating app is running.

## Next Action
Use this hash-bound evidence as the first scrubbed production soak record. Replace it with a live API capture if the release gate requires proof that the packaged Electron/FastAPI path performed the export during an operating shift.
