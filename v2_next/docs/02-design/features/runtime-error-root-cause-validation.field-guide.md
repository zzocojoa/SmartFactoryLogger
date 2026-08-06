# SPOT ConnectTimeout 현장 수집 안내서

> **Feature**: `runtime-error-root-cause-validation`
> **Version**: 1.1.1
> **Date**: 2026-08-06
> **대상 작업자**: 실제 서버에서 직접 실행하는 비개발자 운영자
> **작업 성격**: 조사 전용, 앱 로직·설정·장비 설정 변경 없음

> **역사적 절차**: 이 안내서와 동일 이름의 수집 스크립트는 2026-07-21의 15분
> 원인 조사용 field kit를 설명한다. 2026-07-31의 최종 120분 canary는 별도의
> commit-bound event-trigger field kit로 수행됐다. 이 안내서를 현재 release의
> canary 승인 절차로 대체 사용하지 않는다.

---

## 1. 이번 실행의 목적

이번 실행은 `plc_driver` 오류를 다시 확인하기 위한 작업이 아니다. 이미 확정된
`plc_driver` 시작 오류와 `SystemExit: 3`도 재현하지 않는다.

확인하려는 것은 SPOT 이미지 `ConnectTimeout`이 발생하는 순간에 다음 중 어디가 응답하지
않았는지다.

1. SmartFactoryLogger 앱 내부
2. 실제 서버의 NIC 또는 Windows 네트워크
3. 서버와 SPOT 사이의 스위치·케이블·VLAN 경로
4. SPOT 장비의 TCP/HTTP 서비스
5. 정상 운전 중 이미지 요청률

이를 위해 앱 관측성, SPOT TCP 패킷, 1초 ping, NIC 카운터, Windows System 이벤트,
스위치 포트 로그를 같은 15분 동안 수집한다.

---

## 2. 실행이 허용된 조건

사용자 답변으로 다음 조건이 확인됐다.

- 현재 Codex PC는 실제 서버가 아니다.
- 실제 서버에서 사용자가 직접 실행한다.
- 실제 서버에서 관리자 PowerShell을 사용할 수 있다.
- 유지보수 시간 제약이 없다.
- 사용자가 SPOT 스위치 로그를 직접 확보할 수 있다.
- 사건 뒤 앱이 업데이트되었으므로 사건 버전과 현재 버전을 분리해 분석한다.

따라서 이 패키지는 **실제 SmartFactoryLogger 서버에 복사한 뒤에만** 실행한다.

---

## 3. 패키지에 들어갈 파일

다음 세 파일을 같은 폴더에 둔다.

1. `run-spot-connecttimeout-evidence-as-admin.cmd`
2. `collect-spot-connecttimeout-evidence.ps1`
3. `collect_operational_observability.ps1`

`qa_spot_image_server.ps1`은 이미지 요청을 추가로 발생시키는 부하 성격의 도구이므로 이번
패키지에 넣지 않는다.

---

## 4. 실행 전 확인

### 4.1 앱 화면

실제 서버의 SmartFactoryLogger 화면에서 다음을 확인한다.

- EX 통신 정상
- LS 통신 정상
- SPOT 통신 정상
- CSV queue와 drop 정상
- 화면의 최근 데이터 시각이 갱신 중
- 생산 설비가 정상 운전 중

하나라도 정상 상태가 아니면 실행하지 말고 화면과 시각을 기록한다.

### 4.2 하지 말아야 할 것

- 앱을 종료하거나 재시작하지 않는다.
- 오류 큐의 `비우기`를 누르지 않는다.
- 브라우저 탭을 추가하지 않는다.
- 새로고침을 반복하지 않는다.
- SPOT 이미지 요청을 일부러 증가시키지 않는다.
- `qa_spot_image_server.ps1`을 실행하지 않는다.
- SPOT, PLC, NIC, 스위치 설정을 바꾸지 않는다.
- 기존 `pktmon` 필터가 있으면 삭제하지 않는다.

### 4.3 디스크와 보안

- 증거 저장 드라이브에 최소 5GB 여유 공간이 있어야 한다.
- 패킷 원본과 앱 로그 원본은 실제 서버에서만 보관한다.
- 채팅에는 SPOT IP, PLC IP, MAC, 내부 URL을 직접 적지 않는다.
- 전달할 때는 스크립트가 생성한 `*_sanitized_share.zip`을 우선 사용한다.

---

## 5. 실행 방법

### 5.1 패키지 복사

패키지 ZIP을 실제 서버의 바탕화면에 복사하고 압축을 푼다. 세 파일이 같은 폴더에 있는지
확인한다.

### 5.2 실행

