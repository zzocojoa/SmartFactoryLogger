param(
  [string]$ServiceName = "SmartFactoryLoggerV2",
  [string]$DisplayName = "SmartFactoryLogger V2",
  [string]$ConfigPath = "$env:APPDATA\\SmartFactoryLogger\\config.ini",
  [ValidateSet("REAL", "MOCK")][string]$Mode = "REAL",
  [string]$WorkDir = ""
)

$scriptPath = Join-Path $PSScriptRoot "service_runner.ps1"
if (-not (Test-Path $scriptPath)) {
  Write-Error "service_runner.ps1 not found: $scriptPath"
  exit 1
}

if (-not $WorkDir) {
  $WorkDir = Split-Path -Parent $PSScriptRoot
}

$binPath = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -ConfigPath `"$ConfigPath`" -Mode $Mode -WorkDir `"$WorkDir`""
$binArg = "binPath= `"$binPath`""
$displayArg = "DisplayName= `"$DisplayName`""

& sc.exe create $ServiceName $binArg $displayArg start= auto
& sc.exe description $ServiceName "SmartFactoryLogger V2 backend service"
