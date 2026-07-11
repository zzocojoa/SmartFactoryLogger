# SPOT Temperature v2.4 Operational Hardening - Do Tracking

> Version: 1.4.0 | Date: 2026-07-11 | Status: Completed
> Stage 5 baseline: `master@9cf96f8ba42f408119808537a4ff66de2e979658`
> Completed scope: Stage 0 - Contract Freeze through Stage 5 - Controlled Verification

## 1. Stage Status

| Stage | Status | Scope |
|---|---|---|
| Stage 0 - Contract Freeze | Completed | Plan/Design 승인 |
| Stage 1 - Cache and Comparator | Completed | Cache fallback와 comparator 검증 |
| Stage 2 - Diagnostics Integrity | Completed | Same-poll binding, completeness, age, fact provenance |
| Stage 3 - Config and Evidence | Completed | Config attestation, drift, unsupported evidence 차단 |
| Stage 4 - Quality and Value Age | Completed | v2.5 quality/value-age 계약 |
| Stage 5 - Controlled Verification | Completed | 전체 feature 완료 게이트 |

Stage 5까지 구현·검증되어 Do phase를 완료하고 전체 gap analysis인 Check로 이동했다.

## 2. Stage 3 구현

### 2.1 Config attestation

- `DEFAULT_SPOT_CONFIG_OPERATOR_VERIFIED=false`로 변경했다.
- `spot_config_provenance.py`에 canonical fingerprint builder를 추가했다.
- fingerprint 입력은 valid build commit, sanitized canonical settings hash, SPOT IP/model/app mode, range, analog mapping, Low Signal, Peak Picker, limiter, averager, modemaster, ratio, obscuration, focus, diagnostics mode다.
- fingerprint는 정렬된 compact JSON의 lowercase SHA-256이다.
- `config.ini`의 attestation 항목은 settings hash에서 제외해 승인 fingerprint를 설정할 때 발생하는 순환 변경을 방지한다. Password/token/credential 계열 키도 hash 입력에서 제외해 저엔트로피 비밀값의 offline 추측 위험을 피한다.
- 다음 조건을 모두 만족할 때만 `config_operator_verified=true`가 된다.
  - `SPOT_CONFIG_OPERATOR_VERIFIED=true`
  - 유효한 UTC `SPOT_CONFIG_VERIFIED_AT`
  - 제한된 형식의 비식별 `SPOT_CONFIG_VERIFIED_BY`
  - lowercase SHA-256 `SPOT_CONFIG_VERIFIED_FINGERPRINT_SHA256`
  - valid lowercase 40-hex build commit
  - 승인 fingerprint와 현재 fingerprint의 constant-time 일치
  - device readback 상태가 blocking 상태가 아님
- `low_signal_comparator_verified`는 configured comparator verification과 effective operator verification이 모두 참일 때만 참이다.
- 실제 readback collector가 아직 없으므로 runtime 상태는 `not_supported`이며 `matched`를 위조하지 않는다.

### 2.2 Drift 감지

- build commit, settings, SPOT IP, app mode, threshold, comparator, Peak Picker 등 fingerprint 입력이 변경되면 기존 attestation은 자동 해제된다.
- 누락·손상 attestation, fingerprint mismatch, readback mismatch/partial/not-attempted/error는 fail-closed다.
- sidecar `spot_configuration_snapshot`에 revision, current/verified fingerprint, verified at/by, readback status, drift flag/fields를 기록한다.
- health에는 값이나 IP를 label로 노출하지 않고 `config_drift_detected_count`와 bounded status만 노출한다.

### 2.3 미수집 evidence 차단

- 다음 candidate enum/schema는 호환성을 위해 유지한다.
  - `peak_picker_reset_candidate`
  - `alignment_change_candidate`
  - `target_out_of_fov_candidate`
  - `below_measurement_range_candidate`
