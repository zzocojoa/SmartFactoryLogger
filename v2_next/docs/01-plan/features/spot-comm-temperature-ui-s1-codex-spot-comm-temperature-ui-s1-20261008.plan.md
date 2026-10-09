# PDCA 계획 — UI-S1(P2): SPOT 통신·온도 측정 상태 분리

> 작성일: 2026-10-08 KST
> 작업명 / PDCA feature: `spot-comm-temperature-ui-s1`
> 원본 브랜치명: `codex/spot-comm-temperature-ui-s1-20261008`
> 이전 계획 저장 브랜치명: `codex/temperature-history-p2-20260922`
> 저장 시 새 브랜치 HEAD / 생성 기준: `35959c41edee29573040d571ead952c073f1be13`
> 계획 작성 시 확인한 원격 master: `35959c41edee29573040d571ead952c073f1be13`
> 생성 완료한 구현 브랜치명: `codex/spot-comm-temperature-ui-s1-20261008`
> 구현 worktree: `C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next`
> 문서 상태: 실제 Plan mode에서 계획 작성 완료, 구현 모드에서 파일 저장 완료
> 실행 상태: 새 독립 review 완료(미해결 결함0/cycles0/검토 snapshot binding verified), 최종 full health exit0 및 후보541d701d의 locked installer·실제 packaged API→UI 검증 완료. 서버 로컬 최종 복사·설치·CSV/설정/세대 확인·운영 기준 갱신은 미완료이며4c97d4a를 유지한다. 최신 근거는 계획14.3–14.6절과 candidate-final-validation-001이다.
> 현재 작업의 기준 계획 파일: `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/docs/01-plan/features/spot-comm-temperature-ui-s1-codex-spot-comm-temperature-ui-s1-20261008.plan.md`
> 새 브랜치 worktree의 동일 내용 계획 사본: `C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/docs/01-plan/features/spot-comm-temperature-ui-s1-codex-spot-comm-temperature-ui-s1-20261008.plan.md`
> 이전 준비 계획 원문(보존): `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/docs/01-plan/features/spot-comm-temperature-ui-s1-codex-temperature-history-p2-20260922.plan.md`

## 1. 목표와 범위

설비 운영자가 **응답 수신 상태와 온도 측정 가능 여부를 구분**할 수 있도록 표시를 개선한다. 정상 수신된 under-range가 `SPOT STALE / Comm 1!`로 표시되는 문제와, 최신 통신 오류가 과거 성공 시각 때문에 `OK`로 가려지는 문제를 해결한다.

- **표시 방식:** 데스크톱 헤더에 통신·온도 배지 2개. 520px 이하 화면은 기존 `Comm` 축약 표시를 유지하고 상세 메뉴에 두 상태를 표시한다. 두 방식은 계획 작성 중 사용자 선택으로 확정했다.
- **포함 범위:** frontend 타입, 상태 전달, 배지 판정, 헤더·상세 메뉴, 관련 테스트.
- **제외·유지 범위:** backend API와 수집 로직, Temperature 값·TTL·freshness·안전 gate, CSV schema/rule, 공정 판정, worker 종료 정책. D1의 완료된 기록 로직을 다시 수정하지 않는다.
- under-range를 제품 부재나 특정 물리 원인으로 해석하지 않는다. 기존 shadow 상태와 미검증 설정을 운영 진실이나 `verified=true`로 승격하지 않는다.
- 기존 주 작업공간에는 미커밋 변경이 있다. 그 변경을 보존하고 최신 원격 기준에서 독립 worktree와 UI-S1 브랜치를 생성했다. 운영 설치본과 구분하며, 브랜치 생성과 계획 저장을 로직 구현 완료의 증거로 사용하지 않는다.

## 2. 수정 대상과 구현 결정

### 2.1 수정 대상

아래 경로는 현재 저장소의 대상 식별 경로다. 독립 worktree에서 구현할 때는 같은 저장소 상대 위치에 대응하는 파일을 사용한다.

| 영역 | 수정 대상 | 계획에 연결되는 변경 |
|---|---|---|
| API 응답 타입 | `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/shared/types.ts` | 선택적인 `spot_temperature` 타입 추가 |
| 순수 상태 판정 | `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/shared/utils/commBadge.ts` | 통신 배지와 온도 배지를 별도 출력 |
| 상태 hook | `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/domains/Layout/hooks/useStatusPanel.ts` | 최신 poll·age·캐시 상태를 전달하고 온도 배지를 통신 집계에서 분리 |
| health 수신 상태 | `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/domains/Observability/hooks/useSystemViewModel.ts`, `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/domains/Observability/hooks/useSystemViewModel.types.ts`, `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/domains/Observability/hooks/useSystemViewModelEffects.ts` | 직접 조회·broadcast 수신 경로의 client timing metadata 전달 |
| 화면 연결 | `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/App.tsx`, `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/domains/Layout/components/DashboardHeader/DashboardHeader.tsx` | 수신 metadata와 두 배지를 연결하고 상세 메뉴·접근성 라벨에 반영 |
| 배지 스타일 | `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/App.css` | 필요한 온도 배지 스타일만 추가하고 기존 모바일 축약 구조 유지 |
| 회귀·통합시험 | `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/shared/utils/commBadge.test.ts`, `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/domains/Layout/components/DashboardHeader/DashboardHeader.test.tsx`, `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/domains/Observability/hooks/healthPolling.integration.test.tsx`, `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/frontend/src/domains/Observability/hooks/useSystemViewModelEffects.test.ts` | 아래 필수 시나리오와 기존 polling 동작 검증 |

### 2.2 데이터 전달과 인터페이스

- `HealthSnapshot`에 선택적인 `spot_temperature` 타입을 추가한다. 기존 `/health`의 poll 결과, raw 유효성, source freshness, 장비 상태, snapshot/value age, freshness/TTL 임계값, 값의 origin과 캐시 상태를 그대로 수용한다.
- 상태 판정 함수는 **통신 배지와 온도 배지를 별도로 반환**한다. `commBadges`에는 EX·LS·SPOT 통신 배지만 넣고, 온도 배지는 별도 출력으로 전달한다.
- 기존 `health.comm.spot.last_success_time`은 최근 유효 온도의 이력으로 사용한다. 현재 통신 성공 여부를 결정하는 기준은 `spot_temperature`의 최신 poll 결과다.
- 선택 필드가 없거나 알 수 없는 enum이 전달되면 `UNKNOWN`으로 표시한다. 과거 성공 시각만으로 `OK`를 복원하지 않는다.

### 2.3 freshness와 오류 처리

- health snapshot을 적용하는 공통 경로에서 **클라이언트 수신 시각을 monotonic clock으로 기록**한다. 직접 조회와 다른 탭의 broadcast 수신 모두 이 경로를 사용한다.
- 표시용 snapshot age는 서버가 전달한 age에 수신 후 경과를 더한다. broadcast는 기존 `sent_at`으로 전달 지연도 반영하며, 중복 수신이 age를 초기화하지 않게 한다.
- backend가 `stale`을 전달하면 즉시 반영한다. frontend에서 갱신 중단을 감지하는 경계는 기존 최소 5초를 유지하며, backend freshness 임계값을 우선 사용한다. 임계값이 없으면 기존 refresh 설정의 3배를 사용한다.
- 잘못된 age·임계값이나 freshness 불명은 `UNKNOWN`으로 처리한다. API 조회 실패는 SPOT timeout으로 단정하지 않고, 마지막 snapshot의 age와 기존 API polling 상태를 함께 표시한다.
- 최신 poll의 timeout·connection/http 오류가 과거 유효 온도 성공보다 우선한다. 이후 fresh한 성공 poll이 확인되면 누적 실패 횟수나 과거 오류 시각 때문에 계속 장애로 표시하지 않는다.

### 2.4 표시 계약

| 관측 조건 | 통신 배지 | 온도 배지 |
|---|---|---|
| Fresh 성공·유효 온도 | `SPOT OK` | `Temp OK` |
| Fresh 성공·under-range 장비 코드 | `SPOT OK` | `Temp UNDER_RANGE` |
| Fresh 성공·over-range 장비 코드 | `SPOT OK` | `Temp OVER_RANGE` |
| Fresh 성공·빈 응답/파싱 실패/기타 무효값 | `SPOT OK` | `Temp INVALID` |
| Fresh 성공·backend의 검증된 no-target 분류 | `SPOT OK` | `Temp NO_TARGET` |
| 최신 통신 오류·기존 정책상 사용 가능한 캐시 | `SPOT DOWN` | `Temp CACHED` |
| 최신 통신 오류·사용 가능한 캐시 없음 | `SPOT DOWN` | 기존 상태에 따른 `SOURCE_ERROR` 또는 `STALE` |
| 응답 갱신 중단 | `SPOT STALE` | `Temp STALE`; 허용된 캐시는 TTL 안에서만 `CACHED` |
| 최초 poll 전 / 설정 없음 | `SPOT WAIT` / `SPOT CONFIG` | `Temp WAIT` / `Temp SOURCE_ERROR` |
| 상태 정보 부족·판정 불가능 | `SPOT UNKNOWN` | `Temp UNKNOWN` |

- under/over-range·invalid·cached·stale은 온도 배지에서 경고로 표시한다. 통신 오류는 통신 배지에서 오류로 표시한다.
- `Comm` 요약은 기존 통신 배지 집계 규칙을 유지한다. **온도 배지는 집계에서 제외**하므로, EX·LS가 정상인 fresh under-range 구간은 `Comm OK`다.
- 툴팁과 상세 메뉴에 poll 결과, 관측 경과, 온도 유효성, 값의 origin, 최근 유효 온도·오류 이력을 구분해 표시한다. 색상과 함께 텍스트·접근성 라벨을 제공한다.

## 3. PDCA 구현 단계와 일정

| 단계 | 작업과 완료 조건 | 현재 진행 상태 |
|---|---|---|
| **Plan** | 실제 계획 모드에서 작성한 계획을 새 브랜치명 규칙으로 저장한다. 원격 `master`와 `origin/master`의 SHA 일치 및 D1의 `temperature-operational-v6`를 확인했고, 그 기준에서 독립 worktree와 UI-S1 브랜치를 생성했다. | 계획 작성·최신 기준 확인·D1 확인·worktree·구현 브랜치 생성·계획 저장 완료 |
| **Design** | 이 기준 계획을 읽고 스킬 지정 경로에 설계 문서를 저장하며 PDCA feature를 등록한다. 위 표시 계약, freshness 계산, 캐시 표시, 타입 호환성, 테스트 기대값을 설계에 고정한다. | 상세 설계 저장·PDCA 단계 완료 |
| **Do** | 타입·수신 시각 전달 → 순수 상태 판정 → 상태 hook → 헤더·상세 메뉴 → 회귀시험 순서로 구현한다. 기존 polling 주기·backoff·leader/visibility 정책은 유지한다. | 최초 구현·승인 보완과 순수 수신 helper 분리 완료(10절) |
| **Check** | 설계와 최종 diff를 대조하고 관련 검증을 실행한다. 핵심 요구사항과 아래 필수 시나리오는 모두 충족해야 한다. | 이전398+9/PASS 보존. 후속 독립 coverage·실제 start 확보; 새 회귀/desktop UI/QA casing FAIL, 전체 health exit1. current review INCOMPLETE(11.2절). |
| **Act** | 불일치나 실패를 수정하고 영향받은 검증을 재실행한다. 스킬 기준 최대 5회 반복 후에도 남은 문제가 있으면 미완료로 기록한다. | 이전 A 승인 R1/R2 완료. 새 수정 권장8건·조사1건은 미해결/미승인; proposal 저장 후 사용자 선택 대기. |
| **Report** | 변경 사항, 최종 commit, 검증 명령·exit code, 미실행·미관찰 항목을 기록한다. Match Rate 90%만으로 필수 요구사항의 누락을 완료 처리하지 않는다. | 구현·로컬 검증 보고서 저장; 미커밋·패키지/운영 미실행 명시 |

- 검증 일정은 **설계 → 구현 → 로컬 검증 → 후보 패키지 검증 → 승인 범위의 적용 확인** 순서로 잡는다. 착수·완료 시각은 실제 수행 시 기록하며 확정되지 않은 날짜나 소요 시간을 완료 약속으로 쓰지 않는다.
- 기존 브랜치·worktree·미커밋 파일과 과거 PDCA 기록은 자동 정리하거나 덮어쓰지 않는다. 새 사용자 채팅은 사용하지 않는다. subagent는 11절의 사용자 승인에 따른 읽기 전용 독립 리뷰에 한해 사용하며 구현·최종 검증은 부모가 담당한다.
- 구현 시작 전, 작업 재개 시, 주요 구현 단계에 들어가기 전에 이 기준 계획 파일을 다시 읽는다. 지정 폴더의 기준 계획과 새 브랜치 worktree의 사본이 같은 내용인지 확인하고, 구현·검증 진행 상태를 갱신할 때 두 위치를 동기화한다.
- 범위 변경이 필요하면 이유와 영향을 설명하고 사용자 확인을 받은 뒤 이 계획 파일을 먼저 갱신한다. 확인과 갱신 전에는 범위 밖 변경을 실행하지 않는다.
- AGENTS.md의 브랜치별 계획 파일명과 위 기준 경로를 우선한다. PDCA 문서 경로를 등록할 때 이 실제 계획 파일을 참조하고, 관례적인 feature-only 계획 파일을 중복 생성하거나 기존 문서를 덮어쓰지 않는다.

## 4. 검증 방법과 완료 조건

### 4.1 필수 회귀시험

- [x] 마지막 유효 온도가 오래됐어도 fresh under/over-range 응답이면 통신은 `OK`이고 온도 상태만 경고다.
- [x] 최근 성공 이후 timeout의 DOWN 유지와 새 정상 poll 복구. 지연 legacy 중복·source/leader 교체의 세 영구 회귀 및 native Chrome follower에서 PASS(9절).
- [x] 캐시 재사용은 `CACHED`로 구분하며, TTL 경과 후에도 정상 온도로 표시하지 않는다.
- [x] source 갱신 중단과 health API 갱신 중단에서 과거 `OK`가 계속 유지되지 않는다.
- [x] 초기 데이터 없음, 설정 없음, 누락 필드, 알 수 없는 enum·잘못된 age는 정상으로 표시되지 않는다.
- [x] 벽시계 보정·헤더 재마운트·지연 중복·source/leader 교체·같은 poll 경과 보존 시험 PASS. backend identity 없는 legacy는 최근 256개 중복 이력으로 호환(한계는 9절/보고서).
- [x] 기존 health polling 통합시험을 확장해 transport → view-model → 상태 hook → 실제 헤더 렌더링을 검증한다. 요청 중복 방지·backoff·visibility·정리 동작도 보존한다.
- [x] 데스크톱과 좁은 화면에서 배지·상세 메뉴·접근성 라벨을 확인한다.

### 4.2 최종 변경 상태에서 실행할 명령

```text
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
```

병합 전에는 `npm run health`를 실행한다. 실패·미실행이 있으면 실제 원인과 검증 범위를 기록한다.

### 4.3 완료 조건

- [ ] 현재 후보의 필수 UI-S1 계약과 모든 승인 보완 회귀시험을 충족. 이전398+9 PASS는 보존하되, 11.2절의 새 실패/수정 선택·최종 검증이 남음.
- [ ] 최종 수정 상태의 frontend 검사/build와 기본 health를 통과하고 실제 결과를 기록한다. 현재 frontend 이전PASS와 전체 health exit1 원인 기록은 보존; 최종 전체 재실행 남음.
- [ ] 현재 상세 메뉴·순서 계약·새 후속 결함을 보완하고 최종 review를 완료한다. 이전 R1/R2 완료와 후속 coverage 확보를 전체 PASS로 대체하지 않음.
- [x] 실제 변경과 검증 결과를 이 계획의 목표·범위·완료 조건에 대조하고 진행 상태를 갱신한다.
- [x] 합성 UI 시험과 실제 설치본·실장비 확인 결과를 구분해 보고한다.
- [x] 운영 적용까지 수행한 경우에만 후보 검증·적용 확인·롤백 기준 갱신을 완료로 기록한다.

