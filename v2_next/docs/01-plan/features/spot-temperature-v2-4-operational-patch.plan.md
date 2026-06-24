# spot-temperature-v2-4-operational-patch - Plan Document

> Version: 1.0.0 | Date: 2026-06-24 | Status: Completed
> Level: Dynamic

---

## 1. Overview

### 1.1 Purpose

SPOT temperature v2.3 shadow instrumentation and PR #65 sentinel handling을 기준선으로 유지하면서, 2026-06-24 신규 v2 CSV 분석 보고서의 결론을 v2.4 운영 로직 패치로 단계적으로 반영한다.

핵심 목적은 `6553.4`와 `6553.5`를 숫자 온도나 단순 결측으로 취급하지 않고, 센서 출력 상태와 공정 컨텍스트를 분리해 저장하는 것이다. v2.4는 `Temperature` 값의 안전성은 계속 보존하되, 운영 소비자가 `under_range`, `over_range`, `stale`, `source_error`, `startup_pending`, `setup`, `pre_changeover_hold` 같은 상태를 명시적으로 읽을 수 있게 한다.

### 1.2 Background

PR #65 `Handle SPOT range sentinels explicitly`는 다음 기준선을 이미 구현했다.

- `6553.4`는 AMETEK SPOT REST temperature under-range sentinel이다.
- `6553.5`는 AMETEK SPOT REST temperature over-range sentinel이다.
- 두 sentinel은 `spot_raw_validity=invalid_sentinel`로 분류한다.
- row-level 구분은 `spot_device_status_code=temperature_under_range|temperature_over_range`로 보존한다.
- sentinel 발생 시 `Temperature`에는 숫자를 저장하지 않는다.
- `temperature_value_origin=none`, `temperature_status_shadow=invalid_value`를 유지한다.
- sentinel 이후 기존 정상 온도 캐시는 다음 valid temperature 전까지 현재값으로 재사용하지 않는다.
- raw 응답은 `spot_temperature_raw`와 payload hash로 보존한다.

신규 보고서 `docs/04-report/spot-temperature-final-report/SPOT_Temperature_Report.html`과 `source_note.json`은 2026-06-24 v2.3 CSV 3개 전수 분석 결과를 제공한다. 확인한 현재 근거 파일의 SHA-256은 `source_note.json`과 일치한다.

| Source | Verified SHA-256 |
|---|---|
| `docs/data/Factory_Integrated_Log_v2_20260624_105757.csv` | `EEA5A5B80EA82FFF341E028BE4856D9A0FB6CA30AE19EA23DD8772FA98C37D66` |
| `docs/data/Factory_Integrated_Log_v2_20260624_105757.metadata.json` | `588EE87B55A1B3C85C7465306D903B53842F7F4BD4B0DE2268CF48C8D9E7EC10` |
| `docs/data/Factory_Integrated_Log_v2_20260624_112050.csv` | `B80A0D4A2081E292B999811B3A7007EF1D4B785C2263D0438B99E6E93E965D74` |
| `docs/data/Factory_Integrated_Log_v2_20260624_112050.metadata.json` | `508BA616824E29F074DF99A8B9B0CCBD3C6D2F5C00EFB07E3CA7810CB675B6A6` |
| `docs/data/Factory_Integrated_Log_v2_20260624_114532.csv` | `BEE25E44AC254922596CDB8D0C983D47661DC7C70844C5C9038EF22FE92F1E2D` |
| `docs/data/Factory_Integrated_Log_v2_20260624_114532.metadata.json` | `947338B88A64E09AAE9FD640A7258302C45763173903496F13A2B51F18F8144A` |

분석 검증 요약:

| Metric | Value |
|---|---:|
| total rows | 109,010 |
| schema | `2.3.0` |
| valid temperature rows | 92,582 |
| under-range rows | 16,428 |
| over-range rows | 0 |
| unique SPOT polls | 22,275 |
| unique valid polls | 18,702 |
| unique under-range polls | 3,573 |
| repeat poll rows | 86,735 |
| `invalid_sentinel` rows with nonblank `Temperature` | 0 |
| `temperature_value_origin=none` rows with nonblank `Temperature` | 0 |
| `current_observation` Temperature mismatch | 0 |
| `spot_cache_status=available_not_used` rows | 530 |
| `spot_cache_status=reused` rows | 0 |

