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
