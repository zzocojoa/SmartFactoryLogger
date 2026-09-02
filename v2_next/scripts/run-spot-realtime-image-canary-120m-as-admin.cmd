@echo off
setlocal EnableExtensions

fltmc >nul 2>&1
if not errorlevel 1 goto :elevated

echo [FAILED] This unsigned internal kit cannot elevate itself safely.
echo [ACTION] Use the independently hash-bound external bootstrap from an
echo [ACTION] Administrator PowerShell after it verifies the unopened ZIP.
exit /b 5

:elevated
if /I not "%SFL_CANARY_EXTERNAL_PROVENANCE_VERIFIED%"=="YES" goto :provenance_required
if not defined SFL_ROLLBACK_INSTALLER goto :rollback_path_required

pushd "%~dp0"

echo [CHECK] Verifying the approved v1.0.22 120-minute kit.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify-spot-realtime-image-canary-kit.ps1" -KitRoot "%~dp0"
if errorlevel 1 goto :verification_failed

echo.
echo [CHECK] Running a fresh fail-closed server preflight.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0invoke-spot-realtime-image-canary-120m.ps1" -KitRoot "%~dp0" -ReleaseKitRoot "%~dp0.." -PreflightOnly
if errorlevel 1 goto :preflight_failed

echo.
echo [READY] The approved 15-minute evidence and fresh preflight passed.
echo [ACTION] Keep the SmartFactory camera screen visible for the full run.
echo [ACTION] Do not minimize the app, change tabs, clear errors, or run a load test.
echo [ACTION] Type RUN-120M to start exactly one 120-minute observation.
set "SFL_CANARY_CONFIRM="
set /p "SFL_CANARY_CONFIRM=Confirmation: "
if /I not "%SFL_CANARY_CONFIRM%"=="RUN-120M" goto :cancelled

echo.
echo [START] Starting the 120-minute observation.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0invoke-spot-realtime-image-canary-120m.ps1" -KitRoot "%~dp0" -ReleaseKitRoot "%~dp0.."
set "SFL_CANARY_EXIT=%ERRORLEVEL%"
if "%SFL_CANARY_EXIT%"=="0" goto :passed
if "%SFL_CANARY_EXIT%"=="2" goto :limited_pass
if "%SFL_CANARY_EXIT%"=="3" goto :evidence_hold
if "%SFL_CANARY_EXIT%"=="10" goto :rollback_required
goto :run_failed

:passed
echo.
echo [PASS] The 120-minute gate passed. Production promotion remains separate.
goto :finish

:limited_pass
echo.
echo [PASS WITH LIMITATION] App, packet, and operator gates passed.
echo [LIMITATION] Managed-switch faults remain unexcluded.
goto :finish

:evidence_hold
echo.
echo [EVIDENCE HOLD] Measurement evidence was incomplete or uncertain.
echo [HOLD] Do not rerun or roll back automatically. Preserve all evidence.
goto :finish

:rollback_required
echo.
echo [ROLLBACK REQUIRED] A product hard failure was corroborated.
echo [HOLD] No automatic rollback was performed by this launcher.
goto :finish

:run_failed
echo.
echo [FAILED] The 120-minute controller failed with exit %SFL_CANARY_EXIT%.
echo [HOLD] Preserve the complete output and evidence. Do not rerun automatically.
goto :finish

:verification_failed
set "SFL_CANARY_EXIT=%ERRORLEVEL%"
echo.
echo [FAILED] Kit verification failed. No observation was started.
goto :finish

:preflight_failed
set "SFL_CANARY_EXIT=%ERRORLEVEL%"
echo.
echo [FAILED] Preflight failed. No observation was started.
goto :finish

:cancelled
set "SFL_CANARY_EXIT=4"
echo.
echo [CANCELLED] Confirmation did not match. No observation was started.
goto :finish

:provenance_required
echo.
echo [FAILED] External ZIP provenance verification was not recorded.
echo [ACTION] Do not set SFL_CANARY_EXTERNAL_PROVENANCE_VERIFIED manually.
echo [ACTION] Launch only through the independently hash-bound bootstrap.
exit /b 5

:rollback_path_required
echo.
echo [FAILED] SFL_ROLLBACK_INSTALLER was not supplied by the trusted bootstrap.
exit /b 5

:finish
popd
echo.
echo Press any key to close this window.
pause >nul
exit /b %SFL_CANARY_EXIT%
