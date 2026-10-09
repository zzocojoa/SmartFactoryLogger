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
> 실행 상태: 승인된 UI-S1 개선·서버 적용·운영/다음 롤백 등록은14.27–14.28절에서 완료했다. 후속 로드맵의 사용자 "진행 승인"에 따라 제품 변경 없이 원격 PR·보호된 master 병합·동일 운영 설치본과 소스 이력 연결을 진행한다(15절). 541d701d/08C 운영본과4c97d4a/D453 이전본을 유지하며 최초 timeout/223ms·과거drop15·정식QA/서명/config/comparator/전수검증 한계를 PASS로 바꾸지 않는다.
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
| **Check** | 설계와 최종 diff·필수 회귀·후보 및 실제 적용 검증을 대조한다. | frontend434+Node9/typecheck/lint/build·전체health exit0·최종독립review·packaged7상태, 실제설치54pins/15API/수집·CSV/config·UI/65파일/128조건 검토 완료(14.27). |
| **Act** | 불일치나 실패를 수정하고 영향받은 검증을 재실행한다. 스킬 기준 최대 5회 반복 후에도 남은 문제가 있으면 미완료로 기록한다. | A/I2-A 승인 보완과 응답 지연 조사·최종 회귀 완료. 과거11절 실패와 원인 미확정 항목은 보존. R1 읽기 CSV 경로 오류를 별도R2로 보완·검증했고 현재 저장 진행 확인. 기존 이미지 dropped15 원인 미확정 유지. |
| **Report** | build commit·installer hash·검증exit·미실행/한계를 기록하고 승인 적용 후 기준을 갱신한다. | 541d build/08C installer의 실제 적용 확인과 내부 운영 승격·다음rollback등록 완료. 이전4c/D453·실패원문·정식QA false 보존. 최종 보고/근거는14.28 및 운영기준 문서. |

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

- [x] 현재 후보의 필수 UI-S1 계약과 모든 승인 보완 회귀시험 충족. 승인 수정과 최종434+Node9 및 실제 packaged 상태7단계 PASS; 과거 실패는11–14절에 보존한다.
- [x] 최종 frontend 검사/build와 기본 health exit0 확인. 전체 최종 health의 시각·원문·exit와 실제 대상은14.3–14.6절에 기록한다.
- [x] 상세 메뉴·순서 계약·승인 후속 결함 보완 및 새 독립 review 완료. 현재 review 미해결0/cycles0/binding verified이며 외부 Claude 미설치 범위는 별도로 유지한다.
- [x] 실제 변경과 검증 결과를 이 계획의 목표·범위·완료 조건에 대조하고 진행 상태를 갱신한다.
- [x] 합성 UI 시험과 실제 설치본·실장비 확인 결과를 구분해 보고한다.
- [x] 운영 적용까지 수행한 경우에만 후보 검증·적용 확인·롤백 기준 갱신을 완료로 기록한다.

### 4.4 최초 검증 결과 기록 (당시 상태 보존; 최신 결과는14.28절)

| 검증 항목 / 명령 | 대상 commit·설치본 | 결과 / exit code | 증거 위치 | 미검증·남은 항목 |
|---|---|---|---|---|
| 계획 파일명·필수 항목·저장 내용 확인 | 이 계획 파일 | 원본 브랜치명·필수 항목 확인, 두 저장 위치 동일 | 이 문서의 진행 기록 | 이전 준비 계획 hash 보존 |
| frontend test / typecheck / lint / build | base 35959c4 + 미커밋 frontend; correction/source hash manifest | 390개 + node 9개 PASS, 각 exit 0 | worktree .tmp_ui_s1_verify/correction 및 구현 보고서 6절 | installer·실장비 미검증 |
| npm run health | 위 worktree; 추가 frontend 변경은 최종 검사 재실행 | exit 1: QA Get-FileHash 로딩 실패; backend 880개(1 skip), 이전 단계 통과 | health.log, qa-explicit-utility.json | Utility import 후 동일 QA 5개 각 exit 0; 기본 명령 오류 미해결 |
| 후보 패키지 / 서버 적용 확인 | 후보 생성 후 기록 | 미실행 | 미생성 | 운영 적용 미시작 |

## 5. 운영 적용과 위험 관리

- 이번 개선 시작 시 운영본 `4c97d4a00d79ae0d3da70b2e82af227345e21040`을 교체 전 복귀본으로 보존했다. 적용 확인 후 현재 운영·다음 개선 기준은541d/08C이며4c/D453은 이전본으로 보존한다(14.28).
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

### 14.10 로그인 완료 후 서버 최종 복사와 읽기 준비

- 사용자의 로그인 완료 응답 후 같은 Codex Browser 탭에서 DESKTOP-Extrusion 연결됨과 운영 대시보드를 확인했다. 탐색기 열기/최대화/경로 이동 및 서버 자체 복사 메뉴로 실제 마우스·키보드·텍스트 입력이 전달됨을 확인했다. 브라우저 Ctrl+V는 가상 클립보드 데이터 없음으로 실행되지 않아, 서버 탐색기 복사/붙여넣기 메뉴를 사용했다. 이는 정책 거부를 우회한 실행이 아니다. 별도 인증/보안/클립보드 공유 설정은 변경하지 않았다. 사용자가 지정했던 화면 입력 기능을 이 세션에서도 켰다.
- 공유 S1_CAND_20261009_R1를 서버 실제 바탕화면 SmartFactory 아래 새 C:/Users/user/Desktop/SmartFactory/S1_CAND_20261009_R1에 복사했다. 기존 동명 항목/덮어쓰기 없이 복사가 끝났고 폴더 속성에서 파일69개/폴더12개와 서버 로컬 위치를 확인했다. 화면/파일 존재 확인이며 서버 로컬 SHA256/reparse 검증 PASS가 아니다. 14.6 전달 묶음의 고정 바이트/manifest는 재작성하지 않는다.
- 승인된 서버 검증 단계 안에서 별도 S1_READ_20261009_R1 읽기 전용 묶음을 준비한다. 고정 원본 manifest와 서버 로컬69개 파일 SHA256, Desktop 경계·reparse·표준 사용자/대상 host를 확인한 뒤 기존 해시 고정4c97d4a reader를 변경 없이 실행해 현재 PID/시작시각/listener/config/3회 API 조회를 기록한다. 새 결과만 생성하고 운영 시작/정지/설치·장비 직접 요청·설정/CSV 수정·실패 초기화는 하지 않는다. 새 도우미의 PS5.1 파싱·경로/해시 거부·실제 개발 원본 해시·기존 reader self-test를 검증한다.
- Computer Use guidance의 필수 규칙은 Windows 터미널 명령의 UI 직접/간접 실행을 금지한다. Browser에서 Windows 탐색기를 사용해 이 규칙을 우회해 cmd/PowerShell을 실행하지 않는다. Codex가 읽기 묶음도 서버 최종 폴더까지 복사하고 파일/경로를 확인한 뒤, 사용자에게 정확한 읽기 launcher의 일반 더블클릭 한 단계만 요청한다. 이후 Codex가 결과 회수/검토를 담당한다. 적용/설치 승인 범위를 다시 묻는 요청이 아니다.
- 현재 서버 읽기 및 로컬 파일 SHA256 확인 전에는 신규 적용 도우미의 실행 세대/설정/CSV 기준을 확정하거나 후보를 설치하지 않는다. 운영/복귀4c97d4a 및 후보 build541d 유지, 서버 적용/회수/다음 기준 갱신은 미완료다.

### 14.11 서버 읽기 묶음 최종 전달·검증과 사용자 실행 대기

- 개발 원본 고정69개/330566480bytes의 전체 SHA256/두installer NotSigned를 새 helper self-test14개로 확인했다(exit0). 기존4c reader self-test12개도exit0다. 실제 READ_SERVER.cmd의 고정helper bootstrap→자식 실행을 개발PC에서 시험해 server-host HOLD/exit1을 정상적으로 확인했으며 운영 조회/API/결과 폴더 생성은0회다. 파싱·최종launcher pin/실제3개 공유사본 SHA256이 정상이며 제품 소스/기존helper/installer/고정candidate manifest를 바꾸지 않았다.
- 새 read-server.ps1 SHA256=91591E9B608BC8D4D92B4D0B8B8F0E1C67AB8E8FC4EA93051EDF9CF5D8A3F518, READ_SERVER.cmd= B07D24EB08588C4AD842EAE570A2A8785C858FD40D881E1C86E2A1A746B3DE17다. 처음 helper 검증의 raw DirectoryInfo/PSIsContainer 문제는 .NET type 판정으로 수정한 후 최종 검증했다. validation001의 inherited PSModulePath/WinPS5 autoload 실패와 CP949 원문은 보존했다. validation002는 test 자식에서만 PSModulePath를 제거하며 부모/배포helper 환경은 바꾸지 않았다. 각 실제 exit를 먼저 저장하고 CMD pause의 CP949까지 전체원문을 다시 읽어 완료했으며 성공 시험을 다시 실행하지 않았다.
- 3개 파일을 Z:/SmartFactory/20261009/send/S1_READ_20261009_R1에서 서버 C:/Users/user/Desktop/SmartFactory/S1_READ_20261009_R1에 최종 복사했다. 일반 탐색기에서 절대경로/3개파일/READ_SERVER.cmd의1126bytes를 확인하고 launcher를 선택한 상태로 남겼다. 복사 후 목록 정렬이 늦게 반영되어 기존hash 텍스트 문서가 의도치 않게 열렸고, 입력/편집 없이 기존Notepad 탭을 보존해 최소화했다. 이후 정확한 폴더 절대경로로 이동했다. 터미널/launcher/installer를 UI 자동 실행하지 않았다.
- 증거: C:/Users/user/Desktop/SmartFactory/S1_READ_PREP_20261009_R1/validation-002/result.json과전체raw/exit, development-copy.json/server-copy.json. 공유records/S1_READ_20261009_R1-server-copy.json은 actual server-local path와 화면파일확인/해시확인 범위를 구분한다. candidate69개/reader3개는 서버최종복사·화면확인 완료, 서버로컬 SHA256/OS host·현재세대/config/API3samples는 사용자읽기 실행 대기다. 과거 개발전달receipt의serverFinalCopied:false는 당시기록으로 보존한다.
- Windows terminal 명령 UI 직접/간접 실행 금지 규정 때문에 사용자에게 서버 READ_SERVER.cmd 일반더블클릭1회와 PRE READ EXIT 결과를 요청했다. 필요한 사본/해시고정/로컬시험/정확한서버폴더 준비는 완료했으며 승인범위 재선택 요청이 아니다. 해당완료 전에는 반복자동실행/정지/설치를 하지 않는다. 회수용 Z:/SmartFactory/20261009/return/S1_PRE_READ_20261009_R1를 새로 준비했으며 아직결과를회수한상태가 아니다.
- [x] Browser로그인/원격화면·입력, candidate69개와읽기3개 서버최종복사 및 실제경로·파일확인.
- [x] 읽기helper 최종 PS5.1/hash·경로guard·기존reader self-test·실launcher 환경거부·공유사본 검증.
- [ ] 사용자읽기실행→서버로컬 SHA256·현재PID/owner/listener/세대/config/API→Codex결과회수/수집검토.
- [ ] 현재설정/CSV·정상종료세대에 결합한 승인후보적용/실API→화면·수집·CSV·설정보존/결과회수·다음rollback등록. 기록된운영/복귀4c97d4a를 유지하며 전체목표는 미완료다.

