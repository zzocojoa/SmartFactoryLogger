# Deploy Script for Smart Factory Logger V2
# Usage: .\deploy.ps1

Write-Host ">>> Starting Deployment Process..." -ForegroundColor Cyan

# 1. Build Frontend
Write-Host ">>> Building Frontend..." -ForegroundColor Yellow
Set-Location "frontend"
npm run build
if ($LASTEXITCODE -ne 0) { Write-Error "Frontend Build Failed"; exit 1 }
Set-Location ".."

# 2. Package Backend (clean build)
Write-Host ">>> Packaging Backend (PyInstaller - Single File)..." -ForegroundColor Yellow
Set-Location "backend"
# Remove old dist if exists
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

# Extract Version from package.json
Write-Host ">>> Extracting Version from frontend/package.json..." -ForegroundColor Yellow
$PackageJson = Get-Content -Raw -Path "../frontend/package.json" | ConvertFrom-Json
$Version = $PackageJson.version
Write-Host "    Detected Version: $Version" -ForegroundColor Cyan

# Generate backend/version.py
$VersionFile = "version.py"
Write-Host ">>> Generating $VersionFile..." -ForegroundColor Yellow
$VersionContent = "__version__ = `"$Version`""
Set-Content -Path $VersionFile -Value $VersionContent
Write-Host "    $VersionFile updated to $Version" -ForegroundColor Green

# One-file mode with bundled frontend
# Use python -m PyInstaller with the spec file to ensure all configs (assets, icon, noconsole) are applied
python -m PyInstaller --noconfirm --clean SmartFactoryBackend.spec

if ($LASTEXITCODE -ne 0) { Write-Error "Backend Packaging Failed"; exit 1 }

Write-Host ">>> Deployment Build Complete!" -ForegroundColor Green
$ExePath = Resolve-Path "dist/SmartFactoryBackend.exe"
Write-Host "    Output File: $ExePath"
Write-Host "    You can run this single file directly."
Set-Location ".."