- 현재 provenance-capable collector가 없는 Peak Picker/Actuator/FOV/Range evidence는 raw fact와 evidence code에 보존한다.
- 해당 evidence만으로 realtime 또는 image fact cause candidate를 승격하지 않고 `unknown`으로 강등한다.
- Low Signal은 Stage 2의 same-poll, age, field completeness, comparator attestation gate를 계속 만족할 때만 승격한다.
- validator는 unsupported cause candidate를 현재 계약에서 거부한다.
- `unsupported_evidence_suppressed_count`로 차단 행 수를 집계한다.
- 원인 판정 변경을 식별하도록 rule version을 `temperature-operational-v4`로 올리고, v3 artifact는 legacy validation 경로로 계속 읽는다.

## 3. Stage 4 구현

### 3.1 v2.5 원자적 계약

- `CSV_V2_TEMPERATURE_HARDENING_ENABLED`를 기본 false로 추가했다.
- hardening flag는 `CSV_V2_OPERATIONAL_FIELDS_ENABLED=true`를 요구하며 startup과 runtime config 적용 모두 fail-closed다.
- v2.5는 v2.4 뒤에 `spot_value_age_clock_status` 한 열만 추가한다.
- contract 변경 시 writer를 닫고 별도 v2.5 CSV와 sidecar를 열며 기존 v2.4 header에는 append하지 않는다.
- sidecar에 active schema/column hash, hardening flag, operational rule과 quality mapping version을 기록한다.

### 3.2 Temperature quality 정합화

- v2.5에서는 operational status 확정 후 `Temperature_quality`와 `Temperature_missing_reason`을 매핑한다.
- valid는 `ok/not_missing`, under/over-range는 `invalid/invalid_value`, stale은 `stale/stale_snapshot`이다.
- source error는 `missing/source_error`, startup은 `missing/source_missing`, unknown은 `unknown/source_missing`이다.
- blank `Temperature`와 `ok/not_missing` 조합은 v2.5 validator가 거부한다.
- v2.3/v2.4 quality 의미와 header는 변경하지 않았다.

### 3.3 Monotonic value age

- SPOT driver는 마지막 valid value의 wall-clock과 monotonic 완료 시각을 함께 보존한다.
- invalid sentinel은 마지막 valid 시각을 감사용으로 유지하고, verified no-target은 두 시각을 모두 지운다.
- repository는 v2.5 row에서 monotonic delta를 우선 계산하고 monotonic source가 없을 때만 UTC timestamp로 fallback한다.
- 음수·비유한 age는 값을 비우고 `clock_anomaly`, 두 source가 모두 없으면 `unknown`으로 기록한다.
- health에 `value_age_clock_anomaly_count`를 추가했다.
- replay consumer는 v2.5 rollover 파일과 새 clock status를 읽는다.

## 4. 운영 절차

1. 새 build를 `SPOT_CONFIG_OPERATOR_VERIFIED=false`로 기동한다.
2. sidecar의 `spot_config_fingerprint_sha256`와 장비 설정을 확인한다.
3. 검증 후 승인 시각, 운영자 식별자, 확인한 fingerprint를 설정한다.
4. `SPOT_CONFIG_OPERATOR_VERIFIED=true`로 재기동한다.
5. sidecar에서 `config_attestation_status=verified`, `config_operator_verified=true`를 확인한다.

설정 또는 build가 바뀌면 1~5를 다시 수행한다. 승인 metadata 자체는 canonical settings hash에서 제외된다.

## 5. Stage 5 검증

### 5.1 Writer-validator matrix

- 실제 `CSVLoggerService` writer로 v2.3, v2.4, v2.5 행과 sidecar를 생성했다.
- 세 contract 모두 exact header/row length/schema metadata를 확인하고 full shadow validator를 통과했다.
- v2.4/v2.5는 실제 observation fact를 기록하고 manifest를 갱신했다.

### 5.2 Controlled replay와 rollback

- Sanitized v2.5 artifact의 full validator 결과는 invariant violation 0건이다.
- Realtime observation key 1건과 fact key 1건이 연결되어 link coverage 100%를 확인했다.
- `CsvReplayDriver`가 v2.5 Temperature와 value-age clock status를 재생했다.
- Hardening flag를 끈 rollback drill에서 기존 v2.5 CSV/sidecar byte가 바뀌지 않고 새 v2.4 파일과 sidecar가 열렸다.

### 5.3 Package와 전체 health

