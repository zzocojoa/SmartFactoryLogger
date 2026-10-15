# 1.0.29 health 진단 후보 패키지 검증

작성일: 2026-10-15. 상태: **패키지·격리 설치/lifecycle/데이터 검증 기록 확보, 기존 버전 오류로 전체 검토 HOLD, 출시 HOLD**.

현장 `/health` 203.1356ms 실패의 내부 처리 구간을 구분하기 위해 추가한 선택적 진단을
새 후보에 포함했다. 이전 1.0.28 설치본과 구별하도록 버전만 1.0.29로 갱신했다.
200ms 기준과 기존 현장 FAIL을 유지하며, 이번 결과가 실제 지연 원인 확인을 뜻하지 않는다.

## 산출물과 출처

| 항목 | 확인값 |
|---|---|
| 버전 | 1.0.29, 미서명 내부 운영 후보 |
| clean build commit | `acaf77d95101a050f4d3ecd76125d3502036f5a7` |
| 설치본 | `source/v2_next/dist/smart-factory-logger-v2 Setup 1.0.29.exe` |
| 설치본 크기 | 164,824,610 bytes |
| 설치본 SHA256 | `3394a23de82f0d40749f020af320592a33cd9630113ba02b1e40f63f41549de7` |
| 실제 Authenticode | 설치본·Electron 앱·backend 모두 `NotSigned` |
| backend manifest | 1,740 files, `85b6585bec74540f692ff6ac29e42cdbd85197ceb1c6e9b2bdda4809409ceba3` |
| 설치본 추출 payload | 1,867 files / 563,455,491 bytes; unpacked build와 전 파일 동일 |
| 소스 보관 | `source-acaf77d9.zip`, 1,168 tracked files; commit/blob 및 clean checkout 대조 |

이 표의 상대경로 기준과 원문 증거 위치는
`C:/Users/user/Desktop/SmartFactory/PDCA_HEALTH_BUILD_20261015_268acb39`다.
`candidate-verification.json`은 27,272 bytes, SHA256
`1546a16e44dc87b665d79795d9daaf8be78edf273328b1c43e36e6d32475c21b`다.
기존 고정 묶음·서버 설치본·운영 및 롤백 기준은 변경하지 않았다.

## 실제 실행·확인

- 새 격리 checkout에서 npm lock과 Python 출시 lock을 설치했다. Python40개 wheel의 버전/해시가
  lock과 같고 `pip check` exit0. 빌드 뒤에도 Python package 목록은 같다.
- 최종 `npm run health` exit0: 의존성15, Electron100, 프런트 계약9, 프런트437,
  backend931검사 중 기존 private F01 fixture1건 skip. 타입/린트/QA selftest 완료.
  비공개 자료가 없는 F01 검사는 완료로 계산하지 않는다.
- 출시 환경에서 소비기7검사·실제 HTTP2검사·별도 프로세스1검사도 각각 exit0.
  별도 프로세스의4개 요청 native 연결과 정상 exit0, 잔존/강제 종료 없음 확인.
- `scripts/deploy.ps1` 및 미서명 `npm run dist -- --win nsis --x64
  -c.win.signExecutable=false -c.forceCodeSigning=false --publish never` 각각 exit0.
- 설치본을7zip으로 추출하고 payload 전 파일·양쪽 frontend50파일·backend manifest/provenance·
  Electron11개 실행 소스를 대조했다. 빌드 checkout은 검증 후에도 clean이다.
- 추출된 backend를 별도 AppData·합성 loopback 장비·18029포트에서 실행했다.
  일반 health1건에는 timing 헤더가 없고 진단4건은 외부 native 생성 식별자와 함께
  `REQUEST_AND_NATIVE_CLOCK_BOUND`였다. 보관 원문을 다시 읽은 검산도 동일했다.
- 앱의 인증된 정상 종료 API를 호출해 실제 process handle exit0을 받았다.
  begin/final 종료 영수증 해시·동일 세대·단계 종료0을 검산했다. 영수증 자체의
  `process_exit_observed=false`, `installation_clearance=false`는 유지하고 외부 종료 관찰과 구분한다.
  알려진 자식0, 잔존0, 포트0, 강제 종료 없음. 시스템 로그 ERROR0, crash 로그 empty.
  종료 후 native 조회의 UNAVAILABLE(winerror31)만으로 부재를 판단하지 않았으며,
  별도 process 목록과 포트 목록도 비어 있음을 기록했다.
