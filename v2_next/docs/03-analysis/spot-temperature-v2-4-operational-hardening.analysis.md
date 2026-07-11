# Gap Analysis: SPOT Temperature v2.4 Operational Hardening

> Date: 2026-07-11 | Scope: Full feature, Stage 0-5
> Design: `docs/02-design/features/spot-temperature-v2-4-operational-hardening.design.md`
> Verification baseline: `master@9cf96f8ba42f408119808537a4ff66de2e979658`

## Match Rate: 100%

설계의 exact test matrix 56개 중 56개가 코드, validator, automated test 또는 package/sensitive gate에 대응해 PASS했다. DEC-01~08과 FR-01~07도 모두 구현돼 blocking gap은 없다.

| Matrix | Passed | Total | Evidence area |
|---|---:|---:|---|
| C - Cache and Status | 10 | 10 | state, operational, SPOT API, RealPLC tests |
| L - Low Signal | 7 | 7 | shared helper, operational/fact parity tests |
| D - Diagnostics | 11 | 11 | poll binding, partial/stale/failure tests |
| G - Config and Eligibility | 8 | 8 | provenance, drift, unsupported evidence tests |
| Q - Quality, Age and Schema | 12 | 12 | v2.5 mapping, clock, rollover, config tests |
| V - Validator and Packaging | 8 | 8 | validator, historical fact, package, scan gates |
| **Total** | **56** | **56** | **100%** |

## Functional Requirement Results

| Requirement | Result | Implementation evidence |
|---|---|---|
| FR-01 cache fallback | PASS | transport fallback precedence, TTL/freshness gate, invalid-sentinel latch, origin mismatch fail-closed |
| FR-02 comparator verification | PASS | verified-only numeric comparison, bit 4 direct evidence, realtime/fact shared helper |
| FR-03 diagnostics integrity | PASS | poll context, snapshot identity, per-field status, same-poll/age/required-field eligibility |
| FR-04 config provenance | PASS | default false, canonical fingerprint, attestation, drift/readback fail-closed |
| FR-05 evidence eligibility | PASS | collector 없는 candidate promotion 차단과 suppression counter |
| FR-06 legacy quality | PASS | v2.5 operational mapping, blank/ok contradiction rejection, v2.3/v2.4 compatibility |
| FR-07 monotonic value age | PASS | monotonic-first age, UTC fallback, anomaly/unknown status와 schema rollover |

## Controlled Verification

- 실제 writer와 full validator로 v2.3/v2.4/v2.5 matrix를 통과했다.
- Sanitized v2.5 artifact는 full validator invariant violation 0건이다.
- Observation fact/realtime link coverage는 `1/1`, missing 0, 100%다.
- Replay 결과 Temperature `560.7`, value-age clock status `ok`를 확인했다.
- Rollback은 v2.5 artifact를 변경하지 않고 hardening-disabled v2.4 새 파일을 생성했다.
- Targeted pytest: `381 passed, 87 subtests passed`.
- Full health: frontend `27 files / 202 tests`, backend ruff/mypy PASS, `497 tests OK`.
- Python compile와 `git diff --check`: PASS.
- Added-line sensitive-value scan: 0 hits.

## Package Evidence

- Clean PyInstaller one-file build: PASS.
- Build 시작·완료 provenance: `9cf96f8ba42f408119808537a4ff66de2e979658`.
- Embedded `backend/build_provenance.json`:

```json
{
  "git_commit": "9cf96f8ba42f408119808537a4ff66de2e979658",
  "schema_version": "1.0.0",
  "source": "clean_git_head"
}
```

- EXE size: `65,382,487` bytes.
- EXE SHA-256: `8320ce0464c53dcd56b80256b1e99280a6cd23920a0212ac15d1d4f8d631f0ad`.
- Bundled validator source/bytecode와 build provenance resource를 archive에서 확인했다.
- PR #164 Windows Release Artifact workflow도 portable, NSIS, checksum, artifact upload를 통과했다.

## Design Decisions and Non-Gaps

- Atomic `/output`은 capability evidence가 없어 활성화하지 않았다. 설계 DEC-04에 따라 기본 `async_fact_only`와 strict same-poll eligibility를 사용하므로 미구현 gap이 아니다.
- Device readback collector가 없는 환경은 `not_supported`로 표시하고 operator attestation과 fingerprint를 요구한다. `matched`로 위조하지 않는다.
- Peak Picker, actuator, FOV, detector-range enum은 compatibility를 위해 유지하지만 provenance-capable collector 전에는 원인 승격을 차단한다.
- v2.5 hardening flag 기본 false는 controlled rollout 경계이며 production enablement는 본 feature 범위 밖이다.

## Delivery Traceability

| Stage | PR | Squash commit | Result |
|---|---|---|---|
| Stage 1 | #161 | `218b57b5ea96588b742f7a25560c8188df07cc65` | MERGED |
| Stage 2 | #162 | `e42d75f66a3eacdd6f6f58fafc68a6b46a2b38f9` | MERGED |
| Stage 3 | #163 | `65b123a05677ad1a3468df9647ab8191b778e4e1` | MERGED |
| Stage 4 | #164 | `9cf96f8ba42f408119808537a4ff66de2e979658` | MERGED |

## Residual Risk

- 실제 장비에서 atomic response와 readback을 지원하려면 별도 capability evidence와 collector PR이 필요하다.
- v2.5 exact-column-count consumer는 production enablement 전에 v2.5 지원 확인이 필요하다.
- Config/build 변경 후 attestation을 갱신하지 않으면 numeric low-signal candidate가 `unknown`으로 강등된다. 이는 의도한 fail-closed 동작이다.

## Recommendation

Match rate가 90% gate를 초과했고 blocking gap이 없으므로 Check를 완료하고 final report로 이동한다. Stage 5 test/document PR은 별도 review와 explicit merge approval을 거친다.