### 14.12 사용자 읽기 실행 완료·결과 회수와 현재 저장 상태 검토

- 사용자 “실행 완료” 후 서버 콘솔 PRE READ EXIT0과 결과 폴더 C:/Users/user/Desktop/SmartFactory/S1_READ_20261009_R1/r-20261009-185450-33c511을 확인했다. 콘솔을 자동 조작하지 않고 탐색기의 서버 자체 Copy/Paste로 Z:/SmartFactory/20261009/return/S1_PRE_READ_20261009_R1에 결과 전체를 복사했다. 개발 PC의 S1_READ_PREP_20261009_R1/server-results-001에 회수하고38파일/1235311bytes/manifest37entries 전체를 해시 검증했다(exit0). 콘솔 화면과 회수 manifest SHA256=0C4DECE3EA448452B8FFDCA5BBCC5653EC3AB306092CEFECF8E4364E851AB4CC가 일치한다. 최초 원본 JPEG와 확대 판독 사본을 보존한다.
- 서버 실제 host DESKTOP-CIIT7LK/승인 SID, 최종 전달69파일/330566480bytes의 고정 manifest·개별 SHA256·두installer NotSigned를 확인했다. 운영 설치 핵심4파일은4c97d4a와 일치한다. UI9580/backend9036 및 모든5프로세스의 PID/시작ticks/부모/owner/session과8000 listener가 읽기 전후 동일하다. config SHA256=6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E도 동일하다. 이는 설치 완료가 아닌 현재 운영본의 읽기 검증이다.
- 실제18 API 원문 모두200/ok, raw collector18hash와 원본 reader 사본30파일 해시를 대조했다. 새 자체 검토84조건 PASS/0fail/exit0, server-read-review-001.json에 각 조건을 기록했다. 같은 SPOT/logger 세대에서 poll107027→107061(+34), API rows463167→463299(+132), 동일 current_v2_csv_file_name=Factory_Integrated_Log_v2_20261009_000000.csv다. API counter 증가를 실제 CSV 바이트 연속성/설치 보존 PASS로 바꾸지 않는다. HTTP 오류0, 과거 LS No Body1건 및 drift1은 유지됐으며 storage 오류 증가0이다.
- 새 우려: image written93439/fact_rows4091224/fact SHA256은3회 조회에서 동일하고 queue32→47→63/enqueued93472→93503으로 증가했다. failure/drop은0이나 저장 완료 진행을 확인하지 못했다. 실제 writer는 write_capture 및 retention 처리가 반환된 뒤 완료 counter를 올리는 로직이다. retention 지연 등은 가능한 설명일 뿐 원인이 확정된 것은 아니다. 정상 종료·설치 전에 현재 이미지 진행과 실제 CSV 파일을 추가 읽기로 확인한다. 제품 로직/장비 설정/종료 정책의 수정 범위는 확대하지 않는다.
- 다음 준비는 승인된 서버 적용 전 읽기 단계의 별도 짧은 S1_READY 묶음이다. 현재4c 세대/핵심 파일/설정 pin과 참고 자료를 동봉하고,3회 새 health·spot/config·stats·data 조회, 현재 단일 V2 CSV의 제한된 prefix/tail 및 system.log tail을 읽기만 하여 저장 진행·근거를 회수한다. 운영 데이터 전체 복사/새 대형 백업/재귀 이미지 탐색/정지·설치·설정 변경/장비 직접 요청은 하지 않는다. 새 helper를 PS5.1과 경계·상한·환경 거부 시험 후 공유→서버 최종 폴더까지 전달한다. 이미지가 회복돼도 실제 정상 종료와 후보 설치 후 적용 확인을 별도로 수행한다.
- [x] 사용자 읽기 실행/서버 로컬 SHA256/현재 세대/config/API 근거와 결과 회수 검토.
- [ ] 현재 이미지 저장 진행 추가 확인·실제 CSV 바이트/수집 확인.
- [ ] 정상 종료·승인 후보 적용·실API→화면·CSV/설정 보존·결과 회수·다음rollback등록. 운영/복귀4c97d4a 유지, 전체 목표 미완료.

### 14.13 이미지 진행·CSV 추가 읽기 묶음 준비와 서버 최종 전달

- 새 별도 C:/Users/user/Desktop/SmartFactory/S1_READY_PREP_20261009_R1/S1_READY_20261009_R1의4파일을 작성했다. 기존 candidate/read/installer/서버 결과의 바이트는 변경하지 않는다. reference.json은14.12 실제 세대·critical4파일·설정·SPOT/logger ID·현재 CSV 이름과 원문 manifest 해시에 결합돼 있다. 이전 제품·금형을 강제하지 않으며 설정 내용은 복사하지 않는다.
- read-readiness.ps1 SHA256=BC4C1F22E50193DA8157F97428423C74B53644B3F3CDCFB59DB5D12D16A6B0BE, reference SHA256=3DC041DECC7EF00ADC93B219FED641282031D0CB146C9BE55966B78974842AEA, READ_READINESS.cmd SHA256=4516CEA442FD9C6BA87E420012B0AEFB0E4B927BA7DFAD5381B69E1FCF68BF06이다. launcher는 잠근 helper 바이트의 SHA256을 확인한 뒤 동일 자식을 실행하고 결과 exit를 전파한다. 파일명·세대 변경은 HOLD, 새 결과 폴더만 사용한다.
- native WinPS5.1 self-test19개 exit0(validation001), 실제 파일 prefix/tail6개·소스 보존·충돌 거부·junction 부모 거부·AST오류0 exit0(validation002)다. 실제 CMD launcher의 개발 host guard는 기대 exit1/READY_HOLD:server-host이며 정상 거부 PASS다. raw stdout/stderr와 exit를 먼저 저장하고 모두 읽었다. 시험 자식만 PSModulePath를 제거했고 부모/배포 환경은 바꾸지 않았다. 새 제품/서버 시험으로 계산하지 않는다.
- Z:/SmartFactory/20261009/send/S1_READY_20261009_R1의4파일을 전체 원본과 SHA256 비교했다. 서버 탐색기 자체 Copy/Paste로 C:/Users/user/Desktop/SmartFactory/S1_READY_20261009_R1에 최종 복사했다. 새 폴더와4파일/절대경로, launcher1143bytes를 속성으로 확인했다. 화면 파일·경로 확인과 서버 로컬 SHA256 확인을 구분하며 후자는 실제 launcher 실행 때 helper/reference pin으로 확인한다. 공유 목록은 F5 갱신 후 새 폴더를 선택했고 자동 launcher/terminal 실행은 하지 않았다.
- server-copy.json 및 서버 절대경로/속성/선택 화면3장을 S1_READY_PREP_20261009_R1에 보존한다. 공유records에도 새 전달 기록을 남긴다. 회수용 Z:/SmartFactory/20261009/return/S1_READY_READ_20261009_R1를 새로 준비했다. 사용자가 Windows UI 실행을 해야 하는 정확한 규정과 한 단계 경로를 안내하고 READY READ EXIT 결과를 요청했다. 같은 승인 범위의 재승인 요청이 아니다.
- [x] 추가 읽기 helper/고정 참고 자료/PS5.1·실파일 검사·공유 SHA256·서버 최종 전달 및 화면 확인.
- [ ] 사용자 추가 읽기 실행→Codex 전체 결과 회수/해시·이미지 저장 진행·현재 CSV 바이트 검토.
- [ ] 세대에 결합한 정상 종료와 승인 후보 설치·시작·실화면/API·CSV/설정 보존·회수·다음rollback등록. 전체 목표 미완료,4c97d4a 복귀 기준 유지.