- 시험 전후 추출 payload1,867파일이 동일했다. 합성 데이터와 로그는 실행별 새 폴더에 보존했다.

빌드 로그에는 과거에도 있던 zod 주석 및 optional tzdata 경고가 있다.
7zip의 executable tail 경고는 원문에 남겼으며 installer 전체 해시와 embedded archive의
시작 offset·크기·tail 합계를 검산했다. 이 검산은 설치 프로그램 실행 시험을 대신하지 않는다.
처음 C: 여유 공간이0.9GB까지 관찰돼 빌드를 보류했으며 이후24.9GB 확인 뒤 시작했다.
공간이 회복된 원인은 확인하지 않았고 이번 작업에서 기존 파일을 삭제하거나 이동하지 않았다.

## 실행 상태와 남은 체크리스트

1. 이 **동일 installer SHA**의 격리 설치·업그레이드·재시작·복구와 Electron 실제 lifecycle 검증을 수행했다.
   아래 후속 결과의 기존 1.0.26 오류를 보존하며, 전체 검토를 PASS로 바꾸지 않는다.
2. 새 candidate에 맞춘 제한 진단을 exact payload/listener/session/native generation 및 같은 실행 ETW와
   연결하고, 원격 UI 가용성을 확인한 뒤 서버 로컬 최종 폴더까지 전달한다.
3. 실제 현장 지연 원인을 확인·보완한 뒤 영향받은 현장 QA를 수행한다. 같은15분 시험을 통과할 때까지
   반복하거나200ms 기준을 늘리지 않는다. 선행 조건 전120분 시험과 운영 승격은 진행하지 않는다.

위 빌드 단계에서는 Electron 코드 일치만 확인했다. 이후 실제 실행·설치·복구 결과는 아래에
구분해 기록한다. 서버 접근·변경, 실제 장비 물리 시험은 수행하지 않았다.
현장15분 FAIL/120분 미시작/물리 경계 NOT_TESTED/전체 데이터 미결/R1–R6 및 출시 HOLD는 유지한다.

## 2026-10-15 동일 설치본의 격리 설치·실행·복구

네트워크·클립보드·장치 전달을 차단한 새 Windows Sandbox에서 실행했다.
입력805파일/378,494,001bytes는 읽기 전용이며 실행별 새 출력 폴더만 쓰기 가능했다.
guest의 WDAGUtilityAccount/Virtual Machine/IPv4 loopback과 입력 전체 해시를 확인한 뒤
guest 로컬 사본을 다시 검산했다. Python3.12.6 x64/Pillow12.3.0/psutil7.2.1을 사용했다.
실제 장비 대신 loopback 통신 응답을 제공했으며 제품 driver/lifecycle 코드는 교체하지 않았다.

| 실제 절차 | 결과 |
|---|---|
| 1.0.29 새 설치 및 앱 실행 전 제거 | NSIS/제거 각각 exit0, payload1,867파일·등록·바로가기 일치 |
| 1.0.26 설치 → 수집 → 정상 종료 | installer0, Electron0/backend0, CSV321행·이미지66개 |
| 1.0.29 업그레이드 → 수집 → 정상 종료 | installer0, Electron0/backend0, CSV322행·이미지67개 추가 |
| 1.0.29 재시작 → 수집 → 정상 종료 | Electron0/backend0, CSV314행·이미지67개 추가, 이전 history cursor reset 확인 |
| 1.0.26 복구 설치 → 수집 → 정상 종료 | installer0, Electron0/backend0, CSV315행·이미지66개 추가 |

업그레이드와 복구 설치 전후의 설정·프로필·데이터 바이트가 동일했다.
각 앱 실행은 약74–75초이며 건강 상태/API/이미지/작업 정보 표본15개씩 총60개를 확인했다.
이는 현장15분 성능 시험이 아니다. 네 실행 모두 잔존 프로세스·8000수신 포트가 없었고,
강제 종료를 사용하지 않았다. 후보 두 실행은 renderer의 요청 정리 완료가 backend 종료 시작보다 앞섰다.

### 보관 결과 재검산과 실패 범위

- `execute_matrix.py`: host CLI/guest/native child 모두 exit0, 전체408.265초.
  의도적으로 exit7을 반환한 대조 실행으로 종료 코드 수집도 확인했다.
