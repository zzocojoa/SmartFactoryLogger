# 종료 직전 이미지 502 보완과 v1.0.28 검증

후보 `4cc7393e1bafbf90a329726aed9470fe0daacb21`의 종료 순서를 보완하고, clean 출시 잠금 환경 전체 검사와
새 미서명 설치본의 실제 설치·업그레이드·재시작·이전본 복구를 격리 환경에서 검증했다.
새 후보의 두 정상 종료에서 신규 이미지 502는 0건이고, renderer 준비 완료→backend 종료
순서와 실제 native exit 0을 확인했다. 현장 QA·운영 승격은 완료하지 않았다.

## 원인과 수정

이전 v1.0.27 NSIS 시험의 종료502 6건/독립 review exit1은
[이전 보고](production-release-risk-validation-unsigned-candidate-20261013.report.md)에 보존한다.
정상 종료에서 backend가 이미지 요청을 거부하기 시작해도 창의 renderer가 이미지 polling을
계속해 `shutdown` 오류가 502로 기록됐다. backend 종료가 renderer 준비를 기다리지 않는
회귀를 먼저 재현했다(exit1; backend 호출1/기대0).

`backendProcessLifecycle.js`·`main.js`는 신뢰한 현재 창의 고유 attempt 응답을 기다린 뒤
기존 backend closeout을 실행한다. `preload.js`는 고정 채널만 노출하고,
`useSpotViewModel.ts`는 새 이미지 요청/재시도/타이머를 멈춘 뒤 진행 중인 응답 본문 처리를 기다린다.
위젯 unmount 중인 응답도 기다린다. 준비 거부·15초 timeout은 backend 종료를 진행하지 않고
화면 요청을 재개한다. 실제 transport 오류, writer/종료 증거 및 정상 exit 조건은 유지한다.

## 소스와 빌드 확인

| 항목 | 결과 |
| --- | --- |
| 버전 / clean build commit | 1.0.28 / `4cc7393e1bafbf90a329726aed9470fe0daacb21` |
| 설치본 bytes / SHA256 | 164618981 / `8821746bbed47850ead68c66894e5580afac63483b1569865915dadc30cfc848` |
| 출시 잠금 환경 | Node22.22.2 / Python3.12.6 / wheel40개 버전·hash 대조 / test source46개 |
| 최종 `npm run health` | exit0; Electron100, frontend Vitest437/42파일+Node9, dependency15, backend919통과/F01 skip1 |
| 나머지 health | typecheck/lint/Ruff/mypy9파일/QA 자체 검사 통과 |
| 실제 Electron bridge 시험 | Electron44.3.0, 합성 renderer의 지연 HTTP 응답 처리 후 종료 callback 허용, exit0 |
| 빌드·패키지 검사 | deploy/NSIS/manifest/ASAR/추출 payload 검사 모두 exit0 |
| payload | 1,814파일; backend manifest1,687파일; frontend50파일 두 배치 일치 |
| 서명 | installer/app/backend 모두 NotSigned; NOT_REQUIRED_BY_APPROVED_UNSIGNED_POLICY |

전체 health stdout SHA256 `5ac4bc406e2981ba7420b5aaaab2e687cee14c34f711c0749650ec614e123ba9`, stderr `4807962d6e6648ebbbd471801f5214020037db851474775693a956584599b4a4`.
소스 ZIP은1,089파일을 실제 checkout 및 Git blob과 대조했다. CRLF 변환981개를 명시했고
ZIP SHA256은 `8fe64e22d07f61c34a5eb7161f4fc3f30821faec282a6ba8ef8e65b8474d5619`다.

## 실제 설치와 종료

네트워크·GPU·클립보드 등을 끈 새 Windows Sandbox에서 실제 NSIS를 실행했다.
입력677파일을 서버와 별개인 guest 작업 폴더에 복사해 해시를 대조했다.
신규 후보 설치→제거→기존541d 설치→후보 업그레이드→후보 재시작→541d 재설치/실행 순서다.
설치4회·제거1회 actual exit0, 설치 파일1,814/1,771개·등록 버전·바로가기와
닫힌 config/data/profile의 업그레이드/복구 전후 바이트 보존을 확인했다.
네 실행은 loopback의 합성 PLC/SPOT에 연결한 실제 REAL driver이며 생산 장비 시험은 아니다.

| 단계 | 버전 역할 | 새 CSV 행(v1/v2 각각) | 새 observation | 새 이미지 | main/backend exit |
| --- | --- | ---: | ---: | ---: | --- |
| I2-original-runtime | original | 312 | 24 | 66 | 0 / 0 |
| I4-candidate-runtime | candidate | 327 | 25 | 67 | 0 / 0 |
| I5-candidate-restart | candidate | 296 | 25 | 66 | 0 / 0 |
| I6-original-restored-runtime | original | 297 | 24 | 65 | 0 / 0 |

