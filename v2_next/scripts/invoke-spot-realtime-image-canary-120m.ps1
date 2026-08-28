[CmdletBinding()]
param(
    [string]$KitRoot = "",

    [string]$ReleaseKitRoot = "",

    [string]$RollbackInstallerPath = (
        "C:\Users\user\Desktop\SmartFactory\" +
        "v1020_cd8cfa6_internal_private_server_deploy_20260821_R3\" +
        "smart-factory-logger-v2 Setup 1.0.20.exe"
    ),

    [string]$RuntimeEvidenceBase = "",

    [switch]$PreflightOnly,

    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RequiredProperty {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$Context
    )

    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value) {
        throw "$Context required property missing: $Name"
    }
    return $property.Value
}

function Get-OptionalProperty {
    param(
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $InputObject) {
        return $null
    }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Assert-FileSha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedSha256,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label file missing: $Path"
    }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    if ($actual -cne $ExpectedSha256.ToUpperInvariant()) {
        throw "$Label SHA256 mismatch"
    }
    return $actual
}

function Assert-RollbackBaselineEvidence {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Identity,

        [Parameter(Mandatory = $true)]
        [object]$PreinstallSummary,

        [Parameter(Mandatory = $true)]
        [object]$BaselineHealth
    )

    $rollbackVersion = [string](Get-RequiredProperty `
        -InputObject $Identity.rollback `
        -Name "version" `
        -Context "rollback identity")
    $rollbackCommit = [string](Get-RequiredProperty `
        -InputObject $Identity.rollback `
        -Name "build_git_commit" `
        -Context "rollback identity")
    $preinstallVersion = [string](Get-RequiredProperty `
        -InputObject $PreinstallSummary `
        -Name "current_version" `
        -Context "preinstall summary")
    $healthVersion = [string](Get-RequiredProperty `
        -InputObject $BaselineHealth `
        -Name "app_version" `
        -Context "baseline health")
    $spotTemperature = Get-RequiredProperty `
        -InputObject $BaselineHealth `
        -Name "spot_temperature" `
        -Context "baseline health"
    $healthCommit = [string](Get-RequiredProperty `
        -InputObject $spotTemperature `
        -Name "build_git_commit" `
        -Context "baseline health spot_temperature")

    if ($rollbackVersion -ceq [string]$Identity.product.version) {
        throw "rollback version must differ from the v1.0.21 candidate"
    }
    if ($preinstallVersion -cne $rollbackVersion) {
        throw "rollback version does not match the preinstall baseline"
    }
    if ($healthVersion -cne $rollbackVersion) {
        throw "rollback version does not match baseline health"
    }
    if ($healthCommit -cne $rollbackCommit) {
        throw "rollback commit does not match baseline health"
    }
}

function Get-CounterWindowElapsedSeconds {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Before,

        [Parameter(Mandatory = $true)]
        [object]$After
    )

    $beforeText = [string](Get-OptionalProperty $Before "observed_at_completed")
    if ([string]::IsNullOrWhiteSpace($beforeText)) {
        $beforeText = [string](Get-RequiredProperty `
            -InputObject $Before `
            -Name "observed_at" `
            -Context "observation start state")
    }
    $afterText = [string](Get-OptionalProperty $After "observed_at_completed")
    if ([string]::IsNullOrWhiteSpace($afterText)) {
        $afterText = [string](Get-RequiredProperty `
            -InputObject $After `
            -Name "observed_at" `
            -Context "observation end state")
    }
    $culture = [Globalization.CultureInfo]::InvariantCulture
    $styles = [Globalization.DateTimeStyles]::RoundtripKind
    $beforeAt = [DateTimeOffset]::Parse($beforeText, $culture, $styles)
    $afterAt = [DateTimeOffset]::Parse($afterText, $culture, $styles)
    $elapsedSeconds = ($afterAt - $beforeAt).TotalSeconds
    if ($elapsedSeconds -le 0) {
        throw "invalid SPOT counter observation window"
    }
    return [double]$elapsedSeconds
}

function Get-CollectorEvidenceHolds {
    param(
        [Parameter(Mandatory = $true)]
        [object]$FieldSummary,

        [Parameter(Mandatory = $true)]
        [int]$CollectorExitCode
    )

    $holds = New-Object System.Collections.Generic.List[string]
    if ($CollectorExitCode -notin @(0, 2)) {
        [void]$holds.Add("collector-exit-$CollectorExitCode")
    }
    $statusProperty = $FieldSummary.PSObject.Properties["status"]
    if ($null -eq $statusProperty -or $null -eq $statusProperty.Value) {
        [void]$holds.Add("collector-status-missing")
    } elseif ([string]$statusProperty.Value -notin @("COMPLETED", "PARTIAL")) {
        [void]$holds.Add(
            "collector-status-$([string]$statusProperty.Value)".ToLowerInvariant()
        )
    }
    return @($holds.ToArray())
}

function Test-SwitchEvidenceLimitation {
    param(
        [Parameter(Mandatory = $true)]
        [object]$FieldSummary
    )

    $unavailable = $FieldSummary.PSObject.Properties[
        "switch_evidence_unavailable_declared"
    ]
    if ($null -ne $unavailable -and [bool]$unavailable.Value) {
        return $true
    }
    $switchStatus = $FieldSummary.PSObject.Properties["switch_evidence_status"]
    if ($null -ne $switchStatus -and
        [string]$switchStatus.Value -notin @("complete", "completed")) {
        return $true
    }
    return [string]$FieldSummary.status -ceq "PARTIAL"
}

function Test-OperatorVisualConfirmationEligible {
    param(
        [Parameter(Mandatory = $true)]
        [object]$FieldSummary,

        [double]$MinimumElapsedSeconds = 7190.0
    )

    $elapsed = $FieldSummary.PSObject.Properties["observation_elapsed_seconds"]
    if ($null -eq $elapsed -or $null -eq $elapsed.Value) {
        return $false
    }
    return [double]$elapsed.Value -ge $MinimumElapsedSeconds
}

function Get-CanaryExceptionResultName {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$CollectionStarted,

        [Parameter(Mandatory = $true)]
        [string]$Phase
    )

    if (-not $CollectionStarted) {
        return "SPOT_120M_PREFLIGHT_FAILED"
    }
    return "SPOT_120M_EVIDENCE_HOLD"
}

function ConvertTo-SafeImageSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Image
    )

    $names = @(
        "source_port_policy_version",
        "source_port_enforcement_supported",
        "source_port_enforcement_active",
        "source_port_pool_capacity",
        "source_port_pool_guarded_count",
        "source_port_pool_leased_count",
        "source_port_pool_quarantined_count",
        "source_port_pool_rebind_pending_count",
        "source_port_pool_acquire_wait_count",
        "source_port_pool_exhaustion_count",
        "source_port_rebind_retry_count",
        "source_port_reuse_violation_count",
        "source_port_minimum_reuse_interval_seconds",
        "source_port_transport_started_count",
        "source_port_transport_success_count",
        "source_port_transport_failure_count",
        "source_port_bind_collision_count",
        "source_port_image_failure_count",
        "source_port_temperature_failure_count",
        "source_port_internal_temperature_failure_count",
        "source_port_diagnostic_failure_count",
        "source_port_connection_test_failure_count",
        "source_port_request_event_count_total",
        "source_port_request_event_drop_count",
        "source_port_request_failure_event_count_total",
        "source_port_request_failure_event_drop_count",
        "request_budget_within_target",
        "request_budget_total_background_max_per_sec",
        "image_upstream_request_count",
        "image_refresh_success_count",
        "image_refresh_failure_count",
        "image_cache_clock_anomaly_count"
    )
    $snapshot = [ordered]@{}
    foreach ($name in $names) {
        $snapshot[$name] = Get-RequiredProperty `
            -InputObject $Image `
            -Name $name `
            -Context "SPOT image diagnostics"
    }
    $snapshot["source_port_recent_request_failure_events"] = @(
        foreach ($event in @(
            Get-RequiredProperty `
                -InputObject $Image `
                -Name "source_port_recent_request_failure_events" `
                -Context "SPOT image diagnostics"
        )) {
            [pscustomobject][ordered]@{
                event_sequence = Get-OptionalProperty $event "event_sequence"
                event_at_utc = Get-OptionalProperty $event "event_at_utc"
                request_kind = Get-OptionalProperty $event "request_kind"
                state = Get-OptionalProperty $event "state"
                exception_class = Get-OptionalProperty $event "exception_class"
            }
        }
    )
    return [pscustomobject]$snapshot
}

function Get-CumulativeFailureCounterNames {
    return @(
        "source_port_pool_acquire_wait_count",
        "source_port_pool_exhaustion_count",
        "source_port_reuse_violation_count",
        "source_port_transport_failure_count",
        "source_port_image_failure_count",
        "source_port_temperature_failure_count",
        "source_port_internal_temperature_failure_count",
        "source_port_diagnostic_failure_count",
        "source_port_connection_test_failure_count",
        "source_port_request_failure_event_count_total",
        "source_port_request_failure_event_drop_count",
        "image_refresh_failure_count",
        "image_cache_clock_anomaly_count"
    )
}