### 14.14 후보 설치 후 검증 파일 기준 준비

- 앞선 턴은 실제 PRE READ 결과 회수/84조건 검토/추가 읽기 helper25조건 검사/서버 최종 전달로 진행했다. 이번 재개 시 서버 탐색기 F5에서 추가 읽기 폴더는4파일만 있고 새 r-결과 없음, 공유 회수 폴더도 비어 있음을 확인했다. 사용자 실행 요청은 유지하며 반복 요청/자동 terminal 실행은 하지 않는다.
- 대기와 독립적으로 승인된 후보 설치 후 검증의 고정 입력을 준비한다. 기존 reader의4c 전용 commit/critical hash는 보존하고 새 후보541d의 실제 installer payload 검증 기록과 win-unpacked에서 핵심4파일 및 제공 frontend50파일을 대조한 별도 JSON 기준을 만든다. 실제 후보파일/health commit 식별과 설정 보존 규칙을 구분한다. 기준 파일을 만드는 것이 설치·실서버 검증 PASS가 아니다.
- 완료 조건: 실제1771 payload 기록에서 선택한54파일의 크기/SHA256 대조, 후보 build_provenance full commit 확인, 경계·중복·필수파일·최종 서버 경로240자 예산 및 불일치 거부 검사, 외부 해시 기록. 아직 설치되지 않은 후보의 PID/서비스 ID/CSV 이름을 추정하여 고정하지 않는다. 실제 정상 종료/설치와 적용 후 세대·CSV/설정 확인은 추가 읽기 검토 이후 단계다.
- 별도 C:/Users/user/Desktop/SmartFactory/S1_POST_PREP_20261009_R1/candidate-installed-pins.json을 생성했다(11253bytes/SHA256=5FC82E1BA0353FACE9AB2A85E18019F6036EB15D9D332811307CD6DF4C99502D). prepare-post-install-pins.py는 실제 win-unpacked의 핵심4+frontend50파일을1771 payload 원문과 바이트/해시 대조하고 실제 build_provenance의541d full commit을 확인했다(exit0). 구commit/잘못된hash/중복/경로탈출/frontend필수파일누락5종 거부 확인; 최종 서버 선택파일 최대126자다. 결과는 result.json에 보존한다. 전수 설치파일 무결성이나 실서버 PASS가 아닌 선택54파일의 개발 원본 검증이다. 기존 app.asar와 Electron EXE는4c와 같을 수 있으므로 이 두 파일만으로 새 frontend/build를 식별하지 않는다.
- 추가 읽기 결과가 없는 현재 상태에서는 정상 종료·설치·새 PID/서비스/설정/CSV 보존 기준을 확정하지 않는다. 다음 진행은14.13의 사용자 실행 결과 회수·이미지/CSV 검토다. 현재 명령 프로세스가 실행 중이라는 근거가 없으므로 이 대기를 live process verified wait로 분류하지 않는다. 같은 실행 입력 필요 조건이 재개 후2번째 턴에 이어졌고, 이번 턴에는 별도 후보 검증 기준 준비를 실제 진행했다. 아직blocked로 바꾸지 않는다.

### 14.15 추가 읽기 실행 입력 필요 조건 재검증과 blocked 감사

- 재개 후3번째 목표 턴에 같은 Browser 탭을 조회하고 서버 탐색기 F5를 다시 수행했다. C:/Users/user/Desktop/SmartFactory/S1_READY_20261009_R1는4파일뿐이며 새 r-결과 폴더를 확인하지 못했다. 공유 Z:/SmartFactory/20261009/return/S1_READY_READ_20261009_R1도 실제 자식0개다. 실행 중인 도우미 process/session handle은 확인되지 않았으며, 원격 Browser 연결 자체를 도우미의 live verified wait로 취급하지 않는다. 실행했지만 초기 guard에서 실패했을 가능성도 결과 없이 배제하지 않는다.
- 1번째 턴은 최초 PRE READ 결과 회수·84조건 검토 및 추가 READY helper25조건 검증·최종 전달로 진행했다. 2번째 턴은 실제 후보54파일의 설치 후 기준 생성·5종 거부 검증으로 진행했다. 두 턴 모두 추가 READY 실행 결과가 필요했고, 이번3번째 확인에서도 동일하다. 옛 Computer Use URL 실패나 이미 완료된 최초 READ 대기 기록을 이 새3턴 감사에 합산하지 않는다.
- 적용 전 저장 진행/CSV 증거가 없어 현재 세대 정상 종료·설치를 확정할 수 없고, 해당 실행을 Windows UI로 자동화하는 것은 Computer Use의 필수 guidance 금지 사항이다. 동일 승인/실행 요청을 다시 묻거나 다른 자동 실행 경로로 우회하지 않는다. 독립적으로 필요한 후보 파일 기준 준비는 완료했다. 의미 있는 다음 작업은 사용자 실행 결과 또는 외부 상태 변경에 의존하므로blocked 기준을 충족한다. 목표를complete나paused로 바꾸지 않고blocked 상태 갱신을 요청한다.
- 감사 원문과 현재 화면은 S1_READY_PREP_20261009_R1/read-execution-blocked-audit-002.json 및 .jpg에 보존한다. 재개 조건: 기존 서버 최종 폴더의 READ_READINESS.cmd를 일반 실행한 READY READ EXIT 결과/콘솔 또는 새 r-결과 폴더 확인. HOLD/오류이면 자동 재실행하지 않고 원문을 회수해 조사한다. 결과가 확인되면 전체 manifest/이미지 진행·CSV 검토부터 이어가며4c97d4a 복귀 기준과 기존 증거를 보존한다.

### 14.16 추가 읽기 HOLD 회수와 실제 CSV 경로 보완

- 사용자 READY READ EXIT0 응답으로 재개했다. 실제 서버 콘솔은 EXIT1/READY READ HOLD이며 CSV 기본 경로 logs/data의 현재 파일을 찾지 못했다. 원문 result.json도 sampling/ItemNotFoundException을 기록한다. 결과 r-20261009-195655-7675d8 전체10파일/712843bytes를 서버에서 공유 return/S1_READY_READ_20261009_R1로 복사하고 개발 server-results-001로 회수했다. manifest9항목/개별 SHA256 및 콘솔 manifest B942C83A035D786E436B2DEDE4DB76263494E954F3A810C65C98B7E3B29F2AAA가 일치한다(exit0). 보고된0과 관측1의 충돌을 보존하며 실패를 PASS로 바꾸지 않는다.
- 운영4c 설치 핵심4파일/기존5프로세스 세대/config-before hash는 유지됐다. 1회4API HTTP200, 같은 SPOT/logger 세대 및 수집 증가를 확인했다. CSV window/후속2sample/runtime-after/config-after는 생성되지 않아 읽기 완료로 판정하지 않는다. 이미지 written93823/enqueued93823/queue0으로 이전 대기열이 처리됐지만 dropped15가 발생했다. 최신 이미지 시각은19:01경으로 추가 연속성/누락 원인과 actual CSV 바이트 검토는 미완료다. 원인/설치 보존 PASS로 추정하지 않는다.
- 서버 일반 탐색기에서 실제 C:/Users/user/AppData/Roaming/SmartFactoryLogger/logs/test_data 절대경로와 동일 current V2 CSV의 비어 있지 않은 파일 속성을 확인했다. 목록의 지연된0KB 표시를 데이터 없음으로 오판하지 않았다. 기본 logs/data 하드코딩은 도우미의 경로 확인 오류이며 운영 데이터/설정을 이동·수정하지 않는다.
- 승인된 적용 전 읽기 단계 안에서 별도 S1_READY_20261009_R2를 준비한다. 실제 확인한 csv_root를 새 reference.json에 원본 HOLD manifest/경로 화면과 함께 결합하고, root와 health CSV basename이 모두 일치해야 읽는다. CSV 경로 거부 회귀/PS5.1 파싱·self-test/실제 prefix-tail·소스 보존·충돌·junction 및 launcher host 거부를 검사한다. 기존R1/helper/reference/installer/고정candidate는 재작성하지 않는다. 서버 최종 복사·파일/경로 확인 이후에만 새 launcher의 사용자 일반 실행을 요청한다. 제품 코드·장비 직접 요청·새 종료 정책·범위 밖 기능 변경은 없다.
- [x] R1 HOLD 전체 결과 회수/콘솔·manifest·개별 해시 검증 및 실제 CSV 경로 화면 확인.
- [x] R2 실제 CSV 경로 결합/새 해시·읽기 회귀 검증·서버 최종 전달.
- [ ] R2 사용자 실행→해시·이미지/CSV/세대·설정 검토→정상 종료·후보 적용·적용 확인·회수·다음 기준 갱신. 전체 목표 미완료, 운영/복귀4c97d4a 유지.

