# Gap Analysis: SPOT Temperature v2.4 Operational Hardening

> Date: 2026-07-10 | Scope: Stage 2 - Diagnostics Integrity
> Design: `docs/02-design/features/spot-temperature-v2-4-operational-hardening.design.md`

## Match Rate: 100% (Stage 2 scope)

전체 feature 완료율이 아니라 이번 별도 PR의 Stage 2 설계 7개 항목을 기준으로 계산했다. Stage 3~5는 의도적으로 미구현 상태이며 PDCA Do phase를 유지한다.

## Implemented Items

- [x] `SpotPollContext`와 immutable `DiagnosticSnapshot` 추가
- [x] 비동기 diagnostics에 source poll binding 추가
- [x] capture/binding/per-field status와 missing fields 계산
- [x] RealPLC, FactoryData, repository, operational input 전파
- [x] cause별 same-poll/age/required-field eligibility gate 적용
- [x] observation fact `1.3.0`, provenance, strict validator와 `1.2.1` historical read 지원
- [x] bounded capture/binding/suppression health counters 추가

## Acceptance Evidence

| Design test | Result | Evidence |
|---|---|---|
| D-01 same response | PASS | Atomic-mode eligible input test |
| D-02 async complete same poll | PASS | Scheduled diagnostics source poll binding test |
| D-03 unrelated partial failure | PASS | Required alarm field success promotion test |
| D-03A fact-only | PASS | Raw diagnostics retained, cause suppressed |
| D-04 required field failure | PASS | `required_field_failed` suppression |
| D-05 previous poll | PASS | Driver binding and repository counter test |
| D-06 stale age | PASS | Operational stale suppression test |
| D-07 future clock | PASS | Negative age/future-clock suppression test |
| D-08 legacy async enriched | PASS | Missing identity/capture contract fail-closed test |
| D-09 late completion | PASS | Temperature non-blocking, next-poll reuse forbidden |
| D-10 diagnostics failure | PASS | Temperature success remains independent |

## Missing Items

Stage 2 범위의 blocking 누락은 없다.

다음 항목은 후속 stage 범위다.

- Stage 3: config attestation/fingerprint/readback drift
- Stage 3: runtime collector가 없는 cause promotion 차단
- Stage 4: monotonic value age와 clock status
- Stage 4: realtime schema `2.5.0` legacy quality 정합화
- Stage 5: 전체 feature controlled verification과 report

## Deviations and Decisions

- Atomic `/output`은 capability evidence가 없어 활성화하지 않았다.
- Production default는 `async_fact_only`로 고정했다. `async_same_poll`과 `atomic_output_json` eligibility 경로는 구현·테스트했지만 production enablement는 하지 않았다.
- `DiagnosticSnapshot`에 wall-clock epoch와 collection mode를 추가했다. Monotonic age 계산과 audit mode 보존을 위한 additive internal metadata다.
- Realtime CSV `2.4.0` header는 변경하지 않고 raw diagnostics/provenance는 observation fact `1.3.0`에만 추가했다.

## Validation

- Related Stage 2 pytest: `301 passed, 45 subtests passed`
- Full repository health: PASS
  - Frontend: typecheck/lint, `27 files / 202 tests`
  - Backend: ruff/mypy, `466 tests OK`
- Python compile: PASS
- `git diff --check`: PASS

## Recommendation

Stage 2는 별도 PR로 review 가능하다. 전체 feature report 또는 PDCA completion으로 이동하지 말고 Stage 3를 별도 branch/PR로 진행한다.
