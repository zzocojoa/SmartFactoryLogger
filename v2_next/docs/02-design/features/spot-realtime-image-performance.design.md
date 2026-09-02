# spot-realtime-image-performance - Design Document

> Version: 1.0.2 | Date: 2026-08-21 | Status: Implemented; local validation complete
> Level: Dynamic | Plan: `docs/01-plan/features/spot-realtime-image-performance.plan.md`

---

## 1. Overview

### 1.1 Purpose

Implement an operator-live image profile over the manufacturer-defined SPOT JPEG
resource while preserving the validated snapshot contract and Windows source-port
quarantine controls. Application routes are policy boundaries; both profiles always
perform the same device request: `GET http://{SPOT_IP}/image.jpg`.

### 1.2 Design Goals

- One canonical upstream URL and one process-wide frame acquisition state.
- Up to 4 FPS for the visible operator view under the default configuration.
- A hard theoretical background budget of at most six SPOT requests/s for every
  currently supported polling configuration.
- No stale-success response, parallel upstream image request, or browser polling while
  hidden.
- Additive application API changes with no database, CSV, evidence-fact, or config-file
  migration.

## 2. Architecture

### 2.1 System Architecture

```text
SPOT host config
      |
      v
strict server-side URL builder -> http://{host}/image.jpg
      |
      v
guarded HTTP/1.0-close transport + device-wide serialization
      |
      v
validated immutable JPEG cache + one shared refresh task
      |
      +------------------------------+
      |                              |
snapshot profile                 operator-live profile
TTL 3..10 s                      dynamic TTL >=250 ms
      |                              |
GET /api/spot/image.jpg          GET /api/spot/live_image.jpg
                                     |
                                     v
completion-driven Blob display -> wait effective TTL -> next GET
```

The two application routes do not create two upstream loops. They pass a profile to the
same `fetch_image_async` function. Freshness is evaluated against the caller profile,
but cache publication, refresh task, device lock, transport, JPEG validation, evidence
enqueue, and error state remain shared.

### 2.2 Manufacturer Boundary

The PDF contract is implemented as follows:

1. Sections 2.3 and 5.3 define `GET http://[ipaddress]/image.jpg` and a JPEG/blob
   response.
2. Section 5.3 advances only after the prior response has completed. The frontend keeps
   that completion-driven invariant and adds a safety delay after display completion.
3. Section 3.3's shorter `/image` spelling is not used because the parameter index and
   complete example both use `/image.jpg`.
4. No caller, query parameter, environment image URL, or live profile can select a
   different device path.

### 2.3 Components

| Component | Responsibility |
|---|---|
| Host validator | Accept a host or host:port only; reject scheme, credentials, path, query, fragment, whitespace, and invalid port. |
| Snapshot policy | Normalize existing measurement interval to 3-10 seconds. |
| Live policy | Compute the maximum safe image request rate from remaining background budget, capped at 4 FPS. |
| Shared image cache | Hold one immutable latest validated JPEG and capture metadata. |
| Shared refresh task | Coalesce snapshot/live/multi-client misses into one upstream GET. |
| FastAPI route helper | Return consistent no-store JPEG/error contracts with a profile header. |
| Frontend refresh policy | Prefer server-provided `image_refresh_interval`; fall back to the legacy interval for compatibility. |
| View model | Remain single in-flight, completion-driven, visibility-aware, and bounded-backoff. |
| Observability | Report both application paths and aggregate/per-profile demand without network identifiers; operator settings prefer live-route statistics with snapshot fallback. |

## 3. Request Budget

### 3.1 Inputs

```text
target_total_rate = 6.0 requests/s
desired_live_rate = 4.0 requests/s
poll_interval = max(0.5, configured SPOT_REFRESH_INTERVAL)
diagnostics_interval = max(10.0, poll_interval)

temperature_rate = configured(SPOT_URL) ? 1 / poll_interval : 0
internal_rate = configured(SPOT_INTERNAL_TEMPERATURE_URL) ? 1 / poll_interval : 0
diagnostics_rate = configured(SPOT_URL) ? 8 / diagnostics_interval : 0
remaining_rate = target_total_rate - temperature_rate - internal_rate - diagnostics_rate
live_rate = min(desired_live_rate, remaining_rate)
live_ttl = 1 / live_rate
```

The currently supported minimum poll interval guarantees a positive remaining rate. A
defensive lower image rate equal to the snapshot rate is used if future configuration
changes violate that invariant, and diagnostics then report `request_budget_within_target
= false` rather than hiding the problem.

### 3.2 Expected Values