### 4.4 검증 결과 기록 양식

| 검증 항목 / 명령 | 대상 commit·설치본 | 결과 / exit code | 증거 위치 | 미검증·남은 항목 |
|---|---|---|---|---|
| 계획 파일명·필수 항목·저장 내용 확인 | 이 계획 파일 | 원본 브랜치명·필수 항목 확인, 두 저장 위치 동일 | 이 문서의 진행 기록 | 이전 준비 계획 hash 보존 |
| frontend test / typecheck / lint / build | base 35959c4 + 미커밋 frontend; correction/source hash manifest | 390개 + node 9개 PASS, 각 exit 0 | worktree .tmp_ui_s1_verify/correction 및 구현 보고서 6절 | installer·실장비 미검증 |
| npm run health | 위 worktree; 추가 frontend 변경은 최종 검사 재실행 | exit 1: QA Get-FileHash 로딩 실패; backend 880개(1 skip), 이전 단계 통과 | health.log, qa-explicit-utility.json | Utility import 후 동일 QA 5개 각 exit 0; 기본 명령 오류 미해결 |
| 후보 패키지 / 서버 적용 확인 | 후보 생성 후 기록 | 미실행 | 미생성 | 운영 적용 미시작 |

## 5. 운영 적용과 위험 관리

- 현재 확인된 운영본 `4c97d4a00d79ae0d3da70b2e82af227345e21040`과 installer SHA256을 복귀 기준으로 보존한다.
- 새 후보는 **전체 build commit·installer SHA256·서명 상태**로 식별하고, 패키지에서 새 상태 표시와 API 연결을 확인한다.
- 서버 검증 자료가 필요하면 개발 PC 준비, `Z:\SmartFactory\YYYYMMDD\send` 전송, 서버 바탕화면 `SmartFactory`의 실행별 새 폴더까지 최종 복사·파일 확인을 수행한다.
- 운영 적용은 새 설치본에 해당하는 승인 범위에서 진행한다. 적용 후 실제 `/health`와 화면을 대조하고 수집·CSV 추가 저장·설정 보존을 확인한다.
- 운영 승격과 적용 확인을 마친 후보를 다음 개선의 롤백 기준으로 등록한다. 이전 installer와 증거는 보존하며, 기존 미검증·QA 결과는 그대로 기록한다.
- 변경 없는 설치본의 재승인·재빌드·반복 120분 시험은 자동 추가하지 않는다.

| 위험 | 영향 | 대응 |
|---|---|---|
| 누락된 상태 정보를 정상으로 오판 | 통신·측정 경고가 숨겨짐 | 보수적인 `UNKNOWN`과 누락·비정상 입력 회귀시험 |
| 오래된 snapshot의 재사용 | 응답 중단 후에도 `OK` 유지 | monotonic age 계산, broadcast 지연·중복 처리, 갱신 중단 시험 |
| 좁은 화면의 온도 표시 누락 | 상태 분리의 의미를 확인하기 어려움 | 기존 모바일 축약 구조 유지, 상세 메뉴·접근성 검증 |
| 설치본과 소스·시험 근거 혼동 | 다른 후보의 PASS를 잘못 적용 | 전체 build commit·installer SHA256·검증 대상을 함께 기록 |

## 6. 진행 상태와 변경 이력

- [x] 실제 Plan mode에서 계획 작성.
- [x] 사용자 선택 반영: 데스크톱 배지 2개, 좁은 화면 기존 축약 유지.
- [x] 새 UI-S1 원본 브랜치명 확인과 AGENTS.md 형식의 기준 계획 파일 저장.
- [x] 독립 worktree·최신 구현 기준·구현 브랜치 준비.
- [x] PDCA feature 등록과 상세 설계 저장.
- [x] 로직 구현.
- [x] 승인된 로컬 순서 보완 검증: 전체 398개+9개, 타입·lint·build·Chrome PASS. 독립 review coverage와 기본 health QA 실패는 별도 유지.
- [ ] 후보 패키지 검증.
- [ ] 해당 승인 범위의 운영 적용·적용 확인·다음 롤백 기준 갱신.

| 기록일 | 변경·진행 내용 |
|---|---|
| 2026-10-08 KST | PDCA 스킬과 실제 Plan mode로 계획 작성; 사용자 표시 방식 선택 반영. |
| 2026-10-08 KST | 구현 모드에서 첫 파일 작업으로 계획 저장. 실제 원본 브랜치명, 기준 경로, 수정 대상, 단계·검증·완료 조건과 미시작 상태를 기록. 로직 구현과 PDCA 상태파일 변경은 수행하지 않음. |
| 2026-10-08 KST | 사용자 지시에 따라 UI-S1 전용 브랜치를 최신 `35959c41edee29573040d571ead952c073f1be13` 기준의 독립 worktree에 생성. 새 브랜치명을 실제 확인하고 지정 계획 폴더와 새 브랜치 worktree에 동일 계획을 저장. 이전 준비 계획과 기존 미커밋 변경은 보존. 로직 구현은 미시작. |
| 2026-10-08 KST | 구현 승인에 따라 상세 설계 저장 및 PDCA Design 완료. 직접 조회·broadcast receipt metadata와 별도 온도 배지를 구현한다. feature-only 계획 조회 도구 제약은 기존 브랜치 계획을 그대로 참조하여 해결. |

| 2026-10-08 KST | 최초 UI-S1 구현과 frontend 362개/typecheck/lint/build·Chrome 검증 기록. 기본 health/QA exit 1과 Utility import 후 QA 5개 통과를 구분. 당시 10/10 완료 판정은 후속 직접 검토에서 두 누락을 발견해 재개방했음. 원문 증거는 보존. |
| 2026-10-09 KST | 사용자 수정 승인에 따라 source/sequence 기반 broadcast 중복·역순 처리와 메뉴 진단 본문을 보완. 영구 회귀 28개 추가 후 최종 frontend 390개 + node 9개, typecheck/lint/build, Chrome 1440px/390px 진단 12개 항목·줄바꿈·접근 PASS. 기준 계획·설계·분석·보고·PDCA 상태 갱신. 미커밋·패키지/운영 미실행 유지. |

### 현재 결과 문서와 검증 대상

- worktree 설계: `docs/02-design/features/spot-comm-temperature-ui-s1.design.md`
- worktree 분석: `docs/03-analysis/spot-comm-temperature-ui-s1.analysis.md`
- worktree 보고: `docs/04-report/spot-comm-temperature-ui-s1.report.md`
- 현재 최종 source 식별: worktree `.tmp_ui_s1_verify/refactor-20261009-001/source-manifest.json`(frontend14개, 기존수신hook1개 변경+새helper1개). 최초/correction/ordering-correction manifest와 검토 실패 원문은 각 당시 후보의 증거로 보존한다. 기준 HEAD + 미커밋 변경을 검사했으며 새 구현 commit·installer SHA256은 아직 없다.
- 실장비·실제 backend 프로세스·설치본·운영 적용은 미검증/미실행이다. 현재 운영 복귀 기준은 보존하며, 이 로컬 구현 완료를 운영 승격 완료로 해석하지 않는다.

## 7. 직접 로직 검토 후 승인 보완

- 사용자 승인: 직접 검토에서 제시한 broadcast 오류·복구 누락과 상세 메뉴 진단 정보 누락의 수정 승인. 기존 UI-S1 브랜치와 계획을 이어 사용한다.
- 검토 근거: 기존 76개 시험 PASS, 추가 5개 FAIL(exit 1). `.tmp_ui_s1_verify/review/review-test.log`를 보존한다. 이전 100%·미해결 없음 판정은 재개방했고, 이번 완료 근거는 승인 보완 후 최종 source와 아래 검증 결과다.
- broadcast의 신규 메시지는 송신 hook별 source ID와 증가 sequence로 중복·역순을 판정한다. `sent_at`은 전달 지연 계산에만 사용한다. 구버전 메시지의 두 전송 경로 중복은 송신 탭별 동일 payload로 판정하고, 벽시계 역행이나 미래 시각이 다음 정상 응답 수신을 막지 않게 한다.
- 순수 판정 함수의 진단 항목을 공통 구조로 전달해 기존 툴팁과 상세 메뉴 본문에 같은 poll/raw/source/age/device/origin/cache/성공·오류 정보를 표시한다.
- 수정 대상은 기존 목록의 판정 함수·상태 hook·broadcast hook·헤더·CSS·관련 시험과 PDCA 문서다. backend·수집·TTL·안전 gate·leader/visibility/backoff 정책은 기존 범위를 유지한다.
- [x] 두 전송 경로의 시계 역행 → 최신 timeout → 정상 복구와 미래/비정상 시각 → 정상 복구를 영구 회귀시험에 추가하고 PASS를 확인했다.
- [x] 신규 메시지 식별 정보 생성, effect 재시작 후 sequence 유지, 중복·역순 처리와 기존 메시지 호환을 확인했다.
- [x] 상세 메뉴의 진단 본문과 Chrome 390px의 12개 항목 줄바꿈·마지막 항목 접근을 확인했다.
- [x] 최종 frontend test/typecheck/lint/build, 계획·설계 대조, 분석·보고·PDCA 상태를 갱신했다.


## 8. 최초 review의 실패 기록 (2026-10-09, A 승인 보완 전)

- [검토 보고서](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/docs/03-analysis/spot-comm-temperature-ui-s1-review-20261009.md): 최초 CRITICAL 2건의 기록과 A 승인 보완 결과. 전체 review는 INCOMPLETE이며 시점별 제품 수정·검증 범위를 구분한다.
- R1: legacy 탭의 성공 A → timeout B → 지연된 다른 경로의 A가 마지막 fingerprint와 달라 수용되고 SPOT DOWN이 OK로 돌아간다.
- R2: 새 source/leader의 timeout 뒤에 옛 source의 더 큰 sender sequence를 가진 오래된 성공이 수용된다. sender별 sequence만으로 backend 관측 순서를 보장하지 못한다.
- backend가 이미 노출한 service ID/poll sequence를 fixture에 포함한 세 경우(legacy/source/leader)의 native Vitest 실패를 013/014에서 반복 재현했다. 실제 Chrome BC/storage interleaving도 두 실행에서 관찰했다.
- 현재 제품 입력에서 전체 frontend 390개 + Node 9개, typecheck/lint/build, production App desktop/mobile 12개 항목 PASS를 다시 확인했다. 이 PASS를 새 순서 계약의 FAIL에 적용하지 않는다.
- 기존 7절의 승인 보완·회귀 결과는 당시 시험 범위의 기록이며 보존한다. 현재 전체 완료율 100%를 재사용하지 않는다. Check 단계로 되돌리고 필수 완료 조건을 열었다.
- **수정 제안(아직 미승인):** 기존 frontend 수신 타입/분기에 backend service ID + poll sequence를 연결하고, legacy 중복은 제한된 이력으로 제외한다. 기존 integration 시험 파일에 report의 세 회귀를 먼저 작성해 red를 확인한다. 동일 poll age 갱신·service 재시작·EX/LS 적용·정상 복구·벽시계 보정과 기존 polling 정책을 보존한다. backend·TTL·안전 gate 변경은 제안하지 않는다.
- [ ] 추가 수정 선택 후 해당 설계·계획을 먼저 구체화하고 영구 회귀를 red → repair → green 순서로 검증.
- [ ] 필수 순서 계약과 인접 정상/복구, frontend test/typecheck/lint/build/Chrome 최종 재검증.
- 독립 specialist/native adversarial은 이 계획의 subagent 금지로 미실행. review logger 시작 receipt도 Windows fingerprint 오류로 없음. 이는 결함 2건과 구분하는 미확보 coverage이며 clean/completed로 보고하지 않는다.
- npm run health는 병합 전 필수; 이번 병합 미요청으로 미재실행. 과거 exit 1을 PASS로 바꾸지 않는다. 후보·서버·운영 작업은 계속 미실행이다.


## 9. A 선택에 따른 순서 보완 승인·설계 (2026-10-09)

- 사용자 선택: **A — 두 결함과 세 회귀 수정**. 8절 R1/R2와 보고서의 세 재현을 보완한다. 기존 UI-S1 브랜치·계획을 계속 사용한다.
- 먼저 기존 healthPolling.integration.test.tsx에 legacy-interleaved/source-replacement/leader-replacement를 추가하고 현재 제품에서 red를 확인한다. backend identity 선택 필드를 types.ts에 연결한다.
- 공통 applyHealthSnapshot에서 service ID와 안전한 0 이상의 poll sequence를 비교한다. 같은 service의 작은 poll은 SPOT 관측·comm.spot·receipt를 보존하고 나머지 health 영역만 적용한다. 효과 hook은 이 경우 health polling/leader receipt를 갱신하지 않는다.
- 새 service는 sequence 0부터 수용하며 이전에 수용한 service는 retired로 기록해 그 service의 지연 메시지가 되돌리지 못하게 한다. ID/sequence가 없는 구버전 계약은 기존 보수적 상태 판정과 중복 방지를 유지한다; 서로 다른 backend service의 ID 자체를 시간 순서로 해석하지 않는다.
- 같은 poll의 age 갱신은 수용하되 snapshot/value age 각각을 기존 monotonic 누적 경과 아래로 내려가지 않게 화면용 snapshot에서 정규화한다. 실제 전달 지연 receipt는 유지하며 캐시 값의 긴 경과가 통신 경과를 부풀리지 않게 두 floor를 독립 처리한다. 미래·잘못된 sent_at은 기존 UNKNOWN 처리와 다음 정상 복구를 유지한다.
- legacy 전체 payload fingerprint를 최근 256개 Set으로 유지해 두 전송 경로의 interleaved 중복을 제외한다. backend identity가 있는 오래된 관측은 이 한도를 넘어도 poll 순서로 제외한다. sender source/sequence 검사는 유지한다.
- 수정 파일: 기존 타입·공통 view-model 수신·effects 수신 분기·integration 시험·PDCA 문서. backend API/장비 sampling/TTL/안전 gate/leader 선출/visibility/backoff에는 변경하지 않는다.
- 인접 검증: 새 정상 poll 복구, 같은 poll age와 cache/value age 비회춘, backend 재시작과 retired service, 직접 API 뒤 지연 broadcast, EX/LS 적용, identity 없는 legacy 호환 및 이력 상한.
- [x] 영구 세 회귀 red(exit1) → 순서 처리 → 세 회귀+인접 다섯 사례 8개 green(exit0), 원래 report-only probe 세 개 green(exit0).
- [x] 최종 frontend 398개+Node9개, typecheck/lint/build, Chrome 1440px/390px 메뉴 12개 및 실제 follower 수신 경로 세 시나리오 PASS. source/증거 hash와 계획·설계·분석·보고 갱신.
- 독립 리뷰 금지·logger receipt 미확보와 과거 health QA exit1은 유지한다. 이 보완을 운영 적용이나 완전한 독립 리뷰 완료로 보고하지 않는다.


### 9.1 최종 검증과 남은 범위

- 실행별 증거: `.tmp_ui_s1_verify/ordering-correction-20261009-001`; materialize 판정 pass/open[]. source-manifest.json의 frontend13개 중 승인 대상4개만 이전 review 후보에서 변경됐고 나머지9개는 동일하다. 제품/시험 수정은 최종 검사 시작 전에 끝났다.
- 첫 Chrome 검증의 owned-context setup 오류(exit1)는 008에 보존하고 수정 후 009에서 전체 UI/native follower PASS를 확인했다. 실제 장비·서버 leader 선출 시험으로 해석하지 않는다.
- UI-S1 구현·승인 보완의 로컬 검사 완료와 전체 review/운영 완료를 구분한다. 독립 리뷰/시작 binding, 병합 전 health, 후보·실장비·installer·운영 적용은 아직 완료하지 않았다. PDCA Check를 유지하며 전체 matchRate를 임의로100으로 되돌리지 않는다.


## 10. 후속 코드 리팩토링 (2026-10-09)

