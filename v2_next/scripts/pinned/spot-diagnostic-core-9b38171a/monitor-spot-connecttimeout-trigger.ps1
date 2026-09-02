[CmdletBinding()]
param(
    [string]$ApiBase = 'http://127.0.0.1:8000',

    [ValidateRange(1, 10800)]
    [int]$DurationSec = 7200,

    [ValidateRange(100, 60000)]
    [int]$PollIntervalMs = 1000,

    [ValidateRange(100, 60000)]
    [int]$RequestTimeoutMs = 1000,

    [string]$RawRoot = '',

    [string]$CaptureStopSignalPath = '',

    [string]$CompletionRequestPath = '',

    [ValidateRange(1, 300)]
    [int]$CompletionRequestGraceSec = 30,

    [ValidateRange(1, 600000)]
    [int]$DetectionLatencyWarningMs = 5000,

    [switch]$SelfTest
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Get-PropertyValue {
    param(
        [object]$Object,
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }
    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Name)) {
            return $Object[$Name]
        }
        return $null
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Get-PositiveRepeatCount {
    param([object]$Value)

    $repeat = 1
    if ($null -ne $Value) {
        try {
            $repeat = [int]$Value
        } catch {
            $repeat = 1
        }
    }
    return [Math]::Max(1, $repeat)
}

function Get-SpotConnectTimeoutTriggerState {
    param([object]$Body)

    $itemCount = 0
    $repeatTotal = 0
    $latestErrorAt = $null
    foreach ($item in @((Get-PropertyValue -Object $Body -Name 'items'))) {
        if ($null -eq $item) {
            continue
        }
        $source = [string](Get-PropertyValue -Object $item -Name 'source')
        $errorType = [string](Get-PropertyValue -Object $item -Name 'error_type')
        if ($source -cne 'spot_image' -or $errorType -cne 'ConnectTimeout') {
            continue
        }

        $itemCount += 1
        $repeatTotal += Get-PositiveRepeatCount -Value (
            Get-PropertyValue -Object $item -Name 'repeat'
        )
        $timeText = [string](Get-PropertyValue -Object $item -Name 'time_iso')
        $parsedTime = [DateTimeOffset]::MinValue
        if ([DateTimeOffset]::TryParse($timeText, [ref]$parsedTime) -and
            ($null -eq $latestErrorAt -or $parsedTime -gt $latestErrorAt)) {
            $latestErrorAt = $parsedTime
        }
    }

    return [pscustomobject]@{
        ItemCount = $itemCount
        RepeatTotal = $repeatTotal
        LatestErrorAt = $latestErrorAt
    }
}

function Test-NewSpotConnectTimeout {
    param(
        [object]$Baseline,
        [object]$Current
    )

    if ($null -eq $Baseline -or $null -eq $Current) {
        return $false
    }
    if ([int]$Current.RepeatTotal -gt [int]$Baseline.RepeatTotal -or
        [int]$Current.ItemCount -gt [int]$Baseline.ItemCount) {
        return $true
    }
    return (
        $null -ne $Current.LatestErrorAt -and
        (
            $null -eq $Baseline.LatestErrorAt -or
            $Current.LatestErrorAt -gt $Baseline.LatestErrorAt
        )
    )
}

function New-Sha256Text {
    param([string]$Text)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
        return (
            [BitConverter]::ToString($algorithm.ComputeHash($bytes)) -replace '-', ''
        ).ToLowerInvariant()
    } finally {
        $algorithm.Dispose()
    }
}

