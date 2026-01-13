$ErrorActionPreference = "Stop"

Write-Host ">>> Building Real Hardware Stress Test Tool (Standalone)..."

# Ensure we are in the correct directory (Root of v2_next)
Set-Location "$PSScriptRoot"

# Build Standalone Script
# Dependencies are minimal: httpx only
pyinstaller --noconfirm --onefile --clean `
    --name "RealStressTest" `
    --collect-all "httpx" `
    run_real_stress_standalone.py

Write-Host ">>> Build Complete!"
Write-Host "Output: dist\RealStressTest.exe"
