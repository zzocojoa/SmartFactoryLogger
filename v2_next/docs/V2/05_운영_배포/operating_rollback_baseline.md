# 운영본과 다음 개선 작업의 롤백 기준

## 현재 기준 — 2026-10-26 운영 승격 완료

최종 통합 QA, 실제 서버 적용 상태, 로컬/원격 `v1.0.32` 태그 검산을 완료했다.
판정: **승인된 제약을 포함한 미서명 내부 운영 승격** (`PROMOTED_WITH_DOCUMENTED_LIMITATIONS`).
아래 과거 표의 “검증 중인 후보”, “1.0.26 등록 운영본”은 당시 이력이다. 현재 기준은 이 표다.

| 역할 | 버전 / build commit | installer bytes / SHA256 |
|---|---|---|
| 현재 승인 운영본 및 다음 변경의 롤백 기준 | 1.0.32 / `cd46692ac9c551080c57d8168fa9ea5abd530206` | 164158258 / `558658cf02d59cb6b66468e4e191c447efdc7cc24518b5a69647cc2409eb232f` |
| 이번 승격 전 등록 롤백본 — 보존 | 1.0.26 / `541d701d544eea6a8a4e4836047077eaf9cfaf30` | 163826264 / `08c061ee35a1a01788f05b00ee7395aa40774150c92c06726a92f3df1bf75c3c` |
| C32 설치 직전 현장 후보 — 보존 | 1.0.31 / `a7e5149b718f56d7dfa75df73bfba4a21d16a758` | 164158074 / `a10a59aa544a7bfa60e40778f05b89e3cc5be6da8ca284f94f740b6e6ae4a1dc` |

- C32 서버 설치본: `C:\Users\user\Desktop\SmartFactory\FIELD32_20261023_cd46692a\install\candidate.exe`
- C32 개발 PC 보존 설치본: `C:\Users\user\Desktop\SmartFactory\C32BUILD_20261023_eac4b615\source\v2_next\dist\smart-factory-logger-v2 Setup 1.0.32.exe`
- Annotated tag object: `65045dd6fe018130bc0088cee90420e99bc477b2`. 원격 peeled commit은 위 C32와 일치한다.
- [승격 영수증](C:/Users/user/Desktop/SmartFactory/PROMOTE32_20261026_780e4d2a/promotion.json) · [최종 보고서](../../04-report/production-release-risk-validation.report.md)

운영 범위는 서버 포함3대·각 화면1개, 온도/이미지 수집·저장·조회, Low Signal OFF다.
기존 FAIL/INCOMPLETE, 원인 미확정 timeout, 초기15분 health6건·PC_2 화면 가림의 한 실행 예외,
과거 자료 학습 사용 보류, comparator false/물리 NOT_TESTED를 유지한다.
복구는 향후 변경 시 별도 승인된 정상 종료·저장 검산·호환성 확인 절차로 수행한다.
기준 갱신만으로 자동 설치·복구·재시작하거나 이전 설치본/증거를 삭제하지 않는다.
이번 승격은 이미 설치·검증된 동일 바이트의 운영 등록이며 새 빌드·설치는 없다.


## 2026-10-23 승인된 출시 범위와 복구 제약 처리

[사용자 승인 정책](approved_release_policy_20261023.md)에 따라 Low Signal OFF의 물리 시험 미실시와 보류된 과거 자료의 전체 복구는 이번 수집·저장·조회 출시의 선행 조건에서 제외한다. 기존 실패와 미검증 사실은 그대로 보존한다.

등록 롤백본 1.0.26의 정상 UI 종료 요청 뒤 `/api/spot/live_image.jpg`에 발생한 502/reason shutdown은 정상 exit0·강제 종료 없음·미저장0·데이터 검산 통과를 모두 확인한 경우에만 `ACCEPTED_KNOWN_LIMITATION`으로 수용한다. 정상 수집 중 오류나 저장 실패는 제외하지 않는다. 원 179/180 결과는 재작성하지 않는다.

