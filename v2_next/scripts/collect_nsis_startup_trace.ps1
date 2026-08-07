param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,

    [string]$OutputDirectory = "",

    [string]$LogPath = "",

    [int]$TimeoutSec = 60,

    [int]$TraceDurationSec = 5,

    [string]$Categories = "electron,blink,loading,toplevel,v8,devtools.timeline,disabled-by-default-v8.compile"
)

$ErrorActionPreference = "Stop"

function Resolve-CandidateLogPaths {
    param([string]$ExplicitLogPath)

    if ($ExplicitLogPath) {
        if (Test-Path -LiteralPath $ExplicitLogPath) {
            return @((Resolve-Path -LiteralPath $ExplicitLogPath).Path)
        }
        return @([System.IO.Path]::GetFullPath($ExplicitLogPath))
    }

    $candidates = @()
    if ($env:APPDATA) {
        $candidates += Join-Path $env:APPDATA "smart-factory-logger-v2\debug_electron.log"
        $candidates += Join-Path $env:APPDATA "SmartFactoryLogger\debug_electron.log"
        $candidates += Join-Path $env:APPDATA "smart-factory\debug_electron.log"
    }
    if ($env:LOCALAPPDATA) {
        $candidates += Join-Path $env:LOCALAPPDATA "smart-factory-logger-v2\debug_electron.log"
        $candidates += Join-Path $env:LOCALAPPDATA "SmartFactoryLogger\debug_electron.log"
        $candidates += Join-Path $env:LOCALAPPDATA "smart-factory\debug_electron.log"
    }

    # Preserve priority: Electron's packaged userData path must be checked
    # before legacy product-name and LOCALAPPDATA fallbacks.
    return @($candidates | Select-Object -Unique)
}

function Convert-StartupLogLine {
    param(
        [string]$Line,
        [datetime]$StartedAtUtc
    )

    if ($Line -notmatch '^\[(?<timestamp>[^\]]+)\]\s+STARTUP\s+(?<payload>\{.*\})$') {
        return $null
    }

    $timestamp = [datetime]::Parse(
        $Matches.timestamp,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [System.Globalization.DateTimeStyles]::AdjustToUniversal
    )

    if ($timestamp.ToUniversalTime() -lt $StartedAtUtc) {
        return $null
    }

    $payload = $Matches.payload | ConvertFrom-Json
    return [pscustomobject]@{
        timestamp = $timestamp.ToUniversalTime().ToString("o")
        event = [string]$payload.event
        elapsed_ms = [double]$payload.elapsed_ms
        payload = $payload.payload
    }
}

function Read-StartupEvents {
    param(
        [string[]]$CandidateLogPaths,
        [datetime]$StartedAtUtc
    )

    foreach ($candidate in $CandidateLogPaths) {
        if (-not (Test-Path -LiteralPath $candidate)) {
            continue
        }

        $events = New-Object System.Collections.Generic.List[object]
        $lines = Get-Content -LiteralPath $candidate -Tail 1000 -ErrorAction Stop
        foreach ($line in $lines) {
            $event = Convert-StartupLogLine -Line $line -StartedAtUtc $StartedAtUtc
            if ($null -ne $event) {
                $events.Add($event)
            }
        }

        if ($events.Count -gt 0) {
            return [pscustomobject]@{
                log_path = $candidate
                events = $events.ToArray()
            }
        }
    }

    return $null
}

function Get-StartupEvent {
    param(
        [object[]]$Events,
        [string]$Name
    )

    return $Events | Where-Object { $_.event -eq $Name } | Select-Object -First 1
}

function Stop-LaunchedProcessTree {
    param([System.Diagnostics.Process]$Process)

    if ($null -eq $Process) {
        return [pscustomobject]@{
            attempted = $false
            method = "none"
            ok = $true
            message = "No process handle was captured."
        }
    }

    try {
        $Process.Refresh()
        if ($Process.HasExited) {
            return [pscustomobject]@{
                attempted = $false
                method = "already_exited"
                ok = $true
                message = "Process had already exited."
            }
        }
    } catch {
        return [pscustomobject]@{
            attempted = $false
            method = "refresh"
            ok = $false
            message = $_.Exception.Message
        }
    }

    try {
        $taskkillOutput = & taskkill.exe /PID $Process.Id /T /F 2>&1
        return [pscustomobject]@{
            attempted = $true
            method = "taskkill_tree"
            ok = ($LASTEXITCODE -eq 0)
            message = ($taskkillOutput -join "`n")
        }
    } catch {
        return [pscustomobject]@{
            attempted = $true
            method = "taskkill_tree"
            ok = $false
            message = $_.Exception.Message
        }
    }
}

