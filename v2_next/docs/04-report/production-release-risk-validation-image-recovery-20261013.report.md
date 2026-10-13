# 2026-10-13 재시작 후 오류와 과거 이미지 복구 후보 조사

현재 상태는 **Do 진행, R1~R6 정식 출시 HOLD**다. 미서명 내부 운영 정책을 유지한다.
이번 단계는 공개 읽기 API 관찰, 보존 사본의 해시 조인, 선택 NAS 이미지 사본/디코딩이다.
운영 앱·장비 설정·설치본·롤백 기준을 변경하지 않았다.

## 서버 수집과 작업 정보

03:58 KST API에서 기존 build `541d701d544eea6a8a4e4836047077eaf9cfaf30`의
logger `e9a785c0-46a2-45d2-bf7a-4187cce08771`이 Running/REAL이며,
CSV 누적 8,237행·이미지 writer 1,329장·writer 실패/drop 0이었다.

초기 작업 정보는 `60332 / 6`이었다. 이후 화면과 `/api/facility/operator-metadata`, `/api/data`에서
`2026-10-13 03:58:41.239800 KST`에 `60192 / 17`, `source=operator_input`로 바뀐 것을 확인했다.
Codex는 작업 정보를 입력·적용하지 않았다. API가 변경한 사람의 신원까지 입증하는 것은 아니다.
변경 후에도 같은 logger 세대에서 Running, CSV 8,806행을 확인했다.

증거 루트는 `C:/Users/user/Desktop/SmartFactory/PDCA_SERVER_LIVE_20261013_c087a31d`다.
`observation`과 `job-transition`의 API 원문·시간/경로/해시 영수증,
`server-status.jpg`와 실제 운영 commit 소스를 함께 보존했다.
18파일(목록 포함)을 `Z:/SmartFactory/20261013/records/PDCA_SERVER_LIVE_c087a31d`에 복사해
모든 바이트를 대조했다. evidence manifest SHA256은
`317ea0bf3e4dc97f780cedcac9a079b7bcb4273cfa94dcd357afba123fea6916`이다.

## 영상 오류 큐와 전체 전송 실패의 구분

03:58 표본에서 오류 큐의 영상 6건은 모두 `/api/spot/live_image.jpg`의
`SpotTransportConnectTimeout`/502다. 각 correlation ID가 보존된 transport failure event와 일치한다.
추가 3건의 발생 시각은 03:41:28, 03:43:15, 03:46:18 KST이며 요청 시간은 2,015/2,016/2,015ms다.

| 같은 표본의 전송 실패 카운터 | 건수 |
|---|---:|
| 이미지 | 6 |
| 온도 | 5 |
| 내부 온도 | 1 |
| 진단 | 1 |
| 전체 | 13 |

correlation ID가 있는 failure event는 영상 6+진단 1로 7건이다.
실제 운영 소스의 `_record_request_event_locked`는 유효한 correlation ID가 없으면 event를 생략하고,
온도 요청 경로는 해당 ID를 설정하지 않는다. 따라서 오류 큐 6건 또는 event 7건을 전체 전송 실패 수로
사용하지 않는다. 온도/내부 온도 6건의 구체적인 예외는 이 표본에서 확인하지 못했다.
pool exhaustion·reuse violation·bind collision은 0이었지만, 이 사실이 네트워크·장비 원인 확정이나
일반 timeout 해결을 증명하지 않는다. 화면이 Running으로 돌아와도 과거 실패를 지우지 않는다.

## 과거 이미지 참조와 보존 바이트 대조

최종 분석은 `C:/Users/user/Desktop/SmartFactory/PDCA_IMAGE_RECONCILE_20261013_716ce2f4/results-r2/summary.json`이다.
닫힌 fact index, cold manifest, NAS 내용 SQLite와 최종 결합 manifest 네 입력의 전후 SHA256을 확인했다.

| 대조 결과 | 수량 |
|---|---:|
| 닫힌 image fact 행 | 4,143,509 |
| 현재 capture 경로·크기·해시 일치 | 312,969 |
| 현재 capture 경로에 없음 | 3,830,540 |
| 선택 NAS archive의 일반 member | 1,031,166 |
| archive 고유 크기/SHA256 조합 | 559,369 |
| 없는 참조와 archive 내용 해시 일치 | 0 |
| 없는 참조와 다른 cold 사본 파일 해시 일치 | 0 |

