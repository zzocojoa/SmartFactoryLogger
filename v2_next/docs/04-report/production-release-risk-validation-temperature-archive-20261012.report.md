# 2026-10-12 온도 원본 사본 작업과 압축 자료 범위 확인

최신 사용자 지시에 따라 미서명 내부 운영 설치본을 대상으로 후속 PDCA를 계속 진행한다.
서명 요구는 제거됐으며 R1~R6의 남은 기술 QA는 HOLD다. 이번 단계에는 운영본 교체·종료/재시작·
장비 설정 변경·롤백 기준 갱신을 하지 않았다.

새 작업 루트는 `C:/Users/user/Desktop/SmartFactory/PDCA_DATA_20261012_ed3ad6e0`다.
온도 사본과 전체 구조 검사 프로세스는 종료됐으며 아래에 실제 종료 코드와 결과를 기록한다.
완료 증거 1,688파일/27,542,557,179 bytes를 해시로 봉인했으며 원래 하위 봉인 자료는 그대로 보존했다.
`data-stage-file-manifest.json` SHA256은
`fde0fcbbcbe90c4301adeba8671782820bd9b3ac3cfab6dca65fa5a542cae35c`다.
독립 경로/합계 정산과 1,471개 사본 항목의 최종 manifest 대조는 exit 0이다.
공유 `Z:/SmartFactory/20261012/records/PDCA_DATA_ed3ad6e0`에는 manifest와 회수/완료 영수증만
복사하고 해시를 확인했다. 27GB 전체 사본의 공유 전송 또는 서버 로컬 전달을 주장하지 않는다.
이 완료 루트에 후속 결과를 추가하지 않으며 새 조사는 별도 실행 폴더를 사용한다.

## 서버에서 확인한 원래 NAS 경로

서버 Chrome 원격 데스크톱의 일반 탐색기에서 기존 scope의 원래 NAS UNC 주소를 직접 열었다.
192.168.0.235의 스마트팩토리 공유가 열렸고, `출구부 온도` 안의 1·2·3호기 폴더가 보임을 확인했다.
`server-original-NAS-root.jpg`, `server-temperature-subtree.jpg`에 실제 화면을 보존했다.
터미널 입력·인증·네트워크/권한 설정 변경은 하지 않았다.

이 관측은 서버 GUI의 해당 폴더 접근 증거다. 추가 NAS PS5.1 도우미의 실제 실행·해시/ACL guard,
서버 전체 파일 목록·내용의 검증을 수행했다는 의미로 확대하지 않는다.
개발 PC 전체 NAS 목록의 원래 source 경로와 서버 GUI의 경로가 일치하므로,
추가 도우미 미실행을 NAS 연결 자체가 미확인인 장애로 처리하지 않는다.

## 온도 원본 선택과 현재 복사 상태

입력은 이전 전체 NAS 목록의 `출구부 온도` 하위 모든 일반 파일이다.
선택 CSV 1,470개·XLS 1개, 총 1,471개/27,534,639,606 bytes다.
선택 항목의 가장 최근 mtime은 2026-09-16T04:48:04.046677Z였다.
목록 manifest SHA256은 `41090ab6dfd6856ddd03ede480227c78c6c4d8e659ec3aa52b510823e124daf2`,
entries SHA256은 `df802ac51f2e668f47242c67942dc10de21daab9d9a35bbc544a928c511890c5`다.
원본 목록·이전 봉인 자료를 수정하지 않았다.

개발 PC native Windows PowerShell 5.1의 `copy-temperature-inputs.ps1`로 원래 UNC 파일을 읽는다.
첫 시도는 JSON 배열을 `@(ConvertFrom-Json ...)`으로 감싸 Count가 1이 되는 PS5.1 차이 때문에
입력 수 검사에서 exit 1이었다. 실제 복사/원본 변경 전에 중단됐으며 소스와 로그를 `attempt-01`에 보존했다.
직접 배열 대입은 Count 1,471/합계 27,534,639,606을 반환함을 실제 native PS5.1에서 확인했고,
그 방식으로 수정한 두 번째 실행은 별도 로그의 session 79262에서 5,791.790268초/exit 0으로 완료됐다.

두 번째 실행에서 모든 1,471개 파일을 `FileShare.Read` 스트림으로 먼저 열었고,
크기·원래 mtime ns·reparse 경계·최근 수정 제외 조건을 대조했다.
`PINNED_ALL_SELECTED_INPUTS=1471`을 확인했다. cooperating SMB write/delete open을 거부하는 공유 모드이며,
다른 프로토콜 writer를 통제하는 전체 NAS/서버 atomic snapshot으로 주장하지 않는다.
사본은 `temperature-copy`의 새 폴더에만 쓰며 같은 입력 스트림의 복사 SHA256과 닫힌 사본 해시를 대조한다.
전부 복사한 뒤에도 모든 입력 핸들을 유지한 상태로 각 원본을 다시 해시/mtime 대조한 후 manifest를 만든다.
`temperature-copy-manifest.json` SHA256은
`22ac95a0dd68b2a066bc787ca71e236eea7c4d7db883cd992610bf25860a98eb`이며 콘솔 해시와 같다.
독립 정산은 1,471개/27,534,639,606 bytes, 고유 상대경로 1,471개와 실제 사본 경로 집합,
모든 입력 핸들의 최종 재해시·mtime 대조를 확인했다. 기록은 `temperature-copy-independent-manifest-check.json`이다.
입력 핸들은 완료 후 닫혔다. 앞선 1,300개 진행 관측은 당시 기록으로 보존하며 최종 완료와 구분한다.
시작 시 개발 C 여유는 74,755,665,920 bytes였고, 도우미는 선택 전체 용량 외 10GiB 여유를 요구했다.
원본·기존 증거를 삭제해 공간을 마련하지 않았다.

