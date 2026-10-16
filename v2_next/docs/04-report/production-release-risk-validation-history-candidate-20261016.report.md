# 1.0.30 이력 GC 보완 후보 검증

작성일: 2026-10-16. **1.0.30 현장 설치·원본 보존·승인 설정 연결 및 15분 관찰 확인, 120분 관찰 진행 중, 출시 HOLD**.

최신 상태는 아래 `20:25 15분 관찰 완료와 20:32 120분 관찰 시작` 절을 따른다. 앞선 시각별 미완료 기록은 당시 이력이다.

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
미서명 상태를 서명 검증 PASS로 바꾸지 않는다. 아래 현장 설치에서 서버의1.0.29를 같은
1.0.30 후보로 교체했으며, 정식 운영·롤백 기준은 아직 갱신하지 않았다.

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

## 현장 관찰 도우미 연결 검증

도우미 소스 commit은 `b735967e63f591e6e11e3c08d69c7591300f83b7`이다.
제품 build와 설치본 SHA는 위와 동일하다. 새 후보 식별자와 payload 기준 SHA를 명시적으로
연결하고, 기존 1.0.28 기본값·1.0.29 계약을 보존했다. 일반 관찰900/7200초, host300초,
timing900초 예산과 native 생성 FILETIME 검증을 유지한다. 6초 WPR 전용 경로는 계속
1.0.29만 허용하며 새 후보를 암묵적으로 수용하지 않는다.

증거 루트는 `C:/Users/user/Desktop/SmartFactory/F30_20261016_8cafb9d8`다.
첫 회귀 실행은 실제 검사152개가 통과했으나 시험 실행기의 저장소 PYTHONPATH 누락으로
CSV 모듈을 불러오지 못해 exit1이었다. 원문을 보존했고 제품 변경 없이 실행 경로를
보완한 새 CSV·host 실행25개가 exit0으로 끝났다. 합계 **서로 다른 실제 검사177개 PASS**,
skip0이다. 전체 첫 실행을 exit0으로 보고하지 않는다. 변경한 Python9파일 Ruff와
`git diff --check`는 exit0이었다. 변경이 없는 제품 전체 health를 다시 실행하지 않았다.

새 binding으로 실제 추출 payload1,899파일/563,853,145bytes와 설치본을 읽고 재검산했다.
85개 tracked 도우미 소스를 고정하여 빌드했고, 소스·의존성이 전후 같았다.
frozen 실행 파일의 describe/관리자 차단/합성 닫힌 데이터/중복 JSON/부적합한 과거
attestation/잘못된 요청 SHA 여섯 실행은 모두 예상 종료 코드를 기록했다.
실행된 child3건은 잔존 job0·강제 정리0이고, 입력282파일과 패키지가 전후 같았다.
개발 시험용 controller의 관리자 조건 변경은 별도 파일에만 적용했으며 운영 controller는
그대로 보존했다. **운영 ACL 실제 적용과 서버 관찰 실행은 아직 미검증**이다.

| 증거 | SHA256 |
|---|---|
| 첫 회귀 stderr, exit1 | `fc2ff6ad966302821f22f1e8453d9f19f0ae674276ba3a743f8dc96b3267db69` |
| CSV·host 재실행 stderr, exit0 | `94e791eac514d98c6ca8e179d3654a0238b2851bbd2c7495061a0601dfc6b5f0` |
| `runner-build/RUN130/field_runner.exe`, 16,097,422bytes | `0bf334d539b95cae516b08c59e7a6287525d265ce610ad9ce7062efa22e06976` |
| `runner-build/RUN130/manifest.json` | `d17ebb1efb280d2ff9400cf21c15e76065e6721d8da6418f0d843228c159984f` |
| `runner-build/portable-r1/summary.json` | `d20e9d084cc56494c3f2c31e2420a96f353469cfcfcfc7c3d8d0b087f67cb212` |

검산 예: `test-reconciliation.json`의 모듈별 PASS 합계177과 두 원문을 비교하고,
portable summary의 `package_unchanged`, `inputs_unchanged`, 세 child의 native 종료
코드와 `job_after_cleanup`을 확인한다. 실패를 기대한 음성 대조군의 FAIL은 보존한다.
`release_gate=HOLD`, `field_observation_executed=false`도 함께 확인한다.

## 원본 보존 설치 도우미 검증

설치 도우미 commit은 `a344e4cbab0ce39e852dc45285ecb28c1c31b84c`다.
기존 계약과 함께 정확한1.0.29→1.0.30 쌍을 허용하며 새 요청은
`sfl-history-observed-install-request-v1`/`OMITTED_FOR_1030_HISTORY_ONLY`를 요구한다.
새 설치본·직전1.0.29 후보 설치본·정식541d 롤백 설치본을 각각 잠금 검산한다.
제품은 재빌드하지 않았다. 원문 루트는 `C:/Users/user/Desktop/SmartFactory/I30_20261016_5bd912c7`다.

동일 설치본의 제거 파일을 별도 오프라인 Sandbox에서 확보했다. 234,260bytes,
SHA256 `a9f2f1785d7e1c41ba5b6db75253b91da716eaf565017ed213091bff29091910`이며
앞선 전체 matrix의 해시와 같다. 처음 두 dispatch는 guest 로그인 전이라 실행되지 않았고,
종료 CLI의 빈 성공 출력을 JSON으로 읽은 host wrapper 오류도 원문에 남겼다.
실제 설치1회 exit0, guest 종료0, 환경 부재와 보존 파일을 별도 재검산했다.

`test_install_health_observed.ps1`의80검사 exit0, `test_health_preservation_entry.ps1`의
17검사 exit0이다. 후자는 최초 실행에서 상위 PowerShell7의 module path를 상속하여
Get-FileHash를 찾지 못했다. source 변경 없이 native5.1 기본 module path로 재실행한
결과를 사용하며 첫 exit1을 보존했다. 실제 installer 모사 프로세스0/17/timeout,
구·신 schema/정책·생성 식별자·제거 파일 크기/해시와 패키지 오염 거부를 검사했다.

새 설치 도우미 함수 본문을 바꾸지 않고 별도 오프라인 Sandbox에서 실제1.0.29→1.0.30
설치를 실행했다. 기존 기본 스트림 변경과 추가 스트림 변경 두 음성 대조군은 설치 시작 전에
거부됐다. 정상 조건은4시간 지난 관찰을 전수 재검산하고639ms 뒤 freshness 확인을 통과했다.
설치 native 종료0, 이전1,867개/후보1,899개 payload와 각 제거 파일·등록값, 합성 원본
4파일/3폴더/3추가 스트림/210bytes 보존을 확인했다. 원본·설정 쓰기, 전체 백업, 강제 종료,
자동 복귀는 없었다. 관리자/SYSTEM 쓰기와 운영자 읽기 ACL도 격리 guest에서 적용됐다.

