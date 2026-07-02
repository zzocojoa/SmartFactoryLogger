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
- Runtime writer settings are re-read before each queued write. A saved log path,
  capture path, retention, or SPOT refresh change should apply to the next capture
  without restarting the app.
- Replayed or retried writes with the same generated capture id reuse the existing
  fact row instead of appending a duplicate `spot_image_fact.csv` entry.
- After diagnostics, save Enabled off and Mode off.

## Link Semantics

Image links are operational correlation, not an atomic same-cycle guarantee.
The writer snapshots the latest available SPOT observation when an image capture
is queued, then records the observation key and nearest fields in
`spot_image_fact.csv`. CSV v2.4 rows copy the latest image fact into the realtime
`*_nearest` fields only when the fact's linked observation key matches the row's
`spot_observation_key`.

Current policy keeps realtime CSV image links as best-effort diagnostic pointers.
Guaranteed audit linkage should be implemented as a separate design, starting
with an offline join over settled realtime CSV and `spot_image_fact.csv`
artifacts. See
`docs/03-analysis/spot-realtime-image-linkage-decision.md`.

`spot_image_link_status` values mean:

- `fresh`: linked observation age was within the stale threshold.
- `stale`: linked observation existed, but was older than the stale threshold.
- `missing_observation`: no observation snapshot was available.
- `unlinked_observation`: the snapshot could not produce a valid observation key.
- `unknown_age`: age could not be calculated.
- `clock_anomaly`: calculated age was negative.

The stale threshold follows the runtime SPOT refresh policy
(`SPOT_REFRESH_INTERVAL * 3`). Helper defaults of `9000` ms are legacy fallbacks
for tests or callers that do not pass runtime configuration; do not treat that
fallback as a separate production calibration.

Event-mode capture triggers and temperature cause evidence are separate policies.
`event` mode may queue an image for under/over-range status, process phase,
diagnostic evidence, alarm bit 4, or low `signalpc`. A temperature
`low_signal_candidate` still requires `alarm_low_signal` or `signal_below_threshold`
evidence. A low `signalpc` value by itself, without a configured
threshold/comparator and enabled low-signal alarm policy, is retained as diagnostic
context, not cause proof.

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
`scripts/validate_csv_v2_shadow.py` validates the manifest shape, fact row count,
fact SHA-256, safe relative image paths, and link status values.

For an on-machine validation against the original log directory, do not pass a
fact override. The validator reads `spot_image_fact_manifest.fact_path` and
requires the manifest row count and SHA-256 to match the current fact file.

For a portable smoke bundle copied while the logger is still running, include
the bundled fact file explicitly:

```powershell
py -3 scripts\validate_csv_v2_shadow.py `
  --v2 Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv `
  --metadata Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.metadata.json `
  --spot-observation-fact spot_observation_fact.csv `
  --spot-image-fact spot_image_fact.csv
```

`--spot-image-fact` validates the supplied bundle file directly and reports a
sanitized `spot_image_fact_*` summary using only file names, row counts, hashes,
and match booleans. A copied bundle can legitimately report
`spot_image_fact_row_count_match=false` and `spot_image_fact_sha256_match=false`
when the sidecar metadata was written before the active fact file finished
appending. The validator still checks the supplied fact's required columns,
safe relative image paths, link statuses, and SHA-256 text fields.

CSV v2.4 rows also expose the latest matching image fact link when the capture
fact references the same `spot_observation_key` as the realtime row:

```text
spot_image_capture_id_nearest
spot_image_path_nearest
spot_image_link_status_nearest
spot_image_link_age_ms_nearest
```

These fields are intentionally blank when no image fact has been written yet, or
when the latest image fact belongs to a different SPOT observation. `spot_image_path_nearest`
is a relative path under the log directory; raw camera URLs are not written to
the realtime CSV.

Startup, missing-completion, and non-positive poll sequence snapshots should not
produce a linked observation key; those rows are intentionally unlinked rather
than operational evidence.
