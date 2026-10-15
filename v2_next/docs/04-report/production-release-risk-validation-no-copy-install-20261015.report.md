# 1.0.29 교체의 새 전체 백업 생략 절차 검증

2026-10-15 사용자 지시: “백업을 안해도 진행에 무리가 없다면 백업 하지 않고 진행해라.”

이번 `4cc7393e / 1.0.28` → `acaf77d9 / 1.0.29` 교체는 새 전체 데이터 사본 없이
진행할 수 있도록 별도 절차를 검증했다. 제품 변경은 선택적 health 진단과 버전 변경이며
저장 형식·설정 이관 변경은 없다. 기존 백업과 복귀 설치본은 보존한다.
원본의 전후 해시 검사는 변경을 검출하지만 손실된 데이터를 복원하지 못한다.

최신 상태(20:19 KST): 기존 설치 요청은 관찰 기록의 시간 제한으로 설치 전에 HOLD됐다.
설치 직전 전수 재검산의 완료 시각을 기준으로 하는 수정 도우미를 격리 검증하고 서버에 전달했다.
서버 설치는 아직 시작되지 않았으며, 아래 새 `PINNED_FRESH_INSTALL_COMMAND.txt` 실행을 기다린다.

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