닫힌 증거의 독립 재검토 `review_install_trial.py`는 **127항목 PASS, exit0**이다.
현재 소스와 archived controller 바이트, 모든 입력·결과 해시와 보존 자료61파일을 대조했다.
앱/포트 부재를 확인한 뒤 해당 Sandbox만 종료했다. 이 시험의 정상 종료 리뷰는 합성 자료로,
**실제 서버 앱의 정상 종료나 실제 서버 설치를 대신하지 않는다**.

| 증거 | SHA256 |
|---|---|
| 실제 시험 controller | `a9897e4c0f49d523c807d26bde329dba351aa389806f4e220b450500fcf8e6c1` |
| `preservation-r1/package-manifest.json` | `6bcbe2f18950d54c4d298897c980fa9df0f6e0304030fc1f88eb2d6c224260c9` |
| `install-tests-r1/tests-result.json` | `c79be406aa0ea9a7dc0d338399b7f0e7947b2bd6f2afc54634584e307f8bdaba` |
| `entry-tests-r2/result.json` | `fcde3872fd397900e51bd824b60e5fc5452340cdf99de30096458fdfca8bae63` |
| `install-trial/output/transaction/result.json` | `e11193b73a43a52b622a4889e41f9652fa4382a3d1d5c4fe24caf440586c0d2d` |
| `install-trial/closed-output-manifest.json` | `cbe6eb4487974f090d94743776e74bb194482422b9ba9f3394096b2dacd0b8c9` |

확인 예: `install-trial-review.json`의127개 조건과 원문 receipt를 대조한다.
`installer-inputs.json`에서 candidate/preceding/rollback을 구분하고, 두 `*-rejected.json`의
`installer_started=false`, `original-data-before-install-freshness.json`의120000ms 예산을 확인한다.

## 실제 서버 준비 상태

16:49 KST 화면과 후속 승인된 SSH 읽기에서 서버1.0.29 Running 및 동일 main14044/
backend11520의 생성 시각을 확인했다. 사용자가 알려 준60374·1 이후 작업자가10851·1,
이어 **60534·1을16:48:53 KST에 적용**한 기록이 있었다. 최신 운영자 입력을 보존하고
다시 쓰지 않았다. Smart Factory는 전면에 있었다. 화면은 `server-current-job-1649.png`,
API·권한·생성 식별자·C: 여유18.88GiB는 `server-preflight.json`에 보존했다.

16:53 KST 현재 CSV는357,811,133bytes로 기존 `observe-health-runtime-close.ps1`의
128MiB 읽기 한도를 넘는다. 따라서 이 도우미로 앱부터 종료하지 않았다. 다음 단계는
대용량 현재 CSV와 자정 rollover의 첫 sample sequence를 처리할 정상 종료 증거 경로를
준비·검증하는 것이다. 이 크기 확인은 파일 내용 검증을 뜻하지 않는다.

## 대용량 현재 CSV 종료 도우미 보완

17:02 KST에 현재 파일의 앞32KiB와 metadata를 읽어 첫 순번18,573 및 동일 logger를
확인했다. 서버 파일이나 설정은 변경하지 않았다. 새 도우미 commit은
`4c3e292e54a2fcde989c60f915cc56531a29420f`이며 제품 설치본은 그대로다.
v2 요청은 첫 순번을 고정하고1GiB 한도에서1MiB씩 복사한다. 검토기도 잠금 핸들을
유지하며 해시와 CSV를 순차 읽는다. v1의128MiB/첫 순번1 조건은 유지한다.

증거 루트 `C:/Users/user/Desktop/SmartFactory/C30_20261016_b5d184c2`의
`checks-r1/result.json`은 source 전후 일치와 PowerShell14/Python17 PASS·exit0을
기록한다. 실제134,217,745bytes 복사와 양쪽 독립 SHA,144,291,503bytes/2,200행
CLI 검토, writer lock, 초과 용량, 앞·중간 누락/중복, 잘못된 최종 순번·logger·UTF-8/CSV를
검사했다. `adjacent-r1`의 identity8개 회귀·Ruff·diff 검사도 exit0이다. 합계39개 PASS다.

검사된 observer는18,470bytes/SHA256
`1047549449372034f387984b059c93ea93d6521bf0764df29bcd5841ac500d0e`,
reviewer는14,025bytes/SHA256
`745589fe596c5b75196aaf923f8bbe823064dd40213c1dfaa4d9694737be5b95`다.
확인 예: `checks-r1/python-files/large-cli-review.json`의 첫/끝 순번18,573/20,772와
`prior_csv_content=NOT_EVALUATED`, worker/image/attestation 미평가를 함께 확인한다.
실제 서버 CSV 전수 검토와 정상 종료·원본 manifest 결합은 아직 수행 전이다.

## 서버 전달과 종료 검토 준비

17:23:39 KST에 서버 `C:\Users\user\Desktop\SmartFactory\H30_20261016_b5d184c2`의
22파일/494,509,232bytes를 SSH로 전수 검산했다. 개발 PC와
`Z:\SmartFactory\20261016\send\H30_20261016_b5d184c2`의 검산 후 원격 탐색기로
서버 로컬에 복사했으며, manifest SHA256은
`e428cf55125c49daf1a50cfbfcd09ecee068cf3463f0db6edaa33bb889ffdba0`다.
`C30_20261016_b5d184c2/delivery-server-verification.json`에 서버 이름·최종 경로·
각 파일 해시·SSH exit0을 기록했다. 설치 프로그램 실행은 아직 하지 않았다.

이전 현장 종료 검토기의 버전·현재 CSV·관찰 경로를 명시적 입력으로 바꾼 별도 사본을
준비했다. 처음 검토는 전달 목록의 Windows 경로 구분자와 이전 metadata를 고려하지 못해
`unique-current-metadata`로 중단됐다. 현재 CSV 이름을 고정하도록 수정한 뒤 과거 실제
1.0.28 종료 증거를 읽기 전용으로 재검토하여 기존 결과29필드가 모두 같음을 확인했다
(250,085행, 최종 순번361,155, 이미지76,114건, exit0).
`close-review-preparation-r2.json`과 원문 로그를 보존했다. 새 검토기 SHA256은
`5b9243e4331d1dd5fe3981d78bb254eb51490d19d02e4d972b1edfee928d0f98`이며,
이 재검토는 현재1.0.29의 종료 확인을 대신하지 않는다.

