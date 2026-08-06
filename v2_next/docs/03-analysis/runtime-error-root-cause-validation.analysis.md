# Gap Analysis: runtime-error-root-cause-validation

> **Date**: 2026-07-20  
> **Design**: `docs/02-design/features/runtime-error-root-cause-validation.design.md`  
> **Implementation**: 실제 서버용 증거 수집 패키지와 2026-07-20 현장 실행 결과  
> **Scope**: 수집 패키지 정합성, 현장 증거 완전성, 사건별 원인 판정  
> **PDCA 상태**: Check 완료 — Report 진행 가능

---

## 1. Match Rate

**전체 Check 정합률: 92% (23/25)**  
**패키지 정적 구현 정합률: 100% (25/25)**

전체 Check 정합률은 Design의 25개 검증 ID를 기준으로 계산했다. 현장 실행 또는 오프라인 직접
증거로 판정된 항목, 그리고 진입 조건이 성립하지 않아 설계대로 미실행한 P2·P3 항목을 Match로
계산했다. 확보하지 못한 `SPOT-05` 스위치 로그와 `SPOT-06` 장비 서비스 로그 두 항목만 gap이다.

패키지 정적 구현 정합률 100%는 수집 도구 자체의 25개 설계 요구가 구현됐다는 별도 지표다.

| Gate | 상태 |
|------|------|
| 실제 서버 관리자 preflight | 완료 |
| 실제 서버 동시 수집 | 완료, 약 47분 |
| 같은 시간의 스위치 시작·종료 자료 | 미확보, `SPOT-05` gap |
| SPOT 장비 서비스 로그 | 미확보, `SPOT-06` gap |
| 수집 후 정상 복구 | packet·관측성으로 확인 |
| SPOT 하위 원인 판정 | 08:33 직접 확인, 08:19 유력 |

정합률이 90% 이상이고 두 gap이 핵심 TCP sequence 판정을 뒤집지 않으므로 Report로 이동한다.
08:10 host-side stall의 더 하위 원인은 별도 후속 조사 항목으로 유지한다.

---

## 2. 설계 항목 대 구현

| 번호 | 설계 요구 | 구현 위치 | 판정 |
|------|-----------|-----------|------|
| 1 | 관리자 권한 확인 | `Test-IsAdministrator` | 구현 |
| 2 | 관측성 collector 존재 확인 | `CollectorPath` preflight | 구현 |
| 3 | backend 대상을 localhost로 제한 | `ApiBase` 정규식과 URI port | 구현 |
| 4 | 실제 서버 config에서 SPOT IPv4 확인 | `Get-ConfiguredSpotIp`, `Assert-ValidSpotIp` | 구현 |
| 5 | 증거 드라이브 5GB 이상 확인 | `Get-PSDrive` free 검사 | 구현 |
| 6 | 앱 `/health` HTTP 200 확인 | GET preflight | 구현 |
| 7 | 기존 pktmon filter 보호 | filter list가 비어 있지 않으면 중단 | 구현 |
| 8 | 프로세스·부모 PID·포트 시작 상태 | `Export-ProcessAndPortState before` | 구현 |
| 9 | NIC 시작 카운터 | `Export-NicState nic_before.csv` | 구현 |
| 10 | SPOT 대상 TCP만 filter | `SpotHttpValidation`, target IP, TCP | 구현 |
| 11 | 제한된 packet header와 원형 파일 | NIC component, 128 bytes, 256MB circular | 구현 |
| 12 | 1초 ping 시간축 | background job, JSONL | 구현 |
| 13 | 앱 지표 5초 간격 15분 | 12 samples/minute, 기존 GET collector | 구현 |
| 14 | ping 종료 정리 | `finally`의 stop/receive/remove job | 구현 |
| 15 | pktmon 종료와 자신이 추가한 filter 정리 | `finally` stop, 등록 직후/종료 직전 filter state 동일성 검사 후 remove | 구현 |
| 16 | NIC·프로세스·포트 종료 상태 | after evidence와 NIC delta | 구현 |
| 17 | 같은 시간의 Windows System 이벤트 | 시작 2분 전부터 종료 시점까지 조회 | 구현 |
| 18 | 앱 로그 사본과 원본 경로 index | AppData/LocalAppData log copy | 구현 |
| 19 | ETL·PCAPNG·brief text | pktmon etl2pcap/etl2txt | 구현 |
| 20 | NIC 전후 증가량 | `New-NicDelta` | 구현 |
| 21 | IP·MAC 정제 | `Protect-Text`와 redacted 파일 | 구현 |
| 22 | raw 파일 SHA-256 manifest | `New-RawHashManifest` | 구현 |
| 23 | 공유용 sanitized ZIP과 SHA-256 | `Compress-Archive`, zip hash | 구현 |
| 24 | 스위치 시작·종료 수동 gate | 시작 prompt, 종료 시각, 요청 파일·안내서 | 구현 |
| 25 | 앱 무변경·부하 도구 제외 | GET-only, QA script 패키지 제외 | 구현 |

