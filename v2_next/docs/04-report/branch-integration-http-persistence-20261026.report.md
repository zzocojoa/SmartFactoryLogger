# 브랜치 통합과 HTTP 저장 무결성 구현 진행 기록

2026-10-26. 사용자가 승인한 7개 항목을 모두 완료 대상으로 유지한다.
운영 서버의 승인된 1.0.32 설치본과 다음 개발 소스의 검증 범위를 구분한다.

## 완료 조건과 현재 상태

| 번호 | 완료 조건 | 현재 상태 / 근거 |
|---|---|---|
| 1 | 현재 브랜치에 운영 태그의 후속 10개 커밋 통합 | `685dde94`에서 `cd46692a`로 fast-forward 완료. 로컬 후속 작업 재적용·검증 중 |
| 2 | 운영본의 백엔드·회귀 시험 누락 보완 | `spot_api.py`, `repository.py`, CSV 시작 회귀 시험 등 운영 태그 파일 복원. 통합 검증 중 |
| 3 | 버전 파일 5개를 운영 소스 기준과 일치 | 1.0.32로 동기화. 새 기능의 출시 승인·배포를 의미하지 않음 |
| 4 | 기존 109개 변경 보존·검토·커밋 | 원래 내용 해시 대조 후 stash 보존, 재적용. 도구 충돌 15파일/29블록 통합. 문서/도구를 나누어 커밋하는 중 |
| 5 | 원격 브랜치·upstream·기본 브랜치 반영 | 미완료. 검증 전 기본 브랜치를 변경하지 않음 |
| 6 | HTTP 저장 무결성 계획의 7단계·17개 추가 시험 및 경계 계약 구현 | 2026-10-27 1단계 착수. fact 큐의 inflight 포함 건수 상한부터 구현. 전체 범위 유지 |
| 7 | 최종 통합 상태의 빌드·회귀·정적 검사 | 진행 중. 현재 완료된 일부 검사를 전체 완료로 간주하지 않음 |

## 보존과 통합

- 원래 상태: 추적 파일 수정 54개, 미추적 55개, 스테이징 0개.
- 보존 stash: `f470f32d650badc72d684e79a0cdd2fd0dbb32b6`. 최종 보존 확인 전까지 유지한다.
- 이미 운영 태그에 들어간 동일 변경 13개는 재적용 때 중복 변경으로 남기지 않았다.
- 충돌 처리: 기존 renderer-fix 설치본 식별·취소 marker 검증을 보존하고, 후속 operational 관찰·Python 진단 모드와 합쳤다.
- `capture-closed-facts.ps1`의 라이브러리 해시는 통합된 `observe-health-runtime-close.ps1` 바이트에 결합했다. 기존 현장 배포 묶음·원시 증거의 해시는 수정하지 않았다.
- Python 도구 시험이 사용자별 전역 패키지에 의존하지 않도록 개발 의존성에 `pytest==9.0.3`을 명시하고 프로젝트 가상환경에 설치했다.

## 검증과 다음 작업

통합 검사 명령과 전체 출력은 다음 실행 폴더에 보존한다.

`C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6`

- `git-actions.json`: stash, fast-forward, 재적용의 실제 종료 코드와 출력.
- `before-files.json`, `state.json`: 변경 전 파일 식별과 복원점.
- `conflict-resolution.json`: 충돌별 보존 근거 및 라이브러리 새 해시.
- `checks-*`: 검사 명령·종료 코드·stdout/stderr. 실패한 첫 실행도 보존한다.

통합 도구 검사를 해결한 뒤 [HTTP 감시 유지와 저장 무결성 계획](../01-plan/features/http-persistence-integrity.plan.md)을 구현한다.
각 행동을 하나씩 실패 재현 → 최소 구현 → 관련 회귀 검사 순으로 진행한다.
전체 종료에는 R01–R06, RR01–RR04, FR01–FR03, IC01–IC04 및 RV01–RV09·RR-T01–RR-T04·FR-T01–FR-T04의 실제 근거가 필요하다.
서버 설치·운영 승격은 이번 로컬 구현 승인에 포함하지 않으며 기존 운영본과 롤백 근거를 유지한다.

## 2026-10-27 통합 도구 재검증

- Git 자동 줄바꿈 변환으로 생긴 정책 해시 오류를 원래 SHA256과 일치하는 바이트 복원으로 해결했다. 승인 정책의 기대 해시를 변경하지 않았다.
- `audit-20261027/presentation-recheck.json`: 표시 판정기 3모듈 34시험·67하위 사례 통과, exit0.
- `checks-08932a24/results.json`: 짧은 실제 fixture 경로에서 이전 실패 6본시험·2하위 사례 통과, exit0. 이는 이전 요약의 7 failed에 대응한다. 경로 제한을 낮추지 않았다.
- 같은 실행의 Low Signal 정책 32검사 통과, 원래 정책 SHA256 `81122c28d6d5300c9f9c9eae5961e3661c9f775edc09e16ab108a5593bab5324` 일치. 물리 시험은 NOT_TESTED다.
- 변경된 Python 도구/QA 시험의 Ruff 검사 exit0 (`integration-ruff.json`). 기존 정상 부분 검사와 재검증을 연결하며 현재 전체 빌드 완료로 확대하지 않는다.
- 설계·분석·comparator-readiness·PDCA 진행 문서 4개는 정규화한 본문이 보존 감사와 같지만 원래 혼합 줄바꿈 SHA256 복원은 아직 미완료다. `audit-20261027/audit.json`에 원래/현재 해시를 남겼다. 복원 실패 시도도 보존한다.
- 앞 문서 커밋의 공백 검사는 기존 고정 보고서 끝의 빈 줄 때문에 기본 검사 exit2였다. 해당 원문을 수정하지 않고 `core.whitespace=-blank-at-eof` 검사 exit0을 확인했다. 이 예외는 코드 검사나 기술 판정 기준 변경이 아니다.

