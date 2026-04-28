# Grafana Scenes Alias Hardening

## Summary

- Date: 2026-04-28
- File changed: `frontend/vite.config.ts`
- Target package: `@grafana/scenes`
- Supported version pinned in config: `6.52.0`
- Internal ESM entry used: `node_modules/@grafana/scenes/dist/esm/packages/scenes/src/index.js`

## Why

The Monaco split experiment depends on resolving `@grafana/scenes` to its ESM source entry. The package declares `module: dist/esm/index.js`, but the installed package does not contain that file. The effective ESM path is therefore an internal package path.

Without a guard, a future package upgrade could silently break this optimization or reintroduce the CJS entry that pulls Monaco into the initial App chunk.

## Change

`frontend/vite.config.ts` now:

- reads `@grafana/scenes/package.json`
- validates the package shape
- requires `@grafana/scenes` version `6.52.0`
- requires the verified internal ESM entry to exist
- throws an explicit build-time error if the version or entry path changes
- avoids falling back to another entry automatically

## Validation

Commands run:

- `npm run build`
- `npx vite build --sourcemap`
- backend-connected browser smoke against `http://127.0.0.1:8000/dashboard`

Build result:

- App chunk: `App-Bz_Ymavl.js`
- App chunk size: `2,696.84 kB`
- gzip: `652.72 kB`
- transformed modules: `4542`

Sourcemap check:

- App sources: `1200`
- Monaco sources: `0`
- CJS `@grafana/scenes/dist/index.js` sources: `0`
- ESM scenes sources: `166`

Browser smoke:

- `/dashboard` HTTP status: `200`
- browser `pageerror`: none
- App script loaded: true
- Monaco asset loaded: false
- CSV replay data visible through the backend

Known non-regression console errors:

- client latest layout first-run `404`
- SPOT image proxy `502` because local SPOT camera/proxy target is unavailable

## Remaining Risk

This still depends on an internal package layout. The guard makes that dependency explicit and fail-fast, but it does not remove the dependency. A future upgrade of `@grafana/scenes` should include a dedicated revalidation step for bundle size and dashboard smoke QA.
