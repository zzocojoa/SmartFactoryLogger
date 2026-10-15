# Low Signal 경계 시험의 적용 범위와 준비 기록

2026-10-13. **현재 App1: AL E에서 물리 comparator가 검증됐다고 판정할 근거는 아직 없다.**
제조사 설명서의 적용 모드와 신호값 정밀도를 확인해, 단순히 화면의 1/2/3%를 모으는
방법으로는 임계값 2%의 미만/동일/초과 검증을 마칠 수 없다는 조건을 구체화했다.
이후 USER_SELF가 [관찰 프로파일](production-release-risk-validation-device-profile-20261013.report.md)을
운영 기준으로 승인했다. 아래 물리 시험의 적용 범위·정밀도 조건은 별도로 남는다.
장비 설정·서버 앱·후보 설치본은 변경하지 않았다.

## 제조사 자료와 실제 장비의 범위

[SPOT+ Family User Guide 815954 Issue 18](https://www.ametek-land.com/-/media/ameteklandinstruments/documentation/products/fixedspotnoncontactthermometers/spot-plus/ametek_land_815954_new_spotplus_family_user_guide_issue_18_en.pdf?la=en&revision=dd2d63ad-e71a-4507-9808-82da77ff1ad6),
2025-07-16, 4.8절(인쇄4-17/PDF37쪽)의 색인 본문은 Low Signal 알람의
대상을 Ratio/Multi로 명시하고 설정 신호값보다 낮을 때 작동한다고 설명한다.
따라서 일반 설명은 `lt`를 시사하지만, App 모드·펌웨어40.38에 대한 명시적 계약으로
확대할 수 없다. App1에서 미지원이라고 확정한 것도 아니다.
직접 다운로드 및 페이지 이미지 조회는 사이트 점검 HTML을 반환했다.
원본 PDF를 확보·시각 검증했다는 주장은 하지 않으며 색인 본문이라는 출처 한계를 남긴다.

별도로 보유한 [REST API 안내서](../reference/ametek_land_spot.pdf) Issue2(2024-07-31)의
7–8쪽(인쇄2-1/2-2)을 텍스트와 렌더링 이미지로 대조했다. 7쪽의 `alarmstatus` bit4에도
별표가 있으며, 8쪽의 해당 각주는 Ratio 또는 Application-specific **모델**을 포함한다.
이는 Application 모델의 프로토콜 제공 근거를 보완한다. Family 안내서의 Ratio/Multi
**모드** 설명과 적용 범위가 달라 App1/40.38의 동작 확인이 필요하다. 모든 App 모드의
지원이나 미지원을 이 두 설명만으로 확정하지 않는다. 12쪽의 Application 응답 예시도
실제 장비 시험 결과가 아니다.
`signalpc`는 0–100의 정수 %다. 이 출력과 내부 알람 비교의 정밀도가 같다는 설명은 없다.
**추론:** 표시값 2%는 내부 비교값의 정확한 동일성을 증명하지 않으며, 알람 bit4가
0이었다는 사실만으로 `<`를 확정할 수 없다. 현재처럼 알람이 꺼져 있을 때의 bit4=0도
활성 알람의 경계 동작을 검증하지 못한다.

[실제 장비 관찰](production-release-risk-validation-device-profile-20261013.report.md)은
SPOT+ AL / App1: AL E / 모드값7 / 펌웨어40.38 / Low Signal 꺼짐 / 저장값2%다.
UI에 알람 항목이 있다는 사실과 해당 모드에서 펌웨어가 알람을 평가한다는 증거는 구분한다.

## 기존 소프트웨어 계약 대조

`backend/FacilityData/spot_low_signal.py`의 수치 판정은 검증된 comparator에만 적용된다.
`lt`는 동일값에서 false, `lte`는 true이며, 미검증이면 numeric 판정은 None이다.
알람 비활성 시 임계값 미만 숫자는 비인과 증거로 기록된다. 실제 alarmstatus bit4는
수치 추론과 별도 증거다. attestation 도우미는 comparator configured_verified=false를
거부한다. 관찰 프로파일 승인만으로 이 필드를 true로 바꾸지 않는다.

관련 기존 테스트 7개를 격리 APPDATA에서 실행해 모두 통과했다(actual exit0, skip0).
결과 stdout/stderr 원문을 증거 폴더에 보존했다.
대상은 bit4·미만·동일·초과·비활성·미검증 처리와 attestation 차단 조건이다.
실제 소스 5파일은 후보 build `4cc7393e1bafbf90a329726aed9470fe0daacb21`과
CRLF를 정규화한 내용이 같음을 대조했다. 이것은 소프트웨어 계약 검사이며
장비 펌웨어 검증이나 새 전체 health/build/NSIS 결과가 아니다.

## 현장 기록 양식과 실행 전 조건

다음은 **미실행 시험 준비표**다. 화면 조작만으로 현재 생산 장비의 알람을 켜거나
물리 시야·측정 대상을 바꾸는 절차를 실행하지 않았다.

1. 모델·펌웨어·App1 모드에서 Low Signal 기능이 평가되는지 근거를 확보한다.
   제조사 명시 자료/답변 또는 해당 모드의 승인된 격리 시험으로 확인하며
   Ratio/Multi로 바꾼 결과를 App1 검증으로 사용하지 않는다.
2. 내부 비교값과 REST 정수값의 관계, equality 확인 방법을 확정한다.
   방법이 없으면 동일 구간은 `INCONCLUSIVE`로 남긴다. 반복 횟수로 정밀도 한계를 덮지 않는다.
3. 장비 담당자 USER_SELF가 시험 장치·실제 알람 출력 연결·생산 영향·변경/복원 범위를
   검토한다. 현재 운영 프로파일 승인은 이 시험 변경의 승인과 별개다.
4. 승인된 시험에서 같은 GET `/output` 응답의 signalpc·alarmstatus·온도와 모드/설정을
   연결한다. HTTP 원문·수신시각·지연·기준 신호/불확도를 보존한다.
   같은 응답이라는 사실을 문서 근거 없는 내부 동시 측정 보장으로 확대하지 않는다.
5. 아래 각 구간의 실제 결과와 판정을 기록하고, 종료 후 원래 설정·알람 상태를 대조한다.
   최종 후보의 build/fingerprint/operator attestation 및 정상 종료 증거는 별도로 연결한다.

| 구간 | 필요한 근거 | `lt`를 시험 가설로 쓸 때 예상 | 현재 결과 |
| --- | --- | --- | --- |
| 비활성 대조 | 알람 off 및 실제 설정 | 이 조건으로 활성 경계 판정 불가 | 미실행 |
| 임계값 미만 | 내부 비교 기준보다 낮음이 입증된 자극 | bit4=1 | 미실행 |
| 임계값 동일 | 내부 비교의 동일성이 입증된 자극/계약 | bit4=0 | 미실행·방법 미확정 |
| 임계값 초과 | 내부 비교 기준보다 높음이 입증된 자극 | bit4=0 | 미실행 |
| 설정 복원 | 변경 전/후 전체 프로파일·출력 대조 | 승인된 원래 설정과 일치 | 변경 없음 |

기록 필드: 시험ID · USER_SELF 승인 근거 · 모델/펌웨어/모드 · build/fingerprint ·
알람 enabled/threshold · 기준 자극/불확도 · raw GET 파일/SHA256 · signalpc/alarmstatus/bit4 ·
상승/하강 방향·안정화 조건 · 관찰/예상/불일치 · PASS/FAIL/INCONCLUSIVE · 복원 증거.
예상값은 시험 가설이며 현재 펌웨어의 관찰 결과를 채워 넣은 값이 아니다.

## 증거와 현재 판정

증거 위치는 `C:/Users/user/Desktop/SmartFactory/PDCA_COMPARATOR_20261013_4cb184e9`다.
[출처·한계 기록](C:/Users/user/Desktop/SmartFactory/PDCA_COMPARATOR_20261013_4cb184e9/source-review.json),
[직접 다운로드 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_COMPARATOR_20261013_4cb184e9/download.json),
[소프트웨어 검사 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_COMPARATOR_20261013_4cb184e9/software-guards.json)을 연결한다.
HTTP200 응답은 7,291바이트 HTML이므로 PDF 다운로드 성공으로 세지 않는다.
실제 물리 경계 시험 `NOT_TESTED`, 관찰 운영 프로파일 승인 완료, 정식 출시 **HOLD**다.
이 보고서의 기존 증거 묶음 안 승인 대기 표시는 당시 기록으로 보존한다.

## 후속 배선 확인과 Modbus 자료 대조

USER_SELF는 CMD OUT 알람 접점이 PLC/설비의 정지·제어 입력에 “연결되어 있지 않음”이라고
답했다. [질문·답변 원문](C:/Users/user/Desktop/SmartFactory/PDCA_SOURCE_SCOPE_20261013_5bbfe655/wiring-statement.json)에
사용자 확인과 독립 배선 검사를 구분해 기록했다. 실제 물리 시험·알람 변경은 수행하지 않았다.

제조사의 [SPOT Modbus Controls User Guide 809557 Issue 10](https://www.ametek-land.com/-/media/ameteklandinstruments/documentation/products/fixedspotnoncontactthermometers/spot/ametek_land_809557_spot_modbus_controls_user_guide_issue_10_enpdf.pdf?la=en&revision=1bb46776-24d3-450f-9c84-f3db645b2171)
색인 본문 PDF8쪽도 Low Signal 알람의 적용 범위를 ratio 모드로 설명한다.
이는 별도 SPOT 프로토콜 자료이며 현재 SPOT+ AL/펌웨어40.38/App1의 지원 여부나
내부 비교 정밀도를 확정하는 근거는 아니다. PDF10쪽의 신호 register249 설명에도
내부 알람 비교값과의 동일성·반올림 계약은 확인되지 않았다.
[출처·확인 범위](C:/Users/user/Desktop/SmartFactory/PDCA_SOURCE_SCOPE_20261013_5bbfe655/manufacturer-addendum.json)를
보존하며 실제 장비에 Modbus 요청을 보내지 않았다.

다음 단계는 App1/40.38에서의 알람 적용 및 동일값 확인 방법에 대한 제조사 근거 또는
해당 조건을 입증할 격리 시험 설계다. 배선 답변만으로 물리 경계·attestation을 PASS로 바꾸지 않는다.

## 프로토콜 범위 보완과 제조사 문의 발송

[프로토콜 대조 기록](C:/Users/user/Desktop/SmartFactory/PDCA_PROTOCOL_CONTRACT_20261013_6d6df2e6/protocol-review.json)에
REST 원본 PDF의 SHA256, 확인한 쪽과 렌더링, 별표의 적용 범위를 보존했다.
이전 SPOT AL/AL LT 안내서 811299 Issue7(2021-08-26)의 4.6절도 Low Signal을 설명하지만,
세대가 다른 이 자료를 SPOT+ AL/40.38 동작의 검증으로 사용하지 않는다.

사용자는 처음 “본인이 구매처에 전달”이라고 답한 뒤 “아니다. 너가 전달해라.”라고
명시적으로 변경했다. 이에 따라 준비된 [영문 문의](C:/Users/user/Desktop/SmartFactory/PDCA_PROTOCOL_CONTRACT_20261013_6d6df2e6/manufacturer-inquiry.txt)를
2026-10-13 19:06:27 KST에 제조사 공식 주소 `land.enquiry@ametek.com`으로 발송했다.
App1 알람 지원, `<`/`<=`와 내부 정밀도, 승인된 미만/동일/초과 시험 방법을 문의했다.
본문에는 모델·펌웨어·설정과 공개 문서만 포함하고 첨부파일은 없다.
[발송 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_PROTOCOL_CONTRACT_20261013_6d6df2e6/email-send-receipt.json)에
Gmail SENT 상태와 수신 주소·제목·본문의 발송 후 일치를 기록했다. 수신자의 열람이나
답변을 확인했다는 뜻은 아니다. 기존 프로토콜 기록의 발송 대기 표시는 당시 기록으로 보존한다.

후속 답변에서는 모델/펌웨어/모드의 적용 범위, 비교식과 정밀도, equality 시험 가능 여부를
각각 확인한다. 답변만으로 실제 경계 시험이나 최종 후보 attestation을 완료 처리하지 않는다.
현재 물리 시험 `NOT_TESTED`, App1/40.38 계약 미확정, 정식 출시 **HOLD**를 유지한다.

## 2026-10-14 시험 장비 부재와 현장 검증 순서 변경안

사용자는 전용 시험 장비의 뜻을 설명받은 뒤 "그런 시험 장비는 없다."라고 답했다.
현장 전용 광원/제조사 시험 장비는 사용자 진술 기준 없음으로 기록한다.
제조사 문의에는 이미 승인된 시험 방법과 필요 장비 질문이 포함돼 있다.
10월14일08:30 KST 재조회에서 문의 thread에는 발신1건만 있었다.
이후 물리 시험의 방법·수행 가능성을 제조사 근거와 함께 확정해야 한다.

현재 소프트웨어는 운영자 설정 확인과 comparator 검증을 별도로 표현할 수 있다
(`backend/FacilityData/spot_config_provenance.py`). comparator=false이면 수치 기반
Low Signal 판단은 미확인으로 남고 실제 alarmstatus bit4는 별도 기록된다
(`backend/FacilityData/spot_low_signal.py`). 그러나 현재 attestation 도우미·one-command QA·
현장 실행기는 comparator=true를 요구한다. 현재 도구로 이 조건을 건너뛴 실행은 하지 않았다.

**아래는 확인용 변경안이며, 아직 승인·구현·서버 적용하지 않았다.**

1. 승인 프로파일의 Low Signal 비활성을 유지한 상태에서 설치·일반 수집·성능·새 데이터
   검증에 먼저 착수하도록 적용 전 순서를 변경한다. 장비 알람을 켜는 시험은 보류한다.
2. 근거 없는 configured comparator=true를 새 설정 사본에서 false로 바로잡고,
   사용자에게 승인받은 관찰 프로파일의 최종 후보 fingerprint만 실제로 확인한다.
   기존 설정/metadata/승인 기록은 원문 그대로 백업·보존한다.
3. 도우미에 이 목적의 명시적 제한 실행 경로를 구현·검증한다. 기본 정식 QA 조건은 유지하고,
   물리 경계는 NOT_TESTED, comparator는 false, 전체 QA/출시는 HOLD로 출력한다.
   알람 활성화·프로파일/세대 변경·fingerprint 불일치 시 제한 실행도 실패한다.
4. 정확한 후보4cc/882와 복귀 기준541d/08C를 사용해 백업·정상 종료·설치·정상 시작3회,
   초기15분/120분 계측·정상 종료·새 CSV/이미지 전수 검증을 수행한다.
   단계별 수집/데이터 판정과 미완료 장비 조건을 구분한다. 자동 복구·승격은 하지 않는다.
5. R1–R6의 최종 완료 조건과 과거 finding 처리는 유지한다. 제조사 근거·물리 시험을 포함한
   미완료 조건을 실제로 해결한 뒤 정식 QA·승격·다음 롤백 기준 갱신을 판단한다.

이 선택은 기존 출시 계획의 적용 전 장비 조건과 현장 시험 순서를 바꾸므로 변경 범위에
대한 사용자 확인이 필요하다. "다음 단계 승인"과 시험 장비 부재 진술을 이 변경안의
명시적 선택이나 물리 검증 완료로 간주하지 않는다.

## 2026-10-14 제한된 현장 검증 순서 승인과 도우미 검사

위 변경안에 사용자가 "예, 다른 현장 검증부터 진행"이라고 명시적으로 답했다.
앞 절의 미승인 상태는 당시 이력이며 현재는 이 제한된 순서 변경이 승인됐다.
승인 원문은 `C:/Users/user/Desktop/SmartFactory/PDCA_LIMITED_FIELD_20261014_0dd2ced0/approval.json`,
SHA256은 `6517011d8f51eb4cff560bf83c8dcbb471bd4add99f21cdac59387d3d1c93685`다.

기본 정식 QA 조건을 유지하고 별도 고정 설정 기준에 승인 해시가 결합된 경우에만
`DISABLED_LOW_SIGNAL_FIELD_TRIAL`을 허용했다. 알람과 configured/effective comparator는
모두 false여야 한다. USER_SELF의 실제 후보 fingerprint 확인, 승인 프로파일, 같은 실행
세대와 종료 자료 결합은 계속 검사한다. runtime JSON의 임의 필드로 경로를 선택할 수 없다.
관찰·종료 데이터 결과·최종 실행 영수증에 물리 시험 NOT_TESTED와 정식 QA HOLD를 전달한다.

| 최종 로컬 검사 | 결과 |
| --- | --- |
| 설정 기준 결합 | 10개, exit 0 |
| Windows PowerShell 5.1 설정 확인 도우미 | 8개, exit 0 |
| 종료 사본 CSV·이미지 검사 | 16개, exit 0 |
| 실행 요청·결과 영수증 | 10개, exit 0 |
| 관찰·실행 세대·시간 초과 처리 | 27개, exit 0 |
| 정상 종료 자료 결합 | 10개, exit 0 |

PowerShell 첫 검사에서 Get-FileHash 모듈 탐색 오류, 다음 검사에서 JSON 숫자의 Decimal
형식을 누락한 오류를 발견해 수정했다. 실패 로그와 최종 81개 검사 로그는 위 증거 폴더에
보존했다. 이 결과는 도우미/격리 사본 검사이며 실제 현장 성능이나 물리 시험 PASS가 아니다.
제품 소스와 후보4cc/882 설치본은 변경하지 않았다.

다음 실행 순서: 현재 운영 세대의 정상 종료와 최신 사본 검산 → 같은 후보 설치 → 실제
설정 확인·정상 시작3회 → 15분/120분 계측 → 정상 종료 자료/CSV/이미지 검사.
기존 추가 스트림 보존 사본 도우미의 동일 바이트를 재사용하며 실행 시 정확한 용량과
현재 세대를 검사한다. 이 기록 시점에 새 서버 사본·설치·설정 변경·계측은 미실행이다.
물리 시험과 R1–R6의 미완료 조건, 정식 출시 HOLD 및 승격 금지는 유지한다.

## 2026-10-14 최신 백업 진행과 설치 도우미 검증

09:05 KST에 기존 동일 바이트 스트림 보존 도우미가 `READY_FOR_NORMAL_APP_EXIT`를
출력했다. 실제 앱 닫기 버튼을 누른 뒤 09:07:56 KST에 도우미가 main/backend와
8000 포트의 부재를 세 차례 확인했다. 새 결과 폴더는 서버
`C:/Users/user/Desktop/SmartFactory/Q3d9da3`이다. 이전 main10788/backend9028,
logger `e9a785c0-46a2-45d2-bf7a-4187cce08771`에 결합된 사전 기록 7개를 회수했다.
이 기록 시점에는 복사 진행 중이며 최종 사본 해시와 정상 종료 로그 검토는 미완료다.
앱 종료 기간은 수집 중단 구간으로 기록한다. 최근 화면의 작업 값은 60580/1이며
과거 60332/6으로 되돌리지 않았다.

`install-field-candidate.ps1`은 검토 완료한 최신 백업/동일 세대 종료 영수증의 외부 해시를
요구한다. 고정 후보4cc/882와 복귀본541d/08C, 설치 payload1814파일을 대조하고
앱/포트 부재에서 `/S /currentuser`를 한 번 실행해 실제 종료 코드를 보존한다.
설치 후 기존 백업 엔진의 원본·사본 본문/추가 스트림 재검산을 통과해야 승인된
`low_signal_comparator_verified=false` 한 값만 정정한다. 원본 설정과 변경 후 바이트,
추가 스트림 보존, 결과 파일별 해시를 남긴다. 앱 시작·운영자 attestation·자동 복구·
승격은 수행하지 않으며 최종 상태도 runtime 확인 대기/정식 QA HOLD다.

최종 native Windows PowerShell 5.1 단위 검사 28개(`install-tests-r4`)와 격리 모의
설치 전체 흐름(`install-integration-r8`)은 exit0다. 실제 child exit0/17, 시간 초과 시
강제 종료 없음, 원본/사본 및 설정의 추가 스트림 보존, 단일 설정값 변경과 결과 파일
해시를 확인했다. 전체 흐름 시험은 작은 합성 payload/가짜 installer와 모의
registry/프로세스 상태를 사용했으며, 운영 서버 관리자 ACL·실제 서버 설치 검증은 아니다.
권한의 전체 SDDL 문자열 비교, PowerShell null 문자열과 Byte 배열 처리 오류를
발견·수정했고 실패 자료를 보존했다. 검사 당시 설치 도우미 SHA256은
`1007cac441476a9540d1d13b24dd52193a4d329e755e1f9f308dffef9a6a618f`다.
운영 서버 식별자 차단도 실제 exit1을 확인했다. 서버용 실행 요청은 최신 백업과
종료 로그 검토 후 고정할 예정이며, 이 기록으로 서버 설치 완료를 주장하지 않는다.

## 2026-10-14 같은 운영 세대 종료·CSV 검토와 백업 완료 대기

`Q3d9da3` 복사 중에 탐색기로 종료 자료를 회수했다. 회수 위치는
`Z:/SmartFactory/20261014/return/FIELD_OFF_0dd2ced0_shutdown`이며 개발 증거는
`C:/Users/user/Desktop/SmartFactory/PDCA_LIMITED_FIELD_20261014_0dd2ced0`에 보존했다.
공유 사본과 개발 사본의 바이트·해시는 일치한다. 서버 최종 manifest 결합은 대기 중이다.

| 확인한 자료 | 확인 결과와 범위 |
| --- | --- |
| Electron 종료 로그 | main10788/backend9028의 종료 요청 09:07:34.703 KST, backend 실제 exit0 09:07:49.407, forced=false |
| 같은 세대 begin/final 종료 영수증 | 세대·sidecar SHA 일치, 종료 단계 10개 완료, 이미지 enqueued=written=94,022, queue/inflight/unfinished/new failures during drain=0 |
| 당일 닫힌 CSV·metadata | 142,273행, 순번323776–466048 연속, 마지막09:07:34.930912, finalized=true/reason=shutdown; 전체 의미 검증은 아님 |
| system/status 로그 | 동일 세대 정상 종료 단계와 Offline 전환 일치; 과거 통신 경고 원문 보존 |
| 승인 설정 변경 미리보기 | 실제 config SHA6841…을 입력으로 comparator 검증 값만 true→false; 다른 바이트 불변, 서버 설정 미변경 |

종료 영수증의 `historical_dropped_count=173`, `integrity_unresolved=true`는 미해결이다.
설치된541d 소스는 크기 초과와 queue.Full을 같은 dropped_count로 기록하며 원인별
카운터가 없다. 이 수치를 실제 저장 파일 173개 손실이나 확인된 단일 원인으로 해석하지 않는다.
이번 종료 중 새 실패 0과 과거 drop의 원인·영향 확인은 별개다.

검토 스크립트 `review-preclose.py`, `review-shutdown-receipts.py`, `review-closed-csv.py`,
`preview-approved-config.ps1`, `review-system-logs.py`의 최종 실행은 각각 exit0다.
system.log 첫 검토는 JSON과 일반 텍스트가 섞인 형식을 가정하지 못해 exit1이었고,
두 형식을 명시적으로 읽는 재실행 `server-system-logs-r2`에서 25,168개 기록을 검토했다.
과거 로그를 포함한 경고544개는 발생 횟수가 아니라 기록 개수이며 별도 JSONL로 보존했다.

새 사전 조사 용량14,087,444,216B와 이전 검산 백업55,562,005,735B의 차이는 아직
설명되지 않았다. 이전 원문을 보존하고, 새 최종 manifest의 파일별 추가·변경·부재와
본문/추가 스트림 용량을 대조하도록 도구를 준비했다. manifest 구조·부모 결합·해시·
수량/용량 불일치와 이전 백업 오사용 차단 등 로컬11개 검사는 exit0였다.
이 검사는 현재 서버 사본 검산 성공을 뜻하지 않는다.

다음 순서는 최종 콘솔 해시 회수 → 새 manifest와 위 원본 자료 결합 → 이전 manifest와
용량 차이 검토 → 고정 설치 요청의 서버 최종 전달이다. 이 기록 시점에는 앱이 종료된
유지보수 구간이며 백업 복사 중이다. 후보 설치·설정 변경·현장 계측은 아직 미실행이며,
물리 시험 NOT_TESTED, 정식 출시 HOLD, 승격 금지를 유지한다.

### 백업 대기 중 추가 설치 준비와 기존 응답 지연 근거

개발 증거 폴더의 `INSTALL_OFF_20261014_0dd2ced0`에 설치 도우미·승인 원문·프로파일·
후보 payload 기준·이전 backend manifest·같은 스트림 엔진의 6파일/825,532B를 준비했다.
이전541d/08C installer 추출 기록과 본문에서 backend manifest SHA256
`a928cdaf7eb134acf50a02099b9c6768d076ab965fb529ef3f961f267b7c1e45`를 대조했다.
실제 실행 시 서버 설치 폴더의 manifest가 이 값과 맞아야 한다. 이 로컬 준비가 현재 서버
설치 파일의 해시 확인을 대신하지 않는다. 새 백업 해시가 없어 최종 요청·전달은 미실행이다.

`install-launcher.py`는 해시가 고정된 입력을 잠근 child PowerShell에서만 도우미를 실행하고,
사용자 콘솔에는 실제 child `LAUNCH_EXIT`를 남긴다. native PS5.1 검사7개는 exit0였다.
도우미/요청 잠금, 잘못된 외부 해시·변조·추가 파일 차단, child 실제 exit0/17과 parent
콘솔 유지, 실제 도우미의 개발 PC 차단을 확인했다. 생산 설치 실행은 포함하지 않는다.

회수한 system.log에서 현재 세대의 느린 health 두 기록도 확인했다.
00:50:41 KST 전체678.7ms 중 frontend 확인671.2ms, 06:50:21 전체1,865.8ms 중 runtime
정보 확인1,860.5ms였다. 원문 줄·해시와 같은 세대 결합은
`existing-generation-health-delays.json`에 있다. 측정한 세 함수는541d와 후보4cc에서 같았다.
이 구간 시간은 OS 스케줄링·파일 시스템 대기 등을 포함할 수 있어 근본 원인이나 과거
223.4887ms/timeout 사건의 인과를 확정하지 않는다. 실제 후보의 첫 요청·반복 health와
같은 시각의 디스크/프로세스 계측을 비교해야 하며, 이 근거로 검사·기준을 완화하지 않았다.

### 2026-10-14 11:22 이후 복사 완료와 잠정 파일 목록 비교

동일 도우미의 복사 단계는 325,089파일/14,095,162,877B에서 끝났고,
`source-and-restored-verification` 단계가 계속 진행 중이다. 이 명칭은 이번 실행에서
원본과 백업 사본을 재검산하는 단계이며 별도 복원 실행을 뜻하지 않는다. 최종 콘솔의
RESULT_PATH·MANIFEST_SHA256·RESULT_SHA256은 아직 받지 않았다. 앱은 정상 종료된
유지보수 상태이며 후보 설치를 시작하지 않았다.

이미 닫힌 `files.tsv`를 서버 탐색기로
`Z:/SmartFactory/20261014/return/BACKUP_Q3d9da3_metadata`에 회수했다. 공유/개발 사본은
156,501,349B와 SHA256 `ab637280383d38777649310f00cd586a80e7f74e0cf159d9535a1d170287f393`이
일치한다. 이 해시는 회수 바이트의 식별값이며 아직 서버 완료 콘솔에 결합되지 않았다.
목록 자체의 수량은 파일325,089/폴더246/추가 스트림680, 용량14,095,162,877B다.

이전 콘솔 해시에 결합된 `Qa0596a` 목록과의 **잠정** 비교는 다음과 같다.

| 새 목록에서 보이지 않는 이전 항목 | 파일 수 | 본문·추가 스트림 bytes |
| --- | ---: | ---: |
| logs/data CSV | 199 | 4,399,785,535 |
| logs/test_data CSV | 315 | 37,694,374,986 |
| logs/test_data JSON | 260 | 6,600,642 |
| spot_images의 10월5–6일 이미지 | 82,814 | 791,148,928 |
| 기타 파일 | 40 | 324,032,215 |

부재 파일83,628개와 폴더2개, 추가94,045항목, 변경37항목, 동일231,253항목으로
집계됐다. 부재 -43,215,942,306B, 추가 +1,568,743,113B, 변경 +180,356,335B로
이전55,562,005,735B와 새14,095,162,877B의 차이가 산술적으로 맞는다.
부재 파일의 비어 있지 않은 기본 본문과 같은 크기·해시를 가진 다른 경로는 이번 새 목록
안에서 찾지 못했다. 이 결과는 서버 밖 이동·보관 여부나 삭제 주체·원인을 증명하지 않는다.

증거는 개발 폴더의 `provisional-manifest-review-r1`에 있다. 두 분석 스크립트의 최종
실행은 exit0였고 파일 수·용량을 다시 집계했다. 처음 상세 날짜 집계가 이미지 식별자의
숫자를 날짜로 읽는 문제를 발견해, 실제 날짜 폴더와 달력 검사로 수정한
`provisional-difference-detail-r2.json`을 사용한다. 최초 출력도 보존한다.

기존541d의 이미지 보존기간 코드는 지정된 이미지 경로에만 적용된다. 이 코드나 위 목록만으로
CSV514개의 부재 원인을 확정하지 않는다. 최종 사본 검산·콘솔 해시 결합·정상 종료 원문
결합을 마친 뒤 설치 요청을 확정한다. 이전 백업을 보존하고 물리 시험 NOT_TESTED,
정식 출시 HOLD 및 승격 금지를 유지한다.

### 검산 대기 중 추가 이미지 수량 대조와 설치 입력 준비

`provisional-image-delta-review.json`의 로컬 분석은 exit0였다. 새 목록에 추가된
이미지는 JPG94,022개/916,112,088B로 같은 종료 영수증의 enqueued/written94,022와
수량이 같다. 파일명 날짜 폴더·SHA256 앞12자리·중복 이름·빈 파일·종료 세대의 시간
구간 검사를 모두 통과했다. 파일명 시각 범위는 UTC2026-10-12 18:27:46.789074부터
10월14일00:07:33.983148까지다. 이 시간 구간 일치만으로 이미지의 실행 세대가
증명되는 것은 아니다. 이미지 fact 대장과의 세대 결합, 본문 디코딩 및 최종 서버 사본
검산은 이번 분석 범위 밖이며 과거 drop173의 원인·영향은 계속 미해결이다.

개발 증거 폴더의 `complete-install-bundle.py`는 실제 최종 백업 해시, 정상 종료 검토,
최종 manifest 비교 결과가 모두 있어야 설치 요청·설명서·묶음 manifest와 명령문을
완성한다. 잠정 비교 결과는 입력으로 수용하지 않는다. 문법 검사와 `--help`는 exit0였으며
실제 최종 입력이 없어 묶음 완성 실행은 아직 하지 않았다. 기존 6개 준비 파일과 후보·
복귀 설치본은 유지하고, 서버 검산/설치 도우미를 수정하거나 실행 중 작업을 다시 시작하지 않았다.

### 2026-10-14 실제 입력 용량과 v2 전용 기록의 도우미 호환 수정

잠정 목록의 `spot_image_fact.csv`는 2,171,614,099B로 기존 도우미의 2GiB 한도를
넘는다. 2GiB+1B의 새 합성 파일로 기존 `csv-input-fact-contract` 실패를 재현했다.
`field_csv_inputs.py`는 이미지 fact 역할에만 4GiB 한도를 적용한다. 다른 입력의
2GiB 한도와 1MiB 단위 스트리밍 해시, Windows 읽기 잠금, 종료 시 재검산은 유지한다.
이 수정은 큰 CSV 내용의 의미 검증을 통과시킨 것이 아니다.

회수한 실제 config의 `csv_v1_enabled=false`와 닫힌 metadata의
`schema_metadata.v1_csv_enabled=false`도 일치한다. v1을 항상 요구하던 도우미는
이 운영 형태를 처리할 수 없었다. 이제 해시로 결합한 metadata에 정확한 boolean false가
있고 같은 날짜의 v1 파일도 없을 때만 `--v1`을 생략한다. 예를 들어 v2 전용 요청에서는
`roles`와 `expected_files`에서 v1만 빼고, v2·metadata·observation·image·image_final을
그대로 제공한다. `v1_comparison_requested=false`와 생략 근거를 결과에 남기며,
구형 CSV 비교를 PASS로 기록하지 않는다. flag 누락·true·0·문자열 false 또는 결합되지
않은 v1 파일이 있으면 거부한다. 운영 설정을 바꾸거나 v1 데이터를 만들어 채우지 않는다.

증거 폴더는 `C:/Users/user/Desktop/SmartFactory/PDCA_FIELD_CAPACITY_20261014_0dd2ced0`다.
최종 수정 상태에서 `unittest test_field_csv_inputs -v` 22개와
`unittest test_field_closed_data_qa test_field_runner -v` 27개가 모두 실제 exit0였다.
전자는 2GiB+1B 파일의 해시·쓰기 차단·재검산과 기존 고정 CSV 실행 파일의 v2 전용
검사를 포함한다. 후자는 합성 승인 자료로 v2 전용 전체 흐름을 실행하고 물리 NOT_TESTED,
정식 HOLD를 유지했는지 확인한다. 제품·frontend·backend 변경이 없어 전체 health는
반복하지 않았다. 새 도우미 빌드·휴대 실행 검증·서버 전달은 별도로 완료해야 한다.
이미 전달한 구도우미는 보존하며 이 큰 입력의 검사에 사용하지 않는다.

고정 helper commit `f274b5347eeaaae50d397a07466604bb9826da7c`의 깨끗한 소스 30파일에서
새 도우미를 빌드했다(exit0). 실행 파일은 16,059,253B,
SHA256 `2c62d1d5ad3566d80a1d18b22a55da7d61b3b17f8afd97781394988d16766c68`이다.
내장 CSV 입력 모듈의 코드와 commit 소스의 컴파일 결과도 일치한다. native PS5.1을 포함한
휴대 실행 8개는 모두 예상 exit를 확인했고 전체 검증 driver는 exit0였다. 합성 정상·OFF·
v2 전용 흐름은 exit0, 실제 보관 자료의 미승인 attestation·중복 JSON·잘못된 외부 해시·
비관리자 생산 launcher는 예상대로 exit1이었다. 개발 fixture의 ACL 변경은 새 시험 폴더에만
적용했으며 생산 관리자 ACL 적용 또는 서버 QA를 시험한 것으로 보고하지 않는다.

새 전달 폴더 `FIELD_OFF_20261014_0dd2ced0_R2`는 13파일/42,161,139B다.
전달 manifest SHA256은 `6fd3a6459b42f8b08527a3070be9b4d6c56eb11112eae63ad69b134007db372e`다.
개발 폴더와 `Z:/SmartFactory/20261014/send` 사본의 전체 파일 해시가 일치한다.
Chrome 원격 데스크톱으로 서버
`C:/Users/user/Desktop/SmartFactory/FIELD_OFF_20261014_0dd2ced0_R2`까지 복사하고,
절대경로·RUN128의 8파일·reference의 2파일과 최상위 자료를 화면으로 확인했다.
`server-delivery.json`과 `server-r2-*.png`에 기록했다. 서버 로컬 해시 검산·도우미 실행·
후보 설치는 아직 하지 않았다. 기존 전달 묶음과 제품 후보4cc/installer882 바이트는 유지한다.

### 회수 대장과 추가 이미지 94,022개의 실제 연결

서버 탐색기로 이미지 fact·최종 manifest·관측 fact를 새 공유 회수 폴더
`Z:/SmartFactory/20261014/return/FIELD_OFF_0dd2ced0_dataqa`에 복사했다.
개발 사본의 세 기본 본문은 잠정 백업 목록과 크기·해시가 일치한다. 최종 image manifest는
461B, SHA256 `755a30feaa0e2d86064703d09f9215e70a4a7e50a698e53e2f603999127d080c`다.
image fact는 2,171,614,099B/SHA256 `7b5d26e7e1d85fc884a1398686a3f6f95fdfa4da8761aba6c00afb895cc35d01`,
관측 fact는 365,096,518B/SHA256 `3cf5c2eb694e8e6ece38a644c6b2f1f4452f2b5320595bdf2b73069dd59cd77c`다.
첫 회수 분석은 manifest 상대경로의 선행 역슬래시를 빠뜨려 복사 전에 exit1로 중단됐다.
실제 경로를 정확히 맞추도록 정정한 회수 분석은 exit0였으며 최초 실패 기록도 보존한다.

`image-ledger-review-r1/review.json`은 이미지 대장 4,237,531행 전체를 읽어 최종 manifest의
row_count와 맞췄다(exit0). 새 목록의 추가 이미지 94,022개는 각각 대장 한 행과 연결되며
path·크기·SHA256·capture ID·captured 상태가 일치한다. 전부 같은 SPOT service
`efca4313-f987-4bb2-bcc8-4de40712396c`에 속하고, 관측 대장 314,216행의 실제 key와도
94,022개 모두 연결됐다. 중복 추가 경로·누락 대장 행·없는 관측 key·service 불일치는 0이다.
이 service의 관측 행은 106,655개, 연결 이미지의 link_status 기록은 모두 fresh다.

이는 파일명 시각만으로 세대를 추정하던 범위에서 실제 대장 key 연결로 진행한 결과다.
추가 이미지 본문 디코딩, 전체 보존 이력의 무결성, 과거 drop173의 원인·영향을 증명하지는
않는다. 서버 전체 사본 검산과 최종 콘솔 해시가 아직 없어 잠정 증거로 유지하며
full_data NOT_EVALUATED, physical NOT_TESTED, release HOLD를 바꾸지 않았다.

같은 잠정 목록에 결합한 닫힌 v2 CSV·metadata·관측 fact·이미지 fact·최종 manifest의
새 로컬 사본으로 `run-recovered-csv.py`도 시작했다. 서버 앱이나 설치본을 실행하지 않고
고정 CSV 검증기만 별도 Windows Job에서 실행하며 1,800초 제한과 입력 잠금을 적용한다.
현재 검사는 실행 중이고 실제 consumer exit는 미확정이다. 자료 위치는 위 증거 폴더의
`recovered-csv-r1`, 콘솔 기록은 `recovered-csv-r1.log`다. 새 용량 한도로 큰 입력을
수용했다는 사실은 이 자료의 의미 검증 통과를 뜻하지 않는다.

### 최종 설치 묶음 생성기의 격리 입력 검사

같은 개발 증거 폴더의 `test-install-bundle-builder.py`로 실제 생성기를 격리된
`DEV_ONLY_install_builder_r2`에서 검사했다. 13개 검사는 실제 exit0였고
`install-builder-tests-r2.log`와 `DEV_ONLY_install_builder_r2/summary.json`에 보존했다.
미완료 백업, 다른 백업 경로, false/숫자형 증명값, 오래된 결과, 잘못된 해시 결합,
실패한 정상 종료 검토, 다른 실행 세대, 잠정 비교, 운영 승격 주장, 변조한 정적 파일,
잘못된 외부 해시의 12개 입력은 출력 변경 전에 거부했다. 합성 정상 입력에서는
10파일 묶음의 전체 해시를 재대조하고 같은 출력의 재사용도 거부하는지 확인했다.

최초 `DEV_ONLY_install_builder_r1`의 정상 입력은 허용된 Desktop/SmartFactory 밖의
시험 경로여서 launcher의 경로 검사에 걸렸다(exit1). 시험 경로만 허용 부모 아래의
`DEV_ONLY_NOT_FOR_SERVER_...`로 고친 두 번째 검사가 위 결과다. 최초 실패와 부분
시험 출력도 보존했다. 실제 6파일 준비 묶음과 생성기·launcher 원문은 변경하지 않았다.
합성 요청은 서버로 전달하거나 실행하지 않았으며, 실제 최종 서버 결과를 결합한
설치 요청 생성·설치는 계속 미실행이다.

이전 전체 CSV 소비자 검사의 실제 소요시간은 2,404.04초였고 실제 exit1이었다
(`PDCA_STREAM_COPY_20261012_5a7ed041/validator-memory-validation/completion-review.json`).
당시 실패는 운영자 확인 프로파일 조건이며 현재 자료의 결과로 재사용하지 않는다.
이 기록은 현재 1,800초 예산이 부족할 수 있다는 근거다. 실행 중 검사를 중복 시작하거나
완료로 간주하지 않고 실제 종료 상태를 확인한다.

13:02 KST에 첫 로컬 CSV 검사는 `command-deadline`으로 끝났다. driver exit0는
결과 기록 성공이며 소비자 PASS가 아니다. 소비자 exit는 없고, 소유한 Windows Job의
작업들을 제한 시간에 종료한 뒤 active_processes=0, worker_still_alive=false를 확인했다.
stdout/stderr는 모두 0B였고, 잠근 입력의 종료 재검산만 PASS다. 원본 기록
`recovered-csv-r1/review.json`의 SHA256은
`ae79ee1d0628b0632ef7a2ef010bcb40c27dc62e312b09465ccc926eca84e40b`다.

같은 입력 5파일과 같은 고정 검증기로 `run-recovered-csv-r2.py`를 실행했다.
앞선 실패·Job 종료·입력 해시를 확인하고 시간 예산만 기존 허용 범위인 3,600초로 늘렸다.
입력 사본은 재사용하되 새 경로 전용 metadata와 결과는 `recovered-csv-r2`에 기록한다.
13:03 KST 실제 소비자 실행을 확인했으며 결과는 아직 미확정이다. 서버 도우미·앱·
설치본은 재실행하지 않았다. 검증 조건과 정식 출시 HOLD는 그대로 유지한다.

### 2026-10-14 13:16 KST 백업 완료와 최종 설치 묶음 서버 전달

동일 서버 백업 `C:/Users/user/Desktop/SmartFactory/Q3d9da3`가 13:16:23 KST에
`SELECTED_COLD_COPY_DEFAULT_AND_NAMED_DATA_STREAMS_VERIFIED`로 완료됐다.
파일325,089/폴더246/추가 스트림680, 총14,095,162,877B이며 원본·사본의 본문/추가
스트림 해시와 구성, 원본 metadata 유지, 앱·backend·port 부재 확인이 모두 true다.
콘솔 결과를 서버 탐색기로 공유 회수 폴더에 복사한 뒤 개발 사본과 대조했다(exit0).

- `result.json`: 2,147B, SHA256
  `c4ce41277032748f6c78160e42ed093f11305c0ceb7b88ae0089146efe966afb`
- `files.tsv`: 156,501,349B, SHA256
  `ab637280383d38777649310f00cd586a80e7f74e0cf159d9535a1d170287f393`
- 보존 위치: `PDCA_LIMITED_FIELD_20261014_0dd2ced0/server-final-backup`
- 완료 화면: `PDCA_FIELD_CAPACITY_20261014_0dd2ced0/server-backup-terminal.png`

첫 해시 대조는 콘솔의 `6C`를 `C6`로 옮겨 적어 exit1로 중단됐고, 화면을 잘라 확대해
확인한 정확한 콘솔 값으로 재대조했다. 첫 정상 종료 결합 도구도 종료 영수증 경로에
불필요한 `logs`를 넣어 exit1이었다. 최종 고정 manifest에서 18개 원본이 모두
운영 자료 루트의 `shutdown_evidence` 하위에 있음을 확인해, 별도 `bind-final-backup-review-r2.py`의
경로 상수 한 곳만 정정했다. 원 도구·실패 로그·원본 증거는 보존했다.

수정한 결합 검토는 실제 exit0다. 같은 실행 세대의 정상 종료 기록·종료 영수증18개·
닫힌 CSV와 metadata·config·system/status 로그 등 원본24개가 최종 manifest와 맞았다.
`final-backup-close-review.json` SHA256은
`d776d9cd72252012addb4bfca439729bcfea19a6f9a973bc30cac367c1a2f0c0`다.
이전 백업과 최종 목록의 비교도 exit0이며 기존 잠정 수량/용량 차이와 같았다.
`backup-manifest-comparison/comparison.json` SHA256은
`7ab94baa4d76c1909dbc337fcad0265a00a4fc0be6e981c6a5f91c15e3b93571`다.
과거 CSV514개의 부재 원인과 drop173의 원인·영향은 여전히 미확정이다. 이전 백업을
보존하며 이 비교를 복구 시험이나 전체 데이터 의미 검증 PASS로 해석하지 않는다.

최종 입력으로 `complete-install-bundle.py`를 실행해 설치 묶음을 완성했다(exit0).
서버 최종 위치는 `C:/Users/user/Desktop/SmartFactory/INSTALL_OFF_20261014_0dd2ced0`다.
묶음10파일의 manifest SHA256은
`c9143a129c78ec1aa1c0febaf8daabb4671aa8fa2020af0737a0b70570f6e27a`이며,
별도 `PINNED_FIELD_INSTALL_COMMAND_0dd2ced0.txt`는 8,398B/SHA256
`10c898ea5396e08b43051274070eb25e8c275b7af62f4afe1894e6a63d4d4b7f`다.
합계11파일/848,024B를 `Z:/SmartFactory/20261014/send/INSTALL_OFF_20261014_0dd2ced0_delivery`에
복사하고 개발/공유 전체 해시를 재대조했다(exit0).

Chrome 원격 데스크톱으로 서버 SmartFactory까지 복사하고 최종 절대경로·묶음10파일을
확인했다. 같은 부모의 명령문 텍스트 파일을 메모장에 열어 `$installBundle=`의 실제
서버 경로와 manifest pin을 확인했다. `server-install-delivery.json`,
`server-install-bundle-path.png`, `server-install-command-ready.png`에 범위를 기록했다.
서버 로컬 파일 해시는 실행 launcher가 확인할 대상이며 화면 확인만으로 검산을 주장하지
않는다. 사용자에게 관리자 PowerShell의 실행만 요청했고 이 기록 시점 설치는 미실행이다.

운영 서버 명령 실행은 Computer Use 스킬이 참조하는 guidance의
“Do not run Windows terminal commands via UI automation directly or indirectly.”
제한 때문에 사용자 조작이 필요하다. 승인된 설치 범위는 다시 묻지 않았다. 다음 순서는
사용자 실행 → 실제 설치 결과·파일·설정 확인 → 승인된 일반 수집/15분/120분 검증이다.
Low Signal OFF, physical NOT_TESTED, formal release HOLD, promotion false를 유지한다.

추가로 회수한 5개 CSV 입력도 같은 최종 manifest에 결합했다(exit0).
`PDCA_FIELD_CAPACITY_20261014_0dd2ced0/final-recovered-input-binding.json` SHA256은
`aeaaa57a5fe663695ef81fc55e1b839a6924f71211f90a7f294ac5407be097d2`다. 이전 잠정 목록과
최종 목록의 바이트가 같아 기존 이미지94,022개 대장 연결 근거를 유지할 수 있다.
CSV 소비자 재검사는 13:29 KST에도 실제 프로세스가 실행 중이며 결과는 미확정이다.
과거 입력 영수증의 잠정 상태를 소급 수정하지 않고 최종 결합 근거를 별도로 남겼다.

### 2026-10-14 설치 전 DLL 로드 중단과 R2 수정 전달

사용자가 실행 완료를 알린 첫 설치 명령은 `LAUNCH_EXIT=1`이었다. 서버 결과
`C:/Users/user/Desktop/SmartFactory/Idb221abf/hold.json`은
`backup-and-cold-preconditions` 단계의 DLL 로드 오류 `0x80131515`를 기록했다.
`installer_started=false`, `installer_exit=null`, `configuration_changed=false`,
`force_calls=0`이며, 같은 결과의 runtime-before는 앱/백엔드 프로세스와 포트 목록이 비어 있다.
설치 프로그램을 시작하기 전 중단됐으므로 후보 설치나 설정 변경 완료로 처리하지 않는다.

서버 탐색기로 3개 결과 파일을 공유 드라이브에 회수하고 개발 사본까지 해시를 검증했다.
콘솔 HOLD SHA256은 `855bb31fc5809efc0197eb1d6414df636d69aa1fa504aaf51dc5a7bd150893f2`다.
첫 전사는 `6414df`를 `6414cf`로 읽어 대조에서 거부됐고, 콘솔을 다시 확인한 후
정확한 핀으로 hold와 내부 증거 2개를 대조했다(exit0). 공유 부모 이름의 `Ib221abf`와
실제 결과 자식 `Idb221abf`도 구분했다. 회수 원문은 개발 증거 폴더의
`server-install-hold-Idb221abf`, 검토 기록은 `install-hold-review-r2-preparation.json`이다.

원 도우미의 `Add-Type -LiteralPath`를, 이미 백업 도우미에서 사용한 잠금 스트림의
고정 해시·길이 검증 후 `Assembly.Load(byte[])` 방식으로 바꿨다. 로더는 같은 검증
핸들에서 DLL 바이트를 읽고 핸들을 계속 유지한다. 원 파일/추가 스트림 삭제, 시스템
보안 설정 변경, 설치본 재빌드는 없다. 서버의 Zone.Identifier 내용은 직접 읽지 않았으므로
그 값은 확정하지 않는다. 개발 PC에서 ZoneId=3을 붙인 동일 DLL 사본의 기존 로더가
같은 오류를 내는 것을 재현했다. 이 오류 조건은
[Microsoft의 .NET Framework 설명](https://learn.microsoft.com/en-us/dotnet/framework/configure-apps/file-schema/runtime/loadfromremotesources-element)과도 일치한다.

수정 도우미는 20,776B/SHA256
`7b9f9de874adb099300d340dc0a54849b482e415ff0b39c0cff77bc677b6179d`다.
다음 검사는 모두 실제 exit0이며 개발 PC의 격리된 입력만 사용했다.

- `test_pinned_backup_engine.ps1`: 기존 오류 재현, 변조/길이 불일치 거부,
  파일 잠금, DLL/Zone 스트림 유지, 실제 백업 엔진의 본문/추가 스트림 검산 등 9개 PASS.
  결과 `engine-load-r2-test1/review.json`.
- `test_install_field_candidate.ps1`: 기존 설치·정상 종료 전제·설정 보존 검사 28개 PASS.
  결과 `install-function-tests-r2/tests-result.json`.
- `validate-install-controller.ps1`: 합성 설치 프로그램의 실제 exit0, 설치 파일,
  원본/추가 스트림 보존과 승인한 한 설정값 변경 흐름 PASS.
  결과 `install-integration-r9/integration-review.json`. 서버 registry/관리자 ACL 검증은 아니다.
- `test-install-launcher-r2.py`: native PowerShell 5.1 호출 7개가 각각 기대한 종료 코드와
  출력을 반환했다. stderr의 모든 CLIXML 문서를 읽어 progress/information만 있음을 확인했다.
  결과 `install-carrier-tests-r2/result.json`, `output-review.json`.

최종 백업/정상 종료/비교의 같은 핀으로 별도 R2 생성기를 실행했다(exit0).
서버 최종 폴더는 `C:/Users/user/Desktop/SmartFactory/INSTALL_OFF_20261014_0dd2ced0_R2`다.
10파일 묶음 manifest SHA256은
`2685066d3d92d2b3ae0771824f35c80a2dd4c94bb847cf8e0e75ded96b0faa78`이며,
별도 `PINNED_FIELD_INSTALL_COMMAND_0dd2ced0_R2.txt`는 8,409B/SHA256
`12b025261689f214e2a26018cc8febac0b037676be1a3199385ab8ea0af51d9f`다.
기존 묶음/실패 결과를 보존하고 총11파일을 새 공유 전달 폴더에서 서버 SmartFactory까지
복사했다. 개발/공유 모든 해시를 대조했으며 서버에서는 절대경로, 묶음10파일,
메모장에 열린 R2 경로·핀을 확인했다. `server-install-delivery-r2.json`과 3개 화면에 기록했다.
서버 R2 로컬 해시 검사는 사용자 실행 시 launcher가 수행하며 아직 완료로 주장하지 않는다.

사용자에게 열린 R2 명령 본문을 관리자 PowerShell 5.1에서 한 번 실행하도록 요청했다.
앱은 종료 상태로 유지하며, 실제 설치 결과 확인 후에만 재시작과 승인된 나머지 현장
검증을 진행한다. 물리 경계 NOT_TESTED, 정식 출시 HOLD, promotion false를 유지한다.

### 2026-10-14 13:49 KST 닫힌 CSV 검사 완료와 후보 설치 종료 관찰

로컬 CSV 재검사의 실제 소비자는 exit0, worker/driver도 exit0로 끝났다. 소요시간은
2,810.281초(약46분50초)이며 강제 종료가 없고 소유 Job의 잔존 프로세스는 0이다.
stdout 5,931B의 마지막 PASS뿐 아니라 terminal과 모든 출력 해시, 종료 후 입력 결합을
확인했다. raw `recovered-csv-r2/review.json` SHA256은
`a83117821ae8a6c53c876d4317ac5692d061d5c5d15d32dcd92ae62178dd271c`다.
이미 검증한 최종 서버 manifest의 동일 입력5파일에 결과를 결합한 별도 검토
`PDCA_FIELD_CAPACITY_20261014_0dd2ced0/recovered-csv-r2-final-review.json`은
2,216B/SHA256 `fa4ac4b637502e5e99edc0dc8ed680689c27efb70a518af8ffaf2def7ec04eab`다.
기존 잠정 상태의 원문은 소급 변경하지 않았다.

CSV142,273행/seq323776–466048, 관측 대장314,216행의 행 수/해시와 CSV142,273행의
연결률100%/키 누락0/진단 출처 불일치0, 이미지 대장4,237,531행의 행 수/해시가 통과했다.
이 검사는 이전 운영 build541d의 회수된 닫힌 CSV와 지정 대장 범위다. v1은 검증된
metadata에서 비활성화되어 요청하지 않았고, 선택 changeover/phase 대장은 0행 manifest와
부재 상태를 유지했다. `current_server_promotion_profile_required=False`이며 새 후보의
현장 QA·개별 이미지 바이트 디코딩·전체 과거 데이터·drop173 해소의 PASS는 아니다.

사용자가 R2 실행 완료를 알린 후 새 서버 결과 폴더
`C:/Users/user/Desktop/SmartFactory/I90b5ed1b`를 확인했다. installer-exit 원문을 메모장으로
읽어 후보 설치 PID12752, 시작04:48:45.5958403Z, 종료04:49:19.5212467Z,
실제 exit0/forced_termination=false를 관찰했다. 화면은
`server-install-r2-installer-exit-observed.png`에 보존했다. 아직 최종 결과 해시를
회수한 상태는 아니며 설치·설정·데이터 보존 검산 전체 완료로 처리하지 않는다.

13:54 KST까지 request/runtime-before/config-before/installer-start/installer-exit/
installed-files의 6파일만 보이고 registration 및 검산 진행 출력이 없었다. 개발 PC에서
같은 native PowerShell의 실제 registry 객체를 `ConvertTo-Json -Depth 35`로 변환하는
읽기 전용 재현은 15초 제한을 넘겼고, 검증에 쓰는 문자열5개만 추린 변환은 34.6ms/exit0였다.
원 객체에는 PSDrive/PSProvider 부가 객체가 있다. 결과는
`registration-serialization-probe-r1/comparison.json`에 기록했다. 서버의 지연 위치와
일치하는 원인 후보지만 서버 프로세스의 호출 스택을 직접 확인한 것은 아니다.

등록 정보 기록을 문자열5개만 저장하도록 수정했다. 수정 소스 SHA256은
`a95ec69d7fef3371745ad32685fa10b26f858ef9f93fe1a8669c39b25e225c1a`다.
실제 provider 부가 객체/읽으면 실패하는 무관한 속성을 배제하는 회귀를 포함한
`test_install_field_candidate.ps1` 31개와 합성 전체 제어 흐름이 exit0였다
(`install-function-tests-r3`, `install-integration-r10`). 이 수정본을 서버에서 실행했다고
주장하지 않는다. 사용자에게 지연된 확인 명령을 Ctrl+C로 정상 중단하고 프롬프트가
돌아왔는지 알려 달라고 요청했다. 설치는 반복하지 않으며, 중단 결과 확인 후 별도
검산 도우미로 현재 후보 파일·설정·데이터 보존을 확인할 예정이다.

### 2026-10-14 설치 없이 검산만 재개하는 도우미 개발 검증

`PDCA_LIMITED_FIELD_20261014_0dd2ced0/verify-field-install-resume.ps1`은 위 수정 소스에서
설치 실행 함수와 호출을 제거한 별도 도우미다. SHA256은
`ac197fb1b41317e3bd162b27ffb7907f44c15c9ca71a45323a09cb68b2d94a33`이며,
원 소스와 정확한 변경 내역은 `postinstall-resume-source-derivation.json`에 보존했다.
이 도우미는 기존 설치 exit0·PID·시각, 이전 결과 파일의 크기/해시, 원래 요청/설정,
중단 확인 및 이전 launcher 프로세스 부재를 확인한 뒤 남은 검산을 수행한다.
설치 실행 코드는 없으며 원본/백업의 본문·추가 스트림 전수 검산이 끝나야
승인된 comparator 플래그 하나를 false로 바꾼다. 앱 실행이나 운영 승격은 수행하지 않는다.

native PowerShell 5.1의 모의 재개 시험 8개와 별도 launcher 시험 7개가 통과했다.
정상 재개는 실제 모의 설치를 사전 준비에서 한 번만 실행하고 재개에서는 0회 실행했다.
이전 설치 실패, 영수증 해시 불일치, 이전 요청 불일치, 중단 미확인, 이전 프로세스 활성,
결과 폴더 구성 변경, 설치 파일 변조를 각각 설정 변경 전에 거부했다.
launcher는 helper/request/index 잠금, 외부 핀/입력/폴더 구성 거부, 실제 child 종료 코드,
부모 콘솔 유지, 개발 호스트 거부를 검사했다. 각 거부 시험의 예상 exit1/17은 PASS의
조건이며 정상 재개와 시험 driver는 exit0였다. stdout/stderr를 모두 검토했고, stderr의
복수 CLIXML 문서는 progress/information뿐이었다. 첫 출력 검토는 CP949를 UTF-8로
해석해 exit1이었으나 strict CP949 해독을 추가한 검토는 exit0였다. 시험을 재실행하거나
원 출력 파일을 바꾸지 않았다.

종합 결과 `postinstall-resume-development-review.json`은 10,983B/SHA256
`a2f7042413f57910095491031ee5dd24c5ca3d0c6dcf045cc4d0508a27ab04aa`다.
이는 개발 모의 검증이며 실제 서버 registry/관리자 ACL/데이터 검산 통과가 아니다.
서버 실행용 최종 요청·index는 아직 생성하지 않았고, 새 묶음을 전달하거나 실행하지 않았다.

재개 절차는 다음 순서를 따른다.

1. 사용자 Ctrl+C 후 기존 관리자 콘솔의 프롬프트 복귀와 결과 파일 상태를 확인한다.
   설치 명령은 반복하지 않는다.
2. `I90b5ed1b`의 실제 최종 파일을 새 공유 return 폴더로 회수하고, 기존 설치 시각/PID,
   요청 및 설정 핀을 대조한다. 민감한 config 본문은 출력하지 않는다.
3. 회수 원문을 보존하고 외부 고정 index/새 요청/묶음과 실행 명령을 만든다.
   기존 R1/R2 바이트를 바꾸지 않고 개발/공유 해시 및 서버 최종 경로·파일을 확인한다.
4. 중단과 이전 프로세스 부재를 확인한 재개 도우미만 사용자에게 실행 안내한다.
   백업의 기존 180분 유효성 검사는 유지하며, 기한이 지나면 임의로 완화하지 않는다.
5. 새 콘솔 결과 해시를 회수 파일과 대조한 뒤 표준 사용자 앱 시작과 현장 검증을 진행한다.

현재는 1번의 사용자 중단 확인을 기다린다. 원격 터미널 조작을 하지 않으며,
설치 완료 관찰과 아직 미완료인 설치 후 검산을 구분한다. release HOLD를 유지한다.

### 2026-10-14 14:18 KST 설치 결과의 중간 사본 회수

사용자 중단 확인 전에도 이미 생성된 결과를 분석할 수 있도록 서버 탐색기에서
`I90b5ed1b`의 6파일을 새 공유 폴더
`Z:/SmartFactory/20261014/return/POSTINSTALL_I90b5ed1b_SNAPSHOT1/I90b5ed1b`로 복사했다.
주소 전송을 사이에 둔 첫 복사 시도는 대상에 파일이 생기지 않았으며, 원본/대상 탭을
미리 열고 파일 복사 후 탭만 전환하는 방법으로 회수했다. 개발 사본
`PDCA_LIMITED_FIELD_20261014_0dd2ced0/server-install-r2-snapshot1`은 각 파일의
공유/개발 크기·해시를 대조했고 기존 원본은 변경하지 않았다.

설치 exit0/PID12752/시작·종료 시각은 앞선 화면 관찰과 일치한다. 회수된 installer-exit은
487B/SHA256 `534f53436096a462de2c28a249667e4dec8a0fe3117705479fd545f6ef4af27b`다.
request는 전달한 R2 요청과 의미상 전부 같고, config-before는 원래 설정 핀과 일치한다.
runtime-before는 앱/포트가 비어 있었다. installed-files는 708,232B/SHA256
`3db2514b5d0a2a749efc8dc557d31aa3b2890e361733e549273a5dcd867f00df`이며,
기록된 1,815파일 중 후보 기준 1,814파일의 크기·해시가 전부 일치하고 나머지는 허용된
uninstaller 한 파일이다. config 본문을 출력하지 않았다.

검토 프로그램 `recover-install-snapshot1.py`는 exit0였다. 검토 영수증
`server-install-r2-snapshot1-review.json`은 1,926B/SHA256
`ed3e2f780363a23b72082543f38ce5ab29f46588f36e0621049d8562c2e5fe2e`다.
이는 중간 기록의 대조이며 현재 서버 파일을 다시 해시한 결과나 콘솔 최종 결과 해시에
결합된 완료 영수증이 아니다. `postinstall-snapshot1-index-NOT_FOR_EXECUTION.json`에는
`normal_console_interrupt_confirmed=false`를 명시했다. 최종 index로 자동 사용하지 않는다.

재개용 `POSTVERIFY_20261014_0dd2ced0`의 고정 기준 자료/수정 도우미/설명서 8파일은
개발 PC에서 준비·검증했다(exit0). index/request/manifest와 실행 명령은 미생성 상태이며
서버로 전달하지 않았다. 서버 콘솔을 가리던 탐색기만 최소화했고, 콘솔에는 아직 최종
결과나 `PS C:\...>` 복귀가 보이지 않는다. 터미널 입력은 하지 않았다. 14:18 KST 이후
제조사 Gmail 문의 thread도 읽기 확인했으며 현재 발신 메시지 1개뿐이고 답신은 없다.
기존 명령의 중단 확인 후 결과 폴더 최종 상태를 대조해 재개 절차를 이어가야 한다.

### 2026-10-14 14:51 KST 콘솔 닫기 확인과 설치 후 검산 재개

사용자는 Ctrl+C 후에도 `>>`가 그대로라고 보고했고, 지정한 관리자 PowerShell 창을
X로 닫아 달라는 요청에 “해당 창이 닫힘”이라고 답했다. 원격 화면에서도 창이 사라진
것을 확인했다. 이는 `operator-console-close`이며 정상 Ctrl+C 중단으로 기록하지 않는다.
확인 기록 `operator-console-close-confirmation.json`은 620B/SHA256
`f890e897c0bbd09a9b6d64ec8d14818deb935a491a69ea17d50c072ad8582488`다.
창이 닫힌 관찰만으로 관련 프로세스 부재를 확정하지 않는다.

닫힌 후 서버 `I90b5ed1b`를 새 공유 return 폴더
`POSTINSTALL_I90b5ed1b_STOPPED/I90b5ed1b`와 개발 `server-install-r2-stopped`로 회수했다.
6파일의 크기·해시는 앞선 중간 사본과 모두 동일했고 최종 result/registration은 없었다.
`recover-install-stopped.py`는 exit0, 검토 영수증은 2,013B/SHA256
`d2a4c09d53f6044fcb7a34a26b1282018b076f40d2fb6977fa7c34e338276f2f`다.
후보 설치 exit0와 1,814파일 일치 기록을 보존하며 설치는 반복하지 않는다.

별도 검산 도우미 R2는 위 닫기 방식과 기존 launcher의 UTF-16 명령 SHA256을 결합했다.
실제 기존 launcher가 남아 있으면 설정 변경 전에 거부한다. 설치 실행 함수/호출은 없고,
registry 기록은 검증에 필요한 문자열만 저장한다. 원본·백업 본문 및 추가 스트림을
전수 검산한 후에만 `SPOT.low_signal_comparator_verified`를 false로 바꾼다.
Low Signal 경고 OFF, 앱 종료, 물리 경계 NOT_TESTED, 정식 출시 HOLD를 유지한다.

native PowerShell 5.1 재개 시험 10개와 launcher 시험 7개의 최종 출력·종료 코드를 검토했다.
정상 재개/driver는 exit0였고 각 거부 시험은 예상 exit1/17을 확인했다. 두 정상 중단 방식,
잘못된 중단 방식, 기존 프로세스 활성 및 기존 영수증/설치 파일 변조를 포함한다.
재개 단계의 설치 실행은 0회다. 개발 검토 영수증
`postinstall-resume-development-review-r2.json`은 12,368B/SHA256
`1c511d6a1869f7af82f744c9d4b07c055e4a8a0d5013a72ae3c927058618043a`다.
이는 모의 검증이며 실제 서버 검산 통과를 대신하지 않는다.

최종 묶음 `POSTVERIFY_20261014_0dd2ced0_R2`의 주요 핀은 다음과 같다.

| 항목 | SHA256 |
|---|---|
| helper | `8d620268451e1dc83a80bd75fab734da5fa1f166dcb48e4c71152028f8d857a7` |
| manifest | `e1194c514cb3af61d87f71123a77658a1643cc8308c81723bd1d0a70a529d80c` |
| request | `aa3423dcc7b27610db72a9ad574af81180f5fcff4028905d676ae6ee611d825f` |
| index | `490225f54893dabbecfa93624605619972d7deeac36db6835cd95da41fabc317` |
| command | `9e484cd6cbe87f8f70557f59c19b2397b8de56b6e7876e16d95e2d29af6a4e97` |

개발/공유의 12파일 해시를 대조한 뒤, 서버 탐색기로 바탕화면 SmartFactory에 폴더와
명령 텍스트를 복사했다. 실제 절대경로
`C:/Users/user/Desktop/SmartFactory/POSTVERIFY_20261014_0dd2ced0_R2`와 내부 11파일을
확인하고 `PINNED_POSTINSTALL_VERIFY_COMMAND_0dd2ced0_R2.txt`를 서버 메모장에 열었다.
전송 영수증 `server-postverify-r2-delivery.json`은 3,677B/SHA256
`e10037ff3f0db6b91ac829a5ec534409f34a647c7dddee5ba38258f72e55aacb`다.
서버 파일 존재 화면과 서버 로컬 해시 검증은 구분한다. 기존 R1/R2 증거는 수정하지 않았다.

사용자가 새 관리자 PowerShell에서 “실행 중”이라고 답했고, 14:51 KST 화면에
`VERIFY phase=source-and-restored-verification`이 출력되는 것을 확인했다.
설치 파일/등록 확인 다음의 데이터 검산 단계에 도달한 관찰이며 아직 완료가 아니다.
백업의 기존 180분 제한은 유지했다. 준비 당시 나이는 원문 UTC 기준 84.08분이었다.

남은 절차는 새 결과의 `RESULT_PATH`, `RESULT_SHA256`, `LAUNCH_EXIT` 확인 → 새 return
폴더로 회수 → 콘솔 핀/증거 대조 → 통과 시 표준 사용자 앱 시작 순서다. 결과 확인 전
설치를 반복하거나 앱을 시작하지 않는다. 15분/120분 현장 시험과 정식 출시는 미완료다.


## 2026-10-14 설치 후 검증 완료와 후보 설정 확인 실행

15:45 KST 서버 검증 전용 R2가 `LAUNCH_EXIT=0`으로 완료됐다. 설치를 반복하지 않았다.
실제 결과 `C:/Users/user/Desktop/SmartFactory/I741a00a0/result.json`은 4,955B,
SHA256 `4724dd7d0e30dbbad1cb673b3936e1d84b58433a4546eb6341733730cc25438a`다.
콘솔 확대 증거와 회수본을 대조하고, 11개 결과 파일의 해시·요청·후보 payload 1,814개·
등록 버전 1.0.28·이전 installer exit0·이전 도우미 부재를 확인했다.
원본/사본 325,089파일·246폴더·680 named streams·14,095,162,877B가 보존됐다.
그 뒤 `SPOT.low_signal_comparator_verified=false` 정정만 적용됐으며 설정 결과는
2,671B / `be03f4ef477e4333f616ca8e0f3ef270b2ce3acaa05aeaef3075da3d46557b57`다.

검토기는 `review-postverify-r2-result.py`, 실제 실행 exit0이며 결과
`postverify-r2-production-review.json`은 2,606B /
`9ef69ff9c80abdef8ee84aef9c42f9072ea5af81436e7635bc5d22147530ee19`다.
작은 콘솔 화면의 최초 경로/해시 전사 오류는 원본 기록을 보존하고
`postverify-r2-console-correction.json`으로 정정했다. 공유 회수 wrapper 이름은
`POSTVERIFY_I714a00a0`이나 그 안 실제 서버 폴더는 `I741a00a0`다. 설치/서버 결과를
다시 만들거나 이름을 바꾸지 않았다.

15:56 KST 일반 사용자 바탕화면 바로가기로 후보 4cc를 시작했다. 두 차례의 각 6개
read-only API 조회는 모두 HTTP200/collector exit0였다. logger
`b5902b84-a041-451a-9f46-451b17bda87d`, schema2.5.2, 작업60580/1을 관찰했다.
Low Signal alarm 및 configured/effective comparator는 false다. 승인 프로파일과
일치하지만 이전 Operator1 지문 때문에 `fingerprint_mismatch`로 표시됐다.
현재 후보 지문은 `3ddc2e9080e7d804bdb1eb784d5136b38286c92dc927850c82d16a04732c7683`다.

이 실행은 설정 획득용이며 계측 기동 3회 중 하나로 계산하지 않는다. 16:01 KST
앱 X로 정상 종료를 요청했다. 회수된 CSV는 1–1152 연속이며 startup_pending22,
stale197, valid933이다. 시작 시 observation fact 초기화는 약26.94초였고 후속 조회에서
stale197은 증가하지 않았다. 이 값을 기동 성능 PASS로 바꾸지 않는다.
CSV closeout은 shutdown/finalized이며 같은 시각 후보의 종료 영수증은 10개 서비스
종료/배출 단계와 이미지241건 전량 저장·실패0·drop0을 기록한다. native process exit는
아직 독립 확인하지 않았다. metadata의 이미지 요약 written0/이전 fact row_count와
종료 영수증241의 차이는 별도 데이터 검증 대상이다. 전체 CSV-fact join·이미지 decode는
이 설정 확인 검토에서 수행하지 않았다.

`review-candidate-config-closed.py`는 exit0, 검토 결과
`candidate-config-acquisition-review.json`은 5,173B /
`22353e397b1413055a478729c5f2e46b86272c733d56c5763257736e4609c9da`다.
서버 설정 재확인 도우미는 아직 미실행이며 앱은 종료 상태다. 후속 순서는 승인된 USER_SELF
설정 확인 기록 적용, 실제 재기동 설정 확인, 계측 기동3회·15분/120분·종료 데이터 QA다.
물리 경계 NOT_TESTED, 정식 QA/출시 HOLD, 운영 승격 금지는 유지한다.


## 2026-10-14 후보 운영자 확인 기록 도우미 전달

기존 승인 USER_SELF를 실제 후보 지문에 연결하는 `ATTEST_OFF_20261014_0dd2ced0`을
준비했다. 기존 attestation 도우미 바이트는 변경하지 않았다. 새 wrapper는 서버/SID/
native PowerShell5.1·승인·프로파일·닫힌 metadata·설정 해시·앱/8000 부재·config 추가
스트림0을 검사한다. 고정된 잠금 바이트로 기존 도우미를 실행한 뒤 네 attestation 필드
외 내용이 바뀌지 않았는지 확인한다. 결과는 새 보호 폴더에 만들고 콘솔 해시를 출력한다.
설치 반복·앱 시작·운영 승격 코드는 없다. 이미 적용된 설정으로 재실행하면 원본 해시
검사에서 중단한다.

격리 Windows PowerShell5.1 검사7개(정상 적용, 앱 활성, 설정/metadata 해시 불일치,
config 추가 스트림, 재실행, 개발 PC에서 실제 서버용 코드 차단)와 carrier 검사7개가
모두 기대한 exit0/1/17을 냈으며 두 드라이버는 exit0다. 모든 stdout과 stderr를 검토했다.
stderr의 UTF-8/CP949 및 부모·자식 CLIXML 결합 때문에 검토기 두 번이 중단됐으나,
출력 형식을 처리한 최종 검토에서는 information/progress만 확인했다. 서버용 코드나
검사 결과를 바꾸거나 이 검토 오류를 서버 장애로 기록하지 않았다.

묶음10파일과 명령1파일, 총82,210B를 공유 send 아래로 전송해 해시를 대조한 뒤,
서버 `C:/Users/user/Desktop/SmartFactory/ATTEST_OFF_20261014_0dd2ced0`의 실제 경로와
10개 파일을 일반 탐색기로 확인했다. 서버 루트의
`PINNED_FIELD_ATTEST_COMMAND_0dd2ced0.txt`는 메모장에 열었다.
bundle-manifest SHA256은
`288a2b93979d2bea08ff03f35dee928b75323cec99f00c698b7760f4daaa37c0`,
wrapper SHA256은 `0a519643275da1c72329e2a34fdbaf1f47d661b09a78d5ce51afc7e30a089a3a`다.
서버 로컬 해시는 아직 실행 전이며 파일 존재 관찰을 해시 검증으로 대체하지 않았다.
전달 영수증은 `server-attestation-delivery.json`이다.

원격 UI 터미널 조작 제한에 따라 사용자에게 전체 본문 복사·PowerShell 실행만 요청했다.
이 기록 시점에 서버 attestation은 미실행이며 앱은 종료 상태다. 실행 결과를 회수·대조하기
전에는 앱을 다시 시작하지 않는다. 물리 경계 NOT_TESTED, 정식 QA/출시 HOLD를 유지한다.


## 2026-10-14 USER_SELF 확인 기록 적용과 실제 재기동 확인

사용자 실행 후 16:33 KST `LAUNCH_EXIT=0`을 확인했다. 실제 결과 폴더는
`C:/Users/user/Desktop/SmartFactory/Aa99a9622`이며 result.json은 2,621B /
`14912203e64a8e69cd75d7772ddf50e5d8b7cdb34dd38f2fccfb268e1319f88f`다.
5개 결과를 공유 return과 개발 PC로 회수해 전 파일 해시·콘솔 핀을 대조했다.
`review-field-attestation-result.py` 실제 검토 exit0, 격리 검토기 검사10개도 exit0다.
서버는 적용 전 native 앱 프로세스/8000 listener 부재를 확인했고, 적용 후에도
부재를 검사했다. 이는 앞선 종료 이후의 부재 증거이며 정밀 종료 소요 시간 측정은 아니다.

허용한 네 attestation 필드 외 설정은 동일하다. 결과 config.ini는 2,671B /
`2f872a957b0899858a2f71a2c8b8928f3ef9f416ed04ce2ca7282f83adaf5fb4`다.
운영자 USER_SELF, 확인 시각 `2026-10-14T07:33:48.472124Z`, 후보 지문 3ddc2e90…을
실제 파일에서 확인했다. Low Signal alarm/configured comparator는 false이며 물리 시험
미완료를 verified로 바꾸지 않았다. `attestation-production-review.json` SHA256은
`e8dc2f789e6c7f7d9a4a915c46f1a46faeac679ec75a998cf7aa1086f800cd69`다.

재실행 전에 서버의 `spot_image_fact_manifest.final.json` 457B를 보존했다. SHA256은
`8f25709068c73e79141222e5b72b597da1323095a072bef9b4fbf5f6d7b62fdd`다.
시작 sidecar 요약4,237,531행/written0과 별도 종료 요약4,237,772행/written241의
차이241은 종료 영수증241과 일치한다. 종료 요약의 failure/drop도0이다. 후보 코드와
현재 코드의 관련 파일이 같고, 시작 sidecar를 보존하면서 별도 종료 manifest를 작성하는
계약 및 portable final-manifest validator 검사2개가 exit0였다. 이 요약 차이는 설명됐다.
회수 파일과 공유 사본 해시는 같지만 서버 콘솔 핀은 없으며, 실제 누적 image fact 바이트
해시 대조·241개 이미지 decode·전체 CSV-fact join을 수행했다는 뜻은 아니다.
근거는 `candidate-image-manifest-comparison.json`이며 기존 취득 증거는 수정하지 않았다.

16:43 KST 표준 사용자 바탕화면 바로가기로 후보를 실행했다. 실제 API에서 확인 상태
verified, USER_SELF, 동일 지문, drift=false/빈 목록, 승인 프로파일, Low Signal OFF를
확인했다. logger `5122ad44-bc29-49d3-88c7-f622a3232732`, 새 CSV
`Factory_Integrated_Log_v2_20261014_164348.csv`, 작업60580/1이다.
두 차례 각6GET 모두 HTTP200/collector exit0이며 CSV rows1→323, 이미지0→67로 증가했다.
관측 오류 목록은 비어 있고 이미지 failure/drop0이다. 초기 startup_pending14/stale191은
그대로 기록한다. observation 초기화 약26.45초 관찰이며 기동 성능 PASS가 아니다.
이 실행도 사전 native 계측이 없으므로 정상 기동3회의 계측 결과로 계산하지 않는다.

`candidate-attested-runtime-review.json`은 7,770B /
`3db01449ec50aea1720863f41512a1b7e62e50186beb97e4f415fd4f98195d11`이다.
실제 runtime에서 필요한 필드만 고정한 제한 현장 설정 기준은
`candidate-attested-configuration-reference.json` 1,985B /
`4d4c9b05068719f7bc8810ab7fc0bfa8ab9b83c727d422205e7f687da45ac29f`이며,
기존 설정 binder가 지문을 재계산해 DISABLED_LOW_SIGNAL_FIELD_TRIAL 범위 PASS를 확인했다.
실제 native 프로세스 식별·서버 내부15분/120분 측정·계측 기동3회·전체 데이터 QA는 남아 있다.
현재 앱은 Running으로 유지하며 설치/attestation 명령은 반복하지 않는다.
물리 경계 NOT_TESTED, 정식 QA/출시 HOLD, 운영 승격 금지를 유지한다.


## 2026-10-14 실제 프로세스 결합 15분 관찰 R2 전달

확인 기록이 유효한 Running 후보를 유지하며 서버 내부 900초 관찰용 묶음을 준비했다.
기존 FIELD_OFF R2의 RUN128 계측기와 후보 payload 기준은 재빌드하지 않았다.
준비 도우미는 실제 8000 listener, 설치 경로, 부모 프로세스, PID와 생성 시각을 확인한다.
현재 config 해시와 승인·runtime 설정 기준을 대조하고 실제 프로세스 식별값을 가진
관찰 요청을 만든 뒤 기존 계측기를 호출한다. 앱 시작·종료, 설치, 설정 수정은 수행하지 않는다.

첫 개발 검사에서 FILETIME을 먼저 부동소수점으로 바꾸면 psutil 생성 시각과 달라지는
문제를 발견했다. R1은 서버에 전달하지 않았다. R2는 정수 상태에서 Unix 기준 시각을
먼저 빼고 초로 환산한다. 실제 Windows PowerShell 5.1 프로세스 값 대조를 포함한
native 검사10개와 명령 운반부 검사7개가 통과했고 각 드라이버 exit0다.
분기 검사의 CIM/listener는 fixture이며 실제 프로세스 정밀도 검사는 별도 native 측정이다.
성공 요청은 기존 field_runner validator로 검사했다. 전체 stdout/stderr를 읽었으며
CLIXML stderr는 information/progress였다. 개발 검사를 서버 현장 PASS로 계산하지 않는다.

공유 `Z:/SmartFactory/20261014/send/OBS15_OFF_20261014_0dd2ced0_R2_delivery`에서
서버 `C:/Users/user/Desktop/SmartFactory/OBS15_OFF_20261014_0dd2ced0_R2`로 복사했고,
일반 탐색기에서 실제 절대경로와 묶음8개 파일을 확인했다. 루트의
`PINNED_FIELD_OBSERVE15_COMMAND_0dd2ced0_R2.txt`를 메모장에 열고 `$observeBundle=`
시작 본문을 확인했다. 묶음과 명령 합계9파일/29,976B다. 공유 사본은 해시를 대조했으나
서버 로컬 해시는 사용자 실행 시 잠긴 입력으로 검증한다. 파일 존재 확인을 해시 PASS로 대체하지 않는다.

bundle-manifest SHA256은
`c784a6af1d2b4067c50f096b6ac8122ce07f7538290fc12fd92f4a8d575c2052`,
도우미 SHA256은 `d5ff3ddf1ad941da5b5ad97791e190a200c4d50ffdb8d310d06fbcbedc61c235`,
명령 SHA256은 `515ad2e0e71e2f436147310cd4bb6516d8608f32709d21b1bdb7d304e2180f60`이다.
전달 영수증은 작업 루트 `server-observe15-r2-delivery.json`, 개발 검토는
`observe15-development-transfer-review.json`이다. 기존 실패·원본 증거는 보존했다.

이 기록 시점에 관찰은 미실행이며 원격 UI 터미널 조작 제한 때문에 사용자 실행을 기다린다.
앱은 Running으로 유지한다. 시작 시 PREPARATION_PATH/PREPARATION_SHA256,
STARTING_FIELD_OBSERVATION_SECONDS=900을 출력하며, 이후 상세 출력 없이 측정할 수 있다.
마지막 RESULT_PATH/LAUNCH_EXIT와 결과 파일을 회수·대조한 뒤 측정 결과를 판단한다.
15분/120분, 사전 계측 기동3회, 전체 데이터 QA는 미완료다.
물리 경계 NOT_TESTED, 정식 QA/출시 HOLD, 운영 승격 금지를 유지한다.


## 2026-10-14 15분 회수 결과의 오프라인 검토 준비

서버 측정 실행 답변·시작 출력은 아직 확인되지 않았다. 살아 있는 계측 프로세스의
현재 핸들을 확인한 상태가 아니므로 verified wait나 실행 중으로 분류하지 않는다.
기존 실행 요청을 유지하며 중복 요청·설치·앱 재시작은 하지 않았다.

작업 루트의 `review-observation-recovered.py`를 준비했다. 실제 콘솔의
LAUNCHER_SHA256/PREPARATION_SHA256을 받아 launcher→session manifest→모든 파일과
preparation→실제 native 요청의 바이트 연결을 확인한다. 고정된 helper f274b534 소스를
검산한 뒤 기존 순수 계산 함수로 HTTP·자원 요약과 결합 window 검토를 다시 계산한다.
서버 API/프로세스에 접근하지 않는 회수 사본 전용 도구다. `RECORDED_SUMMARIES_REPRODUCED`는
저장된 계산 결과의 재현이며 관찰 PASS·전체 성능/정식 QA PASS와 구분한다.

파일 변조·누락·추가·경로 탈출·JSON 중복/비정상 수치·승격 주장 거부, frozen 소스 핀,
첫 health 요청223.4887ms 실패 보존, 자원 표본 누락과 성능 gate 구분 등16검사 exit0다.
첫 실행은 기존 fixture의 시험 폴더 환경값이 없어 import 중 exit1이었다.
시험용 환경값을 지정한 후 통과했으며 검토기 코드는 이 수정으로 바뀌지 않았다.
전체 pipeline fixture와 실제 서버 결과 실행은 아직 미수행이다. 실제 회수 후에는
stdout/stderr 원문·설정/세대 경계의 의미·자원 성능을 별도로 검토한다.
근거는 `observation-review-readiness.json`과 `observation-recovered-review-tests-r2/result.json`이다.

제조사 문의 thread1a134ba4e225b647은 재조회 결과 발신1건만 있고 답신은 없었다.
물리 경계 NOT_TESTED, 정식 QA/출시 HOLD, 운영 승격 금지를 유지한다.


## 2026-10-14 실제 15분 관찰 완료: FAIL 및 원시 기록 검산

사용자 실행 후 준비 폴더 `C:/Users/user/Desktop/SmartFactory/Pdcdfcda8`와
900초 시작 출력을 확인했다. preparation SHA256은
`091746d11e1d2c7722c9c35f38945db8ab81f410af14efe54e03ecc1ee3ac31f`다.
준비 4파일을 회수해 콘솔 핀·manifest·실제 main10068/backend10724 식별값과 요청을
대조했다. `observe15-native-preparation-review.json` 검토 exit0다.
종료 전 작업 관리자에서 field_runner PID12268/11876/12012/4928/8288/13444의
Running 상태를 관찰했으며, 재실행하지 않고 같은 실행의 완료를 기다렸다.

실제 결과는 `C:/Users/user/Desktop/SmartFactory/run-b1c4ac5cd2c1`, `LAUNCH_EXIT=1`이다.
launcher SHA256 `a6d81deedcb97a6873db1e47656d937f4e27ada9092c42644a82a120c5429c1c`를
콘솔에서 읽고 공유 `Z:/SmartFactory/20261014/return/OBS15_run-b1c4ac5cd2c1`와
개발 작업 루트의 `server-observe15-run-b1c4ac5cd2c1`로 회수했다.
7,632파일/36,825,802B의 공유·개발 사본 해시가 같고, launcher→session manifest→
7,627개 session 멤버의 바이트 연결 및 정확한 파일 집합을 검증했다.
회수 영수증 `observe15-result-recovery.json` SHA256은
`46445077cabbf224354922215eb302426d476f10a97798f93ae83b474ba5181f`다.

원시 표본으로 HTTP·자원·결합 검토를 재계산한 `review-observation-recovered.py`는
exit0/RECORDED_SUMMARIES_REPRODUCED이며 **관찰 판정은 FAIL**이다.
`observe15-production-replay-review.json` SHA256은
`7de524e1f905dd26f1d50616701b1fab847f4e76141820a77ad6652698afb6ea`다.
재계산 성공을 현장 성능 통과로 바꾸지 않는다. 측정은 서버 시각 기준 약17:21:18–17:36:18,
900초다. supervisor는 observing→finalizing→done을 기록했고 강제 종료 요청은 없었다.

| 항목 | 실제 표본 / 예정 표본 | 관측 결과 |
| --- | --- | --- |
| `/health` 정기 요청 | 445 / 450 | 200ms 초과134건, 최대3189.3657ms, p95 1270.1193ms, 예정5회 누락 |
| 시작·종료 health | 2 / 2 | 6.8373ms / 114.9339ms; 첫 요청 포함, 경계 합계447/452 |
| `/api/data` | 150 / 150 | 500ms 초과21건, 최대2342.9222ms, p95 1158.1565ms |
| 이미지 API | 2441 / 3600 | 예정1159회 누락, HTTP502 1건, 최대2599.6609ms, 500ms 경고150건 |
| 자원·프로세스 | 각181 / 181 | 표본 범위 충족, 모든 프로세스/listener 표본 PASS; 자원 성능 gate는 NOT_EVALUATED |

정기 HTTP timeout은0이다. 이미지 예정 표본 누락은 계측 요청 일정의 미수행이며 앱의
이미지 저장 drop으로 해석하지 않는다. 최초 health 기준 초과는17:22:10, 292.5392ms다.
health 초과134건 중125건의 가장 큰 클라이언트 단계는 응답 헤더 대기였지만 이 시간에는
클라이언트·서버 스케줄링 지연도 포함될 수 있다. 단독 backend 병목의 증거로 삼지 않는다.
측정 중 준비 파일 회수용 탐색기 조작과 읽기 전용 작업 관리자 확인을 수행했다.
작업 관리자에서 높은 host/Explorer CPU를 관찰했으나 host 전체 프로세스 시계열은
수집하지 않아 인과를 확정하지 못했다. 이 구간이나 지연값을 제외하지 않았다.

설정 양쪽 경계의 raw body와 승인 기준을 다시 계산해 같은 지문·Low Signal OFF·
comparator 미검증을 확인했다. 앱 payload1814파일, main/backend, SPOT/logger 세대는
양쪽 경계에서 일치한다. control-final도 같은 backend 세대와 HTTP200이나377.5647ms로
200ms 조건을 초과해 FAIL이다. 이 중 연결 단계375.0058ms였다.
445개 health body는 모두 Running/driver 연결/success/fresh였고 관측 저장 실패·거절0이다.
앱 프로세스 합산 CPU는 머신 용량 기준 평균7.52%/최대15.03%였다. Electron PID9700의
RSS는318,984,192→745,070,592B로 증가했다. 역할별 프로세스 명령행과 장기 회수 추세를
확인하지 않았으므로 이를 메모리 누수 확정이나 자원 성능 PASS로 표현하지 않는다.

worker는 HTTP exit1, resources/processes exit0이며 오류 예외 목록은 비어 있다.
outer launcher는 종료 직후 job active1 때문에 `outer-descendants-remain`을 추가 기록했고,
이어 강제 종료 없이 active0이 됐다. 잔류 프로세스 식별값은 기록되지 않았다.
동일 frozen 계측기의 개발 PC `--help` 3회로는 재현되지 않았고 각 actual exit0/
launcher PASS였다. 이는 실제 observe 자식 구성을 재현한 시험이 아니며 원인 해결로
계산하지 않는다. 운영본·계측기 바이트는 변경하지 않았다.
10개 stdout/stderr 중 root stdout의 FAIL JSON 외에는 모두 비어 있었다.
`analyze-observe15-failure.py` exit0, 결과 `observe15-failure-analysis.json` SHA256은
`b3bc7cc29f987fcd508aee3cce9bbdae9d969df5742d6b384040eedabe8ae2aa`다.

측정 후 기존 읽기 도우미로 LAN GET6회 모두200/exit0를 확인했다. 이미지502의 원문과
오류 API, transport 실패 event22152는 correlation
`transport:b52e652bca9445349c0790183b3bc4cd`로 연결된다.17:24:21의 장비 이미지 요청이
RemoteDisconnected/1422ms로 실패했고 포트 재사용 위반·bind 충돌·풀 고갈은0이었다.
이 연결 단절의 근본 원인은 미확정이다. 후속 이미지 상태는ok, 저장3227/실패0/drop0이다.
`observe15-post-read-review.json` SHA256은
`5e8658af62b09aae7e41f576d5306042df0ea7443a62eac4967b6d10e21ddcc4`다.
LAN 단발 조회의 회복을 실패한15분 결과의 대체 PASS로 삼지 않는다.

서버 `AppData/Roaming/SmartFactoryLogger/logs/system`의 system.log/status.log를 탐색기로
공유 `OBS15_LOGS_1758_b1c4ac5c` 아래 회수했다. 운영 중 파일의 사본으로 atomic snapshot이나
서버 콘솔 핀은 없으며, 공유·개발 사본 해시와 분석 범위만 보증한다.
같은 PID10724/session0bb15639768c의 health slow9건에서 PLC1429.1ms,
runtime info1005.5ms, frontend 파일 확인1060.2ms의 단계별 최대가 관찰됐다.
여러 단계에 분포해 단일 원인을 특정하지 못했다. 같은 시간대 plain-text Config 경고18건은
별도 로그 형식으로 보존했고 JSON 손상으로 분류하지 않았다. status.log는
17:24:27 Running→Warning,17:25:22 Warning→Running을 기록한다.
`observe15-live-log-review.json` SHA256은
`1a8c24a783c53466e360c8f940e427228e5f2220fb746739ae4cefa41e178ca4`, 검토 exit0다.

다음 진단 체크리스트:

- 동일 실행의 서버 slow 로그와 클라이언트 시간, 계측 부하 및 host 프로세스 자원 경합을
  구분할 최소 계측을 준비한다. 현장 원인 미확정 상태에서 단순 재시험으로 실패를 대체하지 않는다.
- outer job 종료 경고는 실제 observe 자식 구성을 사용하는 격리 재현으로 조사한다.
  자식 종료 확인·잠긴 입력·실패 보존을 약화하지 않는다.
- 원인과 필요한 조치를 확인한 뒤 영향받은15분 조건을 다시 검증하고120분 착수 여부를 결정한다.
- 계측 기동3회, UI/packet/전체 데이터·정상 종료 QA 및 물리 경계는 여전히 미완료다.

앱은 Running, 120분 미시작, 물리 경계 NOT_TESTED, 정식 QA/출시 HOLD를 유지한다.
설치·설정 변경·재시작·운영 승격·롤백 기준 갱신을 수행하지 않았다.

## 2026-10-14 지연 구간 대조와 host 진단 소스 검증

원시 응답의 `x-trace-id`와 회수한 system.log를 같은 식별자로 연결해 health 6건과
이미지 오류 1건을 대조했다. 최대 health 요청 `health-00223.json`의 클라이언트 시간은
3189.3657ms, 서버 build_health 구간은1010.6ms(runtime_info1005.5ms)였다.
차이2178.7657ms에는 계측하지 않은 처리·대기·클라이언트/서버 스케줄링이 포함될 수 있다.
이를 특정 CPU 병목이나 네트워크 대기 시간으로 단정하지 않는다. 같은 세대의 다른 요청도
PLC·runtime_info·frontend 구간에 지연이 분포했다. 근본 원인은 UNCONFIRMED다.

`observe15-trace-joined-records.json` SHA256은
`cbc6ca3380bfd411be72273a489f676a160e01df19379fea4bd780d3a5325ca8`이다.
원시 표본의 session manifest와 로그 사본 해시를 대조한 통합 검토
`observe15-causal-followup-review.json`은 exit0, SHA256
`b5fa188a515f0d98185f7cdd311df4f8de72f170c1029966db7b6f8eb341fecd`다.

종료 경고는 기존 f274b534 helper 소스28개를 해시 검증해 복사한 뒤 실제 observation의
HTTP/resources/processes 자식 구성과 같은 outer launcher로 격리 재현했다.
개발 PC에서 frozen onefile의5초 관찰3회는 모두 actual exit0, outer7/active0,
inner4/active0, 강제 종료0이었고 fixture 앱도 정상 종료했다. 당시 서버의
`outer-descendants-remain`은 재현되지 않았다. 짧은 합성 시험이므로 실제15분의
종료 경합을 배제하거나 실패가 해결됐다고 해석하지 않는다. 기존 launcher 판정은 유지한다.
근거는 바탕화면 `SmartFactory/PDCA_OBS15_DIAG_20261014_b1c4ac5c/result.json`, SHA256
`e2fc874a4dc8ec54ed3199d45d86527c70658f8cc57898085a41c0ea24e6b619`다.

새 개발 소스 `scripts/field-v1028/field_host_sampling.py`는 host CPU/메모리와
각 프로세스의 PID·생성 시각·실행 파일명·CPU·메모리만 읽는다. Windows의 제한 조회
핸들 하나로 동일 프로세스 객체를 읽고 원시 생성 시각으로 PID 재사용을 구분한다.
명령행·환경 변수·사용자명·실행 경로는 결과에 저장하지 않는다. 접근 거부·세대 변경·
감소한 카운터는0으로 채우지 않고 미측정으로 남긴다. PID0의 idle 시간은 프로세스
CPU 합산에서 제외하며 host idle 카운터에는 포함한다. 작업 집합 합계의 공유 메모리와
Windows PagefileUsage(commit charge) 의미도 기록한다.

첫 psutil 방식은 개발 PC 약495프로세스에1.5–2.1초가 걸렸다. 제한 조회 방식의 최종
통합 fixture는517–519프로세스에33.5–46.0ms, collector CPU31.25–46.875ms였다.
읽기 불가192–195프로세스가 있어 같은 범위의 단순 속도 비교가 아니다. 관리자 서버의
실제 수집 비용과 접근 범위는 미검증이며, 비용과 누락을 매 표본에 남긴다.
API 근거: [GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes),
[GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo),
[PROCESS_MEMORY_COUNTERS](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters).

`field_host_diagnostic.py`는 기존 observation에 별도 host 수집 자식을 더한다.
기본5초 간격, 최대300초/121표본, 놓친 일정·중단·수집 비용과 파일 해시를 기록한다.
동일 supervisor의 소유 job 안에서만 실행하며 운영 앱을 종료 대상으로 삼지 않는다.
`field_runner.py`의 새 `host-diagnostic` 요청은 정확히300초만 허용한다.
기존 `observe`의900/7200초 조건·후보/설정 핀·실패 판정은 유지한다.
새 진단의 scope는 `HOST_ATTRIBUTION_DIAGNOSTIC_NOT_RELEASE_QA`이며 정식 QA/HOLD와 구분한다.

검증 근거:

- `python -B -m unittest -v test_field_host_sampling test_field_host_diagnostic`: 15검사 exit0.
  Windows 네이티브 조회, 핸들 정리, PID 재사용, 누락/취소, 해시 manifest와 재계산,
  정상/앱 세대 변경5초 fixture를 확인했다. 두 fixture의 소유 프로세스5개는 모두
  active0/강제 종료0, 앱 정상 종료0이며 세대 변경은 observation FAIL/worker exit1을 유지했다.
- `test_field_host_runner` 3검사와 기존 runner의 duration/reference·describe/필수 인수2검사:
  총5검사 exit0. 첫 실행은 시험용 경로가 없어1건 실패했고, 실제 임시 fixture 경로를
  만들도록 시험을 수정한 뒤 통과했다. 전체 제품 health 검사는 제품 코드 변경이 없어 실행하지 않았다.
- `review-host-diagnostic-development.py`는 저장된 원시 표본·manifest·interval 재계산,
  두 fixture의 종료와 잔존 세대 부재를 검토해 exit0이다.
  `host-diagnostic-development-review.json` SHA256은
  `490fc9dda66d5cd6b72d4f78d681c0d3413f127f61da84466424f02bb5ee73da`다.

다음 실행 체크리스트:

1. 확정 소스로 frozen 진단 도우미와 해시 결합 실행 요청을 새 폴더에 준비하고
   소유 job/실패·세대 변경/긴 경로/보호 ACL을 검증한다.
2. 공유 send와 서버 로컬 최종 폴더까지 복사·확인한 뒤 필요한 사용자 실행을 안내한다.
3. 같은 설정·실행 세대에서5분 진단 결과와 실제 CPU/응답 시계열을 회수·대조한다.

현재 새 도우미는 소스·개발 시험 단계이며 frozen 서버 묶음·전달·실행은 아직 하지 않았다.
실패한15분, 120분 미시작, 물리 경계 NOT_TESTED, 정식 QA/출시 HOLD를 유지한다.

### 같은 날 후속: 진단 실행 파일의 개발 검증

위 소스를 clean commit `29e995224b3a4b5528fd9cf999cc2e3bdbd97514`에서 추출한36파일로
빌드했다. PyInstaller exit0, 빌드 전후 소스·의존성·HEAD 일치를 확인했다.
새 helper `field_runner.exe`는16,074,189B, SHA256
`9c9d6c4c7a12bf68c3ac04241f8e9cd52e3fc49f8b6a4747ba21f69b485df804`이다.
제품 후보4cc7393e의 installer/payload는 이 helper 빌드와 별개이며 변경하지 않았다.

개발 위치는 `SmartFactory/PDCA_HOSTDIAG_20261014_29e99522`다.
`HOSTDIAG_20261014_29e99522/RUN128`에 새 manifest·controller·필수 기준 자료를 준비했다.
실행 파일 내부13모듈의 code object와 확정 소스, embedded HTTP/resources 소스를 대조했다.
네이티브 PS5.1의 실제 소유 job에서 describe exit0, 필수 인수 누락 exit1을 확인했다.
두 경우 모두 잔존·강제 종료·launcher 예외0이며 운영자 관리자/ACL 본 실행은 수행하지 않았다.

추가로 같은 소스의 frozen 시험용 entry에서 정상·앱 세대 변경5초 동시 관찰을 실행했다.
정상 actual exit0/PASS, 세대 변경 actual exit1/FAIL을 보존했고 host 수집은 각2표본 완료다.
각 outer8/inner5프로세스는 active0, 강제 종료0이며 fixture 앱도 정상 종료했다.
제품용 실행 파일과 시험용 실행 파일이 공유하는10모듈의 code object가 같고,
시험 사본34소스의 해시도 일치했다. host manifest/interval 재계산과 fixture 잔존 부재를
다시 확인했다. 짧은 합성 시험이며 서버300초·정식15/120분의 통과로 계산하지 않는다.

개발·요청20검사, 휴대 실행2경우, frozen 동시 관찰2경우가 기대 결과를 충족했다.
검토 드라이버 exit0의 `frozen-host-diagnostic-review.json` SHA256은
`a1d6ab4762b8d3b7e5af759d7fb1c0448de4aec75392665017d87d1f484a3455`다.
빌드 경고는 선택적/다른 플랫폼 모듈 및 multiprocessing의 정적 분석 항목이며,
실제 Windows spawn 동작을 위 두 경우로 확인했다.

현재 남은 준비는 서버 세대·설정 핀을 묶는5분 실행 요청/준비 도우미와 그 네이티브
거부 검사, 공유·서버 로컬 전달이다. 아직 사용자 실행을 요청하지 않았다.
서버에 새 진단을 실행하지 않았으며 지연 원인은 UNCONFIRMED, 출시 HOLD다.

### 같은 날 후속: 5분 진단 서버 전달과 실행 안내

`PDCA_HOSTDIAG_20261014_29e99522`에서 준비 도우미와 명령 운반부를 검증했다.
네이티브 PS5.1 준비 검사10건과 운반부7건은 기대 결과를 충족했으며 두 드라이버 exit0이다.
실제 네이티브 PID·생성 시각·실행 파일 조회를 대조했고, 합성 설정 변경·기준 해시 불일치·
포트 소유자 없음/중복·앱 세대 변경·시간 예산 오류·추가 파일·자식 종료 코드를 확인했다.
실제 도우미는 개발 PC의 운영자/관리자 조건을 거부했다. 서버 관리자 ACL 경로의 본 실행을
개발 시험으로 대신하지 않는다. EncodedCommand의 stderr에 기록된 CLIXML은 Write-Host 정보와
완료된 모듈 준비 progress임을 확인했으며, 일반 오류/오류 스트림을 거부하는 검토도 수행했다.

최종 묶음은18파일42,184,813B이며 공유 복사·재대조 exit0이다. 공유와 개발 사본의 모든
상대경로·크기·SHA256이 일치한다. 서버 최장 파일 경로는105자로240자 예산 안이다.
공유 위치는 `Z:\SmartFactory\20261014\send\HOSTDIAG_20261014_29e99522`다.
Chrome 원격 탐색기로 서버 `C:\Users\user\Desktop\SmartFactory\HOSTDIAG_20261014_29e99522`에
복사한 뒤 절대경로, PREP8파일, RUN1288파일, 명령 텍스트와 전달 manifest의 존재를 확인했다.
서버 로컬 해시 검증은 아직 수행하지 않았으며 실행 시작 시 고정 해시 운반부/controller가 확인한다.

실행 명령 `PINNED_HOST_DIAGNOSTIC_COMMAND_29e99522.txt`를 서버 메모장에 열고 사용자에게
전체 본문을 관리자 PS5.1에서 한 번 실행하도록 안내했다. 앱은 Running으로 유지한다.
서버 실행/수집 시작은 아직 관찰하지 않았다. 소스·명령·18파일 목록과 화면 증거는
`PDCA_HOSTDIAG_20261014_29e99522/server-delivery.json`에 연결했으며 SHA256은
`b6add98b18e74071642ad86142cd296c634d5dab59baf71016a8ab21a7087eee`다.
준비 도우미 SHA256은 `689c6f5a2887583a29343ec9a1c6c99a360adadd87876fe78871d20fc527f0db`,
명령 SHA256은 `7ed52de9f7b04c1f88d7f06d91f4cbc808a48769c4366334a86317b1a682b99b`다.

다음 확인 순서는 콘솔의 RESULT_PATH/LAUNCHER_SHA256/LAUNCH_EXIT 확보 → 서버 결과 회수 →
준비·launcher·원시 표본 해시와 CPU/응답 시계열 대조다.5분 진단은 원인 조사이며 기존15분
FAIL을 대체하지 않는다.120분 미시작, 물리 경계 NOT_TESTED, 정식 QA/출시 HOLD를 유지한다.

실행 대기 중 회수용 `review-host-component.py`도 준비했다. 별도로 확인된 manifest 해시를
필수 입력으로 받아 파일 목록/해시, 일정·누락 수, 비용·읽기 불가 수, 원시 CPU 카운터에서
재계산한 interval/summary를 확인한다. 확정 소스의 해시를 검사한 뒤 그 계산 함수를 사용한다.
기존 frozen 정상/세대 변경 결과2건과 해시·추가 파일·변조·잘못된 요약/CPU/출시 판정·
5초 자료의300초 오인 거부7건, 총9검사 exit0이다. 첫 시험의 `host_manifest` 필드 참조 오류는
`manifest_sha256`으로 수정했다. 개발 검사 결과 SHA256은
`164934df5913a6a4c12b94e8eea0daf1684dcafb2f7fb49280f32295264c483f`다.
이는 host 구성요소 검산 준비이며 실제 서버 결과 검토는 미실행이다. 별도 준비/launcher/session
신뢰 연결과 HTTP·앱 세대 대조를 완료해야 하며 근본 원인 확정이나 출시 통과를 반환하지 않는다.

### 같은 날 후속: 실제 5분 진단 FAIL 검산과 탐색기 부하 확인

사용자 실행 후 서버 콘솔에서 `run-42a20723fc0c`, `LAUNCH_EXIT=1`을 확인했다.
준비 `Pbf042b6a`의 SHA256은
`14911f5b3c1b0ac837b8842b32ec8c9d31381fc9cdbf945cfbdef2db1cfdd8e4`,
launcher SHA256은 `74c4bb529b8c611c55d55edeb447282112f29816e81a7dcda5f390e3853cf25f`다.
원격 탐색기로 공유 return 아래 `HOSTDIAG_PREP_Pbf042b6a`와
`HOSTDIAG_run-42a20723fc0c`에 회수하고 개발 PC의 기존 진단 폴더 아래 별도 사본으로 보존했다.
준비4파일6,086B, run2,635파일21,239,737B의 공유·개발 사본 해시가 일치하며 회수 드라이버 exit0이다.
run 회수 영수증 `recovery-run.json` SHA256은
`8deb50dd1e8710df168fd479d6859fadde33306c94f87752ebfa0db2efe72b8b`다.

콘솔 핀→준비/요청→launcher→session manifest2,630파일→원시 HTTP/resources/process/host
자료를 대조했다. 고정 소스로 HTTP·자원·통합 판정·host CPU를 재계산한 검토는 exit0,
`RECORDED_SUMMARIES_REPRODUCED`이며 실제 진단 FAIL을 그대로 재현했다.
검토 도구 준비16검사도 exit0이다. 첫 검사에서300초 자료에 자원 판정 창1개를 기대한
시험 가정을 수정했다. 실제 계약은120초 warmup 뒤300초 창이므로 이 진단의 창은0개다.
자원 성능 NOT_EVALUATED와 정식 QA HOLD는 바꾸지 않았다.

측정은2026-10-14 19:11–19:16 KST의300초다. 같은 main10068/backend10724와 승인된
Low Signal OFF 설정을 전후 확인했다. host61표본/60구간, 자원61표본, 프로세스61표본을
수집했다. HTTP exit1, 나머지 수집기 exit0이다. outer8/inner5프로세스 모두 active0,
강제 종료0이고 이전15분의 `outer-descendants-remain` 경고는 이번에는 발생하지 않았다.
이 사실이 이전 경고 원인의 해결을 뜻하지는 않는다.

| 항목 | 이번 실제 결과 |
| --- | --- |
| 서버 전체 CPU | 구간 평균99.674%, 최소94.136%, 최대100%; 60구간 중59구간이95% 이상 |
| 탐색기 PID9804 | CPU340.141초, 동일 세대 카운터 시간으로 가중한 전체 용량56.580%; 단순 구간 평균56.181% |
| 백신 MsMpEng PID4144 | 전체 용량9.209% |
| 앱5프로세스 | 개별 카운터 비율 합계9.131%; backend3.306%, PID9700 4.060% 포함 |
| 진단 helper 프로세스 | 개별 카운터 비율 합계1.916% |
| health | 148/150요청, 일정 누락2, 200ms 초과43; 최대3503.145ms, p951239.275ms |
| data | 50/50요청, 500ms 초과5; 최대3349.933ms, p95574.838ms |
| image | 817/1200요청, 일정 누락383; 요청 오류/timeout0, 최대3520.005ms |

프로세스별 카운터 시각이 달라 비율 합계는 정확한 host CPU 총합이 아니다. 보호 프로세스
3개의 카운터는 모든 표본에서 읽기 불가였고 전체60구간을 partial로 보존했다.
host capture wall time은 평균688.964ms/최대7149.328ms, 수집 함수 자신의 CPU 시간은
61회 합계0.984375초였다. wall 지연을 수집기의 실제 CPU 사용으로 해석하지 않는다.
측정 중 작업 관리자를 잠시 열었던 관찰자 영향도 기록했다. 미측정 프로세스·스케줄링·
스택 자료가 없어 CPU 포화와 HTTP 지연의 인과관계 및 탐색기 부하 원인은 UNCONFIRMED다.

이미지 저장 카운터는 written7636→7860, failure/drop0→0이다. 끝 경계에서 enqueued7861,
inflight1이었다. 이미지 HTTP 일정 누락383건은 저장 drop이 아니며 이미지 바이트 전수 검증이나
정상 종료 drain 검증으로 확대하지 않는다.

핵심 근거는 `PDCA_HOSTDIAG_20261014_29e99522`의 다음 파일이다.

- `host-diagnostic-production-review.json`: SHA256
  `b61229dabbe60fea2418211157dd64f3f340cec366017596ea8f0dcaec0cb455`, 검토 exit0.
- `host-diagnostic-production-analysis.json`: SHA256
  `748b15ea5dc78c755e391e0ca467d3504defb573ca765b5ac1c3978594bbc685`, 분석 exit0.
  최초 분석은 `in_flight_count`라는 잘못된 키를 거부해 출력 생성 전 exit1이었다.
  실제 필드 `inflight_count`로 수정하고 전체 원시 파일 대조부터 다시 실행했다.
- `host-run-recovered-review-tests-r2/result.json`:16검사, SHA256
  `120cc57ea4a465bcbe088e690ce2b904d6088cad5ccf97783096c6f1ceebe215`.

후속 비교 준비 체크리스트:

1. 복사가 끝난 탐색기 폴더 창과 작업 관리자만 정상적으로 닫는다. explorer 프로세스,
   백신·서비스·운영 앱은 종료하지 않고 설정도 바꾸지 않는다.
2. 같은 검증된 명령으로 새 준비/결과 폴더에300초를 측정한다. 측정 중 탐색기·작업 관리자를
   열거나 파일을 복사하지 않는다. 원격 화면/전후 상태의 차이도 한계로 남긴다.
3. 동일 앱·설정 핀을 먼저 대조한 뒤 CPU 사용 프로세스와 HTTP 지연/누락을 비교한다.
   이 비교가 끝나기 전 탐색기 원인 확정이나15분 재통과를 선언하지 않는다.

19:31경 첫 탐색기 창 종료 후 작업 관리자 순간값40%를 관찰했지만, 이후88%와 백신47.1%,
backend26.9%도 관찰했다. 탐색기는 그 화면에서0%였다. 순간값의 변동만으로 개선을 확정하지
않으며 비교 진단을 준비한다. 원래15분 FAIL, 120분 미시작, 물리 경계 NOT_TESTED,
정식 QA/출시 HOLD와 기존 롤백 기준을 유지한다.

### 같은 날 후속: 탐색기 창을 닫은 5분 비교 결과와 15분 재검증 준비

사용자가 두 번째 실행 완료를 알렸고 콘솔에서 `Pa5cbdd9c`, `run-9c66a5ffdab8`,
`LAUNCH_EXIT=1`을 확인했다. 가려진 창을 옮겨 launcher SHA256
`802e9d917ffea2148915daa4228a554fe1e83a833be1f9128522f511b185c985`를 읽고 회수 파일과
대조했다. 준비 SHA256은 첫 진단과 같은
`14911f5b3c1b0ac837b8842b32ec8c9d31381fc9cdbf945cfbdef2db1cfdd8e4`다. 새 폴더에서도
앱 식별 정보와 설정이 같으면 준비 JSON 바이트는 같을 수 있다. 서로 다른 launcher와 겹치지 않는
후속 측정 구간을 별도로 검증했으며 같은 자료를 두 번 비교한 결과가 아니다.

원격 탐색기로 `Z:\SmartFactory\20261014\return\HOSTCOMP_PREP_1950` 및
`HOSTCOMP_RUN_1950`에 복사했다. 준비 4파일 6,086B, run 3,019파일 25,294,821B의
공유·개발 사본 해시가 일치하며 회수 exit0이다. session manifest의 3,014개 파일을 전수 대조하고
고정 소스로 HTTP·자원·통합 판정·host 카운터를 재계산했다. 비교와 후속 분석 모두 exit0,
`RECORDED_SUMMARIES_REPRODUCED`, replay 오류 0이며 실제 FAIL을 그대로 재현했다.

두 번째 구간은 2026-10-14 19:44:02–19:49:02 KST다. 측정 중 탐색기·작업 관리자를
열거나 파일을 복사하지 않았다. 앱 버전·설정·main/backend 세대·SPOT 서비스와 제품 60580/금형 1이
동일하고 Low Signal OFF를 유지했다. 50개 data 표본 모두 Running/작업 정보 유효다.
압출/정지 표본 수는 첫 측정 42/8에서 두 번째 41/9, 평균 속도는 2.472에서 2.356,
평균 압력은 105.266에서 108.410으로 달라 통제된 부하 비교는 아니다.

| 항목 | 첫 5분 | 탐색기 창을 닫은 후 5분 |
| --- | ---: | ---: |
| 전체 CPU 구간 평균 | 99.674% | 75.146% |
| 탐색기 PID9804 가중 CPU | 56.580% | 11.909% |
| health 최대 / p95 | 3503.145 / 1239.275ms | 260.387 / 96.543ms |
| health 200ms 초과 / 일정 누락 | 43 / 2 | 2 / 0 |
| data 최대 / 500ms 초과 | 3349.933ms / 5 | 88.811ms / 0 |
| image 최대 / 일정 누락 | 3520.005ms / 383 | 243.243ms / 1 |
| HTTP 요청 오류 / timeout | 0 / 0 | 0 / 0 |

두 번째 host 61표본/60구간과 앱 자원·프로세스 표본은 완전 수집됐다. 보호 프로세스 카운터를
읽지 못한 부분은 계속 partial이며 0 사용으로 계산하지 않는다. 백신 가중 CPU 12.794%,
backend 12.628%, 앱 5프로세스의 개별 비율 합계 23.777%다. 카운터 시각이 달라 프로세스별
비율 합계는 정확한 host 총합이 아니다. host 수집 함수 CPU는 61회 합계 0.796875초,
capture wall time 평균 154.374ms/최대 626.213ms다. 관찰자 부하·생산 상태·다른 프로세스
변동과 스케줄링 자료 부족 때문에 탐색기 단독 원인 또는 완전 해결을 확정하지 않는다.

남은 health 실패는 sequence52(19:45:46.933, 206.096ms,
trace `7b47fa0d-b725-4fef-ad6f-3f0208c7da55`)와 sequence65(19:46:12.938, 260.387ms,
trace `51f7f371-cfcc-4461-9f3c-5a67f3d6254f`)다. 모두 HTTP200이며 응답 헤더 대기 시간이
각각 203.899/258.421ms다. 전후 경계 health는 14.880/7.743ms이고 경계 포함 최대도 260.387ms다.
같은 시각 image520의 243.243ms 요청이 다음 예정 시각을 넘어 image521이
`previous-request-decode-or-enqueue-overrun`으로 누락됐다. 이 동시 발생만으로 원인을 확정하지 않는다.

이미지 저장 카운터 written9348→9626, failure/drop0→0, 마지막 queue/inflight0/0이다.
초기 queue8/inflight1이 있어 written 증가량을 이 구간의 신규 생성 수와 동일시하지 않는다.
조회 일정 누락은 저장 drop이 아니며 이미지 바이트 전수 QA나 정상 종료 drain 통과도 아니다.
outer8프로세스 active0/강제 종료0/errors0이며 이전15분 정리 경고는 이번에도 재현되지 않았다.

설치된 정확한 commit `4cc7393e1bafbf90a329726aed9470fe0daacb21`의 `backend/app.py`를
확인했다. health 단계별 경고 기준은 500ms이고 성공 `/health` 접근 완료 로그는 생략한다.
따라서 이 두 206/260ms 요청의 단계별 trace가 기존 로그에 있을 것이라고 가정할 수 없다.
로그가 없다는 사실을 서버 내부 지연이 없었다는 증거로 쓰지 않는다. 코드 변경은 하지 않았다.

주요 증거는 개발 PC `PDCA_HOSTDIAG_20261014_29e99522` 아래에 보존한다.

- `comparison-recovery-run.json`: `85c0c52d5a3542d9fbfc8105b70b07b82ebeedaed7d43b52767a53f6e3c510d7`.
- `host-diagnostic-comparison.json`: `4eed66f8aaf02b3544fbc8a9bd0fd1b756660e30e83ffcddedf136ca7371f965`.
- `host-comparison-followup-analysis.json`: `42ea89436bd78f31846ba943bd936654f60423436be0e99a859d17c513132979`.
- `host-comparison-tests-r2.json`: 16검사 exit0,
  `31e3d247f5f1500344d9e6c516f04f9ce41b4ad1b8af029722927e678d80824c`.
- `comparison-logging-coverage.json`: `fb098f8d7b23a9cf4aa5afa23f6e77ff20926c6557c49eca83f50149f9c9f0ad`.
- `host-comparison-result-record.json`: 기록·상태 연결 검산 exit0,
  `6ebc697dcf73d878a347826ca21e3df0718791bc918fec79eb97a762fae6761e`.

다음 단계는 조건 변경 후 정식900초 재검증이다. 추가 host 프로세스 수집기가 없는 기존
`observe` 도구로 같은 기준을 확인한다. 서버의 기존
`C:\Users\user\Desktop\SmartFactory\PINNED_FIELD_OBSERVE15_COMMAND_0dd2ced0_R2.txt`를
메모장에 다시 열고 탐색기 창을 닫았다. 명령 SHA256은
`515ad2e0e71e2f436147310cd4bb6516d8608f32709d21b1bdb7d304e2180f60`으로 기존 전달본과 같다.
원래 도우미가 실행마다 새 준비/run 폴더를 만들고 앱·설정·도우미 핀을 확인한다. 설치본 재빌드,
설정 변경, 판정 기준 완화 없이 사용자 실행만 대기한다. 900초 재검증은 아직 실행하지 않았다.

후속 실행 체크리스트:

1. Running 유지, Low Signal OFF 유지, 탐색기·작업 관리자 닫힘, 측정 중 파일 복사 없음.
2. 메모장의 `$observeBundle=` 본문 전체를 관리자 Windows PowerShell5.1에서 한 번 실행한다.
3. 새 PREPARATION_PATH/SHA256 및 RESULT_PATH/LAUNCHER_SHA256/LAUNCH_EXIT를 확인하고 회수한다.
4. 기존15분 FAIL을 보존한 채 새 결과를 검산한다. 120분 미시작, 물리 NOT_TESTED,
   정식 QA/출시 HOLD 및 기존 롤백 기준은 새 검산 전까지 유지한다.


### 같은 날 후속: 탐색기 창을 닫은 정식 15분 재관찰 FAIL

사용자 실행 후 새 준비 `Pa723f319`와 `run-d86a587e6803`를 확인했다. 실제 관찰은
20:21:31경–20:36:31경 KST의900초이며,20:38 화면에서 `LAUNCH_EXIT=1`과 프롬프트 복귀를
확인했다. 준비 SHA256은 기존 `091746d11e1d2c7722c9c35f38945db8ab81f410af14efe54e03ecc1ee3ac31f`,
launcher SHA256은 `67188c36070463bb127e7c2d03e5b2d4c3d6a0270b50535b2c224912cfda5ed1`이다.
콘솔의36번째 글자6을f로 옮겨 적은 첫 회수 시도는 해시 불일치 exit1로 복사 전 중단됐다.
콘솔을 다시 읽어 별도 `observe15-recheck-console-r2.json`에 정정했고 원 기록·도우미를 보존했다.

측정 중 Codex는 수동 화면 확인만 했으며 탐색기·작업 관리자·파일 복사를 사용하지 않았다.
두 화면 사이 PowerShell 창 위치가 바뀐 사실은 기록한다. 추가 host 수집기가 없는 기존
observe 도구와 기존 판정 기준을 유지했다. 같은 후보4cc7393e/installer8821746b·설정·
main/backend 세대·SPOT/logger, 동일 request와 겹치지 않는900초 구간을 확인했다.
두 구간150개 data 표본 모두 제품60580/금형1·Running·작업 정보 유효·Low Signal OFF다.
압출/정지/unknown은128/19/3→133/17/0, 평균 속도2.551→2.572,
평균 압력112.741→114.489로 달라 통제된 부하 비교가 아니다.

| 항목 | 첫15분 | 이번15분 |
| --- | ---: | ---: |
| health 최대 / p95 | 3189.366 / 1270.119ms | 203.136 / 72.536ms |
| health200ms 초과 / 일정 누락 | 134 / 5 | 1 / 0 |
| data 최대 / 500ms 초과 | 2342.922ms / 21 | 148.480ms / 0 |
| image 조회 / 예정 | 2441 / 3600 | 3596 / 3600 |
| image 일정 누락 | 1159 | 4 |
| HTTP 요청 오류 / timeout | 1 / 0 | 0 / 0 |

이번health450/450, data150/150이며health142는20:26:15.221에203.1356ms,
trace `50251a77-1490-4cb8-bc03-89de8b10a24d`다. 헤더 대기200.810ms가 대부분이고
첫 경계health7.1272ms, 경계 포함452요청 최대도203.1356ms다. 기준 초과를 반올림으로 숨기지 않는다.
image720/2344/2571/3045는 직전 응답이 다음 예정 시각을 넘겼다. 직전 요청 시간은
336.125/264.606/260.459/273.835ms, 응답 header의 refresh 시간은31/47/250/265ms다.
정확한 후보 소스의 header는 cache entry의 refresh coroutine 구간값이며 전체 client 시간이나
순수 장비/네트워크 시간은 아니다. upstream/coalesced와 시간 차이는 보존하지만 서버 처리·
event-loop/lock 대기·client scheduling의 원인을 분리했다고 주장하지 않는다.

자원·프로세스181표본, 자원300초 창3개의61표본 및 coverage를 재계산했다. 앱 프로세스 CPU
개별 비율 합의 평균18.762%/최대26.656%이며 host 총 CPU가 아니다. 자원 성능 gate는
NOT_EVALUATED다. 이미지enqueued/written11408→12210, failure/drop0→0,
전후queue/inflight0/0이다. 조회 누락4건은 이미지 저장 drop이 아니며 전수 이미지 QA나 종료 drain 통과도 아니다.
outer7프로세스의active1→0, 강제 종료0, `outer-descendants-remain`이 다시 기록됐다.
남은 프로세스 식별 정보가 없어 원인은 미확정이다. HTTP child1/자원0/프로세스0이고
관찰worker 오류0이며 실제 앱의 정상 종료를 수행한 기록은 아니다.

서버 탐색기를 통해 `Z:/SmartFactory/20261014/return/OBS15_RECHECK_PREP_Pa723f319`와
`OBS15_RECHECK_RUN_d86a587e6803`에 회수했다. 준비4파일6064B, run8792파일48,114,678B의
공유 전후·개발 사본 해시가 일치한다. session manifest8787파일을 전수 검산하고 고정 소스로
HTTP·자원·통합 판정을 재계산했다. 회수·재계산·상세 분석·사건 비교 모두 실제exit0,
replay 오류0, `RECORDED_SUMMARIES_REPRODUCED`이며 실제 관찰의FAIL을 재현했다.

- 재계산: `observe15-recheck-replay.json`, SHA256 `f4129b718f266755eafbf88ffafa9e8fb870e216d0e2d1878e3fd80fd6899a3a`.
- 상세 분석: `observe15-recheck-analysis.json`, SHA256 `e9c24523b08421e9db68b0d67729a3c077be51b5c94c835d96d07899bffae350`.
- 사건·조건 비교: `observe15-recheck-event-comparison.json`, SHA256 `c0cf170aa2de2574e18b862bbaec3273f2d3254ad3cdc28c4b73bb3ab45e3456`.
- 전체 기록: `observe15-recheck-result-record.json`, SHA256 `8eb7c7a9224d92f0abe1befb3317478f1769e13e80b6703bf42bb22304e09a9e`.

위 파일은 개발 PC `PDCA_LIMITED_FIELD_20261014_0dd2ced0` 아래에 보존한다.
다음 조치는 남은 요청의 backend 실행/대기와 client scheduling을 분리하고 outer job의
잔여 프로세스 식별을 남길 계측 준비다. 같은15분 반복으로 통과를 찾거나 기준을 완화하지 않는다.
독립적인 전체 데이터 QA를 계속하며120분은 미시작, 물리NOT_TESTED, 정식QA/출시HOLD,
운영 승격·롤백 기준 갱신 미실행을 유지한다. 제품 코드·설치본·설정은 변경하지 않았다.

21:16 KST 화면에서는 작업 정보가 다시필수값 미입력이고 최근 적용 시각이20:52:06으로
바뀌었다. 이는 관찰 종료 후의 상태이며 이번150개 유효 표본을 소급 무효화하지 않는다.
현재 실제 제품·금형 번호를 사용자에게 요청했으며 이전60580·1을 임의 재적용하지 않았다.
현재 상태 증거는 `observe15-recheck-after-recovery.png`다.

후속 계측 후보로 WPR/ETW를 조사했다. [Microsoft 명령 참조](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options)와
[대기 분석 안내](https://learn.microsoft.com/en-us/troubleshoot/windows-server/support-tools/support-tools-xperf-wpa-wpr)를
확인했고 개발 PC의 `wpr -profiles` 및 `wpr -profiledetails CPU`는exit0이다.
개발 PC CPU.Verbose.Memory의CSwitch/ReadyThread 제공을 확인했으나 기본system buffer가
1024KB×1630개이므로 이 설정을 서버에 그대로 사용하지 않는다. 서버 지원·자원 예산·
계측 부하·event loss·시각 정렬과 Python 단계 계측 보완은 미검증이며 trace를 시작하지 않았다.
`observe15-recheck-next-timing-options.json`에 기술 준비 조건을 남겼다.


## 2026-10-14 닫힌 백업의 추가 이미지 본문 검증 완료

추가 이미지 94,022개/916,112,088B의 회수·본문 검산을 실제 exit 0으로 완료했다.
대상은 이전 운영 build541d가 정상 종료한 `Q3d9da3` 사본이며 현재 후보 실행 중 생성된
이미지는 포함하지 않는다. 최종 서버 manifest SHA256은
`ab637280383d38777649310f00cd586a80e7f74e0cf159d9535a1d170287f393`이다.

서버 탐색기의 ZIP/Store로 닫힌 사본 `c/r0/logs/test_data/spot_images/2026/10` 아래
12·13·14일 폴더를 새 반환 위치에 묶었다. 반환 경로는
`Z:/SmartFactory/20261014/return/CLOSED_IMAGES_Q3d9da3_b14a7744/spot_images_12_14.zip`이다.
109,542파일/3폴더/1,065,522,110B이며 날짜 폴더 회수에 기존 검증분 15,520개도 포함됐다.
서버 화면에서 완료·파일 존재를 확인하고 탐색기를 닫았다. 이때 성능 측정은 실행하지 않았다.
ZIP은 1,092,689,038B, SHA256 `98bf58e33467bb227d4a24cfb62b39307c7f476c37f9495f0397718f630aa751`이며,
공유/개발 사본의 전후 해시가 일치했고 모든 member의 경로·EOF/CRC·크기·SHA256을 최종 manifest와 대조했다.
ZIP 컨테이너 해시를 서버 콘솔에서 검증한 것은 아니며 NTFS 추가 스트림 증거를 대신하지 않는다.

기존 312,985개 검사 기록의 SHA256과 이전 완료 증거를 고정해 현재 목록과 대조했다.
현재 사본의 230,171개는 경로·크기·해시가 동일해 기존 decode 결과를 연결했다.
새 94,022개는 이미 검증된 같은 SPOT service의 수집·관측 대장 연결과 이번 실물 해시를 결합했다.
회수 ZIP의 고유 내용 94,022개를 새로 전체 프레임 load/verify했고,
15,520개의 동일 내용에는 기존 decode 증거를 재사용했다.
따라서 현재 닫힌 사본 이미지 324,193개/3,178,166,328B의 본문·decode 근거가 모두 연결됐다.
이전 목록에 있으나 현재 목록에 없는 82,814개는 별도 차이로 남기며 삭제 원인을 확정하지 않는다.
과거 미참조 16개·누락 참조·drop173·CSV 이력의 원인/영향/처리 완료를 뜻하지 않는다.

개발 증거는 `C:/Users/user/Desktop/SmartFactory/PDCA_CLOSED_IMAGES_20261014_b14a7744`다.
새 날짜 선택/기존 증거 연결의 오류 탐지 7검사는 exit 0이며, 기존 고정 ZIP/decoder 함수를 재사용했다.
회수·검토 세션 84976의 실제 exit 0과 각 파일·수량·결합 기록을 확인했다.
`summary.json` SHA256 `86c73296057c50e25debb7cec471b9fdc12ce6afae9632275e1fe120d5673e57`,
`completion-record.json` SHA256 `92321d613404a8447eb7a596d2129cdf182dbb779216e5af945cda31239b6b66`에 최종 근거를 보존했다.

사용자가 현재 제품·금형을 `60345, 1`로 확인했다. 서버의 21:30:09 적용값과 일치하고
작업 정보 OK를 화면에서 확인했다. Codex가 값을 입력하거나 적용하지 않았다.
이전 21:16 미입력 기록은 당시 증거로 유지하며, 후속 현재 작업 정보 조건은 해소됐다.

제품 코드·설치본·설정은 변경하지 않았다. 15분 FAIL/잔여 타이밍·outer cleanup 원인 미확정,
120분 미시작, 물리 NOT_TESTED, full_data NOT_EVALUATED, 정식 QA/출시 HOLD를 유지한다.
다음 성능 시험 전에는 같은 반복으로 통과를 찾지 않고 지연 구간과 잔여 owned 프로세스의
식별을 남기는 계측을 준비한다. 후보 종료 후 생성 자료의 전수 QA는 별도로 남는다.


## 2026-10-14 outer job 잔여 프로세스의 로컬 재현과 식별 계측

기존 도우미 바이트(SHA256 `ab3c98d2611fe5d0c75056e194bf0f26c107dc137a78f93588ce3777387480c8`)로
정상 종료만 하는 Python을 30회 실행했다. 실제 root exit는 모두0이지만29회에서
`outer-descendants-remain`,28회에서 owned job 종료 요청이 기록됐고 최종active는 모두0이었다.
별도 직접 관찰100회도 root 종료 신호 뒤active1을 읽었으며 추가 관찰 중 모두0으로 바뀌었다.
이 단계만으로 실제 남은 프로세스가 없었다거나 서버 경고가 오탐이라고 판단하지 않았다.

읽기 전용 프로세스 식별 계측을 추가한 사본에서 base Python과 venv Python을 각각100회 관찰했다.
각99회, 총198회에서 명시적 owned job membership·생성 시각·실행 경로와 함께
`C:\Windows\System32\conhost.exe`의 아직 종료되지 않은 상태를 확인했다.
200회 모두 강제 종료 없이 정리됐지만 일부 조회는 종료 경합으로 실패했다.
초기 진단 사본의 실패한 API 필드 기본0을 종료 증거로 해석하지 않았으며 해당 원문을 보존했다.
따라서 로컬 재현에는 일시적으로 살아 있는 console 보조 프로세스가 관여한다.
서버의 미식별 잔여 PID가 같은 프로세스였는지, HTTP 지연과 관련이 있는지는 **미확정**이다.

새 `invoke-field-run.template.ps1`은 suspended root의 실제 경로·생성 시각을 먼저 고정하고,
종료/오류 정리 직전에 owned job PID 목록과 handle 기반 membership·종료 신호·exit를 기록한다.
최대1024 PID, 조회 실패/목록 불완전은PARTIAL, 알 수 없는 필드는null이며 관찰은 원자적 snapshot이 아니다.
원래accounting과 실패 판정·시간 제한·owned job 종료·kill-on-close를 유지했다.
진단 오류가 정리를 건너뛰게 하지 않으며 일반 프로세스 이름으로 종료하지 않는다.
새 관찰값은 추가 진단 필드이며 이전 서버 결과의 판정을 바꾸지 않는다.

PowerShell5.1 x64 네이티브14조건 검사와 변경 테스트 파일의 Ruff F/E9는 실제exit0이다.
살아 있는 orphan·timeout child, supervisor 종료, 무관한 프로세스 보존, 진단 호출 실패,
출력 원문/경로 검산 및 빠른 종료30회에서 기존 실패 판정 보존을 확인했다.
추가30회에서는 경고30회/강제 정리28회가 남았으며 이를 수정 완료로 표시하지 않는다.
제품 소스 변경이 없어 전체 앱 health·installer 재빌드·새 현장 시험은 실행하지 않았다.

개발 기록: `C:/Users/user/Desktop/SmartFactory/PDCA_OUTER_JOB_20261014_09c971c5`.
`analysis.json` SHA256 `b3ec626eca5bf2802f59b55f464f635d25426efdfff2c17e3bc39b481814b2a3`,
`evidence-manifest.json` SHA256 `68ec971203b15da20217bdebf7c054311d3050ec0a37b7eda6c5858c211c3616`.
새 도우미 source SHA256은 `163d4d04938e341200bdfa68b2c632752191aa2f30280f410740acfe891bfc18`이다.
기존 서버 묶음은 보존했으며 새 도우미의 서버 전달·실행은 아직 하지 않았다.
차기 묶음의 실제 portable 검증과 지연 구간 계측의 부하·손실·시각 정렬 확인이 남는다.
15분FAIL,120분미시작,물리NOT_TESTED,full_data NOT_EVALUATED,출시HOLD를 유지한다.

API 해석 근거: [Microsoft job accounting](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information),
[PID 목록](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list),
[명시적 job membership](https://learn.microsoft.com/en-us/windows/win32/api/jobapi/nf-jobapi-isprocessinjob).
accounting의 종료 참조 영향은 가능한 해석이며 이번 실제 conhost 식별을 대신하는 원인 확정이 아니다.


## 2026-10-14 요청 스레드·QPC 연결 계측과 제한된 부하 비교

설치 후보의 `/health`는 payload 내부 시간이500ms 이상일 때만 구간 로그를 남긴다.
성공한 health의 access 완료 로그도 생략하므로203.1356ms 사건의 서버 구간은 기존 로그로
분해할 수 없다. 서버 처리·client 실행 대기·Python lock/GIL의 원인은 계속미확정이다.

`field_native_timing.py`와 HTTP 수집기에 자기 PID/TID·생성 FILETIME·QPC 주파수와
요청 전후 시계 대조 범위·thread CPU counter를 추가했다. PID/TID 재사용, 생성 시각/주파수
변경, 역전·불일치 시계는 연결 불가로 남긴다. 알 수 없는 native 값은UNAVAILABLE이며,
원시 응답과 기존 시간/실패 판정은 보존한다. 비교용 OFF는 native API를 호출하지 않는다.
body 완료 시각은 기존 방식으로 측정하고, decoder 이전 경계에서 native 종료 표본을 읽는다.
초기 identity 조회 비용을 첫 요청의 connect 구간에서 제외하지 않았다.
생성 FILETIME과 QPC는 정수로 보존하며 소수점 변환으로 다른 프로세스 세대를 합치지 않는다.

네이티브 clock/identity7검사와 HTTP·resource·인증·설정·관찰105회귀 검사는 실제exit0이다.
Ruff F/E9도exit0이다. 진단 실패 시 원시 body/200ms 위반을 보존하고, 인증 token 비노출,
첫 실패 포함, 일정 누락·정상 종료/세대·설정 조건이 유지되는지 확인했다.

첫 부하 비교는 회귀 검사와 겹쳐CONFOUNDED로 별도 기록하고 원문을 보존했다.
그 결과를 계측 부하의 근거로 쓰지 않고, 회귀 종료 확인 후 새 사본에서
OFF→ON→ON→OFF 각15초의 합성 loopback 비교를 수행했다. 총284요청,ON142요청의
시계·identity 연결을 독립 검산했고4개 manifest/580파일의 크기·SHA256이 일치했다.
정식15분 시험이 아니며 실제 앱·장비·WPR 추적은 포함하지 않는다.

| 전체 client 응답 평균(ms) | OFF | ON | ON−OFF |
| --- | ---: | ---: | ---: |
| health(각16표본) | 2.066519 | 1.906988 | −0.159531 |
| data(각6표본) | 2.288400 | 4.788283 | +2.499883 |
| image(각120표본) | 2.215642 | 3.243265 | +1.027623 |

단기 표본은 변동을 포함하며 무부하 또는 영향 없음의 증거가 아니다. 개별 native capture
2,000회 중앙값1.6µs/p99 2.9µs와 실제 HTTP 차이를 혼동하지 않는다. ON 요청의 경계
시계 대조 폭은 최대118,300ns였다. CPU delta142개 중136개가0, 최대15,625,000ns로
관찰됐으므로 wall−CPU를 서버 대기나 scheduler 지연으로 이름 붙이지 않는다.
이 값은 추후 OS 사건과 연결할 근거이며 인과 설명 자체가 아니다.

WPR의 CSwitch/ProcessThread/ReadyThread/ThreadPriority만 켜는 Memory 프로파일을 준비하고
개발 PC `wpr -profiledetails` exit0으로64KiB×256의 명목16MiB 설정을 확인했다.
실제 할당량·보존 범위·event loss·trace parsing·ON/OFF 부하는 아직 확인하지 않았다.
현재 개발 프로세스는 일반 권한이며 실제 추적에는 적절한 실행 권한이 필요하다.
고유 instance 소유권·시간 제한·정상/오류/중단 정리 도우미를 완성·시험한 뒤 실행 단계를 준비한다.
다른 세션을 stop/cancel하지 않으며 이번 차례에는 추적을 시작하지 않았다.

증거: `C:/Users/user/Desktop/SmartFactory/PDCA_REQUEST_TIMING_20261014_c09c2e46`.
`readiness.json` SHA256 `37b4c634e097d8ab71614795917ccdc0c52b7ac9dda12eac78cb74c4ace181e4`.
새 portable 묶음 검증·서버 전달/실행과 backend 요청 내부의 추가 식별 필요성은 남는다.
제품 소스·설치본은 바꾸지 않아 전체 앱 health/build를 반복하지 않았다.
15분FAIL,120분미시작,물리NOT_TESTED,full_data NOT_EVALUATED,출시HOLD를 유지한다.

근거 문서: [Python 시계](https://docs.python.org/3.12/library/time.html#time.perf_counter),
[Windows QPC](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps),
[thread time](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getthreadtimes),
[WPR 명령·instance](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options),
[버퍼 설정](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/buffers).


## 2026-10-14 로컬 WPR 추적 제어·복구 도우미 준비

현재 작업 정보60345/1은 사용자 답변 및 기존21:30:09 화면 적용 기록으로 유지한다.
완료된15분 측정60580/1의 당시 기록은 변경하지 않는다. 새 현장 작업 전에는 live 값을 재확인한다.

추적 제어기를 고유 `SFLTrace_<GUID>` instance로 한정했다. 모든 WPR 명령의 마지막에
같은 `-instancename`을 붙이며 default/다른 세션은 stop/cancel하지 않는다.
Guard는 부모 PID+생성 FILETIME을 검증한 프로세스 handle을 보유하고, 정상 요청·부모 종료·
8초 감시 제한 때 저장/정리를 수행한다.8초는 전체 프로그램 실행 제한이 아니다.
개별 start/status/cancel20초, stop60초, 해당 명령 job 정리10초의 별도 제한이 있다.
명령 root와 소유 job 전체가 원래 제한 안에 종료됐는지 함께 기다린다.
기존 현장 runner의 즉시 descendants 판정은 변경하지 않았다.

WPR start 전 ABSENT 관찰과 lease/manifest/Guard 세대를 durable intent에 기록한다.
동시 Guard/Recover는 열린 배타적 lock으로 막는다. Guard 소멸 후의 복구는 같은 lease,
manifest, instance와 Guard 세대 부재를 확인한 경우만 허용한다. stop나 로그 기록 실패가
발생해도 상태 재조회·해당 instance cancel을 독립적으로 시도하고 원래 FAIL을 보존한다.
결과/ETL은 새 파일로 보존한다. PID 재사용을 다른 프로세스 종료로 처리하지 않는다.

모의 lifecycle14조건과 PS5.1 네이티브7 suite는 실제exit0이다. 정상/부모 종료/제한,
미확인·기존 세션 불변, 시작/저장/상태/기록 콜백 실패, 복구 소유권, 정확한 프로세스 세대,
실제 자식의 지연 종료/timeout 정리/exit7/없는 실행 파일/무관 프로세스 보존을 확인했다.
변경 테스트의 Ruff F/E9 exit0이다. 최종 묶음 PS5.1 parse exit0,
일반 권한의 내부 실행 exit1과 틀린 외부 SHA의 exit1은 기대한 선행 조건 거부다.
실제 WPR 읽기 전용 status는 exit0, ABSENT, 명령 job active0으로 끝났다.
WPR status exit0만으로 녹화 중이라고 판단하지 않는다.

`package-r2`와 `PINNED_LOCAL_TRACE_COMMAND_2d99c972_R2.txt`를 준비했다.
첫 생성 명령의 Python 경로 escape 오류는 실행/전달 전에 검출했으며 R1은 NOT_FOR_EXECUTION이다.
묶음 manifest SHA256: `6fd9771885eb853f34bf2b5b0974cd499a7229e9eaded5b04ad931d0b9e72e04`.
controller SHA256: `34767aca04d274346619d664cf799f7356291c1a26461e59fa757173a702d7fb`.
suite SHA256: `14c3cbf189d87af5afca04a6c3c8079a191da0ba8e54fd045c09fe0443558966`.
증거 위치: `C:/Users/user/Desktop/SmartFactory/PDCA_TRACE_CONTROL_20261014_2d99c972`.

실제 개발 프로세스는 일반 권한이며 상위 job에 속해 있다. Guard가 제어 창과 함께 제거될
환경을 수용하지 않도록 실제 실행은 Codex/IDE 밖의 관리자 PS5.1을 요구한다.
사용자 실행 단계는 개발 PC에서 정상 종료→제어 프로세스 종료→감시 제한3조건을 자동 검사한다.
직전 조건 실패 시 다음 조건은 시작하지 않는다. 별도 세션 복구가 필요하면 기록을 먼저 검산한다.
실제 elevated WPR lifecycle, parser의 ACTIVE 형식, ETL decoding/loss/coverage 및 부하,
portable 서버 전달/실행은 아직 미검증이다. 이 준비를 현장 QA PASS로 해석하지 않는다.
제품/설치본 변경이 없어 전체 앱 health/build는 실행하지 않았다.
15분FAIL,120분미시작,물리NOT_TESTED,full_data NOT_EVALUATED,출시HOLD를 유지한다.

근거: [WPR 명령과 instance](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options),
[ETW 세션](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/sessions),
[Start-Process](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/start-process?view=powershell-5.1).


## 2026-10-14 tracerpt 원시 사건·손실 판독 사전 검증

이전 차례는 고유 WPR Guard와 실행 묶음을 구현·검증한 PROGRESS였다.
이번 차례 시작/후속 확인에서 해당 묶음의 새 TS/T 결과 폴더 및 일치하는 PowerShell
프로세스를 찾지 못했다. 실제 live handle을 확인한 대기가 아니며 사용자 실행 질문은 유지한다.
기존 제조사 문의 thread는 SENT1건이며 수신 답장은 없었다. 재발송하지 않았다.

관리자 실행에 의존하지 않는 공개 ETL 판독으로 다음 단계를 검증했다.
Microsoft PerfView commit `10e5d271cebcdf5d6cf122c6ab9c863860a7a2f1`의 작은 시험 ETL2개와
MIT LICENSE를 받아 Git blob 식별값·크기·SHA256을 확인했다. 이 파일은 서버 증거가 아니다.
Windows tracerpt로 각각 원시 `-rts` XML과 별도 report XML을 출력했다. 실제4명령 exit0,
명령 소유 job active0과 원문 결과를 보존했다. `-rts`와 report/summary는 같은 실행에 섞지 않는다.

| 공개 fixture | 원시/보고 사건 수 | ProcessingErrorData | 손실 선언 | 판독 품질 |
| --- | ---: | ---: | --- | --- |
| SelfDescribingSingleEvent | 23/23 | 3 | 0 | INCOMPLETE_OR_UNUSABLE |
| gcevents | 71/71 | 1 | 0 | INCOMPLETE_OR_UNUSABLE |

두 결과 모두 opcode80 오류15005와 미해독 BinaryEventData가 있다. 첫 시험에서 빈 Provider를
필수 GUID로 처리해 전체 판독이 중단된 문제를 수정했다. 빈 Provider와 binary payload를
알 수 없는 값/미해독 사건으로 세어 보존하며, 무시하거나 정상 해독으로 간주하지 않는다.
오류 없는 mock만으로 완료하지 않고 실제2 ETL의 사건 수·오류 수·원시 정수 보존을 대조했다.

`field_trace_quality.py`는 같은 ETL에 묶인 두 명령과 raw/report XML을 외부 receipt SHA 및
read-share-only file handle로 검산한다. 실제 command exit/종료 정리, `-rts`와 입력 경로,
event/header clock·종료 시각·손실·report 개수/skip·개별 해독 오류를 검사한다.
시각은 정수로 보존하며 UTF-8/16/32 DTD/entity, 중복 필드, overflow, 입력/사건 예산,
바뀐 파일·receipt·입력 경로를 거부한다. 실제CSwitch/ReadyThread payload·프로세스/스레드 세대
연결·요청 QPC 범위·circular overwrite 여부는 아직 미검증이다. 손실0은 전체 범위 증명이 아니다.

12회귀 검사 및 변경2파일 Ruff F/E9는 실제exit0이다. 공개 ETL 검사 CLI도 각각exit0이지만,
이 값은 검사가 끝났다는 뜻이며 결과 품질 또는 현장 QA PASS가 아니다.
사용 예: `python scripts/field-v1028/field_trace_quality.py --receipt <입력 영수증.json>
--receipt-sha256 <영수증 SHA256> --output <새 결과.json>`.
검증/공개 원문: `C:/Users/user/Desktop/SmartFactory/PDCA_TRACE_DECODE_20261014_20b4649c`.
`public-quality-verification-r2.json` SHA256 `687a466bff95f64e869efb27e114d00da7f2f14465b1954c7c9836858d48319a`.

기존 로컬 WPR 실행 묶음의 바이트는 바꾸지 않았으며, 사용자 실행 요청은 반복하지 않았다.
제품/설치본 변경이 없어 전체 health/build·서버 적용은 수행하지 않았다.
15분FAIL,120분미시작,물리NOT_TESTED,full_data NOT_EVALUATED,출시HOLD를 유지한다.

근거: [tracerpt](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/tracerpt),
[trace header](https://learn.microsoft.com/en-us/windows/win32/etw/trace-logfile-header),
[thread 사건](https://learn.microsoft.com/en-us/windows/win32/etw/thread-v2),
[ReadyThread](https://learn.microsoft.com/en-us/windows/win32/etw/readythread),
[공개 fixture 출처](https://github.com/microsoft/perfview/tree/10e5d271cebcdf5d6cf122c6ab9c863860a7a2f1/src/TraceEvent/TraceEvent.Tests/inputs).


## 2026-10-15 로컬 추적 실행 오류 확인

사용자의 완료 답변 뒤 개발 PC `DESKTOP-SS5CURC`의 Windows 실행 기록을 확인했다.
R2 suite를 실행한 PID99316의 PowerShell engine 시작은00:19:02.806KST,
종료는00:19:03.974KST다. Operational event4100(record7751360)에
“시스템 오류입니다.”가 남았으나 숫자 오류 코드·실패 줄·실제 LAUNCH_EXIT는 없다.
원인은 미확정이다. 시작 전 중단은 추정이며 정확한 실패 단계로 확정하지 않는다.

실제 사용자 바탕화면 SmartFactory에서 예상 TS/T 결과 폴더를 찾지 못했다.
대체 사용자/Public/OneDrive/systemprofile 경로도 확인했으며 대상 SmartFactory가 없었다.
manifest·suite·controller·native helper·WPR profile5파일의 크기/SHA256은 준비 당시와 같다.
같은15초 범위 AppLocker/MSI and Script·CodeIntegrity·Defender 로그에는 사건이 없었다.
이 제한된 검색으로 모든 보안 제한의 부재나 추적 세션 정리 완료를 증명하지 않는다.

증거는 `C:/Users/user/Desktop/SmartFactory/PDCA_TRACE_RUN_REVIEW_20261015_7fbe670b`의
`execution-review.json`(SHA256 `dc5d41d85ecc1998c69df6d241c3c4d08e2a944845f45d95bab3ee5cbcd019ee`)과
`operational-error-review.json`(SHA256 `95d872438f375c121474c9b97acb83274143d9fde6001b542075e469a1393195`)이다.
앞선 차례는 실행 확인, 이번 차례는 실제 engine 오류 확보로 PROGRESS다.
열린 대화형 PowerShell 창은 시험 suite가 계속 실행 중이라는 근거가 아니며 verified wait가 아니다.
이전 blocked 감사 횟수는 새 사용자 완료 답변 뒤의 감사에 그대로 재사용하지 않는다.

다음 절차:

1. 이미 열린 콘솔의 LAUNCH_EXIT와 오류 전문을 확인한다. 원인 검토 전 같은 명령을 재실행하지 않는다.
2. 확인된 원인에 필요한 수정만 수행하고 관련 검사를 실행한다. 기존 묶음/실패 증거는 보존한다.
3. 실제3조건 종료·ETL 저장/해독/손실/범위가 확인된 뒤 요청 시각 연결과 현장 계측을 이어간다.

이번 변경은 조사 기록과 다음 행동의 갱신이다. 제품·설치본·서버 실행은 변경하지 않아
앱 health/build·현장15분/120분 시험은 실행하지 않았다.
15분FAIL,120분미시작,물리NOT_TESTED,full_data NOT_EVALUATED,출시HOLD를 유지한다.


## 2026-10-15 사용자 콘솔 확인과 32/64비트 실행 경로 보완

사용자가 R2의 실제 콘솔을 제공했다: `native PS5.1 x64 required`, `LAUNCH_EXIT=1`,
scenarios0이다. 이 오류는 WPR 시작 전 native runtime 검사에서 발생한다.
사용자 출력에는 실행 시각과 부모 프로세스 비트수가 없어, 앞선00:19 PID99316의
일반적인 시스템 오류와 동일 실행이라고 확정하지 않는다.

읽기 전용 재현에서 기존 고정 System32 명령은 64비트 부모에서는 native 검사를 통과하지만,
32비트 부모에서는 자식 실제 경로가 SysWOW64로 바뀌어 같은 native 검사를 실패했다.
사용자 원래 창의 비트수는 미확정이며, 확인된 보완 대상은 이 bootstrap의 32비트 호환 결함이다.
`trace_validation_bootstrap.py`는 32비트 부모에서 Sysnative, 64비트 부모에서 System32를 선택한다.
suite는 실제 비트수·edition·version·expected/actual exe를 출력한다. 기존 native PS5.1 x64,
관리자, 상위 job 부재, 해시 잠금, 세션 소유권/종료 및 출시 gate는 그대로 유지한다.

실제 x86/x64 프로세스8회에서 올바른 native 자식, 실행 중 suite 쓰기 차단, 틀린 SHA 실행 거부,
공백/따옴표 경로, 실제 suite의 일반 권한 거부와 직접 x86 실행 거부를 확인했다.
입력 경로/해시 거부7조건을 포함한 검사 exit0, 변경 Python2파일 Ruff 및 git diff check exit0이다.
최종 R3 명령 파일 자체도 양쪽 부모에서 실행해 native 통과 후 관리자 조건에서 inner exit1로
거부되는 것을 확인했다. 이 두 실행은 예상 거부 검증이며 관리자 WPR 시험 통과가 아니다.

새 묶음: `C:/Users/user/Desktop/SmartFactory/PDCA_TRACE_ARCH_20261015_4f4490f1/package-r3`.
명령: 같은 부모의 `PINNED_LOCAL_TRACE_COMMAND_R3.txt` 본문 전체를 개발 PC의 독립 관리자
Windows PowerShell에 한 번 실행한다. 완료 시 LAUNCH_EXIT, 오류 시 runtime/errors를 확인한다.
R2와 기존 해시 결합 증거를 덮어쓰지 않았다. controller/helper/profile3파일은 같은 바이트다.
R3 suite SHA256: `4eede2324f9dfff7beaed877793c5a28265a3b4b55a2d7d49a343dbcb63f9543`.
명령 SHA256: `1da29e5abcc3fb02868d54dc17ab41c645328a94e41cf86eccf0881578317b69`.
실제 관리자 추적·ETL·현장 검증은 남는다. 제품/설치본 변경이 없어 앱 health/build는 반복하지 않았다.
15분FAIL,120분미시작,물리NOT_TESTED,full_data NOT_EVALUATED,출시HOLD를 유지한다.

Windows 경로 처리 근거: [Microsoft File System Redirector](https://learn.microsoft.com/en-us/windows/win32/winprog64/file-system-redirector).


## 2026-10-15 R3 실제 실행 실패와 WPR 인자·종료 코드 보완

실제 R3 suite41712/controller4412/Guard41068 실행을 관찰한 뒤 세 프로세스의 종료를 확인했다.
사용자가 제공한 TS0ddd9e1ae7e1 summary SHA256
`bc55f8f53896760d88e7494fc60de5308cdc0407063c91fca75ffbc2fb60ed6f`와 로컬 바이트가 일치한다.
사용자 콘솔은 부모32비트→Sysnative 선택, 자식64비트PS5.1, LAUNCH_EXIT1을 확인한다.
Normal 단계에서 실패해 뒤의 ControllerExit/Deadline은 실행되지 않았다.

실제 WPR 첫 status 인자가 하나의 문자열
`-status-instancename SFLTrace_105ea2aa6cf04cd0a3d5987bbdf6980d`로 전달됐다.
WPR는3311404546(0xc5600602, Invalid command syntax)으로 종료했다.
단일 옵션 switch 결과가 scalar가 되어 +=가 문자열 결합을 한 것이 코드와 원시 argv에서 확인됐다.
start_attempted=false, start-intent 없음, status-before1회만 있으므로 이 실행은 추적을 시작하지 않았다.
이 결과를 cleanup PASS 또는 다른 WPR 세션 부재 증명으로 확대하지 않는다.

별도로 Start-Process 출력 리디렉션과 WaitForExit만 사용하면 실제 exit0/1/23 모두 null이 되는
현상을 PS5.1에서 재현했다. 즉시 프로세스 Handle을 보유하면 각각0/1/23으로 확인됐다.
원래 summary의 controller_exit=null과 FAIL은 보존한다. 추정 값으로 과거 종료 코드를 채우지 않는다.
R4는 Get-TraceArguments로 모든 옵션을 배열로 구성하고 Start-TraceProcess로 핸들을 보유한다.
suite와 Guard 양쪽에 적용하고 종료 후 Dispose한다. 권한·독립성·소유권·시간 제한은 유지한다.

기존 lifecycle14조건과 native PS5.1 suite10개가 최종exit0이다. 네 가지 WPR 동작의 인자를
실제 네이티브 자식에서 대조하고 위험 인자4종을 거부했다. 빠른/지연 종료0/1/23 여섯 경우와
실제 읽기 전용 WPR status exit0/ABSENT/job active0을 확인했다. start/stop/cancel은 실제 WPR에 실행하지 않았다.
32/64비트8실행·입력 거부7조건, Ruff, 최종 R4 명령의 양쪽 비트수 일반 권한 거부 검증도exit0이다.
첫 회귀의 Python 경로 escape 경고는 수정하고 새 tests-r2로 재검증했으며 첫 기록도 보존한다.

기록/새 묶음: `C:/Users/user/Desktop/SmartFactory/PDCA_TRACE_COMMAND_20261015_395f95be`.
R3 원문14파일은 source/copy 길이·SHA로 검산해 보존했다. 다음 실행은 개발 PC 독립 관리자
PowerShell에서 `PINNED_LOCAL_TRACE_COMMAND_R4.txt` 본문을 한 번 실행하고 LAUNCH_EXIT를 확인한다.
manifest SHA256 `7f2ec742e79a857f1b13c8050d30407d6be9628faef24f66de604904a25ae663`.
suite SHA256 `aae7da0ba5f44b025c51f77b5c1c303a5f64d3d047a620cf2f878178cb12fb30`.
실제 R4 WPR3조건·ETL 품질 검증은 남는다. 제품/설치본 변경이 없어 앱 health/build는 반복하지 않았다.
15분FAIL,120분미시작,물리NOT_TESTED,full_data NOT_EVALUATED,출시HOLD를 유지한다.

관련 근거: [PowerShell Start-Process 종료 코드 문제](https://github.com/PowerShell/PowerShell/issues/20400),
[Microsoft Process.WaitForExit](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.waitforexit).


## 2026-10-15 R4 실제 추적 저장·정리와 로그 완료 대기 보완

사용자 콘솔 LAUNCH_EXIT1 및 TS0077ea5bb8cc summary SHA256
`f21d7d131381d51268af89d30734bc55cffca72cebef86a622a4bb41152bee56`를 실제 파일과 대조했다.
Normal의 controller exit0, result/ETL 해시와5개 WPR 명령의 실제exit0/소유 job active0을 확인했다.
ControllerExit의 별도 Guard result도 controller-exited, 추적 저장·해당 instance 정리 완료이며,
controller37500/guard31812 및 Normal37928/14204는 후속 프로세스 목록에서 없었다.
ControllerExit 실제 종료 코드는 summary 작성 전 로그 읽기 실패로 미기록이므로23을 추정해 채우지 않는다.
suite FAIL과 Deadline 미실행을 유지한다. 원본64파일을 새 폴더에 복사하고 길이/SHA를 대조했다.

실제 실패는 timed WaitForExit 직후 ControllerExit.stdout.log의 ReadAllText 공유 위반이다.
원래 파일 잠금 소유자는 미확정이다. 단순 native 자식20회에서는 자연 재현되지 않았지만,
출력 writer를 지연시킨2조건에서 같은 공유 위반을 재현했다. 프로세스 종료만으로 비동기 출력
처리까지 끝났다고 볼 수 없다는 Microsoft 계약에 맞춰 R5는 두 로그를 읽기 전용으로 동시에 열고
쓰기를 배제한 뒤 읽는다. 공유/잠금 위반만 최대10초 재시도하며 파일 누락·크기64KiB 초과는 실패한다.
무제한 WaitForExit나 고정 지연을 추가하지 않았다. 실제 종료 코드는 로그 읽기 전에 기록한다.

최종 tests-r2: lifecycle14조건/native PS5.1 suite11개, 로그 지연2·시간 초과·크기 초과2·파일 누락·
실행 중 읽기 거부7조건, 종료0/1/23과 최종 stdout/stderr6조건이 실제exit0이다.
첫 tests-r1은 PowerShell 예외 래핑에 대한 시험의 타입 판별 오류로 실패했다. 진단으로
FileNotFoundException을 확인해 typed catch로 고쳤고 원래 결과를 보존한 채 전체 관련 검사를 재실행했다.
32/64비트8실행·입력 거부7조건, Ruff, 최종 R5 묶음의 양쪽 비트수 일반 권한 거부 검사도exit0이다.

R4 ETL 두 개를 잠근 상태로 tracerpt raw/report4회를 실행해 각각exit0을 확인했다.
Normal은156906사건/해독오류6825, ControllerExit는60127사건/해독오류6762다.
둘 다 EventsLost/BuffersLost0이나 CSwitch v5가 opaque이고 thread v3 해독오류가 있어 품질은
INCOMPLETE_OR_UNUSABLE이다. Normal CSwitch91708/ReadyThread55267,
ControllerExit30672/20439 사건 수는 payload·thread generation·요청 QPC 연결 검증을 뜻하지 않는다.
이는 실제 추적을 확보한 진전이며 성능 원인 확정이나 현장 QA 통과가 아니다. 별도 decoder 보완이 필요하다.

근거·새 묶음: `C:/Users/user/Desktop/SmartFactory/PDCA_TRACE_LOGS_20261015_4b381b92`.
사용 절차: 개발 PC의 독립 관리자 PowerShell에서 `PINNED_LOCAL_TRACE_COMMAND_R5.txt` 본문 전체를
한 번 실행하고 LAUNCH_EXIT를 확인한다. 오류 시 재실행하지 않고 새 TS/T 원문부터 확인한다.
R5 manifest SHA256 `313112238ff09826e7abbb80ae4651e0e502db991c71c591ce1e4580151009bf`.
suite SHA256 `e355eee44f3c84418dc1a24a4dca7c8c6520a4c03a32ff167a032f7aef94d24a`.
제품/설치본 변경이 없어 앱 health/build·설치를 반복하지 않았다.
15분FAIL,120분미시작,물리NOT_TESTED,full_data NOT_EVALUATED,출시HOLD를 유지한다.

출력 완료 계약: [Microsoft Process.WaitForExit](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.waitforexit?view=netframework-4.8.1).


## 2026-10-15 R5 세 추적 결과 확인과 대체 해독 경로 조사

R5 TS31ecead606bb의 Normal T70da953ccd7a, ControllerExit Tb0fbd84b2e1e,
Deadline T82d774356b09 결과에서 각각 지정된 종료 이유·추적 저장·해당 instance 정리를 확인했다.
모든 WPR 명령은 actualexit0, force 없음, 소유 job active0이며 result/lease/ETL 및 Guard stdout SHA를 대조했다.
해당6개 제어·감시 PID는 후속 조회에서 없었다. 하지만 suite45888(생성 FILETIME134364938856872760)은
실제 프로세스 핸들에 대한10초 WaitForExit에서도 살아 있었고 summary/LAUNCH_EXIT는 아직 없다.
Windows PowerShell event400의 HostApplication은 이 R5 suite/manifest를 명시한다.
사용자는 ‘진행 중’이라고 답했다. 콘솔 선택 상태 가능성을 확인하도록 Esc1회를 요청했으며,
선택 여부와 정지 원인은 미확정이다. 창 목록 도구에는 해당 관리자 콘솔이 나타나지 않았다.
같은 실행을 다시 시작하거나 완료/PASS로 바꾸지 않는다. 이 관찰은 verified live wait다.

R4 원본 두 ETL은 별도 개발 폴더의 Microsoft.Diagnostics.Tracing.TraceEvent4.0.0으로 읽었다.
전체156906/60127사건과 CSwitch91708/30672, ReadyThread55267/20439 수가 tracerpt 원문과 같다.
세 표본에서 원시 QPC·버전·TID/PID·CPU를 대조했다. ThreadTraceData가 EventData 앞8바이트를
repurpose하므로, 라이브러리 반환 payload를 원본 바이트로 오인하지 않도록 별도 기록했다.
미처리 사건1867/1001은 남는다. 전수 payload·thread generation·request QPC·계측 오버헤드 검증은 미완료이며,
기존 tracerpt INCOMPLETE_OR_UNUSABLE 판정이나 현장 latency 원인을 변경하지 않는다.

조사 위치: `C:/Users/user/Desktop/SmartFactory/PDCA_TRACE_PAYLOAD_20261015_d199ce01`.
probe build exit0(원시 QPC API 사용 경고3), 두 ETL 실행exit0, 개수/표본/15개 의존 패키지 기록 검사exit0이다.
NuGet archive SHA512는 cache sha512와, 서명 제외 contentHash는 metadata/lock과 각각 대조했다.
두 해시의 의미를 혼동하지 않는다. SDK 최초 실행이 자동 만든 localhost 개발 인증서는 정확한 thumbprint와
생성 시각을 확인해 CurrentUser/My에서 제거했고, Root 신뢰 저장소에는 없었다. 앱 코드서명 인증서가 아니다.
출처·바이트 기록은 probe-review.json SHA256
`7793231b3b7615d40bb91368249a6efe4794249d66bf1bf6a6348b574a0c0b59`에 있다.

다음 절차: 동일 R5 프로세스의 종료와 최종 summary를 확인한 뒤, 대체 해독기의 전수 payload 및
요청-스레드 연결 검증을 이어간다. 제품/설치본은 변경하지 않았다.
15분FAIL,120분미시작,물리NOT_TESTED,full_data NOT_EVALUATED,출시HOLD를 유지한다.

출처: [Microsoft TraceEvent parser](https://raw.githubusercontent.com/microsoft/perfview/10e5d271cebcdf5d6cf122c6ab9c863860a7a2f1/src/TraceEvent/Parsers/KernelTraceEventParser.cs),
[NuGet contentHash 정의](https://github.com/NuGet/Home/wiki/Nupkg-Metadata-File).


## 2026-10-15 선택한 추적 필드 전수 대조와 R5 대기

보존한 R4 Normal/ControllerExit ETL을 각각 TraceEvent4.0.0으로 다시 읽고, 별도 Python 검사로
tracerpt 원시 XML과 선택 기록153,793/57,866건(합계211,659건)을 전수 대조했다.
전체 사건 수156,906/60,127, 선택 종류별 수, 원시 QPC·CPU·opcode/version·payload·TID/PID가 일치한다.
정렬 순서 대신 중복 수를 보존한 multiset을 비교했으며 이 두 자료의 동일 선택 기록 중복은0건이다.
ReadyThread8바이트는 tracerpt의5개 필드로 재구성했다. ThreadTraceData가 내부 수정한 앞8바이트는
해독 PID/TID로 복원한 뒤 원래 XML EventPayload와 대조했다. ETL·XML·명령 영수증·해독 출력은
동일 잠금 바이트의 SHA/크기를 확인했고, 서로 다른 ETL을 결합하는 경우를 거부한다.

이 결과의 범위는 선택 필드 일치다. CSwitch 나머지 비트/상태 의미, 미처리 사건1867/1001의 영향,
스레드 세대 구분과 실제 요청 구간의 포함 여부는 미검증이다. 기존 tracerpt의
INCOMPLETE_OR_UNUSABLE 판정은 보존하며, 서버203ms 지연 원인이나 현장 QA PASS로 확대하지 않는다.
이 짧은 로컬 추적에는 앞선 HTTP 관찰의 같은 실행·요청 시각 자료가 없으므로 서로 연결하지 않는다.

개발 증거 위치: `C:/Users/user/Desktop/SmartFactory/PDCA_TRACE_CROSSCHECK_20261015_3a71efd6`.
`crosscheck-results.json` SHA256은
`2c20efdd33deec2f1260aba98261201b453af67a3065515de4d0950b715ffd2f`이다.
빌드 exit0/경고0, 두 추출 exit0, 전수 대조 exit0, 최종 단위 검사16개 exit0,
선택 Ruff 검사 exit0를 확인했다. 잘못된 ETL 해시와 기존 출력 폴더를 입력한 두 음성 검사는
각각 실제 exit3762504530으로 해당 오류를 내며 거부했다. 기록을 덮어쓰지 않았다.
검증 원문·도구 소스·빌드 파일 사실은 verification.json에 기록했다.

R5는 같은 suite45888/생성 FILETIME134364938856872760이08:43:36KST의 실제 핸들10초 대기에서도
살아 있었고 최종 summary는 없었다. 세 Guard의 저장·정리 확인은 이전 기록대로 보존한다.
콘솔 선택으로 멈췄는지는 아직 미확정이며 앞선 Esc1회 요청의 답을 기다린다. 재실행하지 않는다.
최종 suite 종료 코드와 요약 확인 후, 요청·스레드 연결에 필요한 검증을 이어간다.
제품/설치본 변경 없음, 15분FAIL·120분미시작·물리NOT_TESTED·full_data NOT_EVALUATED·출시HOLD다.


## 2026-10-15 R5 종료 확인과 요청 연결의 남은 조건

사용자 콘솔의 LAUNCH_EXIT0와 summary SHA256
`93c6d756a41dd89277f5843a46eac35f0a5d17f0bf33308b8ee3c536ef7e8585`를 실제 잠금 파일과 대조했다.
Normal/ControllerExit/Deadline의 실제 controller exit는0/23/0이며23은 해당 격리 시나리오의 예정된 종료다.
세 결과의 lease·instance·ETL·Guard stdout 해시, 시작/정리 상태와15개 WPR 명령의 actualexit0,
force 없음·소유 job active0를 확인했다. suite45888과 여섯 controller/guard PID는 모두 없었다.
95개 결과 파일을 새 사본으로 보존하고 크기·SHA를 대조했다. 현재 source와 package도 일치한다.

ControllerExit의 로그 대기는2002ms, 공유 위반 재시도59회 후 writers_closed=true였다.
R4에서 중단됐던 실제 로그 경쟁 조건을 R5의 제한 시간 내 대기가 처리했다.
최종 suite 상태는 CONTROL_FLOW_COMPLETE, scope는 LOCAL_WPR_CONTROLLER_LIFECYCLE_ONLY다.
콘솔 선택 정지가 원인이었는지는 별도 관측으로 증명하지 않았다. R5는 완료됐으므로 재실행하지 않는다.
검토 스크립트의 초기 저장소 profile 경로 가정을 실제 R4 package 출처로 정정한 후 재검토exit0였다.
추적 자체를 다시 실행하거나 고정 package를 변경하지 않았다.
검토 기록은 `C:/Users/user/Desktop/SmartFactory/PDCA_TRACE_LOGS_20261015_4b381b92/r5-completion-review.json`,
SHA256 `dad7a94b8ed10a52921d7a5e778f9929642589643458f3896c5a14770d485b8a`다.

추가로 R4 두 자료의 CPU별 선택 사건 순서까지 tracerpt와 독립 해독 출력을 대조했다.
CSwitch 연속성 불일치0/0, 시각 역전0/0, 참조한 nonidle TID1112/839개 중 lifecycle 기록 없는 TID0/0,
관찰 구간 내 동일 TID의 다른 PID·반복 시작·종료 후 재시작0/0을 확인했다.
이는 전체 추적 누락 없음이나 native 생성 시각 결합의 증명이 아니다.
[Microsoft 문서](https://learn.microsoft.com/en-us/windows/win32/etw/thread-v2-typegroup1)의 DCStart/DCEnd는
수집 시작/종료 시점의 스레드 목록이므로 native 생성 시각으로 대체하지 않는다.

이전 합성 HTTP142건은 전날 별도 실행의 기록이다. UTC 시작 시각도 R4 trace header 구간보다 앞선다.
coverage-audit.json의 overlaps_with_r4는 숫자 QPC 범위 비교만 뜻하며, 별도 실행의 clock epoch가
같다는 증명이 아니다. 이 의미와 결합 금지를 coverage-qualification.json에 명시했다.
같은 수집 실행·시간 기준·PID/TID 생성 식별자·실제 요청 구간을 결합한 새 검증이 필요하다.
또한 관찰한 CSwitch V5 payload의 byte13에는0/1 외 값이 다수 있다.
[기존 V2 문서](https://learn.microsoft.com/en-us/windows/win32/etw/cswitch)의 WaitMode 정의를
그대로 적용하지 않으며, 나머지 bit/상태 의미와 전체 scheduler duration 해석은 미검증으로 둔다.

검사 위치는 `C:/Users/user/Desktop/SmartFactory/PDCA_TRACE_COVERAGE_20261015_110b3ae4`다.
coverage audit/7개 회귀 조건 및 선택 Ruff exit0, 문서 과거 단계 보존 검사를 수행했다.
이제 종료 코드 대기 대신 같은 실행의 요청·추적 연결 시험을 준비한다.
제품/설치본 변경 없음, 서버 지연 원인 미확정,15분FAIL·120분미시작·물리NOT_TESTED·출시HOLD를 유지한다.


## 2026-10-15 같은 실행의 요청·추적 시험 준비

개발 PC에서 HTTP 요청과 Windows 추적을 같은 실행으로 연결하기 위한 도우미를 추가했다.
`field_trace_request_fixture.py`는 일반 권한으로 loopback 서버와 클라이언트를 실행한다.
기존 HTTP 수집기·native timing 소스는 변경하지 않고, 시험 안에서만 연결 클래스를 바꿔
일반 요청·서버 대기80ms·클라이언트 thread CPU80ms를 각각3회 기록한다.
두 스레드는 같은 Python GIL을 공유하므로 이 결과를 운영 서버 지연 원인으로 직접 확대하지 않는다.

`invoke-request-trace-validation.ps1`은 이미 검증한 R5 Guard와8초/stop60초 계약을 그대로 쓴다.
일반 권한 fixture의 실제 PID/생성 FILETIME·소스 해시·600초 만료를 확인한 후,
새 추적의 lease/ready 해시를 결합해 요청을 시작한다. 완료 결과 해시 확인 후 소유 추적을 정리한다.
외부 명령에서 새 coordinator 바이트를 잠금·고정 해시로 확인하며, R5 기준 manifest와3개 파일은
기존 바이트 그대로 포함한다. 만료되거나 이미 사용한 요청은 거부한다.
사용자 절차: Codex가 fixture를 준비한 뒤 발행한 명령 본문을 독립 관리자 PowerShell에서1회 실행하고,
`LAUNCH_EXIT`와 결과 경로/해시를 확인한다. 오류 시 같은 명령을 반복하지 않는다.

fixture6검사·native PowerShell coordinator5조건·32/64비트 bootstrap6조건을 실제 실행했다.
검사 driver exit는 각각0이며, 낮은 권한과32비트 직접 진입은 예정된 exit1로 거부됐다.
fixture 실패 시 스레드 종료와 transport 복구, 다른 실행/해시/만료 거부, 원본 덮어쓰기 거부,
실제 파일 잠금 경쟁 대기와 잘못된 JSON 거부를 확인했다. 선택 Ruff와 diff 검사를 별도로 수행한다.
전체 coordinator의 관리자 추적 연결·정리와 요청/ETL 연결은 아직 실행하지 않았다.

준비 위치: `C:/Users/user/Desktop/SmartFactory/PDCA_REQUEST_TRACE_20261015_5d90d5a4`.
정적 manifest SHA는 `313112238ff09826e7abbb80ae4651e0e502db991c71c591ce1e4580151009bf`,
coordinator SHA는 `7880ca458d06e68e472d3381e9748f20094c6572ac6a3242439aa34052a64bde`다.
제품/설치본 변경 없음, R5 재실행 없음, 서버203ms 원인 미확정,
15분FAIL·120분미시작·물리NOT_TESTED·출시HOLD를 유지한다.


## 2026-10-15 요청9건과 같은 실행의 추적 연결 완료

단일 요청·추적 시험은 사용자 LAUNCH_EXIT0, 일반 권한 fixture actualexit0로 끝났다.
콘솔 summary SHA `418bb1e427be44bc0f72d43002973865996f2512538ad7c5a32cd74c79605f69`를
실제 잠금 파일과 대조했다. 실행은 `T280f593dda00`, fixture40816/controller9620/guard2536이며,
세 프로세스 부재·소유 추적 정리·WPR5명령 actualexit0·강제 종료 없음과36개 보존 사본 해시를 확인했다.
요청9건은 동일 run ID·PID/생성 FILETIME·lease/ready/결과 해시로 결합됐다. R5 재실행은 하지 않았다.

tracerpt raw/report 내보내기와 기존 TraceEvent 해독기는 각각exit0였다.
전체107519사건 중 선택105393사건(CSwitch60904, Ready36811, thread lifecycle7678)의
QPC·CPU·opcode/version·선택 payload/식별자가 전수 일치했고 CPU별 순서도 일치했다.
CSwitch 연결 불일치0, 시각 역전0, 관찰 TID 재사용0이다.
그러나 원래 tracerpt에는 processing error7685·provider GUID 누락·opaque payload가 있고,
대체 해독기의 unhandled742도 남아 있다. 전체 품질 INCOMPLETE_OR_UNUSABLE을 보존한다.
EventsLost/BuffersLost0은 전체 사건 누락이 없다는 증명으로 사용하지 않는다.

클라이언트 TID43380과 서버 TID45656의 실제 Thread/Start·End가 동일 PID40816으로 기록됐다.
두 스레드의 native 생성 FILETIME은 수집 시간 범위에 있고, 반복 native 식별자는 일치한다.
각 요청의 QPC 주파수10MHz·양끝 CPU 배정 구간·스레드 생존 구간·12개 CPU의 전후 사건 포함을
검사했다. native FILETIME을 ETW의 event timestamp와 같다고 주장하지 않는다.

| 시험 조건(각3건) | 요청 벽시계 시간 ms | 클라이언트 CSwitch 배정 구간 ms | 배정 구간 밖 ms |
| --- | ---: | ---: | ---: |
| 일반 요청 | 1.0260–1.5887 | 0.7766–1.0331 | 0.2494–0.5556 |
| 서버80ms대기 | 81.4734–81.8685 | 0.8964–0.9542 | 80.5770–80.9143 |
| 클라이언트 CPU 지연 | 87.9230–90.4784 | 86.2397–89.4136 | 0.6437–1.6833 |

위 배정 구간은 CSwitch 전환 사이 시간이다. DPC/ISR을 빼지 않았으므로 정확한 thread CPU
작업 시간으로 표시하지 않는다([Microsoft CPU 분석](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/cpu-analysis)).
배정 구간 밖 시간을 ready 대기·서버 대기·GIL/lock 대기로 자동 분류하지 않는다.
native thread CPU 경계 카운터는 세 CPU 주입 요청 모두93.75ms로 벽시계보다 커서,
짧은 구간의 정확한 CPU 합계로 사용할 수 없음을 실제 결과에도 명시했다.
같은 Python GIL을 공유하는 합성 시험이며 현장203ms 지연 원인 검증을 대신하지 않는다.

새 구간 계산의10개 회귀 조건이exit0였다. 누락된 switch, 시간 역전, CPU간 중복 배정,
CPU 누락, 다른 PID, 생존 구간 이탈, 실행 중 아닌 경계, TID 재사용 등을 거부했다.
별도로 raw XML의 대상 스레드별 in/out 전환을 누적해 JSONL의 CPU별 인접 사건 계산과
요청/서버/주입30구간을 대조했고, 모든 세부 구간이 일치했다(exit0). 선택 Ruff exit0.
제품 코드는 변경하지 않아 제품 전체 health/build와 설치 시험은 반복하지 않았다.

증거: `C:/Users/user/Desktop/SmartFactory/PDCA_REQUEST_TRACE_20261015_5d90d5a4`.
`request-correlation.json` SHA256은
`d204a8e0b7ec9a9a654201930ac6910a92097c4d70f00f5936c3e7c42a02f470`이며,
원문·해독·구간 계산·독립 검증 파일 사실은 correlation-verification.json에 기록했다.
관리자 실행 요청은 완료됐고 같은 명령을 다시 실행하지 않는다.
다음은 이 방법의 한계 안에서 collector 스케줄링과 backend 응답 시점을 분리하는 제한된 현장 진단 준비다.
15분FAIL·120분미시작·물리NOT_TESTED·전체 데이터 NOT_EVALUATED·출시HOLD는 유지한다.


## 2026-10-15 health 요청별 서버 처리 구간 계측의 로컬 검증

기존500ms worker 로그와 클라이언트 요청 기록만으로는 현장203.1356ms의 서버 내부 구간을
나눌 수 없었다. `/health`에 선택적 로컬 진단 헤더를 추가하고 기존 HTTP 수집기에 요청 ID 전달을
추가했다. 같은32자리 ID·PID·loop/worker native TID와8개 perf_counter_ns checkpoint를 반환한다.
일반 본문·기존500ms 로그·현장200ms 기준은 유지한다. 잘못된 ID·중복 헤더·외부 peer·Origin/Referer가
있는 요청은 일반 경로로 처리한다. 예외·취소 응답에 완료 계측을 붙이지 않는다.
계약과 사용 예시는 설계5.16에 기록했다. 새 source이며 기존4cc 설치본과 고정 package는 변경하지 않았다.

집중48검사(exit0)는 worker pool 대기, PLC/runtime/frontend 지연, event loop 복귀 지연,
동시 요청 분리·예외·취소·일반 응답 보존을 확인했다. 실제 Uvicorn loopback 통합2검사(exit0)는
일반1건/진단4건의 원문 헤더·본문·해시·ID·시간 순서와 서버 정상 종료를 확인했다.
조회값을 격리하고 lifespan을 꺼 실제 장비 서비스를 시작하지 않았다. 세 처리 단계에 각각80ms를
주입했고 해당 구간에서70ms 이상을 측정했다. 관찰 헤더375bytes는 이번 로컬 표본의 값이다.
기존 HTTP 수집기32검사(exit0), 새 모듈 mypy와 선택 Ruff도 exit0였다.

최종 제품 소스에서 `npm run health` exit0. frontend42파일437검사, backend930검사를 실행했고
private F01 fixture 미지정으로 기존1검사는 skip이다. 의존성·Electron 시작·frontend 타입/린트·
backend 린트/타입 및 QA selftest가 같은 명령에서 완료됐다. 패키지 빌드·설치·현장 시험은 실행하지 않았다.
검증 소스 사본과 전체 출력/원문 응답은
`C:/Users/user/Desktop/SmartFactory/PDCA_HEALTH_TIMING_20261015_e3d88973`에 보존했다.
verification.json SHA256은 `9710323425f782947db8d6f9272e35e8844228a9a14ffc6e7bf369d3a64668a6`이다.

구간 값은 OS scheduling·GIL/lock·계측 비용을 포함할 수 있는 벽시계 시간이며 CPU 사용량이 아니다.
JSON 직렬화·middleware 완료·socket 전송은 route_resume 뒤라 포함하지 않는다.
실제 지연 원인은 여전히 미확정이다. 다음은 진단 응답의 엄격한 소비 검사와 native 세대/clock 결합,
clean source의 패키지 동작 검증 후 제한된 현장 진단 준비다. 이전 원격 UI 실패는 해결됐다고 기록하지 않는다.
15분FAIL·120분미시작·물리NOT_TESTED·전체 데이터 NOT_EVALUATED·출시HOLD를 유지한다.


## 2026-10-15 health v2의 native 세대·시계 연결 검증

v1의 PID/TID·perf_counter_ns 숫자만으로는 재사용과 시계 기준 불일치를 검사할 수 없었다.
선택적 health 진단의 v2에 loop/worker 전후4개 native anchor를 추가했다. 각 anchor는 Windows
process/thread 생성 FILETIME과 QPC/Frequency·호출 전후 perf_counter_ns를 포함한다.
일반 health에는 native 호출이 없고, 조회 실패는 UNAVAILABLE로 표시하며 health 본문은 유지한다.
소비기는 외부에서 확인한 backend 세대·요청 ID, 원문 본문/헤더 해시, 정확한 v2 schema·단조 순서,
anchor의 단계 포함·thread 생성 시각·collector와의 시계 offset 교집합을 검사한다.
부적합 자료는 NOT_CORRELATABLE이며 시간0 또는 QA PASS로 바꾸지 않는다. 설계5.17에 계약을 기록했다.

집중49검사, 소비기7그룹, 실제 loopback HTTP2검사, 별도 프로세스1통합검사 모두 exit0였다.
소비기에는 중복/누락/과대 헤더·중복 JSON key·NaN·bool/float 시각·잘못된 해시·다른 요청/세대·
시계 epoch/주파수 불일치·역전·범위 이탈·native 누락을 주입했다. 마지막 생성 시각 경계 보완 뒤
소비기/실제 HTTP/별도 프로세스를 새 결과 폴더에서 재검증했다. 새2모듈 mypy와 선택 Ruff exit0.
기존 v1 보존 응답4건은 v2 검증에서 모두 거부됐으며 원문은 변경하지 않았다.

별도 프로세스 시험은 장비 lifespan을 끈 합성 health 서버와 실제 Windows API를 사용했다.
부모의 WindowsProcessReader에서 child PID/생성 FILETIME을 요청 전후 확인했고, 서버 응답의 native
생성 시각과 일치했다. 일반진단/PLC80ms/runtime80ms/frontend80ms 총4요청이 연결됐다.
각 주입 구간70ms 이상과 양쪽 process의 QPC frequency/offset 교집합을 검산했다.
child 정상 exit0·잔존 없음·강제 종료 없음이다. native 생성 시각을 ETW event timestamp로 대체하지 않았다.

제품 코드 변경 후 최종 `npm run health` exit0: frontend437검사, backend931검사 중 기존
private F01 fixture1건 skip, 나머지 의존성/Electron/타입/린트/QA selftest 완료.
검증 소스와 원문 증거: `C:/Users/user/Desktop/SmartFactory/PDCA_HEALTH_CLOCK_20261015_652e0d2c`.
verification.json SHA256 `0dac9b6afe931d3a5ebc4f3646dc55558663b557d12793274557f0f97f2e6937`.

이번 결과는 요청·native 시계 연결이며 실제 ETW coverage·정확한 CPU 시간·현장 지연 원인 검증이 아니다.
진단 자체의 native 호출 비용도 경과 시간에 포함된다. 다음 단계는 clean source의 새 패키지와
frozen/Electron 응답·정상 종료 검증 후 제한된 현장 진단 준비다. 기존4cc 설치본은 변경하지 않았다.
15분FAIL·120분미시작·물리NOT_TESTED·전체 데이터 NOT_EVALUATED·출시HOLD를 유지한다.

## 2026-10-15 1.0.29 패키지와 frozen backend 검증

clean `acaf77d95101a050f4d3ecd76125d3502036f5a7`의 새 미서명 후보를 빌드했다.
설치본 SHA256은 `3394a23de82f0d40749f020af320592a33cd9630113ba02b1e40f63f41549de7`이다.
출시 lock 전체 health exit0, 추가 진단10검사 exit0, 추출 payload1,867파일 대조와
frozen backend 일반1/진단4요청·정상 exit0을 확인했다. 기존 private F01 skip1건은 남아 있다.
Electron 실제 실행·설치/복구·현장 검증은 다음 단계이며 출시HOLD를 유지한다.
상세 원문·해시·검증 한계와 실행 체크리스트는
[1.0.29 후보 검증 보고](production-release-risk-validation-health-candidate-20261015.report.md)에 기록했다.
