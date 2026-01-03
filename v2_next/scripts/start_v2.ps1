param(
  [string]$ConfigPath = "$env:APPDATA\\SmartFactoryLogger\\config.ini",
  [ValidateSet("REAL", "MOCK")][string]$Mode = "REAL",
  [switch]$NoFrontend,
  [switch]$HideWindow
)

$root = Split-Path -Parent $PSScriptRoot
$backendDir = $root
$frontendDir = Join-Path $root "frontend"
$windowStyle = if ($HideWindow) { "Hidden" } else { "Normal" }

if (Test-Path $ConfigPath) {
  $env:SFL_CONFIG_PATH = $ConfigPath
} else {
  Write-Host "Config not found: $ConfigPath"
}
$env:V2_MODE = $Mode

Start-Process -FilePath "python" -ArgumentList @("-m", "backend.main") -WorkingDirectory $backendDir -WindowStyle $windowStyle

if (-not $NoFrontend) {
  if (Test-Path $frontendDir) {
    Start-Process -FilePath "npm" -ArgumentList @("start") -WorkingDirectory $frontendDir -WindowStyle $windowStyle
  } else {
    Write-Host "Frontend directory not found: $frontendDir"
  }
}
