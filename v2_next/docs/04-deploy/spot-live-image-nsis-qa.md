# SPOT Live Image NSIS Deployment QA

> **SUPERSEDED (updated 2026-08-21):** 이 문서는 과거 구현 이력 보존용입니다.
> 현재 장비 계약은 `GET /image.jpg` 하나이며, 앱의 snapshot/live 정책은
> `docs/02-design/features/spot-realtime-image-performance.design.md`를 따릅니다.
> 아래의 `/newjpeg.jpg`, `image.ssi`, 확장자 없는 앱 경로, 운영 결과는 현재
> 구현 지침이 아닙니다.

> Date: 2026-06-11
> Scope: Phase 9 deployment runbook + zero-script QA

## Purpose

Verify the SPOT live image feature after NSIS installation without mixing development PC checks and server computer operating checks.

## Environments

| Environment | SPOT access | Expected URLs |
|---|---|---|
| Development PC | Forwarded | `http://192.168.0.7:8080/image.jpg`, `http://192.168.0.7:8080/newjpeg.jpg`, `http://192.168.0.7:8080/image.ssi` |
| Server PC | Direct | `http://10.1.10.50/image.jpg`, `http://10.1.10.50/newjpeg.jpg`, `http://10.1.10.50/image.ssi` |

`image.ssi` is an HTML page. It must never be configured as the live upstream.

## Development PC QA Result

Executed on 2026-06-11:

```powershell
Invoke-WebRequest -Uri http://192.168.0.7:8080/image.jpg -Method Head -TimeoutSec 5
Invoke-WebRequest -Uri http://192.168.0.7:8080/newjpeg.jpg -Method Head -TimeoutSec 5
Invoke-WebRequest -Uri http://192.168.0.7:8080/image.ssi -Method Head -TimeoutSec 5
Invoke-WebRequest -Uri http://192.168.0.7:8080/newjpeg.jpg -Method Get -TimeoutSec 10 -OutFile C:\tmp\spot-newjpeg-dev-test.jpg
```

Result:

- `/image.jpg`: timeout.
- `/newjpeg.jpg`: timeout.
- `/image.ssi`: timeout.
- Downloaded test file was not created.

Interpretation:

- Development PC currently cannot prove forwarded SPOT availability.
- This does not prove feature failure; it means server-side direct SPOT QA remains mandatory before deploy approval.

Additional direct SPOT check from the development PC on 2026-06-11:

| URL | Result |
|---|---|
| `http://10.1.10.50/image.jpg` | Timeout after 5 seconds |
| `http://10.1.10.50/newjpeg.jpg` | Timeout after 5 seconds |
| `http://10.1.10.50/image.ssi` | Timeout after 5 seconds |

Interpretation:

- The development PC cannot directly validate the server-network SPOT camera.
- Server PC execution remains mandatory because `10.1.10.50` is expected to be reachable from the server network.

## Development PC Local HTTP Smoke Result

Executed on 2026-06-11 with a localhost mock SPOT upstream and isolated app config:

```powershell
$env:SFL_CONFIG_PATH='C:\tmp\sfl-live-smoke\config.ini'
$env:BACKEND_PORT='18080'
$env:V2_MODE='MOCK'
$env:SPOT_IMAGE_URL='http://127.0.0.1:19090/image.jpg'
$env:SPOT_LIVE_IMAGE_URL='http://127.0.0.1:19090/newjpeg.jpg'
```

Result:

| Check | Result |
|---|---|
| Mock SPOT `/newjpeg.jpg` -> `/api/spot/live_image` | HTTP 200 |
| `/api/spot/live_image` content type | `image/jpeg` |
| `/api/spot/live_image` cache header | `no-store, no-cache, must-revalidate, max-age=0` |
| `/api/spot/live_image` source header | `X-Spot-Live-Image-Source: upstream` |
| `/api/spot/proxy_image` with mock `/image.jpg` | HTTP 200, `image/jpeg` |
| `/api/spot/config` | HTTP 200 |
| `/stats` | HTTP 200 |
| Mock SPOT `/image.ssi` as live upstream | HTTP 502 |
| HTML upstream rejection code | `invalid-image-html` |
| HTML upstream rejection header | `X-Spot-Payload-Rejection: 1` |

