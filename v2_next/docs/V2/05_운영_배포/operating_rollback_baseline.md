# 운영본과 다음 개선 작업의 롤백 기준

기준일: 2026-10-09 KST. 이 문서는 운영본·다음 개선의 복귀 기준·이번 교체 전 이전본을
구분하고 갱신하는 기준이다. 특정 commit의 영구 사용 지시가 아니다.

## 기준을 갱신하는 원칙

사용자는 `4c97d4a`의 사용을 고정하려는 것이 아니라 개선 중 이상이 생기면 복귀할 수 있게
하려는 것이라고 설명했다. 개선·검증을 마친 버전을 미서명 운영본으로 승격하고,
그 버전을 다음 개선 작업의 롤백 기준으로 삼는 방향을 확정했다.

| 단계 | 작업 대상 | 해당 변경에서 돌아갈 기준 |
| --- | --- | --- |
| 개선 N+1 시작 전 | 승인·검증된 운영본 N | N |
| 개선 N+1 시험 중 | 시험본 N+1 | N |
| N+1 운영 승격·적용 확인 후 | 운영본 N+1 | 다음 변경의 기준은 N+1 |
| 개선 N+2 시험 중 | 시험본 N+2 | N+1 |

현재 운영본과 다음 변경의 롤백 기준은 같은 설치본일 수 있다. 새 개선본이 검증·승격될 때
기준을 갱신하며 이전본과 증거는 보존한다. 승격 직후 그 본에 문제가 생긴 경우에는 보존된
이전본의 호환성과 승인된 복구 경로를 확인한다. 같은 실패본 재설치를 롤백이라고 부르지 않는다.


## 2026-10-09 UI-S1 적용 확인 후 현재 기준

사용자가 승인한 UI-S1 개선·후보 검증·서버 적용·기준 갱신 범위에서 아래 설치본을
미서명 내부 운영본과 다음 개선의 롤백 기준으로 등록했다. 기록 시각: 2026-10-09T14:02:03.420Z.
실제 서버는 `DESKTOP-CIIT7LK`, 표준 사용자 SID `S-1-5-21-2762931165-1280404403-2847611662-1001`이다.
아래 2026-10-08 절은 당시 운영 결정과 이전본 이력이며 최신 기준은 이 절이다.

| 역할 | 표시 버전 / 전체 build commit | installer / bytes / SHA256 |
| --- | --- | --- |
| 현재 운영본·다음 개선의 롤백 기준 | v1.0.26 / `541d701d544eea6a8a4e4836047077eaf9cfaf30` | `UI_S1_541d701_UNSIGNED.exe` / 163826264 / `08C061EE35A1A01788F05B00EE7395AA40774150C92C06726A92F3DF1BF75C3C` |
| 이번 교체 전 이전본 | v1.0.26 / `4c97d4a00d79ae0d3da70b2e82af227345e21040` | `ROLLBACK_4c97d4a_UNSIGNED.exe` / 164583937 / `D453C1D17EFC706D3E21FE6F8D09F739F159EBF9F3F24F2EB2349E92D4EF84FB` |
| 더 이전 교체 이력 | v1.0.26 / `d7a1b20f96711fb07fc7add0867e79ee36506fce` | 아래 2026-10-08 기록의 파일·해시·원문을 보존 |

두 설치본은 모두 `NotSigned`이며 게시자 서명과 정식 기술 QA는 PASS가 아니다.
같은 표시 버전이므로 후속 문서 commit 대신 위 build commit과 installer 해시로 식별한다.
후보 및 이전본의 서버 보존 위치는
`C:/Users/user/Desktop/SmartFactory/S1_CAND_20261009_R1/installers`다.
같은 바이트의 개발 사본은 `C:/Users/user/Desktop/SmartFactory/S1_PKG_20261009_R1/delivery/S1_CAND_20261009_R1/installers`,
공유 사본은 `Z:/SmartFactory/20261009/send/S1_CAND_20261009_R1/installers`에 보존한다.
기존4c/d7 보존 묶음과 hash 결합 증거도 그대로 둔다.