function Get-CumulativeFailureCounterSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Image
    )

    $snapshot = [ordered]@{}
    foreach ($name in @(Get-CumulativeFailureCounterNames)) {
        $snapshot[$name] = [int64](Get-RequiredProperty `
            -InputObject $Image `
            -Name $name `
            -Context "SPOT cumulative failure counters")
    }
    return [pscustomobject]$snapshot
}

function Assert-FailureCounterDeltas {
    param(
        [Parameter(Mandatory = $true)]
        [object]$BeforeImage,

        [Parameter(Mandatory = $true)]
        [object]$AfterImage,

        [Parameter(Mandatory = $true)]
        [string]$Stage
    )

    $deltas = [ordered]@{}
    foreach ($name in @(Get-CumulativeFailureCounterNames)) {
        $beforeValue = [int64](Get-RequiredProperty `
            -InputObject $BeforeImage `
            -Name $name `
            -Context "$Stage baseline counters")
        $afterValue = [int64](Get-RequiredProperty `
            -InputObject $AfterImage `
            -Name $name `
            -Context "$Stage ending counters")
        $delta = $afterValue - $beforeValue
        $deltas[$name] = $delta

        if ($delta -lt 0) {
            throw (
                "SPOT failure counter decreased during canary: " +
                "stage=$Stage field=$name before=$beforeValue " +
                "after=$afterValue delta=$delta"
            )
        }
        if ($delta -gt 0) {
            throw (
                "SPOT failure counter increased during canary: " +
                "stage=$Stage field=$name before=$beforeValue " +
                "after=$afterValue delta=$delta"
            )
        }
    }
    return [pscustomobject]$deltas
}

function Get-FailureCounterDeltaReport {
    param(
        [Parameter(Mandatory = $true)]
        [object]$BeforeImage,
        [Parameter(Mandatory = $true)]
        [object]$AfterImage
    )

    $deltas = [ordered]@{}
    $hardFailures = New-Object System.Collections.Generic.List[string]
    $holds = New-Object System.Collections.Generic.List[string]
    foreach ($name in @(Get-CumulativeFailureCounterNames)) {
        $beforeValue = [int64](Get-RequiredProperty `
            -InputObject $BeforeImage `
            -Name $name `
            -Context "observation start counters")
        $afterValue = [int64](Get-RequiredProperty `
            -InputObject $AfterImage `
            -Name $name `
            -Context "observation end counters")
        $delta = $afterValue - $beforeValue
        $deltas[$name] = $delta
        if ($delta -lt 0) {
            [void]$holds.Add("counter-decreased:$name")
        } elseif ($delta -gt 0) {
            [void]$hardFailures.Add(
                "failure-counter-increased:${name}:$delta"
            )
        }
    }
    return [pscustomobject][ordered]@{
        deltas = [pscustomobject]$deltas
        hard_failures = @($hardFailures.ToArray())
        evidence_holds = @($holds.ToArray())
    }
}

function Get-FailureEventDeltaReport {
    param(
        [Parameter(Mandatory = $true)]
        [object]$BeforeImage,
        [Parameter(Mandatory = $true)]
        [object]$AfterImage
    )

    $beforeTotal = [int64](Get-RequiredProperty `
        $BeforeImage "source_port_request_failure_event_count_total" `
        "observation start failure journal")
    $afterTotal = [int64](Get-RequiredProperty `
        $AfterImage "source_port_request_failure_event_count_total" `
        "observation end failure journal")
    $beforeDrop = [int64](Get-RequiredProperty `
        $BeforeImage "source_port_request_failure_event_drop_count" `
        "observation start failure journal")
    $afterDrop = [int64](Get-RequiredProperty `
        $AfterImage "source_port_request_failure_event_drop_count" `
        "observation end failure journal")
    $eventDelta = $afterTotal - $beforeTotal
    $dropDelta = $afterDrop - $beforeDrop
    $beforeSequence = [int64]0
    foreach ($event in @($BeforeImage.source_port_recent_request_failure_events)) {
        $sequence = [int64](Get-OptionalProperty $event "event_sequence")
        $beforeSequence = [Math]::Max($beforeSequence, $sequence)
    }
    $newEvents = @(
        foreach ($event in @($AfterImage.source_port_recent_request_failure_events)) {
            if ([int64](Get-OptionalProperty $event "event_sequence") -gt
                $beforeSequence) {
                $event
            }
        }
    )
    $hardFailures = New-Object System.Collections.Generic.List[string]
    $holds = New-Object System.Collections.Generic.List[string]
    if ($eventDelta -gt 0) {
        [void]$hardFailures.Add("failure-event-journal-increased:$eventDelta")
    } elseif ($eventDelta -lt 0) {
        [void]$holds.Add("failure-event-journal-decreased")
    }
    if ($dropDelta -gt 0) {
        [void]$hardFailures.Add("failure-event-journal-drop-increased:$dropDelta")
    } elseif ($dropDelta -lt 0) {
        [void]$holds.Add("failure-event-drop-counter-decreased")
    }
    if ($eventDelta -gt 0 -and $newEvents.Count -eq 0) {
        [void]$holds.Add("failure-event-detail-missing")
    }
    return [pscustomobject][ordered]@{
        event_count_delta = $eventDelta
        drop_count_delta = $dropDelta
        failure_events = $newEvents
        hard_failures = @($hardFailures.ToArray())
        evidence_holds = @($holds.ToArray())
    }
}

function ConvertTo-SafeRecentSpotErrors {
    param(
        [object]$ErrorResponse
    )

    $items = @(Get-OptionalProperty -InputObject $ErrorResponse -Name "items")
    $safe = New-Object System.Collections.Generic.List[object]
    foreach ($item in $items) {
        if ($null -eq $item) {
            continue
        }
        $source = [string](Get-OptionalProperty -InputObject $item -Name "source")
        if ($source -notlike "spot*") {
            continue
        }
        [void]$safe.Add([pscustomobject][ordered]@{
            time_iso = Get-OptionalProperty -InputObject $item -Name "time_iso"
            source = $source
            status = Get-OptionalProperty -InputObject $item -Name "status"
            error_type = Get-OptionalProperty -InputObject $item -Name "error_type"
            path = Get-OptionalProperty -InputObject $item -Name "path"
            repeat = Get-OptionalProperty -InputObject $item -Name "repeat"
        })
    }
    return @($safe.ToArray())
}

function Assert-ImageGate {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Image,

        [Parameter(Mandatory = $true)]
        [string]$Stage
    )

    if ($Image.source_port_policy_version -cne "spot-source-port-quarantine-v2") {
        throw "$Stage source-port policy mismatch"
    }
    if (
        $Image.source_port_enforcement_supported -ne $true -or
        $Image.source_port_enforcement_active -ne $true
    ) {
        throw "$Stage source-port enforcement inactive"
    }

    $poolTotal =
        [int]$Image.source_port_pool_guarded_count +
        [int]$Image.source_port_pool_leased_count +
        [int]$Image.source_port_pool_quarantined_count +
        [int]$Image.source_port_pool_rebind_pending_count
    if ($poolTotal -ne [int]$Image.source_port_pool_capacity) {
        throw "$Stage source-port pool partition mismatch"
    }

    foreach ($name in @(Get-CumulativeFailureCounterNames)) {
        if ([int64]$Image.$name -lt 0) {
            throw "$Stage negative cumulative counter: $name=$($Image.$name)"
        }
    }

    if ($Image.request_budget_within_target -ne $true) {
        throw "$Stage SPOT request budget exceeded"
    }
    if ([double]$Image.request_budget_total_background_max_per_sec -gt 6.0) {
        throw "$Stage SPOT request budget limit exceeds 6/s"
    }
    if ([double]$Image.source_port_minimum_reuse_interval_seconds -lt 75.0) {
        throw "$Stage source-port minimum reuse interval below 75 seconds"
    }
}

function Get-InstalledState {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Identity,

        [Parameter(Mandatory = $true)]
        [string]$IntegrityModulePath,

        [Parameter(Mandatory = $true)]
        [string]$ConfigPath,

        [Parameter(Mandatory = $true)]
        [string]$Stage
    )

    $health = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 5
    if ($health.app_version -cne $Identity.product.version) {
        throw "$Stage app version mismatch: $($health.app_version)"
    }

    $backend = @(Get-Process -Name "SmartFactoryBackend" -ErrorAction Stop)
    if ($backend.Count -ne 1) {
        throw "$Stage backend process count mismatch: $($backend.Count)"
    }
    $portOwners = @(
        Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction Stop |
            Select-Object -ExpandProperty OwningProcess -Unique
    )
    if ($portOwners.Count -ne 1 -or $portOwners[0] -ne $backend[0].Id) {
        throw "$Stage port 8000 ownership mismatch"
    }

    $appPaths = @(
        Get-Process -Name "smart-factory" -ErrorAction Stop |
            Where-Object { $_.Path } |
            Select-Object -ExpandProperty Path -Unique
    )
    if ($appPaths.Count -ne 1) {
        throw "$Stage installed Electron path is ambiguous"
    }
    $appRoot = Split-Path -Parent $appPaths[0]
    $backendRoot = Join-Path $appRoot "resources\backend"
    $provenancePath = Join-Path `
        $backendRoot `
        "_internal\backend\build_provenance.json"
    $appAsarPath = Join-Path $appRoot "resources\app.asar"
    $provenance = Get-Content -LiteralPath $provenancePath -Raw | ConvertFrom-Json
    if ($provenance.git_commit -cne $Identity.product.build_git_commit) {
        throw "$Stage installed build commit mismatch"
    }
    $appAsarHash = Assert-FileSha256 `
        -Path $appAsarPath `
        -ExpectedSha256 $Identity.product.app_asar_sha256 `
        -Label "$Stage app.asar"

    Remove-Module backend_bundle_integrity -Force -ErrorAction SilentlyContinue
    Import-Module -Name $IntegrityModulePath -Force -ErrorAction Stop
    $integrity = Test-BackendBundleIntegrity -BackendRoot $backendRoot
    if (-not $integrity.ok) {
        throw "$Stage backend bundle integrity failed"
    }
    if (
        $integrity.build_git_commit -cne $Identity.product.build_git_commit -or
        $integrity.actual_bundle_sha256 -cne $Identity.product.backend_bundle_sha256 -or
        [int]$integrity.verified_file_count -ne
            [int]$Identity.product.backend_bundle_file_count
    ) {
        throw "$Stage backend bundle identity mismatch"
    }

    $configHash = Assert-FileSha256 `
        -Path $ConfigPath `
        -ExpectedSha256 $Identity.product.config_sha256 `
        -Label "$Stage config.ini"
    $imageRaw = (
        Invoke-RestMethod "http://127.0.0.1:8000/api/spot/config" -TimeoutSec 10
    ).image
    $image = ConvertTo-SafeImageSnapshot -Image $imageRaw
    Assert-ImageGate -Image $image -Stage $Stage

    $live = Invoke-WebRequest `
        -UseBasicParsing `
        -Uri "http://127.0.0.1:8000/api/spot/live_image.jpg" `
        -TimeoutSec 10
    if (
        $live.StatusCode -ne 200 -or
        $live.Headers["Content-Type"] -notmatch "^image/jpeg" -or
        $live.Headers["X-Spot-Image-Profile"] -cne "operator_live"
    ) {
        throw "$Stage operator-live image probe failed"
    }

    return [pscustomobject][ordered]@{
        observed_at = (Get-Date).ToString("o")
        version = $health.app_version
        backend_pid = $backend[0].Id
        port_8000_owner = $portOwners[0]
        electron_path = $appPaths[0]
        build_git_commit = $provenance.git_commit
        app_asar_sha256 = $appAsarHash
        backend_bundle_sha256 = $integrity.actual_bundle_sha256
        backend_bundle_files_verified = $integrity.verified_file_count
        config_sha256 = $configHash
        live_image_status = $live.StatusCode
        live_image_profile = $live.Headers["X-Spot-Image-Profile"]
        image = $image
    }
}

function Get-ObservationBoundaryPair {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SanitizedRoot
    )

    $holds = New-Object System.Collections.Generic.List[string]
    $startPath = Join-Path $SanitizedRoot "canary-observation-start.json"
    $endPath = Join-Path $SanitizedRoot "canary-observation-end.json"
    $start = $null
    $end = $null
    foreach ($entry in @(
        [pscustomobject]@{ Role = "start"; Path = $startPath },
        [pscustomobject]@{ Role = "end"; Path = $endPath }
    )) {
        if (-not (Test-Path -LiteralPath $entry.Path -PathType Leaf)) {
            [void]$holds.Add("observation-$($entry.Role)-boundary-missing")
            continue
        }
        try {
            $value = Get-Content -LiteralPath $entry.Path -Raw | ConvertFrom-Json
            if ($value.schema_version -cne
                "spot-canary-observation-boundary-v1" -or
                $value.boundary_role -cne $entry.Role) {
                throw "boundary schema or role mismatch"
            }
            if ([double]$value.capture_latency_ms -gt 5000) {
                [void]$holds.Add("observation-$($entry.Role)-boundary-late")
            }
            if ($entry.Role -ceq "start") {
                $start = $value
            } else {
                $end = $value
            }
        } catch {
            [void]$holds.Add("observation-$($entry.Role)-boundary-invalid")
        }
    }
    if ($null -ne $start -and $null -ne $end) {
        try {
            if ((Get-CounterWindowElapsedSeconds -Before $start -After $end) -le 0) {
                [void]$holds.Add("observation-boundary-order-invalid")
            }
            if ([int64]$end.monotonic_ticks -le [int64]$start.monotonic_ticks -or
                [int64]$end.monotonic_frequency -ne
                    [int64]$start.monotonic_frequency) {
                [void]$holds.Add("observation-monotonic-boundary-invalid")
            }
        } catch {
            [void]$holds.Add("observation-boundary-time-invalid")
        }
    }
    return [pscustomobject][ordered]@{
        start = $start
        end = $end
        evidence_holds = @($holds.ToArray())
        valid = ($null -ne $start -and $null -ne $end -and $holds.Count -eq 0)
        start_path = $startPath
        end_path = $endPath
    }
}