- 사용자 지시: **이어서 코드 리팩토링 진행**. 새 브랜치나 별도 계획을 만들지 않고 현재 UI-S1 브랜치의 승인 보완을 이어 정리한다.
- 이유: 공통 health 수신 callback에 backend 관측 순서 판정, 전달 지연 계산, React 상태 병합이 섞여 있다. 도메인 내부의 순수 함수로 분리하여 정책을 읽기 쉽게 하고 React 상태 처리와 구분한다.
- 수정 대상: 기존 useSystemViewModel.ts와 같은 폴더의 새 useSystemViewModel.health.ts, 관련 계획·설계·분석·보고·PDCA 상태. 새 helper는 다른 도메인의 범용 프레임워크로 확장하지 않는다. 기존 회귀시험을 보존하며 구현을 그대로 따라가는 시험은 추가하지 않는다.
- 보존 계약: service ID/안전한 poll sequence 검증, 오래된 poll/retired service 제외, identity 없는 legacy 호환, 같은 poll의 snapshot/value age 독립 floor, 실제 수신 receipt, 거절된 SPOT/comm.spot/receipt 보존과 나머지 health 적용, 최신 오류·복구를 모두 유지한다.
- 순서 제약: 관측 ref는 메시지를 받은 즉시 갱신하고 React functional updater에는 순수 병합만 둔다. 연속 메시지와 React 재실행에서 ref 갱신 순서나 side effect가 바뀌지 않게 한다. 벽시계와 monotonic 시각은 hook에서 수집하여 순수 함수에 전달한다.
- 제외 범위: effects의 전송/중복 이력, polling·leader/visibility/backoff, 화면 표시 계약, backend·Temperature 값·TTL·안전 gate·CSV·패키지·서버·운영 변경.
- 단계: 계획 범위 저장 → 현재 source/문서 증거 보존 → 수신 helper 분리 → 기존 순서·polling 회귀와 최종 frontend 검사 → production App의 합성 API·실제 follower 수신 확인 → 변경 대조와 문서 동기화.
- 검증: 기존 health broadcast observation ordering 8개를 먼저 실행하고 frontend 전체 test·typecheck·lint·build를 최종 상태에서 실행한다. 기존 소유 Chrome fixture로 desktop/mobile 메뉴와 follower의 legacy/source/leader 세 경우·복구를 재검증한다. git diff --check, 변경 파일/hash, 기준 계획 두 사본, 기존 주 작업공간 보존을 확인한다.
- 실행 증거는 .tmp_ui_s1_verify/refactor-20261009-001에 새로 남긴다. 이전 materialize 증거·hash와 최초 실패 기록은 덮어쓰지 않는다. 독립 review coverage/binding·과거 health QA exit1·후보/운영 미실행은 유지한다.
- [x] 사용자 지시를 좁은 수신 로직 리팩토링 범위로 구체화하고 구현 전에 계획 두 사본에 저장.
- [x] 순수 수신 helper 분리 및 기존 동작/범위 대조. 기존 수신 hook 1개와 새 helper만 변경; 순서 회귀 8개 exit0.
- [x] 최종 순서8개·전체398개+Node9개·typecheck/lint/build·Chrome exit0. 최종 diff/hash와 보존 상태는 아래 실행 증거의 finish.json에 기록.
- [x] 설계·분석·보고·PDCA와 계획 동기화; 로컬 리팩토링 완료와 독립 review/health/운영 미완료를 구분.

### 10.1 최종 결과와 증거

- 순서 판정 assessSpotObservation, 전달 지연 buildHealthReceipt, 순수 상태 병합 mergeHealthSnapshot을 도메인 내부 helper로 분리했다. 관측 ref의 즉시 갱신과 functional updater의 순수성을 보존했다. effects·배지·시험·backend 변경은 없다.
- 기존 frontend13개 중 수신 hook1개만 바뀌었고 나머지12개는 동일하다. 새 helper를 포함한14개 입력의 최종 검사 전/후 hash를 각 receipt에서 확인했다.
- 실행별 source-manifest.json, 6개 검사 receipt와 stdout/stderr, browser-results.json, 화면 캡처2개, finish.json을 .tmp_ui_s1_verify/refactor-20261009-001에 기록한다. 이전 hash 결합 증거는 보존한다.
- 실제 backend 프로세스·장비·installer·서버 적용은 미검증/미실행. 병합 미요청이며 전체 health를 이번에 재실행하지 않았다. 과거 exit1과 독립 review INCOMPLETE는 그대로 유지한다.


## 11. QA·독립 리뷰·후보 패키지·운영 적용 승인 (2026-10-09)

- 사용자 승인: 다음 작업 네 단계(QA 실패 해결, 독립 리뷰/시작 증거 정리, 후보 commit·installer 검증, 승인 범위의 운영 적용 및 기준 갱신)의 진행 승인. 기존 브랜치·기준 계획을 이어 사용한다.
- 이유: frontend 로컬 검증은 끝났으나 기본 health QA exit1, review coverage/binding, 실제 설치본·장비 연결·운영 적용 증거가 남아 있다. 과거 PASS를 새 후보에 이식하지 않고 각 요구의 실제 결과를 확보한다.
- QA 변경 범위: Get-FileHash 오류를 정확한 PowerShell5.1 -File/-SelfTest 진입에서 재현하고 원인을 규명한다. 필요한 최소 QA helper/명령 진입 보완 및 focused regression을 수행한 후 저장소 기본 npm run health를 최종 상태에서 실행한다. backend·온도 판정·TTL·CSV·안전 gate를 QA 우회용으로 바꾸지 않는다.
- 독립 리뷰 범위 변경 승인: 기존 subagent 금지를 이번 독립 review의 읽기 전용 specialist/native adversarial 작업에 한해 해제한다. 새 사용자 채팅이나 쓰기 agent는 만들지 않는다. 현재 부모+최대3개 subagent 슬롯 내에서 필요한 specialist를 순차/독립 배치하고, 코드·계획·증거 기록과 최종 검증/통합은 부모만 수행한다. 저장소 병렬 운영 규칙을 따른다.
- review 시작 증거는 실제 현재 worktree fingerprint로 확보한다. Windows path 문제는 실제 도구/환경에서 조사하여 해결하고, receipt나 completed 값을 만들어 내거나 누락된 coverage를 PASS로 표시하지 않는다. review SKILL의 관련 specialist/adversarial/최종 후보 재검증을 수행한다.
- 후보: 승인된 UI-S1 변경·QA 보완·관련 문서만 커밋한다. 기존 주 작업공간의 미커밋 변경은 보존한다. 운영 후보의 전체 build commit, installer 길이/SHA256, 내부 backend/Electron provenance, 서명 상태를 식별하며 표시 버전만으로 동일본으로 보지 않는다. push/PR/merge는 후보 식별·검증에 필요할 때만 별도 요구/승인 범위를 적용한다.
- 패키지 검증: 실제 installer/패키지의 startup·정상 종료/재시작·UI 상태 분리·API 전달·필요한 CSV/설정 계약을 격리된 실행 경로에서 확인한다. 실제 장비 응답은 설치본·서버 관찰에서 별도로 확인하며 under-range/timeout을 만들기 위해 운영 통신을 끊거나 설정을 변경하지 않는다.
- 운영 적용: 현재 승인 서버의 identity/설치 경로/실행 세대/설정·데이터/직전 복귀 installer를 먼저 읽기 검증한다. 개발 PC와 서버의 실제 Desktop/SmartFactory 아래 새 실행별 폴더, Z:/SmartFactory/20261009/send·return·records를 사용한다. Codex가 Chrome 원격 데스크톱으로 서버 로컬 최종 복사/파일 확인 및 결과 회수를 수행한다.
- 기존 운영 4c97d4a00d79ae0d3da70b2e82af227345e21040 / installer SHA256 D453C1D17EFC706D3E21FE6F8D09F739F159EBF9F3F24F2EB2349E92D4EF84FB를 적용 확인 전 복귀 기준으로 보존한다. 정상 종료가 실패하면 강제 종료/데이터 삭제로 진행하지 않고 실제 근거와 복구 경로를 조사한다. 기존 서명/config/장비/terminal 한계를 임의로 PASS/verified=true로 바꾸지 않는다.
- 적용 완료 조건: 승인 후보의 실제 설치 commit·핵심 파일 해시/실행 세대·실제 /health→화면 상태·수집/CSV 추가·설정 보존을 확인하고 원문 증거를 회수한다. 운영 승격·적용 확인 후에만 operating_rollback_baseline.md에 운영본/다음 복귀 기준/교체 전 이전본과 승인·검증·수용 한계를 갱신한다. 과거 installer/영수증은 보존한다.
- 실행 증거: 로컬 QA/review는 .tmp_ui_s1_verify/closeout-20261009-001, 새 패키지·서버 전달/회수 묶음은 실제 Desktop/SmartFactory의 신규 폴더에 출처·해시를 기록한다. 불가/실패/미관찰은 각각 그대로 남기며 전체 목표가 충족될 때만 완료로 보고한다.
- [x] 진행 승인과 범위 변경을 구현 전에 기준 계획 두 사본에 저장.
- [x] QA 오류 재현·원인 규명·최소 보완·기본 npm run health 최종 exit0.
- [ ] 실제 review-start binding, specialist/native adversarial coverage, 최종 후보 검증·판정.
- [ ] 후보 commit·installer 식별 및 격리 패키지/실제 API→UI 검증.
- [ ] 서버 최종 전달·승인 적용·수집/CSV/설정·실행 세대 검증과 증거 회수.
- [ ] 운영본·다음 롤백 기준 갱신, 이전본 보존, 계획·설계·분석·보고·PDCA 최종 대조.

### 11.1 QA 재현과 확정된 보완 대상

- exact Windows PowerShell5.1 -NoProfile -File measure_nsis_operational_ready.ps1 -SelfTest가 exit1로 재현됐다. inherited PSModulePath에서는 Codex runtime의 Utility7.0 모듈이 로드되며 Get-FileHash가 없다. 동일 자식 프로세스에서 PSModulePath만 제외하면 Windows PSHOME의 Utility3.1 모듈/Get-FileHash가 로드된다. 단순 Import-Module 이름 지정은 잘못된 Utility7을 다시 선택하여 해결되지 않는다.
- 필요한 코드 변경은 package.json의 health:qa:selftest 진입과 scripts/run_qa_selftests.cjs 신규 runner다. 기존5개 PowerShell self-test/배포 helper 바이트는 보존한다. Node runner가 각 powershell.exe -NoProfile -File -SelfTest를 순차 실행하며 child env에서만 PSModulePath를 제외하여 Windows 기본 모듈 경로를 재구성한다. 나머지 환경과 부모/사용자/머신 환경 설정은 변경하지 않는다.
- 관찰 가능한 회귀는 기존5개 self-test의 정확한 기본 npm run health:qa:selftest 진입(오염된 inherited 환경 및 정상 native 환경)과 첫 실패의 비정상 종료 전달이다. 새로운 테스트를 구현 그대로 베끼지 않고 기존 실제 hash/manifest/timeout/실패 fixture 검증을 활용한다. 마지막에는 npm run health 전체의 최종 exit code를 확인한다.
- review 시작 증거 조사에 쓰는 gstack 도구 checkout의 자동업데이트는 기존 auto_upgrade=true 설정에 따른다. 제품 repository/운영 설치본을 도구 갱신으로 수정하지 않는다. 도구 원본 commit·설치 refresh·실패/복구 결과를 별도 기록한다.

### 11.2 후속 리뷰 결과와 수정 범위 확인 대기

- 부모가 기존 14개 frontend hash의 불변을 확인했다. 오염된 canonical/native 환경의 정확한 QA5개 진입은 exit0이나 uppercase PSMODULEPATH replay006/007은 동일 Get-FileHash 오류/exit1이다. 기존5개 PS helper 원문과 환경 설정은 보존한다.
- 기본 npm run health는 PowerShell5.1 outer host에서 exit1이었다. dependencies14/Electron94/frontend398+Node9/typecheck/lint/ruff/mypy9는 PASS; backend880개 중 두 canary subprocess decode 오류·1skip, QA chain 미도달. 같은2개 direct Python은 exit0, 같은 outer host는 오류2/exit1, owned child UTF-8에서는2 PASS/exit0이었다. host encoding 원인을 확인했으나 전체 기본 명령 PASS로 바꾸지 않는다.
- 읽기 전용 specialist8개와 native adversarial이 종료됐다. optional Claude Code는 not_installed로 unavailable. 실제 review-start 캡처 오류를 owned gstack 절대 Windows path 판정에서 보완했다. 실제 원래 token의 start/end wtree가 일치했고 native 정적 review binding verified, parent는 필수 probe 실패로 incomplete/completed:false/converged:false다.
- native composition004/005: 같은 poll invalid timing 뒤 age/cache 회춘3개와 완료 timeout→지연 초기 WAIT 역전1개가 두 번씩 FAIL. QA006/007 동일 case 오류; Chrome009 desktop1440×768/1024×768 마지막 메뉴 제어 접근 FAIL/mobile PASS;012 진단 텍스트 readability 실패를 확인했다.
- 새 수정 권장8건(critical6·informational2)과 direct API delivery-age 조사1건은 후속 문서 **docs/03-analysis/spot-comm-temperature-ui-s1-closeout-review-20261009.md**에 재현·정적 검토·전체 제안 test code·수정 파일/영향을 구분하여 저장했다. 기존 R1/R2와 refactor PASS 원문은 보존한다. 후속 QA materialize는 fail/open[]이며 명령 exit0과 기능 PASS를 구분한다.
- 현재 단계는 **새 발견의 수정 선택 대기**다. 계획에 승인되지 않은 구현 범위를 추가한 것이 아니다. 특히 처음 보는 broadcast backend 세대의 직접 API confirmation은 follower의 기존 무조회 정책에 좁은 예외를 제안하므로, 사용자 확인 후 이 계획의 구현 범위를 먼저 갱신해야 한다. 직접 응답 timing 보완도 먼저 재현·계약을 확인한다.
- backend API/Temperature 값/서버 freshness·TTL/안전 gate/CSV 정책 변경, 장비 통신을 끊는 시험은 제안하지 않는다. current 후보 commit/installer/서버 전달·적용/롤백 갱신은 모두 미실행이다. 기존4c97d4a 복귀 기준 보존과 11절의 승인 목표는 유지한다.
- [x] 실제 independent coverage와 start/end 결과, 첫 full health 실패 원인 및 현재 재현 증거 저장.
- [x] 새 결함/조사와 수정·회귀 제안을 concrete review 문서에 저장; canonical plan 사본 동기화.
- [ ] 사용자 수정 선택 → 계획 범위 먼저 갱신 → 영구 red/repair/green·원래 probe·인접 정상 경로 검증.
- [ ] 최종 frontend/Chrome/기본 health/독립 리뷰 완료 후 후보·패키지·승인 서버 적용·기준 갱신.


### 11.3 기본 health 재실행·패키지 사전 점검

- 실제 PowerShell7.6.5 기본 환경에서 npm run health를 다시 실행했다. wrapper의 환경·encoding override는 없으며 exit1, signal:null이었다. dependencies14/Electron94/frontend398+Node9/typecheck/lint/backendruff/mypy9는 PASS; backend880개(217.422s) 중 오류2·skip1로 QA chain에 도달하지 않았다.
- UTF-8로 읽는 canary subprocess stderr에 비UTF-8 바이트0xc0가 들어가 reader thread UnicodeDecodeError와 stderr:null/TypeError가 발생했다. PowerShell5.1→7 outer host 변경만으로 해결되지 않는다. 기존 같은2개/owned UTF-8 child PASS와 새 전체 FAIL을 구분한다.
- 실행 원문·actual receipt/source-before/after(571개 불변)·전체 stream audit는 .tmp_ui_s1_verify/closeout-health-default-20261009-002에 보존했다. 001은 cmd argument syntax setup 실패이며 제품 health 실행 결과로 세지 않는다.
- 로컬 복귀 설치본4c97d4a 및 이전d7a1b20의 길이·SHA256·NotSigned를 재확인했다. 두 파일은 기록과 일치하고 metadata가 불변이었다. Z는 개발 PC에서 NAS share로 매핑돼 있지만 서버의 현재 identity·연결·설치 상태는 아직 확인하지 않았다.
- worktree venv에 PyInstaller는 없다. 기존 main venv에는6.20.0/hooks2026.5가 있으나 release lock40개 중9개 버전이 다르므로 이 사전 점검만으로 후보 빌드 환경이 완성됐다고 기록하지 않는다. 패키지 단계에서 기존 lock에 따른 격리 환경을 준비하며 main venv·lock·기존 installer는 자동 갱신하지 않는다.
- 사전 점검 증거는 .tmp_ui_s1_verify/closeout-preflight-20261009-001이다. installer 실행·새 빌드·서버 적용은 수행하지 않았다.

