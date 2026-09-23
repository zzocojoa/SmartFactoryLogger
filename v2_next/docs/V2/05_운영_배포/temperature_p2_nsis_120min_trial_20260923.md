# 미서명 NSIS 120분 현장 시험

2026-09-23 서버에서 실제 설치·120분 관찰·정상 종료·원본 복귀가 완료됐다.
자체 검토는 실행/회수 42 통과, 원문/production validator 16 통과,
실패 0이다. 이 결과는 미서명 내부 검증이며 정식 운영 승격이 아니다.
완료 콘솔 종료 후 원본 앱의 생존·화면 값 갱신과 현재 작업 정보의 사용자 확인까지 완료됐다.

## 대상과 실제 시간

후보 commit `d254871f89c98154b4e32879e29601df78f7e159`, 원본 복귀 commit
`d7a1b20f96711fb07fc7add0867e79ee36506fce`. 표시 버전은 둘 다 1.0.26이며 commit·EXE·
설치 payload를 구분했다. 기존 installer를 사용했고 후보 재빌드는 하지 않았다.
서버 결과 폴더: `C:\Users\user\Desktop\SmartFactory\N120-f0b7e4db`.

관찰: 2026-09-23T09:27:40.2616502+09:00 ~ 2026-09-23T11:27:40.6654048+09:00,
monotonic 실제 7201.4850877초, 449표본.
실제 wall timestamp 간격도 120분 이상이다. 이전 Sandbox의 가속 clock을 사용하지 않았다.
원본 정상 종료는 09:23:28, 후보 준비 완료는 09:26:46,
후보 정상 종료는 11:27:44, 원본 복귀 후 수집 확인은 11:30:42~11:31:14(KST)다.
설치/전환 구간에는 수집 공백이 있으며 이를 120분 관찰 시간에 포함하지 않았다.

## 설치·수집·종료 결과

- 후보 설치 1,813파일(원래 payload 1,812 + uninstaller)의 고정 SHA256을 검증했고,
  원본 재설치 뒤 1,646파일의 기존 tree SHA256이 일치했다. 두 installer exit 0,
  등록 경로/바로가기와 설치 전후 선택 상태/profile 파일이 보존됐다.
- 후보 main/backend와 service 세대가 관찰 동안 같고 일반 사용자 권한이었다.
  저장 행 445→31496, SPOT poll
  105→7304. 최종 CSV 31,499행,
  fact 7,305개. fact 순번 gap/중복/invalid identity/미연결 키 0.
- 모든 점검 표본의 service/driver thread가 살아 있었고 PLC snapshot·CSV 크기·history 순번이
  증가했다. source degraded 표본 0. writer write/spool/rejection 및 저장/연결/판정 오류 0.
  표본 queue 최대 0, pending 최대 1.
  연속 high-watermark를 관측한 것은 아니며 표본 사이의 순간 상태까지 0이라고 주장하지 않는다.
- Count 0/1/2 자연 관찰 표본은 각각 32/11/9회다. 원문 해당 행 수는
  {'0': 2296, '1': 803, '2': 646}. history 898페이지의 identity·cursor·순서를 확인했다.
- 원본/후보 모두 main/backend exit 0, port/process 해제, forced=false.
  후보 9개 backend 종료 단계, CSV finalized, fact drain 및 종료 diagnostic trace의
  SHA256 `845C125DE631AB0C72277AC67ED8B3E0B6ACAE42BF67513477D6248581B7D2BA`를 대조했다.
- 원본 복귀 표본에서 CSV 행 181→336,
  SPOT poll 40→71가 증가했다.
  회수 중 UI도 Running 및 통신 OK를 표시했다. 서버 프로세스에 추가 종료/설치 작업 없음.

## 원문 검증과 제한