Interpretation:

- The live endpoint works as a browser-consumable image endpoint in a real FastAPI HTTP runtime.
- The existing proxy image endpoint still works with the same mock SPOT image source.
- HTML `image.ssi` is rejected as an invalid image payload and is not silently proxied as camera data.
- This is still a development-PC smoke test. It does not prove server PC network access to `10.1.10.50` or production runtime load behavior.

## Development PC Browser Smoke Result

Executed on 2026-06-11 with Playwright, the built `frontend/dist`, a localhost FastAPI backend, and a valid JPEG mock SPOT upstream:

| Check | Result |
|---|---|
| Browser URL | `http://127.0.0.1:18083/dashboard` |
| Visible camera image src | `/api/spot/live_image?t=...` |
| Image source uses Blob URL | `false` |
| Image source changed after observation window | `true` |
| Decoded image size | `4 x 3` |
| Live image responses in ~1.2s window | `29` |
| Live image response status/content-type | HTTP 200, `image/jpeg` |
| Live image cache header | `no-store, no-cache, must-revalidate, max-age=0` |
| Existing proxy image request | HTTP 200, `image/jpeg` |
| Page errors | None |

Observed console output included two 404 resource load errors unrelated to `/api/spot/live_image` or `/api/spot/proxy_image`. These should not block SPOT live validation, but can be reviewed separately if frontend asset noise matters.

Interpretation:

- The `CameraWidget` visible image uses the live endpoint, not a Blob URL.
- The `<img>` `src` changes over time in the browser, proving the reload loop is active.
- Because the image successfully decodes, the observed loop is the `onLoad` path rather than only the slower `onError` retry path.
- This remains a mock-upstream browser test. Server-side SPOT FPS, CPU, `/stats`, and logs still require direct server QA.

## Development Package Artifact

Generated on 2026-06-11 from this workspace after rebuilding `frontend/dist` and `backend/dist/SmartFactoryBackend.exe`:

| Item | Value |
|---|---|
| Installer | `C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next\dist\smart-factory-logger-v2 Setup 1.0.11.exe` |
| Size | `146928639` bytes |
| Last write time | `2026-06-11 13:08:13 +09:00` |
| SHA256 | `A2AB91DD46B57E6E5F71CD9A3AAD2D2437AFEFE84E7B0561588CA43F5A12618A` |
| Backend executable | `C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next\backend\dist\SmartFactoryBackend.exe` |
| Packaged QA script | `dist\win-unpacked\resources\qa\qa_spot_live_server.ps1` |

This verifies package generation and confirms the server QA script is included in the unpacked NSIS resources. It does not replace server-side NSIS installation, direct SPOT endpoint checks, browser observation, `/stats`, or log review.

## Electron App Display Regression

Observed on 2026-06-11 after server QA:

- Web dashboard `http://192.168.0.7:8000/dashboard` displayed the SPOT live image.
- Direct backend image `http://192.168.0.7:8000/api/spot/live_image?t=1` displayed the SPOT image.
- Installed Electron desktop app did not display the SPOT image.

Root cause:

- The packaged Electron app loads the frontend with `BrowserWindow.loadFile(...)`, so the frontend runs from a `file:` origin.
- API fetches already resolve `file:` to `http://localhost:8000`.
- The new visible live image path used the relative `/api/spot/live_image` directly in `<img src>`, which works in the web dashboard but not reliably from the Electron file origin.

Fix:

- Relative live image URLs are now resolved against the frontend `API_BASE`.
- In the Electron app, `/api/spot/live_image` becomes `http://localhost:8000/api/spot/live_image`.
- Absolute URLs remain unchanged.

The NSIS installer listed above was regenerated after this fix and must replace the earlier 2026-06-11 12:31:59 build for Electron desktop validation.