탐색기 작업 중 옆의 다른 기록 프로그램을 잘못 열었으나 연결·시작 버튼을 조작하지 않고
닫았다. 이후 Smart Factory Running/60534·1 화면을 전면에 복원했다.
화면 증거는 `C30_20261016_b5d184c2/server-smart-factory-foreground-1724.png`다.

## 실제 1.0.29 정상 종료와 회수 검토

증거 루트는 `C:/Users/user/Desktop/SmartFactory/P30_20261016_e934c7a2`다.
전용 SSH에서 진단 자식만 소유하는 실행기를 정상 종료·시간 제한·제어 프로세스 종료의
세 조건으로 확인했다. 각 시험 후 해당 자식/제어 프로세스 부재를 확인했으며 운영 앱은
그 시험에 포함하지 않았다. `owned-probes-verification.json`에 원문 해시와 부재 관찰을
보존했다. 이 실행기는 설치 프로그램에 적용하지 않는다.

두 도우미의 READY를 확인한 뒤17:51 KST에 Smart Factory의 닫기 버튼으로 정상 종료했다.
종료 결과는 서버 `R89d7e3a4b705`, SHA256
`752609a47798c86c1907c8827be52aa3d2cd238df35d62536a729a280290ba4d`이며 실행0이다.
`native-close-review.json`은 관련5개 프로세스의 native 종료0, 설정 SHA9901d4e3… 유지,
현재 CSV278,630행·순번18,573→297,202의 연속성을 확인했다. valid257,755,
under_range20,852, stale23행으로, 이 집계만으로 온도 의미/전체 데이터 QA를 승인하지 않는다.

추가로 필요한9파일/381,687,645bytes를
`Z:/SmartFactory/20261016/return/P30_20261016_e934c7a2`와 개발 PC로 회수·검산했다.
`preliminary-worker-close-review.json`(SHA256
`06ca2cd6a7c84c383b095c97ac113da1cc7a2592f2fc9e571b38c1a5b8228c8a`)은
Electron 정상 종료 순서·backend11520의 begin/final 결합·10개 작업 종료·이미지57,746건
저장 및 남은 queue/inflight/unfinished/failure/drop0을 확인했다. 이 단계의 상태는
`CLOSE_EVIDENCE_CHECKED_TERMINAL_BINDING_PENDING`이다. 전체 원본 관찰 manifest와의
결합은 서버 `O4ff65a11`의 캡처/재검산 완료 후 별도로 수행한다.

18:20 KST 원본 첫 순회가290,682파일/14,887,746,451bytes로 끝나고 같은 프로세스가
재검산을 시작했다.18:22 KST에도 실행 중이며 최종 결과는 아직 없다. 원본 전체 보존
확정이나 설치 완료를 의미하지 않는다. 진행 상태는 `Nf7c5de0fa3f6` 로그에 보존한다.

종료 직전 작업 정보는 현장 운영자가16:48:53에 적용한60534·1이며 마지막 CSV 행과도 같다.
이전 사용자 입력60374·1로 덮어쓰지 않았다. 원본 검산 중에는 앱을 종료 상태로 유지한다.
새 전체 백업은 만들지 않았고1.0.30 설치는 아직 시작하지 않았다.

## 1.0.30 새 실행 확인 도우미

설정 확인 도우미에 정확한0732c8e… 후보만 추가했고 기존 승인 프로파일/입력 SHA/Low Signal
OFF 조건을 유지한다. `test_spot_attestation_script.py`10개가107.784초에 PASS·exit0이다.
실제 새 metadata와 종료 증거를 얻은 뒤 네 확인 항목만 연결하며 현장 적용은 아직 하지 않았다.

종료 도우미의 v3 요청은1.0.30만 허용하고 v1/v2의1.0.29 계약을 유지한다. v3도 명시적
첫 순번·스트리밍 한도·native 종료 확인을 사용한다. `checks-r1`의 PowerShell15개와
Python18개, `adjacent-r1`의 identity8개가 PASS·exit0이다. 버전/build/schema가 섞인
요청·health·metadata를 거부했고 실제 대용량 복사/CLI 회귀를 확인했다. Ruff/diff도0이다.
설치본은 재빌드하지 않았다. 이 도우미 검증은1.0.30 현장 실행·프로파일 확인·QA 통과가 아니다.

설치 영수증 검토기도 이전 자료를 보존한 별도 사본 `P30_20261016_e934c7a2/review-history-install.py`로
준비했다(SHA256 `d19f16ad12d884270b43e92658e154fcc938e53fc2b81d4f1fc28adc58c21e91`).
정확한1.0.30/직전1.0.29/정식 복귀1.0.26 설치본과 payload·제거 파일·정책을 구분한다.
보존된 I30 실제 격리 설치 영수증을 받아들이고, 콘솔 해시·종료 코드·설정·payload·제거 파일·
직전 설치본·등록 버전·신선도 변경과 중복 JSON 키를 거부하는12개 검사를 exit0으로 마쳤다.
`reviewer-tests-r1/summary.json`이 근거이며 실제 서버 설치 결과 검토는 여전히 대기 중이다.

## 원본 검산 완료와 실제 설치 절차 시작

18:41 KST 원본 관찰·재검산이 실제 종료 코드0으로 완료됐다. 최종 범위는290,682파일,
245폴더,680개 추가 스트림,14,887,746,451bytes다. 서버 `O4ff65a11`의 결과 SHA256은
`4edb1e2f901fc40c1cc3971de4d427e87a292fcd807cb8c595a00b469c2e4bfc`,
manifest SHA256은 `2cd04e6940f847670ef55ad3405b27486ec786a657e02381644d4a899e332ab4`다.
제어 결과 SHA256 `5319920f866999e2fda84c45a4553a7d093734550db27ed9fc03046a63e97567`로
자식 종료0와 잔존0을 확인했고 강제 종료는 없었다. 총14개 결과 파일을 기존 승인된
공유 return 위치와 개발 PC로 회수·검산했다. `preservation-recovery.json`에 기록했다.

`field-close-review.json`은9개 종료 자료를 원본 manifest에 결합하여
`NORMAL_SHUTDOWN_AND_ORIGINAL_MANIFEST_BINDING_CONFIRMED`를 반환했다(exit0).
SHA256은 `c219bf5fab6680f4eb1089b6896dc2aed59ce539533a95cbf2adc2e50ea29fb1`다.
이는 앞서 확인한5개 native 종료·현재 CSV278,630행·이미지57,746건과 동일 실행의 증거다.
예: 이 검토의 `original_manifest_bindings`9개와 `verified_manifest_counts`를
`O4ff65a11/result.json`의 totals와 대조한다. 전체 과거 CSV 의미 QA 통과를 뜻하지 않는다.

