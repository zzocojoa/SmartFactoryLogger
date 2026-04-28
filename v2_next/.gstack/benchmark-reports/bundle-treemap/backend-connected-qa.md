# Backend Connected QA

## Summary

- Date: 2026-04-28
- Route: `http://127.0.0.1:8000/dashboard`
- Backend command: `python -m uvicorn app:app --host 127.0.0.1 --port 8000`
- Backend mode: `V2_MODE=CSV`
- CSV path: `../v1_legacy/logs/Aligned_Results/Factory_Integrated_Log_20251231_000000.csv`
- Browser: Chrome via Playwright
- Backend process: local test process

## Result

The Monaco/Grafana ESM split candidate works in a backend-connected local run.

| Check | Result | Notes |
| --- | --- | --- |
| Backend `/health` | Pass | HTTP `200` |
| Backend `/api/data` | Pass | HTTP `200`, CSV replay values returned |
| Backend `/dashboard` | Pass | HTTP `200`, SPA served by FastAPI |
| App chunk served | Pass | `App-Bz_Ymavl.js`, `2,696,839` bytes |
| Monaco chunk preload | Pass | no Monaco asset loaded during initial dashboard QA |
| Dashboard render | Pass | KPI, SPOT temperature, mold, environment, auxiliary temperature, time series displayed |
| CSV replay data visible | Pass | speed, pressure, count, temperatures, mold values displayed |
| JavaScript `pageerror` | Pass | none observed |
| Failed browser requests | Partial | SPOT camera proxy returns `502` because local SPOT camera is unavailable |
| Layout latest request | Expected first-run miss | client-specific latest layout returns `404`, list/layout fallback succeeds |
| Menu/settings interaction | Partial | `MENU` and `설정` click; theme/edit buttons can be blocked by overlay/menu/modal state in automated click flow |

## Captures

- Backend connected dashboard: `.gstack/benchmark-reports/bundle-treemap/backend-connected-dashboard-absolute-csv-smoke.png`
- Initial backend connected dashboard: `.gstack/benchmark-reports/bundle-treemap/backend-connected-dashboard-smoke.png`

## Observed Data

Rendered body text included representative CSV replay values:

- `SPOT 온도 505.3 °C`
- `메인 압력 215.0`
- `압출 속도 2.5`
- `생산 카운트 43.0`
- `환경 온도 26.0`
- `환경 습도 12.3`
- mold zones around `477.0` to `479.0`

## Console / Network Notes

No browser `pageerror` occurred.

Observed non-fatal request failures:

- `/api/layouts/client/{clientId}/latest` -> `404`
  - First-run client layout is missing; `/api/layout` and client layout list still return `200`.
- `/api/spot/proxy_image?...` -> `502`
  - Local SPOT camera/proxy target is unavailable in this test environment.

These failures are not evidence of Monaco split regression.

## Interpretation

The split candidate is viable for the next hardening step:

- The production build serves through the real FastAPI backend.
- The smaller App chunk loads and renders the dashboard.
- CSV replay data flows into panels.
- Monaco remains absent from initial dashboard loading.

The remaining risk is the internal Grafana ESM alias path:

`node_modules/@grafana/scenes/dist/esm/packages/scenes/src/index.js`

This should be guarded with a package-version check or replaced with an upstream-supported ESM import path if one exists.
