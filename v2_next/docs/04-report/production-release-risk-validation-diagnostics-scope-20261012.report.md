# 2026-10-12 서버 원본 진단 회수와 NAS 전체 범위 탐색

전체 목표는 Do 진행 중이며 R1~R6 정식 출시 HOLD를 유지한다.
이번 단계는 서버의 실제 로그를 회수하고, 기존 NAS 15분 탐색의 한계를 보존한 채 범위 확인을 이어갔다.
운영 앱 종료·설치·복구·장비 설정 변경·서명 workflow 실행·운영/롤백 기준 갱신은 수행하지 않았다.

## 실제 서버 진단 회수

증거 루트는 `C:/Users/user/Desktop/SmartFactory/PDCA_DEEP_20261012_96aced6e`다.
원본은 서버 `C:/Users/user/AppData/Roaming/SmartFactoryLogger/logs`의 stdout/stderr,
`system` 하위 43개 파일 및 `test_data`의 진단 이벤트/회전 로그/실패 journal 6개다.
`test_data`는 현재 운영 logpath이며 이름만으로 시험 데이터로 제외하지 않았다.
일반 탐색기에서 선택 범위를 확인한 뒤 `Z:/SmartFactory/20261012/return/DIAG_96aced6e`로 복사하고,
개발 PC `server-diagnostics`에 회수했다. 공유 사본·개발 PC SHA256 대조는 root/system 45개와 events 6개 각각 exit 0이다.
최초 events 복사 준비는 이미 있는 빈 폴더를 `New-Item`으로 생성하려다 exit 1로 중단됐다.
빈 기존 목적지를 확인한 후 실제 복사/해시 대조를 진행했다. 서버 원본이나 기존 결과를 덮어쓰지 않았다.

앱 실행 중의 순차 진단 사본이다. 원본 전후 해시·전체 atomic snapshot·회전 사이의 무누락을 주장하지 않는다.
서버 C$ 직접 접근은 해당 경로를 찾지 못해 exit 1로 끝났다. 자격 증명·ACL·방화벽을 변경하지 않고
허용된 탐색기 복사로 회수했다. 이 실패를 모든 SMB/원격 경로의 부재로 일반화하지 않는다.

## 확인된 현상과 인과 한계

`analyze_diagnostics.py`는 events 6개의 모든 JSONL 14,990행을 파싱했고 구문 오류 0,
분석 전후 각 사본 SHA256 일치, exit 0이다. 실패 journal 752행은 별도 기록이므로
회전 events의 실패와 합산한 고유 요청/손실 건수로 사용하지 않는다.

| 실패 journal 관측 | 행 | 판정 범위 |
|---|---:|---|
| `signalpc`의 `parse_error` | 746 | 10월 9일~12일 세 journal instance의 기록. 원시 응답/센서 지원 의미 미확인 |
| `timeout` | 6 | 모두 10월 12일 현재 journal, `timeout_phase=connect`, `ConnectTimeout`/`SpotTransportConnectTimeout`, 1,000~1,016ms |

회전 events는 2026-10-12 13:32:06.538~15:14:30.326 KST 범위다.
실패 journal은 2026-10-09 17:49:46.257~2026-10-12 14:56:34.301 KST다.
장비 `/output` 진단 요청의 connect timeout이며, 과거 로컬 `/api/spot/config`의 5초 수집 timeout과
동일 사건/원인으로 취급하지 않는다. 진단 값 해석 실패를 이미지 drop 원인으로 귀속하지 않는다.

system.log와 회전 1~5에서 JSON 객체 230,184행을 읽었다. 다른 형식 48행도 오류 위치를 보존했다.
첫 확인은 `[WARNING] [Config] [MelsecRead] ... status=OK` 형식의 텍스트 행이었다.
혼합 형식을 JSON 손상으로 단정하거나 해당 파일의 모든 행이 JSON이라고 보고하지 않는다.
읽은 JSON 행에는 `/api/spot/config`·`/api/config` 요청 기록이 없었다.
이는 요청이 발생하지 않았다는 증명이 아니며 원래 설정 조회 timeout의 서버 인과는 `UNCONFIRMED`다.
실제 운영 build `541d701d544eea6a8a4e4836047077eaf9cfaf30`의 Git 원본 `app.py`를 읽어
두 경로가 `_QUIET_ACCESS_PATHS`에 있고, 요청 시작 및 상태 코드 400 미만 완료 로그를 생략함을 확인했다.
따라서 클라이언트 timeout 뒤 서버가 200으로 완료된 경우 이 access log에서 요청별 시간을 복원할 수 없다.
해당 build 파일 바이트는 `operating-541d-app.py`로 보존했다. 현재 코드와 과거 배포 코드를 혼동하지 않았다.

실제 `system.log.1` 17,255~17,269행에서 2026-10-08 11:58:15 KST,
pid 12156/시작 03:24:21 KST 실행의 `spot_image_capture` 정상 종료 단계가
`success=False`, 83.2ms였고 큐 미정산 경고와 최종 fact manifest 생략을 확인했다.
10월 9일 20:55:37의 pid 9036 및 10월 10일 08:01:27의 pid 17348은 해당 단계가 각각
`success=True`, 79.6/76.9ms다. 이 단일 단계 성공은 전체 종료·데이터 gate PASS가 아니다.
stdout의 launcher session과 backend session은 식별자가 다르므로 같은 문자열로 조인하지 않았다.
각 과거 build·drop15·현재 drop44·저장 실패와의 연결은 아직 미확인이다.

원본/분석은 `diagnostic-analysis.json`, `historical-config-request-log-extraction.json`,
`diagnostic-events-copy-hashes.json` 및 원본 파일에 보존했다.

