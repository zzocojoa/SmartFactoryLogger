# L1 진행 기록

2026-09-21. 기준 HEAD `10821534b2e9b54f6be6494cafb4b7ee43d45395`,
브랜치 `codex/temperature-remediation-20260909`. 시작 시 staged/unstaged 없음.
기존 untracked 34개와 과거 보고서 9개의 해시를 보존 목록에 기록했다.

## 재현과 최소 수정

- 첨부 CONTEXT 및 12항목 행렬을 읽고 실제 driver/service 및 상위 shutdown/reconnect 호출부를 추적했다.
- production RealPLCDriver를 소유한 PLCService에서 장비 경계만 Event로 막았다.
  SPOT/Extruder/LS 각각 stop=True, old worker 생존, 소유 목록에서 old 참조 소실을 재현했다.
  `lifecycle-before.txt/.json`에 원문과 종료코드 1을 보존했다.
- 첫 before의 부분 생성 실패 2개 subcase는 기존 구현이 thread를 모두 생성한 뒤 시작하여
  fixture의 진입 대기가 실패한 결과다. 이를 별도 제품 결함의 재현 증거로 세지 않는다.
- close는 실제 종료와 자원 정리의 bool을 반환하고, live 참조/stop 신호/실패 자원을 보존한다.
  Mock/CSV는 비동기 worker가 없으므로 정리 후 명시적으로 True를 반환한다.
- driver lifecycle lock은 제어 진입점만 직렬화한다. worker는 이 lock을 취득하지 않는다.
  기존 service/driver의 각 join 1초 예산은 유지한다.
- service는 driver 종료 결과를 결합하고, connect gate 이후에만 자신의 Event를 clear한다.
  부분 시작 실패도 stop 신호와 실제 생성한 객체를 남긴다.
- 직접 reconnect API는 stop=False일 때 start하지 않는다. config reconnect는 driver gate 예외를
  기존 service의 False/pending 경로로 전달한다. 독립 HTTP/fact/image 종료 정책은 변경하지 않는다.

## 검토에서 보완한 경계

독립 검토에서 join timeout 후 소켓 정리와 늦은 소켓 게시의 경합을 확인했다.
live worker가 남으면 소켓도 함께 보존하고, 실제 종료 후 반복 close에서만 정리한다.
실제 `_read_extruder -> _connect_extruder`와 지연 socket factory로 검증했다.
서비스 종료와 config 적용도 service lifecycle lock으로 직렬화했다.
부분 시작 실패는 `_close_incomplete`로 남아 정상 종료 재확인 전 시작할 수 없다.

`lifecycle-after-r2/r3`의 유일 오류는 새 시험에서 app을 임시 경로 patch 이후 import해
comm metrics log handle이 그 경로를 유지한 fixture 정리 오류였다. import를 격리 실행의
지속 APPDATA에 두어 정리를 보완했다. 제품 assertion을 삭제/약화하지 않았다.
`lifecycle-after-r4`: L1 12개+C1 7개, 19 pass. 이후 partial startup의 미완료 flag를 강화하고
`targeted-final`: G/T/C/closeout 포함 131 pass, 0 fail/skip, exit 0으로 확인했다.
독립 재검토 판정은 Approve, 추가 blocker 없음이다.

전체 health는 23:47:09~23:51:48 KST, exit 0으로 완료했다. backend 830 pass,
Electron 94 pass, frontend 291+9 pass, lint/typecheck와 필수 PowerShell QA 5개 통과.
현재 소스와 검증 source hash 9개, 초기 보존 목록 43개를 대조했고 모두 일치한다.
실행 행렬 12항목과 전체 diff/신규 파일의 검토 묶음을 확정했다. L1 코드 목표 완료다.
history/API P2와 실장비/배포/자동 Git 게시는 범위 밖이다.

## 2026-09-22 재대조 및 시험 보강

- 사용자 재확인 요청에 따라 현재 L1 코드와 첨부 12항목을 다시 대조했다. production 추가 변경 없음.
- 직접 `_start_workers` 부분 생성/시작 실패 후 old worker 늦은 종료 조합을 신규 시험 1개/2 subcase로 보강했다.
  service cleanup 없이 Event clear·연결·새 thread 차단, old 추가 주기 없음, close 후 명시 재시작을 확인했다.
- 추가 시험 통과 후 관련 회귀 132 pass, 전체 backend 831 pass,
  Electron 94, frontend 291+9, lint/typecheck·QA 5개, health exit 0.
- 독립 읽기 검토: Approve, 기존 시험 공백 해소, 추가 blocker 없음.
- 이전 evidence 57개와 사용자/과거 보고서 보존 대상 43개를 유지했다. 최신 산출물은 `artifacts/temperature-worker-lifecycle-l1/recheck-20260922/`에 추가했다.
- L1 완료. Git/PR·운영·P2 작업 없이 종료한다.
