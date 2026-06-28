# Report: memory-diagnostics-r04-spot-cache

> Date: 2026-06-28 KST | Parent: `memory-diagnostics-hardening`

## Summary

- Feature: `memory-diagnostics-r04-spot-cache`
- Rank: 4
- Status: completed
- Match rate: 100%
- Scope: SPOT static image cache and live frame cache memory split, retry/failure note exposure, raw live URL redaction

r04 adds a public SPOT image cache memory summary and splits memory diagnostics into `spot.image_cache` and `spot.live_cache`. The existing `spot.cache` collector remains as a compatibility alias, so existing consumers are not broken.

## Completed Items

- Added `get_image_cache_memory_summary()` to `backend/FacilityData/drivers/spot_api.py`.
- Added exact byte accounting for static image cache and live image cache.
- Added age, cache state, failure count, retry timestamp, retry-after, and backoff fields to the summary.
- Redacted raw live image URL from the memory summary, exposing only `live_image_url_present`.
- Added `spot.image_cache` collector with `exactness="exact"`.
- Added `spot.live_cache` collector with `exactness="exact"`.
- Kept `spot.cache` as a compatibility alias that reports combined exact image bytes.
- Added backend tests for static/live bytes, retry/failure fields, raw live URL non-exposure, collector registration, exactness, and alias behavior.

## Files Changed

- `backend/FacilityData/drivers/spot_api.py`: public memory summary API and URL-safe static/live cache accounting.
- `backend/app.py`: split SPOT memory collectors and compatibility alias.
- `backend/tests/test_spot_api.py`: r04 summary and collector regression tests.
- `docs/03-analysis/memory-diagnostics-r04-spot-cache.analysis.md`: gap analysis and match rate evidence.

## Engineering Assessment

- Risk level: medium, because SPOT image diagnostics are production observability paths.
- Compatibility impact: additive. `spot.cache` remains registered as a compatibility alias.
- Security impact: raw live URL is not emitted by memory summary or collector output.
- Rollback path: remove split collectors and summary usage, then restore the previous `spot.cache` direct `_img_cache` byte calculation.
- Migration risk: none. No persistent schema, DB, CSV, or config change.
- Observability impact: static image cache and live frame cache can now be attributed independently.
- Operational failure mode: summary reads cache state only; SPOT fetch, retry, backoff, and cache TTL behavior are unchanged.
- Test coverage gap: no UI smoke was run because this rank does not change frontend rendering or browser behavior.

## Validation

- `.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_spot_api`: 66 passed.
- `npm run health`: passed.
  - frontend typecheck passed.
  - frontend lint passed.
  - frontend tests: 167 passed.
  - backend ruff passed.
  - backend mypy passed.
  - backend tests: 323 passed.
- `git diff --check`: passed with LF/CRLF warnings only.
- `bkit_pdca_analyze memory-diagnostics-r04-spot-cache`: executed; manual implementation comparison recorded 100% match.

## Review

- bkit pre-write checks were run for source, app collector, test, and doc files.
- bkit post-write checks were run for modified source and test files.
- Completed r03 state was rechecked before r04 implementation.

## Next Action

Activate `memory-diagnostics-r05-budget-severity` in `.pdca-status.json` and continue with r05 Do implementation.
