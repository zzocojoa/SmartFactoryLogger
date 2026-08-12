# Changelog

All notable changes to Smart Factory Logger V2 are documented here.

## [1.0.20] - 2026-08-12

### Added

- Added a bounded, append-only SPOT diagnostic request journal so operators can
  correlate each field request with its snapshot, poll, and transport lifecycle
  across timeout, cancellation, recovery, and process restart boundaries.
- Added payload-free transport failure retention that remains available after
  later successful traffic for post-canary root-cause analysis.

### Changed

- Moved diagnostic journal persistence to a bounded single-writer queue outside
  the event loop and serialized SPOT device lock, with queue, write latency,
  rotation, recovery, and shutdown-drain health exposed through diagnostics.
- Made restart recovery byte-bounded and schema-allowlisted, preserving complete
  events that lack only a final newline while rejecting malformed or private
  fields before they can reappear through the diagnostics API.

### Fixed

- Prevented later diagnostic success, JSONL rotation, or process restart from
  erasing the timeout phase, exception class, UTC duration, and correlation IDs
  needed to attribute the post-canary API stalls observed in v1.0.19.
- Made journal shutdown drain retryable without detaching a live writer, and
  record queued transport work as terminal `shutdown_cancelled` evidence.
- Added a bounded failure-terminal queue reserve so successful terminal traffic
  cannot crowd out timeout, cancellation, or failed-completion evidence; exposed
  per-class drop counters and made any failure-terminal drop fail closeout.
- Deferred final journal close until all SPOT producers drain, and made corrupt
  recovery lines, including non-scalar allowlisted fields, fail open without
  blocking startup.
- Converted recovered `queued` or `running` requests without a terminal record
  into durable, cause-neutral `terminal_missing` failure evidence.

## [1.0.19] - 2026-08-07

### Fixed

- Prevented a second Electron launch from creating a competing runtime, and
  made startup Retry preserve a backend only when a bounded, authenticated
  health check matches the spawned child process identity.
- Deferred duplicate-launch focus until the hidden startup window passes its
  normal show gate, and prevented late Retry health from resetting a dashboard
  that became ready while the check was in flight.
- Made SPOT shutdown report each background task's final or timed-out state,
  recover metadata finalization when observation writes drain late, and fail
  closed when a completed drain can no longer produce a trustworthy manifest.
- Kept the event loop active while explicitly awaiting the final bounded SPOT
  observation drain before CSV manifest closeout.
- Normalized unavailable SPOT diagnostic ages to JSON `null`, bounded Electron
  debug logs to three 8 MiB backups, and corrected shutdown evidence discovery
  to prefer the packaged Electron user-data path and merge its rotated backups.

### Changed

- Expanded regression coverage for duplicate launches, Retry health failures,
  late SPOT shutdown completion, manifest closeout, log rotation, and evidence
  path selection.

## [1.0.18] - 2026-08-07

### Fixed

- Routed backend restart stops and native application shutdown through the
  same verified graceful-closeout gate. A window close that overlaps an active
  restart can now reuse the verified old-process closeout instead of becoming
  permanently blocked after the process reference is cleared.
- Kept forced stops, non-zero backend exits, and missing-process states from
  being accepted as successful CSV closeout, including repeated restart
  attempts after a failed closeout. These source changes postdate the `9eaa913`
  field evidence and therefore require a new commit-bound server validation
  before any replacement package is deployed.

### Documentation and Operations

- Restored the source-controlled `runtime-error-root-cause-validation` PDCA
  record, including the original incident split for PLC startup data-shape
  errors, SPOT TCP four-tuple reuse, duplicate-instance rejection, and the
  separate 08:10 host-side stall.
- Preserved the 2026-07-31 `575e869` historical field result: 120-minute
  canary, 7,197 trigger polls with no new ConnectTimeout, 7,101/7,101 successful
  pings, 22,321 successful TCP handshakes, and a 74.039-second minimum observed
  same-four-tuple reuse interval. The sanitized canary SHA-256 remains
  `3393C32C8C248704448E10DD5BC38A49012E8FA07B89362CFE7306B70BFA6350`.
- Corrected the operational boundary after the later `49fbf6b`
  shutdown-closeout QA failure: the actual server was restored to the verified
  v1.0.16 package, `949ef38` was not deployed, and no historical field evidence
  authorizes a later release candidate without new commit-bound validation.
- Recorded the 2026-08-06 `0695a0f` server comparison without reusing prior
  evidence: its first Alt+F4 close completed a verified shutdown closeout, but
  the later native X-button close during one-command QA stopped all product
  processes without adding `csv_closeout` to the matching current-session
  metadata. QA therefore failed closed and smoke/canary were not started.