첫 100개 완료 사본의 header를 별도로 관측했다.
XLS 1개는 BIFF가 아닌 serial/date preamble과 10열 탭 구분 텍스트였으며,
CSV에는 bracket 6열 header, 소문자 quoted 6열 header 및 header 없이 데이터가 시작되는 2개가 있었다.
파일 확장자만으로 Excel 이진 파일 또는 공통 SFL 스키마라고 가정하지 않는다.
이 관측은 header 조사이며 전체 CSV 행·생성자/센서 의미 검증의 PASS가 아니다.
최종 사본에 `audit_temperature_copies.py`를 실행한 session 20569는
1,812.516초/exit 1로 종료됐다. 모든 1,471개 사본의 검사 전후 해시·identity는 manifest와 같았다.
구문·인코딩 예외 없이 576,684,549개 데이터 기록을 읽었으며, 19파일의 행 너비 불일치 33건을 확인했다.
header 없는 2파일/1,061,679행은 6필드 데이터로 관측했지만 승인된 스키마·온도·시간 의미 검증에서 제외했다.
bracket 6열 1,033파일/422,036,252행, 소문자 6열 435파일/153,586,484행,
텍스트 XLS 1파일/134행과 합계가 일치한다.

| 전체 구조 검사 관측 | 결과와 한계 |
|---|---|
| 행 너비 | 19파일/33행 불일치. `structural_status=FAIL`, exit 1 |
| 구문·인코딩 | 선택 파일에서 parser/Unicode 예외 0; 내용·센서 의미 PASS로 확대하지 않음 |
| header 미확인 | 2파일. 원문에 header를 삽입하거나 현재 스키마를 임의 지정하지 않음 |
| 파일 내 인접 시간 감소 | 963파일/79,391,860건. 시간 순서 관측이며 clock 장애·데이터 손실 원인 확정이 아님 |
| 측정값 숫자 변환 불가 | 확인된 temperature 열 174,621,470건. 원시 placeholder의 당시 생산자 의미와 유효성은 미검증 |
| 전체 데이터 판정 | `full_data_gate=NOT_EVALUATED`; 당시 스키마/센서 계약, 전체 서버·이미지·압축 내용 검증 미완료 |

`temperature-csv-audit-records.jsonl`과 `temperature-csv-audit-summary.json`에 파일별 결과를 보존했다.
초기 examples는 시간 감소로 먼저 채워질 수 있어, 너비 불일치 33건을 별도 전수 재확인했다.
`investigate_temperature_widths.py`는 해당 19사본의 해시 전후를 대조하며 원문 행·앞뒤 행·파일 끝 바이트를
`temperature-width-investigation.json`에 기록했고 exit 0이다. 이 exit 0은 조사 정산 성공이며 자료 복구/PASS가 아니다.

18파일의 마지막 1필드 기록은 모두 NUL 문자뿐이며 총 30,854개 NUL을 확인했다.
나머지 `2호기/2025년도 raw data/LandData 2025-06-16-08-27-25.csv`의 15개 행은
7~9필드이며 날짜·시간·SPOT 문자열의 기록 조각이 붙은 원문 형태다.
복사 전후 원본 해시와 사본 해시가 같으므로 이번 복사로 정상 원문이 변형된 것으로 분류하지 않는다.
당시 생성/저장 실패 원인·복구 가능성·사용자 본인의 처리 판단은 아직 미확정이다.
이 과거 LandData 자료를 현행 SFL 후보가 생성한 실패로 귀속하지 않는다.
파일별 SHA256/문제 record 위치와 처리 검토 양식은 `temperature-data-disposition-review.md`에 정리했다.

## ZIP 중앙 목록 확인과 남은 두 파일

고정 전체 NAS 목록의 ZIP 439개(58,292,297,947 bytes)를 선택했다.
`index_archives.py`는 원본을 Read 공유로 열어 ZIP/ZIP64 중앙 목록만 읽으며,
항목 이름으로 파일을 실행하거나 경로에 압축 해제하지 않는다.
원본 크기/mtime과 전후 identity를 대조하고 전체 내용 CRC/바이트 해시 검증은 별도 상태로 남긴다.
첫 전체 실행은 437.078초, 완료 436/미완료 3으로 exit 1이다. 실패를 PASS로 재작성하지 않았다.

그중 `#recycle/mes_data.zip`은 ZIP 오류가 아닌 300,000항목 메모리 제한이었다.
실제 중앙 목록 40,760,377 bytes/326,316항목과 개발 PC 여유 RAM 약 13GB를 확인하고,
동일 파일에 한정한 새 bounded 절차 `read_large_archive.py`로 326,316항목을 읽었다.
source identity 일치, unsafe member name 0, 8.125초/exit 0이다.
326,204 JSON 파일 항목 등이 있다는 목록 사실이며 JSON 내용/스키마/CRC 전수 검사 결과가 아니다.

| 현재 중앙 목록 결과 | 범위 |
|---|---|
| 완료 | 437개 원본 ZIP, 내부 항목 총 1,055,977개 |
| 관측된 주요 확장자 | JSON 802,032, CSV 17,120, JPG 6, PNG 285, 내부 ZIP 161 등 |
| 끝 정보 없는 파일 | `#recycle/SmartFactory_v1.0.0_Portable1_28.zip`, 381,024,975 bytes |
| 끝 정보 없는 파일 | `#recycle/PLC 모니터링/ocr_app.zip`, 3,133,469,543 bytes |

첫 번째 끝 정보 없는 파일의 앞부분은 ZIP local-header이고 마지막 24 bytes는 0이었다.
이를 복사 실패·다운로드 중단·특정 프로그램의 손실 원인으로 단정하지 않는다.
두 파일은 삭제·복구·변조하지 않았고, 실제 내용 범위·다른 사본·복구/처리 결정을 이어서 확인한다.
끝 정보 부재 때문에 해당 파일의 중앙 목록 완료를 주장하지 않는다.

읽은 437개 중앙 목록에는 정확한 `F01_startup_and_poll1.csv` 이름 후보가 없었다.
남은 두 원본, 내부 ZIP 161개, 다른 서버 경로의 부재 증명은 아니다.
private F01의 지정 SHA256은 `bab8f61354124b5fdfa155abdb289255a2514fb710f4fa5e23a7e43418dec4b4`이며
이 해시와 다른 파일·합성 fixture로 기존 skip을 통과시킨 것처럼 대체하지 않는다.
`archive-central-reconciliation.json`에서 원래 439개와 완료 437/미완료 2를 정산했다.
`full_data_gate=NOT_EVALUATED`, 압축 내용 CRC/전체 해시 QA 미실행을 유지한다.

## 다음 실행

