# P2 NSIS 서버 사전점검 준비

> **후속 결과 — 2026-09-23:** [실제 120분 서버 설치 검증과 원본 복귀](temperature_p2_nsis_120min_trial_20260923.md)가 완료됐다.
> 아래 내용은 단계별 작성 시점의 기록이며, 정식 운영 승격과 구분한다.

2026-09-22. 새 읽기 전용 사전점검 묶음 `P2_IP1`을 준비하고 개발 PC와 Z 전송 사본을
파일별 SHA256으로 검증했다. 원격 UI 도구의 초기화 오류로 서버 최종 폴더 복사와 새 서버
사전점검은 미완료다. 서버 설치·정상 종료·재시작·운영 승격은 수행하지 않았다.

## 범위와 식별

후보 commit은 `d254871f89c98154b4e32879e29601df78f7e159`, 원본은
`d7a1b20f96711fb07fc7add0867e79ee36506fce`다. 표시 버전은 모두 1.0.26이며
릴리스 구분은 `UNSIGNED_INTERNAL`이다. 기존 바이너리·소스·설정은 변경하지 않았다.

기존 해시 결합 묶음 `P2_F1`을 변경하지 않고 새 사전점검 도우미를 만들었다.
기존 프로세스·원본 전체 설치 파일·설정·3회 수집 진행 확인을 유지하고 다음을 추가했다.

- 후보와 복귀 installer 원문 해시 및 격리 NSIS 시험 증거의 고정 해시 대조.
- 실제 NSIS 계약에 따른 HKCU 설치 경로·uninstall 등록 확인과 중복/다른 경로 차단.
- fact 파일의 제한된 직계 목록과 원본 54열 헤더 해시 확인. 누적 원문 전체 스캔 없음.
- 설치·복귀 순서, 정상 종료 실패 시 HOLD, schema 변경 시 archive 보존 대조를 문서화.

실제 설치·복귀 실행 런처는 새 서버 영수증과 운영 중단/복귀 조건에 결합해야 하므로
아직 발행하지 않았다. 이 묶음에서 실행 가능한 단계는 읽기 전용 `READ_PREFLIGHT.cmd`다.
현재 서버 결과가 없는 상태를 설치 준비 완료로 처리하지 않는다.

## 이번 검증 결과

| 검증 | 결과 |
|---|---|
| PowerShell 5.1 경계 시험 | 39 pass / 0 fail / 0 skip |
| 런처·개발 PC 차단·읽기 전용 registry 실행 | 6 pass / 0 fail / 0 skip |
| 준비·시험·전송 Python의 Ruff F/E9 | exit 0 |
| 이전 작업본 파일 | 39개 해시 불변 |
| 기존 격리 NSIS 원문 | 1,207개 해시 불변 |
| 개발→Z 전송 | 18개, 329,781,379 bytes, 파일별 해시 일치 |
| 서버 최종 복사·새 서버 사전점검 | 미실행: 원격 도구 초기화 오류 |

실제 helper 함수와 검증된 NSIS 산출물/합성 CSV를 사용했다. 현재 서버에 접속한 시험이 아니다.
변조·누락 helper, 다른 계정, 잘못된/중복 registry, 다른 schema 및 같은 열 수의 잘못된 헤더,
헤더·파일 목록 한도, 정체된 poll·장비 snapshot과 기존 결과 덮어쓰기를 차단하는지 확인했다.
개발 PC에서 실제 helper의 `-Execute`는 `host / server-user-required`로 첫 서버 점검 전에
종료코드 1을 반환했다. 기본 실행은 PREPARED ONLY이며 새 결과 폴더도 만들지 않았다.

원문 명령·환경·종료코드는 개발 증거 루트의 `validation-commands.json`, `boundary-tests.log`,
`launcher-tests`에 기록했다. 전송 준비 첫 실행은 UTF-8 JSON을 Windows 기본 cp949로 읽다가
복사 전에 중단됐다. 명시적 UTF-8 읽기로 고쳤고 이후 전수 검증과 전송이 완료됐다.
제품 테스트 assertion 또는 제품 코드는 수정하지 않았다.

이번 diff는 자체 검토했다. 실제 제품/설치 바이너리에 변경이 없어 기존 exact-commit health와
격리 NSIS 증거를 보존했고 제품 전체 QA를 다시 실행하지 않았다.

## 전달 상태와 해시

개발 묶음: `C:\Users\user\Desktop\SmartFactory\P2_IP1`.
검증된 공유 사본: `Z:\SmartFactory\20260922\send\P2_IP1`.
서버 예정 경로는 같은 바탕화면 `SmartFactory\P2_IP1`이며 **아직 실제 존재를 확인하지 못했다**.

