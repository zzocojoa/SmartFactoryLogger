# 단일 Electron 화면 자원 관측 — 2026-10-13

상태: 준비 운전 120초와 관측 300초의 수집·독립 검산·공유 보존 완료.
화면 프로세스 RSS 상향 추세가 있어 자원 안정성은 통과로 판정하지 않는다.
누수 원인 미확정, 전체 R2는 NOT_EVALUATED, R1–R6/정식 출시는 HOLD다.

## 입력과 실행 조건

[전체 앱 시작 시험](production-release-risk-validation-app-start-20261013.report.md)의
봉인된 runtime과 실제 CSV/fact 사본을 새 격리 폴더에 복사했다.
source manifest SHA256은 `c057bd02816d05d97c75e098d98908e3307bffe178c0ce9629327c019cc84973`다.

- 로컬 증거: `C:/Users/user/Desktop/SmartFactory/PDCA_RESOURCE_WINDOW_20261013_3aa59dad`.
- source HEAD: `eb9af6f1398d588733f3f1884411e2612496d267`, 기존 로컬 수정 포함, v1.0.26.
  runtime 125파일을 현재 저장소 바이트와 대조했다. clean commit/설치 패키지 시험은 아니다.
- Electron 44.3.0 실행 파일 SHA256:
  `e048632e03fabc96de5e10afbebc0aa31f4e1674155ea3d270597fe7523f9d80`.
  Python 3.12.6, Windows 11 10.0.26300, psutil 7.2.2, Pillow 12.3.0, 논리 CPU 12개다.
- CSV 입력 340,304,366바이트, SHA256:
  `d8f7b769dd57c95d7d730df342a59b9b4175a964cca74aba92c0802b6b0c0f69`.
- 초기 fact 2,123,614,003바이트/4,143,906행, SHA256:
  `8df9369aafee2142090ad7217fe2e283e9414cb36ea5dc53e8191a6aab8615d6`.
  실제 과거 4,143,509행에 앞선 격리 시험의 합성 이미지 397행이 추가된 입력이다.
- CSV 재생과 loopback SPOT fixture를 사용했다. JPEG는 320×256/1,910바이트,
  SHA256 `b4d74d6b62f9101e89113fe1da1e681f7c5305cec07e29a0f1f428210015c989`다.
- 새 AppData/userData, native Electron 화면 1개다. 운영 주소·중앙 동기화 인증 설정을 상속하지 않는다.
  실제 운영 작업번호를 시험 UI에 입력하지 않았고 장비 프로파일/물리 온도 정확도 검증은 아니다.
- 제품의 기본 관측 수집은 켜져 있고 memory profiler는 꺼져 있다.
  전용 `SFL_SHUTDOWN_DIAGNOSTIC_DIR` 추적은 이번 단계에서 껐다. 다른 실행 조건도 바뀌었으므로
  이전 시작 시험과의 차이를 통제된 계측 on/off 비교로 해석하지 않는다.

`PLAN.md`를 고정한 뒤 `measure_resource.py`를 실행했다(session 6254, 실제 exit 0).
앱 준비 telemetry는 8,474ms였고 준비 운전 기준점은 06:59:48.401 KST다.
5초 주기 85표본 중 index 0–23은 준비 운전, 24–84는 관측 61표본이다.
관측 실제 길이는 300.0001866초였다. backend process/collector history는 각각 중복 제거 후
60표본/296.2289805초로 최소 48표본·240초와 선호 60표본 조건을 만족했다.
각 `/stats`의 실제 계약도 120초/300초/5초로 대조했다.

준비 운전 중 `/api/memory/state`에 CSV queue가 없음을 확인해 별도 GET 전용
`collect_details.py`를 추가했다(session 3995, 실제 exit 0). 원래 실행 도우미는 변경하지 않았다.
`ADDENDUM.md`에 105초부터의 15초 간격 요청 22개와 준비 운전 초반 미수집을 기록했다.
이 중 21개 요청은 본 관측 구간이다. 이 추가 수집 부하도 후속 비교 조건에 포함해야 한다.

## HTTP와 저장·종료 결과

계획 요청 442개와 details companion 22개, 총 464개 모두 성공했다.
원시 본문의 길이·SHA256·JSON/JPEG와 요청 순서/누락/비중첩을 독립 검산했다.
시간은 연결·송신·헤더·전체 본문 수신까지이며 아래 표의 수량과 지표는 준비 운전을 포함한다.

| 경로 | 전체 / 관측 표본 | 첫 요청 ms | p95 ms | 최대 ms |
| --- | ---: | ---: | ---: | ---: |
| `/health` | 212 / 150 | 19.5539 | 23.4671 | 32.4872 |
| `/api/data` | 71 / 50 | 6.2853 | 18.0038 | 25.4205 |
| `/api/spot/live_image.jpg` | 43 / 31 | 2.0619 | 26.0363 | 34.8380 |

health 요청 시작 간격은 1.9991057–2.0004234초이며 모두 running/driver connected였다.
health 200ms/data 500ms 상한, 각각 50ms/100ms 경고 초과는 0이다.
이미지 500ms 목표·경고 초과도 0이며 이미지에 임의 실패 상한을 추가하지 않았다.
percentile은 nearest-rank다. 이미지 API 본문 수신은 실제 화면 표시 시간의 대체 지표가 아니다.

새 CSV 1,825행의 연속 sample_seq·logger 세대와 `csv_closeout.finalized=true`를 대조했다.
새 이미지/fact 389건의 세대·파일 크기·SHA256·JPEG 디코딩을 모두 확인했다.
image writer 최종 drop/failure는 0이고 원래 fact prefix도 그대로다.
최종 fact는 2,123,811,596바이트/4,144,295행,
SHA256 `6d7ea821461b72b77285beefcc0803d40f1cc4d6a710db2f4741f8d7da33e3f4`다.
추가 197,593바이트의 SHA256은
`d2d46db19582390cd9f330a50b8b792b378f101c63021d15a7c96a2f5b7158a1`이다.
`app.quit` 경로의 정상 종료 후 같은 PID·생성 시각의 모든 관측 프로세스가 끝났고 강제 종료는 없었다.

앱 전체 로그에는 새 userData에 저장 배치가 없어 초기 `/api/layout` 404가 있다.
정상 종료 시작 후 이미지 502 한 건과 같은 `type=shutdown` 오류 기록도 보존했다.
따라서 전용 client 요청 성공을 앱 전체 오류 0으로 확대하지 않는다.
이 종료 오류는 실제 서버의 과거 네트워크 timeout 원인을 입증하지 않는다.

## 자원 증가 관찰과 해석

아래 변화량은 관측 구간 첫/끝 20% 평균 차이다. 외부 프로세스 표본은 양끝 각 13개,
backend history는 각 12개다. RSS는 상주 메모리이며 합계에 공유 페이지가 중복될 수 있다.

| 관측 대상 | 변화/범위 | 판정 범위 |
| --- | --- | --- |
| 전체 소유 프로세스 RSS 합 | +158.07 MiB, 인접 증가 49/60 | 물리 고유 메모리 측정은 아님 |
| Electron 화면 renderer PID 24996 | RSS +143.27 MiB, VMS +22.76 MiB | 저장된 Electron app metrics의 Tab 타입과 PID 대조 |
| backend Python PID 56820 | 외부 RSS +13.12 MiB | backend API의 별도 시각 표본은 +13.07 MiB |
| backend API RSS | 2,424,586,240–2,441,146,368바이트, 인접 증가 56/59 | 단일 관측 창이며 장기 plateau 미확인 |
| 전체 CPU | 기계 용량 기준 2.139–3.724% | 논리 CPU 12개로 정규화, 프로세스 구성 변경 구간 0 |
| 전체 thread / handle | 116–131 / 3,004–3,073 | 열린 파일 수의 대체 증거는 아님 |
| 프로세스 IO | 읽기 1,629,695–1,719,451, 쓰기 1,651,578–1,770,775 bytes/s | 물리 디스크 처리량 측정은 아님 |
| CSV queue | 최대 1/5,000 (0.02%), drop 0 | collector severity 모두 ok |

