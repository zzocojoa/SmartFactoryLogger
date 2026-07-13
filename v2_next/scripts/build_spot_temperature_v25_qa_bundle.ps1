param(
    [string]$OutputDirectory = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
$validatorScript = Join-Path $repoRoot "scripts\validate_csv_v2_shadow.py"
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $repoRoot "dist\spot-temperature-v25-qa"
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$workDirectory = Join-Path $repoRoot "backend\build\spot-temperature-v25-qa"

if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    throw "Python venv not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $validatorScript -PathType Leaf)) {
    throw "Validator source not found: $validatorScript"
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $workDirectory -Force | Out-Null

Push-Location $repoRoot
try {
    & $pythonExe -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --name validate_csv_v2_shadow `
        --paths $repoRoot `
        --distpath $OutputDirectory `
        --workpath (Join-Path $workDirectory "work") `
        --specpath $workDirectory `
        $validatorScript
    if ($LASTEXITCODE -ne 0) {
        throw "Portable validator build failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "qa_spot_temperature_v25.cmd") `
    -Destination $OutputDirectory -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "qa_spot_temperature_v25.ps1") `
    -Destination $OutputDirectory -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "apply_spot_temperature_v25_attestation.cmd") `
    -Destination $OutputDirectory -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "apply_spot_temperature_v25_attestation.ps1") `
    -Destination $OutputDirectory -Force
$readmeSource = Get-ChildItem -LiteralPath (Join-Path $repoRoot "docs") `
    -Filter "spot_temperature_v25_one_command_qa.md" -File -Recurse |
    Select-Object -First 1
if ($null -eq $readmeSource) {
    throw "QA README source was not found."
}
Copy-Item -LiteralPath $readmeSource.FullName `
    -Destination (Join-Path $OutputDirectory "README.md") -Force

$requiredFiles = @(
    "qa_spot_temperature_v25.cmd",
    "qa_spot_temperature_v25.ps1",
    "apply_spot_temperature_v25_attestation.cmd",
    "apply_spot_temperature_v25_attestation.ps1",
    "validate_csv_v2_shadow.exe",
    "README.md"
)
$missing = @(
    $requiredFiles | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $OutputDirectory $_) -PathType Leaf)
    }
)
if ($missing.Count -gt 0) {
    throw "QA bundle is incomplete: $($missing -join ', ')"
}

$manifest = [ordered]@{
    schema_version = "spot-temperature-v25-qa-bundle-v1"
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    files = @(
        $requiredFiles | ForEach-Object {
            $path = Join-Path $OutputDirectory $_
            [ordered]@{
                name = $_
                size_bytes = (Get-Item -LiteralPath $path).Length
                sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        }
    )
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content `
    -LiteralPath (Join-Path $OutputDirectory "bundle-manifest.json") -Encoding UTF8

$archivePath = "$OutputDirectory.zip"
if (Test-Path -LiteralPath $archivePath -PathType Leaf) {
    Remove-Item -LiteralPath $archivePath -Force
}
Compress-Archive -Path (Join-Path $OutputDirectory "*") -DestinationPath $archivePath -CompressionLevel Optimal

Write-Host ""
Write-Host "SPOT Temperature v2.5 QA bundle created:" -ForegroundColor Green
Write-Host $OutputDirectory
Write-Host $archivePath
Write-Host "Copy this entire folder to the server computer."
