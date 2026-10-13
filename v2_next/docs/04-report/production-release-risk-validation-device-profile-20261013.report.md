# 장비 직접 식별과 현재 운영 프로파일 대조

2026-10-13 17:27–17:45 KST. **장비가 직접 반환한 모델은 SPOT+ AL**이다.
사용자의 이전 답변 “미정”과 앱 기본 문자열만 있던 상태를 실제 장비 정보 조회로 보완했다.
모드의 `7`과 `App1: AL E`도 장비 설정 HTML의 선택 항목으로 대응을 확인했다.
이후 USER_SELF가 아래 관찰 설정을 운영 기준으로 승인했다. 물리 경계 시험·최종
attestation은 별도 조건이며 **정식 출시 HOLD**다. 승인 전 원문은 별도 묶음에 보존했다.

## 장비 식별 근거

저장소의 제조사 REST API 안내서 Issue 2(2024-07-31), 2.4절 및 3.4.7절은
`GET /control?p=info`를 읽기 전용 장비 정보 조회로 정의한다. 로컬 PDF SHA256은
`c8d315fafd796075545558afcca894e0f1855fc3ba6ebc2f875e95ca1d39bf22`다.
15쪽 표의 GET 행과 응답 예시를 이미지로도 대조했다.

개발 PC의 직접 GET은 3초 연결 timeout이었다. 서버 Chrome에서 같은 장비 주소를
읽어 화면의 `"SPOT+ AL    "`을 확인하고 웹페이지 저장으로 보존했다.
저장 HTML의 출처 주석과 본문도 일치한다. 공백을 제거한 모델명은 `SPOT+ AL`이다.
이는 브라우저가 저장한 DOM이며 원시 HTTP 헤더/전송 바이트·상태 코드를 확보했다는 뜻은 아니다.

정보 화면의 일련번호·Cal 표기·펌웨어는 전날 보존 화면과 같았고 펌웨어는 40.38이다.
장비 식별자는 사적 원문에 보존했다. 정확한 부품번호·교정 성적서 유효성까지 확인한 것은 아니다.
정보 HTML은 상단을 `Type=AL`, `Name=Spot`으로 구분한다. 이전 전체 표시 `AL Spot`을
사용자 이름 하나로 단정하지 않는다. 모델 판정에는 별도 정보 endpoint의 응답을 사용한다.

## USER_SELF가 승인한 관찰 프로파일

다음 값은 장비 UI에서 읽어 파일로 보존한 설정이다. USER_SELF가 직접
“현재 관찰 설정을 운영 기준으로 승인”이라고 답했다. 동적 표시값·비활성 저장값과
관찰 시각의 한계는 그대로 유지한다.

| 항목 | 실제 관찰값 | 근거/범위 |
| --- | --- | --- |
| 모델 | SPOT+ AL | 장비 정보 GET |
| 측정 모드 | App1: AL E, 선택 value=7 | Settings HTML과 앱 진단 appnumber=7 일치 |
| 온도 범위/단위 | 200–900°C / C | Info/Settings |
| 방사율 | App | E1/E2 입력은 비활성; 당시 표시값 0.061/0.056은 고정 설정 승인값으로 취급하지 않음 |
| Background | 사용 안 함, 저장값 0°C | Settings |
| Process Window | 사용 안 함, Window Obsc. 저장값 12.0% | 비활성 기능의 저장값과 적용값 구분 |
| 출력 | 4–20mA; 4mA=200°C, 20mA=800°C | I/O, 앱 설정 값과 일치 |
| Logic / Scan | N-Open / 사용 안 함 | I/O |
| CMD In / Out | ----- / Alarms | I/O |
| Low/High Target | 모두 사용 안 함; 저장값 200/700°C | Alarms |
| Low/High Instrument | 모두 사용 안 함; 저장값 0/60°C | Alarms |
| Low Signal | 사용 안 함; 저장 임계값 2% | Alarms, 앱 설정과 일치 |
| Output Time | 100ms | Info/Time Functions |
| Limiter·Averager·ModeMaster·Peak Picker·Averager 2·Ratio Raw | 모두 사용 안 함 | Time Functions; Averager 2 외 5개는 앱 metadata와도 대조 |
| Averager / Averager 2 저장값 | 각 1 values | 비활성 상태 |
| Focus | 6071mm | Info 표시; 실제 광학 조준/정확도 시험은 별도 |
| 통신 대상 | 앱 SPOT 주소와 장비 조회 주소 일치, HTTP 사용 | 사적 기록에 정확한 주소 보존 |

