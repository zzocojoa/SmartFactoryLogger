# 실제 C32 화면 코드의 표시 계측 호환성 검증

2026-10-23. [기존 PC4대 동시 조회·육안 확인](production-release-risk-validation-four-pc-evidence-20261023.report.md)은
완료 범위로 유지한다. 이번은 추가 수치 계측 도구의 준비이며 현장 시험을 반복하지 않았다.

## 이번 확인과 수정

- 1.0.32 `cd46692ac9c551080c57d8168fa9ea5abd530206`의 기존 NSIS 추출 화면 파일51개를
  payload manifest의 길이/SHA256으로 검산하고, 수정 없이 loopback fixture에서 제공했다.
- Chromium148.0.7778.96의 별도 headless 프로필에서 실제 dashboard의 arrayBuffer→검증→Blob→img
  경로를 실행했다. API/이미지는 합성 자료이며 실제 장비·운영 데이터는 사용하지 않았다.
- 최초 fixture는 image_refresh_interval을 생략해1초 주기로 동작했다. 실제 이미지 전용 항목
  0.25초를 제공하도록 fixture만 수정했다. 운영 설정은 변경하지 않았다.
- 관찰기의 상단 모서리 검사점이 제품의 Focus 버튼과 겹쳐 가림으로 판정했다. 이미지 내부
  25%/50%/75% 지점으로 바꾸고, 실제 전체 흰 overlay는 여전히 가림으로 검출하는 회귀를 추가했다.
  세 DOM 지점은 전체 창이나 모니터 출력의 독립 증거를 대신하지 않는다.
- 관찰 종료 뒤 표시된 이미지는 tail 자료로 따로 보존하고 본 구간 분위수 표본에 섞지 않는다.
  page watchdog 종료에서도 해시 함수 연결을 제거한다.
- 기존 CDP의 정확한 page 하나에 붙는 CLI를 추가했다. 전후 C32 build/logger를 확인하고 새
  결과 파일만 생성한다. 잘못된 build에는 수집하지 않으며, 정상/실패 모두 page를 닫지 않고
  관찰 연결만 닫는다. 시간 원점/단조 시계도 기록한다.

## 최종 변경 상태 검증

| 확인 | 결과 |
|---|---|
| `node --test scripts/field-v1028/observe_image_presentation.test.cjs` | 5 tests, exit0 (`5c38c1`) |
| `probe-renderer.cjs result-r4.json` | 실제 C32 화면의 5초 구간 표시19개/로드19개 연결, exit0 (`279c1d`) |
| 복원·격리 | Response 함수/elementtiming/관찰 함수 복원, 시험 브라우저·listener 정리 |
| 실서버 수치 성능·4PC 표시 판정 | NOT_EVALUATED. 위 headless 결과로 대체하지 않음 |

시험은 추가 이미지 HTTP 요청 없음, native edge controls 처리, 실제 가림 검출, load만 있는 경우,
모호한 hash·반복 source 식별 거부, 종료 경계, CLI의 기존 결과 덮어쓰기/외부CDP/초과시간/다른
build 거부와 기존 page 보존을 확인한다. R1 실패·R2/R3 중간 결과는 수정하지 않았다.

준비·실행 자료: [PRESENT32 README](C:/Users/user/Desktop/SmartFactory/PRESENT32_20261023_9a736ec2/README.md).
최종 R4 SHA256은 `97cfd36d0acd0b48bc83129c172795185097ed34b9731fdfe5a5f293d3e62fdd`다.

## 서버 현재 상태와 남은 작업

23:49:38 KST 승인 SSH 읽기에서 DESKTOP-CIIT7LK/user 관리자 연결, C32 Running,
logger `5be11b2f-d2cc-42b9-b8ce-3d19fdc72b7e`와214331 CSV, 원장 쓰기/연결 실패0을 확인했다.
19221 listener는 없으며 임시 연결을 열지 않았다. 당시 온도 상태는 invalid_sentinel이었다.
23:51 원격 화면에서 Smart Factory가 전면에 있고 대시보드/카메라가 보임을 확인했다.
작업 정보는22:57:48 이후 미입력으로 보였으며 값을 변경하거나 생산 여부를 추정하지 않았다.

남은 것은 각 실제 PC의 접근 경로·현재 화면 조건에 맞춘 실행 결합, 표시 시각과 독립 화면
증거의 수집·평가, 기존 저장/설치/복구 자료를 합친 최종 QA와 운영 승격이다.
PC4대에서 추가 계측 가능한 시간에 대한 응답은 아직 없다. 단순히 기다린 시간을 실행으로 세지 않는다.
이번에는 운영 설치/재시작/설정 변경/백업/삭제를 수행하지 않았다. 전체 출시 HOLD를 유지한다.