## 12. 사용자 A안 승인 — 후속 8건 보완 및 응답 지연 조사

- 사용자 원문: **A안(권장): 추가 발견 8건 수정 + 응답 지연 조사 및 확인된 문제 보완.** 기존 UI-S1 브랜치·계획을 이어 사용한다. 후속 review 문서의 R3–R10과 I1을 승인했다. 원래 QA→review→candidate/package→approved server/baseline 목표를 유지한다.
- 승인 기록: .tmp_ui_s1_verify/followup-correction-20261009-001/approval.json. 구현 전에 이 범위를 기준 계획 두 사본과 PDCA에 저장한다. 새 permanent test의 실패를 확인한 뒤 repair→green 순서로 검증하며, 과거 FAIL/PASS/receipts는 보존한다.
- R3 QA: run_qa_selftests.cjs child 환경의 PSModulePath를 대소문자 구분 없이 제외한다. 세 표기의 오염된 환경/정상 native/첫 실패 exit 전달을 기존 실제5개 self-test로 확인한다. 부모/사용자/머신 환경과 기존5개 PS helper 바이트는 보존한다.
- R4 수신 age: 신뢰한 snapshot/value age floor와 monotonic anchor를 invalid receipt와 분리해 유지한다. invalid timing 구간은 UNKNOWN이며 같은 poll의 정상 timing 회복이 age/cache를 회춘시키지 않는다. 두 age는 독립 처리하고 새 poll/service의 정상 복구를 허용한다.
- R5 poll 완료: 같은 service/poll에 완료 관측 후 지연 not_attempted가 오면 SPOT/comm.spot/receipt를 보존한다. 초기 poll0·새 service·다음 완료 poll의 수용을 유지한다.
- R6 진단 렌더링: 외부 enum/detail 값을 안전한 문자열로 정규화한다. 비정상 객체를 React 자식으로 전달하지 않고 UNKNOWN/--로 표시하며 정상 값·오류·복구 계약을 보존한다.
- R7 service 세대: unknown broadcast service는 현재 SPOT을 보존하고 권위 있는 직접 health 확인 후 교체한다. 같은 unknown 세대의 중복 confirmation을 막고, 최신 직접 요청으로 실제 service를 복구하며 먼저 시작한 요청의 늦은 완료가 최신 세대를 되돌리지 못하게 한다. follower 무조회 정책에 **세대 변화 확인에만 한정된 예외**를 승인했다. 정상 polling/leader 선출/visibility/backoff 정책은 유지한다.
- R8 stale: 같은 service/poll·같은 freshness 정책에서 이미 확인한 backend stale을 지연 fresh 표현으로 되돌리지 않는다. 새 완료 poll은 정상 복구를 허용한다. backend freshness/TTL/안전 gate 임계값은 바꾸지 않는다.
- R9/R10 메뉴: desktop 메뉴를 헤더 아래 viewport 높이 안에서 scroll 가능하게 하고 진단 dl에 가까운 theme text token을 적용한다. 기존 mobile fixed drawer와 light/dark/auto를 유지한다.
- I1 조사: 기존 integration의 지연 직접 응답에서 실제 API timeout/캡처 시점과 source/cache age를 먼저 재현한다. 확인된 경우 frontend 요청→수신 monotonic duration을 보수적인 표시 age에 더하고 follower 전달에도 누적 경과를 보존한다. backend 캡처가 늦으면 duration이 과대평가될 수 있는 한계를 문서화한다. backend timestamp/API schema 변경은 별도 범위 확인 없이는 수행하지 않는다.
- 기존 승인 QA의 남은 인코딩 실패: 현재 두 canary 기존 회귀의 정확한 child boundary를 먼저 확인한다. 필요하면 QA 명령/시험 진입에서만 UTF-8 출력을 명시하고 default full health로 재검증한다. production backend·수집·CSV·서버 helper 원문·hash-bound kit를 오류 우회용으로 바꾸지 않는다. codec replacement/errors=ignore, assert 제거, skip 추가, stderr:null 무시로 PASS를 만들지 않는다.
- 수정 대상: 기존 useSystemViewModel.health.ts/useSystemViewModel.ts/useSystemViewModel.types.ts/useSystemViewModelEffects.ts·기존 healthPolling.integration.test.tsx/effects 시험, commBadge.ts/기존 단위시험, App.css/관련 header 시험, QA runner 및 필요 최소 QA 시험 진입, 관련 PDCA 문서. 구현을 따라가는 테스트·범용 framework·전면 theme refactor는 추가하지 않는다.
- 검증 순서: 승인범위 기록 → 기존 source/증거 보존 → 새 permanent focused red와 기존 실제 QA/desktop 재현 → 좁은 repair → focused/인접 정상 및 복구 green → frontend전체test/typecheck/lint/build·실제 Chrome 상태/색상/메뉴 → 기본 full health → 최종 independent review/start binding → clean candidate commit·locked package·실 API→UI → 승인 서버 적용/회수·기준 갱신.
- 관측 성공 조건: same-poll invalid/startup/stale 및 unseen legacy service가 최신 장애/경과를 덮지 않음; 객체 진단에도 실제 header가 렌더링됨; duplicate generation confirmation과 역순 직접 완료가 SPOT 세대를 되돌리지 않음; 응답 지연의 source/cache freshness가 허용 기한을 넘으면 STALE; desktop1440×768/1024×768/mobile390×844 마지막 제어·진단12행 접근 및 light/dark/auto 가독성; QA case3개와 실제5개 self-test/full health의 최종 exit0.
- 제외·보존: backend API/temperature value/수집/서버 TTL/안전 gate/CSV·장비 설정 변경 및 실제 통신 중단 시험. 기존 main 미커밋 변경·installer·원문 증거·4c97d4a 복귀 기준을 유지한다. 서명/설정/terminal 미검증을 승인 때문에 PASS로 바꾸지 않는다.
- [x] 직접 사용자 A선택 기록과 계획 사본/PDCA 범위 갱신.
- [x] focused permanent red → repair → green 및 원래 probe/인접 정상 계약.
- [ ] frontend 전체/Chrome/default full health/최종 독립 review.
- [ ] 실제 candidate commit·installer SHA256/서명·패키지/API→UI.
- [ ] 승인 서버 적용·CSV/설정/실행 세대·증거 회수·다음 롤백 기준 갱신.


### 12.1 QA 인코딩 경계와 구현 전 실패 근거

- 승인한 QA 보완의 정확한 변경 경계는 backend/tests/test_spot_realtime_image_canary_kit.py의 기존3개 PowerShell subprocess 소비 진입이다. 이 파일은 production backend 로직이 아니라 기존 QA 도우미 검증 시험이다. 기존2개의 default full health 실패가 repair 전 red이며 controller·네 변조 진단·실패 종료 계약을 그대로 유지한다.
- 출력 encoding을 추정하거나 Console.OutputEncoding/공유 console codepage를 변경하지 않는다. capture_output의 원본 bytes를 받아 기존 ASCII PASS/오류 문구를 같은 byte literal로 정확히 확인한다. stderr replacement/ignore/None 우회·skip·assert 제거 없이 같은 helper·argv/cwd/env/returncode를 검증한다. PS 도우미·기존 hash-bound kit·run_backend_unittest.cjs 원문은 보존한다.
- R4/R5/R6/R7/R8/I1의 영구 회귀를 기존 두 파일에 먼저 추가했고 focused-red에서 새16개가 실제 실패했다(exit1/inputChanges[]). R6 header는 Objects are not valid as a React child로 재현됐고 I1 직접4초·follower payload 모두 실패했다. 기존 malformed timing4개만 인접 PASS했다. 추가 R7 복구/실패 재시도/hidden 사례도 원래 제품에서 먼저 실행한다.
- 같은 두 canary의 outer host만 바꾼 full FAIL 및 child UTF-8 PASS 기록은 역사적 진단 증거다. 과거 'owned child only' 문구는 공유 console codepage가 불변이라는 별도 증명으로 사용하지 않는다. 이번 원본 bytes 소비 보완에는 console setter 자체가 없다.
- 첫 R7 보완은 superseded 성공을 공개 null로 변환했으나, 12.6절의 실제 Diagnosis 회귀로 성공 호출 계약 위반을 확인하여 바로잡았다. 공개 호출은 실제 실패에만 null이며 성공 응답은 화면 적용 여부와 분리한다. 내부 polling superseded는 통신 실패/성공 receipt·재전송으로 계산하지 않는 neutral이다.


### 12.2 R7 확인 요청 도중 새 세대 도착

- 승인한 R7 세대 확인 보완의 인접 경쟁 조건을 영구 회귀로 추가했다. 현재 B에서 A 확인 요청이 시작된 뒤 C가 도착하면, B 응답이 요청 이후 도착한 C까지 과거 세대로 제외해 follower가 C로 복구하지 못했다. r7-later-generation-red는 responder 개수 2 대신 1로 실제 exit1/inputChanges[]를 기록했다.
- 확인 요청을 시작하기 전에 알려진 후보와 요청 도중 새로 도착한 후보를 분리한다. 직접 응답으로 제외할 수 있는 후보는 요청 시작 시점의 집합으로 한정하고, 이후 후보는 현재 요청 종료 후 최신 mounted/visibility/reconnect 조건에서 단일 후속 확인으로 처리한다. 각 집합과 제외 이력은 256개로 제한한다.
- 같은 후보의 중복 메시지는 추가 요청을 만들지 않는다. 직접 요청이 실패하면 다음 메시지에서 재시도할 수 있고, 이미 최신 직접 응답으로 수용된 세대는 후속 확인에서 제외한다. 기존 polling/leader/backoff와 latest-request-wins 계약을 보존한다.
- 수정 대상은 기존 useSystemViewModel.ts와 같은 integration 회귀 및 이 계획의 진행 기록이다. 새 독립 기능이나 backend/API 정책 변경은 아니다. 수정 후 전체 focused 세 파일과 실제 QA 경계를 순서대로 검증한다.


### 12.3 R9 실제 클릭 접근 보완

- 기본 full health는 default-health-green-003에서 exit0/inputChanges[]였다. dependencies14/Electron94/frontend419+Node9/typecheck/lint/backendruff/mypy9/backend880(실패0·기존private fixture skip1)/QA5개를 모두 실행했다. UTF-8 원문 전체와 단계·종료·571개 입력 불변은 audit.json에 확인했다. 앞선 typecheck exit2 및 lint exit1도 수정 전 증거로 보존한다.
- production build exit0 이후 native Chrome에서 desktop Light/Dark 색상 대비와 12개 진단 줄바꿈은 확인했으나, Auto의 실제 클릭은 AI 챗봇 launcher가 가로챘다. 004의 unique CSS 물리 클릭 실패와 menu-hit-before-R9-refinement.json의 receivesCenterClick:false/실제 svg·AI 챗봇 열기 버튼을 통해 제품 화면의 접근 미충족으로 확정했다. 초기001 wait syntax 실패와 구분한다. role-name matcher가 원인이라는004 준비 당시 추정은 실제 hit-test로 기각했다.
- 승인된 R9의 마지막 메뉴 제어 접근 조건을 충족하도록 desktop 메뉴 최대 높이에 하단80px 여유를 두고, 기존 mobile fixed drawer에는 하단80px 내부 padding을 둔다. launcher는56px 높이·bottom24px이고 header stacking context보다 위에 있어, 메뉴의 마지막 제어가 해당 영역에 놓이지 않게 한다. AI 기능·stacking 정책·modal/backdrop는 변경하지 않는다.
- 각 viewport/light-dark-auto에서 마지막 제어의 사각형뿐 아니라 elementFromPoint와 실제 click을 확인한다. 기존 under/over/timeout/복구/초기/unknown HTTP→화면도 이어 검증한다. CSS 보완 이후 frontend 검증·build/Chrome와 기본 full health를 최종 상태에서 다시 확인한다.


### 12.4 A안 로컬 보완·Chrome 검증 결과

- R3 환경명 세 형태에서 실제 QA5개가 각각 exit0. 기존 Get-FileHash red와 실패 종료 원문은 보존한다. canary 기존13개도 원본 bytes 진입에서 exit0이며 helper8개와 run_backend_unittest.cjs SHA256은 repair 전과 같다.
- R4/R5/R6/R7/R8/I1의 영구19개 및 R7 요청 도중 세대 교체1개는 제품 수정 전에 실패를 확인했다. focused 세 파일118개 exit0 이후 superseded 인접 cadence6개 exit0 및 전체frontend419+Node9를 확인했다. cadence 첫 실행은 setState 호출 횟수를 계약으로 잘못 가정한 시험 실패이며, 상태·주기·재전송 계약으로 수정한 결과와 구분한다.
- 원래 composition report-only4개를 byte-identical 사본에서 다시 실행해 exit0, 실제 App의 기존 native follower BC/storage 세 경우·복구도 exit0/JS오류0/외부요청0이다.
- R9/R10 final production build exit0/4577 modules/Router graph PASS. Native gstack Chromium의1440×768·1024×768·390×844 × Light/Dark/Auto 총9개에서 진단12행·줄바꿈·대비13.37~15.80, 마지막 제어 viewport/center hit와 실제 theme click PASS(exit0). Auto 클릭 가림 red와 wait setup 실패를 포함한001~004 원문은 보존하고005가 최종 PASS다.
- I1 backend build_health_payload가 plc health 뒤 runtime/static 상태를 구성하는 경로를 직접 확인했다. frontend 요청→수신 monotonic duration을 표시 age에 보수적으로 누적하고 실제 follower payload에도 전달한다. 늦은 backend 캡처에는 과대평가 가능성이 있으며 서버 TTL/안전 gate를 바꾸지 않는다.
- 최종 입력571개와 보호 helper 불변은 local-correction-source.json에 기록했다. 기본 health003 exit0는 R9 마지막 CSS 보완 전이며, CSS 최종 상태 health004가 실행 중이다. 최종 독립 리뷰/binding·candidate/package·실 API/장비·승인 서버 적용/회수/기준 갱신은 이어 수행하며 전체 완료로 보고하지 않는다.


### 12.5 최종 CSS 상태 기본 health 통과

- default-health-green-004: 실제 npm run health exit0/signal:null, 2026-10-09T01:27:24.140Z~01:32:48.873Z, 입력571개 불변. 전체 stdout162686bytes/SHA256 8f9993d7c1aac491350fad90142c1734c89c2f0052059f2fefac99e681b6f1cc, stderr20694bytes/SHA256 5da561dfef62d7e5dfafaa655f1db494a3466c4867c44da972efbef0cab2737b를 원문 그대로 읽어 audit.json에 단계/결과를 확인했다.
- dependencies14/Electron94/frontend419+Node9/typecheck/lint/backendruff/mypy9/backend880(223.288s, OK·기존private fixture skip1)/QA5개 모두 실행했다. 예상 음성 fixture ERROR 로그와 기존 Starlette deprecation은 실제 테스트 실패와 구분한다. Console/encoding/module 경로 override 없이 실행했다.
- 12.4절의 실행 중 상태는 당시 기록이다. 최종 health 통과를 근거로 현재 코드·시험·문서를 고정하고 새 실제 REVIEW_START/PASS_START로 전체 독립 재리뷰를 수행한다. 후보 패키지/실 API·장비/승인 운영 적용·회수·기준 갱신은 아직 미완료다.


### 12.6 R7·R9·R10 승인 보완의 인접 회귀 수정

