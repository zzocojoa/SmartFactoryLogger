# v1.0.27 미서명 후보 빌드·정적 패키지 검증

2026-10-13. clean commit `19e0e314f7c1dc29b38691382aeda637f4ff3032`에서 미서명
후보를 빌드했고 실제 설치본의 앱 payload와 출처를 검증했다. 후속 frozen backend 격리
실행은 아래 추가 기록을 따른다. installer·Electron 전체 앱·서버 적용·운영 승격은 아직
수행하지 않았다. 전체 목표 active, R1–R6 HOLD, full_data_gate=NOT_EVALUATED다.

## 후보와 운영본 식별

| 항목 | 확인값 |
|---|---|
| 후보 버전 / build commit | 1.0.27 / `19e0e314f7c1dc29b38691382aeda637f4ff3032` |
| installer 파일 / 길이 | `smart-factory-logger-v2 Setup 1.0.27.exe` / 164,617,594 bytes |
| installer SHA256 | `f17040fc65d5856c29b04c2b919c6a4bebfca46520dccbb3ea046de2c034166d` |
| 실제 Authenticode | installer·추출 Electron 앱·backend 모두 `NotSigned`, signer/timestamper 없음 |
| 서명 요구 | `NOT_REQUIRED_BY_APPROVED_UNSIGNED_POLICY` |
| 운영본·다음 변경의 롤백 기준 | `541d701d544eea6a8a4e4836047077eaf9cfaf30` / `08C061EE35A1A01788F05B00EE7395AA40774150C92C06726A92F3DF1BF75C3C` 유지 |

[실제 후보 설치본](C:/Users/user/Desktop/SmartFactory/PDCA_UNSIGNED_CANDIDATE_20261013_a6f804d2/source/v2_next/dist/smart-factory-logger-v2%20Setup%201.0.27.exe)을 보존한다.
로컬·원격 tag 목록에서 버전 충돌을 확인했으며 새 tag·push·publish는 하지 않았다.
후속 보고서의 문서 commit은 이 설치본의 build commit을 대체하지 않는다.

## 소스 확정과 누락 테스트 보완

`fc14c2973ba90b359b4a9a7893428d084034fe78`에서 기존 로컬 변경과 버전 1.0.27을
확정한 뒤 별도 local clone을 만들었다. 새 checkout의 최초 health는 exit 0이었지만
backend 903개뿐이었다. 기존 개발 환경의 920개와 비교해 `.gitignore` 때문에 추적되지 않은
`test_observability_service.py` 12개와 `test_schemas.py` 5개를 확인했다.

두 파일의 기존 내용을 그대로 포함하고 정확한 추적 예외 2줄을 추가한 commit이 `19e0e314`다.
focused 17개 검사는 exit 0이며 46개 테스트 파일과 backend source 83개의 Git/checkout
동일성을 확인했다(텍스트 줄바꿈 정규화 명시). 최초 903개 결과는 전체 검사와 동등하지 않다.
fc14c297 설치본은 만들지 않았다. 후보 제품 변경의 내용은 build commit의 CHANGELOG를 따른다.

## 최종 환경과 실제 검사

Node 22.22.2/Python 3.12.6, 별도 checkout의 새 venv에서 출시 잠금 wheel 40개를
`--require-hashes --only-binary=:all:`로 설치하고 설치 보고서의 해시와 버전을 대조했다.
root/frontend `npm ci`, pip check는 exit 0이다. 기존 개발 venv는 변경하지 않았다.
최종 빌드 전후 clean HEAD와 같은 40개 버전을 다시 확인했다.

