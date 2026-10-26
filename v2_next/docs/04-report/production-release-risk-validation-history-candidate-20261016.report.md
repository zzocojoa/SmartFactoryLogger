# 1.0.30 이력 GC 보완 후보 검증

작성일: 2026-10-16. **1.0.30 현장 15분 관찰 PASS, 120분 관찰 FAIL 및 원문 재계산 완료, 같은 실행 정상 종료 확인, 출시 HOLD**.

최신 추가 분석은 마지막 `2026-10-17 후속: Shell 검사와 지연 요청의 시간 대조` 절을 따른다. 앞선 시각별 미완료 기록은 당시 이력이다.

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

## 22:10 CSV 소비자 연결 준비와 기존 사본 재사용 범위

`P30/run_canary_csv_qa.py`는 실제 canary 재계산·같은 세대 정상 종료·선택 사본의 콘솔 SHA와
native 제어기 종료를 확인한 뒤 기존 고정 CSV 검증기를 실행한다. `CsvInputs`의 파일 잠금과
`shutdown_csv_inputs`의 최종 순번/설정 대조를 검증기 종료까지 유지한다. 누적 관찰·이미지
대장은 잘라내지 않는다. 기존 실제2810초 결과를 근거로 기존 허용 제한3600초를 사용한다.
원본 metadata는 그대로 두고 기존 경로 전용 projection을 사용한다. 실제 실행은 아직 없다.

준비 절차8검사와 소스 preflight·Ruff F/E9는 모두 exit0다. 실행 중인 canary의 terminal이
없으면 검증기나 출력 폴더를 만들지 않는다. 잘못된 콘솔 SHA/종료 코드·입력 세대/역할/경로·
정상 종료 파일 해시·확장된 PASS 범위를 거부하는지 확인했다. 초기 Ruff가 찾은 미사용 import
2개를 제거하고 최종 소스에서8검사와 preflight/Ruff를 다시 실행했다. 제품 코드는 변경하지 않았다.

검토 영수증 `P30/canary-csv-preparation-review.json` SHA256은
`7f777d1e4820fdc2024f1cb3af88e1092a5735147e543c34f848c36573c6fb92`다.
실행기 SHA256은 `73216c0f8a3f82d1bcc2650b8e0f9c178c7511d965cc07ba1c610ac4c4be5dcf`,
검사 소스는 `88ca7bfa25c95c45246e5aa7705dbc7a784c237419de4e731ccd8881b45f9900`이다.
예: `python -B P30/run_canary_csv_qa.py --capture-folder <회수 R폴더>
--capture-sha256 <선택 사본 콘솔 SHA> --close-folder <종료 R폴더>
--close-result-sha256 <종료 콘솔 SHA> --canary-review-sha256 <실제120분 재계산 SHA>`.
현재 후보의 소비자 결과·이미지 실물 검사·전체 데이터 QA를 통과한 것으로 표시하지 않는다.

기존 `Q3d9da3` 백업의 고정 결과/전체 manifest를 다시 검산하고, 설치 전 현행 직접 입력36개와
경로·크기·본문 SHA·추가 스트림 수를 대조했다. 백업 목록325,089파일/246폴더도 결과와 맞았다.

| 현행 입력 분류 | 파일 수 | 현행 바이트 |
|---|---:|---:|
| 기존 검증 백업과 동일 | 21 | 8,087,863,671 |
| 기존 백업에 없던 입력 | 12 | 916,176,290 |
| 같은 경로에서 내용 변경 | 3 | 2,786,822,235 |

`P30/historical-input-reuse.json` SHA256은
`589a2fcadcff5863f2b51ac9a60b26809cdd5d3fb92155d25a7dd6aa51503fbb`다.
동일21파일은 필요한 파일만 기존 사본에서 재검산·회수할 대상으로 정한다. 변경3개는 누적 fact/
최종 manifest이므로 최종 일관된 경계에서 확보하고, 신규12개도 누락 없이 별도로 검사한다.
이 비교는 설치 전 직접 입력36개의 목록 비교이며, 현재1030 생성 데이터·하위 보존 자료·NAS를
포함하는 전체 R4 범위를 축소하지 않는다. 이번 작업에서 서버 파일 회수·새 전체 백업은 없었다.

## 23:23 120분 실패 재계산과 정상 종료

20:32:14–22:32:14 KST의 `run-382f1d686bd7`는 실제 SSH 종료 코드1로 끝났다.
원본 launcher SHA256은 `412e36d795648cb6685d565614e28b247bb99cd0ecd8cc722ae2b8d65a48aae0`,
전체 session manifest SHA256은 `84b55b232376f9d94f74bc8aabd2afca7ec607a6314c1db9f458ef7c6fcc0bbe`다.
회수한 70,101파일과 manifest 대상 70,097파일의 검산 후 원시 HTTP·자원 표본을 독립 재계산했다.

- health 3,600건 중2건이200ms를 초과했다(219.9407ms,302.9669ms). 오류·timeout은0건이다.
- data 1,200건의 최대156.8251ms, 오류·timeout0건이다.
- image HTTP 예정28,800회 중28,788건을 요청하고12개 예정 시점을 놓쳤다. 이는 시험 요청
  스케줄 누락이며 실제 촬영 이미지12개 유실의 증거가 아니다. 실제 이미지·fact QA는 별도다.
- 자원 표본1,441개는 coverage SUFFICIENT/recording COMPLETE이며 기록되지 않은 표본0개다.
- 도우미는 finalizing 단계의180초 제한으로 종료됐다. `worker-result.json` 및 원래
  `shutdown-expectation.json`이 없으며, 원래 worker payload closeout/구성요소 종료 코드도 없다.
  마지막 health·설정·제어 세대 파일은 남아 있지만 이를 worker 성공으로 대체하지 않는다.

`P30/interrupted-canary-review-r1/summary.json` SHA256
`2e2fc5103345e1ffbda7a0c3b3ee8e59ccdf26cfee3f2e088c28a8a319c91a3a`는
원본 FAIL을 유지한다. `combined-recalculated.json`의 SHA256은
`4dd9ccd47b262a751a957467c76900f5a3814ad0eb8f40da43e08ac1aa709f71`이며 재계산도 FAIL이다.
분석 실행은 exit0이고, 기존 reviewer의 INCOMPLETE는 누락된 원래 worker-result 때문이다.
로컬 전체 manifest 검산309.1875초·combined101.1152초는 개발 PC 단계 소요 시간이다.
원시 표본 읽기와 일부 겹쳤으므로 서버의 정확한 finalization 지연 원인으로 단정하지 않는다.

`P30/canary-outlier-evidence.json` SHA256
`7f114fa5c5501443793ac1c8430f72a58ea3638a3e13942c293e1bcedd0d4467`에 느린 요청2건과
누락 시점12개를 연결했다. 느린 요청은 응답 헤더 대기 구간이 대부분이며, 같은 요청의
서버 내부 단계·ETW가 없어 원인은 미확정이다. 기존 GC 원인으로 단정하거나 기준/시간 제한을
늘려 통과시키지 않는다. 시험을 자동으로 다시120분 실행하지 않았다.

최종 health에서 확인한 같은 logger/spot 실행 세대·설정·CSV와 최소 순번40838만 새로운
실패 후 인계에 사용했다. `interrupted_canary_handoff.py`13개 거부/연결 검사 exit0이고,
새 선택 사본·CSV 소비자 연결15개 검사와 Ruff F/E9는 exit0이다. 이전 해시 결합 도우미는
그대로 보존하고 `_v2` 도우미를 새로 준비했다. 누락·FAIL·출시 HOLD가 계속 인계된다.

`RCAN30_20261016_e934c7a2_R2`9파일을 원격 탐색기로 서버 로컬에 전달한 뒤 SSH로
manifest·전체 파일 해시와 PS5.1 구문을 확인했다. 관찰 준비 신호 후 GUI로 앱을 정상 종료했다.
실제 종료 도우미 exit0, native Job 잔여 프로세스0이며 강제 종료는 없다.
결과 `R406500891d2f/result.json` SHA256은
`fe9eb05ba148de81c1c211e4dea4d6a5ce83f17d128a5a28f981a5a019646af8`이고,
제어기 `Nc2e481dac75d/supervisor.json` SHA256은
`a531a43cd6dbb1177e96c8c1a20a8fa9bc6526317c2536831520e853649e2398`이다.
회수 후 정상 종료 reviewer가 프로세스5개 종료 코드0·원래 config 해시·CSV 순번1–53338을 확인했다.
이는 `LIMITED_RUNTIME_CLOSE_RECEIPTS_VERIFIED` 범위이며 전체 CSV 의미·이미지 실물·내부 worker
종료 기록 QA를 대신하지 않는다. 현재 stale244행은 기존 시작 구간 기록으로 남아 있다.

다음 단계는 같은 종료 경계에서 선택 CSV·누적 대장 전체·설정 사본 확보와 실제 CSV 소비자 실행이다.
`FCAN30_20261016_e934c7a2_R2` 준비 영수증 SHA256은
`6140f27c4a91ec3c4697a8a5a54638bd9a03262d88a26d34ae3bc388112e8b54`다.
이 시점에는 공유 전달까지만 완료됐고 서버 실행은 아직 없다. 전체 백업·재설치·설정 변경은 없다.

## 23:43 종료 사본 확보와 운영 화면 복귀

`FCAN30_20261016_e934c7a2_R2`의 서버 로컬8파일을 원격 탐색기에서 확인하고 전체 해시와
PS5.1 구문을 검산한 뒤 승인된 SSH 경로로 실행했다. 실제 launcher exit0, 자식 exit0,
native Job 잔여0을 확인했다. 원본은 읽기 잠금으로 복사 끝까지 유지했으며 추가 스트림0,
원본 변경 없음, 새 전체 백업 없음이다. 선택 사본은 현재 CSV/metadata, config, 누적 관측
대장 전체, 누적 이미지 대장 전체와 이미지 최종 manifest다. 전체 R4나 이미지 실물 사본은 아니다.

- 서버 결과 `Rf3f5b080a2a1/result.json` SHA256:
  `5bcf946c11cea5a69428bf9e67db44938972630ab3f6e4c3aefb0fdad6ce53ed`
- 제어기 `Ncf963e4c7e70/supervisor.json` SHA256:
  `14a30a231fd06eb23bd5177c4142668e4e768cf06fd852c26d8d8782feb97678`
- CSV 72,136,921bytes, 관측 대장560,718,654bytes, 이미지 대장2,247,226,565bytes다.
  CSV/metadata/config는 직전 정상 종료 결과와 일치하고, 사본 전체 크기는 약2.88GB다.
- `capture-before-restart-review.json`에서 콘솔에 결합된 서버 결과와 선택 사본 계약,
  앱 프로세스 없음까지 확인한 뒤 재시작했다. 이 시점 개발 PC 전송·전체 사본 해시 검산은
  진행 중이므로 회수 완료나 내용 QA 통과로 표시하지 않는다.

별도 회수한 내부 shutdown begin/final과5개 native 프로세스 종료 증거를 대조했다.
같은 backend8980/build0732c8e의 종료10단계가 완료됐고 이미지 enqueued/written10,800,
실패/drop/대기/inflight/unfinished0, worker 정지·writes_drained=true다. 이번 종료 시작 때
이미 대기열이 비어 있었으므로 비어 있지 않은 대기열의 drain 시험으로 계산하지 않는다.
이미지 실물 해시·디코딩 검사 역시 이 카운터 대조와 별개다.

설치된 바로가기로 앱을 정상 시작하고 최대화했다. 화면은 Running, 작업 정보60192/18
적용 상태였으며 임의 입력/재적용은 없었다. 새 main17996/backend14012, logger
`9a4d5320-7ef9-4290-a344-a0c03b187362`, CSV `Factory_Integrated_Log_v2_20261016_233657.csv`다.
같은 config SHA `bb1b8326c860bcd14b435bb8865ee14984228245eb626b131316d487a12ab55a`와
첫3개 CSV 논리 레코드의 순번1/2/3·실행 세대를 확인했다. 후속 health는545행까지 기록했다.

시작 관측에는 지연이 남았다. Electron dashboard-ready는9,967.5ms였지만 logger 시작
23:36:57부터 CSV open 로그23:38:17까지 약80초였다. 관측 대장 초기화47,422ms 중
해시6,234ms·색인41,141ms가 보고됐고 초기 CSV 상태는 startup_pending12/stale249였다.
파일 전송과 동시에 시작했으므로 독립 시작 성능 시험이나 특정 지연 원인으로 단정하지 않는다.
화면 Running을 CSV 저장 준비 완료의 근거로 사용하지 않는다.

기존 짧은 읽기 도우미는 처음 두 번 CSV 이름 미준비를 거부했고, 세 번째는65,536bytes
접두부 끝의 잘린 다중행 인용 필드를 모두 파싱하다 실패했다. 원본 stdout을 보존하고 새
오프라인 reviewer가 필요한 첫3개 완전한 논리 레코드만 파싱했다. 잘린 후속 레코드 재현과
필수3번째 레코드 손상/부족 거부 검사를 수행했고 reviewer·Ruff F/E9 모두 exit0이다.
이것은 검사 도우미의 접두부 처리 문제이며 실제 CSV 파일 손상으로 판정하지 않는다.

`P30/canary-close-restart-review-r1.json` SHA256은
`414e40062c2fb3f8aa36324c85448ef23d58517ed69c95c6a37755138bd5013a`다.
해당 범위는 종료 기록과 새 실행의 접두부 확인이다. 다음은 실제 선택 사본 전체 검산 후
고정 CSV 소비자 실행이며,120분 FAIL·전체R4 미완료·물리 NOT_TESTED·출시 HOLD는 유지한다.

## 23:48 사본 회수 완료와 내용 검사 실행

선택 사본과 제어기13파일/2,880,127,963bytes를 회수하고 콘솔 result/supervisor SHA 및
result에 포함된 모든 파일 해시를 대조했다. 회수 SSH tar와 로컬 검산 실행은 exit0이다.
전송 archive2,880,143,360bytes의 SHA256은
`474e91845d4cf317100edf134082039b14d6754acca9a41ec8fc0f4f4fbd86e3`이며,
영수증은 `P30/postcanary-v2-capture-recovery.json`이다. 이전 절의 회수 대기는 해소됐다.

`run_canary_csv_qa_v2.py`가 실패한 canary의 원래 판정·정상 종료·선택 사본 출처를 연결한 뒤
고정 소비자 `validate_csv_v2_shadow.exe`를 실행했다. 소비자 SHA256은
`e728730ad841dd4a754a6c0880e0e1216de5e3d0cd5646c22de9245fc85b0b2f`이며,
출력 폴더는 `P30/canary-csv-qa-v2-r1`이다. 입력 잠금·원래 metadata 보존·경로 projection·
기존3600초 제한을 유지한다. 첫 CLI 호출은 수동 전달한 종료 해시의 문자 누락을 거부해
소비자 실행 전에 exit1이었다. 검산된 회수 영수증에서 해시를 직접 읽은 다음 호출은 실행 중이다.

23:47:16 KST 실제 프로세스 관측에서 worker51192와 소비자15816/7440의 경로·부모·생성 시각을
확인했다. 소비자 terminal은 아직 없으며 실제 완료/정리/전체 stdout·stderr 검토가 남는다.
실행 중이라는 사실을 내용 검사 PASS로 표시하지 않는다. 서버 앱은 Running/60192·18로
전면에 표시했고, 이후 검사는 개발 PC 사본에서 수행한다.120분 FAIL·출시 HOLD는 유지한다.

## 2026-10-17 00:11 누적 이미지 기록과 보존 파일 대조

정상 종료 사본의 이미지 fact 4,385,307행을 전부 읽고 capture ID와 대소문자를 정규화한
경로를 SQLite의 서로 다른 unique 제약으로 검사했다. 이미지 식별·크기·해시·형식·경로 날짜
검사와 최종 manifest 행 수 대조를 완료했다. 설치 전 보존 이미지289,746개가 같은 경로의
fact 크기/해시와 모두 일치하며 미연결0, 중복 ID/경로0이다. 같은 canary SPOT 세대
`2e756cd2-0842-45d7-bfde-b7daf776cc4c`의10,800개/99,802,626bytes를 추출했고
최종 written10,800과 일치했다. 이 결과는 실제 이미지 바이트의 디코딩 결과와 구분한다.

초기 검사기는 현재 날짜 폴더만 허용해 과거 하위 폴더4곳의4,222행을 거부했다(exit1).
기존 이미지 검사기의 안전한 하위 경로 계약을 확인한 뒤 별도 R2에서 과거 폴더를 보존하도록
보완했다. R1 소스·결과는 유지했다. R2의5개 회귀 검사·Ruff F/E9·실제 전체 실행은 exit0이며,
독립 SQL 조회로 원본 출력 해시·438만 행 수·unique 수·보존 파일 조인·과거4,222행의 원래
행 번호/경로/해시를 재검토했다(exit0). 독립 검토의 첫 시도에서 폴더 하나만 가정한 오류도
영수증에 남겼으며 실제 데이터 손상으로 판정하지 않는다.

- `P30/closed-image-ledger-r2-59e6f8760ebe/summary.json`:
  `fba573fd62adec4f6a80c21fabccb09112c8224453394c46a68c7aaa80f2e496`
- 같은 폴더 `independent-review.json`:
  `0843efee045917163527283f0cecd5c3487fc3e69cfb54c96632f27d6e362aba`
- 기존 디코딩 증거가 없는 보존 이미지136,732개와 이번 세대10,800개를 합친
  147,532개/1,371,059,860bytes의 선택 목록:
  `P30/image-byte-review-3dfaea24e245/selection.jsonl`,
  SHA `0c3fccf4be6975f5c0fb6714772bf1fcded6fb739d370372c4c8329ec9297546`.

명시한 파일 목록을 승인된 SSH에서 읽어 `Z:/SmartFactory/20261017/return/`
`image-byte-review-3dfaea24e245/selected-images.tar`로 회수하고 있다. 서버 쓰기·전체 백업·
설정 변경은 없다. 새 회수기의2개 검사에서 archive 외부/중복/링크/크기 불일치와 바이트 불일치·
잘린 JPEG의 거부를 확인했고 Ruff F/E9도 exit0다. 실제 회수·개별 바이트 해시·전체 디코딩의
완료 판정은 아직 대기 중이다. CSV 소비자 exec46981도 같은 기존 프로세스로 계속 실행 중이다.

00:08 서버 화면에서 앱이 전면 Running/60192·18임을 확인했다. 설치 전 목록과 종료 fact의
연결은 종료 후 전체 파일 목록·역방향 orphan·과거 부재 원인·다른 R4 경로의 완료를 대신하지
않는다. 현장120분 FAIL, 물리 NOT_TESTED, 전체R4 미완료와 출시 HOLD를 유지한다.

## 2026-10-17 00:18 이미지 전송 실패와 완전 수신 항목 검토

이미지 회수 exec19815는 SSH의 `server 192.168.0.7 not responding`으로 종료됐다.
실제 SSH exit255, 실행기 exit1이며 오류를 성공으로 바꾸지 않는다. 전송302.328초 후 남은
archive1,480,151,040bytes의 SHA는
`e6dd9c51ef5974cc27a975c8c3e0226da48a0ae9939cb4ad5860b5753e11e237`이다.
`P30/image-byte-review-3dfaea24e245/ssh-terminal.json`, stderr와 failure.json을 보존한다.
파일 전체를 다시 전송하지 않았다.

별도 로컬 검토 exec79708은 읽기 잠금으로 이 archive를 검산·복사한 뒤 완전한 member만
원래 선택 목록의 경로/크기/SHA와 대조하고 동일 고정 decoder로 전체 디코딩한다.
출력은 `P30/partial-image-review-a038d4addc9e`다. 잘린2파일 fixture에서 첫 완전한
이미지1개만 인정하고 두 번째 불완전 이미지를 제외하는 검사와 Ruff F/E9는 exit0이다.
실제 완료 수와 미수신 목록은 검토 완료 후 확정한다. 전송 실패의 원인 자체는 미확정이다.

CSV exec46981은 원래 소비자7440이 계속 실행 중이며 기존3600초 제한을 유지한다.
전체R4·성능 원인·물리 시험·운영 승격은 미완료다. 다음은 같은 검토 handle의 완료 확인,
완전 수신 항목과 미수신 항목의 수량 정산, 미수신 항목에 한정한 추가 회수다.

## 2026-10-17 00:34 선택 이미지 검사와 기존 증거 연결 완료

부분 archive 검토 exec79708은 exit0으로 끝났다. 완전 수신146,969개/1,365,821,084bytes는
각 원래 선택 항목의 크기·SHA256·전체 JPEG 디코딩과 일치했고, 불완전 member를 포함한
미수신563개/5,238,776bytes를 별도로 확정했다. 원래 SSH255 실패는 그대로 보존한다.

표준입력 파일 목록을 사용한 첫 추가 회수도 진전이 없어, 정확한 명령·경로·생성 시각으로
확인한 작업 소유 tar16336/15304만 정리했다. 앱 backend14012는 같은 세대로 유지됐다.
이는 표준입력 전달 방식의 문제라는 추정이며 전송 중단의 원인을 확정한 것은 아니다.
첫 추가 회수의 실패 영수증은 `P30/image-remainder-760aa4a2ef27`에 보존한다.

새 회수는 파일명을 인자로 전달하는64개 이하9묶음으로 수행했다. 각 SSH exit0·stderr0을
확인하고563개를 원래 선택 항목과 대조해 전체 디코딩했다. exec20342 exit0이며, 최초의
완전 수신 항목과 합쳐147,532개/1,371,059,860bytes를 빠짐없이 정산했다. 요약은
`P30/image-remainder-r2-4f44beaa8e47/summary.json`, SHA256은
`019473912ba2d8a3c1199f854151f8d174b13f773035f9fe011df7b8f746bb5d`다.

별도 정산기는 잠근 원본 설치 전 inventory, 과거 동일 바이트 디코딩 증거, 전체 fact 조인,
새 디코딩 결과를 연결했다. 과거 증거153,014개 + 이번 보존 파일 디코딩136,732개 + 닫힌
canary 세대10,800개 = **300,546개/2,855,168,258bytes**다. 중복·누락 없이 두 선택 집합과
정확히 일치하며 전체 입력의 전후 해시도 같다. 원본 이미지 전체를 중복 회수하지 않았다.
9개 전송 영수증·archive·빈 stderr와 로컬/공유 추가 archive의 해시를 다시 확인했다.
정산기 Ruff F/E9와 실제 정산은 exit0이다.

