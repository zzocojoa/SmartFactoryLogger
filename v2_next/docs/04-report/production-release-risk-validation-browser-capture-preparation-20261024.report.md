# 조회 PC의 추가 관리 연결 없이 표시 시각을 수집하는 방법

2026-10-24. [완료한 PC4대 관찰](production-release-risk-validation-four-pc-evidence-20261023.report.md)을
유지하며, 부족한 수치 계측의 실제 실행 방법을 준비했다. **격리 시험 완료·현장 미실행**이다.

기존 CDP 수집기는 각 PC에 원격 제어 인터페이스가 있어야 했다. 새 방식은 조회 PC의 기존
대시보드 안에서만 실행하는 즐겨찾기 도구다. Node 설치·관리자 권한·새 포트·서버 업로드가
필요하지 않다. 서버 Electron은 기존 승인된 내부 CDP 경로가 별도로 필요하다.
다른 PC의 새 관리 접속 권한을 만들지 않았다.

## 구현과 검증

기존 `observe_image_presentation.cjs`의 page 관찰 함수와 대응 함수를 그대로 추출하고,
이미 설치된 `@noble/hashes 2.2.0`과 Rollup4.62.2로 하나의 로컬 파일에 묶었다.
새 npm 설치·제품 코드 수정·설치본 재빌드는 없다. 묶음의 입력8개와 출력6개의 해시를 고정했다.

브라우저의 기존 fetch 응답과 이미 소비하는 본문만 읽어 이미지 SHA·백엔드 프레임 수신 시각·
Blob URL·presentationTime을 연결한다. 이미지 HTTP 요청은 추가하지 않으며 전후 health2회로
build/logger를 확인한다.15분 후 함수/elementtiming을 복원하고 로컬 JSON 저장 링크를 제공한다.
CDP network 이벤트 대신 browser fetch 응답에서 읽은 헤더임을 원시 결과에 명시한다.
센서 원시 샘플 ID나 실제 모니터 전체 픽셀의 증거로 확대하지 않는다.

| 실행 | 결과와 범위 |
|---|---|
| `verify_browser_observer.cjs` | 정상6표시/6응답,HTTP503,다른build의3경우exit0(`ce665e`). 오류는 INCOMPLETE, 모든 경로 복원 |
| `probe-renderer.cjs renderer-result.json` | C32 화면51파일을 변경 없이 검산·실행.19표시/19로드,exit0(`14b0a2`) |
| `verify_bookmark_delivery.cjs` | javascript URL 실행·입력1회·대시보드 유지·JSON 다운로드·복원,exit0(`8c6e22`) |

마지막 시험은 요청을 전부 격리 처리하고 가상 시계로 대기 시간을 진행했다. 따라서 실행/저장
흐름 검사이며15분 실시간 계측이나 현장 성능을 검증한 것은 아니다. 정상 표시 대응 시험은
별도 실제 시간5초로 수행했다. Chromium headless 시험을 물리 PC4대의 결과로 사용하지 않는다.

첫 생성은 함수 추출 기준이 고유하지 않아 파일 출력 전exit1(`07d36a`)로 중단됐다.
정확한 함수 인자까지 포함한 고유 기준을 사용한 생성은exit0(`18c460`)이었다.
출시/제품/서버의 오류가 아닌 준비 도구 오류이며 실패 기록을 보존한다.

실행 자료·사용 순서: [BROWSER32 README](C:/Users/user/Desktop/SmartFactory/BROWSER32_20261024_28ad608e/README.md).
실제 C32 화면 결과 SHA256은 `1bbadeb21dfb0cc4b41b7a9aa13292fcfa33a2c3deeac5d7300573692cabedeb`다.

## 현장 조건과 남은 작업

00:14:33 KST 서버의 승인 SSH 읽기에서8000포트의 Established 연결3개 모두loopback이었다.
이는 순간의 연결 목록이며 다른 PC가 없거나 네트워크에서 사라졌다는 증명이 아니다.
현재 네 화면이 모두 열려 있다는 근거로도 사용할 수 없다. 서버 설정·수집·파일은 변경하지 않았다.

조회 PC3대에서 도구를 실행할 수 있는지와 가능한 시점, 서버의 정상 종료/진단 실행/일반 복귀
관찰 순서를 맞춰야 한다. 각 실제 브라우저의 지원 여부는 그 PC에서 확인해야 한다.
모든 PC가 계속 보이는 조회 구간 안에서 각900초 계측을 수행하고 실제 시작/끝과 공통 구간을
별도로 기록한다. 수치 결과와 독립 화면 확인이 없으면 최종 화면 판정은 INCOMPLETE다.
기존120분·설치/복구·저장 검사를 자동 반복하지 않는다. 전체 목표active·출시HOLD다.