| 실제 명령·검사 | 결과 / 실제 exit |
|---|---|
| `npm run health` | 263.563초 / 0 |
| health의 backend unittest | 920개 중 919개 통과, 비공개 F01 fixture 미제공 1개 skip |
| health의 frontend / frontend Node / Electron / 의존성 | 각각 434 / 9 / 94 / 15개 통과 |
| TypeScript·frontend lint·backend Ruff·mypy·QA 도구 selftest | 통과, mypy source 9개 |
| `scripts/read-operating-data-inventory.test.ps1` | 0; 관리자 결과 폴더 실제 생성 제외 |
| `scripts/server-stage-v1026/test-cold-backup-streams.ps1` | 93조건, 0; 합성 fixture, multi-GiB·실제 서버·앱 복구 QA 제외 |
| `scripts/deploy.ps1` | frontend/PyInstaller/portable build, 197.563초 / 0 |
| `npm run dist -- --win nsis --x64 -c.win.signExecutable=false -c.forceCodeSigning=false --publish never` | 84.141초 / 0 |
| 실제 payload·backend manifest/provenance·ASAR·미서명 검사 | 각각 0 |

health stdout SHA256은 `de1a9f28160dd0ce4c49456d26fa8e08fec5c2b433d01d4f8527fe5716a95e6b`,
stderr는 `f35f5b073ea351587ecabbcb9c44fb49a63298c076db2910358bca7ba30b8ac0`이다.
명령 argv·실제 exit·원문 출력은 보존 묶음의 각 terminal JSON/log에 있다.
이전 사전 시험에서 발생한 간헐 종료 receipt timeout은 이번 실행에서 재현되지 않았지만
원인 규명·수정으로 판단하지 않는다. 기존 private F01 skip과 npm audit 잔여 high 항목도 유지한다.
PyInstaller의 `Hidden import "tzdata" not found!` 경고와 framework deprecation 경고를
보존했으며 경고 없는 빌드나 패키지 런타임 PASS로 보고하지 않는다.

## 실제 설치본에서 검증한 범위

Electron 44.3.0/electron-builder 26.15.3을 사용했다. 인증서 자동 탐색·주입과
publish를 비활성화했고 앱의 버전/아이콘 resource 편집은 유지했다.
설치본과 앱 version resource는 1.0.27에 일치하며 backend 버전은 provenance로 연결한다.
실제 frozen backend의 runtime 응답은 아직 검사하지 않았다.

빌드 cache의 7za로 실제 NSIS 설치본의 embedded 7z 앱 payload를 추출했다.
1,814파일/562,748,426 bytes의 목록·길이·해시가 `win-unpacked`와 전부 일치했다.
frontend 50파일은 resources/frontend와 backend 내부 두 위치에서 일치한다.
backend manifest 1,687파일과 clean HEAD provenance, ASAR의 runtime source와 package
name/version/main을 대조했다. ASAR 텍스트 source 비교는 UTF-8 LF 정규화 방식이다.

7z offset 240,882 + archive 163,919,598 + tail 457,114 = installer 164,617,594 bytes다.
`There are data after the end of archive`는 이 embedded 구조의 관찰 결과로 기록했다.
installer prefix/tail은 전체 해시·Authenticode만 확인했다. NSIS 설치 제어 로직·uninstaller
실행과 파일/registry 적용은 설치 QA에서 확인해야 한다. `nsis-outer` 폴더는 실제 앱 payload다.

소스 ZIP `source-19e0e314.zip`은 7,845,741 bytes,
SHA256 `2a3a4422afa47131e4831b102492c7a676115822b50d88b418bf52622713c6e3`이다.
1,088파일이 clean checkout의 실제 바이트와 일치한다. Git blob 대조에서 텍스트 980개의
CRLF 변환을 명시적으로 처리했으며 raw Git bytes 전부 일치로 표현하지 않는다.

처음 source ZIP 검산은 CRLF 가정 오류로 exit 1, 첫 NSIS 검산은 없는 npm `7zip-bin`
경로로 exit 1, 다음 검산은 존재하지 않는 nested `app-64.7z` 가정으로 exit 1이었다.
원본 실패·성공한 추출 결과를 보존하고 실제 구조에 맞춘 후속 r2/r3 검산이 exit 0이었다.
`candidate-build.json`은 빌드 직후의 PENDING 상태를 유지한다. 후속 최종 상태는
`candidate-payload-verification.json`, `source-archive-verification-r2.json`,
`candidate-closeout.json`에 별도로 기록했다.

## 보존과 다음 실행 기준

명시적 입력 275파일/176,008,626 bytes와 ZIP 276항목의 길이·해시, 원본 재검산 및
공유 사본을 검증했다. snapshot 도우미 actual exit 0, 34.015초다.