새 요청 `J30_20261016_e934c7a2`4파일을 Z send에서 원격 탐색기를 통해 서버 로컬로
복사했다. 화면에서 최종 절대경로와4파일을 확인했고, 실행 시 잠금 바이트로 manifest
`d621fcb76c92ba688e4291324e207e267e21b88a5f595a3b41e88cf110e45367` 및 요청
`c19dcf3e783f5a456b436c4c3c160f91788fcd7246d35bb655b6efb763c36008`을 검증했다.
18:47 KST 직접 SSH 설치 절차를 한 번 시작했다. 결과 폴더는 서버 `J22c6ed1c`이며
18:48 관찰에서 설치 직전 원본 대조가 진행 중이다. 실제 NSIS 실행·종료와 설치 후 검산은
아직 미완료다. 연결을 유지하며 강제 종료·자동 재시도 없이 실제 결과를 확인한다.
새 전체 백업은 없고 앱은 종료 상태를 유지한다. 재시작 뒤 운영 화면 복귀와 현장 QA가 남는다.

## 19:14 당시 남은 작업

- 진행 중인 설치 후 원본 보존 확인과 최종 영수증 검토.
- 새 실행·승인 프로파일 연결과 변경 후 현장15분 및 선행 조건 통과 후120분 관찰.
- 물리 경계 NOT_TESTED/제조사 확인·전체 데이터 미결의 처리와 실제 운영 승격 판단.

새 전체 서버 백업, 서버 재시작·프로파일 변경, 운영/롤백 기준 갱신은 아직 하지 않았다.
설치 프로그램의 실제 종료0은 아래와 같이 관찰했지만 설치 후 검산은 아직 끝나지 않았다.
기존 현장15분 FAIL과 출시 HOLD를 유지하며 1.0.30의 현장 개선 효과는 아직 미검증이다.

## 19:14 설치 종료 관찰과 설치 후 검산

서버 `J22c6ed1c/installer-exit.json`은 동일한 candidate.exe가19:09:25 KST에
PID8276으로 시작해19:09:59에 실제 종료0으로 끝났음을 기록했다. 유지한 native handle,
`/S /currentuser`, 강제 종료 없음이 포함된다. 설치 전290,682파일/14,887,746,451bytes
대조가 끝난 뒤 한 번 실행한 설치다. 이후 `installed-files.json`과 `registration.json`이
생성됐으며, 같은 controller17000이 설치 후 원본 대조를 계속 수행하고 있다.

19:14:43 KST 읽기 관찰에서는50,442파일/5,505,553,329bytes까지 진행했고 `result.json`,
`hold.json`, 로컬 terminal 영수증은 아직 없었다. 현재 근거는 P30의 `install-poll-*.json`에
보존한 진행 중 관찰이다. 최종 콘솔 해시와 회수 파일을 결합한 설치 영수증 검토는 아직
수행하지 않았으므로, 이 관찰을 최종 설치·데이터 보존 PASS로 취급하지 않는다.
예: 다음 확인에서는 `launch-install/terminal.json`의 실제 종료와 stdout 해시를 확인한 뒤
`finalize_install.py`로 새 return 사본을 회수하고, 기존 검토기로22개 영수증을 대조한다.

기존 RUN130의8파일/42,208,828bytes를 해시 변경 없이
`Z:/SmartFactory/20261016/send/RUN130_20261016_e934c7a2`에 준비했다. manifest는
`d17ebb1efb280d2ff9400cf21c15e76065e6721d8da6418f0d843228c159984f`다.
`field-runner-shared-preparation.json`은 공유 사본의 전수 해시 일치와 서버 전달·실행이
아직 미완료임을 구분한다. 이전 portable 증거 SHA의 복사 오타는 공유 복사 전에 차단됐고,
기존 보고서의 정확한64자 해시와 원본 일치를 확인한 뒤 준비했다. 제품 재빌드는 없다.

설치 후 첫 실제 실행에 사용할 `read_new_runtime.py`와 `prepare_new_close.py`는
로컬에 준비하고 Python 구문/해당 PowerShell5.1 파싱을 확인했다. 아직 실행하거나 새
runtime 요청을 만들지 않았다. 실제 새 logger·CSV·첫 순번·설정 SHA를 얻은 뒤 검증된
v3 observer에 연결한다. 현재 앱은 계속 종료 상태이며 원본 검산 후 승인된 재시작,
네 프로파일 확인 항목 적용, 운영 화면 전면 복귀와 현장 QA가 남는다.

## 19:31 설치 보존 검산 완료

SSH 설치 절차가19:31:54 KST 실제 종료0으로 끝났다. 서버 `J22c6ed1c/result.json`의
콘솔 SHA256 `93a6fb2829537489d9093d12fd26a3949f6bbc8e352c1f8f16469228abad675e`와
회수 원문을 대조했다.22개 영수증을 독립 검토한 `field-install-review-J22c6ed1c.json`
(SHA256 `e69cb6957c8d7ac031eb0aec239fe3c9eeeb6d6615c75b8ebf6277fec3b0d73c`)은
exit0이다. 설치 후에도290,682파일/245폴더/680ADS/14,887,746,451bytes가 원본 목록과
일치했다. 새 설치 파일1,900개와 등록 버전1.0.30, 변경 없는 config2671bytes도 확인했다.
설치 직전 전수 대조 종료에서 실제 설치 시작까지3199ms였다. 새 전체 백업은 만들지 않았다.

## 19:42 첫 실제 실행 정상 종료와 시작 지연 발견

첫 실제 실행은 main1376/backend9052와 logger `d6442d39-3d32-48b5-98fd-1d6cd4bb217e`다.
서버 `R0be485d915b8` 결과를 콘솔 SHA256
`39ec5a3370debc6135603ccc74f29a62ae494eb911d9738de2e9a0e94a2f3084`에 결합해 회수했다.
5개 프로세스 모두 유지한 native handle의 종료0이며 강제 종료는 없었다. 현재 CSV는
2439행/순번1→2439로 연속이고 startup_pending11/stale231/valid2197이었다.

추가로 회수한9개 정지 상태 자료의 해시, begin/final, Electron session, native 종료와 CSV를
`analyze_first1030_runtime.py`로 대조했다(exit0). `first1030-runtime-analysis.json` SHA256은
`f50f64c683eb4dc69510b7122b116c592905f8492900f655bebf03ff96d638c3`다.10개 작업 종료가
확인됐고, 이미지 저장 중1건(written243/inflight1/unfinished1)이 최종 written244/
inflight0/unfinished0으로 완료됐다. 실패/drop0, worker stopped·writes drained true다.
이는 실제 저장 중 작업의 종료 근거이며 개별 이미지 바이트·fact 전수 QA를 대신하지 않는다.

