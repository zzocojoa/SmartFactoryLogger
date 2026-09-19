# SFLOps 두 폴더 ACL 정정

## 승인 범위

이 도우미는 서버에서 확인된 추가 권한 한 항목만 다음 순서로 제거한다.

1. `C:\ProgramData\SFLOps\inventory`
2. `C:\ProgramData\SFLOps`

제거할 SID는 `S-1-5-21-2762931165-1280404403-2847611662-1001`이며,
명시적 Allow / FullControl / ContainerInherit+ObjectInherit / Propagation None
항목 하나여야 한다. Administrators 소유자, 상속 차단, SYSTEM과 Administrators의
기존 FullControl 항목은 유지한다. 그룹도 변경하지 않는다.

`SFLOps\tmp`는 이미 관리자/SYSTEM 전용이므로 정정 대상이 아니다.
재귀 ACL 초기화, 원본 파일 삭제, 정리 재실행, 앱 조회·종료·재시작,
설치·롤백은 하지 않는다. 서버 전체 정리 완료나 운영 승인도 아니다.

## 전달과 실행

새로 전달할 파일은 두 개다.

- `repair-sflops-acl-r2.ps1`
- `repair-sflops-acl-r2.ps1.sha256.txt`

두 파일을 서버 `C:\Users\user\Desktop\SmartFactory`에 복사한다.
이미 전송한 다음 파일은 그대로 보관한다. 다시 압축을 풀거나 실행하지 않는다.

`C:\Users\user\Desktop\SmartFactory\v1019-release-pair-cleanup-ready-r1.zip`

기존 ZIP의 길이 22,604bytes와 SHA256
`62CCE5F9B9E020FE859ABEA2977EAF366A0945C5C402B2839632C00A952065F3`를 재검증하고,
그 안의 해시가 고정된 공통 함수 두 파일만 메모리로 읽는다.
삭제 도우미의 본문은 실행하지 않는다.

관리자 **64비트 Windows PowerShell 5.1**에서 이번 배포의 `RUN_ACL_REPAIR.txt`
내용 전체를 붙여넣는다. 실행문은 새 스크립트의 길이/외부 고정 SHA256/sidecar를
검증하고 읽기 잠금을 유지한다. 새 `-NoProfile` 프로세스에서도 동일한 외부 해시와
길이를 확인한 뒤, 바로 그 잠근 스트림의 바이트로 ScriptBlock을 만들어 `-Execute`로
실행한다. 해시 확인 후 경로를 다시 여는 `-File` 방식은 사용하지 않는다.
이 사용자 승인은 ACL 정정만 포함하며 삭제 재시도 승인은 아니다.

개발 PC의 `server-acl-repair-r1`은 실행문 보강 전 초안이다. 서버로 전달하거나
실행하지 말고 이번 `server-acl-repair-r2` 전달물만 사용한다. 정정 스크립트 본문은
동일하며, R2에서 검증한 바이트와 실행 바이트의 결합을 보강했다.

실행 중 SFLOps 폴더를 다른 도구로 변경하지 않는다. 탐색기에서 접근 권한을 부여하는
“계속” 등의 안내를 승인하지 않는다. 기존 추가 ACE가 어떤 도구에서 언제 생겼는지는
확인되지 않았으며, 이 안내가 원인을 확정하는 것은 아니다.

## 변경 전 보호 조건

- 두 대상은 사용자 출력과 같은 정확한 3개 ACE/소유자/상속 상태여야 한다.
- `tmp`는 정확한 SYSTEM+Administrators 2개 ACE 상태여야 한다.
- 두 대상의 모든 직계 자식은 파일도 포함해 DACL 상속이 차단돼 있어야 한다.
  하나라도 상속받는 항목이 있으면 부모 ACL 변경 전에 HOLD한다.
- 직계 항목 수/경로/종류/파일 ID/Owner·Group·DACL을 기록하고 변경 전후 재확인한다.
- reparse 경로, 파일 hardlink, 접근 실패, 예상 밖 권한이나 동시 변경은 HOLD한다.

