# 현장 수집기: 느린 저장 분리와 불완전 결과 보존

2026-10-13. 느린 원문 저장이 다음 HTTP 요청을 지연하는 경로를 주입 시험으로 재현하고
대기열과 저장 worker를 분리했다. 최종 자원/저장28조건·HTTP31조건은 exit0이며,
수정본의 개발 PC420초 관찰에서1,960요청의 누락·오류·timeout0과 전체 저장을 확인했다.
과거 실제18슬롯 누락의 정확한 host 원인 및 이번 실제 ENOSPC 원인은 계속 미확정이다.
실제 서버·제품15분/120분 QA와 출시 승격 완료를 뜻하지 않는다.

## 재현된 문제와 변경

기준 HEAD는 `0a6375ae67cf1b8f75db18f69ffc2ac32b26162d`다.
[이전420초 관찰](production-release-risk-validation-resource-collector-20261013.report.md)의
누락은 fetch/해석 반환 뒤에 발생했으나 저장과 스케줄링의 시간을 분리하지 못했다.
이를 과거 timeout/drop의 원인으로 단정하지 않는다.

기존 동기 저장 코드에 fsync당120ms를 주입하고100ms 요청 주기를 요구했을 때
[수정 전 회귀](C:/Users/user/Desktop/SmartFactory/PDCA_PERSIST128_20261013_9ac57e4d/red.json)는
1조건 exit1로 실패했다. 같은 조건의
[수정 후 회귀](C:/Users/user/Desktop/SmartFactory/PDCA_PERSIST128_20261013_9ac57e4d/green.json)는 exit0으로,
4요청을 누락 없이 수집하고 모두 저장했다. 이는 주입한 저장 지연의 인과를 증명하며
이전 실제 host 지연의 정확한 원인을 소급 확정하지 않는다.

- [HTTP 수집기](../../scripts/field-v1028/field_http_sampling.py) SHA256:
  `e32ecdab54e3c02c9bfe67859c32016920780a82a43d3bb5da8f586df9e4fddb`.
- [자원·저장 회귀](../../scripts/field-v1028/test_field_resource_sampling.py) SHA256:
  `22f0dfc4f4fcdf7d895babc01fbe9e66bdc83a3108353a1bd1e615b71ab152c4`.
- 기존 자원 수집기와 HTTP 회귀 코드는 변경하지 않았다. 실행 소스는 묶음별 사본·SHA로 고정했다.
- 증거 루트: `C:\Users\user\Desktop\SmartFactory\PDCA_PERSIST128_20261013_9ac57e4d`.

요청 worker는 응답·해석·대기열 전달 뒤 다음 원래 주기로 이동한다. 저장 worker 하나가
body→metadata 순으로 각각 flush/fsync/close하고, 둘 다 완료한 요청만 persisted로 센다.
기본 한도는 저장 중인 자료를 포함해256레코드·직렬화 metadata+body64MiB다. 이는 Python
객체 overhead까지 포함한 전체 메모리 상한은 아니다. 기존 전체 body4GiB 예산도 유지한다.

대기열 한도 초과는 수집 실패다. 한도를 넘은 일부 원문을 보존하지 못할 수 있으며 해당
슬롯을 성공으로 세지 않는다. 이미 수락한 자료는 중단 시에도 배출하고 결과는 FAIL이다.
저장 실패는 오류·폐기 수와 생성된 부분 파일의 실제 길이/해시·failed_write 표시를 보존한다.
메모리에서 대기하는 바이트의 내구성은 아직 확정되지 않았다. 갑작스러운 프로세스 손실이나
최종 결과 쓰기 실패는 완전한 manifest/성공 결과가 될 수 없다.

`writes.json`, 제출/저장/폐기 수, 최대 적체, 배출 시작·완료 시각을 함께 기록한다.
느린 파일/드라이버 호출 자체를 강제로 중단하는 기능은 없으며 외부 watchdog은 현장
launcher 통합에서 필요하다. 제품 앱·장비·설정 제어는 추가하지 않았다.

## 실패를 보존한 검증 결과

[최종28조건](C:/Users/user/Desktop/SmartFactory/PDCA_PERSIST128_20261013_9ac57e4d/unit-final.json)은 exit0/skip0이다.
120ms 반복 저장 지연, 기본3채널의 첫 저장1초 정지, 대기 바이트/레코드 한도, 잘못된 한도,
저장 오류·부분 파일, 중단 시 수락 자료 배출을 검사했다. 기존 자원·식별·단위·누락 검사도 포함한다.
1초 정지 조건에서health4/data2/image25의31요청을 누락 없이 수집·저장했다.
[HTTP31조건](C:/Users/user/Desktop/SmartFactory/PDCA_PERSIST128_20261013_9ac57e4d/http-r2.json)도
같은 HTTP 바이트로 exit0/skip0이다.

중간에는 실제 `No space left on device` 오류가 있었다. 기준 코드의420초 시도는
`writes.json` 저장에서 exit1로 끝났고, 첫 HTTP31조건 실행은4개 오류로 exit1이었다.
또한 그 stderr를 UTF-8로만 출력하려던 외부 실행 기록기가 인코딩 오류를 냈다.
원시 stdout/stderr와 실제 child exit1은 이미 저장돼 있었으며 CP949로 전체를 읽어 확인했다.
불완전한 두 출력 폴더의3,603파일/47파일과0바이트 writes.json을 그대로 보존했다.
이를 유효한 수집 manifest나 PASS로 처리하지 않는다.

