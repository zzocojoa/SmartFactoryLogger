# Gap Analysis: spot-request-churn-remediation

> Date: 2026-07-24 | Design: `docs/02-design/features/spot-request-churn-remediation.design.md`
> Implementation commit: `4e3719e` | Act iteration: 2 | Verdict: **Local Check passed / package eligible**

---

## Match Rate: 100%

## Summary

설계의 로컬 검증 항목 50개 전부가 구현 및 검증 증거와 일치한다.

Frontend는 SPOT image 정상 표시가 끝난 뒤 설정된 1~10초 cadence로 다음 요청을
예약한다. 정상 timer, 기존 500/1000/2000ms retry, manual refresh, visibility 복귀 및
unmount lifecycle은 중복 실행되지 않는다.

Backend는 기존 `httpx.AsyncClient`, payload validation, timeout 및
`_spot_device_request_lock`을 유지하면서 process-local JPEG cache와 shared refresh
task를 사용한다. Act에서 mypy narrowing을 명시하고, 실제 shared task를 기다리지 않은
second cache check caller를 waiter 집계에서 제외했다. 또한 refresh 실패 뒤 다음
shared refresh의 복구와 완료 task 정리 중 replacement task 보존을 자동 테스트로
고정했다.

실제 HTTP/1.0 + Content-Length + server close loopback에서 cold caller 20개와 만료 후
caller 20개는 각각 upstream 요청 1개로 병합됐고, fresh caller 100개는 추가 upstream
요청 없이 cache에서 처리됐다. 전체 로컬 quality gate와 회귀 테스트가 통과했으므로
이전 package 차단은 해제한다. 설치 패키지 생성과 실제 서버 설치는 이 분석 범위에서
수행하지 않았으며 별도 승인 대상이다.

## Match Calculation

| 영역 | 전체 | 일치 | 판정 |
|---|---:|---:|---|
| Frontend policy 및 lifecycle | 18 | 18 | 일치 |
| Backend cache 및 concurrency | 20 | 20 | 일치 |
| API, observability 및 security | 8 | 8 | 일치 |
| Local quality 및 protocol gate | 4 | 4 | 일치 |
| **합계** | **50** | **50** | **100%** |

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
- [x] refresh 실패 뒤 다음 shared refresh가 성공하고 cache를 교체한다.
- [x] 완료 task 정리 중 새 replacement task reference를 지우지 않는다.
- [x] lock 내부 second cache check hit는 cache hit로만 집계하고 waiter로 집계하지 않는다.
- [x] upstream 성공 한 번당 image capture enqueue도 한 번만 수행한다.
- [x] `X-Spot-Image-Age-Ms`와 source/captured-at/upstream-latency 계약을 제공한다.
- [x] downstream/upstream/cache/leader/waiter/success/failure/cache-age 누계를 제공한다.
- [x] query parameter를 통한 TTL, upstream URL, force refresh 및 source port 주입을 추가하지 않았다.
- [x] raw socket, source-port allocator, custom HTTP parser 및 Windows network 변경을 추가하지 않았다.
- [x] DB, CSV, config 및 image fact schema migration이 없다.
- [x] HTTP/1.0 + Content-Length + server close loopback에서 freshness window당 upstream 1회를 확인했다.
- [x] Ruff, mypy, Electron, Frontend, Backend 및 QA self-test 전체 gate가 통과했다.

## Resolved Blocking Items

- [x] **BLOCK-01 — mypy:** fresh cache 분기에서 `cache_entry is not None`을 명시하여
      `_SpotImageCacheEntry`로 narrowing했다.
- [x] **BLOCK-02 — recovery test:** 실패한 refresh 뒤 다음 shared refresh가 성공하고
      cache와 failure 상태를 복구하는 테스트를 추가했다.
- [x] **BLOCK-03 — task race test:** 완료 refresh cleanup이 새 replacement task를
      제거하지 않는 테스트를 추가했다.
- [x] **BLOCK-04 — waiter counter:** second cache check hit에서 waiter 증가를 제거하고
      cache hit만 증가하는 테스트를 추가했다.

## Changed Items (Deviations from Design)

- [x] exact HTTP/1.0 close 조건은 repository unit test가 아니라 Check 시점의 body-free
      loopback으로 검증했다. cache/single-flight 동시성 동작은 repository 자동 테스트로
      고정되어 있다.
- [x] 해당 clean worktree에는 `backend/.venv`가 없어 main worktree의 동일 개발 venv를
      사용해 Ruff, mypy 및 backend tests를 실행했다. 실행 interpreter 경로를 검증
      증거에 명시하고 코드 결과와 환경 구성을 분리했다.

## Validation Evidence

- Implementation commit: `4e3719e feat(spot): shape image request demand`
- Act source changes: `spot_api.py` narrowing 및 waiter 의미 수정
- Act tests: recovery, second-cache-check counter, replacement-task race 3건 추가
- Electron startup/lifecycle: 38 tests PASS
- Frontend: typecheck PASS, ESLint PASS, 33 files / 250 tests PASS
- Frontend production build: PASS, 4,532 modules
- Backend Ruff: PASS
- Backend mypy: PASS, 6 source files
- Focused SPOT API tests: 83 tests PASS
- Backend unittest discovery: 504 tests PASS
- NSIS operational-ready self-test: PASS
- HTTP/1.0 close loopback:
  - cold callers 20 → upstream 1
  - fresh callers 100 → additional upstream 0
  - expiry callers 20 → additional upstream 1
  - fresh batch 100 calls total 0.686ms, 0.006862ms/call
  - leaders 2, true coalesced waiters 38, cache hits 100, refresh failures 0
- Installer/PyInstaller/NSIS package: not created
- Actual server 15-minute smoke and 120-minute canary: not started

## Remaining Operational Risk

- 로컬 loopback은 실제 SPOT 장비의 응답 지연, 관리형 스위치 오류 및 Windows 현장 부하를
  재현하지 않는다.
- 새 cache는 process-local이므로 backend process가 여러 개 실행되면 process별로
  upstream refresh가 발생한다. 실제 설치 전 backend 단일 process를 확인해야 한다.
- rollback은 검증된 v1.0.16 설치본과 SHA-256을 유지하는 방식이다.
- schema 및 migration 변경은 없으므로 데이터 migration 위험은 없다.
- 현장 실패 모드는 이미지 갱신 지연 또는 502로 나타나며, 기존 성공 frame과 오류
  관측성 계약은 유지된다.

## Recommendations

1. 현재 Act 변경을 clean commit으로 고정한다.
2. 별도 승인 후 그 clean commit에서만 PyInstaller/NSIS 설치 패키지를 생성한다.
3. package identity와 SHA-256을 확정한 뒤 실제 서버 15분 smoke를 수행한다.
4. 15분 smoke 통과 후 별도 승인으로 120분 canary를 수행한다.

## Next Steps

- [x] Design-code gap analysis
- [x] Blocking gap 수정
- [x] 전체 local Check 재실행
- [x] Match rate 100% 및 package gate 해제
- [ ] Clean Act commit 생성
- [ ] 별도 승인 후 clean package 생성
- [ ] 별도 승인 후 실제 서버 15분 smoke
- [ ] 15분 통과 후 별도 120분 canary
