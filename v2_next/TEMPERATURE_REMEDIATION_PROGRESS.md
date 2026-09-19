# Temperature 개선 진행 기록

- 기준 HEAD: `09e81777d3ca7823ae496e181668f521ebcd2d7a`
- 브랜치: `codex/temperature-remediation-20260909`
- 원본: 2026-09-09 패키지 inputs (읽기 전용). 다른 수집일과 혼합하지 않음.
- 기존 미추적 assets/ 및 운영 문서는 사용자 작업으로 보존.
- 범위: G1 → G2 → G3 → G4 → G5. 코드 완료와 현장 원인 입증/배포는 별도.
- 실행 환경: Windows, Python backend/.venv, unittest; 외부 장비 I/O는 합성 대체.
- 시작 확인: AGENTS.md, 병렬 운영/서버 경로 정책, README, pyproject, package,
  unittest runner, CI, 제공 context/data review/summary/fixture manifest/regression matrix.
- 시작 명령: `git status --short`, `git branch --show-current`, `git rev-parse HEAD`,
  `git worktree list`, `git switch -c codex/temperature-remediation-20260909` (모두 exit 0).
- 초기 광역 rg는 기존 임시 폴더 ACL 오류, PowerShell brace expansion 명령은 구문 오류.
  대상 소스 경로를 명시해 재조회. 소스 읽기/편집 권한에는 영향 없음.

## G1 캐시 TTL

조사: spot_api의 wall-clock max(0, age), repository의 snapshot cache status 재사용,
operational classifier의 value age/clock/TTL 검증 누락을 현재 HEAD에서 확인.
sentinel 이후 fallback 억제는 현재 드라이버에 이미 존재하므로 회귀 검증 대상.

- `python -m unittest backend.tests.test_temperature_remediation` 수정 전: exit 1,
  3 tests / 11 failing subcases. TTL 초과/invalid age/clock/행시 만료 재현.
- `python -m unittest backend.tests.test_temperature_remediation.CacheAtRowTests backend.tests.test_temperature_operational backend.tests.test_csv_v2_4_operational_contract`
  수정 후 exit 0, 115 tests. 드라이버 sentinel 양쪽→timeout→valid와 wall 역행 포함.
- 테스트 출력: `artifacts/temperature-remediation-20260909/g1-before.txt`, `g1-related.txt`.

## G2 freshness

조사: NaN/bool 입력과 `threshold or 9000`, current origin의 unknown 우회,
sample timestamp age가 threshold를 넘으면 monotonic 행 age를 교체하는 분기 확인.

- 수정 전 RowFreshnessTests: exit 1, 3 tests, failures 8/errors 2.
  실제 repository 메서드 + 명시적 합성 clock에서 188437→3093.088 급감 재현.
- 동일 프로세스 domain token에만 monotonic 적용. domain 미제공은 ingest UTC 기준,
  foreign domain은 unknown, snapshot age 재사용 없음. sample 시각은 보존.
- invalid threshold와 생략 기본값 구분. current origin의 unknown 우회 차단.
- 의미 변경: v2.4.1/v2.5.1, operational-v5/row-freshness-v2. 과거 validator 규칙 보존,
  같은 header여도 row/metadata version이 다르면 별도 파일로 rollover.
- G2 관련 119 tests exit 0. `g2-before.txt`, `g2-related.txt`.

## G3 PLC source gate

현재 코드에서 source 정보 없이 production_stable이 되는 시험 실패(exit 1) 확인.
driver의 grace/error/age/usable → FactoryData → service의 sample 시점 재검증 →
repository → ProcessPhaseInput 전달. unavailable이면 외부 phase도 차단하고 lifecycle
갱신을 중단하며 dwell 증거를 초기화. SPOT valid/over-range와 raw PLC 값은 보존.
process-phase-candidate-v4. 합성 driver→service→row 시험 및 Count0..2/recovery 포함.
- `python -m unittest backend.tests.test_temperature_remediation backend.tests.test_process_phase backend.tests.test_real_plc backend.tests.test_csv_v2_4_operational_contract`
  exit 0, 181 tests. `g3-before.txt`, `g3-related.txt`.

## G4 fact 저장 분리

현재 refresh는 publish 후 매 fact의 shield(to_thread) 완료를 기다렸음.
writer 초기화에서 기존 파일 SHA/index를 읽고 CSV 최초 sidecar도 같은 초기화에 합류.
Event로 실제 `_load_manifest_state_from_output`을 차단한 production refresh 연속 호출:
수정 전 1 test error(timeout), 이후 다음 poll 진행. 실제 지연 원인은 CSV만으로 입증 불가.