---

## 3. 구현 검증 결과

### 3.1 PowerShell

| 검증 | 결과 |
|------|------|
| Windows PowerShell parser | 오류 0 |
| 실행 PS1 비ASCII 행 | 0 |
| config parser self-test | 통과 |
| IPv4·MAC redaction self-test | 통과 |
| NIC delta self-test | 통과 |
| raw SHA-256 manifest self-test | 통과 |
| 전체 self-test 종료 코드 | 0, `SELF_TEST_PASS` |
| 비관리자 preflight | 증거 폴더 생성 전 fail-closed |

실행 PS1에서 비ASCII 문자를 제거한 이유는 Windows PowerShell 5.1이 BOM 없는 UTF-8 스크립트를
시스템 ANSI code page로 해석할 수 있기 때문이다. 한국어 설명은 실행 코드가 아닌
`README_KO.md`에 분리했다.

### 3.2 앱 변경 방지

- HTTP 호출은 `/health`와 기존 collector의 여섯 GET endpoint뿐이다.
- POST, PUT, PATCH, DELETE 호출은 없다.
- `/api/spot/image.jpg` 반복 요청은 없다.
- 오류 큐 clear, memory GC/snapshot/profiler 조작은 없다.
- 앱 시작·종료·재시작 명령은 없다.
- `qa_spot_image_server.ps1`은 패키지에서 제외했다.
- 앱 소스, 설정, DB, SPOT·PLC 설정은 수정하지 않는다.

`pktmon` filter는 증거 수집을 위한 일시적 운영 상태다. 기존 filter가 발견되면 fail-closed한다.
추가 직후 filter list와 종료 직전 list가 정확히 같을 때만 remove한다. 수집 중 다른 관리자가
filter를 추가해 목록이 달라지면 아무 filter도 제거하지 않고 실패 상태를 남긴다.

### 3.3 패키지

| 검증 | 결과 |
|------|------|
| 필수 파일 | 5개 모두 존재 |
| 금지 파일 | 부하 QA, EXE, config, log 0개 |
| manifest 내부 해시 | 불일치 0개 |
| source 대 packaged 파일 | 4개 모두 해시 일치 |
| ZIP 크기 | 19,300 bytes |
| ZIP SHA-256 | `C7F6CC5EA27FB8F32B4A840B5150D7B971A619793177ACC88DCF1F333221DF44` |

패키지:

`artifacts/runtime-error-root-cause-validation-field-kit-20260717_203214.zip`

첫 현장 preflight에서 `pktmon filter list`가 한국어로 `패킷 필터: 없음`을 반환했고
`pktmon status`도 실행 중이 아님을 확인했다. 1.0.1은 비어 있지 않은 출력 전체를 기존 필터로
오판했다. 1.0.2는 다국어 문자열 판정을 추가했지만, 관리자 PowerShell의 코드페이지 949가
pktmon UTF-8 출력을 `?⑦궥 ?꾪꽣: / ?놁쓬`으로 디코딩하여 알 수 없는 출력으로 안전 중단했다.
1.0.3은 pktmon 실행 구간에만 UTF-8을 적용하고 `finally`에서 기존 코드페이지를 복구한다.
코드페이지 949 실패 재현, UTF-8 성공, 복구를 검증했다. 두 현장 시도 모두 앱이나 서버 네트워크
설정을 변경하기 전에 중단됐다.

### 3.4 관측성 collector 모의 종단 시험

실제 장비 대신 localhost TCP mock server가 `/health`, `/stats`, 오류 큐, 메모리 2개 endpoint,
SPOT config에 JSON을 반환하도록 구성하고, packaged source와 해시가 같은 collector를 2 samples,
interval 0으로 실행했다.

| 검증 | 결과 |
|------|------|
| collector 종료 코드 | 0 |
| HTTP 요청 | 12/12 모두 GET |
| raw endpoint 파일 | 12개 |
| sanitized summary | 생성 |
| sanitized ZIP | 생성 |
| raw SHA-256 rows | 12, 불량 0 |
| mock SPOT IP의 sanitized summary 잔존 | 없음 |

