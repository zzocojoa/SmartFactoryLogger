# 출시 위험 검증 — GC 이력 보완의 설계 대조

작성일: 2026-10-16. **설계 5.23 개발 검증 기록, 전체 PDCA·출시 HOLD**.

이 문서의 범위는 [설계 5.23](../02-design/features/production-release-risk-validation.design.md)의
화면 이력 보관과 HTTP 응답 준비다. R1–R6 전체 달성률을 계산한 문서가 아니다.
계획은 별도 이름의 [기존 출시 계획](../01-plan/features/production-release-risk-validation-codex-production-release-risk-validation-20261010.plan.md)을 따른다.

## 원인 근거와 구현

[같은 요청 CPU 스택 검산](../04-report/production-release-risk-validation-cpu-outlier-20261016.report.md)에서
PLC thread 표본 170개 중 168개에 자동 GC 호출 경로를 확인했다. 특정 서버 객체가 그 GC의
원인이라는 증명은 아니다. 격리된 실제 service의 보관 표현을 바꿔 비용을 비교했다.

`PLCService.history`는 공개 모델 JSON과 timestamp/sequence/monotonic 값을 불변 record로
보관한다. 장기 Pydantic 객체 그래프를 줄이면서 기존 1시간·36,000개 한도를 유지한다.
Python 조회는 선택한 값만 새 모델로 복원한다. HTTP는 내부 serializer의 JSON을
`BytesIO`에 순차 기록하고 worker thread에서 응답 bytes를 준비한다.
CSV·원본 모델의 freshness anchor·GC 설정·장비 설정은 변경하지 않았다.
새 후보 버전은 1.0.30이며 아직 서버에 적용한 버전을 뜻하지 않는다.

## 설계 대조표

| 설계 항목 | 구현/검증 | 상태 |
|---|---|---|
| 공개 JSON 불변 보관 | `_StoredHistorySample`, 기록 당시 serializer 출력 | 일치 |
| 원래 입력·published·CSV/private 값 보존 | 중첩 입력 변경 격리, private anchor·CSV 경로 회귀 | 일치 |
| 1시간 monotonic/36,000개 FIFO | 기존 retention/경계 회귀 유지 | 일치 |
| UTC 역전·같은 시각·cursor/gap/reset/legacy | 기존 history/API 회귀 | 일치 |
| 조회 객체 격리·clear 시 같은 generation | 복원 지연 중 동시 record/clear 시험 | 일치 |
| 기존 HTTP JSON bytes·Content-Type | 한글·escape·중첩값·empty/limit/cursor 실제 HTTP 대조 | 일치 |
| worker에서 응답 준비 | 같은 event loop의 health 요청 진행과 worker TID 검사 | 일치 |
| GC 설정 및 bounded memory collector 보존 | 코드 대조와 memory 회귀 | 일치 |
| 실제 구현의 GC·기록·조회·peak 메모리 비교 | 아래 R3 별도 프로세스 결과 | 일치 |
| 최종 전체 health | R2 exit0; BytesIO·버전 변경 후 clean 후보에서 다시 실행 예정 | 미완료 |
| 패키지 및 현장 15분/120분 효과 | 아직 새 installer/현장 결과 없음 | 미완료 |

이 시점의 5.23 항목은 **9/11 확인(81.8%)**이다. 소스 구현과 일부 개발 검사만 끝났으며,
미완료 항목을 이전 설치본의 결과나 합성 수치로 대신하지 않는다.

## 개발 비교 방법과 결과

원문 루트: `C:/Users/user/Desktop/SmartFactory/PDCA_HISTORY_GC_20261016_46827a81`.
baseline은 `0bff52aa`의 service, after는 최종 `BytesIO` service 사본이다.
MOCK·별도 AppData·실행별 새 프로세스에서 실제 `_record_history_sample`과 조회 함수를 사용했다.
장비 연결이나 app/background thread 시작은 하지 않았다. 기본 GC를 유지했고 강제 full GC는
개발 시험 프로세스에서만 7회 측정했다. 3개 별도 프로세스 반복의 중앙값을 아래에 기록한다.
HTTP 비용은 조회·직렬화·UTF-8 준비 시간이며 네트워크나 서버 health 지연 시간이 아니다.

