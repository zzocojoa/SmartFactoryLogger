# Gap Analysis: electron-startup-progress

> Date: 2026-07-16 | Design: `docs/02-design/features/electron-startup-progress.design.md`

---

## Match Rate: 100%

## Summary

The implementation covers all 15 functional requirements in the approved plan.
The startup overlay paints from local HTML before React, Electron main owns the
state machine and timeout, the backend emits a bounded allowlisted progress
contract, and renderer handoff distinguishes strict Running readiness from an
honest Offline/Error degraded state. No high-priority design gap remains.

## Implemented Items

- [x] Static one-window splash overlay precedes the React module entry.
- [x] Pure coordinator owns status, gates, progress, deadline, and sequence.
- [x] Backend emits only nine allowlisted compact progress stages through a
  per-launch authenticated private file, with stdout as a development fallback.
- [x] Fragmented/coalesced progress parsers have bounded file, line, and buffer limits.
- [x] Normal Running handoff requires health, data snapshot, and RAF paint.
- [x] Timestamped Offline and Error snapshots reach degraded handoff.
- [x] Existing strict `renderer.first-live-data` and operational-ready semantics remain.
- [x] Spawn/close failures and 30-second timeout expose fixed recovery actions.
- [x] Retry is serialized, terminates the owned backend tree, reloads renderer
  one-shots, and starts one replacement backend.
- [x] Manual offline continuation dismisses only the overlay.
- [x] Fixed IPC methods validate active main-frame sender and `file:` origin.
- [x] Overlay uses text-only state rendering, accessibility roles, RAF fade, and
  browser fallback removal.
- [x] Startup transitions log correlated from/to status and phase without raw logs.
- [x] Existing splash image is copied deterministically after Vite build.
- [x] Electron shutdown waits for backend-tree cleanup before completing quit.
- [x] Backend start waits for an observed double-RAF splash paint, with a bounded
  750 ms fallback armed only after the hidden BrowserWindow reaches
  `ready-to-show` and is shown.
- [x] Stateful renderer IPC is bound to the current document generation.
- [x] Retry and quit request an authenticated backend drain before forced
  process-tree cleanup.
- [x] Packaged `console=False` startup receives all nine backend stages without
  depending on stdout.
- [x] Strict first-data-snapshot and first-live-data events are independently
  accepted before ready handoff.
- [x] Shutdown records every backend stage and returns exit code 2 when any
  required drain fails.
- [x] Electron preserves backend exit code/signal and rejects graceful non-zero
  shutdown before application quit or backend retry.
- [x] SPOT drain rejects new writer failures, CSV stop requires a durable final
  flush, and PLC/metrics/memory/config stops expose explicit thread results.
- [x] Parent progress-path/token variables are removed before backend spawn.

## Missing Items

- None.

## Changed Items (Safe Deviations)

- [x] Retry stops the old backend before coordinator reset. This prevents stale
  responses from the previous renderer/backend generation satisfying fresh gates.
- [x] Renderer subscribes before requesting the state snapshot and rejects older
  sequence numbers. This closes the snapshot/subscription race.
- [x] `SmartFactoryElectronBridge` startup methods are optional in TypeScript so
  browser-mode and partial test bridges remain backward compatible; packaged
  preload always exposes the full fixed contract.
- [x] Quit now awaits child-tree termination. This was added after the first
  local smoke exposed an orphaned development backend.
- [x] Review changed Windows shutdown from `tree-kill` first to an authenticated
  HTTP drain first because `tree-kill` maps to forced `taskkill /F` on Windows.
- [x] Review separated informational paint fallback from the authoritative RAF
  gate and commits one-shot keys only after main accepts the IPC event.
- [x] Final review kept the BrowserWindow hidden until `ready-to-show` and moved
  the backend-start fallback behind the visible splash.
- [x] Server evidence showed the SPOT capture worker scanning the complete
  historical fact CSV during shutdown. The writer now snapshots one immutable
  history boundary, skips historical scans for all current-session queued
  captures, preserves restart deduplication, and delays retention traversal off
  the first capture.
- [x] Backend stage budgets are capped at 30 seconds (SPOT) and 300 seconds
  (CSV); Electron waits 365 seconds so default worst-case drains cannot be
  preempted by launcher cleanup.
- [x] The current-session SPOT fact cache is consulted before any filesystem
  heuristic, so deleting a just-written image cannot append a duplicate capture
  ID to `spot_image_fact.csv`.
- [x] The bundled QA functional exit contract remains intentionally separate
  from `performance_status`; the server release wrapper must require both.
- [x] Final race review rejects a non-zero child already in the `exit` state,
  atomically couples SPOT writer outcomes to queue completion, and orders every
  accepted CSV row before the shutdown sentinel.
- [x] A failed v2 batch write retains its rows for final retry; any runtime v2
  buffer loss is latched so a later empty final buffer cannot produce exit 0.

## Validation Evidence

| Check | Result |
|-------|--------|
| Node coordinator/IPC/lifecycle tests | 38 passed |
| Frontend tests | 237 passed across 31 files |
| Backend tests | 511 passed; focused shutdown/SPOT/contract tests PASS |
| Frontend typecheck/lint | PASS |
| Backend ruff/mypy | PASS |
| Frontend production build and splash copy | PASS |
| Electron local smoke | ready-to-show 274.6 ms; first paint 282.0 ms; window shown 299.4 ms; backend trigger 300.5 ms; operational-ready 7,547.9 ms; overlay hidden |
| Server startup | all 9 stages; operational-ready 10,478.3 ms; visual confirmation PASS |
| Server shutdown diagnosis | backend closed in 60,311.4 ms; SPOT drain failure isolated; CSV drain succeeded in 55,926.1 ms |
| CI build `b0e7148` server startup | all 9 stages; operational-ready 8,517 ms |
| CI build `b0e7148` server shutdown | SPOT and CSV passed; comm metrics failed after 1,013.9 ms because its 60-second sleep was not interruptible |
| `git diff --check` | PASS |

## Risk Review

- Migration risk: none; no persisted schema or configuration changes.
- Security: no arbitrary channel, raw backend content, path, URL, or sensor value
  crosses into startup UI state.
- Operational failure mode: explicit timeout/error overlay with retry, offline,
  and exit actions.
- Rollback: revert the feature commit to restore immediate dashboard exposure;
  no state repair is required.
- Remaining environment gate: rebuild the NSIS from the reviewed hotfix and
  rerun the same server startup/splash/clean-exit validation. The latest package
  proves the SPOT/CSV fixes but is not releasable because comm metrics shutdown
  returned false and backend exited code 2.

## Recommendation

Proceed to update draft PR #174 after the final health gate. Independent
adversarial review identified non-zero exit normalization, SPOT/CSV durability,
fact deduplication, explicit thread-stop, and inherited progress-environment
gaps; each is fixed and covered by regression tests.

## Next Steps

- [x] Design-to-code match rate is at least 90%.
- [x] Complete final independent review verification with no unresolved critical issue.
- [x] Produce the PDCA completion report.
- [x] Create draft PR #174 from the reviewed commit.
- [ ] Validate the post-review hotfix installer on the server and require backend exit code 0.
