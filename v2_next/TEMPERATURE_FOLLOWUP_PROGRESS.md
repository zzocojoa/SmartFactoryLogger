# Temperature 후속 보완 진행

시작: 2026-09-21, `codex/temperature-remediation-20260909`,
`bf428fbe933ef5c52f1e6dd43c90058b5abd6a57`.

T1 → T2 → T3 순서로 production 경로 실패 재현, 최소 수정, 회귀 검증을 수행했다.
최종 판정은 로컬 코드 보완·검증 완료다. 정적 감사의 세 경계조건을 현장 장애로 단정하지 않는다.
기존 G1~G5 및 7시간 후보 증거는 이전 버전의 기록으로 보존한다.

- T1: Count/Speed/Press 필수 수집 완전성과 부분 응답의 오류 보존. 완료.
- T2: T1 source proof를 이용한 자동 metadata/runtime/context 변경 차단. 완료.
- T3: polling/worker 주기를 monotonic으로 전환. 완료.

실장비·운영 데이터·설정·OS 시각을 변경하지 않는다. 로컬 임시 경로와 모의 장비만 사용한다.
commit/push/PR 변경/merge/빌드/설치/배포는 이번 목표에 포함하지 않는다.

초기 작업 트리와 기존 untracked 파일 해시는
`artifacts/temperature-followup-t1-t3/start-state.json`에 보존했다.
첨부의 21개 시험은 계획이며 실행 결과가 아니다. 테스트 원문과 새 결과를 해당 artifact 폴더에 기록한다.

검증 명령은 저장소 `package.json`, `pyproject.toml`, `scripts/run_backend_unittest.cjs`를 기준으로 한다.
추가 회귀 → 기존 G1~G5/관련 모듈 → backend lint/typecheck/통합 → 계약 QA 순으로 실행한다.
공개 계약에 영향이 있으면 frontend/Electron 검사도 수행한다.

## 실제 진행과 실행 기록

모든 Python 시험은 `backend/.venv/Scripts/python.exe`와 임시 APPDATA/SFL_CONFIG_PATH를 사용했다.
최종 환경 및 정확한 health command는 `artifacts/temperature-followup-t1-t3/health-final.json`에 있다.
세 단계 전후 명령·결과는 `verification-runs.json`에도 기계 판독 가능한 형식으로 보존한다.

| 순서 | 실행/결과 | 증거 파일 |
| --- | --- | --- |
| T1 재현 | `-m unittest backend.tests.test_temperature_followup -v`, exit 1, 5 methods/11 실패 subcases | `t1-before.txt` |
| T1 보완 | 필수값 계약, raw partial 보존, 선택 위치 오류/skip/merged 복구, 관련 28 tests pass | `t1-related-r2.txt` |
| T2 재현 | `-m unittest backend.tests.test_temperature_followup.MetadataSourceTests -v`, exit 1, 6 methods/14 실패 subcases | `t2-before.txt` |
| T2 보완 | 실제 store/runtime 파일/mtime·state 불변, 정상 reset/수동 편집, 관련 51 tests pass | `t2-related-r2.txt` |
| T3 재현 | `-m unittest backend.tests.test_temperature_followup_polling -v`, exit 1, 5 methods/10 실패 subcases | `t3-before.txt` |
| T3 보완 | wall ±60/반복 보정, HTTP overrun, 실제 socket/worker helper/취소, 신규 21 tests pass | `followup-final.txt` |
| 통합 1차 | 전체 backend 790 tests, 789 pass/1 private F01 skip, exit 0 | `backend-all-r1.txt` |
| 최종 통합 | 새 PowerShell `npm.cmd run health`, exit 0. backend 792 pass/0 skip, F01 실행 | `health-final.txt` |

초기 정상 fixture 중 Count 또는 source proof 없이 성공을 가정하던 시험을 확인했다.
정상 fixture에 필요한 Count를 명시하고 실제 driver gate로 proof를 계산했다. 기존 assertion을 삭제하지 않았고
불완전 입력의 거부를 별도 새 시험으로 검증했다. 초기 한 실행의 PLCService 기본 CSV 모드는 이후 명시적 MOCK 환경으로 격리했다.

첫 QA selftest의 Get-FileHash 미탐색은 child PowerShell 모듈 검색 경로를 지정하여 해결했다.
최종 통합에서 Electron/frontend/backend와 QA 5개를 함께 통과했다. OS 전역 설정 변경은 없었다.

독립 읽기 검토 `/root/scope_qa_review`: 차단 결함 0. 새 UTC midnight fact 시험과 실제 CSV rollover 시험의
증거를 구분하라는 의견을 결과표/행렬에 반영했다. 진단용 wall-clock poll duration은 범위 밖 후속으로 분리했다.
전체 diff·신규 파일 목록/해시는 artifact에 보존했고 기존 로컬 untracked 34개와 이전 보고서의 바이트 불변을 검사한다.


## 후속 diff 검토와 보완

2026-09-21 검토에서 직접 회귀 1건을 재현했다. baseline merged Speed 실패는 빈 payload로 끝나지만
T1의 부분 raw 보존은 Count0를 legacy LogicProcessor에 전달하여 die_seq와 state.json을 변경했다.
정상 Count20 뒤 실패 및 첫 부분 표본의 두 회귀시험이 실제 parser/worker/read_data 경로에서 실패했다.
read_data에서 동일 snapshot source gate를 ID 계산에도 적용해 raw 부분값을 유지하면서 파생 상태 변경을 막았다.
skip 5회 동안 메모리·파일 bytes/mtime 불변, 완전 복구 시 한 번만 정상 ID 전환, 선택 위치 실패 시 ID 유지도 검증했다.

새 targeted 23 tests / 0 fail / 0 skip, 전체 backend 794 tests / 0 fail / 0 skip.
전체 health: 2026-09-21 11:25:32~11:28:30 KST, exit 0.
frontend 291 + 보조 9, Electron 94, Ruff/mypy/typecheck/lint, PowerShell QA 5개 통과.
읽기 전용 독립 재검토 `/root/baseline_audit`: 해당 수정 차단 결함 없음.
최신 원문·diff·소스 해시는 `artifacts/temperature-followup-t1-t3/review-20260921/`에 있다.
이전 completion-audit/manifest는 보완 전 단계 기록으로 보존하며 최신 소스의 해시 근거로 사용하지 않는다.
현재 HEAD/index와 기존 사용자 파일은 유지한다. Git 게시·병합·빌드·설치·실장비 검증은 하지 않았다.
