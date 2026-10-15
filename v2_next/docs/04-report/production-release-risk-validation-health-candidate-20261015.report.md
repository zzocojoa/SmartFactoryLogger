# 1.0.29 health 진단 후보 패키지 검증

작성일: 2026-10-15. 상태: **패키지·frozen backend 진단 검증 완료, 출시 HOLD**.

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

## 남은 실행 체크리스트

1. 이 **동일 installer SHA**로 격리 설치·업그레이드·재시작·복구와 Electron 실제 lifecycle을 검증한다.
2. 새 candidate에 맞춘 제한 진단을 exact payload/listener/session/native generation 및 같은 실행 ETW와
   연결하고, 원격 UI 가용성을 확인한 뒤 서버 로컬 최종 폴더까지 전달한다.
3. 실제 현장 지연 원인을 확인·보완한 뒤 영향받은 현장 QA를 수행한다. 같은15분 시험을 통과할 때까지
   반복하거나200ms 기준을 늘리지 않는다. 선행 조건 전120분 시험과 운영 승격은 진행하지 않는다.

Electron 코드 일치는 확인했지만 이번에는 Electron 앱 실행·설치·복구를 수행하지 않았다.
서버 접근·변경, 실제 장비 물리 시험도 수행하지 않았다. 설치본 QA/현장15분 FAIL/120분 미시작/
물리 경계 NOT_TESTED/전체 데이터 미결/R1–R6 및 출시 HOLD는 계속 열려 있다.
