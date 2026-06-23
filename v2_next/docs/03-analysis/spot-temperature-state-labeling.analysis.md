# Gap Analysis: spot-temperature-state-labeling

> Date: 2026-06-23 | Design: docs/02-design/features/spot-temperature-state-labeling.design.md
> Phase: Check | Scope: instrumentation_only

---

## Match Rate: 100% Local Instrumentation

Local implementation match is calculated only for design items that can be proven on the development PC. Operational promotion is explicitly out of scope for this match rate and remains blocked by server-PC and downstream-consumer evidence.

```text
Implemented local instrumentation items: 28
Required local instrumentation items: 28
Local match rate: 100%
Operational promotion readiness: blocked
```

## Summary

The current implementation matches the approved instrumentation/shadow design. CSV v2.3.0 remains a permanent shadow schema, realtime CSV rows do not carry future-context segment labels, and `Temperature` remains a legacy effective value with origin/time fields required for interpretation.

No server-PC SPOT behavior is assumed as fact. `no_target` remains available only through verified sentinel configuration, and the current metadata records `server_pc_verified=false` for the sentinel map.

## Implemented Items

- [x] SPOT poll/raw validity enums are separated in `backend/FacilityData/spot_observation.py`.
  Evidence: `SpotPollStatus`, `SpotRawValidity`, `classify_spot_raw_response`, `derive_spot_target_observed_shadow`.
- [x] HTTP error with response body is classified as `spot_raw_validity=not_evaluated`, while missing body failures use `not_received`.
  Evidence: `backend/tests/test_spot_api.py::test_spot_temperature_http_error_with_body_publishes_not_evaluated_snapshot`.
- [x] Stale source snapshots do not provide current target evidence.
  Evidence: `derive_spot_target_observed_shadow` requires `spot_source_freshness=fresh`.
- [x] Temperature status decision table is separated from poll/cache/value-origin fields.
  Evidence: `backend/FacilityData/temperature_state.py::derive_temperature_state`.
- [x] Cache fallback is gated by `cache_fallback_allowed` and transport/request failure status.
  Evidence: `backend/FacilityData/temperature_state.py::cache_fallback_allowed_for_decision` and SPOT API stale fallback tests.
- [x] Invalid responses suppress TTL-valid cache as `available_not_used` rather than reusing it.
  Evidence: `backend/FacilityData/temperature_state.py` and `backend/tests/test_spot_api.py` stale-success coverage.
- [x] `Temperature` is serialized as legacy effective value and may be blank when `temperature_value_origin=none`.
  Evidence: `backend/FacilityData/repository.py::_build_v2_row`; validator invariant tests in `backend/tests/test_real_plc.py`.
- [x] CSV validator enforces `Temperature`/`temperature_value_origin` invariants.
  Evidence: `scripts/validate_csv_v2_shadow.py::validate_temperature_value_origin_invariants`.
- [x] v2.3.0 shadow columns are appended without duplicate `sample_seq`.
  Evidence: `backend/FacilityData/repository.py::SPOT_TEMPERATURE_SHADOW_COLUMNS`; `V2_CSV_COLUMNS.count("sample_seq")` test.
- [x] Realtime row identity is `(logger_service_instance_id, sample_seq)`.
  Evidence: sidecar metadata in `backend/FacilityData/repository.py` and validator check in `scripts/validate_csv_v2_shadow.py`.
- [x] SPOT service sequence uniqueness is scoped to `spot_observation_fact`, not realtime CSV rows.
  Evidence: `schema_metadata.spot_observation_key_scope` and validator check.
- [x] Sequence invariant `spot_observation_seq <= spot_poll_seq` is enforced.
  Evidence: `backend/FacilityData/schemas.py` model validator and `validate_spot_sequence_values`.
- [x] Schema rollover/header mismatch guard exists for v2 files.
  Evidence: `backend/FacilityData/repository.py` header validation and v2.3 contract tests.
- [x] Sidecar records shadow policy, threshold/rule metadata, sentinel map version/hash, logger identity, and git commit policy.
  Evidence: `backend/FacilityData/repository.py::_spot_temperature_shadow_metadata` and sidecar tests.
- [x] Online process state uses causal PLC context only.
  Evidence: `backend/FacilityData/drivers/real_plc.py::_derive_extruder_process_state_online`.
- [x] Metadata-based `changeover_candidate` is compose-layer only and does not override active `extruding`.
  Evidence: `backend/FacilityData/service.py::_derive_metadata_process_state_candidate` and tests.
- [x] Stop duration alone is not promoted to realtime `changeover_candidate`.
  Evidence: online process state priority tests and implementation.
- [x] Post-hoc segment output is separate from realtime CSV rows.
  Evidence: `backend/FacilityData/process_state.py::infer_process_segment_facts` and `scripts/infer_process_segments_for_csv.py`.
- [x] `billet_change_pause` is inferred only post-hoc when stopped segment is between same-context extrusion segments.
  Evidence: `ProcessSegmentFactInferenceTests` in `backend/tests/test_real_plc.py`.
- [x] Realtime v2 columns exclude `process_segment_id`, `extruder_process_state_inferred`, and related future-context fields.
  Evidence: `ProcessSegmentFactInferenceTests::test_realtime_v2_columns_do_not_contain_posthoc_segment_fields`.