- final-review-20261009-001에서 읽기 전용 specialist8개/native가 종료됐다. 기존 실제 core/native token의 start/end wtree는 동일하지만 unresolved 결과의 binding state는 incomplete다. 기본 health004 PASS를 최종 review PASS로 해석하지 않는다. 추가 사용자 선택 대기는 없다.
- R7a: 실제 view-model과 useObservabilityHandlers를 함께 사용한 report-only 회귀가 exit1이었다. 1500ms에 시작한 수동 Diagnosis의 성공 HTTP 응답이 2000ms 정기 poll 때문에 superseded→null로 바뀌어 Diagnosis failed.를 표시한다. 최신 SPOT·receipt·broadcast 보존은 이미 PASS다. 승인된 R7 구현이 훼손한 기존 성공 호출 계약을 복원한다. 공개 fetchHealth는 실제 성공 데이터를 반환하고, 화면 반영·polling broadcast 권한은 최신 요청에만 준다. 실제 실패는 null, 내부 superseded는 neutral을 유지한다. 영구 실제 호출자 회귀를 먼저 추가하여 red를 확인한다.
- R10a/R9a: native Chromium의 실제 computed style에서 desktop36개 상태/viewport/theme를 측정했다. Light/Auto OK/WARN/ERROR/IDLE와 Dark IDLE Temp 배지 대비가 4.5:1 미만이며, 1440px 상세 값 폭이42px이었다. 모바일 desktop-header selector wait는 숨겨진 요소 때문에 timeout으로 끝나 모바일18개는 미측정이다. 준비 실패를 대비 결함과 구분한다.
- Temp 배지에만 theme text-primary를 적용하고 상태별 border·명시적 label·Comm 집계를 유지한다. desktop 상세 메뉴 기본 폭에도 기존 1180px 이하의 min(360px, viewport-28px)/viewport max-width를 적용하며 mobile fixed drawer를 유지한다. 임의의 전체 palette·AI layout 변경은 제외한다.
- native I2의 source-sequence Map/retired-service Set 누적은 정적으로 확인했으나 운영 압력은 미측정이다. 단순 오래된 identity 삭제는 구버전 지연 응답을 되살릴 수 있어 즉시 실행하지 않는다. 기존 ordering/legacy 호환을 보존하는 대안을 조사하고, 추가 계약 변경이 필요하면 구체적 영향·제안 회귀를 저장한 후 별도 범위를 확인한다.
- 순서: 이 계획 사본 저장 → 실제 Diagnosis permanent red → R7a/CSS 좁은 수정 → focused/전체 frontend/typecheck/lint/build → 기존 menu/follower/composition 및 새 Temp6상태×3viewport×3theme 실제54개 → 최종 기본 health → 새 token의 독립 zero-edit 재리뷰. 변경된 소스에 과거 PASS를 재사용하지 않는다. 3 fix-cycle 제한과 protected helper/main/운영 installer 보존을 유지한다.
- [x] 실제 Diagnosis 영구 회귀 red→repair→green·기존 poll neutral/실패/복구 계약.
- [x] Temp 대비·desktop 진단 줄바꿈·mobile/마지막 제어 실제 접근 검증.
- [ ] I2 retention 조사·영향/처리 결정; fresh final health/review.
- candidate commit/installer·승인 서버 적용/증거 회수/rollback baseline은 미완료다.


### 12.7 인접 보완의 실제 검증·기존 backend timeout 조사

- 실제 Diagnosis 영구 회귀는 제품 수정 전 exit1, 수정 후 focused120개 exit0다. 공개 성공 응답을 반환하고 최신 화면·receipt·broadcast 쓰기를 보류하는 기존 계약을 복원했다. 내부 neutral/주기·실패·정상 복구 회귀도 포함한다.
- 전체 frontend420+Node9, typecheck/lint/build exit0; build4577 modules/Router PASS. 처음 PowerShell 경로 오지정(-4058)과 native coordinator fetch 실패/모바일 selector setup 실패를 해당 실행 원문에 보존한다. 제품 실패와 구분한다.
- Temp54개 조합은 현재 소스571개가 같은 desktop36개와 실제 drawer text selector의 mobile18개를 대조하여 audit exit0로 확인했다. 배지 최소 대비11.3737:1, desktop 진단 값 폭222px. desktop36개 실행은 이후 모바일 aria-label 없는 selector에서 exit1이었고, 이 준비 오류를 제외한 행 검증과 fresh mobile18개 exit0를 구분하여 기록한다. Auto의 실제 테마는 day다.
- 메뉴9개 화면·테마/마지막4개 제어 실제 hit/click·진단12개와 정상/under/over/timeout/복구/초기/unknown 상태 exit0. 원래 composition4개 exit0, 실제 App follower legacy/source/leader3개 및 복구 exit0/JS오류0/외부요청0. 원래 fixture 바이트는 새 출력 폴더로 복사하며 기존 증거를 덮어쓰지 않았다.
- default-health-adjacent-green-005의 이름은 결과 판정이 아니다. 실제 exit1/backend880개(233.918s, errors1·기존skip1)이며 test_control_waits_for_pending_peer_final_receipt의 asyncio.timeout(3)에서 TimeoutError였다. frontend420+Node9/dependency14/Electron94/typecheck/lint/ruff/mypy는 PASS, QA chain 미도달이다. source571개 불변, 전체 raw audit는 actual-result-audit.json에 저장했다.
- 해당 backend 시험/production app diff는 없고, 같은 runner의 APPDATA/SFL_CONFIG_PATH를 유지한 별도 프로세스 focused replay001/002는 각1개 PASS(exit0, .251s/.236s)다. test/control cleanup 원문을 직접 읽었으나 환경 타이밍이라는 원인은 아직 확정하지 않았다. test timeout·assert·production shutdown·환경 encoding을 바꾸지 않았다. 기본 full health retry006은 동일 소스에서 실행 중이다. 실패 원문을 이후 PASS로 재작성하지 않는다.
- fresh 최종 독립 review 및 추가 I2 선택은 남아 있다. 원래 A안 승인8건/I1을 다시 묻지 않는다. I2의256개 상한+capacity miss 직접 API 확인은 별도 제안으로 closeout review에 저장했고 질문 D2의 실제 응답을 기다린다. 응답 없음은 승인/Skip이 아니다. 후보 commit·installer·서버 적용·rollback baseline은 미완료다.
- 실행 root: .tmp_ui_s1_verify/final-review-20261009-001, 실제 command receipt/raw는 followup-correction-20261009-001의 adjacent-* 및 health005/006 폴더다. source/head는35959c41edee29573040d571ead952c073f1be13 + 승인 미커밋 수정이며 main의 기존7개 dirty tracked 상태는 유지된다.


### 12.8 최종 health006 PASS와 남은 범위 선택

원래 A안 R3–R10/I1 및 성공 Diagnosis·배지/메뉴 가독성 인접 보완의 로컬 검증 완료. frontend420+Node9/typecheck/lint/build, Chrome 및 기본 health006 exit0. 추가 I2 선택·fresh 최종 독립 review·후보/운영 단계는 미완료. 각 앞선 검증은 당시 입력의 기록이며 실패 원문을 이후 성공으로 덮어쓰지 않는다.

- 성공한 수동 Diagnosis를 정기 poll이 supersede해도 성공 데이터를 반환한다. 최신 요청만 대시보드 SPOT·receipt·broadcast를 쓸 수 있고 실제 실패는 null, 내부 superseded는 neutral이다. 실제 view-model+Diagnosis 영구 회귀 red(exit1) 뒤 focused120개 exit0를 확인했다.
- Temp 배지에만 text-primary를 적용하여 명시적 상태 label·상태 border·Comm 집계와 Temperature/TTL/gate 계약을 유지했다. desktop 상세 메뉴 기본 폭을 기존360px/viewport 제한으로 맞췄고 mobile drawer를 유지했다.
- Temp6상태×3viewport×3theme의 실제54행은 배지 최소 대비11.3737:1, desktop 진단 값 폭222px이다. 소스571개가 같은 desktop36행과 fresh mobile18행을 audit로 결합했다. desktop 실행의 후속 모바일 selector timeout, coordinator fetch 오류와 잘못 지정한 PowerShell 경로의 시작 실패는 준비 실패로 보존한다. Auto는 실제 day 테마였다.
- 메뉴9조합의 진단12행/마지막4개 제어 실제 hit·click과 상태/복구7개 exit0. 원래 composition4개 exit0, production App의 native follower legacy/source/leader3개·복구 exit0, JS오류0·외부요청0. 합성 API 결과이며 실 backend/장비·installer 검증으로 확장하지 않는다.

| 검사 | 실제 현재 결과 |
|---|---|
| frontend npm test |42파일420개 + Node9개 PASS / exit0 |
| frontend npm run typecheck / lint / build | 모두 exit0; build4577 modules, Router contract PASS |
| 기본 npm run health006 | exit0 / dependency14·Electron94·frontend420+Node9·ruff·mypy9·backend880(220.408s, 기존skip1)·QA5개 |
| 이전 동일 소스 health005 | exit1; 변경하지 않은 test_control_waits_for_pending_peer_final_receipt의3초 TimeoutError, QA chain 미도달 |
| 동일 격리의 해당 시험 단독 replay001/002 | 각1개 PASS / exit0; 시험·timeout·assert·production backend 변경 없음 |

health006은2026-10-09T02:19:32.320Z~02:24:28.509Z, 입력571개 불변이다. 전체 stdout162680bytes/SHA256 27e71f912e870b59a376b20f697fd1477b6b4b4bb04f01d48d5c29e1d82e9dc1, stderr20359bytes/SHA256 9eff5def1f7294126c19c8993df32200a305121f972d1aea8b849af40a96f69d를 strict UTF-8로 모두 읽었다. 예상 실패 fixture 로그·기존 deprecation·private fixture skip1과 실제 결과를 구분한다. health005의 비일관 종료 시험 timeout 원인은 확정하지 않았고 영구 수정을 했다고 주장하지 않는다.

현재 evidence는 .tmp_ui_s1_verify/final-review-20261009-001의 badge-matrix-audit/menu-access-audit/pre-health-checks-audit와 followup-correction-20261009-001의 adjacent-*·default-health-adjacent-retry-006/audit.json이다. 실제 commands/exit/raw/source-before/after는 각 receipt를 따른다. 예전 원문·hash-bound helper9개·main 기존 dirty7개 상태·운영4c97d4a 및 rollback 기준을 보존한다.

최종 source는35959c41edee29573040d571ead952c073f1be13 + 미커밋 UI/QA/관련 문서다. review001은 보완 전3건+I2를 발견한 incomplete 기록이며 current zero-edit review가 아니다. fresh 독립 reviewer/token을 아직 실행하지 않았다. I2 capacity miss 직접 API 확인은 closeout review의 구체적 별도 제안/미실행 회귀를 읽고 사용자 D2 응답 후 범위를 저장한다. 현재 I2 제품/영구 시험 변경·Skip 결정은 없다. 후보 commit/installer SHA256/서명·패키지/API→UI·승인 서버 적용/CSV/설정·회수·다음 롤백 기준은 남아 있다.


### 12.9 승인된 패키지 검증의 격리 환경 준비

- 11절 후보/패키지 승인과 11.3절의 lock 기반 새 환경 준비를 이어 수행한다. I2 추가 로직/영구 시험/Skip은 응답 전 실행하지 않는다. final review·candidate commit·installer·운영 적용 상태는 미완료를 유지한다.
- 실제 Desktop/SmartFactory/S1_PKG_20261009_R1을 신규 생성했다. 정규화 경계·부모 reparse 부재와 현재 사용자 읽기 ACL을 확인했고 부모 ACL은 바꾸지 않았다. 일반 Explorer 접근은 아직 화면에서 확인하지 않았다.
- Python3.12.6(C:/Python312/python.exe)으로 이 실행 폴더의 venv를 생성하고, 원래 requirements-windows-release.lock(40개, SHA256 e02cbc44a097eccc93f2986e023bee57881b52a1f6ee28c81f86a953a9bb0672)의 검증 사본에 --require-hashes/--only-binary=:all:를 적용한다. lock·main venv·기존 installer를 갱신하지 않는다. 원문 stream·실제 argv/exit·설치 report·버전/해시 대조를 records에 남긴다.
- 이번 단계는 빌드 환경 준비다. dirty checkout에서는 PyInstaller provenance가 허용하는 clean HEAD 요건을 우회하거나 installer를 만들지 않는다. 현재 소스571개 hash·main venv 패키지 목록/설정·복귀 installer SHA256을 전후 대조한다. 제품 소스 검사를 환경 준비 때문에 반복하지 않는다.
- [x] venv·hash-locked40개 설치·pip check와 설치 report 해시/버전 대조.
- [x] 현재 제품 소스/main 환경/복귀 installer 보존과 준비 결과·계획/PDCA 동기화.
- [x] 필요 browser 자원과 local Explorer 접근 실제 검증.
- [ ] 최종 후보 provenance/패키지/운영 단계 실제 검증.

- 격리 release Python으로 기존 실제 backend 절차(-m ruff check backend, -m mypy, -m unittest discover -s backend/tests)를 순차 실행한다. 새 test-appdata/SFL_CONFIG_PATH만 사용하며 production runner·시험·timeout·encoding은 바꾸지 않는다. 이는 dev health PASS와 다른 dependency 환경의 패키지 사전 검증이며 installer/실장비 PASS로 기록하지 않는다.


### 12.10 격리 릴리스 환경 준비·backend 사전 검증 결과

- Desktop/SmartFactory/S1_PKG_20261009_R1의 새 Python3.12.6 venv에 기존 lock40개를 --require-hashes/--only-binary=:all:로 설치했다. pip report40개 wheel SHA256과 설치 버전40개가 lock에 일치하고 pip check exit0다. 기존 main venv의 패키지 목록/pyvenv.cfg, lock, 두 복귀 installer의 bytes·SHA256·mtime 및 제품 소스571개가 전후 동일하다. 이를 전체 main 환경 바이트 전수 검증으로 확대하지 않는다.
- 격리 release Python의 기존 ruff check backend 및 mypy9개는 각각exit0, unittest discover -s backend/tests는880개/225.868s/OK(skipped=1)/exit0다. owned test-appdata/SFL_CONFIG_PATH에서 실행했으며 시험·assert·timeout·production runner·encoding은 바꾸지 않았다. 전체 stdout133698bytes(SHA25604647d37bba720eb8234fd7cf173afef160b5e5f77fdf4bcc748f67a1cd8c88e), stderr20519bytes(SHA256fac73d42559af9aac5ddde115cbb47d36b6b44635d5e90928c980eb38bf4660d)를 strict UTF-8로 읽고 audit했다. 기존 private fixture skip1/예상 음성 fixture ERROR·deprecation을 실제 실패와 구분한다.
- 기존 빌드 흐름의 별도 Playwright browser 자원을 owned browsers에 준비했다. Playwright1.62.0/Chromium151.0.7922.34가 local HTML을 렌더링하고 정상 종료(exit0, 외부 요청0)했다.610파일/735085639bytes의 manifest SHA256284328585e6485fbbd59d132b8043a2d40d9c3c6f9c8fac9b3ff7eab62d4427f, 가장 긴 resource 경로188자로240자 안이다. 현재 owned browser process0을 실제 CIM에서 확인했다. NSIS 포함 여부와 실제 packaged 동작은 아직 검증하지 않았다.
- computer-use의 실제 Windows Explorer 새 탭에서 준비 폴더와 records/refs/venv/test-appdata를 확인했고 owned 탭만 닫아 원래 두 탭을 유지했다. 부모 ACL/원래 폴더/운영 경로를 바꾸지 않았다. 서버 Explorer나 전달·설치 검증으로 해석하지 않는다.
- evidence는 위 실행 폴더의 records/stage-ready.json, preparation-result.json, release-environment-audit.json, release-backend-checks-audit.json, release-browser-audit.json, explorer-access.json과 각 command/raw receipt다. 기존 증거를 덮어쓰지 않고 새 기록으로 보존했다.
- I2 응답은 아직 없다. I2 구현/영구 시험/Skip, fresh 최종 독립 review, clean candidate commit·PyInstaller/installer·API/장비·승인 서버 적용/회수·rollback baseline 갱신은 미완료다. 패키지 환경 준비를 후보/운영 완료로 기록하지 않는다.


### 12.11 현재 운영본의 읽기 전용 원격 사전 확인

