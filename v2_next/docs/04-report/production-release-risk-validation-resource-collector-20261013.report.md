# 현장 자원·물리 디스크 수집과 HTTP 저장 지연 계측

2026-10-13. 자원 수집 모듈과 HTTP 공통 시작 시각·파일 저장 시간 계측을 추가했다.
최종 자원 회귀23개와 HTTP 회귀31개는 exit0이다. 개발 PC의420초 통합 관찰에서
자원85표본·준비 구간 이후61표본을 확보했으나 HTTP 예정 슬롯18개가 누락됐다.
이 관찰의 HTTP 판정은 **FAIL**이며 실제 서버·제품 성능 또는 전체 현장 QA PASS가 아니다.

## 코드와 계측 범위

- [자원 수집기](../../scripts/field-v1028/field_resource_sampling.py):
  SHA256 `517a28f6de00e495ac16c74099f1e8c949d67d5b0e76069bbe4e9ec8bb91816c`.
- [회귀 검사](../../scripts/field-v1028/test_field_resource_sampling.py):
  SHA256 `7acac89d613418425a4f0fd815a57b54227b38ebc5c326cee3105890dfdc1f45`.
- [HTTP 수집기](../../scripts/field-v1028/field_http_sampling.py):
  SHA256 `6b47aa425b7cc7484fa8f843037f03b9dcb7183866a6abab98d2a045e9d9ea01`.
- 증거 루트: `C:\Users\user\Desktop\SmartFactory\PDCA_RES128_20261013_3bc421b7`.

루트 프로세스는 PID·생성 시각·실행 경로로 확인하고 관찰된 자식 트리를 읽는다.
각 프로세스의 CPU 누적 시간, RSS/VMS, 스레드·핸들 수, I/O 누적 바이트를 보존한다.
재사용 PID, 접근 실패, 수집 중 트리 변경, 인접 표본의 구성 변경·카운터 감소를 감지하면
해당 변화량을 NOT_MEASURED로 처리한다. CPU는 논리 CPU 수로 나눈 기계 전체 용량 비율이다.
RSS 합은 공유 페이지를 포함하며 고유 물리 메모리가 아니다. 프로세스 I/O도 실제 디스크
입출력과 같다고 해석하지 않는다. 표본 사이에 생성·종료된 모든 자식의 수명은 포괄하지 않는다.

디스크는 [QueryDosDeviceW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-querydosdevicew)로
보이는 PhysicalDrive 이름을 열거하고 각 장치의 원시88바이트·누적 바이트/작업 수·시간·순간 큐 깊이를
저장한다. 오류나 장치 목록 변경도 기록한다. 호스트 전체 장치 계측이며 앱별 귀속이나
NAS 서버의 물리 디스크, 변경 불가능한 하드웨어 일련번호 식별을 뜻하지 않는다.

