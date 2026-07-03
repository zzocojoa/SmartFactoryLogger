# SPOT Realtime Image Linkage Guarantee Decision

> Date: 2026-07-03 | Status: Accepted | Scope: CSV v2.4 image link guarantee policy

## Decision

Keep realtime CSV image link fields as best-effort, non-blocking diagnostic
pointers.

The selected guarantee path is a post-hoc linkage fact or report over settled
artifacts. Realtime CSV rows may expose a matching image pointer when the latest
settled capture fact references the same `spot_observation_key`, but those
fields are not the authoritative completeness guarantee.

Do not add pending queue wait/flush, durable fact-file scans, or delayed row
emission to the online CSV writer in this scope.

## Current Behavior

`CSVLoggerService._spot_image_link_for_row` builds realtime `*_nearest` fields by:

1. using explicit `FactoryData` link fields when they are already populated;
2. otherwise reading `spot_api.get_latest_spot_image_capture_fact()`;
3. copying that latest fact only when `spot_image_linked_observation_key` equals
   the realtime row `spot_observation_key`;
4. returning blank link fields when the row has no observation key or the latest
   fact belongs to a different observation.

`spot_api.get_latest_spot_image_capture_fact()` returns only the in-memory latest
capture fact. It is not a durable index of all image facts.

`build_spot_image_fact()` records each image capture's linked observation key,
link status, link age, safe relative image path, and source URL hash in
`spot_image_fact.csv`.

The deploy guide already states that image links are operational correlation,
not an atomic same-cycle guarantee.

## Options Compared

| Option | Decision | Reason |
| --- | --- | --- |
| Keep current realtime best-effort only | Keep for runtime, not enough for guarantee | Smallest and safest online behavior, but it cannot prove settled row-to-image completeness. |
| Observation-key-indexed in-memory lookup | Defer | Better hit rate than latest-only lookup, but adds lifecycle, staleness, retention, and memory cleanup questions while still depending on online timing. |
| Post-hoc linkage fact or report | Chosen guarantee path | Uses settled CSV and fact files, avoids blocking the realtime writer, and can be validator-backed with counts, hashes, and redacted outputs. |
| Pending queue wait/flush before row write | Reject for online writer | Couples row emission to image persistence and can add latency, timeout ambiguity, or queue/backpressure failure modes. |

## Evidence

- Code path: `backend/FacilityData/repository.py::_spot_image_link_for_row`.
- Latest fact source: `backend/FacilityData/drivers/spot_api.py::get_latest_spot_image_capture_fact`.
- Fact schema/write path: `backend/FacilityData/spot_image_fact.py::build_spot_image_fact`.
- Runtime policy doc: `docs/04-deploy/spot-image-capture-settings.md`.
- Unit coverage keeps same-observation rows linked and different-observation rows
  blank in `backend/tests/test_csv_v2_4_operational_contract.py`.
- Image fact tests verify linked observation key, link status, SHA-256 URL hash,
  and no raw camera URL in `backend/tests/test_spot_api.py`.
- Required review search:
  `rg -n "get_latest_spot_image_capture_fact|spot_image_capture_id_nearest|spot_image_link_status_nearest|spot_image_link_age_ms_nearest|spot_image_linked_observation_key|_spot_image_capture_last_fact|write_capture|put_nowait" backend scripts docs`.
- Positive server smoke artifact, sanitized:
  - file: `server_smoke_link_positive_20260703-114627.zip`
  - sha256: `dab938b3d8fe12e002b6da33eeea9d07dd0524cc7e495e1206c5b564b707e4bc`
  - passed: true
  - blocker count: 0
  - warning count: 1
  - realtime CSV rows: 11552
  - realtime rows with any image link field: 306
  - spot image fact rows: 60142
  - spot image fact rows with fresh link status: 60056
  - capture reset after smoke: `enabled=false`, `mode=off`
  - capture failure count: 0

This smoke evidence proves that positive realtime linkage can occur under live
server conditions. It also reinforces that realtime linkage is sparse and timing
dependent; it is not a completeness guarantee.

## Rationale

The current operator value is incident diagnosis and operational correlation.
The realtime CSV pointer helps locate the latest matching evidence image when it
exists, while keeping the CSV writer independent from the asynchronous image
writer.

Guaranteeing linkage in the online writer would add coupling between realtime
row emission and image capture persistence. That can introduce delayed rows,
backfill behavior, or shared state indexed by observation key. The operational
failure mode is worse than a blank diagnostic pointer: slow image writes or a
stuck queue could delay CSV rows or create ambiguous timeout behavior.

The post-hoc path keeps realtime capture non-blocking and moves completeness
checks to a phase where the relevant artifacts have settled. That is the right
place to enforce row counts, hashes, source CSV identity, redaction, and missing
link summaries.

## Post-Hoc Guarantee Requirements

The guaranteed linkage follow-up should emit a dedicated fact or sanitized
report:

1. Read settled realtime CSV v2.4 rows.
2. Read settled `spot_image_fact.csv`.
3. Join by `spot_observation_key == spot_image_linked_observation_key`.
4. Emit counts for total rows, eligible observation rows, matched rows, missing
   rows, and ambiguous rows.
5. Record source CSV identity and SHA-256 values for every input/output artifact.
6. Keep raw image bytes, raw camera URLs, secrets, and full internal paths out of
   the output.
7. Make the validator fail on missing required columns, row/hash mismatch, unsafe
   paths, or source CSV mismatch.

First-class post-hoc linkage fact generation and validator enforcement are a
follow-up implementation. This decision document does not change runtime code,
CSV schema, SPOT image fact schema, or NSIS/build behavior.

## Test Criteria

Current best-effort policy remains covered when:

- same-observation latest facts populate realtime `*_nearest` fields;
- different-observation latest facts leave realtime `*_nearest` fields blank;
- validator accepts populated link fields only when required subfields are
  present and paths are safe relative paths;
- fact validation checks required columns, link status values, SHA-256 text, and
  safe relative image paths;
- smoke evidence reports nonzero fact rows, link rows when capture/linking is
  enabled, and no capture failures.

Guaranteed linkage is not considered implemented until a dedicated validator or
report proves settled fact-to-realtime join completeness with source artifact
hashes and without exposing raw image bytes, raw camera URLs, secrets, or full
internal paths.

## Non-Goals

- No raw image bytes or base64 in realtime CSV.
- No raw camera URL in realtime CSV or audit output.
- No secret exposure.
- No direct mutation of operating data.
- No CSV schema change without explicit approval.
