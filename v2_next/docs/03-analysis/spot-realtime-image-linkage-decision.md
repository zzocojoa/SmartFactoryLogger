# SPOT Realtime Image Linkage Guarantee Decision

> Date: 2026-07-03 | Status: Accepted | Scope: CSV v2.4 image link guarantee policy

## Decision

Keep realtime CSV image link fields as best-effort, non-blocking diagnostic
pointers.

Guaranteed CSV-to-image linkage is operationally needed for promotion bundles,
server smoke closeout, and offline analysis where every source row must be
accounted for. Implement that guarantee as a P1 post-hoc linkage fact plus
sanitized report over settled artifacts. Realtime CSV rows may expose a matching
image pointer when the latest settled capture fact references the same
`spot_observation_key`, but those fields are not the authoritative completeness
guarantee.

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
- Row-time freshness closeout evidence, sanitized:
  - file: `row_time_freshness_closeout_20260707-235635.zip`
  - zip SHA-256: `405c7d89bafecf998385a15d84566aac535589b86f6af34e80233953bb759df1`
  - result: PASS
  - validator: `scripts/validate_csv_v2_shadow.py`
  - validator exit code: 0
  - CSV rows checked: 6716
  - SPOT image fact rows: 190293
  - SPOT image fact row count match: true
  - SPOT image fact SHA-256 match: true
  - effective row age differed from snapshot age on 6696 rows
  - threshold mismatch count: 0
  - startup observation key nonblank count: 0
  - freshness counts: `fresh=6689`, `stale=22`, `unknown=5`
  - temperature output status counts: `valid=6689`, `stale=22`, `startup_pending=5`
  - capture reset after closeout: `capture_enabled=false`, `capture_mode=off`, `dropped_count=0`, `failure_count=0`
  - redaction scope: source records, local absolute paths, camera connection details,
    operator access material, and binary image payloads are omitted
- SPOT image linkage closeout gate evidence, sanitized:
  - artifact leaf: `server_smoke_linkage_gate_20260704-112742`
  - source artifacts: settled v2 CSV, sidecar metadata, and `spot_image_fact.csv`
  - generator: `scripts/infer_spot_image_linkage_for_csv.py`
  - validator: `scripts/validate_csv_v2_shadow.py`
  - closeout helper: `scripts/write_server_smoke_closeout.py --mode copied`
  - `validator_exit_code`: 0
  - `validator_verdict`: PASS
  - `validation_source`: `override`
  - `image_linkage.presence`: `present`
  - `image_linkage.fact_file`: `spot_image_linkage_fact.csv`
  - `image_linkage.report_file`: `spot_image_linkage_report.json`
  - `image_linkage.row_count`: 11552
  - `image_linkage.row_count_match`: true
  - `image_linkage.sha256_match`: true
  - `image_linkage.source_csv_sha256_match`: true
  - `image_linkage.spot_image_fact_sha256_match`: true
  - `image_linkage.report_redaction_passed`: true
  - `image_linkage.matched_rows`: 199
  - `image_linkage.ambiguous_rows`: 561
  - `spot_image_linkage_report.counts.no_image_fact`: 10787
  - `spot_image_linkage_report.counts.no_observation_key`: 5
  - capture reset after closeout: `capture_enabled=false`, `capture_mode=off`
  - note: top-level closeout `spot_image_fact_sha256_match=false` belongs to
    copied artifact versus original sidecar manifest drift. It is not a linkage
    gate failure. The linkage gate value is
    `image_linkage.spot_image_fact_sha256_match=true`.
  - redaction scope: source records, binary payloads, local absolute paths,
    credentials, and connection locators are omitted

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

## Implementation Decision

Implement guaranteed linkage as a post-hoc P1 follow-up. Do not implement it in
the realtime writer.

The guarantee means every settled CSV v2.4 row receives a deterministic linkage
status and reason. It does not mean every row must have an image. Rows without a
usable `spot_observation_key`, rows with no matching image fact, and rows with
ambiguous matches remain valid when they are explicitly counted and explained.

This decision document does not change runtime code, CSV schema, SPOT image fact
schema, or NSIS/build behavior. The implementation must be a separate branch and
PR.

## Post-Hoc Linkage Scope

P1 implements a generator that reads settled artifacts and emits both:

1. `spot_image_linkage_fact.csv`, one row per source CSV v2.4 row.
2. `spot_image_linkage_report.json`, a sanitized summary and manifest for the
   generated fact.

The join key is exact:

```text
CSV.spot_observation_key == spot_image_fact.spot_image_linked_observation_key
```

If multiple image facts map to the same `spot_observation_key`, the row must be
classified as `ambiguous` unless the implementation defines and documents a
deterministic tie-breaker that the validator can reproduce.

## Input Schema

Required settled CSV columns:

| Column | Purpose |
| --- | --- |
| `schema_version` | Must identify a v2.4-compatible CSV. |
| `sample_seq` | Stable row sequence for reporting. |
| `timestamp_utc` | Row time for offline analysis. |
| `spot_service_instance_id` | Service identity used in observation keys. |
| `spot_poll_seq` | Poll sequence used in observation keys. |
| `spot_observation_key` | Exact join key to image facts. |
| `spot_image_capture_id_nearest` | Realtime best-effort pointer for comparison only. |
| `spot_image_path_nearest` | Realtime best-effort pointer for comparison only. |
| `spot_image_link_status_nearest` | Realtime best-effort pointer for comparison only. |
| `spot_image_link_age_ms_nearest` | Realtime best-effort pointer for comparison only. |

