# History/API P2 진행 기록

> **2026-09-23 서버 설치 검증 완료:** P2 병합본 `d254871`의 미서명 NSIS 설치와
> 실제 120분 관찰·정상 종료·원본 재설치·콘솔 종료 후 수집 지속 확인을 완료했다.
> 실행/회수 42항목과 원문 검사 16항목이 통과했다. 실제 작업정보 일치도 사용자가 확인했다.
> [120분 현장 결과](docs/V2/05_운영_배포/temperature_p2_nsis_120min_trial_20260923.md)를 참조한다.
> 현재 서버는 원본으로 복귀했으며 정식 운영 승격은 별도다. 아래 이전 상태는 당시 기록이다.

2026-09-22. 승인 범위: 새 브랜치 생성, P2 재현·최소 수정·로컬 검증.
commit/push/PR/merge, 후보 빌드·설치·운영 적용은 별도 승인 대상이다.

## 시작 기준

- 브랜치: `codex/temperature-history-p2-20260922`.
- 기준: PR #193 병합 `1d4ec21d8b88ce6298742bc4cf21b75884e21b1a`.
- 기존 브랜치 HEAD와 병합 tree가 같음을 확인하고 원격 master를 fetch하여 새 브랜치를 생성했다.
- AGENTS·README·package/CI·기존 history API, 서비스/프론트 계약을 먼저 확인했다.
- staged/unstaged 변경 없음. 기존 untracked 파일 명세/해시는 `artifacts/temperature-history-p2/baseline.json`에 보존했다.
- Downloads의 예전 L1 경로 대신 보존 사본 `artifacts/temperature-worker-lifecycle-l1/input/DEFERRED_HISTORY_API_P2.md`를 읽었다.
  문서의 P2는 감사의 격리 경계조건이며 CSV/fact 유실 또는 현장 프론트 장애의 증거가 아니다.

## 실패 재현

실제 PLCService `_record_history_sample`/producer/consumer loop, FastAPI route, 프론트 SeriesBuffer를 호출했다.
임시 runtime 경로, 모의 장비 경계, 독립 clock과 Event를 사용했고 실제 장비·OS 시각을 변경하지 않았다.

- Backend before: 10 test methods, 10 assertion failures / 4 errors. subTest 실패를 별도 결함 수로 세지 않는다.
  동일 UTC `[1,2]`가 `[2]`로 바뀌고, UTC −60초 후 cursor 조회가 새 표본을 반환하지 않는 것을 확인했다.
  일부 오류는 아직 없는 cursor/identity 인터페이스에 대한 시험이며 별도 기존 장애로 해석하지 않는다.
- 프론트 before: 3 tests fail. 동일 UTC 순번 2 누락, 새 generation 동일 시각 표본 누락, cursor 조회 메서드 부재.
- 원문: `before.txt/.json`, `frontend-before.txt/.json`.

## 최소 변경

- history instance + lock 내부 증가 sequence를 API identity로 사용한다. `/api/data`와 history가 같은 identity를 공유한다.
- UTC·Time 원문은 그대로 두고, 메모리 history 보존 1시간만 monotonic 경과시간으로 판정한다. 수량 제한 36,000은 유지한다.
- 선택 cursor는 순번 순서 페이지를 반환한다. 이전 instance·누락된 보존 범위·미래 순번은 명시적 reset을 반환한다.
- cursor 없는 `since_ms` 필터/최신 limit 계약을 보존하고 limit 생략도 truncated에 표시한다.
- 프론트는 같은 identity만 중복 제거한다. UTC 역행·같은 UTC 표본, 복귀 페이지 조회, legacy→cursor 전환,
  새 instance, 늦은 이전 응답, unmount, 조회 실패·무진전·4페이지 예산을 처리한다.
- API identity는 숫자 차트 항목에서 제외한다. 표시 레이아웃과 CSV/fact 컬럼·버전은 바꾸지 않는다.

## 검증 중 보완

- 1시간 정확한 경계에서 float 뺄셈 오차로 표본이 일찍 제거되는 시험 실패를 확인했다.
  `recorded_monotonic + max_age < now`로 경계 비교를 바꿔 정확한 경계와 1ms 초과를 구분했다.
- 첫 전체 health는 frontend typecheck에서 identity 필드가 `TimeSeriesKey`에 포함되는 오류로 중단됐다.
  명시적 제외 목록을 보완했다. 첫 wrapper는 shell 인자 확장 때문에 exit 0을 잘못 보고했으므로 **실패**로 기록한다.
  원문/영수증을 수정하지 않고 `health-wrapper-assessment.json`에 원인과 보완을 남겼다.
  최종 health는 native 종료코드를 전달하는 `cmd.exe /d /c npm.cmd run health`로 실행한다.
- 집중 시험 1차: backend history/API/C1/L1 56 pass; 프론트 buffer/hook/transport 31 pass.
  이후 동시 recorder와 새 PLCService instance 회귀를 추가했다. 최종 수치는 결과 보고서에 실제 실행 기준으로 기록한다.

## 완료 판정

최종 실행·명령·pass/fail/skip·검토 결과는 `HISTORY_API_RESULT_P2.md`와 실행 행렬에 기록한다.
기존 G1~G5/T1~T3/C1~C3/L1 완료·현장 증거를 수정하거나 P2 시험 결과로 대체하지 않는다.

## 병합본 패키지·현장 후속 결과

2026-09-22 후속 승인으로 PR #194 병합본 `d254871`의 미서명 내부 검증본을 준비하고,
승인된 10분 현장 시험·정상 종료·원본 복귀·콘솔 종료 후 수집 확인을 완료했다.
이전에 기록한 코드 완료 시점의 미게시/미실행 상태와 구분한다.
[후속 현장 결과](docs/V2/05_운영_배포/temperature_p2_ten_minute_trial_20260922.md)에
실제 CSV/fact·P2 API 표본 범위·종료·복귀 근거와 미검증 범위를 연결했다.

이번 후속 정리는 문서 4개만 수정/추가하며 제품 코드·패키지를 변경하지 않는다.
운영 준비에서 현재 signing 환경 미구성과 설치/upgrade 미검증을 확인했다.
문서 작성 단계에서 commit/push/새 PR/merge·서명 workflow 실행·서버 설치·운영 전환은 하지 않았다.

## 2026-09-22 미서명 내부 설치 검증

승인된 Sandbox 활성화와 사용자 재부팅 후, 별도 Windows guest에서 실제 NSIS 설치·upgrade·재시작·
원본 재설치를 수행했다. 4세대 실제 앱 수집·저장·정상 종료와 합성 데이터 보존을 확인했다.
최종 73 pass / 0 fail, 후보 production CSV validator 2회 종료 0이다.
[설치 검증 결과](docs/V2/05_운영_배포/temperature_p2_nsis_installation_20260922.md)에 원문 위치·도우미 보완·fact schema 1.3.0↔1.4.0의
보관본/append 검산을 기록한다. 제품 코드·바이너리를 바꾸지 않았고 서버 설치·정식 운영 승격·Git 게시는 미실행이다.