- 정산 결과: `P30/combined-image-coverage-e8b8d365aabe/summary.json`
- 결과 SHA256: `60039608815ea70fac81ed69f4328b81670b13428994687cde71570565dc0f25`
- 항목별 coverage SHA256: `e9cd610c5a642702e3aac288caad43fb106ecad37b6abc160a0aae1a598f124a`

이 집합은 설치 전 목록과 닫힌 canary 세대의 합집합이며 종료 후 전체 filesystem snapshot은
아니다. 역방향 orphan 검사·과거 부재171,179경로의 원인·다른 보존 경로와 과거 CSV 스키마는
계속 R4 범위에 남는다. 00:34:40 KST 원래 CSV 소비자7440/15816·worker51192가 같은 경로와
생성 시각으로 살아 있음을 확인했다. exec46981의 기존3600초 제한과 원본 입력을 유지하며
terminal 결과를 기다린다.120분 FAIL·물리 NOT_TESTED·정식 출시 HOLD는 유지한다.

## 2026-10-17 00:43 닫힌 CSV 검사 완료와 과거 형식 확인

기존 CSV exec46981은00:37:10 KST에 exit0으로 종료했다. 실제3046.5초이며 제한3600초 안에
완료했다. 소비자/worker exit0·강제 종료 없음·Job 잔여0을 terminal과 process receipt에서
확인했다. 전체 stdout5,920bytes는 PASS, stderr는0bytes다. 종료 후 reviewer가 원본 입력5개,
실행 파일 고정 해시, 종료/실패 canary 출처와 모든 출력 해시를 대조했고 Ruff F/E9·실제 검토는
exit0이다. 입력을 축소하거나 timeout을 늘리지 않았다.

| 검사 | 실제 결과 |
|---|---|
| 닫힌 CSV 전체 | 53,338행, sample_seq 1–53,338, 같은 logger 세대 |
| 누적 관찰 fact | 482,570행/서로 다른 관찰 키482,570개, manifest 크기/해시/행 수 일치 |
| CSV의 관찰 기록 연결 | 키가 있는53,322행 전부 연결, 누락 키 참조0·진단 출처 불일치0 |
| 관찰 키가 없는 CSV 행 | 시작 대기16행; 전체 CSV를 별도 파싱해 상태와 수량 대조 |
| CSV 상태 | startup_pending16, stale244, valid50,620, under_range2,458 |
| 누적 이미지 fact | 4,385,307행, 최종 manifest 해시·행 수 일치 |
| 쓰기 실패/미반영 spool | 관찰 fact 기준 각각0 |

v1 비교는 실제 metadata에서 비활성인 항목이다. changeover/phase fact는 행0·해시 없음인
manifest와 파일 부재를 확인한 상태이며 해당 파일의 내용 검사를 했다고 표시하지 않는다.
이미지 linkage posthoc 항목은 not_applicable, promotion profile required는False다.
따라서 이 CSV 검사 PASS를 장비의 물리 적합성이나 운영 승격 PASS로 확대하지 않는다.

- 소비자 원문 검토: `P30/canary-csv-qa-v2-r1/review.json`,
  SHA `232a02ed274c433babc32ebd43aa1a7b5f32c4ec11bd40df266e40090e086c83`
- 최종 대조 영수증: 같은 폴더 `completed-review.json`,
  SHA `166bf76d669a5dc2210fb2dde79e15891f1859b2828c072d0af35fa9164010b6`

전체 R4의 과거 형식도 이어서 확인했다. 기존 검증 백업 `Q3d9da3/c/r0/logs/test_data`의
schema-mismatch9파일을 새 전체 백업 없이 읽어 헤더를 확인했다. 이미지31열1개,
관찰1.2.0/47열1개·1.3.0/54열4개·1.4.0/55열3개다. 각 헤더를 저장소의 현재 또는 과거
소스 상수와 정확히 대조했다. 원문/명령/SSH exit0과 계약 대응표는
`P30/historical-schema-headers-154129053041`에 보존했으며 `contract-map.json` SHA는
`25f220bfd4872dcfe38fe21e53f015290c87463f7500dd0430f75f315966902e`다.
현재 확인은 헤더/첫 물리 줄과 길이 범위다. 전체 내용 해시·논리 행·버전별 의미 검사는 다음 단계이며,
인용 필드 내 개행으로 짧은 첫 물리 줄을 CSV 손상으로 판단하지 않는다.

00:41 SSH에서 backend14012의 같은 생성 시각을 확인했고00:43 원격 화면은 Smart Factory가
최대화·전면 Running이었다. 작업 정보는00:26:24 이후 필수값 미입력으로 바뀌어 사용자에게
현재 제품/금형을 질문했다. 이전60192·18을 재입력하지 않았고 승인 설정을 변경하지 않았다.
해당 확인 대기는 이미 닫힌 자료의 검증이나 과거 자료 분석을 막지 않는다.

다음은 과거9파일의 전체 내용 검사, 전체 파일 목록/역참조 및 과거 부재 분류다.
120분 성능 실패 원인·시작 지연·물리 경계·모든 R4 경로와 최종 운영 승격은 미완료이며,
정식 출시 HOLD와 이전 롤백 기준을 유지한다.

## 2026-10-17 01:10 과거 9파일 전체 행 검사와 발견 항목 분류

기존 검증 백업에서 schema-mismatch9파일/6,461,851,976bytes를 승인된 SFTP로 회수했다.
9개 전송 모두 exit0·stderr0·시간 제한 초과0이며 각 파일의 크기/SHA256은 기존 신뢰 목록과
일치한다. 새 전체 백업이나 서버 설정 변경은 수행하지 않았다. 회수 요약은
`P30/historical-schema-recovery-4856a6ee1042/summary.json`, SHA256은
`6949ffea1ba0f2cdb1f3ec1576a51a71161cc5f03fc10631a764808a487be312`다.

버전별 원래 행 검사기를4096행 단위로 적용하고 전역 키를 SQLite에 기록했다. 작은 동일 입력의
원본/분할 검사6개 비교와 Ruff F/E9는 exit0이다. 실제 전체 실행 exec56203은270.436초 후
발견 항목을 남기고 exit1로 종료했다. 입력을 읽기 잠금으로 유지하고 전후 해시를 대조했다.
관찰6,170,644행과 과거 이미지 fact54,112행, 합계6,224,756행을 검사했다. 파일 내/파일 사이
관찰 키 중복은0이며 파일별 서비스 순번 범위 내부 gap도0이다. 이는 서비스 경계 밖의 누락이나
이미지 실물·CSV 역참조가 모두 해결됐다는 뜻이 아니다.

초기 결과703,393건 중703,389건은 검사기가 첫 행1.2.0을 파일 전체 버전으로 가정한 데서
발생했다. 실제 같은47열 파일에는1.2.0 307,470행과1.2.1 703,389행이 연속으로 들어 있다.
1.2.1 도입 commit `5f005211db7b88070883b0ab73bf7f67eac5b1e8`의 원래 소스에서 동일 헤더와
헤더만 비교한 append 동작을 확인했다. 두 버전의 행 검사 함수를 포함한 의존 함수6개의 AST와
import가 같음을 대조했고, 원본 전체 파일에서 각 버전의 행 구간을 다시 확인했다. 원래 exit1
결과는 보존하고 이703,389건을 검사기 가정에 따른 오판정으로 분류했다. 분류기의 정상 비교1개와
변경된 함수/상수/import 거부3개 검사·Ruff F/E9·실제 검토 exec18805는 exit0이다.

남은4개 진단은 다음2개 과거 행에서 각각 원래 검사와 추가 버전 검사가 같은 문제를 보고한 것이다.

| 파일 | 논리 record 번호(헤더1) | 관찰 시각 UTC | 실제 이상 |
|---|---:|---|---|
| `spot_observation_fact.20260923T002626499491Z.schema-mismatch.csv` | 3,094,807 | 2026-09-07 21:39:02.057891 | 버전 필드의 `1.3.0` 앞 NUL801개 |
| `spot_observation_fact.20260928T005126664254Z.schema-mismatch.csv` | 159,923 | 2026-09-24 23:03:01.288327 | 버전 필드의 `1.3.0` 앞 NUL1,611개 |

두 파일은 기존 백업과 같은 해시이며 후보 설치 전 보존 목록과도 연결돼 있다. 이 이상을 이번
후보가 새로 만들었다고 판단하지 않는다. 두 행 모두 서비스 poll_seq1이지만 재시작·전원 장애·
파일 시스템 문제 중 어느 것이 원인인지는 아직 증명되지 않았다. 원본을 수정하거나 NUL을
제거하지 않았으며 원인·영향·복구/처리 결정은 후속 R4 항목으로 남긴다.

- 전체 검사: `P30/historical-fact-scan-552d255075fd/summary.json`,
  SHA `477cfa942955274beb9e11fe0d2130581b8f134f26cef07df1909c658fe4ded6`
- 분류: `P30/historical-findings-review-8758eef51dde/summary.json`,
  SHA `20776aa53585bd687f2855494cb4a9a80d957434ee62b0db7669bc6d72c57b09`
- 원본2행 증거: 같은 폴더 `affected-records.json`,
  SHA `d84233a5045232dec61f6fcf9965e06ec045f7ce2d318fb0d8f1a4eb314bf7e5`
- 독립 SQL 수량/출력/전송 로그 대조: `P30/historical-schema-closeout-08a8ee8ce6a4/review.json`,
  SHA `1882eb16debf584cd3e8153cb39246a8b7c4533f0d699beb593ce91884c97052` (exit0).

요약·분류·영수증18파일은 `Z:/SmartFactory/20261017/return/historical-schema-closeout-08a8ee8ce6a4`
에 복사하고 해시를 대조했다.6.46GB 원본 사본은 개발 PC 회수 폴더에 있으며 Z에 중복 복사하지
않았다. 상세 경로와 로컬에만 있는 큰 분석 출력은 `shared-copy-receipt.json`에 구분해 기록했다.
01:07 서버 화면은 Smart Factory 전면 Running, 작업 정보60295·1/적용00:47:27이었다.
Codex가 작업 번호를 다시 입력하지 않았다. 전체R4·과거 이상 원인·120분 실패 원인·물리 시험·
운영 승격은 미완료이며 목표 active, 정식 출시 HOLD와 기존 롤백 기준을 유지한다.

## 2026-10-17 01:34 과거 NUL 기록과 비정상 재시작 이벤트 대조

과거 NUL 두 건 모두 비정상 호스트 재시작 후 새 서비스의 첫 관찰 기록에 연결된다.
**재시작 연관성은 확인했지만 NUL 생성 원리·정확한 중단 시점·덮어써졌거나 사라진 기록의
내용은 미확정**이다. 전원 상실·디스크 고장·앱 결함 중 하나를 원인으로 단정하지 않는다.

기존 `Q3d9da3/c/r0/logs`의 선택 로그11개를 SFTP로 회수해 백업 manifest의 크기/SHA와
전부 대조했다. 회수는10.563초/exit0이다. ±180초 로그59줄과 문제 행 전후7개씩을 추출했고,
추출 실행도 exit0이다.59줄은 모두 시각으로 연결됐으며 관찰 키 문자열 직접 일치는0이다.
시각 없는 로그를 사건에 임의 배정하지 않았다. 회수 요약 SHA는
`79522ea54992dc70c59c9d2c8756923d6d4522dfc76b286d152a4dc54cf056f7`, 추출 요약 SHA는
`63b12addc1d7c976a9ea65460b5f06ec2ec44a3ac08ce5c6f57b28504c7f09c2`다.

승인 SSH에서 대상 서버/SID/관리자 권한을 확인한 뒤 System 전체 이벤트를9월8일05:30–07:10,
9월25일07:30–08:15 KST 범위로 읽었다. 각각145/158건이며 같은 범위 Application의
1000/1001/1002 이벤트는2건씩이다. 네 조회 모두 오류/상한 도달0, SSH exit0/stderr0이다.
총307개 원문 XML의 서버·provider·ID·record 번호·UTC와 조회 시간 범위를 검산했다.
이후 개발 PC 콘솔의 cp949 표시만 실패해 저장된 UTF-8/XML을 읽었으며 서버 조회는 반복하지 않았다.

| 확인 사실 | 9월8일 KST | 9월25일 KST |
|---|---|---|
| Kernel-Power41 | 06:36:57.569, record21003 | 08:00:38.621, record21791 |
| EventLog6008 | record20990 | record21765 |
| 앱 시작 | PID13280, session `d63a333b11ba` | PID6964, session `aaba6fdf6918` |
| NUL이 붙은 첫 관찰 | 06:39:02.057891, poll_seq1 | 08:03:01.288327, poll_seq1 |
| 이전 서비스의 마지막 보존 관찰 | 06:03:42.845004 | 07:55:45.263175 |
| 다음 poll_seq2까지 | 434.610436초 | 7.152346초 |
| NUL 바이트 범위(0부터, 끝 제외) | 3,572,204,696–3,572,205,497:801개 | 186,681,178–186,682,789:1,611개 |

두 원본을 읽기 잠금으로 전부 검사하고 전후 해시를 대조했다. 각 파일에는 해당 NUL 구간
하나가 있고 바로 앞은 CRLF, 뒤는 새 서비스의 `1.3.0,<service-id>:1,...` 기록이다.
두 Kernel-Power 이벤트의 BugcheckCode는0이며 이것만으로 전원 상실을 확정하지 않는다.
6008 메시지의 이전 종료 시각05:50:34/07:33:32는 남아 있는 앱 기록보다 이르므로 정확한
중단 시각으로 사용하지 않는다.9월25일 부팅 뒤 -15.531초 시계 보정도 기록돼 있다.
관찰 시각 간격을 누락 행 수로 환산하거나 원본에서 NUL을 제거하지 않았다.

9월25일 system.log.4에는07:55:39 API 완료 뒤08:02:58 앱 시작이 이어지며 그 사이 정상
종료 기록은 없다.9월8일 상세 system 로그는 회수한 회전 로그 범위보다 오래됐다.
9월25일08:03:34에 CSV를 연 경로는 확인했지만, 이전/설치 전 두 AppData 목록에서 사건
날짜의 CSV 파일명을 찾지 못했다. 전체 NAS 부재 판정이 아니며 CSV 참조 영향은 미평가다.
기존 stderr 전체의 이미지 writer 실패43줄은 선행 프로세스 시작 줄 기준 PID별로
2488:1,15232:1,27440:12,12944:13,12156:16이다. 경고 자체의 시각·예외·capture ID가 없어
과거 drop15 또는 이번 NUL과 같은 원인으로 묶지 않는다.

검토기의 바이트 구간/해시20개와 provider·카디널리티4개 selftest, Ruff F/E9는 exit0이다.
첫 실행은 로컬 CRLF와 SSH LF 전송 바이트를 직접 비교해 본 검사 전에 exit1로 중단됐다.
원래 실행/도구를 보존하고 R2가 실제 전송 바이트를 검산했다. R2 exec97843은43.453초,
exit0/stderr0으로 끝났다. 실행 종료와 입력 불변·출력 해시는 독립 검토에서도 확인했다.

- Windows 원문: `P30/legacy-nul-windows-events-162548816287/stdout.log`,
  SHA `983e6fca5f67a9c973b54cde229069faf76550336994be6720909f62c78f2ce0`
- 대조 요약: `P30/legacy-nul-causality-d5d11a10b514/summary.json`,
  SHA `05a242a6dd7d0c06f69417fe2ad876ffea09fc47de53c915b4aa7125b10ed951`
- 독립 검토: `P30/legacy-nul-closeout-23ce77b56dd0/review.json`,
  SHA `f96baeb53c47f01e9badba994e28f255cd47c397ed7cc87a7e0e13e189c8ef8b`
- 선택 로그/XML/실행/분석48파일109,899,389bytes를
  `Z:/SmartFactory/20261017/return/legacy-nul-closeout-23ce77b56dd0`에 복사해 전부 해시 대조했다.
  별도 복사 영수증 SHA `61c0f3d0506ffd510e74f0467bac0f8dacf80b26ec1be40f102e942470410701`.
  대형 fact 사본은 기존 개발 PC 회수 위치에 보존하며 중복 복사하지 않았다.

다음은 보존 CSV/압축 목록의 사건 자료와 참조·누락 범위, 복구 가능성 및 처리안 확인이다.
120분 health 초과/worker 최종화 실패 원인과 나머지 전체R4도 계속한다. 새 전체 백업·설정
변경·설치·강제 종료는 없으며01:31 화면은 Smart Factory 전면 Running/작업60295·1이다.
Low Signal OFF·물리 NOT_TESTED·120분 FAIL·출시 HOLD·기존 롤백 기준과 목표active를 유지한다.

## 2026-10-17 02:09 KST — 종료 검산의 파일 열기 변동과 읽기 크기 비용 분리

원래120분 실행 `run-382f1d686bd7`의 마지막 설정 확인은 관찰 창 종료1.4268911초 뒤
PASS로 끝났다. SSH로 당시 회수한9개 파일의 원문·해시·수정 시각을 최종 manifest 사본과
다시 대조했다. 다음 코드 경로는 설치 payload 재검산 → 결과 전수 검산 → 종료 기대값
저장이다. worker 결과/기대값이 없고 중간 단계 기록도 없어 어느 호출에서180초를 넘겼는지는
여전히 미확정이다. 이번 로컬 계측을 원래 서버의 실행 시간으로 대체하지 않는다.

해시로 고정한 원래 도우미 commit `b735967e…`와 동일 회수 자료로 `review_window`를
세 번 실행했다. component 파일70,076개(HTTP67,191·자원1,443·프로세스1,442)를 매번
검사했고, 기준/소스101개의 전후 해시도 일치했다. 세 결과 모두 기존 재검산 JSON과 값이
동일하며 health 성능 실패 두 항목을 그대로 재현했다. 원본 JSON은CRLF, 새 JSON은LF여서
원시 해시는 다르며, 읽기 중 줄바꿈만 정규화한 바이트와 파싱 값이 각각 일치한다.
원본 파일의 줄바꿈이나 내용은 변경하지 않았다.

| 실행 순서/계측 | 전체 review | HTTP manifest | 파일 열기 합계 |
|---|---:|---:|---:|
| cProfile 최초 | 369.897초 | 324.585초 | 282.671초 |
| 파일 열기 시간만 기록 | 84.367초 | 57.878초 | 13.676초 |
| 동일 cProfile 재실행 | 96.225초 | 68.579초 | 14.538초 |

세 실행 exit0, 강제 종료0, stderr0이다. 별도 열기 기록78,723개의 경로별 횟수를 실제
manifest와 health/body/resource 재독 순서로 독립 정산했다. 최초/재실행 cProfile은 함수
호출 수도 동일하다. 큰 변동은 native open에 집중됐지만 캐시·호스트 상태를 통제하지
않았으므로 캐시나 보안 제품을 원인으로 확정하지 않는다. 경로 검사 누적은25.611/20.813초다.
read 비용은50.382/53.411초로 두 실행에서 계속 남았다.

이 비용을 구분하기 위해 기존 파일300개(2,083–10,654bytes, health JSON·image body·resource
JSON 각각100개)를 선택했다. 파일마다 읽기 크기 순서를 회전하고 두 번째 반복은 역순으로
실행했다.2,400회 모두 EOF까지 읽은 크기/SHA가 원래 manifest와 일치했다.

| 한 번에 요청한 읽기 크기 |파일600회 읽기 합계|같은600회 파일 열기 합계|
|---|---:|---:|
|8KiB|17.944ms|92.939ms|
|64KiB|17.019ms|87.377ms|
|1MiB|291.022ms|93.864ms|
|16MiB+1byte|4,393.750ms|81.698ms|

확인된 범위는 **작은 파일에 큰 read 요청을 주는 도우미의 로컬 비용**이다. 전체 검산의
대체 구현·대형 payload 처리량·서버 성능 개선은 아직 검증하지 않았다. 다음 보완은 경로/
reparse·파일 집합·크기 상한·SHA·엄격 JSON 검사와180초 제한을 유지하는 bounded chunk
읽기이며, 경계 회귀와 동일 전체 자료 및 대형 payload 대조 후 서버에서 단계를 계측한다.
현재 제품/검증 원본 소스는 수정하지 않았고 설치·설정 변경·새 전체 백업도 없다.

- 전체 계측: `P30/canary-profile-f2e443ad5ed2`, `canary-open-11689b70fc21`,
  `canary-profile-repeat-b886d29c522f`; 실행 영수증은 각 execution 폴더에 보존했다.
- 읽기 크기 시험: `P30/canary-read-chunks-c3316cf982ef/summary.json`, SHA
  `4e35707909de37d8fea01352743fa24a339b209bfb88e218632315c4caae1c4b`.
- 독립 정산: `P30/canary-finalization-closeout-f448b77442e3/review.json`, SHA
  `364c53a1e9dafbd6c09062f6b08e1c72abfa8a39bad9323dd1804a774a660371`.
- 최초 정산의 CRLF/LF 원시 동일성 가정과 후속 함수명 부분 검색(read/seek) 오류는 각각
  exit1로 보존했다. R2는 정확한 함수명·원시 해시와 별도 내용 동일성으로 검산했고 exit0이다.
  정산 오류를 고치면서 측정4회를 다시 실행하지 않았으며, 분석 도우미5개의 Ruff F/E9도 exit0이다.
- 결과/소스/영수증44파일20,379,934bytes를
  `Z:/SmartFactory/20261017/return/canary-finalization-closeout-f448b77442e3`에 복사해 해시 대조했다.
  별도 전송 영수증 SHA `ccff57a25a4b0ec9ebd105b800ba480ea002c3db3fa0afab291b8990b0574562`.

진행은PROGRESS, 목표는active다. 원래 timeout 인과·health 초과2건·전체R4·과거drop15·물리
경계 시험과 정식 운영 승격은 미완료이며, 원래120분 FAIL과 출시 HOLD를 유지한다.

마지막 원격 화면 확인은02:10 KST이며 Smart Factory가 전면 Running이고 작업60295·1이 표시됐다. 작업 정보는 변경하지 않았다.

## 2026-10-17 02:32 KST — 종료 검산 읽기 보완과 전체 자료 대조

