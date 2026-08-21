# spot-realtime-image-performance - Plan Document

> Version: 1.0.1 | Date: 2026-08-21 | Status: Implemented; local validation complete
> Level: Dynamic
> Branch: `codex/spot-realtime-image-performance`

---

## 1. Overview

### 1.1 Purpose

Restore an operator-usable SPOT image cadence without reintroducing the field-observed
TCP source-port reuse failure. The device boundary remains the manufacturer-defined
`GET http://{SPOT_IP}/image.jpg`; the application separates the operator live policy
from the slower snapshot policy while sharing one validated frame cache and one
single-flight upstream request.

### 1.2 Background

The current implementation waits the configured measurement interval after each
displayed frame and enforces a three-second backend cache minimum. With the default
configuration, a new visible frame therefore arrives only about every three seconds.

The manufacturer guide does not require that delay. Sections 2.3 and 5.3 use
`/image.jpg`, and the complete example requests the next JPEG after the prior response
has completed. Earlier unrestricted completion-driven polling reached about 14
requests/s and contributed to short HTTP/1.0 connections, premature Windows source-port
reuse, SPOT old-ACK responses, RSTs, and `ConnectTimeout`. The later guarded transport
proved a 768-port pool with a 75-second quarantine and a six-request/s background
budget on the actual server.

## 2. Goals

### 2.1 Primary Goals

- [x] Keep `/image.jpg` as the only SPOT device image resource.
- [x] Preserve `/api/spot/image.jpg` as the slow snapshot bridge.
- [x] Add a distinct operator route, `/api/spot/live_image.jpg`, backed by the same
      upstream resource, cache, lock, validation, and evidence hook.
- [x] Cap live acquisition dynamically so image + temperature + internal temperature +
      diagnostics remain at or below six background SPOT requests/s.
- [x] Target up to 4 FPS under the default three-second measurement configuration.
- [x] Keep frontend completion-driven scheduling, visibility pause, single in-flight
      ownership, and bounded retry/backoff.
- [x] Reject malformed SPOT host values that could alter the canonical `/image.jpg`
      path.
- [x] Add route/profile observability and repeatable localhost performance validation.

### 2.2 Non-Goals

- No `image.ssi`, `/newjpeg.jpg`, MJPEG, WebSocket, or undocumented device resource.
- No change to temperature, diagnostics, focus, actuator, CSV, database, or evidence
  fact schemas.
- No direct request to a physical SPOT device from the development workstation.
- No production promotion based on localhost performance evidence alone.

## 3. Scope

### 3.1 In Scope

- Backend image profile selection, dynamic request budget, shared cache, and routes.
- Frontend operator image route and effective cadence selection.
- Aggregate observability for snapshot and live application routes.
- Strict server-side construction of `http://{SPOT_IP}/image.jpg`.
- Backend/frontend unit and integration tests.
- A localhost HTTP/1.0-close performance harness using a valid JPEG payload.
- PDCA Plan, Design, Analysis, and Completion Report.

### 3.2 Out of Scope

- Physical-device Network capture of `image.ssi` internals.
- Installer signing, server installation, managed-switch capture, and 120-minute canary.
- Operator FPS configuration UI; the first release uses a code-owned safe maximum.
- Stale-frame fallback after an expired frame refresh fails.

## 4. Requirements

| ID | Requirement | Priority |
|---|---|---:|
| FR-01 | Every upstream image GET resolves to exactly `/image.jpg`. | P0 |
| FR-02 | Snapshot and operator routes share one cache and one refresh task. | P0 |
| FR-03 | Snapshot freshness remains 3-10 seconds. | P0 |
| FR-04 | Operator freshness is dynamically capped at 4 FPS and total background budget <= 6/s. | P0 |
| FR-05 | Hidden documents schedule no new image fetch. | P0 |
| FR-06 | One failed operator request enters the existing 0.5/1/2-second bounded retry sequence. | P0 |
| FR-07 | Concurrent callers never create concurrent SPOT image requests. | P0 |
| FR-08 | Snapshot and live routes expose no-store JPEG responses and profile metadata. | P1 |
| FR-09 | Existing `/api/spot/live_image` and `/api/spot/proxy_image` remain removed. | P1 |
| FR-10 | Malformed host/path/query input cannot change the device resource path. | P0 |

## 5. Success Criteria

- [x] Default configuration reports a live target of 4 FPS and total theoretical
      background load <= 6 requests/s.
- [x] Fastest supported temperature poll configuration automatically reduces live FPS
      and still reports total theoretical load <= 6 requests/s.
- [x] A localhost HTTP/1.0-close run sustains at least 3.5 displayed requests/s for 10
      seconds with zero failures, zero overlapping upstream image requests, and no
      source-port pool exhaustion or reuse violation.
- [x] Upstream image request rate never exceeds the effective live cap by more than one
      startup request in a bounded observation window.
- [x] Snapshot requests continue to use the three-second minimum unless a fresher frame
      already exists in the shared cache.
- [x] Focused backend/frontend tests, typecheck, Ruff, mypy, full backend/frontend tests,
      and repository health checks pass.
- [x] Design-to-implementation gap analysis reaches at least 90% with no P0 gap.

## 6. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| Higher cadence exhausts guarded source ports | High | Medium | Dynamic <=6/s budget, 4 FPS ceiling, shared cache, single-flight, field revalidation gate. |
| Image polling starves temperature/control | High | Medium | Existing device-wide lock releases per request; image rate is budgeted after non-image load. Add concurrency/fairness tests. |
| Multiple windows multiply device traffic | High | Medium | Process-wide freshness cache and shared refresh task make caller count independent of upstream rate. |
| Failed camera causes retry storm | High | Low | Existing frontend bounded exponential retry, backend cache/single-flight, no stale success. |
| Alternate host text changes request target/path | High | Low | Reject scheme, credentials, path, query, fragment, whitespace, and invalid port syntax before URL construction. |
| Local benchmark is mistaken for field approval | High | Medium | Label results localhost-only; require signed package, physical device smoke, and canary before promotion. |

## 7. Rollback and Operations

- Code rollback: revert this feature branch/commit; no data or config migration exists.
- Runtime rollback: reinstall the currently verified package identified by operations.
- Observability: expose effective live FPS/TTL, per-profile downstream counts, aggregate
  upstream/cache/single-flight counters, and source-port policy health without raw IP,
  URL, or port values.
- Failure mode: operator image returns explicit 502/404 while the last displayed frame
  remains visually marked as failed; temperature and logging continue independently.

## 8. References

- `docs/reference/ametek_land_spot.pdf`, sections 2.3, 3.3, and 5.3.
- `docs/02-design/features/spot-camera-rest-api-conformance.design.md`.
- `docs/02-design/features/spot-request-churn-remediation.design.md`.
- `docs/04-report/spot-tcp-source-port-quarantine-v2.report.md`.
- `docs/03-analysis/runtime-error-root-cause-validation.analysis.md`.

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-08-21 | Initial approved implementation plan. |
| 1.0.1 | 2026-08-21 | Marked local implementation and validation criteria complete. |