Electron의 dashboard-operational-ready는8868.6ms, backend 정상 종료는956.9ms였다.
다만 CSV sample→ingest 지연은 최대65944.981ms이고 순번12→242는 ingest 시 stale로
분류됐다. 화면 준비 시간과 CSV 반영 시간을 구분한다. 지연 원인은 아직 확정하지 않았고,
한 번의 시작으로 필수 시작 횟수·화면 수 비교 전체를 PASS로 바꾸지 않는다.

## 19:48 승인 설정 연결과 19:50 새 실행

이미 승인된 설정을 같은1.0.30 build에 연결하는 네 확인 항목만 갱신했다. `A20a65c88`의
콘솔 결과 SHA256은 `73bc8db5a295d96286680a3a13288ff0884c0278bd7499fefb3f091bc0fb2c9a`이며
실행·독립 검토 모두0이다. config SHA256은
`bb1b8326c860bcd14b435bb8865ee14984228245eb626b131316d487a12ab55a`이고 다른 설정은 같다.
네 항목 복원을 위한 작은 config 사본만 보존했다. Low Signal OFF와 물리 NOT_TESTED를 유지한다.

정상 GUI 재시작 뒤 main16128/backend8980, logger `ee648ff0-d3a9-4ab9-bb7e-015ff4457cb4`,
CSV `Factory_Integrated_Log_v2_20261016_195021.csv` 첫 순번1/2/3과 설정 일치를 확인했다.
`attested-runtime-review.json`의 소프트웨어 승인 필드 대조는PASS이며 전 CSV 검증은 아니다.
첫 제한 읽기의 마지막 CSV 행이 잘린 자료는 보존했다. 새 검토기는 완성된 첫3행만 확인하고
첫 행이 불완전하면 거부하는2개 검사를 실행했으며, 전체 CSV 검증기를 완화하지 않았다.
작업 정보는16:48 운영자 입력60534·1이다.14:21 입력60374·1로 덮어쓰지 않았다.

## 20:09 현장 관찰 시작

RUN1308파일과 `O1530_20261016_e934c7a2_R2`5파일을 Z send에서 원격 탐색기로 서버 로컬
SmartFactory 아래 복사했다. 최종 절대경로·파일을 화면에서 확인하고13개 전 파일의 잠금
크기·SHA256을 SSH에서 확인했다. 요청 SHA256은
`7208ae7851ad1481afa84c5b3d4ab28d72eba348bcb722f430406e1b8d6ac870`이다.

20:08:34 KST 승인된 SSH로 한 번 실행했다. 서버 결과 폴더는 `run-51af6bced804`이며,
20:09:22 생성된 관찰은900초와 위 실행 세대에 결합돼 있다. 초기 설치본·프로세스 세대·
설정 대조는PASS지만 최종 측정 결과는 아직 없다. 앱은 최대화해 작업자가 볼 수 있게 했고
측정 중 탐색기·작업 관리자·서버 파일 복사를 수행하지 않는다. 근거는 P30의
`observe1030-launch/start.json`, `observe15-poll-111140.json`,
`attested-1030-operator-foreground.png`다.

남은 작업은 이번15분 원문 회수·독립 재계산, 결과에 따른120분 관찰, 시작 지연 원인과
필수 시작 시험, 전체 데이터 미결·물리 경계·제조사 확인 및 운영 승격 판단이다.
예: 완료 시 콘솔 `LAUNCHER_SHA256`을 회수 `launcher.json`과 대조한 뒤 session manifest의
모든 파일을 확인하고 HTTP/resource/combined 요약을 원시 표본에서 재계산한다.
기존 실패 증거와 출시 HOLD는 유지한다.

## 20:25 15분 관찰 완료와 20:32 120분 관찰 시작

15분 실행은20:25:37 KST 개발 PC의 SSH 종료0으로 끝났다. 콘솔 launcher SHA256은
`4602c1708a9f0a535c49c1b153813cd41d86da4ef2b5bb4c0a1a0c63271f2fb1`이다.
승인된 Z return에61,184,000bytes archive(SHA256
`a2874dad7dd6965dfc39f725efe9e3ab8b5d3fd0177a969a99d1898250a3e8ba`)를 회수했고,
8,795파일/53,944,838bytes를 개발 PC에서 풀어 콘솔·session manifest·전체 파일을 대조했다.

같은 frozen 도우미 소스85개를 build provenance에 결합한 독립 검토에서 HTTP/resource/
combined 요약을 원시 표본으로 재현했다. `review_observe1030.py` exit0,
`observe1030-replay-review.json` SHA256
`66b87ea6f0d65e3d52754d82465abec85cbc886f19bd95e0ae51968f7b4623ce`가 근거다.
판정은 `RECORDED_SUMMARIES_REPRODUCED`/observation PASS이며 release HOLD다.

| 실제15분 범위 | 결과 |
|---|---|
| health 경계 포함452건 | 첫7.6261ms, 최대141.8191ms, 전 요청200ms 이내 |
| 주기 health450건 | p95 65.4291ms, 50ms 경고55건, timeout/오류/누락0 |
| data150건 | 최대111.042ms, 500ms 실패0, 100ms 경고1건 |
| image3600건 | 최대164.3711ms, timeout/오류/누락0, 임의 실패 상한 추가 없음 |
| 자원 표본 | 181/181개, 미측정 구간0, warmup 후300초 창3개 각각61표본 |
| 프로세스 CPU 합계 | 장비 전체 CPU 용량 대비 평균16.9959%, 최대24.1765%; 임의 합격 기준 없음 |
| CSV 운용 표본 | 순번4973→8802, 기존 stale244건 증가0, fact 링크/쓰기 실패·config drift0 |
| 이미지 경계 | written571→1379, 양쪽 실패/drop/대기/inflight0 |

요약 `observe1030-summary.json` SHA256은
`bc9b21d1c84c07409bfa99441ba8474c74b4e0224edf152152ae4c8bbee68ff4`다.
RSS 합계에는 공유 페이지가 중복될 수 있고 disk는 호스트 전체 값이다. 자원 성능 전체·
UI 지표·시작 시 지연·전체 데이터·물리 시험을 이 관찰 PASS로 대체하지 않는다.

이 선행 조건을 확인한 뒤 같은 후보·설정·실행 세대로7200초 요청을 만들었다.
`O12030_20261016_e934c7a2`5파일을 원격 탐색기로 서버 로컬에 복사하고 RUN1308파일과
함께 잠금 해시를 다시 확인했다. 요청 SHA256은
`3f31ca781b4b66b52c6c2963e2e82ec7fe50cc3b4c3399dcd929d63d46d81c58`이다.
20:31:46 KST SSH로 한 번 실행했고 서버 `run-382f1d686bd7`에서20:32:11 관찰 설정과
초기 설치본·세대·설정 PASS를 확인했다. 실제7200초 창은 약22:32까지이며 이후 검산 시간이
추가된다. 아직 최종 결과는 없다. 앱은 최대화 전면으로 복귀했고60534·1을 유지한다.

