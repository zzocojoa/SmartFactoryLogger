# 브랜치 통합과 HTTP 저장 무결성 구현 진행 기록

2026-10-26. 사용자가 승인한 7개 항목을 모두 완료 대상으로 유지한다.
운영 서버의 승인된 1.0.32 설치본과 다음 개발 소스의 검증 범위를 구분한다.

## 완료 조건과 현재 상태

| 번호 | 완료 조건 | 현재 상태 / 근거 |
|---|---|---|
| 1 | 현재 브랜치에 운영 태그의 후속 10개 커밋 통합 | `685dde94`에서 `cd46692a`로 fast-forward 완료. 로컬 후속 작업 재적용·동기화 시점의 전체 health 검증 완료 |
| 2 | 운영본의 백엔드·회귀 시험 누락 보완 | `spot_api.py`, `repository.py`, CSV 시작 회귀 시험 등 운영 태그 파일 복원. 당시 후속 개선을 포함한 `f8ad11d8` 전체 health 검증 완료 |
| 3 | 버전 파일 5개를 운영 소스 기준과 일치 | 1.0.32로 동기화. 새 기능의 출시 승인·배포를 의미하지 않음 |
| 4 | 기존 109개 변경 보존·검토·커밋 | 109개 경로 모두 추적·커밋. 도구 충돌 15파일/29블록 통합. 2026-10-27 원본 4문서 모두 기존 SHA256과 일치하도록 복원했고 보호 stash도 유지 |
| 5 | 원격 브랜치·upstream·기본 브랜치 반영 | 원격 작업 브랜치 생성·upstream 연결·HEAD 대조 완료. master 통합은 미완료 |
| 6 | HTTP 저장 무결성 계획의 7단계·17개 추가 시험 및 경계 계약 구현 | 이미지 CSV 직렬화·파싱·파일 접근의 예약/시각을 추가하고 quoted 헤더 호환성 보완. 초기화/close 불확실·metadata·이전 owner·sidecar·monitor 수명 등 전체 구현은 미완료 |
| 7 | 최종 통합 상태의 빌드·회귀·정적 검사 | `7a5d370c` backend 전체 실행1215통과·1skip 뒤, 같은 제품 소스에서 F01 단독1시험 통과로 누락 보완. backend lint/typecheck·QA 자체 검사 exit0. 새 단일 전체 실행의 skip0을 주장하지 않으며 최종 빌드·새 설치본 검증은 미완료 |

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

## HTTP 1단계 — 세대 전환 예외에서 다음 원본 보존

이전 세대 flush가 예외를 던지면 아직 채택하지 않은 다음 세대 envelope를 동일 ID·내용으로 deferred에 보존한다. 큐에서 이미 꺼냈다는 이유로 다음 자료가 사라지는 경계를 수정했다.

- `test_config_flush_error_preserves_next_generation_event`: 실제 파일 write에서 데이터 쓰기 전 한 번 OSError를 주입. `tdd/csv-config-failure-red`에서 새 경로의 파일0개라는 예상 실패(exit1), 수정 후 이전·새 경로에 각각 원래 행 한 개가 저장됨을 확인.
- `tdd/csv-config-failure-green`: CSV158시험 통과, exit0. 변경 Ruff 및 프로젝트 mypy9파일 exit0.
- 이번 오류는 bytes가 쓰이기 전의 실패다. 일부 행 쓰기 후의 중복 방지·불확실 파일 중단은 여전히 3단계의 별도 미완료 계약이다.

## HTTP 1단계 — CSV 비활성 접수의 구분

자동 저장 OFF일 때 `DISABLED/auto_save_disabled`를 반환하고 큐·drop 집계에 넣지 않는다. 생산 순번과 당시 세대는 영수증에 유지한다.

- `test_disabled_admission_has_no_pending_work`의 ACCEPTED/DISABLED 불일치로 RED(exit1), 수정 후 CSV service/runtime58시험 통과(exit0), Ruff·프로젝트 mypy exit0.
- 비활성만 돌려주는 빈 구현은 같은 모듈의 실제 저장·불변 원본·세대 전환 시험을 통과할 수 없다. 입력 오류·현재 저장 불가·합산 예산 등의 남은 접수 경계는 계속 구현한다.

## HTTP 1단계 — CSV pending 건수 예약

CSV 접수에서 queue 슬롯과 별개로 원본 이벤트를 예약하고 v1/v2의 필수 출력이 모두 flush될 때 해제한다. queue 밖 buffer·inflight도 최대5000건에 포함한다. 끝까지 남은 접수 자료는 정상 종료로 표시하지 않는다. 신규 출력별 trace 확정은 아직 2단계의 미완료 계약이다.

- `test_csv_pending_limit_includes_inflight_and_both_outputs`: 실제 v2 파일 열기를 지연하고 2건 한도에서 세 번째를 거절하는지, 해제 후 두 CSV에30/31만 저장되고 pending0인지 검사. `tdd/csv-items-red`에서 ACCEPTED/LIMIT 예상 실패(exit1), 최종 `csv-items-final-green`의 CSV160시험 통과(exit0).
- 2026-10-27 완료 감사에서 발견한 Optional envelope 타입 오류2개는 실제 decode 조건을 명시해 해결했다. 최종 backend Ruff·프로젝트 mypy9파일 exit0. repository.py 추가 검사는 기존9오류만 남으며 exit1이다. 기존 오류와 신규 오류가 사라진 결과를 구분해 보존했다.
- 이번 건수 제한은 bytes·직렬화/출력 임시 사본·스풀 한도나 부분 쓰기 무결성 전체의 완료를 뜻하지 않는다. 감사의 원시 결과와 원본4문서 복원/원격 통합/전체7단계 잔여 범위도 유지한다.

## HTTP 1단계 — CSV 원본 payload 예약

접수된 원본 bytes의 합계를64MiB 내에서 예약하고 queue에서 꺼내도 유지하며, 필수 출력이 flush된 뒤 해제한다. 기존 EMA 추정치는 변경하지 않고 실제 원본 예약량을 별도 상태로 표시한다.

- `test_csv_source_budget_includes_inflight_payloads`: 실제 writer를 지연하고128KiB Status가 있는 여러 원본을 접수했다. 상한 초과를 `REJECTED_LIMIT/pending_byte_limit`로 거절하고 접수분만 실제 CSV 행으로 저장, 종료 후 예약0을 확인한다.
- `tdd/csv-source-bytes-red`는 예상한 초과 ACCEPTED로 exit1. `csv-source-bytes-green`의 CSV service/runtime60시험, 변경 Ruff·프로젝트 mypy 모두 exit0.
- 아직 원본 직렬화 전에 발생하는 임시 사본과 출력 렌더링 사본은 이 counter에 포함하지 않는다. 이를 전체 R02 합산64MiB 구현으로 표시하지 않으며 같은1단계의 다음 필수 경계로 유지한다.

## HTTP 1단계 — CSV 직렬화 거절과 기존 소비 시험

생산 순번·접수 설정을 먼저 잡고, 직렬화 불가능한 원본에는 `INVALID/snapshot_serialization_failed`와 같은 순번을 반환한다. 존재하지 않는 원본 hash를 만들지 않는다. 수집 호출부로 예외가 전파되는 대신 다음 정상 이벤트를 다음 순번으로 저장한다.

- `test_invalid_csv_payload_keeps_producer_identity`: 생성 후 NaN으로 변한 압력의 실제 JSON ValueError를 RED로 확인(`csv-invalid-red`, exit1). 수정 후 CSV service/runtime61시험·Ruff·프로젝트 mypy exit0.
- 추가 소비 경로 검사 `csv-envelope-consumer-check`에서 기존 시험3개가 queue 항목을 FactoryData로 직접 읽어 AttributeError를 냈다. 제품의 승인된 immutable envelope 계약에 맞춰 fixture 읽기만 payload decode로 변경했다. 원래 값·시각·내부 PLC 시계·이력 ID 검사와 생산 순번을 유지/추가했다.
- `csv-envelope-consumer-green`: 실제 생산/소비·clock source·history31시험 통과, backend Ruff exit0. 전체 backend 또는 17개 추가 시나리오 완료 주장은 아니다.

## CSV 타입 검사 범위 보완

csv.writer 함수 이름을 타입으로 쓰던6곳을 writer Protocol로, object 파일 핸들을 TextIO로 명시했다. Optional freshness 값은 한 번 읽고 null 여부를 확인한다. repository.py를 pyproject의 기본 mypy 대상에 추가해 기본 검사 범위가9→10파일이 됐다.

- 첫 편집은 보조 변수를 잘못된 함수에 넣어 정적 검사2오류와 CSV 회귀 실패를 냈다(`csv-types-mypy/ruff/regression`). 이는 TDD RED가 아닌 편집 오류이며 원문을 보존한다.
- 위치를 수정한 `csv-types-mypy-r2`는10파일 오류0, `csv-types-ruff-r2`는 backend 오류0, `csv-types-regression-r2`는 CSV162시험 통과로 모두 exit0이다. 앞 감사의 기존9+추가2 타입 오류는 현재 남아 있지 않다.
- 이 검사는 현재 CSV 코드 범위의 보완이며 전체 health/빌드·서버 적용을 완료 처리하지 않는다.

## Windows 릴리즈 의존성 잠금 동기화

완료 감사 `completion-audit-20261027-74c018f0`에서 전체 health는 backend979시험 중978통과/1skip까지 완료했으나, QA의 직접 의존성 잠금 대조에서 pytest 누락으로 exit1이었다. `lock-red`로 같은 실패를 재현한 뒤 Windows/Python3.12와 격리된 pip-tools7.6.2에서 기존 입력 `.in`을 다시 compile했다. 해시를 수동 편집하거나 검사 조건을 완화하지 않았다.

- 기존 패키지의 버전·해시를 유지하고 pytest9.0.3, iniconfig2.3.1, pluggy1.7.0, pygments2.21.0을 추가했다. `raw-document-object-search.json`의 기존 pin 변경은0이다.
- `lock-green`: workflow 계약 SelfTest exit0. `lock-dry-run`: 기존 개발 환경에서 `--dry-run --require-hashes --only-binary=:all:` 해석 exit0. 기존 환경의 일부 버전은 lock과 다르며 실제 변경은 하지 않았다. 이 dry-run을 새 clean 설치 검증으로 확대하지 않는다.
- `lock-health-result.json`: 수정된 lock SHA256 `e2d83ec488859f78737e13ee086352f41864ffe383a82e874d940ed0e529b0b6`에서 전체 `npm run health` exit0. 의존성15·Electron103·화면Node9/Vitest442·backend979 중978통과/기존1skip·Ruff/mypy10파일·QA 자체 검사 모두 완료했다.
- 기존 감사의 실패 원문은 보존하며 후속 수정으로 연결한다. 새 설치본 빌드·운영 승격 및 HTTP 전체7단계의 완료 근거는 아니다.

원문4문서의 바이트 복원은 Git 전체24,035객체에서 원래 크기와 맞는 blob이0임을 추가 확인했다. 현재 본문과 보존 stash의 정규화 일치는 유지하지만 원래 SHA256 복원은 미완료다. NAS 당일 records와 REA 경로에서도 해당 이름의 사본을 찾지 못했다. 보호 stash와 기존 감사 해시를 유지한다.

## 원격 작업 브랜치 사전 검사

989ef1d6의 첫 push는 pre-push 비밀값 검사에서 인증정보 형태의 localhost 시험 URL1개 때문에 차단됐다. `push-auth-url-inspection.json`에서 해당 위치를 확인했고, `observe_operator_image.test.cjs`의 정확한 origin 거부 시험 입력이었다. 실제 인증정보나 네트워크 연결 값이 아니며 `resolveImageOrigin`의 username/password 검사로 즉시 거부된다. 해당 실제 시험을 다시 실행해1개 통과(exit0)를 확인했다.

스캐너를 끄거나 시험 입력을 숨기는 대신 루트 `.gstack-redact-allowlist`에 검토한 정확한 scanner span1개만 기록한다. 와일드카드·규칙 비활성화·no-verify를 사용하지 않는다. 전체 health exit0은 직전 lock 수정 상태의 결과이며, 이 예외는 앱 동작이나 운영 QA 판정을 바꾸지 않는다. 원격 HEAD 확인 전까지 전달 완료로 표시하지 않는다.

## 원격 작업 브랜치 반영 완료

검토한 정확한 시험 입력 예외를 포함한 `72266d23`의 정상 push는 exit0이었다. `branch-remote-verification.json`에서 원격 작업 브랜치 HEAD와 로컬 HEAD가 같고 upstream이 설정됐음을 확인했다. master는 별도이며 아직 통합하지 않았다. 기존 실패 push 기록도 유지한다.

## HTTP 1단계 — 실제 CSV 수집 호출부의 상세 결과 처리

`PLCService._loop`가 `enqueue_detailed()`의 결과를 직접 처리한다. 저장 거절은 생산자·순번·원본 hash·설정 세대·필수 출력과 사유를 구조화 경고에 남긴다. 최신값과 화면 이력은 계속 갱신하고, 큐 거절을 이유로 같은 관측을 재생산하지 않는다. 정상 DISABLED는 오류로 기록하지 않는다.

- `test_consumer_reports_csv_rejection_without_losing_latest_sample`: 실제 수집·소비 루프와 capacity1 CSV 큐에서 첫 이벤트만 접수하고, 나머지 ID2–4의 FULL/queue_full과 최신값4·화면 이력1–4를 확인한다. 원본 payload나 인증정보를 로그에 추가하지 않는다.
- `csv-consumer-red`의 예상 실패는 상세 거절 code가 None인 것(exit1)이었다. 첫 green 시도에서는 가상 시각 생산 후 실제 시각으로 이력을 조회해 TTL이 만료되는 시험 오류1개가 남았다. 조회 시계만 같은 기준으로 맞췄고 제품 로직은 추가 변경하지 않았다.
- `csv-consumer-green-r2`: 서비스 시계·원본 시계·history cursor·worker lifecycle 45시험 통과(exit0). backend Ruff(`csv-consumer-ruff-r2`)와 기본 mypy10파일(`csv-consumer-mypy`)도 exit0. Ruff 첫 실행은 기존 실행 폴더 이름 충돌로 시작하지 못했으며 새 이름으로 검사를 완료했다.
- 기존 consumer 종료 시험의 I/O 예외 주입 위치를 실제 호출하는 상세 API로 옮겼으며 기존 종료/재시작 assertions를 유지했다. 구조화 로그를 영속 data-trace, 출력별 저장 대조 또는 7단계 전체 완료로 간주하지 않는다.

## HTTP 1단계 — 이미지 pending 건수

이미지 접수에서 queue 대기뿐 아니라 writer가 처리 중인 capture도 기존128건 상한에 포함한다. 기존 queue 포화와 pending 한도 거절을 분리해 health·종료 상태에 집계한다. 실제 완료/실패와 task_done의 원자적 상태 갱신 및 과거 실패 보존은 유지했다.

- `test_capture_pending_limit_includes_inflight`: 실제 JPEG 파일 쓰기를 지연하고2건 상한에서 세 번째 접수 거절, 해제 후 다음 이미지 접수·실제3파일/3fact·종료 대조를 확인한다. `image-items-red`는 unfinished3/기대2의 행동 실패(exit1)였다.
- `image-items-green`: 이미지 종료 증거·SPOT API·retention·CSV 이미지 시작237시험 통과(exit0). backend Ruff 및 기본 mypy10파일도 exit0.
- 아직 이미지 원본/연결 snapshot/임시 출력의 합산 bytes 예산, 고정 설정·목적지 및 상세 접수 결과는 후속 경계다. 단순 건수 제한을 RV02/RR03 전체 완료로 표시하지 않는다.

## HTTP 1단계 — 이미지 원본·연결 snapshot 예약

접수하는 이미지 bytes와 canonical JSON으로 고정한 연결 snapshot의 합계를128MiB 내로 예약한다. queue에서 꺼내도 예약을 유지하며, 쓰기 완료 또는 명시적 실패 이후 원본과 예외 traceback 참조를 놓고 예약·완료 집계를 함께 갱신한다. queue/개별 이미지 크기/pending 건수/합산 bytes 거절을 별도 집계한다.

- `test_capture_payload_budget_includes_inflight_and_linked_snapshot`: 유효한 JPEG comment segment로1MiB가 넘는 이미지를 만들고, 연결 snapshot까지 포함할 때만 상한을 넘는 세 번째 접수를 검사한다. 저장된3개 이미지의 SHA256과 fact의 관측 키1·2·4를 대조하고 종료 후 예약0을 확인한다.
- `image-bytes-red`: 접수3/기대2로 exit1. 첫 회귀의238시험 중 이 새 시험만 연결 키가 비어 실패했다. fixture에 필수 조회 완료 시각이 빠진 원인을 확인하고 입력을 보완했다. 제품 동작은 추가 변경하지 않았다.
- `image-bytes-green-r2`: 수정 fixture가 포함된 이미지 종료33시험 통과(exit0). 앞 실행의 나머지205시험도 통과했고 해당 제품 상태의 backend Ruff/mypy10파일은 exit0이다.
- 이 예약은 보존 중인 원본 payload 범위다. 직렬화·decode·출력 임시 사본과 공유 참조의 중복 예약 방지, 스풀/복구 예산은 계속 구현할 필수 범위이며 R02/RR03 전체 완료가 아니다. 새 JSON snapshot 경로의 입력 오류가 감시로 전파되지 않도록 하는 경계도 다음 시험으로 확인한다.

## HTTP 1단계 — 잘못된 이미지 연결 snapshot의 거절

직렬화할 수 없는 연결 snapshot은 원본 큐/예약에 넣지 않고 별도 invalid 거절·사유로 남긴다. 저장 입력 오류가 이미지 조회 호출부로 전파되지 않으며 다음 정상 capture를 계속 저장한다. 과거 invalid 집계는 후속 쓰기 성공 후에도 유지한다.

- `test_invalid_link_snapshot_rejects_capture_and_next_capture_succeeds`: NaN의 실제 JSON ValueError가 호출부로 전파되는 RED(`image-invalid-red`, exit1)를 확인했다. 수정 후 다음 정상 이미지만 저장되고 연결 키2·예약0·거절1/쓰기 실패0을 대조했다.
- `image-invalid-green`: 이미지 종료·SPOT API·retention·CSV 이미지 시작239시험 통과(exit0), backend Ruff·mypy10파일 exit0.
- 전체 상세 admission/영속 trace와 이미지 설정 세대·실제 목적지 고정은 아직 후속 작업이다. 이번 수정은 입력 오류 격리 범위다.

## HTTP 1단계 — 접수한 이미지의 저장 경로 고정

이미지 envelope에 접수 당시 writer 설정(절대 log/image 경로, 보존 기간, 연결 신선도 기준)을 고정했다. worker는 현재 전역 설정이 아닌 해당 envelope의 설정으로 writer를 선택한다. 접수 뒤 설정 변경으로 이전 이미지의 JPEG와 연결 fact가 새 위치로 이동하지 않는다.

- `test_queued_captures_keep_admitted_destinations`: 첫 실제 JPEG 쓰기를 지연하고 두 번째 접수 후 log/image 경로를 변경했다. `image-destination-red`는 이전 경로의 이미지1개/기대2개로 실패(exit1). 수정 후 이전 경로2개·새 경로1개와 각 원장/JPEG SHA256, 종료 예약0을 확인했다.
- `image-destination-green`: 이미지 종료·SPOT API·retention·CSV 이미지 시작240시험 통과(exit0). backend Ruff·기본 mypy10파일도 exit0.
- 이 결과는 접수 후 writer 선택 경계다. 설정 적용 전체와 접수의 원자성, 명시적 설정 세대·출력 계약 식별자, 날짜별 실제 목적지·영속 trace와 복구 계약은 계속 남은 필수 범위다. 기존 보존 자료와 서버 설치본은 변경하지 않았다.

## HTTP 1단계 — 이미지 설정 게시와 접수의 일관성

ConfigManager가 log/image 경로·이미지 정책·제한·연결 신선도 설정을 먼저 해석한 뒤 같은 잠금 안에서 한꺼번에 게시한다. 이미지 접수도 그 잠금 경계를 사용한다. 경로 확인·CSV 설정 적용·PLC 재연결은 잠금 밖에 둬서 설정 준비가 느려도 이전의 완전한 설정으로 접수·저장을 계속한다.

- `test_capture_during_config_apply_uses_complete_previous_settings`: 실제 ConfigManager의 경로 변경과 이미지 모드 해석 사이를 지연하고 이미지를 접수했다. 기존 동작은 새 log/옛 상대 image 경로를 섞어 이전 폴더1개/기대2개로 실패했다. 실패 시에도 설정 thread를 join한 뒤 fixture를 복원하도록 정리한 `image-config-atomic-red-r2`에서 동일 실패(exit1)를 다시 확인했다.
- 수정한 `image-config-atomic-green`: 이미지·SPOT·retention·CSV 시작·설정 서비스251시험 통과(exit0). 설정 준비 중 이전 폴더2개, 게시 후 새 폴더1개와 각 원장 수를 대조했다. backend Ruff·기본 mypy10파일도 exit0.
- 잠금 범위는 이 저장 설정 게시와 이미지 접수다. 다른 설정·소비자의 전체 트랜잭션 또는 명시적 generation/required-sink/trace 계약 완료를 주장하지 않는다. 설정 세대 식별·복구·합산 임시 예산과 전체17명세는 계속 남아 있다.

## 2026-10-27 현재 상태의 전체 검사와 원문 복원

이미지 저장 목적지 고정·설정 게시 변경 후 `f8ad11d8`에서 `npm run health`를 실행했다.
2026-10-27 03:27:06~03:33:29 KST, exit0이며 실행 전후 HEAD가 같고 작업 트리가 깨끗했다.
개발 PC의 격리 AppData/설정과 기존 fixture를 사용했다. 서버에 설치하거나 장비 설정을 바꾸지 않았다.

- 의존성 계약 15개, Electron 103개, frontend Node 9개와 Vitest 442개 통과.
- frontend 타입/린트, backend Ruff, 기본 mypy 10파일, QA self-test 모두 exit0.
- backend 985개 중 984개 통과. `TEMPERATURE_GOAL_PACKAGE`가 없는 기존 private F01 fixture 1개는 skip이며 통과 수에 넣지 않는다.
- 로그의 의도된 잘못된 CSV/종료 실패 출력은 부정 입력 회귀 시험의 결과다. 최종 unittest 결과는 `OK (skipped=1)`이다. Starlette의 httpx 사용 중단 예정 경고는 남아 있다.
- 원시 명령/시각/종료 코드: `BRANCH_SYNC_20261026_4d2950c6/image-config-health-result.json`, 전체 stdout/stderr는 같은 접두사의 `.log` 파일이다.

설계·분석·comparator-readiness·PDCA 진행 문서의 원래 혼합 줄바꿈을 편집 기록에서
추적해 복원했다. 네 문서 모두 감사 당시 기대 SHA256과 정확히 일치하고,
줄바꿈을 정규화한 본문은 기존 HEAD와 같다. 기대 해시를 수정하거나 새 해시로 대체하지 않았다.

| 문서 | 복원 bytes | 원래 SHA256 |
|---|---:|---|
| 설계 | 276,343 | `fc234df296d0564259cb4f7573161141cc6564594f4b29a008b3a4430d76152e` |
| 분석 | 578,747 | `b7d723008e342858060743a8b6bc2a7b7b85af09b540a87e7b85f5966369c426` |
| comparator-readiness | 183,357 | `7696910e1fbee91c6d97765509ff98d4580a9acde72d3e24a859c96bb1c7e4bb` |
| PDCA 진행 | 60,032 | `de044aa4f2292f12db8eea7cb59a25bff5b148249e16cbe9bb2f85dcbb677db6` |

근거는 같은 실행 폴더의 `raw-documents-restored.json`이다. 아래/앞의 과거 미복원 기록과
실패한 복원 후보는 당시 이력으로 유지하며, 현재 네 문서의 바이트 복원 미완료 조건은 해소됐다.
보호 stash는 삭제하지 않는다. `.gitattributes`의 `-text`로 원문 줄바꿈을 Git에 보존한다.

`CHANGELOG.md`에는 승인된 1.0.32와 이전 1.0.30/1.0.31 후보 이력, 미출시 후속 개선을
구분해 추가했다. 현재 package의 1.0.32 표기가 이 후속 소스의 운영 승인까지 뜻하지 않는다.
남은 완료 조건은 HTTP 계획 전체 구현·17개 시나리오, 최종 빌드/검증, master 통합이다.

## HTTP 1단계 — 새 이미지 취득의 고유 ID

실제 upstream 취득이 끝날 때 capture ID를 한 번 발급해 cache entry와 불변 저장 이벤트에
전달한다. 같은 JPEG와 같은 벽시계 시각을 가진 별도 취득도 서로 다른 ID로 저장한다.
캐시 응답은 기존 entry를 사용하며 새 저장 후보를 만들지 않는다. 기존 직접 writer 호출과
과거 12자리 hash 파일명은 유지하고, 새 32자리 취득 ID도 같은 날짜별 보존 관리에 포함한다.

- `test_distinct_acquisitions_with_same_time_and_bytes_keep_both_images`: 외부 HTTP 응답과 벽시계만 고정하고 실제 refresh·writer를 사용했다. 원래 원장1행/기대2행의 실패를 `image-acquisition-id-red`에서 확인(exit1). 수정 후 JPEG2개·서로 다른 ID2개·내용/hash·미저장0을 대조했다.
- `image-acquisition-id-green`: 실제 229시험은 통과했으나 제가 마지막 모듈 이름을 잘못 적어 import 오류1개로 exit1이었다. 제품 실패와 구분해 보존했다. 정확한 `test_csv_image_startup`의 별도 실행 `image-acquisition-id-startup`은 13시험 exit0이다. 합계 해당 242시험의 실제 통과를 확인했다.
- backend Ruff와 기본 mypy10파일은 exit0. 기존 single-flight/캐시 재사용과 이미지 retention 검사를 포함했다.
- 취득 ID 전달은 동일 ID의 부분 쓰기 복구·내용 충돌 판정 완료를 뜻하지 않는다. 상세 이미지 접수 결과, 설정 세대/출력 계약과 영속 추적은 계속 남은 필수 범위다.

## HTTP 1단계 — 이미지 상세 접수 결과

이미지 접수 함수가 불변 `ImageCaptureAdmissionResult(status, reason, capture_id)`를 반환한다.
기존 queue/건수/bytes/한 건 크기 거절, 비활성·모드/간격 제외, 잘못된 snapshot과 종료를
구분하고 원래 취득 ID를 유지한다. 저장 성공과 접수 성공은 구분한다.

- `test_capture_admission_reports_pending_limit_with_identity`: 실제 writer를 지연하고2건 한도에서 세 번째 접수의 LIMIT/사유/원래 ID, 앞선 두 ACCEPTED와 실제 저장 ID를 대조했다. 임시 CLOSED 결과와 필요한 LIMIT의 RED(`image-admission-red`, exit1)를 확인했다.
- `image-admission-green`: 이미지 종료·SPOT API·retention·CSV 시작243시험 통과(exit0). backend Ruff·mypy10파일 exit0.
- 기존 정책 제외를 drop으로 바꾸지 않았다. 현재 저장 불가의 가용성 계약과 상세 결과의 실제 HTTP 호출부 기록·영속 추적은 다음 경계이며, 전체 접수 계약 완료로 표시하지 않는다.

## HTTP 1단계 — 실제 이미지 조회 경로의 거절 기록

실제 refresh 호출부가 상세 접수 결과를 확인하고 거절 status/reason/capture ID를 경고에
남긴다. 캐시와 응답 이미지의 최신 갱신은 유지한다. 정상 정책 제외는 오류로 기록하지 않고,
새 경고에 센서 URL·인증정보·이미지 본문을 넣지 않는다.

- `test_rejected_live_capture_keeps_image_and_reports_identity`: 실제 refresh/접수와1byte 저장 예산에서 경고 누락을 RED(`image-producer-red`, exit1)로 확인했다. 수정 후 반환/캐시 이미지 유지·LIMIT 사유·같은 capture ID·저장0·거절1·쓰기 실패0을 대조했다.
- `image-producer-green`: 관련244시험 통과(exit0). backend Ruff·기본 mypy10파일 exit0.
- 이 구조화 로그는 영속 data-trace나 출력별 정상 종료 대조의 대체물이 아니다. 해당 전체 계약은 미완료다.

## HTTP 이미지 저장 간격 — 시스템 시각 변경과 분리

이미지의 최소 저장 간격은 마지막 접수 성공부터 단조 시계로 계산한다. Windows 시각이
앞뒤로 바뀌어도 간격을 우회하거나 오래 저장을 건너뛰지 않는다. 원래 취득 시각과
운영 상태의 벽시계 시각은 그대로 보존하며, 거절된 시도는 다음 접수 기준을 이동시키지 않는다.

- `test_capture_interval_ignores_wall_clock_changes`: 벽시계가 앞으로 이동했을 때 기존 구현이 간격 전 이미지를 ACCEPTED로 처리하는 RED(`image-monotonic-red`, exit1)를 확인했다. 수정 후 간격 전 정책 제외, 크기 초과 거절, 벽시계 후퇴 뒤 다음 정상 접수와 실제 JPEG/원장 2개·미저장 0을 대조했다.
- `image-monotonic-green`: 이미지 종료·SPOT API·retention·CSV 시작 245시험 모두 통과(48.689초, exit0). backend Ruff와 기본 mypy 10파일도 exit0이다.
- 이 결과는 이미지 간격의 해당 경계 검증이다. 영속 추적·전체 저장 결과 계측·7단계 전체 구현과 최종 설치본 검증은 계속 미완료다. 기존 전체 health 실행 이후 추가된 제품 변경에는 이번 관련 회귀 결과를 적용하며, 이전 전체 health를 최신 소스 전체의 검사로 표현하지 않는다.

## HTTP 1단계 — fact 복구의 한 번 처리 건수

기존 fact 스풀 전체를 `list(handle)`로 올리던 복구를 한 호출당 최대20개 물리 행의
읽기/처리로 바꿨다. 확인된 행 다음의 읽기 위치를 writer가 유지하고, 남은 건수에 반영한다.
이 변경은 아직 bytes 제한·새 segment 형식·기존 스풀 원본 보존·독립 복구 예약의 완료가 아니다.

- `test_spool_recovery_processes_at_most_twenty_rows`:23건을 준비했을 때 첫 복구의 실제 CSV23행/기대20행으로 RED(`fact-spool-rows-red`, exit1)를 확인했다. 수정 후 첫20행·미복구3건, 다음3행과 전체 키·manifest23행을 대조했다.
- `fact-spool-rows-green`: fact/queue/종료 회귀/SPOT API268시험 중267통과·기존1skip,76.844초,exit0. backend Ruff 및 기본 mypy10파일 exit0. 전체17명세의 통과로 집계하지 않는다.

## HTTP 1단계 — fact 복구의 한 번 읽기 용량

복구 읽기에1MiB 상한을 추가했다. 다음 행이 남은 bytes 안에 다 들어오지 않으면
그 행을 해석하거나 저장하지 않고 다음 배치에서 원래 시작 위치부터 읽는다.

