# SPOT Image Evidence Capture Do

> Date: 2026-06-30 | Design: docs/02-design/features/spot-image-evidence-capture.design.md

## Implementation Checklist

- [x] Add default-off config values.
- [x] Add `spot_image_fact.py` writer module.
- [x] Add bounded queue and writer thread in `spot_api.py`.
- [x] Enqueue only on fresh upstream success.
- [x] Link nearest SPOT observation snapshot when configured.
- [x] Add tests for fact write, gate, duplicate prevention, oversize drop, failure isolation.
- [x] Run targeted backend tests and `npm run health`.

## Implementation Result

- Config is default-off and supports `off`, `event`, `interval`, and `all`.
- Fresh upstream image success from proxy, live image, and prefetch paths can enqueue capture.
- Cache serves, shared-frame serves, and stale-cache fallbacks do not enqueue captures.
- Writer thread appends `spot_image_fact.csv` and writes image files atomically.
- Raw source URL is hashed in the fact file.
- Writer failure increments counters and does not break live image fetch.

## Excluded From This Do

- Frontend manual review gallery.
- Actuator automation.
- Base64 image data in wide CSV.
- Direct temperature value correction from images.