Under-range 분포:

| Count | 6553.4 rows |
|---:|---:|
| 0 | 14,429 |
| 12 | 957 |
| 15 | 252 |
| 16 | 206 |
| 35 | 269 |
| 49 | 315 |

보고서의 핵심 결론은 현재 `Temperature_quality=missing`, `Temperature_missing_reason=source_missing` 매핑이 운영 의미로는 부정확하다는 것이다. 16,428행은 HTTP 200, poll success, fresh 상태의 장비 출력이므로 원천 결측이 아니라 `under_range` 상태다. 단, `6553.4`의 물리 원인은 아직 Peak Picker Reset, 시야 이탈, 저신호, 실제 측정 범위 미만 중 어느 것인지 확정되지 않았다.

## 2. Goals

### 2.1 Primary Goals

- [ ] v2.4 CSV에 센서 출력 상태와 공정 컨텍스트를 분리한 운영 필드를 추가한다.
- [ ] `6553.4/6553.5`가 `Temperature` 숫자값으로 유입되지 않는 #65 invariant를 유지한다.
- [ ] under/over-range를 `source_missing`이 아닌 명시적 unavailable reason으로 표현한다.
- [ ] Count 0~2 셋팅 구간과 금형 교체 직전 대기 구간을 공정 phase로 분리한다.
- [ ] 온라인 realtime 행은 미래 정보를 사용하지 않고 provisional 상태만 기록한다.
- [ ] 후속 이벤트가 확인된 뒤 별도 fact 또는 정제 계층에서 phase를 confirmed로 승격한다.
- [ ] SPOT poll 반복 행을 값 중복으로 오해하지 않도록 observation key와 fact table 계획을 명확히 한다.
- [ ] v2.3 shadow 필드는 그대로 보존하고, 운영 승격은 v2.4+ 필드와 검증 게이트로만 수행한다.

### 2.2 Non-Goals

- v2.3.0 CSV 과거 파일을 재작성하지 않는다.
- `6553.4`를 `no_target`, 센서 고장, target 없음으로 확정하지 않는다.
- 물리 원인이 확인되지 않은 `6553.4`에 확정 cause를 저장하지 않는다.
- `Temperature`에 sentinel 값을 보간하거나 이전 정상값으로 대체하지 않는다.
- 경보/ML/운영 판단이 v2.3 shadow 필드를 바로 operational truth로 사용하게 하지 않는다.
- 실제 SPOT 장비 설정을 변경하거나 actuator를 제어하지 않는다.

## 3. Scope

### 3.1 In Scope

#### Runtime and deployment context

- Backend Python runtime
- `backend/FacilityData` data model, SPOT diagnostic join, CSV writer, process inference logic
- v2 CSV schema and sidecar metadata
- v2 CSV validation script
- Backend unit tests and evidence replay checks
- Documentation and PDCA design/do/check follow-up

#### New v2.4 fields

v2.4 필드는 기존 v2.3 필드 뒤에 append-only로 추가한다. 기존 v1/v2.3 위치 계약을 깨지 않기 위해 기존 컬럼 순서는 변경하지 않는다.

