# 1.0.29 현장 관찰 지연 구간 진단

## 결론과 범위

2026-10-16 서버 15분 관찰 `run-88b12319867a`는 FAIL이다. health 450회 중
200ms 초과 2회, 영상 시험 요청 3,600개 예정 시점 중 미실행 5개가 있었다.
요청 오류·timeout은 없었다. 실제 운영 영상 저장 누락으로 해석하지 않는다.
원인은 아직 확정하지 않았으며, 기존 실패와 200ms 기준을 보존한다.
정식 QA·운영 승격은 HOLD이고 120분 시험을 시작하지 않았다.

추가 계측한 15분 진단 `run-45e6bd379d57`도 FAIL이다. health 200ms 초과 1회와
영상 조회 시점 누락 11개를 원본 재계산으로 확인했다. 450개 health 요청 모두
요청 식별자·프로세스/스레드 세대·native clock을 결합했다. 가장 느린 응답은 한 함수의
단독 지연이 아니라 route 진입 전·worker 시작 전·runtime 정보·route 재개 후 등 여러
구간에 나뉘었다. OS 실행 대기와 실제 처리 시간을 구분할 후속 근거가 필요하다.

설치 후보는 미서명 내부 운영 정책의 1.0.29,
build `acaf77d95101a050f4d3ecd76125d3502036f5a7`이다.
이번 변경은 진단 도우미에만 적용한다. 제품 설치·재시작·전체 백업은 수행하지 않는다.

## 보존 원본과 재검산

- 원본 회수: `Desktop/SmartFactory/REMOTE_EXEC_20261016_9c72f3a1/recovered-run-88b12319867a`
- 인증된 SSH 실행에서 확보한 launcher SHA256:
  `03ba8f0f3d79a81b5dee8b6169297916a421895813bd93a7d6b332e5daa7aada`
- launcher에 결합된 session manifest와 그 안의 8,786파일을 다시 검산했다.
- 오프라인 분석: `Desktop/SmartFactory/PDCA_OBS_LATENCY_20261016_4b21c68f/review.py`
- 분석 결과 `review.json`: 74,902 bytes,
  SHA256 `cd669b8c3ca567a725142d2e3abd1403f104119f9fbb0131709edcd8986e0aba`.
  분석기 종료 코드 0. 당시 고정된 도우미 소스의 바이트도 대조했다.

| 요청 | UTC 시작 | 전체 요청·본문 수신 | 헤더 대기 |
| --- | --- | ---: | ---: |
| health 216 | 02:27:25.611653 | 202.2317ms | 201.5962ms |
| health 345 | 02:31:43.615544 | 210.3340ms | 209.3956ms |

두 요청에는 `X-SFL-Health-Timing` 응답 헤더가 없다. 이 기록만으로 서버의 어느
처리 구간이 느렸는지 복원할 수 없다. 클라이언트 헤더 대기에는 서버 처리와
클라이언트 스케줄링 대기가 함께 포함될 수 있다. 5초 간격 자원 카운터나 겹친
파일 저장 작업은 시간상 주변 정보이며, 200ms 요청의 원인이나 CPU 시간을 입증하지 않는다.

영상 시험 요청 누락은 다음 두 종류로 구분된다.

| 예정 순번 | 관찰된 직전 상태 | 해석 한계 |
| --- | --- | --- |
| 254, 476, 1037 | 직전 응답 수신이 다음 250ms 시점을 넘음 | 서버·클라이언트 중 원인 미확정 |
| 219, 2763 | 직전 응답 해독·`queued_ns`는 다음 시점 전에 완료 | enqueue 반환·잠금·OS 대기를 기존 기록으로 분리 불가 |

기존 코드의 `queued_ns`는 enqueue 시작 전에 기록한다. enqueue 완료 시각이 아니다.
측정 기록 4,200개는 모두 저장됐고, 대기 큐 최대 3개·폐기 0개였다. 이것이
두 요청 간 진행 지연의 부재나 현장 성능 PASS를 뜻하지 않는다.

