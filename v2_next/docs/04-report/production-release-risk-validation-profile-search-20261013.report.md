# 서버 승인 자료 탐색과 제조사 DB 검사

2026-10-13. 승인 프로파일의 근거를 찾기 위해 기존 서버 목록과 제조사 자료 폴더를
확인했다. 추가로 발견한 SpotViewer DB의 사본 무결성과 전체 행 집계는 확인했으나
정확한 물리 모델·승인 프로파일은 확정하지 못했다. **R3 및 정식 출시 HOLD**를 유지한다.

## 탐색 범위와 발견

기존 서버 metadata 목록 `PDCA_INV_RUN_20261012_bacadba4/server-result/files.jsonl`의
411,798행을 승인/교정/구매 관련 파일명 정규식으로 검색했다. 목록 SHA256은
`e0cdb803979e0075ad0eed966e1d13dd12f4f7fa739f6443a76eb481fdabf68b`이며 일치 파일명은 0개다.
이는 정규식과 당시 목록에 한정된 결과이며, 파일 내용이나 서버 전체의 부재 증명이 아니다.

Chrome 원격 데스크톱의 Explorer에서 확인한 범위:

- 사용자 Documents 직계: EasyTune, WindowsPowerShell, Default 원격 연결 파일.
- 바탕화면 SpotViewerV520 직계: SpotViewerSetup 설치 파일. 실행하지 않았다.
- `C:/Documents/SpotViewer`: `LandData.db` 발견. 속성 화면의 수정 시각은
  2024-11-21 20:41:43 KST, 크기는 874,827,776바이트였다.

새 DB 경로는 이전 목록의 재귀 수집 대상 밖이었다. 기존 서버 CSV/이미지 cold 사본과
동일 snapshot으로 취급하지 않는다. 일반 Explorer 복사로
`Z:/SmartFactory/20261013/return/PDCA_SPOTVIEWER_bcf53e17/LandData.db`에 회수했다.
초기 단축키 복사는 동작하지 않아 빈 목적지를 확인한 뒤 Explorer 복사/붙여넣기 버튼으로
완료했다. 원본이나 기존 파일을 삭제·교체하지 않았다.

## DB 사본의 실제 검사

개발 PC 사본을 `mode=ro&immutable=1`, `PRAGMA query_only=ON`으로 열었다.
공유 사본의 복사 전/후와 개발 사본의 분석 전/후 SHA256이 같았다.

`95ca1fe92d85c1636027bb8109bf80bb3efdfd2be871319e95962f4db6e04c42`

**서버 원본 해시는 미측정**이다. 원본 DB가 실행 중이었는지와 복사의 원자성은
Explorer 시각·크기만으로 증명하지 않는다. SQLite 구조 검사는 확보한 사본에만 적용한다.

| 검사 | 결과 |
| --- | --- |
| SQLite integrity_check | ok |
| DataTag 전체 | 17,966,329행 |
| Temperature | 5,494,857행; NULL 1,689,070행; non-NULL 값 200.0–782.5 |
| TemperatureFast | 12,471,472행; NULL 0행; 값 199.0–787.5 |
| Frame / Recording / Settings / SystemInfo | 각각 0행 |
| DeviceName | SPOT 한 종류 |

태그별·DataContext별·저장 타입별 집계 합계가 전체 행 수와 일치했다.
DateTime은 정수지만 epoch와 시간대 계약은 확인하지 않았다. DataContext 의미,
NULL과 199.0의 원인, 센서 정확도·연속성·보존 누락은 미검증이다.
NULL 1,689,070행을 손상이나 수집 실패 건수로 판정하지 않는다.
설정과 시스템 정보 테이블이 비어 있어 모델·승인 설정의 근거는 얻지 못했다.

## 화면 이름과 실제 모델의 구분

