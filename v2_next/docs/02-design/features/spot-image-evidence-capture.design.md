# SPOT Image Evidence Capture Design

> Date: 2026-06-30 | Level: Dynamic | Plan: docs/01-plan/features/spot-image-evidence-capture.plan.md

## Architecture

Existing flow:

```text
SPOT image HTTP GET -> validation -> memory cache -> /api/spot/proxy_image or /api/spot/live_image
```

New flow:

```text
fresh upstream image success
  -> capture gate
  -> bounded in-memory queue
  -> writer thread
  -> image file + spot_image_fact.csv
```

The writer is intentionally outside the async polling path. Failure is counted and logged but never raises into SPOT polling or live image responses.

## Capture Sources

- `proxy_upstream`: first proxy image fetch when cache is empty.
- `prefetch_upstream`: background image prefetch loop.
- `live_upstream`: `/api/spot/live_image` fresh upstream fetch.

Cache sources excluded:

- `_img_cache` cache serve.
- `_live_img_cache` shared-frame serve.
- `stale-cache` fallback.

## Configuration

All values are read from env first, then `config.ini`.

```python
SPOT_IMAGE_CAPTURE_ENABLED = False
SPOT_IMAGE_CAPTURE_MODE = "event"  # off | event | interval | all
SPOT_IMAGE_CAPTURE_PATH = "spot_images"
SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC = 1.0
SPOT_IMAGE_CAPTURE_RETENTION_DAYS = 7
SPOT_IMAGE_CAPTURE_MAX_BYTES = 2_000_000
SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION = True
```

Relative capture paths resolve under `config.LOG_PATH`.

## Fact Schema

Output: `<LOG_PATH>/spot_image_fact.csv`

Columns:

```text
spot_image_capture_id
spot_image_captured_at
spot_image_source_url_hash
spot_image_path
spot_image_sha256
spot_image_size_bytes
spot_image_mime
spot_image_width
spot_image_height
spot_image_status
spot_image_source
spot_image_age_ms
spot_image_linked_observation_key
spot_service_instance_id
spot_poll_seq_nearest
sample_seq_nearest
timestamp_utc_nearest
temperature_output_status_nearest
temperature_unavailable_reason_nearest
temperature_under_range_cause_candidate_nearest
process_phase_candidate_nearest
signalpc_nearest
alarmstatus_nearest
d1temperature_nearest
d2temperature_nearest
e1out_nearest
e2out_nearest
actuator_position_nearest
focus_mm
low_signal_threshold_pc
peak_picker_enabled
```

`sample_seq_nearest` and `process_phase_candidate_nearest` remain blank in P0 because image capture lives in the SPOT fetch layer, not the CSV row writer. Observation linkage uses `spot_service_instance_id:spot_poll_seq`.

## Event Gate

Event mode captures when the nearest SPOT snapshot indicates one of:

- `spot_device_status_code in {temperature_under_range, temperature_over_range}`
- `spot_raw_validity in {invalid_sentinel, out_of_range, not_received, empty_body, parse_error}`
- `spot_poll_status in {timeout, connection_error, http_error, config_missing}`
- diagnostic evidence contains actuator movement, low signal, target out of FOV, or detector below range
- `signalpc` is below configured threshold

## Security

- Do not store raw source URL in the fact file.
- Do not add new response headers with camera IP or path.
- Image files remain local evidence under the configured log directory.

## Tests

- Capture writer creates image and fact row.
- Event gate captures under-range and skips normal valid temperature.
- Live upstream success persists one fact.
- Shared-frame cache hit does not persist duplicate fact.
- Oversized images are dropped.
- Writer failure is isolated from `fetch_live_image_async`.
