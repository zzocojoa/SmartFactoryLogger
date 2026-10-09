# UI-S1(P2) 설계 — SPOT 통신·온도 상태 분리

> 작성일: 2026-10-08 KST / 브랜치: `codex/spot-comm-temperature-ui-s1-20261008`
> 기준: `35959c41edee29573040d571ead952c073f1be13`
> 계획: [브랜치 기준 계획](../../01-plan/features/spot-comm-temperature-ui-s1-codex-spot-comm-temperature-ui-s1-20261008.plan.md)
> 현재 상태: I2-A와 인접3건 보완 및 현재 로컬 검증 완료. frontend434/typecheck/lint/build·health002 exit0. 리뷰는 cycles3, INCOMPLETE/nonconverged, 실제 binding=changed다. 최종 독립 검토·후보·운영 적용은 남았다.

## 1. 목표와 구조

기존 `/health.spot_temperature`의 관측을 frontend 타입 → view-model → 상태 hook → 헤더로 전달한다. 순수 판정 함수는 `commBadge`와 `temperatureBadge`를 반환한다. EX·LS·SPOT만 Comm 집계에 포함한다. backend, Temperature 값, TTL, 수집·CSV·안전 gate는 변경하지 않는다.

## 2. 데이터 계약

`HealthSnapshot.spot_temperature`는 선택 필드다. poll, raw validity, freshness, device status, shadow status, snapshot/value age, freshness/TTL 임계값, cache 상태·origin·fallback 허용 여부와 최근 온도 성공/오류를 optional 타입으로 수용한다. 런타임에서 허용 enum과 숫자를 검증한다. 필요한 정보가 없거나 알 수 없는 enum/잘못된 age이면 UNKNOWN이며 과거 유효 온도 성공으로 정상 판정을 대신하지 않는다.

클라이언트 전용 `HealthReceiptTiming`은 `receivedAtMonotonicMs`, `ageAtReceiptMs`를 갖는다. 직접 조회의 요청→수신 monotonic duration은 표시 age에 보수적으로 누적하고, receipt의 추가 전달 지연은 0이다. broadcast는 `Date.now() - sent_at`의 유효한 비음수 지연을 사용한다. 적용 이후 경과는 `performance.now()`를 사용한다. health와 timing은 view-model에서 함께 저장하므로 헤더 재마운트로 age가 초기화되지 않는다.

health broadcast에는 송신 hook의 `source_id`와 증가 `health_sequence`를 함께 보낸다. 수신 시 source별 sequence를 보존해 두 전송 경로의 중복과 역순을 제외한다. `sent_at`은 전달 지연 계산에만 사용하며, 미래/비정상 시각을 UNKNOWN으로 표시한 뒤 다음 sequence의 정상 응답은 수용한다. source/sequence가 없는 기존 탭과의 호환은 탭별 동일 payload 중복 제외로 유지한다. 식별 정보가 일부만 있거나 비정상이면 수용하지 않는다. 송신 ID는 hook 수명에 묶고 effect 재시작에도 sequence를 이어 쓴다.

## 3. 판정 순서와 표시 계약

1. 필수 diagnostics/enum/timing 입력을 검증한다. 최초 `not_attempted`, `config_missing`은 age가 없을 수 있으며 WAIT/CONFIG로 분류한다.
2. 최신 poll 오류는 과거 성공보다 우선하여 DOWN으로 표시한다. 온도는 허용된 캐시가 TTL 안에 있으면 CACHED, 아니면 기존 stale 상태는 STALE, 나머지는 SOURCE_ERROR다.
3. backend stale 또는 `snapshot_age_ms + receipt_delay + monotonic_elapsed > max(5000, backend_threshold_sec * 1000)`이면 STALE다. 임계값 누락은 refresh 설정의 3배를 사용한다. invalid 임계값은 UNKNOWN이다.
4. fresh 성공은 통신 OK다. raw `valid_temperature`는 Temp OK, `verified_no_target`은 NO_TARGET, invalid sentinel의 under/over 장비 코드는 UNDER_RANGE/OVER_RANGE, 나머지 무효 응답은 INVALID다. NO_TARGET은 backend 분류이며 물리적 제품 부재를 추론하지 않는다.
5. 캐시는 cached origin + fallback 허용 + reused cache 상태 + 유효 value age/TTL을 모두 확인한다. snapshot 갱신이 중단되어도 TTL 안에서만 CACHED다. TTL 초과는 STALE이며 값이나 유효성을 승격하지 않는다.