- [x] CSV replay preserves v2.3 shadow fields and blank Temperature semantics.
  Evidence: `backend/FacilityData/drivers/csv_replay.py`; `backend/tests/test_csv_replay_driver.py`.
- [x] `/health` exposes non-sensitive SPOT temperature source-health summary without treating it as operational truth.
  Evidence: `backend/FacilityData/service.py::_spot_temperature_health`; `operational_truth=false` test.
- [x] Shadow enum values are validated at schema and CSV-validator layers.
  Evidence: `backend/FacilityData/schemas.py` and `scripts/validate_csv_v2_shadow.py::validate_shadow_enum_values`.
- [x] Physical/numeric SPOT validation rejects negative, non-finite, and boolean values.
  Evidence: `backend/tests/test_schemas.py`.
- [x] Raw payload text is bounded and CSV formula-escaped while hash is kept separately.
  Evidence: `backend/FacilityData/repository.py::_build_v2_row` and CSV contract tests.
- [x] v2.3.0 is documented and encoded as shadow/instrumentation only, with operational fields deferred to v2.4.0+.
  Evidence: design approval gate and sidecar `v2_3_policy`.
- [x] Operational alert and ML promotion are not switched to new labels.
  Evidence: no operational consumer migration; `/health` marks source-health summary as shadow and non-operational.
- [x] PDCA Do has no remaining local implementation item.
  Evidence: `docs/.pdca-status.json` has `remaining_do_items=[]`.

## Missing Items

No local instrumentation implementation gaps remain in the current design scope.

The following are intentionally not completed on the development PC and are not counted as local implementation misses:

- [ ] Server-PC raw SPOT response verification for active extrusion, billet pause, no target, startup, and induced poller stall.
- [ ] Server-PC calibration of `poll_freshness_threshold` from observed poll interval and jitter.
- [ ] Downstream v2.3 consumer compatibility validation for filename, sidecar shape, appended fields, and exact-column-count readers.
- [ ] Legacy reason policy selection for a future operational schema.
- [ ] v2.4.0+ operational fields, if promotion is later approved.

## Changed Items

- [x] `scripts/infer_process_segments_for_csv.py` was listed as optional later work in Design 1.0.8, but PDCA Do still carried `implement_posthoc_process_segment_fact_pipeline` as a remaining item. It has been implemented now as a separate batch output and does not modify realtime CSV rows.
- [x] `/health.spot_temperature` was added as a non-sensitive diagnostic summary. The design said no new public API endpoint was required; this change extends an existing health response and keeps `operational_truth=false`.

## Residual Risks

- Verified no-target behavior is not proven until the server PC captures actual SPOT endpoint responses.
- Local tests simulate poller stale/failure states; they do not prove production network timing or device response semantics.
- `process_segment_fact` uses inferred run segmentation because source CSV has no trusted `run_id`; this is suitable for shadow analysis, not confirmed process truth.
- Exact-column-count external consumers may still reject v2.3.0 until tested in their real deployment context.

## Validation Evidence

Latest local checks:

```text
python -m pytest backend\tests -q
204 passed, 1 warning, 25 subtests passed

python -m pytest backend\tests\test_real_plc.py -q
70 passed, 1 warning, 7 subtests passed

python -m py_compile backend\FacilityData\process_state.py scripts\infer_process_segments_for_csv.py backend\tests\test_real_plc.py
PASS

python -m json.tool docs\.pdca-status.json > $null
PASS

git diff --check
PASS, with existing LF/CRLF warnings only for spot_api.py and test_spot_api.py
```

## Recommendations

1. Keep v2.3.0 as instrumentation/shadow only. Do not reinterpret `*_shadow` columns as operational truth in the same schema.
2. Run server-PC validation before any alert suppression, ML ingestion, or legacy reason remapping.
3. Use the new `process_segment_fact` output only as post-hoc analysis data. Do not join it into realtime training labels unless future-context features are explicitly allowed.
4. Run downstream consumer compatibility checks before enabling v2.3.0 in production logging.

## Next Steps

- [ ] Run server-PC SPOT response capture for the three production states and startup/stall cases.
- [ ] Run downstream consumer compatibility smoke tests against generated v2.3.0 CSV and metadata sidecars.
- [ ] Re-run Check after server evidence is attached.
- [ ] Proceed to Report only for instrumentation completion, not for operational promotion, unless blockers are explicitly accepted as external gates.

## 2026-06-23 SPOT REST Sentinel Evidence Update

- PDF evidence: `docs/reference/ametek_land_spot.pdf` documents REST `temperature` range sentinels as `6553.4` for under-range and `6553.5` for over-range.
- Raw capture evidence: `spot_raw_unattended_20260623_123118.jsonl` contains 2,241 HTTP 200 numeric `6553.4\r\n` samples with `parse_status=numeric` and `parsed_number=6553.4`.
- Factory CSV evidence limitation: inspected `Factory_Integrated_Log_v2_20260623_000000.csv` has no literal `6553.4` or `6553.5` in `Temperature`, so v2.2 CSV output should not be treated as raw device truth for sentinel semantics.
- Contract update: `6553.4` and `6553.5` are documented invalid temperature sentinels, not `verified_no_target`; `verified_no_target_values` remains empty until a no-target response is separately server-verified.
- Additional recommended capture endpoints for promotion evidence: `/output`, `/output?p=alarmstatus`, and `/output?p=signalpc`.
