# Codex App 병렬 Thread 운영 규칙

`작성일: 2026-06-29`
`범위: SmartFactoryLogger v2_next 개발 운영`

## 1. 목적

Codex app에서 여러 작업을 동시에 진행할 때 코드 충돌, 검증 누락, 운영 리스크를
줄이기 위한 프로젝트 내부 운영 규칙이다.

이 문서는 OpenAI 공식 문서가 정한 "권장 thread 수"가 아니다. 공식 문서는 병렬
thread, worktree, subagent, automation 기능을 설명하지만, 몇 개의 thread를 써야
하는지 숫자로 정하지 않는다.

## 2. 문서 근거

- Codex app: https://developers.openai.com/codex/app
- Codex app features: https://developers.openai.com/codex/app/features
- Worktrees: https://developers.openai.com/codex/app/worktrees
- Subagents: https://developers.openai.com/codex/subagents
- Automations: https://developers.openai.com/codex/app/automations

## 3. 프로젝트 기본값

SmartFactoryLogger v2_next에서는 다음 구성을 기본 운영값으로 사용한다.

| 역할 | 기본 수 | 쓰기 권한 | 목적 |
| --- | ---: | --- | --- |
| Main Local thread | 1 | 허용 | 작업 분해, 최종 통합, 최종 검증 |
| Worktree thread | 최대 2 | 제한 허용 | 서로 독립적인 구현 작업 |
| Subagent | 필요 시 | 원칙적으로 금지 | 조사, 리뷰, 테스트 분석 |

이 숫자는 공식 권장값이 아니라 이 저장소의 안전한 시작점이다. 변경 범위가 작거나
같은 파일을 만질 가능성이 높으면 Local thread 1개만 사용한다.

## 4. 역할 분리

### 4.1 Main Local thread

Main Local thread는 항상 하나만 둔다.

담당 범위:

- `AGENTS.md`, `README.md`, package 파일, CI/test 설정 확인
- 작업을 독립 단위로 분해
- Worktree thread에 넘길 범위 결정
- 각 thread 결과 검토
- 최종 `npm run health` 또는 관련 부분 검증 실행
- 최종 commit, push, PR 준비

Main Local thread가 최종 판단과 통합 책임을 가진다.

### 4.2 Worktree thread

Worktree thread는 독립 구현 단위에만 사용한다.

허용 조건:

- 수정 파일 경로가 다른 worktree와 겹치지 않는다.
- shared type, shared util, migration, package 설정을 동시에 수정하지 않는다.
- 작업 완료 후 변경 파일, 테스트 결과, 남은 리스크를 Main Local thread에 보고한다.

금지 조건:

- 같은 파일을 두 worktree가 동시에 수정한다.
- 같은 테스트 fixture 또는 같은 데이터 계약을 병렬로 바꾼다.
- 운영 설정, 배포 스크립트, DB/schema 성격의 변경을 동시에 나눈다.

### 4.3 Subagent

Subagent는 읽기 중심 작업에 사용한다.

허용 작업:

- 주변 코드 패턴 조사
- 보안/권한 누락 가능성 리뷰
- 테스트 커버리지 공백 분석
- 실패 로그 원인 후보 정리
- PR diff 리뷰

기본 원칙:

- Subagent는 코드를 수정하지 않는다.
- 코드 수정을 맡길 필요가 있으면 별도 Worktree thread로 승격한다.
- Subagent 결과는 Main Local thread가 검증한 뒤 반영한다.

## 5. 병렬화 판단 기준

병렬화 가능:

- backend API 수정과 frontend UI polish처럼 파일 경계가 명확히 다르다.
- 테스트 추가가 각 모듈 내부에만 닫혀 있다.
- 문서 작업과 코드 작업이 서로 다른 PR로 분리 가능하다.
- 조사/리뷰처럼 읽기 중심 작업이다.

병렬화 금지:

- 같은 shared type 또는 API contract를 여러 작업이 함께 만진다.
- CSV schema, 설정 저장 포맷, 배포 패키징처럼 하위 호환성이 중요한 변경이다.
- 마이그레이션, rollback, operational toggle이 필요한 변경이다.
- 테스트 실패 원인이 아직 불명확하다.

## 6. 표준 운영 절차

1. Main Local thread에서 작업 목적과 위험도를 정의한다.
2. 수정 예상 파일을 먼저 나열한다.
3. 파일 충돌 가능성이 낮은 작업만 Worktree thread로 분리한다.
4. 읽기 중심 조사는 Subagent에 맡긴다.
5. 각 Worktree thread는 자체 테스트 결과와 잔여 리스크를 보고한다.
6. Main Local thread가 변경을 하나씩 검토하고 통합한다.
7. 최종 검증은 Main Local thread에서 실행한다.
8. PR 설명에는 병렬 작업 경계와 검증 결과를 기록한다.

## 7. Prompt 템플릿

### 7.1 Main Local thread

```text
이 repo의 AGENTS.md, README.md, package 파일, CI/test 설정을 먼저 확인해줘.
요청사항을 독립 작업 단위로 나누고, 병렬 worktree로 분리 가능한 작업과
같은 파일 충돌 가능성이 높은 작업을 구분해줘.
아직 코드는 수정하지 마.
```

### 7.2 Worktree thread

```text
이 worktree에서는 [작업명]만 수행해줘.
수정 범위는 [경로]로 제한하고, [금지 경로]는 수정하지 마.
완료 후 변경 파일, 실행한 테스트, 남은 리스크, rollback 방법을 요약해줘.
```

### 7.3 Subagent

```text
Subagents를 병렬로 사용해서 다음을 조사해줘.
1. 보안/권한 체크 누락 가능성
2. 테스트 커버리지 공백
3. 변경 파일 주변의 기존 패턴
코드는 수정하지 말고 결과만 정리해줘.
```

## 8. 검증 기준

코드 변경이 포함되면 가능한 한 다음 순서로 검증한다.

1. 변경 모듈의 단위 테스트
2. frontend 변경 시 `npm --prefix frontend run typecheck`
3. frontend 변경 시 `npm --prefix frontend run lint`
4. backend 변경 시 `.\\backend\\.venv\\Scripts\\python.exe -m ruff check backend`
5. backend 변경 시 `.\\backend\\.venv\\Scripts\\python.exe -m mypy`
6. merge 전 가능하면 `npm run health`

검증을 생략한 경우 PR 또는 최종 보고에 이유와 잔여 리스크를 기록한다.

## 9. 운영 리스크와 대응

| 리스크 | 대응 |
| --- | --- |
| 같은 파일 동시 수정 | Main Local thread에서 파일 경계 확인 후 worktree 수 축소 |
| 테스트 환경 차이 | 최종 검증은 Main Local thread에서 재실행 |
| 변경 결과 누락 | 각 thread가 변경 파일과 테스트 결과를 명시 |
| 설정/배포 회귀 | 운영 설정과 배포 스크립트는 병렬 수정 금지 |
| rollback 불명확 | worktree/branch 단위로 폐기하거나 PR 단위 revert 준비 |

## 10. 기본 결론

이 repo의 기본 병렬 운영은 다음으로 제한한다.

> Local thread 1개 + Worktree thread 최대 2개 + Subagent는 읽기 작업 전용

범위가 불명확하거나 충돌 가능성이 있으면 병렬화하지 않는다.
