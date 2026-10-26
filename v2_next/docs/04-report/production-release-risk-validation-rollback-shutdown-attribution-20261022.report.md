# 등록 롤백본 종료 502의 출처와 후보 수정 적용 확인

2026-10-22. 목표 정합성 점검에서 남은 R6 복구 matrix 오류를 기존 증거로 좁혀 확인했다.
제품 실행·서버 변경·새 설치·백업 없이 보존 파일 17개와 정확한 Git 소스 6개를 대조했다.

## 결론

실패 1건은 등록 롤백본 1.0.26 / `541d701d544eea6a8a4e4836047077eaf9cfaf30`의
종료 중 이미지 요청 거절이다. 장비의 응답 지연이나 이미지 파일 저장 실패로 판정할 근거는 없다.
이 원인 계열은 [10월 13일 종료 순서 보완](production-release-risk-validation-shutdown-image-20261013.report.md)에서
이미 수정했다. 현재 후보 `240a49522da5d59e9e823f62612e3d4207b497a9`에도 수정이 있으며,
이번 matrix의 후보 첫 실행·재시작 두 기록에서 준비 완료 후 backend 종료와 신규 오류 0건을 확인했다.

따라서 이 항목 때문에 같은 후보를 다시 빌드하거나 동일 비교를 반복할 이유는 확인되지 않았다.
구버전 복귀 시 알려진 종료 제약의 처리 결정은 남는다. 원본 matrix의 179/180과 HOLD는 유지하며,
후보의 정식 운영 승격이나 등록 롤백 기준 변경을 수행하지 않았다.

## 같은 실행의 연결 증거

| 항목 | 보존 기록에서 확인한 값 |
|---|---|
| 실행 | `I8-baseline-restored-runtime`, main PID6876 / backend PID1600 |
| build 확인 | 마지막 health 표본과 종료 영수증 모두 `541d701d…`, 영수증 버전1.0.26 |
| backend 종료 시작 | guest `debug_electron.log`: 2026-10-19 16:05:09.615 UTC |
| 이미지 오류 | `/api/spot/live_image.jpg`, error_time1792425909.9006238, `shutdown` / HTTP502 |
| 시간 관계 | 같은 guest의 종료 시작 약285.624ms 뒤, 완료 전. 호스트 화면 클릭 시각과 시계 정렬을 가정하지 않음 |
| backend 종료 완료 | guest 16:05:10.133 UTC, exit0, forced=false |
| 실제 프로세스 종료 | 별도 lifecycle 관찰 main/backend exit0, 남은 소유 프로세스·listener 없음 |
| 저장 종료 영수증 | 이미지 enqueue105 / written105, queue·inflight·unfinished·failure·drop 모두0, writes_drained=true |

오류 trace_id는 `97e02f93-f40b-4a61-a316-3f4ab4041d1c`다. 같은 trace의 access 기록은
loopback 요청에 502를 반환했음을 보여준다. 요청한 개별 클라이언트나 아래 두 거절 지점 중
어느 곳을 지났는지는 이 자료만으로 확정하지 않는다. 이미지 저장 영수증은 해당 실행의 정산이며
센서 원시 이미지 전체 또는 과거 모든 자료의 무손실 증명이 아니다.

## 코드와 실행 순서

541d의 `backend/FacilityData/drivers/spot_api.py`는 종료 시 `_img_accepting_requests=False`로
바꾸고, `fetch_image_async` 진입 또는 잠금 획득 후 요청을 `SpotImageFetchError("shutdown", …)`로
거절한다. `backend/app.py`는 이 예외도 일반 이미지 오류로 기록하고 502를 반환한다.
기록의 `upstream_status`·transport 오류 값은 null이다. 따라서 오류 메시지의
“upstream failure”라는 문구만으로 장비 통신 장애라고 해석하면 안 된다.

541d의 main 종료 준비에는 renderer 완료 대기가 없다. 240a에는 main의
`rendererShutdownController.prepare()` 대기, preload의 준비 응답, 화면의 이미지 재요청·타이머
중단과 진행 중인 응답 처리 완료 대기가 포함돼 있다. 해당 코드의 Git object·blob·SHA256을
검산 결과에 기록했다. 현재 dirty 작업 트리를 후보 소스로 사용하지 않았다.

후보 `I4-candidate-runtime`과 `I5-candidate-restart`의 guest 기록은 각각
`renderer.shutdown-prepare-start` → `renderer.shutdown-ready` → `backend.shutdown-start`
순서이며 두 실행의 새로운 관측 오류는 0건이다. 일반 브라우저나 다른 PC는 Electron 준비
연결의 적용 대상이 아니므로 이 결과를 외부 조회 클라이언트의 종료 경계 보장으로 확대하지 않는다.

## 검증과 남은 결정

- [재현 가능한 읽기 검산](C:/Users/user/Desktop/SmartFactory/SB20_20261020_18bd8b55/analysis/shutdown-attribution-20261022/audit.py)을 실행해 exit0을 확인했다.
- [결과](C:/Users/user/Desktop/SmartFactory/SB20_20261020_18bd8b55/analysis/shutdown-attribution-20261022/audit-result.json)의 SHA256은 `6571e50d33312d3df7da61574a2cffc3eed10267b0fa39411e2369a9d6265ba1`이다.
- 봉인된 manifest·review·오류 추가분의 해시 및 manifest에 연결된 원시 파일을 확인했다. 과거 파일은 수정하지 않았다.
- 최초 분석 실행 두 번은 혼합 형식 로그와 소스 변수 이름을 분석기가 잘못 가정해 exit1이었다. 실제 형식을 확인해 분석기만 수정했으며 최종 실행이 exit0이다. 제품 실패·성공 횟수에 합산하지 않는다.
- 기존 health·패키지·현장 시험은 반복하지 않았다. 이번 결과는 오류 분류와 기존 수정 적용 확인이며 전체 QA PASS가 아니다.

남은 R6 처리는 **구버전 종료 제약의 명시적 처리 결정과 전체 QA 결과 결합**이다.
이미 수정된 후보의 종료 코드를 다시 바꾸거나 구버전 설치본을 재작성하지 않는다.
R2 실제3PC·화면 지표, R3 물리 경계, R1/R4/R5의 미완료 증거와 최종 운영 승격 판단은 그대로 남는다.
