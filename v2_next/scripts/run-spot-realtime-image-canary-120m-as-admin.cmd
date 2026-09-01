@echo off
setlocal EnableExtensions

fltmc >nul 2>&1
if not errorlevel 1 goto :elevated

echo [INFO] Requesting Windows administrator permission...
set "SFL_CANARY_LAUNCHER=%~f0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$q=[char]34; Start-Process -FilePath $env:ComSpec -Verb RunAs -ArgumentList @('/d','/c',($q+$q+$env:SFL_CANARY_LAUNCHER+$q+$q))"
exit /b

:elevated
pushd "%~dp0"
set "SFL_ROLLBACK_INSTALLER=C:\Users\user\Desktop\SmartFactory\v1020_cd8cfa6_internal_private_server_deploy_20260821_R3\smart-factory-logger-v2 Setup 1.0.20.exe"

echo [CHECK] Verifying the approved v1.0.22 120-minute kit.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify-spot-realtime-image-canary-kit.ps1" -KitRoot "%~dp0"
if errorlevel 1 goto :verification_failed

echo.
echo [CHECK] Running a fresh fail-closed server preflight.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0invoke-spot-realtime-image-canary-120m.ps1" -KitRoot "%~dp0" -ReleaseKitRoot "%~dp0.." -RollbackInstallerPath "%SFL_ROLLBACK_INSTALLER%" -PreflightOnly
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
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0invoke-spot-realtime-image-canary-120m.ps1" -KitRoot "%~dp0" -ReleaseKitRoot "%~dp0.." -RollbackInstallerPath "%SFL_ROLLBACK_INSTALLER%"
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

:finish
popd
echo.
echo Press any key to close this window.
pause >nul
exit /b %SFL_CANARY_EXIT%