이 시험은 collector의 endpoint 순회·파일 생성·정제·압축 경로를 확인한다. 실제 서버의 관리자
권한, pktmon driver, NIC, SPOT 응답을 검증한 것은 아니므로 현장 실행 gate는 그대로 남는다.

---

## 4. 의도된 설계 차이

### 4.1 명령 표시 언어 분리

설계 문서는 비개발자용 한국어 절차를 요구한다. 실행 PS1 문자열을 모두 한국어로 넣으면
Windows PowerShell 5.1 인코딩 문제로 syntax error가 날 수 있어 다음처럼 분리했다.

- 실행 창: 짧은 ASCII 영문 단계명
- 작업 설명: 한국어 `README_KO.md`

기능 범위는 바뀌지 않았고 실행 안정성을 높이는 차이다.

### 4.2 스위치 수집은 수동

스위치 종류와 관리 UI/API가 제공되지 않아 wrapper가 스위치에 로그인하지 않는다. 대신 시작
전에 Enter gate를 두고 시작값을 저장하게 하며, 종료 시각과 필요한 필드를 자동 기록한다.
스위치 자료 자체는 사용자가 같은 15분에 직접 확보해야 한다.

### 4.3 기존 pktmon filter가 있으면 중단

Windows `pktmon filter remove`는 이름 하나가 아니라 모든 filter를 삭제한다. 기존 filter를
복원할 수 있다는 가정을 하지 않고, 하나라도 있으면 중단하는 방향으로 설계했다. 이는 운영
안전을 위한 보수적 차이다. 또한 수집 도중 filter 상태가 변하는 경쟁 조건을 막기 위해 등록
직후와 종료 직전의 filter list가 동일할 때만 remove한다.

---

## 5. 2026-07-20 실제 서버 현장 증거

### 5.1 무결성과 실행 상태

| 항목 | 결과 |
|------|------|
| 실행 ID | `runtime_validation_20260720_080101` |
| 전달 ZIP SHA-256 | 제공값과 실제값 `84868c94372ec29e38a22a7af2187d9c0c082849d8e46493e72492daa6e4dd3c` 일치 |
| 추가 raw ZIP SHA-256 | `c49c6697afbbcddef548c5f84d420e0b5720395215c03c5fac268dc937231299` |
| ZIP 경로 안전성 | 경로 이탈 0, 중복 0 |
| field status | `COLLECTED` |
| pktmon 정리 | `removed_owned_state` |
| 앱 재시작·설정 변경·오류 삭제·부하 시험 | 모두 수행 안 함 |
| 관측성 GET | 6 endpoint × 180 sample = 1,080개, 모두 HTTP 200 |
| ETL·PCAPNG | 모두 생성 |

요청된 관찰 시간은 15분이지만 실제 packet/ping 창은 약 08:06:36~08:53:51로 약 47분이다.
180회 관측 루프가 endpoint 조회 시간과 매 회 5초 대기를 함께 사용했기 때문이다. 또한 sanitized
summary의 `stats_samples.collected_at`은 원본 envelope 시간이 아니라 summary 작성 시각으로 다시
기록되는 결함이 있어 sample 시각으로 사용하지 않았다. 오류 queue의 epoch와 packet/ping 자체
시각을 기준으로 교차 분석했다.

### 5.2 재현된 오류

초기 queue에는 PLC 빈 문자열 검증 오류 57회, Extruder timeout 1회, 기존 SPOT upstream error
1회가 있었다. 현장 수집 중 새 SPOT `ConnectTimeout` 5회와 Extruder timeout 1회가 추가됐다.

| KST 시각 | 새 오류 | 앱 결과 |
|----------|---------|---------|
| 08:10:18.525 | SPOT `ConnectTimeout`, Extruder timeout 동시 | `/api/spot/image.jpg` 502 |
| 08:18:56.266 | SPOT `ConnectTimeout` | 502 |
| 08:19:00.280 | SPOT `ConnectTimeout` 반복 | 502 |
| 08:19:05.320 | SPOT `ConnectTimeout` | 502 |
| 08:33:16.772 | SPOT `ConnectTimeout` | 502 |

누적 HTTP 5xx는 1에서 6으로 증가해 새 ConnectTimeout 5회와 정확히 일치한다. 최종 queue는
8개, repeat total은 65다. 동일 세션에서도 PLC `diagnostics_age_ms=''` 검증 오류가 57회 반복돼
PLC 오류가 SPOT 오류와 별개의 시작 데이터 형상 문제라는 기존 판정도 유지된다.

