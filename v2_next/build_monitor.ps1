$ErrorActionPreference = "Stop"

Write-Host ">>> Building Resource Monitor..."

# Ensure we are in the correct directory
Set-Location "$PSScriptRoot"

# Build
pyinstaller --noconfirm --onefile --clean `
    --name "ResourceMonitor" `
    monitor_resource.py

Write-Host ">>> Build Complete!"
Write-Host "Output: dist\ResourceMonitor.exe"
