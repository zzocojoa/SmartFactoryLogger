# spot-temperature-state-labeling - Design Document

> Version: 1.0.9 | Date: 2026-06-23 | Status: Conditionally Approved - Instrumentation Only
> Level: Dynamic | Plan: docs/01-plan/features/spot-temperature-state-labeling.plan.md

---

## 1. Overview

### 1.1 Purpose
Add a production-aware SPOT temperature observability and shadow-labeling model that distinguishes normal no-target intervals from true temperature source failures while preserving CSV v2 compatibility.

This design is conditionally approved for instrumentation and shadow logging. It is not approved to treat `temperature_status_shadow`, SPOT target shadow fields, or segment-level process labels as operational truth until server-PC validation confirms SPOT no-target response semantics, cache behavior, and consumer compatibility.

v2.3.0 is an instrumentation and shadow-logging schema. It must not be reinterpreted later as operational truth. Operational truth fields require server-PC validation and a later schema such as v2.4.0+.

### 1.2 Design Goals
- Keep extrusion process state, SPOT target state, SPOT poll/cache/source freshness, and final temperature usability status as separate concepts.
- Preserve raw SPOT temperature evidence before validation normalizes invalid values to `None`.
- Avoid label leakage by separating realtime online labels from post-hoc inferred segment labels.
- Keep post-hoc inferred segment labels out of realtime append-only CSV rows. Later v2.4 operational schema work may add causal realtime segment keys, but not future-context inferred labels.
- Preserve existing v2 `sample_seq`; do not append a duplicate column with the same name.
- Treat `Temperature` as a legacy effective value whose actual measurement time and origin must be read from metadata fields.
- Append new CSV columns only after schema rollover checks prevent mixed-header files.
- Use confidence-scored inference only in separate batch outputs where historical or future-context analysis is required.
- Make operational alerting consume poll failure duration, source freshness, and status transitions, not raw 5Hz missing row counts.

## 2. Architecture

### 2.1 System Architecture
The change sits in backend ingestion, SPOT polling, state derivation, and CSV logging.

Current path:

`spot_api temperature cache -> RealPLCDriver._read_spot -> FactoryData.Spot -> CSVLoggerService._quality_for_temperature -> CSV v2`

Target instrumentation path:

`spot_api raw response + immutable poll snapshot -> SpotTemperatureObservation -> RealPLCDriver joins PLC/SPOT snapshots -> FactoryData SPOT observation fields -> shadow state derivation -> CSV v2.3.0 append-only instrumentation fields`

The existing `Temperature`, `Temperature_quality`, `Temperature_missing_reason`, and `Temperature_unit` columns remain legacy compatibility fields. Shadow fields are for validation analysis only and must not be consumed by operations or ML training until explicitly validated and promoted.

### 2.2 Component Design

#### `backend/FacilityData/drivers/spot_api.py`
- Own SPOT HTTP polling.
- Produce immutable poll snapshots with raw response, parsed current value, poll status, raw validity, cache status, source freshness, error code, service instance ID, sequence IDs, and timestamps.
- Use monotonic time for internal age calculations and UTC wall-clock time for CSV/report output.
- Do not infer production state.

#### `backend/FacilityData/spot_observation.py` (new)
- Define immutable `SpotPollSnapshot` / `SpotTemperatureObservation` types.
- Classify raw validity:
  - `valid_temperature`
  - `verified_no_target`
  - `empty_body`
  - `parse_error`
  - `invalid_sentinel`
  - `out_of_range`
  - `not_received`
  - `not_evaluated`
- Manage sequence consistency so value, error code, timestamps, and raw payload cannot come from different poll attempts.
- Publish snapshots atomically so concurrent PLC and SPOT reads cannot mix fields from different observations.

#### `backend/FacilityData/temperature_state.py` (new)
- Derive `temperature_status_shadow` from SPOT observation, source freshness, and cache state.
- Map new status fields to legacy `Temperature_quality` and `Temperature_missing_reason` only in the selected compatibility mode.
- Avoid using extruder state as a substitute for SPOT target evidence.

#### `backend/FacilityData/process_state.py` (new)
- Derive causal online process state from current and past PLC signals only.
- Derive post-hoc segment state separately when future context is available.
- Keep segment inference out of realtime append-only CSV rows.

#### `backend/FacilityData/drivers/real_plc.py`
- Join immutable PLC snapshots and immutable SPOT snapshots.
- Pass validated `Spot` plus observation metadata into `FactoryData`.
- Do not treat `Speed > 0` as SPOT target presence.

#### `backend/FacilityData/repository.py`
- Serialize already-derived fields to CSV.
- Enforce schema rollover and header compatibility checks.
- Generate and persist `logger_service_instance_id` and `logger_service_started_at` in the sidecar.
- Avoid owning complex process or SPOT state derivation.

### 2.3 Data Flow

