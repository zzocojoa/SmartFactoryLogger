# History/API P2 결과

> **2026-09-23 서버 설치 검증 완료:** P2 병합본 `d254871`의 미서명 NSIS 설치와
> 실제 120분 관찰·정상 종료·원본 재설치·콘솔 종료 후 수집 지속 확인을 완료했다.
> 실행/회수 42항목과 원문 검사 16항목이 통과했다. 실제 작업정보 일치도 사용자가 확인했다.
> [120분 현장 결과](docs/V2/05_운영_배포/temperature_p2_nsis_120min_trial_20260923.md)를 참조한다.
> 현재 서버는 원본으로 복귀했으며 정식 운영 승격은 별도다. 아래 이전 상태는 당시 기록이다.

> **2026-09-22 격리 설치 검증 완료:** 같은 P2 병합본 `d254871`을 Windows Sandbox에서 실제 NSIS로
> 신규 설치·업그레이드·재시작·원본 재설치했다. 증거 대조 73/73과 후보 CSV 검증 2회가 통과했다.
> [설치 검증 결과](docs/V2/05_운영_배포/temperature_p2_nsis_installation_20260922.md)에 fact 형식 전환 시 보관본 보존과 한계를 기록한다.
> 실제 서버 설치와 정식 운영 승격은 미실행이다. 아래 기록은 각 작성 시점 기준으로 보존한다.


> **후속 상태 — 2026-09-22:** PR #194는 `d254871f89c98154b4e32879e29601df78f7e159`로
> 병합됐다. 동일 병합본의 미서명 내부 패키지 및 10분 현장 시험·정상 종료·원본 복귀를 검증했다.
> [후속 현장 결과](docs/V2/05_운영_배포/temperature_p2_ten_minute_trial_20260922.md)를 참조한다.
> 아래 미커밋·미게시·현장 미실행 설명은 로컬 코드 검증을 끝낸 당시의 기록이다.
> 정식 운영 승격과 설치·업그레이드 검증은 여전히 별도다.

2026-09-22. **P2 로컬 코드 보완·검증 완료. Git 게시와 운영 적용 준비는 아직 진행하지 않았다.**

브랜치 `codex/temperature-history-p2-20260922`, 기준 HEAD `1d4ec21d8b88ce6298742bc4cf21b75884e21b1a`.
PR #193 병합본에서 시작했으며 이번 변경은 미커밋 local diff다. 이전 G1~G5/T1~T3/C1~C3/L1과
과거 후보 현장 결과는 해당 기준의 완료 기록으로 보존한다.

## 보완 결과

| 재현 조건 | 기존 동작 | 최종 동작 |
| --- | --- | --- |
| 같은 UTC ms의 새 표본 2개 | history 마지막 표본을 덮어써 1개만 남음 | instance + sequence로 2개 모두 보존 |
| UTC −60초 후 이전 위치에서 조회 | since_ms보다 작아 새 표본 제외 | cursor 순번으로 새 표본 반환, 원래 UTC 유지 |
| wall +2시간 / −2시간 | 보존·조회 경계가 wall 보정에 영향받음 | 기존 1시간 보존을 monotonic 경과시간으로 판정 |
| 페이지 한도·retention gap | latest-tail 생략이 충분히 드러나지 않음 | cursor oldest-first 페이징, has_more/next_cursor, gap reset 명시 |
| backend instance 변경·빈 이력 | UTC만으로 새 세대 구분 불가 | reset_required와 새 instance cursor로 재동기화 |
| 프론트의 같은 UTC·숨김 복귀 | timestamp 중복 제거·timestamp 조회 | identity 중복 제거와 cursor 페이지 조회 |

위 결과는 production 모듈/실제 route·hook·buffer를 호출한 합성시험이다. 과거 CSV/fact 유실이나 현장 UI 장애를 입증한 것이 아니다.

## 변경 파일과 계약

- `backend/FacilityData/service.py`, `schemas.py`, `backend/app.py`: history sequence, private monotonic 보존 시각,
  동일 latest/history identity, 선택 cursor와 명시적 reset·페이징 계약.
- frontend FactoryData/metricService DTO·service·transport: 추가 API 필드/선택 cursor 전달.
- seriesSampling·seriesBuffer·seriesCatalog: identity 보존/중복 제거, acquisition cursor와 UTC 분리,
  구세대 초기화와 숫자 차트 key 제외. UI 레이아웃 변경은 없다.
- `useMetricsViewModelEffects.ts`: 복귀 페이지 조회, legacy buffer 재동기화, 응답 세대 확인,
  실패/무진전/페이지 한도와 live polling 복귀.