## Pre-Install Backup

Run on the server computer before NSIS installation:

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = "C:\tmp\SmartFactoryLogger-backup-$stamp"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

Copy-Item -LiteralPath "$env:APPDATA\SmartFactoryLogger\config.ini" -Destination "$backupRoot\config.ini" -ErrorAction SilentlyContinue
Copy-Item -LiteralPath "C:\Program Files\SmartFactoryLogger" -Destination "$backupRoot\install-folder" -Recurse -ErrorAction SilentlyContinue
Copy-Item -LiteralPath "C:\path\to\previous-installer.exe" -Destination "$backupRoot\previous-installer.exe" -ErrorAction SilentlyContinue

Get-ChildItem -LiteralPath $backupRoot
```

Adjust install folder and previous installer path to match the server.

## Pre-Install Configuration Check

```powershell
$config = "$env:APPDATA\SmartFactoryLogger\config.ini"
Get-Content -LiteralPath $config | Select-String -Pattern "^\[SPOT\]|^ip\s*=|^imageurl\s*=|^liveimageurl\s*="
```

Expected:

```ini
[SPOT]
ip = 10.1.10.50
imageurl = http://10.1.10.50/image.jpg
```

Optional live upstream:

```ini
liveimageurl = http://10.1.10.50/newjpeg.jpg
```

Use `newjpeg.jpg` for smoother live display only after direct server checks pass. Use `image.jpg` when prioritizing documented AMETEK REST behavior.

## Direct SPOT Endpoint Checks

Run before and after installation:

```powershell
Invoke-WebRequest -Uri http://10.1.10.50/image.jpg -Method Head -TimeoutSec 5 | Select-Object StatusCode,Headers
Invoke-WebRequest -Uri http://10.1.10.50/newjpeg.jpg -Method Head -TimeoutSec 5 | Select-Object StatusCode,Headers
Invoke-WebRequest -Uri http://10.1.10.50/image.ssi -Method Head -TimeoutSec 5 | Select-Object StatusCode,Headers
```

Expected:

- `/image.jpg`: HTTP 200 and image content type.
- `/newjpeg.jpg`: HTTP 200 and image content type if enabled by device.
- `/image.ssi`: HTTP 200 and `text/html` or equivalent HTML content type.

If HEAD is unsupported, use GET:

```powershell
Invoke-WebRequest -Uri http://10.1.10.50/image.jpg -Method Get -TimeoutSec 10 -OutFile C:\tmp\spot-image.jpg
Invoke-WebRequest -Uri http://10.1.10.50/newjpeg.jpg -Method Get -TimeoutSec 10 -OutFile C:\tmp\spot-newjpeg.jpg
Get-Item C:\tmp\spot-image.jpg,C:\tmp\spot-newjpeg.jpg | Select-Object FullName,Length
```

## NSIS Install

Use GUI install unless silent install support is confirmed for the generated installer.

```powershell
Start-Process -FilePath "C:\path\to\SmartFactoryLogger-setup.exe" -Verb RunAs -Wait
```

Only if silent install is confirmed:

```powershell
Start-Process -FilePath "C:\path\to\SmartFactoryLogger-setup.exe" -ArgumentList "/S" -Verb RunAs -Wait
```

Prefer staging server or non-production time window.

## Post-Install App Smoke QA

Find the backend port from app config or logs. Examples below assume `8000`.

```powershell
$base = "http://127.0.0.1:8000"