Temperature 상태: `{'startup_pending': 14, 'stale': 184, 'valid': 29382, 'under_range': 1919}`.
nonvalid Temperature blank, startup key blank, 연속 sample_seq, 모든 observation key 연결,
idle changeover ID 배제를 확인했다. under-range expectedness 분포:
`{'unknown': 254, 'expected_candidate': 1665}`. 일부 stale/under-range 행은 정상 숫자로 승격하지 않았다.
fact duration 상태: `{'ok': 7305}`.
비동기 diagnostics 상태: `{'missing': 1, 'async_complete': 6858, 'async_partial': 446}`.
async_partial 또는 missing을 전체 정상 진단으로 바꾸지 않았다.

이미지 fact는 누적 파일이므로 시작 metadata의 해시/행 수와 종료 final manifest를 별도로
검증했다. 후보 세션 추가 기록 6,717건,
최종 3,175,882행/1,627,147,208바이트,
SHA256 `c8c54549a7e91535971b4f103bd03d24ae260e3c397aeec26878e63827655cef`.
종료 후 원본이 추가 기록한 tail을 제외한 정확한 prefix를 검증용 새 파일로 만들었고,
시작/종료 해시가 모두 원문과 일치했다. metadata/최종 manifest 원본은 수정하지 않았다.
엄격한 최종 manifest 검사를 포함해 실제 build의 `validate_csv_v2_shadow.py` exit 0.
개발 PC에서 대용량 원문을 검사한 실제 소요 시간은 1477.1초다. 서버 설치/
관찰 시간과 구분한다. 회수 이후의 검증은 개발 PC에서만 실행했다.
사진 파일 자체와 장비의 물리 상태는 이번 원문 검증 대상이 아니다.

기존 `fingerprint_mismatch`, operator/comparator 미검증, drift count 1은 유지된다.
운영 설정·OS 시각·장비 sampling/timeout 변경이나 인위적 장비 장애 주입 없음.
자정 rollover·실제 wall-clock 보정·실장비 미종료 강제 재현은 이번 120분 시험으로 검증하지
않았다. V1은 비활성이어서 비교 미실행이며, 이전 G/T/C/L1/P2 합성 회귀를 이번 실행으로
다시 계산하지 않았다. over-range는 이번 원문에서 0행으로 현장 발생 검증은 미실행이다.

## 데이터 보존과 회수 범위

원본 observation fact 4,878,532,000바이트, 기존 archive 488,471,940바이트와 후보 fact는
서버에서 전체 SHA256을 대조했다. 두 schema 전환 54→55→54의 archive와 닫힌 CSV/metadata가
보존됐다. 4.88GB 원본 fact/기존 대형 archive/사진 폴더/전체 과거 로그는 회수하지 않았다.
복귀용 보관은 도우미의 소형 상태/profile 파일 범위다. 자동 복구 설치나 과거 metadata 복원 없음.

Codex가 서버 탐색기로 `Z:\SmartFactory\20260923\return\P2_N120_RESULT`에 복사하고
개발 PC `C:\Users\user\Desktop\SmartFactory\P2_N120_REVIEW_R1`로 회수했다.
실행 결과 5,491파일과 JSON 2,735개의 해시를 대조했다.
결과 SHA256은 서버 콘솔과 동일한 `75F7D0E8420DFF1E3D2F7919534C3843E55122593FF61A550A2302210271E30E`다.
원문 검증용 회수는 후보 CSV/metadata/observation archive/최종 image manifest 및 누적 image
fact 한 파일(약 1.63GB)이다. 이는 사후 검증 자료이며 복귀용 전체 데이터 백업이 아니다.
누적 image fact에 과거 행이 포함됨을 명시한다.

## 파일과 검증 기록