- Recorded the replacement private unsigned `9eaa913` validation separately:
  commit-bound re-attestation and native X-close one-command QA passed, the
  15-minute passive smoke found no new ConnectTimeout, and the recovered
  120-minute canary plus final live gate retained the same backend process with
  zero transport, source-port reuse, pool-exhaustion, or image failures.
- Added the matching historical 15-minute collector source and marked it
  explicitly as investigation-only so it cannot be mistaken for the later
  commit-bound 120-minute promotion gate. Generated packet captures, private
  raw evidence, and release archives remain outside source control.
- Hardened the restored collector tooling with boundary self-tests, IPv4/IPv6
  and zone-index redaction, error-message/path fingerprinting, fail-closed
  detection of existing pktmon captures, bounded sampling parameters, safe
  elevation path handling, and propagation of collection failure exit codes.

### Distribution

- Deferred purchase and registration of a publicly trusted Windows
  Authenticode certificate while Smart Factory Logger remains limited to
  owner-controlled private use. Unsigned internal installers must still be
  distributed with SHA-256 verification and a commit-bound release kit.
- Publicly trusted production signing remains mandatory before any installer is
  distributed to customers, external users, or commercial environments. Do not
  assume that a CA-issued certificate can be exported as a PFX; token-, HSM-,
  or cloud-backed certificates require the matching remote-signing workflow.

## [1.0.17] - 2026-08-05

### Added

- Added SPOT image request shaping with shared caching and single-flight
  refreshes so multiple dashboard consumers no longer create duplicate device
  connections.
- Added a unified background request budget for image, target-temperature,
  internal-temperature, and diagnostic traffic, with live diagnostics showing
  the effective request rate.
- Added an exclusive source-port pool with a 75-second quarantine window so
  SPOT connections cannot quickly reuse the same TCP four-tuple.
- Added a separate production-signing GitHub Environment workflow that keeps
  certificate secrets out of PR builds and refuses release artifacts unless
  the exact published installer and its extracted application, complete backend
  bundle, signer thumbprint, timestamp, and build provenance all verify. Windows
  release Python dependencies are pinned transitively with SHA-256 hashes, and
  workflow action references are parsed as YAML and restricted to exact commit
  allowlist entries.

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
  observed before operator shutdown and to the sidecar explicitly finalized by
  that service shutdown. The closeout now records only the per-file sample
  sequence persisted after a successful CSV flush, and the validator compares
  it with the actual final and maximum CSV sequence. Daily rollover files,
  multiline CSV values, stale same-process sidecars, failed final flushes, and
  transient health failures therefore cannot misdirect or falsely pass QA.
- Rejected clean fact closeout when an observation spool remains pending or an
  observation/image writer recorded a failure earlier in the runtime, including
  fail-closed handling when a restarted writer cannot read its spool and
  persistent quarantine of malformed or schema-mismatched spool rows.
- Made image-fact closeout fail closed when another writer changes the durable fact
  file outside the active writer's tracked byte range, preventing stale row
  counts or SHA-256 values from being trusted.
- Preserved observation-fact deduplication after a durable append when a
  subsequent file-size probe fails, so the same fact is not spooled and
  appended twice while manifest closeout still fails closed.
- Routed packaged device connection tests through trusted Electron main IPC
  with a per-launch control token, and admitted only one SPOT probe per
  30-second cooldown so unauthenticated LAN or browser traffic cannot queue or
  continuously repeat probes ahead of operational temperature, image, or
  diagnostic requests.
- Kept v2 CSV logging available when the configured LogPath falls back or
  changes before runtime fact writers can follow it, while marking the fact
  manifests incomplete and rejecting a falsely clean shutdown.
- Preserved focus and actuator API compatibility while routing eligible
  background requests through the guarded transport.
- Bound Windows release artifacts and their packaged backend provenance to the
  pull-request head commit so CI cannot publish a synthetic merge build under a
  source-commit identity.

### Post-validation changes — field revalidation required

- Held the native BrowserWindow close event until the existing authenticated
  backend shutdown and CSV closeout completes. A failed closeout now keeps the
  application window open and permits a bounded retry instead of allowing the
  renderer and backend to disappear without finalized metadata.
- Kept forced, signalled, non-zero, and unverified missing-process shutdowns
  outside the successful closeout path. A second close request can no longer
  reinterpret an earlier terminal backend failure as a clean application exit.