function ConvertFrom-JsonOrNull {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $null
    }
    try {
        return $Text | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Join-ApiUrl {
    param(
        [string]$Base,
        [string]$Path
    )

    return '{0}/{1}' -f $Base.TrimEnd('/'), $Path.TrimStart('/')
}

function Invoke-BoundedReadOnlyEndpoint {
    param(
        [string]$Uri,
        [int]$TimeoutMs
    )

    $startedAt = [DateTimeOffset]::Now
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $response = $null
    $stream = $null
    $reader = $null
    try {
        $request = [Net.HttpWebRequest][Net.WebRequest]::Create($Uri)
        $request.Method = 'GET'
        $request.Timeout = $TimeoutMs
        $request.ReadWriteTimeout = $TimeoutMs
        $request.KeepAlive = $false
        $request.Proxy = $null
        $response = [Net.HttpWebResponse]$request.GetResponse()
        $stream = $response.GetResponseStream()
        if ($null -eq $stream) {
            $body = ''
        } else {
            if ($stream.CanTimeout) {
                $stream.ReadTimeout = $TimeoutMs
            }
            $reader = [IO.StreamReader]::new($stream)
            $body = $reader.ReadToEnd()
        }
        $watch.Stop()
        return [pscustomobject][ordered]@{
            ok = $true
            status_code = [int]$response.StatusCode
            body = [string]$body
            error = $null
            request_started_at = $startedAt.ToString('o')
            request_completed_at = [DateTimeOffset]::Now.ToString('o')
            request_elapsed_ms = [Math]::Round($watch.Elapsed.TotalMilliseconds, 1)
        }
    } catch {
        $watch.Stop()
        $exception = $_.Exception
        return [pscustomobject][ordered]@{
            ok = $false
            status_code = 0
            body = ''
            error = $exception.GetType().Name
            error_type = $exception.GetType().FullName
            error_message = $exception.Message
            fully_qualified_error_id = $_.FullyQualifiedErrorId
            error_category = [string]$_.CategoryInfo.Category
            error_hresult = $exception.HResult
            script_stack_trace = $_.ScriptStackTrace
            request_started_at = $startedAt.ToString('o')
            request_completed_at = [DateTimeOffset]::Now.ToString('o')
            request_elapsed_ms = [Math]::Round($watch.Elapsed.TotalMilliseconds, 1)
        }
    } finally {
        if ($null -ne $reader) {
            $reader.Dispose()
        } elseif ($null -ne $stream) {
            $stream.Dispose()
        }
        if ($null -ne $response) {
            $response.Dispose()
        }
    }
}

function New-MonitorErrorEvent {
    param(
        [int]$Sample,
        [object]$Result,
        [double]$PollGapMs,
        [int]$ConsecutiveErrorCount
    )

    return [ordered]@{
        schema_version = 'spot-trigger-monitor-error-event-raw-v1'
        sample = $Sample
        request_started_at = $Result.request_started_at
        request_completed_at = $Result.request_completed_at
        request_elapsed_ms = $Result.request_elapsed_ms
        poll_gap_ms = [Math]::Round($PollGapMs, 1)
        status_code = $Result.status_code
        error_type = $Result.error_type
        error_message = $Result.error_message
        fully_qualified_error_id = $Result.fully_qualified_error_id
        error_category = $Result.error_category
        error_hresult = $Result.error_hresult
        script_stack_trace = $Result.script_stack_trace
        consecutive_error_count = $ConsecutiveErrorCount
        recovered = $false
        recovered_at = $null
        recovery_gap_ms = $null
    }
}

function Complete-MonitorErrorEvent {
    param(
        [System.Collections.IDictionary]$Event,
        [DateTimeOffset]$RecoveredAt,
        [double]$RecoveryGapMs
    )

    $Event['recovered'] = $true
    $Event['recovered_at'] = $RecoveredAt.ToString('o')
    $Event['recovery_gap_ms'] = [Math]::Round($RecoveryGapMs, 1)
}

function Get-MonitorIntegrityStatus {
    param(
        [int]$ErrorCount,
        [int]$RecoveredErrorCount,
        [int]$UnrecoveredErrorCount,
        [double]$PollGapMaxMs,
        [double]$WarningThresholdMs
    )

    if ($ErrorCount -eq 0) {
        return 'complete-no-errors'
    }
    if ($UnrecoveredErrorCount -gt 0 -or
        $RecoveredErrorCount -ne $ErrorCount) {
        return 'incomplete-unrecovered-errors'
    }
    if ($PollGapMaxMs -gt $WarningThresholdMs) {
        return 'incomplete-detection-gap'
    }
    return 'complete-recovered-transient-errors'
}

function Get-PercentileValue {
    param(
        [double[]]$Values,
        [ValidateRange(0.0, 1.0)]
        [double]$Percentile
    )

    if ($null -eq $Values -or $Values.Count -eq 0) {
        return $null
    }
    $ordered = @($Values | Sort-Object)
    $index = [Math]::Max(
        0,
        [Math]::Min(
            $ordered.Count - 1,
            [int][Math]::Ceiling($Percentile * $ordered.Count) - 1
        )
    )
    return [double]$ordered[$index]
}

function Get-DetectionQuality {
    param(
        [object]$DetectionLatencyMs,
        [int]$WarningThresholdMs
    )

    if ($null -eq $DetectionLatencyMs) {
        return 'not-applicable'
    }
    if ([double]$DetectionLatencyMs -gt $WarningThresholdMs) {
        return 'degraded'
    }
    return 'within-threshold'
}

function Write-AtomicJson {
    param(
        [string]$Path,
        [object]$Value,
        [int]$Depth = 12
    )

    $parent = Split-Path -Parent $Path
    if ([string]::IsNullOrWhiteSpace($parent)) {
        throw 'Atomic JSON output must have a parent directory.'
    }
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $temporaryPath = '{0}.{1}.tmp' -f $Path, [guid]::NewGuid().ToString('N')
    $pathLimitChars = 240
    if ($temporaryPath.Length -gt $pathLimitChars) {
        throw (
            'The trigger evidence path exceeds the Windows PowerShell safe limit. ' +
            'chars={0} limit={1}' -f $temporaryPath.Length, $pathLimitChars
        )
    }
    try {
        $Value | ConvertTo-Json -Depth $Depth |
            Set-Content -LiteralPath $temporaryPath -Encoding utf8
        Move-Item -LiteralPath $temporaryPath -Destination $Path
    } finally {
        if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
    }
}

function Read-ObserverCompletionRequest {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or
        -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    $request = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 |
        ConvertFrom-Json
    if ($request.schema_version -cne
            'spot-trigger-monitor-completion-request-v1' -or
        [string]::IsNullOrWhiteSpace([string]$request.request_id) -or
        $request.reason -cne 'observation-deadline-reached' -or
        [string]::IsNullOrWhiteSpace([string]$request.observation_ended_at)) {
        throw 'The observer completion request contract is invalid.'
    }
    $observationEndedAt = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse(
            [string]$request.observation_ended_at,
            [ref]$observationEndedAt
        )) {
        throw 'The observer completion request timestamp is invalid.'
    }
    return [pscustomobject][ordered]@{
        request_id = [string]$request.request_id
        requested_at = [string]$request.requested_at
        observation_ended_at = $observationEndedAt
        reason = [string]$request.reason
        request_source = if (
            $null -eq $request.PSObject.Properties['request_source']
        ) {
            'legacy-child-normal-observer'
        } else {
            [string]$request.request_source
        }
    }
}

