param(
  [string]$TaskName = "SmartFactoryLoggerV2",
  [string]$ConfigPath = "$env:APPDATA\\SmartFactoryLogger\\config.ini",
  [ValidateSet("REAL", "MOCK")][string]$Mode = "REAL"
)

$scriptPath = Join-Path $PSScriptRoot "start_v2.ps1"
if (-not (Test-Path $scriptPath)) {
  Write-Error "start_v2.ps1 not found: $scriptPath"
  exit 1
}

$args = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -ConfigPath `"$ConfigPath`" -Mode $Mode -HideWindow"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $args
$trigger = New-ScheduledTaskTrigger -AtLogOn

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Trigger $trigger `
  -Description "SmartFactoryLogger V2 auto-start" `
  -User $env:USERNAME `
  -RunLevel LeastPrivilege `
  -Force