## HTTP 1단계 — R02 fact pending 건수

`SpotObservationQueue`의 기존 capacity를 대기 중·실제 쓰기 중 합계에 적용했다. queue 슬롯 포화는 기존 `queue_full`, inflight 때문에 총량을 넘는 경우는 `pending_item_limit`로 구분한다. 다른 경로의 예산·스풀·추적·접수 상세 계약은 후속 단계다.

- 기존 `test_temperature_fact_queue.py`에 실제 writer와 파일 I/O 지연을 사용하는 `test_pending_limit_includes_inflight_writes` 추가.
- `tdd/fact-items-red`: 세 번째 접수가 True여서 예상한 행동 실패, exit1.
- `tdd/fact-items-green`: 해당 모듈 14시험 중 13통과·기존 private F01 fixture 1skip, exit0. 기존 큐 포화·종료·fact 저장 검사 포함.
- 임시 시험 경로만 사용했으며 장비 접속·서버 적용·수집 주기 변경은 없다. 이 한 경계의 통과는 RV01 전체 또는 1단계 완료가 아니다.

## HTTP 1단계 — R02 fact payload bytes

직렬화된 fact snapshot의 queue+inflight 합계를 16MiB로 제한하고 실제 payload를 놓은 뒤 예약량을 반환한다. byte 제한 초과는 `pending_byte_limit`로 남긴다. 저장 완료 후 공간 재사용과 실제 저장 행을 검증했다.

- `tdd/fact-bytes-red`는 예상 접수 초과와 시험 정리 대기 부족이 함께 발생했다. 제품 수정 전에 시험 정리 대기를 30초로 바꿨고 `fact-bytes-red-r2`에서 256건 모두 접수되는 예상 실패만 재현(exit1).
- `tdd/fact-bytes-green`: 15시험 중 14통과·기존 F01 1skip, exit0. Ruff 및 해당 모듈 mypy도 exit0.
- 아직 직렬화·writer 출력 사본을 만들기 전의 추가 예약, 디스크 스풀 한도·복구, 다른 CSV/이미지 경로, 상세 접수 결과/ID 계약은 미완료다. 이 구현은 직렬화된 대기 payload의 상한만 입증하며 전체 메모리 예산·1단계 완료로 표시하지 않는다.

## 원문 바이트의 Git 보존

새 `.gitattributes`는 고정 증거·도구의 줄바꿈 자동 변환을 끄고 CRLF를 정상 줄 끝으로 검사한다. 단순 `git add`는 stat이 같은 파일의 이전 변환 결과를 재사용할 수 있어, 원문이 확인된 경로를 `--renormalize`로 다시 읽었다.

`staged-document-byte-check-r2.json`에서 문서/도구 154개가 스테이징 바이트와 실제 원문이 일치함을 확인했다. 문서는 변경 전 감사 SHA256과도 일치하는 것만 포함했다. `git diff --cached --check` exit0, 줄 끝 차이를 제외한 docs/scripts diff exit0이다. 본문 변경 없이 원래 줄바꿈을 보존하는 커밋이며, 미복원 4문서는 포함하지 않았다.

## HTTP 1단계 — fact 상세 접수 API

불변 `FactAdmissionResult(status, reason, observation_key)`와 `enqueue_detailed()`를 추가했다. 기존 Boolean `enqueue()`는 호환 래퍼다. 기존 큐/건수/bytes 거절과 직렬화 실패의 원인을 결과에 연결하며, fact의 `service_id:poll_seq` 키를 그대로 사용한다.

- `tdd/fact-admission-red`: 임시 API가 반환한 CLOSED와 실제 필요한 FULL의 행동 불일치로 exit1.
- `tdd/fact-admission-green`: 16시험 중 15통과·기존 F01 1skip, exit0; 해당 모듈 mypy/Ruff exit0.
- 실제 수집 호출부의 상세 결과 사용, 초기화 실패와 정상 종료의 분리, DISABLED/입력 신원/추적 결과 대조는 후속 경계다. 상세 API 추가 자체를 전체 접수 계약 완료로 간주하지 않는다.

## HTTP 1단계 — 초기화 실패의 상세 결과

실제 파일 열기 실패로 owner 초기화가 끝난 상태를 `REJECTED_UNAVAILABLE/initialization_failed`로 구분했다. 명시적으로 close한 owner의 기존 CLOSED 계약은 유지한다.

