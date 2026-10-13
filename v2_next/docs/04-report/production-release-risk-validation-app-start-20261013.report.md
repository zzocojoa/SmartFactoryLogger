# 전체 앱 격리 시작 반복 계측 — 2026-10-13

상태: run-04~13 격리 초기 시작 계측과 독립 검산 완료. 해당 시작/계획 요청 지표는 통과했지만,
전체 R2·정식 출시 판정은 HOLD다.

## 목적과 입력

[출시 계획 R2](../01-plan/features/production-release-risk-validation-codex-production-release-risk-validation-20261010.plan.md)의
격리 시작 10회 부분을 조사한다. 앞선 [lifespan-off HTTP 시험](production-release-risk-validation-server-read-20261012.report.md)은
전체 앱 시작 시험에 포함하지 않는다. 이번 실행은 실제 Electron 화면, backend lifespan, CSV 재생,
SPOT 합성 응답, 이미지 저장 및 정상 종료 경로를 함께 사용한다.

- 로컬 증거: `C:/Users/user/Desktop/SmartFactory/PDCA_APP_START_20261013_71be68fc`
- 준비 시각: 2026-10-13 06:06:59 KST. runtime 125파일을 경로·크기·SHA256으로 결합했다.
- source HEAD: `eb9af6f1398d588733f3f1884411e2612496d267`, 기존 로컬 수정 포함, 버전 1.0.26.
  clean commit/packaged installer 시험이 아니다. 제품 소스는 이번 단계에서 수정하지 않았다.
- Electron 실제 실행 파일: 44.3.0, 246,070,272바이트,
  SHA256 `e048632e03fabc96de5e10afbebc0aa31f4e1674155ea3d270597fe7523f9d80`.
- 닫힌 서버 CSV: 340,304,366바이트,
  SHA256 `d8f7b769dd57c95d7d730df342a59b9b4175a964cca74aba92c0802b6b0c0f69`.
- 초기 image fact 사본: 2,123,413,658바이트/4,143,509행,
  SHA256 `8233d11d63fad4e624a06dd059273c5a7d372372941735a2dbf3db58b638434d`.
- PLC는 위 CSV 재생, SPOT은 `127.0.0.1:80` 합성 fixture다. JPEG는 320×256/1,910바이트,
  SHA256 `b4d74d6b62f9101e89113fe1da1e681f7c5305cec07e29a0f1f428210015c989`다.
- 운영 AppData/장비 주소/중앙 동기화 인증 설정을 상속하지 않는다. 같은 격리 AppData의 fact는
  시험 저장분만 순차 증가하며, Electron userData는 실행별 새 폴더다. OS 파일 캐시는 초기화하지 않았다.

## 측정과 보존 규칙

전용 client는 listener TCP 확인 직후 첫 `/health`부터 약 2초 주기로 비중첩 요청한다.
connect/send/headers/body를 포함한 전체 본문 수신 시간에 200ms 상한을 적용한다.
앱의 `renderer.dashboard-operational-ready`는 Electron startup telemetry의 `elapsed_ms`를 사용해
별도로 30초 상한을 적용한다. 아래 준비 시간 표도 이 telemetry 기준이며, 요청 주기와 45초 관찰 창은
부모 시험 도우미의 `perf_counter_ns` 실행 시작점을 사용한다.
`/api/data`는 약 6초 주기로 수집하고 실패 상한 500ms, 목표·경고 100ms와 구분한다.
통계·설정 API에는 임의 시간 상한을 만들지 않는다.

각 시행의 `health-000.json/.body`를 포함한 원시 요청, TCP 실패, startup telemetry,
프로세스 CPU/메모리/IO 표본, 화면 PNG, 정상 종료 이벤트, fact 전후 해시 및 추가 바이트를 남긴다.
`capture.request`/`quit.request`는 시험 bootstrap이 읽으며, 종료는 제품의 `app.quit` 경로를 사용한다.
원본 fact prefix와 새 이미지 파일은 최종 독립 검산 대상으로 삼는다.

## 실패한 준비 시행과 도우미 정정

