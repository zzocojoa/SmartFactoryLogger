# Completion Report: spot-temperature-state-labeling

> Date: 2026-06-23 | Level: Dynamic | Scope: instrumentation_only | Status: Completed - Local Instrumentation; Operational Promotion Blocked

---

## 1. Summary

### 1.1 Feature Overview
Implemented the local instrumentation and shadow logging contract for SPOT temperature state labeling. The implementation separates extrusion process state, SPOT target evidence, SPOT poll/raw/cache/source freshness, value origin, and temperature usability shadow status.

This report covers local development-PC implementation only. It does not approve operational truth promotion, alert suppression, legacy reason remapping, or ML usage of the new labels.

### 1.2 Final Match Rate
100% local instrumentation match rate against Design 1.0.8.

Operational promotion readiness remains blocked by server-PC and downstream-consumer evidence.

## 2. Completed Items

- [x] Added immutable SPOT poll snapshot diagnostics and sequence fields.
- [x] Added `spot_poll_status`, `spot_raw_validity`, `spot_cache_status`, `spot_source_freshness`, `temperature_value_origin`, and `cache_fallback_allowed` separation.
- [x] Added `temperature_status_shadow` deterministic decision handling.
- [x] Preserved `Temperature` as legacy effective value and added origin/time invariants.
- [x] Added CSV v2.3.0 shadow fields without duplicate `sample_seq`.
- [x] Preserved row identity as `(logger_service_instance_id, sample_seq)`.
- [x] Scoped SPOT sequence uniqueness to `spot_observation_fact` / diagnostics, not realtime CSV rows.
- [x] Added schema/header rollover guard and validator checks for v2.3.0 shadow CSV.
- [x] Added non-sensitive `/health.spot_temperature` source-health summary with `operational_truth=false`.
- [x] Added post-hoc `process_segment_fact` inference output separate from realtime CSV.
- [x] Verified realtime CSV excludes post-hoc segment fields.
- [x] Added tests for stale cache policy, HTTP error raw validity, enum/sequence invariants, Temperature origin invariants, CSV replay, and post-hoc segment inference.
- [x] Added Check analysis document: `docs/03-analysis/spot-temperature-state-labeling.analysis.md`.

## 3. Key Decisions

- v2.3.0 is permanently `instrumentation/shadow` and must not be reinterpreted later as operational truth.
- Operational fields must be added in v2.4.0 or later after server-PC validation and consumer compatibility checks.
- `no_target` cannot be assumed from empty body, `None`, out-of-range value, or PLC idle state without server/vendor evidence.
- Stale SPOT target evidence is not current target evidence; stale snapshots emit target `unknown` unless a fresh verified snapshot exists.
- TTL-valid cache is reused only when the latest current or stale snapshot is a fallback-eligible transport/request failure with `cache_fallback_allowed=true`.
- `billet_change_pause` is only post-hoc inferred and requires same inferred run context before and after the stopped segment.

## 4. Files Changed

Primary implementation files:

- `backend/FacilityData/spot_observation.py`
- `backend/FacilityData/temperature_state.py`
- `backend/FacilityData/process_state.py`
- `backend/FacilityData/drivers/spot_api.py`
- `backend/FacilityData/drivers/real_plc.py`
- `backend/FacilityData/service.py`
- `backend/FacilityData/repository.py`
- `backend/FacilityData/schemas.py`
- `backend/FacilityData/drivers/csv_replay.py`
- `scripts/validate_csv_v2_shadow.py`
- `scripts/infer_process_segments_for_csv.py`

Primary test files:

- `backend/tests/test_spot_api.py`
- `backend/tests/test_real_plc.py`
- `backend/tests/test_schemas.py`
- `backend/tests/test_csv_replay_driver.py`

PDCA documents:

- `docs/01-plan/features/spot-temperature-state-labeling.plan.md`
- `docs/02-design/features/spot-temperature-state-labeling.design.md`
- `docs/03-analysis/spot-temperature-state-labeling.analysis.md`
- `docs/04-report/spot-temperature-state-labeling.report.md`
- `docs/.pdca-status.json`

## 5. Validation

Latest local validation:

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

## 6. Unverified Server-PC Items

These remain unverified because this is the development computer, not the server computer:

- [ ] Actual SPOT raw response during active extrusion.
- [ ] Actual SPOT raw response during billet-change pause with product still visible.
- [ ] Actual SPOT raw response during no-target / production-ended state.
- [ ] Actual SPOT raw response during startup before first poll completes.
- [ ] Actual behavior under induced poller stall or network failure.
- [ ] Real poll interval and jitter for `poll_freshness_threshold` calibration.
- [ ] Field agreement between server app logs, diagnostics, and generated CSV rows.

## 7. Operational Promotion Blockers

- [ ] `server_pc_spot_no_target_response_unverified`
- [ ] `server_pc_poll_freshness_threshold_unverified`
- [ ] `downstream_v2_3_consumer_compatibility_unverified`
- [ ] `legacy_reason_policy_pending`
- [ ] `operational_schema_v2_4_plus_fields_required`

Until these are resolved, the following remain prohibited:

- Treating `temperature_status_shadow` as operational truth.
- Suppressing alerts based on `no_target`.
- Rewriting legacy `Temperature_missing_reason` semantics.
- Using new labels in ML training pipelines.
- Writing post-hoc segment labels into realtime CSV rows.

## 8. Metrics

| Metric | Value |
|--------|-------|
| Local match rate | 100% |
| Backend tests | 204 passed |
| PDCA iterations | 15 |
| Current PDCA phase | completed - local instrumentation |
| Operational promotion readiness | blocked |

## 9. Follow-up Items

- [ ] Run server-PC SPOT response capture and attach evidence.
- [ ] Run downstream v2.3 consumer compatibility tests.
- [ ] Decide future v2.4.0 operational schema field names after server validation.
- [ ] Keep v2.3.0 shadow fields out of alerting and ML until explicitly promoted.

## 2026-06-23 SPOT REST Sentinel Evidence Update

- PDF evidence: `docs/reference/ametek_land_spot.pdf` documents REST `temperature` range sentinels as `6553.4` for under-range and `6553.5` for over-range.
- Raw capture evidence: `spot_raw_unattended_20260623_123118.jsonl` contains 2,241 HTTP 200 numeric `6553.4\r\n` samples with `parse_status=numeric` and `parsed_number=6553.4`.
- Factory CSV evidence limitation: inspected `Factory_Integrated_Log_v2_20260623_000000.csv` has no literal `6553.4` or `6553.5` in `Temperature`, so v2.2 CSV output should not be treated as raw device truth for sentinel semantics.
- Contract update: `6553.4` and `6553.5` are documented invalid temperature sentinels, not `verified_no_target`; `verified_no_target_values` remains empty until a no-target response is separately server-verified.
- Additional recommended capture endpoints for promotion evidence: `/output`, `/output?p=alarmstatus`, and `/output?p=signalpc`.
