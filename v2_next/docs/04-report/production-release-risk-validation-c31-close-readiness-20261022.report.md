# 1.0.31 적용 전 정상 종료 관찰 준비

2026-10-22. 현재 1.0.30 / `240a4952` 실행을 읽고, 정상 종료와 원본 검산 관찰기의
요청을 준비·전달했다. 서버에서 두 경로의 `-ValidateOnly`가 각각 종료 코드 0으로 끝났다.
준비 시점에는 관찰기 실제 실행·앱 종료·설치·설정 변경·전체 백업을 수행하지 않았다.
이후 사용자 조작 가능 응답을 받아 아래 실제 관찰 단계로 이어갔다. 출시 **HOLD**를 유지한다.

## 현재 실행과 고정 요청

- 개발·서버 실행 폴더: `C:/Users/user/Desktop/SmartFactory/F31CLOSE_20261022_b1d4a5f6`
- main PID 14568, backend PID 3104. 현재 작업 정보는 작업자 입력 제품 21152·금형 4.
- logger: `a3b807df-da24-4928-a899-ddeb79468923`
- CSV: `Factory_Integrated_Log_v2_20261022_000000.csv`, 첫 sample_seq 432343.
- 읽을 때 CSV 크기 317,743,236바이트. 첫 행 확인은 전체 CSV 품질 검증을 대신하지 않는다.
- config.ini SHA256: `0b12949153b3b2ef384aaad5ab394850413db2fc5d072a3a697852b9c9ede3f4`
- 요청 SHA256: `ecdd5c67a8f98d5ae5b8949d39bebde073ea21dcfc3221a86ccf1be93157eba6`
- 진입 스크립트 SHA256: `82b3a669187c19952b92c88e31620386ea88c91d9fb3f259fc32f95e6ee1455f`

기존 실제 SSH 정상 종료·연결 단절 시험을 통과한 guard와 native library를 재사용한다.
진입 스크립트는 기존 검증본의 경로·build·logger·CSV·입력 해시만 치환했으며 역치환으로
원문 일치를 확인했다. PowerShell 구문 검사 종료 0, 공유·서버 파일별 검산 종료 0,
서버 preservation/runtime-close 사전 검사 각각 종료 0이다. 4파일 합계 12,688바이트다.
서버 사전 검사에서는 자식 관찰 프로세스를 시작하지 않았다.

## 실제 실행 선행 조건

브라우저 도구는 kernel assets 경로 오류, 대체 computer-use 도구는 Chrome 현재 URL을
확인할 수 없어 이번 turn의 UI 조작을 중단했다. 이후 UI 입력은 수행하지 않았다.
Smart Factory 화면과 전면 표시 여부는 미확인이다. 사용자에게 X를 직접 누를 수 있는
시점을 요청했으며, 준비되지 않은 종료 관찰기를 실행해 대기 시간을 소진하지 않는다.

실행 순서: 최신 세대·CSV·설정·공간 재확인 → preservation 시작 → READY 확인 →
runtime-close 시작 → 두 READY와 실제 프로세스 확인 → 정상 X 종료 안내 → 실제 종료 코드와
원본 전수 검산 결과 검토. 요청의 CSV나 실행이 바뀌면 이 요청을 그대로 실행하지 않는다.
성공한 종료·원본 보존 증거가 있어야 1.0.31 설치 요청을 생성한다. 제품 강제 종료는 하지 않는다.

근거: 실행 폴더의 `runtime-and-csv-read.json`, `parse-terminal.json`, `shared-transfer.json`,
`verify-observer-input.json`, `both-observer-preflight.json`, `readiness.json`.

## 실행·회수 준비 보완

후속 turn에서 개발 PC의 `launch_observer.py`를 준비했다. 기존 실행기의 경로·고정 해시와
준비 상태 키 6개만 바꿨으며 역치환 원문 일치, 두 역할의 기본 준비 실행 종료 0,
생성한 PowerShell 진입문 2개의 구문 검사 종료 0을 확인했다. 기본 호출은 실행하지 않는다.
실제 관찰은 사용자 조작 가능 응답과 최신 상태 확인 후 `--execute`를 명시할 때만 시작한다.

`recover_observer.py --launch <이번 launches 아래 실제 실행 폴더>`는 종료 코드 0과
SSH 콘솔의 control SHA를 요구한다. 해당 control이 출력한 result SHA·manifest SHA,
정확한 파일 목록·파일별 해시를 묶어 회수한다. 서버가 다시 실행 중이면 중단한다.
회수 성공은 `CLOSED_OBSERVER_FILES_RECOVERED_PENDING_CONTENT_REVIEW`로 기록하며,
실제 정상 종료·CSV·원본 보존의 내용 검토를 대신하지 않는다.

기존 실제 정상 종료 및 원본 검산 결과를 입력으로 회수 검사 21개를 통과했다.
해시 누락·중복, 경로 이탈, 역할 혼용, 파일 추가·누락을 거부했고 native PowerShell
구문 검사도 종료 0이었다. 초기 15검사 결과는 보존하고 최종 21검사는
`recovery-checks-r2/summary.json`에 기록했다. 현재 실행의 완료 결과로 오인하지 않는다.

이 후속 준비에서는 서버에 접속하거나 관찰기를 시작하지 않았다. 사용자 정상 종료 조작
가능 여부 응답은 계속 필요하다. 실행기가 살아 있는 대기 상태는 아니며 `activeExecutions=[]`다.

## 사용자 응답 후 실제 관찰 재개

사용자가 “지금 준비됨”이라고 응답했다. `resume-ready-server-read.json`에서 기존 main 14568,
backend 3104, logger·CSV·설정 결합과 작업자 입력 21152·4를 재확인했다.
`resume-ready-preflight.json`의 두 사전 검사도 각각 종료 코드 0이다.
새 전체 백업 없이 `launch_observer.py --role preservation --execute`를 실행했다.

- 로컬 실행: `launches/preservation-9a24aa7a6236`, SSH PID 34716.
- 서버 control: `C:/Users/user/Desktop/SmartFactory/G80b9cbf58d0e`.
- 서버 controller PID 11156, 생성 FILETIME 134371233585768982.
- `observer-live-read/read-*.json`에 실제 세대·진행 로그를 남긴다. 처음에는 원본 목록 확인 중이며
  이 단계는 아직 `READY_FOR_NORMAL_APP_EXIT`가 아니다.
- preservation READY 후 runtime-close를 시작하고 두 관찰기의 실제 READY와 살아 있는 세대를
  확인한 뒤 사용자에게 X 조작을 요청한다. 종료 시점과 결과 판정은 별도 기록한다.

회수 도우미 사전 재검토에서 PowerShell/.NET 경로 정규식의 역슬래시 이스케이프 오류를
발견했다. 기존 바이트는 보존하고 `recover_observer_r2.py`를 만들었다. 기존 Python 결합 검사와
구문 검사에 실제 .NET 정규식 실행 5개를 더한 26검사를 통과했다(종료 코드 0).
구문 검사만으로 이 오류가 검출되지 않았던 한계를 보완했다. 서버 관찰 코드에는 변경이 없다.

- 회수 R2 SHA256: `415d48e32a406990f8691ea0ad2873cb60a77bf801c4dfed74dadb83b64a989e`.
- 검사 근거: `recovery-checks-r3/summary.json`, `regex-runtime.stdout.log`, `regex-runtime.stderr.log`.
- 실제 회수에는 R2를 사용하며, 26검사 성공은 현재 서버 종료·데이터 검증 성공을 뜻하지 않는다.

## 두 관찰기 준비 확인 및 정상 종료 요청

2026-10-22 06:24:20 UTC 서버 읽기에서 두 controller의 생성 세대와 생존,
두 `READY_FOR_NORMAL_APP_EXIT`, 비어 있는 stderr, HOLD 결과 부재를 확인했다.
같은 main 14568·backend 3104와 Electron 자식 3개도 실행 중이었다.
사용자에게 이 확인 직후 정상 X 종료를 요청했다. 아직 종료·검산 성공으로 판정하지 않는다.

| 역할 | 로컬 실행 폴더 | 서버 control | 결과 폴더 |
|---|---|---|---|
| 원본 보존 | `launches/preservation-9a24aa7a6236` | `G80b9cbf58d0e` | `O984ca45d` |
| 정상 종료 | `launches/runtime-close-b70761a3a78d` | `G7916e91b8201` | `Reb2bea918aeb` |

두 서버 경로의 부모는 `C:/Users/user/Desktop/SmartFactory`다. runtime-close SSH PID는
20016, 서버 controller PID는 11680(생성 FILETIME 134371238449797905)이다.
실제 준비 증거: `observer-live-read/read-20261022T062355356002Z.json`.
준비 전 inventory는 420,382파일·19,132,396,746바이트였으며 종료 후 실제 최종 manifest와는
구분한다. 이 읽기까지 앱 재시작·설치·설정 변경·전체 백업은 수행하지 않았다.

## 실제 정상 종료 및 현재 CSV 검토 완료

