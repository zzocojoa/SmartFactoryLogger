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

## 남은 작업

- 현재 대용량 CSV에 맞는 정상 종료·manifest 결합 증거 경로와 새 현장 설정 기준 준비.
- 승인된 서버 교체, 변경 후 현장15분 및 선행 조건 통과 후120분 관찰.
- 물리 경계 NOT_TESTED/제조사 확인·전체 데이터 미결의 처리와 실제 운영 승격 판단.

새 전체 서버 백업, 서버 설치·재시작·프로파일 변경, 운영/롤백 기준 갱신은 이 단계에서 하지 않았다.
기존 현장15분 FAIL과 출시 HOLD를 유지하며 1.0.30의 현장 개선 효과는 아직 미검증이다.
