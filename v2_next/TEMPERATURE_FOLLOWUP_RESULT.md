# Temperature 후속 보완 결과

상태: **T1~T3 로컬 코드 보완·검증 완료**. 현장 검증·운영 승격은 별도다.
시작/현재 HEAD: `bf428fbe933ef5c52f1e6dd43c90058b5abd6a57`.
브랜치: `codex/temperature-remediation-20260909`. 변경은 로컬 작업 트리에 있다.

## 보완 내용

- T1: Count/Speed/Press를 현재 수집 시도의 필수 입력으로 검증한다.
  finite 값과 0을 허용하고 Count는 음이 아닌 정수여야 한다. 결측·bool·NaN/Infinity는 거부한다.
  부분 raw 값을 보존하며 이전 시도의 누락값을 채우지 않는다. 정상 복구와 split 성공 계수는
  필수 입력 완전성 및 해당 주기 통신 오류 부재를 모두 요구한다.
  선택 위치 실패는 완전한 공정 입력과 구분하며 통신 오류/실패 계수는 보존한다.
  후속 diff 검토에서 부분 Count가 legacy ID 계산에 새로 전달되는 회귀를 재현해 수정했다.
  동일 source gate로 unusable 표본의 파생 ID를 blank로 두고 메모리·state.json 변경을 차단한다.
  skip에서 수집시각을 연장하지 않는다. driver/service/repository/직접 phase 판정에 같은 검증을 적용한다.
- T2: unusable 표본은 자동 metadata reset·이전 유효 Count·정상시각·runtime 저장·operator context를
  갱신하지 않는다. 직접 helper 호출도 재검증한다. 유효 Count 양수→0 reset과 기존 downtime 정책은
  유지하며 첫 복구 표본의 downtime 판정 후 정상시각을 갱신한다. 수동 편집 API/store는 변경하지 않았다.
- T3: SPOT poll 및 세 worker의 주기 계산은 monotonic, PLC I/O deadline과 UTC 기록은 기존 epoch다.
  poll overrun은 지난 tick을 건너뛰고 완료 후 설정 interval을 기다린다. interval·동시요청 수·장비 retry/backoff
  설정은 변경하지 않았다. task 취소와 worker Event 대기는 종료에 응답한다.

## 계약과 호환성

기존 `usable`과 freshness 계약의 구현 오류를 보완한 것으로 CSV 컬럼·enum·물리 임계값·V1 구조를
바꾸지 않았다. schema 2.4.1/2.5.1과 phase rule v4를 유지하며 metadata 정책 설명만 구체화했다.
유효 입력의 기존 ID 알고리즘과 V1 컬럼/저장 형식은 유지한다. unusable 입력의 파생 ID는 blank다.
새 컬럼이나 저장 형식 이관은 없어 새 schema rollover는 필요하지 않다. 기존 파일/후보를 재작성하지 않는다.
mock/replay에 없는 live collection proof는 만들어 넣지 않는다. 이런 입력의 자동 공정 추론은 unknown이다.
CSV validator는 raw PLC transport 완전성 자체를 재검증할 수 없으므로 T1 합격 근거는 실제 호출 경로 시험이다.

## 위험과 복귀

운영 영향 위험은 높다. 부분 응답을 생산 상태로 승격하거나 작업 정보를 초기화하던 동작을 차단한다.
관측성에는 `extruder.process_input_status`가 추가되고 기존 통신 오류·실패·복구 계수를 보존한다.
필수 입력 장애 중 phase/공정 의존 expectedness는 unknown이며 정상 SPOT와 over-range 경고는 유지한다.
보수적인 unknown 증가와 반복 통신 실패는 오류/입력 상태를 통해 관찰할 수 있다.

현재 운영 소프트웨어는 변경하지 않았다. 코드 복귀는 이번 변경 명세의 파일만 시작 HEAD 기준으로 되돌리는
검토된 역패치이며 기존 사용자 자료를 reset/clean으로 삭제하지 않는다. 배포된 후보의 복귀 절차와 분리한다.
새 코드의 실장비·설치·7시간·자정 현장 시험은 미실행이며 이번 코드 목표의 추가 필수조건이 아니다.
과거 G1~G5 및 7시간 증거는 이전 코드의 결과로 보존하며 새 경계조건의 실측 자료로 확대하지 않는다.

## 검증

검토 보완 후 최종 `npm run health`: 2026-09-21 11:25:32~11:28:30 KST, exit 0.
아래 최신 원문 위치는 `artifacts/temperature-followup-t1-t3/review-20260921/`다. 이전 실행 원문과 해시는 부모 폴더에 보존한다.
Python 3.12.6 / Windows / 저장소 venv / Windows PowerShell 5.1 프로세스.
child 프로세스의 PSModulePath를 Windows PowerShell 모듈 경로로 지정했다. OS/사용자 전역 설정은 변경하지 않았다.

