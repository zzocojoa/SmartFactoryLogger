[CmdletBinding()]
param(
    [ValidateRange(5, 180)]
    [int]$ObservationMinutes = 15,

    [string]$ApiBase = "http://127.0.0.1:8000",

    [string]$SpotIp = "",

    [string]$ConfigPath = "",

    [string]$EvidenceBase = "",

    [string]$CollectorPath = "",

    [string]$FramingAnalyzerPath = "",

    [switch]$StopOnNewSpotConnectTimeout,

    [ValidateRange(0, 300)]
    [int]$PostTriggerCaptureSeconds = 75,

    [ValidateRange(10, 300)]
    [int]$ProgressIntervalSeconds = 30,

    [switch]$PreflightOnly,

    [switch]$SelfTest
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Get-OptionalPropertyValue {
    param(
        [object]$Object,
        [string]$Name,
        [object]$DefaultValue = $null
    )

    if ($null -eq $Object) {
        return $DefaultValue
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $DefaultValue
    }
    return $property.Value
}

function Get-ObservationTimingSummary {
    param(
        [object]$ObservationStartSnapshot,
        [object]$ObservationEndSnapshot,
        [object]$AppObservationElapsedSeconds,
        [object]$FallbackStartedAt,
        [object]$FallbackEndedAt
    )

    $parentElapsedSeconds = $null
    if ($null -ne $ObservationStartSnapshot -and
        $null -ne $ObservationEndSnapshot) {
        $startFrequency = [int64]$ObservationStartSnapshot.monotonic_frequency
        $endFrequency = [int64]$ObservationEndSnapshot.monotonic_frequency
        $startTicks = [int64]$ObservationStartSnapshot.monotonic_ticks
        $endTicks = [int64]$ObservationEndSnapshot.monotonic_ticks
        if ($startFrequency -le 0 -or
            $endFrequency -ne $startFrequency -or
            $endTicks -le $startTicks) {
            throw 'The authoritative monotonic observation boundary is invalid.'
        }
        $parentElapsedSeconds = [Math]::Round(
            [double]($endTicks - $startTicks) / [double]$startFrequency,
            3
        )
    }

    $appElapsedSeconds = if ($null -eq $AppObservationElapsedSeconds) {
        $null
    } else {
        [Math]::Round([double]$AppObservationElapsedSeconds, 3)
    }
    $wallElapsedSeconds = if ($null -eq $FallbackStartedAt -or
        $null -eq $FallbackEndedAt) {
        $null
    } else {
        [Math]::Round(
            (([DateTimeOffset]$FallbackEndedAt) -
                ([DateTimeOffset]$FallbackStartedAt)).TotalSeconds,
            3
        )
    }

    $source = if ($null -ne $parentElapsedSeconds) {
        'parent-authoritative-monotonic-boundary'
    } elseif ($null -ne $appElapsedSeconds) {
        'app-collector-fallback'
    } elseif ($null -ne $wallElapsedSeconds) {
        'wall-clock-fallback'
    } else {
        'unavailable'
    }
    $selectedElapsedSeconds = switch ($source) {
        'parent-authoritative-monotonic-boundary' { $parentElapsedSeconds }
        'app-collector-fallback' { $appElapsedSeconds }
        'wall-clock-fallback' { $wallElapsedSeconds }
        default { $null }
    }

    return [pscustomobject][ordered]@{
        elapsed_seconds = $selectedElapsedSeconds
        source = $source
        parent_monotonic_elapsed_seconds = $parentElapsedSeconds
        app_collector_elapsed_seconds = $appElapsedSeconds
        wall_clock_elapsed_seconds = $wallElapsedSeconds
    }
}

function Write-Stage {
    param([string]$Message)
    Write-Host ""
    Write-Host ("[STEP] {0}" -f $Message) -ForegroundColor Cyan
}

function Write-FinalizationProgress {
    param(
        [int]$Step,
        [string]$Message,
        [object]$StartedAt
    )

    $elapsed = if ($null -eq $StartedAt) {
        '00:00:00'
    } else {
        ([TimeSpan]((Get-Date) - [DateTime]$StartedAt)).ToString('hh\:mm\:ss')
    }
    Write-Host (
        '[POSTPROCESS PROGRESS] step={0}/4 observation_complete=true postprocess_elapsed={1} stage={2}' -f `
            $Step,
            $elapsed,
            $Message
    ) -ForegroundColor Cyan
}

function Receive-CollectorJobOutput {
    param(
        [System.Management.Automation.Job]$Job,
        [string]$ConsolePath
    )

    if ($null -eq $Job) {
        return
    }
    $items = @(Receive-Job -Job $Job -ErrorAction SilentlyContinue)
    foreach ($item in $items) {
        $text = ($item | Out-String).TrimEnd()
        if ([string]::IsNullOrWhiteSpace($text)) {
            continue
        }
        Write-Host $text
        $text | Add-Content -LiteralPath $ConsolePath -Encoding unicode
    }
}

function Read-CollectorStopSignal {
    param([string]$SignalPath)

    if (-not (Test-Path -LiteralPath $SignalPath -PathType Leaf)) {
        return $null
    }

    $observedAt = [DateTimeOffset]::Now
    try {
        $signal = Get-Content `
            -LiteralPath $SignalPath `
            -Raw `
            -Encoding utf8 |
            ConvertFrom-Json
        if ($signal.schema_version -ne
            'spot-connecttimeout-capture-stop-v1') {
            throw 'Unexpected capture stop signal schema.'
        }
        $signalEndedAt = [DateTimeOffset]::Parse(
            [string]$signal.collection_ended_at
        )
        return [pscustomobject][ordered]@{
            status = 'signal-observed'
            signal = $signal
            observed_at = $observedAt
            signal_ended_at = $signalEndedAt
            observation_latency_ms = [Math]::Max(
                0,
                [Math]::Round(
                    ($observedAt - $signalEndedAt).TotalMilliseconds,
                    3
                )
            )
            error_message = $null
        }
    } catch {
        return [pscustomobject][ordered]@{
            status = 'signal-invalid'
            signal = $null
            observed_at = $observedAt
            signal_ended_at = $null
            observation_latency_ms = $null
            error_message = $_.Exception.Message
        }
    }
}

function Wait-CollectorObservationBoundary {
    param(
        [System.Management.Automation.Job]$Job,
        [string]$SignalPath,
        [DateTimeOffset]$PlannedEndAt,
        [int64]$MonotonicDeadlineTicks = 0,
        [ValidateRange(50, 1000)]
        [int]$PollIntervalMilliseconds = 200,
        [scriptblock]$OnPoll = $null
    )

    while ($true) {
        $signalResult = Read-CollectorStopSignal -SignalPath $SignalPath
        if ($null -ne $signalResult) {
            return $signalResult
        }

        if ($null -eq $Job -or
            $Job.State -in @('Completed', 'Failed', 'Stopped')) {
            return [pscustomobject][ordered]@{
                status = 'collector-ended-without-signal'
                signal = $null
                observed_at = $null
                signal_ended_at = $null
                observation_latency_ms = $null
                error_message = (
                    'The event-trigger collector ended before the planned ' +
                    'boundary without a capture stop signal.'
                )
            }
        }

        $now = [DateTimeOffset]::Now
        $monotonicBoundaryReached = (
            $MonotonicDeadlineTicks -gt 0 -and
            [Diagnostics.Stopwatch]::GetTimestamp() -ge $MonotonicDeadlineTicks
        )
        if ($monotonicBoundaryReached -or
            ($MonotonicDeadlineTicks -le 0 -and $now -ge $PlannedEndAt)) {
            return [pscustomobject][ordered]@{
                status = 'planned-end-reached'
                signal = $null
                observed_at = $now
                signal_ended_at = $null
                observation_latency_ms = $null
                error_message = $null
            }
        }

        if ($null -ne $OnPoll) {
            & $OnPoll $now
        }

        $sleepMilliseconds = $PollIntervalMilliseconds
        if ($MonotonicDeadlineTicks -gt 0) {
            $ticksRemaining = $MonotonicDeadlineTicks -
                [Diagnostics.Stopwatch]::GetTimestamp()
            $millisecondsRemaining = [int][Math]::Ceiling(
                1000.0 * $ticksRemaining / [Diagnostics.Stopwatch]::Frequency
            )
            $sleepMilliseconds = [Math]::Min(
                $sleepMilliseconds,
                [Math]::Max(1, $millisecondsRemaining)
            )
        }
        Start-Sleep -Milliseconds $sleepMilliseconds
    }
}

function Get-CollectorCompletionRequestPath {
    param([string]$CollectorOutputRoot)

    $sessions = @(
        Get-ChildItem `
            -LiteralPath $CollectorOutputRoot `
            -Directory `
            -Filter 'operational_observability_*' `
            -ErrorAction Stop
    )
    if ($sessions.Count -ne 1) {
        throw (
            'The parent could not resolve exactly one active app evidence ' +
            "session. count=$($sessions.Count)"
        )
    }
    $rawPath = Join-Path $sessions[0].FullName 'raw'
    if (-not (Test-Path -LiteralPath $rawPath -PathType Container)) {
        throw 'The active app evidence raw folder is not ready.'
    }
    return Join-Path $rawPath 'trigger_monitor_completion_request.json'
}

function Write-ParentCollectorCompletionRequest {
    param(
        [string]$Path,
        [DateTimeOffset]$ObservationEndedAt
    )

    $fullPath = [IO.Path]::GetFullPath($Path)
    if (Test-Path -LiteralPath $fullPath) {
        throw 'The collector completion request already exists.'
    }
    $request = [ordered]@{
        schema_version = 'spot-trigger-monitor-completion-request-v1'
        request_id = [guid]::NewGuid().ToString('N')
        requested_at = [DateTimeOffset]::Now.ToString('o')
        observation_ended_at = $ObservationEndedAt.ToString('o')
        reason = 'observation-deadline-reached'
        request_source = 'parent-authoritative-observation-boundary'
    }
    $temporaryPath = '{0}.{1}.tmp' -f `
        $fullPath,
        [guid]::NewGuid().ToString('N')
    try {
        $request | ConvertTo-Json -Depth 5 |
            Set-Content -LiteralPath $temporaryPath -Encoding utf8
        Move-Item -LiteralPath $temporaryPath -Destination $fullPath
    } finally {
        if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
    }
    return [pscustomobject]$request
}

function Wait-CollectorStopSignal {
    param(
        [System.Management.Automation.Job]$Job,
        [string]$SignalPath,
        [DateTimeOffset]$PlannedEndAt,
        [ValidateRange(1, 30)]
        [int]$SignalGraceSeconds = 5,
        [ValidateRange(50, 1000)]
        [int]$PollIntervalMilliseconds = 200,
        [scriptblock]$OnPoll = $null
    )

    $signalDeadlineAt = $PlannedEndAt.AddSeconds($SignalGraceSeconds)
    while ($true) {
        $now = [DateTimeOffset]::Now
        $signalResult = Read-CollectorStopSignal -SignalPath $SignalPath
        if ($null -ne $signalResult) {
            return $signalResult
        }

        if ($null -eq $Job -or
            $Job.State -in @('Completed', 'Failed', 'Stopped')) {
            return [pscustomobject][ordered]@{
                status = 'collector-ended-without-signal'
                signal = $null
                observed_at = $null
                signal_ended_at = $null
                observation_latency_ms = $null
                error_message = 'The event-trigger collector ended without a capture stop signal.'
            }
        }

        if ($now -gt $signalDeadlineAt) {
            return [pscustomobject][ordered]@{
                status = 'signal-deadline-exceeded'
                signal = $null
                observed_at = $null
                signal_ended_at = $null
                observation_latency_ms = $null
                error_message = (
                    'The capture stop signal was not observed within {0} seconds ' +
                    'of the planned observation end.' -f $SignalGraceSeconds
                )
            }
        }

        if ($null -ne $OnPoll) {
            & $OnPoll $now
        }
        Start-Sleep -Milliseconds $PollIntervalMilliseconds
    }
}

function Start-OperationalCollectorJob {
    param(
        [string]$ScriptPath,
        [string]$CollectorApiBase,
        [int]$CollectorSamples,
        [int]$CollectorDurationSec,
        [int]$CollectorIntervalSec,
        [int]$CollectorNormalIntervalSec,
        [int]$CollectorMemoryStateIntervalSec,
        [int]$CollectorMemoryDetailsIntervalSec,
        [string]$CollectorOutputRoot,
        [string]$CollectorSignalPath
    )

    return Start-Job `
        -ArgumentList @(
            $ScriptPath,
            $CollectorApiBase,
            $CollectorSamples,
            $CollectorDurationSec,
            $CollectorIntervalSec,
            $CollectorNormalIntervalSec,
            $CollectorMemoryStateIntervalSec,
            $CollectorMemoryDetailsIntervalSec,
            $CollectorOutputRoot,
            $CollectorSignalPath
        ) `
        -ScriptBlock {
            param(
                $JobScriptPath,
                $JobApiBase,
                $JobSamples,
                $JobDurationSec,
                $JobIntervalSec,
                $JobNormalIntervalSec,
                $JobMemoryStateIntervalSec,
                $JobMemoryDetailsIntervalSec,
                $JobOutputRoot,
                $JobSignalPath
            )
            & powershell.exe `
                -NoProfile `
                -ExecutionPolicy Bypass `
                -File $JobScriptPath `
                -ApiBase $JobApiBase `
                -Samples $JobSamples `
                -DurationSec $JobDurationSec `
                -IntervalSec $JobIntervalSec `
                -NormalEndpointIntervalSec $JobNormalIntervalSec `
                -MemoryStateIntervalSec $JobMemoryStateIntervalSec `
                -MemoryDetailsIntervalSec $JobMemoryDetailsIntervalSec `
                -TimeoutSec 1 `
                -OutputRoot $JobOutputRoot `
                -StopOnNewSpotConnectTimeout `
                -CaptureStopSignalPath $JobSignalPath 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw (
                    'The app evidence collector exited with code {0}.' -f
                        $LASTEXITCODE
                )
            }
        }
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-ImmutableJson {
    param(
        [object]$Value,
        [string]$Path,
        [int]$Depth = 10
    )

    if (Test-Path -LiteralPath $Path) {
        throw "Immutable evidence already exists: $Path"
    }
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $temporaryPath = '{0}.{1}.tmp' -f $Path, [Guid]::NewGuid().ToString('N')
    try {
        $Value |
            ConvertTo-Json -Depth $Depth |
            Set-Content -LiteralPath $temporaryPath -Encoding utf8
        Move-Item -LiteralPath $temporaryPath -Destination $Path -ErrorAction Stop
    } finally {
        if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
    }
}

function Get-SafeSpotFailureEvents {
    param([object]$Image)

    $events = Get-OptionalPropertyValue `
        -Object $Image `
        -Name 'source_port_recent_request_failure_events' `
        -DefaultValue @()
    return @(
        foreach ($event in @($events)) {
            [ordered]@{
                event_sequence = Get-OptionalPropertyValue $event 'event_sequence'
                event_at_utc = Get-OptionalPropertyValue $event 'event_at_utc'
                request_kind = Get-OptionalPropertyValue $event 'request_kind'
                state = Get-OptionalPropertyValue $event 'state'
                exception_class = Get-OptionalPropertyValue $event 'exception_class'
            }
        }
    )
}

function Get-SafeSpotImageSnapshot {
    param([object]$Image)

    $result = [ordered]@{}
    foreach ($name in @(
        'source_port_policy_version',
        'source_port_minimum_reuse_interval_seconds',
        'source_port_transport_started_count',
        'source_port_transport_success_count',
        'source_port_transport_failure_count',
        'source_port_image_started_count',
        'source_port_image_success_count',
        'source_port_image_failure_count',
        'source_port_temperature_started_count',
        'source_port_temperature_success_count',
        'source_port_temperature_failure_count',
        'source_port_internal_temperature_started_count',
        'source_port_internal_temperature_success_count',
        'source_port_internal_temperature_failure_count',
        'source_port_diagnostic_started_count',
        'source_port_diagnostic_success_count',
        'source_port_diagnostic_failure_count',
        'source_port_connection_test_started_count',
        'source_port_connection_test_success_count',
        'source_port_connection_test_failure_count',
        'source_port_bind_collision_count',
        'source_port_pool_acquire_wait_count',
        'source_port_pool_exhaustion_count',
        'source_port_reuse_violation_count',
        'source_port_request_event_count_total',
        'source_port_request_event_drop_count',
        'source_port_request_failure_event_count_total',
        'source_port_request_failure_event_drop_count',
        'image_upstream_request_count',
        'image_refresh_failure_count',
        'request_budget_total_background_max_per_sec'
    )) {
        $result[$name] = Get-OptionalPropertyValue -Object $Image -Name $name
    }
    $result['source_port_recent_request_failure_events'] = @(
        Get-SafeSpotFailureEvents -Image $Image
    )
    return $result
}

function New-ObservationBoundarySnapshot {
    param(
        [ValidateSet('start', 'end')]
        [string]$Role,
        [string]$LocalApiBase,
        [string]$LocalConfigPath,
        [string]$OutputPath
    )

    $startedAt = [DateTimeOffset]::Now
    $startedTicks = [Diagnostics.Stopwatch]::GetTimestamp()
    $backends = @(Get-Process -Name 'SmartFactoryBackend' -ErrorAction Stop)
    if ($backends.Count -ne 1 -or [string]::IsNullOrWhiteSpace($backends[0].Path)) {
        throw "Observation $Role boundary could not resolve one backend process."
    }
    $owners = @(
        Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction Stop |
            Select-Object -ExpandProperty OwningProcess -Unique
    )
    if ($owners.Count -ne 1 -or $owners[0] -ne $backends[0].Id) {
        throw "Observation $Role boundary port 8000 owner mismatch."
    }
    $health = Invoke-RestMethod `
        -Uri ('{0}/health' -f $LocalApiBase.TrimEnd('/')) `
        -TimeoutSec 5
    $spotConfig = Invoke-RestMethod `
        -Uri ('{0}/api/spot/config' -f $LocalApiBase.TrimEnd('/')) `
        -TimeoutSec 5
    $backendRoot = Split-Path -Parent $backends[0].Path
    $provenancePath = Join-Path `
        $backendRoot `
        '_internal\backend\build_provenance.json'
    $provenance = Get-Content -LiteralPath $provenancePath -Raw -Encoding utf8 |
        ConvertFrom-Json
    $completedTicks = [Diagnostics.Stopwatch]::GetTimestamp()
    $completedAt = [DateTimeOffset]::Now
    $latencyMs = [Math]::Round(
        (($completedTicks - $startedTicks) * 1000.0) /
            [Diagnostics.Stopwatch]::Frequency,
        3
    )
    $snapshot = [ordered]@{
        schema_version = 'spot-canary-observation-boundary-v1'
        boundary_role = $Role
        observed_at_started = $startedAt.ToString('o')
        observed_at_completed = $completedAt.ToString('o')
        capture_latency_ms = $latencyMs
        monotonic_ticks = [int64]$completedTicks
        monotonic_frequency = [int64][Diagnostics.Stopwatch]::Frequency
        backend_pid = [int]$backends[0].Id
        port_8000_owner = [int]$owners[0]
        app_version = [string]$health.app_version
        build_git_commit = [string]$provenance.git_commit
        config_sha256 = (
            Get-FileHash -LiteralPath $LocalConfigPath -Algorithm SHA256
        ).Hash
        image = Get-SafeSpotImageSnapshot -Image $spotConfig.image
        local_only = $true
        added_spot_requests = $false
    }
    Write-ImmutableJson -Value $snapshot -Path $OutputPath -Depth 12
    return [pscustomobject]$snapshot
}

function New-CanaryPostprocessState {
    param(
        [string]$LocalApiBase,
        [string]$LocalConfigPath,
        [object]$ObservationEnd,
        [string]$ObservationEndPath,
        [DateTimeOffset]$PostprocessStartedAt,
        [string]$OutputPath
    )

    $backends = @(Get-Process -Name 'SmartFactoryBackend' -ErrorAction Stop)
    if ($backends.Count -ne 1 -or [string]::IsNullOrWhiteSpace($backends[0].Path)) {
        throw 'Postprocess state could not resolve one backend process.'
    }
    $owners = @(
        Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction Stop |
            Select-Object -ExpandProperty OwningProcess -Unique
    )
    if ($owners.Count -ne 1) {
        throw 'Postprocess state port 8000 owner is ambiguous.'
    }
    $health = Invoke-RestMethod `
        -Uri ('{0}/health' -f $LocalApiBase.TrimEnd('/')) `
        -TimeoutSec 5
    $backendRoot = Split-Path -Parent $backends[0].Path
    $provenance = Get-Content `
        -LiteralPath (
            Join-Path $backendRoot '_internal\backend\build_provenance.json'
        ) `
        -Raw `
        -Encoding utf8 |
        ConvertFrom-Json
    $observedAt = [DateTimeOffset]::Now
    $current = [ordered]@{
        app_version = [string]$health.app_version
        backend_pid = [int]$backends[0].Id
        port_8000_owner = [int]$owners[0]
        build_git_commit = [string]$provenance.git_commit
        config_sha256 = (
            Get-FileHash -LiteralPath $LocalConfigPath -Algorithm SHA256
        ).Hash
    }
    $integrityFailures = @(
        foreach ($field in @(
            'app_version',
            'backend_pid',
            'port_8000_owner',
            'build_git_commit',
            'config_sha256'
        )) {
            if ([string]$current[$field] -cne [string]$ObservationEnd.$field) {
                'postprocess-state-changed:{0}' -f $field
            }
        }
    )
    $state = [ordered]@{
        schema_version = 'spot-canary-postprocess-state-v1'
        status = if ($integrityFailures.Count -eq 0) { 'complete' } else { 'changed' }
        postprocess_started_at = $PostprocessStartedAt.ToString('o')
        observed_at = $observedAt.ToString('o')
        postprocess_elapsed_seconds = [Math]::Round(
            ($observedAt - $PostprocessStartedAt).TotalSeconds,
            3
        )
        observation_end_sha256 = if (Test-Path `
            -LiteralPath $ObservationEndPath `
            -PathType Leaf) {
            (
                Get-FileHash `
                    -LiteralPath $ObservationEndPath `
                    -Algorithm SHA256
            ).Hash
        } else {
            $null
        }
        app_version = $current.app_version
        backend_pid = $current.backend_pid
        port_8000_owner = $current.port_8000_owner
        build_git_commit = $current.build_git_commit
        config_sha256 = $current.config_sha256
        integrity_failures = @($integrityFailures)
        local_only = $true
        added_spot_requests = $false
    }
    Write-ImmutableJson -Value $state -Path $OutputPath -Depth 8
    return [pscustomobject]$state
}

function Add-ClockCalibrationAnchor {
    param([string]$Path)

    [ordered]@{
        schema_version = 'spot-canary-clock-anchor-v1'
        wall_clock_at = [DateTimeOffset]::Now.ToString('o')
        monotonic_ticks = [int64][Diagnostics.Stopwatch]::GetTimestamp()
        monotonic_frequency = [int64][Diagnostics.Stopwatch]::Frequency
    } | ConvertTo-Json -Compress | Add-Content -LiteralPath $Path -Encoding utf8
}

function Get-ConfiguredSpotIp {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    $inSpotSection = $false
    foreach ($line in Get-Content -LiteralPath $Path -Encoding utf8 -ErrorAction Stop) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^\[(.+)\]$') {
            $inSpotSection = $Matches[1] -eq 'SPOT'
            continue
        }
        if ($inSpotSection -and $trimmed -match '^ip\s*=\s*(.+)$') {
            return $Matches[1].Trim()
        }
    }
    return $null
}

function Assert-ValidSpotIp {
    param([string]$Value)

    $parsed = $null
    $ok = [System.Net.IPAddress]::TryParse($Value, [ref]$parsed)
    if (-not $ok -or $null -eq $parsed -or
        $parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
        [System.Net.IPAddress]::IsLoopback($parsed)) {
        throw 'A valid SPOT IPv4 address was not found in config.ini. Specify -SpotIp on the real server.'
    }
}

function Invoke-PktmonCommand {
    param(
        [string[]]$Arguments,
        [string]$LogPath = "",
        [switch]$AllowFailure
    )

    $pktmon = Join-Path $env:SystemRoot 'System32\pktmon.exe'
    $originalConsoleOutputEncoding = [Console]::OutputEncoding
    try {
        # Modern pktmon writes localized text as UTF-8. Windows PowerShell 5.1
        # otherwise decodes captured output with the active OEM code page.
        [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
        $lines = @(& $pktmon @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    } finally {
        [Console]::OutputEncoding = $originalConsoleOutputEncoding
    }
    $text = ($lines | Out-String).TrimEnd()

    if (-not [string]::IsNullOrWhiteSpace($LogPath)) {
        $parent = Split-Path -Parent $LogPath
        if (-not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        $text | Set-Content -LiteralPath $LogPath -Encoding utf8
    }

    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw ("pktmon failed with exit code {0}." -f $exitCode)
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Text = $text
    }
}

function Get-PktmonFilterListState {
    param([string]$Text)

    $lines = @($Text -split "`r?`n" | ForEach-Object { $_.Trim() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

    # Every active filter is listed with a numeric ordinal. This part of the
    # pktmon output is stable across display languages.
    if (@($lines | Where-Object { $_ -match '^\d+\s+' }).Count -gt 0) {
        return 'Present'
    }

    $koreanNone = ([string][char]0xC5C6) + ([string][char]0xC74C)
    if (@($lines | Where-Object {
        $_ -eq 'None' -or
        $_ -eq $koreanNone -or
        $_ -match '^There (?:is|are) no packet filters\.?$'
    }).Count -gt 0) {
        return 'Empty'
    }

    return 'Unknown'
}

function Get-PktmonPacketDirectionState {
    param(
        [string]$Text,
        [string]$TargetIp,
        [int]$TargetPort = 80
    )

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return [pscustomobject]@{
            OutboundCount = 0
            InboundCount = 0
            Passed = $false
        }
    }

    $escapedTarget = [regex]::Escape($TargetIp)
    $escapedPort = [regex]::Escape([string]$TargetPort)
    $ipv4WithPort = '(?:\d{1,3}\.){3}\d{1,3}\.\d+'
    $outboundPattern = '{0}\s*>\s*{1}\.{2}:\s*tcp\b' -f `
        $ipv4WithPort, $escapedTarget, $escapedPort
    $inboundPattern = '{0}\.{1}\s*>\s*{2}:\s*tcp\b' -f `
        $escapedTarget, $escapedPort, $ipv4WithPort

    $outboundCount = [regex]::Matches(
        $Text,
        $outboundPattern,
        [Text.RegularExpressions.RegexOptions]::IgnoreCase
    ).Count
    $inboundCount = [regex]::Matches(
        $Text,
        $inboundPattern,
        [Text.RegularExpressions.RegexOptions]::IgnoreCase
    ).Count

    return [pscustomobject]@{
        OutboundCount = $outboundCount
        InboundCount = $inboundCount
        Passed = ($outboundCount -gt 0 -and $inboundCount -gt 0)
    }
}

function Export-ProcessAndPortState {
    param(
        [string]$Directory,
        [string]$Suffix,
        [int]$BackendPort
    )

    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'SmartFactory|Electron|python|uvicorn' } |
        Select-Object ProcessId, ParentProcessId, Name, CreationDate, ExecutablePath, CommandLine |
        Export-Csv -LiteralPath (Join-Path $Directory ("process_{0}.csv" -f $Suffix)) `
            -NoTypeInformation -Encoding utf8

    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -eq $BackendPort } |
        Select-Object LocalAddress, LocalPort, OwningProcess, State |
        Export-Csv -LiteralPath (Join-Path $Directory ("port_{0}.csv" -f $Suffix)) `
            -NoTypeInformation -Encoding utf8
}

function Export-NicState {
    param(
        [string]$Path
    )

    Get-NetAdapterStatistics -ErrorAction Stop |
        Select-Object Name, ReceivedBytes, SentBytes, ReceivedUnicastPackets, SentUnicastPackets,
            ReceivedDiscardedPackets, OutboundDiscardedPackets, ReceivedPacketErrors,
            OutboundPacketErrors |
        Export-Csv -LiteralPath $Path -NoTypeInformation -Encoding utf8
}

function New-NicDelta {
    param(
        [string]$BeforePath,
        [string]$AfterPath,
        [string]$OutputPath
    )

    $beforeRows = @(Import-Csv -LiteralPath $BeforePath -Encoding utf8)
    $afterRows = @(Import-Csv -LiteralPath $AfterPath -Encoding utf8)
    $beforeByName = @{}
    foreach ($row in $beforeRows) {
        $beforeByName[[string]$row.Name] = $row
    }

    $properties = @(
        'ReceivedBytes',
        'SentBytes',
        'ReceivedUnicastPackets',
        'SentUnicastPackets',
        'ReceivedDiscardedPackets',
        'OutboundDiscardedPackets',
        'ReceivedPacketErrors',
        'OutboundPacketErrors'
    )

    $result = foreach ($after in $afterRows) {
        $name = [string]$after.Name
        $before = $beforeByName[$name]
        if ($null -eq $before) {
            continue
        }
        $delta = [ordered]@{ Name = $name }
        foreach ($property in $properties) {
            $delta[$property] = [long]$after.$property - [long]$before.$property
        }
        [pscustomobject]$delta
    }

    $result | Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Encoding utf8
}

function Get-WindowsTcpState {
    if ($null -eq ("SmartFactoryLogger.FieldEvidence.TcpStatisticsNative" -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace SmartFactoryLogger.FieldEvidence
{
    [StructLayout(LayoutKind.Sequential)]
    public struct MibTcpStats
    {
        public UInt32 RtoAlgorithm;
        public UInt32 RtoMinimum;
        public UInt32 RtoMaximum;
        public UInt32 MaximumConnections;
        public UInt32 ActiveOpens;
        public UInt32 PassiveOpens;
        public UInt32 AttemptFailures;
        public UInt32 EstablishedResets;
        public UInt32 CurrentEstablished;
        public UInt32 SegmentsReceived;
        public UInt32 SegmentsSent;
        public UInt32 SegmentsRetransmitted;
        public UInt32 ReceiveErrors;
        public UInt32 ResetSegmentsSent;
        public UInt32 ConnectionsTotal;
    }

    public static class TcpStatisticsNative
    {
        [DllImport("iphlpapi.dll", ExactSpelling = true)]
        public static extern UInt32 GetTcpStatisticsEx(
            ref MibTcpStats statistics,
            UInt32 addressFamily
        );
    }
}
'@
    }

    $statistics = New-Object SmartFactoryLogger.FieldEvidence.MibTcpStats
    $result = [SmartFactoryLogger.FieldEvidence.TcpStatisticsNative]::GetTcpStatisticsEx(
        [ref]$statistics,
        2
    )
    if ($result -ne 0) {
        throw ("GetTcpStatisticsEx(AF_INET) failed with code {0}." -f $result)
    }
    return [pscustomobject][ordered]@{
        schema_version = "windows-tcp-ipv4-state-v1"
        captured_at_kst = (Get-Date).ToString("o")
        scope = "windows-ipv4-global"
        active_opens = [uint64]$statistics.ActiveOpens
        passive_opens = [uint64]$statistics.PassiveOpens
        failed_connection_attempts = [uint64]$statistics.AttemptFailures
        established_connection_resets = [uint64]$statistics.EstablishedResets
        current_established = [uint64]$statistics.CurrentEstablished
        segments_received = [uint64]$statistics.SegmentsReceived
        segments_sent = [uint64]$statistics.SegmentsSent
        segments_retransmitted = [uint64]$statistics.SegmentsRetransmitted
        receive_errors = [uint64]$statistics.ReceiveErrors
        reset_segments_sent = [uint64]$statistics.ResetSegmentsSent
        connections_total = [uint64]$statistics.ConnectionsTotal
    }
}

function Export-WindowsTcpState {
    param([string]$Path)

    $state = Get-WindowsTcpState
    $state | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $Path -Encoding utf8
    return $state
}

function Get-UInt32CounterDelta {
    param(
        [uint64]$Before,
        [uint64]$After
    )

    if ($After -ge $Before) {
        return [uint64]($After - $Before)
    }
    return [uint64](([uint64]4294967296 - $Before) + $After)
}

function New-WindowsTcpDelta {
    param(
        [string]$BeforePath,
        [string]$AfterPath,
        [string]$OutputPath
    )

    $before = Get-Content -LiteralPath $BeforePath -Raw -Encoding utf8 |
        ConvertFrom-Json
    $after = Get-Content -LiteralPath $AfterPath -Raw -Encoding utf8 |
        ConvertFrom-Json
    if ($before.schema_version -ne "windows-tcp-ipv4-state-v1" -or
        $after.schema_version -ne "windows-tcp-ipv4-state-v1") {
        throw "Windows TCP state schema is invalid."
    }

    $counterNames = @(
        "active_opens",
        "passive_opens",
        "failed_connection_attempts",
        "established_connection_resets",
        "segments_received",
        "segments_sent",
        "segments_retransmitted",
        "receive_errors",
        "reset_segments_sent",
        "connections_total"
    )
    $delta = [ordered]@{
        schema_version = "windows-tcp-ipv4-delta-v1"
        scope = "windows-ipv4-global"
        captured_from_kst = [string]$before.captured_at_kst
        captured_to_kst = [string]$after.captured_at_kst
        current_established_start = [uint64]$before.current_established
        current_established_end = [uint64]$after.current_established
    }
    foreach ($name in $counterNames) {
        $delta["{0}_delta" -f $name] = Get-UInt32CounterDelta `
            -Before ([uint64]$before.$name) `
            -After ([uint64]$after.$name)
    }
    $delta["interpretation_limit"] = (
        "Counters cover all Windows IPv4 TCP traffic and are not SPOT-specific."
    )
    $result = [pscustomobject]$delta
    $result | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $OutputPath -Encoding utf8
    return $result
}

function Copy-ApplicationLogs {
    param(
        [string]$OutputDirectory
    )

    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    $roots = @(
        (Join-Path $env:APPDATA 'SmartFactoryLogger'),
        (Join-Path $env:LOCALAPPDATA 'SmartFactoryLogger')
    ) | Select-Object -Unique

    $index = @()
    $copyNumber = 0
    foreach ($root in $roots) {
        if (-not (Test-Path -LiteralPath $root -PathType Container)) {
            continue
        }
        $files = Get-ChildItem -LiteralPath $root -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -in @('system.log', 'status.log', 'crash.log') }
        foreach ($file in $files) {
            $copyNumber += 1
            $copyName = '{0:d2}_{1}' -f $copyNumber, $file.Name
            $destination = Join-Path $OutputDirectory $copyName
            Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
            $hash = Get-FileHash -LiteralPath $destination -Algorithm SHA256
            $index += [pscustomobject]@{
                copied_name = $copyName
                original_path = $file.FullName
                size = $file.Length
                last_write_time = $file.LastWriteTime.ToString('o')
                sha256 = $hash.Hash.ToLowerInvariant()
            }
        }
    }
    $index | Export-Csv -LiteralPath (Join-Path $OutputDirectory 'log_copy_index.csv') `
        -NoTypeInformation -Encoding utf8
}