Invoke-WebRequest -Uri "$base/api/spot/config" -Method Get -TimeoutSec 5 | Select-Object StatusCode,Content
Invoke-WebRequest -Uri "$base/api/spot/live_image?t=$(Get-Date -UFormat %s)" -Method Head -TimeoutSec 5 | Select-Object StatusCode,Headers
Invoke-WebRequest -Uri "$base/api/spot/proxy_image?t=$(Get-Date -UFormat %s)" -Method Head -TimeoutSec 5 | Select-Object StatusCode,Headers
Invoke-WebRequest -Uri "$base/stats" -Method Get -TimeoutSec 5 | Select-Object StatusCode,Content
```

Expected:

- `/api/spot/config`: 200, includes `live_image_url`.
- `/api/spot/live_image`: 200, `Content-Type` contains `image/jpeg`, `Cache-Control` contains `no-store`.
- `/api/spot/proxy_image`: 200 image response or known existing stale/proxy behavior.
- `/stats`: 200, no abnormal error rate.

## Server QA Artifact Script

After NSIS installation and app startup, run the read-only QA script on the server computer to collect repeatable evidence:

```powershell
.\scripts\qa_spot_live_server.ps1 `
  -BackendBaseUrl "http://127.0.0.1:8000" `
  -SpotIp "10.1.10.50" `
  -ConfigPath "$env:APPDATA\SmartFactoryLogger\config.ini" `
  -InstallerPath "C:\path\to\smart-factory-logger-v2 Setup 1.0.11.exe" `
  -OutputPath "C:\tmp\sfl-spot-live-server-qa.json" `
  -LogLookbackMinutes 30 `
  -LiveLoopSeconds 5 `
  -LiveLoopDelayMs 35
```

When running from an installed NSIS app rather than the repository checkout, use the packaged resource copy. The exact install root can vary, but the default per-user location is typically:

```powershell
& "$env:LOCALAPPDATA\Programs\smart-factory-logger-v2\resources\qa\qa_spot_live_server.ps1" `
  -BackendBaseUrl "http://127.0.0.1:8000" `
  -SpotIp "10.1.10.50" `
  -ConfigPath "$env:APPDATA\SmartFactoryLogger\config.ini" `
  -InstallerPath "C:\path\to\smart-factory-logger-v2 Setup 1.0.11.exe" `
  -OutputPath "C:\tmp\sfl-spot-live-server-qa.json" `
  -LogLookbackMinutes 30 `
  -LiveLoopSeconds 5 `
  -LiveLoopDelayMs 35
```

The script does not install, uninstall, or modify configuration. It checks:

- Direct SPOT `/image.jpg`, `/newjpeg.jpg`, and `/image.ssi`.
- App `/api/spot/config`, `/api/spot/live_image`, `/api/spot/proxy_image`, and `/stats`.
- `Cache-Control: no-store` on the live image endpoint.
- A short live endpoint loop and `/stats` before/after delta.
- Recent SPOT-related log lines within the selected lookback window.
- Installer SHA256 when `-InstallerPath` is provided.

Exit code:

- `0`: blocking HTTP/content-type/cache-control checks passed.
- `1`: at least one blocking check failed.

The JSON artifact path printed by the script should be attached to the final server deployment record.

Use `-LiveLoopSeconds 0` when you only want one-shot endpoint checks without additional live request load. For deployment QA, keep the default short loop first, then perform the separate 5-minute browser observation below.

Local script smoke on 2026-06-11:

- Environment: localhost mock SPOT, localhost FastAPI backend, `V2_MODE=MOCK`.
- Result: `passed=true`, `blockerCount=0`.
- Live endpoint observed by script: HTTP 200, `image/jpeg`, `Cache-Control` includes `no-store`.
- Existing proxy endpoint observed by script: HTTP 200.
- Live loop observed by script: 1 second, 20 requests, 20 successes, 0 failures.
- `/stats` delta observed by script: `total_requests +21`, `error_count +0`.
- Warning: recent SPOT-related local log lines can be surfaced for review when present.

This validates the script behavior only. It does not replace server execution against `10.1.10.50`.

## Browser QA

1. Launch the installed app.
2. Open the dashboard with the SPOT camera widget.
3. Observe live view for at least 5 minutes.
4. Confirm the visible image updates smoothly.
5. Confirm no new delayed/stale camera alert is introduced by live view.
6. Open 2 to 3 browser windows/tabs and repeat for 2 minutes.
7. Confirm server CPU, memory, and `/stats` request rate remain acceptable.

## Log Checks

Adjust log directory if the server uses a custom configured log path.

```powershell
$logRoot = "$env:APPDATA\SmartFactoryLogger"
Get-ChildItem -Path $logRoot -Recurse -File |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 20 FullName,LastWriteTime,Length
```

Search recent logs:

```powershell
Get-ChildItem -Path $logRoot -Recurse -File |
  Select-String -Pattern "Spot image fetch failed|upstream-timeout|retry-backoff-active|stale serve|invalid-image-html|live-backoff-active" |
  Select-Object -First 100
