# Gap Analysis: spot-image-auto-recovery

> Date: 2026-07-14 | Design: docs/02-design/features/spot-image-auto-recovery.design.md
> Iteration: 2 | Status: Complete

---

## Match Rate: 100%

## Summary

The implementation matches all 20 reviewed design requirements. Normal SPOT
JPEG acquisition remains completion-driven and uses the existing official
`/image.jpg` bridge. Only failure recovery introduces timers. Transient errors
receive three bounded retries, persistent failures remain manual, and
focus/actuator errors no longer contaminate image state.

The first Check pass found two verification/policy gaps:

1. `upstream-http-error` without an upstream status did not fall back to the
   bridge status;
2. retry exhaustion was tested, but manual recovery after exhaustion was not.

Both gaps were corrected in Act iteration 1 and the focused suite passed.

## Requirement Matrix

| # | Design requirement | Evidence | Result |
|---:|---|---|---|
| 1 | Official `/image.jpg` resource remains unchanged | No backend/config path change; source search | Match |
| 2 | Successful display requests the next frame exactly once | pending Blob identity guard and integration test | Match |
| 3 | No normal success timer | timer exists only in failure scheduler | Match |
| 4 | Timeout/request errors are retryable | pure policy tests | Match |
| 5 | Retryable upstream HTTP statuses are bounded | `408/425/429/5xx` policy tests | Match |
| 6 | Empty body/bridge 5xx/network exception recover | pure policy and hook tests | Match |
| 7 | Browser display failure recovers | display-error integration test | Match |
| 8 | Config/payload failures are terminal | payload rejection integration test | Match |
| 9 | Delays are exactly 500/1000/2000 ms | pure policy and fake-timer tests | Match |
| 10 | Retry stops after three attempts | exhaustion integration test | Match |
| 11 | Manual Retry cancels pending timer | manual override integration test | Match |
| 12 | Manual Retry works after exhaustion | exhaustion recovery integration test | Match |
| 13 | Displayed success resets retry budget | recovery/reset integration assertion | Match |
| 14 | Duplicate consumers cannot duplicate retry | duplicate display-error test | Match |
| 15 | Unmount cancels retry | unmount integration test | Match |
| 16 | Image URL change cancels retry | config-change integration test | Match |
| 17 | Recovery diagnostics are recorded | typed fields and integration assertions | Match |
| 18 | Focus/actuator errors are separate | store state, hook tests, CameraWidget alert | Match |
| 19 | Image Retry depends only on image error | CameraWidget UI test | Match |
| 20 | No backend/CSV/migration change | changed-file audit | Match |

## Implemented Items

- [x] Pure failure classification and bounded delay policy.
- [x] Singleton automatic retry ownership and cleanup.
- [x] Manual immediate retry and exhausted-state recovery.
- [x] Frontend retry diagnostics.
- [x] Separate `spotControlError` state and UI alert.
- [x] Unit, hook integration, and component regression tests.

## Missing Items

None.

## Changed Items (Deviations from Design)

None. The bridge-status fallback added during Act clarifies the designed
unknown/non-payload `502` behavior.

## Validation at Check

- Focused recovery/UI tests: `32 passed` before Act.
- Act-focused policy/hook tests: `27 passed`.
- Frontend full suite before Act: `28 files`, `204 passed`.
- Frontend typecheck: PASS.
- Frontend lint: PASS.
- `git diff --check`: PASS.

Full repository health and package validation are Report/Build gates and are
not inferred from these focused results.

## Recommendations

1. Run full `npm run health` before committing.
2. Build PyInstaller and NSIS only from the resulting clean commit.
3. Install the new NSIS on the server computer and repeat the established
   15-minute physical-device validation.

## Next Steps

- [x] Gap fixes applied and re-tested.
- [ ] Complete full health, report, clean commit, and NSIS build.
