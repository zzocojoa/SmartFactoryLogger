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