Helper SHA256:
`E92081469D5D849DC186F3243A806BAE55FBF3604A33DE84D718D6D8E2D3E71E`.

전송 manifest SHA256:
`3BB0C1996C1D16BD836686E42595DD34AA91E719055F8887E534B0D3C5E49CC8`.

개발 증거: `C:\Users\user\Desktop\SmartFactory\P2_INSTALL_PREP_R1`.
공유 영수증: `Z:\SmartFactory\20260922\records\P2_IP1-transfer-pending.json`.
서버 최종 경로·파일·해시 확인 필드는 모두 false다.

## 남은 단계와 운영 영향

원격 도구는 `failed to write kernel assets: 지정된 경로를 찾을 수 없습니다. (os error 3)`를
반환했다. CUA 초기화, 세션 reset 후 재시도, Computer Use 초기화가 모두 실패했다.
도구 복구 후 Codex가 공유 사본을 서버 최종 폴더까지 복사하고 실제 경로·파일을 확인한다.
파일 전송 책임을 사용자에게 넘기지 않는다. 이후 읽기 전용 실행 결과를 회수해 검토한다.

사전점검은 새 결과 폴더만 쓰므로 운영 데이터 이관이나 되돌릴 제품 변경이 없다.
향후 설치는 운영 중단 위험이 있어 정상 종료·drain·closeout과 파일 보존 검증이 필수다.
복귀 경로는 격리 환경에서 검증한 원본 installer 재설치이며, 실제 서버 복귀는 아직 미검증이다.
전체 CSV/이미지 백업, 강제 종료, 자동 롤백, 보안 설정 우회는 실행 경로에 포함하지 않는다.
관측 결과는 새 receipts로 남기며 기존 필드/스키마 의미와 과거 증거를 덮어쓰지 않는다.

이전 [격리 NSIS 결과](temperature_p2_nsis_installation_20260922.md),
[10분 portable 현장 시험](temperature_p2_ten_minute_trial_20260922.md),
[서버 경로·전달 정책](server_validation_path_policy.md)을 보존한다.
이번 단계에서 commit/push/PR/merge는 수행하지 않았다.


## 2026-09-23 서버 최종 복사 완료

Codex 앱 재시작 후 원격 제어 도구가 복구됐다. 공유 사본의 18개 파일을 다시 SHA256 대조한 뒤,
Chrome 원격 데스크톱의 서버 탐색기 Copy/Paste로 새 `P2_IP1` 폴더를 복사했다.
서버 주소 표시줄에서 `C:\Users\user\Desktop\SmartFactory\P2_IP1`을 확인했고,
상위 파일 9개, basis 7개, installers 2개의 존재를 화면에서 확인했다.
기존 폴더 덮어쓰기나 파일 이동·삭제는 수행하지 않았다.

서버의 `READ_PREFLIGHT.cmd`를 선택한 탐색기 창을 남겼다. 서버 로컬 파일의 해시 검증과
읽기 전용 사전점검은 아직 실행 전이며, 화면 확인을 해시 검증으로 보고하지 않는다.
Computer Use 지침의 터미널 UI 실행 제한 때문에 도우미 실행만 사용자에게 전달한다.
앱 종료·설치·재시작·작업정보 변경은 수행하지 않았다.

07:56~08:02 서버 화면에는 Running, Count 0과 작업정보 필수값 미입력, SPOT STALE 표시가
보였다. 이 관찰을 장비 장애나 현재 commit 확인으로 해석하지 않으며, 새 사전점검 영수증으로
프로세스·설치본·수집 증가를 확인할 예정이다. 과거 확인된 제품/금형 값은 입력하지 않았다.

새 개발 영수증: `Desktop/SmartFactory/P2_IP1_DELIVERY_20260923_R1/server-delivery.json`.
공유 영수증: `Z:\SmartFactory\20260923\records\P2_IP1-server-delivery.json`.
9월 22일 전달 미완료 영수증과 이전 보고서 사본은 그대로 보존했다.
다음은 도우미 실행 결과 회수·검토이며 실제 설치·복귀 실행 도우미 결합은 그 후다.

## 2026-09-23 사전점검 결과 확인

사용자가 실행한 서버 도우미에서 `READ_ONLY_NSIS_PREINSTALL_PASS`, `[CHECK EXIT] 0`을
확인했다. Codex가 결과 24파일을 서버 탐색기로 공유 return 폴더에 복사하고 개발 PC로
회수했다. JSON 12개와 각 해시, 콘솔에 표시된 result SHA256을 대조했다.
result SHA256은 `D2E49F47A17E994EABF89E72F82024F39E262B492CF7E04525256A919B40A143`이다.

