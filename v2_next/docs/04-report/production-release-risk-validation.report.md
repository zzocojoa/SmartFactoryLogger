# SmartFactoryLogger 출시 위험 검증 — 최종 보고서

2026-10-26 KST. **1.0.32를 승인된 제약을 포함한 내부 운영본으로 승격했다.** 다음 개선의 롤백 기준도 같은 설치본으로 갱신했다.
완료 범위는 온도·이미지 수집/저장/조회와 서버 포함3대·각 화면1개다. 원래 기술 FAIL·INCOMPLETE를 PASS로 바꾸지 않았다.

## 설치본과 실제 적용

| 항목 | 값 |
|---|---|
| 버전 / 태그 | 1.0.32 / v1.0.32 |
| Build commit | `cd46692ac9c551080c57d8168fa9ea5abd530206` |
| Installer | 164,158,258 bytes / `558658cf02d59cb6b66468e4e191c447efdc7cc24518b5a69647cc2409eb232f` |
| 서명 | NotSigned — 지속 승인된 미서명 내부 운영 |
| 현재 / 다음 롤백 기준 | 동일 C32 설치본 |
| 기존 보존본 | 등록 C26, 설치 직전 후보 C31; 삭제하지 않음 |

현재 서버 설치 payload1,867파일(561,612,721bytes)과 제거 파일1개, 설치본 전체 해시를 다시 검산했다.
동일 main/backend·자식5프로세스의 생성 시각과 일반 사용자 실행을 확인했다. CSV 행 수41026→41061→41836,
logger `3cae5602-c466-4175-8b35-9f27eff2975f`, 설정 해시·승인 fingerprint 불변을 확인했다.
임시 진단 포트19221은 열려 있지 않다. 원격 화면에서 Running·온도·카메라·작업60589/금형1·전면 표시를 확인했다.
이 현재 실행의 확인은 진행 중 CSV를 종료·마감 검증했다는 의미가 아니다.

## 이번 승인과 남는 제한

| 항목 | 최종 처리 |
|---|---|
| 10월9일 설치 후 확인 timeout | UNCONFIRMED/APPLY_HOLD 보존. 정확한 과거 사건만 현재 출시 선행 조건에서 분리 |
| C32 초기15분 health | p99 228.7438ms, 최대1495.1224ms, 기준200ms 초과6건·오류/timeout0. 원래 FAIL 유지, 해당 실행만 제약 수용 |
| PC_2 표시 | 900초 전체 수치 충족. 약28초 가림만 승인 예외, CAPTURE_INCOMPLETE 유지. 재측정 없음 |
| 최종 현장 QA | 보존 현장/정상 종료/CSV 소비자 근거로 통합. 원래 일괄 명령의 새 FINAL PASS 실행을 주장하지 않음 |
| Low Signal | OFF·comparator false·물리 NOT_TESTED. 활성화 전 별도 시험/승인 필요 |
| 과거 자료 | 온도19/PLC1 손상 및 과거 이미지 거부 실행의 원본 보존·학습 사용 보류 유지 |
| 초기 C32 두 실행 | 수신 간격 FAIL·일부 마감 증거 공백 보존. 승인된 17:25:45 닫힌 세대가 출시 데이터 검증 범위 |
| 구버전 C26 | 정상 UI 종료 뒤 확인된 shutdown 502만 한정 수용. 정상 수집 중 오류·저장 실패·강제 종료는 면제하지 않음 |

새 요청 오류/timeout/저장 손실이나 다른 실행에 예외가 자동 적용되지 않는다. 실제 부품번호·교정/물리 성능,
전체 센서 샘플 무누락과 딥러닝 적합성은 확인되지 않았다. HTTP 약1초 수신은 학습 시간 해상도 보장이 아니다.
닫힌 세대의 HTTP관측9098개 중789개는 invalid sentinel이며, 수신 공백과 유효 온도 공백을 구분해 보존했다.

## 검증 결과