1. SPOT poller attempts temperature request.
2. Poller records `spot_poll_status`, `spot_raw_validity`, raw payload, parse result, error code, poll timestamps, service instance ID, and sequence IDs.
3. Cache manager determines whether a valid value is current, reused, expired, empty, invalidated, or available but suppressed, and emits `cache_fallback_allowed`.
4. Source freshness is calculated from the latest completed immutable snapshot age.
5. `RealPLCDriver` joins SPOT observation with extruder and LS snapshots.
6. Online process state is derived using only available current/past PLC context.
7. Temperature state is derived from SPOT poll/cache/value-origin/source-freshness evidence.
8. CSV v2.3.0 writer emits legacy fields plus realtime shadow instrumentation fields after schema rollover.
9. Optional batch inference later produces separate segment-level inferred outputs using future context.

## 3. Data Model

### 3.1 Online Process State

`extruder_process_state_online` is causal and safe for append-only CSV rows.

```text
extruding
stopped
idle_candidate
changeover_candidate
unknown
```

Before classification, PLC input freshness and quality must be checked. If the PLC snapshot is missing, stale, or contradictory enough that speed/pressure/cycle evidence is unreliable, emit:

```text
extruder_process_state_online=unknown
```

Required configuration values:

```text
SPEED_IDLE_MAX
EXTRUDING_ENTER_DWELL_MS
EXTRUDING_EXIT_DWELL_MS
RECENT_EXTRUSION_WINDOW_SEC
IDLE_CANDIDATE_MIN_SEC
CHANGEOVER_CANDIDATE_MIN_SEC
```

Initial evidence:

| State | Candidate Evidence |
|-------|--------------------|
| `extruding` | `Speed > SPEED_IDLE_MAX` for at least `EXTRUDING_ENTER_DWELL_MS` |
| `stopped` | previously extruding within `RECENT_EXTRUSION_WINDOW_SEC`, now `Speed <= SPEED_IDLE_MAX` for at least `EXTRUDING_EXIT_DWELL_MS` |
| `idle_candidate` | no movement, no pressure, no active cycle, and no recent extrusion evidence for at least `IDLE_CANDIDATE_MIN_SEC` |
| `changeover_candidate` | operator product/die metadata changes while stopped; stop duration alone is not enough |
| `unknown` | missing, stale, insufficient, or contradictory signals |

Online state priority:

1. PLC stale, missing, or contradictory -> `unknown`.
2. Service restart without enough prior context for `RECENT_EXTRUSION_WINDOW_SEC` -> `unknown`.
3. `Speed > SPEED_IDLE_MAX` for at least `EXTRUDING_ENTER_DWELL_MS` -> `extruding`.
4. Recently extruding, now `Speed <= SPEED_IDLE_MAX` for at least `EXTRUDING_EXIT_DWELL_MS` -> `stopped`.
5. Metadata/product/die change while stopped -> `changeover_candidate`.
6. No movement, no pressure, no active cycle, and no recent extrusion evidence for at least `IDLE_CANDIDATE_MIN_SEC` -> `idle_candidate`.
7. Stop duration alone beyond `CHANGEOVER_CANDIDATE_MIN_SEC` without metadata, run, or operator evidence -> `idle_candidate` or `unknown`, never `changeover_candidate`.
8. Otherwise -> `unknown`.

This priority is evaluated before any SPOT target inference and must not use future rows.

### 3.2 Post-hoc Process State

`extruder_process_state_inferred` may use future context and must be written only to a separate batch output or table.

```text
extruding
billet_change_pause
idle
changeover
unknown
```

`billet_change_pause` definition:

```text
Within the same run and same product/die context, the interval between the previous extrusion ending and the next billet extrusion restarting. This state is confirmable only by post-hoc segment analysis.
```

Current source CSV does not provide a guaranteed `run_id`. Therefore `billet_change_pause` can be confirmed only when a trusted `run_id` or equivalent production-run identifier exists. If not, batch inference must emit:

```text
run_segment_id_inferred
run_segmentation_confidence
run_segmentation_rule_version
```

Without a trusted run boundary, `billet_change_pause` remains a post-hoc inference, not a confirmed process fact.

Required batch output shape:

```text
process_segment_fact
- process_segment_id
- segment_start_at
- segment_end_at
- extruder_process_state_inferred
- inference_confidence
- inference_rule_version
- source_file_id or logger_service_instance_id
- sample_seq_start
- sample_seq_end
```

Requirements:

- Do not write `process_segment_id`, `extruder_process_state_inferred`, `extruder_process_state_inferred_confidence`, or `process_state_inference_rule_version` into realtime append-only CSV rows.
- If `sample_seq` is used for row linkage, use `(logger_service_instance_id, sample_seq)`, not `sample_seq` alone.
- Do not use this value as a realtime training label unless downstream explicitly allows future-context features.

### 3.3 SPOT Target State

Realtime target evidence and inferred target state must be separate.

```text
spot_target_state_observed_shadow:
- present
- absent
- unknown

spot_target_state_inferred:
- present
- absent
- unknown

spot_target_state_inference_confidence
spot_target_state_inference_rule_version
```

Operational realtime decisions may use only `spot_target_state_observed_shadow` after validation. `spot_target_state_inferred` belongs in separate batch or shadow analysis output, not as an operational realtime truth field.

Observed evidence priority:

1. Vendor-documented or server-verified no-target response from a fresh snapshot -> `absent`.
2. Valid positive temperature from a fresh snapshot -> `present`.
3. Anything else -> `unknown`.