1. `run-spot-connecttimeout-evidence-as-admin.cmd`를 더블클릭한다.
2. Windows 사용자 계정 컨트롤이 표시되면 `예`를 누른다.
3. 검은색 또는 파란색 PowerShell 창을 닫지 않는다.
4. 사전 점검 실패 메시지가 나오면 임의로 수정하거나 필터를 삭제하지 말고 화면을 캡처한다.
5. `Press Enter after saving the switch start counters`가 나오면 스위치에서 다음 시작값을 저장한다.
   - 서버 연결 포트와 SPOT 연결 포트
   - RX/TX packet
   - error, discard, drop, CRC
   - link 상태, speed/duplex
6. 시작값을 저장한 뒤 PowerShell 창에서 Enter를 누른다.
7. 스크립트가 약 10초 동안 SPOT TCP 송신·수신 방향을 자동 확인한다.
8. `[OK] Bidirectional SPOT TCP packets were captured`가 표시된 경우에만 본 수집이 시작된다.
9. 방향 검증 실패로 중단되면 앱·NIC·스위치·pktmon 설정을 바꾸지 말고 완료 화면과 생성된
   `raw_private` 폴더를 보존한다.
10. 본 수집이 시작되면 명목상 15분 동안 앱을 평소처럼 두고 조작하지 않는다. 이 역사적
    collector는 각 5초 대기 뒤에 API 처리 시간이 더해지므로 실제 관측 구간은 15분보다
    길어질 수 있다.
11. 본 수집 중에는 약 30초마다 `[PROGRESS]` 줄에서 표본 수, 진행률, 경과 시간, 예상 남은
    시간과 수집 예상 종료 시각을 확인한다.
12. 표시된 예상 종료 시각은 현재 처리 속도를 반영한 근사값이다. 그 뒤 패킷 변환·익명화·ZIP
    생성 단계가 이어지며, 이 단계는 `Finalization 1/4`부터 `4/4`까지 표시된다.
13. 오류가 보이면 클릭하지 말고 발생 시각을 초 단위로 메모한다.
14. 수집이 끝나면 스위치의 같은 포트에서 종료값과 링크 이벤트를 저장한다.

---

## 6. 자동으로 수행되는 일

스크립트는 다음 순서로 동작한다.

1. 관리자 권한 확인
2. 앱 `/health` HTTP 200 확인
3. SPOT 주소 설정 존재 확인 — 화면에는 실제 주소를 출력하지 않음
4. 디스크 여유 공간 5GB 확인
5. 기존 `pktmon` 필터가 없는지 확인
6. 프로세스·부모 PID·백엔드 포트 시작 상태 저장
7. NIC 카운터 시작값 저장
8. 별도 10초 probe에서 SPOT TCP outbound와 inbound packet을 각각 1개 이상 확인
9. probe 양방향 통과 시에만 SPOT 대상 본 TCP 헤더 패킷 캡처 시작
10. SPOT 대상 1초 ping 시작
11. 앱 관측성 GET 조회를 5초 간격으로 15분 수집
12. 약 30초마다 표본 진행률·경과 시간·예상 남은 시간·수집 예상 종료 시각 표시
13. ping과 패킷 캡처 종료
14. 종료 직전 필터 목록이 등록 직후와 같을 때만 자신이 등록한 `pktmon` 필터 제거
15. NIC·프로세스·포트 종료 상태 저장
16. 같은 시간의 Windows System 이벤트 저장
17. 앱 로그 사본과 SHA-256 생성
18. 패킷 ETL·PCAPNG 원본 생성
19. 후처리 단계를 `Finalization 1/4`부터 `4/4`까지 표시
20. IP·MAC을 가린 패킷 텍스트와 정제 ZIP 생성

스크립트는 앱 시작·종료, POST API, 설정 저장, 오류 삭제, 강제 GC, 이미지 반복 요청을 하지
않는다.

---

## 7. 자동 중단 조건

다음 경우 수집 전에 자동으로 중단한다.

- 관리자 권한이 아님
- 실제 서버의 SmartFactoryLogger `/health`가 HTTP 200이 아님
- SPOT 주소를 설정에서 확인할 수 없음
- 증거 드라이브 여유 공간이 5GB 미만
- 기존 `pktmon` 필터가 존재함
- 필요한 관측성 수집 스크립트가 같은 폴더에 없음
- API 대상이 localhost가 아님

기존 `pktmon` 필터가 있으면 스크립트는 이를 삭제하지 않는다. 또한 수집 중 다른 필터가 추가되어
종료 직전 목록이 달라지면 전체 filter remove를 실행하지 않고 실패로 기록한다. 이 경우 화면을
캡처해 조사 담당자에게 전달한 뒤 별도 시간을 정한다.

---

## 8. 실행 중 수동 중단 조건

다음 상황이면 PowerShell 창에서 `Ctrl+C`를 한 번 누른다.

- EX 또는 LS 통신이 끊김
- 생산 데이터가 멈춤
- CSV drop이 증가함
- 앱 전체가 응답하지 않음
- SPOT 영상뿐 아니라 온도·진단도 장시간 중단됨
- 현장 작업자가 생산 영향 가능성을 판단함