| 검증 | 결과·범위 |
|---|---|
| 최종 clean 소스/설치본 | 기존 health exit0: backend964 통과/1skip, 의존성15, Electron103, 화면Node9/Vitest442. 동일 clean HEAD·installer를 이번에 다시 확인 |
| VM 설치/복구 | 보존된 C32 설치·업그레이드·정상 재시작·C31/C26복구·C32복귀·768포트 순환 근거 및31요약 조건 검산 |
| 현장 설치 | 기존 installer exit0·설치 전후 원본 보존 근거 확인; 이번 재설치 없음 |
| 정상 시작 | 실제3회30초 이내. OS 캐시 초기화 시험은 아님 |
| 120분 HTTP | health p99 82.7279ms, data p99 67.8831ms. 예정 요청 누락·오류·timeout0 |
| 현재 출시 세대 온도 수신 | 9098관측, 간격p99 1084.018ms·최대2710.821ms. 물리 샘플 완전성 아님 |
| 표시 PC_1 | p95 388ms / p99 408ms / 최대700ms |
| 표시 PC_2 | p95 384ms / p99 664ms / 최대700ms; 가림 예외 수용 |
| 표시 PC_3 | p95 384ms / p99 648ms / 최대716ms |
| 닫힌 CSV | 37944행·관측 연결37926행, 실제 소비자 exit0·입출력/해시/정상 종료 근거 재확인 |
| 닫힌 이미지 | 8375파일/8375fact, 누락·orphan·해시/디코딩 이슈0, 실제 소비자 exit0·정리 완료 근거 확인 |
| 최종 통합 재검산 | 보존 QA41조건·health3602개·입력7219파일, 부정 사례13개 거부. 추가 참조1353파일 검산(앞 입력과 중복 가능), exit0 |
| 운영 등록 | 태그 생성·push·원격 tag object/peeled commit 대조 모두 exit0, 실제 설치 동일성 확인 후 기준 갱신 |

세 PC는 각각900초 계측했지만 모든 기기의 계측 창이 같은 시간 구간은 아니다. 각 보완 구간의3대 동시 조회와
흰 화면/멈춤 없음은 사용자 확인에 연결된다.4대 이상의 정량 성능 보장은 하지 않는다.
41조건은 원 QA 정상 경로 이름40개+오류 처리 분기의 파생 확인1개다. 알람 제외1개는 별도이며 물리 PASS가 아니다.

이번 실행 명령: `begin.py`(승인 결합/보존 QA 재검산), `assess_server.py`(성공한 SSH 읽기 결과/metadata 대조),
`consolidate.py`(최종 통합), `promote.py`(정확한 태그 등록) 모두 최종 exit0이다.
첫 로컬 감사의 health/config 필드 위치·로그 하위 경로·PC별 결과 필드 차이와 기존 설명 보고서의 갱신된 해시를
정확한 기록으로 보완했다. 실패한 시도는 보존하며 서버 재설치·현장 재측정으로 반복하지 않았다.
비공개 F01 fixture 미제공의 기존1skip, tzdata hidden-import 및 deprecated 경고를 보존한다.
전체 health·CSV/이미지 소비자·15/120분 검사는 동일 설치본의 검증 완료 기록을 재사용했다.

## R1–R6 완료 조건 대조

24개 조건 모두 사용자 승인으로 확정한 범위에서 근거/처분이 연결됐다. 예외·제외를 포함한 완료이며 기술 검사100% PASS라는 뜻이 아니다.
일반적인 설계-코드 일치율 점수는 새로 산정하지 않았다. 최종 판정은 아래 개별 근거·명시 승인에 따른다.

