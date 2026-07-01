# SPOT Image Capture Settings

> Date: 2026-07-01 | Scope: operator configuration

## Default Policy

The safe default is disabled:

```ini
imagecaptureenabled = false
imagecapturemode = off
```

This should remain the normal production setting unless diagnostic evidence is required.

## UI Location

Open Settings > SPOT camera > Evidence image capture.

Available settings:

- Enabled: turns evidence image capture on or off.
- Mode: off, event, interval, or all.
- Path: relative path under the configured log directory.
- Min interval: minimum seconds between queued captures.
- Max bytes: maximum accepted image payload size.
- Retention days: managed evidence image retention window.
- Observation link: writes image metadata linkage to observation facts when available.

## Safety Guidance

- Use `event` for most incident diagnostics.
- Use `all` only for short manual investigations because it can grow disk usage quickly.
- Keep path relative, for example `spot_images\incident_20260701`.
- UI and `/api/config` saves reject absolute, rooted, or parent-traversal paths.
- After diagnostics, save Enabled off and Mode off.

## Verification

Check runtime policy:

```powershell
$config = (Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/spot/config" -UseBasicParsing).Content | ConvertFrom-Json
$config.image_capture
```

Expected normal state:

```text
enabled: false
mode: off
```

When evidence capture is enabled for a short diagnostic run, `spot_image_fact.csv`
must include `spot_image_link_age_ms` and `spot_image_link_status`. The matching
CSV v2 sidecar should include `spot_image_fact_manifest` with the fact path,
capture root, row count, SHA-256, writer counters, and last write time.

Startup, missing-completion, and non-positive poll sequence snapshots should not
produce a linked observation key; those rows are intentionally unlinked rather
than operational evidence.