설치1회 actual OS exit0와 설치 선택54파일/provenance를 확인했다. 첫 적용 도우미는
초기 API timeout으로 EXIT1/HOLD였으며 원문 manifest `354E8911670F838144B51C24314DDA2D8369358A578EF61FE440424EDFF501CD`를 보존한다.
재설치·재시작 없이 후속 읽기 `r-20261009-224441-1f2226`의 EXIT0와 65파일 전체 해시를 회수·검토했다.
후속 manifest는 `8666510BABB8D0D6EAAF071DBAAD671554BC6EF782B745AC0723CF157150B92A`다.
128조건/실패0: 동일5프로세스·main17012/backend17348·8000 listener·새SPOT/logger,
15 GET HTTP200와 raw JSON, poll2127→2142/CSV rows9316→9379/image written1107→1121,
현재 저장실패/drop/대기0, 새CSV 추가 저장·제한 레코드/metadata bytes,
원래 config SHA와 닫힌CSV441853493bytes/metadata SHA 보존을 확인했다.
실제 화면에서 정상값 `SPOT OK / Temp OK / Comm OK`와 앞선
under-range의 `SPOT OK / Temp UNDER_RANGE / Comm OK` 및 별도 상태 패널을 관찰했다.
API와 화면은 각 관측 시점의 상태 종류를 대조했으며 동일 poll의 정확한 온도값 검증으로 확대하지 않는다.

수용·보존한 한계: 최초 timeout 원인 미확정, 후속 첫health223.4887ms는 운영200ms 기준 초과,
전체 성능 gate 미통과, `formal_operating_qa_passed=false`, config fingerprint mismatch/drift·
`async_fact_only`·comparator 미확인, 전체CSV validator/개별이미지 전수무결성 미검증이다.
이전4c의 image drop15/원인 미확정·종료 시 오래된metadata snapshot 및 과거 종료502 기록도 보존한다.
새 후보의 관찰구간 image drop0을 과거 누락 해결이나 기존 증거 PASS로 바꾸지 않는다.
이번 기준 갱신은 위 검증 범위와 제한을 가진 내부 운영 결정이며 추가 설치·자동복귀를 실행하지 않는다.

최신 근거:

- `C:/Users/user/Desktop/SmartFactory/S1_POST_READ_PREP_20261009_R1/server-post-review-001.json` 및 `.md`
- `C:/Users/user/Desktop/SmartFactory/S1_POST_READ_PREP_20261009_R1/operating-promotion-001.json`
- `C:/Users/user/Desktop/SmartFactory/S1_POST_READ_PREP_20261009_R1/server-results-001/r-20261009-224441-1f2226`
- `Z:/SmartFactory/20261009/return/S1_POST_READ_20261009_R1/r-20261009-224441-1f2226`
- `C:/Users/user/Desktop/SmartFactory/S1_CLOSE_READ_PREP_20261009_R2/server-normal-shutdown-review-002.json`

다음 개선 시작 때541d/08C를 복귀 기준으로 보존한다. 방금 교체한541d에 문제가 발생하면
이전4c/D453의 호환성·현재 설정/데이터·정상 종료 상태와 해당 복구 승인을 확인한 뒤 복귀한다.
이 문서만으로 강제 종료·자동rollback·데이터 삭제·counter 초기화를 수행하지 않는다.

## 2026-10-08 당시 운영 결정과 식별

사용자가 수용한 기존 한계, 미서명 운영 승격 의사와 이번 문서 반영 승인을 기록한다.
대상은 기존 승인 서버다. 실제 서버 식별값은 아래 로컬 적용 기록에 결합돼 있다. 현재 확인된 설치·검증본을 미서명 내부 운영본과
다음 개선 작업의 롤백 기준으로 등록한다. 자동 설치·자동 롤백 또는 향후 모든 빌드의 승인이 아니다.
승인된 작업은 같은 승인을 반복 요구하지 않고 진행하며, 새 대상·설치본에는 해당 승인 범위를 적용한다.

최신 보존 서버 조회는 2026-10-08 13:36:09 KST이며 v1.0.26 / `4c97d4a`를 가리킨다.
동일 소스 사본의 HEAD와 버전 상수도 일치한다. 이 식별을 기준으로 기록한 것이며,
다른 최신 commit이 설치됐다고 추정하지 않는다. 이번 문서 작업에서 실시간 서버 조회나 교체를 수행하지 않았다.