총 CSV각각1232행, observation98개, 이미지264개를 대조했다.
네 세대의 종료 begin/final/sidecar·writer drain·image queue/drop/failure0·CSV 연속성·
이전 닫힌 CSV/metadata/image와 fact 접두부 보존을 확인했다. CSV/image validator8회 exit0,
v1/v2 row delta0·observation key coverage100%·이미지 hash/크기/디코딩·고아0이다.
합성 위치 열2개의 공란 경고와 phase/changeover 일부 UNKNOWN/NA는 유지한다.
기준 실장비 promotion profile 검증을 수행했다고 해석하지 않는다.

독립 review는 114/118조건 통과, exit 1이다. 누적 로그 오류 조건
4개의 실패를 보존한다. 원래541d 실행에서
종료502 2건이 발생했고, 후보의 첫 실행과 재시작은
각각 새 오류0건이다. 누적 기록의 PASS 변경 없이 실행별 추가 오류와 종료 순서를 별도 검산했다.
분류 검산 exit0은 정식 출시 PASS를 뜻하지 않는다.
모든 닫힌 데이터/AppData/profile ZIP을 회수한 뒤 프로세스·포트 부재를 확인하고
소유 Sandbox만 종료했다. 제품 앱/backend의 강제 종료는 없다.

## 실패 기록과 한계

- 최초 전체 검사 exit1은 기존 preload 계약이 새 고정 IPC를 허용하지 않아 발생했다.
  허용 채널 목록을 명시하고 일반 IPC 금지는 유지했다. 수정·버전 변경 후 새 checkout 전체 검사는 exit0이다.
- 첫 native probe는 잘못된 Electron import 경로를 사용했고 결과를 만들지 못했다.
  Error 창에 정상 닫기를 요청한 뒤에도 남은 시험 helper PID만 강제 정리했다. backend는 시작되지 않았다.
  별도 r2는 실제 preload/controller에서 exit0이다. 이를 제품 강제 종료 시험으로 합산하지 않는다.
- 최초 health launcher의 shell 인수 오류를 보존했다. 초기 TypeScript 테스트 표기 오류와 수정은 도구 기록에 남겼다.
- 새 Sandbox 첫 dispatch는 로그인 준비 전0x80070520로 실패했고 guest 출력이 비어 있음을 확인했다.
  r2 dispatch/guest/Python 실제 exit는0이며 비정상 종료 코드 전달 대조용 exit7도 확인했다.
- PyInstaller tzdata 숨은 import 경고는 남는다. 이번 제한된 실제 실행에서 tzdata 오류는 없었으며
  모든 시간대 경로가 검증됐다는 뜻은 아니다. 기존 npm audit·간헐 종료 receipt timeout 원인도 미해결이다.

## 보존과 후속 조건

실행 자료: `C:/Users/user/Desktop/SmartFactory/PDCA_SHUTDOWN_20261013_6b39ce41` 및 `C:/Users/user/Desktop/SmartFactory/PDCA_NSIS_FIX_20261013_6b39ce41`.
검산: [실행별 판정](C:/Users/user/Desktop/SmartFactory/PDCA_NSIS_FIX_20261013_6b39ce41/review/finding-disposition.json),
[최종 health](C:/Users/user/Desktop/SmartFactory/PDCA_SHUTDOWN_20261013_6b39ce41/health-review.json),
[보존 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_SHUTDOWN_RECORDS_20261013_6b39ce41/archive-result.json).

보존 입력1895파일 / ZIP 351237196bytes,
ZIP SHA256 `159de979e539dd3ee3f6b96ac52007ab8c068bcc8494be9aba76069fcae6f852`, manifest `6b0a91a131fa23687c0272ee089156980ba204c74ddaec0964b65dc13fdb5fec`.
전체 ZIP 내용·원본·공유 사본을 대조했다(exit0). 공유 위치 `Z:\SmartFactory\20261013\records\PDCA_SHUTDOWN_6b39ce41`.
기본 스트림 사본이며 cache/환경/중복 unpacked payload는 제외했다. 작업 루트 전체 seal 또는
서버 최종 전달을 뜻하지 않는다. 이후 문서/PDCA 갱신은 Git에 별도로 기록한다.

실장비 승인 프로파일/비교, 과거 timeout/drop·전체 데이터 판정, browser/CDP OFF,
실제 서버 시작3회, 최종 설치본 현장15분/120분·승격/적용 확인은 남아 있다.
전체 목표 active, R1–R6 HOLD, full_data_gate=NOT_EVALUATED를 유지한다.
실제 운영본과 다음 롤백 기준은541d/08C061EE이며 서버 적용·기준 갱신은 수행하지 않았다.
