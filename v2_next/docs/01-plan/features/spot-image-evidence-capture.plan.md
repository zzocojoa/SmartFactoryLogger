# SPOT Image Evidence Capture Plan

> Date: 2026-06-30 | Level: Dynamic | Feature: `spot-image-evidence-capture`

## Overview

SPOT camera image bytes are already fetched, validated, proxied, and cached in memory. This feature adds an opt-in evidence capture path that persists selected fresh upstream SPOT images and records a sidecar `spot_image_fact.csv`.

The image is diagnostic evidence. It must not be treated as temperature correction data.

## Business Goal

Operators and investigators need evidence for why SPOT temperature is unavailable or under-range, especially after die changes, setup, actuator movement, low signal, or target alignment problems. Persisted images should help answer whether SPOT was viewing the target, an empty background, a shifted hotspot, or an obstructed view.

## Scope In

- Add default-off SPOT image capture settings.
- Capture only fresh upstream images, not repeated cache/proxy responses.
- Use a bounded queue and writer thread so file I/O cannot block SPOT polling.
- Store image bytes under `<LOG_PATH>/spot_images/YYYY/MM/DD/`.
- Append metadata to `<LOG_PATH>/spot_image_fact.csv`.
- Link each fact to the nearest SPOT observation snapshot when available.
- Record path, hash, size, MIME, dimensions when safely detectable, source URL hash, and nearest diagnostic fields.
- Add backend tests for capture gating, queue isolation, cache non-duplication, and fact output.

## Scope Out

- No base64 image data in realtime CSV.
- No frontend manual review gallery in this phase.
- No image-based temperature correction.
- No actuator control automation.
- No ML/training input from image evidence.
- No external URL or IP exposure in new headers.

## Functional Requirements

1. `SPOT_IMAGE_CAPTURE_ENABLED` defaults to `False`.
2. Supported modes: `off`, `event`, `interval`, `all`.
3. Event mode captures under-range, over-range, source error, stale/not-received, low signal, target-out-of-FOV, and actuator scan/move evidence.
4. Capture must happen only after a fresh upstream image fetch succeeds.
5. Cache hits and stale-cache fallback must not create duplicate captures.
6. Captures must respect min interval and max bytes.
7. Writer failure must increment failure counters and must not raise into polling.
8. Fact output must not store the raw image URL. Store `spot_image_source_url_hash`.

## Non-Functional Requirements

- Default-off and backward compatible.
- Bounded memory through a fixed-size queue.
- Atomic file writes using temp file then replace.
- Retention cleanup best-effort and isolated.
- Fact schema stable and header guarded.
- Tests must be included in `npm run health`.

## Success Criteria

- Fresh upstream image success can enqueue and persist one image and one fact.
- Shared-frame/live cache hit does not duplicate fact rows.
- Event mode captures under-range evidence and skips valid-temperature evidence.
- Oversized image bytes are dropped before enqueue.
- Writer failure does not break `fetch_live_image_async`.
- `python -m unittest backend.tests.test_spot_api` passes.
- `npm run health` passes.

## Risks

- Disk growth if capture is enabled with `all`.
- Sensitive environment metadata in paths.
- Poll loop interference if writes are synchronous.
- False confidence if users assume images improve temperature values.

## Mitigations

- Default off.
- Min interval, max bytes, retention days, bounded queue.
- Store URL hash, not URL.
- Queue writer thread isolates disk I/O.
- PDCA docs and fact schema state that image evidence is diagnostic only.
