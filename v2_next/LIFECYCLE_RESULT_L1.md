# RealPLC worker 소유권 L1 결과

2026-09-21 코드 보완, 2026-09-22 요구사항 재대조 완료. **L1 로컬 코드·합성 production 경로 검증 완료.**
현장 검증·설치·운영 승격을 뜻하지 않는다. history/API P2는 보류한다.

기준 및 현재 HEAD는 `10821534b2e9b54f6be6494cafb4b7ee43d45395`, 브랜치는
`codex/temperature-remediation-20260909`다. 현재 결과는 미커밋 local diff이며 staged 변경은 없다.
commit/push/PR 변경/merge, 후보 빌드·설치·배포, 실제 PLC/SPOT 접속, 운영 설정·데이터·OS 시각 변경은 수행하지 않았다.

## 실제 재현과 최종 동작

| 조건 | 수정 전 실제 production 시험 | 수정 후 |
| --- | --- | --- |
| 내부 SPOT/Extruder/LS 한 worker만 지연 | 각 역할에서 service stop=True, old worker alive=True, owned=False | stop=False, old 객체와 stop 신호/소켓 보존 |
| 미완료 상태에서 service/direct connect/_start_workers | 기존 목록 삭제·공유 Event clear가 가능한 코드 경로 | Event clear·소켓 재연결·새 thread 생성 이전 거부 |
| old worker 지연 해제 | 첨부 감사는 다음 주기/중복을 보고했으나 이번 before는 첫 실패 assertion에서 종료 | old 실제 종료, old 추가 주기 0; 반복 close/stop 확인 후 명시 start에서 역할별 새 worker 1개 |
| 부분 thread 생성/시작 실패 | 첫 before fixture 일부는 기존 일괄 생성 순서 때문에 setup 기대에서 실패 | 실제 시작한 객체 보존, stop 신호, 미완료 gate; unstarted 객체 join 안 함 |
| 늦은 socket 생성 / socket.close 실패 | 독립 검토에서 정리/게시 경합 확인 | live worker가 있으면 자원 정리 유보; 늦은 소켓/실패 소켓을 재확인 close에서 정리 |

장비 읽기·socket transport·임시 파일·제어 Event와 해당 시험의 thread factory만 대체했다.
RealPLCDriver/PLCService의 connect/start/stop/close, 실제 worker loop·snapshot·read_data를 실행했다.
SPOT은 RealPLC의 snapshot 전달 worker이며 별도 asyncio HTTP polling task가 아니다.
합성 재현을 실제 현장 장애, HTTP stream 중복 또는 과거 CSV 유실로 표현하지 않는다.

## 최소 변경과 호출 계약

| 파일 | 변경 |
| --- | --- |
| `backend/FacilityData/drivers/real_plc.py` | 제어 lifecycle RLock, alive 참조 보존, close bool, 정리 미완료 gate, 부분 시작 실패 보존, config 적용 직렬화 |
| `backend/FacilityData/service.py` | service 두 thread와 driver 종료 결과 결합, driver gate 이후 Event clear, 부분 시작 cleanup, config/종료 직렬화 |
| `backend/FacilityData/drivers/base.py` | close의 명시적 bool 계약 문서화 |
| `backend/FacilityData/drivers/mock_plc.py`, `csv_replay.py` | 비동기 worker가 없는 실제 구현은 정리 후 True 반환 |
| `backend/app.py` | reconnect API가 stop=False일 때 start하지 않고 기존 오류 경로로 반환 |
| `backend/tests/test_temperature_worker_lifecycle.py` | 신규 13개 production lifecycle 시험 및 역할별 subcase (9/22 보강 포함) |
| `backend/tests/test_temperature_clock_service.py` | C1 합성 driver 3개의 close fixture를 명시 bool 계약에 맞춤; assertion 유지 |
| `.gitignore` | 신규 lifecycle 시험의 상위 ignore 예외 |
| L1 진행·결과·실행 행렬 | 현재 실행과 과거 증거, 완료 범위 구분 |

`connect()`의 False는 기존처럼 PLC가 오프라인이라는 뜻이다. 내부 worker의 자동 retry는 유지하며,
lifecycle 재시작 거부는 RuntimeError로 구분한다. 기존 void close를 무조건 성공/실패로 해석하는
adapter를 넣지 않고 Base와 실제 Mock/CSV 구현을 함께 명시화했다. close 결과를 무시하던 직접 호출자는
그대로 호출할 수 있고, 서비스는 True일 때만 종료 완료로 판단한다.

