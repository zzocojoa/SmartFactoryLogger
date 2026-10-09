# UI-S1(P2) 설계 대조 분석

> 2026-10-09 KST 승인 보완 재검증 / `codex/spot-comm-temperature-ui-s1-20261008`
> [설계](../02-design/features/spot-comm-temperature-ui-s1.design.md) · [계획](../01-plan/features/spot-comm-temperature-ui-s1-codex-spot-comm-temperature-ui-s1-20261008.plan.md)
> 현재 상태: 새최종독립review/fullhealth exit0·541d/08C 패키지/실제서버적용 확인 및65파일/128조건 검토와운영·다음rollback등록 완료. 설계10항목충족10/10=100%(UI-S1 범위). 정식QA·서명·전체성능/전수검증 및기존fallback 한계는유지한다.
> 범위: 계획의승인목표를완료했다. 아래 과거실패·미완료는당시기록이며 최신판정은이현재상태와마지막완료대조다. 실제장비관찰·패키지합성시험·원문hash검토의범위를구분한다.

## 1. 설계 항목과 근거

| 설계 항목 | 구현·검증 근거 | 결과 |
|---|---|---|
| 선택 API 타입·공통 수신 metadata | types, useSystemViewModel의 health/receipt 동시 저장; 직접 조회·storage/BroadcastChannel 시험 | 충족 |
| 통신·측정 분리 | buildSpotStatusBadges; 정상·under/over·invalid·no-target matrix | 충족 |
| 최신 오류 우선·복구 | A 승인 세 영구 회귀 red→green, 원래 probe 및 Chrome 실제 follower에서 최신 timeout 유지·새 poll 복구 PASS | 로컬 검증 충족 |
| age·TTL·invalid 입력 | 서버 age + monotonic elapsed; stale 즉시 반영, 5초 최소값, cache TTL 경계 시험 | 충족 |
| EX/LS·Comm 보존 | commBadges에 EX/LS/SPOT만 포함; fresh under/over에서 Comm OK | 충족 |
| 데스크톱·모바일·접근성 | Header aria/title + 메뉴 진단 본문, 520px 축약 CSS; Chrome 1440px/390px, 12개 진단 값 줄바꿈·마지막 항목 접근 확인 | 충족 |
| API→실제 view-model→hook→헤더 | Axios synthetic transport 88개 통합시험; production App 로컬 HTTP + native follower 세 순서/복구 | 로컬 검증 충족 |
| 벽시계·재마운트·broadcast | backend service/poll 순서와 최근256개 legacy 이력, same-poll 경과/캐시 TTL·restart·API 뒤 지연 수신·기존 시계/재마운트 시험 PASS | 로컬 검증 충족 |
| polling 정책 보존 | cadence, 5/10/20/50초 backoff, visibility, no-overlap, startup-overrun, unmount 시험 | 충족 |
| 최종 검사·계획 대조·보고 | 최종health006 exit0·frontend434+Node9/Chrome·새독립review binding verified/결함0·locked541d package·실제server128조건/65파일 및기준갱신 | 승인범위충족;기존제한보존 |

## 2. Check/Act에서 보완한 사항

- 직접 검토의 추가 5개 시험 FAIL(exit 1)은 벽시계로 새 broadcast를 버리는 분기와 메뉴 진단 본문 누락을 재현했다. 이 실패 원문은 `.tmp_ui_s1_verify/review/review-test.log`에 보존했다.
- 사용자 수정 승인 후 source ID + 증가 sequence를 health broadcast에 부여했다. `sent_at`은 지연 계산에만 쓰고 신규 메시지의 중복·역순은 source별 sequence로 제외한다. 기존 탭은 동일 payload 중복 제외로 호환한다. 미래 시각이 UNKNOWN을 만든 뒤에도 다음 정상 sequence/payload를 수용한다.
- 판정 함수의 진단 배열을 hook에서 헤더로 전달해 툴팁과 메뉴 본문이 같은 값을 표시한다. `dl/dt/dd` 본문과 긴 값 줄바꿈을 DOM/Chrome으로 검증했다.
- 영구 시험 28개를 추가했으며 기존 시험을 포함해 390개가 통과했다. 송신 source/sequence의 effect 재시작 유지와 unmount 후 추가 요청 없음도 확인했다. jsdom의 lock 삭제 storage 이벤트를 처리한 뒤 타이머 잔여 0을 확인했다.

- Chrome의 390px 상세 메뉴에서 긴 Temp 라벨이 잘려 온도 배지만 줄바꿈하도록 수정했다. 실제 `scrollWidth <= clientWidth`, 화면 캡처와 CSS 회귀시험으로 확인했다.
- 비정상 broadcast `sent_at`을 직접 조회의 지연 0으로 처리하지 않도록 유효한 숫자만 수용했다. 누락/null/NaN/숫자 문자열과 미래 시각에서 UNKNOWN을 확인했다.
- 오래된 성공 시각, 누적 실패 횟수, API 실패만으로 poll 결과를 바꾸는 분기는 제거했다. backend·Temperature 값/TTL·CSV·안전 gate 변경은 없다.
- PDCA JSON 갱신 과정에서 변환된 이전 날짜 표기를 원본 값으로 복구했다. 기존 모든 feature 기록의 deep equality를 확인했다.

## 3. 남은 항목과 검증 한계

