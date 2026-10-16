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
| 최종 전체 health | BytesIO·버전 변경 후 clean `0732c8e8` 출시 환경에서 exit0 | 일치 |
| 패키지 및 현장 15분/120분 효과 | 동일 1.0.30 패키지·격리 설치/복구 통과, 현장 효과 미검증 | 미완료 |

최종 clean 소스 검사 후 5.23 항목은 **10/11 확인(90.9%)**이다. 소스 구현과 개발 검사를 마쳤으며,
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
  최종 clean 후보의 전체 health 결과는 아래 후속 절에 기록한다.
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

동일 clean commit의 미서명 패키지·격리 설치/복구는 후속 기록에서 확인했고, 다음은 현장 효과 검증이다.
기존 현장 15분 FAIL, 120분 미시작, 물리 경계 NOT_TESTED, 전체 데이터 미결 및 출시 HOLD를 유지한다.

## 최종 clean 소스의 출시 환경 검증

`0732c8e810be3c46096b397812f53a9767354229`를 별도 checkout에 고정했다.
출시 lock의 Python wheel 40개 버전·SHA256을 설치 보고서와 대조했고 `pip check` exit0이다.
그 환경의 `npm run health`는 414.454초, exit0이었다. dependency15/Electron100/
frontend 계약9·Vitest437, backend936검사 중 private F01 fixture1건 skip,
Ruff·mypy(9파일)·QA selftest 결과를 확인했다. 해당 fixture 환경변수는 설정되지 않았으며
skip 항목은 완료로 계산하지 않는다. 검사 후에도 checkout은 같은 commit의 clean 상태다.

원문은 `C:/Users/user/Desktop/SmartFactory/PDCA_GC_BUILD_20261016_968f2df9`의
`candidate-health-terminal.json`, stdout/stderr 및 `health-review.json`이다.
stdout SHA256은 `4894397fed7f6f06644425543380e4515489bac5449b4df2c0e094661ec07d35`,
stderr SHA256은 `1f1c6fa7dffd98eb5b7c7a902dc6c42a1b0746a480f3ce3b86c298086dc37f25`다.
성능 비교의 after service와 clean 소스 service의 SHA256도 모두
`2563496ea681c81b8001237bd656b6c89c7e1fe8bd5afeb9e843d1b015689a73`으로 같다.
이 결과는 패키지·설치·현장 QA 통과를 뜻하지 않는다.

패키지와 격리 설치/복구의 별도 실제 실행은
[1.0.30 후보 검증 기록](../04-report/production-release-risk-validation-history-candidate-20261016.report.md)에 있다.
동일 installer SHA의 새 설치/제거·1.0.29→1.0.30 업그레이드·재시작·1.0.29 복구를 마쳤다.
닫힌 데이터 140항목/실패0, CSV·이미지 도구8회 exit0, 정상 종료와 증거 보존 후 Sandbox 정리를
확인했다. 현장 15분/120분이 아직 없어 마지막 항목과 전체 출시 HOLD는 유지한다.

## 5.24 현장 관찰 도우미 후보 연결 대조

도우미 commit `b735967e63f591e6e11e3c08d69c7591300f83b7`을 최종 검사했다.
제품 build `0732c8e8...`와 installer `e72c042d...`는 재빌드하지 않았다.
원문 루트는 `C:/Users/user/Desktop/SmartFactory/F30_20261016_8cafb9d8`다.

| 설계 조건 | 실제 확인 | 상태 |
|---|---|---|
| 정확한 새 후보·기존 기본값 유지 | 3개 후보 identity와 잘못된 조합 거부 | 일치 |
| 후보별 외부 payload SHA | 명시 선택, 실제1,899파일/설치본 잠금 재검산 | 일치 |
| outer/spec·fingerprint·runtime 연결 | 새 collector 정상, 누락·혼합·과거 fingerprint 거부 | 일치 |
| 관찰 시간·native 시계·200ms 기준 | 기존 예산, FILETIME, 느린 첫 health 실패 유지 | 일치 |
| 닫힌 CSV·이미지·종료 metadata | 새 후보 전 경로 및 혼합 이전 후보 거부 | 일치 |
| 6초 WPR 범위 유지 | 1.0.30 거부 회귀, 해당 구현 변경 없음 | 일치 |
| frozen helper의 동일 소스와 결과 정리 | 85개 소스 고정, 실제6회, child3건 잔존0 | 일치 |
| 실제 설치·설정 연결·현장15분/120분 | 다음 단계이며 서버 미실행 | 미완료 |

이 대조표는 **7/8 확인(87.5%)**이며 전체 PDCA 달성률이 아니다.
첫 회귀 실행의 PYTHONPATH 누락으로 CSV 모듈 load ERROR와 exit1이 있었다.
실제152개 PASS와 경로를 보완한 CSV·host25개 PASS(exit0)를 합쳐177개를 확인했다.
초기 실패 원문과 재실행을 `test-reconciliation.json`으로 구분했다. 관련 Ruff와 diff 검사0,
frozen 빌드0, `verify_portable.py`0이다. 운영 ACL 적용은 이 개발 시험에 포함되지 않는다.
상세 해시·재검산 예는 [후보 검증 기록](../04-report/production-release-risk-validation-history-candidate-20261016.report.md)에 있다.
미검증 현장 효과·물리 경계·전체 데이터·운영 승격 및 출시 HOLD를 그대로 유지한다.

## 5.25 원본 보존 설치 계약 대조

설치 도우미 commit `a344e4cbab0ce39e852dc45285ecb28c1c31b84c`의 실제 함수 본문으로
PS5.1 단위 검사와 오프라인 NSIS transaction을 실행했다. 제품0732/e72c 설치본은 같다.