| Configuration | Non-image rate | Live rate | Live TTL | Total |
|---|---:|---:|---:|---:|
| Default 3 s, all reads configured | 1.4667/s | 4.0000/s | 0.2500 s | 5.4667/s |
| Fastest 0.5 s, all reads configured | 4.8000/s | 1.2000/s | 0.8333 s | 6.0000/s |
| Image only | 0/s | 4.0000/s | 0.2500 s | 4.0000/s |

The 75-second minimum reuse interval is enforced with a two-second safety margin.
The guarded pool's theoretical steady-state ceiling is therefore 768 / 77 = about
9.97 leases/s.
The six-request/s application budget therefore retains capacity for bind collision
recovery and infrequent operator control requests.

## 4. State and Concurrency

### 4.1 Image Profiles

```python
SpotImageProfile = Literal["snapshot", "operator_live"]
```

`fetch_image_async(profile="snapshot")` remains the default for existing internal and
test callers. Unknown profiles fail before network work.

### 4.2 Freshness

```text
age = monotonic_now - captured_at_monotonic
fresh(snapshot) = 0 <= age < snapshot_ttl
fresh(operator_live) = 0 <= age < live_ttl
```

A live frame is automatically fresh for a snapshot caller. A snapshot-created frame may
be fresh for the first live caller only until the shorter live TTL expires. Both profiles
check the same expected upstream URL, so a host change invalidates the old frame.

### 4.3 Single-Flight

The existing lock/task algorithm remains:

1. Check shared cache using the caller profile.
2. Acquire `_img_fetch_lock`, then repeat the profile-specific check.
3. Join the existing refresh task or create exactly one new task.
4. Release the lock before network I/O.
5. Await the task through `asyncio.shield`.
6. Publish one validated cache entry and enqueue evidence at most once.

Snapshot and live callers can join the same task. No image-profile lock is added, and
the fixed lock order remains `_img_fetch_lock` before awaiting work that later acquires
`_spot_device_request_lock`.

### 4.4 Failure and Retry

- Expired bytes are never returned as a successful stale frame.
- A shared upstream failure is recorded once and propagated to all waiters.
- The frontend retains retry delays of 500, 1000, and 2000 ms, then requires manual
  retry/reconnect.
- Normal refresh and retry timers remain mutually exclusive.
- A hidden document cancels the normal timer and starts one immediate fetch only after
  visibility returns.
- Backend cache and single-flight prevent multiple browser windows from multiplying
  successful upstream cadence.

## 5. API Specification

### 5.1 `GET /api/spot/image.jpg`

- Purpose: snapshot/evidence-compatible application bridge.
- Profile: `snapshot`.
- Effective freshness: 3-10 seconds.
- Response: validated `image/jpeg`, no-store headers, existing capture/source/latency/age
  headers, plus `X-Spot-Image-Profile: snapshot`.

### 5.2 `GET /api/spot/live_image.jpg`

- Purpose: operator display.
- Profile: `operator_live`.
- Effective freshness: dynamically budgeted, up to 4 FPS.
- Upstream: always the same official `/image.jpg` device resource.
- Response/error contract: identical to the snapshot route, with
  `X-Spot-Image-Profile: operator_live`.

The removed extensionless `/api/spot/live_image` and `/api/spot/proxy_image` routes
remain 404 to prevent old unrestricted clients from silently returning.

### 5.3 `GET /api/spot/config`

Additive response fields:

```json
{
  "image_url": "/api/spot/live_image.jpg",
  "snapshot_image_url": "/api/spot/image.jpg",
  "image_refresh_interval": 0.25,
  "refresh_interval": 3.0
}
```

`image_url` continues to mean the URL rendered by the operator UI.
`snapshot_image_url` exposes the slower application bridge for compatible tooling.
`refresh_interval` retains the measurement polling setting.
`image_refresh_interval` is a server-derived effective value, not caller-controlled.

### 5.4 Observability

- Include both image routes in polling path summaries.
- Record success/failure against the actual application path.
- Add aggregate diagnostics:
  - `snapshot_image_refresh_interval_sec_effective`
  - `live_image_refresh_interval_sec_effective`
  - `live_image_max_fps_effective`
  - `image_snapshot_downstream_request_count`
  - `image_live_downstream_request_count`
- Retain shared upstream/cache/single-flight and source-port lifecycle counters.
- Never expose raw IP, URL, source port, credentials, or JPEG bytes.

## 6. Frontend Design

### 6.1 Route and Type Compatibility

- `SpotConfig.image_refresh_interval` and `snapshot_image_url` are optional in the
  TypeScript interface so an older backend response remains usable during rolling local
  development.
- The bundled service maps the visible image request to `/api/spot/live_image.jpg`.
- The normal timer uses `image_refresh_interval` when finite and positive; otherwise it
  falls back to the existing `refresh_interval` normalization.

