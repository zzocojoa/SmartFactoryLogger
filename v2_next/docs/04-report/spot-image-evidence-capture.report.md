# SPOT Image Evidence Capture Report

> Date: 2026-06-30 | Feature: `spot-image-evidence-capture`

## Summary

SPOT image evidence capture has been implemented as a default-off backend feature.

The feature saves selected fresh upstream SPOT images to local evidence storage and writes `spot_image_fact.csv` metadata for later diagnosis. It does not modify SPOT temperature values and does not use image bytes for temperature correction.

## What Changed

- Added SPOT image capture settings.
- Added `spot_image_fact.csv` writer and image file writer.
- Added a bounded queue and writer thread.
- Connected capture to fresh upstream success from proxy, prefetch, and live image fetch paths.
- Added event-mode gating for under-range, over-range, source error, setup/changeover, low signal, actuator, and target-out-of-FOV evidence.
- Added capture health counters through SPOT config diagnostics.
- Limited retention cleanup to managed `spotimg_*` evidence files so unrelated files under the capture root are preserved.
- Added regression tests for write, gate, duplicate prevention, oversize drop, writer failure isolation, and retention cleanup file preservation.

## Operational Defaults

```text
SPOT_IMAGE_CAPTURE_ENABLED = False
SPOT_IMAGE_CAPTURE_MODE = off
SPOT_IMAGE_CAPTURE_PATH = spot_images
SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC = 1.0
SPOT_IMAGE_CAPTURE_RETENTION_DAYS = 7
SPOT_IMAGE_CAPTURE_MAX_BYTES = 2000000
SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION = True
```

Default-off is intentional. Production should enable this only when evidence capture is required.

## Validation

```text
.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_spot_api
npm run health
```

Results:

- Targeted SPOT backend tests: pass, 82 tests
- Full health: pass
- Frontend checks: pass, 24 files / 191 tests
- Backend checks: pass, 357 tests
- Ruff: pass
- Mypy: pass

## Rollback

Revert the feature commit or disable capture with:

```text
SPOT_IMAGE_CAPTURE_ENABLED=false
```

Because the feature is default-off, disabling the setting stops new image/fact writes without changing existing log files.

## Remaining Risk

- Disk use can grow if capture is enabled too broadly. Retention cleanup does not manage unrelated operator files in the capture root.
- Image evidence may contain production visual context and should be treated as operational evidence.
- Image evidence improves under-range diagnosis, not temperature accuracy.
- Production validation should confirm fact row quality during real die change and setup phases.
