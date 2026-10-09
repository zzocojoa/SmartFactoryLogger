# UI-S1 후속 독립 리뷰·수정 제안 — 2026-10-09

I2-A와 인접3건 보완 및 현재 로컬 검증 완료. frontend434/typecheck/lint/build·health002 exit0. 리뷰는 cycles3, INCOMPLETE/nonconverged, 실제 binding=changed다. 최종 독립 검토·후보·운영 적용은 남았다. 과거 제안·실패·당시 결과는 보존하며 현재 상태는 마지막 결과 절을 따른다.

- 브랜치: `codex/spot-comm-temperature-ui-s1-20261008`
- HEAD·origin/master: `35959c41edee29573040d571ead952c073f1be13` + 미커밋 변경.
- 작업 폴더: `C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next`
- 기준 계획: `C:/Users/user/Documents/GitHub/SmartFactoryLogger/v2_next/docs/01-plan/features/spot-comm-temperature-ui-s1-codex-spot-comm-temperature-ui-s1-20261008.plan.md`
- 원문 증거: [closeout 실행](../../.tmp_ui_s1_verify/closeout-20261009-001/merged-findings.json), [현재 입력 hash](../../.tmp_ui_s1_verify/closeout-20261009-001/review-input-manifest.json), [QA materialize](../../.tmp_ui_s1_verify/closeout-20261009-001/evidence.json).
- 아래 제안 코드는 승인 전 당시 기록이다. 사용자 A승인 및 실제 영구 회귀/보완 결과는 마지막 절과 계획12절에 있다. 제안 코드를 실제 실행 source와 혼동하지 않는다.

## 승인 전 제안 순서 (보존)

1. 아래 수정·조사 범위를 확인받고 기준 계획 두 사본을 먼저 갱신한다. 특히 처음 보는 backend 세대의 직접 API 확인은 follower의 기존 무조회 정책에 좁은 예외를 추가한다.
2. 기존 integration 파일에 새 영구 회귀를 먼저 추가하여 현재 제품의 실패를 확인한다. 확인된 결함을 보완하고 원래 probe·회귀·정상 복구를 다시 검증한다.
3. frontend 전체 test/typecheck/lint/build, 실제 Chrome API→화면, 기본 `npm run health`와 최종 독립 리뷰를 현재 소스에서 마친다.
4. 통과한 후보를 커밋하고 깨끗한 실제 HEAD에서 installer를 만든다. commit·SHA256·서명·패키지 동작을 확인한 뒤 승인된 서버 적용·CSV/설정/세대 확인·증거 회수·롤백 기준 갱신을 진행한다. 적용 확인 전에는 기존 `4c97d4a…` 복귀 기준을 보존한다.

## 발견과 구체적인 수정안