다음 작업은120분 결과 검산과 정상 종료 후 새 CSV·이미지·fact 대조, 시작 지연의 원인 확인,
나머지 R2/R4·물리/제조사 조건이다. 설치·전체 백업·설정 변경·앱 재시작을 이번 관찰 중
추가하지 않는다. 운영·롤백 기준과 출시 HOLD는 그대로다.

## 20:43 시작 시 이미지 이력 대기 경로의 격리 재현

`P30/reproduce_startup_image_wait.py`는 후보0732c8e의 repository/spot_api/image fact/config
소스4개를 Git blob과 대조했다. Windows CRLF만 LF로 정규화한 비교이며 실행한 원본 바이트와
Git blob 해시는 각각 결과에 보존했다. 소스나 설치본은 변경하지 않았다.
새 로컬 실험 폴더에 APPDATA/설정/로그를 격리하고 네트워크·하위 프로세스·폴더 밖 쓰기를
금지한 상태에서 두 조건을 검사했다. 관찰 fact 생성은 별도 stub으로 분리했고, 이미지
manifest 초기화만 event로 지연시켰다. 합성 지연의 길이를 서버 지연의 측정값으로 사용하지 않는다.

| 격리 조건 | 실제 스택과 결과 |
|---|---|
| 다른 스레드가 이미지 writer 초기화 중 | CSV open → sidecar → image manifest → health → writer lock에서 대기 |
| CSV가 첫 이미지 writer 생성 | 같은 호출 경로에서 초기화 event 해제를 대기 |

두 경우 모두 대기 중 CSV에는 header1행만 있고 sidecar는 없었다. 초기화를 해제한 뒤 각각
12.4281ms/4.1634ms에 open이 끝났으며 sidecar와 합성 fact1행 대조가 성공했다. 별도 비대기
health 호출은 manifest 미준비 상태를 반환했다. 실행 exit0, 외부 접근 시도0이다.
초기 준비 시 CRLF 바이트 차이를 엄격 비교가 거부했고, 다음 시도는 import의 Git 조회를
하위 프로세스 금지 규칙이 거부했다. 두 시도는 재현 성공으로 계산하지 않는다. 최종 실행은
commit 조회만 검증한 값으로 고정하고 외부 접근 금지 규칙을 유지했다.

결과 `startup-image-wait-bb2f6d111f9e/result.json` SHA256은
`11617c8135d27725a0609691e9e976f19c67b4d3e10aae1fbbdca3f418c92990`,
재현기 SHA256은 `606be2eb98fa41a5ce169e2d8268f397cccaa79b21b4955ba2d3f5d9d07abd22`다.
이는 CSV의 동기 대기 경로를 확인한 제한 재현이다. 서버에서 발생한65944.981ms 지연을
이 초기화에 직접 연결하는 스택·구간 계측은 아직 없으므로 실제 원인은 UNCONFIRMED다.
예: 다음 승인된 시작 측정에서는 CSV open/sidecar와 이미지 이력 hash/count 단계의 시각을
같은 실행 세대에 결합하고, 관찰 fact 초기화 등 다른 대기와 구분해야 한다.

20:43:48 서버 읽기 확인에서 기존120분 collector6개와 같은 요청·실행 세대를 확인했다.
초기 binding/configuration PASS를 최종 성능 PASS로 바꾸지 않았으며 측정은 계속 진행 중이다.
120분 회수·독립 재계산 도우미는 준비했고 provenance85소스 preflight exit0이다. 회수는
실제 종료 뒤 콘솔 해시를 얻은 후에만 수행한다. 운영 화면은60534·1, Running 상태로 전면 유지다.

## 20:53 보존 목록으로 추가 이미지 검사 범위 확정

서버 측정을 방해하지 않도록 개발 PC에 이미 보존된 두 목록만 대조했다. 기준은10월14일
검사를 마친324,193개 이미지 목록과, 이번 설치 직전18:41:57의 `O4ff65a11/observed.tsv`다.
후자는1.0.29 정지 상태의 원본 목록이며1.0.30 실행에서 새로 생성된 자료는 포함하지 않는다.
입력 전후 SHA256과 원본 전체 합계290,682파일/245폴더/680ADS/14,887,746,451bytes를 확인했다.

| 설치 전 이미지 범위 | 파일 수 | bytes | 현재 확인 수준 |
|---|---:|---:|---|
| 전체 이미지 | 289,746 | 2,755,365,632 | 목록의 경로·크기·SHA256 대조 |
| 기존 검사와 경로·바이트 동일 | 153,014 | 1,484,108,398 | 기존 디코딩 증거 재사용 가능 |
| 새 경로 | 136,732 | 1,271,257,234 | 실물 회수·디코딩 미완료 |

같은 경로의 바이트 변경과 이미지 추가 스트림은0이다. 새 검사 대상은10월14일53,387개,
15일59,362개,16일23,983개다. 이전 목록에서 현재 보이지 않는171,179개는 별도 목록에
보존했다. 파일 날짜만으로 보존 기간 삭제라고 판단하지 않으며 부재 원인은 UNCONFIRMED다.
과거 다른 시점의 부재 수와 합산하지 않는다. 이미지 내용 대조는 CSV/fact 연결 검사를 대신하지 않는다.

`compare_preserved_image_coverage.py`의 경로 범위·중복·탈출·추가 스트림·합계·내용 재사용
검사6개와 실제 분류 실행은 exit0이다. 별도 `review_preserved_image_coverage.py`가 원본 TSV를
다른 파서로 읽어 세 분류 집합, 합계, 출력 해시를 다시 확인했고 exit0이다. 근거는
`P30/image-coverage-delta-b7c890422a3b`의 다음 파일이다.

- `summary.json`: `3f614a69cad7eeca1145021b2c323a79c72507abed5805bcea5842b6dfefb22f`
- `independent-review.json`: `e6f9ac04a2ec3b822fee790254a386827e161e35fc736781a25710b9e63fe955`
- `new-decode-required.jsonl`: `1820d9d9870763666d78c1be70382647f5a8185e1aa6e0f97bfa541a85ea96c2`
- `prior-paths-absent.jsonl`: `0cc2f4198dfbfc64f6f2165bc3b118b3b013833a21811546e2a954b7a425951b`

