# Gap Analysis: spot-request-churn-remediation

> Date: 2026-07-24 | Design: `docs/02-design/features/spot-request-churn-remediation.design.md`
> Check commit: `4e3719e` | Verdict: **Act required / package blocked**

---

## Match Rate: 92%

## Summary

설계의 로컬 검증 항목 50개 중 46개가 구현 및 검증 증거와 일치한다. Frontend는
완료 직후 재요청을 제거하고 설정된 1~10초 cadence를 사용하며, 정상 timer와 기존
500/1000/2000ms retry, manual refresh, visibility 및 unmount lifecycle을 상호 배제한다.

Backend는 기존 `httpx.AsyncClient`, payload validation, timeout 및
`_spot_device_request_lock`을 유지하면서 process-local JPEG cache와 shared refresh
task를 추가했다. 실제 HTTP/1.0 close loopback에서 cold caller 20개와 만료 후 caller
20개는 각각 upstream 요청 1개로 합쳐졌고, fresh caller 100개는 추가 upstream 요청
없이 cache에서 처리됐다.

그러나 공식 repository health의 mypy 단계가 2건 실패했으며, cache 실패 후 recovery와
refresh task 교체 race에 대한 명시적 자동 테스트가 없다. 또한 lock 진입 전에는 stale였지만
lock 안에서 fresh cache를 발견한 caller가 `image_cache_hit_count`와
`image_coalesced_waiter_count`에 동시에 포함된다. 이 caller는 실제 shared task를 기다리지
않으므로 설계의 waiter 의미보다 넓게 집계된다.

따라서 구조적 match rate는 90% 이상이지만 production package gate는 통과하지 못했다.
이번 Check에서는 installer를 생성하지 않으며, Act에서 아래 네 항목을 수정한 뒤 전체
Check를 다시 수행해야 한다.

## Match Calculation

| 영역 | 전체 | 일치 | 판정 |
|---|---:|---:|---|
| Frontend policy 및 lifecycle | 18 | 18 | 일치 |
| Backend cache 및 concurrency | 20 | 17 | 3개 gap |
| API, observability 및 security | 8 | 8 | 일치 |
| Local quality 및 protocol gate | 4 | 3 | mypy 실패 |
| **합계** | **50** | **46** | **92%** |

## Implemented Items

- [x] 최초 image 요청은 즉시 수행하고 정상 표시 완료 뒤에만 다음 timer를 예약한다.
- [x] `refresh_interval`의 invalid 값은 3초, finite 값은 1~10초로 정규화한다.
- [x] 정상 timer, 자동 retry 및 manual refresh가 동시에 실행되지 않는다.
- [x] hidden 화면과 unmount에서 정상 timer를 해제하고 visible 복귀 시 한 번 재개한다.
- [x] Blob URL, 마지막 정상 frame, payload validation 및 기존 오류 계약을 유지한다.
- [x] cache entry는 JPEG 한 장과 epoch, monotonic, upstream latency만 process memory에 보유한다.
- [x] monotonic strict TTL 경계와 clock anomaly safe miss를 구현했다.
- [x] cold/expired concurrent caller는 하나의 shielded shared refresh task를 사용한다.
- [x] caller cancellation이 shared refresh를 취소하지 않으며 shutdown은 bounded하다.
- [x] refresh 실패 시 expired cache를 HTTP 200 stale fallback으로 사용하지 않는다.
- [x] upstream 성공 한 번당 image capture enqueue도 한 번만 수행한다.
- [x] `X-Spot-Image-Age-Ms`와 source/captured-at/upstream-latency 계약을 제공한다.
- [x] downstream/upstream/cache/leader/waiter/success/failure/cache-age 누계를 제공한다.
- [x] query parameter를 통한 TTL, upstream URL, force refresh 및 source port 주입을 추가하지 않았다.
- [x] raw socket, source-port allocator, custom HTTP parser 및 Windows network 변경을 추가하지 않았다.
- [x] DB, CSV, config 및 image fact schema migration이 없다.
- [x] HTTP/1.0 + Content-Length + server close loopback에서 freshness window당 upstream 1회를 확인했다.
- [x] Ruff, Electron startup tests, Frontend typecheck/lint/tests/build, backend 501 tests 및 QA self-test가 통과했다.

## Missing or Blocking Items

- [ ] **BLOCK-01 — mypy:** `spot_api.py:2174`, `spot_api.py:2189`에서
      `_SpotImageCacheEntry | None`을 `_spot_image_response()`에 전달하는 것으로 분석된다.
      runtime 분기와 일치하는 명시적 narrowing이 필요하다.
- [ ] **BLOCK-02 — recovery test:** refresh failure 뒤 다음 shared refresh가 성공하고 cache를
      교체하는 `BE-CACHE-09` 전용 테스트가 없다.
- [ ] **BLOCK-03 — task race test:** 완료된 refresh task를 정리하는 동안 새 task reference를
      지우지 않는 `BE-CON-09` 전용 테스트가 없다.
- [ ] **BLOCK-04 — waiter counter:** lock 안의 second cache check에서 fresh entry를 반환하는
      caller가 실제 shared task를 기다리지 않았는데도 coalesced waiter로 집계된다.

## Changed Items (Deviations from Design)

- [x] HTTP/1.0 close 검증은 반복 가능한 repository test가 아니라 Check 시점의 body-free
      loopback 실행으로 검증했다. 동작은 통과했지만 회귀 방지를 위해 자동 테스트로 고정해야 한다.
- [x] clean worktree에는 `backend/.venv`가 없어 최상위 `npm run health`가 해당 경로에서 중단됐다.
      main worktree의 동일 개발 venv를 사용해 Ruff, mypy 및 backend tests를 재실행했다.
      환경 문제와 코드 결과는 분리했으며 mypy 2건은 실제 코드 gate 실패로 판정했다.

## Validation Evidence

- Commit under Check: `4e3719e feat(spot): shape image request demand`
- Electron startup/lifecycle: 38 tests PASS
- Frontend: typecheck PASS, ESLint PASS, 33 files / 250 tests PASS
- Frontend production build: PASS, 4,532 modules
- Backend Ruff: PASS
- Backend mypy: **FAIL, 2 errors**
- Backend unittest discovery: 501 tests PASS
- NSIS operational-ready self-test: PASS
- HTTP/1.0 close loopback:
  - cold callers 20 → upstream 1
  - fresh callers 100 → additional upstream 0
  - expiry callers 20 → additional upstream 1
  - fresh batch 100 calls total 0.464ms, 0.0046ms/call
  - refresh failures 0
- `git diff --check`: PASS
- prohibited transport/secret scan: no new matches
- Installer/PyInstaller/NSIS package: **not created**
- Actual server 15-minute smoke and 120-minute canary: not started

## Recommendations

1. 별도 PDCA Act 승인 후 네 개 blocking item만 최소 변경으로 수정한다.
2. Ruff, mypy, 501 backend tests, 250 frontend tests 및 HTTP/1.0 loopback을 재실행한다.
3. 모든 local gate가 통과한 clean commit에서만 PyInstaller/NSIS package를 생성한다.
4. package identity와 SHA-256을 확정한 뒤 실제 서버 15분 smoke 승인으로 이동한다.

## Next Steps

- [x] Design-code gap analysis
- [x] Local protocol 및 regression Check
- [ ] Blocking gap 수정
- [ ] Check 재실행
- [ ] Clean package 생성
- [ ] 별도 승인 후 실제 서버 15분 smoke
- [ ] 15분 통과 후 별도 120분 canary
