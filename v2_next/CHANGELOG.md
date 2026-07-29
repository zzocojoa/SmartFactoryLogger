# Changelog

All notable changes to Smart Factory Logger V2 are documented here.

## [1.0.17] - 2026-07-29

### Added

- Added SPOT image request shaping with shared caching and single-flight
  refreshes so multiple dashboard consumers no longer create duplicate device
  connections.
- Added a unified background request budget for image, target-temperature,
  internal-temperature, and diagnostic traffic, with live diagnostics showing
  the effective request rate.
- Added an exclusive source-port pool with a 75-second quarantine window so
  SPOT connections cannot quickly reuse the same TCP four-tuple.

### Changed

- Reduced normal SPOT image and diagnostic refresh rates while keeping the
  dashboard responsive after visibility changes, errors, and route changes.
- Expanded privacy-safe SPOT transport diagnostics without exposing raw source
  port values or retaining packet payloads in shared evidence.

### Fixed

- Prevented cancelled requests, shutdown races, and blocked Windows sockets from
  reopening SPOT transport intake or delaying application exit.
- Kept source-port leases unavailable until their quarantine guard is
  successfully rebound, including exhaustion and recovery behavior.
- Preserved primary shutdown failures when drain probes fail, made partial guard
  cleanup retryable, and kept source-port diagnostics schema-stable after
  transport shutdown.
- Kept observation and image fact closeout bounded by maintaining exact
  row-count and SHA-256 manifest state while facts are appended instead of
  rescanning indefinitely growing historical files during shutdown.
- Bound one-command QA to the exact logger-service session and build commit
  observed before operator shutdown, so a newer stale sidecar cannot satisfy
  validation and transient health failures cannot impersonate a stopped app.
- Rejected clean fact closeout when an observation spool remains pending or an
  observation/image writer recorded a failure earlier in the runtime.
- Kept v2 CSV logging available when the configured LogPath falls back or
  changes before runtime fact writers can follow it, while marking the fact
  manifests incomplete and rejecting a falsely clean shutdown.
- Preserved focus and actuator API compatibility while routing eligible
  background requests through the guarded transport.

### Validation

- Passed the complete Electron, frontend, backend, lint, type-check, QA
  self-test, production-build, transport-race, and socket-interrupt suites.
- Passed commit-bound re-attestation, one-command QA, the approved 15-minute
  smoke, and the 120-minute canary for packaged commit `0c641b7`.
  Managed-switch evidence remains unavailable, so that package's software
  field gate is `FIELD_CANARY_PASS` while physical-path attribution is
  `PHYSICAL_PATH_PARTIAL`. Production promotion of a later commit still
  requires an identity-matched field validation.

### Compatibility

- No persistent schema, CSV format, SPOT device configuration, operator
  attestation value, or API route migration is required.

## [1.0.16] - 2026-07-17

### Added

- Added a splash-first startup flow that renders before backend launch and
  reports the Electron, backend lifespan, dashboard paint, health, and live-data
  readiness stages through a monotonic progress coordinator.
- Added a dedicated packaged-backend progress channel so startup stages remain
  observable when the frozen backend runs without a console window.

### Fixed

- Accepted both the first data snapshot and first live-data readiness events
  without rejecting the coordinator payload during packaged startup.
- Aligned Electron's graceful-shutdown wait with the backend control-shutdown
  contract and added explicit SPOT queue drain, CSV durable flush, and
  communication-metrics shutdown evidence.

### Validation

- Verified the merged master installer on the physical server with all nine
  backend progress stages and bundled backend integrity checks passing.
- Verified operational readiness in `7,597.2 ms`, backend exit code `0`, no
  forced Electron termination, and zero residual processes or TCP 8000
  listeners.

### Compatibility

- No persistent schema, configuration, PLC/SPOT protocol, CSV schema, image
  route, or operator workflow migration is required.

## [1.0.15] - 2026-07-16

### Fixed

- Restored the SPOT camera's internal device-temperature badge using the
  backend's existing cached temperature metadata. The dashboard continues to
  use the official `/image.jpg` route and does not add another device request.
- Kept the badge hidden when cached temperature metadata is stale or invalid so
  camera playback remains independent from temperature availability.

### Validation

- Verified the release candidate on the physical server with 13/13 successful
  image responses, 13/13 valid temperature samples from `50.3` to `50.5` °C,
  zero processing, policy, or CORS violations, and visual badge confirmation.
- Added backend header-policy and frontend parsing, visibility, and stale/error
  regression coverage.

### Compatibility

- No persistent schema, configuration, PLC/SPOT protocol, polling interval, CSV
  schema, image route, or operator workflow changes are required.

## [1.0.14] - 2026-07-16

### Added

- Added a session-correlated operational startup metric that waits for backend
  health, the first timestamped live factory snapshot, and dashboard paint.
- Added a strict packaged cold-start PowerShell measurement under `resources/qa`
  with contamination, timeout, and missing-milestone failure evidence.
- Added fail-closed verification for every installed backend bundle file,
  including path, size, SHA-256, aggregate hash, and clean build commit.

### Changed

- Packaged the Python backend as a one-dir bundle while preserving the installed
  `resources/backend/SmartFactoryBackend.exe` launcher path. This removes the
  per-launch one-file extraction delay without changing operator entry points.
- Kept periodic memory sampling lightweight; expensive USS, open-file, and
  handle details remain available through explicit diagnostic snapshots.

### Fixed

