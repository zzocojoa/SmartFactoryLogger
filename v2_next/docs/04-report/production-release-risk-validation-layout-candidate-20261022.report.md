# 초기 로딩 배치 수정 1.0.31 후보의 소스·패키지 검증

2026-10-22. 초기 로딩 카드 크기 미확보 수정이 실제 배포 파일에 포함되는지 확인했다.
새 후보의 소스 검사·미서명 빌드·전체 payload 대조·추출 백엔드 실행·추출 화면 회귀는 완료했다.
이 설치본의 실제 설치/복구와 현장 QA는 미완료이며 출시 HOLD·운영 승격 false를 유지한다.

## 대상과 변경 범위

- 기준 후보: `240a49522da5d59e9e823f62612e3d4207b497a9`, 1.0.30.
- 새 clean commit: `a7e5149b718f56d7dfa75df73bfba4a21d16a758`, 1.0.31.
- 작업 브랜치: `codex/layout-loading-candidate-20261022`.
- 변경은 화면6파일, 버전 식별5파일, 버전 일치 검사1파일이다. 잠긴 의존성의 내용은 그대로다.
- 기존 주 작업본의 다른 미커밋 변경은 포함하지 않았다. 새 작업본과 빌드 사본은 검사 전후 clean이다.
- installer: `C:/Users/user/Desktop/SmartFactory/C31BUILD_20261022_a7e5149b/source/v2_next/dist/smart-factory-logger-v2 Setup 1.0.31.exe`.
- installer 크기: 164,158,074 bytes.
- installer SHA256: `a10a59aa544a7bfa60e40778f05b89e3cc5be6da8ca284f94f740b6e6ae4a1dc`.

버전 검사값만 새 버전에 맞췄으며 과거 후보를 사용하는 시험 fixture의 버전은 바꾸지 않았다.
서명은 사용자 승인대로 불필요하다. 설치본·Electron·backend의 실제 상태는 NotSigned이며
이를 서명 PASS라고 표현하지 않는다. 설치 프로그램을 개발 PC나 서버에서 실행하지 않았다.

## 확인 결과

| 검사 | 결과와 범위 |
|---|---|
| `npm run health` | exit0. 의존성15, Electron103, frontend Node9+Vitest442 통과. backend963 중962통과·비공개 F01 fixture1skip. 타입·린트·QA selftest 통과 |
| 격리된 빌드 환경 | 잠금 wheel40개 일치, 설치 전후 소스 clean, 빌드 전후 의존성 버전 동일. 일반 사용자 실행이며 서버 설정 변경 없음 |
| 미서명 NSIS 빌드 | exit0. 코드·버전·출처 검산, module/DLL 출처3,624개 중 허용 범위 밖0 |
| EXE 내부 payload | exit0. 추출1,867파일이 unpacked와 크기·SHA256·집합 일치. 화면51파일이 Electron/backend 두 경로와 동일 |
| 추출 backend 실행 | exit0. 별도 AppData와 합성 loopback 장비로 health5요청 및 버전/commit 확인. 정상 종료0·잔류 프로세스/리스너0. 실제 장비·Electron 설치 시험이 아님 |
| 추출 화면 회귀 | exit0. 기존800ms 지연·같은 보존 응답·세 화면 조건에서 초기 위젯 배치 이동0. 아래 CLS와 원시 좌표/스크롤·오류 기록 보존 |
| 실행 후 보존 | payload1,867파일 전수 해시가 그대로이며 두 소스 사본 clean. 각 실행의 소유 job은 강제 종료 없이 active process0 |

| 화면 조건 | 수정 전240a CLS | 새 설치본 추출 화면 CLS |
|---|---:|---:|
| 624×549, 스크롤 없음 | 0.569707 | 0 |
| 624×549, 카메라로 스크롤 | 0.893620 | 0.032847 |
| 1280×800, 스크롤 없음 | 0.009020 | 0.009020 |

화면 시험은 개발 PC의 headless Chromium153.0.8010.12, 조건별5초다. pageerror0이며,
예상된 `/api/layout` 404 외의 요청은200이다. 세 스크린샷의 표시 값·카메라 영역도 확인했다.
과거 시각의 고정 응답을 재사용하므로 STALE 표시는 의도된 시험 입력의 결과다.
이 결과를 실제 화면의 장시간 연속성이나 실제3PC 성능 PASS로 확대하지 않는다.

PyInstaller는 `Hidden import "tzdata" not found` 경고를 남겼다. 현재 추출 backend의
시작·요청·정상 종료는 통과했으나 모든 시간대 동작을 검사했다는 뜻은 아니다.
이전 [로딩 수정 보고서](production-release-risk-validation-layout-loading-20261022.report.md)의
Chromium148.0.7778.96 표기는 오기다. 수정 전후 원시 result.json과 이번 실행 모두153.0.8010.12이며,
해시로 연결된 이전 보고서는 보존하고 이 문서에서 정정한다.

## 근거와 다음 작업

[종합 검산](C:/Users/user/Desktop/SmartFactory/C31REL_20261022_a7e5149b/candidate-review.json)
SHA256: `4161dc83b9a12207d5239513036beeb25afb23f6bbf336a50430e804592a9763`.
같은 폴더의 `clean-health-review.json`, `source-change-review.json`, 실행별 `summary.json`·
`terminal.json`, 원 로그와 도우미 변경 대조에 입력·출력 해시와 실제 종료 코드가 있다.
실행 명령은 `prepare_ntfs.py --run`, `build_isolated.py --run`, `verify_payload.py --run`,
`run_frozen.py --run`, `run_packaged_ui.py --run`이며 모두 exit0이다.

다음은 이 정확한 설치본의 실제 설치·업그레이드/복구 및 Electron 화면·정상 종료 확인이다.
기존에 준비한 시험 VM을 활용하고, VM 설치·인증부터 다시 시작하지 않는다. 이후 변경 영향과
계획에 필요한 현장 검사 범위를 결합한다. 기존240a의120분 결과를 새 설치본의 결과로 옮겨 적지 않는다.
실제3PC·물리 경계·과거 timeout/drop·전체 자료 및 최종 운영 승격 판단은 그대로 미완료다.
서버 전달·설치·앱 종료·설정 변경·추가 전체 백업·운영/롤백 기준 갱신은 이번에 하지 않았다.
