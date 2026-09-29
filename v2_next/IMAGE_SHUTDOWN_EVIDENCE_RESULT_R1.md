# 종료 증거 코드 보완 결과

2026-09-30. **승인한 로컬 코드 보완·검증 완료. 현장 인계·운영 승격은 HOLD**.

## 변경과 보존한 판정

실제 이미지 worker 종료와 과거 데이터 실패를 분리해 기록한다. 최초 종료 진입의 실패 누계를
고정하므로 poll/transport 정리를 기다리는 동안 생긴 실패도 신규 delta에 포함된다.
queue 0·unfinished 1, 늦은 worker 종료, 반복 종료를 구분하며 누계나 과거 파일을 초기화하지 않는다.

control/lifespan은 PID·backend generation·session·시작시각·빌드 identity를 가진 별도 begin/final
증거와 SHA256을 만든다. 파일을 덮어쓰지 않고 flush/fsync·재조회·binding을 검사한다.
쓰기 정체가 서비스 정리를 막지 않으며 저장 thread가 살아 있거나 한 attempt라도 실패하면
정상 종료로 판정하지 않는다. 기존 서비스/transport timeout은 유지하고 증거 관측만 각각 최대 1초다.
최종 exit 직전 재검사하므로 마지막 대기 중 다른 종료 경로가 시작돼도 누락하지 않는다.

기존 image shutdown bool, 누적 실패 13건의 false/exit 2, image final manifest 차단,
G1~G5·T1~T3·C1~C3·L1·D1·history/API 의미는 유지한다. 초기화·강제 thread 종료로 성공을 만들지 않았다.
API는 기존 인증·필수 identity 5개를 유지하고 메모리 상태 두 필드만 선택적으로 추가한다.

## 변경 파일

- `backend/FacilityData/drivers/spot_api.py`: 최초 baseline, 실제 worker/queue/accounting snapshot.
- `backend/FacilityData/shutdown_evidence.py`: create-only receipt, 해시/binding, 소유 writer와 sticky failure.
- `backend/app.py`: 두 종료 경로 연결, 전체 attempt 종료 직전 gate, 메모리 control health.
- `backend/tests/test_image_shutdown_evidence.py`: 실제 worker·app·CSV와 파일/transport 경계 합성시험 23개.
- `backend/tests/test_spot_api.py`, `test_shutdown_closeout_regression.py`: 시험별 process registry 격리.
- `backend/tests/test_spot_http_transport.py`: 기존 두 시험의 sleep 가정을 실제 진입·제출·취소 완료 관측으로 교체.
  기존 순서·개인정보 보호 assertion은 유지하고 transport production 코드는 그대로다.
- `.gitignore`, `pyproject.toml`: 신규 시험 검토 누락 방지, 새 모듈 mypy 포함.
- `backend/API_DOCUMENTATION.md`, 진행/결과/행렬 문서: 종료 증거 계약과 한계.

## 검증

Windows 개발 PC, Python 3.12.6, Node 22.22.2. 모든 새 시험은 임시 경로를 사용한다.
새 worker 시험은 connect/connect_ex/sendto 시도 수 0을 확인하며 finally/cleanup에서 제어 대기를 해제하고
실제 thread 객체를 join한다. 기존 전체 회귀의 loopback 서버 시험은 모의 장비 경계다.

| 검사 | 결과 | 종료코드 |
| --- | --- | ---: |
| 최종 backend 전체(신규 23개 포함) | 862 pass / 0 fail / 0 skip | 0 |
| 신규 production 경로 시험 | 23 pass / 0 fail / 0 skip | 0 |
| 이전 로컬 복구 assay를 새 코드에 실행 | Python 10 + Electron 4 pass | 각각 0 |
| 기존 Electron 전체 | 94 pass / 0 fail / 0 skip | 0 |
| HTTP 취소/제출 순서 시험 반복 | 각각 10회 pass, assertion 유지 | 각각 0 |
| backend ruff / mypy | pass / 9 source files pass | 각각 0 |
| 종료·NSIS 측정·trace·서명·workflow SelfTest | 5개 pass | 각각 0 |
| 사용자 작업·기존 증거 보존 | 70개 확인, staged 0 | 0 |

명령·명시적 환경·시간·종료코드는 각 `*.command.json`과 실행 행렬에 있다.
초기 실패/중간 성공/최종 재실행은 별도 이름으로 보존했다. 과거 시험 개수를 복사한 수치가 아니다.
frontend typecheck/lint/tests는 frontend/Electron source·데이터 계약 변경이 없어 실행하지 않았다.
전체 npm health 대신 사용 가능한 고정 Python과 Node로 backend·Electron·QA 단계를 직접 실행했다.
workflow QA의 js-yaml은 기존 후보 node_modules를 child NODE_PATH로 참조했다. 의존성 설치·OS 변경 없음.

## 독립 검토와 증거 위치

읽기 전용 독립 검토를 수행했다. 저장 I/O 정체, 미완료 write의 무결성 표시,
동시 종료 경로의 증거 실패 누락, subTest 상태 공유 지적을 반영했다.
기존 안전 assertion 삭제나 실패를 정상화하는 변경은 없다. 최종 production 및 시험 diff의
읽기 전용 독립 검토에서 남은 차단사항은 발견되지 않았다. 마지막 전체 실행은 177.090초였다.

- 원문: `C:\Users\user\Desktop\SmartFactory\IMAGE_SHUTDOWN_EVIDENCE_20260930_R1`.
- 검토용 보관: `artifacts/image-shutdown-evidence-20260930-r1/`.
  실행 행렬, 로그(주소 마스킹 사본), private 원문 SHA256, 실제 production receipt,
  전체 diff(신규 파일 포함), 13개 변경 파일 명세/해시, 검토 기록, manifest를 포함한다.
- `IMAGE_SHUTDOWN_EVIDENCE_MATRIX_R1.json`: 개별 시험과 실제 실행 명령.

원본 사용자 41개 파일·git 상태, D1 이전 미추적 11개, 봉인 도우미 3개와 원본/후보 핵심 소스를 보존했다.
코드 commit/push/PR/merge, 후보 빌드·설치, 서버 작업은 하지 않았다.

## 위험과 다음 단계

위험 수준은 높다. 종료 경로에 실패를 숨기지 않는 추가 gate가 생긴다. receipt 저장 오류·정체는
정리 후 exit 2/HOLD로 나타나며 새 실패를 원인 코드·attempt ID·상태로 관측할 수 있다.
지원되지 않는 파일시스템·redirect된 AppData 경로는 성공 판정을 막을 수 있다.

데이터/schema migration은 없다. 되돌릴 때는 이번 코드 diff를 되돌리고 기존 증거 파일은 보존한다.
서버는 이번 작업으로 변경하지 않았으므로 기존 원본 상태를 유지하는 것이 현재 보존 경로다.

receipt는 **종료 전 관측**이다. timeout 뒤 늦게 만들어진 파일의 `stage_exit_code=0`도 실제 exit 0을
뜻하지 않는다. 해시는 서명·출처 인증이나 정전 내구성을 증명하지 않으며,
`process_exit_observed=false`, `installation_clearance=false`를 유지한다.
패키지 앱, 실제 PLC/SPOT, 모든 운영 서비스 동시 가동 종료, 디스크 강제 손상, 현장 관찰은 미검증이다.

현재 서버 원본에 새 기능이 소급 적용되지는 않는다. 현재 원본의 무수정 인계 문제는 별도 HOLD로 남는다.
이 단계 이후의 단일 다음 조치는 검토한 로컬 변경의 commit·push·PR이다. 서버 인계/운영 적용과 구분한다.
