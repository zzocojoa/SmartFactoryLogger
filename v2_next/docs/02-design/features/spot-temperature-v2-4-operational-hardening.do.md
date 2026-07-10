# SPOT Temperature v2.4 Operational Hardening - Do Tracking

> Version: 1.0.0 | Date: 2026-07-10 | Status: In Progress
> Baseline: `master@07dd370e22e8bf2c413c4afdc4cf85a30d54d031`
> Completed scope: Stage 1 - Cache and Comparator

## 1. Stage Status

| Stage | Status | Scope |
|---|---|---|
| Stage 0 - Contract Freeze | Completed | Plan/Design 승인 |
| Stage 1 - Cache and Comparator | Completed | 이번 구현 범위 |
| Stage 2 - Diagnostics Integrity | Pending | 미구현 |
| Stage 3 - Config and Evidence | Pending | 미구현 |
| Stage 4 - Quality and Value Age | Pending | 미구현 |
| Stage 5 - Controlled Verification | Pending | 전체 feature 완료 후 |

PDCA Do phase는 Stage 2~4가 남아 있으므로 active 상태를 유지한다.

## 2. Implemented Behavior

### 2.1 Cache Fallback

- `TEMPERATURE_OPERATIONAL_RULE_VERSION`을 `temperature-operational-v2`로 갱신했다.
- State decision이 `OK/REUSED/CACHED_OBSERVATION`이고 transport failure, TTL valid, row/source fresh인 경우 operational status를 `valid`로 유지한다.
- Stale, clock anomaly, under/over-range sentinel은 cached-valid보다 우선한다.
- Non-valid output의 final origin은 `none`이다.
- Input origin과 state origin이 다르면 value를 fail-closed하고 mismatch counter를 증가시킨다.
- Cache fallback accepted/rejected와 rejection reason을 bounded health counter로 노출한다.
- `available_not_used` cache 상태도 TTL cache 존재를 보존해 suppression을 재사용 없이 관측한다.

### 2.2 Comparator Verification

- `low_signal_comparator_verified`를 FactoryData, RealPLC passthrough, repository와 operational input에 추가했다.
- Comparator가 unverified이면 numeric comparison은 수행하지 않고 `signalpc_present_comparator_unverified`를 기록한다.
- `signal_below_threshold`, disabled/at-or-above numeric evidence는 verified=true일 때만 생성한다.
- `alarmstatus bit 4`는 comparator와 무관한 authoritative evidence로 유지한다.
- Realtime/fact 양쪽에서 upstream의 stale numeric evidence를 제거한 뒤 typed input으로 재생성한다.
- Fact validator가 unverified comparator와 causal numeric evidence의 모순을 거부한다.

## 3. Observability

`get_v2_4_operational_summary()`에 다음 bounded 값이 추가됐다.

- `cached_fallback_accepted_count`
- `cached_fallback_rejected_count`
- `cached_fallback_rejected_reason_counts`
- `origin_decision_mismatch_count`
- `comparator_unverified_count`

동적 ID, URL, raw diagnostics 또는 비민감 범위를 벗어난 값을 metric label로 추가하지 않았다.

## 4. Files Changed

### Production

- `backend/FacilityData/spot_low_signal.py`
- `backend/FacilityData/temperature_operational.py`
- `backend/FacilityData/spot_observation_fact.py`
- `backend/FacilityData/schemas.py`
- `backend/FacilityData/drivers/real_plc.py`
- `backend/FacilityData/repository.py`
- `scripts/validate_csv_v2_shadow.py`

### Tests

- `backend/tests/test_temperature_operational.py`
- `backend/tests/test_spot_observation_fact.py`
- `backend/tests/test_real_plc.py`
- `backend/tests/test_spot_api.py`
- `backend/tests/test_csv_v2_4_operational_contract.py`

## 5. Validation

- Targeted Stage 1 tests: PASS
- Related six-file pytest suite: `270 passed, 45 subtests passed`
- Final Stage 1 focused tests after evidence sanitization: `54 passed, 15 subtests passed`
- Backend unittest: `450 tests OK`
- Backend ruff: PASS
- Backend mypy: PASS
- Python compile: PASS
- Frontend typecheck/lint: PASS
- Frontend tests: `27 files, 202 tests` PASS
- Existing invalid-sentinel cache suppression sequence: PASS

## 6. Compatibility and Migration

- Realtime CSV header와 schema version은 변경하지 않았다.
- Observation fact header와 schema version은 변경하지 않았다.
- 기존 v2.3 writer semantics는 유지한다.
- v2.4 operational rule version과 behavior만 수정한다.
- Migration은 필요하지 않다.

## 7. Rollback

Stage 1 rollback은 다음 변경을 함께 revert한다.

1. Operational cached fallback predicate와 origin decision
2. Repository origin/counter 처리
3. Comparator verified 전파와 shared helper
4. Observation fact evidence/validator 변경

부분 rollback으로 classifier와 repository의 cache 의미가 다시 달라지지 않도록 한다. Rollback 시 cached transport fallback은 기존 source_error/blank 동작으로 복귀한다.

## 8. Remaining Work

다음 작업은 Stage 2 diagnostics integrity다. Poll binding, capture completeness, per-field status와 cause eligibility를 구현하기 전에는 기존 async diagnostics를 현재 poll의 atomic evidence로 승격하지 않는다.