function Protect-Text {
    param(
        [string]$Text,
        [string]$TargetIp,
        [string[]]$ServerIps
    )

    if ($null -eq $Text) {
        return ''
    }

    $safe = $Text
    if (-not [string]::IsNullOrWhiteSpace($TargetIp)) {
        $safe = $safe -replace [regex]::Escape($TargetIp), '<SPOT_IP>'
    }
    foreach ($serverIp in @($ServerIps)) {
        if (-not [string]::IsNullOrWhiteSpace($serverIp)) {
            $safe = $safe -replace [regex]::Escape($serverIp), '<SERVER_IP>'
        }
    }
    $safe = $safe -replace '(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)', '<IP_REDACTED>'
    $safe = $safe -replace '(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])', '<MAC_REDACTED>'
    return $safe
}

function New-RawHashManifest {
    param(
        [string]$RawRoot,
        [string]$OutputPath
    )

    $resolvedRoot = (Resolve-Path -LiteralPath $RawRoot).Path.TrimEnd('\')
    $rows = Get-ChildItem -LiteralPath $RawRoot -File -Recurse | ForEach-Object {
        $relative = $_.FullName.Substring($resolvedRoot.Length).TrimStart('\')
        $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        [pscustomobject]@{
            relative_path = $relative
            size = $_.Length
            sha256 = $hash.Hash.ToLowerInvariant()
        }
    }
    $rows | Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Encoding utf8
}

function Remove-TransientPacketArtifact {
    param(
        [string]$Path,
        [string]$NetworkRoot
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }
    $allowedNames = @(
        'spot_tcp.etl',
        'spot_tcp.pcapng',
        'pktmon_direction_probe.etl'
    )
    $fullPath = [IO.Path]::GetFullPath($Path)
    $fullRoot = [IO.Path]::GetFullPath($NetworkRoot).TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith($fullRoot, [StringComparison]::OrdinalIgnoreCase) -or
        ([IO.Path]::GetFileName($fullPath) -notin $allowedNames)) {
        throw 'Refusing to delete an unexpected packet artifact path.'
    }
    Remove-Item -LiteralPath $fullPath -Force
}

function Export-SafeFramingAnalyzerConsole {
    param(
        [string]$RawPath,
        [string]$SafePath
    )

    if (-not (Test-Path -LiteralPath $RawPath -PathType Leaf)) {
        throw 'The private analyzer console log was not created.'
    }
    $safeLines = @(
        Get-Content -LiteralPath $RawPath |
            Where-Object {
                $_ -match '^\[PROGRESS\] HTTP framing analysis \d{1,3}% complete; finalized events=\d+; active flows=\d+$' -or
                $_ -match '^FRAMING_ANALYSIS_PASS events=\d+ header_complete=\d+ header_incomplete=\d+ coverage=[a-z-]+ overwrite=(?:True|False) payload_retained=false$'
            }
    )
    $passLines = @($safeLines | Where-Object { $_ -match '^FRAMING_ANALYSIS_PASS ' })
    if ($passLines.Count -ne 1) {
        throw 'The analyzer did not emit exactly one safe completion record.'
    }
    $safeLines | Set-Content -LiteralPath $SafePath -Encoding utf8
    return [pscustomobject]@{
        SafeLineCount = $safeLines.Count
        PassLineCount = $passLines.Count
    }
}

function Get-PercentileValue {
    param(
        [double[]]$Values,
        [ValidateRange(0.0, 1.0)]
        [double]$Percentile
    )

    $sorted = @($Values | Sort-Object)
    if ($sorted.Count -eq 0) {
        return $null
    }
    $index = [Math]::Max(
        0,
        [Math]::Min(
            $sorted.Count - 1,
            [int][Math]::Ceiling($Percentile * $sorted.Count) - 1
        )
    )
    return [double]$sorted[$index]
}

function Get-SwitchEvidenceState {
    param([string]$Directory)

    $files = @(
        Get-ChildItem -LiteralPath $Directory -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne 'switch_log_request.txt' }
    )
    $allowedPattern = '^switch_(?:start|end|link_events)_(?:server|spot|combined)(?:_\d+)?\.[a-z0-9]{1,8}$'
    $invalidFiles = @($files | Where-Object { $_.Name -notmatch $allowedPattern })
    $emptyFiles = @($files | Where-Object { $_.Length -le 0 })
    $validFiles = @(
        $files |
            Where-Object {
                $_.Name -match $allowedPattern -and $_.Length -gt 0
            }
    )
    $startCombined = @($validFiles | Where-Object { $_.Name -match '^switch_start_combined(?:_\d+)?\.' }).Count -gt 0
    $startServer = @($validFiles | Where-Object { $_.Name -match '^switch_start_server(?:_\d+)?\.' }).Count -gt 0
    $startSpot = @($validFiles | Where-Object { $_.Name -match '^switch_start_spot(?:_\d+)?\.' }).Count -gt 0
    $endCombined = @($validFiles | Where-Object { $_.Name -match '^switch_end_combined(?:_\d+)?\.' }).Count -gt 0
    $endServer = @($validFiles | Where-Object { $_.Name -match '^switch_end_server(?:_\d+)?\.' }).Count -gt 0
    $endSpot = @($validFiles | Where-Object { $_.Name -match '^switch_end_spot(?:_\d+)?\.' }).Count -gt 0

    return [pscustomobject]@{
        FileCount = $files.Count
        InvalidFileCount = $invalidFiles.Count
        EmptyFileCount = $emptyFiles.Count
        StartComplete = ($startCombined -or ($startServer -and $startSpot))
        EndComplete = ($endCombined -or ($endServer -and $endSpot))
        Unavailable = $false
    }
}