- backend P2 신규 테스트와 frontend buffer/hook/transport 회귀, `.gitignore`의 신규 backend 시험 예외.
- `backend/API_DOCUMENTATION.md`, 이 진행/결과/실행 행렬: 호환성·검증·한계 문서화.

UTC Time/timestamp_ms·CSV/fact 컬럼/버전·원본 파일은 그대로다. 운영 데이터 migration이 없다.
backend와 frontend의 추가 계약은 함께 반영해야 하며, 구 since_ms 호출은 기존 UTC 필터 의미를 유지한다.
API 옵션/응답 세부는 [API 문서](backend/API_DOCUMENTATION.md)를 참조한다.

## 실제 검증

Windows / Python 3.12.6, 기존 backend venv·npm 의존성. child 환경은 V2_MODE=MOCK, 임시 APPDATA/config와
Windows PowerShell 모듈 경로로 격리했다. health의 backend runner는 기존 `.tmp_test_appdata`를 사용한다.
실장비·서버·OS 시각을 변경하지 않았다. mock transport의 연결 문구는 실제 장비 접속 증거가 아니다.

| 실행 | 실제 결과 | 원문 |
| --- | --- | --- |
| P2 production history/API 전용 최종 | 12 pass / 0 fail / 0 skip | `p2-final.txt/.json` |
| history/API·C1·L1 집중 (동시 기록/new-instance 추가 전) | 56 pass / 0 fail / 0 skip | `backend-targeted.txt/.json` |
| frontend buffer·hook·transport 집중 | 4파일 31 pass / 0 fail / 0 skip | `frontend-targeted.txt/.json` |
| 전체 backend | **843 pass / 0 fail / 0 skip**, 189.832초 | `health-final.txt/.json` |
| frontend Vitest | **40파일 301 pass** / 0 fail / 0 skip | 같은 health |
| frontend Node / Electron | **9 pass / 94 pass**, fail·skip 0 | 같은 health |
| frontend typecheck/lint · backend Ruff/mypy | 모두 pass; mypy는 설정된 8개 source file | 같은 health |
| operational-ready/startup-trace/closeout/signature/workflow selftest | 5 suite pass | 같은 health |
| `npm.cmd run health` 전체 | **exit 0**, 11:03:50~11:08:23 KST | 같은 health |

위 파일은 `artifacts/temperature-history-p2/`에 있다. 명령 전체·cwd·환경·시각·종료코드와 로그 해시를 JSON에 기록했다.
신규/기존 테스트의 중복 실행 수를 합산하지 않았다. 전체 backend에는 기존 로컬 ignored 시험 17개가 포함되며,
private F01 fixture를 제공했으므로 공개 CI와 동일한 테스트 수/skip을 기대하지 않는다.

처음 재현의 assertion failure/미구현 인터페이스 오류, 정확한 retention 경계의 float 오차,
첫 health typecheck 실패와 잘못된 wrapper exit 0은 모두 원문으로 보존했다. 최종 결과로 덮어쓰지 않았다.
[진행 기록](HISTORY_API_PROGRESS_P2.md)과 [실행 행렬](HISTORY_API_REGRESSION_MATRIX_P2.json)을 참조한다.

## 검토·위험·다음 단계

이번 diff 검토는 **자체 검토**다. 새 독립 검토를 수행했다고 주장하지 않는다.
상세는 `artifacts/temperature-history-p2/SELF_REVIEW.md`, 전체 diff·신규 파일 명세·SHA256은 같은 폴더에 있다.
검토 범위에서 남은 차단 결함을 발견하지 못했다. 기존 사용자 untracked 34개와 이전 보고서를 보존했다.

위험도 **중간**: API·프론트 데이터 연결 계약을 함께 바꾼다. 관측성은 reset/truncated/has_more와 기존
backfill 경고로 제공한다. 보존 범위를 지난 history는 복구되지 않으며, 통신 오류·반복 재시작·페이지 예산 초과 때
경고 후 live polling을 재개한다. UI viewport는 기존 UTC window를 유지한다. 구 backend는 기존 timestamp 한계가 남는다.

새 패키지/실장비/현장·브라우저 수동 검증은 이번 범위에서 미실행이다. 정식 운영 승격 완료를 뜻하지 않는다.
코드 복귀 단위는 이번 backend+frontend+계약 문서 diff이며, 기준 `1d4ec21`으로 함께 되돌려 검증해야 한다.
실제 운영을 변경하지 않았으므로 운영 rollback·migration 작업은 없다.

다음은 **이 diff의 커밋·푸시·별도 PR 생성 및 CI 확인**이며, 실행 전 별도로 사용자 승인을 받는다.
P2 PR 검토·병합 이후 최종 코드 기준 운영 적용 준비로 이어간다.
