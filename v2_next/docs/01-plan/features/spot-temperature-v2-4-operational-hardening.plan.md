# SPOT Temperature v2.4 Operational Hardening - Plan

> Version: 1.0.0 | Date: 2026-07-10 | Status: Completed
> Level: Dynamic | Baseline: `master@07dd370e22e8bf2c413c4afdc4cf85a30d54d031`
> Implementation authorization: Not granted by this document

---

## 1. Overview

### 1.1 Purpose

SPOT Temperature v2.4 운영 경로에서 확인된 7개 계약 불일치를 작은 패치 단위로 해소한다. 최우선 목표는 허용된 cached fallback을 CSV까지 일관되게 보존하고, 검증되지 않았거나 시점이 맞지 않는 diagnostics가 under-range 원인 후보로 승격되지 않도록 하는 것이다.

### 1.2 Background

`master@07dd370e22e8bf2c413c4afdc4cf85a30d54d031`을 기준으로 `temperature_state.py`, `temperature_operational.py`, `spot_low_signal.py`, SPOT/RealPLC driver, repository, observation fact, validator와 관련 테스트를 검토했다.

현재 state 계층은 TTL 내 cache fallback을 `cached_observation`으로 허용하지만 operational classifier가 transport error를 먼저 반환해 최종 CSV의 Temperature를 비운다. Low Signal 숫자 비교는 `low_signal_comparator_verified=false`를 무시한다. Diagnostics에는 SPOT 계층의 max-age 폐기 로직이 있으나 현재 poll과의 원자적 연결, 필드별 완전성 및 classifier 입력 전달이 부족하다. Config provenance, 일부 cause collector, legacy quality 정합성, monotonic value age도 후속 보강이 필요하다.

기존 `spot-temperature-v2-4-operational-patch` PDCA는 완료 상태이므로 이 작업은 별도 hardening feature로 관리한다.

## 2. Goals

### 2.1 Primary Goals

- [x] 7개 결함을 P0/P1/P2와 독립 merge gate로 분해한다.
- [x] 각 패치의 입력 계약, 기대 출력, 테스트 및 rollback 조건을 정의한다.
- [ ] 허용된 cached fallback이 state, operational classifier, repository, CSV에서 같은 의미를 갖도록 한다.
- [ ] 검증되지 않거나 stale/partial/unbound diagnostics의 원인 후보 승격을 차단한다.
- [ ] 장비 설정 provenance와 지원되는 evidence source를 감사 가능한 형태로 만든다.
- [ ] Legacy quality와 value-age 계약을 호환 가능한 방식으로 정합화한다.

### 2.2 Non-Goals

- 실제 물리 원인을 `confirmed`로 승격하지 않는다.
- 검증되지 않은 AMETEK `/output` 전체 응답 형식을 가정하지 않는다.
- 기존 realtime CSV에 raw diagnostics 전체를 중복 저장하지 않는다.
- 알림 억제, ML 입력 승격, 현장 threshold 변경을 수행하지 않는다.
- 이 Plan 단계에서 code, branch, remote, deploy 또는 migration을 변경하지 않는다.

## 3. Scope

### 3.1 In Scope

- Cache fallback precedence와 invalid-sentinel suppression 계약
- `low_signal_comparator_verified`의 end-to-end 전파
- Diagnostics snapshot 시점, 완전성, source 및 cause-promotion gate
- Config verification 기본값과 drift/fingerprint 정책
- Runtime collector가 없는 cause 후보의 승격 제한
- Legacy Temperature quality 호환성 정책
- Monotonic value age와 clock anomaly 상태
- FactoryData/schema/repository/validator/fact/sidecar와 회귀 테스트의 계약 일치
- 관측성, schema rollover, rollback 및 배포 gate

### 3.2 Out of Scope

- SPOT firmware나 장비 설정을 애플리케이션이 자동 변경하는 기능
- Camera 기반 target-present 판정 모델 구현
- Actuator 제어 기능
- 기존 fact 파일의 소급 재작성
- PR 생성, merge, production enablement