- [검토 ZIP](C:/Users/user/Desktop/SmartFactory/PDCA_CANDIDATE_RECORDS_20261013_a6f804d2/PDCA_UNSIGNED_CANDIDATE_a6f804d2.zip): 173,436,255 bytes.
- ZIP SHA256: `c8421737cc7b1c89fc87788b40d53b2e1a030dceff3408d24f1008a48adcddf5`.
- manifest SHA256: `8dce9a90c1c1a1762d98f0c7046a278877fd11ba8630dfebfb4ec3dc6da0a348`.
- [검산 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_CANDIDATE_RECORDS_20261013_a6f804d2/snapshot-receipt.json).
- 공유: `Z:/SmartFactory/20261013/records/PDCA_UNSIGNED_CANDIDATE_a6f804d2`.

installer·source ZIP·도우미·로그·실패 기록·JSON·변경 전 버전 파일·selftest 결과·빌드
경고를 포함했다. source checkout/의존성 환경, build cache/temp, 중복 추출 payload와
portable ZIP, 합성 junction/ADS fixture는 제외했다. 기본 스트림 스냅샷이며 전체 작업
환경 백업이나 ADS 보존·작업 루트 봉인이 아니다. 공유 보존을 서버 최종 전달로 보고하지 않는다.

다음 순서와 판정 기준:

1. 같은 installer의 격리 runtime·신규 설치·업그레이드·재시작·이전본 복구를 확인하고 설정/
   데이터·정상 종료 증거를 검산한다. 실제 runtime의 tzdata 관련 오류 유무도 확인한다.
2. 승인 실장비 프로파일·물리 비교, 과거 timeout/drop/전체 데이터 처리, browser/CDP OFF와
   실제 서버 시작 3회 등 남은 근거를 확보한다. 실장비 모델명은 기존 사용자 답변대로 미정이다.
3. 최종 설치본의 현장 초기 15분/120분 canary·전체 새 데이터 QA 및 승격/적용 확인 후에만
   운영본과 다음 롤백 기준을 갱신한다. 이번 정적 검증만으로 R6를 완료 처리하지 않는다.

## 2026-10-13 frozen backend 격리 시작·수집·재시작·정상 종료

같은 installer에서 추출한 backend를 새 폴더에 복사해 파일별 해시를 대조한 뒤 실행했다.
`V2_MODE=MOCK`, loopback 합성 SPOT, 별도 AppData/config/데이터 경로를 사용했다.
제품 코드·installer 바이트는 변경하지 않았다. Electron 화면·installer·실장비는 실행하지 않았다.
frontend HTML/JS를 HTTP로 읽은 검사는 화면 렌더링 QA가 아니다.

| 시행 | 결과 | 범위 |
|---|---|---|
| 최초 도우미 `6f217cb9` | helper exit1, backend 정상 정리 exit0 | 실제 `./assets` 경로를 `/assets`로만 가정해 관측 전 중단. 실패 원문 보존 |
| 기본 API `9c8470ad` | 30초/20초 두 실행 모두 OS exit0 | HTTP104개 성공, CSV246행·observation19행. 이미지 요청이 없어 이미지0 |
| 이미지 포함 `f52b83d6` | 30초/20초 두 실행 모두 OS exit0 | HTTP129개 성공(이미지25 포함), CSV176행·observation19행·이미지25개 |

기본 API 시행은 backend-only 배치로 내부 frontend fallback과 `legacy_meipass` 경고2개가
발생했다. 이미지 시행은 actual payload의 frontend resource도 실제 상대 위치에 복사해
`frontend_source=resources`, `frontend_runtime_warning=none`, HTML/JS HTTP200을 확인했다.
이미지 저장은 log 하위 별도 폴더이며 기존 파일을 덮어쓰지 않는 새 실행별 루트를 사용했다.