### 6.2 Scheduling

The timer starts after the browser fires `<img onLoad>`, not when HTTP begins. This
retains manufacturer completion ordering and ensures slow network/decode time lowers,
rather than raises, upstream demand. `250 ms` is the smallest accepted server-derived
interval; legacy fallback remains clamped to 1-10 seconds.

## 7. Security

- URL construction is server-owned and accepts no request-supplied target.
- Host validation rejects path/query injection and credentials before URL creation.
- Redirect validation, response byte limits, timeouts, device serialization, guarded
  source ports, payload checks, and no-store response headers remain.
- JPEG acceptance requires both marker framing and a successful Pillow JPEG decoder
  verification; marker-wrapped arbitrary bytes fail closed.
- Errors expose bounded codes/metadata only; network locators remain excluded from
  diagnostics and user-facing responses.
- The route is read-only; authorization/listening/firewall scope is unchanged.

## 8. Implementation Plan

### 8.1 Files

- `backend/FacilityData/drivers/spot_api.py`
- `backend/app.py`
- `backend/Observability/service.py`
- `backend/API_DOCUMENTATION.md`
- `backend/tests/test_spot_api.py`
- `backend/tests/test_observability_service.py`
- `frontend/src/shared/types.ts`
- `frontend/src/domains/FacilityData/api/spotService.mapper.ts`
- `frontend/src/domains/FacilityData/hooks/useSpotViewModel.ts`
- `frontend/src/domains/FacilityData/utils/spotImageRefreshPolicy.pure.ts`
- `frontend/src/domains/Configuration/components/SettingsModal/SettingsModal.tsx`
- `frontend/src/domains/Configuration/components/SettingsModal/settingsModalHelpers.ts`
- relevant frontend tests
- `scripts/qa_spot_realtime_image_performance.py`
- `scripts/qa_spot_image_server.ps1`

### 8.2 Order

1. Add backend profile and budget helpers with unit tests.
2. Make cache freshness profile-aware without duplicating state.
3. Add the live application route through a shared response helper.
4. Add per-route/per-profile observability.
5. Move the frontend display endpoint and cadence to the server-derived live profile.
6. Add and run the localhost HTTP/1.0-close performance harness.
7. Run focused and full validation, then PDCA gap analysis and report.

## 9. Test Plan

### 9.1 Backend Unit and Integration

- Canonical path is `/image.jpg` for IPv4, DNS, and optional test port hosts.
- Scheme/path/query/fragment/credential/whitespace values fail before network I/O.
- Snapshot TTL remains 3-10 seconds.
- Default live TTL is 250 ms and fastest-poll live TTL is approximately 833 ms.
- The total theoretical budget is <=6/s in both configurations.
- Snapshot/live concurrent misses call upstream once and receive shared bytes.
- Live cache expires earlier than snapshot cache.
- Removed extensionless routes remain 404; both `.jpg` routes return expected profile.
- Route errors and observability are attributed to the actual path.

### 9.2 Frontend

- Mapper returns `/api/spot/live_image.jpg`.
- Server-derived 250 ms cadence is accepted.
- Missing live cadence falls back to the legacy 1-10-second policy.
- Display completion schedules exactly one request.
- Hidden state schedules none; visibility resume schedules one.
- Retry remains 500/1000/2000 ms and does not overlap normal refresh.
- Settings observability prefers `/api/spot/live_image.jpg` statistics and falls back to
  the snapshot path for an older backend.

### 9.3 Performance Harness

The harness starts a loopback HTTP/1.0 server that closes each response, serves a real
JPEG, and records request timestamps/concurrency. It uses the real backend guarded
transport and live cache policy for ten seconds. Pass conditions:

- displayed/downstream cadence >=3.5/s under default non-image configuration;
- upstream cadence <=4.0/s plus one startup-boundary allowance;
- zero HTTP, payload, timeout, pool exhaustion, reuse, and overlap failures;
- source-port policy active on Windows and no raw source-port output;
- cache/single-flight counters internally consistent.

This is real localhost network and transport performance evidence, not physical-device
or production approval.

## 10. Rollback and Promotion Gate

No migration is introduced. Reverting the code restores the three-second operator
route behavior. Production promotion still requires an identity-bound installer,
actual SPOT device smoke, error-queue comparison, source-port/pool checks, at least a
15-minute observation, and the established 120-minute canary. Local success cannot
inherit earlier field evidence because the source commit changes.

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-08-21 | Initial approved design. |
| 1.0.1 | 2026-08-21 | Recorded decoder validation and local implementation completion. |
| 1.0.2 | 2026-08-21 | Aligned settings observability and packaged field QA. |