- 새R2 helper SHA256=894DF2BF021027BF381412227BD8016B4FD04B03BDAD73AF4B357A11EF5E57DA(14290bytes), reference=27D8BDE6CA8EDDA1EC11184336112D4B7BCEA3EBC3624A82FB99D35DB230E70A(3803bytes), launcher=464FAB72510E0D4504E48F8BA3836D43A0F0CE0DB6309D883FAA3FA4A68AD521(1143bytes)다. 기존 hash 고정R1을 읽어 별도 파일을 생성했고 기존기준/후보를 변경하지 않았다. default logs/data 거부와 실제root/current CSV 결합, 잘못된 이름 거부를 추가했다.
- C:/Users/user/Desktop/SmartFactory/S1_READY_PREP_20261009_R2/run-validation.ps1 실제exit0: nativePS5.1 self-test23/실파일6 exit0, 실제launcher 개발host 거부는 기대exit1/READY_HOLD:server-host다. 전체 raw/exit를 먼저 기록하고 모두 읽었으며 validation-001/result.json에3case PASS가 있다. CMD CP949와 자식전용PSModulePath 제거를 기록했다. R1 부분 결과 검토12조건 일치는 완료 QA가 아니다. 프로세스 목록은 순서만 달라 PID별 전체 필드/리스너 일치를 확인했다.
- 개발4파일→Z:/SmartFactory/20261009/send/S1_READY_20261009_R2 전체 SHA256 일치를 확인했다(exit0). 서버 탐색기 자체Copy/Paste로 실제 C:/Users/user/Desktop/SmartFactory/S1_READY_20261009_R2에 새 폴더를 최종 복사했다. 절대경로/4파일/launcher1143bytes와 선택 상태를 화면·속성으로 확인했다. 덮어쓰기/자동terminal 실행은 없다. server-copy.json과3화면, 공유records 영수증에 실제경로와 확인 범위를 구분했다. 서버 로컬 helper/reference SHA256은 사용자 실행 시 pin 검증 대기이며 화면 확인을 SHA256 PASS로 바꾸지 않는다.
- 회수용 Z:/SmartFactory/20261009/return/S1_READY_READ_20261009_R2를 준비했다. 기존R1 HOLD는 재실행하지 않는다. Windows UI로 terminal 명령을 직접·간접 실행하지 말라는 Computer Use 필수 guidance 때문에, 원인 보완·검증·서버 전달까지 완료한 새R2의 일반 사용자 실행 결과가 다음 필요 입력이다. 적용 승인 범위를 다시 묻지 않는다. 이전blocked 조건은 R1 결과 회수로 해소됐고, 새 보완본 결과 필요 조건의 첫 턴이며 현재 목표는active/전체 미완료다.

### 14.17 R2 실행 결과 대기 재검증과 blocked 감사

- R1 결과 회수로 이전 blocker를 해소한 재개 첫 턴은 실제CSV 경로 확인과R2 보완·29검사/host 거부·공유해시·서버 최종 복사로 진행했다. 이후 두 재개 턴의 fresh Browser 화면/F5에서도 C:/Users/user/Desktop/SmartFactory/S1_READY_20261009_R2는 기존4파일만 있고 새r-결과 없음, 공유 return/S1_READY_READ_20261009_R2도 자식0개다. 최근 두 턴은no progress이며 확인된live 실행 handle이 없어verified wait로 분류하지 않는다. 원격 연결 자체를 도우미 실행 증거로 바꾸지 않는다.
- R2 일반 실행 결과가 세 턴 연속 필요한 동일 조건이며, 안전하게 수행할 독립 준비·검증·최종 전달은 끝났다. Windows terminal 명령 UI 직접·간접 실행 금지 규정 때문에 자동 실행이나 별도 우회로 진행하지 않는다. 현재 실제 CSV byte windows/새3sample/전후 세대·설정 및 이미지 누락 원인이 없으므로 종료·설치를 먼저 수행하지 않는다. 입력/외부 상태 변경 없이는 의미 있는 다음 작업이 없어blocked 감사 기준을 충족한다. 목표를complete나paused로 바꾸지 않고blocked 갱신을 요청한다.
- 원문: S1_READY_PREP_20261009_R2/handoff-audit-001.json(첫 턴 진행), read-execution-pending-audit-001.json 및 .jpg(둘째), read-execution-blocked-audit-002.json 및 .jpg(셋째). 결과가 없다는 관측으로 사용자 미실행이나 초기guard 오류 부재를 단정하지 않는다. 필요한 입력은 기존 서버 최종R2 READ_READINESS.cmd의 READY READ EXIT/콘솔 또는 실제 새r-결과다. 이미 제시한 실행 요청을 반복하거나 적용 범위 재승인을 요청하지 않는다.
- 재개하면 R2 원문을 서버→공유→개발로 회수하고 콘솔/manifest/개별 SHA256, 현재CSV 바이트·이미지 저장·프로세스/설정부터 검토한다. HOLD이면 자동 재실행 없이 오류 원문을 조사한다. 승인 후보 적용/수집·CSV·설정 보존/결과 회수/다음rollback 등록은 미완료이며4c97d4a 복귀 기준과 기존 설치본·증거를 보존한다.

### 14.18 R2 실행 완료 회수와 현재 수집 진행 검토

- 사용자 실행 완료 응답 후 같은 Browser 탭의 실제 콘솔에서3회 조회/READY READ COMPLETE/EXIT0을 확인했다. 새 r-20261009-202423-0c5c36을 서버 탐색기 자체Copy/Paste로 Z:/SmartFactory/20261009/return/S1_READY_READ_20261009_R2에 회수하고 개발 S1_READY_PREP_20261009_R2/server-results-001로 새 복사했다. 전체33파일/32manifest항목/15781423bytes, 콘솔·공유·개발 manifest SHA256=9FFA7E23093F25D4AA7D8835E824D242FFD5D68D88A25470E4BEF14F44FE7FDC 및 개별 크기/해시/정확한 파일집합이 일치한다. retrieve-ready-read.py exit0, 원문/화면/영수증 보존. 기존R2 입력 blocker는 해소됐고 현재 목표active다.
- review-ready.py 실제exit0/87조건/실패0:12API200, 실제4c fullcommit/frozen, 기존5프로세스·시작ticks/부모/사용자/session 및8000listener, 핵심4파일과설정 전후SHA 유지, 같은SPOT/logger/CSV. poll112368→112387→112404, API rows487056→487133→487211, observation pending/failure0이다. 통신/저장 전수무결성이나 신규 후보 적용 PASS가 아니다.
- 실제 현재CSV의3회 크기는430697452→430797961→430900356bytes(+202904)다. prefix2MiB 해시 유지, 겹치는tail 완전행 내용 유지,110열/schema2.5.2/동일logger·SPOT/연속seq를 확인했다. tail의마지막seq487062→487135→487209/최근시각 진행이다. CSV 인용필드 내부LF를 단순 행경계로 처리한 최초 inspection은_csv.Error/exit1이며 제품CSV오류로 분류하지 않았다. 최종검토는 quote-aware record경계와strict CSV 파싱으로 부분레코드를 제외했다. 전체CSV/metadata/fact validator는 미실행이고 window검토를 전수PASS로 확대하지 않는다.
- image written93922→93938→93954/fact_rows4091706→4091722→4091738,queue0/enqueued=written/failure0,최근write시각과fresh image 요청 진행을 확인했다. 기존dropped15는 증가 없음이나 누락 원인 미확정·개별이미지 파일 미검증을 유지한다. 제한system.log tail의과거18:02 LS No Body/읽기지연 경고가 원인 증명은 아니다. backend shutdown의integrity_unresolved는 과거drop을 보존하는 별도표시이며 증거생성/OS exit/설치허용 판정과 혼동하지 않는다. counter초기화·제품backend/worker정책 변경은 없다.
- 다음은 승인된 적용 단계 내 새 S1_CLOSE_20261009_R1 준비다. R2 원문에 결합한현재실행세대/4c핵심파일/config/CSV 기준,실행직전fresh API·현재작업정보 재확인,정확한main의정상CloseMainWindow1회·held OS handles/exit·cold조회·종료후metadata/제한CSV/log/shutdown증거를 기록한다. 세대·설정·새오류/drop 증가·미완료저장·작업정보동시변경·정상종료 입증부족이면HOLD하며강제종료/자동재시작/설치/복구는 포함하지 않는다. 종료 코드0도후속증거검토 전설치허용이나전수QA가 아니다. 현재4c 롤백과541d 후보 바이트는 유지한다.
- 새helper는 nativePS5.1 파싱·경로/세대/카운터 거부·실파일/fixture정상종료 및exit보존을 검증하고, 공유해시·서버최종폴더/필요파일 확인 후 사용자 일반 실행을 안내한다. Windows terminal UI 직접·간접 실행 금지 때문에 자동 launcher실행은 하지 않는다. 이 단계에서 후보설치·다음rollback 기준갱신은 미완료다.

### 14.19 현재 운영본 정상 종료 도우미 검증과 서버 최종 전달

