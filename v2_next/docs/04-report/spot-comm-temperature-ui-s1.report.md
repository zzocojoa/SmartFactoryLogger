# UI-S1(P2) 구현·로컬 검증 보고서

> 작성일: 2026-10-08 KST / 승인 보완 갱신: 2026-10-09 KST / 브랜치: `codex/spot-comm-temperature-ui-s1-20261008`
> 현재 상태: I2-A와 인접3건 보완 및 현재 로컬 검증 완료. frontend434/typecheck/lint/build·health002 exit0. 리뷰는 cycles3, INCOMPLETE/nonconverged, 실제 binding=changed다. 최종 독립 검토·후보·운영 적용은 남았다.
> 대상: 35959c41edee29573040d571ead952c073f1be13 + 승인된 frontend·QA 시험/runner 변경. 최종 구현 commit/installer SHA256 미생성.
> worktree: `C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next`
> [기준 계획](../01-plan/features/spot-comm-temperature-ui-s1-codex-spot-comm-temperature-ui-s1-20261008.plan.md) · [설계](../02-design/features/spot-comm-temperature-ui-s1.design.md) · [분석](../03-analysis/spot-comm-temperature-ui-s1.analysis.md)

## 1. 변경 결과

`/health.spot_temperature`를 상태 패널에 연결하여 **통신 정상과 온도 측정 불가를 분리**했다. fresh under-range는 `SPOT OK / Temp UNDER_RANGE / Comm OK`, over-range는 `Temp OVER_RANGE`로 표시한다. timeout 등 최신 통신 오류는 과거 성공이 남아 있어도 `SPOT DOWN`이며 이후 fresh 성공에서 복구한다.

통신·온도 배지와 툴팁/aria 라벨, 모바일 상세 메뉴를 추가했다. Temp는 Comm 집계에서 제외했다. 수신 metadata와 monotonic age를 구현해 갱신 중단·wall-clock 보정·헤더 재마운트의 기존 시험을 충족했다. 중복·지연 broadcast는 최초 후속 review에서 두 순서 결함을 확인했고(7절), A 승인 보완(8절) 및 후속 구조 정리(9절)에서 로컬 검증했다. 캐시는 기존 허용 여부와 TTL 안에서만 CACHED로 표시한다. 값·backend 정책·CSV·안전 gate는 변경하지 않았다.

## 2. 최초 검증 기록 (2026-10-08)

증거 폴더: `C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/.tmp_ui_s1_verify`

| 명령·검증 | 실제 결과 / exit | 증거 파일 |
|---|---|---|
| `npm --prefix frontend test` | node 9개 + Vitest 42파일/362개 PASS / 0 | frontend-test.log |
| `npm --prefix frontend run typecheck` | PASS / 0 | typecheck.log |
| `npm --prefix frontend run lint` | 오류·경고 0 / 0 | lint.log |
| `npm --prefix frontend run build` | PASS; production Router graph contract PASS / 0 | build.log |
| `node .tmp_ui_s1_verify/browser-smoke.cjs` | 실제 build+App, 1440px/390px, under/over/timeout/복구/WAIT/UNKNOWN PASS; JS 오류·외부 요청 0 / 0 | browser-results.json, browser.log, 캡처 2개 |
| `npm run health` | dependencies 14개, Electron 94개, frontend 단계, backend lint/mypy PASS; backend 880개(1 skip) 후 QA 오류 / **1** | health.log |
| `npm run health:qa:selftest` 재실행 | 같은 Get-FileHash 오류 / **1** | qa-selftest.log |
| Utility import 후 QA self-test 5개 | 동일 helper 5개 모두 PASS / 각 0 | qa-explicit-utility.json |
| 최종 diff·source hash·계획 복제 | diff whitespace 검사 PASS; backend diff 없음; 계획 두 위치 동일; 이전 준비 계획 hash 보존 | final-source-sha256.json, 기준 계획 |