1. 완료한 원본/사본/구조 검사와 19파일의 33개 문제 위치를 보존하고 당시 생산자 계약·복구 가능한 다른 사본을 조사한다.
2. header 없는 두 파일·시간 순서·placeholder 의미를 해당 과거 스키마에 따라 확인한다. 실패 원문을 정정해 PASS로 대체하지 않는다.
3. 압축 내부 CSV/JSON·nested archive 및 나머지 NAS/서버 데이터 사본·관련 스키마/이미지/종료 delta를 이어서 검증한다.
4. 실제 담당자는 사용자 직접 답변 “모두 본인”으로 장비·운영 확인/QA/릴리즈 판단 모두 사용자 본인으로 확정했다.
   승인 장비 프로파일과 과거 timeout/drop의 인과·영향은 계속 연결한다.
5. 최종 clean commit의 미서명 설치본·동일 바이트 설치/복구·현장 15분/120분 QA 후 실제 승격을 확인한다.

제품 코드가 바뀌지 않은 자료 읽기/사본 단계이므로 동일 소스 health를 반복하지 않았다.
Python 분석 도우미의 parser 검사 exit 0, 압축 전체 bounded pass exit 1/추가 큰 파일 pass exit 0을 구분한다.
전체 후속 목표와 기술 QA는 미완료이며 운영본/롤백 기준은 기존 build/installer identity를 유지한다.

## 2026-10-13 외부 ZIP 전체 사본 작업 시작

앞서 목록만 확인한 외부 ZIP 439개/58,292,297,947 bytes의 기본 바이트 사본을 새로 만들기 시작했다.
개발 C의 실제 여유 81,485,045,760 bytes를 확인했으며 전체 입력 외 10GiB reserve를 요구한다.
원래 상대경로가 긴 파일은 새 사본에서 `0001.zip` 형식으로 저장하고 원래 절대/상대경로를
영수증에 결합한다. 기존 원본과 증거를 이동·삭제하지 않는다. 끝 정보가 없던 두 ZIP도 원문 그대로 포함한다.

첫 실행 `Desktop/SmartFactory/PDCA_NAS_ARCHIVE_COPY_20261013_a12f94e6`은
원래 IP UNC의 WinError 1326으로 exit 1이었다. 입력 목록만 준비했으며 실제 사본 폴더 생성 전 중단했다.
오류와 첫 소스를 보존한다. 현재 연결된 `Z:`는 `\\nas\스마트팩토리`, DNS `NAS.local`은
192.168.0.235로 확인됐고 첫 입력 3개의 크기/mtime가 원래 목록과 일치했다.
SMB connection 상세 조회는 권한 부족으로 읽지 못했으며 연결 설정이나 인증 정보를 변경하지 않았다.

두 번째 실행 루트는 `C:/Users/user/Desktop/SmartFactory/PDCA_NAS_ARCHIVE_COPY_20261013_a12f94e6_r2`다.
기존 봉인 manifest와 선택 목록 SHA256을 먼저 확인하고, 모든 439개 원본의 크기·mtime·경로 경계를
재대조한 뒤 Read 공유 핸들을 전부 열었다. `all_inputs_pinned_before_copy files=439`를 실제 확인했다.
session 42943은 사본 작성/해시 대조 진행 중이다. 각 사본의 hash 대조 후에도 모든 원본 핸들을 유지해
최종 원본 재해시와 identity를 확인해야 완료다. 6시간 처리 예산과 남은 전체 bytes+reserve를 검사한다.
cooperating SMB writer/delete open을 제한하는 방식이며 전체 NAS atomic snapshot이나 ADS 복사 증거는 아니다.
전체 사본 완료 manifest와 후속 외부 ZIP member CRC/스키마 QA는 아직 없다.

### 외부 ZIP member 내용 검사와 손상 비교본 조사

회수 완료 영수증이 나온 사본부터 내부 항목의 EOF·CRC32·길이·SHA256 검사를 시작했다.
새 증거 위치는 `C:/Users/user/Desktop/SmartFactory/PDCA_NAS_CONTENT_20261013_b44335c4`이며,
같은 source copy session 42943을 유지하면서 내용 검사 session 96822가 진행 중이다.
선택 목록 439개를 기존 봉인 manifest에 대조하고 각 닫힌 사본의 Read 공유 핸들을 유지해
전체 ZIP hash를 member 검사 전후 확인한다. 동일 SHA256 사본은 각 사본의 전체 hash를
검사한 후 같은 바이트의 member 결과를 연결한다. 중복 이름은 중앙 목록 순번으로 구분한다.
내부 이름으로 압축 해제하거나 실행하지 않으며, 실제 copy producer 프로세스 핸들을 관찰해
새 완료 영수증을 기다린다. 전체 source 최종 재해시·manifest 결합까지 끝나야 이 검사가 종결된다.

실제 실행 전 10개 fixture 검사는 exit 0이었다. 손상 CRC·끝 정보 없는 ZIP·암호화 flag·
중복 이름·경로 탈출 이름·시간 제한·Read pin 쓰기 거절을 확인했다. 20MiB 압축 해제 읽기의
tracemalloc peak는 3,235,806바이트였다. 도우미 SHA256은
`a80ffe8225dbda0e44e044eed10cd57b5a6b03716199aec3a586233108842742`다.

2026-10-13 01:26 KST의 완료 transaction은 103사본/101고유 ZIP 바이트였고, 그중 84번
`#recycle/SmartFactory_v1.0.0_Portable1_28.zip`은 기존과 같이 `BadZipFile`이다.
나머지 완료 내용의 고유 member 834,349개/60,741,023,012 압축 해제 bytes에 EOF·CRC·길이·
해시 결과를 저장했다. 이 bytes는 ZIP 원본 크기나 모든 439개의 완료 수치가 아니다.
SQLite와 실행 폴더는 진행 중이므로 봉인하지 않았다. `progress-review.json`의 SHA256은
`7d6d9962af4064b8f1c2214d1ae93c6068ae8c7b85c6ba58bc195041563371a9`다.
업무 스키마 의미·나머지 사본·원본 최종 재해시와 전체 gate는 계속 미완료다.

