# 1.0.29 health 진단 후보 패키지 검증

작성일: 2026-10-15. 상태: **패키지·격리 설치/lifecycle/데이터 검증 기록 확보, 기존 버전 오류로 전체 검토 HOLD, 출시 HOLD**.

현재 현장 절차는 사용자의 백업 생략 지시에 따른
[새 전체 백업 없는 교체 검증 기록](production-release-risk-validation-no-copy-install-20261015.report.md)으로 이어진다.
아래 외장 저장장치 준비·백업 실행 대기 기록은 당시 이력이며 현재 실행 요청이 아니다.
기존 백업 명령을 재실행하지 않는다. 16:32 KST 현재 앱은 정상 종료됐고 원본 재검산이 진행 중이며,
1.0.29 서버 설치는 아직 시작하지 않았다. 기존 실패와 출시 HOLD는 유지한다.

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
2. 제한 진단의 payload/listener/session/native generation·설정 연결은 아래 실제 격리 검증을 마쳤다.
   다음은 같은 실행 ETW·독립 감시 프로세스 연결과 coverage 검증, 원격 UI 확인 및 서버 로컬 전달이다.
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

## 2026-10-15 소유 수집기와 실제 설치 앱의 통합 검증

`field_health_collection.py`에서 외부 고정 payload/설정 기준, 인증된 backend 실행 세대,
native 생성 FILETIME과 진단 요청 함수를 연결했다. 기존 supervisor의 gated child/job과
시간 제한을 사용하며 앱은 그 job에 넣지 않는다. 요청 전후 설정·실행 세대를 확인하고
원문·manifest·종료 결과를 보존한다. 개발 API의 수집 구간은 최대30초, 요청 간격은2초다.
누락된 시점을 뒤늦게 채우거나 실패한 요청을 자동 재시도하지 않는다. 200ms 초과 요청도
연결 가능한 진단 증거로 남으며 `BOUND_WINDOW_CAPTURED`는 현장 성능 통과가 아니다.

변경 모듈의 합성 실패 전파8검사와 Ruff는 각각 exit0였다. 초기 시험 fixture의 기준 파일
누락은 오류로 남겼고, placeholder 파일을 추가한 최종 상태에서8검사를 다시 실행했다.
중단·설정/실행 세대 변경·native 조회 실패·reference 종료 검사 실패·시간 초과에 따른 slot
누락·결과 변조를 확인했다. 기존 supervisor 구현과 제품 코드는 변경하지 않았다.

별도 오프라인 Windows Sandbox에 **동일 1.0.29 installer**를1회 설치해 실제 Electron/backend로
실행했다. loopback 장비와 시험 전용 설정 확인값을 사용했으며 실제 현장 장비 승인이 아니다.
최종 runtime의 host/guest exit0, 수집 worker exit0, 정상 앱/backend 종료 각각0이었다.
잘못된 backend 생성 FILETIME을 넣은 대조 실행은 probe0건/worker exit1로 거부됐고,
두 collector job 모두 active process0·강제 종료 없음이었다. 그 뒤 같은 앱 실행에서
6초 구간의 진단3건이 모두 `REQUEST_AND_RUNTIME_BOUND`였다.

원문을 다시 읽어 해시·요청 ID·native 시계·실행 세대와 전후 설정을 재검산한 결과도 일치했다.
3건의 client 시간은4.9869/7.2946/7.3821ms다. 이 소수 격리 표본은 현장15분 성능 결과를
대체하지 않는다. payload1,867파일과 정확한 해시의 NSIS uninstaller1파일을 종료 전 재대조했다.
최종 system ERROR/traceback0, crash log0bytes, 앱/backend/fixture와 관련 수신 포트 부재를
확인했다. 출력338파일/4,376,547bytes를 검산하고 Sandbox를 종료한 뒤 동일 바이트를 확인했다.

시험 준비의 실패도 보존했다. 로그인 준비 전 CLI2회 거부, 과대 설정 reference의 수집 거부,
격리 Python import 경로 보완, fixture의 UTC 표기 `+00:00`→제품의 `Z` 정규화가 있었다.
최초 크기 제한32768과 정확한 설정 비교는 유지했다. 정상 종료를 확인한 뒤 같은 설치 앱을
사용했으며 재설치하지 않았다. 검토기의 파일 수에는 payload 외의 고정 uninstaller1개를
구분했고, 종료 확인은 보존된 초기 실패 summary와 최종 성공 실행을 구별하도록 수정했다.
이전 실패·로그·고정 input은 덮어쓰지 않았다.

원문·실행 종료 코드·최종 소스와 후속 도우미는
`C:/Users/user/Desktop/SmartFactory/PDCA_HEALTH_COLLECT_20261015_1ee93334`에 보존했다.
`review_collection.py`, `finalize_collection_r2.py`, `record_verification.py`는 각각 exit0였다.
`verification.json`: 24,248bytes, SHA256
`8eadbbba7794a003c03fded89552a4570b55623305a78e20ea1414227bdc52a3`.

