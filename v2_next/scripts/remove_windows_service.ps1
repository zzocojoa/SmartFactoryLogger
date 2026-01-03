param(
  [string]$ServiceName = "SmartFactoryLoggerV2"
)

try {
  $stopScript = Join-Path $PSScriptRoot "stop_windows_service.ps1"
  if (Test-Path $stopScript) {
    & $stopScript -ServiceName $ServiceName | Out-Null
  }
} catch {
  Write-Host "Graceful stop skipped."
}

& sc.exe stop $ServiceName | Out-Null
& sc.exe delete $ServiceName | Out-Null
