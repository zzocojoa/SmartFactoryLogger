# Changelog

All notable changes to Smart Factory Logger V2 are documented here.

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
