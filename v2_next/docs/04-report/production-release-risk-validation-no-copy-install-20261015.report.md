# 1.0.29 교체의 새 전체 백업 생략 절차 검증

2026-10-15 사용자 지시: “백업을 안해도 진행에 무리가 없다면 백업 하지 않고 진행해라.”

이번 `4cc7393e / 1.0.28` → `acaf77d9 / 1.0.29` 교체는 새 전체 데이터 사본 없이
진행할 수 있도록 별도 절차를 검증했다. 제품 변경은 선택적 health 진단과 버전 변경이며
저장 형식·설정 이관 변경은 없다. 기존 백업과 복귀 설치본은 보존한다.
원본의 전후 해시 검사는 변경을 검출하지만 손실된 데이터를 복원하지 못한다.

최신 상태(21:29 KST): 새 도우미의 서버 설치·전후 원본 보존 검토를 완료했다.
실제 installer와 launcher exit 0, 설치 파일 1,868개·원본 313,365개·추가 스트림 680개 및 설정 불변을 확인했다.
일반 사용자 바로가기로 1.0.29를 시작했고 수집 증가를 관찰했다. 새 빌드 attestation,
현재 실행의 native 세대·정상 종료·데이터 내용 검사와 현장 성능 QA는 남아 있어 출시·승격 HOLD다.

## 변경과 실행 조건

- `cold-data-observation.cs`: 두 원본 루트의 기본/추가 NTFS 스트림, 파일/폴더 목록,
  생성·수정 시각, 속성 및 owner/group/DACL을 기록하고 다시 대조한다. 데이터 사본은 만들지 않는다.
- `invoke-health-preservation.ps1`: 현재 서버·사용자·빌드·실행 세대를 확인하고 READY 후
  정상 UI 종료를 기다린다. 새 보호 폴더에 관찰 기록을 만들며 설치를 실행하지 않는다.
- `install-health-observed.ps1`: 별도 관찰 request와 정상 종료 검토를 결합한다.
  설치 전후 원본, 정확한 payload·등록·설정과 installer 종료 코드를 확인한다.
  구 백업 결과를 대용으로 받거나 백업 검사를 끄지 않는다.

새 절차는 운영 여유 10 GiB와 설치/검사 공간을 확인한다. 전체 데이터 복사 공간은 예약하지 않는다.
현재 원본을 정상 종료 상태에서 검사하고 같은 실행 세대의 종료 근거가 확인돼야 설치할 수 있다.
설치·검사 실패 시 자동 재실행, 강제 종료, 자동 복귀 또는 앱 시작을 하지 않는다.

## 실제 검증 결과

근거 루트: `C:/Users/user/Desktop/SmartFactory/PDCA_NO_COPY_20261015_738bf0e0`.

| 검사 | 결과와 범위 |
|---|---|
| 네이티브 PS5.1 관찰기 | exit 0, 71 assertions. 반복된 fixture 경계 검사 포함. 기본/추가 스트림·디렉터리 ADS, 목록/내용/메타데이터 변조, writer lock, reparse, 잘못된 manifest·실행 상태 거부 |
| 최종 관찰 실행 묶음 | `entry-r3`, exit 0, 5 checks. 정상 library load, 잘못된 pin·추가 파일·변조·다른 서버 거부 |
| 별도 설치 소비기 | exit 0, 48 checks. 관찰/백업 구분, 정상 종료·세대·범위·시각 검사, 설정 불변, 실제 자식 종료 코드와 timeout 무강제 처리 |
| 실제 Windows Sandbox 설치 | CLI/guest/후보 installer 모두 exit 0. 실제 1.0.28 1,815파일에서 1.0.29 1,868파일로 교체 |
| 격리 데이터 보존 | 합성 파일 4개·폴더 3개·추가 스트림 3개·210바이트의 전후 대조 통과. 새 전체 백업 없음. 실제 현장 규모·앱 정상 종료 검증은 이 시험 범위 밖 |
| 수동 실행 bootstrap | 32/64비트 창에서 네이티브 64비트 PS5.1 선택, 두 번 모두 exit 0. LibraryOnly로 원본 접근 없이 검증 |
| 격리 환경 정리 | 앱/포트 부재 확인 후 해당 Sandbox 종료. 결과 34파일 보존·해시 재대조, 강제 앱 종료 없음 |

최초 Sandbox 실행은 로그인 세션이 준비되지 않아 guest 실행 전에 실패했다.
동일 격리 환경의 로그인 연결과 빈 출력 폴더를 확인한 뒤 새 실행 기록으로 성공했다.
최초 실패 기록은 보존했다. 제품 설치본을 재빌드하거나 변경 없는 전체 health를 반복하지 않았다.

