# D1 PR #196 저장 경로 보완

2026-09-29. PR 병합 전 자동 리뷰의 P1을 production writer 경로에서 재현하고 보완했다.
이는 후보 `830a89c`의 기존 패키지·현장 시험 이후 변경이다. 이전 후보의 실행파일 승인과 새 소스 검증을 구분한다.

## 재현과 최소 수정

이전 v2.3 헤더를 가진 base 파일과 이미 생성된 `_2_5_2.csv`의 v5 metadata가 함께 있으면,
기존 코드는 base의 열만 보고 schema-only 경로를 다시 선택했다. 그 경로는 v6 rule과 맞지 않아
writer를 열지 못했다. metadata 없는 populated schema target도 같은 실패를 보였다.
이는 격리 합성 재현이며 실제 현장 장애가 발생했다고 표현하지 않는다.

이제 operational rollover에서 base 열뿐 아니라 기존 schema-only target의 호환성도 확인한다.
그 target이 현재 rule과 맞지 않으면 `_2_5_2_temperature_operational_v6.csv`로 분리한다.
이미 호환되는 v6 schema-only target은 그대로 사용하며, 최종 rule target도 충돌하면 기존처럼 쓰기를 거부한다.
이전 CSV·metadata를 수정하거나 임의 숫자 suffix를 반복 생성하지 않는다.
Temperature 값·상태·cause·gate·validator와 sampling/timeout 정책은 변경하지 않았다.

## 실행 검증

개발 PC Windows 11, Python 3.12.6. 현재 worktree의 production 모듈을 import하고 임시 CSV만 사용했다.
`APPDATA`/설정은 격리 경로, `V2_MODE=MOCK`; 실제 장비 접속·운영 설정·데이터 변경 없음.
명령·환경·시간·exit code·원문은 `artifacts/temperature-diagnostics-reason-d1/pr196-*-command.json`과 해당 로그에 보존한다.

| 단계 | 실행과 결과 |
| --- | --- |
| 수정 전 | 신규 시험 3개 실행, writer loop의 v5/metadata 없음 두 경우 실패, exit 1 |
| 수정 후 D1 | `python -m unittest -v backend.tests.test_temperature_diagnostics_reason`: 13개 통과, 실패·skip 0, exit 0 |
| 전체 backend·관련 통합 | `python -m unittest discover -v -s backend/tests`: 839개 통과, 실패·skip 0, 169.884초, exit 0; 기존 F01 fixture 해시 검증 포함 |
| lint | `python -m ruff check backend`: 통과, exit 0 |
| typecheck | `python -m mypy`: 저장소 지정 8개 파일 통과, exit 0 |
| closeout QA | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_closeout_hang_reproduction.ps1 -SelfTest`: PASS, exit 0 |
| PR CI | 새 commit의 Windows artifact·운영 도우미 검사 결과는 [PR #196 Checks](https://github.com/zzocojoa/SmartFactoryLogger/pull/196/checks)에서 확인; 이전 HEAD의 성공으로 대체하지 않음 |

새 시험은 실제 `start → enqueue → stop`으로 두 행을 저장하고 정상 종료·행 순번·Count·v6 metadata를 검사한다.
기존 base·schema target·sidecar의 바이트 보존, 호환 target 재사용, 마지막 target 충돌 시 파일 보존을 확인한다.
첫 수정 후 시험은 정상 종료가 비우는 `_current_v2_csv_path`를 종료 후 참조하는 시험 오류가 있었다.
이를 실제 생성돼야 하는 파일 경로와 파일 수·행 내용 검사로 바로잡았다. 실패 로그를 보존하며 assertion을 삭제하지 않았다.
첫 관련 156개 시험과 이미 시작된 첫 전체 839개 실행에는 이 시험 오류 2개가 있었고,
위의 최종 13개·전체 839개 실행은 이를 바로잡은 소스에서 별도로 실행한 결과다.

읽기 전용 독립 정적 검토에서 차단 이슈 없음. 시험 실행은 주 작업자가 담당했다.
frontend/Electron production 코드는 변경하지 않았으며 PR CI의 패키지 검증과 기존 후보의 전체 검증을 구분한다.

## 승인·복귀 경계

사용자의 이번 승인은 PR 검토·병합 진행이다. 이 보완은 해당 리뷰 지적을 해결하는 직접 의존 수정이다.
기존 후보 `830a89c`와 NSIS 해시의 패키지·현장 기록 및 위험 수용은 그대로 보존한다.
이번에 새로 재현된 P1은 기존 현장 미관찰 한계 수용에 포함된 결함이 아니다. 보완 전 후보를 새 운영 배포본으로 선택하지 않는다.
새 코드·PR CI 실행파일을 기존 승인 후보로 자동 대체하지 않는다. 수정본 운영 적용에는 새 후보 identity와
변경 영향 검증을 다시 연결해야 하며, 이번 작업에서 설치·배포·장비 설정 변경은 수행하지 않는다.

위험은 파일 선택 경로에 한정된다. 데이터 이관은 없으며 충돌 시 오류 기록·append 거부를 유지한다.
운영 서버는 검증 후 복귀한 원본을 유지하고, 기존 원본 복귀 수단을 바꾸지 않는다.
