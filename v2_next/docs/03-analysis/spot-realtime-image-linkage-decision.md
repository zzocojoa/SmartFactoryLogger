# SPOT Realtime Image Linkage Decision

> Date: 2026-07-02 | Status: Accepted | Scope: CSV v2.4 image link semantics

## Decision

Keep realtime CSV image link fields as best-effort diagnostic pointers.

Do not implement guaranteed per-row image linkage in the online CSV writer now.
If guaranteed audit linkage becomes an explicit requirement, implement it as a
separate design starting with an offline join/report over settled CSV artifacts.

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

## Evidence

- Code path: `backend/FacilityData/repository.py::_spot_image_link_for_row`.
- Latest fact source: `backend/FacilityData/drivers/spot_api.py::get_latest_spot_image_capture_fact`.
- Fact schema/write path: `backend/FacilityData/spot_image_fact.py::build_spot_image_fact`.
- Runtime policy doc: `docs/04-deploy/spot-image-capture-settings.md`.
- Unit coverage keeps same-observation rows linked and different-observation rows
  blank in `backend/tests/test_csv_v2_4_operational_contract.py`.
- Image fact tests verify linked observation key, link status, SHA-256 URL hash,
  and no raw camera URL in `backend/tests/test_spot_api.py`.
- Smoke artifact, sanitized:
  - passed: true
  - fact rows in smoke run: 1409
  - recent realtime rows scanned: 1225
  - recent rows with any capture link: 261
  - latest capture id/path/status/observation-key match: true
  - capture failure count: 0
  - raw secret/image/camera URL/full internal path included: false

## Rationale

The current operator value is incident diagnosis and operational correlation.
The realtime CSV pointer helps locate the latest matching evidence image when it
exists, while keeping the CSV writer independent from the asynchronous image
writer.

Guaranteeing linkage online would add coupling between realtime row emission and
image capture persistence. That can introduce delayed rows, backfill behavior,
or shared state indexed by observation key. Those changes are disproportionate
unless the product requirement becomes an audit guarantee.

## If Guaranteed Linkage Is Required Later

Prefer an offline audit join first:

1. Read settled realtime CSV v2.4 rows.
2. Read settled `spot_image_fact.csv`.
3. Join by `spot_observation_key == spot_image_linked_observation_key`.
4. Emit a sanitized audit report with counts, match booleans, and missing-link
   summaries only.
5. Keep raw image bytes, raw camera URLs, secrets, and full internal paths out of
   the report.

Online guaranteed linkage is a larger change and needs separate approval. It
would require one of:

- an observation-key-indexed in-memory fact cache;
- delayed realtime row emission until the image writer has committed a fact;
- a backfill or sidecar enrichment pass after capture writes settle.

Any online guarantee must explicitly define latency impact, race handling,
retention behavior, CSV schema compatibility, and rollback.

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
report proves settled fact-to-realtime join completeness without exposing raw
image bytes, raw camera URLs, secrets, or full internal paths.

## Non-Goals

- No raw image bytes or base64 in realtime CSV.
- No raw camera URL in realtime CSV or audit output.
- No secret exposure.
- No direct mutation of operating data.
- No CSV schema change without explicit approval.
