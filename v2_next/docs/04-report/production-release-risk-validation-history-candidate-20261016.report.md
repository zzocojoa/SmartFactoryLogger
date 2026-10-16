# 1.0.30 이력 GC 보완 후보 검증

작성일: 2026-10-16. **clean 소스·미서명 패키지·격리 설치/복구 검증 완료, 현장 효과 미검증, 출시 HOLD**.

같은 현장 요청의 CPU 스택에서 관찰한 자동 GC 비용을 줄이기 위해 화면 이력을 불변 JSON
record로 보관하도록 변경했다. HTTP 이력 응답은 worker thread에서 BytesIO로 준비한다.
1시간·36,000개 한도, cursor/UTC/monotonic, 공개 JSON과 CSV·장비 설정 계약을 유지했다.
구현·중간 회귀와 최종 비교는 [설계 대조 기록](../03-analysis/production-release-risk-validation.analysis.md)에 있다.

## 동일 후보 식별

아래 상대경로 기준은 `C:/Users/user/Desktop/SmartFactory/PDCA_GC_BUILD_20261016_968f2df9`다.

| 항목 | 확인값 |
|---|---|
| 버전 | 1.0.30, 미서명 내부 운영 후보 |
| clean build commit | `0732c8e810be3c46096b397812f53a9767354229` |
| 설치본 | `source/v2_next/dist/smart-factory-logger-v2 Setup 1.0.30.exe` |
| 설치본 크기 | 164,941,077bytes |
| 설치본 SHA256 | `e72c042dd4554d5c31e27b8a2edfa6ecdcbdd08c58ed43769e7a84d782b370c1` |
| 실제 Authenticode | 설치본·Electron·backend 모두 `NotSigned` |
| backend manifest | 1,772파일, `ecd36a6c62f3e1782ce4177236500b640286da504ff6806c045b3428b7e85b39` |
| 설치본 추출 파일 | 1,899파일 / 563,853,145bytes, unpacked build와 전 파일 일치 |
| 소스 보관 | `source-0732c8e8.zip`, 1,206 tracked files, 8,545,325bytes |
| 소스 ZIP SHA256 | `8aed114fad559d2617de8c8193219f8c495253a55950c17fa05f5f2710d429d2` |
| 검산 결과 | `candidate-verification.json`, SHA256 `b26bd2a47ef3d61200ed6d7a96553e6b3cd101bc846493169e8b9185c9155914` |

서명은 승인된 정책에 따라 `NOT_REQUIRED_BY_APPROVED_UNSIGNED_POLICY`로 기록한다.
미서명 상태를 서명 검증 PASS로 바꾸지 않는다. 서버의 1.0.29나 운영·롤백 기준을 갱신한 기록이 아니다.

## 실제 실행한 검사

1. 별도 clean checkout에서 npm lock과 Python 출시 lock을 설치했다. Python wheel40개의
   버전·해시, `pip check` exit0, 빌드 전후 package 목록 일치를 확인했다.
2. 최종 `npm run health` exit0. dependency15/Electron100/frontend 계약9·Vitest437,
   backend936검사 중 private F01 fixture1건 skip. Ruff·mypy9파일·QA selftest 완료.
   skip 항목은 미검증이며, 해당 자료를 제공한 시험으로 계산하지 않는다.
3. `scripts/deploy.ps1` exit0 및 `npm run dist -- --win nsis --x64
   -c.win.signExecutable=false -c.forceCodeSigning=false --publish never` exit0.
4. 설치본을 7zip으로 추출해 파일 전체, 양쪽 frontend50파일, backend manifest/provenance,
   Electron 실행 소스의 commit 일치를 확인했다. 추출 도구의 tail 경고는 보존했고
   embedded archive offset+length+tail과 전체 installer 길이·해시를 대조했다.
5. 추출 백엔드를 별도 AppData와 loopback 합성 장비에 연결했다. 일반 health1건에는
   timing 헤더가 없었고 진단4건은 native 생성 식별자와 `REQUEST_AND_NATIVE_CLOCK_BOUND`였다.
   보관한 원문을 다시 읽은 검산도 실행 당시 결과와 같았다.
6. 실제 이력 API의 snapshot14개와 cursor 페이지 두 개를 조회했다. 페이지 내용·순서·
   generation·공개 필드와 Content-Type/Length를 확인했다. 개발 비교의 36,000개 시험과
   이 짧은 패키지 시험을 구분하며 현장 성능 통과로 사용하지 않는다.
7. 인증된 정상 종료 요청 뒤 실제 process handle exit0을 받았다. begin/final 영수증의
   같은 실행 세대·해시·단계 종료0을 재검산했다. 영수증의 `process_exit_observed=false`,
   `installation_clearance=false`를 유지하고 외부에서 관찰한 종료 결과와 구분했다.
   강제 종료·잔존 child·관련 수신 포트0, system ERROR/traceback0, crash log0bytes였다.
8. 실행 후 추출 파일1,899개가 이전과 같고 build checkout도 같은 commit의 clean 상태였다.
   `review_candidate.py`의 원문 재검산은 exit0이었다.

