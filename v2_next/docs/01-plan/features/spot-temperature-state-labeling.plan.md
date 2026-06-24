# spot-temperature-state-labeling - Plan Document

> Version: 1.0.9 | Date: 2026-06-23 | Document Status: Completed
> Implementation Acceptance Criteria: Local Instrumentation Completed; Operational Promotion Pending
> Level: Dynamic

---

## 1. Overview

### 1.1 Purpose
Separate extrusion process state, SPOT target presence, and temperature measurement status so CSV v2 data can distinguish normal no-target intervals from real SPOT data failures. This plan is approved for instrumentation and shadow logging only. v2.3.0 is a shadow/instrumentation schema, not an operational truth schema; operational fields require server-PC validation and a later v2.4.0+ schema.

### 1.2 Background
The current CSV v2 schema stores all `Temperature` gaps as `Temperature_quality=missing` and `Temperature_missing_reason=source_missing`. Recent server CSV analysis showed 26,616 missing rows out of 341,319 rows, about 7.80%. All missing rows had `captured_at_spot`, and the SPOT capture timestamp advanced at roughly 1.01 second intervals. That means many gaps are not simply "SPOT stopped updating."

Domain review found two important facts:

- `Speed > 0` means the extruder is moving, but it does not prove the extruded product has reached the SPOT measurement position.
- `Speed <= 0.05`, `MainPress <= 0.1`, and `cycle_state=idle` do not prove no target exists at SPOT, because valid SPOT temperatures were observed in idle-looking rows for about 119.4 minutes.
- Segment states such as `billet_change_pause` and `changeover` require future context, so they cannot be written as realtime append-only truth labels without label leakage.

The current label conflates at least three different cases: product not in SPOT measurement area, startup/cache pending, and true source failure. This creates misleading downtime reports and unsafe ML preprocessing.

## 2. Goals

### 2.1 Primary Goals
- [x] Add a state model that separates extrusion process state from SPOT target state and temperature measurement status.
- [x] Separate online causal state from post-hoc inferred segment state to avoid label leakage.
- [x] Add SPOT poll status, raw validity, cache status, source freshness, cache fallback allowance, and temperature value origin before emitting final status labels.
- [x] Define `Temperature` as the effective legacy temperature value, whose measurement time and origin are determined from `temperature_value_origin` and `spot_last_valid_value_at`.
- [x] Preserve SPOT raw value and failure reason before Pydantic validation converts values to `None`.
- [x] Add CSV v2.3.0 candidate columns by appending to the existing v2 schema, without changing existing column order.
- [x] Make historical relabeling conservative by producing separate post-hoc inference output with confidence instead of overwriting original quality labels.
- [x] Define clear rules for ML exclusion, interpolation, and operational alerting.

### 2.2 Non-Goals
- Do not assume every `Temperature` gap is SPOT equipment downtime.
- Do not use `Speed > 0` alone as proof that a product is present at the SPOT target.
- Do not use a fixed 30 second idle threshold as the sole no-target rule.
- Do not change the semantics of existing CSV columns in-place without schema versioning.
- Do not write `temperature_status` or `extruder_process_state` as operational truth until shadow logging is validated on the server PC.
- Do not implement segment-level post-hoc labels in the append-only realtime CSV writer.

## 3. Scope

### 3.1 In Scope
- Backend data model design for:
  - `extruder_process_state_online`
  - `extruder_process_state_inferred`
  - concept `spot_target_state`; realtime field `spot_target_state_observed_shadow`
  - concept `temperature_status`; realtime field `temperature_status_shadow`
  - `spot_poll_status`
  - `spot_raw_validity`
  - `spot_cache_status`
  - `spot_source_freshness`
  - `cache_fallback_allowed`
  - `temperature_value_origin`
  - SPOT raw value validity and error code fields
- CSV v2.3.0 schema extension plan.
- Compatibility mapping for existing `Temperature_quality` and `Temperature_missing_reason`.
- Conservative historical inference output for existing CSV files.
- Test and validation plan for row-level status derivation and segment-level state machines.
- Server-PC operational verification requirements.
- Schema rollover requirements when v2.3.0 columns are enabled.

### 3.2 Out of Scope
- SPOT hardware changes.
- PLC address mapping changes beyond reading already available process signals.
- Full ML pipeline implementation.
- Retrospective overwrite of existing raw CSV files.
- UI dashboard changes unless later required for operator visibility.
- Switching production alerting or ML preprocessing to new labels before shadow validation.

## 4. Success Criteria

These criteria are split to avoid implying that development-PC instrumentation completion is the same as server-PC operational approval.

### 4.1 Local Instrumentation Criteria

