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

### Health Counters Versus Fact Rows

Do not compare `/api/spot/config` `image_capture.written_count` directly with
`spot_image_fact_manifest.row_count`.

- `spot_image_fact_manifest.row_count` is the actual number of data rows present
  in `spot_image_fact.csv` at metadata or validator time. Use this value, plus
  the manifest SHA-256 checks, for bundle completeness and audit validation.
- `image_capture.written_count` is a runtime worker success counter. It increases
  when the capture worker successfully handles a queued capture event. It is not
  an append-row counter and it resets with the backend process.
- `image_capture.fact_row_count` is the current backend runtime view of actual
  data rows in `spot_image_fact.csv`. It is initialized from the fact file and
  increases only when a new fact row is appended.
- Replayed or retried captures with the same generated capture id reuse the
  existing fact row to prevent duplicate evidence rows. In that path
  `written_count` may increase while `fact_row_count` and manifest `row_count`
  do not.

Operational rule: `failure_count == 0` means the writer has not reported a
runtime write failure. Fact completeness is proven by `row_count`, SHA-256, and
validator results, not by equality with `written_count`. Keep `written_count`
unchanged for existing consumers; use `fact_row_count` when an API consumer needs
the current fact-file row count.

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

### NSIS Server Smoke Closeout Artifact

Every NSIS server smoke that enables image capture must include a sanitized
closeout JSON file in the smoke bundle before the final zip is archived. Use
`server_smoke_closeout_sanitized.json` as the file name. The closeout file is
audit metadata only; it must not contain raw image bytes, camera URLs, secrets,
or full local paths.

Required fields:

```json
{
  "artifact_kind": "server_smoke_bundle",
  "bundle_name": "server_csv_linkage_bundle_YYYYMMDD-HHMMSS",
  "csv_file": "Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv",
  "metadata_file": "Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.metadata.json",
  "observation_fact_file": "spot_observation_fact.csv",
  "image_fact_file": "spot_image_fact.csv",
  "validation_source": "override",
  "validator_command": [
    "py -3 scripts\\validate_csv_v2_shadow.py",
    "--v2",
    "Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv",
    "--metadata",
    "Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.metadata.json",
    "--spot-observation-fact",
    "spot_observation_fact.csv",
    "--spot-image-fact",
    "spot_image_fact.csv"
  ],
  "validator_exit_code": 0,
  "validator_verdict": "PASS",
  "spot_image_fact_row_count_match": false,
  "spot_image_fact_sha256_match": false,
  "v2_rows": 0,
  "realtime_image_link_rows": 0,
  "realtime_image_link_blank_rows": 0,
  "capture_enabled": false,
  "capture_mode": "off",
  "capture_failure_count": 0,
  "redaction": {
    "raw_image_included": false,
    "camera_url_included": false,
    "secret_included": false,
    "full_path_included": false
  }
}
```

For copied server smoke bundles, `validation_source` must be `override`.
Do not record this as a strict metadata-manifest pass. Row/hash match values
must be copied from the validator output exactly as reported.

Run the validator from the repository root, but record only file names in the
closeout JSON:

```powershell
$bundleName = "server_csv_linkage_bundle_YYYYMMDD-HHMMSS"
$bundle = Join-Path $outRoot $bundleName
$csvFile = "Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv"
$metadataFile = "Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.metadata.json"
$obsFile = "spot_observation_fact.csv"
$imageFactFile = "spot_image_fact.csv"

$validatorOutput = & py -3 scripts\validate_csv_v2_shadow.py `
  --v2 (Join-Path $bundle $csvFile) `
  --metadata (Join-Path $bundle $metadataFile) `
  --spot-observation-fact (Join-Path $bundle $obsFile) `
  --spot-image-fact (Join-Path $bundle $imageFactFile) 2>&1
$validatorExitCode = $LASTEXITCODE
$validatorLines = @($validatorOutput | ForEach-Object { [string]$_ })
```

Extract only sanitized summary keys:

```powershell
function Get-ValidatorValue($key) {
  $line = $validatorLines | Where-Object { $_ -like "$key=*" } | Select-Object -First 1
  if ($line) { return $line.Substring($key.Length + 1) }
  return ""
}

$rows = @(Import-Csv -LiteralPath (Join-Path $bundle $csvFile))
$linkRows = @($rows | Where-Object {
  $_.spot_image_capture_id_nearest -or
  $_.spot_image_path_nearest -or
  $_.spot_image_link_status_nearest -or
  $_.spot_image_link_age_ms_nearest
})

$spotConfig = (Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/spot/config" -TimeoutSec 5 -UseBasicParsing).Content | ConvertFrom-Json

$closeout = [ordered]@{
  artifact_kind = "server_smoke_bundle"
  bundle_name = $bundleName
  csv_file = $csvFile
  metadata_file = $metadataFile
  observation_fact_file = $obsFile
  image_fact_file = $imageFactFile
  validation_source = Get-ValidatorValue "spot_image_fact_validation_source"
  validator_command = @(
    "py -3 scripts\validate_csv_v2_shadow.py",
    "--v2", $csvFile,
    "--metadata", $metadataFile,
    "--spot-observation-fact", $obsFile,
    "--spot-image-fact", $imageFactFile
  )
  validator_exit_code = $validatorExitCode
  validator_verdict = if ($validatorExitCode -eq 0 -and ($validatorLines -contains "PASS")) { "PASS" } else { "FAIL" }
  spot_image_fact_row_count_match = Get-ValidatorValue "spot_image_fact_row_count_match"
  spot_image_fact_sha256_match = Get-ValidatorValue "spot_image_fact_sha256_match"
  v2_rows = [int](Get-ValidatorValue "v2_rows")
  realtime_image_link_rows = $linkRows.Count
  realtime_image_link_blank_rows = $rows.Count - $linkRows.Count
  capture_enabled = [bool]$spotConfig.image_capture.enabled
  capture_mode = [string]$spotConfig.image_capture.mode
  capture_failure_count = [int]$spotConfig.image_capture.failure_count
  redaction = [ordered]@{
    raw_image_included = $false
    camera_url_included = $false
    secret_included = $false
    full_path_included = $false
  }
}

if ($closeout.validator_exit_code -ne 0) { throw "validator failed" }
if ($closeout.capture_enabled -ne $false -or $closeout.capture_mode -ne "off") {
  throw "capture closeout is not back to the normal off policy"
}
if ($closeout.capture_failure_count -ne 0) { throw "capture failure count is non-zero" }

$closeoutPath = Join-Path $bundle "server_smoke_closeout_sanitized.json"
$closeout | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $closeoutPath -Encoding UTF8
```

Before archiving or sharing the bundle, verify that closeout JSON string values
contain no raw image content, camera URL, secret, or full path. Check values, not
field names, so redaction flags such as `secret_included=false` are allowed:

```powershell
$closeoutText = Get-Content -LiteralPath $closeoutPath -Raw
$closeoutJson = $closeoutText | ConvertFrom-Json

function Get-JsonStringValues($value) {
  if ($null -eq $value) {
    return
  }
  if ($value -is [string]) {
    $value
    return
  }
  if ($value -is [System.Collections.IEnumerable] -and $value -isnot [string]) {
    foreach ($item in $value) {
      Get-JsonStringValues $item
    }
    return
  }
  if ($value.PSObject -and $value.PSObject.Properties.Count -gt 0) {
    foreach ($property in $value.PSObject.Properties) {
      Get-JsonStringValues $property.Value
    }
  }
}

$stringValues = @(Get-JsonStringValues $closeoutJson)
$forbiddenValuePatterns = @(
  "https?://",
  "^[A-Za-z]:\\",
  "^\\\\",
  "password\\s*[:=]",
  "secret\\s*[:=]",
  "token\\s*[:=]",
  "^data:image/",
  "^/9j/",
  "^iVBOR"
)

$hits = @($stringValues | Where-Object {
  $candidate = $_
  $forbiddenValuePatterns | Where-Object { $candidate -match $_ }
})
if ($hits.Count -gt 0) {
  throw "closeout JSON contains forbidden sensitive or path-like values"
}
```

Archive the bundle only after the closeout JSON is written and redaction checks
pass. Then record the final zip hash:

```powershell
$zip = "$bundle.zip"
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -LiteralPath (Join-Path $bundle "*") -DestinationPath $zip -Force
Get-FileHash -Algorithm SHA256 -LiteralPath $zip
```

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