If `spot_source_freshness=stale`, do not treat the old snapshot as current target evidence. Emit `spot_target_state_observed_shadow=unknown` unless a fresh snapshot explicitly verifies target state.

Do not assume the following until verified on the server PC:

- empty body means no target
- value above 2000 means no target
- `None` means no target
- `Speed > 0` means target present
- idle-looking extruder state means target absent

### 3.4 Poll, Raw Validity, Cache, and Value Origin

These fields must be separate from `temperature_status_shadow`.

```text
spot_poll_status:
- success
- timeout
- connection_error
- http_error
- config_missing
- not_attempted

spot_raw_validity:
- valid_temperature
- verified_no_target
- empty_body
- parse_error
- invalid_sentinel
- out_of_range
- not_received
- not_evaluated

spot_cache_status:
- fresh
- reused
- expired
- empty
- invalidated
- available_not_used

spot_source_freshness:
- fresh
- stale
- unknown

temperature_value_origin:
- current_observation
- cached_observation
- none

cache_fallback_allowed:
- true
- false
```

Layering rules:

- `spot_poll_status` describes request/transport outcome.
- `spot_raw_validity` describes the received response body or the absence of a response body.
- HTTP 2xx with an empty body is `spot_poll_status=success` and `spot_raw_validity=empty_body` until vendor evidence proves it is no-target.
- Timeout or connection failure is `spot_poll_status=<failure>` and `spot_raw_validity=not_received`.
- HTTP error with an available response body is `spot_poll_status=http_error` and `spot_raw_validity=not_evaluated`.
- `not_received` means no response body was available for raw-value evaluation.
- A valid cache suppressed by an invalid current response is `spot_cache_status=available_not_used`.
- A cache cleared by verified no-target is `spot_cache_status=invalidated`.
- `cache_fallback_allowed=true` only for transport/request failures where no successful SPOT observation can be evaluated, such as `timeout`, `connection_error`, or `http_error`.
- `cache_fallback_allowed=false` for `valid_temperature`, `verified_no_target`, `empty_body`, `parse_error`, `invalid_sentinel`, `out_of_range`, `not_attempted`, and `config_missing`.

Example:

```text
current poll timeout + valid cache from 2 seconds ago:
- temperature_status_shadow=ok
- spot_poll_status=timeout
- spot_cache_status=reused
- temperature_value_origin=cached_observation

current poll timeout + expired cache:
- temperature_status_shadow=stale
- spot_cache_status=expired
- temperature_value_origin=none
```

Operational alerts should use consecutive poll failures, snapshot age, and source freshness, not only `temperature_status_shadow`.

### 3.5 Service Instance, Sequence, and Time Fields

Store distinct identifiers and timestamps:

```text
logger_service_instance_id
logger_service_started_at
spot_service_instance_id
spot_service_started_at
spot_last_poll_started_at
spot_last_poll_completed_at
spot_last_response_at
spot_last_valid_value_at
spot_snapshot_age_ms
spot_value_age_ms
```

Logger identity rules:

```text
logger_service_instance_id:
- UUID generated when CSVLoggerService starts
- new UUID after process restart
- recorded in CSV sidecar

sample_seq:
- existing v2 column, not a new append column
- increases from 1 within each logger_service_instance_id

row unique key:
- (logger_service_instance_id, sample_seq)
```

SPOT sequence rules:

```text
spot_poll_seq:
- allocated at every poll start

spot_observation_seq:
- allocated whenever a poll completes and a new immutable snapshot is atomically published
```

Sequence invariants:

```text
observation_seq <= poll_seq
normally poll_seq - observation_seq is 0 or 1
```

Unique SPOT keys:

```text
(spot_service_instance_id, spot_poll_seq)
(spot_service_instance_id, spot_observation_seq)
```

These SPOT keys apply to `spot_observation_fact` or poll diagnostics. They are not realtime CSV row keys. A single `(spot_service_instance_id, spot_observation_seq)` can appear in multiple 5Hz CSV rows while the SPOT poller updates at about 1Hz. Realtime CSV row identity remains only `(logger_service_instance_id, sample_seq)`.

Use distinct thresholds:

```text
poll_freshness_threshold
cache_expiry_threshold
```

Guidance:

- `poll_freshness_threshold`: source freshness, usually poll interval * 2 to 3 plus jitter.
- `cache_expiry_threshold`: compatibility/UI carry-forward window, can initially retain the current 15 second TTL.
- `spot_snapshot_age_ms`: age of `spot_last_poll_completed_at` for the latest immutable snapshot referenced by the CSV row.
- `spot_value_age_ms`: age of `spot_last_valid_value_at`, not age of the last poll that may have returned no target or an error.
- Internal age calculations should use monotonic time. CSV/report timestamps should use UTC wall-clock time.

### 3.6 Temperature Value Semantics

The existing `Temperature` column is a legacy compatibility field, not necessarily a current-row measurement.

