# spot-camera-rest-api-conformance - Plan Document

> Version: 1.0.0 | Date: 2026-07-11 | Status: Approved
> Level: Dynamic

---

## 1. Overview

### 1.1 Purpose

Align every SPOT camera image acquisition and display path with the normative
contract in `docs/reference/ametek_land_spot.pdf`:

- read the latest JPEG from `GET http://[ipaddress]/image.jpg`;
- display the completed JPEG response;
- request the next image only after the current image has completed;
- use one logical image acquisition loop for all UI consumers.

### 1.2 Background

The current implementation predates the manufacturer REST API guide and has two
independent application paths (`/api/spot/live_image` and
`/api/spot/proxy_image`), two caches, optional non-manual upstream paths,
success/error delays, stale-frame fallback, and separate dashboard/settings
presentation behavior. This creates protocol ambiguity, duplicate upstream
traffic, and inconsistent operator status.

## 2. Goals

### 2.1 Primary Goals

- [x] Make `/image.jpg` derived from the configured SPOT IP the only upstream
      camera resource.
- [x] Replace live/proxy acquisition with one internal bridge and one
      completion-driven frontend state machine.
- [x] Make Dashboard and Settings display the same frame state and the same
      success/error status.
- [x] Remove alternative live URL configuration, `/newjpeg.jpg` support,
      duplicate caches, stale-frame responses, artificial success delays, and
      duplicate polling.
- [x] Preserve JPEG validation, bounded HTTP timeout, single-flight safety,
      observability, and optional evidence capture as application safeguards
      around the official resource.

### 2.2 Non-Goals

- Do not change SPOT temperature, diagnostics, focus, actuator, or control REST
  contracts.
- Do not change CSV schemas or existing image evidence fact schemas.
- Do not introduce MJPEG, WebSocket, device writes, or undocumented SPOT
  resources.

## 3. Scope

### 3.1 In Scope

- Backend SPOT image URL resolution and HTTP acquisition.
- Backend camera route, diagnostics, observability, and memory reporting.
- Frontend SPOT image transport, lifecycle state, Dashboard camera, and Settings
  preview.
- Configuration models and persistence fields used only by the removed live URL.
- Tests, API documentation, deployment QA, and PDCA records for the removed
  paths.

### 3.2 Out of Scope

- Temperature/phase/quality logic.
- SPOT control writes and security mode.
- Image retention policy and evidence facts after a successful official JPEG
  acquisition.
- Historical reports retained as audit records; they may be marked superseded
  instead of rewritten.

## 4. Success Criteria

- [x] Source search finds no runtime support for `SPOT_LIVE_IMAGE_URL`,
      `liveimageurl`, `/api/spot/live_image`, or `/newjpeg.jpg`.
- [x] Runtime upstream camera requests can only resolve to
      `http://{SPOT_IP}/image.jpg`.
- [x] Runtime exposes one internal image bridge and one in-flight acquisition.
- [x] No current-frame cache, stale-frame fallback, or success-delay timer can
      substitute an older image for the latest completed response.
- [x] Dashboard and Settings render the same Blob URL and share the same
      load/error lifecycle.
- [x] A successful image load triggers exactly one next acquisition even when
      both UI consumers are mounted.
- [x] An image error stops automatic recursion and remains visible until an
      explicit retry/reconnect, matching the guide's success-only recursion.
- [ ] Focused frontend/backend tests, full health checks, lint, type checking,
      build, and packaged smoke validation pass.
- [ ] Server validation proves PLC/temperature/CSV remain healthy and the camera
      error queue stabilizes under the single official path.

## 5. Schedule

| Phase | Target Date | Status |
|-------|------------|--------|
| Plan | 2026-07-11 | Complete |
| Design | 2026-07-11 | Complete |
| Implementation | 2026-07-11 | Complete |
| Review | 2026-07-11 | Pending |

## 6. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| CORS/file-origin prevents direct device XHR | High | High | Keep one same-origin backend bridge while fixing its upstream to the official resource. |
| Removing stale cache exposes device errors | Medium | Medium | Surface the real error and require explicit retry; do not silently present an old frame. |
| Two mounted image consumers trigger duplicate requests | High | Medium | Guard completion by Blob URL/frame identity and keep a single in-flight owner. |
| Evidence capture regression | High | Medium | Enqueue capture only from the single successful official response and retain existing fact tests. |
| Existing integrations call removed routes | Medium | Low | Update all repository consumers and document the intentional breaking route removal. |
| Device load remains high | Medium | Medium | Completion-driven recursion naturally limits requests to device response/decode speed; measure server request/error rates. |

## 7. References

- `docs/reference/ametek_land_spot.pdf`, sections 2.3, 3.3, and 5.3.
- `docs/02-design/features/spot-live-image.design.md` (superseded design).
- `docs/03-review/spot-live-image-post-implementation-review.md` (historical evidence).