| 항목 | 수정 전 | 최종 R3 |
|---|---:|---:|
| 15,800개 full GC 중앙값 | 33.53ms | 8.48ms |
| 36,000개 full GC 중앙값 | 66.02ms | 14.08ms |
| 36,000개 보관 시 기록 1건 평균의 중앙값 | 0.0700ms | 0.0135ms |
| 같은 조건 500개 응답 준비 | 12.83ms | 6.70ms |
| 같은 조건 1,000개 응답 준비 | 17.83ms | 11.62ms |
| 같은 조건 36,000개 응답 준비 | 427.44ms | 310.18ms |
| 별도 최대 조회 시험의 process peak working set | 496.34MiB | 421.39MiB |
| 같은 시험 process peak pagefile/commit | 494.16MiB | 428.05MiB |

최대 응답은 126,662,042bytes다. 모든 비교에서 입력별 응답 길이와 SHA256이 같았다.
peak는 프로세스 수명 전체의 Windows high-water mark이며 이력 전용 heap 값이 아니다.
15,800개 최대 페이지 준비는 186.87→180.57ms로 차이가 작았다. 모든 부하의 지연이 줄었다고
일반화하지 않는다. 최대 조회는 여전히 큰 응답이며 서버의 200ms health 기준과 별개다.

중간 실패도 보존했다. 첫 모델 복원 구현은 1,000개 준비 비용이 66–81ms로 늘었다.
R2 문자열 결합은 조회를 줄였으나 최대 조회 peak working set이 약 496→546MiB로 늘었다.
최종 R3는 중간 전체 문자열 사본을 줄였다. 이전 결과 파일을 덮어쓰지 않았다.

## 검사와 증거 식별

- 최종 BytesIO 변경 후 관련 5개 unittest 모듈: **89검사, exit0** (`focused-r3.log`).
- R2의 `npm run health`: **exit0**, dependency15/Electron100/frontend 계약9·Vitest437,
  backend936검사 중 private F01 fixture1건 skip. Ruff·mypy(9파일)·QA selftest 완료.
  이는 BytesIO·1.0.30 변경 전 결과라 최종 전체 통과로 사용하지 않는다.
- 새 버전 package/lock/backend와 installer identity 회귀의 고정 기대값을 함께 갱신했다.
  최종 clean 후보에서 전체 health를 다시 확인하고 패키지 검증 기록에 연결한다.
- `git diff --check` exit0. 외부 설치·서버 restart·백업·운영 승격은 이 개발 단계에서 수행하지 않았다.

| 원문 | SHA256 |
|---|---|
| `r3/benchmark-results.json` | `2392a8a923f12b375d4d9d50f0e2237df5700fe2712c6e8a843fe065f0351b94` |
| `peak-memory-r3/benchmark-results.json` | `aac0c076a2e55bcdfdddb4fbfeee255bf2643a4b0345c5716bb538ad9c055969` |
| `focused-r3.log` | `464a32c56542ce65f29a59a56a0526460f07b5efd3b6bd117f2c1607451c49ac` |

확인 예: 위 루트의 결과 JSON에서 before/after 각각의 `service_source.sha256`을 확인하고,
`queries[].runs[].sha256`을 같은 count/limit별로 비교한다. 최대 메모리는 별도 결과의
`memory_before_query`와 `memory_after_query`를 함께 확인한다. 성능 반복 출력에 남은
`query_1000_ms` 이름은 peak 시험에서 실제 limit36000을 뜻하므로 결과 JSON의 limit를 따른다.

다음은 최종 clean commit의 미서명 패키지·설치/복구·현장 효과 검증이다.
기존 현장 15분 FAIL, 120분 미시작, 물리 경계 NOT_TESTED, 전체 데이터 미결 및 출시 HOLD를 유지한다.