raw error detail의 `request_elapsed_ms`는 08:10 오류만 4,844ms였고, 이후 네 건은 각각
2,000ms, 2,000ms, 2,000ms, 2,016ms였다. 따라서 08:10 오류는 설정된 2초 connect timeout보다
약 2.8초 늦게 처리된 별도 지연이 함께 있었다.

### 5.3 앱 부하와 SPOT 요청

- `/api/spot/image.jpg` 최근 60초 요청률은 17.467~33.75 req/s, 표본 평균 30.659 req/s다.
- 전체 HTTP 최근 60초 요청률은 19.4~38 req/s다.
- SPOT image 평균 latency 표본 범위는 18.018~54.178ms다.
- image capture queue는 0/128로 종료했고 enqueued와 written이 1,830건 같이 증가했다.
- capture dropped 4,456은 수집 전후 증가하지 않았고 failure도 0이다.

현재 코드는 모든 image fetch를 `_img_fetch_lock`으로, 모든 SPOT 장비 요청을
`_spot_device_request_lock`으로 직렬화한다. 한 upstream connect가 막히면 후속 image 요청도
같이 기다린다. image connect timeout은 2초이고 공용 `AsyncClient`를 사용한다.

### 5.4 raw TCP flags와 연결 재사용

추가 제공된 raw PCAPNG는 08:06:37.200~08:53:53.118의 enhanced packet block
1,107,735개를 포함한다. 08:28:35부터 양방향 packet이 모두 보이는 구간을 TCP 4-tuple과 sequence
기준으로 중복 제거해 분석한 결과는 다음과 같다.

| 항목 | 결과 |
|------|------|
| 고유 TCP SYN 시도 | 64,862건, 평균 42.757건/s, 초당 최대 48건 |
| 정상 SYN-ACK | 64,861건 |
| SYN-ACK 없이 끝난 시도 | 1건, 08:33 오류와 정확히 일치 |
| 서로 다른 local source port | 16,238개 |
| 같은 local port 재사용 | 48,624회 |
| 1초 미만 재사용 | 단 1회, 48.484ms |
| HTTP 응답 시작 | `HTTP/1.0` 64,860건, keep-alive header 0건 |
| FIN | SPOT 64,861건, 서버 PC 64,861건 |

유일한 1초 미만 port 재사용과 유일한 TCP 연결 실패가 같은 연결이다.

1. 08:33:14.720: 서버 PC가 local port 50516으로 SYN을 보내고 SPOT이 0.330ms 뒤
   SYN-ACK를 반환했다.
2. 08:33:14.722~14.734: image 요청이 `HTTP/1.0 200 OK`로 완료됐다. SPOT이 먼저 FIN을
   보내고 서버 PC도 FIN을 보내 정상 종료했다.
3. 08:33:14.769: 종료 35ms 뒤 서버 PC가 같은 4-tuple을 새 sequence로 재사용했다.
4. SPOT은 새 SYN에 SYN-ACK가 아니라 직전 연결에서 기대하던 sequence의 plain ACK를 반환했다.
   서버 PC는 이를 현재 연결에 맞지 않는 ACK로 판단해 RST를 보냈다.
5. 08:33:15.772: 같은 SYN을 재전송했지만 SPOT이 같은 old ACK를 반환했고 서버 PC가 다시
   RST를 보냈다.
6. 08:33:16.772: 앱이 2,016ms `ConnectTimeout`을 기록했다.
7. 08:33:16.787: 다음 local port의 새 SYN은 0.252ms 뒤 정상 SYN-ACK를 받고 즉시 복구됐다.

이는 SPOT이 먼저 연결을 닫아 SPOT 측에 직전 연결의 종료 상태가 남은 동안 서버 PC가 같은
4-tuple을 너무 빨리 재사용했고, SPOT이 새 SYN을 새 연결로 받아들이지 못한 상황과 일치한다.
`HTTP/1.0` 응답과 매 요청 FIN 때문에 공용 `AsyncClient`가 있어도 TCP 연결은 재사용되지 않았고,
초당 약 43회의 새 TCP 연결이 생성됐다.

08:28 이전에는 PCAP에 SPOT→서버 방향이 기록되지 않아 같은 응답 sequence를 직접 확인할 수는
없다. 다만 08:19:00 오류를 만든 SYN은 local port를 직전 FIN 후 4.435초 만에 재사용했고 1초 뒤
재전송됐으며, 08:19:05 전후 SYN도 직전 FIN 후 10.382초 만에 port를 재사용했다. 따라서 08:19
세 건도 같은 port 재사용 충돌일 가능성이 높다.

