# 운영본과 다음 개선 작업의 롤백 기준

기준일: 2026-10-08 KST. 이 문서는 운영본·다음 개선의 복귀 기준·이번 교체 전 이전본을
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

## 2026-10-08 운영 결정과 식별

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
