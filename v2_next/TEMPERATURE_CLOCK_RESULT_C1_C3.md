# Temperature C1~C3 결과

2026-09-21. **로컬 코드 보완 완료. 현장 검증·운영 승격 완료를 뜻하지 않는다.**

브랜치 `codex/temperature-remediation-20260909`, HEAD `376618267aa52c822e1692d50de637d657ddf28e`.
첨부 감사 기준과 같은 HEAD에서 시작했다. 변경은 미커밋 로컬 diff이며 staged 변경은 없다.
이번 범위에서 commit/push/PR 변경/merge, 후보 빌드·설치·배포, 실 PLC/SPOT 접속,
운영 데이터·설정·OS 시각 변경은 수행하지 않았다.

## 수정과 확인 결과

| 구분 | 재현한 합성 조건 | 최종 동작 | 상태 |
|---|---|---|---|
| C1 | interval 0.2초, read 0.01초, wall −60초에서 wait 60.19초. 동일 UTC 신규 표본 하나 enqueue 누락 | wait 0.19초 유지. 내부 증가 순번으로 새 표본 구분. 두 loop 정상/예외 wait가 stop Event에 응답 | 수정·검증 완료 |
| C2 | 완전한 이전 PLC 원천, 실제 10.5초 경과·wall −10초에서 age 500ms/usable | 원천 완료와 통합 표본 채택의 동일 domain monotonic 차이 10500ms, unusable. 채택 후 처리 지연은 age를 변경하지 않음 | 수정·검증 완료 |
| C3 | 실제 poll 200ms에 wall −60/+60초일 때 duration 0/60200ms | 원래 poll context 시작~완료로 200ms. UTC는 역순이어도 원문 의미 유지. 미검증 duration은 공백과 사유 | 수정·검증 완료 |
| 기존 G1~G5/T1~T3 | TTL·센티널·부분응답·metadata·Count0~2·writer/identity 등 | 현재 변경본의 전체 backend와 계약 시험에서 재검증 | 보존 확인 |

위 수치는 모의 transport와 독립 clock을 사용하는 현재 production 모듈의 시험이다.
실제 현장 장애나 과거 CSV의 실측 사건으로 주장하지 않는다. C1~C3는 모두 새 보완이 필요했으며,
기해결로 닫은 C 항목은 없다. 첨부의 전사된 probe는 실행 근거로 대체하지 않았다.

## 구현과 공개 계약

- `service.py`: monotonic cadence, 중단 가능한 정상/1초 retry 대기, lifecycle lock와 미종료 thread 재시작 거부. 신규 표본 식별은 내부 순번, 공개 감사 시각은 UTC 유지.
- `real_plc.py`, `freshness.py`, `schemas.py`, `process_phase.py`, `repository.py`: source 완료 monotonic/domain을 payload·오류와 같은 snapshot에 보존하고 `read_data`의 snapshot lock에서 채택 시각을 고정. service/model_copy/queue/repository와 직접 helper가 같은 proof를 검증한다. 내부 필드는 공개 JSON에서 제외되며 replay에 없는 proof를 생성하지 않는다.
- `spot_api.py`, `spot_diagnostics.py`: 원래 poll 시작 monotonic/domain을 성공·sentinel·timeout·connection·HTTP·config-missing 완료 경로로 전달. publisher 진입 지연을 duration에 더하지 않는다. startup/취소된 미완료 poll은 완료 fact를 만들지 않는다.
- `spot_observation_fact.py`, CSV/replay/validator/PowerShell QA: `spot_poll_duration_status`와 `spot-poll-duration-monotonic-v1` metadata 추가. CSV **2.3.1/2.4.2/2.5.2**, fact **1.4.0**. `ok`이면 유한 비음수 ms, 그 외는 공백·사유. 유효한 실제 0ms는 허용한다. duration의 시작/domain 이상만으로 정상 Temperature를 지우지 않는다.
- 구 CSV header는 새 파일로 rollover하고, 구 fact는 기존 archive 경로로 보관한다. 역사 fact **1.3.0/1.2.1**의 header·manifest·epoch duration 해석을 유지한다. 1.3.0의 기존 provenance 검사도 계속 적용한다. V1 형식은 변경하지 않았다.

25개 tracked 파일 수정과 신규 6개 파일의 정확한 목록·내용·해시는 `artifacts/temperature-clock-c1-c3/FILES.json`,
`review-files/`, `full.patch`에 있다. 신규 테스트 3개는 `.gitignore` 예외로 제출 대상임을 확인했다.

## 실제 검증 결과

Windows, Python 3.12.6, 저장소 backend 가상환경과 설치된 npm 의존성을 사용했다.
장비 경계는 모의 transport/loopback이며 clock은 모듈 단위로 대체했다.
`APPDATA`, `SFL_CONFIG_PATH`, `V2_MODE=MOCK`를 자식 프로세스에 제한했다.
`npm run health`의 backend runner는 추가로 저장소 `.tmp_test_appdata`를 사용한다.
PowerShell QA는 Windows PowerShell 5.1 모듈 경로를 자식 환경에 명시했다.