```

Pass criteria:

- No repeated `invalid-image-html` for live endpoint.
- No sustained `upstream-timeout`.
- No continuous `live-backoff-active`.
- Existing proxy stale behavior does not increase after live view starts.

## Fail Criteria

- `/api/spot/proxy_image` fails after install.
- `/api/spot/live_image` returns `text/html`.
- `image.ssi` is accepted as image data.
- 5 minutes of live view causes CPU, memory, or logs to spike.
- Live view causes delayed/stale alert frequency to increase.
- Multiple tabs make request rate or CPU unacceptable.

## Rollback

1. Close the new app version.
2. Reinstall previous NSIS installer or restore previous install folder.
3. Restore backed-up `config.ini`.
4. Remove `liveimageurl` or unset `SPOT_LIVE_IMAGE_URL`.
5. Start app.
6. Verify `/api/spot/proxy_image` and dashboard camera snapshot path.

## Final Deployment Record

Latest server QA artifact received on 2026-06-11 13:14:17 +09:00 from `DESKTOP-CIIT7LK`.

| Item | Result |
|---|---|
| Actual server NSIS install performed | App was running on server and QA script executed against `http://127.0.0.1:8000`; installer path/hash was not supplied to script |
| Server `[SPOT] imageurl` | `http://10.1.10.50/image.jpg` |
| Server `[SPOT] liveimageurl` | `http://10.1.10.50/image.jpg` |
| Direct SPOT `/image.jpg` | HTTP 200, `image/jpeg`, 10464 bytes, 94 ms |
| Direct SPOT `/newjpeg.jpg` | HTTP 200, `image/jpeg`, 10464 bytes, 4.8 ms |
| Direct SPOT `/image.ssi` | HTTP 200, `text/html`, 2804 bytes |
| `/api/spot/live_image` status/content-type/cache-control | HTTP 200, `image/jpeg`, `no-store, must-revalidate, no-cache, max-age=0`, source `shared-frame` |
| `/api/spot/proxy_image` status/content-type/cache-control | HTTP 200, `image/jpeg`, `no-store, must-revalidate, no-cache, max-age=0` |
| Live loop probe | 5 sec, 69 requests, 69 successes, 0 failures, avg 16.1 ms, max 52.6 ms |
| Browser FPS/visual observation | Passed: Electron desktop app displayed the SPOT camera image for more than 5 minutes |
| `/stats` request rate/error rate | Before: 16.617 req/s, 0 errors. After: 20.017 req/s, 0 errors. Delta: `total_requests +204`, `error_count +0`, `total_http_error_count +0` |
| `/stats` live image rate | Before: 11.583 req/s over the 60 sec window. After: 14.367 req/s over the 60 sec window. Error rate: 0.0 |
| `/stats` proxy image state | After: 95 proxy requests, 1.583 req/s, 0 failures, 0 stale responses, avg age 0.609 sec |
| Log summary | Warning: recent `Spot image fetch failed` and `Spot stale serve` lines were present in `server_stderr.log`; current `/stats` window showed zero proxy failures/stale responses, and the 5-minute Electron observation had no interruption or delayed alert |
| Rollback package verified | Passed: previous installer or backup is available |
| Server QA JSON artifact | Generated at `2026-06-11T13:14:17.8535864+09:00`; script verdict `passed=true` with warning |
| Merge/deploy verdict | Approved for merge/deploy: HTTP/API checks passed, Electron desktop observation passed, and rollback is available |