| ID | 판정·근거 | 문제 | 수정안·영향 |
|---|---|---|---|
| R3 | CRITICAL, confidence10; native006/007 동일 오류 replay | Node 환경 객체에서 `PSModulePath`만 삭제하여 `PSMODULEPATH`가 Windows 자식에 남고 Get-FileHash 로딩이 실패한다. | `scripts/run_qa_selftests.cjs:15`에서 key를 소문자로 비교하여 child env에 모든 표기 변형을 제외한다. 부모/사용자/머신 환경과 기존5개 PS helper 바이트는 보존한다. |
| R4 | CRITICAL, confidence10; native004/005 네 회귀 중3건 | 같은 poll의 경과가 6초를 넘은 뒤 잘못된 receipt timing을 거쳐 정상 timing을 받으면 경과 floor가 사라져 STALE→OK 또는 만료 캐시→CACHED로 역전한다. | `useSystemViewModel.health.ts:70`의 신뢰한 snapshot/value age floor를 invalid timing과 분리하여 보존한다. invalid timing 자체는 UNKNOWN으로 표시한다. 두 age와 monotonic anchor를 각각 유지하며 새 poll/service에서만 새 기준을 사용한다. |
| R5 | CRITICAL, confidence10; native004/005 네 회귀 중1건, backend 시작/완료 경로 직접 대조 | 첫 poll 번호1은 시작할 때 증가한다. 초기 not_attempted와 완료 timeout에 같은 번호가 들어갈 수 있어, 지연 초기 응답이 DOWN을 WAIT로 되돌린다. | `assessSpotObservation`의 즉시 ref 판정에 완료 관측 여부를 연결한다. 동일 service/poll의 완료 상태 뒤 not_attempted는 SPOT/comm.spot/receipt를 보존한다. 정상 초기 poll0·새 service·새 완료 poll은 수용한다. backend 변경은 제안하지 않는다. |
| R6 | CRITICAL, confidence9; red-team 소스 검토, native 실행 미재현 | 진단 enum이 객체이면 판정은 UNKNOWN이어도 details의 원본 객체가 `DashboardHeader.tsx:605`의 React 자식으로 전달된다. | `commBadge.ts:108`에서 외부 진단 문자열을 문자열인지 확인하고 비정상 값은 unknown/--로 만든다. 상세 값은 항상 렌더링 가능한 문자열이어야 한다. 정상 텍스트·오류/복구 계약은 보존한다. |
| R7 | CRITICAL, confidence9; native adversarial 소스 검토, runtime 미재현 | 현재 B를 받은 뒤 처음 보는 과거 A가 도착하면 A를 수용하며 B를 영구 retired로 기록한다. 이후 실제 B의 모든 새 poll이 거절된다. UUID 자체에는 순서가 없다. | `useSystemViewModel.ts:64`/effects에 수신 출처와 직접 요청 번호를 연결한다. 알 수 없는 broadcast 세대는 현재 SPOT을 보존하고 중복되지 않는 직접 health 확인 후 교체한다. 최신 직접 요청은 잘못 retired된 실제 service를 복구할 수 있고, 먼저 시작한 요청의 늦은 완료는 세대를 바꾸지 못한다. **기존 follower 정책 변경을 승인받아야 한다.** 확인 호출은 세대 변화에만 한정·중복 방지하며 정상 주기/leader/visibility/backoff를 보존한다. |
| R8 | CRITICAL, confidence9; native adversarial 소스 검토, runtime 미재현 | backend가 같은 poll을 3.5초에 stale로 표시한 뒤 지연된 fresh 표현을 받으면 numeric age는4초로 보존되지만 frontend 최소5초 때문에 SPOT/Temp OK로 되돌아간다. | 같은 service/poll·동일 freshness 정책에서 이미 관측한 stale 분류를 보존한다. 새 poll의 정상 완료는 복구를 허용한다. 서버 freshness·TTL·안전 gate 임계값을 바꾸지 않는다. |
| R9 | INFORMATIONAL, confidence10; design→native009·실제 픽셀 | 1440×768에서 메뉴 bottom1201px, 설정 top1047px/테마 top1147px; 1024×768에서도 설정 top800px/테마 top899px. body/menu scroll 후 좌표가 그대로라 마지막 제어에 접근할 수 없다. 모바일390×844는 내부 scroll로 접근 가능하다. | `App.css:716`의 desktop 메뉴에 헤더 아래 남은 viewport 기준 max-height와 overflow-y:auto를 넣는다. 기존 mobile fixed drawer를 보존한다. |
| R10 | INFORMATIONAL, confidence10; required native012·실제 픽셀 | 새 진단 dl/dt/dd가 rgb(230,237,243)을 상속하고 메뉴 배경은 rgb(255,255,255)이어서 텍스트가 매우 희미하다. | 새 `.mobile-menu-spot-details`에 해당 메뉴/앱의 테마 text token을 명시한다. light/dark/auto의 실제 computed color와 픽셀을 대조하며 전체 테마 체계를 리팩토링하지 않는다. |
| I1 | INFORMATIONAL / INVESTIGATE, confidence8; native adversarial 정적 추적 | 직접 API 수신은 delay0으로 receipt를 만들고, backend는 추가 상태 점검 전에 age를 계산한다. 구성/전송 지연이 화면과 follower의 관측/cache age에서 빠질 수 있다. | 기존 integration fixture에 지연 직접 응답을 추가해 먼저 재현한다. 확인되면 monotonic 요청→수신 duration을 표시용 보수적인 age 상한에 반영하고 follower 전달에서도 그 누적 경과를 보존하는 좁은 frontend 보완을 검증한다. duration은 backend가 늦게 캡처하면 과대평가할 수 있으므로 그 한계를 기록한다. backend timestamp/API schema 변경이 필요하면 다시 범위를 확인한다. |

동일 결함의 reviewer·QA 발견은 하나로 합쳤다. R4의 observation/cache 두 회귀는 각각 검증한다. R7의 세대 판정과 R5의 같은 poll 완료 판정은 서로 다른 계약이다. R6/R7/R8/I1을 runtime에서 재현했다고 주장하지 않는다.

## Discoveries and permanent tests — 제안 코드

R4/R5/R7/R8 및 I1의 추가 대상은 기존 파일
`C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/frontend/src/domains/Observability/hooks/healthPolling.integration.test.tsx`다.
아래 ordering 사례는 기존 describe의 `setupOrdering`/`currentHealth`를 사용한다. 각 사례의 finally에서 기존 unmount·timer flush·외부 요청0 확인을 유지한다.

### R4/R5: 이미 두 번 실패를 확인한 네 사례

현재 report-only transform의 **전체 제안 코드**는 [composition-probe.txt](../../.tmp_ui_s1_verify/closeout-20261009-001/composition-probe.txt)에 보존했다. 영구 파일에 같은 네 테스트를 추가한 뒤 원래 source에서 red를 다시 확인한다.

```tsx
// 각각 기존 integration harness에서 실제 수신→헤더를 검증한다.
// 1/2: stale 6s → 동일 poll future 또는 null sent_at → 정상 sent_at
//       UNKNOWN 구간 후에도 SPOT STALE 유지, 새 poll11만 OK 복구.
// 3: value age9s → 2s 경과 → future timing → 정상 timing
//    SPOT OK 유지, Temp STALE 유지; 만료 캐시가 CACHED가 되지 않음.
// 4: poll1 timeout → poll1 not_attempted/null ages
//    SPOT DOWN과 기존 receipt 유지, poll2 success로 OK 복구.
```

### R6: 객체 진단이 문자열 상세로만 전달되는 회귀

추가 파일은 기존
`C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/frontend/src/shared/utils/commBadge.test.ts`다. 실제 header 경로도 integration에 이어 확인한다.

