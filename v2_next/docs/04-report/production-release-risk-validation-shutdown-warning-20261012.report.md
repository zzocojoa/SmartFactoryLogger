# 2026-10-12 과거 종료 실행 연결과 이미지 종료 경고 정정

후속 PDCA는 미서명 내부 운영 정책으로 Do 진행 중이며 전체 R1~R6는 HOLD다.
이 단계는 과거 실패 실행을 식별하고 실제 코드의 반환 조건에 맞게 개발 소스의 경고 문구를 정정했다.
운영 설치본·실제 서버 설정·실패/drop 카운터·종료 gate·롤백 기준은 변경하지 않았다.

## 실행 식별과 확인 범위

새 증거는 진행 중인 자료 작업 루트 `C:/Users/user/Desktop/SmartFactory/PDCA_DATA_20261012_ed3ad6e0`에 있다.
NAS의 기존 `SmartFactory/20261008/return/SUI_APPLY_READ_R2`에서 닫힌 metadata를 Read 공유로 잠가 복사했다.
복사 전후 source identity가 같고 26,384 bytes, SHA256
`a76df6fa69a3890e89ced2883eef9ddbaeb2ea9dab10fb2016c4524d8a7baea3`다.
이는 당시 회수 사본의 읽기이며 새 서버 실시간 metadata 조회로 표시하지 않는다.

metadata의 build `d7a1b20f96711fb07fc7add0867e79ee36506fce`, logger `925017a5-61ec-4177-b44c-8c2be666d1f3`,
시작 `2026-10-07T18:24:21.285073Z`를 확인했다. 10월8일 11:58:15 KST system.log의
pid 12156/시작 03:24:21 KST와 같은 실행 시간선이며 CSV closeout의 동일 logger를 연결했다.
closeout은 shutdown/finalized true, final sequence 149843이다. CSV closeout 성공을 이미지·전체 종료 성공으로 확대하지 않는다.

기존 실제 `sample-3.json`의 11:40:58.521 KST 기록도 같은 logger다.
이미지 queue_size 0, enqueued 27705, written 27689, failure_count 16, dropped_count 0이었다.
시작 metadata의 image failure/written/dropped 0은 시작 snapshot이며 그 실행의 종료 실패가 0이었다는 근거가 아니다.
해당 실행은 R5의 `4c97d4a…` drop15 및 현행 `541d701…` drop44와 별개다.
다른 d7 실행의 카운터도 build 이름만 같다는 이유로 합산하지 않는다.

## 확인된 코드 조건과 최소 정정

실제 d7 Git 원본의 `stop_spot_image_capture_for_shutdown`은
`stop_spot_image_capture_writer`의 반환값과 `failure_count_after == 0`을 함께 요구한다.
writer stop은 unfinished_tasks와 worker 생존을 확인하지만, 최종 함수는 저장 실패가 기록됐으면 false가 될 수 있다.
따라서 기존 “queue did not drain” 경고는 false의 이유를 실제 큐 잔여로 제한해 표현할 수 없다.
실제 종료 시점의 queued/unfinished/inflight/worker 상태와 16건의 저장 실패 원인은 계속 `UNCONFIRMED`다.

현재 `backend/app.py`의 control/lifespan 경고 두 곳을
“SPOT image capture shutdown did not complete cleanly”로 정정했다.
control에는 pending writes와 recorded write failures를 검토하도록 안내한다.
반환값·시간 제한·카운터·정상 종료 실패·최종 manifest 억제·증거 보존 조건은 동일하다.
이 경고 정정은 과거 저장 실패/drop의 원인 해결 또는 큐 잔여 없음의 증명이 아니다.

## 검증 상태

- 첫 직접 focused 실행: 248건, 실패 3/오류 8, exit 1. 로그를 보존했다.
  이 실행은 repository runner의 APPDATA/SFL_CONFIG_PATH 격리를 적용하지 않았고 모듈 순서도 후속 실행과 달랐다.
  환경·모듈 순서의 영향은 한 조건씩 비교한 원인 확정 결과가 아니다.
- 별도 APPDATA/SFL_CONFIG_PATH로 격리한 focused 실행: `test_spot_api`, `test_image_shutdown_evidence`,
  `test_shutdown_closeout_regression` 248건, 70.206초/exit 0. 실제 전체 출력에서 OK를 확인했다.
  기존 불완전 종료·실패 보존·최종 manifest 억제 검사를 유지했다.
- `python -m ruff check backend/app.py`: exit 0.
- 최종 전체 `npm run health`: session 55910 종료 코드 0. 전체 UTF-8 로그 194,120 bytes/3,474행을
  읽어 backend 915건(914통과/private F01 skip1), frontend Vitest 42파일/434건,
  Electron 94건·의존성 14건·frontend Node 9건, ruff/mypy 9파일 및 QA selftest 6개 통과를 확인했다.
  원시 출력은 `health-after-warning.log`, 정산은 `health-final-summary.json`이다.

이 변경은 경고 문구만 정정하므로 문구를 그대로 복제하는 새 테스트는 추가하지 않았다.
같은 온도 사본 작업 session 79262는 exit 0으로 완료됐다. 온도 구조 검사 session 20569는
19파일/33행 너비 불일치로 exit 1이며 해당 원본/사본을 보존했다. 구조 검사와 전체 데이터 QA를 구분한다.
현재 서버/이미지/압축 내부 전수 QA와 최종 미서명 설치본의 현장 QA는 아직 미완료다.