function Wait-SwitchEvidence {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Directory,
        [Parameter(Mandatory = $true)]
        [ValidateSet('Start', 'End')]
        [string]$Phase,
        [switch]$AllowSkip,
        [switch]$AllowUnavailable
    )

    if ($AllowUnavailable -and $Phase -ne 'Start') {
        throw 'UNAVAILABLE can only be declared before packet capture starts.'
    }

    $phaseLower = $Phase.ToLowerInvariant()
    $combinedName = "switch_${phaseLower}_combined.png"
    $serverName = "switch_${phaseLower}_server.png"
    $spotName = "switch_${phaseLower}_spot.png"
    while ($true) {
        $optionText = if ($AllowSkip) {
            ' Type SKIP only if the evidence cannot be saved; the run will be finalized as FAILED.'
        } elseif ($AllowUnavailable) {
            (
                ' Type UNAVAILABLE only when managed-switch access does not exist; ' +
                'server-side collection will continue as PARTIAL. Type CANCEL to stop.'
            )
        } else {
            ' Type CANCEL to stop before packet collection starts.'
        }
        $answer = [string](Read-Host (
            'Save the required switch evidence, then press Enter to verify it.' +
            $optionText
        ))
        $answer = $answer.Trim()
        if (-not $AllowSkip -and $answer.Equals('CANCEL', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Collection cancelled before packet capture because switch start evidence was not confirmed.'
        }

        $state = Get-SwitchEvidenceState -Directory $Directory
        if ($AllowUnavailable -and
            $answer.Equals('UNAVAILABLE', [StringComparison]::OrdinalIgnoreCase)) {
            if ($state.FileCount -gt 0) {
                Write-Host (
                    '[NOT READY] UNAVAILABLE cannot bypass files already placed in the switch evidence folder.'
                ) -ForegroundColor Red
                Write-Host (
                    'Verify the existing evidence files, or type CANCEL and report the result.'
                ) -ForegroundColor Yellow
                continue
            }
            $state.Unavailable = $true
            Write-Warning (
                'Managed-switch evidence was declared unavailable. ' +
                'Server NIC, TCP, ping, HTTP, and app evidence will be collected as PARTIAL.'
            )
            return $state
        }
        if ($AllowSkip -and $answer.Equals('SKIP', [StringComparison]::OrdinalIgnoreCase)) {
            Write-Warning 'Switch end evidence was explicitly skipped. The evidence package will be finalized as FAILED.'
            return $state
        }

        $phaseComplete = if ($Phase -eq 'Start') {
            $state.StartComplete
        } else {
            $state.EndComplete
        }
        if ($phaseComplete -and
            $state.InvalidFileCount -eq 0 -and
            $state.EmptyFileCount -eq 0) {
            Write-Host (
                '[OK] Switch {0} evidence verified. files={1}' -f `
                    $phaseLower,
                    $state.FileCount
            ) -ForegroundColor Green
            return $state
        }

        Write-Host '[NOT READY] Required switch evidence has not been verified.' -ForegroundColor Red
        Write-Host ('Folder: {0}' -f $Directory) -ForegroundColor Yellow
        Write-Host (
            'Save either {0}, or both {1} and {2}.' -f `
                $combinedName,
                $serverName,
                $spotName
        ) -ForegroundColor Yellow
        if ($state.InvalidFileCount -gt 0) {
            Write-Host (
                '[NOT READY] {0} file(s) use an unsupported or non-generic filename.' -f `
                    $state.InvalidFileCount
            ) -ForegroundColor Red
        }
        if ($state.EmptyFileCount -gt 0) {
            Write-Host (
                '[NOT READY] {0} evidence file(s) are empty.' -f `
                    $state.EmptyFileCount
            ) -ForegroundColor Red
        }
    }
}

function Resolve-CollectionResult {
    param(
        [bool]$HasRunFailure,
        [bool]$RequiredEvidenceFailureCreated,
        [bool]$SwitchEvidenceUnavailable
    )

    if ($HasRunFailure) {
        return [pscustomobject]@{
            Status = 'FAILED'
            CollectionReasonCode = if ($RequiredEvidenceFailureCreated) {
                'required-evidence-missing'
            } else {
                'runtime-error'
            }
            FailureReasonCode = if ($RequiredEvidenceFailureCreated) {
                'required-evidence-missing'
            } else {
                'runtime-error'
            }
            ExitCode = 1
        }
    }
    if ($SwitchEvidenceUnavailable) {
        return [pscustomobject]@{
            Status = 'PARTIAL'
            CollectionReasonCode = 'switch-evidence-unavailable'
            FailureReasonCode = $null
            ExitCode = 2
        }
    }
    return [pscustomobject]@{
        Status = 'COLLECTED'
        CollectionReasonCode = 'complete'
        FailureReasonCode = $null
        ExitCode = 0
    }
}

function Get-ObservationPlan {
    param(
        [ValidateRange(5, 180)]
        [int]$Minutes,

        [switch]$EventTrigger
    )

    $intervalSeconds = if ($EventTrigger) { 1 } else { 5 }
    $samplesPerMinute = [int](60 / $intervalSeconds)
    $maximumSamples = [int]($Minutes * $samplesPerMinute)
    $durationSeconds = [int]($Minutes * 60)
    return [pscustomobject]@{
        Minutes = $Minutes
        IntervalSeconds = $intervalSeconds
        SamplesPerMinute = $samplesPerMinute
        MaximumSamples = $maximumSamples
        DurationSeconds = $durationSeconds
        NormalEndpointIntervalSeconds = 5
        MemoryStateIntervalSeconds = 30
        MemoryDetailsIntervalSeconds = 60
        EventTrigger = [bool]$EventTrigger
    }
}

function Invoke-SelfTest {
    param([int]$RequestedObservationMinutes)

    $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $tempRoot = Join-Path $tempBase ('sfl-evidence-selftest-{0}' -f [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    try {
        $configPath = Join-Path $tempRoot 'config.ini'
        "[SPOT]`nip = 192.0.2.10" | Set-Content -LiteralPath $configPath -Encoding ascii
        $configuredIp = Get-ConfiguredSpotIp -Path $configPath
        if ($configuredIp -ne '192.0.2.10') {
            throw 'Self-test failed: config parser.'
        }

        $timingStart = [pscustomobject]@{
            monotonic_ticks = 10000000
            monotonic_frequency = 10000000
        }
        $timingEnd = [pscustomobject]@{
            monotonic_ticks = 9019695530
            monotonic_frequency = 10000000
        }
        $timing = Get-ObservationTimingSummary `
            -ObservationStartSnapshot $timingStart `
            -ObservationEndSnapshot $timingEnd `
            -AppObservationElapsedSeconds 896.785 `
            -FallbackStartedAt ([DateTimeOffset]'2026-08-31T09:18:26+09:00') `
            -FallbackEndedAt ([DateTimeOffset]'2026-08-31T09:33:27+09:00')
        if ($timing.source -cne
                'parent-authoritative-monotonic-boundary' -or
            [double]$timing.elapsed_seconds -ne 900.97 -or
            [double]$timing.app_collector_elapsed_seconds -ne 896.785) {
            throw 'Self-test failed: authoritative observation timing precedence.'
        }

        $protected = Protect-Text `
            -Text 'src=192.0.2.10 dst=198.51.100.20 mac=AA-BB-CC-DD-EE-FF other=203.0.113.7' `
            -TargetIp '192.0.2.10' `
            -ServerIps @('198.51.100.20')
        if ($protected -match '192\.0\.2\.10|198\.51\.100\.20|203\.0\.113\.7|AA-BB-CC-DD-EE-FF') {
            throw 'Self-test failed: sensitive network identifier remained.'
        }
        foreach ($label in @('<SPOT_IP>', '<SERVER_IP>', '<IP_REDACTED>', '<MAC_REDACTED>')) {
            if ($protected -notmatch [regex]::Escape($label)) {
                throw ('Self-test failed: missing redaction label {0}.' -f $label)
            }
        }

        $beforePath = Join-Path $tempRoot 'before.csv'
        $afterPath = Join-Path $tempRoot 'after.csv'
        $deltaPath = Join-Path $tempRoot 'delta.csv'
        [pscustomobject]@{
            Name = 'NIC1'; ReceivedBytes = 100; SentBytes = 200
            ReceivedUnicastPackets = 10; SentUnicastPackets = 20
            ReceivedDiscardedPackets = 1; OutboundDiscardedPackets = 2
            ReceivedPacketErrors = 3; OutboundPacketErrors = 4
        } | Export-Csv -LiteralPath $beforePath -NoTypeInformation -Encoding utf8
        [pscustomobject]@{
            Name = 'NIC1'; ReceivedBytes = 150; SentBytes = 260
            ReceivedUnicastPackets = 15; SentUnicastPackets = 27
            ReceivedDiscardedPackets = 1; OutboundDiscardedPackets = 3
            ReceivedPacketErrors = 3; OutboundPacketErrors = 5
        } | Export-Csv -LiteralPath $afterPath -NoTypeInformation -Encoding utf8
        New-NicDelta -BeforePath $beforePath -AfterPath $afterPath -OutputPath $deltaPath
        $delta = Import-Csv -LiteralPath $deltaPath -Encoding utf8
        if ([long]$delta.ReceivedBytes -ne 50 -or
            [long]$delta.OutboundDiscardedPackets -ne 1 -or
            [long]$delta.OutboundPacketErrors -ne 1) {
            throw 'Self-test failed: NIC delta.'
        }

        $tcpBeforePath = Join-Path $tempRoot 'tcp_before.json'
        $tcpAfterPath = Join-Path $tempRoot 'tcp_after.json'
        $tcpDeltaPath = Join-Path $tempRoot 'tcp_delta.json'
        [pscustomobject][ordered]@{
            schema_version = 'windows-tcp-ipv4-state-v1'
            captured_at_kst = '2026-07-24T13:00:00+09:00'
            scope = 'windows-ipv4-global'
            active_opens = 100
            passive_opens = 200
            failed_connection_attempts = 10
            established_connection_resets = 20
            current_established = 5
            segments_received = 1000
            segments_sent = 2000
            segments_retransmitted = 30
            receive_errors = 2
            reset_segments_sent = 40
            connections_total = 300
        } | ConvertTo-Json -Depth 4 |
            Set-Content -LiteralPath $tcpBeforePath -Encoding utf8
        [pscustomobject][ordered]@{
            schema_version = 'windows-tcp-ipv4-state-v1'
            captured_at_kst = '2026-07-24T13:01:15+09:00'
            scope = 'windows-ipv4-global'
            active_opens = 140
            passive_opens = 205
            failed_connection_attempts = 12
            established_connection_resets = 23
            current_established = 7
            segments_received = 1600
            segments_sent = 2700
            segments_retransmitted = 34
            receive_errors = 2
            reset_segments_sent = 43
            connections_total = 345
        } | ConvertTo-Json -Depth 4 |
            Set-Content -LiteralPath $tcpAfterPath -Encoding utf8
        $tcpDelta = New-WindowsTcpDelta `
            -BeforePath $tcpBeforePath `
            -AfterPath $tcpAfterPath `
            -OutputPath $tcpDeltaPath
        if ([uint64]$tcpDelta.active_opens_delta -ne 40 -or
            [uint64]$tcpDelta.failed_connection_attempts_delta -ne 2 -or
            [uint64]$tcpDelta.established_connection_resets_delta -ne 3 -or
            [uint64]$tcpDelta.reset_segments_sent_delta -ne 3 -or
            [uint64]$tcpDelta.current_established_start -ne 5 -or
            [uint64]$tcpDelta.current_established_end -ne 7 -or
            (Get-UInt32CounterDelta -Before 4294967294 -After 3) -ne 5) {
            throw 'Self-test failed: Windows TCP delta.'
        }
        $liveTcpState = Get-WindowsTcpState
        if ($liveTcpState.schema_version -ne 'windows-tcp-ipv4-state-v1' -or
            $liveTcpState.scope -ne 'windows-ipv4-global') {
            throw 'Self-test failed: Windows TCP state.'
        }

        $rawRoot = Join-Path $tempRoot 'raw'
        New-Item -ItemType Directory -Path $rawRoot | Out-Null
        'evidence' | Set-Content -LiteralPath (Join-Path $rawRoot 'sample.txt') -Encoding ascii
        $hashPath = Join-Path $tempRoot 'hash.csv'
        New-RawHashManifest -RawRoot $rawRoot -OutputPath $hashPath
        $hashRow = Import-Csv -LiteralPath $hashPath -Encoding utf8
        if ($hashRow.relative_path -ne 'sample.txt' -or $hashRow.sha256 -notmatch '^[a-f0-9]{64}$') {
            throw 'Self-test failed: hash manifest.'
        }

        $transientPath = Join-Path $tempRoot 'spot_tcp.pcapng'
        'transient-packet-data' | Set-Content -LiteralPath $transientPath -Encoding ascii
        Remove-TransientPacketArtifact -Path $transientPath -NetworkRoot $tempRoot
        if (Test-Path -LiteralPath $transientPath -PathType Leaf) {
            throw 'Self-test failed: transient packet artifact cleanup.'
        }

        $rawAnalyzerConsolePath = Join-Path $tempRoot 'analyzer_raw.txt'
        $safeAnalyzerConsolePath = Join-Path $tempRoot 'analyzer_safe.txt'
        @(
            '[PROGRESS] HTTP framing analysis 10% complete; finalized events=12; active flows=1',
            'At C:\Users\private\analyze-spot-http-framing.ps1:42 char:1',
            'FRAMING_ANALYSIS_PASS events=123 header_complete=120 header_incomplete=3 coverage=capture-overwrite-detected overwrite=True payload_retained=false'
        ) | Set-Content -LiteralPath $rawAnalyzerConsolePath -Encoding unicode
        $consoleExport = Export-SafeFramingAnalyzerConsole `
            -RawPath $rawAnalyzerConsolePath `
            -SafePath $safeAnalyzerConsolePath
        $safeAnalyzerConsole = Get-Content -LiteralPath $safeAnalyzerConsolePath -Raw -Encoding utf8
        if ($consoleExport.SafeLineCount -ne 2 -or
            $consoleExport.PassLineCount -ne 1 -or
            $safeAnalyzerConsole -match 'C:\\Users|char:') {
            throw 'Self-test failed: analyzer console privacy filter.'
        }

        $koreanNone = ([string][char]0xC5C6) + ([string][char]0xC74C)
        $emptyFilterOutputs = @(
            "Packet Filters:`n    None",
            'There are no packet filters.',
            "Packet Filters:`n    $koreanNone"
        )
        foreach ($filterOutput in $emptyFilterOutputs) {
            if ((Get-PktmonFilterListState -Text $filterOutput) -ne 'Empty') {
                throw 'Self-test failed: empty pktmon filter list.'
            }
        }
        $presentFilterOutput = "Packet Filters:`n # Name Protocol`n - ---- --------`n 1 SpotHttpValidation TCP"
        if ((Get-PktmonFilterListState -Text $presentFilterOutput) -ne 'Present') {
            throw 'Self-test failed: active pktmon filter list.'
        }
        if ((Get-PktmonFilterListState -Text 'Unexpected successful output') -ne 'Unknown') {
            throw 'Self-test failed: unknown pktmon filter list.'
        }

        $bidirectionalPacketText = @'
09:00:00.0000000 packet
    Ethernet, IPv4, length 54: 198.51.100.20.51000 > 192.0.2.10.80: tcp 0
09:00:00.0010000 packet
    Ethernet, IPv4, length 60: 192.0.2.10.80 > 198.51.100.20.51000: tcp 0
'@
        $bidirectionalState = Get-PktmonPacketDirectionState `
            -Text $bidirectionalPacketText -TargetIp '192.0.2.10'
        if (-not $bidirectionalState.Passed -or
            $bidirectionalState.OutboundCount -ne 1 -or
            $bidirectionalState.InboundCount -ne 1) {
            throw 'Self-test failed: bidirectional packet direction parser.'
        }

        $outboundOnlyPacketText = `
            'Ethernet, IPv4, length 54: 198.51.100.20.51000 > 192.0.2.10.80: tcp 0'
        $outboundOnlyState = Get-PktmonPacketDirectionState `
            -Text $outboundOnlyPacketText -TargetIp '192.0.2.10'
        if ($outboundOnlyState.Passed -or
            $outboundOnlyState.OutboundCount -ne 1 -or
            $outboundOnlyState.InboundCount -ne 0) {
            throw 'Self-test failed: one-way packet direction must not pass.'
        }

        $smokePlan = Get-ObservationPlan -Minutes 15
        $canaryPlan = Get-ObservationPlan -Minutes 120
        $requestedPlan = Get-ObservationPlan -Minutes $RequestedObservationMinutes
        $triggerPlan = Get-ObservationPlan -Minutes 120 -EventTrigger
        if ($smokePlan.MaximumSamples -ne 180 -or
            $smokePlan.DurationSeconds -ne 900 -or
            $smokePlan.MemoryDetailsIntervalSeconds -ne 60) {
            throw 'Self-test failed: 15-minute observation plan.'
        }
        if ($canaryPlan.MaximumSamples -ne 1440 -or $canaryPlan.DurationSeconds -ne 7200) {
            throw 'Self-test failed: 120-minute observation plan.'
        }
        if ($requestedPlan.Minutes -ne $RequestedObservationMinutes -or
            $requestedPlan.MaximumSamples -ne ($RequestedObservationMinutes * 12) -or
            $requestedPlan.DurationSeconds -ne ($RequestedObservationMinutes * 60)) {
            throw 'Self-test failed: requested observation plan.'
        }
        if (-not $triggerPlan.EventTrigger -or
            $triggerPlan.IntervalSeconds -ne 1 -or
            $triggerPlan.MaximumSamples -ne 7200 -or
            $triggerPlan.NormalEndpointIntervalSeconds -ne 5 -or
            $triggerPlan.DurationSeconds -ne 7200) {
            throw 'Self-test failed: event-trigger observation plan.'
        }
        if ($StopOnNewSpotConnectTimeout -and
            $PostTriggerCaptureSeconds -ne 75) {
            throw 'Self-test failed: event-trigger post-capture tail must be 75 seconds.'
        }

        $dummyCollectorPath = Join-Path $tempRoot 'dummy_operational_collector.ps1'
        @'
param(
  [string]$ApiBase,
  [int]$Samples,
  [int]$DurationSec,
  [int]$IntervalSec,
  [int]$NormalEndpointIntervalSec,
  [int]$MemoryStateIntervalSec,
  [int]$MemoryDetailsIntervalSec,
  [int]$TimeoutSec,
  [string]$OutputRoot,
  [switch]$StopOnNewSpotConnectTimeout,
  [string]$CaptureStopSignalPath
)
[ordered]@{
  schema_version = 'spot-connecttimeout-capture-stop-v1'
  stop_reason = 'deadline-reached-without-trigger'
  trigger_detected = $false
  trigger_source = $null
  trigger_error_type = $null
  trigger_detected_at = $null
  trigger_error_at = $null
  trigger_detection_latency_ms = $null
  baseline_repeat_total = 112
  observed_repeat_total = 112
  repeat_delta = 0
  collection_ended_at = (Get-Date).ToString('o')
} | ConvertTo-Json -Depth 5 |
  Set-Content -LiteralPath $CaptureStopSignalPath -Encoding utf8
Write-Output 'DUMMY_TRIGGER_JOB_PASS'
'@ | Set-Content -LiteralPath $dummyCollectorPath -Encoding utf8
        $dummyOutputRoot = Join-Path $tempRoot 'dummy_output'
        New-Item -ItemType Directory -Path $dummyOutputRoot | Out-Null
        $dummySignalPath = Join-Path $dummyOutputRoot 'capture_stop_signal.json'
        $dummyConsolePath = Join-Path $dummyOutputRoot 'collector_console.txt'
        $dummyJob = Start-OperationalCollectorJob `
            -ScriptPath $dummyCollectorPath `
            -CollectorApiBase 'http://127.0.0.1:1' `
            -CollectorSamples 1 `
            -CollectorDurationSec 1 `
            -CollectorIntervalSec 1 `
            -CollectorNormalIntervalSec 5 `
            -CollectorMemoryStateIntervalSec 30 `
            -CollectorMemoryDetailsIntervalSec 60 `
            -CollectorOutputRoot $dummyOutputRoot `
            -CollectorSignalPath $dummySignalPath
        try {
            Wait-Job -Job $dummyJob -Timeout 10 | Out-Null
            Receive-CollectorJobOutput `
                -Job $dummyJob `
                -ConsolePath $dummyConsolePath
            if ($dummyJob.State -ne 'Completed' -or
                -not (Test-Path -LiteralPath $dummySignalPath -PathType Leaf) -or
                -not (Test-Path -LiteralPath $dummyConsolePath -PathType Leaf) -or
                (Get-Content -LiteralPath $dummyConsolePath -Raw -Encoding unicode) -notmatch
                    'DUMMY_TRIGGER_JOB_PASS') {
                throw 'Self-test failed: event-trigger collector job plumbing.'
            }
        } finally {
            if ($dummyJob.State -eq 'Running') {
                Stop-Job -Job $dummyJob -ErrorAction SilentlyContinue
            }
            Remove-Job -Job $dummyJob -Force -ErrorAction SilentlyContinue
        }

        $slowCollectorPath = Join-Path $tempRoot 'slow_output_collector.ps1'
        @'
param(
  [string]$ApiBase,
  [int]$Samples,
  [int]$DurationSec,
  [int]$IntervalSec,
  [int]$NormalEndpointIntervalSec,
  [int]$MemoryStateIntervalSec,
  [int]$MemoryDetailsIntervalSec,
  [int]$TimeoutSec,
  [string]$OutputRoot,
  [switch]$StopOnNewSpotConnectTimeout,
  [string]$CaptureStopSignalPath
)
Start-Sleep -Milliseconds 300
$endedAt = [DateTimeOffset]::Now
[ordered]@{
  schema_version = 'spot-connecttimeout-capture-stop-v1'
  stop_reason = 'deadline-reached-without-trigger'
  trigger_detected = $false
  collection_ended_at = $endedAt.ToString('o')
} | ConvertTo-Json -Depth 4 |
  Set-Content -LiteralPath $CaptureStopSignalPath -Encoding utf8
1..40 | ForEach-Object {
  Write-Output ('DEFERRED_COLLECTOR_OUTPUT_{0}' -f $_)
  Start-Sleep -Milliseconds 100
}
'@ | Set-Content -LiteralPath $slowCollectorPath -Encoding utf8
        $slowOutputRoot = Join-Path $tempRoot 'slow_output'
        New-Item -ItemType Directory -Path $slowOutputRoot | Out-Null
        $slowSignalPath = Join-Path $slowOutputRoot 'capture_stop_signal.json'
        $slowJob = Start-OperationalCollectorJob `
            -ScriptPath $slowCollectorPath `
            -CollectorApiBase 'http://127.0.0.1:1' `
            -CollectorSamples 1 `
            -CollectorDurationSec 1 `
            -CollectorIntervalSec 1 `
            -CollectorNormalIntervalSec 5 `
            -CollectorMemoryStateIntervalSec 30 `
            -CollectorMemoryDetailsIntervalSec 60 `
            -CollectorOutputRoot $slowOutputRoot `
            -CollectorSignalPath $slowSignalPath
        try {
            $signalWatch = [Diagnostics.Stopwatch]::StartNew()
            $pollFixture = @{ count = 0 }
            $pollCallback = {
                param([DateTimeOffset]$Now)
                $pollFixture.count = [int]$pollFixture.count + 1
            }
            $slowSignalResult = Wait-CollectorStopSignal `
                -Job $slowJob `
                -SignalPath $slowSignalPath `
                -PlannedEndAt ([DateTimeOffset]::Now.AddSeconds(5)) `
                -SignalGraceSeconds 1 `
                -PollIntervalMilliseconds 50 `
                -OnPoll $pollCallback
            $signalWatch.Stop()
            if ($slowSignalResult.status -ne 'signal-observed' -or
                $signalWatch.Elapsed.TotalSeconds -ge 3 -or
                $slowJob.State -ne 'Running' -or
                [int]$pollFixture.count -lt 1 -or
                [double]$slowSignalResult.observation_latency_ms -gt 2000) {
                throw (
                    'Self-test failed: parent boundary signal polling waited for ' +
                    'collector output or job completion.'
                )
            }
        } finally {
            if ($slowJob.State -eq 'Running') {
                Stop-Job -Job $slowJob -ErrorAction SilentlyContinue
            }
            Remove-Job -Job $slowJob -Force -ErrorAction SilentlyContinue
        }

        $lateSignalCollectorPath = Join-Path $tempRoot 'late_signal_collector.ps1'
        @'
param(
  [string]$ApiBase,
  [int]$Samples,
  [int]$DurationSec,
  [int]$IntervalSec,
  [int]$NormalEndpointIntervalSec,
  [int]$MemoryStateIntervalSec,
  [int]$MemoryDetailsIntervalSec,
  [int]$TimeoutSec,
  [string]$OutputRoot,
  [switch]$StopOnNewSpotConnectTimeout,
  [string]$CaptureStopSignalPath
)
Start-Sleep -Milliseconds 1800
[ordered]@{
  schema_version = 'spot-connecttimeout-capture-stop-v1'
  stop_reason = 'observation-completion-requested'
  trigger_detected = $false
  collection_ended_at = [DateTimeOffset]::Now.ToString('o')
} | ConvertTo-Json -Depth 4 |
  Set-Content -LiteralPath $CaptureStopSignalPath -Encoding utf8
'@ | Set-Content -LiteralPath $lateSignalCollectorPath -Encoding utf8
        $lateSignalOutputRoot = Join-Path $tempRoot 'late_signal_output'
        New-Item -ItemType Directory -Path $lateSignalOutputRoot | Out-Null
        $lateSignalPath = Join-Path $lateSignalOutputRoot 'capture_stop_signal.json'
        $lateSignalJob = Start-OperationalCollectorJob `
            -ScriptPath $lateSignalCollectorPath `
            -CollectorApiBase 'http://127.0.0.1:1' `
            -CollectorSamples 1 `
            -CollectorDurationSec 1 `
            -CollectorIntervalSec 1 `
            -CollectorNormalIntervalSec 5 `
            -CollectorMemoryStateIntervalSec 30 `
            -CollectorMemoryDetailsIntervalSec 60 `
            -CollectorOutputRoot $lateSignalOutputRoot `
            -CollectorSignalPath $lateSignalPath
        try {
            $boundaryWatch = [Diagnostics.Stopwatch]::StartNew()
            $boundaryResult = Wait-CollectorObservationBoundary `
                -Job $lateSignalJob `
                -SignalPath $lateSignalPath `
                -PlannedEndAt ([DateTimeOffset]::Now.AddMilliseconds(400)) `
                -PollIntervalMilliseconds 50
            $boundaryWatch.Stop()
            if ($boundaryResult.status -ne 'planned-end-reached' -or
                $boundaryWatch.Elapsed.TotalSeconds -ge 1.2 -or
                $lateSignalJob.State -ne 'Running') {
                throw (
                    'Self-test failed: parent did not take authority at the ' +
                    'planned observation end.'
                )
            }
            $parentRequestPath = Join-Path `
                $lateSignalOutputRoot `
                'parent_completion_request.json'
            $parentObservationEndedAt = [DateTimeOffset]::Now
            $parentRequest = Write-ParentCollectorCompletionRequest `
                -Path $parentRequestPath `
                -ObservationEndedAt $parentObservationEndedAt
            $savedParentRequest = Get-Content `
                -LiteralPath $parentRequestPath `
                -Raw `
                -Encoding utf8 |
                ConvertFrom-Json
            if ($parentRequest.request_source -cne
                    'parent-authoritative-observation-boundary' -or
                $savedParentRequest.request_id -cne
                    $parentRequest.request_id -or
                [DateTimeOffset]::Parse(
                    [string]$savedParentRequest.observation_ended_at
                ) -ne $parentObservationEndedAt) {
                throw (
                    'Self-test failed: parent completion request contract.'
                )
            }
        } finally {
            if ($lateSignalJob.State -eq 'Running') {
                Stop-Job -Job $lateSignalJob -ErrorAction SilentlyContinue
            }
            Remove-Job -Job $lateSignalJob -Force -ErrorAction SilentlyContinue
        }

        $staleSignalPath = Join-Path $tempRoot 'stale_capture_stop_signal.json'
        [ordered]@{
            schema_version = 'spot-connecttimeout-capture-stop-v1'
            stop_reason = 'deadline-reached-without-trigger'
            trigger_detected = $false
            collection_ended_at = [DateTimeOffset]::Now.AddSeconds(-10).ToString('o')
        } | ConvertTo-Json -Depth 4 |
            Set-Content -LiteralPath $staleSignalPath -Encoding utf8
        $staleSignalResult = Wait-CollectorStopSignal `
            -SignalPath $staleSignalPath `
            -PlannedEndAt ([DateTimeOffset]::Now.AddSeconds(1))
        if ($staleSignalResult.status -ne 'signal-observed' -or
            [double]$staleSignalResult.observation_latency_ms -lt 5000) {
            throw 'Self-test failed: delayed boundary signal latency was not retained.'
        }

        $percentileFixture = Get-PercentileValue -Values @(
            [double]1,
            [double]2,
            [double]3,
            [double]4
        ) -Percentile 0.95
        if ($percentileFixture -ne 4) {
            throw 'Self-test failed: percentile calculation.'
        }
        $switchFixture = Join-Path $tempRoot 'switch'
        New-Item -ItemType Directory -Path $switchFixture | Out-Null
        'start' | Set-Content -LiteralPath (Join-Path $switchFixture 'switch_start_combined.txt') -Encoding ascii
        'end' | Set-Content -LiteralPath (Join-Path $switchFixture 'switch_end_combined.txt') -Encoding ascii
        $switchState = Get-SwitchEvidenceState -Directory $switchFixture
        if ($switchState.FileCount -ne 2 -or
            -not $switchState.StartComplete -or
            -not $switchState.EndComplete -or
            $switchState.InvalidFileCount -ne 0 -or
            $switchState.EmptyFileCount -ne 0 -or
            $switchState.Unavailable) {
            throw 'Self-test failed: switch evidence state.'
        }

        $emptySwitchFixture = Join-Path $tempRoot 'switch_empty'
        New-Item -ItemType Directory -Path $emptySwitchFixture | Out-Null
        New-Item -ItemType File -Path (Join-Path $emptySwitchFixture 'switch_start_combined.png') |
            Out-Null
        $emptySwitchState = Get-SwitchEvidenceState -Directory $emptySwitchFixture
        if ($emptySwitchState.StartComplete -or $emptySwitchState.EmptyFileCount -ne 1) {
            throw 'Self-test failed: empty switch evidence must not pass.'
        }

        $invalidSwitchFixture = Join-Path $tempRoot 'switch_invalid'
        New-Item -ItemType Directory -Path $invalidSwitchFixture | Out-Null
        'invalid' |
            Set-Content -LiteralPath (Join-Path $invalidSwitchFixture 'switch-start-device-name.png') `
                -Encoding ascii
        $invalidSwitchState = Get-SwitchEvidenceState -Directory $invalidSwitchFixture
        if ($invalidSwitchState.StartComplete -or $invalidSwitchState.InvalidFileCount -ne 1) {
            throw 'Self-test failed: invalid switch evidence filename must not pass.'
        }

        $completeResult = Resolve-CollectionResult `
            -HasRunFailure $false `
            -RequiredEvidenceFailureCreated $false `
            -SwitchEvidenceUnavailable $false
        $partialResult = Resolve-CollectionResult `
            -HasRunFailure $false `
            -RequiredEvidenceFailureCreated $false `
            -SwitchEvidenceUnavailable $true
        $missingResult = Resolve-CollectionResult `
            -HasRunFailure $true `
            -RequiredEvidenceFailureCreated $true `
            -SwitchEvidenceUnavailable $false
        $runtimeResult = Resolve-CollectionResult `
            -HasRunFailure $true `
            -RequiredEvidenceFailureCreated $false `
            -SwitchEvidenceUnavailable $true
        if ($completeResult.Status -ne 'COLLECTED' -or
            $completeResult.CollectionReasonCode -ne 'complete' -or
            $completeResult.ExitCode -ne 0) {
            throw 'Self-test failed: complete collection result.'
        }
        if ($partialResult.Status -ne 'PARTIAL' -or
            $partialResult.CollectionReasonCode -ne 'switch-evidence-unavailable' -or
            $null -ne $partialResult.FailureReasonCode -or
            $partialResult.ExitCode -ne 2) {
            throw 'Self-test failed: partial collection result.'
        }
        if ($missingResult.Status -ne 'FAILED' -or
            $missingResult.FailureReasonCode -ne 'required-evidence-missing' -or
            $missingResult.ExitCode -ne 1) {
            throw 'Self-test failed: required evidence failure result.'
        }
        if ($runtimeResult.Status -ne 'FAILED' -or
            $runtimeResult.FailureReasonCode -ne 'runtime-error' -or
            $runtimeResult.ExitCode -ne 1) {
            throw 'Self-test failed: runtime failure must override partial mode.'
        }

        Write-Output (
            (
                'SELF_TEST_PASS minutes={0} maximum_samples={1} ' +
                'duration_seconds={2} partial_exit_code={3} trigger_job=true ' +
                'boundary_signal_nonblocking=true'
            ) -f `
                $requestedPlan.Minutes,
                $requestedPlan.MaximumSamples,
                $requestedPlan.DurationSeconds,
                $partialResult.ExitCode
        )
    } finally {
        $resolvedTempRoot = [IO.Path]::GetFullPath($tempRoot)
        if (-not $resolvedTempRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Unsafe self-test cleanup path.'
        }
        Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force
    }
}

