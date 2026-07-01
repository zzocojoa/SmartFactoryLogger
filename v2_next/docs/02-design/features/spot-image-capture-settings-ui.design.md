# SPOT Image Capture Settings UI Design

> Date: 2026-07-01 | Feature: `spot-image-capture-settings-ui`

## Backend Contract

`/api/config` exposes `values.spot.image_capture`:

```json
{
  "enabled": false,
  "mode": "off",
  "path": "spot_images",
  "min_interval_sec": 1.0,
  "max_bytes": 2000000,
  "retention_days": 7,
  "link_to_observation": true
}
```

`ConfigUpdate.spot.image_capture` writes the same values to `[SPOT]` config.ini keys:

- `imagecaptureenabled`
- `imagecapturemode`
- `imagecapturepath`
- `imagecaptureminintervalsec`
- `imagecapturemaxbytes`
- `imagecaptureretentiondays`
- `imagecapturelinktoobservation`

When disabled, the snapshot and save path normalize mode to `off`.

## Frontend Design

Settings > SPOT camera adds an advanced "Evidence image capture" block above the live preview.

Controls:

- Toggle: enabled/off.
- Select: off, event, interval, all.
- Text input: relative path under the log directory.
- Numeric inputs: min interval seconds, max bytes, retention days.
- Toggle: link captured image metadata to observation rows.

Validation:

- Enabled capture cannot use `off` mode.
- Path must be relative and cannot contain `.` or `..` segments.
- Min interval and retention days must be zero or greater.
- Max bytes must be positive.

## Risk Controls

- Default is disabled/off.
- Warning text is visible next to the controls.
- The UI does not expose raw SPOT URLs or captured images.
- Writer and retention cleanup are not modified.