| 통신 | 온도 | Comm 반영 |
|---|---|---|
| OK | OK / UNDER_RANGE / OVER_RANGE / INVALID / NO_TARGET | 정상 |
| DOWN | CACHED / SOURCE_ERROR / STALE | 오류 |
| STALE | CACHED / STALE | 경고 |
| WAIT / CONFIG / UNKNOWN | WAIT / SOURCE_ERROR / UNKNOWN | 기존 idle·경고 집계 |

API polling 실패는 SPOT timeout으로 바꾸지 않는다. 기존 polling 상태를 툴팁에 표시하고 마지막 관측의 age로 stale을 판단한다. 최신 fresh 성공은 누적 실패 횟수와 과거 오류가 남아 있어도 복구한다.

## 4. 화면과 접근성

데스크톱 헤더는 기존 SPOT 통신 배지와 별도의 Temp 배지를 표시한다. Temp는 기존 상태 색상을 재사용한다. 520px 이하에서는 기존 CSS에 따라 개별 배지를 숨기고 Comm만 축약하며 상세 메뉴에 두 상태를 표시한다. 텍스트와 aria-label을 제공한다. 판정 함수의 공통 진단 배열을 두 툴팁과 상세 메뉴의 정의 목록(`dl/dt/dd`)에 사용한다. poll/raw/source freshness와 age, 장비 코드, value origin/cache, 최근 유효 온도와 오류 이력을 본문에서 읽을 수 있게 하며 긴 값은 좁은 화면에서 줄바꿈한다.

승인 보완의 필수 시험: storage/BroadcastChannel의 역행 시계 후 timeout·복구, 미래/비정상 시각 후 복구, source/sequence 생성과 중복·역순 제외, 구버전 중복 호환, 메뉴 본문 진단 항목·390px 레이아웃. 기존 polling과 온도 판정 시험도 유지한다.

## 5. 구현 순서와 검증 체크리스트

- [x] 선택 API 타입과 view-model receipt metadata, 직접/broadcast 공통 적용 경로.
- [x] 순수 분류 함수: 정상·under/over·invalid/no-target, 최신 오류와 복구, 초기/설정/unknown.
- [x] snapshot age·TTL 계산: stale·health freeze·cache expiry·invalid 입력.
- [x] 상태 hook와 App 전달: 온도 분리, EX/LS/기존 집계 유지.
- [x] 헤더 두 배지, 모바일 상세, 텍스트·aria·툴팁.
- [x] transport → 실제 view-model → 실제 hook → 헤더 통합 회귀시험.
- [x] monotonic wall-clock 보정, 재마운트, 중복·지연 broadcast 회귀시험.
- [x] 기존 cadence/backoff/visibility/no-overlap/unmount 시험 유지.
- [x] frontend test/typecheck/lint/build 및 root health 실제 결과 기록.
- [x] 최종 diff/계획 대조, PDCA 분석·보고·계획 진행 상태 갱신.

## 6. 운영과 도구 제약

실장비·설치본 검증은 합성 API 통합시험과 구분한다. 현재 운영본과 installer 해시는 보존하며 UI 구현 승인만으로 설치·복구·기준 갱신을 실행하지 않는다.

PDCA design 도구는 feature-only 계획 경로를 고정 조회하여 브랜치명 파일을 찾지 못했다. AGENTS.md와 사용자 계획의 파일명 규칙을 우선하고, 실제 계획을 위 링크와 PDCA 상태에 등록한다. 중복 계획이나 도구 소스 변경 없이 스킬의 설계 템플릿 구조로 이 문서를 작성했다.


