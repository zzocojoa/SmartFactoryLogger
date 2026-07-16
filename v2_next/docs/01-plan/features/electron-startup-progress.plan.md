# Electron Startup Progress - Plan Document

> Version: 1.0.0 | Date: 2026-07-16 | Status: Approved for implementation
> Level: Dynamic

---

## 1. Overview

### 1.1 Purpose

Replace the current immediately exposed dashboard startup with one Electron-owned
startup experience. The installed app must paint the existing splash artwork as
soon as the local HTML loads, show truthful backend and renderer readiness
milestones, and reveal the dashboard only after the minimum operator-usable gates
have completed.

### 1.2 Background

Electron currently starts the backend and dashboard window in parallel. The
backend's legacy Tk splash is intentionally disabled for an embedded Electron
host, and the renderer can expose loading or offline dashboard content before the
backend and first factory-data response are ready. Startup telemetry already
records backend health, first Running data, dashboard paint, diagnostic timeout,
and operational ready. This feature turns that evidence into a bounded user-facing
startup flow without weakening the existing release performance metric.

## 2. Goals

### 2.1 Primary Goals

- [x] Paint a single-window startup overlay immediately from local HTML without
  waiting for React or backend availability.
- [x] Show real, monotonic milestone progress for Electron, backend lifecycle,
  backend HTTP health, first factory-data snapshot, and dashboard paint.
- [x] Preserve the existing strict `renderer.dashboard-operational-ready` event,
  which still requires a timestamped `Status=Running` snapshot.
- [x] Add a separate first-data-snapshot gate for UI handoff so a timestamped
  explicit Offline/Error snapshot can reveal an honest degraded dashboard.
- [x] Never leave an operator on an endless splash: expose retry, continue
  offline, and exit actions after a 30-second deadline or backend failure.
- [x] Keep Electron renderer privileges constrained with context isolation,
  no Node integration, allowlisted IPC, bounded payloads, and no raw backend log
  forwarding.
- [x] Add automated normal, degraded, timeout, parser, one-shot, cleanup, and IPC
  contract tests before creating the PR.

### 2.2 Non-Goals

- Do not change PLC, LS PLC, SPOT, CSV, or dashboard polling intervals.
- Do not wait for every optional device or background diagnostic before showing
  the dashboard.
- Do not replace the existing operational-ready release gate or its PowerShell QA
  artifact schema.
- Do not re-enable the standalone Tk splash inside Electron.
- Do not add a second BrowserWindow, generic IPC forwarding, network telemetry,
  persistent settings, database migrations, or a package-version bump.

## 3. Scope

### 3.1 In Scope

- A pure main-process startup coordinator and bounded backend progress parser.
- Structured backend lifecycle stage events written to embedded stdout.
- Constrained preload methods for startup state snapshot, subscription, retry,
  offline continuation, and exit.
- An inline HTML overlay using the existing splash image and a locally rendered
  progress/status/action surface.
- A Vite build hook that emits the existing backend splash asset into the packaged
  frontend without duplicating the binary in source control.
- Renderer telemetry for the first timestamped factory-data snapshot regardless
  of Running/Offline/Error status.
- Normal/degraded/error/timeout state transitions and one-shot dashboard handoff.
- PDCA design, analysis, report, test evidence, review, and PR metadata.

### 3.2 Out of Scope

- Installer creation and physical-server acceptance in this PR turn. Those remain
  post-merge release gates because they require the server computer.
- Redesigning the dashboard after the startup overlay is dismissed.
- Displaying raw stack traces, device addresses, sensor values, or log file paths
  in the startup UI.
- Automatically restarting physical-device workers independently of the backend.

## 4. Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | Local HTML displays the splash overlay before the React module entry executes. | High |
| FR-02 | Main owns the authoritative startup state and elapsed clock. | High |
| FR-03 | Backend emits only allowlisted structured lifecycle stage names. | High |
| FR-04 | Main parses fragmented/multiple stdout lines with a bounded buffer and ignores malformed or unknown events. | High |
| FR-05 | Progress is milestone-based, monotonic, and reaches 100 only at a terminal ready/degraded state. | High |
| FR-06 | Normal handoff requires backend health, first timestamped Running snapshot, and confirmed dashboard paint. | High |
| FR-07 | Degraded handoff accepts a valid timestamped non-Running snapshot after backend health and paint. | High |
| FR-08 | Existing strict operational-ready telemetry semantics remain unchanged. | High |
| FR-09 | Backend exit/spawn failure becomes an actionable error state immediately. | High |
| FR-10 | A 30-second deadline exposes retry, offline continuation, and exit without hiding the diagnostic state. | High |
| FR-11 | Retry resets the startup session state, terminates the current backend tree, and starts one replacement backend. | High |
| FR-12 | Continue offline dismisses only the overlay and leaves the dashboard's existing Offline status visible. | High |
| FR-13 | State IPC and actions are fixed-name, schema-validated, and unavailable to arbitrary channels. | High |
| FR-14 | Overlay dismissal waits for a paint opportunity and uses a bounded fade transition. | Medium |
| FR-15 | Startup events remain locally observable and correlated to the existing Electron startup session. | High |