스크립트의 종료 정리 구문은 ping과 패킷 캡처를 멈춘다. 필터 목록이 등록 직후 상태와 같을 때만
자신이 추가한 필터를 제거하며, 달라졌다면 다른 필터를 보호하기 위해 아무 필터도 제거하지 않는다.
그 뒤 앱의 정상 복구 여부를 확인하고, 생성된 원본 폴더를 삭제하지 않는다.

---

## 9. 실행 후 파일

기본 저장 위치는 실제 서버 바탕화면의 다음 폴더다.

```text
SmartFactoryLogger_Evidence
└── runtime_validation_YYYYMMDD_HHMMSS
    ├── raw_private
    │   ├── app
    │   ├── logs
    │   ├── network
    │   ├── process
    │   └── switch_logs_drop_here
    ├── sanitized_share
    ├── runtime_validation_..._sanitized_share.zip
    └── sanitized_share_sha256.txt
```

- `raw_private`: 내부 IP·경로·패킷이 포함될 수 있으므로 서버 내부 보관
- `sanitized_share`: IP·MAC을 가린 분석 자료
- `*_sanitized_share.zip`: 우선 전달할 파일
- `switch_logs_drop_here`: 같은 15분의 스위치 자료를 넣을 위치

---

## 10. 스위치에서 반드시 저장할 자료

서버 포트와 SPOT 포트 각각에 대해 다음을 저장한다.

- 포트 번호와 장비 역할 — 외부 공유본에서는 마스킹
- 시작·종료 RX/TX packet
- 시작·종료 error, discard, drop, CRC
- 링크 up/down 이벤트
- speed/duplex 변경
- STP/VLAN 이벤트
- MAC 이동 또는 포트 보안 이벤트
- 같은 시간의 스위치 재부팅·관리 이벤트

누적 숫자 하나만 보내지 말고 반드시 시작값과 종료값을 함께 저장한다.

---

## 11. 전달할 자료

1. `*_sanitized_share.zip`
2. `sanitized_share_sha256.txt`
3. 스위치 로그 정제본 또는 다음 값을 적은 표
   - 실행 시작·종료 시각
   - 서버 포트의 error/discard/CRC 증가량
   - SPOT 포트의 error/discard/CRC 증가량
   - 링크 이벤트 유무
4. 앱 화면에서 오류를 본 정확한 시각 메모
5. 수집 창에 실패 메시지가 있었다면 그 화면 캡처

원본 PCAPNG와 원본 앱 로그가 추가로 필요하면 내부 보안 범위를 확인한 뒤 별도로 요청한다.

---

## 12. 결과 판정 방법

| 동시 증거 | 판정 방향 |
|-----------|-----------|
| 앱 ConnectTimeout + TCP SYN 전송 + SYN-ACK 없음 | 앱 밖으로 요청은 나감; SPOT 장비 또는 중간 경로 |
| 위 현상 + ping 손실 + NIC/스위치 drop 증가 | 서버 NIC·케이블·스위치·경로 가능성 높음 |
| SYN 반복 + ping 성공 + SYN-ACK 없음 | SPOT TCP 서비스·포트·접속 한도 가능성 높음 |
| SYN-ACK 정상인데 앱 ConnectTimeout | 앱 연결 관리 또는 서버 네트워크 스택 추가 조사 |
| 앱 오류 시각에 SYN 자체가 없음 | 네트워크 호출 전 앱 단계 또는 캡처 대상 재검토 |
| TCP 정상 뒤 HTTP 5xx | ConnectTimeout과 다른 장비 HTTP 응답 문제 |
| 15분 동안 오류 없음 | `NOT_REPRODUCED`; 정상이라는 최종 결론은 아님 |

SPOT 하위 원인 판정은 이 자료를 받은 뒤 PDCA Check 단계에서 수행한다.

---

## 13. 버전 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| 1.0.0 | 2026-07-17 | 비개발자용 실제 서버 15분 동시 수집 절차 작성 |
| 1.0.1 | 2026-07-17 | 수집 중 pktmon filter 상태 변경 시 전체 filter 삭제를 건너뛰는 안전 조건 추가 |
| 1.0.2 | 2026-07-17 | 한국어·영어의 `pktmon filter list` 무필터 출력을 기존 필터로 오판하지 않도록 수정 |
| 1.0.3 | 2026-07-17 | Windows PowerShell 5.1 코드페이지 949에서 pktmon UTF-8 출력이 깨지는 문제를 실행 구간 UTF-8 적용·즉시 복구로 수정 |
| 1.1.0 | 2026-07-21 | 15분 현장 수집 결과와 비개발자 운영 절차를 동결 |
| 1.1.1 | 2026-08-06 | 15분 역사적 조사 kit와 후속 120분 commit-bound canary의 사용 경계를 명시 |
