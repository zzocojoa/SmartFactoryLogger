# Gap Analysis: SPOT Temperature v2.4 Operational Hardening

> Date: 2026-07-11 | Scope: Stage 4 - Quality and Value Age
> Design: `docs/02-design/features/spot-temperature-v2-4-operational-hardening.design.md`

## Match Rate: 100% (Stage 4 scope)

이 문서는 Stage 4 범위만 분석한다. Stage 5가 남아 있으므로 전체 feature는 완료 상태가 아니며 PDCA phase는 `Do`를 유지한다.

## Implemented Items

- [x] hardening flag 기본 false와 operational flag dependency
- [x] v2.5 schema/header/sidecar contract
- [x] v2.4에서 v2.5로 별도 파일 rollover
- [x] operational status 기반 legacy Temperature quality 정합화
- [x] blank Temperature와 `ok/not_missing` 조합 차단
- [x] last-valid monotonic clock의 driver/RealPLC/FactoryData 전파
- [x] monotonic 우선 value-age와 UTC fallback
- [x] negative/non-finite clock anomaly fail-closed
- [x] value-age clock anomaly bounded health counter
- [x] v2.5 validator와 replay consumer 호환

## Acceptance Evidence

| Design test | Result | Evidence |
|---|---|---|
| Q-01 v2.5 valid current/cached | PASS | finite Temperature, `ok/not_missing` |
| Q-02 under/over range | PASS | blank Temperature, `invalid/invalid_value` |
| Q-03 stale | PASS | blank Temperature, `stale/stale_snapshot` |
| Q-04 source error | PASS | blank Temperature, `missing/source_error` |
| Q-05 startup/unknown | PASS | `missing/source_missing`, `unknown/source_missing` |
| Q-06 monotonic exact delta | PASS | explicit snapshot age 무시, finite non-negative age와 `ok` |
| Q-07 UTC fallback | PASS | monotonic source가 없을 때만 timestamp delta 사용 |
| Q-08 clock anomaly | PASS | monotonic/UTC 음수 모두 blank age와 `clock_anomaly` |
| Q-09 age source 없음 | PASS | blank age와 `unknown` |
| Q-10 v2.4 보존 | PASS | 기존 header, legacy quality, explicit value age 유지 |
| Q-11 v2.4→v2.5 rollover | PASS | CSV와 sidecar가 schema별로 분리됨 |
| Q-12 invalid flag 조합 | PASS | startup/runtime 모두 fail-closed, runtime config 부분 적용 없음 |
| V-01 blank + quality ok | PASS | v2.5 validator가 거부 |
| V-02 anomaly + nonblank age | PASS | v2.5 validator가 거부 |

## Correctness and Security Review

- monotonic timestamp는 `FactoryData.model_dump()`에서 제외해 외부 API나 persisted payload에 process-local clock 값을 노출하지 않는다.
- source monotonic 값이 존재하지만 invalid/negative/non-finite이면 wall-clock으로 우회하지 않고 `clock_anomaly`로 차단한다.
- v2.5 metadata는 실제 header의 canonical SHA-256과 active schema를 validator에서 교차 검증한다.
- hardening flag validation은 runtime config의 다른 값을 변경하기 전에 실행해 실패 시 부분 적용을 방지한다.
- health에는 raw timestamp나 장비 식별자를 추가하지 않고 anomaly count만 노출한다.
- 비공개 설정값, external URL 또는 사용자 식별정보를 새로 기록하지 않는다.

## Deviations and Decisions

- v2.3/v2.4의 기존 value-age와 quality 의미는 호환성 때문에 유지하고 v2.5에서만 강화했다.
- `spot_value_age_clock_status`는 v2.4 header에 넣지 않고 v2.5 마지막 열로 추가했다.
- 프로세스 재시작 후 monotonic clock은 복원하지 않는다. 이때 wall-clock timestamp가 있으면 fallback하고 없으면 `unknown`이다.
- invalid sentinel은 cache suppression 상태를 유지하되 last-valid 시각은 감사용으로 보존한다. verified no-target만 wall/monotonic 시각을 함께 제거한다.
- 전체 feature 자동 gap analysis는 Stage 5 완료 전 PDCA를 `Check`로 이동시키므로 실행하지 않았다. 현재 분석은 Stage 4 scoped audit다.

## Validation

- Targeted Stage 4 pytest: `262 passed, 38 subtests passed`
- Full repository health: PASS
  - Frontend: typecheck/lint, `27 files / 202 tests`
  - Backend: ruff/mypy, `494 tests OK`
- Full v2.5 producer→sidecar→validator path: PASS
- v2.5 rollover replay consumer: PASS
- Python compile와 `git diff --check`: final publish gate에서 재확인
- Windows packaged artifact: PR CI merge gate에서 확인 예정

## Remaining Items

- Stage 5: v2.3/v2.4/v2.5 writer-validator matrix
- Stage 5: controlled replay, rollback drill, package build
- Stage 5: 전체 feature gap analysis와 final report

## Recommendation

Stage 4를 별도 PR로 검토한다. Windows Release Artifact check가 PASS한 뒤 merge하며, 전체 feature 완료 처리는 Stage 5 종료 후 수행한다.
