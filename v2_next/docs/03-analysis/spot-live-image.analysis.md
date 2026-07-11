# Gap Analysis: spot-live-image

> **SUPERSEDED (2026-07-11):** 이 문서는 과거 구현 이력 보존용입니다. 현재 운영 계약은 `docs/02-design/features/spot-camera-rest-api-conformance.design.md`이며, 장비 `GET /image.jpg`와 앱 `GET /api/spot/image.jpg`만 사용합니다.

> Date: 2026-06-11 | Design: docs/02-design/features/spot-live-image.design.md

## Match Rate: 95%

## Summary

The implementation matches the API, configuration, and UI integration design for the SPOT live image path. Existing `/api/spot/proxy_image` remains in place for snapshot metadata, delayed alert status, cache diagnostics, and Blob lifecycle handling. Development-PC HTTP and browser smoke tests now cover the live endpoint, Blob-free `<img>` reload loop, proxy compatibility, and HTML rejection behavior. The remaining gap is server-PC NSIS installation and physical-device QA against the real SPOT camera.

## Implemented Items

- [x] `GET /api/spot/live_image` exists and returns direct image bytes.
- [x] Live endpoint returns `image/jpeg` with `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`.
- [x] Live endpoint ignores client-provided upstream URLs and only uses server configuration.
- [x] Configuration supports `SPOT_LIVE_IMAGE_URL` and `[SPOT] liveimageurl`.
- [x] Live URL fallback uses `SPOT_IMAGE_URL` and then `http://{SPOT_IP}/image.jpg`.
- [x] HTML/non-image payloads are rejected through existing SPOT image payload validation.
- [x] Live helper has separate cache, failure count, retry backoff, and diagnostics.
- [x] Live helper does not write `_img_cache`, temperature metadata, or proxy state.
- [x] `CameraWidget` renders the visible camera image from `/api/spot/live_image?t=...`.
- [x] `CameraWidget` updates the live image DOM `src` from `onLoad` after 35ms and retries `onError` after 500ms.
- [x] Existing proxy Blob load/error handlers are preserved through a hidden lifecycle image.
- [x] Development-PC FastAPI HTTP smoke verifies `200 image/jpeg`, `Cache-Control: no-store`, existing proxy compatibility, and `image.ssi` rejection.
- [x] Development-PC Playwright smoke verifies the visible camera image uses `/api/spot/live_image?t=...`, not a Blob URL, and refreshes over time.
- [x] Server-PC QA script exists at `scripts/qa_spot_live_server.ps1` to collect direct SPOT, app endpoint, live loop, `/stats` delta, log, and installer-hash evidence after NSIS installation.
- [x] NSIS package resources include the QA script at `resources/qa/qa_spot_live_server.ps1`.

## Missing Items

- [ ] Server-PC NSIS installation and direct SPOT QA against `10.1.10.50` have not been executed in this environment.
- [ ] Browser FPS/visual observation, `/stats` request rate, and post-install log summary remain pending on the server computer.

## Changed Items

- [x] The design initially described `useSpotViewModel` as initializing the live display URL. Implementation keeps `useSpotViewModel` focused on config/proxy metadata and lets `CameraWidget` own the live display loop directly.

## Recommendations

1. On the target network, test both `http://10.1.10.50/image.jpg` and `http://10.1.10.50/newjpeg.jpg` via `SPOT_LIVE_IMAGE_URL`.
2. Watch `/stats` polling summaries after rollout; multiple dashboards can still create high request volume even with 50ms shared-frame protection.
3. Run `scripts/qa_spot_live_server.ps1` after server NSIS installation and attach the JSON artifact, including live loop and `/stats` delta, to the deployment record.

## Next Steps

- [x] Proceed to review because match rate is above 90%.