- 단일 writer thread + bounded queue(256), immutable bytes snapshot, 비차단 enqueue.
- saturation은 newest reject + 계수/에러/clean=false. 파일·spool 실패 구별.
- 초기 sidecar pending은 정상 비동기 상태로 기록. health는 worker의 메모리 상태만 조회.
- 종료 drain/timeout/cancel 후 worker 소유권 유지, pending/reject/failure는 finalized 금지.
- spool 복구 직후 현재 key의 중복 append 수정. 기존 durable append/digest 실패 계약 유지.
- 초기 hash/index, queue residence, append, CSV build/flush 계측; 기존 enqueue/persisted 시각 보존.
- `python -m unittest backend.tests.test_temperature_fact_queue backend.tests.test_spot_observation_fact backend.tests.test_shutdown_closeout_regression backend.tests.test_spot_api`
  exit 0, 246 tests / 59.515s (`g4-related.txt`). 예전 callback 복사 대체 시험 3개는
  새 실제 writer Event/health/cancel/drain 시험으로 대체. 장비/원본 fact 기반 원인 입증은 미검증.

## G5 서비스별 gap

실 fact 파일이 없어 실제 link/gap 독립 검산은 미검증。
A={1,3}, B={1,2,3} 실제5행에서 runtime/reload/offline/manifest 모두 gap0인 실패4건(exit1)
재현 후 service+seq 집계로 gap1 수정. duplicate key/invalid identity는 별도 계수.
manifest rule `spot-poll-completeness-v2`; 기존 fact 컬럼과 원본 파일은 재작성하지 않음.
빈파일/단일poll/restart/역순/중복/bad service+seq/offline validator 포함112 tests exit0
(`g5-before.txt`, `g5-related.txt`, `g5-completeness.txt`).

## 독립 diff 1차 검토

읽기 전용 subagent 검토에서 다음 문제를 발견하여 재현/수정함:
FactoryData bool→clock/proof coercion(strict), same-domain missing monotonic(wall fallback 금지),
음수 monotonic endpoint(공유 helper), 외부 production phase의 Count0..2 우회,
manifest 중간 generation 변경 및 외부 append(stable generation+size/mtime 확인),
repository 최종 generation 재확인. `review-fixes.txt` 20 tests exit0,
`review-fixes2.txt` 91 tests exit0. 최종 검토는 전체 diff/통합검증 후 수행.

## 통합 및 독립 검토 보완

- 최초 전체 backend: 755 tests, exit1. 과거 합성 관측을 현재 row 시각으로 저장하던
  stage5 fixture가 새 freshness 계약에 따라 stale이 됨. 합성 평가 epoch를 명시하여 수정.
- validator: explicit invalid threshold/TTL을 default로 숨기지 않음. cached-valid TTL,
  valid/fresh/origin, unknown에서 observed 진단값 보존 및 clock anomaly/sentinel 우선순위 보완.
- 초기 validator 통합: 96 tests, exit1. 기존 stale fixture가 row freshness만 수동 변경하고
  age/clock을 그대로 둔 불일치 수정. 149개 관련 통합/종료 tests exit0, 39.847s.
- F01 940행 해시 확인 후 poll1/2 raw payload를 실제 refresh→snapshot→driver mapper→
  CSV enqueue/build/flush로 전달. 기존 fact 파일 hash/index 초기화를 Event로 막은 상태에서도
  두 poll과 CSV 저장 진행. 초기화 해제 후 drain/final closeout 확인.
  timing은 합성 계측이며 과거 clock 복원 또는 당시 지연 원인 입증이 아님.
- 실제 append Event 중 다음 poll, queue 포화, disk/spool, timeout/cancel, restart/dedup 검증.
- 독립 검토가 발견한 active rollover final hash 경합: 동일 경로의 정상 writer가 실행 중이면
  sidecar pending으로 닫고 파일별 persisted state 보존. writer 종료 후 이번 runtime에서 보류한
  경로만 최종 확정. flush/path/metadata 실패는 failure를 유지하며 clean 종료 불가.
- 독립 검토가 발견한 매 poll 전체 이력 재집계: 서비스별 min/max 증분 갱신으로 수정.
  반복 전체 set 순회 금지 regression 포함. 이어 발견한 schema archive bounds reset 누락은
  실제 archive 시험에서 exit1 `(1,20,10)!=(20,20,0)` 재현 후 bounds.clear() 수정.