C32의 최종 필수 검증·운영 승격·실제 적용 확인을 마친 뒤에만 아래 등록 운영본/다음 롤백 기준을 C32로 갱신한다. 이 정책 편집 자체로 등록 버전은 바꾸지 않는다.


기준일: 2026-10-09 KST. 이 문서는 운영본·다음 개선의 복귀 기준·이번 교체 전 이전본을
구분하고 갱신하는 기준이다. 특정 commit의 영구 사용 지시가 아니다.

## 2026-10-12 이후 미서명 내부 운영 정책

사용자는 인증서가 없으며 앞으로도 SmartFactoryLogger를 미서명으로만 운영하고,
출시계획의 서명된 설치본 조건을 변경하라고 명시적으로 지시했다.
해당 사내 서버의 이후 개선본은 미서명 내부 운영 경로를 사용한다. 인증서 확보·서명 담당자·
서명 환경·유효 서명·서명자·타임스탬프를 운영 승격의 선행 조건으로 요구하지 않는다.
이 지시를 같은 서명 예외 승인으로 반복 요청하지 않는다.
실제 `NotSigned`와 `NOT_REQUIRED_BY_APPROVED_UNSIGNED_POLICY`를 기록하며 서명 PASS로 표시하지 않는다.
최종 clean commit·installer SHA256·payload/provenance 및 변경에 필요한 기술 QA,
설정/데이터 보존·정상 종료·복구·실제 승격/적용 확인 조건은 유지한다.
상세 현재 조건은 [출시 계획](../../01-plan/features/production-release-risk-validation-codex-production-release-risk-validation-20261010.plan.md#r6-최종-미서명-내부-운영-설치본과-정식-qa-검증)을 따른다.
이번 정책 반영으로 아래 실제 운영본·롤백 기준의 build commit/installer SHA256을 갱신하지 않는다.
과거 서명·기술 QA·승인 판정과 해시 결합 자료는 당시 기록으로 보존한다.

## 2026-10-23 1.0.32 현장 적용·재시작 확인

1.0.32의 실제 설치 종료 0, 설치 전후 원본 보존과 payload 1,867파일 검산,
일반 사용자 실행·정상 종료 및 CSV 493행 순번 검사를 완료했다. 기존 승인 설정의
확인 항목 네 개를 새 build에 연결한 뒤 재시작했고, 실제 수집과 대시보드 전면 표시를 확인했다.
이 적용 확인은 정식 운영 승격이 아니다. 15분 R2와 120분의 실제 종료·원시 재계산은
수집/세대 결합 범위 PASS다. 120분 후 정상 종료·CSV/원장 참조·이미지 파일 검산과
일반 사용자 재시작을 마쳤다. 현재 CSV 상세 소비자, 전체 필수 QA·물리 경계의 남은
조건은 별도 확인한다. 운영본과 아래 롤백 기준은 이번 진행 기록으로 갱신하지 않는다.

| 역할 | 버전 / build commit | installer bytes / SHA256 |
| --- | --- | --- |
| 현장에 적용해 검증 중인 후보 | 1.0.32 / `cd46692ac9c551080c57d8168fa9ea5abd530206` | 164158258 / `558658cf02d59cb6b66468e4e191c447efdc7cc24518b5a69647cc2409eb232f` |
| 이번 교체 직전의 현장 후보 | 1.0.31 / `a7e5149b718f56d7dfa75df73bfba4a21d16a758` | 164158074 / `a10a59aa544a7bfa60e40778f05b89e3cc5be6da8ca284f94f740b6e6ae4a1dc` |
| 마지막 승인·등록 운영본 및 다음 변경의 롤백 기준 | 1.0.26 / `541d701d544eea6a8a4e4836047077eaf9cfaf30` | 163826264 / `08c061ee35a1a01788f05b00ee7395aa40774150c92c06726a92f3df1bf75c3c` |

실제 설치본은 서버 `C:/Users/user/Desktop/SmartFactory/FIELD32_20261023_cd46692a/install/candidate.exe`다.
설치 결과 `J9f4b09c5`, 정상 종료 `Rd257d0f58a96`, 승인 확인 기록 갱신 `A696aaa98`,
재시작 `ST32_b73f3b70`의 해시와 독립 검토를
[현장 적용 기록](../../04-report/production-release-risk-validation-c32-field-preparation-20261023.report.md)에 연결했다.
새 전체 백업은 만들지 않았다. Low Signal OFF, 과거 자료 사용 보류, 등록 롤백본의 종료 제약을 유지한다.
기존 C31의 완료 결과를 C32 결과로 바꾸지 않으며 등록 롤백 기준은 갱신하지 않았다.

## 2026-10-22 1.0.31 현장 적용 — 당시 기록

1.0.31의 실제 설치·설치 전후 원본 보존 검산, 일반 사용자 실행, 정상 종료와 현재 CSV
검토, 기존 승인 설정의 네 확인 항목 연결 및 재시작을 완료했다. 재시작 후 대시보드·작업 정보와
전면 상태도 사용자가 확인했다. 아래 2026-10-20 표는 당시 현장 설치 이력으로 보존한다.

| 역할 | 버전 / build commit | installer bytes / SHA256 |
| --- | --- | --- |
| 현장에 적용해 검증 중인 후보 | 1.0.31 / `a7e5149b718f56d7dfa75df73bfba4a21d16a758` | 164158074 / `a10a59aa544a7bfa60e40778f05b89e3cc5be6da8ca284f94f740b6e6ae4a1dc` |
| 이번 교체 직전의 현장 후보 | 1.0.30 / `240a49522da5d59e9e823f62612e3d4207b497a9` | 164158434 / `56ec126261970efbcee26fa22789d57c313dc8d27e5a71bb6b9296c3cab891b4` |
| 마지막 승인·등록 운영본 및 다음 변경의 롤백 기준 | 1.0.26 / `541d701d544eea6a8a4e4836047077eaf9cfaf30` | 163826264 / `08c061ee35a1a01788f05b00ee7395aa40774150c92c06726a92f3df1bf75c3c` |

새 후보 설치본의 실제 서버 경로는
`C:/Users/user/Desktop/SmartFactory/FIELD31_20261022_a7e5149b/install/candidate.exe`다.
설치 결과 `Jc4d79976`과 새 버전 종료 결과 `R575b518825b1`, 승인 설정 연결 결과
`A4e537c18` 및 재시작 결과 `ST31_e5b547e9`를 각각 독립 검토했다.
상세 범위·해시·검사 명령은 [새 버전 적용·종료·재시작 기록](../../04-report/production-release-risk-validation-c31-close-readiness-20261022.report.md)에 있다.

이 표는 현장에 실제 설치된 후보 식별의 갱신이다. 운영 승격이나 다음 롤백 기준 변경은 아니다.
2026-10-23에는 C31 자체의 15/120분 수집·세대 결합, 닫힌 CSV105,816행·이미지23,022개,
최초CSV3,047행 검산 및 실제4기기 관찰의 확인된 범위가 추가 완료됐다. PC4곳의 계속 갱신은
교체 후 약555초 구간에 대한 사용자 확인이며 전체 성능·물리 경계·정식QA는 미완료다.
[최신 완료 범위·남은 조건](../../04-report/production-release-risk-validation-goal-alignment-20261022.report.md)을 따른다.
기존 240a의 120분 결과를 C31 통과로 재표시하지 않는다. 미서명 내부 정책과
Low Signal OFF 조건, 과거 데이터 사용 보류 및 541d 종료 제약도 유지한다.

## 2026-10-22 완료 증거 연결 — 등록 기준 변경 없음

240a/56ec 후보의 120분 수집·세대결합과 해당 닫힌 실행 CSV41,487행·JPEG8,912개 검산은
완료됐다. VM 동시 조회3조건의 자료 검토도 완료했지만 실제3PC·전체 성능·물리 경계·과거 원인·
전체 데이터와 정식 QA는 미완료다. 설치/복구 matrix의 등록541d 종료502 오류1건도 유지한다.
운영 승격이나 다음 롤백 기준 갱신은 하지 않았다. 아래 표의 역할과 SHA는 그대로다.

[등록 롤백본 종료502 대조](../../04-report/production-release-risk-validation-rollback-shutdown-attribution-20261022.report.md)에서
541d의 내부 종료 요청 거절과240a의 기존 종료 순서 수정 적용을 확인했다. 해당541d 실행의 이미지
105건은 저장 완료됐지만 무오류 검사 실패는 유지한다. 구버전 복귀 시 종료 제약의 처리 결정은
미완료이며, 이 원인 확인을 이유로 기존 설치본을 재작성하거나 자동 복구하지 않는다.

[목표 정합성 점검](../../04-report/production-release-risk-validation-goal-alignment-20261022.report.md)에
완료 범위와 남은 R1–R6 조건을 연결했다. 아래 2026-10-20 시점의 ‘관찰 진행 중’ 문구는
당시 이력이며 현재 실행 상태를 뜻하지 않는다. 완료된 같은120분 검사를 자동 반복하지 않는다.

## 2026-10-20 현장 검증 설치본과 등록된 복귀 기준

아래는 보존된 설치 영수증과 2026-10-20 17:54:31 KST의 실행 조회를 대조한 상태다.
같은 실행을 대상으로 한 120분 관찰과 새 데이터 검증은 진행 중이다.
이 절은 현재 설치된 현장 후보를 식별하며 운영 승격이나 등록된 롤백 기준 변경이 아니다.
아래 과거 기록의 “현재 운영본”은 당시 승인·등록된 기준을 뜻한다. 실제 현장 설치본과 구분한다.

| 역할 | 버전 / build commit | installer bytes / SHA256 |
| --- | --- | --- |
| 현장에 적용해 검증 중인 후보 | 1.0.30 / `240a49522da5d59e9e823f62612e3d4207b497a9` | 164158434 / `56ec126261970efbcee26fa22789d57c313dc8d27e5a71bb6b9296c3cab891b4` |
| 이번 교체 직전의 현장 후보 | 1.0.30 / `8de064317d6de42d321afb8395f7a30a1f31cd55` | 164150064 / `f1b6d4d843504e09410cd90dcd309a0e485e9fd7a59a524b64941c61719f5a32` |
| 마지막 승인·등록 운영본 및 다음 변경의 롤백 기준 | 1.0.26 / `541d701d544eea6a8a4e4836047077eaf9cfaf30` | 163826264 / `08c061ee35a1a01788f05b00ee7395aa40774150c92c06726a92f3df1bf75c3c` |

두 1.0.30 후보는 표시 버전이 같아 commit과 installer SHA로 구분한다.
8de를 교체 직전 후보로 기록한 것은 승인된 복귀 기준으로 승격했다는 뜻이 아니다.
설치 영수증의 원래 서버 경로는 다음과 같다. 이 문서 검토에서는 서버 파일을 다시 읽거나
설치·복구·정리하지 않았으며, 실제 사용 전에는 대상 파일과 승인된 복구 절차를 재확인한다.

- 240a: `C:\Users\user\Desktop\SmartFactory\FIELD240A_20261020_d2cbfa10\install\candidate.exe`
- 8de: `C:\Users\user\Desktop\SmartFactory\FIELD8DE_20261019_f62a1c90\install\candidate.exe`
- 541d: `C:\Users\user\Desktop\SmartFactory\H30_20261016_b5d184c2\install\rollback.exe`

240a 설치는 실제 종료 코드0이며 당시 설치 payload1,867파일과 원본 보존을 검산했다.
17:54 실행 조회 및 초기 관찰은 main7528/backend20088,
logger `551b463e-79f4-4d74-b8bd-a0ae922f207f`,
CSV `Factory_Integrated_Log_v2_20261020_172326.csv`에 결합돼 있다.
관찰 완료 후 동일 실행의 최종 검토·정상 종료·저장 검증을 계속해야 한다.
물리 경계, 과거 데이터/누락 원인 및 전체 필수 QA가 남아 있어 출시 HOLD를 유지한다.
새 운영본·다음 롤백 기준 갱신은 별도의 실제 승격·적용 확인이 끝난 뒤 수행한다.

근거: [설치·원본 보존 검토](C:/Users/user/Desktop/SmartFactory/F20READY_20261020_d2cbfa10/installation-final-review/review.json),
[설치본 3종 식별 영수증](C:/Users/user/Desktop/SmartFactory/F20READY_20261020_d2cbfa10/installation-final-review/returned/installer-inputs.json),
[120분 초기 결합 검증](C:/Users/user/Desktop/SmartFactory/OP120R2_20261020_61be7c90/started-phase/verification.json).
기존 해시 결합 증거와 아래 과거 승인 기록은 보존한다.

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

## UI-S1 소스 병합과 운영 인계

2026-10-09 사용자의 후속 로드맵 "진행 승인"은 UI-S1 PR·보호된 master 병합과 기존 운영본의
이력 연결에 적용한다. 실제 병합 전후의 SHA·PR·CI·출처 비교는
`C:/Users/user/Desktop/SmartFactory/S1_MERGE_20261009_R1`의 새 영수증으로 기록한다.
[PR203](https://github.com/zzocojoa/SmartFactoryLogger/pull/203)은2026-10-09T15:11:42Z
(2026-10-10 00:11:42 KST)에MERGED됐고 실제master merge는
`fb38b872f1f3ea371ac3dea29641a5939ed54074`다. 검증한PR head는
`401025ed3d31ca013269b11c1f4d20c814f90f6e`, 제품build는위의541d다.
merge와PR head의전체tree가같고 docs밖818항목·제품/검증571입력이541d와같다.
실제merge와제품build를별도로관리하며 문서후속commit으로 운영installer identity를바꾸지않는다.

제품 build541d와 문서 후속 HEAD의 docs 밖818개 Git 항목이 동일하고 최종health 입력571개가
최종 exit0 당시와 동일함을 대조했다(preflight.py exit0). health stdout/stderr를 모두 읽고
원문 해시·실제 exit0·frontend434/backend880(기존skip1)/QA 결과를 확인했다. 동일 설치본을
재빌드·재설치하지 않는다. PR CI가 생성하는 별도 시험 설치본은 운영08C installer가 아니다.

PR203의Frontend CI/Operations offline fixtures/Windows PR Artifact 세결과는SUCCESS다.
새병합완료영수증product-merge-complete.json과CI원문/메타데이터pr-ci-final.json을보존한다.
기존operating-promotion-001.json 원문해시도유지했으며 서버재설치·시작/종료·재시작·자동복구는없다.

### 현장 대응과 복구 인계

| 표시/상황 | 우선 확인 | 운영 원칙 |
| --- | --- | --- |
| SPOT OK / Temp UNDER_RANGE 또는 OVER_RANGE | 측정 조건·장비 응답 상태 | 통신 재연결부터 시도하지 않는다. 제품 부재·실제 물리 원인·공정 안전으로 단정하지 않는다. |
| SPOT DOWN | 장비 응답·통신 경로·최근 오류 | 과거 정상값 또는 CACHED가 현재 통신 정상의 근거가 아니다. |
| STALE 또는 UNKNOWN | 마지막 갱신 경과·화면 갱신 상태·진단 상세 | 현재 상태를 판단할 자료가 충분한지 확인한다. |
| Temp CACHED | 기존 허용 기한과 새 응답 | 이전 값임을 인지하며 기한을 늘리거나 값을 정상 수신으로 바꾸지 않는다. |
| 다음 개선본 시험 실패 | 현재541d/08C 운영본 | 승인된 정상 종료·보존·호환성 확인 후 복구한다. |
| 현재 UI-S1 운영본 자체의 장애 | 교체 전4c/D453·설정/CSV 보존 근거 | 이전본의 호환성과 실제 원인을 확인한다. 현재 실패본 재설치를 롤백이라고 부르지 않는다. |

설치본 불일치, 지속 수집 중단, 새 CSV 손상 또는 예상하지 않은 설정 변경은 새 변경 승격을
보류하고 근거를 수집할 조건이다. 자동 강제 종료·재설치·counter 초기화·복구는 실행하지 않는다.
현재 수용한223ms/최초timeout 등의 기록과 새로운 장애를 구분한다.

### 정식 검증 후속 목록

| 항목 | 담당 역할 | 완료 근거와 현재 한계 |
| --- | --- | --- |
| 최초 API timeout·200ms 기준 초과 | 개발/성능 담당 | 발생 조건·원인·영향을 확인하고 필요한 보완의 회귀·성능 결과 확보. 현재 원인 미확정/전체성능 PASS 아님. |
| 장비 설정·비교 기준 | 장비/QA 담당 | 승인 장비 조건과 실제 설정의 대조·comparator 검증. 원래 파일 보존만으로 일치 검증을 대신하지 않음. |
| 전체 CSV·개별 이미지와 과거drop15 | 데이터 QA/개발 담당 | 합의한 검증 범위의 원문 결과·누락 원인 확보. 현재 제한 구간 확인이며 전수 검증/과거 누락 해결 아님. |
| 정식 서명·품질 검증 | 릴리스/QA/운영 책임자 | 실제 서명과 기술 QA 근거 각각 확보. 새 파일은 새 SHA로 검증하며 내부 승인으로 PASS를 만들지 않음. |
| 식별 정보 없는 구형 메시지 순서 | frontend/QA 담당 | 지원 계약·추가 필요 범위를 결정. 현재 fallback의 완전한 cross-source 순서 보장 없음. |

위 목록은 남은 정식 검증의 인계다. 이번 소스 병합으로 제품 수정·인증서 구성·새 서버 시험을
자동 실행하거나 현재 한계를 해소한 것으로 표시하지 않는다.

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
| 2026-10-12 | 이후 미서명 내부 운영을 지속하고 출시계획의 서명 선행 조건 제거 | 사용자 인증서 없음·미서명 운영 지시. 기술 QA·출처/해시·승격/적용 확인 조건과 실제 운영본/롤백 identity 유지 |

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

## 2026-10-19 중복 정리 후 서버 보존 경로

사용자가 승인한 Desktop SmartFactory 정리로 중복 설치본을 삭제했다. 위 운영/롤백 build와 SHA256은 변경하지 않는다.
이전 절의 서버 경로는 당시 기록이며, 새 작업에서는 아래 보존본을 사용한다. 2026-10-19 14:10 KST 후검산에서
파일 크기·SHA256을 다시 확인했다. 기존 helper·manifest 내용은 수정하지 않았다.

| 설치본 | 현재 서버 보존 위치 | SHA256 |
|---|---|---|
| 등록 운영/롤백 541d701d | `C:\Users\user\Desktop\SmartFactory\H30_20261016_b5d184c2\install\rollback.exe` | `08c061ee35a1a01788f05b00ee7395aa40774150c92c06726a92f3df1bf75c3c` |
| 이전 4c97d4a0 | `C:\Users\user\Desktop\SmartFactory\S1_CAND_20261009_R1\installers\ROLLBACK_4c97d4a_UNSIGNED.exe` | `d453c1d17efc706d3e21fe6f8d09f739f159ebf9f3f24f2eb2349e92d4ef84fb` |
| 더 이전 d7a1b20f | `C:\Users\user\Desktop\SmartFactory\SFL_TRC_STAGE_20260920_R1\rollback-d7a1b20\smart-factory-logger-v2 Setup 1.0.26.exe` | 보존 대응표 및 후검산의 해당 파일 SHA256 참조 |

예전 절차를 재실행하려면 대표 설치본을 당시의 정확한 경로로 복원하고 기존 외부 해시와 대조해야 한다.
개발 PC의 동일 바이트 사본도 보존했다. 이 경로 정리는 앱 설치·자동 복구·운영 승격이 아니다.
[정리 및 복원 대응표](C:/Users/user/Desktop/SmartFactory/CLEAN_SERVER_20261019_A/cleanup-report.md),
[대표 설치본 후검산](C:/Users/user/Desktop/SmartFactory/CLEAN_SERVER_20261019_A/postcheck-r2.json).