- Restored the packaged Electron X-button shutdown request through the tested,
  authenticated backend control client, including bounded fallback when the
  request fails synchronously or the backend exits non-zero.
- Restricted backend shutdown control to trusted loopback requests. Packaged
  Electron requests still require the per-launch token, while standalone mode
  rejects remote clients and non-loopback browser origins or referrers.
- Rejected truncated, aborted, and errored backend connection-test responses so
  the trusted Electron IPC request always settles instead of waiting
  indefinitely after a partial HTTP response.
- Included the extracted connection-test client in the Electron Builder file
  allowlist so packaged startup cannot fail with `MODULE_NOT_FOUND`.
- Validated v2 `sample_seq` persistence bookkeeping before writing a batch so
  a rejected non-advancing batch cannot already be durable and then be appended
  again on retry.
- Bound one-command QA shutdown selection to the exact current-session CSV
  basename and recorded the observed basename rather than echoing the expected
  value.
- Cached observation-fact spool/archive pending counts and updated them on
  spool mutation so frequent health requests do not repeatedly rescan every
  quarantined archive row.

### Validation

- The packaged `575e869` baseline passed the complete Electron, frontend,
  backend, lint, type-check, QA self-test, production-build, transport-race,
  and socket-interrupt suites.
- Code candidate `d8ca5c4` passed the complete local health suite: 51 Electron
  tests, 253 frontend tests across 34 files, 642 backend tests, frontend
  type-check and lint, Ruff, mypy, and the NSIS QA self-test. The subsequent
  `c1845e9` packaged development build passed an isolated native X-button close:
  startup health reached `200`, all product processes and health stopped, and
  its commit-bound metadata recorded `csv_closeout.finalized=true`.
- Passed commit-bound re-attestation, one-command QA, the approved 15-minute
  smoke, and the 120-minute canary for packaged commit `575e869`. The final
  live gate retained the expected backend and config hashes, verified
  attestation, active source-port quarantine, zero reuse, exhaustion, and
  transport failures, and healthy image capture.
- Added direct regression coverage for the valid, backward-compatible, and
  fail-closed CSV shutdown-closeout validation paths.
- Managed-switch evidence remains unavailable for the earlier `575e869` canary,
  so that historical result is `FIELD_CANARY_PASS` with
  `PHYSICAL_PATH_PARTIAL`; it cannot be reused for the current commit.
- Packaged commit `49fbf6b` reproduced the missing CSV shutdown-closeout failure
  during one-command QA and was rolled back to the verified v1.0.16 installer.
  Neither the unsigned `949ef38` candidate nor the later development packages
  have been installed on the server.
- Private unsigned commit `0695a0f` passed install, current-session metadata,
  and commit-bound re-attestation on the server. Its first Alt+F4 close produced
  a verified finalized closeout, but a later native X-button close reproduced
  the missing `csv_closeout` failure. The exact QA evidence SHA-256 is
  `531F1E399B12846F8DD20EC949B7A21260EDDAC7A4E9F231041D81AD98BEB6B6`;
  the server was left stopped and no smoke or canary evidence exists for this
  commit.
- Private unsigned commit `9eaa913` then passed commit-bound re-attestation and
  native X-close one-command QA. The QA evidence SHA-256 is
  `AA644BA2A2FB90742BCD204A9DE4CA6F53D4E629949900150B66B654E493D294`.
  Its 15-minute passive smoke completed without a new ConnectTimeout; managed
  switch counters were unavailable, so physical-path exclusion remained
  partial and the sanitized evidence SHA-256 is
  `33B2A238CB0E71D289EB0C3ADFC8014C1329DC370552DED409DE716C8D4B85F5`.
- The recovered 120-minute `9eaa913` canary and unchanged-runtime final live
  gate passed with the original backend PID, 7,191 successful trigger polls,
  zero ConnectTimeout, zero transport failures, a 75-second minimum source-port
  reuse interval, and bounded memory. The original collector exit-code failure
  remains preserved as a tooling limitation. The official sanitized ZIP
  SHA-256 is `5B0E9F486F0CC1E38D1F64DB61A36FFDF4D86E6F6345C9173F02553D8BF4EB14`;
  the final live-gate evidence SHA-256 is
  `7F12C87A79774803956B5024520ACB3AA38A79C6350276DD548B7E2AB00AE586`.
- `9eaa913` authorizes its exact private package only. The later source change
  that rejects forced or otherwise unverified backend stops has local automated
  coverage but needs its own commit-bound field validation before deployment.
  Public, customer, or commercial promotion remains blocked until that final
  package is publicly trusted, signed, and passes the complete server sequence.

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