function ConvertTo-CompactPollRecord {
    param(
        [int]$Sample,
        [object]$Result,
        [object]$Body,
        [object]$TriggerState,
        [string]$BodySha256,
        [double]$PollGapMs
    )

    $summary = Get-PropertyValue -Object $Body -Name 'summary'
    return [ordered]@{
        schema_version = 'observability-error-poll-compact-v2'
        sample = $Sample
        request_started_at = $Result.request_started_at
        collected_at = $Result.request_completed_at
        request_elapsed_ms = $Result.request_elapsed_ms
        poll_gap_ms = [Math]::Round($PollGapMs, 1)
        response_status = $Result.status_code
        ok = [bool]$Result.ok
        error = $Result.error
        body_sha256 = $BodySha256
        queue_size = Get-PropertyValue -Object $summary -Name 'queue_size'
        repeat_total = Get-PropertyValue -Object $summary -Name 'repeat_total'
        spot_connecttimeout_item_count = if ($null -eq $TriggerState) {
            $null
        } else {
            [int]$TriggerState.ItemCount
        }
        spot_connecttimeout_repeat_total = if ($null -eq $TriggerState) {
            $null
        } else {
            [int]$TriggerState.RepeatTotal
        }
        spot_connecttimeout_latest_error_at = if (
            $null -eq $TriggerState -or
            $null -eq $TriggerState.LatestErrorAt
        ) {
            $null
        } else {
            $TriggerState.LatestErrorAt.ToString('o')
        }
    }
}