```tsx
it('keeps malformed diagnostic details renderable while showing UNKNOWN', () => {
  const result = classify({temperature_status_shadow: {code: 'invalid'}} as unknown as Partial<SpotTemperatureHealth>);
  expect(result.commBadge.text).toBe('SPOT UNKNOWN');
  expect(result.temperatureBadge.text).toBe('Temp UNKNOWN');
  expect(result.details.every(({value}) => typeof value === 'string')).toBe(true);
});

it('renders UNKNOWN through the header for malformed diagnostic enums', async () => {
  const {view, send, label} = setupOrdering();
  try {
    await act(async () => {send(currentHealth({temperature_status_shadow: {code: 'invalid'}} as unknown as Partial<SpotTemperatureHealth>));});
    expect(label()).toBe('SPOT UNKNOWN');
    expect(view.container.querySelectorAll('.mobile-menu-spot-details dd')).toHaveLength(12);
  } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
});
```

### R7: 처음 보는 과거 service와 겹친 직접 요청

```tsx
it('keeps the live service after a first-seen predecessor broadcast', async () => {
  const {view, send, label} = setupOrdering();
  let live = currentHealth({spot_service_instance_id: 'service-b', spot_poll_seq: 50});
  apiClient.defaults.adapter = async config => ({data: live, status: 200, statusText: 'OK', headers: {}, config});
  try {
    await act(async () => {await latestVm.fetchHealth();});
    await act(async () => {send(currentHealth({spot_service_instance_id: 'old-service-a', spot_poll_seq: 100}));});
    await act(async () => {await latestVm.fetchHealth();});
    expect(latestVm.health?.spot_temperature?.spot_service_instance_id).toBe('service-b');
    live = currentHealth({spot_service_instance_id: 'service-b', spot_poll_seq: 51, spot_poll_status: 'timeout'});
    await act(async () => {await latestVm.fetchHealth();});
    expect(label()).toBe('SPOT DOWN');
    expect(externalNetworkAttempts).toBe(0);
  } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
});

it('does not let an earlier direct request retire the later confirmed service', async () => {
  const {view} = setupOrdering();
  const replies: Array<(data: HealthSnapshot) => void> = [];
  apiClient.defaults.adapter = config => new Promise(resolve => {
    replies.push(data => resolve({data, status: 200, statusText: 'OK', headers: {}, config}));
  });
  try {
    const earlier = latestVm.fetchHealth();
    const later = latestVm.fetchHealth();
    await act(async () => {replies[1](currentHealth({spot_service_instance_id: 'service-b', spot_poll_seq: 0})); await later;});
    await act(async () => {replies[0](currentHealth({spot_service_instance_id: 'old-service-a', spot_poll_seq: 100})); await earlier;});
    expect(latestVm.health?.spot_temperature?.spot_service_instance_id).toBe('service-b');
  } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
});
```

추가 인접 검증은 실제 새 service poll0→poll1, confirmation 실패 시 보수적 상태, 동시/중복 generation 메시지에서 확인 요청1개, known retired·legacy 호환, 기존 요청 중복 방지/visibility/leader/backoff다. 다른 UUID의 시간 순서를 추측하거나 sent_at의 벽시계만으로 backend 세대를 결정하지 않는다.

### R8: 같은 poll의 backend stale 분류 보존

```tsx
it('keeps observed backend STALE for a delayed fresh representation of one poll', async () => {
  const {view, send, label} = setupOrdering();
  try {
    await act(async () => {send(currentHealth({spot_snapshot_age_ms: 3500, spot_source_freshness: 'stale',
      temperature_status_shadow: 'stale', temperature_value_origin: 'none', spot_poll_freshness_threshold_sec: 3}));});
    expect(label()).toBe('SPOT STALE');
    await act(async () => {await vi.advanceTimersByTimeAsync(500); send(currentHealth({spot_snapshot_age_ms: 100,
      spot_poll_freshness_threshold_sec: 3}));});
    expect(label()).toBe('SPOT STALE');
    expect(view.container.querySelector('[aria-label^="Temp "]')?.getAttribute('aria-label')).toBe('Temp STALE');
    await act(async () => {send(currentHealth({spot_poll_seq: 11, spot_poll_freshness_threshold_sec: 3}));});
    expect(label()).toBe('SPOT OK');
  } finally {view.unmount(); await act(async () => {await vi.advanceTimersByTimeAsync(50);});}
});
```

### I1: 직접 응답 지연 조사

현재 polling describe의 기존 `exercise`를 사용한다. metadata 캡처 시 source age는 fresh 범위이고 캐시는 TTL 안이지만, 응답 도착 때는 둘의 실제 기한을 넘는 fixture다. adapter latency/timeout과 실제 HTTP 경로를 대조한 뒤 재현 결과에 따라 처분한다.

```tsx
it('accounts for delivery time before showing source freshness or usable cache', async () => {
  const r = await exercise({name:'direct-delivery-age', latencyMs:4000, initialAgeMs:1500, durationMs:4000,
    spotAt: () => ({spot_snapshot_age_ms:1500, spot_value_age_ms:8000,
      temperature_value_origin:'cached_observation', spot_cache_status:'reused',
      cache_fallback_allowed:true, spot_cache_expiry_threshold_sec:10})});
  const delivered = r.frames.find(frame => frame.at_ms === 4000);
  expect(delivered?.badge).toBe('SPOT STALE');
  expect(delivered?.temperature).toBe('Temp STALE');
});
```

### R3/R9/R10: 실제 진입과 브라우저 재검증