검증 영수증: `verification.json`, SHA256
`7c173e05dddde42ff80cd5fbd1dde4ac67e89404fa8b2a0d9186e28474549c36`.
최종 관찰 package manifest SHA256:
`C30714AD665E7E1D14614E40C599BE2ED78A87425264CA6AE77D605F7ED01515`.

## 현장 상태

15:48 KST까지 21파일·329,526,835바이트를 공유 `20261015/send`에 전달하고 SHA256을 대조했다.
Chrome 원격 탐색기로 서버의 `C:\Users\user\Desktop\SmartFactory\HP29_20261015_738bf0e0`에
복사했으며 절대경로와 관찰 묶음 9파일의 존재를 화면에서 확인했다.
서버 로컬 해시는 아직 검사하지 않았으며 외부 pin이 포함된 수동 명령이 실행할 때 대조한다.
화면 확인을 서버 바이트 검산으로 표시하지 않는다. 증거는 `server-delivery-ui.json`,
`server-local-path.jpg`, `server-observe-files.jpg`에 보존했다. 구현 commit은 `0879ff82`다.

위 전달 확인 당시 서버 앱은 Running이고 수동 관찰 명령 실행을 기다렸다.

### 2026-10-15 16:16 KST 진행 기록

사용자의 실행 완료 응답 뒤 서버 콘솔의 `READY_FOR_NORMAL_APP_EXIT`를 확인했다.
앱 창의 X로 정상 종료를 요청했고 `O3aa2e84e`에서 원본 관찰 검사가 진행 중이다.
회수한 Electron 로그에는 15:57:50 KST backend 10724의 종료 코드 0, forced=false가 기록됐다.
종료 영수증의 이미지 76,114건은 모두 저장됐고 대기·진행 작업은 0이다.
당일 CSV 250,085행의 순번 연속성과 마지막 순번 361155의 종료 metadata 일치를 확인했다.
이는 회수 자료의 예비 검토이며, 아직 콘솔 고정 해시와 최종 원본 manifest에 결합하지 않았다.
검토 도구 실제 exit 0, `field-close-preliminary-review.json` SHA256:
`3c2d918c1e2db29f6cf4dbb461285ee5646c97dd153883cbebb09b1816664f56`.
새 전체 백업은 만들지 않았다. 원본 검사 완료·결과 회수·정상 종료 근거의 최종 결합이 남았다.

1.0.29 서버 설치·설치 전후 원본 보존은 아직 미실행이다. 현장 15분 실패 이력,
미실행 120분, 물리 경계 미시험, 전체 데이터 QA와 운영 승격 HOLD는 유지한다.

### 2026-10-15 16:51 KST 원본 재검산 완료·설치 요청 전달

같은 `O3aa2e84e` 검사가 정상 종료됐고 콘솔 `LAUNCH_EXIT=0`을 확인했다.
파일 313,365개·폴더 245개·추가 스트림 680개, 총 14,590,063,063바이트의
내용·목록·메타데이터를 관찰 후 재검산했다. 새 전체 백업은 만들지 않았다.
결과 9파일을 서버 탐색기로 회수하고 공유→개발 PC 사본의 크기·SHA256을 대조했다.

- 콘솔/회수 `result.json` SHA256: `be923dd734b3346cf045c05d4825230b2254f8ee7e2fd6beec0938fb6abe6e23`
- 콘솔/회수 `observed.tsv` SHA256: `2183acb7a5aca7d5107c22d104b40e5ed47797ae684157cf9e0a8dd37e06b886`
- `review-field-close.py` 실제 exit 0. 종료 전 native PID·생성 시각·logger와 정상 종료,
  현재 CSV 250,085행·마지막 순번 361155·이미지 drain 76,114건 및 회수 자료 34파일을
  원본 manifest에 결합했다. `field-observed-close-review.json` SHA256:
  `56fe651507460c2db7c0a04f61b01961b067abc92ae34e81e20b79578048e344`.

실제 결과를 사용하는 설치 request 생성은 exit 0이며, native PS5.1 x64에서 request 계약,
정상 종료·원본 결과·실행 세대·관찰 유효 시간과 bootstrap 구문/요청 해시를 검사해 exit 0이었다.
17:02 KST까지 새 4파일을 `Z:/SmartFactory/20261015/send/HI29_OBS_20261015_738bf0e0`로
전달·검산하고 서버 `C:/Users/user/Desktop/SmartFactory/HI29_OBS_20261015_738bf0e0`에 복사했다.
절대경로·파일 존재를 화면에서 확인하고 `PINNED_OBSERVED_INSTALL_COMMAND.txt`를 메모장에 열었다.
서버 로컬 바이트 검산은 실행 시 고정 해시 검사로 남으며 화면 관찰로 대신하지 않는다.
전달 근거는 `server-observed-install-delivery.json`과 해당 경로/메모장 화면이다.