사용자 “종료됨” 응답 후 서버에서 앱 프로세스 부재를 확인했다. runtime-close controller는
PASS·actual exit 0, 자식 정리 후 active/remaining 0, 강제 종료 없음이다.
결과 `Reb2bea918aeb/result.json` SHA256은
`a30f03997ae09ce0ac9fa857752cd838a43d334eaede7e7f3ba365344e3fe22a`이며 SSH 출력과 회수 파일이 일치했다.
helper commit `305014c8b1d85d7e3f43a250d2f33e7f959ce8fb`의 116개 원본 파일을 재대조한 뒤
`review_health_runtime_close.py`를 실행해 종료 코드 0을 확인했다.

- 범위: `LIMITED_RUNTIME_CLOSE_RECEIPTS_VERIFIED`, 현재 CSV와 보유 native handle 종료 증거.
- main·backend·Electron 자식 합계 5개 모두 실제 종료 코드 0, 강제 종료 없음.
- 현재 CSV 239,639행, sample_seq 432343–671981 연속, shutdown finalized 마지막 번호 일치.
- 온도 상태: valid 221,578행, under_range 18,053행, stale 8행. 이 상태를 삭제하거나 valid로 바꾸지 않았다.
- config SHA256은 고정 요청과 일치. 이미지 대응·worker shutdown receipt·과거 CSV 전체·물리 QA는 이 검사 범위가 아니다.
- 내용 검토: `recovered-runtime-close-b70761a3a78d/content-review.json` 및 실행 로그·종료 기록.
- 공유 보관: `Z:/SmartFactory/20261022/return/F31CLOSE_20261022_b1d4a5f6/runtime-close-Reb2bea918aeb`,
  31파일·327,893,741바이트 파일별 검산 완료. `normal-close-archive.json` 참조.

원본 preservation controller는 같은 `G80b9cbf58d0e`에서 계속 실행 중이다. 앱은 닫힌 상태이며
원본 결과가 완료·회수·정상 종료와 결합되기 전에는 설치하지 않는다. 설치본·직전본·등록 롤백본과
관련 참조 6개는 `install-input-preflight.json`에서 다시 해시 대조했다(종료 0).
로컬 설치 요청 생성기와 실행·회수 경로를 준비했지만 아직 실제 요청이나 설치 실행은 없다.
`install-preparation-checks/summary.json`은 Python 구문 3개·native PS 구문 2개와 helper 핀 검산만
증명한다. `preservation-content-checks/result.json`의 16개 검사도 실제 원본 보존 완료 증거는 아니다.

## 원본 대조 진행 중 준비한 정상 실행 경로

같은 원본 관찰기의 stdout에서 첫 Capture 420,563파일·19,136,133,224바이트 완료와
두 번째 Verify의 카운터 초기화를 확인했다. 이후 진행 숫자는 두 번째 대조 범위이며
전체 검산 완료율이나 최종 PASS로 표시하지 않는다. 최종 결과와 원래 controller의 종료를
확인하기 전에는 설치 요청을 생성하지 않는다.

이 대기 중 `start-preparation/start-installed-candidate.ps1`을 준비했다. 10월 19일 서버에서
실제 실행·회수했던 일반 사용자 시작 절차의 대상 commit·버전·참조 경로·해시만 C31로
바꿨다. 역치환 원문 일치와 설치 실패·문자열 종료 코드·보존 증거 누락 등을 거부하는
native PowerShell 26검사를 통과했다(종료 0). 설치 실제 결과와 파일별 검토 완료를
요구하는 `run_standard_start.py`는 기본 호출이 준비 전용이고 `--execute`를 별도로
지정해야 전달·실행한다. 현재 기본 호출만 종료 0이며 서버 작업이나 task 등록은 없다.

- helper SHA256: `674e7a669da6e72c5e108c62bed748b5efec5e2a98a9fbe7a1b639ae384d84f8`.
- driver SHA256: `7084734fdc004a5138c5fda4ff4d692df7c248ab85932e3d9d713bbd563db85c`.
- 검사: `start-preparation/restart-validation.json`, `tests.stdout.log`, `tests.stderr.log`, `tests-terminal.json`.
- 이 준비는 설치·새 버전 실행·화면 확인·현장 성능 검증 완료를 뜻하지 않는다.

## 원본 보존 검산 완료와 설치 절차 시작

원래 preservation 실행이 5,348.953초 후 실제 종료 코드 0으로 끝났다. guard도 PASS,
강제 종료 없음·자식 정리 완료다. 두 번째 대조까지 완료한 최종 합계는 420,563파일,
231디렉터리, 추가 데이터 스트림 680개, 19,136,133,224바이트다.

- 서버 원본 결과: `C:/Users/user/Desktop/SmartFactory/O984ca45d`.
- result SHA256: `4b381cff3c8c562063a5f9f73a062b795446a24197c8bdd1979e1b23099b2b45`.
- manifest SHA256: `638a8c69f887cfa4d720c54305178bf688faeb32e86ec077cfb58c40d1e65013`.
- 실제 내용 검토: `preservation-content-review/review.json`, 상태
  `ORIGINAL_OBSERVATION_AND_NORMAL_CLOSE_BOUND`, 실행 종료 코드 0.
- 공유 증거: `Z:/SmartFactory/20261022/return/F31CLOSE_20261022_b1d4a5f6/preservation-O984ca45d`,
  29파일·204,500,668바이트 파일별 검산 완료. 원본 데이터 전체 백업을 만든 것은 아니다.

실제 종료와 원본 검산을 결합한 요청 3파일을 새 서버 폴더
`C:/Users/user/Desktop/SmartFactory/I31_20261022_b1d4a5f6`에 전달하고 해시를 대조했다.
요청 SHA256은 `19589412e4e250c3eb8faa06bdbd0c8f70e20b39e34386211251090b2d0501df`다.
2026-10-22 07:48:23 UTC에 설치 절차를 한 번 시작했으며, 초기 stdout에서 설치 전 원본
재검산 진행을 확인했다. 로컬 SSH PID 29116, 서버 wrapper PID 20924,
생성 FILETIME 134371289273744454다. 실제 설치 프로그램 종료·설치 후 보존 검산·새 앱
실행은 아직 확인 전이다. `install-execution`의 원래 실행을 추적하며 자동 재실행하지 않는다.

## 설치 검산 대기 중 후속 검증 준비

새 앱의 실제 실행을 읽는 `read_candidate_runtime.py`는 설치 결과·보관본 해시를 먼저
요구한다. 현재 C31인 것처럼 바꾼 시험 입력은 별도 합성 자료로 표시했으며, 버전·commit·
계정·세션·native handle·첫 CSV 행 대응 등 13개 로컬 검사만 통과했다.

`prepare_candidate_observer.py`는 실제 C31 실행 기록이 확보된 뒤에만 새
`C31CLOSE_20261022_b1d4a5f6` 묶음을 만든다. 기존 종료 관찰 절차의 출처·해시를
유지하고 runtime-close 하나만 허용했다. 8개 로컬 합성/구문 검사는 종료 코드 0이며,
preservation 역할은 PowerShell 인수 검사에서 거부됐다. 이 준비로 서버 관찰기를
시작하거나 앱을 종료하지 않았다. 종료 회수본의 검토·공유 보관을 위한
`review_candidate_close.py`도 준비했지만 실제 새 버전 종료 결과는 아직 없다.

기존 USER_SELF 승인 설정의 네 확인 항목을 연결하는 후속 생성기·적용·회수 경로는
현재 C31 helper와 실제 C31 종료 metadata를 요구하도록 준비했다. 대상 helper는
기존 C31 준비 단계의 13검사 통과 바이트
`1c52e1645c219f2fca385882a6298405719cfc6ff76cfc7328fb0976b2b33e27`다.
현재는 로컬 어댑터 준비·역치환·Python 구문 확인과 준비 전용 호출만 수행했으며,
실제 묶음·metadata fingerprint·서버 설정 변경·적용 성공을 확인한 것은 아니다.

근거: `candidate-observer-checks/result.json`, `runtime-reader-checks/result.json`,
`attestation-adapter-preparation.json`, `attestation-execution-adapter-preparation.json`.
설치 원본 검산이 진행 중인 동안 서버에 추가 관찰기나 설정 변경을 병행하지 않는다.

## 설치 프로그램 실제 종료 확인

`install-live-read/phase-20261022T082019514860Z.json`에서 이번 요청의 SHA256과
일치하는 서버 결과 `SmartFactory/Jc4d79976`을 확인했다. 설치 전 원본 대조와
freshness 영수증이 생성됐고, 실제 installer PID 18464의 보유 native handle로
종료 코드 0, 강제 종료 없음이 기록됐다. 서버 기록의 시작은 08:19:57.4303118 UTC,
종료는 08:20:28.9000842 UTC다.

이는 설치 프로그램 종료 확인이며 설치 후 원본 보존·전체 payload 독립 검토나
앱 실행 확인 완료는 아니다. 원래 SSH 실행 19011을 계속 추적하며 앱은 닫힌 상태로 유지한다.

### 점검 중 수집 공백

