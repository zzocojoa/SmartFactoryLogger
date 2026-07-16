# Changelog

All notable changes to Smart Factory Logger V2 are documented here.

## [1.0.14] - 2026-07-16

### Added

- Added a session-correlated operational startup metric that waits for backend
  health, the first timestamped live factory snapshot, and dashboard paint.
- Added a strict packaged cold-start PowerShell measurement under `resources/qa`
  with contamination, timeout, and missing-milestone failure evidence.

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
- Bounded the two operational startup polling requests (`/health` and
  `/api/data`) to two seconds so a request opened before Uvicorn is listening
  cannot indefinitely prevent its next retry.
- Kept health polling at its five-second base interval until the first
  successful response; the existing post-recovery outage backoff is unchanged.
- Kept packaged cold-start health and live-data polling active until their first
  successful readiness result even when the Electron document is hidden or a
  stale dashboard leader lock exists; normal visibility and leader behavior
  resumes after success.

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
