# SPOT 포트 재사용·복구 종료 보완 R3

## 후속 후보 R5 통합 기준 정정 — 2026-10-01

아래 R3 본문과 동결 증거의 853개 통과는 과거 P2 `1cd48e6` 작업본의 결과다.
후보 준비 중 기존 PR #199 병합본 `21b2e80cd12134dd97a794b6d53373b72877089c`와
대조하여 D1·이미지 종료 receipt·최종 로그·의존성 보완의 누락을 확인했다.
R4는 BASELINE_HOLD로 보존했으며 설치본을 만들거나 실행하지 않았다.

R5는 이 PR #199 병합본을 기준으로 R3 포트 변경을 hunk 단위로 적용했다.
선행 transport 시험의 Event/cleanup과 D1/image 시험 ignore 예외를 유지했다.
통합시험은 새 production receipt의 해시·상호 결합·writer 종료도 확인한다.
추가 의존성 변경은 기존 scoped DOMPurify 3.4.15→3.4.16 하나다.
실제 JSDOM의 제거된 원본 노드에서 두 after-hook 문제를 재현했고, 네 hook의
수정 후 정리를 검증했다. 근거: https://github.com/advisories/GHSA-p98j-92pf-mc4p

통합 소스 QA: backend 880, Electron 94, frontend Node 9·Vitest 305,
dependency security 14, lint/typecheck 및 PowerShell SelfTest 5개 통과.
root/frontend npm audit 모두 0건. 최초 전체 실행은 기존 peer receipt 시험
한 건의 3초 대기 초과로 exit 1이었다. assertion/timeout 변경 없이 해당 모듈
31개와 전체 880개 재실행이 통과했다. 최초 실패는 유지하며 원인 확정·수정으로
표현하지 않는다. 읽기 전용 독립 검토에서 추가 중대 회귀를 발견하지 않았다.

소스·명령·종료코드·전후 로그·새 후보 결과는
`C:\Users\user\Desktop\SmartFactory\SOURCE_PORT_CANDIDATE_R5`에 보존한다.
이 커밋 시점의 패키지/설치 검증은 아직 미실행이다. 이후 실제 결과는 해당 폴더의
결과 보고서에 분리 기록한다. 과거 R1/R2/R3와 서버 상태는 변경하지 않았다.

## 보존한 R3 소스 검증 기록

기준: `codex/temperature-history-p2-20260922`, HEAD
`1cd48e6457637e97ca77787c0744579cc1479dfb`. 2026-10-01 로컬 작업.

현재 판정: 로컬 코드 보완·합성 복구·종료 검증 완료. 서버 적용 승인은 아니다.
기존 사용자 변경과 과거 R1/R2 증거를 보존했다. 이 작업은 로컬 소스·합성 시험·문서에 한정한다.

## 재현과 변경

Windows에서 이전 TCP 연결의 TIME_WAIT가 남아 있어도 wildcard exclusive bind는
성공할 수 있었다. 실제 HTTP 연결에서 10048이 발생하고, 8개 재시도 포트가 모두
같은 조건이면 아직 사용하지 않은 포트가 있어도 요청이 실패했다. 실제 소켓 시험으로
재현했으며 exclusive 옵션 추가 또는 구체적인 local IP bind만으로는 해소되지 않았다.

`spot_port_quarantine.py`는 재사용 시점이 된 포트를 다시 guard하기 전에 기존 의존성인
psutil의 시스템 IPv4 TCP 목록을 조회한다. PID 없는 TIME_WAIT를 포함한 모든 local port를
제외한다. 조회 오류·잘못된 행은 빈 목록으로 간주하지 않는다. 기존 exclusive guard와
연결 재시도도 유지하여 조회 이후의 경쟁을 방어한다.

독립 검토에서 새 조회를 pool lock 안에서 실행하면 종료까지 정체될 수 있음을 발견했다.
Event 재현에서 50ms 종료 예산을 지정해도 비상 해제까지 2.016초가 걸렸고 늦은 guard가
생성됐다. 조회를 lock 밖으로 옮기고 복귀 후 pool 종료 상태·record 세대·positive acquire
deadline을 다시 확인했다. 조회가 끝나지 않으면 종료는 제한시간 안에 False로 반환하고
실제 미종료 thread 참조를 보존한다. 조회를 강제 중단한다고 주장하지 않는다.

pool 768개, quarantine 77초, acquire 5초, rebind retry 1초, bind retry 8회,
sampling·HTTP 요청 정책·OS TCP 설정은 변경하지 않았다. 초기 guard 할당은 기존 방식이다.
TTL/source proof/phase/metadata/queue·drain/attestation 계약과 lifecycle 제품 코드는 그대로다.

## 검증 범위와 결과

