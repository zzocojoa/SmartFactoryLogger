# 최종 종료 로그 보완 결과

## 현재 판정

최종 로그를 큐에 넣자마자 `os._exit`해 파일 기록이 누락되는 회귀를 수정했다.
현재는 **source 수정·검증 완료, 새 packaged 후보 미검증**이다. 이전 후보의
`OBSERVABILITY_HOLD`와 기존 서버 HOLD를 해제하거나 운영 승격으로 표현하지 않는다.

## 변경과 영향

| 파일 | 목적 |
|---|---|
| `backend/app.py` | 실제 파일 write/flush ack, 내부 오류 전달, 기존 0.2초 공유 deadline, 최종 receipt 재검사 |
| `backend/tests/test_image_shutdown_evidence.py` | 실제 subprocess 종료 및 정상·정체·write/flush 오류·취소 시험 추가, 기존 peer 경계 시험 강화 |
| `backend/API_DOCUMENTATION.md` | 종료 로그의 revision·실패·종료 전 관측 의미 명시 |
| `SHUTDOWN_FINAL_LOG_PROGRESS_R1.md` | 실행 과정과 미완료 gate 기록 |
| `SHUTDOWN_FINAL_LOG_MATRIX_R1.json` | 현재 명령·환경·결과 및 요구사항별 근거 |
| 본 문서 | 결과·한계·다음 단계 |

서비스·transport timeout, 이미지 drain·실패 이력·receipt, G/T/C/L1, HTTP 인증·CSV schema·UI는
그대로 유지한다. receipt를 덮어쓰거나 최종 증거 확인을 약화하지 않는다.
로그 처리는 기존 QueueListener에서 수행하며 control coroutine에서 I/O나 무한 join을 하지 않는다.

## 재현과 검증

| 검사 | 결과 |
|---|---|
| 같은 실제 subprocess/os._exit 시험 | 이전 production 소스: 최종 로그 0건 실패 → 수정본: 통과 |
| 이미지 종료 회귀 | 28 통과, 실패·skip 0(backend 전체에 포함) |
| backend 전체 `unittest discover -s backend/tests -v` | 867 통과, 실패·skip 0 |
| Electron startup/control/lifecycle/shutdown 계약 | 94 통과, 실패·skip 0 |
| backend ruff / mypy | 통과 / 9개 설정 대상 모듈 통과 |
| closeout·NSIS readiness·startup trace·signature·workflow SelfTest | 5개군 통과 |

Python 3.12.6, Node 22.22.2, Windows에서 실행했다. backend 의존성은 직전 동일 잠금파일의
검증용 venv를 사용하고, 코드 import·명령 cwd는 현재 engineering worktree로 지정했다.
AppData·설정 경로는 별도 QA 폴더이고 외부 장비는 모의 경계로 대체한다. 과거 CSV F01 fixture도
현재 전체 시험에 포함했다. 이전 시험 개수를 복사해 이번 결과로 사용하지 않았다.

초기 재현 시험의 JSON 파서 오류와 workflow의 의존성 부재 실패는 보존했다.
전후 비교에 사용한 확정 재현은 초기화 문구와 구분한 최종 JSON 레코드를 검사하며,
이전 소스와 수정본에 동일한 assertion을 적용했다.

frontend는 변경하지 않았고 이번 source 단계에서 전체 frontend lint/typecheck/Vitest는 재실행하지
않았다. 새 clean 후보 빌드 단계의 전체 health 검증은 아직 남아 있다. 기존 후보의 health 또는
Sandbox 결과를 수정 후보의 결과로 간주하지 않는다.

## 검토와 실패 의미

독립 읽기 검토(`/root/shutdown_candidate_readonly_review`)에서 차단 사항이 없었다.
timeout 시험은 Windows scheduling 여유를 두어 0.6초 상한으로 관찰하므로, 그 시험 하나만으로
정확한 0.2초를 입증하지 않는다. 현재 코드의 단일 monotonic deadline·재시도 공유를 함께 검토했다.

로그 저장이 멈추거나 오류·취소가 발생하면 exit2다. 대기 중 다른 종료 작업이 생기면 상태를
재검사하고 같은 남은 예산 안에서 실패 revision을 최대 한 번 기록한다. 예산이 소진되면 정정
로그도 없을 수 있다. 성공 문구만 읽지 않고 실제 OS 종료 코드·PID/세대·receipt를 함께 확인한다.
이 ack는 stream flush 완료이며 fsync·정전 내구성·실제 process 종료 증명이 아니다.

위험도는 중간이다. 로그 저장 상태를 확인할 수 없는 환경에서는 기존보다 보수적으로 exit2가
된다. 설정·저장 schema 이관은 없다. 로컬 코드 복귀는 이번 diff를 되돌리는 방식이며, 그러면
기존 로그 누락도 다시 생기므로 이전 후보를 운영 검증 통과본으로 간주하지 않는다.

## 남은 gate

1. 검토된 변경을 정확한 clean commit으로 고정한다. dirty 소스를 이전 SHA로 빌드하지 않는다.
2. 새 미서명 후보 빌드와 전체 health·payload/내장 모듈 검증을 수행한다.
3. 새 frozen 후보를 Windows Sandbox에서 설치·수집·이미지 저장·종료·재시작·원본 복귀하며,
   기존 96개 검사(마지막 로그 포함)를 그대로 재검증한다.

현재 커밋·푸시·PR·설치·서버 조작은 수행하지 않았다. 과거 실패와 기존 사용자 파일은 보존한다.
새 후보의 격리 QA가 끝나기 전에는 이 보완 목표 전체를 완료로 선언하지 않는다.