| 역할 | 현재 기록 |
| --- | --- |
| 현재 확인된 운영본 | v1.0.26 / `4c97d4a00d79ae0d3da70b2e82af227345e21040` |
| 다음 개선 작업의 롤백 기준 | 위 운영본과 동일한 commit·installer 해시. 다음 검증본 승격 때 갱신 |
| 이번 교체 전 이전본 | v1.0.26 / `d7a1b20f96711fb07fc7add0867e79ee36506fce`. 과거 복귀본으로 보존 |
| 배포 상태 | 미서명 내부 운영, 사용자 결정 및 수용한 한계 기록 |
| Authenticode | `NotSigned` — 게시자 서명 검증 완료로 표시하지 않음 |
| 정식 기술 QA | 보존 결과의 `formal_operating_qa_passed=false` 유지 |

표시 버전은 두 본 모두 1.0.26이다. commit과 설치본 해시로 구분한다.
현재 기준이 `4c97d4a`라는 사실은 해당 버전을 영구 사용하도록 고정한다는 뜻이 아니다.

| 항목 | 운영본·다음 변경의 기준 | 이번 교체 전 이전본 |
| --- | --- | --- |
| installer | `UI_4c97d4a_UNSIGNED.exe` | `ORIGINAL_d7a1b20.exe` |
| 길이(bytes) | 164583937 | 164003067 |
| SHA256 | `D453C1D17EFC706D3E21FE6F8D09F739F159EBF9F3F24F2EB2349E92D4EF84FB` | `1096276CC7C82E765A7BD1F03597CC09FF285AE587AC6B666CC86A04A3BFC25F` |

두 installer의 개발 PC 보존 위치:
`C:/Users/user/Desktop/SmartFactory/SUI_APPLY_PREP_R1/delivery/SUI_APPLY_R1/installers`.
이번 문서 반영 중 실제 파일의 길이·SHA256·`NotSigned`를 읽기 전용으로 다시 확인했다.
다음 문서 commit의 HEAD로 위 build commit을 바꾸어 쓰거나 과거 installer를 재빌드하지 않는다.

## 검증 근거와 남겨 둔 한계

기존 R7은 같은 설치본의 120분 관찰·정상 종료·원본 복귀를 검증했다. 폐쇄 CSV 31,548행의
production validator는 exit 0, 후보 이미지 저장 실패는 0, held process 5개는 모두 exit 0이었다.
후속 적용 확인에서는 같은 commit의 핵심 설치 파일 4개, 단일 실행 세대, 실제 CSV 추가 저장,
설정 보존과 완료 콘솔 종료 후 수집 지속을 확인했다. 이번 문서 작업의 새 제품 시험으로 계산하지 않는다.

다음 제한은 운영 결정 이후에도 같은 상태로 보존한다.

- 서명 gate와 정식 one-command QA의 PASS가 아니다. config attestation/comparator 미확인,
  config drift 기록과 `async_fact_only` 등 기존 안전 gate를 유지한다.
- 실제 nonempty-at-shutdown drain과 개별 PLC worker terminal 영수증은 현장 미관찰이다.
  기존 합성·패키지 시험과 실제 세대·종료 근거의 검증 범위를 확대하지 않는다.
- 이전 원본의 이미지 저장 실패 16건과 terminal drain unknown은 이전본의 기록이다.
  현재 운영본의 실패로 옮기지 않으며 실패 원인도 확정하지 않는다.
- IDLE일 때 `SPOT STALE / Comm 1`이 표시된다는 사용자 관찰은 보존한다.
  그 표시만으로 물리 원인이나 통신 장애를 확정하지 않고 source proof·저장 상태를 함께 확인한다.
- 제품·금형은 공정 중 바뀌거나 IDLE/공란일 수 있다. 과거 값을 강제로 적용하지 않는다.

승인 상태와 QA 결과는 별개다. 운영 결정 때문에 과거 영수증·실패·`verified=false`를
PASS/true로 편집하지 않는다. 수용한 한계를 새 필수 시험으로 자동 확대하지도 않는다.

## 다음 개선과 복구 절차