이 전달 당시 사용자 PowerShell 실행을 기다렸다. 앱은 종료 상태이며 설치는 시작하지 않았다.
관찰 결과의 유효 시간 180분을 적용하므로 오늘 19:40 KST 이후에는 실행 전에 상태를 다시 확인한다.
실패하면 자동 재실행하지 않는다. 새 전체 백업 생략은 전체 데이터 의미 검증 완료나
현장 성능·물리 경계·출시 HOLD 해소를 뜻하지 않는다.

### 2026-10-15 19:54 KST 설치 전 HOLD 확인

서버 콘솔에서 `Ja72cb21d`, `INSTALL_HOLD=observation-freshness`, `LAUNCH_EXIT=1`을 확인했다.
결과 6파일을 서버 탐색기로 `Z:/SmartFactory/20261015/return/HI29_HOLD_738bf0e0`에 회수하고
개발 PC 사본과 크기·SHA256을 대조했다. 콘솔과 회수 `hold.json`의 SHA256은
`ab7081d086f14e9ccd93a8af87c8499c0b6c64623d86b2046167006c28216b68`로 일치했다.
실제 검토 exit 0이며 입력 5파일의 고정 해시도 일치했다. 설치는 시작하지 않았고 설정도 변경하지 않았다.
실패 근거는 `field-install-hold-review-Ja72cb21d.json`, SHA256
`8b153bc795301628e860e5f06dd88aea52144da5020af63998aeafbc41ad209a`다.

### 2026-10-15 20:19 KST 전수 재검산 기준 수정·전달

관찰 시각 자체는 그대로 보존하고, 설치 직전 원본의 내용·목록·추가 스트림·메타데이터를
고정 manifest와 전수 대조하도록 했다. 재검산 전후 앱·포트 부재를 확인하며,
재검산 완료 후 단조 시계로 120초 이내에만 설치를 시작한다. 원본 변경, 미래 관찰 시각,
앱 실행 또는 재검산 후 지연은 설치 전에 차단한다. 구 결과의 시각이나 해시를 다시 쓰지 않는다.

예: 4시간 전 정상 종료 관찰 결과라도 지금 전수 대조가 성공하면 설치할 수 있다.
기본 파일 본문이나 NTFS 추가 스트림이 한 바이트라도 바뀌면 설치하지 않는다.

근거 루트: `C:/Users/user/Desktop/SmartFactory/PDCA_INSTALL_FRESH_20261015_6f267a91`.

| 검사 | 결과와 범위 |
|---|---|
| `test_install_health_observed.ps1` | native PS5.1 x64, exit 0, 54 checks. 미래 시각·만료/정지/누락된 단조 시계·120초 초과 한도 거부, 기존 pin·정상 종료·실제 자식 종료 코드 검사 포함 |
| 실제 격리 설치 `trial-r2` | host CLI·guest·NSIS 모두 exit 0. 4시간 전 기준으로 1.0.28 1,815파일 → 1.0.29 1,868파일 교체 |
| 변조 차단 | 기본 파일 본문과 이름 있는 추가 스트림 변경 2조건 모두 `preinstall-original-data-reverification`에서 설치 전 차단 |
| 보존과 유효 시각 | 합성 파일 4개·폴더 3개·추가 스트림 3개·210바이트 및 설정 불변. 전수 재검산 뒤 460ms 시점 영수증, 허용 한도 120,000ms |
| 격리 환경 정리 | 프로세스·포트 부재 확인 후 해당 Sandbox 종료, 62파일·5,943,516바이트 보존, 강제 앱 종료 없음 |
| `validate-field-package.ps1` | native PS5.1 x64 exit 0. 새 6파일 pin, 실제 종료 세대/관찰 결과, request 계약, bootstrap 구문 확인 |

첫 격리 시도는 기본 본문 변경 차단을 확인한 뒤 시험 파일 복원 과정에서 빈 추가 스트림이
없어진 것을 검출해 중단됐다. 시험 fixture가 빈 스트림도 복원하도록 수정한 새 격리 환경에서
위 두 변조 차단과 실제 설치를 완료했다. 실패 기록도 보존했다. 제품 설치본은 재빌드하지 않았다.
이 시험은 합성 자료를 사용하므로 실제 서버 설치나 앱 시작·정상 종료 검증을 대신하지 않는다.