- `tdd/fact-unavailable-red` 및 `audit-recheck-20261027-d66ea095`에서 CLOSED/UNAVAILABLE의 예상 행동 실패를 확인했다.
- `tdd/fact-unavailable-green`: 모듈 17시험 중 16통과·기존 F01 1skip, exit0. 해당 변경의 Ruff/mypy도 exit0.
- 이는 실패 상태의 분류 수정이며, 독립 재초기화·복구 제어까지 구현했다는 의미는 아니다.

## HTTP 1단계 — 실제 수집 경로의 거절 처리

`_write_spot_observation_fact_async`가 상세 접수 API를 사용하고 거절 status/reason/기존 observation key를 구조화 로그에 남긴다. 추가 재시도나 새 관측 ID를 만들지 않으며 화면용 최신 캐시 갱신은 유지한다.

- `test_rejected_poll_keeps_display_and_identity`: 실제 HTTP 수집 함수와 capacity1 owner를 사용하고 외부 HTTP 응답만 대체했다. 두 번째 온도502가 캐시에 반영되고, 거절된 원래 poll2의 상세 결과가 로그에 남으며 실제 fact에는 poll1만 저장되는지 검사한다.
- `tdd/fact-producer-red`: 상세 상태가 None인 예상 실패(exit1). `fact-producer-green`: 모듈18시험 중17통과·기존 F01 1skip, exit0. Ruff/mypy exit0.
- 구조화 로그는 후속 data-trace 대조 계약의 대체물이 아니다. 생산–저장 전체 대조와 거절 범위 보존은 2단계에서 계속 구현한다.

## HTTP 1단계 — CSV 원본 envelope와 생산 식별자

CSV 접수 전에 canonical JSON bytes와 source payload hash를 만들고, `logger_service_instance_id + producer_seq`를 부여한 frozen envelope를 큐에 전달한다. API에서 제외하는 내부 단조 시각·PLC 출처 필드도 worker 전달 자료에는 보존한다. 기존 `enqueue`는 호환 진입점이며 상세 접수 영수증을 추가했다.

- `test_admission_freezes_payload_and_identity`: 실제 파일 열기를 지연한 상태에서 접수 후 원본 압력을31→999로 변경했다. `tdd/csv-envelope-red`에서 실제 저장값999의 예상 실패(exit1), 수정 후 저장값31·생산 ID·원본 hash 대조 통과.
- 첫 회귀 검사에서 기존 queue 객체 동일성 가정1건과 EMA 변경2건이 실패했다. EMA의 기존 추정 의미를 복원하고, 종료 sentinel 순서 시험은 immutable envelope의 전체 데이터(내부 필드 포함)·순번·뒤따르는 sentinel을 확인하도록 조정했다.
- `tdd/csv-envelope-green`: CSV service/runtime/image-startup/fact 86시험 중85통과·기존 F01 1skip, exit0. 변경 파일 Ruff와 프로젝트 지정 mypy 9파일 exit0.
- 추가로 repository.py를 명시 지정한 mypy는 기존 annotation 오류9개로 exit1이다. 변경 전 HEAD를 `--shadow-file`로 검사한 `csv-envelope-mypy-baseline`에서도 같은9개가 확인됐다. 현재 변경으로 새 오류는 없지만 이 추가 범위의 전체 정적 검사 통과를 주장하지 않는다.
- 설정 세대·목적지 고정, 합산64MiB/5000 예약, 상세 결과의 통합 수집 호출부 연결 및 출력별 추적은 아직 후속 작업이다. 현재 envelope 추가만으로 CSV 저장 무결성 전체를 완료 처리하지 않는다.

## HTTP 1단계 — CSV 접수 세대와 출력 설정 고정

접수와 같은 설정 잠금 안에서 세대·출력 목록·절대 경로·v1 헤더·v2 계약을 frozen 설정으로 잡는다. worker는 이벤트 순서대로 설정을 채택하며 이전 세대의 buffer를 이전 설정으로 flush한 뒤 전환한다. 접수한 경로가 실패했다고 다른 fallback 경로로 몰래 바꾸지 않는다. 기존 직접 파일 열기 API의 fallback 동작은 유지한다.

- `test_queued_records_keep_admitted_sink_after_config_change`: 실제 첫 파일 열기를 지연하고 두 번째 v1 자료 접수 후 경로와 형식을 v2로 변경한다. `tdd/csv-config-red`에서 이전 v1 파일에30만 남는 실패(exit1)를 확인했고, 수정 후 이전 파일30/31·새 v2 파일32와 세대/출력 영수증을 대조했다.
- `tdd/csv-config-regression`: 기존 CSV service/runtime/image-startup/replay/v2 운영 계약157시험 통과, exit0. Ruff와 프로젝트 지정 mypy9파일도 exit0.
- 현재 고정한 것은 설정상의 출력 경로와 계약이다. 파일명·schema rollover의 최종 실제 목적지 ID, trace 출력·복구 중 가용성의 세대별 결합, 합산 예산 및 실패 경계는 아직 미완료다. RV03/RV04/RR02 전체 통과로 집계하지 않는다.