- [x] `Temperature` gaps caused by no SPOT target are distinguishable from source failures in shadow fields when verified SPOT evidence exists.
- [x] `source_error`, `stale`, `invalid_value`, `startup_pending`, and `unknown_missing` are separately representable.
- [x] Existing v2 fields are preserved, and v2.3.0 appends shadow fields only after schema/header guardrails.
- [x] Historical CSV relabeling uses separate post-hoc batch inference output with confidence, not destructive mutation.
- [x] Production-moving gaps are not automatically labeled source failures unless SPOT evidence supports that conclusion.
- [x] Billet-change pauses can be represented without misclassifying valid low-temperature readings as poor quality.
- [x] Online CSV rows do not contain labels that depend on future rows.
- [x] Existing v2.2 files cannot receive v2.3 rows with a different column count.
- [x] Legacy `Temperature_missing_reason` policy is explicit for shadow mode and any later operational schema.
- [x] v2.3.0 shadow fields cannot be treated as operational truth; operational fields must be added in v2.4.0+.
- [x] Fresh or stale transport failures reuse cache only when `cache_fallback_allowed=true`; stale success, invalid, no-target, or non-fallback snapshots suppress TTL-valid cache values.
- [x] Tests cover startup, no-target classification safeguards, valid paused temperature, invalid sentinel, timeout, stale cache, and unknown missing cases.

### 4.2 Operational Promotion Criteria

- [ ] Actual server-PC SPOT raw responses are captured for active extrusion, billet-change pause, no target, startup, and poller/network failure.
- [ ] Server-PC poll interval and jitter are measured and used to calibrate `poll_freshness_threshold`.
- [ ] Downstream v2.3.0 consumer compatibility is verified, including exact-column-count readers.
- [ ] Legacy `Temperature_missing_reason` operational remapping policy is approved.
- [ ] v2.4.0+ operational fields are designed before any shadow label is promoted to operational truth.
## 5. Schedule

| Phase | Target Date | Status |
|-------|------------|--------|
| Plan | 2026-06-22 | Completed |
| Design | 2026-06-22 | Conditionally Approved - Instrumentation Only |
| Implementation | 2026-06-23 | Completed - Local Instrumentation Only |
| Review | 2026-06-23 | Completed - Local Check; Operational Promotion Pending |

## 6. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| `Speed > 0` mislabels SPOT target presence | High | High | Keep `extruder_process_state` and `spot_target_state` separate |
| Idle-looking rows with valid SPOT temperature become false no-target | High | High | Use state machine and SPOT evidence, not a single idle threshold |
| Historical data is over-reclassified | Medium | Medium | Add inferred fields with confidence and rule version |
| Existing CSV consumers break on schema changes | High | Medium | Append fields, bump schema version, and force schema rollover |
| Raw SPOT failure reason is lost before CSV write | High | High | Capture raw value, validity, and error code before validation |
| Future context leaks into realtime CSV labels | High | Medium | Write online state only; calculate segment labels in post-hoc inference |
| SPOT poll error is confused with still-valid cached temperature | High | Medium | Store poll status, cache status, cache fallback allowance, and value origin separately |
| Stale poller snapshot revives cache without a transport-failure fallback basis | High | Medium | Require `cache_fallback_allowed=true` transport failure for reuse; otherwise emit `available_not_used` or `stale` |
| v2.3 rows append to v2.2 file | High | Medium | Force schema rollover or reject append on header mismatch |
| `no_target` is assumed without device evidence | High | Medium | Treat unverified cases as `unknown_missing` or inferred candidates |
| Operational alerts include normal no-target periods | Medium | High | Alert only on validated target-present source failures and poll failure duration |

## 7. References

- `backend/FacilityData/repository.py`
- `backend/FacilityData/schemas.py`
- `backend/FacilityData/drivers/real_plc.py`
- `backend/FacilityData/drivers/spot_api.py`
- `backend/constants.py`
- Dataset `spot-temperature-gap-20260619-20260620`
  - `Factory_Integrated_Log_v2_20260619_195704.csv`: SHA256 `AA708210E2D60D7E68895BAB13F3CD6C731F835E0E5D04543C12E697493C83A0`
  - `Factory_Integrated_Log_v2_20260620_000000.csv`: SHA256 `DFD988624D11A0CDF585D45B8A337D1DBC4A057507006FDD0567CF856913E634`
  - `Factory_Integrated_Log_v2_20260619_195704.metadata.json`: SHA256 `261EA580E55267A197E6ED8923E6467AED8DEAE4ABDD10C11F4645130F843B32`
  - `Factory_Integrated_Log_v2_20260620_000000.metadata.json`: SHA256 `8D69FD5165ACEB0BDCC184A60A4DB1DFAF0750698B060C79033A1AEE517DE71F`

## 8. Approval Gate

Current status: conditionally approved for instrumentation and shadow logging. v2.3.0 is limited to shadow/instrumentation fields. Operational truth promotion requires server-PC validation, downstream consumer compatibility validation, and new operational fields in v2.4.0+.

Do implementation is limited to:

- Raw SPOT observation capture.
- Poll/cache/value-origin/source-freshness/cache-fallback diagnostics.
- Schema rollover guardrails.
- Separate post-hoc batch inference output.
- No inferred segment fields are written into realtime append-only CSV rows.

Do not switch operational alerts, ML preprocessing, or legacy quality mapping to the new labels until server-PC evidence confirms the SPOT no-target response semantics.

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