- Chrome 원격 데스크톱의 DESKTOP-Extrusion 연결에서 실제 운영 대시보드와 localhost:8000/health를 확인했다. RDP alias와 OS hostname의 대응은 이번 화면에서 별도 검증하지 않았다. 2026-10-09T03:16:46.726Z 및03:21:48.412Z body 시각의 두 응답은 commit4c97d4a00d79ae0d3da70b2e82af227345e21040/app1.0.26/frozen/packaged-resources이며 frontend_static_ready와 running/driver/thread가 true다. 신규 후보가 적용된 결과가 아니다.
- 같은 SPOT service와 logger service를 유지하며 약301.686초 사이 poll83113→83415(+302), API가 보고한 CSV rows359687→360967(+1280)를 확인했다. current CSV는 Factory_Integrated_Log_v2_20261009_000000.csv다. 원본 CSV 파일 읽기·무결성/프로세스 소유자/설정 파일 hash 검증은 수행하지 않았으므로 API counter 증가를 그 검증으로 확대하지 않는다. 기존 config_drift_detected_count1, previous_poll/fact_only 진단의 한계는 유지한다.
- 원문 health.json(6360bytes/SHA256128e43508052e7bbcc1ba0ea4bd140ede7d64c77cce0b3ff97216349c60567d2), health-002.json(6361bytes/SHA25695fa05ba2b949b606a1f7ec0fda9c00517f927863d2a70cbbc174158fd1af7c9)을 서버 Edge의 SaveAs로 Z:/SmartFactory/20261009/return/S1_PREFLIGHT_20261009_R1에 저장하고 개발 PC records/server-preflight-001로 회수했다. 두 위치의 byte SHA256이 일치하고 strict UTF-8/JSON 파싱을 확인했다. 서버 로컬에서 hash 명령을 실행한 증거는 아니다.
- 조회용 새 Edge 창을 닫고 Running 대시보드 복원을 실제 화면과 remote-dashboard-restored.png로 확인했다. installer/수집 정지/장비·작업 설정/보안 설정/운영 baseline 변경은 수행하지 않았다. 최초 URL 입력의 colon→semicolon 검색 오류는 바로잡은 뒤 실제 localhost 응답을 저장했으며 검색 화면을 API 증거로 쓰지 않는다.
- evidence: Desktop/SmartFactory/S1_PKG_20261009_R1/records/server-preflight-001의 health-audit.json, ui-observation.json, 두 원문 JSON과 remote-health.png/remote-dashboard-restored.png. shared return 위치는 원문 회수 목적이며 서버 최종 candidate 전달 완료를 뜻하지 않는다.
- 승인8건/I1 로컬 검증은 유지한다. I2 직접 선택/추가 구현·시험 또는 explicit Skip, fresh 최종 독립 review, clean candidate commit·installer/API→UI·승인 운영 적용/회수·다음 rollback baseline은 여전히 미완료다.


### 12.12 후보 패키징 설정·provenance 차단 검증 및 I2 의존성

- 현재 실제 HEAD는35959c41edee29573040d571ead952c073f1be13이고 전체 git status는 dirty다. 기존 backend.version의 write_build_provenance_file과 verify_build_source_commit을 격리 release Python에서 직접 호출하여 dirty 시작/종료를 모두 거부하는 것을 확인했다. probe exit0는 거부 계약 검증 성공이며 PyInstaller 빌드 PASS가 아니다. provenance 파일을 생성하지 않았고 우회/환경 commit 대체를 하지 않았다.
- electron-builder26.15.3의 실제 validateConfiguration으로 candidate-builder.config.json을 검증했다(exit0). 기존 package.json.build 대비 directories.output과 extraResources[0].from만 실행 폴더의 packaging/electron 및 packaging/backend-dist/SmartFactoryBackend로 지정했다. appId/asar/files/frontend·QA resources/NSIS·버전 설정은 동일하며 세 버전은1.0.26이다. schema 통과를 installer 동작/포함 파일 PASS로 해석하지 않는다.
- 원래 backend/build_specs/SmartFactoryBackend.spec(SHA2561dc131ddc9e3f2d5408172ea2ff22740e08ff90bf14e4131b1057f7c27cb2fe8)의 시작/종료 clean HEAD 검증을 그대로 사용한다. 준비 명령은 candidate-build-commands.json이며 PyInstaller --distpath/--workpath 및 electron-builder --projectDir/--config/--win/--x64/--publish never를 명시했다. 두 빌드 명령은 미실행이다. backend manifest와 기존 integrity verifier 확인 뒤 electron 단계로 진행해야 하며 잠금없는 deploy.ps1을 이번 단계에서 실행하지 않았다.
- evidence: Desktop/SmartFactory/S1_PKG_20261009_R1/records/candidate-preflight-001의 candidate-preflight.json, candidate-builder.config.json(SHA2561ffcbe61e710c2f27e958972fd2ad55f6cc027f0f6908c109e65909fb67df1d1), dirty-provenance-guard.receipt.json/raw 및 goal-blocked-audit.json. 제품 소스571개 불변·원래 main dirty 상태/복귀 installer·운영 기준을 유지한다.
- I2-A/I2-B의 직접 사용자 선택이 연속4개 실제 goal turn에 걸쳐 미응답이다. 기존 A8/I1 승인을 재요청하지 않는다. I2 선택 → 선택 범위 구현/Skip 기록 → fresh 최종 독립 review/binding → clean 후보 commit → 실제 패키지/API→UI → 승인 서버 적용/회수 → rollback baseline 갱신의 의존성이 남아 있다. 독립 선행 준비(locked env/backend 검사/browser/Explorer/운영본 health/빌드 설정과 dirty guard)는 완료했으며 선택 없이 후보 완료를 더 진행할 수 없다. 완료로 기록하지 않고 사용자 입력이 필요한 blocker로 유지한다.


## 13. I2-A 직접 승인 — 제한된 identity 이력과 capacity 확인

- 사용자 선택 문구 “I2-A 권장: 이력 상한 256개와 이력 밖 송신자의 직접 API 확인을 추가.”를 인용한 응답 “승인”을 직접 I2-A 승인으로 반영한다. annotation1 및 원문은 .tmp_ui_s1_verify/i2-correction-20261009-001/approval.json에 보존했다. 기존 A8/I1·후보/운영 승인과 같은 UI-S1 브랜치·기준 계획을 이어 사용하며 이전 blocked 원인은 해소됐다.
- received source-sequence Map과 retired backend-service Set을 각각256개로 제한한다. 현재 service는 퇴역하지 않는다. 동일 service/poll의 낮은 poll·완료→초기·stale/age floor 및 legacy/source/leader 순서 보호를 유지한다.
- retired 이력에서 빠진 service는 unknown으로 기존 R7 직접 확인을 거친다. source 이력이 capacity에 도달한 뒤 unknown/evicted source의 broadcast는 화면/receipt를 적용하지 않고 권위 있는 직접 /health를 단일 확인한다. 성공한 최신 확인 후에만 source/최대 sequence를 제한된 이력에 등록한다. 보류 후보/요청 도중 도착 이력도256개 이하이며 중복 확인·늦은 과거 응답의 역전·실패의 성공 처리를 허용하지 않는다.
- 실패·hidden·reconnect·unmount에서는 최신 SPOT/receipt를 보존하고 다음 허용된 메시지에서 재시도한다. 기존 latest-request guard/poll superseded-neutral·성공 Diagnosis 반환·leader/visibility/backoff는 유지한다. 추가 follower GET은 capacity miss 확인에만 한정한다.
- 수정 대상은 기존 useSystemViewModel.ts/useSystemViewModelEffects.ts/useSystemViewModel.types.ts, healthPolling.integration.test.tsx 및 effects 시험, 이 계획/PDCA/design/analysis/report/review 기록이다. 시험 전용 공개 API·범용 framework·backend/API schema/Temperature 값·TTL/안전 gate/CSV/장비·운영 설정 변경은 제외한다.
- 회귀: 257개 이상 sender 뒤 evicted legacy OK가 최신 timeout을 되돌리지 않음; 같은/다른 capacity-miss 중복과 실패·hidden/reconnect·늦은 이전 완료·정상 복구; 257개 이상 backend 교체 뒤 evicted retired UUID의 OK 수용 금지. 실제 adapter/view-model/BC·StorageEvent/fake-clock 기반 permanent test를 먼저 실행해 실패를 확인하고 resource 이력 상한을 private context에서 독립 검증한다.
- 순서: 승인/계획 저장 → 영구 회귀 red → 최소 repair/focused green → 전체 frontend/typecheck/lint/build·native follower/기존 composition/메뉴 → 기본 full health → fresh independent review/start-end binding → clean candidate commit/locked package·installer SHA256/서명/API→UI → 승인 서버 적용·수집/CSV/설정·증거 회수 → 다음 롤백 기준 갱신. 이전 FAIL/PASS와 package preflight는 당시 snapshot으로 보존한다.
- 완료 조건: 두 persistent 이력과 임시 후보 모두256개 이하; 이력 밖 지연 legacy/retired 메시지가 최신 장애·age를 덮지 않음; 권위 확인 dedupe/실패 retry/hidden/reconnect/latest-request 정상 복구; 기존 전체 회귀·health·fresh 리뷰 완료 및 최종 후보/운영 단계 증거 확보. 기존 3 fix-cycle 제한과 parent 단일 writer/verifier·최대3 read-only specialist 병렬 규칙을 유지한다.
- [x] 직접 승인과 기준 계획 두 사본 저장; I2 blocker 해소.
- [x] 영구 회귀 red→repair→focused/상한 green.
- [ ] 최종 frontend/Chrome/default health/fresh 독립 review.
- [ ] clean candidate commit·installer/패키지·실 API→UI.
- [ ] 승인 운영 적용/회수와 다음 롤백 기준 갱신.


### 13.1 I2-A 구현·최종 로컬 검증 결과 (2026-10-09T05:24:06.314Z)

- I2-A 직접 승인 보완의 로컬 검증 완료. 영구 회귀10개·focused91개, 전체 frontend430+Node9/typecheck/lint/build, 기본 health003 exit0 및 현재 Chrome/menu/composition PASS. fresh 독립 review·clean 후보 commit/installer·승인 운영 적용/rollback 기준 갱신은 미완료. 앞선12절의 선택 대기/blocker·health006 결과는 당시 기록이며 최신 I2 직접 승인과 검증은13절/이번 항목을 따른다.
- source-sequence Map과 retired-service Set을256개로 제한했다. 상한 이후 unknown/evicted 송신자는 broadcast를 적용하지 않고 단일 직접 /health를 확인한다. 요청 시작 전 후보와 도착 후보를 각각256개 이하로 유지하고, 최신 성공 확인의 최대 sequence만 등록한다. 실패·superseded·hidden·reconnect·unmount는 source를 등록하거나 SPOT/receipt를 갱신하지 않으며 다음 허용 메시지에서 재시도한다. 퇴역 UUID 확인에도 같은 응답 적용 guard를 연결했다. 현재 service는 retired 이력에 포함하지 않는다.
- capacity 원래7개는 먼저 exit1(직접 확인 미실행6개/retired257개1개)로 재현한 뒤7개 PASS했다. retired lifecycle 추가3개 중hidden/reconnect2개는 receipt 변경으로 먼저 exit1, unmount1개는 기존 계약 PASS였다. 최종 focused 두 파일91개 exit0, 기본 full frontend430개에 이 영구10개가 모두 포함된다. 테스트 전용 공개 API·backend/장비/Temperature/TTL/gate/CSV/설정 변경은 없다.
- default-health-003은2026-10-09T05:11:36.900Z~2026-10-09T05:16:50.139Z, dependency14/Electron94/frontend430+Node9/typecheck/lint/ruff/mypy9/backend880(209.376s, 기존private fixture skip1)/QA5개 전체 exit0다. stdout162688bytes/SHA256604b0604159accb340344f2b0903315eed2714c2a53e945989460fcb29f9b4ed, stderr20357bytes/SHA256976f6b104b52b6a9f3ef17d692e845b8cdfe1117bdf5f881541317af1ff77fba를 strict UTF-8로 모두 읽었다. 기존 음성 fixture ERROR·deprecation과 실제 실패를 구분했고 errors/decodeErrors0·571개 입력 불변이다.
- 이번 첫 typecheck exit2와 첫 health lint exit1은 새 시험의 ES5 Set 반복/this-alias lint 보완으로 해결했다. default-health-002는 V8 OOM 원문과 normal receipt 누락을 보존했으며 exec handle/owned wrapper·child가 사라진 것을 CIM으로 확인했다. 해당 종료 코드는 알 수 없다. 소스/runner/default 명령/시험 timeout·assert를 바꾸지 않고003을 재실행해 PASS했다. 일시 OOM의 근본 원인이나 재발 방지를 검증했다고 주장하지 않는다.
- 최종 production build4577 modules/Router contract exit0, composition report-only4개 exit0, native App HTTP→화면 상태·follower legacy/source/leader3개·복구 exit0/JS오류0/외부요청0다. 현재 native 상세 메뉴9조합(1440×768/1024×768/390×844 × Light/Dark/Auto)의 진단12행·마지막4개 실제 hit/click·줄바꿈·최소 대비13.3697:1과 상태/복구7개가 exit0다. Auto는 실제 day였다. 합성 API 검증이며 installer/실장비 PASS는 아니다. 새 owned fixture PID25260는 quit으로 정상 종료했고 CIM 부재를 확인했다. 기존/unrelated 사용자 탭은 닫지 않았다.
- evidence: .tmp_ui_s1_verify/i2-correction-20261009-001/local-result.json, 각 raw/receipt/source-before/after, default-health-003/audit.json, browser-results.json, native-browser-result-005.json 및 현재 캡처. 승인 전571개 중제품 변경3개만 VM/Effects/기존integration시험이며 나머지568개가 동일하다. 원래 승인 A8/I1/QA 입력은 보존한다.
- 원래 기준계획·branch·origin/master35959c41edee29573040d571ead952c073f1be13을 유지한다. fresh review002/start-end binding → clean 후보 commit → locked package/installer SHA256·서명·실제 API→UI → 승인 운영 적용/수집·CSV/설정/회수 → 다음 롤백 기준은 계속 필요하다. 현재4c97d4a 복귀 기준을 변경하지 않았다.


### 13.2 review002의 승인 범위 인접 보완 (2026-10-09T05:45:09.489Z)

