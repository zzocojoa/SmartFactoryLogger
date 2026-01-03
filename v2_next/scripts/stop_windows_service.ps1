param(
  [string]$ServiceName = "SmartFactoryLoggerV2",
  [string]$ApiBase = "http://127.0.0.1:8000"
)

try {
  Invoke-RestMethod -Method Post -Uri "$ApiBase/api/control/shutdown" -Body (@{ reason = "service stop" } | ConvertTo-Json) -ContentType "application/json"
} catch {
  Write-Host "Shutdown API not reachable."
}

Start-Sleep -Seconds 2
& sc.exe stop $ServiceName | Out-Null
