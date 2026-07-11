# Gap Analysis: SPOT Temperature v2.4 Operational Hardening

> Date: 2026-07-11 | Scope: Stage 3 - Config and Evidence
> Design: `docs/02-design/features/spot-temperature-v2-4-operational-hardening.design.md`

## Match Rate: 100% (Stage 3 scope)

이 문서는 Stage 3 범위만 분석한다. Stage 4~5가 남아 있으므로 전체 feature는 완료 상태가 아니며 PDCA phase는 `Do`를 유지한다.

## Implemented Items

- [x] 운영자 검증 기본값 false
- [x] canonical config fingerprint와 constant-time 비교
- [x] 승인 시각·운영자 ID·승인 fingerprint 필수화
- [x] build/settings/SPOT 설정 변경 시 attestation 자동 무효화
- [x] readback mismatch/partial/not-attempted/error fail-closed
- [x] effective comparator verification을 config attestation과 결합
- [x] collector 없는 cause evidence 승격 차단
- [x] realtime/image fact/validator 동일 gate 적용
- [x] drift와 unsupported suppression bounded health counter

## Acceptance Evidence

| Design test | Result | Evidence |
|---|---|---|
| G-01 신규 배포 metadata 없음 | PASS | operator/comparator verification false |
| G-02 exact fingerprint + valid by/at | PASS | effective verification true |
| G-03 SPOT IP 변경 | PASS | fingerprint mismatch, verification false |
| G-04 app mode/threshold/comparator/Peak Picker 변경 | PASS | 모든 변경에서 verification false |
| G-05 build commit/settings 변경 | PASS | fingerprint mismatch, settings attestation 항목은 순환 제외 |
| G-06 readback mismatch/error | PASS | fail-closed와 drift field 기록 |
| G-07 Peak Picker config-only | PASS | evidence 보존, candidate unknown |
| G-08 Actuator/FOV/Range 문자열 주입 | PASS | evidence 보존, candidate unknown, validator 거부 |

## Security Review

- fingerprint는 lowercase SHA-256이며 비교는 `hmac.compare_digest`를 사용한다.
- settings canonical hash에서 password/token/credential/auth 계열 키를 제외하고, fingerprint payload와 health counter에 비밀값을 추가하지 않았다.
- 운영자 ID는 128자 이하의 제한된 비식별 문자 집합만 허용하며 이메일 형태는 허용하지 않는다.
- health에는 IP, operator ID, raw diagnostics를 노출하지 않는다.
- 설정 파일 hash는 canonical 내용의 hash만 기록하며 원문 설정값은 추가로 노출하지 않는다.

## Deviations and Decisions

- device config readback collector는 이번 단계에서 구현하지 않았다. 실제 지원 증거가 없으므로 상태를 `not_supported`로 기록하고 `matched`를 생성하지 않는다.
- attestation 항목은 canonical settings hash에서 제외했다. 그렇지 않으면 승인 fingerprint를 config 파일에 쓰는 행위가 fingerprint 자체를 변경해 고정점이 존재하지 않는다.
- unsupported enum과 fact evidence는 호환성·감사를 위해 유지하고 causal promotion만 차단했다.
- 원인 판정 rule을 `temperature-operational-v4`로 올렸으며 v3 sidecar/row는 legacy 호환 경로로 검증한다.
- GitHub review P2에 따라 `device_config_readback_status=matched`는 nonblank current device fingerprint가 일치할 때만 validator가 허용한다.
- 전체 feature 자동 gap analysis는 Stage 4~5 완료 전 PDCA를 `Check`로 이동시키므로 실행하지 않았다. 현재 분석은 Stage 3 scoped audit다.

## Validation

- Targeted Stage 3 pytest: `284 passed, 52 subtests passed`
- Full repository health: PASS
  - Frontend: typecheck/lint, `27 files / 202 tests`
  - Backend: ruff/mypy, `481 tests OK`
- Python compile: PASS
- `git diff --check`: PASS
- Windows packaged artifact: PR CI merge gate에서 확인 예정

## Remaining Items

- Stage 4: legacy Temperature quality와 operational status 정합화
- Stage 4: monotonic `spot_effective_value_age_ms_at_row`와 clock status
- Stage 5: 전체 feature gap analysis, controlled verification, final report

## Recommendation

Stage 3을 별도 PR로 검토한다. Windows Release Artifact check가 PASS한 뒤 merge하며, 전체 feature 완료 처리는 Stage 4~5 종료 후 수행한다.