- R3 focused CLI: 현재 [qa-case-probe.cjs](../../.tmp_ui_s1_verify/closeout-20261009-001/qa-case-probe.cjs)의 전체 코드를 재사용해 `PSModulePath`, `PSMODULEPATH`, `psmodulepath` 각각의 오염된 child 환경에서 실제 `scripts/run_qa_selftests.cjs`와5개 helper를 실행한다. 현재006/007은 uppercase red다. 정상 native 환경과 첫 실패 exit 전달도 확인한다. 구현을 그대로 복제하는 새 모의 테스트 대신 실제 self-test 계약을 사용한다.
- R9/R10 native 회귀: 기존 [browser-menu-probe.cjs](../../.tmp_ui_s1_verify/closeout-20261009-001/browser-menu-probe.cjs)와 [readability probe](../../.tmp_ui_s1_verify/closeout-20261009-001/browser-readability-probe.cjs)를 새 실행 폴더에서 재검증한다. 실제 앱과 합성 API를 사용하고 desktop1440×768/1024×768/mobile390×844, light/dark/auto에서 마지막 버튼 접근·진단12행·읽을 수 있는 색상·SPOT/Temp/Comm를 확인한다. jsdom이 CSS 배치를 증명한다고 주장하지 않는다.

## 실행 결과·coverage·제한

| 실행 | 실제 결과 | 판정 |
|---|---|---|
| 기본 `npm run health:qa:selftest`, inherited/native 환경 | 기존5개 self-test 각각 통과, 두 진입 exit0 | 최초 QA 보완의 좁은 PASS. casing006/007 때문에 runner 전체 완성은 아님. |
| missing powershell.exe 경로 | child exit1 정상 전달 | 실패를 성공으로 삼키지 않음. |
| `npm run health` (PowerShell5.1 outer host) | exit1; dependencies14/Electron94/frontend398+Node9/typecheck/lint/backendruff/mypy9 PASS; backend880개 중 오류2·skip1, QA chained 단계 미도달 | 전체 FAIL. 기본 환경의 최종 전체 명령 미재실행. |
| 002 기존 ordering | 8 PASS / exit0 | 변경 없는 이전 회귀의 현재 PASS. |
| 004/005 composition | 각4 FAIL / exit1, 외부 요청0 | R4/R5 두 번 재현. |
| 006/007 QA casing | Get-FileHash CommandNotFound / 각exit1; raw stderr SHA256 동일 | R3 두 번 재현, parent env 보존. |
| 008 / 010 / 011 canary 두 메서드 | 직접 Python2 PASS/0 → native outer PS5 오류2/1 → child console UTF-8 동일2 PASS/0 | 오류 원인은 host 출력 encoding. backend/PS 원본 수정 없음. full health PASS 대체 근거로 쓰지 않음. |
| 009 Chrome | desktop2개 마지막 버튼 접근 FAIL, mobile PASS / probe exit1 | R9 실제 메뉴 결함. |
| 012 Chrome 읽기 | command exit0, near-white foreground/white background | R10 실제 readability 결함. 명령 성공과 표시 계약 실패를 구분. |
| QA materialize | 실행 exit0, **verdict fail / open[]** | open[]는 계약 PASS를 의미하지 않는다. |

001/003은 Vitest configuration/cwd setup 오류로 보존하고 제품 결함으로 세지 않는다. 실제 command argv·exit·stdout/stderr는 각 `.qa-evidence/NNN/receipt.json`과 스트림 원문에 있다. stdout만으로 실패 이유를 판정하지 않았다.

필수 체크포인트: [002](../../.tmp_ui_s1_verify/closeout-20261009-001/exploration-002.json), [003](../../.tmp_ui_s1_verify/closeout-20261009-001/exploration-003.json), [004](../../.tmp_ui_s1_verify/closeout-20261009-001/exploration-004.json), [005](../../.tmp_ui_s1_verify/closeout-20261009-001/exploration-005.json), [006](../../.tmp_ui_s1_verify/closeout-20261009-001/exploration-006.json), [007](../../.tmp_ui_s1_verify/closeout-20261009-001/exploration-007.json), [008](../../.tmp_ui_s1_verify/closeout-20261009-001/exploration-008.json), [009](../../.tmp_ui_s1_verify/closeout-20261009-001/exploration-009.json), [010](../../.tmp_ui_s1_verify/closeout-20261009-001/exploration-010.json), [011](../../.tmp_ui_s1_verify/closeout-20261009-001/exploration-011.json), [012](../../.tmp_ui_s1_verify/closeout-20261009-001/exploration-012.json).

testing/maintainability/security/performance/api-contract/design/simplification/red-team의 읽기 전용 독립 작업이 종료됐다. migration은 범위 밖이다. specialist 원래 findings는 critical4+informational1이며 점수1.5/10이다. 이는 현재 통과율이나 운영 QA 점수가 아니다. 부모·native 발견은 이 specialist 점수에 합산하지 않았다.

native in-host adversarial은 같은 Codex harness의 별도 context이며 독립 모델 identity는 미확인이다. test/fixture diff는 summary/stat 범위로만 검토했고 직접 테스트를 실행하지 않았다. optional Claude Code는 not_installed라 adversarial/structured 모두 unavailable; 시작하지 않은 pass에 token을 만들지 않았다.

실제 시작 token으로 parent/native 결과를 기록했다. start/end working-tree fingerprint는 `cce9fd9b8c7b8f5fead4641049d0eee3e8a061f9`로 일치했다. native의 완료된 정적 review는 binding verified, parent는 필수 probe 실패로 binding incomplete / completed:false / converged:false다. **시작 증거 오류는 해결했지만 전체 리뷰 완료는 아니다.** 이후 이 문서/계획 갱신은 그 review tree보다 새로운 문서 변경이며 최종 후보에서는 새 token·최종 재검증을 확보한다.