function Invoke-SelfTest {
    $baselineBody = [pscustomobject]@{
        items = @(
            [pscustomobject]@{
                source = 'spot_image'
                error_type = 'ConnectTimeout'
                repeat = 98
                time_iso = '2026-07-24T00:00:00+00:00'
            }
        )
    }
    $currentBody = [pscustomobject]@{
        items = @(
            [pscustomobject]@{
                source = 'spot_image'
                error_type = 'ConnectTimeout'
                repeat = 99
                time_iso = '2026-07-24T00:01:00+00:00'
                message = 'must-not-be-retained'
            }
        )
        summary = [pscustomobject]@{
            queue_size = 1
            repeat_total = 99
        }
    }
    $baseline = Get-SpotConnectTimeoutTriggerState -Body $baselineBody
    $current = Get-SpotConnectTimeoutTriggerState -Body $currentBody
    if (-not (Test-NewSpotConnectTimeout -Baseline $baseline -Current $current)) {
        throw 'Self-test failed: new ConnectTimeout was not detected.'
    }
    if ((Get-DetectionQuality -DetectionLatencyMs 5001 -WarningThresholdMs 5000) -ne
        'degraded') {
        throw 'Self-test failed: detection latency warning.'
    }
    $result = [pscustomobject]@{
        request_started_at = '2026-07-24T00:01:01+00:00'
        request_completed_at = '2026-07-24T00:01:01.050+00:00'
        request_elapsed_ms = 50.0
        status_code = 200
        ok = $true
        error = $null
    }
    $compact = ConvertTo-CompactPollRecord `
        -Sample 1 `
        -Result $result `
        -Body $currentBody `
        -TriggerState $current `
        -BodySha256 ('a' * 64) `
        -PollGapMs 1000
    $serialized = $compact | ConvertTo-Json -Compress
    if ($serialized -match 'must-not-be-retained' -or
        $compact.schema_version -ne 'observability-error-poll-compact-v2' -or
        [double]$compact.request_elapsed_ms -ne 50) {
        throw 'Self-test failed: compact polling contract.'
    }

    $failureResult = [pscustomobject]@{
        request_started_at = '2026-07-24T00:01:02+00:00'
        request_completed_at = '2026-07-24T00:01:03.250+00:00'
        request_elapsed_ms = 1250.0
        status_code = 0
        ok = $false
        error = 'MethodInvocationException'
        error_type = 'System.Management.Automation.MethodInvocationException'
        error_message = 'synthetic read failure'
        fully_qualified_error_id = 'SyntheticFailure'
        error_category = 'NotSpecified'
        error_hresult = -1
        script_stack_trace = 'self-test'
    }
    $errorEvent = New-MonitorErrorEvent `
        -Sample 2 `
        -Result $failureResult `
        -PollGapMs 1001 `
        -ConsecutiveErrorCount 1
    Complete-MonitorErrorEvent `
        -Event $errorEvent `
        -RecoveredAt ([DateTimeOffset]'2026-07-24T00:01:04+00:00') `
        -RecoveryGapMs 2000
    $integrity = Get-MonitorIntegrityStatus `
        -ErrorCount 1 `
        -RecoveredErrorCount 1 `
        -UnrecoveredErrorCount 0 `
        -PollGapMaxMs 2000 `
        -WarningThresholdMs 5000
    if ($errorEvent.schema_version -cne
            'spot-trigger-monitor-error-event-raw-v1' -or
        $errorEvent.error_message -cne 'synthetic read failure' -or
        $errorEvent.fully_qualified_error_id -cne 'SyntheticFailure' -or
        -not [bool]$errorEvent.recovered -or
        $integrity -cne 'complete-recovered-transient-errors') {
        throw 'Self-test failed: monitor error evidence contract.'
    }

    $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $tempRoot = Join-Path $tempBase (
        'sfl-trigger-monitor-selftest-{0}' -f [guid]::NewGuid().ToString('N')
    )
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    try {
        $completionPath = Join-Path $tempRoot 'completion-request.json'
        [ordered]@{
            schema_version = 'spot-trigger-monitor-completion-request-v1'
            request_id = [guid]::NewGuid().ToString('N')
            requested_at = '2026-07-24T00:15:00.100+00:00'
            observation_ended_at = '2026-07-24T00:15:00+00:00'
            reason = 'observation-deadline-reached'
            request_source = 'parent-authoritative-observation-boundary'
        } | ConvertTo-Json -Depth 4 |
            Set-Content -LiteralPath $completionPath -Encoding utf8
        $completion = Read-ObserverCompletionRequest -Path $completionPath
        if ($null -eq $completion -or
            $completion.reason -cne 'observation-deadline-reached' -or
            $completion.request_source -cne
                'parent-authoritative-observation-boundary' -or
            $completion.observation_ended_at.ToString('o') -cne
                '2026-07-24T00:15:00.0000000+00:00') {
            throw 'Self-test failed: observer completion request contract.'
        }
    } finally {
        $resolvedTempRoot = [IO.Path]::GetFullPath($tempRoot)
        if (-not $resolvedTempRoot.StartsWith(
                $tempBase,
                [StringComparison]::OrdinalIgnoreCase
            )) {
            throw 'Unsafe trigger monitor self-test cleanup path.'
        }
        Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force
    }
    Write-Output (
        'TRIGGER_MONITOR_SELF_TEST_PASS independent=true compact_v2=true ' +
        'latency_warning=true completion_request=true'
    )
}

if ($SelfTest) {
    Invoke-SelfTest
    exit 0
}