08:10 오류는 패턴이 다르다. 앱의 실제 elapsed는 4,844ms이고 4.848초 동안 SPOT packet 자체가
없었으며 같은 시각 Extruder timeout도 발생했다. 가장 가까운 ping은 성공했지만 `ping.exe`
프로세스 실행에 2,927.7ms가 걸렸다. 이 건은 SPOT만의 TCP 충돌보다 서버 프로세스 또는 OS의
일시 정체가 함께 있었던 별도 사건으로 분리한다.

### 5.5 ping, NIC, Windows

- SPOT ping 2,619/2,619 성공, 실패 0이다.
- `elapsed_ms`는 ICMP RTT가 아니라 `ping.exe` 프로세스 전체 실행시간이다. 최대 6.375초를
  네트워크 RTT로 해석하지 않는다.
- 오류 시각 주변 ping도 모두 성공했다. 08:19는 약 17~67ms의 프로세스 실행시간이었다.
- 서버의 세 NIC 모두 received/outbound discard와 packet error 증가는 0이다.
- Windows System log에는 오류 시각의 NIC·TCP/IP·link 경고/오류가 없다.
- 08:31~08:36 Windows Update 정보 이벤트가 있지만 네트워크 장애를 입증하지 않는다.

## 6. 현재 원인 판정

| 후보 | 현재 판정 | 근거와 제한 |
|------|-----------|-------------|
| 서버 NIC 물리 오류 | 가능성 낮음 | NIC error/discard 0, ping 100% 성공, System network 오류 없음 |
| 케이블·스위치 링크 전체 단절 | 가능성 낮음, 미확정 | ping과 08:33 TCP 왕복 유지; 스위치 시작/종료 자료 미제공 |
| SPOT 장비 전체 다운 | 배제 | 오류 시각에도 ping 성공, 오류 사이 정상 image 응답 지속 |
| 빠른 TCP 4-tuple 재사용과 SPOT의 이전 연결 상태 충돌 | **08:33 직접 확인, 08:19 유력** | 정상 종료 35ms 뒤 같은 tuple 재사용, SPOT old ACK, PC RST, 재시도 후 2.016초 timeout |
| SPOT TCP 80 accept/backlog 일시 정체 | 주원인 후보에서 제외 | 실패 SYN에도 SPOT이 즉시 old ACK를 반환해 TCP stack과 왕복 경로는 동작함 |
| 서버 앱/OS 일시 정체 | **08:10 유력, 세부 원인 미확정** | SPOT packet 4.848초 공백, 앱 elapsed 4.844초, Extruder timeout 동시, ping 프로세스도 지연 |
| 서버 동적 port 고갈 또는 강한 port 압력 | 높은 기여 요인 | 25분여에 local port 16,238개 사용, 48,624회 재사용, 초당 약 43개 새 연결 |
| PLC 오류가 SPOT 오류의 원인 | 배제 | PLC 빈 문자열 검증 오류는 별도 시작 데이터 형상 문제 |

현재 결론은 **주된 SPOT ConnectTimeout 메커니즘이 고율의 짧은 HTTP/1.0 연결 반복과 local
port 조기 재사용으로 SPOT의 이전 TCP 종료 상태와 새 SYN이 충돌한 것**이다. 08:33 건은 packet
sequence까지 직접 확인됐고 08:19 세 건도 같은 패턴이 유력하다. 08:10 건은 SPOT 외 Extruder와
서버 실행 지연이 함께 발생한 별도 host-side stall로 분리하며, 그 하위 원인은 아직 확정하지
않는다. PLC 오류는 두 현상과 무관하다.

## 7. 남은 증거와 다음 단계

1. raw ZIP은 내부 IP, MAC, HTTP payload를 포함할 수 있으므로 공개 채널에 올리지 않고 제한된
   위치에 보관한다.
2. 스위치에 2026-07-20 08:01~08:54의 과거 link/CRC/error/discard event가 남아 있으면 보조
   증거로 확보한다. 없어도 08:33 TCP 충돌 판정은 유지된다.
3. 08:10 host-side stall의 하위 원인을 확정하려면 다음 재발 시 CPU, disk latency, process
   scheduling delay와 앱 event-loop lag를 같은 1초 해상도로 추가 수집한다.
4. 로직 변경을 검토하는 별도 단계에서는 SPOT HTTP/1.0 close 특성, image 요청률, source-port
   재사용 압력을 함께 낮추는 대안을 설계하고 재발 시험 기준을 정한다. 이 문서에서는 패치하지
   않는다.

현재 권고: **핵심 원인 분석은 완료, 08:10 host-side stall은 별도 조사 항목으로 유지**.