없어진 참조의 촬영 시각은 2026-07-01 14:27:56.229137~2026-10-05 10:39:26.658452 UTC다.
모두 진단용 7일 촬영 경계보다 오래됐다. 그러나 운영 cleanup은 촬영 시각이 아닌 **파일 mtime**을
사용한다. 사라진 원본의 mtime·개별 삭제 영수증이 없어 retention 삭제라고 확정하지 않는다.

오래된 mtime인데 남아 있는 4,222파일은 현재 cleanup의 직접 `YYYY/MM/DD` 구조 밖이다.
정확한 그룹은 `server_csv_link_20260701-233304` 1,304개,
`server_csv_link_20260702-000130` 1,416개, `server_csv_link_20260703-112058` 228개,
`server_link_positive_20260703-114627` 1,274개다.
봉인 README의 `server_csv_link_*` 표기는 이 네 그룹을 충분히 표현하지 못한다. 위 목록과 원본
`old_mtime_path_scope_groups`를 정확한 구분으로 사용하며 봉인 바이트를 다시 쓰지 않았다.

최초 분석은 archive 성공 상태를 잘못된 접두어로 비교해 미검증 목록에 439개를 넣었다.
수정 분석은 정확한 성공 문자열을 사용하고 기존 손상 ZIP이 84·431번 두 개임을 확인했다.
최초 소스/결과를 보존했다. 이미지 내용 해시 대조 결과는 동일하다. 두 실행 모두 실제 exit 0이며,
최초 exit 0만으로 그 분류 오류가 없었다고 주장하지 않는다.

15파일(목록 포함)을 `Z:/SmartFactory/20261013/records/PDCA_IMAGE_RECONCILE_716ce2f4`에 복사해
모두 대조했다. manifest SHA256은
`b50979cef5bb622f6624fd9b334061629a6787067376c60ee54db68fb553c46d`다.
손상 ZIP 내부·nested 압축의 추가 내용·NAS loose 파일 바이트는 위 해시 조인 범위 밖이다.

## NAS loose 이미지 사본과 디코딩 — 최종 확인

기존 전체 NAS metadata manifest와 entries 해시를 확인한 뒤 이미지 확장자 기준으로
20,157파일/449,350,328바이트를 선택했다. PNG 125, JPG 19,975, ICO 37, GIF 20개다.
SPOT 이름 후보 19,888개 중 Thumbs.db 2개를 제외한 19,886개가 이미지 선택에 포함된다.
과거 목록 시점의 선택 범위이며 이후 추가된 NAS 파일을 포함한 현재 전수 목록은 아니다.

작업 루트는 `C:/Users/user/Desktop/SmartFactory/PDCA_NAS_IMAGES_20261013_671b3c82`다.
도우미는 원본 읽기 핸들·부모 경로 보호, 개별 원본 즉시 재해시, 새 ZIP,
모든 프레임 load/verify, 닫힌 ZIP 전 member의 EOF/CRC/길이/SHA256,
모든 선택 원본의 마지막 해시·메타데이터·identity 재검사를 수행한다.
기본 데이터 스트림 범위이며 NAS 전체 원자적 snapshot·ADS 보존을 주장하지 않는다.

다중 프레임·손상 이미지·truncation 허용 거부·경로 이탈·최종 사본/원본 대조·중도 원본 변경 탐지
6개 로컬 시험이 exit 0이었다. 도우미 SHA256은
`e0bb27b9a8f57b617c217cfff2fc1be7e609100a41b569eb44941fdb816f4b16`이다.
04:07:26 KST, session 70742 / Python PID 10528로 시작했고 부모 경로 154개를 보호했다.

04:24:10 KST 실제 exit **1**로 끝났다. 선택한 20,157파일의 사본 무결성, 모든 ZIP member의
EOF/CRC/크기/SHA256, 모든 선택 원본의 최종 해시·메타데이터·identity 재검사가 완료됐다.
이미지 디코딩은 PASS 20,154, FAIL 3이며 고유 내용 18,082개에 모든 프레임 load/verify를 수행했다.
동일 크기·SHA256 파일에는 같은 디코딩 결과를 연결했다.

세 FAIL은 아래 **0바이트** recycle 파일이다. 현재 SPOT 저장 실패로 분류하지 않는다.

- `#recycle/화면 캡처 2024-10-30 092830.png`
- `#recycle/image.jpg`
- `#recycle/Merged_Data_생산일자/필터 데이터/NG 자료/20240830(제작시점 불명확)-소재 (2).png`

