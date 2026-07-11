param(
    [string]$BackendBaseUrl = "http://127.0.0.1:8000",
    [string]$SpotIp = "",
    [string]$ConfigPath = "",
    [string]$InstallerPath = "",
    [string]$OutputPath = "",
    [int]$ObservationSeconds = 30,
    [int]$LogLookbackMinutes = 30
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $env:APPDATA "SmartFactoryLogger\config.ini"
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputPath = Join-Path $env:TEMP "sfl-spot-image-server-qa-$stamp.json"
}

function Get-ConfiguredSpotIp {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    $inSpotSection = $false
    foreach ($line in Get-Content -LiteralPath $Path -ErrorAction Stop) {
        $trimmed = $line.Trim()
        if ($trimmed -match "^\[(.+)\]$") {
            $inSpotSection = $Matches[1] -eq "SPOT"
            continue
        }
        if ($inSpotSection -and $trimmed -match "^ip\s*=\s*(.+)$") {
            return $Matches[1].Trim()
        }
    }
    return $null
}

if ([string]::IsNullOrWhiteSpace($SpotIp)) {
    $SpotIp = Get-ConfiguredSpotIp -Path $ConfigPath
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
        [switch]$IncludeBodyText
    )
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $response = $null
    try {
        $response = $httpClient.GetAsync($Uri).GetAwaiter().GetResult()
        $bytes = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
        $timer.Stop()
        return [ordered]@{
            name = $Name
            ok = [bool]$response.IsSuccessStatusCode
            status = [int]$response.StatusCode
            elapsed_ms = [math]::Round($timer.Elapsed.TotalMilliseconds, 1)
            content_type = Get-HeaderValue -Response $response -Name "Content-Type"
            cache_control = Get-HeaderValue -Response $response -Name "Cache-Control"
            image_source = Get-HeaderValue -Response $response -Name "X-Spot-Image-Source"
            body_bytes = $bytes.Length
            body_text = if ($IncludeBodyText) { [Text.Encoding]::UTF8.GetString($bytes) } else { $null }
            error = $null
        }
    } catch {
        $timer.Stop()
        return [ordered]@{
            name = $Name
            ok = $false
            status = $null
            elapsed_ms = [math]::Round($timer.Elapsed.TotalMilliseconds, 1)
            content_type = $null
            cache_control = $null
            image_source = $null
            body_bytes = 0
            body_text = $null
            error = $_.Exception.Message
        }
    } finally {
        if ($null -ne $response) {
            $response.Dispose()
        }
    }
}

function Invoke-CompletionDrivenObservation {
    param(
        [string]$Uri,
        [int]$DurationSeconds
    )
    $deadline = (Get-Date).AddSeconds([math]::Max(0, $DurationSeconds))
    $requests = 0
    $successes = 0
    $failures = 0
    $latencies = New-Object "System.Collections.Generic.List[double]"
    $samples = New-Object "System.Collections.Generic.List[object]"

    while ((Get-Date) -lt $deadline) {
        # The next request starts only after the previous response is fully read.
        $probe = Invoke-HttpProbe -Name "app-image-observation" -Uri $Uri
        $requests += 1
        $latencies.Add([double]$probe.elapsed_ms)
        if ($probe.ok -and $probe.content_type -match "^image/jpeg") {
            $successes += 1
        } else {
            $failures += 1
            if ($samples.Count -lt 5) {
                $samples.Add($probe)
            }
        }
    }

    return [ordered]@{
        duration_sec = [math]::Max(0, $DurationSeconds)
        request_mode = "completion_driven"
        requests = $requests
        successes = $successes
        failures = $failures
        avg_elapsed_ms = if ($latencies.Count) {
            [math]::Round(($latencies | Measure-Object -Average).Average, 1)
        } else { $null }
        max_elapsed_ms = if ($latencies.Count) {
            [math]::Round(($latencies | Measure-Object -Maximum).Maximum, 1)
        } else { $null }
        failure_samples = $samples
    }
}

$backend = $BackendBaseUrl.TrimEnd("/")
$artifact = [ordered]@{
    schema_version = "spot-image-server-qa-v1"
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    config_path_exists = Test-Path -LiteralPath $ConfigPath -PathType Leaf
    spot_ip_configured = -not [string]::IsNullOrWhiteSpace($SpotIp)
    installer = if (
        -not [string]::IsNullOrWhiteSpace($InstallerPath) -and
        (Test-Path -LiteralPath $InstallerPath -PathType Leaf)
    ) {
        [ordered]@{
            file = Split-Path -Leaf $InstallerPath
            sha256 = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    } else { $null }
    direct_spot = $null
    app_config = Invoke-HttpProbe -Name "app-config" -Uri "$backend/api/spot/config" -IncludeBodyText
    app_image = Invoke-HttpProbe -Name "app-image" -Uri "$backend/api/spot/image.jpg"
    health = Invoke-HttpProbe -Name "health" -Uri "$backend/health" -IncludeBodyText
    stats_before = Invoke-HttpProbe -Name "stats-before" -Uri "$backend/stats" -IncludeBodyText
    observation = $null
    stats_after = $null
    recent_image_errors = @()
    blockers = @()
}

if ($artifact.spot_ip_configured) {
    $artifact.direct_spot = Invoke-HttpProbe -Name "spot-image-jpg" -Uri "http://$SpotIp/image.jpg"
}
$artifact.observation = Invoke-CompletionDrivenObservation -Uri "$backend/api/spot/image.jpg" -DurationSeconds $ObservationSeconds
$artifact.stats_after = Invoke-HttpProbe -Name "stats-after" -Uri "$backend/stats" -IncludeBodyText

$logRoot = Join-Path $env:APPDATA "SmartFactoryLogger\logs"
if (Test-Path -LiteralPath $logRoot -PathType Container) {
    $cutoff = (Get-Date).AddMinutes(-[math]::Abs($LogLookbackMinutes))
    $artifact.recent_image_errors = @(
        Get-ChildItem -LiteralPath $logRoot -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -ge $cutoff } |
            ForEach-Object {
                Select-String -LiteralPath $_.FullName -Pattern (
                    "spot_image|upstream-timeout|upstream-http-error|" +
                    "invalid-image-html|invalid-image-payload|empty-body"
                ) -ErrorAction SilentlyContinue
            } |
            Select-Object -First 100 |
            ForEach-Object { $_.Line }
    )
}

$blockers = New-Object "System.Collections.Generic.List[string]"
if (-not $artifact.spot_ip_configured) {
    $blockers.Add("SPOT IP is not configured.")
} elseif (-not $artifact.direct_spot.ok -or $artifact.direct_spot.content_type -notmatch "^image/jpeg") {
    $blockers.Add("Direct SPOT /image.jpg did not return HTTP 200 image/jpeg.")
}
if (-not $artifact.app_image.ok -or $artifact.app_image.content_type -notmatch "^image/jpeg") {
    $blockers.Add("App /api/spot/image.jpg did not return HTTP 200 image/jpeg.")
}
if ($artifact.app_image.cache_control -notmatch "no-store") {
    $blockers.Add("App /api/spot/image.jpg did not include Cache-Control no-store.")
}
if ($artifact.observation.failures -gt 0) {
    $blockers.Add("Completion-driven image observation contained failures.")
}
$artifact.blockers = $blockers

$outputDirectory = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}
$artifact | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $OutputPath -Encoding utf8
$httpClient.Dispose()

Write-Host "SPOT image server QA artifact: $OutputPath"
Write-Host "blockers=$($blockers.Count)"
if ($blockers.Count -gt 0) {
    exit 1
}