## NAS 첫 전체 탐색의 한계와 후속 절차

개발 PC가 기존 고정 scope의 원래 UNC 주소를 직접 읽었다. 서버 native NAS 실행을 대신하지 않는다.
잠금 helper SHA256 `4d66fb164bfbb375d976af524203af9f5ba53818665713990001f376833d351a`로
900초 탐색한 결과는 일반 파일 298,342개·디렉터리 2,775개·301,119행,
apparent 179,367,160,865 bytes, 900.2012215초다. `#recycle`도 조사 범위에 포함했다.
시간 제한으로 `PARTIAL_TIME_BUDGET`이며, 240자 경로 예산 초과 2건을 기록했다.

이 개인 실행 harness는 탐색 이후 manifest 작성 때 자신의 열린 redirect 로그를 glob에 포함해
공유 위반으로 exit 1이었다. 수집 결과와 실패 로그를 보존하고 종료된 세 파일의 명시적 목록/해시를
`nas-collection-recovery.json`에 새로 기록했다. 같은 탐색을 완료/PASS로 바꾸지 않았다.
회복 기록 시점에는 재탐색하지 않았다.

제한을 해결하기 위해 별도 개발 PC용 `read_nas_scandir.py`로 NAS 메타데이터 범위를 다시 탐색했다.
내용을 읽거나 원본을 변경하지 않고 링크/reparse를 따라가지 않는다. 하위 디렉터리 완료/오류와
미완료 stack을 기록하고 결과는 NAS 바깥의 새 `nas-scandir`에만 쓴다.
서버 PS5.1의 경로/실행 검증으로 간주하지 않는다.
실행 전 읽기 전용 로컬 oracle 6개/9,365,894 bytes/오류 0/미완료 0을 확인했고 exit 0이다.
실제 NAS 탐색은 657.359초, CLI exit 0으로 완료됐다.
파일 1,029,146개·하위 디렉터리 2,869개(원래 root까지 완료 기록 2,870개),
1,032,015행·200,089,154,934 bytes다. 탐색 오류·reparse·시간 제한 초과·미완료 stack은 모두 0이다.
메타데이터 단계에는 파일 내용 해시를 계산하지 않았다.
별도 검사에서 전 행 JSON·대소문자 정규화 고유 경로·파일/행 수·크기 합계를 대조했고,
entries/directories/pending/summary 네 파일의 manifest SHA256/크기를 모두 재검증했다. 검사 exit 0이다.
manifest SHA256은 `41090ab6dfd6856ddd03ede480227c78c6c4d8e659ec3aa52b510823e124daf2`다.
240자를 넘는 두 경로도 개발 PC Python에서는 메타데이터를 읽었다. 서버 PS5.1 지원을 주장하지 않는다.

| NAS 최상위 관측 | 파일 | apparent bytes |
|---|---:|---:|
| `#recycle` | 850,438 | 144,006,578,331 |
| 출구부 온도 | 1,471 | 27,534,639,606 |
| SmartFactory | 46,497 | 22,393,439,624 |
| 통합 데이터 (2025.12.~2026.02) | 1,510 | 1,875,355,591 |
| 병합 데이터 | 113 | 1,507,727,318 |
| PLC 모니터링 | 127,159 | 1,007,073,087 |

이 표 외 나머지 항목도 원본 summary에 포함했다. recycle·배포/회수 사본을 포함한 물리 목록이며
같은 바이트를 제거한 고유 운영 데이터 용량이 아니다. 이름만으로 원본/중복/삭제 대상을 확정하지 않는다.
확장자 기준 CSV 157,139개, JPG 19,975개, PNG 125개, ZIP 439개가 있다.
내부 archive는 아직 펼쳐 검사하지 않았다. 전체 목록에서 F01 파일/패키지 이름 후보는 없었으나
archive 내부나 다른 서버 경로까지 fixture 부재로 일반화하지 않는다.

2026-10-12 15:24 KST 개발 C 여유 공간은 89,943,838,720 bytes,
NAS 공유 여유는 2,131,630,125,056 bytes였다. 전체 물리 NAS 사본은 C에 들어가지 않는다.
저장 공간 확보를 위해 원본/증거를 삭제하지 않았고, 고정된 원본 후보 목록과 새 NAS 사본 목적지를
분리하는 전체 사본/일관성 절차가 필요하다. 재귀 원본 안의 사본을 새 원본으로 다시 복사하지 않는다.
전체 내용 사본·CSV 의미·이미지 decode/역참조·일관성 검증은 미완료다.

## 재개 순서

1. NAS 범위의 최종 완료/오류·중복/원본 후보와 보관 공간을 정산하고 전체 일관된 사본 절차를 결정한다.
2. 과거 timeout·drop의 실제 build/session 연결과 이미지/CSV/metadata/종료 영수증 전수 검증을 수행한다.
3. 이미 요청한 서버 native NAS 실행 및 승인 코드서명 인증서/담당자 답변을 반영한다.
4. 최종 clean 소스·서명 설치본 및 동일 바이트 설치/복구/현장 15분·120분 시험을 완료한 뒤 실제 승격을 확인한다.

유지보수는 언제든 가능하다는 사용자 지시를 유지하며 다시 승인 요청하지 않는다.
전체 `full_data_gate=NOT_EVALUATED`, 원본 timeout/drop 인과 미확인, 승인 전체 장비 프로파일/실제 담당자 미확인,
서명 설치본·현장 QA 미완료다. 이번 단계에는 제품 코드 수정이 없어 이미 통과한 동일 소스 health를 반복하지 않았다.