- Kept the packaged cold-start measurement running for its caller-supplied
  timeout budget after the renderer's 30-second diagnostic event, allowing a
  genuine later operational-ready event to be measured instead of terminating
  and force-closing the process at 30 seconds.
- Moved the initial memory diagnostics snapshot onto the existing sampler
  thread so slow physical-device initialization cannot block FastAPI startup
  and `/health` availability.
- Added per-stage backend lifespan timing logs for startup delay diagnosis
  without recording raw sensor or network configuration values.
- Routed packaged renderer API calls through the explicit IPv4 loopback address
  so Windows IPv6-first `localhost` resolution cannot delay every backend
  request past the operational-ready polling cycle.
- Bounded startup `/health` requests to eight seconds until their first success,
  then restored the existing two-second steady-state bound. `/api/data` remains
  bounded to two seconds throughout.
- Kept health polling at its five-second base interval until the first
  successful response; the existing post-recovery outage backoff is unchanged.
- Kept packaged cold-start health and live-data polling active until their first
  successful readiness result even when the Electron document is hidden or a
  stale dashboard leader lock exists; normal visibility and leader behavior
  resumes after success.
- Latched the first operational live-data result so a later transient
  Offline/Error snapshot cannot reactivate startup recovery or bypass hidden-tab
  leader rules.
- Moved SPOT observation-fact writes and health payload construction off the
  async event loop while preserving ordered fact persistence and cancellation
  draining.
- Moved local backend-address discovery to a diagnostic daemon thread so slow
  Windows hostname resolution cannot delay Uvicorn readiness.

### Validation

- Verified the installed one-dir package on the physical server: operational
  ready completed in `5,076.2 ms` with full 1,707-file bundle integrity.
- Verified the same installed package for 15 minutes with zero runtime, image,
  observability, logging, fact-write, fact-link, signalpc, or duplicate-key
  failures.
- Rebuilt the merged release candidate after the hidden-tab recovery latch,
  then reverified installer SHA-256 `F72567E3EFFCD84D0858E42C81666BADD13F2C35F0AAA6ED1842D0830BB4A63F`
  on the physical server. Final operational readiness completed in `4,184.3 ms`
  with no timeout, one startup session, connected PLC, Running live data, and
  1,707/1,707 backend bundle files verified.

### Compatibility

- Existing visual `renderer.dashboard-ready` telemetry, memory snapshot content
  and cadence, PLC/SPOT polling, dashboard layout, and CSV schemas are unchanged.
- SPOT/device request intervals and protocols are unchanged; the new timeout
  applies only to renderer-to-local-backend operational polling.

## [1.0.13] - 2026-07-13

### Fixed

- Published the SPOT effective temperature cache and observation snapshot as one
  atomic generation so CSV `Temperature` cannot be paired with a different
  `spot_temperature_observed_c` during a poll transition.
- Captured the cache value and observation snapshot together when producing
  diagnostics, preventing a concurrent poll from mixing two generations.

### Validation

- Added deterministic concurrency regression tests for both publish-time and
  read-time SPOT snapshot races.
- Added a portable one-command v2.5 QA bundle that performs graceful backend
  closeout before validating finalized CSV and fact manifests.
- Verified the 1.0.13 server build with the physical SPOT device: all 31 runtime,
  attestation, CSV, fact, and validator checks passed with zero warnings. See the
  [server validation report](docs/04-report/spot-temperature-v2-5-server-validation.md).

### Security

- Refreshed compatible transitive frontend dependencies to remove the critical
  `protobufjs` audit finding without forcing an unsupported Grafana upgrade.
- Pinned the validated Grafana 12.3.1 / Scenes 6.52.0 dependency set so a clean
  install cannot silently cross the repository's compatibility gate.

## [1.0.12] - 2026-07-12

### Security

- Updated Vite and Vitest within their current release lines to include Windows
  path handling and test API security fixes.
- Pinned python-multipart 0.0.32 and Pillow 12.3.0 so backend and packaged builds
  use the reviewed parser and image-decoder security floors.
- Moved the Electron runtime to the smallest currently supported stable line and
  updated electron-builder to its audited remediation release.

### Packaging

- Bumped desktop and frontend release metadata to 1.0.12 for an independently
  identifiable PyInstaller, portable, and NSIS build.
- Allowed NSIS warnings during compilation to accommodate electron-builder 26's
  known `IsPowerShellAvailable` template warning; release validation still
  requires reviewing the complete makensis warning output.

## [1.0.11] - 2026-06-01

### For contributors

- Updated backend development and packaging tooling pins so linting, type checking, and Windows backend builds use current verified patch-level tools.

## [1.0.9] - 2026-05-22

### Added

- Backfilled time-series history after the dashboard resumes from a hidden tab so users do not lose recent data when returning to the app.
- Added focused coverage for time-series buffering, sampling, and uPlot data preparation paths.

### Changed

- Refactored time-series chart data preparation into reusable helpers while preserving visible chart behavior and latest-point window anchoring.
- Refactored settings password inputs into a shared component with accessible visibility toggles.
- Simplified status panel and memory view model derivation logic without changing the visible dashboard state.
- Consolidated SPOT image cache diagnostics and cached response construction to reduce duplicated metadata handling.

### Fixed

- Kept the notification drawer aligned with the alert button.
- Preserved the newest time-series point during extrema-based downsampling so trailing chart windows stay anchored to the latest sample.
- Avoided stale cache metadata drift when serving cached SPOT images.
