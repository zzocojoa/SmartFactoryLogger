# spot-live-image - Design Document

> Version: 1.0.0 | Date: 2026-06-11 | Status: Draft
> Level: Dynamic

## 1. Architecture

The feature adds a live display path beside the existing snapshot proxy path.

Existing path:
`SPOT_IMAGE_URL -> fetch_image_async -> /api/spot/proxy_image -> Blob validation -> dashboard alert metadata`

New path:
`SPOT_LIVE_IMAGE_URL | [SPOT] liveimageurl | SPOT_IMAGE_URL | http://{SPOT_IP}/image.jpg -> fetch_live_image_async -> /api/spot/live_image -> <img src reload loop>`

The live path does not read or write `_img_cache`, temperature metadata, or proxy diagnostics used by delayed alert decisions.

## 2. API Specification

### GET /api/spot/live_image

- Description: Return the current SPOT camera image for direct browser rendering.
- Auth: Same local backend trust boundary as existing SPOT endpoints.
- Request: No body. Query parameters are ignored except cache-busting values such as `t`.
- Response 200:
  - Body: image bytes.
  - Media type: `image/jpeg`.
  - Headers:
    - `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`
    - `Pragma: no-cache`
    - `Expires: 0`
    - `X-Spot-Live-Image-At`
    - `X-Spot-Live-Image-Source`
- Errors:
  - `404 config-missing` when no usable live URL is configured.
  - `503 live-backoff-active` while live retry backoff is active.
  - `502 invalid-image-html` or `invalid-image-payload` for non-image upstream payloads.
  - `502 upstream-*` for upstream request failures.

## 3. Configuration

Priority order:

1. `SPOT_LIVE_IMAGE_URL`
2. `[SPOT] liveimageurl`
3. `SPOT_IMAGE_URL`
4. `http://{SPOT_IP}/image.jpg`

Operators may set `SPOT_LIVE_IMAGE_URL=http://10.1.10.50/newjpeg.jpg` when the device-specific smoother JPEG endpoint is desired. `image.ssi` is not valid because it returns HTML.

## 4. UI Integration

`SpotConfig` includes `live_image_url`. `CameraWidget` uses that endpoint for the visible image, mutates the image DOM `src` after load with a 35ms delay, and retries after image error with a conservative delay. The existing proxy Blob image is kept as a hidden lifecycle image so snapshot load/error handlers and Blob revocation still run without becoming the live display path.

The existing proxy snapshot polling remains active for metadata and delayed alert behavior, but the visible camera image uses the live URL.

## 5. Test Plan

- Backend unit tests:
  - live URL fallback order.
  - live fetch rejects HTML payload.
  - live fetch does not update `_img_cache`.
- Frontend tests:
  - camera image points to `/api/spot/live_image`.
  - `onLoad` schedules a fresh URL with cache-busting query.
  - existing focus and internal temperature rendering still work.
- Validation:
  - `npm run typecheck`
  - focused frontend tests
  - backend SPOT tests