```text
Temperature:
- legacy effective temperature value
- may come from current observation or TTL-valid cached observation
- actual measurement time is `spot_last_valid_value_at`
- origin is `temperature_value_origin`

spot_temperature_observed_c:
- parsed temperature from the latest completed SPOT poll snapshot
- NULL when the latest completed snapshot has no valid current temperature
```

Example:

```text
row timestamp=2026-06-22T05:00:03.100Z
Temperature=448.5
spot_temperature_observed_c=NULL
temperature_value_origin=cached_observation
spot_last_valid_value_at=2026-06-22T05:00:01.100Z
spot_value_age_ms=2000
```

Consumers must not interpret `Temperature` alone as a fresh measurement at the row timestamp.

Required invariants:

```text
temperature_value_origin=current_observation
-> Temperature == spot_temperature_observed_c

temperature_value_origin=cached_observation
-> Temperature is the TTL-valid cached effective value
-> spot_temperature_observed_c is NULL unless the latest completed poll also parsed a valid current value

temperature_value_origin=none
-> Temperature is NULL
```

The existing `captured_at_spot` meaning is unchanged for legacy compatibility. Use `spot_last_valid_value_at`, `spot_last_poll_completed_at`, `spot_snapshot_age_ms`, and `spot_value_age_ms` to determine measurement age and source freshness.

### 3.7 Temperature Status Shadow

`temperature_status_shadow` is the final usability status candidate for the row. It is not an operational truth label during instrumentation.

```text
ok
no_target
startup_pending
source_error
invalid_value
stale
unknown_missing
```

`Current response` means the latest completed immutable SPOT poll snapshot referenced by the realtime CSV row. A 5Hz CSV row may reference the same 1Hz SPOT snapshot as previous rows.

Freshness gate:

| Source Freshness Condition | Temperature Rule | `spot_source_freshness` |
|----------------------------|------------------|-------------------------|
| First poll has not completed | `temperature_status_shadow=startup_pending`; `temperature_value_origin=none` | `unknown` |
| Latest snapshot age is within `poll_freshness_threshold` | Apply deterministic decision table below | `fresh` |
| Snapshot is older than `poll_freshness_threshold`, latest snapshot is a transport/request failure, `cache_fallback_allowed=true`, and cache is within TTL | `temperature_status_shadow=ok`; `spot_cache_status=reused`; `temperature_value_origin=cached_observation`; poller-health alert remains eligible | `stale` |
| Snapshot is older than `poll_freshness_threshold`, latest snapshot is a transport/request failure, `cache_fallback_allowed=true`, and previous value exists but TTL is exceeded | `temperature_status_shadow=stale`; `spot_cache_status=expired`; `temperature_value_origin=none` | `stale` |
| Snapshot is older than `poll_freshness_threshold`, latest snapshot is a transport/request failure, and no fallback value is usable | `temperature_status_shadow=source_error`; `spot_cache_status=available_not_used` if TTL-valid cache exists but fallback is suppressed, otherwise `empty`; `temperature_value_origin=none` | `stale` |
| Snapshot is older than `poll_freshness_threshold`, latest snapshot is not a transport/request failure, `cache_fallback_allowed=false`, and TTL-valid cache exists | `temperature_status_shadow=unknown_missing`; `spot_cache_status=available_not_used`; `temperature_value_origin=none` | `stale` |
| Snapshot is older than `poll_freshness_threshold`, latest snapshot is not a transport/request failure, `cache_fallback_allowed=false`, previous value exists, and TTL is exceeded | `temperature_status_shadow=stale`; `spot_cache_status=expired`; `temperature_value_origin=none` | `stale` |

When the source snapshot itself is stale, a TTL-valid legacy effective temperature may be reused only if the latest stale snapshot is a transport/request failure with `cache_fallback_allowed=true`. A transport/request failure with `cache_fallback_allowed=false` is still a source failure, so it emits `temperature_status_shadow=source_error` and reports any TTL-valid cache as `available_not_used`. A stale success, parse error, invalid sentinel, out-of-range value, empty successful response, or verified no-target response must not revive cache merely because TTL has not expired; in those non-transport non-fallback cases, emit `spot_cache_status=available_not_used` when TTL-valid cache exists, otherwise `expired` or `empty` as applicable.

Deterministic decision table for fresh snapshots:

| Priority | Input State | Result |
|----------|-------------|--------|
| 1 | Current response is verified no-target | `temperature_status_shadow=no_target`; invalidate previous product temperature cache; `spot_cache_status=invalidated`; `temperature_value_origin=none` |
| 2 | Current response is a valid temperature | `temperature_status_shadow=ok`; `spot_cache_status=fresh`; `temperature_value_origin=current_observation`; `spot_temperature_observed_c=<parsed value>` |
| 3 | Current poll has transport/request failure, `cache_fallback_allowed=true`, and valid cache is within TTL | `temperature_status_shadow=ok`; `spot_cache_status=reused`; `temperature_value_origin=cached_observation` |
| 4 | Current poll has transport/request failure, `cache_fallback_allowed=true`, and a previous value exists but TTL is exceeded | `temperature_status_shadow=stale`; `spot_cache_status=expired`; `temperature_value_origin=none` |
| 5 | Current poll has transport/request failure and no fallback value is usable | `temperature_status_shadow=source_error`; `spot_cache_status=available_not_used` if TTL-valid cache exists but fallback is suppressed, otherwise `empty`; `temperature_value_origin=none` |
| 6 | Current response is received but invalid and is not verified no-target | `temperature_status_shadow=invalid_value`; `spot_cache_status=available_not_used` if TTL-valid cache exists, otherwise `empty`; `temperature_value_origin=none` |
| 7 | Service started but the first poll has not completed | `temperature_status_shadow=startup_pending`; `spot_cache_status=empty`; `temperature_value_origin=none` |
| 8 | None of the above is provable | `temperature_status_shadow=unknown_missing`; `temperature_value_origin=none` |

