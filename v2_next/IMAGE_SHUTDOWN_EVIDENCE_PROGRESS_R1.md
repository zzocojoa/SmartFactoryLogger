# 종료 증거 보완 진행 기록

2026-09-30. 범위: 승인한 로컬 production 코드·시험·문서. 서버 종료·설치·재시작·운영 승격은 포함하지 않는다.

## 기준과 보존

- 재사용 작업본: 기존 D1 worktree. 새 브랜치 `codex/image-shutdown-evidence-20260930`.
- 기준 HEAD: `586855d8b0185fb8ed36e44ab6998aae987cbdb5`(PR #196 병합본).
  이전 D1 HEAD와 전체 tree가 같음을 확인한 뒤 분기했다. 강제 checkout/reset/clean 없음.
- 기존 사용자 작업 41개 파일·git 상태, D1 미추적 자료 11개, 봉인 도우미 3개,
  원본/후보 핵심 소스 12개 해시를 보존했다. 총 70개 보존 검사 통과, staged 0.
- 앞선 `IMAGE_HOLD_RECOVERY_DESIGN_R1.md`/`IMAGE_HOLD_RECOVERY_RESULT_R1.md`와 과거 실패 증거를 수정하지 않았다.

## 재현과 최소 변경

1. 실제 이미지 enqueue/worker를 사용한 4개 신규 시험을 먼저 실행했다.
   기존 코드에 종료 snapshot/baseline API가 없어 4 error였고 원문을 보존했다.
2. image lock→queue mutex 아래 실제 worker·미완료 작업·결과 집계를 읽는 순수 메모리 snapshot을 추가했다.
   최초 종료 baseline을 고정하고 과거 실패와 신규 실패를 분리했다. 기존 bool 판정은 유지했다.
3. control/lifespan 진입에서 baseline을 잡고 세대별 create-only begin/final 증거를 추가했다.
   기존 manifest gate와 과거 실패 exit 2는 유지했다.
4. 읽기 전용 독립 검토로 저장 정체, 미완료 작업의 무결성 표시, 겹친 종료 경로의 실패 누락을 보완했다.
   증거 I/O는 별도 소유 thread에서 진행하고 종료 정리를 막지 않는다. 각 저장 관측은 최대 1초다.
   같은 process의 모든 attempt를 마지막 exit 직전 확인한다. 실패·미종료 참조는 지우지 않는다.
5. 독립 검토가 지적한 subTest 공유 상태를 분리했다. 과거 증거 실패가 새 성공으로 지워지지 않는 시험은 별도로 둔다.
6. 전체 회귀에서 기존 HTTP 취소 시험의 이벤트 순서 경쟁을 발견했다. transport production은 수정하지 않고,
   기존 Event로 응답 진입과 실제 취소 완료를 기다린 후 모의 worker를 해제하도록 시험만 보완했다.
   기존 로그 순서·개인정보 보호 assertion은 유지했다.

## 검증 기록과 실패 보존

원문·명령·환경·종료코드:
`C:\Users\user\Desktop\SmartFactory\IMAGE_SHUTDOWN_EVIDENCE_20260930_R1`.

- `driver-before`: 4 error(미구현 API), `driver-after`: 4 pass.
- `integrated-r2`: CSV stop이 완료 thread 참조를 비우는 것을 시험이 고려하지 못해 2 subTest error.
  시작 시 thread 객체를 잡아 실제 종료를 확인하도록 수정했다.
- `integrated-r4`/`integrated-repeat-r1`: 시험이 정상 종료에도 0.1초 timeout을 주어
  worker의 queue 대기 0.1초와 경쟁했다. 정상 시험은 2초, 의도한 정체 시험만 0.01초로 분리했다.
  production timeout은 바꾸지 않았다.
- `backend-full-r1`: 신규 실제 stop 시험이 남긴 poll 상태가 기존 mock 시험에 영향을 줬다.
  테스트가 바꾼 메모리 상태를 원복하고 process별 receipt registry를 시험마다 격리했다.
- `qa-workflow-r1`: worktree에 `js-yaml` 의존성이 없어 실패했다.
  재실행 child 환경의 NODE_PATH에 기존 후보의 의존성을 연결해 통과했다. 설치·OS 설정 변경 없음.
- `backend-final`: 기존 HTTP 취소 시험에서 `failure`가 `caller_cancelled`보다 먼저 기록된 1건 실패.
  불가능한 순서를 기대한 것이 아니라, 그 순서를 시험에서 제어하지 못한 문제였다.
  취소 완료 후 응답 해제로 수정한 동일 assertion이 10회 연속 통과했다.
- `backend-final-r2`: 기존 sync 요청 시험이 `to_thread` 생성 뒤 0.01초만 기다리고
  제출 완료를 가정하여, 실제 제출 전에 close가 호출된 1건 실패.
  실제 diagnostics의 `submitted`를 기다린 후 동일 shutdown_cancelled 검사를 수행하도록 보완했다.
  실패 시에도 Event 해제·종료를 보장하는 async cleanup을 추가했고 단독 10회 통과했다.

최종 수치·실행 행렬·코드/현장 검증 경계는 `IMAGE_SHUTDOWN_EVIDENCE_RESULT_R1.md`와
`IMAGE_SHUTDOWN_EVIDENCE_MATRIX_R1.json`에 기록한다. 실패 로그는 성공 로그로 덮어쓰지 않는다.
최종 `backend-final-r3`는 862 pass / 0 fail / 0 skip, 종료코드 0으로 완료했다.

## 운영 경계

이 변경은 새 버전의 종료 관찰성을 보완한다. 현재 서버 원본에는 새 계약이 없으므로 인계는 계속 HOLD다.
서버 실행·복사·설치, 실제 PLC/SPOT 접속, commit/push/PR/merge, 후보 빌드는 수행하지 않았다.
서버 원본의 기존 상태를 건드리지 않는 것이 이번 단계의 보존 경로다.