`facility.plc_history`는 457→1,816항목(최대 36,000), 추정 3,181,755→12,765,302바이트로
늘었다. 이 추정값은 실제 heap의 정확한 귀속이나 renderer 증가 원인을 증명하지 않는다.
관측된 `observability.errors` 항목은 0이고 최종 backend `leak_suspects`는 빈 목록이지만
이 둘만으로 메모리 누수 부재나 전체 자원 안정성을 판정하지 않는다.

`resource-growth-details.json`의 판정은
`RSS_UPWARD_TREND_REQUIRES_FOLLOWUP; NO_LEAK_CAUSE_CONFIRMED`다.
소스 읽기에서 이미지 성공/오류/해제 경로의 `revokeObjectURL`과 36,000점 시계열 상한을 확인했다.
해제 코드의 존재만으로 실제 retained object 수명이나 RSS 증가 원인을 확정할 수 없다.
원인 확인 전 제품 코드의 메모리 제한·수집 간격을 임의 변경하지 않았다.

## 검증과 증거 보존

- `resource_review.py`: 실제 exit 0. warmup 제외·중복 제거·최소 창·HTTP·저장·정상 종료 독립 검산.
- `describe_resource_growth.py`: 실제 exit 0. 프로세스별 증가와 종료 오류 시점 분리.
- 도우미 회귀: HTTP fixture 1개, 관측 검산 2개, archive 1개 모두 최종 exit 0.
  각 변경 전 실패와 변경 후 결과를 보존했다. 동일 길이 변조/뜻밖의 archive member도 거부했다.
- 도우미 Ruff F와 bootstrap `node --check`: exit 0. 원문 로그와 실제 종료 영수증 보존.
- `final_source_check.py`: exit 0. 이전 봉인 입력 130개와 현재 runtime 125개,
  이전 전체 health에 결합된 source 해시 8개 불변 확인.
  제품 소스 변경이 없어 전체 health는 반복하지 않았다.

공유 보존은 session 59970에서 실제 exit 0(07:16:00 KST)이었다.
입력 1,707파일/2,517,515,282바이트와 manifest를 ZIP 1,708 member로 보존했다.
모든 member의 경로·길이·내용 해시, 원본 최종 해시/목록, 공유 archive 해시 일치를 확인했다.
기본 데이터 스트림을 검증했으며 NTFS 추가 스트림을 검증한 것은 아니다.

- 공유: `Z:/SmartFactory/20261013/records/PDCA_RESOURCE_WINDOW_3aa59dad`.
  `evidence.zip`, `evidence-manifest.json`, `seal-receipt.json` 3파일이다.
- 로컬 ZIP: `C:/Users/user/Desktop/SmartFactory/PDCA_SERVER_IMAGES_20261013_43ef972a/PDCA_RESOURCE_WINDOW_3aa59dad.zip`.
- ZIP 419,941,615바이트, SHA256
  `c66e32c0c469db35fd56e7a50fa25bf46b41153afebfd18a5f66bfd11e2e2ecb`.
- manifest SHA256: `dbc80200c7714f9157b6ff74e257159b19a2d4e54183fd4c2396a657b31b6f2b`.

## 다음 검증 체크리스트

1. renderer의 JS heap·DOM·Blob URL·이미지/차트 보유량과 장기 plateau를 격리 계측해 RSS 증가 원인을 좁힌다.
2. 같은 브라우저 1/3탭과 통제된 계측 on/off 조건을 비교한다. native 화면 3개로 대체하지 않는다.
3. LCP/CLS·이미지 실제 표시·open-file 추세의 미측정 범위를 보완한다.
4. 실제 서버 정상 시작 3회 및 최종 clean 미서명 설치본의 설치/복구/현장 QA·15분/120분은 별도로 검증한다.

운영 서버 설치·재시작·승격과 롤백 기준 갱신은 이번 단계에 없다.
전체 목표 active, `full_data_gate=NOT_EVALUATED`와 기존 운영본/다음 롤백 기준을 유지한다.

## 2026-10-13 07:44 KST renderer 수명 후속 진단

앞선 RSS 증가를 JS 객체·DOM·URL 수명과 구분하기 위해 새 격리 폴더
`C:/Users/user/Desktop/SmartFactory/PDCA_RENDERER_GROWTH_20261013_e3a1a8e0`에서 계측했다.
위 단계의 봉인 입력 132파일을 복사했고 현재 runtime 125파일·기존 health 결합 source 8개가
그대로임을 재확인했다. 초기 fact는 위 단계 최종 4,144,295행이며 과거 원본에 앞선 합성 786행이
포함돼 있다. 동일 CSV/JPEG·새 AppData/userData·native 화면 1개다. 제품 소스는 변경하지 않았다.

### 실행 순서와 검사 범위

추가 preload가 앱 실행 전 main world에 URL 호출 계측을 설치하고,
15초마다 CDP `Runtime.getHeapUsage`/`Memory.getDOMCounters`와 Electron 프로세스 지표를 읽었다.
활성 URL의 문자열·크기·시각만 보관하고 Blob/DOM 객체를 수집 목록에 남기지 않는다.
이 계측 부하와 30초 일반 파일 조회, 후반 USS 조회가 있으므로 이전 시험과 통제된 on/off 비교는 아니다.

첫 `diagnostic-01`은 도우미가 `app.whenReady` 이후 제품을 import해 제품의
`disableHardwareAcceleration` 사전 조건을 위반했다. backend/창 생성 전 실패였고,
해당 소유 Electron만 `app.quit`으로 정상 종료했다. 측정 helper exit 1/Electron exit 0,
fact 추가 0바이트/원본 해시 불변을 보존한다. 초기화 순서 회귀를 수정 전 실패→수정 후 통과로
확인한 새 v2 도우미만 `diagnostic-02`에 사용했다. 원래 도우미/실패 결과는 수정하지 않았다.

`diagnostic-02`는 session 97567에서 07:43:57 KST에 실제 exit 0이었다.
앱 준비 12,727.5ms, 준비 운전 120초+baseline 300초 뒤 GC 1회,
추가 300초 관측 뒤 GC 1회, 정상 종료 순서다. 기본 관측 중에는 강제 GC가 없다.
경계 probe 완료→GC 전 표본→GC 후 표본의 실제 순서를 검산했다.
외부 자원 145표본/CDP 49표본이며 baseline 자원은 61표본/300.0002286초다.
backend/collector의 baseline은 각각 고유 59표본/291.2425초로 최소 48개·240초를 만족하고,
선호 60개에는 한 개 부족했다. 후반 GC 구간을 baseline 표본으로 채우지 않았다.

### 관측 결과

각 구간의 증가는 첫/끝 20% 평균 차이이며 CDP는 구간별 21표본이다.
첫 GC 뒤 구간의 실제 CDP 창은 299.602초로, baseline 자원 계약과 구분한다.

| 지표 | baseline 120–420초 | 첫 GC 뒤 약 300초 |
| --- | ---: | ---: |
| renderer RSS 평균 변화 | +138.22 MiB | +24.22 MiB |
| JS 사용 heap 평균 변화 | +4.00 MiB | +2.84 MiB |
| DOM 노드 범위 | 744–834 | 744–814 |
| JS event listener 범위 | 386–426 | 386–418 |
| 활성 Blob URL / 바이트 | 모든 표본 1 / 1,910 | 모든 표본 1 / 1,910 |

첫 GC 뒤와 두 번째 GC 뒤를 비교하면 JS 사용 heap +789,488바이트(0.75 MiB),
RSS +1,302,528바이트(1.24 MiB), private commit +1,789,952바이트,
DOM 노드 -9개, listener 변화 0이다. 각 GC 전후 RSS는 27,836,416바이트와
31,924,224바이트 줄었다. 앱은 계속 수집/표시 중이었고 두 번째 GC 전후에도 새 이미지 한 번이
추가됐다. 정지한 동일 heap snapshot 비교나 모든 사용 메모리의 감소로 해석하지 않는다.

두 번째 GC 직후 URL 생성 2,636회/알려진 해제 2,635회/활성 1개,
순간 최대 활성 2개이며 이미지 load 오류는 0이다. 이 조건에서 계측한 URL 해제 호출 누락이나
DOM/listener의 지속 누적은 관찰되지 않았다. URL 해제 호출 균형은 Blink 내부 이미지 캐시까지
전부 회수됐다는 증거가 아니다. 회수 가능한 메모리의 기여를 확인했으나 초기 RSS 증가 전체의
귀속·장기 plateau·누수 부재는 미확정이다.

