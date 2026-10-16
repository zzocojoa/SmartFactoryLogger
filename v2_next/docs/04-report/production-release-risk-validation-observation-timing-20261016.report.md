# 1.0.29 현장 관찰 지연 구간 진단

## 결론과 범위

2026-10-16 서버 15분 관찰 `run-88b12319867a`는 FAIL이다. health 450회 중
200ms 초과 2회, 영상 시험 요청 3,600개 예정 시점 중 미실행 5개가 있었다.
요청 오류·timeout은 없었다. 실제 운영 영상 저장 누락으로 해석하지 않는다.
원인은 아직 확정하지 않았으며, 기존 실패와 200ms 기준을 보존한다.
정식 QA·운영 승격은 HOLD이고 120분 시험을 시작하지 않았다.

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
Ruff·diff 검사를 적용했다. 새 묶음 재포장 검증과 현장 진단은 후속 단계다.
