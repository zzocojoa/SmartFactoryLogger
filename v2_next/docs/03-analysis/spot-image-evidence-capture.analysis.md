# SPOT Image Evidence Capture Analysis

> Date: 2026-06-30 | Feature: `spot-image-evidence-capture`

## Result

P0 implementation is complete.

SPOT image capture is now an opt-in evidence path. It stores selected fresh upstream image bytes and writes a sidecar fact row for correlation with the nearest SPOT temperature observation.

This does not change temperature calculation. Images are stored only to explain why temperature was unavailable, under-range, over-range, stale, or otherwise suspicious.

## Evidence

- `SPOT_IMAGE_CAPTURE_ENABLED` defaults to `False`.
- Capture modes are `off`, `event`, `interval`, and `all`.
- Capture is attached only to fresh upstream success paths:
  - `proxy_upstream`
  - `prefetch_upstream`
  - `live_upstream`
- Excluded paths:
  - memory cache response
  - live shared-frame response
  - stale-cache fallback response
- Fact output:
  - `<LOG_PATH>/spot_image_fact.csv`
  - image files under `<LOG_PATH>/spot_images/YYYY/MM/DD/`
- Raw camera URL is not written to fact rows; only SHA-256 hash is stored.

## Validation

- `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_spot_api`
  - Result: pass
  - Backend SPOT tests: 82 tests
- `npm run health`
  - Result: pass
  - Frontend typecheck/lint/test: pass, 24 files / 191 tests
  - Backend ruff/mypy/unittest: pass, 357 tests

## Risk Analysis

### Disk Growth

Risk remains if operators enable `all` mode or set a very small interval.

Mitigation:

- default off
- bounded queue
- max bytes
- min interval
- retention cleanup

### Polling Interference

The writer runs in a separate thread. Queue/write failure is counted and logged without raising into SPOT polling or live image fetch.

### Sensitive Data

Fact rows store a URL hash rather than the raw URL. Image paths are relative evidence paths rather than full local filesystem paths.

### Interpretation Risk

Images can support manual diagnosis of target, alignment, focus, and obstruction problems. They must not be treated as a way to recover real temperature from sentinel values such as under-range.

## Remaining Work

- Manual review gallery is not included.
- Actuator scan position correlation remains limited to nearest snapshot fields.
- Production validation must confirm disk growth, writer counters, and fact rows under real setup/changeover conditions.