if ($SelfTest) {
    if ([string]::IsNullOrWhiteSpace($FramingAnalyzerPath)) {
        $FramingAnalyzerPath = Join-Path $PSScriptRoot 'analyze-spot-http-framing.ps1'
    }
    if (-not (Test-Path -LiteralPath $FramingAnalyzerPath -PathType Leaf)) {
        throw 'Self-test failed: framing analyzer is missing.'
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $FramingAnalyzerPath -SelfTest
    if ($LASTEXITCODE -ne 0) {
        throw 'Self-test failed: framing analyzer.'
    }
    Invoke-SelfTest -RequestedObservationMinutes $ObservationMinutes
    exit 0
}

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $env:APPDATA 'SmartFactoryLogger\config.ini'
}
if ([string]::IsNullOrWhiteSpace($EvidenceBase)) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $EvidenceBase = Join-Path $desktop 'SmartFactoryLogger_Evidence'
}
if ([string]::IsNullOrWhiteSpace($CollectorPath)) {
    $CollectorPath = Join-Path $PSScriptRoot 'collect_operational_observability.ps1'
}
if ([string]::IsNullOrWhiteSpace($FramingAnalyzerPath)) {
    $FramingAnalyzerPath = Join-Path $PSScriptRoot 'analyze-spot-http-framing.ps1'
}

Write-Stage 'Preflight safety checks'
if (-not (Test-IsAdministrator)) {
    throw 'Administrator PowerShell is required. Use the administrator CMD launcher.'
}
if (-not (Test-Path -LiteralPath $CollectorPath -PathType Leaf)) {
    throw 'collect_operational_observability.ps1 is missing from this folder.'
}
if (-not (Test-Path -LiteralPath $FramingAnalyzerPath -PathType Leaf)) {
    throw 'analyze-spot-http-framing.ps1 is missing from this folder.'
}
if ($ApiBase -notmatch '^https?://(127\.0\.0\.1|localhost)(:\d+)?/?$') {
    throw 'ApiBase must point to localhost on the real SmartFactoryLogger server.'
}

$backendUri = [Uri]$ApiBase
$backendPort = $backendUri.Port
if ([string]::IsNullOrWhiteSpace($SpotIp)) {
    $SpotIp = Get-ConfiguredSpotIp -Path $ConfigPath
}
Assert-ValidSpotIp -Value $SpotIp

