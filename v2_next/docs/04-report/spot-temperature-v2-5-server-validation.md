# SPOT Temperature v2.5 Server Validation

> Date: 2026-07-13 | Status: `PASS` | Runtime: server computer with physical SPOT device

## 1. Executive Verdict

SmartFactoryLogger `1.0.13`의 SPOT Temperature v2.5 production enablement 검증을
완료했다. 최종 one-command QA는 `31/31 PASS`, warning `0`, full CSV validator
exit code `0`을 기록했다. 1.0.12에서 관측된 `Temperature must equal
spot_temperature_observed_c` 오류는 새 CSV에서 재발하지 않았다.

운영 판정은 `APPROVED`다. QA가 검증을 위해 백엔드를 정상 종료했으므로 운영자는
남은 창을 닫고 애플리케이션을 다시 실행한 뒤 정상 로깅을 계속한다.

## 2. Release Identity

| Item | Value |
|---|---|
| Application version | `1.0.13` |
| CSV schema | `2.5.0` |
| Packaged build commit | `6acc606e49b5a8f7573adf9873c4b4b98586ff4f` |
| Atomic snapshot fix commit | `128b1d02f8cad56a3f34f1a3ad8e144f83f2daa0` |
| QA re-attestation helper commit | `a4f333fb77f9d2c69dc4088581b13915e00aed34` |
| Installer SHA-256 | `5d10dd3d8cf9cba27d86eeabe068dcfe41a35fe530d1db6e82fdd44035fc0246` |
| Final QA bundle SHA-256 | `a7c0af6ebab47f149b560890a315e62e392513ff6fa7b7731c70508eb0b1875b` |

Installer hash는 clean local release artifact에서 기록했다. 서버 runtime identity는
metadata에 포함된 packaged build commit으로 확인했다.

## 3. Execution Sequence

1. 1.0.13 설치 후 최초 QA에서 runtime, CSV, fact와 full validator가 통과했다.
2. build commit 변경으로 기존 config attestation이 `fingerprint_mismatch`가 됐다.
3. 기존 helper가 fingerprint 단독 drift까지 차단하는 workflow 결함을 발견했다.
4. helper를 수정해 `spot_config_fingerprint_sha256` 단독 mismatch만 명시적 운영자
   재확인 대상으로 허용하고 device readback 등 다른 drift는 계속 차단했다.
5. 운영자가 SPOT model, app mode, Low Signal alarm/threshold/comparator를 확인하고
   새 fingerprint를 attestation했다.
6. 애플리케이션 재시작 후 최종 QA와 graceful shutdown을 실행했다.

최종 검증 구간은 `2026-07-13 23:31:42`부터 `23:35:16 KST`까지다. 이 중
runtime observation은 60초, 표본은 12개다.

## 4. Validation Results

| Area | Result | Evidence |
|---|---|---|
| Runtime | PASS | REAL mode, backend reachable |
| SPOT polling | PASS | success만 관측, current_observation만 관측 |
| CSV write activity | PASS | rows `187 -> 434`, observation 중 `247`행 증가 |
| Temperature binding | PASS | origin decision mismatch `0` |
| Monotonic age | PASS | value-age clock anomaly `0` |
| Observation fact | PASS | write/link failure `0` |
| Config attestation | PASS | verified, fingerprint matched, drift false |
| Low Signal comparator | PASS | verified true |
| Fact finalization | PASS | write failure `0`, pending spool `0` |
| Graceful shutdown | PASS | QA shutdown 후 backend stopped |
| Full CSV validator | PASS | portable validator exit code `0` |

### 4.1 Validator Invariants

| Invariant | Result |
|---|---|
| Final v2 rows | `592`, sample sequence `1..592` |
| Observation fact manifest/actual rows | `95,273 / 95,273` |
| Observation fact row count | matched |
| Observation poll sequence gaps | matched, no manifest discrepancy |
| Realtime observation link coverage | `100.0%` |
| Diagnostic source mismatch | `0` |
| SPOT image fact manifest/actual rows | `234,534 / 234,534` |
| SPOT image fact row count | matched |
| SPOT image fact SHA-256 | matched |

## 5. Preserved Evidence

- Sanitized artifact:
  [sfl-spot-temperature-v25-qa-20260713-233141.sanitized.json](evidence/sfl-spot-temperature-v25-qa-20260713-233141.sanitized.json)
- Original file name: `sfl-spot-temperature-v25-qa-20260713-233141.json`
- Original size: `21,510` bytes
- Original SHA-256:
  `5726b259a7190f90004f6e4953688085ddbfca40410a86e6f90d01f990688807`
- Sanitized SHA-256: `5b822dadc549684b725da29ce704e910718d3f2d50b3af84adfea81c139b4115`

원본은 local absolute Windows path를 포함하므로 커밋하지 않는다. Sanitized artifact는
파일 basename, release identity, 31개 PASS 목록과 validator invariant를 보존하고 절대
경로와 runtime endpoint를 제거했다.

## 6. Engineering Assessment

- Risk: production-critical correctness defect의 배포 검증이었으며 최종 결과는 PASS다.
- Compatibility: 기존 CSV를 rewrite하지 않고 v2.5 새 파일과 sidecar를 검증했다.
- Migration: database migration은 없고 기존 로그는 삭제하거나 변경하지 않는다.
- Security: 원본 증거의 absolute path는 커밋하지 않았다. 설치본은 Authenticode
  미서명 상태이므로 내부 배포 시 release SHA-256을 확인한다.
- Observability: runtime counter, attestation, manifest, portable validator가 동일 실행에서
  확인됐다.
- Operational failure mode: 이후 mismatch, clock anomaly, fact failure 또는 fingerprint
  drift가 발생하면 QA가 FAIL로 종료하고 evidence JSON을 남긴다.

## 7. Coverage Boundary

실장비 검증 구간에서는 정상 `success/current_observation` 경로만 자연 발생했다. 장비
통신을 끊거나 `6553.4` sentinel을 강제로 발생시키는 시험은 생산 장비에 영향을 주므로
실행하지 않았다. Transport cache fallback, invalid sentinel cache suppression,
stale/partial diagnostics와 comparator gating은 자동화된 회귀 테스트로 검증했다.

`device_config_readback_status=not_supported`이므로 device configuration은 자동 readback이
아니라 운영자가 확인한 attestation을 근거로 한다. 향후 장비 readback capability가 생기면
별도 collector와 server validation이 필요하다.

## 8. Rollback and Retention

- 정상 운영에서는 1.0.13을 재실행하고 QA를 반복 실행하지 않는다. QA는 백엔드 로깅을
  정상 종료하기 때문이다.
- 롤백이 필요하면 보관한 1.0.12 설치본을 재설치하고
  `config.ini.backup-v25-attestation-20260713-232644`을 복원한다.
- 기존 CSV, metadata, observation fact, image fact와 evidence JSON은 삭제하지 않는다.
- 새 build 또는 SPOT 관련 설정 변경 후에만 config attestation과 최종 QA를 다시 수행한다.

## 9. Final Approval

1.0.13 SPOT Temperature v2.5 runtime, config attestation, CSV, observation/image fact와
repository validator가 모두 통과했다. 서버 production enablement gate는 완료됐으며
다음 작업은 정상 운영과 정기 로그 보존이다.

실행 방법은 [SPOT Temperature v2.5 한 번에 검증](../V2/04_검증/spot_temperature_v25_one_command_qa.md)을
참조한다.