전날 보존한 장비 정보 화면은 상단 `AL Spot`, 본문 `App1: AL E / 200–900°C`를
보여준다. 제조사의 [SPOT Web Simulator](https://www.ametek-land.com/simulator)는
화면의 이름을 사용자가 지정하는 장비/측정 위치 명칭으로 설명한다.
[SPOT User Guide 813452 Issue 2](https://www.ametek-land.com/-/media/ameteklandinstruments/documentation/products/fixedspotnoncontactthermometers/spot/ametek_land_813452_new_spot_pyrometer_user_guide_issue_2_en.pdf?la=en&revision=f811e381-7f32-4d05-9108-8025abee963f)의
검색 반환문도 3.3절 항목 2 Name을 같은 의미로 설명했다.
따라서 `AL Spot`만으로 정확한 모델을 확정할 수 없다.

위 설명은 검색 도구가 반환한 공식 출처의 색인 본문을 확인한 범위다. 후속 원문/그림
요청은 제조사 점검 화면을 반환했고 직접 HTTP 다운로드도 HTML 7,291바이트였다.
PDF 실물 수신·그림 대조는 완료하지 못했다. 저장한 HTML을 PDF로 취급하지 않는다.
화면 위치와 Name 항목의 정확한 대응은 이 조회로 확정하지 않았다.
소프트웨어 metadata의 SPOT+ AL 기본 문자열도 실제 모델 readback을 대신하지 않는다.

## 판정과 다음 단계

담당자 USER_SELF, 언제든 유지보수 가능, 미서명 운영, 실제 모델 미정이라는 기존
답변을 유지한다. 새 승인 자료를 찾지 못했다는 이유로 동일 질문을 반복하지 않는다.
확인할 다음 증거는 다음과 같다.

1. 장비 라벨/구매·교정 기록과 승인된 실제 프로파일의 연결.
2. 물리 LowSignal 경계 comparator 및 최종 build/fingerprint/운영자 확인.
3. 새 역사 DB 범위의 데이터 의미·보존/처리 판단. 기존 이미지 drop 사건과 합산하지 않는다.
4. 적용 전 조건 충족 후 동일 1.0.28 후보의 현장 QA·정상 시작3회·15/120분·종료 delta.

이 DB 검사로 전체 데이터 gate를 통과시키지 않는다. 현재 운영본541d와 후보4cc7393e,
각 설치본 SHA 및 롤백 기준은 유지한다. 서버 앱·장비 설정·작업 정보의 적용 변경,
설치·재시작·승격을 수행하지 않았다.

## 검증 기록

`read_db.py`, `review_db.py` actual exit0; 두 도우미 Ruff F/E9 exit0.
근거는 [실행 기록](C:/Users/user/Desktop/SmartFactory/PDCA_PROFILE_SEARCH_20261013_bcf53e17/README.md),
[DB 집계](C:/Users/user/Desktop/SmartFactory/PDCA_PROFILE_SEARCH_20261013_bcf53e17/database-review.json),
[사본 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_PROFILE_SEARCH_20261013_bcf53e17/database-copy-receipt.json)에 있다.
제품·빌드 설정 변경이 없어 완료된 health/NSIS/성능 시험은 반복하지 않았다.

선택한 닫힌 조사 기록16파일(manifest 포함), 증거117,416바이트를
`Z:/SmartFactory/20261013/records/PDCA_PROFILE_SEARCH_bcf53e17`에 보존했다.
manifest SHA256은 `ba3fae36f46ed3c04c9e2100b87b4b22d1437d3d2b59daa4a74dd77534a54f78`다.
대형 DB는 앞서 검증한 return 폴더에 보존하고 manifest의 외부 데이터 항목에
경로·크기·해시를 기록했다. 작업 폴더 전체 봉인이나 서버 원본 해시 검증을 뜻하지 않는다.
공유 보존·최종 문서/PDCA 정합성 검산 및 `git diff --check`는 exit0으로 확인했다.

## 후속: NULL 온도와 고속 온도 기록의 관계

이 절은 위 역사 DB의 의미를 추가 조사한 결과다. 장비 모델과 관찰 프로파일 승인은 이후
[장비 직접 조회·승인 기록](production-release-risk-validation-device-profile-20261013.report.md)으로
보완됐으며, 앞부분의 모델·승인 미정은 최초 탐색 시점의 기록이다.

같은 개발 사본의 17,966,329행을 읽기 전용으로 순회했다. 분석 전후 SHA256은 위의
`95ca1fe9…`와 같았다. SQL 교차 집계에서 `Temperature=NULL` 1,689,070행은 모두
`DataContext=0`이고, 나머지 Temperature 3,805,787행과 TemperatureFast 12,471,472행은
모두 `DataContext=1`이었다. 이는 저장된 값의 관계이며 enum의 의미를 확정한 것은 아니다.

`DataTagId` 순서의 Temperature 한 행부터 다음 Temperature 직전까지의 TemperatureFast를
한 저장 구간으로 묶었다. **행 인접성만 비교했으며 같은 취득 시점·원자적 측정으로 간주하지 않는다.**

| Temperature가 NULL인 구간 | 구간 수 | NULL 전체 대비 |
| --- | ---: | ---: |
| 뒤따르는 고속 값이 모두 199.0 | 1,633,135 | 96.69% |
| 199.0과 다른 고속 숫자가 섞임 | 39,418 | 2.33% |
| 뒤따르는 고속 값에 199.0이 없음 | 16,517 | 0.98% |
| 합계 | 1,689,070 | 100.00% |

반대로 Temperature가 숫자인데 뒤따르는 고속 값이 모두 199.0인 구간도 4,613개다.
따라서 NULL 1,689,070행을 모두 199.0과 같은 의미로 판정하거나, 인접 고속 값으로
채워 넣을 근거는 없다. NULL 쪽 예외 55,935구간과 반대쪽 4,613구간을 합친
60,548구간의 행ID·원시 시각·값 범위를 별도 CSV에 보존했다.
예: 행98529의 Temperature는 NULL이나 뒤따르는 두 고속 값은 343.1과 445.5다.

Temperature 태그 순서의 연속 NULL 구간은 49,558개이고, 가장 긴 구간은 179,455행이다.
실제 경과 시간의 단위·epoch·시간대 및 공정 상태 계약을 확인하지 못했으므로 이를
정지 시간이나 통신 장애 횟수로 해석하지 않는다. 행ID 연속성도 취득 데이터의 무누락을 증명하지 않는다.
Temperature 태그 안에서 원시 DateTime이 앞선 값보다 감소한 지점4개도 별도 SQL로 확인했다.
해당 행ID는 7023557, 7559151, 7974596, 10982315이며 시계 보정·저장 순서 등 원인은 미확정이다.

[제조사 SPOTPro 안내서 812953 Issue3](https://ameteklandinstrumentscn.cdn.ametekweb.com/-/media/ameteklandinstruments/documentation/products/software/spotpro/ametek_land_812953_spotpro_user_guide_issue-3_en.pdf?la=zh-cn&revision=29448605-2d36-48ac-9767-6714ea97a8b5)의
6-2쪽 색인 표는 현재 온도와 장비 속도의 고속 온도 스트림을 구분한다. 다른 소프트웨어의
이 설명은 이번 SpotViewer DB의 NULL·199.0·DataContext 계약을 증명하지 않는다.
SpotViewer 안내서 후속 검색의 점검 HTML 응답도 문서 안에 설명이 없다는 증거로 사용하지 않았다.

[전체 분석](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_NULL_20261013_c1b03095/null-analysis.json),
[예외 구간 목록](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_NULL_20261013_c1b03095/contradictory-or-unpaired-blocks.csv),
[연속 NULL 구간](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_NULL_20261013_c1b03095/null-runs.csv),
[문서 근거와 한계](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_NULL_20261013_c1b03095/source-review.json)를 보존했다.
전체 집계 정산과 별도 SQL로 재조회한 6분류 표본72개가 일치했고 분석 actual exit0이다.
[독립 검산](C:/Users/user/Desktop/SmartFactory/PDCA_SPOTVIEWER_NULL_20261013_c1b03095/analysis-review.json)에서
CSV 60,548구간·연속 NULL 49,558구간/1,689,070행과 원시 시각 감소4지점을 대조해 exit0을 확인했다.
원본 DB·서버·후보 코드는 변경하지 않았다. 다음 확인 대상은 실제 기록 소프트웨어의 버전과
NULL/199.0/DataContext 변환 계약, 예외 구간의 취득 관계다. R4 원인·영향·처리 및
서버 원본 해시/사본 원자성은 미완료이며 `full_data_gate=NOT_EVALUATED`를 유지한다.
