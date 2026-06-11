# Completion Report: spot-live-image

> Date: 2026-06-11 | Match Rate: 92%

## Summary

Added a dedicated SPOT live image endpoint and a frontend `<img>` reload loop for smooth camera display while preserving the existing snapshot/proxy/alert path.

## Completed Items

- Backend configuration supports `SPOT_LIVE_IMAGE_URL` and `[SPOT] liveimageurl`.
- `GET /api/spot/live_image` returns direct `image/jpeg` bytes with no-store cache headers.
- Live fetch uses server-side configured URLs only, validates image payloads, rejects HTML, and applies live-only backoff.
- Live fetch state is isolated from `_img_cache` and delayed alert metadata.
- `CameraWidget` uses the live endpoint for the visible image and mutates DOM `src` from `onLoad`/`onError`.
- Existing proxy Blob lifecycle is preserved through a hidden image for load/error handling and Blob revocation.
- API and PDCA docs were updated.

## Validation

- `backend\.venv\Scripts\python.exe -m unittest backend.tests.test_spot_api`
- `npm --prefix frontend run test -- src/domains/FacilityData/components/widgets/CameraWidget.focusDirection.test.tsx`
- `npm --prefix frontend run test -- src/domains/FacilityData/hooks/useSpotViewModel.integration.test.ts`
- `npm --prefix frontend run typecheck`
- `npm run health:backend:test`
- `npm run health:backend:typecheck`

## Residual Risk

- Physical SPOT/browser QA was not executed in this environment.
- Multiple open dashboard clients can still generate meaningful device load; the backend shares frames for 50ms and applies backoff, but production should monitor request rate after rollout.
- Switching live upstream to `/newjpeg.jpg` is operational configuration and should be verified on the target network.

## Rollback

Remove `SPOT_LIVE_IMAGE_URL` or `[SPOT] liveimageurl` customization to fall back to `SPOT_IMAGE_URL`/`image.jpg`. If needed, revert the `CameraWidget` live-image branch to display the existing proxy Blob URL only.