- `test_spool_recovery_read_budget_preserves_utf8_rows`: 한글 필드가 큰3건에서 첫 복구3행/기대2행의 RED(`fact-spool-bytes-red`, exit1)를 확인했다. 수정 후 첫2행·잔여1건과 다음1행의 원래 키/한글 내용을 대조했다. 실제 파일 읽기의 각 합계가1MiB 이하임도 확인했다.
- `fact-spool-bytes-green`: fact/queue/종료 회귀90시험 중89통과·기존 private F01자료 미제공1skip,46.301초,exit0. backend Ruff·mypy10파일 exit0.
- 이 단계는 읽기 bytes 경계다. 한 행 자체의 상한 초과 종결, 새 segment/전체 스풀 예산 및 임시 해석 사본 예약은 후속 필수 범위다.

## HTTP 1단계 — 상한을 넘는 단일 fact 스풀 행

한 행이1MiB를 넘으면 자동으로 건너뛰거나 자르지 않고 `UNCERTAIN spool-row-too-large`와
원본 절대경로·바이트 위치를 오류로 보고한다. 앞서 확인한 행의 복구와 원본은 유지한다.

- `test_oversized_spool_row_is_preserved_and_rejected`: 정상 앞 행 다음의 큰 행에서 오류가 없던 RED(`fact-spool-large-row-red`, exit1)를 확인했다. 수정 후 두 번의 같은 오류/위치, 원본 바이트 불변, CSV 앞1행·미복구1건을 대조했다.
- `fact-spool-large-row-green`: fact/queue/종료 회귀91시험 중90통과·기존 private F01자료 미제공1skip,exit0. backend Ruff·mypy10파일 exit0.
- 오류의 최종 상태/API 연결과 새 segment·원본 읽기 전용 정책 전체는 미완료다. 이 한 경계로 전체 복구를 통과 처리하지 않는다.

## HTTP 1단계 — fact 미복구 건수 집계의 행 메모리 제한

복구 외의 미복구 건수 집계도 최대64KiB 조각으로 읽는다. 긴 한 행을 통째로 올리지 않고,
빈 행·공백뿐인 긴 행·마지막 줄바꿈이 없는 행을 구분한다. 기존 집계 cache는 유지한다.

- `test_spool_pending_count_uses_bounded_reads`: 실제 파일에1MiB를 넘는 행을 만들고 파일 읽기 경계에서 무제한 읽기를 거부했다. 기존 행 반복의 RED(`fact-spool-count-red`, exit1) 뒤, writer 및 독립 집계의 정확한3건/2건과 cache 재조회 무 I/O를 확인했다.
- 기존 unreadable-spool 시험은 binary 읽기에도 같은 I/O 실패를 주입하도록 보완했으며 실패를 clean으로 바꾸지 않는 assertion을 유지했다.
- `fact-spool-count-green`: fact/queue/종료 회귀/SPOT API271시험 중270통과·기존 private F01자료 미제공1skip,75.979초,exit0. backend Ruff·mypy10파일 exit0.
- 읽기 조각 크기 제한이며 집계 총 스캔 시간의 보장은 아니다. 스풀 전체64MiB·4MiB segment·원본 읽기 전용 전환과 독립 복구 제어는 계속 남아 있다.

## HTTP 1단계 — fact 스풀 전체 미복구 bytes 상한

현재 활성 스풀과 미해결 schema-mismatch 보존 파일의 미복구 bytes 합계에64MiB 상한을
적용했다. 새 행까지 합산해 상한을 넘으면 추가 쓰기를 거절하고 기존 파일은 유지한다.
`spool_failure_count`와 `spool_last_error_code=spool_byte_limit`를 남기며 owner의 메모리
상태에도 사유를 전달한다. 이후 성공 때문에 과거 실패를 지우지 않는다.

- `test_spool_byte_limit_preserves_existing_pending_files`: 실제 활성/보존 파일과 다음 행을 합산한 경계에서 기존 거절0/기대1의 RED(`fact-spool-limit-red`, exit1)를 확인했다. 수정 후 거절1·정확한 사유·두 기존 파일 바이트와 미복구2건 불변을 대조했다. 정상 스풀 쓰기/복구 회귀도 유지했다.
- `fact-spool-limit-green`: fact/queue/종료 회귀/SPOT API272시험 중271통과·기존 private F01자료 미제공1skip,77.170초,exit0. backend Ruff·mypy10파일 exit0.
- 스풀 새4MiB segment·기존 단일 원본의 읽기 전용 전환, 직렬화 임시 bytes 선예약과 복구 독립 제어는 계속 구현해야 한다. 이 상한 추가를 R02/RR03 전체 완료로 보지 않는다.

## 2026-10-27 fact 스풀 변경 후 백엔드 전체 회귀

제품 코드 `4a753efe`에서 프로젝트 백엔드 검사와 같은
`python -m unittest discover -s backend/tests`를 격리 AppData/설정으로 실행했다.
`fact-spool-full-backend`:994시험 중993통과·기존 private F01자료 미제공1skip,
314.121초,exit0. 전체 stdout/stderr와 결과는 기존 `BRANCH_SYNC_20261026_4d2950c6/tdd/`
아래 해당 폴더에 보존했다. `log-review.json`에는 두 전체 로그의 해시와 오류/경고 분류가 있다.

- 기존 부정 입력/디스크 실패/종료 timeout 시험의 로그는 보존하며 실제 unittest FAIL/ERROR는 없었다.
- Starlette/httpx deprecation 경고는 남아 있다. 이 실행은 frontend/Electron/패키지 빌드 또는 현장 검증을 새로 수행한 것이 아니다.
- 관련 backend Ruff와 기본 mypy10파일도 최종 제품 변경에서 exit0이다. 이후에는 이 보고서와 CHANGELOG만 갱신했다.
- 이번5개 행동 수정은 b94bcc58·8f1d7657·78ed68ed·2a46f31a·4a753efe에 분리해 커밋했다. 전체 HTTP7단계/17명세, 새4MiB segment와 원본 읽기 전용 전환, master 통합 및 최종 설치본 검증은 계속 미완료다. 운영 서버에는 변경을 적용하지 않았다.

## HTTP 1단계 — 새 fact 스풀 분할과 기존 단일 원본 보존

새 임시 기록은 `<기존 스풀 파일명>.segments-v1` 폴더의 고유 순번/UUID 파일에 저장한다.
한 파일은4MiB 이하이며 기존 단일 스풀에는 덧붙이거나 복구 후 삭제하지 않는다.
잘못된 기존 스풀도 자동 이동하지 않고 원래 경로/위치의 UNCERTAIN 오류로 남긴다.
새 segment만 해당 데이터 복구 후 정리하며 기존20행/1MiB 읽기와64MiB 미복구 상한을 유지한다.

- `test_segmented_spool_rotates_and_preserves_legacy_source`: 기존2,331bytes가4,350,331bytes로 늘어나는 RED(`fact-spool-segments-red`, exit1)를 확인했다. 수정 후 새2파일 각각4MiB 이하·원본 불변·13개 관측 키와 실제 fact CSV 내용·재시작 중복 없음·미복구0을 확인했다.
- 기존 파일 삭제/오류 파일 이동을 기대하던 fixture를 승인된 읽기 전용 원본 정책으로 변경했다. 기존 성공 데이터·미복구 건수·실패 판정 assertions를 유지하고, 디스크 실패 주입도 실제 새 segment 쓰기 경로에 적용했다.
- `fact-spool-segments-green`: fact/queue/종료 회귀/SPOT API273시험 중272통과·기존 private F01자료 미제공1skip,77.204초,exit0. backend Ruff·mypy10파일 exit0.
- 새 segment의 부분 쓰기/닫기 불확실성, 임시 사본 선예약·독립 복구 예약과 나머지17명세 전체는 계속 남은 범위다. 이전994시험 전체 결과를 이 제품 변경 이후의 전체 검사로 재사용하지 않는다.

## HTTP 1단계 — 새 fact 스풀 닫기 실패의 불확실성 유지

실제 bytes를 쓴 뒤 close가 실패하면 해당 writer를 미확정 상태로 유지한다. 추가 segment를 만들거나 자동 복구하지 않고 원본과 오류 경로를 보존한다. 이전 pending 건수 cache도 무효화해 실제 남은 행을 다시 확인한다.

- `test_spool_close_failure_blocks_later_segments`: 실제 파일 쓰기 후 close 오류를 주입했다. 기존 동작은 다음 접수에서 새 파일을 만들어 2파일/기대1파일로 RED(`fact-spool-close-red`, exit1)였다. 수정 후 원본 불변·추가 쓰기 거절·UNCERTAIN 복구 오류·실제 pending1을 확인했다.
- `fact-spool-close-green`: fact/queue/종료 회귀95개 중94통과·기존 private F01자료 미제공1skip,46.405초,exit0. 현재 작업 폴더의 `branch-audit-current-ruff`와 `branch-audit-current-mypy`는 각각 exit0이며 기본 mypy 범위는10파일이다.
- 동일 writer의 close 실패 처리 범위다. 짧은 쓰기 반환값, 읽기 실패의 독립 집계, 행 크기 계약 및 전체17명세는 계속 남아 있다. 강제 종료 복구용 영속 저널을 추가한 것은 아니다.

## HTTP 1단계 — 읽을 수 없는 스풀의 거짓 0건 방지

독립 manifest 생성에서 임시 기록을 읽지 못하면 OSError를 전달한다. 실제 미복구0건과 확인 불가를 구분하며, 정상 읽기가 돌아오면 원본을 그대로 집계한다.

- `test_manifest_rejects_unreadable_spool`: 실제1행 파일의 읽기만 PermissionError로 막았을 때 기존 manifest가 정상 반환되는 RED(`fact-spool-read-error-red`, OSError not raised, exit1)를 확인했다. 수정 후 오류 전달·읽기 복구 뒤 pending1·원본 불변을 확인했다.
- `fact-spool-read-error-green`: fact/queue/종료 회귀96개 중95통과·기존 private F01자료 미제공1skip,47.775초,exit0. backend Ruff·기본 mypy10파일도 exit0이다.
- 명시적으로 전달된 runtime pending과 독립 재계산 경로는 구분한다. 이 수정은 독립 집계의 I/O 오류 은폐를 제거하며 전체 metadata/validator 계약 완료는 아니다.

## HTTP 1단계 — 스풀의 짧은 쓰기 반환 확인

스풀 write의 반환 길이가 요청 bytes보다 작으면 성공으로 확정하지 않고 UNCERTAIN 상태를 유지한다. 같은 writer에서 추가 쓰기/자동 복구를 차단하고 실제 부분 원본을 보존한다.

- `test_short_spool_write_blocks_retry`: 실제 파일에 절반만 기록하는 경계에서 기존 실패0/기대1의 RED(`fact-spool-short-write-red`, exit1)를 확인했다. 수정 후 부분 bytes·거절 사유·다음 쓰기 차단·pending1·CSV 미생성을 대조했다.
- `fact-spool-short-write-green`: fact 모듈39시험 통과(0.807초, exit0). backend Ruff·기본 mypy10파일도 exit0. 전체 백엔드 회귀는 남은 스풀 경계를 반영한 뒤 수행한다.

## HTTP 1단계 — 새 스풀 행과 복구 크기 계약 일치

새 fact 스풀의 직렬화 행이1MiB를 넘으면 파일에 추가하지 않고 `spool_row_too_large`로 명시적으로 실패 처리한다. 기존 초과 원본은 읽기 전용 UNCERTAIN 처리대로 보존한다. 이 제한은 JPEG 크기 제한에 적용하지 않는다.

- `test_spool_rejects_rows_above_recovery_limit`: 정확히1MiB의 실제 행 뒤1바이트 초과 행을 보냈을 때 기존 실패0/기대1의 RED(`fact-spool-write-size-red`, exit1)를 확인했다. 수정 후 기존 bytes 불변·초과 행 거절·다음 정상 행 접수·두 배치의 실제 CSV 복구/내용·과거 실패1 유지·잔여0을 대조했다.
- `fact-spool-write-size-green`: fact 모듈40시험 통과(0.816초, exit0). backend Ruff·기본 mypy10파일 exit0. 직렬화 전에 필요한 임시 메모리의 선예약과 전체 출력별 계약은 후속 범위다.

## HTTP 1단계 — 미해결 보존 스풀의 독립 집계

runtime writer와 독립 manifest가 같은 파일 목록으로 잔여를 계산한다. 현재 단일 파일·새 segment뿐 아니라 기존 schema-mismatch 보존 파일도 포함하고, 어느 파일이든 읽기 실패를 정상0건으로 바꾸지 않는다. 보존 파일을 자동 복구하거나 삭제하지 않는다.

- `test_manifest_counts_unresolved_spool_archives`: 실제 세 종류 파일에서 독립 manifest2건/기대3건의 RED(`fact-spool-archive-count-red`, exit1)를 확인했다. 수정 후 양쪽3건·보존 파일 읽기 오류 전달·원본 불변을 대조했다.
- 기존 bounded-read 시험의 독립 집계 기대값도 포함된 보존1행을 더한3건으로 맞췄다. 읽기 크기 제한과 runtime cache 검사는 유지했다.
- `fact-spool-archive-count-green`: fact 모듈41시험 통과(0.834초, exit0), backend Ruff·기본 mypy10파일 exit0. 전체 백엔드 검사를 이어간다.

## 2026-10-27 스풀 분할·실패 처리의 전체 백엔드 회귀

제품 코드 `58fd675f`에서 `python -m unittest discover -s backend/tests`를 격리 AppData/설정으로 실행했다. `fact-spool-integrity-full-backend` 결과는 **1,000시험 중999통과·기존 private F01자료 미제공1skip**,315.091초,exit0이다. 분할/기존 원본 보존, close·짧은 쓰기, 독립 집계 읽기 오류,1MiB 행 제한과 과거 미해결 파일 집계 변경을 포함한다.

- stdout150,036bytes SHA256 `6c718cbe034b5791453b4abadbdb23b7546124cd9813e4e27eeb2b5c582fb39c`, stderr45,964bytes SHA256 `bb4dbc0e3c2f07bd64272790924421c5b88df59a4cd094254d9693e46af1cc86`.
- `log-review-r2.json`에서 전체 로그와 unittest 결과를 대조했다. 이미지 manifest 초기화 Traceback1개는 `test_csv_image_startup.py`의 의도된 읽기 오류이며, 첫 로그 검사기의 포괄적인 Traceback 분류를 바로잡았다. 제품 검사를 반복하거나 실패 원문을 삭제하지 않았다. unittest FAIL/ERROR는 없고 Starlette/httpx deprecation 경고는 남아 있다.
- 최종 제품 변경의 backend Ruff·기본 mypy10파일은 exit0이다. 전체 회귀 이후에는 보고서와 CHANGELOG만 편집했다.
- 이번 묶음의 코드 commit은 f5ae671b·272bbb52·d20fea81·facaff71·e6656ce0·58fd675f이다. 임시 메모리 선예약, 생산/출력 영속 대조, 부분 CSV/JPEG 복구, 압력 제어 및 전체7단계/17명세·최종 설치본·master 통합은 미완료다. 이번 결과를 frontend/Electron/설치본/현장 전체 통과로 확대하지 않는다.

## HTTP 1단계 — fact 접수 직렬화 사본의 선예약

fact owner에서 JSON 컨테이너를 분리하고 인코딩 길이를 먼저 계산한다. source 문자열은 불변 참조를 공유하며, 실제 직렬화 문자열/UTF-8 bytes를 만들기 전에 두 사본의 공간을 예약한다. 접수 성공 후 문자열 임시분을 해제하고 최종 bytes 예약은 기존 완료 시점까지 유지한다. 부족하면 기존 관측 ID와 `pending_byte_limit`를 반환한다.

- `test_serialization_scratch_respects_pending_budget`: 실제 첫6MiB 입력의 쓰기를 지연하고 다음6MiB 입력을 보내 기존 ACCEPTED/기대REJECTED_LIMIT의 RED(`fact-serialization-budget-red-r2`, exit1)를 확인했다. 첫 실행은 시험 클래스명을 잘못 지정한 로더 오류로 별도 보존했다. 수정 후 첫 실제 저장·두 번째 거절·잔여 공간 반환·다음 정상 접수/저장을 대조했다.
- 기존 bytes 한계 시험의 기대식을 원본1개에서 직렬화 사본까지 포함한2개로 변경했다. 기존 예약 유지·반환·실제 저장 데이터 assertions는 유지했다. 새 내부 반환값의 타입 표기도 보완했다.
- `fact-serialization-budget-green-r2`: 관련19시험 중18통과·기존 private F01자료 미제공1skip,exit0. backend Ruff·기본 mypy10파일 exit0.
- 현재는 UTF-8 길이를 기준으로 두 사본을 예약한다. Python의 넓은 Unicode 문자열 표현, decode/출력 사본과 CSV·이미지 경로의 선예약은 아직 추가 검증·보완이 필요하다. 이 접수 경계나 앞선1,000시험을 현재 전체 예산 계약의 완료로 표시하지 않는다.

## HTTP 1단계 — 직렬화 문자열의 Unicode 폭 반영

직렬화 전에 UTF-8 bytes 길이와 JSON 문자열의 문자 수·최대 문자 폭(1/2/4bytes)을 계산한다. 한 개의 이모지 때문에 전체 문자열이 넓어지는 경우도 포함해 예약한다. 원본 문자열 참조는 공유하고 컨테이너를 분리하므로 원본의 후속 중첩 수정이 직렬화 길이를 바꾸지 않는다. 이 값은 payload/문자 내용 공간이며 Python 객체 overhead나 전체 RSS 상한은 아니다.

- `test_serialization_budget_accounts_for_wide_unicode_text`:6MiB 영문과 이모지1개 입력이 기존 ACCEPTED로 통과하는 RED(`fact-wide-serialization-red`, exit1)를 확인했다. 수정 후 초과 입력 거절·예약0·다음 작은 한글/이모지/제어문자 입력의 실제 저장·예약 반환을 확인했다.
- `fact-wide-serialization-green`: fact queue/fact/종료/SPOT API280시험 중279통과·기존 private F01자료 미제공1skip,76.682초,exit0. 전체 로그 검사에 unittest FAIL/ERROR/Traceback은 없고, 기존 오류 주입 로그·asyncio 지연 알림·Starlette 경고는 보존한다. backend Ruff·기본 mypy10파일도 exit0.
- `verify_fact_json_budget.py`의 독립 대조는269개 JSON 자료의 실제 직렬화 bytes·문자 수·문자 폭, 정확한 경계/1바이트 부족, 공유 중첩 참조 분리와 잘못된6입력을 확인해 exit0이었다. 근거 `fact-json-budget-differential.json`은 소스 SHA256에 결합돼 있다. 이269개는17개 필수 시나리오에 추가 통과로 합산하지 않는다.
- fact 접수 직렬화 경계의 구현이다. decode·writer 출력·스풀 직렬화 및 CSV·이미지 경로의 임시 사본 예약, 컨테이너/인덱스 메모리 계측과 전체7단계/17명세는 계속 남아 있다. 직전58fd675f의 전체1,000시험에는 이후 직렬화 변경이 포함되지 않으므로 최신 전체 회귀로 표시하지 않는다.

## HTTP 1단계 — fact JSON 해석 전 예약과 실패 ID

큐의 불변 이벤트에 접수 당시 JSON 문자열 크기와 관측 ID를 유지한다. worker는 UTF-8 해석 문자열과 결과 문자열 공간을 먼저 예약하고, 해석 후에는 공유 문자열을 한 번만 계산한 실제 내용 크기로 줄인다. 원본 bytes와 해석 결과를 놓은 뒤에만 예약을 반환한다. 공간이 부족하면 `decode_byte_limit`와 원래 ID를 실패로 기록하고 뒤의 항목을 처리한다. 실패한 접수 건을 정상 drain으로 표시하지 않는다.

- `test_decode_budget_failure_records_admitted_identity`: 초기화를 지연해 6/4/2MiB 입력을 먼저 접수했다. 기존 실패0/기대1의 RED(`fact-decode-budget-red`, 이번 재점검 `branch-final-audit-decode-20261027`, exit1)를 확인했다. 수정 후 첫 ID 실패, 뒤 두 ID의 실제 CSV 저장, 접수/완료3·잔량/예약0과 close 실패 유지가 일치했다.
- 기존 직렬화 시험의 첫 입력은 해석까지 정상 수용할 수 있는5MiB로 변경했다. 두 번째6MiB 거절·첫째/셋째 실제 저장을 유지했다. 기존 bytes 시험은 source와 processing을 분리해 검산하고 합산16MiB 제한을 확인한다.
- `fact-decode-budget-green`: 관련21시험 중20통과·기존 private F01자료 미제공1skip,6.845초,exit0. backend Ruff·기본 mypy10파일도 exit0이다.
- 이 구현은 fact JSON 해석 경계다. writer 출력·스풀 사본 및 CSV/이미지 선예약, 영속 실패 추적·복구/압력 제어·전체17명세는 계속 남아 있다. 직전 전체 회귀를 이 변경 후의 전체 검증으로 표시하지 않는다.

## HTTP 1단계 — 처리 실패와 디스크 실패의 합산

worker 처리 실패와 실제 writer 실패를 별도 누적한 뒤 합산한다. 두 값의 최댓값으로 덮어써 서로 다른 실패가1건으로 줄어드는 문제를 수정했다. 실제 실패 발생 때만 원래 관측 ID/사유를 갱신하고, 다음 정상 쓰기나 스풀 복구로 과거 실패를 지우지 않는다.

- `test_processing_and_disk_failures_are_counted_separately`: 메모리 부족 뒤 실제 append1회 실패를 주입했다. 기존1건/기대2건의 RED(`fact-failure-accounting-red`,exit1)를 확인했다. 수정 후 실패2건·각 ID/사유의 구조화 로그·뒤2개 실제 CSV 저장·스풀/메모리 잔량0·close 실패 유지가 일치했다.
- `fact-failure-accounting-green`: 관련22시험 중21통과·기존 private F01자료 미제공1skip,6.979초,exit0. backend Ruff·기본 mypy10파일 exit0.
- 이는 오류 집계와 원래 ID 기록 보완이다. 정상 복구가 과거 실패를 면제하지 않으며, 영속 data-trace/최종 출력별 판정이나 전체17시나리오 완료를 대신하지 않는다.

## 2026-10-27 fact 해석·실패 집계 후 전체 백엔드 회귀

제품 commit `6daf4fdb2f5c45caede5f61e580969410755fe98`에서 격리 AppData/설정의 `python -m unittest discover -s backend/tests`를 실행했다. `fact-decode-accounting-full-backend`는 **1,004개 중1,003통과·기존 private F01자료 미제공1skip**,319.785초,exit0이다. 원시 로그·결과·전체 로그 대조는 `BRANCH_SYNC_20261026_4d2950c6/tdd/fact-decode-accounting-full-backend`에 있다.

- stdout150,036bytes SHA256 `5259e9df9094dd341168727d7f59894018e90323b8a1dc263efbc4d8a334d8f3`, stderr46,609bytes SHA256 `ab4740a475482fec6d410cdc9d67bb35a66162545718f2081a0d808bff97331f`.
- `log-review.json`에서 unittest FAIL/ERROR0을 확인했다. 기존 전체 실행과 정규화 비교 시 새 오류 문구는 새 실패 시험의 `SPOT fact processing failed`뿐이다. traceback1개는 `test_csv_image_startup.py`의 `injected manifest read failure` 주입과 대조했다. 기존 경고는 유지한다.
- backend Ruff·기본 mypy10파일은 이번 제품 변경에서 exit0이다. 이후에는 보고서/CHANGELOG만 편집했다. frontend/Electron/설치본/현장 검사를 새로 수행했다는 뜻은 아니다.
- 독립 대조 `fact-decode-accounting/decoded-payload-verification.json`은261자료의 해석 문자열 내용 크기·접수 시 상한·공유 JSON key의 중복 청구 방지를 확인했다. 현재 queue SHA256 `06e775f16e442d8f6e502d1c83209898fa4ff37df6d75096af5a024272178812`에 결합됐다. R1 검증 스크립트의 getsizeof 기준 문자열에는 선택적 UTF-8 cache까지 포함돼 비교가 실패했으며, 원문/로그를 보존하고 R2에서는 독립 고정폭 인코더로 문자 내용만 대조했다. 제품 코드의 변경은 없었다. 이 검사는 선택적 cache·객체 overhead·전체 RSS 보장이 아니다.
- 이번 제품 변경은 `ab0da354`, `6daf4fdb`다. writer/스풀 및 CSV/이미지 임시 메모리, 영속 추적·부분 쓰기 복구·압력 제어·전체7단계/17명세·최종 설치본과 master 통합은 계속 미완료다. 운영 서버에는 적용하지 않았다.

## HTTP 1단계 — owner의 fact CSV 출력 사본 선예약

owner가 writer에 합산 예산 예약 경로를 연결한다. 실제 행을 렌더링하기 전에 열의 길이·CSV quoting·UTF-8 길이·문자 폭을 계산하고, CSV 내부 레코드 버퍼/성장 사본·최종 문자열·인코딩/파일 버퍼 공간을 예약한다. writer와 파일을 놓은 뒤 예약을 반환한다. 부족하면 `csv_output_byte_limit`와 원래 접수 ID의 실패로 종결하고 무제한 스풀 할당으로 우회하지 않는다.

