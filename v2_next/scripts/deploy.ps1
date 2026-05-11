# Smart Factory Logger V2 배포 스크립트
# 사용법: .\deploy.ps1
# 시스템에 설치된 Grafana를 사용하는 포터블 배포 패키지를 생성한다.

Write-Host ">>> Starting Deployment Process..." -ForegroundColor Cyan

$ErrorActionPreference = "Stop"
$ScriptDir = (Get-Item "$(Split-Path -Parent $MyInvocation.MyCommand.Path)\..").FullName
Set-Location $ScriptDir
$BackendDir = Join-Path $ScriptDir "backend"
$BackendVenvDir = Join-Path $BackendDir ".venv"
$BackendVenvPython = Join-Path $BackendVenvDir "Scripts\python.exe"

function Invoke-CheckedCommand {
    param(
        [scriptblock]$Command,
        [string]$ErrorMessage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Error $ErrorMessage
        exit 1
    }
}

function Test-PortableFrontendPattern {
    param(
        [string]$BasePath,
        [string]$RelativePattern
    )

    $targetPattern = Join-Path $BasePath $RelativePattern
    $matches = Get-ChildItem -Path $targetPattern -ErrorAction SilentlyContinue
    return [bool]($matches -and $matches.Count -gt 0)
}

function Get-FrontendEntryAssets {
    param(
        [string]$FrontendDistPath
    )

    $indexPath = Join-Path $FrontendDistPath "index.html"
    if (-not (Test-Path $indexPath)) {
        return @()
    }

    $indexHtml = Get-Content -Raw -Path $indexPath
    $matches = [regex]::Matches($indexHtml, '(?:src|href)="\./(assets/[^"]+\.(?:js|css))"')
    $entryAssets = @()
    foreach ($match in $matches) {
        $entryAssets += $match.Groups[1].Value
    }

    return $entryAssets | Sort-Object -Unique
}

# =============================================================================
# 1. 프론트엔드 빌드
# =============================================================================
Write-Host ">>> Cleaning Frontend dist..." -ForegroundColor Yellow
if (Test-Path "frontend/dist") { Remove-Item "frontend/dist" -Recurse -Force }

Write-Host ">>> Building Frontend..." -ForegroundColor Yellow
Set-Location "frontend"
Invoke-CheckedCommand -Command { npm run build } -ErrorMessage "Frontend Build Failed"
Set-Location ".."

# =============================================================================
# 2. 백엔드 가상 환경 준비
# =============================================================================
Write-Host ">>> Preparing Backend Python Virtual Environment..." -ForegroundColor Yellow
if (-not (Test-Path $BackendVenvPython)) {
    Invoke-CheckedCommand -Command { python -m venv $BackendVenvDir } -ErrorMessage "Backend venv creation failed"
}
if (-not (Test-Path $BackendVenvPython)) {
    Write-Error "Backend venv python not found: $BackendVenvPython"
    exit 1
}

$env:PYTHONNOUSERSITE = "1"
Write-Host "    Using Python: $BackendVenvPython" -ForegroundColor Cyan

# =============================================================================
# 3. 백엔드 의존성 갱신
# =============================================================================
Write-Host ">>> Updating Backend Dependencies..." -ForegroundColor Yellow
Set-Location "backend"
Invoke-CheckedCommand -Command { & $BackendVenvPython -m pip install --disable-pip-version-check --require-virtualenv -r requirements-build.txt } -ErrorMessage "Backend Dependency Install Failed"

# =============================================================================
# 4. 번들링용 Playwright 브라우저 설치
# =============================================================================
Write-Host ">>> Installing Playwright Browsers (Local)..." -ForegroundColor Yellow
# Set-Location 위치 차이를 피하기 위해 절대 경로를 사용한다.
$BrowsersDir = Join-Path $ScriptDir "backend\browsers"
if (Test-Path $BrowsersDir) { Remove-Item $BrowsersDir -Recurse -Force }
New-Item -ItemType Directory -Path $BrowsersDir -Force | Out-Null

$env:PLAYWRIGHT_BROWSERS_PATH = $BrowsersDir
Invoke-CheckedCommand -Command { & $BackendVenvPython -m playwright install chromium } -ErrorMessage "Playwright Install Failed"
Write-Host "    Browsers installed to: $BrowsersDir" -ForegroundColor Green


# =============================================================================
# 5. PyInstaller 백엔드 패키징
# =============================================================================
Write-Host ">>> Packaging Backend (PyInstaller)..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }

# 버전 추출
Write-Host ">>> Extracting Version from frontend/package.json..." -ForegroundColor Yellow
$PackageJson = Get-Content -Raw -Path "../frontend/package.json" | ConvertFrom-Json
$Version = $PackageJson.version
Write-Host "    Detected Version: $Version" -ForegroundColor Cyan