손상 portable과 크기가 같은 `_29.zip` 사본을 전체 비교했다. 사본 hash는 각각
`abb95576dc1473406859bc029cef6d08cb968641f750deb8e3839f1bcba3ae1a`와
`bd8c65d0e1e695464b08af178d6aad35494db53b2651df38cffb0d9597df554a`다.
앞 220,200,960바이트(210MiB)는 완전히 같고 손상 사본의 나머지 160,824,015바이트는 모두 0이다.
두 사본을 Read 공유로 유지한 전체 비교 및 전후 hash 재확인은 exit 0이었다.
정상 비교본 `_29.zip`의 618 member/763,319,519 압축 해제 bytes는 내용 검사를 통과했다.
비교본 기준 local header·압축 payload 21개가 같은 앞부분에 완전히 있고,
`SmartFactory_Portable/browsers/chromium-1200/chrome-win64/dxcompiler.dll` 한 항목이
0으로 채워진 경계를 가로지르며 나머지 596개는 그 뒤에 있다. 이는 비교본의 항목 분류다.
사라진 원본 뒷부분의 원래 의도된 바이트나 복사/저장 장애 원인을 확정하지 않으며,
손상 ZIP의 자체 중앙 목록 복구·원본 덮어쓰기·복원은 수행하지 않았다.

다른 손상 `#recycle/PLC 모니터링/ocr_app.zip`에는 같은 크기의 별도
`#recycle/ocr_app.zip`이 있었다. 후자의 사본 SHA256
`e223112d78ad6d4a6821deaeaf0ee37b3576cf5cfaaa58ed6fb74e5098ea9e7f`에 대해
17,304 member/6,503,187,147 압축 해제 bytes의 내용 검사를 통과했다.
손상 원본은 기존 Z 연결에서 Read 공유로 앞/뒤 각 65,557바이트만 읽었다. 앞부분은 정상
사본과 같고, 손상 원본의 끝 표본은 모두 0이며 정상 사본의 끝에는 EOCD가 있다.
원본의 크기/mtime/identity를 전후 대조했지만 전체 파일의 동일성·복구 가능성을 증명한 것은 아니다.
431번의 전체 사본 전달 후 이어서 비교한다. 원본과 실패 자료는 그대로 보존했다.

### 완료 사본 내 CSV 구조 검사와 실제 형식 분류

01:39 KST에 완료된 외부 ZIP 125개 시점의 CSV member 5,909개를 고정 선택했다.
고유 CSV 바이트는 5,856종류, 합계 25,414,397바이트다. 대표 ZIP 사본 9개의 Read 공유 핸들을
유지해 전후 전체 hash를 검사하고, 선택한 각 member를 EOF까지 읽어 CRC·길이·SHA256을 다시 확인했다.
UTF-8/BOM 및 UTF-16 BOM의 strict 쉼표 CSV 구조 검사 10개 fixture는 exit 0이며,
실제 검사 session 55702는 10.516초/exit 1이었다. 첫 record 뒤 461,672개 record 중 빈 record는
5,843개다. 빈 행·header·센서 값의 업무 의미를 승인했다고 해석하지 않는다.

일반 검사 결과 5개 항목을 실제 바이트와 경로로 재분류했다. 원래 exit 1과 원문은 보존한다.

- `PLC 모니터링/Documents.zip`의 `250516052348_압출기.csv`는 총 5,744바이트 중 마지막
  108바이트가 NUL이다(offset 5,636~5,743, 실제 104번째 줄). SHA256은
  `e67efda402e46b577154808405a28527715eabdef8ca4a144087d1ef94006106`이다.
  발생 원인·손실 영향·복구/처리 결정은 미확인이다. 원문을 보정하지 않았으며 현행 후보 결함으로 추정하지 않는다.
- 묶인 `matplotlib/mpl-data/sample_data/Stocks.csv`는 첫 주석을 일반 header로 해석해
  너비 오류 525건이 나왔다. 실제 주석 다음 11열 header와 524개 데이터 행의 너비가 일치한다.
  라이브러리 예제 자료이며 SFL 운영 CSV 규칙의 적용 대상으로 판정하지 않는다.
- `__MACOSX/.../._error_report_*.csv` 3개는 UTF-8 CSV가 아닌 163바이트의 별도 이진 부가 파일이다.
  각 대응 일반 CSV 항목의 존재를 확인했고, 부가 파일을 일반 CSV 손상으로 합산하지 않는다.

후속 분류 검사 exit 0은 5개 결과의 실제 형식을 확인했다는 뜻이며, 과거 NUL 문제의 해결이나
전체 업무 스키마 통과를 뜻하지 않는다. 근거는 `PDCA_NAS_CONTENT_20261013_b44335c4`의
`csv-structure-snapshot-01*` 파일들이다. 완료 CSV snapshot 이후 추가된 압축 내용은 이 범위에 포함되지 않는다.
439개 외부 ZIP 사본의 최종 원본 재해시, 나머지 member와 업무 의미 검증은 계속 진행 중이다.

### 두 번째 손상 OCR ZIP의 전체 사본 대조

02:03 KST에 431번 손상 `#recycle/PLC 모니터링/ocr_app.zip`의 완료 사본 영수증을 확인했다.
3,133,469,543바이트의 SHA256은
`3c0ab7b92370144f99c0a13313cbbec167a75f7fa76bf837c846af7ca9ddf8d0`이다.
member 감사에서도 기존과 같이 `CONTENT_ERRORS_PRESERVED`였다.

정상 비교본 13번과 두 전체 사본의 Read 공유 핸들을 유지해 전후 hash/identity를 대조했다.
session 37005는 23.125초/exit 0이다. 앞 860,880,896바이트는 완전히 같고, 손상 사본의
그 뒤 2,272,588,647바이트는 모두 0이다. 마지막 차이는 offset 3,133,469,540이다.
정상 비교본의 local header/압축 payload 15,769개는 같은 앞부분 안에 있으며,
`ocr_app/torch/lib/cublasLt64_12.dll` 한 항목이 경계를 가로지르고 1,534개 항목은 그 뒤에 있다.

이는 정상 비교본의 offset 분류이며 손상 ZIP의 자체 중앙 목록 복구나 사라진 뒷부분의
원래 의도된 바이트를 증명하지 않는다. 복사/저장 장애의 실제 발생 원인은 미확인이다.
원본·손상 사본을 변경하거나 정상 비교본으로 덮어쓰지 않았다.
근거는 같은 실행 폴더의 `ocr-full-copy-comparison.json`이다. 외부 ZIP 439개 원본의
최종 재해시/manifest 결합은 아직 진행 중이므로 이 대조를 전체 사본 완료로 보고하지 않는다.

