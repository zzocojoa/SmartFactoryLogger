# 운영 데이터 사본 사전 검사와 추가 스트림 진단

작성일: 2026-10-12. 상태: 종료 전 사전 검사 HOLD, 첫 거절 경로 확인 완료.
목표는 선택한 운영 AppData 두 루트의 검증용 사본 한 벌이다. 전체 서버/NAS,
앱 복구나 전체 데이터 QA 완료를 뜻하지 않는다. `full_data_gate=NOT_EVALUATED`,
`formal_release_gate=HOLD`, goal `active`를 유지한다.

## 현재 작업 정보와 저장 공간

사용자는 현재 생산 제품번호·금형번호를 `60332, 6 유지`로 확인했다.
원격 화면을 다시 열었을 때 이미 두 값이 `적용됨`이었고, 표시된 최근 적용은
2026-10-12 21:59:48 KST였다. Codex는 값을 다시 제출하지 않았다.
`서버 값 새로고침` 뒤에도 두 값과 Running 상태를 확인했다.
과거 12:34:51 적용 및 그 이후 필수값 미입력 관찰은 그대로 보존한다.
초기화 원인과 재시작 후 지속성은 아직 검증하지 않았다.

서버 탐색기에서 C 드라이브 여유 공간은 70.5GB 표시값이었다.
서버 Z는 `\\192.168.0.235\스마트팩토리`에 연결되며 속성의 여유 공간은
2,123,449,217,024바이트였다. NAS 속성의 NTFS 표시는 물리 파일시스템 증명이 아니다.
live `test_data` 화면에는 620항목과 증가하는 이미지/observation fact가 보였다.
따라서 Running 상태에서 탐색기로 복사한 자료를 일관된 종료 사본으로 간주하지 않는다.

## 한 벌 사본 도우미

과거 2026-09-20에 사용자가 중단한 세 루트 전체 backup/restore 도우미를 재실행하지 않았다.
기존 실패·부분 사본과 [과거 취소 기록](../V2/05_운영_배포/temperature_field_cold_backup_20260920.md)을 보존한다.

새 도우미는 다음 두 루트를 선택한다.

```text
C:\Users\user\AppData\Roaming\SmartFactoryLogger
C:\Users\user\AppData\Roaming\smart-factory-logger-v2
```

- Running 상태에서 경로·수량·실제 용량을 먼저 검사한다. 필요 공간은 원본 한 벌 bytes +
  10% + 파일/폴더당 8KiB + 10GiB reserve다. 준비 완료를 확인하기 전에는 앱을 종료하지 않는다.
- 결과는 실제 Desktop의 `SmartFactory\Q<6자리>\c\r0|r1`이다.
  현재 접두부 47자가 원본 루트 48/53자보다 길어지지 않음을 확인했다.
- 도우미는 앱을 닫거나 강제 종료하지 않는다. 준비 완료 후 정상 UI 종료를 별도로 수행하고,
  앱/backend/8000 부재를 반복 확인한 뒤 한 벌 복사 및 원본/사본 최종 해시·membership을 검사한다.
- 새 결과 자식에만 관리자/SYSTEM 쓰기와 운영 사용자 읽기를 적용한다.
  부모/원본 ACL, 설정, 설치본, 장비 설정, attestation을 변경하지 않는다.
- 실제 동일 세대 정상 종료 영수증, 모든 저장 경로, schema/이미지 decode 및 재시작은 별도 검증이다.

개발 기록은 `C:/Users/user/Desktop/SmartFactory/PDCA_COLD_20261012_b13afe6c`다.
private 원본·프로필 식별자는 Git 문서에 추가하지 않았다.

| 묶음 | 서버 최종 폴더 | 외부 고정 manifest SHA256 |
|---|---|---|
| 선택 사본 | `C:\Users\user\Desktop\SmartFactory\SFL_COLD_COPY_b13afe6c` | `74CA55CF37032877FE9A29FE5FFAF20606F25DBCF8B3EE040F64FC33AC79F80B` |
| 읽기 전용 추가 진단 R2 | `C:\Users\user\Desktop\SmartFactory\SFL_STREAM_READ_b13afe6c_r2` | `B6ED4C8A17C076278FDB7B658B00F8E9ABB6F0529C2752A948627D80EAB08593` |

두 묶음 각각 payload 4개와 manifest, 별도 실행 TXT를 Z의 날짜별 send 아래 전달했다.
Codex가 원격 탐색기로 서버 최종 로컬 폴더까지 복사하고 실제 절대경로/5파일/TXT 열림을 확인했다.
개발 원본→공유 사본 6파일의 길이/해시 대조는 각각 exit 0이다.
화면상 존재 확인 자체를 서버 로컬 해시 측정으로 보고하지 않는다.
수동 실행 carrier는 외부 manifest pin과 payload 이름·수·크기·해시를 검사하고,
모든 입력의 Read 공유 잠금을 유지한 채 같은 helper 바이트를 ScriptBlock으로 실행한다.

## 실제 서버 실패와 원인

사용자가 첫 TXT 본문을 관리자 Windows PowerShell 5.1에서 실행했다.
2026-10-12 22:12:50 KST의 `Qac981f/hold.json`은
`live-capacity-and-path-preflight`의 `COLD_BACKUP:alternate-data-stream`을 기록했다.
`READY_FOR_NORMAL_APP_EXIT`에 도달하지 않았고, 앱 종료·사본 복사를 수행하지 않았다.
수량/용량 검사도 완료되지 않았다. 셸의 전체 종료 코드는 별도 수집되지 않았다.