$driveRoot = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($EvidenceBase))
$driveName = $driveRoot.TrimEnd('\').TrimEnd(':')
$drive = Get-PSDrive -Name $driveName -PSProvider FileSystem -ErrorAction Stop
if ($drive.Free -lt 5GB) {
    throw 'The evidence drive has less than 5 GB free.'
}

try {
    $healthUri = '{0}/health' -f $ApiBase.TrimEnd('/')
    $health = Invoke-WebRequest -Uri $healthUri -Method Get -TimeoutSec 5 -UseBasicParsing
    if ([int]$health.StatusCode -ne 200) {
        throw 'The health endpoint did not return HTTP 200.'
    }
} catch {
    throw 'The SmartFactoryLogger backend is not healthy. This script will not start the application.'
}

$initialFilters = Invoke-PktmonCommand -Arguments @('filter', 'list')
$initialFilterState = Get-PktmonFilterListState -Text $initialFilters.Text
if ($initialFilterState -eq 'Present') {
    throw 'Existing pktmon filters were detected. Do not remove them. Stop and report this result.'
}
if ($initialFilterState -ne 'Empty') {
    throw 'The pktmon filter list output was not recognized. Do not remove filters. Stop and report this result.'
}

Write-Host '[OK] Administrator, disk, app health, SPOT config, and pktmon filter checks passed.' -ForegroundColor Green
Write-Host '[SAFE] No app restart, error clear, setting change, or image load test will be performed.' -ForegroundColor Green

if ($PreflightOnly) {
    Write-Host '[DONE] Preflight only. No application or system setting was changed.' -ForegroundColor Green
    exit 0
}

$runId = 'runtime_validation_{0}' -f (Get-Date -Format 'yyyyMMdd_HHmmss')
$evidenceRoot = Join-Path $EvidenceBase $runId
$rawRoot = Join-Path $evidenceRoot 'raw_private'
$sanitizedRoot = Join-Path $evidenceRoot 'sanitized_share'
$networkRoot = Join-Path $rawRoot 'network'
$appRoot = Join-Path $rawRoot 'app'
$processRoot = Join-Path $rawRoot 'process'
$logsRoot = Join-Path $rawRoot 'logs'
$switchRoot = Join-Path $rawRoot 'switch_logs_drop_here'
foreach ($directory in @($rawRoot, $sanitizedRoot, $networkRoot, $appRoot, $processRoot, $logsRoot, $switchRoot)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$timelinePath = Join-Path $rawRoot 'timeline.json'
$rawManifestPath = Join-Path $rawRoot 'run_manifest.json'
$filterAdded = $false
$ownedFilterStateText = $null
$filterCleanupStatus = 'not_added'
$pktmonStarted = $false
$pingJob = $null
$collectorJob = $null
$runFailure = $null
$startedAt = Get-Date
$endedAt = $null
$observationStartedAt = $null
$observationEndedAt = $null
$collectorReturnedAt = $null
$captureStartedAt = $null
$captureEndedAt = $null
$captureStopSignalObservedAt = $null
$captureStopSignalEndedAt = $null
$captureStopSignalObservationLatencyMs = $null
$captureStopSignalBoundaryStatus = 'not-started'
$captureStopSignalIntegrityStatus = 'not-started'
$captureStopSignalAfterBoundaryLatencyMs = $null
$captureStopSignal = $null
$observationBoundaryTargetAt = $null
$parentCompletionRequest = $null
$parentCompletionRequestPath = $null
$parentCompletionRequestFailure = $null
$deferredObservationFailure = $null
$appObservationStartedAt = $null
$appObservationDeadlineAt = $null
$appObservationEndedAt = $null
$appObservationGeneratedAt = $null
$appObservationElapsedSeconds = $null
$appDeadlineOverrunMilliseconds = $null
$appObservationStopReason = $null
$appEventTrigger = $null
$etlPath = Join-Path $networkRoot 'spot_tcp.etl'
$pcapPath = Join-Path $networkRoot 'spot_tcp.pcapng'
$framingEventsPath = Join-Path $sanitizedRoot 'spot_http_framing_events.jsonl'
$framingSummaryPath = Join-Path $sanitizedRoot 'spot_http_framing_summary.json'
$observationStartPath = Join-Path $appRoot 'canary-observation-start.json'
$observationEndPath = Join-Path $appRoot 'canary-observation-end.json'
$safeObservationStartPath = Join-Path $sanitizedRoot 'canary-observation-start.json'
$safeObservationEndPath = Join-Path $sanitizedRoot 'canary-observation-end.json'
$postprocessStatePath = Join-Path $appRoot 'canary-postprocess-state.json'
$safePostprocessStatePath = Join-Path $sanitizedRoot 'canary-postprocess-state.json'
$clockCalibrationPath = Join-Path $appRoot 'canary-clock-calibration.jsonl'
$safeClockCalibrationPath = Join-Path $sanitizedRoot 'canary-clock-calibration.jsonl'
$observationStartSnapshot = $null
$observationEndSnapshot = $null
$observationEndSnapshotCapturedAt = $null
$lastClockAnchorAt = $null
$postprocessStartedAt = $null
$postprocessState = $null
$postprocessIntegrityFailures = @()
$framingAnalyzerRawConsolePath = Join-Path $rawRoot 'spot_http_framing_analyzer_console_raw.txt'
$framingAnalyzerSafeConsolePath = Join-Path $sanitizedRoot 'spot_http_framing_analyzer_console.txt'
$framingAnalysisStatus = 'not_started'
$framingSummary = $null
$packetPayloadArtifactsRetained = $false
$circularCaptureMaxFileSizeMB = 1024
$circularCaptureMaxFileSizeBytes = [int64]$circularCaptureMaxFileSizeMB * 1MB
$captureFileSizeBytes = [int64]0
$directionProbeSeconds = 10
$directionProbeEtlPath = Join-Path $networkRoot 'pktmon_direction_probe.etl'
$directionProbeTextPath = Join-Path $networkRoot 'pktmon_direction_probe.txt'
$directionProbeStatus = 'not_started'
$directionProbeOutboundCount = 0
$directionProbeInboundCount = 0
$pingPath = Join-Path $networkRoot 'ping_spot.jsonl'
$captureStopSignalPath = Join-Path $appRoot 'capture_stop_signal.json'
$collectorConsolePath = Join-Path $appRoot 'collector_console.txt'
$nicBeforePath = Join-Path $networkRoot 'nic_before.csv'
$nicAfterPath = Join-Path $networkRoot 'nic_after.csv'
$windowsTcpBeforePath = Join-Path $networkRoot 'windows_tcp_ipv4_before.json'
$windowsTcpAfterPath = Join-Path $networkRoot 'windows_tcp_ipv4_after.json'
$windowsTcpDeltaPath = Join-Path $sanitizedRoot 'windows_tcp_ipv4_delta.json'
$windowsTcpEvidenceStatus = 'not_started'
$windowsTcpDelta = $null
$switchEvidenceState = $null
$switchEvidenceUnavailableDeclared = $false

$timeline = [ordered]@{
    run_id = $runId
    started_at_kst = $startedAt.ToString('o')
    observation_minutes = $ObservationMinutes
    event_trigger_enabled = [bool]$StopOnNewSpotConnectTimeout
    post_trigger_capture_seconds = $PostTriggerCaptureSeconds
    switch_log_instruction = 'Save server-side and SPOT-side switch port counters and link events for the same interval.'
}
$timeline | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $timelinePath -Encoding utf8
$switchRequestPath = Join-Path $switchRoot 'switch_log_request.txt'
@"
SPOT switch log drop location

Run start: $($startedAt.ToString('yyyy-MM-dd HH:mm:ss K'))
Run end: pending

Use generic filenames only:
- switch_start_server.<ext> and switch_start_spot.<ext>, or switch_start_combined.<ext>
- switch_end_server.<ext> and switch_end_spot.<ext>, or switch_end_combined.<ext>
- optional switch_link_events_server.<ext>, switch_link_events_spot.<ext>, or switch_link_events_combined.<ext>

If no managed-switch administration page or credentials exist, type UNAVAILABLE at the
start prompt. The server-side collection will continue with PARTIAL status, and switch
faults will remain unexcluded.

Do not put an IP address, hostname, account name, or switch name in a filename.
"@ | Set-Content -LiteralPath $switchRequestPath -Encoding utf8

$scriptHash = Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256
$collectorHash = Get-FileHash -LiteralPath $CollectorPath -Algorithm SHA256
$framingAnalyzerHash = Get-FileHash -LiteralPath $FramingAnalyzerPath -Algorithm SHA256
$manifest = [ordered]@{
    run_id = $runId
    started_at_kst = $startedAt.ToString('o')
    status = 'RUNNING'
    observation_minutes = $ObservationMinutes
    event_trigger_enabled = [bool]$StopOnNewSpotConnectTimeout
    post_trigger_capture_seconds = $PostTriggerCaptureSeconds
    backend = 'localhost'
    spot_target = 'configured-target-redacted'
    app_restart_performed = $false
    settings_changed = $false
    error_queue_cleared = $false
    image_load_test_performed = $false
    collection_script_sha256 = $scriptHash.Hash.ToLowerInvariant()
    observability_collector_sha256 = $collectorHash.Hash.ToLowerInvariant()
    framing_analyzer_sha256 = $framingAnalyzerHash.Hash.ToLowerInvariant()
    packet_capture_snapshot_bytes = 512
    packet_capture_circular_limit_bytes = $circularCaptureMaxFileSizeBytes
    packet_payload_artifacts_retained = 'unknown_until_finalization'
    packet_direction_probe_seconds = $directionProbeSeconds
    packet_direction_preflight = $directionProbeStatus
    switch_evidence_status = 'pending'
    switch_evidence_unavailable_declared = $false
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $rawManifestPath -Encoding utf8

Write-Stage 'Save switch start counters'
Write-Host ('Save RX/TX, error, discard, CRC, and link state for the server and SPOT switch ports. Start: {0}' -f $startedAt.ToString('yyyy-MM-dd HH:mm:ss K')) -ForegroundColor Yellow
Write-Host ('Save the start evidence in: {0}' -f $switchRoot) -ForegroundColor Yellow
Write-Host 'Use switch_start_server + switch_start_spot, or one switch_start_combined filename.' -ForegroundColor Yellow
$switchEvidenceState = Wait-SwitchEvidence `
    -Directory $switchRoot `
    -Phase Start `
    -AllowUnavailable
$switchEvidenceUnavailableDeclared = [bool]$switchEvidenceState.Unavailable
$manifest['switch_evidence_status'] = if ($switchEvidenceUnavailableDeclared) {
    'unavailable'
} else {
    'start_verified'
}
$manifest['switch_evidence_unavailable_declared'] = $switchEvidenceUnavailableDeclared
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $rawManifestPath -Encoding utf8

try {
    Write-Stage 'Save process, port, and NIC start state'
    Export-ProcessAndPortState -Directory $processRoot -Suffix 'before' -BackendPort $backendPort
    Export-NicState -Path $nicBeforePath

    Write-Stage 'Start SPOT TCP packet direction preflight'
    Invoke-PktmonCommand -Arguments @('filter', 'add', 'SpotHttpValidation', '-i', $SpotIp, '-t', 'TCP') `
        -LogPath (Join-Path $networkRoot 'pktmon_filter_add.txt') | Out-Null
    $filterAdded = $true
    $filterCleanupStatus = 'pending'
    $ownedFilterState = Invoke-PktmonCommand -Arguments @('filter', 'list') `
        -LogPath (Join-Path $networkRoot 'pktmon_filter_owned_state.txt')
    $ownedFilterStateText = $ownedFilterState.Text
    if ([string]::IsNullOrWhiteSpace($ownedFilterStateText)) {
        throw 'The owned pktmon filter could not be verified after it was added.'
    }
    Invoke-PktmonCommand -Arguments @(
        'start', '--capture', '--comp', 'nics', '--pkt-size', '128',
        '--file-name', $directionProbeEtlPath, '--file-size', '32', '--log-mode', 'circular'
    ) -LogPath (Join-Path $networkRoot 'pktmon_direction_probe_start.txt') | Out-Null
    $pktmonStarted = $true
    $directionProbeStatus = 'capturing'
    Start-Sleep -Seconds $directionProbeSeconds
    Invoke-PktmonCommand -Arguments @('stop') `
        -LogPath (Join-Path $networkRoot 'pktmon_direction_probe_stop.txt') | Out-Null
    $pktmonStarted = $false

    $directionProbeConversion = Invoke-PktmonCommand -Arguments @(
        'etl2txt', $directionProbeEtlPath, '--out', $directionProbeTextPath, '--brief', '--timestamp'
    ) -LogPath (Join-Path $networkRoot 'pktmon_direction_probe_etl2txt.txt') -AllowFailure
    if ($directionProbeConversion.ExitCode -ne 0 -or
        -not (Test-Path -LiteralPath $directionProbeTextPath -PathType Leaf)) {
        $directionProbeStatus = 'conversion_failed'
        $manifest['packet_direction_preflight'] = $directionProbeStatus
        throw 'The pktmon direction preflight could not be converted. Full collection was not started.'
    }

    $directionProbeText = Get-Content -LiteralPath $directionProbeTextPath -Raw -Encoding utf8
    $directionState = Get-PktmonPacketDirectionState -Text $directionProbeText -TargetIp $SpotIp
    Remove-TransientPacketArtifact -Path $directionProbeEtlPath -NetworkRoot $networkRoot
    $directionProbeOutboundCount = [int]$directionState.OutboundCount
    $directionProbeInboundCount = [int]$directionState.InboundCount
    $directionProbeStatus = if ($directionState.Passed) { 'passed' } else { 'failed_one_way_or_empty' }
    $manifest['packet_direction_preflight'] = $directionProbeStatus
    $manifest['packet_direction_probe_outbound_count'] = $directionProbeOutboundCount
    $manifest['packet_direction_probe_inbound_count'] = $directionProbeInboundCount
    if (-not $directionState.Passed) {
        throw (
            'Pktmon did not capture both SPOT TCP directions during the 10-second preflight. ' +
            'Full collection was not started. Do not change the application or network settings.'
        )
    }
    Write-Host (
        '[OK] Bidirectional SPOT TCP packets were captured. outbound={0}, inbound={1}' -f `
            $directionProbeOutboundCount, $directionProbeInboundCount
    ) -ForegroundColor Green

    Export-WindowsTcpState -Path $windowsTcpBeforePath | Out-Null
    $windowsTcpEvidenceStatus = 'before_collected'
    Write-Stage 'Start SPOT TCP packet capture'
    Invoke-PktmonCommand -Arguments @(
        'start', '--capture', '--comp', 'nics', '--pkt-size', '512',
        '--file-name', $etlPath, '--file-size', ([string]$circularCaptureMaxFileSizeMB),
        '--log-mode', 'circular'
    ) -LogPath (Join-Path $networkRoot 'pktmon_start.txt') | Out-Null
    $pktmonStarted = $true
    $captureStartedAt = Get-Date

    Write-Stage 'Start one-second ping logging'
    $pingJob = Start-Job -ArgumentList $SpotIp, $pingPath -ScriptBlock {
        param($Target, $OutputPath)
        $ping = [Net.NetworkInformation.Ping]::new()
        try {
            while ($true) {
                $at = Get-Date
                $watch = [Diagnostics.Stopwatch]::StartNew()
                $reply = $null
                $status = 'ProbeException'
                try {
                    $reply = $ping.Send($Target, 900)
                    $status = [string]$reply.Status
                } catch {
                    $status = 'ProbeException'
                } finally {
                    $watch.Stop()
                }
                $success = $null -ne $reply -and
                    $reply.Status -eq [Net.NetworkInformation.IPStatus]::Success
                [ordered]@{
                    at_kst = $at.ToString('o')
                    success = $success
                    status = $status
                    roundtrip_time_ms = if ($success) { [long]$reply.RoundtripTime } else { $null }
                    probe_wall_time_ms = [math]::Round($watch.Elapsed.TotalMilliseconds, 1)
                } | ConvertTo-Json -Compress | Add-Content -LiteralPath $OutputPath -Encoding utf8
                $remaining = 1000 - [int]$watch.Elapsed.TotalMilliseconds
                if ($remaining -gt 0) {
                    Start-Sleep -Milliseconds $remaining
                }
            }
        } finally {
            $ping.Dispose()
        }
    }

    Write-Stage ('Collect app, TCP, and ping evidence for {0} minutes' -f $ObservationMinutes)
    Write-Host 'Keep the normal screen unchanged. Do not add tabs, repeatedly refresh, or run image load tests.' -ForegroundColor Yellow
    Write-Host 'If an error appears, do not click it. Record the exact time.' -ForegroundColor Yellow
    $observationPlan = Get-ObservationPlan `
        -Minutes $ObservationMinutes `
        -EventTrigger:$StopOnNewSpotConnectTimeout
    $observationStartSnapshot = New-ObservationBoundarySnapshot `
        -Role start `
        -LocalApiBase $ApiBase `
        -LocalConfigPath $ConfigPath `
        -OutputPath $observationStartPath
    Copy-Item `
        -LiteralPath $observationStartPath `
        -Destination $safeObservationStartPath `
        -ErrorAction Stop
    $observationStartedAt = [DateTimeOffset]::Parse(
        [string]$observationStartSnapshot.observed_at_completed
    )
    $observationMonotonicStartTicks = [int64](
        $observationStartSnapshot.monotonic_ticks
    )
    Add-ClockCalibrationAnchor -Path $clockCalibrationPath
    $lastClockAnchorAt = Get-Date
    $plannedEndAt = $observationStartedAt.AddSeconds($observationPlan.DurationSeconds)
    Write-Host (
        '[PLAN] duration={0}s, target interval={1}s, fixed collection end={2}' -f `
            $observationPlan.DurationSeconds,
            $observationPlan.IntervalSeconds,
            $plannedEndAt.ToString('yyyy-MM-dd HH:mm:ss K')
    ) -ForegroundColor Cyan
    if ($StopOnNewSpotConnectTimeout) {
        Write-Host (
            '[TRIGGER] Existing errors will be fixed as the baseline. ' +
            'Only a new spot_image ConnectTimeout will stop capture early.'
        ) -ForegroundColor Cyan
        Write-Host (
            '[TRIGGER] Error queue every {0}s; other app APIs every {1}s; maximum wait={2} minutes.' -f `
                $observationPlan.IntervalSeconds,
                $observationPlan.NormalEndpointIntervalSeconds,
                $ObservationMinutes
        ) -ForegroundColor Cyan
    }
    Write-Host (
        '[PLAN] memory state every {0}s; memory details every {1}s' -f `
            $observationPlan.MemoryStateIntervalSeconds,
            $observationPlan.MemoryDetailsIntervalSeconds
    ) -ForegroundColor Cyan

    if ($StopOnNewSpotConnectTimeout) {
        $collectorJob = Start-OperationalCollectorJob `
            -ScriptPath $CollectorPath `
            -CollectorApiBase $ApiBase `
            -CollectorSamples $observationPlan.MaximumSamples `
            -CollectorDurationSec $observationPlan.DurationSeconds `
            -CollectorIntervalSec $observationPlan.IntervalSeconds `
            -CollectorNormalIntervalSec $observationPlan.NormalEndpointIntervalSeconds `
            -CollectorMemoryStateIntervalSec $observationPlan.MemoryStateIntervalSeconds `
            -CollectorMemoryDetailsIntervalSec $observationPlan.MemoryDetailsIntervalSeconds `
            -CollectorOutputRoot $appRoot `
            -CollectorSignalPath $captureStopSignalPath

        $progressState = @{
            last_clock_anchor_at = $lastClockAnchorAt
        }
        $onCollectorPoll = {
            param([DateTimeOffset]$Now)

            $nowLocal = $Now.LocalDateTime
            if (($nowLocal - $progressState.last_clock_anchor_at).TotalSeconds -ge
                $ProgressIntervalSeconds) {
                Add-ClockCalibrationAnchor -Path $clockCalibrationPath
                $progressState.last_clock_anchor_at = $nowLocal
                $elapsedSeconds = [Math]::Max(
                    0,
                    ([Diagnostics.Stopwatch]::GetTimestamp() -
                        $observationMonotonicStartTicks) /
                        [Diagnostics.Stopwatch]::Frequency
                )
                $remainingSeconds = [Math]::Max(
                    0,
                    $observationPlan.DurationSeconds - $elapsedSeconds
                )
                $percent = [Math]::Min(
                    100,
                    [Math]::Round(
                        100.0 * $elapsedSeconds / $observationPlan.DurationSeconds,
                        1
                    )
                )
                $backendAlive = $null -ne (
                    Get-Process `
                        -Id ([int]$observationStartSnapshot.backend_pid) `
                        -ErrorAction SilentlyContinue
                )
                Write-Host (
                    '[CANARY PROGRESS] stage=observing elapsed={0} remaining={1} percent={2}% expected_end={3} backend_pid={4} backend_alive={5}; local clock/process only; no added SPOT requests' -f `
                        ([TimeSpan]::FromSeconds($elapsedSeconds).ToString('hh\:mm\:ss')),
                        ([TimeSpan]::FromSeconds($remainingSeconds).ToString('hh\:mm\:ss')),
                        $percent,
                        $plannedEndAt.ToString('yyyy-MM-dd HH:mm:ss K'),
                        $observationStartSnapshot.backend_pid,
                        $backendAlive
                ) -ForegroundColor Cyan
            }
        }

        $monotonicDeadlineTicks = [int64](
            $observationMonotonicStartTicks +
            [Math]::Round(
                $observationPlan.DurationSeconds *
                [Diagnostics.Stopwatch]::Frequency
            )
        )
        $boundaryResult = Wait-CollectorObservationBoundary `
            -Job $collectorJob `
            -SignalPath $captureStopSignalPath `
            -PlannedEndAt $plannedEndAt `
            -MonotonicDeadlineTicks $monotonicDeadlineTicks `
            -PollIntervalMilliseconds 200 `
            -OnPoll $onCollectorPoll
        $lastClockAnchorAt = $progressState.last_clock_anchor_at
        $captureStopSignalBoundaryStatus = [string]$boundaryResult.status
        if ($captureStopSignalBoundaryStatus -eq 'signal-observed') {
            $captureStopSignalIntegrityStatus = 'signal-observed'
            $captureStopSignal = $boundaryResult.signal
            $captureStopSignalObservedAt = $boundaryResult.observed_at
            $captureStopSignalEndedAt = $boundaryResult.signal_ended_at
            $captureStopSignalObservationLatencyMs =
                $boundaryResult.observation_latency_ms
            $observationBoundaryTargetAt = $captureStopSignalEndedAt
        } elseif ($captureStopSignalBoundaryStatus -eq 'planned-end-reached') {
            $observationBoundaryTargetAt = $plannedEndAt
            try {
                $parentCompletionRequestPath =
                    Get-CollectorCompletionRequestPath `
                        -CollectorOutputRoot $appRoot
                $parentCompletionRequest =
                    Write-ParentCollectorCompletionRequest `
                        -Path $parentCompletionRequestPath `
                        -ObservationEndedAt $plannedEndAt
            } catch {
                $parentCompletionRequestFailure = $_
            }
        } else {
            $captureStopSignalIntegrityStatus =
                $captureStopSignalBoundaryStatus
            $observationBoundaryTargetAt = [DateTimeOffset]::Now
            $deferredObservationFailure =
                [System.InvalidOperationException]::new(
                    [string]$boundaryResult.error_message
                )
        }

        $observationEndSnapshot = New-ObservationBoundarySnapshot `
            -Role end `
            -LocalApiBase $ApiBase `
            -LocalConfigPath $ConfigPath `
            -OutputPath $observationEndPath
        $observationEndSnapshotCapturedAt = Get-Date
        Copy-Item `
            -LiteralPath $observationEndPath `
            -Destination $safeObservationEndPath `
            -ErrorAction Stop
        Add-ClockCalibrationAnchor -Path $clockCalibrationPath
        Copy-Item `
            -LiteralPath $clockCalibrationPath `
            -Destination $safeClockCalibrationPath `
            -ErrorAction Stop
        $observationEndedAt = [DateTimeOffset]::Parse(
            [string]$observationEndSnapshot.observed_at_completed
        )
        if ($null -ne $captureStopSignal -and
            [bool]$captureStopSignal.trigger_detected -and
            $PostTriggerCaptureSeconds -gt 0) {
            Write-Host (
                '[TRIGGER] New ConnectTimeout detected. Retaining {0}s of follow-up packets before stop.' -f `
                    $PostTriggerCaptureSeconds
            ) -ForegroundColor Yellow
            Start-Sleep -Seconds $PostTriggerCaptureSeconds
        } else {
            Write-Host (
                '[TRIGGER] Maximum wait ended without a new ConnectTimeout. Stopping capture.'
            ) -ForegroundColor Yellow
        }

        if ($null -ne $pingJob) {
            Stop-Job -Job $pingJob -ErrorAction SilentlyContinue
            Receive-Job -Job $pingJob -ErrorAction SilentlyContinue | Out-Null
            Remove-Job -Job $pingJob -Force -ErrorAction SilentlyContinue
            $pingJob = $null
        }
        if ($pktmonStarted) {
            Invoke-PktmonCommand -Arguments @('stop') `
                -LogPath (Join-Path $networkRoot 'pktmon_stop.txt') -AllowFailure |
                Out-Null
            $pktmonStarted = $false
            $captureEndedAt = Get-Date
        }

        if ($captureStopSignalBoundaryStatus -eq 'planned-end-reached') {
            $signalIntegrityResult = Wait-CollectorStopSignal `
                -Job $collectorJob `
                -SignalPath $captureStopSignalPath `
                -PlannedEndAt $plannedEndAt `
                -SignalGraceSeconds 5 `
                -PollIntervalMilliseconds 100
            $captureStopSignalIntegrityStatus =
                [string]$signalIntegrityResult.status
            $captureStopSignal = $signalIntegrityResult.signal
            $captureStopSignalObservedAt = $signalIntegrityResult.observed_at
            $captureStopSignalEndedAt = $signalIntegrityResult.signal_ended_at
            $captureStopSignalObservationLatencyMs =
                $signalIntegrityResult.observation_latency_ms
            if ($null -ne $captureStopSignalObservedAt) {
                $signalAfterBoundaryDelta =
                    $captureStopSignalObservedAt - $plannedEndAt
                $captureStopSignalAfterBoundaryLatencyMs = [Math]::Max(
                    0,
                    [Math]::Round(
                        $signalAfterBoundaryDelta.TotalMilliseconds,
                        3
                    )
                )
            }
            if ($captureStopSignalIntegrityStatus -eq 'signal-observed' -and
                $null -ne $parentCompletionRequest) {
                $signalRequestId = [string](
                    Get-OptionalPropertyValue `
                        -Object $captureStopSignal `
                        -Name 'completion_request_id'
                )
                if ($signalRequestId -cne
                    [string]$parentCompletionRequest.request_id) {
                    $captureStopSignalIntegrityStatus =
                        'signal-completion-request-mismatch'
                    $signalIntegrityResult.error_message = (
                        'The capture stop signal did not acknowledge the ' +
                        'parent completion request.'
                    )
                }
            }
            if ($null -ne $parentCompletionRequestFailure) {
                $deferredObservationFailure =
                    $parentCompletionRequestFailure.Exception
            } elseif ($captureStopSignalIntegrityStatus -ne 'signal-observed') {
                $integrityFailureMessage = if (
                    [string]::IsNullOrWhiteSpace(
                        [string]$signalIntegrityResult.error_message
                    )
                ) {
                    'The capture stop signal integrity check failed: {0}' -f
                        $captureStopSignalIntegrityStatus
                } else {
                    [string]$signalIntegrityResult.error_message
                }
                $deferredObservationFailure =
                    [System.InvalidOperationException]::new(
                        $integrityFailureMessage
                    )
            }
        } elseif ($captureStopSignalBoundaryStatus -eq 'signal-observed') {
            $captureStopSignalAfterBoundaryLatencyMs = 0.0
        }

        if ($null -ne $deferredObservationFailure) {
            Write-Warning (
                '[EVIDENCE HOLD] {0}' -f
                    $deferredObservationFailure.Message
            )
        }
    } else {
        & $CollectorPath `
            -ApiBase $ApiBase `
            -Samples $observationPlan.MaximumSamples `
            -DurationSec $observationPlan.DurationSeconds `
            -IntervalSec $observationPlan.IntervalSeconds `
            -NormalEndpointIntervalSec $observationPlan.NormalEndpointIntervalSeconds `
            -MemoryStateIntervalSec $observationPlan.MemoryStateIntervalSeconds `
            -MemoryDetailsIntervalSec $observationPlan.MemoryDetailsIntervalSeconds `
            -TimeoutSec 3 `
            -OutputRoot $appRoot 2>&1 |
            Tee-Object -FilePath $collectorConsolePath
        $collectorReturnedAt = Get-Date
        $observationEndSnapshot = New-ObservationBoundarySnapshot `
            -Role end `
            -LocalApiBase $ApiBase `
            -LocalConfigPath $ConfigPath `
            -OutputPath $observationEndPath
        $observationEndSnapshotCapturedAt = Get-Date
        Copy-Item $observationEndPath $safeObservationEndPath -ErrorAction Stop
        Add-ClockCalibrationAnchor -Path $clockCalibrationPath
        Copy-Item $clockCalibrationPath $safeClockCalibrationPath -ErrorAction Stop
        $observationEndedAt = [DateTimeOffset]::Parse(
            [string]$observationEndSnapshot.observed_at_completed
        )
    }
    Write-Host '[PROGRESS] Timed app, TCP, and ping collection is complete. Stopping capture safely.' -ForegroundColor Green
} catch {
    $runFailure = $_
} finally {
    $endedAt = Get-Date
    $postprocessStartedAt = $endedAt

    if ($null -ne $runFailure -and $null -ne $collectorJob) {
        if ($collectorJob.State -eq 'Running') {
            Stop-Job -Job $collectorJob -ErrorAction SilentlyContinue
        }
        Receive-CollectorJobOutput -Job $collectorJob -ConsolePath $collectorConsolePath
        Remove-Job -Job $collectorJob -Force -ErrorAction SilentlyContinue
        $collectorJob = $null
    }

    if ($null -ne $pingJob) {
        Stop-Job -Job $pingJob -ErrorAction SilentlyContinue
        Receive-Job -Job $pingJob -ErrorAction SilentlyContinue | Out-Null
        Remove-Job -Job $pingJob -Force -ErrorAction SilentlyContinue
    }

    if ($pktmonStarted) {
        Invoke-PktmonCommand -Arguments @('stop') `
            -LogPath (Join-Path $networkRoot 'pktmon_stop.txt') -AllowFailure | Out-Null
        $pktmonStarted = $false
        $captureEndedAt = Get-Date
    }

    if ($null -ne $captureStartedAt) {
        try {
            Export-WindowsTcpState -Path $windowsTcpAfterPath | Out-Null
            $windowsTcpEvidenceStatus = 'before_after_collected'
        } catch {
            $windowsTcpEvidenceStatus = 'after_collection_failed'
            if ($null -eq $runFailure) {
                $runFailure = $_
            }
            $_.Exception.GetType().Name |
                Set-Content `
                    -LiteralPath (Join-Path $rawRoot 'windows_tcp_after_error_type.txt') `
                    -Encoding ascii
        }
    }

    if ($filterAdded) {
        $currentFilterState = Invoke-PktmonCommand -Arguments @('filter', 'list') `
            -LogPath (Join-Path $networkRoot 'pktmon_filter_before_cleanup.txt') -AllowFailure
        $filterStateUnchanged = $currentFilterState.ExitCode -eq 0 -and
            $currentFilterState.Text -ceq $ownedFilterStateText
        if ($filterStateUnchanged) {
            $removeResult = Invoke-PktmonCommand -Arguments @('filter', 'remove') `
                -LogPath (Join-Path $networkRoot 'pktmon_filter_remove.txt') -AllowFailure
            if ($removeResult.ExitCode -eq 0) {
                $filterCleanupStatus = 'removed_owned_state'
                $filterAdded = $false
            } else {
                $filterCleanupStatus = 'remove_failed'
                if ($null -eq $runFailure) {
                    $runFailure = [System.InvalidOperationException]::new('The owned pktmon filter could not be removed.')
                }
            }
        } else {
            $filterCleanupStatus = 'skipped_filter_state_changed'
            'FILTER_CLEANUP_SKIPPED_BECAUSE_FILTER_STATE_CHANGED' |
                Set-Content -LiteralPath (Join-Path $networkRoot 'pktmon_filter_cleanup_skipped.txt') -Encoding ascii
            Write-Warning 'Pktmon filter cleanup was skipped because the active filter state changed during collection.'
            if ($null -eq $runFailure) {
                $runFailure = [System.InvalidOperationException]::new(
                    'Pktmon filter state changed during collection. No filters were removed.'
                )
            }
        }
    }

    try {
        Export-NicState -Path $nicAfterPath
    } catch {
        if ($null -eq $runFailure) {
            $runFailure = $_
        }
        $_.Exception.GetType().Name |
            Set-Content -LiteralPath (Join-Path $rawRoot 'nic_after_error_type.txt') -Encoding ascii
    }
    try {
        Export-ProcessAndPortState -Directory $processRoot -Suffix 'after' -BackendPort $backendPort
    } catch {
        if ($null -eq $runFailure) {
            $runFailure = $_
        }
        $_.Exception.GetType().Name |
            Set-Content -LiteralPath (Join-Path $rawRoot 'process_after_error_type.txt') -Encoding ascii
    }
    $endedAt = Get-Date
}