검증 도우미의 `stream_fact`/`read_json`을64KiB 단위 읽기로 보완했다. 짧은 read는 EOF로
간주하지 않고 계속 읽으며, 바이트 상한·경로/reparse·파일 집합·잠금·동일성·해시·JSON
중복 키/비유한 수 거부를 유지한다. 제품 앱, 설치본, 설정,180초 finalization 제한은 변경하지 않았다.

- 수정 전 동일11개 회귀: exit1, 실패4/오류2. 수정 후11개: exit0.
- 기존 영향 범위11개 test 모듈152개: exit0,199.464초. 설치/관찰/세대/설정/종료/health/trace/
  candidate/진단 타이밍 소비자와 실제 Windows 파일 잠금·독립 프로세스·루프백 검사를 포함한다.
- 실제16MiB JSON 및512MiB 해시의 상한 직전/동일/초과, UTF-8 청크 경계, 짧은 read,
  I/O 오류가 부분 성공으로 처리되지 않는 조건을 검사했다.
- Python3.12의 새 프로세스마다 원본 또는 현재 소스를 선택해 아래 순서로 실행했다.
  두 코드의 실제 import 모듈11개 중 차이는 보완한 두 파일뿐이다. 테스트/비교 중 소스 변동0이다.

|순서|코드|70,076개 수집 파일 및 결과 검산|1,899개 설치본 구성 파일 검산|
|---|---|---:|---:|
|1|원본|80.158초|25.701초|
|2|수정|29.436초|4.657초|
|3|수정|29.329초|4.670초|
|4|원본|81.914초|7.648초|

수집 자료 검산은 HTTP67,191/resources1,443/processes1,442개의 모든 크기/SHA와 후속
health/resource 내용을 검사했다. 네 번의 전체 결과가 기존 재검산과 동일하며 원래
`http-component-failed`, `all-health-including-boundaries-failed`를 그대로 유지한다.
worker-result/종료 기대값 누락도 원본에 새로 채우지 않았다. 로컬 평균 검산 시간은
81.036→29.383초(관찰 감소63.74%)다. 설치본 구성은 총563,853,145bytes이며 가장 큰
실행 파일246,141,440bytes를 포함한다. 전체 잠금·파일 집합·해시 확인과 재검산이 모두 통과했다.
캐시/호스트 상태를 통제하지 않았으므로 첫 설치본 검산의 변동이나 원래 서버 timeout을
특정 원인에 귀속하지 않는다. 이 결과는 서버 개선 PASS나 새120분 통과를 의미하지 않는다.

- 실행 폴더: `C:/Users/user/Desktop/SmartFactory/RB17_3f0ba68a`.
  정확한 명령/환경은 `native-affected/request.json`, 각 `*-execution/terminal.json`에 있다.
- 독립 정산 `review.json`: SHA256 `cb5eaad6f60b6eb95c260031bf5a8263f5e31876b8ca8e9ad51a4dab11b25261`.
  정산/Ruff F,E9/diff check 모두 exit0. comparison4회의 stderr는0bytes다.
- 코드·회귀·설계 commit: `2ab06e1d1f019bc3e51b7fbc59f1cf7dcbfbf2d9`.
  `commit.json`에서 세 Python 파일의 시험 바이트와 commit blob SHA가 같은지 확인했다.
  다른 진행 문서의 미커밋 상태와 현재 운영 설치본의 build commit을 구분한다.
- 증거/시험 소스134파일21,146,257bytes를
  `Z:/SmartFactory/20261017/return/bounded-read-2ab06e1d-RB17`로 복사하고 SHA를 대조했다.
  `share-receipt.json` SHA256 `b935efed679d8bea953cef040133ed1f82f4c3b53cd2692dbecb68cc841f8be7`.

이번 작업은 개발 PC의 기존 자료만 읽었고 서버 설치·재시험·설정 변경·전체 백업은 하지 않았다.
다음은 clean helper source의 실행 묶음 검증과 같은 서버의 단계별 종료 검산 계측이다.
원래 timeout 인과, health 초과2건, 전체R4·과거drop15·물리 경계·운영 승격은 미완료이며
PROGRESS·목표active·출시HOLD를 유지한다.

## 2026-10-17 03:32 KST — 같은 서버의 종료 검산 비교

원래120분 자료를 읽기 전용으로 재검산했다. 원본 코드 실행은600초 진단 상한에 걸렸고,
보완 코드의 별도 실행은100.897초에 끝났다. 보완 코드가 계산한 전체 결과는 기존 FAIL과
동일하다. 이는 같은 서버에서의 오프라인 검산 완료 증거이며 새120분 관찰 PASS가 아니다.
운영 앱과 설치본은 그대로이며 원래180초 finalization 제한도 변경하지 않았다.

|대상|진단 전체|관찰 자료 검산|HTTP 구성 파일 검산|판정|
|---|---:|---:|---:|---|
|원본 코드 / `R74a081de9e69`|600.147초|미완료|미완료|outer-deadline, exit1|
|보완 코드 / `R0d3a16e08d51`|100.897초|86.384초|50.870초|전체 결과 동일, exit0|

원본은 payload-open39.947초와 payload-recheck5.735초 뒤 `component-http` 중 중단됐다.
실패 시 중단하는 launcher 때문에 수정 코드 차례는 실행되지 않았다. 원본 실패 launcher의
SHA/정리 상태를 확인하는 새 묶음으로 수정 코드만 실행했다. 기존 묶음·결과는 보존했다.
새 실행의 resources/processes 검산은17.319/14.419초, payload-open6.945초,
앞/뒤 재검산2.998/3.092초다. 캐시/호스트 상태는 통제하지 않아 정량 개선율이나 과거
180초 timeout의 인과를 확정하지 않는다. 당시 정확한 중단 호출은 원래 증거에 없다.

- 전체70,076개 component 파일과 결과 값, 실제 import 모듈11개의 고정 소스를 대조했다.
  설치본1,899개와 제거 파일1개, 합계564,087,405bytes의 잠금·해시·재검산을 통과했다.
- 두 실행 모두 원래 핵심 입력13개의 해시와 worker-result/종료 기대값의 부재를 보존했다.
  앱5개 프로세스의 PID·생성 시각·실행 경로는 전후 동일하다. 진단 owned Job의 잔여0과
  해당 진단 프로세스 부재를 확인했다. 원본 실패 실행을 완전 검산 PASS로 바꾸지 않았다.
- SSH stderr는0bytes가 아니다. 각각 `LAUNCH_EXIT=1/0`의 Write-Host 정보 레코드1개인
  CLIXML을 원문과 대조했다. 오류 스트림으로 오인하거나 버리지 않았다. SFTP는 두 번 모두
  exit0/stderr0이며 회수44/56개 파일 모두 서버의 독립 해시와 일치했다.
- 앞선 로컬 ABBA는 자료 검산 후 설치본 잠금을 검사했다. 잠금을 유지한 추가 첫 검산은
  299.704초였고, 잠금 해제29.889초·잠금 유지 재검산31.425초였다. 시작 handle은 각각
  2,098/4,001개다. 잠금 유지로 첫 지연을 재현하지 못했고 잠금 보호를 제거하지 않았다.
- 기존 native owned Job 제어기16조건과 요청/입력 거부14조건을 검토했다. 새 launcher의
  변화는 new-only 선택·구분 schema·원본 실패 영수증 선행 확인이며 Python 모듈/입력은
  동일하다. PS5.1 parse와 관련 Python Ruff F/E9, 실제 두 결과의 독립 검토기는 exit0이다.
  이미 통과한 읽기 회귀11개/영향 범위152개는 소스가 같아 반복하지 않았다.

개발 증거는 `Desktop/SmartFactory/RP17_20261017_72c856a9`와
`Desktop/SmartFactory/RPN17_20261017_0c62910a`다. 양쪽 서버 전달은 Z send→원격 탐색기
서버 로컬 복사→31파일 전체 해시 대조를 완료했다. 서버 원본 결과는 각각
`C:/Users/user/Desktop/SmartFactory/R74a081de9e69`, `R0d3a16e08d51`에 보존한다.

|정산 파일|SHA256|
|---|---|
|RP17/local-replay-review.json|`3d340cb9db56b661a244c3d2391a12803d5891841eb0ec555cb45288ad9d9ddd`|
|RP17/server-replay-review.json|`7dfee4ac61d0dde092c7372c413076d605fda1f25a99c0813be73e10c7c29f41`|
|RPN17/server-replay-review.json|`a2bbd7d4c916ce01b009dc6f0f0bfb5dbf54ccfa64f9f19ffb956e41b946c0bc`|
|RPN17/goal-turn-review.json|`6b2c74bb626cf76fae7b8c150302fdf36bb1c8b3ed081f28631c4c0078298be6`|

진단 소스/결과518파일43,672,994bytes를
`Z:/SmartFactory/20261017/return/offline-replay-RP17-RPN17`에 복사·해시 대조했다.
전송 영수증은 같은 날짜 records의 `offline-replay-RP17-RPN17-receipt.json`, SHA
`2474c2c878e1230286b910799264f7044162e6a3570e3794acda30c017276517`이다.
새 운영 데이터 전체 백업·설치·설정 변경·자동120분 재시험·운영 승격은 수행하지 않았다.

다음은 보존된 HTTP/resource/process 원문에서 health 초과2건의 실행 시각과 부하를 대조하고,
실제 finalization 범위·전체R4/과거NUL 영향·drop15·물리 시험의 남은 근거를 확보하는 것이다.
현재 PROGRESS/목표active/출시HOLD이며 공식 롤백 기준은 갱신하지 않는다.
03:31 KST 최종 화면은 Smart Factory 전면 Running/60295·1 적용 상태다.


## 2026-10-17 04:04 KST — 1.0.30의 같은 요청 CPU 진단 시작

기존120분의 health 초과2건은 HTTP/resource 대조를 이미 마쳤으나 같은 요청의 서버 내부
추적이 없어 원인이 미확정이다. 같은 작업을 새 분석으로 반복하지 않고, 현재1.0.30의
새 지연을 포착하도록 진단 도우미만 확장했다. 제품 설치본·설정·백업은 변경하지 않았다.

helper commit `0b94035346e3d14ccd4d691a5a1c109ec53afeaf`은 등록된1.0.29/1.0.30과
각 payload SHA의 정확한 쌍만 허용한다. 과거 spec의 후보 생략은1.0.29만 뜻하며,
1.0.30은 명시해야 한다. request/spec/package/설치 파일/health/config의 교차 조합을 거부한다.
48개 단위 검사·8개 native 그룹·frozen11조건이 exit0으로 완료됐다. 예상 거부 경로의
자식 exit1은 각 시험에서 확인한 값이다. 테스트와 원문은 `HD30_20261017_1c41bd2a`에 있다.

Git 추출 소스88개로 빌드한 EXE는16,090,979bytes/SHA256
`09783723707c8bff4da674fe9954eb4bda8f75f8ffdb46a78492f2eacd0e0b2d`이며 package manifest는
`9e6f7e4c40dbe12d58a055c94bfb20c355c33138b16abc82fed18291db9f8c71`다.
Z의 `SmartFactory/20261017/send/HT30_20261017_1c41bd2a`를 거쳐 CRD 탐색기로 서버
`C:/Users/user/Desktop/SmartFactory/HT30_20261017_1c41bd2a`에 복사했다.
15파일/16,924,405bytes의 SSH 해시와 일반 탐색기에서 폴더/요청 파일의 존재를 확인했다.

준비 중 서버 시계가 개발 PC의 조회 완료보다 약6초 앞서 configuration-time-order가
발생했다. 시계나2초 검사를 바꾸지 않고 같은 고정 읽기 자료의 캡처 시각이 지난 후
10분 이내의 자료로 재검토했다. 설정 fingerprint/승인 필드 PASS이며 Low Signal OFF다.
실행 직전에는 같은 main17996/backend14012의 native 생성 식별자와 build를 다시 확인했다.

03:50:57 KST count-to-zero로 작업 정보가 비워져 현재 생산 여부를 사용자에게 질문했다.
읽기에서 제품/금형은 빈 문자열이고 valid=false였다. 화면의12345/123은 입력 안내값이며
현재 작업 정보로 취급하지 않는다. 속도/압력0의 한 시점도 전체 구간의 비생산 증거가 아니다.
새 진단은 이 미입력 상태/갱신 시각까지 결합했고 값을 임의로 넣지 않았다. 결과를 생산 중
동시 부하 QA로 사용하지 않으며 제품 정보 답변은 계속 대기한다.

최초 stdin 전달은60초 응답 제한에 걸렸다. 같은 PowerShell PID15772/생성 식별자가 계속
살아 있고 CPU0.28125초가 변하지 않으며 자식/새D·H·T폴더가 없음을 확인했다. 이때 실행을
재시작하지 않았다. 같은 bootstrap 바이트를 압축해 직접 전달하는 읽기 전용 해시 시험에서
SHA256 `446d576b49023d9d3452fb28838584b0ffafeacfd94f1ff94da4b1221ba99d28` 일치를 확인했다.
그 뒤 정확한 세대·실행 경로·명령·무자식 상태를 확인한 전달 프로세스만 정리했고, native
종료(-1)·자식/새결과폴더0을 재확인했다. 운영 앱은 종료하지 않았다. stdin 경로 정체의
정확한 Windows 내부 원인은 미확정이며 제품 지연과 동일 원인이라고 주장하지 않는다.

동일 bootstrap의 직접 전달은04:02:18 KST에 시작해 exit0/CAPTURE_ENTRY_STARTED였다.
제어 폴더 `D91f6a5d8cb5f`, 결과 `Hd05e8e89be52`, 독립 감시자18200/실행기16748의
생성 식별자와 실제 생존을 확인했다. 최대900초·200ms trigger와 기존 WPR/Job 정리
계약을 유지한다.04:03:38 KST에는18표본이 생성됐고 두 프로세스가 살아 있었다.
시작/생존 증거는 완료·추적 품질·원인 판정이 아니며 `capture-start-review.json`에 연결했다.
원문 회수·해시·정리·동일 요청의 시계/스택 검토가 남아 있다. Smart Factory는 전면 Running이다.


## 2026-10-17 04:25 KST — 1.0.30 CPU 진단 종료·회수, 지연 미재현

같은 실행 D91f6a5d8cb5f/Hd05e8e89be52를 재시작하지 않고 확인했다.04:18:26 KST에
entry exit0, 감시자·실행기 동일 세대의 부재, 로그 writer 종료와 launcher 해시를 SSH로
확인했다.450/450요청의200ms 초과는0건이고 `NO_OUTLIER_OBSERVED`다.04:03:04~04:18:02
요청을 원문 body·응답 헤더·native 시계로 다시 검산한 중앙값은11.1268ms,
p99(nearest rank)는44.1703ms, 최대는216번 요청의175.4241ms였다. HTTP 오류/timeout은0이다.

서버 일반 탐색기로 결과를 `Z:/SmartFactory/20261017/return/CPU1030_1c41bd2a/Hd05e8e89be52`에
복사했다. 개발 PC 회수529파일/104,241,528bytes의 정확한 목록·해시, 서버 종료 시 확인한
launcher SHA `b2ebe729ef9b96d90396bd129f3c5439bbd46abdef8e1ce0825843e8373b048a`를 대조했다.
설정 전후 PASS와 동일 backend14012/생성 식별자, worker/coordinator exit0, Job 잔여0을
재검토했다. WPR stop/status-after-stop exit0, 추적 저장 및 recording 해제를 확인했다.
ETL76,546,048bytes/SHA `4d5bdb1bfba9202a38140441ec874f969e3dc406475a0e5367c3e29ed436db3d`를
보존했다. `recover_control.py`, `recover_and_review.py`, `closeout_capture.py` 모두 exit0이다.
독립 정산은 HD30의 `capture-closeout-review.json`(2027bytes/SHA `3637fd423ab9265e979e7d345174c2af13806dbfe65acc42199d8a4ff24a7635`)이다.

지연이 재현되지 않아 새 지연의 원인은 판단하지 않는다. ETL 이벤트 품질·스택 상관관계도
NOT_EVALUATED이며 이번 결과는 현장 성능 QA PASS나 기존120분 FAIL의 해제가 아니다.
측정 시작 시 작업 정보가 비어 있었고,04:10:26에 운영자 입력60227·5로 바뀌었다.
04:14경 CRD 접속 해제를 발견해 재연결했으므로 완전히 고정된 호스트 조건도 아니다.
전 구간 생산 상태를 단정하지 않는다.04:21 SSH 확인에서 앱의 같은 main/backend 세대가
REAL/Running이고 해당 작업 정보가 valid였다.04:23 화면은 탐색기를 닫은 전면 Running이다.

서버 측정 중에는 개발 PC의 보존 목록만 읽었다. NAS 목록1,029,146파일, 외부 압축
1,036,015멤버, 내부 압축13,328멤버에서 과거 NUL 두 사건의 UTC/KST 날짜에 맞는
CSV/metadata 파일명은 발견하지 못했다. 별도 CSV 구조17,046기록 중 header가 없는81건을
명시적으로 분리했고, sample_seq와 spot_observation_key를 함께 갖춘272기록/208고유내용
(19,544,972,285bytes)을 SQLite 멤버 해시에 연결했다. 이름/헤더 검색이며 실제 사건 키의
내용 검색은 하지 않았다. 따라서 과거 CSV 영향은 NOT_EVALUATED다. 근거는 HD30의
`historical-csv-catalog-search/summary.json`, `header-candidates.json`에 있다.

제조사 메일은 같은10월16일 답신을 다시 읽었고 새 회신으로 집계하지 않았다. 기존
comparator 보고서의 App1 지원·엄격한 미만 비교·REST/내부값 동일성 근거를 유지한다.
국내 대리점 국문 문의는 작성하지 않았다. 이번 턴은 실제 진단 종료·회수·원문 재검산과
보존 목록 범위 확인의 PROGRESS다. 목표active/출시HOLD이며 전체R4·과거drop15/NUL 영향·
물리경계·기존120분 실패의 남은 조건과 공식 롤백 기준은 유지한다. 자동 재시험은 시작하지 않았다.

## 2026-10-17 04:39 KST — 보존 압축 CSV의 과거 사건 키 검색 완료

직전 목표 턴의 실제 진단 종료·회수·450요청 검산을 PROGRESS로 분류했다. 이번에는
파일명/헤더 후보 검색을 넘어 보존 CSV 본문에서 두 NUL 사건의 관측 키를 직접 검색했다.
대상은 `da076946-7bea-4165-a52c-0b89397453b7:1`과
`3d88a702-47a1-4d91-ab5c-dd25d58715b5:1`이다. 사건 원문과 입력 목록의 SHA를 고정했다.

| 실제 검색 범위 | 논리 CSV 수 | 고유 내용 수 | 읽은 본문 bytes | 원문 키 발견 |
|---|---:|---:|---:|---:|
| 보존 외부 ZIP의 모든 CSV | 17,046 | 16,586 | 26,977,100,041 | 0 |
| 보존 내부 ZIP의 모든 CSV | 161 | 115 | 17,036,373 | 0 |

두 범위 사이의 중복도 제외한 고유 내용 해시는16,596개다. 외부 ZIP97개와 내부 ZIP68개의
대표 사본을 읽기 잠금으로 열고 전후 해시·파일 식별자를 확인했다. 모든 선택 CSV를 EOF까지
읽어 CRC/크기/SHA256을 기존 목록과 대조했다. 해시가 같은 논리 경로의 대응도 모두 남겼다.
UTF-8 및 UTF-16/32의 양쪽 바이트 순서로 키를 찾았고, 조각 경계에 걸친 문자열도 검사했다.
원문 바이트 검색은 `:10` 같은 접두부도 후보로 잡되 참조 확정은 정확한 CSV 필드로 구분한다.
이번에는 원문 후보 자체가0건이므로 해당 필드 재해석이 필요한 파일은 없었다.

도구 self-test42개(인코딩/조각 경계/정확한 필드/CRC 손상/시간 제한), 실제 외부 검색119.438초,
내부 검색과 외부23항목 정산은 각각 exit0이었다. 합동 정산 R1은 제가 NAS 목록의 기준 해시를
잘못 옮겨 적어 exit1이었다. 실패 소스/기록을 보존했고 원래 manifest와 실제 파일의 해시가
일치함을 확인한 R2의135항목 정산은 exit0이다. 완료된 본문 검색은 반복하지 않았다.

증거 루트는 `C:/Users/user/Desktop/SmartFactory/CSVREF_20261017_7eac9c23`다.

| 증거 | SHA256 |
|---|---|
| `summary.json` | `a0522bd8b6745e205b68d29eb47204aebb1420878fbefeb1a483fad82d3c5df6` |
| `nested/summary.json` | `6e53af20ac8f4c363c93eb8caa9f9838d60abbc214ba76cb412d72dd48c720dd` |
| `closeout-review.json` | `9d91c54aa41829eed681e03dbc534c0acaacb9c1a5e5e9cd15f8efd1ad31d97d` |
| `nas-loose-csv-selection.json` | `d05b56f4e72dd1c9cd668ee2aba1101553b136103dbd96e60a11f75b6afb6f48` |

검산 예: closeout의 outer/nested summary 해시를 비교하고 각 selection의 전체 논리 경로와
records의 고유 내용/alias 수를 정산한다. 외부17,046 및 내부161의 합을 고유 파일 수로 쓰지 않는다.

이 결과는 **보존 압축 CSV에서 두 키의 바이트를 찾지 못했다는 증거**다. 읽을 수 없는 외부
압축84·431의 내부 범위, 유실됐거나 목록에 없는 자료, 다른 키 및 다른 표현은 포함하지 않는다.
고정 NAS 목록의 압축 밖 CSV157,139파일/81,844,390,133bytes도 이번 내용 검색과 별도다.
해당 목록을 새로 정산했으며 기존 PLC·온도 등 검증된 사본과 먼저 연결한 뒤 검색을 확장한다.
기존 사본으로 충분한 파일을 다시 백업하지 않는다. 과거 CSV 영향은 NOT_ESTABLISHED이고
NUL 원인·전체R4·drop15·물리 경계·원래120분 FAIL/최종 승격은 미완료다.

이번 턴은 PROGRESS, 목표active/출시HOLD다. 제품 코드·설정·서버 상태·설치본·롤백 기준을
변경하지 않았고 새로운 전체 백업도 만들지 않았다. 서버 UI를 조작하지 않은 로컬 분석이다.

## 2026-10-17 04:50 KST — NAS 기존 사본 검색 완료·나머지 원본 읽기 진행

