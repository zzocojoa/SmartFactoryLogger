# 출시 환경 사전 검증 — 종료 timeout 원인 미확정

2026-10-13. 출시 잠금 의존성 40개를 새 격리 환경에 설치·검증했다. 최신 backend 실행은
919개 통과/기존 비공개 fixture 1개 건너뜀, actual exit 0이다. 앞선 전체 실행 두 번의
종료 receipt timeout 원인은 미확정이며 제품 수정 완료나 출시 통과로 판단하지 않는다.
전체 목표 active, R1–R6 HOLD, full_data_gate=NOT_EVALUATED를 유지한다.

## 환경 차이와 검증 범위

Python 3.12.6에서 `backend/requirements-windows-release.lock`을 복사하고
`pip install --require-hashes --only-binary=:all:`로 새 `release-env`를 만들었다.
40개 wheel의 설치 보고서 SHA256이 잠금 파일 허용값에 포함되는지 및 설치 버전을 대조했다.
bootstrap pip는 잠금 대상 밖으로 구분했다. 잠금 파일 SHA256:
`e02cbc44a097eccc93f2986e023bee57881b52a1f6ee28c81f86a953a9bb0672`.

| 패키지 | 기존 개발 환경 | 출시 잠금 |
|---|---|---|
| annotated-doc | 0.0.4 | 0.0.5 |
| annotated-types | 0.7.0 | 0.8.0 |
| certifi | 2026.6.17 | 2026.7.22 |
| fastapi | 0.139.1 | 0.141.1 |
| greenlet | 3.5.3 | 3.5.4 |
| packaging | 26.2 | 26.3 |
| playwright | 1.61.0 | 1.62.0 |
| uvicorn | 0.51.0 | 0.52.1 |
| websockets | 16.1 | 17.0.1 |

이 차이 때문에 이전 개발 환경의 health/성능 결과만으로 최종 출시 환경을 검증했다고
판단하지 않는다. 특정 패키지가 timeout을 유발했다는 인과도 확인하지 않았다.
기존 개발 환경의 40개 비교 대상 버전은 변경되지 않았다.
새 환경 생성·해시 잠금 설치·pip check·backend Ruff·mypy(9개 source)는 각각 actual exit 0이다.
83개 backend source, 15개 build/의존성 입력, 기존 health 결합 8개 파일과 untracked 6개,
비문서 diff 및 HEAD의 동일성을 검산했다. 제품·서버·운영 설정은 변경하지 않았다.

## 실패와 후속 실행

| 실행 | 검사 수 / unittest 결과 | 실제 프로세스 exit |
|---|---|---:|
| initial-encoding-override | 920 / FAILED (errors=14, skipped=1) | 1 |
| corrected-focused | 7 / OK | 0 |
| corrected-full | 920 / FAILED (errors=1, skipped=1) | 1 |
| custom-full-diagnostic | 920 / OK (skipped=1) | 1 |
| original-cli-with-timeout-snapshot | 920 / OK (skipped=1) | 0 |

첫 도우미는 UTF-8을 강제해 Windows PowerShell 5.1의 한국어 cp949 출력 해석에 실패했다.
14개 오류 중 attestation 관련 13개는 이 도우미 설정 오류였다. 새 후속 실행에서 강제 설정을
제거했고 해당 6개 메서드와 종료 검사 1개가 통과했다. 원래 실패 로그는 수정하지 않았다.

별도로 `ImageShutdownEvidenceTests`의 다음 검사가 각각 첫 전체 실행과 수정된 전체 실행에서
3초 receipt 대기 timeout으로 실패했다. 내부 상태 로그에는 `EvidenceWriteTimeout`이 남았다.

- `test_control_waits_for_pending_peer_final_receipt`
- `test_cancel_pending_peer_wait_cannot_exit_successfully`

종료 모듈 31개, discovery 앞부분 246개, 실패 후 상태 수집만 추가한 246개 5회는 통과했다.
이후 전체 진단의 unittest도 919개 통과/1개 건너뜀이었지만 도우미가 skip의 TestCase 객체를
JSON으로 직렬화하지 못했다. child와 결과 판독 wrapper는 exit 1이며 partial JSON과 traceback을
보존했다. 이 실행을 정상 종료한 도우미로 보고하지 않는다.