이미지 시행의 두 시작 준비는1.625/1.531초, health27개 최대30.2997ms였다. 이는 짧은 합성
backend 시험이며 정식 120초 준비/300초 성능이나 실장비 시작3회를 대체하지 않는다.
각 실행은 버전1.0.27/`runtime_kind=frozen`과 exact executable path를 반환했다.
shutdown begin/final의 SHA sidecar·commit·PID·generation을 실제 OS 종료0과 연결했다.
sidecar의 `process_exit_observed=false`·`installation_clearance=false`는 그대로 보존한다.

독립 `verify_runtime.py`는 actual exit0이었다. 이미지 시행의 두 CSV103/73행 sequence와
같은 logger 세대의 final closeout, 누적 observation19개/hash, 첫 실행 뒤 파일18개의 재시작
후 접두부 보존을 검산했다. 이미지 writer는 각각15/10개 저장, 종료 시 실패/drop/queue/
inflight/unfinished0, writes_drained/worker_stopped true이며 총25개 fact와 일치했다.
초기 실패를 포함해 소유한 backend PID5개는 모두 종료됐음을 확인했다.

기존 최종 source의 실제 검사 명령은 기록 묶음의 terminal JSON argv를 따른다.

- `validate_spot_image_files.py`: exit0,25개 길이·해시·디코딩·fact 일치, 고아0/문제0.
- `validate_csv_v2_shadow.py`: exit0, 마지막 CSV73행과 누적 observation19개/image25개 및
  final manifest 확인. 첫103행은 별도 독립 sequence/closeout 검산 범위다.
- CSV 검사에는 MOCK의 두 position 열 값 없음 경고2개가 있다. realtime observation 연결0,
  v1 비교 미실행, server promotion profile 요구false, phase/changeover/linkage 일부
  unknown/not applicable을 보존한다. 이 PASS는 실장비/전체 데이터/정식 QA 통과가 아니다.
- 관찰한 로그에는 tzdata 관련 import/timezone 오류가 없었다. 모든 timezone 경로를
  검증하거나 기존 빌드 경고를 제거한 것은 아니다.

세 시행과 검산의166파일/6,556,200 bytes를 ZIP167항목과 전수 대조하고 공유 사본을
확인했다. 보존 도우미 actual exit0. backend/frontend 바이너리 중복·tmp/localappdata·
validator 임시 환경은 제외했으며 실제 installer는 앞선 후보 묶음에 보존한다.
기본 스트림 스냅샷이고 전체 환경/ADS 백업·작업 루트 봉인은 아니다.

- [runtime 검토 ZIP](C:/Users/user/Desktop/SmartFactory/PDCA_RUNTIME_RECORDS_20261013_f52b83d6/PDCA_FROZEN_RUNTIME_f52b83d6.zip):980,314 bytes.
- ZIP SHA256 `cb10e613bfc69371530873d2d59a68996434c52783c09b1a0519e5058ae06a91`.
- manifest SHA256 `f97c44d13c5420d4e3c30cba010e26b1764005d18e1508280ef7275110184703`.
- [독립 검산](C:/Users/user/Desktop/SmartFactory/PDCA_RUNTIME_RECORDS_20261013_f52b83d6/runtime-verification.json),
  [보존 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_RUNTIME_RECORDS_20261013_f52b83d6/snapshot-receipt.json).
- 공유 `Z:/SmartFactory/20261013/records/PDCA_FROZEN_RUNTIME_f52b83d6`; 서버 최종 전달 아님.

후속은 동일 installer의 격리 신규 설치·업그레이드·이전본 복구와 packaged Electron 전체 앱,
설정/데이터 보존이다. 승인 장비 프로파일·물리 비교, 과거 timeout/drop 처리, 전체 데이터·
성능·현장15분/120분 QA·승격/적용 확인은 남아 있다. 운영본/다음 롤백 기준은 유지한다.


## 2026-10-13 실제 NSIS 설치·업그레이드·이전본 복구

동일 v1.0.27/19e0e314/F17040FC 후보와 현재 운영·롤백 기준 v1.0.26/541d701d/08C061EE를
새 offline Windows Sandbox에서 실행했다. 후보 신규 설치·제거, 기존본 신규 설치,
후보 업그레이드·시작·재시작, 기존본 재설치·복구 후 시작 순서다. per-user 기본 설치 경로와
실제 packaged Electron/backend를 사용했다. 두 설치본의 `NotSigned`를 다시 확인했다.
호스트와 운영 서버에 설치하지 않았고 운영본·다음 롤백 기준은 갱신하지 않았다.