### 439개 사본의 내용 기록과 추가 CSV 검사

02:30 KST의 SQLite 완료 transaction에는 외부 ZIP 439개/421고유 바이트의 검사 결과가 있다.
84번과 431번의 `BadZipFile`은 그대로이며, 나머지 읽을 수 있는 고유 내용의
1,036,015 member/130,458,089,604 압축 해제 바이트에 EOF·CRC·길이·SHA256 결과를 저장했다.
사본 producer 42943은 모든 439개/58,292,297,947바이트 사본을 기록한 뒤 원본의 마지막
전체 재해시를 진행 중이다. member 검사 96822도 이 최종 manifest 결합을 기다린다.
손상 ZIP의 알 수 없는 member를 검사 완료한 것으로 계산하지 않으며 아직 실행 폴더를 봉인하지 않았다.

OCR 전체 비교 결과 JSON SHA256은
`1c87eb50cd2aed576b4395807b06b14f557a46c1f02b2de4d5dfbba18049263a`다.

이 시점의 읽을 수 있는 ZIP 전체에서 알려진 CSV member는 17,046개다. 앞선 5,909개 선택과
겹치지 않는 11,137개/28,074,554,570바이트를 `csv-structure-delta-selection.json`으로 고정했다.
최대 개별 파일이 553,374,342바이트여서 새 `stream-csv-structure.py`는 전체 파일을 메모리에
올리지 않고 첫 읽기에서 strict decode/NUL·EOF·SHA256, 다음 읽기에서 CSV 구조를 검사한다.
decode/CSV 오류가 있어도 첫 binary 읽기는 끝까지 진행해 내용 해시와 CRC 확인을 유지한다.

기존 파서와의 결과 대조 18개(증분 decoder 오류 메시지의 위치 표현 제외), 시간 제한 시험은
exit 0이었다. 20,971,524바이트/5,242,880행 fixture의 tracemalloc peak는 2,098,025바이트다.
이 결과를 임의로 거대한 단일 CSV record까지 메모리가 일정하다는 주장으로 확대하지 않는다.
도우미 SHA256은 `e50d2b5e1a51160ca1f26d9ac01335caebf79c9bfadb743d113755c9b235aee3`다.

실제 추가 검사는 session 38762 / PID 20968로 02:28:20 KST에 시작했다. 대표 ZIP의 전체
hash를 전후 확인하고 각 선택 member의 실제 길이·SHA256을 기존 내용 기록에 다시 대조한다.
진행 중의 구조 finding은 그대로 기록한다. 종료 결과·전체 정산 전에 CSV 통과로 보고하지 않는다.
이 검사는 업무 스키마 의미, 손상 ZIP의 누락 범위 또는 과거 데이터 문제의 처리 결정을 대신하지 않는다.

### 추가 CSV 종료와 149개 finding 분류

session 38762는 02:34:56 KST에 397.187초/exit 1로 끝났다. 11,137개/28,074,554,570바이트,
첫 record 뒤 73,403,870개 record를 검사했다. 빈 record는 9,898개, NUL은 0개다.
대표 ZIP 110개의 전체 hash를 전후 확인했고, 모든 선택 member를 원래 EOF·CRC·길이·SHA256과
정산했다. 선택/결과/도우미 해시와 member 수를 별도로 재검산했다(exit 0).

149개 일반 검사 finding은 실제 바이트를 다음과 같이 분류했다. 원래 exit 1과 모든 결과를 보존한다.

| 분류 | member | 확인 내용·남은 조건 |
|---|---:|---|
| 이벤트 CSV의 UTF-8 BOM만 존재 | 78 | 모두 3바이트 `efbbbf`의 동일 바이트. 이벤트가 실제로 없었는지, 내보내기가 완전했는지는 미확인 |
| 과거 Rect 자료의 header/본문 열 수 차이 | 70 | `#recycle/PLC 모니터링/2호기/abs.zip` 69개와 `abs_1.zip` 1개. header 9열, 본문 4열. 총 249,252개 너비 차이. 원인·업무 계약·처리 결정 미확인 |
| matplotlib Stocks 예제 주석 | 1 | 첫 주석을 header로 해석한 525건. 실제 다음 11열 header와 524행은 너비 일치 |

마지막 미분류였던 `abs_1.zip`의 `2024-05-27-3.csv`는 9,878,412바이트,
SHA256 `5c505fb6031f4d4ac0d1f5e04317ae5e61f97ce4a5efb9776da6dfc7f93e8897`이다.
전체 member/ZIP hash를 다시 확인하고 238,250개 본문 record가 모두 4열임을 확인했다(exit 0).
샘플 일부만 보고 전체 행을 추정하지 않았다. 원문이나 사본을 수정하지 않았다.

최종 summary SHA256은 `6950955cdf923af86f6debc4126cbce1f1ba25613f13e3d7227b4167fc06636f`,
선택 목록은 `b3af316498aa39b7b5b62f64e2bf0cd31b18578e48a0c9f60b51e60f08fe7f1b`,
결과 JSONL은 `04f3c5244971ea12e0f078bce8b40cfc1ed42f1f8880d978269e134e5877c1dc`다.
이전 5,909개와 합친 알려진 CSV 범위는 17,046개이며, 읽을 수 없는 ZIP 2개의 내부 범위는 여전히 미상이다.
현재 NAS 원본의 최종 재해시·업무 의미·전체 gate는 별도 미완료다.

## 2026-10-13 03:47 KST 외부 ZIP 사본·내용 검사 종료

위 최종 재해시 대기는 실제 종료 결과로 갱신한다. 사본 producer session 42943은
11,337.956초/exit 0으로 끝났으며 439개/58,292,297,947바이트의 원본 최종 재해시와 identity 일치를
기록했다. 콘솔 `MANIFEST_SHA256`과 `archive-copy-manifest.json`의 실제 SHA256은
`45608d8bc30983f2b3e8082c2bb64c0f80aec2e2f9f8d4ba7c8b35a03265ff2c`로 일치한다.

내용 검사 session 96822도 9,079.594초/exit 1로 종료했다. 437개는 읽을 수 있는 member의
EOF·CRC·길이·SHA256 검사를 마쳤고, 84번 portable/431번 OCR의 BadZipFile 두 건을 그대로 보존했다.
421개 고유 archive 내용에서 member 1,036,015개(파일 1,031,166·디렉터리 4,849),
130,458,089,604바이트가 기록됐다. 손상 ZIP의 알 수 없는 내부 항목은 이 수에 포함하지 않는다.