- 새 C:/Users/user/Desktop/SmartFactory/S1_CLOSE_PREP_20261009_R1/S1_CLOSE_20261009_R1의6파일을 준비했다. 실제R2 manifest/최종health·이미지·오류·runtime/핵심4파일/config·CSV에 결합한reference와R2 검토JSON/MD를 동봉한다. 제품/installer/과거도우미·증거는재작성하지 않는다. helper=close-current.ps1 27632bytes/SHA256734427EAD82DA10DDC8BBD37395CD93A9871FFA437F8C47777939381BDC8BF11; reference=15523bytes/0AE9A3623945BBEAE46392BF065404A00637BD2DAE49E58A8C4C8A5902295E65; CLOSE_CURRENT.cmd=1144bytes/C900B7D88AE93AD3FC53CC5007DC7458896F176553550B5BF40265663B07D05F다.
- 정확한host/SID/표준nativePS5.1/Desktop·reparse/새경로·고정helper/reference를검사한다. 기존5개OS handle·시작ticks/path/parent/session과listener를결합하고 fresh3회조회/수집·이미지 진행/현재작업정보를재확인한다. 종료직전6초기한·같은작업정보/세대/config·새에러/누락없음·미완료저장0과exactmainPID의유일Chrome_WidgetWin_1/Process.MainWindowHandle일치를요구한다. 현재main의CloseMainWindow1회만요청하며mutex/지속intentmarker로동시·동일helper재요청을거부한다. 원래제품의390초fallback은변경하지않고helper는최대450초OSexit만관찰한다. 강제종료 호출은없다.
- held5개실제exit0와cold2회없음을확인한뒤config동일SHA/새CSVshutdown metadata를확인한다. 닫힌현재CSV 최대2GiB를전체해시만읽고복사하지않으며제한prefix/tail/metadata/system·Electron log와현재backend의shutdown begin/final+sidecar를새결과로보존한다. pair/stage/drain·최종행/전체CSV정식validator의후속검토는회수후이며normal_shutdown_verified/installation_clearance=false로남긴다. 기존dropped15/원인미확정은초기화하지않고새후보에귀속하지않는다. 설치·재시작·복구는없다.
- 실제run-validation.ps1 exit0: WinPS5.1 자체검사27개/실파일6개·AST오류0/원본보존·충돌/junction거부,격리된off-screen native창의CloseMainWindow1회/heldexit0 및exit7거부2case(exit0),실제CMD 개발host guard 기대exit1/NORMAL CLOSE EXIT1이다. 모든raw stdout/stderr·exit를기록한후전부읽었고validation-001/result.json의4case가PASS다. 자식에만PSModulePath를제외하며부모/배포환경은그대로다. 도우미시험이며운영정상종료의PASS가아니다.
- 개발6파일59098bytes와Z:/SmartFactory/20261009/send/S1_CLOSE_20261009_R1의개별SHA256을대조했다. 최초공유목록캐시에서이전READ폴더가선택돼동명충돌창에서취소했고덮어쓰기옵션을선택하지않았다. F5후새CLOSE폴더속성의이름·6파일/0폴더/59098bytes를확인하고다시복사했다. 이전공유READ3파일은보존개발원본과같음도대조했다. 캐시목록을새폴더존재증거로사용하지않는다.
- 서버탐색기자체Copy/Paste로실제C:/Users/user/Desktop/SmartFactory/S1_CLOSE_20261009_R1을새복사했다. 해당절대경로/6파일·launcher1144bytes속성·선택화면을확인했고server-copy-001.json/3화면·공유records에보존한다. 서버로컬helper/reference SHA는사용자launcher실행시검증대기이며화면확인을해시PASS로바꾸지않는다. 회수용return/S1_CLOSE_READ_20261009_R1도새준비했다.
- Windows terminal UI 직접·간접실행금지의정확한규정과서버CLOSE_CURRENT.cmd의일반1회실행/NORMAL CLOSE EXIT 결과를안내했다. 실행되면현재앱이정상종료되고후속검토까지닫힌상태로남는다. EXIT1/HOLD이면재실행하지않고원문/실제앱상태부터회수한다. 기존적용승인재요청이아니며이번새실행입력의첫turn다. 목표active/전체미완료,4c 복귀기준/541d후보를유지하고후보설치·적용확인·결과회수·다음rollback갱신은남아있다.

### 14.20 정상 종료 HOLD 회수와 종료 후 읽기 보완

- 실제 콘솔은 NORMAL CLOSE EXIT1/CLOSE_HOLD:cold-not-empty다. r-20261009-205507-89d3d9을 서버→공유 return/S1_CLOSE_READ_20261009_R1→개발 S1_CLOSE_PREP_20261009_R1/server-results-001로 회수했다. 전체41파일/40manifest항목/15510112bytes, 콘솔·공유·개발 manifest SHA256=497BE79329FA90D35CB4EAA24EF64988147FAA172AD5202C9CE29A2F1B94C079 및 개별크기/해시/파일집합이 일치한다(retrieve-close.py exit0). HOLD 원문과 화면은 변경하지 않는다.
- CloseMainWindow 요청은20:55:36.923+09:00 한 번, sent=true다. os-exit와held-final에는 기존5개 OS handle의actual exit0이 있다. cold-1에는동일PID9384/부모9580/시작ticks639270294880862241/session3/SID가 남고 path=null이며8000 listener는0개다. 재조회의 비어 있지 않은 결과를 무시해 정상종료 PASS로 바꾸지 않는다. 후속 cold-2/config-after/closedCSV/log/metadata-after/shutdown pair는 이 HOLD로 생성되지 않았다. 후보설치/재시작/강제종료는없다.
- 개발 PC의고립native창3개를 정상CloseMainWindow 후 actual exit0 상태로관찰하는 WinPS5.1 재현은exit0다. held handle 유지중·Dispose후 모두CIM목록0개여서 이번잔존현상은재현되지않았다. handle때문인원인을확정하거나제품worker/종료정책을변경하지않는다.
- 승인된 적용전 증거수집의누락보완으로 새S1_CLOSE_READ_20261009_R2를준비한다. 원래R2기준/고정CLOSE manifest·closeintent·held5exit0을결합하고, 새실행에서cold2회/config·old핵심4파일/같은CSV shutdownmetadata/전체해시와제한window·Electron/system log·같은backend의begin/final+sidecar만읽는다. 현재process나8000listener가있으면HOLD한다. 앱종료요청/시작/설치/복구/장비API/카운터초기화/CSV·설정쓰기/재귀data조사는없다. 종료후OS여유상태·pair/stage/drain·최종행검토전설치허용=false다.
- 새helper nativePS5.1 parser/self-test·거짓세대/exit거부·실파일경로/창해시/충돌·hostguard와전송해시를검증하고서버최종폴더확인후일반사용자실행을안내한다. 구CLOSE helper는재실행하지않는다. 이번HOLD회수로실행입력blocker는해소됐으며목표active/전체미완료다.

- review-close.py 최종검토exit0/62조건/실패0:19API200·고정작업정보6필드/4c세대/수집과이미지진행,3CSVwindow의해시/110열/동일logger·SPOT/연속tail seq·겹침행보존,CloseMainWindow1회/held5 actual exit0/HOLD 충돌원문을확인했다. 최초review001은API전체body와Work6필드를비교해추가history필드때문에4조건실패(exit1)했고그원문을보존했다. 작업정보변경으로판정하지않는다. 최종MD/JSON은S1_CLOSE_PREP_20261009_R1/server-close-review-002에있다. 정상종료전체·설치허용PASS가아니다.
- 새S1_CLOSE_READ_20261009_R2 helper15974bytes/SHA256 CB85989DE5DF8EA7C7E89FD3D61EAA6F8CB9D2FEB4AC3CFC17D241693BB99D1A,reference21826bytes/7629003903874D9798B500DBABC6030DDB10C25C63BB3A68DB0C8C3301D984CB,READ_CLOSE.cmd1139bytes/7AEC92266FBC7837D818218849B1411FF64E3684669042BBACAD98A83EF89EB8다. WinPS5.1 run-validation.ps1 실제exit0:자체19·실파일6/parser0·소스보존/충돌/junction거부exit0,실제CMD hostguard 기대exit1/CLOSE READ EXIT1,stderr0다. 제품시작·종료·장비요청AST금지검사도exit0이며앱변경없다.
- 개발6파일45251bytes→Z:/SmartFactory/20261009/send/S1_CLOSE_READ_20261009_R2의전체해시대조exit0. 서버탐색기Copy/Paste로C:/Users/user/Desktop/SmartFactory/S1_CLOSE_READ_20261009_R2를새복사하고절대경로/6파일/launcher1139bytes속성·선택화면을확인했다. 갱신중목록좌표가바뀌어과거sha256텍스트가미리보기로열렸지만읽기상태에서닫고정확한최종절대경로로이동했다. 텍스트·구증거변경/덮어쓰기/terminal자동실행없다. server-copy-001.json과4화면/공유records에확인범위를보존하며서버로컬helper/reference해시는일반실행의pin검증대기다.
- 회수return/S1_CLOSE_POST_READ_20261009_R2를새준비했다. 새READ_CLOSE.cmd의일반실행/CLOSE READ EXIT결과를안내했고Computer Use필수guidance의Windows terminal UI직접·간접실행금지로사용자실행을요청했다. 기존CLOSE_CURRENT.cmd재실행/추가종료요청없다. 이번새읽기실행입력의첫진행turn이며목표active/전체미완료다. 실제결과가오면현재OS빈상태·설정·closedCSV·shutdown pair/stage/drain부터검토하고승인된후보적용으로이어간다.

### 14.21 종료 후 읽기 완료와 실제 정상 종료 근거 확인

