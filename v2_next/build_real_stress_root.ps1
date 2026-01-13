$ErrorActionPreference = "Stop"

Write-Host ">>> Building Real Hardware Stress Test Tool (Root)..."

# Ensure we are in the correct directory (Root of v2_next)
Set-Location "$PSScriptRoot"

# Build
# Include backend package
pyinstaller --noconfirm --onefile --clean `
    --name "RealStressTest" `
    --paths "." `
    --paths "backend" `
    --collect-all "modbus_tk" `
    --hidden-import "backend" `
    --hidden-import "backend.services" `
    --hidden-import "backend.services.plc_service" `
    --hidden-import "backend.services.spot_service" `
    --hidden-import "backend.services.logger_service" `
    --hidden-import "backend.config" `
    run_real_stress_root.py

Write-Host ">>> Build Complete!"
Write-Host "Output: dist\RealStressTest.exe"
