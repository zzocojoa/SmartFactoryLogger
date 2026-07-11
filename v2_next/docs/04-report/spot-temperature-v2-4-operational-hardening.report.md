# SPOT Temperature v2.4 Operational Hardening - Final Report

> Version: 1.0.0 | Date: 2026-07-11 | Status: Complete
> Baseline: `07dd370e22e8bf2c413c4afdc4cf85a30d54d031`
> Verified through: `9cf96f8ba42f408119808537a4ff66de2e979658`

## 1. Executive Summary

Temperature 운영 경로에서 보고된 7개 계약 결함을 Stage 1~4로 패치하고 Stage 5 controlled verification까지 완료했다. Cache fallback, comparator verification, diagnostics binding, config drift, unsupported cause gating, legacy quality, monotonic value age가 writer·fact·validator·consumer에서 일관되게 동작한다.

전체 design match rate는 100%이며 exact matrix 56/56, controlled replay, rollback drill, full health, clean package build와 sensitive scan을 모두 통과했다.

## 2. Delivered Outcomes

| Area | Final behavior |
|---|---|
| Cache fallback | TTL-valid하고 fresh한 transport fallback만 finite cached Temperature로 유지 |
| Invalid sentinel | 새 valid poll 전까지 cache 부활 차단 |
| Low Signal | 검증된 comparator 또는 alarm bit 4만 causal evidence로 사용 |
| Diagnostics | same-poll, bounded age, required-field success가 없으면 cause 승격 차단 |
| Config | default unverified, fingerprint drift/readback failure 시 자동 fail-closed |
| Unsupported causes | enum/fact는 보존하되 collector provenance 전까지 candidate 차단 |
| Legacy quality | v2.5에서 operational status와 deterministic mapping |
| Value age | monotonic 우선, UTC fallback, 음수·비유한 값은 clock anomaly |

## 3. Delivery History

- PR #161: Cache fallback and comparator verification, squash `218b57b5ea96588b742f7a25560c8188df07cc65`.
- PR #162: Diagnostics integrity and poll binding, squash `e42d75f66a3eacdd6f6f58fafc68a6b46a2b38f9`.
- PR #163: Config provenance and unsupported evidence gating, squash `65b123a05677ad1a3468df9647ab8191b778e4e1`.
- PR #164: v2.5 quality and monotonic value age, squash `9cf96f8ba42f408119808537a4ff66de2e979658`.

## 4. Verification Results

- Exact test matrix: `56/56` PASS.
- Stage 5 controlled tests: `3 passed, 3 subtests passed`.
- Targeted tests: `381 passed, 87 subtests passed`.
- Full health: frontend typecheck/lint and `27 files / 202 tests`; backend ruff/mypy and `497 tests OK`.
- v2.3/v2.4/v2.5 actual writer → sidecar/fact → full validator matrix: PASS.
- Sanitized v2.5 replay: invariant violation 0, fact link coverage 100%.
- Rollback drill: 기존 v2.5 immutable, 새 v2.4 artifact 생성 PASS.
- Clean PyInstaller build and embedded squash provenance: PASS.
- EXE SHA-256: `8320ce0464c53dcd56b80256b1e99280a6cd23920a0212ac15d1d4f8d631f0ad`.
- `git diff --check`, Python compile, added-line sensitive scan: PASS, 0 hits.

## 5. Engineering Assessment

- Risk: medium. Runtime cause attribution과 새 opt-in v2.5 CSV contract를 변경했다.
- Compatibility: v2.3/v2.4 header와 quality 의미는 유지한다. v2.5는 feature flag가 켜질 때 별도 파일로 rollover한다.
- Migration: database migration과 기존 CSV rewrite는 없다.
- Security: config fingerprint는 비민감 canonical inputs만 사용하고 raw credentials, URL, auth headers를 기록하지 않는다.
- Observability: cache, diagnostics, comparator, drift, unsupported evidence, clock anomaly를 bounded counters로 노출한다.
- Failure mode: 불완전·stale·unbound·unverified 입력은 Temperature 또는 cause를 높이지 않고 blank/unknown으로 낮춘다.

## 6. Rollout and Rollback

Production enablement는 이 PDCA 범위 밖이며 `CSV_V2_TEMPERATURE_HARDENING_ENABLED=false`가 기본값이다. Controlled rollout 전에 v2.5 consumer 지원과 config attestation을 확인해야 한다.

Rollback은 hardening flag를 끄고 새 v2.4 파일을 여는 방식이다. 기존 v2.5 CSV와 sidecar는 수정하거나 삭제하지 않는다. Diagnostics 또는 config 문제 시 cause promotion을 disable하고 raw fact만 보존할 수 있다.

## 7. Remaining Risk

- Atomic `/output` 또는 device readback은 실제 capability evidence가 생길 때 별도 collector로 구현한다.
- 설정·build 변경 시 fingerprint attestation을 다시 수행해야 한다.
- 실제 장비 production smoke와 장기 관측은 배포 승인 후 운영 단계에서 수행한다.

## 8. Conclusion

계획된 로직 패치 1~7과 Stage 5 verification은 모두 완료됐다. 구현 gap은 없으며 다음 gate는 Stage 5 verification PR review와 explicit squash-merge approval이다.