gstack 도구9a1dc81→54efba6 업데이트는 기존 auto_upgrade=true에 따른다. Codex host 등록은 갱신됐지만 전체 setup refresh는 다른 Claude checkout의 helper 문제로 exit1였다. 그 checkout을 자동 복구·초기화하지 않았다. Windows 절대 Git 경로 판정만 owned gstack-wtree에서 보완하고 실제 capture 성공을 확인했다. 제품/서버 변경과 구분한다.

현재14개 frontend raw hash는 이전 refactor build와 일치한다. 이번 Chrome 서버는 그 합성 fixture의 새 복사이며 실 backend/장비 결과가 아니다. fixture의 layout/SPOT 설정 부족에 따른404/오류 console 원문을 보존했으며 전체 앱 crash-free PASS로 보고하지 않는다. owned tab2는 닫았고 HTTP 서버는 quit/exit0으로 종료했다. 다른 탭·운영 프로세스는 조작하지 않았다.

## 수정 선택이 필요한 이유

[사용자가 지정한 review SKILL.md](C:/Users/user/.agents/skills/gstack/review/SKILL.md:936)는 “Any finding that has a `test_stub` field … is reclassified as ASK”라고 정한다. 위 새 회귀는 그 규칙에 따라 먼저 선택받는다. 또한 기준 계획은 “계획 변경이 필요하면 … 사용자 확인을 받은 뒤 계획 파일을 먼저 갱신”하도록 요구한다. R7의 세대 확인 호출과 I1이 확인될 때의 직접 응답 timing 전달은 기존 유지/제외 범위에 영향을 준다.

권장 선택은 **R3–R10 수정 + I1 재현·확인된 frontend timing 보완**이다. backend API·Temperature 값·서버 TTL·안전 gate·CSV 변경과 실제 통신 중단 시험은 이 제안에 포함하지 않는다. Skip을 선택하면 코드/영구 시험 수정 없이 선택만 기록하고 해당 결함을 미해결로 남긴다. 후보/운영 적용까지의 기존 승인은 계속 유효하나 이 새 결함 판정·검증을 먼저 마쳐야 한다.


## A안 승인 보완의 현재 결과 (2026-10-09)

사용자 원문 “A안(권장): 추가 발견 8건 수정 + 응답 지연 조사 및 확인된 문제 보완.”을 기준 계획12절에 저장한 뒤 보완했다. 현재 local source/실행 증거는 .tmp_ui_s1_verify/followup-correction-20261009-001이다. 이전 제안·실패·PASS는 각 당시 후보의 기록으로 보존한다. 수정 범위 선택을 다시 요청하지 않는다.

- R3: case-insensitive child PSModulePath 제거와 원본 byte 진단 소비. 세 환경명 × 기존QA5개·canary13개 exit0. 보호 PS helper 및 backend unittest runner 바이트 보존.
- R4/R5/R8: invalid receipt와 신뢰한 source/value floor를 분리하고 같은 poll 완료/stale 상태를 유지한다. 새 완료 poll에서 복구한다.
- R6: 비문자열 진단은 문자열 unknown/--로 표시하여 실제 header의 React 객체 자식 오류를 막는다.
- R7: broadcast 세대 변화는 단일 직접 API 확인으로 판정한다. 요청 시작 후보와 이후 후보를 분리하고256개로 제한한다. 최신 직접 요청/정상 복구를 보존하고 superseded는 재전송·실패 횟수를 바꾸지 않는다.
- R9/R10: 메뉴 scroll·하단80px 접근 여유와 가까운 theme text token. Native Chrome9개 viewport/theme 조합에서 마지막 제어의 실제 클릭·진단12개·대비13.37~15.80 PASS. AI launcher가 Auto 클릭을 가로챈 중간 실패도 보존했다.
- I1: 지연 직접 응답/실제 follower payload의 freshness 누락을 red로 확인한 뒤 monotonic duration을 보수적인 표시 age에 더했다. backend가 늦게 캡처하면 과대평가할 수 있고, backend API/TTL/안전 gate는 변경하지 않는다.

영구20개 red 및 focused118개/인접cadence6개 green, 원래composition4개 green, 전체frontend419+Node9, 실제 follower3개/복구/JS오류·외부요청0, production build4577 modules/Router PASS를 확인했다. 기본 full health003은 exit0/backend880(실패0·기존private fixture skip1)/QA5개였고, R9 최종CSS의 health004와 독립 리뷰는 진행 중이다. 현재 구현은 미커밋이며 installer·실장비·서버 적용·운영 승격·다음 롤백 기준 갱신은 미실행이다.

예: 현재B timeout → 처음 보는 과거A → 확인 중 새C가 도착하면 B 응답으로A만 제외하고C는 다음 확인에서 판정한다. 같은B poll의 invalid timing은 UNKNOWN 구간을 만들지만 신뢰한 경과 floor를 지우지 않는다. 새 정상poll에서만 신선한 관측으로 복구한다.


최종 CSS 상태 검증 기록: default-health-green-004의 기본 npm run health가 exit0으로 종료됐다. frontend419+Node9, backend880(기존private fixture skip1), QA5개와 모든 lint/typecheck 단계가 통과했고 입력571개가 불변이었다. 전체 원문 audit는 .tmp_ui_s1_verify/followup-correction-20261009-001/default-health-green-004/audit.json이다. 독립 재리뷰·후보 패키지·서버 적용·기준 갱신은 계속 미완료다.