- 모든8개 읽기 전용 specialist/native가 종료된 뒤, 제품 입력571개 불변을 확인하고 실제 native PASS_START의 결과를 먼저 저장했다. 원래 core REVIEW_START는 이번 최종 처리까지 보존한다. 실제 review002는2 CRITICAL/1 INFORMATIONAL이며 최종 zero-edit PASS가 아니다.
- I2a는 직접 승인 I2-A의 요청 중 도착·중복/최신 장애 보존 계약을 완성한다. 요청 시작 당시 source/sequence 후보는 수정하지 않고, 같은 source의 높은 sequence를 포함한 이후 도착분은256개 제한 arriving에 넣는다. 후속 확인은 기존 이력의 sequence floor보다 높은 후보도 확인하며, 보류 후보의 중복 broadcast를 먼저 적용하지 않는다. 직접 API만 receipt를 갱신한다.
- R5a는 이미 승인된 R5의 같은 service/poll 완료→초기 보호에 backend terminal config_missing을 포함한다. 현재 실제 backend가 시작 시 poll을 증가시키고 config_missing 완료를 발행하는 경로와 report-only CONFIG→WAIT failure(exit1)를 확인했다. 다음 poll 정상 복구는 유지한다.
- R10b는 승인된 UI-S1 온도 상태 구분·R10 가독성의 compact 표시 누락을 보완한다. 실제640×844 Chrome에서 Temp UNDER_RANGE aria label의 visibleText가 Temp였으며 native exit1이다. compact label에도 실제 측정 상태를 보여주고521/640/768px의 실제 표시/잘림을 검증한다. <=520px의 Comm-summary/상세 drawer 정책과 기존 theme·TTL·gate는 유지한다. 필요한 경우 기존 status-panel 제한 안에서만 좁은 CSS 조정을 한다.
- 제품 변경 전 기존 integration에 native-ID/legacy capacity-arrival2개·완료 CONFIG1개, 기존 header에 compact under-range1개를 추가하고 permanent red를 확인한다. 이후 위 세 생산 경로만 repair한다. 기존 시험의 단축Temp 기대값은 최종 실제 상태 표현으로 갱신하며 임의 assert 제거/timeout 확장/skip은 하지 않는다.
- 별도 mixed native→no-ID report-only는 DOWN→OK exit1이나, 승인 design70/75/84가 명시한 identity 없는 구버전 fallback/cross-source 순서 미보장 범위다. 새 global restriction·permanent test·임의 Skip으로 바꾸지 않는다. 이 한계를최종 결과에 남긴다.
- 수정 대상: 기존 useSystemViewModelEffects.ts/useSystemViewModel.health.ts/healthPolling.integration.test.tsx, DashboardHeader.tsx/기존시험 및 필요한 최소 App.css, 기준계획/관련 PDCA 문서. public 타입·backend/API·수집/Temperature/TTL/gate/CSV·장비/운영 설정 변경은 제외한다.
- 검증: permanent red → focused green → 원래 report-only2개/기존composition4개 → frontend typecheck/lint/test/build → 실제 production Chrome 상태/follower/compact521·640·768px와 기존 메뉴/대비의 영향 검사 → 기본 npm run health. 각 changed-input 단계의 실제 stdout/stderr/exit·571개 입력을 저장한다. 이전 I2 health003·build/native PASS는 이전 snapshot으로 보존한다.
- 이번은 원래 review의3번째 fix cycle이다. review SKILL.md Step5.8의 'At 3, persist converged:false … then STOP … without … a fourth pass'에 따라 검증 뒤 INCOMPLETE/nonconverged를 저장하며 이 invocation에서4번째 review를 만들지 않는다. 최종 독립 zero-edit review·clean candidate commit/installer/API→UI·승인 서버 적용/CSV/설정/회수·다음 롤백 기준은 여전히 필요하다. 전체 목표가 완료됐다고 보고하지 않는다.
- [x] 세 누락의 실제 red/승인 범위 연결·reader settlement·native 원래 token 저장.
- [x] 영구 회귀 red→최소repair→focused/original/adjacent green.
- [x] 최종 frontend/build/Chrome/full health와 cycles3 INCOMPLETE 기록.
- [ ] 이후 새로운 최종 review invocation·후보/운영 증거.


### 13.3 I2-A 인접 보완·현재 로컬 검증 결과 (2026-10-09T06:15:11.616Z)

- I2-A 및 review002의 인접 3건 보완·로컬 검증 완료. frontend 434개/typecheck/lint/build, 현재 Chrome와 기본 health002 exit0. review는3번째 수정으로 INCOMPLETE/nonconverged이며 최종 zero-edit review·후보·운영은 미완료다. 전체 목표가 완료된 상태가 아니다. 원래 세번째 fix cycle에 대한 core token 종료 기록은 다음 처리에서 저장한다.
- I2a: 요청 시작 후보 sequence를 고정하고 같은 sender의 높은 후속 sequence를 arriving에 보관하여 별도 직접 API로 확인한다. 확인 중 중복 broadcast가 화면/receipt를 덮지 않는다. R5a: backend terminal config_missing을 완료 관측에 포함하여 지연된 같은 poll not_attempted를 거절하며 다음 poll 복구를 허용한다. R10b: compact Temp에도 실제 상태를 표시하고521–768px 헤더/배지가 내용에 맞게 줄바꿈하여 잘림을 해소했다.
- 제품 수정 전 영구 회귀 4개가 모두 실패(exit1). 이후 focused 109개 exit0; 원래 capacity/config probe 각1개와composition 4개도 exit0다. focused/original 두 probe 이후 App.css만 달라졌으며 최종 전체 frontend 434개개와 Chrome 검증이 현재 CSS를 포함한다. 위 6개 파일 외 565개 입력은 I2 health003과 동일하다. backend/API·수집·Temperature 값·TTL/gate/CSV·운영 설정 변경은 없다.
- 현재 default-health-002: 2026-10-09T06:05:43.015Z~2026-10-09T06:11:20.489Z, 실제 exit 0/signal:null, 입력 571개 불변. dependencies14/Electron94/frontend 434개+Node9/typecheck/lint/backendruff/mypy9/backend880(246.729s, 기존 private fixture skip 1개)/QA5개 모두 실행했다. 전체strict UTF-8 stdout162678bytes/SHA25670b5f83577ded7bb39953e78ab33dd8d0ddd6abeeb759f96224329c335c45941, stderr20359bytes/SHA2567a3ebf2c73cf5b4ca98cd770191fe4d2a4badc3b2054965abe88390812df72ac를 읽어 audit.json에 기록했다.
- 같은 소스의 default-health-001은 exit1/backend880(234.505s, errors1/기존 skip 1개)이며 기존 test_control_waits_for_pending_peer_final_receipt가 asyncio.timeout(3)에서 실패했다. 동일 APPDATA/config 환경의 별도 replay 1개는 .289s/exit0; timeout/assert/runner/production shutdown을 바꾸지 않은 전체002가 PASS했다. 원인·재발 방지가 검증된 것은 아니다. 최초 FAIL과 이전 OOM 및 다른 과거 FAIL은 그대로 보존한다.
- 최종 production build4577 modules/Router contract exit0. 현재 App의 합성 HTTP→화면 정상/under/over/timeout/복구/WAIT/UNKNOWN과 실제 follower 3경로 PASS, 격리 브라우저 JS 오류 0/외부 요청 0. compact 521/640/768px의 24개 조합 모두 텍스트가 완전히 보이고 가로 넘침 없음/최소 대비11.3737:1; 기존 상태×theme×viewport 54개 조합도 PASS. 메뉴 9개 조합에서 진단 12행·마지막 4개 제어의 실제 hit/click·최소 대비13.3697:1 PASS. Auto는 day였다. 공유 native console의 과거 404를 JS오류0 근거로 사용하지 않는다. 새 owned fixture들은 quit 정상 종료 후 CIM 부재 확인; 관련 owned 탭만 닫았다.
- 영구 회귀: healthPolling.integration.test.tsx:950 I2a legacy/identified2개 및:985 R5a CONFIG; DashboardHeader.test.tsx:179 R10b compact 상태. 현재 Effects:371–414/API 후보 guard, health helper:47 완료 분류, Header:489 상태 텍스트, App.css:355/937/945 실제 표시 보완을 검증했다.
- 한계: native-ID 이후 식별 정보가 없는 legacy가 들어오는 경우 DOWN→OK report-only FAIL을 보존한다. 기존 승인 설계 70/75/84의 fallback/cross-source 순서 미보장 계약이며, I2-A가 모든 구버전 순서까지 보장한다는 뜻이 아니다. 외부 Claude Code 미설치/structured 미실행, core의 과거 root Markdown 전체 미재독, 최종 zero-edit review 미실행도coverage gap으로 유지한다.
- review SKILL.md Step5.8: “At 3, persist converged:false … then STOP … without … a fourth pass”. 이번 invocation의 3회 수정 후 INCOMPLETE/nonconverged로 종료하며 4번째 pass를 만들지 않는다. 새 최종 review → clean 후보 commit/locked installer SHA256·서명·패키지의 실제 API→UI → 승인 서버 전달/적용·수집/CSV/설정·증거 회수 → 다음 롤백 기준은 남았다. 4c97d4a 복귀기준을 유지한다.
- evidence: .tmp_ui_s1_verify/review2-correction-20261009-001/local-result.json, default-health-001/actual-result-audit.json, default-health-002/audit.json, browser-validation-002/compact-views.json 및 browser-results.json, badge-validation-001/badge-current-001.json, native-browser-result-005.json, 각 raw/receipt/source-before/after.
- [x] I2-A·I2a/R5a/R10b 영구 red/repair/green 및 현재 전체 로컬 검증.
- [x] 원래 core token의 cycles 3 INCOMPLETE 결과 종료 저장.
- [ ] 최종 zero-edit review·후보/installer/실제 API·승인 서버 적용/회수/롤백 기준 갱신.


### 13.4 원래 review token 종료·현재 미완료 단계 (2026-10-09T06:19:32.978Z)

- 원래 REVIEW_START b973c737-c2f4-4432-bcea-d7bc571a6ba9를 실제 종료했다. gstack-review-log에 completed:false/converged:false/cycles:3/status:issues_found를 저장했고, 로컬 검증한 기존 승인 16개 finding의 fixed action/fingerprint/근거를 보존했다. 현재 확인된 미해결 결함 수는 0이지만, 수정 뒤 최종 zero-edit 독립 검토를 수행하지 않아 clean/PASS로 보고하지 않는다.
- logger가 계산한 binding은 changed다. 실제 start_wtree=8b6d1acc0614bab71e28ea5920c5d8d3c08269cf, end_wtree=08cb61849cf4343e579bba3fe8279d43541eadcd, start=2026-10-09T05:24:47.886Z; 제품·문서의 3회 수정으로 시작 snapshot과 다르다. caller supplied binding이나 새 start token으로 PASS를 만들지 않았다. native 원래 token은 수정 전에 이미 저장했고 외부 Claude Code 미설치는 coverage gap이다.
- 첫 logger argv 전달은 exit 1/invalid JSON이며 token 미소모를 확인했다. 동일 record를 파일에서 읽어 검증한 뒤 원래 token으로 재전달해 exit 0; 실제 로그 1행과 token 소모를 확인했다. 첫 실패와 재시도 receipt/raw를 보존한다. 처음 전달 실패의 근본 원인은 확정하지 않았다.
- 최신 근거: .tmp_ui_s1_verify/final-review-20261009-002/core-finish-file.receipt.json, final-review-20261009-002/actual-logged-cycle3-record.json, .tmp_ui_s1_verify/review2-correction-20261009-001/local-result.json. 세 번째 수정한 현재 소스의 health002/Chrome 검증과 13.3절의 한계를 유지한다.
- [x] 최종 frontend/build/Chrome/full health와 cycles 3 INCOMPLETE 종료 기록.
- [ ] 새 review invocation의 최종 zero-edit 독립 검토·유효한 unchanged start/end binding.
- [ ] clean 후보 commit·locked installer의 commit/SHA256/서명·패키지 실제 API→화면 검증.
- [ ] 승인 서버 최종 폴더 전달·적용 확인/수집/CSV/설정/실행 세대·결과 회수·다음 롤백 기준 갱신.
- 운영 복귀 기준 4c97d4a를 유지한다. 새 installer/서버 적용/기준 갱신을 수행하지 않았다.

## 14. 새 최종 review와 후보 검증 직접 승인

- 사용자 선택 “새 /review 시작 후 후보 검증 진행”을 새 invocation의 직접 승인으로 기록한다. 13.4절의 cycles3 INCOMPLETE와 changed binding은 과거 결과로 보존한다. 기존 승인 보완을 다시 요청하거나 이전 invocation의 네 번째 pass를 만들지 않는다.
- 현재 UI-S1 브랜치와 기준 계획을 이어 사용한다. 새 core/native 시작 token을 diff 읽기 전에 각각 확보하고, 최대3명의 읽기 전용 specialist를 순차 batch로 운영한다. 부모만 코드 수정·실행 검증을 수행한다. reviewer가 모두 종료되기 전 제품/시험/계약을 수정하지 않는다.
- 현재 snapshot에 대해 checklist critical→informational, scope에 해당하는 specialist와 native adversarial, 격리 functional/browser smoke 및 필수 plan 명령을 검증한다. 과거 health002/434개 PASS는 보존하며 새 invocation 완료를 대신하지 않는다. outside reviewer 가용성과 미실행 범위는 실제 probe로 기록한다.
- 새 리뷰 결과와 실제 unchanged binding을 기록한 뒤, 사용자 승인 범위의 최종 후보 commit과 locked packaging을 수행한다. dirty provenance guard는 우회하지 않는다. 실제 installer commit·SHA256·서명 상태, backend manifest/ASAR/frontend resources와 패키지 API→화면을 대조한다.
- 패키징 사전 확인: 준비한 Chromium cache와 PyInstaller spec/NSIS resources 포함 여부를 구분한다. 현재 SPOT은 HTTP transport를 사용하며 제품 소스에서 Playwright 실행 호출은 확인되지 않았다. browser cache 준비를 installer 포함/필수 런타임 PASS로 확대하지 않고, 필요성이 입증되지 않은 spec/resources 변경을 추가하지 않는다.
- Chrome 원격 창 제목 DESKTOP-Extrusion - Chrome은 사용자 “열어둠” 뒤 확인됐지만, 도구의 Windows URL 판별 제한으로 화면 캡처가 다시 중단됐다. 서버 내부 화면/상태·전달·설치·수집/CSV/설정 보존을 검증한 결과가 아니다. 로컬 후보 검증 후 가능한 서버 최종 전달/승인 적용/회수를 이어 수행하며 4c97d4a 복귀 기준을 적용 확인 전까지 유지한다.
- [x] 새 review→후보 검증 직접 승인과 기준 계획 두 사본 기록.
- [ ] 새 독립 review·현재 기능/화면 검증·unchanged start/end binding.
- [ ] clean 후보 commit·locked installer의 commit/SHA256/서명·실제 API→화면.
- [ ] 서버 최종 폴더 전달·승인 적용/수집·CSV·설정·실행 세대 증거 회수 및 다음 롤백 기준 갱신.

### 14.1 새 리뷰 preamble의 도구 설정 실패

- 새 사용자 승인은 저장됐으며 재승인 대상이 아니다. 새 skill session은1-1791528125-a001fdac/TEL_START1791528125다. core REVIEW_START/native PASS_START와 diff 검토는 아직 시작하지 않았다.
- 실제 auto_upgrade=true 설정에 따른 도구 갱신에서 source54efba6dd5a6dc7f04e62106b97079279ed53b41→20eb6202fa8ea83a882e7c0463b722cd8a31af1e가 fast-forward됐고 기존 bin/gstack-wtree 수정은 autostash로 복원됐다. 전후SHA25615ff37c642aef0346fe4c04195b5a2ac470bd150a0fbe36739cd8c6b3ce5bb5f가 동일하다.
- ./setup --refresh-registered는 실제 exit1이다. Codex 설치는1.91.67.0→1.91.68.0 updated이나, 다른 checkout의 기존 Claude1.67.1.0 설치는 skipped다. 그 기존 설치의 question-log/question-preference/auq-error-fallback/timeline-stop hook4개 TypeScript 파싱 실패가 보고됐다. CSO native helper 경고와 UI-S1 제품 결함은 구분한다. 전체 setup raw stream을 별도 파일로 보존하지 못했으며 실제 terminal session8572의 종료/summary를 근거로 기록했다.
- gstack-upgrade/SKILL.md Inline upgrade Step4의 “On SETUP_FAILED, STOP”에 따라 이번 invocation을 preamble 실패로 종료한다. 도구를 파괴적으로 reset하거나 다른 Claude checkout/보안·사용자 설정을 임의 변경하지 않았다. 다음 단계는 도구 prerequisite 복구 후 기존 승인의 새 리뷰/후보 검증을 이어가는 것이다.
- 현재 제품571개는 마지막 health002 source-after와 동일하고 검사 exit0, 기준 계획 두 사본도 동일하다. 새 frontend/health/browser 검증이나 최종 review 완료로 계산하지 않는다. evidence는 .tmp_ui_s1_verify/final-review-20261009-003/tool-setup-failure.json 및 tool fetch/pull/raw receipts다. 후보 commit/installer/서버 적용/기준 갱신은 미실행이며4c97d4a를 유지한다.

### 14.2 도구 설정 실패의 실제 경로 판정과 리뷰 재개

