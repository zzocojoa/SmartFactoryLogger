# SPOT Camera REST API Server Validation

## Status

- Result: `PASS_WITH_STARTUP_COUNTER_BOUNDARY`
- Observation window: `2026-07-11T23:20:39.0146589+09:00` to
  `2026-07-11T23:35:39.2572258+09:00`
- Runtime: server computer with the physical SPOT device
- Build commit: `d6b49a1e741321dcf245687c773fa124e62f8745`
- Installer SHA-256:
  `1391055afe1aa829c30cd3c6955ed65fbc3d1dc5ba2f9d56d418738744d04bae`
- Backend SHA-256:
  `f8d62b78816f04c3b12f9558308fced3ee30d5a117819e2191c831620ebb9a2a`

## Preserved Evidence

- Sanitized artifact:
  [spot-device-evidence-15min-20260711-233544.sanitized.json](evidence/spot-device-evidence-15min-20260711-233544.sanitized.json)
- Original file name: `spot-device-evidence-15min-20260711-233544.json`
- Original size: `98,919` bytes
- Original SHA-256:
  `68ff989c4ac98fc7cf96712ad2ca12e3065e222b28d4dfec59343a70dc221cd4`
- Sanitized size: `100,176` bytes
- Sanitized SHA-256:
  `8408a8e62d992a417e0fc4755d463c5dc7647fa7670e67b63fa22216be185df8`

The original artifact is not committed because it contains local absolute
paths and a runtime endpoint. The committed artifact preserves the original
hash and all validation metrics while redacting those environment-specific
values. The sanitized artifact contains no absolute Windows path, URL, or
credential-pattern hit.

## Validation Results

- Realtime CSV rows added: `3,997`
- Diagnostics `async_complete` rows added: `3,987`
- Diagnostics `async_partial` rows added: `0`
- Row-level startup/counter-boundary `missing` additions: `10`
- Observation fact polls: `900`
- Observation fact polls with `async_complete`: `900`
- `signalpc=parse_error`: `0`
- Health probe failures: `0`
- Temperature poll failures: `0`
- Image error entries: `0`
- Total SPOT failures: `0`
- Observation fact write failure delta: `0`
- Observation fact link failure delta: `0`
- Driver connected at completion: `true`

## Adjudication

All 900 device observation facts were complete. The ten `missing` additions
were row-level logger counts at the startup/counter boundary, not ten failed
SPOT diagnostic polls. The strict first-pass script therefore produced a false
negative by treating row-level warmup counts as runtime device failures.

The parse-failure raw-evidence path did not activate because `signalpc` had no
parse failure during this observation. Its behavior remains covered by the
focused regression tests. No additional installer rebuild or 15-minute rerun
is required for this validation.

## PLC and Live-Image Recovery Monitor

- Result: `PASS`
- Observation window: `2026-07-11T23:55:29.7559934+09:00` to
  `2026-07-12T00:10:30.6016455+09:00`
- Preserved artifact:
  [plc-live-image-monitor-20260712-001030.json](evidence/plc-live-image-monitor-20260712-001030.json)
- Artifact size: `103,190` bytes
- Artifact SHA-256:
  `415704244b1388ef95629e908141a31d724c55ff03f11a220edb13f90d9b5064`
- Health samples: `174`
- Health probe failures: `0`
- Disconnected samples: `0`
- Stale snapshot samples: `0`
- Thread failure samples: `0`
- SPOT poll failure samples: `0`
- Extruder failure delta: `0`
- LS PLC failure delta: `0`
- Observability error total: `0`
- PLC error total: `0`
- Live-image error total: `0`
- Final official image probe: `PASS`

The monitor cleared the in-memory observability queue only after recovery
preflight completed, so the zero-error result covers new errors during the
full observation window. The artifact intentionally stores summarized health
and sanitized error fields only; it contains no absolute path, URL,
credential-pattern value, or private device address.
