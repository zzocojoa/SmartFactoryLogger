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

# One-file mode with bundled frontend
# Windows separator for add-data is ';'
# Use python -m PyInstaller to ensure we use the current virtualenv context
# Use --collect-all to force full inclusion of Pydantic v2 binaries/data
python -m PyInstaller --noconfirm --onefile --name SmartFactoryBackend --clean --add-data "../frontend/dist;frontend/dist" --collect-all "pydantic" --collect-all "pydantic_core" server_entry.py

if ($LASTEXITCODE -ne 0) { Write-Error "Backend Packaging Failed"; exit 1 }

Write-Host ">>> Deployment Build Complete!" -ForegroundColor Green
$ExePath = Resolve-Path "dist/SmartFactoryBackend.exe"
Write-Host "    Output File: $ExePath"
Write-Host "    You can run this single file directly."
Set-Location ".."