if ([string]::IsNullOrWhiteSpace($RawRoot) -or
    -not (Test-Path -LiteralPath $RawRoot -PathType Container)) {
    throw 'RawRoot must be an existing private evidence folder.'
}
if ([string]::IsNullOrWhiteSpace($CaptureStopSignalPath)) {
    throw 'CaptureStopSignalPath is required.'
}
if ([string]::IsNullOrWhiteSpace($CompletionRequestPath)) {
    throw 'CompletionRequestPath is required.'
}
$resolvedRawRoot = (Resolve-Path -LiteralPath $RawRoot).Path
$resolvedSignalPath = [IO.Path]::GetFullPath($CaptureStopSignalPath)
$resolvedCompletionRequestPath = [IO.Path]::GetFullPath($CompletionRequestPath)
$rawRootPrefix = $resolvedRawRoot.TrimEnd('\') + '\'
$signalParent = Split-Path -Parent $resolvedSignalPath
if (-not (Test-Path -LiteralPath $signalParent -PathType Container)) {
    throw 'The capture stop signal parent folder does not exist.'
}
if (Test-Path -LiteralPath $resolvedSignalPath) {
    throw 'The capture stop signal already exists.'
}
$completionRequestParent = Split-Path -Parent $resolvedCompletionRequestPath
if (-not (Test-Path -LiteralPath $completionRequestParent -PathType Container)) {
    throw 'The observer completion request parent folder does not exist.'
}
if (-not $resolvedCompletionRequestPath.StartsWith(
        $rawRootPrefix,
        [StringComparison]::OrdinalIgnoreCase
    )) {
    throw 'CompletionRequestPath must be inside RawRoot.'
}

$errorUri = Join-ApiUrl `
    -Base $ApiBase `
    -Path '/api/observability/errors?limit=200'
$baselineResult = Invoke-BoundedReadOnlyEndpoint `
    -Uri $errorUri `
    -TimeoutMs $RequestTimeoutMs
$baselineBody = if ([bool]$baselineResult.ok) {
    ConvertFrom-JsonOrNull -Text ([string]$baselineResult.body)
} else {
    $null
}
if ($null -eq $baselineBody) {
    throw 'The dedicated ConnectTimeout monitor could not read its baseline.'
}

$baselineState = Get-SpotConnectTimeoutTriggerState -Body $baselineBody
$currentState = $baselineState
$baselineEnvelope = [ordered]@{
    sample = 0
    endpoint = 'observability_errors'
    path = '/api/observability/errors?limit=200'
    collected_at = $baselineResult.request_completed_at
    status_code = $baselineResult.status_code
    ok = $baselineResult.ok
    error = $baselineResult.error
    body = $baselineResult.body
}
$baselinePath = Join-Path $resolvedRawRoot 'trigger_baseline_observability_errors.json'
Write-AtomicJson -Path $baselinePath -Value $baselineEnvelope

$compactPath = Join-Path $resolvedRawRoot 'trigger_observability_errors_compact.jsonl'
$summaryPath = Join-Path $resolvedRawRoot 'trigger_monitor_summary.json'
$finalPath = Join-Path $resolvedRawRoot 'trigger_final_observability_errors.json'
$writer = [IO.StreamWriter]::new(
    $compactPath,
    $false,
    [Text.UTF8Encoding]::new($false)
)
$startedAt = [DateTimeOffset]::Now
$deadlineAt = $startedAt.AddSeconds(
    [double]$DurationSec + [double]$CompletionRequestGraceSec
)
$nextPollAt = $startedAt
$lastPollStartedAt = $null
$latestFullEnvelope = $baselineEnvelope
$lastPersistedBodySha256 = New-Sha256Text -Text ([string]$baselineResult.body)
$pollCount = 0
$pollErrorCount = 0
$recoveredPollErrorCount = 0
$consecutivePollErrorCount = 0
$maxConsecutivePollErrorCount = 0
$monitorErrorEvents = [Collections.Generic.List[object]]::new()
$pendingMonitorErrorEvents = [Collections.Generic.List[object]]::new()
$changeSnapshotCount = 0
$fullSnapshotCount = 1
$triggerDetected = $false
$triggerDetectedAt = $null
$completionRequest = $null
$completionRequestObservedAt = $null
$requestElapsedValues = [Collections.Generic.List[double]]::new()
$pollGapValues = [Collections.Generic.List[double]]::new()

Write-Output (
    '[TRIGGER] Dedicated monitor baseline fixed: items={0}, repeats={1}.' -f
        $baselineState.ItemCount,
        $baselineState.RepeatTotal
)

try {
    while ([DateTimeOffset]::Now -lt $deadlineAt) {
        if ($null -eq $completionRequest) {
            $completionRequest = Read-ObserverCompletionRequest `
                -Path $resolvedCompletionRequestPath
            if ($null -ne $completionRequest) {
                $completionRequestObservedAt = [DateTimeOffset]::Now
            }
        }
        $pollStartedAt = [DateTimeOffset]::Now
        $pollGapMs = if ($null -eq $lastPollStartedAt) {
            0.0
        } else {
            ($pollStartedAt - $lastPollStartedAt).TotalMilliseconds
        }
        $lastPollStartedAt = $pollStartedAt
        $pollGapValues.Add([double]$pollGapMs)
        $pollCount += 1

        $result = Invoke-BoundedReadOnlyEndpoint `
            -Uri $errorUri `
            -TimeoutMs $RequestTimeoutMs
        $requestElapsedValues.Add([double]$result.request_elapsed_ms)
        $body = if ([bool]$result.ok) {
            ConvertFrom-JsonOrNull -Text ([string]$result.body)
        } else {
            $null
        }
        $bodySha256 = if ($null -eq $body) {
            $null
        } else {
            New-Sha256Text -Text ([string]$result.body)
        }
        if ($null -eq $body) {
            $pollErrorCount += 1
            $consecutivePollErrorCount += 1
            $maxConsecutivePollErrorCount = [Math]::Max(
                $maxConsecutivePollErrorCount,
                $consecutivePollErrorCount
            )
            $errorEvent = New-MonitorErrorEvent `
                -Sample $pollCount `
                -Result $result `
                -PollGapMs $pollGapMs `
                -ConsecutiveErrorCount $consecutivePollErrorCount
            $monitorErrorEvents.Add($errorEvent)
            $pendingMonitorErrorEvents.Add($errorEvent)
        } else {
            if ($pendingMonitorErrorEvents.Count -gt 0) {
                $recoveredAt = [DateTimeOffset]::Parse(
                    [string]$result.request_completed_at
                )
                foreach ($pendingErrorEvent in @($pendingMonitorErrorEvents)) {
                    $failedAt = [DateTimeOffset]::Parse(
                        [string]$pendingErrorEvent.request_started_at
                    )
                    Complete-MonitorErrorEvent `
                        -Event $pendingErrorEvent `
                        -RecoveredAt $recoveredAt `
                        -RecoveryGapMs (($recoveredAt - $failedAt).TotalMilliseconds)
                    $recoveredPollErrorCount += 1
                }
                $pendingMonitorErrorEvents.Clear()
            }
            $consecutivePollErrorCount = 0
            $currentState = Get-SpotConnectTimeoutTriggerState -Body $body
            $envelope = [ordered]@{
                sample = $pollCount
                endpoint = 'observability_errors'
                path = '/api/observability/errors?limit=200'
                collected_at = $result.request_completed_at
                status_code = $result.status_code
                ok = $result.ok
                error = $result.error
                body = $result.body
            }
            $latestFullEnvelope = $envelope
            if ($bodySha256 -cne $lastPersistedBodySha256) {
                $changeSnapshotCount += 1
                $changePath = Join-Path $resolvedRawRoot (
                    'trigger_change_{0:d4}_observability_errors.json' -f
                        $changeSnapshotCount
                )
                Write-AtomicJson -Path $changePath -Value $envelope
                $lastPersistedBodySha256 = $bodySha256
                $fullSnapshotCount += 1
            }
            if (Test-NewSpotConnectTimeout `
                -Baseline $baselineState `
                -Current $currentState) {
                $triggerDetected = $true
                $triggerDetectedAt = [DateTimeOffset]::Now
            }
        }

        $compact = ConvertTo-CompactPollRecord `
            -Sample $pollCount `
            -Result $result `
            -Body $body `
            -TriggerState $(if ($null -eq $body) { $null } else { $currentState }) `
            -BodySha256 $bodySha256 `
            -PollGapMs $pollGapMs
        $writer.WriteLine(($compact | ConvertTo-Json -Compress))
        $writer.Flush()

        if ($triggerDetected) {
            break
        }
        if ($null -eq $completionRequest) {
            $completionRequest = Read-ObserverCompletionRequest `
                -Path $resolvedCompletionRequestPath
        }
        if ($null -ne $completionRequest) {
            if ($null -eq $completionRequestObservedAt) {
                $completionRequestObservedAt = [DateTimeOffset]::Now
            }
            break
        }
        $nextPollAt = $nextPollAt.AddMilliseconds($PollIntervalMs)
        $now = [DateTimeOffset]::Now
        while ($nextPollAt -le $now) {
            $nextPollAt = $nextPollAt.AddMilliseconds($PollIntervalMs)
        }
        $sleepMs = [int][Math]::Floor(($nextPollAt - $now).TotalMilliseconds)
        if ($sleepMs -gt 0) {
            Start-Sleep -Milliseconds $sleepMs
        }
    }
} finally {
    $writer.Flush()
    $writer.Dispose()
}

$endedAt = [DateTimeOffset]::Now
Write-AtomicJson -Path $finalPath -Value $latestFullEnvelope
$fullSnapshotCount += 1
$triggerErrorAt = if (
    -not $triggerDetected -or
    $null -eq $currentState.LatestErrorAt
) {
    $null
} else {
    [DateTimeOffset]$currentState.LatestErrorAt
}
$detectionLatencyMs = if (
    $null -eq $triggerDetectedAt -or
    $null -eq $triggerErrorAt
) {
    $null
} else {
    [Math]::Max(
        0,
        [Math]::Round(
            ($triggerDetectedAt - $triggerErrorAt).TotalMilliseconds,
            1
        )
    )
}
$detectionQuality = Get-DetectionQuality `
    -DetectionLatencyMs $detectionLatencyMs `
    -WarningThresholdMs $DetectionLatencyWarningMs
$pollGapMaxMs = if ($pollGapValues.Count -eq 0) {
    $null
} else {
    [double](($pollGapValues | Measure-Object -Maximum).Maximum)
}
$requestElapsedMaxMs = if ($requestElapsedValues.Count -eq 0) {
    $null
} else {
    [double](($requestElapsedValues | Measure-Object -Maximum).Maximum)
}
$unrecoveredPollErrorCount = $pendingMonitorErrorEvents.Count
$monitorIntegrityStatus = Get-MonitorIntegrityStatus `
    -ErrorCount $pollErrorCount `
    -RecoveredErrorCount $recoveredPollErrorCount `
    -UnrecoveredErrorCount $unrecoveredPollErrorCount `
    -PollGapMaxMs $(if ($null -eq $pollGapMaxMs) { 0 } else { $pollGapMaxMs }) `
    -WarningThresholdMs $DetectionLatencyWarningMs
$monitorErrorEventsPath = Join-Path `
    $resolvedRawRoot `
    'trigger_monitor_error_events_raw.json'
[ordered]@{
    schema_version = 'spot-trigger-monitor-error-events-raw-v1'
    generated_at = [DateTimeOffset]::Now.ToString('o')
    error_count = $pollErrorCount
    recovered_error_count = $recoveredPollErrorCount
    unrecovered_error_count = $unrecoveredPollErrorCount
    events = @($monitorErrorEvents)
} | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath $monitorErrorEventsPath -Encoding utf8
$monitorSummary = [ordered]@{
    schema_version = 'spot-connecttimeout-trigger-monitor-v1'
    monitor_mode = 'dedicated-background-job'
    started_at = $startedAt.ToString('o')
    deadline_at = $deadlineAt.ToString('o')
    ended_at = $endedAt.ToString('o')
    stop_reason = if ($triggerDetected) {
        'spot-connect-timeout-detected'
    } elseif ($null -ne $completionRequest) {
        'observation-completion-requested'
    } else {
        'completion-request-timeout-without-trigger'
    }
    trigger_detected = $triggerDetected
    trigger_detected_at = if ($null -eq $triggerDetectedAt) {
        $null
    } else {
        $triggerDetectedAt.ToString('o')
    }
    trigger_error_at = if ($null -eq $triggerErrorAt) {
        $null
    } else {
        $triggerErrorAt.ToString('o')
    }
    trigger_detection_latency_ms = $detectionLatencyMs
    trigger_detection_latency_warning_ms = $DetectionLatencyWarningMs
    trigger_detection_quality = $detectionQuality
    trigger_detection_latency_exceeded = ($detectionQuality -eq 'degraded')
    baseline_item_count = [int]$baselineState.ItemCount
    baseline_repeat_total = [int]$baselineState.RepeatTotal
    observed_item_count = [int]$currentState.ItemCount
    observed_repeat_total = [int]$currentState.RepeatTotal
    repeat_delta = [Math]::Max(
        0,
        [int]$currentState.RepeatTotal - [int]$baselineState.RepeatTotal
    )
    poll_interval_ms = $PollIntervalMs
    request_timeout_ms = $RequestTimeoutMs
    completion_request_schema = 'spot-trigger-monitor-completion-request-v1'
    completion_request_grace_sec = $CompletionRequestGraceSec
    completion_request_observed = ($null -ne $completionRequest)
    completion_request_id = if ($null -eq $completionRequest) {
        $null
    } else {
        $completionRequest.request_id
    }
    completion_request_source = if ($null -eq $completionRequest) {
        $null
    } else {
        $completionRequest.request_source
    }
    completion_request_observed_at = if (
        $null -eq $completionRequestObservedAt
    ) {
        $null
    } else {
        $completionRequestObservedAt.ToString('o')
    }
    requested_observation_ended_at = if ($null -eq $completionRequest) {
        $null
    } else {
        $completionRequest.observation_ended_at.ToString('o')
    }
    monitor_poll_count = $pollCount
    monitor_error_count = $pollErrorCount
    monitor_recovered_error_count = $recoveredPollErrorCount
    monitor_unrecovered_error_count = $unrecoveredPollErrorCount
    monitor_max_consecutive_error_count = $maxConsecutivePollErrorCount
    monitor_integrity_policy =
        'recovered-errors-within-detection-threshold-are-complete'
    monitor_integrity_status = $monitorIntegrityStatus
    monitor_error_event_schema = 'spot-trigger-monitor-error-event-raw-v1'
    compact_poll_schema = 'observability-error-poll-compact-v2'
    compact_poll_count = $pollCount
    full_snapshot_policy = 'baseline-change-trigger-final'
    full_snapshot_count = $fullSnapshotCount
    change_snapshot_count = $changeSnapshotCount
    poll_gap_ms_p95 = Get-PercentileValue `
        -Values ([double[]]$pollGapValues.ToArray()) `
        -Percentile 0.95
    poll_gap_ms_max = $pollGapMaxMs
    request_elapsed_ms_p95 = Get-PercentileValue `
        -Values ([double[]]$requestElapsedValues.ToArray()) `
        -Percentile 0.95
    request_elapsed_ms_max = $requestElapsedMaxMs
}
Write-AtomicJson -Path $summaryPath -Value $monitorSummary

$captureStopSignal = [ordered]@{
    schema_version = 'spot-connecttimeout-capture-stop-v1'
    stop_reason = $monitorSummary.stop_reason
    trigger_detected = $triggerDetected
    trigger_source = if ($triggerDetected) { 'spot_image' } else { $null }
    trigger_error_type = if ($triggerDetected) { 'ConnectTimeout' } else { $null }
    trigger_detected_at = $monitorSummary.trigger_detected_at
    trigger_error_at = $monitorSummary.trigger_error_at
    trigger_detection_latency_ms = $detectionLatencyMs
    trigger_detection_latency_warning_ms = $DetectionLatencyWarningMs
    trigger_detection_quality = $detectionQuality
    trigger_detection_latency_exceeded = ($detectionQuality -eq 'degraded')
    baseline_item_count = [int]$baselineState.ItemCount
    baseline_repeat_total = [int]$baselineState.RepeatTotal
    observed_item_count = [int]$currentState.ItemCount
    observed_repeat_total = [int]$currentState.RepeatTotal
    repeat_delta = $monitorSummary.repeat_delta
    monitor_mode = 'dedicated-background-job'
    monitor_poll_interval_ms = $PollIntervalMs
    monitor_poll_count = $pollCount
    monitor_error_count = $pollErrorCount
    monitor_recovered_error_count = $recoveredPollErrorCount
    monitor_unrecovered_error_count = $unrecoveredPollErrorCount
    monitor_max_consecutive_error_count = $maxConsecutivePollErrorCount
    monitor_integrity_policy = $monitorSummary.monitor_integrity_policy
    monitor_integrity_status = $monitorIntegrityStatus
    monitor_poll_gap_ms_max = $pollGapMaxMs
    completion_request_id = $monitorSummary.completion_request_id
    completion_request_source = $monitorSummary.completion_request_source
    completion_request_observed_at =
        $monitorSummary.completion_request_observed_at
    collection_ended_at = if ($null -eq $completionRequest) {
        $endedAt.ToString('o')
    } else {
        $completionRequest.observation_ended_at.ToString('o')
    }
}
Write-AtomicJson -Path $resolvedSignalPath -Value $captureStopSignal

if ($detectionQuality -eq 'degraded') {
    Write-Warning (
        'ConnectTimeout detection latency {0}ms exceeded the {1}ms evidence-quality threshold.' -f
            $detectionLatencyMs,
            $DetectionLatencyWarningMs
    )
}
Write-Output (
    'TRIGGER_MONITOR_RESULT detected={0} polls={1} errors={2} quality={3}' -f
        $triggerDetected,
        $pollCount,
        $pollErrorCount,
        $detectionQuality
)