Network/clipboard/GPU/audio/video/printer를 끈 Sandbox에 input을 읽기 전용, output만
쓰기로 연결했다. input677파일/363,444,383bytes를 guest로 복사해 전수 재해시했다.
외부 IPv4는 없으며 `V2_MODE=REAL`의 실제 PLC/SPOT 드라이버가 loopback 합성 장비에
연결됐다. 제품/금형99001/1, 온도500°C·count20·main pressure30·speed1과 합성160×120 JPEG를
사용했다. 실제 생산 제품번호나 장비 설정을 확인한 시험이 아니다. 표시 성능·현장15/120분
QA는 이 약74~75초 실행들로 대체하지 않는다. renderer ready는 로그로 확인한 범위다.

| 단계 | 검증 결과 |
|---|---|
| 후보 신규 설치 | NSIS exit0, 설치 파일1,814개·build commit·등록 버전·바로가기·uninstaller 일치 |
| 후보 제거 | uninstaller exit0, 앱/등록 제거와 AppData/profile 미생성 확인 |
| 기존본 신규 설치 | NSIS exit0, 설치 파일1,771개·등록/바로가기·build commit 일치 |
| 기존본→후보 업그레이드 | NSIS exit0,1,814개 일치, 닫힌 config/AppData/profile/data 전후 해시 동일 |
| 후보→기존본 복구 | NSIS exit0,1,771개 일치, 닫힌 config/AppData/profile/data 전후 해시 동일 |

| 실제 앱 실행 | CSV v1/v2 각각 | 해당 세대 observation | 새 이미지 | main/backend OS exit |
|---|---:|---:|---:|---|
| 기존본 최초 |303행|24|66|0/0|
| 업그레이드 후보 |280행|25|67|0/0|
| 후보 재시작 |322행|25|66|0/0|
| 복구 기존본 |302행|24|65|0/0|

합계 CSV v1/v2 각각1,207행, observation98개, 이미지264개다. 네 실행의 logger/SPOT 세대는
서로 다르고, 각15개 표본의 실제 executable/version/commit·resources frontend·장비 snapshot
진행·운영자 fixture·비loopback 연결 없음과 이미지200을 검산했다. 후보 history 페이지와
재시작 후 이전 cursor reset도 확인했다. 종료는 정확한 owned PID/create_time/exe/hash의
WM_CLOSE였고 강제 종료는 없다. 모든 descendants/8000 listener가 사라졌음을 확인했다.

기존 source의 `validate_csv_v2_shadow.py`와 `validate_spot_image_files.py`를 각 실행의
닫힌 사본에 실행한 총8개 명령은 actual exit0이었다. v1/v2 행 차이0, observation key 연결
100%·누락0, 이미지 길이/해시/디코딩/fact·final manifest 일치, 고아0/문제0이다. CSV/metadata와
기존 이미지의 이전 바이트, 누적 fact 접두부, 전체 closed-data 복사본도 대조했다.
프로필은 ZIP 내부 모든 파일의 길이·해시를 원본 inventory와 대조했다.
shutdown begin/final·sidecar·세대/commit/PID와 native exit를 연결했으며 이미지 저장 실패/drop/
queue/inflight/unfinished는 모두0, writes_drained/worker_stopped true였다.
각 CSV 검사에는 position 두 열 값 없음 경고가 있고 phase/changeover/linkage 일부는
unknown/not applicable, server promotion profile 요구는 false다. 전수 운영 데이터 PASS가 아니다.

독립 `review_matrix.py`는 **actual exit1**,111조건 중107통과·4실패다. 실패4개는 각 누적
로그의 “error 없음” 조건이다. 중복 제거한 이미지 `shutdown` HTTP502가6건(실행별1/2/2/1)
있고, 전부 owned WM_CLOSE 이후 native exit 이전이다. 별도 `classify_findings.py` exit0으로
시각/종류/경로/표본을 검산했으며 원래 실패를 PASS로 바꾸지 않았다. 종료 전 직접 이미지
요청60개는 모두200이다. 현재 판정은 `INSTALL_RECOVERY_DATA_VERIFIED_SHUTDOWN_HTTP_502_OPEN`.