| 검사 | 실제 결과 | 원문 |
| --- | --- | --- |
| T1~T3 신규 production 경로 회귀 | 23 tests / 23 pass / 0 fail / 0 skip, exit 0 | `followup-after.txt` |
| 전체 backend unittest | 794 tests / 794 pass / 0 fail / 0 skip, 137.965초 | `health-final.txt` |
| frontend Vitest | 39 files / 291 tests pass | `health-final.txt` |
| frontend 보조 Node 시험 | 9 pass | `health-final.txt` |
| Electron 계약 | 94 pass | `health-final.txt` |
| backend Ruff / mypy | PASS / 설정된 8개 source 파일 PASS | `health-final.txt` |
| frontend typecheck / lint | PASS | `health-final.txt` |
| PowerShell QA self-tests | 5개 script PASS | `health-final.txt` |
| diff 공백 검사 / 독립 검토 | PASS / 읽기 전용 독립 검토 차단 결함 0 | `independent-review.md`, `git-diff-check.txt` |

전체 backend 794개는 기존 tracked 754개 + 새 후속 23개 + 기존 로컬 ignored 보충 17개다.
tracked/new/ignored 시험 소스의 구분은 artifact의 test source 목록에서 확인한다.
과거 시험 수를 이번 결과로 복사하지 않았다.
최종 실행은 해시 고정 F01 fixture를 제공하여 이전 1 skip도 실제 실행했다. 과거 CSV의 실측 clock 사건으로
해석하지 않고 Event로 지연을 주입한 production-path 회귀로만 사용한다.

실패 재현은 T1 5 methods/11 failed subcases, T2 6 methods/14 failed subcases,
T3 5 methods/10 failed subcases다. 단계별 보완 후 21 methods를 통과했고, diff 검토에서 드러난 직접 회귀 2 methods의 실패를 확인한 뒤
gate 보완으로 최종 23 methods를 통과했다. baseline 비교는 모의 통신과 임시 state 경로로 수행했다.
첫 QA self-test 실행은 호스트 PowerShell 모듈 검색 경로 때문에 Get-FileHash를 찾지 못해 exit 1이었다.
새 PowerShell 프로세스의 환경을 바로잡은 최종 health에서 동일 QA 5개를 모두 통과했다.

T3-07의 UTC/poll identity/drain은 새 actual poll loop 시험으로, 실제 CSV 날짜 전환은 전체 suite의
`CSVLoggerServiceTests.test_midnight_boundary_rolls_over_to_new_file`,
`test_v2_midnight_boundary_rolls_over_with_sidecar` 및 `test_temperature_fact_queue` rollover/closeout 시험으로
각각 검증했다. 합성 자정 전환이며 물리 서버 자정 관찰을 수행한 것은 아니다.

21개 요구사항의 호출 경로·실행 함수·명령·원문은 `TEMPERATURE_FOLLOWUP_REGRESSION_MATRIX.json`에 연결했다.
`artifacts/temperature-followup-t1-t3/`에 실패 재현 원문, 시험 결과, 독립 검토, 전체 diff와 신규 파일 명세/해시를 보존한다.
commit/push/PR 수정/merge/후보 빌드/설치/운영 승격은 수행하지 않았다.

## 변경 파일

- `backend/FacilityData/drivers/real_plc.py`: 필수 수집 proof, 부분값·오류 보존, monotonic worker scheduling.
- `backend/FacilityData/freshness.py`: 공통 필수 필드 검증.
- `backend/FacilityData/service.py`: 자동 metadata·context·runtime 저장의 독립 source gate.
- `backend/FacilityData/process_phase.py`, `repository.py`: 직접/외부 phase 우회 방지와 정책 metadata.
- `backend/FacilityData/drivers/spot_api.py`: monotonic polling, overrun 재예약, 취소 종료.
- `backend/tests/test_real_plc.py`: 정상 수집을 가정하던 기존 fixture에 실제 driver 검증을 통한 합성 source 증거와 일치하는 수집시각 제공. 기존 assertion 유지.
- `backend/tests/test_temperature_followup.py`, `test_temperature_followup_polling.py`: 실제 transport/loop/store/files 경로 회귀.
- `.gitignore`: 새 회귀 두 파일이 부모 ignore 규칙으로 CI에서 누락되지 않게 명시적 예외.
- `TEMPERATURE_FOLLOWUP_PROGRESS.md`, `TEMPERATURE_FOLLOWUP_REGRESSION_MATRIX.json`, 본 보고서: 새 후속 기록.

## 별도 후속과 한계

기존 `spot_poll_duration_ms`는 wall-clock 차이로 기록되어 시각 보정 시 0 또는 과대값이 될 수 있다.
이 값은 polling 주기를 결정하지 않으며 이번 scheduling 수정의 필수 의존성이 아니다.
독립 검토로 소비 경로와 목표 범위를 확인하고 별도 진단 품질 후속으로 남겼다.
PLC I/O deadline·retry/backoff의 epoch 계약도 보존했으므로 전체 통신 계층의 시각 보정 내성을 주장하지 않는다.

필수 로컬 시험 미실행 항목은 없다. 실장비 부분 응답·OS 시각 변경·설치·새 장시간 시험은 수행하지 않았다.
로컬 diff 검토에서 발견한 직접 회귀 1건을 보완하고 독립 재검토와 전체 health를 통과했다.
다음 단계는 선별한 13개 변경 파일의 커밋·푸시와 기존 PR #193의 새 커밋 CI 확인이다.
이 목표의 자동 Git 게시 금지에 따라 커밋·푸시는 수행하지 않았다. 병합 및 새 후보 검증도 별도다.