## 후속 진단 계약

새 요청 모드 `timing-observe`는 1.0.29와 900초만 허용한다. 기존 `observe`
15분/120분 및 `host-diagnostic` 5분 계약은 유지한다.

1. 설치 파일·승인 설정·인증된 실행 세대의 기존 검증을 유지한다.
2. 요청에 외부 확인한 `backend_created_filetime`을 필수로 넣고 전후 native 세대를 대조한다.
3. 기존 health 2초, data 6초, image 250ms 주기를 유지한다. health 요청마다
   고유 probe ID를 전송하고 서버 구간·native clock을 원본 응답/프로세스 세대와 검산한다.
4. 각 측정 스레드의 반복 진입, JSON 준비, 잠금 획득, enqueue 반환, 반복 종료
   시각을 별도 `http/progress.json`에 저장한다. 원본 요청의 순번·시각과 대조한다.
5. 누락·오류·200ms 초과를 숨기거나 재시도하지 않는다. 첫 요청과 종료 경계 요청도 보존한다.
6. 독립 supervisor와 소유 작업 묶음의 시간 제한·정리를 유지한다. 운영 앱은 그 묶음에 넣지 않는다.
7. 이 측정은 `TIMING_DIAGNOSTIC_NOT_FIELD_PERFORMANCE`이다. 추가 계측의 영향이 있으므로
   일반 관찰의 PASS 대체 자료로 쓰지 않는다. 구간별 경과 시간은 정확한 CPU 시간이나
   스케줄링 원인 판정이 아니다. 필요한 구간을 좁힌 뒤 ETW 증거를 별도로 연결한다.

시간 구간 해석은 실제 설치 commit의 `backend/app.py`와 대조한다. 현재 소스의
해당 파일·`backend/version.py`·`backend/FacilityData/service.py`는 설치 commit
`acaf77d95101a050f4d3ecd76125d3502036f5a7`와 차이가 없다.

| 구간 | 포함되는 작업과 해석 한계 |
| --- | --- |
| 요청 시작 → route 진입 | 연결·송신·서버 진입 전 시간. 서버 큐 대기만으로 단정할 수 없음 |
| submitted → worker 진입 | `asyncio.to_thread` 제출 이후 worker 시작까지. 큐·스케줄링·계측 비용 포함 |
| worker 진입 → plc_done | native 시작 계측 및 PLC/온도 상태 읽기. 내부 잠금과 통신 통계 읽기 포함 |
| plc_done → runtime_done | 실행 파일 경로·수정 시각 등 런타임 정보 읽기 |
| runtime_done → frontend_done | 프런트엔드 경로·index·assets·누락 자원·후보 경로 상태 읽기 |
| worker 종료 → route 재개 | native 종료 계측 및 비동기 route가 재개되기까지 |
| route 재개 → 응답 수신 완료 | native/헤더 생성·직렬화·middleware·전송·클라이언트 수신. 단일 원인으로 단정 불가 |

진단기의 `metadata_ready → lock_acquired`도 벽시계 경과 시간이다. 실제 잠금 경합 시간과
OS의 실행 지연을 이 두 시각만으로 분리하지 않는다.

## 개발 검증

- 새 격리 시험 8개: PASS, exit 0. 실제 Windows 소유 프로세스와 loopback HTTP를 사용했다.
  정상 구간 결합, 잘못된 native 세대, 누락 헤더, 230ms 지연, enqueue 지연·요청 누락,
  진행 기록 변조, 일반 모드 유지, 진단 요청 계약을 확인했다.
- 기존 HTTP·관찰·후보·실제 backend timing 시험 67개: PASS, exit 0.
- 기존 host 요청 계약 시험 3개: PASS, exit 0.
- 변경 Python 파일 Ruff: PASS, exit 0.
- 전체 `npm run health`: PASS, exit 0. 프런트엔드 437개, backend 932개 중
  931개 통과·1개 skip이며, 의존성·Electron·타입·lint·QA selftest도 완료했다.
