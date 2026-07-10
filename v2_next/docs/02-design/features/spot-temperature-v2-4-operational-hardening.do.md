# SPOT Temperature v2.4 Operational Hardening - Do Tracking

> Version: 1.2.0 | Date: 2026-07-11 | Status: In Progress
> Stage 3 baseline: `master@e42d75f66a3eacdd6f6f58fafc68a6b46a2b38f9`
> Completed scope: Stage 1 - Cache and Comparator, Stage 2 - Diagnostics Integrity, Stage 3 - Config and Evidence

## 1. Stage Status

| Stage | Status | Scope |
|---|---|---|
| Stage 0 - Contract Freeze | Completed | Plan/Design 승인 |
| Stage 1 - Cache and Comparator | Completed | Cache fallback와 comparator 검증 |
| Stage 2 - Diagnostics Integrity | Completed | Same-poll binding, completeness, age, fact provenance |
| Stage 3 - Config and Evidence | Completed | Config attestation, drift, unsupported evidence 차단 |
| Stage 4 - Quality and Value Age | Pending | v2.5 quality/value-age 계약 |
| Stage 5 - Controlled Verification | Pending | 전체 feature 완료 게이트 |

Stage 4~5가 남아 있으므로 전체 PDCA phase는 `Do`를 유지한다.

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

## 3. 운영 절차

1. 새 build를 `SPOT_CONFIG_OPERATOR_VERIFIED=false`로 기동한다.
2. sidecar의 `spot_config_fingerprint_sha256`와 장비 설정을 확인한다.
3. 검증 후 승인 시각, 운영자 식별자, 확인한 fingerprint를 설정한다.
4. `SPOT_CONFIG_OPERATOR_VERIFIED=true`로 재기동한다.
5. sidecar에서 `config_attestation_status=verified`, `config_operator_verified=true`를 확인한다.

설정 또는 build가 바뀌면 1~5를 다시 수행한다. 승인 metadata 자체는 canonical settings hash에서 제외된다.

## 4. Files Changed

### Production

- `.gitignore`
- `backend/config.py`
- `backend/FacilityData/spot_config_provenance.py`
- `backend/FacilityData/drivers/spot_api.py`
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
- `backend/tests/test_csv_v2_4_operational_contract.py`

## 5. Validation

- Stage 3 targeted pytest: `283 passed, 50 subtests passed`
- Frontend typecheck/lint: PASS
- Frontend tests: `27 files, 202 tests` PASS
- Backend ruff/mypy: PASS
- Backend unittest: `480 tests OK`
- Python compile: PASS
- `git diff --check`: PASS
- Local PyInstaller build: 미실행, PR의 Windows Release Artifact check를 merge gate로 사용

## 6. Compatibility and Failure Modes

- Realtime CSV header와 schema version은 변경하지 않았다.
- Database migration과 배포 migration은 없다.
- 누락·손상·불일치 provenance는 `config_operator_verified=false`와 numeric comparator cause 차단으로 귀결된다.
- 미수집 evidence는 삭제하지 않고 fact에 남기므로 사후 조사 가능성은 유지된다.
- Future collector를 활성화하려면 typed field, source, captured-at, age, binding, completeness, validator test를 함께 추가해야 한다.

## 7. Rollback

- `spot_config_provenance.py`, config attestation 설정, driver/repository snapshot 통합을 함께 revert한다.
- unsupported cause gate와 validator 규칙을 함께 revert해야 producer/validator 계약이 어긋나지 않는다.
- 안전한 운영 rollback은 `SPOT_CONFIG_OPERATOR_VERIFIED=false`를 유지하는 것이다. 이 경우 numeric comparator cause는 비활성화되고 원인은 `unknown`으로 강등된다.
- CSV migration은 필요하지 않다.

## 8. Remaining Work

- Stage 4: legacy Temperature quality 정합화, monotonic value age, clock status, CSV v2.5 계약
- Stage 5: 전체 feature gap analysis, controlled verification, final report
