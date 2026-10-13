# 현장 HTTP 계측 구성요소: 독립 주기·전체 응답·실패 보존

2026-10-13. 1.0.28 현장 15분/120분 collector에 필요한 HTTP 수집 모듈을 구현하고
실제 loopback 소켓 시험 31개를 완료했다. 기존 보조 계측기의 순차 요청 구조와 달리
health·data·image별 단일 worker가 같은 monotonic 원점을 기준으로 독립 실행한다.
전체 현장 collector·실제 서버 성능·설치·승격 완료를 뜻하지 않는다.

## 코드와 측정 계약

- [수집 모듈](../../scripts/field-v1028/field_http_sampling.py) SHA256:
  `a1a5bcb7fbdfaabe8bb6b5e8e0659f60a889217af35eff216b6547eea3340a53`.
- [회귀 검사](../../scripts/field-v1028/test_field_http_sampling.py) SHA256:
  `d2a623954e63646d0ba956bcc359e1c608be4b595cc272aaf11fda9a2fa2c37e`.
- evidence: `C:\Users\user\Desktop\SmartFactory\PDCA_HTTP128_20261013_0c6db624`.

기본 주기는 `/health` 2초, `/api/data` 6초, `/api/spot/live_image.jpg` 250ms다.
각 worker는 자기 요청을 겹치지 않게 하며, 이전 요청·해석·파일 쓰기가 다음 예정 시각을
넘으면 지나간 슬롯을 `missed_slot`으로 보존한다. 지연 후 연속 요청으로 누락을 숨기지 않는다.
첫 요청도 포함해 first/max/nearest-rank p50/p95/p99, timeout·HTTP 실패·시작 지연을 기록한다.
health 경고50/실패200ms, data100/500ms와 이미지 경고500ms를 사용한다.
이미지에 정의되지 않은 실패 상한은 `null`로 유지한다.