- 이번 승인 보완 두 건은 최종 회귀시험과 UI 검증을 충족했다. 이전 기본 `npm run health`는 QA self-test의 `Get-FileHash` 로딩 실패로 **exit 1**이다. 명시 Utility import 후 동일 self-test 5개 exit 0과 구분한다. 이번에는 backend/Electron/QA 변경이나 병합이 없어 해당 전체 검사를 재실행하지 않았으며, 이전 결과를 현재 전체 health PASS로 표시하지 않는다.
- backend unittest는 880개 실행, 실패 0, skip 1이다. private F01 fixture 조건 시험은 `TEMPERATURE_GOAL_PACKAGE`가 없어 제외된다. 이 결과를 해당 private fixture PASS로 표시하지 않는다.
- browser smoke는 합성 HTTP 응답을 사용하는 실제 production frontend의 검증이다. 실제 backend 프로세스·SPOT 장비·installer·서버 수집/CSV 보존은 아직 관찰하지 않았다. 모바일 drawer는 기존 Escape 닫기 경로로 검증했다.
- 현재 변경은 worktree의 미커밋 상태다. 후보 commit/installer SHA256은 아직 없다. 운영본·롤백 기준과 승인 이력은 변경하지 않았다.

## 4. 증거

worktree의 `.tmp_ui_s1_verify`에 `frontend-test.log`, `typecheck.log`, `lint.log`, `build.log`, `health.log`, `qa-explicit-utility.json`, `browser-results.json`, `polling/results.json`, `final-source-sha256.json`과 데스크톱/모바일 캡처를 보존했다. 원문 로그와 source hash는 [구현 보고서](../04-report/spot-comm-temperature-ui-s1.report.md)에 식별한다.

이번 최종 검증은 그 아래 `correction/`의 frontend-test/typecheck/lint/build/browser 로그와 exit 파일, browser-results, 캡처, final-source-sha256/evidence-sha256을 사용한다. 최초 검증 source manifest와 로그는 그대로 보존한다.


## 5. review 재개방 기록 (2026-10-09, A 보완 전)

현재 입력을 다시 검증한 전체 frontend 390개 + Node 9개와 typecheck/lint/build·Chrome은 exit 0이나 새 순서 3개는 반복 exit 1이다. source/leader를 넘어선 관측 순서와 두 경로 legacy 중복은 아직 충족하지 않는다. 구현 범위를 임의로 늘리거나 제품을 수정하지 않았다. 구체적 원인·증거·영구 회귀 제안·리뷰 coverage 한계는 [이번 review](spot-comm-temperature-ui-s1-review-20261009.md)에 기록했다. 현재 matchRate는 재평가 전 null로 기록한다.


## 6. A 승인 순서 보완의 최종 분석

R1/R2를 공통 수신의 backend 관측 순서와 제한된 legacy 중복 이력으로 보완했다. 화면용 snapshot/value age floor는 독립적으로 정규화해 값의 오래된 경과가 fresh 통신을 STALE로 만들지 않는다. 오래된 SPOT/comm.spot/receipt는 보존하면서 다른 health 영역은 전달한다. 영구8개 추가 후398개+Node9개, 타입/lint/build와 Chrome 실제 수신 세 경우가 통과했다. 확인된 로컬 로직 미해결0건이며 독립 review·binding 및 운영 증거는 미확보다. 이전5절은 수정 전 실패 기록으로 유지한다. 현재 전체 matchRate는 null이며 PASS의 범위는 [현재 review](spot-comm-temperature-ui-s1-review-20261009.md)를 따른다.


## 7. 후속 리팩토링의 범위·동작 대조

기존 frontend13개 입력에서 useSystemViewModel.ts만 변경하고 같은 도메인에 순수 helper1개를 추가했다. 나머지12개와 영구 회귀시험, effects의256개 이력/source sequence, 배지 및 backend 계약은 동일하다. 순서 ref 갱신은 setter 이전에 유지하고 state updater 안의 코드는 순수 함수 호출로 바꿨다. 기존 accepted 반환과 두 age floor 식은 보존했다.

기존 순서8개 및 전체398개+Node9개, typecheck/lint/build를 최종 source에서 각각 exit0으로 확인했다. 기존 fixture를 바이트 변경 없이 복사해 production build의 합성 HTTP→App과 실제 follower BC/storage 세 경우·복구를 재검증했다. desktop1440/mobile390 메뉴12개 fits/마지막항목 접근, JS오류·외부요청0, exit0이다. 실행 로그·해시·기준 계획 사본/이전 작업공간 대조는 [보고서9절](../04-report/spot-comm-temperature-ui-s1.report.md#9-후속-수신-로직-리팩토링과-최종-검증)에 기록한다.

리팩토링을 새 독립 review 통과나 장비·설치본 검증으로 해석하지 않는다. phase Check/matchRate null, 과거 전체 health QA exit1, 미커밋·운영 미실행은 유지한다.


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

## 최신 완료 대조 (2026-10-09T14:02:03.420Z)

위10개 설계항목을최종변경과14.3/14.5/14.27–14.28의검증에대조해10/10충족을확인했다.
설계일치율100%는UI-S1의타입·수신순서·상태분리·age/TTL·Comm·UI·polling·보고범위다.
새independent review의completed/converged·unchanged binding/결함0,fullhealth exit0,
실제541d/08C locked패키지7전환과승인server설치/현재수집·CSV/config·UI·회수검토를확인했다.
현재운영본/다음rollback은541d/08C,4c/D453은교체전이전본으로보존한다.
실제후속검토128조건/실패0/exit0·65파일 manifest `8666510BABB8D0D6EAAF071DBAAD671554BC6EF782B745AC0723CF157150B92A`가근거다.
최초APPLY timeout/원인미확정·후속health223ms/성능gate미통과·정식QA/서명/
config/comparator/전체CSV·개별image전수검증미실행·과거drop15와기존legacyfallback을
설계일치율때문에PASS로바꾸지않는다. 과거cycles3 INCOMPLETE·FAIL은당시원문으로유지한다.
