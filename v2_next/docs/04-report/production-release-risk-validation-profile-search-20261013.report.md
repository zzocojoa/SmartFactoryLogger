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