function Get-PostprocessState {
    param([Parameter(Mandatory = $true)][string]$ConfigPath)

    $health = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 5
    $backend = @(Get-Process -Name "SmartFactoryBackend" -ErrorAction Stop)
    if ($backend.Count -ne 1) {
        throw "postprocess backend process count mismatch"
    }
    $owners = @(
        Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction Stop |
            Select-Object -ExpandProperty OwningProcess -Unique
    )
    if ($owners.Count -ne 1) {
        throw "postprocess port 8000 owner is ambiguous"
    }
    $backendRoot = Split-Path -Parent $backend[0].Path
    $provenance = Get-Content `
        -LiteralPath (Join-Path $backendRoot "_internal\backend\build_provenance.json") `
        -Raw |
        ConvertFrom-Json
    return [pscustomobject][ordered]@{
        schema_version = "spot-canary-postprocess-state-v1"
        observed_at = (Get-Date).ToString("o")
        app_version = [string]$health.app_version
        backend_pid = [int]$backend[0].Id
        port_8000_owner = [int]$owners[0]
        build_git_commit = [string]$provenance.git_commit
        config_sha256 = (
            Get-FileHash -LiteralPath $ConfigPath -Algorithm SHA256
        ).Hash
        local_only = $true
        added_spot_requests = $false
    }
}

function Get-PostprocessIntegrityFailures {
    param(
        [Parameter(Mandatory = $true)][object]$ObservationEnd,
        [Parameter(Mandatory = $true)][object]$PostprocessState
    )

    $failures = New-Object System.Collections.Generic.List[string]
    foreach ($field in @(
        "backend_pid",
        "port_8000_owner",
        "build_git_commit",
        "config_sha256"
    )) {
        if ([string]$PostprocessState.$field -cne [string]$ObservationEnd.$field) {
            [void]$failures.Add("postprocess-state-changed:$field")
        }
    }
    return @($failures.ToArray())
}

