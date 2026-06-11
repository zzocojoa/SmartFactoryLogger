param(
    [string]$BackendBaseUrl = "http://127.0.0.1:8000",
    [string]$SpotIp = "10.1.10.50",
    [string]$ConfigPath = "",
    [string]$InstallerPath = "",
    [string]$OutputPath = "",
    [int]$LogLookbackMinutes = 30,
    [int]$LiveLoopSeconds = 5,
    [int]$LiveLoopDelayMs = 35
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $env:APPDATA "SmartFactoryLogger\config.ini"
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputPath = Join-Path $env:TEMP "sfl-spot-live-server-qa-$stamp.json"
}

Add-Type -AssemblyName System.Net.Http

$httpClient = [System.Net.Http.HttpClient]::new()
$httpClient.Timeout = [TimeSpan]::FromSeconds(10)

function Get-HeaderValue {
    param(
        [System.Net.Http.HttpResponseMessage]$Response,
        [string]$Name
    )

    $values = New-Object "System.Collections.Generic.List[string]"
    if ($Response.Headers.TryGetValues($Name, [ref]$values)) {
        return ($values -join ", ")
    }

    $contentValues = New-Object "System.Collections.Generic.List[string]"
    if ($Response.Content.Headers.TryGetValues($Name, [ref]$contentValues)) {
        return ($contentValues -join ", ")
    }

    return $null
}

function Invoke-HttpProbe {
    param(
        [string]$Name,
        [string]$Uri,
        [string]$Method = "GET",
        [string]$SaveAs = "",
        [switch]$IncludeBodyText
    )

    $startedAt = Get-Date
    $timer = [System.Diagnostics.Stopwatch]::StartNew()

    try {
        $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::new($Method), $Uri)
        $response = $httpClient.SendAsync($request).GetAwaiter().GetResult()
        $bytes = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
        $timer.Stop()

        if (-not [string]::IsNullOrWhiteSpace($SaveAs)) {
            [System.IO.File]::WriteAllBytes($SaveAs, $bytes)
        }
        $bodyText = $null
        if ($IncludeBodyText) {
            $bodyText = [System.Text.Encoding]::UTF8.GetString($bytes)
        }

        return [ordered]@{
            name = $Name
            uri = $Uri
            method = $Method
            ok = [bool]$response.IsSuccessStatusCode
            status = [int]$response.StatusCode
            elapsed_ms = [math]::Round($timer.Elapsed.TotalMilliseconds, 1)
            content_type = Get-HeaderValue -Response $response -Name "Content-Type"
            cache_control = Get-HeaderValue -Response $response -Name "Cache-Control"
            retry_after = Get-HeaderValue -Response $response -Name "Retry-After"
            payload_rejection = Get-HeaderValue -Response $response -Name "X-Spot-Payload-Rejection"
            spot_live_source = Get-HeaderValue -Response $response -Name "X-Spot-Live-Image-Source"
            body_bytes = $bytes.Length
            body_text = $bodyText
            saved_as = if ([string]::IsNullOrWhiteSpace($SaveAs)) { $null } else { $SaveAs }
            started_at = $startedAt.ToString("o")
            error = $null
        }
    } catch {
        $timer.Stop()
        return [ordered]@{
            name = $Name
            uri = $Uri
            method = $Method
            ok = $false
            status = $null
            elapsed_ms = [math]::Round($timer.Elapsed.TotalMilliseconds, 1)
            content_type = $null
            cache_control = $null
            retry_after = $null
            payload_rejection = $null
            spot_live_source = $null
            body_bytes = 0
            body_text = $null
            saved_as = if ([string]::IsNullOrWhiteSpace($SaveAs)) { $null } else { $SaveAs }
            started_at = $startedAt.ToString("o")
            error = $_.Exception.Message
        }
    }
}