- 실제 logger.start→2일 enqueue→daily rollover→stop의 성공/metadata 실패 전파 시험 추가.
- 추가한 rollover 시험 첫 실행은 fixture의 image fact LOG_PATH 격리 누락으로 경로 불일치
  fail-closed 발생. LOG_PATH를 같은 임시 디렉터리로 격리하고 UTF-8 sidecar 읽기를 명시.
  실제 rollover+G5 6 tests exit0 (`review-final-related.txt`). production 동작 우회/mock 없음.
- 최종 읽기 전용 독립 검토 결과는 `artifacts/temperature-remediation-20260909/independent_diff_review.md`.

## 검증 명령과 증거

PowerShell, 저장소 root에서 실행. 아래 경로의 test 출력은 private 내용을 포함할 수 있어 Git 제외.

```powershell
$env:APPDATA = Join-Path $PWD '.tmp_test_appdata'
$env:SFL_CONFIG_PATH = Join-Path $env:APPDATA 'config.ini'
$env:TEMPERATURE_GOAL_PACKAGE = 'C:\Users\user\Downloads\Codex_Temperature_20260909_Goal_Package'
$env:TEMPERATURE_EVIDENCE_OUTPUT = Join-Path $PWD 'artifacts/temperature-remediation-20260909'
node scripts/run_backend_unittest.cjs
backend/.venv/Scripts/python.exe -m ruff check backend
backend/.venv/Scripts/python.exe -m mypy
backend/.venv/Scripts/python.exe scripts/verify_temperature_remediation.py --package $env:TEMPERATURE_GOAL_PACKAGE --output $env:TEMPERATURE_EVIDENCE_OUTPUT
npm run health
```

- `npm run health`: exit1은 마지막 QA helper의 Get-FileHash 모듈 검색 실패.
  이전 단계 Electron94 / frontend 보조9 / Vitest291(39files) / backend763 tests는 모두 통과.
  frontend typecheck/lint, backend Ruff/mypy8files도 통과. `health-full.txt`.
- QA 재실행은 현재 프로세스에만
  `$env:PSModulePath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\Modules"`를 설정하고
  `npm run health:qa:selftest`: exit0, 도우미5개 PASS. 소스/시스템 설정 변경 없음. `qa-selftest.txt`.
- 최종 archive reset/실제 rollover 추가 후 backend: **765 tests / 107.431s, exit0**.
  F01 private fixture를 환경변수로 제공하여 skip 없이 실행. `backend-final.txt`.
- Git 기본 CRLF 정책으로 `git diff --check` exit0. autocrlf=false 임시 override 검사에서는
  기존 CRLF를 trailing whitespace로 인식해 exit2였으나 소스 줄바꿈 변경 없이 기본 정책으로 재검증.
- 신규 모듈은 mypy 기본 대상에 추가. compileall로 두 검증 script 구문 검사, exit0.
- 전수 baseline/replay CLI: exit0. 논리186878행/109열, 물리373743줄, categorical24종/전체 nonblank
  통계 일치, fixture8개1921행 원본 cell 일치, 입력 CSV/metadata SHA256 재확인.
- CSV 한 행(sample_seq116741)이 valid→stale: 기록 age3000ms→ingest UTC 기준3002.245ms.
  기존 stale902개 모두 stale 유지. seq26→27은 동일 UTC 기준188440.391→188442.396ms.
- baseline/report/replay/current patch/matrix 목록과 해석은 `TEMPERATURE_REMEDIATION_RESULT.md`.

## 미검증과 범위 유지

원본 fact 부재로 실제 link/gap/provenance 검산 미검증. wide 미관측694poll은 fact 유실 아님.
원본에 cache fallback/transport error/PLC error proof/monotonic clock이 없어 해당 실측 검증은 불가하며
production 모듈 합성 시험으로 보완. PLC proof 없는 replay phase unknown은 실제 PLC 장애 판정이 아님.
fingerprint_mismatch/effective verified=false/async_fact_only 유지. Low Signal2% lt 경계는 미검증.
배포/실장비/원인입증/서명 빌드는 미실행. 사용자 assets/운영문서 보존. commit/push/PR/merge/배포 없음.

## 종료 판정

G1~G5 코드 종료조건 및 관련 안전/통합/계약 시험 통과. 최종 독립 diff 검토 승인.
current SHA는 기준 HEAD와 동일한 미커밋 변경이며, 전체 patch는 `current.patch`에 보존.
`git apply --reverse --check`는 실제 파일을 변경하지 않고 전체 patch의 현 작업 트리 일치를 검증(exit0).
코드 목표 완료. 현장 배포/실제 지연 원인/원본 fact 검산 완료를 뜻하지 않음.