이 작업은 추가 검사 대상을 정한 것이며 새 이미지 회수·디코딩 건수는0이다. 서버 접근·변경·
새 전체 백업도0이다. 다음 예:120분 관찰과 정상 종료 뒤 최종 목록으로 범위를 확장하고,
이전 동일 바이트의 검사 증거를 재사용하며 미검사 이미지와 새 후보 CSV/fact를 대조한다.
전체 데이터 판정과 출시 HOLD는 유지한다.

## 20:55 실제 크기 이미지 이력의 로컬 초기화 비용

보존된10월14일 이미지 fact2,171,614,099bytes/4,237,531행을 Windows 읽기 공유 잠금으로
열고, 같은1.0.30 소스의 `SpotImageCaptureWriter` 생성자를 실행했다. 개발 PC의 새 실험
폴더에 APPDATA/설정/로그를 격리하고 네트워크·하위 프로세스·외부 쓰기를 금지했다.
행 수 계산 함수는 원래 함수를 그대로 호출하면서 시간만 측정했고 합성 지연은 사용하지 않았다.

| 단일 실행 측정 | 경과 시간 | 프로세스 CPU 시간 |
|---|---:|---:|
| 생성자 전체 | 17.5213초 | 17.3125초 |
| 기존 CSV 행 수 계산 | 15.5844초 | 15.3906초 |
| 나머지 초기화 | 1.9369초 | 별도 측정 없음 |

실행 전 검산이 파일 캐시를 데웠으므로 cold start 결과가 아니다. 나머지 시간에는 해시와
다른 초기화가 포함되며 순수 해시 시간으로 분류하지 않는다. 입력 전후 SHA256은
`7b5d26e7e1d85fc884a1398686a3f6f95fdfa4da8761aba6c00afb895cc35d01`로 같고,
파일 identity·크기·수정 시각 및 기존 최종 manifest의 행 수·해시도 일치했다.

실행 exit0, 외부 접근 시도0이다. 결과는 `P30/image-init-scale-eb1a3664fa5d/result.json`,
SHA256 `156084bd57be92fac81795d2a3b62c3b316ef5dcdbceccf0b9f74ed35bc75f3f`다.
실행 도우미 `measure_preserved_image_initialization.py` SHA256은
`fd66196183767dc304ae492300148955a8b44195f118c4a47c2c514a17bec616`이다.

실제 크기의 이력 초기화에 유의미한 CPU 시간이 드는 것은 확인했지만, 개발 PC·과거 자료·
캐시가 데워진 단일 생성자 실행이라는 범위를 지킨다. 현재 설치 전 이력2,241,600,730bytes와
자료도 다르다. 서버 시작의 CSV/관찰 fact/이미지 초기화 구간을 함께 계측하지 않았으므로
65944.981ms 지연의 현장 원인은 계속 UNCONFIRMED이며 제품 코드·설치본은 변경하지 않았다.

## 21:12 canary 완료 이후 정상 종료 준비 검사

개발 PC의 `P30/prepare_canary_final_close.py`를 준비했다. 실제120분 SSH terminal과 콘솔
결과 경로·launcher SHA·종료 코드, 회수 manifest, 명시적으로 고정한 독립 재계산 결과 SHA를
연결한다. 최종 health 바이트에서 backend/build/spot/logger/CSV/최소 순번을 다시 계산하고
관찰 shutdown expectation과 대조한다. 현재 실행의 승인 설정·첫3행 증거를 함께 사용한다.
기존 v3 종료 관찰기와 native 제어기는 변경하지 않았고 제품 설치본도 재빌드하지 않았다.

`test_canary_final_close.py`15개가 exit0이다. 실행 중 terminal 부재·콘솔 중복/해시/종료 코드,
900초 창·다른 요청·재계산 미완료·다른 logger/CSV/build·순번 감소/형식·변조된 health·승격
scope를 거부했다. 로컬 fixture 안에서만9파일 묶음과 실행기를 생성하고 파일별 해시·기준
도우미 바이트 유지·실행 전 연결 조건·기존 목적지 재사용 거부를 확인했다. 이 fixture는
실제120분 완료·서버 전달 증거가 아니다. 실제 실행 중 canary로는 준비 파일을 만들지 않았다.

| 검증 자료 | 결과 / SHA256 |
|---|---|
| `canary-close-preparation-checks-r1/summary.json` | 15개 PASS / exit0 / `5de78b6ec067966acbbb64654c48cd252241cf603563a63507ac6b0f72046e8d` |
| `canary-close-preparation-checks-r1/preflight-and-parse.json` | frozen85소스·실제 runtime preflight0, PowerShell3파일 정적 parse0 / `783da8ff1a898e85d0943bb617e8679c90b29bd1ca80ce50c2226f898662c236` |
| `prepare_canary_final_close.py` | `395717b54580a29f87d65fbaed90a82e2c49b45e2d95336252d5b82d8f91664f` |
| `test_canary_final_close.py` | `2da89f8da8546248c2d6da5a629abda376c95eca2f20404889206658ed6dc830` |

native PowerShell5.1x64에서 실제 v3 요청을 `-LibraryOnly`로 검사한 종료 코드도0이다.
측정 FAIL이 있어도 증거가 온전하면 자료 보존을 위한 정상 종료 준비는 허용하며, FAIL과
출시 HOLD는 유지한다. 예: 실제 측정 종료 → 원문 회수·독립 재계산 → 그 결과 SHA로
준비기 실행 → 새 묶음의 서버 로컬 전달·잠금 해시 확인 → 관찰기 READY 확인 → 정상 GUI 종료.
실제 서버용 묶음 생성·전달·종료·후속 CSV/fact/이미지 QA는 아직 수행하지 않았다.

21:13 기존 제조사 문의 thread를 한 번 읽어 보낸 메일1건만 확인했다. 답장은 아직 없으며
재발송하지 않았다. `manufacturer-reply-check-2113.json`에 기록했다. 진행 중120분 관찰과
물리 경계 NOT_TESTED·정식 QA/출시 HOLD는 유지한다.

## 21:29 관찰 후 데이터 검사에 필요한 용량·실행 시간

개발 PC의 보존 자료만 읽어 후속 데이터 검사 조건을 확인했다. `O4ff65a11/observed.tsv`와
결과 SHA를 전후 대조했고, `logs/test_data` 직접 하위36파일(v2 CSV12·metadata12·현재
fact/최종 manifest3·과거 schema-mismatch fact9)의 경로·크기·해시·추가 스트림 수를
`P30/dataqa-readiness.json`에 기록했다. 이36파일의 추가 스트림은0이다. 이미지 폴더·NAS·
외부 자료를 포함한 전체 R4 범위를 이 목록으로 축소하지 않는다.

