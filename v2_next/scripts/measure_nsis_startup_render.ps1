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

function Get-StartupPayloadNumber {
    param(
        [object[]]$Events,
        [string]$EventName,
        [string]$PayloadKey
    )

    $value = Get-StartupPayloadValue -Events $Events -EventName $EventName -PayloadKey $PayloadKey
    if ($null -eq $value) {
        return $null
    }

    try {
        $number = [double]$value
    } catch {
        return $null
    }

    if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
        return $null
    }

    return $number
}

function Get-StartupPayloadIntervalMs {
    param(
        [object[]]$Events,
        [string]$StartEvent,
        [string]$EndEvent,
        [string]$PayloadKey
    )

    $start = Get-StartupPayloadNumber -Events $Events -EventName $StartEvent -PayloadKey $PayloadKey
    $end = Get-StartupPayloadNumber -Events $Events -EventName $EndEvent -PayloadKey $PayloadKey

    if ($null -eq $start -or $null -eq $end) {
        return $null
    }

    return [math]::Round(($end - $start), 1)
}

function Get-StartupPayloadDeltaMs {
    param(
        [object[]]$Events,
        [string]$EventName,
        [string]$StartPayloadKey,
        [string]$EndPayloadKey
    )

    $start = Get-StartupPayloadNumber -Events $Events -EventName $EventName -PayloadKey $StartPayloadKey
    $end = Get-StartupPayloadNumber -Events $Events -EventName $EventName -PayloadKey $EndPayloadKey

    if ($null -eq $start -or $null -eq $end) {
        return $null
    }

    return [math]::Round(($end - $start), 1)
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

function Get-RequiredStartupMilestones {
    return @(
        "renderer.preload-start",
        "renderer.preload-bridge-exposed",
        "renderer.index-html-inline-script",
        "renderer.index-boot",
        "renderer.index-render",
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
        "renderer.native-surface-render-end",
        "renderer.dashboard-ready"
    )
}

function Get-StartupIntervals {
    param([object[]]$Events)

    $requiredMilestones = Get-RequiredStartupMilestones
    $missingRequiredMilestones = Get-MissingStartupMilestones -Events $Events -Names $requiredMilestones

    return [pscustomobject]@{
        load_file_to_preload_start_ms = Get-StartupIntervalMs -Events $Events -StartEvent "electron.load-file-start" -EndEvent "renderer.preload-start"
        load_file_to_did_start_navigation_ms = Get-StartupIntervalMs -Events $Events -StartEvent "electron.load-file-start" -EndEvent "electron.webcontents-did-start-navigation"
        did_start_navigation_to_did_start_loading_ms = Get-StartupIntervalMs -Events $Events -StartEvent "electron.webcontents-did-start-navigation" -EndEvent "electron.webcontents-did-start-loading"
        did_start_navigation_to_preload_start_ms = Get-StartupIntervalMs -Events $Events -StartEvent "electron.webcontents-did-start-navigation" -EndEvent "renderer.preload-start"
        did_start_navigation_to_index_html_inline_ms = Get-StartupIntervalMs -Events $Events -StartEvent "electron.webcontents-did-start-navigation" -EndEvent "renderer.index-html-inline-script"
        did_start_loading_to_index_html_inline_ms = Get-StartupIntervalMs -Events $Events -StartEvent "electron.webcontents-did-start-loading" -EndEvent "renderer.index-html-inline-script"
        preload_start_to_bridge_exposed_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.preload-start" -EndEvent "renderer.preload-bridge-exposed"
        preload_bridge_to_index_html_inline_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.preload-bridge-exposed" -EndEvent "renderer.index-html-inline-script"
        index_html_inline_to_index_boot_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.index-html-inline-script" -EndEvent "renderer.index-boot"
        load_file_to_index_html_inline_ms = Get-StartupIntervalMs -Events $Events -StartEvent "electron.load-file-start" -EndEvent "renderer.index-html-inline-script"
        preload_start_to_index_boot_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.preload-start" -EndEvent "renderer.index-boot"
        load_file_to_index_boot_ms = Get-StartupIntervalMs -Events $Events -StartEvent "electron.load-file-start" -EndEvent "renderer.index-boot"
        index_boot_to_index_render_ms = Get-StartupIntervalMs -Events $Events -StartEvent "renderer.index-boot" -EndEvent "renderer.index-render"
        main_frame_finish_to_did_finish_load_ms = Get-StartupIntervalMs -Events $Events -StartEvent "electron.webcontents-did-frame-finish-load" -EndEvent "electron.webcontents-did-finish-load"
        did_navigate_to_did_finish_load_ms = Get-StartupIntervalMs -Events $Events -StartEvent "electron.webcontents-did-navigate" -EndEvent "electron.webcontents-did-finish-load"
        renderer_clock_preload_start_to_bridge_exposed_ms = Get-StartupPayloadIntervalMs -Events $Events -StartEvent "renderer.preload-start" -EndEvent "renderer.preload-bridge-exposed" -PayloadKey "renderer_epoch_ms"
        renderer_clock_preload_bridge_to_index_html_inline_ms = Get-StartupPayloadIntervalMs -Events $Events -StartEvent "renderer.preload-bridge-exposed" -EndEvent "renderer.index-html-inline-script" -PayloadKey "renderer_epoch_ms"
        renderer_clock_index_html_inline_to_index_boot_ms = Get-StartupPayloadIntervalMs -Events $Events -StartEvent "renderer.index-html-inline-script" -EndEvent "renderer.index-boot" -PayloadKey "renderer_epoch_ms"
        renderer_clock_preload_start_to_index_boot_ms = Get-StartupPayloadIntervalMs -Events $Events -StartEvent "renderer.preload-start" -EndEvent "renderer.index-boot" -PayloadKey "renderer_epoch_ms"
        index_html_navigation_start_to_inline_ms = Get-StartupPayloadDeltaMs -Events $Events -EventName "renderer.index-html-inline-script" -StartPayloadKey "navigation_start_ms" -EndPayloadKey "renderer_now_ms"
        index_html_fetch_start_to_response_end_ms = Get-StartupPayloadDeltaMs -Events $Events -EventName "renderer.index-html-inline-script" -StartPayloadKey "navigation_fetch_start_ms" -EndPayloadKey "navigation_response_end_ms"
        index_html_response_start_to_response_end_ms = Get-StartupPayloadDeltaMs -Events $Events -EventName "renderer.index-html-inline-script" -StartPayloadKey "navigation_response_start_ms" -EndPayloadKey "navigation_response_end_ms"
        index_html_response_end_to_inline_ms = Get-StartupPayloadValue -Events $Events -EventName "renderer.index-html-inline-script" -PayloadKey "navigation_response_end_to_inline_ms"
        index_html_dom_interactive_at_inline_ms = Get-StartupPayloadValue -Events $Events -EventName "renderer.index-html-inline-script" -PayloadKey "navigation_dom_interactive_ms"
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
        missing_required_milestones = $missingRequiredMilestones
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
            $startupIntervals = Get-StartupIntervals -Events $logSnapshot.events
            $missingRequiredMilestones = Get-MissingStartupMilestones -Events $logSnapshot.events -Names (Get-RequiredStartupMilestones)
            $missingRequiredMilestoneCount = if ($null -eq $missingRequiredMilestones) {
                0
            } elseif ($missingRequiredMilestones -is [array]) {
                $missingRequiredMilestones.Count
            } else {
                1
            }
            $status = if ($missingRequiredMilestoneCount -eq 0) { "PASS" } else { "MISSING_MILESTONES" }
            [pscustomobject]@{
                status = $status
                exe_path = $resolvedExePath
                process_id = $process.Id
                started_at_utc = $startedAtUtc.ToString("o")
                log_path = $logSnapshot.log_path
                dashboard_ready_elapsed_ms = $dashboardReady.elapsed_ms
                event_count = $logSnapshot.events.Count
                startup_intervals = $startupIntervals
                cleanup = $cleanup
                events = $logSnapshot.events
            } | ConvertTo-Json -Depth 6
            if ($status -eq "PASS") {
                exit 0
            }
            exit 1
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
