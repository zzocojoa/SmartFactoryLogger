# 브랜치 통합과 HTTP 저장 무결성 구현 진행 기록

2026-10-26. 사용자가 승인한 7개 항목을 모두 완료 대상으로 유지한다.
운영 서버의 승인된 1.0.32 설치본과 다음 개발 소스의 검증 범위를 구분한다.

## 완료 조건과 현재 상태

| 번호 | 완료 조건 | 현재 상태 / 근거 |
|---|---|---|
| 1 | 현재 브랜치에 운영 태그의 후속 10개 커밋 통합 | `685dde94`에서 `cd46692a`로 fast-forward 완료. 로컬 후속 작업 재적용·현재 전체 health 검증 완료 |
| 2 | 운영본의 백엔드·회귀 시험 누락 보완 | `spot_api.py`, `repository.py`, CSV 시작 회귀 시험 등 운영 태그 파일 복원. 후속 개선을 포함한 현재 전체 health 검증 완료 |
| 3 | 버전 파일 5개를 운영 소스 기준과 일치 | 1.0.32로 동기화. 새 기능의 출시 승인·배포를 의미하지 않음 |
| 4 | 기존 109개 변경 보존·검토·커밋 | 109개 경로 모두 추적·커밋. 도구 충돌 15파일/29블록 통합. 2026-10-27 원본 4문서 모두 기존 SHA256과 일치하도록 복원했고 보호 stash도 유지 |
| 5 | 원격 브랜치·upstream·기본 브랜치 반영 | 원격 작업 브랜치 생성·upstream 연결·HEAD 대조 완료. master 통합은 미완료 |
| 6 | HTTP 저장 무결성 계획의 7단계·17개 추가 시험 및 경계 계약 구현 | 2026-10-27 1단계 착수. fact 큐의 inflight 포함 건수 상한부터 구현. 전체 범위 유지 |
| 7 | 최종 통합 상태의 빌드·회귀·정적 검사 | `f8ad11d8` 전체 health exit0: backend 985개 중 984통과·기존 F01 1skip, frontend 442통과, 기본 정적 검사 통과. 전체 구현 완료 후 새 설치본 빌드·최종 검증은 미완료 |

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