- 사용자 새READ 실행완료 응답 후 실제콘솔 CLOSE READ EXIT0/COMPLETE를확인했다. r-20261009-211407-6fd4bc 전체34파일/33manifest항목/22858525bytes를서버→공유return/S1_CLOSE_POST_READ_20261009_R2→개발S1_CLOSE_READ_PREP_20261009_R2/server-results-001로회수했다. 콘솔·공유·개발manifestSHA256=94C9BECAF2D8E1DE2AD81ED06B23BF1D9A3CE0D93C01215C1AFA88509485E743 및개별해시/크기/파일집합일치(retrieve-read.py exit0). 이실행입력blocker는해소됐고목표active다.
- review-read.py 최종002 실제exit0/46조건/실패0:held5개actualOS exit0·새cold3회process/listener0·설정SHA전후일치·old핵심4파일일치다. 동일backend PID9036/시작시각/세대/session/4c fullcommit에결합한begin/final pair·sidecar·beginSHA/before_verified·동일image shutdownID/실제종료요청시각을확인했다.9stage성공·observation/image drained·system final ack exit0와Electron session9580-muz0rofv-ogdsa2j3의시작ticks/9036spawn/shutdown-complete forced=false/exit0/20.6305초가일치한다. 이전CLOSE EXIT1/cold충돌원인미확정을삭제하지않으며정상종료근거는별도후속검토로등록한다.
- closedCSV441853493bytes/SHA256 D4147FF00A2B71A45F9782A8E55927AD9BF7D3B2A47BBC8B2F07F7FEF5E4213C,원래metadataSHA A855D32D33E50E37FA0146CEAE90C64B9005ECB68DBF9A4B9286BCD65DF302BE다. prefix·종료전tail겹침행/110열/schema2.5.2/동일logger·SPOT/연속tail·최종seq495480,시각20:55:37.159798이shutdown closeout과일치한다. CSV·metadata전체raw bytes는개발복사하지않고서버해시계산을기록했다. 회수metadata는파싱후재직렬화한객체로결과manifest해시를검증한다. 최초001에서원래metadataSHA와재직렬화객체SHA를비교해1조건실패(exit1)한분석오류를보존하고002에서수정했다. 원본손상으로판정하지않는다. 전수CSV schema/fact validator는미실행이다.
- 이미지begin/final written/enqueued94043/queue·unfinished·inflight·새failure0·workerstopped/writes_drained=true다. 과거drop15/integrity_unresolved=true·개별이미지미검증을보존한다. CSV image manifest는종료전과동일한과거snapshot33590written/drop0이며최신drop15의반증으로사용하지않는다. 실제repository closeout은observation manifest/closeout만갱신한소스·전후metadata 차이와일치하며backend수정범위를확대하지않는다. 영수증installation_clearance=false/formalQA=false는그대로다.
- 다음은현재승인범위의고정541d 후보설치와후속검증이다. 후보install54핵심/외부frontend파일pin·실제provenance·새runtime/PID/start/owner/parent/listener·health fullcommit·실API/화면SPOT통신/온도분리·수집진행·원래설정/closedCSV해시보존을확인한다. 적용후확인전4c 롤백/구증거를보존하고새기준갱신/강제종료/자동복구/카운터초기화/장비설정변경/반복120분시험은하지않는다. 설치전후증거도우미를서버최종폴더까지준비·검증한뒤설치를진행한다.

### 14.22 승인 후보 설치와 적용 후 증거 묶음

- 승인된541d 설치본은서버C:/Users/user/Desktop/SmartFactory/S1_CAND_20261009_R1/installers/UI_S1_541d701_UNSIGNED.exe(163826264bytes/SHA08C061EE35A1A01788F05B00EE7395AA40774150C92C06726A92F3DF1BF75C3C/NotSigned)다. 4c 롤백installer/hash는보존한다. 제품소스·빌드·installer를새로만들지않고검증한동일바이트를적용한다.
- 별도새S1_APPLY_20261009_R1 도우미를준비한다. 정상종료검토002/후속READ manifest94C9와닫힌CSV/meta/config 해시·old핵심4파일,후보54파일catalog를reference해시로결합한다. 실제서버host/SID/표준사용자/WinPS5.1/폴더/새결과/reparse/cold2회·closedCSV/meta/config/old핵심·후보와rollback installer hash/NotSigned를먼저검사한다. 불일치면설치하지않는다.
- 실행은사용자가일반launcher를실행하는경로다. 도우미는잠근정확한후보installer1회만일반GUI로열고actual OS exit0을기록한다. 기존설치경로를그대로사용하며새EULA/UAC/보안경고는사용자에게인계한다. 자동보안우회/강제종료/재시도/자동rollback은없다. 설치가끝난뒤이미실행된후보를확인하고없을때만정확한설치exe를1회시작한다. 동시/중복적용은같은도우미의지속intent/mutex로거부한다.
- 새실제provenance/핵심4+외부frontend50파일pin을검증하고,실제관측한단일main/backend 세대의PID/시작ticks/path/부모/session/SID/listener8000을결합한다. startup안정화를제한시간안에확인한후3회health/spot-config/stats/data/operator정보GET만수집한다. fullcommit541d/frozen·새SPOT/logger·fresh poll/수집증가·observation/image오류0·실제새CSV의제한prefix/tail/설정전후SHA와기존닫힌CSV/meta전체SHA보존을확인한다. UI실화면은후속Browser관찰로API응답과대조한다.
- 새CSV는health실제basename/실제root에결합하며기존닫힌CSV와다른지검사한다. 값이바뀔수있는제품/금형을과거값으로고정하지않는다. logger/수집세대가바뀌어counter가새로시작한것과기존counter초기화명령을구분한다. historicaldrop15와원인미확정을구영수증에보존한다. 새후보정식QA/기존이미지전수무결성/과거CSV 전수schema-validator는새PASS로바꾸지않는다.
- nativePS5.1 parser/self-test·부정hash/commit/path/runtime/nonzeroexit·실파일창/소스보존/충돌/junction/hostguard·고립child exit보존을검증하고전체해시·서버최종복사/필수파일을확인한뒤사용자실행을안내한다. 적용후결과는서버→공유return→개발로회수해검토한다. 성공범위확인전운영승격/다음rollback등록은대기한다.

- 새적용묶음6파일/69346bytes의최종helper28298bytes/SHA256=4A65A2790EA8AF1C14FAD1F598D6E39D659BAF5B99486FDCA755E9447BB67243,reference32121bytes/3195F14EB0724AC403D0B55D2B86643106047B706CDAF80B667451D01EBD3BF5,launcher1145bytes/017408A6BE9C77A264B8AE9DB0DE4E4441246047F2CC7DE57C8C2D6C2B2B77E9다. 실제old API fixture를reference에넣어dev절대경로의존없이서버자체검사를재현한다. 원본fixture의상태를현재서버상태로사용하지않는다.
- nativeWinPS5.1 validation003 실제exit0:자체31개/실파일6개·parser0·원본보존/충돌/junction거부exit0,actualCMD개발host거부기대exit1/CLOSE_HOLD:server-host·UI-S1 APPLY EXIT1,모든stderr0다. owned-child001/validation-owned001 실제exit0는고립Pythonchild의실제held OS exit0허용/exit7원문보존·거부2case를확인한다. 제품installer/앱은시험에서실행하지않았다. 최초validation001 exit1은제약없는main부모를거짓거부하려던시험오류(runtime-negative)이며원문보존후backend부모시험으로수정했다. 중간002와draft준비001도재작성하지않는다. 최종helper바이트는최종시험후변경없음/전체stdout·stderr·exit검토,prepared-files002에결합했다.
- 개발6파일→Z:/SmartFactory/20261009/send/S1_APPLY_20261009_R1 전체크기/SHA256대조exit0. 서버탐색기자체Copy/Paste로실제C:/Users/user/Desktop/SmartFactory/S1_APPLY_20261009_R1에새복사했고절대경로/6파일/launcher1145bytes속성·선택상태를확인했다. server-copy001과4화면·공유records에확인범위를보존한다. 기존파일덮어쓰기/terminal자동실행없음. 서버로컬helper/reference SHA256은실제사용자launcher의pin검증대기이며화면확인을해시PASS로바꾸지않는다.
- 새회수return/S1_APPLY_READ_20261009_R1를준비했다. 선택된APPLY_UI_S1.cmd를일반1회실행하고기존설치경로유지·정상installer GUI완료후UI-S1 APPLY EXIT결과를알려달라고안내했다. 이번실행은읽기전용이아닌승인후보설치·시작임을명시했다. Computer Use필수guidance의Windows terminal UI직접·간접실행금지때문에사용자실행이필요하며적용승인재요청이아니다. EXIT1/HOLD재실행/자동rollback없음. 이번새적용실행입력의첫진행turn/목표active이고실제후보적용·UI/API·CSV/config검토·회수·운영승격/다음rollback등록은미완료다.

### 14.23 적용 실행 결과 대기 재검증

- 직전 목표 턴은 최종 WinPS5.1/실제 child exit 검증, 고정 해시의 공유 전송·서버 최종 복사와 실행 인계를 완료한 progress다. 이번 재개에서 같은 Browser 탭의 fresh 탐색기 F5로 S1_APPLY_20261009_R1의 기존6파일만 확인했고 새 r-결과는 관측하지 못했다. 공유 return/S1_APPLY_READ_20261009_R1의 실제 자식은0개다. 실행 중인 도우미 process/session handle은 확인되지 않았으므로 verified wait로 분류하지 않는다. 초기 launcher guard 실패 가능성도 결과 없이 배제하지 않는다.
- 이번 턴은 같은 실행 입력이 필요한2번째 턴이며 no progress다. 실행 요청을 반복하거나 terminal UI 금지의 우회로 설치·시작을 수행하지 않는다. 안전하게 필요한 준비/검증/최종 전달은 끝났으며 다음 의미 있는 단계는 실제 UI-S1 APPLY EXIT와 결과 회수다. 아직3턴 blocked 감사 기준을 충족하지 않아 목표active/전체미완료를 유지한다.
- fresh 화면과 감사 원문은 S1_APPLY_PREP_20261009_R1/apply-execution-pending-001.jpg 및 apply-execution-pending-audit-001.json에 보존한다. 실제 적용·새 API/화면·CSV/config 보존을 확인한 뒤에만 후보 운영 승격과 다음 롤백 기준을 등록한다. 기준4c/후보541d/installer·과거 증거는 그대로다.

### 14.24 적용 실행 입력 필요 조건의 blocked 감사