ZIP SHA256은 `624d5b8730fb640ec14e484844fc65e3db7c422566726c982bcac26621e73cf3`,
전체 파일 journal SHA256은 `c3189e9f0ff5457d7d0c3c4adb1857a0c50508990226c48d1538cbef51d7fef7`다.
실제 exit 1을 PASS로 바꾸지 않는다. 선택 사본 무결성 완료와 디코딩 finding을 구분한다.

## 누락 참조 7건의 격리 복구 후보

위 ZIP과 journal, 기존 cold manifest, 닫힌 fact index의 전후 해시를 확인하고 4,143,509행을 조인했다.
현재 경로에 없는 3,830,540건 중 **7건**은 선택 NAS 사본에 동일한 크기·SHA256 바이트가 있고
디코딩도 통과했다. 동일 capture 경로는 0건, 동일 파일명은 3건이다.
촬영일 UTC 기준 9월 8일 2건, 9일 1건, 10일 1건, 11일 2건, 12일 1건이다.

이번 선택 NAS loose 이미지에서 동일 바이트를 찾지 못한 참조는 **3,830,533건**이다.
다른 백업에 없다는 증명으로 확장하지 않는다. 앞 절의 archive/cold 일치 0건과도 범위가 다르다.
`missing-reference-join/recoverable-missing-references.jsonl`의 SHA256은
`d4539590a27c03d60ed31d0b1afcb866ae5414943e2eaa43bc7bbe6c412df637`이다.

7개 파일을 같은 증거 루트의 `recovery-candidates/fact-row-<행번호>.jpg`에 별도로 보존했다.
저장소 이미지 검증기로 각 사본의 크기·SHA256·디코딩을 독립 재검사해 모두 PASS였다.
조인과 독립 검사는 각각 실제 exit 0이다. 운영 원본 경로를 복원하거나 덮어쓰지 않았다.
기존 누락·retention·drop 원인은 여전히 미확정이다.

## 서버 cold 이미지 ZIP 회수와 검사

서버의 `C:/Users/user/Desktop/SmartFactory/Qa0596a/c/r0/logs/test_data/spot_images`를
Windows 기본 압축 UI에서 ZIP/Store로 별도 묶었다. 서버 최종 ZIP은
`C:/Users/user/Desktop/SmartFactory/SFL_IMAGE_EXPORT_43ef972a/spot_images_Qa0596a.zip`이다.
기존 cold 원본을 바꾸지 않았다. 서버 화면에서 파일 존재와 복사 완료를 확인했으며,
공유 반환 경로는 `Z:/SmartFactory/20261013/return/PDCA_SERVER_IMAGE_ZIP_Qa0596a_43ef972a`다.

central directory는 312,985파일 + 26디렉터리, 파일 내용 총 3,053,203,168바이트다.
ZIP 컨테이너는 3,143,631,386바이트다. 이는 아직 개별 member 무결성이나 디코딩 통과를 뜻하지 않는다.
개발 증거 루트 `C:/Users/user/Desktop/SmartFactory/PDCA_SERVER_IMAGES_20261013_43ef972a`에서
도우미 오류 탐지 시험 6개 exit 0 후 session 88251로 읽기 잠금 수신·개별 대조·디코딩 검사를 시작했다.
서버 콘솔에 결합된 cold manifest SHA256은
`30b5967d88f102cd0618b191f99fdcd21c69fc59740b862d022ffcf0d02c85bf`다.
ZIP 컨테이너 해시는 개발 PC에서 계산하는 값이며 서버 콘솔에서 확인한 컨테이너 해시라고 주장하지 않는다.
ZIP은 기본 데이터 스트림 범위이고 기존 NTFS 원본의 추가 스트림 보존 증거를 대체하지 않는다.

## 다음 확인 순서

1. 기존 PLC session 78990의 최종 원본 재해시·목록·실제 종료를 확인한다.
2. 이미지 복구 후보와 미참조 파일의 과거 오류 로그 연결을 확인한다.
3. 서버 cold 사본의 미참조 16파일의 원인·복구 가능성 대조를 이어간다.
4. timeout 원인·장비 설정·최종 후보 패키지/현장 QA를 각각 완료한다.

이번 단계에 제품 소스·의존성 변경이 없어 기존 동일 소스 health/build를 반복하지 않았다.
NAS producer는 디코딩 finding으로 exit 1, 읽기 조인·독립 후보 검사·각 도우미 6개 시험은 exit 0이다.
서버 ZIP 검사는 아래 최종 결과처럼 exit 0이다. full_data_gate=NOT_EVALUATED, formal_release_gate=HOLD를 유지한다.