- 최종 controller SHA256: `61dc38efee5d107e9292fb585e00cbfb6ce9b917c0abcea04c31f3d3dbcd90eb`
- request SHA256: `ce5cc05ac641eeb40ce008ea721ae661b0f7a0261227aa8661d347d055064ee7`
- 격리 transaction result SHA256: `3251a6f4a98738790b80c012304fd122a7ae597d7bc9ed5f0688cb6c287e8f60`
- 격리 보존 manifest SHA256: `2c78d096842a24c34efbff189ac74fbf5c8ff7d86201f57f958c91773a9dc487`

새 6파일·67,419바이트를 `Z:/SmartFactory/20261015/send/HI29_FRESH_20261015_6f267a91`에
전달·검산한 뒤 서버 `C:/Users/user/Desktop/SmartFactory/HI29_FRESH_20261015_6f267a91`로
탐색기 복사했다. 실제 절대경로·6파일을 확인하고 `PINNED_FRESH_INSTALL_COMMAND.txt`를 메모장에 열었다.
서버 로컬 바이트 검산은 새 bootstrap 실행 시 수행하며 화면 확인으로 대신하지 않는다.
증거는 `server-fresh-package-path.jpg`, `server-fresh-command-ready.jpg`, `server-delivery.json`이다.

사용자 실행은 새 명령 본문 전체를 관리자 PowerShell에 붙여넣고 Enter를 한 번 누르는 단계다.
시작 표시는 `REVERIFY_BEFORE_INSTALL_START`다. 이전 19:40 제한은 구 요청에만 적용되며,
새 요청은 실행 중 전수 재검산 완료 후 120초 조건을 검사한다. 종료 결과를 회수·검산할 때까지
앱은 종료 상태로 유지한다. 새 전체 백업은 만들지 않으며 기존 복구 자료를 보존한다.
서버 설치·설치 후 런타임은 아직 미검증이고 정식 출시와 운영 승격은 계속 HOLD다.

### 2026-10-15 21:29 KST 실제 설치·보존 검토와 첫 실행

사용자 실행 뒤 같은 콘솔에서 전후 전수 검사를 관찰했고, 21:16 KST에
`RESULT_PATH=C:\Users\user\Desktop\SmartFactory\J644f98ad`, `LAUNCH_EXIT=0`을 확인했다.
실제 installer PID 10868은 20:52:01부터 20:52:44 KST까지 실행돼 exit 0으로 끝났다.
설치 전 재검산은 20:51:58 KST 완료됐으며 freshness 영수증은 1,981ms였다.
원래 16:51 관찰 기록과 고정 manifest를 보존하고 실제 재검산 완료 시각을 사용했다.

서버 탐색기로 완료 결과 23파일·2,257,832바이트를 아래 공유 위치에 회수하고
개발 PC 사본과 파일별 크기·SHA256 및 콘솔 result pin을 대조했다.

- 공유: `Z:/SmartFactory/20261015/return/HI29_FRESH_6f267a91/J644f98ad`
- 개발: 위 `PDCA_INSTALL_FRESH_20261015_6f267a91/field-install-J644f98ad`
- 콘솔/회수 result SHA256: `12efb1b8ec824e1ba0d40257618b9bd05dde1ff343ff3d4f350f713e0859e047`
- `review-health-install.py` 실제 exit 0, 입력 영수증 22개·고정 controller/library/기준 자료,
  원래 관찰·정상 종료 세대, 설치 시각·actual exit, 전후 전체 payload·등록·원본·설정 결합.
  별도로 전후 uninstaller의 외부 고정 크기·SHA도 대조해 exit 0이었다.
- 검토 `field-install-review-J644f98ad.json` SHA256:
  `8a2949ca5edbd24dfa4da0674318e273636e20b56a4b68fe6842c427ff5e53a6`.

원본 파일 313,365개·폴더 245개·추가 스트림 680개·14,590,063,063바이트의
내용·목록·메타데이터가 설치 전후 같은 manifest와 일치했다. 설정 2,671바이트의 원문 SHA는
`2f872a957b0899858a2f71a2c8b8928f3ef9f416ed04ce2ca7282f83adaf5fb4`로 같았다.
새 전체 백업·설정 변경·자동 복귀는 없었다. 검토기는 실제 격리 설치 영수증과
잘못된 pin·종료 코드·변조·만료·payload/config 불일치·중복 JSON 키 8조건으로 검사해 exit 0이었다.