기존 실행의 마지막 저장 행은 서버 기록 기준 2026-10-22 15:25:47.442802 KST,
sample_seq 671981이다. backend의 실제 종료 기록은 06:26:07.3841378 UTC다.
앱을 닫고 검산·설치를 수행하는 구간에는 새 온도·이미지를 수집하지 않는다.
원본 파일 보존 성공이 이 점검 시간의 측정값을 복원했다는 의미는 아니다.
`maintenance-gap-open.json`에 마지막 저장 행·종료 근거를 기록했으며 새 실행의 실제
첫 CSV 행을 확인한 뒤 구간을 연결한다. 줄바꿈을 포함한 CSV 필드는 CSV 파서로 읽었다.

### 후속 요청 형식 결합 수정

서버 실행 전에 실제 종료 도우미와 대조하여 로컬 요청 생성기의 형식 결합 오류를 찾았다.
처음 준비한 C31 생성기가 이전 버전용 v6를 만들었으나 C31 소비 도우미는 v7을 요구한다.
초기 13개 생성기 검사도 같은 v6 기대값을 사용해 이 불일치를 잡지 못했다. 초기 결과는
보존하고 서버 전달·실행은 하지 않았다.

`read_candidate_runtime_r2.py`, `prepare_candidate_observer_r2.py`,
`prepare_candidate_attestation_r2.py`, `capture_attested_candidate_runtime_r2.py`로
요청 형식과 참조 해시를 갱신했다. 생성기 13개·관찰 어댑터 8개를 다시 검사해 종료 0이다.
추가로 실제 서버 도우미의 요청 검증 함수를 native PowerShell에서 호출한 9조건은
기존 잘못된 생성기 요청 거부, R2 v7 수락, 기존 240a/v6 호환 및 잘못된 세대·번호 거부를
확인했다(종료 0). 최초 native 검사기의 모듈 경로 오류는 별도 실패 기록으로 보존했고,
native PS5.1 모듈 경로를 명시한 재실행 결과는 `runtime-contract-r2-checks-native`에 있다.
진행 중인 설치·원본 검산 도우미는 수정하거나 다시 실행하지 않았다.

## 설치 후 독립 검산 완료

원래 설치 절차가 종료 코드 0으로 끝났다. `recover_current_install.py --execute`도
종료 0이며, 서버 `Jc4d79976`의 실제 결과 23파일을 회수하여 콘솔 해시·각 파일 해시와
내용을 대조했다. result SHA256은
`b69b1505cf8aa2be1e59bf35cd32ef1bd6823c0c46def69499b56d85b1e4bf10`이다.

- 실제 installer 종료 0, 강제 종료 없음, 같은 보유 native handle의 시작·종료 기록 일치.
- 새 payload 1,867파일과 제거 파일 1개, 버전 1.0.31 등록 일치.
- 설치 전후 원본 420,563파일·231디렉터리·추가 스트림 680개·19,136,133,224바이트 일치.
- config SHA256 `0b12949153b3b2ef384aaad5ab394850413db2fc5d072a3a697852b9c9ede3f4` 유지.
- 설정 변경·새 전체 백업·자동 복귀 없음. 이 결과 시점에 앱은 종료 상태다.
- 독립 검토: `installation-final-review/review.json`, 상태
  `INSTALLATION_RECEIPTS_PAYLOAD_AND_ORIGINAL_PRESERVATION_VERIFIED_PENDING_RUNTIME`.
- 공유 보관: `Z:/SmartFactory/20261022/return/I31_20261022_b1d4a5f6`, 파일별 검산 완료.

이후 `start-preparation/run_standard_start.py --execute`를 한 번 시작했다.
새로운 설치 실행이 아니며, 일반 사용자 세션의 실제 앱 시작과 수집·화면 확인은 별도로 검토한다.

## 새 버전 실행 확인과 다음 정상 종료 대기

일반 사용자 실행과 회수는 모두 종료 코드 0이다. 서버 결과 `ST31_e80cefbf`의
5파일을 검토했으며 result SHA256은
`7f0091e6bc9c7d56c3836b14e15960e9cc9387fe7683e2347e6378101d95cc1b`다.
임시 실행 작업 정의는 제거됐고 앱 중단 호출은 없었다.

`wait_for_c31_runtime.py --execute`와 `read_candidate_runtime_r2.py --execute`가
모두 종료 0이었다. 실제 1.0.31/a7e5149b, REAL·Running을 확인했다.
main PID 6764, backend PID 6752 및 Electron 자식들은 세션 3의 일반 사용자 권한이다.
logger는 `cea865b7-e83c-41ab-86e9-3ff1627806f5`, 새 CSV는
`Factory_Integrated_Log_v2_20261022_175209.csv`, 첫 sample_seq는 1이다.
요청 v7 SHA256은 `9524183a9d587938d679116fb2fad16a072f4a22743c202f115483548dc5499c`다.
설정 해시는 설치 전 값 그대로이고, 작업 정보는 기존 운영자 입력 21152·4/valid=true다.

첫 새 CSV 행은 서버 기록 기준 17:52:09.194239 KST다. 이전 마지막 저장 행과의
시간 차이는 8,781.751437초(약 146분 22초)이며 `maintenance-gap-closed.json`에 남겼다.
이는 서버 wall-clock상의 저장 경계로, 정확한 센서 누락 개수나 단조 시계 성능 측정값은 아니다.

새 실행에 결합한 종료 관찰 준비 4파일(11,406바이트)을
`C:/Users/user/Desktop/SmartFactory/C31CLOSE_20261022_b1d4a5f6`에 전달·검산했다.
`candidate-close-preflight`는 종료 0, `CANDIDATE_CLOSE_PREFLIGHT_VERIFIED`다.
관찰기는 아직 시작하지 않았으며 앱은 계속 Running이다.
사용자에게 대시보드 정상 표시·전면 상태와 짧은 정상 종료 조작 가능 여부를 확인 요청했다.
응답 후 현재 실행을 다시 대조하고 실제 READY가 확인된 뒤에만 X 클릭을 안내한다.
새 버전의 종료·네 항목 attestation·해당 현장 QA와 전체 출시 승격은 아직 미완료다.

## 새 버전 정상 종료·설정 확인 연결·일반 실행 복귀

사용자가 첫 C31 실행의 대시보드 정상 표시·전면 상태와 종료 조작 준비를 확인했다.
현재 세대의 사전 검사를 다시 통과한 뒤 runtime-close 관찰기 하나만 시작했다.
`G1a05fde4c004`의 실제 `READY_FOR_NORMAL_APP_EXIT`, 동일한 관찰 프로세스와
실행 중인 앱을 확인하고 X 클릭을 안내했으며, 사용자는 `종료됨`으로 응답했다.
설치·원본 전수 검산·전체 백업은 반복하지 않았다.

- 원래 실행 `runtime-close-94b3c15ea12b`의 종료 코드 0, guard PASS·오류 없음.
- 서버 결과 `R575b518825b1`, result SHA256
  `c313c949a8836ac6d7c4d18366950c5ca91966d74b112c6eedf4c5957ff88cd6`.
- 보유 native handle로 확인한 backend·Electron 5개 프로세스 모두 실제 종료 코드 0,
  강제 종료 없음. backend 종료는 09:04:16.8118840 UTC다.
- `recover_observer_r2.py`와 `review_candidate_close.py` 모두 종료 0.
  9개 결과 파일의 해시와 내용, 현재 CSV의 sample_seq 1–3,047 연속성을 확인했다.
  순번 누락·중복은 없으며, valid 3,026행과 startup_pending 21행을 구분해 보존했다.
  startup_pending 행을 유효 온도 측정값으로 간주하지 않는다.
- 독립 검토 상태 `LIMITED_RUNTIME_CLOSE_RECEIPTS_VERIFIED`는 현재 CSV와 정상 종료의
  제한된 확인이다. 이미지 바이트·수신/저장 전체 대응·worker 종료 영수증 QA를 대신하지 않는다.
- 검토 및 공유 보관:
  `C:/Users/user/Desktop/SmartFactory/C31CLOSE_20261022_b1d4a5f6/recovered-runtime-close-94b3c15ea12b`,
  `Z:/SmartFactory/20261022/return/C31CLOSE_20261022_b1d4a5f6/recovered-runtime-close-94b3c15ea12b`.

실제 닫힌 C31 metadata와 기존 USER_SELF·프로파일 승인을 결합한 AT31 10파일을
준비했다. 치환된 실제 controller와 helper를 검토하고 native PowerShell 5.1 x64
구문 검사 2개가 종료 0인 것을 확인한 뒤, 새 서버 폴더에 전달·전체 해시 검산했다.
적용과 회수 모두 종료 0이다. 서버 결과는 `A4e537c18`, result SHA256은
`5ce637843bfdc5dbb110df49413ab606e36882bd04fb28ff060e6cad4075b13a`다.