직전 압축 CSV 검색·정산을 PROGRESS로 분류했다. 고정 NAS CSV157,139개를 기존 사본의
원본 상대경로·크기·mtime에 대조해 PLC127,158개와 온도1,470개를 정확히 연결했다.
중복 경로와 metadata 불일치는0이었다. 두 사본 범위와 나머지28,511개의 합집합이 원래
목록 전체와 같고 서로 겹치지 않음을 별도로 확인했다. metadata 일치만을 내용 일치로 쓰지 않았다.

이후 기존 PLC ZIP과 온도 사본에서 실제 본문을 읽고 SHA256/크기와 전후 불변성을 검사했다.
PLC125,558고유 내용과 온도1,450고유 내용, 합계127,008개/28,370,766,043bytes의
두 사건 키 검색은0건이었다. 대응되는 논리 CSV는128,628개다. UTF-8/16/32 검색 도구는
이전42개 self-test를 통과한 같은 해시이며 ZIP은 EOF/CRC와 압축 자체의 전후 해시도 대조했다.
실제 검색122.235초/exit0, 독립 경로·입력·결과 정산27항목/exit0이다.

경로 정규화의 단독 시험에서 `/x`가 거부되지 않는 오류를 확인했다. 실패한 도구와 시험
기록을 보존하고, root/drive/traversal을 모두 거부하는 정산기의10조건을 확인했다.
실제 고정 입력128,628개에는 해당 경로가0건이었고 모두 엄격한 검사와 원래 목록 대조를
통과했다. 완료한 본문 검색을 반복하거나 실패 시험을 PASS로 재작성하지 않았다.

증거 루트는 `C:/Users/user/Desktop/SmartFactory/CSVLOOSE_20261017_f04c62aa`다.

| 닫힌 증거 | SHA256 |
|---|---|
| `summary.json` | `c5d75ceeab196b6869e78533c7bcb34e333a1fbd412e17aaa1c22eb26a8733bf` |
| `review.json` | `a3623a35929f4933f5bfa56ba816df71e6da62179869f816525524747a583c0e` |
| `remaining-nas-csv.json` | `48f70d14faec5b952abc95f02f405cb18248774606a77ccb672ecfc008789a8a` |

나머지28,511개/53,337,156,348bytes는 새 전체 사본 없이 승인된 NAS 공유에서 직접 읽기
시작했다. Z가 실제 `\\nas\스마트팩토리`인지 확인했고, 원래 UNC anchor의 상대경로만
대응한다. 다른 공유·drive·traversal·ADS 경로 거부와 실제 작은 원본/부모 식별자 확인 등
7개 사전 검사가 exit0이었다. 디렉터리와 각 파일을 읽기 잠금으로 열어 목록의 크기/mtime,
EOF 내용과 두 번째 전체 해시, 종료 전 경로/핸들 식별자를 대조한다. 일치하지 않는 파일은
검증 불가로 기록한다. 이는 NAS 전체의 원자적 과거 snapshot 증거가 아니다.

같은 실행 session58660/PID53208/생성FILETIME134366536994252918이04:50:38 KST에
실제로 살아 있음을 확인했다. 당시 완결된58기록/1,419,866,518bytes가 검산됐고 키 후보/오류는
각0이었다. `nas-live-observation-01.json`은 이 **진행 시점**의 증거다. 최종 summary와 terminal은
아직 없었으며 완료로 계산하지 않는다. 최대7,200초 예산을 유지하고 같은 handle을 계속 확인한다.
관찰 응답 제한만으로 재실행하지 않는다. 원시 후보가 나오면 정확한 CSV 필드 대조를 기록한다.

이번 턴은 기존 사본의 실제 검색과 나머지 NAS 실행의 PROGRESS/verified live wait다.
CSV 영향·전체R4·원래120분 실패·drop15·물리 경계·최종 승격은 계속 미완료이며 출시HOLD다.
제품·설정·설치·서버 앱을 변경하지 않았고 전체 백업을 추가하지 않았다.


## 2026-10-17 05:06 KST — 결과 저장·종료 경로 재현 검산과 NAS 동일 실행 추적

보존된 120분 FAIL의 review·최종 health·설정·제어 원문을 사용해 검산 이후 결과 저장과
worker 종료 경로를 개발 PC에서 실행했다. 실제 production expectation 생성/JSON fsync,
worker entry, Pipe의 done/hash 전달, supervisor와 Windows Job 정리를 사용했다.
수집·component 종료 관찰·현재 경계 읽기·payload 재검산·review_window는 이전 원문으로
대체했으므로 실제 120분 finalization 전체 시험이 아니다. 기존 FAIL 원문이나 누락 영수증을
새 결과로 채우지 않았다. 서버 앱에 접속하거나 설치/설정/전체 백업을 수행하지 않았다.

| 조건 | 확인 결과 |
|---|---|
| 실제 FAIL 결과 저장 | worker 결과 3,904,137bytes, done 해시 일치, 정상적인 실패 종료 코드1, 강제 종료 없음 |
| 최종 health 해시 변조 | shutdown-health-body-binding 거부, 오류 결과 저장, expectation 파일 없음, 종료 코드1 |
| 두 조건의 수명 정리 | 각 Job total1/active0/terminated0, worker와 event reader 종료 |
| 검산 근거 | 원문8파일·현재와 동일한 source11파일, 전체 review 구조 보존, 원래 누락2파일 계속 부재 |

첫 조건의 tail 시작부터 native worker 완료까지0.1778495초, 변조 조건0.1759917초다.
호스트·캐시·수집 구간이 실제120분 실행과 같지 않으며, 이 결과로 기존 timeout 원인을
확정하거나 서버 성능/전체 finalization PASS를 주장하지 않는다. 원래 FAIL과 출시HOLD 유지.

증거 루트: `C:/Users/user/Desktop/SmartFactory/TAIL17_20261017_eb913d5c`.
`replay_tail.py` 실제 exit0, `review_tail.py` 독립72항목 exit0, 두 도구의 Ruff F/E9 exit0.
summary 4,844bytes/SHA `afa25afd703acc030db5b4a3c12b8639356960a9daeb453bda039695e8f13537`,
review 4,120bytes/SHA `f6fec7a38f8aa626e884e13cb51a634caa3e00afcd0c93a0b0e92cbb8581b07e`.

NAS는 기존 session58660/PID53208/생성FILETIME134366536994252918을 그대로 추적했다.
05:05:24 KST native 생존 확인 후 중간 원문 접두부를 읽은 값은
187파일/11,415,056,245bytes, 키 후보0건/오류0건이다.
`CSVLOOSE_20261017_f04c62aa/nas-live-observation-02.json`에 관찰 시각·완전한 JSONL
접두부 해시를 저장했다. 아직 전체28,511파일 검사가 끝나지 않았고 summary/terminal도 없다.
완료된 사본·압축 검색을 반복하거나 NAS 검사를 재시작하지 않는다. 최종 출력과 변경/읽기 실패
파일을 대조한 뒤 정확한 CSV 필드 참조를 판정한다. 전체R4·과거drop15·물리 경계·120분
실패 해소/승격은 미완료다. 이번 목표 턴은PROGRESS, NAS 부분은 verified live wait다.

기록 저장 뒤 마지막 콘솔 출력은 CP949 인코딩 오류로 exit1이었다. 저장된 문서/상태는
보존했다. 첫 문서 확인은 예상 시각05:07과 실제05:06의 불일치로 exit1이었으며, 실제
저장 시각에서 제목을 도출한 재검산은 exit0이었다. 진단 시험과 NAS 검색은 재실행하지 않았다.


## 2026-10-17 05:16 KST — NAS 정산 준비·기존 CPU 추적의 요청 보존 한계 확인

NAS 결과 정산기 `CSVLOOSE_20261017_f04c62aa/review_nas.py`를 준비했다. 누락/중복/
경로·크기·시각·해시 형식 거부14조건, 정확한 이름의 참조 열/다른 열/파싱 실패 구분 등
추가8조건을 통과했다. 실제 완료 기록236개/13,752,206,016bytes를 고정 선택 목록과
대조했고 exit0이다. prefix 검사는 완료로 표시하지 않으며 최종 모드는 아직 실행하지 않았다.
최종 실행 뒤에도 실제 프로세스 종료 코드와 집계별 status를 별도로 대조해야 한다.

정산기 SHA `cf0aa78f26db0e507f3c7937163a785f6c8b010030b21cc7ca99d8a33abac425`,
중간 검산 SHA `31e602be5dd68b009a0705ae4315fbff67e3c4895b58df42f69dc848a1bd4c46`.
같은 NAS session58660/PID53208/생성FILETIME134366536994252918이05:15:31 KST에
살아 있었고, 후속 완결 기록 접두부는 284파일/17,940,041,121bytes,
대상 키0건/오류0건이다. 아직 전체28,511파일/53,337,156,348bytes 검사는
진행 중이며 재시작하지 않았다. `nas-live-observation-03.json`에 시점·접두부 해시를 보존했다.

기존1.0.30 CPU 추적을 개발 PC에서 해독했다. 같은 ETL76,546,048bytes/SHA
`4d5bdb1bfba9202a38140441ec874f969e3dc406475a0e5367c3e29ed436db3d`와 기존 디코더
실행 파일을 잠금·해시 대조했다. native 명령8.078887초/exit0, 전체 Job active0/강제 종료0.
서버 재수집·앱 조작은 없었으며 해독 원문은 `HD30_20261017_1c41bd2a/cpu-decode-01`에 있다.

CPU sample105,986/DPC47,234/ISR30,729, 합계183,949선택 사건의 raw ETW/ETLX payload
대조가 exit0이었다. 두 경로는 같은 TraceEvent 라이브러리이므로 독립 ETL reader 검증이
아니다. stack 누락2,265개·leaf/IP 불일치71개를 보존했고 전체 추적 품질은 미평가다.

인증된 launcher에 결합된 요청450개를 다시 대조했다. 해독된 CPU sample의 QPC 범위는
5912805083424–5913663392254, 85.830883초다. 최대175.4241ms 요청216의 loop QPC
5908971106869–5908971242719는 이 범위보다 앞이다. 따라서 이번 해독 자료로 해당 요청의
CPU 원인을 설명할 수 없다. 요청408–449의42개가 범위 안에 있어도 해당 thread의 모든
사건/스택이 보존됐다는 뜻은 아니다. EventsLost/BuffersLost0으로 전체 구간 보존을 주장하지 않는다.

`review_cpu_retention.py` exit0, 관련 분석 도구 Ruff F/E9 exit0. 결합 결과
`retention-review.json`2,665bytes/SHA
`77182ae9b48081b6f5f68e8caf7b4a5aa67ca3434796470c7386326eea8e596c`.
다음 latency 진단은 관련 동시 요청 부하에서 목표 요청 자체가 추적에 남도록 해야 한다.
기존 무초과 관찰/마지막 샘플로 과거120분 초과2건의 원인을 확정하지 않는다.
제품 코드 변경이 없어 전체 health/설치/120분 시험은 반복하지 않았다. 전체R4·drop15·물리
경계·full live finalization/출시HOLD는 유지한다. 이번 목표 턴은PROGRESS와 verified live wait다.


## 2026-10-17 05:31 KST — 동시 요청 수집기 로컬 종료·증거 검사

data6초/image0.25초 보조 수집기를 추가했다. health 중복 요청 없이 기존 HTTP 수집기의
응답/기록/fsync 검증을 사용한다. 실제 loopback HTTP와 native Windows Job에서 정상,
조기 중지, deadline, Job 배정 실패, 결과 body 변조, 예상하지 않은 중지, 입력 거부의
7개 시험이20.965초/exit0으로 끝났다. 별도 보존 결과52항목 검산과 Ruff F/E9도 exit0이다.
초기 Ruff의 미사용 json import1건은 제거했으며 최종 소스로7개 시험을 수행했다.

증거 `CONCURRENT_20261017_3e842b71/component-review.json`은2,979bytes,
SHA256 `2ddc10e9c6ad57d18871b4dc6a824b6b2c733042cd41bd9f59713fe713953062`다.
강제 종료2조건은 예상 FAIL로 보존했고 모든6개 실제 자식의 Job 잔여는0이었다.
조기 중지의 취소 슬롯과 HTTP FAIL을 유지했으며 이 결과를 서버 성능 PASS로 확대하지 않는다.
명시적 CPU 동시 부하 요청·trace 계약 연결, frozen helper, 서버 검증은 아직 수행하지 않았다.

NAS 동일session58660/PID53208/생성FILETIME134366536994252918의 생존을 확인했다.
완료된 중간 기록504개/26,209,283,257bytes, 키 후보0건/오류0건이며
전체28,511개 완료가 아니다. `nas-live-observation-04.json`에 접두부 해시를 보존했다.
제조사 답신의 App1 지원/엄격한 미만/REST 동일값 근거와 물리 시험 미완료를 구분한다.
이번 턴PROGRESS, 목표active/출시HOLD. 제품·서버 변경이나 새 전체 백업은 없다.


## 2026-10-17 06:01 KST — CPU 동시 진단 통합·배포 파일 검증, 서버 공유 접근 오류

명시적 `sfl-health-cpu-concurrent-request-v1`을 CPU contract/lease와 연결했다.
WPR 준비 뒤 data6초/image0.25초·health가 같은3초 미래 origin을 사용한다. 첫200ms 초과
health를 확인하면 보조 요청 중지 → WPR 저장/정지 → 보조 drain 순서로 종료한다.
900/960초·외부1500초·최종180초 제한, 설정·앱 세대 결합과 출시HOLD를 유지한다.

도우미 commit `bfd78daff0aa7c325c773dc272b1fa04e350ad87`의90개 소스와 패키지를 대조했다.
Python23+10+16=49시험, native PowerShell8+10=18묶음, 실제 frozen CLI/실패 worker14조건은
exit0이다. 실제 loopback HTTP·native 자식2조건에서 정상 정리/Job잔여0을 확인했지만
앱·health·WPR 경계는 합성이다. frozen 검사는 잘못된 입력/비어 있는 설치경로를 거부한
범위이며 실제 성공 concurrent capture나 ETW 품질·서버 성능 검증으로 확대하지 않는다.
보존 소스·기록·종료/해시405항목 검산도 exit0이다. 증거는
`CTRACE_20261017_e94b0a7a/integration-review.json`이며 SHA256
`9c7f6c516cbba4da04e2610aafdbbc3606513d4156b9178f6d62783b95bf69c7`다. 최초 준비의 test script CRLF/LF 불일치 실패는 보존했고,
정확한 committed test script로 native10묶음을 다시 통과했다. 실행 소스 차이는 없었다.

배포 도우미는16,099,563bytes/SHA
`2bca181493c2a2514baee3735f595fb10207e7360b938542edba4d546bc3a64d`,
package manifest SHA `dcc582429f73d1469415eb842e43a9ec1cef6e40cc3dda26ad0ceee06c972db4`다.
제품 설치본은 재빌드하지 않았다. 새 현장 묶음15파일/16,941,380bytes는 개발PC와
`Z:/SmartFactory/20261017/send/HCT30_20261017_e94b0a7a`에서 해시 일치를 확인했다.
서버 탐색기에서 부모 새로고침·정확한 새 폴더 접근을 시도했으나0x80004005로 실패했다.
서버 SSH 세션에는Z매핑이 없으며, 개발PC의 직접IP UNC 조회는 기존/새 폴더 모두
인증 오류1326이었다. 이 별개 관찰만으로 서버 오류 원인을 인증 문제라고 확정하지 않는다.
서버 로컬 복사·잠금 해시 검증은 미완료이고 진단은 시작하지 않았다.
`server-delivery-attempt.json`에 실패와 준비 상태를 구분했다. 서버 설정·앱 종료·백업은 없다.
05:50경 읽은 동일 main17996/backend14012와 작업60227·5, 승인 설정을 확인했고,
05:59 서버 화면에서 Running·Smart Factory 전면·작업60227·5를 확인했다.

NAS 동일session58660/PID53208/생성FILETIME134366536994252918은 계속 살아 있다.
완결 기록3,712파일/36,907,026,135bytes의 접두부 대조는 exit0이다.4개 이미지 대장 사본에서
raw후보1,874건, 정확한 다른열 참조1,188건을 구분했다. 모두 `spot_image_linked_observation_key`
열의 `da076946-7bea-4165-a52c-0b89397453b7:1`이며 각 사본297건이다.
이는1,188개 서로 다른 유실 사건을 뜻하지 않는다. `spot_observation_key` 정확 참조는
현재 접두부에서0이고 두 번째 사건 키의 raw후보는 정확한 필드값 일치로 판정되지 않았다.
전체28,511경로 완료·원본 CSV 영향 판정은 아직 남아 있다. 접두부 검산 SHA는
`b7b7cc67c6d77db4529077d32c71fe5d4a9dd7cda976af556bc3110d8477b7fe`다.
제조사 계약 확인은 물리 경계 PASS를 대신하지 않는다. 원래120분 FAIL/full live finalization/
R4/drop15/물리 시험·승격은 미완료다. 이번 턴PROGRESS, NAS는 verified live wait이며 목표active다.


## 2026-10-17 06:53 KST — 현장 동시 진단 종료·독립 추적 대조와 NAS 검색 최종 정산

서버 공유 경로가 다시 접근 가능해진 뒤 일반 원격 탐색기로 최종 로컬 복사를 마쳤고,
15파일/16,941,380bytes를 잠금 해시로 대조했다. 인증·ACL·네트워크 설정은 변경하지 않았다.
앞선0x80004005의 원인은 UNDETERMINED이며 실패 기록을 보존한다. 06:14:40 KST에 시작한
실제 frozen 동시 진단은 entry exit0으로 끝났고 결과2,215파일/111,484,594bytes를 회수했다.
launcher SHA는 `9f6deffded349776df74611de66258ea5a3836379de95e9b602d3dda2b79bfa1`이다.
설정/동일 backend14012·생성 시각 결합, 제어기/worker 종료, WPR 정리와 Job 잔여0을 확인했다.

health121건은 HTTP 오류/timeout0, 중앙값11.0282ms, p99 107.2514ms였고 마지막 요청120이
221.0337ms로200ms를 초과했다. 요청 전체와 native clock121건을 재계산했다. data41건,
image957건과 missed image 슬롯6개를 보존했다. 종료 후 취소 슬롯은 data109/image2637개다.
data1/image13건은 예정 시각보다0.0722–2.5579ms 일찍 시작해 기존 검사에서 invalid다.
이 판정을 완화하지 않았다. 저장1,006기록, pending/discard0이며 동시 HTTP는 FAIL/
채널 NOT_MEASURED다. 이 짧은 진단은 정식15/120분 성능 PASS가 아니다.

ETL76,283,904bytes/SHA `b7d06df21751cad3e0279ece5b5fd2df2ad6c5fe944ca744088e901a52c6d6cc`를
오프라인 해독했다. 대상 요청은 실제 보존 sample46.7969019초 범위 안에 있었다.
Windows tracerpt와 별도 TraceEvent 수집 결과를 대조해 전체사건1,337,420개 중 scheduler
964,958개, CPU sample90,533개, interrupt 종료/함수97,080개 및 대상 수집기 sample 스택1개가
일치했다. 커널35/사용자18프레임의 두 원시 StackWalk를 합친53프레임도 정확히 일치했다.
첫 검산의512MiB/XML2GiB 제한 불일치와 둘째 검산의 단일 스택 가정 실패를 보존했다.
검산기만 보완했고12개 스택 조합 검사 및 최종 전체 대조는 exit0, 서버 재수집은 없었다.
해독기의 전체 의미·모든 스택은 검증하지 않았다. sample stack 누락1,406개/leaf 불일치54개,
tracerpt 오류 envelope15005/111을 보존하며 선택 필드 대조를 전체 추적 PASS로 확대하지 않는다.