1. 새 개선 작업 시작 시 이 문서의 운영본을 복귀 기준으로 보존하고 정확한 installer·해시·위치를 확인한다.
2. 새 코드의 관련 회귀·통합·패키지 및 승인된 적용 검증을 수행한다. 다른 commit의 PASS를 복사하지 않는다.
3. 설치·복귀는 해당 승인 범위에서 현재 실행 상태·설정/데이터 호환성을 확인해 진행한다.
   정상 종료 뒤 미완료 저장·worker/프로세스 잔존이 있으면 실제 증거와 복구 절차를 확인한다.
   이 문서만으로 강제 종료·자동 복귀·데이터 삭제·실패 counter 초기화를 실행하지 않는다.
4. 개선본의 운영 승격과 적용 확인이 끝나면 그 본을 운영본 및 다음 변경의 롤백 기준으로 등록한다.
   이전 기준 → 새 기준, 승인 근거, 적용 확인 시점, 수용한 한계를 새 이력에 적는다.
5. 이전 설치본·해시 결합 helper·실패 자료는 그대로 보존한다. 동일 설치본의 기록 정리에
   재빌드·변경 없는 전체 회귀·추가 120분 시험을 자동으로 붙이지 않는다.

다음 갱신 때 사용할 기록 양식:

```text
기록 시각 / 대상 서버:
현재 운영본: 표시 버전 / 전체 build commit / installer 파일명·길이·SHA256
서명 상태 / 승인 근거·범위 / 적용 확인:
다음 개선의 롤백 기준: 전체 commit / installer SHA256 / 보존 위치
이번 교체 전 이전본: 전체 commit / installer SHA256 / 설정·데이터 호환성 근거
해당 개선본의 검증 근거 / 미실행·실패·미관찰 / 수용한 한계:
문제 발생 시 복구 조건·절차:
변경 이력: 이전 기준 → 새 기준 / 이유 / 확인 근거
```

## 변경 이력과 자료 위치

| 날짜 | 기록 | 근거와 범위 |
| --- | --- | --- |
| 2026-10-08 | 개선·검증·운영 승격에 따라 다음 변경의 롤백 기준을 갱신하는 원칙 확정 | 사용자 설명 및 문서 반영 승인. 특정 commit의 영구 사용 고정 아님 |
| 2026-10-08 | 확인된 4c97d4a 운영본을 다음 개선의 기준으로 등록, d7a1b20은 이전 교체 이력으로 보존 | R7·실제 적용 확인과 이번 로컬 installer 재검사. 새 설치나 현장 재시험 없음 |
| 2026-10-09 | UI-S1 적용 확인 후541d701d/08C를 운영본·다음 개선의 기준으로 갱신,4c97d4a/D453은 이번 교체 전 이전본 | 실제 installer exit0·선택54파일·후속READ EXIT0/128조건·수집/CSV/config보존·UI·65파일 회수. 미서명·정식QA/성능/전수검증 한계 유지 |

로컬 보존 자료(원문을 Git에 추가하는 지정이 아님):

- `C:/Users/user/Desktop/SmartFactory/SUI_R7_TRIAL_R1/RESULT.md`
- `C:/Users/user/Desktop/SmartFactory/SUI_R7_READINESS_R1/RESULT.md`
- `C:/Users/user/Desktop/SmartFactory/SUI_APPLY_VERIFY_R1_LOCAL/APPLY_RESULT.md` 및 `.json`
- `C:/Users/user/Desktop/SmartFactory/SUI_APPLY_VERIFY_R1_LOCAL/server-results/operational_observability_20261008_133538/raw/sample_003_health.json`
- `C:/Users/user/Desktop/SmartFactory/OPERATING_BASELINE_DOCS_20261008_R1/installer-identity.json`

적용 확인 자료의 최종 manifest SHA256:
`C00D950D2D138DF7FF946C74CF1832E8798525FBC422AD8722F94CECFECDE265`.
과거 자료의 `UNSIGNED_INTERNAL_CANDIDATE_APPLIED_WITH_DOCUMENTED_LIMITS` 판정은 보존하고
이 후속 운영 결정을 별도로 기록한다. 정식 QA 미통과를 통과로 변경하지 않는다.

관련 문서: [서명 운영](windows_authenticode_signing.md),
[배포 체크리스트](../DEPLOYMENT_CHECKLIST.md),
[과거 Temperature 상태](../../../TEMPERATURE_BRANCH_STATUS.md).