This policy distinguishes `source_error` from `stale`: `source_error` means no usable value exists during a current source failure, while `stale` means an older value exists but has expired or the source snapshot is no longer fresh.

## 4. CSV Schema

### 4.1 v2.3.0 Realtime Append Fields

Append after current `cycle_state`, only after schema rollover has created a new file:

```text
logger_service_instance_id
logger_service_started_at
extruder_process_state_online
process_state_online_rule_version
spot_target_state_observed_shadow
spot_target_state_observed_source
label_validation_state
temperature_status_shadow
temperature_status_rule_version
spot_poll_status
spot_raw_validity
spot_cache_status
spot_source_freshness
temperature_value_origin
cache_fallback_allowed
spot_service_instance_id
spot_service_started_at
spot_poll_seq
spot_observation_seq
spot_temperature_observed_c
spot_temperature_raw
spot_temperature_raw_truncated
spot_raw_payload_hash
spot_raw_payload_encoding
spot_http_status_code
spot_device_status_code
spot_error_code
spot_poll_duration_ms
spot_response_content_length
spot_last_poll_started_at
spot_last_poll_completed_at
spot_last_response_at
spot_last_valid_value_at
spot_snapshot_age_ms
spot_value_age_ms
```

The existing v2 `sample_seq` column is reused and must not be appended again. Row identity is `(logger_service_instance_id, sample_seq)`.

For v2.3 instrumentation rows, the following fields are explicitly excluded from realtime append-only CSV rows. v2.4 operational schema work may add a causal realtime process_segment_id; the inferred state/confidence fields remain excluded:

```text
process_segment_id
extruder_process_state_inferred
extruder_process_state_inferred_confidence
process_state_inference_rule_version
spot_target_state_inferred
spot_target_state_inference_confidence
spot_target_state_inference_rule_version
```

Confidence policy:

- Direct observed or causal realtime fields do not use probability-like confidence columns.
- Realtime fields use `*_source`, rule version, and `label_validation_state` instead of confidence.
- `label_validation_state` values are `shadow`, `validated`, and `deprecated`.
- During instrumentation, every new realtime status label has `label_validation_state=shadow`.
- Post-hoc inferred batch outputs may keep confidence values in the `0.0` to `1.0` range.
- Any post-hoc confidence must document the rule version, calculation method, and calibration assumptions.

Raw payload guidance:

- Limit `spot_temperature_raw` to 256 characters.
- Store `spot_temperature_raw_truncated=true` when truncated.
- Store `spot_raw_payload_hash` for full-payload identity.
- Define `spot_raw_payload_hash` as SHA-256 over the original response body bytes.
- Calculate the hash before truncation, CR/LF normalization, text decoding cleanup, or CSV escaping.
- Store `spot_raw_payload_encoding` as the HTTP charset when known, or `raw-bytes` when the hash is based only on original bytes.
- Escape CSV formula prefixes and normalize CR/LF only for the stored text field, not for the hash input.
- Raw payload repetition in the 5Hz wide CSV is temporary and limited to the instrumentation validation period.

Longer-term storage should move raw payloads to `spot_observation_fact`:

```text
spot_observation_fact
- spot_service_instance_id
- spot_observation_seq
- raw payload
- hash
- poll status
- raw validity
- parsed value
- timestamps
```

### 4.2 Legacy Compatibility Policy

Two modes must be explicit.

#### Shadow mode

```text
Temperature contains the effective legacy temperature value.
Temperature_missing_reason=source_missing or existing legacy behavior
new fields carry temperature_status_shadow=no_target/source_error/etc.
```

Use this mode during server validation. Shadow fields are validation data only and must not be used for operational alert suppression or ML training input.

#### Future operational schema mode

```text
temperature_status=no_target
-> Temperature_quality=missing initially
-> Temperature_missing_reason=no_target
```

`Temperature_quality=not_applicable` may be introduced only after consumers support it. Do not enable this mode in v2.3.0; the operational promotion target is v2.4.0 or later.

Specific source codes do not belong directly in legacy reason fields:

```text
Temperature_missing_reason=source_error
spot_error_code=source_timeout
```

### 4.3 Schema Rollover

A schema change must not append rows with a new column count to an existing file.

Required behavior:

- Force a new file when the active CSV schema version changes.
- Include the full schema version in filename or rollover metadata.
- Read existing header before append and reject mismatched column count/order.
- Write a new sidecar for the new schema.
- Record `logger_service_instance_id` and `logger_service_started_at` in the sidecar.
- Record threshold values, threshold rule versions, sentinel map version/hash, application version, status rule versions, and git commit. If the working tree is uncommitted, write `git_commit=null` rather than implying an uncommitted document or schema is present in HEAD.