연결·송신·헤더 대기·본문 수신과 JSON/JPEG 해석 시각을 분리한다. 전체 응답 시간은
본문 수신까지이며 해석·결과 파일 쓰기 시간은 포함됐다고 주장하지 않는다.
Python의 일반 HTTP timeout은 blocking operation에 적용된다. 따라서 단일 요청 deadline의
남은 시간을 각 socket read에 적용하는 설계를 사용했고, 로컬 CPython의
`SocketIO.readinto → recv_into` 경로와 느린 연속 수신을 실제 시험했다.
근거: [Python HTTPConnection 문서](https://docs.python.org/3.12/library/http.client.html#http.client.HTTPConnection),
[socket timeout 문서](https://docs.python.org/3.12/library/socket.html#socket.socket.settimeout),
[실제 stdlib 경로](C:/Users/user/Desktop/SmartFactory/PDCA_HTTP128_20261013_0c6db624/stdlib-readinto-source.txt).

부분 본문·응답 헤더·길이·SHA와 성공/실패 이유를 보존한다. 크기 제한을 넘는 헤더는 길이·SHA와
잘림 표시를 남기며, 오류 문자열도 2048자로 제한한다. health1MiB/data8MiB/image2MiB,
JPEG 16,777,216픽셀·전체 본문4GiB·예정 표본50,000개 상한이 있다. 상한 초과는 실패다.
새 폴더와 새 파일만 사용하고 원문·요약·manifest를 생성한다. 중단·worker 오류·누락·잘못된
시간값/중복 sequence는 PASS가 될 수 없다. 모든 결과에 `field_gate=NOT_EVALUATED`,
`release_gate=HOLD`, `promotion_allowed=false`를 유지한다.

## 시험과 수정 전후 근거

첫 호출은 개발 가상환경에 pytest가 없어 exit1이었으며 검사가 실행되지 않았다.
저장소의 실제 `health:backend:test`가 unittest를 사용함을 확인하고 외부 의존성 추가 없이
unittest 실행 방식으로 변경했다. [최초 환경 오류](C:/Users/user/Desktop/SmartFactory/PDCA_HTTP128_20261013_0c6db624/initial-tests.json)를 보존했다.

기본27조건 통과 후, 요약 함수에 NaN 시간과 중복 sequence를 넣었을 때 통과할 수 있는
두 결함을 추가 회귀로 재현했다. [수정 전 exit1/실패2](C:/Users/user/Desktop/SmartFactory/PDCA_HTTP128_20261013_0c6db624/summary-red.json)와
당시 소스를 보존했다. 유한한 비음수 시간·엄격한 boolean·유일한 순서·계획된 슬롯의
실제 coverage를 확인하도록 보완해 해당 입력을 `NOT_MEASURED`로 처리했다.

최종 [31조건 결과](C:/Users/user/Desktop/SmartFactory/PDCA_HTTP128_20261013_0c6db624/unit-r3.json)는
실제 exit0/skip0이다. 전체 stdout/stderr와 종료 코드를 읽고 확인했다.

| 시험 범위 | 확인 결과 |
| --- | --- |
| 정상 JSON/JPEG·chunked 본문 | 전체 바이트·해시·해석과 시간 구간 일치 |
| HTTP503·redirect·연결 거부 | 실패 기록, redirect를 외부 주소로 따라가지 않음 |
| 불완전 본문·과대 본문/헤더·잘못된 JSON/JPEG·중복 JSON key·NaN | 실패와 보존된 부분 바이트 또는 제한 표시 |
| 조금씩 계속 전송하는 헤더·본문 | 단일 요청 deadline으로 timeout, 성공으로 판정하지 않음 |
| 이미지 응답240ms·세 endpoint 시험 주기80ms | health8/data8 요청 유지, image2 요청/누락6을 기록, 같은 endpoint 동시 요청 최대1 |
| 첫 요청 실패·200ms 경계·이미지 상한 미정 | 첫 실패/최댓값 유지, health200ms 허용, 이미지 실패 상한 null |
| 중단·본문 예산·기존 경로·잘못된 계약 | 수집 미완료/실패 또는 쓰기 전 거부 |

실제 기본 주기로6.2초 loopback 관찰을 수행해 health4/data2/image25 요청을 남겼다.
실제 시작 간격은 health1994.5728–2006.6533ms, data6006.2519ms,
image241.0084–261.3726ms였다. 예정 시각·실제 지연을 함께 보존하며 정확히 일정한 간격이었다고
표현하지 않는다. 이 짧은 fixture 관찰은 실제 앱이나15분/120분 현장 성능의 대체가 아니다.

실행 방법 예:

```powershell
$env:SFL_HTTP_TEST_ROOT = 'C:\Users\user\Desktop\SmartFactory\<새 실행 폴더>\unit-new'
& .\backend\.venv\Scripts\python.exe .\scripts\field-v1028\test_field_http_sampling.py
```

상위 실행 폴더는 먼저 만들고 `unit-new`는 존재하지 않아야 한다. 시험은 임의 포트의
127.0.0.1 fixture만 사용하며 운영 앱·장비·설정을 제어하지 않는다.

## 검산·보존과 남은 통합

[최종 검산](C:/Users/user/Desktop/SmartFactory/PDCA_HTTP128_20261013_0c6db624/verification-reviewed.json)은
최종 소스 SHA, 원시 로그, 이전/최종 실행에서 생성한 결과 manifest11개 및 각 본문 해시를
대조해 exit0이었다. 수집기·시험기·검산기의 Ruff F/E9도 exit0이다.
기록309파일은 `Z:\SmartFactory\20261013\records\PDCA_HTTP128_0c6db624`에 복사해 전체 SHA를 확인했다.
manifest 제외370,021바이트, [기록 manifest](C:/Users/user/Desktop/SmartFactory/PDCA_HTTP128_20261013_0c6db624/records-manifest.json)
SHA256은 `fe047eddc2fa420c61b4fcde3af6e8f9b10c4465f2e722638a93ee1b3c19a414`다.
봉인 후 [전송 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_HTTP128_20261013_0c6db624/record-transfer.json)은 별도 보존한다.

실제 서버 실행 entrypoint·실행 묶음은 아직 제공하지 않는다. 다음 통합은 최종 installer/설치
트리·프로세스/logger/fingerprint 결합, 보호된 결과 경로와 잠긴 실행, 자원/물리 디스크/
화면/packet 계측, 최종 정상 종료·delta와 같은 관찰 경계 연결이다. 이 새 계측 방식의 실제
부하도 해당 통합 단계에서 확인해야 한다. 기존1.0.26 canary를 버전 문자열만 바꿔 재사용하지 않는다.

제품 소스·설치본은 변경하거나 재빌드하지 않았다. 전체 health/NSIS·대규모 데이터 전수 검사는
이번 도구 변경으로 반복하지 않았다. 미서명 내부 운영 정책, 현재541d/08C 롤백 기준,
R1–R6 HOLD와 전체 후속 PDCA 목표를 유지한다.
