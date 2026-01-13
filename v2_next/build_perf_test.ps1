$ErrorActionPreference = "Stop"

Write-Host ">>> Building CSV Performance Test Tool..."

# Ensure we are in the correct directory
Set-Location "$PSScriptRoot\backend"

# Install PyInstaller if not already (should be there)
# pip install pyinstaller

# Build the executable
# --onefile: Create a single EXE
# --name: Output filename
# --hidden-import: Ensure necessary modules are included if dynamic
# --clean: Clean cache
pyinstaller --noconfirm --onefile --clean `
    --name "CSVPerformanceTest" `
    --hidden-import "services" `
    --hidden-import "models" `
    --paths "." `
    check_csv_perf.py

Write-Host ">>> Build Complete!"
Write-Host "Output: backend\dist\CSVPerformanceTest.exe"