function Stop-ResidualSmartFactoryProcesses {
    $targets = @(
        Get-Process -ErrorAction SilentlyContinue |
            Where-Object { $_.ProcessName -in @("smart-factory", "SmartFactoryBackend") }
    )

    $stopped = 0
    foreach ($target in $targets) {
        $current = Get-Process -Id $target.Id -ErrorAction SilentlyContinue
        if ($null -ne $current) {
            Stop-Process -Id $target.Id -Force -ErrorAction SilentlyContinue
            $stopped += 1
        }
    }

    return [pscustomobject]@{
        attempted = ($targets.Count -gt 0)
        ok = $true
        stopped_count = $stopped
        message = if ($targets.Count -gt 0) { "Residual startup processes stopped." } else { "No residual startup processes found." }
    }
}

function Get-TraceOutputDirectory {
    param([string]$ConfiguredDirectory)

    if ($ConfiguredDirectory) {
        return [System.IO.Path]::GetFullPath($ConfiguredDirectory)
    }

    return Join-Path ([System.IO.Path]::GetTempPath()) "smart-factory-startup-traces"
}

$resolvedExePath = (Resolve-Path -LiteralPath $ExePath).Path
$resolvedOutputDirectory = Get-TraceOutputDirectory -ConfiguredDirectory $OutputDirectory
New-Item -ItemType Directory -Path $resolvedOutputDirectory -Force | Out-Null

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$tracePath = Join-Path $resolvedOutputDirectory "smart-factory-startup-$timestamp.json"
$startedAtUtc = (Get-Date).ToUniversalTime()
$deadline = (Get-Date).AddSeconds($TimeoutSec)
$candidateLogPaths = Resolve-CandidateLogPaths -ExplicitLogPath $LogPath

$argumentList = @(
    "--trace-startup",
    "--trace-startup-file=$tracePath",
    "--trace-startup-duration=$TraceDurationSec",
    "--trace-startup-record-mode=record-until-full",
    "--trace-startup-categories=$Categories"
)

$process = Start-Process -FilePath $resolvedExePath -ArgumentList $argumentList -PassThru
$lastSnapshot = $null
$dashboardReadySeen = $false

while ((Get-Date) -lt $deadline) {
    $logSnapshot = Read-StartupEvents -CandidateLogPaths $candidateLogPaths -StartedAtUtc $startedAtUtc
    if ($null -ne $logSnapshot) {
        $lastSnapshot = $logSnapshot
        $dashboardReadySeen = $null -ne (Get-StartupEvent -Events $logSnapshot.events -Name "renderer.dashboard-ready")
    }

    $traceExists = Test-Path -LiteralPath $tracePath
    $traceBytes = if ($traceExists) { (Get-Item -LiteralPath $tracePath).Length } else { 0 }
    if ($dashboardReadySeen -and $traceExists -and $traceBytes -gt 0) {
        $cleanup = Stop-LaunchedProcessTree -Process $process
        $residualCleanup = Stop-ResidualSmartFactoryProcesses
        [pscustomobject]@{
            status = "PASS"
            exe_path = $resolvedExePath
            process_id = $process.Id
            started_at_utc = $startedAtUtc.ToString("o")
            log_path = if ($null -eq $lastSnapshot) { $null } else { $lastSnapshot.log_path }
            trace_path = $tracePath
            trace_exists = $true
            trace_bytes = $traceBytes
            trace_duration_sec = $TraceDurationSec
            categories = $Categories
            dashboard_ready_seen = $dashboardReadySeen
            event_count = if ($null -eq $lastSnapshot) { 0 } else { $lastSnapshot.events.Count }
            cleanup = $cleanup
            residual_cleanup = $residualCleanup
        } | ConvertTo-Json -Depth 5
        if ($cleanup.ok -and $residualCleanup.ok) {
            exit 0
        }
        exit 1
    }

    Start-Sleep -Milliseconds 250
}

$cleanup = Stop-LaunchedProcessTree -Process $process
$residualCleanup = Stop-ResidualSmartFactoryProcesses
$traceExists = Test-Path -LiteralPath $tracePath
$traceBytes = if ($traceExists) { (Get-Item -LiteralPath $tracePath).Length } else { 0 }
[pscustomobject]@{
    status = "TIMEOUT"
    exe_path = $resolvedExePath
    process_id = $process.Id
    started_at_utc = $startedAtUtc.ToString("o")
    timeout_sec = $TimeoutSec
    candidate_log_paths = $candidateLogPaths
    trace_path = $tracePath
    trace_exists = $traceExists
    trace_bytes = $traceBytes
    trace_duration_sec = $TraceDurationSec
    categories = $Categories
    dashboard_ready_seen = $dashboardReadySeen
    event_count = if ($null -eq $lastSnapshot) { 0 } else { $lastSnapshot.events.Count }
    cleanup = $cleanup
    residual_cleanup = $residualCleanup
} | ConvertTo-Json -Depth 5
exit 1