`config_operator_verified`, `config_verified_at`, `config_verified_by`,
`config_verified_fingerprint_sha256` 네 확인 항목만 갱신했다. 회수한 6개 영수증과
설정 전후 내용을 비교하여 나머지 설정이 그대로임을 확인했다. 장비·수집 설정은
변경하지 않았다. 쓰기 실패 복구용 설정 파일 1개만 기존 도우미가 보존했으며,
전체 데이터 백업은 추가하지 않았다. 새 config SHA256은
`e9792bfa97ee5dd3f60a7a24a796d443a50bf3c3965c7b940ad719a01b847e12`다.

### 재시작과 현재 수집 상태

승인된 일반 사용자 실행과 결과 회수, 준비 상태 조회 및 실제 runtime 대조 모두 종료 0이다.
서버 실행 영수증 `ST31_e5b547e9`의 5파일을 검토했으며 result SHA256은
`2082d0a305b0777613d8181f743246a881c586883157409f772ada4ec6eec165`다.
임시 실행 작업 정의는 제거됐고, 앱 프로세스를 중단하는 호출은 없었다.

- main PID 20148, backend PID 9888, Electron 자식 포함 모두 세션 3·일반 사용자 권한.
- 1.0.31/a7e5149b, REAL·Running, 새 logger
  `08e3a608-ba3e-4a1c-929b-894644b196ed`와
  `Factory_Integrated_Log_v2_20261022_180746.csv` 확인.
- 기존 운영자 입력 21152·4/valid=true 유지. 임의 재입력 없음.
- 실제 runtime의 승인 설정 fingerprint
  `28f7e06202bd46696dd33a5a87e72d23c57512d318760cb94fa3f983d8583d0f`를 재계산·대조했다.
  `config_attestation_status=verified`, drift 없음. 검토 범위는
  `SOFTWARE_REPRESENTED_APPROVED_FIELDS`다. 장비 직접 readback은 `not_supported`,
  물리 경계 시험은 `NOT_TESTED`이며 Low Signal은 계속 OFF다.
- 09:13:55 UTC 읽기 확인에서도 같은 프로세스 세대와 설정을 유지했다.
  수신 관측 기록 accepted/completed 각 366, 거부·쓰기 오류·대기 0으로 보고됐다.
  이는 해당 시점 카운터이며 파일 전수 대조·성능 통과를 뜻하지 않는다.
  CSV 상태는 startup_pending·valid·under_range를 구분해 기록 중이다.

이번 정상 종료 직전 마지막 행 18:04:15.910410 KST와 재시작 첫 행
18:07:46.875922 KST 사이의 서버 wall-clock 차이는 210.965512초다.
`attestation-maintenance-gap.json`에 이 점검 구간을 기록했다. 그동안 수집하지 않은
센서 값을 복원했다는 뜻은 아니며, 새 실행 첫 행은 startup_pending이다.

현재 앱은 실행 중이다. 재시작 이후의 대시보드·작업 정보 표시와 전면 상태는 사용자에게
확인을 요청했으며 아직 응답 전이다. 앞서 받은 첫 실행의 화면 확인을 재시작 후 확인으로
재사용하지 않는다. 새 버전의 해당 현장 관찰·이미지/저장 대응 QA, 실제 3대 PC 조회와
물리 경계 시험은 별도 미완료다. 기존 240a의 120분 결과를 C31 통과로 바꾸지 않는다.
전체 출시와 운영 승격은 HOLD를 유지한다.

근거: `F31CLOSE_20261022_b1d4a5f6` 아래 `attestation-package-review.json`,
`attestation-apply/review.json`, `after-attestation-start/start-review.json`,
`attested-candidate-runtime/review.json`, `attested-candidate-runtime/configuration-review.json`,
`postrestart-status/current.json`, `c31-close-attestation-restart-stage.json`.

## 재시작 후 화면 확인과 15분 관찰 시작

사용자가 재시작한 대시보드·작업 정보 표시와 전면 상태 확인 요청에 `네`로 응답했다.
현재 앱을 그대로 두고, 새 설치본·실제 프로세스 생성 시각·승인 설정에 결합한
`operational-observe` 900초 관찰을 시작했다. 이미지 UI 연속성이나 실제 3대 PC 시험과는
구분하며, 이 관찰의 수집·세대결합 결과를 전체 운영 성능 통과로 확대하지 않는다.

- 입력: `C:/Users/user/Desktop/SmartFactory/O15C31_20261022_b1d4a5f6`.
- 기존 검산된 RUN31과 SSH 연결 중단 시 진단 자식만 정리하는 guard를 재사용했다.
- 소스 116개·실행 묶음 8개를 검산하고 실제 요청 소비 코드의 정상/거부 5조건을 확인했다.
  실제 guard 결합의 native 구문 검사와 서버 ValidateOnly도 종료 0이다.
- 5파일·14,160바이트만 새 서버 폴더에 전달·검산했다. 로컬 전달 코드 준비 때 치환 개수
  검사 1건이 실패했으나 서버 실행 전 중단됐으며 실제 소스에 맞춰 수정한 뒤 준비를 마쳤다.
- request SHA256 `a5b09b6cc0f0c73b86cb18b470582ec41ff7ea6e1d279394de445c500aac4919`.
- 원래 실행 `observe15-477f3495c613`, 서버 guard `G9689c4ecc399`,
  측정 결과 경로 `run-5316c2c38f50`. 측정 원점 `origin_ns=1073990138345900`.
- 09:23:46 UTC 읽기에서 실제 측정 약 122초까지의 기록과 같은 앱 세대를 확인했다.
  원래 실행은 아직 진행 중이며, 종료·회수·원시 기록 재계산 전에는 통과로 표시하지 않는다.

화면은 작업자에게 보이는 상태로 유지한다. 관찰 중 앱 종료·설치·설정 변경·전체 백업은
하지 않는다. 기록이 정상 종료된 뒤 콘솔 해시, 파일 manifest, 요청·설정 결합과 원시 HTTP·
자원 요약을 다시 검토한다. 지연의 200/500ms 참조 초과는 그대로 기록한다.

## 15분 관찰 검산 완료와 120분 관찰 재개

15분 원래 실행의 종료 코드 0을 확인하고 `recover_observation.py`와
`review_observation.py --minutes 15`를 실행했다. 두 명령 모두 종료 0이며,
회수한 1,596파일과 콘솔 launcher SHA256
`3ef29b0f3ec662b5ddfedba533e9f4418efbd75a3c0fdf7559c56029fbc7ad64`를 검산했다.
기록 manifest의 1,591파일과 원시 HTTP·자원·결합 요약 재계산이 일치했다.
`review.json` SHA256은 `411aec2606a55635acc73cf954d9ae5b064d34dfd78e4f1942af259837db5e7e`다.

| 관찰 항목 | 확인 결과 |
| --- | --- |
| `/health` | 정규 450건과 첫·마지막 2건, 총 452건. 오류·타임아웃·측정 누락 0, 최대 78.2129ms |
| `/api/data` | 150건, 오류·타임아웃·측정 누락 0, 최대 65.5473ms |
| 자원·프로세스 | 181/181회, 관찰 구간 누락 0, 같은 앱 실행 세대 유지 |
| 판정 범위 | `COLLECTION_AND_BINDING_ONLY` PASS. 운영 성능 요구 충족·이미지 연속성·전체 데이터 완전성은 별도 미평가 |

200/500ms 참조 초과도 이번에는 0이다. 이는 새 임의 합격 기준을 확정한 것이 아니다.
원시 결과 tar와 검토·진단 영수증 104파일을
`Z:/SmartFactory/20261022/return/O15C31_20261022_b1d4a5f6`에 검산·보존했다.

첫 120분 실행 `observe120-a2df3b3b8699`는 `observation-connection-lost`로 중단됐다.
서버 guard `G89a57b33ed8e`의 실제 종료 코드 1·진단 자식 잔여 0을 확인했다.
관찰 기록은 약 46초만 남았으며 `run-3ae5d23123c9`의 177파일과 guard 6파일을
인증된 SSH로 회수해 전 파일 해시를 대조했다. 원래 SSH 종료 코드는 확인할 수 없어
null로 남겼다. 결과는 검증 미완료이며 앱 실패나 120분 통과로 기록하지 않는다.
중단 전후 앱 main20148/backend9888의 생성 시각은 동일했다.

정리 완료·동일 앱 세대·설정·입력 해시와 서버 사전 검사를 확인한 뒤, 같은 검증 바이트를
재사용해 `O120C31R2_20261022_b1d4a5f6`에서 새 관찰 한 번을 시작했다. 앱 종료·설치·
설정 변경·전체 백업은 하지 않았다. 첫 실행과 새 실행의 측정 시간을 합산하지 않는다.

- 새 실행: `observe120-c3ca6691b19b`, 서버 guard `Gd0195cd2ab0d`.
- 새 결과: `run-33f6823fb025`, `origin_ns=1081599179959500`, 예정 측정 7,200초.
- 11:29:10 UTC 서버 읽기에서 실제 측정 약 36초와 살아 있는 guard를 확인했다.
- 다음 단계: 원래 실행 종료 확인 → 결과 회수·해시 검산 → 원시 기록 재계산.
  완료 전까지 120분은 진행 중으로 유지한다. 출시·운영 승격은 계속 HOLD다.

