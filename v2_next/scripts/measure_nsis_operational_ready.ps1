param(
    [string]$ExePath = "",

    [string]$LogPath = "",

    [ValidateRange(10, 600)]
    [int]$TimeoutSec = 90,

    [switch]$KeepRunning,

    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-CandidateLogPaths {
    param([string]$ExplicitLogPath)

    if ($ExplicitLogPath) {
        if (Test-Path -LiteralPath $ExplicitLogPath) {
            return @((Resolve-Path -LiteralPath $ExplicitLogPath).Path)
        }
        return @([System.IO.Path]::GetFullPath($ExplicitLogPath))
    }

    $Candidates = New-Object System.Collections.Generic.List[string]
    if ($env:APPDATA) {
        [void]$Candidates.Add((Join-Path $env:APPDATA "smart-factory-logger-v2\debug_electron.log"))
        [void]$Candidates.Add((Join-Path $env:APPDATA "SmartFactoryLogger\debug_electron.log"))
        [void]$Candidates.Add((Join-Path $env:APPDATA "smart-factory\debug_electron.log"))
    }
    if ($env:LOCALAPPDATA) {
        [void]$Candidates.Add((Join-Path $env:LOCALAPPDATA "smart-factory-logger-v2\debug_electron.log"))
        [void]$Candidates.Add((Join-Path $env:LOCALAPPDATA "SmartFactoryLogger\debug_electron.log"))
        [void]$Candidates.Add((Join-Path $env:LOCALAPPDATA "smart-factory\debug_electron.log"))
    }

    return @($Candidates.ToArray() | Sort-Object -Unique)
}

function Convert-StartupLogLine {
    param(
        [string]$Line,
        [DateTimeOffset]$StartedAtUtc
    )

    if ($Line -notmatch '^\[(?<timestamp>[^\]]+)\]\s+STARTUP\s+(?<payload>\{.*\})$') {
        return $null
    }

    $Timestamp = [DateTimeOffset]::Parse(
        $Matches.timestamp,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [System.Globalization.DateTimeStyles]::AssumeUniversal
    ).ToUniversalTime()

    if ($Timestamp -lt $StartedAtUtc) {
        return $null
    }

    $Payload = $Matches.payload | ConvertFrom-Json
    $SessionProperty = $Payload.PSObject.Properties["session_id"]
    $SessionId = if ($null -eq $SessionProperty) { "" } else { [string]$SessionProperty.Value }
    $EventPayloadProperty = $Payload.PSObject.Properties["payload"]
    $EventPayload = if ($null -eq $EventPayloadProperty) { $null } else { $EventPayloadProperty.Value }

    return [pscustomobject][ordered]@{
        timestamp_utc = $Timestamp.ToString("o")
        event         = [string]$Payload.event
        session_id    = $SessionId
        elapsed_ms    = [double]$Payload.elapsed_ms
        payload       = $EventPayload
    }
}

function Read-StartupEvents {
    param(
        [string[]]$CandidateLogPaths,
        [DateTimeOffset]$StartedAtUtc
    )

    foreach ($Candidate in $CandidateLogPaths) {
        if (-not (Test-Path -LiteralPath $Candidate)) {
            continue
        }

        $Events = New-Object System.Collections.Generic.List[object]
        foreach ($Line in (Get-Content -LiteralPath $Candidate -Tail 5000 -ErrorAction Stop)) {
            $EventItem = Convert-StartupLogLine -Line $Line -StartedAtUtc $StartedAtUtc
            if ($null -ne $EventItem -and $EventItem.session_id) {
                [void]$Events.Add($EventItem)
            }
        }

        if ($Events.Count -gt 0) {
            return [pscustomobject][ordered]@{
                log_path = $Candidate
                events   = @($Events.ToArray())
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

    return $Events |
        Where-Object { $_.event -eq $Name } |
        Select-Object -First 1
}

function Get-RequiredMilestones {
    return @(
        "electron.process-start",
        "backend.spawned",
        "renderer.index-boot",
        "renderer.app-render-end",
        "renderer.backend-health-ready",
        "renderer.first-live-data",
        "renderer.dashboard-ready",
        "renderer.dashboard-operational-ready"
    )
}

function Get-StartupSessionIds {
    param([object[]]$Events)

    return @(
        $Events |
            Where-Object { $_.event -eq "electron.process-start" -and $_.session_id } |
            Sort-Object timestamp_utc |
            ForEach-Object { $_.session_id } |
            Sort-Object -Unique
    )
}

function Get-MissingMilestones {
    param(
        [object[]]$Events,
        [string[]]$Required
    )

    $Present = @{}
    foreach ($EventItem in $Events) {
        $Present[[string]$EventItem.event] = $true
    }

    return @($Required | Where-Object { -not $Present.ContainsKey($_) })
}

function Get-EventPayloadValue {
    param(
        [object]$EventItem,
        [string]$Name
    )

    if ($null -eq $EventItem -or $null -eq $EventItem.payload) {
        return $null
    }

    $Property = $EventItem.payload.PSObject.Properties[$Name]
    if ($null -eq $Property) {
        return $null
    }

    return $Property.Value
}

function Get-ContaminatingProcesses {
    $Names = @("smart-factory", "SmartFactoryBackend")
    return @(
        Get-Process -ErrorAction SilentlyContinue |
            Where-Object { $Names -contains $_.ProcessName } |
            ForEach-Object {
                [pscustomobject][ordered]@{
                    process_name = $_.ProcessName
                    process_id   = $_.Id
                }
            }
    )
}

function Resolve-MeasurementStatus {
    param(
        [string]$TerminalReason,
        [object]$OperationalReady,
        [int]$MissingMilestoneCount,
        [object]$ReadyStrategy
    )

    if ($TerminalReason -eq "MULTIPLE_STARTUP_SESSIONS") {
        return "CONTAMINATED"
    }
    if ($TerminalReason -eq "OPERATIONAL_TIMEOUT") {
        return "OPERATIONAL_TIMEOUT"
    }
    if ($TerminalReason -eq "PROCESS_EXITED" -or $TerminalReason -eq "PROCESS_STATE_ERROR") {
        return $TerminalReason
    }
    if ($null -ne $OperationalReady -and $MissingMilestoneCount -gt 0) {
        return "MISSING_MILESTONES"
    }
    if ($null -ne $OperationalReady -and $ReadyStrategy -ne "raf") {
        return "INVALID_READY_STRATEGY"
    }
    if ($null -ne $OperationalReady -and $MissingMilestoneCount -eq 0) {
        return "PASS"
    }
    return "TIMEOUT"
}

function Stop-LaunchedProcessTree {
    param(
        [System.Diagnostics.Process]$Process,
        [switch]$KeepProcessRunning
    )

    if ($KeepProcessRunning.IsPresent) {
        return [pscustomobject][ordered]@{
            attempted = $false
            method    = "keep_running"
            ok        = $true
            message   = "Process left running by request."
        }
    }

    if ($null -eq $Process) {
        return [pscustomobject][ordered]@{
            attempted = $false
            method    = "none"
            ok        = $true
            message   = "No process handle was captured."
        }
    }

    try {
        $Process.Refresh()
        if ($Process.HasExited) {
            return [pscustomobject][ordered]@{
                attempted = $false
                method    = "already_exited"
                ok        = $true
                message   = "Process had already exited."
            }
        }
    } catch {
        return [pscustomobject][ordered]@{
            attempted = $false
            method    = "refresh"
            ok        = $false
            message   = $_.Exception.Message
        }
    }

    try {
        $TaskkillOutput = & taskkill.exe /PID $Process.Id /T /F 2>&1
        $TaskkillOk = $LASTEXITCODE -eq 0
        return [pscustomobject][ordered]@{
            attempted = $true
            method    = "taskkill_tree"
            ok        = $TaskkillOk
            message   = ($TaskkillOutput -join "`n")
        }
    } catch {
        return [pscustomobject][ordered]@{
            attempted = $true
            method    = "taskkill_tree"
            ok        = $false
            message   = $_.Exception.Message
        }
    }
}

function Invoke-SelfTest {
    $FixtureStartedAt = [DateTimeOffset]::Parse("2026-07-15T00:00:00Z")
    $FixturePayload = [ordered]@{
        event      = "electron.process-start"
        session_id = "fixture-session"
        elapsed_ms = 2.5
        payload    = [ordered]@{ is_packaged = $true }
    }
    $FixtureJson = $FixturePayload | ConvertTo-Json -Compress -Depth 4
    $FixtureLine = "[2026-07-15T00:00:01.000Z] STARTUP $FixtureJson"
    $Parsed = Convert-StartupLogLine -Line $FixtureLine -StartedAtUtc $FixtureStartedAt
    if ($null -eq $Parsed) {
        throw "Fixture line was not parsed."
    }
    if ($Parsed.session_id -ne "fixture-session" -or $Parsed.event -ne "electron.process-start") {
        throw "Fixture session correlation failed."
    }

    $FixtureEvents = @(
        $Parsed,
        [pscustomobject]@{ event = "backend.spawned" },
        [pscustomobject]@{ event = "renderer.index-boot" },
        [pscustomobject]@{ event = "renderer.app-render-end" },
        [pscustomobject]@{ event = "renderer.backend-health-ready" },
        [pscustomobject]@{ event = "renderer.first-live-data" },
        [pscustomobject]@{ event = "renderer.dashboard-ready" },
        [pscustomobject]@{ event = "renderer.dashboard-operational-ready" }
    )
    $Missing = @(Get-MissingMilestones -Events $FixtureEvents -Required (Get-RequiredMilestones))
    if ($Missing.Count -ne 0) {
        throw "Fixture milestone validation failed."
    }

    $ContaminatedSessionIds = @(Get-StartupSessionIds -Events @(
        [pscustomobject]@{
            event = "electron.process-start"; session_id = "session-a"; timestamp_utc = "1"
        },
        [pscustomobject]@{
            event = "electron.process-start"; session_id = "session-b"; timestamp_utc = "2"
        }
    ))
    if ($ContaminatedSessionIds.Count -ne 2) {
        throw "Fixture multi-session contamination detection failed."
    }

    $ReadyFixture = [pscustomobject]@{ event = "renderer.dashboard-operational-ready" }
    if ((Resolve-MeasurementStatus "READY" $ReadyFixture 0 "raf") -ne "PASS") {
        throw "Fixture PASS classification failed."
    }
    if ((Resolve-MeasurementStatus "OPERATIONAL_TIMEOUT" $null 1 $null) -ne "OPERATIONAL_TIMEOUT") {
        throw "Fixture timeout classification failed."
    }
    if ((Resolve-MeasurementStatus "MULTIPLE_STARTUP_SESSIONS" $null 8 $null) -ne "CONTAMINATED") {
        throw "Fixture contamination classification failed."
    }

    [pscustomobject][ordered]@{
        status               = "PASS"
        parser               = "PASS"
        session_correlation  = "PASS"
        milestone_validation = "PASS"
        failure_classification = "PASS"
    } | ConvertTo-Json -Depth 3
}

if ($SelfTest.IsPresent) {
    Invoke-SelfTest
    exit 0
}

if (-not $ExePath) {
    throw "-ExePath is required unless -SelfTest is used."
}

$ResolvedExePath = (Resolve-Path -LiteralPath $ExePath).Path
$ContaminatingProcesses = @(Get-ContaminatingProcesses)
if ($ContaminatingProcesses.Count -gt 0) {
    [pscustomobject][ordered]@{
        status                  = "CONTAMINATED"
        exe_path                = $ResolvedExePath
        contaminating_processes = $ContaminatingProcesses
        message                 = "Close the app and backend before a cold-start measurement."
    } | ConvertTo-Json -Depth 5
    exit 2
}

$CandidateLogPaths = @(Resolve-CandidateLogPaths -ExplicitLogPath $LogPath)
$StartedAtUtc = [DateTimeOffset]::UtcNow
$Deadline = [DateTimeOffset]::Now.AddSeconds($TimeoutSec)
$LaunchedProcess = Start-Process -FilePath $ResolvedExePath -PassThru
$SelectedSessionId = ""
$SelectedLogPath = ""
$SelectedEvents = @()
$TerminalReason = "TIMEOUT"
$MultipleSessions = @()

while ([DateTimeOffset]::Now -lt $Deadline) {
    $Snapshot = Read-StartupEvents -CandidateLogPaths $CandidateLogPaths -StartedAtUtc $StartedAtUtc
    if ($null -ne $Snapshot) {
        $SessionIds = @(Get-StartupSessionIds -Events $Snapshot.events)

        if ($SessionIds.Count -gt 1) {
            $MultipleSessions = $SessionIds
            $TerminalReason = "MULTIPLE_STARTUP_SESSIONS"
            break
        }

        if ($SessionIds.Count -eq 1) {
            $SelectedSessionId = [string]$SessionIds[0]
            $SelectedLogPath = [string]$Snapshot.log_path
            $SelectedEvents = @(
                $Snapshot.events |
                    Where-Object { $_.session_id -eq $SelectedSessionId }
            )

            if ($null -ne (Get-StartupEvent -Events $SelectedEvents -Name "renderer.dashboard-operational-timeout")) {
                $TerminalReason = "OPERATIONAL_TIMEOUT"
                break
            }
            if ($null -ne (Get-StartupEvent -Events $SelectedEvents -Name "renderer.dashboard-operational-ready")) {
                $TerminalReason = "READY"
                break
            }
        }
    }

    try {
        $LaunchedProcess.Refresh()
        if ($LaunchedProcess.HasExited) {
            $TerminalReason = "PROCESS_EXITED"
            break
        }
    } catch {
        $TerminalReason = "PROCESS_STATE_ERROR"
        break
    }

    Start-Sleep -Milliseconds 250
}

$Cleanup = Stop-LaunchedProcessTree -Process $LaunchedProcess -KeepProcessRunning:$KeepRunning
$RequiredMilestones = @(Get-RequiredMilestones)
$MissingMilestones = @(Get-MissingMilestones -Events $SelectedEvents -Required $RequiredMilestones)
$BackendReady = Get-StartupEvent -Events $SelectedEvents -Name "renderer.backend-health-ready"
$FirstLiveData = Get-StartupEvent -Events $SelectedEvents -Name "renderer.first-live-data"
$DashboardReady = Get-StartupEvent -Events $SelectedEvents -Name "renderer.dashboard-ready"
$OperationalTimeout = Get-StartupEvent -Events $SelectedEvents -Name "renderer.dashboard-operational-timeout"
$OperationalReady = Get-StartupEvent -Events $SelectedEvents -Name "renderer.dashboard-operational-ready"
$ReadyStrategy = Get-EventPayloadValue -EventItem $OperationalReady -Name "ready_strategy"

$Status = Resolve-MeasurementStatus `
    -TerminalReason $TerminalReason `
    -OperationalReady $OperationalReady `
    -MissingMilestoneCount $MissingMilestones.Count `
    -ReadyStrategy $ReadyStrategy

$OperationalReadyTimestampUtc = $null
$LauncherObservedMs = $null
if ($null -ne $OperationalReady) {
    $OperationalReadyTimestampUtc = [string]$OperationalReady.timestamp_utc
    $ReadyTimestamp = [DateTimeOffset]::Parse($OperationalReadyTimestampUtc)
    $LauncherObservedMs = [math]::Round(($ReadyTimestamp - $StartedAtUtc).TotalMilliseconds, 1)
}

$Result = [pscustomobject][ordered]@{
    status                                  = $Status
    terminal_reason                         = $TerminalReason
    exe_path                                = $ResolvedExePath
    process_id                              = $LaunchedProcess.Id
    startup_session_id                      = $SelectedSessionId
    started_at_utc                          = $StartedAtUtc.ToString("o")
    operational_ready_timestamp_utc         = $OperationalReadyTimestampUtc
    timeout_sec                             = $TimeoutSec
    log_path                                = $SelectedLogPath
    backend_health_ready_elapsed_ms         = if ($null -eq $BackendReady) { $null } else { $BackendReady.elapsed_ms }
    first_live_data_elapsed_ms               = if ($null -eq $FirstLiveData) { $null } else { $FirstLiveData.elapsed_ms }
    dashboard_ready_elapsed_ms               = if ($null -eq $DashboardReady) { $null } else { $DashboardReady.elapsed_ms }
    operational_ready_elapsed_ms             = if ($null -eq $OperationalReady) { $null } else { $OperationalReady.elapsed_ms }
    launcher_observed_operational_ready_ms   = $LauncherObservedMs
    ready_strategy                          = $ReadyStrategy
    operational_timeout_missing_gates       = Get-EventPayloadValue -EventItem $OperationalTimeout -Name "missing_gates"
    missing_milestones                      = $MissingMilestones
    multiple_startup_sessions               = $MultipleSessions
    event_count                             = $SelectedEvents.Count
    cleanup                                 = $Cleanup
    events                                  = $SelectedEvents
}

$Result | ConvertTo-Json -Depth 7
if ($Status -eq "PASS") {
    exit 0
}
exit 1