lock 순서는 service lifecycle -> driver lifecycle이다. worker는 driver lifecycle lock을 취득하지 않는다.
join 중 snapshot/state/config lock을 새로 보유하지 않는다. 기존 서비스 thread 각 1초와 driver worker 각 1초
join 예산을 유지한다. 지연된 I/O가 같은 세대의 snapshot을 마무리하는 것은 허용하되,
실제 종료·자원 정리 확인 전 새 세대가 시작되지 않아 다음 세대 상태를 덮어쓸 수 없다.

상위 lifespan/control shutdown은 service bool을 기존 경로로 소비한다. HTTP poll task, fact queue/writer,
image writer, CSV logger의 별도 drain/종료 성공 조건은 그대로다.

## 이번 소스의 검증 결과

Windows, Python 3.12.6, 저장소 backend venv, Windows PowerShell 5.1을 사용했다.
실행별 APPDATA/config는 새 evidence 하위에 격리했다. 전체 health의 backend runner는 추가로 기존
`.tmp_test_appdata`를 사용하며 `V2_MODE=MOCK`다. 신규 시험의 socket factory는 모두 가짜 transport다.
실행 명령 전체·cwd·환경·시작/종료·종료코드·로그 SHA와 검증 소스 SHA는 artifacts의 JSON에 있다.

| 검사 | 실제 결과 | 근거 |
| --- | --- | --- |
| L1 신규 12개 + C1 7개 | r4에서 19 pass; 뒤의 미완료 flag 보완은 아래 최신 실행에 포함 | `lifecycle-after-r4.txt/.json` |
| L1/G1~G5/T1~T3/C1~C3/종료·closeout | 131 pass, 0 fail/skip, 65.222초, exit 0 | `targeted-final.txt/.json`, source manifest |
| 전체 backend | 830 pass, 0 fail/skip, 175.249초 | `health-final.txt/.json` |
| Electron / frontend 보조 Node | 94 pass / 9 pass, fail/skip 0 | 같은 health 원문 |
| frontend Vitest | 39파일 291 pass | 같은 health 원문 |
| frontend typecheck/lint, backend Ruff/mypy | 모두 pass; Ruff E9/F821, 설정된 mypy 8 source files | 같은 health 원문 |
| NSIS operational-ready/startup trace/closeout/signature/workflow QA selftest | 5개 모두 pass | 같은 health 원문 |
| 전체 `npm run health` | exit 0, 23:47:09~23:51:48 KST | `health-final.json` |

전체 backend에는 기존 로컬 보충 17개가 포함되며 비공개 F01 fixture도 실제 실행했다.
이전 818개 결과를 복사하지 않았다. GitHub CI/후보 빌드는 이번 목표에서 실행하지 않았다.
설정된 mypy 검사 8개가 lifecycle 변경 파일 전체의 엄격한 typecheck를 뜻하지는 않는다.

첫 before는 3개 method/6개 실패 subcase다. 역할별 3개는 stop의 실제 오판 재현,
1개는 기존 close=None 계약 확인, 부분 생성 fixture 2개는 기존 생성 순서에서의 진입 대기 실패다.
후자의 2개를 추가 제품 결함 수로 세지 않는다. r2/r3 오류는 app import 시점 때문에 임시 로그 파일이
열려 있던 fixture 정리 문제이며 import 위치를 수정했다. 원문은 보존하고 assertion을 약화하지 않았다.

## 독립 검토와 완료 대조

읽기 전용 독립 검토를 수행했고 소켓 게시/정리 경합과 config/stop 경합을 보완했다.
최종 판정은 Approve, 남은 blocker 없음이다. 검토자는 131개 결과와 현재 소스 9개 SHA를 확인했고,
주 작업자가 전체 health exit 0과 최종 산출물을 확인했다. 상세는 `INDEPENDENT_REVIEW.md`에 있다.

첨부 12항목의 실제 테스트 함수·명령·결과·근거는 `LIFECYCLE_REGRESSION_MATRIX_L1.json`에 대응한다.
초기 검토의 직접 `_start_workers` 부분 실패→모든 old worker의 늦은 종료 조합은
2026-09-22에 독립 회귀시험을 추가하여 확인했다. 상세는 아래 재대조 기록에 있다.
유한 합성 thread 일정에 대한 시험이며 가능한 모든 scheduler interleaving의 정형 증명은 아니다.