같은 요청의 연결 준비 구간192.48ms, 서버 route17.2605ms를 구분했다. native 수집기 구간
221.0456ms 중 CSwitch residency는1.0999ms, 비실행은219.9457ms다. 가장 긴 두 비실행 구간
127.5472/64.4168ms에서 outgoing state1(Ready), reason31/30이 관찰됐다. 합계191.964ms는
연결 준비 중 실행 준비 상태의 스케줄링 지연 증거다. 연결 구간은 초기 native 계측/Python/
socket 준비도 포함하므로 순수 TCP 지연으로 표현하지 않는다. state/offset 해석 근거는
[Microsoft CSwitch](https://learn.microsoft.com/en-us/windows/desktop/ETW/cswitch)와
[공식 PerfView 구현](https://raw.githubusercontent.com/microsoft/perfview/main/src/TraceEvent/Parsers/KernelTraceEventParser.cs)이다.
같은 구간의 PID9804는212 sample이며 추적 종료 process rundown 이름은 Explorer였다.
이는 경쟁 작업 조사 단서이고 Explorer나 네트워크를 근본 원인으로 확정한 증거는 아니다.

NAS 동일session58660은6,392.546초/실제exit0으로 종료했다. 남은28,511경로/
53,337,156,348bytes의 모든 완료 기록·경로·크기·해시·종료 영수증을 최종 대조했고 exit0이다.
기존 사본128,628논리 경로와 합쳐 고정 NAS CSV목록157,139개에 대한 사건 키2개 검색을
완료했다. raw1,874건, 정확한 다른열1,188건은 이미지 대장4사본의 같은관측키297참조씩이다.
`spot_observation_key` 정확참조0이며1,188개 별도 유실 사건으로 합산하지 않는다.
NAS 원자적 전체 snapshot/모든 CSV 내용 QA/원본 NUL 영향 판정은 이 검색으로 증명되지 않는다.
최종 정산 SHA `5a10372c92cbf2ae74d765abdff44d92b82059b341f978a3a0a6d40bab0b3384`.

실제 회수/closeout/CPU retention/scheduler 및 tracerpt 해독/독립 대조/구간 분석은 모두exit0,
최종 분석 도구 Ruff F/E9도exit0이다. 첫 기본 Python의 Ruff 모듈 부재는 저장소 backend
venv로 해결했다. 제품 코드를 변경하지 않아 재빌드·재설치·120분 재시험·새 전체 백업은 없다.
06:16 이후 작업 metadata가 비어 전체 생산 상태는 미확정이며 사용자 현재 제품/금형 확인은
대기한다. 서버 작업 종료 후06:25:46 KST 화면에서 Running·Smart Factory 전면을 확인했다.
이번 검산 단계는 개발PC의 보존 자료만 사용했다. 다음은 Ready 지연의 경쟁 작업/계측 영향과
14건 조기 시작의 격리 재현, 과거 이미지 참조 영향/처리 판단이다. R1/R2·full live finalization/
R3 실제물리시험/R4 전체QA/R5drop15/R6승격은 미완료이며 전체 목표active/출시HOLD다.
주요 근거: `CTRACE_20261017_e94b0a7a/capture-analysis-stage.json`,
`schedule-window-review.json`, `trace-independent-crosscheck.json`,
`CSVLOOSE_20261017_f04c62aa/nas-closeout-01.json`. 이번 목표 턴은PROGRESS다.


## 2026-10-17 07:04 KST — 보조 수집기 조기 대기 반환 수정·경쟁 작업 대조

현장14건의 조기 시작 경로를 조사했다. 새 보조 worker는 일반 관찰기의 ObservationStop을
거치지 않고 raw multiprocessing.Event를 HTTP 수집기에 전달했다. 개발PC Python3.12.6의
실제 native 대기960회에서 multiprocessing0.3ms의80회가 모두 일찍 반환됐고 최소 lateness는
-0.2964ms였다. threading480회는 조기 반환0이다. [해당 CPython 구현](https://raw.githubusercontent.com/python/cpython/v3.12.6/Modules/_multiprocessing/semaphore.c)은
Windows 대기를 정수 ms로 반올림한다. 이 근거는 누락된 deadline 재확인의 필요성을 보여주며,
서버14건 각각의 OS 내부 원인이나221ms 지연의 원인을 증명하지 않는다.

같은 worker 경로의 재현에서30ms 대기가0.0023ms에 끝나 수정 전exit1이었다. 보조 worker에
기존 ObservationStop을 연결하고 성공·예외 모두 bridge를 닫도록 최소 보완했다. 사용자 지정
중지를 유지하며 시각/음수 lateness 보정이나 기준 완화는 없다. 소스2파일을 commit
`d372d4efb98ea651b6a0062cf6e799a7ddb13d94`에 기록했고 검증된 실제 바이트와 committed blob SHA를 대조했다.
일반 HTTP/제품 로직/설치본은 변경하지 않았다. 기존 고정 도우미도 재작성하지 않았다.

실제 native 자식·loopback HTTP9시험, HTTP 구성요소32시험, native timing7시험,
기존 ObservationStop1시험은 모두 실제exit0이다. 6.2초 정상 자식의 data2/image25요청 전부
예정 시각 이후 시작했고 마지막 관찰 구간도 충족했다. manifest/본문·시각·종료 증거210항목을
별도로 검산해exit0이다. 실제 자식6조건 모두 Job 잔여0, 결함 주입2조건의 강제 정리와
변조/비요청 중지 등4조건의 FAIL을 보존했다. Ruff F/E9도exit0이다.
근거 `WAIT17_20261017_2d81a4c9/local-fix-review.json`, SHA
`09effa1ce48cf3a56fc7fea5735d2705f8e9fc5f95b8b65dbea84de8b8d9053b`. 새 frozen 패키지·서버 적용은 아직 미실시다.

별도 보존 추적에서64.4168/127.5472ms Ready 구간의 두 논리CPU residency를 빠짐없이
정산했다. 직후 교체 스레드는 각각 System TID13732(우선순위12), Explorer TID15572(10)이고
수집기 교체 시 우선순위는8이었다. 두 CPU 합계128.8336/255.0944ms 중 Explorer residency는
75.8099/106.8554ms였다. 앱·backend·DWM 등도 같은 구간에 실행됐다. residency는 DPC/ISR을
포함할 수 있어 정확한 CPU 작업시간이 아니며, process 이름은 추적 rundown 연결이다.
Explorer가 단독 근본 원인이라는 인과 증거로 확대하지 않는다. 과거 탐색기 창 종료 비교도
CPU는 낮아졌지만 health 실패가 남았으므로 이미 수행한 비교를 새 해결책처럼 반복하지 않는다.
근거 `CTRACE_20261017_e94b0a7a/competing-window-review.json`, SHA
`2942d109b548f5c02f7b11c98a32770546ca67da4566bdae32f5ebadc532b78a`, 실제 분석exit0.

기존120분 FAIL, 현장14invalid, R1/full live finalization/R3물리시험/R4전체분류/R5drop15/
R6정식QA·승격은 유지한다. 이번에는 서버 접속·설정 변경·새 전체 백업·제품 재빌드·재설치가
없었다. 목표active/출시HOLD이며 이번 목표 턴은PROGRESS다. 다음은 새 도우미 패키지 검증,
경쟁 작업/계측 영향의 인과 확인, 완료한NAS 검색을 이용한 과거 자료 영향/처리 판단이다.


## 2026-10-17 07:34 KST — 수정 도우미 frozen 검증·서버 전달·동일 실행 관찰

보조 수집기의 대기 수정 commit `d372d4efb98ea651b6a0062cf6e799a7ddb13d94`의90개 소스를 추출해 별도 미서명 도우미를
빌드했다. EXE16,100,167bytes/SHA `852b6c461fa40b4f10da0a52e6f8b8621f0eb9d8cb9d60b3707e1e3352900bd2`,
manifest SHA `7524a0102568af2f3dfd74482fe603c734a8fc9e2e344eb76e4927c8fd7fad86`다. 제품1.0.30 설치본은 변경하지 않았다.
빌드exit0, frozen CLI14조건(설명1정상/거부13예상실패), 실제 frozen 부모·자식3조건을 확인했다.
정상6.2초에서 data2/image25요청의 조기 시작0, 외부 중지와 소유 Job 시간 제한 종료도
예상 결과/잔여0으로 확인했다. 외부 시험 controller를 사용했으며 전체 WPR 성공 경로의
로컬 검증으로 확대하지 않는다. 소스부모가 onefile bootloader를 넘어 semaphore를 전달한
최초 시험은WinError6/exit1이었다. 시험 controller를 frozen 내부에서 실행하도록 고쳤으며
그 실패 자료와 정리 결과를 보존했고 제품 결함으로 분류하지 않았다.

패키지90소스/15내장모듈/기준 파일·요청본문·종료 증거569항목 대조는exit0이다. 상세 범위는
`CWAIT_20261017_c8314fa2/package-review.json`과 `frozen-companion-verification-r2.json`에 있다.
서버 공유 새 경로 접근 오류 때문에 기존 승인SSH로 새 수신 폴더에 전달한 후 CRD 탐색기
복사/붙여넣기 버튼으로 최종 `HCTW30_20261017_c8314fa2` 폴더를 만들었다. 기존 공유 전달본과
서버 최종15파일의 크기/SHA를 대조했다(exit0). 매핑·인증·부모ACL은 변경하지 않았다.

Smart Factory Running·60180/38 전면을 확인한 뒤 승인SSH로 한 번 실행했다(bootstrap exit0).
서버상07:30:02 시작, control `Dc2aced764774`, 결과 `H49927dfe58dc`다. 감시 PID6912와
entry PID10000의 생성시각을 매번 대조하며 2026-10-16T22:34:28.9553090Z 조회에서 두 세대가
실제로 살아 있고 probe 122개가 확인됐다. 현재는 진행 중이며 완료·성능PASS가 아니다.
요청은최대900초/최초200ms초과 포착이며 기존 종료예산을 유지한다. metadata60180/38은
관찰값이며 전체 생산상태의 별도 확인으로 해석하지 않는다. 다음 조회도 같은 실행만 사용한다.

기존120분FAIL/과거14invalid/R1·R2·full live finalization/R3물리시험/R4전수분류/R5drop15/
R6정식QA·승격은 미완료다. 새 전체백업·재설치·설정변경·120분재시험은 없다. 목표active,
출시HOLD, 이번 목표 턴PROGRESS이며 서버 수집은native 생성시각으로 확인한 verified wait다.
현재 단계 근거 `CWAIT_20261017_c8314fa2/progress-stage.json`. 종료 후 원본 해시와 전체 결과를
회수·검산하여 조기 시작과 CPU 지연을 따로 판단한다.


## 2026-10-17 07:56 KST — 대기 수정 현장 진단 종료·과거 이미지 참조 영향 확인

같은 실행 `Dc2aced764774` / `H49927dfe58dc`의 native 생성시각을 확인해 종료까지 추적했다.
entry/coordinator/worker exit0, owned Job 잔여0, WPR 정지를 확인했다. 서버 원본의 인증된
launcher SHA와 공유 회수본·개발PC 사본 8,039파일/157,175,652bytes의
목록·크기·SHA를 대조했다. 새 설치·설정 변경·전체 백업은 없다.

900초 동시 CPU 진단의 health450건에서200ms초과0, 최대143.0205ms,
중앙값10.8884ms, p99 66.3359ms였다.
data 요청150/누락0/취소0,
image 요청3599/누락1/취소0이며,
모든 본문·시각·예정 슬롯을 재대조했다. 보조 요청 조기 시작은0으로 이번 실행에서 대기
수정 효과를 확인했다. 과거14invalid를 재분류하지 않으며 이전120분FAIL도 유지한다.
전체 생산상태 별도 확인과 추적에 따른 계측 영향이 남아 정식15/120분 QA를 대신하지 않는다.
이미지 최대256.8425ms 요청1717은 다음 예정시각보다52.6417ms 늦게 응답을 끝냈고 슬롯1718을
놓쳤다. 이는 관찰기의 요청 누락이며 제품의 이미지 저장 누락이나 과거drop15와 동일시하지 않는다.

오프라인 CPU 해독과 원시/변환 이벤트133,084건의 선택 필드 대조는exit0이었다. 별도 ETL
reader 교차검사는 이번 실행에서 하지 않았고, 스택 누락1,209/최상단 IP 불일치51건을 보존했다.
실제 CPU 표본 범위는54.4943276초로 health424~449만 포함했다. 가장 느린health215의143.0205ms
및 이미지1717의256.8425ms는 모두 보존 범위 밖이었다. health215의계측상connect135.7867ms,
image1717의headers_wait229.1069ms는 관찰했으나 CPU/네트워크 근본 원인은 미확정이다.
다음 진단은 기존200ms기준을 유지하면서 보조 요청의 주기 초과·누락 시점에도 추적을 보존하도록
설계·격리 검증한다. health만 기다리는 현재 방식으로 같은900초를 반복하지 않는다.

별도로 개발PC에 보존된 누적 이미지 대장2,247,226,565bytes/4,385,307행을 전수 파싱했다.
원문 SHA `97a3fceb72b07bed757d11cfec73b20c1e0491ecbcc15fd394a1d978e88fb490`는
읽기 잠금 중 전후 일치했다. NUL801 사건의 관측키를 참조한297개 행은 모두captured,
stale, under_range였고 NUL1611 사건의 정확 참조는0이었다. 기존 NAS4사본의 두 사건에
대한8개 행번호 비교가 일치했고, 독립 SQLite 인덱스의 ID/경로/SHA/크기/서비스/시각/행번호
912항목 대조는exit0이었다. 실제 이미지 파일 존재·디코딩·원본 누락 수·손상 원인은 미확정이다.

분석 도구의 최초 JSON 배열 처리 오류와 행번호의 header offset 오류는 각각exit1로 보존했다.
시각차와 기록된 link age의 완전 일치 검사도exit1이었다. 297건 중1건은 약1.51ms 차이가
남아 R3에서 차이를 보존했다. 실제 코드는 capture 시각과 link 확인 시각을 별도로 받으므로
이 차이만으로 제품 결함을 단정하지 않는다. summary의all_raw_rows_saved는 모든 '일치하는
파싱 행'을 보존했다는 의미로 reconciliation에 정정했으며 원시 CSV를 재작성하지 않았다.

현재 근거는 `CWAIT_20261017_c8314fa2/closeout-stage.json`, `capture-closeout-review.json`,
`incident-image-links-r2/reconciliation.json`, `missed-slot-review.json`이다. 회수·capture검산·종료검산,
CPU해독/선택payload대조/보존구간/누락slot검토의 실제exit0을 확인했다.
Smart Factory Running·60180/38 전면 표시를 확인했다. R1/R2근본원인·full live finalization,
R3물리시험/R4전체분류/R5drop15/R6정식QA·승격은 미완료다. 목표active/출시HOLD/이번 턴PROGRESS다.


## 2026-10-17 08:16 KST — 보조 요청 이상 알림 재현·수정·패키지 검증

이전 목표 턴은 현장 진단 종료·회수·분석을 완료한 PROGRESS이며 현재 턴도 PROGRESS다.
설계5.33의 health 정상/이미지 지연 상황을 개발PC loopback으로 재현했다. 수정 전에는
이미지353.0669ms 및 관찰기 missed slot1건에도 추적 저장을 요청하지 않고8초 시험 제한으로
중단됐다(exit1). 제품의 과거drop15 원인을 재현한 시험은 아니다.

도우미 commit `4a79d1fed517f3ddfd32008d7ab211de35589fea`에서 요청 실패·기존 failure 임계값 초과·다음 슬롯 도달/초과·실제
missed slot의 첫 알림을 단방향 Pipe로 전달한다. 원문 SHA와 예정/판단 시각을 묶고 기존
health 대기 전후에 확인한다. 부모가 중지를 요청하고 WPR 저장을 요청한 뒤 자식 저장을
마치며 원문·알림·결과 일치를 검증한다. health200ms와 data6초/image250ms 주기는 유지한다.
추적 저장 요청 뒤 도착한 알림은 late로 별도 기록해 포착 근거로 사용하지 않는다.

첫 수정 시험은 Windows Pipe 종료가 WinError109로 보고되어exit1이었다. 정상 EOF 처리를
보완한 재시험은exit0, health1건/이미지353.3175ms의 알림을
받아 저장 단계로 진행했고 owned Job 잔여0이었다. 알림부터 부모 관찰까지
1633.2821ms가 걸렸으므로 즉시 보존을 보장하지 않는다.
기존 정상450개 health 일정, 임계값 경계, 첫/동시/마지막/늦은 알림, 실패/중복/원문 불일치,
취소·spawn 실패·Job 정리를 포함한 소스 검사116개가 통과했다. health HTTP 첫 호출의
환경변수 누락(exit1)은 기록을 보존하고 지정 경로로 재실행해2개 검사 exit0을 확인했다.
Ruff와 git diff --check도exit0이었다.

같은 commit의 도우미만 freeze했고 제품 설치본은 다시 만들지 않았다. 도우미 EXE SHA는
`1c9dfa3e4fb8aacc2699e0a136a287d3e5ba6bf896e5a5c98fb80ab25eb0d086`, package manifest SHA는
`9d377ee6762ff5d4584599d384f7af433ca3aa6d4c3362cdbf558083eb2cf3b4`다. 실제 frozen CLI14조건과 frozen 부모/자식의
정상·중지 요청·시간 제한·이미지 지연4조건 검증은exit0이었다. 패키지에 포함된 field 모듈
bytecode와 commit 원문도 대조했다. 도우미 소스 경로는clean이지만 기존 문서 변경이 남아
전체 저장소가clean이라고 보고하지 않는다.

근거는 `CNOTICE_20261017_5a63b057/progress-stage.json`과 동봉 source/시험 로그/패키지다.
현재 사용자 확인값은60180/38이며 과거 측정 전체 구간의 생산 확인을 대신하지 않는다.
이번 턴은 서버에 접속하거나 설치·설정 변경·백업을 하지 않았다. 실제 WPR 지연 구간 보존,
R1/R2 원인·full live finalization, R3 물리시험, R4 전체분류, R5 drop15, R6 정식QA·승격은
계속 미완료다. 다음에는 승인된 경로로 새 도우미를 전달·결합한 뒤 해당 이상 시점의 현장
추적을 수집한다. 목표active/출시HOLD를 유지한다.


## 2026-10-17 08:54 KST — 보조 이상 알림 도우미의 현장 정상 경로 검증 완료

수정 도우미 commit `4a79d1fed517f3ddfd32008d7ab211de35589fea`의 패키지599항목 대조,
공유 전달·원격 탐색기 최종 로컬 복사 및 서버15파일 해시 대조를 완료했다. 승인된 SSH로
`Ddcf6567f8c79` / `H5ebe9b83fd48`을 한 번 실행했다. entry/coordinator/worker exit0,
소유 Job 잔여0, WPR 정지와 로그 writer 종료를 확인했다. 인증된 launcher SHA는
`7b9abd144eaed58a6690cb61f36704afd1615afb7638e6f66328acc1181139a4`다. 회수본 8,040파일/
156,853,939bytes의 전체 목록·크기·해시가 서버 기록과 일치했다.

900초 진단에서 health450건의200ms초과·HTTP오류·timeout은0이었다. 중앙값
9.1518ms, p99 77.8724ms, 최대
98.3963ms(요청300)다.
data 요청150/누락0/취소0,
image 요청3600/누락0/취소0이며
보조 요청 조기 시작은0건이다. 본문·예정 슬롯·native clock을
재대조하고 비동기 저장 pending/discard0을 확인했다. 보조 알림과 late알림은 모두없었다.
따라서 실제 서버의 정상 종료 경로를 확인했으며, 현장 이상 알림 시점의 추적 보존 경로는
이번 실행에서 행사되지 않았다. 로컬 이미지 지연 재현 성공과 실제 서버 이상 재현을 구분한다.

오프라인 CPU 해독과 원시/변환 이벤트 135,053건의 선택 필드 대조는exit0이었다.
보존 CPU 표본 범위는56.0115560초이며 최대health 요청의 전체 클라이언트
구간은 해당 표본 범위 밖에 있다. 표본 범위 안이라는 사실도 완전한 thread coverage나
원인을 입증하지 않는다. 스택 누락1,471/leaf IP 불일치
61건을 보존했다. 이번 ETL의 독립 reader 교차검사는 수행하지
않았고 전체 추적 품질·지연 원인은 미확정이다. 이전120분FAIL을 이번 무재현 결과로 바꾸지 않는다.

수집 전후 main17996/backend14012의 생성시각이 같고 Running·60180/38을 확인했다.
운영 화면은 Smart Factory가 전면에 보이는 상태다. 현재 작업 확인을 과거 전체 측정 구간의
생산 확인으로 확대하지 않는다. 제품 재빌드·재설치·설정 변경·전체 백업·120분 재시험은 없다.
결과 확인 예: `CNOTICE_20261017_5a63b057/closeout-stage.json` → `capture-closeout-review.json`
→ `cpu-decode-01/trigger-retention-review.json`의 원문 해시와 판정 범위를 확인한다.

회수·원문/종료 검산·CPU해독/선택payload/보존구간 검사는 실제exit0이다. R1/R2 원인·full live
finalization, R3 물리시험, R4 전체분류, R5 drop15, R6 정식QA·승격은 미완료다. 동일 진단을
성공 결과가 나올 때까지 반복하지 않고 기존 보존 자료의 분석을 이어간다. 목표active/출시HOLD,
이번 목표 턴PROGRESS이며 실행 중인 진단은 남아 있지 않다.

## 2026-10-17 09:07 KST — 과거 이미지 누락 목록 171,179개 역방향 연결 대조

기존 10월14일 검증 이미지 중 10월16일 설치 전 목록에서 사라진 **171,179개 /
1,694,057,930바이트**를 보존 백업 목록·완전 디코딩 증거·닫힌 image fact 인덱스와
대조했다. 모두 기존 백업과 크기·SHA256이 일치하고 디코딩 PASS 근거가 연결된다.
이 중171,163개는 image fact의 정확한 경로·크기·SHA256·행번호와 일치한다.
나머지16개는10월13일 조사·격리 보존한 미참조 이미지와 정확히 같으며 새로운 미참조
파일은0개다. 이16개 로컬 사본의 현재 바이트도 다시 해시 대조했다.

별도 bulk SQL 검산으로171,179개의 원본 목록·백업·디코딩 행번호와 fact 연결을 확인했다.
전체 인덱스4,385,307행에서16개 이미지의 크기·SHA256이 다른 fact에 연결된 경우도0이다.
이 결과는 해당 누락 집합의 분류이며 전체 과거 누락 이미지나 현재 서버/NAS 전수 검증은 아니다.
사본 증거는 당시 검증 경계에 해당하며 현재 서버 백업의 모든 바이트를 재검사하지 않았다.
개별 삭제 기록이 없으므로 사라진 이유·retention 삭제 여부·기존16개 저장 실패 원인과
과거drop15는 미확정으로 유지한다. 원본 fact 생성·복원이나 오류 판정 변경은 없다.

근거는 `C:/Users/user/Desktop/SmartFactory/R4REV_20261017_6f021c8a`다.
확인 예: `result/summary.json` → `result/relations.jsonl`의 원본 행번호 →
`independent-review.json` 순서로 대조한다. 결과 summary SHA256은
`96fddf629a06750522c8df6b5fa78d7dae29ccb41dd1cc9a8b6bbdc7470b7b58`이다.
거부 조건6개 검사, 최종 Ruff(F/E9), 실제 대조·별도 검산은exit0이다. 최초 시험의
스트림 정리 경고(exit0이지만 깨끗한 결과 아님)와 unused import lint exit1은
`verification-history.json`에 기록하고 수정 뒤 영향 검사만 다시 통과시켰다.
제품 소스 변경이 없어 전체 health/build·현장 시험을 반복하지 않았다.

이번 단계는 개발PC의 보존 자료만 읽었으며 서버 접속·설치·새 전체 백업이 없다.
현재 전수 목록과 나머지 데이터 finding, R1/R2원인·R3물리시험·R5drop15·R6정식QA는
미완료다. 목표active/출시HOLD/이번 턴PROGRESS이며 실행 중인 진단은 없다.

## 2026-10-17 — 과거 CSV 복구 후보102개와 추가 사본 부재 확인

사용자는 NAS 외 2023~2025년 온도·PLC 보관 PC·외장디스크·백업이 **없음**을 확인했다.
이 질문의 답변 대기를 종료했으며 사본 부재를 검사 통과나 손상 수용으로 해석하지 않았다.

온도 손상19개와 PLC 손상1개의 대체 사본 후보를 기존 NAS 목록1,032,015행과
읽을 수 있는 외부 압축 파일 멤버1,031,166개에서 검색했다. ZIP의 Unicode 표시 이름과
원래 CP437 이름을 구분하고, 기존 PLC 손상본이 검색되는 양성 대조를 확인했다.
파일명 날짜 후보70개 외에 실제 문제 행 날짜8개로 후보32개를 추가했다.
총102개 / 1,533,321,166바이트 / 32,190,279행이며 기존 검증 사본71개와 NAS 읽기31개다.
NAS는 이전 검증 Z: 경로·SHA와 현재 크기·수정시각·읽기 전후 SHA를 대조했다.
현재 NAS 전체의 원자적 스냅샷은 아니다.

온도19개 중17개에서 전후 참조 기록과 같은 내용8,124건을 찾았지만 반복이 많아
복원 관계를 확정하지 않았다. 2025-06-17 정리본915,343행을 추가 확인한 결과,
데이터행771172/902130은6열이지만 온도값524.62025/5082025와 단위SPOT가 남아 있었다.
원본 결합 형태 손상15행 중13행은 정리본에서 앞뒤 참조 기록이 바로 이어지는 위치도 있다.
이를 특정 변환 프로그램의 실행이나 손상 발생 원인으로 단정하지 않는다.
구조상6열이라는 사실만으로 정상 복구본으로 사용할 수 없다. 남은2개 온도 파일에는
선택 후보 안에서 같은 전후 기록을 찾지 못했다.

압축 멤버3개는 EOF·CRC·크기·SHA를 다시 검증했다. 온도2개는 기존 후보와 동일한
바이트이고 PLC1개는 기존 NUL108바이트 손상본 그대로였다. 다른 이름·병합 자료·중첩
압축·읽을 수 없는 압축까지 대체 사본 부재를 증명한 결과는 아니다. 원본 수정·복원·
새 전체 백업은0건이고, 원래 실패 판정·원인 미확정·출시HOLD를 유지한다.

근거는 `C:/Users/user/Desktop/SmartFactory/R4REC_20261017_b2964c10`의
`closeout-stage.json`, `reconciliation-r2.json`, `recovery-review.md`다.
확인 예: 최종 대상 분류 → candidate group/number → 원문 journal의 앞뒤 행·SHA 순서로 읽는다.
closeout SHA256은 `1696af1873b0e964a6b6db7abb94c38a6536cd7bb598f47bd5f49ddbd5e40e1a`다.
이름/문맥 검사7개, 최종Ruff(F/E9),102개 관계 검산·선택 정리본 재읽기는exit0이다.
초기UNC 인증 실패와ZIP 표시/원문 이름 비교 실패, unused import lint 실패 및 수정은
`verification-history.json`에 보존했다. 제품 변경이 없어 전체health/build·현장 시험을 반복하지 않았다.

이번 단계는 개발PC 보존 자료와NAS 후보의 읽기 작업이며 서버 접속·설치·설정 변경은 없다.
R4 전체 분류·원인/처리 확정과R1/R2·R3물리시험·R5drop15·R6정식QA는 미완료다.
목표active/이번 턴PROGRESS이며 실행 중인 진단과 답변 대기는 없다.

## 2026-10-17 — 온도 정리본915343행 연결과 손상 전달 재현

개발PC `temp_info_git`에서 날짜별 LandData CSV를 생성하는 소스를 확인했다.
HEAD는 `473c6c6194fc0b21a81cfe65f5c49d00f03a485b`, 변환 파일 SHA256은
`7ded71609fc292ed3da45bc9f0640734ade49ad8b06b81ae326184ea98339680`이며
HEAD와 줄바꿈 정규화 후 일치한다. 과거 배포/실행 버전의 증거는 아니다.
기존 PLC 후보 소스 조사와 별개인 온도 정리 소스다.

현재 보존 csv-parser3.1.0과 실제 소스402–457행을 격리해 원시 결합 손상15행을 재현했다.
초과 열이 허용되고 parseFloat가 숫자 접두부를 받아들여2행은 온도524.62025/5082025,
고속값10/11, 단위SPOT로 남았다. 다른13행은 숫자 칸의SPOT가 NaN이 되어 제외됐다.
정상 인접30행은 모두 유지됐고 관측 정리본의2행과 셀 값이 정확히 일치했다.
원본 앱·DB·전체 내보내기는 실행하지 않았다.

해당 원시 파일714,327행의 부분 변환을 전수 재현한714,314행이 정리본의
201,030–915,343행과 값·순서가 일치했다. 별도 Python CSV/십진수 접두부 비교도
전714,314행과 canonical SHA를 대조했다. 이어 정리본 전체915,343행을 원시3파일의
2025-06-17 기록과 연결했다:141,550 + 59,479 + 714,314행이다.
원시3파일의 총1,186,199행을 읽었고, 해당 날짜915,356행 중13행 제외 구성과 일치한다.
이 한 정리본에서 연결하지 못한 행은0개다. 다른 날짜·파일에 대한 완료 증거는 아니다.

첫 prefix 후보를 잘못된 순서로 비교한exit1은 보존했다. 실제 시작 행을 확인한 뒤
세 입력을 순서대로 대조한 검산은exit0이다. 입력·정리본 전후 SHA·동일성은 유지됐으며
전체 정리본 canonical SHA는 `2495f10387c9f2fe204af7405cbe75e88daf25f5b842a5138cc37a3eefc347e0`다.
값·순서의 대응과 변환 동작은 확인했으나 당시 정확한 프로그램 실행 및 원시 파일의
최초 결합 손상 원인은 미확정이다. 현존 로컬 로그8개의 날짜 바이트 검색에도 해당 날짜
기록이 없었으며, 역사 전체 로그 부재를 의미하지 않는다.

개발PC LandData 폴더의 같은 이름 원시 파일은 기존 NAS 손상본과 동일 바이트였다.
추가 정상 백업으로 보지 않았고 원본·정리본을 수정/삭제하거나 값을 추정 복원하지 않았다.
소스가 있는 다른 저장소와 운영 제품에도 변경이 없다. 이 정리본을 정상 복원 사본으로
사용하지 않도록 기록했고,2개 이상값·13개 제외 행을 R4 처리 대상으로 유지한다.

근거: `C:/Users/user/Desktop/SmartFactory/R4TRANS_20261017_95a1fb8d/review.md`.
확인 예:45사례 재현 → full-sequence 결과/독립 검산 → entire-derivative의 세 원본·범위.
closeout SHA256은 `3718e1313fc20d7e1b694857c7097136547d24fc70c39ed8bae6542780a3d664`다.
최종 준비·Node 문법/재현·독립 검산·전체 정리본 대조·Ruff는exit0이다.
초기 로그 인코딩/CRLF/헤더 가정 오류와 수정은verification-history에 보존했다.
제품 변경이 없어 전체health/build 및 현장 시험은 반복하지 않았다.
R4 전체 스키마별 검증·처리 결정과 나머지 R1/R2/R3/R5/R6는 미완료다.
목표active/이번 턴PROGRESS/출시HOLD, 실행 중인 진단·답변 대기 없음이다.

## 2026-10-17 — 온도1,471파일 장비명·단위 전수 대조

보존 온도 사본1,471개(27,534,639,606바이트), 총576,684,549행의 장비명·단위 문자열 검사를 마쳤다.
6열576,684,382행 중 단위C는576,684,380행, 단위SPOT는2행이다.
장비명은 Spot272,557,244행 / SPOT304,127,138행이며 대소문자를 병합하지 않았다.
표기와 물리 장비의 동일성·교정·온도 정확도가 입증된 것은 아니다.

단위SPOT 두 행은 `LandData_2025-06-17.csv`의 데이터행771172/902130이다.
값은 각각524.62025/고속10,5082025/고속11이며 앞 단계의 손상 전달 재현과 일치한다.
이상 파일915,343행을 별도 검산에서 다시 읽어 다른 이상 단위가 없는지 확인했다.
나머지1,470개는 최초 도우미의 파일별 잠금·전후 해시/동일성 검사를 재사용했다.

기존 구조 손상33행은 단위 집계에서 제외해 별도 유지했다. 다른10열 XLS134행은
6열 단위로 해석하지 않았다. 제목 없는2파일1,061,679행은 열 위치 관찰에 한정한다.
이전 문법 검사나 이번 단위 집계로 전체 의미 검증·정상 복구본 판정을 대신하지 않는다.

최초 도우미가 제목만 있는0행 파일에서 KeyError로 exit1이 됐다. 완성된1,470개 원장은
바꾸지 않고 SHA를 고정했다. 제목 전용 회귀시험에서 같은 실패를 재현한 뒤 수정본으로
누락1파일만 확인했다. 완성 원장은 기존 바이트+새1개 결과를 그대로 연결했다.
최종7사례, Ruff F/E9, 재개 및 전체 원장 대조는 실제 exit0이다. 최초 실패 기록도 보존했다.

사용자가 NAS 외 추가 백업은 없다고 확인한 사실을 유지한다. 이 답변과 이번 검사는
다른 이름·압축 속에 정상 사본이 전혀 없다는 증명이 아니다. 손상 원본·정리본을 수정하거나
추정 복원하지 않았다. 새 전체 백업0건, 제품 변경0건, 서버 접속/설치/설정 변경0건이다.
제품 변경이 없어 전체health/build 및 같은 현장15/120분 시험은 반복하지 않았다.

확인 예: `unit-summary.json` 집계 → `unit-records-complete.jsonl` 파일별 단위 →
`unit-review.json`의 두 원문 행 → `verification-history.json` 실패·수정 이력을 확인한다.
요약 SHA256: `4b3006f72beed897188e9f6e774e4e79805805aacbec1c9e696d7c288b401825`.
완성 원장 SHA256: `49cb1c85a3b936608b306b6ab11d1ae8f49eeae0d5eb452bc7a204ad7fc8a901`.
검산 SHA256: `bcaa81f21f2e326baf709cd9e0f35f69b30b6963614cbc81ad733755076ed2d7`.
근거 폴더: `C:/Users/user/Desktop/SmartFactory/R4UNITS_20261017_31b87de2`.

R4 전체 분류·원인·처리 결정과 R1/R2, R3물리시험, R5drop15, R6최종QA는 미완료다.
목표active/이번 단계PROGRESS/출시HOLD를 유지한다. 실행 중인 진단·답변 대기는 없다.
다음에는 별도로 찾은 PLC 정리 소스의 자정 전환 조건을 기존 원문 관찰 쌍과 대조한다.
소스가 존재한다는 사실만으로 과거 실제 실행이나 날짜 이상 원인을 확정하지 않는다.

closeout SHA256: `7e59842595a9ae5583c5118cf5ea880739a9b1860f5377a016201a76d6918ab4`.

## 2026-10-17 후속: 기존 221ms 요청의 인터럽트·경쟁 실행 분리

CTRACE의 동일 요청에서 확인한64.4168/127.5472ms Ready 구간을 기존 원본으로 추가 분석했다.
DPC/ISR97,080건의 시작·종료 시각, CPU와 routine이 원시 추적과 별도 tracerpt 해독에 일치했다.
추적 header의 기준 시각을 사용했으며 tracerpt의 FILETIME을 QPC로 오인한 초기 실패는 보존했다.

두 CPU 합산에서 기록된 인터럽트 합집합은 각각2.4731/2.9207ms다. 이를 제외한 점유는
126.3605/252.1737ms이며, 그중 전환 양끝의 우선순위가 수집기8보다 높은 구간은
122.4561/245.1747ms다. Explorer의 점유는74.5604/105.3001ms이고 앱·backend·DWM 등도
함께 실행됐다. 두 CPU의 합계이므로 요청의 벽시계 시간과 그대로 비교·합산하지 않는다.

이번 결과는 기록된 인터럽트 처리만으로 긴 대기 전체를 설명할 수 없고 다른 스레드와의
경쟁을 더 조사할 근거가 있음을 보여 준다. 우선순위의 경계값은 연속 상태나 affinity 증명이
아니며, 특정 앱을 근본 원인으로 확정하거나 우선순위를 올리는 조치는 하지 않았다.
스케줄링 해석은 [Microsoft 정의](https://learn.microsoft.com/en-us/windows/win32/procthread/scheduling-priorities)를 따른다.

최종 분석48.250초/exit0, 소유 프로세스 잔류0, interval·clock fixture109개와 Ruff F 통과다.
서버 재측정·제품 수정·설치·전체 백업은 없다. 실제120분의219.9407/302.9669ms 실패를
이번 다른 요청의 분석으로 해결했다고 판단하지 않는다. 전체 출시는 HOLD다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R4R2_20261017_9b37d6c1/review.md).
앞선 절은 이전 실행 이력이며, 데이터 전체 범위는
[최신 R4 정산](production-release-risk-validation-data-coverage-20261017.report.md)을 따른다.

## 2026-10-17 후속: 탐색기의 앱 캐시 갱신 스택 확인

같은221.0337ms 요청(한국 시간10월17일06:19:02)의 CPU표본442개를 추가 분석했다.
일반 프로세스428표본의 전체 스택이 독립 원문과 일치했다. 비프로세스14표본 중12개는
kernel prefix만 검증됐으므로 전체 프로세스 스택으로 취급하지 않는다. Ready구간의
4표본/CSwitch 불일치는 보존했으며 탐색기와 주요 앱의 표본 연결에는 해당 차이가 없다.

공개 symbol8개를 PDB GUID/DBI age로 독립 검산하고398스택의10,600주소를 유지한 채
5,604프레임의 함수명을 확인했다. 두 번째 긴 Ready구간의 탐색기106표본은 모두 같은
thread15572에서 `CAppResolverCacheBuilder::ScanFoldersAndCreateNewCache`를 포함한다.
99개에는 `MsiQueryFeatureStateW`가 있다. 이는 앱·바로가기 캐시 갱신 및 설치 기능의 상태
조회 경로라는 단서다. 캐시 갱신 계기·설치 실행·단일 지연 원인·변경 효과는 아직 미확정이다.

스택·raw분류·PDB/주소 검산의 최종 실행은exit0이며, 분석 도우미 build 경고0/오류0,
최종fixture16+14와 Ruff F 통과다. 서버 변경·새 백업·재측정은 없었다. 다음은 원 trace의
ImageID/RSDS와 같은 시간의 이벤트를 연결해 캐시 갱신 계기를 확인하는 것이다.
원래120분의두FAIL 및 R1/R3/R4/R5/R6 잔여조건은 유지한다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R2STACK_20261017_d31e8a64/review.md).

## 2026-10-17 후속: Shell 검사와 지연 요청의 시간 대조

원 ImageID/RSDS/ImageLoad666개 연결에서 Windows 모듈8개의 PDB 식별값을 확인했다.
서버의 보존 Shell-Core 로그에서는 같은 시간대 AppResolver 검사84쌍을 확인했다.
81쌍은 기존 스택의 Explorer PID9804/thread15572,3쌍은 같은 프로세스의 thread704다.

121개 요청 중221.0337ms인 한 건만 이 검사와 겹쳤다. 겹치지 않은120건의 최대는
107.2514ms다. 문제 구간의 검사는242.1505ms, 요청과 겹침은QPC 기준195.4738ms다.
요청UTC 기준 독립 계산에서도 동일한 한 건만 겹치며 겹침은194.3694ms다.
clock 차이를 오차 상한으로 보장하지 않는다. 캐시 갱신 계기·단일 원인·개입 효과는 미확정이다.

독립 대조3,543/fixture15/Ruff F/PS parser가 통과했다(exit0). 서버는 로그만 읽었고
18:30KST에 Smart Factory 전면 Running을 확인했다. 작업 입력·운영 설정은 변경하지 않았다.
다음은 진단 출력 파일 생성과 반복 스캔의 관계를 작은 격리 실험으로 확인한다.
원래120분 실패와 R1~R6 잔여조건, 미서명 운영 방침, 출시 HOLD를 유지한다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R2TRIGGER_20261017_8bbd59e6/review.md).

## 2026-10-17 후속: 파일 생성 조건에서 검사 재현

개발 PC의 두 차례 비교에서 새 파일 생성4구간 모두 AppResolver 검사가1회씩 발생했고,
기존 파일 추가4구간과 무쓰기4구간에는 관측되지 않았다. 순서를 바꾼 시험에서도 같았다.
동일한4KiB 데이터를250ms마다 쓰며 두 쓰기 조건의 총량은각1,966,080바이트다.
검사 지속시간8.7~10.4ms, Explorer CPU 합계는 생성11.906초/추가2.219초/무쓰기0.078초다.

파일/원 XML 검증은각3,445검사, 별도 Windows reader의8이벤트 대조도 통과(exit0)했다.
본 시험 두 번 모두 정상 종료·잔류 프로세스0이며 Ruff/PS 구문도 통과했다.
서버 직접 원인이나 성능 통과를 뜻하지 않는다. 다음은 서버에서 같은 조건을 제한적으로
비교하는 단계다. 이번에 서버·제품·원본·백업을 변경하지 않았고 출시 HOLD를 유지한다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R2WRITE_20261017_c73e52b8/review.md).