| 검증 | 결과와 근거 |
| --- | --- |
| Windows 실제 HTTP 반복 | 최종 소스 250.531초, 1,501회, 실패·충돌·고갈 0. 최소 재사용 119.828초 ≥ 77초. 소스 해시 불변. executor/watchdog/fixture 종료 확인 |
| 새 포트 회귀 | OS 점유·모든 포트 고갈·조회 오류/잘못된 행·지연 조회 종료·동시 acquire·deadline 초과·실제 TIME_WAIT를 시험 |
| production 통합 | 실제 RealPLCDriver/PLCService/CSVLoggerService/SpotHttpTransport/poll·writer와 `app._run_control_shutdown` 실행. 장비 읽기·loopback peer·파일 I/O 대기·마지막 `os._exit` 경계만 대체 |
| 정상·오류 복구 | 최초 HTTP503 → 동일 service ID의 증가한 poll seq에서 정상 500. 과거 진단 실패 event 원문·request ID 보존 |
| 실제 미완료 fact drain | accepted 4/completed 3/pending 1/inflight=True에서 종료. stop 신호 후에도 writer 생존·종료 미완료 확인, 해제 후 pending 0·writer 종료 |
| 종료 소유권 | thread 객체 11개와 task 3개 종료. HTTP active/leased/pending, observation pending/spool/failure, image unfinished/drop/failure, CSV queue/buffer/drop, journal active/pending/write failure 모두 0 |
| 저장 closeout | CSV finalized, observation SHA·누락 연결 키 0, 별도 final image manifest SHA 확인. CSV 시작 시 이미지 manifest snapshot과 최종 이미지 manifest를 구분 |
| 백엔드 전체 | 853/853 통과, 실패 0·skip 0, 198.074초, exit 0. 기존 G/T/C/L1·저장 closeout·history/API·계약 회귀 포함 |
| Electron·프런트엔드 | Electron 94/94, frontend Node 계약 9/9 및 Vitest 301/301(40 files). frontend typecheck/lint 통과 |
| Python 정적 검사 | Ruff 통과, 기존 mypy 8개 모듈 및 변경 pool 모듈 별도 통과 |
| 운영 도우미 QA | NSIS operational-ready/startup trace, closeout hang, release signature, workflow contract의 5개 SelfTest 통과. 실제 설치·서명·배포 시험이 아님 |
| 과거 증거 | R2 manifest 1,166개 파일·약 297.5MB의 전체 해시 일치. 과거 실패와 원본 d7a drain 미검증 판정 유지 |
| 독립 검토 | 읽기 전용 reviewer 2명: 조회 lock/deadline 및 통합시험 격리/복구 assertion 지적 반영, 재검토 추가 중대 사항 없음 |

백엔드는 Python 3.12.6, `backend/.venv/Scripts/python.exe -B -m unittest discover -s backend/tests -v`
명령을 새 APPDATA/SFL_CONFIG_PATH, V2_MODE=MOCK, 제공된 F01 fixture 경로로 실행했다.
실제 명령·환경·종료코드·stdout/stderr는 각 실행 폴더의 `command.json`과 로그에 있다.
통합 시험의 socket proxy는 RealPLC 모듈 참조만 바꾸며 HTTP는 실제 Windows loopback 소켓이다.
이미지 경로는 시험 root 아래로 고정하고 포함 관계를 검사한다.
통합시험에서 활성화한 소유자는 위 11개 thread와 3개 task다. config watcher·memory·
comm-metrics 등 관련 없는 서비스는 시작하지 않았으므로 그 서비스의 부하 종료 증거는 아니다.

실행 예시(저장소 root):

```powershell
$env:V2_MODE = 'MOCK'
$trialRoot = Join-Path ([IO.Path]::GetTempPath()) ('sfl-r3-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $trialRoot | Out-Null
$env:APPDATA = Join-Path $trialRoot 'appdata'
$env:SFL_CONFIG_PATH = Join-Path $trialRoot 'config.ini'
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_spot_tcp_reuse backend.tests.test_temperature_terminal_integration -v
```

중간 실패도 보존한다. 초기 Python 실행의 사용자 site 의존성 누락, 시험 API 이름 오기,
unittest discover의 자식 모듈 경로 문제를 수정한 뒤 다시 검증했다. PowerShell QA 첫 실행은
상속된 PowerShell 7 module 경로 때문에 Windows PowerShell 5.1의 Get-FileHash 자동 로드에
실패했다. 별도 시험 프로세스에서 PS5.1 module 경로를 지정하여 같은 5개 SelfTest를 통과했다.
운영 OS 환경이나 QA assertion을 바꾸지 않았다.

## 산출물과 한계

- 코드: `backend/FacilityData/drivers/spot_port_quarantine.py`
- 신규 시험: `backend/tests/test_spot_tcp_reuse.py`, `backend/tests/test_temperature_terminal_integration.py`
- 기존 factory fixture의 TCP 목록 계약 추가: `test_spot_http_transport.py`, `test_spot_port_quarantine.py`
- `.gitignore`에 신규 시험 2개를 명시해 검토에서 제외되지 않도록 했다.
- 로컬 증거: `C:\Users\user\Desktop\SmartFactory\SOURCE_PORT_RECOVERY_R3`
  - `before-reuse-venv`, `before-stalled-query-real`, `before-query-deadline`: 실패 원문
  - `native-soak-release`: 최종 소스 반복 시험과 연결 포트 기록
  - `terminal-backlog-final/observed`: 실제 데이터·종료 상태·원래 실패 event
  - `backend-all-verified`: 최종 전체 회귀
  - `full-change.diff`, `new-files.json`, `execution-ledger.json`, `artifact-manifest.json`: 검토·무결성 자료

시스템에 재사용 가능한 포트가 부족하면 기존 정책대로 제한시간 후 실패한다. 모든 OS 부하와
실장비 동작을 보장하는 시험은 아니다. TCP 조회가 정체된 thread는 완료로 표시하지 않으며,
조회가 끝나야 실제 thread 종료를 재확인할 수 있다.

이번 결과는 현재 소스의 합성 통신 복구·저장 drain·정상 종료 검증이다. 원본 d7a의 과거
실행, 새 패키지/Electron UI/NSIS/Windows Sandbox, 서버 120분 관찰·현장 TCP 상태의
검증을 대체하지 않는다. 커밋·푸시·PR·빌드·설치·서버 실행·운영 승격은 수행하지 않았다.