Recommended filename pattern:

```text
Factory_Integrated_Log_v2.3.0_YYYYMMDD_HHMMSS.csv
```

Compatibility statement:

```text
Append-compatible for tolerant column-name consumers.
Strict backward compatibility is not guaranteed for exact-column-count consumers.
```

## 5. API and Diagnostics

No new public API endpoint is required for the first implementation.

Existing diagnostics should expose non-sensitive fields where practical:

- `/api/spot/config`
- `/stats`

Diagnostic fields:

```text
logger_service_instance_id
logger_service_started_at
spot_service_instance_id
spot_service_started_at
spot_poll_status
spot_raw_validity
spot_cache_status
spot_source_freshness
temperature_value_origin
temperature_status_shadow
spot_target_state_observed_shadow
cache_fallback_allowed
spot_temperature_observed_c
spot_error_code
spot_http_status_code
spot_poll_duration_ms
spot_response_content_length
spot_last_poll_started_at
spot_last_poll_completed_at
spot_last_response_at
spot_last_valid_value_at
spot_snapshot_age_ms
spot_value_age_ms
spot_poll_seq
spot_observation_seq
```
Do not expose credentials or unrelated private network details. Existing local operator URLs may remain in server logs if already part of diagnostics policy.

## 6. Implementation Plan

### 6.1 File Structure

Expected files:

- `backend/FacilityData/drivers/spot_api.py`
- `backend/FacilityData/spot_observation.py`
- `backend/FacilityData/temperature_state.py`
- `backend/FacilityData/process_state.py`
- `backend/FacilityData/drivers/real_plc.py`
- `backend/FacilityData/schemas.py`
- `backend/FacilityData/repository.py`
- `backend/tests/test_spot_api.py`
- `backend/tests/test_real_plc.py`
- `scripts/validate_csv_v2_shadow.py`

Optional later files:

- `scripts/infer_temperature_status_for_csv.py`
- `scripts/infer_process_segments_for_csv.py`
- `docs/03-analysis/spot-temperature-state-labeling.analysis.md`

### 6.2 Implementation Order

1. Server-PC evidence collection for active extrusion, billet pause, no target, and startup raw SPOT responses.
2. Add immutable SPOT poll snapshot and raw validity classification.
3. Add logger and SPOT service instance identifiers.
4. Add poll/cache/value-origin/source-freshness/cache-fallback diagnostics in shadow mode.
5. Add schema rollover guardrails before enabling appended fields.
6. Emit v2.3.0 realtime shadow instrumentation fields without duplicate `sample_seq`.
7. Add `temperature_status_shadow` calculation using the freshness gate and deterministic decision table.
8. Validate downstream v2.3.0 consumer compatibility, including filename, sidecar, and exact-column-count behavior.
9. Validate field agreement against server logs and CSV samples.
10. Only after validation, consider legacy mapping and operational alert migration through v2.4.0+ operational fields.
11. Implement segment-based process state inference as a separate post-hoc pipeline or separate feature.

### 6.3 Decisions Fixed Before Coding

- Realtime CSV rows must not contain post-hoc inferred segment fields.
- Realtime append fields must not include a duplicate `sample_seq`.
- Existing v2 `sample_seq` plus `logger_service_instance_id` is the row unique key.
- `Temperature` is the effective legacy temperature value and may be current or cached.
- `spot_temperature_observed_c` is the latest completed poll snapshot parsed current temperature or NULL.
- Verified no-target response invalidates the previous product temperature cache immediately.
- Invalid current responses suppress TTL-valid cache for that row: `spot_cache_status=available_not_used`.
- `cache_fallback_allowed` gates cache reuse and is false for invalid/empty/no-target successful responses.
- Stale source snapshots do not automatically revive TTL-valid cache values.
- `spot_poll_status` is transport/request state; `spot_raw_validity` is response-body validity.
- `spot_source_freshness` gates the temperature decision table.
- `spot_poll_seq` is allocated at poll start.
- `spot_observation_seq` is allocated at atomic snapshot publication.
- Initial rollout uses shadow mode legacy mapping.

### 6.4 Decisions Still Pending Server-PC Evidence

- Confirm real SPOT no-target response from the server PC.
- Define vendor-confirmed sentinel values, if any.
- Confirm whether empty 2xx response is no-target or response error.
- Define exact `poll_freshness_threshold` from observed poll interval and jitter.
- Confirm downstream consumer behavior for v2.3.0 filename, sidecar changes, appended fields, and exact-column-count readers.

## 7. Test Plan

### 7.1 Unit Tests

