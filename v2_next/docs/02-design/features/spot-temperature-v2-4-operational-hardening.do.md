# SPOT Temperature v2.4 Operational Hardening - Do Tracking

> Version: 1.1.0 | Date: 2026-07-10 | Status: In Progress
> Stage 2 baseline: `master@218b57b5ea96588b742f7a25560c8188df07cc65`
> Completed scope: Stage 1 - Cache and Comparator, Stage 2 - Diagnostics Integrity

## 1. Stage Status

| Stage | Status | Scope |
|---|---|---|
| Stage 0 - Contract Freeze | Completed | Plan/Design 승인 |
| Stage 1 - Cache and Comparator | Completed | Cache fallback와 comparator verification |
| Stage 2 - Diagnostics Integrity | Completed | Same-poll binding, completeness, age, fact provenance |
| Stage 3 - Config and Evidence | Pending | Config attestation, drift, unsupported evidence |
| Stage 4 - Quality and Value Age | Pending | v2.5 quality/value-age 계약 |
| Stage 5 - Controlled Verification | Pending | 전체 feature 완료 게이트 |

Stage 3~5가 남아 있으므로 PDCA Do phase는 active 상태를 유지한다.

## 2. Implemented Behavior

### 2.1 Stage 1 - Cache and Comparator

- TTL-valid transport cache fallback을 operational `valid/cached_observation` 계약과 일치시켰다.
- Stale, clock anomaly, sentinel, origin mismatch는 fail-closed 한다.
- Numeric Low Signal은 `low_signal_comparator_verified=true`일 때만 causal evidence로 사용한다.
- `alarmstatus` bit 4는 comparator와 무관한 authoritative evidence로 유지한다.

### 2.2 Stage 2 - Diagnostics Integrity

- `SpotPollContext`와 immutable `DiagnosticSnapshot`을 추가했다.
- 8개 비동기 output 요청에 source poll sequence, snapshot identity, capture status, per-field status와 missing fields를 기록한다.
- Temperature 요청은 diagnostics 완료를 기다리지 않는다.
- 완료된 snapshot은 `same_poll`, `previous_poll`, `future_clock`, `unbound`, `missing`으로 결합 상태를 계산한다.
- Cause 승격은 causal collection mode, same-poll identity, bounded non-negative age, required field success/value 존재를 모두 요구한다.
- `async_partial`은 원인에 필요한 필드가 성공한 경우만 허용하며, 관련 필드 실패는 차단한다.
- 검증되지 않은 parameter GET 기본 mode는 `async_fact_only`로 고정해 raw fact만 보존하고 cause 승격은 금지한다.
- Legacy `async_enriched`, late completion, previous poll, stale/future-clock snapshot은 causal use를 차단한다.
- `TEMPERATURE_OPERATIONAL_RULE_VERSION`은 `temperature-operational-v3`이다.

## 3. Observation Fact and Validator

- Observation fact schema를 `1.3.0`으로 갱신했다.
- Snapshot ID, source poll, binding, missing fields, field status, source mode, evidence provenance를 추가했다.
- Manifest에 capture/binding/missing-field counts와 provenance coverage를 추가했다.
- Validator는 current `1.3.0`을 strict 검증하고 historical `1.2.1` exact header를 계속 읽는다.
- Realtime causal evidence는 fact의 same-poll identity, causal mode, bounded age, successful field provenance와 일치해야 한다.
- Realtime CSV `2.4.0` header와 column list는 변경하지 않았다.

## 4. Observability

`get_v2_4_operational_summary()`에 다음 bounded aggregate를 추가했다.

- `diagnostics_capture_status_counts`
- `diagnostics_binding_status_counts`
- `diagnostics_cause_suppressed_count`
- `diagnostics_cause_suppressed_reason_counts`

URL, IP, raw diagnostic value와 unbounded identifier는 health aggregate label로 노출하지 않는다.

## 5. Stage 2 Files Changed

### Production

- `backend/FacilityData/spot_diagnostics.py`
- `backend/FacilityData/drivers/spot_api.py`
- `backend/FacilityData/drivers/real_plc.py`
- `backend/FacilityData/schemas.py`
- `backend/FacilityData/temperature_operational.py`
- `backend/FacilityData/repository.py`
- `backend/FacilityData/spot_observation_fact.py`
- `scripts/validate_csv_v2_shadow.py`

### Tests

- `backend/tests/test_temperature_operational.py`
- `backend/tests/test_spot_api.py`
- `backend/tests/test_spot_observation_fact.py`
- `backend/tests/test_csv_v2_4_operational_contract.py`
- `backend/tests/test_real_plc.py`

## 6. Validation

- Stage 2 related six-file pytest suite: `301 passed, 45 subtests passed`
- D-01~D-10 diagnostics scenarios: PASS
- Historical fact `1.2.1` read compatibility: PASS
- Realtime `2.4.0` header unchanged: covered by contract tests
- Backend ruff/mypy: PASS
- Backend unittest: `466 tests OK`
- Frontend typecheck/lint: PASS
- Frontend tests: `27 files, 202 tests` PASS
- Python compile: PASS
- Final diff review: Critical 0 / Major 0 / Minor 0 / Approve

## 7. Compatibility and Failure Modes

- Realtime CSV schema/migration: 없음.
- Observation fact writer는 header mismatch 시 기존 `1.2.1` 파일을 archive하고 새 `1.3.0` 파일을 연다.
- Diagnostics 실패·지연은 Temperature poll status와 latency path를 차단하지 않는다.
- Missing, malformed, partial-required, stale, previous-poll diagnostics는 raw fact를 보존하되 cause를 `unknown`으로 유지한다.
- Atomic `/output` mode는 capability evidence가 없어 활성화하지 않았다.

## 8. Rollback

Stage 2 rollback은 diagnostics promotion을 전부 disable하고 `async_fact_only` raw fact 수집만 유지한다. Poll context, operational gate, fact `1.3.0`, validator 변경은 함께 revert해야 writer와 validator schema가 어긋나지 않는다. 생성된 `1.3.0` fact artifact는 삭제하거나 `1.2.1`로 재작성하지 않는다.

## 9. Remaining Work

다음 단계는 Stage 3이다. Config attestation과 drift detection을 구현하고, 실제 collector가 없는 cause evidence promotion을 차단한다. Stage 4의 legacy quality/value-age 변경은 realtime schema `2.5.0`에서 별도로 처리한다.