- ./setup --status는 exit0이며 Codex global1.91.68.0 current, router 파일과 section link24개가 정상이다. gstack-doctor는 exit1/hook-check 실패를 보존한다. browse bundle와4개 binary 실행 검사는 OK, outside Claude CLI는 not configured다. 이를 doctor 전체 PASS로 바꾸지 않는다.
- 실제 Bun1.3.11로 현재/기존 Claude source의 문제 hook4개씩 총8개를 실행하지 않고 번들링했다. 모두 success:true/logs[]/실제 dependency inputs 존재, probe exit0다. TypeScript 파싱 오류라는 기존 메시지만으로 제품·hook 소스 결함으로 단정하지 않는다.
- bin/gstack-hook-check:161–168의 Bun 출력 entry는 Windows native C:/...로 전달된다. 같은 파일의:206은 MSYS /c/... entry를 awk로 문자 그대로 대조하여 결과 없음으로 실패한다. 실제 argv probe에서 C:/...와 /c/...가 달라 rawLookupMatches:false임을 확인했다. hook 실행/설치·인증/보안 설정/툴 원문 변경은 없다. evidence: final-review-20261009-003/tool-readiness.json.
- 이전 preamble 실패 invocation은 종료한 그대로 보존하고, 기존 직접 승인에 따라 새 리뷰 invocation에서 실제 core/native 시작 token과 Codex 도구 실행을 검증한다. 원래 설정/doctor exit1은 별도 도구 제한으로 유지한다. 리뷰에 쓰는 해당 명령이 실패하면 미완료를 기록하며 token/coverage를 조작하지 않는다.


### 14.3 새 최종 review 완료와 후보 확정 단계 (2026-10-09T07:25:16.089Z)

- 직접 승인한 새 invocation에서 specialist 8개와 필수 in-host native adversarial을 완료했다. 현재 미해결 결함0개, completed:true/converged:true/cycles:0다. 원래 cycles3 INCOMPLETE 기록은 재작성하지 않는다. maintainability가 root Markdown34개도 전체 재독하여 이전 coverage gap을 닫았다.
- 실제 logger가 원래 core token78831db9-56fc-475b-ba3d-fc5294f203c9와 native token91a2ea40-ad0c-4423-97d4-85ef3b1f5ea4를 각각 한 번 소모했다. start/end wtree=41c8617703ac175659609b2bbc640126339a4083, state=verified; 실제 review-read status=CURRENT다. 이 proof는 아래 진행 문서 갱신 전의 검토 snapshot을 가리킨다. 문서 갱신 뒤 전체 tree도 같은 것처럼 주장하지 않는다. 제품571개 바이트는 유지한다.
- 이번 invocation에서 focused148+Node9, production build4577modules/Router contract, 합성 실제 App 상태·follower3경로·compact24개 및 native menu9개를 검증했다. 새 full npm run health는07:13:04.401Z~07:19:14.492Z exit0: dependency14/Electron94/frontend434+Node9/typecheck/lint/ruff/mypy9/backend880(223.890s, 기존skip1)/QA5다. 원본stdout162695bytes/SHA2566656701fa83aa14715ba2574a73031c4f27f5eaa5a15f37c2ceaa19304db3f6b, stderr20359bytes/SHA256a4139c11a8174345936fad99bc5a275bb8564ce9af11276dcd04e21d4cb38c1d를 모두 strict UTF-8로 읽었다. 현재 source-before/after와571개 동일, Q materialize pass/open[]다.
- 외부 Claude Code는 실제not_installed이며 adversarial/structured coverage를 unavailable로 각각 기록했다. security/red-team/native는 fixture-summary coverage이며 parent/testing이 변경 test body 전체를 읽었다. IMPECCABLE_NOT_AVAILABLE와 식별 정보 없는 legacy의 승인 fallback/cross-source 순서 미보장 한계는 유지한다. memo wrapper7줄 정리는 선택적 INFORMATIONAL advice이며 미적용/사용자Skip 아님이다.
- 단일 최종 리뷰/QA 보고서: [.tmp_ui_s1_verify/final-review-20261009-004/final-review.md](../../../.tmp_ui_s1_verify/final-review-20261009-004/final-review.md). 같은 폴더 core-finish-actual.json/native-finish-actual.json/input-audit.json/evidence.json/health/audit.json 및checkpoint002~006이 근거다. owned tab/context 종료, fixturePID131304는 실제 identity를 확인하고 Force 없이 중지/CIM 부재 확인했다.
- 승인된 후보 commit 준비를 진행한다. 이 항목 작성 시 아직 후보 commit/installer/실제 packaged API→UI/서버 적용은 미실행이다. 커밋 전에 아래 메타데이터 갱신만 추가됐는지/제품571개 동일인지/다른 기능PDCA 보존/diff check를 확인한다. dirty provenance guard는 우회하지 않는다. candidate hash와 패키지 원본 증거는 바탕화면SmartFactory/S1_PKG_20261009_R1/records에 기록하여 build 중 tree를 바꾸지 않는다.
- [x] 새 zero-edit 독립 review·현재 필수 로컬검증·unchanged binding.
- [ ] clean 후보 commit·locked installer commit/SHA256/서명·packaged API→UI.
- [ ] 서버 최종 폴더 전달·승인 적용/CSV/설정/실행 세대·회수·다음 롤백 기준 갱신. 적용 확인 전4c97d4a 유지.

### 14.4 후보 커밋과 패키징 환경 출처 검증

- 후보541d701d544eea6a8a4e4836047077eaf9cfaf30을 실제 커밋했다. 24개 승인 파일/제품571개 유지, clean Git 상태이며 push/merge는 수행하지 않았다. fresh review 뒤 추가한 변경은 진행 문서와 해당 feature PDCA 메타데이터다. candidate-commit-001은 상태 파서의 앞 공백 trim 문제로 stage 전에 중단된 기록이며, -002가 실제 커밋/clean 증거다.
- 첫 PyInstaller exit0/provenance commit 일치이나 Analysis-00.toc3482개에서 도구 cache의 DLL44개가 포함돼 출처 검사 FAIL이다. 산출물을 실행/승격하지 않고 보존한다. records/candidate-pyinstaller/audit.json을 최초 결과로 유지한다.
- 승인된 locked packaging의 실행 환경 확인을 위해 다음 build 자식에만 Python -I와 제한 PATH(locked venv/Python312/Windows/Git)를 적용하고 PYTHONPATH/PYTHONHOME을 제외한다. 부모/운영 설정·의존성 lock·spec·제품 코드 변경은 없다. 새 backend-dist-2/backend-work-2에 빌드하며 첫 산출물을 덮어쓰지 않는다. TOC 실제 source, provenance, bundle manifest와 frontend bytes 확인 후 Electron 패키징한다.
- 이 실행 기록은 기본 작업 폴더의 기준 계획에 먼저 저장한다. 후보 checkout의 계획 사본은 clean provenance 확보를 위해 빌드 중 변경하지 않으며 패키지 검증 뒤 문서만 동기화한다. candidate와 메타데이터 후속 commit을 구분한다. installer/패키지 실API→UI/운영 적용/롤백 갱신은 미완료다.


### 14.5 후보 installer와 실제 패키지 연결 검증 완료 (2026-10-09T07:59:38.857Z)

- 후보 build commit은541d701d544eea6a8a4e4836047077eaf9cfaf30, branch는codex/spot-comm-temperature-ui-s1-20261008이다. 진행 문서 후속 commit은 이 build commit과 구분하며 재빌드/서버 승격을 뜻하지 않는다. push/merge는 하지 않았다.
- locked Python -I/child 제한 PATH PyInstaller는 exit0, TOC3439개 실제 source 검사에서 ambient 파일0개다. 첫 ambient DLL44개 산출물은 제외·보존했다. Electron 첫 child PATH powershell.exe ENOENT도 실패 그대로 보존하고 새 output에 필수 WindowsPowerShell/Node PATH를 추가한 child-only 실행이 exit0다. lock/spec/제품/부모 환경 변경은 없다.
- installer는 바탕화면SmartFactory/S1_PKG_20261009_R1/packaging/electron-2/smart-factory-logger-v2 Setup 1.0.26.exe,163826264bytes,SHA256 08C061EE35A1A01788F05B00EE7395AA40774150C92C06726A92F3DF1BF75C3C,Authenticode NotSigned다. backend manifest1644개/C4AA5DE5B1B4889EE0B09B8450CB9B29392CFC4C327CF4272305B513A19CC6D3,ASAR runtime11개가 후보와 일치한다.
- installer를 실행하지 않고 archive를 안전한 새 경로에 추출했다. 전체1771개 파일이 실제 시험한win-unpacked와 길이/SHA256까지 일치하며 outer/embedded frontend50개도 production build와 같다. 7za의 trailing NSIS data 경고는 원문 보존했다. 설치 UI·설치 전환 PASS로 확대하지 않는다.
- 실제 packaged Electron44.3.0/frozen backend/후보commit의 /health→renderer를 own localhost SPOT/Mock PLC로 시험했다. 정상/under/over/timeout(SOURCE_ERROR)/복구/timeout(CACHED)/복구7전환 PASS, 실제health11응답/JS오류0/외부요청0이다. under/over는SPOT OK/온도개별상태, timeout은SPOT DOWN이다. Mock PLC2개 기준Comm2이며 timeout때만Comm3, 복구Comm2를 확인했다. 기존 Temperature/TTL/gate는 바꾸지 않았다.
- owned Electron/backend exit0/forced:false(1042.7ms), CIM에 stage소유 프로세스0개이며 실제candidate/rollback installer의 SHA와NotSigned를 재확인했다. 첫runtime의 health shape 기대 오류와2초지연 fixture 실패는 원문을 보존하고 shape수정/12초지연 및 유효이미지 fixture를 사용한003에서 PASS했다. 실제transport timeout/config 변경은 없다.
- 검증 후제품/시험/명령입력571개가 fresh review 및build 전과 동일하다. 증거는 [candidate-package-validation.md](C:/Users/user/Desktop/SmartFactory/S1_PKG_20261009_R1/records/candidate-final-validation-001/candidate-package-validation.md), 같은폴더 result.json/process-signature-audit.json과records/installer-payload-001/packaged-runtime-003에 있다. 외부review 미설치·legacy fallback·장비설정/정식운영QA 미검증은 그대로다.
- [x] 새 독립review·최종로컬health/build/browser.
- [x] clean후보commit·lockedinstaller commit/SHA/서명상태·실제packaged API→UI·installer payload일치.
- [ ] 서버최종폴더 전달·승인적용·단일실행세대/CSV/설정·회수·다음롤백기준갱신. 현재4c97d4a00d79ae0d3da70b2e82af227345e21040은 적용확인 전까지 유지한다.


### 14.6 서버 전달 묶음의 개발 PC·공유 사본 준비 (2026-10-09T08:02:57.420Z)

- 새S1_CAND_20261009_R1 묶음69개/330566480bytes를개발PC 바탕화면SmartFactory/S1_PKG_20261009_R1/delivery와Z:/SmartFactory/20261009/send에 준비했다. 전체공유사본 SHA256이개발원본과 일치하며manifest SHA256=286dd373d34adae7a203ab49d693842ee4eaada8fb84a11efd284fd3af16ffd8다. 해당 묶음의계획은14.5시점사본이며이후진행기록과구분한다. 공유전달은서버최종복사가아니다.
- 후보541d/복귀4c97d4a installer, local검증원문, baseline/경로정책, 기존4c97d4a read-only reader를포함했다. 기존reader/launcher/고정해시 바이트는 바꾸지 않았고 후보541d의설치후검증으로 사용하지 않는다. 새로운적용코드·종료·설치·운영설정변경은 없다.
- 서버실제 절대경로/파일존재·로컬해시, 현재실행세대/CSV/설정, 후보승인적용·결과회수·다음롤백기준은 아직미확인이다. Chrome원격은computer-use허용경로만사용하며URL확인실패/정책중단이면우회하지않고실제완료위치와제한을보고한다.
- 로컬검증문서4개만후속metadata commit에저장한다. installer build commit541d와구분하고제품571개불변을커밋전후확인한다.


### 14.7 서버 접근 제한과 현재 보고서 상태 정합성 (2026-10-09T08:08:20.793Z)

- 이전 완료 턴의 Chrome get_window_state는 현재브라우저URL을확신할수없다는자동정책검사로중단됐다. 서버로컬복사/실행/조회는 수행하지 못했다. 이번 재개에서 후보metadataHEAD16d5e8d·clean상태, 준비전달영수증과 미완료운영항목을 실제 읽어 확인했다. 반복제품검증/재빌드/기존묶음 변경은 하지 않는다.
- 계획·분석·보고서의상단에남은cycles3/미커밋/installer미생성 상태를14.3–14.6의현재증거로바로잡는다. 원래실패/구review/고정manifest/전달묶음의당시사본은보존한다. 문서만수정하며buildcommit541d/제품571개를유지한다.
- 사용자에게주소표시줄이보이는일반Chrome탭에서대상원격서버연결을요청했다. 연결상태변화가확인되기전에는URL검사를우회하거나다른원격실행경로를쓰지않는다. 서버파일복사/현재세대·CSV·설정결합이후승인적용/결과회수/다음rollback기준갱신까지필요하다.


### 14.8 원격 접속 방식 추정 정정과 재시도 (2026-10-09T08:27:03.736Z)

- 사용자가 이미 일반 Chrome 탭으로 DESKTOP-Extrusion에 접속 중이라고 직접 확인했다. 별도창/주소표시줄 부재가 원인이라는 이전 추정은 근거가 없으며 접속 방식 변경 요청을 철회한다. 실제 확인된 오류는 computer-use가 현재 URL을 확신할 수 없어 화면 조회를 거부했다는 것이다. 정확한 실패 원인은 제공 문서/공개 API에서 확인되지 않았다. 이전 감사 기록은 당시 사실/추정으로 보존한다.
- 사용자 “그럼 다시 진행해라”에 따라 같은 연결에서 새 반환 창을 선택하고, 공식 guidance의 get_window→activate_window→get_window_state 순서로 재시도한다. URL 검사/보안 설정을 우회하지 않는다. 실패하면 해당 도구의 턴 종료 지시를 따르고 실제 미완료 항목을 보고한다.
- 제품/installer/고정 전달 묶음은 바꾸지 않는다. 후보 build541d와 현재4c97d4a 복귀 기준 유지. 서버 최종 폴더 복사·현재 세대/CSV/설정·승인 후보 적용·회수·기준 갱신은 여전히 남았다.

### 14.9 브라우저 플러그인 연결 확인과 로그인 대기

- 사용자가 computer-use 또는 Browser 플러그인을 직접 지정했다. 이전 Computer Use의 Windows URL 판별 실패를 두 도구 모두의 실패로 확대하지 않고, 이번 턴에는 Browser의 공식 사용 지침과 지원 API로 별도 연결을 확인했다. 실제 Codex In-app Browser 연결과 탭 조회는 성공했다. 기존 Chrome 연결 방식 변경 요청은 철회한 상태다.
- 사용자 제공 http://remotedesktop.google.com/access/session/8dac2c49-886b-3a5c-c6d6-39e1bcc173f0?hl=ko를 새 탭에서 열었다. HTTPS Google 계정 로그인 화면으로 이동했고 계정이 로그아웃됨으로 표시됐다. 링크 열기와 화면 조회 성공이며 서버 세션 접속/화면 입력 성공은 아직 검증하지 못했다. 실제 Chrome 세션의 로그인 상태를 변경하거나 검사한 결과가 아니다.
- 해당 브라우저의 지원 인증 handoff capability는 제공되지 않았다. 로그인 화면을 사용자에게 표시하고 탭을 다음 턴에 유지하도록 설정했다. control-in-app-browser SKILL.md의 인증 차단 시 지정 브라우저에서 로그인 요청 규정에 따라, 사용자가 Codex 브라우저 패널에서 직접 로그인한 뒤 같은 탭에서 접속/화면/입력을 확인한다. 비밀번호/쿠키/프로필/저장된 인증 정보를 읽거나 정책 검사를 우회하지 않는다.
- 증거: C:/Users/user/Desktop/SmartFactory/S1_PKG_20261009_R1/records/server-access-pending-001/browser-access-audit-20261009.json 및 browser-login-required-20261009.png. 제품/installer/고정 전송 묶음은 변경하지 않았고 build541d와 운영/복귀4c97d4a를 유지한다. 서버 최종 폴더 복사·현재 실행 세대/CSV/설정·승인 후보 적용·회수·기준 갱신은 미완료다.
