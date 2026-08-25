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
echo [CHECK] Verifying the v1.0.21 commit-bound 120-minute canary kit.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify-spot-realtime-image-canary-kit.ps1"
if errorlevel 1 goto :verification_failed

echo.
echo [CHECK] Running fail-closed identity, v1.0.20 baseline rollback, 15-minute evidence, and pktmon preflight.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0invoke-spot-realtime-image-canary-120m.ps1" -ReleaseKitRoot "%~dp0.." -RollbackInstallerPath "%SFL_ROLLBACK_INSTALLER%" -PreflightOnly
if errorlevel 1 goto :preflight_failed

echo.
echo [START] Starting the passive 120-minute v1.0.21 SPOT canary.
echo [START] Progress appears every 30 seconds after packet observation starts.
echo [START] Keep the normal app screen visible and do not close this window.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0invoke-spot-realtime-image-canary-120m.ps1" -ReleaseKitRoot "%~dp0.." -RollbackInstallerPath "%SFL_ROLLBACK_INSTALLER%"
set "SFL_CANARY_EXIT=%ERRORLEVEL%"
popd

echo.
if "%SFL_CANARY_EXIT%"=="0" (
  echo [PASS] 120-minute app, packet, source-port, and operator gates passed.
  echo [PASS] This remains an unsigned internal canary; production promotion is still not allowed.
) else if "%SFL_CANARY_EXIT%"=="2" (
  echo [LIMITED PASS] Runtime and packet gates passed, but managed-switch faults remain unexcluded.
  echo [LIMITED PASS] Provide the sanitized ZIP, its SHA-256, and canary-control folder.
) else if "%SFL_CANARY_EXIT%"=="3" (
  echo [HOLD] Product rollback is not required, but collection or packet evidence is incomplete.
  echo [HOLD] Preserve all evidence and do not promote or immediately repeat the run.
) else if "%SFL_CANARY_EXIT%"=="10" (
  echo [ROLLBACK REQUIRED] A runtime hard gate failed after collection started.
  echo [ROLLBACK REQUIRED] Preserve evidence, close SmartFactoryLogger normally, then use the verified v1.0.20 cd8cfa6 installer.
) else (
  echo [FAILED] Canary preflight or control script failed with exit code %SFL_CANARY_EXIT%.
  echo [FAILED] No canary-driven product or setting change was performed.
)
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
