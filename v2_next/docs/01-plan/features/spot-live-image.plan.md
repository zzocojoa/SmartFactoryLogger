# spot-live-image - Plan Document

> Version: 1.0.0 | Date: 2026-06-11 | Status: Draft
> Level: Dynamic

## 1. Overview

### 1.1 Purpose
Add a live SPOT camera image path that can be used directly by a browser `<img>` element without changing the existing snapshot, alert, cache, and validation flow.

### 1.2 Background
The current `/api/spot/proxy_image` path is optimized for validated snapshots and status metadata. A smooth camera view needs a separate endpoint and a frontend image reload loop so React state does not store a Blob for every frame.

## 2. Goals

### 2.1 Primary Goals
- [ ] Add `GET /api/spot/live_image` for direct image rendering.
- [ ] Keep `/api/spot/proxy_image` behavior and delayed alert logic unchanged.
- [ ] Support dedicated live upstream configuration with safe fallback to the configured SPOT image URL.
- [ ] Use `<img src>` refresh through `onLoad` and conservative `onError` retry.

### 2.2 Non-Goals
- Replace existing snapshot cache or proxy validation.
- Proxy arbitrary user-provided URLs.
- Add WebSocket, MJPEG streaming, or video transcoding.

## 3. Scope

### 3.1 In Scope
- Backend configuration: `SPOT_LIVE_IMAGE_URL` and `[SPOT] liveimageurl`.
- Backend helper: live image fetch with timeout, single-flight, payload validation, and failure backoff.
- FastAPI endpoint: `GET /api/spot/live_image`.
- Frontend config type and camera widget live image loop.
- Focused unit/integration tests.

### 3.2 Out of Scope
- Device firmware changes.
- Authentication model changes.
- Multi-client global frame fanout beyond a lightweight single-flight guard.

## 4. Success Criteria

- [ ] Existing `/api/spot/proxy_image` fetch path still returns validated snapshot data.
- [ ] Existing SPOT stale/delayed alert state continues to use proxy metadata.
- [ ] New live endpoint returns `image/jpeg` with `Cache-Control: no-store`.
- [ ] HTML upstream responses such as `image.ssi` are rejected.
- [ ] Frontend live view uses URL reloads, not per-frame Blob URLs.

## 5. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| High request rate overloads SPOT device | Medium | Medium | Single-flight lock, timeout, and frontend error backoff |
| Live fetch pollutes snapshot state | High | Low | Separate live helper state and no writes to `_img_cache` |
| Arbitrary URL proxy risk | High | Low | Only server-side configured URLs are accepted |
| `image.ssi` HTML treated as image | Medium | Low | Reuse image payload validation |

## 6. References

- `backend/FacilityData/drivers/spot_api.py`
- `backend/app.py`
- `frontend/src/domains/FacilityData/hooks/useSpotViewModel.ts`
- `frontend/src/domains/FacilityData/components/widgets/CameraWidget.tsx`