## 2026-10-23: C31 120분 원시 검산 완료와 자정 CSV 전환

`observe120-c3ca6691b19b`의 원래 실행이 종료 코드 0으로 끝났다. 실행을 다시 시작하지
않고 실제 terminal, 서버 guard의 PASS·종료 0·잔여 프로세스 0과 콘솔 해시를 확인했다.
`recover_observation.py` 및 `review_observation.py --minutes 120` 모두 종료 0이다.
회수 12,516파일(60,281,627바이트), session manifest 12,511파일의 검산과 HTTP·자원·결합
요약 원시 재계산이 일치했다. 첫·마지막 경계 기록은 한국 시간 10월 22일
20:28:30.270243 / 22:28:34.366050이며 요청의 측정 기간은 7,200초다.

| 항목 | 실제 결과 |
| --- | --- |
| `/health` | 정규 3,600건 + 경계 2건. 오류·타임아웃·예정 측정 누락 0. 최대 210.2077ms, 200ms 참조 초과 2건, 연속 초과 최대 1건 |
| `/api/data` | 1,200건. 오류·타임아웃·예정 측정 누락 0. 최대 186.4545ms, 500ms 참조 초과 0건 |
| 자원·프로세스 | 1,441/1,441회, 미측정 구간 0, 동일 앱 실행 세대 유지 |
| 검산 범위 | `RECORDED_SUMMARIES_REPRODUCED`, `COLLECTION_AND_BINDING_ONLY` PASS, 새 정책의 request_status PASS |
| 별도 미완료 | 운영 성능 요구 충족, 이미지 표시 연속성, 저장 완전성·물리 샘플 완전성, 정식 QA·운영 승격 |

이전 단일 지연 기준의 health `legacy_status=FAIL`과 초과 원시값은 유지했다. 변경 승인된
`operational-evidence-v2`에 따라 이를 자동 전체 운영 실패로 사용하지 않으며, 반대로
수집·세대 결합 PASS를 전체 운영 성능이나 출시 PASS로 확대하지 않는다.

- launcher SHA256: `45075cdf26befd63bdaf5e7d6dfdd265401905c1d8f243264d152232c1a58092`
- review SHA256: `591afea47a55f7418305ffe22abda0be978369212d7fa201db369901fccdf4ce`
- 원시 tar: 71,690,240바이트, SHA256 `316cb14dc49ad8525204ac18a47a29e56637a2ae96ebb9cea4e424bf0274c309`
- 근거: `O120C31R2_20261022_b1d4a5f6/recovery.json`, `review.json`, 원래 launch terminal 및 guard 반환 기록.

00:37:52의 읽기 확인에서 main20148/backend9888의 생성 시각과 logger/service는 그대로이며
현재 CSV는 `Factory_Integrated_Log_v2_20261023_000000.csv`, 첫 순번은 90211이다.
설정 SHA256도 유지됐다. 제품번호 21155·금형번호 3은 API에서도 유효하게 확인됐으며,
이전 미입력 구간은 소급해서 채우지 않는다. 이후 같은 값을 다시 적용한 시각은 당시
원시 기록대로 별도 보존한다.

기존 `C31POST120_20261022_b1d4a5f6` 종료 준비는 22일 CSV에 결합돼 있어 서버에 실행하지
않았다. 다음 단계는 현재 23일 CSV에 맞춘 새 정상 종료 관찰 준비와, 관찰이 포함된 22일
파일까지 함께 보존·대조하는 것이다. 자정 전환 때문에 120분 관찰을 반복하지 않는다.
추가 기록만 읽는 도구와 참조 대조 검사 12개는 개발 PC에서 종료 0으로 확인했지만,
현재 데이터의 전체 CSV 소비자·이미지 실파일 검사와 자정 양쪽 파일 검산은 아직 미완료다.
앱은 계속 실행 중이며 설치·설정 변경·전체 백업은 하지 않았다. 출시·운영 승격은 HOLD다.

## 2026-10-23: 자정 양쪽 파일 회수·정상 종료·일반 실행 복귀

위 준비 이후 `C31DAY_20261023_7c82a9f0`의 새 v7 요청으로 23일 CSV를 결합했다.
4파일 10,702바이트를 공유 및 서버 최종 경로에 전달·검산했고 ValidateOnly는 종료 0이다.
guard `Gae3fbe379c9a`의 실제 READY를 확인한 뒤 Chrome 원격 데스크톱의 Smart Factory에
Alt+F4를 전달해 정상 종료했다. 강제 종료나 설치·설정 변경·전체 백업은 하지 않았다.

- 관찰 실행 `runtime-close-7f321a1d1731`: 종료 0, guard PASS, 잔여·강제 종료 0.
- 결과 `Ra16dcf823a92`: SHA256 `39be31462bd5ca8a9c0850056d36a1d3f5115e4075711a6bc1efdfe61220c5c1`.
- 실제 앱 프로세스 5개가 모두 정상 종료 0. 10개 필수 저장·서비스 종료 단계가 확인됐다.
- 22일 CSV 90,210행(1–90,210)과 23일 CSV 15,606행(90,211–105,816)의 순번이 연결된다.
  합계 105,816행이며 파일 경계의 순번 누락·중복은 0이다. 이는 전체 실행 건수이며 120분만의 건수가 아니다.
- 자정 전 파일의 observation manifest는 정상 종료 후 확정됐다. 이미지의 원래 open-time
  `image-persistence-pending-at-open` 표시는 보존하고, 별도 final image manifest와 worker 종료 기록으로 대조한다.
- 누적 ledger 전체를 재전송하지 않고 기존 검산 prefix와 추가 297,167,123바이트를 결합했다.
  두 ledger의 최종 전체 SHA256·행 수가 마감 manifest와 일치하고 현재 service만 추출했다.
- 수신 기록 24,784건, CSV의 참조 105,798건 중 서로 다른 수신값 참조 24,431건,
  반복 참조 81,367건이다. 참조 없는 CSV 18행과 CSV에 연결되지 않은 수신 기록 353건도
  그대로 기록한다. 후자는 별도 fact에 보존되어 있으며 이를 장비 샘플 손실로 해석하지 않는다.
- 수신 기록의 raw validity는 valid_temperature 21,726건, invalid_sentinel 3,058건이다.
  제품·금형 정보가 비었던 CSV는 24,931행이며 소급 입력하지 않았다. 학습용 데이터의
  유효값 선별·제품 귀속·최소 변화 시간 충족은 별도 판단이며 학습 적합성 PASS가 아니다.
- worker 보고 이미지 등록·저장 23,022건, 미저장·실패·drop 0. 이미지 실파일 전체 검사 완료 전에는
  이 보고만으로 실파일 완전성이나 화면 연속성 PASS를 선언하지 않는다.

종료 자료를 회수한 후, 대상과 빈 인수를 검산한 기존 `SmartFactory-normal.lnk`를 원격 화면에서
실행했다. 새 logger `77f1d84c-0286-4dbc-a7cf-3b49482fc555`, CSV
`Factory_Integrated_Log_v2_20261023_010622.csv` 첫 순번 1, 일반 사용자 권한과 기존 config SHA가
확인됐다. 다음 읽기에서 순번 416→2,274 증가와 진단 인수·19221 listener 부재를 확인했다.
화면은 Running·21155/3 적용·카메라 표시·전면 상태다. 작업자가 00:57:51에 다시 입력한 값을
보존했으며, 00:55:58의 자동 초기화 구간을 과거 값으로 채우지 않았다.

JPEG 실파일 검사는 23,022개, 184,427,182바이트 전부 통과했다. 복사 누락·크기/해시 불일치·
디코딩 문제·선택한 사본 트리의 orphan은 0이다. 고정 이미지 소비자와 외부 실행기의 종료는 모두 0,
잔여·강제 종료 0이며 입력 잠금 해제 전 재검산과 출력 파일 해시까지 확인했다.
`verify_images_and_drain.py`도 종료 0이다. 화면 표시 연속성과 장비 원시 샘플 완전성은 이 판정 밖이다.
입력·재시작 영수증 74파일 480,181,212바이트와 이미지 검사 영수증 33파일 34,627,257바이트를
공유 return의 각각 `closed-data-inputs`, `image-check`에 전 파일 검산해 보존했다.

현재 개발 PC에서 두 날짜의 고정 CSV 상세 소비자가 실행 중이다.
입력 ledger는 로컬 검증 작업 공간 한 벌로 공유하고 두 CSV의 원본 metadata는 각각 보존한다.
CSV 검사 프로세스의 최종 종료·출력 검산 전에는 해당 상세 검사를 미완료로 유지한다.
원래 실행은 `csv-owned`이며 두 날짜를 순서대로 검사한다. 이전 같은 유형의 누적 CSV 검사는
5,061.547초가 걸렸으므로 이번 처리 시간을 120분 관찰의 연장이나 새 관찰로 표현하지 않는다.
관련 근거는 `C31DAY_20261023_7c82a9f0`의 `post120/closed-delta-review.json`,
`worker-closure/verification.json`, `images-and-drain-verification.json`, `normal-return/review.json`,
`normal-return/normal-mode-confirmation.json`이다. 최종 원격 화면에서 앱 최대화·전면·21155/3 적용을 확인했다.

