# 루트·inbox 권한 정정

## 승인된 두 폴더만 변경

서버에서 제공한 ACL과 사용자의 두 폴더 정정 승인을 바탕으로 한다.

1. `C:\ProgramData\SFLOps\inbox`: 작업자 소유자와 세 SID의 FullControl을 보존한다.
   상속된 규칙을 동일 권한의 명시 규칙으로 바꾸고 상속을 차단한다.
2. `C:\ProgramData\SFLOps`: 관리자 소유자와 SYSTEM/Administrators 규칙을 유지하고,
   `S-1-5-21-2762931165-1280404403-2847611662-1001`의 명시 FullControl 한 항목만 제거한다.

inbox는 계속 사용자 소유의 **신뢰하지 않는 전송 경로**다. 그 안의 파일을 검증 없이
관리자 권한으로 실행해도 된다는 뜻이 아니다. 기존 설치 확인 도우미의 안전 검사는 완화하지 않는다.

## 전달 및 실행

- `repair-sflops-root-inbox-r1.ps1`과 `.sha256.txt` 두 파일만 서버 Desktop의 SmartFactory로 옮긴다.
- 새 관리자 **64비트 Windows PowerShell 5.1** 창에서 `RUN_ON_SERVER.txt` 전체를 붙여넣는다.
- 실행문에 고정된 외부 SHA256 및 길이가 맞는 읽기 잠금 스트림만 실행한다. sidecar만 신뢰하지 않는다.
- 사용자 승인에 따라 별도 승인 토큰 질문 없이 사전검사 후 정확히 두 ACL을 변경한다.
- 실행 중 SFLOps/inbox 파일 전송, 이동, ACL 편집을 하지 않는다. 앱은 그대로 둔다.
- 탐색기가 SFLOps 접근 권한을 추가하겠다는 “계속” 안내를 보여도 승인하지 않는다.
- 새 결과는 `C:\ProgramData\SFLOps\tmp\root-inbox-acl-<GUID>` 아래에만 생성된다.
  결과를 찾으려고 탐색기 권한을 변경하지 말고, 콘솔의 마지막 짧은 JSON 요약을 전달한다.

## 변경 전후 확인

루트와 inbox의 소유자·상속·SID·허용 유형·권한·상속 플래그는 사용자 출력과 일치해야 한다.
루트 직계 항목은 backups/inbox/inventory/runs/tmp 다섯 폴더여야 한다. 나머지 네 폴더는
상속 차단 상태를 요구하고, 기록 폴더의 부모 tmp는 정확한 관리자/SYSTEM 전용 ACL을 요구한다.
기존 inventory의 추가 권한 제거 등 다른 정정은 포함하지 않는다.

inbox 하위 항목은 파일 내용을 읽지 않고 이름·종류·파일 ID·Owner/Group/DACL을 기록한다.
최대 5,000 하위 항목, 깊이 32, 경로 240자, 실행 120초 예산을 초과하면 HOLD한다.
시간은 항목 사이에서 확인하며 개별 OS 호출에 대한 강제 중단 시간은 아니다.
재분석 지점, 파일 hardlink, 접근 실패, 예상 밖 규칙, 동시 항목/ACL 변경은 거부한다.
핸들로 기존 경로의 삭제·이름 변경을 막고, 각 변경 직전/직후 전체 범위를 재확인한다.

원래 Owner/Group/DACL을 `before-acl.json`에 CreateNew로 저장하고 재읽기 SHA256과 읽기 잠금을
확인한 뒤 변경한다. SACL과 파일 내용은 백업하지 않는다. `journal.jsonl`에 변경 전 INTENT와
변경 후 VERIFIED를 즉시 디스크에 기록한다. 정상 완료 시 `result.json`도 생성한다.

inbox 규칙 변환은 메모리에서 완성한 다음 한 번만 저장한다. 빈 ACL을 중간에 저장하지 않는다.
상속 차단 메서드의 `preserveInheritance` 동작과 Windows의 ACE 전파를 기준으로 검증했다.
[Microsoft: 상속 보호](https://learn.microsoft.com/en-us/dotnet/api/system.security.accesscontrol.objectsecurity.setaccessruleprotection?view=netframework-4.8.1),
[Microsoft: ACE 전파](https://learn.microsoft.com/en-us/windows/win32/secauthz/automatic-propagation-of-inheritable-aces).

대상 외 항목의 Owner/Group/DACL은 비교하며, Windows가 추가하는 DACL auto-inherited 제어 비트의
0→1 변화만 허용한다. 권한/SID/소유자/그룹/보호 상태 변화는 허용하지 않는다.

## 실패·복구·검증 한계

두 폴더 변경은 원자적이지 않다. inbox만 보호된 뒤 루트 변경이 실패할 수 있다.
이 경우도 기록을 보존하고 자동 재실행·롤백하지 않는다. attempted는 호출 시도 수,
returned는 쓰기 API 정상 반환 수이며, 사후 검증 성공 수와 다르다.
복구가 필요하면 보관한 SDDL과 현재 상태를 별도로 대조해 승인 후 수행한다.
루트의 과도한 권한을 자동으로 다시 부여하지 않는다.

잠금은 새 자식 생성이나 ACL 편집을 원자적으로 막지 못한다. 이미 열린 핸들의 권한도
소급 철회하지 않는다. 이전 증거가 과거에 변조되지 않았음을 입증하는 절차가 아니다.
파일 삭제/이동, 앱 조회·종료·재시작, 설치, HTTP, Canary, DB 마이그레이션은 수행하지 않는다.

로컬 시험은 함수 AST만 로드한다. 정확한 운영 ACL은 메모리로, 실제 NTFS 변경·실패 처리는
격리된 개발자 소유 fixture로 확인한다. 비관리자 개발 환경이므로 fixture 검증기의
소유자 기대값만 개발자 SID에 맞춘다. 배포 함수와 서버 엔트리포인트는 변형하지 않는다.
실제 서버 관리자 토큰·실제 현장 폴더 통합 실행은 아직 수행하지 않았다.
실패 fixture와 기존 해시 결합 도우미는 삭제·수정하지 않는다.

성공 결과는 `SFLOPS_ROOT_INBOX_ACL_REPAIR_PASS`다. 이것은 두 폴더 권한 정정만 뜻한다.
v1.0.26 설치 파일 검사 재개나 운영 승인으로 간주하지 않는다.