- `review_matrix.py`: **exit1, HOLD_REVIEW_FINDINGS**, 140항목 중136통과/4실패.
  실패는 네 단계의 누적 ERROR 로그 검사다. 1.0.26 최초 실행 종료 때
  `/api/spot/live_image.jpg`의 `502 / shutdown` 기록1개, 복구 후 종료 때2개가 추가됐다.
  후보1.0.29 두 실행의 추가 ERROR/traceback은 각각0이다. 기존 기록을 지우거나
  누적 검사 기준을 완화하지 않았다. 이는 네 개의 독립된 후보 결함이라는 뜻도 아니다.
- 동일 clean 후보 소스의 `validate_csv_v2_shadow.py`4회와
  `validate_spot_image_files.py`4회가 모두 exit0였다. CSV1,272행,
  SPOT observation98행, 최종 이미지266개를 대조했다. 이전 CSV/metadata/이미지와
  fact append prefix 보존, manifest/hash, 저장 완료 및 writer failure/drop/잔여 queue0을 확인했다.
- CSV 검사는 위치 항목 `MainRamPosition_D0010`, `ContainerPosition_D0012`가 비었다는
  경고를 남겼다. 제품 교체·공정 단계 event fact는 이번 입력에서0행으로 실측 검증하지 못했다.
  이미지 연결 후처리와 실제 서버 전체 데이터 판정도 이번 검사의 범위 밖이다.
- 후보 실행 두 차례의 일반 health2건에는 timing 헤더가 없었다. 진단8건은 외부에서 읽은
  backend PID/생성 FILETIME과 전후 listener 소유자를 확인하고 raw body/header를 보관했다.
  보관 원문을 다시 읽은 strict consumer8회가 모두 `REQUEST_AND_NATIVE_CLOCK_BOUND`였고
  실행 시 결과와 같았다. ETW coverage·정확한 CPU 시간·현장 지연 원인 판정은 아니다.
- `finalize_matrix.py` exit0: 앱/backend/fixture Python과 관련 포트가 모두 없는 상태를 확인했다.
  출력1,002파일/12,979,519bytes를 해시로 보존한 뒤 이번 Sandbox만 종료했고,
  종료 후에도 모든 결과 파일이 동일했다. `record_verification.py` exit0은 위 증거의
  일관성 확인이며 전체 검토 exit1을 덮어쓰지 않는다.

원문 실행 루트: `C:/Users/user/Desktop/SmartFactory/PDCA_HEALTH_NSIS_20261015_38b56536`.
`matrix-verification.json`: 51,737bytes, SHA256
`05672d116ad5e93ee147b091f13dcec563fd0239bc47740c61f97e5c1e66c65a`.
`closed-output-manifest.json`: SHA256
`36462e705b51d853aeee842be58392c31b850f262d6b67afc107dcacf2abfa44`.

제품 코드·설치본을 변경하거나 다시 빌드하지 않았다. 빌드 checkout은 여전히 clean
`acaf77d9`다. 따라서 제품 전체 health 검사를 중복 실행하지 않았고 앞선 실제 결과를 연결했다.
이번 작업의 도우미 구문/import·실제 guest 실행·검산은 변경한 최종 바이트로 수행했다.
실제 화면의 시각적 상태·프레임 성능·장시간 현장 QA는 확인하지 않았다.
다음은 동일 후보에 맞춘 제한 현장 진단 준비와 서버 로컬 전달이며,
기존 서버 설치본·운영/롤백 기준·200ms 기준·출시 HOLD는 유지한다.

## 2026-10-15 제한 진단의 설치본·요청 연결 구성요소

`field_installation_binding.py`와 `field_configuration_binding.py`에 위 1.0.29의 정확한
build/installer identity를 명시적으로 선택하는 경로를 추가했다. 기존 기본값은 1.0.28이며,
입력 manifest에서 버전을 자동 선택하지 않는다. 다른 설치본·provenance·실행 버전의 혼합은
거부한다. 기존 파일 잠금·추가 파일·hardlink/reparse 및 설정 fingerprint 검사는 유지한다.
기존 사용자 운영 프로파일 승인은 계속 유효하지만, 새 build의 실제 설정 확인값에는 새
fingerprint가 필요하다. 1.0.28 확인값을 복사해서 1.0.29 확인 근거로 사용하지 않는다.

