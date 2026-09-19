# v1.0.26 설치 경계 정정본 r2

기존 `install-v1026-after-minimal-backup.ps1` 및 기존 ZIP/영수증은
`LEGACY_PINNED` 이력으로 보존한다. 신규 실행에는 사용하지 않는다.
r2도 과거의 정확한 stage/backup에 결합된 도구이며 일반 업그레이더가 아니다.
이미 v1.0.26을 실행한 서버에서 재설치하는 절차가 아니다.

## 새 검사

- 승인 전과 설치 실행 직전에 backup/restore 양쪽의 실제 파일·해시·membership을 검사한다.
- 원본 profile/layouts/state-source의 내용·메타데이터가 백업 시점과 같아야 한다.
- 실제 AppData의 8개 state 파일도 state-map과 대조하며, 당시 없던 두 파일/폴더가 나타나면 HOLD한다.
- 승인 입력 후 중지 상태를 다시 확인한다. 마지막 전체 검사와 COM 실행 사이에는
  추가 입력·복사·컴파일·영수증 기록이 없다. 프로세스/포트 조회 실패도 HOLD한다.
- 검사는 시점별 확인이며 다른 관리자와의 동시 실행을 원자적으로 차단하지는 않는다.
  단일 작업자와 승인된 유지보수 창이 필요하다.

## 오프라인 검증

`test-install-cold-boundary-r2.ps1 -OutputRoot <새 합성 시험 폴더>`를
native x64 Windows PowerShell 5.1에서 실행한다. 서버 main/설치/네트워크는 실행하지 않는다.
시험은 기존 C# 소스를 컴파일하며 누락·변조·추가 파일, 원본 상태 변경,
승인 대기 중 재시작 및 조회 실패를 합성 데이터로 검사한다.

## 전송과 실행 제한

별도 r2 builder는 시험 영수증의 외부 해시와 helper 해시를 확인한다.
기존 검증된 `cold-backup-core.dll`(19,456 bytes, SHA256
`3B8B3649C623EB8A7112C762D95A00AD9745231291C50CCC2B66E0AA2C7F8A71`)도 필요하다.
새로 컴파일한 DLL을 같은 바이트라고 간주하지 않는다.

패키징·CI 통과는 서버 실행 승인이 아니다. 새 ZIP/helper/DLL을 외부 해시로 검증하고
새 SFLOps 보호 실행 폴더에 배치하는 launcher와 현장 유지보수 승인은 별도이다.
확인되지 않은 launcher를 임의로 만들거나 r1 launcher의 해시만 바꾸지 않는다.
앱이 켜져 있거나 원본이 이미 변경됐으면 HOLD하며 백업을 덮어쓰지 않는다.

최소 백업 제외 데이터(CSV/이미지/fact 로그, snapshots, 설치 폴더), unsigned 내부용
설치본, 실제 사용자 토큰/COM 실행·다운그레이드 복구 미검증 제한은 그대로다.
HOLD 시 출력과 생성물을 보존한다. 강제 종료·자동 재시도·롤백·Canary를 실행하지 않는다.
