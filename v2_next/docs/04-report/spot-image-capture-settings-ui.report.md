# SPOT Image Capture Settings UI Report

> Date: 2026-07-01 | Feature: `spot-image-capture-settings-ui`

## Summary

Settings > SPOT camera now exposes the existing SPOT evidence image capture policy through a guarded advanced section.

## Defaults

```ini
SPOT_IMAGE_CAPTURE_ENABLED = False
SPOT_IMAGE_CAPTURE_MODE = off
SPOT_IMAGE_CAPTURE_PATH = spot_images
SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC = 1.0
SPOT_IMAGE_CAPTURE_RETENTION_DAYS = 7
SPOT_IMAGE_CAPTURE_MAX_BYTES = 2000000
SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION = True
```

## Operational Notes

- Enabling capture stores field images and increases disk usage.
- `all` mode is the highest-volume setting and should be used only for short diagnostics.
- Retention deletes managed evidence images according to the existing writer policy.
- Rollback is PR revert or saving disabled/off from Settings.

## Validation

- `npm --prefix frontend run typecheck`
- `npm --prefix frontend run lint`
- `npm --prefix frontend run test -- SettingsModal`
- `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_configuration_service`
- `npm run health`