- 재개3번째 턴의 같은 Browser 탭/fresh 탐색기 F5에서도 최종 S1_APPLY_20261009_R1는 기존6파일만 보이고 새r-결과를 관측하지 못했다. 공유 return/S1_APPLY_READ_20261009_R1의 실제 자식은0개다. live 도우미 실행 handle은 확인되지 않았으며 초기guard 실패를 배제하지 않는다. Browser 연결을 installer/도우미의 verified wait로 취급하지 않는다.
- 첫 턴의 최종검증·공유해시·서버최종복사·인계는 progress, 둘째와 이번 셋째 재개는 no progress다. 같은 실제 실행 결과 입력이3턴 연속 필요했고 안전하게 수행할 독립 준비는 완료했다. Windows terminal UI 직접·간접 실행 금지 규정을 우회하지 않고 기존 사용자 실행 요청을 유지한다. 실제 설치·새세대·UI/API·CSV/config 보존 증거 없이 운영승격/다음rollback등록을 수행할 수 없으므로 blocked 감사 기준을 충족한다. 목표complete/paused로 바꾸지 않고blocked 상태변경을 요청한다.
- 감사 원문·fresh 화면은 S1_APPLY_PREP_20261009_R1/apply-execution-blocked-audit-002.json 및 apply-execution-blocked-002.jpg다. 재개 조건은 기존 서버 최종 폴더의 APPLY_UI_S1.cmd 실행 후 UI-S1 APPLY EXIT/실제콘솔 또는 새r-결과 확인이다. EXIT1/HOLD이면 재실행하지 않고 원문부터 회수한다. 기준4c/후보541d/검증한installer 및 원래 증거를 보존한다.

### 14.25 실제 후보 설치와 API timeout HOLD 회수

- 사용자 실행완료 후 실제 콘솔 UI-S1 APPLY EXIT1/GetResponse timeout/HOLD를 확인했다. r-20261009-220826-a3fbbb 전체18파일/17manifest항목/63130bytes를 서버→공유 return/S1_APPLY_READ_20261009_R1→개발 S1_APPLY_PREP_20261009_R1/server-results-001로 회수했다. 콘솔·공유·개발 manifest SHA256=354E8911670F838144B51C24314DDA2D8369358A578EF61FE440424EDFF501CD와 개별 크기/해시/파일집합이 일치한다(retrieve-apply.py exit0). 이전 실행 입력blocker는 해소됐고 목표active다.
- 부분 검토32조건/실패0/exit0: installer PID25388 actual OS exit0(22:08:42.171~22:09:22.534 KST), 정확한541d provenance와 선택54설치파일, 새main17012/backend17348·전체5process/owner/session/parent/8000 listener binding이 일치한다. 자동launch된 후보를 관측했으며 helper의 별도 app-start 요청은false다. 설치 전cold3회0, 설치 직후 원래 config SHA6841... 및 닫힌CSV441853493bytes/SHA D414.../metadata A855...도 그대로다. 전체payload 설치무결성/운영승격 PASS가 아니다.
- 초기health2회200/latency362.4042ms·26.2021ms, 새SPOT9f93aea7-b9c8-4882-b833-34a029741881/logger9307deb8-6b70-4005-8d0c-400f5a27f217, poll20→24/success/fresh를 확인했다. 두health의 logger rows1/current CSV=null이어서 전체수집·CSV 준비 완료가 아니다. 원래 helper의 startup-ready는 SPOT poll>0만 확인했고CSV/image 준비를 요구하지 않았다는 한계를 기록한다.
- 순차helper에서 sample001health만 생성되고 다음spot-config가 없으며 GetResponse timeout 원문이 있으므로 실패route는 /api/spot/config로 추론된다. source의 image-capture health는 capture lock 안의 writer생성→기존 fact 전체hash/CSV행수 초기화를 통과한다. 이경로와 app/spot-image source는4c→541d에서동일함을git diff로 확인했다(exit0). 실제 서버의 timeout 원인은 미확정이다. 제품backend 수정/재빌드·재설치·재시작·force/자동rollback은 하지 않는다.
- 실제 후보 UI에서 SPOT OK / Temp UNDER_RANGE / Comm OK와poll=success/raw=invalid_sentinel/source=fresh/온도invalid_value/cacheempty를 별도로 표시하는 상태 패널을 관찰했다. under-range를 통신장애로 집계하지 않는다. 원래Temperature 값/안전gate 계약은 유지한다. 서버 UI 원본·패널 화면, APPLY EXIT1, 부분검토JSON/MD를 S1_APPLY_PREP_20261009_R1에 보존한다. 초기 API와 이후 UI는 시간대가 달라 이 두개만으로 전체실API→화면·수집/CSV보존 완료라고 하지 않는다.
- 승인된 적용후 검증 누락을 채우기 위해 새 S1_POST_READ_20261009_R1의읽기전용묶음을 준비한다. 실제APPLY manifest/부분검토/고정541d·54pins/원래CSV/meta/config·실제main/backend·SPOT/logger IDs를reference로 결합한다. 기존후보를 설치·시작·종료하지 않고현재세대만 읽는다. 현재전체runtime를 새binding으로 기록하되 main/backend의원래PID/시작ticks/path/owner/session/parent가 동일해야 한다. 나머지Electron자식도현재단일main/path/owner/session에속해야 하며조회 전후새전체binding을유지한다.
- 세번의같은5 GET/고정5초timeout·2MiB/원문body·route/실제latency/error/status를기록하고독립조회실패도보존한다. 전체조회/세대/신선poll·온도유효성분리/실제새CSV·수집과이미지진행/설정·옛closedCSV/meta hash보존은별도criteria로판정한다. 실패를없애기위해timeout을늘리거나신규오류·image drop을지우지않는다. 현재CSV의제한prefix/tail과raw metadata(원래bytes/hash)를읽고제한system/Electron log를회수한다. 과거이미지15drop/원인미확정·전수CSV/schema/개별image/정식QA미검증은유지한다.
- 새reader는nativePS5.1 parser/self-test/거짓commit·runtime·service·route/실파일window·source보존·충돌/junction·actualHTTP200/503/timeout기록·hostguard를검증하고공유해시·서버최종복사후일반실행을인계한다. 기존APPLY installerhelper는재실행하지않는다. 후속read와실UI를대조하고전체수집·CSV/config보존을검토한뒤운영승격/다음rollback기준을갱신한다. 현재그단계는미완료이며4c복귀설치본을보존한다.

### 14.26 설치 후 읽기 도우미 검증과 서버 최종 전달

- 새S1_POST_READ_20261009_R1의6파일/81758bytes를 준비했다. 최종 read-post.ps1 29034bytes/SHA2561594D9E2CCF159AA894B529703AFCC4947992B8044F48A3E64EAA26CA2781CE4,reference42336bytes/5EEB7C85B81D5975EFEEBB617C1D8938797CAF42E6C0D989752A6C4F03CEE765,READ_POST.cmd1137bytes/EF2803D61198A05F6CD33FC20A135EB610F6DD57367BD354B760D147836611AA다. 18개의기존 검증함수를source hash/AST로 추출했고 설치·시작·종료 함수는 포함하지 않는다. 초안prepared001은보존하며 최종prepared002에실제시험을결합했다.
- native WinPS5.1 run-validation.ps1 실제exit0:자체37개/실파일6개·parser0·source보존/충돌/junction거부exit0,actualCMD개발host거부는기대exit1/POST_READ_HOLD:server-host·UI-S1 POST READ EXIT1이다. raw stdout/stderr/exit 전체를읽었고stderr0이다. 자식에만PSModulePath를제외했으며부모/배포환경은변경하지않는다.
- 별도고립loopback actualHTTP4case는200 JSON/503 원문·status/2MiB초과거부/5초timeout(5011.8097ms)을확인했다. runtime endpoint/예산/에러원인을저장하고 성공·503 raw body를보존한다. 실제fixturechild의exit0/stderr0, static제품실행·종료금지0,helper원본 hash불변을검증했다(validation-http002 exit0). fixture 전용port치환은shiphelper에없고server/장비요청0이다. 최초HTTP001은4case결과를저장했지만 oversize client abort의Windows10053를fixture가stderr에남겨parent exit1이었다. 원문을보존하고fixture의예상ConnectionAbortedError 처리만보완했다. shiphelper 바이트는수정하지않았다.
- 개발→Z:/SmartFactory/20261009/send/S1_POST_READ_20261009_R1 전체6파일 SHA256/크기대조exit0. 서버탐색기자체Copy/Paste로 C:/Users/user/Desktop/SmartFactory/S1_POST_READ_20261009_R1에새복사했고 정확한절대경로/6파일/READ_POST1137bytes속성·선택을확인했다. 4화면·server-copy001·공유records에확인범위를기록한다. 서버로컬helper/reference hash는실제사용자launcher의pin검증대기이며 화면확인을hash PASS로바꾸지않는다. 기존파일덮어쓰기/terminal자동실행없다.
- 새return/S1_POST_READ_20261009_R1를준비했고 선택된READ_POST.cmd의일반1회실행/UI-S1 POST READ EXIT결과를요청했다. 읽기전용이며설치·앱시작·종료없음,EXIT1/HOLD이면재실행하지않고원문회수,기존APPLY도재실행하지않음을명시했다. Computer Use필수guidance의Windows terminal UI직접·간접실행금지때문에사용자실행이필요하며재승인요청이아니다.
- 이번재개는실제18파일 회수·부분검토32조건·UI의under-range와정상복구관찰·후속reader47검사/hostguard·공유해시·서버최종전달을완료한progress다. 새로운읽기실행입력의첫턴이며목표active/전체미완료다. UI 정상값복구원본도보존했다(server-candidate-normal002). current제품/금형값은변동가능하며과거값강제/물리작업상태단정은하지않는다. 결과회수·3회실API/새CSV/config보존검토·UI대조·운영승격/다음rollback등록은남아있다.

