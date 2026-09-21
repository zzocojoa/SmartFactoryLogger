# Temperature 개선 검증 결과

> **현재 상태 안내 (2026-09-21):** [브랜치 완료 상태](TEMPERATURE_BRANCH_STATUS.md)를 먼저 읽는다.
> G1~G5는 `72a4103`으로 commit·후보 빌드되었고 후보 준비와 추가 7시간 관찰을 통과했다.
> 아래 HEAD·미커밋·현장 미실행·다음 단계 표현은 코드 검증 당시의 이력이다.
> 원문과 보존 증거는 유지하며 전체 현장 검증·운영 승격 완료와 구분한다.

## 범위와 기준

브랜치 `codex/temperature-remediation-20260909`, 기준 및 현재 HEAD
`09e81777d3ca7823ae496e181668f521ebcd2d7a`. 변경은 미커밋 상태이며 자동 push/PR/merge/배포를 하지 않았다.
사용자 기존 assets/ 및 운영 문서는 보존했다. 9월9일 자료만 사용했다.

G1~G5 코드 목표 완료. 최종 backend765개 시험과 독립 diff 검토를 통과하고 원본 전수 검증을 완료했다.
현장 배포와 당시 지연 원인 입증은 이번 코드 완료와 별도다.

## 최종 판정표

| 목표 | 코드 판정 | 근거 | 현장 한계 |
| --- | --- | --- | --- |
| G1 cache TTL | 통과 | finite age, clock ok, 0≤age≤TTL; driver→row 재평가; sentinel 후 캐시 억제 | 원본 cache 재사용 0행 |
| G2 freshness | 통과 | invalid/default 구분, 같은 domain만 monotonic, ingest UTC fallback, unknown 우회 차단 | 원본 monotonic 없음 |
| G3 PLC source | 통과 | driver/service의 collection-time proof 전달, phase/lifecycle gate, 정상 SPOT/over-range 보존 | PLC 오류 원천 proof 없음 |
| G4 저장 분리 | 통과 | queue256/단일 owner, 실제 Event 초기화·append, F01 및 CSV 저장, 종료·rollover 통합 | 192.769초의 실제 원인 미입증 |
| G5 poll 전수성 | 통과 | A={1,3},B={1,2,3} gap1, runtime/reload/offline 일치, duplicate 별도 | 실fact link/gap/provenance 미검증 |

상세 30개 요구사항과 시험 연결은 [회귀 매트릭스](TEMPERATURE_REMEDIATION_REGRESSION_MATRIX.json)에 있다.
G5-04 실fact 검산은 통과로 표시하지 않았다.

## 원본과 replay 결과

원본 CSV SHA256 `1d368c103e9d269e5dda4dcf0d6d5d67077375dfdeb1a9c7f94c1197f441f965`,
metadata SHA256 `b1bb29c1078c5c7eb253b15d67296f3f175819c1dec6e0237fec6c4f7cfd2202` 유지.
multiline parser로 186878논리행/109열, seq 연속 및 fixture8개1921행의 원본 일치를 확인했다.
373743물리줄은 raw 내장 개행 때문이다.

| 상태 | 원본 baseline | 수정 코드 UTC replay |
| --- | ---: | ---: |
| valid | 161770 | 161769 |
| under_range | 24192 | 24192 |
| stale | 902 | 903 |
| startup_pending | 14 | 14 |

원시6553.4 24200행은 under_range24192+stale8. sentinel/nonvalid Temperature 누출,
quality 매핑 불일치, Count0~2 production_stable 모두 0이다.
sample_seq116741은 age3000ms였으나 기록된 ingest−poll 시각으로3002.245ms여서 stale로 바뀌었다.
seq15~908 stale은 유지된다. seq26→27은 UTC 기준188440.391→188442.396ms로 평가 시각 급감이 없다.

Replay는 원본에 기록된 UTC 시각과 이 파일의 TTL15초/freshness3초만 사용했다.
운영 설정에 이 값을 새로 하드코딩하지 않았다. sample 시각을 덮어쓰거나 monotonic/error를 실측값처럼 만들지 않았다.
PLC proof 부재로 replay phase는 unknown이며 실제 PLC 장애를 뜻하지 않는다.
원본 fact3242032행/link100%/gap0은 metadata 주장이다. wide CSV의 미관측694poll은 fact 유실 증거가 아니다.

## 변경 파일과 호환성

| 파일군 | 변경 목적 |
| --- | --- |
| backend/FacilityData/freshness.py, temperature_operational.py | clock/TTL/PLC proof 공통 검사, current unknown 우회 차단 |
| drivers/spot_api.py, drivers/real_plc.py, service.py, schemas.py | 같은 프로세스 clock domain 및 PLC collection proof 전달, 엄격한 내부 필드 |
| process_phase.py, repository.py | source gate, ingest 평가, 신규 schema rollover, pending/final closeout, timing/거절 계수 |
| spot_observation_queue.py, spot_observation_fact.py | bounded immutable queue/단일 writer, failure/drain, 서비스별 증분 gap 및 reset |
| scripts/validate_csv_v2_shadow.py | 새 row/TTL/clock/gap 불변식, 과거 schema 구분 |
| scripts/verify_temperature_remediation.py | 원본 해시·통계·fixture 전수 확인 및 별도 replay 비교 |
| backend/tests/test_temperature_*.py 및 관련 기존 시험 | 실제 production 함수 회귀/통합/계약 검증 |
| .gitignore, pyproject.toml | 새 시험 소스 노출, 새 모듈 기본 typecheck 포함 |