검증 도우미의 준비 실패도 보존한다. 첫 공유 복사는 새 날짜의 send 부모가 없어 서버 전달 전에
중단됐고 부모 생성 후 전달했다. worker 회수도 로컬 결과 부모 생성 전에 중단돼 부모를 준비한 뒤
진행했다. rolled CSV 검사기의 초기 가정과 달리 완료 시 observation closeout 표시는 제거되고
manifest로 대체되므로 실제 필드와 전체 해시를 대조했다. 이미지 R1은 한국 날짜와 UTC 저장 경로를
같게 가정해 서버 읽기 전에 중단됐으며, 실제 manifest의 22일 경로만 사용하는 R2가 종료 0으로 완료됐다.
이 준비 실패를 제품 실패나 기술 QA 통과로 바꾸지 않는다. 출시·운영 승격은 HOLD다.

## 기존 C31 시작 3회 대조 — 추가 재시작 없음

2026-10-23 01:34 KST 후속 점검에서 서버의 제한된 Electron 로그 4개를 읽고,
동일 C31 build의 실제 시작 3회를 native 생성 시각과 종료/읽기 범위로 연결했다.
각각 필수 milestone 9개·backend progress 9개가 있다. 앱 내부 대시보드 준비 시간은
17:52 실행 16,567.8ms, 18:07 실행 8,528.3ms, 01:06 실행 8,774.8ms다.
앞 두 실행은 5개 프로세스의 정상 종료 0, 마지막 실행은 Running으로 구분한다.

첫 실행은 운영자 확인 네 항목 갱신 전이다. 세 실행을 동일 설정·캐시 조건의 반복 시험이나
외부 stopwatch 측정으로 해석하지 않는다. R2 전체 시작 성능 계약은 NOT_EVALUATED로 유지한다.
보존된 시작을 확인했으므로 이 증거 대조를 위해 추가 종료·시작을 하지 않았다.
읽기·해시/세대 결합 검산·구문 검사·Ruff F/E9는 종료 0, 분석기 경계 확인 7개는 통과했다.
[시작 대조 기록](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/startup-coverage/review.md)과
[원시 근거 결합](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/startup-coverage/review.json)에
범위와 차이를 기록했다. 원래 두 날짜 CSV 상세 검사와 전체 출시 HOLD는 유지한다.

### 01:38 KST 운영 화면 재확인

Smart Factory는 최대화·전면·Running이고 카메라 화면도 표시됐다. 작업자 입력 21155·3은
00:57:51 이력으로 보존돼 있으나 현재 필드는 01:27:20에 다시 비워졌다.
읽기 전용 API의 `source=auto_count_transition_to_zero`를 확인했다. 현재 작업 상태를
추정해 다시 입력하지 않았으며 이전 누락 구간도 수정하지 않았다. 같은 logger
`77f1d84c-0286-4dbc-a7cf-3b49482fc555`에서 sample_seq 8,288을 읽었다.
근거: `C31DAY_20261023_7c82a9f0/operator-state-check/current.json` 및 해당 SSH 종료 0.
현재 작업 정보의 재입력과 이미 닫힌 실행의 CSV 상세 검사는 별개다.

동시에 읽은 port8000 연결 표본에는 loopback 연결 3개만 있었다. 실제 3대 PC 접속이나
평소 외부 조회가 없다는 증거로 해석하지 않는다. 3대 PC의 식별·화면/네트워크 조건은 미확정이다.

## C31 정식 QA 선행 조건 확인

같은 clean commit의 `qa_spot_temperature_v25.ps1`와 외부 SHA에 연결된 닫힌 23일 metadata를
대조했다. 확인한 metadata 조건 9개 중 운영자 확인·attestation·drift·fingerprint·readback 정책·
fact 활성·쓰기 실패·미저장 spool의 8개는 충족한다. `low_signal_comparator_verified=false`는
원래 도구의 true 조건을 충족하지 않는다. 이는 [선행 조건 검토](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/formal-qa-readiness/review.md)이며
one-command QA 실행이나 전체 QA PASS가 아니다. 기존 도구는 미충족 조건이 있으면 FAIL을
생성하므로 같은 조건에서 앱 종료와 QA를 반복하는 대신 실제 comparator 증거가 필요함을 기록했다.

읽기 검산 R2와 Ruff F/E9는 종료 0이다. 초기 검토기의 spool 필드명 오류(exit1)는 보존하고
원래 도구·metadata의 `spool_pending_count`로 바로잡았다. 서버·앱·설정은 변경하지 않았다.
두 날짜 CSV 상세 검사는 원래 실행을 유지하며, 그 완료가 물리 미시험이나 정식 출시 보류를 해제하지 않는다.

## 최초 C31 실행의 자료 범위 추가 확인

120분 대상 실행 외에, 최초 logger `cea865b7-e83c-41ab-86e9-3ff1627806f5`의 3,047행도
별도로 확인했다. 최초 닫힌 observation prefix에 연결된 수신 기록 721건과 CSV 참조 3,026건을
대조해 참조 누락·payload 충돌·관찰 순번 gap 0을 확인했다. 반복 참조 2,316건과 참조 없는
CSV 21행은 원문대로 보존한다. 이는 고정 CSV 상세 소비자 전체 검사를 대신하지 않는다.

당시 worker의 이미지 등록·저장 655건과 정상 종료 기록을 연결했고, 실제 JPEG 655개
(4,997,948바이트)의 해시·디코딩 검사 및 후속 검산이 모두 종료 0이다. 실패·drop·잔량은 0이다.
원래 최초 실행의 최종 이미지 manifest는 회수되지 않았다. 이후 확정된 누적 ledger에서 해당
service만 선택한 근거이며, 원래 metadata의 pending 표시나 첫 설정 fingerprint_mismatch를
고치지 않았다. 최초 CSV 상세 검사·학습 적합성·전체 출시 판정은 미완료다.
[범위·근거·한계](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/initial-run/review.md)를 연결한다.

02:02 KST 원격 화면에서 앱의 Running·최대화·전면·카메라 표시를 다시 확인했다. 21155·3은
00:57:51 입력 이력에 있으며 현재 필드는 여전히 01:27:20 초기화 이후 미입력이다. 임의 재입력하지 않았다.
원래 CSV 실행에서 22일 90,210행의 상세 소비자는 종료 0·PASS(3,076.078초)이며,
23일 15,606행을 이어서 검사하고 있다. 전체 실행 최종 종료 전에는 두 파일 검사 완료로 표시하지 않는다.

최초 CSV의 상세 소비자 입력도 별도로 준비했다. 당시 observation prefix 869,663행을
원래 SHA256으로 재구성하고, 이후 닫힌 누적 이미지 ledger는 기존 사본을 재사용했다.
새 입력 3파일은 1,014,286,637바이트이며 이미지 2,436,250,968바이트를 다시 복사하지 않았다.
준비·고정 입력 잠금/해제 검산과 Ruff F/E9는 종료 0이다. 원본 metadata의 경로 외 필드는
변경하지 않았고 원래 이미지 마감 파일 회수는 계속 미완료다. 기존 두 날짜 최종 검산이 끝난 뒤
실행하도록 선행 조건을 둔 [최초 CSV 검사 준비](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/initial-run/csv-preparation-review.md)이며,
준비 성공을 소비자 실행·CSV PASS로 바꾸지 않는다.

## 교체 직전 1.0.30 실행의 누락된 상세 범위 확인

120분 대조가 끝난 1.0.30 실행과 별개로, logger `a3b807df-da24-4928-a899-ddeb79468923`의
마지막 실행을 추가 확인했다. 20·21일 CSV/metadata 4파일 591,191,254바이트를 읽고 설치 전
보존 목록 SHA256과 대조했다. 22일 사본과 기존 ledger prefix/tail은 재사용했다.

CSV는 59,984 + 372,358 + 239,639 = 671,981행이며 순번 1–671,981이 날짜 경계까지 이어진다.
참조 671,967회에 대해 누락된 수신 기록·원시 payload 해시 충돌은 0이다. 수신 기록 155,807건 중
CSV 미참조 2,010건(유효 온도 1,824, invalid_sentinel 186)은 ledger에 보존돼 있다. 반복 참조
518,170회를 고유 센서 샘플로 계산하지 않는다. 제품번호 또는 금형번호 미입력 80,335행은
원문대로 보존하며 제품별 학습·품질 분석의 귀속 정보가 충분하다고 판정하지 않는다.

이미지 ledger 144,190건과 worker의 등록·저장 건수가 일치한다. 종료 잔량·실패·drop 0,
필수 단계 10개와 native 프로세스 5개의 정상 종료 0을 연결했다. 이는 실제 JPEG 144,190개의
파일 해시·디코딩 검사나 고정 CSV 상세 소비자 PASS가 아니다. 두 검사는 계속 NOT_EVALUATED다.
원래 이미지 최종 manifest는 회수되지 않았지만 닫힌 이미지 ledger 전체 바이트는 설치 전
목록의 SHA256과 일치했다. 원래 1.0.30 metadata에 없는 closeout 필드를 추가하지 않았다.