function Convert-JsonBody {
    param([object]$Probe)

    if ($null -eq $Probe -or [string]::IsNullOrWhiteSpace($Probe.body_text)) {
        return $null
    }

    try {
        return $Probe.body_text | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Get-NumericField {
    param(
        [object]$Object,
        [string[]]$Names
    )

    if ($null -eq $Object) {
        return $null
    }

    foreach ($name in $Names) {
        $property = $Object.PSObject.Properties[$name]
        if ($null -ne $property -and $null -ne $property.Value) {
            try {
                return [double]$property.Value
            } catch {
                return $null
            }
        }
    }

    return $null
}

function Get-StatsDelta {
    param(
        [object]$Before,
        [object]$After
    )

    $fields = [ordered]@{
        total_requests = @("total_requests", "requests_total", "request_count")
        error_count = @("error_count", "errors_total")
        total_http_error_count = @("total_http_error_count")
        total_http_4xx_count = @("total_http_4xx_count")
        total_http_5xx_count = @("total_http_5xx_count")
    }
    $delta = [ordered]@{}
    foreach ($field in $fields.Keys) {
        $beforeValue = Get-NumericField -Object $Before -Names $fields[$field]
        $afterValue = Get-NumericField -Object $After -Names $fields[$field]
        $delta[$field] = [ordered]@{
            before = $beforeValue
            after = $afterValue
            delta = if ($null -ne $beforeValue -and $null -ne $afterValue) { $afterValue - $beforeValue } else { $null }
        }
    }
    return $delta
}

function Invoke-LiveLoopProbe {
    param(
        [string]$Uri,
        [int]$DurationSeconds,
        [int]$DelayMs
    )

    if ($DurationSeconds -le 0) {
        return [ordered]@{
            enabled = $false
            duration_sec = 0
            delay_ms = $DelayMs
            requests = 0
            successes = 0
            failures = 0
            avg_elapsed_ms = $null
            max_elapsed_ms = $null
            first_content_type = $null
            first_cache_control = $null
            first_status = $null
            first_error = $null
            sample_failures = @()
        }
    }

    $deadline = (Get-Date).AddSeconds($DurationSeconds)
    $elapsedValues = New-Object "System.Collections.Generic.List[double]"
    $requests = 0
    $successes = 0
    $failures = 0
    $firstStatus = $null
    $firstContentType = $null
    $firstCacheControl = $null
    $firstError = $null
    $sampleFailures = New-Object "System.Collections.Generic.List[object]"
    $separator = if ($Uri.Contains("?")) { "&" } else { "?" }

    while ((Get-Date) -lt $deadline) {
        $probeUri = "{0}{1}t={2}-{3}" -f $Uri, $separator, [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds(), $requests
        $probe = Invoke-HttpProbe -Name "app-live-loop" -Uri $probeUri
        $requests += 1
        $elapsedValues.Add([double]$probe.elapsed_ms)
        if ($null -eq $firstStatus) {
            $firstStatus = $probe.status
            $firstContentType = $probe.content_type
            $firstCacheControl = $probe.cache_control
            $firstError = $probe.error
        }
        if ($probe.ok -and $probe.content_type -match "image/jpeg") {
            $successes += 1
        } else {
            $failures += 1
            if ($sampleFailures.Count -lt 5) {
                $sampleFailures.Add([ordered]@{
                    uri = $probeUri
                    status = $probe.status
                    content_type = $probe.content_type
                    error = $probe.error
                })
            }
        }
        if ($DelayMs -gt 0) {
            Start-Sleep -Milliseconds $DelayMs
        }
    }

    $avgElapsed = if ($elapsedValues.Count -gt 0) {
        [math]::Round(($elapsedValues | Measure-Object -Average).Average, 1)
    } else {
        $null
    }
    $maxElapsed = if ($elapsedValues.Count -gt 0) {
        [math]::Round(($elapsedValues | Measure-Object -Maximum).Maximum, 1)
    } else {
        $null
    }

    return [ordered]@{
        enabled = $true
        duration_sec = $DurationSeconds
        delay_ms = $DelayMs
        requests = $requests
        successes = $successes
        failures = $failures
        avg_elapsed_ms = $avgElapsed
        max_elapsed_ms = $maxElapsed
        first_content_type = $firstContentType
        first_cache_control = $firstCacheControl
        first_status = $firstStatus
        first_error = $firstError
        sample_failures = @($sampleFailures.ToArray())
    }
}

function Read-SpotConfigLines {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return [ordered]@{
            exists = $false
            path = $Path
            lines = @()
        }
    }

    $lines = Get-Content -LiteralPath $Path |
        Select-String -Pattern "^\[SPOT\]|^ip\s*=|^imageurl\s*=|^liveimageurl\s*=" |
        ForEach-Object { $_.Line }

    return [ordered]@{
        exists = $true
        path = $Path
        lines = @($lines)
    }
}

function Get-RecentSpotLogLines {
    param([int]$LookbackMinutes)

    $logRoot = Join-Path $env:APPDATA "SmartFactoryLogger"
    if (-not (Test-Path -LiteralPath $logRoot)) {
        return @()
    }

    $since = (Get-Date).AddMinutes(-1 * [math]::Max(1, $LookbackMinutes))
    $patterns = "Spot image fetch failed|upstream-timeout|retry-backoff-active|stale serve|invalid-image-html|live-backoff-active"
    return @(Get-ChildItem -Path $logRoot -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $since } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 40 |
        ForEach-Object {
            $filePath = $_.FullName
            Get-Content -LiteralPath $filePath -Tail 500 -ErrorAction SilentlyContinue |
                Select-String -Pattern $patterns -ErrorAction SilentlyContinue |
                ForEach-Object {
                    [ordered]@{
                        path = $filePath
                        line = $_.LineNumber
                        text = $_.Line
                    }
                }
        } |
        Select-Object -First 100 |
        ForEach-Object { $_ })
}

$artifact = [ordered]@{
    generated_at = (Get-Date).ToString("o")
    host = $env:COMPUTERNAME
    backend_base_url = $BackendBaseUrl.TrimEnd("/")
    spot_ip = $SpotIp
    log_lookback_minutes = $LogLookbackMinutes
    live_loop_requested = [ordered]@{
        seconds = $LiveLoopSeconds
        delay_ms = $LiveLoopDelayMs
    }
    config = Read-SpotConfigLines -Path $ConfigPath
    installer = $null
    direct_spot = @()
    app_endpoints = @()
    live_loop = $null
    stats_delta = $null
    logs = @()
    verdict = [ordered]@{
        passed = $false
        blockers = @()
        warnings = @()
    }
}

if (-not [string]::IsNullOrWhiteSpace($InstallerPath)) {
    if (Test-Path -LiteralPath $InstallerPath) {
        $installerItem = Get-Item -LiteralPath $InstallerPath
        $installerHash = Get-FileHash -Algorithm SHA256 -LiteralPath $InstallerPath
        $artifact.installer = [ordered]@{
            path = $installerItem.FullName
            bytes = $installerItem.Length
            last_write_time = $installerItem.LastWriteTime.ToString("o")
            sha256 = $installerHash.Hash
        }
    } else {
        $artifact.installer = [ordered]@{
            path = $InstallerPath
            error = "Installer path not found."
        }
        $artifact.verdict.warnings += "Installer path was provided but not found."
    }
}

$tempDir = Join-Path $env:TEMP ("sfl-spot-live-qa-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

$spotBase = "http://$SpotIp"
$artifact.direct_spot += Invoke-HttpProbe -Name "spot-image-jpg" -Uri "$spotBase/image.jpg" -SaveAs (Join-Path $tempDir "spot-image.jpg")
$artifact.direct_spot += Invoke-HttpProbe -Name "spot-newjpeg-jpg" -Uri "$spotBase/newjpeg.jpg" -SaveAs (Join-Path $tempDir "spot-newjpeg.jpg")
$artifact.direct_spot += Invoke-HttpProbe -Name "spot-image-ssi" -Uri "$spotBase/image.ssi"

$backend = $BackendBaseUrl.TrimEnd("/")
$artifact.app_endpoints += Invoke-HttpProbe -Name "app-spot-config" -Uri "$backend/api/spot/config"
$artifact.app_endpoints += Invoke-HttpProbe -Name "app-live-image" -Uri "$backend/api/spot/live_image?t=$(Get-Date -UFormat %s)" -SaveAs (Join-Path $tempDir "app-live-image.jpg")
$artifact.app_endpoints += Invoke-HttpProbe -Name "app-proxy-image" -Uri "$backend/api/spot/proxy_image?t=$(Get-Date -UFormat %s)" -SaveAs (Join-Path $tempDir "app-proxy-image.jpg")
$statsBefore = Invoke-HttpProbe -Name "app-stats-before-live-loop" -Uri "$backend/stats" -IncludeBodyText
$artifact.app_endpoints += $statsBefore
$artifact.live_loop = Invoke-LiveLoopProbe -Uri "$backend/api/spot/live_image" -DurationSeconds $LiveLoopSeconds -DelayMs $LiveLoopDelayMs
$statsAfter = Invoke-HttpProbe -Name "app-stats-after-live-loop" -Uri "$backend/stats" -IncludeBodyText
$artifact.app_endpoints += $statsAfter
$artifact.stats_delta = Get-StatsDelta -Before (Convert-JsonBody -Probe $statsBefore) -After (Convert-JsonBody -Probe $statsAfter)

$artifact.logs = Get-RecentSpotLogLines -LookbackMinutes $LogLookbackMinutes

$blockers = New-Object "System.Collections.Generic.List[string]"
$warnings = New-Object "System.Collections.Generic.List[string]"

$directImage = $artifact.direct_spot | Where-Object { $_.name -eq "spot-image-jpg" } | Select-Object -First 1
$directHtml = $artifact.direct_spot | Where-Object { $_.name -eq "spot-image-ssi" } | Select-Object -First 1
$live = $artifact.app_endpoints | Where-Object { $_.name -eq "app-live-image" } | Select-Object -First 1
$proxy = $artifact.app_endpoints | Where-Object { $_.name -eq "app-proxy-image" } | Select-Object -First 1
$stats = $artifact.app_endpoints | Where-Object { $_.name -eq "app-stats-after-live-loop" } | Select-Object -First 1

if (-not $directImage.ok -or ($directImage.content_type -notmatch "image/")) {
    $blockers.Add("Direct SPOT /image.jpg did not return an image response.")
}
if ($directHtml.ok -and ($directHtml.content_type -match "image/")) {
    $blockers.Add("Direct SPOT /image.ssi unexpectedly returned an image content type.")
}
if (-not $live.ok -or ($live.content_type -notmatch "image/jpeg")) {
    $blockers.Add("App /api/spot/live_image did not return HTTP 200 image/jpeg.")
}
if ($live.cache_control -notmatch "no-store") {
    $blockers.Add("App /api/spot/live_image did not include Cache-Control no-store.")
}
if (-not $proxy.ok -or ($proxy.content_type -notmatch "image/")) {
    $blockers.Add("Existing /api/spot/proxy_image did not return an image response.")
}
if (-not $stats.ok) {
    $blockers.Add("App /stats did not return HTTP 200.")
}
if ($artifact.live_loop.enabled -and $artifact.live_loop.failures -gt 0) {
    $blockers.Add("Live loop probe had one or more failed image responses.")
}
if ($artifact.logs.Count -gt 0) {
    $warnings.Add("Recent SPOT-related warning/error log lines were found; review logs in artifact.")
}

$artifact.verdict.blockers = @($blockers)
$artifact.verdict.warnings = @($warnings)
$artifact.verdict.passed = ($blockers.Count -eq 0)

$json = $artifact | ConvertTo-Json -Depth 8
Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8

Write-Host "SPOT live server QA artifact: $OutputPath"
Write-Host "Passed: $($artifact.verdict.passed)"
if ($blockers.Count -gt 0) {
    Write-Host "Blockers:" -ForegroundColor Red
    $blockers | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
    exit 1
}
if ($warnings.Count -gt 0) {
    Write-Host "Warnings:" -ForegroundColor Yellow
    $warnings | ForEach-Object { Write-Host " - $_" -ForegroundColor Yellow }
}
