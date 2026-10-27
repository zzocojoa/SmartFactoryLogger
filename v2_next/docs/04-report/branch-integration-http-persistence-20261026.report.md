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
| 6 | HTTP 저장 무결성 계획의 7단계·17개 추가 시험 및 경계 계약 구현 | 2026-10-27 1단계 착수. fact 큐의 inflight 포함 건수 상한부터 구현. 전체 범위 유지 |
| 7 | 최종 통합 상태의 빌드·회귀·정적 검사 | `e9d9a6f8` 전체 backend1,007시험의 시간 계측 실패를 재현·수정했다. 최신 `22928c20` 전체 backend1,025시험 중1,024통과·1skip, backend Ruff·기본 mypy11파일 통과. frontend442통과의 기존 전체 health는 `f8ad11d8` 시점이다. 전체 구현 완료 후 새 설치본 빌드·최종 검증은 미완료 |

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