- Clean PyInstaller one-file build가 squash baseline `9cf96f8ba42f408119808537a4ff66de2e979658`를 시작·완료 시점에 동일하게 검증했다.
- Embedded `backend/build_provenance.json`과 validator resource를 archive에서 직접 확인했다.
- EXE SHA-256은 `8320ce0464c53dcd56b80256b1e99280a6cd23920a0212ac15d1d4f8d631f0ad`이다.
- Targeted suite, full health, compile, diff check와 added-line sensitive scan을 통과했다.

## 6. Files Changed

### Production

- `.gitignore`
- `backend/config.py`
- `backend/FacilityData/spot_config_provenance.py`
- `backend/FacilityData/drivers/spot_api.py`
- `backend/FacilityData/drivers/real_plc.py`
- `backend/FacilityData/drivers/csv_replay.py`
- `backend/FacilityData/schemas.py`
- `backend/FacilityData/repository.py`
- `backend/FacilityData/service.py`
- `backend/FacilityData/temperature_operational.py`
- `backend/FacilityData/spot_image_fact.py`
- `scripts/validate_csv_v2_shadow.py`

### Tests

- `backend/tests/test_spot_config_provenance.py`
- `backend/tests/test_temperature_operational.py`
- `backend/tests/test_spot_api.py`
- `backend/tests/test_real_plc.py`
- `backend/tests/test_csv_replay_driver.py`
- `backend/tests/test_csv_v2_4_operational_contract.py`
- `backend/tests/test_spot_temperature_stage5_verification.py`

### PDCA

- `docs/02-design/features/spot-temperature-v2-4-operational-hardening.do.md`
- `docs/03-analysis/spot-temperature-v2-4-operational-hardening.analysis.md`
- `docs/04-report/spot-temperature-v2-4-operational-hardening.report.md`

## 7. Validation

- Stage 3 targeted pytest: `284 passed, 52 subtests passed`
- Stage 4 targeted pytest: `262 passed, 38 subtests passed`
- Stage 5 controlled verification: `3 passed, 3 subtests passed`
- Stage 5 targeted pytest: `381 passed, 87 subtests passed`
- Frontend typecheck/lint: PASS
- Frontend tests: `27 files, 202 tests` PASS
- Backend ruff/mypy: PASS
- Backend unittest: `497 tests OK`
- Python compile: PASS
- `git diff --check`: PASS
- Added-line sensitive scan: `0 hits`
- Local clean PyInstaller build와 embedded provenance 검증: PASS
- PR #164 Windows Release Artifact workflow: PASS

## 8. Compatibility and Failure Modes

- v2.3/v2.4 realtime CSV header와 quality 의미는 변경하지 않았다.
- v2.5는 hardening flag가 켜진 경우에만 별도 파일로 생성된다. exact-column-count consumer는 v2.5 지원이 필요하다.
- invalid flag 조합, 음수/non-finite clock delta, header mismatch는 fail-closed다.
- Database migration과 배포 migration은 없다.
- 누락·손상·불일치 provenance는 `config_operator_verified=false`와 numeric comparator cause 차단으로 귀결된다.
- 미수집 evidence는 삭제하지 않고 fact에 남기므로 사후 조사 가능성은 유지된다.
- Future collector를 활성화하려면 typed field, source, captured-at, age, binding, completeness, validator test를 함께 추가해야 한다.

## 9. Rollback

- `spot_config_provenance.py`, config attestation 설정, driver/repository snapshot 통합을 함께 revert한다.
- unsupported cause gate와 validator 규칙을 함께 revert해야 producer/validator 계약이 어긋나지 않는다.
- 안전한 운영 rollback은 `SPOT_CONFIG_OPERATOR_VERIFIED=false`를 유지하는 것이다. 이 경우 numeric comparator cause는 비활성화되고 원인은 `unknown`으로 강등된다.
- CSV migration은 필요하지 않다.
- Stage 4 운영 rollback은 hardening flag를 끄고 새 v2.4 파일로 rollover하는 것이다. 기존 v2.5 파일은 수정하지 않는다.

## 10. Remaining Work

- 구현 gap은 없다.
- Production enablement는 범위 밖이며 v2.5 hardening flag 기본값은 false다.
- Stage 5 verification PR의 review/merge는 별도 승인 gate다.