| Field | Type | Values / Rule | Purpose |
|---|---|---|---|
| `temperature_output_status` | enum | `valid`, `under_range`, `over_range`, `source_stale`, `source_error`, `startup_pending`, `unknown_missing` | 센서 출력의 운영 판정 |
| `temperature_unavailable_reason` | enum/blank | `under_range`, `over_range`, `source_stale`, `http_error`, `connection_error`, `timeout`, `parse_error`, `startup_no_observation`, `unknown_missing` | `Temperature`가 비어 있는 이유 |
| `temperature_expectedness` | enum | `expected`, `unexpected`, `unknown` | 공정 phase 기준으로 under-range가 예상 가능한지 |
| `temperature_under_range_cause` | enum | `unknown`, `peak_picker_reset_candidate`, `target_out_of_view_candidate`, `low_signal_candidate`, `below_range_candidate` | 미검증 물리 원인 후보. 확정값 금지 |
| `spot_effective_age_ms_at_row` | float/blank | row timestamp 기준 SPOT effective value age | stale 판정 기준 |
| `process_phase` | enum | `production_stable`, `setup_candidate`, `pre_changeover_hold_candidate`, `changeover_candidate`, `idle_candidate`, `unknown` | 온라인 공정 phase 후보 |
| `phase_confirmation_state` | enum | `realtime_candidate`, `posthoc_confirmed`, `not_applicable`, `unknown` | phase 확정 상태 |
| `changeover_event_id` | text/blank | post-hoc event fact 참조 | 금형 교체 이벤트 연결 |
| `spot_observation_key` | text | `{spot_service_instance_id}:{spot_poll_seq}` | realtime row와 SPOT observation fact 연결 |

#### Patch targets

- `backend/FacilityData/temperature_operational.py`
  - 신규 순수 함수 모듈.
  - #65 shadow 진단값, row 시점 age, process context를 입력받아 v2.4 운영 필드를 계산한다.
- `backend/FacilityData/schemas.py`
  - `FactoryData`에 v2.4 optional fields 추가.
  - enum validator 추가.
- `backend/FacilityData/repository.py`
  - `CSV_SCHEMA_VERSION`을 `2.4.0`으로 bump하는 설계.
  - `V2_CSV_COLUMNS` append-only 확장.
  - `_build_v2_row`에서 v2.4 운영 필드 추가.
  - sidecar metadata에 v2.4 operational rule version과 promotion gate 기록.
- `backend/FacilityData/drivers/real_plc.py`
  - SPOT diagnostics passthrough 유지.
  - row timestamp 기준 age 계산에 필요한 필드 전달.
- `backend/FacilityData/process_state.py`
  - post-hoc phase event fact 확장 또는 별도 `process_phase_event_fact` writer 설계.
  - Count 0~2 setup, pre-changeover hold 후보/확정 로직 분리.
- `scripts/validate_csv_v2_shadow.py`
  - v2.4 schema support 추가.
  - v2.3 invariant 유지.
  - v2.4 operational invariant 추가.
- `scripts/infer_process_segments_for_csv.py`
  - v2.4 phase event fact 출력 확장 또는 별도 script 추가.
- `backend/tests/test_spot_observation.py`
  - #65 sentinel classification regression 유지.
- `backend/tests/test_spot_api.py`
  - cache suppression, stale, invalid sentinel behavior 유지.
- `backend/tests/test_real_plc.py`
  - v2.4 CSV row, validator, process phase, replay tests 추가.

### 3.2 Out of Scope

- DB 저장소 도입 또는 외부 데이터 웨어하우스 연동.
- 실제 SPOT device 설정 변경.
- actuator autoscan 제어 자동화.
- UI 표시 변경.
- installer/release packaging 변경.
- 기존 v2.3 consumer를 강제로 v2.4로 전환.

## 4. Success Criteria