## 서버 이미지 검사 최종 결과와 NAS 봉인

서버 ZIP 회수·검사 session 88251은 실제 exit 0으로 끝났다.
312,985파일 / 3,053,203,168바이트와 26디렉터리가 서버 콘솔에 결합된 cold manifest와 일치했다.
모든 member의 경로·EOF/CRC·크기·SHA256, 로컬/공유 ZIP의 최종 해시가 일치했고
이미지 312,985개가 완전 디코딩 PASS였다. 고유 내용 디코딩 수는 312,719개다.
ZIP SHA256은 `6d7afa90a2b72b51401246f8e69fc5c2b64ac118d8e9329c83892ff0186ce9a2`이다. 기본 데이터 스트림의 검증 결과다.

미참조 16파일도 모두 정상 디코딩되며 별도 `isolated-orphan-images`에 보존했다.
fact 3,985,223행(23:12:37.796712 UTC)과 다음 3,985,224행(23:12:56.673370 UTC) 사이
18.876658초 간격에 모인다. 양쪽 service는 `25a1065a-5758-42d2-9789-65c6d4659be4`로 같다.
같은 바이트가 다른 fact에 연결된 행은 0건이다.
기존 d7 과거 표본의 SPOT service도 같고 저장 실패 카운터가 16이다. 마지막 저장 오류는
`2026-10-07T23:12:55.344067+00:00`로 마지막 미참조 이미지 촬영 뒤
0.065043초다. 표본 SHA256은
`65f5da533cff0ab17156d249d6df0df3f4e47551cccab94e77293ddabcb7575a`이며 원문 사본을 함께 보존했다.
세대·수량·마지막 시각의 연관은 확인됐지만 당시 예외 원인과 16개 각각의 오류 event 대응은 미확정이다.
원본 fact를 생성·수정하지 않았다.

NAS 이미지 묶음은 `Z:\SmartFactory\20261013\records\PDCA_NAS_IMAGES_671b3c82`에 38파일(목록 포함)을 복사하고
공유 사본과 최종 원본 바이트를 모두 대조했다. manifest SHA256은
`4822a9ed4c3772f920cdca8a641c32714d74a3eaba93542f1d6c99a05599c942`이다. 재생성 가능한 `__pycache__`는 명시적으로 제외했다.
NAS producer의 디코딩 finding exit 1과 후속 사본/조인/후보 확인 exit 0을 구분한다.

ZIP 최종 검사 후 18%에서 일시정지돼 있던 파일별 전송을 취소했다.
서버 cold 원본과 부분 반환 폴더는 삭제하지 않았다. `transfer-finished-receipt.json`과
`server-transfer-finished.jpg`에 대체 경로와 화면을 기록했다.

최종 문서 확인기의 첫 실행은 CSV 검증기 해시를 이미지 검증기 경로에 잘못 연결해 exit 1이었다.
원본 확인기와 실패 기록을 보존하고 r2에서 봉인된 빌드 `source-identities.json`을 직접 읽도록 고쳤다.
제품 파일은 변경하지 않았다. r2는 문서 4개·상대 링크 20개·상태 JSON과 기존 검증된 소스 6개의
동일 해시를 확인해 exit 0이었다. `git diff --check`도 exit 0이며 기존 줄바꿈 경고만 있다.


## 2026-10-13 서버 로그 회수와 저장 실패 기록 보완

서버 cold `Qa0596a/c/r0/logs`에서 system 43파일과 stdout/stderr 2파일을
탐색기로 새 공유 반환 폴더에 복사하고 개발 PC로 회수했다. 총 45파일 / 135,798,398바이트의
기본 스트림이 서버 콘솔 결합 cold manifest와 크기·SHA256 일치한다. 최종 대조 exit 0이다.
자료: `C:/Users/user/Desktop/SmartFactory/PDCA_SERVER_SYSTEM_20261013_5f3d891a`.
공유 원문: `Z:/SmartFactory/20261013/return/PDCA_SERVER_SYSTEM_Qa0596a_5f3d891a`.
실행 중인 운영 원본을 변경하지 않았고 NTFS 추가 스트림 검사로 확대하지 않는다.