### 3.3 Expected Files

Design 단계에서 최종 확정하되 다음 파일을 우선 대상으로 한다.

- `backend/FacilityData/temperature_state.py`
- `backend/FacilityData/temperature_operational.py`
- `backend/FacilityData/spot_low_signal.py`
- `backend/FacilityData/drivers/spot_api.py`
- `backend/FacilityData/drivers/real_plc.py`
- `backend/FacilityData/schemas.py`
- `backend/FacilityData/repository.py`
- `backend/FacilityData/spot_observation_fact.py`
- `backend/config.py`
- `backend/validate_csv_v2.py` 및 관련 validator
- 관련 backend tests와 운영 문서

## 4. Functional Requirements

### FR-01 Cache Fallback Contract

- TTL 내 valid cache, `spot_cache_status=reused`, row freshness `fresh`인 transport failure는 정책 A에 따라 `temperature_output_status=valid`, `temperature_value_origin=cached_observation`으로 기록한다.
- Startup, clock anomaly, under/over-range sentinel, cache TTL 초과 및 cache suppression latch는 cached-valid보다 우선한다.
- `valid -> 6553.4 -> timeout`에서는 이전 valid cache를 절대 재사용하지 않는다.
- Classifier와 repository가 state decision을 재해석해 서로 다른 결과를 만들지 않도록 단일 decision contract를 사용한다.

### FR-02 Verified Low Signal Comparison

- `low_signal_comparator_verified`를 operational input과 공통 low-signal evidence helper에 추가한다.
- `verified=false`이면 `signalpc` 숫자 비교 결과는 `None`이며 원인 승격에 사용하지 않는다.
- 이 경우 안정적인 evidence code `signalpc_present_comparator_unverified`를 기록한다.
- `alarmstatus bit 4`는 comparator와 독립된 authoritative low-signal evidence로 유지한다.
- Realtime classifier와 observation fact가 같은 helper와 같은 결과를 사용한다.

### FR-03 Diagnostics Integrity Gate

- Design 단계에서 장비가 temperature와 diagnostics를 동일 `/output` 응답으로 제공하는지 실제 API 계약 또는 캡처로 검증한다.
- 지원되면 단일 응답을 `same_response` atomic snapshot으로 사용한다.
- 지원되지 않으면 diagnostic snapshot ID, captured/completed time, source poll association, field별 성공 상태를 저장한다.
- Operational input에 capture status, age, missing fields 및 source identity를 전달한다.
- Required evidence field가 없거나, max age를 초과하거나, 현재 observation과 연결되지 않은 diagnostics는 cause 후보를 승격하지 않는다.
- Partial async success는 `async_enriched` 하나로 완전 성공처럼 취급하지 않는다.

### FR-04 Config Provenance and Drift

- `DEFAULT_SPOT_CONFIG_OPERATOR_VERIFIED=false`를 기본값으로 한다.
- Sidecar configuration snapshot에 revision, verified timestamp/by, deterministic fingerprint SHA-256, device readback status를 기록한다.
- SPOT IP, app mode, threshold/comparator, Peak Picker 또는 설정 파일 fingerprint가 바뀌면 기존 verification을 자동 무효화한다.
- 운영자 식별자는 secret/token이 아닌 감사 가능한 비민감 identifier만 허용한다.

### FR-05 Evidence Eligibility

- Runtime collector가 없는 Peak Picker, actuator, target/FOV 및 detector-range evidence는 cause 승격에 사용할 수 없다.
- Collector 구현을 선택한 evidence에는 `captured_at`, `age_ms`, `source`, completeness 상태를 함께 기록한다.
- Collector 미구현 상태에서는 enum/schema는 호환성을 위해 유지할 수 있으나 classifier promotion path를 명시적으로 gate한다.

### FR-06 Legacy Quality Compatibility