| 최종 검사 | 실제 결과 | 원문/영수증 |
|---|---|---|
| 신규 C1/C2/C3 production 경로 | 23 pass, 0 fail, 0 skip (C1 7, C2 8, C3 8) | `clock-final.txt/.json` |
| 영향받은 통합·계약 시험 | 182 pass, 0 fail, 0 skip | `affected-contracts-r2.txt/.json` |
| 전체 backend (G1~G5/T1~T3·종료·drain 포함) | 818 pass, 0 fail, 0 skip, 151.837초 | `health-final.txt`, `health-final.json` |
| Electron 시작·종료 계약 | 94 pass, 0 fail, 0 skip | 같은 health 원문 |
| frontend 지원 Node 검사 / Vitest | 9 pass / 39파일 291 pass | 같은 health 원문 |
| frontend typecheck·lint / backend Ruff·mypy | 모두 pass, mypy 8 source files | 같은 health 원문 |
| NSIS operational-ready·startup trace·closeout·서명·workflow 계약 selftest | 모두 pass | 같은 health 원문 |
| 전체 `npm run health` | exit 0, 13:11:36~13:15:23 KST | 같은 health 영수증 |

실행 명령은 `backend/.venv/Scripts/python.exe -m unittest ...`와 `npm.cmd run health`이며,
전체 인자·cwd·환경·시작/종료·종료코드는 실행별 JSON 및 `CHECKS.json`에 보존했다.
첨부 요구 21개 case의 실제 함수 대응은 `TEMPERATURE_CLOCK_REGRESSION_MATRIX_C1_C3.json`에 있다.
이전 실행 수나 이전 7시간 관찰 결과를 현재 diff의 통과 근거로 사용하지 않았다.

## 실패 재현과 검토 보완

각 before 원문은 보존했다. C1-before는 6개 method/10개 실패 subcase, C2-before는 7개 method/42개 실패와 2개 오류,
C3-before-r2는 3개 method/35개 실패와 18개 오류를 기록했다. 이것을 독립 결함 수로 세지 않는다.
C2/C3 일부 대조군의 미세한 epoch float 오차와 새 필드 부재도 포함된다.
첫 C3-before는 fixture의 잘못된 설정명으로 setup 실패한 실행이며 결함 재현 근거로 사용하지 않는다.

초기 전체 backend는 812개 중 11개 실패했다. 새 status/버전을 반영하지 않은 합성 fixture와
EMA의 `6628.000000000001`을 정수에 완전 일치 비교한 시험을 보완했다. 안전 검사 삭제 없이
선언된 clock proof/측정 status를 fixture에 추가했고 EMA는 근사 비교로 변경했다.

읽기 전용 독립 검토 3개를 수행했다. C2 비정상 UTC가 runtime 상태를 오염시킬 수 있는 guard 누락,
C3 기존 diagnostics snapshot과 문자열 완료 endpoint 조합의 게시 예외,
C1 정상 대기 fixture의 필수 Time 누락을 각각 보완했다. 마지막 C1 정상 wait 4.5~5초와 오류 retry 1초를
명시적으로 구분하며 stop/restart를 검사한다. 최신 diff에 남은 차단 결함은 없다는 판정을 받았다.
검토자들은 코드를 수정하거나 시험을 실행하지 않았으며 주 작업자가 실행을 책임졌다.
상세는 `INDEPENDENT_REVIEW.md`에 있다.

## 위험과 범위 밖 항목

위험도는 높음: 생산 판정용 source gate와 기록 계약을 수정한다. PLC proof가 없으면 자동 상태·phase는
fail-closed하고 정상 SPOT/over-range 처리는 독립 유지한다. 새 duration status가 관측 가능성을 보완한다.
잘못된 clock proof는 공백/unknown으로 드러나며 정상 값으로 숨기지 않는다.

데이터 변환 migration은 없다. 새 실행 시 schema rollover가 발생하며 과거 파일·바이트는 유지된다.
현재는 배포하지 않았으므로 운영 복귀 작업은 필요하지 않다. 코드 복귀 기준은 시작 HEAD `3766182`이며,
향후 배포 시에는 새 schema 파일을 보존하고 승인된 이전 번들로 복귀해야 한다. 이번 작업은 복귀 설치를 검증하지 않았다.

동기 read/I/O 자체의 강제 중단은 보장하지 않는다. 미종료 thread가 있으면 stop=False와 restart 거부로 드러낸다.
기존 interval·retry/backoff·phase dwell·장비 통신·G4 writer 정책을 재설계하지 않았다.
controlled snapshot generation 시험은 동기화된 20세대를 확인하며 무한 경쟁 상황의 정형 증명은 아니다.

비차단 후속 항목: offline validator는 CSV/fact 각각의 duration/status 형식과 metadata를 검사하지만
같은 observation key의 두 파일 사이 duration 수치까지 대조하지 않는다. 실제 production publisher→두 출력의
일치는 이번 신규 시험이 확인한다. 이 추가 offline join 검사는 별도 보완 후보이며 제품 경로 결함으로 판정되지 않았다.

새 실장비·7시간·자정 시험, 후보 빌드·운영 승격은 이번 목표 밖이므로 미실행이다.
기존 private 자료 시험은 이번 환경에서 skip 없이 실행됐지만, 새 clock 사건을 과거 CSV에 합성하지 않았다.
이전 G/T 보고서 5개와 기존 untracked 34개의 SHA256 불변을 `PRESERVATION.json`으로 확인한다.

다음 조치는 **로컬 diff와 이 검증 묶음의 검토**다. 이번 코드 목표 종료 후 새 개발·장비 시험·Git 게시를 자동 진행하지 않는다.