stderr 928,102줄의 writer 경고는 43건이다. 선행 시작 PID별 1/1/12/13/16건이며
PID 12156의 마지막 16건은 910248–910263행이다. 기존 Oct8 기록도 같은 16건을
이미 확인했다. 그 기록 5개를 당시 COPY_RECEIPT 해시와 대조해 별도 사본으로 보존했다.
이번 새 근거는 cold 바이트 재확인과 16개 미참조 이미지의 세대·수량·시각 연결이다.
경고 각각의 시각·예외·capture ID는 없어 실제 원인은 여전히 미확정이다.
Oct8 reader는 10:06 KST에 시작했고 마지막 오류는 08:12 KST이므로 그 reader를
선행 오류의 원인으로 지정하지 않는다. 다른 실행 구간의 27건도 합치지 않는다.
system 로그 6개는 JSON 231,886줄과 비JSON 48줄을 포함한다. 해당 분의 JSON 12줄은
접근 INFO이며 이미지 writer 상세 오류가 아니다. 비JSON 줄은 원문 그대로 보존했다.

현재 `spot_api.py`의 경고도 기본 stderr에서 `extra.error_type`이 보이지 않는 결함을
확인했다. 경고 본문 JSON에 실패 시각, capture 시각/ID/SHA256/크기, service ID,
실패 누계, writer 초기화/저장 단계, 예외 종류와 숫자 errno/winerror를 추가했다.
URL·경로·원본 예외 문자열·이미지 본문은 기록하지 않는다. 잘못된 capture 시각은
null로 남기고 후속 큐 처리를 계속한다. 저장/retention/fact 복원 정책과 실패 누계는 유지한다.

실제 fact append 실패로 고립 이미지를 만든 뒤 다음 이미지가 저장되는 회귀에서
수정 전 exit 1, 수정 후 exit 0을 확인했다. 잘못된 시각의 초기화 실패도 수정 전 exit 1,
수정 후 성공이다. 기존 종료/큐 원자성 검사를 포함한 관련 시험 5개 exit 0이다.
최종 `npm run health`는 실제 exit 0(340.1초): 의존성 15,
Electron 94, frontend Node 9·Vitest 42파일/434, type/lint, ruff, mypy 9파일,
backend 920개(919통과·private fixture 1생략), QA selftest를 확인했다.
검사 전후 소스 8개의 해시가 같으며 이번 두 변경 파일의 전후 바이트·diff를 보존했다.
이 백엔드 로그 변경에 frontend build를 반복하지 않았고 새 설치본/현장 QA는 아직이다.

증거 대조 도우미의 초기 3회는 해시 기입 오류 2회와 읽기 경로 고정 누락 1회로 exit 1이었다.
해당 도우미·부분 결과·실패 영수증을 보존한 뒤 r4가 전체 대조 exit 0을 확인했다.
이는 자료 손상 발견이 아니며 제품 회귀의 실패 재현 결과와 구분한다.
PLC 최신 관측은 `original_source_final_recheck` 96000파일이며
실제 종료·최종 전체 목록 대조 완료를 아직 주장하지 않는다.
서버 설치·승격·롤백 기준 갱신 없이 R1–R6 HOLD, full_data_gate=NOT_EVALUATED다.

최종 기록 묶음 120파일(목록 포함)을 `Z:\SmartFactory\20261013\records\PDCA_SERVER_SYSTEM_5f3d891a_r2`에 복사하고
공유 사본·최종 로컬 원본 해시를 확인했다(exit 0). manifest SHA256:
`abc3d7fcdb8135794fb62ea5d5c826f0d323561660d89dadc95915aea108fd92`. 첫 봉인 도우미는 Windows 경로와 문자열의 정렬 순서 차이로
목록 비교 exit 1이었고, 부분 사본을 보존한 뒤 r2에서 같은 정렬 기준으로 전체 대조했다.
최종 문서 확인기의 첫 UTF-8 디코딩은 Windows 혼합 인코딩 출력 때문에 exit 1이었다.
원본 로그를 보존하고 비UTF-8 바이트를 가역 이스케이프로 읽은 확인기는 문서 3개·상대 링크 20개,
소스 8개 해시·전체 로그 3,330/150줄·실패 JSON 55개를 검사해 exit 0이었다.
시각 오류 회귀는 새 진단 코드가 잘못된 시각 때문에 큐를 중단하지 않도록 검증한 것이며
과거 서버 장애의 원인 재현이라는 뜻이 아니다. 2026-10-12T20:21:56.823704+00:00의 PLC 최종 원본 대조는
105000파일까지 진행됐고 Python PID 37268은 같은 시작시각으로 실행 중이다.
