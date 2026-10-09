# UI-S1 Pre-Landing Review — A 승인 보완 결과 (2026-10-09 KST)

**Pre-Landing Review: 0 issues (0 critical, 0 informational) — INCOMPLETE.**

> 후속 상태: 이 문서의 review/QA 판정과 source manifest는 A 승인 보완 시점의 증거다. 이후 사용자가 승인한 순수 수신 helper 리팩토링의 현재 source·최종 로컬 검증은 [구현 보고서9절](../04-report/spot-comm-temperature-ui-s1.report.md#9-후속-수신-로직-리팩토링과-최종-검증)을 따른다. 새 독립 review/binding을 확보한 것은 아니며 전체 INCOMPLETE를 유지한다.

승인한 R1/R2의 로직 보완·회귀·로컬 검증은 끝났다. 전체 review는 기준 계획의 독립 agent 금지와 Windows review-start receipt 오류로 필수 coverage/binding이 없어 INCOMPLETE다. 이 구분은 코드 보완의 PASS를 취소하거나 운영/병합 준비를 승인하는 의미가 아니다.

| 검토 대상 | 값 |
|---|---|
| 브랜치 / HEAD | codex/spot-comm-temperature-ui-s1-20261008 / 35959c41edee29573040d571ead952c073f1be13 + 미커밋 변경 |
| 승인 | 사용자 A — 두 결함과 세 회귀 수정; 부모 구현1회, 독립 subagent 미사용 |
| 범위 | 이전 후보에서 frontend 타입·공통수신·effects·integration시험4개 변경, 나머지9개 frontend 입력 동일. backend/장비/TTL/안전 gate/CSV/leader/backoff 변경 없음. |
| 현재 판정 | 확인된 로컬 로직 미해결0건. scoped QA materialize pass/open[]. full review completed:false, converged:false, cycles:1, trusted binding 없음. |
| 과거 원문 | [최초 review 전체](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/previous-review.md); 최초 red/correction/review 로그 및13개 discovery checkpoint를 포함한 원문 보존 |

## 완료한 승인 수정

- **[FIXED + TEST] R1 [CRITICAL, confidence10/10]** legacy 지연 중복을 최근256개 전체 payload 이력으로 제외한다. [effects](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/frontend/src/domains/Observability/hooks/useSystemViewModelEffects.ts:365). 원래 fingerprint: frontend/src/domains/Observability/hooks/useSystemViewModelEffects.ts:364:race-condition.
- **[FIXED + TEST] R2 [CRITICAL, confidence10/10]** sender와 무관하게 기존 backend service ID/poll sequence를 공통 수신에서 비교한다. 작은 poll 및 이미 retired된 service의 SPOT/comm.spot/receipt를 보존하고 다른 health 정보는 전달한다. effects는 rejected health로 leader receipt를 바꾸지 않는다. [공통 수신](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/frontend/src/domains/Observability/hooks/useSystemViewModel.ts:60). 원래 fingerprint: frontend/src/domains/Observability/hooks/useSystemViewModelEffects.ts:357:race-condition.
- 같은 poll의 snapshot/value age는 독립적인 monotonic floor로 화면 상태에서 정규화한다. 새 service poll0·새 정상 poll·유효한 age 갱신은 수용하고 기존 wall-clock/UNKNOWN 복구를 유지한다.
- legacy 이력 256개 상한은 최종 분기에서 추가 후 초과 시 가장 오래된 문자열을 제거하는 코드를 직접 대조했다. identity 없는 지연 중복 호환은 영구 integration 시험으로 확인했다.
- [영구 회귀](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/frontend/src/domains/Observability/hooks/healthPolling.integration.test.tsx:450): 세 race를 먼저 작성해 모두 red 확인. 각 race의 정상 복구와 인접5개(API/order/EX, same-poll source/value age, restart/retired service, identity 없는 legacy)를 검증했다. 수정 전3 FAIL→수정 후8 PASS 및 원래 probe3 PASS.

## Exploratory QA and Verification Results

| Field | Value |
|---|---|
| Date / branch / revision | 2026-10-09 KST / 위 branch/HEAD + [현재 source manifest](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/source-manifest.json) |
| Caller / authority / depth | review 승인 A의 local repair; permanent regression-before-repair; report/plan progress update; commit/deploy 제외 |
| Surfaces / scope | 실제 transport→view-model→hook→header, API와 BC/storage 공통 순서·기존 polling, production App 실제 Chrome |
| Runtime / native tools | Node22.22.2 / Vitest4.1.11 / TypeScript·ESLint·Vite 저장소 명령 / Bun1.3.11 evidence helper / native Chrome channel |
| Fixture ownership / destinations | 본 실행 ignored폴더; memory Axios/BC/storage와127.0.0.1 HTTP, owned Chrome context/tab. 실제 장비/외부 요청0. |
| Probe budget / guarded command time / stop reason | 승인 보완의 필수 검사·revalidation9개, 각60/120/180초 유한 timeout; 합계157.393초. 모든 scoped 최종 계약 PASS로 종료. |

### Contract outcomes

| ID | Exact command | Observed / exit | Classification | Evidence |
|---|---|---|---|---|
| 001 | `node node_modules/vitest/vitest.mjs run src/domains/Observability/hooks/healthPolling.integration.test.tsx -t health broadcast observation ordering` | Red:3 FAIL /1 (보완 전) | superseded | [receipt](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/001/receipt.json) · [stdout](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/001/stdout) · [stderr](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/001/stderr) |
| 002 | `node node_modules/vitest/vitest.mjs run src/domains/Observability/hooks/healthPolling.integration.test.tsx -t health broadcast observation ordering` | 8 PASS /0 | pass | [receipt](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/002/receipt.json) · [stdout](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/002/stdout) · [stderr](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/002/stderr) |
| 003 | `node node_modules/vitest/vitest.mjs run --config ../.tmp_ui_s1_verify/gstack-review-20261009-001/vitest.contract-probe.config.ts -t report-only ordering probe` | 원래3 PASS /0 | pass | [receipt](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/003/receipt.json) · [stdout](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/003/stdout) · [stderr](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/003/stderr) |
| 004 | `npm.cmd --prefix frontend run typecheck` | PASS /0 | pass | [receipt](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/004/receipt.json) · [stdout](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/004/stdout) · [stderr](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/004/stderr) |
| 005 | `npm.cmd --prefix frontend run lint` | 오류·경고0 /0 | pass | [receipt](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/005/receipt.json) · [stdout](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/005/stdout) · [stderr](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/005/stderr) |
| 006 | `npm.cmd --prefix frontend test` | 398 Vitest +9 Node PASS /0 | pass | [receipt](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/006/receipt.json) · [stdout](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/006/stdout) · [stderr](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/006/stderr) |
| 007 | `npm.cmd --prefix frontend run build` | build/Router graph PASS /0; 기존 zod 주석 경고 | pass | [receipt](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/007/receipt.json) · [stdout](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/007/stdout) · [stderr](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/007/stderr) |
| 008 | `node .tmp_ui_s1_verify/ordering-correction-20261009-001/browser-smoke.cjs` | setup 오류 /1;009로 대체 | superseded | [receipt](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/008/receipt.json) · [stdout](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/008/stdout) · [stderr](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/008/stderr) |
| 009 | `node .tmp_ui_s1_verify/ordering-correction-20261009-001/browser-smoke.cjs` | UI/native follower3/메뉴12 PASS /0 | pass | [receipt](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/009/receipt.json) · [stdout](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/009/stdout) · [stderr](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/.qa-evidence/009/stderr) |

최종 materialize **pass/open[]**. 001의 pre-repair red 및008의 setup 실패는 superseded 이력이며 exit1 원문을 보존했다. 001은 영구 test가 제품 수정 전에 실패했다는 근거이고, 008은 제품 결함으로 세지 않는다. 제품/영구시험 수정은002 시작 전에 끝났고002–009 동안 현재 입력은 동일했다. 이후 문서 갱신은 검증한 frontend 입력을 바꾸지 않는다. 기능 결과에 visual score를 합산하지 않는다.

### Browser results

| 항목 | 현재 결과 |
|---|---|
| URL / scope / framework | fixture가 매 실행 생성한 owned127.0.0.1 임시포트; React/Vite production dist, UI-S1 화면+메뉴+native follower |
| 화면 / 증거 | desktop1440×900 / mobile390×844; 캡처2개 실제 픽셀 확인. [desktop](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/desktop-under-range.png), [mobile](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/mobile-under-range.png) |
| 상태 / 메뉴 | 정상·under/over·timeout·복구·WAIT·UNKNOWN·Comm, 12개 진단 항목 fits·마지막 항목 접근 PASS |
| Native follower | 같은 ownedcontext의 실제 App follower탭에서 BC 성공→timeout→storage 옛 메시지 입력. legacy/source/leader identity 세 경우 DOWN 유지·정상 복구 PASS. changed leader는 합성 sender identity이며 물리 서버 선출 audit을 뜻하지 않음. |
| Console / network | JavaScript 오류0, 외부 요청0. [현재 JSON](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/browser-results.json) |
| Health Score | 전체 앱 시각·링크·성능·접근성 audit 미실행으로 전체 점수 미산정. scoped UI/native 기능 PASS와 독립 review coverage를 구분. |

### Discoveries and permanent tests

- [checkpoint 002](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/exploration-002.json) — red 후 승인 수정과8개 회귀
- [checkpoint 003](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/exploration-003.json) — 원래 probe 재검증
- [checkpoint 004](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/exploration-004.json) — 최종 타입 검사
- [checkpoint 005](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/exploration-005.json) — 최종 lint
- [checkpoint 006](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/exploration-006.json) — 전체 시험
- [checkpoint 007](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/exploration-007.json) — production build
- [checkpoint 008](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/exploration-008.json) — browser setup 오류 기록
- [checkpoint 009](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/exploration-009.json) — setup 수정 후 전체 native/UI 재검증

| 발견 | 영구 regression / native case | Red | Green+original+adjacent | 처분 |
|---|---|---|---|---|
| R1 지연 legacy 중복 | legacy-interleaved |001 /3FAIL |0028PASS,003원래3PASS,006전체398+9PASS,009native3PASS |A 승인 fixed |
| R2 source/leader 교체 | source-replacement/leader-replacement |001 /3FAIL |위와 동일; 새 poll 정상 복구도 PASS |A 승인 fixed |
| 같은 poll 경과·cache/value TTL·restart·API 순서·legacy fallback |같은 integration파일 인접5개 |건강한 계약 검증, 임의의 red 주장 없음 |002/006 PASS |승인 보완의 인접 검증 |

### Coverage limits and cleanup

- 독립 Review Army/native adversarial은 승인 계획이 subagent를 금지해 미실행. 부모의 최종 diff·직접 로직 및 replay 검토를 independent review로 대체해 표시하지 않는다.
- Windows review-start capture의 working-tree fingerprint 오류로 trusted start binding 없음. logger 기록은 unverified/incomplete. 이 상태에서 clean이나 전체 완료를 선언하지 않는다.
- backend identity 없는 구버전은 최근256개 fingerprint fallback과 기존 보수적 상태/age 처리 범위다. ID가 없으면 cross-source backend 관측 순서를 비교할 수 없고, 서로 다른 service의 ID 자체에는 시간 순서가 없다. 수용한 뒤 retired된 service는 지연 복귀를 차단한다.
- 첫 browser fixture setup 오류008은 원문/스크립트를 보존했다. 부분008 캡처를 별도 PASS 증거로 사용하지 않고 현재 캡처와 browser JSON은009의 유효한 전체 실행에 한정한다. 모든 ownedChrome tab/context/browser와HTTP서버는 finally에서 닫았다.
- 병합 전 npm run health 미재실행; 기존 Get-FileHash QA exit1은 과거 미해결. backend/Electron/QA 변경 없어 반복하지 않았으며 이전 일부helper PASS를 전체 PASS로 승격하지 않는다.
- 실 backend·SPOT/PLC·installer·서명·서버CSV 보존·운영 적용 미검증/미실행. commit/push/PR/운영 승격/롤백 기준 갱신 없음. 현재 운영복귀 commit4c97d4a00d79ae0d3da70b2e82af227345e21040과 installer증거 보존.
- [최종 QA evidence](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/evidence.json) · [source/fixture SHA256](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify/ordering-correction-20261009-001/source-manifest.json). 최초 검토 원문과 기존 승인 보완의 증거는 덮어쓰지 않았다.