빌드 로그의 기존 zod annotation과 optional tzdata 경고는 원문에 남겼다.
새 의존성으로 임의 교체하거나 경고를 숨기지 않았다. 소스·구성요소 검사와 실제 앱 검사의
범위를 구분하며, 이 절은 설치 프로그램 실행·Electron lifecycle 검증을 포함하지 않는다.

## 설치·복구 시험 범위

별도 오프라인 Windows Sandbox에서 같은 SHA의 1.0.30 새 설치/제거,
현재 서버에 설치된 후보와 같은 1.0.29의 실행 → 1.0.30 업그레이드 → 재시작 →
1.0.29 재설치·복구를 검사했다. 실제 host/guest/native 종료 코드는 모두 0이었고,
별도 종료 코드 음성 대조군은 의도한 7을 기록했다. 실행은 408.391초였다.
시험 원문 루트는 `C:/Users/user/Desktop/SmartFactory/PDCA_GC_NSIS_20261016_855cb7e9`다.

이 matrix의 `original`은 **이번 교체 전 설치 후보 1.0.29**를 뜻한다.
정식 운영·다음 개선의 롤백 기준인 1.0.26 `541d701d...`을 1.0.29로 승격하는 뜻이 아니다.
과거 1.0.26 복구 검사와 당시 누적 오류 기록도 보존한다.

확인 예: `candidate-build.json`과 `candidate-payload-verification.json`의 installer SHA를
비교하고, Sandbox `input/pins.json`의 candidate SHA도 같은지 확인한다.

닫힌 원문에 `review_matrix.py`를 실행한 결과는 **140항목/실패0, exit0**이다.
네 실행 구간의 CSV 및 개별 이미지 검증 도구 8회도 모두 exit0이었다.

| 실행 구간 | CSV 전체/유효 행 | 이번 관찰/이미지 | 정상 종료 |
|---|---:|---:|---|
| 1.0.29 최초 실행 | 313/303 | 24/65 | main·backend exit0 |
| 1.0.30 업그레이드 후 | 295/281 | 25/67 | main·backend exit0 |
| 1.0.30 재시작 | 323/310 | 25/67 | main·backend exit0 |
| 1.0.29 복구 후 | 298/288 | 24/66 | main·backend exit0 |

각 실행은 약 74초의 합성 장비 수집이다. 나머지 CSV 행은 초기 `startup_pending`이며
온도 칸이 비어 있음을 확인했다. 설치·복구 전후 설정/데이터/프로필 바이트가 같았고,
수집 후 관찰·이미지는 기존 접두부에 추가됐다. 이전 폐쇄 CSV·메타데이터·이미지가
보존됐으며 최종 누적 관찰98개/이미지265개와 각 manifest·종료 영수증이 일치했다.
네 세대의 logger/SPOT 식별자가 서로 달랐고 오류·traceback·경고는 관찰되지 않았다.
후보의 실제 이력 페이지와 재시작 cursor reset, renderer 종료 준비 순서,
8개 진단 health 원문의 native 시계 결합 재검산도 통과했다.

앱·backend·fixture 프로세스와 수신 포트가 모두 끝난 후 해당 Sandbox만 정리했다.
결과 998파일/12,832,850bytes는 정리 전후 같았으며 강제 앱 종료는 없었다.

| 증거 | SHA256 |
|---|---|
| `review/review.json` | `92dee358fc86ba299c7beda65c58dd2131b46eacf1af1b9829dc38e713bc42c9` |
| `closed-output-manifest.json` | `2c5455e9edce1b27f4f9bd6c393d138da8f16a987f33d7797f1d9cf3f35e6d0c` |
| `disposal-verification.json` | `f8d31f96a0a8ea21f8ffd5240fdb048c530f78dcfa844b7c7cb60c1e2d8c3b11` |

이 결과는 격리된 설치/복구와 합성 데이터 계약 범위다. 현장 지연 개선이나 15분/120분
통과를 뜻하지 않는다. 서버는 아직 1.0.29이며, 사용자 최신 답변의 생산 제품60374·금형1이
적용된 Smart Factory Running 전면 화면을 16:09–16:10 KST에 확인했다. 재입력하지 않았다.
화면 증거는 같은 루트의 `server-60374-1-foreground.png`다.

## 남은 작업

- 1.0.30 식별자를 명시적으로 전달하는 현장 도우미와 설정 기준 연결·검증.
- 승인된 서버 교체, 변경 후 현장15분 및 선행 조건 통과 후120분 관찰.
- 물리 경계 NOT_TESTED/제조사 확인·전체 데이터 미결의 처리와 실제 운영 승격 판단.

새 전체 서버 백업, 서버 설치·재시작·프로파일 변경, 운영/롤백 기준 갱신은 이 단계에서 하지 않았다.
기존 현장15분 FAIL과 출시 HOLD를 유지하며 1.0.30의 현장 개선 효과는 아직 미검증이다.