화면별로 순차 조회한 결과이며 장비 전체의 원자적 snapshot은 아니다.
각 HTML과 연결 리소스 28파일을 개발 PC로 복사하고 공유 사본 전/후·개발 사본 해시를 대조했다.
장비 폼의 적용 버튼·PUT·설정 변경 요청은 실행하지 않았다.

## 앱 기록과의 연결

17:36:52/17:44:56 KST의 `/health`, `/api/spot/config` 총 4개 GET은 HTTP200이었다.
이 두 표본은 뒤쪽 출력/알람/시간 화면 조회를 전후로 한다. 모델/Info/Settings 조회 전체를
둘러싼 시작·종료 표본이라고 확대하지 않는다.

- 두 표본 모두 Running/REAL, 운영 build `541d701d544eea6a8a4e4836047077eaf9cfaf30`.
- logger `e9a785c0…`, SPOT `efca4313…` 동일. CSV 카운터 223,821→225,927,
  이미지 written 44,480→44,913, drop 173→173, writer failure 0→0.
- 설정 SHA256 `55ea6a48ea1480891f8eeebf60969e3a25791335614aea5ab7c250466b31b220`,
  fingerprint `f84f9d9ddc3b958b1048cbf7bba37933d9e9e83e5b98ba666c6326154c2f74d5` 동일.
- effective operator/comparator false, fingerprint_mismatch는 유지됐다.
  수동 장비 조회 성공이 앱의 `device_config_readback_status=not_supported` 구현을 바꾸지는 않는다.

17:45 KST 화면에서 운영 앱 Running으로 복귀한 것을 확인했다. 제품60322·금형9,
최근 적용16:39:04는 당시 화면의 관찰값이다. 변경 주체는 확인하지 않았으며 Codex가 적용하지 않았다.
기존 drop173의 원인·영향·처리는 이번 조회로 종결되지 않는다.

## 승인과 기술 QA의 구분

출시 계획 R3의 “승인된 장비 식별·모델·모드·온도 범위·방사율·LowSignal·comparator·통신 조건” 중,
이번에는 장비 모델 및 모드 대응을 확인하고 검토 가능한 현재 설정표를 확보했다.
USER_SELF는 **위 관찰 설정을 현장의 운영 기준으로 승인**했다.
이 승인은 물리 LowSignal 경계 comparator 시험, 교정 정확도, 최종 후보의 같은 build/fingerprint
attestation 또는 전체 출시 QA의 통과를 대신하지 않는다.

1. USER_SELF의 관찰 프로파일 운영 기준 승인 완료. 동일 승인 질문을 반복하지 않는다.
2. 실제 LowSignal 경계 미만/같음/초과 근거와 최종 fingerprint 확인을 별도로 확보한다.
3. 적용 전 조건을 충족한 같은 1.0.28 후보의 현장 QA·정상 시작3회·15/120분·종료 delta를 수행한다.
4. 실제 승격·적용 확인 뒤 운영/다음 롤백 기준을 갱신한다.

승인 원문·질문 식별자·승인 대상 보고서/장비 대조 기록의 SHA256은
[승인 기록](C:/Users/user/Desktop/SmartFactory/PDCA_PROFILE_APPROVAL_20261013_969c8d76/approval.json)에 있다.
기존 장비 조회 묶음의 PENDING 기록과 해시는 당시 상태로 보존하며 재작성하지 않았다.
이 답변으로 장비 설정 변경·알람 활성화·미검증 항목 PASS·설치 전 조건의 예외를 만들지 않는다.

## 검증

`read_app.py before/after` actual exit0, 수정된 `review.py` exit0, Ruff F/E9 exit0.
초기 reviewer의 잘못된 metadata 키 `analog_low_c`는 KeyError·exit1로 보존했다.
실제 키 `spot_analog_4ma_c`/`spot_analog_20ma_c`로 수정하고 원본 사본을 재사용해
해시·폼 선택값·API identity·모드/범위/알람/필터 대조를 완료했다. 제품 오류로 분류하지 않는다.
제품 변경이 없어 health/build/NSIS를 반복하지 않았다.

[원시 대조 기록](C:/Users/user/Desktop/SmartFactory/PDCA_DEVICE_INFO_20261013_e1c047c0/review.json)과
[실행 안내](C:/Users/user/Desktop/SmartFactory/PDCA_DEVICE_INFO_20261013_e1c047c0/README.md)를 보존한다.

선택한 닫힌 증거45파일(manifest 포함), 원문1,847,695바이트를
`Z:/SmartFactory/20261013/records/PDCA_DEVICE_INFO_e1c047c0`에 복사·대조했다.
manifest SHA256은 `9290604178e4b67eebc31da433561faa8aa927adb863a1706885e3ce508e0295`다.
이는 공유 보존이며 서버 설치·실행 묶음 전달이 아니다.