마지막 `diagnose_cli.py`는 `unittest discover -s backend/tests`의 실제 CLI discovery·경고·실행
방식을 유지했다. 시작 시 현재 검사명을 기록하고, 기본 1초 evidence timeout이 발생해 이미
실패로 확정된 직후에만 상태·스레드 위치를 수집하도록 했다. 정상 처리와 timeout 값은 바꾸지
않았다. 920개/226.082초, `OK (skipped=1)`, actual exit 0이며 예상 밖 timeout 관측은 0이다.
이는 간헐 실패의 원인 규명이나 수정이 아니다. 반복 통과로 앞선 실패를 지우지 않는다.

건너뛴 기존 FactPolling F01 검사는 `TEMPERATURE_GOAL_PACKAGE` 비공개 fixture 미제공 범위다.
출시 환경에서 전체 `npm run health`, 최종 clean commit 빌드, installer 검증·설치·복구·현장
15분/120분 QA는 이번 실행에 포함하지 않았다.

## 의존성 감사와 남은 작업

실제 `npm audit --json`은 root high 1/moderate 8, frontend high 5/moderate 2로 모두 exit 1이다.
이는 이번 로컬 감사 출력의 분류이며 운영 공격 경로의 확인이나 의존성 수정 결과가 아니다.
패키지 버전·잠금 파일은 수정하지 않았다. 기존 http-cache-semantics 후속 증거도 유지한다.

재개 순서:

1. 실패 원문과 다음 재현의 timeout 순간 상태로 종료 지연 원인을 확인한다. 근거 없이 대기
   시간을 늘리거나 의존성 업그레이드 탓으로 단정하지 않는다.
2. 확인된 변경에 맞는 회귀 검사와 출시 환경 검증을 수행한다. 최종 clean commit·installer SHA256,
   payload/provenance를 확정한 뒤 필요한 설치·복구·실장비 QA를 진행한다.
3. 승인 실장비 프로파일/경계 비교, 과거 timeout/drop와 전체 데이터 처리, 브라우저 계측 OFF,
   실제 서버 시작 3회 등 기존 잔여 조건을 함께 유지한다.

미서명 내부 운영 정책 `NOT_REQUIRED_BY_APPROVED_UNSIGNED_POLICY`를 유지한다.
현재 운영·다음 롤백 기준 `541d701d544eea6a8a4e4836047077eaf9cfaf30` / installer
`08C061EE35A1A01788F05B00EE7395AA40774150C92C06726A92F3DF1BF75C3C`를 갱신하지 않았다.

## 증거 보존

[결과와 전체 실행 목록](C:/Users/user/Desktop/SmartFactory/PDCA_CANDIDATE_PREFLIGHT_20261013_349ab716/preflight-closeout.json),
[사용자용 결과](C:/Users/user/Desktop/SmartFactory/PDCA_CANDIDATE_PREFLIGHT_20261013_349ab716/RESULT.md)를 보존했다.
입력 627파일/5,690,299바이트의 기본 스트림을
ZIP 628개 항목과 대조하고 원본 재검산 및 공유 ZIP 동일성을 확인했다.
`release-env/` 설치 바이너리와 `cache/`는 명시적으로 제외했고 설치 보고서·잠금 파일·원문
로그·도우미·실패 결과는 포함했다. 작업 루트 자체를 봉인하거나 환경 전체를 백업한 것은 아니다.
ADS 검증도 아니다. 스냅샷 보존 actual exit 0.

- ZIP SHA256 `657f59ee60ad13b89826eb3075f3b38889c9831df617e0e3d38d48aa96dee189` (874,493바이트).
- manifest SHA256 `39616bf6d6d0e3647ee04b7dd66ba612c96fe370b3d5b756a9f18f84b8dd6bdb`.
- [로컬 ZIP](C:/Users/user/Desktop/SmartFactory/PDCA_CANDIDATE_RECORDS_20261013_349ab716/PDCA_CANDIDATE_PREFLIGHT_349ab716.zip).
- 공유 위치 `Z:/SmartFactory/20261013/records/PDCA_CANDIDATE_PREFLIGHT_349ab716`.