## 위험·관측·복귀·범위

위험도 높음: 종료 성공과 재시작 소유권에 영향을 준다. 미종료 worker나 소켓 정리 실패는 경고와 False로
드러나며 reconnect API는 기존 HTTP 500 경로로 실패한다. 정상 실행 중 중복 start는 멱등적이다.

동기 I/O 강제 중단을 보장하지 않는다. worker가 계속 정체하면 소켓도 소유 상태로 남고 재시작은 차단된다.
I/O가 실제로 끝난 뒤 close/stop을 다시 호출해 자원 정리를 확인하고 명시적으로 start해야 한다.
자동 재시작·무한 join·강제 thread/process 종료는 없다. 이것이 미완료 상태의 운영상 실패 형태다.

CSV/fact schema·metadata 의미·저장 형식 변경과 migration은 없다. TTL/source proof/duration/phase·metadata
gate/sentinel/startup key/queue·drain·gap/comparator/attestation/async_fact_only는 그대로 유지한다.
코드 복귀 단위는 이번 L1 diff와 시작 HEAD `1082153`이다. 운영을 변경하지 않아 운영 복귀는 실행하지 않았다.

실제 장비·설치·장시간·자정 시험은 범위 밖으로 미실행이다. history cursor/since_ms/UI P2는 보류이며
구현 또는 통과로 표시하지 않는다. 기존 G/T/C 보고서 9개와 기존 untracked 34개를 보존한다.

검토 묶음은 `artifacts/temperature-worker-lifecycle-l1/`의 `FILES.json`, `NEW_FILES.json`,
`full.patch`, `review-files/`, `EVIDENCE_SHA256.json`, `COMPLETION_AUDIT.json`이다.
다음 조치는 이 로컬 diff 검토이며 Git 게시·현장 시험·운영 승격은 자동 진행하지 않는다.

## 2026-09-22 요구사항 재대조

L1-A/B/C와 첨부 12항목을 현재 구현에 다시 대조했다. 미반영 production 결함은 발견하지 않았다.
service cleanup을 거치지 않는 직접 `_start_workers` 부분 실패 시험이 빠져 있어 생성 실패와
시작 실패 2 subcase를 추가했다. old worker가 살아 있을 때와 모두 종료된 뒤에도 명시 close 전에는
Event clear·socket 연결·thread 생성이 늘지 않고 old 실행 주기는 1회로 유지된다.
명시 close/stop 확인 후 새 세대의 start/stop도 성공한다. production 코드는 이전 검증 SHA와 동일하다.

| 최신 검사 | 실제 결과 |
| --- | --- |
| 추가 직접 진입 시험 | 1 method, 2 subcase, pass, exit 0 |
| L1/G/T/C 및 종료·closeout | 132 pass, 0 fail/skip, 63.279초, exit 0 |
| 전체 backend | 831 pass, 0 fail/skip, 173.551초 |
| Electron / frontend | 94 / 291+9 pass |
| lint/typecheck·PowerShell QA 5개·전체 health | 모두 pass, exit 0 |
| 읽기 전용 독립 재검토 | Approve, 시험 공백 해소, 추가 blocker 없음 |

실행 환경과 검사 범위의 한계는 앞 절과 같다. 실제 명령·환경·시각·종료코드·source/log SHA는
`artifacts/temperature-worker-lifecycle-l1/recheck-20260922/`에 있다. 이전 health/backend 830 결과를 이번 831 결과로 소급 수정하지 않았다.
이전 57개 evidence 파일과 기존 43개 보존 대상의 해시는 그대로다. 최신 전체 diff·신규 파일 명세·해시는
이 재검증 폴더의 `full.patch`, `FILES.json`, `NEW_FILES.json`, `EVIDENCE_SHA256.json`에 별도로 제출한다.
신규 시험은 Git ignore 예외가 적용되어 검토 대상 untracked 파일로 보인다. staged 변경은 없다.

L1 로컬 코드·검증 목표를 완료하고 여기서 종료한다. Git 게시·PR 변경·merge·후보 빌드·설치·배포·실장비
접속은 수행하지 않았으며 P2로 진행하지 않는다. 현장 검증 또는 운영 승격으로 해석하지 않는다.