[오류 후 공간 관찰](C:/Users/user/Desktop/SmartFactory/PDCA_PERSIST128_20261013_9ac57e4d/storage-after-failure.json)에서
C:의 가용 공간은15,428,845,568바이트였고 이번 작업 폴더는3,937,417바이트였다.
작은 결과의 실제 flush/fsync를 확인한 뒤 동일 바이트로 실패한 HTTP 검사를 재실행했다.
재실행 통과는 ENOSPC의 원인·발생 순간의 공간 상태가 해결됐다는 증거가 아니다.
기존 자료를 삭제하거나 ACL·디스크 설정을 변경하지 않았다.

## 수정본420초 실제 관찰

[최종 관찰](C:/Users/user/Desktop/SmartFactory/PDCA_PERSIST128_20261013_9ac57e4d/candidate-run/native-review.json)은
실제 Windows 개발 PC의 자체 loopback fixture·프로세스·PhysicalDrive0/1을 사용했다.
수집 모듈은 최종 회귀 및 저장소 바이트와 같으며 기존 실행과 출력 폴더를 분리했다.

| 항목 | 실제 결과 |
| --- | --- |
| health | 210/210요청, 누락·오류·timeout0, 최대59.7644ms;50ms 경고1 |
| data | 70/70요청, 누락·오류·timeout0, 최대46.7136ms |
| image | 1680/1680요청, 누락·오류·timeout0, 최대50.9527ms |
| 저장 | 제출/저장1960/1960, 폐기0, 종료 시 대기0바이트/0레코드 |
| 최대 적체 | 3레코드, 직렬화 바이트3902 |
| 저장 시간 | 최대 파일162.3493ms; 요청 작업 종료 후 배출7.4557ms |
| 자원 | 85표본; 준비120초 뒤61표본, 실제 span300.0037689초 |
| 실제 자원 간격 | 4988.7245–5014.089ms; 무효 변화량 구간0 |
| 공간 동반 관찰 | 5초 간격 스냅샷의 C: 최소15,344,791,552바이트 |

helper 실제 exit0, 해당 HTTP 구성요소 PASS다. 함께 저장한3,921개 파일 쓰기 시각을
원문과 대조했다. 이 실행의 최대 저장 지연은1초 주입보다 짧았으며, 순차 실행과 host 부하가
다르므로 과거 실패와 엄격한 성능 A/B 비교라고 표현하지 않는다. 공간 표본 사이의 순간 상태,
제품 전체 오버헤드, 실제 서버 성능, 자원 누수 부재를 증명하지 않는다.

## 검산·보존과 다음 조건

[최종 검산](C:/Users/user/Desktop/SmartFactory/PDCA_PERSIST128_20261013_9ac57e4d/verification.json)은
manifest가 생성된 결과29개의 원문/body SHA와 실패한 부분 쓰기2개를 구분해 확인했다.
별도 불완전 폴더2개는 ENOSPC 증거로 분류했다. Ruff F/E9도 exit0이다.
공유 records의 파일 수·전체 해시 대조는
[전송 영수증](C:/Users/user/Desktop/SmartFactory/PDCA_PERSIST128_20261013_9ac57e4d/record-transfer.json)에 기록했다.
`Z:\SmartFactory\20261013\records\PDCA_PERSIST128_9ac57e4d`의8,256파일을 대조했다.
manifest 제외9,020,140바이트이며 기록 manifest SHA256은
`dfb8fd5b7f6cfd36235b1bb2050c138d63f73b4a313397555f5df45d9aba20a6`다.
봉인 뒤 문서/commit 검증 영수증은 기존 manifest를 바꾸지 않고 별도로 보존한다.

재현 예:

```powershell
$env:SFL_RESOURCE_TEST_ROOT = 'C:\Users\user\Desktop\SmartFactory\<새 실행 폴더>\unit-new'
& .\backend\.venv\Scripts\python.exe .\scripts\field-v1028\test_field_resource_sampling.py
```

상위 폴더를 먼저 만들고 unit-new는 새 경로여야 한다. 실제 로컬 디스크 카운터·자체
프로세스/loopback fixture를 사용하는 개발 검사다. 현장 실행 entrypoint는 아직 제공하지 않는다.

다음 순서는 최종 build/session·backend 자원/큐·화면/packet·종료 delta를 한 실행에 묶고,
보호된 결과·잠긴 실행·외부 watchdog과 전체 계측 부하를 검증한 뒤 실제 서버 QA를 연결하는 것이다.
기존 서버 패키지 읽기 결과, R1–R6 잔여 근거,3회 현장 시작·15분/120분·승격은 계속 남는다.
제품 소스·installer 변경이 없어 전체 health/NSIS·과거 전수 검사는 반복하지 않았다.
미서명 정책·현재541d/08C 운영/롤백·full_data_gate NOT_EVALUATED·출시 HOLD를 유지한다.