최종 전체 frontend 검사는 마지막 source/test 변경 이후 재실행했다. build와 Chrome smoke는 마지막 production source 변경 이후 수행했다. 통합 health의 frontend 단계 이후 추가된 UI 보완은 최종 frontend 검사와 build/smoke로 다시 검증했다. 변경하지 않은 backend/Electron 시험은 다시 반복하지 않았다.

기본 Windows PowerShell `-File` 실행에서는 `measure_nsis_operational_ready.ps1:489`의 `Get-FileHash` 해석이 실패했다. 같은 호스트에서 `Import-Module Microsoft.PowerShell.Utility`를 먼저 실행하면 통과함을 확인했으나 정확한 자동 로딩 실패 원인은 확정하지 않았다. 기본 health 전체를 PASS로 표시하지 않는다. 별도 실행 예:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Import-Module Microsoft.PowerShell.Utility; & './scripts/measure_nsis_operational_ready.ps1' -SelfTest"
```

위 패턴으로 collect_nsis_startup_trace, run_closeout_hang_reproduction, verify_windows_release_signature, verify_windows_release_workflow_contract도 각각 검증했다. 운영 설치나 서버 작업을 실행한 결과가 아니다.

backend의 private F01 fixture 시험은 `TEMPERATURE_GOAL_PACKAGE` 미설정으로 skip 조건에 해당한다. 실장비 시험은 이 단위시험 결과에 포함하지 않는다. build의 기존 zod annotation 경고는 실제 로그에 보존했다.

## 3. 핵심 회귀 결과

- 정상·fresh under/over·empty/parse/out-of-range·verified-no-target: 통신/온도 개별 판정 확인.
- 성공 뒤 timeout/connection/http 오류 및 fresh 복구: 누적 오류·기존 성공이 최신 poll을 가리지 않음.
- source/health 갱신 중단, cache TTL 경계·만료, 누락/unknown enum/비정상 age: 오래된 정상 표시 차단.
- ±60초 시각 보정(정상·frozen source), remount, 중복 storage/BroadcastChannel, 전달 지연·잘못된 sent_at: age 보존/UNKNOWN 확인.
- cadence·backoff·visibility·no-overlap·startup overrun·unmount: 기존 통합시험 보존.
- 모바일의 Comm 축약과 상세 두 배지, 긴 라벨 비잘림, desktop aria/title: DOM 시험과 실제 Chrome 화면 확인. drawer 닫기는 기존 Escape 경로를 사용했다.

## 4. 증거 무결성

| 원문 파일 | SHA256 |
|---|---|
| health.log | `7DF583EEAA9CB9E7FC5C99DC4151EE8238D6E0B5EC68D954D7D24FD684D38550` |
| frontend-test.log | `250A7A0CE12224C1E010951E63CAE41004D50BD931D7D7CC67CE38A79C725BE6` |
| typecheck.log | `6FDF114D39A16B1E54838E5CE7BF75B333C2BDF5B24A8654C1D75ACBB03DB32D` |
| lint.log | `076C13C5C57ED04D43D5100D036AFB010783C66E95BB2A73B570807CF9C89C95` |
| build.log | `DFF5F9AD4206127AD3B8A7502A199291151B4FC66EBC628DB4C921B7EBF89BBF` |
| browser-results.json | `BC1B95EDE3856696BEE85086B71BD3AC922824AB81AA581B5DF6788233A94C85` |
| qa-explicit-utility.json | `CCC2498CA44DA13F60641E60BF3C3F5EF3781CCA94A980C72E28EF3D18B37852` |

최초 source SHA256은 `final-source-sha256.json`에 보존했다. 첫 승인 보완 source는 `correction/final-source-sha256.json`이며, 현재 후속 리팩토링 source는 9절의 새 manifest로 식별한다. 과거 manifest의 PASS를 다른 source에 자동 적용하지 않는다. installer 검증은 아직 수행하지 않았다.

## 5. 다음 단계와 한계

최초 설계 대조 10/10 판정은 직접 검토에서 두 누락을 발견해 재개방했고, 사용자 승인 보완 결과는 6절에 기록한다. 기본 health QA 자동 로딩 실패는 별도 조치가 남아 있으며, 승인된 UI 구현 범위 밖의 helper 변경은 하지 않았다. 후보 commit 확정·installer 생성/해시·패키지 동작·실제 backend/장비 API→화면·서버 적용과 다음 롤백 기준 갱신은 아직 수행하지 않았다.

운영 복귀 기준 `4c97d4a00d79ae0d3da70b2e82af227345e21040`, installer SHA256 `D453C1D17EFC706D3E21FE6F8D09F739F159EBF9F3F24F2EB2349E92D4EF84FB`를 보존한다. 새 후보 검증과 해당 승인 범위의 적용 확인 후에만 다음 롤백 기준을 갱신한다.

PDCA 관찰: 과거 유효 온도 시각은 현재 응답 성공과 다른 정보이므로 배지 판정 기준으로 재사용하지 않는다. UI 라벨은 단위시험뿐 아니라 실제 좁은 화면에서 확인하며, 전체 검사 명령의 실패와 우회 실행 결과를 별개로 기록한다.

## 6. 사용자 승인 보완과 최종 검증 (2026-10-09)

직접 검토의 기존 76개 PASS·추가 5개 FAIL(exit 1)을 근거로 수정 승인을 받았다. 기존 문서는 `correction/previous-report.md`에 보존했다.

- **broadcast:** 송신 hook의 source ID와 증가 sequence로 중복·역순을 제외한다. 벽시계 `sent_at`은 전달 지연에만 사용한다. 시계 역행 후 timeout·복구와 미래/누락/null/NaN/문자열 시각 후 정상 복구가 storage/BroadcastChannel 및 신구 메시지 형식에서 통과했다. 기존 메시지는 동일 payload 중복 제외로 호환하며 같은 시각의 다른 관측은 수용한다. effect 재시작에도 송신 sequence를 유지한다.
- **상세 메뉴:** poll/raw/source/age/device/shadow/origin/cache/최근 유효 온도·오류의 공통 진단 값을 정의 목록 본문에 표시한다. 툴팁과 본문 값을 대조하고 390px의 12개 항목 줄바꿈·마지막 항목 접근을 확인했다.
- 추가 시험의 초기 실패는 jsdom storage 이벤트의 대기 타이머였다. `Storage-impl.js`의 lock 삭제 이벤트를 확인하고, 이벤트 처리 후 잔여 타이머 0과 unmount 후 추가 요청 없음을 검증했다. 제품 polling 정책을 변경하지 않았다.

증거 폴더: worktree `.tmp_ui_s1_verify/correction`.

| 최종 명령 | 결과 / exit | 증거 |
|---|---|---|
| `npm --prefix frontend test` | node 9개 + Vitest 42파일/390개 PASS / 0 | frontend-test.log, frontend-test.exit.txt |
| `npm --prefix frontend run typecheck` | PASS / 0 | typecheck.log, typecheck.exit.txt |
| `npm --prefix frontend run lint` | 오류·경고 0 / 0 | lint.log, lint.exit.txt |
| `npm --prefix frontend run build` | PASS, Router graph 계약 PASS / 0 | build.log, build.exit.txt |
| `node .tmp_ui_s1_verify/correction/browser-smoke.cjs` | production build+App, 1440px/390px, 상태 전환·메뉴 진단·줄바꿈·접근 PASS; JS 오류·외부 요청 0 / 0 | browser.log, browser.exit.txt, browser-results.json, 캡처 |

최종 source 변경 후 검사했다. backend/Electron/QA에는 변경이 없어 이번에 전체 health를 재실행하지 않았다. 이전 health exit 1과 Utility import 후 결과는 최초 기록으로만 유지한다. build의 기존 zod 주석 경고는 로그에 보존했다.

| 이번 원문 | SHA256 |
|---|---|
| correction/frontend-test.log | `67E8792169B6F2313522C6FBFCA55E6EE0A02BA9E965B53D0B47BFDD7F17C365` |
| correction/typecheck.log | `6FDF114D39A16B1E54838E5CE7BF75B333C2BDF5B24A8654C1D75ACBB03DB32D` |
| correction/lint.log | `076C13C5C57ED04D43D5100D036AFB010783C66E95BB2A73B570807CF9C89C95` |
| correction/build.log | `1B635AB512329A4F712A52BB007B631FCE7807979E630EDCC47466DAAB625FCC` |
| correction/browser-results.json | `5113D533DEDEF71CC34C0181A84DDC23AF306CC2B24CF5DCB79889F44EB04719` |
| review/review-test.log (수정 전 5개 실패) | `84665A9B6F4193AE4274084A6993637078219EE26DE0AD83847B7DDDF3F3E8FD` |

추가 증거 해시는 `correction/evidence-sha256.json`, 현재 frontend 13개 source 해시는 `correction/final-source-sha256.json`에 기록한다. 승인 보완의 두 누락은 해소됐으며 변경은 여전히 미커밋이다. 실제 backend·장비·installer·운영 적용은 미검증/미실행이다.


## 7. 최초 review 판정 기록 (2026-10-09, A 보완 전)

- [이번 검토 보고서](../03-analysis/spot-comm-temperature-ui-s1-review-20261009.md): CRITICAL 2건, INCOMPLETE. latest timeout이 legacy 지연 중복 또는 source/leader 교체 후 옛 성공으로 가려진다.
- 현재 source 전체 frontend 390개 + Node 9개, typecheck/lint/build와 합성 HTTP production App의 desktop/mobile 메뉴 12개 항목은 재실행 exit 0. 추가 세 순서 검사는 backend identity/poll 필드를 갖춘 fixture에서 두 번 exit 1. 통과 범위와 실패 범위를 구분한다.
- 이번에는 제품 코드·영구 회귀를 수정하지 않았다. 제안은 기존 수신 타입/분기의 관측 순서 보완 및 세 영구 회귀이며 판단 대기다. source hash는 검토 시작부터 보고 직전까지 동일했다.
- 계획·분석·PDCA의 현재 완료 상태를 재개방했다. 6절의 과거 수정/검증 증거를 덮어쓰거나 새 실패를 PASS로 바꾸지 않는다.
- 독립 specialist/native adversarial 미실행과 review-start logger 오류는 coverage/binding 미확보로 기록했다. 병합 전 전체 health, 실장비·installer·운영 적용은 현재 미검증/미실행이다.


## 8. A 승인 R1/R2 순서 보완과 최종 결과

- backend의 기존 service ID/poll sequence를 공통 health 수신에 연결했다. 같은 service의 오래된 poll 및 이미 수용 후 retired된 service의 메시지는 SPOT/comm.spot/receipt와 leader receipt를 덮어쓰지 않는다. 다른 health 필드는 적용한다. 새 service poll0과 새 정상 poll은 수용한다.
- legacy 중복을 최근256개 payload 이력으로 제외한다. 같은 poll의 snapshot/value age를 독립적으로 정규화해 오래된 관측·캐시 값이 젊어지지 않게 한다. backend·값/TTL·안전 gate·CSV·polling/leader 정책 변경은 없다.
- 영구 세 회귀를 제품 수정 전에 추가해 모두 exit1을 확인했다. 수정 후 세 회귀+인접 다섯 사례8개와 원래 report-only probe3개 PASS. 전체 frontend398개+Node9개, typecheck/lint/build 모두 exit0.
- 합성 localhost API→production App Chrome 1440px/390px, 상세 메뉴12개, 실제 follower BC/storage handler의 세 순서 경우와 복구 PASS(exit0); JavaScript 오류·외부 요청0. changed leader는 합성 sender identity이며 실제 서버 선출 audit과 구분한다.
- 첫 browser fixture의 context setup 실패는 raw008에 보존했고 전체 재실행009 PASS. 관련 제품 입력은 최종검사 시작 후 바뀌지 않았다. 이번 실행 증거와 source/fixture hash는 `.tmp_ui_s1_verify/ordering-correction-20261009-001`에 있다.
- 확인된 로컬 로직 미해결0건. 독립 review/native adversarial 미실행·review-start binding 오류와 병합 전 전체 health 미재실행은 남는다. PDCA Check 유지. 미커밋; 새 후보 commit/installer·운영 승격 미실행. [현재 review](../03-analysis/spot-comm-temperature-ui-s1-review-20261009.md).


## 9. 후속 수신 로직 리팩토링과 최종 검증

사용자의 “이어서 코드 리팩토링 진행” 지시에 따라 계획10절을 먼저 저장하고 기존 브랜치에서 진행했다. [수신 helper](C:/Users/user/.codex/worktrees/spot-comm-temperature-ui-s1/SmartFactoryLogger/v2_next/frontend/src/domains/Observability/hooks/useSystemViewModel.health.ts)에 순서 판정·수신 시간 계산·상태 병합을 분리하여 hook의 React 상태 처리와 구분했다. refs는 즉시 갱신하고 functional updater는 순수 함수만 실행한다. 최신 timeout 유지·복구, SPOT/receipt 보존, legacy fallback, snapshot/value age 독립 floor 동작을 유지했다.

변경 전 기존 frontend13개에서 수신 hook1개만 변경, 나머지12개 동일, 새helper1개 추가다. effects·배지·시험·backend/값/TTL/안전gate/CSV/leader/backoff 변경은 없다. 기존 검증 fixture를 바이트 변경 없이 새 실행 폴더로 복사했다. [현재 source/fixture manifest](../../.tmp_ui_s1_verify/refactor-20261009-001/source-manifest.json)와 각 receipt의 candidateUnchanged 확인으로 최종 검증 입력을 구분한다.

| 명령·검증 | 최종 결과 / exit | 원문 증거 |
|---|---|---|
| `frontend에서 node node_modules/vitest/vitest.mjs run src/domains/Observability/hooks/healthPolling.integration.test.tsx -t "health broadcast observation ordering"` | 순서 회귀8개 PASS / 0 | [receipt](../../.tmp_ui_s1_verify/refactor-20261009-001/focused.receipt.json) · [stdout](../../.tmp_ui_s1_verify/refactor-20261009-001/focused.stdout.log) · [stderr](../../.tmp_ui_s1_verify/refactor-20261009-001/focused.stderr.log) |
| `npm.cmd --prefix frontend run typecheck` | PASS / 0 | [receipt](../../.tmp_ui_s1_verify/refactor-20261009-001/typecheck.receipt.json) · [stdout](../../.tmp_ui_s1_verify/refactor-20261009-001/typecheck.stdout.log) · [stderr](../../.tmp_ui_s1_verify/refactor-20261009-001/typecheck.stderr.log) |
| `npm.cmd --prefix frontend run lint` | 오류·경고0 / 0 | [receipt](../../.tmp_ui_s1_verify/refactor-20261009-001/lint.receipt.json) · [stdout](../../.tmp_ui_s1_verify/refactor-20261009-001/lint.stdout.log) · [stderr](../../.tmp_ui_s1_verify/refactor-20261009-001/lint.stderr.log) |
| `npm.cmd --prefix frontend test` | Vitest42파일/398개 + Node9개 PASS / 0 | [receipt](../../.tmp_ui_s1_verify/refactor-20261009-001/test.receipt.json) · [stdout](../../.tmp_ui_s1_verify/refactor-20261009-001/test.stdout.log) · [stderr](../../.tmp_ui_s1_verify/refactor-20261009-001/test.stderr.log) |
| `npm.cmd --prefix frontend run build` | 4577 modules; production Router contract PASS / 0 | [receipt](../../.tmp_ui_s1_verify/refactor-20261009-001/build.receipt.json) · [stdout](../../.tmp_ui_s1_verify/refactor-20261009-001/build.stdout.log) · [stderr](../../.tmp_ui_s1_verify/refactor-20261009-001/build.stderr.log) |
| `node .tmp_ui_s1_verify/refactor-20261009-001/browser-smoke.cjs` | 합성API→App desktop/mobile12항목·follower3경우/복구 PASS; JS오류·외부요청0 / 0 | [receipt](../../.tmp_ui_s1_verify/refactor-20261009-001/browser.receipt.json) · [stdout](../../.tmp_ui_s1_verify/refactor-20261009-001/browser.stdout.log) · [stderr](../../.tmp_ui_s1_verify/refactor-20261009-001/browser.stderr.log) |

원문 stdout/stderr 전체와 exit code를 확인했다. 기존 zod Rollup annotation 경고는 build stderr에 보존한다. 화면은 [desktop 캡처](../../.tmp_ui_s1_verify/refactor-20261009-001/desktop-under-range.png) · [mobile 캡처](../../.tmp_ui_s1_verify/refactor-20261009-001/mobile-under-range.png), 실제 관찰은 [browser 결과](../../.tmp_ui_s1_verify/refactor-20261009-001/browser-results.json)에 있다. changed leader는 합성 sender identity이며 실제 서버 leader 선출 검증은 아니다.

최종 [변경·보존 검증](../../.tmp_ui_s1_verify/refactor-20261009-001/finish.json)에 diff/문서 링크·기준 계획 두 사본·이전 브랜치/미커밋 상태·이전 PDCA28개 보존을 대조한다. [실행 증거 SHA256](../../.tmp_ui_s1_verify/refactor-20261009-001/evidence-sha256.json)으로 이번 로그와 source를 식별하며 이전 묶음의 바이트/해시를 다시 작성하지 않는다.

이번 수신 로직 리팩토링과 로컬 검증은 완료했다. 독립 review coverage/binding은 INCOMPLETE, PDCA Check/matchRate null을 유지한다. 병합 미요청으로 전체 health를 재실행하지 않았고 과거 QA exit1은 미해결이다. 실제 backend/장비·installer·서버·운영 적용은 미검증/미실행이며 운영/롤백 기준은 보존했다. 변경은 미커밋이다.


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
- [ ] 영구 회귀 red→최소repair→focused/original/adjacent green.
- [ ] 최종 frontend/build/Chrome/full health와 cycles3 INCOMPLETE 기록.
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
- [ ] 원래 core token의 cycles 3 INCOMPLETE 결과 종료 저장.
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


## 최신 상태 — 새 최종 review 완료 (2026-10-09T07:25:16.089Z)

새 직접 승인 invocation에서 미해결 결함0개, completed/converged=true/cycles0, 실제 core/native unchanged binding verified 및 review-read CURRENT다. 필수 health006 exit0(frontend434/backend880 기존skip1), build4577modules, 현재 App/follower3/compact24/menu9가 모두 PASS이며 제품571개는 동일하다. 이전 cycles3 INCOMPLETE 및 음성 검증은 당시 기록으로 보존한다. root Markdown34개 재독 완료; 외부 Claude Code 미설치/summary-only fixture coverage와 legacy fallback 한계는 유지한다. memo7줄 선택적 정리는 미적용이며 사용자Skip이 아니다.

단일 fresh 리뷰/QA 보고서는 [.tmp_ui_s1_verify/final-review-20261009-004/final-review.md](../../.tmp_ui_s1_verify/final-review-20261009-004/final-review.md), 실제 binding은 같은 폴더 core-finish-actual.json/native-finish-actual.json이며 필수 검증은 health/audit.json/input-audit.json/evidence.json이다. 기준 계획14.3절에 최신 증거/한계를 기록했다. 후보commit/installer/packaged API→UI와 승인서버 적용/회수/롤백기준 갱신은 다음 단계다. 현재4c97d4a 유지.