| 조건 | 최종 상태 | 처리 |
|---|---|---|
| R1.1 | APPROVED_HISTORICAL_SEPARATION | 10월9일 단일 사건의 원인 UNCONFIRMED를 유지하며 사용자 승인으로 현재 출시 선행 조건에서 분리한다. |
| R1.2 | VERIFIED_FIXES_WITH_HISTORICAL_LIMIT | 확인된 포트/초기화/종료 경로 회귀는 보존한다. 과거 최초 timeout이 수정됐다는 주장은 하지 않는다. |
| R1.3 | VERIFIED_CURRENT_WINDOWS_WITH_HISTORICAL_LIMIT | 현재 초기15분·120분 요청 오류와 timeout 0. 과거 사건의 동일 조건 재현 또는 재발 가능성 제거의 증명은 아니다. |
| R1.4 | PRESERVED_WITH_APPROVED_DISPOSITION | 원 사건의 UNCONFIRMED/APPLY_HOLD 유지. 이 사건 때문에 현재 전체 출시를 HOLD하는 조건만 명시 승인으로 대체한다. |
| R2.1 | ACCEPTED_WITH_DOCUMENTED_LIMITATIONS | 초기15분 health 원래 FAIL을 유지하고 해당6건만 수용. 데이터/120분 통과, 표시 가림 한 실행 예외를 각각 연결한다. |
| R2.2 | ACCEPTED_APPROVED_OPERATIONAL_SCOPE | 실제 정상 시작3회30초 이내, 승인된 닫힌 세대의 온도 수신,120분/API·3대 표시 기준과 두 한정 예외를 연결한다. |
| R2.3 | PRESERVED_WITH_APPROVED_EXCEPTION | 가림 약28초를 지우지 않고 원시 INCOMPLETE·수치 PASS·한 실행 예외 수용을 분리한다. PC별900초는 동일 계측 구간이 아니다. |
| R2.4 | PRESERVED | 기존 단발 초과 FAIL과 초기15분 FAIL을 보존한다. 별도 재평가가 과거 원문을 덮어쓰지 않는다. |
| R3.1 | VERIFIED_APPROVED_DISABLED_SCOPE | 승인 관찰 프로파일·운영자·build·fingerprint·drift 조건을 보존 QA로 검산. 실제 부품번호/교정/물리 성능은 미확인으로 유지한다. |
| R3.2 | VERIFIED_IN_SCOPE | 현재 평가 대상의 runtime·설정·마감 fingerprint 결합과 drift0 확인. 다른 실행으로 무조건 소급하지 않는다. |
| R3.3 | APPROVED_SCOPE_EXCLUSION | 운영자 확인은 검증. Low Signal OFF·comparator false인 승인 범위에서만 알람 제외. 물리 시험은 NOT_TESTED. |
| R3.4 | VERIFIED_IN_SCOPE | 이전 승인 설정 연결·설치 전후 원본 검산 및 기존 복구 근거를 보존. 불필요한 전체 백업은 추가하지 않는다. |
| R4.1 | CURRENT_SCOPE_VERIFIED_HISTORY_SEPARATE | 현재 닫힌 세대의 상세 검사와 고정 자료 분류를 연결. 과거 전체 복구/인과는 별도 관리하며 모든 과거 자료 PASS로 표기하지 않는다. |
| R4.2 | VERIFIED_SELECTED_CLOSED_GENERATION | 17:25:45 세대 CSV37944행·연결37926행 및 저장 이미지8375개 검산 완료. 초기 두 세대의 마감 증거 공백은 보존한다. |
| R4.3 | APPROVED_HISTORICAL_USE_HOLD | 온도19/PLC1 손상 및 과거 이미지 거부 실행은 원본 보존·학습 사용 보류. 복구 완료가 아니며 과거 원인/영향 미확정을 명시한다. |
| R4.4 | PRESERVED | 원본·기존 판정을 수정하지 않고 현재 닫힌 세대 검산을 전체 과거 자료 합격으로 확대하지 않는다. |
| R5.1 | HISTORICAL_CAUSE_UNCONFIRMED_SEPARATED | 과거15회 거부의 개별 이미지/인과는 미확정. 해당 자료 사용 보류와 출시 선행 조건 분리 승인을 적용한다. |
| R5.2 | APPROVED_DISPOSITION | 책임자의 원본 보존·학습/품질 분석 사용 보류 결정 유지. 15회 거부를 서로 다른 이미지15개 손실로 단정하지 않는다. |
| R5.3 | VERIFIED_CURRENT_SCOPE | 확인된 경로 회귀·현재 대상 정상 종료·저장 실패0·잔량0 및 이미지 바이트/디코딩 검산 연결. 과거 원인 해결을 뜻하지 않는다. |
| R5.4 | PRESERVED_WITH_SCOPE_CHANGE | 과거 원인 미확정은 유지하되 승인된 과거 이미지 사건은 현재 출시의 선행 조건에서 분리한다. |
| R6.1 | VERIFIED_EXACT_TAG_AND_OPERATIONAL_BASELINE | 정확한 C32/installer/NotSigned·현재 서버 payload·로컬/원격 v1.0.32 태그와 다음 롤백 기준을 확인했다. |
| R6.2 | ACCEPTED_RETAINED_CONSOLIDATED_QA | 소스/패키지·VM 설치/복구·현장 설치 및 원시3602요청/종료/CSV 조건41개를 재검산했다. 사용자 승인된 통합 QA이며 새 원래 일괄 명령 FINAL PASS는 아니다. |
| R6.3 | ACCEPTED_WITH_SCOPED_DISPOSITIONS | 승인된 닫힌 실행의 설정·CSV37944행·이미지8375개·정상 종료와 성능/표시 예외를 결합하고 현재 서버 payload/일반 실행을 다시 확인했다. |
| R6.4 | NOT_REQUIRED_UNSIGNED_POLICY | 사용자의 영구 미서명 정책 적용. NotSigned를 서명 PASS 또는 QA 대체로 표기하지 않는다. |

