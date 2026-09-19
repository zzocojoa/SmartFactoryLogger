# AGENTS.md

## Codex App 병렬 운영

Codex app에서 여러 thread/worktree를 사용할 때는
[Codex App 병렬 Thread 운영 규칙](docs/V2/05_운영_배포/codex_app_parallel_thread_operating_rules.md)을
따른다.

기본값:

- Local thread 1개
- Worktree thread 최대 2개
- Subagent는 읽기 작업 전용

공식 문서가 권장 thread 수를 정한 것은 아니다. 이 기준은 SmartFactoryLogger
v2_next의 충돌 방지와 최종 검증 책임을 명확히 하기 위한 내부 운영 규칙이다.

## 서버 검증 경로와 정리

이후 새 서버 검증·배포 준비·백업 도우미는
[서버 검증 경로와 정리 기준](docs/V2/05_운영_배포/server_validation_path_policy.md)을 따른다.
관리 루트는 `C:\ProgramData\SFLOps`로 고정하고 실행별 자식 폴더를 사용한다.
기존 해시 결합 도우미/증거를 자동 변경·이동하지 않는다. 운영 AppData/설치 폴더는
별도 데이터 이관 없이 이 기준으로 옮기지 않는다. 탐색 결과는 삭제 승인이 아니다.