원본 설치 1,646파일·트리 해시·설정 해시가 기준과 일치했다. 08:07:10~08:07:42의
3회 표본에서 같은 logger/service 세대의 저장 행은 294,386→294,545(+159),
SPOT poll은 60,321→60,353(+32)로 증가했다. driver/service thread와 fresh poll,
저장·연결·판정 오류 카운터 0을 확인했다. 원본이 제공하지 않는 observation_writer의
null 필드를 0 또는 정상으로 해석하지 않았다. 자체 검토 37항목 통과, 실패 0이다.

SPOT `fingerprint_mismatch`, operator/comparator false는 이전 portable 시험과 같은
기존 제한이다. 설정을 고치거나 검증 완료로 승격하지 않았다. 현재 fact는
4,873,011,439바이트·54열이고 기존 schema archive는 488,471,940바이트다.
사전점검에서는 헤더·직계 목록만 읽었으며 전체 해시·백업·닫힌 파일 보존 검증은 하지 않았다.

사용자는 새 NSIS 후보 관찰 시간을 **120분**으로 선택했다. 설치·정상 종료·원본 복귀 시간은
별도이며, 이 시간 선택을 서버 설치 실행 승인으로 확대하지 않는다. 새 실행 도우미는
이 결과에 결합해 격리 검증 중이다. 서버 원본 앱 종료·후보 설치·시작은 아직 수행하지 않았다.

회수: `Z:\SmartFactory\20260923\return\P2_IP1_RESULT\results-20260923-080619-a4cb68`.
개발 검토: `Desktop/SmartFactory/P2_IP1_PREFLIGHT_REVIEW_R1/review.json`.
원본 증거와 이전 보고서 사본을 보존했다. 실제 120분 현장 검증·운영 승격은 미완료다.


## 2026-09-23 120분 실행 묶음 준비 완료

사용자가 선택한 후보 관찰 120분(7,200초)을 새 `P2_N120` 도우미에 결합했다.
후보 `d254871` 및 복귀 원본 `d7a1b20`의 기존 미서명 installer를 재빌드 없이 사용한다.
지정 서버·일반 사용자·사전점검 24시간 이내·원본 PID/시작시각·설정·설치 파일을 실행 직전
확인한다. 원본 정상 종료 → 후보 설치/시작 → 120분 관찰 → 후보 정상 종료 → 원본 재설치/
재시작/수집 증가 확인 순서다. 설치·해시 확인·종료·복귀 시간은 120분에 포함되지 않는다.

설정/작업 상태 5파일은 합계 5MiB, Electron 선택 profile 파일은 64개·합계 16MiB 이내만
보관한다. 전체 CSV·이미지·과거 로그·캐시 백업은 하지 않는다. 닫힌 fact와 변경되지 않아야
하는 schema archive는 원문 SHA256을 순차 읽어 비교한다. fact 계열 8파일·합계 8GiB,
각 해시 단계 240초 한도로 디스크 읽기 부하가 있다. 서버의 4.87GB fact에 대한 실제 전체
해시는 아직 미실행이다. 현장 한도 초과/오류/미종료 시 HOLD하며 강제 종료·반복 설치·실패
후 자동 복구 설치를 하지 않는다. HOLD 단계에 따라 수집이 중단된 채 남을 수 있다.

### 실제 실행한 격리 검증

- Windows 개발 PC의 native PowerShell 5.1 경계 검사 41 통과/0 실패, Python 런처 검사
  5 통과/0 실패, 관련 Python ruff 통과. 실제 명령·환경·종료코드는
  `P2_N120_PREP_R1/final2-validation-commands.json`과 대응 원문 로그에 있다(모두 exit 0).
- 네트워크를 차단한 Windows Sandbox의 일반 사용자 토큰에서 실제 NSIS·패키징된
  production driver/service/writer/UI를 실행했다. 외부 장비는 loopback 합성 transport다.
  전체 절차 169.054초, 후보 실제 관찰 약 79.397초/6표본이며 QA 관찰 clock만 96배로
  가속했다. 배포 도우미의 실제 현장 clock은 1배다. 이 증거는 실제 120분 안정성 시험이 아니다.
- 최종 자체 검토 113 통과/0 실패. 실제 두 설치/정상 종료/원본 복귀, process exit 0,
  후보 9개 종료 단계, small state 보존, schema 전환 archive 원문 해시, closed CSV와
  metadata/fact manifest를 확인했다. 실제 build 소스의 `validate_csv_v2_shadow.py` exit 0.
  누적 image fact에서 후보 종료 시점 원문 prefix를 추출하되 종료 manifest SHA256 일치를
  먼저 증명했고, validator에 당시 manifest를 명시해 strict count/hash 검사를 유지했다.