| 시행 | 실제 결과 | 처리 |
| --- | --- | --- |
| run-01 | Electron binary 부재, process 생성 전 exit 1 | npm Electron 패키지의 기존 lazy install 수행. 잘못된 경로라는 초기 해석은 별도 영수증으로 정정 |
| run-02 | 필수 operational flag 3개 중 하나 누락, backend import exit 1 | 세 플래그를 함께 설정. GUI stdin 수신 실패로 파일 명령 방식으로 변경 |
| run-02 종료 | backend 없는 상태에서 정상 종료 closeout 검증 거부 | 정확한 소유 시험 PID/실행 파일/시작 시각·backend 부재·fact 원본 해시를 확인한 뒤 해당 격리 Electron만 강제 종료(exit 15). 운영 앱 변경 없음 |
| run-03 | 앱 준비 12,819.2ms, health 20개 모두 200ms 이내, 정상 종료 0 | 부가 통계를 잘못된 `/api/stats`로 요청해 404. 원래 summary의 pass=true는 전체 요청 성공을 의미하지 않음 |

run-02 기존 summary의 `force_stop=false`는 별도 `forced-owned-trial-stop.json`으로 정정한다.
run-03 원문은 변경하지 않고 `request-gate-correction.json`에 실패 경로와 `/stats` 누락을 기록했다.
수정 후 run-04~13을 별도 10회 계열로 측정한다. 앞선 실패와 첫 응답을 제거하지 않는다.
v3 도우미는 모든 계획 route의 HTTP 200·완전한 JSON 본문·오류/timeout 없음·누락 없음과
각 route의 정의된 시간 상한을 함께 판정한다.

## 06:35 KST 반복 실행 완료 결과

실제 `measure_app.py --start 4 --count 10`은 session 73440에서 exit 0이었다.
모든 실행의 backend/renderer가 활성화되고 CSV 재생값과 history sequence가 변했으며,
각각 다른 logger/SPOT 세대에서 저장 후 정상 종료했다. 강제 종료는 이 10회에 없다.

| 시행 | 준비 ms | 첫 health ms | health 최대 ms | health 표본 | CSV 행 | 새 이미지 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 04 | 12805.6 | 25.0455 | 26.6075 | 20 | 140 | 37 |
| 05 | 12810.6 | 4.2555 | 27.1322 | 19 | 130 | 36 |
| 06 | 12916.1 | 29.7095 | 30.6311 | 19 | 178 | 35 |
| 07 | 13131.6 | 22.1402 | 30.0384 | 19 | 159 | 36 |
| 08 | 13116.9 | 4.0163 | 9.8677 | 20 | 130 | 38 |
| 09 | 10132.6 | 4.9740 | 14.8189 | 19 | 167 | 36 |
| 10 | 13152.1 | 23.2884 | 27.5896 | 19 | 169 | 36 |
| 11 | 12830.9 | 18.1041 | 27.1450 | 19 | 140 | 36 |
| 12 | 12869.2 | 35.1973 | 35.1973 | 19 | 166 | 35 |
| 13 | 12885.1 | 34.0677 | 34.0677 | 19 | 132 | 35 |

- 준비 시간 10,132.6~13,152.1ms, 10/10회 30초 이내.
- health 192개: p50 7.7114ms, p95 27.1322ms, p99 34.0677ms, 최대 35.1973ms.
  오류/timeout/200ms 초과 및 50ms 경고 초과 0. 첫 요청도 포함한다.
- data 70개: p50 2.5766ms, p95 20.1625ms, p99/최대 25.8825ms.
  오류/timeout/500ms 초과 및 100ms 경고 초과 0. percentile은 nearest-rank 방식이다.
- 설정/통계 각 10개를 합쳐 계획된 HTTP 요청 282개는 모두 200·본문/해시/JSON 일치다.
  앱의 내부 응답 시간과 별도로 client 전체 시간을 사용했다.
- 새 CSV 1,511행의 연속 sample_seq·실제 최종 seq·같은 logger 세대의 `csv_closeout.finalized=true`를 대조했다.
  observation fact 누적 prefix SHA와 각 sidecar의 종료 manifest가 일치했다.
- 새 이미지 360개 및 선행 run-03의 37개, 합계 397개의 경로/크기/SHA256/JPEG 디코딩을 확인했다.
  실행별 final image manifest의 행·해시·written 수, drop/failure=0과 일치한다.
- 초기 2,123,413,658바이트는 그대로 보존됐고 실행별 추가 바이트와 누적 해시를 독립 계산했다.
  최종 fact는 2,123,614,003바이트/4,143,906행,
  SHA256 `8df9369aafee2142090ad7217fe2e283e9414cb36ea5dc53e8191a6aab8615d6`다.
- backend 정상 종료는 436.3~1,360.7ms였고 Electron/관측된 자식 process의 동일 PID·생성 시각이 남아 있지 않음을 확인했다.

## 검산·도우미 검사와 제한

