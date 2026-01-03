param(
  [string]$ConfigPath = "$env:APPDATA\\SmartFactoryLogger\\config.ini",
  [ValidateSet("REAL", "MOCK")][string]$Mode = "REAL",
  [string]$WorkDir = ""
)

if ($WorkDir) {
  Set-Location $WorkDir
} else {
  Set-Location (Split-Path -Parent $PSScriptRoot)
}

if (Test-Path $ConfigPath) {
  $env:SFL_CONFIG_PATH = $ConfigPath
}
$env:V2_MODE = $Mode

python -m backend.main