USS는 준비 기준 330–720초의 14표본만 수집했다(session 33810, exit 0).
첫 GC 이후 10표본/270초에서 96,268,288–124,882,944바이트였고 조회 최대 11.34ms였다.
별도 07:36:10 표본의 RSS 530,235,392/USS 104,079,360바이트도 보존한다.
전체 초기 창 또는 모든 프로세스의 물리 고유 메모리를 측정한 것은 아니다.

소유 7프로세스의 일반 파일 열거는 각각 30초 간격 25표본, 오류 0이었다.
renderer 16개 고정, main 43–48개, 큰 backend Python 8–9개였다.
개별 조회 최대 163.36ms로 계측 자체 부하를 포함하며 Windows의 모든 file handle 목록을 보장하지 않는다.
기본 `resource-review.json`의 inherited `open_file_count_trend=NOT_MEASURED`와 별도로
추가 부분 관측은 `diagnostic-review.json`에 있다. 전체 5초 계약 충족으로 확대하지 않는다.

Electron MemoryInfo 값은 [공식 단위](https://www.electronjs.org/docs/latest/api/structures/memory-info)에 따라
KB에서 바이트로 환산했다. 별도 psutil memory_maps의 `rss` 이름 필드는
[7.2.2 Windows 구현](https://raw.githubusercontent.com/giampaolo/psutil/release-7.2.2/psutil/arch/windows/proc.c)에서
`RegionSize`를 반환하므로 라이브러리별 실제 상주 메모리로 해석하지 않았다.

### HTTP·저장·종료와 검증

계획 요청 804개는 모두 성공했고 health 364개 최대 34.6114ms, data 122개 최대 26.1719ms,
이미지 73개 최대 33.1047ms였다. health 시작 간격은 1.9988413–2.0006632초로 비중첩이다.
baseline CPU는 기계 용량 기준 2.344–3.906%, CSV queue 최대 1/5,000·drop 0이었다.
새 CSV 2,867행·이미지 662개, 원래 fact prefix와 같은 세대의 정상 종료를 독립 검산했다.
최종 fact 4,144,957행/2,124,148,345바이트,
SHA256 `618bdafbe2cbbbdb1617b0ff1fd1d4e4cfd87e6fefa82efc56950ade5ce0677d`다.
종료 시작 뒤 이미지 502 한 건은 이번에도 남았으며 계획 요청 오류 0과 구분한다.

Node 회귀 2개·Python 회귀 1개·실제 Electron smoke 1개, Ruff F/Node 문법 검사,
HTTP/저장 및 renderer 독립 검산·원본/현재 소스 대조는 모두 최종 exit 0이었다.
제품 소스가 그대로여서 전체 health는 반복하지 않았다. 화면은 Running/합성 이미지/작업 정보
미입력 상태를 확인했으며 실제 장비/작업번호/업무 화면 QA 통과가 아니다.

후속은 Blink `webFrame.getResourceUsage()`로 이미지/기타 캐시를 분리하고,
동일 JPEG의 URL 교체·해제 패턴을 별도 격리 fixture에서 대조하는 것이다.
원인 확인 없이 제품에 주기적 GC나 캐시 삭제를 추가하지 않는다.
동일 브라우저 1/3탭·통제된 계측 off·LCP/CLS·이미지 실제 표시·현장 시작 및 최종 clean
미서명 패키지/설치/복구/QA/15분/120분 조건이 남아 있으며 전체 목표 active/R1–R6 HOLD다.

### 후속 진단 증거 보존

session 33021의 공유 보존은 07:48:43 KST 실제 exit 0이었다.
입력 2,954파일/2,572,377,487바이트와 manifest를 ZIP 2,955 member로 검증했다.
개별 내용·원본 최종 목록/해시 및 로컬/공유 ZIP 바이트 일치를 확인했다.
공유는 `Z:/SmartFactory/20261013/records/PDCA_RENDERER_GROWTH_e3a1a8e0`의
`evidence.zip`, `evidence-manifest.json`, `seal-receipt.json` 3파일이다.
로컬 ZIP은 `C:/Users/user/Desktop/SmartFactory/PDCA_SERVER_IMAGES_20261013_43ef972a/PDCA_RENDERER_GROWTH_e3a1a8e0.zip`이다.

- ZIP 424,567,605바이트, SHA256
  `dc188e2eaab9a382f505181d7b999be8f9342680d9a6009ec1d5a4bef5626375`.
- manifest SHA256:
  `9f81e17c0c249d032d04395f196404ab647b9a1656978b8cda1d4290e972fc43`.
- 기본 스트림 검증이며 NTFS 추가 스트림 검증은 아니다. 원문 실패·부분 측정·예외도 보존했다.

<a id="image-cache-comparison-20261013"></a>

## 2026-10-13 08:16 KST 이미지 URL 교체·캐시 격리 비교

작은 격리 화면에서도 새 Blob URL을 반복 교체하는 조건의 RSS 증가가 재현됐다.
다만 고유 상주 메모리(USS)와 private commit 증가는 재사용 조건과 비슷했고,
Blink 이미지 캐시 항목 수·활성 URL은 둘 다 1개였다. 이 결과로 제품의 누수나
직전 전체 앱 RSS 증가 +138.22 MiB의 원인을 확정하지 않는다.

근거는 `C:/Users/user/Desktop/SmartFactory/PDCA_IMAGE_CACHE_20261013_b86fe19e`의
`RESULT.md`, 두 `runs/*-01/review.json`, 원시 `samples.jsonl`/`external.jsonl`,
`interventions.json` 및 `final-verification.json`이다.

### 고정 조건과 관측

앞선 봉인 묶음의 동일 1,910바이트 JPEG와 계측 도우미를 manifest 해시와 대조해 복사했다.
같은 Electron 44.3.0/Chromium 152.0.7977.78·소프트웨어 렌더링·250ms load 후 timer,
새 process/userData·1280×800 창·488×418 이미지 영역을 사용했다.
`replace`는 매 프레임 새 URL을 만들고 다음 load 후 이전 URL을 해제했다.
`reuse`는 새 Blob 할당은 동일하게 수행하되 첫 URL을 계속 사용했다.
두 조건 모두 1,619프레임, 이미지 오류 0, 연결 DOM 요소 10개였다.

두 실제 실행 session 22723/72861은 각각 08:07:24/08:14:36 KST에 helper exit 0이었다.
Electron도 exit 0이며 각 소유 4개 PID/생성 시각의 정상 종료와 최종 도우미 해시를 확인했다.
각 120초 준비+300초 관측, 전체 85표본/관측 61표본이고 실제 관측 폭은
300.0072648/299.9967457초다. 외부 USS 관측은 각 60표본/약 295초,
main 시행의 조회 오류 0, 개별 조회 최대 21.8244/35.1473ms다.

변화량은 첫/끝 20% 평균 차이이며 RSS/heap은 각 13표본, USS는 각 12표본이다.

| 관측 지표 | URL 교체 | URL 재사용 |
| --- | ---: | ---: |
| renderer RSS 변화 | +58.65 MiB | +3.73 MiB |
| renderer USS 변화 | +3.05 MiB | +3.67 MiB |
| renderer private commit 변화 | +3.49 MiB | +3.70 MiB |
| JS 사용 heap 변화 | -0.16 MiB | -0.20 MiB |
| 이미지 캐시 항목 / 활성 URL | 모두 1 / 1 | 모두 1 / 1 |
| 이미지 캐시 size | 6,560–334,240바이트 | 334,240바이트 고정 |

교체 조건은 URL 생성 1,619/해제 1,618/순간 최대 활성 2개이고 미확인 해제 0이었다.
재사용은 생성 1/해제 0/최대 활성 1이다. CDP DOM 노드 수에는 매 load의 카운터 갱신으로
생기는 분리된 text node가 포함됐다. 기본 관측 중 명시적 GC/캐시 삭제는 없었고,
별도 GC 후에는 두 조건 모두 노드 21개·document 1개·listener 4개가 됐다.
이 fixture의 카운터 현상을 제품의 DOM 결함으로 판단하지 않는다.

### 별도 개입과 해석 범위

관측 후 timer를 멈추고 마지막 이미지를 유지한 상태에서 GC→캐시 삭제를 순서대로 실행했다.
교체 RSS는 190,779,392→189,022,208→188,297,216바이트,
재사용은 81,166,336→80,838,656→80,465,920바이트였다.
캐시 삭제 후 두 조건의 이미지/script 캐시 수는 0이었지만 교체 RSS가 재사용 수준으로
돌아오지는 않았다. 고정 순서의 개입으로, 각 효과가 독립적으로 분리됐다는 뜻은 아니다.
RSS와 USS 차이를 특정 DLL·이미지 버퍼·물리 공유 페이지의 원인으로 귀속하지 않는다.

`getResourceUsage`는 [Blink 내부 캐시](https://www.electronjs.org/docs/latest/api/web-frame)만 보고한다.
44.3.0의 `liveSize`는 [변환 코드](https://raw.githubusercontent.com/electron/electron/v44.3.0/shell/common/gin_converters/blink_converter.cc)에서
`decoded_size`에 대응하며 전체 살아 있는 객체의 메모리가 아니다.
단위·원문 출처는 `MEASUREMENT_NOTES.md`와 함께 보존했다.

이 시험은 조건별 1회 순차 실행, 숨겨진 창(`show=false`, `backgroundThrottling=false`),
동일 JPEG, 작은 DOM이며 React/backend/HTTP/저장 부하는 없다.
실제 `visibilityState=visible`은 사용자에게 픽셀이 표시됐다는 증거가 아니다.
그리기·decode 경로와 OS 상태/실행 순서 차이, 전체 앱 원인·장기 안정성은 미확인이다.
다음은 실제 상주 페이지 종류의 구분과 보이는 전체 앱의 캐시/그리기 관찰이다.
확인되지 않은 원인에 맞춰 제품 URL 재사용·주기적 GC·캐시 삭제를 추가하지 않았다.

### 검증과 보존

native smoke 2회, 검산 회귀 1개, 두 원시 결과 검산, 별도 RSS 산술/수량 검산,
최종 Ruff F·Node 문법 검사가 모두 실제 exit 0이었다.
초기 검산 모듈 부재의 실패와 잘못된 Ruff 디렉터리 검색은 기록했고,
최종 검사는 명시적 파일 목록으로 통과했다. smoke 재사용의 종료 시점 프로세스 조회 경합
1건도 보존했다. 주 시행은 해당 조회 오류가 없다.
건강 검사에 결합된 8개 해시·제품 Git diff·문서 외 untracked 6개 해시·HEAD가 그대로여서
전체 health는 반복하지 않았다. 제품/서버/설치본/운영·롤백 기준은 변경하지 않았다.

공유 보존은 08:15:50 KST 실제 exit 0이며 입력 284파일/125,342,161바이트,
ZIP 285 member의 개별 내용·최종 원본 해시 및 로컬/공유 ZIP 일치를 확인했다.
공유 `Z:/SmartFactory/20261013/records/PDCA_IMAGE_CACHE_b86fe19e`에
`evidence.zip`, `evidence-manifest.json`, `seal-receipt.json`을 보존했다.
로컬 ZIP은 `C:/Users/user/Desktop/SmartFactory/PDCA_SERVER_IMAGES_20261013_43ef972a/PDCA_IMAGE_CACHE_b86fe19e.zip`이다.

- ZIP 7,684,796바이트 / SHA256 `fc468ff460a89e40a177e18dd8e1940186958a636ca303ccb0df966c080a8a79`.
- manifest SHA256 `1c759261293fbec85f9da177d72c7dba6736eacb164676874dfef68c1c7fc048`.
- 제외 항목 0. 기본 스트림 검증이며 NTFS 추가 스트림 검증은 아니다.

전체 목표 active, full_data_gate=NOT_EVALUATED, R1–R6 HOLD를 유지한다.
동일 브라우저 1/3탭·계측 off·실제 표시/현장 성능·최종 clean 미서명 설치본 QA는 남아 있다.

<a id="resident-page-attribution-20261013"></a>

## 2026-10-13 08:42 KST renderer 상주 페이지 종류 대조

실행 순서를 재사용→교체로 바꾼 반복 시험에서도 RSS 차이가 재현됐다.
별도 상주 페이지의 두 시점 대조에서 교체 조건 증가량의 **90.43%가 MEM_MAPPED이며,
그 순증가 페이지는 Shared=true/ShareCount>1**이었다. 매핑을 만든 Chromium 객체와
전체 앱 증가의 원인은 아직 미확정이다. 공유 메모리라는 이유로 비용이 없거나 누수가
아니라고 판단하지 않으며 전체 R1–R6 HOLD를 유지한다.

근거 묶음은 `C:/Users/user/Desktop/SmartFactory/PDCA_RESIDENT_PAGES_20261013_82cbe395`다.
`RESULT.md`, `comparison.json`, `runs/*-01/resident-review.json`과 raw working-set
버퍼/영역 원장을 보존했다. 앞 단계의 검증된 기준 도우미 12파일도 원래 바이트로 포함했다.

### 반복 실행과 자원 관측

같은 JPEG/Electron 44.3.0/소프트웨어 렌더링/숨겨진 창/250ms load 후 timer를 사용했다.
재사용 session 99647과 교체 session 39795는 각각 08:31:32/08:39:19 KST에 실제 exit 0이었다.
각 Electron도 exit 0, 1,618프레임·이미지 오류 0·소유 4프로세스의 정상 종료를 확인했다.
main stderr는 비어 있었다. 각 120초 준비+300초 관측, 전체 85/관측 61표본이며
실제 관측 폭은 299.9962246/299.9926084초다. 외부 USS는 각 60표본/약 295초였다.

| 첫/끝 20% 평균 변화 | URL 재사용 | URL 교체 |
| --- | ---: | ---: |
| renderer RSS | +3.95 MiB | +60.13 MiB |
| renderer USS | +3.71 MiB | +3.42 MiB |

RSS는 각 끝 13표본, USS는 각 끝 12표본이다. 활성 URL·이미지 캐시 항목은 모두 1개,
연결 DOM 요소는 모두 10개였다. 교체 URL 생성/해제는 1,618/1,617, 순간 최대 2개다.
원래 순서의 +58.65/+3.73 MiB와 같은 방향이지만 전체 앱/실제 표시 성능 통과는 아니다.

### 상주 페이지 정산과 귀속 범위

각 시행에서 실제 약 4.7/124.7/404.7초, timer 정지·GC·캐시 삭제 후 약 9.05/29.05초에
다섯 번 조회했다. [QueryWorkingSet](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-queryworkingset)의
페이지 주소/속성과 [VirtualQueryEx](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualqueryex)의
종류를 연결했으며 **반환된 상주 페이지 수×4,096바이트**로 정산했다. 가상 RegionSize를
RSS로 합산하지 않았다. 주 시행 10개 표본의 반환 페이지 전부를 중복 없이 대조했고
미분류 allocation type은 0이었다. 내용 바이트를 읽거나 프로세스를 정지시키지 않았다.

아래는 약 125→405초, 약 280초 간격의 **두 표본 차이**다. 위 300초 평균 변화와 구분한다.

| 상주 바이트 변화 | 재사용 | 교체 |
| --- | ---: | ---: |
| 반환된 전체 상주 페이지 | +5,009,408 | +77,377,536 |
| MEM_PRIVATE 영역 | +4,431,872 | +5,521,408 |
| MEM_MAPPED 영역 | +53,248 | +69,971,968 |
| MEM_IMAGE 영역 | +524,288 | +1,884,160 |
| USS 규칙 해당 페이지 | +4,435,968 | +5,525,504 |

MEM_MAPPED는 교체 증가량의 90.4293%이며 해당 순증가의 USS 규칙 바이트는 0이었다.
USS 규칙은 확인한 psutil 7.2.2 구현의 `!Shared 또는 ShareCount<=1`이다.
allocation type과 실제 공유 속성은 별도로 보존했다. ShareCount는 7에서 포화되며
물리 페이지 식별자를 얻은 것이 아니므로 전체 앱의 물리 메모리를 중복 제거할 수 없다.

파일명이 반환되지 않은 매핑 그룹(Windows 오류 1006 보존)은 70,230,016바이트 늘었고,
다른 매핑의 감소를 합치면 위 순증가량이 된다. 파일명 미확인·가상 영역 크기
4,198,400바이트인 매핑 수는 교체에서 11→29개, 재사용에서 1→1개였다.
관측된 크기 패턴은 정확한 Chromium 152.0.7977.78 소스의
[4 MiB discardable 할당](https://raw.githubusercontent.com/chromium/chromium/152.0.7977.78/components/discardable_memory/client/client_discardable_shared_memory_manager.cc)과
[페이지 정렬한 공유 헤더](https://raw.githubusercontent.com/chromium/chromium/152.0.7977.78/base/memory/discardable_shared_memory.cc)에 맞는다.
이미지 decode가 이 할당기를 사용하는 경로도 확인했지만, 이는 **원인 후보**이며 실제
매핑의 객체 식별은 아니다. 원문/해시는 묶음의 `chromium-source`와 `NOTES.md`에 있다.

정지·GC·캐시 삭제 후 두 후속 표본에서 교체 상주 합계는 187,121,664바이트,
MEM_MAPPED 106,487,808바이트와 해당 크기 매핑 26개가 같았다.
재사용은 상주 80,732,160/MEM_MAPPED 6,709,248바이트였다.
20초 동안의 동일 값 관찰이며 장기 plateau·128 MiB 상한·누수 부재를 입증하지 않는다.

페이지 규칙의 USS는 주변 psutil USS와 주 시행 10개 모두 일치했다.
목록 합계는 psutil RSS보다 재사용 69,632바이트/교체 73,728바이트 작았고 원인은 미확정이다.
목록·영역·파일명·psutil 조회가 한 시점의 atomic snapshot은 아니라는 제한도 유지한다.
전체 조회/분류 최대 시간은 재사용 31.158ms, 교체 74.3833ms였다.
일반 psutil 조회 오류 0과 파일명 조회 실패 1006을 구분하며 실패를 지우지 않았다.

### 검증·보존 및 다음 단계

전용/파일 매핑 1 MiB씩의 native 자기 시험, Electron smoke(16프레임), Python 회귀 2개,
두 시행의 자원·상주 페이지·시각 검산, 최종 Ruff F/Node 문법 검사는 실제 exit 0이었다.
초기 모듈 부재와 시험의 정렬 순서 가정 실패도 원문으로 보존했다.
8개 health 결합 해시·제품 diff·문서 외 untracked 6개·HEAD가 그대로여서 전체 health는
재실행하지 않았다. 제품/서버·설치본·운영/롤백 기준을 변경하지 않았다.

공유 보존은 08:41:20 KST 실제 exit 0, 입력 280파일/102,144,418바이트,
ZIP 281 member의 내용·원본 최종 목록/해시 및 로컬/공유 ZIP 일치를 확인했다.
공유 `Z:/SmartFactory/20261013/records/PDCA_RESIDENT_PAGES_82cbe395`에 3파일을 보존했다.
로컬 ZIP은 `C:/Users/user/Desktop/SmartFactory/PDCA_SERVER_IMAGES_20261013_43ef972a/PDCA_RESIDENT_PAGES_82cbe395.zip`이다.

- ZIP 6,554,651바이트 / SHA256 `48a887159cd038738b25d47a4af516cd6646bfcee82e3073094ced66127ade22`.
- manifest SHA256 `718beb6b2a989df07483128066d1f73e2e91703c07b8e3db61c2bfad596eb979`.
- 제외 항목 0. 기본 스트림 검증이며 NTFS 추가 스트림 검증은 아니다.

다음은 Chromium memory-infra의 할당기 이름/소유 관계로 후보를 대조하고, 보이는 전체 앱의
메모리·표시를 관찰하는 것이다. 제품에 주기적 GC/캐시 삭제를 추가하지 않았다.
전체 목표 active, full_data_gate=NOT_EVALUATED 및 R1–R6 HOLD를 유지한다.

<a id="memory-infra-attribution-20261013"></a>

## 2026-10-13 Chromium 할당기 대조와 전체 앱 표시 조건 미충족

작은 JPEG 시험에서는 `cc/image_memory`의 이미지 항목이 `discardable` 메모리를
소유하는 관계를 실제 Chromium trace에서 확인했다. 3개 dump의 이미지 캐시 크기는
1,314,816 → 1,642,496 → 1,970,176바이트였다. 정상 종료와 소유 프로세스 5개 종료를
확인했다. 이는 앞선 매핑 패턴 후보를 뒷받침하지만 실제 물리 페이지 객체의 동일성이나
전체 앱 RSS 증가의 원인 전부를 입증하지 않는다.

### 실제 규모 사본의 수집 결과와 비교 제외 사유

현재 저장소와 일치하는 runtime 125파일, 닫힌 CSV 340,304,366바이트,
fact 2,124,148,345바이트의 새 사본으로 전체 앱을 실행했다. 준비 완료 12,779.5ms,
120초 준비+300초 관측, 자원 85표본(관측 61표본/300.0065337초), renderer 29표본과
두 개의 3.2초 trace를 수집했다. 계측 수집·정상 종료 helper는 실제 exit 0이었다.

그러나 첫 표본만 `visible`이고 약 15초의 index 3부터 나머지 28표본은 `hidden`이었다.
최종 native 창도 `isVisible=false`, 관측 시작/끝의 이미지 표시 횟수는 모두 39였다.
캡처에는 STALE 표시가 있었으며, 캡처 이미지 생성 자체는 실제 화면 갱신의 증명이 아니다.
누가 또는 무엇이 창을 숨겼는지는 확인되지 않았다. **visible_workload_valid=false**로
판정하여 보이는 전체 앱의 성능 비교에서 제외한다. 이 조건의 RSS 평균 감소
153,994,791.38바이트를 개선·장기 안정성·누수 해소 또는 R2 통과로 해석하지 않는다.

첫 전체 앱 trace의 이미지 캐시는 36,651,008바이트이고 모든 이미지 leaf의
discardable 소유 관계가 확인됐다. 42개 leaf는 327,680바이트 39개와
262,144/24,576/23,584,768바이트 각 1개였다. 두 번째 trace는 같은 수의 leaf를
기록했으나 크기 속성과 소유 edge를 보고하지 않았다. 이 값은 **미보고**로 보존하며
0으로 채우거나 완전한 캐시 크기 감소량을 계산하지 않는다. 원시 trace 버퍼 사용률은
각각 0.0206967853/0.01938982494였고 파일은 정상적으로 닫혀 JSON으로 읽혔다.

### 저장·종료 검산과 분석기 보완

계획한 HTTP 474회는 모두 200/완전한 본문/해시·JSON·JPEG 검산을 통과했다.
health 214회의 최대 53.6687ms, p95 23.5871ms였다. 새 CSV 1,897행의 순서와
이미지 53개의 크기·해시·디코딩, 원래 fact 접두부 보존을 확인했다.
CSV 대기열 최대 1/5000·drop 0, 같은 세대의 정상 종료와 소유 PID/생성 시각 8쌍의
종료를 검산했다. 새 fact는 4,145,010행/2,124,175,210바이트,
SHA256 `8440a1a3d7532e15c9908329247ba210d75c2de8163aafdc1fda7dc4f44bbb63`다.
이 저장 결과는 위 표시 조건 실패를 통과로 바꾸지 않는다.

첫 분석기는 미보고 `size`에서 실제 exit 1로 중단됐다. 원문 로그·종료 영수증과
기존 해시가 일치하는 초기 분석기 바이트를 보존했다. 미보고 값을 unknown으로
취급하는 회귀를 추가했고 최종 4개 시험과 수정 분석기는 exit 0이었다.
자원/저장 검산·소스 검산·Ruff F·Node 문법 3개도 exit 0이었다.
8개 health 결합 입력·6개 문서 외 untracked·제품 diff·HEAD가 그대로여서 전체 health는
반복하지 않았다. 제품 소스·서버·설치본·운영/롤백 기준 변경은 없다.

### 보존과 다음 확인

로컬 근거는 [RESULT.md](C:/Users/user/Desktop/SmartFactory/PDCA_MEMORY_INFRA_20261013_68ae47b2/RESULT.md),
[전체 trace 검산](C:/Users/user/Desktop/SmartFactory/PDCA_MEMORY_INFRA_20261013_68ae47b2/full-trace-review.json),
[저장 검산](C:/Users/user/Desktop/SmartFactory/PDCA_MEMORY_INFRA_20261013_68ae47b2/resource-review.json)에 있다.
공유 위치는 `Z:/SmartFactory/20261013/records/PDCA_MEMORY_INFRA_68ae47b2`다.
입력 1,509파일/2,576,817,679바이트와
ZIP 1,510 member를 검산했고 공유 3파일을 보존했다.
로컬 ZIP은 `C:/Users/user/Desktop/SmartFactory/PDCA_SERVER_IMAGES_20261013_43ef972a/PDCA_MEMORY_INFRA_68ae47b2.zip`이다.

- ZIP 423,897,740바이트 / SHA256 `a58dcb22b89060966753475b475609e345685ad1f09450b4f1cf428feb6c738c`.
- manifest SHA256 `fc9789a1af771fe501eb1de35f4bd32e52b083be4daa86f78f7020c38d67367e`.
- 모든 ZIP 내용, 원본 최종 목록/해시와 로컬·공유 ZIP 일치를 확인했다. 기본 스트림 범위이며 추가 스트림 검증은 아니다.

다음 비교는 show/hide/minimize와 page visibility를 실행 초기에 기록하고,
실제 프레임 갱신을 준비 구간에서 검증해야 한다. 조건이 깨지면 정상 종료로 조기 중단한다.
계측용 렌더링 조건을 변경하면 제품 기본 동작·정식 R2와 구분한다.
[Electron 표시 상태 문서](https://www.electronjs.org/docs/latest/api/browser-window#page-visibility)에 따르면
backgroundThrottling을 끄면 실제 창이 숨겨져도 page visibility가 visible일 수 있으므로,
해당 옵션만으로 표시 조건 통과를 만들지 않고 native 상태도 함께 검증한다.
전체 목표 active, full_data_gate=NOT_EVALUATED 및 R1–R6 HOLD를 유지한다.

<a id="visible-app-cache-growth-20261013"></a>

## 2026-10-13 표시 조건을 유지한 전체 앱의 이미지 캐시 증가 확인

실제 규모 사본의 전체 앱을 표시한 상태에서 이미지 디코딩 캐시가 RSS 증가에
기여한다는 근거를 확보했다. 같은 renderer PID 46140과 같은 캐시 인스턴스의
첫 trace에서 `cc/image_memory`는 171,982,848바이트/455항목이었고,
약 300초 뒤 trace의 세 dump 모두 327,680,000바이트/1,000항목이었다.
종료 측 1,000항목은 각각 327,680바이트(320×256×4)였다. 여섯 dump 모두
이미지 leaf의 크기와 discardable 소유 관계를 보고했다.

캐시 논리 크기는 155,697,152바이트(148.484375MiB) 증가했다. 관측 구간의
renderer RSS 처음/마지막 20% 평균 차이는 130,289,348.923바이트(약 124.25MiB),
사용 JS heap 평균 차이는 3,190,720.8바이트(약 3.04MiB)였다.
활성 Blob URL은 1개/최대 2개, 알 수 없는 revoke 0회, 연결된 element 502개였다.
캐시와 discardable은 backing 메모리를 공유하므로 두 크기를 더하지 않는다.
논리 할당과 RSS는 집계 방식·표본 시점이 달라 모든 상주 바이트의 원인 비율로
해석하지 않는다. 누수 부재·장기 안정성·제품 수정 완료 또는 R2 통과 판정도 아니다.

정확한 Chromium 152.0.7977.78 소스의 기본 디코딩 캐시 항목 수는 1,000이며,
참조 중인 항목은 퇴출 시 건너뛴다. discardable 정리의 나이 조건 5분/주기 1분과
내부 보편 용량 제한 부재를 확인했다. 약 2초 동안 같은 종료 dump 세 개를
장기 plateau나 고정 RSS 상한으로 해석하지 않는다. 출처 사본과 해시는
[REFERENCES.md](C:/Users/user/Desktop/SmartFactory/PDCA_VISIBLE_TRACE_20261013_7fe1a964/REFERENCES.md)에 있다.

### 실행 조건과 저장·종료 검산

- `visible-02`: 준비 완료 12,834ms, 120초 준비+300초 관측, 자원 85표본 중
  관측 61표본/299.990054초. renderer 29표본과 활성 native 기록 440개가 모두
  visible/non-minimized였고 이미지 표시 횟수는 9→1,534, 오류 0이었다.
  backgroundThrottling/page visibility를 강제 변경하지 않았다.
- 계획한 HTTP 472회는 모두 200/완전한 본문/해시·JSON·JPEG 검산 통과.
  health 213회 최대 30.402ms/p95 25.033ms, data 최대 26.1707ms,
  표본 image 최대 49.7243ms였다. backend/collector 고유 60표본을 확보했다.
- 새 CSV 1,759행의 sample ID 연속성과 이미지 392개의 크기·해시·디코딩을 검산했다.
  CSV queue 최대 1/5000, drop 0. 최종 fact 4,145,408행/2,124,377,355바이트,
  SHA256 `0a1b156c97dc93f7ba2c7a0d70f121803d3e96ddfb771ea9a38457f79a280741`.
  실행 전 fact 접두부, 같은 세대 backend/Electron 정상 종료 및 소유 PID/생성 시각
  8쌍의 종료를 확인했다. 파일 열거 오류는 0이었다.
- 정상 종료 시작 뒤 UI 이미지 요청 1회는 502였다. 같은 요청의 로그 두 줄을 보존하며
  계획한 472회와 구분한다. 전체 HTTP 오류 0으로 보고하지 않는다.
- 최종 화면은 Running/SPOT OK/Temp OK였지만 격리 fixture의 작업 정보는 공란이었다.
  합성 이미지·읽기는 실제 장비 모델/설정·운영자 검증을 대신하지 않는다.

### 준비 실패와 계측 한계 보존

초기 C: 여유 약 1.9GB로 새 입력/로그 폴더에만 NTFS 압축을 적용했다.
완료된 사본 141파일은 논리 2,469,271,237바이트/할당 928,013,677바이트이고
원본 해시가 일치했다. runtime 125파일은 현 저장소와 일치한다.
압축은 디스크 I/O 조건을 바꾸므로 비압축 성능 수용 증거로 사용하지 않는다.
이후 여유 공간 증가 원인은 미확정이며 이 작업에서 삭제·이동은 하지 않았다.

첫 압축 probe는 flush 전 할당량 assertion으로 exit 1이었고 당시 반환값은
기록되지 않았다. 이후 1MiB 파일의 할당 131,072바이트와 명시적 flush probe 통과를
확인했다. 최초 원인이 write-behind라는 설명은 추론으로 남긴다.
첫 복사는 예약 여유 공간 조건으로 exit 1이었으며 부분 fact 268,435,456바이트와
원본 접두부 해시 일치를 보존했다. 성공 준비는 새 `trial` 폴더를 사용했다.

첫 `visible-01` 수집은 broad glob이 probe 등록 metadata까지 선택해 exit 1,
Electron은 정상 exit 0이었다. 원래 도우미·오류와 새 CSV 83행/이미지 6개,
접두부 보존·정상 종료를 검산했다. 숫자 probe 파일 선택 회귀를 보완한
`visible-02`는 새 출력/프로필과 검산된 현재 격리 AppData를 사용해 정상 재시작했다.
기준 데이터를 되돌리거나 이전 증거를 덮어쓰지 않았다.

native guard 4시나리오·실제 Electron show/hide smoke·workload 회귀 4개·파일 선택
회귀 1개가 통과했다. 최종 Python AST 25파일·Ruff F·자원/trace/소스 검산은 exit 0이다.
8개 health 입력과 6개 문서 외 untracked·제품 diff·HEAD가 그대로여서 전체 health는
반복하지 않았다. 제품 소스·서버·설치본·운영/롤백 기준 변경은 없다.

### 근거 보존과 후속 범위

[결과](C:/Users/user/Desktop/SmartFactory/PDCA_VISIBLE_TRACE_20261013_7fe1a964/RESULT.md),
[trace 검산](C:/Users/user/Desktop/SmartFactory/PDCA_VISIBLE_TRACE_20261013_7fe1a964/trial/full-trace-review.json),
[저장 검산](C:/Users/user/Desktop/SmartFactory/PDCA_VISIBLE_TRACE_20261013_7fe1a964/trial/resource-review.json),
[최종 정적 검산](C:/Users/user/Desktop/SmartFactory/PDCA_VISIBLE_TRACE_20261013_7fe1a964/trial/final-verification.json)을 보존했다.
입력 2,103파일/3,224,041,197바이트,
ZIP 2,104개 항목의 내용과 최종 원본 해시를 대조했다.
공유 `Z:/SmartFactory/20261013/records/PDCA_VISIBLE_TRACE_7fe1a964`의 3파일과
로컬 ZIP을 확인했으며 보존 helper 실제 exit 0이다. 기본 스트림 범위이며 ADS 검산은 아니다.

- ZIP 501,609,715바이트 / SHA256 `b416f9431f7f5c69437492ceb88322bc86ee6b0c959ca2222f63fca0ee5d2f42`.
- manifest SHA256 `c6cf95f5e832e8bc95b5ab97597b80f81f8125f1d78994d9d08a57b5bb266ddb`.
- 로컬 ZIP: `C:/Users/user/Desktop/SmartFactory/PDCA_SERVER_IMAGES_20261013_43ef972a/PDCA_VISIBLE_TRACE_7fe1a964.zip`.

전체 앱 표시 조건을 충족한 캐시 기여 확인 단계는 끝났다. 다음은 요구된 동일 브라우저의
1개/3개 탭 비교와 memory-infra/CDP를 끈 표시 성능, 별도의 비압축 I/O 조건 확인이다.
반복 GC·캐시 강제 비우기를 제품에 추가하지 않는다. 미서명 내부 운영 정책을 유지하고
전체 목표 active, full_data_gate=NOT_EVALUATED 및 R1–R6 HOLD를 유지한다.

<a id="same-browser-one-three-tabs-20261013"></a>

## 2026-10-13 같은 브라우저의 1개·3개 탭 비교 완료

사용자가 개발 PC의 시험 창을 약 15분간 유지할 수 있다고 확인한 뒤, 같은 초기 데이터의
비압축 사본과 새 프로필로 1개 탭 → 3개 탭 순서의 격리 비교를 완료했다.
Chromium 148.0.7778.96/Playwright 1.60.0/web-vitals 2.1.4, 창 1300×900,
실제 viewport 1284×749/DPR 1이었다. 각 조건은 브라우저 창·context 각각 1개였다.
125 runtime 파일이 현재 저장소와 일치했고, CSV 340,304,366바이트 및
fact 4,145,408행/2,124,377,355바이트의 시작 내용이 동일했다.

각각 120초 준비+300초 관측, 자원 85표본 중 관측 61표본,
backend/collector 고유 표본 각각 60개를 확보했다. 모든 측정 탭은 처음부터 visible로
로드됐다. 3개 탭은 관측 내내 전면 1개·숨김 2개이며 같은 native window ID였다.
29개 브라우저 표본으로 확인했다. 백그라운드 두 탭의 이미지 표시 횟수는 9에 머물렀고
전면 탭만 갱신됐다. 세 화면을 동시에 전면 렌더링한 부하 시험으로 확대 해석하지 않는다.

| 지표 | 1개 탭 | 3개 탭 |
| --- | ---: | ---: |
| 계획한 HTTP 전체 검산 | 477회/실패 0 | 503회/실패 0 |
| 외부 health 첫 응답/최대, ms | 16.5016/30.5529 | 32.6794/32.6794 |
| 외부 health p50/p95/p99, ms | 4.6924/19.9269/27.7504 | 4.7965/25.3042/29.2821 |
| 브라우저 health 횟수/최대, ms | 212/36.265 | 214/12.953 |
| data 최대, ms | 25.2975 | 26.5446 |
| 표본 이미지 최대, ms | 30.4846 | 25.1845 |
| 탭별 LCP, ms | 1512 | 1448/448/384 |
| 탭별 CLS | 0.0216166 | 0.0058610/0/0.0022489 |
| 관측 실제 길이, 초 | 299.995366 | 299.9930062 |
| 프로세스 RSS 합계 처음/마지막 20% 평균 증가, MiB | 107.6553 | 123.3507 |
| 마지막 20% RSS 합계 평균, GiB | 3.15433 | 3.45311 |
| CPU 범위, 12논리 CPU 용량 대비 % | 2.1892–7.6354 | 1.5400–10.4331 |
| 새 CSV 행/이미지 검산 | 2,041/389 | 2,178/391 |
| 종료 확인한 소유 PID/생성 시각 쌍 | 12 | 14 |

계획한 요청의 200 응답·완전한 본문·해시·JSON/JPEG를 확인했다. health/data/image의
외부 경고 초과는 0이며 브라우저 health도 200ms 초과·오류가 없었다.
LCP/CLS는 목표 2500ms/0.1 및 실패 상한 4000ms/0.25 이내였다.
같은 프로필의 후속 탭이므로 짧은 후속 LCP를 탭 수 증가의 성능 개선으로 해석하지 않는다.
각 조건 1회이며 순서·OS 캐시 조건을 통계적으로 통제한 인과 효과 추정은 아니다.

신규 격리 폴더에 저장된 active layout이 없어 `/api/layout`은 각각 404 2회/6회를
반환했다. 해당 API는 active layout 부재 시 명시적으로 404를 반환한다.
이를 성공 응답으로 바꾸지 않았으며 전체 브라우저 요청 4,416/4,518회에 보존했다.
캡처에는 Running/SPOT OK/Temp OK, 필수 작업 정보 공란과 일부 잘린 기본 위젯 내용이
보였다. 화면 배치·운영자·실장비 QA 통과로 보고하지 않는다.

CSV 대기열 최대 1/5000, drop 0이었다. 새 CSV sample ID 연속성, 같은 logger/spot
세대, 이미지별 경로·크기·SHA256·320×256 디코딩, 기존 fact 접두부와 전체 최종 해시를
검산했다. backend 정상 lifespan의 begin/final 해시·worker 종료와 실제 프로세스 종료를
대조했다. 최종 fact SHA256은 1개 탭
`56bebdc934ee3ea9cf609af447832925ca3dc0bb7f8f762c9742d4b5fc10af5d`,
3개 탭 `568c62af31285334270449249e83b55e27b2ad8201fd9cdcba83cb89a2e67e09`다.

### 계측 범위와 실패 기록

두 조건 모두 RSS 합계가 증가했다. 이는 고유 물리 메모리가 아니며 프로세스 I/O 카운터도
물리 디스크 처리량이 아니다. 해당 수치와 CPU 추세는 원시 검산에 남겼고 임의 상한으로
PASS를 만들지 않았다. 강제 GC·페이지 표시/포커스·백그라운드 throttling 우회는 없었다.
CDP 제어와 web-vitals/주기적 표본 수집은 활성 상태이므로 계측 OFF 비교는 남아 있다.
이 Chromium 148 측정을 앞선 Electron Chromium 152 trace와 직접적인 전후 비교로 쓰지 않는다.

포트 접근 거부, Playwright 기본 포커스 설정으로 숨김 탭이 visible로 보인 두 smoke,
격리 LOCALAPPDATA의 실행 파일 탐색 실패, warmup 중 실제 숨김으로 조기 종료된 실행을
원문 보존했다. native 실행+noDefaults 연결 smoke는 탭/창/표시/LCP/CLS 검사를 통과했다.
실패한 앱 두 실행의 CSV 5/114행·이미지 0/5개와 정상 backend 종료·접두부도 검산했다.
Computer Use 활성화 API의 창 소유자 오류와 잘못 적힌 한 begin-file 문구는 별도 정정
JSON으로 보존했다. 활성화 성공을 주장하지 않으며 실제 visibility 기록을 증거로 사용한다.
초기 분석기는 Windows venv launcher PID와 실제 backend PID를 같다고 가정해 실패했다.
수정본은 ready/exit/final lifespan/관측된 소유 프로세스의 실제 backend PID를 대조한다.
원래 분석기와 오류를 보존했고 최종 두 분석 및 최종 검산은 실제 exit 0이었다.

### 보존과 다음 단계

[실행 조건·결과](C:/Users/user/Desktop/SmartFactory/PDCA_BROWSER_TABS_20261013_9df08dc7/RESULT.md),
[1개 탭 검산](C:/Users/user/Desktop/SmartFactory/PDCA_BROWSER_TABS_20261013_9df08dc7/one-r3-review.json),
[3개 탭 검산](C:/Users/user/Desktop/SmartFactory/PDCA_BROWSER_TABS_20261013_9df08dc7/three-review.json),
[최종 검산](C:/Users/user/Desktop/SmartFactory/PDCA_BROWSER_TABS_20261013_9df08dc7/final-verification.json)을 보존했다.
138개 사본과 runtime 125파일, 동일 시작 fact·비압축 속성·Python AST·Node 문법·Ruff F를
확인했다. 8개 health 입력·문서 외 untracked 6개·제품 diff·HEAD가 같아 전체 health는
반복하지 않았다. 제품·서버·설치본·운영/롤백 기준은 바꾸지 않았다.

입력 4,599파일/8,993,103,400바이트와 ZIP
4,600개 항목을 전수 대조하고 공유 3파일을 보존했다.
공유 위치는 `Z:/SmartFactory/20261013/records/PDCA_BROWSER_TABS_9df08dc7`이다.

- ZIP 1,588,563,768바이트 / SHA256 `e70fbfc7c0d49f76de58ef23b1c49c8d7b8742ae51dec3a8ca1bca1269d30423`.
- manifest SHA256 `b380c5b1651b1a33dbba1651bb14691cf3ad91d73b25736947975624e35d343c`.
- 로컬 ZIP: `C:/Users/user/Desktop/SmartFactory/PDCA_SERVER_IMAGES_20261013_43ef972a/PDCA_BROWSER_TABS_9df08dc7.zip`.
- 모든 ZIP 내용·최종 원본 해시·공유 ZIP 동일성 검산 실제 exit 0. 기본 스트림 범위이며 ADS 검사는 아니다.

동일 브라우저 1개/3개 탭과 비압축 사본의 이번 비교는 완료됐다. 다음은 동일 조건의
계측 ON/OFF 및 필요한 물리 디스크 관측, 남은 실제 서버·최종 후보 검증이다.
미서명 내부 운영 정책과 전체 목표 active, R1–R6 HOLD, full_data_gate=NOT_EVALUATED를 유지한다.


<a id="supplemental-backend-probe-overhead-20261013"></a>

## 2026-10-13 추가 backend 계측 ON/OFF 비교 완료

같은 2,124,377,355바이트/4,145,408행 fact의 독립 비압축 사본 4개와 동일 CSV·설정·
runtime을 사용해 OFF→ON→ON→OFF 순서로 비교했다. 화면을 띄우지 않은 backend 격리 시험이다.
각 warmup 30초+측정 120초이며, 정식 자원 계약의 120초+300초 수용 시험을 대체하지 않는다.
기본 workload는 health 2초/data 6초/이미지 250ms 요청과 합성 SPOT 수집·CSV/이미지 저장이다.
ON은 추가 프로세스 조회·memory API를 5초, details를 15초, stats/config를 30초 주기로 수집했다.
OFF에서도 기본 workload·앱 자체 관측·공통 host disk 표본은 유지했다.

| 조건 | 기본/추가 요청 | health 첫값/전체 최대, ms | 측정 평균/p95, ms | 새 CSV/이미지 |
|---|---:|---:|---:|---:|
| off-1 | 703/0 | 14.7754/28.2274 | 6.7918/24.0528 | 559/129 |
| on-1 | 703/54 | 33.7090/41.3921 | 11.2284/33.3426 | 577/126 |
| on-2 | 703/54 | 18.2213/46.8310 | 10.5800/31.9089 | 639/124 |
| off-2 | 703/0 | 11.7803/30.8110 | 5.3690/6.2309 | 638/129 |

전체 요청 2,920개는 200 응답·완전한 본문·해시·JSON/JPEG 검사를 통과했다. 각 health≤200ms,
data≤500ms이며 health 50ms/data 100ms/이미지 500ms 경고 초과도 0이다. 첫 요청과 지연 표본을
제외하지 않았다. 실행마다 기본 703개 요청의 예정 sequence와 비중첩을 검산했다.

측정 구간 health 평균은 OFF 6.0804ms, ON 10.9042ms로 관측 차이 +4.8238ms였다.
data 평균 차이는 +2.1855ms, 이미지 평균 차이는 +1.5286ms다. 조건당 2회 고정 ABBA 순서의
결과이며 통계적 유의성·보편적 비용·계측 영향 없음으로 단정하지 않는다. CDP/web-vitals와
전면 브라우저 렌더링의 OFF 비교는 이 시험에 포함하지 않았다.

공통 host disk 표본은 각 31개 중 측정 구간 25개다. Windows 장치별 누적 I/O의 증가량과
실제 간격으로 읽기/쓰기 bytes/s·횟수/s를 검산했고 원시 파일 및 각 review JSON에 보존했다.
이 수치는 PC 전체 앱의 I/O이며 제품에 귀속한 물리 디스크 사용량이 아니다. 기존 계약에 없는
디스크 상한을 추가하거나 PASS를 만들지 않았다. ON 프로세스 표본도 31개로 별도 보존했다.

새 CSV 2,413행의 연속 sample_seq와 동일 logger, 이미지 508개의 바이트/크기/해시/전체
디코딩 및 fact·최종 manifest를 검산했다. 4개 원래 fact prefix를 보존했고 backend는 모두
강제 종료 없이 exit 0이었다. begin/final 해시·동일 backend PID·worker drain·drop/failure 0과
실제 PID/생성 시각의 소멸을 대조했다. 수집 4회·검산 4회·최종 검산 모두 실제 exit 0이다.

139개 입력 사본과 runtime 125개를 검증했다. 8개 health 결합 파일·비문서 untracked 6개·
제품 diff·HEAD가 같아 full health를 반복하지 않았다. 신규 도우미 AST/Ruff F와 실제 실행을
확인했다. 미서명 내부 운영 정책, 설치본과 서버·장비 설정·운영/롤백 기준은 그대로다.

[실행 결과](C:/Users/user/Desktop/SmartFactory/PDCA_PROBE_OVERHEAD_20261013_82d431ef/RESULT.md),
[비교·최종 검산](C:/Users/user/Desktop/SmartFactory/PDCA_PROBE_OVERHEAD_20261013_82d431ef/comparison.json),
[실제 종료 코드](C:/Users/user/Desktop/SmartFactory/PDCA_PROBE_OVERHEAD_20261013_82d431ef/actual-terminal-receipts.json)를 보존했다.
입력 6,803파일/8,867,139,987바이트와 ZIP
6,804개 항목을 전수 대조했고 공유 ZIP 동일성을 확인했다.

- ZIP SHA256 `99919423b68b20a34467c5e7f297230714153dd07652f3e7d2a849253a05d7bc` (1,578,676,846바이트).
- manifest SHA256 `d3bf2717fba6f047c5d93d00739cd60e22115840c946ea07f1458cfd309c21b5`.
- 공유 위치: `Z:/SmartFactory/20261013/records/PDCA_PROBE_OVERHEAD_82d431ef`.
- 로컬 ZIP: `C:/Users/user/Desktop/SmartFactory/PDCA_PROBE_OVERHEAD_RECORDS_20261013_82d431ef/PDCA_PROBE_OVERHEAD_82d431ef.zip`.
- 봉인 검산 실제 exit 0. 기본 스트림 범위이며 ADS 검사는 아니다.

서버 측 추가 계측 비교는 완료했다. 브라우저 계측 영향, 실제 서버 정상 종료·시작 3회,
승인 실장비 프로파일/경계 판정, 과거 timeout/drop 인과·전체 데이터 처리 결정과 최종 clean
미서명 후보의 설치/복구·현장 QA/15분/120분이 남는다. 전체 목표 active,
R1–R6 HOLD, full_data_gate/full_r2_gate=NOT_EVALUATED를 유지한다.