- [ ] `6553.4/6553.5`가 `Temperature` 숫자값으로 저장되는 사례 0건.
- [ ] `invalid_sentinel` row의 `Temperature`와 `spot_temperature_observed_c`는 blank.
- [ ] `6553.4` row는 `temperature_output_status=under_range`, `temperature_unavailable_reason=under_range`.
- [ ] `6553.5` row는 `temperature_output_status=over_range`, `temperature_unavailable_reason=over_range`.
- [ ] sentinel row는 `Temperature_quality=missing/source_missing`만으로 운영 소비자가 판단하지 않도록 v2.4 field가 우선 계약으로 명시된다.
- [ ] P3 운영 승격 전까지 legacy `Temperature_quality` 변경 여부는 feature flag 또는 schema gate로 통제된다.
- [ ] row 시점 age가 threshold를 초과하면 `temperature_output_status=source_stale`, unavailable reason은 `source_stale`.
- [ ] HTTP timeout/connection/http error/malformed response는 `source_error` 계열 reason으로 분리된다.
- [ ] Count 0~2 구간 under-range는 `process_phase=setup_candidate`, `temperature_expectedness=expected`.
- [ ] 이전 final Count 유지 후 Count 0/operator context change로 이어지는 구간은 post-hoc에서 `pre_changeover_hold`로 confirmed된다.
- [ ] 온라인 realtime row는 future context 없이 `*_candidate` 상태만 저장한다.
- [ ] 물리 원인 미확정 `6553.4`는 `temperature_under_range_cause=unknown` 또는 `*_candidate`만 허용한다.
- [ ] SPOT observation 반복 row는 `spot_observation_key`로 추적 가능하다.
- [ ] v2.4 sidecar에 schema version, operational rule version, v2.3 compatibility, sentinel provenance, promotion gate가 기록된다.
- [ ] v2.3 validator는 기존 파일을 계속 통과시킨다.
- [ ] v2.4 validator는 신규 operational invariant를 검사한다.
- [ ] 첨부 CSV 3개 replay에서 보고서 핵심 수치가 재현된다.

## 5. Detailed Patch Plan

### P0 - Schema and operational classifier

1. `temperature_operational.py` 추가.
   - 입력: `FactoryData` 또는 명시적 dict, row timestamp, SPOT diagnostics, process context.
   - 출력: `TemperatureOperationalDecision` dataclass.
   - 순수 함수로 작성해 CSV writer, tests, replay script에서 동일하게 사용한다.
2. #65 sentinel mapping을 재사용한다.
   - `spot_raw_validity=invalid_sentinel`
   - `spot_device_status_code=temperature_under_range|temperature_over_range`
   - `temperature_value_origin=none`
   - `Temperature` blank invariant 유지.
3. v2.4 enum 정의.
   - enum 값은 `schemas.py`와 validator에 동일하게 선언한다.
   - 불명확한 값은 `unknown`으로 수렴시키고 raw text를 운영 필드에 직접 쓰지 않는다.
4. v2.4 CSV schema 추가.
   - `CSV_SCHEMA_VERSION="2.4.0"`.
   - 기존 `V2_CSV_COLUMNS` 뒤에 v2.4 fields append.
   - header mismatch guard가 기존 파일 append를 막는 동작을 유지한다.
5. legacy `Temperature_quality` 처리.
   - P0에서는 `Temperature` numeric safety를 우선 유지한다.
   - `Temperature_quality` 즉시 변경은 downstream risk가 있으므로 `temperature_output_status`를 새 우선 필드로 추가한다.
   - P3 gate 충족 후 `Temperature_quality=invalid`, `Temperature_missing_reason=under_range|over_range` 전환을 별도 switch로 수행한다.

### P1 - Observation/config facts

1. `spot_observation_key`를 realtime row에 추가한다.
   - `{spot_service_instance_id}:{spot_poll_seq}`.
   - poll 반복 row를 정상 fan-out으로 설명한다.
2. `spot_observation_fact` 출력 경로를 설계한다.
   - poll 1건당 1행.
   - raw response, raw validity, device status code, http status, payload hash, freshness, cache status 포함.
   - realtime CSV의 반복 raw payload 저장은 장기적으로 fact 참조로 대체한다.
3. `spot_config_snapshot` 수집 설계를 추가한다.
   - `alarmstatus`, `signalpc`, mode/App, range, Peak Picker, response time, firmware.
   - 현재 단계에서는 읽기 전용 수집만 허용한다.
4. `actuator_observation_fact`는 별도 설계 항목으로 둔다.
   - position, scan state, trigger, hotspot, peak found 접근 가능성 확인 후 구현한다.

### P2 - Process phase and post-hoc confirmation