## 운용 방법과 재검토 조건

- 서버 포함3대·각 대시보드1개, Low Signal OFF와 승인 설정을 유지한다. 작업자는 제품·금형 변경 시 실제 값을 입력한다.
- 새 빌드/설정/동시 사용자 수 변경에는 영향받는 검증을 적용한다. 이번 지연·가림 예외를 다른 실행에 재사용하지 않는다.
- 요청 timeout/오류, 화면 지속 정지, 저장 실패가 새로 나타나면 해당 실행 기록을 보존하고 원인·영향을 별도 판단한다.
- 다음 개선 시 이번 C32 installer SHA를 복귀 기준으로 확인한다. 자동 복구·강제 종료·새 전체 백업을 추가하지 않는다.
- 학습용 데이터는 사용 보류 목록을 제외하고, 학습 목표의 최소 변화 시간과 유효 온도/상태/관측 ID를 별도로 검증한다.

## 개선 과정에서 확인한 점

실제 화면의 로드 완료 후 대기 방식과 고정 주기 부하 시험을 구분해야 한다. 입력 초점/가림과 프레임 오류도 구분한다.
계측 도구의 미시작·미완료를 이미지 저장 손실로 표현하지 않는다. 이미 검산된 동일 설치본의 증거는 재사용하고,
처리 방침 변경은 원래 실패를 지우지 않는 별도 승인 기록으로 남긴다.

## 근거

- [고정 승인 기록](../V2/05_운영_배포/approved_final_disposition_20261026_c32.json)
- [통합 QA](C:/Users/user/Desktop/SmartFactory/PROMOTE32_20261026_780e4d2a/consolidated-qa.json)
- [승격·태그 영수증](C:/Users/user/Desktop/SmartFactory/PROMOTE32_20261026_780e4d2a/promotion.json)
- [최종 24조건 기계 판독 기록](C:/Users/user/Desktop/SmartFactory/PROMOTE32_20261026_780e4d2a/completion.json)
- [현재 운영·롤백 기준](../V2/05_운영_배포/operating_rollback_baseline.md)
- [계획](../01-plan/features/production-release-risk-validation-codex-production-release-risk-validation-20261010.plan.md) · [설계](../02-design/features/production-release-risk-validation.design.md) · [분석](../03-analysis/production-release-risk-validation.analysis.md)

