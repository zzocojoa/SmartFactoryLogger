# Monaco Split Browser Smoke

## Summary

- Date: 2026-04-28
- Route: `http://127.0.0.1:4173/dashboard`
- Preview command: `npm run preview -- --host 127.0.0.1 --port 4173`
- Browser path: local Chrome installation
- Browser runner: Playwright with bundled Node `v24.14.0`
- `@browser-use` status: blocked by Node REPL runtime check. The REPL resolved the system Node.js as `v22.17.0`, but requires `>= v22.22.0`.

## Result

The dashboard route loads and renders after the Monaco/Grafana ESM split experiment.

| Check | Result | Notes |
| --- | --- | --- |
| `/dashboard` HTTP status | Pass | `200` |
| React boot logs | Pass | `Index.tsx: Booting...`, scenes runtime initialized, app render log observed |
| Page title | Pass | `창녕 2호기 Smart Factory` |
| Root render | Pass | `#root` has one child on initial load |
| Dashboard panels visible | Pass | KPI, SPOT temperature, mold zone, auxiliary temperature, camera, environment, time series panels visible |
| JavaScript `pageerror` | Pass | none observed |
| Suspicious prompt-injection text | Pass | none detected in rendered body text |
| Backend/API console errors | Expected in preview | Preview has no live backend/proxy; repeated `500` API errors observed |
| Settings interaction | Partial | `MENU` and `설정` click work; settings password status check fails because backend returns `500`, then an alert modal blocks theme button clicks |

## Captures

- Initial dashboard: `.gstack/benchmark-reports/bundle-treemap/monaco-dashboard-smoke.png`
- Interaction state: `.gstack/benchmark-reports/bundle-treemap/monaco-dashboard-interaction-smoke.png`

## Console Notes

Observed errors are request/API failures, not module load or runtime exceptions:

- `Failed to load spot config g1`
- `Failed to load client layout g1`
- `Failed to fetch health g1`
- `Layout load failed g1`
- `Failed to list client layouts g1`
- `Settings password status check failed g1`
- `API Error (Worker) Request failed with status code 500`

No `pageerror` event was observed.

## Interpretation

This smoke test supports the current split candidate:

- App chunk remains reduced by the ESM alias experiment.
- The dashboard renders in a real Chromium browser.
- Monaco is not required for initial dashboard rendering.
- Remaining visible console errors are caused by missing backend endpoints in the static preview environment.

## Remaining Risk

- The current alias points to an internal `@grafana/scenes` ESM source path:
  `node_modules/@grafana/scenes/dist/esm/packages/scenes/src/index.js`
- This is effective for bundle size, but fragile if Grafana package internals change.
- Full confidence needs a backend-connected QA run, especially for settings, saved layouts, snapshots, diagnosis, and live panel data.