## 2026-10-17 후속: 서버 비교에서는 반복 검사 미재현

서버에서 두 가지 순서로 파일 생성·추가 쓰기·무쓰기를 각각4구간 비교했다. 생성과 추가는
각480회/1,966,080바이트를 기록했지만, 구간 중 AppResolver 검사는 모두0회였다.
준비 대기에만 실행당1회(약183ms) 관찰됐다. 개발 PC 결과와 달라 파일 생성을 서버 지연의
원인으로 확정하지 않는다. Explorer CPU는 생성13.734초/추가5.125초/무쓰기0.031초였으며
앱 응답 시간을 뜻하지 않는다.

서버 두 실행은exit0·잔류0, 전후 승인 설정/프로세스 세대 일치다. 원본 결과의 공유·개발
사본1,028개 크기/SHA 대조와 분석6,922검사, 독립 이벤트4개 대조가 통과했다.
19:25KST Smart Factory 전면 Running을 확인했다. 제품·장비 설정·원본·전체 백업 변경은 없다.
다음은 기존 진단의 파일 종류·경로·준비/실행 활동 차이를 보존 증거로 좁힌다.
원래120분 실패와 R1~R6 잔여조건은 남아 전체 출시HOLD를 유지한다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R2SERVER_20261017_f391c2a8/review.md).

## 2026-10-17 후속: fsync 추가 조건도 반복 검사 미재현

실제 진단과 앞선 시험의 저장 차이(fsync)를 반영해 두 서버 순서를 비교했다. 일반 저장과
fsync 저장은 각각480회였고 측정4구간씩에서 검색 검사는 모두0회였다. 준비 대기에만
실행당1회씩 관찰됐다. fsync 쓰기 중앙값2.028ms/최대42.741ms는 HTTP 응답시간이 아니다.

두 실행 exit0·잔류0, 전후 승인 설정/세대 일치, 회수1,980개 파일 크기/SHA·분석8,836조건·
독립4이벤트 대조가 통과했다. 과거2,005개 쓰기와84개 검색의 시각 대조도 마쳤으나 원인은
미확정이다. fsync나 원본 보존 장치를 제거하지 않는다. 19:53KST Smart Factory 전면 Running을
확인했고 작업번호를 변경하거나 새 백업을 만들지 않았다. 원래120분 실패와 전체 출시HOLD를
유지하며 보존 trace의 준비/백그라운드 활동을 더 확인한다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R2SYNC_20261017_6205ca92/review.md).

## 2026-10-17 후속: 기존 추적에서 호출자를 확정할 수 없는 이유

검색 스레드와 관련된 실행 기록80,521건이 두 해독 방식에서 일치했다. 다만 준비 이벤트
885건 모두 호출자 PID/TID가0xFFFFFFFF이고, 원 추적에는 준비시킨 쪽 스택이 없다.
실행 전환 기록의 두 CPU 공통 보존 구간은 약46.19초여서 전체 검색84회 중14회만 대조
범위에 있다. FileIO·Registry도 수집되지 않아 원인 프로세스를 확정할 수 없다.

첫 로컬 추출의 필터 오류는 별도 R2에서 수정했다. R2 exit0/잔류0, 행 중심 분석83,803조건과
별도 검토25조건을 통과했다. 시간상 직전 이벤트나 프로세스 시작을 원인으로 간주하지 않았다.
서버·제품·원본·작업번호 변경과 새 백업은 없었다. 이번에는 새로운 서버 UI 관찰도 하지 않았다.
다음은 누락된 ReadyThread 스택을 짧게 수집하는 방법을 개발 PC에서 검증하는 단계다.
원래120분 실패·전체 출시HOLD와 나머지R1~R6 검증 조건은 그대로 남아 있다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R2WAKE_20261017_8f99b4ab/review.md).

## 2026-10-17 후속: 호출자 스택 시험 준비

누락된 ReadyThread 스택을 수집하는 새 프로파일과8회 신호 재현 도구를 준비했다.
일반 권한의 정상/신호 누락 시험, 제어기14조건/프로세스11묶음, WPR 프로파일 해석과
PS5.1 구문·Ruff 검사까지 통과했다. 실제 추적 성공이나 성능 QA 통과는 아니다.

자동 관리자 실행은 상위 Job 문제로 추적 시작 전에 중단됐다. 독립 감시 조건을 유지하기
위해 Windows 탐색기에서 한 번 실행하는 검증된 shortcut을 준비하고 사용자에게 안내했다.
명령 복사 단계는 필요 없다. 실행 후 기록을 회수해 실제 호출자 연결과 보존 범위를 확인한다.
서버·앱·장비 설정·백업은 변경하지 않았고 전체 출시HOLD를 유지한다.
[준비 결과와 실행 방법](C:/Users/user/Desktop/SmartFactory/R2READY_20261017_9562c578/review.md).

## 2026-10-17 후속: 추적 해독기 대조 완료, 실제 호출자 시험 대기

새 해독기로 스택 미수집 기록428,946행을 읽어 스택0을 확인했고, 별도 회귀 기록153,793행은
이전 독립 대조 결과와 바이트까지 같았다. 두 실행과 원 payload 검산·Ruff F는 exit0,
소유 프로세스 잔류0이다. 잠금 패키지15개를 로컬 원본에서 복원한 빌드는 경고/오류0이었다.

실제 호출자 스택을 수집하는 shortcut은 아직 시작 기록이 없다. 따라서 실제 스택 연결과
성능 원인은 미검증이다. 최신 사용자 '생산 중 아님' 보고를 유지했고 서버·제품·작업번호를
변경하거나 새 백업을 만들지 않았다. 원래120분 실패와 전체 출시HOLD는 유지한다.
[검증 결과와 다음 단계](C:/Users/user/Desktop/SmartFactory/R2READY_DECODE_20261017_d0523b5e/review.md).

