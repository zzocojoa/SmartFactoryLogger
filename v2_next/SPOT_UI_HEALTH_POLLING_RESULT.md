# SPOT 화면 상태 조회 보완 결과

2026-10-02. 로컬 코드 보완 및 검증 완료. 미커밋이며 후보 빌드·설치·서버 적용은 하지 않았다.

## 문제와 수정

정상 SPOT 수집을 합성한 경우에도 기존 UI는 `/health` 응답을 받은 뒤 5초를 기다려 다음 요청을 시작했다. Header는 보관한 마지막 성공 시각을 매초 평가하므로, 5초 stale 경계를 넘은 뒤 다음 health가 도착하기까지 짧은 `SPOT STALE / Comm 1!`을 표시할 수 있었다. 서버에서 관찰한 특정 경고의 원인까지 확정한 것은 아니다.

`useSystemViewModelEffects.ts`의 정상 health 조회만 **요청 시작 기준 2초 주기**로 변경했다. `performance.now()`로 응답에 소요된 시간을 빼고 다음 요청을 예약한다. 주기를 초과한 응답 뒤에는 2초를 더 기다려 밀린 요청을 연속 실행하지 않는다. 같은 effect 실행 중 visibility가 바뀌어도 health 요청을 중복 실행하지 않으며, cleanup 또는 조회 권한 상실 뒤에는 health 결과를 broadcast하거나 재예약하지 않는다.

유지한 계약:

- SPOT 배지의 기존 stale 임계값과 마지막 성공 시각을 변경하지 않는다.
- 실제 source 성공 시각이 멈추면 경고를 유지한다. 표시를 숨기거나 timestamp를 현재 시각으로 바꾸지 않는다.
- 장비 수집 주기, 정상 요청 timeout 2초, startup timeout 8초, stats 조회 5초는 그대로다.
- startup 실패 대기 5초와 정상 조회 실패 시 5·10·20·50초 backoff를 유지한다. publish 실패도 완료 후 전체 backoff를 기다린다.
- 기존 backend·저장·TTL·phase·metadata·worker 종료 계약은 수정하지 않는다.

## 작업본

- 경로: `C:\Users\user\Desktop\SmartFactory\SPOT_UI_REFRESH_FIX_R1\src\v2_next`
- 브랜치: `codex/spot-health-polling-20261002`
- 기반 HEAD: `08b2f918919f4a9047d71adcd999f532efb8f491` (R6 / 선행 복구 수정 포함)
- 변경: production effect 1개, 기존 unit test 1개, 신규 production UI 통합시험 1개, 이 문서.
- 과거 Documents 작업본의 미커밋 문서·미추적 파일, R6 및 이전 원본 checkout, 이전 재현 증거는 보존했다.
- 새 clone의 origin은 기존 로컬 R6 checkout이다. 향후 PR 작업 시 원격 저장소 설정을 확인해야 한다.

## 실제 검증

실제 `useSystemViewModel → transport → polling effect → DashboardHeader → useStatusPanel → badge`를 연결했다. Axios adapter·clock·visibility/storage·활성 공정 입력만 합성했다. UI 판정과 poll loop를 복사하거나 mock하지 않았다. Speed 2.8, Press 165, Count 5를 실제 store에 공급하되 실제 장비나 backend 수집은 실행하지 않았다.

| 검증 | 최종 결과 |
| --- | --- |
| 응답 0/100/450/1900ms, 초기 성공 시각 나이 800ms | 정상 DOM에 STALE 없음, 요청 시작 2초 간격 |
| 실제 source 시각 정체 후 복구 | 기존 임계값에서 STALE/Comm1, 새 성공 수신 후 OK |
| health 실패·복구 및 전체 backoff | 5/10/20/50초 유지, 복구 후 2초 정상 주기 |
| 숨김·복귀 및 응답 중 visibility 전환 | 중복 health 요청 없음, 다시 표시할 때 조회 복구 |
| startup overrun·벽시계 ±60초 보정 | catch-up burst 없음, monotonic 요청 간격 유지 |
| unmount 중 응답 완료 | health broadcast·재예약 없음, timer 및 예기치 않은 외부 요청 0 |
| follower·startup hidden 복구·publish 실패 | 관련 상태·timeout 인자·재시도 대기 유지 |
| 전체 프런트엔드 | **42 files / 320 passed / 0 failed / 0 skipped, exit 0** |
| frontend 선행 Node 스크립트 검사 | **9 passed / 0 failed / 0 skipped, exit 0** |
| TypeScript / ESLint | 각각 **exit 0** |
| Git diff / 신규 파일 | diff whitespace 오류 없음, 신규 시험·문서가 ignore되지 않음 |

