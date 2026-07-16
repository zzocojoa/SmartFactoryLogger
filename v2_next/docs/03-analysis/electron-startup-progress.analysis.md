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
- [x] Backend stdout emits only nine allowlisted compact progress stages.
- [x] Fragmented/coalesced stdout parser has bounded line and buffer limits.
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

## Validation Evidence

| Check | Result |
|-------|--------|
| Node coordinator/IPC/lifecycle tests | 27 passed |
| Frontend tests | 237 passed across 31 files |
| Backend tests | 500 passed |
| Frontend typecheck/lint | PASS |
| Backend ruff/mypy | PASS |
| Frontend production build and splash copy | PASS |
| Electron local smoke | ready-to-show 274.6 ms; first paint 282.0 ms; window shown 299.4 ms; backend trigger 300.5 ms; operational-ready 7,547.9 ms; overlay hidden |
| Process cleanup | Electron 0; TCP 8000 listener 0 |
| `git diff --check` | PASS |

## Risk Review

- Migration risk: none; no persisted schema or configuration changes.
- Security: no arbitrary channel, raw backend content, path, URL, or sensor value
  crosses into startup UI state.
- Operational failure mode: explicit timeout/error overlay with retry, offline,
  and exit actions.
- Rollback: revert the feature commit to restore immediate dashboard exposure;
  no state repair is required.
- Remaining environment gate: packaged NSIS and server-device startup validation
  occur after PR merge approval and are not a code/design gap.

## Recommendation

Proceed to commit/push/PR. The first review pass identified lifecycle,
generation, first-paint ordering, semantic-gate, and accessibility gaps; each is
fixed and covered by tests. The final independent `$review` result is `CLEAN`.

## Next Steps

- [x] Design-to-code match rate is at least 90%.
- [x] Complete final independent review verification with no unresolved critical issue.
- [x] Produce the PDCA completion report.
- [ ] Create the pull request from the reviewed commit.