분석 R2·Ruff F/E9·근거 149파일 및 출력 재검산은 종료 0. R1의 보고서 작성 중 필드 부재 오류
(exit1)는 보존했다. [상세 범위와 근거](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/prior-c30/review.md)를 연결한다.
진행 중인 C31 CSV 분석을 재시작하지 않으며 이 결과로 R4 전체나 출시를 PASS로 바꾸지 않는다.

02:38 KST 원격 화면은 Smart Factory 최대화·전면·Running·카메라 표시 상태였다. 작업자
21155·3 입력은 00:57:51 이력으로 확인되며 현재 필드는 01:27:20 이후 미입력이다.
운영 설정·작업 정보·원본은 변경하지 않았다. 상태표의 오래된 120분 실행 중 표시는 완료 기록으로
구분하고 실제 실행 중인 로컬 CSV 분석으로 정정했다.

## C31 120분 대상 실행의 두 날짜 CSV 상세 검사 완료

2026-10-23 02:46 KST에 원래 실행 37501이 정상 종료했다. 22일 90,210행과 23일 15,606행,
합계 105,816행의 고정 CSV 상세 소비자가 모두 PASS·exit0이다. 처리 시간은 각각
3,076.078초와 2,795.063초다. 23일 출력 전체와 stderr 0바이트, 두 날짜의 입력 잠금/해제 전
해시 대조·출력 결합·실제 프로세스 종료를 확인했다. 잔여·강제 종료 0이며
`verify_csv_suite_completion.py`도 종료 0이다. 결과 29파일 184,512바이트를 공유 return의
`post120-csv-check`에 파일별 검산해 보존했다.

[완료 결합 기록](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/csv-completion-verification.json)을
기존 JPEG 23,022개 및 worker/native 종료 검산에 연결한다. 참조 가능한 CSV 105,798행의
수신 기록 연결 100%, 참조 누락 0이며 원래 참조 없는 18행과 작업 정보 누락 구간은 보존한다.
범위는 닫힌 실행의 CSV/fact 내용이다. v1 대조는 metadata상 비활성으로 요청하지 않았으며,
장비 원시 샘플 완전성·학습 적합성·실제3PC 화면·물리 경계·전체 데이터 판정은 이 PASS 밖이다.

02:47 KST에는 선행 조건 완료 후 최초 C31 CSV 3,047행의 준비된 검사를 한 번 시작했다.
실행 1993, driver 56284의 입력 재검산 완료와 실제 소비자 시작을 확인했다. 결과는 아직
미완료이며 기존 실행을 재시작하지 않는다. 이후 원래 관측 prefix/이후 누적 이미지 사용 범위와
최초 원본 이미지 manifest 미회수를 그대로 표시하고 최종 종료를 검산한다.

교체 직전 1.0.30 자료의 별도 보존도 완료됐다: 57파일 889,925,821바이트를 공유 return의
`prior-c30-reference-check`에 검산했다. 이는 이미 확인한 범위의 증거 보존이며 그 구간의
고정 CSV 상세 검사·JPEG 실파일 검사를 완료했다는 뜻은 아니다. 전체 출시·운영 승격은 HOLD다.

02:49 KST 최종 화면에는 02:43:11의 21155·10 입력 이력이 새로 나타났고, 현재 필드는 02:45:24 이후 미입력이다. 이 최신 초기화의 원인은 화면만으로 확정하지 않는다. 앞의 01:27 API 확인과 구분해 `operator-state-check/screen-20261023-0249.json`에 기록했다. 임의 재입력 없이 Running·최대화·전면·카메라 표시를 확인했다.

## 1.0.30 추가 상세 검사 준비와 이미지 실파일 읽기 시작

671,981행의 원본 CSV 3개와 metadata/관측 prefix의 입력 준비를 마쳤다. 필요한 7파일은
1,928,391,113바이트이며 누적 이미지 ledger 2,436,250,968바이트는 기존 사본을 재사용했다.
세 날짜의 고정 `CsvInputs` 선행 검사·입력 해시·원본 경로 외 필드 보존·해제 전 검산은 모두 PASS,
준비 R2와 Ruff F/E9는 exit0이다. 고정 CSV 내용 소비자 3회는 아직 실행하지 않았다.

현재 최초 C31 CSV 실행 1993은 실제 프로세스가 살아 있음을 확인했다. 완료·검산 후 준비한
1.0.30 세 날짜 소비자를 순서대로 시작한다. 두 날짜 C31 105,816행의 완료 검산은 재사용한다.

03:00:58 KST에 구버전 실행의 이미지 144,190개(기록 크기 1,339,924,746바이트) 읽기/검사
실행 9365를 시작했다. 서버 신원·경로·reparse·닫힌 manifest 검산을 통과했고 지정 파일
SFTP 읽기가 실제 진행 중이다. 처음 655개 및 이후 C31 23,022개와 경로 중복은 0이다.
파일 수에 맞게 읽기/소비자 각각 3,600초, 전체 owned 실행 9,000초를 배정했다. 내용·경로·
해시·디코딩 합격 기준은 유지하며 읽기 진행을 전체 이미지 PASS로 표시하지 않는다.

앞선 closeout 필드 부재 설명은 마지막 22일 metadata에 해당한다. 추가 검사에서 20일에는
미완료 마감 표시가 있고 21·22일에는 해당 필드가 없는 차이를 확인했다. R1 준비는 이 차이를
하나로 가정해 exit1로 끝났고, R2는 각각의 원래 바이트를 보존하며 이미 만든 입력 3개를
재사용했다. 이 준비 오류를 제품 데이터 실패로 바꾸지 않는다. 원래 이미지 최종 manifest의
미회수와 이후 누적 image ledger를 사용하는 고정 CSV 검사 범위는 그대로 유지한다.

[준비·진행 범위와 해석](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/prior-c30/qa-preparation-review.md),
준비 증거 32파일 190,055바이트는 공유 `prior-c30-qa-preparation`에 검산해 보존했다.
제품 코드·설정·설치·전체 백업은 변경하지 않았다. 실제 종료 뒤 각 완료 검산을 수행하며
물리 경계·실제 3대 PC·전체 자료/학습 적합성·운영 승격은 계속 미완료다.

## 10월 22일 설치 전 이미지 목록 역방향 대조 완료

10월 23일 추가 검토에서 보존된 두 AppData 루트의 파일 420,563개 중 이미지 419,520개를
당시 닫힌 이미지 대장 4,730,776행과 대조했다. 이미지 전부가 경로·크기·SHA256으로 연결됐고,
연결되지 않은 파일·크기/해시 차이·대응 경로 중복은 각각 0개다. 직전 1.0.30의 144,190개도
모두 그 목록에 포함됐다. 현재 서버를 다시 전수 읽거나 디코딩한 결과로 확대하지 않는다.

대장 4,311,256행은 그 고정 목록에 없다. 과거부터 누적된 행 수이며 고유 소실 파일 수,
현재 전역 부재나 보존 기간에 따른 정상 삭제로 단정하지 않는다. 원인·다른 사본의 증거는
별도 조건이다. 원래 이미지 최종 manifest 미회수와 전체 R4/출시 HOLD도 유지한다.

[전체 범위·실패와 수정·검사 결과](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/prior-c30/reverse-inventory-review.md).
최초 도구는 과거 하위 경로를 처리하지 못해 exit1이었다. 실패본을 보존하고 안전한 과거 경로를
허용한 R2의 11개 검사·Ruff·실제 전체 대조·합계 검산은 모두 exit0이다. 증거 6파일
39,629바이트를 공유 `prior-c30-inventory-check`에 SHA256 대조 후 보존했다.

03:25 KST 재확인에서 최초 C31 CSV 실행 1993과 이전 C30 이미지 실행 9365의 실제 PID·생성
시각이 같고 CPU/IO가 증가했다. 같은 실행을 유지하며 완료 검산 후 다음 소비자로 이어간다.
원격 화면 재연결 후 03:22 KST 화면은 Running·전면·카메라 표시·작업 정보 OK였고,
21155·10이 03:18:29에 적용된 상태였다. 과거 사용자 보고 21155·3은 이력으로 보존하며
Codex가 현재 값을 변경하거나 과거 누락을 채우지 않았다.

## 설치 전 이미지의 기존 디코딩 증거 재사용 검산

2026-10-23 03:47 KST에 고정 목록 419,520개를 중복 없이 분할하고 파일별 근거를 검산했다.
기존 정상 디코딩 증거 155,901개와 UIQA 추가 1,147개, 합계 157,048개를 정확한 크기·SHA256으로
연결했다. 원래 분할 기록의 증거 행을 독립적으로 재검산했으며 실패한 NAS 기록 3개는 제외했다.
다른 파일명에 같은 내용이 있는 경우 내용의 디코딩 결과만 재사용하며 캡처·생산 귀속을 추론하지 않는다.