- 이 절의 Python 검증 이후 frozen 포장 검사에서 아래 종료 판정 문제가 발견됐다.
  서버에는 새 진단을 실행하지 않은 상태다.

예시 검증 명령(각 `SFL_*_TEST_ROOT`는 기존 경로를 재사용하지 않는 새 폴더):

```powershell
backend\.venv\Scripts\python.exe -m unittest discover -s scripts/field-v1028 -p test_field_timing_observation.py -v
npm run health
```

검증 로그는 `Desktop/SmartFactory/PDCA_OBS_LATENCY_20261016_4b21c68f`에 보존한다.
이전 여섯 초 진단의 launcher도 03:00 UTC 인증된 SSH 읽기로 원본 서버 SHA와 회수
SHA 일치를 확인했다. 이것은 당시 닫힌 콘솔의 해시를 복원했다는 주장이 아니다.

작업자 화면 요구는 `AGENTS.md`에 반영했다. 서버 작업 종료 시 실행 중인
Smart Factory를 복원·전면 표시하고 현재 작업 정보가 보이는지 확인한다.

## 포장 검사에서 확인한 종료 판정 수정

첫 frozen 빌드는 clean commit `1baf2433e8ac9e6ebf2510ae704a5e4b11183c83`에서
완료됐다. 그러나 개발 fixture의 내부 검사 PASS와 바깥 실행기 FAIL이 충돌했다.
첫 실패 결과를 보존하고, 개발 전용 실행기에 검산 전 child receipt 저장만 추가해
한 번 더 실행했다. 운영 서버나 제품 코드는 이 조사에 사용하지 않았다.

`PDCA_TIMING_BUILD_20261016_7e8a9c03/pd1/run-cb324cc5508f/dev-child-before-verification.json`
(SHA256 `ae04cc1f58178f8eda5d1fab36c23822f936948f1a4750118ede09f22c2474f2`)의 사실:

- 실제 루트 종료 코드 0, 강제 종료 없음.
- 첫 작업 묶음 accounting: 전체 11, active 1.
- 뒤따른 native 관찰: 전후 active 0, 열거 멤버 0, 루트 signaled·exit 0.
- 최종 active 0이지만 첫 값만 검사하는 `outer-descendants-remain`이 FAIL을 유지했다.

