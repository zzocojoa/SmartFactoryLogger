# 동시 종료 증거 대기 보완

## 발견과 범위

PR #198의 첫 Windows PR Artifact 실행 `36659784975`는
`b5cd9b5180e123d5a0f55e6d08a441b8a83ead1e`에서 backend 867개 중
실패 1·skip 1로 중단했다. 기존 control/partial-lifespan 동시 종료 시험이
exit0을 기대했으나 exit2를 받았다. 뒤의 패키징 단계는 실행되지 않았다.

실제 lifespan final writer의 fsync를 Event로 보류하고 실제 control receipt가
완료된 뒤 해제하는 합성 시험에서 같은 조기 exit2 경로를 재현했다.
진행 중인 peer와 확정 오류를 모두 미검증 bool 하나로 즉시 실패 처리한 것이
원인이다. 현장 장애 재현 또는 실제 PLC/SPOT 시험은 아니다.

## 최소 변경

- `backend/app.py`: 최종 로그 판정 전 peer 검증을 기존 0.2초 안에서 기다린다.
  `error_phase`가 있는 확정 실패와 pending을 구분한다. begin 완료~final 시작
  사이도 pending이며 thread 부재만으로 성공 처리하지 않는다.
- peer와 실제 로그 write/flush가 같은 monotonic deadline을 공유한다.
  service/transport/receipt I/O 예산을 늘리거나 종료 loop를 복제하지 않았다.
- 로그 ack 후에도 미검증인 late peer는 기존대로 즉시 exit2다. 남은 예산의
  수정 revision, 과거 실패 보존, timeout·취소·로그 오류의 실패 판정을 유지한다.
- `backend/tests/test_image_shutdown_evidence.py`: 기존 overlap 검사를 유지하고
  fsync 순서, peer 대기 취소, 두 대기의 단일 예산 검사를 추가했다.
  단일 예산 시험은 app의 monotonic clock만 고정 tick으로 제어한다.
- `backend/API_DOCUMENTATION.md`: pending/실패 및 두 대기가 공유하는 예산을 설명한다.

## 실행과 증거

최종 source 회귀를 통과했다. 로컬 증거는 개발 PC의
`Desktop/SmartFactory/SHUTDOWN_LOG_PR_20260930/repair/`에 보존한다.
각 `logs/*.json`에 명령·cwd·환경·시작/종료 시각·종료 코드·로그 SHA256을 기록했다.
Python 3.12.6, Node 22.22.2, Windows, 잠금 의존성의 기존 검증 venv를 사용하며
import 대상은 현재 engineering 소스다. 장비 I/O는 합성 경계로 대체한다.

| 실제 실행 | 결과 | 기록 |
|---|---|---|
| `python -m unittest discover -s backend/tests -v` | 870 pass, fail/error/skip 0 | `logs/backend-final.*` |
| 이미지 종료 회귀 | 31 pass, 위 전체 실행에 포함 | 같은 로그의 실제 test별 결과 |
| `python -m ruff check backend` | exit0 | `logs/ruff-final.*` |
| `python -m mypy` | 9개 설정 대상 모듈, exit0 | `logs/mypy.*` |
| `npm run health:electron-startup` | 94 pass, fail/skip 0 | `logs/electron.*` |
| `npm run health:qa:selftest` | 종료·설치·서명·workflow 5개군, exit0 | `logs/qa-selftest.*` |

현재 전체 backend 실행은 F01 private fixture를 포함했다. CI는 private fixture를
공급하지 않으므로 해당 조건부 시험 skip과 로컬 통과를 구분한다. frontend 소스와
계약은 변경하지 않았으며 이번 추가 diff에서 frontend 전체 검사를 재실행하지 않았다.
기존 후보의 frontend 결과를 새 diff 실행 결과로 세지 않는다.

`before-peer-v1.log`는 production b5에서 조기 `_exit(2)`를 검출한 실패다.
처음 잘못 지정한 실행 파일로 시작하지 못한 `before-peer.log`도 보존한다.
`after-peer-final.log`는 고정 clock 시험의 전체 실행 중 취소 시험이 자기 begin
writer의 1초 timeout으로 목표 경계에 진입하지 못한 오류다. 그 실행과 병렬
backend 실행이 같은 QA AppData를 사용했으나 직접적인 disk 지연 원인은
확정하지 않았다. 후속 최종 실행은 실행별 임시 AppData를 사용하고 단독 실행한다.
실패 기록·I/O timeout 정책·assertion을 삭제하거나 완화하지 않았다.

## 한계와 운영 판정

위험도는 중간이다. 상태/CSV schema·운영 설정·migration 변경은 없다.
이미지 drain·G/T/C/L1/P2·기존 receipt 의미는 유지한다. 확정 오류·정체·취소는
exit2로 종료하며, 마지막 예산을 소진하면 최종 로그가 없을 수 있다.
실제 OS 종료 코드·PID/세대·receipt를 함께 확인해야 한다.

독립 읽기 검토(`/root/shutdown_candidate_readonly_review`)에서 production 변경과
고정 clock 시험의 차단사항이 없었다. 원본 checkout의 사용자 변경 41개와 기존
engineering 자료 11개, b5 후보 및 증거 묶음의 해시 보존을 확인했다.
코드 복귀는 이 보완 commit을 revert하는 방식이며 조기 exit2가 다시 생길 수 있다.
후보 설치 없이 source와 CI만 확인한 결과를 운영 적용 완료로 표현하지 않는다.

b5의 기존 미서명 후보·PYZ 55개·Sandbox 96개 검증은 과거 결과다.
이번 추가 diff의 실제 설치·원본 복귀 검증으로 전용하지 않는다.
새 SHA의 후보 검증·현장 적용은 별도 gate이며, 서버 HOLD는 유지한다.