# EXE 빌드
Invoke-CheckedCommand -Command { & $BackendVenvPython -m PyInstaller --noconfirm --clean build_specs\SmartFactoryBackend.spec } -ErrorMessage "Backend Packaging Failed"

Set-Location ".."

# =============================================================================
# 6. 포터블 디렉터리 구조 생성
# =============================================================================
Write-Host ">>> Creating Portable Directory Structure..." -ForegroundColor Yellow
$PortableDir = "dist\SmartFactory_Portable"
$PortablePath = Join-Path $ScriptDir $PortableDir

if (Test-Path $PortablePath) { Remove-Item $PortablePath -Recurse -Force }
New-Item -ItemType Directory -Path $PortablePath -Force | Out-Null

# EXE 복사
$ExeName = "SmartFactory_v$Version.exe"
$SourceExe = "backend\dist\SmartFactoryBackend.exe"
$DestExe = Join-Path $PortablePath $ExeName
Copy-Item -Path $SourceExe -Destination $DestExe -Force
Write-Host "    Copied EXE: $ExeName" -ForegroundColor Green

# mes_data 폴더 복사
$MesDataSource = "mes_data"
$MesDataDest = Join-Path $PortablePath "mes_data"
if (Test-Path $MesDataSource) {
    Copy-Item -Path $MesDataSource -Destination $MesDataDest -Recurse -Force
    Write-Host "    Copied mes_data folder" -ForegroundColor Green
}

# 브라우저 폴더 복사
$BrowsersSource = Join-Path $ScriptDir "backend\browsers"
$BrowsersDest = Join-Path $PortablePath "browsers"
if (Test-Path $BrowsersSource) {
    Copy-Item -Path $BrowsersSource -Destination $BrowsersDest -Recurse -Force
    Write-Host "    Copied browsers folder" -ForegroundColor Green
}

# 프런트 정적 번들을 EXE 옆 사이드카로 복사
$FrontendSource = Join-Path $ScriptDir "frontend\dist"
$FrontendRootDest = Join-Path $PortablePath "frontend"
$FrontendDistDest = Join-Path $FrontendRootDest "dist"
if (-not (Test-Path $FrontendSource)) {
    Write-Error "Frontend dist not found: $FrontendSource"
    exit 1
}
New-Item -ItemType Directory -Path $FrontendRootDest -Force | Out-Null
Copy-Item -Path $FrontendSource -Destination $FrontendRootDest -Recurse -Force
Write-Host "    Copied frontend dist sidecar" -ForegroundColor Green

$RequiredFrontendPatterns = @(
    "index.html",
    "manifest.json",
    "favicon.ico",
    "logo192.png",
    "logo512.png",
    "assets\logo_white.png",
    "assets\logo_color.png"
)
$EntryAssetPatterns = Get-FrontendEntryAssets -FrontendDistPath $FrontendDistDest
if ($EntryAssetPatterns.Count -gt 0) {
    $RequiredFrontendPatterns += $EntryAssetPatterns
} else {
    $RequiredFrontendPatterns += @(
        "assets\index-*.js",
        "assets\index-*.css"
    )
}
$MissingFrontendPatterns = @()
foreach ($RelativePattern in $RequiredFrontendPatterns) {
    if (-not (Test-PortableFrontendPattern -BasePath $FrontendDistDest -RelativePattern $RelativePattern)) {
        $MissingFrontendPatterns += $RelativePattern
    }
}
if ($MissingFrontendPatterns.Count -gt 0) {
    Write-Error ("Portable frontend sidecar verification failed: " + ($MissingFrontendPatterns -join ", "))
    exit 1
}
Write-Host "    Verified frontend dist sidecar" -ForegroundColor Green

# =============================================================================
# 7. 시스템 Grafana를 사용하는 실행 스크립트 생성
# =============================================================================
Write-Host ">>> Creating Launcher Scripts..." -ForegroundColor Yellow

# start.bat - Windows Grafana 서비스를 사용한다.
$StartBatContent = @"
@echo off
title Smart Factory Logger
echo ============================================
echo   Smart Factory Logger v$Version
echo ============================================
echo.

cd /d "%~dp0"

REM Set Playwright Browsers Path to local bundled folder
set PLAYWRIGHT_BROWSERS_PATH=%~dp0browsers


REM Check and start Grafana Windows Service
echo Checking Grafana service...
sc query Grafana >nul 2>&1
if %errorlevel% equ 0 (
    echo Starting Grafana service...
    net start Grafana 2>nul
    echo Grafana available at http://localhost:3030
) else (
    echo [WARNING] Grafana service not found.
    echo Please install Grafana from: https://grafana.com/grafana/download
)