`review-terminal-binding.py`는 실제 두 종료 코드, producer 콘솔 해시, 선택 목록·도우미 해시,
439개 파일 영수증과 SQLite의 모든 archive 영수증, member/내용 집계, 두 손상본 식별을 대조했다(exit 0).
SQLite SHA256은 `505b1c3a15c7ed6bfee00f58e986940b60a052c3e08192a6e01ce42d7356ed0a`다.
후속 review의 성공은 원래 내용 검사 exit 1을 바꾸지 않는다. 원래 summary의
`copy_producer_console_hash_binding_verified=false`도 보존하고 후속 결합을 별도 기록했다.

완료 결합 기록만 `PDCA_NAS_CONTENT_20261013_b44335c4/terminal-binding`에 봉인했고,
manifest SHA256은 `9f0d4e0634606c07e1d5b0ba8b475a91f384c256cc37dfa0f6bfbd279ad6286b`다.
`Z:/SmartFactory/20261013/records/PDCA_NAS_ARCHIVE_CONTENT_terminal_b44335c4`의 10파일 기본 바이트와
대조했다. 58GB archive 사본이나 918MB SQLite 전체를 공유로 전송한 것은 아니다.
전체 NAS snapshot 원자성·ADS·업무 스키마 의미·손상 원인/복구·전체 출시 gate는 계속 미완료다.

## 2026-10-15 후속: 전체 온도 사본의 문자열·시각 유형 분류

서버 RI29 실행 결과 대기와 독립적으로 기존 온도 사본 1,471개 전체를 읽었다.
`profile-temperature-observations-r1.py`는 697.031초/exit 0으로 끝났으며
576,684,549행을 정산했다. 기존 manifest와 각 사본의 검사 전후 SHA256·파일 identity가
일치했다. 기존 구조 오류 33행과 다른 형식인 10열 XLS 134행은 새 6열 분석에서 제외하고
별도 수량으로 남겼다. 576,684,382개의 정상 너비 6필드 행에 대한 원문 분류다.
이 exit 0은 관측 집계 완료이며 기존 구조 검사 exit 1과 역사 의미 미확인을 바꾸지 않는다.

| 범위 | 숫자가 아닌 온도 문자열 `-` | 인접 기록의 시각 감소 |
| --- | ---: | ---: |
| bracket header 1,033파일 | 135,679,595 | 79,391,860 |
| 소문자 header 435파일 | 38,941,875 | 42,889,300 |
| header 없는 2파일의 위치 기반 관찰 | 235,023 | 300,525 |
| 합계 | 174,856,493 | 122,581,685 |

앞선 감사의 선언된 온도 열 비숫자 174,621,470건은 전부 `-`였다. header 없는 파일은
추가로 위치만 관찰했으며 승인된 스키마로 확정하지 않았다. 다른 비숫자·빈 문자열·
비유한 수는 이번 6열 범위에서 없었다. 숫자 401,827,889건도 센서 유효성 PASS를 의미하지 않는다.
소문자 header의 날짜 `YYYY-MM-DDT00:00:00.000Z`는 날짜 표지와 별도 시각 열을 결합해
비교했다. 실제 UTC/현지 시각·취득 시간으로 변환한 것이 아니다. 이 추가 범위 때문에
시각 감소 합계가 이전보다 커졌으며, 종전 bracket 범위 79,391,860건은 정확히 재현됐다.

TemperatureFast 열이 정확히 `-`인지 그 밖의 문자열인지만 구분한 감소 유형은 다음과 같다.

| 이전 행 → 현재 행의 고속 열 문자열 | 감소 수 |
| --- | ---: |
| `-` → 그 밖의 문자열 | 120,608,820 |
| 그 밖의 문자열 → 그 밖의 문자열 | 1,972,541 |
| 그 밖의 문자열 → `-` | 289 |
| `-` → `-` | 35 |

감소 중 장비 이름이 달라진 것은 3건뿐이었다. 이름은 원문 그대로 비교했으며 `Spot`과
`SPOT`를 같은 물리 장비로 임의 통합하지 않았다. 고속 열이 `-`인 행만 별도 순회했을 때도
시각 감소 331건이 남았다. 따라서 모든 감소를 서로 다른 장비의 혼합이나 하나의 정상
기록 방식으로 종결하지 않는다. 이전 [SPOTViewer 구현·반복 기록 조사](production-release-risk-validation-profile-search-20261013.report.md)의
일부 원인 후보를 전체 행에 소급 적용하거나 모든 `-`를 물리 무효 측정으로 세지 않는다.

독립 검산은 기존 감사와 파일별 행 수·기존 범위의 감소 수·온도 분류 합계를 대조했다.
원래 봉인 1,688파일 중 온도 1,471개는 이번 전후 해시로, 나머지 217개는 별도 재해시로
확인했으며 모두 기존 목록과 같았다. `review-profile.py` exit 0이다. 표본 raw/정리 파일의
`-` 개수 1,723,996/3,448,022는 별도 `rg` 집계에서도 각각 exit 0으로 일치했다.
한 정리 파일 31,433행은 별도 정수 시각 비교로 7,626개 감소 및 그중 양쪽 고속 열이 `-`인
7개를 재확인했다(exit 0). 예를 들어 데이터 행 2,175→2,176은 같은 날짜의
16:02:13.221→10:46:04.864다. 원인·정리 경로는 미확정이며 원문을 정렬/치환하지 않았다.
표본 설명 초안의 잘못된 `same-second` 표현만 R2에서 정정했고 최초 결과도 보존했다.

최종 분석 근거는
[별도 실행 폴더](C:/Users/user/Desktop/SmartFactory/PDCA_TEMP_PROFILE_20261015_c75d1a8e/README.md)에 있다.
요약 SHA256은 `eed8d21ac8c133bc424501fa6c7ea6e95a69fc1559cf28cf869e51b0e82a0e36`,
파일별 결과 SHA256은 `6897ccf9c683b958a3f8751efac1c0be43a1e1e4c9847e8a5f207ac95a9fc276`다.
초기 스크립트·probe·전체 출력은 경로 실수로 종전 작업 루트에 새로 추가됐다. 기존 봉인 바이트와
목록은 보존됐으며, 이번 소형 산출물만 별도 실행 폴더로 복사하고 `review.json`에 양쪽 경로와
해시를 기록했다. 종전 목록 밖의 추가 파일을 기존 봉인에 포함된 것으로 주장하지 않는다.
감사/검산/예외 추출 Python의 Ruff E9/F821/F401 검사도 exit 0이다.