남은 현장 선행 작업은 보호된 외부 실행기, 같은 실행 WPR 감시·요청 연결, 이미 실행 중인
thread의 ETW rundown/coverage 검증과 서버 로컬 전달이다. 이번 시험에서는 WPR와 서버를
사용하지 않았다. 미서명 후보의 build/installer와 운영/롤백 기준은 유지하며 전체 health·
빌드를 반복하지 않았다. 기존 15분 FAIL/120분 미시작/물리 NOT_TESTED/출시 HOLD는 그대로다.

## 2026-10-15 실행 중 스레드의 ETW 구간 연결 검증

`field_thread_coverage.py`에 native PID/TID·생성 FILETIME·QPC 경계와 선택된 ETW 이벤트를
연결하는 순수 분석 함수를 추가했다. 정확한 외부 process 생성 세대와 동일한 전후 thread
생성 세대를 요구하며, 추적 중 새로 생성된 thread와 추적 전부터 존재한 thread를 구분한다.
후자의 Start event를 만들어 내지 않고, 구간 이후의 동일 PID/TID End 또는 DCEnd 기록을
요구한다. 중복 lifecycle·다른 PID·모순된 Start·CPU 전환 누락·동시 실행·모호한 경계를 거부한다.

DCStart/DCEnd는 추적 시작/종료 시 살아 있는 thread의 열거이며 생성/종료 시각을 뜻하지 않는다.
근거: [Microsoft Thread event 설명](https://learn.microsoft.com/en-us/windows/win32/etw/thread-v2-typegroup1).
native 생성 FILETIME을 ETW QPC로 치환하지 않는다. 모든 CPU의 전환 기록이 구간 앞뒤를
포함해야 하며 `EventsLost=0`만으로 ring buffer의 구간 보존을 인정하지 않는다.
CSwitch residency에는 미측정 DPC/ISR가 포함될 수 있으므로 정확한 thread CPU 시간으로
보고하지 않는다. [Microsoft CSwitch 분석 옵션](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/cswitch).

| 실제 검증 | 결과·한계 |
|---|---|
| `python -m unittest -v test_field_thread_coverage` | 11검사 exit0. 새/기존 thread, End/DCEnd, 재사용·PID/시계·구간 누락·loss·CPU 연속성 거부 |
| 기존 고정 request trace 재분석 | 31구간. 기존 30구간과 추적 전에 생성된 main thread 1구간; 후자는 실제 End event로 연결 |
| 새 오프라인 Sandbox 첫 기록 | capture/정리 exit0, 연결 검사는 exit1. CPU7–11의 첫 전환이 구간보다 늦어 거부; 원문 보존 |
| 입력을 바꾼 두 번째 Sandbox 기록 | capture/정리 exit0. 구간 전후에 각 CPU에서 20ms의 제한된 spin/sleep을 수행한 fixture. 분석 기준은 동일 |
| 두 번째 기록의 실제 DCEnd 연결 | 추적이 끝난 뒤에도 살아 있는 thread의 195.0097ms 구간 연결. residency40.0874ms, 나머지154.9223ms; CPU 시간·대기 원인 판정 아님 |
| 독립 원문 XML 재검산 | per-thread switch-in/out 계산과 per-CPU 인접 event 계산의 정수 구간이 32구간 모두 동일, exit0 |
| 최종 소스 Ruff | 프로젝트 루트 `pyproject.toml`로 선택2파일 exit0. 앞선 잘못된 `backend/pyproject.toml` 경로 호출은 lint 실행 전 exit1 |

두 번째 기록의 선택9,696이벤트는 두 해석 경로에서 값·payload·순서가 일치했고 switch chain
gap0이었다. 전체 tracerpt 해석 오류1,430개와 TraceEvent unhandled96개는 남아 있어 전체
추적 품질은 **INCOMPLETE_OR_UNUSABLE**다. 선택 구간 연결을 전체 추적 품질 PASS로 바꾸지 않는다.
격리 fixture는 관리자 권한으로 동작했고 CPU 전환을 추가했으므로 실제 앱 통합·일반 요청
성능·현장 검증을 대신하지 않는다. 실제 현장에서 CPU가 조용하면 같은 coverage 거부가 발생할
수 있다. 첫 실패를 지우거나 현장 수집에 부하 발생 코드를 자동 추가하지 않는다.

호출자는 ETL·독립 crosscheck·원문 요청과 native anchor를 같은 실행의 해시로 먼저 묶어야 한다.
아래 함수 자체는 그 파일 provenance를 대신하지 않는다.

```python
schedule = checked_schedule(verified_selected_rows, {begin["tid"]}, header["NumberOfProcessors"])
window = join_native_window(schedule, begin, end, header,
    expected_pid=externally_observed_pid,
    expected_created_filetime=externally_observed_creation_filetime)
```

관련 프로세스6개의 정확한 생성 세대와 고유 WPR instance2개가 모두 사라졌음을 확인했다.
출력93파일/4,277,034bytes를 검산하고 이번 Sandbox만 종료한 뒤 바이트가 같은지 확인했다.
`finalize_sandbox.py`, `record_verification.py`는 각각 exit0였다. 단위 검사와 Ruff 기록은
Codex 실행 도구의 실제 출력/종료 코드에서 보존한 관측 기록이며 별도 raw 콘솔 파일은 없다.
실제 capture/export/독립 검산/종료 확인은 stdout·stderr·종료 코드 파일을 보존했다.

증거 루트: `C:/Users/user/Desktop/SmartFactory/PDCA_THREAD_COVERAGE_20261015_6f9c9e24`.
`verification.json`: 21,868bytes, SHA256
`2cea6ae8a2b3b62e2c44514e04c3c65c42efd434100b3985dc3eb2894d36b647`.

다음은 **실제 설치 앱의 health 수집과 WPR를 같은 실행으로 연결하는 외부 실행기**다.
독립 guard의 새 계약·제한 시간·원문 보존·종료/정리 및 무부하 조건의 요청 coverage를 함께
검증한 뒤 서버 로컬 전달을 진행한다. 기존8초 로컬 helper와 고정 증거는 변경하지 않았다.
제품/설치본/서버 변경이 없어 전체 health·빌드는 반복하지 않았다. 실제 field15 FAIL,
120분 미시작, 물리 NOT_TESTED, 지연 원인 미확정, 출시 HOLD와 기존 롤백 기준은 유지한다.

## 2026-10-15 실제 health 요청과 동일 실행 WPR 연결

`field_health_trace.py`와 `invoke-health-trace.ps1`에 별도 실행 계약을 추가했다. 기존 수집기의
설정·실행 세대 확인 뒤 WPR 준비 신호를 받고, 6초/3요청을 기록한 뒤 추적 저장·정리를
확인해야 최종 설정·payload 재검산으로 진행한다. 수집기는 기존 job 안에 있고 WPR 감시기는
독립 프로세스로 동작한다. 고정30초 guard, 정확한 native 생성 세대, 고유 instance와 고정
package/contract/ready/lease/ETL 해시로 연결한다. 이전8초 helper·프로파일·증거는 바꾸지 않았다.
앱 시작·종료·설치를 제어하는 현장 실행기는 아직 아니며 현재 API 범위는 로컬 통합 진단이다.

| 최종 검증 | 실제 결과 |
|---|---|
| 수집기·연결 단위 검사 | `python -m unittest -v test_field_health_collection test_field_health_trace`, 17검사 exit0 |
| PS5.1 계약/실패 전파 검사 | `test_health_trace_validation.py --output <새 폴더>`, 6그룹 driver exit0. 일반 권한·32비트 실행 거부의 child exit1은 예상 결과 |
| 변경 Python 5파일 Ruff | 프로젝트 `pyproject.toml` 사용, exit0 |
| 실제 동일1.0.29 설치 앱과 추적 | installer0, host/guest0, 수집 worker0, trace coordinator/guard0. 앱/backend 두 실행의 정상 종료 각각0 |
| 독립 guard 실제 시험 | 제어 프로세스 exit23·30초 시간 제한 모두 추적 저장/정리 확인 |
| 수집기 실패 실제 시험 | 합성 collector의 exit23 및 중단 통보 각각 coordinator exit1, `health-trace-window-incomplete`; guard0/정리 완료, 성공 통보 없음 |
| 요청·스케줄링 연결 | 실제 health3건의 loop/worker/collector 총9구간. native 생성 세대·QPC·DCEnd 연결 및 원문 XML의 별도 per-thread 계산과 정수 구간 일치, exit0 |
| 닫힌 데이터 검증 | 실제 candidate 소스의 CSV2회·이미지2회 validator 모두 exit0. 새 wide CSV55/165행, 최종 누적 관측17·이미지45 |

첫 PowerShell 합성 검사는 fixture의 `$state`가 기존 lifecycle 함수의 지역 변수와 충돌해
exit1이었다. fixture 이름만 바꾼 최종6그룹 결과를 확인했고 이전 실패를 보존했다.
전체 요청 시간은7.7410/5.9310/7.1928ms다. 별도 CPU 부하를 추가하지 않은 오프라인 장비
fixture의 소수 표본이며, 현장200ms 기준·기존15분 실패를 대체하지 않는다. 선택 이벤트
48,813개(CSwitch31,970/Ready15,058/Thread1,785)의 값·payload·순서가 두 해석 경로에서
일치했고 CPU 전환 chain gap은0이었다. 전체 tracerpt 해석 오류1,792개와 unhandled309개는
남아 있어 전체 추적 품질은 **INCOMPLETE_OR_UNUSABLE**다. 정확한 CPU 시간·지연 원인은 미판정이다.

원문 설정 응답·실행 세대·manifest를 다시 검산했고 payload1,867개와 고정 uninstaller1개를
수집기 종료 전에 재대조했다. 두 앱 실행의 ERROR/traceback0·crash log0bytes와 정상 종료
영수증을 확인했다. CSV의 두 위치 필드 미입력 경고와 미대상 fact의 unknown은 보존했다.

**첫 Sandbox의 마지막 종료 확인에는 한계가 있다.** 실제 앱 정상 종료와 guard 두 시험의
정리 결과가 저장된 뒤, 추가 collector 시험을 시작할 때 해당 Sandbox가 목록에서 사라져
있었다. 종료 원인은 미확정이며 마지막 cold check는 미실행이다. 실패한 CLI dispatch와
관측을 `original-disposal-observation.json`에 남겼고 첫 환경 전체 종료를 PASS로 표시하지 않는다.
소실된 work의 합성 설정 reference는 보존한 초기 snapshot과 설정 시각으로 재구성한 뒤
원래 수집기에 고정한 SHA256과 정확히 일치함을 확인했다. 원본 회수와 재구성 사본을 구분한다.

추가 collector 실패 두 조건은 앱 설치 없이 별도 Sandbox에서 실행했다. 관련7개 native
프로세스 생성 세대와 고유 WPR instance2개의 부재를 확인한 뒤 해당 환경만 종료했다.
첫 환경 출력291파일/17,033,168bytes, 추가 환경96파일/4,291,863bytes를 보존·재해시했다.
두 번째 환경의 최종 cold 확인·종료는 exit0이며 첫 환경의 누락을 대신하지 않는다.

증거 루트: `C:/Users/user/Desktop/SmartFactory/PDCA_HEALTH_TRACE_20261015_07559ba3`.
`verification.json`: 27,588bytes, SHA256
`0384e5ab4b19e0f29d1fd4122b2f7f3ae2f15110032627dc45c223505f3e9e10`.
`verify_health_windows.py`, `review_health_capture.py`, `finalize_failure.py`,
`record_verification.py`는 각각 exit0였다. 앞의 세 wrapper 종료는 Codex 도구 관측 기록이며
내부 native/validator 명령은 별도 stdout·stderr·종료 코드도 보존했다.

다음 현장 묶음 체크리스트:

1. 검증된 모듈을 보호된 외부 실행기에 연결하고 실행 전에 소스·프로파일·payload·설정 기준
   원문을 결과 묶음에 보존한다. UI/controller/collector 권한과 소유 프로세스 경계를 검증한다.
2. 새 실행기의 시간 제한·실패·실제 정상 종료와 결과 회수 경로를 검증한다. 기존 조각의
   PASS로 새 실행기 전체를 통과 처리하지 않으며, 같은 제품 installer를 재빌드하지 않는다.
3. 원격 UI 가용성 및 현장 현재 앱/제품·금형을 확인하고 검증 묶음을 서버 로컬 최종 폴더까지
   전달한다. 미확인 과거 작업번호를 강제로 적용하지 않는다.

제품 코드·installer·서버·롤백 기준은 그대로다. 전체 health·빌드는 반복하지 않았다.
현장15분 FAIL/120분 미시작/물리 NOT_TESTED/출시 HOLD를 유지한다.

## 2026-10-15 보호된 6초 진단 실행기 검증

helper commit `4cf0f26bb1825efe1c2835f5648c44893a9d1f57`에
`field_health_runner.py`와 `invoke-health-diagnostic.ps1`을 추가했다. 원문 request·설정·
payload·소스·추적 프로파일을 실행 전에 새 보호 결과 폴더에 복사하고 같은 잠금 바이트를
검증한다. 수집기는 소유 job 안에서, 추적 coordinator/guard는 독립 프로세스로 실행한다.
두 결과 작성자의 종료와 로그 닫힘을 확인한 뒤 최종 manifest를 만든다. 기존 폴더 덮어쓰기,
앱 시작/종료·설치·장비 설정 변경은 이 실행기의 기능에 포함되지 않는다.

| 최종 상태 검사 | 실제 결과 |
|---|---|
| `python -m unittest discover -s scripts/field-v1028 -p test_field_health_runner.py -v` | 9검사 exit0. 보존 원문 사용·잠금, 잘못된 pin/세대/계약·출력 재사용 거부, 실패 전파 |
| `test_health_entry_validation.py --output <새 폴더>` | PS5.1 6그룹 driver exit0. 정상 소유 job 종료 및 callback 실패 시 해당 job만 정리. 일반 권한·32비트 거부는 예상 child exit1 |
| 선택 Python 3파일 Ruff | 프로젝트 설정 사용, exit0 |
| 고정 실행 파일 빌드·설명 | PyInstaller exit0, frozen true, 후보 commit·6초·HOLD 일치 |
| 오프라인 Sandbox의 실제 설치 앱 | 잘못된 package pin/프로세스 생성 세대는 exit1, WPR 시작 없음. 정상 caller/worker/coordinator/guard는 모두 exit0 |
| 동일 실행 추적 | health3건의 loop/worker/collector 총9구간을 원문 XML의 독립 계산과 대조, 정수 구간 일치 |
| 닫힌 CSV·이미지 검사 | validator4회 모두 exit0. wide CSV52/235행, 최종 누적 관측23·이미지60. 위치 필드 미입력 경고 보존 |
| 최종 종료 확인 | 정확한 프로세스 생성 세대6개 및 고유 WPR instance 부재. 앱/backend 정상 종료4건 exit0, 강제 앱 종료 없음 |

초기 PS 구문 검사는 줄바꿈 위치 오류로 exit1이었다. 해당 실패를 보존하고 구문을 수정한
최종 소스로 PS6그룹과 실제 frozen 실행을 검증했다. Python 소스는 그 수정 전후 동일하다.
새 외부 실행기를 WPR 수집 중 강제 종료하는 추가 실제 시험은 수행하지 않았다. 기존
coordinator/guard의 다섯 종료 조건 검증과 새 실행기의 정상·사전 거부·소유 job 실패 검증을
구분하며, 모든 조합의 장애 시험을 완료했다고 주장하지 않는다.

정상 요청 시간은5.2837/13.8196/5.0781ms다. 합성 loopback 장비를 사용하는 격리 시험의
소수 표본이며 현장 성능 기준 검증이 아니다. 선택43,957이벤트(CSwitch27,812/Ready14,293/
Thread1,852)의 값·payload·순서가 일치하고 switch chain gap은0이었다. 전체 해석 오류
1,859개와 unhandled142개가 남아 **INCOMPLETE_OR_UNUSABLE** 상태를 유지한다.
요청 구간 연결은 현장 지연 원인이나 정확한 CPU 작업 시간 판정이 아니다.

이번 설정 reference는 실행 전에 원본2,098bytes를 보존했다(SHA256
`664c5d43f46e03d44250749371881ae771fd980254f616408669e7d345b7dd9d`).
payload1,867개·uninstaller1개를 다시 검산했고 출력307파일/39,784,078bytes를 보존했다.
최종 cold check 후 해당 Sandbox만 종료하고 사본 해시를 재확인했다. 앞선 Sandbox의 종료
원인 미확정·cold 확인 누락 기록은 그대로 남으며 이번 결과로 소급 PASS하지 않는다.

증거 루트: `C:/Users/user/Desktop/SmartFactory/PDCA_HEALTH_ENTRY_20261015_7e735e28`.
`verification.json`: 11,000bytes, SHA256
`64fb2e7fc2f985d1dfad99d0e7a17f7ba564854a0057bed195cc2253091a87b4`.
`export_health.py`, `verify_health_windows.py`, `review_health_capture.py`,
`finalize_matrix.py`, `record_verification.py`는 exit0였다. native/validator 로그와 반환값을
보존했으며 wrapper 종료 코드는 Codex 실행 도구 관측으로도 확인했다.

배포 준비 파일 `package-r1/manifest.json`은1,758bytes, SHA256
`643d2da73d0d9c55973fd7bdaf0ac9b0ab6c068cf74d4607726dd0fedb8a7f5b`다.
frozen 도우미는16,083,544bytes, SHA256
`c6d6f5b3f6579f03602a622180a5ea55d8d8bee94163a809a49bd9f33fa3bb7c`다.
제품 commit `acaf77d9`와 installer `3394a23d…`는 재빌드하지 않았다.

12:57 KST 서버 GET6건은 모두200이며 실행 중1.0.28/`4cc7393e`, 제품60250·금형108,
Low Signal OFF, 설정 drift 없음으로 관찰했다. 현재 작업값은 API·화면 관찰이며 새로운
사용자 확인을 뜻하지 않는다. 실제 native 생성 세대와 설치 파일 전체는 이번 조회에서
재검증하지 않았다. 서버에1.0.29 설치·진단 실행은 아직 수행하지 않았다.

다음 순서: 고정 묶음을 서버 로컬로 전달 → 현재 실행 세대·설치 바이트 읽기 → 정상 종료와
최신 닫힌 백업 검산 →1.0.29용 교체·보존 확인 → 새 실행 세대/설정으로 진단 request 발행.
이전1.0.28 설치 helper나 격리 시험 request를 새 후보에 사용하지 않는다.
현장15분 FAIL·120분 미시작·물리 NOT_TESTED·출시 HOLD와 승인된1.0.26 복귀 기준을 유지한다.

### 같은 날 서버 로컬 전달·회수 검산

`prepare_delivery.py` exit0으로 진단 package·기존 후보/복귀 installer·기준 자료19파일,
345,514,402bytes를 새 `HD29_20261015_7e735e28` 폴더에 묶고 공유 사본 해시를 대조했다.
Chrome 원격 데스크톱의 서버 탐색기로 아래 경로에 복사했으며 기존 파일 덮어쓰기 없이
최종 절대경로와 최상위 파일·폴더를 확인했다.

- 전달: `Z:/SmartFactory/20261015/send/HD29_20261015_7e735e28`
- 서버 로컬: `C:/Users/user/Desktop/SmartFactory/HD29_20261015_7e735e28`
- 서버 로컬에서 회수: `Z:/SmartFactory/20261015/return/HD29_COPY_7e735e28/HD29_20261015_7e735e28`

서버 로컬 폴더를 탐색기에서 선택해 새 회수 위치로 복사하고 `verify_delivery_return.py`
exit0으로19파일의 상대경로·크기·기본 스트림 SHA256이 원본과 같음을 확인했다.
서버에서 native hash 명령을 실행한 것은 아니다. 회수 사본 바이트 검산과 화면 관찰을
구분한다. 전송 manifest는3,430bytes/SHA256
`f68763a586881bc146ba7c9df8dc68198d7eb5bfa5b2f232d2fb04c39db7a311`이다.
로컬 증거 루트의 `server-delivery-verification.json`은4,895bytes/SHA256
`84752184419bef7bebdc2e002b83acb48c044d4fab6df790f41539330ad9d650`이며 공유 `records/HD29_7e735e28`에도 보존했다.

전달 상태는 **STAGED_NOT_READY_TO_EXECUTE**다. 현장 request·설치 명령은 아직 발행하지
않았으며 위 체크리스트의 최신 native 확인·백업·1.0.29용 교체 절차가 남아 있다.
탐색기를 닫은13:15 KST 화면에서 앱 Running과 제품60250·금형108을 다시 관찰했다.
이번 전달로 서버 앱을 종료하거나 설치·설정을 변경하지 않았다.

## 1.0.28→1.0.29 설정 보존 설치 도우미 검증

후속 helper commit ad418291에서 install-health-candidate.ps1을 추가했다. 고정된 이전
library의 함수 정의만 재사용하며, 과거1.0.26→1.0.28 설치와 비교기 변경 코드는 실행하지
않는다. 현재4cc/새acaf 전체 payload와 uninstaller, 미서명 installer, 최신 닫힌 백업 및
같은 main/backend PID·UTC 생성 시각·logger를 결합한다. OFF 설정의 원본 바이트와 추가
스트림을 보존하고 새 실행 세대 attestation은 후속 단계로 남긴다.

원본 request·controller·고정 library·기준 자료를 보호 결과 폴더에 보존하며 운영 사용자
읽기 권한도 확인한다. 설치 timeout/실패 시 강제 종료·자동 재시도·자동 복귀는 없다.
과거 field-sequence approval은 그대로 보존하고 새 후보의 명시 승인으로 재표현하지 않는다.

| 검증 | 실제 결과와 한계 |
|---|---|
| test_install_health_candidate.ps1 | 최종35검사 exit0. request/경로/생성 세대/설정, 실제 child exit0·17·timeout |
| test_health_backup_entry.ps1 | 9검사 exit0. 고정 묶음, 잘못된 pin·변조·추가 파일 거부, 실제32/64비트 bootstrap→64비트 PS5.1 library-only child exit0 |
| 오프라인 Sandbox | 실제1.0.28 installer exit0→변경 없는 transaction 함수→실제1.0.29 installer exit0. CLI/guest exit0 |
| 설치 파일·등록 | 교체 전1,815개·후1,868개 기준 일치, 등록 버전1.0.29·설치 경로 확인 |
| 합성 닫힌 데이터 | 4파일·3폴더·추가 스트림3개·210bytes의 원본/사본 재검산. BOM 포함 설정133bytes와 설정 ADS10bytes 보존 |
| 서버 실행 경계 | Sandbox에서 서버 전용 top-level은 예상 exit1. 실제 서버 host/사용자 경계 통과·실제 앱 정상 종료는 미검증 |
| 종료·보존 | 앱/backend/installer/8000 부재 후 소유 Sandbox만 정리. 출력32파일/2,930,848bytes 보존 |

초기 UTF-8 BOM 파싱 실패와 PS5.1의 PSScriptRoot 기본 인수 초기화 실패를 보존하고
수정했다. JSON PID Int64 호환성과 직렬화 왕복 검사도 추가했다. 최초 Sandbox는 후보
설치 전에 중단됐다. 최초 cleanup 확인의 출력 경로 오류로는 Sandbox를 종료하지 않았고,
수정된 확인에서 cold 상태를 관찰한 후 정리했다. 최종 시험은 새 Sandbox에서 수행했다.
이를 실제 현장 정상 종료·전체 데이터 규모·성능 QA 통과로 확대하지 않는다.

검증 루트: C:/Users/user/Desktop/SmartFactory/PDCA_HEALTH_INSTALL_20261015_9c43d21a.
verification.json: 4,744bytes/SHA256
cb8a10b4edf5bc600edd4efa066655ec4997384228ac02b14d1c26de4f9dda1a.
설치 helper SHA256:
f3cdf97ac9bb84fb9a8b303dab551c7d6f21becc4f0dba1ae68c76275c7b8b0b.
고정 library SHA256:
a95ec69d7fef3371745ad32685fa10b26f858ef9f93fe1a8669c39b25e225c1a.
제품 acaf/installer3394는 재빌드하지 않았다. 변경은 현장 helper/test뿐이므로 기존 제품
전체 health를 반복하지 않았다.

### 최신 백업·설치 준비 묶음

HI29_20261015_9c43d21a의 현재 실행 단계는 백업 준비만이다. engine/wrapper는 이전
고정 바이트 그대로이고 scope 기대 버전은 현재 후보1.0.28이다. 승인 복귀541d와 현재
시험 후보4cc는 별도 필드다. PINNED_HEALTH_BACKUP_COMMAND.txt는32비트 창에서도
64비트 PS5.1을 선택하고 잠근 launcher·전체 backup manifest를 검증한다.

- backup manifest: BBE23EABDCA536ED2D582674D2B77B0435AC41C51CA68604D310A84493635D00
- launcher: 6366244f1e56c70d936cc92734e51b3b725de9cabbe65bb5a9ea5aa77105bd24
- delivery manifest: 70ba6c2bd2be69a8617c60c2fe1e58fd8df611aea7d1ea3fce77fd48c3ba6f6a
- 공유 send 복사17파일/840,042bytes의 상대경로·크기·SHA256 일치

실행 순서:

1. 서버 로컬 전달 확인 후 앱 Running 상태에서 새 백업 명령을 한 번 실행한다.
2. READY_FOR_NORMAL_APP_EXIT 후 기존 UI로 정상 종료하고 새 Q폴더 사본을 검산한다.
3. 콘솔 해시·사본·같은 세대 정상 종료를 검토해 새 close review와 request를 만든다.
4. 설정 SHA와 installer를 결합한 별도 설치 명령을 발행한다. 현재 묶음에는 설치
   request/명령이 없고 Sandbox 합성 request를 서버에 사용하지 않는다.
5. 실제 설치·보존 검산 후 일반 사용자로 시작하고 새 세대·설정 attestation·진단 request를 확인한다.

실패 후 설치를 다시 실행하지 않는다. installer 종료 후 검산에서 멈춘 경우 설치 없는
후속 검산을 준비한다. 현장15분 FAIL·120분 미시작·물리 NOT_TESTED·출시 HOLD를 유지한다.

### 서버 로컬 백업 명령 전달 완료

13:53 KST 서버 탐색기에서 새 묶음의 로컬 경로와 파일 존재를 확인하고 백업 명령을
메모장에 열었다. 앱은 Running, 화면 작업값은 제품60250·금형108이었다. 이는 현재 화면
관찰이며 새 운영자 확인이나 변경 지시로 취급하지 않는다.

- 서버 로컬: `C:/Users/user/Desktop/SmartFactory/HI29_20261015_9c43d21a`
- 전달: `Z:/SmartFactory/20261015/send/HI29_20261015_9c43d21a`
- 서버 로컬에서 회수: `Z:/SmartFactory/20261015/return/HI29_COPY_9c43d21a/HI29_20261015_9c43d21a`
- 전송 기록: `Z:/SmartFactory/20261015/records/HI29_9c43d21a`

`verify_server_return.py` exit0으로 서버 로컬에서 선택해 회수한17파일/840,042bytes의
상대경로·크기·기본 스트림 SHA256이 준비 원본과 같은 것을 확인했다. 서버 native hash
명령을 실행한 것은 아니다. 증거 루트의 `server-delivery-verification.json`은1,863bytes,
SHA256 `aed1be3763d89621d493af7b54fbe590facf5bcd82c8bf0f64c8505492794478`이다.
공유 records 사본도 같은 해시다. 로컬 경로·파일 목록·메모장 화면3장을 함께 보존했다.

현재 상태는 **백업 명령 서버 준비 완료·사용자 실행 대기**다. 서버 백업·앱 종료·설치는
수행하지 않았다. 서버 메모장의 `PINNED_HEALTH_BACKUP_COMMAND.txt`에서 `& {`로 시작하는
본문 전체를 독립된 관리자 Windows PowerShell에서 한 번 실행하고 앱은 Running으로
유지한다. `READY_FOR_NORMAL_APP_EXIT`를 즉시 알려 주면450초 대기 안에 Codex가 앱을
정상 종료한다. 오류 시 재실행하지 않는다. 이 직접 실행 단계는 computer-use 필수
guidance의 “Do not automate terminal applications” 규칙에 따른다.

### 서버 최신 백업: 용량 사전 검사 HOLD

사용자의 실행 완료 응답 후 실제 서버 콘솔의 증가하는 inventory 진행을 확인했다.
새 결과 `C:/Users/user/Desktop/SmartFactory/Qc940b7`은 2026-10-15 14:14:50 KST에
`live-capacity-and-path-preflight`에서 `Single-copy capacity reserve not met before
normal shutdown.`으로 중단됐다. 앞 절의 사용자 실행 대기는 해소됐지만 백업 완료가 아니다.

| 사전 검사 | 실제 값 |
|---|---|
| 원본 파일 / 폴더 / 이름 있는 추가 스트림 | 313,731 / 245 / 680 |
| 추가 스트림 포함 원본 크기 | 14,548,242,608bytes |
| 보존 여유분 포함 필요 공간 | 29,318,147,061bytes |
| C: 사용 가능 공간 | 24,326,463,488bytes |
| 부족분 | 4,991,683,573bytes (약4.99GB) |

기존 식 `ceil(source_bytes * 1.1 + (files + directories + streams) * 8192 + 10GiB)`을
독립 재계산해 필요 공간과 일치함을 확인했다. 조건은 완화하지 않았다. 이는 실행 중 원본의
이름·크기 조사이며 닫힌 사본의 내용 검증이나 전체 데이터 QA가 아니다.

READY 기록과 사본 `c` 폴더가 없고 결과는 사전 검사/중단 JSON 5파일뿐이다.
앱 정상 종료·백업 payload 복사·설치 프로그램 실행은 시작되지 않았다. hold의 일반 필드
`partial_copy_preserved=true`를 실제 데이터 복사 근거로 사용하지 않는다. native 콘솔의
최종 종료 코드·결과 해시는 관찰하지 못했으며 종료 코드0이나 콘솔 pin 일치를 주장하지 않는다.

서버 탐색기에서 결과 폴더를 선택해 `Z:/SmartFactory/20261015/return/HB29_9c43d21a/Qc940b7`으로
회수했다. 개발 PC의 `server-capacity-hold-Qc940b7` 사본과 공유 사본의 5파일 크기·기본 스트림
SHA256을 대조했다. `field-capacity-hold-review.json` SHA256은
`91bb06ff511db82be23432ea8e07ef4a2d60ddc41ef2d7490668db372107e6ce`이다.
증거 루트는 앞 절의 `PDCA_HEALTH_INSTALL_20261015_9c43d21a`와 같다.
`finalize_capacity_hold.py` exit0으로 회수 사본5파일·용량 식·상태 JSON 왕복을 검증하고
기록3개를 공유 records에 같은 해시로 보존했다. `capacity-hold-verification.json` SHA256은
`c6bc4da04f7b9569552b966280d25789b0f5add768ec0c97cfc9b0fbe9c916d3`이다.

현재 앱1.0.28/4cc는 Running이다. 사전 native 기록은 main10068/backend10724 및 각각
2026-10-14T07:43:45.0354100Z/07:43:46.1890860Z 생성 시각을 확인했다.
14:08 KST 읽기 전용 GET6건은 모두200, logger5122ad44/SPOTf1ccda6b 세대가 유지됐다.
작업 정보는14:01:07 KST 이후 필수값 미입력으로 관찰돼 현재 제품·금형을 사용자에게
요청했다. 이전60250·108이나 화면의 입력 예시12345·123을 실제 작업값으로 재사용하지 않는다.

탐색기의 내 PC에는 C:와 Z: NAS만 표시됐다. SmartFactory에서 `size:>1GB`로 검색한
3파일은 `spot_image_fact` CSV로, 삭제 가능한 중복으로 검증되지 않았다. 이 UI 검색은 전체
디스크 목록 조사나 삭제 승인 목록이 아니다. 파일 삭제·이동·권한 변경은 하지 않았다.
여유 공간30GB 이상의 외장 SSD/하드를 서버에 연결할 수 있는지 확인 중이다. 다른 저장
위치를 사용하려면 원본/추가 스트림/메타데이터와 새 경로 계약을 먼저 검증한다.

다음 체크: 공간 확보 방법 확정 → 필요한 경로·도우미 검증 → 현재 용량 재확인 → 새 실행의
READY 이후에만 정상 종료·전체 사본 검산 → 새 close review와 설치 request 발행.
현재 명령을 그대로 재실행하거나 NAS를 검증 없이 사본 경로로 대체하지 않는다.
제품 코드·installer·롤백 기준은 그대로이며 현장15분 FAIL·120분 미시작·물리 NOT_TESTED·
출시 HOLD를 유지한다.

### 2026-10-15 생산 정보 확정·외장 저장장치 준비 재개

사용자는 앞선 미입력 시점에는 생산 중이 아니었고, 현재 제품60365·금형4로 생산 중이라고
확인했다. 서버 화면은14:47:28 KST 적용됨이며14:52:57 KST 읽기 전용 GET6건 모두200,
`Product_No_operator=60365`, `Mold_No_operator=4`, `operator_metadata_valid=true`가 일치했다.
Codex가 입력값을 변경하지 않았다. 앱1.0.28/4cc와 logger5122ad44 세대는 유지됐다.

여유 공간30GB 이상의 외장 SSD/하드를 연결할 수 있다는 사용자 답변을 받았다. 실제 서버
연결을 요청했으며 드라이브 문자·볼륨 identity·파일시스템·여유 공간은 아직 확인되지 않았다.
현재 고정 copy wrapper는 Desktop/SmartFactory 결과만 생성하고 engine은 Fixed NTFS를
요구한다. 설치 consumer도 같은 Desktop 아래 Q폴더를 요구하므로 외장 목적지의 단순 경로
치환으로 실행하지 않는다. 실제 디스크를 확인한 뒤 영향받는 경로/보존 계약을 검증하고
새 묶음으로 준비한다. 기존 파일을 포맷·삭제하거나 보호 조건을 낮추지 않는다.

상태 기록 `PDCA_HEALTH_INSTALL_20261015_9c43d21a/external-storage-readiness.json`, SHA256
`4ff90fd7b23503c356188a3127da73fb8fe7153fbc54aa451c152ed6fd4edbab`.
GET 수집·응답6개 해시·작업값 대조·상태 JSON 검증은 exit0다. 제조사 thread는 여전히
발신1건이며 답변이 없다. 코드/installer 변경·백업 재실행·앱 종료·설치는 수행하지 않았다.
전체 목표는 재개했지만 현장15분 FAIL·120분 미시작·물리 NOT_TESTED·출시 HOLD를 유지한다.