설치된 psutil7.2.2의 [Windows disk 소스](https://raw.githubusercontent.com/giampaolo/psutil/release-7.2.2/psutil/arch/windows/disk.c)는
ReadTime/WriteTime을10,000,000으로 나눈다. 반면
[Microsoft 드라이버 구조 문서](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ns-ntdddisk-_disk_performance)는
누적 읽기/쓰기 시간을100ns 단위로 정의한다. 실제 앞뒤 psutil 값과 원시 카운터를 대조해 이 차이를
확인했다. 새 수집기는 원시100ns를 보존하고 시간 변화량을10,000으로 나눠 ms로 표현한다.
작업별 지연이나 디스크 사용률로 환산하지 않는다. QueryTime은 벽시계로 보존하며 속도 계산에는
monotonic 시작 시각의 차이를 사용한다. 이전 봉인 기록의 값을 소급 수정하지 않는다.

[IOCTL_DISK_PERFORMANCE](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_disk_performance)는
카운터를 활성화·조회하는 호출이다. 순수한 무부작용 읽기라고 표현하지 않는다. 이 코드에는
PERFORMANCE_OFF, diskperf 구성 변경, 장비 제어 또는 제품 프로세스 종료가 없다.

기본5초 주기·최대7200초이며120초 준비 뒤300초 창, 최소48표본·240초 범위를 계산한다.
긴 수집은 완전한300초 창들과 마지막300초 창을 각각 보존한다. 실제 시각·누락·중단을 남기고
원문/요약/manifest를 새 폴더에만 쓴다. 자원 파일의 최종 경로240자 제한과 마지막 표본의 주기
초과도 검사한다. coverage와 수치 추세는 성능 승인과 구분하며 release HOLD를 유지한다.

## 시험·실제 관찰과 발견한 실패

[최종 자원23조건](C:/Users/user/Desktop/SmartFactory/PDCA_RES128_20261013_3bc421b7/unit-r6.json) 및
[HTTP31조건](C:/Users/user/Desktop/SmartFactory/PDCA_RES128_20261013_3bc421b7/http-r3.json)은 exit0/skip0이다.
구조체 offset, 실제 디스크 단위 대조, PID·exe·장치 식별 변경, 권한 실패·빈 목록,
카운터 감소/NaN/bool/누락, 중단·주기 누락·경로 제한, 동일 origin의 실제 HTTP/자원 수집을 검사했다.
느린 fsync를 주입한 검사는 HTTP FAIL·누락을 보존하면서 별도 저장 시간120ms 이상을 확인했다.

초기18조건 중1개는 Windows 가상환경의 중계 프로세스 때문에 “정확히2프로세스” 가정이 틀려
실패했다. 후속22조건 중1개는 자식 인터프리터 준비 전에 트리를 읽어 MembershipChanged를
정상적으로 검출했다. 시험의 실제 부모 연결 검사와 자식 ready handshake를 보완했다.
두 실패의 stdout/stderr·소스 사본을 보존했으며 수집기의 변경 감지를 약화하지 않았다.

[420초 관찰](C:/Users/user/Desktop/SmartFactory/PDCA_RES128_20261013_3bc421b7/native-review.json)은
실제 Windows 개발 PC의 자체 loopback fixture와 그 프로세스를 사용했다.

| 항목 | 실제 결과 |
| --- | --- |
| 자원 | 85표본;120–420초61표본, 실제 span299.9970816초 |
| 자원 실제 간격 | 4987.3236–5012.0459ms; 무효 변화량 구간0 |
| 디스크 | PhysicalDrive0/1 원시값 확보; 장치·프로세스 읽기 오류0 |
| health | 예정210/실제209/누락1; 요청 오류·timeout0, 최대61.1058ms |
| data | 예정70/실제70/누락0; 요청 오류·timeout0, 최대50.3204ms |
| image | 예정1680/실제1663/누락17; 요청 오류·timeout0, 최대61.4813ms |
| 통합 HTTP 판정 | FAIL; 누락을 응답 성공으로 덮지 않음 |

관찰 helper의 exit0은 자료 수집·검산 성공이다. HTTP FAIL과 구분한다.
[누락 전후 대조](C:/Users/user/Desktop/SmartFactory/PDCA_RES128_20261013_3bc421b7/http-slot-diagnosis.json)에서
health140의 직전 요청은1.3279ms였고 fetch/해석이 다음 슬롯보다1997.8016ms 먼저 끝났다.
image1110–1125의 직전 요청1109도1.55ms였고 마지막 누락 슬롯보다3995.4071ms 먼저 끝났다.
따라서 지연은 fetch 반환 후 구간에 있었으나 당시 기록은 파일 저장과 스케줄링 원인을 분리하지 못한다.

후속 HTTP 코드에 `writes.json`을 추가해 파일 열기·쓰기·flush·fsync·닫기의 벽시계 시간을
응답 시간과 별도로 남겼다. 원시 저장의 내구성이나 누락 판정을 제거하지 않았다.
이 계측은 원인 규명을 위한 보완이며420초 실패가 해결됐다는 증거가 아니다.

420초 실행은 보존된 `source-r2` 바이트로 수행했다(HTTP `d863286f…`, 자원 `4e2c2a86…`).
그 뒤 추가한 자원 경로/마지막 표본 검사로 동일85개 원문을
[최종 코드 재판정](C:/Users/user/Desktop/SmartFactory/PDCA_RES128_20261013_3bc421b7/native-current-evaluator.json)했고
coverage 결과가 같았다. 최종 쓰기 시간 계측은 짧은 실제 수집·주입 회귀로 검증했으며
최종 바이트의 새420초 통합 관찰이나 오버헤드 검증을 완료했다고 주장하지 않는다.

## 재현·보존·남은 통합

개발 PC의 새 시험 폴더로 실행하는 예:

```powershell
$env:SFL_RESOURCE_TEST_ROOT = 'C:\Users\user\Desktop\SmartFactory\<새 실행 폴더>\unit-new'
& .\backend\.venv\Scripts\python.exe .\scripts\field-v1028\test_field_resource_sampling.py
```

상위 폴더는 먼저 만들고 `unit-new`는 존재하지 않아야 한다. 이 시험은 로컬 물리 디스크
카운터와 자체 프로세스/loopback fixture를 사용한다. 실제 제품/서버 QA 실행 명령이 아니다.

[최종 검산](C:/Users/user/Desktop/SmartFactory/PDCA_RES128_20261013_3bc421b7/verification.json)은
원문·본문·소스 SHA와 결과 manifest39개를 확인했다. 검산 helper·Ruff F/E9 실제 exit0.
4,781파일을 `Z:\SmartFactory\20261013\records\PDCA_RES128_3bc421b7`에 복사해 전체 SHA를 확인했다.
manifest 제외5,363,037바이트이며 기록 manifest SHA256은
`205a9e2d1a920a441949d0ae508721f4bd725f657b557b5c1ece77ee4b57eea4`다.
[공유 전송 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_RES128_20261013_3bc421b7/record-transfer.json)은 봉인 뒤 별도 보존한다.

다음 작업은 다음과 같다.

1. 새 쓰기 계측으로 실제 통합 수집의 슬롯 누락 구간을 분리하고 확인된 원인만 보완한다.
2. 최종 installer/설치 트리·프로세스/logger/fingerprint, backend 자원/큐, 화면/packet,
   정상 종료·delta를 동일 경계에 연결하고 전체 수집기의 오버헤드를 확인한다.
3. 동기 Windows 호출의 외부 watchdog과 보호된 결과 폴더·잠금 실행을 실제 현장 launcher에 연결한다.
4. 기존 서버 패키지 읽기 실행 결과, 실제3회 시작·15분/120분, R1–R6 조건과 승격·적용을 완료한다.

제품 소스·installer·운영 설정은 변경하지 않았다. 변경 범위가 검증 도구라 전체 health/NSIS 및
과거 전수 데이터 검사는 반복하지 않았다. 미서명 내부 정책, 현재541d/08C 롤백 기준,
`full_data_gate=NOT_EVALUATED`, R1–R6 HOLD와 전체 목표 active를 유지한다.