if ($switchEvidenceUnavailableDeclared) {
    Write-Stage 'Switch end evidence unavailable'
    Write-Warning (
        'The run remains PARTIAL because managed-switch evidence was declared unavailable before capture.'
    )
} else {
    Write-Stage 'Save switch end counters'
    $captureEndForDisplay = if ($null -eq $captureEndedAt) { $endedAt } else { $captureEndedAt }
    Write-Host ('Save the switch end counters and link events now. Capture end: {0}' -f $captureEndForDisplay.ToString('yyyy-MM-dd HH:mm:ss K')) -ForegroundColor Yellow
    Write-Host ('Save the end evidence in: {0}' -f $switchRoot) -ForegroundColor Yellow
    Write-Host 'Use switch_end_server + switch_end_spot, or one switch_end_combined filename.' -ForegroundColor Yellow
    $switchEvidenceState = Wait-SwitchEvidence -Directory $switchRoot -Phase End -AllowSkip
}

if ($null -ne $collectorJob) {
    Write-Stage 'Finish app evidence after packet capture stop'
    Write-Host (
        '[PROGRESS] Packet, ping, NIC, and process end state are already fixed. ' +
        'Waiting only for app evidence packaging.'
    ) -ForegroundColor Cyan
    $collectorWaitDeadline = (Get-Date).AddMinutes(30)
    $lastCollectorWaitMessageAt = [DateTime]::MinValue
    while ($collectorJob.State -eq 'Running') {
        Receive-CollectorJobOutput -Job $collectorJob -ConsolePath $collectorConsolePath
        $now = Get-Date
        if (($now - $lastCollectorWaitMessageAt).TotalSeconds -ge 15) {
            Write-Host (
                '[PROGRESS] App evidence packaging is still running; packet capture remains stopped.'
            ) -ForegroundColor Cyan
            $lastCollectorWaitMessageAt = $now
        }
        if ($now -ge $collectorWaitDeadline) {
            Stop-Job -Job $collectorJob -ErrorAction SilentlyContinue
            if ($null -eq $runFailure) {
                $runFailure = [System.TimeoutException]::new(
                    'App evidence packaging did not finish within 30 minutes after capture stop.'
                )
            }
            break
        }
        Start-Sleep -Seconds 1
    }
    Receive-CollectorJobOutput -Job $collectorJob -ConsolePath $collectorConsolePath
    $collectorReturnedAt = Get-Date
    if ($collectorJob.State -ne 'Completed' -and $null -eq $runFailure) {
        $collectorReason = if ($null -eq $collectorJob.JobStateInfo.Reason) {
            $collectorJob.State
        } else {
            $collectorJob.JobStateInfo.Reason.GetType().Name
        }
        $runFailure = [System.InvalidOperationException]::new(
            ('The event-trigger app collector did not complete. State: {0}.' -f $collectorReason)
        )
    }
    Remove-Job -Job $collectorJob -Force -ErrorAction SilentlyContinue
    $collectorJob = $null
}

if ($null -eq $runFailure -and $null -ne $deferredObservationFailure) {
    $runFailure = $deferredObservationFailure
}

@"
SPOT switch log drop location

Run start: $($startedAt.ToString('yyyy-MM-dd HH:mm:ss K'))
Capture end: $($endedAt.ToString('yyyy-MM-dd HH:mm:ss K'))

Use generic filenames only:
- switch_start_server.<ext> and switch_start_spot.<ext>, or switch_start_combined.<ext>
- switch_end_server.<ext> and switch_end_spot.<ext>, or switch_end_combined.<ext>
- optional switch_link_events_server.<ext>, switch_link_events_spot.<ext>, or switch_link_events_combined.<ext>

Managed-switch evidence unavailable declared: $switchEvidenceUnavailableDeclared

Do not put an IP address, hostname, account name, or switch name in a filename.
"@ | Set-Content -LiteralPath $switchRequestPath -Encoding utf8

Write-Stage 'Convert packets and collect events, logs, and hashes'
Write-FinalizationProgress `
    -Step 1 `
    -Message 'create body-free HTTP framing evidence, then remove packet payload artifacts' `
    -StartedAt $postprocessStartedAt
try {
    if (-not (Test-Path -LiteralPath $etlPath -PathType Leaf)) {
        throw 'The transient pktmon ETL file was not created.'
    }
    if ($null -eq $observationStartSnapshot -or
        $null -eq $observationEndSnapshot) {
        throw 'The immutable observation boundary pair is incomplete.'
    }
    $captureFileSizeBytes = [int64](
        Get-Item -LiteralPath $etlPath -ErrorAction Stop
    ).Length
    $pcapConversion = Invoke-PktmonCommand -Arguments @('etl2pcap', $etlPath, '--out', $pcapPath) `
        -LogPath (Join-Path $networkRoot 'pktmon_etl2pcap.txt') -AllowFailure
    if ($pcapConversion.ExitCode -ne 0 -or
        -not (Test-Path -LiteralPath $pcapPath -PathType Leaf)) {
        throw 'The transient pktmon ETL file could not be converted to pcapng.'
    }
    $framingAnalysisStatus = 'running'
    & powershell.exe `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $FramingAnalyzerPath `
        -InputPath $pcapPath `
        -EventsOutputPath $framingEventsPath `
        -SummaryOutputPath $framingSummaryPath `
        -CaptureStartedAt $captureStartedAt.ToString('o') `
        -CaptureEndedAt $captureEndedAt.ToString('o') `
        -AnalysisWindowStartedAt $observationStartSnapshot.observed_at_completed `
        -AnalysisWindowEndedAt $observationEndSnapshot.observed_at_completed `
        -ClockCalibrationPath $clockCalibrationPath `
        -CaptureFileSizeBytes $captureFileSizeBytes `
        -CircularCaptureMaxFileSizeMB $circularCaptureMaxFileSizeMB `
        -ServerPort 80 2>&1 |
        Tee-Object -FilePath $framingAnalyzerRawConsolePath
    if ($LASTEXITCODE -ne 0 -or
        -not (Test-Path -LiteralPath $framingEventsPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $framingSummaryPath -PathType Leaf)) {
        throw 'The body-free HTTP framing analysis did not complete.'
    }
    Export-SafeFramingAnalyzerConsole `
        -RawPath $framingAnalyzerRawConsolePath `
        -SafePath $framingAnalyzerSafeConsolePath | Out-Null
    $framingSummary = Get-Content `
        -LiteralPath $framingSummaryPath `
        -Raw `
        -Encoding utf8 |
        ConvertFrom-Json
    if ($framingSummary.schema_version -ne 'spot-http-framing-evidence-v10' -or
        $null -eq $framingSummary.capture_coverage) {
        throw 'The framing analyzer did not emit the required capture coverage contract.'
    }
    $framingAnalysisStatus = 'completed'
} catch {
    $framingAnalysisStatus = 'failed'
    if ($null -eq $runFailure) {
        $runFailure = $_
    }
    $_.Exception.GetType().Name |
        Set-Content -LiteralPath (Join-Path $rawRoot 'framing_analysis_error_type.txt') -Encoding ascii
} finally {
    try {
        foreach ($artifact in @($etlPath, $pcapPath, $directionProbeEtlPath)) {
            Remove-TransientPacketArtifact -Path $artifact -NetworkRoot $networkRoot
        }
        $packetPayloadArtifactsRetained = @(
            $etlPath,
            $pcapPath,
            $directionProbeEtlPath
        ) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
        $packetPayloadArtifactsRetained = $null -ne $packetPayloadArtifactsRetained
        if ($packetPayloadArtifactsRetained) {
            throw 'A transient packet payload artifact remains after finalization.'
        }
    } catch {
        $packetPayloadArtifactsRetained = $true
        if ($null -eq $runFailure) {
            $runFailure = $_
        }
        $_.Exception.GetType().Name |
            Set-Content -LiteralPath (Join-Path $rawRoot 'packet_cleanup_error_type.txt') -Encoding ascii
    }
}

Write-FinalizationProgress `
    -Step 2 `
    -Message 'calculate NIC deltas and collect Windows/application logs' `
    -StartedAt $postprocessStartedAt
$nicDeltaPath = Join-Path $sanitizedRoot 'nic_delta.csv'
try {
    if (-not (Test-Path -LiteralPath $nicBeforePath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $nicAfterPath -PathType Leaf)) {
        throw 'NIC before/after evidence is incomplete.'
    }
    New-NicDelta -BeforePath $nicBeforePath -AfterPath $nicAfterPath -OutputPath $nicDeltaPath
} catch {
    if ($null -eq $runFailure) {
        $runFailure = $_
    }
    'NIC_DELTA_UNAVAILABLE' | Set-Content -LiteralPath $nicDeltaPath -Encoding ascii
}

try {
    if (-not (Test-Path -LiteralPath $windowsTcpBeforePath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $windowsTcpAfterPath -PathType Leaf)) {
        throw 'Windows TCP before/after evidence is incomplete.'
    }
    $windowsTcpDelta = New-WindowsTcpDelta `
        -BeforePath $windowsTcpBeforePath `
        -AfterPath $windowsTcpAfterPath `
        -OutputPath $windowsTcpDeltaPath
    $windowsTcpEvidenceStatus = 'completed'
} catch {
    $windowsTcpEvidenceStatus = 'failed'
    if ($null -eq $runFailure) {
        $runFailure = $_
    }
    [pscustomobject][ordered]@{
        schema_version = 'windows-tcp-ipv4-delta-v1'
        status = 'unavailable'
        scope = 'windows-ipv4-global'
        error_type = $_.Exception.GetType().Name
    } | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $windowsTcpDeltaPath -Encoding utf8
}

$eventStart = $startedAt.AddMinutes(-2)
$eventEnd = Get-Date
$systemEvents = @(Get-WinEvent -FilterHashtable @{
    LogName = 'System'
    StartTime = $eventStart
    EndTime = $eventEnd
} -ErrorAction SilentlyContinue | Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, Message)
$systemEvents | Export-Csv -LiteralPath (Join-Path $rawRoot 'windows_system_events.csv') `
    -NoTypeInformation -Encoding utf8

try {
    Copy-ApplicationLogs -OutputDirectory $logsRoot
} catch {
    if ($null -eq $runFailure) {
        $runFailure = $_
    }
    $_.Exception.GetType().Name |
        Set-Content -LiteralPath (Join-Path $rawRoot 'log_copy_error_type.txt') -Encoding ascii
}

$serverIps = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notmatch '^127\.' } |
    ForEach-Object { [string]$_.IPAddress })
Write-FinalizationProgress `
    -Step 3 `
    -Message 'redact network identifiers and assemble sanitized evidence' `
    -StartedAt $postprocessStartedAt
if (Test-Path -LiteralPath $pingPath -PathType Leaf) {
    Copy-Item -LiteralPath $pingPath -Destination (Join-Path $sanitizedRoot 'ping_spot.jsonl') -Force
}

$safeEvents = foreach ($event in $systemEvents) {
    [pscustomobject]@{
        TimeCreated = $event.TimeCreated
        Id = $event.Id
        Level = $event.LevelDisplayName
        Provider = $event.ProviderName
        Message = Protect-Text -Text ([string]$event.Message) -TargetIp $SpotIp -ServerIps $serverIps
    }
}
$safeEvents | Export-Csv -LiteralPath (Join-Path $sanitizedRoot 'windows_system_events_redacted.csv') `
    -NoTypeInformation -Encoding utf8

$collectorSession = Get-ChildItem -LiteralPath $appRoot -Directory -Filter 'operational_observability_*' |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
$appObservabilitySummary = $null
$triggerMonitorFailure = $null
if ($null -ne $collectorSession) {
    $triggerMonitorFailurePath = Join-Path `
        $collectorSession.FullName `
        'raw\trigger_monitor_failure.json'
    if (Test-Path -LiteralPath $triggerMonitorFailurePath -PathType Leaf) {
        try {
            $triggerMonitorFailure = Get-Content `
                -LiteralPath $triggerMonitorFailurePath `
                -Raw `
                -Encoding utf8 |
                ConvertFrom-Json
            if ($triggerMonitorFailure.schema_version -ne
                'spot-connecttimeout-trigger-monitor-failure-v1') {
                throw 'Unexpected trigger monitor failure evidence schema.'
            }
            Copy-Item `
                -LiteralPath $triggerMonitorFailurePath `
                -Destination (Join-Path $sanitizedRoot 'trigger_monitor_failure.json') `
                -Force
        } catch {
            $triggerMonitorFailure = $null
        }
    }
    $collectorSanitized = Join-Path $collectorSession.FullName 'sanitized'
    if (Test-Path -LiteralPath $collectorSanitized -PathType Container) {
        Copy-Item -LiteralPath $collectorSanitized -Destination (Join-Path $sanitizedRoot 'app_observability') `
            -Recurse -Force
    }
    $appObservabilitySummaryPath = Join-Path `
        $collectorSanitized `
        'operational_observability_summary.json'
    if (Test-Path -LiteralPath $appObservabilitySummaryPath -PathType Leaf) {
        try {
            $appObservabilitySummary = Get-Content `
                -LiteralPath $appObservabilitySummaryPath `
                -Raw `
                -Encoding utf8 |
                ConvertFrom-Json
            $appObservationStartedAt = [DateTimeOffset]::Parse(
                [string]$appObservabilitySummary.collection_started_at
            )
            $appObservationDeadlineAt = [DateTimeOffset]::Parse(
                [string]$appObservabilitySummary.collection_deadline_at
            )
            $appObservationEndedAt = [DateTimeOffset]::Parse(
                [string]$appObservabilitySummary.collection_ended_at
            )
            $appObservationGeneratedAt = [DateTimeOffset]::Parse(
                [string]$appObservabilitySummary.generated_at
            )
            $appObservationElapsedSeconds = [double]$appObservabilitySummary.collection_elapsed_sec
            $appDeadlineOverrunMilliseconds = [double]$appObservabilitySummary.deadline_overrun_ms
            $appObservationStopReason = [string]$appObservabilitySummary.observation_stop_reason
            $appEventTrigger = $appObservabilitySummary.event_trigger
        } catch {
            if ($null -eq $runFailure) {
                $runFailure = $_
            }
            $_.Exception.GetType().Name |
                Set-Content -LiteralPath (Join-Path $rawRoot 'app_summary_error_type.txt') `
                    -Encoding ascii
            $appObservabilitySummary = $null
        }
    }
}

if ($StopOnNewSpotConnectTimeout -and
    $null -eq $captureStopSignal -and
    (Test-Path -LiteralPath $captureStopSignalPath -PathType Leaf)) {
    try {
        $captureStopSignal = Get-Content `
            -LiteralPath $captureStopSignalPath `
            -Raw `
            -Encoding utf8 |
            ConvertFrom-Json
        $captureStopSignalEndedAt = [DateTimeOffset]::Parse(
            [string]$captureStopSignal.collection_ended_at
        )
    } catch {
        if ($null -eq $runFailure) {
            $runFailure = $_
        }
    }
}