다음 검토 순서는 원문 유형별 역사 생성·시계·센서 의미와 영향 확인, USER_SELF의 과거 실패
처리 결정, 현재 후보의 별도 데이터/성능/정상 종료 QA다. 구조 오류 33행·원인 미확정 항목을
해결 처리하지 않았고 `full_data_gate=NOT_EVALUATED`, 출시/승격 HOLD를 유지한다.


## 2026-10-17 후속 — Rect CSV 70개 형식 재현과 값 검토

보존 ZIP `abs.zip`의 69개와 `abs_1.zip`의 1개, 총 70 CSV의 249,252행을 전수 재확인했다.
9열 제목과 4열 본문이 일치하지 않는다. 같은 ZIP의 비교 파일 1개 43,749행을 포함한
총 71파일 293,001행을 검사했고, 9열 비교 파일도 Rect_4~8은 전 행 빈 문자열이었다.
누락된 제목 칸을 0으로 채우거나 실제 값 5개가 유실됐다고 해석하지 않았다.

clean 보존 소스 `OCR-raspberry/OCR-raspberry.py`의 commit은
`da2f129263a771946a7b2c1389dee1f6dfbd6a4c`(2024-05-23 10:52:32 +09:00)다.
Git blob과 현재 파일 바이트가 일치하며 SHA256은
`75978c25e2c3ab0168abb1dc0f74ea30cea366c4ab887fc1167a962b2affe0e9`다.
353행은 항상 Date와 Rect_1~8을 제목으로 기록하고, 370행은 실제 영역 수+1만큼 본문을 만든다.
387~392행은 OCR 결과에서 영문자·숫자·마침표를 허용하며, 361행은 현재 길이 그대로 저장한다.

해당 구문만 추출해 메모리 안에서 실행했다. GUI·카메라·OCR·원본 파일 쓰기는 실행하지 않았다.
3개 영역은 4열, 8개 영역은 9열을 만들며, 기존 값·시각을 입력하면 71파일 전체의
제목·본문·개행 바이트가 동일하게 재현된다. 이것은 저장 형식의 기전 재현이다.
일부 CSV가 commit 시각보다 이르고 당시 배포/실행 기록도 없어 실제 생산자 실행을 확정하지 않는다.
원본 화면의 OCR 정답, 영역 설정, 각 Rect의 물리량·단위도 미확정이다.

| 범위 | 파일 | 행 | 숫자가 아닌 비어 있지 않은 값이 있는 행 | 앞 3값 중 빈 값이 있는 행 |
|---|---:|---:|---:|---:|
| 4열 본문 | 70 | 249,252 | 6,093 | 1,807 |
| 9열 비교 본문 | 1 | 43,749 | 480 | 0 |
| 합계 | 71 | 293,001 | 6,573 | 1,807 |

마지막 두 열의 행 집합은 배타적이지 않을 수 있어 더하지 않는다. 비수치 비어 있지 않은 셀은
Rect_1 6,349 / Rect_2 456 / Rect_3 2,171, 총 8,976개다. `Z.1`, `C.` 등도 포함된다.
빈 문자열은 앞 3열 각각 21/1,782/42개다. 숫자 문법 통과가 실제 계기값 정확성을 뜻하지 않는다.
모든 파일의 NUL, 파일 내 시각 역전, 인접 동일 시각은 0개다. 실제 시계와 파일 사이 연속성은 별도다.

member CRC·크기·SHA256은 종전 구조 검사 71개와 일치했고 입력 파일 전후 해시도 일치했다.
`0435.zip`과 `0436.zip`이 분석 대상이며, `새 폴더.zip`인 `0437.zip`은 0435와 같은 바이트로
다시 확인했다. 이를 별도 고유 자료나 정상 복구본으로 집계하지 않았다. 외부 추가 사본 없음이라는
사용자 답변을 유지한다. 원본 수정·복구·새 전체 백업·서버 호출·제품 코드 변경은 0건이다.

`inspect_rect_r2.py`(5가지 실제 구문 fixture 포함) 7.269초/exit 0,
`review_rect.py` 3.617초/exit 0(1,011 비교), 최종 3개 Python helper Ruff E9/F exit 0이다.
독립 검산은 CSV/AST 생산자 구현을 쓰지 않고 CRLF 줄·쉼표 분할로 전수 대조했다.
R1은 같은 해시의 중복 ZIP을 경로로 구분하지 못해 member 검사 전 exit 1로 중단됐고 보존했다.
R2는 고유 사본 경로와 해시를 함께 확인한다. 제품 변경이 없어 전체 health/build와 기존 현장
15/120분 시험·설치는 반복하지 않았다.

처리 기준: 원본을 보존하고, 영역의 물리적 의미·단위·OCR 정확성을 확인하기 전에는 검증된
수치 추세나 품질 판정에 편입하지 않는다. 헤더·값을 자동 수정하지 않는다.
분류는 `CODE_REPRODUCED_HISTORICAL_DEPLOYMENT_UNCONFIRMED`이며 데이터 PASS가 아니다.
78개 BOM-only CSV와 손상 ZIP 2개 내부 미상 범위, 다른 손상/원인 미확정 자료는 남아 있다.
전체 R4와 R1/R2·R3 물리·R5 drop15·R6 최종 QA는 미완료, 목표 active/이번 단계 PROGRESS/출시 HOLD다.

확인 예: `result-r2/records.json`의 archive/member_index → column_kinds/nonnumeric_tokens →
`source-excerpts.json`/`replay-fixtures.json` → `independent-review.json` 순서로 확인한다.
근거: [상세 검토](C:/Users/user/Desktop/SmartFactory/R4RECT_20261017_c8e4a210/review.md).
전체 결과 SHA256: `c058cee9214245a563c3186769d9b234c08e11d85e192a2cff5b68f809834368`.
독립 검산 SHA256: `649ed892bdd508f5897a5e8ad8b5d497952c24c312fffcf634abe13147ddab03`.
closeout SHA256: `53eec466e307333470698d090406f23a80f7a9c614c230ec099910ca15f33b8c`.


