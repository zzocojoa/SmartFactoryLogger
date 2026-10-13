# 실제 서버 현장 진입 확인과 새 drop 관찰

2026-10-13. 운영 build `541d701d544eea6a8a4e4836047077eaf9cfaf30`의
읽기 API 12개와 이전 같은 세대의 사본을 대조했다. 앱은 Running/REAL이다.
새로운 이미지 enqueue 누락 **173건**이 확인돼 R5에 별도 사건으로 추가한다.
정식 출시 **HOLD**, `full_data_gate=NOT_EVALUATED`를 유지한다.

## 동일 실행 세대와 카운터

logger는 `e9a785c0-46a2-45d2-bf7a-4187cce08771`, SPOT은
`efca4313-f987-4bb2-bcc8-4de40712396c`다. 시작 시각은 KST 03:26:56이며
아래 세 표본 모두 같은 세대다. 현재 CSV는 `Factory_Integrated_Log_v2_20261013_032656.csv`다.

| KST 관찰 시각 | CSV rows | 이미지 written | image drop | writer failure |
| --- | ---: | ---: | ---: | ---: |
| 03:58:13 | 8,237 | 1,329 | 0 | 0 |
| 16:22:51 | 204,106 | 40,558 | 173 | 0 |
| 16:30:40 | 206,188 | 40,968 | 173 | 0 |

마지막 두 config 요청 시각 차이는 469.566390초다. CSV rows +2,082,
이미지 written +410, drop 증가0이며 두 표본의 queue는0이다.
중간의 모든 queue 전이나 닫힌 파일의 실제 내용을 검증한 결과는 아니다.
173은 거부된 enqueue 시도 수이며 고유 누락 프레임 수·영향받은 행의 수로 바꾸지 않는다.

## 원인과 영향의 확인 범위

실제 운영 commit의 `backend/FacilityData/drivers/spot_api.py` 원문을 추출했다.
AST 대조에서 drop 증가는 1035행의 이미지 크기 상한 초과와 1063행의 `queue.Full`
두 곳뿐이다. 이 버전은 원인별 카운터·drop 시각·payload ID를 제공하지 않는다.
따라서 **원인·정확한 발생 시각·영향받은 프레임/행·복구 가능성은 미확정**이다.
기본 크기 상한이나 현재 큐0을 과거 원인의 증거로 사용하지 않는다.

이전4c의 drop15, 다른541d 실행 세대의 drop44, 과거 writer 저장실패16은 별도 사건이다.
이번173과 합산하거나 격리 시험의 drop0으로 종결하지 않는다.
후보의 원인별 카운터 개선은 이미 로컬 검증됐으나 이번 과거 사건의 원인을 복원하지는 않는다.

SPOT transport 누적 실패는154건이다: image90, temperature28, internal temperature29,
diagnostic7. 보존된 correlation failure event는 image90+diagnostic7=97건이고 모두
`SpotTransportConnectTimeout`이다. 오류 큐의 이미지6건은 각각 ID·예외와 일치하며 HTTP502다.
온도 계열57건의 구체적인 예외와 네트워크·장비·OS 원인은 이 목록으로 확정하지 않는다.
두 표본 사이 transport 누계와97개 event가 같았다. timeout과 drop의 인과도 미확정이다.

## 현장 프로파일과 적용 조건

설정 canonical SHA256은
`55ea6a48ea1480891f8eeebf60969e3a25791335614aea5ab7c250466b31b220`으로 이전 표본과 같다.
현재 fingerprint는 `f84f9d9ddc3b958b1048cbf7bba37933d9e9e83e5b98ba666c6326154c2f74d5`다.
`fingerprint_mismatch`, effective operator/comparator verification false,
`device_config_readback_status=not_supported`, `async_fact_only`가 유지된다.
configured comparator verified=true와 effective=false를 구분한다.
소프트웨어의 SPOT+ AL 문자열은 물리 모델 확인이 아니다.

현재 제품60322·금형10, 작업 정보 적용 시각13:39:05 KST를 API에서도 확인했다.
Codex가 입력한 값이 아니며 이전60332/6·60192/17은 당시 기록으로 보존한다.
담당자 USER_SELF·언제든 유지보수·미서명 운영·모델 미정이라는 기존 답변은 유지한다.

후속 순서:

1. 물리 모델/승인 프로파일·comparator 근거의 미확정 상태를 유지한다. 근거 없이 attestation만 갱신하지 않는다.
2. 새173 사건의 원인/영향/처리와 기존 사건을 세대별로 관리한다. 추가 자료가 원인을 입증하지 못하면 미확정으로 남긴다.
3. 적용 전 조건을 충족한 동일1.0.28 설치본에 현장 QA·정상 시작3회·15/120분·동일 세대 종료/데이터 검증을 연결한다.
4. 실제 승격과 적용 확인 후 운영·다음 롤백 기준을 갱신한다. 이번 조회에서는 설치·재시작·장비 설정·카운터를 변경하지 않았다.

원격 화면의 진단 메뉴 확인 중 표시 편집 모드가 잠시 켜졌으나 저장 없이 껐다.
위젯 이동·배치 저장·설정 적용은 하지 않았다. 서버 변경 없음이라는 표현을 UI 조작 전체에 확대하지 않는다.

## 검증과 보존

`read_server.py`, `read_followup.py`, `review.py` actual exit0. GET12개의 HTTP200,
bytes/SHA256, 이전 사본4개의 기존 manifest 일치, 동일 세대·카운터 정산,
6오류 correlation과 운영 소스 AST를 검산했다. 검산 도우미 Ruff F/E9 exit0.
GET elapsed는 JSON 파싱과 증거 파일 쓰기를 포함하여 정식 HTTP 성능 기준으로 판정하지 않는다.
실행 중 API fact hash도 닫힌 전체 파일의 무결성 검증이 아니다.
제품 변경이 없으므로 통과한 전체 health·설치본 빌드를 반복하지 않았다.

원문·검산은 [실행 기록](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD_ENTRY_20261013_42d60689/README.md)과
[검산 JSON](C:/Users/user/Desktop/SmartFactory/PDCA_FIELD_ENTRY_20261013_42d60689/review.json)에 있다.

선택한 닫힌 증거29파일(manifest 포함), 원문1,061,910바이트를
`Z:/SmartFactory/20261013/records/PDCA_FIELD_ENTRY_42d60689`에 복사하고 전부 대조했다.
manifest SHA256은 `6482f834053aeadf81fec545adfbbe549e92fe4cfb00dffc8e129d3cf22720d9`다.
공유 보존이며 서버 실행 묶음의 전달이나 작업 폴더 전체 봉인을 뜻하지 않는다.
