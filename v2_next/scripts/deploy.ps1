# Deploy Script for Smart Factory Logger V2
# Usage: .\deploy.ps1
# Creates a portable deployment package (uses system-installed Grafana)

Write-Host ">>> Starting Deployment Process..." -ForegroundColor Cyan

$ErrorActionPreference = "Stop"
$ScriptDir = (Get-Item "$(Split-Path -Parent $MyInvocation.MyCommand.Path)\..").FullName
Set-Location $ScriptDir

# =============================================================================
# 1. Build Frontend
# =============================================================================
Write-Host ">>> Cleaning Frontend dist..." -ForegroundColor Yellow
if (Test-Path "frontend/dist") { Remove-Item "frontend/dist" -Recurse -Force }

Write-Host ">>> Building Frontend..." -ForegroundColor Yellow
Set-Location "frontend"
npm run build
if ($LASTEXITCODE -ne 0) { Write-Error "Frontend Build Failed"; exit 1 }
Set-Location ".."

# =============================================================================
# 2. Update Backend Dependencies
# =============================================================================
Write-Host ">>> Updating Backend Dependencies..." -ForegroundColor Yellow
Set-Location "backend"
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Error "Backend Dependency Install Failed"; exit 1 }

# =============================================================================
# 3. Install Playwright Browsers (Local for bundling)
# =============================================================================
Write-Host ">>> Installing Playwright Browsers (Local)..." -ForegroundColor Yellow
# Use Absolute Path to avoid alignment issues with Set-Location
$BrowsersDir = Join-Path $ScriptDir "backend\browsers"
if (Test-Path $BrowsersDir) { Remove-Item $BrowsersDir -Recurse -Force }
New-Item -ItemType Directory -Path $BrowsersDir -Force | Out-Null

$env:PLAYWRIGHT_BROWSERS_PATH = $BrowsersDir
python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { Write-Error "Playwright Install Failed"; exit 1 }
Write-Host "    Browsers installed to: $BrowsersDir" -ForegroundColor Green


# =============================================================================
# 4. Package Backend with PyInstaller
# =============================================================================
Write-Host ">>> Packaging Backend (PyInstaller)..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }

# Extract Version
Write-Host ">>> Extracting Version from frontend/package.json..." -ForegroundColor Yellow
$PackageJson = Get-Content -Raw -Path "../frontend/package.json" | ConvertFrom-Json
$Version = $PackageJson.version
Write-Host "    Detected Version: $Version" -ForegroundColor Cyan

# Generate version.py
$VersionContent = "__version__ = `"$Version`""
Set-Content -Path "version.py" -Value $VersionContent
Write-Host "    version.py updated to $Version" -ForegroundColor Green

# Build EXE
python -m PyInstaller --noconfirm --clean SmartFactoryBackend.spec
if ($LASTEXITCODE -ne 0) { Write-Error "Backend Packaging Failed"; exit 1 }

Set-Location ".."

# =============================================================================
# 5. Create Portable Directory Structure
# =============================================================================
Write-Host ">>> Creating Portable Directory Structure..." -ForegroundColor Yellow
$PortableDir = "dist\SmartFactory_Portable"
$PortablePath = Join-Path $ScriptDir $PortableDir

if (Test-Path $PortablePath) { Remove-Item $PortablePath -Recurse -Force }
New-Item -ItemType Directory -Path $PortablePath -Force | Out-Null

# Copy EXE
$ExeName = "SmartFactory_v$Version.exe"
$SourceExe = "backend\dist\SmartFactoryBackend.exe"
$DestExe = Join-Path $PortablePath $ExeName
Copy-Item -Path $SourceExe -Destination $DestExe -Force
Write-Host "    Copied EXE: $ExeName" -ForegroundColor Green

# Copy mes_data folder (database)
$MesDataSource = "mes_data"
$MesDataDest = Join-Path $PortablePath "mes_data"
if (Test-Path $MesDataSource) {
    Copy-Item -Path $MesDataSource -Destination $MesDataDest -Recurse -Force
    Write-Host "    Copied mes_data folder" -ForegroundColor Green
}

# Copy browsers folder
$BrowsersSource = Join-Path $ScriptDir "backend\browsers"
$BrowsersDest = Join-Path $PortablePath "browsers"
if (Test-Path $BrowsersSource) {
    Copy-Item -Path $BrowsersSource -Destination $BrowsersDest -Recurse -Force
    Write-Host "    Copied browsers folder" -ForegroundColor Green
}

# =============================================================================
# 6. Create Launcher Scripts (Uses System Grafana)
# =============================================================================
Write-Host ">>> Creating Launcher Scripts..." -ForegroundColor Yellow

# start.bat - Uses Windows Grafana Service
$StartBatContent = @"
@echo off
title Smart Factory Logger
echo ============================================
echo   Smart Factory Logger v$Version
echo ============================================
echo.

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

# setup_grafana.bat - Grafana configuration helper
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
# 7. Create README
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
"@
Set-Content -Path (Join-Path $PortablePath "README.txt") -Value $ReadmeContent -Encoding UTF8
Write-Host "    README.txt created" -ForegroundColor Green

# =============================================================================
# 8. Create Final ZIP
# =============================================================================
Write-Host ">>> Creating Final ZIP Package..." -ForegroundColor Yellow
$ZipName = "SmartFactory_v$Version`_Portable.zip"
$ZipPath = Join-Path (Join-Path $ScriptDir "dist") $ZipName

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path $PortablePath -DestinationPath $ZipPath -Force
Write-Host "    ZIP created: $ZipName" -ForegroundColor Green

# =============================================================================
# Complete
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