새 `field_health_diagnostic.py`는 한 health 진단 요청의 전후 process/listener와 외부에서
확인한 backend 생성 FILETIME을 대조한다. 원문 body/header·요청 ID·native 시계를 엄격히
검사한 뒤 정확한 build와 SPOT/logger 실행 세대가 같을 때만 `REQUEST_AND_RUNTIME_BOUND`를
기록한다. 원문은 후속 검사 실패 때도 가능한 범위에서 보존한다. 느린 요청도 증거로 남기며
이 상태에 성능 통과 의미를 부여하지 않는다.

| 실행한 검사 | 결과·범위 |
|---|---|
| `test_field_installation_binding` | 25검사, exit0; 실제 Windows 잠금·process/listener 및 거부 조건 |
| `test_field_configuration_binding` | 11검사, exit0; 제품 serializer·실제 파일/HTTP 및 설정 변경 |
| `test_field_health_diagnostic` | 6검사, exit0; native/process/HTTP 합성 입력과 실제 strict timing 소비기 |
| `test_field_generation_binding` | 8검사, exit0; 실제 Windows 환경/인증 loopback 및 비밀값 보존 방지 |
| `test_field_observation` | 27검사, exit0; 실제 소유 job·중단/시간 제한/장애·잔존 처리 회귀 |
| 마지막 Low Signal OFF 검사 보완 후 해당 메서드 재실행 | 1검사, exit0; 물리 NOT_TESTED/정식 HOLD 유지 |
| 추출된 실제 1.0.29 payload의 새 identity 경로 검산 | 1,867파일/563,455,491bytes 잠금·종료 전 재대조; 이전 기본 경로는 거부 |

총77개 서로 다른 검사, 마지막 재실행을 포함한 실행 수는78개다. 출시 lock의 Python을
사용했다. 변경6파일의 프로젝트 설정 Ruff 및 `git diff --check`도 exit0였다.
제품 코드와 설치본은 바뀌지 않아 전체 health·빌드를 반복하지 않았다.
검사 stdout/stderr·종료 코드·환경·최종 소스47파일 사본과 원문 해시는
`C:/Users/user/Desktop/SmartFactory/PDCA_HEALTH_BIND_20261015_bd4e31d6`에 보존했다.
`record_verification.py` exit0은 보존 검사 기록의 일관성 확인이다.
`verification.json`: 9,819bytes, SHA256
`5c2f3e9004b7335e19dbe9297f6394c610b6940a9164253fc4cbf18fda08878d`.
시험용 junction/hardlink 디렉터리는 재귀적으로 따라가거나 정리하지 않았다.

### 현장 실행 전에 남은 연결 작업

이 단계는 구성요소 검증이며 새 현장 실행 명령은 아직 없다. 새 진단 함수를 실제 앱에
호출하는 통합 검사도 미실행이다. 기존 `field_runner`/관찰/종료 경로는 기존 1.0.28 대상으로
남아 있어 그대로 새 후보의 현장 실행기로 사용하지 않는다.

1. 설정 및 인증된 실행 세대 확인과 새 요청 함수를 소유 collector의 제한 시간·출력 보존에 연결한다.
2. 이미 실행 중인 backend thread의 생성 세대와 ETW rundown을 연결하고, 요청 구간의 trace
   coverage를 검증한다. 앞선 짧은 fixture의 시작·종료 event 요구를 장시간 실행 thread에
   그대로 적용하지 않는다. native 생성 FILETIME은 ETW event timestamp를 대신하지 않는다.
3. 독립 WPR 감시 프로세스의 소유권·시간 제한·종료/정리 절차를 새 수집기와 함께 검증한다.
   기존 8초 로컬 시험 helper의 범위·제한을 조용히 늘리지 않는다. memory trace의
   `EventsLost=0`만으로 요청 전 구간이 남았다고 판단하지 않는다.
4. 원격 UI 가용성을 확인하고, 검증한 전체 묶음을 서버 로컬 최종 폴더까지 전달한다.

이 단계에서 실제 앱/Windows 추적 실행·서버 조작·설치본 재생성은 없었다.
기존 15분 FAIL/120분 미시작/물리 NOT_TESTED/출시 HOLD와 이전 전체 검토의 실패 기록을 유지한다.