21:23 KST 일반 사용자 바탕화면 바로가기에서 시작한 앱의 Running 화면과 제품 60365·금형 4,
GET 6건 HTTP 200, 실제 1.0.29/acaf77d9 packaged runtime을 관찰했다.
`first-runtime-review.json`(SHA256 `359c95655f822a3b4b549bc645b0c7a62b6d9b82a4807e607ab4789a4ce2c964`)
검토 exit 0: 승인 프로파일 필드와 canonical settings hash가 일치하며 지문 payload에서
build commit만 이전 4cc로 바꾸면 기존 승인 지문이 재현된다. 현재 `fingerprint_mismatch`는
새 build attestation 미적용 상태이며 이를 설정 확인 PASS로 바꾸지 않았다.

21:28 KST 같은 logger/spot 세대의 후속 GET 2건은 HTTP 200이었다. API 보고상 CSV 1,512행,
이미지 enqueued/written 333/333·queue/drop/failure 0, observation link/write failure 0이다.
초기 startup_pending 17행·stale 198행과 writer 초기화 33,109ms는 후속 검토 대상으로 남긴다.
첫 startup 전체 시간·현재 native PID/생성 FILETIME·실제 CSV/이미지 내용·정상 종료는 아직 검증하지 않았다.
추가 GET `/api/log/status`는 기록용 POST 경로라 404/reader exit 1이었으며 실패 기록을 보존했다.
지원되는 health/config 조회로 후속 관찰을 마쳤고, 이를 전체 15분/120분 성능 통과로 확대하지 않는다.

### 2026-10-15 21:53 KST 첫 실행 종료 자료 수집 준비

`scripts/field-v1028/observe-health-runtime-close.ps1`와 해당 PowerShell 검사를 추가했다.
설계 5.19와 대조해 현재 build/logger/CSV/config pin, CIM-parent/listener/native handle 결합,
450초 정상 종료 대기, 현재 CSV·metadata·설정의 제한된 읽기와 HOLD 범위를 확인했다.
이번 실행에 설치·설정 쓰기·전체 백업·강제 종료는 없다. 저장 worker 영수증·파일 내용 QA와
새 build attestation은 후속 작업이며, 이 도우미의 결과만으로 해당 조건을 통과시키지 않는다.

실제 native PowerShell 5.1 x64에서 `test-health-runtime-close.ps1 -OutputParent <개발 검증 폴더>`
8검사 exit 0이었다. parser·실제 자식 exit 23·잘못된 실행 경로·덮어쓰기/크기 예산·경로/스트림·
active process/listener·요청 build/CSV·개발 PC 실행 거부를 포함한다. 32/64비트 명령 창의
동일 launcher는 모두 native child까지 도달해 의도한 개발 host guard/LAUNCH_EXIT=1을 출력했다.
이는 서버 정상 종료 실행 PASS가 아니며 실제 결과를 기다린다.

5파일·17,724바이트를 `Z:/SmartFactory/20261015/send/RC29_20261015_804b2fcc`에 복사해
개발 사본과 파일별 해시를 대조했다. 원격 탐색기로 서버 로컬
`C:/Users/user/Desktop/SmartFactory/RC29_20261015_804b2fcc`까지 복사하고 절대경로·5파일 존재와
메모장에 열린 `PINNED_RUNTIME_CLOSE_COMMAND.txt`를 확인했다. 서버 로컬 바이트는 실행 시
잠긴 helper SHA `24523e09c0adc3385aea3117fe3fc8353d552ad435e8e04dff0d2b11f48b6656` 및
요청 SHA `0a48997cdc9e336265de7c3edf87e1240a7b1d37504f757d09976decde277292`로 검사한다.
현재 앱은 Running이며 작업 정보는 최근 적용 21:38:35 이후 필수값 미입력이다.
이전 60365·4를 재적용하지 않았고 다음 재시작 시 현재 작업값을 확인해야 한다.

### 2026-10-15 22:35 KST 첫 실행 종료 자료 검토와 설정 확인 준비

사용자 실행 뒤 22:09 KST 콘솔의 `READY_FOR_NORMAL_APP_EXIT`를 확인하고 앱의 닫기 버튼을
눌렀다. 종료 직전 화면은 제품 60365·금형 4, 최근 적용 22:04:47이었다. Codex가 작업값을
다시 입력한 것은 아니다. 앱 창은 닫혔으나 도우미는 `closed-read` 단계에서
`held-process-still-running`, `LAUNCH_EXIT=1`로 끝났다. 결과 폴더는
`C:\Users\user\Desktop\SmartFactory\Rc3c34431385b`이며 콘솔과 회수한 `hold.json` SHA는
`49e34eedd8758eb5bd6e368c4d74ceaf9fe88ffbd0bca161102752693346eb4e`로 일치한다.
보유 native handle은 도우미 종료 시 해제됐으므로 이번 실행의 OS exit code를 사후 추정하지 않는다.

