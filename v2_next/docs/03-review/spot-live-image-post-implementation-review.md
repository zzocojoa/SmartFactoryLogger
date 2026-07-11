# SPOT Live Image Post-Implementation Review

> **SUPERSEDED (2026-07-11):** 이 문서는 과거 구현 이력 보존용입니다. 현재 운영 계약은 `docs/02-design/features/spot-camera-rest-api-conformance.design.md`이며, 장비 `GET /image.jpg`와 앱 `GET /api/spot/image.jpg`만 사용합니다.

> Date: 2026-06-11
> Scope: Phase 8 review + code-review for `spot-live-image`

## Verdict

Approved for merge/deploy.

The code-level review found no blocking correctness or security issue in the backend implementation. Server-side script QA has now verified direct SPOT access and app endpoint behavior. A desktop-app regression was found and fixed: packaged Electron uses a `file:` frontend origin, so relative live image URLs must resolve against the API base before being assigned to `<img src>`. Final server observation confirmed the Electron desktop app displayed the SPOT camera image for more than 5 minutes with no interruption or delayed alert, and rollback is available.

## Blocking Issues

None found in the current implementation diff.

## Non-Blocking Issues

- Physical SPOT browser QA is not yet proven. Development PC checks to `192.168.0.7:8080` timed out on 2026-06-11.
- Server QA script passed on `DESKTOP-CIIT7LK`, but recent `Spot image fetch failed` and `Spot stale serve` lines were present in `server_stderr.log`.
- Device load remains an operational risk. Backend single-flight, 50ms shared-frame cache, timeout, and backoff reduce pressure, but multiple dashboard clients can still create sustained live image traffic.
- `/newjpeg.jpg` is optional configuration. It should be selected only after server-side smoke test proves stable response and acceptable request rate.
- The earlier 2026-06-11 12:31:59 NSIS installer should not be used for final Electron validation because it can fail to display the live image from the packaged desktop app.

## Review Evidence

### Correctness

- `GET /api/spot/live_image` is separate from `/api/spot/proxy_image`.
- Live helper uses separate `_live_img_cache`, `_live_img_failure_count`, `_live_img_next_retry_at`, and `_live_img_fetch_lock`.
- Existing `_img_cache` remains owned by snapshot/proxy flow.
- Existing `useSpotViewModel` proxy polling remains in place for snapshot metadata and delayed alert status.
- `CameraWidget` uses the configured `live_image_url` for visible display and keeps a hidden proxy lifecycle image for existing load/error handlers.
- `CameraWidget` now resolves relative live image URLs against `API_BASE`, preserving web dashboard behavior while making the packaged Electron `file:` origin call `http://localhost:8000/api/spot/live_image`.

### Security

- No request parameter controls live upstream.
- Upstream URL is server-side config only: `SPOT_LIVE_IMAGE_URL`, `[SPOT] liveimageurl`, `SPOT_IMAGE_URL`, or `http://{SPOT_IP}/image.jpg`.
- HTML payloads such as `image.ssi` are rejected by existing image payload validation.

### Performance

- Frontend does not store live frames as React Blob state.
- Visible live image reload is DOM `img.src` mutation after `onLoad`.
- Default live success delay is 35ms.
- Default error retry delay is 500ms.
- Backend shares a frame for 50ms to limit duplicate upstream hits across near-simultaneous clients.

### Operations

- `/api/spot/live_image` is added to quiet polling paths for observability.
- `/api/spot/config` exposes `live_image_url` and live diagnostics.
- Deployment runbook must verify `/stats` request rate and logs during live view.
- Server artifact from `DESKTOP-CIIT7LK` showed direct SPOT `/image.jpg` and `/newjpeg.jpg` as HTTP 200 `image/jpeg`, while `/image.ssi` remained `text/html`.
- Latest server artifact showed `/api/spot/live_image` HTTP 200 `image/jpeg` with `Cache-Control` containing `no-store`.
- Latest server live loop probe passed for 5 seconds: 69 requests, 69 successes, 0 failures, average 16.1ms.
- Latest server `/stats` delta during the probe showed `total_requests +204`, `error_count +0`, and `total_http_error_count +0`.
- Latest `/stats` window showed `/api/spot/live_image` at 14.367 req/s with 0.0 error rate and `/api/spot/proxy_image` at 1.583 req/s with 0 failures and 0 stale responses.
- Regenerated NSIS installer after the Electron display fix: `A2AB91DD46B57E6E5F71CD9A3AAD2D2437AFEFE84E7B0561588CA43F5A12618A`, last write `2026-06-11 13:08:13 +09:00`.

## Regression Watchlist

- `/api/spot/proxy_image` response and delayed camera alert state.
- `X-Spot-Payload-Rejection` behavior for invalid image payloads.
- Blob URL revocation through hidden lifecycle image.
- Live view error bursts causing repeated `live-backoff-active`.
- Device CPU/network pressure if many clients open the dashboard.

## Merge Readiness

Code is merge/deploy-ready based on the following evidence:

- Local checks remain green.
- The regenerated NSIS installer was validated on the server PC and the Electron desktop app displayed the SPOT live image for more than 5 minutes.
- Server script QA artifact is retained with the release record.
- The 5-minute observation had no interruption and no delayed alert.
- Recent `Spot image fetch failed` and `Spot stale serve` log entries are treated as non-blocking because the current `/stats` window showed zero proxy failures/stale responses and the final Electron observation did not reproduce an operator-visible failure.
- Rollback package/path is verified before production rollout.