## A안 적용 뒤 재리뷰 결과와 추가 I2 제안

A안의 R3–R10/I1은 승인된 범위이며 재승인 대기가 아니다. 재리뷰에서 R7의 성공 Diagnosis를 실패로 바꾸는 구현 회귀 및 R9/R10의 새 Temp 글자 대비·desktop 진단 폭을 추가 확인했다. 기존 성공/가독성 완료 조건을 복원하는 보완은 계획12.6에 저장했고 영구 Diagnosis red(exit1) → focused120 green(exit0)을 확인했다. 전체 최종 검사·운영은 아직 진행 중이다.

추가 I2는 별도 유지 범위 판단이다. receivedHealthSequencesRef Map은 새 송신 hook UUID마다 키를 추가하고 삭제하지 않는다(useSystemViewModelEffects.ts:365). retiredSpotServicesRef Set도 backend UUID 교체마다 누적한다(useSystemViewModel.ts:91). 메모리 성장 구조는 정적으로 확인했으며 실제 운영 누적량/메모리 압력은 미측정이다. 이를 측정된 장애로 보고하지 않는다.

### 구체적 권장 보완: 상한과 권위 있는 확인

- 두 identity 이력을 각각256개로 제한한다. 현재 backend service는 제외/퇴역하지 않는다. 같은 service의 낮은 poll, 완료→초기 역전, stale/floor 계약을 유지한다.
- retired-service 이력에서 빠진 과거 UUID는 현재 화면을 적용하지 않는 unknown service가 되며 기존 R7 직접 확인 경로를 통과한다. 최신 실제 backend GET이 판단하므로 evicted 옛 UUID가 현재 service를 뒤집지 못한다.
- source sequence에서 빠진 송신자를 단순 새 메시지로 수용하면 backend ID가 없는 구버전 지연 메시지가 장애를 OK로 되돌릴 수 있다. 따라서 이력 상한에 도달한 뒤 **알 수 없는 source의 메시지**만 화면 적용을 보류하고 직접 health를 단일 확인한다. 정상/기존 송신자는 계속 broadcast를 사용한다. 확인에 성공할 때만 최신 source/최대 수신 sequence를 제한된 이력에 등록하고 가장 오래된 항목을 정리한다. 같은 unknown source 중복은 하나로 묶고, 대기 중 도착 source 목록도256개 이하로 제한한다.
- 직접 확인은 기존 mounted·visibility·reconnect·latest-request guard와 내부 superseded-neutral을 따른다. 성공보다 늦은 기존 응답의 화면/broadcast 쓰기, 실패 응답의 정상화, backoff/leader 변경을 허용하지 않는다. 실패/hidden/reconnect 중에는 기존 SPOT/receipt를 보존하고 다음 허용된 메시지에서 재시도한다.
- 영향: 장기간 탭을 열어256개를 넘는 sender 세대를 관찰한 경우에 한해, 새 sender/evicted sender의 첫 재수신에서 follower가 health API를 조회한다. 이는 승인된 R7의 backend 세대 확인보다 넓은 예외이므로 구현 전 추가 범위를 확인한다. backend API·TTL·온도·안전 gate·CSV·운영 설정은 바꾸지 않는다.

수정 후보: frontend/src/domains/Observability/hooks/useSystemViewModel.ts, useSystemViewModelEffects.ts, 기존 healthPolling.integration.test.tsx 및 effects 시험, 기준 계획/PDCA. 현재 I2 제품·영구 시험은 수정하지 않았다.

### 제안 회귀 코드 (미작성·미실행)

기존 frontend/src/domains/Observability/hooks/healthPolling.integration.test.tsx의 실제 adapter/view-model/StorageEvent 및 fake-clock setup을 이어 사용한다. 다음은 의도를 명시한 Vitest skeleton이며 PASS 증거가 아니다.

```tsx
it('preserves latest timeout after more than 256 sender generations and an evicted legacy replay', async () => {
  // 실제 hook에 서로 다른 source_id/health_sequence를 가진 257세대 이상을 전달.
  // 최신 timeout을 유지하고, backend identity 없는 첫 세대의 옛 OK를 재전달.
  // capacity miss는 broadcast를 적용하지 않고 실제 adapter GET 하나로 확인.
  // 최신 SPOT DOWN/온도 상태·receipt/broadcast 순서와 실제 조회 횟수를 확인.
});
it('deduplicates capacity confirmations and retries failure without declaring success', async () => {
  // 미완료 확인에 같은/다른 sender 중복, 확인 실패, hidden/reconnect,
  // 뒤늦은 이전 응답과 최신 정상 복구를 실제 transport/clock으로 검증.
});
it('does not revive an evicted retired backend service after repeated restarts', async () => {
  // 실제 backend UUID를257개 넘게 확인한 뒤 최초 퇴역 UUID의 OK를 재전달.
  // 최신 timeout을 보존하고 실제 backend 확인 후에만 현재 세대를 수용.
});
```

상한은 독립 resource/capacity 검증으로 확인하며 제품 공개 API에 시험 전용 크기 필드를 추가하지 않는다. 새 회귀의 실패를 먼저 입증하고 기존 legacy/source/leader·unknown-generation·지연/초기/복구/Diagnosis·기본 health/native 브라우저 및 fresh 독립 review를 다시 실행한다.