루트 프로세스 종료와 작업 묶음 전체의 정리 확인은 별개다. Microsoft의
[ActiveProcesses 정의](https://learn.microsoft.com/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information)는
종료 프로세스의 참조가 해제된 뒤 카운터가 감소한다고 설명한다. 위 관찰은 첫 카운터와
뒤의 비동시 관찰이 달랐다는 근거이며, 특정 숨은 프로세스의 정체나 현장 HTTP 지연 원인을
입증하지 않는다.

실행기는 최초 카운터를 보존하면서 전체 제한 시간 안에서 최대 2초간 소유 작업 묶음의
active 0을 확인한다. 끝까지 남은 프로세스, 전체 시간 제한, nonzero 종료는 계속 FAIL이고
소유 프로세스만 정리한다. 새 프로세스 실행이나 실패 요청 재시도는 없다. 출력 검산보다
먼저 `native-child.json`을 저장하고 launcher 성공·실패 영수증에 해시를 연결해, 후속 검산
오류가 발생해도 종료 근거를 잃지 않도록 했다.

최종 `test_field_run_native.py` 16개 그룹 PASS, exit 0. 자연 종료하는 자식의 drain,
잔류 자식·종료 7·전체 deadline·감시자 사망·진단 오류·30회 빠른 종료·다른 프로세스
보존·출력 변조 거절을 확인했다. Windows PowerShell 5.1 x64에서 수행했고, 보호 ACL의
descriptor를 검사했으며 관리자 소유 ACL 실제 적용은 개발 일반 권한 시험 범위 밖이다.
결과: `PDCA_OBS_LATENCY_20261016_4b21c68f/native-drain-r2/summary.json`.
최종 실행기 SHA256은 `65d37c5c1722efc0a572f36b2d792df611a96406d7a879e8b332fe72c775c41c`다.
전체 health는 앞의 Python 변경 상태에서 통과했으며, 이후 실행기 수정은 위 native 시험과
Ruff·diff 검사를 적용했다.

## 수정 묶음 검증과 서버 전달

수정된 clean commit `f937029fff2c34d03c9072ccdb17052d5912530d`에서 다시 빌드했다.
`PDCA_TIMING_BUILD_20261016_7e8a9c03_R2/portable-r1/summary.json`의 포장 검사는
PASS, exit 0이다. 실제 frozen 실행 6건에서 정상 fixture, 실제 attestation의 의도된
거절, 중복 JSON 거절, 일반 권한의 관리자 실행 거절, 잘못된 요청 해시 거절 및
describe 출력을 확인했다. 각 결과의 `native-child.json` 해시·내용이 launcher와
일치했고 소유 작업 묶음 active 0·강제 정리 없음도 확인했다. 개발 fixture용 실행기와
서버에 전달한 관리자 실행기는 구분한다.

서버 전달 위치는 `C:\Users\user\Desktop\SmartFactory\TO29_20261016_7e8a9c03_R2`다.
`Z:\SmartFactory\20261016\send`에서 Chrome 원격 데스크톱의 탐색기로 복사하고,
최종 절대경로를 화면에서 확인한 뒤 인증된 SSH로 13개 파일의 길이·SHA256을 대조했다.
`server-delivery-verification.json`은 exit 0이며 제품 프로세스 세대와 작업 정보
60313·1도 동일했다. 운영 앱의 설치·재시작·전체 백업은 수행하지 않았다.

| 식별 항목 | SHA256 |
| --- | --- |
| frozen `field_runner.exe` (16,097,208 bytes) | `b464c2ec9e3669a17c3a62ef50d1c326237a9dbf2bb5c77e89e37eb64fc05847` |
| 패키지 manifest | `879e6e3d467167aa74a1bdc8c35d4990af19791859b562d4208550c93c63ef12` |
| 현장 진단 request | `dd47d4432ad9eb981b4ba0b0880fb89b9201e27c9621d7b9505ae926a6c6e995` |
| 잠금 실행 명령 | `25cc69a219eedaec3959ef35a293346206c6bc75361e0f32c524fa9bc003d7e5` |

Smart Factory를 전면에 복원한 뒤 SSH로 한 번 실행했다. 서버 결과 폴더는
`C:\Users\user\Desktop\SmartFactory\run-45e6bd379d57`이며 HTTP origin 기록 시각은
2026-10-16 03:30:40.744606 UTC다. 900초 진단을 완료한 뒤 회수·검산했다.
측정 중 읽기 전용 시작 확인을 두 번 수행했다. 첫 확인의 UTC/local 필터 오류로
폴더가 0개 반환돼 실제 측정 파일을 읽지 못했고, 두 번째 확인에서 UTC로 맞춰
요청 해시와 origin만 읽었다. 진단을 재실행하거나 원본을 변경하지 않았다.

## 실제 진단 결과와 원본 재계산

SSH 출력의 `LAUNCH_EXIT=1`과 launcher SHA256
`12d2e10740099cbd2365220336be0ffbd986a91ce4a314f270303084de7521ee`를 회수 파일과
대조했다. tar에는 8,788개 파일, 60,036,232 bytes가 있으며 tar 자체는 67,430,400 bytes,
SHA256 `ea344dbcb3b7a8b6f5b7ca338c743a364282c49f6d15d577764dc52a988c0488`이다.
session manifest의 8,783개 파일을 모두 확인하고 frozen source 85개를 대조했다.
HTTP·자원·전체 결합 요약과 진행 기록을 다시 계산해 모두 일치했다.
`review_timing_ssh.py` exit 0, `RECORDED_SUMMARIES_REPRODUCED`, replay errors 0이다.
검산 성공은 진단의 FAIL을 바꾸지 않는다.

| 채널 | 실행/예정 | 최대 응답 | 기록 결과 |
| --- | ---: | ---: | --- |
| health | 450/450 | 207.5919ms | 200ms 초과 1건, 오류·timeout 0 |
| data | 150/150 | 123.2425ms | 500ms 초과 0건, 오류·timeout 0 |
| image | 3,589/3,600 | 552.3252ms | 조회 시점 누락 11개, 오류·timeout 0 |

health 초기·최종 경계까지 452개를 검사했고, 예약 health 450개 모두
`REQUEST_AND_NATIVE_CLOCK_BOUND`다. 영속 기록은 4,200개 모두 저장됐으며
discarded 0, 최고 pending 3이다. 소유 작업 묶음의 잔여 프로세스는 안쪽·바깥쪽 모두
0이고 강제 정리도 없었다. 종료 후 SSH 확인에서도 진단 프로세스는 없었다.

200ms 초과는 health 순번 65, 서버 시각 03:32:53.304527 UTC의 207.5919ms다.
이 시점은 시작 확인용 SSH 읽기 두 번보다 앞선다.

| 벽시계 구간 | 시간 |
| --- | ---: |
| 클라이언트 요청 시작 → route 진입 | 45.0063ms |
| route 진입 → worker 제출 | 0.0486ms |
| 제출 → worker 진입 | 30.7151ms |
| worker 진입 → PLC 상태 완료 | 0.9607ms |
| PLC 상태 완료 → runtime 정보 완료 | 22.4122ms |
| runtime → frontend 상태 완료 | 3.4724ms |
| frontend 완료 → worker 종료 | 0.0085ms |
| worker 종료 → route 재개 | 10.3838ms |
| route 재개 → 클라이언트 응답 수신 완료 | 94.5843ms |

영상 조회 누락 순번은 75, 416, 859, 860, 1045, 1046, 1196, 1655, 2336,
3136, 3330이다. 앞선 실제 응답 9건이 다음 250ms 시점을 넘겼고, 이 중 2건은
각각 두 시점을 넘겼다. 직전 요청 이후 metadata 준비·잠금 획득·enqueue 반환의
기록은 모두 짧았으며 이 11개 누락을 설명하지 않는다. 앞선 일반 관찰의 두
enqueue 이후 지연 사례를 이번 진단에서 재현했다는 뜻은 아니다.

`timing-review.json` SHA256:
`19e74815338117982a7f5d1d55b5f0fb27064188b9e70a3494550baefc14aa66`.
`timing-analysis.json` SHA256:
`613332f28d14917a2c37b767aad8dd891983b114bdeb0b866abf993e14b10367`.
분석 명령 exit 0. 회수·분석 원본은 위 R2 빌드 폴더에, 공유 사본은
`Z:\SmartFactory\20261016\return\TIMING_run-45e6bd379d57`에 보존한다.

앱 1.0.29와 main/backend의 native 생성 시각은 실행 전후 동일했다. 제품 60313·금형 1,
Running 상태와 전면 Smart Factory 화면을 확인했다. 설치·재시작·전체 백업은 없었다.
제조사 문의의 정확한 Gmail thread도 다시 읽었으나 보낸 메일 1개만 확인됐다.

다음 원인 조사는 위 느린 구간의 backend loop·worker·collector 스레드에 대한
실행/대기 근거와 route 재개 이후 직렬화·전송 구간을 대상으로 한다. 특정 함수의
캐시 변경, 잠금 제거, 임계값 완화 또는 원인 미확정 상태의 120분 시험은 수행하지 않는다.
물리 경계·전체 QA·운영 승격은 여전히 미완료다.