- 버퍼 계산 근거는 [CPython3.12.6 _csv.c](https://raw.githubusercontent.com/python/cpython/v3.12.6/Modules/_csv.c)의 UCS4 레코드·32768문자 증가 단위와 출력 문자열 생성이다. 실제 사용 중 Python3.12의 보수적 작업 공간 계산이며 프로세스 RSS 상한이 아니다. 원본 문자열 참조는 다시 청구하지 않는다.
- `test_csv_output_budget_failure_preserves_identity`:5MiB 실제 출력 필드를 보냈을 때 기존 실패0/기대1의 RED(`fact-csv-output-budget-red`,exit1)를 확인했다. 수정 후 첫 ID/사유·스풀 우회 없음·예약 반환·다음 작은 ID의 실제 CSV 저장·과거 실패 유지가 일치했다.
- `fact-csv-output-budget-green`: queue/fact64시험 중63통과·기존 private F01자료 미제공1skip,8.186초,exit0. backend Ruff·기본 mypy10파일 exit0.
- 이 경계는 owner를 통한 fact CSV 렌더링이다. fact 구성·스풀 직렬화/복구·파일 읽기 임시 공간 및 통합 CSV/이미지 경로의 전체 예약은 계속 남아 있다. 앞선1,004시험 전체 결과는 이번 제품 변경을 포함하지 않는다.

## HTTP 1단계 — 초과 스풀 행의 직렬화 전 거절

JSON 크기 계산을 `persistence_payload.py`로 옮겨 접수와 스풀에서 재사용한다. 함수 본문이 이름 변경 외에 기존 구현과 같은지 대조했다. 스풀의1MiB 행 제한과64MiB 미복구 제한을 실제 문자열/bytes 생성 전에 확인하며, 원래 파일과 다음 정상 행의 저장/복구를 유지한다.

- `test_oversized_spool_rejects_before_serialization`:12MiB 입력의 생성은 측정에서 제외하고 스풀 거절 동안의 추가 할당을 tracemalloc로 측정했다. 기존 최고31,462,003bytes/상한16,777,216bytes의 RED(`fact-spool-preflight-red`,exit1)를 확인했다. 수정 후 상한 이하·원본 불변·명시적 행 크기 실패1·다음 실제 정상 복구를 확인했다.
- `fact-spool-preflight-green`: fact/queue65시험 중64통과·기존 private F01자료 미제공1skip,8.735초,exit0. backend Ruff와 공통 모듈을 추가한 기본 mypy11파일 exit0.
- 이는 초과 입력의 사전 거절이다. 허용된 스풀 행의 실제 임시 사본도 owner의 다른 대기 자료와 합산하는 예약, 복구 읽기·fact 구성 등의 남은 메모리 경계는 계속 구현한다. tracemalloc 측정은 전체 프로세스 RSS 보장이 아니다.

## HTTP 1단계 — 허용 스풀 행의 owner 예산 합산

허용된 JSON 행도 직렬화 문자열·줄바꿈 사본·UTF-8 bytes와 파일 버퍼 공간을 owner의 기존 대기/처리 예산에 추가 예약한다. 파일을 닫고 payload 참조를 놓은 뒤에만 반환한다. 공간이 없으면 기존 파일에 쓰기 전에 `spool_memory_byte_limit`로 실패를 기록하며, 디스크 상한 거절과 구분한다.

- `test_spool_serialization_shares_owner_budget`: 실제 첫 append를 지연해 큐를 채운 뒤 해당 append에1회 오류를 주입했다. JSON escape로 커지는 유효 행에서 기존 스풀 실패0/기대1의 RED(`fact-spool-shared-budget-red`,exit1)를 확인했다. 수정 후 메모리 사유·스풀/메모리 잔량0·실패 ID의 저장 누락이 설명됨·이후 작은 ID의 실제 저장 및 중복 없음이 일치했다. 이 합성 한도 시험은 운영 데이터 손실 발생의 근거가 아니다.
- `fact-spool-shared-budget-green-r2`: 파일 버퍼 예약까지 포함한 최종 상태의 fact/queue66시험 중65통과·기존 private F01자료 미제공1skip,9.268초,exit0. backend Ruff·기본 mypy11파일 exit0.
- 전체 복구 읽기·fact 구성·파일 검산 임시 공간, 통합 CSV/이미지 및 영속 추적/압력 제어와17개 전체 시나리오는 계속 남아 있다. 다음 관련 회귀 범위 검증을 수행한다.

## 2026-10-27 fact 출력·스풀 예약 후 관련 회귀

제품 commit `446fb62d76afc852cf013de58b6d925aba59efd0`에서 fact/queue/정상 종료/SPOT API/온도 시계5모듈을 실행했다. `fact-output-shared-budget-regression`은 **293시험 중292통과·기존 private F01자료 미제공1skip**,80.319초,exit0이다. backend Ruff 및 기본 mypy11파일도 최종 제품 상태에서 exit0이다.

- stdout17,106bytes SHA256 `07fdddf1ec43139e68cedc8a1c52549be46410bddaa78271aec449408a0856f8`, stderr10,500bytes SHA256 `055fb71f1d6f3e5c9659139b88b3d1dd7ff144d58c8234e47ed1ea7bfa25c23a`. `log-review.json`에서 unittest FAIL/ERROR·Traceback0, 기존 전체 검사 대비 새로운 정규화 오류 문구0을 확인했다.
- `fact-output-budget/csv-preflight-verification.json`:258개 실제 CSV 자료의 문자/UTF-8 길이·문자 폭이 계산과 일치했다. ASCII·따옴표/한글/이모지·제어문자·넓은 문자열4조건의 실제 파일 쓰기와 tracemalloc 최고치가 예약량 이내였으며 내용 readback도 일치했다. 전체 RSS 또는 모든 경로의 예약 완료를 뜻하지 않는다.
- 근거는 세 제품 파일의 SHA256과 Python3.12.6에 결합했다. `spot_observation_fact.py`=`628bcd09c50aee547e9f067c6b40405b341af9a3e3d8e13d02036da6e4a81abc`, `spot_observation_queue.py`=`30893d7e43bb9ccc00fcae4febb91883a524511fa9c1d471dbcd36974e61cb25`, `persistence_payload.py`=`3c253503666c6fce2714f20970fb9e3f7c1d98d7dba01fe9831d0b9a678e8d9a`.
- 이번 제품 변경은 `877bf4f0`, `a7945a51`, `446fb62d`다. 이전 전체1,004시험은 이 세 변경 전 결과로 보존한다. 이번 결과를 최신 전체 backend/frontend/Electron/설치본/현장 통과로 확대하지 않는다. 전체7단계/17명세와 master 통합·최종 빌드는 계속 남아 있다.

## 2026-10-27 완료 재점검에서 발견한 health 시험 경계

사용자 요청으로 `e9d9a6f8`에서 전체 backend를 다시 실행했다. `branch-completion-audit-e9d9-full-backend`는1,007개 중1,005통과·1실패·기존 F01 1skip,318.965초,exit1이었다. `test_executor_backlog_is_separate_from_worker_execution`에서 기대50ms 이상에46.6227ms가 기록됐다. 단독 모듈9개는 통과했지만 전체 실패를 지우지 않고 보존했다.

- 원인 재현: task 생성 직후부터60ms를 기다리던 fixture에 event-loop30ms 지연을 넣었다. 실제 제출부터의 대기는33.2525ms로 짧아져 예상한 assertion이 실패했다(`health-backlog-scheduling-red`,exit1).
- 수정: 실제 단일 ThreadPoolExecutor의 submit 완료를 확인한 뒤60ms hold를 시작한다. 제품 health 계측과50ms assertion은 그대로다. 지연 사례를 유지한 `health-backlog-scheduling-green`의9시험 통과(0.516초,exit0), 해당 시험 Ruff exit0.
- commit `ce607541`. 이는 시험의 시작 경계 수정이며 현장 성능 기준을 완화하거나 서버 응답 시간을 개선한 변경이 아니다. 원래 전체 실패와 이전 감사는 당시 결과로 유지한다.

## HTTP 1단계 — fact 복구 읽기·해석·보존 자료의 owner 예산 합산

복구 파일의 읽기 범위를 실제 남은 크기와1MiB 중 작은 값으로 고정한다. 읽은 bytes와 읽기/strip 사본·파일 버퍼를 먼저 예약하고, 각 행의 JSON 해석 공간과 보존할 문자열 공간도 owner의 기존 queue/inflight와 합산한다. 읽기 사본은 CSV 렌더링 전에 해제하며, 보존 문자열 예약은 참조를 놓은 뒤 반환한다. 기존20행/1MiB 제한과 실제 복구 성공 후에만 offset을 전진하는 동작을 유지한다. 공간 부족은 `spool_recovery_byte_limit`로 전달한다.

- `test_spool_recovery_shares_owner_budget_and_preserves_source`: 실제20행 스풀과12MiB 이상의 큐 원본을 두었다. 기존 초기화 ready/기대failed의 RED(`fact-recovery-shared-budget-red`,exit1)를 확인했다. 수정 후 원본 bytes·offset0·아직 처리하지 않은 접수12건 보존, 임시 processing 예약0, 정상 drain 금지를 확인했다. 별도 충분한 공간의 owner에서는 같은20행과 후속 관측999가 실제 CSV에 정확히 저장됐다. 첫 owner의12건을 저장 완료로 집계하지 않는다.
- `fact-recovery-shared-budget-green`:67시험 중66통과·F01 1skip,9.492초,exit0. backend Ruff·기본 mypy11파일 exit0. commit `5cb22f5b`.
- JSON 파싱 오류는 위치/사유를 유지한 작은 오류로 연결하고 전체 decoded 문서를 예외에 붙잡아 두지 않는다. 이 작업은 일반 복구 payload 사본의 예약이며 모든 Python 객체/인덱스·프로세스 RSS 상한의 입증은 아니다.
- 독립 복구 제어·최초 owner 가용성/접수 결과의 전체 계약, fact 구성/파일 검산 및 통합CSV/이미지 임시 사본은 계속 남은 범위다.

## HTTP 1단계 — 과거 복구 값의 문자열 확장 예약

과거 JSON 필드가 dict/list인 경우 CSV 문자열화 과정에서 따옴표가 추가될 수 있다. 일반 문자열의4배 입력 크기 예약 외에 같은 크기를 추가로 확보한 뒤 변환한다. 기존 자료를 다른 값으로 바꾸거나 임의로 삭제하지 않는다.

- `test_recovery_reserves_expanded_container_text`: 실제 복구한 Unicode/따옴표 문자열의 보존 공간320,064bytes가 예약167,764bytes보다 큰 RED를 확인했다. 이후 실제 CSV 확인에서 fixture의 완료 시각 누락 때문에 관측 키가 비어 저장되지 않는 별도 실패가 났다. 그 실패를 확인하기 전에 `1b7b104d`를 커밋한 절차 오류도 기록한다. 이 중간 실행은 GREEN으로 집계하지 않는다.
- 완료 시각과 `legacy:1` 키 확인을 fixture에 추가한 뒤 제품 소스를 `5cb22f5b`와 같게 되돌려 재현했다. `fact-recovery-container-budget-red-r2`는167,956/320,064bytes의 예상 assertion 실패(exit1)였다. 추가 예약을 복원한 최종 `fact-recovery-container-budget-green-r2`는68시험 중67통과·F01 1skip,9.812초,exit0이며 실제 CSV 값·잔여0까지 확인했다.
- 최종 제품 Ruff·mypy11파일 exit0이며, 후속 fixture만 수정한 `671865ab`의 Ruff도 exit0이다. 원시 실패·수정 결과를 모두 보존한다. 이 작은 경계 검증을 전체17명세 완료로 집계하지 않는다.

## 2026-10-27 복구 메모리·health 시험 보완 후 전체 회귀

최종 코드 `671865ab6bcd2c34ee991ee90eae8f790d34728f`에서 격리 AppData/설정의 `python -m unittest discover -s backend/tests`를 실행했다. `fact-recovery-and-health-full-backend`는 **1,009개 중1,008통과·기존 F01자료 미제공1skip**,315.855초,exit0이다. 제품·시험 변경 없이 실행을 마쳤으며 이후에는 이 보고서와 CHANGELOG만 정리했다.

- stdout150,036bytes SHA256 `9b4dd0e836229b4997f157561616c0a03273548e57367461a0f30b0e2bd69ec7`, stderr46,285bytes SHA256 `87a4aab7ce99f6f46767870c6d38c684c644b8f59a378fdee601f180fc9fce99`. 전체 로그 대조 `log-review.json`에 unittest FAIL/ERROR0을 확인했다.
- manifest 초기화 traceback은 기존 `test_csv_image_startup.py:120`의 의도적 읽기 오류다. 이전 전체 검사 대비 추가된 `preserving primary error stages=shutdown_evidence_peers` 문구는 `test_image_shutdown_evidence.py`의 부분 시작 실패·동시 종료 시나리오 및 최종 영수증0/2 검사와 대조했다. 검사 실패로 숨기거나 운영 장애로 확대하지 않는다. 기존 Starlette/httpx 경고는 유지한다.
- 최종 제품 파일 SHA256: `spot_observation_fact.py`=`4f35691e5e3b1d0eb0f90348dee1d4cee654512084d08c4461b2b37d2d133a43`. 시험 SHA256은 `health_timing`=`0c2d35c3a761d50cac186960542eccf174204f022fc194f431a86850343f84c1`, `spot_observation_fact`=`9b2642618318d2118484f4f1fc5c6eadd78c1b302c5fd0cd7458e24d0b3e0fba`, `temperature_fact_queue`=`27092d114d2c2e8325a1ce183077a2eb9c7b8aa60afc14dcd6dc001c16fb6e2d`다.
- 변경 commit은 `ce607541`, `5cb22f5b`, `1b7b104d`, `671865ab`다. 첫 실패한 전체 검사와 잘못된 fixture의 중간 결과는 보존한다. 전체 HTTP7단계/17명세, 통합CSV/이미지·fact 구성/검산 예산, 영속 대조·복구 제어, 최종 설치본과 master 통합은 미완료다. 서버 적용은 하지 않았다.

## HTTP 1단계 — 통합 CSV 접수 직렬화 공간 선예약

기존 CSV 원본 bytes와 변환 중인 작업 공간을 합산한다. JSON 문자열·UTF-8 bytes를 생성하기 전에 공통 크기 계산으로 공간을 확보하고, 접수 성공 시 실제 원본 bytes만 기존 pending 예약으로 옮긴다. 예약을 이중 청구하지 않으며 거절·예외·정상 접수 뒤 임시 참조를 놓고 나머지 예약을 반환한다. 기존 canonical compact JSON·원본 hash·EMA 의미는 유지한다.

- `test_csv_serialization_shares_pending_budget_before_allocation`: 실제 writer를 지연해20MiB 원본을 유지한 상태에서24MiB 입력을 보냈다. 원본만 합치면64MiB 이하지만 직렬화 공간을 합치면 넘는다. 기존 ACCEPTED/기대 REJECTED_LIMIT의 RED(`csv-serialization-shared-budget-red`,exit1)를 확인했다.
- 수정 후 생성 전 `pending_byte_limit` 거절, 원래 생산 순번2·hash 없음·drop1, 추가 할당 상한, 임시 예약0을 확인했다. 뒤의 작은 순번3은 실제 CSV에 저장됐고 종료 후 전체 예약0이었다. 첫 원본과 작은 후속값만30/32로 남는다.
- `csv-serialization-shared-budget-green`: CSV service/runtime62시험 통과,13.624초,exit0. 예약 반환 assertion을 보완한 최종 단독 검사도 exit0. backend Ruff·기본 mypy11파일 exit0. commit `b31b6172`.
- 상태의 `pending_processing_payload_bytes`는 현재 접수 직렬화 예약을 포함하고 `pending_payload_bytes`는 원본과 그 작업 공간의 합계다. worker의 decode·출력 행/CSV 렌더링 공간은 아직 남아 있다. 이 필드를 전체 CSV 메모리 또는 프로세스 RSS 검증 완료로 해석하지 않는다.

## HTTP 1단계 — 비활성·종료 CSV 접수의 우선 판정

같은 lifecycle/config 잠금에서 생산 ID와 설정을 잡은 뒤 저장 OFF·종료 여부를 먼저 판정한다. 저장하지 않을 큰 입력을 직렬화하거나 메모리 부족으로 집계하지 않는다. 이 경로는 원본 bytes를 만들지 않으므로 hash를 생성하지 않는다. 활성 저장의 잘못된 입력·용량 거절 계약은 유지한다.

- `test_csv_inactive_admission_skips_large_payload_work`:40MiB 입력에 기존 REJECTED_LIMIT/기대 DISABLED의 RED(`csv-inactive-large-payload-red`,exit1)를 확인했다. 수정 후 OFF는 DISABLED, 종료는 CLOSED, 생산 순번1/2·원본 hash 없음·pending/drop0과 파일 생성 없음이 일치했다. 저장을 켜고 재시작한 뒤 순번3은 실제 CSV에 기록됐다.
- `csv-inactive-large-payload-green`: CSV service/runtime와 실제 소비·온도 clock·history5모듈95시험 통과,28.593초,exit0. backend Ruff·기본 mypy11파일 exit0. commit `5e42daf2`.
- `csv-serialization-budget/compact-json-verification.json`:266개 한글·이모지·제어문자·중첩 JSON의 기존 canonical bytes/hash 일치와 보수적 예약 상한을 대조했다. 이는 compact 출력의 크기 계산 대조이며17개 전체 시나리오에 추가 통과로 합산하지 않는다.

## 2026-10-27 CSV 접수 메모리 보완 후 전체 백엔드 회귀

최종 제품 commit `5e42daf22bf19acda891e813d02b3a54e5ec3846`에서 격리 AppData/설정의 `python -m unittest discover -s backend/tests`를 실행했다. `csv-serialization-full-backend`는 **1,011개 중1,010통과·기존 private F01자료 미제공1skip**,322.370초,exit0이다. 실행 중 제품·시험·문서를 변경하지 않았다.

- 전체 stdout/stderr를 읽고 직전1,009시험의 로그와 정규화 대조했다. unittest FAIL/ERROR0, 새 오류 문구0이다. manifest 초기화 traceback은 기존 `test_csv_image_startup.py`의 오류 주입이며 Starlette/httpx 경고는 유지한다.
- `csv-serialization-budget/verification.json`에 RED·GREEN·전체 회귀의 명령/종료 코드·로그 해시와 최종 소스 해시를 연결했다. repository.py SHA256=`17b63197523a9490c2e052759f2454e6348570383da743009946eb3f796c501e`, 시험 SHA256=`315d2a945ced0e2604177a520ffc54a0a0a02148f5692bf8545100387f21a583`다.
- 전체7단계/17명세는 계속 미완료다. 다음 CSV decode·출력 사본, 이미지·fact의 남은 예산, 영속 대조·부분 쓰기 복구·압력 제어·화면 연동, 최종 설치본 검증과 master 통합이 남아 있다. 이번 변경은 개발 브랜치 범위이며 운영 서버에 적용하지 않았다.

## HTTP 1단계 — CSV 해석 공간과 실패 식별자

CSV worker의 JSON 해석 전 원본 예약과 작업 공간을 합산하고, 해석된 문자열 중 출력 buffer가 계속 참조하는 문자열의 예약은 유지한다. 실제 참조를 놓고 필수 출력을 마친 뒤에만 원본/해석 예약을 반환한다. 공간 부족 또는 필드 검증 실패는 원래 생산 ID·원본 hash·실패 사유로 기록하고 정상 종료 성공에 포함하지 않는다. 같은 owner의 재시작과 후속 정상 저장도 실패 이력을 지우지 않는다.

- `test_csv_decode_budget_failure_preserves_admitted_identity`: 실제 첫 파일 쓰기를 지연하고 큰 원본과 후속96건을 접수했다. 기존 stop True/기대 False로 RED(`csv-decode-shared-budget-red`,exit1)를 확인했다. 수정 후 seq2만 `decode_byte_limit`, 앞선1건·후속96건 저장, 재시작 뒤 작은 추가1건 저장과 실패 이력 유지·예약0을 확인했다.
- 첫 mypy는 tuple 변수에 None을 대입한 오류로 exit1이었다. 참조를 명시적으로 삭제한 최종 CSV service/runtime64시험·Ruff·mypy11파일 모두 exit0이다. 실패 원문을 보존한다. commit `071a7a10`.
- `test_csv_decode_validation_failure_preserves_identity`: JSON에는 유효하지만 Status 필드 형식이 잘못된 원본의 실패 집계0/기대1로 RED(`csv-decode-invalid-payload-red`,exit1)를 확인했다. 수정 후 같은 ID/hash의 `decode_invalid_payload`, 후속 정상 행만 저장·예약0이 일치했다. 관련110시험·Ruff·mypy11파일 exit0. commit `62da5867`.
- 문자열 내용 크기 계산은 기존 fact 함수와 본문이 같음을 AST로 대조한 뒤 공통 모듈로 옮겼다. 출력 시 새로 만든 문자열·CSV 렌더링 공간과 EMA 계산의 추가 `model_dump_json()` 사본은 아직 전체 예산에 포함하지 못했다. 이를 R02 전체 또는 프로세스 RSS 검증 완료로 표시하지 않는다.

## 2026-10-27 CSV 해석 보완 후 전체 회귀와 완료 감사

제품 commit `62da58672c0bca73c1386ea6439bf9921df5bad1`에서 격리 AppData/설정의 `python -m unittest discover -s backend/tests`가 **1,013개 중1,012통과·기존 private F01자료 미제공1skip**,323.744초,exit0으로 끝났다. 실행 중 제품·시험·문서를 변경하지 않았다.

- `completion-audit-62da-20261027/verification.json`: RED/GREEN·정적 검사·전체 stdout/stderr를 읽고 로그 해시·최종 소스 해시를 결합했다. unittest FAIL/ERROR0. 새 Pydantic 경고는 위 잘못된 Status 시험에 대응하고, manifest traceback과 shutdown 오류 문구는 기존 오류 주입 시험과 대조했다.
- 같은 폴더의 `audit.json`/`review.md`:109경로 모두 추적, 원본4문서·승격4자료 해시 일치, 작업 트리 clean, master 미통합을 확인했다. 감사 당시 최신2커밋은 로컬에만 있었으며 이 감사 기록은 이후 push로 재작성하지 않는다.
- 전체7단계/17명세·최종 설치본과 master 통합은 미완료다. 새 개발 코드는 서버에 적용하지 않았다.

## HTTP 1단계 — EMA 사본과 JSON 인코더 내부 버퍼 확장

CSV의 기존 EMA 계산을 canonical bytes 생성 전에 끝내 같은 예약 공간을 재사용한다. EMA는 접수 때 분리한 snapshot으로 만든 모델을 사용하며 기존 계산식·필드 제외 규칙을 유지한다. JSON 일괄 인코더의 내부 버퍼 확장도 실측에서 예약을 넘었으므로, CSV·fact 접수와 fact 스풀에 공통 조각 인코더를 적용했다. 조각/합친 문자열 및 문자열/UTF-8 bytes가 공존하는 두 단계 중 큰 공간을 먼저 예약한다. 스풀의 줄바꿈도 한 번에 합친다.

- `test_csv_ema_workspace_reuses_serialization_reservation`: 실제 첫 CSV 쓰기를 지연했다. 수정 전 추가 할당53,494,487bytes가 가용44,033,866bytes를 넘는 RED(exit1)를 확인했다. 수정 후 같은 기준·기존 EMA 값·실제30/31/32 행 저장·예약0이 일치했다. 최종 관련111시험·Ruff·mypy11파일 exit0. commit `e7ba8899`.
- 첫 CSV fixture는 별도의 후속 decode 공간까지 넘어서 cleanup도 실패했다. 제품을 바꾸기 전에 입력을11/17MiB로 조정해 위 직렬화 실패만 재현했다. 첫 GREEN 시도는 내부 버퍼 확장 실패와 존재하지 않는 history 시험 모듈을 지정한 오류가 있었다. 수정된 실행은 `test_history_cursor`를 사용했고 가용 공간 기준은 완화하지 않았다. 중간 실패 원문을 보존한다.
- `test_json_encoder_growth_stays_within_owner_budget`: 온도 fact의 실제 파일 쓰기를 지연한 상태에서13,109,025bytes/가용12,307,449bytes의 RED(exit1)를 확인했다. 공통 인코더 적용 후 세 원래 관측 ID의 실제 CSV 저장·예약0·오류0이 일치했다. 관련135시험 중134통과·기존 F01 1skip, Ruff·mypy exit0. commit `e6afe1c9`.
- `test_spool_encoder_growth_stays_within_two_copy_budget`:1MiB 이내 행의 실제 스풀 쓰기가2,255,351bytes/검사상한1,870,198bytes로 RED(exit1)였다. 이 상한은 두 payload 사본과 별도64KiB 객체/경로 여유다. 수정 후 기존 segment 앞부분·전체 추가 bytes 불변, 실제 세 ID와 큰 필드의 복구·잔량0을 확인했다. 관련136시험 중135통과·기존 F01 1skip, Ruff·mypy11파일 exit0. commit `5a8a0b69`.
- `json-workspace/encoding-verification.json`:266자료×3출력 형식,798경우의 변경 전후 bytes/hash 일치. ASCII·escape·한글·넓은 혼합 문자열의12계측도 예약과 별도 객체 여유 안에서 일치했다. 관찰된 payload 이외 추가 할당은 최대2,324bytes다. 이는 해당 인코더 계측이며 전체 객체 상한이나 프로세스 RSS 보장이 아니다.

## 2026-10-27 JSON 작업 공간 보완 후 전체 회귀

제품 commit `5a8a0b69`에서 격리 AppData/설정의 `python -m unittest discover -s backend/tests`가 **1,016개 중1,015통과·기존 private F01자료 미제공1skip**,325.671초,exit0으로 완료됐다. 실행 중 제품·시험·문서를 변경하지 않았다.

- `json-workspace/verification.json`에 세 변경의 최초 실패·수정 결과·정적 검사·전체 stdout/stderr 해시·최종 소스 해시를 연결했다. 전체 로그를 읽어 unittest FAIL/ERROR0과 직전1,013시험 대비 새로운 정규화 오류 문구0을 확인했다.
- 앞 CSV 해석 변경과 기록은 `200bf264`에서 원격 반영을 확인했다. 현재 변경도 원격 HEAD를 대조한 뒤 완료로 보고하며, master 병합이나 운영 서버 적용으로 확대하지 않는다.
- 남은 CSV 출력 렌더링·이미지/fact 구성/검산 예산, 실제 목적지/설정 세대 결합, 영속 대조·부분 쓰기 복구·압력 제어·화면 연동, 전체7단계/17명세 및 최종 설치본 검증을 계속 유지한다.


## HTTP 1단계 — CSV 출력 공간 예약과 출력별 실패 보존

제품 commit `f4fec384`는 실제 CSV 파일 출력 전에 레코드 인코딩·내부 버퍼·파일 출력 공간을 원본/해석 예약과 합산한다. `csv.writer`가 가장 큰 레코드 버퍼를 계속 보유하지 않도록 매행 쓰기 뒤 해제한다. 기존 batch/시간 drain 조건은 유지하며, 그 내부에서 행별 flush를 완료한 뒤 임시 예약을 반환한다. 파일 쓰기 호출 수의 변화가 운영 처리량에 미치는 영향은 최종 성능 검증 범위로 남긴다.

- `test_csv_output_budget_failure_keeps_identity_and_later_rows`: 5MiB 금형번호 입력이 v1/v2 출력 예약을 넘는 경우 원래 생산 ID·순번·hash와 각 출력 실패를 남긴다. 생산 입력 기준 실패 집계는 중복 없이1건이며, 뒤의 정상 행31만 두 실제 CSV에 저장되고 최종 pending0·stop False를 확인했다.
- 최초 RED는 ERROR 로그 부재로 실패했다. 기존 코드도 다른 종료 검사로 stop False였으므로 이 반환값만으로는 해당 실패를 증명하지 못했다. 제품 변경 전에 실패 집계를 명시한 `csv-output-workspace-red-r2`에서 실제0/기대1의 RED(exit1)를 확인했다. 최초 실패 원문도 보존하며 다른 종료 실패의 원인을 이번 결과로 확정하지 않는다.
- 관련 CSV168시험 exit0, fact70시험 중69통과·기존 F01 1skip, Ruff·기본 mypy11파일 exit0이다. 공통 CSV 크기 계산기로 이동한 함수의 본문이 이전과 같음을 AST로 확인했다.
- 원본 예산을 가득 채우는 `test_csv_source_budget_includes_inflight_payloads`에서 헤더 공간 부족 재시도974회가 발생했다. 해당 시험만 따로 실행해 동일 로그와 접수분 전체 저장·종료 성공·예약0을 확인했다. 이 포화 조건의 재시도와 최소 작업 공간 확보는 전체 자원/복구 계약 검토에서 계속 다룬다.

## 2026-10-27 CSV 출력 보완 후 전체 회귀와 잔여 범위

- 첫 전체 검사 `csv-output-workspace-full-backend`는1,017시험 중 기존 종료 시험1건 실패·1skip,334.218초,exit1이었다. 시험이 `writerows` 호출에 고정돼 있었고 제품은 행별 `writerow`를 사용한다. 실패를 삭제하거나 통과로 바꾸지 않았다.
- 관련 기존 종료 시험4개는 mock writer 대신 실제 CSV 직렬화 결과를 검사하도록 보완했다. 순서 오류는 쓰기·flush0, flush 실패는 실제 행이 만들어져도 완료 순번 갱신0, 정상 쓰기는 flush 이후에만 완료 순번 갱신을 확인한다. 네 시험과 최종 backend Ruff 모두 exit0이다.
- 최종 `csv-output-workspace-full-backend-r2`: **1,017시험 중1,016통과·기존 private F01자료 미제공1skip**,319.178초,exit0. 최종 제품·시험을 변경하지 않고 완료했다. 전체 stdout/stderr를 읽고 실패0과 위 포화 시험의974회 로그 귀속을 확인했다.
- 근거는 `BRANCH_SYNC_20261026_4d2950c6/csv-output-workspace/verification.json`에 보존한다. RED·수정 결과·첫 전체 실패·최종 전체 결과·소스 SHA256을 구분한다. 근거 취합 스크립트의 첫 실행은 결과 key 표기 오류로 실패했으며, key만 수정한 뒤 원래 결과들을 다시 읽어 검증했다. 제품 시험 결과를 재작성하지 않았다.
- 완료: 운영 커밋 동기화, 운영 코드/시험 복원, 버전5파일, 기존109경로의 보존·커밋. 원격 작업 브랜치/upstream도 구성돼 있다.
- 미완료: master 통합, HTTP7단계/17명세 전체, CSV 행 생성/스칼라 변환과 오류 경로 잔존값의 예산, 이미지/fact 구성·검산 예산, 실제 목적지·설정 세대 결합, 영속 대조·부분 쓰기 복구·독립 압력 제어·화면 연동, 새 설치본 빌드와 최종 검증.
- 이번 개발 변경은 서버에 적용하지 않았다. 등록 운영본·다음 복귀 기준은 계속 `cd46692a`/installer SHA256 `558658cf02d59cb6b66468e4e191c447efdc7cc24518b5a69647cc2409eb232f`이며, 패키지의1.0.32 표기를 새 개발 코드의 운영 승인으로 사용하지 않는다.


## HTTP 1단계 — 헤더 최소 공간과 CSV 행 사본

- `5aa4f6d5`: 접수 당시 설정의 v1/v2 헤더 중 더 큰 작성 공간을 접수·해석 단계에서 남겨 둔다. 64MiB 정책 상한을 늘리지 않았으며 실제 출력 때는 같은 계산으로 예약한다. `test_csv_header_pressure_does_not_strand_admitted_rows`의 RED는 종료 후 접수497건이 남는 실패(exit1)였다. 수정 후 저장 행과 원래 ID/hash의 실패 기록이 접수 목록을 빠짐·중복 없이 설명하고, pending0·재시작 후 정상 행 저장을 확인했다. 관련 CSV169시험·Ruff·mypy exit0이다. 기존 원본 포화 시험의 헤더 재시도974회는 같은 입력에서0회가 됐고 접수분 전체 저장도 유지했다.
- `0866f53d`: 수식 해석 방지를 위해 문자열 앞에 작은따옴표를 추가할 때 사본 크기를 먼저 예약한다. 생성한 문자열은 행에 연결되거나 폐기될 때까지 소유하고, v1/v2가 공유하는 문자열은 한 번만 계수한다. `test_csv_escaped_row_copy_remains_in_pending_budget`의 RED는 실제 할당6,334,257bytes가 기록된 payload와 별도1MiB 객체 여유를 합친5,249,218bytes를 넘는 실패(exit1)였다. 수정 후 같은 상한·두 실제 CSV의 원래 escaped 값·종료 후 예약0이 일치했다. 관련 CSV170시험·Ruff·mypy exit0이다.
- `b3bd13ce`: 길이가 제한된 온도 원문의 CRLF/CR 정규화는 원문 전체 대신 필요한 앞부분만 사용한다. 한 정규화 문자가 최대2개 입력 문자를 소비하므로 양수/0 길이N에서는 앞2×(N+1)자면 잘림 여부까지 판정할 수 있다. 기존 음수 slice 동작은 보존한다. `test_bounded_temperature_text_avoids_full_raw_copies`의 RED는8,388,728bytes/검사상한131,072bytes였고, 수정 후 상한·결과256자·잘림 표시 및42개 짧은 경계 대조가 통과했다. 수집 원본·CSV 형식·수집 주기는 변경하지 않았다.

## 2026-10-27 CSV 최소 작업 공간 보완 후 전체 회귀

최종 제품 `b3bd13ce`에서 `python -m unittest discover -s backend/tests -v`는 **1,020개 중1,019통과·기존 private F01자료 미제공1skip**,304.700초,exit0이다. backend Ruff와 기본 mypy11파일도 exit0이다. 실행 중 소스·시험·문서를 변경하지 않았다.

- 근거: `BRANCH_SYNC_20261026_4d2950c6/csv-row-workspaces/verification.json`. 세 RED·수정 결과·관련 회귀·정적 검사·전체 stdout/stderr·최종 소스 SHA256을 연결했다. 이전 실패 원문은 보존한다.
- 전체 검사에서 헤더 공간 부족 로그는0회다. 직전 검사와 달라 보인 종료 로그는 무작위 attempt/session ID를 정규화한 뒤 한 문구가 남았다. 이는 `test_control_and_partial_lifespan_cleanup_overlap_without_mixing_receipts`의 기존 부분 시작 실패·동시 종료 시험이며, 이전 `json-workspace-full-backend`와 `fact-recovery-and-health-full-backend`에도 있었다. 해당 시험의 실제 두 종료 영수증0/2·스레드 종료·호출 결과 assertion이 통과했고 app/해당 시험 소스는 이번에 변경하지 않았다. 이를 새로운 운영 실패나 종료 판정 완화로 처리하지 않는다.
- 이번 경계들은 전체 CSV 행 생성의 합산 예산 완료가 아니다. 결합 문자열·기타 스칼라/파생 필드·오류 경로 잔존값과 fact/image 구성·검산, 실제 목적지 식별, 영속 결과 대조·부분 쓰기 복구·압력 제어·화면 연동을 계속 구현해야 한다. 전체7단계/17명세·최종 설치본 빌드와 master 통합은 미완료다. 새 개발 코드의 서버 적용도 하지 않았다.

## 2026-10-27 CSV 결합 문자열과 이미지 snapshot 작업 공간

- `1310ec77`: 여러 작업 메타데이터를 쉼표로 결합할 때 새 문자열 공간을 먼저 예약하고 행 소비까지 소유한다. 기존 escaped 문자열도 같은 예약 경로를 사용한다. 실제 파일 쓰기를 지연한 RED는 할당 12,626,030bytes가 집계 예산과 객체 여유 1MiB의 합계 9,443,553bytes를 넘는 실패였다. 수정 후 실제 CSV의 원래 결합 값·정상 종료·예약 0이 일치했다. CSV 모듈 47시험과 Ruff·mypy가 exit0이다.
- `78bea0c6`: 이미지에 연결할 온도 snapshot은 JSON 사본을 만들기 전에 크기를 검사하고 인코딩 공간을 예약한다. JSON 순회·인코딩 중에는 이미지 상태 잠금을 잡지 않는다. 128MiB 원문을 거절하는 RED에서 순간 할당 336,274,481bytes가 관찰됐고, 수정 후 같은 거절은 2MiB 이하에서 끝났다. 이후 정상 JPEG와 관측 연결 기록도 저장됐다. 기존 compact/sorted JSON 형식과 제품의 128MiB 한도는 유지한다.
- `1a549755`: worker가 JSON bytes를 해석할 때 입력 문자열과 해석된 문자열의 공간을 예약한다. 해석된 문자열은 JPEG 쓰기·실패 처리까지 소유하고 실제 참조를 놓은 뒤 예약을 반환한다. RED에서 할당 4,935,245bytes가 집계와 객체 여유의 합계 3,146,496bytes를 넘었고 수정 후 기준을 충족했다. 부족한 공간으로 처리에 실패한 경우 원래 capture ID·JPEG hash·`snapshot_decode_byte_limit`를 남기며, 다음 정상 저장 후에도 failure_count와 비정상 clean 종료 판정이 유지되는 경계를 별도로 통과했다.
- 기존 축소 예산 시험은 사본을 제외한 5MiB에서 두 건을 받는 가정 때문에 첫 회귀에서 실패했다. 접수 인코딩 공간을 포함할 때 6MiB, worker의 해석 자료까지 포함할 때 7MiB로 시험용 한도를 조정했다. 여전히 두 건 접수·세 번째 거절·실제 파일과 원래 관측 ID·종료 후 예약 0을 검증한다. 제품 상수를 늘린 변경은 아니다.
- `22928c20`: 최소 저장 간격의 기준을 실제 큐 접수 성공 직후의 단조 시각으로 고정한다. 실제 큐 삽입 중 시각이 2초 전진하는 시험에서 성공 0.5초 뒤 요청을 잘못 접수하는 RED를 재현했다. 수정 후 0.5초 요청은 정책 제외, 1초 뒤 요청은 실제 저장된다. 이미지 종료 모듈 44시험·Ruff·기본 mypy11파일 exit0이다.

## 2026-10-27 이미지 작업 공간 보완 후 최종 회귀

`22928c20`에서 `python -m unittest discover -s backend/tests -v`는 **1,025시험 중1,024통과·기존 private F01자료 미제공1skip**,331.997초,exit0이다. 앞선 `1a549755`의 전체1,024시험/324.846초/exit0도 별도 보존했다. 최종 전체 실행 중 제품·시험 소스는 변경하지 않았다.

- `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-csv-workspaces/verification.json`에 22개 실행의 명령·종료 코드·전체 stdout/stderr 해시·실패/통과 요약을 묶었다. 예상 RED 4개와 기존 축소 예산 시험의 첫 회귀 실패도 원문 그대로 보존한다.
- 전체 시험 전 원문 SHA256 4개를 기록하고 시험 후 일치 여부를 확인했다. Windows 작업 파일의 CRLF와 Git의 LF 차이를 명시해 각 시험 당시 커밋 바이트를 대조했으며 최종 AST도 일치했다.
- 완료 범위는 CSV 결합 문자열, 이미지 snapshot 직렬화·해석 공간, 저장 간격의 접수 성공 시각이다. CSV의 나머지 행/스칼라/오류 경로, fact/image writer 구성·파일 재읽기 공간과 인덱스 계측, 실제 목적지·세대별 계약, 영속 결과 대조·부분 쓰기 복구·압력 제어·화면 연동은 남아 있다. 전체 7단계·17명세, 최종 설치본 빌드와 master 통합은 미완료다.
- 서버 설치·설정·수집 주기·운영본은 변경하지 않았다. 승인 운영본과 다음 변경의 복귀 기준은 계속 `cd46692a`/installer SHA256 `558658cf02d59cb6b66468e4e191c447efdc7cc24518b5a69647cc2409eb232f`이다.

## 2026-10-27 추적 segment와 CSV 생산·설정 구간 연결

- `1756ef12`·`9b58069f`·`707fb3d6`·`1bcb3b9b`: 추적 segment의 동일 바이트 게시 재시도, 1MiB/1,000건 단위·최대2개 대기, 직렬화 사전 크기 검사·4KiB 읽기 검산, 첫 기록부터1초의 단조 시각 flush 예정 시각을 구현했다. Python 객체/인덱스까지 포함한 프로세스 RSS 상한을 입증한 것은 아니다.
- 완료 감사에서 재현한 짧은 쓰기는 `e3c3a326`에서 보완했다. 실제 파일의 헤더·7개 기록 뒤 다음 기록이 일부만 써지면 즉시 멈추고 pending 원본을 보존한다. 최종 이름으로 바꾸기 전에도 내용을 검산하며 불확실성·오류 사유를 남긴다. 동일 실패 재시도에서 원본 불변·최종 게시 없음·20개 대기 유지가 확인됐다. 이 시험은 추적 메타데이터 대상이며, 계획3단계의 실제 CSV20행/7행 실패 검증을 대신하지 않는다.
- `2db6c5dd`: `CSVLoggerService`의 실제 owner 실행에 생산 시작/종료 추적을 연결했다. 파일 경로는 최초 활성 로그 폴더의 `.sfl_trace/<logger_service_instance_id>`다. 게시 실패가 나면 CSV 자체의 두 행은 유지하지만 정상 종료 완료로 표시하지 않는다. 미해결 추적을 다음 실행으로 조용히 덮어쓰지도 않는다. 관련 CSV/추적53시험 통과.
- `1e548123`: 접수와 같은 lifecycle 잠금에서 종료 요청 시 생산 마지막 번호를 고정한다. 파일 종료 대기 중 들어온 `REJECTED_CLOSED` 요청은 이전 실행 범위를 늘리지 않는다. 실제 두 번의 실행에서 시작/종료 범위와 저장30/32 두 행을 확인했고, 종료 후 거절된31은 저장되지 않았다.
- `253df9e6`: 접수된 설정 세대가 worker에 적용되는 첫 생산 번호, required sinks, 접수 당시 로그 폴더, v2 schema/column hash를 추적한다. v1의 기존 두 행은 이전 폴더, 새 v2 한 행은 새 폴더에 남는 것을 실제 CSV와 대조했다. CSV/추적54시험 통과.
- 현재 공개하는 추적 범위는 `PRODUCER_AND_CONFIG_BOUNDARIES`다. 개별 접수·거절 범위, 출력별 데이터/증거 상태, 실제 파일/행 대응, 종료 전체 대조는 아직 구현 중이다. `producer_stop` 기록이나 pending0만으로 저장 무결성 전체 PASS를 주장하지 않는다.
- `5c6bc173`: 추적 모듈을 기본 mypy 검사 대상으로 추가했다. 기본12파일 및 관련 명시2파일 검사·backend Ruff가 exit0이다.

## 2026-10-27 CSV 추적 연결 후 전체 회귀

첫 전체 실행은1,032시험 중1실패·1skip,336.703초,exit1이었다. 기존 부분 시작 실패 시험의 `patch.object(evidence.os, 'fsync', ...)`가 전역 os 모듈을 변경해, 종료 영수증뿐 아니라 새 CSV 추적의 fsync까지 실패시켰다. 같은 실패를 단독으로 재현한 뒤 `2ae6143c`에서 종료 영수증 모듈의 OS 참조만 감싸 오류를 주입하도록 수정했다. 원래 시작 오류·실패한 영수증 판정·실제 worker 종료 검사를 유지하고, CSV 추적 파일의 실제 존재·실패0·pending0 대조를 추가했다. 이미지/종료44시험이 통과했다. 제품의 추적 실패 판정을 완화하지 않았다.

최종 `2ae6143c`의 `python -m unittest discover -s backend/tests -v`는 **1,032시험 중1,031통과·기존 private F01자료 미제공1skip**,334.516초,exit0이다. 최종 실행 중 제품·시험 소스를 변경하지 않았고6파일의 시험 전후 SHA256 및 해당 커밋의 줄바꿈 정규화 바이트가 일치했다.

- 증거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/csv-trace-integration/verification.json`. 19개 실행의 명령·종료 코드·전체 stdout/stderr 해시를 연결한다. 기능 RED4건, 첫 전체 실패와 그 단독 재현도 보존한다.
- 저장 경로는 기존 접수 설정에서 얻고, 새 파일명은 writer UUID/segment 번호로 만든다. 추적 JSON에 인증정보를 추가하지 않았으며 상태 조회는 파일 I/O를 수행하지 않는다. 기존 CSV 형식과 실패한 증거 원본은 유지한다.
- 다음 작업은 출력별 접수/거절 및 저장 결과 연결, 부분 데이터 쓰기의 확인·중복 방지, 나머지 승인된 자원/복구/압력/화면 계약이다. 전체7단계·17명세, master 통합, 최종 설치본 빌드·운영 적용은 여전히 미완료다. 운영 서버와 승인된1.0.32 바이트는 변경하지 않았다.

## 2026-10-27 실제 CSV 부분 배치 재시도와 닫기 실패

- `e802dcbc`: 기존 실제 CSV worker 시험에서 헤더와7행을 파일에 기록한 뒤8번째 행 쓰기를 실패시켰다. 수정 전 전체 배치를 다시 append해20행 대신27행이 남는 실패를 재현했다. 접수한 행에 파일 식별자·바이트 위치·길이·SHA256을 연결하고, 재시도에는 최대4KiB씩 실제 내용을 읽어 동일 행이 있으면 append하지 않는다. 없는8번째 행부터 쓰는 경우 v1/v2 모두20행이 각각 한 번 남고, 최초7행의 전체 내용과 v2 `sample_seq`1–20이 유지됐다.
- 이 대응은 현재 프로세스의 pending 행에 한정된다. 경로 객체는 writer와 공유하고32바이트 digest는 기존 payload 예산에 예약한다. 비교용 인코딩·4KiB 재읽기 공간도 출력 예약에 포함한다. 디스크 바이트 digest는 계획의 canonical `output_payload_hash`나 영속 저널이 아니며, 재시작 후 v1 행 ID 복구를 보장하지 않는다. 나머지 스칼라·예외 프레임·인덱스 등 전체 메모리 경계 검증은 계속 남아 있다.
- `97624f34`: 재시도 직전 이미 쓰였던7행을 실제 파일에서 제거한 시험은, 수정 전 이를 조용히20행으로 재작성했다. 이제 write/flush 완료 이력을 함께 확인하고, 이전에 존재했던 행이 사라졌으면 원본 바이트를 바꾸지 않고 미확정으로 남긴다. 손상 tail과 기존 행 내용 변경의 추가 회귀 검사에서도 파일 불변·pending20·정상 종료 거부를 확인했다.
- 쓰기 오류 횟수와 안정적인 사유를 메모리 상태에 게시한다. 재시도 후 자료를 복구했더라도 기존 오류 이력은 남기고 해당 실행을 무오류 정상 종료로 표시하지 않는다. 기존 설정 전환 시험의 성공 종료 기대 한 곳을 이 계약에 맞게 강화했으며, 이전/새 폴더의 두 행과 다음 세대 입력 보존 검사는 유지했다. 첫 관련 회귀 실패도 보존했다.
- `4226c3e2`: 실제 CSV v1/v2 핸들의 close 오류가 정상 종료로 표시되는 실패를 재현했다. 실제 핸들이 닫힌 뒤 예외가 발생한 경우와 열려 있는 경우를 모두 확인했다. 이제 close 오류는 종료 실패·미확정 파일로 기록하고, 남은 핸들의 소유권을 유지한다. 미확정 파일/핸들이 있으면 새 서비스 시작을 거부한다. v2 최종 observation manifest 처리 전에 파일 닫기 결과를 반영한다.
- `c3646c96`: 위 실제 경계의 회귀 검사 보강. CSV/추적/runtime/이미지 종료126시험이 통과했다. 데이터·증거 분리 확정, v1성공/v2실패 전체 대조, 같은 ID의 다른 출력 내용, 다양한 flush·파일 교체, 같은 실행의 새 파일/설정 전환에서 미해결 owner 우회를 막는 추가 차단·검증, JPEG/fact 복구는 아직 완료로 선언하지 않는다.

## 2026-10-27 CSV 복구 변경 후 전체 백엔드 회귀

최종 제품·시험 커밋 `c3646c969641f1cf4d01855119bece6b0de67303`에서
`python -m unittest discover -s backend/tests -v`를 실행했다. **1,036시험 중1,035통과·기존 private F01자료 미제공1skip**,314.556초,exit0이다. 실행 중 제품·시험·문서를 변경하지 않았고 작업 트리가 깨끗했다. 기본 mypy12파일·backend Ruff도 exit0이다.

- 증거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/csv-partial-recovery/verification.json`.18개 실행의 명령·종료 코드·전체 stdout/stderr 해시와 제품/시험2파일의 현재 바이트·시험 커밋을 검산했다.
- 7/20행 중복, 이미 쓰인 행 제거, v1/v2 close 실패의 RED를 보존했다. close 핸들 잔존 조건 보강 재현과 기존 종료 기대의 회귀 실패까지 실패 실행5개를 모두 보존했다. 새 guard 시험은 기존 readback 구현의 회귀 확인이며 별도 RED/GREEN 성과로 세지 않는다.
- 보존된 설계·분석·comparator-readiness·PDCA 원문4문서의 SHA256이 기존 값과 일치한다. 실제 저장 경로와 접수한 행에만 쓰며, 불확실한 자료의 자동 절단·삭제·복제 백업을 추가하지 않았다.
- 전체7단계·17명세, 압력/복구/화면 계약, master 통합, 최종 통합 health·새 설치본은 미완료다. 운영 서버에 설치·설정 변경·앱 조작은 하지 않았다. 승인 운영본과 다음 변경의 복귀 기준은 계속 `cd46692a`/installer SHA256 `558658cf02d59cb6b66468e4e191c447efdc7cc24518b5a69647cc2409eb232f`이다.

## 2026-10-27 CSV 행별 데이터·증거 확정과 출력 내용 결합

- `82005f62`: CSV close 또는 행 확인이 불확실해지면 같은 owner가 날짜/목적지 전환으로 새 파일을 열어 우회하지 못하게 했다. 신규 접수는 `REJECTED_UNAVAILABLE/csv_owner_requires_manual_recovery`이며 이미 접수한 다음 행은 보존한다. v1/v2·날짜/경로·실제 핸들 닫힘/잔존의8경계 RED를 확인했고 관련127시험이 통과했다.
- 작업 폴더 재감사 당시 미커밋 행 증거 구현은 `committed_sequence`/실제 `committed_segment_seq` 불일치와 타입 오류3건이 있었다. 관련127시험에서23본시험·하위 사례 포함31실패였으며 이 원문과 감사 기록은 유지한다. 이름을 바로잡은 뒤에도 종료 경계 전에 증거를 확정하려는 순서 때문에 기존 producer-stop 검사1개가 실패했다. 이 실패도 보존했다.
- `92e4db9b`: 실제 CSV 데이터가 존재해도 행 증거 segment가 확정되기 전에는 원래 이벤트·행·예약을 완료 처리하지 않는다. 파일 ID·행 바이트 범위·원본 hash·설정 세대와 증거 segment 번호를 결합한다. runtime의 `csv_data_written_evidence_pending_count`와 `csv_evidence_pending_by_sink`로 대기를 구분한다. 정상 운전은 기존1초 증거 예정 시각을 따르고, 종료에서는 생산 경계를 기록한 뒤 강제 flush한다. 종료 경계의 미완료 수는 `pending_event_count_at_stop`이며 최종 완료 수로 해석하지 않는다. 관련127시험·mypy12파일·Ruff가 exit0이다.
- `535bfb60`: 증거 파일 교체만 실제 실패시키고 복구한 회귀 검사에서 v1 단독과 v1/v2 동시 출력 모두 CSV 원래 두 행이 한 번씩 유지됐다. 파일 bytes가 전후 동일하고 원래 producer/sink·설정·원본 hash·파일 ID/바이트 범위가 증거와 일치한다. 복구 후 pending/예약은0이지만 과거 trace failure는 남고 무오류 정상 종료로 표시하지 않는다. 이 추가 검사는 이미 구현된 경계의 회귀 보강이며 별도 RED 성과로 세지 않는다.
- `920aa91e`: 새 출력 내용 계약 `CSV_ROW_CONTENT_V1`의 canonical JSON은 `contract_version`, 순서가 있는 `columns`, 최종 문자열 `values`로 구성한다. 정렬된 키·compact 구분자·UTF-8/ensure_ascii=False로 SHA256을 계산한다. 실제 파일 bytes hash와 별도인 `output_payload_hash`를 기록하고 원본 `source_payload_hash`도 유지한다. 한글·따옴표·줄바꿈·비BMP 문자열을 포함한 실제 v1/v2 CSV로 해시 누락 RED와 수정 후 일치를 확인했다. JSON 작업 공간은 생성 전에 예약하고 pending 행의 두 digest64bytes와 hex 변환 공간도 집계한다. 관련129시험과 정적 검사가 통과했다.

## 2026-10-27 행 증거 변경 후 전체 회귀와 범위

첫 전체 backend는1,039시험 중2하위 사례 실패·1skip,354.475초,exit1이었다. `test_logger_loop_daily_rollover_and_stop_propagate_deferred_failure`의 내부 flush 감시기가 처리 후 비워지는 목록에 행이 남아 있어야 완료 신호를 보내는 가정이었다. 단독 재현에서도 같은2실패를 확인했다.

`170fd985`에서 해당 감시를 실제 CSV 행과 확정된 trace의 바이트 범위/hash 대조로 바꿨다. 기존3초 fixture 기한·정상/손상 sidecar 종료 판정은 유지하고 두 날짜 파일·producer1/2·sample_seq1/2를 추가 확인했다. 같은 감시를 쓰던 private F01 경로도 이 파일 대조를 사용하며 새 계측 이름은 `csv_evidence_observed`다. 실제 F01 자료는 제공되지 않아 그 경로의 실행은 여전히 skip이고 통과로 세지 않는다. 온도 fact 모듈26시험 중25통과·1skip,exit0이다.

최종 clean commit `170fd98592ac302f7ec19eacc96f05dfd2064b06`에서
`python -m unittest discover -s backend/tests -v`는 **1,039시험 중1,038통과·private F01자료 미제공1skip**,348.332초,exit0이다. 실행 중 소스·시험·문서를 변경하지 않았다.

- 근거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/csv-row-evidence/verification.json`.27실행의 명령/종료 코드·전체 stdout/stderr hash, 실패 실행9개, 최종3소스 파일과 커밋 바이트, 원문4문서 불변을 검산했다.
- 새 trace는 별도 파일이며 기존 CSV 열을 추가/삭제하지 않는다. 새 기록은 내용 전체 대신 source/output/실제 bytes hash와 원래 경로·파일/행 식별자를 연결한다. 상태 조회는 메모리만 읽고 서버·설치본·운영 설정은 변경하지 않았다.
- 이번 범위는 같은 프로세스의 행/증거 확인이다. 전체 생산/접수/거절 및 출력 상태 보존식, 거절 범위4,096개 제한, 증거 포화 시 접수 차단, 모든 동일ID/목적지/자원 경계, JPEG/fact 복구, 압력 제어·화면·계약 버전의7단계/17시나리오 전체는 미완료다. master 통합·최종 통합 health·새 설치본 검증도 남는다. 현재 운영/복귀 기준은 계속 `cd46692a`다.

## 2026-10-27 증거 공간 포화와 신규 CSV 접수 제어

- `5a0db581`: 미확정 trace segment 두 개가 가득 차면 신규 CSV 접수를 직렬화 전에 `REJECTED_LIMIT/trace_segments_full`로 거절한다. 기존 접수 행은 보존하며 실제 증거 확정으로 공간이 반환되면 다시 접수한다. 최초 RED는 포화 뒤에도 ACCEPTED였던 실제 계약 위반이다. 이후 단독/감사 실행의 종료 기대 실패는 오류 주입기가 실제 파일 교체 실패를 관찰하기 전에 복구를 허용했던 시험 순서 문제였다. 실패 횟수와 `.pending` 파일을 먼저 확인하도록 수정했다. 오류가 발생한 실행은 복구 뒤에도 실패 이력이 남고 stop 성공으로 처리되지 않는다. 실제 CSV 행 집합과 예약 반환도 확인했다. 관련130시험이 통과했다.
- `49fbd191`: segment 개수·행 개수에 여유가 있어도 다음 기록의 직렬화 공간이 부족하면 `admission_blocked_reason=trace_workspace_full`을 게시한다. 필요한 작업 공간만 정수로 보관하고 실제 segment 확정으로 충분한 공간이 생기면 차단을 해제한다. 실패한 flush는 공간을 반환하지 않는다. 384KiB 본문4개를 담은 실제 trace에서 누락 상태 RED를 재현하고, 파일 교체 실패→복구 후 원래5개 기록의 정확한 저장을 확인했다. 과거 last_error/failure_count로 현재 가용성을 영구 차단하지 않는다.
- `fd3a0670`: 본문 또는 헤더가 빈 전체 예산에서도 처리될 수 없는 경우를 일시적인 포화와 구분한다. 각각 `record_workspace_too_large`·`header_workspace_too_large`와 `incomplete=true`를 남기고 파일·직렬화 사본을 만들지 않는다. ASCII와 비BMP 문자를 섞은 넓은 문자열2사례에서 RED를 확인했다. 처리 가능한 다음 본문의 실제 저장은 가능하되 이전 incomplete 이력은 유지한다.

최종 관련 CSV/runtime/trace/이미지 종료132시험은51.122초·exit0, backend Ruff 및 기본 mypy12소스 파일도 exit0이다. clean commit `fd3a06703d91898ece797f41b909feff069efd5e`에서 `python -m unittest discover -s backend/tests -v`를 실행해 **1,042시험 중1,041통과·기존 private F01자료 미제공1skip**,330.989초·exit0을 확인했다. 전체 검사 중 저장소 파일은 편집하지 않았다.

- 증거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/trace-admission/verification.json`.19실행의 실제 명령·종료 코드·전체 stdout/stderr hash, 실패 실행5개, 최종4소스의 commit 바이트, 원문4문서 불변을 검산했다. 직전 branch-review의 FAIL 기록은 당시 상태로 보존한다.
- 상태 조회와 신규 접수 gate는 메모리만 읽는다. 파일 경로·포맷·권한·서버 설치·운영 설정 변경, 신규 백업은 없다. 공간 제한은 소프트웨어 payload 예산이며 전체 프로세스 RSS 보장이 아니다.
- 아직 전체 생산/접수/거절 대조, 거절 ID 범위4,096개 제한 및 초과 INCOMPLETE, 출력별 최종 보존식과 manifest, JPEG/fact·설정/파일/자원 경계 전체, 독립 압력/복구·API/화면 계약의7단계/17시나리오는 미완료다. master 통합·최종 통합 health·새 설치본 검증도 남는다. 이번 작은 경계 시험들을 전체 RV/RR/FR 명세의 PASS로 집계하지 않는다.

## 2026-10-27 실행별 접수 집계와 거절 범위 메모리 원장

- `c88bdbed`: 접수·정책상 제외·최종 거절을 별도 집계하고, 거절 번호의 상세 범위를 최대4,096개만 보유하는 `AdmissionRejectionLedger`를 추가했다. 상세 한도 뒤에도 집계는 계속하며 `details_incomplete`, 생략된 거절 수와 첫/마지막 생략 번호를 표시한다. 이 두 번호가 그 사이 모든 ID의 상세 결과를 복구한다는 뜻은 아니다. 실제4,097개 거절 범위와 접수/제외를 섞은12,291개 결과에서 RED/GREEN을 확인했다.
- `19eede95`: 번호가 바로 이어지고 상태·사유·설정 세대가 모두 같은 경우에만 마지막 범위를 확장한다. 중간에 접수된 번호, 다른 사유·세대·상태를 가로질러 병합하지 않는다. 범위가 이미 한도에 도달했어도 같은 범위의 연속 확장은 가능하다. 반환된 범위는 불변 객체이며 이전 snapshot을 뒤에서 변경하지 않는다.
- `b105abc6`: 실제 `CSVLoggerService.enqueue_detailed()`의 모든 반환 경로를 lifecycle/config 잠금 안에서 공통 집계한다. 원래 접수 판단 본문은 별도 `_admit_csv_locked()`로 옮겼고 AST가 기존 본문과 같음을 확인했다. runtime의 `admission_summary`는 `CSV_ADMISSION_SUMMARY_V1`·`IN_MEMORY_RECEIPTS`로 범위를 명시하며 전체 상세 목록을 상태 API에 복제하지 않는다. 시작 전/종료 후 CLOSED 요청은 실행 집계에 넣지 않고, 재시작은 새 실행 원장으로 분리한다. 실제 저장2행과 비활성2·입력 거절3·접수2 및 다음 실행1건을 확인했다.
- `43236f1e`: 결과가 없는 중간 번호와 종료 경계까지의 끝 번호를 `unaccounted_count`로 분리했다. 생산 경계와 실제 결과 수가 다르면 상세 추적을 불완전으로 표시하고, 이를 접수·제외·거절로 임의 분류하지 않는다. 실제 CSV stop의 생산 경계를 lifecycle 잠금 안에서 원장에 전달한다. 원장은 CSV의 증가하는 생산 번호를 사용하며 새로운 센서 표본이나 장비 수신 번호를 생성하는 기능은 아니다.

통합135시험은49.554초·exit0이었다. 이후 종료 경계 보완의 trace/CSV12시험, backend Ruff, 기본 mypy12파일도 exit0이다. 최종 clean commit `43236f1eea50983fe2112632440a3d23a83abce5`의 전체 backend는 **1,046시험 중1,045통과·private F01자료 미제공1skip**,366.457초·exit0이다. 검사 중 저장소를 변경하지 않았다.

- 증거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/admission-ledger/verification.json`.16실행의 명령·종료 코드·전체 stdout/stderr hash, 실제 RED4개, 최종4소스 commit 바이트, 원문4문서 불변과 접수 본문 AST 동일성을 검산했다.
- 이번 원장은 메모리 집계다. 거절 범위의 writer 전달·영속 저장·증거 확정·재시도·종료 manifest 연결은 **아직 구현되지 않았다**. 이 메모리 결과만으로 저장 완전성 PASS나 전체 RV09 통과를 선언하지 않는다. 원장의 제한은 상세 메타데이터 건수이며 전체 RSS 제한이 아니다.
- 원래 CSV 열·파일 경로·출력 주기·장비 설정·운영 설치본은 변경하지 않았다. 기존 원본4문서와 보호 stash를 보존한다. 전체 출력 상태 대조, JPEG/fact 복구, 독립 압력 제어·API/화면 계약,17개 전체 명세, master 통합과 최종 통합 빌드가 계속 남는다.

## 2026-10-27 거절 범위 영속 기록과 종료 접수 집계

- `5066de5b`·`4b5b9e52`: 인계한 범위를 불변 상태로 보존하고, 같은 trace segment에 여러 범위를 묶어도 실제 segment 확정 번호까지 도달한 범위만 해제한다. 대기·인계·segment 저장 대기를 합쳐4,096개 한도를 유지하며, 같은 확정 번호의 재확인으로 집계를 중복 증가시키지 않는다. 한도 초과의 생략 이력도 유지한다.
- `e30a2df0`: 실제 CSV worker에 `CSV_ADMISSION_REJECTIONS_V1` 기록을 연결했다. 한 worker 차례의 범위 수를 제한하고 기존1초/1,000항목/1MiB segment·미확정2개 상한을 사용한다. 파일 I/O는 생산자의 lifecycle/config/runtime 잠금 밖에서 수행한다. 실제 파일 교체 실패 후 같은 거절 번호·사유·설정 세대가 한 번씩 저장되는지 확인했고, 회복 뒤에도 기존 trace 실패 이력을 지우지 않았다.
- `49d621ea`: 거절 범위가 확정된 뒤 `CSV_ADMISSION_SUMMARY_V1` 종료 집계를 저장한다. 한도 때문에 상세가 생략된 실행은 전체 거절 수·생략 수·첫/마지막 생략 번호와 `INCOMPLETE`를 남긴다. 집계의 범위는 `PRODUCER_ADMISSION_COUNTS_ONLY`, 데이터 전체 무결성은 `NOT_EVALUATED`다. 이 집계 기록을 출력별 최종 보존식/manifest 또는 신규 완전성 PASS로 대체하지 않는다. 아직 범위가 미확정이면 그 뒤에 정상 종료 집계를 내보내지 않는다.
- `5ef5998f`: 저장 OFF로 시작한 뒤 ON에서 거절만 발생하고 다시 OFF/경로 변경된 경우, 최초 거절 당시 설정·경로를 보존해 worker가 증거를 기록한다. 생산자에서 파일 I/O를 시작하지 않는다. 미확정 거절이 남으면 다음 실행이 원장을 초기화하지 못하게 했고, OFF만 유지한 경우 파일을 만들지 않는 기존 동작도 확인했다.

관련 회귀95시험·96시험과 마지막 시작/종료 경계19시험이 통과했다. 최종 clean commit `5ef5998fb26f11bf75724b82f32cd787d5637941`에서 전체 backend는 **1,051시험 중1,050통과·private F01자료 미제공1skip**,360.059초·exit0이다. backend Ruff·기본 mypy12소스 파일도 exit0이다. 전체 검사 중 저장소 파일을 편집하지 않았다.

- 증거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/admission-durable/verification.json`.23실행의 전체 stdout/stderr·명령·종료 코드·SHA256, 실제 RED5건, 최종4소스 commit 바이트, 원문4문서 및 기존 접수 판단 본문 AST 불변을 검산했다. 앞선 완료 감사의 FAIL/미커밋 기록은 당시 상태로 보존한다.
- 보안/보존 검토: 새 기록에는 생산 번호·정형 사유·세대·집계만 추가하며 비밀번호·원본 payload를 복제하지 않는다. 승인된 운영 설치본 SHA256은 `558658cf02d59cb6b66468e4e191c447efdc7cc24518b5a69647cc2409eb232f`로 유지됐다. 서버 접속·설정 변경·설치·새 백업은 하지 않았다.
- 전체 생산/접수/정책상 제외·출력별 최종 결과 대조와 validator, 나머지 CSV/JPEG/fact 복구·자원 경계, 독립 압력 제어·API/화면 연결 및17개 전체 시나리오는 계속 미완료다. master 통합과 최종 전체 health·새 설치본 빌드/검산도 남는다. 이번 진행을 전체 목표 완료로 표시하지 않는다.

## 2026-10-27 필수 CSV 출력별 결과 집계와 완료 상태 재점검

- `688b79b7`: 접수 시 고정된 CSV v1/v2 각각의 접수·증거까지 확정·실패·미완료 수를 분리했다. 한 출력만 저장된 자료를 전체 완료로 세지 않는다. 모든 필수 출력이 정리되고 보유 payload가 해제된 뒤 논리 자료 한 건의 완료/실패를 한 번 집계한다. 실제 v2 파일 쓰기 실패 동안 v1만 확정되는 상황과 회복 후 두 출력의 저장 행을 확인했다. 이전 쓰기 실패 이력은 유지한다.
- `5679d001`: 파일 소유권·거절 증거 검사와 별개로, 이전 실행의 접수된 CSV 출력이 미해결이면 `start()`가 원장을 초기화하지 못하게 했다. 실제 파일 쓰기 실패로 출력이 남고 trace 대기는 없는 경우의 잘못된 재시작을 RED로 재현한 뒤 차단했다.
- `f004733a`: 정상 종료 경계의 `admission_summary`에 출력별 결과 집계를 `TERMINAL_REQUIRED_SINK_COUNTS` 범위로 저장한다. 접수 수와 확정/실패/미완료 수의 합이 맞는지 확인하지만, 전체 ID별 검증은 아니므로 데이터 무결성 판정은 계속 `NOT_EVALUATED`다.

최종 clean commit `f004733a032d5dbbc82e73dcd8a641edf0ba2a4d`에서 `python -m unittest discover -s backend/tests -v`는 **1,053시험 중1,052통과·private F01자료 미제공1skip**,361.482초·exit0이다. 최종 backend Ruff와 기본 mypy12파일도 exit0이다. 검사 중 저장소 파일을 편집하지 않았다.

- 증거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/csv-sink-outcomes/verification.json`.14실행의 전체 로그·명령·종료 코드·SHA256, 실제 RED3건, 최종4소스 commit 바이트와 원문4문서 불변을 검산했다. 기존 접수 판단 AST는 출력 접수 counter 한 줄 외에 바뀌지 않았다.
- 보안/보존 검토: 추가 집계는 고정 출력 이름과 정수이며 비밀번호·원본 payload를 복제하지 않는다. 기존 경로·권한·CSV 열·수집 주기·운영 설치본은 변경하지 않았다. 이번 작업에서 서버 접속·설치·백업을 하지 않았다.
- 구현된 것은 출력별 **집계**다. 개별 ID의 최종 상태, 목적지/설정 세대별 대조, 독립 판정기, CSV/JPEG/fact의 나머지 복구 경계, 독립 압력 제어·API·화면 연결 및17개 전체 시나리오는 미완료다. 현재 단계의 시험 통과를 이 항목들의 PASS로 확대하지 않는다.
- 완료 여부 재점검: 최초7항목 중1–4는 완료,5는 원격 작업 브랜치/upstream까지만 완료,6은 일부 구현,7은 현재 backend 회귀까지만 확인됐다. master 통합과 전체 구현 후 최종 health·새 설치본 빌드/검산이 남는다. 운영 중인1.0.32의 승인과 현재 후속 개발 브랜치의 완료는 별개다.

## 2026-10-27 개별 접수 계약과 처리 실패 증거

- `93f7ec2a`: CSV 출력 생성·decode 단계의 최종 실패를 `CSV_PROCESSING_FAILURE_V1`로 남긴다. 생산 ID·원본 hash·설정 세대·필수 출력·실패한 출력·사유·접수 경로를 기록한다. 각 미완료 이벤트의 필수 출력당 하나의 메타데이터만 보유하고, 추적 segment가 확정되기 전에는 같은 증거와 payload 소유권을 유지한다. 파일 교체가 회복되면 중복 없이 확정하고, 계속 실패하면 종료 집계를 발행하지 않으며 재시작도 차단한다. 기존 실패 이력은 남긴다.
- `b3491061`: 실제 row 생성 전에 `CSV_ADMISSION_EVENT_V1` 접수 기록을 연결했다. ID·원본 hash·설정 세대·필수 출력·원래/대체 경로·v1 열·v2 schema/열 hash는 불변 envelope의 계약을 사용한다. segment 예산이 없으면 같은 이벤트를 보류하고 writer 차례에서 재시도한다. 생산자에서 파일 I/O를 수행하지 않는다.
- `e990dcdd`: 파일 종료가 불확실해 새 목적지를 채택하지 못한 경우에도 종료 단계에서 남은 접수 계약을 기록한다. deferred 항목뿐 아니라 아직 queue에 있는 접수 자료도 포함한다. 실제 CSV를 새로 만들거나 기존 소유권 차단을 우회하지 않고, 종료 집계에는 미완료 수와 `NOT_EVALUATED`를 유지한다. commit 진전이 없거나 추적 파일을 확정할 수 없으면 종료 재시도를 끝내고 증거를 보유한다. 임시 envelope 참조는 예약량 반환 전에 해제한다.

설정 세대/목적지 전환, CSV v1/v2의 종료 불확실성, 실제 추적 파일 교체 실패·회복을 기존 fixture로 검증했다. 관련76시험은 각 변경 단계에서 통과했고, 최종 clean commit `e990dcdd36f3f4c8916fca11a24a5218efcd262b`의 전체 backend는 **1,054시험 중1,053통과·private F01자료 미제공1skip**,365.751초·exit0이다. backend Ruff·기본 mypy12파일도 exit0이다. 전체 검사 중 저장소는 변경하지 않았다.

- 증거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/csv-id-evidence/verification.json`.22실행의 전체 로그·명령·종료 코드·SHA256, 실제 행동 RED3건과 시험 코드 `mock` 표기 오류1건을 구분해 보존했다. 표기 오류는 제품 실패 재현으로 세지 않는다. 최종4소스의 commit 바이트·원문4문서 불변·접수 판단 AST 불변을 검산했다.
- 보안/보존 검토: 새로운 증거에는 ID·hash·계약·정형 사유만 저장하며 원본 데이터나 비밀번호를 복제하지 않는다. 파일 I/O는 runtime 잠금 밖의 기존 단일 writer에서 수행한다. 미확정 segment2개/2MiB와 접수 이벤트5,000개 상한을 유지하며, 이는 전체 RSS 보장이 아니다. 기존 CSV 형식·수집 주기·운영 설치본·서버 설정은 바꾸지 않았다.
- 아직 정책상 제외 ID의 상세 대응, 출력별 전체 상태 분류와 목적지/세대별 대조, 독립 validator, 나머지 CSV/JPEG/fact 복구, 압력 제어·API·화면 및17개 전체 시나리오는 미완료다. 기존 CSV 판정기에 새 추적 증거를 연결하는 작업도 남는다. master 통합·최종 health·새 설치본 빌드/검증이 끝나지 않았으므로 목표는 계속 진행 중이다.


## 2026-10-27 정책상 제외 ID와 독립 판정기 초기 구현

- `bb6c2aa9`: 저장 비활성화로 제외한 ID 범위를 접수 거절과 구분해 영속 기록한다. 두 종류의 미확정 범위는 기존4,096개 한도를 공유한다. 한도 초과는 종류별 생략 수·구간과 INCOMPLETE로 유지하며, 파일 교체 실패→복구 뒤에도 과거 실패 이력을 지우지 않는다. 기존 접수 판단 본문의 AST는 변경 전과 같다.
- `21ed8c19`: 독립 읽기 전용 검증기를 추가했다. segment당1MiB/1,000기록 한도, 잘림·중복 JSON 키·지원하지 않는 schema·종료 요약 누락/중복을 검사한다.8MiB 파일은 전체를 읽지 않고 거부한다.
- `f278874d`: 생산/접수/제외/거절/미설명 합계와 생산 번호 경계의 산술 일치, 상태별 합계·잘못된 숫자/상태·보고된 상세 손실을 검사한다. 실제 CSV bytes와 모든 ID/출력 결과의 일치를 입증하지 않으므로 전체 무결성은 NOT_EVALUATED다. QA 호출부 연결도 아직 남는다.

각각 실제 계약 위반 RED3건을 확인했다. 관련20실행의 전체 로그·종료 코드·최종 소스5파일·원문4문서를 검산한 증거는 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/csv-exclusions-validator/verification.json`이다. clean `f278874d`의 전체 backend는 **1,059개 중1,058통과·private F01자료 미제공1skip**,363.611초·exit0이다. backend Ruff, 기본 mypy12파일, 별도 검증기 mypy1파일도 exit0이다.

이 구현은7단계·17시나리오 전체 완료가 아니다. 전체 ID·실제 출력 bytes·생산자/segment 연결, 목적지/설정 세대별 검산, 이미지/fact 복구·압력 제어·API/화면·최종 통합health/새 설치본·master 통합은 남아 있다. 서버·설치본·운영 설정·백업은 변경하지 않았다.


## 2026-10-27 독립 검증기의 생산 ID·필수 출력 증거 대조

- `966468cd`: 실제 실행의 생산 시작/종료 경계 누락·중복·잘못된 숫자와 종료 요약의 번호 범위 불일치를 검사한다.
- `8a4d7a6f`: 다른 생산자 또는 writer의 segment를 한 실행으로 섞으면 불완전으로 판정한다. 파일 인자 순서는 실행 식별의 근거로 사용하지 않는다.
- `34d0aa56`: 접수·정책상 제외·거절 범위를 생산 시작/종료와 상태별 종료 합계에 대조한다. 중간 누락·겹침·범위 밖 ID·접수 생산자 불일치를 탐지한다. 원본은 읽기 전용이며 임시 SQLite 인덱스를 사용해 모든 ID를 RAM에 펼치지 않는다.100만 ID의 제외 범위와 원본 불변을 검증했다. 임시 공간 실패는 INCOMPLETE이고 종료 시 연결/임시 파일을 정리한다.
- `99f8dc14`: segment ID의 양의 정수·유일성·1부터의 연속성을 대조한다. 가운데 파일이 빠져도 접수 합계가 우연히 맞는 경우를 탐지한다. Boolean/문자열/중복/매우 큰 번호와 파일 인자 역순도 검사했다.
- `43c09270`: 접수한 각 CSV v1/v2 출력의 결과 기록을 확인한다. 빠진 결과·접수되지 않은 출력·원본 hash/설정 세대 불일치·중복 결과·명시된 처리 실패를 분리한다. v1/v2 실제 정상 저장 증거에서 v2 기록만 제거한 RED를 포함한다.

이번 변경은 validator와 시험에 한정된다. 실제 자료 생산·저장 코드인 repository.py/persistence_trace.py의 바이트는 직전 검증과 같다. 실제 CSV의 경로·행 bytes·canonical 출력 hash를 아직 읽어 대조하지 않으며, 종료 요약의 필수 출력/논리 이벤트 합계 전체 대조도 남아 있다. 따라서 `data_integrity_status=NOT_EVALUATED`를 유지하고 전체 무결성 PASS를 반환하지 않는다. 새 검증기의 QA/CLI 통합·설정/목적지별 전체 계약도 미완료다.

- 행동 RED5건과 관련28실행의 명령·전체 stdout/stderr·해시·최종5소스·원문4문서 검산: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/csv-validator-identities/verification.json`.
- clean `43c0927052d0c1e36b6284169f96f6b4462dd722`에서 CSV service/runtime·trace·이미지 종료 **155시험 통과**,71.314초·exit0. backend Ruff·기본 mypy12파일·별도 검증기 mypy1파일도 exit0.
- 전체 backend/health·설치본 검증은 이번 변경에서 반복하지 않았다. 이번 코드는 시험에서만 호출되는 독립 검증기이며 범위에 맞는 관련 회귀를 실행했다. 이전 전체 backend 결과는 `f278874d`, 전체health는 `f8ad11d8`의 증거로 구분한다.
- 전용 security-review 도구는 없으므로 원본 읽기 모드, SQL 매개변수화, 임시 공간 정리, 원시 payload/자격증명 비수집, 네트워크/서버 비접속을 직접 검토했다. 임시 인덱스의 cache1MiB 설정과 Python 할당 검사는 전체 RSS 상한 보장이 아니다.

7단계·17개 시나리오 전체, 실제 데이터/전체 최종 상태 대조, 독립 압력·복구·API/화면 연동, 최종 통합 검증·새 설치본·master 병합은 계속 남는다. 현장 적용/운영 승격·백업은 수행하지 않았다.


## 2026-10-27 종료 합계·실제 CSV 행 검산과 큰 필드 종료 오류 수정

- `1e5a3620`: 필수 출력별 접수/확정/실패/미완료와 논리 이벤트 종료 합계를 개별 ID 증거에서 재계산한다. 내부 산술만 맞고 실제 결과와 다른 요약을 거부한다.
- `827c4cc8`: 호출자가 지정한 허용 루트 안에서 경로·파일 ID·행 위치·실제 bytes SHA256을 읽기 전용으로 대조한다. 읽기 요청은 최대4KiB, 한 행은 기존 CSV 계약64MiB 이내다. 잘림·파일 교체/변경·범위 밖 경로를 거부한다.
- 같은 커밋은 접수에 성공한1MiB 초과 CSV 필드가 종료 manifest의 Python CSV 기본131,072자 제한에 걸려 `stop=False`가 되는 오류를 수정한다. 해당 두 종료 검산 경로에서만 필드 한도를 맞추고 성공·예외 뒤 원래 한도로 복원한다. 오프라인 마지막 행 재확인도 실제 파일로 검증했다. 첫 편집의 잘못된 위치와 보완 시험의 파일명 가정 오류는 원인을 확인해 수정했으며 원래 실패 로그를 보존한다.
- `2b534a09`: 실제 파일의 열 순서와 값으로 `CSV_ROW_CONTENT_V1` canonical hash를 독립 재계산한다. 원본/바이트 hash와 출력 내용 hash를 구분하고, 헤더 변경·지원하지 않는 계약·잘못된 hash·깨진 UTF-8/인용·여러 행 결합·열 수 불일치를 탐지한다. 한글/따옴표/개행/이모지와 큰 행을 검사했다.
- `bc5b1b4b`: 동일 물리 파일의 행 위치가 겹치면 내용 hash가 맞아도 불완전이다. 두 접수 ID를 동일한 한 행으로 설명하는 경우, 일부 겹침·인접 정상 행·64bit를 넘는 메타데이터 offset·입력 순서 변경을 검사한다. 임시 SQLite 인덱스를 사용하며 모든 위치를 RAM 목록으로 만들지 않는다.

실제 행 bytes/내용 검산은 `data_roots`가 명시된 경우만 수행한다. 기본 메타데이터 검사는 해당 항목을 NOT_EVALUATED로 남긴다. 검사한 행의 VERIFIED와 전체 파일/무결성 PASS는 다르다. 전체 파일 범위·설정/목적지 결합·모든 최종 상태·QA/CLI 연결이 남아 있으므로 `data_integrity_status=NOT_EVALUATED`를 유지한다. CSV parser 한도는 process-wide이며 같은 helper를 사용하는 읽기만 직렬화한다. 다른 모든 CSV 소비자의 동시성이나 전체 RSS 상한을 입증한 것으로 확대하지 않는다.

검증 근거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/csv-validator-data/verification.json`.

- 행동 실패 재현5건, 진단/편집/fixture 실패 시도와 정상 회귀를 포함한32실행의 명령·전체 출력·종료 코드·소스6파일·원문4문서 해시를 보존했다.
- clean `bc5b1b4bfbd93d7c5ae67b3b8747ea811923ef14`: CSV service/runtime·trace·이미지 종료·앱 종료 **200시험 통과**,116.422초·exit0. backend Ruff·기본 mypy12파일·별도 검증기 mypy1파일 exit0.
- 원문4문서와 보호 stash는 유지했다. 전용 security-review 도구가 없어 허용 경로/파일 ID·읽기 모드·bounded window·parser 복원·SQL 매개변수화·임시 공간 정리를 직접 검토했다.
- 전체 backend/health·새 설치본·서버 적용은 이번에 실행하지 않았다. 기존 전체 결과는 당시 commit의 증거로 유지한다. 7단계·17개 전체 명세와 master 통합은 계속 미완료다.


## 2026-10-27 접수 목적지·CSV 형식·설정 적용 구간 대조

- `29bcefd1`: 각 실제 행을 유일한 원래 접수 계약과 연결해 `admitted_log_dir`와 대조한다. 현재 설정이나 fallback 경로로 대체하지 않는다. 접수 계약 누락/중복·상대 경로·다른 목적지를 거부하고 실제2세대·2경로의 정상 저장을 검증했다. 행과 접수 기록을 임시 디스크에 먼저 인덱싱하므로 segment 인자 순서에 의존하지 않는다.
- `b6358486`: CSV v1의 실제 열 목록, v2의 실제 열 hash와 각 행의 schema_version을 접수 계약에 대조한다. 원래 행 내용 hash가 일치해도 접수하지 않은 열/스키마이면 불완전이다. 잘못된 형식/미지원 schema와 지원 형식2.3.1·2.4.2·2.5.2의 실제 저장 파일을 검사했다.
- `691f6db7`: config_activated의 적용 시작 번호를 따라 접수 ID의 설정 세대·필수 출력·경로·v2 계약을 비교한다. 누락/중복 세대·모호한 시작 경계·비단조 세대·아직 적용하지 않은 설정·접수 없는 뒤쪽 설정을 불완전으로 남긴다. 설정과 접수 목록 전체를 RAM에 보관하지 않고 디스크 정렬 커서로 대조한다.
- `d83486a1`: 접수와 설정 기록이 함께 빠졌을 때 configuration_status가 VERIFIED로 표시되던 경계를 실제 실패로 재현해 수정했다. 전체 오류뿐 아니라 개별 판정도 INCOMPLETE로 유지한다.

`validate_csv_persistence_trace(paths, data_roots=[allowed_root])`에서 실제 자료와의 계약 대조를 수행한다. 원본 읽기 전용·허용 루트/파일 ID·4KiB 읽기 경계는 유지한다. data_roots 없는 메타데이터 검사에서는 destination_status/configuration_status/output_content_status를 NOT_EVALUATED로 남긴다. 개별 VERIFIED는 전체 무결성 PASS가 아니며 data_integrity_status는 계속 NOT_EVALUATED다.

- 검산 기록: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/csv-validator-contracts/verification.json`. 행동 RED4건과 관련20실행의 명령·전체 로그·종료 코드·소스6파일·원문4문서 해시를 보존했다.
- clean `d83486a1b681ca4a7562dd36b7c345ac84180b13`의 CSV service/runtime·trace·이미지/앱 종료 **203시험 통과**,131.682초·exit0. backend Ruff·독립 검증기 mypy1파일 exit0.
- 변경은 `persistence_validation.py`와 `test_csv_logger_service.py` 두 파일이다. 실제 수집/저장 런타임 소스는 직전200시험 상태와 같고 기존 기본 mypy12파일 소스도 바뀌지 않았다. 전체 backend/health·새 설치본·현장 검증을 이번 부분 검사로 대체하지 않는다.
- 전용 security-review 도구는 없었다. 허용 루트에서만 실제 파일을 열고 접수 목적지 비교는 경로를 접속하지 않는 어휘 비교로 수행함을 확인했다. SQL 매개변수화·최대2개 계약 조회·segment 한도·임시 디스크 정리·원본 불변을 검토했다.

파일 소유/시작/끝 범위·메타데이터/종료 최종 상태·QA/CLI 연결, 남은 복구/압력/API/화면 계약, 전체7단계/17시험 명세·최종 통합 빌드·master 통합은 계속 남는다. 기존 운영본/롤백 기준·서버·설정·백업은 변경하지 않았다.


## 2026-10-27 CSV 파일 소유 범위와 정상 종료 경계

- `8ca0a933`: 파일별 `CSV_FILE_EXTENT_V1` 시작/종료 기록과 고유 소유 ID를 추가하고 각 행의 증거에 연결했다. 시작 위치는 헤더 또는 기존 자료 뒤의 실제 append 위치이며 종료 위치는 정상 close 전후 파일 ID·크기·시각을 대조해 확정한다. 닫기 실패에는 성공 종료 기록을 만들지 않는다. 활성 소유 기록은 현재 v1/v2 핸들 최대2개이며 과거 파일 목록을 메모리에 계속 쌓지 않는다. 최종 추적 요약은 파일·기존 마감 처리가 끝난 뒤 작성한다.
- `95c06348`: 독립 검증기가 시작/종료 쌍과 행을 임시 디스크 인덱스로 대조한다. 첫·가운데·마지막 행의 대응 누락, 잘못된 종료/설정, 시작·종료 누락/중복, 허용되지 않은 경로와 종료 뒤 추가 bytes를 불완전으로 판정한다. 기존 bytes/hash 검사는 별도로 유지한다.
- `e8101d4f`: 설정 A→B→A 전환으로 같은 파일을 다시 여는 실제 실행을 검증했다. 물리 파일별 소유 구간을 이어 공백/겹침을 검사하고 마지막 소유자의 종료 위치만 최종 EOF와 비교한다. 순서가 뒤집힌 segment 목록도 동일하게 판정한다.

`file_extent_status`는 명시한 data_roots 안의 현재 생산자 소유 구간만 평가한다. 기존 실행에서 작성된 prefix는 이번 실행의 새 자료로 세지 않으며, legacy/범위 증거 누락은 전체 PASS로 채우지 않는다. 메타데이터·최종 종료 상태·QA 소비자 연결이 남아 있어 `data_integrity_status`는 계속 NOT_EVALUATED다.

- 근거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/csv-file-ownership/verification.json`. 행동 RED3건·전체17실행의 명령/종료 코드/전체 로그 해시와 소스6·원문4문서 해시를 보존했다.
- clean `e8101d4f` 통합 회귀 **206시험 통과**,145.541초·exit0. backend Ruff, 기본 mypy12파일, 독립 검증기 mypy1파일 모두 exit0. 기존 종료 오류·부분 쓰기·큰 CSV 필드·이미지 종료 검사 포함.
- 별도 security-review 도구는 없어 활성 소유 상한, SQL 매개변수화, 임시 디스크 사용, 허용 경로·파일 ID 확인과 원본 읽기 전용 동작을 직접 검토했다. 새 운영 연결·설치·백업은 없다.
- 전체 backend/health·새 설치본 검증은 이번 부분 검사로 대체하지 않는다. 메타데이터/최종 상태, 남은 fact/JPEG 복구·압력/API/화면 계약, 7단계/17명세 전체 및 master 통합은 계속 미완료다.

## 2026-10-27 실제 CSV 종료·메타데이터 대조와 QA CLI

- `1a2762e7`: 추적 종료 요약에 실제 데이터 마감 성공, 과거 쓰기 실패, pending/미해결 파일 소유/닫히지 않은 핸들 수를 연결했다. 메타데이터 교체 실패로 런타임 종료가 실패하면 독립 판정도 불완전이다. legacy 종료 상태는 미평가다.
- `0c4f87b3`, `a1d15f04`: 허용 루트 안의 실제 sidecar를 최대1MiB로 읽고 읽기 중 변경·누락·잘못된 JSON/중복 키를 검사한다. 접수 스키마/열 hash, 최종 CSV 행의 생산자·sample_seq, 파일명·finalized 상태도 대조한다.
- `581969b7`: 런타임이 sidecar 교체 후 실제 파일 전체 bytes/SHA256을 `CSV_METADATA_COMMIT_V1`로 기록한다. 독립 검증기는 물리 CSV별 마지막 확정 기록과 실제 sidecar를 대조한다. 파일 재개방과 segment 인자 역순을 허용하지만 누락·잘못된 확정 기록·종료 후 변조를 허용하지 않는다. 읽기 성공과 hash 일치 여부는 별도 상태다.
- `7d15a7e4`: `csv_integrity_status`는 현재 생산자가 소유한 CSV 범위만 판정한다. 대조가 정상이어도 `rejected_count > 0`이면 `csv_admissions_rejected`/INCOMPLETE다. 실제 CSV 읽기나 종료 증거가 없으면 NOT_EVALUATED이며, 모든 CSV 조건을 충족해야 VERIFIED다. 전체 온도 fact/JPEG 무결성을 의미하는 `data_integrity_status`는 계속 NOT_EVALUATED다.
- `253cce7d`: 기존 CSV QA 도구에 명시적인 persistence 모드를 추가했다. 실제 CLI로 없는 trace, 정상 CSV, 변조 파일, legacy 종료 상태, 잘못된 옵션 조합을 검사했다. 이 모드는 CSV VERIFIED만 exit0이고 미평가/불완전은 exit1, 잘못된 명령 구성은 exit2다. 기존 단일/다중 CSV와 fact 옵션은 별도 모드이며 섞으면 거부한다.

종료된 한 생산자의 모든 trace segment와 원래 CSV/sidecar가 존재하는 허용 루트를 지정한다. 예시는 시험 경로이며 서버 실행 지시가 아니다.

```powershell
.\backend\.venv\Scripts\python.exe scripts\validate_csv_v2_shadow.py `
  --persistence-data-root 'C:\QA\closed-run' `
  --persistence-trace 'C:\QA\closed-run\trace\001.trace.jsonl' 'C:\QA\closed-run\trace\002.trace.jsonl'
```

여러 실제 데이터 루트가 있으면 `--persistence-data-root`를 반복한다. 다른 생산자를 섞거나 원래 절대경로가 없는 이관 사본을 임의로 성공 처리하지 않는다. 출력 JSON의 범위는 `CSV_CURRENT_PRODUCER_OWNED_RANGES`이며, 기존 파일의 과거 prefix·센서 물리 샘플·fact/JPEG·운영 성능 또는 출시 전체 승격으로 확대하지 않는다. 보존된 설치본/현장 원시 증거는 재작성하지 않았다.

추가 SHA256 시험의 첫 실행은 시험 자료 구조를 잘못 지정한 KeyError였다. 이를 제품 수정 전에 고쳐 `csv-sidecar-bytes-red-r2`에서 실제 누락 검출 실패를 재현했다. 첫 GREEN에서 읽기 성공과 hash 불일치를 같은 상태로 표시해 기존 회귀1건이 실패했고, 두 상태를 구분한 R2에서 통과했다. 이 두 중간 실패는 정상 RED나 성공으로 재분류하지 않는다.

- 최종 코드 `253cce7d`: 전체 backend **1,082시험 중1,081통과·기존 private F01 fixture 미제공1skip**,436.547초·exit0. backend와 CSV QA 스크립트 Ruff, 기본 mypy12파일, 독립 검증기 mypy1파일도 exit0이다. 최종 코드 검사 중에는 제품 소스를 수정하지 않았고 결과 문서만 정리했다.
- 명령·전체 stdout/stderr·종료 코드·로그 hash29실행과 최종 소스7파일/원문4문서 검산: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/csv-metadata-closeout/verification.json`.
- 별도 security-review 도구는 사용할 수 없어 제한된 메타데이터 읽기, 허용 루트·실제 파일 식별, 읽기 전용 검증, CLI 모드 분리, legacy 미평가와 실패 보존을 직접 검토했다. 새 서버 연결·설치·백업·설정 변경은 없다.
- 직전 목표 턴은 현재 작업본209회귀와 브랜치 감사로 다음 동작을 확정한 PROGRESS다. 이번에는 CSV 마감/증거 검증과 실제 QA CLI를 구현·시험·커밋했다. 전체 목표를 줄이지 않으며, 남은 fact/JPEG 복구·압력/API/화면·관측 재사용 계약,7단계/17명세 전체, 출시 통합 QA·최종 health·새 설치본 검증·master 통합은 계속 진행 대상이다.


## 2026-10-27 이미지 파일 재사용·불확실 쓰기 보존과 완료 상태 재점검

- `4d671d6c`: 동일 capture ID에 다른 고정 내용이 들어오면 파일 쓰기 전에 거부한다.
- `50e0d6e7`: JPEG 저장 후 fact 열기가 실패한 경우, 재호출 시 기존 JPEG의 파일 ID·크기·수정 시각과 실제 bytes를 대조하고 원본을 재작성하지 않는다. 최대4KiB 읽기 창을 사용한다.
- `bccd9d91`: 읽기 창의 메모리를 이미지 owner의 기존 payload 예산에 먼저 예약하고 사용 후 반환한다. 경계 바로 아래에서는 파일 읽기 전에 거절하고 정확한 예산에서는 검산한다.
- `68cf19da`: fact 부분 쓰기·짧은 쓰기·닫기 오류를 해당 writer의 불확실 상태로 유지한다. 이후 같은/새 capture의 추가 쓰기와 정상 최종 확정을 막고 원래 파일을 보존한다.
- `8db88999`, `dbc79f20`: 1MiB 전후·1.5MB의 유효 JPEG, 같은 크기의 변조/잘린 파일, fact 유무, 부분/짧은 쓰기·닫기 실패 회귀를 추가했다. 이 후속 경계 검사는 새 행동 RED로 세지 않는다.

아직 worker는 실패 event를 계속 보유해 자동 복구하지 않는다. 불확실 상태는 같은 writer의 메모리 상태이며 writer 재생성·설정 전환·재시작의 전체 경계를 입증하지 않았다. 따라서 이 변경을 RR-T03 전체 통과, 자동 복구 완료 또는 전체 이미지 무결성 PASS로 기록하지 않는다.

검증 근거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-file-recovery-r2/verification.json`.

- 행동 실패 재현과 중간 오류를 포함한13실행의 전체 로그·종료 코드·SHA256, 현재 소스4개와 원문4문서 해시를 대조했다. 첫 JPEG 재사용 검사는 Windows의 path/handle ctime 차이 때문에 실패했고, 실제 파일 ID·크기·mtime 및 내용으로 검산하도록 수정했다. 예산 시험의 첫 실패는 live 상태 필드 오기였고, 이를 수정한 뒤 실제 예산 초과 실패를 재현했다. 실패 기록은 그대로 보존한다.
- 최신 코드 `dbc79f2003161e04ec6d68f0ba5df2146a607b58`: 전체 backend **1,087시험 중1,086통과·private F01자료 미제공1skip**,432.346초·exit0. backend Ruff·기본 mypy12파일 exit0.
- 전체 `npm.cmd run health`는 앞선 `4d671d6c`에서 exit0이다. 의존성15·Electron103·화면 Node9/Vitest442·backend1,083(1skip)·타입/린트·QA 자체 검사를 포함한다. 근거는 `C:/Users/user/Desktop/SmartFactory/BRANCH_RECHECK_20261027_63a52959/health-result.json`이다. 최신 이미지 변경 후에는 영향을 받는 backend 전체와 정적 검사를 실행했으며 전체 health/새 설치본 검증은 별도로 남는다.
- 증거 수집기 첫 시도의 Git blob/작업 파일 원시 SHA 비교는 LF/CRLF 차이로 실패했다. R2에는 두 SHA를 모두 남기고 줄 끝 변환만으로 동일한지 확인했다. 소스나 고정 원문 증거를 이 검사에 맞춰 변경하지 않았다.
- 전용 security-review 도구는 없었다. 파일 식별·내용 대조, 제한된 raw 읽기, 할당 전 예산 예약, 계수 lock 밖 I/O, 원본 보존을 직접 검토했다. 서버·설치본·설정·백업은 변경하지 않았다.

`.pdca-status.json`에 누락된 HTTP 개선을 DO/부분 구현으로 등록했다. 기존 feature 기록은 보존했다. 과거 네 feature의 check/act 표시는 후속 근거와의 연결 정리가 남아 있으며, 기능 전체 미구현이나 현장 시험 전체 재실행을 뜻하지 않는다: `nsis-startup-render-performance`, `spot-camera-rest-api-conformance`, `spot-request-churn-remediation`, `spot-tcp-source-port-quarantine-v2`.

원래 일곱 목표의 범위는 유지한다. 1~4는 완료,5는 작업 브랜치/upstream 완료·master 미완료,6은 부분 구현,7은 부분 검증이다. 남은 사항은 fact/JPEG 전체 복구와 독립 대조, 저장 압력/목적지 probe/재시도, API·화면·관측 참조 계약,7단계/17시나리오 전체,최종 통합 health·새 설치본 검증·master 통합이다. 운영 등록 build `cd46692a`와 승인된 예외·제외 범위는 그대로다.


## 2026-10-27 이미지 owner의 동일 작업 복구와 경로별 불확실 상태

- `732dd9c5`: 단일 image worker가 일시 OSError에 실패한 원래 capture event·접수 경로·snapshot·payload 예약을 유지한다. 새 취득/UI 요청 없이1→2→4→8→16→30초 상한으로 재시도하며, 성공한 뒤에만 작업을 완료하고 예약을 해제한다. 새 설정의 작은 capture 한도를 이미 접수한1.5MB JPEG에 소급하지 않고 기존 JPEG를 재작성하지 않는다.
- 재시도 오류는 `retry_error_count`, 최종 실패는 기존 `failure_count`, 복구 대기는 `pending_recovery`, 성공한 복구는 `recovered_count`로 분리한다. enqueue=written+final_failure+unfinished 관계를 유지하며 복구 성공이 오류 이력이나 기존 clean 종료 조건을 지우지 않는다. 종료 시작 이후 새 재시도를 예약하지 않고, 대기 작업은 미완료·예약 유지 상태로 남긴다.
- `eee891e3`: 부분/짧은 fact 쓰기·닫기 실패의 수동 복구 상태를 같은 프로세스의 writer 재생성·설정 변경으로 우회하지 못하게 했다. 정규화한 경로의 SHA25632bytes key를 최대4,096개 보관하며 한도를 넘으면 기존 표식을 지우지 않고 이미지 fact 쓰기를 차단한다. 다른 정상 경로는 상한 초과 전까지 별도로 사용할 수 있다. 영속 저널이나 프로세스 재시작 후 복구 보장은 추가하지 않았다.
- `4610d46b`, `73686a4b`: 일시적인 fact 헤더 읽기 실패와 기존 capture ID 조회 실패를 그대로 전달한다. 읽지 못한 원본을 schema-mismatch 파일로 이관하거나, 없는 기록으로 캐시해 중복 append하지 않는다.
- `cf7f06c0`: 제어한 단조 시계와 실제 파일 I/O 실패로 backoff 상한/성공 후 초기화/종료 중 중지, 실제 부분 append 후 설정 변경에도 원본 보존을 추가 검증했다. 이 두 검사는 이미 구현한 동작의 회귀 검사이며 새로운 행동 RED로 세지 않는다.

행동 RED4건을 확인했다. 첫 복구 GREEN의 실패는 fixture가 실제 취득 ID를 전달하지 않고 영수증에 ID가 있으리라 가정한 오류였다. 이를 명시적인 취득 ID로 수정했다. 기존 역사 실패 fixture4건은 일시 OSError를 즉시 최종 실패로 가정해 실패했으므로 최종 실패 주입으로 명확히 분리했고, 이후 실제 종료 시작 전송 drain에서 새 재시도가 예약되는 회귀1건을 확인해 수정했다. 원래 실패 로그와 판정은 보존했다.

- `5157bedec39bd85e34d18a6b5581aab9f1444a39` 전체 backend **1,094시험 중1,093통과·private F01자료 미제공1skip**,439.105초·exit0. backend Ruff·기본 mypy12파일·diff 검사도 exit0이다.
- 관련90시험·75시험, 실제 장애 재현과 경계 회귀를 포함한20실행의 명령/전체 출력/종료 코드/해시·최종 소스5파일·고정 원문4문서 검산: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-owned-recovery/verification.json`.
- 최초 전체 backend는1,094시험 중 CSV fixture1건 실패·1skip이었다. 초기 producer_start trace의 publish 실패가 처리 실패 증거 준비보다 먼저 발생할 수 있는데 시험이 두 사건을 같은 신호로 처리했다. 단독 통과만으로 무시하지 않고 초기 trace를 먼저 실패시키는 순서에서 두 recovery 모드 모두0≠2를 재현했다. `5157bede`는 실제 처리 실패 증거2건을 기다리도록 시험 동기화만 수정했다. 관련 CSV 저장 코드는 `a204a0b9`와 Git blob hash가 같으며 기존 증거/합계/원본 보존 assertion은 유지했다. 수정 후 단독 및 위 전체R2를 검사했다.
- 전용 security-review 도구가 없어 단일 owner, 예약 승계, 재시도 payload 중복 없음, bounded key, 원본 자동 절단/삭제 없음과 인증/네트워크 비변경을 직접 검토했다. 서버·설치본·운영 설정·백업은 변경하지 않았다.

잔여 범위는 명시적으로 유지한다. malformed 역사 fact/마지막 행 처리, 역사 ID 조회와 출력 작업 공간 상한, 고정 fact·메타데이터 실패의 전체 복구 및 독립 대조, 실제 목적지별 probe/가용성과 초기 owner 활성화, 압력 제어·API·화면·관측 참조 계약,7단계/17시나리오 전체·최종 health/새 설치본/master 통합은 미완료다. 이번 부분 검증을 RR-T03 전체 또는 정식 출시 PASS로 바꾸지 않는다. 이전 목표 턴은 감사·검증·문서 정합화·원격 반영을 완료한 PROGRESS였고 전체 일곱 목표를 줄이지 않는다.


## 2026-10-27 손상된 이미지 history 보존과 한 행 조회

- `70efd9dc`, `94bd299c`: 재시작한 writer도 불완전한 행과 마지막 줄바꿈이 없는 tail을 수동 복구 상태로 남긴다. 기존 CSV/JPEG에 추가 쓰기·자동 절단·삭제를 하지 않으며 manifest를 정상 완료로 내보내지 않는다.
- `49bb87a3`: 알 수 없는 헤더를 schema-mismatch 파일로 이관한 뒤 새 기록을 시작하는 경로를 제거했다. 원래 경로를 보존한다.
- `f0b4012f`: 역사 lookup은 순차적으로 읽되 요청한 ID의 한 행만 보유하며 최근 캐시도 한 행이다. 캐시에서 빠진 현재 capture도 기록 시각 상한에 따라 다시 확인하여 JPEG가 사라진 경우 fact를 중복 append하지 않는다. 일반적인 새 capture는 기존 빠른 경로를 유지한다.
- `aec3f1e6`: 잘못된 UTF-8·따옴표·추가 열·빈 행·중복 요청 ID·초기화 후 조회 중 UTF-8 오류6경계를 원본 보존과 함께 확인했다. 정상 multiline/quoted CSV도 저장·재조회한다. 이6경계는 후속 회귀 검사이며 새 RED6건으로 세지 않는다.

행동 RED4건은 예상대로 추가 쓰기를 허용하거나 전체 사전을 메모리에 보유하여 실패했다. 12,001행 조회의 RED peak는20,127,909bytes였고 GREEN은4MiB 미만이다. 이 값은 해당 조회의 Python 할당이며 전체 RSS·모든 행 크기·전체 owner 작업 공간 예약의 통과를 뜻하지 않는다. 조회 결과와 원본 해시·행 수, 캐시에서 빠진 현재 자료의 중복 없음도 확인했다.

- 관련103시험·수집 경로 포함285시험이 통과했다. 최종 `aec3f1e6c4c2968a8fbb7ee7b109fc6408c87226` 전체 backend **1,099시험 중1,098통과·private F01자료 미제공1skip**, 441.980초·exit0. backend Ruff·기본 mypy12파일·diff 검사 exit0.
- 명령/전체 출력/종료 코드·SHA25612실행, 소스2파일과 고정 원문4문서 대조: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-history-recovery/verification.json`. 보호 stash와 기존 원시 결과를 보존했다.
- 전용 security-review 도구가 없어 원본 보존·자동 이관 제거·한 행 캐시·불확실 상태·일시 I/O 전파·네트워크/인증 비변경을 직접 검토했다. 서버·설치본·운영 설정·백업은 변경하지 않았다.

남은 범위는 전체 fact/JPEG/메타데이터 대조, 역사 자료의 의미/조회하지 않은 ID의 중복, 실행 중 외부 파일 변경의 신원 대조, 행 크기 제한과 read/parse/output 전체 작업 공간 예약, 목적지 probe/압력 제어/초기 owner·재시도 경계, API·화면·관측 참조 계약,7단계/17시나리오 전체·최종 health/새 설치본/master 통합이다. 프로세스 내 latch와 초기화 시 손상 탐지를 새 영속 복구 저널 또는 과거 전체 무결성 PASS로 확대하지 않는다.

이전 목표 턴은109경로 보존·소스/고정 문서·20실행40로그 hash·원격 브랜치 대조를 완료한 PROGRESS다. 전체 일곱 목표와 승인된 운영본은 유지하며 목표 완료로 표시하지 않는다.


## 2026-10-27 이미지 기록의 경로·열린 핸들·닫기 후 식별 대조

- `ed72b6ea`: 이미지 기록의 device/file ID·크기·수정 시각을 보유하고, cached/new capture 처리 전과 append 준비 전에 대조한다. 같은 크기와 수정 시각을 유지한 파일 교체도 거부하며, 교체를 새 기준으로 삼지 않는다. 초기화 전후 식별도 대조한다.
- `6bc84fc9`: 경로 검사 직후 교체되는 경우를 실제 Path.open 경계에서 재현했다. 열린 append handle의 fstat와 기존/현재 경로를 쓰기 전에 비교한다. 기존 실제 부분 쓰기 fixture3개에는 진짜 fileno 전달만 추가했고 쓰기/닫기 장애 주입·원본 보존 assertion은 유지했다.
- `49824edf`: 닫기 직후 교체된 파일의 ID 또는 크기가 다르면 수동 복구로 유지한다. 교체된 파일을 정상 기준으로 갱신하지 않으며 이후 writer 재생성으로 우회하지 않는다.
- `4828260c`: 내용 수정·잘림·삭제·디렉터리 대체4경계와 초기화 중 파일 교체를 추가 검증했다. 이 검사는 이미 구현한 동작의 회귀이며 새 행동 RED로 세지 않는다.

행동 RED3건을 확인했다. 첫 관련 회귀의 오류1건은 이전 시험이 외부 append 뒤 새 행을 더 쓴 다음 manifest에서 실패하기를 기대했기 때문이다. 승인된 사전 차단 계약으로 강화해 외부 변경 후 파일2행 그대로·writer 기록1행·추가 JPEG 없음·manifest 미확정을 확인했다. 두 번째 회귀 실패는 검사 코드를 이동하며 생성자에 잘못 넣은 편집 오류였다. lookup 장애가 초기화에서 먼저 소비되는 실패를 확인하고 올바른 메서드로 복원했다. 두 실패와 최종 통과 기록을 모두 보존한다.

- 관련102시험·열린 handle 포함103시험 통과. 최종 `4828260c71468cbb642e38c3bbcb57bd163aae4b` 전체 backend **1,104시험 중1,103통과·private F01자료 미제공1skip**, 436.763초·exit0. backend Ruff·기본 mypy12파일·diff 검사 exit0.
- 12실행의 명령·전체 출력·종료 코드·SHA256, 소스3파일·고정 원문4문서 대조: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-file-identity/verification.json`. 기존 실패 기록·보호 stash·운영 설치본은 유지한다.
- 전용 security-review 도구가 없어 일반 파일 확인·경로/핸들 식별·원본 비삭제·보수적인 불확실 상태·인증/네트워크 비변경을 직접 검토했다. 서버·설치본·운영 설정·백업은 변경하지 않았다.

파일 메타데이터 검사는 I/O를 원자적으로 만들지 않는다. 같은 inode의 내용을 바꾸고 메타데이터를 복원하는 모든 상황, 남은 동시 변경 구간·처음 없는 파일의 독점 생성·파일 ID 미제공·메타데이터 복구는 아직 완전 검증되지 않았다. JPEG 생성 후 기록 교체를 발견한 경우 JPEG는 미확정으로 남을 수 있으며 자동 삭제나 전체 무결성 PASS를 추가하지 않는다. 전체 fact/JPEG/역사 의미 대조, 모든 작업 공간 예약·행 제한, 목적지 probe·압력 제어·초기 owner/재시도, API·화면·관측 참조,7단계/17시나리오·최종 health/새 설치본/master 통합은 계속 미완료다.

이전 목표 턴은 손상 history 보존·한 행 조회·1,099시험 검증·원격 반영을 마친 PROGRESS다. 전체 일곱 목표와 현재 운영본의 승인 범위는 그대로 유지한다.

## 2026-10-27 현재 브랜치 완료 여부 재점검

결론: 승인된 일곱 항목 중 1~4는 완료, 5~7은 일부 진행이다. 현재 브랜치 전체 완료나 후속 개선본의 운영 적용으로 표시하지 않는다.

- 반영 완료: 운영 태그의 후속 10커밋과 누락 백엔드·시험 통합, 버전 파일 5개 1.0.32 동기화, 원래 수정 54개·미추적 55개의 총 109경로 커밋 보존, 작업 브랜치와 upstream 연결.
- 일부 반영: 현재 생산자의 CSV 접수·출력·종료 대조, 부분 쓰기와 재시도 처리, fact/spool·이미지 payload 예산, 이미지 원본 재사용·손상 기록 보존·파일 교체 감지. 전체 저장 무결성 계약의 완료를 뜻하지 않는다.
- 미완료: fact/JPEG 전체 대조와 남은 동시 변경·메타데이터 복구, 모든 읽기/파싱/출력 임시 공간의 상한, 저장 압력 제어와 목적지별 복구 확인, API 발송 억제·화면 재확인·새 관측/반복 참조 연결, r4의 17개 명세 전체 검증, 최종 전체 health·새 설치본 빌드/검증, master 통합.
- 별도 완료된 운영 범위: 기존 `cd46692a` 1.0.32의 제약을 명시한 내부 운영 승격. 서버 포함 3대·Low Signal OFF와 승인된 한 실행 예외를 유지한다. 물리 알람 시험은 미실시이며 과거 보류 자료는 학습에 사용하지 않는다. 현재 개발 HEAD는 같은 버전 문자열을 사용하더라도 해당 운영 설치본과 다른 코드다.

재점검에서 원래 109개 변경 경로의 HEAD blob 존재, 버전 5개, 보호 stash, 소스 3개·고정 문서 4개의 SHA256, 12실행의 전체 로그 24개와 종료 코드, 보존 운영 설치본의 크기·SHA256을 확인했다. 이번 점검에서 서버의 실시간 상태는 새로 조회하지 않았다.

근거: [브랜치 재점검 결과](C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-file-identity/branch-audit-20261027-203229.json). 최신 코드의 backend 전체 검사와 정적 검사는 위 결과이며, 문서 정리 이후 제품 코드는 변경하지 않았다.


## 2026-10-27 이미지 fact 복구 행·해시 읽기 예산

- `cd2aee67`: 초기 이력 계수·capture ID 조회·헤더 읽기에 한 논리 CSV 행당 UTF-8 1MiB 상한을 적용했다. 여러 물리 줄의 quoted 행도 합산한다. 초과한 원본을 절단·삭제·재작성하지 않고 수동 복구 상태로 유지한다.
- `70df5575`: 초기 파일/추가 append의 hash 읽기 전에 최대4KiB를 기존 이미지 payload 예산에서 예약하고 readinto로 같은 버퍼를 재사용한다. 저장 후 검산 예산을 확보하지 못하면 원래 행과 ID는 유지하고 manifest만 미확정으로 남긴다.
- `3e89f937`: ASCII·UTF-8·multiline의 정확한1MiB/1바이트 초과6조건과 저장 후 검산 예약 거절 시 재시도 중복 없음·미확정 보존을 회귀 검사했다. 이 후속 검사는 새 행동 RED로 세지 않는다.

두 행동 RED는 각각 oversized row가 ready인 실패와 초기 digest 예약 거절이 발생하지 않은 실패였다. 관련107/108시험 통과, 최종 backend **1,108중1,107통과·private F01자료 미제공1skip**, 438.976초·exit0. Ruff·기본 mypy12파일·diff 검사도 exit0이다. 8실행의 명령·전체 로그16개·종료 코드·SHA256과 소스2개/고정 원문4개 대조는 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-recovery-budget/verification.json`에 보존한다.

한 행의 상한과 digest 버퍼 예약을 전체 이미지 메모리 상한 완료로 확대하지 않는다. 파서·출력·보유 cache 사본의 예약, 전체 fact/JPEG 독립 대조·역사 의미/중복·남은 동시 I/O 복구, 저장 압력·목적지 probe·API/화면/관측 계약,7단계·17시나리오 전체 및 최종 health/새 설치본/master는 남아 있다. 기존 운영본·태그·stash·실패 증거를 유지하고 서버 조작·백업은 하지 않았다.

직전 목표 턴은109경로·기존 증거·운영 설치본 검산, 최신 진행 기록 갱신과 원격 반영을 완료한 PROGRESS다. 전체 목표는 계속 active다.


## 2026-10-27 이미지 fact 쓰기·재시작 행 계약 정합성

읽기 상한만 추가하면 현재 writer가 더 큰 행을 저장한 뒤 재시작 시 읽지 못할 수 있다. `5871a7b6`에서 CSV 출력 바이트 수를 생성 전에 계산해 1MiB 초과는 `image_fact_row_byte_limit`으로 거절하고 새 JPEG·fact 쓰기를 하지 않도록 했다. 정상 기록 후 초과 기록 거절·원본 보존·뒤의 정상 기록 저장을 시험했다. 기존 허용 기록과 쓰기 거절을 서로 구분한다.

1MiB 안의 긴 단일 필드는 Python CSV 기본 필드 한도 때문에 복구가 실패하는 행동 RED도 확인했다. `66635d0f`는 기존 공용 parser lock/원복 context를 재사용해 field limit과 행 한도를 맞췄다. 큰 UTF-8·quoted newline 필드의 재시작 재사용·행 중복 없음·최종 해시 일치·기존 parser 한도 복원을 확인했다.

- 쓰기 경계 관련111시험 exit0; 최종 코드의 종료/image shutdown/temperature fact 관련156시험,55.152초·exit0. Ruff·기본 mypy12파일·diff 검사도 exit0.
- 앞선 전체 backend1,108시험 결과는 `3e89f937`에만 해당한다. 이후 두 변경의 최종 전체 backend/health를 실행했다고 표시하지 않는다.
- 6실행·전체 로그12개·원래 종료 코드와 SHA256, 소스2개 및 고정 원문4개 대조: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-row-contract/verification.json`.
- 읽기/쓰기 크기 계약을 맞췄지만 파서·출력·캐시 사본의 전체 예약, 이미지 데이터/증거 독립 검산과 나머지7단계/17시나리오는 미완료다. 목표 범위·운영본·master·기존 승인 조건은 바꾸지 않았다.


## 2026-10-27 저장 압력 구성요소 반영 후 재점검

**전체 완료 아님.** 목표1~4는 완료, 목표5는 master 병합 미완료, 목표6은 부분 구현, 목표7은 최종 전체 검증·설치본 미완료다. 로컬 코드 기준은 `e6a59284`이며 현재 승인 운영본은 여전히 `cd46692a`의 1.0.32다. 운영본과 이후 개발 소스는 같은 버전 문자열이어도 같은 바이트가 아니다.

반영된 내용:

- 운영 후속10커밋 통합, 누락 backend/시험 복원, 버전5파일1.0.32 동기화, 원래109경로 추적·커밋 및 보호 stash 유지.
- CSV 접수 ID·설정/출력 고정, 합산 예산, 부분 쓰기/증거 분리, 출력별 결과·종료·현재 생산자 소유 파일의 독립 검산과 QA CLI.
- 이미지 동일 event 재시도, JPEG 재사용, 불확실/손상 원본 보존, 파일 식별 검사, 한 행 조회/캐시 및1MiB 행/예약4KiB 해시 읽기 경계.
- 저장 압력의 NORMAL/PRESSURED/PERSISTENCE_BLOCKED 판정,1초 간격·3회 복귀 확인, 단일 독립 스레드, 읽기 실패/종료/이전 세대 대기 자료 경계. 이 구성요소를 운영 코드에서 호출하는 경로는 아직 없다.

미반영·미완료 내용:

- writer별 가용성·예정 시각 게시, 목적지 probe/복구와 제어기 연결. 멈춘 sampler의 오래된 정상 snapshot 처리도 남는다.
- 이미지/진단 요청 발송 직전 억제, 같은 센서 캐시 조건, API 상태·헤더 및 화면 timer/관측 식별 계약.
- 전체 fact/JPEG 독립 대조, 남은 파일 동시 변경·메타데이터 복구 및 파서/출력/캐시 전체 작업 공간 예약.
- r4 7단계·17개 전체 시나리오, 최종 HEAD 전체 health·빌드·새 설치본 검증, master 병합. 작은 경계 시험들을17명세 전체 통과로 집계하지 않는다.

검증 근거:

- 상태 불명, 점유/지연 임계,3회 복귀, 시각 불명, 독립 monitor, sampler 실패의6행동에 RED→GREEN 기록이 있다. stop timeout/이전 세대 검사는 후속 회귀다.
- 제어기 자체8시험, 공용 시각 회귀를 포함한32시험(11.877초) exit0. 현재 source의 backend Ruff, 기본 mypy12파일 및 제어기 mypy1파일도 exit0.
- 14실행의 전체 로그28개·명령·종료 코드·SHA256, 버전5개·109경로·고정 원문4개·운영 설치본·원격 tag/master 대조는 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/pressure-controller/verification.json`에 보존한다.
- 점검 시작 시 로컬 작업 트리는 clean이고 원격 작업 브랜치보다8커밋 앞서 있었다. 원격 동기화의 최종 상태는 같은 폴더의 별도 후속 검산 기록으로 확인한다.
- 기존 전체 backend 결과는 그 시험 commit에 한정한다. 서버 실시간 상태 확인·설정 변경·설치·백업·기존 증거 재작성은 수행하지 않았다. 물리 알람 미시험과 과거 자료 사용 보류 등 승인된 운영 제약은 그대로다.


## 2026-10-27 이미지 owner 사전 초기화와 실제 목적지 probe

- `d1124085`: 이미지 저장이 활성일 때 SPOT 서비스 시작에서 기존 단일 image owner 초기화를 예약한다. 과거 기록 읽기가 지연돼도 온도 poll 시작은 기다리지 않는다. 첫 capture·UI·CSV 열기를 시작 조건으로 삼지 않는다. 초기화 단위 시험은 poll 본문을 고립 대기 task로 바꾸고 실제 image owner를 사용했다. 기존 실제 수집·종료 통합을 포함한 관련194시험도 통과했다.
- `2a94ecd2`: 실제 fact 폴더와 UTC 날짜별 JPEG 폴더에서 각각 고유 임시 파일 두 개를 생성해 소량 쓰기·flush·교체·제한된 재읽기를 확인한다. 파일 식별이 일치하는 자기 임시 파일만 정리한다. 로그 폴더 성공으로 JPEG 폴더 실패를 덮지 않는다. 교체·내용 불일치와 다른 소유자 파일 보존, 손상 fact 원본·미확정 상태 유지도 검증했다. 초기 mypy의 두 형식 오류를 수정했고 관련17시험과 최종 정적 검사가 통과했다.
- `388602e2`: 큐가 비고 종료 중이 아닌 활성 image owner가 초기화 후 probe를 수행하고 결과를 메모리로 게시한다. snapshot 읽기는 파일을 열거나 stat하지 않으며 반환 사본의 변경이 원래 결과를 바꾸지 않는다. 이 결과는 `directory_only`이고 기존 본 파일의 무결성·append 가능성·전체 저장 가용성 PASS가 아니다.

세 행동의 RED는 각각 owner 미기동, JPEG 목적지 unknown, owner probe 미실행의 예상 실패였다. 최종 관련246시험(65.915초) exit0, backend Ruff와 기본 mypy12파일 및 diff 검사 exit0이다. 8실행·전체 로그16개·종료 코드·SHA256과 최종 소스3개의 대조는 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-owner-probes/verification.json`에 보존한다.

off→on·목적지/날짜 변경·probe backoff와 설정 세대별 결합, CSV/fact의 필수 출력 가용성/예정 시각, 압력 제어기의 실제 수집·API·화면 연결은 남는다. 기존 큐 자료 우선 처리와 장애 이력 보존을 유지하며 다음 통합에서 확인한다. FR01/RR02 전체 또는17시나리오 완료로 집계하지 않는다. 최종 전체 health·빌드·설치본·master 병합도 미완료다. 서버 설정·설치·백업·운영본/롤백 기준은 변경하지 않았다.


## 2026-10-27 이미지 저장 재활성화·재시도·대기 자료 우선 처리

- `61e8f505`: 실제 poll이 저장 off→on·목적지 변경을 감지해 기존 단일 owner 초기화를 예약한다. poll은 파일 I/O를 기다리지 않는다.
- `43070178`, `57f5e9f0`: 실패한 실제 폴더 검사는 단조 시계 기준 1→2→4→8→16→30초 상한으로 재시도하며 필요한 목적지의 회복 후 예약을 해제한다. 같은 writer의 실패 이력을 유지한다. UTC 날짜 전진·역행에도 현재 JPEG 폴더를 재검사한다.
- `16489472`: 같은 경로로 저장을 다시 켜도 세대가 바뀌며 이전 성공 결과를 비운다. 새 검사 중 unknown, 새 JPEG 경로 실패와 fact 경로 성공을 구분한다. 이 세대는 폴더 검사 식별이며 전체 capture 접수 세대 계약의 완료를 뜻하지 않는다.
- `ff9fcb85`: 상태 수집이 멈추면 메모리 snapshot에서 오래된 NORMAL을 계속 반환하지 않는다. 제어기 2주기(2초)를 내부 표본 유효성 한도로 두며, 늦게 끝난 수집은 실패 이력으로 남긴 뒤 정상 표본 3회로 복귀한다. 새 스레드를 중복 생성하지 않는다.
- `b608eed7`: 기존에 접수한 이미지 큐와 복구 작업을 먼저 처리하고 새 목적지의 초기화를 수행한다. 실제 JPEG bytes와 fact 한 행이 원래 경로에 저장됐음을 확인했다.

직전 감사는 최신250시험 결과·원격 미전송3커밋·미커밋3파일을 확인해 다음 작업을 확정한 진행이었다. 이번에는 미커밋 변경을 커밋하고 stale 상태와 저장 순서의 두 실제 실패를 재현·수정했다. 우선 처리 시험의 첫 실패는 접수 상태를 ENQUEUED로 잘못 적은 fixture 오류였고, 제품 변경 전에 ACCEPTED로 고쳐 R2에서 실제 순서 오류를 재현했다. 원래 실패 로그를 보존한다.

최종 관련260시험(86.373초), backend Ruff·기본 mypy12파일·pressure 모듈 mypy1파일·diff 검사 exit0. 설정/날짜/재시도/세대 및 후속 두 동작의 13실행·전체26로그·종료 코드·SHA256과 소스5파일/고정 원문4문서 검산은 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-owner-lifecycle/verification.json`에 보존한다. 앞선 전체 backend/health를 최신 전체 결과로 바꾸지 않는다.

남은 범위: 초기화 실패 후 종료 확인·backoff 재기동, writer 교체를 넘는 목적지별 이력, 실제 본 파일/CSV/fact 필수 출력 가용성·예정 시각, 압력 제어기의 실제 수집/API/화면 연결, 전체 fact/JPEG 대조·작업 공간 상한, r4 7단계/17시나리오, 최종 전체 health·새 설치본·master 병합. FR01/RR02 전체 통과나 목표 완료로 집계하지 않는다. 목표1~4 완료,5~7 부분 완료를 유지한다.

별도 보안 검토 도구는 없어 기존 소유 파일 정리 범위, poll/API 파일 I/O 없음, 단일 worker·대기 자료 원래 경로 보존, 상태 수집 지연의 보수적 처리와 원문 해시를 직접 검토했다. 서버·설치본·설정·백업·운영/롤백 기준은 변경하지 않았다. 원격 동기화 결과는 같은 증거 폴더의 별도 기록으로 남긴다.


## 2026-10-27 이미지 발송 압력 gate·캐시와 응답 계약

- `6ec753eb`: 이미지 task가 장치 잠금을 기다린 뒤 transport 호출 직전에 BLOCKED 상태를 재확인한다. shared task와 waiter는 무캐시일 때 `storage_pressure` 503을 받고 센서 실패 계수는 늘리지 않는다.
- `ccdf78db`: 같은 센서의 검증된 캐시 JPEG는 TTL 만료 후에도 원래 취득 시각·age로 200 반환한다. 다른 센서의 캐시로 대체하지 않는다. 정상 응답은 suppression 0, 억제 응답은1·storage_pressure·profile별 양의 정수 Retry-After 초를 전달한다. 원래 JPEG를 다시 취득·저장한 것으로 집계하지 않는다.
- `e1979b12`: 기존 image_upstream_request_count(task 의미)는 유지하고 image_http_dispatch_count와 image_storage_suppressed_task_count를 별도로 게시한다. 하나의 shared task를 두 waiter가 기다려도 미발송 억제는1회다. 복구 후 실제 발송이 재개되는 것을 확인했다.
- `4fbc767c`, `067d6bad`: 실제503 HTTP 응답의 CORS 공개 헤더를 확인했고, 캐시200 헤더는 route 호출로 별도 검사했다. 프런트엔드 타입/parser에서 누락·잘못된 flag는 unknown, 비억제/알 수 없는 사유의 retry는 null이며 양의 안전 정수 초만 받는다. 일반 오류 재시도와 분리된 압력 timer는 아직 연결하지 않았다.
- `d88ad315`: BLOCKED 전 이미 dispatch한 요청은 취소·미발송으로 재분류하지 않고 실제 JPEG와 비억제 메타데이터로 완료하는 후속 회귀다. 새로운 행동 RED로 세지 않는다.
- `dc66f6d0`: 조회 잠금 대기 중 A→B로 센서가 바뀌면 이전 A 캐시를 반환하던 경계를 실제200≠503으로 재현했다. 억제 캐시를 선택하는 순간 현재 URL을 다시 확인하도록 수정했다.

6개 행동 RED→GREEN과 이미 발송된 요청의 후속 회귀를 포함한13실행, 프런트엔드 전체 타입·린트·시험3명령의 전체32로그와 종료 코드·SHA256을 보존했다. 최신 관련 backend265시험(91.049초) exit0, frontend Node9/Vitest443(42파일)·타입·lint exit0, backend Ruff·기본 mypy12파일·diff 검사 exit0이다. 소스6개/고정 원문4문서 검산과 명령은 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/pressure-image-api/verification.json`에 연결한다.

범위 제한: 시험은 실제 pressure monitor·driver·API에 제어된 메모리 저장 상태와 외부 transport fixture를 공급했다. 운영 lifecycle은 아직 monitor를 생성·시작하지 않으며 `_storage_pressure_monitor`는 기본 None이다. 따라서 실제 운영의 저장 장애 억제 전체 완료를 주장하지 않는다. 필수 writer 상태 제공/예정 시각, 초기화 실패 재기동, PRESSURED 감속과 주기 진단/journal, 화면 압력 timer·visibility·callback 소유권, 전체 fact/JPEG/작업 공간, r4 17시나리오와 최종 전체 health·설치본·master가 남는다. 기존 임계값·전체 목표를 줄이지 않았다.

직전 턴은 코드/검증/원격 반영을 마친 PROGRESS다. 이번에도 위 구성요소를 구현·검증했으며 원래 목표1~4 완료·5~7 부분 완료를 유지한다. 서버·설치본·설정·백업은 변경하지 않았다. 별도 보안 검토 도구는 없어 새 응답에 경로/인증정보를 넣지 않는지, 캐시 센서 일치·양수 retry·발송 전 잠금 경계·기존 오류 분류 보존을 직접 검토했다. 원격 동기화 결과는 같은 증거 폴더에 별도로 기록한다.


## 2026-10-27 화면 저장 장애 재확인과 표시 수명 계약

최종 소스 `f8da5043133e50aff229775c4d4bfe672880d724`. 별도 재확인 timer가 명시적 storage-pressure 캐시200/무캐시503을 처리한다. 일반500/1000/2000ms 재시도 예산은 소비하거나 초기화하지 않고 실제 통신·payload·표시 오류는 기존 오류 경로로 처리한다. 현재 이미지의 정상 표시가 확인된 경우에만 일반 성공 복귀를 허용한다.

- `b2aa7ebf`, `d43959be`: 응답 본문 처리와 in-flight 해제 뒤 재확인을 예약한다. 압력 캐시 onLoad를 기다리지 않으며 늦은 알림으로 정상 timer를 추가하지 않는다.
- `581a2b17`, `fc415da7`: 마지막으로 표시된 fallback과 pending을 구분하고 교체된 pending URL을 즉시 해제한다. 이전 onLoad/onError는 현재 상태·오류 수·timer를 바꾸지 않는다.
- `830c078e`, `e2fdcd5f`: 실제 visibility listener와 설정 변경·종료·unmount에 timer/URL 수명을 연결했다. 구 설정의 응답은 본문 완료 후 폐기하고 새 설정 요청을 이어간다. 진행 중 HTTP를 취소하지 않고 shutdown drain을 유지한다.
- `6218d618`, `b03d4ece`, `8ce32f75`, `4d173ef4`, `6fb2d410`: 503에서도 기존 취득 식별을 보존하고, 잘못된 Retry-After는 현재 간격의 양수 fallback을 사용한다. 간격 변경만 deadline을 갱신하고 표시 설정 변경은 유지한다. 큰 양수 지연은 브라우저 정수 범위 안에서 단조 시각으로 나눠 기다린다. 숨김 뒤 실제 오류가 도착해도 새 timer/예산 소비는 없다.
- `e7b5685a`, `f8da5043`: 실제 오류·본문 drain·누락/음수/소수/문자열 fallback 회귀와 3회 재확인 간격에 해당하는 6초 지연 표시 callback을 추가 검사했다. 이 회귀는 새로운 RED로 집계하지 않는다.

11개 행동 RED→GREEN을 확인했다. 주소 정리 시험의 finally assertion이 최초 실패를 가린 기록과 환경 timer 전체 개수 가정이 어긋난 기록은 별도 보존하고 제품 코드 변경 전에 시험 범위를 수정했다. TypeScript 대상 버전에서 Set 순회가 거부된 exit2는 forEach로 수정한 뒤 타입/관련 검사를 다시 통과했다.

최종 관련43시험, 프런트엔드 전체 Node9/Vitest460(42파일), 타입·lint 모두 exit0. 각 실행의 명령·전체 출력·종료 코드·SHA256, 소스3파일과 고정 원문4문서 검산은 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/pressure-ui/verification.json`에 보존한다. 실제 React hook/effect·configuration leader를 사용했고 네트워크 응답/JPEG는 시험 입력이다. 실제 화면 painting·센서/서버 현장 시험의 통과로 확대하지 않는다.

전체 목표1~4 완료·5~7 일부 진행을 유지한다. required writer 상태/가용성·monitor 서비스 연결, 초기화 실패 재기동, PRESSURED 감속·주기 진단/journal, 전체 상태/관측 참조·fact/JPEG/작업 공간과17시나리오, 최종 전체 health·새 설치본·master 병합은 남는다. 운영 monitor는 여전히 기본 None이며 이번에 서버·설치본·설정·백업을 변경하지 않았다. 별도 보안 검토 도구가 없어 새 권한/인증정보 노출 없음·명시적 억제 분기·실제 오류 보존·URL/정수 timer·설정 세대 경계를 직접 검토했다.

직전 재점검은 HEAD/원격·109경로·원문·운영 설치본/승격 근거와32로그를 검산한 PROGRESS다. 이번 턴은 위 화면 코드·회귀의 구현과 검증을 진행했다. 목표를 축소하거나 완료로 표시하지 않는다.


## 2026-10-28 주기 진단의 저장 압력 차단·기록 복원

- `77adc129`: journal v2의 queued→suppressed/storage_pressure를 실제 실패와 분리한다. 미발송에는 시작/소요 시각을 만들지 않고 active를 종결한다. v1 원문은 유지하고 새 reader에서 읽는다.
- `c8bf19ee`: 장치 잠금 대기 중 BLOCKED 전환 시 진단 발송0건. 필드별 결과로 중간 억제의 길이 예외를 제거하고 받은 값·실제 오류·억제 현재 항목·미접수 나머지를 구분한다. field status parser와 관측 fact 직렬화도 연결했다.
- `f7b50e29`: BLOCKED에서 진단 task/journal을 만들지 않고 별도 poll 억제 계수를 남긴다. 회복 후 정상8항목 수신과 기존 단일 작업 제한을 유지한다.
- `e52bcab3`: 이미 발송한 성공/timeout을 사후 억제로 바꾸지 않음, 부분 결과·fact 상태·journal 재시작 복원, v1/v2 혼합 읽기·v1의 잘못된 억제 거부, running/exception 요청의 억제 전환 거부를 회귀 검사했다.
- `9f7e1dbf`: schema_version 배열/객체 입력으로 복원이 TypeError로 끝나는 행동 RED를 확인하고 타입 검사를 추가했다. 정상 오류 기록은 복원하고 잘못된6행만 거부한다.
- `ba093228`: 계획의 `image_dispatch_attempt_count`·`diagnostic_dispatch_attempt_count`·`pre_dispatch_suppressed_count`를 공개 상태에 연결했다. 기존 필드는 유지한다. 마지막 항목은 현재 프로세스에서 장치 발송 gate를 넘지 못한 이미지 작업+개별 진단 요청의 합이며, 작업 생성 전 poll 억제·coalesced waiter·task 없는 캐시/503 응답은 포함하지 않는다. 이미지 두 waiter를 억제1건으로 집계하고 회복 후 실제 발송1건을 별도로 확인했다.

총5행동 RED→GREEN은 journal 상태, 잠금 뒤 발송, 작업 생성 전 차단, 잘못된 schema 값, 계획의 계측 필드다. 보완4메서드는 후속 회귀이며 새 RED가 아니다. 시험 도중 잘못된 journal 변수명·fact 키·일반 fixture의 비UUID 서비스 식별자 때문에 나온 실패는 수정·보존했으며 제품 실패로 집계하지 않는다.

`9f7e1dbf7628faa0d17ee9065e0c17f75e886cab`의 `npm.cmd run health` exit0. backend 전체 **1140중1139통과·1skip**, 473.975초; frontend Node9/Vitest460, 타입·lint, 기본 mypy12파일, Electron/의존성 및 QA selftest 체인이 완료됐다. skip은 기존 private F01자료 미제공이다. 이후 계획의 계측 필드와 관련 시험을 보완한 최종 소스 `2976c9a3d86e44ed57e661634775226b84a42b9c`는 SPOT API 전체 **190시험 exit0**, 변경 파일 Ruff·diff 검사 exit0을 확인했다. 전체 health를 이 후속 commit에서 다시 실행한 것으로 표시하지 않는다. 명령·전체 출력·종료 코드·SHA256, 소스4개/고정 원문4개 검산: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/pressure-diagnostics/verification.json`.

IC02의 로컬 구현/기록 계약만 완료 표시했다. 운영 monitor 시작/required writer 제공, PRESSURED 감속·NORMAL 온도 우선/간격, 전체 상태/관측 참조·fact/JPEG·작업 공간·17시나리오, 최종 새 설치본과 master 통합은 계속 미완료다. v2의 구버전 reader 복구는 아직 검증하지 않았다. 최종 배포 전 관련 호환성을 검증해야 하며 승인 운영본을 자동 교체하지 않는다.

전용 security-review 도구가 없어 strict schema·타입·민감정보 비추가·기록 보존·발송/실패 분리·잠금 내 I/O/backoff 없음·명시 제어 경로 비변경을 직접 검토했다. 서버·운영 설치본·설정·백업은 변경하지 않았다. 직전 목표 턴은 재점검 보고로 구현 진전이 없었으므로 이번 턴에는 위 코드·시험을 이어갔다. 일곱 목표와 운영 승격 범위는 유지하고 전체 완료로 표시하지 않는다.


## 2026-10-28 필수 이미지 원장 접근과 초기 읽기 복구

- `9d7110f7`: 실제 원장 파일의 읽기/쓰기 접근·handle/path 식별과 기존 불확실 상태를 확인한다. 폴더 성공을 파일 성공으로 대체하지 않고, 파일 실패도 기존 단일 owner의 1→2→4→8→16→30초 재시도에 연결한다. 회복해도 실패 이력과 원본 bytes를 보존한다.
- `d0d14205`: 초기 digest 또는 CSV 행 읽기가 일시적으로 실패했을 때 잘못 available로 표시되거나 manifest가 영구 불완료로 남는 문제를 수정했다. 행 수·해시를 실제 다시 읽어 확인한 뒤만 초기 manifest 상태를 복원한다. 손상/미확정 상태는 해제하지 않는다.
- `ef537065`: 읽기 실패 사이 원장이 교체·삭제되면 최초 관찰한 파일 식별을 보존해 자동 기준 변경을 차단한다. 같은 bytes의 교체 파일도 수동 복구로 남기며 원본을 생성·절단·수정하지 않는다.
- `e2c29819`: 캡처/UI 요청이 없는 실제 owner에서 파일 잠금→단조 시각 재시도→회복을 검증했다. 새 worker·새 capture가 없고 기존 파일과 실패 이력이 보존된다. 이 시험과 기존 손상/새 경로 guard 보완은 후속 회귀이며 별도 RED로 세지 않는다.

세 행동의 RED→GREEN은 파일 접근 거부, 초기 두 읽기 경로의 복구, 실패 사이 교체/삭제다. 파일 권한 오류는 파일 열기 경계에 주입했고 원장·JPEG·owner·파일 비교는 실제 구성요소를 사용했다. 소스 `e2c29819863d08a38e527e1022be797715c538d5`에서 `npm.cmd run health:backend:test` **1144중 1143통과·1skip**, 469.208초, exit0. skip은 기존 private F01자료 미제공이다. 관련 287시험과 추가 owner1시험, 변경 파일 Ruff·기본 mypy12파일·diff 검사도 exit0. 이번 실행은 backend 전체이며 frontend/Electron/전체 health·새 설치본 결과로 확대하지 않는다.

명령·종료 코드·전체 출력20개와 backend 로그, 소스2개·고정 원문4개·109경로 검산은 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/required-file-state/verification.json`에 보존했다. 파일 접근은 확인 시점의 제한된 증거이며 전체 과거 원장 의미/JPEG 무결성이나 전원 장애 내구성 증거가 아니다. 전용 보안 검토 도구가 없어 원본 비변경·파일 식별·불확실 상태 유지·임시 파일 소유권·권한/인증정보 비추가를 직접 검토했다.

CSV/관측 fact/trace/spool 가용성·예정 시각·세대별 pending, 생성자 중단 초기화의 종료 확인 후 재시작, monitor 운영 연결·PRESSURED/NORMAL 요청 정책·전체 17시나리오·최종 health/build/installer/master 통합은 계속 미완료다. 기존 운영본·서버·설정·백업은 변경하지 않았다. 직전 목표 턴은 기존 남은 항목을 재보고한 NO_PROGRESS이며, 이번 턴은 위 구현과 검증을 진행했다. 일곱 목표와 전체 완료 조건을 유지한다.


## 2026-10-28 초기화 owner 복구와 온도 원장 상태 제공

- `db193c57`, `df079275`: 이미지 생성자 중단 후 이전 worker 종료·backoff를 확인해 재시작한다. 접수 event·예약·원래 경로를 유지하며 저장 OFF 뒤에도 기존 pending을 버리지 않는다.
- `fbd40411`, `e63cabfd`: 초기화 재시도 상한·종료 중 억제·이전 정리 완료·실제 poll 기동을 검증했다. 자원 정리 미확정이면 새 owner/force 시작을 차단하고 종료·manifest 검산도 미완료로 남긴다. 초기화 실패 이력을 지우지 않는다.
- `fd2b8614`: 온도 fact의 queue/inflight 최초 접수 시각·즉시 처리 예정 시각·clock domain을 제공한다. 새 접수·dequeue가 이전 기한을 미루지 않으며 snapshot은 파일을 열지 않는다.
- `38fce813`, `74475830`: 단일 fact owner가 기존 파일을 생성·절단·추가 쓰기 없이 확인한다. 잠금 실패는 새 관측/UI 없이 단조 backoff로 재확인하며 실제 회복과 실패 이력을 분리한다. 재시도 중 동일 bytes 파일 교체도 수동 복구로 남겨 새 접수·정상 종료·manifest 확정을 막는다.
- `7aa74ecb`: fact 재시도 30초 상한·종료 후 중단·원본 삭제와 close 미확정 후 자동 복구 금지를 후속 회귀로 검증했다. 생성자 중단 자동 재시작은 이미지 owner에 대한 완료이며 온도 fact 초기화 실패 재시작 전체를 대신하지 않는다.

최초 관련 회귀는 경로 stat과 handle fstat의 생성 시각 차이를 정상 파일 교체로 오판해 일부 시험이 대기했다. 실제 실행 중인 로컬 시험 child PID/명령을 확인해 중단하고 로그·종료 코드4294967295를 보존했다. 동일 현상의 결정적 RED를 추가한 뒤 기존 이미지 원장과 같은 device/inode/size/mtime 비교로 수정했다. 수정 후 관련39시험 및 최종122시험은 각각1skip을 제외하고 통과했다. 이는 제어기 조건 완화가 아니며 파일 교체 차단 시험도 유지된다.

최종 소스 `7aa74ecb3767c1d377860b5e3126b3aa3f49769d`의 `npm.cmd run health:backend:test`: **1156중 1155통과·1skip**, 474.131초, exit0. skip은 기존 private F01자료 미제공이다. 변경4파일 Ruff·기본 mypy12파일·diff 검사 exit0. 전체 frontend/Electron/health와 새 설치본은 재검증하지 않았다. 25실행의 원 명령·종료 코드·50로그·backend 전체 로그·소스4개·고정 원문4개·109경로를 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/owner-recovery-state/verification.json`에 결합했다. fixture capture ID 누락 실패도 제품 RED와 구분해 보존한다.

남은 범위: 새 fact 쓰기 실패 시 현재 접근 상태 무효화/재예약, CSV/fact/spool/trace required sink 전체 가용성·세대/복구 시각·owner 교체 후 이력, monitor 서비스 연결, PRESSURED/NORMAL 정책, 상태/관측 참조·전체 fact/JPEG·작업 공간 상한·7단계/17시나리오, 최종 health/build/installer와 master 통합. 온도 fact 접근 성공을 전체 저장 가용성이나 과거 무결성 PASS로 확대하지 않는다. 직전 턴은 점검 보고의 NO_PROGRESS였고 이번에는 구현·검증·커밋을 진행했다. 서버·승인 운영본·설정·백업은 변경하지 않았고 전체 목표는 유지한다.

## 2026-10-28 온도 임시 저장 복구와 CSV 데이터 단계 시각

- `53403bd2`: 온도 fact 실제 쓰기 실패 뒤 이전 파일 접근 성공 상태를 unknown으로 바꾸고 재확인을 예약한다. 기존 실패 이력과 마지막 성공 시각은 보존하며 새 실패로 기존 예약을 뒤로 밀지 않는다.
- `46163406`, `b1a96f31`: 같은 owner가 새 관측/UI 없이 기존 spool을 20행·1MiB 처리 단위로 재시도한다. 실패 시 30초 상한의 backoff를 적용하고 진전 시 초기 간격으로 돌아온다. 새 관측은 기존 재시도 간격을 우회하지 않고 spool에 보존한다. 종료가 시작되면 배경 복구는 중지하되 이미 접수된 큐의 기존 정상 종료 drain은 유지한다.
- `47877514`: 큐에 새 관측이 남아 있어도 예정된 20행 복구를 먼저 수행하고, 손상 spool은 원본을 보존한 수동 복구 상태로 남기는 회귀를 확인했다. recovered 계수는 처리된 spool 항목 수이며 서로 다른 관측 수로 확대하지 않는다.
- `e07f8ef5`: CSV 접수 envelope에 같은 프로세스의 단조 접수 시각·고정된 데이터 단계 예정 시각·clock domain을 보존한다. 실제 1초 flush 스케줄도 단조 시계로 계산하며 주기는 바꾸지 않는다. queue/inflight·새 입력·설정 변경으로 기존 기한이 미뤄지지 않는다. 설정 세대·출력별 메모리 상태는 configured directory 조합의 해시를 제공하며 실제 fallback 선택이나 파일 가용성 증거로 쓰지 않는다. 데이터가 기록되고 증거만 기다리는 행은 데이터 단계에서 제외한다.

세 fact 행동과 CSV 접수 시각 행동의 RED→GREEN을 확인했다. 나머지 두 spool 경계와 시계 역행·증거 대기 분리는 구현 후 회귀 검사다. 실제 owner·임시 파일을 사용하고 접근 오류/지연과 시계 경계만 주입했다. 후속 회귀를 새로운 실패 재현으로 집계하지 않았다.

최종 소스 `e07f8ef5a1a9153926ae3dd07563ff872e323f21`와 동일한 5개 파일 SHA256에서 `npm.cmd run health:backend:test`: **1163중 1162통과·1skip**, 466.515초, exit0. 전체 검사는 CSV 변경이 미커밋인 상태에서 실행됐고, 검사 전후 및 커밋 후 소스 해시 일치를 확인했다. skip은 기존 private F01자료 미제공이다. 변경5파일 Ruff·기본 mypy12파일·diff 검사 exit0. 14실행/28로그와 backend 전체 로그·소스·고정 원문4개·109경로·승인 설치본을 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/fact-csv-recovery/verification.json`에 결합했다. 마지막 전체 health는 여전히 `9f7e1dbf`이며 이번 backend 검사를 frontend/Electron/빌드·새 설치본 검증으로 확대하지 않는다.

전용 보안 검토 도구가 없어 원본/파일 식별 보존·불확실 상태 차단·종료 책임·메모리 상태 읽기의 파일 I/O 부재·인증정보/접속 권한 비추가를 직접 검토했다. CSV의 configured destination 해시는 실제 저장 성공이나 파일 접근 성공을 뜻하지 않는다.

남은 범위: CSV/fact/spool/trace의 전체 목적지 가용성·복구/증거 단계 시각·세대별 pending·owner 교체 이력, 온도 fact 초기화 재시도, required writer 제공과 monitor 서비스 연결, PRESSURED 감속·NORMAL 온도 우선, 전체 fact/JPEG 대조·작업 공간·상태/관측 참조·7단계/17명세, 최종 health/build/installer와 master 통합. 이전 점검 턴은 구현 진전 없는 NO_PROGRESS였으며 이번에는 코드·회귀·커밋을 진행했다. 서버·운영 설치본·설정·백업은 변경하지 않았고 일곱 목표를 유지한다.

## 2026-10-28 증거 단계 시각·손상 보류·제한된 재시도

- `e170a0bf`: trace segment 최초 기록의 단조 시각·예정 시각·clock domain을 제공하고 실제 실패한 segment의 기록만 pending_recovery에 포함한다. 강제 조기 flush는 기한을 앞당길 수 있지만 재시도·새 기록이 기존 기한을 미루지 않는다. 정상 예약 대기와 장애 복구 대기를 구분한다.
- `dba2e81d`: 불일치/부분 기록 등 내용이 불확실한 trace는 수동 복구 상태를 유지한다. 외부에서 bytes를 맞춰 놓더라도 자동 공개·새 접수·정상 완료로 전환하지 않으며 원본 pending을 보존한다.
- `1fdff0fe`: trace 수동 복구로 막힌 CSV 접수를 REJECTED_UNAVAILABLE로 연결했다. 실제 용량 부족의 REJECTED_LIMIT와 구분하고 종료는 미완료로 남긴다. 실제 CSV 행과 손상 pending 보존을 검사했다.
- `3edac6b5`: 일시적인 trace 공개 실패는 1→2→4→8→16→30초 상한으로 재시도한다. 새 기록과 force flush가 예약을 우회하지 못하고 성공 후 다음 실패는 1초부터 시작한다. 과거 failure_count는 유지한다. 현재 가용성의 범위는 last_trace_publication이며 디렉터리 전체 probe나 과거 파일 전체 무결성으로 확대하지 않는다.

위 네 행동의 RED→GREEN을 확인했다. 실제 writer/CSV 서비스와 임시 파일을 사용하고 파일 공개 오류·손상·시계만 주입했다. 기존 trace 시험 3개는 실패 직후 즉시 재시도하던 fixture를 첫 재시도 시각 이후로 진행시키도록 조정했으며 원본 보존·복구·손상 보류 주장은 유지했다. 해당 최초 3실패 출력은 제품 RED와 구분해 보존한다. 30초 상한·성공 후 초기 간격·수동 보류의 예약 없음은 후속 회귀이며 별도 RED로 세지 않는다.

clean 소스 `3edac6b51587688e738787bbe7aa91d04541a0d5`의 `npm.cmd run health:backend:test`: **1168중 1167통과·1skip**, 474.908초, exit0. 검사 전후와 커밋 소스의 해시 일치를 확인했다. skip은 기존 private F01자료 미제공이다. 변경4파일 Ruff·기본 mypy12파일·diff 검사 exit0. 13실행/26로그와 backend 전체 로그·소스4개·고정 원문4개·109경로·승인 설치본을 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/trace-recovery-state/verification.json`에 결합했다. 마지막 전체 health는 여전히 `9f7e1dbf`이며 이번 backend 검사를 frontend/Electron/빌드·새 설치본 검증으로 확대하지 않는다.

전용 보안 검토 도구가 없어 원본 보존·불확실 상태 차단·파일 공개 전후 실제 검산·메모리 상태 읽기의 파일 I/O 부재·인증정보/접속 권한 비추가를 직접 검토했다. 재시도 대기 중 force flush는 False이며 성공·완료로 위장하지 않는다.

남은 범위: CSV/fact/spool/trace의 전체 목적지 probe·가용성, spool 및 단계 간 최초 나이/세대 결합, 초기화/종료 수명과 owner 교체 이력, required writer 제공과 monitor 서비스 연결, PRESSURED 감속·NORMAL 온도 우선, 전체 fact/JPEG 대조·작업 공간·상태/관측 참조·7단계/17명세, 최종 health/build/installer와 master 통합. trace 공개 가용성을 다른 파일의 가용성으로 대체하지 않는다. 직전 턴은 CSV 단계 시각 구현·전체 backend 검증·원격 반영의 PROGRESS였으며 이번에도 코드·회귀를 진행했다. 서버·운영 설치본·설정·백업은 변경하지 않았고 일곱 목표를 유지한다.

## 2026-10-28 온도 원장 초기 읽기 복구와 원본 보존

- `2bdef134`: 온도 fact 헤더의 읽기 실패를 다른 스키마로 오인해 원본을 archive/교체하던 경로를 수정했다. 실제 기존 CSV·동일 파일 식별과 임시 저장을 보존하고, 장애 해소 후 원래 관측 ID 두 개가 중복 없이 저장됨을 확인했다. 실제 구버전 헤더의 기존 이관 동작은 유지한다.
- `ebae14ca`: 초기 hash/행 읽기 실패는 동일 파일의 식별·크기·수정 시각을 다시 확인하고 초기 색인을 재구성한다. 부분 색인과 집계는 재시도 전에 초기화한다. 파일 교체·삭제·문자/CSV 해석 오류·닫기 실패는 수동 복구로 유지하며 외부에서 원문을 돌려 놓아도 자동 해제하지 않는다. 초기 읽기 실패 중 새 append를 허용하지 않는다. 일반 append 이후 digest 불확실성을 초기 읽기 재시도로 해제하지 않는다.
- `82de3a6b`: 확인된 초기 읽기 실패는 같은 저장 owner가 새 관측/UI 없이 1→2→4→8→16→30초 상한으로 재시도한다. 기존 접수의 payload·ID·최초 시각을 유지하고, 원본 확인 후 대기 항목을 처리한다. 과거 실패는 남기며 종료 시 새 재시도를 중단하고 잔여 접수를 성공/빈 큐로 표시하지 않는다. generic factory 생성 실패·헤더 쓰기·스풀 초기화 실패까지 복구했다고 주장하지 않는다.

세 행동의 RED→GREEN을 실제 writer와 파일 I/O로 확인했다. 초기 읽기 시험의 첫 시도는 fixture 관측 시각 누락, 첫 green은 fixture의 summary 필드 오타로 실패했으며 두 출력 모두 제품 RED와 구분해 보존한다. 파일 교체/삭제/닫기/문자 오류와 30초 상한·종료 검사는 후속 회귀다. 최종 관련 119시험 중118통과·기존 F01 1skip, exit0.

clean 소스 `82de3a6bb1de6f606bace11bd9092c1af9729462`의 `npm.cmd run health:backend:test`: **1173중 1172통과·기존 F01 자료 미제공 1skip**, 473.834초, exit0. 변경4파일 Ruff·기본 mypy12파일·diff 검사 exit0. 검사 전후/커밋 소스·10실행/20로그·고정 원문4개·109경로·운영 설치본을 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/fact-initialization-recovery/verification.json`에 결합했다. 마지막 전체 health는 `9f7e1dbf`; 현재 전체 health/새 빌드/설치본은 미완료다.

직전 턴은 완료 상태 재점검으로 구현 진전이 없었다. 이번은 실제 원본 보존 문제 수정과 독립 초기 읽기 복구의 PROGRESS다. 전용 보안 검토 도구가 없어 기존 원본 비절단·파일/핸들 식별 대조·닫기 실패 차단·접수 및 실패 이력 보존·추가 권한/네트워크 접근 없음의 경계를 직접 검토했다. 서버/설치본/설정/백업 변경은 없다.

남은 범위는 전체 목적지/필수 파일 가용성, spool 및 단계 간 최초 나이·설정 세대 결합, 나머지 초기화/종료/owner 교체, required writer 상태 제공과 monitor 실제 연결, PRESSURED 감속/NORMAL 온도 우선, 전체 fact/JPEG 대조와 작업 공간, 상태/관측 참조 계약, 7단계·17명세 전체, 최종 health/build/installer와 master 통합이다. 현재 구현은 초기 read 복구이며 전체 과거 자료 무결성 또는 런타임 감시 연결 완료가 아니다.

## 2026-10-28 CSV 목적지 확인·복구 상태와 Windows 종료 경로 수정

- `69c7db48`: 기존 CSV owner가 현재 설정과 이전 접수 세대의 폴더를 새 유입 없이 확인한다. 임시 probe의128byte도 합산 예산에 포함하며 상태 조회에는 파일 I/O를 넣지 않는다.
- `29fb1bd7`: 디렉터리 확인과 본 CSV의 파일 ID/접근 상태를 분리한다. 파일 교체·삭제·확인 핸들 닫기 불확실은 수동 복구로 유지하고 거짓 정상 종료를 차단한다. 본문 전체 무결성·전원 장애 내구성의 증명은 아니다.
- `3062dc7b`: 데이터 write/flush 실패의 출력·설정 세대별 복구 대기는 폴더 검사 성공으로 지우지 않고 해당 데이터 flush 성공 뒤 해제한다. 과거 실패 이력은 유지한다.
- `368b55ae`: 전체 backend에서 정상/복구 종료 두 조건이 exit2로 실패했다. 진단 결과 같은 Windows 경로의 일반/extended-length 표기가 달라 원장 마감을 거부했다. 같은 디렉터리의 실제 식별과 남은 경로명을 대조하도록 수정했다. 생성 전 pending·다른 디렉터리의 hard link 거부·접근 거부 시 차단도 검사했다. 정상/복구 종료 모두 exit0·CSV/이미지 마감 검산을 통과했다.
- `6ee70b61`: 새 CSV 생성/파일 확인이 기존 실패 probe의 단조 재시도 시각을 앞당기던 오류를 수정했다. 실제20행 저장 중에도100→101→103 시각의 재시도와 과거 실패 계수를 유지한다.
- `15044c4f`: AUTO_SAVE OFF·경로 변경·새 접수 없음 조건에서도 이전 파일의 수동 복구 목적지를 유지한다. 새 비활성 폴더는 만들지 않고 원래 세대/목적지·원본 bytes·미완료 종료를 보존한다.

RED→GREEN 및 보완 회귀의20실행/40로그를 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/csv-probe-completion/verification.json`에 결합했다. 최초 CSV probe 회귀의 동시 workspace assertion, 실제 수동 복구 종료 오류, Windows 경로 불일치의 전체 backend 실패와 재현, 새 시험의 상태 키 오타를 구분해 보존했다. 예상과 다른 시험 키 오류를 제품 RED로 집계하지 않았다. 경로 관련89시험 중88통과·기존 F01자료1skip, 별도 CSV 재시도3시험과 수동 복구2시험 통과.

clean 소스 `15044c4faca18093545240413c31b7d098c288b5`에서 **`npm.cmd run health` exit0**. backend **1181중1180통과·기존 F01자료 미제공1skip**, 498.171초. 의존성15·Electron103·frontend Node9/Vitest460, 타입/lint·기본 mypy12파일과 QA selftest를 같은 명령으로 확인했다. 시작/종료 HEAD·소스4개 해시가 같고 원문4개·109경로·운영 설치본·태그를 재검산했다. 과거3062의 전체 backend 실패를 삭제하지 않는다. 이번 검사는 새 설치본 빌드·현장 성능·운영 승격을 대신하지 않는다.

별도 보안 검토 도구가 없어 원본 비절단/비교체·임시 파일 소유권·실제 경로 식별·타 디렉터리 hard link 거부·권한 오류 차단·예약 예산·메모리 상태 조회를 직접 검토했다. 인증정보/접속 권한을 추가하지 않았다. 직전 목표 턴은 상태 재점검으로 구현 진전이 없었으며, 이번은 실패 수정과 검증의 PROGRESS다.

남은 범위: 모든 required fact/spool/trace 및 sidecar 상태·단계 시각/설정 세대 결합·초기화/종료 수명과 owner 교체 이력, monitor 실제 서비스 연결, PRESSURED 감속/NORMAL 간격·온도 우선, 전체 fact/JPEG 대조·작업 공간·상태/관측 참조 계약,7단계/17명세 전체, 최종 변경 후 health/build/installer와 master 통합. monitor 기본 None은 그대로다. 서버·운영 설치본·설정·백업 변경은 없다.

## 2026-10-28 온도 임시 저장 용량·접근 실패·파일 변경 보호

- `25e6ec1a`: owner가 임시 저장 대기/보존 bytes를 게시한다. 메모리 큐에서 빠진 자료도 실제 스풀 복구 전까지 용량에 남고, 상태 조회에는 파일 I/O가 없다.
- `e6b582ae`: Path.glob이 디렉터리 접근 오류를 빈 목록으로 숨기는 경계를 수정했다. 마지막으로 확인한 bytes는 유지하고 unknown/PermissionError를 게시한다. 실제 기존 owner가 새 유입 없이 backoff 후 원래 ID를 한 번만 저장하고 과거 실패를 보존한다.
- `3519b32d`, `dc136702`: 관찰한 임시 파일의 삭제·폴더 소실·잘림·교체·mtime 변경은 수동 복구 상태로 남긴다. 원래 대기 건수와 bytes, 실패 이력을 보존하고 임의로 파일을 복원해도 같은 owner가 자동 해제하지 않는다. 정상 복구 후 owner가 삭제한 segment만 추적에서 제거한다.
- `44c1d7a4`: 복구 읽기의 실제 handle과 읽기 완료 뒤 경로를 관찰한 파일 식별/크기/mtime에 대조한다. 읽기 직전·종료 직후 교체는 원장 append 전에 차단하고 교체된 원문을 자동 삭제하지 않는다. metadata stamp는 전체 내용 hash나 전원 장애 내구성 증명이 아니다.

실제 writer·owner와 파일 I/O 경계로 RED→GREEN을 확인했다. 기존 용량 시험의 helper 누락, 읽기 교체 시험의 초기 fixture 캡처 전에 mutation이 발생한 오류는 제품 RED와 구분해 보존했다. 마지막 관련95시험 중94통과·기존 F01자료1skip. 총17실행/34로그와 변경 소스·원문4개·109경로·stash·운영 설치본을 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/spool-integrity/verification.json`에 결합했다.

clean `44c1d7a4`에서 `npm.cmd run health:backend:test` **exit0**, **1188중1187통과·F01자료1skip**, 500.185초. 최종3파일 Ruff·기본 mypy12파일·diff 검사 exit0. 마지막 전체 health는15044c4f이며 현재 소스 전체 health·새 빌드·설치본·master 통합은 미완료다. 이번에 서버·설정·백업은 변경하지 않았다.

남은 범위: 스풀 append/close/unlink 동시 변경과 추적 metadata 예산, 모든 required fact/spool/trace·sidecar 가용성, 단계별 최초 시각/설정 세대·초기화/종료·owner 교체, monitor 실제 서비스 연결, PRESSURED 감속/NORMAL 온도 우선, fact/JPEG 전체 대조·작업 공간·상태/관측 참조 계약,7단계/17명세 전체 및 최종 배포 준비. 직전 감사는 접근 오류 재현으로 다음 행동을 바꾼 PROGRESS였고 이번에는 구현·회귀 검증을 진행했다. 전체 목표는 미완료다.

후속 제어 경계도 실제 순수 controller로 확인했다. enabled=False·대기 계수0이지만 manual_recovery_required=True인 이전 목적지를 입력하면 현재 NORMAL/available을 반환한다. `disabled-manual-controller-reproduction.json`에 입력/결과를 보존했다. 저장 비활성화가 이전 미해결 상태를 제외하지 않도록 고친 뒤 전체 상태 제공·monitor 연결로 이어가야 한다. 이 재현은 코드·설정 변경이나 서버 실행이 아니다.

## 2026-10-28 온도 저장 목적지의 독립 확인·회복·수동 복구

- `fc071951`: 저장 OFF·대기0인 이전 목적지라도 manual_recovery_required를 압력 평가에서 제외하지 않는다. 원래 실패 재현은 보존했다.
- `b4d905c1`: 새 spool에 최초 접수 단조 시각·clock domain을 보존하고 복구 진행에 맞춰 oldest/stage due를 갱신한다. 기존 파일의 시각은 근거 없이 known으로 바꾸지 않으며 CSV 열은 유지한다.
- `a2d2e11c`: 기존 온도 owner가 원장 폴더와 실제 spool segment 폴더를 각각 확인한다. 128byte도 합산 예산에 포함하며 조회 함수는 메모리 상태만 복사한다.
- `9e0ce51d`: 초기 성공 이후에도 1초 단위로 확인한다. 실패는 1→2→4→8→16→30초 간격, 회복은 과거 실패 보존, 종료 후 추가 검사 없음으로 검증했다.
- `3cfa28e5`: 확인 파일 교체·내용 불확실은 새 접수와 정상 마감을 차단한다. 다른 소유자 파일을 삭제하지 않는다.
- `7a03a789`: 확인 파일 정리 실패를 일반 접근 실패와 구분한다. 온도 owner는 수동 복구를 유지해 반복 생성하지 않는다. CSV/이미지 owner의 같은 수명 연결은 후속 항목이다.
- `a1d78c47`: 전체 health에서 데이터 큐 drain 직후 확인 작업128byte를 읽어 0byte 주장에 실패한 시험을 실제 파일 읽기 대기로 재현했다. 데이터 대기0·확인 작업128byte의 합산 예산·owner 종료 후 전체0을 구분하도록 시험을 수정했다.16MiB 한도나 제품 동작은 완화하지 않았다.

실패 재현·회귀 22실행과 전체 로그 44개를 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/fact-destination-recovery/verification.json`에 결합했다. 최초 신규 시험의 try 블록 삽입 오류와 회귀 명령의 잘못된 이미지 시험 모듈명은 각각 fixture/명령 오류로 구분했다. 전자는 배치를 수정한 뒤 실제 기능 실패를 재현했고, 후자는 실행된108시험의 결과와 실제 이미지/시작39시험을 대조했다. 최종 관련150시험은149통과·기존 F01자료1skip, exit0이다.

clean `7a03a789`의 최초 `npm.cmd run health`는 backend1195중1실패·1skip으로 exit1이며 QA에 도달하지 않았다. 의존성15·Electron103·frontend Node9/Vitest460과 타입/lint·기본 mypy12파일은 해당 실행에서 통과했다. 시험 한 파일만 수정한 clean `a1d78c47`에서 **`npm.cmd run health:backend:test`와 `npm.cmd run health:qa:selftest` exit0**을 확인했다. backend **1195중1194통과·기존 F01자료1skip**, 503.805초. 변경 없는 선행 검사를 반복하지 않았으며 새 단일 health 명령 exit0을 주장하지 않는다. 시작·종료 HEAD/소스 해시와 원본4문서·109경로·stash·운영 설치본을 재검산했다. 앞선 감사의108시험 중1실패도 이번 구현으로 해결했으며 원래 감사와 모든 실패 기록을 보존한다.

현재 상태는 전체 완료가 아니다. 전체 required 상태/설정 세대·trace/sidecar, 초기화·종료 수명, CSV/이미지 probe 정리 불확실성, monitor 실제 서비스 연결, PRESSURED/NORMAL 제어, 전체 fact/JPEG 대조·7단계/17명세와 최종 빌드/설치본·master 통합이 남는다. 운영 태그·서버·백업은 변경하지 않았다.

## 2026-10-28 CSV·이미지 확인 파일 정리 실패와 idle 재확인

- `e69b86aa`: 실제 CSV probe 삭제 실패를 수동 복구로 유지한다. 신규 접수/정상 마감을 차단하고, 대기 행이 없거나 저장 OFF·목적지 변경 뒤에도 원래 목적지를 유지한다. 실패 확인 파일은 반복 생성하지 않는다.
- `ad826108`: 이미지 원장/JPEG 폴더 probe 정리 실패를 같은 writer의 수동 복구로 고정한다. 설정 세대·날짜 변경/직접 쓰기로 우회하지 못하며 원본을 보존한다.
- `7669db69`: 실제 이미지 서비스의 접수·owner 교체·종료에 이 상태를 연결한다. 새 접수는 REJECTED_UNAVAILABLE, 미해결 종료는 writes_drained=False로 기록한다. 기존 owner/이미 접수한 작업은 보존한다. 임시 파일 정리 불확실을 이미지 유실 수로 바꾸지 않는다.
- `70d92a80`: 초기 성공 뒤 멈췄던 idle 확인을 1초 주기로 재개한다. 실패 시 기존 1→2→4→8→16→30초 backoff, 실제 회복 후 과거 실패 보존, 종료 후 추가 probe 없음과 메모리 전용 조회를 검증했다.

4개 실제 행동 실패와 관련 회귀를 포함한 13실행·26로그를 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/probe-cleanup-owners/verification.json`에 결합했다. CSV 관련107시험, 이미지 서비스/종료 관련356시험, 최종 이미지 시작/원장42시험을 통과했다. 중간42시험의1실패는 회복 뒤 다시 확인하지 않는 이전 기대값과 새 요구의 충돌이었다. 해당 실패를 보존하고, 기존 backoff 검사는 유지하면서 회복 후1초 확인과 실패 이력8건 유지로 기대값을 갱신했다. 마지막42시험 exit0이다.

clean `70d92a80`에서 `npm.cmd run health` **exit0**. 의존성15·Electron103·frontend Node9/Vitest460, lint/typecheck, backend **1199중1198통과·기존 F01자료1skip**(511.475초), QA 자체 검사까지 완료했다. 시작/종료 HEAD와 소스 해시가 같고, 운영 설치본·원본4문서·109경로·보호 stash를 재검산했다. 이전 health 실패나 과거 현장 판정은 재작성하지 않았다.

이전 목표 턴은 검증 자료 커밋·원격 반영으로 PROGRESS, 이번 턴은 실제 구현/회귀 검증으로 PROGRESS다. 전체 required 파일/세대/단계 시각, 초기화·spool 경계와 합산 metadata 예산, 실제 monitor 연결·PRESSURED/NORMAL 제어, 화면/관측/판정 계약·전체17명세, 최종 빌드/설치본·master 통합은 계속 미완료다. 이번에는 서버·운영 태그·백업을 변경하지 않았다.


## 2026-10-28 추적 목적지·마지막 공개 파일의 독립 확인

- `f6a04f03`: 기존 CSV owner가 새 데이터/UI 요청 없이 idle 추적 폴더를 확인한다. pending 공개가 우선이며 정상1초·실패최대30초 간격과 별도 probe 실패 이력을 사용한다. 확인128byte도 예약하며 메모리 상태 조회는 파일 I/O를 하지 않는다.
- `0eaffb8d`: 마지막 공개 segment의 파일 식별·크기·mtime과 실제 읽기 handle을 대조한다. 삭제·교체·변경은 수동 복구로 남고 폴더 성공으로 해제하지 않는다. 확인 작업은 원문을 생성·절단·재기록하지 않는다.
- `89492096`: 신규 segment가 기존 파일 접근 장애나 probe 재시도 간격을 우회하지 못한다. 실제 접근 회복 뒤 원래 ID의 기록을 한 번만 공개하고 과거 실패는 보존한다.
- `47d9c3b9`: 확인용 읽기 handle의 close 불확실은 handle 하나를 보유한 수동 복구로 남겨 추가 열기·접수·공개를 차단한다. fixture에서 남긴 handle은 시험 종료 시 명시 정리했다.

4개 행동의 예상 RED와 관련 검사를 12실행·24로그로 보존했다. 최초 관련129시험, 마지막 파일 식별 관련24시험, 새 기록 재시도 trace23시험/CSV2시험, 마지막 close 처리 trace24시험이 통과했다. 직접 시험과 모듈을 함께 실행한 중간23회에는 같은 신규 시험의 중복 실행1회가 있으며 독립 시나리오 수로 합산하지 않는다. 근거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/trace-idle-access/verification.json`.

clean `47d9c3b9`에서 `npm.cmd run health` **exit0**. 의존성15·Electron103·frontend Node9/Vitest460, lint/typecheck, backend **1203중1202통과·기존 F01자료1skip**(518.427초), QA 자체 검사까지 완료했다. 시작/종료 HEAD·소스 해시가 일치하고 원본4문서·109경로·보호 stash·기존 운영 설치본을 재검산했다. 이전 실패를 삭제하지 않았다.

이 확인은 마지막 공개 파일의 metadata·접근 범위다. 전체 과거 segment 내용 검산, 동일 metadata를 유지한 외부 내용 변경의 탐지, 추적 파일 전체 세대/단계 시각·서비스 교체 이력의 증명이 아니다. 전체 required 상태·monitor 실제 연결, PRESSURED/NORMAL 제어, 초기화/spool 경계·합산 예산·관측/판정 계약, 전체7단계/17명세와 최종 빌드/설치본·master 통합이 남는다. 직전 사용자 요청 감사는 구현 관점 NO_PROGRESS였으며 이번은 실제 구현·검증 PROGRESS다. 서버·운영 태그·백업은 변경하지 않았다.


## 2026-10-28 실제 CSV·추적 상태와 공유 용량의 제어기 연결

- `3bd20527`: 추적 확인 작업의 예약 bytes에 최초 단조 시각·예정 시각을 연결했다. 새 접수 때문에 지연 시각이 뒤로 밀리지 않는다.
- `5fa2fbd0`: 필수 목적지의 설정 세대/식별자가 없으면 unknown으로 차단한다. 저장 OFF·대기/수동 복구 없음은 평가에서 제외한다. 기본 mypy 범위를13파일로 넓혔다.
- `8025cca9`: 실제 CSV owner가 추적 생성 당시 세대를 전달한다. 추적 표본은 원래 목적지·가용성·용량·단계 시각·복구 상태를 메모리에서 읽는다. 뒤의 CSV 설정 변경이 기존 추적 위치를 바꾸지 않는다.
- `c5a73dad`: 사용량100% 미만이어도 다음 기록의 작업 공간이 없어 실제 접수가 거절된 상태를 제어기에 연결했다. 이를 물리 저장소 접근 실패로 바꾸지 않으며 용량 회복 뒤 해제한다.
- `87d4cc78`: CSV 목적지별 상태·원래 단계 시각과 owner 공유 예산을 함께 전달한다. 세대별로 나뉜 대기2+1건이 공유 한도3건에서100%로 평가된다. 공유 예산은 max 평가에만 쓰며 출력별 표본 수만큼 합산하지 않는다. 데이터 저장 뒤 보존되는 증거용 메모리는 완료한 데이터 단계의 시계를 다시 시작시키지 않는다.
- `c6901ab5`: 실제 확인 작업의128byte와 시작 시각을 원래 목적지에 연결했다. 저장 OFF·경로 변경 중에도 진행 중인 확인 위치를 보존한다. 지연된 파일 I/O는 PRESSURED로 평가되고 조회는 파일을 열거나 stat하지 않는다.

이전 감사에서 실패했던 `test_trace_pressure_binding_survives_csv_configuration_change`는 실제 구현 뒤 통과했다. 해당 실패와 최초 호출 이름 안내의 정정도 보존한다.14실행·28로그를 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/owner-pressure-join/verification.json`에 연결했다. 앞 단계35/36시험, 추적 연결37시험, 접수 용량36시험, 세대 공유13시험, 실제 probe15시험이 각각 통과했으며 중복 포함 합계를 독립 시나리오 수로 주장하지 않는다.

clean `c6901ab5`에서 **`npm.cmd run health` exit0**. backend **1207중1206통과·기존 F01자료1skip**(515.962초), 의존성15·Electron103·frontend Node9/Vitest460·lint/typecheck·기본 mypy13파일·QA 자체 검사를 확인했다. 시작/종료 HEAD와 소스7파일 해시가 일치한다. 원문4문서·109경로·보호 stash를 재확인했다. 운영 설치본은 이번 감사의 기존 SHA256 대조를 참조하며 새 설치본으로 바꾸지 않았다.

전용 보안 검토 도구가 없어 파일 I/O 없는 조회·잠금 순서·공유 예산 중복 합산 방지·원래 세대 유지·해시 식별자 사용을 직접 검토했다. 이는 전체 보안 감사의 대체물이 아니다. 직전 목표 턴은 읽기 감사로 구현 NO_PROGRESS였고 이번은 구현·검증 PROGRESS다.

남은 범위는 전체 required fact/spool/trace/image/sidecar 파일 무결성·상태와 세대/시각, 초기화·owner 교체·spool 경계·합산 metadata 예산 및 접수 전 작업 시각, 실제 monitor 시작/종료, PRESSURED 감속·NORMAL 온도 우선/간격, 전체 fact/JPEG·관측/화면/판정 계약,7단계/17명세·최종 빌드/설치본·master 통합이다. CSV 상태 제공 함수의 추가를 전체 monitor 활성화로 확대하지 않는다. 서버·운영 태그·설정·백업 변경은 없다.


## 2026-10-28 온도 원장·임시 저장 상태의 제어기 연결

- `31b1db7c`: 실제 온도 원장과 임시 저장 폴더의 가용성·현재 복구·수동 복구·공유 예산을 메모리 표본으로 연결했다. 한 폴더의 성공이 다른 필수 폴더 실패를 숨기지 않으며, 장애 해소 뒤3회 연속 확인을 거쳐 NORMAL로 복귀한다.
- `6bdf20cd`: 실제 서비스의 owner 생성 잠금 안에서 저장 세대를 부여한다. 경로 변경·저장 OFF 뒤에도 접수된 자료의 원래 세대·목적지·지연 시각을 유지하고 실제 원본 경로에 저장한다. 전체 owner 교체 이력의 완료는 아니다.
- `3b06432c`: owner 작업 공간 예약의 최초 시각을 목적지별로 유지한다. 원장/임시 폴더의 idle 확인128byte가 실제 폴더의 단계로 집계되며, 정상 짧은 대기와2초 이상 지연을 구분한다. 공유 메모리를 중복 합산하지 않고 종료 후 예약을 해제한다. 이전 spool의 알 수 없는 시각은 확인 작업의 새 시각으로 덮지 않는다.

예상 행동 실패와 관련 회귀11실행/22로그를 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/fact-pressure-join/verification.json`에 보존했다. 실제 세대 시험의 첫 회귀는 데이터 대신 초기 헤더 생성을 지연한 fixture 오류였다. 초기화 뒤 데이터를 지연하도록 고치고 수정 전 코드의 세대 누락 RED를 다시 확인했다. idle probe 관련67시험은66통과·기존 F01자료1skip이었으며 이후 mypy의 목적지 str/Literal 오류1건을 수정했다. 마지막 관련3시험과 정적 검사는 통과했다. 이 기록들을17개 전체 명세 통과로 합산하지 않는다.

clean `3b06432c`에서 **backend lint·typecheck·전체 unittest·QA 자체 검사 모두 exit0**. backend **1209중1208통과·기존 F01자료1skip**(512.578초). 시작/종료 HEAD·변경3파일 해시가 일치한다. 마지막 단일 전체 health는 `c6901ab5`이며 변경 없는 frontend/Electron/의존성 결과는 그 실행에서 재사용했다. 새 전체 health 실행이나 새 설치본 검증을 주장하지 않는다. 원문4문서·109경로·보호 stash를 다시 대조했다.

데이터 상태 조회의 파일 I/O 없음, 단일 owner의 잠금/예약 해제, 해시 식별자·세대 보존과 unknown 시각 처리를 직접 검토했다. 전용 보안 검토 도구는 없으며 전체 보안 감사로 확대하지 않는다. 직전 목표 턴은 상태 점검으로 구현 NO_PROGRESS였고 이번은 구현·회귀 검증 PROGRESS다.

남은 범위: 전체 required fact/spool/trace/image/sidecar 파일 무결성·상태와 세대/시각, 초기화·owner 교체·spool append/close/unlink 경계·합산 metadata 예산 및 접수 전 작업 시각, 실제 monitor 시작/종료, PRESSURED 감속·NORMAL 온도 우선/간격, 전체 fact/JPEG·관측/화면/판정 계약,7단계/17명세·최종 빌드/설치본·master 통합. monitor는 실제 서비스에 아직 연결하지 않았다. 서버·운영 태그·설정·백업 변경은 없다.


## 2026-10-28 이미지 접수 시각·설정 세대와 압력 표본 연결

- `314ec6af`: 이미지의 최초 접수 단조 시각을 queue/inflight/복구 대기에서 보존하고 실제 종결과 함께 해제한다. 재시도·신규 작업으로 최초 시각을 바꾸지 않는다. payload 없는 metadata는 객체 ID 재사용 전에 같은 잠금 안에서 제거한다.
- `0b338905`: 설정 잠금과 같은 접수 경계에서 세대를 결합하고 원장 파일·취득 날짜의 JPEG 폴더를 해시 식별자로 보존한다. OFF·경로 변경 뒤에도 원래 위치에 각각 저장하고 대기 상태를 분리한다.
- `ebf564a1`: 실제 원장/JPEG 목적지의 독립 접근 결과를 제어기 표본으로 제공한다. 한 위치 실패 시 BLOCKED, 회복 뒤3회 확인 시 NORMAL이며 조회는 파일을 열지 않는다.
- `3f41d7c1`: 접수 당시 목적지·시각·예약량과 현재 가용성을 결합한다. 실제 JPEG 쓰기를 지연하면 최초 대기3.25초로 PRESSURED, OFF 뒤에도 같은 대기 유지, 저장 완료 후 해제된다. 공유 예산은 출력별로 더하지 않는다.

네 예상 RED와 관련17실행/34로그를 `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-pressure-join/verification.json`에 보존했다. 관련84시험·최종 시각2시험·세대85시험·idle 압력47시험·최종 이미지/시작/제어97시험이 통과했다. 겹치는 실행을 독립 시나리오 수로 합산하지 않는다. 각 단계·최종 정적 검사는 exit0이다.

clean `3f41d7c1`에서 **backend lint·typecheck·전체 unittest·QA 자체 검사 모두 exit0**. backend **1211중1210통과·기존 F01자료1skip**(523.075초). 시작/종료 HEAD·변경3파일 SHA가 일치한다. frontend/Electron/의존성은 마지막 단일 전체 health `c6901ab5` 이후 변경이 없어 그 근거를 재사용했다. 새 전체 health 실행 또는 새 설치본 검증을 주장하지 않는다. 원문4문서·109경로·보호 stash를 재대조했고 운영 설치본은 같은 날 감사의 실물 해시 결과를 연결했다.

파일 I/O 없는 조회, 잠금 순서, payload 없는 제한된 metadata, 객체 ID 재사용 전 제거, 해시 식별자·unknown 보존을 직접 검토했다. 전용 보안 검토 도구는 없어 전체 보안 감사로 확대하지 않는다. 앞 목표 턴은 읽기 감사로 구현 NO_PROGRESS, 이번은 구현·검증 PROGRESS다. 진행 기록 생성기 준비 중 따옴표 구문 오류는 실행 전 발견·수정했으며 제품 코드/시험 실패로 집계하지 않는다.

남은 범위: 이미지 초기화/probe/decode/append 작업 공간의 목적지·시각, 이전 owner/세대 및 sidecar 상태, 전체 파일 무결성과 spool append/close/unlink, 합산 metadata 예산·접수 전 시각, monitor 실제 시작/종료, PRESSURED 감속·NORMAL 온도 우선/간격, 전체 fact/JPEG·관측/화면/판정 계약,7단계/17명세·최종 빌드/설치본·master 통합. 미결합 작업 공간은 unknown/BLOCKED로 보존하며 monitor는 실제 서비스에 연결하지 않았다. 서버·운영 태그·설정·백업은 변경하지 않았다.


## 2026-10-28 이미지 작업 공간의 목적지·시각·세대 연결

- `df0475f6`: 연결된 온도 snapshot 해석 메모리를 원래 capture의 목적지·세대·시각과 결합한다. 해석 뒤 실제 보유량으로 줄이고 종결/재시도 전 임시 사본을 버린 뒤 같은 잠금 안에서 예약과 metadata를 해제한다. 파일 저장 지연·OFF에서 원래 binding과 합산 상한을 유지한다.
- `454751cc`: image writer의 probe128 bytes·JPEG 재읽기 최대4096 bytes·원장 digest 버퍼 예약에 실제 sink/경로 해시/세대와 단조 시작 시각을 붙인다. idle JPEG 폴더 확인을 지연하고 OFF로 바꿔도 원래 목적지의 3.25초 지연을 PRESSURED로 판정하며, 끝나면 예약·확인 파일이 정리된다. capture 건수를 작업 공간 수만큼 늘리지 않는다.
- `2b78c443`: writer 생성 이전 및 이전/새 경로의 실제 원장 읽기에 접수 당시 세대를 전달한다. 현재 설정이나 기본 세대0으로 기존 작업을 재분류하지 않는다. 외부 I/O 전에 설정/접수 상태만 복사하고 잠금을 해제한다.

3개 행동 RED를 확인한 뒤 순서대로 구현·관련 검증·커밋했다. decode 관련97시험과 최종2시험, probe/세대 관련162시험씩 통과했다. 중복 실행 수를 17명세 통과 개수로 합산하지 않는다. 첫 probe 시험은 삽입 위치 들여쓰기 오류로 실행되지 않아 RED로 세지 않고, 수정한 `red-r2`의 행동 실패를 사용했다. decode 타입 검사1건은 object/int token 목록 타입을 명시한 뒤 최종 통과했다. 모든 원래 결과를 보존했다.

clean `2b78c443`에서 **backend lint·typecheck·전체 unittest·QA 자체 검사 모두 exit0**. backend **1212중1211통과·기존 F01자료1skip**(515.707초). 변경4파일의 시작/종료 SHA와 HEAD가 일치한다. 근거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-workspace-join/verification.json`. frontend/Electron/의존성은 마지막 단일 전체 health `c6901ab5` 이후 변경하지 않아 그 근거를 재사용하며 새 전체 health·설치본 검증을 주장하지 않는다. 원문4문서·원래109경로·보호 stash도 보존을 재확인했다.

수동 검토: 원본 payload를 metadata에 넣지 않음, 예산 초과 시 예약/metadata 없음, finally와 terminal 잠금의 원자적 해제, config→accounting 잠금 순서 및 I/O 이전 잠금 해제, 해시 목적지 식별과 상태 조회의 파일 I/O 없음. 전용 보안 검토 도구는 없어 이 범위의 직접 검토로 제한한다. 직전·이번 목표 턴 모두 구현/검증 PROGRESS다.

남은 범위: 기존 예약 밖의 이미지 초기화·append 단계, 이전 owner/세대 가용성·sidecar, 전체 파일 무결성·spool append/close/unlink·metadata 합산 예산·접수 전 시각, monitor 실제 시작/종료와 PRESSURED 감속·NORMAL 온도 우선/간격, fact/JPEG 대조·관측 참조·공개 상태/판정 계약,7단계/17명세·최종 빌드/설치본·master 통합. monitor 실제 연결과 서버 변경은 하지 않았다. 운영본·태그·설정·기존 실패 원문은 유지한다.

다음 구현 위치를 확인했다. `SpotImageCaptureWriter._append_fact()`의 StringIO/UTF-8 사본은 아직 예약 없이 생성하며, `_load_fact_row_count()`와 `_check_fact_access()`는 digest/probe 버퍼 예약 바깥에서 파일을 읽거나 연다. 이 단계의 합산 메모리·최초 시각과 실패/close 경계를 먼저 검증해야 실제 monitor를 연결해도 정상 작업의 거짓 BLOCKED 또는 누락된 지연을 방지할 수 있다. 이번 변경의 완료 범위에 포함하지 않았다.


## 2026-10-28 이미지 원장 직렬화·파싱·파일 접근 작업 공간

- `e7619fa6`: CSV 직렬화 전에 StringIO·CSV writer·UTF-8/BOM 임시 사본의 예산을 예약한다. 예산 부족 시 렌더링 전에 차단하고, 실패 traceback에 남을 수 있는 임시 사본을 예약 반환 전에 정리한다. 실제 JPEG는 보존하고 거절 사유를 기록한다.
- `0c565d87`: 이력·행수·헤더 파싱의 작업 공간을 파일 열기 전부터 reader/파일 닫기까지 예약한다. 파일 길이와 무관하게 논리 행1MiB의 제한을 유지한다. 일반 이력 파서 예약은 약24MiB의 보수적 예산이며 실제 RSS 측정값이나 최적값을 뜻하지 않는다.
- `08bc1167`: 같은 열 이름을 모두 따옴표로 감싼 정상 CSV 헤더도 기존 bytes를 보존하며 이어 쓸 수 있게 했다. 헤더가 작다는 이유로 허용 CSV 표현을 차단했던 새 경계 오류를 수정했다.
- `7a5d370c`: idle 원장 파일 접근의 버퍼·잠금/파일 대기에 원래 목적지·세대·단조 시작 시각을 연결한다. 실제 파일 열기 중 저장을 꺼도 대기 상태가 남고3.25초 지연은 PRESSURED, 종료 뒤 예약0·원본 보존을 확인했다.

4개 행동 RED를 보존하고 각 수정 뒤 관련 검사를 통과해 순서대로 커밋했다. 관련 검사는 append163, read164, quoted-header165, file-access166시험이 각각 통과했다. 중복 실행을 전체17명세 통과 개수로 합산하지 않는다. 첫 append GREEN은 legacy capture ID와 빈 receipt ID를 비교한 fixture 오류로 실패해 명시적 ID를 부여했다. 첫 quoted-header GREEN은 시험 모듈 이름2개를 잘못 지정해 import 오류가 났으며, 정확한 모듈의 재검사로 해결했다. 원래 실패 기록도 보존했다.

clean `7a5d370c`에서 **backend lint·typecheck·전체 unittest·QA 자체 검사 모두 exit0**. backend **1216중1215통과·기존 F01자료1skip**(512.175초). 시작/종료 HEAD와 변경4파일 SHA가 같고, 로그 전체의 실패/오류와 종료 코드를 확인했다. 근거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-fact-workspace/verification.json`. 변경 없는 frontend/Electron/의존성은 마지막 단일 전체 health `c6901ab5`의 근거를 재사용한다. 새 전체 health·빌드·설치본 통과로 표시하지 않는다. 원문4문서·109경로·보호 stash도 재검산했다.

직접 검토한 범위는 예약 전 할당 차단, finally의 임시 사본/reader 정리, 정상 CSV 표현 유지, 파일 접근의 시각/세대 결합, 조회 경로의 파일 I/O 없음이다. 전용 보안 검토 도구가 없어 전체 보안 감사로 확대하지 않는다. 직전·이번 목표 턴 모두 실제 구현·검증 PROGRESS다.

남은 범위는 초기화 stat/identity와 close 실패 시 자원 소유, metadata/cache 합산 예산, 이전 owner/세대 가용성·sidecar, 전체 파일 무결성·spool append/close/unlink·접수 전 시각, 실제 monitor 시작/종료·PRESSURED 감속·NORMAL 온도 우선/간격, fact/JPEG 대조·관측 참조·공개 상태/판정 계약,7단계/17명세·최종 빌드/설치본·master 통합이다. `_storage_pressure_monitor`를 실제 서비스에 아직 연결하지 않았다. 서버·운영본·태그·설정·백업은 변경하지 않았다.


## 2026-10-28 F01 입력 자료 발견과 누락 시험 보완

사용자의 전용 자료 질문에 따라 Downloads까지 다시 확인하여 `C:/Users/user/Downloads/Codex_Temperature_20260909_Goal_Package/fixtures/F01_startup_and_poll1.csv`를 찾았다. 1303015bytes·940행이며 SHA256 `bab8f61354124b5fdfa155abdb289255a2514fb710f4fa5e23a7e43418dec4b4`가 기존 시험의 고정값과 일치한다. 2026-09-09 자료에서 원래 열/셀을 내보낸 부분집합이며 원본 바이트 구간 사본이나 새 현장 측정은 아니다. 사용자에게 새 자료·장비·비밀번호를 요청할 필요가 없다.

이전 일반 실행은 `TEMPERATURE_GOAL_PACKAGE`가 지정되지 않아 skip됐다. 이번 확인 전에는 자료 위치를 더 조사하지 않고 같은 skip 설명을 반복했다. 과거 NAS/ZIP 미발견 기록은 당시 조사 범위의 결과로 보존하고, 현재 개발 PC Downloads에서 찾은 사실을 별도로 기록한다.

자료 폴더를 해당 시험 프로세스의 환경변수로 전달해 `backend.tests.test_temperature_fact_queue.FactPollingTests.test_f01_raw_inputs_poll_publish_csv_continue_during_fact_initialization`을 실행했다. **1시험 통과·skip0·exit0**. 두 원시 온도 응답을 재생하여, 원장 초기화가 지연된 동안 최신 온도 게시와 CSV 저장이 진행되고 마지막 저장 정산이 완료됨을 확인했다. 시간 기록에서도 CSV 증거 시각이 초기화 완료보다 앞섰다. 실제 장비·화면 성능 시험으로 확대하지 않는다.

근거: `C:/Users/user/Desktop/SmartFactory/BRANCH_SYNC_20261026_4d2950c6/image-fact-workspace/f01-replay/verification.json`. 직전 전체 backend 실행의1215통과·1skip은 그대로 보존하며, 제품 소스 SHA가 같은 상태의 보완1시험을 연결한다. 전체1216시험을 skip0으로 한 번에 다시 실행한 결과는 아니다. 원시 CSV는 읽기만 했고 Git에 넣지 않았다. 제품 코드·서버·운영본은 변경하지 않았다.

이 개발 PC에서 후속 전체 backend 검사를 실행할 때는 아래처럼 위치를 명시하여 같은 이유의 skip을 방지한다. 다른 PC/CI에 자료가 있다고 가정하거나 임의 파일로 고정 해시를 대체하지 않는다.

```powershell
$env:TEMPERATURE_GOAL_PACKAGE = 'C:\Users\user\Downloads\Codex_Temperature_20260909_Goal_Package'
npm.cmd run health:backend:test
```

이는 개발 검사용 절차이며 사용자가 직접 실행할 요청이 아니다. 전체 HTTP 개선·최종 빌드·master 통합의 미완료 상태는 유지한다.
