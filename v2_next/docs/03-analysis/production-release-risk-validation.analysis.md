# 출시 위험 검증 — GC 이력 보완의 설계 대조

## 2026-10-26 최종 상태 — 승인 범위의 운영 승격 완료

사용자의 “세 항목 처리안 승인”을 정확한 C32와 실행 기록에 연결하고 최종 통합 QA를 마쳤다.
판정은 `PROMOTED_WITH_DOCUMENTED_LIMITATIONS`다. 원래 기술 FAIL·INCOMPLETE는 유지한다.
실제 서버 설치 payload 1,867개·설치본·설정·일반 사용자 프로세스·수집 증가를 다시 확인했고,
`v1.0.32` 태그가 build `cd46692ac9c551080c57d8168fa9ea5abd530206`을 가리킴을 로컬/원격에서 검산했다.
현재 운영본과 다음 변경의 롤백 기준을 동일 C32/installer SHA256으로 갱신했다.

[최종 보고서](../04-report/production-release-risk-validation.report.md)가 현재 판정이다.
아래 이전 날짜·단계의 HOLD, 승인 대기, 미완료 문구는 당시 이력이며 현재 상태를 덮어쓰지 않는다.
알람 OFF·물리 NOT_TESTED, 과거 자료 학습 사용 보류, 초기15분 health6건과 PC_2 약28초 가림의
한 실행 예외, 원인 미확정의 제한을 유지한다. 새 설치·앱 재시작·전체 백업·15/120분 반복은 없다.


## 2026-10-26 기존 C32 내부 시간 계측의 제한적 현장 확인

[검토 기록](C:/Users/user/Desktop/SmartFactory/HST32_20261026_5f23a91c/review.md)에
기존 선택적 health timing을 사용한 15건을 보존했다. 제품 변경·설치·재시작 없이
현재 실행과 설정·설치 파일 1,868개를 결합했고, 모든 요청의 본문/헤더·네이티브 시계를
오프라인에서 재검산했다. 오류·타임아웃 0건, 총 응답 시간 7.5475~21.6566ms다.
기존 모듈 18개·실행 루프 3개·잘못된 입력 5개 검사와 실제 실행/회수는 exit 0이다.

다른 세대의 짧은 진단이며 요청 전 파일 검산으로 캐시가 준비됐을 수 있다. 과거 지연은
재현되지 않았고 원인 해결·성능 PASS를 뜻하지 않는다. 초기 15분 p99 228.7438ms FAIL과
출시 HOLD를 유지한다. 표시 예외는 이미 수용됐으며 화면 15분/120분 반복은 하지 않았다.
결과 회수기의 개수 제한에 빈 stdin 파일이 누락됐던 오류는 기존 결과 회수만으로 해결했다.
서버 앱은 계속 Running·전면 표시 상태다. 작업 정보는 14:11:51 이후 미입력이며 임의로
과거 제품번호를 다시 넣지 않았다. 별도 health 제약 수용 또는 다음 정상 재시작에서의
추가 원인 진단을 검토안에 구분했고, 아직 새 예외 승인이나 운영 승격으로 기록하지 않았다.

## 2026-10-26 초기 15분 지연의 자원·서버 로그 대조

[분석 기록](C:/Users/user/Desktop/SmartFactory/PRES3PC2_20261026_61a92cbe/initial15-latency-review.md):
기존1,417파일을 검산하고 health6건을5초 자원181회·프로세스181회와 연결했다. 앱 실행144.4초
뒤부터 측정했으므로 초과 구간을 시작 준비 시간으로 제외하지 않는다. 해당 온도 영속화
rejected/write_failure/spool_failure는0이며, 압출기 timeout 카운터는 이전1건에서 증가하지 않았다.
자원 평균만으로 짧은 스케줄링·락·파일 지연이나 다른 프로세스 부하를 배제하지 않는다.

승인 SSH로 당시 회전 로그10,485,571바이트를 읽고 정확한3분/trace 조건의 원문42줄을 보존했다.
후보 코드는 성공한 health의 접근 로그를 생략하므로 여섯 trace의 내부 시간은 복원되지 않는다.
원인미확정·초기health p99 228.7438ms FAIL·출시HOLD를 유지한다. 별도PowerShell 해시/quantile
검산exit0이며 새 측정·제품수정·설치·재시작은 하지 않았다. 서버Running·60588/1 전면 화면을 확인했다.
표시예외 수용은 완료 상태다. 다음은 기존 선택적 health timing의 제한적 진단 준비이며,
짧은 정상 재측정으로 과거FAIL을 지우거나 화면15분/120분을 자동 반복하지 않는다.

## 2026-10-26 승인된 표시 예외와 완료 감사 누락 보완

설계5.141의 한 실행 예외를 구현했다. 원래 엄격 판정은 INCOMPLETE로 재현되고,
해시·승인·단일 구간·사용자 가림 확인이 일치할 때만 별도 예외 수용 결과를 낸다.
34개 회귀와 최종 영향12개, 실제3대 자료 결합은 exit0이다. 모든 조건이 구현됐다는
백분율로 전체 PDCA 완료를 대신하지 않는다.

보존69개 릴리즈 기록과 후보 설치본 전체 해시를 확인했으나, 기존 성능 재평가가120분만
포함하고 초기15분을 새 수치 기준으로 판정하지 않은 누락을 발견했다. 전후 요청 포함
health452건 p99 228.7438ms로 승인200ms를 넘는다. 초과6건은 관찰 첫120초에 집중되며
오류/timeout은0이지만 지연 원인은 미확정이다. 원시1,208파일 검산·재평가는 exit0,
제품의 해당 성능 판정은 FAIL이다. 후속120분의 PASS와 이번 화면 예외는 이를 면제하지 않는다.

따라서 표시 재측정은 끝냈고, 다음 작업은 기존 지연 요청과 같은 시간축의 프로세스·자원
기록 대조 및 원인/영향 판단이다. 새 측정·제품 변경·서버 재시작·운영 승격·롤백 기준 갱신은
실행하지 않았다. 근거는 `PRES3PC2_20261026_61a92cbe/completion-audit.json`,
`initial15-http-audit.json`, `accepted-exception-assessment-r2.json`이다.

## 2026-10-24 PC별 원시 표시 기록 판정기 준비

[판정기와 입력 계약](../04-report/production-release-risk-validation-presentation-assessment-20261024.report.md):
서버1대·조회 PC3대의 결과/세대/물리 PC 확인을 결합하고 원시 응답·표시에서 새 승인 수치를
판정한다. 23검사exit0, 실제 보존 격리 결과3개는 현장 증거로 거부했다. 제품/설치본/서버는
변경하지 않았다. 조회 PC 조작 가능 여부 응답이 없어 현장 계측은 미실행이며, 기존4PC 육안
확인/120분은 완료로 유지한다. 최종 통합 QA·운영 승격·롤백 기준 갱신은 미완료다.

## 2026-10-24 추가 계측 파일 서버 전달 완료

[전달 기록](C:/Users/user/Desktop/SmartFactory/PRESEND32_20261024_c017ce4a/README.md):
준비 파일9개·160,163바이트를 공유와 서버 새 폴더에 전달하고 이름/길이/SHA256을 대조했다.
기존 서버 Playwright106파일과 Node를 재검산해 재사용 가능함을 확인했다. 실제 전달exit0이다.
서버 C32 Running·작업60073/7·최종 전면 화면을 확인했으며 계측/앱 종료/설치는 실행하지 않았다.
새 폴더의 탐색기 화면 확인과 조회 PC3대 전달/조작, 서버 진단 실행 결합은 미완료다.
기존4PC 육안 시험/120분은 유지하며 수치 계측을 위한 조작 가능 여부 응답을 기다린다.
목표active·전체 출시HOLD·운영 승격 미완료.

## 2026-10-24 조회 PC의 추가 관리 접속 없이 계측하는 방법

[브라우저 계측 준비](../04-report/production-release-risk-validation-browser-capture-preparation-20261024.report.md):
기존 대시보드 안에서만 관찰하고 로컬 JSON을 저장하는 도구를 준비했다. 격리3조건·실제 C32
화면19표시 대응·즐겨찾기 실행/다운로드 검사는 exit0이다. 다운로드 흐름 시험의 가상 시계를
현장15분 성능으로 해석하지 않는다. 조회 PC의 조작 가능 여부와 서버 계측 결합은 아직 미확인이다.

## 2026-10-24 기존 현장 QA 조건의 원시 기록 대조

[C32 보존 기록 대조](../04-report/production-release-risk-validation-retained-qa-20261024.report.md)에서
health3,602개·같은 세대의 종료·metadata·기존 CSV 소비자를 연결했다. QA 검사 이름42개 중
41조건 충족·1개 승인 범위 제외이며13가지 부정 입력 거부, 실제 감사 실행exit0이다.
새 one-command QA 실행이나 전체 출시 PASS로 표시하지 않는다. 완료한4PC 육안 확인·120분은
유지하고 추가 표시 시간 증거와 최종 통합 판정·운영 승격은 아직 미완료다.

## 2026-10-23 실제 C32 화면 코드의 추가 계측 준비

[계측 호환성 검증](../04-report/production-release-risk-validation-presentation-readiness-20261023.report.md):
기존 설치본의 화면51파일을 해시 대조하고 격리 실행해19표시/19로드를 연결했다. native 카메라
버튼의 가림 오판을 수정했으며 회귀5개와 기존 page를 보존하는 CLI 검사는 exit0이다.
기존 PC4대 육안 확인은 완료 범위로 유지하고, 새 수치 현장 계측과 최종 QA는 아직 미완료다.

## 2026-10-23 사용자 승인 범위 구현·재평가

[최신 승인 반영 보고서](../04-report/production-release-risk-validation-approved-scope-20261023.report.md)가 아래 과거 알람/전체 과거 복구 선행 조건보다 우선한다. Low Signal OFF 범위 제외, 과거 사용 보류 분리, 수치 기준 및 C26 종료 제약 수용을 반영했다. 최신 수신/HTTP·시작 증거는 새 기준을 충족하며 초기 두 실행 FAIL은 보존한다. **PC4대 동시 조회·육안 연속 갱신 확인은 이미 완료**했으며, 남은 것은 각 PC의 표시 간격 수치 계측과 최종 통합 QA·운영 승격이다. [완료 범위 정정과 원 증거](../04-report/production-release-risk-validation-four-pc-evidence-20261023.report.md)를 따른다. 정책 반영으로 전체 출시를 PASS로 바꾸지 않았다.


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

### 5.25 현장 설치 진행 보완

2026-10-16 19:09:25~19:09:59 KST에 실제 후보 설치 프로그램 PID8276의 native 종료0,
강제 종료 없음이 `J22c6ed1c/installer-exit.json`에서 관찰됐다. 설치 전 원본290,682파일
대조는 끝났고, 설치 파일·등록 영수증이 생성된 뒤 같은 controller17000이 설치 후 원본
대조를 진행 중이다.19:14:43 관찰은50,442파일이며 최종 result/terminal은 아직 없다.
따라서5.25의 실제 서버 행은 계속 미완료다. 콘솔에 결합한 최종 영수증 검토·원본 보존,
새 실행·프로파일 연결·현장 QA가 끝나기 전 확인율이나 출시 HOLD를 변경하지 않는다.

### 5.25 / 5.27 현장 완료 범위 보완 — 20:09 KST

설치 절차가19:31:54 실제 종료0으로 끝났고, 콘솔 결과 SHA256
`93a6fb2829537489d9093d12fd26a3949f6bbc8e352c1f8f16469228abad675e`와 회수 파일이 같다.
독립 검토22개 영수증으로 설치본1,900파일/등록1.0.30, 원본290,682파일/245폴더/680ADS/
14,887,746,451bytes와 config 보존을 확인했다.5.25 실제 서버 행은 이제 확인되어6/6이다.
이는 설치 계약 대조 완료이며 전체 PDCA·현장 성능·운영 승격 완료가 아니다.

첫1.0.30 실행은19:42에5개 native process 종료0, 현재CSV2439행의 순번1→2439를 확인했다.
별도9개 cold 자료와 begin/final/Electron/native를 대조한 검토도0이다. 이미지 저장 중1건이
완료되며 written243→244, inflight1→0, unfinished1→0으로 바뀌고 실패/drop0·10개 작업 종료를
확인했다. `first1030-runtime-analysis.json` SHA256은
`f50f64c683eb4dc69510b7122b116c592905f8492900f655bebf03ff96d638c3`다.
개별 이미지와 fact 바이트 QA는 이 제한 검토에 포함하지 않았다.

화면 준비8868.6ms와 별개로 시작 CSV sample→ingest 최대65944.981ms, stale231행이 관찰됐다.
원인 미확정이며 시작 횟수·화면 수 전체 조건은 미완료다. 코드 읽기에서 CSV sidecar 작성이
이미지 writer의 초기 manifest 읽기를 동기 호출하는 경로를 찾았으나, 실제 서버 지연의
원인이라고 확정할 실행 스택이나 구간 계측은 아직 없다.

19:48에는 같은 후보의 기존 승인 설정 확인4항목만 갱신하고 실행·검토0을 확인했다.
19:50 재시작한 main16128/backend8980/logger `ee648ff0-d3a9-4ab9-bb7e-015ff4457cb4`의
실제 config SHA와 첫CSV1/2/3을 확인했다. 소프트웨어 승인 필드 대조PASS, 물리NOT_TESTED다.
5.27의 새 실행·승인 설정 연결·첫 종료 확인은 완료됐지만 현장 QA는 계속 미완료다.

RUN1308파일/새900초 요청5파일을 서버 로컬에 전달해 잠금 해시로 검산한 뒤 한 번 실행했다.
20:09의 `run-51af6bced804` 초기 설치본·실행 세대·설정 대조는PASS이고 측정은 진행 중이다.
완료 시 콘솔 해시→launcher→session manifest→원시 HTTP/resource 표본 순서로 대조한다.
최종15분·선행 조건 통과 후120분·시작 지연·전체 데이터 미결·물리/제조사 확인·운영 승격은
남아 있으며 출시 HOLD와 기존 실패 기록은 유지한다. 상세 경로와 재검산 예는
[후보 검증 기록](../04-report/production-release-risk-validation-history-candidate-20261016.report.md)을 따른다.

### 5.27 15분 관찰 결과와120분 진행 — 20:32 KST

1.0.30 현장15분 관찰은 실제 종료0이며 launcher SHA256
`4602c1708a9f0a535c49c1b153813cd41d86da4ef2b5bb4c0a1a0c63271f2fb1`과 회수8,795파일을
결합했다. 같은 도우미 소스85개와 원시 HTTP/resource/combined 재계산의 독립 검토도0이다.
`observe1030-replay-review.json` SHA256은
`66b87ea6f0d65e3d52754d82465abec85cbc886f19bd95e0ae51968f7b4623ce`다.
경계 포함health452건 최대141.8191ms로200ms 이내, timeout·오류·누락0이다.
주기 표본의50ms 경고55건, data100ms 경고1건은 보존한다. 자원181표본과300초 창3개가
충분하며 미측정 구간0이다. 전체 자원 성능·UI·시작 시험·전수 데이터의 PASS는 아니다.

이 결과를 선행 조건으로 같은 실행 세대의120분 관찰을 시작했다. 서버
`run-382f1d686bd7`에서7200초 및 초기 설치본·세대·설정 대조PASS를 확인했다.
20:32 현재 최종 결과는 대기 중이다. 현재 실행의 초기 stale244건은15분 구간 중 늘지
않았지만 시작 지연의 원인은 미확정이다. R2 전체와 R4·물리 조건·운영 승격·출시 HOLD를 유지한다.

### 5.27 시작 지연 경로의 제한 재현 — 20:43 KST

같은 후보 소스4개를 commit과 대조하고 로컬 APPDATA/설정/로그를 격리한 재현에서,
이미지 writer를 다른 스레드가 초기화하는 경우와 CSV가 처음 생성하는 경우 모두 CSV
open→sidecar→image manifest→health→writer 초기화 경로의 대기를 실제 스택으로 확인했다.
event 해제 전 header만 있고 sidecar는 없으며, 해제 뒤 두 경우 모두 작성 완료·exit0이다.
네트워크/하위 프로세스/격리 폴더 밖 쓰기는 금지했고 최종 실행의 외부 접근 시도0이다.
관찰 fact 생성은 stub이고 이미지 초기화 지연은 합성 조건이므로 서버의66초 원인 확정이 아니다.
결과 SHA256 `11617c8135d27725a0609691e9e976f19c67b4d3e10aae1fbbdca3f418c92990`와
정확한 경로·제약은 후보 보고서의20:43 절에 기록했다. 다음 시작의 구간 계측이 남아 있으며,
진행 중인120분 측정을 위해 서버 코드·설치본·설정·프로세스는 변경하지 않았다.

### 5.27 보존 자료의 실규모 분석 보완 — 20:55 KST

설치 전18:41:57의 원본 목록과10월14일 이미지 디코딩 증거를 개발 PC에서 대조했다.
현재289,746개 이미지 중153,014개는 기존 경로·크기·SHA256과 같고,136,732개/
1,271,257,234bytes는 새 실물 검사가 필요하다. 이전 목록에서 보이지 않는171,179개는
부재 원인 UNCONFIRMED로 별도 기록했다. 분류 검사6개와 실제 실행·독립 집합 대조는
각 exit0이다. 새 이미지 회수/디코딩0건, 후보1.0.30 생성 자료는 이 경계 밖이다.
따라서 R4 전체 데이터 판정은 완료가 아니며 최종 종료 경계의 확장이 필요하다.

별도 격리 실험에서 보존된2.17GB/4,237,531행 이미지 fact에 실제 후보 생성자를 적용했다.
전체17.5213초 중 행 수 계산15.5844초였고, 입력 전후 해시·identity·manifest 일치와
외부 접근0을 확인했다(exit0). 사전 검산으로 캐시가 데워진 개발 PC의 단일 실행이며,
서버 시작66초의 원인 확정이나 현장 성능 통과가 아니다. 결과 SHA256은
`156084bd57be92fac81795d2a3b62c3b316ef5dcdbceccf0b9f74ed35bc75f3f`다.
상세 입력·출력 해시와 다음 검증 예는 후보 보고서20:53/20:55 절에 기록했다.
120분 관찰은 계속 진행하며 전체 데이터·시작 구간 계측·물리 시험·출시 HOLD는 유지한다.

### 5.28 canary 완료와 정상 종료 연결 도우미 — 21:12 KST

설계5.28을 적용한 로컬 준비기 `P30/prepare_canary_final_close.py`는 기존 v3 observer와
native 제어기 바이트를 유지하고, 실제120분 terminal·콘솔·manifest·독립 재계산·최종 health를
연결한다. 실행 중 자료로 준비가 거부되는 것과 부수 파일 생성이 없는 것을 확인했다.
최종 health에서 종료 기대값을 재계산하고, 다른 세대·순번·해시·900초 창·불완전 재계산을
거부하는15개 검사와 합성 묶음 생성·중복 목적지 거부가 exit0이다. 원시15분 경계 자료를
사용한 시험 사례는120분 현장 성능 증거로 계산하지 않는다.

같은 frozen 도우미85소스와 실제 승인된 runtime 기준 preflight0, native PowerShell5.1x64의
v3 요청 library 검사0 및 생성된 PowerShell3파일 정적 구문 검사0을 확인했다. 실제 서버용
종료 묶음 생성·전달·실행과 canary 최종 결과는 대기 중이다. 상세 해시와 실행 순서는
후보 보고서21:12 절에 있으며, 제품·서버 설정·프로세스는 변경하지 않았다.

### 5.29 종료 후 데이터 검사의 실제 용량·시간 조건

설치 전 원본 목록의 직접 하위 CSV·metadata·최종 manifest36파일을 해시가 고정된 목록에서
추렸다. v2 CSV12개와 metadata12개, 현재 fact/최종 manifest3개, 과거 schema-mismatch
fact9개다. 현재 이미지 fact2,241,600,730bytes와 관찰 fact545,221,046bytes는 기존 역할별
한도4GiB/2GiB 안에 있다. 과거 별도 관찰 fact4,878,532,000bytes는 현재 관찰 fact와
구분하며, 현재 소비자의2GiB 한도로 과거 전체 검사를 완료할 수 있다고 주장하지 않는다.

기존 실제 CSV 소비자의2810.281초·exit0와 출력3파일 해시·잔존 프로세스0을 다시 확인했다.
후속 현재 CSV 검사는 기존 함수가 허용하는3600초 예산을 사용한다. HTTP 성능 한도나
제품 코드는 바꾸지 않는다. frozen85소스와 고정 CSV EXE를 확인한 준비 검토는 exit0이며,
`P30/dataqa-readiness.json` SHA256은 `e61ba9e50f36417e9c317cd6a49a3b1afe6f5fddb3363798e4411a3a8c7622f1`이다.
이 목록은 설치 전 경계다. canary 종료·같은 세대 정상 종료 뒤 최종 CSV/metadata/fact를
확보하고 전체 범위를 확장해야 하며, 후보 데이터 QA·R4·출시 판정은 미완료다.

### 5.30 선택 입력 확보 도우미의 로컬 검증 — 21:51 KST

설계5.30의 `capture-closed-facts.ps1`를 추가했다. native PS5.1x64의10개 검사(exit0)에서
실제3,145,745bytes 스트리밍 복사·원본 쓰기 차단·덮어쓰기/용량/추가 스트림 거부, 다른 세대·
미완료/감소 순번·잘못된 선택 경로를 확인했다. 합성6파일 복사 후 모든 목적지 SHA를 재확인했고,
config/CSV/metadata/관찰/이미지 각각의 잘못된 외부 SHA가 거부됐다. 개발 PC에서 실제 진입점을
실행하면 서버 식별에서 exit1로 거부되며 원본 경로를 읽기 전에 끝나는 것도 확인했다.

로컬 준비기 `P30/prepare_closed_fact_capture.py`의7개 검사도 exit0다. 실제 canary terminal이
없는 상태에서 묶음을 생성하지 않으며, 정상 종료의 native 프로세스 세대·제어기 정리·최종 순번·
콘솔 SHA를 연결한다. 합성 묶음8파일의 해시와 PowerShell4파일 구문을 확인했다. 기존 native
Job 구현은 동일 바이트로 재사용하고 실제 서버용 묶음 생성/전달/실행은 아직 하지 않았다.

검토 영수증 `P30/closed-fact-preparation-review.json` SHA256은
`8b899b8f3909e329cab43cf6111c11e2558d544abae5eaddfee06a7d3e40207d`다.
초기 로컬 시험의 경로 변수 충돌·OrderedDictionary 그룹화·ADS fixture 생성 실패 기록도
보존했다. 수정한 최종 소스의10+7검사와 각 실제 종료 코드/전체 로그를 확인했으며,
서버 대용량 복사·실제 후보 데이터 QA·120분 최종 성능·정식 출시를 통과한 것으로 표시하지 않는다.

### 5.31 CSV 소비자 연결과 기존 사본 재사용 — 22:10 KST

실제 canary/정상 종료/선택 사본 콘솔과 native 제어기 정리 기록을 연결하는 로컬 실행기
`P30/run_canary_csv_qa.py`를 준비했다. 기존 `CsvInputs`·`shutdown_csv_inputs`·owned Job
소비자를 재사용하고3600초 예산을 적용한다. 누적 대장 전체를 유지하며 최종 순번/설정을
검사한 동일 입력의 실제 소비자 종료를 기록한다. 준비8검사·preflight·Ruff F/E9 모두 exit0이며
현재 실행 중 canary에서 실제 소비자 실행을 거부하는 것도 확인했다. 실제 후보 내용 QA는 미실행이다.

검토 영수증 SHA256은 `7f777d1e4820fdc2024f1cb3af88e1092a5735147e543c34f848c36573c6fb92`다.
기존 Q3d9da3 백업과 설치 전 직접 입력36개를 비교해21개/8,087,863,671bytes의 동일 내용,
신규12개/916,176,290bytes, 변경3개/2,786,822,235bytes를 구분했다. 원본 전체 manifest를
전후 검산했으며 `P30/historical-input-reuse.json` SHA256은
`589a2fcadcff5863f2b51ac9a60b26809cdd5d3fb92155d25a7dd6aa51503fbb`다.
동일 자료는 기존 백업에서 필요한 입력만 재검산·회수하면 된다. 이 목록 비교는 서버의 현재
바이트 재검산·실제 내용 QA·전체 R4 완료를 대신하지 않는다. 새 백업이나 서버 복사는 하지 않았다.

### 5.32 실제120분 실패와 실패 후 정상 종료 인계 — 23:23 KST

실제 canary는 health200ms 초과2건(최대302.9669ms), image HTTP 예정 시점 누락12건,
도우미 finalization180초 제한으로 FAIL이다. 전체 session manifest70,097파일 검산과
원시 표본 독립 재계산도 FAIL을 확인했다. 같은 요청 서버 내부 단계/ETW가 없어 지연 원인은
미확정이며, HTTP 예정 시점 누락을 실제 촬영 이미지 유실로 해석하지 않는다.
`worker-result.json`과 원래 shutdown expectation 등 미생성 증거도 계속 누락으로 기록한다.

인계 보완은 관찰 성공 조건을 완화하지 않는다. 실제 terminal/콘솔/launcher와 마지막 health·
설정·제어 세대 및 독립 replay를 결합해 정상 종료에 필요한 최소 순번40838만 도출한다.
새 인계13검사, 선택 사본·CSV 소비자 v2 연결15검사, Ruff F/E9 및 생성 PS 구문 검사는 exit0다.
원래 도우미 바이트는 유지했다. 코드·설정·성능 임계치·시험 제한 시간 변경은 없다.

실제 서버 정상 종료 결과 `R406500891d2f`의 콘솔 SHA
`fe9eb05ba148de81c1c211e4dea4d6a5ce83f17d128a5a28f981a5a019646af8`와 제어기 정리를
검산했다. main/backend 및 자식5개 종료 코드0, 원래 config 해시, CSV1–53338을 확인했다.
이 결과는 제한된 종료·순번 대조이며 누적 대장 소비자/이미지 실물/전체R4 QA는 아직 미완료다.
관련 원문·재계산 SHA와 다음 절차는 [현장 후보 보고서](../04-report/production-release-risk-validation-history-candidate-20261016.report.md)의
`23:23 120분 실패 재계산과 정상 종료` 절에 기록한다. 정식 출시 HOLD를 유지한다.

### 5.33 종료 시점 선택 사본과 재시작 구간 — 23:43 KST

동일 종료 경계의 CSV·metadata·설정과 누적 관측/이미지 대장을 잘라내지 않고 선택 복사했다.
실제 capture exit0·Job 잔여0과 결과 SHA `5bcf946c11cea5a69428bf9e67db44938972630ab3f6e4c3aefb0fdad6ce53ed`를
확인한 뒤 설치된 앱을 재시작했다. 선택 사본 확보와 전체 데이터/이미지 실물 QA는 구분한다.
새 전체 백업·재설치·설정 변경은 없다. 내부 종료10단계 및 image10,800건 완료와 native5개
종료0을 연결했고, 종료 시작 시 대기열은 이미0이므로 비어 있지 않은 큐 drain 시험은 아니다.

새 실행 main17996/backend14012·logger9a4d5320의 첫 CSV 논리 레코드1–3과 config 보존,
화면 Running/60192·18을 확인했다. 화면 준비9,967.5ms와 CSV open 약80초는 서로 다른
관측값이다. 초기 startup_pending12/stale249와 관측 대장 초기화47,422ms를 남겼다.
전송 부하가 함께 있었고 같은 요청의 서버 내부 추적은 없으므로 원인 확정/성능 PASS로
확대하지 않는다. 접두부 끝의 잘린 다중행 CSV를 전부 파싱하던 검사 오류는 원문을 보존하고
필요한 첫3개 완전한 레코드를 읽는 오프라인 reviewer로 확인했다. 재현·거부 검사 및 Ruff는 exit0이다.
실제 내용 소비자와 전체R4,120분 실패 원인,물리 시험·운영 승격은 계속 미완료다.

### 5.34 누적 이미지 기록 전체 대조 — 2026-10-17 00:11 KST

정상 종료 이미지 fact4,385,307행 전체의 식별·경로·크기·해시와 중복 ID/경로를 검사했다.
설치 전 보존 이미지289,746개와 fact의 동일 경로·내용 조인이 전부 일치했고, canary 세대의
10,800개/99,802,626bytes가 최종 written 수와 일치했다. 결과 SHA는
`fba573fd62adec4f6a80c21fabccb09112c8224453394c46a68c7aaa80f2e496`이며,
별도 SQL 조회/출력 해시/역조인 검토 SHA는
`0843efee045917163527283f0cecd5c3487fc3e69cfb54c96632f27d6e362aba`다.

현재 날짜 폴더만 허용하던 새 검사기의 제한은 과거4개 하위 폴더4,222행과 충돌했다.
R1의 exit1을 보존하고 안전한 과거 하위 경로를 허용한 R2로 전수 재검사했다. 회귀5개·
Ruff F/E9·실제 검사·독립 검토는 exit0다. 제품 코드나 원본 파일을 바꾸지 않았다.

기존 디코딩 증거가 없는136,732개와 canary10,800개를 원본 fact에 다시 연결한 명시 목록으로
회수/바이트/디코딩 검사를 진행 중이다. 회수기2개 검사와 Ruff는 exit0이며 실제 완료는 아직
미확인이다. 이 작업은 부분 사본 PASS로 전체R4를 대체하지 않는다. 종료 후 전체 inventory와
orphan/과거 부재 원인/다른 보존 경로, CSV 소비자 결과 및120분 실패 원인·물리 시험은 남아 있다.

00:18 갱신: 이미지 전송은 SSH255/실행기1로 실패했고 원문을 보존했다. 받은1,480,151,040bytes는
SHA `e6dd9c51ef5974cc27a975c8c3e0226da48a0ae9939cb4ad5860b5753e11e237`로 고정했다.
전체 재전송 대신 별도 검토가 완전한 member의 해시/디코딩과 미수신 목록을 도출하고 있다.
잘린 archive의 완전/불완전 member 분리 fixture 및 Ruff는 exit0이며 실제 항목별 결과는 대기 중이다.

### 5.35 선택 이미지 실제 바이트와 기존 검증 증거 정산 — 2026-10-17 00:34 KST

부분 수신146,969개와 추가 회수563개를 원래 선택147,532개/1,371,059,860bytes에 전수 대조하고
각 SHA256·JPEG 전체 디코딩을 확인했다. 추가9묶음의 SSH exit0·stderr0, 각 archive와 로컬/공유
사본 해시를 확인했으며 원래 SSH255 실패는 보존했다. 입력 파일 목록 전달로 멈춘 작업 소유
tar 두 개만 경로·명령·생성 시각을 확인해 정리했으며 앱 backend14012는 유지됐다.

설치 전 전체 이미지 목록289,746개에는 과거 동일 바이트 증거153,014개와 새 디코딩136,732개가
모두 연결됐다. 여기에 닫힌 canary 세대10,800개를 더한300,546개/2,855,168,258bytes의 개별
증거를 정산했다. `P30/combined-image-coverage-e8b8d365aabe/summary.json`의 SHA256은
`60039608815ea70fac81ed69f4328b81670b13428994687cde71570565dc0f25`다.
정산 중 원래 inventory·prior proof·fact join·decode proof 읽기 잠금과 전후 해시를 유지했고,
새 정산기의 Ruff F/E9·실제 실행은 exit0이다. 제품 코드·운영 설정·설치본은 변경하지 않았다.

이 정산은 종료 후 전체 파일 목록이나 모든 R4 경로의 완료가 아니다. orphan·과거 부재 원인·
역사적 CSV 계약/내용 검사는 남아 있다. 원래 CSV exec46981은 같은 프로세스로 계속 실행 중이며
기존3600초 제한을 유지한다. 전체R4·120분 FAIL 원인·물리 시험·운영 승격은 미완료다.

### 5.36 닫힌 CSV 전수 소비자 완료와 과거 형식 대조 — 2026-10-17 00:43 KST

기존 exec46981은3046.5초 후 실제 exit0, consumer/worker exit0·강제 종료0·잔여 프로세스0으로
끝났다. 원래 입력과3600초 제한을 유지했다. CSV53,338행/순번1–53,338, 관찰 fact482,570행과
동일 수의 서로 다른 키, 이미지 fact4,385,307행 및 최종 manifest 해시·행 수가 일치했다.
관찰 키가 있는53,322행의 연결률은100%이고 누락 참조·진단 출처 불일치0이다. 별도 원본 CSV
전체 파싱으로 키 없는16행이 모두 startup_pending임을 확인했다. 원본의 stale244/valid50,620/
under_range2,458도 보존한다. 이는 시작 성능이 통과했다는 의미가 아니다.

입력5개와 출력 stdout/stderr/terminal, process receipt·정상 종료·실패 canary 출처를 대조했다.
`P30/canary-csv-qa-v2-r1/completed-review.json` SHA는
`166bf76d669a5dc2210fb2dde79e15891f1859b2828c072d0af35fa9164010b6`다.
최종 reviewer의 Ruff F/E9와 실제 실행은 exit0이다. v1은 metadata상 비활성, changeover/phase는
행0 manifest와 부재 상태이며 내용 검사를 수행한 파일로 세지 않는다. promotion profile 검사를
요구하지 않는 소비자 범위를 그대로 기록했다. 실제 전체R4/장비/출시 gate를 PASS로 바꾸지 않는다.

기존 백업의 과거 schema-mismatch9파일 헤더를 확인해 이미지31열, 관찰1.2.0/47열·1.3.0/54열·
1.4.0/55열로 저장소 소스와 대조했다. 대응표 SHA는
`25f220bfd4872dcfe38fe21e53f015290c87463f7500dd0430f75f315966902e`다.
전체 내용·논리 행·해시 재검사는 아직 수행 전이다. 원래 파일명이나 첫 물리 줄의 길이만으로
손상을 선언하지 않는다. 서버 앱은 전면 Running이며 새 작업 번호는 사용자 확인 대기다.

### 5.37 과거 형식 전체 행 검사와 혼합 버전/실제 NUL 구분 — 2026-10-17 01:10 KST

기존 백업의9파일6,461,851,976bytes를 SFTP로 회수하고 각각 신뢰 목록의 크기/SHA와 대조했다.
9회 모두 exit0/stderr0이다. 버전별 원본 행 규칙과 분할 적용의6개 동일 입력 비교를 통과한 뒤,
실제 관찰6,170,644행·이미지 fact54,112행을 읽기 잠금/전후 해시/디스크 index로 검사했다.
exec56203은270.436초 후 exit1, stderr0으로 완료됐으며 발견 항목703,393건을 보존한다.
파일별/파일 사이 관찰 키 중복0, 각 서비스 범위 내부 순번 gap0이다.

703,389건은 첫 행1.2.0을 파일 전체에 적용한 검사기의 가정에서 생겼다. 실제 원본은 동일47열의
1.2.0 307,470행과1.2.1 703,389행으로 구성된다. 과거1.2.1 commit의 동일 헤더/append 동작,
행 검사와 의존 함수6개의 동일 AST/import 및 원본 전체의 정확한 행 구간을 확인했다. 별도
분류기 회귀4개·Ruff F/E9·실행은 exit0이며 원래 검사/증거를 덮어쓰지 않는다.

나머지4개 진단은 과거2행의 버전 값 앞 NUL801개/1,611개를 중복 탐지한 것이다. 원본 record는
20260923 파일의3,094,807과20260928 파일의159,923이며 관찰 시각은 각각9월7일/24일 UTC다.
기존 백업과 현재 회수 파일의 해시는 같다. 원인과 영향·복구/처리 결정은 아직 미확정이며
정상 데이터나 후보 신규 손상으로 단정하지 않는다. 전체 스키마/CSV 역참조/이미지 실물 및
다른 보존 경로에 대한 R4 검사를 대신하지 않는다.

전체 검사 SHA `477cfa942955274beb9e11fe0d2130581b8f134f26cef07df1909c658fe4ded6`,
분류 SHA `20776aa53585bd687f2855494cb4a9a80d957434ee62b0db7669bc6d72c57b09`,
독립 SQL 수량/출력/전송 검토 SHA `1882eb16debf584cd3e8153cb39246a8b7c4533f0d699beb593ce91884c97052`다.
상세 경로/검사 범위는 후보 보고서01:10 절에 연결했다. 요약/영수증18개는 Z return에 해시 대조
사본을 남겼고 큰 원본/분석 사본은 개발 PC 위치를 명시했다. 새 전체 백업·서버 설정 변경은 없다.
01:07 운영 화면은 전면 Running/60295·1 적용 상태다.120분 FAIL·전체R4 미완료·물리 NOT_TESTED·
출시 HOLD를 유지하며 과거 이상 행의 참조/전후 기록과 다른 보존 파일 검사를 이어간다.

### 5.38 과거 NUL 두 건과 비정상 호스트 재시작 연결 — 2026-10-17 01:34 KST

기존 백업 로그11개를 크기/SHA로 회수 검증한 뒤, 사건 ±180초59줄과 인접 관찰7개씩을
원문으로 보존했다. 승인 SSH의 Windows System 두 시간 범위145/158건과 Application
1000/1001/1002 각2건, 총307건을 XML의 서버/provider/ID/시각과 대조했다. 조회 상한 도달·
오류는0이다.9월8일/25일 모두 Kernel-Power41 및 EventLog6008 뒤 새 서비스 poll_seq1에서
NUL801/1611개가 확인된다. 파일 전체 읽기와 전후 해시가 기존 백업과 일치한다.

이는 비정상 재시작과의 연관성 증거다. NUL 생성 원리·전원 상실 여부·기존 바이트의 원래
내용은 증명하지 못했다.6008의 종료 시각은 앱의 마지막 기록과 충돌하며, 당시 CSV는 선택
AppData 목록에 없어 참조 영향이 미평가다. 원본 복구/삭제 및 과거 실패 PASS 전환은 없다.
stderr의 writer 실패43줄도 과거 drop15와 같은 항목으로 정산하지 않는다.

검토기24개 selftest/Ruff F,E9 및 R2 실제43.453초 실행은 exit0이다. LF/CRLF 영수증 비교로
중단된 최초 실행은 보존했다. 대조 요약 SHA는
`05a242a6dd7d0c06f69417fe2ad876ffea09fc47de53c915b4aa7125b10ed951`, 독립 종료/출력/XML 검토
SHA는 `f96baeb53c47f01e9badba994e28f255cd47c397ed7cc87a7e0e13e189c8ef8b`다.
상세 입력·원시 이벤트·범위·Z 회수 영수증은 후보 보고서01:34 절에 연결했다.
진행 판정은PROGRESS이며 전체R4·물리 경계·120분 실패 원인과 운영 승격은 미완료다.
서버01:31 화면은 전면 Running/60295·1, Low Signal OFF 및 정식 출시 HOLD를 유지한다.

### 5.39 종료 검산의 파일 I/O 비용과 읽기 크기 확인 — 2026-10-17 02:09 KST

원래120분 결과의 동일70,076개 component 파일에 고정 원본 `review_window`를 실행했다.
cProfile/열기 기록/cProfile 순서로369.897/84.367/96.225초, 모두 실제 exit0·원본과 동일
FAIL 결과다. 초기/반복 cProfile의 함수 호출 수는 같고 native open은282.671→14.538초다.
캐시 상태가 통제되지 않아 이 차이를 원래 서버 timeout이나 특정 보안 제품에 귀속하지 않는다.
최종 설정 PASS는 창 종료1.4268911초 뒤이나, 이후 payload 재검산/결과 검산 중 정확한 중단
단계는 원래 기록에 없다. 원래 worker 결과·종료 기대값은 여전히 누락 상태로 보존했다.

두 cProfile에서 read 비용50.382/53.411초가 남아, 실제 작은 파일300개를 순서 회전/역순으로
2,400회 읽었다. EOF까지 크기/SHA가 모두 일치하며600회 read 합계는64KiB17.019ms,
1MiB291.022ms,16MiB+1byte4,393.750ms다. 이는 도우미의 큰 읽기 요청 비용을 확인한
로컬 증거다. 다음은 기존 경로·집합·크기·해시·JSON 검사와 제한을 유지하는 읽기 보완,
경계 회귀/전체 원본 corpus/대형 payload 대조, 같은 서버의 단계별 계측이다.

독립 정산은78,723회 열기 기록의 경로/횟수와2,400회 측정·300개 원본 해시를 확인했다.
초기 정산의 줄바꿈 동일성 가정 및 함수명 선택 오류는 보존했고 R2 exit0, 분석 도우미5개의
Ruff F/E9 exit0이다. 검토 SHA `364c53a1e9dafbd6c09062f6b08e1c72abfa8a39bad9323dd1804a774a660371`,
상세 실행/공유 기록은 후보 보고서02:09 절에 연결했다. 제품/서버 변경은 없으며 R1~R6와
전체 목표의 완료 근거는 여전히 부족하다. PROGRESS·목표active·출시HOLD를 유지한다.

### 5.40 읽기 크기 보완의 전체 자료·설치본 대조 — 2026-10-17 02:32 KST

`stream_fact`와 `read_json`의 요청 크기를64KiB로 제한하고 EOF까지 이어 읽도록 보완했다.
512MiB 해시 상한·16MiB JSON 기본 상한 및 경로/집합/잠금/동일성/SHA/엄격 JSON 검사는 유지한다.
수정 전 동일 회귀11개에서 실패4/오류2를 재현했고 수정 후11개, 기존 영향 검사152개가 exit0이다.
원본→수정→수정→원본의 독립 프로세스4회는 같은70,076개 수집 파일을 모두 검산했으며,
결과 전체가 기존 결과와 같다. 평균81.036→29.383초, 로컬 관찰 감소율63.74%다.
각 실행에서 실제 설치본 구성1,899개/563,853,145bytes의 파일 집합·잠금·해시·재검산도 통과했다.
읽힌 Python 모듈11개의 출처를 검산했고 차이는 위 두 모듈뿐이다. 원래120분 FAIL은 유지한다.

코드/회귀/설계 commit `2ab06e1d1f019bc3e51b7fbc59f1cf7dcbfbf2d9`의 세 Python blob은
시험한 바이트와 일치한다. 독립 정산·Ruff F/E9·diff check exit0이며 정산 SHA256은
`cb5eaad6f60b6eb95c260031bf5a8263f5e31876b8ca8e9ad51a4dab11b25261`이다.
증거는 `C:/Users/user/Desktop/SmartFactory/RB17_3f0ba68a` 및 후보 보고서02:32 절에 연결했다.
서버 미적용이며 캐시/호스트 상태는 통제하지 않았다. 같은 서버의 단계별 측정, 두 health 초과,
전체R4·과거drop15·물리 경계·최종 승격은 미완료다. 현재 단계는 PROGRESS, 전체 목표 active/HOLD다.

### 5.41 동일 서버의 오프라인 검산과 잠금 영향 대조 — 2026-10-17 03:32 KST

원본 코드의 서버 재검산은600.147초에서 HTTP component 검산 중 중단됐다. 새 묶음에서
보완 코드만 실행해 동일70,076개 자료와 전체 결과를100.897초에 대조 완료했다. 자료 검산은
86.384초이며 기존 FAIL/health 초과2건·누락 worker 결과는 그대로다. 실제 설치본1,899개와
제거 파일의 전체564,087,405bytes도 잠금·해시·앞/뒤 재검산을 통과했다.

두 진단의 Job 정리·프로세스 부재, 앱5프로세스의 동일 생성 식별자, 원래 핵심13파일의
해시와 누락2파일의 부재를 독립 확인했다. 회수44/56파일의 서버·개발 해시가 일치한다.
stdout 종료 코드와 launcher SHA를 대조했고 stderr의 CLIXML은 해당 종료 코드의
Write-Host 정보 레코드1개임을 확인했다. 실제 자식 오류/timeout 판정은 별도로 유지했다.

앞선 로컬 ABBA는 자료 검산 뒤 payload 잠금을 검사한 순서였다. 잠금을 유지하는 첫 추가
검산299.704초 뒤 잠금 해제29.889초·잠금 유지31.425초를 관찰했다. 잠금 자체로 지연을
재현하지 못했고 보호를 제거하지 않았다. 호스트/캐시는 미통제이며 원래 timeout의 인과는
미확정이다. 이번 오프라인 재검산을 실제180초 finalization 전체나 현장 성능 PASS로 확대하지 않는다.

진단 제어기16조건/요청14조건, PS5.1 parse/Ruff 및 실제 결과 독립 정산을 확인했다.
정산은 `RPN17_20261017_0c62910a/goal-turn-review.json`, SHA
`6b2c74bb626cf76fae7b8c150302fdf36bb1c8b3ed081f28631c4c0078298be6`이며 상세 입력·명령·
단계 시간·전송518파일은 후보 보고서03:32 절에 연결했다. 제품 설치/설정/전체 백업은 없다.
후속은 health 초과2건의 보존 원문과 부하 대조, 전체R4/과거NUL·drop15·물리 경계 검증이다.
03:31 운영 화면은 전면 Running/60295·1이다. 목표active/출시HOLD와 기존 롤백 기준을 유지한다.


### 5.42 1.0.30 동일 요청 진단 연결 — 2026-10-17 04:04 KST

1.0.30의 정확한 candidate/payload 결합을 진단 도우미에 추가했다.48개 단위·8개 native 그룹·
frozen11조건을 통과했고, source/helper commit0b940353의 EXE를 서버에 전달·전수 해시 검증했다.
기존120분 초과2건의 원시 대조는 이미 끝났으므로 새로운 원인 규명 결과로 반복 보고하지 않는다.

최초 SSH stdin 전달의 정체를 native 세대/자식/결과 폴더로 확인하고 해당 전달 프로세스만
정리했다. 동일 bootstrap 해시의 직접 전달로 독립 감시자18200·실행기16748을 시작했다.
04:03:38 KST 결과Hd05e8e89be52에18표본, 두 세대의 실제 생존을 확인했다. 앱/설치/설정은
바꾸지 않았다. 작업 정보는 자동 초기화돼 생산 여부 미확인이고 이 진단은 현장 QA가 아니다.

상세 원문·실행/해시·전송·정리 근거는 후보 보고서04:04 절과 Desktop/SmartFactory/
HD30_20261017_1c41bd2a/capture-start-review.json에 있다. 회수/동일요청 추적 검토가 남았다.
직전 메일 답신 재확인 턴은 새로운 목표 진전이 없는 NO_PROGRESS, 이번 턴은 실제 진단 시작의
PROGRESS다. 전체R4·과거drop15/NUL·물리경계·120분 실패/최종 승격은 미완료이며 active/HOLD다.


### 5.43 1.0.30 CPU 진단 종료 — 2026-10-17 04:25 KST

같은 실행을 종료까지 추적하고529파일/104,241,528bytes와 authenticated launcher SHA를
회수·대조했다.450개 요청의 native 시계/응답 원문을 재검산했고 최대175.4241ms,
200ms 초과0, HTTP 오류/timeout0이었다. worker/coordinator/guard exit0, Job 잔여0,
WPR recording 해제를 확인했다. 설정 전후 및 앱의 같은 세대도 유지됐다.

측정 중 작업 정보는 미입력에서 운영자 입력60227·5로 변경됐으며 CRD 재연결도 있었다.
따라서 전 구간 생산 QA가 아니고, 지연 원인/ETL 품질은 아직 미평가다. 기존120분 FAIL은
보존한다. 보존 NAS/압축 파일명 날짜 검색0과 CSV 참조 열을 가진272기록/208고유내용 후보를
확인했으나 사건 키의 실제 내용 검색은 하지 않아 과거 CSV 영향은 NOT_EVALUATED다.

상세 수치·해시·한계는 후보 보고서04:25 절과 HD30_20261017_1c41bd2a의
capture-closeout-review.json 및 historical-csv-catalog-search에 있다. 세 회수/재검산
스크립트는 exit0이다. 목표active/출시HOLD, 이번 턴PROGRESS를 유지한다.

### 5.44 과거 NUL 관측 키의 보존 압축 CSV 본문 검색 — 2026-10-17 04:39 KST

외부 ZIP CSV17,046논리 경로/16,586고유 내용/26,977,100,041bytes와 내부 ZIP
CSV161경로/115고유 내용/17,036,373bytes를 실제 EOF까지 읽었다. 두 범위 합동 고유 해시는
16,596개다. 사건 첫 관측 키2개는 UTF-8/16/32 바이트 검색에서0건이며 전체 선택 CSV의
CRC/크기/SHA와 대표 압축 사본의 잠금/전후 해시를 확인했다. 파일명 검색만의 결과를 갱신했다.

도구 self-test42개, 외부/내부 실제 검색, 외부23항목 정산은 exit0이다. 합동 정산 R1의
기준 해시 오기 때문에 발생한 exit1을 보존하고 원래 manifest에서 확인한 R2의135항목이
exit0으로 끝났다. 검색 자체는 재실행하지 않았다. 증거는 CSVREF_20261017_7eac9c23의
closeout-review.json, SHA `9d91c54aa41829eed681e03dbc534c0acaacb9c1a5e5e9cd15f8efd1ad31d97d`다.

손상 압축2개의 내부·유실 자료·다른 키/표현·압축 밖 NAS CSV는 포함되지 않는다. 고정 NAS
목록에서 압축 밖 CSV157,139개/81,844,390,133bytes를 정산했고 기존 검증된 사본과의
연결이 다음 작업이다. CSV 영향은 NOT_ESTABLISHED이며 R4를 PASS로 바꾸지 않는다.
제품/서버 변경·전체 백업은 없었다. 이번 턴PROGRESS, 전체 목표active/출시HOLD를 유지한다.

### 5.45 기존 NAS 사본의 실제 키 검색과 남은 범위 실행 — 2026-10-17 04:50 KST

고정 NAS 목록157,139CSV를 기존 PLC·온도 사본128,628개와 나머지28,511개로 빠짐/중복
없이 나눴다. 기존 사본의 본문127,008고유 내용/28,370,766,043bytes를 읽고 해시/길이/
입력 불변성을 확인했으며 사건 키2개는0건이었다. 검색122.235초/exit0, 독립 정산27항목
exit0이다. 경로 정규화 `/x` 거부 실패를 보존하고 엄격한10조건 및 실제128,628경로를
재대조했다. 실제 입력의 root/drive/traversal 경로는0이며 완료 검색을 재실행하지 않았다.

증거 CSVLOOSE_20261017_f04c62aa/review.json의 SHA256은
`a3623a35929f4933f5bfa56ba816df71e6da62179869f816525524747a583c0e`다.
나머지53,337,156,348bytes는 읽기 전용 NAS 검색을 시작했다.7개 사전 검사 exit0이며,
실제 session58660/PID53208/생성FILETIME134366536994252918의 생존을 확인했다.
04:50:38 KST의58파일/1,419,866,518bytes는 중간 값이고 최종 결과가 아니다.

같은 handle로 완료/오류를 추적하고 변경·미확인 파일 및 정확한 필드 참조를 구분한다.
출시HOLD/전체R4 미완료를 유지하며 과거 실패나 유실 자료의 영향 없음으로 확대하지 않는다.
이번 턴PROGRESS, NAS 부분은 verified live wait다. 제품/서버 변경·새 전체 백업은 없다.


### 5.46 결과 저장·worker 종료의 실제 제한 재현 — 2026-10-17 05:06 KST

보존 FAIL의 실제 review와 최종 health를 사용해 production expectation/JSON 저장·Pipe
전달·worker/supervisor·Job 종료를 실행했다. 정상 입력과 health 해시 변조2조건 모두
예상 실패 판정을 내구성 있는 결과로 저장하고 종료했다. 새 강제 종료/잔존 worker는0이다.
수집·경계 조회·payload/review 자체는 대체했으므로 전체 live finalization 검증은 아니다.
원본8파일과 소스11파일, 원래 누락2파일의 부재를 독립72항목으로 검산했고 exit0이다.

증거TAIL17_20261017_eb913d5c/review.json, SHA
`f6fec7a38f8aa626e884e13cb51a634caa3e00afcd0c93a0b0e92cbb8581b07e`.
원래120분 FAIL/timeout 원인UNDETERMINED를 유지한다. 상세 시간·바이트·대체 범위는
후보 보고서의 같은 시각 절에 기록했다. NAS 동일session58660의 생존 및 중간
187파일/11,415,056,245bytes를 확인했으며 최종 완료는 아니다.
이번 턴PROGRESS, 전체 목표active/출시HOLD. 제품·서버 변경·새 전체 백업은 없다.


### 5.47 NAS 결과 대조와 현재 CPU 추적의 보존 범위 — 2026-10-17 05:16 KST

NAS 정산기의14+8조건과 실제236경로/13,752,206,016bytes 접두부 대조는 exit0이다.
전체 선택28,511개는 아직 진행 중이다. 같은session58660/PID53208의 native 생존을
확인했고 접두부284파일/17,940,041,121bytes를 기록했다. 최종 결과/실제종료 대조가 남았다.

기존1.0.30 ETL의CPU105,986/DPC47,234/ISR30,729사건을 해독·payload 대조했다.
요청450개의 원문/시계 재결합으로 최대175.4241ms 요청216이 CPU sample의85.830883초
범위보다 앞임을 확인했다. 이 자료는 해당 지연의 CPU 원인 증거가 될 수 없다. 범위 안
요청42개도 완전한 thread coverage를 뜻하지 않는다. 독립 ETL reader·전체 추적 품질은
미검증이고 stack 누락2,265/leaf mismatch71을 보존한다.

증거HD30_20261017_1c41bd2a/cpu-decode-01/retention-review.json SHA
`77182ae9b48081b6f5f68e8caf7b4a5aa67ca3434796470c7386326eea8e596c`.
실제 해독·payload/retention 검산·Ruff exit0, Job 잔여0. 서버 접속/재수집/제품 변경/
전체 백업은 없었다. 다음 지연 진단은 동시 부하와 목표 요청의 추적 보존이 필요하다.
전체R4/120분 FAIL/drop15/물리 경계/최종 승격은 계속 미완료이며 목표active/출시HOLD다.


### 5.48 동시 API 보조 수집기의 로컬 검증 — 2026-10-17 05:31 KST

data6초/image0.25초 보조 수집기를 추가했다. health 중복 요청 없이 기존 HTTP 수집기의
응답/기록/fsync 검증을 사용한다. 실제 loopback HTTP와 native Windows Job에서 정상,
조기 중지, deadline, Job 배정 실패, 결과 body 변조, 예상하지 않은 중지, 입력 거부의
7개 시험이20.965초/exit0으로 끝났다. 별도 보존 결과52항목 검산과 Ruff F/E9도 exit0이다.
초기 Ruff의 미사용 json import1건은 제거했으며 최종 소스로7개 시험을 수행했다.

증거 `CONCURRENT_20261017_3e842b71/component-review.json`은2,979bytes,
SHA256 `2ddc10e9c6ad57d18871b4dc6a824b6b2c733042cd41bd9f59713fe713953062`다.
강제 종료2조건은 예상 FAIL로 보존했고 모든6개 실제 자식의 Job 잔여는0이었다.
조기 중지의 취소 슬롯과 HTTP FAIL을 유지했으며 이 결과를 서버 성능 PASS로 확대하지 않는다.
명시적 CPU 동시 부하 요청·trace 계약 연결, frozen helper, 서버 검증은 아직 수행하지 않았다.

NAS 동일session58660/PID53208/생성FILETIME134366536994252918의 생존을 확인했다.
완료된 중간 기록504개/26,209,283,257bytes, 키 후보0건/오류0건이며
전체28,511개 완료가 아니다. `nas-live-observation-04.json`에 접두부 해시를 보존했다.
제조사 답신의 App1 지원/엄격한 미만/REST 동일값 근거와 물리 시험 미완료를 구분한다.
이번 턴PROGRESS, 목표active/출시HOLD. 제품·서버 변경이나 새 전체 백업은 없다.


### 5.49 CPU 동시 진단 연결 및 frozen 검증 — 2026-10-17 06:01 KST

명시적 `sfl-health-cpu-concurrent-request-v1`을 CPU contract/lease와 연결했다.
WPR 준비 뒤 data6초/image0.25초·health가 같은3초 미래 origin을 사용한다. 첫200ms 초과
health를 확인하면 보조 요청 중지 → WPR 저장/정지 → 보조 drain 순서로 종료한다.
900/960초·외부1500초·최종180초 제한, 설정·앱 세대 결합과 출시HOLD를 유지한다.

도우미 commit `bfd78daff0aa7c325c773dc272b1fa04e350ad87`의90개 소스와 패키지를 대조했다.
Python23+10+16=49시험, native PowerShell8+10=18묶음, 실제 frozen CLI/실패 worker14조건은
exit0이다. 실제 loopback HTTP·native 자식2조건에서 정상 정리/Job잔여0을 확인했지만
앱·health·WPR 경계는 합성이다. frozen 검사는 잘못된 입력/비어 있는 설치경로를 거부한
범위이며 실제 성공 concurrent capture나 ETW 품질·서버 성능 검증으로 확대하지 않는다.
보존 소스·기록·종료/해시405항목 검산도 exit0이다. 증거는
`CTRACE_20261017_e94b0a7a/integration-review.json`이며 SHA256
`9c7f6c516cbba4da04e2610aafdbbc3606513d4156b9178f6d62783b95bf69c7`다. 최초 준비의 test script CRLF/LF 불일치 실패는 보존했고,
정확한 committed test script로 native10묶음을 다시 통과했다. 실행 소스 차이는 없었다.

배포 도우미는16,099,563bytes/SHA
`2bca181493c2a2514baee3735f595fb10207e7360b938542edba4d546bc3a64d`,
package manifest SHA `dcc582429f73d1469415eb842e43a9ec1cef6e40cc3dda26ad0ceee06c972db4`다.
제품 설치본은 재빌드하지 않았다. 새 현장 묶음15파일/16,941,380bytes는 개발PC와
`Z:/SmartFactory/20261017/send/HCT30_20261017_e94b0a7a`에서 해시 일치를 확인했다.
서버 탐색기에서 부모 새로고침·정확한 새 폴더 접근을 시도했으나0x80004005로 실패했다.
서버 SSH 세션에는Z매핑이 없으며, 개발PC의 직접IP UNC 조회는 기존/새 폴더 모두
인증 오류1326이었다. 이 별개 관찰만으로 서버 오류 원인을 인증 문제라고 확정하지 않는다.
서버 로컬 복사·잠금 해시 검증은 미완료이고 진단은 시작하지 않았다.
`server-delivery-attempt.json`에 실패와 준비 상태를 구분했다. 서버 설정·앱 종료·백업은 없다.
05:50경 읽은 동일 main17996/backend14012와 작업60227·5, 승인 설정을 확인했고,
05:59 서버 화면에서 Running·Smart Factory 전면·작업60227·5를 확인했다.

NAS 동일session58660/PID53208/생성FILETIME134366536994252918은 계속 살아 있다.
완결 기록3,712파일/36,907,026,135bytes의 접두부 대조는 exit0이다.4개 이미지 대장 사본에서
raw후보1,874건, 정확한 다른열 참조1,188건을 구분했다. 모두 `spot_image_linked_observation_key`
열의 `da076946-7bea-4165-a52c-0b89397453b7:1`이며 각 사본297건이다.
이는1,188개 서로 다른 유실 사건을 뜻하지 않는다. `spot_observation_key` 정확 참조는
현재 접두부에서0이고 두 번째 사건 키의 raw후보는 정확한 필드값 일치로 판정되지 않았다.
전체28,511경로 완료·원본 CSV 영향 판정은 아직 남아 있다. 접두부 검산 SHA는
`b7b7cc67c6d77db4529077d32c71fe5d4a9dd7cda976af556bc3110d8477b7fe`다.
제조사 계약 확인은 물리 경계 PASS를 대신하지 않는다. 원래120분 FAIL/full live finalization/
R4/drop15/물리 시험·승격은 미완료다. 이번 턴PROGRESS, NAS는 verified live wait이며 목표active다.


### 5.50 현장 동시 진단·독립 추적 및 NAS 최종 대조 — 2026-10-17 06:53 KST

서버 공유 경로가 다시 접근 가능해진 뒤 일반 원격 탐색기로 최종 로컬 복사를 마쳤고,
15파일/16,941,380bytes를 잠금 해시로 대조했다. 인증·ACL·네트워크 설정은 변경하지 않았다.
앞선0x80004005의 원인은 UNDETERMINED이며 실패 기록을 보존한다. 06:14:40 KST에 시작한
실제 frozen 동시 진단은 entry exit0으로 끝났고 결과2,215파일/111,484,594bytes를 회수했다.
launcher SHA는 `9f6deffded349776df74611de66258ea5a3836379de95e9b602d3dda2b79bfa1`이다.
설정/동일 backend14012·생성 시각 결합, 제어기/worker 종료, WPR 정리와 Job 잔여0을 확인했다.

health121건은 HTTP 오류/timeout0, 중앙값11.0282ms, p99 107.2514ms였고 마지막 요청120이
221.0337ms로200ms를 초과했다. 요청 전체와 native clock121건을 재계산했다. data41건,
image957건과 missed image 슬롯6개를 보존했다. 종료 후 취소 슬롯은 data109/image2637개다.
data1/image13건은 예정 시각보다0.0722–2.5579ms 일찍 시작해 기존 검사에서 invalid다.
이 판정을 완화하지 않았다. 저장1,006기록, pending/discard0이며 동시 HTTP는 FAIL/
채널 NOT_MEASURED다. 이 짧은 진단은 정식15/120분 성능 PASS가 아니다.

ETL76,283,904bytes/SHA `b7d06df21751cad3e0279ece5b5fd2df2ad6c5fe944ca744088e901a52c6d6cc`를
오프라인 해독했다. 대상 요청은 실제 보존 sample46.7969019초 범위 안에 있었다.
Windows tracerpt와 별도 TraceEvent 수집 결과를 대조해 전체사건1,337,420개 중 scheduler
964,958개, CPU sample90,533개, interrupt 종료/함수97,080개 및 대상 수집기 sample 스택1개가
일치했다. 커널35/사용자18프레임의 두 원시 StackWalk를 합친53프레임도 정확히 일치했다.
첫 검산의512MiB/XML2GiB 제한 불일치와 둘째 검산의 단일 스택 가정 실패를 보존했다.
검산기만 보완했고12개 스택 조합 검사 및 최종 전체 대조는 exit0, 서버 재수집은 없었다.
해독기의 전체 의미·모든 스택은 검증하지 않았다. sample stack 누락1,406개/leaf 불일치54개,
tracerpt 오류 envelope15005/111을 보존하며 선택 필드 대조를 전체 추적 PASS로 확대하지 않는다.

같은 요청의 연결 준비 구간192.48ms, 서버 route17.2605ms를 구분했다. native 수집기 구간
221.0456ms 중 CSwitch residency는1.0999ms, 비실행은219.9457ms다. 가장 긴 두 비실행 구간
127.5472/64.4168ms에서 outgoing state1(Ready), reason31/30이 관찰됐다. 합계191.964ms는
연결 준비 중 실행 준비 상태의 스케줄링 지연 증거다. 연결 구간은 초기 native 계측/Python/
socket 준비도 포함하므로 순수 TCP 지연으로 표현하지 않는다. state/offset 해석 근거는
[Microsoft CSwitch](https://learn.microsoft.com/en-us/windows/desktop/ETW/cswitch)와
[공식 PerfView 구현](https://raw.githubusercontent.com/microsoft/perfview/main/src/TraceEvent/Parsers/KernelTraceEventParser.cs)이다.
같은 구간의 PID9804는212 sample이며 추적 종료 process rundown 이름은 Explorer였다.
이는 경쟁 작업 조사 단서이고 Explorer나 네트워크를 근본 원인으로 확정한 증거는 아니다.

NAS 동일session58660은6,392.546초/실제exit0으로 종료했다. 남은28,511경로/
53,337,156,348bytes의 모든 완료 기록·경로·크기·해시·종료 영수증을 최종 대조했고 exit0이다.
기존 사본128,628논리 경로와 합쳐 고정 NAS CSV목록157,139개에 대한 사건 키2개 검색을
완료했다. raw1,874건, 정확한 다른열1,188건은 이미지 대장4사본의 같은관측키297참조씩이다.
`spot_observation_key` 정확참조0이며1,188개 별도 유실 사건으로 합산하지 않는다.
NAS 원자적 전체 snapshot/모든 CSV 내용 QA/원본 NUL 영향 판정은 이 검색으로 증명되지 않는다.
최종 정산 SHA `5a10372c92cbf2ae74d765abdff44d92b82059b341f978a3a0a6d40bab0b3384`.

실제 회수/closeout/CPU retention/scheduler 및 tracerpt 해독/독립 대조/구간 분석은 모두exit0,
최종 분석 도구 Ruff F/E9도exit0이다. 첫 기본 Python의 Ruff 모듈 부재는 저장소 backend
venv로 해결했다. 제품 코드를 변경하지 않아 재빌드·재설치·120분 재시험·새 전체 백업은 없다.
06:16 이후 작업 metadata가 비어 전체 생산 상태는 미확정이며 사용자 현재 제품/금형 확인은
대기한다. 서버 작업 종료 후06:25:46 KST 화면에서 Running·Smart Factory 전면을 확인했다.
이번 검산 단계는 개발PC의 보존 자료만 사용했다. 다음은 Ready 지연의 경쟁 작업/계측 영향과
14건 조기 시작의 격리 재현, 과거 이미지 참조 영향/처리 판단이다. R1/R2·full live finalization/
R3 실제물리시험/R4 전체QA/R5drop15/R6승격은 미완료이며 전체 목표active/출시HOLD다.
주요 근거: `CTRACE_20261017_e94b0a7a/capture-analysis-stage.json`,
`schedule-window-review.json`, `trace-independent-crosscheck.json`,
`CSVLOOSE_20261017_f04c62aa/nas-closeout-01.json`. 이번 목표 턴은PROGRESS다.


### 5.51 2026-10-17 07:04 KST — 보조 수집기 조기 대기 반환 수정·경쟁 작업 대조

현장14건의 조기 시작 경로를 조사했다. 새 보조 worker는 일반 관찰기의 ObservationStop을
거치지 않고 raw multiprocessing.Event를 HTTP 수집기에 전달했다. 개발PC Python3.12.6의
실제 native 대기960회에서 multiprocessing0.3ms의80회가 모두 일찍 반환됐고 최소 lateness는
-0.2964ms였다. threading480회는 조기 반환0이다. [해당 CPython 구현](https://raw.githubusercontent.com/python/cpython/v3.12.6/Modules/_multiprocessing/semaphore.c)은
Windows 대기를 정수 ms로 반올림한다. 이 근거는 누락된 deadline 재확인의 필요성을 보여주며,
서버14건 각각의 OS 내부 원인이나221ms 지연의 원인을 증명하지 않는다.

같은 worker 경로의 재현에서30ms 대기가0.0023ms에 끝나 수정 전exit1이었다. 보조 worker에
기존 ObservationStop을 연결하고 성공·예외 모두 bridge를 닫도록 최소 보완했다. 사용자 지정
중지를 유지하며 시각/음수 lateness 보정이나 기준 완화는 없다. 소스2파일을 commit
`d372d4efb98ea651b6a0062cf6e799a7ddb13d94`에 기록했고 검증된 실제 바이트와 committed blob SHA를 대조했다.
일반 HTTP/제품 로직/설치본은 변경하지 않았다. 기존 고정 도우미도 재작성하지 않았다.

실제 native 자식·loopback HTTP9시험, HTTP 구성요소32시험, native timing7시험,
기존 ObservationStop1시험은 모두 실제exit0이다. 6.2초 정상 자식의 data2/image25요청 전부
예정 시각 이후 시작했고 마지막 관찰 구간도 충족했다. manifest/본문·시각·종료 증거210항목을
별도로 검산해exit0이다. 실제 자식6조건 모두 Job 잔여0, 결함 주입2조건의 강제 정리와
변조/비요청 중지 등4조건의 FAIL을 보존했다. Ruff F/E9도exit0이다.
근거 `WAIT17_20261017_2d81a4c9/local-fix-review.json`, SHA
`09effa1ce48cf3a56fc7fea5735d2705f8e9fc5f95b8b65dbea84de8b8d9053b`. 새 frozen 패키지·서버 적용은 아직 미실시다.

별도 보존 추적에서64.4168/127.5472ms Ready 구간의 두 논리CPU residency를 빠짐없이
정산했다. 직후 교체 스레드는 각각 System TID13732(우선순위12), Explorer TID15572(10)이고
수집기 교체 시 우선순위는8이었다. 두 CPU 합계128.8336/255.0944ms 중 Explorer residency는
75.8099/106.8554ms였다. 앱·backend·DWM 등도 같은 구간에 실행됐다. residency는 DPC/ISR을
포함할 수 있어 정확한 CPU 작업시간이 아니며, process 이름은 추적 rundown 연결이다.
Explorer가 단독 근본 원인이라는 인과 증거로 확대하지 않는다. 과거 탐색기 창 종료 비교도
CPU는 낮아졌지만 health 실패가 남았으므로 이미 수행한 비교를 새 해결책처럼 반복하지 않는다.
근거 `CTRACE_20261017_e94b0a7a/competing-window-review.json`, SHA
`2942d109b548f5c02f7b11c98a32770546ca67da4566bdae32f5ebadc532b78a`, 실제 분석exit0.

기존120분 FAIL, 현장14invalid, R1/full live finalization/R3물리시험/R4전체분류/R5drop15/
R6정식QA·승격은 유지한다. 이번에는 서버 접속·설정 변경·새 전체 백업·제품 재빌드·재설치가
없었다. 목표active/출시HOLD이며 이번 목표 턴은PROGRESS다. 다음은 새 도우미 패키지 검증,
경쟁 작업/계측 영향의 인과 확인, 완료한NAS 검색을 이용한 과거 자료 영향/처리 판단이다.


### 5.52 2026-10-17 07:34 KST — 수정 도우미 frozen 검증·서버 전달·동일 실행 관찰

보조 수집기의 대기 수정 commit `d372d4efb98ea651b6a0062cf6e799a7ddb13d94`의90개 소스를 추출해 별도 미서명 도우미를
빌드했다. EXE16,100,167bytes/SHA `852b6c461fa40b4f10da0a52e6f8b8621f0eb9d8cb9d60b3707e1e3352900bd2`,
manifest SHA `7524a0102568af2f3dfd74482fe603c734a8fc9e2e344eb76e4927c8fd7fad86`다. 제품1.0.30 설치본은 변경하지 않았다.
빌드exit0, frozen CLI14조건(설명1정상/거부13예상실패), 실제 frozen 부모·자식3조건을 확인했다.
정상6.2초에서 data2/image25요청의 조기 시작0, 외부 중지와 소유 Job 시간 제한 종료도
예상 결과/잔여0으로 확인했다. 외부 시험 controller를 사용했으며 전체 WPR 성공 경로의
로컬 검증으로 확대하지 않는다. 소스부모가 onefile bootloader를 넘어 semaphore를 전달한
최초 시험은WinError6/exit1이었다. 시험 controller를 frozen 내부에서 실행하도록 고쳤으며
그 실패 자료와 정리 결과를 보존했고 제품 결함으로 분류하지 않았다.

패키지90소스/15내장모듈/기준 파일·요청본문·종료 증거569항목 대조는exit0이다. 상세 범위는
`CWAIT_20261017_c8314fa2/package-review.json`과 `frozen-companion-verification-r2.json`에 있다.
서버 공유 새 경로 접근 오류 때문에 기존 승인SSH로 새 수신 폴더에 전달한 후 CRD 탐색기
복사/붙여넣기 버튼으로 최종 `HCTW30_20261017_c8314fa2` 폴더를 만들었다. 기존 공유 전달본과
서버 최종15파일의 크기/SHA를 대조했다(exit0). 매핑·인증·부모ACL은 변경하지 않았다.

Smart Factory Running·60180/38 전면을 확인한 뒤 승인SSH로 한 번 실행했다(bootstrap exit0).
서버상07:30:02 시작, control `Dc2aced764774`, 결과 `H49927dfe58dc`다. 감시 PID6912와
entry PID10000의 생성시각을 매번 대조하며 2026-10-16T22:34:28.9553090Z 조회에서 두 세대가
실제로 살아 있고 probe 122개가 확인됐다. 현재는 진행 중이며 완료·성능PASS가 아니다.
요청은최대900초/최초200ms초과 포착이며 기존 종료예산을 유지한다. metadata60180/38은
관찰값이며 전체 생산상태의 별도 확인으로 해석하지 않는다. 다음 조회도 같은 실행만 사용한다.

기존120분FAIL/과거14invalid/R1·R2·full live finalization/R3물리시험/R4전수분류/R5drop15/
R6정식QA·승격은 미완료다. 새 전체백업·재설치·설정변경·120분재시험은 없다. 목표active,
출시HOLD, 이번 목표 턴PROGRESS이며 서버 수집은native 생성시각으로 확인한 verified wait다.
현재 단계 근거 `CWAIT_20261017_c8314fa2/progress-stage.json`. 종료 후 원본 해시와 전체 결과를
회수·검산하여 조기 시작과 CPU 지연을 따로 판단한다.


### 5.53 2026-10-17 07:56 KST — 대기 수정 현장 진단 종료·과거 이미지 참조 영향 확인

같은 실행 `Dc2aced764774` / `H49927dfe58dc`의 native 생성시각을 확인해 종료까지 추적했다.
entry/coordinator/worker exit0, owned Job 잔여0, WPR 정지를 확인했다. 서버 원본의 인증된
launcher SHA와 공유 회수본·개발PC 사본 8,039파일/157,175,652bytes의
목록·크기·SHA를 대조했다. 새 설치·설정 변경·전체 백업은 없다.

900초 동시 CPU 진단의 health450건에서200ms초과0, 최대143.0205ms,
중앙값10.8884ms, p99 66.3359ms였다.
data 요청150/누락0/취소0,
image 요청3599/누락1/취소0이며,
모든 본문·시각·예정 슬롯을 재대조했다. 보조 요청 조기 시작은0으로 이번 실행에서 대기
수정 효과를 확인했다. 과거14invalid를 재분류하지 않으며 이전120분FAIL도 유지한다.
전체 생산상태 별도 확인과 추적에 따른 계측 영향이 남아 정식15/120분 QA를 대신하지 않는다.
이미지 최대256.8425ms 요청1717은 다음 예정시각보다52.6417ms 늦게 응답을 끝냈고 슬롯1718을
놓쳤다. 이는 관찰기의 요청 누락이며 제품의 이미지 저장 누락이나 과거drop15와 동일시하지 않는다.

오프라인 CPU 해독과 원시/변환 이벤트133,084건의 선택 필드 대조는exit0이었다. 별도 ETL
reader 교차검사는 이번 실행에서 하지 않았고, 스택 누락1,209/최상단 IP 불일치51건을 보존했다.
실제 CPU 표본 범위는54.4943276초로 health424~449만 포함했다. 가장 느린health215의143.0205ms
및 이미지1717의256.8425ms는 모두 보존 범위 밖이었다. health215의계측상connect135.7867ms,
image1717의headers_wait229.1069ms는 관찰했으나 CPU/네트워크 근본 원인은 미확정이다.
다음 진단은 기존200ms기준을 유지하면서 보조 요청의 주기 초과·누락 시점에도 추적을 보존하도록
설계·격리 검증한다. health만 기다리는 현재 방식으로 같은900초를 반복하지 않는다.

별도로 개발PC에 보존된 누적 이미지 대장2,247,226,565bytes/4,385,307행을 전수 파싱했다.
원문 SHA `97a3fceb72b07bed757d11cfec73b20c1e0491ecbcc15fd394a1d978e88fb490`는
읽기 잠금 중 전후 일치했다. NUL801 사건의 관측키를 참조한297개 행은 모두captured,
stale, under_range였고 NUL1611 사건의 정확 참조는0이었다. 기존 NAS4사본의 두 사건에
대한8개 행번호 비교가 일치했고, 독립 SQLite 인덱스의 ID/경로/SHA/크기/서비스/시각/행번호
912항목 대조는exit0이었다. 실제 이미지 파일 존재·디코딩·원본 누락 수·손상 원인은 미확정이다.

분석 도구의 최초 JSON 배열 처리 오류와 행번호의 header offset 오류는 각각exit1로 보존했다.
시각차와 기록된 link age의 완전 일치 검사도exit1이었다. 297건 중1건은 약1.51ms 차이가
남아 R3에서 차이를 보존했다. 실제 코드는 capture 시각과 link 확인 시각을 별도로 받으므로
이 차이만으로 제품 결함을 단정하지 않는다. summary의all_raw_rows_saved는 모든 '일치하는
파싱 행'을 보존했다는 의미로 reconciliation에 정정했으며 원시 CSV를 재작성하지 않았다.

현재 근거는 `CWAIT_20261017_c8314fa2/closeout-stage.json`, `capture-closeout-review.json`,
`incident-image-links-r2/reconciliation.json`, `missed-slot-review.json`이다. 회수·capture검산·종료검산,
CPU해독/선택payload대조/보존구간/누락slot검토의 실제exit0을 확인했다.
Smart Factory Running·60180/38 전면 표시를 확인했다. R1/R2근본원인·full live finalization,
R3물리시험/R4전체분류/R5drop15/R6정식QA·승격은 미완료다. 목표active/출시HOLD/이번 턴PROGRESS다.


### 5.54 2026-10-17 08:16 KST — 보조 요청 이상 알림 재현·수정·패키지 검증

이전 목표 턴은 현장 진단 종료·회수·분석을 완료한 PROGRESS이며 현재 턴도 PROGRESS다.
설계5.33의 health 정상/이미지 지연 상황을 개발PC loopback으로 재현했다. 수정 전에는
이미지353.0669ms 및 관찰기 missed slot1건에도 추적 저장을 요청하지 않고8초 시험 제한으로
중단됐다(exit1). 제품의 과거drop15 원인을 재현한 시험은 아니다.

도우미 commit `4a79d1fed517f3ddfd32008d7ab211de35589fea`에서 요청 실패·기존 failure 임계값 초과·다음 슬롯 도달/초과·실제
missed slot의 첫 알림을 단방향 Pipe로 전달한다. 원문 SHA와 예정/판단 시각을 묶고 기존
health 대기 전후에 확인한다. 부모가 중지를 요청하고 WPR 저장을 요청한 뒤 자식 저장을
마치며 원문·알림·결과 일치를 검증한다. health200ms와 data6초/image250ms 주기는 유지한다.
추적 저장 요청 뒤 도착한 알림은 late로 별도 기록해 포착 근거로 사용하지 않는다.

첫 수정 시험은 Windows Pipe 종료가 WinError109로 보고되어exit1이었다. 정상 EOF 처리를
보완한 재시험은exit0, health1건/이미지353.3175ms의 알림을
받아 저장 단계로 진행했고 owned Job 잔여0이었다. 알림부터 부모 관찰까지
1633.2821ms가 걸렸으므로 즉시 보존을 보장하지 않는다.
기존 정상450개 health 일정, 임계값 경계, 첫/동시/마지막/늦은 알림, 실패/중복/원문 불일치,
취소·spawn 실패·Job 정리를 포함한 소스 검사116개가 통과했다. health HTTP 첫 호출의
환경변수 누락(exit1)은 기록을 보존하고 지정 경로로 재실행해2개 검사 exit0을 확인했다.
Ruff와 git diff --check도exit0이었다.

같은 commit의 도우미만 freeze했고 제품 설치본은 다시 만들지 않았다. 도우미 EXE SHA는
`1c9dfa3e4fb8aacc2699e0a136a287d3e5ba6bf896e5a5c98fb80ab25eb0d086`, package manifest SHA는
`9d377ee6762ff5d4584599d384f7af433ca3aa6d4c3362cdbf558083eb2cf3b4`다. 실제 frozen CLI14조건과 frozen 부모/자식의
정상·중지 요청·시간 제한·이미지 지연4조건 검증은exit0이었다. 패키지에 포함된 field 모듈
bytecode와 commit 원문도 대조했다. 도우미 소스 경로는clean이지만 기존 문서 변경이 남아
전체 저장소가clean이라고 보고하지 않는다.

근거는 `CNOTICE_20261017_5a63b057/progress-stage.json`과 동봉 source/시험 로그/패키지다.
현재 사용자 확인값은60180/38이며 과거 측정 전체 구간의 생산 확인을 대신하지 않는다.
이번 턴은 서버에 접속하거나 설치·설정 변경·백업을 하지 않았다. 실제 WPR 지연 구간 보존,
R1/R2 원인·full live finalization, R3 물리시험, R4 전체분류, R5 drop15, R6 정식QA·승격은
계속 미완료다. 다음에는 승인된 경로로 새 도우미를 전달·결합한 뒤 해당 이상 시점의 현장
추적을 수집한다. 목표active/출시HOLD를 유지한다.


### 5.55 2026-10-17 08:54 KST — 보조 이상 알림 도우미의 현장 정상 경로 검증 완료

수정 도우미 commit `4a79d1fed517f3ddfd32008d7ab211de35589fea`의 패키지599항목 대조,
공유 전달·원격 탐색기 최종 로컬 복사 및 서버15파일 해시 대조를 완료했다. 승인된 SSH로
`Ddcf6567f8c79` / `H5ebe9b83fd48`을 한 번 실행했다. entry/coordinator/worker exit0,
소유 Job 잔여0, WPR 정지와 로그 writer 종료를 확인했다. 인증된 launcher SHA는
`7b9abd144eaed58a6690cb61f36704afd1615afb7638e6f66328acc1181139a4`다. 회수본 8,040파일/
156,853,939bytes의 전체 목록·크기·해시가 서버 기록과 일치했다.

900초 진단에서 health450건의200ms초과·HTTP오류·timeout은0이었다. 중앙값
9.1518ms, p99 77.8724ms, 최대
98.3963ms(요청300)다.
data 요청150/누락0/취소0,
image 요청3600/누락0/취소0이며
보조 요청 조기 시작은0건이다. 본문·예정 슬롯·native clock을
재대조하고 비동기 저장 pending/discard0을 확인했다. 보조 알림과 late알림은 모두없었다.
따라서 실제 서버의 정상 종료 경로를 확인했으며, 현장 이상 알림 시점의 추적 보존 경로는
이번 실행에서 행사되지 않았다. 로컬 이미지 지연 재현 성공과 실제 서버 이상 재현을 구분한다.

오프라인 CPU 해독과 원시/변환 이벤트 135,053건의 선택 필드 대조는exit0이었다.
보존 CPU 표본 범위는56.0115560초이며 최대health 요청의 전체 클라이언트
구간은 해당 표본 범위 밖에 있다. 표본 범위 안이라는 사실도 완전한 thread coverage나
원인을 입증하지 않는다. 스택 누락1,471/leaf IP 불일치
61건을 보존했다. 이번 ETL의 독립 reader 교차검사는 수행하지
않았고 전체 추적 품질·지연 원인은 미확정이다. 이전120분FAIL을 이번 무재현 결과로 바꾸지 않는다.

수집 전후 main17996/backend14012의 생성시각이 같고 Running·60180/38을 확인했다.
운영 화면은 Smart Factory가 전면에 보이는 상태다. 현재 작업 확인을 과거 전체 측정 구간의
생산 확인으로 확대하지 않는다. 제품 재빌드·재설치·설정 변경·전체 백업·120분 재시험은 없다.
결과 확인 예: `CNOTICE_20261017_5a63b057/closeout-stage.json` → `capture-closeout-review.json`
→ `cpu-decode-01/trigger-retention-review.json`의 원문 해시와 판정 범위를 확인한다.

회수·원문/종료 검산·CPU해독/선택payload/보존구간 검사는 실제exit0이다. R1/R2 원인·full live
finalization, R3 물리시험, R4 전체분류, R5 drop15, R6 정식QA·승격은 미완료다. 동일 진단을
성공 결과가 나올 때까지 반복하지 않고 기존 보존 자료의 분석을 이어간다. 목표active/출시HOLD,
이번 목표 턴PROGRESS이며 실행 중인 진단은 남아 있지 않다.

### 5.56 2026-10-17 09:07 KST — 과거 이미지 누락 목록 171,179개 역방향 연결 대조

기존 10월14일 검증 이미지 중 10월16일 설치 전 목록에서 사라진 **171,179개 /
1,694,057,930바이트**를 보존 백업 목록·완전 디코딩 증거·닫힌 image fact 인덱스와
대조했다. 모두 기존 백업과 크기·SHA256이 일치하고 디코딩 PASS 근거가 연결된다.
이 중171,163개는 image fact의 정확한 경로·크기·SHA256·행번호와 일치한다.
나머지16개는10월13일 조사·격리 보존한 미참조 이미지와 정확히 같으며 새로운 미참조
파일은0개다. 이16개 로컬 사본의 현재 바이트도 다시 해시 대조했다.

별도 bulk SQL 검산으로171,179개의 원본 목록·백업·디코딩 행번호와 fact 연결을 확인했다.
전체 인덱스4,385,307행에서16개 이미지의 크기·SHA256이 다른 fact에 연결된 경우도0이다.
이 결과는 해당 누락 집합의 분류이며 전체 과거 누락 이미지나 현재 서버/NAS 전수 검증은 아니다.
사본 증거는 당시 검증 경계에 해당하며 현재 서버 백업의 모든 바이트를 재검사하지 않았다.
개별 삭제 기록이 없으므로 사라진 이유·retention 삭제 여부·기존16개 저장 실패 원인과
과거drop15는 미확정으로 유지한다. 원본 fact 생성·복원이나 오류 판정 변경은 없다.

근거는 `C:/Users/user/Desktop/SmartFactory/R4REV_20261017_6f021c8a`다.
확인 예: `result/summary.json` → `result/relations.jsonl`의 원본 행번호 →
`independent-review.json` 순서로 대조한다. 결과 summary SHA256은
`96fddf629a06750522c8df6b5fa78d7dae29ccb41dd1cc9a8b6bbdc7470b7b58`이다.
거부 조건6개 검사, 최종 Ruff(F/E9), 실제 대조·별도 검산은exit0이다. 최초 시험의
스트림 정리 경고(exit0이지만 깨끗한 결과 아님)와 unused import lint exit1은
`verification-history.json`에 기록하고 수정 뒤 영향 검사만 다시 통과시켰다.
제품 소스 변경이 없어 전체 health/build·현장 시험을 반복하지 않았다.

이번 단계는 개발PC의 보존 자료만 읽었으며 서버 접속·설치·새 전체 백업이 없다.
현재 전수 목록과 나머지 데이터 finding, R1/R2원인·R3물리시험·R5drop15·R6정식QA는
미완료다. 목표active/출시HOLD/이번 턴PROGRESS이며 실행 중인 진단은 없다.

### 5.57 2026-10-17 — 과거 CSV 복구 후보102개와 추가 사본 부재 확인

사용자는 NAS 외 2023~2025년 온도·PLC 보관 PC·외장디스크·백업이 **없음**을 확인했다.
이 질문의 답변 대기를 종료했으며 사본 부재를 검사 통과나 손상 수용으로 해석하지 않았다.

온도 손상19개와 PLC 손상1개의 대체 사본 후보를 기존 NAS 목록1,032,015행과
읽을 수 있는 외부 압축 파일 멤버1,031,166개에서 검색했다. ZIP의 Unicode 표시 이름과
원래 CP437 이름을 구분하고, 기존 PLC 손상본이 검색되는 양성 대조를 확인했다.
파일명 날짜 후보70개 외에 실제 문제 행 날짜8개로 후보32개를 추가했다.
총102개 / 1,533,321,166바이트 / 32,190,279행이며 기존 검증 사본71개와 NAS 읽기31개다.
NAS는 이전 검증 Z: 경로·SHA와 현재 크기·수정시각·읽기 전후 SHA를 대조했다.
현재 NAS 전체의 원자적 스냅샷은 아니다.

온도19개 중17개에서 전후 참조 기록과 같은 내용8,124건을 찾았지만 반복이 많아
복원 관계를 확정하지 않았다. 2025-06-17 정리본915,343행을 추가 확인한 결과,
데이터행771172/902130은6열이지만 온도값524.62025/5082025와 단위SPOT가 남아 있었다.
원본 결합 형태 손상15행 중13행은 정리본에서 앞뒤 참조 기록이 바로 이어지는 위치도 있다.
이를 특정 변환 프로그램의 실행이나 손상 발생 원인으로 단정하지 않는다.
구조상6열이라는 사실만으로 정상 복구본으로 사용할 수 없다. 남은2개 온도 파일에는
선택 후보 안에서 같은 전후 기록을 찾지 못했다.

압축 멤버3개는 EOF·CRC·크기·SHA를 다시 검증했다. 온도2개는 기존 후보와 동일한
바이트이고 PLC1개는 기존 NUL108바이트 손상본 그대로였다. 다른 이름·병합 자료·중첩
압축·읽을 수 없는 압축까지 대체 사본 부재를 증명한 결과는 아니다. 원본 수정·복원·
새 전체 백업은0건이고, 원래 실패 판정·원인 미확정·출시HOLD를 유지한다.

근거는 `C:/Users/user/Desktop/SmartFactory/R4REC_20261017_b2964c10`의
`closeout-stage.json`, `reconciliation-r2.json`, `recovery-review.md`다.
확인 예: 최종 대상 분류 → candidate group/number → 원문 journal의 앞뒤 행·SHA 순서로 읽는다.
closeout SHA256은 `1696af1873b0e964a6b6db7abb94c38a6536cd7bb598f47bd5f49ddbd5e40e1a`다.
이름/문맥 검사7개, 최종Ruff(F/E9),102개 관계 검산·선택 정리본 재읽기는exit0이다.
초기UNC 인증 실패와ZIP 표시/원문 이름 비교 실패, unused import lint 실패 및 수정은
`verification-history.json`에 보존했다. 제품 변경이 없어 전체health/build·현장 시험을 반복하지 않았다.

이번 단계는 개발PC 보존 자료와NAS 후보의 읽기 작업이며 서버 접속·설치·설정 변경은 없다.
R4 전체 분류·원인/처리 확정과R1/R2·R3물리시험·R5drop15·R6정식QA는 미완료다.
목표active/이번 턴PROGRESS이며 실행 중인 진단과 답변 대기는 없다.

### 5.58 2026-10-17 — 온도 정리본915343행 연결과 손상 전달 재현

개발PC `temp_info_git`에서 날짜별 LandData CSV를 생성하는 소스를 확인했다.
HEAD는 `473c6c6194fc0b21a81cfe65f5c49d00f03a485b`, 변환 파일 SHA256은
`7ded71609fc292ed3da45bc9f0640734ade49ad8b06b81ae326184ea98339680`이며
HEAD와 줄바꿈 정규화 후 일치한다. 과거 배포/실행 버전의 증거는 아니다.
기존 PLC 후보 소스 조사와 별개인 온도 정리 소스다.

현재 보존 csv-parser3.1.0과 실제 소스402–457행을 격리해 원시 결합 손상15행을 재현했다.
초과 열이 허용되고 parseFloat가 숫자 접두부를 받아들여2행은 온도524.62025/5082025,
고속값10/11, 단위SPOT로 남았다. 다른13행은 숫자 칸의SPOT가 NaN이 되어 제외됐다.
정상 인접30행은 모두 유지됐고 관측 정리본의2행과 셀 값이 정확히 일치했다.
원본 앱·DB·전체 내보내기는 실행하지 않았다.

해당 원시 파일714,327행의 부분 변환을 전수 재현한714,314행이 정리본의
201,030–915,343행과 값·순서가 일치했다. 별도 Python CSV/십진수 접두부 비교도
전714,314행과 canonical SHA를 대조했다. 이어 정리본 전체915,343행을 원시3파일의
2025-06-17 기록과 연결했다:141,550 + 59,479 + 714,314행이다.
원시3파일의 총1,186,199행을 읽었고, 해당 날짜915,356행 중13행 제외 구성과 일치한다.
이 한 정리본에서 연결하지 못한 행은0개다. 다른 날짜·파일에 대한 완료 증거는 아니다.

첫 prefix 후보를 잘못된 순서로 비교한exit1은 보존했다. 실제 시작 행을 확인한 뒤
세 입력을 순서대로 대조한 검산은exit0이다. 입력·정리본 전후 SHA·동일성은 유지됐으며
전체 정리본 canonical SHA는 `2495f10387c9f2fe204af7405cbe75e88daf25f5b842a5138cc37a3eefc347e0`다.
값·순서의 대응과 변환 동작은 확인했으나 당시 정확한 프로그램 실행 및 원시 파일의
최초 결합 손상 원인은 미확정이다. 현존 로컬 로그8개의 날짜 바이트 검색에도 해당 날짜
기록이 없었으며, 역사 전체 로그 부재를 의미하지 않는다.

개발PC LandData 폴더의 같은 이름 원시 파일은 기존 NAS 손상본과 동일 바이트였다.
추가 정상 백업으로 보지 않았고 원본·정리본을 수정/삭제하거나 값을 추정 복원하지 않았다.
소스가 있는 다른 저장소와 운영 제품에도 변경이 없다. 이 정리본을 정상 복원 사본으로
사용하지 않도록 기록했고,2개 이상값·13개 제외 행을 R4 처리 대상으로 유지한다.

근거: `C:/Users/user/Desktop/SmartFactory/R4TRANS_20261017_95a1fb8d/review.md`.
확인 예:45사례 재현 → full-sequence 결과/독립 검산 → entire-derivative의 세 원본·범위.
closeout SHA256은 `3718e1313fc20d7e1b694857c7097136547d24fc70c39ed8bae6542780a3d664`다.
최종 준비·Node 문법/재현·독립 검산·전체 정리본 대조·Ruff는exit0이다.
초기 로그 인코딩/CRLF/헤더 가정 오류와 수정은verification-history에 보존했다.
제품 변경이 없어 전체health/build 및 현장 시험은 반복하지 않았다.
R4 전체 스키마별 검증·처리 결정과 나머지 R1/R2/R3/R5/R6는 미완료다.
목표active/이번 턴PROGRESS/출시HOLD, 실행 중인 진단·답변 대기 없음이다.

### 5.59 2026-10-17 — 온도1,471파일 장비명·단위 전수 대조

보존 온도 사본1,471개(27,534,639,606바이트), 총576,684,549행의 장비명·단위 문자열 검사를 마쳤다.
6열576,684,382행 중 단위C는576,684,380행, 단위SPOT는2행이다.
장비명은 Spot272,557,244행 / SPOT304,127,138행이며 대소문자를 병합하지 않았다.
표기와 물리 장비의 동일성·교정·온도 정확도가 입증된 것은 아니다.

단위SPOT 두 행은 `LandData_2025-06-17.csv`의 데이터행771172/902130이다.
값은 각각524.62025/고속10,5082025/고속11이며 앞 단계의 손상 전달 재현과 일치한다.
이상 파일915,343행을 별도 검산에서 다시 읽어 다른 이상 단위가 없는지 확인했다.
나머지1,470개는 최초 도우미의 파일별 잠금·전후 해시/동일성 검사를 재사용했다.

기존 구조 손상33행은 단위 집계에서 제외해 별도 유지했다. 다른10열 XLS134행은
6열 단위로 해석하지 않았다. 제목 없는2파일1,061,679행은 열 위치 관찰에 한정한다.
이전 문법 검사나 이번 단위 집계로 전체 의미 검증·정상 복구본 판정을 대신하지 않는다.

최초 도우미가 제목만 있는0행 파일에서 KeyError로 exit1이 됐다. 완성된1,470개 원장은
바꾸지 않고 SHA를 고정했다. 제목 전용 회귀시험에서 같은 실패를 재현한 뒤 수정본으로
누락1파일만 확인했다. 완성 원장은 기존 바이트+새1개 결과를 그대로 연결했다.
최종7사례, Ruff F/E9, 재개 및 전체 원장 대조는 실제 exit0이다. 최초 실패 기록도 보존했다.

사용자가 NAS 외 추가 백업은 없다고 확인한 사실을 유지한다. 이 답변과 이번 검사는
다른 이름·압축 속에 정상 사본이 전혀 없다는 증명이 아니다. 손상 원본·정리본을 수정하거나
추정 복원하지 않았다. 새 전체 백업0건, 제품 변경0건, 서버 접속/설치/설정 변경0건이다.
제품 변경이 없어 전체health/build 및 같은 현장15/120분 시험은 반복하지 않았다.

확인 예: `unit-summary.json` 집계 → `unit-records-complete.jsonl` 파일별 단위 →
`unit-review.json`의 두 원문 행 → `verification-history.json` 실패·수정 이력을 확인한다.
요약 SHA256: `4b3006f72beed897188e9f6e774e4e79805805aacbec1c9e696d7c288b401825`.
완성 원장 SHA256: `49cb1c85a3b936608b306b6ab11d1ae8f49eeae0d5eb452bc7a204ad7fc8a901`.
검산 SHA256: `bcaa81f21f2e326baf709cd9e0f35f69b30b6963614cbc81ad733755076ed2d7`.
근거 폴더: `C:/Users/user/Desktop/SmartFactory/R4UNITS_20261017_31b87de2`.

R4 전체 분류·원인·처리 결정과 R1/R2, R3물리시험, R5drop15, R6최종QA는 미완료다.
목표active/이번 단계PROGRESS/출시HOLD를 유지한다. 실행 중인 진단·답변 대기는 없다.
다음에는 별도로 찾은 PLC 정리 소스의 자정 전환 조건을 기존 원문 관찰 쌍과 대조한다.
소스가 존재한다는 사실만으로 과거 실제 실행이나 날짜 이상 원인을 확정하지 않는다.

closeout SHA256: `7e59842595a9ae5583c5118cf5ea880739a9b1860f5377a016201a76d6918ab4`.

### 5.60 2026-10-17 — PLC 관찰35쌍의 변환·파일 경계 재현

과거 정리 PLC의 관찰35쌍을 보존 원시 기록과 현재 변환 소스로 모두 재현했다.
같은 원시 파일 안의32쌍과 파일 사이 경계3쌍이며, 날짜·시각·숫자7개·비고가 일치한다.
관찰 분류는 날짜가 그대로인 자정 전환15쌍,0.04초 시간 감소1쌍,인접 동일 기록19쌍이다.
35쌍의 연결 완료가 정리172파일/전체 PLC 자료의 모든 행 연결 또는 최초 원인 확정은 아니다.

확인 소스는 개발PC `temp_info_git/server/utils/PLCMergeData/PLCMergeProcess.js`다.
SHA256은 `0b3f1e92948915b165045467685e5374e48b4b62d1f319b94f34101e0b1a25d4`,
마지막 해당 파일 commit은 `8ddbab8e6e61f93a161e2c6feb6149f8058bbb55`(2025-01-18)다.
현재HEAD와 줄바꿈 정규화 후 일치하고 해당 파일은 수정되지 않았다. 과거 배포본/실행 기록은 아니다.
파일명 `PLCData_YYYY-MM-DD.csv`와 영문10열, 원시 파일명 순서 처리 방식이 검사 자료와 맞는다.

원시 파일마다 날짜를 파일명에서 가져오고, 시·분·초가 모두0인 행을 만났을 때만 하루를 더한다.
실제144파일128,041행을 처음부터 처리했다. 원시 자정 전환114쌍 중97쌍은 날짜가 넘어갔으나
17쌍은 날짜가 남았다. 예:23:59:58.58→00:00:04.03에서는0초 행이 없어 전날 날짜를 유지한다.
정리본 자정 이상12쌍을 이 동작으로 재현했고, 나머지5원시 관찰은 이번35정리 관찰과 연결되지 않았다.
이5건이 전체 정리 자료에서 누락됐다는 판정은 아니다.

남은 정리3쌍은 해당 날짜±1일의 원시4,970파일302,535행에서 각 행을 찾았다.
원시6파일359행을 추가 재현하니 이전 파일의 마지막 행→다음 파일의 첫 행이 정확히 이어졌다.
다음 파일명은 전날23:59대인데 실제 첫 기록은00:00:01 또는00:00:07대로 시작했다.
파일별 상태가 초기화되고0초 기록을 만나지 않아 전날 날짜가 남는 결과였다.
보존 원장 안에서 이 파일들이 파일명 시각 순서상 바로 이웃함도 대조했다.

별도 Python 검산은 원시150파일128,400행의 전체 변환 값·순서 해시와 정리24파일472,626행의
35개 관찰 위치를 확인했다. 동일 기록19쌍과0.04초 감소는 원시에도 있어 이 변환으로 새로
생긴 현상이라고 보지 않는다. 최초 PLC 기록/시계 원인은 계속 미확정이다.

첫 데이터 콜백을 건너뛰는 코드도 확인했다. 선택144원시 파일에서는 모두 실제 빈 줄이었다.
기존 전체 원장 기준 빈 줄 없는 원시1,601파일은 모두 데이터0행이었다. 관찰 범위의 첫 실제
데이터 손실로 보고하지 않는다. 빈 줄 없는 합성 입력에서 첫 행이 제외되는 동작은 별도 기록했다.
원본 프로그램·DB·CSV 내보내기는 실행하지 않았고, 인코딩 자동 감지는 재현 범위가 아니다.

Node 격리 재현과 독립 검산,5개 시각 사례/2개 파서 사례, 최종Node 문법 및Ruff F/E9는exit0이다.
독립 검산 초안의 해시 구분자 가정 오류(exit1)를 보존하고 실제LF 규칙에 맞춘R2가exit0으로 끝났다.
원본·운영 앱·다른 저장소 변경0,날짜 자동 보정0,새 전체 백업0,서버 접속/설치0건이다.
제품 변경이 없어 전체health/build·동일 현장15/120분 시험은 반복하지 않았다.

확인 예: `replay-result.json`의32쌍 → `boundary-search.json`의나머지6원문 행 →
`boundary-replay.json` 및 `boundary-review.json`의3파일경계 → `source-provenance.json` 순서로 읽는다.
근거 폴더: `C:/Users/user/Desktop/SmartFactory/R4PLCT_20261017_42092ea9`.
32쌍 재현 SHA256: `f2cad646cbc1c4e0dedb0846fe5bf6728e77f53d3327ad1fbed9524eeccd99bf`.
35쌍 최종 검산 SHA256: `b40c29f6c59558d8771fe7905619869f6654d4c979b5d5a8b8479b3c49471332`.

현재 보존 코드가 관측 결과를 만드는 동작은 확인했으나 당시 실제 실행과 최초 기록의 원인은
미확정이다. 손상/이상 원장을 정상으로 바꾸지 않았다. R4전체와 R1/R2·R3물리·R5drop15·R6최종QA는
미완료이며 목표active/이번단계PROGRESS/출시HOLD다. 실행 중인 진단·사용자 답변 대기는 없다.
다음은 원시 폴더별 변환을 정리172파일의 전체 행과 연결해 영향 범위를 정산하는 단계다.

closeout SHA256: `7a19a5e2829afc2732e70bc4509a55019e07f45768994c56938094642d1c08f3`.

### 5.61 2026-10-17 — PLC172정리본 전체 원시 연결·수록 범위 정산

보존 PLC127,158파일(972,602,108바이트)을 전수 재현·독립 검산했다.
원시126,986파일8,541,219행과 정리172파일6,788,297행이다. 원시 중 제목만 있는1,601파일도 포함했다.
원본 ZIP의 EOF·CRC·member SHA와 전체 ZIP 전후 SHA를 확인했고 원본을 수정하지 않았다.
Node에서 실제 보존 변환 부분과csv-parser3.1.0을 실행하고, 별도 Python CSV/Decimal 구현이
모든 파일의 값·순서 해시·행 수와 날짜별 집계를 다시 대조했다. 인코딩 자동 감지는 재현 범위 밖이다.

정리172파일의6,788,297행 전부를 원시 변환값과 연결했다. 연결하지 못한 정리 행은0개다.
전체 원시 자료를 합쳐 본 날짜별 기준에서는168파일이 전체 일치,4파일은 정확한 앞부분이다.
최초 결과의169일치는 폴더별 일치1개를 포함한 값이다.2025-01-24의50행은 이전 원시 폴더와
일치하지만 다음 원시 폴더까지 합치면31,395행 중 앞50행이므로 최종 분류는 부분 수록이다.

| 정리본 날짜 | 수록 행 | 전체 원시 변환 행 | 정리본 뒤에 남은 원시 행 |
|---|---:|---:|---:|
|2025-01-24|50|31,395|31,345|
|2025-06-28|3,976|5,229|1,253|
|2025-07-01|5,049|18,740|13,691|
|2025-07-03|3,832|10,253|6,421|

이4파일은 모두 특정 원시 파일의 마지막 행에서 끝나고, 다음 미수록 행은 다음 원시 파일의
첫 데이터 행이다. 저장된 부분 내부의 값·순서 불일치는 발견하지 못했다. 부분 수록 이유나
당시 내보내기 시점/선택 폴더를 실제 실행 기록으로 확정한 것은 아니다.52,710개 미수록 행의
원시 파일과 마지막 수록/첫 미수록 위치는 `partial-review.json`, `january-review.json`에 있다.

변환 규칙상215날짜 중43날짜는 이번 보존 정리 파일 목록에 없고 원시1,700,212행이 남아 있다.
기존 정리 기간 안의6날짜는2024-12-26(36,798),12-27(51,870),2025-06-20(15,589),
06-23(4,224),06-24(7,321),07-02(8,226)로124,028행이다. 나머지37날짜1,576,184행은
기존 정리본 기간 뒤의 원시 자료다. 정리 파일이 없다는 사실을 원시 데이터 소실로 보고하지 않는다.
전체 정산은6,788,297수록 +52,710부분 수록 뒤 +1,700,212정리 파일 없음 =8,541,219원시 행이다.

이 결과는 보존 소스의 변환 규칙에 따른 값·순서·수록 범위 확인이다. 앞 단계에서 재현한
자정 날짜15쌍·0.04초 감소1쌍·동일 기록19쌍을 정상화하지 않았다. 물리적 날짜/시계의 정확성,
당시 실행본·내보내기 범위/시각은 계속 미확정이다. 다른 과거 손상PLC/NUL·온도·이미지·압축
미분류 finding도 이 검사로 PASS가 되지 않는다. 자동 복원·원본 변경·새 전체 백업은0건이다.

전체producer95.031초와 독립 검산127.454초는 실제exit0이며, 부분 수록 대조·집계 정산·
6개 grouping fixture·최종Node 문법/Ruff F/E9도exit0이다. 서버 접속·설치·제품 변경은0건이다.
제품 코드가 같아 전체health/build·기존 현장15/120분 시험은 반복하지 않았다.

확인 예: `coverage-ledger.json`에서 날짜와분류 → `whole-records.jsonl`의member와출처SHA →
`whole-result.json`의전체/폴더별 해시 → `independent-review.json`과부분 수록 경계 순서로 읽는다.
근거: `C:/Users/user/Desktop/SmartFactory/R4PLCF_20261017_b2d1b79a`.
전체 재현 SHA256: `f1aa2965316c6092650a5de35665600e45a76a806d1371a05cf1b32d8f2b2517`.
독립 검산 SHA256: `c6b621845b7d20fd02b6bdc4f342c0d01a5d5426126635d99558c3853ce512b5`.
범위 원장 SHA256: `ff768a7ebd90d7fc375f44742340caec9e1d17709d3ef84c5debec6a5d7b061f`.

전체R4와R1/R2·R3물리·R5drop15·R6최종QA는 미완료다. 목표active/이번단계PROGRESS/출시HOLD를
유지한다. 실행 중인 진단·사용자 답변 대기는 없다. 다음에는 남아 있는 과거Rect CSV70개
(9열header/4열본문249,252행)의 생산자 계약을 확인한다. 완료한PLC 전수 재현은 반복하지 않는다.

closeout SHA256: `14720c1617aca3a3389d6bc292d5015333579d10c03697cdb429a0c67a373fd1`.


### 5.62 2026-10-17 — Rect CSV 70개 형식 재현과 값 검토

보존 ZIP `abs.zip`의 69개와 `abs_1.zip`의 1개, 총 70 CSV의 249,252행을 전수 재확인했다.
9열 제목과 4열 본문이 일치하지 않는다. 같은 ZIP의 비교 파일 1개 43,749행을 포함한
총 71파일 293,001행을 검사했고, 9열 비교 파일도 Rect_4~8은 전 행 빈 문자열이었다.
누락된 제목 칸을 0으로 채우거나 실제 값 5개가 유실됐다고 해석하지 않았다.

clean 보존 소스 `OCR-raspberry/OCR-raspberry.py`의 commit은
`da2f129263a771946a7b2c1389dee1f6dfbd6a4c`(2024-05-23 10:52:32 +09:00)다.
Git blob과 현재 파일 바이트가 일치하며 SHA256은
`75978c25e2c3ab0168abb1dc0f74ea30cea366c4ab887fc1167a962b2affe0e9`다.
353행은 항상 Date와 Rect_1~8을 제목으로 기록하고, 370행은 실제 영역 수+1만큼 본문을 만든다.
387~392행은 OCR 결과에서 영문자·숫자·마침표를 허용하며, 361행은 현재 길이 그대로 저장한다.

해당 구문만 추출해 메모리 안에서 실행했다. GUI·카메라·OCR·원본 파일 쓰기는 실행하지 않았다.
3개 영역은 4열, 8개 영역은 9열을 만들며, 기존 값·시각을 입력하면 71파일 전체의
제목·본문·개행 바이트가 동일하게 재현된다. 이것은 저장 형식의 기전 재현이다.
일부 CSV가 commit 시각보다 이르고 당시 배포/실행 기록도 없어 실제 생산자 실행을 확정하지 않는다.
원본 화면의 OCR 정답, 영역 설정, 각 Rect의 물리량·단위도 미확정이다.

| 범위 | 파일 | 행 | 숫자가 아닌 비어 있지 않은 값이 있는 행 | 앞 3값 중 빈 값이 있는 행 |
|---|---:|---:|---:|---:|
| 4열 본문 | 70 | 249,252 | 6,093 | 1,807 |
| 9열 비교 본문 | 1 | 43,749 | 480 | 0 |
| 합계 | 71 | 293,001 | 6,573 | 1,807 |

마지막 두 열의 행 집합은 배타적이지 않을 수 있어 더하지 않는다. 비수치 비어 있지 않은 셀은
Rect_1 6,349 / Rect_2 456 / Rect_3 2,171, 총 8,976개다. `Z.1`, `C.` 등도 포함된다.
빈 문자열은 앞 3열 각각 21/1,782/42개다. 숫자 문법 통과가 실제 계기값 정확성을 뜻하지 않는다.
모든 파일의 NUL, 파일 내 시각 역전, 인접 동일 시각은 0개다. 실제 시계와 파일 사이 연속성은 별도다.

member CRC·크기·SHA256은 종전 구조 검사 71개와 일치했고 입력 파일 전후 해시도 일치했다.
`0435.zip`과 `0436.zip`이 분석 대상이며, `새 폴더.zip`인 `0437.zip`은 0435와 같은 바이트로
다시 확인했다. 이를 별도 고유 자료나 정상 복구본으로 집계하지 않았다. 외부 추가 사본 없음이라는
사용자 답변을 유지한다. 원본 수정·복구·새 전체 백업·서버 호출·제품 코드 변경은 0건이다.

`inspect_rect_r2.py`(5가지 실제 구문 fixture 포함) 7.269초/exit 0,
`review_rect.py` 3.617초/exit 0(1,011 비교), 최종 3개 Python helper Ruff E9/F exit 0이다.
독립 검산은 CSV/AST 생산자 구현을 쓰지 않고 CRLF 줄·쉼표 분할로 전수 대조했다.
R1은 같은 해시의 중복 ZIP을 경로로 구분하지 못해 member 검사 전 exit 1로 중단됐고 보존했다.
R2는 고유 사본 경로와 해시를 함께 확인한다. 제품 변경이 없어 전체 health/build와 기존 현장
15/120분 시험·설치는 반복하지 않았다.

처리 기준: 원본을 보존하고, 영역의 물리적 의미·단위·OCR 정확성을 확인하기 전에는 검증된
수치 추세나 품질 판정에 편입하지 않는다. 헤더·값을 자동 수정하지 않는다.
분류는 `CODE_REPRODUCED_HISTORICAL_DEPLOYMENT_UNCONFIRMED`이며 데이터 PASS가 아니다.
78개 BOM-only CSV와 손상 ZIP 2개 내부 미상 범위, 다른 손상/원인 미확정 자료는 남아 있다.
전체 R4와 R1/R2·R3 물리·R5 drop15·R6 최종 QA는 미완료, 목표 active/이번 단계 PROGRESS/출시 HOLD다.

확인 예: `result-r2/records.json`의 archive/member_index → column_kinds/nonnumeric_tokens →
`source-excerpts.json`/`replay-fixtures.json` → `independent-review.json` 순서로 확인한다.
근거: [상세 검토](C:/Users/user/Desktop/SmartFactory/R4RECT_20261017_c8e4a210/review.md).
전체 결과 SHA256: `c058cee9214245a563c3186769d9b234c08e11d85e192a2cff5b68f809834368`.
독립 검산 SHA256: `649ed892bdd508f5897a5e8ad8b5d497952c24c312fffcf634abe13147ddab03`.
closeout SHA256: `53eec466e307333470698d090406f23a80f7a9c614c230ec099910ca15f33b8c`.


### 5.63 2026-10-17 — BOM-only 출처와 손상 ZIP 자체 앞부분 확인

78개 BOM-only CSV를 60개 ZIP의 원본 member 바이트와 같은 묶음의 실행 메타데이터로 대조했다.
모두 UTF-8 BOM EF BB BF 3바이트이며, raw Windows 시스템 이벤트 32개와 redacted 46개다.
30개 실제 run_id에 연결됐고 온도·PLC 측정 파일로 분류하지 않는다. 중복 보관 member 수를 실행 수로
세지 않는다. 연결된 메타데이터 사본 상태는 COLLECTED 3/FAILED 10/PARTIAL 65이며, 이는 시스템
이벤트 조회의 성공 상태가 아니다. 개별 조회 성공/실패 기록은 모든 관련 메타데이터에서 찾지 못했다.

실행별 collection_script_sha256 13종을 전부 보존 소스와 연결했다. 12종은 Git blob/CRLF와,
1종은 보존 현장 도구 ZIP member와 일치했다. 13종 모두 Get-WinEvent의 오류를 SilentlyContinue로
처리한 뒤 Export-Csv -Encoding utf8로 저장한다. 조회 오류를 별도 기록하는 변수가 해당 구문에 없다.
Windows PowerShell 5.1에서 빈 입력(오류0)과 존재하지 않는 로그 조회(오류1)를 시험했으며,
둘 다 raw/redacted 각각 동일한 3바이트 BOM을 만들었다(exit 0). 과거 실제 조회를 재실행한 것은 아니다.
과거 파일의 분류는 DIAGNOSTIC_SYSTEM_EVENT_EXPORT_WITH_NO_RECORDS, 빈 원인은 UNDETERMINED다.
이벤트가 없었다거나 측정 데이터가 유실됐다고 확정하지 않는다. 향후 현행 수집기에 조회 범위·성공
상태·오류 ID/유형·건수를 구분하는 증거를 추가하되, 기존 해시가 고정된 도우미와 결과는 보존한다.

손상 ZIP 2개는 자체 local header부터 순서대로 해석하고 완전한 payload를 EOF·CRC·크기·SHA로
검증했다. 정상 대조본의 이전 검증 member 원장과도 모두 일치했다. 파일로 추출하거나 복구하지 않았다.

| 손상 사본 | 온전한 항목 | 파일 수 | 검증한 압축 해제 바이트 | 부분만 남은 다음 항목 |
|---|---:|---:|---:|---|
|0084.zip Portable|21|19|371,052,442|dxcompiler.dll|
|0431.zip OCR|15,769|14,779|2,074,149,335|cublasLt64_12.dll|
|합계|15,790|14,798|2,445,201,777|2개|

Portable은 offset220,200,960부터160,824,015바이트, OCR은 offset860,880,896부터
2,272,588,647바이트가 모두0임을 재확인했다. 자체 중앙 디렉터리와 원래 뒷부분은 미복구다.
정상 대조 ZIP의618/17,304항목을 사라진 원래 뒷부분의 확정 목록으로 사용하지 않는다.
원래 tail 내용과0채움 발생 원인은 미확정이며, 대조본 존재를 원본 덮어쓰기 승인으로 사용하지 않는다.

온전한 앞부분의 CSV3개는 matplotlib 예제다. data_x_x2_x3.csv는 제목 없는 공백 구분11행·3열이며
x/x²/x³관계를 확인했다. msft.csv는7열·65행, Stocks.csv는 출처 주석 다음11열 제목·524행이다.
독립 검산의 첫 파일 header/body_rows는 일반 쉼표 파서의 미리보기였으며,
library-sample-contracts.json의 실제 공백 구분 형식을 최종 판단으로 쓴다. 금융값의 외부 사실검증은
하지 않았다. 함께 있는 프로그램/라이브러리 PNG25·JPEG2는 Pillow verify·전체 load를 통과했다.
이 결과를 공장 측정 스키마나 ZIP 미확인 뒷부분의 통과 근거로 사용하지 않는다.

BOM 검사R2, 실제 PowerShell 재현, ZIP 앞부분 검사R2와6개 payload fixture, 독립48,193개 비교,
예제형식 확인, Python5개 명시 Ruff E9/F는 모두 실제exit0이다. BOM R1의 ZIP루트 경로 처리,
ZIP R1의 이름 구분자 정규화 오류, Git 소스1종 미발견은 실패 기록을 보존하고 해결했다.
최초 디렉터리 지정 Ruff는 파일을 찾지 못해 검사로 세지 않고 명시적5파일 검사를 수행했다.
원본 변경·새 전체 백업·복구파일 작성·서버 호출·제품 코드 변경은0건이다. 제품 코드가 같아
전체health/build와 기존 현장15/120분 검사·설치는 반복하지 않았다.

확인 예: bom-records.json의 member/run_id → collector-source-map.json → powershell-export-result.json.
ZIP은 badzip-prefix-summary.json의 경계 → badzip-prefix-records.json의 자체 header와SHA → independent-review.json.
근거: [상세 검토](C:/Users/user/Desktop/SmartFactory/R4ARC_20261017_94c9d2af/review.md).
BOM 결과 SHA256: `cc4964f3e14dc12988e22e38010828999b1f34b5c6fa59de1cf404d47a6b62d6`.
ZIP 결과 SHA256: `ea3692df8f7a508584a5b55faa6f3be0f58a45604c048c630cc4b1f0436d29a4`.
독립 검산 SHA256: `5ea98d7d65139b3bdf382acfce5d3e3482ab7197c67cbead1062069d0f88cb33`.
closeout SHA256: `43f3fa816ce2b74a32a2273eb016cdb0656d2842554b2d496785a8461d0e9818`.

전체 R4의 다른 손상·의미 미확정 자료, R1/R2 성능원인·200ms기준, R3물리, R5drop15, R6최종QA는
계속 미완료다. 목표active/이번단계PROGRESS/full_data_gate NOT_EVALUATED/출시HOLD를 유지한다.
실행 중 진단이나 사용자 입력 대기는 없다. 다음에는 현행 비고정 진단 수집기의 이벤트 조회 결과
기록을 보완하고, 과거 증거의 미확정 범위는 최종 영향·처리 원장에 남긴다.


### 5.64 현행 health 진단기의 System 이벤트 조회 기록 보완(2026-10-17)

5.63의13종은 역사적 수집기다. 현재 health 진단에는 해당 Get-WinEvent 경로가 없어,
과거 소스 대신 field-v1028의 현재 소유 worker에 읽기 전용 System 조회를 연결했다.
field_system_events.py가 조회 범위/시각/XPath·오류 단계/유형/Windows 코드·부분 건수를
기록하고, field_health_collection.py가 측정·trace 저장·보조 drain·최종 결합 뒤 실행한다.
system-events.json은 기존 manifest에 결합한다. 완료된0건과 실패를 구분하며 실패/제한/취소는
matched_record_count=null이고 전체 수집 완료도 거부한다. 상세 한도는 설계5.34를 따른다.

최종 이벤트15개·health 통합31개·trace/runner/동시 요청/소유 Job 회귀53개, 총99개가 실제exit0이다.
개발PC의 실제 보존 이벤트2건을 PowerShell과 대조했다. 최초 최근 창은0건이어서 양성 경로
검증으로 세지 않았다. 오류·부분 결과·정확한/초과 건수·취소·시간 한도·정리 실패·결과 변조를
검사했고, 명시적4파일 Ruff E9/F와 관련 Git diff 검사가 exit0이다. bkit에 계획 파일이 없다고
표시된 것은 사용자 지정 plan 파일명 때문이며 기존 계획/설계에 따라 작업했다.

검사별 결과는 review.md와 verification.json, 최종 소스 사본/해시는 evidence-manifest.json에
연결했다. [상세 기록](C:/Users/user/Desktop/SmartFactory/EVTQ_20261017_5ac4c3b7/review.md), closeout SHA256
`45c3367f155ac3299a079eaf62c7a3eaa3cfb988d577a6b0943f387f8f57da22`. 기존 archive closeout 해시는 다시 일치 확인했다.
Windows API query/next/render/close 동작은 Microsoft 문서를 확인했고 상세 기록에 링크했다.

이번 보완은 진단 helper 소스에만 적용했다. 새 frozen helper·WPR 전체 실행·서버 적용은
미검증이며 기존 배포본에 이 기능이 생겼다고 보고하지 않는다. 제품 코드는 변경하지 않아
전체 product health/build·재설치·기존15/120분은 반복하지 않았다. 서버 호출/새 전체 백업0건.
과거78개 BOM의 조회 결과는 여전히 UNDETERMINED다. 전체 R4 영향·처리 원장과 R1/R2/R3물리/
R5drop15/R6최종QA는 미완료이며 목표active/이번단계PROGRESS/출시HOLD를 유지한다.

### 5.65 NAS CSV 구조 검사 범위 결합과 미대응 내용 검사 착수(2026-10-17)

고정 NAS CSV157,139개/81,844,390,133바이트를 온도1,470·PLC127,158사본 및 기존 NAS본문
검색28,511개와 경로·크기·mtime·SHA로 결합했다. 본문 검색 완료를 CSV 구조 검사로 세지 않았다.
온도/PLC/압축 구조 원장과 같은 내용인148,920파일/53,028,047,789바이트는 기존 검사에 연결됐다.
나머지8,219파일/28,816,342,344바이트는 조회한 원장에 대응이 없으며, 중복 제거하면
7,596내용/25,506,700,718바이트다. 원장 밖의 모든 검사 부재나 현재 alias 전체 불변성을 뜻하지 않는다.

별도 검증기38개 확인과 모든 경로/출처/내용집합 정산은 실제exit0이다. 초기5,909+추가11,137개의
압축 CSV를 합쳐17,046논리/16,586고유내용과154finding을 정산했다. 초기 finding5개는 PLC NUL1,
Stocks예제1, Mac동반바이너리3이다. 후자는163바이트로 BOM-only78개에 더하지 않는다.
기존11개 단계의 고정 해시를 재확인해 알려진 문제8범주의 영향·보존·미확정 원장도 작성했다.

읽기 전용 도우미의 CSV/입력28개와 종료4시나리오가 실제exit0이다. 최초 정상종료fixture는
process exit0 직후Job active1이 남아 실패했다. 최대5초 정상 정리 대기를 추가한 후47ms 내0이
관측됐고 오류/시간초과/부모종료도 확인했다. 실패기록은 유지했다. 마지막3도우미 Ruff E9/F exit0.
11:18:40KST에 R4SCOPE_20261017_62e84d39/scan-r1을 실행했으며 도구session76433이다.
시작/진행 기록만으로 종료나 구조 PASS를 주장하지 않는다. 이 실행의 summary/terminal와 실제
종료 코드를 확인한 뒤 후속 정산한다. 원본 복사·수정·새 전체백업·서버 호출은 하지 않는다.

[범위·처리 보고서](../04-report/production-release-risk-validation-data-coverage-20261017.report.md),
coverage-summary SHA256 `ba959067ba4290da1e8624066843c6ca7125651eaebf7e2b3bb068c9f2cb8b1e`.
전체 R4/출시 조건은 미완료다. 중첩 CSV·과거 스키마/metadata·최종delta·역방향 이미지 연결과
R1/R2/R3물리/R5drop15/R6최종QA를 남기고 목표active/이번단계PROGRESS/출시HOLD를 유지한다.

### 5.66 중첩 CSV 구조 검사 결합과 원본 참조의 증거 범위(2026-10-17)

설계5.36에 따라 중첩161논리 CSV/115고유 내용을 전수 결합했다. 기존105내용에151경로를
연결하고 추가10내용/1,601,544바이트/11,266본문행을 보존 ZIP3개에서 검사했다. 새 구조
finding은0개이며 기존18논리 BOM-only finding은 유지한다. outer78개와 중복 내용이므로
고유 손상 수로 더하지 않는다. 원본 추출·변경·새 전체백업 없이 잠금/전후해시/멤버EOF·CRC를 대조했다.

추가 해시 목록6개의11,256참조/5,667고유 내용을 기존 outer/nested 본문 원장과 대조해
37내용/54참조를 연결했다. 나머지5,630내용/11,202참조는 해당 목록에서 찾지 못했으며,
NAS 고정 목록의 이름·크기 후보도0개다. 사본 미발견을 실제 소실로 단정하지 않는다.
동봉 JSON과CSV5,568행의 전수 일치는 원본 존재·당시 경로·시각을 증명하지 않는다.
NIC3파일의 수치/이벤트1행의 형식은 확인했으나 카운터 원값·이벤트 조회 완전성은 미확정이다.

승인 SSH 읽기3회(hostname,명시 경로,상위 폴더 목록)는 실제exit0이다. 기본 EvidenceBase와
과거 실행3경로는 PathNotFound였고, Desktop/SmartFactory 바로 아래에도 해당 이름은 없었다.
당시 override 경로는 미확정이며 서버 전체 검색이나 모든 원본 부재로 보고하지 않는다.
2023~2025 외부 백업 없음 답변을2026 진단 원본 부재로 확대하지 않았다. 서버 변경0건이며
11:38KST 화면은 SmartFactory 전면/Running/제품60180·금형38/작업정보OK였다.

10fixture와 최종 별도691확인은 실제exit0이다. 최종2helper Ruff E9/F도exit0이며,
최초 검산기의 unused Counter lint 실패와 그때의 결과는 보존했다. 제품 코드가 변하지 않아
product build/health·설치·기존15/120분 시험은 반복하지 않았다. 같은 NAS검사session76433은
계속 관찰하며 재실행하지 않는다. summary/terminal·실제 종료가 있어야 완료로 분류한다.

근거: [범위 보고서](../04-report/production-release-risk-validation-data-coverage-20261017.report.md),
[상세 검토](C:/Users/user/Desktop/SmartFactory/R4NEST_20261017_679a7046/review.md).
verification-r2 SHA256 `0b342432886fa5ff3d136b70361c82d4d7c0ed1357a1a6e1ae69811efc02ddde`.
중첩 구조 범위만 완료다. 과거 원본 참조·스키마 의미·최종delta·이미지 역방향 대조와 다른
출시 조건은 미완료이며 목표active/이번단계PROGRESS/full_data_gate NOT_EVALUATED/출시HOLD다.

### 5.67 NAS 중간 finding의 형식·PLC 사본 대조(2026-10-17)

NAS 실행의 완결된5,707행 prefix를 길이·SHA로 고정하고540고유 내용/242,342,088바이트를
후속 검사했다. 첫 실행은538개 후 쉼표 CSV parser 오류로exit1이며 소유 프로세스 정리0을
확인했다. 완료된538개를 보존해 재사용하고 나머지2개를 검사했다. 오류 파일은 CP949 탭 구분
형식으로35행/8열 전부 해석되었다. 첫 오류는 잘못된 구분자 적용에 따른 오탐으로 정정한다.
온도NaN5행과 다른4수치 칸의 각35행NaN은 별도 품질 제한으로 남긴다.

Rect521내용/5,588,004행 중520개는 보존 문자 필터/CSV writer로 바이트 일치했다. 남은1개는
85,394행의 `0.00E+00` 표기1칸이다. 이는 과학적 숫자 표기이며 모든 비일치 값을 비숫자 손상으로
분류하지 않는다. 기존1,285,529행/2,230,024칸은 단순 소수 정규식 거절 건수다. 물리량·단위·OCR
정답·실제 배포 소스는 미확정이다. 제목 없는5개와 동적 본문 폭도 원래 형태로 보존한다.

PLC test-2 사본11개는 공통9열·순서2,883행으로 비교했다. 붙은 행4개를 메모리에서만 나누면
각각의 전체 문자열이 정상 폭 비교사본4개 및 빈 행 제외 사본1개와 일치한다. 다른2개는 모든
차이가 시간 표기의 끝0 추가 또는 마지막 콜론→점이며 나머지 칸은 같다. 빈 행2,883개가 있는
사본은 행 위치를 별도로 확인했다. `_13`의 빈 행은 뒤에 연속되므로 이전 INTERLEAVED라는
분류명을 위치 증거로 사용하지 않는다. 원본 날짜·실제 값·생성 원인은 미확정이며 복구 파일은 쓰지 않았다.

선택 밖 옛 통합CSV3개/2,636행은 제목14열·본문19열이다. 보존Git `46f95079aeb455ca3b1ebab1bc3022d78052e3d2`
소스의 설정 제목/고정19열 행 구성을 순수 메모리에서 재현해3개 바이트가 일치했다. 당시 실제
설정이나 배포본의 확정은 아니다. 빈 파일/개행만/Invalid Date/HCell signature 및 기타CP949
자료도 각 범위·수치 사용 제한을 기록했다. 추가2023~2025 외부 사본이 없다는 사용자 답변을 반영했다.

후속 검사·PLC 비교·차이 분석은 실제exit0, 별도 증거 정산1,676확인도exit0이다. 처음의exit1은
보존한다. [상세 기록](C:/Users/user/Desktop/SmartFactory/R4NAS_20261017_7cc6fa64/review.md),
verification SHA256 `f2323068e377ee91a49544234cf396cd018e2a365822700a104c65eab6f72cce`.
NAS 전체session76433은 별도 실제종료/terminal 정산 전까지 진행 중이다. 이543개 후속 분석을
전체R4 완료로 확대하지 않는다. 원본 수정·새 전체백업·서버 호출·제품 변경0건이다.

### 5.68 NAS CSV 구조 범위 완료와 세대 연결 후보 확정(2026-10-17)

기존session76433은12:08:49KST에 실제exit0으로 종료했다. 7,596고유내용/25,506,700,718바이트,
8,219alias를 전부 검사했고 읽기 실패0이다. worker3,008.44초, Job47ms정리 뒤active0,
강제종료0/stderr0이다. 기존구조근거148,920경로와결합해고정CSV157,139개 전부를 연결했다.
잠금 전후SHA·선택/기록/집합/크기/alias 정산353,458확인은 실제exit0이다.

남은4인코딩 finding은CP949 탭구분으로총15,345행 파싱 완료했다. 통합2개21열,
가공2개8열이며 후자의온도NaN40행은 보존한다. 기존후속분석과합쳐532개generic finding의
형식 분류를마쳤다. PLC붙은행4개는보존사본과경계분리일치, 빈행2개는후미연속으로정정했다.
형식분류완료를실제원인확정·물리값검증·복구실행으로확대하지 않는다.

generic제목60종을다음의미검사목록에 전부배치했다. 그중새v2측정51/관찰fact11/이미지fact11
고유내용을73내용/79사본경로로연결하고,15부모의모든인접JSON/JSONL247개72,822,940바이트를
고정NAS목록에서선정했다. 측정56경로중예상metadata41개발견/15개목록미발견이다.
이는본문검사전후속범위이며모든NAS JSON이나기존검사범위전체가아니다. 이름일치로세대를
확정하지않으며미발견을전역부재로단정하지않는다.

새형식검사3fixture/실행·최종분류보완·후보선정은각실제exit0이다. 최초정산기Ruff는미사용
import로exit1이었으며수정후Ruff/실제정산exit0이다. 제품·서버변경/전체백업0건이다.
[상세검토](C:/Users/user/Desktop/SmartFactory/R4NASFINAL_20261017_c4dd9a9c/review.md),
reconciliation SHA256 `af555b8c7ccb870fd5113af6aa2242549c0edc612672bf79bd4f41b86b0b4d5a`.
기존NAS대기는종료하고세대/metadata/전체의미·최종delta/이미지역방향검증을이어간다.
전체목표active/이번단계PROGRESS/full_data_gate NOT_EVALUATED/출시HOLD다.

### 5.69 인접 JSON 읽기와 metadata·manifest 내용 대조(2026-10-17)

고정 후보 JSON 241개와 JSONL 6개, 총 72,822,940바이트를 읽었다. strict UTF-8/BOM,
중복 키·비유한 수·Unicode·JSONL 파싱 finding과 읽기 실패는 0개다. 과거 내용 해시가 없는
입력이므로 현재 SHA·목록 크기/mtime 일치만 증명하며 과거 바이트 불변으로 확대하지 않는다.
실제 reader exit 0, worker 17.157초, 정리 뒤 Job active 0, 강제 종료·stderr는 0이다.

metadata 41개의 선언 열은 CSV 제목과 모두 일치한다. active-column hash는 21개 일치,
20개 미기록이며 후자는 옛 계약의 기록 부재다. finalized 선언 12개의 CSV 이름도 일치한다.
예상 metadata 15개는 고정 NAS 전체 목록에서도 같은 basename 후보가 없으나 전역 부재를
증명하지 않는다. 행별 스키마·순번·출처·닫힌 세대 검증을 이 제목 대조로 대신하지 않는다.

manifest 68건을 경로와 별도로 내용 해시/행 수로 결합했다. 11건은 같은 본문 SHA와 행 수가
있고, 36건은 0행·해시 없음 선언이다. 21건은 지정 registry에서 같은 전체 해시가 없었다.
역사적 절대경로 미해결 55건은 파일 손실 건수가 아니다. 0행 선언도 실제 본문 부재의 증거가
아니다. 추가 행이 붙은 사본인지 확인할 prefix 후보 9파일/8,323,536,965바이트/53대응을
준비했으며 아직 prefix를 읽거나 일치를 판정하지 않았다. 3참조에는 해당 NAS 후보가 없다.

JSON fixture 13확인, 상대경로 fixture 7확인과 세 실제 실행은 exit 0이다. 제품 변경·서버 호출·
원본 수정·새 전체 백업은 없다. [세대 대조 기록](C:/Users/user/Desktop/SmartFactory/R4GEN_20261017_df0e602d/review.md),
내용 결합 SHA256 `f697da92c2b199f3effe0cbea30d43730a9bd71c30620fdb4b20137a726f3365`.
후속 prefix·행 의미·최종 delta·이미지 역방향과 R1/R2·R3 물리·R5·R6는 남아 있다. 출시 HOLD다.

### 5.70 누적 fact prefix로 manifest 미대응 21건 연결(2026-10-17)

이미 회수한 로컬 누적 이미지 fact 1개와 역사적 관찰 fact 2개, 총 7,938,087,216바이트를
선정했다. 29 fixture 확인 뒤 원본 바이트를 CSV 논리 행 경계까지 hash하고, 전체 EOF/행 수/
제목/기존 SHA 및 같은 잠금의 재해시·전후 identity를 대조했다. 새 NAS 읽기·복사·전체 백업은 없다.
worker 112.86초, 실제 session54342 exit0(897e50), Job 정리 active0, 강제종료·stderr0이다.

25개 후보 대응 중 21개가 일치했으며 고유 미대응 참조 21건 모두 해결됐다. 이미지15건은
4,385,307행 누적 본문의 prefix, 관찰4건은 702,095행 본문의 prefix, 나머지 관찰2건은
4,236,916행 본문의 prefix였다. 다른 관찰 후보4쌍의 불일치는 중복 후보 비교이며 미해결
참조가 아니다. 기존 NAS 후보 9파일을 추가로 읽을 필요가 없어 그 읽기는 실행하지 않았다.

manifest 68건의 최종 연결은 전체 본문/행 수 11일치, 정확한 prefix/행 수 21일치,
0행·해시 없음 선언36건이다. 36건은 changeover16/process-phase16/image4이며 실제 본문
부재나 정상성 판정이 아니다. 과거 경로의 현재 상태·실제 물리값·행별 계약·닫힌 세대는 별도다.

관찰 prefix 3,242,032행과 3,802,168행은 기존에 확인한 논리 record3,094,807의 NUL801개를
포함한다. 전체 해시와 metadata 선언의 일치는 이 손상을 정상으로 바꾸지 않는다. 원인·원래
손상 없는 바이트·복구·관련 CSV 영향은 미확정이며, 이번 대조로 과거 JSON의 불변성까지
증명하지 않는다. 원문과 이전 finding을 보존했다.

별도 정산128확인은 실제exit0(f235e0). 최초 정산기 lint의 미사용 import2개를 제거한 뒤
Ruff exit0(0a4cb5)을 확인했다. [prefix 상세 검토](C:/Users/user/Desktop/SmartFactory/R4PREFIX_20261017_6eadbcd2/review.md),
reconciliation SHA256 `8eb90d9cdce87964eece9f960662cbb2ea5d8fd064d68dc7364b82154b9f2fd0`.
다음은 기존 동일 내용의 의미 검사 재사용과 남은 스키마·원본 참조·최종 delta·이미지 역방향이다.
전체 목표 active/PROGRESS, full_data_gate NOT_EVALUATED, 출시 HOLD를 유지한다.

### 5.71 v2 측정 전체 행과 참고 규칙 차이 분류(2026-10-17)

고정 NAS 세대 후보 중 측정 CSV51내용/56경로의 4,325,141행, 4,271,397,540바이트를 모두
읽었다. 경로 잠금·선택 SHA·크기/mtime·전체 EOF/행 수·같은 잠금에서 재해시·전후 identity를
대조했다. 실제 session31414 exit0(4adda3),573.093초,소유 Job active0이며 강제 종료와 stderr는
없다. 스키마2.0.0~2.5.2의8종이다. 열 폭/NUL/시각 구문/순번 및 적용 가능한 행 규칙 범위다.

Git 객체14개에서 원래 함수와 의존 정의363개/소스31개를 고정해 앱 초기화 없이 실행했다.
56문맥 중14개는 metadata 선언 commit,27개는 배포 commit 미상 참고 계약,15개는 metadata
미확보 참고 계약이다. 선언도 실제 설치 바이트의 증명은 아니다. 옛 스키마22내용/1,795,039행은
공통 형식·순번 검사만 가능했다. 선택 소스 풀에서2.0.0 원래 계약을 찾지 못했다는 범위이며
저장소 전체 부재를 뜻하지 않는다. metadata 부족으로 운영 규칙5문맥/온도 강화 규칙4문맥은
적용하지 않았다. 원래 caller의 metadata 인자를 유지했고 부재를 현재 승인 설정으로 채우지 않았다.

참고 규칙의 메시지3,070건은5내용의3,033논리 record에서 나왔다. 공통 형식/순번 finding은0이다.
기록을 다시 고정해 변경 이력이 있는6commit의3함수와 비교했다. 실제 session32214 exit0(ad242a),
51.625초,Job active0이다. 최종 issue 원장 전체가 후속 비교에 포함됨을 확인했다.

- 3,060메시지/3,023행은 문서화된 상태명·stale 처리 규칙 변경과 일치한다. 출처 none 허용4,
  오래된 유효 관측값 허용2,025, phase-v2 상태명77, phase-v3 상태명880,stale sentinel37행의
  74메시지다. 실제 배포 commit은 미상이다. 열이 부족한 후대 운영 계약은 통과로 세지 않았다.
- 10메시지/10행은 비교 가능한6계약 모두에서 남았다.6월29일 record11,188~11,192는
  cached_observation인데 Temperature/원 관측값이 빈칸이며 source_error이다.7월7일
  record64,635~64,639는 current_observation인데 Temperature498.6과 관측값498.1이 다르다.
  각5행이 같은 관측 순번을 공유한다. 원인·실제 올바른 값·현재 제품 재현 여부는 미확정이다.

이10행은 원본 SHA와 행 식별자·필드 값을 보존했다. 당시 소스·관측 fact와 연결할 후속 대상이며
복구값을 만들어 쓰지 않았다. 버전 차이3,060건도 데이터 전체 정상/출시 통과로 바꾸지 않았다.
별도 fact22내용 중3내용/21,904행은 기존 전체 SHA·크기·행 수·규칙 근거와 같아 재사용했다.
나머지19내용은 행 의미 근거 연결 미완료이며 준비된 prefix 후보는 아직 일치 판정이 아니다.

행 adapter174확인, 규칙 차이 fixture5확인, fact 재사용42확인, 최종 정산12,495확인은 exit0이다.
최초 정산은 모든 후대 계약이 같은 열을 지원한다는 assertion에서 exit1(ce3147)이었고, 적용 불가
계약을 명시적으로 제외/기록하도록 수정한 뒤 Ruff와 실제 정산 exit0(60adde)을 확인했다.
제품 코드·서버·원본 변경과 새 전체 백업은 없다. metadata 전체·CSV/fact 교차 참조·최종 delta·
이미지 역방향, R1/R2·R3물리·R5·R6는 미완료다. full_data_gate NOT_EVALUATED/출시 HOLD다.
[행 대조 검토](C:/Users/user/Desktop/SmartFactory/R4ROWS_20261017_431b2e9d/review.md),
정산 SHA256 `48afaaa87a3828843e45b42a327565c34bcb4405d20d67a9bbec256440fda307`.

### 5.72 보존 fact 22내용의 행 근거와 불일치 관측 연결(2026-10-17)

앞 단계에서 남긴 19내용 중 10내용은 보존 누적 파일의 정확한 prefix로 연결했고, 나머지
9내용은 직접 검사했다. 이미 연결한 동일 본문 3내용을 합쳐 22내용 모두에 범위를 명시한 행
검사 근거가 있다. 합계 16,557,590행/8,454,722,699바이트이며 누적 이력의 겹치는 행을 포함한다.
이를 고유 관측 수나 전체 R4 완료로 세지 않는다.

로컬 후보 9파일/8,682,244,488바이트에서 28대응을 비교했다. 실제 session63000 exit0(519ba4),
136.266초,Job active0이다. 관측 3내용/1,357,723행과 이미지 7내용/15,009,674행의 prefix SHA,
바이트 길이,행 수,제목이 일치했다. 전체 EOF/전후 해시와 identity도 대조했다. 이전 manifest21건과
목표 행 경계가 다른 검사이며 같은 참조를 다시 판정한 것이 아니다. 불일치18쌍은 후보 비교 결과다.

관측 prefix는 47열의1.2.0/1.2.1 혼합 이력이다. 원본 규칙의 함수/의존 AST 동일성과 기존
혼합 버전 분류를 재확인했다. prefix 안의 NUL/열 폭 finding은0이다. 이미지 prefix는 기존의
ID/경로/해시 원장 검사 범위만 재사용했으며 실물 이미지 decode나 역방향 참조의 근거는 아니다.

직접 검사한9내용은84,962,450바이트/168,289행이고 실제 session76793 exit0(300573),
20.406초,Job active0이다. 36열 관측117,936행은1.0.0 원래 writer의 불변 조건 재생과
ID/순번/시각 검사 범위다. 54/55열 관측에는 고정 소스의 원래 행 함수를 적용했다. 이미지4내용은
metadata의 capture_root/log_path와 원래 writer 경로 생성 함수를 결합했다. `images`라는
설정 경로는 `spot_images` 고정 규칙만으로 오류로 세지 않았다. 원문은 변경하지 않았다.
적용한 규칙/ID/순번/시각의 finding과 내부 순번 gap은0이다. 실제 배포 commit은 별도 미확정이다.

시험용 이미지4내용의 실제23,707행과, 같은 폴더 metadata의0행/해시 없음 선언은 동시에 남긴다.
경로 설정 대조는 가능하지만 이 metadata snapshot을 실제 fact 전체 종료 상태로 결합하지 못했다.
파일 손실 또는 정상 종료로 단정하지 않는다. 전체 metadata/세대 교차 참조의 후속 대상이다.

이전10행은 logger ID 대신 정확한 SPOT observation key로 원 관측과 연결했다.

- `686939e6-54b1-4b00-b7a7-28ab0d3e15fd:2496`: 원 fact는 timeout/not_received,
  raw값 없음,오류 temperature-upstream-timeout,요청 시간1004.8215389251709ms다.
  CSV5행의 빈값은 이 관측과 맞지만 cached_observation 표기의 불일치는 남는다.
- `43e3d23f-b809-47f7-8c07-ed3ece457aa2:13953`: 원 fact 값498.1은 CSV 관측값과 같다.
  CSV Temperature498.6은 다음 poll13954의 raw값과 같으며5행 모두 해당 다음 poll 종료 뒤에
  기록됐다. 다음 값과 이전 관측 참조의 혼재는 관측 사실이고, 정확한 코드 원인은 미확정이다.

앞뒤2관측씩 총10관측을 문맥으로 보존했다. 이6월29일 timeout을 R1의 원래 timeout 원인 해결로
대체하지 않으며, 당시 설치본 증명·원인 재현·현재 제품 영향·복구값 작성은 하지 않았다.

prefix fixture7확인, 최종 직접 검사 fixture39확인, 결과 정산191확인은 exit0이다. 최초 직접
검사 준비 fixture는 실제 시험 경로를 정상 고정 경로로 가정해 실패(38c9ce)했다. 설정과 원래
writer의 경로 생성으로 대조하도록 보완했다. 첫 reader는 UNC→Z 경로를 두 번 변환해 본문을
읽기 전에 exit1(308786)로 끝났으며, 매핑 일치9확인을 추가한 수정본은 exit0이다. 실패 기록도
보존했다. 제품·서버·원본 변경과 새 전체 백업은 없다.
[fact 검토](C:/Users/user/Desktop/SmartFactory/R4FACT_20261017_ebcdb018/review.md),
정산 SHA256 `157da0ae6d06c076ca0dd20a23a62d87cc067f279b2b0e0e100a931504aab3b0`.
다음은 metadata snapshot/CSV-fact 전체 교차 참조,실제 배포 소스와 원인,최종 delta/이미지 역방향이다.
R1/R2·R3물리·R5·R6도 미완료이며 full_data_gate NOT_EVALUATED/출시 HOLD를 유지한다.

### 5.73 이미지 종료 명세와 CSV 종료 순번 결합(2026-10-17)

5.72에서 미결로 남긴 이미지4내용에는 각각 같은 폴더의 별도
`spot_image_fact_manifest.final.json`이 있었다. metadata가 선언한3개 Git commit의
원래 검증 함수에 명시적인 final-manifest 인자를 전달했다. 실제 전체 fact 해시와
행 수22,407/177/559/564(합계23,707)가 모두 맞고 검증 오류는0이다. 원본 metadata,
final manifest,fact의 전후 해시와 파일 identity를 같은 읽기 잠금 아래 확인했다.
실제 reader exit0(3d7055),55.797초,소유 Job active0이며 강제 종료와 stderr는 없다.

선언 commit의 종료 코드는 CSV closeout/관찰 manifest를 metadata에 갱신하되 이미지
manifest는 별도 final 파일에 쓴다. 따라서 이번4건의 metadata 0행/무해시 값은 시작 snapshot과
종료 명세의 구분으로 설명된다. 선언 소스와 실제 배포 바이트의 동일성을 별도로 입증한 것은
아니다. 시작 metadata를 종료 값으로 덮어쓰지 않았다. 이 판단은 전체 이미지 실물이나
역방향 참조의 통과가 아니다. 이전 단계의 미결 기록은 당시 관측으로 보존했다.

고정 NAS의 metadata41건 중 CSV closeout이 기록된12건도 대조했다. 기존 전체 행 검사에서
확인한 양의 정수/엄격 증가 순번과 `끝-시작+1=행 수`로 완전한 순번열을 복원했다. 보존된
종료 블록과 schema logger ID를 선언7개 commit의 원래 `validate_csv_closeout`에 적용한
결과12건 모두 오류0이다. 해당 CSV1,882,809행의 종료 순번/파일명/logger/종료 표기가 맞는다.
이 단계는 순번 증거 재생이며 원본 CSV 재읽기나 센서 값 재구성이 아니다. 종료 시각과
실제 프로세스 종료·flush·설치본 검증을 대신하지 않는다.

metadata가 있으나 closeout이 없는29건과, 정해진 NAS 목록에서 이름이 대응되지 않은
metadata15건은 별도로 남겼다. 종료 기록이 없다는 사실을 비정상 종료나 파일 손실로
판정하지 않는다. 실제 배포 소스·전체 metadata 의미·CSV/fact 교차 참조는 후속 범위다.

이미지 final/override 차이 fixture12확인, CSV 종료의 정상/잘못된 순번·boolean형·logger·
파일명·finalized·사유 fixture49확인, 통합 정산170확인은 모두 exit0이다. 실제 정산과 Ruff
exit0(bd2085)을 확인했다. 제품·서버·원본 변경과 새 전체 백업은 없다.
[종료 명세 검토](C:/Users/user/Desktop/SmartFactory/R4META_20261017_b44eb3c6/review.md),
정산 SHA256 `7999a0c58d2a79c395d24870997f2a9f8295230927a372c5980daeae571efd05`.
전체 R4와 R1/R2·R3물리·R5·R6는 미완료이며 출시 HOLD를 유지한다.

### 5.74 보존 metadata 계약과 전체 관측 키 연결(2026-10-17)

metadata41건 중37건에 선언 또는 명시된 참고 소스의 정적 계약을 적용했다. 원 계약을 찾지
못한 schema2.0의4건과 고정 NAS 목록에 대응 이름이 없는15건은 미검증으로 남긴다. 원래
validator의 metadata/헤더 구문을 유지하고 제외한 행·fact·파일 검사의 소스 위치를 기록했다.
14개 소스 계약을 사용했으며 실제 설치 바이트와 동일하다는 판정은 하지 않았다.

6월26일11:40 metadata의 설정 snapshot 부재1건은 참고 규칙과의 차이다. 해당 요구가 추가된
commit6e580e의 기록 시각은 같은 날23:32이며, 부모a40169c의 원래 정적 계약에서는 오류0이다.
이는 버전 차이 근거이며 실제 생성 소스의 확정은 아니다. fixture85확인은 변경 검출84건과
이미 없는 필수 블록1건으로 구분했다. 첫 fixture는 이미 없는 블록을 제거한 뒤 새 오류를
요구하여 실패했고 수정본은 exit0이다. 원본을 보완하거나 불일치 기록을 지우지 않았다.

관측 키가 있는 CSV24내용/26경로/2,391,032행(3,246,357,446바이트)을 읽어 정확한 키로
연결했다. 기존 역사 관측6,170,644행의 읽기 전용 색인, 직접 fact5건/144,582행을 사용했다.
처음 남은 양의 키9,613건은 이미 회수한 최근 관측482,570행에서 모두 찾았다. 최근 원본에서
고유 관측7,947건이 해당 CSV42,564행을 설명한다. CSV별 키 집계는 파일 간 중복을 포함한다.

| 구분 | CSV별 키 | CSV 행 |
| --- | ---: | ---: |
| 양의 폴링 순번, 정확한 원 관측 연결 | 490,131 | 2,390,830 |
| 시작 순번0, 아직 요청/수신하지 않은 기록 | 4 | 22 |
| 키 빈칸 | 해당 없음 | 180 |
| 남은 양의 키 미대응 | 0 | 0 |

시작 순번0은 당시 참고 key 생성 함수에서 가능한 값이며 현재 소스의 빈 키 동작과 구분했다.
키 없는 다른 CSV27내용은 관측 참조 열을 갖지 않으므로 이 연결 검사 대상이 아니다. 종료
선언12건은 각 선언이 가리키는 정확한 source/prefix 경계 안에서도 모두 연결됐고, 기록된
link coverage와의 차이는0이다. 알려진 NUL fact2행의 키는 이 CSV 범위에서 참조되지 않았다.
이 결과를 역사 손상 복구나 전체 관측 값 일치로 해석하지 않는다.

행 설정 검사는 실제 snapshot이 있는19경로에 적용하여 새 finding0을 확인했다. 함수에
전달한20경로 중1건은 snapshot이 없어 행 조건을 검증할 수 없었고, 다른6경로는 metadata
또는 원 계약이 없다. 따라서20건 전체의 설정 검증 완료로 표시하지 않는다. 값별 분석 원장을
압축 보존하여 다음 온도·진단 출처 대조에서 전체 CSV를 다시 읽지 않도록 했다.

metadata/주 연결/최근 보완 reader는 각각2.875/507.109/5.953초, exit0, Job active0이다.
키 연결 fixture22확인, 최근 원본 fixture6확인, 최초 정산1,470,907확인과 보완 정산43,092확인은
완료했다. SQLite ATTACH의 URI 설정 누락과 fixture writer 미종료 실패를 별도 보존하고,
읽기 전용 연결과 명시적 close로 수정한 R3를 실제 실행했다. 제품·원본·서버 변경은 없다.
[검토 기록](C:/Users/user/Desktop/SmartFactory/R4CONTRACT_20261017_f60c333d/review.md),
최종 정산 SHA256 `9e77e428c02fd390ded703873a01b5603c522bb3dc693b9f6d84b7a6dcbb0262`.
후속은 보존 값 투영과 원 fact의 값·진단 출처 대조, 이미지 역방향, 남은 metadata/배포 출처와
현재 delta다. 원 R1 timeout/R2 health 실패/R3물리/R5 drop15/R6도 미완료이며 출시 HOLD다.

### 5.75 원 관측 값과 진단 출처의 교차 비교(2026-10-17)

5.74에서 연결한 양의 폴링 참조2,390,830행/490,131CSV별 키를 보존 값 투영으로 대조했다.
원 fact11파일6,116,356행을 읽고 최근 검증 관측의 필드 투영42,564CSV행을 재사용했다.
원본 CSV는 다시 읽지 않았다. 실제 reader124.344초,exit0(344ed5),소유 Job active0이며
강제 종료·stderr는 없다. 새 분석 색인만 만들었으며 원 자료와 기존 색인은 변경하지 않았다.

공통 직접 필드15개와 raw에서 파싱한 관측 온도1개를 모든 대상 행에서 비교했다. poll/service
ID,순번,상태,원 온도·payload hash,오류/HTTP/응답 길이,encoding,요청 시작·종료/소요 시간이다.
응답 길이의 두 열 이름은11개 선언/참고 소스의 원 fact writer 대응식을 확인했다.
spot_service_started_at은 fact 열이 없어 비교하지 못했고,spot_last_response_at도 독립 원
필드가 없어 완료 시각으로 추정하지 않았다. 원 기록의 실제 배포 바이트는 미확정이다.

정확한 문자열 비교에서2,390,761행의 raw 온도 텍스트 차이가 나왔다.11개 선언/참고 commit의
원 `_bounded_csv_text`와 `_escape_csv_text`를 앱 초기화 없이 추출해 원 fact raw에 적용했다.
모든 차이가 해당 writer 변환 결과와 같아 설명되지 않은 값 차이는0행이다. 대표적으로
fact의 `552.3\r\n`은 CSV의 `552.3\n`으로 기록된다. 변환 전 값과 차이 원장을 보존하며,
숫자 허용 오차를 추가하거나 문자열 차이를 지우지 않았다. 실제 생성 코드를 입증한 것은 아니다.

원래 진단-source 함수가 있는17CSV/2,003,221행에 evidence code의 필요한 원 관측 필드와
provenance 규칙을 적용하여 새 불일치0을 확인했다. 옛7CSV/387,609행은 참고 소스에 이 함수가
없어 해당 검사를 수행하지 않았다. 현재 규칙으로 임의 대체하지 않는다. 양의 키 외 시작
순번0의22행과 빈 키180행도 이번 값 비교 범위 밖이다.

fixture113확인(키/record·값/빈값/필드 부재/진단 근거),원 writer fixture88확인,정산980,703확인은
exit0(6c8acc/e7110d/1b8f38)이다. 비교16필드와17CSV 진단의 제한된 결과이며 모든 데이터 품질
통과가 아니다. 기존 `Temperature`와 관측 참조의 불일치10행,역사 NUL손상·미복구 구간의
원인과 복구는 그대로 남긴다. 이 projection에는 주 출력 Temperature가 포함되지 않는다.

[값 대조 검토](C:/Users/user/Desktop/SmartFactory/R4VALUES_20261017_33ab640f/review.md),
정산 SHA256 `cb4e044eb42209f85cdb766093354e5107c04ceeb2dcbcc25a8a5d3a2d8dc965`.
다음은 아직 수행하지 않은 manifest 전체 통계·이미지 역방향·현재 delta,계약/metadata 부재와
실제 배포 출처,기존10행의 원인이다. R1/R2·R3물리·R5·R6와 출시 HOLD는 유지한다.

### 5.76 관측 manifest 전체 집계와 비종료 snapshot 경계(2026-10-17)

고정 metadata의 비어 있지 않은 관측 명세13건을 모두 대조했다. 종료 선언12건과 비종료1건이며,
같은 source/prefix를 공유하는 명세 행 수 합계9,229,135는 중복 누적 범위다. 실제 읽은 원본은
9파일/4,987,561행이다. 선언7개 commit의 원 summarize 함수에서 진단 누적 구문과 최종 계산식을
추출했고, 원 전체 함수의 작은 fixture 실행과91확인으로 일치시켰다. 파일 I/O·SHA·identity
부분은 제외 위치/이유를 기록하고, 기존 전후 해시·읽기 전용 색인·prefix 경계 근거에 결합했다.

수집/결합 상태별 수,진단 필드/누락 수,evidence/provenance 수,전체·고유 관측 수와 순번/누락
집계를 원 규칙대로 계산했다. 옛 전역 순번과 새 service별 순번 규칙을 구별했다. 동일 원본은
한 번 읽고 필요한 prefix 경계에서 집계를 보존했다. CSV는 기존 키 원장으로 연결하여 재읽지
않았다. 실제 reader143.89초,exit0(b3ba66),Job active0이며 강제 종료·stderr는 없다.

종료 명세12건은 재구성한 전체 manifest와 차이가0이다. 이는 당시 명세의 통계/해시/열 계약과
CSV 연결 집계의 일치이며, 원본이 손상되지 않았다는 판정은 아니다. 특히 알려진 NUL 행을
포함한 누적 prefix2개도 당시 해시에 그 바이트가 포함되어 있다. 기존 NUL과 원인은 미해결이다.
write/spool의0 선언은 원 규칙의 요구값과 비교했으며 실제 과거 실패 이력0을 새로 입증하지 않았다.

비종료 `SPOT_IDLE_FIELD_R1` 명세는 관측275,160행의 통계가 맞지만 CSV link_coverage4항목이
다르다. 기록된4값은 모두0이다. 그 prefix에 실제 CSV를 연결하면 키 있는76,575행 중227행만
포함되고76,348행은 범위 밖이다. 원 d7a1b20f 소스의 일반 sidecar 경로는 realtime_rows 없이
집계를 요청하며, 종료 refresh는 CSV rows를 전달한다. 원 runtime method의 격리 메모리
fixture8확인으로 이 차이를 재현했다. 실제 배포 코드 또는 당시 실행 경로를 확정한 것은 아니다.

별도 경계 대조에서 범위 밖15,484키/76,348CSV행은 모두 같은 SHA-bound 역사 원본의 뒤쪽
record275,163–290,876에 있었다. prefix 안에는 key `6374a3b3-08dd-4099-bc95-acda1d11e900:1`
하나가 record275,161에서227CSV행에 연결된다. 후속 참조는 poll3부터15716까지이며 마지막
참조의 완료 시각은2026-10-02T06:14:17.872276Z다. 원본 전체702,095행/SHA와 앞선 값 대조
색인에 연결했다. 키 빈칸13행까지 합해 CSV76,588행을 정산했다. snapshot의 범위 부족을
원 관측 손실로 보고하지 않으며, 전체 CSV 종료 명세나 정상 종료 증거로 승격하지 않는다.

원 함수 fixture91/색인·경계 fixture31/runtime snapshot fixture8확인과 정산98확인은 exit0
(19762a/9613e4/6c6761/6f3bf6)이다. 후속 경계 대조66c50d도 exit0이다. 제품·서버·원본 변경,
복구본과 새 전체 백업은 없다. [집계 검토](C:/Users/user/Desktop/SmartFactory/R4STATS_20261017_89ab12a4/review.md).
정산 SHA256 `a566be25afb86aa426b0c5a17563e7932299d8bb060a8fe0a2fb7454ed5fdbff`,
경계 후속 SHA256 `14bb73935f70993e8030de6ed2c9fee4415d382c0049dddd607dd7fe35041aa8`.
다음은 고정 이미지 manifest/CSV-이미지 및 실물의 양방향 연결,현재 delta와 남은 배포/손상
원인이다. 기존 metadata 부재와 R1/R2·R3물리·R5·R6는 미완료이며 출시 HOLD다.

### 5.77 CSV 이미지 참조·명세 경계·기록 값 대조(2026-10-17)

고정 측정 CSV51종 중 이미지 열이 있는19종/2,105,074행을 대조했다. 이미지4열이 모두 빈
810,956행과 값이 있는1,294,118행을 구별했다. CSV별 ID·경로·service 참조374,477개는 고유
이미지373,000개에 해당한다. 값이 있는 모든 행이 보존 원장의 ID/경로와 일치했고 경로 차이,
service 차이,여러 source에 중복 일치는0이다. 빈 이미지 열을 손실 또는 실패로 분류하지 않았다.

기존 읽기 전용 원장 색인4,385,307행을 재사용하고 별도 시험 원장4종/23,707행을 추가했다.
19CSV에만 필요한 재읽기를 수행하고 이미지4열·시각·관측 키·공정 문맥을 분석 투영에 보존했다.
원본 SHA·identity를 전후 확인했으며 reader301.891초,exit0(e54a44),Job active0이었다.
독립 검산은 투영 전체를 재집계하고 모든 연결을 원 색인/시험 원장에 재대조하여4,001,393확인,
exit0(709a92)으로 마쳤다. Windows 상대 경로의 대소문자는 원 색인과 같이 구분하지 않았다.

이미지 명세23건은 metadata16건(비어 있지 않은12건/초기0행4건)과 별도 final7건이다.
기존 전체/prefix 해시 경계에 참조를 적용했다. 별도 final7건은 해당 CSV의 이미지 참조
133,263행을 모두 포함한다. metadata16건은 참조1,282,921행 중323행만 명세 범위에 들어가며
1,282,598행은 범위 밖이다. 이 참조들도 보존 원장 전체에는 모두 있다. 따라서 metadata에
기록된 이미지 명세의 범위 부족을 원장 전체 부재로 바꾸지 않았다. final 없는 metadata9건과
대응 metadata 없는CSV3종은 이 결과만으로 이미지 정상 종료를 확정하지 않는다.

참조된 원 이미지 기록373,000개를 다시 선택해 관측 키·service·연결 상태·연결 age 네 필드를
CSV1,294,118행과 정확한 문자열로 비교했다. 차이는0이며 수치 허용 오차나 문자열 보정은
적용하지 않았다. 공통 보존 fact4,385,307행/2,247,226,565bytes의 전체 SHA를 확인하고 필요한
원 행만 압축 투영으로 남겼다. 별도4시험 원장은 이미 검증한 투영을 재사용했다. 비교40.609초,
exit0(eb183a),독립 필드 검산2,040,160확인/exit0(a4a3b6),두 Job 모두 active0이었다.

경계/경로 fixture16확인과 필드 차이 fixture7확인은 exit0(7c9291/349733)이다. 분석 도우미
4파일의 Ruff F검사도 exit0(9835a0)이다. 선택된 원 행의 투영은 후속 이미지 실물·관측 연결에
재사용하며 원본 복구본이나 새 전체 백업이 아니다. 제품·서버·원본 변경은 없다.

실제 이미지 바이트/디코드 증거와의 전체 양방향 연결,현재 파일시스템 delta,당시 최신 이미지
선택 및 age 계산 재현은 남아 있다. 기록 값의 일치는 시간 선택 로직이나 실제 배포 바이트의
증명이 아니다. 기존 손상·Temperature 참조10행·R1/R2·R3물리·R5·R6와 출시 HOLD는 유지한다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R4IMAGE_20261017_6b9d3c42/review.md).
ID/경계 summary SHA256 `3af689f872196ba0134bdfd6151cd46f9c6db7693a6f913a920dd9e746441b80`,
기록 필드 summary SHA256 `2d500fae9940e10055cdabf83884a9b43a292326cd025a19e469eb5db1be79fb`.

### 5.78 보존 디코드 근거의 양방향 연결과 시험 이미지 실물 확인(2026-10-17)

기존 서버13일·14일·16일 및 NAS 이미지 증거590,216건을 크기/SHA로 결합했다. 이 수에는
겹치는 사본이 포함된다. 공통 원장4,385,307행,시험4원장23,707행,옛31열 원장54,112행의
전체4,463,126기록에 역방향 대조했다. CSV 고유 참조373,000개 중130,867개는 기존 전체
디코드 근거와 연결됐고 형식·해상도·프레임 차이는0이었다. NAS 검증 압축의 일반 멤버
1,031,166건에서는 나머지 참조의 추가 바이트가 발견되지 않았다. 손상 압축84/431의 미확인
부분과 선택 밖 파일까지 부재가 증명된 것은 아니다. 초기 결합은54.875초/exit0(e30992),
독립 검산2,718,082확인/39.171초/exit0(050a71)이었고 두 Job의 종료 후 active는0이다.

역방향에서 서버 사본의 원장 미연결 이미지는 기존에 알려진16개뿐이었다. NAS에는0바이트
실패3개,내용/파일명 capture가 모두 연결되지 않는 정상 디코드264개,내용만 연결되고 다른
파일명으로 보관된4개가 있다. 이들은 NAS의 기타 이미지도 포함하므로 설비 이미지 손실이나
orphan으로 일괄 분류하지 않는다. 기존16개와 원래 drop15의 발생 원인도 같은 것으로 단정하지 않는다.

원 final manifest의 시험 이미지 경로 네 곳을 승인된 SSH로 확인하니 서버에 남아 있었다.
host `DESKTOP-CIIT7LK`,계정 user,관리자 권한을 확인한 뒤 정확한 네 폴더만 읽었다.
`U76fbb38e`22,407개,`Udc7d3bfb`177개,`U1ac3f0e4`559개,`Ud5580ed0`564개 등 총23,707개/
236,755,252bytes가 원 fact의 크기·SHA·JPEG·512×288·1프레임과 모두 일치했다. 폴더마다
17바이트 `trial-write-probe` 파일1개도 별도로 기록했다. 이미지 누락·추가·디코드 실패는
이 네 폴더/원장 범위에서0이다. 운영 이미지 전체의 현재 증분 검증을 뜻하지 않는다.

첫 큰 폴더 전송은180.062초 제한에 걸려exit1로 끝났다. 233,297,920바이트 부분 수신과 실패
기록을 보존하고, 완전한21,521개 payload를 검증한 뒤 부족한886개만64개 이하14묶음으로
읽었다. 작은 세 폴더1,300개도 읽었다. 보완 실행68.578초/exit0(16a50b),Job active0이며
서버에 해당 tar 프로세스가 남지 않은 것을97acc3/exit0으로 확인했다. 첫 실패는 PASS로
재작성하지 않는다. 서버 원본 변경·압축 해제·새 전체 백업은 하지 않았다.

새 실물 검증은 CSV 참조22,653개/77,468행을 추가로 뒷받침한다. 최종 실물 근거 연결은
153,520개/535,376CSV행이며,219,480개/758,742CSV행은 선택한 근거에서 실물 미확인이다.
이전 원장 연결은 전부 있으므로 실물 근거 부재를 CSV 참조 오류 또는 데이터 복구 완료로
바꾸지 않는다. 별도 정산118,612확인과 도우미5파일 Ruff F검사 exit0(8eb13b),경계 fixture
9+8+3확인을 마쳤다. 서버 최종 화면15:14 KST에서 Smart Factory Running/전면 표시와
적용된 제품60180·금형37을 관찰했다. 작업 정보는 수정하지 않았다.

추가2023–2025 온도·PLC 사본은 없다는 사용자 답변을 해당 범위에만 적용한다. 기존 손상,
실제 당시 배포 바이트·이미지 선택/age 계산·현재 전체 증분·R1/R2 원인·R3 물리·R5·R6는
남아 있으며 출시 HOLD다. [상세 검토](C:/Users/user/Desktop/SmartFactory/R4BYTES_20261017_7a69d201/review.md).
실물 summary SHA256 `6a3ff84bfa1eb5a98356d04d35e1d67b73db56be97fddb4f6217275e2ae9d7ba`,
정산 SHA256 `4859c852a755de12d7756fc6f175501d3e142e92459dc89385c213de048ef5e1`.

### 5.79 이미지 연결 시간 계약과 지연 기록의 재현 한계(2026-10-17)

선택 이미지373,000개/CSV1,294,118행에 대해 선언 또는 명시된 참고 commit9개,원 소스27개를
고정했다. 핵심 age 계산·snapshot 읽기·CSV 연결 함수의 AST는 각각1종이고,enqueue 함수의
2종 차이는 종료 시 enqueue 차단이다. 실제 당시 배포 바이트를 확인한 결과는 아니다.

age 원 계약은 `(link_checked_at - completed_at_epoch) * 1000`이다. 촬영 이후 시계를 읽고
그 다음 lock을 얻어 최신 공개 snapshot을 복사한다. private epoch를 우선하며 ISO 시각은
대체 입력이다. CSV는 명시 입력이 있으면 이를 쓰고,없으면 관측 키가 같은 최근 기록 이미지를
쓴다. 따라서 전체 이력에서 수학적으로 최근접인 이미지를 검색한다는 계약으로 해석하지 않는다.

원 순수 함수 fixture44확인(exit0/5f59e7)을 완료했다. 경계값과 같은 age는 fresh,초과하면
stale,음수는 clock_anomaly다. link_checked_at·원 private epoch의 정밀도·snapshot lock 순서와
실제 stale 기준은 저장돼 있지 않다. 대응 metadata16건에도 검색한 시계/refresh/link-stale
설정이 없어 현재 기본값을 소급 적용하지 않았다. 시계 읽기 후 snapshot이 바뀌는 fixture는
가능한 경쟁 조건의 예일 뿐 실제 발생 또는 시계 역행을 입증하지 않는다.

전체 원 행의 capture ID 시각/해시 접두부,service:poll 연결 키,유한한3자리 age와 상태 부호
검사에서 새 불일치0이다. fresh372,968개/CSV1,291,934행,stale32개/CSV2,184행이다.
모든 spot_image_age_ms는0.000이며 연결 age와는 다른 필드다. 촬영 시각이 연결 관측 완료
시각보다 이른 행과 음수 연결 age는0이다. 기록 age에서 추정한 확인 시각과 촬영 시각의 차이는
-1~10,930µs이며 이는 저장 정밀도·반올림을 포함한 추정값으로 정확한 당시 시각 재현이 아니다.

stale32개는29개 관측 키/6CSV에 연결된다. 원 행과 CSV의 첫/마지막 논리 record를 보존했다.
UTC 날짜별 이미지/CSV행은7월7일26/109,9월9일2/894,9월16일1/48,9월20일1/1,036,
10월4일1/58,10월6일1/39다. 최대 연결 age는220,738.214ms다. 긴2개 관측 그룹은poll1,
짧은3개는 한국 시각 자정 직후 CSV 문맥이다. 시작·파일 교체와의 시각상 연관만 관찰됐으며
지연 원인은 미확정이다. 기록된 stale를 참조 파손 또는 실제 장비 오류로 바꾸지 않는다.

reader15.813초/exit0(8cd440),독립 검산1,865,010확인/8.078초/exit0(a99375),원 CSV 문맥
해시 대조7확인/exit0(056147)을 마쳤다. 두 Job의 정리 후 active0,stderr0이고 강제 종료는
없었다. 두 분석 도우미의 Ruff F검사는 exit0다. 설계5.48의 원 계약·기록 불변조건·독립
집계·누락 입력 명시는 충족했다. 정확한 과거 age/선택 재현은 입력 부재로 검증 불가이며,
새 입력이 발견되지 않는 한 같은 전체 투영을 반복해도 이 한계가 해소되지 않는다.

[상세 검토](C:/Users/user/Desktop/SmartFactory/R4TIME_20261017_30690235/review.md).
시간 summary SHA256 `c341c6a69cf5346d6c878a8d86ffb3d4810188162b952ab51a9c5126e28caab7`,
독립 summary SHA256 `a8dd03aa1a633f5fa3d7ffa023985198ad50a7e133eae770315687d8b0eadea7`.
제품·서버·원본 변경과 새 전체 백업은 없다. 추가2023–2025 온도·PLC 보관본 없음은 유지한다.
실물 근거 미확인219,480이미지,현재 전체 증분,기존 손상과Temperature10행,R1/R2 원인,
R3 물리,R5,R6는 남아 있다. 전체 R4 미완료/full_data_gate NOT_EVALUATED/출시 HOLD다.

### 5.80 현재 운영 파일 목록과 이전 종료 기준의 증분(2026-10-17)

이전5.79는 PROGRESS였다. 실제 SSH 대상DESKTOP-CIIT7LK/user/관리자 권한을 다시 확인하고
현재 config.ini의 logpath와 imagecapturepath를 읽었다. 저장 경로는기존logs/test_data와
spot_images이며 이미지 보존7일이다. config SHA는bb1b8326…으로 기존 재시작 근거와 같다.
처음 사전 확인은 SSH exit0였지만 PowerShell의 모듈 준비 progress CLIXML을stderr에 남겨
로컬의 stderr0검사가exit1로 끝났다. 원 출력은 보존하고3개progress만 있음을 XML로 분류했다.
오류를 숨기거나 서버 실행을 다시 반복하지 않았다. 이후 읽기 명령은progress출력을 끄고 실행했다.

SmartFactoryLogger 루트 전체를 링크 미추적·120초/600,000항목/5,000디렉터리 한도로 읽었다.
현재319,310파일/221디렉터리/15,566,121,254bytes가목록에 있다. 이는55.979초 동안 순차로
관찰한 metadata이고,동시 시점의 내용 snapshot은 아니다. 서버 종료 시각은06:41:13.0764931Z다.
읽기 핸들 접근 실패는0이다. 디렉터리 조회와 실제 handle 길이가 다른6개 파일은 두 값을
보존했다. 쓰기 중 CSV가0바이트로 표시된 초기 관찰도 실제 handle329,685,605bytes와 헤더를
읽어 빈 파일로 오판하지 않았다. 최종 목록에서 같은 CSV handle길이는330,329,569bytes다.

이전 닫힌O4ff65a11 목록의 같은 운영 루트290,596파일과 비교한354,168경로는 다음과 같다.
metadata동일255,719,변경19,추가63,572,현재부재34,858이다. 이전 목록의Electron프로필 루트는
이번 운영 데이터 루트 범위에 포함하지 않았다. 동일 metadata를 현재 내용 SHA 동일성으로
승격하지 않았다. 비이미지 추가17/변경19개에는CSV4종과metadata4종,진단로그,fact,설정,
종료영수증 등이 있다. 이미 검증된 canary파일과 이후 생성분을 구분해야 한다.

현재 이미지318,443개 중254,888개는 이전 목록과metadata가같고63,555개는추가됐다.
이전 decode원장300,546개를 경로·크기로 대조하면 추가분10,800개는이미 검증된canary
근거가 있다. 현재 이미지265,688개에 이전 실물 근거가 있고,52,755개/511,098,674bytes는
기존 근거가 없다. 후속 선택 목록을 저장했으므로 전체 이미지를 중복 회수하지 않는다.
이 분류는 현재 파일의 새 SHA 검산을 대신하지 않으며 관찰 종료 이후 추가분은 별도다.

현재부재34,858개는모두2026/10/09폴더이며 이전 크기/SHA/디코드 근거가 남아 있다.
원mtime은10월9일08:13:07.830872~23:01:25.937599UTC이고 관찰 시점7일 초과/관리 경로
형식에 모두 해당한다. 실제 후보0732c8e소스는매시간mtime<cutoff인관리이미지를정리하지만
개별 삭제 기록을 남기지 않는다. 날짜·원mtime·정책의 일관성은 확인했으나 실제 삭제 주체/
원인을 입증하지 못했으므로 정상삭제 확정 또는 역사손상 해소로 바꾸지 않는다.

metadata수집59.578초/exit0(333a94),비교5.719초/exit0(36d7c4),독립 정산585,926확인/
4.391초/exit0(95ef16)을 마쳤다. 세Job정리후active0,stderr0,강제종료0이다. 비교fixture9확인,
Python도우미3파일Ruff F검사,PowerShell구문검사가exit0다. 설계5.49의경계·개별상태·증분
분류는충족했다. 현재SHA/전체decode와일관된snapshot·종료delta의내용검증은미완료다.

승인된SSH읽기6회 후 서버에 해당목록수집프로세스0을 확인했다(2d9a99/exit0).
backend14012/생성14:36:54.945803UTC(10월16일)는같고 앱·설정·원본을변경하지 않았다.
15:46KST화면에서Smart Factory Running/전면,적용제품60180·금형37을확인했으며작업값을
수정하지 않았다. [상세 검토](C:/Users/user/Desktop/SmartFactory/R4DELTA_20261017_39c3fa46/review.md).
정산SHA256 `6ccb7c4856410b6ac17c57168e2a15600ed3acefc468e31993ee96392c4c9d18`.
추가2023–2025온도·PLC사본없음,불필요한전체백업생성없음,기존손상·Temperature10행·
과거219,480참조이미지실물근거공백은유지한다. R1/R2,R3물리,R5,R6와출시HOLD도유지한다.

### 5.81 현재 증분 이미지52,755개 회수·전체 디코딩과 독립 검산

이전5.80의고정 선택 목록(15:40~15:41 KST)을 재사용했다. 해당52,755개/511,098,674bytes
모두 수신SHA와 파일명12자리SHA 접두부, 선택크기, 초단위mtime, JPEG512×288/1frame 전체
디코딩을 확인했다. 각 불일치와 decode실패는0이다. 10월16일30,820개/298,960,406bytes,
10월17일21,935개/212,138,268bytes다. 경로·크기와 NTFS tick을 저장하지만 tar초단위mtime
일치를 전체tick/원자적snapshot/최신fact SHA 일치로 확대하지 않는다.

첫3개 시험은성공했다. stdin목록6000개의첫대형전송은109.594초뒤SSH255로끊겼다.
원stderr는`Timeout, server 192.168.0.7 not responding.`이며56,350,720bytes 부분tar를
그대로 보존했다. 로컬Job active0 후에도서버tar10480이남아 있어부모18904/명령/생성시각
06:55:05.0890400Z와실제handle을대조하여이진단프로세스만종료했다. 끊긴원인은미확정이다.
부분tar에서완전한5519payload만검증했다. 다음파일은offset56345600/size9686으로끝부분이
부족하여성공집합에서제외했다. 부족한파일도이후누락집합으로정상회수했다.

작은argv묶음으로추가1680개를검증한후,도우미의exclusive-create save함수에같은progress.json을
반복지정한오류로workerexit1이었다. 원helper/요약을고치지않고새진행기록을고유이름으로작성했다.
완료7202개를제외한45553개는23개입력목록으로고정했다. 새서버Desktop/SmartFactory 실행폴더에
목록23파일만전달하여전후모든SHA를확인했다. 서버목록파일을읽는23회전송과decode가629.516초/
exit0으로끝났다(2bd518). 전체백업·운영데이터수정·설치·앱재시작은없다. 서버에는진단목록23개가남는다.

46개수신tar의전체SHA와완전한선택payload를별도reader로다시읽었다. 선택52755집합·기록·실물과
디코딩근거의독립대조738633확인,60.484초/exit0(e722b9),소유Job잔류0이다. 검산은같은바이트와
decode근거를결합하며PIL디코딩을다시실행했다고보고하지않는다. 이전373000참조이미지ID와겹침은0,
과거219480개실물근거공백은그대로다. 성공한모든payload는한번만새로받았고,중단된부분payload는
보존한실패증거와구분했다. 최초capture/r2중단은최종데이터대조성공으로지우지않았다.

확인도우미5파일의각최종변경상태Ruff F검사와경로/중복/링크/손상fixture11확인은exit0이었다.
PowerShell최종확인구문검사와실제서버확인도exit0이다. 서버최종tar0,backend14012/부모17996/
생성2026-10-16T14:36:54.945Z동일,새목록폴더와표본파일의운영사용자FullAccess를확인했다.
16:14 KST화면에서Smart Factory Running/전면과적용60180·37을확인했다. 작업값은변경하지않았다.

설계5.50의고정집합·부분실패보존·누락분만회수·전체decode·독립검산을충족했다. 현재목록318443개
중기존근거265688개와새근거52755개가있으나,이는동일시점에전체파일을새로SHA검사한뜻이아니다.
최신image/observation fact증분과233657/20261017 CSV의일관된완전행경계·양방향연결은다음단계다.
추가2023–2025온도·PLC사본없음,기존손상/R1/R2/R3물리/R5/R6미완료와출시HOLD는유지한다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R4DIMG_20261017_1cb25b5a/review.md).
검산summary SHA256 `e805a477f812e30dfa532d9b3f97002fc793b2380331099aff0efd0a0d3912c7`.

### 5.82 고정 CSV/fact 증분 전체 행과 이미지 52,755개 연결

설계5.51의 고정 6개 범위 432,599,007바이트를 회수했다. 서버 native64/admin/host/user,
helper·request 잠금 SHA, 원본 생성 시각, 기존 prefix와 선택 범위의 전후 SHA를 확인했고
수신 SHA가 일치한다. 기존 종료 image 2,247,226,565바이트/observation 560,718,654바이트는
다시 전송하지 않았다. 회수 중 append를 허용하되 원래 정한 끝바이트만 읽었으며 동시 시점
전체 snapshot이라고 주장하지 않는다. 새 전체 백업·설치·앱 재시작·원본 수정은 없다.

233657 CSV 5,838행과 당일 CSV 243,106행, 총248,944행에 field 수/NUL/순서 오류가 없다.
image 증분52,508행과 observation 증분57,796행도 완전 record이고 identity 중복이 없다.
원 4개 CSV/fact 범위의 끝 조각은0바이트다. 관측 key가 있는248,932행/57,056고유 key 모두
fact에 연결되며16개 raw 필드3,733,980개 문자열 동일·248,932개 수치 표현 동등이다.
초기12행은 key가 없다. raw validity에 따른 관측 온도도 일치하지만 파생Temperature 의미는
이번 raw echo 결과로 PASS 처리하지 않는다.

이미지 참조157,252행/50,054고유 ID 모두 fact의ID·경로·service와 일치하고 검증된 실물에
연결된다. 빈image hint91,692행(초기12/poll success91,680)은 별도 집계했으며 파일 소실로
판정하지 않았다. 빈 hint와 age/status의 당시 규칙 적용은 다음 의미 검토 범위다.
선택 이미지52,755개 중 이전종료fact244/현재증분52,508개가 바로 일치했다. 남은3개는
처음 fact 경계 이후06:40:19.294741/20.298820/21.649983UTC의 이미지였다. 원 QA의
미연결3건을 보존하고 각각8,192바이트의 fact 보충을 한 번만 읽어 정확한3개 ID·전체SHA·
크기·차원·관측key를 확인했다. 선택집합 확대 없이 경계 차이를 해소했다.

보충 image16행/8,157바이트 뒤35바이트와 observation6행/7,177바이트 뒤1,015바이트는
불완전 원바이트로 따로 보존했다. 후자는 quoted CSV record 안에서 끝나므로 물리적 LF를
논리적 행 끝으로 취급하지 않았다. 별도 reader의 전체 행수·ref집합·fact원문·SQLite·실물
근거 검산732,347확인/62.750초/exit0(bfc146), 주 QA108.312초/exit0(fbdde9)이다.
보충51.187초/exit0(86e080), 원 전송137.250초/exit0(9f9daa)이고 smoke 포함5개 Job의
최종active0/stderr0/강제종료0을 확인했다. Python4도우미 각 최종상태Ruff F,CSV fixture19,
PowerShell range fixture6/구문 검사는 통과했다. 제품 수정이 없어 제품 테스트/빌드/설치와
동일15/120분 시험은 반복하지 않았다.

metadata의 image manifest는 각각 이전종료4,385,307행/SHA와 추가1,245행까지의
4,386,552행/2,247,856,901바이트 SHA에 일치한다. 실행 중 시점의 prefix로 분류했다.
닫힌 metadata의 observation closeout은 finalized=false/writes_drained=false이므로
최종 runtime 종료 확인이 아니다. 서버 사후확인02ecbf/exit0에서 원격helper0,진단6파일
SHA동일,운영사용자FullAccess,backend14012/부모17996/생성14:36:54.945803UTC(10월16일)
동일이다. 16:44KST 화면에서 Running/전면,60180·39/적용16:40:22를 확인했다.
앞서 사용자의‘생산 중 아님’ 답변과 이후 화면 관찰을 시점별로 기록했으며 값을 변경하지 않았다.

고정 범위 구조·raw echo·참조/실물 연결은 완료했다. 파생온도와image hint 의미,나머지변경파일,
최종종료일관성,과거219,480실물근거공백·Temperature10차이·기존손상은 남는다.
R1/R2/R3물리/R5/R6·출시HOLD/미서명방침과 추가2023–2025사본없음도 유지한다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R4CUR_20261017_0378ef72/review.md).
독립summary SHA256 `6c11532373a84fbcba0d55fbb4bf914c3d7798c263119f2d2604ada3010fed33`.

### 5.83 현재248,944행의 설치 소스 규칙과 이미지 hint 분류

직전5.82의 고정 CSV/metadata와 image 인덱스를 재사용했다. 빌드0732c8e의 validator와
의존 소스5개를 Git object에서 추출하고,원 호출식에 당시 metadata를 적용했다.
3000ms freshness/15000ms cache TTL/temperature-operational-v6 조건이다. 설치 commit의
shadow enum,SPOT sequence,온도출처,sentinel,operational,hardening,poll duration의7개
순수 행 규칙을 전체248,944행에 적용해 위반0을 확인했다. 기록된 값의 의미 일관성을
검사한 결과이며 미기록 런타임 입력의 전수 재생으로 확대하지 않는다.

valid230,848/under_range17,821/stale263/startup_pending12행이며 각각의 품질·빈값 조건이
일치한다. 모든valid행은 current_observation이다. under_range의 cause는unknown,
diagnostics_excluded_fact_only만7,514행/phase_setup_candidate도함께10,307행이다.
소프트웨어 규칙 일치가 실제 장비 물리 경계를 증명하지 않는다.

채워진image hint157,252행은 image fact의 관측key·status·age 문자열까지 일치한다.
빈91,692행은 관측key없음12,고정범위에해당key의image fact없음22,887,관련capture가
CSV보다늦음27,053,이전capture가있지만게시·lock순서미기록41,740으로분류했다.
당시 `_spot_image_link_for_row`는 명시적값 우선/최신fact의관측key일치 때만 fallback한다.
capture와publish시각을같다고가정하지않았고,41,740행의미기록순서를정상또는유실로판정하지않았다.

주검사46.516초/exit0(318d23),독립1,310,307확인·38.375초/exit0(5e2dee),두Job정리후
active0/stderr0/강제종료0이다. 독립검산은 소스5개와Git object,전체CSV와행분류journal의
일대일대응,ref/echo,시간분류와분포를확인했다. 불변7규칙을다시실행한것은아니다.
fixture20확인(원본·변이/chunk/온도단독변이/UTC)과두도우미최종Ruff F도exit0이다.
준비중사용하지않는import·metadata helper정의복원누락·복합변이fixture의경로문제는
실제전수검사전수정했다. 제품수정·서버접속·새수집·전체백업이없어제품검사/빌드/설치/
동일15/120분시험은반복하지않았다.

설계5.52의입력고정/원소스조건/전체규칙/fixture/힌트분류/무변경6항목을6/6충족했다.
전체R4/R1~R6진도나출시PASS는아니다. 기존고정비이미지36개중내용결합6개를제외한30개를
기존receipt우선대조15/로그범위·회전11/volatile상태4개로다음범위를정리했다.
나머지내용·최종종료일관성·과거손상/실물근거공백과R1/R2/R3물리/R5/R6는남는다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R4SEM_20261017_f52a6689/review.md).
독립summary SHA256 `f335e6570f9107913c58b0803a284ce9c163afc2614e0e748dee357b01116fd7`.


### 5.84 잔여30개 비이미지 경로의 원본 결합과 과거 세대 한계

같은 R4DELTA 고정 범위의30개를 대조했다. 기존 사본15개·75,365,599바이트는 실제 원본의
길이/생성·수정tick/전후SHA와 일치해 재복사하지 않았다. 설정 전후 값 차이는 승인 시각과
fingerprint 두 항목이며, 이전 attestation에서 네 필드를 썼다는 기록과 구분했다.
기존195021 CSV53,338행 완료QA를 재사용하고193310 CSV2,439행은 당시0732c8e의7개
행 규칙과sequence를 새 확인해 위반0건이다. 초기CSV의관측·이미지fact echo는추가검사대상이다.

append로그6개는 기존prefix의전후SHA를검증하고4,461,151바이트를회수했다. 모두UTF-8엄격
해석/NUL0/끝줄바꿈이며,comm1,189JSON행과오류journal457JSON행도해석됐다. 후자의457행은
모두signalpc parse_error,2개journal세대,12:41:00.672Z(16일)~04:47:42.783Z(17일)이다.
형식일관성이운영오류0이나R1/R2의원인입증은아니다. 종료begin/final2쌍과sidecar4개도일치한다.

회전로그5개는당시경로세대와다르다. 이전.1과같은metadata가현재.4에남아있어1회보충조회했으나,
08:06:47Z와08:11:09Z사이에handle ID까지바뀌어내용0바이트/미확보로종결했다. 나머지4개도
처음관찰한회전집합에같은metadata가없었다. 상태4개는현재표본을확보하고lock14012/backend를
결합했다. 작업정보/런타임상태/state3개는당시목록과달라과거snapshot으로사용하지않는다.
이는삭제원인이나생산원본유실확정이아니며,원래고정끝을확대해무한추적하지않는다.

두서버읽기Job exit0/잔류0/강제종료0,독립23,705확인/1.141초/exit0(52ede2),행규칙위반0이다.
PowerShell fixture9(88774a),분류·metadata fixture12(bc9e33),최종Ruff F도exit0이다.
검산r1/r2/r3는회전별명·교체시점·쓰기필드와실제값차이의잘못된가정을고쳐r4에서통과했고
실패자료를보존했다. 제품코드/원본/설정/설치/전체백업변경은없어제품검사와동일15/120분시험은반복하지않았다.
17:13KST화면은전면Running/60180·39/적용16:40:22이며기존사용자답변과후속관찰을구분했다.

설계5.53의고정범위/기존증거재사용/prefix증분/회전분류/현재표본/독립검산6항목은6/6이다.
전체R4는NOT_PASSED,출시HOLD다. 이전6+이번15+로그6개의내용범위결합과현재상태4개/회전5개
미확보를따로기록했다. [상세 검토](C:/Users/user/Desktop/SmartFactory/R4AUX_20261017_c81f86d2/review.md).
검산summary SHA256 `ca7adc8bfa6741e541bc177891a655127cce271f261d6fa74db1d852b458f71d`.

### 5.85 초기 193310 실행의 관측·이미지 원바이트 연결

5.84에서 남긴 초기 CSV 2,439행의 fact 연결을 완료했다. 관측 키가 있는 2,428행은
555개 관측과 연결되며, 16개 raw echo 38,848값 중 36,420개는 문자열까지 같고
2,428개는 온도 또는 소요시간의 유한 Decimal 값이 같다. 관측 온도도 일치한다.
이미지 힌트 581행은 183개 이미지의 ID·경로·관측 키·status·age와 모두 일치한다.
초기 서비스의 전체 관측 563개와 이미지 244개를 누적 원본의 record/byte offset으로
분리했고, 이미지 244개의 기존 실물 SHA·크기·512×288 JPEG decode 증거와 연결했다.
이미지 실물 합계는 2,234,610바이트다. 새 복사나 반복 디코딩은 하지 않았다.

CSV의 빈 이미지 힌트 1,858행은 관측 키 없음 11, 같은 관측의 이미지 없음 1,404,
관련 이미지가 CSV보다 늦게 캡처됨 137, 이전 캡처는 있으나 게시 순서가 미기록인 306행이다.
마지막 306행을 정상 또는 유실이라고 판정하지 않는다. 이는 사후 기록 연결이며
당시 publish/lock 시각이나 실시간 선택 과정을 재생한 결과가 아니다.

metadata의 관측 manifest는 469,923행/545,885,456바이트 종료 prefix와 일치한다.
이미지 manifest는 4,374,263행/2,241,600,730바이트 시작 prefix와 일치한다. 뒤의
244개 이미지 fact는 record 4,374,264~4,374,507에 연속으로 존재한다. metadata의
written=0과 종료 receipt의 written=244를 서로 다른 시점으로 구분했다. 설치 소스
0732c8e는 CSV 종료 시 관측 manifest를 갱신하고 이미지 final manifest는 별도로 쓴다.
현재 보유한 누적 image final manifest는 이후 canary 종료본이다. 초기 실행 당시의
별도 image final manifest를 확보했다고 주장하지 않는다.

최초 연결 r1은 두 전체 fact 스캔을 마친 뒤 이미지 ID의 대소문자 정규화 차이로
exit1이 됐다. 실패 자료를 보존하고, r2에서 고정 해시의 완료된 스캔/추출을 재사용했다.
원 힌트 문자열 비교는 그대로 유지했다. r2는 0.547초/exit0, 독립 검산은 54,869확인/
2.750초/exit0(7102dd)이다. 독립 검산은 원본 전체·prefix SHA, 선택 원바이트를 별도
CSV reader로 읽은 결과, 2,439행 journal과 244개 proof offset, Git 소스까지 대조했다.
세 실행의 소유 프로세스 잔류·stderr·강제 종료는 모두 0이다. 최종 연결 fixture 28확인과
독립 parser/숫자 fixture 11확인, 도우미 Ruff F는 통과했다.

설계5.54의 입력/전체 참조/prefix/설치 소스/독립 검산/무변경 6조건은 6/6이다.
전체 R4나 출시 완료율이 아니다. 서버 접속·원본 변경·설정 변경·제품 수정·백업·설치는
없었고, 제품 검사와 동일 15/120분 시험은 반복하지 않았다. 사용자의 생산 중 아님 답변은
사용자 보고로 기록하며, 과거 화면 관찰이나 현재 서버 값 변경으로 대신하지 않는다.
이제 초기 2,439행·canary 53,338행·고정 현재 248,944행의 범위별 검증 근거를 통합한다.
과거 손상·이미지 실물 공백·회전 로그 미확보·최종 종료 검증 및 R1/R2/R3/R5/R6는 남는다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R4EARLY_20261017_384cf12a/review.md).
독립 summary SHA256 `d4f036402be9ba6e9a7238e3be005e8c4f785f09ac05ca53df8f043152435162`.

### 5.86 고정 데이터 범위 통합과 기존 Ready 구간의 인터럽트 분리

R4 단계 기록21개 및 기존 처리 원장의 참조11개를 실제 고정 SHA와 대조했다(4e1ed5).
새 `coverage-sources.json`은32개 원문을 연결한다. NAS CSV157,139경로의 구조 근거,
측정51내용/4,325,141행과 지속 차이10행, 참조 이미지373,000개의 실물 근거153,520개/
공백219,480개, 현재 이미지52,755개, 초기/canary/현재 CSV와 비이미지36개 정산을
데이터 범위 보고서의 최신 표로 통합했다. 사본·시점·참조가 겹치므로 합산하지 않는다.
구조 분류와 원인 분류·물리 의미·현재 전체 원바이트 불변성·최종 종료 검증을 구분했다.
32개 기록의 대조는 원본 전체 재검사가 아니다. R4의 원인 미분류0/후보 손상·설명 없는
누락0 조건은 전체 범위에서 충족되지 않아 NOT_PASSED다.

R2는 CTRACE의 같은221.0337ms 요청과 두 Ready 구간만 추가 분석했다. 원시/변환 CPU
이벤트187,613개를 대조하고 DPC/ISR97,080개의 시작·종료/CPU/routine을 tracerpt와 연결했다.
tracerpt의 `-rts`는 header의 raw 시각만 지정하므로 `InitialTime`은 별도의 FILETIME 값이다.
헤더 QPC5983793582073/StartTime134366588988869680/frequency10,000,000으로 변환하면
97,080개가 정확히 일치한다. BootTime을 기준으로 쓰거나 시간 오차 허용 폭을 추가하지 않았다.
1,337,420개 XML 이벤트를 읽고 기존 processing error15005(15,756개)/111(88,169개)은 보존했다.
선택 필드의 성공을 전체 ETW 해독 품질 PASS로 확대하지 않는다.

| 수집기 Ready 구간 | 두 CPU 점유 합계(ms) | 기록된 DPC/ISR 합집합(ms) | 제외 후 점유(ms) | 양쪽 전환 경계 우선순위가 수집기보다 높은 점유(ms) |
|---|---:|---:|---:|---:|
|64.4168ms|128.8336|2.4731|126.3605|122.4561|
|127.5472ms|255.0944|2.9207|252.1737|245.1747|

두 CPU 합계이며 벽시계 지연과 직접 합산하지 않는다. nested ISR/DPC는 합집합으로 빼고
독립 endpoint sweep과 각 CPU의 빈틈 없는 residency 분할로 정산했다. 그 밖의 Explorer
점유는 각각74.5604/105.3001ms이며 Smart Factory, backend, DWM 등도 함께 실행됐다.
수집기 전환 시 우선순위는8이다. 양쪽 경계값은 연속 우선순위·affinity 증거가 아니고,
process 이름은 trace rundown 매핑이다. 기록된 인터럽트 처리만으로 두 긴 대기 구간이
설명되지는 않으며 경쟁 실행 단서가 강화됐다. Explorer 단독 원인·변경 효과는 미확정이다.

초기 분석 r1/r2/r3의 ISR 길이·InitialTime clock·header 보조 필드 가정 실패는 보존했다.
r4는48.250초/실제exit0(602651), 소유Job 잔류0/stderr0/강제 종료0이다. 최종109개
interval/변환 fixture 및 Ruff F가 통과했다. 제품·서버 설정·우선순위·성능 기준·백업은
변경하지 않아 제품 테스트/빌드/설치/동일15·120분 시험은 수행하지 않았다.
설계5.55의 고정 근거 통합/판정 분리/원시·독립 clock 대조/중첩 정산/한계 보존/무변경을
수행했다. 전체 PDCA 완료율이 아니다. 원래120분의219.9407/302.9669ms FAIL, 최초R1,
R3물리/R4최종 종료·과거 공백/R5drop15/R6clean 미서명 패키지·승격은 그대로 남는다.

정의 근거: [Microsoft 우선순위](https://learn.microsoft.com/en-us/windows/win32/procthread/scheduling-priorities),
[tracerpt](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/tracerpt),
[Microsoft PerfView의 ISR/DPC 계산](https://github.com/microsoft/perfview/blob/main/src/TraceEvent/Parsers/KernelTraceEventParser.cs).
[분석 결과](C:/Users/user/Desktop/SmartFactory/R4R2_20261017_9b37d6c1/review.md).
interrupt summary SHA256 `fd85dcec5448b9d78253e5f1b6f2b1143114e3484169d8818870fd6357e05a2e`.

### 5.87 기존 221ms 요청의 경쟁 스택과 탐색기 캐시 작업

R2STACK의442CPU표본/398고유스택을 같은 CTRACE의 원시 StackWalk와 대조했다.
291단일+139kernel/user 전체 주소가 일치한다. 12개DPC/ISR은 kernel prefix만 일치하고
변환된 나머지 프레임은 미확인이다. 일반 프로세스428표본은 모두 전체 스택이 일치한다.
raw flags를 별도로 읽어14비프로세스 표본을 프로세스 작업량에서 제외했다. 두 Ready구간의
384표본 중380개는 CSwitch와 일치하고4개는8.8–13.1µs 뒤 다음 switch의 새thread와 일치한다.
그 차이의 원인은 미확정이다. Explorer/주요 앱 표본에는 이 스케줄 불일치가 없다.

ETLX의 정확한 PDB 식별값으로 Microsoft symbol을 조회했다.8개PDB의 GUID·info age·DBI age를
독립 MSF7 reader로 검증하고398스택/10,600프레임의 주소·모듈 불변,5,604함수명 연결을 확인했다.
첫 검산의 info age 동등 조건 실패는 보존했다. Microsoft `OpenValidate4`에 따른 실제 조건은
GUID일치/info age>=image age/DBI age=image age다. 실제 info age2–6/DBI age1/trace age1이다.
이것은 검증을 생략한 동일 이름 PDB 사용이 아니다. 원 trace ImageID/RSDS 대조는 후속이다.

두 번째127.5472ms Ready구간에서 Explorer thread15572의 일반표본106개 모두에
`CAppResolverCacheBuilder::ScanFoldersAndCreateNewCache`/`_UpdateRoot`가 있다.
105개는 Darwin 바로가기 등록/캐시 경로,100개는 `CDarwinAd::CheckInstalled`,99개는
`MsiQueryFeatureStateW`를 포함한다(같은 표본의 동일 함수는1회). 첫64.4168ms구간은
Explorer74표본 중캐시 작성33/MSI조회24, 별도thread9316의32표본에 ChangeNotify 처리다.
함수명은 앱·바로가기 캐시 갱신 및 MSI 기능 상태 조회를 가리킨다. 설치 실행·사용자의
파일 복사·캐시 갱신 trigger·단일 근본 원인·개입 효과는 확정되지 않았다.
Explorer표본priority10/11, 앱17632표본11/12/13은 raw sample byte와 일치한다.
연속priority/affinity나 두CPU 표본 수를 벽시계 지연으로 확대하지 않는다.

실제 결과: 스택r2 38.062초/exit0(ff0516), 분류2,212확인/exit0(2590cd),
locked restore/build/lookup exit0(6892a5), PDB/주소 대조exit0(c50a39).
최종fixture16+14, Ruff F 통과. 초기 stack strict 비교와 PDB info-age 가정 실패를 보존했다.
설계5.56의 입력/주소대조/스케줄/한계/종료/symbol계약6조건을 이 범위에서 수행했다.
서버·제품·원본·우선순위·백업 변경은 없다. 기존 제품검사/15·120분을 반복하지 않았다.
원래 R1/R2실패, R3물리/R4근거공백/R5drop15/R6clean 미서명 최종QA·승격은 남는다.

[검토 기록](C:/Users/user/Desktop/SmartFactory/R2STACK_20261017_d31e8a64/review.md).
PDB 검산 summary SHA256 `049c0fce98f4b7e2d30b540bf952f8bc709df1c17ad7fed8f3c6a2bc18312635`.
근거: [Microsoft PDB OpenValidate4](https://github.com/microsoft/microsoft-pdb/blob/master/PDB/dbi/pdb.cpp),
[MsiQueryFeatureStateW](https://learn.microsoft.com/en-us/windows/win32/api/msi/nf-msi-msiqueryfeaturestatew).

### 5.88 원 모듈 식별과 Shell 검사 구간 대조

R2TRIGGER에서8개PDB를 원 ImageID/RSDS/ImageLoad666개 모듈·프로세스 기록과 연결했다.
trace의1,337,420이벤트/70종과 profile에는 파일·레지스트리·Shell 알림이 없다.
승인된 SSH로 과거06:14–06:22KST의 보존 Application/System/Shell-Core 로그만 조회했다.
Application/System은0건, Shell-Core는168건이며 로그 보존 완전성은 미확인이다.
서버 provider 정의에 따른 AppResolver 검사84쌍: PID9804/thread15572에81쌍, thread704에3쌍.
지속 시간178.9271–262.5609ms/중앙값234.6948ms다.

기존121요청 중221.0337ms 요청 한 건만 검사와 겹친다. 나머지120건은
중앙값11.0238ms/최대107.2514ms다. record57942/57943의242.1505ms 검사와
trace QPC 기준 겹침은195.4738ms, 별도 요청UTC+지속시간 기준은194.3694ms다.
전체121개의 시작 clock 차이0.0088–5.7577ms는 오차의 보장 상한이 아니다.
같은 PID/thread와 스택이 연결되지만 단일 원인·알림 계기·개입 효과는 아직 미확정이다.

fixture15/독립대조3,543/Python Ruff F/PS parser PASS(exit0), 추출r2 52.203초/exit0.
첫 추출의 BinaryEventData 누락, 초기 분석의 빈 PDB 이름·단일thread 가정 실패를 보존했다.
최종 서버 화면18:30KST에서 Smart Factory 전면 Running을 확인했고 작업 입력은 변경하지 않았다.
다음은 진단 파일 생성과 반복 스캔의 관계를 작은 격리 실험으로 확인한다. 현재는 가설이다.
원래120분 실패/R1/R3물리/R4미확보/R5drop15/R6최종clean 미서명QA·승격은 남는다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R2TRIGGER_20261017_8bbd59e6/review.md).

### 5.89 개발 PC 파일 생성 조건에서 AppResolver 재현

R2WRITE의 두 비교에서 무쓰기·새 파일 생성·기존 파일 추가를 각각30초씩 총4회 수행했다.
첫 비교의 생성 구간 간격120초를 두 번째에서160초로 바꾸어 주기와의 우연한 일치를 점검했다.
모든 생성 구간(4/4)에서 검사1회씩, 추가/무쓰기에서는각0/4였다. 동일4KiB/250ms 기록으로
생성480회와 추가480회의 각각 기록량1,966,080바이트를 실제 파일과 확인했다.
검사는8.7004~10.4344ms, Explorer 두 프로세스 CPU 합계는 생성11.906초/추가2.219초/
무쓰기0.078초다. CPU 전후 측정은 요청 지연이나 검사 함수 자체 시간과 구분한다.

각 시험3,445검사와 독립 .NET 로그 재조회8이벤트 ID/시각/PID/TID 일치, Ruff/PS 구문,
smoke/본 시험 모두exit0. 두 본 시험의 소유 Job 잔류0, stderr0이다.
개발 PC에서 가설을 지지하는 재현이며 서버의 직접 원인·개입 효과는 미확정이다.
서버는 이번 단계에 접근하지 않았고 원래120분FAIL 및 R1~R6 잔여조건을 유지한다.
다음은 승인된 보호 묶음으로 서버의 같은 세 조건을 짧게 비교하는 것이다. 제품 설정·
원본·200ms 기준은 그대로 두며, 결과에 따라 진단 출력 방식의 변경 범위를 결정한다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R2WRITE_20261017_c73e52b8/review.md).

### 5.90 서버 파일 쓰기 비교: 반복 검사 미재현

R2SERVER의 두 순서에서 새 파일 생성·기존 파일 추가·무쓰기를 각각30초씩 총4회 비교했다.
두 쓰기 조건은 각각480회/1,966,080바이트이며 실제 파일 내용이 일치했다. 구간 중
AppResolver 검사는 세 조건 모두0/4였다. 준비 직후20초 대기에는 실행마다1회씩
183.4112/183.6275ms 검사가 관찰됐고, 독립 .NET reader의4이벤트가 시각/PID/TID까지 일치했다.
개발 PC 생성4/4 결과를 서버 원인으로 일반화할 수 없다. 서버 Explorer CPU 합계는
생성13.734초/추가5.125초/무쓰기0.031초지만 요청 지연이나 함수 자체 시간은 아니다.

동결 두 smoke/소유 실행16조건, 서버 두 실행·회수·6,922검사 모두exit0이다.
서버 두 결과 각257파일의 공유/개발 사본1,028개 크기·SHA검사가 일치했다.
전후 main17996/backend14012 세대와 승인 Low Signal OFF 프로파일이 유지됐고 잔류0이다.
최초 서명정책 차단과 회수 명령 길이 초과를 보존했고, 프로세스 단위 실행 옵션·압축 전송으로
해결했다. 영구 실행 정책·제품·설정·원본·백업은 바꾸지 않았다. 마지막19:25KST 앱 전면
Running을 확인했다. 최신 사용자 '생산 중 아님' 답변과 움직이는 UI 관측을 구분하며 부하 통제를
주장하지 않는다. 원 진단의 실제 파일/경로·준비 활동 차이를 더 확인해야 한다.
설계5.59의 제한된 비교는 수행했지만 R1~R6 잔여조건과 원래120분FAIL/출시HOLD는 유지한다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R2SERVER_20261017_f391c2a8/review.md).

### 5.91 fsync 비교와 원 진단 쓰기 시각 대조

원 진단 소스는 파일마다 flush+os.fsync를 호출했고 앞선 비교는 flush만 사용했다. 설계5.60의
새 동결 worker로 서버 두 순서를 수행했다. flush-only와 fsync는 각각480회·1,966,080바이트,
무쓰기를 포함한 조건별4구간에서 반복 AppResolver 검사는 모두0회였다. 준비 대기에만
238.5122/216.9438ms 검사 각1회가 있었고 독립.NET 재조회4이벤트가 일치했다.
Explorer CPU 합계는 flush14.000초/fsync14.266초/무쓰기0.078초, 쓰기 중앙값은1.426/2.028ms,
최대37.013/42.741ms다. HTTP 지연·원인 확정·fsync 제거 근거로 해석하지 않는다.

원2,005개 쓰기 파일과 시각은 manifest 검산 및17,371조건을 통과했다. 저장 구간243.347803초
안에 검색78회, 앞2회/뒤4회가 있으며52회가 쓰기와 겹쳤다. 121개 probe 기준 검색 시작은
HTTP구간1/후처리1/probe밖82회다. 고빈도 쓰기의 시각 근접은 인과를 증명하지 않는다.
시각 불확도와 로그 보존 완전성은 미확정이다.

동결 smoke2회 exit0·잔류0, 변경 없는 native16조건 증거 재사용, 서버2회 exit0·잔류0이다.
전후 main17996/backend14012 세대와 승인 OFF 프로파일이 일치했다. 결과 각495파일을
공유·개발 PC에 회수하여1,980개 파일 크기/SHA 및 분석8,836조건을 검산했다.
19:53KST 앱 전면 Running을 확인했다. 작업 정보60180/39는 UI 관찰로만 기록했고 최신
‘생산 중 아님’ 사용자 보고와 구분했다. 제품·원본·설정·백업은 바꾸지 않았다.
설계5.60의 제한된 비교는 완료했지만 원120분FAIL과 R1~R6 잔여조건·출시HOLD는 유지한다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R2SYNC_20261017_6205ca92/review.md).

### 5.92 보존 실행 문맥의 호출자·시간 범위 한계

설계5.61에 따라 고정 XML1,337,420이벤트에서 Process/Thread 문맥을 추출했다.
대상 ReadyThread885/CSwitch76,603/전체 스레드 생애3,033의80,521건이 독립 native
decoder와 QPC/CPU/opcode/version/payload 및 중복 수까지 일치했다. TID15572/704는
종료 시점 rundown에서 PID9804이며 보존 구간의 시작·종료 이벤트는 없었다.

ReadyThread885건 모두 호출자 PID/TID가0xFFFFFFFF이고 원 프로파일에는 ReadyThread
스택·FileIO·Registry가 없다. 같은 CPU의 실행 문맥을 원인 프로세스로 해석하지 않는다.
Flag1(DPC)21건, 문서에서 의미가 확인되지 않은Flag8 366건은 원 숫자를 보존했다.
프로세스 시작7건(dllhost5/wpr1/conhost1)도 검색을 깨운 호출자라는 근거는 없다.

두 CPU의 공통 실행 전환 보존 경계는 약46.185655초다. Shell 검색84회 중14회만 이
범위에 있고70회는 밖이다. header의 약247초를 보존 기록의 전체 범위로 확대하지 않는다.
14회 중13회에 이전 ReadyThread가 있지만 간격0.0087~4070.5279ms는 인과 근거가 아니다.
221.0337ms 관찰과 겹친 검색의 미세 순서는 미확정 시계 오차 때문에 확정하지 않는다.

초기 추출의 필터 삽입 실패(exit1)를 보존하고 R2에서 수정했다. R2 exit0/잔류0,
분석83,803행 중심 assertion/별도 검토25조건과 Ruff F는 통과했다. 이는 제품 QA가 아니다.
서버·제품·원본·백업·작업번호를 변경하지 않았다. 누락된 호출자 스택을 기존 자료에서
반복 추론하지 않고, 다음에는 ReadyThread 스택의 짧은 로컬 수집·결합·비용·정리를 검증한다.
원120분FAIL·R1~R6 미완료·출시HOLD·미서명 운영 방침은 유지한다.
[상세 검토](C:/Users/user/Desktop/SmartFactory/R2WAKE_20261017_8f99b4ab/review.md).

### 5.93 ReadyThread 스택 시험 준비 및 독립 실행 미완료

설계5.62의 새 묶음은 R5 제어기·native helper를 원 SHA로 확인한 뒤 생성했다. Loader와
ReadyThread 스택을 추가하고 Memory64KiB×1024버퍼를 사용한다. 일반 권한 fixture의
정상8신호는0.8530808초에 완료됐고, 첫 신호 누락은1.3118212초에 실패를 검출해 수신
스레드를 종료했다. 변경 제어기의 모의 lifecycle14조건과 process11묶음, WPR 프로파일
목록/상세조회, native PS5.1 구문, Ruff F가 통과했다. 실제 ETW 수집은 이 검사 범위 밖이다.

자동 관리자 실행은 성공적으로 권한을 얻었지만 상위 Job 때문에 추적 전 exit1로 중단됐다.
기존 독립 프로세스 API도 자식이 Job 안에 남아 거부·정리됐다. 감시자 독립 조건을 유지한다.
사용자가 Windows 탐색기에서 실행할 고정 shortcut `START_READY_TRACE_R2.lnk`를 준비했고
인수947자·읽기 대조와 Codex Job 내 거부를 확인했다. 사용자 독립 실행을 요청한 상태다.

설계의 실제 스택 연결·보존 시간·수집 비용 검증은 미완료이며 준비 검사를 현장 QA로
승격하지 않는다. 서버·제품·장비 설정·운영 작업번호·백업에는 변화가 없다.
원120분FAIL·R1~R6 미완료·출시HOLD·미서명 운영 정책을 유지한다.
[검증 준비와 실행 경로](C:/Users/user/Desktop/SmartFactory/R2READY_20261017_9562c578/review.md).

### 5.94 추적 해독기의 스택 미수집 대조 및 기존 출력 회귀

실제 독립 추적이 시작되기 전, 설계5.62의 해독기를 별도 개발 PC 폴더에서 준비했다.
고정 TraceEvent4.0.0과 잠금 파일의15개 패키지를 보존 로컬 원본에서 새 경로로 복원했고,
복원된 패키지 내용 해시·원 압축 해시를 대조했다. 빌드는 경고/오류0, exit0이다.
새 분기는 x64 StackWalk의 원 QPC/PID/TID/payload를 보존하며 스택 참조는 미해결로 내보낸다.

스택을 수집하지 않은 R5 Normal ETL에서 선택428,946행을 읽었고 스택/스택 참조는0이었다.
R4 Normal 회귀153,793행의 출력27,248,856바이트와 SHA256은 기존 독립 XML 대조를 통과한
출력과 정확히 같았다. 두 실행 exit0·소유 프로세스 잔류0·stderr0이며, 전체582,739행의
원 payload 길이/식별자/QPC/CPU 검사와 패키지/파일 검산, Ruff F가 통과했다.
행별 반복 assertion2,331,052개를 서로 다른 시험2,331,052개로 표현하지 않는다.

최초 오프라인 복원 경로 오류, raw archive 해시와 서명 패키지 contentHash 혼동,
첫 wrapper의 인수 결합 오류를 보존하고 수정한 실행으로 확인했다. 새 추적의 실제 스택
해독·8회 신호 연결·보존 범위·비용은 미검증이며, 위 음성/회귀 대조로 통과 처리하지 않는다.
Windows 탐색기 shortcut의 독립 실행은 아직 시작 기록이 없다. 사용자 최신 생산 보고는
'생산 중 아님'으로 유지하며 작업번호·서버·제품·원본·백업을 변경하지 않았다.
원120분FAIL·R1~R6 잔여조건·출시HOLD를 유지한다.
[해독기 검증과 남은 단계](C:/Users/user/Desktop/SmartFactory/R2READY_DECODE_20261017_d0523b5e/review.md).

### 5.95 Explorer 독립 실행 및 실제8회 신호·스택 연결 확인

사용자 권한 승인 후 기존 Explorer의 Shell dispatch에서 실행한 읽기 프로브가 일반 권한/
x64/Job밖 실행과 종료를 확인했다. 같은 경로로 기존 고정 launcher를 실행해 관리자 PID52844,
제어기49040,감시자50988이 완료됐다. 실제 추적은1회이며 launcher/제어기/감시자 exit0,
WPR5명령 exit0·소유 잔류0,종료 뒤 해당 instance 미수집을 확인했다. 새 권한 서비스나
예약 작업을 만들지 않았고 앞선 자동 실행 실패 기록은 그대로 보존했다.

32,768,000바이트 ETL과 결과·fixture를 console summary 해시에 결합했다. TraceEvent와
tracerpt의 전체326,640이벤트 중 선택195,197건(CSwitch72,217/Ready43,220/Stack72,113/
Thread7,647)의 원 QPC·CPU·opcode·version·payload·식별자가 중복 수까지 일치했다.
XML의 schema 오류 envelope15005/15,271건 및111/64,121건은 보존했고, 선택한 원 payload의
일치와 전체 ETW schema 의미 검증을 구분했다. header의 lost event/buffer는0이다.

fixture PID49040의 발신TID30856→수신TID41976 신호8회 모두 SetEvent 전후 QPC 구간에
유일한 ReadyThread가 있었으며, 같은 event QPC/PID/TID의 커널4·사용자3프레임과 연결됐다.
두 신호의 사용자 조각은 커널 조각과 다른 CPU에서 출력됐다. CPU를 결합키에 강제하면 이
두 조각을 놓치므로 원 CPU는 유지하면서 event QPC/PID/TID로 대조한다. 실제 fixture 시간은
0.851762초,준비→수신 간격은0.0079~0.021ms이며 서버 HTTP 지연으로 해석하지 않는다.

첫 XML wrapper는 기존60초 명령 한도에120초를 전달해 실행 전에 거부됐다. 원 실패를 보존하고
새 R2경로에서60초로 실행해11.074초/exit0/잔류0을 확인했다. 원 추적을 재실행하지 않았다.
실제 해독·독립 대조·Ruff F는exit0이다. 동일조건 무추적 대조가 없어 수집 비용은 미검증이고,
기호 해석·서버 호출 원인·최종 성능QA도 미완료다. 다음은 비교 가능한 로컬 조건으로 추적
비용을 검증한 뒤 승인된 제한 서버 진단에 이 수집 방법을 적용하는 것이다.
원120분FAIL·R1~R6 잔여조건·출시HOLD·미서명 방침은 유지한다. 서버·제품·작업번호·백업은
변경하지 않았다. 독립 실행 대기는 해소됐으며 전체 목표는 active다.
[실제 실행과 대조 근거](C:/Users/user/Desktop/SmartFactory/R2EXPLORER_20261017_c73ed3ea/review.md).

### 5.96 ReadyThread 스택 OFF/ON 로컬 비용 비교

같은8신호 fixture·스케줄/Loader 키워드·Memory64KiB×1024버퍼에서 스택 태그와 대응 해시만
달리한 OFF→ON→ON→OFF4회가 완료됐다. 관리자 launcher/suite/제어기와 WPR20명령 exit0,
소유 잔류0과 모든 해당 instance 종료를 확인했다. PID·생성시각15세대도 모두 종료됐다.
첫 launcher 사본의 인코딩 손상과 시작 기록 부재를 보존하고 새 R2 launcher에서 완료했다.

신호 작업 평균은 OFF855.807ms/ON855.157ms였다. 첫 신호는 각각666.2/510.5µs와498.5/488.9µs,
나머지 조건별14신호의 중앙값은21.4/14.9µs,최대137.7/166.7µs다. ETL평균은21.0/26.125MiB,
저장평균19.001/19.165초였다. OFF에도 스케줄 추적이 있으며 무추적 대조가 아니다.
시스템 busy 비율은 순서대로27.91/13.18/13.78/21.50%로 배경 부하가 달라 정확한 CPU 비용은
분리하지 못했다. CPU 차분15.625/31.25/15.625/15.625ms와 private bytes 변화는 시험 프로세스
범위이며 시스템 추적 버퍼 비용으로 해석하지 않는다.

네 decoder의 lost event보고는0,OFF 스택0,ON 스택58,078/38,696건이다.32신호의 ReadyThread,
ON16신호의 발신자 커널/사용자 스택 연결을 확인했다. 해독기의 이전 독립 검증을 재사용했으며
이번4개 ETL 전체를 tracerpt로 다시 대조하거나 buffer-loss header를 독립 확인한 것은 아니다.
fixture 정상/누락 검사·프로파일/해시 검사·실제 수집·해독·분석·정리 확인은exit0이다.

로컬 짧은 수집/정리 검증은 완료됐으므로 다음은 승인된 제한 서버 진단 준비다. 신규 스택 추적의
HTTP 값은 기존 성능QA와 직접 혼합하지 않는다. 서버 원인과 원120분FAIL·R1~R6·출시HOLD는
여전히 미해결이며 같은4회 시험이나 동일120분QA를 자동 반복하지 않는다. 제품·서버·백업 변경은 없다.
[관찰값·한계·검토 예](C:/Users/user/Desktop/SmartFactory/R2COST_20261017_dbf5002b/review.md).


### 5.97 ReadyThread 스택 현장1회 수집 및 독립 원문 대조

도우미 commit c7c8db5에서 별도 ReadyThread 동시 요청 계약과 한도 있는 System 이벤트 조회를
추가했다. 단위76건/native entry9·trace11묶음/frozen17조건 및 고정 소스93파일 빌드를 검증했다.
잘못된 입력의 기대 exit1과 검증 도구 exit0을 구분한다. 제품 설치본은 재빌드하지 않았다.
15파일을 서버 로컬에 전달·검산한 뒤 승인된 SSH에서900초 진단1회를 실행했다.

health450건은 모두 HTTP200,최대124.2006ms/중앙8.1806ms,
200ms초과0건이다. data150건/image3600건 최대는
73.6604/135.5453ms였다. 각 채널 누락·미설명 슬롯과 기록 폐기는0이고,
동시 요청 종료 조건도 없었다. System 조회는COMPLETE/0건이며 제한 조회 결과로
시스템 전체 장애 부재를 주장하지 않는다. 수집과 종료·WPR5명령 exit0/소유 잔류0이다.

SSH launcher pin으로 회수8,041파일/156,732,679바이트를 검산했다.
ETL 76,283,904바이트의 전체800,159이벤트 중 선택
725,991건은 TraceEvent와 tracerpt에서 원 payload·QPC·CPU·식별자·중복 수까지
같았다. StackWalk277,372건,header lost event/buffer0/0,
미해결 스택 참조0이다. XML 오류 envelope와 전체 의미 검증 미완료는 보존한다.
두 CPU 공통 관찰 경계는18.765686초이며 health
8/450건의 경계가 안에 있다. 연속성이나 전체15분
보존으로 해석하지 않는다. 실제 서버 호출자 결합·기호 해석·지연 원인은 미검증이다.

XML 해독은exit0이었으나 결과 출력 wrapper는CP949 문자 오류로exit1이었다. UTF-8로
출력만 수정해 저장 로그 재표시exit0을 확인했고, 원 로그·문자 치환 흔적을 보존했다.
해독과 서버 수집은 재실행하지 않았다.

앱은Running을 유지했고 최종 화면60180/39를 확인했다. 작업자 입력 관찰과 마지막 사용자
'생산 중 아님' 보고를 구분한다. 설치·재시작·작업정보/설정 변경·전체 백업은 없었다.
다음은 회수본의 보존 범위와 호출자 스택 연결 분석이다. 이번 무이상 구간으로 원120분FAIL을
덮어쓰거나 동일QA를 자동 반복하지 않는다. R1~R6·출시HOLD와 미서명 운영 방침을 유지한다.
[실행·해시·대조·검토 체크리스트](C:/Users/user/Desktop/SmartFactory/R2FIELD_20261017_91c0af6d/review.md).

### 5.98 보존된8요청의 스케줄·ReadyThread 호출자 연결

앞선 실제 수집/원문 대조는 PROGRESS이며 새 서버 실행 없이 회수본을 분석했다.
450건의 본문·헤더·native 시각을 재검산했고 최대 124.2006ms인 요청438은 스케줄 보존 범위
밖임을 확인했다. 포함된 요청442~449의 8건은 최대 36.4551ms다. 두 CPU의 CSwitch 연속성과
대상 TID 7개의 세대/상충 실행 조건을 검사하여 collector/loop/worker 24구간을 연결했다.

ReadyThread 569건 모두 유일한 원 QPC와 하나의 caller PID/TID 및 커널/사용자 스택에 연결됐다.
모두 backend14012이며 528건의 caller TID는17460이다. Python 스레드 이름/함수는 미확인이다.
중복 Ready 시각·스택 누락·상이한 caller PID의 3가지 음성 조건은 거부됐다. 선택 기록725,991건의
기존 독립 바이트 대조를 재사용하고 이번 입력 해시를 전후 검산했다.

예: 요청443 collector의 가장 긴 비실행 19.3711ms는 switch-out 상태5이며 Ready→재실행은0.0177ms다.
요청445에는 상태1의 12.7488ms 구간도 있다. 정상 8요청의 차이를 원120분 실패 원인으로 확대하지 않는다.
같은 XML의 주소127개가 모듈15개의 범위에 각각 들어가는 후보를 얻었고, 그중51주소는 python312.dll
범위다. 처음 미분류한 KernelBase 메타데이터1건은 별도로 분류하고 원 결과를 보존했다.
Image 원 바이트의 별도 해독 대조·기호·Python 호출 프레임은 미확인으로 남긴다.

분석·모듈 후보 추출·메타데이터 분류는 exit0/오류 출력0이며 서버·제품·설정·백업 변경이 없다.
다음은 동일 설치본의 모듈 식별·Loader 원문 대조로 후보의 실제 호출 경로를 확인하는 단계다.
원120분 FAIL·R1~R6·출시 HOLD·미서명 방침을 유지한다.
[분석 근거와 확인 예](C:/Users/user/Desktop/SmartFactory/R2JOIN_20261017_061ce9db/review.md).

### 5.99 모듈70,722이벤트 대조 및 설치본6파일 식별

같은 ETL을 고정 TraceEvent4.0.0 의존성15개로 만든 별도 해독기로 읽었다. 전체800,159건 중
Image/DbgID70,722건의 GUID·opcode·version·QPC·CPU·payload·중복 수가 Windows XML과
일치했다. Image13,831건은 XML의 모든 필드를 재조립했고, 나머지56,891건은 XML 원 바이트를
대조했다. 누락/초과0이며 이전 범위 후보에 사용한 Loader286기록도 일치한다.

15모듈 모두 유일한 ImageID 및 RSDS 기록에 연결됐다. python312.dll, _asyncio.pyd,
_socket.pyd, _overlapped.pyd, select.pyd, _queue.pyd의6파일은 설치 당시 manifest 및
회수된 진단 입력의 SHA256과 일치하고, PE size/checksum/timestamp와 RSDS GUID/age/name도
일치했다. 대상127주소 중63주소가 이6파일 범위에 있다. 나머지9개 OS 모듈의 파일 바이트는
대조하지 않았다. 12모듈의 Loader timestamp0은 미제공으로 보존하고 ImageID 시각을 사용했다.

별도 pefile 파서로6파일의 헤더/RSDS를 재대조했다. 크기·시각·checksum·GUID·age·name 변경6조건,
잘못된 ETL 해시·기존 출력 경로2조건을 거부했고 원 출력은 보존됐다. 복원·빌드·해독·최종 대조·
모듈 연결·검증은 exit0이다. 초기 대조의 raw 부재와 초기 연결의 timestamp0 처리 실패는 각각
exit1 기록과 해당 소스를 보존했으며, 수정한 분석만 다시 실행했다. 서버 추적은 반복하지 않았다.

함수 기호/Python 프레임과 지연 원인은 여전히 미확정이다. 종료 시 모듈 목록은 전체 과거 적재
수명을 입증하지 않고, 가장 느린124.2006ms 요청은 보존 범위 밖이다. 다음은 같은 GUID/age의
기호가 확보되는 범위에서 호출 주소를 해석하고, 정상8요청 분석의 추가 실익을 판단하는 단계다.
원120분 FAIL·R1~R6·출시HOLD·미서명 운영 방침을 유지한다. 서버·제품·설정·작업번호·백업 변경은 없다.
[대조 범위·검증·사용 예](C:/Users/user/Desktop/SmartFactory/R2IMAGE_20261017_7c460a12/review.md).

### 5.100 공식 Python PDB6개와 원 호출 주소63개 연결

Python3.12.6 amd64의 공식 core_pdb/lib_pdb MSI에서 필요한 PDB6개만 추출했다. MSI 실행은
없었다. 모든 GUID/info age/DBI age가 설치본·추적의 RSDS와 같았고, 별도 MSF/DBI 파서와
DbgHelp 적재 정보로 교차 확인했다. 로컬 exact-symbol 조회에서63주소 모두 크기가 있는
함수 범위에 들어갔으며 함수 이름은51종이다. 실제 PDB 경로·해시와 해제/정리도 확인했다.

ReadyThread569건의14,863프레임을 원 순서대로 대조했다. 고유127주소 중63주소를 해석했고
나머지64주소는 미해석으로 보존했다. TID17460의528건에서 파일 상태 조회 os_stat/posix_do_stat
518건, ScandirIterator_iternext10건, GIL 해제 PyEval_SaveThread/drop_gil527건,
복귀 PyEval_RestoreThread/take_gil1건이 확인됐다. 이는 스택 포함 횟수이며 전체 호출 수나
CPU 비중이 아니다. 공식 소스의 조건변수 신호·파일 열거 경로와 의미가 맞지만, Python 앱
호출 프레임·파일 경로·스레드 역할은 미확인이다. 제품의 시간별 이미지 보존 정리 함수는
정적 조사 후보일 뿐 해당 TID와 연결하지 않았다.

추출·기호 조회·연결·검증·소스 검토 exit0이며 잘못된 주소 연결4조건을 거부했다. 최종 Ruff F와
git diff --check도 exit0이다. 제품 코드/설치본은 바꾸지 않아 제품 시험·빌드를 반복하지 않았다.
새 서버 추적·설정 변경·작업정보 변경·백업은 없고 새 운영 화면 관찰도 없다.

이번 정상8요청의 최대는36.4551ms이고 전체 진단 최대124.2006ms 요청은 여전히 보존 범위 밖이다.
반면 이전 지연 당시 CPU 샘플43개에 동일 PDB 식별자의 모듈이 있고30개는 collector 비실행
구간과 겹친다. 이는 다음 분석 후보이며 해당 기록의 원 모듈 대조와 기호 적용은 아직 하지 않았다.
이 후보를 먼저 확인하여 정상 캡처를 반복하지 않는다. 기존120분 FAIL·R1~R6·출시HOLD와
미서명 방침을 유지한다. [조회·집계·검증·사용 예](C:/Users/user/Desktop/SmartFactory/R2SYMBOL_20261017_91ed0c67/review.md).

### 5.101 실제221.0337ms 지연 당시 Python native 함수 확인

새 서버 수집 없이 기존 CTRACE의43개 CPU 샘플을 분석했다.7개 PID/모듈 조합의 ImageID·RSDS
원 바이트 및 Loader 필드가 별도 TraceEvent 메타데이터와 일치한다. 공식 PDB의 GUID/age와
참조 PE size/timestamp/checksum도 같았다. 과거 도우미 프로세스의 파일 바이트를 새로 회수한
것은 아니며, 종료 시 rundown만으로 전체 적재 수명을 입증하지 않는다.

PID/모듈/주소206조합 중205개는 실제 적재 PDB의 함수 범위 안이었다. 나머지1개는 DbgHelp가
이름을 반환했지만 displacement가 함수 크기를 벗어나 미해석으로 유지했다.43샘플/1,261프레임이
원본과 순서대로 같고 독립 StackWalk 조각과도 일치했다. DPC/ISR 플래그가 없는 프로세스 샘플이며
30개는 기존64.4168/127.5472ms collector Ready 비실행 구간의 스케줄과 일치했다.

백엔드 TID5412의19샘플에서 통신·import/객체 처리와 GC1샘플을 확인했다. TID812의10샘플은
이벤트 루프/JSON 관련 호출을, TID17288의1샘플은 CSV 쓰기를 포함한다. 실제 health worker
TID16664 구간의5샘플에는 dict·stat·정규식·경로 조회·파일 읽기가 보였다. 모두 native 함수의
관찰이며 Python 업무 함수나 파일명은 확인되지 않았다. collector는 별도 프로세스이므로
백엔드 GC1샘플을191.964ms Ready 대기의 직접 GIL 원인으로 주장하지 않는다. GC 지속시간도 미확인이다.

초기 준비는 ImageID/RSDS version0을 잘못 가정해 exit1로 중단됐다. 실제 version2를 확인하여
수정한 준비·조회·분석·검증은 exit0이고 원 실패 소스/로그를 보존했다. 최종 검증·Ruff F·diff 검사도
exit0이다. 서버·제품·설정·작업정보·백업 변경은 없다. 변경 없는 제품 빌드와15/120분 시험은 반복하지 않았다.
미사용 import 제거 후 검증을 반복할 때 기존 출력 파일 보호로 exit1이 발생했다. 원 결과는 보존하고
새 출력 이름을 받도록 수정한 최종 검증은 exit0이다. 이 실패의 소스·로그도 함께 보존했다.

다음은 앱 프레임을 읽을 외부 프로파일러의 로컬 검증이다. py-spy 문서의 Windows 외부 메모리
읽기와 nonblocking 방식을 검토했으나 도구는 현재 설치되어 있지 않고 실행 적합성은 미검증이다.
비정지 읽기의 불완전 샘플 가능성을 보존한다. 기존 서버 fresh-file/fsync 비교의 미재현 결과는
재사용하며 같은 조건을 반복하지 않는다. 원120분 FAIL·R1~R6·출시HOLD와 미서명 방침을 유지한다.
[원 호출·검증·다음 조건](C:/Users/user/Desktop/SmartFactory/OUTSYM_20261017_27ceba41/review.md).

### 5.102 Python 프레임 읽기·frozen 호환·소유 프로세스 정리 검증

공식 PyPI의 py-spy0.4.2 Windows amd64 wheel을 배포 SHA256으로 확인하고 실행 파일과 라이선스만
추출했다. 전역 설치는 없다. 실제 버전과 dump/record 옵션을 읽고 Python3.12.6 x64 일반 시험의
비정지 dump10회에서 알려진3스레드의 native ID·이름·함수 순서·줄 범위를30회 대조했다.
지역변수는 모두 null이며 누락 스레드·잘못된 ID·누락 함수·지역변수 추가4조건은 거부했다.
정상 종료 후 핸들을 보존한 대상 조회는 기대한 exit1과 빈 stdout이었다.

동일 시험 소스를 PyInstaller6.17.0 onedir 실행 파일로 묶었다. 포함된 python312.dll은 후보
설치본의 DLL과 해시가 같았다. 추가3회/9스레드 대조가 성공했고 대상은 정상 종료했다.
이는 최소 시험 프로그램의 호환 확인이며 실제 서버 앱 전체 프레임의 완전성을 보증하지 않는다.

기존 CollectorJob 바이트를 그대로 복사한 로컬 보호 실행에서 실제 dump 정상 종료,0.7초
시간 제한,1MiB 출력 상한,제어 프로세스 강제 종료4조건을 검사했다. 정상/제한2조건 모두
Job의 잔류 프로세스0이고, 제어자 종료 조건은 외부 시험에서 보유한 worker/reader 핸들의
종료를 확인했다. 같은 대상 프로세스의 생성 시각·생존을 매 단계 확인했고 마지막 정상 종료도
exit0이다. 잘못된 생성 시각은 거부했다. 제어자 종료 시 최종 요약 부재는 미완료로 보존한다.

첫 보호 실행은 닫힌 결과 파이프를 재조회해 WinError109로 실패했다. 원 소스/로그를 보존하고
child PID 수신 후 파이프 조회를 중단하도록 수정한 R2는 네 조건 모두 exit0이다. 최초 실패에서도
Job 잔류0과 대상의 정상 종료를 확인했다. 결과를 덮어쓰지 않고 R2를 새 폴더에 저장했다.
최종 오프라인 검산의 첫 실행은 UTF-8 로그를 Windows 기본 인코딩으로 읽어 exit1이었다.
인코딩을 명시한 최종 검산 R2는 exit0이며 이 실패 자료도 보존했다. 실제 관찰을 다시 실행하지 않았다.

일반 dump10회의 벽시계 시간은47.65–64.67ms였다. 짧고 길이가 다른 OFF/ON 구간의
처리량 비율0.9267은 배경 부하를 분리하지 못했으므로 정확한 도구 비용이나 서버 성능 판정에
사용하지 않는다. 비정지 읽기의 불완전 샘플 가능성도 남는다. 로컬 보호 prototype은 서버
진입점이 아니며 고정 인수·설치/설정·세대·외부 감시 경로와의 결합 검증이 다음 단계다.

서버·제품·설정·작업번호·백업 변경이나 새 서버 화면 관찰은 없다. 원120분 FAIL·R1~R6·
출시HOLD 및 미서명 방침을 유지한다. [검증 결과·사용 예·다음 조건](C:/Users/user/Desktop/SmartFactory/PYFRAME_20261017_82eb041c/review.md).

### 5.103 보호 진단 경로에 Python 프레임 모드 결합

field_runner에 별도 python-frames 모드를 추가하고 기존 설치본·설정·인증 세대 확인과 owned Job
감시를 재사용했다. 요청은1.0.30/6초로 고정하며 도구/인수는 요청에서 선택할 수 없다. 프로세스와
스레드의 native 핸들·생성 시각·전후 생존으로 읽기 결과를 연결한다. 종료되거나 사전 확인하지
못한 TID는 UNBOUND/PARTIAL로 남기며 현재 TID를 과거 지연 당시 역할로 소급하지 않는다.

최종 단위·인접 회귀8건이 통과했다. 실제 frozen 대상의 프레임/생성 시각 대조, 다른 도구 및
잘못된 요청/지역변수/중복ID 거부를 포함한다. 실제 loopback·설치파일 fixture를 기존 감시 경로로
실행한 정상/설정 변경/취소/잘못된 생성 시각4조건도 통과했다. 정상은3샘플을 수집했고 나머지는
FAIL을 유지했다. 모든 경우 대상 앱을 유지하며 진단 Job 잔류0, fixture 정상 종료를 확인했다.

PyInstaller6.20.0/Python3.12.6으로 실제 field_runner를 빌드했다. 실제 CLI의 모드 안내와 혼합
인수 거부를 확인하고, 같은 수집 모듈의 별도 frozen synthetic harness에서 정상3샘플과 잘못된
세대 거부2조건을 실행했다. harness는 서버 묶음에 포함하지 않았다. 실제 제품/서버 전체 경로의
시험으로 확대하지 않는다. PowerShell5.1은 새 모드600초/잘못된 계약6조건 거부/기존4모드 한도
유지를 확인했다. 각 최종 시험·빌드는 exit0이며 기대한 거부 실행의 exit1은 구분한다.

첫 단위 실행은 배열 JSON을 객체 전용 decoder로 읽은 오류와 시험 경로/환경 준비 누락으로
실패했다. 수정 R2에서는 Python join 직후 OS 스레드 종료를 단정한 시험1건이 실패했다.
실제 핸들 종료를 기다리는 R3는8건 통과했다. 첫 소스/결과와 R2 로그를 보존했다. 첫 명령의
원 콘솔 출력은 대화 도구 기록에 있으며 별도 원 로그 파일을 만들었다고 주장하지 않는다.

로컬 전달 묶음 PF30은11파일, ZIP43,469,538바이트다. 실행 파일·도구·소스 snapshot·라이선스·
후보 기준과 기존 검증기2개를 파일별 검산했다. helper는 현재 작업트리의 고정 소스 snapshot에서
빌드했으며 clean commit 빌드라고 표시하지 않는다. 제품 설치본은 바뀌지 않았다.
서버 전달·현재 상태 요청 작성·현장 실행은 아직 미실시다. 다음 단계에서 승인된 SSH와 기존
최종 폴더 전달/검산 규칙을 적용한다. R1~R6·원120분 FAIL·출시HOLD를 유지한다.
[시험·묶음·남은 단계](C:/Users/user/Desktop/SmartFactory/PYBIND_20261018_5a0d719c/review.md).

### 5.104 실제 서버의 Python 호출 역할 제한 관찰

승인된 SSH로 대상/계정/관리자 권한과1.0.30 후보의 현재 실행 세대를 확인했다. 고정 묶음과
설정 기준·요청14파일을 날짜별 Z send 경로에서 원격 탐색기로 서버 로컬에 복사하고 전 파일
해시를 대조했다. 기존 보호 실행의 실제 frozen CLI가3회 비정지 읽기를 완료하고 exit0으로 종료됐다.
설치 파일1,900개 재검산·설정 전후·같은 앱/제어/로그 세대 확인이 통과했고 내·외부 Job 잔류0이다.

결과30파일/1,067,508바이트의 서버·공유·로컬 해시를 비교했다. 각27개 Python 스레드, 총81행을
native 생성 시각과 전후 생존에 연결했다. 별도 native15592에는 Python 프레임이 없다. 원 출력
재해석과 앱 소스 함수/행63건 대조를 완료했다. 후보 git blob과 빌드 소스의 CRLF/LF 차이를
구분하고 원 해시를 보존했다. 현재17460은spot-image-capture-writer,5412는HTTP통신,
17688은ObservationFact,17288은CSVLogger,2228은진단journal,812는asyncio/uvicorn이다.
세 번 모두 대기/폴링 상태로 관찰했으며 과거 역할이나 지연 원인·CPU/GIL 경합 부재를 확정하지 않는다.

읽기 경과180.8006/212.5279/78.2053ms와 snapshot295.3064/337.4727/240.1485ms는
앱 응답 시간이나 순수 계측 부담이 아니다. 현재 이미지 저장 역할은 다음 조사 범위를 좁히지만
과거528 ReadyThread 기록이나221.0337ms 지연의 원인 판정으로 확대하지 않는다.

최초 읽기 전송문의 구문 오류, 개발 PC 대비 서버 약9초 시각 차이에 따른 로컬 시각 검토 실패,
복사 전 없는 폴더의 잘못된 reparse 표시, 오프라인 JSON 키/줄바꿈/entry 경로 가정 오류를
각각 보존했다. 검증 조건이나 시각을 완화하지 않았고 실제 서버 수집은 한 번만 수행했다.
최종 전달 검산·실행·회수·분석은 exit0이다. 실패 원 script 및 SSH 터미널 영수증을 보존하며
별도 저장하지 않은 초기 Python 콘솔 로그는 대화 도구 기록과 구분한다.

최종 화면은Running/60180·19이며 앱·설정·작업번호·백업 변경 없이 Smart Factory를 전면에
복귀시켰다. 최근 사용자 생산 중 아님 보고를 화면 metadata로 대체하지 않았다. R1~R6·원120분
FAIL·전체 출시HOLD와 미서명 방침을 유지한다. 다음은 기존 ETW의 생명주기/호출 구간과 연결
가능한 근거를 검토하는 단계다. [현재 역할·검증·한계](C:/Users/user/Desktop/SmartFactory/PYFIELD_20261018_46f2c831/review.md).

### 5.105 과거 스레드 기록과 현재 native 생성 시각의 대조

기존 정상/지연 추적의 원 XML에서800,159/1,337,420이벤트를 읽어 프로세스·스레드 생명주기를
추출했다. 스레드2,812/3,033행은 기존 TraceEvent 출력과 QPC·CPU·opcode·version·PID/TID·
전체 payload·중복 횟수가 일치한다. 백엔드14012의28개 스레드는 모두 DCEnd 열거이며 두 추적의
원 payload가 같다. 프로세스 열거 필드와 BootTime도 같지만 연속 생존이나 과거 Python 호출의
독립 증명으로 쓰지 않는다. 실제 대상 Start/End는 보존되어 있지 않다.

과거 HTTP 진단450+121건의 원 응답과 헤더·식별자·native anchor·QPC 구간을 기존 검증기로
재계산했다. 모든 결과가 기존 validation과 일치한다. loop812와 worker17264/16664/4384/
3760/16380/7368의7개 생성 시각이 PYFIELD와 정확히 같다. 실제221.0337ms 요청의
loop812/worker16664도 포함된다. 현재 이미지 writer17460은 당시 생성 시각이 없어 호환 관찰로
남긴다. 같은 숫자·payload·앞선 생성 wall-clock만으로 과거 역할이나 지연 원인을 확정하지 않는다.

최종 `analyze.py`는 exit0, 두 분석 Python 파일의 Ruff F 검사는 exit0이다. 최초 원 XML 추출의
콘솔 종료 코드는 컨텍스트 전환 때 회수하지 못했으므로 exit0이라고 표시하지 않는다. 결과 파일과
원 XML/TraceEvent 대조는 현재 검산했다. 서버·제품·설정·작업번호·백업은 변경하지 않았다.
기존120분 FAIL·R1~R6·전체 출시HOLD를 유지한다. 다음은 같은 구간의 Python 호출과 수집기
실행 대기를 연결할 수 있는 제한된 원인 검증이며, 기존 열거/15·120분 시험을 단순 반복하지 않는다.
[대조 결과·요청별 근거·한계](C:/Users/user/Desktop/SmartFactory/THREADLINK_20261018_674c2ba9/review.md).

### 5.106 단발 Python 읽기의 실제 QPC 범위 검증

`field_python_frames.py`에 고정 reader 실행 전/출력 수신 후 native anchor와 read_window를
추가했다. 기존 clock validator로 같은 프로세스·스레드·주파수·단조 순서·변환 범위를 확인하며
원 프레임 CAPTURED와 시간 범위 BOUNDED/UNAVAILABLE를 분리한다. 요약 clock_coverage도
추가했다. 설치/설정/세대 검증·고정3회·reader 시간/출력 한도·비정지 읽기·소유 자식 정리는 유지했다.

실제 격리 대상의 알려진 함수2구간이 각 reader의 전체 QPC 범위를 포함했고 원 프레임의 함수명이
일치한다. 생성 시각이 다른 anchor를 주입한 실제 읽기는 프레임을 보존하되 시간 결합을 거부했다.
단위/회귀12건과 정상 수집·취소·설정 변경·잘못된 세대4조건이 모두exit0이다. 최초 collection
실행은 import용 환경 변수 누락으로 시험 시작 전exit1이며, 원 실패 로그와 수정 실행을 구분했다.

알려진 함수의 reader 폭230.3277/62.0743ms, 수집 fixture의53.2838/63.4340/51.5408ms는
정확한 개별 프레임 시각·함수 실행 시간·순수 관찰 부담이 아니다. 단발 읽기가 기존221.0337ms
지연 내부를 충분히 구분한다고 판단하지 않는다. 공식0.4.2 chrometrace의 병합 상대시각도 원
메모리 읽기 시각으로 대체하지 않는다. 다음은 지속 읽기에서 원 프레임과 실제 읽기 시작/끝 시각을
보존하고 비용·정리를 로컬에서 검증하는 단계다. 새 frozen 묶음/서버 적용은 하지 않았다.
설계5.72의 시간 범위·실패 분리·실제 함수 구간 대조는 확인했으나 정밀 현장 인과/비용은 미완료다.
제품·서버·백업 변경 없이 전체HOLD를 유지한다.
[시험·원 출력·시간 범위 한계](C:/Users/user/Desktop/SmartFactory/PYQPC_20261018_c38b691d/review.md).

### 5.107 지속 읽기·종료·로컬 부담 확인

공식 py-spy0.4.2 library를 유지하는 시제품에 get_stack_traces 직전/직후 QPC와 원 배열을
기록했다. 고정100회/20ms, NonBlocking, locals/native/자식 수집 끄기, 출력 상한과8초
자체 종료를 적용했다. 독립된 작업 폴더에 공식 Rust1.99.1/LLVM 구성요소를 해시 확인해
준비하고 Cargo.lock 유지·release 빌드exit0을 확인했다. 첫 두 빌드의 dlltool 오류는 보존했다.

알려진 함수의100회는 전체 읽기 범위가 alpha31/beta69구간과 일치하고 native 생성 시각도
일치한다. 중앙값0.27175ms, p95 0.3635ms, 최대0.7655ms다. 정상·취소·잘못된 세대·
제어 프로세스 종료+Job 닫기·출력 수신 정지에 따른8초 종료·대상 정상 종료를 실제 확인했다.
각 suite exit0, 최상위 Job 잔류0이다. 강제 종료의 미완성 stdout은 완전 샘플로 해석하지 않았다.

Python3.12.6 frozen 대상의 동일 CPU 작업에서 OFF/ON/ON/OFF를2회 수행했다. ON400회
읽기 모두 native 세대와 연결했고 최대 읽기 폭1.1088ms였다. 처리량 중앙값 차이-0.0960%,
reader CPU62.5~109.375ms는 짧은 합성 부하에서 관찰한 값이며 현장 HTTP 영향/비용 상한이
아니다. 초기 연결/출력 비용은 비교에 포함되며 개별 read 폭과 구분한다. 20ms 사이 공백과
비원자적 읽기는 남고 과거221.0337ms 인과를 소급해 증명하지 않는다.

설계5.73의 로컬 실제 호출 시각·생명주기·generation·합성 비용은 확인했다. 기존 보호 launcher의
설치본/설정 결합·동일 구간 HTTP/ETW 통합과 현장 비용은 미완료다. 원 library의 권한 요청에는
suspend/resume 등이 포함되므로 전체 HANDLE 최소 읽기 권한을 주장하지 않는다. NonBlocking
설정에서 잠금 경로를 호출하지 않도록 했다. 서버·제품·백업 변경 없이 전체HOLD를 유지한다.
[실제 빌드·500회·종료 조건·부담 한계](C:/Users/user/Desktop/SmartFactory/PYPERSIST_20261018_e664ac62/review.md).

### 5.108 지속 Python 읽기와 HTTP 요청의 로컬 결합

`python-health`를 1.0.30/6초로 고정하고 reader 경로를 묶음 내부에서만 선택한다. 기존
payload/configuration/control/native generation 전후 검사를 그대로 수행한다. 별도 수집
스레드에서 고정 reader를3회 실행해 각100개 원 JSONL·QPC 범위를 보존하고, 직접 관찰한
프로세스/스레드 생성 시각과 연결한다. 도구 크기/SHA는 실행 중 잠긴 핸들로 확인한다.

원 HTTP 응답을 재검산해 클라이언트 요청 전체·서버 route·각 단계의 시간 범위를 구분했다.
샘플이 경계를 가로지르면 완전 포함으로 세지 않으며, 생성 시각을 결합하지 못한 프레임도
그 상태를 유지한다. 이미 저장된 validation 판정만 바꾸어도 원 응답 검증을 생략하지 않는다.
원 응답/대상 생성 시각 불일치는 결합 실패다. 취소 시 부분 stdout과 해시를 보존하고 소유
reader를 정리하며 대상 앱은 유지했다. 설정 변경 시 수집 완료로 승격하지 않는다.

최종 소스 시험43건과 기존 runner/trace/frame 회귀34건이 모두exit0이다. 정상 지연 fixture의
300회와 요청3건에서 각각11개의 읽기가 알려진 work 함수 구간에 포함됐다. frozen 실행의
300회와 요청3건에서도12/11/11개를 연결했다. 소스 요청231.7946/253.6847/231.8173ms,
frozen241.5345/232.2770/236.5562ms는 의도적인230ms sleep을 포함한 로컬 값이다.
실제 서버 인과나 성능 통과로 사용하지 않는다. frozen 정상/잘못된 세대2조건 모두 기대한
판정과 Job 잔류0을 확인했다. PowerShell 두 Python 모드600초·잘못된 입력12개 거부·기존
네 모드9000초 유지도exit0이다. 새 도우미와 시험 harness의 PyInstaller 빌드는exit0이다.

첫 시험은 Cargo 빌드 출력의 하드링크2개를 기존 single-link 검사에서 거부해3건 실패했다.
검사를 완화하지 않고 새 묶음용 실제 사본을 만들었으며 동일 SHA·링크1개를 확인했다.
실패 원 출력은 tests-r1에 보존했다. tests-r2의10건 통과 뒤 요청 전체 구간/취소 영수증을
보완하고 최종 tests-r3에서 관련43건을 다시 확인했다.

설계5.74의 소유 수집기·입력/원 바이트·시간/세대 결합·중단 처리는 확인했다. ETW 시작 후
reader 시작, reader 정리 후 ETW 종료 순서는 주입 fixture로만 확인했다. 실제 Windows 추적,
외부 관리자 launcher·완성 묶음의 실행, 현장 비용/인과는 다음 검증 대상이다. 이번 frozen
fixture는 합성 reference를 사용하는 로컬 전용이며 서버 묶음에 포함하지 않는다. 새 운영
설치본은 만들지 않았다. 서버·설정·작업 정보·백업 변경 없이 전체HOLD를 유지한다.
[검증 명령·원 결과·남은 범위](C:/Users/user/Desktop/SmartFactory/PYJOIN_20261018_a2562c7a/review.md).

### 5.109 실제 보호 launcher와 Python·HTTP·ETW 통합

설계5.75~5.76을 새 6초 요청/계약/lease와 ReadyThread 프로파일에 연결했다. 기존
운영 payload pin을 유지하고 실제 미서명1.0.30을 오프라인 Sandbox에서 실행했다.
최종 stream/collection46개 및 runner/trace33개가 exit0이며 PowerShell 계약의
잘못된 입력12개 거부, 실제 package pin/생성 시각 불일치 거부도 확인했다.

초기 두 실행은 각각100회 중1회 스택 읽기 실패로 중단됐다. 원 오류와 정상 정리를
보존하고 새 추적 경로에 명시적 누락 처리를 추가했다. 순번·QPC·완전한100개 시도·
오류 수·고정 stderr/종료의 일치를 검증한다. 취소/잘림/전체 실패는 계속 거부하고,
기존 Python 단독 경로는0오류 조건을 유지한다. 최종300회 중297회 해석,3회 누락을
별도로 기록했다. 수집 완료는 품질/현장/인과 통과를 뜻하지 않는다.

실제 관리자 launcher·frozen helper·WPR는 exit0, 앱/백엔드 정상 종료0, Job 잔류0,
소유 WPR 세션 없음과 Sandbox 종료를 확인했다. 동일 ETL128,647이벤트 중 스케줄링/
스레드65,662개를 독립 decoder와 tracerpt에서 대조했고 손실0이다. HTTP3건과
Python 읽기의 겹침은1/1/0개다. 세 번째 요청은 reader 묶음 사이 공백에 있고,
대상 ETW 스레드 기록은 종료 rundown만 있어 전체 수명 결합은 미확정이다.

남은 격차는 묶음 사이 공백, 비차단 읽기 누락, 전체 호출자 의미, 현장 비용/인과다.
읽기 구간 중앙값1.5789ms/최대3.552ms를 현장 영향 상한으로 확대하지 않는다.
기존 R1~R6와120분FAIL/HOLD를 유지한다. [원 결과와 후속 조건](C:/Users/user/Desktop/SmartFactory/PYTRACE_20261018_16c222a2/review.md).

### 5.110 한 번의 읽기로 6초 관찰 범위 포함

설계5.77에 따라 reader를 새 schema/hash의 350회·20ms 고정 실행으로 교체하고,
시작·종료 시각의 불확실성을 포함해 관찰 6초 전체가 첫/마지막 읽기 사이에 있는지
검사했다. 실제 단일 프로세스와 native HANDLE이 세 요청의 route 구간을 모두 포함한다.
최대 읽기 시작 간격은21.5181ms이며 모든 순간의 스택을 관찰한 것으로 해석하지 않는다.

최종 관련 Python 검사82개(기존66개와 변경된 stream16개 재검), PowerShell 거부12개,
정상350회·취소·세대 불일치·부모 종료·8초 제한·대상 종료가 통과했다. 첫 엄격 단독
통합 시험은350회 중1회 읽기 실패를 올바르게 거부했다. 실패 증거를 보존하고 통합
fixture를 실제 추적 모드의 명시적 누락 정책으로 보완했다. 제품의 단독0오류 정책은
변경하지 않았다. 단위 시험의 trace handshake는 대역이며 실제 WPR는 아래 Sandbox로 확인했다.

새 frozen helper와 실제 미서명1.0.30의 격리 실행은 exit0이다.350회 중349회 해석·
1회 누락, HTTP6.1383/5.2253/4.7970ms와 각각1개 읽기 겹침을 기록했다. 누락 구간은
세 요청과 겹치지 않는다. ETL138,407이벤트 중 스케줄링/스레드73,417개를 TraceEvent와
tracerpt로 대조해 일치했고 헤더 손실0이다. tracerpt의 일부 이벤트 schema 경고는
남아 있으며 전체 이벤트/호출자 의미를 검증했다고 주장하지 않는다. 대상 스레드는 종료
rundown만 있어 전체 ETW 수명은 미확정이고, 직접 보유한 HANDLE의 세대 근거와 구분한다.

앱·백엔드 정상 종료0, 소유 Job 잔류0, WPR 세션 없음, Sandbox 폐기를 확인했다.
기존 제품 설치본을 시험 대상으로 사용했으며 재빌드·설치/복구 매트릭스 재판정은 하지 않았다.
다음은 승인된 현장 진단에서 같은 수집 범위와 비용을 확인하는 단계다. 서버 미접속,
새 백업 없음, 기존120분FAIL 및 전체HOLD를 유지한다.
[원 결과·명령·검증 한계](C:/Users/user/Desktop/SmartFactory/PYWINDOW_20261018_b39217f1/review.md).

### 5.111 실제 현장 단일 reader와 빈 스택 실패의 분리

승인된 SSH와 UI 전달로 PW30 묶음16파일을 서버 로컬에서 검산하고6초 진단을1회 실행했다.
설치·설정·프로세스 초기 결합은 통과했으나 순번312의 TID5412(`spot-http-transport`)에
빈 `frames=[]`가 있어 기존 해석기가 `frame-stack-budget`으로 중단했다. reader는350회,
오류5회와 완전한 종료 레코드를 남겼다. 실제 launcher/entry/coordinator는FAIL/exit1이며
설정·payload의 최종 검증은 도달하지 못했다. 이 실패를 소급해PASS로 바꾸지 않는다.

설계5.78의 보완은 빈 스택을 명시적 공백으로만 처리한다. 모든 행 검증을 유지하고 해당
샘플 전체를 함수 대조에서 제외한다. reader 오류5회와 빈 스택1회를 구분하며 엄격 단독
경로·전체 공백·잘못된 필드는 계속 거부한다. 최종 관련90개 검사 exit0, 원 바이트 실패
재현과 별도 재해석을 확인했다. 새 소스의 frozen 묶음 검증과 현장 완료 검증은 남는다.

불변 원자료의 별도 재해석에서는345개 reader 응답 중344개가 함수 대조 가능했다.
한 reader의 시각 범위가6초를 포함하지만 읽기 시작 최대 간격62.1571ms, 읽기 범위
중앙값5.3075/최대56.6272ms였다. 이는 reader의 현장 부담을 분리한OFF/ON 측정이 아니다.
HTTP3건7.6403/13.9651/11.3400ms에 각각1개 읽기가 겹치며6개 공백은 요청과 겹치지 않는다.
프레임은 worker 대기/loop poll을 포함하지만 비원자적 읽기와 경계 겹침으로 원인을 단정하지 않는다.

ETL339,962이벤트 중 스케줄링/스레드166,962개가 TraceEvent와 tracerpt에서 일치했다.
헤더 손실0, ReadyThread stack99,475개의 호출자 의미는 미평가다. tracerpt schema 경고,
대상 스레드의 시작 rundown 부재와 전체ETW 수명 미확정은 유지한다. native HANDLE 세대
근거는3개 route를 포함한다. 소유 Job 잔류0·WPR 세션 정리·helper 잔류 없음과 기존 앱
실행 세대를 확인했다. 앱60180·19 화면은 관찰값이며 최신 사용자 생산 확인을 대체하지 않는다.
Smart Factory를 전면에 표시했고 새 백업·설치·작업 정보 변경은 없었다. 기존120분FAIL과
R1~R6/HOLD를 유지한다. [증거·검증·후속 조건](C:/Users/user/Desktop/SmartFactory/PYWFIELD_20261018_6c90a272/review.md).

### 5.112 빈 스택 보완 실행 파일과 격리 통합 검증

설계5.78의 최종90개 검사 소스에서 새 frozen 도우미를 만들었다. 내부19개 모듈과
진입 코드의 소스 일치를 확인하고, 추출 코드로 과거 현장 원자료를 재해석해 읽기 오류5회와
빈 스택1회 및 분석 가능344개를 재확인했다. 이 호스트 재해석과 실제 실행 파일 시험은 구분한다.

실제 보호 launcher와 새 실행 파일은 오프라인 Windows Sandbox에서 exit0이었다.
잘못된 패키지 해시/프로세스 세대는 추적 전에 거부했다.350시도 중344회 성공·6회 읽기 실패,
빈 스택0이며 HTTP3건과 읽기 겹침은1/1/0개다. 같은 ETL의 스케줄링/스레드69,904개 독립
대조가 일치했고 헤더 손실0이다. 전체 호출자 의미·ETW 수명·현장 비용/지연 인과는 미확정이다.

앱·백엔드 정상 종료0, 소유 Job 잔류0, WPR 세션 없음과 Sandbox 폐기를 확인했다.
초기 로그인 세션 부재에 따른 실행 전 실패는 보존했다. 이번 단계는 서버 미접속이며
새 실행 파일의 현장 완료 검증이 남는다. 과거 현장FAIL/120분FAIL 및 R1~R6/HOLD는 유지한다.
[실행 파일 식별·명령·검증 한계](C:/Users/user/Desktop/SmartFactory/PYEMPTY_20261018_9a466f97/review.md).

### 5.113 수정 도우미의 현장 최종 검증 완료

새 PE30 묶음16파일을 서버 로컬까지 전달·해시 대조하고 승인된6초 진단을1회 실행했다.
entry/coordinator exit0, 초기·최종 설정 및 실행 세대PASS, 설치파일1,900개 최종 재검산을
확인했다. 이전 빈 스택 실패의 최종 검증 미도달을 이번 새 실행으로 해소했으며 과거FAIL은 보존한다.

350시도 중348회 성공·2회 읽기 실패·빈 스택0이다. 세 HTTP7.6148/8.4222/12.4613ms에
각각1개 읽기가 겹쳤으며 실패 구간은 겹치지 않았다.6초 범위 포함과 최대58.3749ms 샘플
간격을 함께 기록한다. 원 스케줄링/스레드166,146개 독립 대조가 일치했고 헤더 손실0이다.
진단 비용 OFF/ON, 과거 지연 원인, 전체 호출자 의미와 ETW 스레드 수명은 미확정이다.

97파일69,411,224바이트를 회수·검산했다. 소유 Job/WPR/helper 정리와 기존 앱의 실행 세대,
Running 및 Smart Factory 전면 표시를 확인했다. 설치·설정·작업 정보 변경이나 새 백업은 없다.
빈 스택 자체는 이번 현장에서 재발하지 않았으므로 앞선 원자료 재해석의 검증 범위와 구분한다.
기존120분FAIL/R1~R6/HOLD는 유지한다.
[현장 결과·후속 조건](C:/Users/user/Desktop/SmartFactory/PYEFIELD_20261018_4c758d20/review.md).

### 5.114 회수 추적에서 확인한 reader의 CPU 배정 시간

새 서버 실행 없이 봉인된 PYEFIELD 원자료를 분석했다. CSwitch105,062개에서 각 CPU의
old/new TID 연결과5,067개 reader 구간을 구성하고, 별도 전역 누적 적분 방식으로
두 관찰 범위와350개 읽기 구간을 검산했다. 원 manifest 해시 및 입력 바이트를 대조했다.
최종 verifier exit0, 경계·중복·두 CPU·불완전 구간 거부 검사7개 exit0이다.

첫/마지막 읽기 사이6,990.3529ms에서 reader의 CPU 배정 시간은1,956.6403ms다.
보수적인6초 관찰 경계5,999.9974ms 안에서는1,696.7962ms로, 관찰된2개 논리 CPU
전체 시간의14.1400%다.350개 읽기의 누적 wall 시간2,741.1749ms 중 reader 배정 시간은
1,478.1154ms다. 가장 긴52.1726ms 읽기에는 reader 배정5.5534ms와 미배정46.6192ms가
포함됐다. 미배정의 이유·대기 대상은 판정하지 않는다. 수집기 단일 스레드 CPU62.5ms는
별도 reader 프로세스의 CPU 시간을 대신하지 않는다.

초기 verifier는 Thread/End 뒤의 동일 TID CSwitch 구간20개를 발견해 exit1이었다.
해당 경계의 소유권을 추정하지 않고 ‘전체 수명’ 수치는 채택하지 않았다. 최종 보고 범위는
5개 reader 스레드의 Start/End 안에 완전히 포함되는 sampling span과6초 구간으로 한정했다.
원 계산·실패·범위 제한을 보존하며6초 수치는 변경되지 않았다. 초기 분석의 잘못된 키 참조
실패도 보존했다. 스케줄링 시간은 인터럽트 등을 포함할 수 있어 순수 실행 CPU 계측과 구분한다.

추가 부하·앱 영향은 OFF 조건이 없어 미확정이다. 설계5.79에 동일 조건 비교를 명시했다.
기존 기본 health/Python 모드의 추적 profile이 달라 단순 모드 비교는 채택하지 않는다.
서버·제품·진단 소스·설정·작업 정보·백업은 변경하지 않았고 이번 서버 화면 관찰도 없다.
기존120분FAIL 및 R1~R6/HOLD를 유지한다.
[원자료·검산·다음 비교 조건](C:/Users/user/Desktop/SmartFactory/PYCOST_20261018_a52c80df/review.md).

### 5.115 같은 profile을 사용하는 OFF 비교 경로와 새 실행 파일

설계5.79~5.80의 OFF 요청을 별도 schema로 구현했다. ON과 같은 Ready profile·6초 관찰·
30초 추적 제한·600초 외부 예산·패키지 reader 잠금을 유지하며 공통 HTTP 수집 루프에
Python companion만 전달하지 않는다. 기존 기본 health의 다른 profile을 OFF로 사용하지 않는다.

첫96개 검사 중95개가 성공했고 새 baseline 계약 fixture의 파일 생성 누락1건이 실패했다.
fixture를 수정한 뒤 관련 trace16개를 재검해 exit0이었다. 변경되지 않은80개와 재검16개로
최종96개 범위를 확인했고 최초FAIL 원문도 보존했다. 소스 및 실제 새 패키지의 PowerShell
함수를 각각 검사해 잘못된 요청/시간/계약/lease/profile 등21조건 거부를 확인했다.

새 도우미16,148,954바이트/SHA `f87f936913992046f5cc8cde39963ab0d68a5a64f74e8b56226efb43bede6752`,
패키지 manifest SHA `fc807efc492ebd6045a4642f3d3953882c2ed5ca0fddc4d0a28379e55683b477`를 생성했다.
실제 실행 파일 describe exit0, 내부19개 모듈·진입 코드와 최종 소스의 일치, 추출 코드의
OFF/ON 요청 및3개 거부 조건을 확인했다. 제품 설치본·reader·의존성 버전은 바꾸지 않았다.

새 baseline의 실제 관리자 추적과8구간 비교는 아직 실행하지 않았다. 이번 검사는 제어 흐름의
대역과 실제 기존 reader/HTTP fixture를 구분하며 실제 앱 성능 효과를 주장하지 않는다.
서버 접속·설정/작업 정보 변경·새 백업은 없다. 기존120분FAIL과 R1~R6/HOLD를 유지한다.
[원 검사·패키지·후속 실행 조건](C:/Users/user/Desktop/SmartFactory/PYPAIR_20261018_0554749e/review.md).

### 5.116 실제 격리 앱의 고정 OFF/ON 비교 완료

PYAB의 새 read-only 입력 구성으로 기존 설치본/Python과 PYPAIR 패키지를 재사용했다.
오프라인 Windows Sandbox에서 실제1.0.30을 설치하고 정상 종료·설정 대조·재시작 후 같은
backend1340 생성 시각134367388583830877을 유지해 예비 OFF와8구간을 실행했다.
보호 launcher9개와 전체 guest 명령 exit0,각각 설치파일1,900개/설정/세대 최종 확인,
Job0·추적9개 부재·잔존 프로세스/포트0·앱/backend 정상 종료0을 검산하고 Sandbox를 종료했다.

| 조건 | 요청 수 | 중앙값 | 최솟값~최댓값 | 200ms 초과 |
|---|---:|---:|---:|---:|
| OFF |12|6.04675ms|4.7489~30.5824ms|0|
| ON |12|6.24645ms|4.6149~16.2467ms|0|

인접4쌍의 평균 지연 차이(ON−OFF)는−8.4681,+0.2078,−5.2221,+3.0145ms였다.
작은 표본과 변동을 보존하며 ON의 개선/악화를 단정하지 않는다. Reader 전체 프로세스 CPU는
718.75~921.875ms,6초 안의 확인된 배정 시간은738.9471~799.5867ms였다. 후자는12논리 CPU
용량의 약1.03~1.11%이며 interrupt를 포함할 수 있어 GetProcessTimes CPU와 다르다.
수집기 전체 CPU는 준비/파일 검산까지 포함하며 같은6초 비용으로 해석하지 않는다.

ON1,400회 중 읽기 오류13회와 빈 스택1회를 제외한1,386회만 함수 대조에 사용했다.
9개 ETL의총1,035,524이벤트에서 스케줄링/스레드513,771개를 두 해석기로 독립 대조했고,
EventsLost/BuffersLost 모두0이었다. 원 응답/clock 및 읽기 공백 결합도 재검산했다.
첫 분석 exit1은 모든 CPU의 끝 전환이 관찰 종료 이후에 있을 것이라는 가정 때문이었다.
실측 끝부분을 추정하지 않고 예비138.799ms/04-OFF768.938ms/08-OFF260.4702ms를
미확인 배정 시간으로 남겼다. 보완 분석 exit0,별도 누적 적분/원 HTTP 집계9개 대조 exit0,
경계 계산4조건 검사를 확인했다. 첫 분석/로그와 connect 대기 timeout도 보존했다.

기존 현장은2논리 CPU이며 로컬은12논리 CPU·모의 장비다. 이 비교로 현장 영향이나 과거
120분FAIL 원인을 확정하지 않는다. 서버 미접속,제품/설정/작업 정보/새 백업 변경 없음,
R1~R6/출시HOLD 유지. [원자료·검산·한계](C:/Users/user/Desktop/SmartFactory/PYAB_20261018_a7b921c4/review.md).

### 5.117 실제 서버의 고정 OFF/ON 비교

서버 DESKTOP-CIIT7LK의 같은1.0.30 앱(main17996/backend14012)과 승인 설정을 유지했다.
PYPAIR 패키지의 예비 OFF 이후 OFF→ON→ON→OFF를 두 차례 실행했다. 각 회차6초/HTTP3건/2초 간격,
동일 Ready profile·30초 trace guard·600초 보호 launcher를 사용했다.9개 실제 종료 코드0,
각각 설치파일1,900개·설정·세대 종료 검산,Job0·WPR 정리와 원본/공유/로컬 해시 일치를 확인했다.

| 조건 | 요청 | 중앙값(ms) | 평균(ms) | 범위(ms) | 200ms 초과 |
|---|---:|---:|---:|---:|---:|
|OFF|12|9.48780|13.64132|7.5376~37.6214|0|
|ON|12|9.33745|13.18273|6.9220~36.3290|0|

평균 ON−OFF 차이: +2.3308, +0.2735, -2.9021, -1.5365ms.

Reader 전체 프로세스 CPU는1312.500~2031.250ms,6초 안의 확인된 배정 시간은
1203.0172~1755.8583ms로2논리 CPU 용량의10.0251~14.6322%였다.
전체 CPU는 초기 연결·읽기·종료를 포함하고,배정 시간은 interrupt 실행을 포함할 수 있다.
200ms 간격 PowerShell 보조 관찰기의 보호 실행 전후 CPU는1421.875~1718.750ms였다.
보조 관찰기는 양쪽 조건에서 동일하게 동작했으며 이 값 역시6초만의 비용이 아니다.
수집기 전체 CPU와 backend 전후 차이,관찰기 자체 비용을 구분했다. 로컬 Python 관찰기와 직접 비용 비교하지 않는다.

ON1,400시도에서 native 읽기 오류17회·빈 스택0회를 명시적으로 남겼고1383회를 함수 대조에 사용했다.
9개 ETL의2,697,987이벤트 중 스케줄링/스레드1,270,521개가 두 해석기에서 일치했다.
EventsLost/BuffersLost 모두0이며 원 HTTP/native clock·읽기 공백 결합도 재검산했다.
tracerpt의 일부 이벤트 스키마 불일치 경고는 보존했다. 해석 확정 범위는 대조한 스케줄링/스레드 필드이며,
전체 이벤트·호출 스택의 모든 필드 해석은 미확정이다.
별도 누적 적분과 원 요청 집계의9개 대조가 exit0이었다. 전환 기록으로 묶이지 않은 경계는 추정하지 않는다.

준비 첫 실행은 개발 PC 시계로 서버 시각을 비교해 configuration-time-order/exit1로 중단됐다.
SSH 전후 시각 대조에서 서버가 약10초 앞서는 것을 확인했다. 원 FAIL과 로그를 보존하고 서버 기준
시각 순서/수집 나이를 별도로 검사했다.9개 준비 경계 검사와18개 PowerShell 진입점의 구문/잘못된 호스트
거부36조건을 확인했다. 실제 서버의 고정 도우미는 기존 검증 그대로 초기/종료 설정 대조를 통과했다.
초기 Ruff의 미사용 import1건은 실행 전 수정했다. 실측 실패를 유리한 결과로 바꾸기 위한 재실행은 없었다.
큰 해석 산출물은 Z:\SmartFactory\20261018\records\PYAFIELD_03baf471\decode에 보존했다.

작은 표본의 관찰 차이를 지연 상한·통계적 유의성이나 과거120분FAIL 원인으로 해석하지 않는다.
기존221.0337ms 실패에는 이번 reader가 없었으므로 reader가 그 과거 실패를 만들었다고 주장하지 않는다.
Backend/collector의 과거 전체 스레드 수명·개별 affinity는 독립 확정 범위가 아니다.
제품/설정/작업 정보/전체 백업 변경은 없다. 현재 화면 값은 관찰 정보이며 새 사용자 생산 확인이 아니다.
기존120분FAIL·R1 timeout·R3 물리 NOT_TESTED/Low Signal OFF·R4 전체 데이터·R5 drop·R6 최종 QA/승격은 계속 미완료다.
[원자료·해시·실행 결과](C:/Users/user/Desktop/SmartFactory/PYAFIELD_20261018_03baf471/review.md).


### 5.118 기존 현장 요청의 함수·실행 전환 대조

PYJOIN에서 예비를 제외한8구간·24요청의 원 HTTP·native clock·스레드 세대·선택 ETW를
이전 manifest와 대조했다. 36.3290ms ON은 연결·준비29.2955ms/route4.8077ms,
수집기 배정1.1398~1.1418ms/Ready 전환 후 재배정 구간29.6839ms다.
37.6214ms OFF도 Ready 전환 후 구간36.3231ms/배정1.2972~1.2994ms였다.
연결 값에는 시계·객체 준비가 포함되며 CPU 배정·전환 후 구간은 인과 확정과 구분한다.

ON12요청 중7개에 Python 읽기9구간이 겹쳤다. route 완전 포함0/부분 겹침 가능1,
읽기 실패 겹침1요청이며 나머지 공백을 추정하지 않았다. 가장 느린 ON의 `_poll`/`_worker`
세 읽기는 route 앞 연결·준비 구간에 겹쳤다. 표본 수를 지속 시간이나 GIL 원인으로 해석하지 않는다.

두 CPU 경쟁 배정 합계는 ON에서 System13.9693/Explorer12.0001/reader8.4960ms,
OFF에서 smart-factory PID15700/17632의23.4696/13.9761ms와 backend18.3665ms였다.
원 thread→PID 대조와 Windows XML process 이름을 구분했다. 대부분 DCEnd 한 건만 있어
이름·세대의 완전 결합과 개입 효과는 미확정이다. 원문 XML의 해시는 이전 봉인 값과 일치한다.

분석/독립24요청 적분/Ready 정산24/두 XML 추출 exit0,경계9조건 및 최종 Ruff F/diff를 확인했다.
첫 Ruff의 미사용 import 실패를 보존했다. 전체 ETW 스키마 경고와 원120분FAIL은 유지한다.
서버·제품·설정·우선순위·백업 변경 없이 기존 trace의 wake-caller 스택 결합으로 후속 범위를 좁혔다.
기존 THREADLINK/OUTSYM/파일 생성·fsync 비교는 반복하지 않는다. R1~R6와 출시HOLD 유지.
[근거·방법·한계·다음 단계](C:/Users/user/Desktop/SmartFactory/PYJOIN_20261018_900730b0/review.md).


### 5.119 스레드 호출 문맥·그래픽 경로 대조

WAKEPAIR는 기존02-ON/05-OFF 요청의 Ready456건과 직전 문맥114건을570개 유일 호출 문맥에
연결했다. Image27,778건/Process486건/스택980조각을 독립 비교해 누락·초과0, 검산17,521항목과
중복/부재/충돌6거부 조건을 확인했다. 미확정 프레임31개와 XML 스키마 경고는 보존했다.
ON 탐색기에는 thumbcache/windows.storage/RPC 및 shell32/UI 경로가, OFF 앱에는
d3d11/dxgi/d3d10warp 경로가 보였다. WARP 사용자 스택 연결은 ON6/OFF24건이며 지속 시간이 아니다.

기존221.0337ms 요청의 PID17632 일반 CPU73표본 중11개가 WARP를 포함했다(첫 Ready3/둘째7/밖1).
PID15700은29개 중0, DPC1개는 앱 귀속에서 제외했다. 검증된102표본의 주소/모듈 순서를 재사용했고
새 ETL 해석·심볼 다운로드는 하지 않았다. 후보0732c8e main.js50행의 가속OFF는 PR144 시작 최적화다.
후속은 동일 격리 화면에서 실제 backend 차이를 확인하는 그래픽 비용 비교 준비이며 운영 변경은 없다.
제거 후보에는 기존 설치 앱20회 시작 gate가 필요하다. 단독 원인이나 개선 효과는 미확정이다.

새 오프라인 decoder build/두 export/수정 분석/독립 검산/과거 재집계 exit0. 초기 분석형식 누락과
재집계 상태 이름 오류의 exit1을 보존했다. 제품/서버/설정/백업 변경 없이 원120분FAIL 및R1~R6HOLD 유지.
[검증·원문·제약](C:/Users/user/Desktop/SmartFactory/WAKEPAIR_20261018_72c71e5d/review.md).


### 5.120 개발 PC 후보 화면 그래픽 비교

GPUCHECK는 후보50파일을 고정해 실제 software(Microsoft Basic Render Driver)/default(RTX3060)
경로를 확인하고,6초 준비+30초 네 회차를S/D/D/S 순서로 수행했다. 전체 앱 CPU초는2.336990,
3.965026,3.941892,2.249473이었다. rAF25ms 초과0/long-task0, 모의health 최대3.5594ms다.
가속 기본값 변경의 비용 개선 근거가 아니며 현장 지연 원인도 확정하지 않았다.

입력220회·누적CPU값496개·동일세대/창포커스/전체차트영역/API/소유Job 정상종료를 검산했다.
각 실행HTTP177건/data70/image36은 같았으나 측정 경계 내 data는60/60/59/59건이다.
history 호출0, synthetic 영상/수치, 장비UNKNOWN·일부 기본layout 잘림, observer 부하 미분리,
공유캐시·12CPU개발PC·실제backend부재를 한계로 남겼다. 첫 준비의API/시각 누락과 두 번째zoom
미적용은 보존하고 수정R3의 네 회차만 비교했다. 제품/서버 변경 없이 원120분FAIL/R1~R6HOLD 유지.
후속은 기존 현장GPU/드라이버 식별 정보의 적용 가능성 확인이다. 같은 모의 비교를 반복하지 않는다.
[방법·결과·한계](C:/Users/user/Desktop/SmartFactory/GPUCHECK_20261018_fcf9b609/review.md).


### 5.121 현장 그래픽 장치와 프로세스 역할 연결

FIELDGPU의 승인 SSH 3회 exit0으로 Intel UHD610/30.0.101.1273,Celeron G5905/2CPU를 확인했다.
GPU17632의 WARP 선택, renderer15700의 GPU 합성 OFF/래스터1과 정밀 생성 시각을 읽었다.
현재4프로세스 수명이 기존221.0337ms trace를 포함하고 backend14012는 기존 native 세대와 같다.
R2STACK 봉인 manifest→원 trace header/clock 입력 해시로 연결했다. 과거 WARP 표본은 GPU 프로세스에
연결되지만 exclusive CPU 시간·단독 원인·가속 전환 효과는 확정하지 않았다. 개발 RTX3060 결과는 현장 대체 불가다.
06:43KST Smart Factory 전면 Running과60180·28을 관찰했다. 새 사용자 확인이나 metadata 변경은 없다.
제품/설정/드라이버/설치/백업 변경 없이 원120분 FAIL/R1~R6 HOLD를 유지한다.
[읽기·검산·후속범위](C:/Users/user/Desktop/SmartFactory/FIELDGPU_20261018_a73c09d2/review.md).


### 5.122 현장 Intel 화면 비교의 결과와 불완전 CPU 기록

FIELDRENDER는 검산한 후보frontend50파일/Electron44.3.0으로 실제IntelUHD610과software를
S/D/D/S,6초준비+30초씩 비교했다. 네 회차 기능·포커스·요청·정상종료/Job잔류0은 확인했다.
전체CPU초software5.071587/5.207482,default2=5.952364다. default3는일시GPU20252의
최종CPU가 없어 strict검사exit1이며 전체 합계 미확정,고정 프로세스 소계만5.463628로 남긴다.
정확한Intel중앙값은 계산하지 않고 실패한 회차를 대체하지 않았다. 관찰 길이를 맞춘 소계도
두software값보다 커,이 결과로 운영 가속 기본값을 바꾸지 않는다. 지연 인과관계는 미확정이다.
현재 화면의 위젯·512×288반복JPEG/고정수치 범위이며 화면밖timeseries·실제backend·시작QA를
검증하지 않았다. 모의health는 실제gate대체가 아니다. 첫 준비·전달·회수 실패도 원본을 보존했다.
최종임시작업/소유프로세스0,기존main17996동일세대Running과07:28KST전면60180·28을 확인했다.
해당metadata는관찰값이며새사용자확인이아니다. 제품/설정/드라이버/설치/전체백업변경없음.
원120분FAIL/R1~R6HOLD유지. 기존221ms보존trace의미확정경로검토로돌아가며같은비교를반복하지않는다.
[근거·실패·검산](C:/Users/user/Desktop/SmartFactory/FIELDRENDER_20261018_e19b0d46/review.md).


### 5.123 정확한4c 소스 재현과 과거drop15 직전 적체 연결

R5FORENSIC은기존5manifest175파일·원문11표본을검산했다.10/09KST18:55:28/45/18:56:03의
완료93,439/fact4,091,224·SHA는같고queue32/47/63,접수93,472/93,487/93,503이다.
기존factprefix3,997,784보다1개앞서며접수−완료=queue+1이다.마지막drop0은18:56:03,
첫15는19:56:59이고정확한발생시각/함수는미확정이다.사전회수console-pin pending한계도유지했다.
원최종sidecar의begin해시/같은세대,접수=완료94,043·잔류0을확인했으나drop15/integrity미해결은보존했다.
정확한4c Git blob57파일로정상/크기초과15/이미지쓰기대기/보존정리대기4조건exit0이다.
실제259이미지/행SHA와worker종료를확인했다.정리대기는fact1개앞섬을재현하지만현장원인은아니다.
첫Git-probe차단예외와다음Windows audit인수형식검사실패를보존했고R3만4PASS다.
제품/서버변경없는로컬분석이며동일API/성능재시험은하지않았다.R1~R6/출시HOLD유지.
다음은기존R4 index의4,091,224번째fact와인접원본mtime/로그를확인하는것이다.
[근거·검산·실패·한계](C:/Users/user/Desktop/SmartFactory/R5FORENSIC_20261018_c48e9d21/review.md).


### 5.124 과거 대기열·파일 시각·시간당 정리 후보 대조

R5TIMELINE은 기존 인덱스619행과 원본 목록619행을 연결하고 별도로4,333필드 및 메타데이터를
검산했다. 첫 정체의 fact는4,091,224번째, 다음 이미지의 촬영 대비 수정 차이는141.982658초다.
대기열32/47/63의 끝 행과 원문 enqueue 시각도1마이크로초 이내로 맞는다.128번째 대기 행 뒤
촬영 공백은6.846484초다. 촬영/수정 차이2초 초과 집합은131개와96개이며 두 번째 최대113.943019초다.
정체 후보 시작 간격3,727.010308초는 원래3600초 주기 동기 retention 경로와 일치하는 양상이다.
단, 원본 수정 시각은 나중 보존한 메타데이터이며 함수 실행 추적이 아니다. 실제 원인과 drop15의
개별ID·영향은 미확정이다.58분 촬영 공백을58분 저장 정체로 확대하지 않는다.
선택 로그206행의 JSON/일반 텍스트를 함께 처리했다. 최초 형식 가정/시각 비교 실패를 보존하고
최종 대조·별도 검산·Ruff·문서 검사는exit0이다. 제품·서버·새 백업 변경 없이 전체 gate HOLD를 유지한다.
[근거와 검증 방법](C:/Users/user/Desktop/SmartFactory/R5TIMELINE_20261018_a481cd39/review.md).


### 5.125 실제 서버 보존 정리 읽기 경로의 비용

RETSCAN은 실제 서버의 10/14 보존 사본에서 원래 retention AST의 읽기 경로를 실행했다.
8개 날짜 폴더의319,971항목/639,982회 stat에91.094초, CPU53.03125초,
stat 누적21.865865초가 걸렸다. 만료 후보0/실제 삭제0이며 삭제 비용과 계측 오버헤드는 분리하지 않았다.
원10/09 디렉터리 상태·동시 부하·캐시·스케줄링이 달라 과거 drop15의 직접 원인은 미확정이다.
로컬5종 종료/차단 시험과 서버 입력EOF 저장·정리, 실제 측정exit0, 회수4파일 해시를 확인했다.
초기 Python 종료 실패와 SSH Z:미매핑 회수 실패는 보존했다. 수정 도우미/회수/별도 검산/Ruff는exit0이다.
main17996/backend14012는 같은 세대이며 도우미 잔류0,08:13KST Smart Factory 전면 Running을 확인했다.
작업 정보는08:04 이후 필수값 미입력으로 관찰했으며 값을 임의로 넣지 않았다.
현재 작업 트리의 retention 네 함수 AST는 같지만 설치본 전체 동일성 검증을 대신하지 않는다.
제품·설정·설치·새 백업 변경 없이 원120분FAIL/R1~R6/출시HOLD를 유지한다.
[범위·실패·검산·후속](C:/Users/user/Desktop/SmartFactory/RETSCAN_20261018_3b876b21/review.md).


### 5.126 보존 정리 분할 처리와 수명 관리의 로컬 검증

RETINC은 소스80fee9aa에 보존 정리 분할 처리를 저장했다. 호출당256단계/monotonic10ms의
협력적 예산과 scandir 지연 순회, 기존 큐의 유휴 진행, 종료·writer/설정 교체 시 iterator 닫힘을 적용했다.
단일 OS 호출의 hard 상한은 아니다. 주기·strict mtime cutoff·관리 파일 조건·캡처/대장/큐 회계를 유지한다.
수정 전2회귀는601개 전체 확인/20회 확인으로FAIL이었다. 첫 후보의 빈 연·월 폴더 삭제 차이를
별도 대조로 발견해 실패를 보존하고, 관리 날짜 폴더를 제거한 부모만 정리하도록 보완했다.
최종 신규13회귀를 포함한 전체 백엔드950건(1skip),Ruff,mypy9파일,범위 검산,staged diff검사는exit0이다.
기존 writer20메서드/helper15개/큐 집계 AST가 같고 최종 소스 해시와 로컬 커밋을 연결했다.
운영 서버 적용·새 경로의 실제 규모 성능·전체 패키지 QA는 미완료이며 다른 기존 작업 트리 변경도 남았다.
원120분FAIL/R1~R6/출시HOLD와 미서명 정책을 유지한다. 서버/설정/설치/새 백업 변경은 없다.
[변경·실패 보존·검증·다음 단계](C:/Users/user/Desktop/SmartFactory/RETINC_20261018_4385cc9c/review.md).


### 5.127 Windows 정밀 시계 보완과 서버 오프라인

RETBOUND 사전 계측에서 개발Python3.12.6 monotonic의GetTickCount64/15.625ms 해상도를
확인해, 소스a21e963d의10ms 예산 두 호출을QueryPerformanceCounter 기반perf_counter로 바꿨다.
저해상도 시계가 정지한 회귀는 수정 전20개/기대2개FAIL(exit1),수정 후통과했다.
제품 나머지AST 불변과 최종13회귀·백엔드950건(1skip,308.369초)·Ruff·mypy exit0을 확인했다.
최종R2 도우미7조건과 공유5파일 SHA/선택6함수AST/PS5.1구문·ACL객체 검산을 마쳤다.
로컬합성1,200파일은9회 호출,최대10.0594ms/148단계,열린scandir최대4/종료0이다.
작은 합성시험이며 실제 캡처 스케줄·삭제 비용·서버 성능은 미검증이다.
Chrome은마지막온라인08:14/오프라인,SSH는10.078초timeout(exit255)이다. 서버 최종복사·실행·
운영화면복귀가 미완료여서 연결 복구를 요청했다. 서버/설치/설정/전체백업 변경은 없다.
원80fee9aa 전달묶음은 대체관계만 별도기록하고 보존했다. R1~R6/출시HOLD 유지.
[근거·수정 전후·전달 상태·후속](C:/Users/user/Desktop/SmartFactory/RETBOUND_20261018_2f683e7a/review.md).

### 5.128 기존 느린 요청의 우선순위 변경 기록 대조

R2PRIORITY는 기존221.0337ms 요청의 Thread opcode48/49 이벤트3,905건을 XML 필드와
별도 native ETL의 원시payload·QPC·CPU·header PID/TID까지 대조했다. 최종exit0,손상/누락/중복
등9조건 거부,도우미Ruff exit0,정리 후 소유 프로세스0이다. 첫DLL 해시 비교 키 오류는 보존했다.
64.4168/127.5472ms Ready구간에 수집기TID11168의 변경 이벤트는 없다. 두 번째 구간에는
다른 두TID의4이벤트가 있다. 수집기 CSwitch에는8·10·11이 관찰되므로 이벤트 부재가 동적
우선순위 불변을 뜻하지 않는다. rundown기본8은 나중 스냅샷이고 생성 세대·조정 원인은 제한적이다.
제품·서버·설정 변경 없이 기존120분FAIL/R1~R6/출시HOLD를 유지한다. SSH exit255 timeout으로
실제 서버 계측과 운영화면 복귀는 미완료다. 연결 후 준비된RETBOUND_R2 최종전달/EOF검증/계측을 잇는다.
[원본·검증·실패·해석 한계](C:/Users/user/Desktop/SmartFactory/R2PRIORITY_20261018_73ac19de/review.md).

### 5.129 Clean 후보 준비 중단 확인과 다운로드 의존성 경로

후보 a21e963d의 R2 루트 npm 설치는 exit0이고, frontend는 900초 timeout/정리0이었다.
R3는 이후 exec 핸들·worker·관찰된 자식이 없어졌으며 terminal/summary도 없다.
01:32 UTC 실제 부재 확인을 `r3-interruption-review.json`에 보존하고 종료 코드는 미상으로 둔다.
새 R4가 같은 소스와 루트 설치를 확인해 frontend부터 재개 중이다. 전체 health와 설치본은 미완료다.
사용자는 서버 전원을 끈 상태라고 알렸다. 서버 사용 가능 통보 전 원격 재시도를 멈추고
독립된 로컬 검증을 진행한다. 서버 확인 요청은 답변 완료이며 새 권한 승인을 요구하지 않는다.

현재 lock npm 감사는 root9/frontend7, native exit1이며 10월13일 원문과 각각 바이트/SHA가 같다.
독립 권고는4개이고 16개 패키지 항목 모두 dev지만 실제 노출이 없다는 근거로 삼지 않는다.
설치된 GotDownloader의 로컬 시험에서는 기본 옵션 두 다운로드의 CachePolicy 생성0,
명시적 cache 양성 대조의 생성2/실제HTTP1을 확인했다(native exit0,7.157초).
선택 입력 전후 SHA·다운로드 내용·listener 종료도 확인했다. 첫45초 timeout은 보존했다.
기본 downloader 경로의 제한된 근거이며 실제 빌드 옵션·배포 payload와 나머지 감사 항목은 미검증이다.
R1~R6/출시HOLD/원120분FAIL을 유지한다.
[진행·중단 기록](C:/Users/user/Desktop/SmartFactory/PKG30_PREP_20261018_5cc40d8e/review.md),
[시험 근거와 해석 한계](C:/Users/user/Desktop/SmartFactory/PKG30_PREP_20261018_5cc40d8e/dependency-audit/reachability-review.md).

### 5.130 서버 재연결과 기존 데이터의 분할 순회 확인

사용자 승인으로 RETBOUND_R2 5파일45,877바이트만 SSH 전달·해시 검증하고 기존10/14 보존 데이터를 재사용했다.
서버 EOF는 STOPPED/CONTROLLER_EOF(의도한SSH1), 순회4개 모두 닫힘·도우미0이었다.
전체 읽기 투영은100.625초/CPU53.578125초, 날짜 항목319,971개/stat639,942회/7,630호출로 완료했다(SSH0).
최대60단계로256 제한을 지켰고 순회11개 모두 닫혔다. 실제 삭제0/오류0, 빈 폴더 제거8회는 억제했다.
호출 p95 22.9108ms/p99 42.4616ms/최대1,031.8582ms로 엄격한10ms 상한은 아니다.
실제 큐 유휴/캡처 스케줄·삭제 비용을 제외한 연속 호출이며 과거 RETSCAN 시간과 직접 비교하지 않는다.
소스6함수AST·분할 집계·콘솔/서버/공유/로컬 결과SHA를 대조했다. 원drop15 직접 원인은 미확정이다.
최초 명령 길이 실패를 보존하고 원 스크립트 압축·해시 검증 전송으로 보완했다. 최종 stderr는 진행 CLIXML이다.
서버 main17896/backend17684는 같은 세대이며09:31KST 기존0732c8e8 수집·유효 metadata60390/2를 관찰했다.
새 설치·설정 변경·전체 백업은 없다. 화면 도구 초기화 실패로 전면 복귀/화면 확인은 미완료다.

### 5.131 FAT32 실패 재현과 같은 소스의 NTFS 전체 health

E: 후속 health는 frontend437통과, backend950 중1실패/10오류/1skip으로 종료1이었다.
같은 종료 증거 hardlink 발행은 C:성공/E:WinError1, Git fixture config는 C:0/E:128로 재현했다.
제품 안전장치를 바꾸지 않고 C:의 a21e963d clean clone/고정 lock에서 전체health를 다시 실행했다.
최종 `npm run health` exit0/479.453초: frontend42파일437검사, backend950검사(1skip),
Electron100/의존성15 및 typecheck/lint/QA selftest 통과. 전후 HEAD/clean·의존성 일치, 소유job잔류0이다.
기존 E: 실패와 원 작업 트리27개 변경 경로를 보존했다. 설치/현장/복구 QA와는 별도 결과다.

### 5.132 출처를 분리한 미서명 설치본과 실제 패키지 백엔드

첫 빌드에서 Codex runtime 경유DLL43개를 확인해 실행하지 않고 보존했다. 명시적 PATH/PYTHONPATH 분리 후
PyInstaller 출처3,620개 중 허용 경계 밖0을 확인했다. NSIS의 PowerShell PATH 누락 실패도 보존하고
이미 검증한 frontend/backend를 재사용해 패키징만 재개했다(최종native0/job잔류0).
최종1.0.30/a21e963d 설치본164,147,965바이트의 SHA256은
`d0e28e3e1636e00d2a188dfa61d4cf1a85a3f5ab724d3e0526ad5b83bb6318b1`이다.
NotSigned는 승인된 정책이며 서명PASS가 아니다. 추출1,864파일·frontend50파일 양쪽 위치·backend
manifest/provenance·ASAR11소스를 대조했다. 실제 추출 백엔드의 합성loopback5요청/시계 결합,
정상 종료0·listener/자식0·강제 종료 없음과 실행 후 payload 불변을 확인했다.
전체 Electron·설치/업그레이드/복구·새 후보 현장15분/120분 QA는 미완료다. 기존 npm 감사와
물리 comparator NOT_TESTED, 원120분FAIL/R1~R6/출시HOLD를 유지한다. 롤백 기준도 변경하지 않았다.
[근거·실패 보존·검산·동일 설치본 후속](C:/Users/user/Desktop/SmartFactory/RESUME_20261019_b3ea61d4/review.md).

### 5.133 최종 설치본의 감사 패키지 포함 여부

같은 a21e963d/d0e28e3e 설치본 ASAR16파일은 앱과 tree-kill1.2.2만 포함한다. 기존 감사 대상16개
패키지는 ASAR와 바깥 node_modules 경로에서 발견되지 않았다. 같은 config/소스/고정 의존성으로
별도 출력에 관찰 빌드한 주 화면4,577모듈/Worker64모듈에도 해당 패키지가 없다(external module0).
JavaScript34개 전부의 그래프 코드SHA가 최종 파일과 같고, 전체50파일이 원 설치본 frontend와 같다.
독립 Python 경로 분석·50파일/installer/20입력pin 검산, Node syntax·Ruff·최종 실행은exit0/job잔류0이다.
Windows ASAR 경로 실패, 첫 그래프의 Worker 누락, 후속 Vite hook 전 코드SHA 불일치를 보존했다.
R4는 Worker 관찰과 post hook에서 모든 JS 최종SHA 일치 조건을 유지해 통과했다. 기존 Zod 주석 경고2개도 남겼다.
10/19 네 GitHub 권고를 다시 읽었으며 개발 lock 감사 root9/frontend7은 해소하지 않았다.
실제 앱 JavaScript 미포함의 근거이며 빌드 시 모든 외부 입력·다운로드 옵션의 안전성이나 Electron 전체 보안은 미검증이다.
소스·의존성·설치본·서버 변경은 없고 전체 Electron/설치/복구/현장15분·120분 QA와 원래 gate는 유지한다.
화면 도구 초기화 실패가 계속돼 전체 앱 조작·서버 전면 확인은 미완료다.
[모듈 그래프·실패·한계·현재 권고](C:/Users/user/Desktop/SmartFactory/PKGDEP_20261019_c72e8a16/review.md).

### 5.134 실제 전체 앱 정상 종료와 새 기본 배치 결함

재시작 후 native 도구가 복구돼 같은 a21e963d/d0e28e3e payload의 실제 창에서99001·1을 확인했다.
R2 renderer operational2164.6ms, 창 닫기 후 renderer 준비/backend 종료550.6ms, main/backend exit0,
forced=false, 잔여child/listener/job0이다. 종료trace299행·begin/final SHA, CSV269/269/23행 구조와
payload1864파일/installer 불변을 독립 검증했다(exit0). 기존 개발 프로필은 metadata 대조만 했다.
첫 실행은 외부 socket assertion 뒤 소유 job 강제 정리되어 정상 종료 증거가 아니다. R2 NetLog는
Electron NetworkService의 한국어 사전 GET/redirect를 보여 준다. 전체 loopback/무오류 QA는 미통과다.
EX recv 경고 복구1회, mock ConnectionAbortedError도 보존했다. verifier CSV 개수 가정 오류는
통합2개+observation1개를 정확히 확인하는 수정본으로 보완했고 앱 재실행은 하지 않았다.
새 프로필의 카드 겹침이 기본 창·최대화 모두에서 확인됐다. 기본4행 높이와 콘텐츠 경계가 원인 후보다.
따라서 정상 종료 검증과 화면 QA를 구분하며 다음 Act에서 재현·수정·실제 렌더링 검증을 진행한다.
설치/복구/새 현장15분·120분, 서버 전면 확인, R1~R6의 남은 조건은 미완료. 출시HOLD·승격false.
[실제 로그·화면 기록·후속 결함](C:/Users/user/Desktop/SmartFactory/EL30_20261019_6c17a0e3_R2/review.md).

### 5.135 기본 카드 겹침 수정의 로컬 화면 검증

3e96342b에서 7파일을 변경했다. 수정 전 회귀 검사는 8개 중 1개 실패(exit1, SPOT 92px),
수정 후 관련 14개와 전체 439+9개가 통과했다. 타입·린트·빌드 exit0이다.
실제 일반/최대화·Scenes 편집 화면에서 겹침 해소와 작업 정보 버튼/그래프 접근을 확인했다.
Native 제품 변경 경고 테두리도 표시됐다. 다만 편집 모드 전환 시 경고가 ‘적용됨’으로 바뀌어 지속성은 미통과다.
changeNeeded 로컬 state와 최초 load의 false 설정, Native/Scenes 재마운트 경로를 확인했다.
이 위젯은 이번 commit에 포함하지 않았다.
시험 main/backend exit0, 강제 종료 false, backend 종료 793.3ms, job/포트/잔여 child0이다.
CSV 893/893/71행 구조와 종료 증거의 독립 검증도 exit0이다.
기존 수정 27파일·원 payload 1,864파일·installer는 불변이다. 기존 앱 프로필은 metadata 대조만 했다.
새 frontend와 기존 a21 backend의 혼합 시험본이며, 최종 후보/설치/복구/현장 QA 통과가 아니다.
최초 HTTP4xx 2건도 보존한다. 한국어 사전 GET/redirect가 있어 전체 loopback 통신도 아니다.
Windows Sandbox/VM 없이 별도 경로·모의 장비·소유 job으로 시험했다.
모든 프리셋/화면 크기·경고 상태 지속성·최종 설치/복구/새 현장 15분·120분은 미완료다. 출시 HOLD·승격 false.
[근거와 검증 범위](C:/Users/user/Desktop/SmartFactory/LAYOUT_20261019_d485f920/review.md).

### 5.136 편집 상태 소실 재현·수정 및 실제 화면 왕복

685dde94의 3파일 변경으로 제품 변경 경고·미저장 필드·진행 중 저장 오류를 분기 상위에서 유지한다.
추가3검사는 수정 전 모두 실패(exit1), 수정 후 관련26개 및 전체442+Node9개가 통과했다.
타입·린트·Vite build exit0이다. 해당 상태 보존 회귀 요구3개 중3개를 검사했으며 전체 R1~R6 완료율이 아니다.
실제 시험 Native 경고→Scenes 경고, Scenes 입력99002→Native 미저장99002를 확인했다.
적용하지 않고 닫아 저장값99001·1과 빈 이력을 확인했다. main/backend exit0, forced=false,
backend 정상 종료308.5ms, job/포트/잔여child0이다. 기본 프로필은 metadata 대조에서 불변이었다.
기존 dirty27파일·원payload1864파일·시험payload1865파일·기존installer를 대조했다.
독립 검산 첫 실행의 cp949 출력 실패를 보존하고 ASCII 출력 R2 재검산 exit0을 확인했다.
이 결과는 기존a21 backend+수정frontend의 격리 화면 시험이다. OS Sandbox/VM·모든 통신 차단은 아니다.
Electron 사전 GET/redirect가 기록됐다. 최종685dde94 설치본·설치/복구·새 현장15분/120분은 미완료다.
서버 변경·전체 백업 없음, 기존 물리 경계NOT_TESTED와 과거120분FAIL 유지, 출시HOLD·승격false.
[실행·독립 검산·한계](C:/Users/user/Desktop/SmartFactory/EDITSTATE_20261019_c07dba0f/review.md).


### 5.137 최종 clean 후보의 소스 검사·실제 NSIS 내용·백엔드 검증

685dde94 clean checkout의 npm run health는 실제 exit0이었다. 의존성15·Electron100·Node9·Vitest442/42파일,
backend950개(1skip), 타입·린트 및 PowerShell QA self-test6개를 확인했다. 전체 출력·로그 해시를 대조했다.
미서명 v1.0.30 설치본2965d4c0cb98bdedb4357c308f9c23d4b5f319cf259b8639201669650b0e9303,
164,149,766bytes를 만들었다. 실제 내부1866파일·frontend두 위치51파일·backend1738파일·ASAR/commit 일치,
빌드 외부 출처0, 준비/빌드/payload/runtime wrapper exit0·잔여job0이다.
추출 backend의 일반1·진단4요청과 native clock 결합4개, 인증 종료exit0·잔여child/listener0을 확인했다.
이번 검사는 개발 Windows 별도 경로에서 수행했고 OS Sandbox는 아니다. 과거2026-10-13 설치·복구는
실제 offline Windows Sandbox였음을 원기록으로 재확인했다. 새 후보의 실제 Electron UI·설치/복구·현장QA는 미완료다.
서버 변경·전체 백업 없음. 경고·skip·기존 물리NOT_TESTED/120분FAIL을 보존하고 출시HOLD·승격false를 유지한다.
[실행 결과·격리 수준·남은 검증](C:/Users/user/Desktop/SmartFactory/FINAL30_20261019_5a20da2d/review.md).


### 5.138 최종 후보의 실제 오프라인 Sandbox 설치·복구와 종료 검산

같은685dde94/2965d4c0 설치본으로 깨끗한 설치·제거·업그레이드·재시작·0732 직전 후보 및541d 롤백 복구를 실행했다.
설치6회/제거1회 exit0, 교체4회 데이터·설정·프로필 동일, 다섯 앱/backend 정상 종료0·잔여child/listener0이다.
CSV5·이미지5 검사 exit0, 이전CSV/JPEG 보존·fact접두부 추가·후보 진단8개 native clock 재검산을 확인했다.
179개 검산 중178통과/1실패: 롤백1.0.26의 종료 중 SPOT 이미지502오류2건이다. 신규 후보 실행에는 해당오류가 없다.
Native→Scenes 변경경고·Scenes→Native 미저장 빈 입력/필수값경고 유지, 재시작 저장값99001·1을 확인했다.
99002 type_text 입력은 채워지지 않아 숫자 draft 검증 성공으로 기록하지 않는다. 모든 프리셋/해상도 검증도 아니다.
초기 도우미의 잘못된 영문 창 제목 비교 실패와 Pillow 없는 이미지검사 실패를 보존했다. R2제목회귀4개/구문검사0,
고정 빌드 환경의 실패 이미지검사만 재실행0이다. 최초 실패 실행의 native 종료는 검증된5회에 포함하지 않았다.
실제 실행793.062초/native·guest·host0, 최종review는 알려진 롤백오류로1, 독립검산0이다.
앱/백엔드/fixture/지정포트0 확인 후 해당Sandbox만 폐기하고 출력4630파일56,349,102bytes를 검산했다.
서버변경·전체백업·롤백기준갱신 없음. 현장15분/120분 미완료·물리NOT_TESTED·과거120분FAIL/출시HOLD 유지.
[실행·오류·한계·후속](C:/Users/user/Desktop/SmartFactory/SB30_20261019_6b7c91d2/review.md).


### 5.139 최종 후보 도우미 검증과 승인된 서버 중복9개 정리

최종685dde94/2965d4c0의1866파일을 기준bb8d9e36에 결합하고 기존0732c8e8과 같은1.0.30을 명시적으로 구분했다.
별도 helper commit45fb16a9(15파일)의 정확한 추출 소스에서 Python85·PowerShell122=207검사/native0,
PyInstaller0·소스/의존성 불변을 확인했다. RUN30F frozen실행6건은 정상0/거부조건1을 보존하고
142입력/패키지 불변·소유job잔류0·강제 종료false다. 관리자 ACL 적용과 실제 현장 검증은 미실행이다.
제품은 재빌드하지 않았고 원 작업 트리의 기존 변경·HEAD/index를 유지했다. 실제 OS Sandbox와 로컬 도우미 검사를 구분한다.
사용자가 승인한 ZIP1개+진단사본8개만 서버에서 제거했다. 로컬 보존9개와 서버9개의 크기/SHA를 다시 확인하고,
서버 경로·reparse·ADS 경계를 검사했다. 삭제 동안 로컬 보존 사본을 잠갔고 종료 후 전수 SHA도 일치했다.
삭제6,023,752,648bytes/native0, 실제free7,477,575,680→13,501,239,296bytes(12.57GiB)다.
후속9파일부재/native0, 기존main17896/backend17684·REAL/running·0732c8e8 및 운영/기존cold 폴더 존재를 확인했다.
첫 명령 길이 실패와 후속 읽기 인코딩 오류를 보존했으며 추가 삭제·설치·설정·전체 백업은 없다.
새installer+RUN30F 전송만 감안해도 reserve 초과분은133.56MiB다. 관찰manifest·운영 증가를 더 고려해야 하므로
공간조건 통과를 확정하지 않는다. 현재 제품/금형 확인, 서버 최종 전달/화면 전면 표시, 최종 설치·현장15분/120분은 남아 있다.
물리NOT_TESTED·과거120분FAIL·Sandbox롤백502오류·R1~R6/출시HOLD·승격false와 롤백 기준을 유지한다.
[정확한 보존/삭제 목록·실패 기록·검산·후속](C:/Users/user/Desktop/SmartFactory/F30FIELD_20261019_4ae6b901/review.md).

### 5.140 renderer 소실 후 종료 timeout 재현과 수정

10:53KST renderer 준비15초 timeout 뒤12:42 서버에는 main/GPU/network/backend만 남고 renderer는 없었다.
백엔드는REAL/running/HTTP200이지만 최근60초 화면 요청은 없고 마지막 이미지 성공은10:50:39였다.
제한된 Windows 사건 조회0건으로 renderer 소실의 근본 원인을 확정하지 않는다.
실제 Electron44.3.0에서 renderer 소실 전/준비 중 두 조건 모두 창과webContents가 살아 남아 같은 timeout을 재현했다.
8de06431의3파일 변경은 crashed/gone 상태의 화면 준비 대기만 종료하며 backend 인증/drain/closeout을 보존한다.
추가3회귀는수정전FAIL→수정후PASS, 관련30/전체Electron103 exit0이다. 실제Electron2조건도완료/native0,
감독자강제정리false·잔류job0을확인했다. 실제CSV/backend대신대체함수인시험범위는현장정상종료로확대하지않는다.
최초fixture listener수오판FAIL을보존하고실제baseline대조R2로재검사했다. 별도commit/activeHEAD·index/기존변경을보존했다.
새제품빌드·설치·복구·현장15분/120분·운영화면복귀는미완료, 서버설치/설정/종료/백업변경없음.
추가확인:preservation scope는0732→신규후보계약이없고14.25GiBreserve가필요하다. 설치12.25GiB와혼동하지않는다.
기존물리NOT_TESTED·120분FAIL·롤백502·출시HOLD·승격false유지.
[재현·변경·검증·남은 조건](C:/Users/user/Desktop/SmartFactory/SDREPRO_20261019_3c59b1a7/review.md).


### 5.141 renderer 종료 수정본의 clean 빌드·패키지 실행 및 현재 세대 관찰 도우미

8de06431 clean worktree의 npm run health는510.234초/exit0이다. 의존성15·Electron103·Node9·Vitest442/42파일,
backend950개(1skip), 타입·린트·QA self-test6개를 확인했다. build/payload/runtime도exit0·잔류job0·강제정리false다.
미서명1.0.30 설치본은164,150,064bytes,
SHA256 `f1b6d4d843504e09410cd90dcd309a0e485e9fd7a59a524b64941c61719f5a32`이며 실제 내부1866파일을 실행 후에도 전수 검산했다.
실제 추출backend 일반1/진단4요청과 native clock결합4건·인증 종료0·잔여child/listener0을 확인했다.
이는 별도 경로/프로필의 개발Windows 시험이며 OS Sandbox가 아니다. 새 설치본의 실제Electron/설치/복구·현장QA는 미완료다.
별도 helper d064c381은 현재1.0.30/0732와새정책만 허용한다. 기존코드거부exit1 재현→23검사exit0을 확인했다.
설계5.102의 로컬요구3개(정확한현재세대허용,다른세대거부,패키지/호스트방어)3개를 검사했다. 전체R1~R6 완료율이 아니다.
14.25GiB reserve·원본읽기·정상종료대기·패키지잠금은 유지했고 서버실행/설치본선택은 하지 않았다.
사용자보고:웹dashboard접속가능,Electron Ctrl+R복구안됨.13:12SSH에서도기존main17896/backend17684·HTTP200,
renderer부재를확인했다. 소실원인은미확정이며백엔드응답이전체수집/이미지정상증거는아니다.
서버free13.62GiB는preservation조건미달이다. 추가삭제/백업/설치/종료/설정변경없음. 새설치본결합도우미와현장검증은남는다.
기존685 설치본의Sandbox/도우미결과를새8de에전용하지않는다. 물리NOT_TESTED·120분FAIL·롤백502·출시HOLD·승격false유지.
[새설치본·도우미·검산·남은조건](C:/Users/user/Desktop/SmartFactory/SDREL_20261019_683109b2/review.md).

### 5.142 새 수정본의 실제 Sandbox 장애·설치·복구 검증

8de/f1b6 설치본으로 네트워크 차단 Windows Sandbox에서 설치6회·제거1회·실행5회를 완료했다(native0).
설계5.103의6요구 중6개를 충족했다. 전체 검산178개 중177개 통과, 롤백541d 종료 이미지502오류2건의1항목 실패(exit1)를 보존한다.
후보 두 실행82항목 및 CSV/이미지 독립검증10회는 모두 통과했다. CSV2039행·fact161·이미지407과 종료/drain/누적 보존을 검산했다.
I5에서 소유renderer만 의도적으로 소실시켜 빈 창을 관찰했다. main/backend는 유지됐고 지원되는 창 닫기 뒤
준비0.4ms·backend1102.6ms, main/backend exit0·forced=false·잔류0이었다. 서버의 소실 원인은 미확정이다.
모든 앱/fixture 종료 후 이번 Sandbox만 폐기(native0), 결과1672파일21636036bytes 전후 해시를 검증했다.
GUI 연결 wrapper timeout(exit1)은 별도 기록하며 실제 GUI·matrix·cold/폐기 성공과 구분한다.
13:37 서버 읽기는 기존17896/17684·health200·renderer부재다. 작업정보는60209·2/valid/operator_input으로 확인했다.
이전13:12 원문도 같은 값이므로 제품·금형 응답 대기 표시는 정정한다. 물리 생산값을 별도로 확인했다는 뜻은 아니다.
여유13.57GiB는preservation14.25GiB 미달. 서버변경/새백업/추가삭제없음. 새8de 결합 도우미·서버복구/설치·현장15분/120분은 남는다.
물리NOT_TESTED·과거120분FAIL·롤백오류·출시HOLD·승격false와 기존 롤백 기준을 유지한다.
[실행·검산·제한·후속](C:/Users/user/Desktop/SmartFactory/SBLOSS_20261019_0ce84e31/review.md).

### 5.143 새 후보 현장 도우미 계약과 남은 검증 실패

8de/f1b6에 결합한 별도 helper commit `be0c4302596160753246af14bc4c13bb7b888940`을 만들었다.
기존 작업 트리 소스는 유지하고 d064/45fb 출처 94파일 중 15파일의 계약·검사를 변경했다.
새 후보를 기존 코드가 거부하는 음성 대조(exit1), Python AST와 PowerShell 구문 검사를 확인했다.
커밋의 Python 검사 93개 중 92개가 통과했고 1개가 실패했다(exit1,210.221초).
실패는 이전685 후보의 closed-copy 검사에서 CSV validator 자체 exit0 뒤 소유 job의 active_processes가1로
관찰돼 `command-descendants-remain`을 보고한 경우다. 정리 뒤 active0이며 실패를 PASS로 바꾸지 않는다.
이 원인의 확인·보완과 후속 PowerShell 설치/종료/사본 검사, frozen runner 빌드·휴대 패키지 검증은 남는다.
준비 스크립트의 첫 CP949 읽기 실패는 UTF-8 명시로 해결했으며 이전 실패 기록을 보존했다.
서버 실행·설치·현장 QA는 수행하지 않았고 출시 HOLD·승격 false를 유지한다.
[정확한 소스](C:/Users/user/Desktop/SmartFactory/F8DE_20261019_ca0746b0/helper-source.json),
[검사 원문](C:/Users/user/Desktop/SmartFactory/F8DE_20261019_ca0746b0/committed-checks/python-tests.stderr.log).


### 5.144 서버 SmartFactory 중복 정리 승인 실행

사용자의 추가 삭제 승인에 따라 Desktop SmartFactory의 중복 5457파일/4674564472bytes(4.35GiB)와 빈 앱 폴더369개를 제거했다.
대표 설치본5개·기존 전체 백업3개·운영 AppData/설치·고유 검증 기록은 보존했다. 보존 파일/ZIP 멤버의 크기·SHA와 대상 바이트를 대조하고
개발 PC 보존 파일을 읽기 잠금한 동안 서버 사본만 삭제했다. 기존 helper/manifest를 재작성하지 않고 복원 위치 대응표를 남겼다.
216707파일·2191폴더 메타데이터 조사에서 명시 제외 외 시간/개수 한도 초과는 없었다. Bec174d 33.73GiB는 보존했다.
경계/reparse/스트림/실행·서비스·예약·바로가기 검사를 거쳤고 삭제3회 및 후검산 native0이다. 준비 단계의 PS/입력 대기 실패는 보존하며
해당 실패에서는 삭제하지 않았다. 자기 읽기 전용 입력 대기 프로세스만 identity 확인 뒤 종료했다.
14:10:43 서버 여유17.71GiB, 동일main17896/backend17684, health/작업정보HTTP200, renderer부재다.
공간 조건은 개선됐지만 화면 오류/신규helper 1검사실패/현장 설치·15분·120분과 출시HOLD·승격false는 남는다.
[삭제·보존·복원 위치·검증 기록](C:/Users/user/Desktop/SmartFactory/CLEAN_SERVER_20261019_A/cleanup-report.md).

### 5.145 내부 검사 종료 확인 보완과 새 후보 현장 묶음 전달

도우미 be0의 worker exit0/job active1 실패에 대해 최초 관찰을 보존하고 원래 제한 안에서 최대2초의
job 종료 확인을 추가했다. 출력 상한·잔류 자식 실패/소유 정리·실제 consumer exit를 유지한다.
실제 로그 공유 오류32/33만 총2초 안에서 재시도하고 다른 오류는 실패 receipt를 남긴다.
별도 helper01ed→0b80d6f4의94소스를 Git blob과 대조했다. Python113 PASS/245.589초/exit0,
PowerShell 설치109·종료17·선택사본12 PASS/각exit0, frozen 빌드exit0이다.
R2의 변경은 PS 테스트 기대값뿐이므로 같은 Python/제품 바이트의113검사는 재사용하고 PS는 재실행했다.
휴대 패키지6실행은 정상0·거부조건1, 소유job0·강제정리false·142입력/패키지 불변을 확인했다.
설계5.104/5.106의 로컬 계약·종료 검사는 충족했으며 실제 관리자 ACL/현장 전체 QA는 별도 미완료다.
제품8de/f1b6 설치본은 재빌드하지 않았다. 기존 실패와 테스트 수정 기록은 보존한다.
사용자의 “항상 승인”을 준비·검산한 검증/배포 준비 파일의 SSH 전달에 적용하고 지침에 기록했다.
25파일206546491bytes를 공유 send 및 서버 FIELD8DE_20261019_f62a1c90에 전달해 전수 SHA를 검산했다.
서버 native 전달/검산exit0, 운영 사용자 읽기 ACL 유지, 여유17.51GiB다. 후속 LibraryOnly/describe도exit0이며
원본 데이터 검사·설치·종료 대기는 시작하지 않았다. 기존main17896/backend17684와 생성 시각이 유지됐다.
14:32 읽기에서HTTP200·60209/2 valid, renderer부재다. 화면 복귀·정상 종료 준비·설치·현장15분/120분은 남는다.
전체백업·추가삭제·설정 변경·운영승격·롤백기준갱신 없음. 물리NOT_TESTED·과거120분FAIL·출시HOLD 유지.
[도우미 수정·실행 원문·전달·남은 조건](C:/Users/user/Desktop/SmartFactory/J8DE_20261019_f62a1c90/review.md).

### 5.146 기존 버전의 화면 다시 읽기와 종료 준비 재시도 검증

정확한0732 lifecycle과 실제Electron44.3.0의 별도 개발 프로필에서 소유renderer 소실을 주입했다.
첫 종료는15002.685ms timeout/backend호출0으로 실패했다. 같은main/window/webContents의 reload API 뒤
renderer PID가바뀌고실제preload IPC응답을받아 두번째종료준비는1.857ms에완료됐다. native/감독자exit0,
정리강제false·잔류job0이다. 설계5.107의 격리경로를확인했으며 실제backend대신대체함수를사용했다.
운영서버/UI클릭/WindowsSandbox/실제데이터종료검증으로확대하지않는다. 제품소스·설치본변경없음.
14:51SSH는기존main17896/backend17684·renderer0·healthrunning/0732였다. 사용자는Alt로도메뉴가안보인다고답했다.
서버의포커스/modal/main응답상태는미확정이며지원화면도구재초기화가다음단계다. 설치·정상종료대기·백업은시작하지않았다.
[시험 원문·한계·사용자 결과](C:/Users/user/Desktop/SmartFactory/UIREC_20261019_a276e615/review.md).

### 5.147 화면 소실 사고 복구의 실제 Sandbox 검증

지원 화면 도구의 재초기화도 Chrome URL 확인 실패로 종료됐다. 기존0732 코드에는 SSH에서
Electron main을 정상 종료/새로고침할 외부 인터페이스가 없고, 백엔드 단독 종료는 main 종료 검증을 대신하지 않는다.
15:01 SSH는 같은 main17896/backend17684, renderer0, 수집 생존이었다. 첫 읽기 명령의 지연은
정확한 PID·생성시각·source hash로 한정해 그 조회만 취소하고 고정64KiB 로그 읽기로 완료했다(exit0/468ms).
운영 제품 상태는 변경하지 않았다. 과거 통신 오류·현재 under_range를 전체 정상 판정으로 바꾸지 않는다.

설계5.108의 대체 복구 가능성을 네트워크 차단 Windows Sandbox에서 실제0732/e72c 설치본으로 시험했다.
정확한 설치1899파일,15표본,의도한 소유renderer 소실,인증오류403 거부,실제backend 정상exit0,
세대별 종료receipt/CSV/fact/image 검산 후main 강제exit15를 native handle과부모Popen으로 확인했다.
main 강제 종료는 정상 종료 QA와 구분한다. 이어같은8de/f1b6 설치exit0·1866파일·데이터/설정/프로필
전후바이트일치를확인했다. 이번교체후앱시작은수행하지않았다.
독립26검사PASS,CSV274행/fact24개/image66개 검사각exit0. 위치열2개빈값경고유지.
host/guest/native0·143.844초,최종앱/모의장비프로세스/시험포트0 후Sandbox폐기0,증거150파일1470416바이트보존.
첫trial의main exit1가정실패와검산기의CRLF/LF비교실패는보존했다. 재시험으로native exit15를확인했고,
검사기소스는CRLF→LF변환만으로Git일치/실행바이트해시별도기록했다. 제품8de는재빌드하지않았다.

설계5.108의 격리·동일제품·인증/세대·저장후정리·강제종료구분·현장미실행6범위를충족했다.
이는정상종료QA나전체출시PASS가아니다. 현재복구도우미는Sandbox전용이며,운영main강제종료에대한
사용자절차변경승인과현장용해시결합/설치gate분기구현·검증이남는다. 기존normal_shutdown_observed를
true로위조하거나조건을자동완화하지않는다. 실제서버복구/원본전수검산/설치/15분·120분/운영승격은미완료다.
[검증 결과와 구체적인 서버 복구 변경안](C:/Users/user/Desktop/SmartFactory/RREC_R2_20261019_dedfa748/review.md).


### 5.148 승인된 사고 복구의 실제 코드·설치 분기 검증과 서버 사전 확인

사용자가 이번 사고의 한정 복구 절차를 승인했다. 5.109에 따라 0b80 기반 별도 helper9133d09b를 만들었다.
기존 정상 종료 조건을 보존하고, 정확한 승인 해시·0732→8de·main17896/backend17684 생성시각·동일 logger와
복구 receipt를 확인하는 별도 설치 분기를 추가했다. 강제 main 종료는 normal_shutdown_observed=false로 유지한다.
Python16/기존 설치109/사고 분기34 검사 모두 최종 커밋 exit0. 실제 Windows worker 정상/시간 제한/부모 종료에서
소유 job 정리와 무관한 프로세스 보존을 확인했다. 소스99파일은 Git 바이트와 일치하며 활성 HEAD/index는 보존했다.
동일 복구 core의 Windows Sandbox 실행은 backend exit0·저장 검산 후 main exit15·8de 설치 exit0과 전체 시험
데이터/설정/프로필 보존을 확인했다. 독립19조건 및 CSV282행/fact24/image66 검사가 통과했다. 위치 열 빈값 경고 유지.
Sandbox127.453초, host/guest/native0; cold 상태에서 폐기하고152파일/1,495,447B 증거를 보존했다.
8파일/16,079,656B를 승인 SSH로 서버 새 RFLD_20261019_76af43e1에 전달·검산했다. frozen 도우미의 실제 서버
inspect는 exit0/job0이며 payload1899+제거 프로그램과 정확한 실행 세대를 확인했다. 결과 IR5c6922bb를 회수·대조했다.
이번 구현의 승인 결합, 동일 세대/설치 확인, 정상 backend drain, 저장 후 main-only 정리, 오류 시 차단,
강제/정상 QA 구분, 기존 설치 계약, 실제 격리 검증은 확인했다. 이는 전체 출시계획 완료율이 아니다.
현재 원본 관찰과 조건부 복구 제어기를 실행 중이며 현장 결과·설치·재시작·현장 QA·운영 화면은 아직 완료 판정하지 않는다.
새 전체 백업 없음, 물리 경계/과거120분/전체 데이터 잔여 조건 및 HOLD 유지.
근거: `Desktop/SmartFactory/RFLD_20261019_76af43e1/review.md` 및 각 원문 로그/해시.


### 5.149 현장 부분 중단 분석과 승인된 main-only 정리 완료

2026-10-19 사용자 승인의 범위에서 진행했다. 정상 수집 종료를 다시 요청하지 않았으며 backend 강제 종료는 없었다.

- 첫 실행 IR16bf5f01은 인증된 정상 종료 후 retained handle exit0 및 포트 부재 검사를 통과한 다음
  PID 존재 검사에서 중단됐다. main 정리는 실행하지 않았다. 원래 HOLD와 원본 관찰 O16e8daa1의
  종료 대기 timeout은 보존한다. 첫 실행 전체가 성공한 것으로 바꾸지 않는다.
- 이후 읽기에서 backend/port가 없고, 같은 세대의 final receipt에 10개 종료 단계와 이미지18,235건
  drain 완료/failure0/drop0을 확인했다. 현재 CSV의 최종 sample_seq는131649였다.
- helper d39ec480은 정확한 이전 실행 파일·요청·preflight·stop intent·hold·supervisor를 외부 해시로
  고정한다. 유일한 오류 지점의 선행 조건으로 native exit0을 추론하며, 이를 새 native 측정이나
  독립적인 exit 영수증으로 표시하지 않는다. 실제 코드 경로 검사와 음성 조건 검사를 포함했다.
- 최종 커밋 검사: Python24, 기존 설치109, 사고 분기46 모두 exit0. 빌드/도움말0,
  개발 PC host 거부는 기대한1. 실제 Windows 프로세스 시험에서 무관한 프로세스를 보존했다.
- Windows Sandbox는 최초 로그온 세션 부재로 2회 실행 전 중단됐다. 공식 connect로 로그인 세션을
  만든 뒤 같은 adapter의 0732 정상 backend 종료→main 정리→8de 설치를 실행했다.
  host/guest/native0,129.219초;19개 독립 검사 PASS, CSV296행/fact24/image65, validator 각각0.
  cold 상태에서 폐기하고151파일/1,514,670B를 검산했다. 위치 열 빈값 경고2개는 유지한다.
- 서버 읽기 검사 IRc8f2bd37 exit0/job0: payload1899+제거 프로그램과 현재 CSV/fact/image의 종료 해시
  및 drain을 검증했다. 이후 IR112bfd7c에서 같은 검사를 다시 통과하고 main17896만 native exit15로
  정리했다. 07:19:29Z에 모든 앱/backend 프로세스와 포트 부재를 확인했고 helper exit0/job0이었다.
- main 강제 종료는 normal_shutdown_observed=false, product_normal_close_pass=false로 기록한다.
  backend_exit_from_retained_handle=false는 이번 이어가기에서 새 native backend 측정을 하지 않았다는 뜻이며,
  별도 backend_exit_evidence.kind=PRIOR_PINNED_FAILURE_PATH에 정확한 이전 근거를 연결했다.

현재 전체 운영 원본의 cold 관찰/재검산을 실행 중이다. 새 전체 백업은 만들지 않는다.
설치·재시작·현장 검증·작업자 화면 복귀는 아직 완료되지 않았다. 출시 HOLD 및 과거 미완료 조건을 유지한다.

주요 근거: helper-source.json, checks/result.json, sandbox/review/review.json,
sandbox/disposal-verification.json, inspection/, recovery/, cold-observer-start.json.

복구 result SHA256: `8b3dd1791d95a08c02bda2275b1836745596d52273613e21b87a81520195039b`.

### 5.150 전체 원본 관찰 중 후속 설치·재시작 절차 점검

exec83421의 기존 cold 관찰이 계속 진행되는 동안 개발 PC에서 후속 절차를 점검했다.
서버 실행 전 재시작 스크립트의 설치 종료 코드 검사가 숫자와 증거 객체를 잘못 비교하는 점을 수정했다.
실제 native 설치 시험의 종료 영수증 형식과 실패/잘못된 형식/다른 build/보존 미완료/이미 시작됨 등을
입력한 26조건이 PowerShell 5.1 exit0으로 통과했다. 예약 작업을 등록하거나 서버 앱을 시작한 검사는 아니다.

외부 attestation helper7b85086b62dae6b4c11f4f3462feba45c2124e7f는 기존 허용 build 목록에 정확한
8de만 추가했다. 최종 커밋 바이트의 회귀11시험 exit0(132.673초); 추가된 8de의 성공 및 잘못된
프로파일·해시·다른 commit 음성 조건을 포함한다. 합성 설정/metadata만 사용했으며 서버 설정은 변경하지 않았다.
활성 HEAD/index는 그대로다. 제품8de 설치본을 재빌드하지 않았다. 실제 새 runtime metadata·정상 종료 후의
설정 결합 패키지는 아직 만들지 않았으며, 서버 설치·재시작·현장 QA·운영 화면 확인도 계속 미완료다.

근거: `Desktop/SmartFactory/RRES_20261019_58d923a1/restart-validation.json`,
`attestation-support/source.json`, `attestation-support/tests-terminal.json`, 원문 stdout/stderr.
재시작 helper SHA256: `05df7d7747248c4e6cd109f9f8a5d3d5936a9af0708d3f1cbfe9a5580bc73ebb`.
외부 attestation helper SHA256: `6bc0fafa921582488b237389ccbc54c15f4ed325ae45b7751772d2c3c62f4b7f`.

### 5.151 새 실행 정보 검토기의 요청 호환성 보완

서버 실행 정보 수집 도우미는8de/v5를 지원하지만 로컬 `review_health_runtime_identity.py`는
기존acaf/v1과1.0.29만 허용하는 누락을 확인했다. 합성 입력의 v2~v5가 `request-build-schema`로
실패하는 재현 후, revision별 정확한 candidate/version과 시작 sequence를 검증하도록 수정했다.
native 생성시각·PID·경로·CIM parent·listener 소유자·외부 해시 검사를 유지하며 현재 생존/QA PASS는 주장하지 않는다.
최종 helper10a6e5cd34fd48d188332702956f61c06967fac8에서 identity11/close20, 총31시험 exit0.
실제 잠긴 파일 CLI 및 동일1.0.30의 다른 build 거부를 포함했다.107개 소스 파일이 해당 Git 바이트와 일치했다.
최초 red 시도는 설치된 사용자 패키지psutil을 숨긴 시험 환경 때문에 import 전 실패했다. 해당 기록을 보존하고
기존 설치 의존성으로 실행한 red-r2에서 대상 오류를 재현했다. 이 환경 실패를 회귀 재현으로 계산하지 않았다.
활성HEAD/index는 보존했고 제품 재빌드·서버 코드/설정 변경은 없었다. 기존 exec83421의 원본 재대조는 계속 진행 중이다.
근거: `Desktop/SmartFactory/RRES_20261019_58d923a1/identity-review-support/source.json`,
`red-r2/stderr.log`, `final/stdout.log`, `final/stderr.log`, `final/terminal.json`, `verification.json`.


### 5.152 사고 복구 후 전체 원본 대조 완료와 설치 절차 시작

2026-10-19 08:23:49Z, Ocb32a611에서375,355파일/230디렉터리/680추가 스트림,
16,930,471,480바이트의 기록과 재대조를 완료했다. exec83421은3716.282초/exit0,
전체743출력행 중739진행행과4정상종료행만 있었고 stderr0바이트였다.
콘솔 result/manifest 핀, 서버 외부 manifest, 개발 PC와공유 사본을 모두 대조했다.
result SHA256은c7ebb55df96b589ebfca48b9a2e6e9fb53d636fe060d294fba6e31050ff1cdda,
observed.tsv는90461a3b6439716fa2857b5c8aaf214ea42df142f12e33056f10f0352e311e80이다.
이는 원본 보존 검산이며 과거 데이터의 내용 QA나 정상 종료 PASS를 의미하지 않는다.

승인된8de 설치 요청051baaf9b263746abefe5738fdb0f934eeebcfb2c56737a9d13506b41cfecabc를
IRES_20261019_58d923a1에3파일로 전달·검산하고 한 번 실행했다. 현재 exec93399가
설치 직전 전체 재검산을 진행 중이며 설치 프로그램 종료/설치 후 원본 검산/앱 재시작은
아직 성공 판정하지 않았다. 새 전체 백업 없이 진행하고 기존 실패 증거·HOLD를 유지한다.
근거: RRES_20261019_58d923a1의 observation/, install-request/, install-start.json과실시간 로그.


### 5.153 수정본 실제 설치 종료와 후속 원본 보존 검사

2026-10-19 08:55:13.4093367Z에 준비된8de/f1b6 설치본을 `/S /currentuser`로 한 번 실행했다.
Je95cb930의 요청 SHA256은051baaf9b263746abefe5738fdb0f934eeebcfb2c56737a9d13506b41cfecabc와일치한다.
installer PID11736의 retained handle 영수증은08:55:46.2609155Z actual_exit_code0,
forced_termination=false다. installed-files/registration 결과가생겼고, 08:57:13Z에는
최종result/hold는아직없으며 같은exec93399가설치후 원본전체검산을실행중이다.
설치전 검산은375,355파일/16,930,471,480바이트로완료한뒤설치가시작됐다.

설치중간상태의첫읽기installation-phase-01은PowerShell자동변수`$Matches`와조회목록변수의
이름충돌로expected-one-owned-install-result에서실패했다. 실제짧은재현에서정규식평가가
배열을Hashtable로바꾸는것을확인하고, 별도이름을쓴phase-02조회exit0으로같은설치의영수증을읽었다.
이조회오류는실제설치명령의실패/재실행이아니며원래로그도보존했다.

앱시작·설치후데이터/설정보존최종검토·화면·현장QA는아직미완료다.
새전체백업/자동롤백/추가강제종료는없다. 출시HOLD와기존롤백기준을유지한다.
근거: RRES_20261019_58d923a1/installation-phase-02.json, install.stdout.log, install-start.json.

### 5.154 수정본 설치 보존 완료와 실제 일반 사용자 실행 확인

Je95cb930의 설치 전후 원본 375,355파일/230디렉터리/680추가 스트림,
16,930,471,480바이트 및 manifest 90461a3b…311e80이 모두 일치했다.
최종 설치 결과 SHA256은9677ed375135b19b933ce64d312a96332e8825f0e4fa0a2910d5a3234a9f4f33,
exec93399 종료0이며24개 결과의 서버·로컬·공유 사본 해시를 검증했다. 설정 SHA256 bb1b8326…ab55a도 보존됐다.

09:24:04Z에 준비된1.0.30/8de를 로그인 사용자 세션3에서 한 번 시작했다.
ST8DE_d742ef42의5개 결과를 검증했으며 임시 예약 작업은 정의만 제거했다. 저장된 task XML은
UTF-16 선언과UTF-8 실제 바이트가 달라 첫 로컬 파싱에 실패했다. 원문은 보존하고 실제 UTF-8 텍스트로
다시 파싱해 등록 옵션을 검증했다. 서버 작업이나 앱 시작을 반복하지 않았다.

09:33:27Z 읽기와09:34:32Z 별도 identity helper에서 main21008/backend12388의 생성시각,
native handle·부모 관계·listener를 검증했다.5개 프로세스 모두 동일 사용자/세션3의 비관리자 권한,
main/backend는 Normal 우선순위다. 실제health는REAL/Running/8de,
CSV Factory_Integrated_Log_v2_20261019_182406.csv의 첫3개 행은1·2·3,
logger는31e53142-b54b-4243-b651-9bd4b32334c7다. 현재 작업 정보는60250·107/operator_input/valid=true이며 임의 변경하지 않았다.
Identity 결과5파일 검토 exit0, result SHA256은65f6555ab441a9c81d72e447367dcb98caccd1e94af6407c45237acf2a4544bf다.

첫 stdin 전달 조회는45초 시간 초과였다. 잔류한 조회용 PowerShell6444의 명령·생성시각·SID·native handle을
대조해 그 프로세스만 정리했다. 앱과backend는 건드리지 않았다. 동일 원격 본문을 압축 명령 전달로 실행하자
exit0으로 완료됐다. stdin/EOF 대기를 원인으로 의심하지만 스택 증거로 확정하지는 않는다.
뒤이은 로컬 CSV-prefix 검토는64KiB 경계에서 잘린 마지막 인용 필드를 끝까지 파싱해 실패했다.
요청 범위인 첫3개 완성 행만 엄격히 검사하도록 고쳐 이미 회수한 바이트로 검토했다. 서버 조회/앱 시작을 반복하지 않았다.

이 결과는 설치 보존과 관측 시점 실행 확인이다. 화면 복귀, 실제 정상 종료, 새 실행 설정 확인값,
15분/120분 현장 QA와 데이터 내용 검증은 아직 미완료이며 정식 출시HOLD/승격불가를 유지한다.
근거: RRES_20261019_58d923a1/installation-review.json, start-review.json,
started-runtime-093311298677/review.json, runtime-identity/review.json, startup-reader-cleanup-01.json.

### 5.155 새 실행의 화면 준비 로그와 설정 확인값 차이 분리

09:37:16Z의 실제health에서 동일main21008/backend12388 및 logger31e53142…의수집을 확인했다.
작업 정보는60250·107/valid=true이며 설정 원본SHA는bb1b8326…ab55a로유지됐다.
현재 전체 성능이나 데이터 내용QA를 통과했다고 판정하지 않았다.

09:38:56Z에 현재 실행의STARTUP 이벤트68개와 SPOT 설정을 읽었다.
세션21008-mvf1s2da-frdokach는window-shown666ms, dashboard-ready1275.4ms,
dashboard-operational-ready8305.5ms를 기록했다. 이는 시작 로그이며 현재 화면 전면 표시의 증명이 아니다.
사용자에게 현재 대시보드 표시 여부만 확인 요청했다. 앱 종료나450초 종료 대기 도우미는 시작하지 않았다.

승인 프로파일의소프트웨어표현15항목이일치했다. 현재 fingerprint는5f6b926c…cbef1,
이전확인값은eb6f4b44…0db71이다. 현재정규화payload에서build만0732로바꾸어계산하면
이전확인값이정확히재현됐다. 따라서이번확인값불일치는build변경으로설명된다.
이분석을실제attestation갱신으로대체하지않는다. 정상종료증거확보후기존승인범위의네확인항목만갱신할예정이며,
Low Signal OFF/물리NOT_TESTED/정식HOLD를유지한다.
근거: RRES_20261019_58d923a1/continuation-runtime-01.json,
renderer-startup-log-01.json 및startup-profile-review.json. 서버설정변경/재시작/전체백업은없다.

### 5.156 사용자 화면 확인 후 정상 종료 관찰의 대기 시간 초과

사용자가 대시보드 정상 표시를 확인했다.12:10:10Z에 기존main21008/backend12388,
logger31e53142… 및configbb1b8326…의동일실행을재확인하고정상종료관찰기를한번시작했다.
exec86038/Re5816026422b는READY_FOR_NORMAL_APP_EXIT 이후450초대기했고,
453.578초에exit1/normal-exit-timeout-no-force로종료됐다. 앱강제종료/설정변경은없다.
HOLD SHA256은eb903067cd93e680c799b218464b94cfcc22035c9af81b30d34c7a921cb62e59,
서버의4개실패증거를개발PC/공유폴더로회수하고콘솔·외부manifest와전체해시를대조했다.

12:18:36Z에도동일5프로세스와REAL/Running/logger를확인했으며rows44667이었다.
현재세션STARTUP68이벤트가포함된512KiB로그끝부분에서종료관련이벤트는관측되지않았다.
이를정상종료PASS나제품종료실패의원인확정으로해석하지않는다.
이전관찰기를재실행하지않고사용자가즉시창을닫을수있는시점을확인요청했다.
새로분리한r2실행경로와후속네확인항목적용/회수도우미는로컬구문검증만마쳤다.
실제정상종료9파일검토와그결과에결합된설정묶음없이는설정적용이진행되지않는다.
설정쓰기복구용약2.7KB사본의필요성을설명했으며새전체백업은만들지않는다.

근거: RRES_20261019_58d923a1/operator-display-confirmation.json,
runtime-close/capture-terminal.json, runtime-close/hold-review.json,
runtime-close/timeout-state-01.json, post-timeout-preparation-review.json.


### 5.157 실제 정상 종료·승인 설정 연결·재시작과 15분 관찰 착수

사용자가 즉시 종료할 준비와 창 종료를 확인했다. R2 관찰 exec97408/R8ce9d2e99359는
exit0으로 끝났고, native handle로 추적한 backend12388/main21008 및 자식3개가 모두
실제 종료 코드0이었다. 강제 종료는 없었다. 결과9파일을 콘솔 고정 해시와 서버·로컬·공유
사본으로 검산했다(result SHA256 32b2413f9d9cb6d013aa6cc3cfb61f13394696af45cf76781525b510cedad808).
CSV 56,633행은 sample_seq1–56633이 연속이고 종료 metadata finalized/shutdown을 확인했다.
설정 SHA256 bb1b8326…ab55a는 유지됐다. 이미지·fact 전체 QA 및 worker 종료 근거 평가는 별개다.

실제 종료 자료에 결합한10파일을 준비·PowerShell 구문 검증·치환 검토 후 적용했다.
A1e35edbe의6파일 검토는 exit0이며 기존 승인 확인4항목만 갱신됐다. 변경 후 설정SHA256은
 d9ec0ed325cf61e28533d49377e6849e1f453e91706bd70cfd2d59675e590dcd다.
Low Signal OFF와 나머지 설정은 그대로이며 쓰기 실패 대비2671바이트 설정 사본만 보존했다.
전체 데이터 백업·재설치는 없었다.

첫 재시작 사전 조회는 바탕화면 전용 Plain 경계 검사를 AppData 설정에 사용하여 중단됐다.
도우미 호출 전 실패였으며 원래 로그를 보존했다. 정확한 운영 설정 경로만 별도로 검사하고
실제 앱/port 종료 상태를 재확인한 R2에서 이미 검증된 동일 시작 도우미를 실행했다.
ST8DE_98b76f29/exit0, main2132/backend12076은 세션3의 비관리자 권한이며 임시 작업 정의를 제거했다.
사용자가 대시보드 정상 표시 및 전면 표시를 확인했다. 에이전트 화면 캡처 확인과 구분한다.

재시작 초기 조회에서는 CSV 이름이 null이어서 검토를 중단했다. 22:09:45의 로그에 새 CSV
Factory_Integrated_Log_v2_20261019_220821.csv 개방이 기록됐고,13:11:00Z rows670을 확인했다.
이 시작 지연의 원인은 확정하지 않았다. 이후 읽기 검토 exit0에서 새 logger
58defb7f-9371-48d6-85cf-8b9cd3562fb5, 첫3행1·2·3과 설정 해시를 확인했다.
승인 프로파일 검토는 PASS/disabled-low-signal 범위이며 attestation verified, drift 없음,
fingerprint5f6b926c…cbef1이다. 실제 작업 정보60250·114는 operator_input/valid이며 임의 변경하지 않았다.

O15_8DE_20261019_58d923a1의4개 요청 파일과 기존 RUN8DE8파일을 서버에서 잠금·전체 해시
검증하고 exec46589로900초 관찰을 시작했다. 완료/성능 판정은 아직 미확정이다.
물리NOT_TESTED·정식HOLD·승격불가 및 기존 롤백 기준은 유지한다.
근거: RRES_20261019_58d923a1/runtime-close-r2/review.json, attestation-apply/review.json,
attested-restart-r2/start-review.json, attested-runtime-131103181974/review.json,
attested-restart-display-confirmation.json, O15_8DE_20261019_58d923a1/execution.


### 5.158 첫 8de 15분 관찰의 조기 취소와 실패 자료 재분석

exec46589/run-ce158c4e0bcd는614.609초 후exit1이다. 관찰 도구의5초 프로세스 검사110번은PASS,
111번은MISSED이며 공유 취소 후건강 확인172슬롯/자원70슬롯이취소됐다. HTTP이미지누락1도있다.
이후집계기가cancelled_remaining의뒤쪽개별파일을요구해health-00279.json부재오류를추가했다.
콘솔launcher SHA34f698a4…44c0ab와회수5,448파일/session manifest5,444파일의바이트를대조했다.
기존HTTP·자원요약은재현됐고통합집계는동일오류다. 기존증거는수정하지않았다.

격리된worktree에서취소범위집계를수정해실제동일바이트를재분석했다. 검토exit0은부분수집FAIL의
재분석완료일뿐관찰PASS가아니다. 요청278+전후2=280건,최대102.0365ms,timeout0이며
자원111표본을검사했다. 취소구간과원래미달판정은유지됐다. 회귀6건은수정전3오류/수정후exit0이고,
프로세스직전표본과파일저장시각계측을추가했다. 관련전체수집기검사는진행중이며서버적용은없다.

HTTP image-02196.body 저장이관찰549.0071868–555.803839초동안6796.6522ms걸렸으며
프로세스111번예약시각555초와겹친다. 해당프로세스의파일저장시각은기존원시자료에없으므로
디스크/스케줄링/보안프로그램등정확한현장원인은미확정이다. 실패조건을완화하거나자동재시도하지않았다.
13:27:43Z동일main2132/backend12076/REAL/두스레드alive,CSVseq4982와fact쓰기실패0/연결실패0,
설정drift0을확인했다. 관찰기잔류없음,앱강제종료/재설치/설정변경/전체백업없음이다.

근거:RRES_20261019_58d923a1/O15_8DE_20261019_58d923a1/review.md,
recovery.json,replay-review.json,partial-reanalysis.json및post-observe-current-01.json.
120분미착수,물리NOT_TESTED,정식HOLD/승격불가,기존롤백등록기준을유지한다.


### 5.159 관찰 도우미 수정117검사·패키지6실행 및 R2 착수

새도우미3a7609b7은취소구간FAIL보고와직전프로세스표본/파일저장시각기록만변경했다.
5초조건과MISSED취소,200ms판정은유지했다. 관련7개모듈117검사exit0,
수정전회귀3오류/수정후6검사통과,동일실패자료재분석exit0/관찰FAIL유지다.
원래작업트리의관련기존변경을덮어쓰지않고관리형격리worktree의두파일만commit했다.
초기전체검사2회는환경의존성/fixture변수누락으로시작전에중단됐으며그기록도보존했다.
최종검사R3의모든출력과종료0을확인했다.

빌드exit0,새field_runner16,099,530바이트/SHA2fabeb5ca4c46c0f4ffb0139c743e196534f8d1d2d7815b75c56fa6c0ec637e6,
의존성·소스변경없음과수정모듈bytecode일치를확인했다. 패키지6실행은모두기대종료값과일치했다.
합성자료검증이며서버수집성능PASS로확대하지않는다. 공유/서버새P8DE폴더8파일SHA를대조했다.
현재실행정체성을재확인해새요청4파일을생성·파싱검증하고exec54145를한번시작했다.
13:43:09Z에run-e236297c550a/초기binding·control·configuration PASS와관찰기6개를확인했다.
900초완료결과는대기중이다.앱재설치/설정변경/전체백업없음,120분미착수,정식HOLD유지다.
근거:P8DE_20261019_58d923a1/review.json및review.md,
RRES_20261019_58d923a1/O15R2_8DE_20261019_58d923a1/progress-01.json.

### 5.160 재시작 시 화면 준비와 CSV 준비 시각의 분리

이미 회수한 세 기록과 실제 제품 commit 8de의 소스만 분석했다. Electron ready는
8,381.2ms이며, 같은 logger의 시작 13:08:21.604100Z에 비해 CSV open 로그는 약
83.4초 뒤다. CSV open 로그는 초 단위라 정확한 함수 소요 시간으로 취급하지 않는다.
13:09:36Z에는 현재 CSV 경로가 null/처리 행 1이고, 13:11:00Z에는 경로와 670행을 확인했다.
관측 fact 초기화 계측값은 62,437ms(해시 6,860ms, 인덱스 55,546ms)다.

CSV 헤더 flush 후 sidecar를 동기 생성하고 경로를 공개하는 순서를 소스에서 확인했다.
이미지 fact writer 초기화도 기존 파일의 해시·행 수를 읽을 수 있다. 다만 함수별 현장
시각·스택이 없어 전체 지연의 직접 원인은 미확정이다. 같은 규모 fact를 이용한 격리
재현·함수별 시간 측정이 필요하며, 현재 세대 데이터의 손실 여부는 최종 데이터 QA에서
따로 검증해야 한다. 화면 준비나 정상 운전 15분 결과로 시작 성능 통과를 대신하지 않는다.

읽기 분석 종료 0, 입력 바이트 불변을 확인했다. 결과 SHA256은
6f02a4e3f7ec74cff69fbd83d4aef34cfd2382fab86531786d4d0b290864a16d다.
근거: RRES_20261019_58d923a1/startup-latency-review.json 및 .md.
서버 추가 계측·재시작·변경은 없으며, R2 관찰은 기존 exec54145에서 계속 진행 중이다.

### 5.161 R2 900초 관찰 종료: 상태 확인 통과·이미지 측정 누락 FAIL

exec54145는 973.187초 후 실제 종료 1이다. run-e236297c550a의 콘솔 launcher 해시는
6c8d3b1c2b141b5a9504336c9d35f0e49b01a662332a9011446c20c1351c0062다. 회수 8,793파일,
session manifest 8,789파일을 대조하고 HTTP·자원·통합 요약을 원시 자료로 재현했다.
재검토와 실패 분석은 각각 종료 0이며 관찰 FAIL을 유지한다.

상태 확인은 계획 450건/전후 포함 452건, 최대 117.6141ms, timeout 0이다. 데이터 API 150건,
자원 유효 표본 181개 및 프로세스 검사 181개는 빠짐없이 수집했다. 이미지 조회는 3,600회 중
3,598회 요청, 2회 누락이다. 실제 요청 오류·타임아웃은 없으며 유일한 통합 실패 항목은
http-component-failed다. 자원 coverage는 SUFFICIENT이나 성능 종합 판정은 NOT_EVALUATED다.

이미지 1241번이 249.5913ms 늦게 시작해 응답에 266.75ms가 걸렸고, 다음 두 예약 시각을
넘겨 1242·1243번이 누락됐다. 헤더 대기 234.2508ms, response source=upstream,
image latency=203.0ms다. 직전 1240번은 제때 완료됐다. 누락 제어 흐름은 확정했지만
늦은 시작의 OS·디스크·장비 등 직접 원인은 미확정이다. 생산 이미지 파일 손실로 확대하지 않는다.
프로세스 검사·증거 저장의 첫 시험 실패는 이번에는 재발하지 않았다. 기준 완화·자동 반복은 없다.

13:59:34Z 동일 앱 세대가 계속 수집하며 CSV seq13,146, fact 쓰기 실패·연결 실패·설정 drift 0,
진단 프로세스 잔류 0이다. 다음은 해당 지연의 격리 재현·표적 추적과 현재 데이터 QA다.
120분 미착수, 물리 NOT_TESTED, 전체 R1–R6 및 정식 출시 HOLD를 유지한다.
근거: O15R2_8DE_20261019_58d923a1/review.md, recovery.json, replay-review.json,
failure-analysis.json, ../post-observe-r2-current-01.json.

### 5.162 이미지 조회 누락의 격리 재현

현장에 전달한 도우미 소스의 핀을 유지하고 개발 PC loopback HTTP에서 세 가지 2초 실험을 했다.
기본 조건은 계획 8회/실제 8회/누락 0이며, 세 번째 응답에 267ms 지연을 넣으면 실제 최대
268.866ms/누락 1회다. 요청 시작에 240ms 지연도 넣으면 실제 시작 지연 242.7545ms,
응답 269.1117ms/누락 2회다. 모두 요청 오류·저장 폐기 0이며 동시에 같은 경로에 두 요청을
보내지 않았다. 실행 종료 0, 소스 핀 불변을 확인했다.

500ms 경고 기준을 넘지 않는 응답도 250ms 예약 간격을 넘으면 완전성 검사에서 실패한다.
현장의 두 누락과 같은 제어 흐름을 재현했지만, 합성 지연을 넣은 시험이므로 현장 시작 지연의
OS·디스크·장비 원인을 입증하지 않는다. 기준을 낮추거나 FAIL을 PASS로 바꾸지 않는다.
기존 R2는 diagnostic_timing=false였으므로 요청 경계 시각만으로 sleep 복귀·스레드 스케줄링·
Python 실행 지연을 분리할 수 없다. 다음 현장 계측은 이 구분을 위한 근거를 수집해야 한다.

근거: RRES_20261019_58d923a1/image-slot-reproduction/review.json 및 각 조건 원시 기록.
서버 추가 성능 시험·설정 변경·재시작은 없고, 120분 시험은 미착수다.

### 5.163 CSV 시작의 이미지 manifest 대기 제거: 로컬 소스 검증

실제 8de와 동일했던 backend에서 CSV open → sidecar → image health/manifest → writer 생성의
동기 경로를 확인했다. 초기화 Event를 멈춘 재현은 CSV 준비를 막았고, cold 시작에서는 sidecar가
직접 과거 파일 스캔을 시작했다. 수정 전 4검사 중 2실패, 첫 보완 후 4검사 통과다.
확대 449검사의 경로 변경 2실패를 통해 실제 경로 오류와 준비 중 상태를 구분하도록 보완했다.

cold 시작의 초기화를 생략하기만 하면 이미지 저장 OFF에서 종료까지 스캔이 미뤄지는 경로도
1개 회귀 실패로 확인했다. 최종 변경은 기존 이미지 worker에 초기화를 요청하고 종료 시 join한다.
초기화 요청 도중 설정이 바뀌어 새 요청이 들어와도 지우지 않는다. 초기화 실패는 캡처 건수에
섞지 않고 별도 실패 상태로 남기며 clean closeout을 거부한다. 최종 manifest 검증은 유지한다.

최종 commit은 `20e7f2063a5048db71b73ba566fb1cf1c84daa3f`다. 제품 두 파일과 검사 두 파일만
변경했고 관리형 작업본은 clean이다. 전체 49모듈/963검사(962통과·비공개 F01 자료 1skip),
Ruff, 프로젝트 지정 mypy 9파일, diff 확인이 모두 종료 0이다. 새 회귀 13개를 포함한다.
최종 전체 표준출력 2,401줄·오류출력 1,133줄을 읽고 framework 실패·처리되지 않은 thread 오류·
인코딩 오류 0을 확인했다. 의도적으로 주입한 초기화 I/O 오류와 기존 Starlette deprecation 경고를
구분했다. 전체 검사와 정적 검사 후 소스 핀 불변을 확인했다.

이전 전체 실행의 PowerShell 한국어 출력 인코딩 오류 27건과 성공한 중간 실행을 모두 보존했다.
최종 실행은 독립 AppData/설정 경로, Windows 기본 subprocess 문자 인코딩, UTF-8 시험 로그를
사용했다. 실제 OS Sandbox 실행은 이 소스 단계에서 수행하지 않았다.

14:38:35Z 서버 읽기에서는 같은 main2132/backend12076/logger58defb7f…/CSV220821이며
seq23,373, 기록 쓰기·연결 오류·drift0, 진단 잔류0이다. 서버 제품·설정·화면은 바꾸지 않았다.
실제 규모 초기화와 새 설치본의 Sandbox·현장 검증은 미완료다. 현장 약83.4초의 전부를 이 경로에
귀속하지 않으며, 이미지 조회의 늦은 시작 원인·현재 세대 전체 데이터 QA·120분·물리 시험은 미결이다.
기존 15분 FAIL과 정식 출시 HOLD/승격 금지를 유지한다.

근거: RRES_20261019_58d923a1/startup-image-review.md 및 .json,
JSON SHA256 `faf93756ec91e7b783421378bb63c20bae8ee514963b97733e454ad63e7a699a`.

### 5.164 보존 이미지 기록 2.25GB의 실제 규모 CSV 준비 비교

20e7f206 수정본과 기존8de를 같은2,247,226,565바이트·4,385,307행 이미지 fact로 비교했다.
보존 원본과 최소 시험 사본 하나를 읽기 공유 handle로 보호하고 전후 SHA256을 대조했다.
원본 SHA256은97a3fceb72b07bed757d11cfec73b20c1e0491ecbcc15fd394a1d978e88fb490다.
새 전체 백업·운영 데이터 변경은 없다.

기존 CSV 준비19,173.0255ms/초기화19,166.9147ms는 main thread에서 순차 완료됐다.
수정 CSV 준비6.2631ms는 초기화18,995.7525ms 완료 전에 끝났고 초기화는 기존 image worker가
수행했다. 이미지 저장 OFF에서도 종료까지 초기화를 미루지 않았다. 두 실행 모두 종료0,
강제 종료 없음, 최종 행 수·해시 일치, 무결성 미결 없음이다. 수정본 시작 metadata의 pending과
검산 후 final manifest를 구분했다. source108핀·baseline archive130파일 대조도 완료했다.

실제 CSV telemetry 저장·온도 observation 경로·전체 앱·이미지 손실·현장 성능은 이 시험의
검증 범위 밖이다. observation manifest는 대역이며 OS 캐시를 비우지 않았고 기존→수정 순서다.
현장83.4초 전체 원인을 이 시험으로 확정하지 않는다. r1은 Git archive 작업 위치 오류로
실제 비교 전에 중단됐고 원 기록을 보존했다. r2의 두 실행과 결과 대조는 정상 완료됐다.

근거: RRES_20261019_58d923a1/startup-image-scale-r2/review.md와review.json,
원 결과 SHA256 2ea2b43264e2cc0295646d63afc78137ce362cc89085891f8085e47c4deaba68.
패키지·Sandbox·현장 검증과 이미지 요청 시작 지연 원인은 미완료다.15분 FAIL/120분 미착수,
물리 NOT_TESTED와 정식 출시 HOLD는 유지한다.

### 5.165 새 잠금 환경의 종료 순서 검사 시간 초과와 검사 전용 대기 분리

C20REL_20261020_18bd8b55/prepare-ntfs에서40개 잠금 wheel 설치·pip check가 통과했으나,
full health는963개 중1개 오류·1개skip으로 종료1이다. 비공개 fixture skip은 기존 조건이다.
실패한 peer 순서 검사는 앱 시계를 고정하면서 실제 파일 I/O를3초 안에 완료하도록 기다렸다.
분리 계측30회는 모두 통과했으나2.76초 receipt 대기와 경로 확인·열기 지연을 관찰했다.
최초 실패의 OS 원인을 확정하지 않는다. 경로 확인에3.2초 지연을 넣으면 같은 wait에서
TimeoutError가 재현된다. clean240a4952에서 해당 peer-ordering host watchdog만10초로
분리한 뒤 같은 지연이 통과했다. 제품 종료1초/최종0.2초 제한·증거 무결성·실패 검사는 유지한다.
종료 module31개와 Ruff는 종료0이다. 변경은 test_image_shutdown_evidence.py 한 파일이다.
기존 실패 기록은 삭제/재작성하지 않았다. 전체 health-r2 실행 중이며 아직 설치본·Sandbox 결과가 없다.
근거: C20REL_20261020_18bd8b55/peer-watchdog-review.json 및 .md. 서버 변경 없음/출시HOLD.

5.165 후속 최종검사: health-r2는240a4952에서 npm health 종료0,backend963 중962통과/1skip이다.
Electron103/frontend442+Node9/의존성15/Ruff/mypy/QA selftest도 통과했다. 실행456.007초,
강제 종료 없이 owned process0,잠금 wheel40개·clean source 전후 일치다. 이전 실패 기록은
보존한다. 설치본 빌드만 진행 중이며 payload·runtime·Sandbox·현장 PASS를 의미하지 않는다.

### 5.166 미서명 패키지 검산과 Sandbox 종료 확인 기록 지연

clean240a4952 미서명 NSIS 빌드·payload·분리된 frozen backend 실행은 모두 종료0이다.
설치본 164,158,434바이트의 SHA256은
56ec126261970efbcee26fa22789d57c313dc8d27e5a71bb6b9296c3cab891b4다.
추출 payload 1,867개가 빌드 산출물과 일치하며 backend manifest 1,739개도 대조했다.
frozen backend 요청5건과 정상 종료0을 확인했다. 선택 hidden import tzdata 경고는 보존하며,
이는 설치된 전체 앱·현장 성능·과거 데이터 전체 QA의 통과를 의미하지 않는다.

SB20_20261020_18bd8b55에서 실제 NSIS 초기 설치·제거·이전8de 설치·후보 업그레이드를 수행했다.
최초 I4는 화면의 X를 실제로 눌렀으나 작업 문맥 복원 동안 확인 파일 기록이 지연돼 도우미의
종료 후60초 대기가 만료됐다. 원 native exit1/HOLD와 늦은 확인·문자 인코딩 오류를 모두 보존한다.
해당 앱/백엔드 잔류와 포트는0이고 앱의 종료 영수증은 존재하지만 native 종료 코드는 확보하지
못했으므로 완전한 실행 통과로 간주하지 않는다.

기존 Sandbox와 설치·데이터를 그대로 사용한 matrix-r2는 I4부터 시작한다. CUA 조작 직후
동일 JavaScript 실행에서 UTF-8 확인 파일을 기록하며 제품 코드·종료 제한·검증 도우미 조건은
변경하지 않았다. I4와 I5 native 앱/백엔드 종료0·잔류0을 확인했으며 복구·실규모 시험은 진행 중이다.
중단된 I4의 cold 사본과 고유 세대 영수증을 별도로 검토해 누적 이미지 수에 반영한다.
근거: SB20의 원 matrix-exec-terminal.json, late-confirmation-addendum.json,
resume-preparation.json 및 output/matrix-r2. 서버 변경·새 전체 백업 없음/출시HOLD 유지.

5.166 후속 완료: matrix-r2 host/guest 종료0, 완결6세대 모두 앱/백엔드 native 종료0·잔류0이다.
일반 독립검사180개 중179개 통과·1개 실패, CSV/이미지 검증 도구10개는 종료0이다.
실패는 등록된 롤백541d/1.0.26의 X 종료 직후 이미지 요청502/shutdown 한 건이다.
CUA 확인16:05:09.616Z, 오류16:05:09.900Z, native 종료16:05:10.240Z로 결합된다.
후속 후보I10에도 이 과거 오류는 보존되며 신규 오류는 없다. 기존 버전의 온도/금형 패널 잘림도
기록했다. 원 오류를 제외하여 전체 판정을 통과로 바꾸지 않았다.

I10 실규모 독립검사39개는 모두 통과했다. 2,247,226,565바이트/4,385,307행 이미지 fact를
초기화하는 동안 실제 CSV 저장을3회 관찰한 뒤 초기화 완료를 확인했다. 새 CSV480행 중
유효 온도466행, observation38개, 정상 closeout/소유 worker 정리/입력 전후 해시 일치다.
캡처OFF 상태로 기존 fact 해시를 검산한 범위이며 과거 이미지 실파일 전체 QA가 아니다.
OS 캐시는 통제하지 않았고 현장83.4초의 전체 원인/서버 성능 개선 증명으로 확대하지 않는다.
모의 위치 값 미입력 경고2개, 교체/공정 이벤트 미발생, image linkage 비적용도 별도 한계다.

Sandbox cold 확인 후 동일 id만 종료했다. 결과2,850파일/37,501,892바이트는 종료 전후 일치한다.
출력 manifest SHA256은8813342815a48979dc36629317fc0a088ef7b229b8b397621bc63a2b45f7b6fe다.
제품 소스/빌드/전체 health는 반복 변경·실행하지 않았다. 서버 접속·변경/새 전체 백업 없음.
전체 출시HOLD, 현장15분 FAIL,120분 미착수,물리NOT_TESTED와 goal active/PROGRESS를 유지한다.
근거: SB20/report.json SHA256 7e74cd94ad0e496c6d0a662d909f0c6759a9d51d3e0350484eea27e307ab5a4c,
report.md, review-r2/review.json, retained-scale-review.json, disposal-verification-r2.json.

### 5.167 현장 응답 대기 초과와 추적 세대 연결의 한계

| 항목 | 결과와 의미 |
|---|---|
| 이번 image 939 | 시작 지연 17.5472ms, 응답 289.2062ms, HTTP 200 |
| 응답 구간 | 헤더 대기 282.4577ms. 기존 이미지 갱신을 함께 기다리는 coalesced 응답 |
| 다음 예약 940 | 250ms 간격의 다음 시점에도 이전 요청이 끝나지 않아 측정 1회 누락 |
| health | 118회, 최대 118.2983ms, 200ms 초과 없음 |
| 측정 기준 | 이미지 경고 500ms, 실패 지연 기준 미정, 측정 누락 허용 0. 기준 변경 없음 |
| 원 15분 실패 | 시작 249.5913ms 지연 + 응답 266.75ms로 2회 누락. 원 FAIL 유지 |

289ms 응답은 500ms 경고 기준 미만이어도 요청을 겹치지 않는 수집기의 250ms 예약을 넘는다.
확인된 것은 진단 측정의 누락이며 운영 이미지 파일의 손실을 뜻하지 않는다. 응답에 기록된
upstream 250ms는 앱 스케줄링을 포함한 대기 시간으로, 장비만의 통신 지연이라고 단정할 수 없다.
이전 실패 직전 기록 저장 네 건은 예정 시각 229.48ms 전에 끝났다. 해당 기록 저장이 예약 시각을
직접 점유했다는 설명은 배제되지만 OS 대기·잠금·간접 I/O 영향은 미확정이다.

#### 추적의 검증 범위와 한계

ETL 76,414,976바이트의 SHA256은
`f2bd647919d99c2bb40f83f099863c4573cb5e0f03e36e3b95eacd11227088fd`다.
서로 다른 내보내기 경로에서 선택된 원시 기록 723,581개가 모두 일치했고 헤더의
EventsLost/BuffersLost는 0이다. XML 변환의 15005/111 오류 표시는 원문에 보존했다.
이는 전체 이벤트 의미나 지연 원인이 모두 검증됐다는 뜻은 아니다.

메모리 순환 버퍼에는 끝부분 약 18.54초의 공통 스케줄링 구간이 남았다. 요청은 그 안에 있으나
추적 시작 후 만들어진 수집기 스레드의 생성 기록이 앞부분과 함께 사라졌다. 엄격한 세대 연결은
`new-thread-start-missing-or-conflicting`으로 거부됐다. 이 검사를 완화하지 않았고 CPU 부족이나
특정 잠금을 원인으로 확정하지 않는다. 이번 17.5ms 시작 지연은 이전 249.6ms 지연의 재현이 아니다.

#### 도우미와 실행 검증

도우미 commit `3bbf3ba7166f692e8f0673cc02f83f2a7e696a16`은 5개 파일에서 현재 8de의
정확한 설치본 식별값과 거부 검사를 추가했다. 제품 코드와 설치본은 변경하지 않았다.
최종 서로 다른 연관 검사 102개, native PowerShell 계약 9개, frozen 실행 8개가 예상 결과다.
초기 환경변수 누락과 프로파일 CRLF 핀 불일치 실패는 보존했다. Git 원본 LF 바이트로 영향받은
12개를 재검사해 종료 0을 확인했으며 기대 해시는 바꾸지 않았다. Ruff/diff도 종료 0이다.

승인 SSH 전달 15파일/16,961,207바이트를 검산했다. 최초 시작은 작업 정보 변경으로 실제 수집
전에 거부됐다. 관찰된 60140·34를 새 시작 기록에만 반영한 R2는 서버 16:30:14Z에 시작해
16:35:08Z에 정상 완료됐다. entry/coordinator 종료 0, 로그 닫힘, 소유 프로세스 잔류 0이다.
닫힌 결과의 외부 SSH 핀부터 확인해 2,181파일/110,419,964바이트를 회수·검산했다.

이상 감지 후 의도적으로 남은 진단을 취소했다. 이미지 944요청/실제 누락1/후속 취소2655,
data 40요청/실제 누락0/후속 취소110이다. 15분 완전성 PASS로 사용할 수 없다.

#### 서버 상태와 다음 절차

서버 16:37:07Z 읽기에서 main 2132/backend 12076의 같은 실행 세대가 유지됐고 REAL 수집,
표본 54,315, 관찰 기록 쓰기·연결 오류와 설정 drift는 0이다. 작업자 입력은 60140·34이며
실제 생산 여부를 별도 확인한 것은 아니다. Low Signal OFF, 진단 프로세스 0, WPR 기록 안 함이다.
사용자의 대시보드 정상·전면 표시 확인 이후 화면을 조작하지 않았다. 새 전체 백업은 만들지 않았다.

다음 검토는 250ms 예약과 500ms 경고 아래에서 측정 완전성을 확보하는 수집기 동작이다.
먼저 기존 합성 재현과 실제 원시 기록을 기준으로 수정안을 만들고, 요청·누락·취소·실패를
숨기지 않는 회귀 검사를 설계한다. 기준이나 주기를 몰래 바꿔 기존 FAIL을 PASS로 바꾸지 않는다.
같은 현장 추적·15분 시험을 반복하기 전에 수정의 필요성과 관찰 가능성을 검토한다.
독립적으로 현재 완료 세대의 CSV QA와 이미 만든 240a 설치본의 현장 적용 준비를 이어간다.

기존 현장 15분 FAIL, 120분 미착수, 물리 시험 NOT_TESTED, 정식 출시 HOLD와 승격 금지를 유지한다.
기계 판독 근거와 파일별 핀은 같은 폴더의 `report.json`에 있다.

report.json SHA256 `71c26c08c8f17e59c918e4f13ea0c6ea961cafed0f0274f148d8ff4f7815a53a`.

### 5.168 종료 세대 이미지 전수 검증과 네이티브 잠금 수정


종료 세대 `31e53142-b54b-4243-b651-9bd4b32334c7`에서 생성된 이미지 12,214개 검증을 완료했다.
CSV R2는 1800초 제한으로 중단되고 잔류0을 확인했다. 같은 검증기의 과거 4,237,531행 검사에 2810.281초가 걸린 기록을 확인하여 R3를 기존 3600초 한도로 실행 중이다(exec48138). R2는 보존하며 R3의 내용 판정은 아직 없다. 서버의 현재 실행 세대와 구분하며 정식 출시는 HOLD다.

#### 확인한 범위

| 항목 | 확인 결과 |
|---|---|
| 종료 CSV | 56,633행, 원본 SHA e0ba6e10… 유지, 내용 검사 RUNNING_NO_CONTENT_VERDICT |
| 관찰 원장 | 당시 643,203행 / 746,252,872바이트를 원 SHA와 대조 |
| 이미지 원장 | 당시 4,522,664행 / 2,317,581,403바이트를 원 SHA와 대조 |
| 이미지 선택 | 초기 4,510,450행 이후 최종 원장까지 12,214행, 같은 SPOT 실행 세대 |
| 이미지 파일 | 12,214개 / 118,684,412바이트, JPEG 디코딩·크기·해시·연결 PASS |
| 이미지 추가/누락 | 선택 세대 사본에서 0, 원장·파일 목록·바이트 전후 대조 |
| 종료 | 이미지 검증기 exit 0, 소유 프로세스 잔류 0, 입력 잠금 재검산 PASS |

원장은 계속 추가되는 서버 파일에서 당시 행 수까지 읽고, 이미 보존한 종료 manifest의 SHA256과
일치하는 바이트만 회수했다. 서버에 전체 원장 사본이나 새 전체 백업을 만들지 않았다.
인용·줄바꿈·따옴표·UTF-8·블록 경계·잘못된 해시·잘린 입력 등 11조건을 검증했다.
선택한 이미지 PASS는 과거 모든 이미지나 별도로 확인된 과거 손상 파일의 복구를 뜻하지 않는다.

#### 도우미 수정과 실패 기록

12,214개 이미지 잠금에서 CRT 파일 디스크립터가 소진됐다. 8,200개 회귀 시험으로 같은 오류를
재현한 후, 파일마다 유지하던 Python 객체를 Windows 네이티브 읽기 잠금으로 바꿨다.
변경 금지 잠금은 검사 전체 동안 유지하고, 실제 읽기는 임시 파일 객체 하나씩 수행한다.
쓰기·이름 변경 차단, 전체 재검산, 마지막 해시 오류 때 앞선 잠금 해제를 확인했다.
두 파일만 변경했으며 helper commit은 `0e5a4fdf3450e021554c7526823c4c6f953af6dc`다. 제품 설치본은 변경하지 않았다.

서로 다른 연관 검사 44개를 확인했다. 최초 전체 명령은 QA 22개 통과 뒤 CSV 시험 import 경로
누락으로 exit 1이었다. 경로 보완 후 CSV 22개가 exit 0이다. 실패 원문은 보존했다.
최종 저장소 통합 검사 2개, Ruff 및 diff 검사도 exit 0이다.
실제 검증의 입력 하드링크 거부, 최소 환경 SFTP exit 255, 이미지 출력 경로 조건 거부도 보존했다.
일반 사본·기존 SSH 환경·입력 밖 결과 경로로 각각 보완했고 보호 조건은 완화하지 않았다.

#### 보존과 운영 상태

새 원장·이미지 입력 12,218파일을 `Z:\SmartFactory\20261020\return\CQA20_c1e37003`에 복사하고 전수 해시 대조했다.
종료 CSV와 metadata는 기존 공유 `RC8DE_R2_20261019_58d923a1` 사본을 재사용한다.
서버 2026-10-19T17:29:26.1912880+00:00 읽기에서 main 2132/backend 12076, 같은 8de 실행이 REAL 수집 중이며
관찰 쓰기·연결 오류와 설정 drift는 0이다. Low Signal OFF, 추적·진단 프로세스 잔류 0이다.
작업 정보 60140·34는 서버 저장값 관찰이며 실제 생산을 별도 확인한 것은 아니다.
사용자가 정상·전면 표시를 확인한 뒤 화면 조작은 없었다. 이번에 새 화면 관찰을 한 것은 아니다.

#### 남은 작업

Wait for the existing CSV R3 exec48138; no relaunch. Same pinned validator and locked inputs, measured-scale 3600-second budget. Inspect full output, native exit, input closeout, and owned-job cleanup before verdict.
기존 250ms 비중첩 측정 계약을 확인했으며 주기·허용 누락·경고 기준을 바꾸지 않았다.
기존 15분 FAIL, 120분 미착수, 물리 경계 NOT_TESTED와 출시 HOLD를 유지한다.
기계 판독 근거: report-r3-pending.json, SHA256 `843f72e9f716f1394e42e9b7893aacf6de188c20e16ea81ac1bed1785b98775e`.

### 5.169 240a 후보 현장 준비 도우미 검증과 서버 전달


새 후보 `240a4952`의 현장 준비 파일 25개(206,565,459바이트)를
`C:\Users\user\Desktop\SmartFactory\FIELD240A_20261020_d2cbfa10`에 전달하고 모든 파일의 크기·SHA256을 검산했다.
제품 설치본은 기존에 검증한 미서명 SHA256 `56ec126261970efbcee26fa22789d57c313dc8d27e5a71bb6b9296c3cab891b4` 그대로다.
제품 1,867파일을 다시 대조했다. 서버에는 현재 `8de06431`이 실행 중이며 새 후보는 설치하지 않았다.

#### 검증한 도우미

현재/새 후보의 버전명이 모두 1.0.30이므로 커밋·설치본·기준 파일을 함께 검사한다.
관찰·설치·종료·회수 요청을 새 후보에 연결하고, 다른 1.0.30 자료를 섞으면 거부한다.
원본 보존 도우미에는 현재 8de를 받는 별도 정책을 추가했다. 이전 정책과 후보는 유지했다.
field_runner 커밋 `1947907a876e3968f0dc593a7d3932244cc73e0f`, 보존 도우미 후속 커밋 `2274bea1b068930d2ac8a3f272552d1c1efa6a68`다.
현재 작업 트리와 실행 중인 CSV 도우미는 변경하지 않았다.

| 검사 | 결과 |
|---|---|
| 최종 커밋 Python 시험 | 129개 PASS, exit 0 |
| 네이티브 설치 / 정상 종료 / 회수 | 123 / 18 / 13개 PASS, 각 exit 0 |
| 진단 진입 계약 | 9조건, 정상·거부·정리 결과 기대값 일치, 실제 ETW 시작 없음 |
| 현재 8de 원본 보존 | 30개 PASS, exit 0; 잘못된 빌드·정책·패키지 거부 |
| 실행 파일 6회 | 정상 0, 중복 JSON·빌드 혼합·해시 오류·비관리자 요청 거부 1 |
| 실행 파일 입력/정리 | 입력 142파일 불변, 소유 프로세스 잔류 0 |
| 정적 검사 / 빌드 | Ruff F·Git diff check·PyInstaller exit 0, 빌드 경고 없음 |

최초 시험의 환경 누락과 Git archive 줄바꿈 변환으로 발생한 실패는 보존했다.
최종 사본은 Git blob 바이트와 일치하며 해시 검사를 완화하지 않았다.
실제 관리자용 런처 ACL 적용·서버 설치·새 후보 현장 성능은 이 로컬 결과로 통과 처리하지 않는다.

#### 전달 후 서버 상태와 다음 순서

2026-10-19T18:08:50.7345879+00:00 확인: main 2132/backend 12076, 같은 logger 실행, REAL 수집 중이다.
관찰 쓰기·연결 오류/설정 drift는 0, Low Signal OFF, 추가 수집기·WPR 없음이다.
작업 정보는 02:56 KST 자동 초기화되어 현재 제품·금형 또는 비생산 여부를 사용자에게 요청했다.
화면은 사용자의 정상 전면 표시 확인 이후 조작하지 않았고 새 시각 확인은 하지 못했다.

1. 기존 CSV R3(exec48138) 종료를 기다린다. 재실행하지 않는다. 종료 후 출력·입력 결합·잔류를 독립 검토한다.
2. 현재 생산 정보를 확인하고 정상 종료/원본 검산을 준비한다. 종료 관찰은 아직 시작하지 않았다.
3. 승인된 제한 현장 순서에 따라 실행 세대가 확인된 설치 요청을 만든다. 기존 8de 및 공식 541d 복귀 자료를 재검산해 사용한다.

새 전체 백업·설치·설정 변경은 없다. 기존 15분 FAIL, 120분 미착수, 물리 NOT_TESTED, 출시 HOLD를 유지한다.
화면 갱신이 로드 완료 후 대기하는 방식이고 계측기가 고정 시각을 쓰는 차이는 `ui-cadence-review.md`에 기록했다. 측정 기준은 변경하지 않았다.
기계 판독 근거: report.json, SHA256 `9dd9e74b83cd9d58a723b7600d7d4409f47fb7c99c2cce13fc9288b6d18357ea`.

### 5.170 종료 세대 이미지 전수 검증과 네이티브 잠금 수정


종료 세대 `31e53142-b54b-4243-b651-9bd4b32334c7`에서 생성된 이미지 12,214개 검증을 완료했다.
CSV 내용 검사까지 종료 코드 0을 확인했다. 서버의 현재 실행 세대와 구분하며 정식 출시는 HOLD다.

#### 확인한 범위

| 항목 | 확인 결과 |
|---|---|
| 종료 CSV | 56,633행, 원본 SHA e0ba6e10… 유지, 내용 검사 PASS |
| 관찰 원장 | 당시 643,203행 / 746,252,872바이트를 원 SHA와 대조 |
| 이미지 원장 | 당시 4,522,664행 / 2,317,581,403바이트를 원 SHA와 대조 |
| 이미지 선택 | 초기 4,510,450행 이후 최종 원장까지 12,214행, 같은 SPOT 실행 세대 |
| 이미지 파일 | 12,214개 / 118,684,412바이트, JPEG 디코딩·크기·해시·연결 PASS |
| 이미지 추가/누락 | 선택 세대 사본에서 0, 원장·파일 목록·바이트 전후 대조 |
| 종료 | 이미지 검증기 exit 0, 소유 프로세스 잔류 0, 입력 잠금 재검산 PASS |

원장은 계속 추가되는 서버 파일에서 당시 행 수까지 읽고, 이미 보존한 종료 manifest의 SHA256과
일치하는 바이트만 회수했다. 서버에 전체 원장 사본이나 새 전체 백업을 만들지 않았다.
인용·줄바꿈·따옴표·UTF-8·블록 경계·잘못된 해시·잘린 입력 등 11조건을 검증했다.
선택한 이미지 PASS는 과거 모든 이미지나 별도로 확인된 과거 손상 파일의 복구를 뜻하지 않는다.

#### 도우미 수정과 실패 기록

12,214개 이미지 잠금에서 CRT 파일 디스크립터가 소진됐다. 8,200개 회귀 시험으로 같은 오류를
재현한 후, 파일마다 유지하던 Python 객체를 Windows 네이티브 읽기 잠금으로 바꿨다.
변경 금지 잠금은 검사 전체 동안 유지하고, 실제 읽기는 임시 파일 객체 하나씩 수행한다.
쓰기·이름 변경 차단, 전체 재검산, 마지막 해시 오류 때 앞선 잠금 해제를 확인했다.
두 파일만 변경했으며 helper commit은 `0e5a4fdf3450e021554c7526823c4c6f953af6dc`다. 제품 설치본은 변경하지 않았다.

서로 다른 연관 검사 44개를 확인했다. 최초 전체 명령은 QA 22개 통과 뒤 CSV 시험 import 경로
누락으로 exit 1이었다. 경로 보완 후 CSV 22개가 exit 0이다. 실패 원문은 보존했다.
최종 저장소 통합 검사 2개, Ruff 및 diff 검사도 exit 0이다.
실제 검증의 입력 하드링크 거부, 최소 환경 SFTP exit 255, 이미지 출력 경로 조건 거부도 보존했다.
일반 사본·기존 SSH 환경·입력 밖 결과 경로로 각각 보완했고 보호 조건은 완화하지 않았다.

#### 보존과 운영 상태

새 원장·이미지 입력 12,218파일을 `Z:\SmartFactory\20261020\return\CQA20_c1e37003`에 복사하고 전수 해시 대조했다.
종료 CSV와 metadata는 기존 공유 `RC8DE_R2_20261019_58d923a1` 사본을 재사용한다.
서버 2026-10-19T18:08:50.7345879+00:00 읽기에서 main 2132/backend 12076, 같은 8de 실행이 REAL 수집 중이며
관찰 쓰기·연결 오류와 설정 drift는 0이다. Low Signal OFF, 추적·진단 프로세스 잔류 0이다.
작업 정보는 02:56 KST 자동 초기화 이후 미입력 상태이며, 현재 생산 정보는 사용자에게 요청했다.
사용자가 정상·전면 표시를 확인한 뒤 화면 조작은 없었다. 이번에 새 화면 관찰을 한 것은 아니다.

#### 남은 작업

Use the delivered and verified F20READY 240a field bundle after current production information and normal-close readiness are confirmed. Preserve the original 15-minute failure; do not repeat unchanged image or CSV QA.
기존 250ms 비중첩 측정 계약을 확인했으며 주기·허용 누락·경고 기준을 바꾸지 않았다.
기존 15분 FAIL, 120분 미착수, 물리 경계 NOT_TESTED와 출시 HOLD를 유지한다.
기계 판독 근거: report.json, SHA256 `8983ed6a58e44e683cec86eaf953691aec846d87e6b248891f787b0502165647`.

### 5.171 현재 실행 결합과 새 후보 실행 정보 검토기 지원


현장 준비 도우미의 실행 정보 검토기에 새 240a 식별 지원이 빠져 있었다.
기존 검증된 v1–v5 지원을 통합하고 v6는 정확한 240a 커밋과만 결합하도록 보완했다.
같은 1.0.30 버전명의 다른 빌드, 요청 스키마 혼합, 잘못된 첫 순번을 거부한다.
helper commit: `48f498f77b224c5589f58d7a65ca59ea4f56ae3f`. 제품 설치본과 서버 도우미 묶음은 바뀌지 않았다.

#### 검증

- 수정 전 v6 요청의 `request-build-schema` 실패를 재현했다(exit 1).
- 실행 정보·종료 검토기 관련 35검사 및 실제 CLI 조건을 확인했다(exit 0).
- Ruff F, Git diff 검사 exit 0. 현재 작업본의 HEAD·index·기존 변경은 유지했다.
- 검증 실행 자체는 통과했지만 기록 도우미가 CRLF의 OK 줄을 오판한 오류가 있었다.
  줄바꿈을 정규화하고 동일 소스의 기존 종료 결과를 재사용했으며 테스트를 반복하지 않았다.

#### 실제 서버 읽기 결과

서버 main 2132 / backend 12076을 포함한 프로세스 5개의 네이티브 생성 시각·경로·부모 관계·포트 소유를 검토했다.
logger는 `58defb7f-9371-48d6-85cf-8b9cd3562fb5`이며 같은 8de 실행을 유지한다.
자정 이후 CSV는 `Factory_Integrated_Log_v2_20261020_000000.csv`, 첫 순번은 28930이다.
설정 SHA256은 `d9ec0ed325cf61e28533d49377e6849e1f453e91706bd70cfd2d59675e590dcd`다.
읽기 전용 수집과 독립 검토 모두 exit 0이며, 결과 5파일을 공유 위치에 전수 해시 대조해 보존했다.

서버 작업자는 03:12:32 KST에 제품 60140·금형 35를 입력했다(source=operator_input).
앞서 미입력일 때 요청한 질문의 의존성은 이 실제 입력으로 해소했다. Codex가 값을 입력하거나 덮어쓰지 않았다.
이는 서버에 입력된 작업 정보이며 물리적인 제품을 독립 확인한 것은 아니다.

#### 다음 단계

정상 종료 관찰 요청은 `C:\Users\user\Desktop\SmartFactory\CLOSE8DE_20261020_d2cbfa10\request.json`에
전달·검산했다. 아직 정상 종료 대기를 시작하지 않았다. 화면을 정상 닫을 수 있을 때 관찰기를 시작하고,
정상 종료 증거와 원본 전수 검산을 확인한 후 해당 실행에 결합한 설치 요청을 작성한다.
이후 새 후보 재시작·설정/수집·현장 15분/120분·종료 데이터 검증을 진행한다.
앞서 발생한 15분 FAIL, 물리 시험 미완료와 출시 HOLD는 유지한다.

### 5.172 SSH 연결 단절 시 관찰 도우미 정리 검증


현장 적용 전 읽기 관찰이 SSH 연결 단절 뒤에도 계속 실행될 수 있음을 실제 시험에서 확인했다.
진단 도우미만 종료하고 로그를 보존하는 보호 기능을 보완해 검증했다. 운영 앱은 계속 수집 중이며,
원본 관찰·정상 종료 대기·설치는 아직 시작하지 않았다.

#### 재현과 보완

기존 호출 방식의 짧은 시험에서는 SSH 연결 종료 약 2초 뒤에도 같은 부모·자식 프로세스가 살아 있었고
시험 파일 잠금이 유지됐다. 이들은 시험 자체의 10초 제한으로 나중에 종료됐다.
따라서 연결 종료를 진단 종료의 증거로 사용할 수 없었다.

기존 검증된 네이티브 Windows job 구현을 재사용했다. 진단 자식은 정지 상태로 만들고 job에 연결한 뒤
시작한다. 해당 SSH 연결이 끊기거나 제한 시간이 끝나면 그 job의 진단 프로세스만 정리한다.
운영 앱은 이 job에 넣지 않는다. 정상 완료와 중단 결과를 구분하고 부분 로그도 남긴다.
helper commit은 `fa57f962c331ab540847178545fcfccfc329d47d`이며 제품 설치본 변경은 없다.

#### 확인한 결과

| 범위 | 결과 |
|---|---|
| 개발 PC 네이티브 PowerShell 5.1 | 정상·비정상 종료, 제한 시간, 연결 단절·오류, 시작 전 연결 없음, 잔류 자식, 실제 TCP 연결 종료 등 9조건 확인, exit 0 |
| 실제 서버 정상 시험 | 자식 exit 0, job 잔류 0, 파일 잠금 해제 |
| 실제 서버 연결 단절 시험 | 예상한 `observation-connection-lost` 실패, 해당 job 정리, 잔류 0, 부분 로그 보존 |
| 정리 확인 시각 | 개발 PC의 연결 종료부터 외부 조회로 정리를 확인할 때까지 1.063초. 정확한 종료 지연 측정값은 아님 |
| 결과 회수 | 서버 기록 10파일을 회수하고 외부 SHA256과 전수 대조 |
| 실제 관찰 진입부 | 경로 조건 5개와 구문 검사 exit 0, 서버의 두 역할 사전 확인 exit 0, 관찰 자식은 시작하지 않음 |

첫 로컬 시험의 PowerShell 변수 이름 충돌과 첫 서버 사전 확인의 `PSIsContainer` 오류를 보존했다.
각 오류를 고친 최종 소스와 별도 R2 묶음을 검증했으며 기존 실패 파일을 덮어쓰지 않았다.

#### 현재 서버와 다음 단계

서버가 기록한 2026-10-20 03:51:15 KST 상태에서 main 2132 / backend 12076,
logger `58defb7f-9371-48d6-85cf-8b9cd3562fb5`의 기존 8de 빌드가 REAL 수집 중이다.
작업자 입력은 제품 60140·금형 35다. 관찰 연결·쓰기 오류와 설정 drift는 0,
Low Signal은 OFF, 추가 진단 수집기와 WPR 기록은 없다.
사용자의 대시보드 정상·전면 표시 확인은 유지하되 이번에 화면을 새로 확인한 것은 아니다.

준비된 서버 진입부는
`C:\Users\user\Desktop\SmartFactory\OBS240A_20261020_d2cbfa10_R2\invoke-guarded-observation.ps1`이며
SHA256은 `2731c60ec567643ba1380c093a585fa862106627005d628f974ca80f22c303f1`이다.

1. 이미 요청한 현장 창 닫기 가능 여부를 확인한다. 아직 앱을 닫지 않는다.
2. 원본 관찰기의 READY를 확인한 뒤 종료 관찰기의 READY와 같은 실행 세대를 확인한다.
3. 현장에서 X로 한 번 정상 종료하도록 안내하고 실제 종료 결과·원본 검산을 회수한다.
4. 두 결과를 검토한 뒤 그 실행에 결합한 설치 요청을 작성한다. 실패한 관찰기는 자동 재실행하지 않는다.

새 전체 백업·앱 종료·설정 변경·설치는 없었다. 기존 15분 FAIL, 120분 미착수,
물리 경계 NOT_TESTED 및 정식 출시 HOLD는 그대로다.

### 5.173 현재 8de 실행의 정상 종료와 원본 검산 진행


2026-10-20 08:18 KST. 사용자가 두 관찰기의 READY 안내 후 X로 종료하고 “종료됨”이라고 답했다.
main 2132/backend 12076을 포함한 같은 실행의 프로세스 5개가 모두 실제 종료 코드 0으로 끝났다.
최종 종료 시각은 서버 기록 2026-10-20 08:12:07 KST다. 앱 프로세스와 8000번 포트 잔류는 없다.

#### 검토 완료 범위

- build: `8de064317d6de42d321afb8395f7a30a1f31cd55`, logger: `58defb7f-9371-48d6-85cf-8b9cd3562fb5`.
- 현재 CSV 127,812행의 순번 28,930–156,741이 연속하며 metadata의 shutdown/finalized 및 최종 순번과 일치한다.
- CSV 상태는 valid 113,783행, under_range 14,029행이다. 범위 미달 상태를 정상 온도로 바꾸지 않았다.
- 설정 SHA256 `d9ec0ed325cf61e28533d49377e6849e1f453e91706bd70cfd2d59675e590dcd`가 종료 전후 동일하다.
- 종료 결과 9파일과 관찰 제어 기록 6파일을 회수해 외부 해시와 대조했다.
- `review_health_runtime_close.py` 실제 검토 exit 0. 실행·회수·검토 기록과 영수증 총 31파일을 공유 위치에 해시 대조해 보존했다.
- 원격 브라우저 도구로 연결된 서버 바탕화면을 읽을 수 있게 됐으며, Smart Factory가 닫힌 상태를 화면에서도 확인했다. 화면 입력은 하지 않았다.

종료 결과: `C:\Users\user\Desktop\SmartFactory\R0ef1a9094e92`, result SHA256
`5bad9ac7ef1cf05816999d430e2e1f21e8a6da966de4ae216ad869d7d37233cd`.
독립 검토: [review.json](C:/Users/user/Desktop/SmartFactory/F20READY_20261020_d2cbfa10/closed-runtime-review/review.json).
공유 보존: `Z:\SmartFactory\20261020\return\CLOSE8DE_d2cbfa10\normal-close-R0ef1a9094e92`.

#### 진행 중인 원본 검산

원본 관찰은 같은 실행을 계속 유지한다. 서버 control `G656dd47ee22d`, 결과 `O3c489b54`,
controller PID 21184/created_filetime 134369245507093707, local exec session 97634다.
08:17:24 KST 읽기에서 capture가 61,115파일까지 진행됐고 stderr/hold가 없다.
이는 중간 진행 수치이며 최종 검산 통과나 전체 파일 수를 뜻하지 않는다.
종료 전 경로 목록은 401,441파일이었으며 종료 후 Capture와 Verify의 최종 결과를 따로 확인해야 한다.

앱은 닫힌 상태로 유지한다. 동일 관찰기를 다시 시작하지 않는다. 검산 완료 후 원본 결과·manifest·실제 종료 기록을
같은 실행에 결합한 설치 요청을 준비한다. 설치/설정 변경/전체 백업은 아직 수행하지 않았다.
이번 검토는 현재 CSV 순번과 프로세스 종료 확인이며 이미지·사실 원장 내용과 worker 종료 영수증의 전체 QA를 대신하지 않는다.
이전 15분 FAIL, 120분 미착수, 물리 NOT_TESTED와 출시 HOLD는 유지한다.

### 5.174 새 240a 빌드의 승인 설정 확인 도우미 준비

2026-10-20 08:43 KST. 원본 관찰기를 유지하는 동안 기존 승인 프로파일을 새 build와 연결할 외부 도우미를 준비했다.
분리 helper commit `3dda260afb6ffba4dbe66479083331b2433225a4`는 허용 build에
`240a49522da5d59e9e823f62612e3d4207b497a9`만 추가한다. 제품·설치본을 다시 만들지 않았다.
기존 도우미의 새 build 거부를 red exit1로 확인했고, 변경 후 전체 12개 테스트와 diff 검사는 exit0이다.
합성 입력 7조건은 승인 설정, 변경된 Low Signal·비교기·온도 범위·자료형, 다른 build와 해시 불일치를 확인한다.
기존 unrelated 35파일·primary HEAD·index 보존 확인도 exit0이다. 14개 기록·소스·영수증을 공유 위치에 해시 대조해 보존했다.

[도우미 검토와 적용 조건](C:/Users/user/Desktop/SmartFactory/F20READY_20261020_d2cbfa10/attestation-support/review.md).
실제 새 build 설치 검토와 그 실행의 정상 종료 metadata가 없으므로 서버 적용 묶음은 아직 생성·전달·실행하지 않았다.
08:43:15 KST 원본 관찰 읽기는 392,323파일 중간 진행이며 stderr/hold가 없다. 앱 프로세스는 없다.
같은 exec97634를 유지하며 Capture와 Verify의 최종 결과를 기다린다. 설치·설정 변경·새 전체 백업은 없다.
이 결과는 현장 설정 확인이나 QA 통과가 아니다. 기존 15분 FAIL·120분 미착수·물리 NOT_TESTED·출시 HOLD를 유지한다.

### 5.175 원본 검산 완료와 단일 설치 절차 시작


2026-10-20 09:20 KST. 사용자가 정상 종료한 8de 실행의 원본 Capture와 Verify를 완료했다.
원래 exec97634는 실제 종료0, 서버 관찰 job은 PASS/오류0/잔류0다. 동일 실행을 재시작하지 않았다.

- 원본 범위: Roaming/SmartFactoryLogger 및 Roaming/smart-factory-logger-v2.
- 검산: 398,341파일, 230디렉터리, 추가 스트림680개, 17,531,891,198바이트.
- 결과: `O3c489b54/result.json`, SHA256 `37d0011a3f9efda9c84f6f363e2e2fccc77bbe9f5560fe023aa90b7ea9f0dc3a`.
- manifest: `6c2b5de09e1ab23a329ed249493ed3269224d52b6b7ea7a135cd10d69ac44a1e`.
- 종료 기록 결합: 같은 logger와 main/backend의 PID·native 생성 시각, 5프로세스 정상 종료0 및 CSV127,812행.
- 독립 회수·검토 `recover_current_preservation.py --execute` exit0, 공유 사본 해시 대조 완료.
- 새 전체 백업 없음. 파일 보존 검산이며 데이터 내용의 전체 QA 통과를 뜻하지 않는다.

#### 실행 중 단계

새 요청3파일을 `C:\Users\user\Desktop\SmartFactory\I240A_20261020_d2cbfa10`에 전달하고
해시 및 일반 서버 탐색기 접근을 확인했다. 화면에서는 close-review, manifest, request의 JSON3파일을 확인했다.
탐색기를 닫았다. 요청 SHA256은 `c81dfaaf46a890bd27bb4e9118396a03dbb59530ce086e67be8c06d0e3d47015`다.

`launch_current_install.py --execute`는 09:18 KST에 한 번 시작했다. 실제 exec session13125,
localSSH46860, 서버 wrapper16172/created_filetime134369291183577783, 자식PowerShell8380이다.
09:19:48 서버 조회에서 동일 wrapper 세대가 살아 있고 앱 프로세스는 없다.
현재 stdout은 INSTALL_TRANSACTION_BEGIN_REVERIFY_FIRST이며, 설치 프로그램의 시작·성공은 아직 확인되지 않았다.
실행에는 설치 직전 원본 재검산과 설치 후 원본/설치본 검산이 포함된다.

무출력이나 연결 관찰 만료를 이유로 재실행하거나 강제 종료하지 않는다. 실제 session13125를 추적하고,
완료0이면 `recover_current_install.py --execute`로 최종 증거를 회수·독립 검토한다.
그 전까지 앱을 시작하지 않는다. 검토 후 승인된 정상 시작과 작업자 화면 복귀를 진행한다.
이전 15분 FAIL·120분 미착수·물리 NOT_TESTED·정식 출시 HOLD와 롤백 기준은 유지한다.

### 5.176 새 후보 실행 입력 준비와 설치 중간 상태 확인

2026-10-20 서버 09:30:06 KST 조회에서 같은 설치 wrapper16172/134369291183577783와 자식8380이 살아 있고,
Smart Factory 프로세스는 없다. 정확한 요청 SHA가 일치하는 결과 폴더는 `J8708bfe7`이다.
이 시점에 installer-start/installer-exit/hold/result 파일은 없으며 설치 전 원본 재검산을 계속한다.
stdout 진행과 실제 exec13125를 함께 추적한다. 결과 폴더 존재를 설치 성공으로 처리하지 않는다.

설치 검토 뒤 실제240a 실행을 읽을 `prepare_candidate_runtime_input.py`를 개발 PC에서 준비했다.
합성 정상1조건과 거부14조건, native PowerShell 구문 검사 exit0, 실제 설치 검토가 없을 때 예상 exit1을 확인했다.
소스 SHA `d8c01a3e1d74aad719479bb5fa9d69f4a82dd8c7aaea32e9fd708069f1cbc0ac`와 검사 기록을 재대조하고,
소스/검사/범위 설명/보존 영수증10파일(18,675바이트)을 공유 위치에 해시 검산해 보존했다(기록 처리 exit0).
새 후보의 실제 서버 읽기·시작·종료·설정 변경은 수행하지 않았다. 합성 입력을 실제 후보 증거로 사용하지 않는다.

[준비 범위와 실행 조건](C:/Users/user/Desktop/SmartFactory/F20READY_20261020_d2cbfa10/candidate-runtime-input-checks/review.md).
설치 terminal0 및 독립 결과 검토 → 승인된 표준 사용자 시작 → 실제 새 logger/CSV 첫 순번/설정·프로세스 읽기 →
별도 native identity 검토·실행 직전 재확인 순서다. 이전8de 관찰 요청을 새240a 세대에 재사용하지 않는다.
첫 CSV 행 확인은 전체 CSV·이미지 QA를 대신하지 않는다. 새 전체 백업 없음, 기존 실패와 출시HOLD 유지.

### 5.177 새 실행 요청의 native v6 계약 수정과 후속 신원 준비

2026-10-20 09:43 KST. 5.176의 R1 입력 준비는 build240a에 이전8de용 request schema v5를 생성했다.
입력 검사와 구문 검사는 통과했지만 실제 도우미 요청 계약과의 통합 검사가 빠져 있었다.
서버 실행 전 개발 PC에서 현재 전달 도우미55f1bbc2의 LibraryOnly/Assert-RuntimeRequest로
`request-contract`/exit1을 재현했다. R2는 schema v6를 생성하며 같은 실제 도우미 검사 exit0을 확인했다.

- 최신 입력 준비: `prepare_candidate_runtime_input_r2.py`, SHA256 `93de87a99e13730149d556580b93eb6e717be56032c01ee7d787ae8b1fef358f`.
- 최신 신원 확인 준비: `prepare_candidate_identity_capture_r2.py`, SHA256 `f7a413e46ea92417f22301ce4435f3d33966f511ce80149e563c2325a922d45e`.
- 정상 입력1/입력 거부14, native 요청5조건(정상exit0와 의도된 거부4개exit1), 기본 모드·실제 설치 미완료 차단4조건을 확인했다.
- `candidate-runtime-contract-r2/check_r2.py` 최종 exit0. 기존 identity-only 전달·회수 코드의 PowerShell 문자열7개는 그대로다.
- 최초 테스트 도구의 PSModulePath 및 dot-source 매개변수 충돌도 수정하고 실패 로그를 보존했다.
- 과거 소스·검사·공유 사본을 덮어쓰지 않았다. 새 소스/재현/검사/영수증54파일(59,453바이트)을 공유 위치에 해시 대조해 보존했다.

모든 새 검사는 개발 PC 합성 입력이며 실제 서버 실행/설치/설정 확인 PASS가 아니다.
기존 RUN240A 8파일의 해시와 manifest/launcher 결합도 확인했다. 제품·설치본·서버 도우미는 변경하지 않았다.
최신 [후속 실행 순서](C:/Users/user/Desktop/SmartFactory/F20READY_20261020_d2cbfa10/candidate-runtime-contract-r2/review.md)를 적용한다.
기존 R1 및 CLOSE8DE 요청은 새 실행에 사용하지 않는다. 실제 설치 검토·표준 사용자 시작 후 R2 입력 읽기,
R2 identity-only 회수·검토, 새 세대 종료 관찰·승인 설정 확인·재시작·15분/120분 검증 순서다.

서버 09:42:58 읽기에서 같은 wrapper16172/134369291183577783와 child8380이 살아 있다.
J8708bfe7의 요청 해시는 일치하고 installer-start/exit/hold/result는 아직 없다. 앱은 닫혀 있으며
같은 exec13125의 설치 직전 전수 재검산을 유지한다. 자동 재실행/강제 종료/새 전체 백업 없음.
기존15분FAIL, 120분미착수, 물리NOT_TESTED, 정식 출시HOLD와 롤백 기준은 유지한다.

### 5.178 단일 설치 프로그램 정상 종료와 사후 원본 검산

2026-10-20 서버09:50:18 KST 읽기에서 설치 프로그램 PID13028의 실제 exit0을 확인했다.
시작09:48:18.449, 종료09:48:50.474 KST이며 retained native handle/forced_termination=false다.
설치 직전 원본 전수 검산은09:48:14.900에 완료됐고 실제 설치까지3.549초로120초 제한 안이다.
398,341파일/230디렉터리/680추가 스트림/17,531,891,198바이트가 원래 관찰 totals와 일치한다.

같은 exec13125/wrapper16172·134369291183577783에서 설치 후 원본 검산으로 넘어갔다.
J8708bfe7에 설치 파일/등록 기록이 생성됐지만 최종 result.json은 아직 없다. 앱 프로세스는 없다.
설치 성공 전체 판정·설치본/설정/원본 보존의 최종 독립 검토·재시작은 미완료다.
09:45 원격 브라우저 화면에서도 닫힌 앱 상태를 읽었으며 UI 입력은 하지 않았다.

[중간 결과와 다음 실행](C:/Users/user/Desktop/SmartFactory/F20READY_20261020_d2cbfa10/installation-native-exit-pending-review.md).
실제 terminal0 후 recover_current_install.py --execute로 최종 회수·대조를 마친 뒤 표준 사용자 시작을 진행한다.
이 중간 native exit0을 현장 QA나 운영 승격으로 처리하지 않는다. 기존 실패·물리NOT_TESTED·출시HOLD 유지.

### 5.179 새 후보 정상 종료 관찰의 세대 결합 준비

2026-10-20 10:07 KST. 같은 설치 exec13125의 사후 원본 검산이 계속 진행 중이며 앱은 아직 시작하지 않았다.
기존 정상 종료 관찰은 이전8de/logger/CSV에 고정돼 있어 새240a에 재사용하지 않는다.
`prepare_candidate_close_guard.py`는 실제 설치 검토·R2 runtime·native identity 자료가 일치할 때만
새 세대 요청을 넣은 별도 관찰 진입점/전송/실행 파일을 로컬에 준비한다. 허용 역할은 runtime-close뿐이다.
검증된 연결 단절·기한·관찰 자식 정리 코드는 바꾸지 않는다. 실제 서버 전송·관찰·앱 제어는 아직 하지 않았다.

로컬 검사 check.py exit0: 생성1건, 잘못된 입력 거부11건, native PS5.1 구문·역할 제한 exit0,
기본 준비 모드 exit0, 실제 설치 검토 미완료 상태의 준비 차단은 예상 exit1을 확인했다.
소스 SHA256은 `4dae3c8e735c65bef7264f979dbf74b253e5eb7a43811e86932bf2af56f3cd82`다.
소스·검사·실패 로그·설명17파일/37,302바이트를 공유 return에 파일별 해시 대조해 보존했다.
[검증 범위와 실행 순서](C:/Users/user/Desktop/SmartFactory/F20READY_20261020_d2cbfa10/candidate-close-adapter-checks/review.md).
실제 새 실행과 결합한 파일은 생성 후 별도 구문·서버 사전 검사가 필요하다. 로컬 준비 성공은 현장 종료나 QA 통과가 아니다.

### 5.180 설치 보존 검토 완료와 새 후보 실제 시작

2026-10-20 10:23 KST. 단일 설치 exec13125가 실제 exit0으로 완료됐고,
recover_current_install.py --execute의 회수·독립 검토도 exit0이다. J8708bfe7 결과23파일,
설치payload1,867파일+제거프로그램1개, 원본398,341파일/680추가스트림/17,531,891,198바이트와 설정 보존을 확인했다.
최종 결과 SHA256 `bc598bc307b6bc4e2b5efb7c57b6fb5ec20dec7975155a4a5dfc3b33bdd396d5`.
설치본은240a/v1.0.30이며 새 전체 백업·강제 종료·재설치는 없다.

서버 기존 바로가기로 시작했고, main7036/backend19840 및 총5프로세스의 실제 표준 사용자 토큰/session3을 검토했다.
새 logger929ecd1d-d395-49e8-88e5-a02a903127b0, CSV101848의 첫 순번1을 읽었고10:22:43 health는957행/REAL/Running이다.
초기화 pending 상태에서 실제CSV64KiB를 읽은 뒤 관측 사실 이력이 ready/53,094ms로 바뀌었다.
최초 flush 지연과 이미지 manifest 완료 시점의 정확한 계측은 아니다.
대시보드를 최대화해 맨 앞으로 표시했고 기존 operator_input60141/38과 카메라 화면을 확인·보존했다.

R2 입력/identity 검토 exit0. 새 세대 종료 관찰 파일3개의 서버 최종 전달·해시와 native 구문/서버 사전 검사 exit0.
관찰 자체는 아직 미시작이다. 새 build 승인 설정 확인 전이므로 config drift1을 그대로 기록한다.
새 폴더의 Explorer 화면 검증은 미완료이며 실제 SSH 파일 검산과 구분했다.
[설치·실행 근거와 남은 범위](C:/Users/user/Desktop/SmartFactory/F20READY_20261020_d2cbfa10/candidate-start-review/review.md).
정상 종료·설정 확인·재시작·15분/120분·전체 데이터 QA가 남았고 기존 실패·물리NOT_TESTED·출시HOLD는 유지한다.

### 5.181 새 후보 정상 종료·승인 확인 갱신과 실제 재시작

2026-10-20 10:44 KST. candidate-close 관찰 exec84293은 실제 exit0, 제어 Gb619218f81a9는 PASS/소유잔류0이다.
Rca09eff18c3d 결과 SHA256 `86a9a7edf5f77b3132f74a50110f1bcb99a1d9cab5ee4892276e88ad89d33782`를
외부 콘솔 핀과 회수 파일에 대조했다. 독립 검토 exit0: 제품5프로세스 native exit0,
CSV2,310행 순번1–2,310 연속·metadata finalized·종료사유shutdown·기존 설정SHA 유지.
startup_pending15/under_range2,295행이며 유효 온도 측정이나 전체 fact/image QA 통과가 아니다.

앱이 닫힌 상태에서 기존 승인 확인4항목만240a fingerprint에 연결했다. apply 실제 exit0,
A38327dcb 결과 SHA256 `8e9c239f825a6a064ed450868861cdaa79228478095406037753849b755a7219`.
회수6파일 독립 검토 exit0, 설정4항목 외 바이트 동일·앱 미실행·전후 프로세스/포트 없음 확인.
config SHA256은 d9ec0ed3…에서 `0b12949153b3b2ef384aaad5ab394850413db2fc5d072a3a697852b9c9ede3f4`로 바뀌었다.
전체 백업·재설치 없이 설정 쓰기 복구용 작은 config 사본1개만 보존했다.
초기 로컬 추가 검사의 matched 가정은 실패했으며 실제 이전/현재 readback은 not_supported였다.
기존 도우미 계약을 바꾸지 않고 장비 직접 읽기 미검증을 그대로 기록했다.

기존 바로가기로 재시작 후 main7864/backend14360/총5프로세스 일반 사용자 토큰·session3,
새 loggerc671227f-aa27-4844-9eff-928540ae31ba와 CSV103735 첫순번1을 확인했다.
서버10:41:57 KST에는1,106행, drift0, 관측 사실 accepted/completed260·실패/거부/대기0.
초기화는 ready/46,765ms이며 정확한 최초 flush나 이미지 manifest 완료 시점의 측정이 아니다.
소프트웨어 표현 승인 프로파일과 fingerprint 재계산은 제한 범위 PASS, 물리NOT_TESTED/readback not_supported 유지.
대시보드 최대화/전면 표시와 기존 작업자 입력60141/38을 실제 화면으로 확인·보존했다.

실제 RUN240A8파일과 helper1947907a의95소스 파일을 재대조하고, 현재 프로세스의 native 생성시각으로
새15분 입력3파일을 만들었다. request/config 계약 검증·공유 사본 해시 exit0.
관찰 실행 명령은 생성하지 않았으며 SSH 단절 정리 경로 연결·서버 전달·15분 실행은 다음 단계다.
기존 실패·120분미착수·전체 데이터 QA·R1–R6·출시HOLD·롤백 기준을 유지한다.
[실제 결과와 재실행 금지 대상](C:/Users/user/Desktop/SmartFactory/F20READY_20261020_d2cbfa10/attested-candidate-runtime/review.md).

### 5.182 새 후보 15분 관찰의 보호 실행과 원시 기록 검토

2026-10-20 10:59 KST 중간 상태. 기존 측정 코드·주기·판정 기준을 유지한 채 현재240a 실행용
관찰 진입점을 연결했다. native PS5.1 구문과 실제 frozen runner를 이용한 중첩 정상 종료,
모의 연결 단절 정리를 로컬에서 검사했다. 검사 exit0이며 정상 자식exit0, 단절 자식예상exit1,
두 경우 소유 프로세스 잔류0이다. 운영 앱이나 서버에는 로컬 시험이 접속하지 않았다.

서버 O15_240A_20261020_d2cbfa10에6파일의 목록·길이·SHA256을 검산하고 사전 검사exit0을 확인했다.
실제 실행은 exec97354 한 번이며 localSSH57436, 제어G4ffb44be2b32/controller8840,
결과run-4471e3005134다. 요청SHA256은 `0f74861681ec08bc0fec14d81566db9ee5cab533a9e3a838238382dc0eddfac5`,
진입점SHA256은 `b8c7ef8870b97f5bb526ac86819e672779ea2dea7ca2d0a674e1bd6d36eba556`.
main7864/backend14360의 native 생성시각·logger c671227f·CSV103735·설정SHA에 결합했다.

10:50:38의 읽기 확인에서 동일 제어 프로세스와 진단 자식들을 확인했다. 첫 상태 읽기는 사용 중인
출력 로그의 공유 잠금으로 실패했으며, 로그 본문을 읽지 않는 후속 확인은exit0이었다.
실제 관찰은 중단·재실행하지 않았다. 이 상태 확인 부하를 없었던 것으로 처리하지 않는다.

회수 도구는 실제 종료 뒤 외부 콘솔의 제어 결과SHA와 launcherSHA를 검산한다. 독립 검토 도구는
helper1947907a의95소스 파일을 다시 확인하고 원시 HTTP·자원·결합 요약을 재계산한다.
검토 도구 사전 검사exit0은 완료했지만 실제 측정 결과 회수·재계산은 아직이다.
기존15분 실패 기록·120분 미착수·물리NOT_TESTED·전체 데이터 QA·출시HOLD를 유지한다.

2026-10-20 11:14 KST 결과. 같은exec97354가1,043.406초 뒤exit1로 끝났다. 감독 오류·강제 종료요청은
없고 두 단계Job의잔류0을 확인했다. 외부 콘솔 제어결과SHA256 `488f82d534b96760e8ac922d1c662568ba8184eb00048d0382e3714b25ca2e5e`,
launcherSHA256 `a7f7fb00b7dde4d2b80afd730cdc6d5ad11c879debaef6efcc99a44bb1913b55`에 결합해 회수했다.
회수exit0,8,657파일 중session manifest8,652파일/52,547,873바이트 대조와 HTTP·자원·결합 요약의
독립 재계산exit0. 이는 관찰FAIL의 재현이며 성능PASS가 아니다.

health는전후포함452건·최대425.5674ms·200ms초과11건·timeout0, data150건·최대450.1434ms·500ms초과0.
이미지는3,600슬롯 중3,461요청/139누락이고 실제응답오류0·timeout0·최대694.287ms다.
누락분류는previous-request-decode-or-enqueue-overrun109회와scheduler-missed-entire-slot30회다.
프로세스검사181회PASS, 자원181유효표본/세300초창각61표본coverage충족이지만 자원전체성능판정은NOT_EVALUATED다.
11건health초과는주로헤더대기였고, 최대요청277번은425.5674ms중423.2441ms가헤더대기다. 직접원인은미확정이다.

마지막누락은관찰636.25초에있었다. 작업정보가11:00:32.323842 KST에60190/10으로바뀐시각과가깝지만
인과관계로처리하지않는다. data106번과화면에서새작업값을확인했으며에이전트가수정하지않았다.
나머지약264초에실패가없어도실패구간을제외하거나15분을PASS로바꾸지않는다.
이전8de의2누락/health117.6141ms와조건이통제된비교가아니므로제품회귀원인도단정하지않는다.

같은logger/CSV/프로세스/승인설정경계는PASS. 전후CSV행3,170→6,551, 관측사실completed737→1,641,
이미지written674→1,457이며실패/drop/거부/대기와설정drift0이다. 실행중카운터이며닫힌세대전체QA대체가아니다.
11:08대시보드Running·최대화·전면·60190/10을화면으로확인했다. 앱종료·설정변경·설치·전체백업없음.
검토SHA256 `51ba956751cea2e4c904c44d37391aa375cb1082444fbe5b7f0972ebae9d4a30`,
실패분석SHA256 `89417b4334a48483f61bd0b0d31adc35be8bd5593aa7f01505e7b35f7bf84898`.
[실제15분결과와근거](C:/Users/user/Desktop/SmartFactory/F20READY_20261020_d2cbfa10/O15_240A_20261020_d2cbfa10/review.md).
다음은보존자료의요청·native시계·자원·작업변경대조와원인별격리재현이다. 동일15분자동반복이나120분착수는하지않는다.
전체목표active/이번턴PROGRESS, R1–R6/물리NOT_TESTED/정식출시HOLD와기존롤백기준을유지한다.

### 5.183 사용자 승인에 따른 운영 성능 판정 v2

2026-10-20 기준 개정 구현. 위 5.182는 당시 계약의 FAIL 기록으로 그대로 보존한다.
새 `operational-observe`는 health/data·프로세스·자원을 수집하며 합성 이미지 요청을 제외한다.
200/500ms 초과 통계와 최초/최종 응답을 보존하되 단발 지연을 전체 운영 부적합으로 바꾸지 않는다.
요청 오류, 누락/취소/잘못된 계측, 앱 세대/설정 불일치, 실제 표시, 저장 무결성을 구분한다.
정의되지 않은 운영 허용시간은 NOT_EVALUATED, 측정 공백은 INCOMPLETE다.
연속 지연·성공 간격 계산은 기록 공백에서 끊으며 상위 결과에도 관찰 범위와 미완료 사유를 남긴다.

별도 이미지 관찰기는 기존 페이지의 실제 요청·load/error·가시성·포커스를 기록한다.
이미지 요청을 추가하거나 화면의 완료 후 대기 타이머를 바꾸지 않는다.
CDP 연결 해제 뒤 기존 페이지 생존과 관찰기 정리를 개발 PC의 Chromium fixture에서 검사했다.
headless 검사로 실제 작업자 화면, 물리 표시, 센서 프레임 시각이나 저장 완전성을 증명하지 않는다.

이번 설계 5항목 중 5항목의 코드/회귀 대응을 확인했다. 전체 출시 달성률과 구분한다.
판정 19개, 실제 Windows 수집/세대 결합 24개, 최종 결과 전달/모드 2개, 기존 strict HTTP 34개,
frontend 36개, Chromium 2개 모두 exit0. 일부 재실행 중복을 고유 검사 수로 합산하지 않는다.
데이터 전수 대조 및 종료 정산 코드는 변경하지 않았고 과거 데이터 QA 실패를 재판정하지 않았다.

고정 archive와 session manifest를 연결해 과거 8,652파일을 전수 재검산했다.
기존 review SHA `51ba956751cea2e4c904c44d37391aa375cb1082444fbe5b7f0972ebae9d4a30`은 유지한다.
별도 새 평가 SHA `65df8903245ea4f93b7c7a7159f83f4895a5e358611ecffd62ad3f69a2c266af`:
health 초과11건/최대425.5674ms, image139누락을 유지하며 전체 계측INCOMPLETE·운영NOT_EVALUATED다.
원래 FAIL을 PASS로 수정하지 않았다.

증거: `C:/Users/user/Desktop/SmartFactory/VCR20_20261020_0cef5f4d`.
서버 작업·장비 설정·제품 수집 주기·설치·전체 백업은 이번에 수행하지 않았다.
새 검증 묶음 배포와 실제 UI/앱 세대 연결·공정 시간 요구 확정·현장 검증은 남아 있다.
정식 출시HOLD·물리NOT_TESTED·기존 롤백 기준은 유지한다.
[개정 계약·재실행 방법·근거와 남은 조건](../04-report/production-release-risk-validation-operational-criteria-20261020.report.md).

### 5.184 운영 관찰 v2의 재검토와 누락 보완

2026-10-20 사용자 재검토 요청. 원문 timing-conditions와 제품 완료 후 대기 코드,
현재 검증기/데이터 대조/종료 검사를 다시 확인했다.
DOM load만으로 HTTP 증거가 부족한데도 COMPLETE가 되는 경우, 호스트/페이지 시각 혼용,
load 이후 다음 요청 간격의 누락, HTTP 마지막 값·응답 시계 검증 누락,
자원 조회 실패와 실제 backend 불일치의 혼동을 보완했다.
renderer 무응답으로 관찰기가 무기한 대기하지 않도록 evaluate 실행 제한도 추가했다.

브라우저 Resource Timing/DOM을 같은 페이지 monotonic 시계로 기록하고,
load 간격·응답 완료 간격·load→다음 요청 간격을 별도 요약한다.
설정값·프레임 대응·화면 정지·저장 무결성은 증거 없이는 NOT_EVALUATED다.
HTTP 응답 완료와 디코딩/처리 완료를 구분하며 기존 strict 수집 코드는 바꾸지 않았다.
자원 읽기 실패는 INCOMPLETE, 실제 관측된 backend identity 불일치는 FAIL로 유지한다.

관련 최종 검사: 판정31, Windows통합25, Chromium6, frontend36, 데이터/종료20 — 모두 exit0.
최초 데이터 검사의 Windows stdin/spawn 오류는 파일 진입점으로 수정해 재검사했다.
운영 데이터 대신 새 시험 사본에서 누락·손상·정리 실패를 주입했다.
원시 장치 샘플 무손실이나 현재 서버 전체 데이터 QA를 PASS로 판정하지 않는다.
관측 키 중복·fact 연결 누락·종료 spool 잔량 검사의 기존 거부 조건을 코드로 대조했다.

과거8,652파일 전수 검산 exit0. 새 별도 평가 SHA:
`56d5e39bcd95df05795e80e46afe3139223aaf4014e32884fe62f822676a8535`.
health11초과·image139누락·기존FAIL·새계측INCOMPLETE·운영NOT_EVALUATED 유지.
이전 평가/검증 기록은 덮어쓰지 않았으며 해시 일치를 확인했다.
증거: `C:/Users/user/Desktop/SmartFactory/VCR_REVIEW_20261020_b2f20330`.
이번 변경 범위는 개발 PC 검증 코드·문서다. 서버/장비 설정·수집 주기·운영 승격은 변경하지 않았다.
[추가 보완과 검사 범위](../04-report/production-release-risk-validation-operational-criteria-20261020.report.md).

### 5.185 이미지 연속성·향후 학습 목적과 현재 후보용 검증 통합

사용자는 시간 기준을 모르며 이미지는 끊기지 않아야 하고 온도는 향후 딥러닝에 활용한다고
답했다. 정량 지연/최소 변화 시간은 미정이다. 독립 관측과 CSV 반복 참조, 원시 유효성,
미확정 공정 라벨을 구분하는 요구를 계획에 추가했다. 기존 제품 주기는 유지한다.

주 작업 트리의 검증 코드를 기존 현장 도구에 그대로 덮으면 현재240a 후보 식별/취소 꼬리
처리를 잃을 수 있어, helper1947907a에 필요한9파일을 통합했다.
새 helper7c0af584의99소스와 commit 바이트를 확인했다. primary HEAD/index/기존 소스 변경은 없다.
판정31·통합114·브라우저6 검사, 빌드/의존성 전후 대조, frozen6조건이 모두 기대 결과다.
중첩 진단 정상/연결단절 두 조건도 exit0, 소유 진단 잔류0이다.

새8파일/42,217,919바이트를 서버 `SmartFactory\OPV2_20261020_c3496c21`에 전달·해시 대조했다.
서버 describe와 별도6파일 관찰 진입점 사전 검사 exit0이다.
13:14 KST 운영 판정 v2의900초 수집을 한 번 시작했다. 제어Ga7e83203c097,
요청SHA `f0f1cd22d39589472bd8fbe18c730a8c864796fac730908adec36f3f9a54d6dc`.
동일 main7864/backend14360·loggerc671227f·CSV103735·설정에 결합했고 합성 이미지 요청은 없다.
실제 Electron CDP listener가 없어 실제 화면 연속성 계측은 미평가다.
제품 설치·설정·앱 종료·새 전체 백업은 수행하지 않았다.

이전8de 종료 세대의 보존CSV56,633행을 읽어 독립 키13,047개·추가 반복 참조43,573행,
키 없는13행을 확인했다. 같은 SPOT 세대fact13,230개 중183키는 이CSV에 참조되지 않았다.
참조 키 누락·fact 중복·로컬poll순번 공백0, 원시 유효온도12,631/invalid_sentinel599이다.
전체CSV 라벨이shadow/realtime_candidate이며 학습 정답으로 확정된 자료가 아니다.
13,047 raw 문자열 차이는 해당8de 코드의CRLF→LF 정규화와 일치한다.
상태/poll시각/payload hash를 포함한 설명되지 않는 차이는0이다. 최초 literal 결과도 보존했다.
PC poll완료 간격 중앙값1.000029초/최대1.538507초는 이과거세대의 특성이며 새운영기준이 아니다.
현재240a나 장치 원시 샘플 전체/학습 적합성 PASS로 확대하지 않는다.

전체목표 active, 이번범위 progress. 기존FAIL·전체데이터QA·물리NOT_TESTED·출시HOLD와
기존롤백기준을 유지한다. 새15분결과는 원시 기록을 회수·독립 재계산한 후 별도로 덧붙인다.
증거: `C:/Users/user/Desktop/SmartFactory/OPV2_20261020_c3496c21`.

13:30 KST 같은 관찰 exit0. run-62140094c40e의 외부 제어/launcher SHA 연결 회수와
session1,591파일 전수 검산·원시 요약 재계산 exit0, replay 오류0이다.
health 전후포함452건/최대180.7787ms, data150건/최대48.7353ms이고 오류·timeout·누락0,
참고200/500ms 초과0이다. 프로세스181표본·자원181유효표본/coverage충족,
같은실행·진단잔류0·강제종료 없음. 수집/세대결합 범위PASS이며 운영성능/실제UI연속성은미평가다.
CSV카운터40,244→44,106, fact연결/쓰기실패·drift·시계이상0이다. 닫힌세대전체QA대체가 아니다.
13:31 API와 화면에서 동일실행·작업60190/10·Running·카메라이미지·전면표시를 확인했다.
새제품설치·앱종료·설정/주기변경·전체백업없음. 기존FAIL과전체출시HOLD를 유지한다.
검토SHA `5202b463f3bbf4c579f4c52b6dc2744cec19f339156f957354b1944a86da92ce`.

### 5.186 설치형 file 화면 관찰과 연결 단절 영향

현재240a는 file 문서에서127.0.0.1:8000 API를 사용한다. 기존 same-origin 관찰기는
이 요청을 놓쳤다. Chromium file fixture의3요청을0으로 세는 red exit1을 확인하고,
file 문서의 명시적 loopback origin만 허용하도록 수정했다. HTTP 문서 제한은 유지한다.
다른 포트/잘못된 origin 배제와 기존 계측 검사를 포함한8시험 exit0이다.
도구2파일 commit7d1bbb57524d2654106ca760e5c7a2ed72d24a06을 이전helper7c0af584에
연결했으며 primary HEAD/index·제품 설치본·기존 해시 증거는 유지했다.

같은 payload1867파일의 전후 대조와 격리 AppData/합성장비에서 TCP/파이프 연결을 시험했다.
TCP 기본15초57요청/57load·오류0, 파이프 준비 보완 후57/57·오류0을 관측했다.
초기 파이프2회는 frameTree URL 초기값이 비어 관찰기 초기화에 실패했고 원본을 보존했다.
파이프 단절 시험에서는2초 안에 앱이 종료돼 운영 수집 유지 조건을 충족하지 못했다.
TCP 분리 시험에서는56/56·오류0을 기록하고 분리2초 후에도 같은 앱/logger가 실행 중이었다.
각6회는 이후 정상 종료0·소유 Job 잔류0·강제 종료 요청 없음으로 정리됐다.
단절 실패 때문에 파이프는 현장에 적용하지 않는다. TCP가 작동해도 현재 서버 세대 결합과
운영 권한·진단 수명·정상 종료 후 포트 제거 검증 전에는 현장 준비 완료로 보지 않는다.

13:37 서버 API와13:48 화면은 동일 앱/작업60190/10·Running·전면 표시를 확인했다.
이번 서버 설치·설정 변경·종료·포트 개방·새 전체 백업은 없다. 실제 이미지 연속성,
현재 세대 전체 데이터 QA,120분,물리 시험,승격은 미완료다. 전체 목표 active/출시 HOLD.
증거: `C:/Users/user/Desktop/SmartFactory/UIOBS_20261020_c10ed6de`.

### 5.187 현재 실행 종료 입력과 진단 실행 경로 준비

13:58:59 KST 서버에서240a/main7864/backend14360·loggerc671227f·CSV103735·
config0b129491을 다시 읽었다.5프로세스는 일반 사용자/session3이며 작업60190/10이다.
현재 실행에 맞춘 종료 요청·관찰 진입점·README·manifest4파일9,544바이트를 새
`UIFIELD_20261020_9fd4dfaa`에 전달하고 개발/공유/서버 SHA256을 대조했다.
PowerShell5.1 구문 검사와 서버의ValidateOnly는 각각exit0이다. 종료 관찰기는 시작하지 않았다.

진단 인수가 있는/없는 바로가기2개3,338바이트를 별도새 `UIRUN_20261020_9fd4dfaa`에
전달했다. 서버에서 바이트와TargetPath/Arguments/WorkingDirectory/WindowStyle을
검토했고 제안 포트19221이 현재 닫혀 있음을 확인했다. 바로가기를 실행하지 않았다.
새 진단 연결은 서버 내부의 화면 제어 접근을 열므로 실행 전 범위 확인 대상이다.
기존 SSH 전달 승인을 새 진단 접근 승인으로 간주하지 않는다.

이 작업의 검증 범위는 준비·전달·사전 조건이다. 실제 현장 이미지 관찰이나 정상 종료·
전체 데이터 검산이 아니다.14:01 화면에서 앱의Running·작업·카메라 전면 표시를 확인했다.
제품 종료/시작/설정/설치/포트 개방/새 전체 백업은 없고 목표active·출시HOLD를 유지한다.
구체 절차: `C:/Users/user/Desktop/SmartFactory/UIFIELD_20261020_9fd4dfaa/review.md`.

### 5.188 승인된 현장 이미지 관찰과 닫힌 CSV의 온도 관측 수

사용자가 임시 loopback 진단 연결과 관찰 후 일반 실행 복귀를 승인했다.
기존 SSH의 포트 전달 금지 조건을 유지하기 위해 관찰기를 서버 내부에서 실행한다.
제품을 진단 Job에 넣지 않으며, 서버의 기존 Node24.12.0/OpenJS 유효 서명·실제 바이트와
Playwright Core1.60.0/observer revision3의 109파일을 고정 해시로 확인했다.
전달된 ZIP은2,875,612바이트, 압축 해제된 입력은12,491,315바이트다.

14:08:42 KST 기존 c671227f 실행의 정상 종료5프로세스 exit0·잔류0 및 CSV54,143행
sequence1–54143을 검토했다. 원장 잠금 사본은 서버R9d50be5f9e89에 보존했다.
첫 원장 복사 시도는 StrictMode의 DirectoryInfo 부모 검사에서 자식 실행 전 실패했고,
새 R2 transport의 경계 검사 회귀 후 완료했다. 원래 실패 기록·구 도우미 바이트는 보존한다.
이 결과는 전체 fact·이미지 바이트·worker 종료 영수증의 QA PASS를 대신하지 않는다.

닫힌 CSV만의 추가 분석은 정상 종료 후 회수한
73,220,278바이트/SHA22bf468e5e2474944ffda132f2a817a08662712692740a195d25d5b5a63d6ba0을
잠금 상태에서 전후 검산했다.54,143행 중13행은 관측 키가 없고, 나머지54,130행은
서로 다른12,466키를 참조했다. 같은 키의 온도·상태·payload hash 충돌은0이다.
추가41,664회 참조는 새로운 물리적 온도 측정 수로 세지 않는다.
CSV가 참조한 poll sequence는1–12664이며198개 중간 poll 번호가 이 CSV에서 참조되지 않았다.
이는 원장 손실 판정이 아니다. 원장에는 별도의 종료 시 전체 행 수·키 해시·연결 검증이 필요하다.
유효 온도53,279행, under_range851행, startup_pending13행이며,
전체 행의 label_validation_state는shadow, phase_confirmation_state는realtime_candidate다.
이 값들을 정답 라벨로 승인하거나 원본을 학습용으로 변환하지 않았다.

14:20 같은240a 설치본을 진단 인수로 일반 사용자/session3에 재시작했다.
새 main9084/backend3760·logger6140e7f1·CSV142023·config0b129491을 읽고,
main9084 소유127.0.0.1:19221 listener 하나와 대시보드/작업60190/10의 전면 표시를 확인했다.
14:25:23 KST 실제 file dashboard에 연결한15분 관찰을 시작했다.
완료 결과와 정상 실행 복귀는 후속 영수증으로 별도 기록하며 시작 성공을 PASS로 사용하지 않는다.
증거: `C:/Users/user/Desktop/SmartFactory/UIFIELD_20261020_9fd4dfaa/execution-addendum.md`.

### 5.189 실제 이미지 관찰의 종료 경계와 일반 실행 복귀

승인된15분은14:25:23–14:40:23 KST에 실제 file dashboard에서 수행했다.
revision3 원본1,354,657바이트/SHA
b668573c50b56628ee78bc0393e2fd1d1a1244e35ed689ba20ceb54f78bcfa0b의 요약을
같은 고정 도구로 재계산해 일치함을 확인했다(exit0). 같은5 native process와 설정도 유지됐다.
요청2480/DOM load2479, 관찰 오류0, 최대 load 간격418.7ms, p95 390ms다.
가시성/포커스 표본902개는 모두true였다. 실제 물리 화면 표시나 프레임 최신성의 증거는 아니다.

0–2478 요청은 각각request→200 response→finished이고 마지막2479는request만 기록돼 있다.
계측 종료 때 진행 중인 마지막 요청의 완료가 없어서 HTTP/resource 측정이 INCOMPLETE다.
진단 Node exit1은 이 미완료 판정이며 강제 종료 요청·잔류 자식·guard 오류는 없었다.
원본과 당시 판정을 보존하고 한 건의 차이를 저장 이미지 손실이나 요청 실패로 변환하지 않는다.
load/요청 ID의 동일성 대응·load 후 대기 계약도 NOT_EVALUATED다.
경계 요청의 제한된 후속 관찰과 검열된 표본의 별도 판정을 회귀 검증하는 것이 다음 도구 개선이다.
완료될 때까지 무제한 대기하거나 동일 현장 시험을 자동 반복하는 방식으로 해결하지 않는다.

14:41:17 KST 진단 실행5프로세스가 모두 정상 exit0으로 종료됐다.
닫힌 CSV5287행/sequence1–5287, valid5270/startup_pending17과 config0b129491을 검토했다.
전체 fact/image/worker QA는 별도 미완료다. 진단 포트 소멸을 확인한 뒤14:41:52 일반
실행으로 재시작했고 loggerd59057c9·CSV144152·같은설정·핵심설치3파일을 확인했다.
진단 인수와19221 listener가 없고14:43 화면에서 Running/카메라/작업60190/10을 전면 확인했다.
복귀 후 이미지대기312.5ms/온도1초 설정은 새 실행에서 읽은 값이며 원본null 필드를 바꾸지 않는다.

새 통합 검산의 SHA는00f756117eba1f1fc3d2db23e8e1031cb4acaa090ce3ff5f7f78ea054b0bc147이다.
제품 설치·설정·SSH 전달 제한·방화벽은 변경하지 않았고 새 전체 백업은 없다.
목표active/출시HOLD를 유지한다. 승인된 연결 사용과 일반 복귀는 완료했지만 이미지 계측은
불완전하며, 전체 데이터 QA·학습 적합성·120분·물리 시험·정식 승격은 여전히 미완료다.

### 5.190 이미지 관찰 종료 경계의 개발 회귀 보완

직전 목표 턴은 실제 관찰·종료 검산·일반 복귀·증거 회수를 완료한 PROGRESS로 분류했다.
현재소스 SHA b7e64bfc와 실제 현장 마지막 요청의 미완료를 확인한 뒤, 합성 loopback 장비의
400ms 관찰에서2load/3요청 중 마지막 요청이 느리게 완료되는 결함을 재현했다(red exit1).

새 revision4는 기본 DOM 구간을 보존하고 당시 진행 중 HTTP ID만 최대2초 후속 확인한다.
추가 요청은 제외 수로 남기고, 완료/실패/미완료·후속 DOM 이벤트를 구분한다.
창이 닫힐 경우 cutoff 때 받은 기본 구간 사본을 유지한다.2초는 도구 정리 예산이지 제품 SLO가 아니다.
기본 구간과 후속 구간의 load를 합치거나 네트워크 ID와 같은 이미지라고 추정하지 않는다.

초기 실패 fixture는 응답 시작 전 소켓을 닫아 Chromium 자동 재시도를 유발했다.
응답 body를 일부 보낸 뒤 절단하는 fixture로 원인을 구분했고, 그 이전 실패 로그도 보존했다.
최종 실제 Chromium 회귀13개는 모두pass, fail/cancel/skip0, exit0이다.
성공·부분 응답 실패·기한 초과·관찰 중 페이지 종료, 잘못된 경계/시계,
기존 file origin/가시성/무응답 renderer/수동 개입 없는 요청 수·listener 정리를 포함했다.
이는 개발 PC headless 합성 시험이며 Windows Sandbox·실제 현장 검증이 아니다.

새도구로 기존 현장 원본 b668573c...를 재계산해 revision3 요약과 완전히 같음을 확인했다(exit0).
원래 INCOMPLETE·최대418.7ms·관찰 오류0을 그대로 보존했다.
도구/시험2파일만 이전helper7d1bbb57에 연결한 commit은
07f14e7192b42ea6462afdc003c97760c223428e이다. 관찰기 SHA는
a523bef6d46e57d283e8ea51b07e041baf603b81ec2cb4dd56a77a9b36bc2226이다.
primary HEAD/index는 유지했고 제품 설치본·서버 실행·설정은 변경하지 않았다.

증거: `C:/Users/user/Desktop/SmartFactory/UIEDGE_20261020_e27a6c91`.
다음은 새 도구의 현재 설치형 Electron 격리 확인과 닫힌 fact/CSV/이미지/worker 전체 QA다.
동일 현장15분을 자동 반복하지 않으며, 전체 목표active·출시HOLD·운영 승격 보류를 유지한다.


### 5.191 수정 관찰기의 설치형 앱 확인과 240a 종료 데이터 검사 착수

revision4 관찰기를 같은240a 설치 payload 1,867파일과 함께 개발 PC에서 격리 실행했다.
실제 file dashboard/합성 loopback 장비의15초에서 요청56·load56·관찰 오류0이었다.
원시 이벤트 재계산 일치와 관찰기 제거, 분리 후 동일 logger의 Running, 정상 앱/backend
exit0/forced=false, 자체 Job 잔류0, 진단 listener 소멸을 확인했다.
이 실행의 cutoff 진행 요청은0이며 늦은 완료 처리는 앞 절의13개 회귀 검사 범위다.
Windows Sandbox·실제 현장 연속성·새 성능 기준의 PASS로 확대하지 않는다.
검산 SHA는bb98e8bcced7e00f44ef8397ef8dd80c0dd9b23d6c98bd0314504292445b05a2이며
`UIEDGE_PKG_20261020_7c1d2a90/review.md`와 검산된48파일/72,648바이트 공유 증거에 기록했다.

서버의 이미 닫힌 사본R9d50be5f9e89에서 원장·최종 manifest 등3,144,223,156바이트를
회수하고 당시 결과 SHA d1ac1d25… 및 모든 입력 해시와 일치함을 확인했다.
전후 보호 사본의 목록·크기·시각은 동일하며 회수 exit0/잔류0이었다.
최소 환경의 SSH exit255는 보존하고, 원래 환경을 유지하는 소유 Job에서 연결했다.
공개키·호스트 키·접속 제한·서버 ACL을 변경하지 않았다.

CSV54,143행을 재사용하려고 만든 연결 사본은 독립 파일 검사에서 중단됐다.
내용 검증기는 시작되지 않았고 최초 실패를 보존했다. 이 실행의 CSV·metadata 약73MB만
동일 해시의 독립 사본으로 교정하고 원본 바이트와 단일 링크를 재확인했다.
기존 CsvInputs/검증기 조건은 유지했다. 같은 검증기의 과거4,237,531행/2810.281초
기록을 근거로 이번4,567,705행에는 기존3600초 실행 예산을 사용했다.
15:24:24 KST에 R2 내용 검사가 시작됐으며 완료 전 판정은RUNNING_NO_VERDICT다.
초기 검산 실패와 현재의 내용 검사를 구분한다.

이미지 초기 manifest가 없으므로 임의의 baseline을 만들지 않았다.
닫힌 CSV의 단일 SPOT service와 전체 원장 해시를 대조하여 마지막11,605행
(4,556,101–4,567,705)이 모두 같은 service/captured임을 확인했다.
선택 파일114,449,944바이트는 별도 회수·해시·JPEG 검증 중이다.
6개 선택기 검사는 정상·해시 불일치·중복·다른 service·부적절 경로·실패 상태 보존을 확인했다.
처음 이미지 전달은 Desktop 경계 검사에서 중단돼 파일0개였다. 기존 guard를 유지하고
정확한2026/10/20 이미지 경로의 읽기 검사를 추가한 새 실행을 사용했다.
이는 현재 세대의 선택이며 전체 과거 이미지나 파일 디코딩의 PASS가 아니다.

서버는 같은 일반 실행을 유지했고15:24 화면에서 Running/카메라/작업60210/4가 전면에 보였다.
현재 조작으로 작업 정보를 입력하거나 설치·종료·설정 변경·전체 백업은 하지 않았다.
`CQA240A_R2_20261020_f6be3a19/progress.json`에 진행 중 실행과 다음 확인을 기록했다.
전체목표active/출시HOLD이며 CSV·이미지 소비자 종료, worker 정산, 전체 QA·120분·물리 시험은 남아 있다.

### 5.192 240a 종료 service 이미지 검산과 학습용 관측 참조 구분

앞 절에서 실행 중이던 이미지 검사는 15:33:17 KST에 종료됐다.
선택 service 65b92381의 11,605개/114,449,944바이트가 크기·해시·JPEG 디코딩을 통과했다.
전후 목록·11,605개 실제 검산 결과·원장 해시는 일치하고 선택 사본의 누락/불일치/추가는 0이다.
소비자 exit0·잠금 closeout PASS·내부/외부 Job 잔류 0·강제 종료 없음을 확인했다.
새 통합 검산 SHA는 609a9228912d0a6d8455a9832a9fdd04ebcbbfb4cdaf2dcf1c7d2d065c3b0aad다.
원 선택기의 scope는 바이트 검사 전 상태이며 최종 image-output-verification이 실제 검사 범위를 명시한다.

수신 원장 692,642행 전체 해시를 확인하면서 현재 service 12,665행을 CSV와 대조했다.
poll 1–12665 공백/중복 0, CSV 54,130회 참조의 고유 관측 12,466개가 모두 원장에 있고 raw payload 충돌은 0이다.
반복 참조 41,664회와 startup_pending 13행을 새 물리 관측으로 세지 않는다.
CSV에 채택되지 않은 199관측은 원장에 보존됐으며 유효 온도 197/sentinel 2다.
예전 CSV만의 198개 중간 poll 미참조에 마지막 poll 12665의 미참조 1개가 더해진 값이다.
이 대조는 수신된 원장의 보존 증거이며 장비의 모든 물리 변화 수집·학습 정답 라벨의 PASS가 아니다.
shadow/realtime_candidate 라벨과 요구 수집 주기 미정은 유지한다.

새 원장 ZIP 484,607,396바이트/SHA43201740a80342a7fa13ad38565fef87a99ae330ff25ea6e321a2213d087c917,
선택 이미지·기록 ZIP 118,126,921바이트/SHA2848efe78219fb1f29f8ed38878191abea566f37d8a670932c789a10e754acf1를
공유 return/CQA240A_R2_20261020_f6be3a19에 보존하고 모든 멤버 해시를 대조했다.
기존 CSV/metadata 공유 증거는 재사용했다. 새 전체 백업은 없다.
15:34 서버 화면은 Running/카메라/작업 60210·4가 전면에 있었다.
현재 CSV 전체 검사 exec30247은 계속 실행 중이며 최종 내용 판정·worker 전체 정산·현장 QA·120분·물리 시험은 남아 있다.
목표 active/출시 HOLD와 과거 현장 INCOMPLETE를 유지한다.

### 5.193 240a 종료 worker 정산·실제 종료·승인 설정 연결

서버의 기존 shutdown_evidence에서 PID14360/build240a에 해당하는 begin/final과
해시 sidecar 4파일을 승인된 SSH로 읽었다. 서버 변경·앱 제어·새 백업은 없고
읽기 exit0/자체 Job 잔류0이었다. 기록의 generation 4bf97cade0d225444f21d1b738192176,
session ffdacb1e064f, started_at 01:37:35Z가 이전 현장 HTTP 응답과 일치했다.
그 응답을 보관한 TAR SHA07879d10… 및 실제 worker-result 멤버 바이트를 재대조했다.
과거 현장 FAIL을 변경하지 않았다.

같은 shutdown ID의 시작→완료 기록이 해시로 결합돼 있다. 마지막 기록은
05:08:45.003526Z이고, 보관한 backend native handle의 실제 exit0는
05:08:45.0763584Z다. 같은 생성 시각의 프로세스 5개가 모두 exit0/forced=false였다.
receipt 자체의 process_exit_observed=false를 실제 종료로 재작성하지 않았다.

이미지 enqueued=written=11,605, queue/inflight/unfinished/failure/drop=0,
worker_stopped/writes_drained/accounting_consistent=true와 최종 이미지 manifest·
11,605개 파일 디코딩 완료 결과를 연결했다. 필수 서비스 10항목이 true이고,
실제240a PLC stop 코드가 두 작업 스레드 종료와 driver close를 확인함을 읽었다.
이 결과는 해당 실행의 앱 보고/저장 정산이며 전체 물리 관측 보장의 PASS가 아니다.

helper1947907a의 exact Git 바이트와 별도 승인 설정 참조 SHAe9a6fd68…를 사용한
metadata 검사는 PASS였다. config.ini 전체 SHA0b129491…와 비교용 설정 SHA26114104…를
각각 확인했다. 후자는 승인 기록·민감 키를 제외한 정규화 값이므로 전체 파일 해시와
같을 필요가 없다. 제품240a의 실제 함수를 재사용해 계산했고 승인 fingerprint4bdef05a…와 일치했다.
Low Signal OFF, device readback not_supported, 물리 경계 미시험 조건은 유지했다.

오프라인 검산 exit0, 통합 결과 SHA8e9e880d283bf5f0b998019d4c98f0cbf755e20c3005d613a79be81882afb592.
기록: `C:/Users/user/Desktop/SmartFactory/WQA240A_20261020_948d17bc/review.md`.
15:53 KST 서버 화면은 Running/카메라/작업60210·4가 전면에 있었다.
CSV exec30247은 기존 실행을 유지하며 최종 내용·잠금·종료 검산 전이다.
전체목표active/출시HOLD, 현장·120분·물리 시험·운영 승격 미완료를 유지한다.

### 5.194 직전 CSV 검사 완료와 실제 화면 관찰 실행의 저장 대조

앞 절의 exec30247은 exit0으로 완료됐다. CSV54,143행/누적 수신 원장692,642행/
이미지 원장4,567,705행의 내용 검사 PASS, 입력 종료 재해시 PASS, stderr0,
자체 Job4프로세스 잔류0/강제 종료 없음이다. 소요2712.922초,
결과 SHAbb5dbb4fc2dc43ff450504ef45b675596215cf44ca794cd6c6ea247f2070e569.
단, 이는 관찰 직전 logger c671227f의 자료다. 실제15분 관찰 logger6140e7f1의
CSV5287행과 혼용하지 않는다. 기존 단계 기록은 당시 진행 상태로 보존한다.

실제 관찰 실행은 이미 닫힌 manifest와 누적 원장 prefix를 재사용했다.
서버 끝부분7,028,837바이트를 읽고 그중2,060,828바이트만 종료 범위로 선택했다.
기존 prefix와 이어 계산한 전체 해시가 닫힌 수신 원장57083e51…/
이미지 원장d9ab1c65…와 정확히 일치했다. 실시간 끝부분 읽기 자체를 원자적
snapshot으로 주장하지 않고 이후 실행의 나머지 바이트를 제외했다.

같은 service72ef68d4의 수신1249건, CSV참조5270회/고유1231/반복4039,
시작 미참조17행, CSV미채택 수신18건을 확인했다. 참조 누락·payload 충돌0,
poll1–1249 공백0이다. 이미지1147개/11,360,498바이트의 크기·SHA256·JPEG
검사는 exit0이며 누락/불일치/추가0, 자체 Job15프로세스 잔류0이다.
화면 load2479회와 저장 이미지1147개는 다른 경로이므로 차이를 손실로 판정하지 않는다.

관찰 전후의 native PID/생성시각5개를 종료 증거와 연결했다. backend3760의
shutdown begin/final·sidecar·동일ID·시각 순서를 검산하고 등록=저장1147,
대기/실패/drop0, 필수10종료 항목과 실제5프로세스 exit0/forced=false를 확인했다.
별도 control generation ID를 원래 관찰에서 얻었다고 확대하지 않았다.
고정 helper1947907a/승인 설정 참조로 metadata와 Low Signal OFF 프로파일도 일치했다.
통합 SHA1e0f240b119769861abdfe026d000a2134af29051497bcddb5a45cf71047213f.

실제 관찰 CSV의 전체 내용 검사는 같은 검증기를 사용해16:13:33 KST에 시작했다.
exec66307/driver48604 생성1792480407.3785608, 기존3600초 예산이며 판정 전이다.
소비자 요구에 맞춰 원본+delta의 동일 해시 독립 입력3,153,404,479바이트를
개발 PC에 구성했고 서버 원본·기존 증거를 변경하지 않았다. 새 서버 백업은 없다.
공유 보존은 기존 prefix를 재사용하고 새 delta·이미지·검토 기록만 추가한다.

기록: `C:/Users/user/Desktop/SmartFactory/UIQA_20261020_4edec30b/review.md`.
16:14 KST 서버 화면은 Running/카메라/작업60210·4가 전면에 있었다.
기존 화면 INCOMPLETE는 보존한다. 새 CSV 최종 내용·입력 closeout·자식 종료,
수정 관찰기 현장 재검증·전체 QA·120분·물리 시험·운영 승격은 남아 있다.
전체목표active/출시HOLD를 유지한다.

### 5.195 revision4 관찰기의 최소 서버 전달과 import 검증

실제 관찰 CSV exec66307을 유지하며, 종료 경계 처리 수정본을 서버에 준비했다.
Git commit07f14e71의 관찰기 원바이트21,700과 기존 wrapper의 import 경로2곳만
바꾼4,922바이트, 의존성 목록17,280바이트의3파일/43,902바이트를 전달했다.
server `UIREPEAT_20261020_b85f1c04`에서 전수 SHA256을 대조했다.
기존 `UIWATCH_20261020_9fd4dfaa/package/playwright-core`106파일은 원manifest
SHA0b06697c…와 새 목록을 대조하고 읽기 잠금을 유지해 재사용했다. 기존 파일 덮어쓰기,
의존성 재설치·전체 패키지 재복사·부모 ACL 변경은 없었다.

개발 Node 구문2개와 native PS5.1 parse exit0, 서버 Node 구문2개/import-only1개도
exit0·stderr0이었다. 서버의 세 소유 Job은 모두 잔류0/강제 종료 없음이고 개발 전달
Job도11프로세스 정리 후0, worker exit0이었다. 서버 기존 Node24.12.0과 Playwright
Core1.60.0의 연결 없는 모듈 로딩만 확인했으며 CDP 접속·앱 제어는 수행하지 않았다.
현재 일반 실행 프로세스5개의 PID/생성시각은 전후 같고 진단 인수·19221 listener는 없었다.
16:23 KST 화면에서 Running/카메라/작업60210·4가 전면에 보였다.

기록: `C:/Users/user/Desktop/SmartFactory/UIREPEAT_20261020_b85f1c04/review.md`.
새 묶음에는 오래된 실행 request를 포함하지 않았다. CSV 내용/closeout 결과 확인 후
현재 실행을 다시 결합해 승인된 정상 재시작·15분 재관찰·일반 복귀 절차를 이어간다.
이전13개 회귀/설치형56요청 검사는 원해시로 재사용했으며 현장 통과로 확대하지 않는다.
목표active/출시HOLD, 과거 화면INCOMPLETE·120분·물리/과거 데이터 처리의 미완료를 유지한다.

### 5.196 현재 일반 실행의 종료 관찰 입력과 이미지 재측정 절차 준비

기존 CSV exec66307을 유지한 채 현재 일반 실행d59057c9/CSV144152를 다시 읽었다.
기존 정상 종료 어댑터에서 폴더·logger·CSV·요청 해시만 치환하고 역치환 동등성을 확인했다.
새4파일10,094바이트를 `UIRECLOSE_20261020_70e41b83`의 개발/공유/서버 경로에서
크기·SHA256으로 대조했다. native PS5.1 parse 및 서버ValidateOnly exit0이며
child_started=false, 앱 종료·진단 포트 개방은 수행하지 않았다.
개발 소유 Job17프로세스는 모두 정리됐고 worker exit0/강제 종료 없음이다.

revision4 실행 입력 생성기는 과거 진단 기록으로 오프라인 검증했다. 기존1100초
진단 Job·SSH 단절 확인·106의존성 잠금에 현재 예상5프로세스의 전체 native 생성시각
대조를 연결했다. 잘못된 listener·logger·설정·프로세스 목록·요청 경로5조건을 거부했고
최종 생성본의 PS5.1 parse exit0을 확인했다. 이 과거 요청은 서버 실행용이 아니다.
실제 재시작 후 새 logger/native 실행을 읽어 별도 요청을 만들도록 제한했다.

기존OPV2의 operational-observe 실행 파일과7개지원 파일은 현재 해시가 보존 기록과 같다.
helper7c0af584→07f14e71의 차이는 이미지 관찰기/검사2파일뿐이므로 재빌드하지 않는다.
기존15분 HTTP·자원 관찰 결과와 후속120분 미시작을 구분했다.
기록: `C:/Users/user/Desktop/SmartFactory/UIRECLOSE_20261020_70e41b83/review.md`.
CSV 최종 내용 판정과 입력/자식 closeout 후 승인된 정상 종료·이미지 재관찰·일반 복귀를
이어간다. 과거INCOMPLETE·물리NOT_TESTED·출시HOLD와 전체목표active를 유지한다.

### 5.197 실제 관찰 실행의 CSV 검사 완료와 revision4 현장 관찰 시작

앞 절의 exec66307은 종료 코드0으로 완료됐다. 실제 화면 관찰 logger6140e7f1의
CSV5,287행/순번1–5287, 수신 원장693,891행·이미지 원장4,568,852행의
전체 내용 검사를 통과했다. CSV 참조5,270건의 원장 연결100%, 누락0이며,
입력5파일3,153,404,479바이트의 종료 재해시와 입력 잠금 검증도 PASS다.
검증기·worker exit0, stderr0, 자체 Job 잔류0/강제 종료 없음, 소요2624.75초다.
전체 stdout5,914바이트와 필수 결과 필드를 읽고 검산했다.
결과 SHA1f36080db01d79df41f564d2a4fff64002afb90e7f7931ab79d53c8b226808a4.
선택 입력이 없는 changeover/phase 검사는 unknown으로 보존했고, 이 CSV 결과를
별도 승인 프로파일·물리 전수 측정·전체 데이터 범위의 통과로 확대하지 않았다.

기록: `C:/Users/user/Desktop/SmartFactory/UIQA_20261020_4edec30b/csv-completion-verification.json`.
완료 기록8개는 공유 csv-completed.zip10,716바이트/SHAaef1bc4c…에 보존했고
대형 입력은 기존 검산 사본을 재사용했다. 앞선 화면 INCOMPLETE는 변경하지 않았다.

이후 일반 실행d59057c9를 관찰 READY 확인 후 UI의 X로 정상 종료했다.
CSV35,479행/순번1–35479, 설정0b129491…·metadata·종료 결과와
native5프로세스의 exit0/forced=false를 확인했다. 결과 SHAa014b409…,
종료 observer/개발 Job 잔류0이다. 이것은 제한된 종료 영수증 검사이며 새 실행의
전체 fact/이미지/내용 검사를 대신하지 않는다. 서버와 개발 PC의 시계 차이가 있어
서로 다른 호스트의 UTC만으로 종료 사건의 순서를 판정하지 않았다.

승인된 임시 loopback 연결로 동일240a 설치본을 새로 실행했다.
logger04250393-67ab-44cd-9017-80e870070b6b/main7084/backend10972와
native5프로세스를 새 요청에 결합했다. listener는127.0.0.1:19221 하나이며
소유main7084·설정SHA 일치, 화면Running/작업60210·4·카메라 전면을 확인했다.
748바이트 요청만 새UIR4RUN 폴더에 전달하고 기존 관찰기3파일/라이브러리106개를 재사용했다.
요청SHAbe13b722…/관찰bodySHA6f5c23e6…의 nativePS5.1 parse와 전달 검산은exit0이다.
서버08:06:28Z 연결 표식으로 revision4의900초 실제 화면 관찰 시작을 확인했다.
관찰 완료·원본 재계산·정상 종료·19221 제거·일반 실행 복귀는 이 기록 시점에 진행 전이다.
기록: `C:/Users/user/Desktop/SmartFactory/UIRECLOSE_20261020_70e41b83`.
새 설치·설정 변경·전체 백업은 없으며 전체목표active/출시HOLD다.

### 5.198 revision4 실제 화면 관찰 완료와 진단 연결 제거

exec74182는900초 기본 구간 후 exit0으로 끝났다. 관찰기 raw를 exact07f14e71
바이트로 재계산한 결과와 저장 요약이 일치했다. 요청2,480건/load2,479회/오류0,
measurement COMPLETE/request-and-load PASS, 기본 구간900017.4ms다.
load 간격 중앙값363.2ms/p95 392.6ms/p99 408.4ms/최대454.6ms,
시작→첫load234ms/마지막load→기본 종료360ms였다.
종료 경계 진행 중1요청은 추가47.494ms 동안 완료했고 미해결·제외 새 요청0이다.
tail DOM load2회는 기본 구간에 합치지 않았고 요청별 짝짓기는 미평가로 유지했다.

server controlGe2eb1b4746d4의 회수 파일 전수 해시, ui-receipt·request SHAbe13b722…,
logger04250393/CSV170108/build240a, 전후 native5개를 대조했다.
관찰·회수의 개발 Job6/7프로세스는 모두 정리됐고 worker exit0/강제 종료 없음이다.
서버 관찰 Job도 exit0/잔류0이며 CDP 접속은 분리됐지만 포트는 앱 정상 종료로 제거했다.

새 종료 입력4파일의 parse·전달·ValidateOnly를 검산하고 controller READY 후
UI의 X로 정상 종료했다. controlG49da801b1430/runtimeR522a626d413c,
결과 SHA cf815b411c624c7bc66a11ca7dbe35f6a863907af4e5fc00d6ef11440940c11d.
CSV5,524행/순번1–5524, 시작12/유효5512, 설정SHA0b129491…를 확인했다.
native5개 exit0/forced=false와 관찰 전후 PID/생성시각이 일치했다.
backend10972의 begin/final/sidecar·동일attempt·서버 시각 순서를 연결했으며
등록=저장1183, 대기/실패/drop0, 필수10종료 단계가 true였다.
앱 영수증의 process_exit_observed=false를 수정하지 않고 별도 native 증거를 사용했다.
이는 앱 보고 저장 정산이며1183개 파일의 독립 바이트 QA나 전체 원장 대조를 대신하지 않는다.

같은 검산된 일반 바로가기로 재시작했다. 새logger551b463e-79f4-4d74-b8bd-a0ae922f207f,
CSV172326, 진단 인수·19221 listener 없음, 주요 설치 파일3개의 SHA·설정SHA가 일치했다.
현재 설정 이미지대기0.3125초/온도조회1초를 읽었으며 변경하지 않았다.
17:24 KST CUA에서 Running·작업60210/4·카메라의 최대화 전면 표시를 확인했다.
기록: `C:/Users/user/Desktop/SmartFactory/UIRECLOSE_20261020_70e41b83/execution-review.md`.
이전INCOMPLETE를 보존하고 새 측정의 요청·load 범위만 통과로 표시한다.
물리 표시 연속성·장비 프레임 나이·학습 적합성은 미평가, 새 종료 실행의 전체데이터QA와
120분·물리 경계·과거 데이터 공백·운영 승격도 남아 있으며 목표active/출시HOLD다.

### 5.199 두 종료 실행의 저장 이미지·원장 경계 검산과 120분 실제 수집 시작

DQREV4_20261020_f4a7c091에서 기존 UIQA 원장 prefix와 새로운 닫힌 delta를 검산했다.
일반d59057c9: CSV35,479/수신8,265/이미지7,639, 화면04250393:
CSV5,524/수신1,290/이미지1,183이다. 각 누적 원장의 실제 SHA가 종료 manifest와
일치했으며, 현재 실행이 추가한 tail은 제외했다. 실시간 전체 파일의 원자적 snapshot을
주장하지 않는다. CSV 참조 누락·payload 충돌·poll 순번 공백0을 확인했다.

이미지8,822개/86,154,632바이트는 지정 경로 회수 후 크기·SHA256·JPEG 디코딩 전수 검사,
입력 잠금 재확인과 선택 범위 추가 파일 검사를 통과했다. 회수/검증기exit0·자식 잔류0,
두 종료 영수증의 등록=저장·대기/실패/drop0, 필수10단계와 실제native5개exit0을 연결했다.
앱 내부 process_exit_observed=false는 유지하고 실제 종료는 별도 native 증거로 확인했다.

CSV 비참조 관측109/20개는 원장에 남아 있으며 유효 온도117/sentinel12개다.
일반 실행 전체의 sentinel980개와 각 실행 첫missing/이후previous_poll 진단 연결을
보존했다. 같은payload 자체를 중복 측정으로 삭제하거나 진단 품질을OK로 대체하지 않았다.
서버 완료 시각 간격 최대1,123.88/1,467.00ms는 호스트 관측 간격으로 한정했다.
학습 적합성이나 장비100ms 물리 변화의 전수 수집 증거로 확대하지 않는다.

CSV 소비기 입력은 검증된 E: 새 전용 폴더에 각각3,208,083,516/3,169,211,233바이트를
재구성했다. 원본 hash·대상 전체 hash·읽기 잠금/동시 쓰기 차단을 확인했고,
기존소비기e728730a…/clean helper0e5a4fdf로 두 실행을 순차 검사 중이다.
첫 검사17:47:29 KST 시작, 최종stdout·입력 재해시·정리는 아직 대기한다.

OP120_20261020_61be7c90 첫 시도는 payload1,867파일561,846,463바이트 검산 후
initial process-identity-changed로측정 전 종료했다. 제어기·하위Job 잔류0/강제 종료없음,
원본실패tar SHA6c4f7325…를 보존했다. 원인은 요청 생성의 datetime 경유로100ns
일곱째 자리가 잘린 것이며 각created 값이4.76837158203125e-7초 달랐다.
정수FILETIME에서epoch를 빼고초로 환산하도록 수정했고 실제 로컬native/psutil
정확 일치와 문제의 두 생성시각 회귀 검사를 통과했다. 식별 허용오차는 완화하지 않았다.

새OP120R2 요청SHAf02db7aa…를 전수 전달 검산·PS parse·ValidateOnly 후 실행했다.
현재main7528/backend20088/logger551b463e/CSV172326와config0b129491…를 결합했다.
serverrun-6f0c1f3f0ac8의 초기runtime/control/configuration검사PASS와
observation.json의7200초/origin899583310046200을 확인해 실제 수집 시작으로 기록했다.
개발exec10915는진행 중이며 최초실패를PASS로바꾸지 않는다. 현재일반실행의
19221·debug인수없음, 작업60210/4·Running·카메라전면표시를 확인했다.
목표active/출시HOLD이며 CSV종료·120분완료·물리경계·과거공백·학습적합성은별도남는다.

### 5.200 120분 관찰 이후 같은 실행의 정상 종료 준비

exec74970(CSV)와10915(120분)의 실행 핸들이 계속 살아 있음을 확인했다.
완료 전에 앱을 닫지 않도록 O120CLOSE_20261020_61be7c90에 종료 준비 어댑터를 만들었다.
검증된 준비·회수 템플릿의 해시를 대조하고, 두 CSV 소비기의 완료 검산 및120분 원시
재계산·소유 프로세스 정리를 다음 단계의 선행 조건으로 결합했다. 이전 실행용 요청을
그대로 재사용하지 않으며, 실제 준비 시 현재logger/CSV/config와main/backend의 native
생성 시각을 관찰 시작 기록과 대조한다.

로컬 구문 검사와 미완료 실행 거부 확인은exit0이었다. 실제main() 진입에서
PREREQUISITE_EXECUTION_NOT_TERMINAL로 서버 접속 전에 중단되는 것을 확인했고,
서버 전달·관찰기 시작·앱 제어는 수행하지 않았다. 이는 실행 준비 검증이며 현장 종료
통과가 아니다. 120분 결과에 실패·불충분·정리 오류가 있으면 그 원본을 먼저 검토한다.

최종 순서는 OP120R2_20261020_61be7c90/completion-plan.md에 남겼다.
120분health/data·자원 관찰을15분 실제화면 관찰과 합쳐120분화면시험으로 표기하지 않는다.
같은 실행의 정상 종료·새 데이터 대조 후 일반 실행과 작업자 화면을 복귀한다.
제품·설정·수집 주기·진단 연결 변경 없이 목표active/출시HOLD를 유지한다.


### 5.201 CSV 소비기의 60분 제한 종료와 별도 재시도

첫 DQREV4 소비기는 18:47:47 KST에 command-deadline으로 종료했다. 출력 전 제한에
도달해 PROCESS_INCOMPLETE_NO_CONTENT_VERDICT이며 revision4는 시작되지 않았다.
입력 context 종료 재검산 PASS, 소비기·바깥 Job 잔존0을 확인했다. 기존 원본 실패와
로그 해시는 보존하고 데이터 내용 불합격이나 통과로 변경하지 않는다.

새 clean helper commit3501e4406e9dfffd6a240231537edadf3ca8e51c에서 명시적 명령
예산 상한만3600→7200초로 늘렸다. 기본120초와 데이터 조건, 고정CSV EXE e728730a…,
입력 잠금·정리·출력 한도는 유지한다. 수정 전 새 회귀2개는 상한 거부로exit1,
수정 후 해당 모듈 전체24개145.764초/skip0/exit0, Ruff exit0, diff check exit0이다.
이는 시간 예산 회귀 검증이며 현장 데이터 검사가2시간 안에 끝난다는 증거는 아니다.

DQREV4R2_20261020_f4a7c091에서 기존E: 입력을 재사용하며 새 대용량 사본은 만들지
않았다. 첫 소비기는19:00:06 KST에 입력 전수 재해시 후 실제 실행을 시작했다.
exec88825/driver62764, 두 소비기 순차·각7200초/바깥15000초로 제한한다.
실제 stdout·내용 판정·입력 종료 재해시·정리는 아직 대기 중이다.

120분 exec10915는 같은 제어기/서버run을 계속 관찰 중이다. 서버 앱·설정·수집 주기를
변경하거나 관찰을 재시작하지 않았다. O120CLOSER2와 completion-plan-r2.md에는
새CSV 결과 경로만 연결했고, 실제main 진입이 미완료 관찰 때문에 서버 접속 전 거부됨을
확인했다. 구 어댑터·원래계획은 당시 증거로 보존한다. 출시HOLD/목표active를 유지한다.


### 5.202 고정 CSV 소비기의 경로 검사 비용 조사

CSV exec88825와120분 exec10915가 같은 프로세스 생성 시각으로 살아 있음을 확인했다.
고정EXE e728730a…의 Python archive에서 이미지 원장 검사와 두 경로 판정 함수의
코드 객체를 읽어, 원 빌드4cc7393e/소스3040f3e9…의 컴파일 결과와 대조했다.
filename만 정규화한 코드 객체 세 개가 일치했다. 실행 중 프로세스에 접속·주입하지 않았다.

원래 소스는 이미지 행마다 Path.resolve()로 실제 경로를 확인한다. 기존E: 원장의
첫512경로만 별도 계측했으며 전체0.812초, resolve누적0.7440062초, Windows
_getfinalpathname4341회/readlink2805회였다. 경로 형식·외부 이탈 검출은0이다.
이 결과는 경로 처리의 소규모 비용이며 현재 소비기 전체 프로파일이나 과거timeout의
확정 원인이 아니다. 전체 완료 시각으로 단순 외삽하지 않는다.

CSVPATH_20261020_3501e440/path-probe.json과review.md에 원문·범위를 보존했다.
스크립트·결과 대조·Ruff 모두exit0. 제품·검사기·서버 설정·진행 중 관찰은 변경하지
않았다. 재시도가 또deadline으로 끝나면 종료·정리 증거 후 단계별 비용과 경로 검사를
조사하며, 시간 제한 반복 확대나 경로 검사 생략을 자동 수행하지 않는다. 목표active/출시HOLD.


### 5.203 현장 후보와 승인된 롤백 기준의 식별 기록 대조

120분과 CSV 실행 핸들이 계속 살아 있는 동안 보존된 설치 영수증의 연결을 검산했다.
설치 검토 review를 archive 해시와 대조하고 request·installer-inputs·installer-exit·
candidate/preceding payload·result 6개 파일의 전체 해시·크기를 확인했다.
설치 종료0/handle 유지/강제 종료false, 후보240a와 직전후보8de의 build·버전·installer
크기/SHA, payload 목록의 행수·바이트 합계가 일치했다. 서버 파일의 재검산은 아니다.

운영 기준 문서에는 현장 검증 후보240a/56ec1262…, 직전 후보8de/f1b6d4d8…,
마지막 승인·등록 기준541d/08c061ee…를 구분했다. 새 절을 제외한 원문은 변경 전
21,831바이트/SHA08587200…와 정확히 일치해 기존 승인·정리 경로 기록 보존을 확인했다.
17:54:31 실행 snapshot의 build/logger/CSV와120분 초기 관찰 자료도 연결했다.
동일 표시1.0.30만으로 설치본을 혼동하거나 후보를 승인된 기준으로 바꾸지 않는다.

GATE_REVIEW_20261020_240a에 검산과 남은 R1–R6/Act 항목을 남겼다.
실제120분 종료·원시 재계산과 두 CSV 소비기 종료, 같은 실행의 정상 종료·저장 검증은
계속 진행해야 한다. 물리·과거 공백 및 전체 QA를 완료로 세지 않으며 출시HOLD를 유지한다.

### 5.204 보존된 후보 시작 로그와 계획상 반복 측정의 범위 대조

SB20의 report·닫힌 전체 manifest·선택 profile ZIP과 내부 debug_electron.log의
해시를 대조했다. 완료 runtime6회 중240a 후보는 I4/I5/I10의3회이며 나머지는 이전
후보/롤백이다. PID·생성 시각·startup session·build를 연결한9개milestone이 각 존재한다.
화면 준비 telemetry는1,606.3/1,469.0/2,184.9ms이고 OS 생성부터 로그까지는
1,700.37/1,534.16/2,247.00ms다. 두 시계를 섞거나 외부 launcher stopwatch로 표기하지 않는다.

이 matrix는 서로 다른 데이터 조건이며 R2의 통제된 초기 시작10회 완료를 증명하지
않는다. 다른 보존 후보 자료를 먼저 확인하고 부족한 조건만 이어간다. 기존 I4 중단,
등록 롤백의 종료502와 미검증 성능 항목은 보존한다. 새 설치·앱 실행은 수행하지 않았다.
기존 시작 측정 도구의 기본 taskkill 정리는 현장 정상 종료 요구와 맞지 않으므로
재사용 시 KeepRunning과 같은 실행의 정상 종료·저장 검증을 연결해야 한다.

GATE_REVIEW_20261020_240a/startup-coverage.json과.md에 범위·근거·후속 조건을
기록했다. 검토 스크립트와 Ruff F/E9는exit0이다. 기존 CSV와120분은 같은 핸들로
실행 중이며 제품·서버·설정 변경과 신규 성능 시험을 겹치지 않았다. 전체목표active/출시HOLD.

### 5.205 현재 실행의 정상 종료와 과거 CSV 검사의 실행 순서 분리

R2 종료 준비의 두 과거 CSV 완료 선행 조건은 계획상 필수 관계가 아니라 추가한
실행 순서였다. 과거 logger d59057c9/04250393의 고정 입력은 개발 PC의 별도E: 사본이며
현재 서버 logger551b463e/CSV172326과 독립이다. 고정 provenance·닫힌 대조 기록의 해시,
입력 경로·로컬 드라이브·reparse 부재·크기를 확인했다. 내용 전수 검사나 재해시는 별도
CSV 소비기의 책임으로 유지한다.

O120CLOSER3는120분의 실제 종료·정리·회수·원시 재계산·정확한 실행 identity 조건을
유지하고 과거 CSV 검사를 전체 QA의 별도 필수 항목으로 기록한다. 관련 구간을 복원하면
기존 선행 조건 함수와 정확히 일치한다. 경로/현재logger/현재CSV/이탈8개 부정 사례를
거부했으며, 실제main 진입은 아직 진행 중인120분 때문에 서버 연결 전에 거부됐다.
준비기·생성 도구·Ruff/구문 검사exit0, 서버 접속·앱 제어 없음이다.

현재 완료 후 절차는 OP120R2/completion-plan-r3.md와O120CLOSER3를 사용한다.
exec88825의 두 CSV 내용 판정·종료 입력 재검산·정리는 계속 필수이고 실패를 숨기지 않는다.
원R2와 증거는 보존하며,120분 검산 뒤 승인된 같은 실행의 정상 종료 검증을 별도 CSV
완료 때문에 지연하지 않는다. 전체목표active/출시HOLD 유지.

### 5.206 120분 관찰 종료·원시 재계산과 동일 실행 종료 준비

OP120R2의 실제 120분 관찰(17:54:58.600 시작)은 후처리를 포함해 19:56:10에
종료 코드 0으로 끝났다. 소유 진단 프로세스 잔류 0, 강제 정리 0, 오류 0을 확인했다.
같은 controller Geaae461d3263/run-6f0c1f3f0ac8에서 12,516파일을 회수했고
콘솔 해시→controller→launcher→manifest→원시 파일 연결과 세 재계산 단계가 일치했다.
review_operational120.py는 종료 0, RECORDED_SUMMARIES_REPRODUCED다.

정규 health 3,600회, 경계 포함 3,602회, data 1,200회 모두 요청 오류·타임아웃·누락 0이다.
최대 응답은 health 181.5504ms, data 86.1782ms이며 200/500ms 참고선 초과 0이다.
자원 관찰 1,441/1,441회, 미측정 간격 0이고 같은 프로세스·logger·설정 연결이 충족됐다.
이번 PASS는 COLLECTION_AND_BINDING_ONLY이며 운영 요구 성능·전체 저장 데이터·
물리 경계·학습 적합성을 통과로 바꾸지 않는다. 합성 이미지 요청은 추가하지 않았다.

O120CLOSER3의 현재 실행 재확인과 4파일 전달·서버 구문/ValidateOnly 검증은 종료 0이다.
logger551b463e와CSV172326이 유지됐고 종료 도구를 생성했다. 아직 종료 관찰기를
시작하거나 앱을 닫지 않았다. 19:58 화면은 Running·카메라·작업60210/3으로 정상 표시됐으며
작업 정보는 수정하지 않았다. 다음에는 실제 관찰 준비 직후 정상 X 종료를 수행하고
같은 실행의 저장·잔량 검산 및 일반 실행/작업자 화면 복귀를 이어간다.

별도 E: 과거 CSV 소비기 exec88825는 계속 실행 중이며 최종 내용 판정은 아직 없다.
120분을 재실행하지 않는다. 이전 실패와 미검증 항목을 보존하고 전체목표active/출시HOLD다.

### 5.207 120분 실행 정상 종료·일반 복귀와 현재 세대 저장 대조

O120CLOSER3의 실제 READY marker와 살아 있는 controller를 확인한 뒤 원격 화면의 X로
정상 종료했다. 같은 logger551b463e의 CSV41,487행·연속번호와 프로세스5개의 실제 종료0을
회수·검산했다. 이미지 등록/저장8,912건, 대기·실패·폐기0, 종료10단계 완료를 native 생성
시각·120분 전후 경계·shutdown begin/final 해시·실제 종료 시각으로 연결했다.

검산한 일반 바로가기로 재시작한 새 logger는 a3b807df-da24-4928-a899-ddeb79468923이며
CSV200859다. 설치 핵심3파일·설정SHA가 유지되고19221/디버그인수 없음, 작업60210/3을
확인했다. 창을 최대화·전면 표시했고 normal-return/server-dashboard.png로 확인했다.
앱 강제 종료·설치·설정 변경·전체 백업은 수행하지 않았다.

DQ120은 기존 E: revision4 prefix를 재해시하고 약16MB의 추가 범위만 회수해 이번 종료
시점의 수신 기록713,135행·이미지원장4,586,586행의 전체SHA를 재구성했다. 현재 세대의
수신9,689건/CSV41,487행/이미지8,912건을 분리했으며 poll gap·참조 없는 키·payload 충돌0이다.
CSV가 참조하지 않은 수신151건(valid145/sentinel6)은 원본 원장에 존재한다. CSV의31,932개
반복 참조를 새로운 온도 측정으로 세지 않으며 물리 샘플·학습 적합성은 미검증이다.

이미지 최초 시도는 C: 여유공간 조건에서 전송 전에 중단됐고 원본 FAIL을 보존했다.
동일 검사·여유공간 조건을 유지해 검증된 E: 새 폴더로85,714,674바이트를 회수하는
exec92052를 실행했다. exec88825의 과거 두 CSV 소비기도 실행 중이다. 둘의 실제 종료와
전체 출력 검산을 기다리며 현재 CSV 입력/소비기 준비 코드는 생성·Ruff/구문 검사0이다.

종료·복귀 증거는 Z:/SmartFactory/20261020/return/POST120_20261020_61be7c90/closure-records.zip에
파일별 검산해 보존했다. 후속 단계는 DQ120/progress.json에 기록했다. 전체목표active/출시HOLD.

### 5.208 보존된 현장 일반 시작 3회의 시간·실행 identity 대조

GATE_REVIEW_20261020_240a에서 승인된 SSH로 Electron 로그 4개의 고정 길이 범위
26,443,216바이트를 읽었다. 같은 파일 핸들에서 해당 범위의 두 번 읽기 SHA가 일치했다.
로그 prefix 검산이며 쓰기 중 파일의 원자적 snapshot이라고 주장하지 않는다.
앱 제어·설정 변경·추가 시작·전체 백업은 수행하지 않았다.

일반 실행 PID7760/7528/14568을 native 생성 시각과 startup session, backend spawned PID,
정확한240a commit에 연결했다. 필수 milestone9개와 backend progress9개가 각 실행에
존재한다. 앱 내부 대시보드 준비는8,297.5/8,288.8/11,792.6ms, OS 생성부터 기록된
준비 시각까지는8,407.00/8,406.11/11,966.22ms다. 앞선 두 실행의 정상 종료5프로세스/exit0도
연결했다. 세 번째는 일반 복귀 확인 당시 Running이며 종료 완료로 세지 않는다.

외부 실행 명령 직전 stopwatch와 통제된 캐시 조건은 없으므로 전체 시작 성능 계약과
격리 초기10회는 여전히 미검증이다. 현장 로그3회를 이 두 조건의 대체로 사용하지 않는다.
회수·PowerShell 구문·독립 연결 검토·Ruff F/E9는exit0이며 근거는 같은 폴더의
field-startup-coverage.json/.md다. 현재 이미지8,912개 회수 해시는 일치했으나 전체
디코딩·닫힌 CSV 소비기 결과는 아직 진행 중이다. 전체목표active/출시HOLD를 유지한다.

### 5.209 첫 닫힌 CSV 내용 검증 완료와 이미지 입력 재검산의 분리

DQREV4R2의 ordinary 소비기는 6,359.093초 후 종료0으로 완료됐다. CSV35,479행,
수신원장702,156행, 이미지원장4,576,491행을 검사했고 수신 참조35,464행의
연결 누락0·출처 충돌0이다. 닫힌 원장의 행 수·SHA·poll gap과 출력 전체를 읽고,
원 검증기의 동일 세대 검사 본문으로 독립 대조했다. 입력은 검사 전후 재해시와
핸들 보유 조건이 충족됐고 소비기4프로세스 잔류0·강제 정리0이다.
ordinary-completion-verification.json은 단일 완료 세대의 증거이며 두 세대 suite
완료를 뜻하지 않는다. exec88825는 20:46:06부터 revision4 소비기를 계속 실행 중이다.

이미지 R2는 8,912개 전체 내용 검사가 종료0/PASS였으나, 이를 감싼 도우미가
입력 후검산에서 1,920초 제한에 도달해 종료1/FAIL이다. live stack의
ImageInputs.__exit__ → recheck → image_names를 당시 실행 identity에 연결했다.
독립 내용 재대조는 통과했지만 전체 입력 검증 완료로 바꾸지 않는다.
DQ120/image-r2-partial-review.json과 원 실패·정리0 증거를 보존했다.

R3는 회수된 동일85,714,674바이트를 재사용하며 전송·서버 접근·백업을 추가하지 않는다.
입력 잠금/전후 재검산/기존 frozen 소비기와 내부900초 제한을 유지했다. 실제 관찰한
전후 검산 단계를 포함하도록 바깥 한도만3,600초로 준비하고 별도images-r3 결과 경로에서
exec42001을 실행했다. 전체 결과 검증기는 경로 한 곳만 변경해 준비했으며 아직 미실행이다.

CSVSTACK의 비중단 stack3회는 같은 ordinary 소비기의 이미지 경로 Path.resolve 구간을
가리켰다. 네 번째 진단은 부분 읽기 오류299이며 별도 실패로 보존했다. 이 세 표본으로
전체 실행의 시간 비중·디스크 원인·완료 시간을 추정하지 않는다. 현재 전체 내용 검사는
통과했으므로 이 진단 실패를 소비기 실패로 해석하지 않는다.

단일 세대 결과 검토·stack 증거 검토·새 검토 코드 Ruff F/E9는 모두 종료0이다.
DQ120/progress.json과 PDCA의 ordinaryCsvVerifiedImageR3Running20261020에
현재 핸들과 다음 실행 조건을 기록했다. 다음은 R3 실제 종료 후 전체 입력·내용·종료
검산, post120 입력 재구성, 기존 두 소비기 실제 종료 후 post120 내용 검사다.
완료된120분은 반복하지 않는다. 전체 데이터·물리 샘플·학습 적합성·운영 승격은 미완료다.

### 5.210 120분 세대 이미지·종료 잔량 검증 완료와 CSV 입력 준비

이미지 R3(exec42001)는21:04:11에 종료0, 강제 정리0, 최종 소유 프로세스 잔류0으로 끝났다.
8,912개/85,714,674바이트 전체 내용·fact 연결·입력 전후 재검산을 통과했다. 같은 logger551b463e의
정상 종료 worker 등록=저장8,912, 대기/실패/폐기0, 필수10단계와 native5프로세스 종료0을
독립 검증기에서 연결했다. DQ120/images-and-drain-verification.json과 원 R2의 불완전 판정은
별개로 보존한다. 이번 PASS는 닫힌 실행의 선택 이미지와 저장·종료 회계 범위다.

exec16294는21:08:32에 post120 검사용5파일/3,233,842,891바이트를 준비하고 종료0으로 끝났다.
기존 고정 prefix와 회수된delta를 읽기 잠금으로 연결해 원본 부분·재구성 결과의 SHA를 대조했다.
CSV41,487행, 이미지원장4,586,586행에 해당하는 입력이며 전체 내용 소비기는 아직 미실행이다.
앞선 두 세대 suite exec88825의 revision4 소비기가 실제 실행 중이라 완료·정리 확인 후
같은 frozen 소비기로 post120 검사를 시작한다. 완료된120분과 이미지 검사를 반복하지 않는다.

GATE_REVIEW의 historical-limits.json/.md는 최초 APPLY17파일과 과거drop11표본·정확한
4c 소스 Git blob을 대조했다. 원 timeout의 경로는 추론이고, 과거15회는 개별 ID·사유·payload가
저장되지 않은 거부 시도 수다. 최신 정상 운전으로 이 원인·영향·복구를 확정하지 않는다.
첫 원문 시각 필드 가정 오류(exit1)는 보존했고 실제at/collected_at 구분 뒤 대조/Ruff는exit0이다.
과거 영향·처리 결정은 아직 없으며 현재 후보 검증 완료 후 판단 자료로 연결한다.

상태 키는 post120ImagesAndDrainVerifiedCsvInputsReady20261020이다. 서버·제품·설정·
등록 롤백 기준을 변경하지 않았으며 전체 목표active/출시HOLD를 유지한다.

### 5.211 앞선 두 세대 CSV 완료와 120분 세대의 기록 간격 대조

exec88825는21:20:39에 종료0, 강제 정리0, 잔류 프로세스0으로 끝났다.
DQREV4R2/verify_csv_suite_completion.py를 실제 실행해 ordinary35,479행과
revision4 5,524행의 frozen 소비기 결과·전체 출력·입력 결합·종료 정리를 대조했고 exit0이다.
이는 두 닫힌 실행의 CSV·fact 참조 검사이며 물리 샘플 완전성/전체 이력 판정을 대신하지 않는다.
입력 준비를 마친 post12041,487행의 검사는21:24:13부터 exec42917에서 실행 중이다.
앞선 실패와 완료 기록을 보존하며 동일7200초 소비기·7800초 외부 한도를 유지한다.

DQ120/record-intervals.json/.md는 logger551b463e 전체 실행17:23:26–20:04:58 KST의
온도 요청·CSV 행·저장 이미지 시각을 분리했다. 120분 구간만의 분포로 표현하지 않는다.
온도 HTTP 요청 시작 간격 중앙값1.000080초/최대1.215981초, CSV 행0.210465/0.849722초,
저장 이미지 캡처1.072350/1.698016초다. 회수 config의0.2초 CSV·1.0초 온도 요청·
1.0초 이미지 최소 저장 간격과 대조했다. 화면 표시나 물리 디스크 flush 간격은 미계측이다.

온도 fact9,689개 중 유효9,297·무효392이며, 전부HTTP200/success다.
18:27:59–18:34:30의 연속 무효 원문6553.4는 invalid_sentinel로 보존돼 있고
전후 유효 온도 간격은392.961080초다. CSV에서 참조한386관측/1,616행 전부는
온도 빈값·quality invalid·origin none을 유지했다. 물리 원인과 학습 적합성은 미확정이다.
CSV의31,932반복 참조를 신규 측정으로 세지 않으며, CSV 미참조151관측도 fact에 남아 있다.
학습 준비에는 고유 관측 키·유효성 마스크·시간/생산 구간을 사용해야 하고 임의 보간은
측정값으로 취급하지 않는다. 이 분석으로 새 운영 시간 기준이나 PASS를 만들지 않는다.

분석/Ruff F/E9/별도 정수 시각 재계산/무효 CSV 전수 대조는 모두exit0이다.
입력 전후 SHA를 같은 읽기 잠금에서 확인했고 별도 계산은0.002ms 허용 오차 내 일치했다.
상태 키 post120CsvRunningRecordIntervalsVerified20261020, 이전 턴 VERIFIED_WAIT,
이번 턴 PROGRESS다. 서버·제품·설정·등록 롤백 기준 변경은 없고 목표active/출시HOLD다.

### 5.212 기존 CSV를 유지하며 격리 초기 시작10회 입력 준비

exec42917의 driver49352/생성1792499046.6974635와 자식5개가 실제 실행 중임을 확인했다.
관찰 만료를 종료로 취급하거나 소비기를 재시작하지 않았다. 앞선 목표 턴과 이번 턴은PROGRESS다.

계획R2와 기존 시작 증거를 대조했다. 현장3회는 외부launcher 시계가 없고,
Sandbox의240a3회는 일반·재시작·대량 데이터 조건이 달라 초기10회를 완료하지 않는다.
START10_20261020_6f83a2c1에 동일 후보의 초기10회 측정 묶음을 준비했다.
기존installer/Python213,540,949바이트는 읽기 전용 재사용하고 새 입력57,718바이트를 추가했다.
799입력 SHA를 고정하고 도구/무결성 모듈은240a Git 바이트와 일치시켰다.
외부 통신 차단·새AppData/합성 데이터·기존30000ms 두 시계·9milestone/9progress/raf 계약을 유지한다.
기존 도구의taskkill은 Sandbox 합성 앱 정리 전용이며 정상 저장/종료PASS로 계산하지 않는다.

Python AST/Ruff F·E9, PowerShell4파일 구문 검사,799입력 재검산은exit0이다.
개발PC 직접 실행은 예상exit1로 거부됐고, 기존CSV 미완료 시 새Sandbox 시작gate의 거부도 확인했다.
실제Sandbox 생성·10회 측정은 아직 하지 않았다. 소유Sandbox만 종료하는host 실행기와 결과 검토를
준비했으며 현재CSV 완료 검산 뒤 실행한다. 서버·설정·롤백 기준 변경은 없다.

### 5.213 과거 탭 비교와 현재 후보의 동일성 확인

앞선 상태 확인 턴은 exec42917의 실제 live handle을 확인한 VERIFIED_WAIT다.
이번 턴은 기존 1/3탭 증거의 재사용 범위를 실제 소스와 대조한 PROGRESS다.
PDCA_BROWSER_TABS_20261013_9df08dc7의 backend Python54파일은 보존 목록 SHA와
일치했으나 현재240a Git과 비교하면5개 동일/43개 개행 차이/6개 내용 변경이다.
변경에는 SPOT 수집·저장·이미지fact·앱 경로가 포함되므로 과거 비교를 현재 후보의
다중 화면 완료 근거로 대체하지 않는다. 전체frontend/runtime 동일성을 주장하지 않는다.

기존1/3탭의 예정 표본58개와 준비·마지막4개, 총62개 화면 상태를 대조했다.
각 조건은 한 창이고 마지막탭만visible·나머지hidden·최소화없음이다.
과거계획HTTP477/503건과 별도 browser의layout404 2/6건은 함께 보존한다.
132입력 전후SHA와 source 비교/원시화면 검토/Ruff F·E9는exit0이다.
GATE_REVIEW_20261020_240a/multitab-coverage.json/.md에 근거와 후속 계약을 연결했다.
기존CSV 실행을 유지하고, 완료 검산→START10→현재후보1/3탭 비교 순서로 진행한다.
실제 후속 탭 시험·새 성능 판정·서버 변경은 없고 전체 목표active/출시HOLD다.

### 5.214 현재 후보용 브라우저 관찰 구성요소 확인

앞선 턴은 탭 비교의 소스 동일성 확인을 완료한PROGRESS다. 이번 턴은
TAB20_20261020_2d30f468/input/browser.cjs를 작성·검사한PROGRESS다.
기존1/3탭 원시 화면62개에 새상태검사를 적용하고, 탭수·창ID·최소화·전면/배경·순번이
잘못된6개 사례를 거부했다. Node구문0·검사기전체0·개발PC실행예상거부1을 확인했다.
web-vitals원문SHA를 두과거실행과 대조해 재사용했고 새입력은15,624바이트다.

요청시작ID/완료/실패/미완료, 실제이미지load/error와브라우저시각, LCP/CLS 및
visibility를 원시기록으로 남기는 구성이다. 기록종료0을 운영PASS로 해석하지 않는다.
아직 실제브라우저·Sandbox·후보 측정은 실행하지 않았다. 게스트수집·호스트종료제어·
입력명세·독립결과검산은 남아 있으며 준비완료로 표시하지 않는다.
기존exec42917은 live handle을 다시 확인해 유지했다. 완료후CSV검산→START10순서를
유지하고 현재후보탭비교를 준비한다. 서버·제품변경없음, 목표active/출시HOLD다.

### 5.215 현재 후보 탭 비교의 수집·정리·검산 코드 준비

앞선 상태 답변 턴은 exec42917의 실제 live handle을 확인한 VERIFIED_WAIT다.
이번 턴은 TAB20 게스트 수집기·입력 봉인 도구·호스트 실행기·독립 검산 코드를
작성한 PROGRESS다. START10의 준비/설치 payload 함수 5개와 기존 fixture·HTTP
수집기는 바이트/함수 출처를 연결해 재사용했다. 기존 브라우저 probe는 변경하지 않았다.

14개 오프라인 검사와 Ruff F/E9·Python 구문·PowerShell entry 구문 검사가 exit0이다.
실제 과거 화면 62개를 대조하고 요청 중복·미완료 누락·URL 혼동·화면 숨김·이미지
다른 서비스 ID·파일 변조를 거부했다. 개발 PC의 게스트/entry 실행과 선행 작업
미완료 상태의 호스트 실행은 예상 exit1이다. 이것을 실제 Sandbox 성공으로 세지 않는다.
첫 검사에서는 과거 원시 자료의 run 하위 경로를 빠뜨려 62개 대조가 실패(exit1)했으며,
실제 경로로 수정한 뒤 전체 검사는 exit0(f10c6b)이다. 실패 기록도 보존한다.

22:36:39에 CSV driver49352/생성1792499046.6974635와 자식5개의 실제 실행을 확인했다.
frozen 소비기8348의 누적 CPU는4,279.046875초로 증가했다. 재시작하지 않았다.
TAB20의 입력 manifest 봉인·전체 runtime 재검산·실제 모의 페이지/후보1·3탭 시험은
아직 실행 전이다. 대량 입력 재검산도 기존 CSV 완료 뒤 수행하도록 제한했다.
새 2.35GB 입력은 기존 파일을 읽기 전용으로 재사용하며 새 전체 백업은 없다.
기존 CSV 완료 검산→START10→TAB20 봉인·실행 순서를 유지한다.
서버·제품·설정·등록 롤백 기준을 변경하지 않았고 목표active/출시HOLD다.

### 5.216 탭 비교와 R2 측정 계약의 누락 보완

이전 턴은 실행기·검산 코드 작성의PROGRESS다. 이번 턴은 계획R2와 대조해 빠진
HTTP 첫/마지막·p95/p99·연속 초과 요약과guest 디스크 계측을 보완한PROGRESS다.
전체 시도와 본 관찰 구간을 분리해 첫 실패/최대값을 숨기지 않는다. 디스크 정보가
없거나 집합이 바뀌고 카운터가 초기화된 경우를 정상 측정으로 처리하지 않는다.

아직 manifest로 봉인하지 않은TAB20의3파일만 수정했다. 이전검사에 결합된 바이트는
source-r1과 provenance.json에 대조·보존했으며 이전 결과를 다시 쓰지 않았다.
package-checks-r2.json의18검사는exit0(13996c), 최종변경파일Ruff F/E9도exit0이다.
기존62개화면/거부검사와 새분위수·첫실패·연속초과·디스크정상/계측불가/초기화/집합변경을
확인했다. 실제VM디스크성능·앱실행·물리표시는 아직 측정하지 않았다.
exec42917은 같은live handle을 확인해 유지했다. CSV완료검산→START10→TAB20 봉인·
실행순서는 유지하며 서버·설정·롤백 변경 없이 전체목표active/출시HOLD다.

### 5.217 120분 세대 CSV 완료와 초기 시작10회 실측 완료

exec42917은22:48:28 KST에 종료0·강제정리0·잔류0으로 완료됐다.
변경하지 않은 완료 검산기를 실제 실행해 전체 출력·입력 결합·해시·정리 결과를 확인했고
exit0(d1755c)이다. 해당CSV41,487행·sequence1..41487, 참조41,470행의 원장 연결100%,
관측fact713,135행과 image fact4,586,586행의 최종 개수/SHA가 일치한다.
이는 닫힌 대상CSV·fact 내용 검사이며 전체 이력/물리 샘플/학습 적합성의PASS가 아니다.

START10 최초 실행은 ExistingLogin 미준비0x80070520으로 앱 실행 전 중단됐다.
정상 Sandbox stop의 빈 stdout을 JSON으로 읽어 정리false로 남긴 도구 오류도 확인했다.
실제stop0과 후속 빈목록을 구분해 보존했다. R2는 준비 확인·빈stop 처리를 보완했고,
연결 창을 연 뒤 guest가 시작됐지만 첫 회차의 로그 이벤트0/90초TIMEOUT으로 종료1이었다.
모의 장비 응답은 있었으나 시작 성능은NOT_MEASURED다. Sandbox와 연결 창은 정상 정리됐다.

정확한240a main.js는 app.getPath('userData')에 로그를 쓰며 setPath/setName이 없다.
R3는 실제native 로그와 환경변수/fallback 경로를 보존하고 매회 실제Electron 프로필
부재·이동 경계를 확인했다. 제품·기존측정helper 변경 없이799입력 재검산·Ruff·로그
보존/비guest이동거부/host실행거부 검사가exit0(5dfd98)이다.

exec10195는23:06:55 KST 종료0이다. 초기10회 전부 기능/성능PASS이며 앱내부 최대
2,205.9ms, launcher 최대4,878.1ms로 기존30,000ms 계약을 충족했다.
9milestone·9progress·raf,10개 서로 다른 시작session, 각회차잔류0, 설치payload1,867개
전후 일치와118개 출력 결합을 실제host검산했다. native로그는 존재하고 이전환경경로는
없음이 후속실측에서 확인됐다. 소유Sandbox 소멸·viewer종료0도 확인했다.
과거실패2개는 보존하며 이초기시험의taskkill 정리를 정상저장/종료시험으로 계산하지 않는다.
OS cold-cache나현장3회·다중탭·전체R2/출시PASS로 확대하지 않는다.
다음은TAB20 host의준비/stop 처리와START10R3 선행근거를 연결한뒤봉인·실측이다.

### 5.218 탭 시험 실행기 보완과 실제 브라우저 예비 시험

직전 사용자 상태 답변은 결과 재확인으로 NO_PROGRESS다. 이번 턴은 준비된 탭 시험을
실행하고 확인된 실행 도구 오류를 보완한 PROGRESS다. START10R3 완료 SHA와 로그인
준비·연결 창·빈 stop 출력 처리를 TAB20에 적용했다. 이전 검사에 결합된 파일은
source-r2와 출처 목록에 보존했다. 오프라인21검사·Ruff는 exit0(8cc697)이다.

첫 봉인 시도는 Chromium 구성 manifest까지 제외해 설치/VM 실행 전에 실패했다.
자체 input/manifest만 제외하도록 수정 후1,230파일 봉인은 exit0(ce1f3b)이다.
별도 목록 검산의 첫 접미사 검색 오류도 보존했고 정확한 파일명 대조는 exit0(196ead)다.
TAB20 실제 exec24530은 게스트 입력 검산 후 Python exit1로 종료했다.
앱/브라우저 시험 결과는 없고, 소유 Sandbox 소멸·viewer0·정리 오류 없음은 확인했다.

동일 묶음 Python으로 startup_support import 실패를 재현했다(9c09e5).
._pth가 현재 스크립트 경로를 포함하지 않는 원인이며 R2의 명시적 입력 경로와 실제
모듈 출처 기록으로 보완했다. 최초 실패의 누락된 stderr를 추정한 원문으로 채우지 않는다.
새 TAB20R2 폴더의 실제 묶음 Python 모듈 대조·21검사·Ruff·PS 구문은 exit0(300cbb),
PS5.1 양쪽 출력/실제 종료 코드 보존 검사와1,230입력 봉인은 exit0(694e8f)다.

exec52423은 새 소유 Sandbox에서 실행을 시작했다. 게스트 입력 검산과 네 모듈 출처가
일치했고 실제 Chromium3탭 이미지 이벤트·상태/정상종료 예비 시험이23:23:22 KST에
통과했다. 이는 실제 후보1·3탭 성능 비교 완료가 아니며 후속 관찰·독립 검산을 이어간다.
기존120분/CSV/초기10회는 재실행하지 않았고 서버·설정·롤백 변경 없이 목표active/출시HOLD다.

### 5.219 탭 관찰의 blob 표시와 종료 증거 회수 수정

TAB20R2의 실제 후보 준비는 이미지 이벤트 대기60초 초과로 종료1(ccd0c2)이다.
HTTP 이미지176건은200이고 blob 요청도 존재하지만, 관찰기가 URL만 필터링하여 실제
카메라 요소의 blob 로드를 기록하지 못했다. 정확한240a CameraWidget의 img.camera-image
클래스와 src 바인딩을 읽어 대조했다. 백엔드 정상종료0·소유VM소멸·viewer0은 확인했으며
이를 이미지 표시/성능 비교 PASS로 바꾸지 않았다.

새 R3의 실제 카메라 요소 관찰·실패 화면 보존·blob 예비 시험을 보완했다.
62개 기존 상태·6개 거부·Node구문/host거부, Python21검사·Ruff·봉인은 exit0이다
(9662af/f95769). 실제 blob3탭 예비 시험과 후보1탭 준비는 성공했다.
이후 R2 종료자료 검산에서 실제 receipt 회수 누락을 발견했다(911586 exit1).
정확한후보 app.py는 APP_DATA_DIR/shutdown_evidence를 사용하지만 도구는 별도 빈폴더를
회수하고 있었다. R3는 이 결함을 확인한 뒤 browser 정상종료 요청으로 시험을 중단했다.
12자원표본·51요청 뒤 비교 INCOMPLETE/전체exit1을 보존했다. 브라우저/백엔드 실제0,
정리오류0·VM소멸·viewer0은 확인했고 강제종료는 하지 않았다.

새 TAB20R4는 native backend 종료 후 실제 격리 프로필의 receipt를 복사·SHA 대조한다.
제품/설정/측정기준 변경은 없고 이전 봉인 묶음은 보존했다. 수정본21검사·Ruff·1,230입력
봉인은 exit0(daae2d)이다. exec16505와 실제 PID46544/생성1792506708.1145253의
실행을 확인했고, 새VM의 입력 검산이23:32:21 KST에 완료됐다.
1·3탭 관찰 완료와 정상저장·독립검산은 아직 진행 중이며 목표active/출시HOLD를 유지한다.

### 5.220 120분 완료 범위 문서화와 Sandbox 예기치 않은 종료

직전 턴은 실행도구 보완·실측 시작의PROGRESS다. 이번 턴은 완료된120분·닫힌CSV·이미지
원문을 다시 읽어 운영기준 보고서의 후속완료 절에 연결했다. 과거 진행기록과 이미지검산의
당시CSV PENDING을 재작성하지 않고 후속완료증거를 명시했다. 120분 관찰과161분32초
전체 실행의 저장 검산 범위, 온도392무효관측·반복참조와 학습적합성 미평가를 구분했다.

TAB20R4 exec16505는23:35:14 KST에 native CLI2151088390(0x80370106)으로 종료했다.
원문은 VM/컨테이너의 예기치 않은 종료를 보고한다. 준비구간 자원24개(0..23)만 있고
guest 완료·backend 정상종료 영수증이 없어 비교 INCOMPLETE다. 소유 Sandbox는 정리했고
viewer0·정리오류0을 확인했다. 마지막guest 메모리는29% 사용/약6.10GB available이며,
이 표본만으로 host VM 종료 원인을 확정하지 않는다. Hyper-V Admin 로그는 현재 권한으로
접근 거부됐고 해당2분 System 조회에는 이벤트가 없었다. 원인UNCONFIRMED를 유지한다.

실제종료와정리를 확인한 후 새TAB20R5에서 한 번의 동일조건 재현을 시작했다.
이는 관찰timeout에 따른 중복실행이 아니다. helper 바이트·1,230개 입력manifest SHA
7d8ce5a007f3a410bc07492185bfc2a908f3afd8d8803232cfec31ceee110ea0는 R4와 동일하다.
새결과경로만다르며 과거실패를수정하지않았다. exec66941, PID9708/생성1792507269.2720191의
실행을확인했다. 사용자에게 당시Sandbox창을닫았는지확인질문을남겼으며답변은대기중이다.
운영서버나120분결과에변경없고 후속실측·정리·독립검산은미완료, 목표active/출시HOLD다.

### 5.221 동일 입력 재현도 Sandbox 종료로 미완료

TAB20R5 exec66941은23:44:43 KST에 R4와 같은 native CLI2151088390
(0x80370106)으로 종료했다. 실제 host exit1(3d2f8a), 소유VM 정리·viewer0·정리오류0을
확인했다. 준비구간24표본만 있고 guest 완료·backend 정상종료 기록이 없으므로
1·3탭 비교는 INCOMPLETE이며 후보 성능 불합격이나 저장 무손실로 판정하지 않는다.
마지막 guest 메모리는28.6% 사용/약6.13GB available이다.

R4와R5 종료 인접 시간창에서 Application/Windows Error Reporting의
ContainerCrashDump 이벤트를 각각3개 확인·보존했다. 개수는 중복 보고 단계를 포함하며
독립 충돌3회라는 뜻이 아니다. 이벤트와 Sandbox UUID의 직접 연결은 아직 없고 원인도
UNCONFIRMED다. Hyper-V Admin과 해당 WER 보고서 경로는 현재 권한으로 접근 거부됐으며
관련 dump 경로에는 파일이 없었다. 권한을 변경하지 않았고 동일조건R6를 시작하지 않았다.

[종료 검산](C:/Users/user/Desktop/SmartFactory/TAB20R5_20261020_2d30f468/failure-review.json)과
[시간창별 이벤트](C:/Users/user/Desktop/SmartFactory/TAB20R5_20261020_2d30f468/container-crash-events.json)를
연결했다. 현재 실행 목록은 비어 있고 원시 실패·봉인 입력·과거 진행 기록은 보존한다.
완료된 서버120분·닫힌CSV/이미지·시작10회 결과는 유지한다. 서버·제품 코드·설정은
변경하지 않았으며 목표active/출시HOLD다. 다음은 해당 VM의 종료 원인에 필요한
제한된 진단 자료 확인이며, 완료된120분 시험을 반복하지 않는다.

### 5.222 VM 오류 서명 대조와 관리자 읽기 진단 준비

직전 턴은 실제R5종료와 원시 이벤트를 확보·기록한PROGRESS다. 이번 턴은 현재
Sandbox 목록이 비어 있고 Codex가 일반 권한임을 확인했다. 두 시간창의 WER 세 이벤트는
각각 한 ReportId로 묶인다. 두 보고서 모두P1=0x3b, P2=0xc0000005,
P3=0xfffff80533753152이며 P4만 다르다. 오류 주소 일치는 확인했지만 Hyper-V VM
식별과 faulting module은 미확정이다.

개발 PC는 DisplayVersion26H2/build26300.9711, Sandbox0.8.107.0이다.
[Microsoft 저장소의 사용자 보고131](https://github.com/microsoft/Windows-Sandbox/issues/131)에는
같은 빌드·오류 코드 사례와10월20일 작성자의26300.9807 개선 보고가 있다.
[보고132](https://github.com/microsoft/Windows-Sandbox/issues/132)의 다른 사용자는
Release Preview26300.9807에서 해결됐다고 적었다. 이는 개별 사용자 관찰이며
Microsoft의 이 PC 원인 확인이나 정식 업데이트 적용 근거로 확대하지 않는다.
Windows 업데이트·기능 토글·드라이버/보안 설정은 변경하지 않았다.

`VMLOG_20261020_2d30f468`의 고정 범위 수집기·SHA 잠금 실행기·README를 준비했다.
native PS5.1 구문/범위 확인과 실행기 dry-run은exit0, 실제 일반 권한 수집은
예상대로exit1이며 출력 폴더 생성0이다(09f856/c6c507). retained handle 방식의
별도 무해한 프로세스 exit23도 실제로 읽었다. 이는 관리자 수집 성공 증거가 아니다.
[준비·해시 기록](C:/Users/user/Desktop/SmartFactory/VMLOG_20261020_2d30f468/preparation-review.json).

사용자에게 Windows 관리자 확인 창에 응답할 수 있는지 질문했으며 아직 답변 대기다.
명령 복사는 필요 없고 준비 응답 후 Codex가 실행기를 시작한다. 실제 수집 미실행,
후속 탭 비교 미완료, 서버·후보·완료된120분 증거 변경 없음, 전체 목표active/출시HOLD다.

### 5.223 사용자 준비 응답 대기와 blocked 감사

직전 턴은 제한된 관리자 읽기 묶음 준비·검사의PROGRESS다. 이번 턴의 실제 확인
(27ef85)에서는 일치하는 실행 프로세스·Sandbox·관리자 실행 결과·수집 결과가 모두 없었다.
이는 실행 중 프로세스를 기다리는 VERIFIED_WAIT가 아니며 이번 턴은 NO_PROGRESS다.
준비 응답은 아직 없고 수집기/실행기/준비기록 SHA는 그대로다.

R5 VM 종료 진단→관리자 진단 준비→이번 재확인의 세 연속 목표 턴에서 같은 환경/권한
의존성을 확인했다. R1 과거 인과·R3 물리 장비·R4/R5 과거 처리 결정과 R2 성능 요구는
기존 미확정이며, R6/Act는 이 미완료를 통과로 변경할 수 없다. 추가 독립 실행 없이
요구를 낮추거나 같은 실패 시험을 반복하는 경로는 선택하지 않는다.
[감사 기록](C:/Users/user/Desktop/SmartFactory/VMLOG_20261020_2d30f468/blocked-audit.json)에
따라 goal 도구의 실제 상태를blocked로 변경했다. 전체 완료나 사용자 요청 pause가 아니다.
사용자 준비 응답 후 해시가 고정된 관리자 읽기를 한 번 실행하여 실제 로그로 원인을
좁히는 지점에서 재개한다. 완료된120분 결과와 출시HOLD·기존 롤백 기준은 유지한다.

### 5.224 승인된 관리자 진단 완료와 Sandbox 게스트 오류 확인

사용자의 준비 응답으로 목표를 재개했다. 고정 수집기·실행기·준비 기록 SHA를 확인한 뒤
관리자 수집을 한 번 실행했고 실제 LAUNCH_EXIT=0이다(68be3d). 새 결과 3파일의 크기·SHA와
native 결과를 확인했다(cd033f). 별도 대조 30항목/22개 입력 핀이 통과했다(4ad384).
[진단 검토](C:/Users/user/Desktop/SmartFactory/VMLOG_20261020_2d30f468/admin-result-review.md).

R4/R5 인접 시각의 Hyper-V 18590은 모두 0x3B/0xC0000005이며 오류 주소도 같다.
각 오류는 시험 명령의 0x80370106 종료보다1.171612/1.192720초 앞선다. Hyper-V VM·덤프 경로·
WER 보고서 ID·이름 있는 Bugcheck 매개변수의 대응은 검증했다. Sandbox CLI ID와 VM ID의
직접 연결은 확보하지 못해 해당 시험과의 연결은 시간적 추론으로 구분한다. 덤프 생성 기록은
있지만 지정된 dmp/vmrs 네 경로는 현재 없다. faulting module·근본 원인은 UNCONFIRMED다.
뒤따른 게스트 reset/중지 오류를 최초 원인으로 바꾸지 않는다.

현재 개발 PC는26300.9711/Sandbox0.8.107.0이며 현재 원본 온라인 업데이트 조회는 성공/제공0개다.
26300.9807/KB5127936은 공식 Release Preview이고 사용자 개선 보고는 있지만 조회한 공식
릴리스 노트의 Sandbox 수정 명시는 없다. 개발 PC의 OS·업데이트 채널·보안 설정은 변경하지 않았다.
사용자는 대체 개발·시험 PC가 없다고 답했다. 환경 변경은 진단 승인과 구분해 결정해야 한다.

이번 턴은 실제 증거를 확보한 PROGRESS/goal active다. 기존 blocked 감사는 과거 상태로 보존하며
재개 뒤 같은 의존성이 반복되면 새로 집계한다. 1·3탭은 INCOMPLETE, 출시HOLD·승격false 유지.
완료된120분/닫힌CSV·이미지/시작10회는 유지하고 반복하지 않았다. 서버·제품 코드·HEAD·index는
변경하지 않았다. 현재 실행 없음이며 동일 R6를 재실행하거나 VM 격리 조건을 제거하지 않는다.

### 5.225 시험 환경 대안 확인과 재개 후 두 번째 차단 확인

직전 턴은 관리자 진단을 실행·대조한 PROGRESS다. 이번 턴은 읽기 전용 재확인과 경로 검토이며
남은 성능 시험을 완료하거나 환경 의존성을 해소하지 못해 NO_PROGRESS로 기록한다.
현재 wsb 목록0, 해당 TAB/VMLOG 작업 프로세스0·조회 불가0을 확인했다(4a772c/87d6f5).
실제 실행을 기다리는 VERIFIED_WAIT가 아니다. Hyper-V vmms/vmcompute와 관리 모듈은 있지만,
필터 없는 Msvm_ComputerSystem 조회에는 호스트만 있고 등록 게스트는 없다(86e1c5).

Downloads/Desktop SmartFactory 최상위의 ISO/VHD/VHDX는 발견되지 않았다. ProgramData의
Virtual Hard Disks는 접근 거부여서 기존 이미지 부재로 단정하지 않는다. 최초 조회exit1을
보존하고 경로별 오류를 기록하는 재확인은exit0이었다(e367df/ddda44). 권한을 바꾸지 않았다.
[환경 대안 검토](C:/Users/user/Desktop/SmartFactory/VMLOG_20261020_2d30f468/environment-options-review.json).

대체 PC가 없다는 사용자 응답에 따라 같은 PC의 독립 Windows VM 준비/정식 수정 대기/
미리보기 업데이트 검토 중 방향을 질문했다. 선택·환경 설치·OS 변경·재부팅은 아직 미실행이다.
기존 VM guard를 없애 호스트 시험으로 대체하지 않고 완료된120분·CSV/이미지·시작10회는 보존한다.
재개 후 동일 환경 의존성을 확인한 두 번째 목표 턴이며 active/출시HOLD를 유지한다.
같은 차단이 세 번째 연속 재현되고 추가 안전한 진행이 없으면 goal blocked로 기록한다.

### 5.226 사용자 선택에 따른 독립 Windows VM 준비

사용자는 같은 개발 PC의 별도 Windows VM 준비를 선택했다. 이는 실제 VM 생성/OS 설치
승인이 아닌 준비 방향 선택이다. `VM21_20261021_83be8a5a`에 공식 평가판 매체와 새 VM
구성 도우미를 준비하고 있으며 이번 턴은 PROGRESS/goal active다. 이전 미응답/차단 기록은
당시 상태로 보존한다. 서버·호스트 OS/보안/네트워크·후보 설치본은 변경하지 않았다.

호스트는12논리CPU/약31.84GiB RAM이며 준비 시 여유 RAM 약12.34GiB, C: 여유 약697GiB를
확인했다(d9ca53). Hyper-V 서비스와 모듈은 있지만 일반 권한 Get-VMSwitch는 접근 거부다.
CIM 조회에는 등록 게스트가 없고 현재 Sandbox 목록도 비어 있다. 관리자 전체 목록 확인은
실제 적용 전 다시 수행한다. Windows 이미지나 네트워크 연결의 준비 완료를 추정하지 않는다.

공식 90일 평가판은8,225,329,152바이트/공개SHA256
`bc3f24086ebadc94489066b5ad78089e2cf5c3491e90e790bb81a2b199c10e38`다.
최초 전송 방식 변경과 R2의 실제exit1/ReadTimeoutError를 보존했다(117c8f/1cb340).
R3는4MiB 범위·제한된 재시도·검산한 완료 구간 기록을 사용하며 세션87292에서 다운로드 중이다.
부분 파일의 전체 예약 길이는 완료 바이트 수가 아니다. 최종 전체 해시 일치 전에는 매체를 사용하지 않는다.

정지 상태의 Generation2/4vCPU/8GiB/새 동적64GiB VHDX/secure boot/vTPM/가상NIC0개
구성 도우미와 SHA잠금 실행기를 준비했다. native PS5.1 구문·설치된 명령 매개변수·경로 경계
8검사exit0(7279d4), 실제 일반 권한 Apply는 예상exit1/ADMIN_REQUIRED_NO_MUTATION이며
VM/시도/결과 생성0(3e71fa)이다. Python AST와 기존 venv Ruff F/E9는 통과했다.
전역 Python의 Ruff 부재 오류(b15757)는 보존하며 실제 VM 생성 검증으로 확대하지 않는다.

[검토 가능한 변경 범위](C:/Users/user/Desktop/SmartFactory/VM21_20261021_83be8a5a/review.md)에
등록·Microsoft 계정·평가판 인증과 시험 전 네트워크 차단을 구분했다. 계정 준비 응답은 대기 중이다.
새 VM 실제 생성·설치·안정성·남은1·3탭 비교는 미실행이며 기존120분·CSV/이미지·시작10회
증거를 반복하거나 재판정하지 않는다. 출시HOLD/승격false를 유지한다.

이후 R3 전송은 실제 exit 0/1,962구간/공식 전체 SHA 일치로 완료됐다(09db0b). 마지막 4MiB의
별도 curl 확인도 206/길이 일치/exit 0이었지만 기존 R3가 정상 완료되어 조각 병합이나 강제 중단은
하지 않았다(99481a). SHA 잠금 실행기의 실제 읽기 전용 점검은 exit 0이고 Apply=false,
새 VM 폴더/시도 기록은 0이다(a23f90). 준비 시점 여유 RAM 14,744,170,496바이트와
C: 731,247,558,656바이트를 확인했으며 관리자 Hyper-V 전체 목록·실제 생성은 여전히 미실행이다.

7-Zip의 기존 실행 연결은 실제 프로그램 부재로 exit 4294967295였고(d224fa/3296e2), 공식 해시로
고정한 작업 폴더 내 pycdlib 1.22.0으로 UEFI 부팅 파일·boot.wim·install.wim·setup.exe 존재를
읽기 확인했다(54695a). 전역 라이브러리 설치나 ISO 마운트/실행은 하지 않았다. 기존 시험 입력
1,230파일/3,115,181,865바이트 전체 크기·SHA 대조도 오류 0/exit 0이다(1b97f1).
전체 ISO 확보 후 이 작업의 실패/중복 전송 임시 3파일만 정확한 경로·크기·해시를 기록하고 삭제했다(db522b).
기존 검증 증거·실패 기록·원본 묶음은 보존했다.

사용자는 초기 등록·로그인을 직접 할 수 있다고 답했다. 평가판의 90일 기간과 만료 시 시간당 VM 종료를
공식 안내에 따라 설명했고, 호스트 Windows/운영 서버의 라이선스 기간과 구분했다.
실제 새 VM 생성은 준비 방향 선택과 분리해 검토 가능한 구성을 제시한 뒤 승인받는다.

### 5.227 승인된 정지·오프라인 VM 생성과 최신 계획 상태 대조

사용자는 VM 생성과 Windows 관리자 확인을 승인했다(`call_4f83e543c1aa4d85ba9481eba3c2b63c`).
기존 실행기·도우미·준비 기록 해시와 대상/시도 부재를 확인하고 승인 범위를 새 기록으로 보존했다.
고정 실행기를 한 번 호출했으며 관리자 프로세스59268과 실제 실행기 모두 exit0이다(4887f9).
VM은 `SFL-QA-20261021-83be8a5a`, ID `b7ee8fcd-dd3d-46b5-901a-f465f9e06f6b`다.

관리자 도우미의 실제 Get-VM/Memory/Processor/Firmware/Security/Disk/DVD/VHD/Network 대조가
Generation2·4vCPU·고정8GiB·동적64GiB·secure boot/vTPM·NIC0·Off 조건을 충족했다.
새 VHDX의 초기 파일 크기는4,194,304바이트이며64GiB를 즉시 점유한 것이 아니다.
별도 결과 대조는 승인/시도/ID/결과/실제 종료 코드·해시·파일 크기·프로세스 종료를 확인했다(exit0,9e86d4).
일반 권한 CIM 목록에는 호스트만 나타났으므로 이 조회로 새 VM 부재를 추정하지 않았다.
[생성 결과와 증거](C:/Users/user/Desktop/SmartFactory/VM21_20261021_83be8a5a/creation-review.md).

VM 시작·Windows 설치·등록/로그인·네트워크 연결은 이번 승인 범위 밖이며 수행하지 않았다.
서버 접근·제품 코드/설정·전체 백업·운영 기준 갱신도 없다. 준비 시점 기록은 당시 상태로 보존하고
현재 상태는 새 생성 검토와 canonical stage로 구분했다. 이번 턴은 PROGRESS/goal active다.

계획의 현재 상태가10월20일13:31에 머물러 있어 OP120 review·닫힌 세대 CSV/이미지·START10 검증
네 원본의 SHA를 다시 확인했다(fb820c). 120분의 수집/세대결합 PASS, 해당 닫힌 세대41,487행/
8,912이미지, 새 프로필 시작10회를 완료된 범위로 반영했다. 이는 같은 시험 재실행이나
전체 역사 자료·장치 샘플 완전성·학습 적합성 PASS가 아니다. 과거 실패와 R1~R6 미완료,
물리NOT_TESTED·출시HOLD·승격false는 그대로 유지한다. 다음은 이 VM의 설치 절차 준비와 승인이다.

### 5.228 새 VM의 설치 시작 경로 준비와 화면 도구 제한

직전 턴은 승인된 VM 생성과 실제 종료 검산을 완료한 PROGRESS다. 이번 턴은 생성 증거와 초기
VHDX를 다시 읽고 구체적 설치 시작 도우미·절차를 준비한 PROGRESS이며 실제 설치/부팅은 하지 않았다.
기존 VM 생성 승인과 별개로 새 시작 승인을 확인한다. 무실행 계획만의 상태 재진술이 아니라
실행 가능한 한정 도우미와 native 검증 결과를 새로 확보했다.

computer-use 지침을 읽고 공식 node/sky 진입을 시도했으나 `failed to write kernel assets:
지정된 경로를 찾을 수 없습니다. (os error 3)`가 발생했다. node 초기화 후 재시도도 동일하며
sky 함수나 화면 입력은 실행되지 않았다. 대체 입력 주입 방식이나 인증/보안 UI 자동화를 사용하지 않는다.
VMConnect는 설치된 공식 실행 파일로 확인했고 Microsoft의 Start-VM/VMConnect 절차와
평가판 등록/계정 조건을 재확인했다. 현재는 사용자가 설치 화면을 선택할 수 있어야 실제 시작한다.

새 도우미는 기존 생성 ID·이름·CPU/RAM·TPM/secure boot·Off·NIC0·단일 초기 VHDX·공식 ISO를
확인하고 한 번만 VMConnect/Start-VM을 실행한다. 기본 호출은 읽기 검사다. VM Running과
Windows 설치/화면 성공은 구분하고 설치·네트워크·보안/계정 처리는 자동 실행하지 않는다.
시작 요청 후 오류가 나면 결과/현재 상태를 남기며 자동 재시작·강제 종료하지 않는다.
[구체적인 설치 시작 범위](C:/Users/user/Desktop/SmartFactory/VM21_20261021_83be8a5a/setup-review.md).

native PS5.1 x64 구문2파일·설치된 명령 매개변수·경로 허용3/거부3 검사는exit0(3684d6)이다.
실제 SHA잠금 실행기의 기본 읽기 검사는exit0/Apply=false(9906a4), 일반 권한의 실제 Apply는
예상exit1/ADMIN_REQUIRED_NO_MUTATION이며 시작기록0·초기 VHDX 해시 동일(fbcbb3)이다.
이는 관리자 부팅이나 설치 성공을 대신하지 않는다. 계획 도우미 프로세스는 실제 종료됐으며
실행 중 작업을 기다리는 VERIFIED_WAIT가 아니다. 사용자에게 설치 시작과 화면 조작 가능 여부를
확인한다. 기존120분·CSV/이미지·시작10회는 반복하지 않고 R1~R6 미완료·HOLD를 보존한다.

### 5.229 설치 시작 승인 대기와 화면 도구 경로 확인

직전 턴은 설치 시작 도우미의 실제 준비·검산을 완료한 PROGRESS다. 이번 턴은 동일 설치 승인/
화면 조작 준비 응답이 없는 상태를 재확인했으며 실제 환경 의존성을 해소하지 못한 NO_PROGRESS다.
준비 검토 SHA는 동일하고 시작 시도/결과 파일과 해당 실행 프로세스는 없다(eb32e3).
기본 Temp·Node 실행 파일/패키지는 존재한다(04ea60). 제한된 최신 앱 로그에서는 실패한
kernel asset 경로를 특정하지 못했고(923849), 현재 node 도구도 동일 초기화 오류를 반환했다.
그 원인은 UNCONFIRMED이며 관련 없는 프로세스나 권한·설정을 변경하지 않았다.

이는 실행 중 진단을 기다리는 VERIFIED_WAIT가 아니다. 준비 시점부터 같은 설치 승인/화면
준비 의존성이 남은 두 번째 목표 턴이다. [대기 감사](C:/Users/user/Desktop/SmartFactory/VM21_20261021_83be8a5a/records/setup-blocker-audit-01.json)를
기록하고 goal active를 유지한다. 같은 질문을 다시 보내거나 VM 부팅·설치·네트워크 연결을 하지 않았다.
세 번째 연속 재확인에서도 동일 차단과 독립 진행 불가가 확인되면 goal blocked로 전환한다.

### 5.230 동일 설치 의존성 세 번째 확인과 실제 blocked 전환

직전 턴과 이번 턴은 NO_PROGRESS다. 같은 설치 승인/화면 조작 준비 의존성이 세 번째 연속
목표 턴에 남았다. 준비 검토와 두 실행기 해시는 그대로이며 시작 시도/결과0·관련 실행 프로세스0을
재확인했다(29f2e2). VM 생성 승인은 정지·오프라인 생성까지이고 새 부팅·설치 응답은 아직 없다.
이는 실제 진행 중 작업의 VERIFIED_WAIT가 아니다.

현재 계획·과거 증거 한계·운영 기준도 읽어 독립 진행 여부를 점검했다(ea4760). 물리 시험 장비,
과거에 저장되지 않은 이벤트/대상과 처리 결정, 운영 수치 요구 및 남은 QA를 새로 확보한 근거는 없다.
이미 끝난120분·닫힌 세대·시작10회 반복이나 격리/승인 조건 삭제로 진행을 대신하지 않는다.
[차단 감사](C:/Users/user/Desktop/SmartFactory/VM21_20261021_83be8a5a/records/setup-blocked-audit.json) 후
goal 도구가 실제 `blocked`를 반환했고 그 결과를 별도 보존했다. 전체 완료나 사용자 pause 요청이 아니다.
기존 설치 시작 승인/화면 준비 응답 지점에서 재개하며 새 질문을 중복 발송하지 않는다.
미서명 정책·후보/롤백 식별·R1~R6 미완료·출시HOLD는 그대로다.

### 5.231 화면 읽기 부분 복구와 VM 재개 도우미 R2 검증

사용자의 앱 재실행 후 최소 runtime·창 목록·화면 읽기는 성공했으나 입력과 활성화는 복구되지 않았다.
이전 시작 도우미는 창이 늦게 생성돼 exit1로 끝났고, 이후 실제 VM 화면에서는 UEFI 부팅 오류를
관찰했다. OS 설치 없이 고정 ID의 빈 VM을 Off로 돌린 결과는exit0/정지 기록SHA
`e07c8c4a7208aae58801a6cd325c4fb8014a67c6b9c62c4265d19e453dc0ad48`이다.
이 부팅/정지 기록과 원래 실패는 보존했다. DVD 부팅 실패 원인은 미확정이다.

이번에는 일반 권한 VMConnect의 접근 거부 창까지 읽었지만 그 창에도 좌표/활성화 오류가 발생했다.
따라서 관리자 창의 권한 수준만으로 입력 실패를 설명하지 않는다. 권한·보안·런타임 바이너리는
변경하지 않았다. 같은 실패 입력이나 앱 재시작을 근거 없이 반복하지 않는다.

독립적으로 확인된 창 생성 대기 결함을 R2로 수정했다. 현재 디스크/정지 증거에 결합하고, 기존
같은 VM 창 하나를 확인해 재사용하며 InputIdle 뒤 창이 생길 때까지 최대15초 기다린다.
native PS5.1 CP949에서 BOM 없는 한글 제목이 잘못 해석됨을 확인해 UTF-8 BOM과 제목 검사를 추가했다.
최종 회귀6개 native exit0(cead0b), SHA잠금 실행기의 기본 읽기/전체ISO 검산 exit0(2899b4),
native 구문3파일 오류0 및 원래8파일/HEAD/index 보존 exit0(f57a4a)을 확인했다.
[최종 검토](C:/Users/user/Desktop/SmartFactory/VM21_20261021_83be8a5a/setup-r2-review.md)의
검산 기록SHA는`83fe1638192c67f18b7b2714135e3dc8495e882252513a1f066671d7ac9faade`다.

이번 턴은 수정과 실제 검증 증거를 확보한 PROGRESS다. R2 Apply·VM 시작·OS 설치·네트워크 연결은
하지 않았다. 일반 권한 읽기 검사를 새로운 관리자 VM 상태 조회로 해석하지 않는다. 마지막 확인된
상태는Off이고 VHDX는 동일하다. 화면 입력/OS 설치/1·3탭 QA는 미완료, goal active·출시HOLD를
유지한다. 완료된120분/닫힌 데이터/시작10회를 다시 실행하지 않았고 운영 서버도 변경하지 않았다.

### 5.232 과거 데이터 사용 방침 검토안과 VM 입력 의존성

VM 화면 읽기에서 Off를 확인했다. 공식 Raise는 VM 창에서 성공했으나 키 입력의 화면 효과는
확인되지 않았고 일반 Explorer에서도 새 관찰 후 활성화 오류가 반복됐다. 입력 복구·Windows 설치를
성공 처리하지 않는다. 호스트 재부팅이 필요하다는 근거는 확보하지 못해 사용자에게 재부팅과
VM Start를 지금 실행하지 않도록 안내했다. 이번 단계에는 VM 시작·설치·서버 접근이 없다.

독립적으로 [과거 자료 사용 검토안](C:/Users/user/Desktop/SmartFactory/HIST_USE_20261021_d582ac91/review-r2.md)을
준비했다. 온도19파일·PLC1항목과 특정 R5 실행의 이미지 자료를 원본 보존 상태에서 향후 학습·검증된
품질 분석 입력으로 사용 보류하는 제안이다. 사용자 결정 전이며 실제 데이터셋/원본을 변경하지 않았다.
거부15회는 개별 이미지15개나 제품15개의 유실을 뜻하지 않는다. 온도 구조 이상33건 역시 전체 유실량이 아니다.
손상 ZIP2개는 확인된 앞부분이 프로그램/라이브러리 자산이므로 공장 학습 자료와 구분해 결정 대상에서 제외했다.

기존19증거와 추가3증거의 해시·길이, 온도 경로/레코드 및 실행 결합을 확인했다. 초기 최종화에서
PowerShell 불리언 표기2곳 오류가 있어 프로세스 exit0을 성공 근거로 채택하지 않았다. 원래 시도를
보존하고 R2에서 두 값의 실제 bool/false 여부와 범위를 검산했다(exit0,5d6a71). 최종 검산SHA는
`e14baed1c56a3d96f8ae6f064ec6523cf234e98e1d17162331ab983899f4dbb7`이다.
원시 자료 전수 재검사·제품 변경이 없어 제품 test/build 및 완료된 현장 시험은 반복하지 않았다.

사용 방침을 승인해도 복구·원인·영향 미확정이나 R4 NOT_PASSED/R5 INCOMPLETE를 해소하지 않는다.
이번 PROGRESS는 구체적인 담당자 검토안 준비이며 UI 실패 재확인을 진전으로 센 것이 아니다.
goal active·출시HOLD·운영 승격 금지와 기존 운영/롤백 기준은 유지한다.

### 5.233 화면 의존성 감사 후 담당자의 과거 자료 사용 보류 승인

직전 검토안 준비 턴은 PROGRESS였으며 다음 재확인은 NO_PROGRESS였다. 실제 VM 화면에서 Off를
확인했고 R2 시도/결과와 관련 실행 프로세스는 없었다(ae6251). VMConnect 창의 존재를 진행 중인
시험으로 세지 않았다. 같은 화면 입력 조건이 네 목표 턴에 걸쳐 남고 독립 준비가 끝난 시점에
[차단 감사](C:/Users/user/Desktop/SmartFactory/VM21_20261021_83be8a5a/records/setup-input-blocked-audit-20261021.json)를
기록해 goal 도구의 blocked 반환을 확인했다. 완료 판정이나 사용자 pause 요청이 아니었다.

이후 사용자가 준비된 검토안에 “원본 보존·해당 자료 사용 보류 승인”이라고 응답하여 goal이 active로
재개됐음을 확인했다. [승인 방침](../V2/05_운영_배포/historical_data_use_policy.md)과 같은 폴더의 JSON 원장에
온도19파일·PLC1항목·R5의 특정 이미지 실행 범위를 기록했다. 승인 원문과 검토안SHA를 결합한
[승인 기록](C:/Users/user/Desktop/SmartFactory/HIST_USE_20261021_d582ac91/approval-record.json)의 SHA는
`d28da33045678c3e0f5be0fa5adda3b06cbcb94d2c698b8d27f45e38db53c866`이다.

이번 사용자 응답 후 진행은 승인된 사용 방침의 실제 기록(PROGRESS)이다. 원본·운영 서버·학습
파이프라인을 수정하지 않았고 자동 차단이 구현됐다고 주장하지 않는다. 과거 손상 원인·복구·영향은
미확정이며 R4 NOT_PASSED/R5 INCOMPLETE/출시HOLD를 유지한다. 데이터 사용 결정은 더 이상 대기
사항이 아니지만 VM 화면 입력/Windows 설치/1·3탭은 남아 있다. 재개된 목표의 차단 감사는 새로 센다.

### 5.234 재개 감사와 Sandbox 오류 알림의 실제 정리

승인 응답 후 같은 화면 조건이 세 목표 턴에 걸쳐 남아 재개 차단 감사3을 마쳤고, goal 도구가 실제
blocked를 반환했다. 기록은 `VM21_20261021_83be8a5a/records/setup-input-resumed-blocked-audit-20261021.json`과
`setup-input-resumed-blocked-goal-result-20261021.json`에 보존했다. 이어 사용자가 현재 Sandbox 오류
창을 지목하자 goal이 active로 재개됐음을 확인하고 해당 실제 창을 조사했다.

두 창 모두 0x80370106이고 RemoteSession 생성 시각은 어젯밤 두 시험 시각과 부합했다. 공식 CLI의
실행 목록은0(exit0)이었으며, 각 오류 알림의 실제 닫기 버튼을 한 번씩 클릭했다. 후속 창 목록과
프로세스에서 두 알림 및 RemoteSession0, CLI 실행 환경0을 확인했다(f90f36 exit0). 이는 실제
화면 상태를 바꾼 PROGRESS지만 Sandbox 자체 오류 해결을 뜻하지 않는다.

별도 VMConnect에서는 메뉴 클릭과 Alt+V 뒤에도 메뉴가 나타나지 않았고 최종 상태는Off였다.
오류 없는 API 반환을 입력 성공으로 세지 않는다. 알림 두 개만이 VM 입력 장애 원인이라는 가설은
지지되지 않았고 정확한 원인은 미확정이다. [상세 확인](C:/Users/user/Desktop/SmartFactory/VMLOG_20261020_2d30f468/sandbox-alert-cleanup-20261021.md)의
SHA는 `043e99b0a84f09a7b1e31f8c6b2fec5ed52b7c31c7e553fe4d1966bdd5b8b2a2`다.
VM 시작·설치·재부팅·서버/제품/보안 변경은 없고 사용자 조건과 승인 데이터 방침·출시HOLD를 유지한다.

### 5.235 사용자 직접 설치 방식 승인과 VM R2 시작

사용자가 “지금 직접 조작하며 진행”으로 화면 도구 복구 대기 조건을 변경했다. 승인된 검토안과
해시를 보존하고, 잠긴 R2 실행기를 한 번 실행했다. native 관리자 도우미와 실행기는 실제 exit0으로
종료했다(721c1e). 결과 파일은 지정 VM의 Running, NIC0, 기존 콘솔 재사용을 확인한다(c3a177).
원본 ISO 전체 검산과 현재 빈 가상 디스크·자원 검사는 도우미 내부에서 통과했다.

실제 화면에는 UEFI 부팅 요약과 DVD boot loader failed/no OS loaded가 표시돼 Windows 설치 성공으로
판정하지 않았다. 원인은 미확정이다. 사용자가 VM 안의 Restart now와 DVD 부팅 안내 키를 조작하도록
안내했으며 현재 실제 설치 화면을 기다린다. PowerShell 실행기는 다시 실행하지 않는다.
이번 PROGRESS는 승인 조건 변경과 VM 시작의 실제 완료다. 호스트 재부팅·서버 접근·제품 변경·새 백업은
없다. 인터넷이 필요한 단계에서 멈추며 Windows 설치·1/3탭 QA·R1~R6와 출시HOLD는 미완료로 유지한다.

사용자가 Restart now 클릭이 되지 않아 직접 조작을 요청했다. 새 화면을 읽고 공식 도구로 클릭,
Tab·Enter와 화면 ID에 결합한 클릭까지 확인했으나 부팅 화면 변화가 없었다. 오류 없는 도구 반환은
입력 성공으로 해석하지 않았다. 직접 키보드에서도 같은지 구분하기 위해 사용자에게 VM 내부 클릭 후
Tab·Enter 비교를 요청했다. 동일 실패 입력이나 관리자 실행기는 반복하지 않는다.

### 5.236 직접 설치 응답과 화면 불일치로 인한 차단

사용자는 직접 입력 후 “설치 화면”이라고 답했으나 후속 창 읽기·전면 표시·새 관찰에서는
계속 UEFI 부팅 요약이 보였다. 사용자 답변을 부정하거나 화면 도구가 정확하다고 단정하지 않고
현재 직접 보이는 제목을 요청했다. 설치 진입 상태는 상충 관찰로 UNCONFIRMED다.

VMConnect PID49592는 존재하지만 시작 도우미는 terminal exit0이고 관련 실행 프로세스0이다
(d40020 exit0). 콘솔 존재를 진행 중 설치 시험의 VERIFIED_WAIT로 세지 않는다. 기존 1·3탭
실행기의 WDAG 계정/고정 경로와 Sandbox 폐기에 의존하는 정리를 읽고, 별도 VM에 그대로 실행할
수 없음을 확인했다. 실제 guest 식별·실행 경로 없이 격리 조건을 제거하지 않는다.

시작 후 입력 미확정, 사용자 답변과 화면 불일치, 현재 재확인까지 같은 설치/입력 의존성이
세 연속 목표 턴에 남았다. 직전과 이번 턴은 NO_PROGRESS이며 별도 시험은 시작하지 않았다.
`VM21_20261021_83be8a5a/records/manual-setup-screen-conflict-blocked-audit.json`을 검산한 뒤
goal 도구의 실제 blocked 반환을 확인했다. 완료나 사용자 pause가 아니며 현재 화면 제목 응답 또는
확인 가능한 화면·입력 경로가 제공되면 승인된 설치 단계에서 재개한다. 출시HOLD는 유지한다.

### 5.237 사용자 직접 확인 요청 후 native 상태 조회와 콘솔 재연결

사용자가 화면 내용 질문 대신 직접 확인하라고 요청해 goal active 재개를 확인했다. 공식 node 세션을
초기화하고 새 앱/창 선택으로 캡처했으나 기존 창에는 부팅 요약이 보였다. 일반 권한 Hyper-V 조회는
권한 거부(exit1)여서 지정 VM만 읽는 도우미를 구문/명령 목록/해시 검사 후 관리자 실행했다.
실제 exit0(2e4e07), VM Running·지정 ISO 연결·DVD 우선·NIC0를 확인했다. heartbeat 연결 없음은
설치 화면 부재의 단독 증거로 취급하지 않는다. 결과 SHA는
`5f029a26f0cd9f34213ccda38c60b1ebaa60ab9e15daba40627513b6d531468d`다.

VM 전원·디스크를 바꾸지 않고 새 VMConnect PID63884/window35130358을 열었다. 기존 작업용 연결을
새 콘솔로 넘기는 확인 창을 실제 읽었지만 클릭·Alt+C가 반영되지 않아 연결 전환은 미완료다.
사용자에게 화면 제목을 반복 요청하지 않고 연결(C) 한 번만 조작하도록 요청했다. 다음 화면은
Codex가 직접 확인한다. 이번 PROGRESS는 실제 관리자 조회와 새 콘솔 준비이며 UI 입력 복구나
Windows 설치 완료를 뜻하지 않는다. 서버/제품/새 백업 변경 없고 출시HOLD를 유지한다.

### 5.238 콘솔 확인 결과 정정과 실제3대 동시 사용 요구 확정

후속 사용자 응답은 연결(C) 클릭 완료다. 새 콘솔 캡처에는 부팅 요약이 반환됐지만 일반 권한
vmconnect 도움말을 읽었을 때 다른 VM 창 픽셀이 겹쳤고 좌표가 창 밖이라는 오류 및
`failed to activate captured window`가 발생했다. 기존 콘솔도 비활성 대화상자 accessibility와
다른 창의 잘린 픽셀을 함께 반환했다. 따라서 도구 이미지만으로 최신 설치 화면을 확정한
이전 설명을 정정했다. 직접 설치 응답과의 상충은 UNCONFIRMED이며 사용자에게 제목 전사를
다시 요구하지 않는다. 자체 도움말 PID38556만 시작 시각/명령/보유 handle을 대조해 정리했고
VMConnect49592/63884는 보존했다(dfc593 exit0). 권한·보안·VM 전원 변경은 없었다.

직전 목표 턴은 시험 목적 설명과 기존 자료 재확인뿐이므로 NO_PROGRESS로 분류한다.
이번에는 사용자가 실제로 여러 PC/탭에서 조회하고 약3대·각1탭임을 확정했다. 이는 Plan의
운영 요구를 구체화하는 PROGRESS다. 같은 창3탭의 마지막 탭만visible인 기존 설계를 읽어
독립3화면과 구분하고, 계획·설계5.128에 단일/동일브라우저/독립클라이언트/실PC 증거 범위를
반영했다. 이전 시험을 제외·통과시키거나 3대를 지원 최대치로 정하지 않았다.

기존 승인 SSH로 대상DESKTOP-CIIT7LK/user를 확인(b22f6f exit0)하고 관리자 권한과 앱8000의
순간 연결만 읽었다(dd3a15 exit0, 2026-10-21T01:22:04Z). backend3104 listener는0.0.0.0:8000,
Established2개·외부peer0이다. 이는 PC/사용자/탭 수나 평소 최대 사용량의 증거가 아니다.
추가 부하·설치·설정·원본 데이터·서버 화면 변경은 없으며 전면 표시의 현재값은 미확인이다.

현재 실제 Electron15분 revision4 COMPLETE/오류0, 120분COLLECTION_AND_BINDING_ONLY PASS,
닫힌CSV/이미지 완료 근거를 재대조해 보고서 상단의 오래된 '진행 중' 안내를 정정했다.
원래 결과는 재작성하지 않았고 새 시험도 실행하지 않았다. VM 설치 상태·동시 조회QA·R1~R6
잔여 조건과 출시HOLD는 유지한다. 필요한 다음 작업은 확인 가능한 VM 설치/입력 경로 확보와
실제3대 조건에 맞는 실행 구성 결합이며, 같은 실패 입력·완료된120분을 반복하지 않는다.

### 5.239 지속 VM용 식별 검사의 구현과 개발 호스트 거부 검증

직전 턴은 약3대·각1탭 요구 확정의 PROGRESS다. 현재 실행기를 다시 읽어 WDAG 고정 경로와
전체 Sandbox 폐기에 의존한 정리를 확인했다. 새 VM에서는 그 실행기를 그대로 재사용하지 않는다.
제품 실행 전에 사용할 읽기 전용 `preparation/vm_guest_guard.py`와 회귀 검사를 만들었다.

`C:\Python312\python.exe -B -m unittest -v test_vm_guest_guard`는11개/exit0(e4c71b)이다.
실제 개발 호스트의 CIM/계정/주소를 읽은 뒤 경로 접근 전에 거부했고, 합성 identity 일치/불일치,
외부IPv4/IPv6·잘못된경로·중복키·reparse와 실제 빈/사용된 파일시스템 경계를 검사했다.
호스트 위의 fixture에서 identity만 주입한 성공을 실제 게스트 실행 PASS로 확대하지 않는다.

실제 게스트 UUID/계정/binding은 아직 없고, 새 전체 입력 봉인·자식 job 정리·실행기 통합도 미완료다.
소스 파일2개와 검사 설명만 준비했으며 기존1230파일 묶음·후보·원본·서버·VM 전원은 변경하지 않았다.
이번 PROGRESS는 실행 전 검사 구현/검증이며 Windows 설치나 다중 PC QA 완료가 아니다.
확인 가능한 VM 설치 화면이 여전히 다음 실행의 의존성이다. 출시HOLD/승격false를 유지한다.

### 5.240 설치 화면 의존성 재검증과 blocked 전환

직전 식별 검사 구현은 PROGRESS였지만 설치 화면/입력 의존성은 동시 사용 요구 확정,
식별 검사 준비, 이번 재확인까지 세 연속 목표 턴에 남았다. 이번 턴은 NO_PROGRESS다.
실제 시작기 PID3700은 현재 없고 원래 종료 기록은exit0이다(064169/972e90 exit0).
연결 콘솔49592/63884의 존재만으로 설치나 시험 진행을 VERIFIED_WAIT로 세지 않는다.
준비한3파일 해시는 동일하며 새 제품/VM 실행·서버 작업·백업을 수행하지 않았다.

독립 준비 이후 실제 게스트 식별·실행기 통합/검증은 신뢰 가능한 설치 화면 및 설치 완료에
의존한다. 사용자에게 현재 VMConnect 캡처1장을 요청했고 화면 제목을 다시 전사하도록
요구하지 않는다. 기존 공식 도구 재선택/새 콘솔/native 상태/일반 창 대조의 실패 근거를
`records/persistent-vm-setup-blocked-audit-20261021.json`에 묶어 검산했다.
SHA256은`340e76c223dddeb76b6c221ebdfdfd9c7eeda2e83d564f8f13786bfb3171e362`다.

goal 도구가 실제 blocked를 반환했다. 완료나 사용자 pause가 아니며 목표 범위·출시HOLD는
유지한다. 최신 실제 화면 또는 복구된 공식 화면/입력 경로가 제공되면 승인된 설치 단계에서
재개하고 이후 약3대·각1화면 동시 조회와 나머지 QA를 이어간다. 같은 실패 입력이나
완료된15분/120분·사전 검사를 단순 대기 중 반복하지 않는다.

### 5.241 공식 Hyper-V 관리 API로 화면·입력 복구와 실제 설치 진행

2026-10-21 사용자가 다른 방법으로 직접 확인·설치를 계속하도록 요청해 goal active를 확인했다.
VMConnect 캡처는 여전히 부팅 오류를 반환했다. 공식 `GetVirtualSystemThumbnailImage`를
지정 VM/디스크/NIC0에 결합해 직접 읽었으며, 현재 실제 UEFI 오류임을 확인했다(a21333 exit0).
RGB565 응답의4바이트 길이 prefix를 처리하기 전 세 변환 실패는 원문 그대로 보존했다.

`Msvm_Keyboard.TypeKey`와 화면 해시 재확인을 결합하여 실제 Tab focus·Enter 입력을 확인했다.
화면이 달라진3건은 입력 전에 거부했고 key_sent=false였다. DVD의 짧은 키 대기는 관찰된
안내 문구 픽셀과 일치할 때만 Space를 보냈다. 부팅 전환 중 읽기 실패는 보존하고 bounded
읽기 재시도를 넣은 R2가 실제 exit0/prompt_match=true였다(21cffe). 임의 입력·보안 완화는 없다.

관리 API 프레임에서 설치 언어 화면, 빈64GB 단일 디스크, Windows 11 Enterprise Evaluation을
직접 확인했다. 기존 설치 승인에 따라 Install 입력을 전달했고 실제 exit0(01d04a), 설치7%와
이후40%(13:36:57 KST)를 확인했다. 화면 의존성은 해결됐고 OS 설치가 실제 진행 중이다.
이번 턴은 PROGRESS다. 네트워크·계정·보안/개인정보 단계에서 멈추는 기존 조건은 유지한다.

실행 및 화면 근거는 `VM21_20261021_83be8a5a/management-recovery-review.md`와 records에 있다.
VM 설치 완료·실제 게스트 binding·후속 실행기 통합/동시 조회 QA는 아직 완료하지 않았다.
운영 서버·제품 소스·기존 데이터·완료된120분 검증은 변경하지 않았고 출시HOLD를 유지한다.

후속 확인: 파일 설치와 자동 재시작 후 OOBE로 진입했다. 화면 해시/해상도에 결합한 공식
가상 마우스 API로 Korea/US 기본 설정을 진행하고, 제공된 I don't have internet을 선택해
NIC0를 유지했다. 계정 이름 화면에서 멈춰 사용자에게 계정·비밀번호·개인정보 설정을 요청했다.
13:49:53 KST 관리 조회는 실제 exit0(4742ba), Running/정상 heartbeat/KVP/CPU4/RAM8GiB,
지정 단일 VHDX·NIC0·Windows Boot Manager를 확인했다. KVP OSName은 Windows10 표기,
설치 화면은 Windows11 표기여서 원문을 보존하고 실제 게스트 OS/에디션/인증 검증을 남긴다.
설치 화면 의존성은 해결됐으나 계정 초기 설정·게스트 binding·제품 QA는 미완료다.

### 5.242 별도 VM의 시험 프로세스 정리 경로 준비

계정 초기 설정 응답을 기다리는 동안 기존 Sandbox 전체 폐기 계약을 대체할 독립 모듈을
준비했다. `VM21_20261021_83be8a5a/preparation/vm_process_lifecycle.py`는 생성한 작업자를
이름 없는 Windows job에 결합하고 gate를 연다. 기존 field_windows_job.py와 바이트가 같은
복사본을 사용하며 봉인된 Sandbox 입력·제품·서버·VM 계정 화면은 변경하지 않았다.

최종 상태에서 실제 Windows 합성 프로세스로 9개 unittest가16.713초/exit0이었다
(c5a23f/23a7d7). 정상 종료·협조 종료·강제 정리·자식 잔류·코드23·job 결합 실패·계수 조회
실패·잘못된 예산/기존 결과·제어기 소실을 검사했다. 제어기 소실은 미리 보유한 읽기 전용
핸들로 작업자와 자식 모두 종료됐음을 확인했다. 별도 무관한 프로세스는 계속 실행됐다.

시간 제한 후 정상 정리돼도 FAIL이며, job 계수 조회 실패는 cleanup_confirmed=false다.
제어기 소실로 비어 있는 최종 보고는 검증 불충분이다. 데이터 저장·제품 QA PASS를 주장하지 않는다.
결과 파일/소스 재대조 exit0(36a17c), `preparation/lifecycle-verification.json` SHA256은
`83c769cfc0b52784367de99ce12cf8ce29a1bbc961f602be53e9d7c86b0bc41d`다.

이번 턴은 독립 실행기 준비의 PROGRESS다. 전체 실행기에는 실제 게스트 identity와 입력
manifest, 브라우저/백엔드 협조 종료·정상 저장 검산을 연결해야 한다. 계정 초기 설정 완료
응답은 아직 없으며 개인정보 입력 중일 수 있어 화면을 재촬영하지 않았다. 실제 제품 시험,
동시 조회 비교·운영 승격은 미완료이며 출시HOLD를 유지한다.

### 5.243 VM 실행기 통합 준비와 계정 초기 설정 의존성

`VM21_20261021_83be8a5a/preparation/runner-r1`에 실제 identity/입력 해시 잠금/소유 job을
연결한 실행기 후보를 준비했다. 기존1·3탭은 유지하고 독립 브라우저3개·각1탭을 추가한다.
각 조건의120초 warmup·300초 측정과 전체 FACT 입력, 실제 visibility·요청·이미지 load/error,
자원·종료·저장 대조를 유지한다. 숨김을 강제로 visible로 바꾸거나 실제3대 검증으로 확대하지 않는다.

최종 Python18개 검사4.406초/exit0(3afdab), Node4개 및 문법 검사exit0(011a91), PS5.1 구문과
실제 개발 PC 거부 검사exit0(f2edb2)를 확인했다. 거부된 PS 자식은 기대한exit1이다.
실제 파일 잠금과 개발 PC 거부를 확인했고, 브라우저 조율/취소 일부는 제어된 모의 프로세스 검사다.
취소 후 정상 저장 정리 경로를 확인했지만 이것을 실제 CSV 저장·제품 QA 결과로 해석하지 않는다.
이전9개 native job 검사 모듈은 같은 바이트로 재사용했다.

기존 입력과 새 준비 파일1,236개·3,115,219,713바이트의 전체 SHA256 대조가exit0이었다
(298899/02332d). 새 전체 백업이나 대용량 중복 사본은 만들지 않았다. 실제 게스트 binding과
실행용 manifest는 아직 없다. verification SHA256은
`ae5cb88bf1391bb666a62774bc9f8f50f6e8e3ad06f39eade8bbabdf11a82b5c`다.

이번 턴은 PROGRESS이지만 계정/비밀번호/개인정보 초기 설정 의존성은 설치OOBE 진입,
native 수명 검사 준비, 이번 실행기 통합까지3연속 목표 턴에 남았다. 초기 설정 완료 응답은 없고,
인증 입력 중일 수 있어 화면을 재촬영하지 않았다. 현재 화면이 여전히 같다고 단정하지 않는다.
실제 게스트 UUID/SID/세션/경로 결합, 최종 묶음 전달, 게스트 실행은 이 입력 없이는 진행할 수 없다.

독립 준비를 끝낸 뒤 `records/account-setup-dependency-audit-20261021.json`에 의존성을 기록했다
(SHA256 `31bd914fa70e63833ea6951c584eac76f22b247e58d36d0a78394382d332e44c`). goal 도구가
실제 blocked를 반환했다. 완료나 사용자 pause가 아니며 출시HOLD·기존 롤백 기준을 유지한다.
사용자가 VM 바탕화면 진입을 알려 주면 실제 게스트 확인부터 재개한다. 비밀번호는 요구하지 않는다.

### 5.244 재개 후 실제 VM 꺼짐 확인과 초기 설정 복귀

사용자의 ‘바탕화면 직접 확인’ 요청으로 목표가 active로 재개됐다. 15:20:02 KST의 native 조회
(3c17ea, exit0)와 새 VM 연결 창 화면에서 지정 VM의 Off 상태를 확인했다. 꺼진 원인은 미확인이다.
화면의 시작 버튼 입력은 반영되지 않아, 기존 승인 범위에서 정확한 VM ID·단일64GiB VHD·NIC0·
Windows Boot Manager를 검사하는 관리 도우미로 시작했다. 구문 검사5530f9와 실제 실행9a80a8은
exit0이며 15:25:16 KST에 Running을 확인했다. 새 설치·네트워크 추가·호스트 재부팅은 하지 않았다.

공식 Hyper-V 화면 조회에서 국가 선택 OOBE를 확인했다. 이미 승인된 Korea/US/추가 키보드 생략/
공식 오프라인 선택을 화면 해시에 결합한 입력으로 진행했다. 네 입력 모두 실제 exit0이었다
(095d45,7f00c9,0552f9,3cc390). 15:27:59 KST 화면은 ‘Who’s going to use this device?’이며
이름 칸이 비어 있다. 바탕화면이나 계정 설정 완료를 주장하지 않는다. 인증·개인정보 입력은
자동화하지 않고 사용자에게 해당 부분만 요청했다. 이후 화면은 Codex가 직접 확인한다.

근거는 `VM21_20261021_83be8a5a/records/resume-desktop-check-20261021.json`에 결합했다.
이번 재개 주기의 첫 의존성 확인이며 이전3회 blocked 판정 횟수를 이어 붙이지 않는다.
게스트 binding·최종 입력 전달·제품 QA는 미완료다. 준비된 실행기 검사를 반복하지 않았고
운영 서버·완료된120분 증거·롤백 기준은 변경하지 않았다. 출시HOLD를 유지한다.

### 5.245 동시 조회 관찰의 HTTP 측정 누락 검출

계정 설정 대기 중 R1 수집 반복문을 검토해, 지연 후 health 예정 번호를 건너뛰고 data 요청도
생략할 수 있지만 별도 누락 판정이 없음을 확인했다. `preparation/runner-r2/review.md`의 R2는
요청 간격을 바꾸지 않고 예정 번호/시각을 보존하며 health211/data71/resource85 슬롯을 검사한다.
누락·중복·잘못된 기록을 측정 불충분으로 표시하고 제품 데이터 손실과 구분한다.

최종 Python25개5.701초/exit0(7e7497). 제어된 시계/프로세스로 실제 반복문을 실행한 재현에서
자원85개가 모두 있으나 health3회/data1회가 빠지는 경우를 검출했다. 최초 추가 재현의 Mock
클래스 누락 실패(4c7e0f)는 시험 대역을 수정해 해결했고 전체 검사를 다시 통과했다.
Node/PS5.1/job 코드8개는 동일 바이트여서 기존 검사를 재사용한다. 새 모듈과 수정 수집기 포함
16개 작은 입력 해시와 목록의 유일성/합계를 검사했다. 1,221개 재사용 파일의 과거 해시는
승계하며 이번에 3GB 원본을 반복 검산했다고 주장하지 않는다. 실제 전달 전후 검산은 남아 있다.

이 턴은 실행기 보완의 PROGRESS다. 계정/개인정보 완료 응답은 아직 없으며 사용자 인증 입력
중일 수 있어 화면을 다시 촬영하지 않았다. 재개 주기의 의존성 확인2회이며 목표active를 유지한다.
실제 게스트 결합·전달·제품 시험은 미완료, 출시HOLD다. R1 원본과 기존120분 증거는 보존했다.

### 5.246 계정 설정 의존성 재확인과 재개 주기 대기 전환

15:39:18 KST 공식 Hyper-V 화면 조회가 실제 exit0(f76515)으로 끝났다. 현재 화면은
‘Who’s going to use this device?’이며 Name 칸은 비어 있고 바탕화면은 없다. 입력은 보내지 않았다.
R2 검증 기록과 준비 소스19개/최종 목록 해시를 대조했고 동일했다. 완료된 검사는 반복하지 않았다.

재개 후 VM 복귀, 관찰 누락 보완, 이번 직접 확인의3연속 턴에 동일 계정/개인정보 의존성이
남았다. 이전 재개 전 blocked 횟수는 합산하지 않았다. 이번 턴은 NO_PROGRESS이며 실행 중 QA를
기다리는 verified wait가 아니다. 독립 준비가 끝나 실제 게스트 binding/실행은 사용자 입력에
의존한다. `records/account-setup-resumed-dependency-audit-20261021.json` SHA256은
`4f5903a7578f9845916e702e8327f7427a8a6786414845c08ade270e681a446a`다. goal 도구가 실제
blocked를 반환했다. 계정 설정 후 직접 바탕화면 확인과 R2 묶음 결합부터 재개하며 출시HOLD다.

### 5.247 계정 설정 완료·평가판 종료 원인 확인과 중복 연결 창 정리

사용자의 SFLQA 설정 완료 응답 후 16:09:55 KST 공식 Hyper-V thumbnail 읽기(exit0,8c6ff7)에서
바탕화면을 직접 확인했다. 화면에는 평가판 라이선스 만료 워터마크가 있었다. 사용자가 native
자격 증명 창에 비밀번호를 직접 입력한 뒤 PowerShell Direct 읽기가 exit0(0a310a)으로 완료됐다.
첫 읽기 도우미는 없는 ConsolePrompting 속성 처리 오류로 인증 전에 종료됐고 새 R2에서 기본값
읽기로 수정했다. 기존 실패 기록을 보존했으며 콘솔 정책이나 계정 설정을 변경하지 않았다.

실제 게스트 DESKTOP-GK5R521/UUID272276EE-6CD7-44F4-B184-4744C5A576EC,
SFLQA SID의 Explorer 세션2를 확인했다. 원격 명령 세션0을 GUI 세션으로 해석하지 않는다.
OS는 Windows11 Enterprise Evaluation/26300.9457, LicenseStatus5/0xC004F009,
남은 인증 유예0분이다. System1074에 wlms.exe의 라이선스 만료 종료 사유가 있다.
이 기록은 적어도 해당 종료의 원인을 설명하며 이전 Sandbox 오류 전체의 원인으로 확대하지 않는다.
게스트 UTC23:15와 실제 호스트 UTC07:15 사이 약16시간 차이가 있다. 1601년 sentinel을 실제
만료일로 해석하거나90일을 이미 사용했다고 판단하지 않는다. 시계/정식 인증은 아직 변경하지 않았다.
credential_persisted=false,session_removed=true,guest_mutation=false였다.

호스트 네트워크 준비 읽기exit0(23e151): NIC0, 시간 동기화 서비스Enabled,
Default Switch IDc08cb7b8-9b3c-408e-8e30-5e16a3aeb444를 확인했다. 스위치/NIC를 만들거나
인터넷에 연결하지 않았다. 계정 의존성은 해소됐고 별도 임시 연결·정식 인증·격리 복귀 절차 준비가
다음 단계다. 게스트 시계 정정은 현재 실제 시각과 맞추기 위한 것이며 평가 기간 연장 우회가 아니다.

사용자가 중복 연결 창 확인·정리를 요청했다. native 창/프로세스/명령줄/생성 시각 조회로
두 vmconnect가 같은 시험 VM 하나를 가리킴을 확인했다(043fab,exit0).
화면 도구의 닫기 입력은 반영되지 않아, 정확한 실행파일·PID·생성시각·명령줄·창 핸들을 재검사한
관리 도우미로 오래된 연결 프로세스49592만 종료했다(6dd2c5,exit0). VM 전원 명령은 없었다.
남은63884/창35130358과 연결 설정 대화상자24776012를 재확인했다. 정리 전후 VM은Running,
uptime3496.406→3496.957초,NIC0다. 파일 삭제나 VM 재부팅을 하지 않았다.

근거는 VM21 records의 guest-identity-license-r2-20261021.json,
network-prerequisites-20261021.json,vmconnect-inventory-20261021.json,
vmconnect-dedup-20261021.json이다. 목표active·PROGRESS이며 실제 제품 시험과 출시gate는 미완료다.

### 5.248 평가판 인증 준비와 임시 네트워크 정리 계약 검사

`VM21_20261021_83be8a5a/preparation/activation-r2/review.md`에 실제 Default Switch와
대상 VM·게스트 UUID/SID·EnterpriseEval을 결합한 변경안을 준비했다. 시계 정정과 공식
`slmgr.vbs /ato` 뒤 NIC를 제거하며, 제어기가 중단돼도10분 뒤 소유 NIC만 제거할 예약 작업을
연결 전에 등록·확인한다. Microsoft 도메인만 통신 가능하다는 제한을 주장하지 않는다.

정책20개 nativePS5.1 검사exit0(ad45de), 실제 정리 스크립트의 명령 대역5개exit0(7cf08b).
무관한 NIC·이름 불일치·해시 불일치에서 임의 대상을 제거하지 않음을 검사했다.
첫 R1의 목록 비교 우선순위 오류(2228d7)는 새 R2에서 수정했고 R1을 보존했다. 첫 정리 대역
검사의 script 범위 변수 오류(ad45de)는 시험 대역의 독립 프로세스 global 변수로 수정했다.
최종 실제 네트워크 명령·예약 작업 실행을 시험한 것으로 확대하지 않는다.

해시 잠금 실행기의 실제 관리자 읽기 계획검사exit0(c24050):16:35 KST VM Off·NIC0·스위치ID
일치. 마지막 종료 원인을 확인할 새 게스트 로그는 아직 읽지 않았다. 잘못된manifest해시의
실행 거부는 기대한exit1이며 검사전체exit0(fcaf18)였다. 최종 문법/실제명령 매개변수 검사exit0.
manifest SHA256은4080a54a5e82e37cd9e92d962ec7faa012a584cbacfd139b904b81718a2205c4다.

기존 설치 승인의 인터넷 단계 보류 때문에 구체 변경안에 대해 임시 연결·시계 정정·공식 인증·
일회성 관리자 정리 작업을 확인 요청했다. 아직Apply를 실행하지 않았고 네트워크/시계/인증을
변경하지 않았다. 이번 턴은 실행기 준비의PROGRESS이며 목표active·출시HOLD를 유지한다.

### 5.249 인증 실행기의 실패 경로 추가 검사

인터넷 연결 승인 대기 중 `preparation/activation-workflow-tests/test-workflow.ps1`에서
해시 고정된 실제activation-r2 실행기 본문을8개 조건으로 실행했다. Hyper-V·인증·원격 명령·
작업 스케줄러 명령20개가 모두 함수 대역인지 먼저 확인하고, 원격 ScriptBlock은 실행하지 않았다.
실제 VM/네트워크/인증/예약 작업 변경은 없다. 대역 결과 폴더에는 synthetic 표시를 별도로 남겼다.

실제 native관리자 PowerShell 검사exit0(232d18): 정상, 인증 호출 실패, 예약 작업 등록 실패,
연결 실패, NIC 정리 실패, 잘못된 게스트, 시각 불일치, 인증 상태 미충족8개가 예상대로 끝났다.
정상만0이고 나머지는 기대한1이다. 등록 실패 후 연결0회, preflight 실패 후 NIC 생성0회,
즉시 정리 실패 후 예약 정리 작업 보존, 나머지 조건의 세션/자격 증명 정리를 검사했다.
이는 실제 네트워크 연결·정식 인증·Windows 예약 작업의 시간 도래 실행을 증명하지 않는다.

기존 봉인activation-r2 입력/실행기를 변경하지 않았다. 실제 제품 QA와 운영 승격은 미완료다.
승인 요청 후 두 번째 목표 턴이며 독립 검증을 완료한PROGRESS다. 승인 응답은 아직 없고,
실행 중인 인증 작업을 기다리는 verified wait가 아니다. 목표active·출시HOLD를 유지한다.

### 5.250 임시 연결 승인 의존성 확인과 목표 대기 전환

16:45:24 KST 읽기 전용 실제 확인exit0(9ef522): 지정 VM Off·NIC0·해당 임시 정리 작업0·
인증/워크플로 실행 프로세스0였다. 봉인입력과 최종8개 검사 기록도 같은 해시다. 검사는 반복하지 않았다.
임시 연결 승인 요청 이후 준비, 실패 경로 검사, 이번 재확인의3연속 목표 턴에 승인 응답이 없었다.
독립 준비는 완료됐고 실제 인증·격리/게스트 QA는 보류된 연결 범위의 사용자 승인에 의존한다.
이번 턴은 NO_PROGRESS이며 verified wait나 완료가 아니다. dependency audit SHA256은
c4764940b9608a8ca4e3f2f129041f718766018ce14357e8ccd01f18d420b62f다.
goal 도구가 blocked를 반환했다. 기존 승인 질문을 중복 전송하지 않으며 응답 후 새 실제 상태와
호스트 시각을 확인하고 해시 고정activation-r2부터 재개한다. 출시HOLD·실제동시QA 미완료를 유지한다.

### 5.251 임시 연결 승인 수신과 실제 인증 실행 시작

2026-10-22 사용자가 준비된 임시 연결·실제 시각 정정·공식 인증 범위를 승인했다. 이전 승인
의존성은 해소됐고 goal은active로 재개됐다. 독립 UTC와 호스트 UTC를 대조했고, 기존
activation-r2 실행기/manifest/입력 해시를 잠근 native64bit PS5.1 관리자 실행을 시작했다.
정확한 시각 기준은2026-10-21T16:38:14Z(한국10월22일01:38:14)다.

실행 PID35960/exec session2347, 실제 실행 폴더records/activation-d05984dcfb7d를 확인했다.
waiting-credential.json의 PID와 생존 프로세스가 일치한다(455773/13edbf). 실제 결과는 아직
없고 자격 증명 입력 대기다. Get-Credential 이후 단계인 시계 정정·NIC 연결·인증은 아직 실행
결과가 없다. 비밀번호를 자동 입력하거나 채팅으로 요청하지 않고 해당 Windows 창 입력만 요청했다.
후속 session2347 조회도 실행 중이었다(741752/4343f8). 시간 초과만으로 재시작하지 않는다.

승인/실행 근거는records/activation-approved-start-20261022.json과 승인된 실행 래퍼에 보존한다.
이 턴은 실제 승인된 실행 시작의PROGRESS다. 이전 blocked 횟수를 새 재개 주기에 합산하지 않는다.
최종 결과와 실제 NIC0/예약 작업·세션 정리를 확인하기 전 환경 준비나 제품 QA 통과를 주장하지 않는다.

### 5.252 실행 생존 확인과 수동 인증 단계 확인 대기

2026-10-22 01:50 KST 별도 읽기 전용 관리자 검사 exit0(773b02/301917)에서 지정 VM은
정상 작동, uptime 약12분, NIC0, 임시 정리 작업0이었다. PID35960의 생성 시각과 생존을
대조했고, 같은 exec session2347도 계속 실행 중이었다(9874e8/564e17). 프로세스를
종료하거나 인증을 중복 실행하지 않았다. 이 턴과 직전 턴은 VERIFIED_WAIT다.

`waiting-credential.json`은 Get-Credential 호출 직전 기록이다. 이 파일만으로 현재 호출이
Get-Credential인지 이후 New-PSSession인지 구별할 수 없다. 따라서 앞 절의 '입력 대기'는
관찰된 마지막 단계이며 실제 입력 미완료의 확정 증거가 아니다. 창 목록에서도 인증 창이
확인되지 않았고, 최종 인증 결과와 시계 변경 여부는 아직 미확인이다. NIC0는 직접 확인했다.

승인 후 실제 실행 시작, 생존/창 확인, 이번 별도 호스트 확인의3연속 목표 턴 동안 수동 인증
입력 또는 그 완료 상태에 대한 응답이 없었다. 독립 준비는 끝났고, 현재는 기존 질문의 응답
또는 실제 실행 종료 결과 없이는 다음 인증/게스트 QA 단계로 진행할 수 없다. 목표 도구가
blocked를 반환했다. 이는 살아 있는 실행기를 중단됐다고 판정하거나 관찰 시간 초과로
재시작한다는 의미가 아니다. 실행기는 그대로 두며 추가 인증 실행을 시작하지 않는다.

근거: `VM21_20261021_83be8a5a/records/activation-manual-step-dependency-audit-20261022.json`,
SHA256 `b723fa5884bb5f73c6a6b9c20d3fb733e63d968a2fb1505f43439a9959b7fd00`.
응답 후 같은 실행의 terminal 결과부터 확인한다. 실제 stale-anchor 실패로 끝난 경우에만
정리 결과를 확인한 뒤 기존 승인 범위에서 새 시각 기준으로 재개한다. 출시HOLD를 유지한다.

### 5.253 VM 평가판 실제 인증 완료와 네트워크 격리 재확인

2026-10-22 수동 인증 응답 후 기존 실행의 실제 종료 결과부터 확인했다. R2는 긴 입력 대기 뒤
시각 기준 만료로 종료했고, R3는 게스트 OS 하트비트의 `OkApplicationsUnknown`을 부팅 실패로
잘못 제한하여 종료했다. 새 R4는 정상 OS 하트비트를 허용하고 실제 native 문법/명령 검사,
정책37개와 흐름12개 검사를 통과했다. 기존 실패와 봉인 파일은 보존했다.

R4는 게스트 UTC의 약16시간 차이를 정정하고 승인된 임시 연결에서 공식 인증을 요청했다.
응답0xC004E028은 다른 인증 진행 중 상태였으며, 당시 LicenseStatus5/남은 기간0을 성공으로
취급하지 않았다. 해당 실행의 NIC·예약 작업·세션 정리를 확인했다. 새 R5는 `/ato`를 반복하지
않고 기존 인증의 완료를 최대180초 관찰하도록 준비했다. 실제 조회 본문6개/흐름13개 검사와
native 문법·명령 검사는 모두exit0이다. 시험 대역 분기 누락의 첫 실패도 보존했다.

실제 R5 실행 `records/activation-cf31ef1aeae2`는08:56:15 KST에exit0으로 끝났다.
`EVALUATION_VERIFIED_NETWORK_ISOLATED`, LicenseStatus1, 남은129600분(관찰 시점90일),
network_isolated/scheduled_cleanup_removed/session_removed 모두true, credential_persisted=false다.
관찰5.49초에 상태가1로 바뀌었으며 새 인증 명령을 발행하지 않았다. 원본 결과·래퍼 완료 파일과
exec terminal exit0을 대조했다(aed55d/950cf6).

08:59 KST 별도 관리자 읽기exit0(9901bf/e39987)에서 대상 VM Running, NIC0, 임시 정리 작업0,
인증 실행 프로세스 없음도 확인했다. 근거는
`VM21_20261021_83be8a5a/preparation/activation-r5/verification.json`, SHA256
`c17521421b3fee534b5b4418b7e5369a8bd364094aa4e7fd0ecb3697e1263dc5`다.
이 결과는 시험 VM의 정식 평가판 인증·격리만 증명한다. 동시 조회 제품 QA와 출시 판정은 미완료다.

기존 실행기 R2의1237파일·3,115,223,345바이트를 재사용하고 실제 새 게스트 세션 식별값을 더해
전달 전후 검산한다. 한 PowerShell Direct 연결에서 식별·전달·시험·결과 회수를 수행하도록
준비하여 수동 비밀번호 반복 입력을 줄인다. 사용자가 VM 연결을 눌렀고 새 화면은 SFLQA 로그인
화면이다. 인증 입력은 자동화하지 않으며 실제 바탕화면 준비 후 GUI 시험을 진행한다.
제품 설정·운영 서버·기존 원본·롤백 기준은 바꾸지 않았다. 목표active·출시HOLD·승격false다.

### 5.254 VM 바탕화면 확인과 단일 연결 QA 도우미 시작

사용자가 연결·로그인을 완료한 뒤 실제 vmconnect 화면에서 Windows 바탕화면과 평가판90일
표시를 확인했다. 계정 설정을 다시 요구하지 않았다. 기존1237파일·3,115,223,345바이트를 모두
읽어 원본 해시 일치를 재확인했다(exit0,92233b). 새 전체 백업이나 대용량 개발 PC 사본은 없다.

`preparation/qa-session-r1`은 인증을 반복하지 않도록 PowerShell Direct 연결 하나에서 실제
게스트 식별, 파일 전달과 정확한 집합 검산, 로그인 세션의 일회성 작업, 결과 회수를 담당한다.
13개 잘못된 경로/알 수 없는 루트 거부와 native명령9개·작업 정의 검사exit0(c08330), 실제
전달 검산 본문4조건·오류 기록 실행기4조건 검사exit0(5c4eb3). 마지막 봉인 실행기 읽기 검사도
exit0(47adb7)다. 실제 게스트 시험 완료를 주장하지 않는다.

새 입력은 기존1237파일에 실제 guest-binding과 작은 launch 오류 기록 실행기를 더한1239개,
manifest 포함1240개다. 전달 완료 후 주 담당자가 실제 결과를 검토해 같은 두 해시의 시작 요청
파일을 기록한다. 추가 사용자 승인을 요구하는 단계가 아니다. 실행기 R2의 제품 설정·표시 관찰·
정상 종료·제어기 소실 시 소유 job 정리·기한을 유지한다. 세션0 GUI 실행은 거부한다.
호스트 진행 확인은 정해진 파일만 조회하며, 결과 전수 회수는 측정 종료 후 수행한다.

실제 PID41448/exec session24687을 시작했고,09:13 KST 자격 증명 단계까지 도달했다.
`records/qa-session-c1752142/waiting-credential.json`과 controller PID가 일치한다.
사용자에게 해당 Windows 인증 입력만 요청했다. 입력 대기는 마지막 관찰 단계이며 이후 진행은
stage/결과 파일로 확인한다. 중복 실행하지 않는다. 목표active·출시HOLD를 유지한다.

### 5.255 FAT32 추가 스트림 전송 오류와 기존 사본 재사용 R2

R1은09:21 KST에exit1로 끝났다(3b2635). 설치·QA 시작false, 세션 제거true,
예약 작업 잔류false다. E:는FAT32이며,2,350,216,905바이트 CSV의 추가 스트림 열거에서
같은 GetStreams 오류를 읽기 전용으로 재현했다(174529). CSV 본문이 완전히 전달됐는지는
아직 게스트 해시로 확인하지 않아 성공으로 간주하지 않는다. R1·원본·부분 사본은 보존했다.

새 qa-session-r2는 원본1237파일을 다시 잠금·검산하고, 같은 게스트 루트의 기존 파일을
전수 해시로 대조한다. 일치하면 복사를 건너뛰며, CSV 부분 사본만 원본의 같은 길이 앞부분과
일치할 때 이어 쓴다. 추가 스트림 열거를 사용하지 않는다. 다른 파일 불일치·예상 밖 파일·
재분석 경로는 중단한다. 제품 실행기와 시험 조건은 변경하지 않았다.

nativePS5.1에서 실제 전송 본문9조건(직렬화 왕복 포함)exit0 ac6a75, 기존 파일 목록4조건
exit0 3ae5a6, 경로13조건/알 수 없는 루트/명령9개 exit0 9cd6bd,
전달 검산4조건/실행기4조건 exit0 9a4e87을 확인했다. 봉인 실행기의 마지막 읽기 검사도
1237경로와 문법exit0 206d3f다. 준비 기록 SHA256은
274c39e719487d37d5a91596ed05ecfcc674abbae88726a8e90909f25505c1b8이다.

R2 PID41436/exec73597은09:33 KST 인증 대기에 도달했고 사용자가 입력 완료를 알렸다.
같은 세션에서 기존 사본 검산·남은 전달·로그인 세션 QA·회수를 이어간다.
이 단계는 실제 전달/제품 시험 통과가 아니다. 출시HOLD·승격false·목표active를 유지한다.

R2 실제 전달은09:34 KST에완료됐다. 큰 CSV를 포함한1221개는전체해시가일치하여재사용했고
나머지원본16개만복사했다.최종1239입력+manifest1240파일정확집합검산성공(08aa66).
09:35새vmconnect화면에서로그인바탕화면을확인한뒤동일manifest/binding해시로
시작요청을기록했다(ad0c71).로그인세션2의일회성QA작업Running을확인했다.

### 5.256 동시 조회 시험 초기 종료와 결과 회수 오류 분리

R2 게스트 작업은 09:36:09 KST에 Ready/LastTaskResult1/entry-terminal 존재로
종료됐다. 호스트도 exit1(1a67c5)이며, 결과 폴더의 Copy-Item -FromSession에서
Length 속성 오류가 발생했다. task_removed/session_removed=true, task_left_registered=false다.
시험의 실제 내부 실패 원인은 아직 회수하지 못했다. 전송 성공과 제품 QA 성공을 구분한다.
비교 관찰 21분이 완료됐다고 기록하지 않는다.

VM 화면 읽기는 되지만 폴더 더블클릭이 재시도에도 반영되지 않았다. 새 R3는 결과 폴더와
launch-result만 본문·SHA256으로 읽으며 재분석 경로, 파일당10MiB/전체50MiB/200파일
제한을 검사한다. nativePS5.1에서 빈 파일·하위 폴더·직렬화·해시·크기 제한 및 검토 작업
접수 경계 7조건 exit0(f7af44), 봉인 실행기 문법/해시 검사 exit0(e82a65)다.
기존 실패 기록·입력·제품 바이트는 수정하지 않았다.

R3 PID28448/exec31959가 09:41 KST에 Windows 자격 증명 입력을 기다린다.
비밀번호는 저장하지 않는다. 회수 뒤에는 같은 연결을 유지하며, 주 담당자가 로컬에서
준비·검사한 QA 작업의 이름·해시를 명시한 경우에만 다음 작업을 실행한다.
회수 내용에서 명령을 자동 도출해 실행하지 않는다. 연결 최대2시간/종료 요청 시 제거한다.
출시 HOLD와 승격false를 유지하며, 실제 실패 원인 분석·동시 조회 QA는 미완료다.

### 5.257 실제 초기 실패 회수와 일반 권한 시험 재개

R3 인증 후 동일 연결에서19파일을 본문·SHA256으로 회수했다(80e9db).
제품 설치 전 smoke에서 최초 Chromium 프로세스 exit0 후 listener unavailable로 실패했다.
이미지/HTTP 요청0건이며, job의 잔류9개를 정리해 active0/cleanup_confirmed=true다.
현재 guest state도 task0/process0/제품 미설치다. 이는 제품 동시 조회 실패 측정값이 아니다.
이전 정리의 forced_termination=true를 정상 종료로 바꾸지 않는다.

동일 프로파일의 DevToolsActivePort가 생성돼 있었고 Chromium 버전은148.0.7778.96이다.
Highest 작업에서 브라우저가 일반 권한으로 다시 실행된 정황으로 추론했다. Chromium 공식
chrome/app/chrome_main_delegate.cc 주 브랜치의 MaybeAutoDeElevate가 이 동작을 설명한다.
설치 버전의 소스 바이트를 대조한 것은 아니므로 Limited 실행의 실제 결과로 검증해야 한다.

runner-r3-limited는 Interactive/Limited 작업과 관리자 토큰 거부를 추가하고 새 실행 경로를
사용한다. 제품·설치본·브라우저·주기·PID 소유권 검사는 유지한다. Python25개/5.810초 exit0
(28a7dc), 토큰 분기와 native 작업 정의/문법 exit0(657d69), 새 루트/이전 루트 거부 및 입력
변경2개 검사 exit0(458f9b), 실제 결과 본문 읽기4조건 exit0(bb66d5)다.
처음 이전R2 경로에서 실행한25개 결과51d835는 R3 검사 근거로 사용하지 않는다.

새 VMQA3_20261022_83be8a5a 폴더의 입력1240파일을 전수 검산했다(fec4f9).
변경 제어4개 외1235개는 기존 VM 내부 바이트를 재검산해 독립 사본으로 준비했다.
입력 검사가 하드링크를 거부하고 이전 해시 결합 증거를 이동하지 않기 위한 새 시험 입력이며,
관행적 전체 백업이 아니다. 기존 실패 루트/출력은 보존했다. 준비 검증 SHA256은
 a6c71a22c01581601224d8acd30897d8cd3a102d17cf2e701ef6cc427afb24ab이다.

09:53 KST 실제 VM 바탕화면을 확인한 뒤 동일 인증 연결의action003으로 시험을 재개했다.
결과 전수 회수는 task terminal 후에 수행하며, 본문·해시 직접 읽기로 파일 공급자 오류를 피한다.
세 조건 비교·정상 종료·저장 대조는 진행 중이며 출시HOLD·승격false·목표active를 유지한다.

### 5.258 브라우저 준비 파일 공유 잠금과 실행 경로 보완

R3 일반 권한 실행은 3탭 예비 시험을 통과했고 이미지 이벤트44개와 정상 종료를 기록했다.
독립 브라우저3개 중 client1은 Chromium이 쓰는 DevToolsActivePort를 읽다가 EBUSY로
중단됐다. 제품 설치 전이며 잔류11프로세스는 시험 job이 정리해 active0을 확인했다.
회수91파일의 정확한 집합·크기·SHA256 검산은 exit0(548279)이다. 이 강제 정리 기록을
정상 종료 PASS로 바꾸지 않는다.

포트 준비를 최대60초/50ms 간격으로 기다리며 없음·일시 공유 잠금·미완성 두 줄만
재시도하도록 보완했다. 실제 Windows 배타적 파일 잠금 재현을 포함한 Node9개 exit0
(e28f80)이다. 종료 PID·영구 권한 오류·잘못된 완성 포트/경로는 거부한다.
R4는 entry.ps1에 R3 경로를 남긴 준비 오류로 Entry path mismatch에서 종료됐다.
제품 설치와 본 측정은 시작하지 않았다. 해당 launch-result와 입력을 보존한다.

R5는 entry·guard·binding·launch의 경로 일치를 검사하고 실제 R4 오류를 음성 사례로
검출했다. 최종 경로·해시 검사, nativePS5.1 토큰 검사, Python25개/6.404초가 exit0
(02190a)이다. 브라우저 코드·검사 바이트는 Node9개 통과 당시와 같음을 검산했다.
VMQA5 새 폴더의1240파일을 전수 검산(c81ae5)하고 10:06:41 KST 같은 인증 연결로
action007을 시작했다. 설치본·보안 기능·관찰 길이·가시성·저장 종료 검증은 유지했다.
실제 결과는 아직 판정 전이며 출시HOLD·승격false·목표active를 유지한다.

### 5.259 카메라 화면 위치와 VM 방화벽 사용자 선택

R5는 두 예비 시험과 동일 후보 설치 exit0/1,867파일 검산을 완료했다. 첫 제품 화면은
카메라가 좁은 창 아래에 있어 이미지 load를60초 기다리다 중단됐다. 실제 DOM의 blob URL,
complete=false/너비0과 이미지HTTP200 1건을 확인했다. build240a의 CameraWidget에도
loading=lazy가 있다(071976). API/layout404 두 건과 원래 실패 기록은 보존한다.
본 측정은 시작하지 않았고 backend는 정상exit0, 강제 종료false/잔류0이었다.
회수168파일을 전수 검산했으며 새JPEG1개/948바이트의 사실 기록·본문·종료drain을
대조했다(d326d4). 이 부분 검증은 전체 비교나CSV 내용 검증을 대신하지 않는다.

R6는 정상 스크롤로 카메라를 화면 안에 배치하고 실제 bounding rectangle을 매 표본에
기록·검사한다. 예비 페이지도5000px 아래의lazy 이미지로 변경했다. 가시성·focus·loading
속성을 위조하지 않는다. 설치된 동일 후보를 전수 재검산해 재사용하고 설치는 반복하지 않는다.
Node10개/Python25개 exit0(dfa686, terminal aa0997), 경로/해시·native 토큰·문법exit0
(8479c0)다. 추가 네트워크 기록의 잘못된VMId 매개변수는 준비 변경 전 중단됐고,
실제Hyper-V 명령 매개변수를 확인해VM 객체 방식으로 보완했다(7a2f78).

사용자는VM 방화벽 요청에서취소대신Allow를눌렀다고알렸다. 실제창이닫힌것을확인했고,
10:20:14 KST Hyper-V 재조회에서NIC0을확인했다(071976). Codex는방화벽설정을조작하지
않았으며서버·외부네트워크연결도추가하지않았다. 해당선택과시험격리조건을별도로기록한다.
R6 준비·실행은기존인증연결을사용한다. 새본시험결과는미평가이며출시HOLD·승격false다.


### 5.260 설치 재사용 조건과 독립 창 시작 경합 보완

R6는 10:23:16 KST exit1로 끝났다. 설치된 후보를 재사용하는 본문과 달리 guard에
EXISTING_PRODUCT_INSTALLATION 거부 조건이 남아 있었다. 브라우저·제품 시작 전 실패이며,
회수 3파일의 정확한 집합·크기·해시를 독립 검산했다(65a628).
R7는 기존 R5 설치 영수증의 고정 SHA256과 설치 폴더를 확인하고, 첫 브라우저 전에
기존 1,867파일 전수 대조를 유지했다. 설치를 반복하지 않았다. 누락·변조·출력 재사용
거부를 포함한 Python32개 exit0(3b0184), 최종 경로·해시·native 토큰 검사 exit0(f20132)다.
처음 경로 검사에서 준비 action 참조가 오래된 문제는 검사 파일에서 보완한 후 재검사했다.

R7의 실제 입력 1,240파일을 검산(112ab1)하고 10:28:07 KST 시작했다. 설치본 재사용과
3탭 예비 시험은 통과했으나, 독립 창 client1이 about:blank에서 native visibility 확인
30초 제한으로 중단됐다. 다른 client0·2는 정상 준비됐고, controller exit1/잔류0,
강제 종료 false로 끝났다. 본 제품 측정은 시작하지 않았다. 이 원인을 브라우저 초기
활성화 경합으로 추론하며, 아직 실제 시험으로 확정한 원인은 아니다.

R8는 각 창이 ready가 된 뒤 다음 창을 시작한다. 모든 창의 준비가 완료된 뒤부터는
같은 시간 구간에 세 창을 함께 측정한다. visibilityState를 100ms마다 읽되 30초 제한을
유지하고 속성·포커스·보안 기능을 위조하지 않는다. 36 Python 검사 exit0(3a2b93),
10 Node 검사 및 경로·해시 검사 exit0(f3c79f), action 구문 검사 exit0(8739cb)다.
기존 인증 연결을 유지하며 원본 결과와 해시 결합 입력은 수정하지 않는다.
사용자의 Allow 선택 뒤에도 10:27:20 KST VM 네트워크 어댑터 0개를 재확인했다.
운영 서버 변경은 없고, 비교 시험 및 출시 판정은 아직 완료가 아니다.


### 5.261 한 화면 조건의 독립 검토와 첫 탭 생성 대기

R8는 두 smoke를 통과하고 one 조건을 warmup120초+측정300.2789865초 수행했다.
369개 독립 HTTP 요청 오류0, 자원표본0..84와 요청 coverage COMPLETE, backend·Chromium
정상 종료를 확인했다. 전체 R8 회수1,430파일의 정확한 집합·크기·SHA256 대조 후,
해당 조건을 독립 검토했다(e06170). observation 구간 /health p95 14.8277ms/max39.9398ms,
/api/data p95 3.2851ms/max7.7299ms다. 이미지 load899회/error0, 간격p95 349.7ms/max409.5ms다.
새 CSV1,983행·온도 관측428행·저장 JPEG340개와 종료 drain을 대조했다. fixture 기반
범위이며 물리 화면 연속성·실제 센서 변화와 학습 적합성을 입증하지 않는다.

다음 three 준비는 CDP가 연결됐으나 첫 Page가 아직 없는 상태를 바로 참조하여
expected Page or Frame 오류로 중단됐다. three 본 측정은 시작하지 않았다.
해당 브라우저 종료도90초 안에 확인되지 않아 suite job이 잔류7개를 강제 정리한 뒤0개를
확인했다. 전체 R8의 FAIL을 PASS로 바꾸지 않으며, 앞서 정상 완료한 one만 비교에 재사용한다.

R9는 첫 실제 Page를 최대60초 동안 기다리고 종료 프로세스·닫힌 Page·초기 복수 Page를
거부한다. 이전 one은 반복하지 않고 three/three_clients를 실행한다. Python36개,
Node14개 exit0(6903f9/29bd4f), 경로·해시 exit0(55329f), action 구문 exit0(b25e71)다.
새 VMQA9 입력1,240파일 검산(567868) 후 기존 인증 연결의action016을 시작했다.
출시HOLD·승격false를 유지하고 결과 회수·독립 검토 후 조건별 출처를 결합한다.

### 5.262 격리 VM 세 조건의 자료 검토 완료와 종료 확인

R9 action016은 11:07:47 KST exit0으로 종료됐고, 2,885파일을 전수 회수·검산했다.
설치된 240a49522da5d59e9e823f62612e3d4207b497a9 / 1.0.30 후보를 1,867파일
전후 대조해 재사용했다. 추가 설치·운영 서버 변경·전체 백업은 없었다.
R9의 three와 three_clients는 각각 120초 준비 뒤 300.294/300.331초 측정,
정상 저장·종료 및 강제 종료 없음/잔류0을 확인했다. 전체 R8 FAIL은 보존하고
정상 완료한 one 조건만 재사용했다. 측정 본문·공통 도우미의 동일성을 대조했다.

최초 독립 분석은 숨김 탭에도 이미지 load를 요구해 REVIEW_INCOMPLETE exit1이었다
(7961d1). 고정 commit의 useSpotViewModelEffects.ts:88과 useSpotViewModel.ts:263,455에서
숨김 시 이미지 갱신 취소·요청 중지를 확인했다(65e74a). 숨김 탭은 연속성 평가 대상에서
제외하되 전체 가시성 이력 누락·측정 중 예상 밖 상태 변경·표시 화면 load 없음은 거부한다.
초기 분석 결과를 보존하고 수정 전 회귀 3실패(exit1,6933a0), 수정 후 17통과(exit0,d5932f),
R9 독립 재분석 exit0(dc1560), R8 one 브라우저 이력 재검토 및 출처 결합 exit0(be3eb5)을
확인했다. 원시 VM 측정은 반복하지 않았다.

| 조건 | /health p95 / 최대 ms | /api/data p95 / 최대 ms | 표시 화면 이미지 load | 간격 최대 ms |
|---|---:|---:|---:|---:|
| one | 14.83 / 39.94 | 3.29 / 7.73 | 899 | 409.5 |
| three(표시 1탭·숨김 2탭) | 18.36 / 65.66 | 4.05 / 7.53 | 897 | 413.1 |
| three_clients | 29.22 / 71.65 | 20.90 / 27.91 | 894 / 888 / 891 | 457.5 / 512.9 / 478.6 |

첫·마지막·준비 요청 포함 독립 HTTP 1,107건 오류·타임아웃0, 200/500ms 진단 초과0이며
원시 요청·자원 표본 coverage는 세 조건 모두 COMPLETE다. 본 측정의 브라우저 요청 오류와
이미지 error는0이나, 시작 단계 /api/layout 404가 조건별2/6/6건 있어 전체 오류0으로
보고하지 않는다. 숨김 두 탭의 load0은 실제 가시성 이력과 제품 동작으로 설명되며
재활성화 시 복귀 속도는 이번에 측정하지 않았다.

새 CSV5,791행·온도 관측1,303건·JPEG1,081개를 대조했다. 이미지 연결 키1,081건이
관측의 서비스·poll 순번·완료 시각과 일치했고 종료 drain과 파일 본문을 검산했다.
과거2.35GB 사실 기록의 접두 바이트 보존과 새 행 검사를 구분하며 과거 전체 소비자 검사를
반복하지 않았다. 고정500°C·948바이트 JPEG 시험으로 실제 온도 변화·영상 신선도·학습 적합성은
입증하지 않는다. 같은 VM의 독립 Chromium3개는 실제PC3대의 네트워크 시험이 아니다.

action017의 11:08:53 KST 최종 읽기에서 QA 작업0·프로세스0·NIC0·비루프백IP0이다.
사용자의 Allow 선택에 따라 backend Public 인바운드 TCP/UDP 허용 규칙2개가 존재하지만
Codex는 설정을 변경하지 않았다. 향후 VM 네트워크 연결 전에 이 상태를 검토해야 한다.
VM 바탕화면도 직접 확인했고 기존 인증 연결은 11:13:11 KST 정상 해제(exit0,a837bc),
비밀번호 저장false다. VM 자체는 실행 중이며 운영 서버에는 이번 작업으로 접속하지 않았다.

상세 보고서: `Desktop/SmartFactory/VM21_20261021_83be8a5a/analysis/qa-r9/comparison-report.md`.
보고서 SHA256 `0ac1651b5045a3b06683b9bb6896d6531488272b8f8833a2ff6ef614591c3c92`,
검증 기록 `verification.json` SHA256 `8782db5d884a7eab7211774162ca55454256e28db8cebbccd7f269592e1a21cc`.
이 결과는 세 조건의 자료 검토 완료이며 정식 출시 PASS가 아니다. 목표active·출시HOLD·승격false,
실제3PC 네트워크·물리 연속성·학습 적합성 미평가를 유지한다. 같은 field120·완료한 one은
자동 반복하지 않고 남은 실제 운영 범위와 기존 미해결 gate에 필요한 검증만 준비한다.

### 5.263 목표 정합성 재점검과 누락된 화면 지표 판정

사용자가 현재 진행의 목표 정합성과 완료/미완료/목표 밖 작업을 요청하여 원래4단계,
사용자 변경 승인, 현재 계획R1–R6와 실제 완료 영수증을 다시 대조했다. 결과는
`docs/04-report/production-release-risk-validation-goal-alignment-20261022.report.md`다.
VM 환경 준비는 사용자 승인된Check의 수단이며 출시 완료 조건으로 계산하지 않는다.
완료된120분/닫힌 데이터/시작10회/VM3조건 자료 검토를 현재 요약에 반영하고,
실제3PC·현장3회 전체계약·물리 경계·과거 원인·전수데이터·정식QA의 공백을 유지했다.
설치복구matrix179/180(등록541d 종료 이미지502 1건)도 완료된 실행과 통과 여부를 구분했다.
미서명운영 지시를 반영하며 인증서·서명을 새 차단 조건으로 추가하지 않는다.

기존VM 원시 기록/회수inventory/combined-review의 해시와 내용으로 7페이지의 LCP/CLS를
재검토했다. 6페이지의초기CLS는0.5603369763–0.5931842876으로 기존0.25를 초과했고,
1페이지는최종hide시 명시적인0을 보고했다. LCP432–1484ms다. 최대값을 여러번 보고한
값을 합산하지 않으며 첫보고·초기화면값도 제외하지 않는다. raw shift항목/영향요소좌표와
scroll시각이 없으므로 제품/스크롤/비동기배치의 원인은UNCONFIRMED다.

봉인된web-vitals2.1.4 SHA2ad3e1ebf36f4d5375c097486e514befc0294cf035eb492965b32a3274e6fed0가
현재동일버전배포파일과 바이트동일함을 확인했다. 실제라이브러리의 합성observer시험5개가
exit0(d5ad24), 분석기경계검사8개가exit0(78b7a0), 원시자료재분석exit0(ebe554)이다.
이 라이브러리는후속작은session이기존최대CLS를넘지않으면reportAllChanges=true여도
보고하지않는다. 측정중양의새보고0을 ‘배치이동없음’으로 확대하지 않는다.
분석결과는`VM21_20261021_83be8a5a/analysis/qa-vitals-20261022/audit-result.json`,
SHA f70a9db62268e17dfbee966b7c922e22f537e3104c4f266b68eac1881ee2f28b다.

기존GATE22 서버읽기는재실행없이검산했다. SSHexit0,CLIXMLstderr는progress10개이며,
host콘솔cp949출력오류exit1은결과저장후발생했다. DESKTOP-CIIT7LK/user/admin,
승인된SSHsource192.168.0.115→192.168.0.7,후보240a/nativePID3104와세대가결합됐다.
약28.18초의6표본에는loopback127.0.0.1만보였지만 실제3PC부재/개수를증명하지않는다.
서버/개발PCwallclock정렬은미확인으로교차시계지연을계산하지않았고,운영화면전면확인도
미완료로유지했다.이번분석은서버/VM재실행·설정변경·설치·백업을하지않았다.
새시험준비를확대하지않고목표대조를먼저완료했다. 목표active/출시HOLD/승격false다.

### 5.264 등록 롤백본 종료 오류의 코드·동일 guest 시간선 대조

R6의 남은 matrix 오류를 원본 재실행 없이 좁혀 확인했다. 봉인된 입력17개와 Git 소스6개를
대조한 분석은 exit0(87da3c)이며 결과 SHA256은
`6571e50d33312d3df7da61574a2cffc3eed10267b0fa39411e2369a9d6265ba1`이다.
상세는 [등록 롤백본 종료 오류](../04-report/production-release-risk-validation-rollback-shutdown-attribution-20261022.report.md)다.

I8의 main6876/backend1600·health·종료 영수증은 모두541d/1.0.26으로 연결됐다.
guest backend.shutdown-start16:05:09.615UTC 뒤285.624ms에 shutdown/502가 발생하고
16:05:10.133UTC에 강제 종료 없이 backend exit0을 기록했다. driver의 이미지 요청 허용 플래그가
종료 시 false가 된 뒤 두 방어 지점에서 발생시키는 내부 예외를 API가502로 반환한다.
요청한 개별 클라이언트나 두 지점 중 실제 분기는 미확정이다. 이미지 영수증은105enqueue/105written,
queue/inflight/unfinished/failure/drop0이다. 이502를 장비 통신 장애나 저장 이미지 손실로 환산하지 않는다.

현재 clean후보240a에는10월13일 보완한 renderer 준비 대기가 있고, I4/I5의 실제 기록도
renderer 준비 완료→backend 종료·각실행 신규 오류0이다. 외부브라우저/다른PC는 이Electron연결의
대상이 아니다. 기존후보를같은이유로재빌드하거나같은종료시험을반복하지않는다.
matrix179/180·기존FAIL은보존하며 구버전복귀시종료제약의처리결정과전체QA결합은남는다.
분석기의혼합로그/소스변수명가정으로초기2회exit1이었고 실제형식을반영한최종분석만exit0이다.
제품코드/서버/설치본/등록롤백기준변경없음,목표active·출시HOLD·승격false다.

### 5.265 초기 로딩 카드 크기 미확보의 브라우저 재현과 소스 수정

이전차례는R6출처확인/상태정리로PROGRESS였다. 이번에는R2의남은CLS를같은240a패키지의
프런트엔드51파일과보존된시험응답으로개발PC에서짧게재현했다. 원본/회수해시대조를선행했고
제품backend/장비/서버/VM은실행하지않았다. 새headless브라우저와loopback시험서버만사용했다.

624×549에서첫데이터후KPI영역140→786px확장과아래위젯의이동을확인했다. 원시source/좌표와
명령시각으로초기재현의큰이동이스크롤전에발생함을확인했고,800msdata지연의무스크롤조건에서도
CLS0.569707로재현했다. 원래VM에는source가없어과거모든개별이동의직접인과증명은유지할수없다.
원인은대기일반div에완성카드의responsive크기규칙이적용되지않는것이다. 5위젯과native지연대기에
기존card클래스/aria-busy를적용했다. 입력값/완성디자인/수집주기/장비설정은변경없음.

수정전회귀exit1(ac0f80),수정후동일조건재현exit0(b5048b):작은무스크롤CLS0.569707→0,
작은카메라스크롤0.893620→0.032847,1280×800무스크롤0.009020→0.009020이다.
grid이동원시항목0/pageerror0,기존목표0.1이하를확인했다. headless5초/합성일부응답이며
실제운영성능/3PC/무손실/설치본QA의PASS가아니다. 예상layout404와오래된시험값의STALE은보존했다.
frontend별도출력buildexit0(6cf100),typecheck0(a9f2a3),lint0(838d32),test0(eb0b26):
Node9/Vitest442검사42파일통과. zod주석경고2건보존. 상세보고와검산sha는
`production-release-risk-validation-layout-loading-20261022.report.md` 및
`911c687c6422ea390fcb83c60f6cc2ce399692bdb6100edf36febd965775e9e4`다.
이번6파일은미커밋/미패키지/서버미적용이므로기존clean240a설치본에포함된것으로해석하지않는다.
다음은clean후보결합과영향받는화면/패키지검사이며기존동일120분·VM환경준비를자동반복하지않는다.

### 5.266 로딩 배치 수정의 clean 1.0.31 패키지 검증

2026-10-22: 별도 작업본에서 검증된 화면6파일과 버전 식별/검사만 결합하여
`a7e5149b718f56d7dfa75df73bfba4a21d16a758`을 만들었다. 전체 health exit0
(backend962pass/비공개fixture1skip, Electron103, frontend442+9, 의존성15), 잠금wheel40·clean 유지다.
installer SHA `a10a59aa544a7bfa60e40778f05b89e3cc5be6da8ca284f94f740b6e6ae4a1dc`,
164158074bytes/NotSigned. NSIS 추출1867파일·화면51파일·출처3624개를 검산했다.
추출backend health5건·정상종료0, 추출화면3조건 회귀0이며 실행 후 payload 전수 해시도 동일하다.
각 소유job의 잔류0/강제종료없음. 작은화면 CLS0.569707→0, 카메라스크롤0.893620→0.032847,
넓은화면0.009020 유지다. Chromium은 원시값153.0.8010.12로 이전 보고서148 표기를 정정한다.
PyInstaller tzdata hidden-import 경고는 남는다. 새 설치본 실제 설치/복구·Electron·현장 QA 미완료,
서버 미변경·전체백업없음·출시HOLD/승격false. C31REL_20261022_a7e5149b/candidate-review.json과
production-release-risk-validation-layout-candidate-20261022.report.md에 근거·범위·다음 작업을 연결했다.

### 5.267 기존 guard가 있을 때 불필요한 OS 조회를 기다리던 경로 수정

2026-10-23: 별도 로컬 회귀에서 여유 guard가 있는데도 재사용 대상 포트의 OS 조회가 6초
지연되거나 오류를 내면 acquire가 실패함을 수정 전 exit1로 확인했다. 기존 guard를 lock 안에서
먼저 선택하도록 수정했다. OS 조회가 필요한 포트의 77초 격리·점유 상태·배타적 rebind,
5초 양수 deadline과 동시 lease/종료 계약은 유지한다. lock 지연 후 deadline 초과도 거부한다.

포트/TCP30검사 exit0, HTTP transport/정상 종료 통합37검사 exit0, Ruff exit0,
대상 모듈 mypy exit0이다. native Windows TIME_WAIT 검사를 실제 실행했고 통합 시험의
정상/복구 조건 CSV39/52행·종료0·terminal drain을 확인했다. PLC는 fake socket,
SPOT는 loopback이며 asyncio slow-task 원문은 로그에 보존했다.

`C:/Users/user/Desktop/SmartFactory/PORTFAST_20261023_a981e3c7/review.md`와 stage.json에
소스·시험 출력·수정 전 실패를 결합한다. canonical 작업본의 관련 검사이며 새 clean 설치본,
VM/현장 검증 또는 과거 오류 원인 확정은 아니다. 이번 변경은 미커밋·미패키지·서버 미적용이다.
10월19일 transport 오류 지연 원인과10월9일 최초 timeout은 구분해 미확정으로 유지한다.
전체 출시 HOLD이며 다음은 C31 출처와 이번 변경만 결합한 clean 후보의 영향 검증 준비다.

### 5.268 포트 할당 개선의 clean 1.0.32 후보 검증

2026-10-23: C31/a7e5149b에서 제품·회귀2파일과 버전6파일만 결합한 clean
`cd46692ac9c551080c57d8168fa9ea5abd530206`을 만들었다. 새 clone의 잠금 wheel40개,
전체 health exit0(backend964pass/비공개F01fixture1skip, Electron103, 화면442+9, 의존성15),
전후 clean을 확인했다. installer164158258bytes/NotSigned, SHA
`558658cf02d59cb6b66468e4e191c447efdc7cc24518b5a69647cc2409eb232f`다.

NSIS 추출1867파일·화면51파일과 두 포함 위치, 허용된 빌드 출처3624개를 대조했다.
추출 backend의 loopback health5건과 정상 종료0·잔류0을 확인했다. 각 실행 native exit0,
강제 종료없음이며 tzdata 경고/비공개fixture skip은 보존한다. 초기 도우미 준비의 경로 필드
형식 오류는 실행 전 수정·검사했고 실패 기록을 남겼다.

이번 것은 새 후보의 로컬 패키지 검사다. 실제 설치/복구·Electron·포트 전체 순환 성능·현장 QA는
미완료이며 서버 미변경·전체 백업없음·출시HOLD다. 상세 범위와 후속 적용 조건은
[C32 후보 보고서](../04-report/production-release-risk-validation-port-candidate-20261023.report.md)와
`C32REL_20261023_eac4b615/candidate-review.json`에 연결한다. C31 현장 증거를 C32 PASS로 바꾸지 않는다.

### 5.269 C32 동일 설치본의 격리 VM 설치·복구·실제 포트 순환

2026-10-23: 기존 오프라인 VM의 SFLQA 인증·바탕화면 로그인 후 동일 C32 설치본을 검증했다.
949입력 파일을 검산하고 7회 설치·2회 제거, 6회 Electron/수집/정상 종료를 수행했다.
실제 worker 종료0, 1,040.109초, 소유 Job135프로세스의 강제 종료·잔류0이다.
3,193파일/39,516,484bytes를 회수·해시 대조한 독립 검산249항목과 CSV6/이미지6검사가 exit0이다.
CSV2,765행·자체 관측230건·이미지633개와 이전 자료·기본 AppData/프로필 보존을 확인했다.

C32 단일 실행에서 native HTTP 성공1,643건과 fixture peer1,643건, 768포트 각각2회 이상을
관찰했다. 최소 재사용82.093초, 전송/바인딩/소진/격리 위반0이다. 총 요청 수나 시간만으로
포트 순환을 통과 처리하지 않았다. 이 실행의329.377초는 운영 지연 기준이 아니다.

준비 중 요청 실패35건은 유지하며 운영 준비 이후에는 관찰된 실패0이다. C26의 기존 종료
이미지502/shutdown1건은 그대로 제한사항이다. 정적 합성 JPEG라 실제 영상 연속성 증거가 아니다.
첫 독립 검산의 C26 목록 경로 오류(exit1)는 실제 전송 계획·해시로 수정하고 R2만 exit0으로
기록했다. 원시 자료·최초 실패를 보존했고 VM 시험은 반복하지 않았다.

[C32 VM 보고서](../04-report/production-release-risk-validation-c32-vm-matrix-20261023.report.md)와
`C32VM_20261023_cd46692a_R2/matrix-review-r2/review.json`에 근거를 결합한다.
현재는 새 C32의 격리 검증 진전이며 현장 미적용·전체 출시HOLD다. 다음은 동일 설치본의
변경 영향에 맞춘 현장 검증 준비다. 물리·과거 데이터/timeout/drop 미확정 항목은 유지한다.

### 5.270 C32 현장 도우미·전달과 현재 C31 정상 종료 준비

2026-10-23: C32 exact identity를 지원하는 도우미 clean commit `bb6fbc807ecea4182efe90b369f1b110436b14eb`를
검증했다. Python167·설정13 및 C32 하위7조건, 설치151·종료20·보존38·캡처15 checks와
health 진입9 cases가 각 기대 결과를 만족했다. frozen 도우미6회 직접 호출도 통과했다.
첫 캡처의 CRLF/LF 고정 해시 오류는 보존하고 실제 배포 LF 바이트로 수정한 R2만 재검사했다.

동일 C32 설치본 SHA `558658cf02d59cb6b66468e4e191c447efdc7cc24518b5a69647cc2409eb232f`를
포함한 26파일/206,618,292bytes를 승인 SSH로 새 FIELD32 폴더까지 전달·전수 검산했다.
서버 library/describe exit0·도우미 잔류0이며 현재 C31 실행 세대는 유지됐다.
종료 입력4파일/12,740bytes를 현재 logger·CSV·설정에 연결하고 두 서버 ValidateOnly exit0을 확인했다.
두 실행기는 준비만 했고 실제 관찰·앱 종료·설치·설정 변경·새 전체 백업은 아직 없다.

12:47 자동 초기화된 작업 정보에 대해 사용자는 생산 중 아님으로 답했다. 공란을 유지한다.
화면 도구의 Chrome 주소 확인 오류로 UI·전면 표시는 미확인이다. 운영자가 X 클릭 가능한 시점에
두 관찰기의 실제 준비를 확인한 뒤 정상 종료·원본 검산을 진행한다. 준비 결과는 설치 통과가 아니다.
[C32 현장 준비 보고서](../04-report/production-release-risk-validation-c32-field-preparation-20261023.report.md)에
실제 출처·결과·제한을 연결하며 C31 증거와 등록 복귀 기준, 전체 출시 HOLD를 유지한다.

### 5.271 C32 적용 전 종료 관찰 시간 초과와 C31 재시작

2026-10-23 14:00 KST: 사용자의 X 종료는 최초 두 관찰기의 450초 대기가 끝난 뒤에 발생했다.
보호 실행기의 exit 1·timeout 실패와 원시 영수증을 보존했다. 실제 앱·포트 부재,
CSV finalized/shutdown, Electron의 backend exit 0·forced=false 기록은 확인했지만,
전체 프로세스 native 종료 증거는 회수할 수 없어 정상 종료 관찰 PASS와 설치 선행조건으로 쓰지 않았다.

이전 CSV 199,442행의 전체 열·logger·sequence 1~199,442와 최종 저장 번호는 별도로 검산했다(exit 0).
stale 93행 등 품질 상태는 그대로 남겼고 이미지/fact 전체 QA로 확대 해석하지 않았다.
기존 C31 도우미를 바이트 변경 없이 사용해 일반 사용자 세션에서 재시작했다(exit 0).
현재 설정 해시는 불변, 새 logger `0b9fa18a-7432-49ca-823b-51cce309bf0d`의 REAL/Running을 확인했다.

새 `F32CLOSE_20261023_cd46692a_R2` 요청의 서버 4파일 해시와 두 ValidateOnly exit 0을 확인하고
preservation 관찰을 시작했다. 새 준비 완료 후 정상 X 시점을 다시 안내한다.
관찰 실패를 덮어쓰지 않고 C32 설치·정식 출시 HOLD를 유지한다.
상세 근거는 [현장 보고서](../04-report/production-release-risk-validation-c32-field-preparation-20261023.report.md)의
14시 종료 관찰 항목과 `timeout-review`, `previous-csv-review`, `current-c31-restart` 기록에 연결한다.

14:27 이후 R2도 X 종료 없이 대기 제한에 도달했다. 두 실제 exit 1, 소유 Job 잔류 0을 확인했고
외부 SHA256에 결합한 원문 실패 결과를 회수했다. 14:28 서버는 동일 C31/REAL/Running이다.
현재 관찰기 0·C32 설치 미실행이며 자동 재시도하지 않는다. Chrome 창 열거는 가능하지만
상태 캡처는 URL 확인 오류로 차단돼 정상 X를 직접 수행할 수 없었다.
후속 조건은 새 운영자 조작 가능 시점 또는 원격 UI 복구다. 기존 실패·원시 자료를 유지하고
상태 파일의 오래된 ‘관찰기 실행 중’을 실제 terminal 상태로 갱신했다.