- QA 앱·backend·fixture·시험 포트를 정상 정리한 뒤 Sandbox를 종료했다. 강제 종료 없음.
  이전 실패 시도(관리자 token 차단, 합성 transport 오류, QA 영수증 이름 충돌, 잘못된
  PSModulePath, 최초 validator 입력 경로 문제)와 수정 전 결과를 보존했다. 각 실패가
  안전하게 HOLD한 결과를 성공으로 덮어쓰지 않았다.

검토는 자체 검토다. 제품 코드/바이너리를 수정하지 않아 backend/frontend/Electron 전체
회귀를 이번 단계에 다시 실행하지 않았다. 이전 exact-build QA와 NSIS 증거 1,207파일,
저장소 선행 변경 39파일의 동일 해시를 확인했다. 과거 테스트 수를 신규 실행으로 합산하지
않았다. V1 비교는 기존 fixture에서 비활성이므로 미실행이고, 선택 위치 필드 미수집 warning은
validator 원문에 남아 있다. 실장비 NSIS 설치·복귀 및 실제 120분 관찰은 아직 미검증이다.

### 서버 최종 전달과 실행 인계

개발 `C:\Users\user\Desktop\SmartFactory\P2_N120`의 10파일/329,566,903바이트를
`Z:\SmartFactory\20260923\send\P2_N120`에 복사하고 모든 SHA256을 대조했다.
Codex가 Chrome 원격 데스크톱의 탐색기로 서버 바탕화면에 최종 복사했다. 서버 주소 표시줄의
`C:\Users\user\Desktop\SmartFactory\P2_N120`, 상위 파일 8개와 installers의 2파일을
화면에서 확인했다. 화면 확인은 서버 로컬 해시 검증이 아니다. 서버 실행 때 첫 변경 전에
고정 helper/installer/manifest와 원본 상태를 검증한다. 기존 폴더 덮어쓰기·이동·삭제 없음.

Helper SHA256: `4D9C14CAF926DD401D311038060862141710F6A93EBC4427DF26F71F5F9DEE89`.
Transfer manifest SHA256: `FE59058F96774C59F5063A726A30821B2299C230C82FFC7ABD0508128CF1A5F4`.
전체 준비/시험/검토 증거: `C:\Users\user\Desktop\SmartFactory\P2_N120_PREP_R1`.
최종 전달 영수증: `Z:\SmartFactory\20260923\records\P2_N120-server-delivery.json`.

실행 파일은 서버의 `RUN_120_MINUTES.cmd`다. 실행하면 앞서 설명한 실제 수집 중단/설치/
관찰/원본 복귀가 진행된다. Computer Use 지침의 terminal UI 실행 금지에 따라 사용자에게
마지막 실행을 인계한다. 한 번만 일반 사용자로 실행하고 콘솔을 유지한다. 아직 서버 앱
종료·설치·시작은 수행하지 않았고 원본 Running 화면을 확인했다. 현재 UI 당시 제품·금형를
읽기만 했으며 사용자 확인 없이 수정하지 않았다. 결과는 새 Desktop/SmartFactory/N120-<ID>에
남는다. 다음은 사용자 실행 후 서버 결과 회수와 판정이다. 이번 단계는 운영 승격이 아니다.

복귀 경로는 성공한 관찰 뒤 동일 원본 installer 재설치다. 자동 schema archive 54→55→54
전환과 보존 여부가 핵심 이관 위험이다. 기존 attestation fingerprint_mismatch와
operator/comparator 미검증 제한은 유지한다. 단계별 receipts가 관측 근거이며, 실패한 실제
서버 실행은 별도 상태 확인 후 복귀 조치가 필요하다. commit/push/PR/merge는 수행하지 않았다.


## 2026-09-23 실제 120분 시험 결과

사용자가 실행한 서버 NSIS 시험은 7,201.485초 관찰 후 정상 종료·원본 복귀했다. 회수 해시/실행 기록과 production 원문 검증을 완료했다. [실제 현장 결과](temperature_p2_nsis_120min_trial_20260923.md)를 참조한다. 앞의 실행 전 기록은 보존하며, 콘솔 종료 후 생존·현재 작업 정보 확인 및 정식 운영 승격은 각각 별도 상태로 남긴다.

### 콘솔 종료 후 확인 완료

2026-09-23 사용자가 콘솔 종료와 실제 현재 제품·금형의 일치를 확인했다.
14:02~14:03(KST) 원격 화면에서도 원본 앱의 Running / Comm OK와 실시간 값 갱신을 확인했다.
미서명 내부 설치 검증의 사용자 확인은 완료됐으며 정식 운영 승격은 별도다.
이전 해시 결합 증거는 보존하고 추가 기록은 `P2_N120_CLOSEOUT_R1`로 분리했다.