원래 엔진의 추가 스트림 거절 규칙을 보존한 읽기 전용 R2를 준비했다.
예외에 실제 path/name/bytes를 추가했으며 앱 제어·복사 API를 호출하지 않는다.
사용자가 새 R2 TXT를 실행한 결과, 22:29:56 KST의 `S0d62f0/result.json`은 다음을 확인했다.

```text
status = READ_ONLY_FIRST_BLOCKER_IDENTIFIED
blocking_source_path = C:\Users\user\AppData\Roaming\SmartFactoryLogger\logs\test_data\CLOSE_ONCE_AFTER_APPROVAL.cmd
stream_name = :Zone.Identifier:$DATA
stream_bytes = 26
source_file_content_read = false
copy_created = false
app_close_requested = false
original_ACL_or_stream_changed = false
```

이는 첫 거절 경로의 추가 스트림 메타데이터다. 스트림 본문이나 CMD 본문을 읽지 않았고,
전체 추가 스트림/파일 목록 검사도 완료하지 않았다. 다른 추가 스트림의 존재는 아직 미확인이다.
현재 거절의 직접 원인은 이 스트림에 대한 사본 엔진의 지원 부재다.
원본 파일/스트림을 삭제하거나 Unblock하지 않았다.

첫 실패의 `hold.json`, `intent.json`은 탐색기로
`Z:/SmartFactory/20261012/return/PDCA_COLD_b13afe6c_R1`에 회수했다.
공유→개발 사본 해시 대조 exit 0이며, 서버 콘솔의 해당 파일 해시는 없었다.
R2 결과는 별도 `return/PDCA_STREAM_READ_b13afe6c_R2`로 회수했다.
콘솔·공유·개발 사본 SHA256은 모두
`A91AC34DB0326AAE36D09D8437A9CDA9062716F8FEE2D59505F16207C899E466`과 일치한다.
첫 콘솔 해시 수기 전사는 `36D09D84`의 `8`을 `B`로 입력해 대조 exit 1이었다.
원래 화면과 재대조해 전사 오류를 바로잡은 뒤 exit 0이며, 공유/개발 사본 바이트 차이는 없었다.

## 개발 검증과 한계

| 실제 실행 | 결과 |
|---|---|
| `test-cold-operating-copy.ps1` 최종 실행 | native PS5.1 검사 21건, exit 0. 한 벌 복사·원본/사본 변경·membership·runtime/port·충돌/공간 경계 |
| 기존 `test-cold-backup.ps1`와 동일 core DLL | 58 assertions, exit 0. server main 미실행 |
| `build-pinned-command.ps1` | carrier 5건, native exit 0. 외부 pin/변조/extra member/Read 잠금 |
| `test-stream-diagnostic.ps1` 최종 실행 | 4건, native exit 0. 파일/폴더 ADS path/name/bytes, stream/일반 원본 보존, 사본 미생성 |
| R2 carrier | 5건 PASS. payload/manifest 검사와 별도 최종 전송 대조 exit 0 |

첫 사본 wrapper는 8자리 결과 이름의 접두부가 49자여서 원본 48자보다 길어졌다.
6자리 이름으로 수정했고 기존 결과 충돌 시 HOLD 파일을 쓰지 않는 guard를 추가한 최종 21건을 실행했다.
R2 첫 fixture는 .NET Framework 경로 API가 ADS 경로를 지원하지 않아 exit 1,
다음 fixture는 PowerShell의 `New` constructor 이름 충돌로 exit 1이었다.
새 합성 경로에서 Win32 stream fixture를 사용하고 메서드명을 수정한 최종 4건이 통과했다.
R2 packaging의 첫 프로세스는 같은 프로세스 script 실행 뒤 미설정 `$LASTEXITCODE` 조회로 exit 1이었다.
carrier 5건은 그 전에 끝났으며, 해당 후처리를 고치고 실제 묶음의 manifest/payload 및 전송 해시를
별도 exit 0으로 검증했다. 실패를 실제 서버/원본 변경이나 성공으로 바꾸지 않는다.

제품 소스는 직전 전체 `npm run health` exit 0 이후 바뀌지 않았다.
이번 private 도우미·문서 변경 때문에 제품 health를 반복하지 않았다.
위 검사 통과는 서버 사본 완료나 R4 PASS가 아니다.

## 다음 실행 기준

1. 원본 및 첫 실패/R2 증거를 보존한다. 원본의 추가 스트림을 삭제·변경하거나 검사에서 제외하지 않는다.
2. 추가 스트림을 복사본에도 보존하고 원본/사본 해시·스트림 집합을 검산하는 도우미를 준비한다.
   지원하지 못하는 스트림은 정상 종료 전에 구체적 경로와 함께 HOLD해야 한다.
3. 새 묶음/해시/회귀/최종 서버 전달을 완료한 뒤 사용자에게 필요한 수동 실행 시작만 안내한다.
4. 준비 완료 및 실제 공간을 확인한 후 정상 종료한다. 동일 세대 종료 영수증과 최종 사본을 검증하고
   같은 승인 운영 앱의 재시작·수집 재개를 확인한다. 강제 종료나 이전 묶음의 재사용은 하지 않는다.
5. 불변 사본에 CSV·metadata·observation·이미지/fact/manifest 검사를 적용한다.

원격 실행은 [경로 정책](../V2/05_운영_배포/server_validation_path_policy.md)을 따른다.
Computer Use의 `SKILL.md`가 필수로 지정한 `guidance.md`는
“Do not run Windows terminal commands via UI automation directly or indirectly.”라고 제한한다.
Codex가 서버 로컬 전달과 회수를 담당하고 수동 실행 시작만 사용자 조작으로 넘긴 이유다.
미서명 정책·역할 확정·장비 모델 미정은 유지하며 설치/운영 승격/롤백 기준 갱신은 없었다.
