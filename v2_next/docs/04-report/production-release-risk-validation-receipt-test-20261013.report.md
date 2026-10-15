# 종료 영수증 동기화 검사의 시간 의존성 보완

2026-10-13. 실제 파일 처리 지연 때문에 본래 확인할 동기화 상태에 도달하지 못하던
검사 두 개를 보완했다. 변경은 `backend/tests/test_image_shutdown_evidence.py` 한 곳이다.
제품의 영수증 쓰기 제한 1초, 종료 실패 판정, 파일 동기화·해시·게시·읽기 검사는 그대로다.
호스트 파일 처리/스케줄링 지연의 하위 원인과 과거 서버 timeout/drop 원인은 미확정이다.

## 재현과 관찰

기존 clean 후보 `4cc7393e…`와 그 Python3.12.6 출시 잠금 환경에서 원래 검사와
I/O 경계의 경과 시간·timeout 직후 스레드 위치를 기록했다. deadline·결과를 바꾸거나
지연을 주입하지 않은 첫 두 진단은 다음과 같다.

| 실행 | 실제 결과 | timeout 관찰 |
| --- | --- | --- |
| 두 문제 검사 반복 | 37번째 검사 실패, exit1 | lifespan final 경로가 시험의 peer release를 기다리는 동안 1초 예산 소진 |
| 원래 CLI 전체 순서 | 920개 중919통과/F01 skip1, exit0 | 예상 밖 timeout0; 명시적 stall 검사의 timeout2는 보존 |
| 취소 검사 단독 반복 | 16번째 검사 오류, exit1 | control begin 검증이 끝나기 전1초 제한; 이후 테스트의3초 대기 timeout |

마지막 실패 순간 writer는 begin 영수증의 해시 sidecar를 읽기 위해 파일을 여는
경로에 있었다. 해당 `preserve_receipt` 호출의 측정 벽시계 시간은990.509ms였다.
전체 writer의 시작·스케줄링과 관찰 경계가 다르므로 이 수치를 정확한1초 대기 시간이나
순수 디스크 서비스 시간으로 해석하지 않는다. 단일 fsync만의 지연도 아니다.
원래 teardown이 writer 종료를 확인한 뒤 begin JSON/sidecar를 회수했다.
뒤늦은 begin 검증은 완료됐지만 `EvidenceWriteTimeout`, `receipt_verified=false`가
유지됐고 남은 writer0이었다. 실패를 성공으로 바꾸는 제품 결함은 관찰하지 않았다.

이전 전체 검사에서의 두 실패 로그에는 같은 I/O 세부 계측이 없다.
이번 재현은 같은 검사·실패 경로에 대한 새 증거이며 과거 호스트/서버 사건의 원인을
소급 확정하지 않는다. 첫 반복의 peer 대기는 시험이 의도적으로 넣은 조건이다.

## 최소 보완과 검증

두 검사는 상대 종료 경로가 아직 완료되지 않았을 때의 대기 순서와 취소 결과를 확인한다.
실제 파일 처리가 이 검사 목적과 무관하게 앱의 시간 예산을 소비하지 않도록 해당 검사
안에서만 `app.time.monotonic`을 고정했다. asyncio와 원래3초 대기 제한은 실제 시계를
사용한다. 겹친 작업의 최종 gather에도 실제3초 제한을 적용해 시계 고정으로 검사가
무한 대기하지 않게 했다. 명시적 deadline/stall·취소·실제 영수증 검사는 유지했다.

| 검증 | 실제 결과 |
| --- | --- |
| control begin 기록에1.15초 지연 주입 | 수정 전 두 검사 모두 오류/exit1 → 수정 후 두 검사 통과/exit0 |
| 계측 없는 두 검사50쌍 반복 | 100개 통과, exit0 |
| 기존 종료 영수증 모듈 전체 | 31개 통과, exit0; 명시적 timeout·실패 보존 검사 포함 |
| 출시 잠금 환경 backend 전체 | 920개 중919통과/F01 skip1, exit0 |
| 저장소 실제 `npm run health` | exit0; backend919통과/F01 skip1, Electron100, Vitest437, dependency15 및 나머지 health 단계 |
| 최종 기록 검산 | stdout/stderr9쌍의 전체 바이트·해시·종료 코드, 닫힌 실패 영수증·sidecar, 변경 메서드3곳을 대조, exit0 |

수정 전후 지연 주입은 원인 가설 확인용 합성 조건이며 생산 서버에 가한 부하가 아니다.
시험 후 실제 앱 시계 복원·제품 제한1.0초·writer 부재를 확인했다.
주요 원문은
[진단·검산](C:/Users/user/Desktop/SmartFactory/PDCA_RECEIPT_DIAG_20261013_2ec419bf/review.json),
[수정 전후 실행](C:/Users/user/Desktop/SmartFactory/PDCA_RECEIPT_DIAG_20261013_2ec419bf/delayed-terminal.json),
[최종 검사 실행](C:/Users/user/Desktop/SmartFactory/PDCA_RECEIPT_DIAG_20261013_2ec419bf/verification-terminals.json)에 있다.
관측 wrapper가 스케줄링에 영향을 줄 가능성은 남으며 계측 없는100회 반복을 별도로 확인했다.

