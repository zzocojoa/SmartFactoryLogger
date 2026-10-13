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

별도로 보유한 [REST API 안내서](../reference/ametek_land_spot.pdf) Issue2의 8쪽(인쇄2-2)을
텍스트와 렌더링 이미지로 대조했다. `signalpc`는 Ratio/Application 모델에서 제공하는
0–100의 정수 %다. 이 출력의 정밀도와 내부 알람 비교 정밀도가 같다는 설명은 없다.
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