Required image fact columns are the current `SPOT_IMAGE_FACT_COLUMNS`, including:

| Column | Purpose |
| --- | --- |
| `spot_image_capture_id` | Matched capture identity. |
| `spot_image_path` | Safe relative image path under the log directory. |
| `spot_image_sha256` | Image content hash already recorded by the writer. |
| `spot_image_link_status` | Link status, such as `fresh` or `stale`. |
| `spot_image_link_age_ms` | Age used for analysis and optional tie-breakers. |
| `spot_image_linked_observation_key` | Exact join key back to the CSV row. |

The generator should also read the CSV sidecar metadata and the final image fact
manifest when present. Those manifests are inputs for identity and hash checks,
not sources for raw camera data.

## Output Fact Schema

`spot_image_linkage_fact.csv` should use safe, portable values only:

| Column | Meaning |
| --- | --- |
| `spot_image_linkage_schema_version` | Linkage fact schema version. |
| `linkage_rule_version` | Post-hoc linkage rule version. |
| `source_file_id` | `sha256:<source_csv_sha256>` identifier used by post-hoc facts. |
| `source_csv_sha256` | SHA-256 of the source CSV. |
| `source_csv_row_number` | Physical CSV row number, including header line offset. |
| `sample_seq` | Copied source row sequence. |
| `timestamp_utc` | Copied source row timestamp. |
| `spot_observation_key` | Copied join key. |
| `linkage_status` | `matched`, `no_observation_key`, `no_image_fact`, `ambiguous`, or `invalid_source_row`. |
| `unmatched_reason` | Blank for `matched`, otherwise a stable reason code. |
| `match_count` | Number of image facts found for the observation key. |
| `matched_spot_image_capture_id` | Capture id for deterministic matched rows. |
| `matched_spot_image_path` | Safe relative path only. |
| `matched_spot_image_sha256` | SHA-256 copied from image fact. |
| `matched_spot_image_link_status` | Link status copied from image fact. |
| `matched_spot_image_link_age_ms` | Link age copied from image fact. |
| `image_fact_row_number` | Source image fact row number for matched rows. |
| `realtime_spot_image_capture_id_nearest` | Original realtime pointer for comparison. |
| `realtime_pointer_status` | `same_as_posthoc`, `blank`, `different`, or `not_applicable`. |

`spot_image_linkage_report.json` includes:

- schema version, rule version, and generated timestamp;
- source CSV file name, row count, and SHA-256;
- image fact file name, row count, and SHA-256;
- output fact file name, row count, and SHA-256;
- total rows, matched rows, unmatched rows by reason, ambiguous rows, invalid
  source rows, and realtime pointer comparison counts;
- redaction summary with booleans for raw image bytes, raw camera URLs, secrets,
  and full internal paths.

## Validator Requirements

The validator accepts `--spot-image-linkage-fact` and
`--spot-image-linkage-report` for copied bundles, and also validates
`spot_image_linkage_fact_manifest` from metadata when present. It fails when:

1. any required input or output column is missing;
2. `spot_image_linkage_fact.csv` row count does not equal the source CSV data row
   count;
3. source CSV SHA-256, image fact SHA-256, or output fact SHA-256 does not match
   the report;
4. a `matched` row references a capture id not present in `spot_image_fact.csv`;
5. a `matched` row's `spot_observation_key` differs from the matched image
   fact's `spot_image_linked_observation_key`;
6. a matched image path is absolute, escapes the log directory, or contains a raw
   camera URL;
7. count summaries in the report do not equal the fact rows;
8. any output string value contains raw image bytes, `data:image/`, raw camera
   URLs, secrets, drive-root paths, UNC paths, or full internal paths.

The validator may pass with nonzero `no_image_fact` or `ambiguous` counts only
when those rows are explicitly represented in the fact and included in report
counts.

## Redaction Policy

The post-hoc output must not include:

- raw image bytes or base64;
- raw camera URLs;
- passwords, tokens, or secrets;
- absolute Windows paths, UNC paths, or full internal POSIX paths;
- copied config values that identify private infrastructure beyond sanitized
  file names and SHA-256 hashes.

Relative image paths already written by `spot_image_fact.csv` are allowed after
safe-path validation.

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

Post-hoc implementation must add tests that cover:

- one-to-one matched rows;
- rows without `spot_observation_key`;
- rows with no matching image fact;
- duplicate image facts for one observation key;
- unsafe relative paths and absolute paths;
- source CSV hash mismatch;
- image fact hash mismatch;
- redaction rejection for URLs, secrets, full paths, and image-like payloads;
- realtime pointer comparison where the best-effort pointer is blank, same, and
  different from the post-hoc match.

Minimum verification commands for the implementation PR:

```powershell
py -3 -m pytest backend\tests\test_csv_v2_4_operational_contract.py backend\tests\test_spot_api.py -q
py -3 -m pytest backend\tests\test_spot_image_linkage_fact.py -q
py -3 -m py_compile scripts\validate_csv_v2_shadow.py scripts\write_server_smoke_closeout.py
.\backend\.venv\Scripts\python.exe -m ruff check backend scripts
.\backend\.venv\Scripts\python.exe -m mypy
git diff --check
```

## Non-Goals

- No raw image bytes or base64 in realtime CSV.
- No raw camera URL in realtime CSV or audit output.
- No secret exposure.
- No direct mutation of operating data.
- No CSV schema change without explicit approval.