## 설치본과 남은 범위

후보1.0.28의 제품/패키징 소스는 clean4cc7393e와 같다. 실제 설치본 SHA256을 다시 읽어
`8821746bbed47850ead68c66894e5580afac63483b1569865915dadc30cfc848`가 유지됨을 확인했다.
새 수정 테스트 SHA256은 `6fb59c26ac3511d25d277e08c38a06e1ce4b583217f5630f053efa7abc8602f4`다.
새 테스트 결과를 기존 source ZIP 안에 들어 있던 테스트 바이트의 결과로 혼동하지 않는다.
테스트만 변경했으므로 설치본을 재빌드하거나 기존 NSIS matrix를 반복하지 않았다.

서버·설정·원본 데이터·운영/롤백 기준은 바꾸지 않았다. 실제 운영/다음 롤백 기준은
541d701d/08C061EE이고, 후보의 [기존 설치·복구 결과](production-release-risk-validation-shutdown-image-20261013.report.md)는 유지한다.
미서명 내부 운영 정책을 적용한다. 남은 [전체 조건](production-release-risk-validation-current-gates-20261013.report.md)은
browser/CDP OFF·실장비 승인/경계·과거 원인/처리·서버 시작/최종 현장 QA·승격이다.
R1–R6 HOLD, full_data_gate=NOT_EVALUATED, 목표 active를 유지한다.

## 2026-10-16 후속 3초 대기 오류의 재현 조사

1.0.29 관찰 도우미 검증 중 발생한 `wait_control_receipt`의 3초 TimeoutError를
clean `b87ab8f2f97ef02fdd49841797a895e9db38eb11`에서 조사했다. 제품·시험 소스,
시간 제한, 성공/실패 판정은 변경하지 않았다. 원래 실패 로그 SHA256은
`266311c4b93a0bb32c49a54731f9dbb9d5f2e5853718dd9511fd4f075c488e64`다.

개발 PC의 `PDCA_RECEIPT_RECHECK_20261016_cba9a28d/diagnose.py`는 실제 영수증
I/O 경과 시간과 실패 시 취소 전 스레드/async 작업 상태를 수집한다. 기존 시험 자체의
의도적인 장애 외에 추가 지연은 주입하지 않는다. 격리 MOCK 설정과 관찰 wrapper가
실행 환경·스케줄링에 영향을 줄 수 있으므로 정식 health 명령도 별도로 확인했다.

| 확인 | 결과 |
| --- | --- |
| 문제의 취소 시험 100회, 진단 계측 포함 | 100개 통과, 13.792초, exit 0; 예상 밖 timeout 관찰 0 |
| 전체 backend 순서, 같은 계측 포함 | 932개 중 931통과·F01 skip 1, 277.836초, exit 0 |
| 계측 없는 `npm.cmd run health` | 모든 단계 완료, exit 0; backend 932개 중 931통과·skip 1, 300.064초 |
| 최종 근거 검산 | 21개 파일의 크기·해시 및 소스 일치 확인, exit 0 |

전체 계측의 관찰 3건은 기존 의도적 취소 1건과 begin/final stall 2건에 정확히 대응했다.
문제의 취소 시험은 전체 순서에서도 약 139.85ms로 통과했다. 두 계측 실행 뒤 영수증
writer는 남지 않았고 소스 해시도 같았다. 정식 health에는 dependency 15개,
Electron 100개, frontend 보조 9개·Vitest 437개, 타입/린트와 QA self-test가 포함된다.
비공개 F01 입력이 없어 기존 skip 1개는 유지하며 Starlette deprecation 경고도 남아 있다.

근거는 [review.json](C:/Users/user/Desktop/SmartFactory/PDCA_RECEIPT_RECHECK_20261016_cba9a28d/review.json)
(9,294 bytes, SHA256 `d5036144384adcd835219081fad0f7b2221f00068df835a5d46e1673f625e66e`)과
같은 폴더의 `review-check.json`, `health-terminal.json`, 원문 로그다.
최초 검산 명령은 JSON 저장 후 tuple/list 비교 차이로 exit 1이었으며, 저장된 내용을
재작성하지 않고 독립적으로 읽어 검산한 결과는 exit 0이다.

이번 실행에서 오류는 재현되지 않았다. 앞선 전체 health 실패와 원인 미확정 상태를
해결됐다고 바꾸지 않는다. 서버의 15분 실행 요청은 대기 중이며 이 로컬 결과로 현장
15분/120분, 전체 데이터 QA, 물리 경계 시험 또는 운영 승격을 통과 처리하지 않는다.
새 설치·전체 백업·운영 설정 변경은 없으며 정식 출시 HOLD와 목표 active를 유지한다.
