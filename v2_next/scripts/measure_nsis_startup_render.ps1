param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,

    [string]$LogPath = "",

    [int]$TimeoutSec = 90,

    [switch]$KeepRunning
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

    return $candidates | Sort-Object -Unique
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

function Get-StartupIntervalMs {
    param(
        [object[]]$Events,
        [string]$StartEvent,
        [string]$EndEvent
    )

    $start = Get-StartupEvent -Events $Events -Name $StartEvent
    $end = Get-StartupEvent -Events $Events -Name $EndEvent

    if ($null -eq $start -or $null -eq $end) {
        return $null
    }

    return [math]::Round(([double]$end.elapsed_ms - [double]$start.elapsed_ms), 1)
}

function Get-StartupPayloadValue {
    param(
        [object[]]$Events,
        [string]$EventName,
        [string]$PayloadKey
    )

    $event = Get-StartupEvent -Events $Events -Name $EventName
    if ($null -eq $event -or $null -eq $event.payload) {
        return $null
    }

    $property = $event.payload.PSObject.Properties[$PayloadKey]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Get-MissingStartupMilestones {
    param(
        [object[]]$Events,
        [string[]]$Names
    )

    $present = @{}
    foreach ($event in $Events) {
        $present[[string]$event.event] = $true
    }

    $missing = @($Names | Where-Object { -not $present.ContainsKey($_) })
    return ,([string[]]$missing)
}

function Get-StartupIntervals {
    param([object[]]$Events)

    $requiredMilestones = @(
        "renderer.app-import-start",
        "renderer.app-module-evaluated",
        "renderer.app-import-end",
        "renderer.app-render-start",
        "renderer.polling-interval-resolved",
        "renderer.app-render-end",
        "renderer.native-surface-import-start",
        "renderer.native-surface-module-evaluated",
        "renderer.native-surface-import-end",
        "renderer.native-surface-render-start",
        "renderer.native-surface-render-end"
    )

    return [pscustomobject]@{
        load_file_to_index_boot_ms = Get-StartupIntervalMs -Events $Events -StartEvent "electron.load-file-start" -EndEvent "renderer.index-boot"
        index_boot_to_index_render_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.index-boot" -EndEvent "renderer.index-render"
        app_import_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.app-import-start" -EndEvent "renderer.app-import-end"
        app_import_to_module_eval_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.app-import-start" -EndEvent "renderer.app-module-evaluated"
        app_module_eval_to_import_end_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.app-module-evaluated" -EndEvent "renderer.app-import-end"
        app_render_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.app-render-start" -EndEvent "renderer.app-render-end"
        native_surface_import_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.native-surface-import-start" -EndEvent "renderer.native-surface-import-end"
        native_surface_import_to_module_eval_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.native-surface-import-start" -EndEvent "renderer.native-surface-module-evaluated"
        native_surface_module_eval_to_import_end_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.native-surface-module-evaluated" -EndEvent "renderer.native-surface-import-end"
        native_surface_render_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.native-surface-render-start" -EndEvent "renderer.native-surface-render-end"
        native_surface_render_end_to_dashboard_ready_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.native-surface-render-end" -EndEvent "renderer.dashboard-ready"
        index_render_to_dashboard_ready_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.index-render" -EndEvent "renderer.dashboard-ready"
        polling_interval_ms = Get-StartupPayloadValue -Events $Events -EventName "renderer.polling-interval-resolved" -PayloadKey "polling_interval_ms"
        missing_required_milestones = Get-MissingStartupMilestones -Events $Events -Names $requiredMilestones
    }
}

function Stop-LaunchedProcessTree {
    param(
        [System.Diagnostics.Process]$Process,
        [switch]$KeepProcessRunning
    )

    if ($KeepProcessRunning.IsPresent) {
        return [pscustomobject]@{
            attempted = $false
            method = "keep_running"
            ok = $true
            message = "Process left running by request."
        }
    }

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

$resolvedExePath = (Resolve-Path -LiteralPath $ExePath).Path
$startedAtUtc = (Get-Date).ToUniversalTime()
$deadline = (Get-Date).AddSeconds($TimeoutSec)
$candidateLogPaths = Resolve-CandidateLogPaths -ExplicitLogPath $LogPath

$process = Start-Process -FilePath $resolvedExePath -PassThru

while ((Get-Date) -lt $deadline) {
    $logSnapshot = Read-StartupEvents -CandidateLogPaths $candidateLogPaths -StartedAtUtc $startedAtUtc
    if ($null -ne $logSnapshot) {
        $dashboardReady = $logSnapshot.events | Where-Object { $_.event -eq "renderer.dashboard-ready" } | Select-Object -Last 1
        if ($null -ne $dashboardReady) {
            $cleanup = Stop-LaunchedProcessTree -Process $process -KeepProcessRunning:$KeepRunning
            [pscustomobject]@{
                status = "PASS"
                exe_path = $resolvedExePath
                process_id = $process.Id
                started_at_utc = $startedAtUtc.ToString("o")
                log_path = $logSnapshot.log_path
                dashboard_ready_elapsed_ms = $dashboardReady.elapsed_ms
                event_count = $logSnapshot.events.Count
                startup_intervals = Get-StartupIntervals -Events $logSnapshot.events
                cleanup = $cleanup
                events = $logSnapshot.events
            } | ConvertTo-Json -Depth 6
            exit 0
        }
    }

    Start-Sleep -Milliseconds 250
}

$lastSnapshot = Read-StartupEvents -CandidateLogPaths $candidateLogPaths -StartedAtUtc $startedAtUtc
$cleanup = Stop-LaunchedProcessTree -Process $process -KeepProcessRunning:$KeepRunning
[pscustomobject]@{
    status = "TIMEOUT"
    exe_path = $resolvedExePath
    process_id = $process.Id
    started_at_utc = $startedAtUtc.ToString("o")
    timeout_sec = $TimeoutSec
    candidate_log_paths = $candidateLogPaths
    event_count = if ($null -eq $lastSnapshot) { 0 } else { $lastSnapshot.events.Count }
    startup_intervals = if ($null -eq $lastSnapshot) { $null } else { Get-StartupIntervals -Events $lastSnapshot.events }
    cleanup = $cleanup
    events = if ($null -eq $lastSnapshot) { @() } else { $lastSnapshot.events }
} | ConvertTo-Json -Depth 6
exit 1
