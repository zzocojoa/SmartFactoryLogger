$ErrorActionPreference = "Stop"

Write-Host ">>> Building Real Hardware Stress Test Tool..."

# Ensure we are in the correct directory
Set-Location "$PSScriptRoot\backend"

# Build the executable
# Using --paths "." to include current directory modules
pyinstaller --noconfirm --onefile --clean `
    --name "RealStressTest" `
    --paths "." `
    --hidden-import "services" `
    --hidden-import "models" `
    --hidden-import "config" `
    --collect-all "modbus_tk" `
    run_real_stress.py

Write-Host ">>> Build Complete!"
Write-Host "Output: backend\dist\RealStressTest.exe"