1. 온라인 realtime classifier.
   - Count 0~2와 stopped/idle 조건을 `setup_candidate`로 표시한다.
   - product/mold metadata change while stopped는 `changeover_candidate`로 표시한다.
   - 이전 final Count를 보존하더라도 future reset을 모르는 realtime row는 확정하지 않는다.
2. post-hoc event fact.
   - Count 0 또는 operator context 변경이 확인된 뒤 이전 구간을 `pre_changeover_hold`로 confirmed.
   - event id는 source file hash, logger service instance, time interval, product/mold transition으로 결정적으로 생성한다.
3. expectedness 계산.
   - `under_range` + `setup_candidate|setup_confirmed` => `expected`.
   - `under_range` + `pre_changeover_hold_confirmed` => `expected`.
   - `over_range`는 공정 phase와 무관하게 기본 `unexpected`.
   - phase 불명확 시 `unknown`.
4. 미래 정보 오염 방지.
   - realtime CSV row에는 `posthoc_confirmed`를 쓰지 않는다.
   - confirmed 값은 별도 fact 또는 정제 산출물에만 쓴다.

### P3 - Controlled tests and operational promotion

1. 통제 시험.
   - `6553.5` 응답 주입.
   - 5초/20초 SPOT 통신 차단.
   - malformed response.
   - SPOT service restart.
   - logger restart.
   - 실제 금형 교체 1건.
2. validator gate.
   - sentinel numeric leakage 0건.
   - stale 판정 누락 0건.
   - cache reused 오사용 0건.
   - realtime row와 `spot_observation_fact` match 100%.
   - service instance restart boundary 명확.
3. legacy quality promotion.
   - P3 gate가 통과한 뒤 `Temperature_quality`와 `Temperature_missing_reason`을 v2.4 operational status에서 산출하도록 전환한다.
   - 전환 전후 consumer compatibility test를 별도 실행한다.

## 6. Tests and Checks

### Unit tests

- `6553.4`, `6553.40`, whitespace/CRLF under-range decimal equivalence.
- `6553.5`, `6553.50` over-range decimal equivalence.
- nearby values `6553.39`, `6553.41`, `6553.49`, `6553.51`는 sentinel이 아닌 out-of-range.
- sentinel row는 `Temperature` blank, `temperature_value_origin=none`.
- invalid sentinel 이후 timeout은 cache reuse가 아니라 `source_error`.
- valid 이후 timeout은 fallback 허용 조건에서만 cached observation.
- v2.4 classifier table:
  - valid + fresh
  - under-range
  - over-range
  - stale age
  - timeout
  - malformed
  - startup pending
- Count 0~2 setup expectedness.
- pre-changeover hold는 post-hoc에서만 confirmed.
- over-range는 expected setup이어도 `unexpected` 기본값.

### Integration and replay checks

- `scripts/validate_csv_v2_shadow.py`에 v2.4 support 추가 후 v2.3/v2.4 모두 검증.
- 첨부 CSV 3개 replay에서 다음 수치 재현:
  - total 109,010 rows
  - under-range 16,428 rows
  - over-range 0 rows
  - unique poll 22,275
  - cache reused 0
  - invalid sentinel with `Temperature` 0
- generated v2.4 sample CSV sidecar metadata validation.
- CSV replay driver가 새 fields를 보존하거나 미지원 스키마를 명시적으로 거부.
- process phase event fact output이 source CSV를 변형하지 않는지 확인.

### Commands

Targeted checks:

```powershell
python -m unittest backend.tests.test_spot_observation backend.tests.test_spot_api backend.tests.test_real_plc
python scripts/validate_csv_v2_shadow.py --v2 docs/data/Factory_Integrated_Log_v2_20260624_105757.csv --metadata docs/data/Factory_Integrated_Log_v2_20260624_105757.metadata.json
python scripts/validate_csv_v2_shadow.py --v2 docs/data/Factory_Integrated_Log_v2_20260624_112050.csv --metadata docs/data/Factory_Integrated_Log_v2_20260624_112050.metadata.json
python scripts/validate_csv_v2_shadow.py --v2 docs/data/Factory_Integrated_Log_v2_20260624_114532.csv --metadata docs/data/Factory_Integrated_Log_v2_20260624_114532.metadata.json
```