function Confirm-StableHistoricalFailureBaseline {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InitialState,

        [Parameter(Mandatory = $true)]
        [string]$ConfigPath,

        [int]$StabilitySeconds = 30,

        [int]$ProgressIntervalSeconds = 10
    )

    if ($StabilitySeconds -lt 1) {
        throw "historical failure baseline stability duration must be positive"
    }
    if ($ProgressIntervalSeconds -lt 1) {
        throw "historical failure baseline progress interval must be positive"
    }

    $startedAt = Get-Date
    $clock = [System.Diagnostics.Stopwatch]::StartNew()
    while ($clock.Elapsed.TotalSeconds -lt $StabilitySeconds) {
        $remainingBeforeSleep = [math]::Max(
            0.0,
            $StabilitySeconds - $clock.Elapsed.TotalSeconds
        )
        $sleepSeconds = [math]::Min(
            [double]$ProgressIntervalSeconds,
            $remainingBeforeSleep
        )
        if ($sleepSeconds -gt 0) {
            Start-Sleep -Milliseconds ([int][math]::Ceiling($sleepSeconds * 1000))
        }

        $backend = @(
            Get-Process -Name "SmartFactoryBackend" -ErrorAction SilentlyContinue
        )
        $backendAlive = (
            $backend.Count -eq 1 -and
            $backend[0].Id -eq [int]$InitialState.backend_pid
        )
        $elapsedSeconds = [math]::Min(
            [double]$StabilitySeconds,
            $clock.Elapsed.TotalSeconds
        )
        $remainingSeconds = [math]::Max(
            0.0,
            $StabilitySeconds - $elapsedSeconds
        )
        $percent = [math]::Round(
            100.0 * $elapsedSeconds / $StabilitySeconds,
            1
        )
        $progressMessage = (
            "[PREFLIGHT BASELINE PROGRESS] elapsed={0} remaining={1} " +
            "percent={2}% backend_pid={3} backend_alive={4} checked_at={5}; " +
            "local clock/process only; no added SPOT requests"
        ) -f `
            ([TimeSpan]::FromSeconds($elapsedSeconds).ToString("hh\:mm\:ss")), `
            ([TimeSpan]::FromSeconds($remainingSeconds).ToString("hh\:mm\:ss")), `
            $percent, `
            $InitialState.backend_pid, `
            $backendAlive, `
            (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")
        Write-Host $progressMessage -ForegroundColor Cyan

        if (-not $backendAlive) {
            throw "backend changed during historical failure baseline stability check"
        }
    }
    $clock.Stop()

    $portOwners = @(
        Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction Stop |
            Select-Object -ExpandProperty OwningProcess -Unique
    )
    if (
        $portOwners.Count -ne 1 -or
        $portOwners[0] -ne [int]$InitialState.backend_pid
    ) {
        throw "port 8000 ownership changed during historical failure baseline"
    }
    $configHash = (
        Get-FileHash -LiteralPath $ConfigPath -Algorithm SHA256
    ).Hash
    if ($configHash -cne [string]$InitialState.config_sha256) {
        throw "config.ini changed during historical failure baseline"
    }

    $imageRaw = (
        Invoke-RestMethod "http://127.0.0.1:8000/api/spot/config" -TimeoutSec 10
    ).image
    $stableImage = ConvertTo-SafeImageSnapshot -Image $imageRaw
    Assert-ImageGate -Image $stableImage -Stage "historical failure baseline"
    $failureCounterDeltas = Assert-FailureCounterDeltas `
        -BeforeImage $InitialState.image `
        -AfterImage $stableImage `
        -Stage "preflight baseline"

    $recentErrors = Invoke-RestMethod `
        "http://127.0.0.1:8000/api/observability/errors?limit=50" `
        -TimeoutSec 10
    $baselineCounters = Get-CumulativeFailureCounterSnapshot -Image $stableImage
    $hasHistoricalFailure = $false
    foreach ($name in @(Get-CumulativeFailureCounterNames)) {
        if ([int64]$baselineCounters.$name -gt 0) {
            $hasHistoricalFailure = $true
            break
        }
    }

    $completedAt = Get-Date
    $InitialState.observed_at = $completedAt.ToString("o")
    $InitialState.image = $stableImage
    $evidence = [pscustomobject][ordered]@{
        schema_version = "spot-canary-historical-failure-baseline-v1"
        classification = if ($hasHistoricalFailure) {
            "STABLE_HISTORICAL_FAILURE_BASELINE"
        } else {
            "CLEAN_FAILURE_BASELINE"
        }
        started_at = $startedAt.ToString("o")
        completed_at = $completedAt.ToString("o")
        stability_duration_seconds = [math]::Round(
            $clock.Elapsed.TotalSeconds,
            3
        )
        progress_interval_seconds = $ProgressIntervalSeconds
        progress_source = "local-clock-and-process-state-only"
        progress_adds_spot_requests = $false
        backend_pid = $InitialState.backend_pid
        config_sha256 = $InitialState.config_sha256
        historical_failure_baseline = $baselineCounters
        stability_failure_counter_deltas = $failureCounterDeltas
        recent_spot_errors = @(
            ConvertTo-SafeRecentSpotErrors -ErrorResponse $recentErrors
        )
        error_queue_cleared = $false
        application_restarted = $false
    }
    return [pscustomobject][ordered]@{
        state = $InitialState
        evidence = $evidence
    }
}

function Assert-EvidenceFiles {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Identity,

        [Parameter(Mandatory = $true)]
        [string]$EvidenceRoot
    )

    foreach ($entry in @($Identity.prerequisite_15m.evidence_files)) {
        $path = Join-Path $EvidenceRoot ([string]$entry.file)
        Assert-FileSha256 `
            -Path $path `
            -ExpectedSha256 ([string]$entry.sha256) `
            -Label "15-minute evidence $($entry.file)" | Out-Null
    }

    $preinstallSummaryPath = Join-Path `
        $EvidenceRoot `
        ([string]$Identity.rollback.baseline_preinstall_summary_file)
    $baselineHealthPath = Join-Path `
        $EvidenceRoot `
        ([string]$Identity.rollback.baseline_health_file)
    $preinstallSummary = Get-Content `
        -LiteralPath $preinstallSummaryPath `
        -Raw |
        ConvertFrom-Json
    $baselineHealth = Get-Content `
        -LiteralPath $baselineHealthPath `
        -Raw |
        ConvertFrom-Json
    Assert-RollbackBaselineEvidence `
        -Identity $Identity `
        -PreinstallSummary $preinstallSummary `
        -BaselineHealth $baselineHealth
}

function Get-ObservationDeltaReport {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Before,

        [Parameter(Mandatory = $true)]
        [object]$After
    )

    $hardFailures = New-Object System.Collections.Generic.List[string]
    $holds = New-Object System.Collections.Generic.List[string]
    foreach ($field in @(
        "backend_pid",
        "port_8000_owner",
        "build_git_commit",
        "config_sha256"
    )) {
        if ([string]$After.$field -cne [string]$Before.$field) {
            [void]$hardFailures.Add("observation-state-changed:$field")
        }
    }

    $failureCounterReport = Get-FailureCounterDeltaReport `
        -BeforeImage $Before.image `
        -AfterImage $After.image
    foreach ($item in @($failureCounterReport.hard_failures)) {
        [void]$hardFailures.Add([string]$item)
    }
    foreach ($item in @($failureCounterReport.evidence_holds)) {
        [void]$holds.Add([string]$item)
    }
    $failureEventReport = Get-FailureEventDeltaReport `
        -BeforeImage $Before.image `
        -AfterImage $After.image
    foreach ($item in @($failureEventReport.hard_failures)) {
        [void]$hardFailures.Add([string]$item)
    }
    foreach ($item in @($failureEventReport.evidence_holds)) {
        [void]$holds.Add([string]$item)
    }

    $transportDelta =
        [int64]$After.image.source_port_transport_started_count -
        [int64]$Before.image.source_port_transport_started_count
    $successDelta =
        [int64]$After.image.source_port_transport_success_count -
        [int64]$Before.image.source_port_transport_success_count
    $imageDelta =
        [int64]$After.image.image_upstream_request_count -
        [int64]$Before.image.image_upstream_request_count
    if ($transportDelta -le 0) {
        [void]$hardFailures.Add("transport-counter-did-not-progress")
    }
    if ($successDelta -le 0) {
        [void]$hardFailures.Add("transport-success-counter-did-not-progress")
    }
    if ($imageDelta -le 0) {
        [void]$hardFailures.Add("image-counter-did-not-progress")
    }
    if ($successDelta -gt $transportDelta) {
        [void]$holds.Add("transport-counter-relationship-invalid")
    }
    $counterWindowElapsedSeconds = Get-CounterWindowElapsedSeconds `
        -Before $Before `
        -After $After
    $transportRate = [math]::Round(
        $transportDelta / $counterWindowElapsedSeconds,
        4
    )
    $imageRate = [math]::Round(
        $imageDelta / $counterWindowElapsedSeconds,
        4
    )
    if ($transportRate -gt 6.0) {
        [void]$hardFailures.Add("transport-rate-over-6:$transportRate")
    }
    if ($imageRate -gt 3.2) {
        [void]$hardFailures.Add("image-rate-over-3.2:$imageRate")
    }

    return [pscustomobject][ordered]@{
        transport_started_delta = $transportDelta
        transport_success_delta = $successDelta
        image_upstream_delta = $imageDelta
        counter_window_elapsed_seconds = $counterWindowElapsedSeconds
        transport_rate_per_sec = $transportRate
        image_upstream_rate_per_sec = $imageRate
        failure_counter_deltas = $failureCounterReport.deltas
        failure_event_count_delta = $failureEventReport.event_count_delta
        failure_event_drop_count_delta = $failureEventReport.drop_count_delta
        failure_events = @($failureEventReport.failure_events)
        hard_failures = @($hardFailures.ToArray())
        evidence_holds = @($holds.ToArray())
    }
}

function Test-PacketEvidence {
    param(
        [Parameter(Mandatory = $true)]
        [object]$FieldSummary,

        [Parameter(Mandatory = $true)]
        [object]$FramingSummary
    )

    $hardFailures = New-Object System.Collections.Generic.List[string]
    $holds = New-Object System.Collections.Generic.List[string]

    if ([bool]$FieldSummary.event_trigger_detected) {
        [void]$hardFailures.Add("new-spot-image-connecttimeout")
    }
    $monitorErrorCount =
        [int]$FieldSummary.event_trigger_monitor_error_count
    $monitorRecoveredErrorCount =
        [int]$FieldSummary.event_trigger_monitor_recovered_error_count
    $monitorUnrecoveredErrorCount =
        [int]$FieldSummary.event_trigger_monitor_unrecovered_error_count
    $monitorIntegrityStatus =
        [string]$FieldSummary.event_trigger_monitor_integrity_status
    $monitorIntegrityPolicy =
        [string]$FieldSummary.event_trigger_monitor_integrity_policy
    $monitorIntegrityComplete = (
        $monitorIntegrityPolicy -ceq
            "recovered-errors-within-detection-threshold-are-complete" -and
        $monitorIntegrityStatus.StartsWith(
            "complete-",
            [StringComparison]::Ordinal
        ) -and
        $monitorUnrecoveredErrorCount -eq 0 -and
        ($monitorRecoveredErrorCount + $monitorUnrecoveredErrorCount) -eq
            $monitorErrorCount
    )
    if (-not $monitorIntegrityComplete) {
        [void]$holds.Add("trigger-monitor-integrity-incomplete")
    }
    if ($FieldSummary.packet_direction_preflight -ne "passed") {
        [void]$holds.Add("packet-direction-preflight")
    }
    if ($FieldSummary.framing_analysis_status -ne "completed") {
        [void]$holds.Add("framing-analysis-incomplete")
    }
    if ($FieldSummary.observation_boundary_status -ne "complete") {
        [void]$holds.Add("observation-boundary-incomplete")
    }
    if ($FieldSummary.observation_counter_policy -cne
        "observation-start-to-observation-end") {
        [void]$holds.Add("observation-counter-policy-mismatch")
    }
    if ($FieldSummary.packet_analysis_schema -cne
        "spot-http-framing-evidence-v7") {
        [void]$holds.Add("packet-analysis-schema-mismatch")
    }
    if ($FieldSummary.windows_tcp_ipv4_evidence_status -ne "completed") {
        [void]$holds.Add("windows-tcp-evidence-incomplete")
    }
    if ([bool]$FieldSummary.packet_payload_artifacts_retained) {
        [void]$holds.Add("packet-payload-retained")
    }
    if ([double]$FieldSummary.observation_elapsed_seconds -lt 7190.0 -and
        -not [bool]$FieldSummary.event_trigger_detected) {
        [void]$holds.Add("observation-shorter-than-120m")
    }

    $allowedMissing = @("switch-start-counters", "switch-end-counters")
    foreach ($missing in @($FieldSummary.required_evidence_missing)) {
        if ([string]$missing -notin $allowedMissing) {
            [void]$holds.Add("required-evidence-missing:$missing")
        }
    }

    if ($FramingSummary.schema_version -ne "spot-http-framing-evidence-v7") {
        [void]$holds.Add("framing-schema-mismatch")
    }
    if ($FramingSummary.analysis_window.policy -cne
        "observation-start-to-observation-end") {
        [void]$holds.Add("packet-analysis-window-policy-mismatch")
    }
    if (
        [bool]$FramingSummary.capture_coverage.overwrite_detected -or
        $FramingSummary.capture_coverage.status -ne "capture-window-retained"
    ) {
        [void]$holds.Add("packet-capture-window-incomplete")
    }

    $tcp = $FramingSummary.tcp_connection_summary
    $measurement = $FramingSummary.packet_measurement
    $clockCalibrationComplete =
        [string]$measurement.clock_calibration.status -ceq "complete"
    if (-not $clockCalibrationComplete) {
        [void]$holds.Add("packet-clock-calibration-incomplete")
    }
    $packetOrderComplete = (
        [string]$measurement.timestamp_ordering_policy -ceq
            "timestamp-sorted-stable-v1"
    )
    if (-not $packetOrderComplete) {
        [void]$holds.Add("packet-timestamp-order-unresolved")
    }
    if ([int]$measurement.timestamp_regression_count -ne 0 -and
        -not [bool]$measurement.timestamp_order_correction_applied) {
        [void]$holds.Add("packet-timestamp-regression-uncorrected")
    }
    if ($packetOrderComplete) {
        if ([int]$tcp.failed_connection_attempts -ne 0) {
            [void]$hardFailures.Add("failed-connection-attempt")
        }
        if ([int]$tcp.reset_before_response_attempts -ne 0) {
            [void]$hardFailures.Add("reset-before-response")
        }
        if ([int]$tcp.no_response_after_handshake_attempts -ne 0) {
            [void]$hardFailures.Add("no-response-after-handshake")
        }
        if ([int]$tcp.syn_retransmissions_total -ne 0) {
            [void]$hardFailures.Add("syn-retransmission-observed")
        }
    } elseif (
        [int]$tcp.failed_connection_attempts -ne 0 -or
        [int]$tcp.reset_before_response_attempts -ne 0 -or
        [int]$tcp.no_response_after_handshake_attempts -ne 0 -or
        [int]$tcp.syn_retransmissions_total -ne 0
    ) {
        [void]$holds.Add("packet-connection-outcome-unresolved")
    }
    if ([int]$measurement.rst_total -ne 0) {
        [void]$hardFailures.Add("bidirectional-rst-observed")
    }

    $reuse = $tcp.same_four_tuple_reuse.monotonic_corrected
    $reuseMeasurementComplete = (
        $packetOrderComplete -and
        $clockCalibrationComplete -and
        [string]$tcp.same_four_tuple_reuse.ordering_policy -ceq
            "timestamp-sorted-per-four-tuple-v1" -and
        [string]$tcp.same_four_tuple_reuse.measurement_integrity_status -ceq
            "complete"
    )
    if (-not $reuseMeasurementComplete) {
        [void]$holds.Add("same-four-tuple-reuse-measurement-unresolved")
    } else {
        if ([int]$reuse.under_60000_ms_count -ne 0) {
            [void]$hardFailures.Add("same-four-tuple-reuse-under-60s")
        }
        if (
            [int]$reuse.observed_count -gt 0 -and
            [double]$reuse.interval_ms_min -lt 75000.0
        ) {
            [void]$hardFailures.Add("same-four-tuple-reuse-under-75s")
        }
    }

    $serverResetProperty = $FramingSummary.server_close_counts.PSObject.Properties["reset"]
    $serverResetCount = if ($null -eq $serverResetProperty) {
        0
    } else {
        [int]$serverResetProperty.Value
    }

    return [pscustomobject][ordered]@{
        hard_failures = @($hardFailures.ToArray())
        evidence_holds = @($holds.ToArray())
        capture_coverage_status = $FramingSummary.capture_coverage.status
        capture_overwrite_detected = [bool]$FramingSummary.capture_coverage.overwrite_detected
        connection_attempts_total = [int]$tcp.connection_attempts_total
        failed_connection_attempts = [int]$tcp.failed_connection_attempts
        reset_before_response_attempts = [int]$tcp.reset_before_response_attempts
        server_reset_response_count = $serverResetCount
        syn_retransmissions_total = [int]$tcp.syn_retransmissions_total
        interface_count = [int]$measurement.interface_count
        duplicate_packet_count = [int64]$measurement.duplicate_packet_count
        duplicate_initial_syn_count = [int64]$measurement.duplicate_initial_syn_count
        timestamp_regression_count = [int64]$measurement.timestamp_regression_count
        timestamp_regression_max_ms = $measurement.timestamp_regression_max_ms
        initial_syn_timestamp_regression_count =
            [int64]$measurement.initial_syn_timestamp_regression_count
        initial_syn_timestamp_regression_max_ms =
            $measurement.initial_syn_timestamp_regression_max_ms
        timestamp_ordering_policy = [string]$measurement.timestamp_ordering_policy
        timestamp_order_correction_applied =
            [bool]$measurement.timestamp_order_correction_applied
        client_to_server_rst_count = [int64]$measurement.client_to_server_rst_count
        server_to_client_rst_count = [int64]$measurement.server_to_client_rst_count
        excluded_before_observation_count = [int64](
            $FramingSummary.analysis_window.excluded_before_count
        )
        excluded_after_observation_count = [int64](
            $FramingSummary.analysis_window.excluded_after_count
        )
        clock_calibration_status = [string]$measurement.clock_calibration.status
        same_four_tuple_original = $tcp.same_four_tuple_reuse.original
        same_four_tuple_duplicate_removed = (
            $tcp.same_four_tuple_reuse.duplicate_removed
        )
        same_four_tuple_monotonic_corrected = $reuse
        same_four_tuple_reuse_ordering_policy =
            [string]$tcp.same_four_tuple_reuse.ordering_policy
        same_four_tuple_reuse_measurement_integrity_status =
            [string]$tcp.same_four_tuple_reuse.measurement_integrity_status
        same_four_tuple_reuse_observed_count = [int]$reuse.observed_count
        same_four_tuple_reuse_interval_ms_min = $reuse.interval_ms_min
        same_four_tuple_reuse_under_60000_ms_count = [int]$reuse.under_60000_ms_count
        old_ack_rst_proxy_policy = (
            "No source port values are serialized. Gate uses >=75s same-four-tuple " +
            "reuse plus zero reset-before-response and zero reuse violations; " +
            "it does not claim direct attribution of every late ACK."
        )
    }
}

function Resolve-CanaryRuntimeEvidenceBase {
    param(
        [string]$ExplicitPath = ""
    )

    $candidate = $ExplicitPath
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
            throw "LOCALAPPDATA is unavailable for the private canary runtime evidence root"
        }
        $candidate = Join-Path $env:LOCALAPPDATA "SFLCanary"
    }
    if (-not [IO.Path]::IsPathRooted($candidate)) {
        throw "runtime evidence base must be an absolute path"
    }

    $fullPath = [IO.Path]::GetFullPath($candidate).TrimEnd("\")
    $volumeRoot = [IO.Path]::GetPathRoot($fullPath).TrimEnd("\")
    if ($fullPath -ceq $volumeRoot) {
        throw "runtime evidence base must not be a volume root"
    }
    return $fullPath
}

function Get-ProjectedRuntimeEvidencePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$EvidenceBase
    )

    return Join-Path $EvidenceBase (
        "runtime_validation_yyyyMMdd_HHmmss\raw_private\app\" +
        "operational_observability_yyyyMMdd_HHmmss\raw\" +
        "trigger_baseline_observability_errors.json." +
        "ffffffffffffffffffffffffffffffff.tmp"
    )
}

function Assert-CanaryRuntimeEvidencePathBudget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$EvidenceBase,

        [ValidateRange(200, 259)]
        [int]$MaxPathChars = 240
    )

    $projectedPath = Get-ProjectedRuntimeEvidencePath -EvidenceBase $EvidenceBase
    if ($projectedPath.Length -gt $MaxPathChars) {
        throw (
            "trigger-evidence-path-too-long: projected runtime evidence path " +
            "chars={0} limit={1} base={2}" -f
                $projectedPath.Length,
                $MaxPathChars,
                $EvidenceBase
        )
    }
    return $projectedPath
}

function Invoke-SelfTest {
    $image = [pscustomobject]@{
        source_port_policy_version = "spot-source-port-quarantine-v2"
        source_port_enforcement_supported = $true
        source_port_enforcement_active = $true
        source_port_pool_capacity = 4
        source_port_pool_guarded_count = 1
        source_port_pool_leased_count = 1
        source_port_pool_quarantined_count = 2
        source_port_pool_rebind_pending_count = 0
        source_port_pool_acquire_wait_count = 0
        source_port_pool_exhaustion_count = 0
        source_port_rebind_retry_count = 0
        source_port_reuse_violation_count = 0
        source_port_minimum_reuse_interval_seconds = 75.0
        source_port_transport_started_count = 10
        source_port_transport_success_count = 10
        source_port_transport_failure_count = 1
        source_port_bind_collision_count = 0
        source_port_image_failure_count = 1
        source_port_temperature_failure_count = 0
        source_port_internal_temperature_failure_count = 0
        source_port_diagnostic_failure_count = 0
        source_port_connection_test_failure_count = 0
        source_port_request_event_count_total = 20
        source_port_request_event_drop_count = 0
        source_port_request_failure_event_count_total = 2
        source_port_request_failure_event_drop_count = 0
        source_port_recent_request_failure_events = @(
            [pscustomobject]@{
                event_sequence = 10
                event_at_utc = "2026-08-21T10:32:26.000Z"
                correlation_id = "must-not-be-copied"
                request_kind = "image"
                state = "failed"
                exception_class = "TimeoutError"
            }
        )
        request_budget_within_target = $true
        request_budget_total_background_max_per_sec = 6.0
        image_upstream_request_count = 5
        image_refresh_success_count = 5
        image_refresh_failure_count = 0
        image_cache_clock_anomaly_count = 0
    }
    $snapshot = ConvertTo-SafeImageSnapshot -Image $image
    Assert-ImageGate -Image $snapshot -Stage "self-test"
    if ($snapshot.source_port_recent_request_failure_events[0].PSObject.Properties[
        "correlation_id"
    ]) {
        throw "self-test safe failure event leaked correlation_id"
    }

    $field = [pscustomobject]@{
        status = "COMPLETED"
        event_trigger_detected = $false
        event_trigger_monitor_error_count = 0
        event_trigger_monitor_recovered_error_count = 0
        event_trigger_monitor_unrecovered_error_count = 0
        event_trigger_monitor_integrity_status = "complete-no-errors"
        event_trigger_monitor_integrity_policy =
            "recovered-errors-within-detection-threshold-are-complete"
        packet_direction_preflight = "passed"
        framing_analysis_status = "completed"
        windows_tcp_ipv4_evidence_status = "completed"
        packet_payload_artifacts_retained = $false
        observation_elapsed_seconds = 7200
        required_evidence_missing = @()
        observation_boundary_status = "complete"
        observation_counter_policy = "observation-start-to-observation-end"
        packet_analysis_schema = "spot-http-framing-evidence-v7"
    }
    $framing = [pscustomobject]@{
        schema_version = "spot-http-framing-evidence-v7"
        analysis_window = [pscustomobject]@{
            policy = "observation-start-to-observation-end"
            excluded_before_count = 2
            excluded_after_count = 3
        }
        packet_measurement = [pscustomobject]@{
            interface_count = 2
            duplicate_packet_count = 8
            duplicate_initial_syn_count = 4
            timestamp_regression_count = 924
            timestamp_regression_max_ms = 1.25
            initial_syn_timestamp_regression_count = 0
            initial_syn_timestamp_regression_max_ms = 0
            timestamp_ordering_policy = "timestamp-sorted-stable-v1"
            timestamp_order_correction_applied = $true
            client_to_server_rst_count = 0
            server_to_client_rst_count = 0
            rst_total = 0
            clock_calibration = [pscustomobject]@{ status = "complete" }
        }
        capture_coverage = [pscustomobject]@{
            overwrite_detected = $false
            status = "capture-window-retained"
        }
        tcp_connection_summary = [pscustomobject]@{
            connection_attempts_total = 100
            failed_connection_attempts = 0
            reset_before_response_attempts = 0
            no_response_after_handshake_attempts = 0
            syn_retransmissions_total = 0
            same_four_tuple_reuse = [pscustomobject]@{
                original = [pscustomobject]@{ interval_ms_min = 74011 }
                duplicate_removed = [pscustomobject]@{ interval_ms_min = 74011 }
                ordering_policy = "timestamp-sorted-per-four-tuple-v1"
                measurement_integrity_status = "complete"
                monotonic_corrected = [pscustomobject]@{
                    observed_count = 1
                    interval_ms_min = 75000
                    under_60000_ms_count = 0
                }
            }
        }
        server_close_counts = [pscustomobject]@{ reset = 0 }
    }
    $packet = Test-PacketEvidence -FieldSummary $field -FramingSummary $framing
    if ($packet.hard_failures.Count -ne 0 -or $packet.evidence_holds.Count -ne 0) {
        throw "self-test valid packet evidence was rejected"
    }
    $framing.tcp_connection_summary.same_four_tuple_reuse.monotonic_corrected.interval_ms_min = 74999
    $framing.tcp_connection_summary.same_four_tuple_reuse.measurement_integrity_status =
        "packet-order-unresolved"
    $packet = Test-PacketEvidence -FieldSummary $field -FramingSummary $framing
    if ("same-four-tuple-reuse-under-75s" -in $packet.hard_failures -or
        "same-four-tuple-reuse-measurement-unresolved" -notin
            $packet.evidence_holds) {
        throw "self-test uncertain reuse interval was not held"
    }
    $framing.tcp_connection_summary.same_four_tuple_reuse.measurement_integrity_status =
        "complete"
    $packet = Test-PacketEvidence -FieldSummary $field -FramingSummary $framing
    if ("same-four-tuple-reuse-under-75s" -notin $packet.hard_failures) {
        throw "self-test confirmed short reuse interval was not rejected"
    }
    $framing.tcp_connection_summary.same_four_tuple_reuse.monotonic_corrected.interval_ms_min = 75000
    $field.event_trigger_monitor_error_count = 1
    $field.event_trigger_monitor_recovered_error_count = 1
    $field.event_trigger_monitor_integrity_status =
        "complete-recovered-transient-errors"
    $packet = Test-PacketEvidence -FieldSummary $field -FramingSummary $framing
    if ("trigger-monitor-integrity-incomplete" -in $packet.evidence_holds) {
        throw "self-test recovered trigger monitor error was rejected"
    }
    $field.event_trigger_monitor_recovered_error_count = 0
    $field.event_trigger_monitor_unrecovered_error_count = 1
    $field.event_trigger_monitor_integrity_status = "incomplete-unrecovered-errors"
    $packet = Test-PacketEvidence -FieldSummary $field -FramingSummary $framing
    if ("trigger-monitor-integrity-incomplete" -notin $packet.evidence_holds) {
        throw "self-test unrecovered trigger monitor error was accepted"
    }

    $before = [pscustomobject]@{
        observed_at = "2026-08-21T20:12:04.2365692+09:00"
        backend_pid = 10
        port_8000_owner = 10
        build_git_commit = "5971fc4fbdeec07ef65681a945319f0ae12d55cb"
        config_sha256 = "config-hash"
        electron_path = "C:\Program Files\SmartFactory\smart-factory.exe"
        image = [pscustomobject]@{
            source_port_transport_started_count = 21094
            source_port_transport_success_count = 21094
            image_upstream_request_count = 9822
        }
    }
    $after = [pscustomobject]@{
        observed_at = "2026-08-21T20:13:03.7043697+09:00"
        backend_pid = 10
        port_8000_owner = 10
        build_git_commit = "5971fc4fbdeec07ef65681a945319f0ae12d55cb"
        config_sha256 = "config-hash"
        electron_path = "C:\Program Files\SmartFactory\smart-factory.exe"
        image = [pscustomobject]@{
            source_port_transport_started_count = 21426
            source_port_transport_success_count = 21426
            image_upstream_request_count = 9986
        }
    }
    foreach ($name in @(Get-CumulativeFailureCounterNames)) {
        Add-Member `
            -InputObject $before.image `
            -NotePropertyName $name `
            -NotePropertyValue 0
        Add-Member `
            -InputObject $after.image `
            -NotePropertyName $name `
            -NotePropertyValue 0
    }
    $before.image.source_port_transport_failure_count = 1
    $before.image.source_port_image_failure_count = 1
    $after.image.source_port_transport_failure_count = 1
    $after.image.source_port_image_failure_count = 1
    Add-Member `
        -InputObject $before.image `
        -NotePropertyName source_port_recent_request_failure_events `
        -NotePropertyValue @()
    Add-Member `
        -InputObject $after.image `
        -NotePropertyName source_port_recent_request_failure_events `
        -NotePropertyValue @()
    Add-Member `
        -InputObject $before.image `
        -NotePropertyName source_port_request_event_drop_count `
        -NotePropertyValue 593576
    Add-Member `
        -InputObject $after.image `
        -NotePropertyName source_port_request_event_drop_count `
        -NotePropertyValue 593648
    $journalEvictionDeltas = Assert-FailureCounterDeltas `
        -BeforeImage $before.image `
        -AfterImage $after.image `
        -Stage "self-test general request journal eviction"
    if ($journalEvictionDeltas.PSObject.Properties[
        "source_port_request_event_drop_count"
    ]) {
        throw "self-test general request journal eviction was treated as failure"
    }
    $deltas = Get-ObservationDeltaReport -Before $before -After $after
    if (
        [math]::Abs(
            [double]$deltas.counter_window_elapsed_seconds - 59.4678005
        ) -gt 0.0001 -or
        [double]$deltas.transport_rate_per_sec -ne 5.5829 -or
        [double]$deltas.image_upstream_rate_per_sec -ne 2.7578 -or
        [int64]$deltas.failure_counter_deltas.source_port_transport_failure_count -ne 0 -or
        @($deltas.hard_failures).Count -ne 0 -or
        @($deltas.evidence_holds).Count -ne 0
    ) {
        throw "self-test counter-window rate calculation mismatch"
    }
    $after.image.source_port_request_failure_event_drop_count = 1
    $failureJournalDropRejected = $false
    try {
        $null = Assert-FailureCounterDeltas `
            -BeforeImage $before.image `
            -AfterImage $after.image `
            -Stage "self-test failure journal drop"
    } catch {
        if ($_.Exception.Message -like (
            "*field=source_port_request_failure_event_drop_count*"
        )) {
            $failureJournalDropRejected = $true
        } else {
            throw
        }
    }
    if (-not $failureJournalDropRejected) {
        throw "self-test failure journal drop was not rejected"
    }
    $after.image.source_port_request_failure_event_drop_count = 0
    $after.image.source_port_transport_failure_count = 2
    $after.image.source_port_image_failure_count = 2
    $after.image.source_port_temperature_failure_count = 1
    $after.image.source_port_request_failure_event_count_total = 2
    $after.image.source_port_recent_request_failure_events = @(
        [pscustomobject]@{
            event_sequence = 11
            event_at_utc = "2026-08-21T11:13:00.000Z"
            request_kind = "image"
            state = "failed"
            exception_class = "TimeoutError"
        }
    )
    $multiFailure = Get-ObservationDeltaReport -Before $before -After $after
    if (@($multiFailure.hard_failures).Count -lt 4 -or
        @($multiFailure.failure_events).Count -ne 1) {
        throw "self-test simultaneous failure aggregation was incomplete"
    }
    $after.image.source_port_transport_failure_count = 1
    $after.image.source_port_image_failure_count = 1
    $after.image.source_port_temperature_failure_count = 0
    $after.image.source_port_request_failure_event_count_total = 0
    $after.image.source_port_recent_request_failure_events = @()
    $after.image.source_port_transport_started_count = 21452
    $after.image.source_port_transport_success_count = 21452
    $rateReport = Get-ObservationDeltaReport -Before $before -After $after
    if (@($rateReport.hard_failures | Where-Object {
        $_ -like "transport-rate-over-6:*"
    }).Count -ne 1) {
        throw "self-test transport rate limit was not enforced"
    }

    $boundaryRoot = Join-Path `
        ([IO.Path]::GetTempPath()) `
        ("sfl-canary-boundary-{0}" -f [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $boundaryRoot | Out-Null
    try {
        $boundaryStart = [pscustomobject][ordered]@{
            schema_version = "spot-canary-observation-boundary-v1"
            boundary_role = "start"
            observed_at_completed = "2026-08-21T20:00:00+09:00"
            capture_latency_ms = 40
            monotonic_ticks = 1000
            monotonic_frequency = 1000
        }
        $boundaryEnd = [pscustomobject][ordered]@{
            schema_version = "spot-canary-observation-boundary-v1"
            boundary_role = "end"
            observed_at_completed = "2026-08-21T22:00:00+09:00"
            capture_latency_ms = 45
            monotonic_ticks = 7201000
            monotonic_frequency = 1000
        }
        $boundaryStart | ConvertTo-Json |
            Set-Content (Join-Path $boundaryRoot "canary-observation-start.json")
        $boundaryEnd | ConvertTo-Json |
            Set-Content (Join-Path $boundaryRoot "canary-observation-end.json")
        $boundaryPair = Get-ObservationBoundaryPair -SanitizedRoot $boundaryRoot
        if (-not [bool]$boundaryPair.valid) {
            throw "self-test valid observation boundaries were rejected"
        }
        $boundaryEnd.capture_latency_ms = 5001
        $boundaryEnd | ConvertTo-Json |
            Set-Content (Join-Path $boundaryRoot "canary-observation-end.json")
        $lateBoundary = Get-ObservationBoundaryPair -SanitizedRoot $boundaryRoot
        if ("observation-end-boundary-late" -notin
            @($lateBoundary.evidence_holds)) {
            throw "self-test late observation boundary was accepted"
        }
        Remove-Item `
            -LiteralPath (Join-Path $boundaryRoot "canary-observation-end.json")
        $missingBoundary = Get-ObservationBoundaryPair -SanitizedRoot $boundaryRoot
        if ("observation-end-boundary-missing" -notin
            @($missingBoundary.evidence_holds)) {
            throw "self-test missing observation boundary was accepted"
        }
    } finally {
        $resolvedBoundaryRoot = [IO.Path]::GetFullPath($boundaryRoot)
        $resolvedTempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $resolvedBoundaryRoot.StartsWith(
            $resolvedTempRoot,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            throw "self-test boundary cleanup path is unsafe"
        }
        Remove-Item -LiteralPath $resolvedBoundaryRoot -Recurse -Force
    }

    $postprocessEnd = [pscustomobject]@{
        backend_pid = 10
        port_8000_owner = 10
        build_git_commit = "commit"
        config_sha256 = "config"
    }
    $postprocessChanged = [pscustomobject]@{
        backend_pid = 11
        port_8000_owner = 11
        build_git_commit = "changed"
        config_sha256 = "changed"
    }
    $postprocessFailures = @(
        Get-PostprocessIntegrityFailures `
            -ObservationEnd $postprocessEnd `
            -PostprocessState $postprocessChanged
    )
    if ($postprocessFailures.Count -ne 4 -or
        @($deltas.hard_failures).Count -ne 0) {
        throw "self-test postprocess failures contaminated observation deltas"
    }

    $field.status = "FAILED"
    $collectorHolds = @(
        Get-CollectorEvidenceHolds -FieldSummary $field -CollectorExitCode 1
    )
    if (
        "collector-exit-1" -notin $collectorHolds -or
        "collector-status-failed" -notin $collectorHolds
    ) {
        throw "self-test collector failure was not classified as evidence hold"
    }
    if (
        (Get-CanaryExceptionResultName `
            -CollectionStarted $true `
            -Phase "collection") -cne "SPOT_120M_EVIDENCE_HOLD" -or
        (Get-CanaryExceptionResultName `
            -CollectionStarted $true `
            -Phase "postflight-runtime") -cne "SPOT_120M_EVIDENCE_HOLD"
    ) {
        throw "self-test canary exception classification mismatch"
    }

    $failedSwitchField = [pscustomobject]@{
        status = "FAILED"
        switch_evidence_status = "unavailable"
        switch_evidence_unavailable_declared = $true
        observation_elapsed_seconds = 8.852
    }
    if (-not (Test-SwitchEvidenceLimitation -FieldSummary $failedSwitchField)) {
        throw "self-test unavailable switch evidence was not reported"
    }
    if (Test-OperatorVisualConfirmationEligible -FieldSummary $failedSwitchField) {
        throw "self-test incomplete interval allowed operator confirmation"
    }
    $failedSwitchField.observation_elapsed_seconds = 7200
    if (-not (Test-OperatorVisualConfirmationEligible `
        -FieldSummary $failedSwitchField)) {
        throw "self-test complete interval blocked operator confirmation"
    }

    $identity = [pscustomobject]@{
        product = [pscustomobject]@{ version = "1.0.21" }
        rollback = [pscustomobject]@{
            version = "1.0.20"
            build_git_commit = "cd8cfa649203494cf087206cf656dc2197107ea1"
        }
    }
    $preinstall = [pscustomobject]@{ current_version = "1.0.20" }
    $baselineHealth = [pscustomobject]@{
        app_version = "1.0.20"
        spot_temperature = [pscustomobject]@{
            build_git_commit = "cd8cfa649203494cf087206cf656dc2197107ea1"
        }
    }
    Assert-RollbackBaselineEvidence `
        -Identity $identity `
        -PreinstallSummary $preinstall `
        -BaselineHealth $baselineHealth
    $preinstall.current_version = "1.0.16"
    $mismatchRejected = $false
    try {
        Assert-RollbackBaselineEvidence `
            -Identity $identity `
            -PreinstallSummary $preinstall `
            -BaselineHealth $baselineHealth
    } catch {
        $mismatchRejected = $true
    }
    if (-not $mismatchRejected) {
        throw "self-test mismatched rollback baseline was accepted"
    }

    $shortRuntimeEvidenceBase = Resolve-CanaryRuntimeEvidenceBase `
        -ExplicitPath "C:\SFLCanary"
    $projectedRuntimeEvidencePath = Assert-CanaryRuntimeEvidencePathBudget `
        -EvidenceBase $shortRuntimeEvidenceBase
    if (
        $shortRuntimeEvidenceBase -cne "C:\SFLCanary" -or
        $projectedRuntimeEvidencePath.Length -gt 240
    ) {
        throw "self-test short runtime evidence path was rejected"
    }
    $longRuntimeEvidenceBase = "C:\" + (("x" * 220) -join "")
    $longRuntimeEvidenceRejected = $false
    try {
        Assert-CanaryRuntimeEvidencePathBudget `
            -EvidenceBase $longRuntimeEvidenceBase |
            Out-Null
    } catch {
        $longRuntimeEvidenceRejected = $_.Exception.Message -like (
            "trigger-evidence-path-too-long:*"
        )
    }
    if (-not $longRuntimeEvidenceRejected) {
        throw "self-test long runtime evidence path was accepted"
    }
    Write-Output "SPOT_REALTIME_IMAGE_CANARY_120M_SELF_TEST_PASS"
}

if ($SelfTest) {
    Invoke-SelfTest
    exit 0
}

if ([string]::IsNullOrWhiteSpace($KitRoot)) {
    $KitRoot = $PSScriptRoot
}
$KitRoot = (Resolve-Path -LiteralPath $KitRoot).Path
if ([string]::IsNullOrWhiteSpace($ReleaseKitRoot)) {
    $ReleaseKitRoot = Split-Path -Parent $KitRoot
}
$ReleaseKitRoot = (Resolve-Path -LiteralPath $ReleaseKitRoot).Path

$identityPath = Join-Path $KitRoot "canary_kit_identity.json"
$identity = Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json
$evidenceRoot = Join-Path `
    $ReleaseKitRoot `
    ([string]$identity.prerequisite_15m.evidence_relative_path)
$configPath = Join-Path $env:APPDATA "SmartFactoryLogger\config.ini"
$integrityModulePath = Join-Path $KitRoot "backend_bundle_integrity.psm1"
$collectorPath = Join-Path $KitRoot "collect-spot-connecttimeout-evidence.ps1"
$framingAnalyzerPath = Join-Path $KitRoot "analyze-spot-http-framing.ps1"
$runtimeEvidencePathLimitChars = 240
$canaryEvidenceBase = Resolve-CanaryRuntimeEvidenceBase `
    -ExplicitPath $RuntimeEvidenceBase
$projectedRuntimeEvidencePath = Get-ProjectedRuntimeEvidencePath `
    -EvidenceBase $canaryEvidenceBase
$runtimeEvidenceProjectedPathChars = $projectedRuntimeEvidencePath.Length
$controlRoot = Join-Path `
    $evidenceRoot `
    ("canary-control-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Path $controlRoot -Force | Out-Null

$phase = "preflight"
$collectionStarted = $false
try {
    Assert-CanaryRuntimeEvidencePathBudget `
        -EvidenceBase $canaryEvidenceBase `
        -MaxPathChars $runtimeEvidencePathLimitChars |
        Out-Null

    & powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $KitRoot "verify-spot-realtime-image-canary-kit.ps1") `
        -KitRoot $KitRoot `
        -Quiet
    if ($LASTEXITCODE -ne 0) {
        throw "canary kit verification failed"
    }

    Assert-FileSha256 `
        -Path (Join-Path $ReleaseKitRoot $identity.product.installer_file) `
        -ExpectedSha256 $identity.product.installer_sha256 `
        -Label "v1.0.21 installer" | Out-Null
    if (
        (Split-Path -Leaf $RollbackInstallerPath) -cne
            [string]$identity.rollback.installer_file
    ) {
        throw "rollback installer file name does not match the verified baseline"
    }
    Assert-FileSha256 `
        -Path $RollbackInstallerPath `
        -ExpectedSha256 $identity.rollback.installer_sha256 `
        -Label "v1.0.20 rollback installer" | Out-Null
    Assert-EvidenceFiles -Identity $identity -EvidenceRoot $evidenceRoot

    $initialBefore = Get-InstalledState `
        -Identity $identity `
        -IntegrityModulePath $integrityModulePath `
        -ConfigPath $configPath `
        -Stage "120m preflight"
    $phase = "preflight-history-baseline"
    $historicalBaseline = Confirm-StableHistoricalFailureBaseline `
        -InitialState $initialBefore `
        -ConfigPath $configPath `
        -StabilitySeconds 30 `
        -ProgressIntervalSeconds 10
    $before = $historicalBaseline.state
    $historicalBaseline.evidence | ConvertTo-Json -Depth 10 |
        Set-Content `
            -LiteralPath (Join-Path $controlRoot "historical-failure-baseline.json") `
            -Encoding UTF8
    $before | ConvertTo-Json -Depth 10 |
        Set-Content -LiteralPath (Join-Path $controlRoot "canary-preflight.json") -Encoding UTF8
    $phase = "preflight"

    & powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File $collectorPath `
        -ObservationMinutes 120 `
        -StopOnNewSpotConnectTimeout `
        -PostTriggerCaptureSeconds 75 `
        -ProgressIntervalSeconds 30 `
        -EvidenceBase $canaryEvidenceBase `
        -FramingAnalyzerPath $framingAnalyzerPath `
        -PreflightOnly
    if ($LASTEXITCODE -ne 0) {
        throw "packet collector preflight failed: exit=$LASTEXITCODE"
    }

    if ($PreflightOnly) {
        [pscustomobject]@{
            result = "SPOT_120M_PREFLIGHT_PASS"
            version = $before.version
            build_commit = $before.build_git_commit
            backend_pid = $before.backend_pid
            config_sha256 = $before.config_sha256
            rollback_version = $identity.rollback.version
            rollback_build_commit = $identity.rollback.build_git_commit
            rollback_installer = $RollbackInstallerPath
            rollback_sha256 = $identity.rollback.installer_sha256
            evidence_path = $controlRoot
            runtime_evidence_base = $canaryEvidenceBase
            runtime_evidence_projected_path_chars = $runtimeEvidenceProjectedPathChars
            runtime_evidence_path_limit_chars = $runtimeEvidencePathLimitChars
            historical_failure_baseline = $historicalBaseline.evidence.classification
            historical_failure_stability_seconds = (
                $historicalBaseline.evidence.stability_duration_seconds
            )
            product_changes_performed = $false
        }
        exit 0
    }

    $phase = "collection"
    New-Item -ItemType Directory -Path $canaryEvidenceBase -Force | Out-Null
    $existingRuns = @(
        Get-ChildItem -LiteralPath $canaryEvidenceBase -Directory -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty FullName
    )
    $collectionStarted = $true
    & powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File $collectorPath `
        -ObservationMinutes 120 `
        -StopOnNewSpotConnectTimeout `
        -PostTriggerCaptureSeconds 75 `
        -ProgressIntervalSeconds 30 `
        -EvidenceBase $canaryEvidenceBase `
        -FramingAnalyzerPath $framingAnalyzerPath
    $collectorExitCode = $LASTEXITCODE

    $newRuns = @(
        Get-ChildItem -LiteralPath $canaryEvidenceBase -Directory |
            Where-Object { $_.FullName -notin $existingRuns } |
            Sort-Object LastWriteTime
    )
    if ($newRuns.Count -ne 1) {
        throw "could not identify exactly one new packet evidence run"
    }
    $runRoot = $newRuns[0].FullName
    $fieldSummaryPath = Join-Path `
        $runRoot `
        "sanitized_share\field_collection_summary.json"
    $framingSummaryPath = Join-Path `
        $runRoot `
        "sanitized_share\spot_http_framing_summary.json"
    if (
        -not (Test-Path -LiteralPath $fieldSummaryPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $framingSummaryPath -PathType Leaf)
    ) {
        throw "packet evidence summary is missing"
    }
    $fieldSummary = Get-Content -LiteralPath $fieldSummaryPath -Raw | ConvertFrom-Json
    $framingSummary = Get-Content -LiteralPath $framingSummaryPath -Raw | ConvertFrom-Json

    $phase = "evidence-evaluation"
    $sanitizedRoot = Join-Path $runRoot "sanitized_share"
    $boundary = Get-ObservationBoundaryPair -SanitizedRoot $sanitizedRoot
    $deltas = $null
    $observationHardFailures = New-Object System.Collections.Generic.List[string]
    $observationEvidenceHolds = New-Object System.Collections.Generic.List[string]
    foreach ($item in @($boundary.evidence_holds)) {
        [void]$observationEvidenceHolds.Add([string]$item)
    }
    if ([bool]$boundary.valid) {
        $deltas = Get-ObservationDeltaReport `
            -Before $boundary.start `
            -After $boundary.end
        foreach ($item in @($deltas.hard_failures)) {
            [void]$observationHardFailures.Add([string]$item)
        }
        foreach ($item in @($deltas.evidence_holds)) {
            [void]$observationEvidenceHolds.Add([string]$item)
        }
    } else {
        [void]$observationEvidenceHolds.Add("observation-delta-unavailable")
    }

    $postprocessIntegrityFailures = New-Object System.Collections.Generic.List[string]
    $postprocessState = $null
    if ($null -ne $boundary.end) {
        try {
            $postprocessState = Get-PostprocessState -ConfigPath $configPath
            foreach ($item in @(
                Get-PostprocessIntegrityFailures `
                    -ObservationEnd $boundary.end `
                    -PostprocessState $postprocessState
            )) {
                [void]$postprocessIntegrityFailures.Add([string]$item)
            }
        } catch {
            [void]$postprocessIntegrityFailures.Add(
                "postprocess-state-capture-failed:$($_.Exception.GetType().Name)"
            )
        }
    } else {
        [void]$postprocessIntegrityFailures.Add("postprocess-baseline-boundary-missing")
    }
    $postprocessState | ConvertTo-Json -Depth 10 |
        Set-Content `
            -LiteralPath (Join-Path $controlRoot "canary-postprocess-state.json") `
            -Encoding UTF8
    [pscustomobject][ordered]@{
        schema_version = "spot-canary-postflight-evaluation-v2"
        observation_start = $boundary.start
        observation_end = $boundary.end
        observation_hard_failures = @($observationHardFailures.ToArray())
        observation_evidence_holds = @($observationEvidenceHolds.ToArray())
        postprocess_integrity_failures = @($postprocessIntegrityFailures.ToArray())
    } | ConvertTo-Json -Depth 12 |
        Set-Content `
            -LiteralPath (Join-Path $controlRoot "canary-postflight.json") `
            -Encoding UTF8

    $packet = Test-PacketEvidence `
        -FieldSummary $fieldSummary `
        -FramingSummary $framingSummary

    foreach ($item in @($observationHardFailures.ToArray())) {
        $packet.hard_failures += [string]$item
    }
    foreach ($item in @($observationEvidenceHolds.ToArray())) {
        $packet.evidence_holds += [string]$item
    }

    foreach (
        $collectorHold in @(
            Get-CollectorEvidenceHolds `
                -FieldSummary $fieldSummary `
                -CollectorExitCode $collectorExitCode
        )
    ) {
        $packet.evidence_holds += $collectorHold
    }

    $operatorEligible = (
        [bool]$boundary.valid -and
        (Test-OperatorVisualConfirmationEligible -FieldSummary $fieldSummary)
    )
    $operatorAnswer = if ($operatorEligible) {
        Read-Host (
            "120분 전체 구간 동안 SPOT 영상이 계속 갱신되고 화면 오류가 없었습니까? " +
            "정상인 경우 YES 입력"
        )
    } else {
        $packet.evidence_holds += (
            "operator-visual-confirmation-not-requested-incomplete-interval"
        )
        "NOT_REQUESTED_INCOMPLETE_INTERVAL"
    }
    $operatorEvidence = [pscustomobject]@{
        recorded_at = (Get-Date).ToString("o")
        confirmed_at = if ($operatorEligible) {
            (Get-Date).ToString("o")
        } else {
            $null
        }
        answer = $operatorAnswer
        prompted = $operatorEligible
        eligible = $operatorEligible
        full_interval_required = $true
        minimum_elapsed_seconds = 7190.0
        observed_elapsed_seconds = $fieldSummary.observation_elapsed_seconds
    }
    $operatorEvidence | ConvertTo-Json |
        Set-Content `
            -LiteralPath (Join-Path $controlRoot "operator-visual-confirmation-120m.json") `
            -Encoding UTF8
    if ($operatorEligible -and $operatorAnswer -cne "YES") {
        $packet.hard_failures += "operator-visual-confirmation-failed"
    }

    $switchLimited = Test-SwitchEvidenceLimitation -FieldSummary $fieldSummary
    $resultName = if (@($packet.hard_failures).Count -gt 0) {
        "SPOT_120M_ROLLBACK_REQUIRED"
    } elseif (@($packet.evidence_holds).Count -gt 0 -or
        $postprocessIntegrityFailures.Count -gt 0) {
        "SPOT_120M_EVIDENCE_HOLD"
    } elseif ($switchLimited) {
        "SPOT_120M_PASS_WITH_SWITCH_LIMITATION"
    } else {
        "SPOT_120M_GATE_PASS"
    }
    $result = [pscustomobject][ordered]@{
        result = $resultName
        classification = $identity.classification
        production_promotion_allowed = $false
        version = if ($null -eq $boundary.end) {
            $null
        } else {
            $boundary.end.app_version
        }
        build_commit = if ($null -eq $boundary.end) {
            $null
        } else {
            $boundary.end.build_git_commit
        }
        backend_pid = if ($null -eq $boundary.end) {
            $null
        } else {
            $boundary.end.backend_pid
        }
        observation_elapsed_seconds = $fieldSummary.observation_elapsed_seconds
        event_trigger_detected = $fieldSummary.event_trigger_detected
        collector_status = $fieldSummary.status
        collector_exit_code = $collectorExitCode
        switch_limitation = $switchLimited
        operator_visual_confirmation = (
            $operatorEligible -and $operatorAnswer -ceq "YES"
        )
        counter_rate_window = $identity.canary.counter_rate_window
        deltas = $deltas
        failure_counter_deltas = if ($null -eq $deltas) {
            $null
        } else {
            $deltas.failure_counter_deltas
        }
        failure_events = if ($null -eq $deltas) {
            @()
        } else {
            @($deltas.failure_events)
        }
        hard_failures = @($packet.hard_failures)
        evidence_holds = @($packet.evidence_holds)
        postprocess_integrity_failures = @(
            $postprocessIntegrityFailures.ToArray()
        )
        observation_boundary = [pscustomobject][ordered]@{
            schema_version = "spot-canary-observation-boundary-v1"
            valid = [bool]$boundary.valid
            start_path = $boundary.start_path
            end_path = $boundary.end_path
        }
        packet_gate = $packet
        packet_evidence_run = $runRoot
        sanitized_zip = Join-Path `
            $runRoot `
            ("{0}_sanitized_share.zip" -f $fieldSummary.run_id)
        sanitized_zip_sha256_file = Join-Path $runRoot "sanitized_share_sha256.txt"
        rollback_version = $identity.rollback.version
        rollback_build_commit = $identity.rollback.build_git_commit
        rollback_installer = $RollbackInstallerPath
        rollback_sha256 = $identity.rollback.installer_sha256
        control_evidence_path = $controlRoot
        runtime_evidence_base = $canaryEvidenceBase
        runtime_evidence_projected_path_chars = $runtimeEvidenceProjectedPathChars
        runtime_evidence_path_limit_chars = $runtimeEvidencePathLimitChars
    }
    $result | ConvertTo-Json -Depth 12 |
        Set-Content -LiteralPath (Join-Path $controlRoot "canary-120m-gate.json") -Encoding UTF8
    $result

    if ($resultName -eq "SPOT_120M_ROLLBACK_REQUIRED") {
        exit 10
    }
    if ($resultName -eq "SPOT_120M_EVIDENCE_HOLD") {
        exit 3
    }
    if ($resultName -eq "SPOT_120M_PASS_WITH_SWITCH_LIMITATION") {
        exit 2
    }
    exit 0
} catch {
    $failureResult = Get-CanaryExceptionResultName `
        -CollectionStarted $collectionStarted `
        -Phase $phase
    $failure = [pscustomobject][ordered]@{
        result = $failureResult
        phase = $phase
        failed_at = (Get-Date).ToString("o")
        error_type = $_.Exception.GetType().FullName
        error_message = $_.Exception.Message
        collection_started = $collectionStarted
        rollback_required = $failureResult -ceq "SPOT_120M_ROLLBACK_REQUIRED"
        product_changes_performed_by_canary = $false
        rollback_version = $identity.rollback.version
        rollback_build_commit = $identity.rollback.build_git_commit
        rollback_installer = $RollbackInstallerPath
        rollback_sha256 = $identity.rollback.installer_sha256
        control_evidence_path = $controlRoot
        runtime_evidence_base = $canaryEvidenceBase
        runtime_evidence_projected_path_chars = $runtimeEvidenceProjectedPathChars
        runtime_evidence_path_limit_chars = $runtimeEvidencePathLimitChars
    }
    $failure | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath (Join-Path $controlRoot "canary-120m-failure.json") -Encoding UTF8
    $failure | Format-List | Out-String | Write-Host
    if ($failureResult -ceq "SPOT_120M_ROLLBACK_REQUIRED") {
        exit 10
    }
    if ($failureResult -ceq "SPOT_120M_EVIDENCE_HOLD") {
        exit 3
    }
    exit 1
}