## 5. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Performance | Static overlay paint target <= 500 ms; no new backend/device request; normal v1.0.15 startup must remain below the existing 30-second gate. |
| Availability | Device Offline/Error must not permanently block access to the dashboard. |
| Security | Context isolation and no Node integration remain; no raw stdout, paths, URLs, secrets, or sensor values enter the UI state. |
| Accessibility | Status uses `role=status`/`aria-live`; progress uses `role=progressbar`; actions are keyboard focusable. |
| Observability | Every state transition logs bounded `from`, `to`, `reason`, and elapsed data under the existing startup session. |
| Compatibility | Browser development without the Electron bridge removes the overlay immediately and retains current routing. |
| Maintainability | State machine and parser are pure CommonJS code testable with Node's built-in test runner. |

## 6. Success Criteria

- [x] `[AC-01]` HTML test proves overlay markup precedes the module entry.
- [x] `[AC-02]` Normal coordinator test reaches ready exactly once with monotonic progress.
- [x] `[AC-03]` Offline/error snapshot test reaches degraded without satisfying strict operational-ready.
- [x] `[AC-04]` Timeout test exposes exactly the three approved actions and never fabricates ready.
- [x] `[AC-05]` Backend failure test enters error immediately and retry creates a fresh deadline/state.
- [x] `[AC-06]` Parser tests cover fragmented, coalesced, malformed, oversized, and unknown-stage input.
- [x] `[AC-07]` Preload tests/contracts prove only fixed startup methods/channels are exposed and listeners unsubscribe.
- [x] `[AC-08]` Backend tests prove every lifespan stage emits a structured allowlisted event and embedded output is flushed.
- [x] `[AC-09]` Existing startup telemetry unit tests remain green with unchanged strict Running semantics.
- [x] `[AC-10]` Frontend typecheck, lint, full tests, backend lint/typecheck/tests, Node startup tests, build, and `git diff --check` pass.
- [x] `[AC-11]` PDCA gap analysis reaches at least 90% with no missing high-priority requirement.
- [x] `[AC-12]` Review finds no unresolved critical issue before commit/push/PR.

## 7. Delivery Sequence

| Phase | Target Date | Status |
|-------|-------------|--------|
| Plan | 2026-07-16 | Complete |
| Design | 2026-07-16 | Complete |
| Implementation | 2026-07-16 | Complete |
| Check / Act | 2026-07-16 | Complete |
| Review / PR | 2026-07-16 | Review complete; PR ready |

## 8. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Overlay never dismisses | Production-critical | Medium | Separate snapshot and strict Running gates; 30-second action state; browser fallback removal. |
| Dashboard shows before real paint | High | Medium | Reuse the confirmed `raf` dashboard event and apply a bounded fade. |
| Retry starts duplicate backends | High | Medium | Serialize restart, kill the owned backend tree, and block repeated retry while restarting. |
| Stdout parser trusts arbitrary text | High | Medium | Fixed prefix, bounded line/buffer sizes, JSON object validation, and stage allowlist. |
| Device outage becomes app outage | High | High | Degraded dashboard is an accepted terminal UI state. |
| Existing server QA semantics regress | High | Medium | Preserve strict first-live-data and operational-ready gates; add a new event instead of redefining old events. |
| Startup image increases bundle drift | Medium | Low | Emit the existing tracked image during Vite build; no duplicated binary. |
| New IPC broadens attack surface | High | Low | Fixed methods only, sender-frame validation in main, no arbitrary names/arguments. |

## 9. Rollback and Operations

- Rollback is one branch revert removing the coordinator, preload methods,
  structured backend events, inline overlay, and tests. Existing immediate
  dashboard loading and operational-ready instrumentation remain available.
- No data/config migration exists, so rollback does not require state repair.
- The expected operational failure mode is an explicit timeout/error overlay,
  never a blank screen or infinite spinner.
- Post-merge release validation must run the existing bundled operational-ready
  QA and verify normal, PLC-offline, SPOT-offline, retry, and clean-exit behavior.

## 10. References

- `docs/01-plan/features/nsis-operational-ready-timing.plan.md`
- `docs/02-design/features/nsis-operational-ready-timing.design.md`
- `docs/03-analysis/nsis-operational-ready-timing.analysis.md`
- `main.js`
- `preload.js`
- `frontend/src/shared/startup/startupTelemetry.ts`