현재 실행 9365의 144,190개는 SFTP 회수 exit0과 전체 크기·해시 일치를 확인했다. 디코딩 소비자와
입력 해제 후 검산은 아직 완료되지 않았다. 나머지 118,282개(1,132,418,304바이트)는 연결된
디코딩 증거가 없으며 다른 기존 근거 또는 실파일 검사가 필요하다. 날짜별 수량은 10/17 54,397개,
10/18 4,269개, 10/19 59,107개, 10/20 509개다. 모든 증거 위치를 소진했다고 판정하지 않는다.

분할 도구의 6개 검사, 원래 분할 실행, 독립 검산 실행, 각 Ruff E9/F는 exit0이다.
[검산 결과와 범위](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/prior-c30/decode-coverage-review.md)
및 증거 12파일 91,391,042바이트를 공유 `prior-c30-decode-coverage`에 파일별 검산해 보존했다.
최초 C31 CSV 실행 1993과 이전 C30 이미지 실행 9365는 같은 PID·생성 시각으로 진행 중이다.
전체 R4·원시 샘플 완전성·학습 적합성·출시는 HOLD이며 기존 실패와 공백을 보존한다.

03:43 KST 서버 화면은 Running·최대화·전면·카메라 표시 상태다. 작업 정보는 03:43:00 이후
다시 필수값 미입력이며 이전 21155·10과 21155·3은 이력으로 남아 있다. 화면만으로 초기화 원인이나
생산 여부를 판단하지 않았고 운영 설정·현재 작업 정보·과거 누락을 변경하지 않았다.

## 최초 C31 CSV와 이전 C30 이미지 검산 완료, 남은 검사 시작

최초 C31 CSV 실행 1993은 2026-10-23 04:02:56 KST에 정상 종료했다. 고정 소비자는
3,047행 PASS·exit0, 참조 3,026행의 수신 기록 연결 100%·누락 0이다. 전체 stdout 5,950바이트와
빈 stderr, 입력 잠금/해제 전후 해시, 종료·출력 결합을 확인했다. 소요 4,541.016초이며 잔여·강제
종료 0이다. 별도 완료 검산 exit0과 증거 16파일 51,130바이트의 공유 보존도 확인했다.
원래 참조 없는 21행, 최초 설정 확인 불일치, 원래 이미지 final manifest 미회수는 그대로 유지한다.
이후 닫힌 누적 image ledger를 이용한 내용 검사 범위이며 당시 final manifest 복구로 해석하지 않는다.

이전 C30 이미지 실행 9365는 04:08:04 KST에 정상 종료했다. 144,190개/1,339,924,746바이트
모두 크기·SHA256·JPEG 디코딩 PASS, 선택 사본의 고아 파일 0, 해제 후 입력 대조 PASS다.
전체 출력·원래 native 종료와 worker drain 결합·검사 프로세스 정리 0을 별도 검산했고 exit0이다.
증거 24파일 131,607,634바이트를 공유 `prior-c30-image-check`에 검산했다. JPEG 본문은 다시
복사하지 않았다. 원래 세대의 final manifest 미회수와 전체 R4 HOLD는 유지한다.

추가 기존 기록 CQA20의 12,214개를 연결해 재사용 증거는 169,262개가 됐다. 새 완료분 144,190개와
합쳐 고정 목록 419,520개 중 313,452개가 내용 검증에 연결된다. 남은 106,068개/1,013,733,892바이트는
당시 닫힌 원장에서 선택하고 별도 재대조·Ruff·PowerShell 구문 검사를 통과했다. 첫 구문 준비 확인의
PowerShell 진행 출력 처리 오류는 기록했으며 제품/서버 실패로 바꾸지 않는다.

선행 조건 완료 후 이전 C30 세 날짜 CSV 실행 22966(04:07:49 첫 소비자)과 남은 이미지 실행
41532(04:09:15)를 각 한 번 시작했다. 이미지 서버 신원·경로·닫힌 manifest 확인은 exit0이다.
두 실행의 내용 판정은 아직 미완료이며 관찰 대기 반환만으로 재실행하지 않는다.
[추가 증거·남은 범위·검사 인계](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/prior-c30/remaining-image-preparation-review.md).

04:12 KST 원격 화면 재연결 후 Smart Factory의 Running·전면·최대화·카메라 표시를 확인했다.
현재 제품번호 21155·금형번호 10은 04:07:26에 적용된 상태이며, 사용자 보고 21155·3은
00:57:51의 입력 이력으로 유지된다. Codex는 현재 값을 덮어쓰거나 과거 누락 구간을 보정하지 않았다.
남은 검사 준비 근거 14파일 24,482,534바이트는 공유 `remaining-image-preparation`에 검산해 보존했고,
54,299,099바이트의 선택 CSV 파생물은 개발 PC 기존 경로에서 재사용해 중복 복사하지 않았다.

## 닫힌 실행의 관측 간격과 누락 final manifest 추가 점검

2026-10-23 04:26 KST, 같은 닫힌 C31 실행의 원자료로 온도 HTTP 관측·CSV 행·이미지 원장
간격을 구분했다. 24,784관측의 시작 간격 중앙값은 1.000084초, 105,816 CSV 행의 시각 간격
중앙값은 0.211141초, 23,022 이미지 원장의 캡처 기록 간격 중앙값은 1.062756초다.
이는 약 6시간 53분의 닫힌 전체 실행이며 120분만의 결과가 아니다. wall-clock 시각 차이를
장비 샘플 생성·화면 표시·디스크 flush 주기로 바꾸지 않는다.

CSV의 105,798참조는 독립 관측 24,431건에 연결돼 반복 참조가 81,367행이다. fact에만 남은
353관측도 보존돼 있다. 유효 온도 21,726건 외 sentinel 3,058건, 미입력 작업 정보 24,931행,
shadow 라벨을 정상 온도나 확정 학습 정답으로 바꾸지 않는다. 유효 온도 사이 최대
2,289.992473초에는 수신 성공 sentinel 2,289건이 있었으므로 수집 정지로 판정하지 않는다.
7개 분석기 검사·Ruff·실제 분석·원자료 추가 대조는 모두 exit0이다.
[실행 범위·시각·학습 사용 제한](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/observation-timing/review.md).

별도로 누락된 과거 image final manifest를 개발 PC의 관련 이름 1,086파일 및 공유의
20261022/20261023 관련 이름 2파일에서 찾았다. 이전 C30의 고정 SHA256 사본과 최초 C31의
4,731,431행 후보를 찾지 못했다. 지정 이름·경로 검색 결과이며 전 세계 사본 부재나 복구
불가능을 증명하지 않는다. 원래 마감 시각을 만들어 파일을 재구성하지 않았다.

04:21 KST 화면은 Running·전면·카메라 표시·현재 21155/10 적용 상태다. 사용자가 보고한
21155/3은 00:57:51 이력으로 확인되며 이후 입력을 덮어쓰지 않았다. 기존 실행 22966/41532의
검사는 계속 진행 중이다. 정식 QA·학습 적합성·물리 시험·출시 HOLD는 유지한다.

## 설치 전 고정 목록 이미지 419,520개 내용 검산 완료

2026-10-23 04:50:05 KST 남은 이미지 실행 41532가 exit0으로 종료했다. 106,068개 /
1,013,733,892바이트의 크기·SHA256·JPEG 디코딩, 입력 해제 후 대조, 검사 프로세스 정리를
확인했다. 잔여·강제 종료 0이며 완료 검산 도구도 exit0이다.

04:54 KST 전체 목록 대조도 exit0이다. 기존 근거 169,262개, 직전 C30 추가 완료 144,190개,
이번 완료 106,068개를 합쳐 설치 전 고정 목록 **419,520개 / 3,969,970,160바이트** 전부가
정상 내용 검사에 연결됐다. 미연결·중복 연결·크기/해시 불일치는 각각 0개다. 재사용한 근거는
같은 바이트의 디코딩 속성만 입증하며 다른 이름의 캡처·생산 귀속까지 대신하지 않는다.
[대조 결과·입력 해시·범위](C:/Users/user/Desktop/SmartFactory/C31DAY_20261023_7c82a9f0/prior-c30/complete-inventory/review.md).

이 결과는 고정 목록에 한정된다. 과거 원장 중 목록에 없는 4,311,256행의 원인, 손상 자료,
원래 누락된 final manifest, 현재 서버 전체 상태, 물리 샘플 완전성과 학습 적합성은 확정하지
않았다. 전체 R4·출시 HOLD는 유지한다. C30 세 날짜 CSV 671,981행은 같은 실행 22966에서
계속 검사 중이며, 앞선 PENDING 기록은 당시 상태로 보존한다.

04:54 KST 서버 화면은 Running·전면·카메라·작업 정보 적용됨 상태였다. 현재 값은
21155/10(최근 적용 04:27:04), 사용자가 알려 준 21155/3은 00:57:51 이력이다. Codex가
작업 정보나 이전 누락 구간을 변경하지 않았다.