$observationEndBoundarySaveLatencyMs = if (
    $null -eq $observationBoundaryTargetAt -or
    $null -eq $observationEndSnapshotCapturedAt
) {
    $null
} else {
    $boundarySaveDelta =
        [DateTimeOffset]$observationEndSnapshotCapturedAt -
        [DateTimeOffset]$observationBoundaryTargetAt
    [Math]::Max(
        0,
        [Math]::Round(
            $boundarySaveDelta.TotalMilliseconds,
            3
        )
    )
}

try {
    if ($null -eq $observationEndSnapshot) {
        throw 'Postprocess state requires the immutable observation end boundary.'
    }
    $postprocessState = New-CanaryPostprocessState `
        -LocalApiBase $ApiBase `
        -LocalConfigPath $ConfigPath `
        -ObservationEnd $observationEndSnapshot `
        -ObservationEndPath $observationEndPath `
        -PostprocessStartedAt ([DateTimeOffset]$postprocessStartedAt) `
        -OutputPath $postprocessStatePath
    $postprocessIntegrityFailures = @($postprocessState.integrity_failures)
    Copy-Item `
        -LiteralPath $postprocessStatePath `
        -Destination $safePostprocessStatePath `
        -ErrorAction Stop
} catch {
    $postprocessIntegrityFailures = @(
        'postprocess-state-capture-failed:{0}' -f
            $_.Exception.GetType().Name
    )
    if (-not (Test-Path -LiteralPath $postprocessStatePath -PathType Leaf)) {
        try {
            Write-ImmutableJson `
                -Value ([ordered]@{
                    schema_version = 'spot-canary-postprocess-state-v1'
                    status = 'capture-failed'
                    postprocess_started_at = if ($null -eq $postprocessStartedAt) {
                        $null
                    } else {
                        ([DateTimeOffset]$postprocessStartedAt).ToString('o')
                    }
                    observed_at = [DateTimeOffset]::Now.ToString('o')
                    integrity_failures = @($postprocessIntegrityFailures)
                    local_only = $true
                    added_spot_requests = $false
                }) `
                -Path $postprocessStatePath `
                -Depth 6
            Copy-Item `
                -LiteralPath $postprocessStatePath `
                -Destination $safePostprocessStatePath `
                -ErrorAction Stop
        } catch {
            $postprocessState = $null
        }
    }
}

$pingRows = @()
if (Test-Path -LiteralPath $pingPath -PathType Leaf) {
    $pingRows = @(Get-Content -LiteralPath $pingPath -Encoding utf8 | ForEach-Object {
        if (-not [string]::IsNullOrWhiteSpace($_)) { $_ | ConvertFrom-Json }
    })
}
$pingFailures = @($pingRows | Where-Object { -not [bool]$_.success }).Count
$pingSuccesses = @($pingRows | Where-Object { [bool]$_.success }).Count
$pingRoundTripValues = [double[]]@(
    $pingRows |
        Where-Object { [bool]$_.success -and $null -ne $_.roundtrip_time_ms } |
        ForEach-Object { [double]$_.roundtrip_time_ms }
)
$pingProbeWallValues = [double[]]@(
    $pingRows |
        Where-Object { $null -ne $_.probe_wall_time_ms } |
        ForEach-Object { [double]$_.probe_wall_time_ms }
)
$pingStatusCounts = [ordered]@{}
foreach ($pingRow in $pingRows) {
    $statusKey = if ([string]::IsNullOrWhiteSpace([string]$pingRow.status)) {
        'Unknown'
    } else {
        [string]$pingRow.status
    }
    if (-not $pingStatusCounts.Contains($statusKey)) {
        $pingStatusCounts[$statusKey] = 0
    }
    $pingStatusCounts[$statusKey] = [int]$pingStatusCounts[$statusKey] + 1
}

$requiredEvidenceMissing = @()
if ($null -eq $observationStartSnapshot -or
    -not (Test-Path -LiteralPath $safeObservationStartPath -PathType Leaf)) {
    $requiredEvidenceMissing += 'observation-start-boundary'
}
if ($null -eq $observationEndSnapshot -or
    -not (Test-Path -LiteralPath $safeObservationEndPath -PathType Leaf)) {
    $requiredEvidenceMissing += 'observation-end-boundary'
}
if ($null -ne $observationEndSnapshot -and
    [double]$observationEndSnapshot.capture_latency_ms -gt 5000) {
    $requiredEvidenceMissing += 'observation-end-boundary-within-5s'
}
if ($StopOnNewSpotConnectTimeout -and
    $captureStopSignalBoundaryStatus -notin @(
        'signal-observed',
        'planned-end-reached'
    )) {
    $requiredEvidenceMissing += 'observation-boundary-authority'
}
if ($StopOnNewSpotConnectTimeout -and
    $captureStopSignalIntegrityStatus -ne 'signal-observed') {
    $requiredEvidenceMissing += 'capture-stop-signal-integrity'
}
if ($captureStopSignalBoundaryStatus -eq 'planned-end-reached' -and
    $null -eq $parentCompletionRequest) {
    $requiredEvidenceMissing += 'parent-completion-request'
}
if ($null -ne $captureStopSignalObservationLatencyMs -and
    [double]$captureStopSignalObservationLatencyMs -gt 5000) {
    $requiredEvidenceMissing += 'capture-stop-signal-observed-within-5s'
}
if ($captureStopSignalBoundaryStatus -eq 'planned-end-reached' -and
    ($null -eq $captureStopSignalAfterBoundaryLatencyMs -or
        [double]$captureStopSignalAfterBoundaryLatencyMs -gt 5000)) {
    $requiredEvidenceMissing += 'capture-stop-signal-after-boundary-within-5s'
}
if ($null -ne $observationEndBoundarySaveLatencyMs -and
    [double]$observationEndBoundarySaveLatencyMs -gt 5000) {
    $requiredEvidenceMissing += 'observation-end-boundary-save-within-5s'
}
if (-not (Test-Path -LiteralPath $safeClockCalibrationPath -PathType Leaf)) {
    $requiredEvidenceMissing += 'clock-calibration'
}
if ($null -eq $postprocessState -or
    -not (Test-Path -LiteralPath $safePostprocessStatePath -PathType Leaf)) {
    $requiredEvidenceMissing += 'postprocess-state'
}
if ($postprocessIntegrityFailures.Count -gt 0) {
    $requiredEvidenceMissing += 'postprocess-integrity'
}
if ($framingAnalysisStatus -ne 'completed' -or
    -not (Test-Path -LiteralPath $framingEventsPath -PathType Leaf) -or
    -not (Test-Path -LiteralPath $framingSummaryPath -PathType Leaf)) {
    $requiredEvidenceMissing += 'body-free-http-framing'
}
if ($null -ne $framingSummary -and
    ($framingSummary.schema_version -ne 'spot-http-framing-evidence-v10' -or
        $null -eq $framingSummary.analysis_window -or
        $null -eq $framingSummary.packet_measurement)) {
    $requiredEvidenceMissing += 'packet-analysis-v10-contract'
}
if ($packetPayloadArtifactsRetained) {
    $requiredEvidenceMissing += 'packet-payload-cleanup'
}
if ($pingRows.Count -eq 0) {
    $requiredEvidenceMissing += 'ping-samples'
}
if ($null -eq $appObservabilitySummary) {
    $requiredEvidenceMissing += 'app-observability'
}
if ($StopOnNewSpotConnectTimeout -and $null -eq $captureStopSignal) {
    $requiredEvidenceMissing += 'capture-stop-signal'
}
if ($StopOnNewSpotConnectTimeout -and $null -eq $appEventTrigger) {
    $requiredEvidenceMissing += 'app-event-trigger-summary'
}
if ($directionProbeStatus -ne 'passed') {
    $requiredEvidenceMissing += 'packet-direction-preflight'
}
if ($null -eq $switchEvidenceState -or -not $switchEvidenceState.StartComplete) {
    $requiredEvidenceMissing += 'switch-start-counters'
}
if ($null -eq $switchEvidenceState -or -not $switchEvidenceState.EndComplete) {
    $requiredEvidenceMissing += 'switch-end-counters'
}
if ($null -ne $switchEvidenceState -and $switchEvidenceState.InvalidFileCount -gt 0) {
    $requiredEvidenceMissing += 'switch-evidence-generic-filenames'
}
$switchEmptyFileCount = if ($null -eq $switchEvidenceState) {
    0
} else {
    $switchEvidenceState.EmptyFileCount
}
if ($switchEmptyFileCount -gt 0) {
    $requiredEvidenceMissing += 'switch-evidence-nonempty-files'
}
$fatalRequiredEvidenceMissing = @($requiredEvidenceMissing)
if ($switchEvidenceUnavailableDeclared) {
    $fatalRequiredEvidenceMissing = @(
        $requiredEvidenceMissing |
            Where-Object {
                $_ -notin @('switch-start-counters', 'switch-end-counters')
            }
    )
}
$requiredEvidenceFailureCreated = $false
if ($null -eq $runFailure -and $fatalRequiredEvidenceMissing.Count -gt 0) {
    $runFailure = [System.InvalidOperationException]::new(
        ('Required evidence is missing: {0}' -f ($fatalRequiredEvidenceMissing -join ', '))
    )
    $requiredEvidenceFailureCreated = $true
}
$failureType = $null
if ($null -ne $runFailure) {
    if ($runFailure -is [System.Management.Automation.ErrorRecord]) {
        $failureType = $runFailure.Exception.GetType().Name
    } else {
        $failureType = $runFailure.GetType().Name
    }
}
$collectionResult = Resolve-CollectionResult `
    -HasRunFailure ($null -ne $runFailure) `
    -RequiredEvidenceFailureCreated $requiredEvidenceFailureCreated `
    -SwitchEvidenceUnavailable $switchEvidenceUnavailableDeclared
$failureReasonCode = $collectionResult.FailureReasonCode
$collectionReasonCode = $collectionResult.CollectionReasonCode
$switchEvidenceStatus = if ($switchEvidenceUnavailableDeclared) {
    'unavailable'
} elseif ($null -ne $switchEvidenceState -and
    $switchEvidenceState.StartComplete -and
    $switchEvidenceState.EndComplete -and
    $switchEvidenceState.InvalidFileCount -eq 0 -and
    $switchEmptyFileCount -eq 0) {
    'complete'
} else {
    'incomplete'
}
$effectiveObservationStartedAt = if ($null -ne $observationStartSnapshot) {
    [DateTimeOffset]::Parse(
        [string]$observationStartSnapshot.observed_at_completed
    )
} elseif ($null -eq $appObservationStartedAt) {
    if ($null -eq $observationStartedAt) {
        $null
    } else {
        [DateTimeOffset]$observationStartedAt
    }
} else {
    $appObservationStartedAt
}
$effectiveObservationEndedAt = if ($null -ne $observationEndSnapshot) {
    [DateTimeOffset]::Parse(
        [string]$observationEndSnapshot.observed_at_completed
    )
} elseif ($null -eq $appObservationEndedAt) {
    if ($null -eq $observationEndedAt) {
        $null
    } else {
        [DateTimeOffset]$observationEndedAt
    }
} else {
    $appObservationEndedAt
}
$observationTiming = Get-ObservationTimingSummary `
    -ObservationStartSnapshot $observationStartSnapshot `
    -ObservationEndSnapshot $observationEndSnapshot `
    -AppObservationElapsedSeconds $appObservationElapsedSeconds `
    -FallbackStartedAt $effectiveObservationStartedAt `
    -FallbackEndedAt $effectiveObservationEndedAt
$effectiveObservationElapsedSeconds = $observationTiming.elapsed_seconds
$collectorPostprocessElapsedSeconds = if ($null -eq $appObservationEndedAt -or
    $null -eq $collectorReturnedAt) {
    $null
} else {
    [Math]::Round(
        (([DateTimeOffset]$collectorReturnedAt) - $appObservationEndedAt).TotalSeconds,
        3
    )
}
$appSummaryGenerationElapsedSeconds = if ($null -eq $appObservationEndedAt -or
    $null -eq $appObservationGeneratedAt) {
    $null
} else {
    [Math]::Round(
        ($appObservationGeneratedAt - $appObservationEndedAt).TotalSeconds,
        3
    )
}
$packetCaptureElapsedSeconds = if ($null -eq $captureStartedAt -or
    $null -eq $captureEndedAt) {
    $null
} else {
    [Math]::Round(($captureEndedAt - $captureStartedAt).TotalSeconds, 3)
}
$packetCaptureTailSeconds = if ($null -eq $appObservationEndedAt -or
    $null -eq $captureEndedAt) {
    $null
} else {
    [Math]::Round(
        (([DateTimeOffset]$captureEndedAt) - $appObservationEndedAt).TotalSeconds,
        3
    )
}
$packetCaptureCoverage = if ($null -eq $framingSummary) {
    $null
} else {
    $framingSummary.capture_coverage
}
$packetCaptureCoverageStatus = if ($null -eq $packetCaptureCoverage) {
    $null
} else {
    [string]$packetCaptureCoverage.status
}
$packetCaptureOverwriteDetected = if ($null -eq $packetCaptureCoverage) {
    $null
} else {
    [bool]$packetCaptureCoverage.overwrite_detected
}
$packetCaptureOverwriteUnresolvedAttempts = if (
    $null -eq $framingSummary -or
    $null -eq $framingSummary.tcp_connection_summary
) {
    $null
} else {
    [int]$framingSummary.tcp_connection_summary.capture_overwrite_unresolved_attempts
}
$eventTriggerDetected = (
    $null -ne $captureStopSignal -and
    [bool]$captureStopSignal.trigger_detected
)
$eventTriggerDetectedAt = if (-not $eventTriggerDetected -or
    [string]::IsNullOrWhiteSpace([string]$captureStopSignal.trigger_detected_at)) {
    $null
} else {
    [DateTimeOffset]::Parse([string]$captureStopSignal.trigger_detected_at)
}
$eventTriggerErrorAt = if (-not $eventTriggerDetected -or
    [string]::IsNullOrWhiteSpace([string]$captureStopSignal.trigger_error_at)) {
    $null
} else {
    [DateTimeOffset]::Parse([string]$captureStopSignal.trigger_error_at)
}
$eventTriggerDetectionLatencyMs = if (-not $eventTriggerDetected) {
    $null
} else {
    [double]$captureStopSignal.trigger_detection_latency_ms
}
$eventTriggerBaselineRepeatTotal = if ($null -eq $captureStopSignal) {
    $null
} else {
    [int]$captureStopSignal.baseline_repeat_total
}
$eventTriggerObservedRepeatTotal = if ($null -eq $captureStopSignal) {
    $null
} else {
    [int]$captureStopSignal.observed_repeat_total
}
$eventTriggerRepeatDelta = if ($null -eq $captureStopSignal) {
    $null
} else {
    [int]$captureStopSignal.repeat_delta
}
$eventTriggerDetectionLatencyWarningMs = Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'trigger_detection_latency_warning_ms'
$eventTriggerDetectionQuality = Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'trigger_detection_quality'
$eventTriggerDetectionLatencyExceeded = [bool](Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'trigger_detection_latency_exceeded' `
    -DefaultValue $false)
$eventTriggerMonitorMode = Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'monitor_mode'
$eventTriggerMonitorPollIntervalMs = Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'monitor_poll_interval_ms'
$eventTriggerMonitorPollCount = Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'monitor_poll_count'
$eventTriggerMonitorErrorCount = Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'monitor_error_count'
$eventTriggerMonitorRecoveredErrorCount = Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'monitor_recovered_error_count'
$eventTriggerMonitorUnrecoveredErrorCount = Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'monitor_unrecovered_error_count'
$eventTriggerMonitorMaxConsecutiveErrorCount = Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'monitor_max_consecutive_error_count'
$eventTriggerMonitorIntegrityStatus = Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'monitor_integrity_status'
$eventTriggerMonitorIntegrityPolicy = Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'monitor_integrity_policy'
$eventTriggerMonitorPollGapMaxMs = Get-OptionalPropertyValue `
    -Object $captureStopSignal `
    -Name 'monitor_poll_gap_ms_max'
$effectiveObservationStopReason = if (-not [string]::IsNullOrWhiteSpace(
    $appObservationStopReason
)) {
    $appObservationStopReason
} elseif ($null -ne $captureStopSignal) {
    [string]$captureStopSignal.stop_reason
} else {
    $null
}
$packetCaptureTailAfterTriggerSeconds = if ($null -eq $eventTriggerDetectedAt -or
    $null -eq $captureEndedAt) {
    $null
} else {
    [Math]::Round(
        (([DateTimeOffset]$captureEndedAt) - $eventTriggerDetectedAt).TotalSeconds,
        3
    )
}
$observationBoundaryStatus = if (
    $null -eq $observationStartSnapshot -or
    $null -eq $observationEndSnapshot
) {
    'missing'
} elseif ([double]$observationEndSnapshot.capture_latency_ms -gt 5000 -or
    $captureStopSignalBoundaryStatus -notin @(
        'signal-observed',
        'planned-end-reached'
    ) -or
    $captureStopSignalIntegrityStatus -ne 'signal-observed' -or
    ($null -ne $captureStopSignalObservationLatencyMs -and
        [double]$captureStopSignalObservationLatencyMs -gt 5000) -or
    ($captureStopSignalBoundaryStatus -eq 'planned-end-reached' -and
        ($null -eq $captureStopSignalAfterBoundaryLatencyMs -or
            [double]$captureStopSignalAfterBoundaryLatencyMs -gt 5000)) -or
    ($null -ne $observationEndBoundarySaveLatencyMs -and
        $observationEndBoundarySaveLatencyMs -gt 5000)) {
    'late'
} else {
    'complete'
}

$manifest.status = $collectionResult.Status
$manifest['observation_boundary_schema'] = 'spot-canary-observation-boundary-v1'
$manifest['observation_boundary_status'] = $observationBoundaryStatus
$manifest['observation_counter_policy'] = 'observation-start-to-observation-end'
$manifest['observation_end_boundary_save_latency_ms'] = (
    $observationEndBoundarySaveLatencyMs
)
$manifest['capture_stop_signal_boundary_status'] =
    $captureStopSignalBoundaryStatus
$manifest['capture_stop_signal_integrity_status'] =
    $captureStopSignalIntegrityStatus
$manifest['capture_stop_signal_after_boundary_latency_ms'] =
    $captureStopSignalAfterBoundaryLatencyMs