신규 CSV 의미 버전2.4.1/2.5.1, operational-v5, row-freshness-v2, process-phase-candidate-v4,
poll-completeness-v2. CSV 컬럼 배열과 fact1.3.0 컬럼은 유지한다.
동일 header여도 구버전 row/metadata는 별도 파일로 rollover하며 과거 파일을 재작성하지 않는다.
V1, atomic output, cause collector, 측정범위, 알람/동시요청/샘플링/운영 flag는 변경하지 않았다.

## 검증과 독립 검토

- 전체 health의 Electron94, frontend 보조9, Vitest291/39files, typecheck/lint 통과.
- 최종 backend **765 tests / 107.431s, exit0**. F01 제공 상태로 skip 없이 실행했다.
  Ruff/mypy8files/검증 script 구문 검사 및 git diff --check 통과.
  초기 실패·수정 근거는 진행 기록에 남겼다.
- health 통합 명령은 마지막 QA 단계의 PowerShell 모듈 검색 실패로 exit1이었다.
  프로세스 내 PSModulePath 수정 후 QA 도우미5개 재실행 exit0. 따라서 최초 health를 exit0으로 표기하지 않는다.
- F01은 실제 raw payload와 기존 fact 파일을 사용하되 외부 I/O 및 Event 대기는 합성이다.
  실제 poll/publish→CSV enqueue/build/flush가 fact 초기화 완료 전에 진행됨을 확인했다.
- 읽기 전용 독립 검토에서 strict bool/clock 우회, active rollover final 경합,
  매 poll 전체 이력 집계, schema archive bounds reset 누락을 발견해 회귀시험과 함께 수정했다.
  전체 시험은 주 작업자가 실행했고 독립 검토자는 diff와 별도 production probe를 확인했다.

## 위험과 운영 확인

위험도는 **높음**이다. 수집/저장/종료 계약이 바뀌므로 실장비 검증 후 배포해야 한다.
원본 인증 상태 fingerprint_mismatch, effective verified=false, async_fact_only를 그대로 보존했다.
새 source proof와 clock은 내부 필드이며 외부 API로 권한을 추가하지 않는다. 원본/private 로그는 Git 제외다.

Queue 포화는 newest reject이며 계수/에러와 clean=false로 드러난다. Disk/spool 실패 또는 종료 timeout도
finalized를 금지한다. 무한 저장장애나 프로세스 강제 종료에서 무손실을 보장하지 않는다.
기존 fact index는 이력에 비례한 메모리를 사용하며 현장 장기 부하/메모리 검증은 남아 있다.
정상 rollover는 CSV를 닫되 fact final을 pending으로 보존하고, writer 종료 후 이번 runtime의 보류 경로를 확정한다.
그 전에 프로세스가 강제 종료되면 pending은 남는다. 과거 디렉터리를 자동 탐색해 final로 바꾸지 않는다.

관측 항목은 queue depth/capacity/accepted/completed/rejected/pending, initialization/hash/index/write/residence 시간,
spool/write failure, last success/error, CSV enqueue/build/flush/persisted 시각이다.
PLC sample age와 writer backlog를 분리해서 읽어야 한다.

배포 전에는 같은 빌드의 backend/validator/schema를 함께 검증하고, 기존 대용량 fact 파일로 cold start와
장시간 queue/메모리, 실제 PLC 단절·복구, 저장장애/종료/drain을 확인한다. 기존 attestation false는 장비 확인 전 유지한다.
Low Signal2%/lt 경계, 원본 fact link/gap, 실제192.769초 지연 원인은 별도 증거가 필요하다.
서명된 배포물 생성과 설치 smoke는 이번에 실행하지 않았다.

Rollback은 이전 검증된 앱 번들로 복귀하고, 신규 CSV/fact/spool/metadata를 보존해 schema별로 분석하는 방식이다.
데이터 이관은 없으며 신구 의미를 같은 CSV에 섞지 않는다. 소스 rollback 시 current.patch에 포함된 변경만 되돌려
사용자 기존 작업을 보존한다. 운영 파일 삭제/reset/clean을 rollback 수단으로 사용하지 않는다.

## 로컬 증거 목록

모든 출력은 Git 제외 경로 `artifacts/temperature-remediation-20260909/`에 있다.

| 산출물 | 파일 |
| --- | --- |
| current SHA/변경 파일 해시/전체 patch | current_state.json, current.patch |
| baseline | baseline_report.json |
| 전수 replay/차이 | replay_report.json, replay_diff.csv, replay_status_changes.json |
| regression matrix | regression_matrix.json |
| 테스트 원문 | health-full.txt, backend-final.txt, qa-selftest.txt, final-integration.txt, g1~g5 및 review 로그 |
| F01 합성 계측 | f01_event_timing.json |
| 독립 diff 검토 | independent_diff_review.md |

다음 단계는 배포 전 실장비에서 cold start·PLC 복구·종료 closeout을 검증하는 것이다.