최종 전체 명령(cwd는 작업본 `frontend`):

```powershell
npm test -- --config C:\Users\user\Desktop\SmartFactory\SPOT_UI_REFRESH_FIX_R1\offline-tests.config.mjs --maxWorkers=2
npm run typecheck
npm run lint
```

보조 config는 저장소의 Vite config를 그대로 가져와 외부 요청 차단 setup만 추가했다. `/api/log/status`는 메모리 응답이며 실제 요청을 보내지 않는다. 테스트 관찰은 50ms 해상도의 jsdom DOM이며 Chromium/Electron 실제 paint 측정은 아니다.

## 전후 기록과 검토

수정 전 기존 코드에서 목표 조건 12개 시험이 실패했다. 정상 지연 조건의 STALE, visibility 전환 중 중복 요청, cleanup 이후 health broadcast를 포함하며, 새 주기·복구 시점을 기대한 assertion 실패도 포함한다. 이를 12개의 현장 장애로 해석하지 않는다.

첫 수정 후 14개 중 13개가 통과했다. 나머지는 unmount 전에 정상 stats broadcast가 이미 있는데 저장소가 비었다고 기대한 fixture 오류였다. 기존 broadcast가 이후 변경되지 않는다는 assertion으로 교정하고 최초 실패 로그를 보존했다. 이후 예외 검토에서 publish 실패에도 성공 주기 계산이 적용되던 신규 문제를 실패 시험으로 재현했고, publish까지 성공한 뒤에만 정상 주기를 적용하도록 수정했다. 최종 전체 실행은 위 표와 같이 통과했다.

읽기 전용 독립 subagent가 production diff·신규 시험·예외 보완을 검토했고 새 P1/P2 차단 사항을 발견하지 못했다. 최종 전체 명령 실행 및 결과 확인은 main agent가 수행했다.

## 한계와 후속 단계

정상 health 조회 빈도는 지연 없는 기존 5초 대비 **2.5배**다. `/health`는 직접 PLC/SPOT 장비 읽기를 추가하지 않지만 frontend asset·실행파일 확인 등의 로컬 I/O가 있으므로 현장 부하 영향은 미검증이다. 실제 source 정체, OS 스케줄 지연, startup 지연, idle sentinel로 유효 성공 시각이 멈추는 상황까지 경고가 없어지는 변경은 아니다.

단일 요청 보장은 같은 effect 세대의 visibility/재예약 범위다. StrictMode·reconnect에 따른 서로 다른 effect 세대까지 전역 단일 요청을 보장하지 않는다. view-model의 `setHealth`는 effect 완료 검사보다 먼저 실행되므로 모든 늦은 state 갱신을 차단했다고 주장하지 않는다. timeout 인자·합성 실패는 검증했지만 실제 Axios timeout이나 서버의 `asyncio.to_thread` 취소는 시험하지 않았다.

backend/Electron 코드·공개 API·패키징 계약이 바뀌지 않아 이 단계에서는 backend/Electron 전체 suite와 후보 빌드를 실행하지 않았다. 실제 서버 경고 원인 확정, drain·worker 종료 확인 및 운영 승격은 남아 있다. 다음 단계는 변경 검토·커밋 후 새 후보의 격리 검증이며, 기존 후보의 현장 통과 기록을 새 diff의 검증으로 재사용하지 않는다.

원문·환경·실행 기록·전후 DOM·전체 diff·신규 파일 명세/해시는 `C:\Users\user\Desktop\SmartFactory\SPOT_UI_REFRESH_FIX_R1`에 있다. 이전 `SPOT_UI_POLL_REPRO_R1`의 77개 파일 manifest를 재검증해 변경 없음을 확인했다.