## 2026-10-17 후속: 실행 대기 해소 및 실제 스택 연결 검증

사용자 권한 승인 후 기존 Windows 탐색기를 통한 독립 실행을 확인했다. 검증된 동일 묶음의
실제 추적1회가 정상 종료됐으며 launcher/제어기/감시자 exit0과 WPR 세션 정리를 확인했다.
새 서비스·예약 작업·계정은 만들지 않았다.

두 해독 방식에서 선택195,197기록이 원 바이트까지 일치했고, 통제된8회 신호 모두 발신
스레드의 커널/사용자 스택과 연결됐다. 두 신호의 사용자 조각은 다른 CPU에서 출력되어,
CPU 동일 여부 대신 원 이벤트 시각·프로세스·스레드 번호로 연결해야 함을 확인했다.
초기 XML 명령의 시간한도 오류를 수정한 R2해독과 실제 대조·Ruff F는exit0이다.

독립 실행 대기는 해소됐지만 추적 비용과 서버 지연 원인은 미검증이다. 제품·서버·작업번호·
백업을 변경하지 않았으며 원래120분 실패와 전체 출시HOLD를 유지한다.
[실제 실행·검증 결과](C:/Users/user/Desktop/SmartFactory/R2EXPLORER_20261017_c73ed3ea/review.md).

## 2026-10-17 후속: 스택 OFF/ON 비교 완료

개발 PC에서 같은8신호를 OFF→ON→ON→OFF4회 수집했다. 모든 실행·추적 저장·정리는exit0이고
남은 프로세스는 없다. OFF는 스택0,ON의16신호는 모두 발신자 스택과 연결됐다.
ETL평균은 OFF21.0MiB/ON26.125MiB,저장시간은19.001/19.165초였다. 첫 신호를 따로 표시한
나머지14신호의 중앙값은21.4/14.9µs,최대137.7/166.7µs였다.

배경 CPU가 달라 정확한 수집 CPU 비용을 분리하지 못했고, 이 짧은 비교를 서버 성능 통과로
판정하지 않는다. 초기 launcher 인코딩 오류를 보존하고 수정한 R2로 실행했다. 기존 독립 검증을
마친 해독기로 원바이트·신호를 확인했으며 이번4개 trace의 tracerpt 전체 대조는 반복하지 않았다.
서버·제품·작업번호·백업 변경 없이 전체 출시HOLD를 유지한다. 다음은 승인된 제한 서버 추적
준비다. [비교 결과와 검증](C:/Users/user/Desktop/SmartFactory/R2COST_20261017_dbf5002b/review.md).


## 2026-10-17 후속: 스택을 포함한 현장15분 진단 완료

실제 서버에서900초 진단1회를 완료했다. health450건 모두 응답했고 최대
124.2006ms로200ms초과는 없었다. 동시 data150건/image
3600건도 누락 없이 저장됐다. 실행·추적 저장·정리 exit0과 소유 잔류0을 확인했다.

회수8,041파일의 해시를 서버 기록과 검산하고, 선택725,991개 추적 기록을
두 해독 방식으로 원 바이트까지 대조했다. ReadyThread 호출자 스택을 실제 서버에서 수집했으나
이번 구간에는 지연이 없어 기존 실패의 원인을 확정할 수 없다. CPU별 공통 관찰 경계는
18.766초이며 전체15분 이벤트가 모두 보존된 것은 아니다.

새 도우미의 단위76건/native20묶음/frozen17조건과 빌드·실행·원문 대조를 확인했다.
제품 설치·재시작·설정/작업번호 변경·전체 백업은 하지 않았다. Smart Factory를 작업자가
볼 수 있는 전면 상태로 확인했다. 원120분FAIL과 전체 출시HOLD는 계속 유지한다.
[상세 관찰값·검증·남은 작업](C:/Users/user/Desktop/SmartFactory/R2FIELD_20261017_91c0af6d/review.md).

## 2026-10-17 후속: 보존된 요청과 호출자 스택 연결

회수본의 요청8건·스레드 구간24개와 ReadyThread569건의 호출자 스택을 연결했다.
모든 호출자는 당시 백엔드 프로세스이며 528건은 같은 TID17460이었다. 이는 실제 호출 연결이며
해당 스레드가 병목이라는 뜻은 아니다. 최대124.20ms 응답은 보존 범위 밖이라 원인을 설명할 수 없다.

원 파일 해시와 스케줄 연속성·세대 조건을 검산했고 3가지 모호한 연결 조건을 거부했다.
주소127개의 모듈15개 범위 후보를 확인했지만 함수 기호·Python 호출 경로는 미검증이다.
분석·모듈 후보·메타데이터 분류는 exit0이다. 제품과 서버를 변경하지 않았으며 전체 출시HOLD를 유지한다.
[연결 방법·한계·다음 검토](C:/Users/user/Desktop/SmartFactory/R2JOIN_20261017_061ce9db/review.md).

## 2026-10-17 후속: 모듈 기록과 설치 파일 식별

같은 추적 파일의 모듈 관련70,722이벤트가 독립 해독 결과와 일치했다. 원 바이트56,891건과
전체 필드 재조립13,831건을 구분한다. 15모듈의 디버그 식별자를 확보했고, Python 관련6파일은
설치 당시 파일 해시와 추적/PE의 식별 정보까지 일치했다. 주소127개 중63개가 이6파일 범위다.

별도 PE 파서 대조와 잘못된 식별자6조건·입력 해시/출력 경로2조건의 거부를 확인했다.
최종 빌드·분석·검증 exit0이며 초기 분석 실패2건도 보존했다. 함수 이름과 지연 원인은 아직
확정되지 않았다. 서버·제품·작업정보·백업 변경 없이 원120분FAIL 및 전체 출시HOLD를 유지한다.
[확인한 범위와 다음 단계](C:/Users/user/Desktop/SmartFactory/R2IMAGE_20261017_7c460a12/review.md).

## 2026-10-17 후속: Python 호출 함수 식별

설치본과 식별자가 일치하는 공식 PDB6개로 주소63개를 함수 이름에 연결했다. 호출 기록569건의
원 프레임14,863개를 보존했고, 주로 관찰된 스레드의528건은 파일 상태 조회518건과 폴더 열거
10건으로 나뉘었다. GIL 해제527건도 함께 관찰됐다. 스택의 함수 포함 횟수이며 지연 원인 확정은 아니다.

별도 PDB 식별 대조·잘못된 연결4조건 거부·원 프레임 연속성 검사와 최종 Ruff F/diff 검사는
exit0이다. 정상8요청 분석으로 기존120분 실패를 덮어쓰지 않았다. 다음은 같은 기호를 활용할 수
있는 이전 지연 샘플의 모듈 대조와 호출 해석이다. 서버·제품 변경이나 새 백업은 없으며 전체 출시HOLD를 유지한다.
[근거와 남은 조건](C:/Users/user/Desktop/SmartFactory/R2SYMBOL_20261017_91ed0c67/review.md).

## 2026-10-17 후속: 실제 지연 기록의 호출 함수 확인

이전221.0337ms 응답 구간의43샘플에서205개 주소 조합을 함수 범위에 연결했고, 범위 밖1개는
미해석으로 유지했다. 프로세스/모듈7조합의 원 식별 기록과1,261프레임 순서를 검산했다.
통신·JSON·CSV 및 GC1샘플을 관찰했지만 특정 기능의 지연 기여도와 Python 앱 호출부는 미확정이다.

초기 이벤트 버전 가정 오류를 수정한 뒤 준비·조회·분석·검증 및 최종 Ruff F/diff 검사는 exit0이다.
실패 원본도 보존했다. 다음은 앱 재시작 없이 Python 프레임을 읽는 도구의 로컬 검증이며,
서버 적용은 아직 하지 않았다. 전체 출시HOLD와 기존120분FAIL을 유지한다.
[상세 결과](C:/Users/user/Desktop/SmartFactory/OUTSYM_20261017_27ceba41/review.md).

## 2026-10-18 후속: 외부 Python 프레임 도구의 로컬 검증

py-spy0.4.2의 공식 배포 해시를 확인하고 일반 시험10회와 frozen 시험3회에서 함수·스레드
식별39건을 대조했다. frozen 시험의 Python DLL은 후보 설치본과 같았다. 종료된 대상 조회는
오류로 처리했고 잘못된 샘플4조건도 거부했다.

별도 보호 실행의 정상·시간 제한·출력 상한·제어자 종료4조건에서 진단 프로세스 정리와
대상 앱의 계속 실행을 확인했다. 첫 시험의 닫힌 파이프 재조회 오류를 수정한 R2는 exit0이며
실패 원본도 보존했다. 짧은 시험의 관찰 부담은 서버 성능 판정으로 사용하지 않는다.

서버 실행은 아직 하지 않았다. 다음은 기존 보호 진단 경로와 결합해 현재 앱 역할을 제한 관찰하는
준비다. 과거 지연 원인·전체 출시HOLD는 그대로다.
[범위와 검증 기록](C:/Users/user/Desktop/SmartFactory/PYFRAME_20261017_82eb041c/review.md).

## 2026-10-18 후속: 보호 실행 경로 결합과 전달 묶음 준비

기존 도우미에 고정3회 Python 프레임 모드를 추가했다. 함수와 스레드 생성 시각을 함께 확인하고,
현재 스레드에 연결하지 못한 결과는 부분 관찰로 표시한다. 기존 설치·설정·실행 세대 확인을 유지한다.

최종 단위/회귀8건, 실제 수집4조건, frozen 수집2조건과 CLI2조건, PowerShell 실행 한도 검사를
통과했다. 시험 대상은 유지됐고 진단 자식은 정리됐다. 초기 JSON/시험 준비 오류와 스레드 종료
시점 단정 오류를 수정했으며 실패 기록을 보존했다.

11파일 전달 묶음을 로컬에서 검산했다. 서버 전달·실행은 다음 단계이며, 제품 설치본이나 서버
설정·작업번호는 변경하지 않았다. 전체 출시HOLD를 유지한다.
[검증 결과와 현장 적용 준비](C:/Users/user/Desktop/SmartFactory/PYBIND_20261018_5a0d719c/review.md).

## 2026-10-18 후속: 서버 호출 역할 관찰 완료

서버에 진단 묶음을 전달·검산하고 실제 보호 실행으로 Python 프레임을3회 읽었다.27개 스레드의
81행을 생성 시각에 연결하고 앱 소스 함수/행63건을 대조했다. 이미지 저장·PLC·CSV·통신·
이벤트 처리 역할을 구분했으며, 현재 관찰을 과거 지연 원인 확정으로 확대하지 않았다.

전달 검산·실행·30파일 회수·최종 분석은 exit0이다. 진단 Job 잔류0과 앱의 계속 실행을 확인했다.
준비/오프라인 분석 중 발견한 구문·시각·경로/자료형 가정 오류와 수정 내역을 보존했고 서버 진단은
한 번만 실행했다. 앱 재시작·설정/작업번호 변경·새 전체 백업은 없었다.

Smart Factory를 전면에 복귀시켰고 화면은Running/60180·19다. 화면 metadata를 실제 생산
확인으로 대신하지 않았다. 과거 ETW와 연결 가능한 근거를 다음으로 검토하며 기존120분 FAIL과
전체 출시HOLD를 유지한다. [상세 결과와 원본 증거](C:/Users/user/Desktop/SmartFactory/PYFIELD_20261018_46f2c831/review.md).

## 2026-10-18 후속: 과거 기록과 현재 스레드 식별 대조

정상/지연 추적의 스레드5,845행을 두 decoder에서 대조하고 과거 HTTP 진단571건을 원 응답·
생성 시각·QPC 기준으로 재검산했다. 이벤트 루프와 요청 worker7개는 현재 관찰과 생성 시각까지
일치한다. 이미지 저장17460은 과거 생성 시각이 없어 호환되는 관찰로 남겼다. 현재 역할만으로
과거528건의 파일 조회나221.0337ms 지연의 원인을 확정하지 않았다.

이번 단계는 기존 파일을 읽는 오프라인 분석이다. 서버 작업·제품 변경·새 백업을 하지 않았다.
최종 분석과 정적 검사는 exit0이며 원120분 FAIL과 전체 출시HOLD를 유지한다.
[직접 일치7개와 남은 연결 한계](C:/Users/user/Desktop/SmartFactory/THREADLINK_20261018_674c2ba9/review.md).

## 2026-10-18 후속: Python 읽기 시각의 앞뒤 범위 기록

진단 도우미에 읽기 전후 Windows QPC를 추가했다. 시계 검산 실패와 원 프레임 관찰을 구분해
현재 함수를 과거 지연 순간에 잘못 연결하지 않도록 했다. 알려진 함수2개와 단위/회귀12건,
실제 수집4조건이 통과했다. 최초 시험 환경 변수 누락은 보완하고 실패 기록을 보존했다.

관찰 범위가230.3ms까지 넓어지는 사례를 확인했으므로 이 방식만으로221ms 지연 내부의 정확한
순간을 구분했다고 주장하지 않는다. 다음은 지속 읽기와 실제 읽기 시각 보존 방법의 로컬 검증이다.
제품·서버·새 백업은 변경하지 않았고 전체 출시HOLD를 유지한다.
[검증 결과와 시간 해상도 한계](C:/Users/user/Desktop/SmartFactory/PYQPC_20261018_c38b691d/review.md).

## 2026-10-18 후속: 지속 읽기의 로컬 실행 확인

Python 프레임을 지속해서 읽는 시제품을 빌드하고, 알려진 함수100회와 frozen 대상400회를
실제로 기록했다. 최대 읽기 범위는 각각0.7655ms/1.1088ms였다. 취소·잘못된 프로세스 세대·
제어 프로세스 종료·8초 제한·대상 종료를 확인했고 시험 종료 후 소유 Job 잔류는0이다.

같은 frozen 대상의 OFF/ON/ON/OFF 비교2회에서 처리량 중앙값 차이는-0.0960%였다.
짧은 로컬 합성 작업의 관찰값이며 현장 성능 통과나 과거 지연 원인 판정으로 확대하지 않는다.
다음은 기존 보호 실행·설정/설치본 결합과 HTTP/ETW 통합이다. 서버·제품에는 적용하지 않았고
전체HOLD를 유지한다. [원 출력과 검증 범위](C:/Users/user/Desktop/SmartFactory/PYPERSIST_20261018_e664ac62/review.md).

## 2026-10-18 후속: 지속 읽기와 HTTP 요청의 연결

기존 설치본·설정·실행 세대 검사와 소유 Job 안에서 새 reader를 실행하는 `python-health`
경로를 추가했다. 로컬에서 최종77개 검사, frozen 정상/세대 불일치2조건, 고정 PowerShell
예산 검사가 통과했다. 소스와 frozen 각각300회 읽기·지연 요청3건에서 같은 스레드의 알려진
함수를 해당 QPC 구간에 연결했다. 취소·잘못된 도구·설정 변경은 실패로 보존하고 정리했다.

첫 시험의 Cargo 하드링크 출력은 기존 검증에서 거부됐다. 검증을 유지한 채 같은 바이트의
일반 파일 사본을 준비했고 실패 기록도 보존했다. 실제 ETW 결합과 관리자 외부 launcher,
현장 비용 검증은 남아 있다. 운영 서버·제품·새 백업을 변경하지 않았으며 기존120분 FAIL과
출시HOLD를 유지한다. [상세 검증 기록](C:/Users/user/Desktop/SmartFactory/PYJOIN_20261018_a2562c7a/review.md).

## 2026-10-18 후속: 실제 Windows 추적과 Python 기록의 통합

오프라인 Sandbox에 실제1.0.30 설치본을 설치해 보호 관리자 실행을 검증했다.
최종79개 Python 검사와 PowerShell 잘못된 입력12개 거부가 통과했다. 읽기 실패를
원문과 함께 별도로 남기도록 보완한 뒤300회 중297회 해석,3회 누락과 HTTP3건,
Windows 추적을 같은 실행에서 저장했다. 원 스케줄링/스레드65,662개 독립 대조가
일치했고 추적 손실은0이다. 앱·수집기·WPR 정리와 Sandbox 종료도 확인했다.

세 번째 HTTP 요청은 읽기 묶음 사이에 있어 Python 스택과 겹치지 않았다. 이 공백과
현장 부담·원인 분석은 후속 작업이다. 서버·제품·새 전체 백업을 변경하지 않았고
기존120분FAIL 및 출시HOLD를 유지한다. [검증 범위와 실패 이력](C:/Users/user/Desktop/SmartFactory/PYTRACE_20261018_16c222a2/review.md).

## 2026-10-18 후속: 읽기 재시작 공백 제거

진단 reader를 한 프로세스의350회 읽기로 바꾸고 실제 읽기 범위가6초 관찰 전체를
포함하는지 검사했다. 관련 Python82개, PowerShell 거부12개와 정상·중단·종료·시간
제한 검사를 통과했다. 첫 엄격 단독 시험의1회 읽기 실패는 보존했으며, 단독0오류
조건은 유지하고 추적용 통합 fixture에서 누락을 명시하도록 검증 경로를 맞췄다.

격리 Windows의 실제1.0.30/frozen 진단 실행에서349회 해석·1회 누락을 기록했고,
HTTP3건 모두 같은 읽기 프로세스의 native 세대 확인 범위 안에 있었다. 각 요청에
읽기1개가 겹쳤다. 스케줄링/스레드73,417개 독립 대조가 일치했으며 앱·추적·격리
환경 정리까지 완료했다. 샘플 사이 공백과 전체 호출자 의미·현장 비용/원인은 남는다.
서버·제품·새 전체 백업을 변경하지 않았고 기존120분FAIL/출시HOLD를 유지한다.
[검증 결과와 후속 범위](C:/Users/user/Desktop/SmartFactory/PYWINDOW_20261018_b39217f1/review.md).

## 2026-10-18 후속: 현장 단일 reader와 빈 스택 처리

서버 로컬16파일 해시 확인 후 승인된6초 진단을1회 실행했다. reader350시도 중5회 읽기
실패와1회 빈 스택이 있었고 기존 해석기가 빈 스택을 거부했다. 현장 실행의FAIL/exit1과
최종 설정·payload 검증 미도달을 보존했다. 앱은 같은 실행 세대로Running을 유지했고,
진단 Job·WPR·helper 정리와 Smart Factory 전면 화면을 확인했다. 설치·새 백업은 없다.

빈 스택을 명시적 공백으로 남기고 함수 일치에서 제외하도록 소스를 보완했다. 관련90개
검사 exit0이며 원 기록의 별도 재해석으로344개 분석 가능 읽기와6초 범위 포함을 확인했다.
HTTP3건에는각1개 읽기가 겹쳤고, Windows 스케줄링/스레드166,962개 독립 대조가 일치했다.
비원자적 읽기·최대62.1571ms 샘플 간격·불완전한ETW 수명·진단 부담과 지연 원인 미확정은
남는다. 보완된 frozen 도우미와 현장 완료 검증이 후속이며 과거 실패를PASS로 바꾸지 않는다.
기존120분FAIL/출시HOLD를 유지한다. [상세 기록](C:/Users/user/Desktop/SmartFactory/PYWFIELD_20261018_6c90a272/review.md).

## 2026-10-18 후속: 빈 스택 보완 실행 파일 검증

90개 검사를 통과한 소스에서 새 도우미를 빌드하고 내부 코드 일치 및 과거 빈 스택 사례의
명시적 공백 처리를 확인했다. 실제 오프라인 Windows 실행은 exit0이며 잘못된 해시/세대는
거부했다.350시도 중344회 성공·6회 읽기 실패를 기록했고 스케줄링/스레드69,904개 독립
대조가 일치했다. 앱·추적 정리와 Sandbox 폐기도 확인했다.

서버에서의 새 도우미 완료 검증은 남는다. 제품·서버·전체 백업은 변경하지 않았으며
과거 현장FAIL과120분FAIL/출시HOLD를 유지한다.
[원자료와 검증 범위](C:/Users/user/Desktop/SmartFactory/PYEMPTY_20261018_9a466f97/review.md).

## 2026-10-18 후속: 수정 도우미의 현장 완료 확인

새 도우미를 승인된 SSH로1회 실행해 exit0과 설정·실행 세대·설치파일1,900개의 최종 검증을
확인했다.350시도 중348회 성공·2회 읽기 실패, HTTP3건 각각1개 읽기 겹침을 기록했다.
스케줄링/스레드166,146개 독립 대조가 일치했다.97개 결과 파일을 회수·검산했고 앱은 같은
실행 세대로Running을 유지했다. 진단 프로세스·WPR 정리와 작업자용 전면 화면도 확인했다.

제품·설정·작업 정보 변경과 새 전체 백업은 없었다. 빈 스택은 이번 실행에서 발생하지
않았으며 진단 비용·과거 지연 원인은 여전히 미확정이다. 기존120분FAIL/출시HOLD를 유지한다.
[상세 증거와 미완료 범위](C:/Users/user/Desktop/SmartFactory/PYEFIELD_20261018_4c758d20/review.md).

## 2026-10-18 후속: reader의 배정 CPU 시간과 비교 조건

이미 회수한 원 추적에서 reader가6초 동안 CPU에 배정된 시간은1,696.7962ms였다.
관찰된2개 논리 CPU의 전체 시간 대비14.1400%이며, 별도 누적 적분 계산으로 대조했다.
105,062개 CSwitch와350개 읽기 구간을 검산했고 관련7개 검사·최종 verifier exit0이다.
Thread/End 이후 일부 동일 TID 기록은 소유권을 추정하지 않고 전체 수명 보고에서 제외했다.
초기 분석/검산 실패도 원문으로 보존했다.6초 범위는 모든 관련 스레드의 수명 기록 안에 있다.

이 값은 실제 추가 부하나 과거 지연 원인이 아니다. 기존 기본 health와 Python 진단은
Windows 추적 설정도 달라 직접 OFF/ON으로 비교할 수 없음을 확인했다. 동일 profile·요청·
실제 frozen 앱을 사용하는 비교 절차를 설계5.79에 정리했으며 아직 구현·실행 전이다.
이번에는 서버·제품 변경과 새 백업을 하지 않았고 기존120분FAIL/출시HOLD를 유지한다.
[상세 검산·해석 한계](C:/Users/user/Desktop/SmartFactory/PYCOST_20261018_a52c80df/review.md).

## 2026-10-18 후속: 동일 조건 OFF 비교 계약 구현

