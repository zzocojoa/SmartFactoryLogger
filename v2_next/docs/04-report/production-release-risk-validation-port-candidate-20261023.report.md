# 포트 할당 개선 후보 1.0.32의 clean 빌드·패키지 검증

2026-10-23. **미서명 설치본·로컬 검사, 후속 VM 설치/복구와 현장 적용·제한 범위 검증을 완료했다. 전체 출시는 HOLD다.**

현재 결과는 [VM 검증](production-release-risk-validation-c32-vm-matrix-20261023.report.md),
[현장 검증](production-release-risk-validation-c32-field-preparation-20261023.report.md),
[목표 대조](production-release-risk-validation-goal-alignment-20261022.report.md)를 따른다.
아래 ‘미완료’·C31 현장 후보·서버 미조작 문구는 최초 빌드 단계의 보존 이력이다.

이미 확보한 SPOT 포트가 있어도 다른 포트의 OS 상태 조회를 먼저 기다리던 경로를 수정했다.
앞선 로컬 회귀에서 조회 지연·실패에 의한 불필요한 요청 실패를 재현했다. 이 수정은 과거
10월 19일 오류 여섯 건의 실제 지연 원인 또는 10월 9일 최초 적용 timeout 원인을 확정하지 않는다.

## 후보 식별과 변경 범위

| 항목 | 확인 값 |
|---|---|
| 출발 commit | `a7e5149b718f56d7dfa75df73bfba4a21d16a758` / 1.0.31 |
| 새 clean commit | `cd46692ac9c551080c57d8168fa9ea5abd530206` / 1.0.32 |
| 작업 branch | `codex/port-guard-candidate-20261023` |
| installer 크기 | 164,158,258 bytes |
| installer SHA256 | `558658cf02d59cb6b66468e4e191c447efdc7cc24518b5a69647cc2409eb232f` |
| 서명 | `NotSigned` / 승인된 미서명 내부 운영 정책 적용 |

재사용한 managed worktree에서 포트 구현·회귀검사 2파일과 버전 식별·검사 6파일만 커밋했다.
버전 6파일은 `1.0.31` → `1.0.32` 변경뿐임을 원 commit과 대조했다. 기존 C31 commit,
설치본 및 주 작업본의 다른 미커밋 변경은 보존했다. 새 clone에서 의존성 설치·검사·빌드
전후 clean 상태를 확인했다. Python 잠금 wheel 40개와 설치 목록·해시도 일치했다.

설치본 위치:
`C:/Users/user/Desktop/SmartFactory/C32BUILD_20261023_eac4b615/source/v2_next/dist/smart-factory-logger-v2 Setup 1.0.32.exe`

## 실행한 검사

| 실행 | 결과와 범위 |
|---|---|
| `prepare_ntfs.py --run` → `npm run health` | exit 0. 의존성15, Electron103, 화면 Node9/Vitest442, backend964 통과/1건 skip. 타입·린트·QA 도구 self-test 통과 |
| `build_isolated.py --run` | exit 0. 화면·PyInstaller·NSIS 빌드, provenance·backend manifest·asar 대조, 미서명·버전 확인 |
| `verify_payload.py --run` | exit 0. 설치본 추출1,867파일/561,612,721 bytes가 win-unpacked와 일치. 화면51파일의 두 포함 위치 대조 |
| `run_frozen.py --run` | exit 0. 추출 backend의 loopback 모의 장비 실행, health5요청(일반1/진단4), 정상 종료0, 잔류 프로세스·listener0 |

빌드 출처3,624개가 허용된 새 source/venv·Python·Windows 경로 안에 있었다.
모든 실행은 소유 Job에서 진행했고 강제 종료 없이 정리됐다. 이 짧은 backend 검사는
Electron 화면, 실제 설치·복구, 포트 전체 순환의 장시간 성능 또는 현장 QA를 대신하지 않는다.
기존 C31의 120분·데이터·네 화면 결과를 새 C32의 결과로 재표시하지 않는다.

비공개 `TEMPERATURE_GOAL_PACKAGE`의 F01 자료가 없는 1검사는 skip으로 남는다.
PyInstaller의 `tzdata` hidden-import 경고와 npm의 deprecated 경고를 원시 로그에 보존했다.
기존 도우미 기록의 경로 필드 형식을 잘못 읽은 첫 준비는 파일 생성 전 TypeError로 중단됐다.
형식을 확인해 수정·정적 검사한 뒤 실행했으며 실패 기록도 별도 보존했다.

## 남은 적용 조건

1. 동일 installer의 격리 설치·정상 종료·복구와 변경된 포트 경로의 충분한 순환·수집/저장 검사.
2. 해당 후보의 현장 적용 범위와 필요한 검증. 기존 동일 설치본의 완료 시험을 자동 반복하지 않는다.
3. 물리 Low Signal 비교·정식 QA, 과거 데이터/timeout/drop의 미확정 항목과 운영 승격 판단.

서버 조작·파일 전달·설치·설정 변경·백업을 이번 단계에서 수행하지 않았다. 현장 적용 후보는
기존 C31이며 등록 롤백 기준은 별도 운영 기준 문서 그대로다. 전체 출시 `HOLD`, 승격 false.

원시 로그·전체 단계 결과·검산표는
`C:/Users/user/Desktop/SmartFactory/C32REL_20261023_eac4b615`의
`candidate-review.json`, `clean-health-review.json`, 각 단계 `summary.json`/`terminal.json`에 있다.