## 최초 후속 review의 미충족 기록 (2026-10-09, A 보완 전)

[검토 보고서](../../03-analysis/spot-comm-temperature-ui-s1-review-20261009.md)의 R1/R2에 따라 두 전송 경로의 legacy 지연 중복 및 source/leader 교체를 넘어선 최신 관측 보존 계약은 아직 충족하지 않는다. 기존 승인 보완의 sender별 sequence와 마지막 legacy payload 비교만으로 이 계약이 완성된 것으로 해석하지 않는다. 제품 수정은 하지 않았으며, backend가 이미 제공하는 service ID/poll sequence 활용과 제한된 중복 이력의 구체 설계는 추가 수정 선택 후 먼저 갱신한다.


## 승인된 R1/R2 수신 순서 설계 (2026-10-09)

A 선택에 따라 공통 health 수신이 backend service/poll identity를 판정한다. 작은 poll 및 retired service의 SPOT·comm.spot·receipt는 이전 값을 유지하고 다른 health 필드는 적용한다. 반환 false는 effects의 health/leader receipt 갱신을 막는다. 새 service poll0은 수용한다. 같은 poll의 snapshot/value age는 각각 monotonic floor로 화면용 상태에서 정규화하고 실제 지연 receipt는 보존한다. 값의 긴 경과가 통신 경과를 부풀리지 않는다. identity 선택 필드가 없는 구버전에는 기존 fallback을 유지한다. legacy fingerprint Set은 256개로 제한하며 source별 증가 sequence 검사는 그대로 둔다.

완료 조건은 계획 9절과 보고서의 세 회귀 및 인접 API/복구/restart/age/legacy 사례다. 제품 변경 전에 영구 회귀가 현재 제품에서 실패하는 것을 먼저 확인한다.


승인 보완 완료: 영구3개 red→green과 인접5개, 전체398개+Node9/typecheck/lint/build 및 Chrome handler3개·메뉴12개 PASS. 기존 backend service ID/poll sequence가 없는 계약의 cross-source 관측 순서는 보장할 수 없어 bounded legacy fallback과 기존 보수적 age/status 처리 범위로 기록한다. 전체 독립 리뷰·binding·health/운영 검증과 구분한다.


## 후속 수신 로직 리팩토링 설계 (2026-10-09)

useSystemViewModel.health.ts는 React·시계·API·storage 의존성 없이 관측 순서 판정, 수신 receipt 계산, health 병합을 담당한다. hook은 refs의 즉시 갱신, Date.now/performance.now 수집, functional state updater 실행을 맡는다. ref 변경을 updater로 옮기지 않아 연속 수신과 React 재실행에서 순서 판정이 바뀌지 않는다.

| 함수 | 입력·출력과 보존 계약 |
|---|---|
| assessSpotObservation | snapshot/직전 observation/readonly retired Set → 유효 identity·accepted·sameObservation. invalid/missing identity의 기존 호환 정책 보존 |
| buildHealthReceipt | sent_at/수신 wall-clock/monotonic clock → 기존 비음수 지연 또는 null. 직접 API는0, 미래·비정상 시각은 기존 UNKNOWN 계약 유지 |
| mergeHealthSnapshot | 이전 상태/snapshot/receipt/판정 → 새 상태. 거절 시 SPOT/comm.spot/receipt 보존, 같은 poll의 두 age floor 독립 적용 |

예: service-a의 poll10 성공 → poll11 timeout → 지연 poll10 성공이면 SPOT DOWN과 poll11 receipt를 유지하고 EX/LS 등 다른 health 정보만 적용한다. poll12 성공에서는 정상 복구한다. 기존 8개 순서 회귀와 전체398개+Node9개, production App Chrome follower 세 경우 및 메뉴12개로 구조 변경 후 같은 계약을 확인했다. 검증 근거는 보고서9절의 현재 source manifest와 실행 로그를 따른다.


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
