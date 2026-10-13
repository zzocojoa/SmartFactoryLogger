# v1.0.27 미서명 후보 빌드·정적 패키지 검증

2026-10-13. clean commit `19e0e314f7c1dc29b38691382aeda637f4ff3032`에서 미서명
후보를 빌드했고 실제 설치본의 앱 payload와 출처를 검증했다. 설치·실행·서버 적용·운영 승격은
아직 수행하지 않았다. 전체 목표 active, R1–R6 HOLD, full_data_gate=NOT_EVALUATED다.

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