## 2026-10-17 후속 — BOM-only 78개 출처와 손상 ZIP 자체의 온전한 앞부분

78개 BOM-only CSV를 60개 ZIP의 원본 member 바이트와 같은 묶음의 실행 메타데이터로 대조했다.
모두 UTF-8 BOM EF BB BF 3바이트이며, raw Windows 시스템 이벤트 32개와 redacted 46개다.
30개 실제 run_id에 연결됐고 온도·PLC 측정 파일로 분류하지 않는다. 중복 보관 member 수를 실행 수로
세지 않는다. 연결된 메타데이터 사본 상태는 COLLECTED 3/FAILED 10/PARTIAL 65이며, 이는 시스템
이벤트 조회의 성공 상태가 아니다. 개별 조회 성공/실패 기록은 모든 관련 메타데이터에서 찾지 못했다.

실행별 collection_script_sha256 13종을 전부 보존 소스와 연결했다. 12종은 Git blob/CRLF와,
1종은 보존 현장 도구 ZIP member와 일치했다. 13종 모두 Get-WinEvent의 오류를 SilentlyContinue로
처리한 뒤 Export-Csv -Encoding utf8로 저장한다. 조회 오류를 별도 기록하는 변수가 해당 구문에 없다.
Windows PowerShell 5.1에서 빈 입력(오류0)과 존재하지 않는 로그 조회(오류1)를 시험했으며,
둘 다 raw/redacted 각각 동일한 3바이트 BOM을 만들었다(exit 0). 과거 실제 조회를 재실행한 것은 아니다.
과거 파일의 분류는 DIAGNOSTIC_SYSTEM_EVENT_EXPORT_WITH_NO_RECORDS, 빈 원인은 UNDETERMINED다.
이벤트가 없었다거나 측정 데이터가 유실됐다고 확정하지 않는다. 향후 현행 수집기에 조회 범위·성공
상태·오류 ID/유형·건수를 구분하는 증거를 추가하되, 기존 해시가 고정된 도우미와 결과는 보존한다.

손상 ZIP 2개는 자체 local header부터 순서대로 해석하고 완전한 payload를 EOF·CRC·크기·SHA로
검증했다. 정상 대조본의 이전 검증 member 원장과도 모두 일치했다. 파일로 추출하거나 복구하지 않았다.

| 손상 사본 | 온전한 항목 | 파일 수 | 검증한 압축 해제 바이트 | 부분만 남은 다음 항목 |
|---|---:|---:|---:|---|
|0084.zip Portable|21|19|371,052,442|dxcompiler.dll|
|0431.zip OCR|15,769|14,779|2,074,149,335|cublasLt64_12.dll|
|합계|15,790|14,798|2,445,201,777|2개|

Portable은 offset220,200,960부터160,824,015바이트, OCR은 offset860,880,896부터
2,272,588,647바이트가 모두0임을 재확인했다. 자체 중앙 디렉터리와 원래 뒷부분은 미복구다.
정상 대조 ZIP의618/17,304항목을 사라진 원래 뒷부분의 확정 목록으로 사용하지 않는다.
원래 tail 내용과0채움 발생 원인은 미확정이며, 대조본 존재를 원본 덮어쓰기 승인으로 사용하지 않는다.

온전한 앞부분의 CSV3개는 matplotlib 예제다. data_x_x2_x3.csv는 제목 없는 공백 구분11행·3열이며
x/x²/x³관계를 확인했다. msft.csv는7열·65행, Stocks.csv는 출처 주석 다음11열 제목·524행이다.
독립 검산의 첫 파일 header/body_rows는 일반 쉼표 파서의 미리보기였으며,
library-sample-contracts.json의 실제 공백 구분 형식을 최종 판단으로 쓴다. 금융값의 외부 사실검증은
하지 않았다. 함께 있는 프로그램/라이브러리 PNG25·JPEG2는 Pillow verify·전체 load를 통과했다.
이 결과를 공장 측정 스키마나 ZIP 미확인 뒷부분의 통과 근거로 사용하지 않는다.

BOM 검사R2, 실제 PowerShell 재현, ZIP 앞부분 검사R2와6개 payload fixture, 독립48,193개 비교,
예제형식 확인, Python5개 명시 Ruff E9/F는 모두 실제exit0이다. BOM R1의 ZIP루트 경로 처리,
ZIP R1의 이름 구분자 정규화 오류, Git 소스1종 미발견은 실패 기록을 보존하고 해결했다.
최초 디렉터리 지정 Ruff는 파일을 찾지 못해 검사로 세지 않고 명시적5파일 검사를 수행했다.
원본 변경·새 전체 백업·복구파일 작성·서버 호출·제품 코드 변경은0건이다. 제품 코드가 같아
전체health/build와 기존 현장15/120분 검사·설치는 반복하지 않았다.

확인 예: bom-records.json의 member/run_id → collector-source-map.json → powershell-export-result.json.
ZIP은 badzip-prefix-summary.json의 경계 → badzip-prefix-records.json의 자체 header와SHA → independent-review.json.
근거: [상세 검토](C:/Users/user/Desktop/SmartFactory/R4ARC_20261017_94c9d2af/review.md).
BOM 결과 SHA256: `cc4964f3e14dc12988e22e38010828999b1f34b5c6fa59de1cf404d47a6b62d6`.
ZIP 결과 SHA256: `ea3692df8f7a508584a5b55faa6f3be0f58a45604c048c630cc4b1f0436d29a4`.
독립 검산 SHA256: `5ea98d7d65139b3bdf382acfce5d3e3482ab7197c67cbead1062069d0f88cb33`.
closeout SHA256: `43f3fa816ce2b74a32a2273eb016cdb0656d2842554b2d496785a8461d0e9818`.

전체 R4의 다른 손상·의미 미확정 자료, R1/R2 성능원인·200ms기준, R3물리, R5drop15, R6최종QA는
계속 미완료다. 목표active/이번단계PROGRESS/full_data_gate NOT_EVALUATED/출시HOLD를 유지한다.
실행 중 진단이나 사용자 입력 대기는 없다. 다음에는 현행 비고정 진단 수집기의 이벤트 조회 결과
기록을 보완하고, 과거 증거의 미확정 범위는 최종 영향·처리 원장에 남긴다.