Python 관찰 기능만 끄는 고정 baseline 요청을 추가했다. ON과 같은 패키지/reader 해시 잠금,
Ready profile·6초 관찰·30초 추적 제한을 사용한다. 관련96개 검사 범위를 확인했고,
PowerShell 소스/패키지 함수에서 각각21개 잘못된 조건의 거부를 확인했다. 최초 시험용 파일
생성 누락1건은 수정 후 관련16개를 재검했으며 첫FAIL 로그를 보존했다.

새 도우미와 패키지를 만들고 실제 describe 및 내부 코드 일치를 확인했다. 새 baseline의
관리자 WPR 실행과 실제 OFF/ON 비교는 후속이며 빌드 성공을 성능 검증으로 처리하지 않는다.
제품·서버·설정·작업 정보·새 백업은 변경하지 않았고 기존120분FAIL/출시HOLD를 유지한다.
[검사 범위·실행 파일 식별·남은 단계](C:/Users/user/Desktop/SmartFactory/PYPAIR_20261018_0554749e/review.md).

## 2026-10-18 후속: 실제 격리 앱의 OFF/ON 비교

실제1.0.30 앱에서 예비 OFF와 고정8구간을 실행했다. 같은 실행 세대·설정·추적 조건에서
OFF/ON 각12요청의 중앙값은6.04675/6.24645ms였고 모든 요청이200ms 이내였다.
ON reader의 전체 CPU 시간718.75~921.875ms와6초 구간의 배정 시간738.9471~799.5867ms를
구분해 기록했다. 인접 쌍의 지연 차이는 방향이 달랐으므로 개선/악화를 단정하지 않았다.

보호 실행9개·앱/backend 정상 종료0,Job/추적/잔존 프로세스 정리를 확인했고 Sandbox를
종료했다. ETW 스케줄링/스레드513,771개 독립 대조와 손실0을 확인했다. 관찰 끝부분이
전환 기록으로 묶이지 않은 CPU 시간은 추정하지 않았으며 첫 분석 실패와 보완 결과를 보존했다.
읽기 오류13회·빈 스택1회도 누락으로 남겼다. 서버/제품/설정/작업 정보와 새 백업 변경은 없다.
12논리 CPU 모의 장비 결과를2논리 CPU 현장 성능이나120분 통과로 확대하지 않고 출시HOLD를 유지한다.
[실행·검산 결과](C:/Users/user/Desktop/SmartFactory/PYAB_20261018_a7b921c4/review.md).

## 2026-10-18 후속: 실제 서버의 OFF/ON 비교

서버 DESKTOP-CIIT7LK의 같은1.0.30 앱(main17996/backend14012)과 승인 설정을 유지했다.
PYPAIR 패키지의 예비 OFF 이후 OFF→ON→ON→OFF를 두 차례 실행했다. 각 회차6초/HTTP3건/2초 간격,
동일 Ready profile·30초 trace guard·600초 보호 launcher를 사용했다.9개 실제 종료 코드0,
각각 설치파일1,900개·설정·세대 종료 검산,Job0·WPR 정리와 원본/공유/로컬 해시 일치를 확인했다.

| 조건 | 요청 | 중앙값(ms) | 평균(ms) | 범위(ms) | 200ms 초과 |
|---|---:|---:|---:|---:|---:|
|OFF|12|9.48780|13.64132|7.5376~37.6214|0|
|ON|12|9.33745|13.18273|6.9220~36.3290|0|

Reader 전체 프로세스 CPU는1312.500~2031.250ms,6초 안의 확인된 배정 시간은
1203.0172~1755.8583ms로2논리 CPU 용량의10.0251~14.6322%였다.
전체 CPU는 초기 연결·읽기·종료를 포함하고,배정 시간은 interrupt 실행을 포함할 수 있다.
200ms 간격 PowerShell 보조 관찰기의 보호 실행 전후 CPU는1421.875~1718.750ms였다.
보조 관찰기는 양쪽 조건에서 동일하게 동작했으며 이 값 역시6초만의 비용이 아니다.
수집기 전체 CPU와 backend 전후 차이,관찰기 자체 비용을 구분했다. 로컬 Python 관찰기와 직접 비용 비교하지 않는다.

ON1,400시도에서 native 읽기 오류17회·빈 스택0회를 명시적으로 남겼고1383회를 함수 대조에 사용했다.
9개 ETL의2,697,987이벤트 중 스케줄링/스레드1,270,521개가 두 해석기에서 일치했다.
EventsLost/BuffersLost 모두0이며 원 HTTP/native clock·읽기 공백 결합도 재검산했다.
tracerpt의 일부 이벤트 스키마 불일치 경고는 보존했다. 해석 확정 범위는 대조한 스케줄링/스레드 필드이며,
전체 이벤트·호출 스택의 모든 필드 해석은 미확정이다.
별도 누적 적분과 원 요청 집계의9개 대조가 exit0이었다. 전환 기록으로 묶이지 않은 경계는 추정하지 않는다.

작은 표본의 관찰 차이를 지연 상한·통계적 유의성이나 과거120분FAIL 원인으로 해석하지 않는다.
기존221.0337ms 실패에는 이번 reader가 없었으므로 reader가 그 과거 실패를 만들었다고 주장하지 않는다.
Backend/collector의 과거 전체 스레드 수명·개별 affinity는 독립 확정 범위가 아니다.
제품/설정/작업 정보/전체 백업 변경은 없다. 현재 화면 값은 관찰 정보이며 새 사용자 생산 확인이 아니다.
기존120분FAIL·R1 timeout·R3 물리 NOT_TESTED/Low Signal OFF·R4 전체 데이터·R5 drop·R6 최종 QA/승격은 계속 미완료다.
[원자료·해시·실행 결과](C:/Users/user/Desktop/SmartFactory/PYAFIELD_20261018_03baf471/review.md).


### 2026-10-18 기존 현장 요청의 함수·실행 전환 대조

PYJOIN에서 예비를 제외한8구간·24요청의 원 HTTP·native clock·스레드 세대·선택 ETW를
이전 manifest와 대조했다. 36.3290ms ON은 연결·준비29.2955ms/route4.8077ms,
수집기 배정1.1398~1.1418ms/Ready 전환 후 재배정 구간29.6839ms다.
37.6214ms OFF도 Ready 전환 후 구간36.3231ms/배정1.2972~1.2994ms였다.
연결 값에는 시계·객체 준비가 포함되며 CPU 배정·전환 후 구간은 인과 확정과 구분한다.

ON12요청 중7개에 Python 읽기9구간이 겹쳤다. route 완전 포함0/부분 겹침 가능1,
읽기 실패 겹침1요청이며 나머지 공백을 추정하지 않았다. 가장 느린 ON의 `_poll`/`_worker`
세 읽기는 route 앞 연결·준비 구간에 겹쳤다. 표본 수를 지속 시간이나 GIL 원인으로 해석하지 않는다.

두 CPU 경쟁 배정 합계는 ON에서 System13.9693/Explorer12.0001/reader8.4960ms,
OFF에서 smart-factory PID15700/17632의23.4696/13.9761ms와 backend18.3665ms였다.
원 thread→PID 대조와 Windows XML process 이름을 구분했다. 대부분 DCEnd 한 건만 있어
이름·세대의 완전 결합과 개입 효과는 미확정이다. 원문 XML의 해시는 이전 봉인 값과 일치한다.

분석/독립24요청 적분/Ready 정산24/두 XML 추출 exit0,경계9조건 및 최종 Ruff F/diff를 확인했다.
첫 Ruff의 미사용 import 실패를 보존했다. 전체 ETW 스키마 경고와 원120분FAIL은 유지한다.
서버·제품·설정·우선순위·백업 변경 없이 기존 trace의 wake-caller 스택 결합으로 후속 범위를 좁혔다.
기존 THREADLINK/OUTSYM/파일 생성·fsync 비교는 반복하지 않는다. R1~R6와 출시HOLD 유지.
[근거·방법·한계·다음 단계](C:/Users/user/Desktop/SmartFactory/PYJOIN_20261018_900730b0/review.md).


### 2026-10-18 스레드 호출 문맥·그래픽 경로 대조

WAKEPAIR는 기존02-ON/05-OFF 요청의 Ready456건과 직전 문맥114건을570개 유일 호출 문맥에
연결했다. Image27,778건/Process486건/스택980조각을 독립 비교해 누락·초과0, 검산17,521항목과
중복/부재/충돌6거부 조건을 확인했다. 미확정 프레임31개와 XML 스키마 경고는 보존했다.
ON 탐색기에는 thumbcache/windows.storage/RPC 및 shell32/UI 경로가, OFF 앱에는
d3d11/dxgi/d3d10warp 경로가 보였다. WARP 사용자 스택 연결은 ON6/OFF24건이며 지속 시간이 아니다.

기존221.0337ms 요청의 PID17632 일반 CPU73표본 중11개가 WARP를 포함했다(첫 Ready3/둘째7/밖1).
PID15700은29개 중0, DPC1개는 앱 귀속에서 제외했다. 검증된102표본의 주소/모듈 순서를 재사용했고
새 ETL 해석·심볼 다운로드는 하지 않았다. 후보0732c8e main.js50행의 가속OFF는 PR144 시작 최적화다.
후속은 동일 격리 화면에서 실제 backend 차이를 확인하는 그래픽 비용 비교 준비이며 운영 변경은 없다.
제거 후보에는 기존 설치 앱20회 시작 gate가 필요하다. 단독 원인이나 개선 효과는 미확정이다.

새 오프라인 decoder build/두 export/수정 분석/독립 검산/과거 재집계 exit0. 초기 분석형식 누락과
재집계 상태 이름 오류의 exit1을 보존했다. 제품/서버/설정/백업 변경 없이 원120분FAIL 및R1~R6HOLD 유지.
[검증·원문·제약](C:/Users/user/Desktop/SmartFactory/WAKEPAIR_20261018_72c71e5d/review.md).


### 2026-10-18 개발 PC 후보 화면 그래픽 비교

GPUCHECK는 후보50파일을 고정해 실제 software(Microsoft Basic Render Driver)/default(RTX3060)
경로를 확인하고,6초 준비+30초 네 회차를S/D/D/S 순서로 수행했다. 전체 앱 CPU초는2.336990,
3.965026,3.941892,2.249473이었다. rAF25ms 초과0/long-task0, 모의health 최대3.5594ms다.
가속 기본값 변경의 비용 개선 근거가 아니며 현장 지연 원인도 확정하지 않았다.

입력220회·누적CPU값496개·동일세대/창포커스/전체차트영역/API/소유Job 정상종료를 검산했다.
각 실행HTTP177건/data70/image36은 같았으나 측정 경계 내 data는60/60/59/59건이다.
history 호출0, synthetic 영상/수치, 장비UNKNOWN·일부 기본layout 잘림, observer 부하 미분리,
공유캐시·12CPU개발PC·실제backend부재를 한계로 남겼다. 첫 준비의API/시각 누락과 두 번째zoom
미적용은 보존하고 수정R3의 네 회차만 비교했다. 제품/서버 변경 없이 원120분FAIL/R1~R6HOLD 유지.
후속은 기존 현장GPU/드라이버 식별 정보의 적용 가능성 확인이다. 같은 모의 비교를 반복하지 않는다.
[방법·결과·한계](C:/Users/user/Desktop/SmartFactory/GPUCHECK_20261018_fcf9b609/review.md).


### 2026-10-18 현장 그래픽 장치와 프로세스 역할 연결

FIELDGPU의 승인 SSH 3회 exit0으로 Intel UHD610/30.0.101.1273,Celeron G5905/2CPU를 확인했다.
GPU17632의 WARP 선택, renderer15700의 GPU 합성 OFF/래스터1과 정밀 생성 시각을 읽었다.
현재4프로세스 수명이 기존221.0337ms trace를 포함하고 backend14012는 기존 native 세대와 같다.
R2STACK 봉인 manifest→원 trace header/clock 입력 해시로 연결했다. 과거 WARP 표본은 GPU 프로세스에
연결되지만 exclusive CPU 시간·단독 원인·가속 전환 효과는 확정하지 않았다. 개발 RTX3060 결과는 현장 대체 불가다.
06:43KST Smart Factory 전면 Running과60180·28을 관찰했다. 새 사용자 확인이나 metadata 변경은 없다.
제품/설정/드라이버/설치/백업 변경 없이 원120분 FAIL/R1~R6 HOLD를 유지한다.
[읽기·검산·후속범위](C:/Users/user/Desktop/SmartFactory/FIELDGPU_20261018_a73c09d2/review.md).


### 2026-10-18 현장 Intel 화면 비교의 결과와 불완전 CPU 기록

FIELDRENDER는 검산한 후보frontend50파일/Electron44.3.0으로 실제IntelUHD610과software를
S/D/D/S,6초준비+30초씩 비교했다. 네 회차 기능·포커스·요청·정상종료/Job잔류0은 확인했다.
전체CPU초software5.071587/5.207482,default2=5.952364다. default3는일시GPU20252의
최종CPU가 없어 strict검사exit1이며 전체 합계 미확정,고정 프로세스 소계만5.463628로 남긴다.
정확한Intel중앙값은 계산하지 않고 실패한 회차를 대체하지 않았다. 관찰 길이를 맞춘 소계도
두software값보다 커,이 결과로 운영 가속 기본값을 바꾸지 않는다. 지연 인과관계는 미확정이다.
현재 화면의 위젯·512×288반복JPEG/고정수치 범위이며 화면밖timeseries·실제backend·시작QA를
검증하지 않았다. 모의health는 실제gate대체가 아니다. 첫 준비·전달·회수 실패도 원본을 보존했다.
최종임시작업/소유프로세스0,기존main17996동일세대Running과07:28KST전면60180·28을 확인했다.
해당metadata는관찰값이며새사용자확인이아니다. 제품/설정/드라이버/설치/전체백업변경없음.
원120분FAIL/R1~R6HOLD유지. 기존221ms보존trace의미확정경로검토로돌아가며같은비교를반복하지않는다.
[근거·실패·검산](C:/Users/user/Desktop/SmartFactory/FIELDRENDER_20261018_e19b0d46/review.md).


### 2026-10-18 정확한4c 소스 재현과 과거drop15 직전 적체 연결

R5FORENSIC은기존5manifest175파일·원문11표본을검산했다.10/09KST18:55:28/45/18:56:03의
완료93,439/fact4,091,224·SHA는같고queue32/47/63,접수93,472/93,487/93,503이다.
기존factprefix3,997,784보다1개앞서며접수−완료=queue+1이다.마지막drop0은18:56:03,
첫15는19:56:59이고정확한발생시각/함수는미확정이다.사전회수console-pin pending한계도유지했다.
원최종sidecar의begin해시/같은세대,접수=완료94,043·잔류0을확인했으나drop15/integrity미해결은보존했다.
정확한4c Git blob57파일로정상/크기초과15/이미지쓰기대기/보존정리대기4조건exit0이다.
실제259이미지/행SHA와worker종료를확인했다.정리대기는fact1개앞섬을재현하지만현장원인은아니다.
첫Git-probe차단예외와다음Windows audit인수형식검사실패를보존했고R3만4PASS다.
제품/서버변경없는로컬분석이며동일API/성능재시험은하지않았다.R1~R6/출시HOLD유지.
다음은기존R4 index의4,091,224번째fact와인접원본mtime/로그를확인하는것이다.
[근거·검산·실패·한계](C:/Users/user/Desktop/SmartFactory/R5FORENSIC_20261018_c48e9d21/review.md).


### 2026-10-18 과거 대기열·파일 시각·시간당 정리 후보 대조

R5TIMELINE은 기존 인덱스619행과 원본 목록619행을 연결하고 별도로4,333필드 및 메타데이터를
검산했다. 첫 정체의 fact는4,091,224번째, 다음 이미지의 촬영 대비 수정 차이는141.982658초다.
대기열32/47/63의 끝 행과 원문 enqueue 시각도1마이크로초 이내로 맞는다.128번째 대기 행 뒤
촬영 공백은6.846484초다. 촬영/수정 차이2초 초과 집합은131개와96개이며 두 번째 최대113.943019초다.
정체 후보 시작 간격3,727.010308초는 원래3600초 주기 동기 retention 경로와 일치하는 양상이다.
단, 원본 수정 시각은 나중 보존한 메타데이터이며 함수 실행 추적이 아니다. 실제 원인과 drop15의
개별ID·영향은 미확정이다.58분 촬영 공백을58분 저장 정체로 확대하지 않는다.
선택 로그206행의 JSON/일반 텍스트를 함께 처리했다. 최초 형식 가정/시각 비교 실패를 보존하고
최종 대조·별도 검산·Ruff·문서 검사는exit0이다. 제품·서버·새 백업 변경 없이 전체 gate HOLD를 유지한다.
[근거와 검증 방법](C:/Users/user/Desktop/SmartFactory/R5TIMELINE_20261018_a481cd39/review.md).


### 2026-10-18 실제 서버 보존 정리 읽기 경로의 비용

RETSCAN은 실제 서버의 10/14 보존 사본에서 원래 retention AST의 읽기 경로를 실행했다.
8개 날짜 폴더의319,971항목/639,982회 stat에91.094초, CPU53.03125초,
stat 누적21.865865초가 걸렸다. 만료 후보0/실제 삭제0이며 삭제 비용과 계측 오버헤드는 분리하지 않았다.
원10/09 디렉터리 상태·동시 부하·캐시·스케줄링이 달라 과거 drop15의 직접 원인은 미확정이다.
로컬5종 종료/차단 시험과 서버 입력EOF 저장·정리, 실제 측정exit0, 회수4파일 해시를 확인했다.
초기 Python 종료 실패와 SSH Z:미매핑 회수 실패는 보존했다. 수정 도우미/회수/별도 검산/Ruff는exit0이다.
main17996/backend14012는 같은 세대이며 도우미 잔류0,08:13KST Smart Factory 전면 Running을 확인했다.
작업 정보는08:04 이후 필수값 미입력으로 관찰했으며 값을 임의로 넣지 않았다.
현재 작업 트리의 retention 네 함수 AST는 같지만 설치본 전체 동일성 검증을 대신하지 않는다.
제품·설정·설치·새 백업 변경 없이 원120분FAIL/R1~R6/출시HOLD를 유지한다.
[범위·실패·검산·후속](C:/Users/user/Desktop/SmartFactory/RETSCAN_20261018_3b876b21/review.md).


### 2026-10-18 보존 정리 분할 처리와 수명 관리의 로컬 검증

RETINC은 소스80fee9aa에 보존 정리 분할 처리를 저장했다. 호출당256단계/monotonic10ms의
협력적 예산과 scandir 지연 순회, 기존 큐의 유휴 진행, 종료·writer/설정 교체 시 iterator 닫힘을 적용했다.
단일 OS 호출의 hard 상한은 아니다. 주기·strict mtime cutoff·관리 파일 조건·캡처/대장/큐 회계를 유지한다.
수정 전2회귀는601개 전체 확인/20회 확인으로FAIL이었다. 첫 후보의 빈 연·월 폴더 삭제 차이를
별도 대조로 발견해 실패를 보존하고, 관리 날짜 폴더를 제거한 부모만 정리하도록 보완했다.
최종 신규13회귀를 포함한 전체 백엔드950건(1skip),Ruff,mypy9파일,범위 검산,staged diff검사는exit0이다.
기존 writer20메서드/helper15개/큐 집계 AST가 같고 최종 소스 해시와 로컬 커밋을 연결했다.
운영 서버 적용·새 경로의 실제 규모 성능·전체 패키지 QA는 미완료이며 다른 기존 작업 트리 변경도 남았다.
원120분FAIL/R1~R6/출시HOLD와 미서명 정책을 유지한다. 서버/설정/설치/새 백업 변경은 없다.
[변경·실패 보존·검증·다음 단계](C:/Users/user/Desktop/SmartFactory/RETINC_20261018_4385cc9c/review.md).


## 2026-10-18 RETBOUND: 정밀 시계 보완·현장 연결 대기

 개발Python3.12.6 monotonic의GetTickCount64/15.625ms 해상도를
확인해, 소스a21e963d의10ms 예산 두 호출을QueryPerformanceCounter 기반perf_counter로 바꿨다.
저해상도 시계가 정지한 회귀는 수정 전20개/기대2개FAIL(exit1),수정 후통과했다.
제품 나머지AST 불변과 최종13회귀·백엔드950건(1skip,308.369초)·Ruff·mypy exit0을 확인했다.
최종R2 도우미7조건과 공유5파일 SHA/선택6함수AST/PS5.1구문·ACL객체 검산을 마쳤다.
로컬합성1,200파일은9회 호출,최대10.0594ms/148단계,열린scandir최대4/종료0이다.
작은 합성시험이며 실제 캡처 스케줄·삭제 비용·서버 성능은 미검증이다.
Chrome은마지막온라인08:14/오프라인,SSH는10.078초timeout(exit255)이다. 서버 최종복사·실행·
운영화면복귀가 미완료여서 연결 복구를 요청했다. 서버/설치/설정/전체백업 변경은 없다.
원80fee9aa 전달묶음은 대체관계만 별도기록하고 보존했다. R1~R6/출시HOLD 유지.
[근거·수정 전후·전달 상태·후속](C:/Users/user/Desktop/SmartFactory/RETBOUND_20261018_2f683e7a/review.md).

### 2026-10-18 우선순위 변경 기록의 원본 대조

R2PRIORITY는 기존221.0337ms 요청의 Thread opcode48/49 이벤트3,905건을 XML/ETL의
원시payload·QPC·CPU·header PID/TID까지 대조했다(exit0). 손상/누락/중복 등9조건 검출,
도우미Ruff exit0과 소유 프로세스 정리를 확인했다. 첫DLL 상대경로 비교 실패는 보존했다.
두 긴Ready구간에 수집기 변경 이벤트는 없지만 CSwitch 우선순위8·10·11은 관찰된다.
이벤트 부재를 동적 우선순위 불변이나 인과 해결로 해석하지 않는다. 서버SSH는 timeout(exit255)이며
서버 변경·전면 복귀는 수행하지 못했다. 연결 복구 후 기존RETBOUND_R2 현장 검증을 이어간다.
제품·설정·백업 변경 없이 원120분FAIL/R1~R6/출시HOLD 유지.
[검증 결과와 한계](C:/Users/user/Desktop/SmartFactory/R2PRIORITY_20261018_73ac19de/review.md).