$manifest['parent_completion_request_id'] = if (
    $null -eq $parentCompletionRequest
) {
    $null
} else {
    [string]$parentCompletionRequest.request_id
}
$manifest['parent_completion_request_source'] = if (
    $null -eq $parentCompletionRequest
) {
    $null
} else {
    [string]$parentCompletionRequest.request_source
}
$manifest['capture_stop_signal_observation_latency_limit_ms'] = 5000
$manifest['postprocess_state_status'] = if ($null -eq $postprocessState) {
    'missing'
} else {
    [string]$postprocessState.status
}
$manifest['postprocess_integrity_failures'] = @($postprocessIntegrityFailures)
$manifest['postprocess_state_sha256'] = if (
    Test-Path -LiteralPath $safePostprocessStatePath -PathType Leaf
) {
    (Get-FileHash $safePostprocessStatePath -Algorithm SHA256).Hash
} else {
    $null
}
$manifest['observation_start_sha256'] = if (
    Test-Path -LiteralPath $safeObservationStartPath -PathType Leaf
) { (Get-FileHash $safeObservationStartPath -Algorithm SHA256).Hash } else { $null }
$manifest['observation_end_sha256'] = if (
    Test-Path -LiteralPath $safeObservationEndPath -PathType Leaf
) { (Get-FileHash $safeObservationEndPath -Algorithm SHA256).Hash } else { $null }
$manifest['packet_analysis_schema'] = if ($null -eq $framingSummary) {
    $null
} else {
    [string]$framingSummary.schema_version
}
$manifest['ended_at_kst'] = $endedAt.ToString('o')
$manifest['observation_started_at_kst'] = if ($null -eq $effectiveObservationStartedAt) {
    $null
} else {
    $effectiveObservationStartedAt.ToString('o')
}
$manifest['observation_ended_at_kst'] = if ($null -eq $effectiveObservationEndedAt) {
    $null
} else {
    $effectiveObservationEndedAt.ToString('o')
}
$manifest['observation_elapsed_seconds'] = $effectiveObservationElapsedSeconds
$manifest['observation_elapsed_source'] = $observationTiming.source
$manifest['parent_observation_elapsed_seconds'] = (
    $observationTiming.parent_monotonic_elapsed_seconds
)
$manifest['app_observation_elapsed_seconds'] = (
    $observationTiming.app_collector_elapsed_seconds
)
$manifest['observation_deadline_at_kst'] = if ($null -eq $appObservationDeadlineAt) {
    $null
} else {
    $appObservationDeadlineAt.ToString('o')
}
$manifest['observation_deadline_overrun_ms'] = $appDeadlineOverrunMilliseconds
$manifest['observation_stop_reason'] = $effectiveObservationStopReason
$manifest['event_trigger_enabled'] = [bool]$StopOnNewSpotConnectTimeout
$manifest['event_trigger_detected'] = $eventTriggerDetected
$manifest['event_trigger_source'] = if ($eventTriggerDetected) { 'spot_image' } else { $null }
$manifest['event_trigger_error_type'] = if ($eventTriggerDetected) {
    'ConnectTimeout'
} else {
    $null
}
$manifest['event_trigger_detected_at_kst'] = if ($null -eq $eventTriggerDetectedAt) {
    $null
} else {
    $eventTriggerDetectedAt.ToString('o')
}
$manifest['event_trigger_error_at_kst'] = if ($null -eq $eventTriggerErrorAt) {
    $null
} else {
    $eventTriggerErrorAt.ToString('o')
}
$manifest['event_trigger_detection_latency_ms'] = $eventTriggerDetectionLatencyMs
$manifest['event_trigger_detection_latency_warning_ms'] = (
    $eventTriggerDetectionLatencyWarningMs
)
$manifest['event_trigger_detection_quality'] = $eventTriggerDetectionQuality
$manifest['event_trigger_detection_latency_exceeded'] = (
    $eventTriggerDetectionLatencyExceeded
)
$manifest['event_trigger_monitor_mode'] = $eventTriggerMonitorMode
$manifest['event_trigger_monitor_poll_interval_ms'] = (
    $eventTriggerMonitorPollIntervalMs
)
$manifest['event_trigger_monitor_poll_count'] = $eventTriggerMonitorPollCount
$manifest['event_trigger_monitor_error_count'] = $eventTriggerMonitorErrorCount
$manifest['event_trigger_monitor_recovered_error_count'] = (
    $eventTriggerMonitorRecoveredErrorCount
)
$manifest['event_trigger_monitor_unrecovered_error_count'] = (
    $eventTriggerMonitorUnrecoveredErrorCount
)
$manifest['event_trigger_monitor_max_consecutive_error_count'] = (
    $eventTriggerMonitorMaxConsecutiveErrorCount
)
$manifest['event_trigger_monitor_integrity_status'] = (
    $eventTriggerMonitorIntegrityStatus
)
$manifest['event_trigger_monitor_integrity_policy'] = (
    $eventTriggerMonitorIntegrityPolicy
)
$manifest['event_trigger_monitor_poll_gap_ms_max'] = (
    $eventTriggerMonitorPollGapMaxMs
)
$manifest['event_trigger_baseline_repeat_total'] = $eventTriggerBaselineRepeatTotal
$manifest['event_trigger_observed_repeat_total'] = $eventTriggerObservedRepeatTotal
$manifest['event_trigger_repeat_delta'] = $eventTriggerRepeatDelta
$manifest['capture_stop_signal_observed_at_kst'] = if (
    $null -eq $captureStopSignalObservedAt
) {
    $null
} else {
    $captureStopSignalObservedAt.ToString('o')
}
$manifest['capture_stop_signal_observation_latency_ms'] = $captureStopSignalObservationLatencyMs
$manifest['collector_process_returned_at_kst'] = if ($null -eq $collectorReturnedAt) {
    $null
} else {
    $collectorReturnedAt.ToString('o')
}
$manifest['collector_postprocess_elapsed_seconds'] = $collectorPostprocessElapsedSeconds
$manifest['app_summary_generation_elapsed_seconds'] = $appSummaryGenerationElapsedSeconds
$manifest['packet_capture_started_at_kst'] = if ($null -eq $captureStartedAt) {
    $null
} else {
    $captureStartedAt.ToString('o')
}
$manifest['packet_capture_ended_at_kst'] = if ($null -eq $captureEndedAt) {
    $null
} else {
    $captureEndedAt.ToString('o')
}
$manifest['packet_capture_elapsed_seconds'] = $packetCaptureElapsedSeconds
$manifest['packet_capture_tail_after_observation_seconds'] = $packetCaptureTailSeconds
$manifest['packet_capture_tail_after_trigger_seconds'] = $packetCaptureTailAfterTriggerSeconds
$manifest['packet_capture_file_size_bytes'] = $captureFileSizeBytes
$manifest['packet_capture_circular_limit_bytes'] = $circularCaptureMaxFileSizeBytes
$manifest['packet_capture_coverage_status'] = $packetCaptureCoverageStatus
$manifest['packet_capture_overwrite_detected'] = $packetCaptureOverwriteDetected
$manifest['packet_capture_overwrite_unresolved_attempts'] = (
    $packetCaptureOverwriteUnresolvedAttempts
)
$manifest['windows_tcp_ipv4_evidence_status'] = $windowsTcpEvidenceStatus
$manifest['windows_tcp_ipv4_delta_schema'] = if ($null -eq $windowsTcpDelta) {
    $null
} else {
    [string]$windowsTcpDelta.schema_version
}
$manifest['windows_tcp_ipv4_scope'] = 'windows-ipv4-global'
$manifest['packet_capture_retained_first_packet_at_kst'] = if (
    $null -eq $packetCaptureCoverage
) {
    $null
} else {
    $packetCaptureCoverage.retained_first_packet_at
}
$manifest['packet_capture_retained_last_packet_at_kst'] = if (
    $null -eq $packetCaptureCoverage
) {
    $null
} else {
    $packetCaptureCoverage.retained_last_packet_at
}
$manifest['packet_capture_continuous_bidirectional_start_at_kst'] = if (
    $null -eq $packetCaptureCoverage
) {
    $null
} else {
    $packetCaptureCoverage.continuous_bidirectional_start_at
}
$manifest['failure_type'] = $failureType
$manifest['failure_reason_code'] = $failureReasonCode
$manifest['collection_reason_code'] = $collectionReasonCode
$manifest['collector_exit_code'] = $collectionResult.ExitCode
$manifest['required_evidence_missing'] = @($requiredEvidenceMissing)
$manifest['pktmon_filter_cleanup'] = $filterCleanupStatus
$manifest['framing_analysis_status'] = $framingAnalysisStatus
$manifest['packet_payload_artifacts_retained'] = $packetPayloadArtifactsRetained
$manifest['switch_evidence_file_count'] = if ($null -eq $switchEvidenceState) {
    0
} else {
    $switchEvidenceState.FileCount
}
$manifest['switch_start_counters_present'] = (
    $null -ne $switchEvidenceState -and $switchEvidenceState.StartComplete
)
$manifest['switch_end_counters_present'] = (
    $null -ne $switchEvidenceState -and $switchEvidenceState.EndComplete
)
$manifest['switch_evidence_invalid_filename_count'] = if ($null -eq $switchEvidenceState) {
    0
} else {
    $switchEvidenceState.InvalidFileCount
}
$manifest['switch_evidence_empty_file_count'] = $switchEmptyFileCount
$manifest['switch_evidence_status'] = $switchEvidenceStatus
$manifest['switch_evidence_unavailable_declared'] = $switchEvidenceUnavailableDeclared
$manifest['switch_evidence_required_for_collected_status'] = $true
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $rawManifestPath -Encoding utf8

$safeSummary = [ordered]@{
    run_id = $runId
    status = $manifest.status
    started_at_kst = $startedAt.ToString('o')
    ended_at_kst = $endedAt.ToString('o')
    observation_minutes_requested = $ObservationMinutes
    observation_duration_seconds_requested = $ObservationMinutes * 60
    observation_boundary_schema = 'spot-canary-observation-boundary-v1'
    observation_boundary_status = $observationBoundaryStatus
    observation_counter_policy = 'observation-start-to-observation-end'
    observation_end_boundary_save_latency_ms = $observationEndBoundarySaveLatencyMs
    capture_stop_signal_boundary_status = $captureStopSignalBoundaryStatus
    capture_stop_signal_integrity_status = $captureStopSignalIntegrityStatus
    capture_stop_signal_after_boundary_latency_ms = (
        $captureStopSignalAfterBoundaryLatencyMs
    )
    parent_completion_request_id = if ($null -eq $parentCompletionRequest) {
        $null
    } else {
        [string]$parentCompletionRequest.request_id
    }
    parent_completion_request_source = if ($null -eq $parentCompletionRequest) {
        $null
    } else {
        [string]$parentCompletionRequest.request_source
    }
    capture_stop_signal_observation_latency_limit_ms = 5000
    postprocess_state_status = if ($null -eq $postprocessState) {
        'missing'
    } else {
        [string]$postprocessState.status
    }
    postprocess_integrity_failures = @($postprocessIntegrityFailures)
    postprocess_state_sha256 = if (
        Test-Path -LiteralPath $safePostprocessStatePath -PathType Leaf
    ) {
        (Get-FileHash $safePostprocessStatePath -Algorithm SHA256).Hash
    } else {
        $null
    }
    packet_analysis_schema = if ($null -eq $framingSummary) {
        $null
    } else {
        [string]$framingSummary.schema_version
    }
    observation_started_at_kst = if ($null -eq $effectiveObservationStartedAt) {
        $null
    } else {
        $effectiveObservationStartedAt.ToString('o')
    }
    observation_ended_at_kst = if ($null -eq $effectiveObservationEndedAt) {
        $null
    } else {
        $effectiveObservationEndedAt.ToString('o')
    }
    observation_elapsed_seconds = $effectiveObservationElapsedSeconds
    observation_elapsed_source = $observationTiming.source
    parent_observation_elapsed_seconds = (
        $observationTiming.parent_monotonic_elapsed_seconds
    )
    app_observation_elapsed_seconds = (
        $observationTiming.app_collector_elapsed_seconds
    )
    observation_deadline_at_kst = if ($null -eq $appObservationDeadlineAt) {
        $null
    } else {
        $appObservationDeadlineAt.ToString('o')
    }
    observation_deadline_overrun_ms = $appDeadlineOverrunMilliseconds
    observation_stop_reason = $effectiveObservationStopReason
    event_trigger_enabled = [bool]$StopOnNewSpotConnectTimeout
    event_trigger_detected = $eventTriggerDetected
    event_trigger_source = if ($eventTriggerDetected) { 'spot_image' } else { $null }
    event_trigger_error_type = if ($eventTriggerDetected) { 'ConnectTimeout' } else { $null }
    event_trigger_detected_at_kst = if ($null -eq $eventTriggerDetectedAt) {
        $null
    } else {
        $eventTriggerDetectedAt.ToString('o')
    }
    event_trigger_error_at_kst = if ($null -eq $eventTriggerErrorAt) {
        $null
    } else {
        $eventTriggerErrorAt.ToString('o')
    }
    event_trigger_detection_latency_ms = $eventTriggerDetectionLatencyMs
    event_trigger_detection_latency_warning_ms = (
        $eventTriggerDetectionLatencyWarningMs
    )
    event_trigger_detection_quality = $eventTriggerDetectionQuality
    event_trigger_detection_latency_exceeded = (
        $eventTriggerDetectionLatencyExceeded
    )
    event_trigger_monitor_mode = $eventTriggerMonitorMode
    event_trigger_monitor_poll_interval_ms = $eventTriggerMonitorPollIntervalMs
    event_trigger_monitor_poll_count = $eventTriggerMonitorPollCount
    event_trigger_monitor_error_count = $eventTriggerMonitorErrorCount
    event_trigger_monitor_recovered_error_count =
        $eventTriggerMonitorRecoveredErrorCount
    event_trigger_monitor_unrecovered_error_count =
        $eventTriggerMonitorUnrecoveredErrorCount
    event_trigger_monitor_max_consecutive_error_count =
        $eventTriggerMonitorMaxConsecutiveErrorCount
    event_trigger_monitor_integrity_status = $eventTriggerMonitorIntegrityStatus
    event_trigger_monitor_integrity_policy = $eventTriggerMonitorIntegrityPolicy
    event_trigger_monitor_poll_gap_ms_max = $eventTriggerMonitorPollGapMaxMs
    event_trigger_baseline_repeat_total = $eventTriggerBaselineRepeatTotal
    event_trigger_observed_repeat_total = $eventTriggerObservedRepeatTotal
    event_trigger_repeat_delta = $eventTriggerRepeatDelta
    capture_stop_signal_observed_at_kst = if ($null -eq $captureStopSignalObservedAt) {
        $null
    } else {
        $captureStopSignalObservedAt.ToString('o')
    }
    capture_stop_signal_observation_latency_ms = $captureStopSignalObservationLatencyMs
    post_trigger_capture_seconds_requested = $PostTriggerCaptureSeconds
    collector_process_returned_at_kst = if ($null -eq $collectorReturnedAt) {
        $null
    } else {
        $collectorReturnedAt.ToString('o')
    }
    collector_postprocess_elapsed_seconds = $collectorPostprocessElapsedSeconds
    app_summary_generation_elapsed_seconds = $appSummaryGenerationElapsedSeconds
    packet_capture_started_at_kst = if ($null -eq $captureStartedAt) {
        $null
    } else {
        $captureStartedAt.ToString('o')
    }
    packet_capture_ended_at_kst = if ($null -eq $captureEndedAt) {
        $null
    } else {
        $captureEndedAt.ToString('o')
    }
    packet_capture_elapsed_seconds = $packetCaptureElapsedSeconds
    packet_capture_tail_after_observation_seconds = $packetCaptureTailSeconds
    packet_capture_tail_after_trigger_seconds = $packetCaptureTailAfterTriggerSeconds
    packet_capture_file_size_bytes = $captureFileSizeBytes
    packet_capture_circular_limit_bytes = $circularCaptureMaxFileSizeBytes
    packet_capture_coverage = $packetCaptureCoverage
    packet_capture_overwrite_unresolved_attempts = (
        $packetCaptureOverwriteUnresolvedAttempts
    )
    failure_type = $failureType
    failure_reason_code = $failureReasonCode
    collection_reason_code = $collectionReasonCode
    collector_exit_code = $collectionResult.ExitCode
    required_evidence_missing = @($requiredEvidenceMissing)
    trigger_monitor_failure_present = $null -ne $triggerMonitorFailure
    trigger_monitor_failure_reason_code = if ($null -eq $triggerMonitorFailure) {
        $null
    } else {
        [string]$triggerMonitorFailure.reason_code
    }
    trigger_monitor_failure_job_state = if ($null -eq $triggerMonitorFailure) {
        $null
    } else {
        [string]$triggerMonitorFailure.job_state
    }
    ping_samples = $pingRows.Count
    ping_successes = $pingSuccesses
    ping_failures = $pingFailures
    ping_status_counts = $pingStatusCounts
    ping_roundtrip_time_ms_p95 = Get-PercentileValue -Values $pingRoundTripValues -Percentile 0.95
    ping_roundtrip_time_ms_max = if ($pingRoundTripValues.Count -eq 0) {
        $null
    } else {
        [double](($pingRoundTripValues | Measure-Object -Maximum).Maximum)
    }
    ping_probe_wall_time_ms_max = if ($pingProbeWallValues.Count -eq 0) {
        $null
    } else {
        [double](($pingProbeWallValues | Measure-Object -Maximum).Maximum)
    }
    windows_tcp_ipv4_evidence_status = $windowsTcpEvidenceStatus
    windows_tcp_ipv4_delta = $windowsTcpDelta
    framing_analysis_status = $framingAnalysisStatus
    framing_events_created = (Test-Path -LiteralPath $framingEventsPath -PathType Leaf)
    framing_summary_created = (Test-Path -LiteralPath $framingSummaryPath -PathType Leaf)
    packet_capture_snapshot_bytes = 512
    packet_payload_artifacts_retained = $packetPayloadArtifactsRetained
    packet_direction_preflight = $directionProbeStatus
    packet_direction_probe_seconds = $directionProbeSeconds
    packet_direction_probe_outbound_count = $directionProbeOutboundCount
    packet_direction_probe_inbound_count = $directionProbeInboundCount
    pktmon_filter_cleanup = $filterCleanupStatus
    app_restart_performed = $false
    settings_changed = $false
    error_queue_cleared = $false
    image_load_test_performed = $false
    switch_logs_required = $true
    switch_evidence_file_count = if ($null -eq $switchEvidenceState) {
        0
    } else {
        $switchEvidenceState.FileCount
    }
    switch_start_counters_present = (
        $null -ne $switchEvidenceState -and $switchEvidenceState.StartComplete
    )
    switch_end_counters_present = (
        $null -ne $switchEvidenceState -and $switchEvidenceState.EndComplete
    )
    switch_evidence_invalid_filename_count = if ($null -eq $switchEvidenceState) {
        0
    } else {
        $switchEvidenceState.InvalidFileCount
    }
    switch_evidence_empty_file_count = $switchEmptyFileCount
    switch_evidence_status = $switchEvidenceStatus
    switch_evidence_unavailable_declared = $switchEvidenceUnavailableDeclared
    switch_evidence_required_for_collected_status = $true
    raw_private_location = 'Retained in the same run folder on the real server.'
}
$safeSummary | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $sanitizedRoot 'field_collection_summary.json') -Encoding utf8

Write-FinalizationProgress `
    -Step 4 `
    -Message 'calculate hashes and create the sanitized sharing ZIP' `
    -StartedAt $postprocessStartedAt
New-RawHashManifest -RawRoot $rawRoot -OutputPath (Join-Path $sanitizedRoot 'raw_file_sha256.csv')

$sanitizedZip = Join-Path $evidenceRoot ("{0}_sanitized_share.zip" -f $runId)
Compress-Archive -Path (Join-Path $sanitizedRoot '*') -DestinationPath $sanitizedZip -Force
$zipHash = Get-FileHash -LiteralPath $sanitizedZip -Algorithm SHA256
$zipHash.Hash.ToLowerInvariant() |
    Set-Content -LiteralPath (Join-Path $evidenceRoot 'sanitized_share_sha256.txt') -Encoding ascii
Write-Host '[PROGRESS] Finalization complete. The evidence package is ready.' -ForegroundColor Green

Write-Host ('Private raw folder on the server: {0}' -f $rawRoot) -ForegroundColor Yellow
Write-Host ('Sanitized ZIP for sharing: {0}' -f $sanitizedZip) -ForegroundColor Green

if ($null -ne $runFailure) {
    $missingText = if ($requiredEvidenceMissing.Count -eq 0) {
        'none'
    } else {
        $requiredEvidenceMissing -join ','
    }
    throw (
        'Collection failed. The raw folder was retained. ' +
        'Reason: {0}. Error type: {1}. Required evidence missing: {2}.' -f `
            $failureReasonCode,
            $failureType,
            $missingText
    )
}

if ($collectionResult.Status -eq 'PARTIAL') {
    Write-Warning (
        'Evidence collection completed with PARTIAL status because managed-switch evidence is unavailable. ' +
        'Switch faults remain unexcluded.'
    )
    Write-Host (
        'COLLECTION_RESULT_PARTIAL reason={0} exit_code={1}' -f `
            $collectionReasonCode,
            $collectionResult.ExitCode
    ) -ForegroundColor Yellow
    exit $collectionResult.ExitCode
}

Write-Host '[DONE] Evidence collection completed. The application and settings were not changed.' -ForegroundColor Green