부모의 상속 가능한 ACE 제거는 상속받는 자식에 전파될 수 있으므로, 보호된 직계 자식
경계가 확인돼야 한다. 이 조건을 통과시키려고 하위 폴더의 상속을 자동 변경하지 않는다.
[Microsoft: ACE 자동 전파](https://learn.microsoft.com/en-us/windows/win32/secauthz/automatic-propagation-of-inheritable-aces)

## 백업과 결과

첫 ACL 쓰기 전에 새 관리자/SYSTEM 전용 폴더를 만든다.

`C:\ProgramData\SFLOps\tmp\acl-repair-<고유 ID>`

- `before-acl.json`: 원래 두 대상과 직계 자식의 Owner/Group/DACL 기록
- `before-acl.json.sha256.txt`: 백업을 다시 읽어서 검증한 해시
- `acl-repair.jsonl`: 변경 의도와 변경 후 검증, COMPLETE 또는 가능한 경우 HOLD

SACL은 읽거나 변경하지 않는다. 원래 ACL 기록이므로 파일 내용·앱 데이터 백업은 아니다.
대상 정정 전 실패하더라도 새 기록 폴더/백업 파일은 생성됐을 수 있다.

성공 결과는 `SFLOPS_EXACT_TWO_FOLDER_ACL_REPAIR_PASS`이며, 정확히 두 ACL 쓰기 후
대상과 직계 자식 경계를 다시 검증한다. 새 스크립트를 재실행하면 원래 3개 ACE
조건에 맞지 않으므로 자동 재실행하지 않는다.

성공하거나 HOLD하면 **출력 전체**를 제공한다. 정리 명령을 바로 재실행하지 않는다.
후속 삭제 전에는 보존 자료와 기존 정리 기록의 무결성을 별도로 재검증해야 한다.

## 실패와 복구 한계

두 폴더 변경은 하나의 원자적 작업이 아니다. 첫 폴더만 변경된 뒤 두 번째에서
실패할 수 있다. `attempted`와 `returned_success`는 각각 API 호출 시도와 정상 반환
횟수다. 정상 반환만으로 사후 검증 완료를 의미하지 않으며, 호출 도중 예외가 나면
해당 폴더 상태도 다시 읽어야 한다. 기록 실패 시 마지막 의도 기록까지 보존한다.

자동 롤백은 하지 않는다. 복원이 필요하면 `before-acl.json`과 현재 ACL을 대조한 뒤
별도 검토한다. 자동 복원으로 불필요한 FullControl을 재부여하지 않는다.
기존 파일과 정리 ZIP은 삭제하지 않으므로 이 단계에 데이터 복원 작업은 없다.

경로 핸들은 경로 교체를 막는 용도이며 ACL 편집/새 자식 생성을 원자적으로 잠그는
기능은 아니다. 각 단계 재확인으로 관측된 변경을 거부하지만 모든 동시 변경을
원천 차단한다는 보장은 없다. 기존 열린 핸들의 권한도 소급 철회하지 않는다.

기존 ACL 객체에서 해당 ACE만 제거하고 DACL만 저장한다. Windows가 저장 과정에서
추가할 수 있는 `SE_DACL_AUTO_INHERITED` 플래그 하나의 0→1 변화만 별도로 허용한다.
그 외 플래그/ACE/소유자/그룹 변화는 실패한다.
[Microsoft: Directory.SetAccessControl](https://learn.microsoft.com/en-us/dotnet/api/system.io.directory.setaccesscontrol?view=netframework-4.8.1)

## 로컬 검증 범위

네이티브 PowerShell 5.1에서 테스트 60개를 통과했다. 정확한 운영 ACL 형태는
메모리에서 검사했고, 실제 NTFS ACE 제거/직계 자식 보호/중간 실패는 새 개발자 소유
격리 폴더에서 검사했다. 테스트 검증기에만 개발자 SID를 대입했으며 배포 코드와
ACL 변경 함수는 해당 대입으로 수정하지 않았다.

실행문 검사는 추가 10개를 통과했다. 별도 합성 파일로 새 자식 프로세스의 정확한
바이트 실행과 일반 텍스트 진행 출력을 확인하고, 길이/해시 불일치 및 잘못된 UTF-8은
실행 전에 거부했다. 서버 도우미나 서버 경로는 이 시험에 사용하지 않았다.

실제 서버 실행과 관리자 소유 폴더를 사용하는 전체 통합 시험은 수행하지 않았다.
제품 코드 변경·DB 마이그레이션·Canary 실행은 없으며 제품 테스트 대상도 아니다.