현재 이미지 fact는2,241,600,730bytes, 현재 관찰 fact는545,221,046bytes다. 기존 CSV 입력
검증기의 이미지 역할4GiB/기타2GiB 한도에 들어가므로 코드나 한도를 변경하지 않았다.
4,878,532,000bytes의 과거 schema-mismatch 관찰 fact는 별도 이력이며, 이번 현재 CSV
검사에 자동 포함되거나 검증된 것으로 처리하지 않는다. 전체 과거 데이터 판정은 남아 있다.

10월14일 실제 CSV 검사 원문·최종 결합 기록·stdout/stderr/terminal 해시를 다시 확인했다.
consumer/worker exit0, 강제 종료 없음, 잔존 프로세스0, 소요2810.281초다. 후속 현재 CSV
검사는 기존 `run_command`의3600초 예산을 사용하며, 120초 기본값으로 실행해 같은
시간 초과를 반복하지 않는다. 이는 로컬 오프라인 검증기 시간 예산이며 HTTP 성능 기준은 그대로다.

`review_dataqa_readiness.py` 실행 exit0, frozen85소스와 고정 CSV EXE 해시 확인 완료다.
검토 파일11,047bytes/SHA256 `e61ba9e50f36417e9c317cd6a49a3b1afe6f5fddb3363798e4411a3a8c7622f1`,
도우미 SHA256 `d3f26547e9749ba0dc6f5b9b1a643aa118270cbafcb87fd8d0b14cbdfdeb7260`이다.
실제 후보 CSV 소비자는 아직 실행하지 않았고 새 전체 백업·서버 파일 복사도 하지 않았다.

다음 순서는 실제 canary 종료·원시 표본 재계산 → 같은 세대 정상 종료와 최종 순번 대조 →
닫힌 현재 CSV/metadata/관찰 fact/이미지 fact/최종 image manifest 및 metadata가 요구하는
선택 fact 확보 → 입력 해시·잠금을 유지한 소비자 실행이다. 최종 이미지 목록은 이전 검사와
경로·해시가 같은 자료의 증거를 재사용하고 새 자료를 검사하되, 원인 미확인 부재는 그대로 남긴다.
21:26의 제한된 SSH 상태 확인은 같은7200초 요청과6개 수집 프로세스의 실행을 확인했다.
최종 결과는 없으며 초기 binding/configuration PASS를 최종 성능 PASS로 바꾸지 않았다.

## 21:51 정상 종료 후 대장 확보 도우미 준비

기존 종료 관찰기에 포함되지 않는 누적 관찰 fact·이미지 fact·최종 image manifest를 확보하는
별도 `scripts/field-v1028/capture-closed-facts.ps1`를 추가했다. 현재 닫힌 CSV/metadata/config와
필요한 선택 fact도 같은 읽기 잠금 아래 확인·복사한다. 이미지4GiB/관찰2GiB 한도를 유지하고
새 결과 폴더에 필요한 입력만 보관한다. 전체 백업·원본 변경·앱 시작/종료 기능은 없다.

선택한 원본 전체의 쓰기/삭제 공유를 막는 핸들을 유지하고, 복사 목적지를 다시 해시한다.
CSV/metadata/config는 정상 종료 결과, 관찰 fact는 metadata, 이미지 fact는 최종 manifest와
SHA를 대조한다. 다른 실행 세대·최종 순번 감소·원본 추가 스트림·경로 탈출·기존 목적지는
거부한다. 서버 앱/포트 부재를 전후 확인하고 실패한 부분 사본은 지우지 않고 HOLD로 남긴다.
이 복사 결과는 실제 내용 검증이나 전체 R4 통과를 대신하지 않는다.

| 검사 | 실제 결과 |
|---|---|
| native Windows PowerShell5.1x64 | 10개 검사, exit0 |
| 합성 스트리밍/파일 결합 | 3,145,745bytes 복사, 원본 쓰기·덮어쓰기 차단, 선택6파일 목적지 SHA 일치 |
| 부정 입력 | 다른 세대·미완료 종료·순번 감소·선택 경로/별칭·추가 스트림·잘못된5역할 SHA 거부 |
| 실제 개발 PC 진입점 | 서버 식별에서 예상 exit1, 입력 경로 읽기/서버 작업 없이 거부 |
| 로컬 묶음 준비기 | 7개 검사, exit0; 생성 파일8개 해시·PowerShell4파일 parse0 |
| 현재 실행 중 canary | terminal 부재 시 묶음 생성 거부, 새 서버용 산출물 없음 |

검토 영수증 `P30/closed-fact-preparation-review.json`은2,855bytes이며 SHA256은
`8b899b8f3909e329cab43cf6111c11e2558d544abae5eaddfee06a7d3e40207d`다.
최종 PowerShell summary SHA는 `fd93d182622ec94012aeadc2477beb3ca4fa15caf2335060c1feb021e9d1b68a`다.
초기3개 실패는 시험 경로 변수 충돌, OrderedDictionary 그룹화, .NET의 ADS fixture 경로
처리에서 발생했다. 각 원문을 보존했고 수정 후 최종10개 검사를 실제로 다시 수행했다.

| 준비 소스 | SHA256 |
|---|---|
| `capture-closed-facts.ps1` | `0c84e46af3f48a66f71670d48d23974b71c36773e06dad0c28aa21e21b206cb5` |
| `test-capture-closed-facts.ps1` | `c6c08a2887263747eceecf5b438be860a111a188eca5d785c9b6c495caf239ff` |
| `P30/prepare_closed_fact_capture.py` | `50c03eccb2bbab163693b5e36b785c7a8700603c00b8e8f91642f301bd6a5950` |
| `P30/test_closed_fact_capture_preparation.py` | `96c51a2b20f625879ff15f648a4bbd04c8d44958b657149922999c253ee8bcaa` |

준비기는 실제 canary 재계산 결과, 정상 종료 콘솔/결과 SHA, 같은 main/backend 생성 시각,
정상 종료 제어기의 exit0·잔존 프로세스0을 확인한 뒤에만 `FCAN30_20261016_e934c7a2`를 만든다.
기존 native owned Job 바이트를 재사용하며 새 묶음의 진단 제한은1800초다. 생성 후에도 기존
정책대로 Z 전달 → 서버 로컬 최종 복사 → 잠금 해시 검산을 마친 뒤 실행해야 한다.
예: `prepare_closed_fact_capture.py --close-folder <회수한 R폴더> --result-sha256 <종료 콘솔 SHA>
--canary-review-sha256 <120분 재계산 결과 SHA>`. 실제 묶음과 사본은 아직 생성하지 않았다.
제품1.0.30 설치본은 재빌드하지 않았고 측정 중인 서버 앱/설정을 변경하지 않았다.