선택 A: I2 상한/권위 확인까지 추가 보완(권장); 선택 B: 코드/영구 시험 변경 없이 I2를 미해결 정보 항목으로 보존. B는 explicit Skip이며 review clean으로 보고하지 않는다. 원래8건과 I1 승인·후보/운영 적용 승인 자체는 유지한다.


## 현재 인접 보완·최종 로컬 검증 결과 (2026-10-09)

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


### 12.11 현재 운영본의 읽기 전용 원격 사전 확인

- Chrome 원격 데스크톱의 DESKTOP-Extrusion 연결에서 실제 운영 대시보드와 localhost:8000/health를 확인했다. RDP alias와 OS hostname의 대응은 이번 화면에서 별도 검증하지 않았다. 2026-10-09T03:16:46.726Z 및03:21:48.412Z body 시각의 두 응답은 commit4c97d4a00d79ae0d3da70b2e82af227345e21040/app1.0.26/frozen/packaged-resources이며 frontend_static_ready와 running/driver/thread가 true다. 신규 후보가 적용된 결과가 아니다.
- 같은 SPOT service와 logger service를 유지하며 약301.686초 사이 poll83113→83415(+302), API가 보고한 CSV rows359687→360967(+1280)를 확인했다. current CSV는 Factory_Integrated_Log_v2_20261009_000000.csv다. 원본 CSV 파일 읽기·무결성/프로세스 소유자/설정 파일 hash 검증은 수행하지 않았으므로 API counter 증가를 그 검증으로 확대하지 않는다. 기존 config_drift_detected_count1, previous_poll/fact_only 진단의 한계는 유지한다.
- 원문 health.json(6360bytes/SHA256128e43508052e7bbcc1ba0ea4bd140ede7d64c77cce0b3ff97216349c60567d2), health-002.json(6361bytes/SHA25695fa05ba2b949b606a1f7ec0fda9c00517f927863d2a70cbbc174158fd1af7c9)을 서버 Edge의 SaveAs로 Z:/SmartFactory/20261009/return/S1_PREFLIGHT_20261009_R1에 저장하고 개발 PC records/server-preflight-001로 회수했다. 두 위치의 byte SHA256이 일치하고 strict UTF-8/JSON 파싱을 확인했다. 서버 로컬에서 hash 명령을 실행한 증거는 아니다.
- 조회용 새 Edge 창을 닫고 Running 대시보드 복원을 실제 화면과 remote-dashboard-restored.png로 확인했다. installer/수집 정지/장비·작업 설정/보안 설정/운영 baseline 변경은 수행하지 않았다. 최초 URL 입력의 colon→semicolon 검색 오류는 바로잡은 뒤 실제 localhost 응답을 저장했으며 검색 화면을 API 증거로 쓰지 않는다.
- evidence: Desktop/SmartFactory/S1_PKG_20261009_R1/records/server-preflight-001의 health-audit.json, ui-observation.json, 두 원문 JSON과 remote-health.png/remote-dashboard-restored.png. shared return 위치는 원문 회수 목적이며 서버 최종 candidate 전달 완료를 뜻하지 않는다.
- 승인8건/I1 로컬 검증은 유지한다. I2 직접 선택/추가 구현·시험 또는 explicit Skip, fresh 최종 독립 review, clean candidate commit·installer/API→UI·승인 운영 적용/회수·다음 rollback baseline은 여전히 미완료다.


## Pre-Landing Review: 0 issues (0 critical, 0 informational) — INCOMPLETE

I2-A와 인접 3건 보완 및 현재 로컬 검증 완료. frontend 434개/typecheck/lint/build·health002 exit0. 리뷰는 cycles 3, INCOMPLETE/nonconverged, 실제 binding=changed다. 최종 독립 검토·후보·운영 적용은 남았다. 2026-10-09T06:19:32.978Z

현재 확인한 결함을 보완한 로컬 결과와 최종 독립 PASS는 구분한다. 새 리뷰를 수행하지 않은 부분은 coverage gap이며, 기존 16개 승인 finding의 fixed action을 계속 보존한다. 사용자 Skip은 없다.

### Fixed + test

- [FIXED + TEST] [CRITICAL/confidence10] useSystemViewModelEffects.ts:379 — API 시작 이후 같은 source의 높은 sequence를 이전 응답이 소비함 → 요청 시작 sequence 고정·arriving 후속 API 확인·보류 payload 미적용. healthPolling.integration.test.tsx:950의 I2a legacy/identified 2개 red→green.
- [FIXED + TEST] [CRITICAL/confidence10] useSystemViewModel.health.ts:47 — 완료 CONFIG가 지연 초기 WAIT로 교체됨 → config_missing을 완료 관측으로 분류. healthPolling.integration.test.tsx:985 R5a에서 receipt/comm 보존 및 다음 poll 복구 red→green.
- [FIXED + TEST] [INFORMATIONAL/confidence10] DashboardHeader.tsx:489 — 521–768px에서 온도 상태가 보이지 않음 → compact 상태 텍스트와 App.css:355/937/945 줄바꿈. DashboardHeader.test.tsx:179 R10b red→green; 실제 521/640/768px 24개 조합 완전 표시 PASS.
- 기존 승인 R3–R10/I1·R7a/R9a/R10a/I2의 13개 fixed action과 원래 fingerprint/증거를 actual-logged-cycle3-record.json에보존했다. 현재 전체 검사와 원래 composition/Chrome 회귀로 재검증했고, 최종 zero-edit 검토 완료를 대신하지 않는다.

## Exploratory QA and Verification Results