- Blank Temperature와 `Temperature_quality=ok/not_missing`가 새로 생성되지 않도록 한다.
- 기존 필드 의미 변경은 downstream compatibility gate와 feature flag를 거친다.
- 즉시 의미 변경이 안전하지 않으면 별도의 legacy snapshot 필드 또는 명시적인 compatibility mode를 사용한다.
- Operational status에서 legacy quality로의 deterministic mapping은 Design 문서에서 고정한다.

### FR-07 Monotonic Value Age

- SPOT snapshot에 마지막 valid value의 monotonic 완료 시각을 보존한다.
- 같은 process에서는 row-created monotonic과의 차이를 value age로 사용한다.
- Wall-clock fallback은 monotonic 값이 없을 때만 허용한다.
- 음수, non-finite 또는 clock rollback은 age를 blank로 하고 `clock_anomaly`를 기록한다.
- 새 clock-status column이 필요하면 schema version/header rollover를 원자적으로 수행한다.

## 5. Non-Functional Requirements

### 5.1 Correctness

- State, operational result, CSV, observation fact와 validator가 동일 invariant를 적용해야 한다.
- Cause candidate는 direct evidence와 provenance 없이는 `unknown`을 유지한다.
- 모든 age 값은 finite non-negative 또는 blank여야 한다.

### 5.2 Compatibility and Migration

- 내부 classifier 수정은 기존 CSV 열 순서를 변경하지 않는다.
- 새 CSV/sidecar field가 필요하면 append-only 새 schema contract와 파일 rollover를 사용한다.
- 정확한 다음 schema version은 Design 단계에서 확정한다.
- 기존 v2.4 파일을 in-place 수정하거나 서로 다른 header의 행을 같은 파일에 append하지 않는다.

### 5.3 Performance and Availability

- Diagnostics 수집은 Temperature poll critical path를 block하지 않는다.
- Atomic `/output` 방식은 timeout budget과 payload 비용을 검증한 뒤 채택한다.
- Fact/sidecar write 실패가 realtime logging을 중단시키지 않되 failure counter와 spool 상태를 노출한다.

### 5.4 Observability

- 최소 counter: cached fallback accepted/rejected, comparator unverified, diagnostics stale/partial/unbound, config drift, unsupported evidence suppressed, value-age clock anomaly.
- 로그에는 secret, raw credential, 내부 인증 header를 기록하지 않는다.
- Health와 sidecar 집계가 row-level 결과와 대조 가능해야 한다.

### 5.5 Security

- Config fingerprint는 정규화된 비민감 설정만 대상으로 한다.
- Operator verification metadata에 credential 또는 개인 비밀값을 저장하지 않는다.
- 장비 readback 응답은 허용된 필드만 parse하고 크기, 타입, 범위를 검증한다.

## 6. Patch Sequence

| Stage | Priority | Scope | Merge Gate |
|---|---|---|---|
| 0. Contract Freeze | P0 | 재현 fixture, precedence table, API capability, schema/consumer 영향 확정 | Design 승인 전 코드 변경 금지 |
| 1. Cache + Comparator | P0 | FR-01, FR-02, shared helper, repository invariant | 교차 계층 sequence tests 및 targeted suite PASS |
| 2. Diagnostics Integrity | P1 | FR-03, partial/stale/unbound gate, fact provenance | Cause attribution tests와 non-blocking poll test PASS |
| 3. Config + Evidence | P1 | FR-04, FR-05, fingerprint/readback, unsupported candidate gate | Drift invalidation 및 evidence provenance tests PASS |
| 4. Quality + Value Age | P1/P2 | FR-06, FR-07, compatibility/schema rollover | Consumer compatibility와 rollover/clock tests PASS |
| 5. Controlled Verification | Gate | validator, full health, packaged build, replay/smoke | Match rate >= 90%, rollback drill, explicit merge approval |

각 stage는 별도 reviewable commit을 기본으로 한다. Stage 4처럼 schema와 downstream 의미를 함께 변경할 가능성이 있는 작업은 별도 PR로 분리할 수 있다. Stage 1 완료 전 Stage 2의 cause 승격 범위를 넓히지 않는다.