- `Spot=-1`, `NaN`, `Infinity`, `-Infinity`, `True`, and `False` are not valid temperatures.
- Official sentinel values are classified by configured sentinel map.
- Value above configured physical max is `invalid_value`, not silent `source_missing`.
- Poll timeout with fresh source and fresh cache emits `temperature_status_shadow=ok`, `spot_poll_status=timeout`, `spot_cache_status=reused`.
- Poll timeout with expired cache emits `temperature_status_shadow=stale`.
- Poll timeout with no previous valid value emits `temperature_status_shadow=source_error`.
- Poller thread stopped after a transport/request failure snapshot with `cache_fallback_allowed=true` and TTL-valid cache emits `temperature_status_shadow=ok`, `temperature_value_origin=cached_observation`, and `spot_source_freshness=stale`.
- Poller thread stopped after a stale success snapshot with TTL-valid cache emits `temperature_status_shadow=unknown_missing`, `spot_cache_status=available_not_used`, and `temperature_value_origin=none`.
- Poller thread stopped with stale fallback-eligible snapshot and expired cache emits `temperature_status_shadow=stale` and `spot_source_freshness=stale`.
- Empty body defaults to `spot_raw_validity=empty_body` and is not no-target unless vendor evidence classifies it as no-target.
- HTTP error with a response body emits `spot_poll_status=http_error` and `spot_raw_validity=not_evaluated`.
- `not_received` is emitted only when no response body exists.
- Invalid current response with TTL-valid cache emits `temperature_status_shadow=invalid_value` and `spot_cache_status=available_not_used`.
- No-target response clears or invalidates previous temperature cache.
- Valid low temperature during billet pause remains `ok`.
- PLC stale overrides speed, metadata, and stop-duration evidence in online process state.
- Service restart emits `unknown` online process state until enough recent context exists.
- Startup while production is already moving emits `startup_pending`, not source failure.
- Contradictory response containing no-target code and valid temperature is rejected or marked `unknown_missing` with error code.

### 7.2 Sequence and Time Tests

- Existing v2 `sample_seq` remains the only `sample_seq` column.
- `(logger_service_instance_id, sample_seq)` is unique.
- Same `spot_observation_seq` can repeat across multiple 5Hz CSV rows between 1Hz SPOT polls.
- `spot_poll_seq` is allocated on every poll start.
- `spot_observation_seq` increments whenever a poll completes and a new immutable snapshot is atomically published.
- `(spot_service_instance_id, spot_poll_seq)` and `(spot_service_instance_id, spot_observation_seq)` are unique.
- `observation_seq <= poll_seq` holds.
- `spot_snapshot_age_ms` is based on latest completed snapshot time.
- `spot_value_age_ms` is based on last valid value time.
- System wall-clock jump does not make internal age negative.
- UTC timestamps are emitted for CSV/report fields.

### 7.3 CSV Contract Tests

- Existing v1 row contract remains unchanged.
- Existing v2 columns remain in current order.
- v2.3.0 fields are appended only in new schema files.
- Appending a v2.3.0 row to a v2.2 header is rejected or forces rollover.
- Realtime append field list contains no duplicate `sample_seq`.
- Realtime CSV excludes post-hoc inferred segment columns.
- Sidecar documents new fields, enum values, validation state, and rule versions.
- Sidecar records `logger_service_instance_id` and `logger_service_started_at`.
- Sidecar records threshold values, sentinel map version/hash, app/rule versions, and `git_commit=null` when the schema/document changes are uncommitted.
- Downstream consumers are tested for v2.3.0 filename, sidecar, appended field, and exact-column-count compatibility.
- Raw response values with comma, quote, CR/LF, `=`, `+`, `-`, or `@` are safely escaped or hashed/truncated.
- `spot_raw_payload_hash` remains stable for the same original response bytes regardless of CSV escaping/truncation.

### 7.4 Historical Inference QA

- Existing server CSVs are read-only inputs.
- Batch inference output adds `*_inferred` fields without overwriting original columns.
- Long missing segments with active transfer delay are not labeled `source_error` without SPOT error evidence.
- Short gaps are not automatically interpolated.
- Inferred labels include confidence and rule version.
- `billet_change_pause` is confirmed only when a trusted `run_id` or equivalent run boundary exists; otherwise run segmentation fields are inferred.
- Online state and post-hoc segment state can differ without being treated as a bug.

### 7.5 Server-PC Validation

Run on the actual server computer, not the development PC.

Verify raw SPOT temperature endpoint responses during:

- active extrusion
- billet pause
- no target
- startup
- poller restart or induced poller stall

Confirm diagnostics and CSV rows agree on:

- `logger_service_instance_id`
- `sample_seq`
- `spot_service_instance_id`
- `spot_poll_seq`
- `spot_observation_seq`
- `spot_poll_status`
- `spot_raw_validity`
- `spot_cache_status`
- `spot_source_freshness`
- `cache_fallback_allowed`
- `temperature_value_origin`
- `spot_error_code`
- `spot_temperature_observed_c`
- `temperature_status_shadow`

## 8. Operations and Metrics

Operational metrics should be poll/time based, not 5Hz row-count based.

```text
poll_error_rate = failed poll count / total poll count
poller_stale_duration = time-weighted spot_source_freshness=stale duration
no_target_duration_ratio = no_target duration / observation duration
stale_duration = time-weighted temperature_status_shadow=stale duration
unknown_missing_duration = time-weighted unknown missing duration
consecutive_poll_failure_duration = current failure streak duration
```

Alerting guidance:

- Alert on sustained poll failures or stale source freshness.
- A row may have `temperature_status_shadow=ok` and `spot_source_freshness=stale` only when the latest stale snapshot is a transport/request failure with `cache_fallback_allowed=true`; that means the value is temporarily usable but the poller may be unhealthy.
- Do not suppress alerts based on `no_target` until no-target semantics are server-validated.
- Do not alert on verified no-target after validation.
- Debounce transient poll errors when fresh cache remains usable.

Rollback:

- Disable v2.3.0 shadow fields or pin writer to legacy schema.
- Preserve existing v2 columns and sidecars.
- Reopen a new schema-specific file if rollback changes column count.

## 9. ML Data Policy

| Field | ML Handling During Instrumentation |
|-------|------------------------------------|
| `Temperature` | Legacy effective value only; do not treat as current-row observation without origin/time fields |
| `spot_temperature_observed_c` | Validation analysis only; use as current SPOT poll value after promotion policy is approved |
| `temperature_status_shadow=ok` | Validation analysis only; not an ML training target until promoted |
| `temperature_status_shadow=no_target` | Validation analysis only; not an alert suppression or training label until promoted |
| `temperature_status_shadow=startup_pending` | Validation analysis only; exclude from training target |
| `temperature_status_shadow=source_error` | Validation analysis only; exclude or flag after promotion policy is approved |
| `temperature_status_shadow=invalid_value` | Validation analysis only; exclude and audit raw validity |
| `temperature_status_shadow=stale` | Validation analysis only; exclude unless downstream explicitly supports stale carry-forward |
| `temperature_status_shadow=unknown_missing` | Validation analysis only; exclude and audit |

Interpolation is not allowed by duration alone. It requires process context, target presence evidence, poll/cache/source freshness status, and downstream-approved ML policy.

## 10. Approval Gate

Current status: conditionally approved for instrumentation only. v2.3.0 is a shadow/instrumentation schema and must remain non-operational. Operational truth promotion requires server-PC validation, consumer compatibility validation, and later v2.4.0+ operational fields.

Approved now:

- Raw SPOT observation and diagnostic capture.
- Immutable poll snapshot implementation.
- Logger and SPOT service instance identifiers.
- Shadow logging of poll/cache/value-origin/source-freshness/cache-fallback fields.
- Schema rollover guardrails.
- Deterministic `temperature_status_shadow` calculation.
- Separate post-hoc batch inference output.

Blocked until operational promotion gates are resolved:

- Treating `temperature_status_shadow` as operational truth.
- Updating operational alerts to depend on new labels.
- Rewriting legacy `Temperature_missing_reason` semantics.
- Writing post-hoc segment labels into realtime CSV rows.
- Using new labels in ML training pipelines.
## 2026-06-23 SPOT REST Sentinel Evidence Update

- PDF evidence: `docs/reference/ametek_land_spot.pdf` documents REST `temperature` range sentinels as `6553.4` for under-range and `6553.5` for over-range.
- Raw capture evidence: `spot_raw_unattended_20260623_123118.jsonl` contains 2,241 HTTP 200 numeric `6553.4\r\n` samples with `parse_status=numeric` and `parsed_number=6553.4`.
- Factory CSV evidence limitation: inspected `Factory_Integrated_Log_v2_20260623_000000.csv` has no literal `6553.4` or `6553.5` in `Temperature`, so v2.2 CSV output should not be treated as raw device truth for sentinel semantics.
- Contract update: `6553.4` and `6553.5` are documented invalid temperature sentinels, not `verified_no_target`; `verified_no_target_values` remains empty until a no-target response is separately server-verified.
- Additional recommended capture endpoints for promotion evidence: `/output`, `/output?p=alarmstatus`, and `/output?p=signalpc`.

## 2026-06-24 Sentinel Contract Patch

- Decimal equivalence update: `6553.40` and `6553.50` are classified as the documented `6553.4` under-range and `6553.5` over-range invalid sentinels, while nearby values such as `6553.39`, `6553.41`, `6553.49`, and `6553.51` remain `out_of_range`.
- Row-level preservation: `spot_raw_validity=invalid_sentinel` remains generic, but CSV rows now preserve `spot_device_status_code=temperature_under_range` or `temperature_over_range` so downstream consumers do not need raw text or sidecar lookup to distinguish the two.
- Cache suppression: after an invalid sentinel, the pre-sentinel temperature cache may remain physically present but is emitted as `available_not_used`; transport fallback is suppressed until the next `valid_temperature` replaces the cache, and suppressed transport failures emit `temperature_status_shadow=source_error` rather than `unknown_missing`.
- Raw preservation and provenance: raw decoded text and payload hash are preserved separately from the stripped Decimal classification text. The sentinel sidecar records repo-relative PDF path, title, issue, page, SHA-256, verification date, and verification method.
- Regression evidence: tests cover `6553.4`, `6553.40`, whitespace/CRLF, `6553.5`, `6553.50`, non-sentinel nearby values, NaN/Inf invalid numeric handling, row-level device status propagation, health API device-status exposure, and `valid -> sentinel -> timeout(source_error) -> valid -> timeout(reused)` cache behavior.