독립 검산 도구는 sampler/gate 구현을 import하지 않고 원시 JSON·본문·CSV·추가 fact·이미지와
종료 이벤트를 다시 비교했다. 첫 두 검산 실패는 각각 임의 최소 20표본 조건과 마지막 health 시작
시각을 전체 관찰 종료 시각으로 잘못 사용한 조건 때문이었다. 원문·도구 v1/v2·exit 1 기록을 보존했다.
계획의 실제 종료 조건(health/data/자원 수집 후 45초 도달)을 적용한 최종 검산은 exit 0이다.
sequence 0부터의 누락 없음, data 매 3번째 health, 비중첩·2초±0.1초 요청 간격을 확인했다.
`independent-review-correction.md`에 정확한 시각과 수정 근거를 남겼고 성능 상한은 변경하지 않았다.

도우미 회귀 8개는 수정 전 실패를 확인한 뒤 최종 exit 0이었다. Ruff F 정적 검사와
`node --check test-bootstrap.cjs`도 exit 0이다. runtime 125파일은 현재 repository 바이트와 일치하며,
원본 CSV/fact 해시 및 이전 전체 health에 결합한 8개 source 해시도 그대로다.
제품 변경이 없어서 전체 health를 반복하지 않았다. 기존 전체 health exit 0의 backend 범위는
920개 중 919통과·기존 private fixture 1생략이며, 이번 시험의 결과와 구분한다.

run-04/13 저장 화면에서 Running·재생값·합성 이미지 표시를 확인했다. UI의 작업 정보는 미입력이고
전체 화면 배치/현장 업무 QA를 통과한 것으로 해석하지 않는다.

## 범위와 남은 검증

저장된 화면 배치가 없는 격리 환경에서 `/api/layout` 404가 관측됐다. 구현도 활성 배치가 없으면
404를 반환한다(`backend/app.py`의 `get_layout`). 원시 로그와 전체 HTTP 통계에 그대로 보존한다.
단일 전용 client의 계획 요청 성공을 앱의 모든 요청에서 오류가 없었다는 뜻으로 확장하지 않는다.

각 시행의 종료 전 `/stats`에는 5xx=0이지만 종료 시작 이후 이미지 요청 502가 총 14건 남았다.
stdout의 `backend.shutdown-start` 이후 위치와 같은 구간의 `source=spot_image status=502 type=shutdown`
관측 14건을 확인했다(`shutdown-http-review.json`, exit 0). 정상 종료 시 UI 이미지 요청이 계속되는
현상은 후속 검토 대상으로 보존한다. 이 로컬 종료 관찰을 과거 실제 장비 timeout 원인으로 대체하지 않는다.

CSV sidecar의 `spot_image_fact_manifest`는 파일 생성 시점 값이 남고, 정상 종료 후 image fact의
최종 값은 별도 `spot_image_fact_manifest.final.json`에 기록된다. 검산은 각각의 시점을 구분하고
최종 이미지 manifest와 실제 누적 fact 바이트를 비교한다. sidecar 이미지 값을 최종 값으로 보고하지 않는다.

과거 fact의 이미지 전체를 이 격리 폴더에 복원하지 않았고 실제 제품/금형도 시험용 UI에 입력하지 않았다.
전체 데이터 의미 검증, 승인 실장비 모델·설정, 실제 네트워크 timeout/drop 원인은 별도다.
자원 계약의 120초 warmup+300초 창, 1/3탭 비교, 계측 off 비교, LCP/CLS와 전체 이미지 client 시간,
현장 정상 시작 3회, 최종 clean 미서명 설치본의 설치·복구·15분/120분 시험은 이번 시행에 포함하지 않는다.
전체 목표 active, `full_data_gate=NOT_EVALUATED`, R1–R6 HOLD를 유지한다.

## 공유 증거 보존

전체 실행 증거를 `Z:/SmartFactory/20261013/records/PDCA_APP_START_71be68fc`에 복사했다.
공유 복사·원본 최종 재해시·목록 검사는 session 41967에서 실제 exit 0이었다.
manifest/receipt 포함 2,266파일,
입력 내용 2,863,467,420바이트다.
manifest SHA256은 `c057bd02816d05d97c75e098d98908e3307bffe178c0ce9629327c019cc84973`다.
생성 manifest/receipt 자체는 manifest의 입력 목록에서 제외하고 별도로 동일 바이트를 확인했다.
제외 목록은 seal-receipt의 `excluded_preserved_locally`에 기록되어 있으며 원본에서 삭제하지 않았다.
운영 서버 설치·재시작·승격과 롤백 기준 갱신은 수행하지 않았다.
