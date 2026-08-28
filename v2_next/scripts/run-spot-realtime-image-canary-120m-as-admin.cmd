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
echo [CHECK] Verifying the v1.0.22 commit-bound server-validation kit.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify-spot-realtime-image-canary-kit.ps1"
if errorlevel 1 goto :verification_failed

echo.
echo [CHECK] Running fail-closed identity, v1.0.20 rollback, and pktmon preflight.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0invoke-spot-realtime-image-canary-120m.ps1" -ReleaseKitRoot "%~dp0.." -RollbackInstallerPath "%SFL_ROLLBACK_INSTALLER%" -PreflightOnly
if errorlevel 1 goto :preflight_failed

echo.
echo [READY] v1.0.22 preflight passed. Run the separate 15-minute diagnostic next.
echo [HOLD] This kit intentionally blocks the 120-minute observation until the
echo [HOLD] v1.0.22 15-minute evidence is reviewed and bound to a new kit.
set "SFL_CANARY_EXIT=3"
popd

echo.
echo Press any key to close this window.
pause >nul
exit /b %SFL_CANARY_EXIT%

:verification_failed
set "SFL_CANARY_EXIT=%ERRORLEVEL%"
popd
echo.
echo [FAILED] Canary kit verification failed. No evidence collection was started.
echo Press any key to close this window.
pause >nul
exit /b %SFL_CANARY_EXIT%

:preflight_failed
set "SFL_CANARY_EXIT=%ERRORLEVEL%"
popd
echo.
echo [FAILED] Preflight failed. The 120-minute observation was not started.
echo Press any key to close this window.
pause >nul
exit /b %SFL_CANARY_EXIT%