echo.
echo Starting SmartFactory Backend...
start "" "$ExeName"
echo SmartFactory starting on http://localhost:8000

echo.
echo ============================================
echo   All services started!
echo   - Dashboard: http://localhost:8000
echo   - Grafana:   http://localhost:3030
echo ============================================
echo.
timeout /t 5 /nobreak > nul
REM Browser is opened automatically by the EXE
"@
Set-Content -Path (Join-Path $PortablePath "start.bat") -Value $StartBatContent -Encoding ASCII
Write-Host "    start.bat created" -ForegroundColor Green

# stop.bat
$StopBatContent = @"
@echo off
echo Stopping SmartFactory...
taskkill /IM SmartFactory*.exe /F 2>nul
echo.
echo Note: Grafana service is not stopped (other apps may use it).
echo To stop Grafana manually: net stop Grafana
echo.
echo SmartFactory stopped.
pause
"@
Set-Content -Path (Join-Path $PortablePath "stop.bat") -Value $StopBatContent -Encoding ASCII
Write-Host "    stop.bat created" -ForegroundColor Green

# setup_grafana.bat - Grafana 설정 도우미
$SetupGrafanaBatContent = @"
@echo off
title Grafana Setup for SmartFactory
echo ============================================
echo   Grafana Configuration for SmartFactory
echo ============================================
echo.
echo This script will configure Grafana for embedding.
echo Please run as Administrator.
echo.

set GRAFANA_CONF="C:\Program Files\GrafanaLabs\grafana\conf\custom.ini"

echo Creating custom.ini with required settings...
(
echo [server]
echo http_port = 3030
echo.
echo [security]
echo allow_embedding = true
echo.
echo [auth.anonymous]
echo enabled = true
echo org_role = Viewer
) > %GRAFANA_CONF%

echo.
echo Configuration written to: %GRAFANA_CONF%
echo.
echo Restarting Grafana service...
net stop Grafana
net start Grafana

echo.
echo ============================================
echo   Grafana configured successfully!
echo   Access: http://localhost:3030
echo ============================================
pause
"@
Set-Content -Path (Join-Path $PortablePath "setup_grafana.bat") -Value $SetupGrafanaBatContent -Encoding ASCII
Write-Host "    setup_grafana.bat created (run once on target machine)" -ForegroundColor Green

# =============================================================================
# 8. README 생성
# =============================================================================
$ReadmeContent = @"
# SmartFactory Logger v$Version

## Quick Start
1. Run ``start.bat`` to launch the application
2. Dashboard opens automatically at http://localhost:8000

## First-Time Setup (Grafana)
If Grafana is not configured:
1. Run ``setup_grafana.bat`` as Administrator
2. This configures Grafana for embedding (port 3030)

## Requirements
- Windows 10/11
- Grafana OSS installed from https://grafana.com/grafana/download

## Files
- ``start.bat`` - Start all services
- ``stop.bat`` - Stop SmartFactory
- ``setup_grafana.bat`` - Configure Grafana (run once as Admin)
- ``mes_data/`` - Database folder

## SPOT Actuator Config
- Default ``[SPOT] actuatorstep`` is ``50`` for physical actuator movement.
- Packaged config is loaded from ``config.ini`` or ``config\config.ini`` next to this launcher when present.
- Otherwise existing machine config is loaded from ``%APPDATA%\SmartFactoryLogger\config.ini``.
- ``[SPOT] actuatorip`` falls back to legacy ``[ACTUATOR] actuatorip`` and then ``[SPOT] ip``.
- ``[SPOT] actuatorurl`` defaults to ``http://{actuatorip}/scan.cgi`` when omitted.
"@
Set-Content -Path (Join-Path $PortablePath "README.txt") -Value $ReadmeContent -Encoding UTF8
Write-Host "    README.txt created" -ForegroundColor Green

# =============================================================================
# 9. 최종 ZIP 생성
# =============================================================================
Write-Host ">>> Creating Final ZIP Package..." -ForegroundColor Yellow
$ZipName = "SmartFactory_v$Version`_Portable.zip"
$ZipPath = Join-Path (Join-Path $ScriptDir "dist") $ZipName

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path $PortablePath -DestinationPath $ZipPath -Force
Write-Host "    ZIP created: $ZipName" -ForegroundColor Green

# =============================================================================
# 완료
# =============================================================================
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host ">>> Deployment Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Portable Folder: $PortablePath" -ForegroundColor Cyan
Write-Host "ZIP Package:     dist\$ZipName" -ForegroundColor Cyan
Write-Host ""
Write-Host "On target machine:" -ForegroundColor Yellow
Write-Host "  1. Install Grafana OSS (if not installed)"
Write-Host "  2. Run setup_grafana.bat as Administrator (first time only)"
Write-Host "  3. Run start.bat"
Write-Host ""