4개 오류 증거 파일과 별도로 현재 CSV·metadata·설정·이미지 최종 manifest·shutdown 영수증을
탐색기로 `Z:/SmartFactory/20261015/return/RC29_804b2fcc_2210`에 회수했다. 개발 사본은
위 근거 루트의 `runtime-close-Rc3c34431385b`, `first-runtime-closed`다. 공유/개발 바이트는
파일별 대조했고, 별도 회수 CSV/metadata에는 콘솔 외부 pin이 없다는 범위도 기록했다.
설정 SHA는 기존 `2f872a95…`와 일치한다. `review-first-runtime-closed.py` exit 0 결과:

- CSV 12,386행, 실제 metadata의 전체 헤더 일치·행 형태·sample_seq 1–12,386 연속·logger 일치.
  status는 valid 7,967 / under_range 4,204 / stale 198 / startup_pending 17이다.
  이는 전체 온도 의미·이미지/fact 연결 QA 통과를 뜻하지 않는다.
- `csv_closeout`은 동일 logger의 finalized shutdown, 마지막 번호 12,386이다.
- 같은 build/backend PID 6104의 control begin/final 영수증·SHA 연결을 대조했다.
  stopped/drained 10단계 true, stage exit 0, 이미지 enqueue/written 2,631/2,631,
  queue/inflight/unfinished/failure/drop 0이다. OS 프로세스 종료 관찰과는 별개다.
- metadata 이미지 manifest는 시작 시점 4,313,886행/written 0이고 별도 최종 manifest는
  4,316,517행/written 2,631이다. 실제 이미지 fact/바이트 전체 대조는 아직 하지 않았다.
- 검토 `first-runtime-closed-review.json` SHA:
  `4d7fe1203bc1c624c6ef480294cf26360287fb025a99eee21b49131e227254ef`.
  결과는 `CSV_SEQUENCE_AND_APPLICATION_CLOSEOUT_VERIFIED_NATIVE_EXIT_UNVERIFIED`다.