제품 코드 변경 없음. 현장 결과 정리 당시 저장소 변경은 이 보고서와 사전점검 보고서의 결과 링크였다.
당시 선행 39파일과 기존 준비 보고서/도우미 해시가 그대로임을 확인했고 Git 게시는 수행하지 않았다.
사용자 후속 승인에 따른 게시 범위는 10분·격리 설치·사전점검·120분 결과 4개와 P2 상태 문서 3개다.
공개본에는 실제 작업 식별값을 싣지 않으며 로컬 해시 결합 원문과 이전 보고서 사본은 보존한다.
실제 검토 명령은 `review_receipts.py`, `review_data.py`이며 production validator의 정확한
command/cwd/exit code는 `data-review.json`, 원문은 `production-validator.log`에 보존했다.
검토 스크립트 ruff exit 0, `git diff --check` exit 0. 제품 변경이 없어 전체 제품 QA를
이번 회수 단계에서 다시 실행하지 않았다. 독립 검토가 아닌 자체 검토다.
원문 검토의 초기 idle 보조 조건은 CSV에 없는 `idle` 값을 사용했으므로 그 조건은 검증
coverage로 세지 않았다. 별도 `verify_idle_rows.py`가 실제 `idle_candidate` 3,696행이
존재하고 changeover ID가 전부 빈값임을 확인했다(exit 0). 원문 검사 수는 초기 조건 1개를
제외하고 이 실제 검사 1개를 포함했다. 기존 결과/스크립트는 수정하거나 삭제하지 않았다.

## 콘솔 종료 후 최종 확인

복귀 직후와 12:54 이후 화면의 작업정보는 서로 달랐으며, 후속 화면에는
적용 시각 12:38:31이 표시됐다. 기존 작업값으로 덮어쓰지 않았다.
2026-09-23 사용자가 완료 콘솔을 닫았으며 현재 제품·금형이 실제 작업과 일치한다고
명시적으로 확인했다. 이어 14:02~14:03(KST) 원격 화면에서 콘솔이 사라진 상태로 원본 앱이
Running / EX OK / LS OK / SPOT OK / Comm OK를 유지함을 확인했다. 두 화면 사이에
SPOT 온도·압력·메인 램 현재 위치가 갱신됐다. 정확한 작업 식별값과 측정값은 비공개 로컬
원문에 보존한다. 현재 제품·금형은 두 화면에서 같았다. 사용자 확인은 실제 작업 일치의 근거,
화면 관찰은 콘솔 종료 후 앱 생존·실시간 값 갱신의 근거로 구분한다.
이 마지막 확인에서 저장 파일을 다시 회수하거나 검증하지 않았으며, 저장·종료·복귀의
파일 근거는 앞서 완료한 receipt와 원문 검증을 따른다. 추가 실행/설치/설정 변경은 없다.

이번 미서명 내부 설치 시험의 남은 사용자 확인은 모두 종료했다. 추가 확인 기록은
`C:\Users\user\Desktop\SmartFactory\P2_N120_CLOSEOUT_R1` 및
`Z:\SmartFactory\20260923\records\P2_N120-closeout-R1`에 보관한다.
이전 `P2_N120_REVIEW_R1`의 해시 결합 결과와 당시 대기 상태 기록은 수정하지 않았으며,
이번 closeout 기록과 갱신된 보고서 사본을 별도로 연결한다.
공식 운영 승격은 별도 결정이며 이번 내부 시험 성공으로 자동 진행하지 않는다.

## 게시 증거 연결

로컬 원문 manifest `P2_N120_REVIEW_R1/EVIDENCE_MANIFEST.json`의 SHA256은
`EAE98FB0241A9DFAB7B6C80EA13AC027BA5CDEEC510B605B8C85990A38F16267`이다.
콘솔 종료 후 추가 확인 manifest `P2_N120_CLOSEOUT_R1/MANIFEST.json`의 SHA256은
`C9B0F091173E135AF7BB1E6CABE93F74CC6204B8ECB12E0E4A132963373946B2`다.
공개 문서만으로 비공개 원문을 재현할 수 없으며, 실제 명령·원문 로그·파일 해시는 해당 자료에 보존한다.
문서 게시에는 제품/운영 데이터 이관이 없고 서버의 실행 상태를 변경하지 않는다.
게시 내용의 오류는 문서 정정 또는 해당 문서 커밋 revert로 되돌릴 수 있다.