Full local health check remains:

```powershell
npm run health
```

## 7. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---:|---|
| Downstream consumers assume v2.3 column set | Medium | High | v2.4 schema version bump, append-only columns, compatibility notes, consumer validation before P3 |
| `Temperature_quality` semantic change breaks reports | High | Medium | P0 adds new fields first; P3 changes legacy quality only after gate |
| Future context leaks into realtime rows | High | Medium | realtime candidate only; confirmed phase in separate post-hoc fact |
| `6553.4` incorrectly treated as no target | High | Medium | validator blocks no-target/cause certainty without evidence |
| Physical cause overclaiming | Medium | High | cause values restricted to `unknown` or `*_candidate` until detector/config evidence exists |
| Header mismatch appends to old file | Medium | Low | existing header guard refuses append; schema bump creates new file |
| CSV formula injection in new text fields | Medium | Low | reuse `_escape_csv_text` for all text fields |
| Test data reflects one day only | Medium | Medium | require controlled tests and server-PC evidence before operational promotion |

## 8. Operational Controls

### Rollback path

- Keep #65 v2.3 sentinel logic intact as the fallback baseline.
- Add a feature flag such as `CSV_V2_OPERATIONAL_FIELDS_ENABLED`.
- If v2.4 operational fields cause consumer issues, disable the flag and continue emitting v2.3-compatible shadow rows.
- Do not rewrite historical CSV rows.
- If schema `2.4.0` has already emitted files, consumers can ignore unknown appended fields or pin to schema `2.3.0` until upgraded.

### Observability impact

- Add counters/log fields for:
  - `temperature_output_status`
  - `temperature_unavailable_reason`
  - `temperature_expectedness`
  - stale age threshold breaches
  - sentinel count by device status code
  - observation fact match failures
- `/health` should expose aggregate status only, not raw URLs or sensitive local paths.

### Migration risk

- Schema bump is required from `2.3.0` to `2.4.0`.
- Existing validator must keep accepting `2.3.0`.
- v2.4 metadata must document that v2.3 shadow fields are not operational truth.
- Consumer compatibility tests must run before legacy `Temperature_quality` behavior changes.

### Failure modes

- SPOT poll timeout after sentinel: must remain `source_error` or unavailable, not cached value.
- SPOT service restart: service instance key must prevent poll sequence collision.
- Logger restart: logger instance/sample sequence key must preserve row uniqueness.
- Empty or malformed raw body: must not become `under_range` or `no_target`.
- Missing process context: phase and expectedness must be `unknown`, not guessed.

## 9. Schedule

| Phase | Target Date | Status |
|---|---|---|
| Plan | 2026-06-24 | Completed |
| Design | TBD | Pending |
| P0 implementation | TBD | Pending |
| P1 facts | TBD | Pending |
| P2 post-hoc phase | TBD | Pending |
| P3 controlled tests | TBD | Pending |
| Operational promotion | TBD | Pending |

## 10. References

- `docs/04-report/spot-temperature-final-report/SPOT_Temperature_Report.html`
- `docs/04-report/spot-temperature-final-report/source_note.json`
- `docs/04-report/spot-temperature-state-labeling.report.md`
- `docs/01-plan/features/spot-temperature-state-labeling.plan.md`
- `docs/02-design/features/spot-temperature-state-labeling.design.md`
- `docs/03-analysis/spot-temperature-state-labeling.analysis.md`
- `backend/FacilityData/spot_observation.py`
- `backend/FacilityData/drivers/spot_api.py`
- `backend/FacilityData/drivers/real_plc.py`
- `backend/FacilityData/repository.py`
- `backend/FacilityData/process_state.py`
- `scripts/validate_csv_v2_shadow.py`
- `scripts/infer_process_segments_for_csv.py`
- PR #65 commit `95b55f5 Handle SPOT range sentinels explicitly`