도우미의 `HasExited` 대기와 `WaitForExit(0)` 사이 불일치를 발견했다. .NET Framework의
[`Process` 구현](https://github.com/Microsoft/referencesource/blob/main/System/services/monitoring/system/diagnosticts/Process.cs)은
종료 코드와 handle 신호를 구분한다. 이 차이는 이번 오류의 원인 후보이며 서버 재현으로 확정하지 않았다.
공통 450초 예산에서 모든 보유 handle의 실제 신호를 기다리도록 수정했고 native PS5.1 x64
`test-health-runtime-close.ps1` 10검사 exit 0이었다. 기존 해시 고정 서버 묶음은 변경하지 않았다.
새 `review_health_runtime_close.py`의 외부 pin/native/CSV 계약 검사 10개 exit 0,
Ruff `--isolated --select E9,F821` exit 0도 확인했다. 이번 실패 폴더를 정상 result로 처리하지 않았다.

새 build의 확인 기록 연결을 위해 `apply_spot_temperature_v25_attestation.ps1`의 제한된
현장 허용 build에 acaf77d9를 추가했다. 승인 프로파일·외부 input SHA·Low Signal OFF·
comparator 미확인 조건은 유지한다. `test_spot_attestation_script.py` 9검사 exit 0이다.
실제 회수 config/metadata 사본을 사용한 native PS5.1 시험에서도 네 attestation 필드만 바뀌었고,
active process/listener 거부 및 32/64비트 bootstrap의 개발 host 실행 거부를 확인했다(exit 0).
시험 요약은 `attestation-tests-4a4b55e91736/summary.json`이다.

다음 묶음 `AT29_20261015_ae932846`은 11파일·74,756바이트다. 고정 controller SHA는
`c4f8f154f4becb00f6323ca647f9af30419daf1d1c905d5ab7a71c2d2a548b7c`, request SHA는
`53e10d0fc93cf89108b5840bd87f9e319e5b880aac8eabc6aa87a9f5c06c6878`다.
현재 metadata SHA `b75e847f90462a2eb33191688030af076f805a04d8909391e53435c7ef639b62`를
서버 원본과 다시 비교하고 process/port 부재를 확인한 뒤에만 네 설정 확인 항목을 쓴다.
전체 백업·설치·자동 앱 시작은 하지 않는다. 쓰기 복구를 위해 설정 파일 범위의 사본만 보존한다.
네 확인 항목의 적용·새 runtime·native 정상 종료·현장 성능·전체 데이터 QA와 운영 승격은 미완료다.

22:37 KST 서버 `C:/Users/user/Desktop/SmartFactory/AT29_20261015_ae932846`의 11파일과
메모장에 열린 `PINNED_HEALTH_ATTEST_COMMAND.txt`를 확인했다. 공유 사본은 파일별 해시를
대조했으며 서버 로컬 잠금 바이트 검증은 사용자 실행 시 수행한다. 전달 기록은
`health-attestation-server-delivery.json`, 화면은 `server-health-attestation-command-open.jpg`다.
앱은 종료 상태로 유지하며 사용자에게 명령 본문 1회 실행을 요청했다. 이전 종료 도우미나
설치 프로그램은 재실행하지 않는다. 전체 PDCA는 진행 중이며 출시/승격 HOLD다.

### 2026-10-15 22:54 KST 설정 확인 적용·재시작 검산

사용자 실행 후 콘솔에서 `LAUNCH_EXIT=0`과 서버 결과 `A32088b67`을 확인했다.
결과 SHA는 `1e74d55e6870294eea82238d7a4a99c39ffc76303393bf55f372eb543da0858e`다.
최초 화면 전사값은 두 군데 오독으로 복사 전 hash 검사에서 거부됐다. 보존 화면을 확대해
위 값을 다시 읽었고, 회수한 result 및 모든 하위 증거 hash와 정확한 6파일 목록이 일치했다.
공유 회수 위치는 `Z:/SmartFactory/20261015/return/AT29_ae932846_2244/A32088b67`,
개발 사본은 근거 루트의 `attestation-A32088b67`이다. `health-attestation-recovery-review.json`에
검산을 남겼으며 실제 검산 명령 exit 0이다.

전후 설정을 네 attestation 키만 마스킹해 바이트에 해당하는 전체 텍스트를 비교했다.
실제 값이 바뀐 것은 확인 시각·fingerprint 두 항목이고, operator true/USER_SELF는 유지됐다.
설정 SHA는 `2f872a95…`에서 `9901d4e3c11c8e0ebe1787d84343cd6db70b7f4dce992ef23c778eca712c21ac`로
바뀌었다. 전후 OS snapshot의 앱 프로세스와 port 8000 listener는 모두 비어 있었다.
이 관찰은 이전 프로세스의 누락된 실제 exit code를 대신하지 않는다.

22:48 KST 일반 사용자 바탕화면 바로가기로 앱을 시작했다. 화면은 Running, 작업 정보
60365·4(기존 적용 22:04:47)였으며 Codex는 작업값을 수정하지 않았다. 두 차례 읽기 수집의
각 6 GET은 모두 HTTP 200/exit 0이었다. `review-post-attestation.py` exit 0 검토 결과:

- 실제 build acaf77d9, `runtime_config_attestation / verified`, USER_SELF,
  fingerprint `14b58a8cf9dec3669c475776c99d6cc62f19f9caebf6fad8b33267b774d36431` 재계산 일치.
  drift false/빈 목록, Low Signal OFF, comparator 미확인 false를 유지한다.
- 새 logger `5618690a-6e8b-444f-a37c-e0cd63c94c85`, SPOT
  `74f42667-bfd7-41aa-81fb-71f3664aa206`, CSV `Factory_Integrated_Log_v2_20261015_224850.csv`.
  API rows 1→430, 상태 startup_pending 10/stale 229/valid 191. 시작 구간 stale을 숨기지 않는다.
- 이미지 enqueue/written 95/95, queue/failure/drop 0. 이는 해당 API 관측이며 파일 내용 QA가 아니다.
- 제한된 설정 기준 1,808바이트 SHA
  `24d7c58826e31d60ce80c0a728fa5e718967eb274d6912cf901ef67c18afe757`.
  경로 `post-attestation-configuration-reference-r2.json`이며 기존 승인 두 hash를 포함한다.
  최초 생성본은 전체 image 응답을 포함해 32KiB 제한으로 거부됐고 진단 입력으로 사용하지 않는다.
  R2는 계약상 설정 필드와 실행 식별 필드만 선택해 기존 기준 검증기를 통과했다.

다음 6초 진단 요청에 필요한 독립 OS 식별자를 위해 기존 native 수집기에 `-IdentityOnly`를
추가했다. 닫기 대기 전에 현재 프로세스·health·원문 설정 증거를 쓰고 끝나며 종료/설치/설정
변경/전체 백업을 하지 않는다. native PS5.1 `test-health-runtime-close.ps1` 11검사 exit 0,
32/64비트 launcher의 개발 host 거부도 확인했다. 검사 기록은
`runtime-close-tests-3279e18ac8784f1a9b46bc8685833a5d/summary.json`이다.
새 묶음은 `RI29_20261015_cd4a5f22`, helper SHA `117d4bdb08c9b8b6db35ea32be94ae9e13083a984ed60fd4cfe3acf61d4ddb5e`,
request SHA `911ae16bf5bc6836cccf27bb902f457ee7c5edef895c5b1c38adabaf2a4a4857`이다.
현재 앱은 Running으로 유지한다. 독립 native 읽기·6초 추적·현장 성능·전체 데이터 QA·정식
운영 승격은 아직 완료되지 않았다. 전체 PDCA/출시 HOLD를 유지한다.

최종 전달: 5파일·19,214바이트를 공유 send에 복사하고 파일별 SHA를 대조했다.
원격 탐색기로 서버 로컬 `C:/Users/user/Desktop/SmartFactory/RI29_20261015_cd4a5f22`까지
복사한 뒤 절대경로·5파일·열린 `PINNED_RUNTIME_IDENTITY_COMMAND.txt`를 확인했다.
`runtime-identity-server-delivery.json` SHA는
`99da277dd2fd46c31c587fec5e5cd980ef865b91cd0b8bdf0964ccf8806c76e9`다.
서버 로컬 SHA는 아직 회수 검증하지 않았으며 사용자 실행 시 helper/request pin으로 검사한다.
앱 Running을 유지한 채 읽기 명령 1회 실행을 요청했다. `git diff --check`와 두 준비/검토
Python 파일의 Ruff `--isolated --select E9,F821`도 exit 0이었다.

### 2026-10-15 23:06 KST 실행 입력 대기 중 닫힌 CSV의 의미 규칙 검사

서버 RI29 읽기 명령의 완료 출력은 아직 관찰하지 못했다. 이 대기와 독립적으로 이미 회수한
첫 1.0.29 실행의 CSV 12,386행·metadata·이미지 최종 manifest를 변경 없이 검사했다.
`audit-first-runtime-semantics.py`는 기존 `validate_csv_v2_shadow.py`를 실제 CLI로 실행하고,
같은 입력에 대한 기간/enum/순번/origin/sentinel/운영 상태/TTL/closeout/설정 규칙 9그룹을
별도로 호출했다. 9그룹의 오류는 0이다. 전체 헤더·스키마·행 수·sample_seq도 기존 CLI 출력과
대조했고 원본 입력 및 validator 소스의 검사 전후 SHA는 같다. 이 검사는 이미지 실물·fact
연결·OS exit·전체 과거 데이터 QA의 통과를 뜻하지 않는다.

전체 CLI는 exit 1이며 사본이 없는 경로에 대해 5개 실패를 출력했다. 개발 PC의 같은 이름
AppData 자료를 잘못 읽지 않도록 모든 fact 위치를 명시적으로 존재하지 않는 로컬 경로로
지정했다. 그중 실제 닫힌 snapshot의 필수 누락 입력은 다음 두 파일이다.

- 관찰 fact: 400,833행, metadata SHA `0bc2679fb7f424fd30f42b37f83af09e29883f98b1c6295f5bdd8a7bd9c23f7a`.
- 이미지 fact: 최종 manifest 4,316,517행, SHA `1c8c69e3ca5d123b778a578ce2468b3db0960c7841dc04a6d1eddf0685e6e4de`.

나머지 세 실패는 명시한 미존재 posthoc/linkage override에서 발생했다. 원래 두 posthoc
manifest는 row 0/hash null이며 linkage manifest는 미발행이다. 이 출력을 서버 원본 유실이나
손상 증거로 해석하지 않는다. 향후 전체 양방향 연결 검사와 사후처리 생성 여부는 별도로 판단한다.
기존 CSV는 탐색기 회수 사본으로 독립 콘솔 pin이 없고, metadata만 이후 서버 attestation
도우미에서 고정 hash로 검증됐다는 출처 제한도 유지했다.

근거 루트의 `first-runtime-semantics-r1`에 CLI 전체 stdout 6,198바이트/stderr 0바이트,
실제 명령·종료 코드·소스/입력 hash·범위 판정을 기록했다. 감사 실행 자체는 exit 0이며
전체 CLI의 exit 1을 그대로 보존한다. 요약 SHA
`605e54f2527c8be5c90f7ab7a1190d4bbd786c7b598f5f1220434276637d27b1`, 범위 판정 SHA
`506b51b956f551d5a851bdc42ede39a197f7ade1ec9608f07f54db39dde3b40c`다.
새 감사 파일의 Ruff `--isolated --select E9,F821` exit 0. 제품·서버 데이터는 변경하지 않았고
full_data_gate NOT_EVALUATED, 출시/승격 HOLD를 유지한다.
