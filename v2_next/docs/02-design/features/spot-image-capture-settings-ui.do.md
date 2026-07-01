# SPOT Image Capture Settings UI Do

> Date: 2026-07-01 | Feature: `spot-image-capture-settings-ui`

## Implementation Checklist

- Add backend update model for nested `spot.image_capture`.
- Add backend snapshot and update handling for existing `[SPOT] imagecapture*` keys.
- Keep `DEFAULT_SPOT_IMAGE_CAPTURE_ENABLED=False`.
- Change default mode to `off`.
- Add frontend snapshot/form/payload fields.
- Add Settings > SPOT camera evidence capture controls.
- Add short disk/image retention warning.
- Add frontend helper tests and backend configuration service tests.
- Run typecheck, lint, SettingsModal tests, backend unittest, and health.

## Non-Changes

- `backend/FacilityData/spot_image_fact.py` writer logic remains unchanged.
- SPOT live/proxy upstream fetch logic remains unchanged.
- Retention cleanup policy remains unchanged.