소스에서 `main.js`의 종료는 backend closeout 후 app.quit를 수행하고, 이미지 서비스는
정지 이후 `SpotImageFetchError("shutdown")`를 반환하며 `backend/app.py`의 공통 처리에서
502로 기록한다. 화면 polling이 종료 대기 중 지속됐다는 해석은 이 코드와 관측 시각에 근거한
추론이다. 제품 코드는 수정하지 않았다. 종료 요청·renderer polling의 경계를 후속 확인하되
전송 오류·writer 실패·종료 검증을 숨기거나 약화하지 않는다.

도우미 실패도 보존했다. 최초 profile 캐시 경로는 원본231자에서 복사 대상275자로 길어져
copytree가 중단됐다. 이때 앱/backend는 이미 정상 exit0이었으나 PowerShell Start-Process
래퍼의 Python exit가 null이라 외부 CLI exit0을 전체 성공으로 해석할 수 없었다.
원본은 그대로 두고 프로필 ZIP 보존/전수 대조, native handle 유지와 의도적 exit7 검증을
추가했다. 재개r2는 UTF-8 traceback의 cp949 읽기 오류로 설치 전 exit1, 명시적 UTF-8의
r3는 원본 설치/닫힌 상태를 재확인한 후 남은 단계만 실행해 실제 child/wrapper/host exit0이다.
첫 inline PowerShell guest cold 확인은 durable 출력이 없어서 불완전으로 남겼고,
후속 `-File` 실행에서 실제 빈 process/listener 목록과 loopback-only를 확인했다.

모든 필요한 데이터/AppData/profile/종료 자료 회수·검산 후 owned Sandbox만 종료했다.
`wsb stop` exit0와 목록에서 해당 ID 부재를 확인했다. 시험 프로세스 강제 종료는 없다.
제품 코드가 바뀌지 않아 전체 health/빌드는 반복하지 않았고 도우미 Python 정적 검사와
PowerShell 구문 검사는 exit0이었다. 운영 서버에는 접속·설치·변경하지 않았다.

- [원문·독립 검사](C:/Users/user/Desktop/SmartFactory/PDCA_NSIS_20261013_5d8f24ab/review/review.json),
  [502 분류](C:/Users/user/Desktop/SmartFactory/PDCA_NSIS_20261013_5d8f24ab/review/finding-disposition.json).
- [설치/복구 검토 ZIP](C:/Users/user/Desktop/SmartFactory/PDCA_NSIS_RECORDS_20261013_5d8f24ab/PDCA_NSIS_5d8f24ab.zip).
- 입력 1904파일/386340215bytes, ZIP 1905항목/344722857bytes를 원본·ZIP·공유 사본과 대조.
- ZIP SHA256 `fe514e18de297f4ee5cad88a0ffd4887ab28e5db8164dd6d802477fe2436ad1e`.
- manifest SHA256 `7b7936a81c0e2abadd79e07baecf50045cc47f8958d81eccdf778556c0b0822e`.
- 공유 `Z:/SmartFactory/20261013/records/PDCA_NSIS_5d8f24ab`; 서버 최종 전달 아님.

두 installer·portable Python 포함 전체 input과 도우미·실패·닫힌 사본·검사 원문을 보존했다.
중복 baseline 추출 payload·validator 임시 환경·bytecode cache는 제외했다. 기본 스트림
스냅샷이며 전체 작업 루트 봉인이나 host/server 환경 백업은 아니다. 보존 도우미 exit0.
후속은 종료 이미지502 처리, browser/CDP OFF·서버 실제 시작3회, 승인 실장비 프로파일·
물리 비교·과거 timeout/drop·전체 데이터 처리와 최종 현장15분/120분 QA·승격/적용 확인이다.
전체 목표 active, R1–R6 HOLD, full_data_gate NOT_EVALUATED를 유지한다.