| 설계 조건 | 실제 확인 | 상태 |
|---|---|---|
| 두 교체 쌍·기존 기본값·새 schema/정책 | 정확한 새 요청 수용, 혼합/누락 거부 | 일치 |
| 후보/직전 후보/정식 롤백 설치본 구분 | 세 실제 설치본 잠금 해시·크기, receipt 독립 대조 | 일치 |
| payload·제거 파일·등록값 | 이전1,867/새1,899파일+제거 파일, 실제234,260bytes 확보 | 일치 |
| 원본 전수 재검산·120초·native0·무강제 | 기본/ADS 변경 설치 전 차단, 오래된 기준 재검산 후 실제 설치0 | 일치 |
| 원본/설정·ACL 보존 | 합성4파일/3폴더/3ADS/210bytes, protected ACL 실제 적용 | 일치 |
| 실제 서버 정상 종료·설치·검산 | 현재 CSV357,811,133bytes에 맞는 종료 증거 경로 준비 필요 | 미완료 |

이 표는 **5/6 확인(83.3%)**이며 전체 PDCA 달성률이 아니다. 원문은
`C:/Users/user/Desktop/SmartFactory/I30_20261016_5bd912c7`에 있다.
설치 검사80/보존 entry17 PASS, 닫힌 증거 독립 재검토127 PASS와 실제 native0을 확인했다.
초기 guest 로그인 미완료 dispatch·성공한 stop의 빈 출력 파싱 오류·PS5.1 module path
시험 실행기 오류를 보존했다. 최종 검산은 모두 exit0이며 실패를 PASS로 재작성하지 않았다.
격리 시험의 close review는 합성 자료다. 실제 서버 current CSV가128MiB를 넘어 기존
runtime-close 도우미를 그대로 실행하지 않았다. 새 실제 정상 종료·원본 manifest 결합,
현장15분/120분과 효과 검증은 남아 있다. 상세 증거와 재검산 예는
[후보 검증 기록](../04-report/production-release-risk-validation-history-candidate-20261016.report.md)에 있다.

## 5.26 대용량·자정 rollover 종료 증거 대조

도우미 commit `4c3e292e54a2fcde989c60f915cc56531a29420f`를 검사했다. 서버 현재
파일의 첫 세 순번18,573/18,574/18,575와 동일 logger를32KiB 제한 읽기로 확인했다.
이 확인은 전체 CSV 검증이 아니다. 원문은 `C:/Users/user/Desktop/SmartFactory/C30_20261016_b5d184c2`다.

| 설계 조건 | 확인 | 상태 |
|---|---|---|
| v2 첫 순번 고정·v1 유지 | 잘못된/생략된 시작값과 v1 override 거부 | 일치 |
| 한도·순차 복사·덮어쓰기 방지 | 실제134,217,745bytes 복사와 독립 양쪽 SHA, writer lock/예산 거부 | 일치 |
| 잠금 순차 검토·연속성·최종 순번 | 실제144,291,503bytes CLI와18,573→20,772 합성2,200행, 잘린 시작/중간/중복 거부 | 일치 |
| native 종료·기존 identity 계약 유지 | 기존 종료/native 조건과 identity8개 회귀 | 일치 |
| 실제 서버 종료와 원본 manifest·worker 증거 결합 | 다음 현장 단계 | 미완료 |

이 표의 확인율은4/5(80%)이며 전체 PDCA 달성률이 아니다. PowerShell14/Python17/
인접 identity8개, 총39개 PASS와 각 exit0을 확인했다. Ruff와 diff 검사도0이다.
로컬 도우미 검증만으로 서버 정상 종료·설치·현장 QA를 PASS로 바꾸지 않는다.

### 5.26 현장 진행 보완

2026-10-16 17:51 KST 실제 정상 종료 뒤 native5개 종료0와 현재 CSV278,630행의
18,573→297,202 연속성을 확인했다. 별도 종료 로그 검토에서10개 작업 종료, 이미지57,746건
저장·queue/inflight/unfinished/failure/drop0을 확인했다. 전체 원본 `O4ff65a11`의 캡처와
재검산은18:41 KST 실제 종료0으로 완료됐다.290,682파일/245폴더/680ADS/14,887,746,451bytes의
결과·manifest·제어 결과를 콘솔 해시와 대조하여 회수했고,9개 종료 자료를 동일 원본 목록에
결합했다. `P30_20261016_e934c7a2/field-close-review.json`의
`NORMAL_SHUTDOWN_AND_ORIGINAL_MANIFEST_BINDING_CONFIRMED`와 exit0이 근거다.
이에 따라5.26의 실제 서버 종료·manifest 결합 행도 확인되어5/5이며, 전체 PDCA 달성률은 아니다.
18:47 시작한 서버 설치 절차는18:48 현재 설치 전 원본 대조 중이다. 실제 설치 종료·설치 후
보존·새 실행·현장 QA는 아직 미완료이며 출시 HOLD를 유지한다.

## 5.27 1.0.30 실행 확인 연결

정확한 후보0732c8e…를 승인 프로파일 도우미에 추가한 회귀10개가PASS·exit0이다.
새 종료 v3 요청의1.0.30 build/version 결합과 기존 v1/v2 격리를 확인했다.
PowerShell15/Python18/인접 identity8개, 총41개PASS·exit0이며 Ruff/diff도0이다.
검사는 `P30_20261016_e934c7a2/checks-r1` 및 `adjacent-r1`에 있다.
실제 새 실행 metadata를 이용한 네 확인 항목 적용과1.0.30 종료/현장 QA는 아직 미완료다.