## 7. Success Criteria

### 7.1 Required Regression Sequences

- [ ] `valid -> timeout`, TTL valid: Temperature 유지, `valid/cached_observation/reused`.
- [ ] `valid -> 6553.4 -> timeout`: Temperature blank, cache reuse 금지, origin `none`.
- [ ] Cache TTL expired 또는 row stale: cached-valid 금지.
- [ ] `signalpc=1.5`, threshold `2.0`, comparator `lt`, verified false: cause `unknown`.
- [ ] 같은 numeric 입력에서 verified true와 alarm enabled: `low_signal_candidate`.
- [ ] `alarmstatus bit 4`: comparator verified 여부와 무관하게 low-signal direct evidence.
- [ ] Partial, stale 또는 unbound diagnostics: 관련 cause 승격 없음.
- [ ] Fresh complete diagnostics: 대응하는 candidate와 evidence provenance 생성.
- [ ] Config 기본값은 unverified이고 fingerprint 변경 시 verification이 해제됨.
- [ ] Collector가 없는 evidence는 candidate를 생성하지 않음.
- [ ] 모든 non-valid Temperature 행에서 legacy quality contract가 Design mapping과 일치함.
- [ ] Monotonic value age는 finite non-negative이고 음수 clock case는 blank/anomaly.

### 7.2 Validation Gates

- [ ] Targeted Temperature/state/repository/fact/validator tests PASS.
- [ ] Backend ruff, mypy, compile 및 전체 backend test PASS.
- [ ] Frontend/consumer health suite PASS.
- [ ] `git diff --check` PASS.
- [ ] Added-line sensitive-value scan 0 hits.
- [ ] Schema/header rollover 및 metadata manifest validation PASS.
- [ ] Frozen/PyInstaller package가 필요한 schema/config resource를 포함함.
- [ ] Controlled replay에서 invariant violation 0건.
- [ ] Design 대비 Check match rate 90% 이상.

## 8. Test Plan

| Layer | Required Coverage |
|---|---|
| Unit | precedence table 전 분기, comparator verified, age anomaly, config fingerprint |
| State-to-operational | cache accepted/rejected sequence, stale/transport/sentinel precedence |
| Driver | same-response 또는 async snapshot association, partial/error/timeout |
| Repository | Temperature/origin/quality/age 최종 CSV invariant |
| Observation fact | field provenance, missing fields, source age, shared evidence 결과 |
| Validator | invalid combinations 거부, schema/version/header 일치 |
| Integration | CSV open/rollover/close, metadata/fact manifest, health counters |
| Packaging | frozen config/resource/readback fallback 및 clean build |
| Operational | controlled SPOT replay 또는 sanitized capture smoke |

기존 테스트가 통과하는 것만으로 완료로 보지 않는다. 현재 기준 관련 테스트 `63 passed, 25 subtests passed`가 교차 계층 cache/comparator 결함을 검출하지 못했으므로 위 sequence tests를 먼저 추가한다.

## 9. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| Cache fallback이 invalid sentinel을 되살림 | High | Medium | suppression latch 우선순위와 3-step sequence test |
| Cached value가 stale인데 valid 처리됨 | High | Medium | row/value TTL 이중 gate와 health counter |
| 이전 poll diagnostics로 원인 오판 | High | Medium | snapshot association, per-field completeness, promotion gate |
| 장비 API가 atomic `/output`을 지원하지 않음 | Medium | Medium | Design에서 capability 검증, async provenance 대안 유지 |
| Operator verified 기본값 변경으로 candidate 감소 | Medium | High | 안전한 unknown 기본값, 운영 확인 절차 문서화 |
| Legacy quality 의미 변경으로 소비자 장애 | High | Medium | feature flag/new field, consumer contract test, 별도 rollout |
| CSV field 추가로 header 충돌 | High | Medium | schema bump와 atomic rollover, append 거부 guard |
| Sidecar/fact write failure | Medium | Low | failure counters, spool, realtime path isolation |

## 10. Rollback and Failure Modes