| 현재 검증 | 실제 결과 | 현재 범위·한계 |
|---|---|---|
| 새 영구 red / focused green | red4개FAIL/exit1 → focused 109개PASS/exit0 | 기존 실제 hook/Header 시험, focused 이후 CSS만 변경됨 |
| npm run health002 | exit0; frontend 434개+Node9/dep14/Electron94/typecheck/lint/ruff/mypy9/backend880/QA5 | 기존 private fixture skip 1개. 동일 소스 첫 health의 backend timeout 1개 FAIL은 보존·원인 미확정 |
| production build002 | exit0 /4577modules/Router contractPASS | 실제 installer 빌드 검증과 구분 |
| API→production App / follower | 상태 7개·follower 3경로·복구 PASS/exit 0, 격리 JS 오류 0·외부 요청 0 | 합성 로컬 HTTP이며 실장비/운영 검증 아님 |
| compact / 배지matrix / 메뉴 | 24/54/9개 조합 PASS/exit 0; 진단 12행·마지막 4개 hit/click | Auto의 실제 theme는 day; 공유 console과 격리 JS 오류를 구분 |
| 원래 probe / composition | capacity1/config1/composition4 PASS/exit0 | probe 이후 CSS 변경은 현재 Chrome 전체 영향 검증으로 확인 |
| 원래 core token 종료 | exit0; cycles 3/completedfalse/convergedfalse/bindingchanged | 최종 zero-edit 리뷰 미실행; 4번째 pass 없음 |

- 현재입력 571개중이번인접보완6개외 565개동일. API/수집/Temperature값/TTL/gate/CSV/장비 설정/운영 기준은 바꾸지 않았다. 사용한 owned server들은 quit 정상 종료/CIM 부재 확인, owned 탭만닫았다.
- 식별 정보 없는 legacy는 승인 설계의 호환 fallback/cross-source 순서 미보장 한계를 유지한다. mixed native→no-ID report-only DOWN→OK/exit 1을 성공 보장이나 새 Skip으로 바꾸지 않는다.
- 모든 8개 specialist와 native가 종료됐지만 수정 후 최종 독립 검토가 없다. native는 같은 Codex 환경이며 외부 모델 증거가 아니다. Claude Code 미설치/외부 structured 미실행·core의 과거 root Markdown 전체 미재독·backend timeout/이전 OOM 원인 미확정·후보 installer/운영 미검증을 유지한다.
- review SKILL.md Step5.8의“거듭 수정 최대 3회, converged:false 저장 후 STOP”을 따른다. 다음작업은새 최종 review→clean후보commit/lockedinstaller검증→승인서버적용/증거 회수→롤백기준갱신이다. 현재4c97d4a를복귀기준으로보존한다.
- 결과 원문: .tmp_ui_s1_verify/review2-correction-20261009-001/local-result.json, default-health-001/actual-result-audit.json, default-health-002/audit.json, final-review-20261009-002/actual-logged-cycle3-record.json, .tmp_ui_s1_verify/final-review-20261009-002/core-finish-file.receipt.json.


## 최신 상태 — 새 최종 review 완료 (2026-10-09T07:25:16.089Z)

새 직접 승인 invocation에서 미해결 결함0개, completed/converged=true/cycles0, 실제 core/native unchanged binding verified 및 review-read CURRENT다. 필수 health006 exit0(frontend434/backend880 기존skip1), build4577modules, 현재 App/follower3/compact24/menu9가 모두 PASS이며 제품571개는 동일하다. 이전 cycles3 INCOMPLETE 및 음성 검증은 당시 기록으로 보존한다. root Markdown34개 재독 완료; 외부 Claude Code 미설치/summary-only fixture coverage와 legacy fallback 한계는 유지한다. memo7줄 선택적 정리는 미적용이며 사용자Skip이 아니다.

단일 fresh 리뷰/QA 보고서는 [.tmp_ui_s1_verify/final-review-20261009-004/final-review.md](../../.tmp_ui_s1_verify/final-review-20261009-004/final-review.md), 실제 binding은 같은 폴더 core-finish-actual.json/native-finish-actual.json이며 필수 검증은 health/audit.json/input-audit.json/evidence.json이다. 기준 계획14.3절에 최신 증거/한계를 기록했다. 후보commit/installer/packaged API→UI와 승인서버 적용/회수/롤백기준 갱신은 다음 단계다. 현재4c97d4a 유지.


## 최신 상태 — 후보 패키지 검증 완료 (2026-10-09T07:59:38.857Z)

새review 결함0/최종health exit0에 이어 build commit541d701d544eea6a8a4e4836047077eaf9cfaf30의 locked 패키징과 실제packaged API→UI7전환이 PASS했다. installer163826264bytes/SHA256 08C061EE35A1A01788F05B00EE7395AA40774150C92C06726A92F3DF1BF75C3C/NotSigned, 추출payload1771개·내/외부frontend50개가 실제runtime package와 동일하다. 제품571개 유지, owned프로세스 정상종료/CIM부재를 확인했다.

[패키지검증보고서](C:/Users/user/Desktop/SmartFactory/S1_PKG_20261009_R1/records/candidate-final-validation-001/candidate-package-validation.md), 기준계획14.5절 및 같은records raw/receipts가 근거다. 설치실행·서버적용·실장비/CSV/설정보존·결과회수·운영기준갱신은 미완료이며4c97d4a를 유지한다. metadata후속commit은541d build commit과 구분한다.
