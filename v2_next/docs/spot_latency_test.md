# SPOT Latency Test (PowerShell)

Use these as single-line commands (no line breaks). Paste and run in PowerShell.

## Camera direct image (single request)

```powershell
$ms=(Measure-Command { Invoke-WebRequest -UseBasicParsing -Uri ("http://10.1.10.50/image.jpg?ts="+[DateTime]::UtcNow.Ticks) -TimeoutSec 5 | Out-Null }).TotalMilliseconds; "ms=$([Math]::Round($ms,1))"
```

## Camera direct image (20 samples)

```powershell
$times=1..20|%{ (Measure-Command { Invoke-WebRequest -UseBasicParsing -Uri ("http://10.1.10.50/image.jpg?ts="+[DateTime]::UtcNow.Ticks) -TimeoutSec 5 | Out-Null }).TotalMilliseconds; Start-Sleep -Milliseconds 200 }; $s=$times|Measure-Object -Average -Minimum -Maximum; "avg=$([Math]::Round($s.Average,1))ms min=$([Math]::Round($s.Minimum,1))ms max=$([Math]::Round($s.Maximum,1))ms"
```

## Proxy image via EXE (20 samples)

```powershell
$times=1..20|%{ (Measure-Command { Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:8000/api/spot/proxy_image?ts="+[DateTime]::UtcNow.Ticks) -TimeoutSec 5 | Out-Null }).TotalMilliseconds; Start-Sleep -Milliseconds 200 }; $s=$times|Measure-Object -Average -Minimum -Maximum; "avg=$([Math]::Round($s.Average,1))ms min=$([Math]::Round($s.Minimum,1))ms max=$([Math]::Round($s.Maximum,1))ms"
```

```
- 결과
PS C:\WINDOWS\system32> $ms=(Measure-Command { Invoke-WebRequest -UseBasicParsing -Uri ("http://10.1.10.50/image.jpg?ts="+[DateTime]::UtcNow.Ticks) -TimeoutSec 5 | Out-Null }).TotalMilliseconds; "ms=$([Math]::Round($ms,1))"
ms=681.9
PS C:\WINDOWS\system32> $times=1..20|%{ (Measure-Command { Invoke-WebRequest -UseBasicParsing -Uri ("http://10.1.10.50/image.jpg?ts="+[DateTime]::UtcNow.Ticks) -TimeoutSec 5 | Out-Null }).TotalMilliseconds; Start-Sleep -Milliseconds 200 }; $s=$times|Measure-Object -Average -Minimum -Maximum; "avg=$([Math]::Round($s.Average,1))ms min=$([Math]::Round($s.Minimum,1))ms max=$([Math]::Round($s.Maximum,1))ms"
avg=64.7ms min=21ms max=157.2ms
PS C:\WINDOWS\system32> $times=1..20|%{ (Measure-Command { Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:8000/api/spot/proxy_image?ts="+[DateTime]::UtcNow.Ticks) -TimeoutSec 5 | Out-Null }).TotalMilliseconds; Start-Sleep -Milliseconds 200 }; $s=$times|Measure-Object -Average -Minimum -Maximum; "avg=$([Math]::Round($s.Average,1))ms min=$([Math]::Round($s.Minimum,1))ms max=$([Math]::Round($s.Maximum,1))ms"
avg=83.1ms min=19.5ms max=327.2ms
```
