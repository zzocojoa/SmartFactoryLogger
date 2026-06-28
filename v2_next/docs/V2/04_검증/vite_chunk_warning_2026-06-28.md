# Vite chunk warning follow-up, 2026-06-28

## Summary

`npm --prefix frontend run build` produced the Vite 500 kB chunk warning because two manual vendor chunks were too broad:

- `vendor-grafana`: all `@grafana/*` packages were forced into one chunk.
- `vendor-moment-timezone`: `@grafana/data` pulled the default `moment-timezone` package with the full packed timezone dataset.

The fix keeps the existing lazy component boundaries and changes only build-time chunk policy in `frontend/vite.config.ts`.

## Baseline

Command:

```powershell
npm --prefix frontend run build
```

Relevant output before the change:

| Chunk | Size | Gzip | Warning |
| --- | ---: | ---: | --- |
| `vendor-grafana-11IRMQLt.js` | 1,497.34 kB | 464.04 kB | yes |
| `vendor-moment-timezone-DEu0mB9u.js` | 731.42 kB | 39.46 kB | yes |

Other build noise:

- `Generated an empty chunk: "vendor-monaco".`

## Result

Command:

```powershell
npm --prefix frontend run build
```

Relevant output after the change:

| Chunk | Size | Gzip | Warning |
| --- | ---: | ---: | --- |
| `vendor-grafana-scenes-I6cwfkjp.js` | 494.37 kB | 145.56 kB | no |
| `vendor-grafana-ui-GJGvaxMP.js` | 443.64 kB | 139.86 kB | no |
| `vendor-grafana-data-CJWLk8jZ.js` | 402.76 kB | 132.83 kB | no |
| `vendor-grafana-support-BcsBgcPL.js` | 133.20 kB | 39.54 kB | no |
| `vendor-grafana-runtime-clmB27-Y.js` | 21.47 kB | 8.11 kB | no |
| `vendor-moment-timezone-DJxF8DDF.js` | 42.16 kB | 11.90 kB | no |

The Vite 500 kB chunk warning no longer appears. The empty `vendor-monaco` chunk warning also no longer appears because there is no `monaco-editor` dependency or app import to justify a manual chunk rule.

## Policy

- Do not raise `build.chunkSizeWarningLimit` for this case. The previous warning identified real over-bundling.
- Keep Grafana chunks package-scoped so `@grafana/scenes`, `@grafana/ui`, `@grafana/data`, and runtime/support packages can be cached and loaded independently.
- Use `moment-timezone-with-data-10-year-range.js` for the dashboard bundle. The app displays near-term telemetry and does not require the full historical timezone database in the browser bundle.
- Keep `moment-timezone` as a direct `frontend` dependency. `frontend/vite.config.ts` aliases `moment-timezone` explicitly, so the bundle policy should not depend on `@grafana/data` continuing to pull the package transitively.

## Follow-up validation

NONBLOCK-1/2 were checked after PR #92 merged:

- Frontend source does not import `moment-timezone` directly.
- Browser-facing telemetry ranges are built from current poll/history samples in `frontend/src/domains/FacilityData/timeseries` and are retained in a one-hour buffer.
- General UI timestamps use native `Date`/`toLocaleString`; they do not require the full Moment Timezone database.
- The selected `moment-timezone-with-data-10-year-range.js` bundle has timezone transition data covering 2020 through 2030 for DST zones such as `America/New_York` and `Europe/Berlin`.
- `frontend/src/shared/build/timezoneBundlePolicy.test.ts` verifies the direct dependency, lockfile entry, Vite alias target, bundle file existence, and 2020-2030 transition coverage.

## Risk and rollback

Main behavior risk is timezone data range. If the dashboard later needs far historical, pre-2020, post-2030, or user-selected future timezone conversions, remove the `moment-timezone` alias and accept the larger chunk or choose a wider bundled dataset such as `moment-timezone-with-data-1970-2030.js`.

Rollback path:

- Revert the `frontend/vite.config.ts`, `frontend/package.json`, `frontend/package-lock.json`, test, and doc changes from the policy PR.
- Re-run `npm --prefix frontend run build` and confirm the previous vendor chunks return.
