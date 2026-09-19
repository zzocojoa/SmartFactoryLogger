# 운영 도구 오프라인 회귀시험

관리 목록이나 실제 서버 파일 없이 합성 fixture로 실행한다. 운영 설치·정리
entrypoint는 실행하지 않는다. Windows NTFS, Node 22, Windows PowerShell 5.1,
PowerShell 7이 필요하다.

```powershell
node scripts/run-ops-offline-tests.cjs
```

PowerShell 7이 PATH에 없다면 SFL_TEST_PWSH 환경변수에 pwsh.exe 절대 경로를
지정한다. 각 PowerShell 시험은 새 프로세스에서 실행한다. 실행별 요약은
.tmp/ops-offline-<UUID>/summary.json에 남는다. 기존 시험의 새 합성 fixture는
.tmp 또는 artifacts 아래 보존되며 이 runner는 재귀 삭제하지 않는다.

## 실행 범위와 한계

- 관리기 명령의 PARTIAL 상태 차단 및 dist 합성 계약 시험 포함.
- r2 설치 도우미는 실제 AssertBackup 함수까지 실행하되 원본/백업/복원은 모두
  fixture이며 앱 상태와 호스트 ACL 검사는 mock이다. COM 설치는 호출하지 않는다.
- dist PowerShell 시험의 관리자 ACL/copy 검사는 비관리자 실행 시 생략된다.
  summary.json의 administrator_acl_copy_tests 값을 확인한다.
- repair-dependency-acl 시험은 -PureOnly로 실행한다. 비관리자 Set-Acl 권한 실패를
  통과로 간주하지 않으며 네이티브 ACL 상속 검사는 별도 관리자 세션에서만 수행한다.
- 실제 전송 ZIP·과거 서버 영수증·배포본이 필요한 8개 시험은 제외한다.
  정확한 제외 목록은 runner와 summary.json에 있다. 제외는 통과를 뜻하지 않는다.
- 이 시험 통과는 서버 실행·설치·삭제·운영 승인이나 장시간 안정성 검증이 아니다.
- 개인 관리 파일 verification-files.local.json, artifacts, .tmp는 Git 대상이 아니다.
  시험 fixture 원본은 scripts 아래만 둔다.

## 역사적 실행본

이미 배포된 해시 결합 도우미는 변경하지 않는다. 설치 결함 수정은
server-stage-v1026/install-v1026-after-minimal-backup-r2.ps1과 별도 builder에만
있다. r1은 과거 증거 대조용이며 신규 실행 대상으로 선택하지 않는다.
