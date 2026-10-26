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