- Stage 1: classifier/state/repository 변경을 함께 revert한다. Cache fallback을 비활성화해야 할 때는 cached value를 blank로 만드는 fail-closed 정책으로 복귀한다.
- Stage 2: diagnostics cause promotion gate를 off로 전환해 모든 비직접 evidence를 `unknown`으로 낮춘다. Temperature 값 수집은 계속한다.
- Stage 3: config verification은 false로 복귀하며 원인 후보를 낮추는 방향으로 실패한다.
- Stage 4: legacy promotion flag를 끄고 이전 quality 의미로 rollover한다. 새 schema 파일이 이미 생성됐다면 기존 파일을 수정하지 않고 이전 schema로 새 파일을 연다.
- Value-age monotonic source가 없거나 손상되면 age blank와 `unknown/clock_anomaly`를 기록하며 임의의 0으로 대체하지 않는다.
- Rollback 후에도 sidecar rule/schema version과 health counter가 실제 활성 정책을 표시해야 한다.

Migration risk는 internal classifier-only 변경에서는 낮지만, CSV/sidecar field 또는 legacy quality 의미 변경에서는 중간 이상이다. Stage 4는 production enablement 전에 downstream consumer 검증과 rollback drill을 필수로 한다.

## 11. Architecture Considerations

- Transport/cache 판단의 단일 source of truth는 `temperature_state.py` decision object로 유지한다.
- Operational classifier는 source decision을 소비하고 row-time freshness 및 sentinel precedence만 추가한다.
- Low Signal evidence는 realtime/fact가 공유하는 pure helper에서 산출한다.
- Diagnostics snapshot은 observation grain identity와 source provenance를 가져야 한다.
- Realtime CSV에는 derived output과 observation key를 유지하고 raw diagnostics의 authoritative source는 observation fact로 유지한다.
- Validator는 production writer와 동일 enum/invariant를 독립적으로 검증하되 writer helper를 그대로 호출해 결함을 공유하지 않는다.

## 12. Convention Prerequisites

- Enum 문자열, reason code 및 evidence code를 Design 문서에서 먼저 고정한다.
- Dataclass/schema/CSV column/validator/test fixture 변경 순서를 Design에 명시한다.
- 새 환경변수 또는 feature flag는 기본 fail-closed, sidecar 기록, package 포함 여부를 정의한다.
- 각 code patch 전에 PDCA pre-write check를 실행한다.
- Commit과 PR은 stage별로 scope를 고정하고 unrelated 변경을 포함하지 않는다.

## 13. Schedule

| Phase | Target | Status |
|---|---|---|
| Plan | 2026-07-10 | Completed |
| Design | 다음 승인 후 | Pending |
| Stage 1 implementation | Design 승인 후 | Pending |
| Stage 2-4 implementation | 선행 stage gate 통과 후 | Pending |
| Check/Act | 구현 완료 후 | Pending |
| Report/controlled rollout | match rate 90% 이상 후 | Pending |

## 14. References

- `docs/01-plan/features/spot-temperature-v2-4-operational-patch.plan.md`
- `docs/02-design/features/spot-temperature-v2-4-operational-patch.design.md`
- `docs/03-analysis/spot-temperature-v2-4-operational-patch.analysis.md`
- `docs/04-report/spot-temperature-v2-4-operational-patch.report.md`
- `backend/FacilityData/temperature_state.py`
- `backend/FacilityData/temperature_operational.py`
- `backend/FacilityData/spot_low_signal.py`
- `backend/FacilityData/drivers/spot_api.py`
- `backend/FacilityData/repository.py`
- `backend/FacilityData/spot_observation_fact.py`

## 15. Next Phase Gate

다음 단계는 `$pdca design spot-temperature-v2-4-operational-hardening`이다. Design 승인 전에는 production code를 수정하지 않는다. Design은 최소한 cache precedence table, diagnostics atomic capability 결정, schema/version 전략, legacy quality compatibility mode와 stage별 exact test matrix를 확정해야 한다.