### 14.27 실제 후속 POST READ 완료·회수·독립 검토

- 사용자 실행 완료 뒤 실제 콘솔 POST READ COMPLETE/EXIT0, `r-20261009-224441-1f2226`을 확인했다. 처음 조회에는 새폴더가 아직 보이지 않았으나 이후 실제 완료창과 새r-폴더를 확인했다. 재실행하지 않았다. 처음 저장한 complete001/002 화면은 탐색기 상태이며 콘솔 증거는 complete003 원본이다. 구스냅샷을 완료창의 증거로 사용하지 않는다.
- 서버→공유return/S1_POST_READ_20261009_R1→개발S1_POST_READ_PREP_20261009_R1/server-results-001로65파일/64manifest항목/19553736bytes를 회수했다. 콘솔·공유·개발 manifest SHA256 `8666510BABB8D0D6EAAF071DBAAD671554BC6EF782B745AC0723CF157150B92A`와 모든파일 크기/해시/정확한 집합이 일치한다(retrieve-post.py exit0). helper/reference 서버pin 검사를 통과한 실제결과이며 기존APPLY/installer는 재실행하지 않았다.
- review-post.py 실제exit0/128조건/실패0다. installed54pins/provenance/full541d, 동일5runtime/main17012/backend17348·start/parent/path/owner/session·8000listener 및SPOT9f93/logger9307 유지. 15 GET 모두HTTP200/원문JSON 일치, 5000ms/2MiB 예산 유지. poll2127→2134→2142,rows9316→9349→9379,imagewritten1107→1114→1121/factrows4092934→4092941→4092948,새image drop·저장/source/HTTP오류·대기0.
- 실제 새CSV Factory_Integrated_Log_v2_20261009_220923.csv 크기12528968→12568695→12608748bytes(+79780),prefix2MiB 유지/겹침tail행 보존/110열/schema2.5.2/연속seq/최근행을확인했다. 마지막seq9316→9345→9376이며API보다늦게읽어도항상API와동일행이라고추정하지않는다. 첫10행SPOT ID없음은startup_pending/Temperature공란이고그뒤세대는동일하다. under/stale/초기 온도공란·sentinel 미기록을확인했다. metadata raw24499bytes/SHA C3076C70F5BA60F1EF4C9312A246D149D083935D3BDB5D658059D92ADCD1BCB2를3회 보존·객체/hash대조했다. 전체CSV/이미지 전수validator는미실행이다.
- 원래config6841.../닫힌CSV441853493bytes·D414.../rawmetadataA855... 전후동일해시다. actual UI정상SPOT OK/Temp OK/Comm OK·success/valid_temperature/fresh 패널,앞선UNDER_RANGE/통신OK 패널을보존했다. API와화면은각관측시점의상태종류를대조했으며동일poll/정확온도값대조로확대하지않는다. 실제현재작업60383/8과API/CSVtail이일치하고agent의설정/작업정보변경은없다.
- 최초APPLY EXIT1 timeout/원인미확정 원문은유지한다. 후속spot-config47.3727/32.7931/31.8358ms로응답했지만첫health223.4887ms는운영200ms기준초과다. 다음health13.7190/9.9844ms도전체성능PASS근거로확대하지않는다. 과거4c drop15/원인미확정과shutdown502·metadataopen snapshot/configfingerprint mismatch/async_fact_only/comparator미확인·정식QA false를보존한다. 과거증거수정·counter초기화·제품변경/재빌드·재설치·재시작/stop/force/자동rollback은없다.

### 14.28 승인 범위 완료·운영본과 다음 롤백 기준 등록 (2026-10-09T14:02:03.420Z)

- 승인된4단계 목표를대조했다: QA Get-FileHash 범위보완/최종fullhealth exit0(14.3),새independentreview completed/converged·binding verified/결함0,541d cleanbuild commit·lockedinstaller08C/NotSigned·payload1771/frontend50·packaged7state(14.5),실제server최종전달/old정상종료/installeractualexit0/후속수집·CSV/config/UI·전체결과회수(14.21/14.25/14.27)가준비됐다. 후속제품/검증입력은541d 이후변경없고이번문서검증에빌드·health를반복하지않는다.
- [x] 새운영본/다음변경rollback:541d701d544eea6a8a4e4836047077eaf9cfaf30 /163826264bytes/SHA08C061EE35A1A01788F05B00EE7395AA40774150C92C06726A92F3DF1BF75C3C/NotSigned.
- [x] 이번교체전이전본:4c97d4a00d79ae0d3da70b2e82af227345e21040 /164583937bytes/SHAD453C1D17EFC706D3E21FE6F8D09F739F159EBF9F3F24F2EB2349E92D4EF84FB/NotSigned와구증거보존. 두서버installer는S1_CAND_20261009_R1/installers에있으며원래설정/closedCSV보존을호환근거로남긴다.
- [x] 운영기준문서의2026-10-09 새이력/최신보고·분석/PDCA상태와기준계획두사본을갱신한다. 기존main checkout의다른미커밋변경과baseline의기존문구차이는보존한다. oldhelper/result/promotionfalse 영수증은재작성하지않고새operating-promotion001로별도운영결정을등록했다.
- 현재승인된UI-S1 작업은완료다. 설계10항목의충족률100%는UI-S1 범위의대조이며정식QA/서명·전체성능·CSV/개별image전수무결성/기존fallback 미보장까지PASS라는뜻이아니다. 외부Claude 미설치·legacy identity없는cross-source fallback·선택적memo7줄 advice 미적용/과거OOM·backendtimeout 원인미확정도유지한다. 과거절의미완료체크는그때상태이며현재결론은이절과최신보고다. push/merge/PR/추가운영행위는수행하지않는다.

## 15. 승인된 소스 병합과 기존 운영본의 이력 연결

### 15.1 승인·범위·완료 조건 (2026-10-09 후속 재개)

- 사용자는 TPM 설명의 "UI-S1 승인 개선·운영 적용 완료 / 소스 병합 미완료 / 정식 전체 검증 미완료" 결론을 선택하고 "진행 승인"했다. 이 승인은 UI-S1 원격 브랜치 게시, PR 작성·검사 확인, 보호된 master 병합 및 병합 결과와 기존 운영 설치본·승인·복구 기록 연결에 적용한다.
- 원격 master와 기준은35959c41edee29573040d571ead952c073f1be13, 재개 브랜치 HEAD는2808d103db9e80f61a3e28dc61c8cb5a00bcfc32다. 현재 제품/검증 입력은541d701d544eea6a8a4e4836047077eaf9cfaf30와 같으며 그 뒤 변경은 docs뿐이다. master는 PR 필수/관리자 포함 보호 적용, 필수 승인 수0, 필수 status check 등록 없음, 미해결 대화 해소 요구다. 보호를 해제하거나 우회하지 않는다.
- 포함: 이 계획·보고서·운영 기준에 병합 절차와 인계 기준 기록, 제품 출처 비교, 변경에 필요한 최종 검증, GitHub PR/CI/병합 상태 확인, 병합 후 실제 SHA와 운영본 식별을 새 증거로 보존. 정식 QA·서명·성능·설정/전수 검증의 미완료 항목은 별도 후속 목록으로 관리한다.
- 제외: 추가 제품 로직·설정 수정, 신규 installer 배포, 서버 앱 재설치·시작·종료·자동 롤백, 서명 인증서/비밀정보 구성, 과거 증거 재작성. CI가 생성하는 별도 시험 artifact는541d/08C 운영 설치본으로 간주하지 않는다. 새 제품 변경이 필요하면 이유·영향을 알리고 승인·계획 반영을 먼저 한다.
- 현재 운영본/다음 개선 rollback은541d/08C, UI-S1 자체 장애의 교체 전 이전본은4c/D453이며 원래 설정/CSV 보존 근거와 복구 호환성을 유지한다. 동일 installer의 재승인·재빌드·반복120분 시험을 자동 추가하지 않는다.
- 절차: 원격 재조회 → 최종 diff/제품 동일성 확인 → 문서·인계 항목 갱신 및 원문/exit 검토 → clean 문서 commit → branch push/PR → CI 결과 확인 → 승인된 PR merge → 원격 master와 실제 merge SHA/제품 동일성 재검증 → 새 병합 완료 영수증과 원격 기록 연결.
- 증거 위치: `C:/Users/user/Desktop/SmartFactory/S1_MERGE_20261009_R1`의 새 실행 폴더. 기본 개발 폴더의 기존 미커밋 변경을 보존하고, 기준 계획의 동일 내용 사본만 동기화한다.
- [x] 승인 범위 기록·기준 계획 재개, GitHub 로그인/원격·브랜치·보호 정책 확인, 운영/이전 installer SHA256 재대조.
- [x] 최종 병합 대상 문서·인계 및 검증 근거 정리. preflight.py exit0: docs 밖818개 Git 항목/제품·검증571개 입력이541d 및 최종health exit0 당시와 동일, 원문전체/hash/exit 검토, 운영·이전 installer SHA 및 POST 검토 결합 확인. 현장 대응·복구·정식 검증 후속 목록은 운영 기준에 기록했다. 제품 변경 없는 기존 검증을 재실행한 것으로 표시하지 않는다.
- [ ] PR 게시·연결, 해당 head의 CI 결과 확인.
- [ ] 보호된 master 병합과 실제 원격 SHA/제품 동일성 확인.
- [ ] 운영 build541d/installer08C와 merge SHA를 구분한 완료·인계 기록 및 기존 변경 보존 대조.
