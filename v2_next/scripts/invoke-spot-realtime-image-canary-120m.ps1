[CmdletBinding()]
param(
    [string]$KitRoot = "",

    [string]$ReleaseKitRoot = "",

    [string]$RollbackInstallerPath = (
        "C:\Users\user\Desktop\SmartFactory\" +
        "v1020_cd8cfa6_internal_private_server_deploy_20260821_R3\" +
        "smart-factory-logger-v2 Setup 1.0.20.exe"
    ),

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

    $beforeText = [string](Get-RequiredProperty `
        -InputObject $Before `
        -Name "observed_at" `
        -Context "preflight installed state")
    $afterText = [string](Get-RequiredProperty `
        -InputObject $After `
        -Name "observed_at" `
        -Context "postflight installed state")
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
    if ($Phase -ceq "postflight-runtime") {
        return "SPOT_120M_ROLLBACK_REQUIRED"
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
    return [pscustomobject]$snapshot
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

    $zeroFields = @(
        "source_port_pool_acquire_wait_count",
        "source_port_pool_exhaustion_count",
        "source_port_reuse_violation_count",
        "source_port_transport_failure_count",
        "source_port_image_failure_count",
        "source_port_temperature_failure_count",
        "source_port_internal_temperature_failure_count",
        "source_port_diagnostic_failure_count",
        "image_refresh_failure_count",
        "image_cache_clock_anomaly_count"
    )
    foreach ($name in $zeroFields) {
        if ([int64]$Image.$name -ne 0) {
            throw "$Stage non-zero failure counter: $name=$($Image.$name)"
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

function Assert-PostflightDeltas {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Before,

        [Parameter(Mandatory = $true)]
        [object]$After
    )

    if ($After.backend_pid -ne $Before.backend_pid) {
        throw "backend restarted during the 120-minute canary"
    }
    if ($After.electron_path -cne $Before.electron_path) {
        throw "Electron executable path changed during the 120-minute canary"
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
    if ($transportDelta -le 0 -or $successDelta -le 0 -or $imageDelta -le 0) {
        throw "SPOT transport or image counters did not progress"
    }
    if ($successDelta -gt $transportDelta) {
        throw "SPOT transport counter relationship is invalid"
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
        throw "SPOT average transport rate exceeded 6/s: $transportRate"
    }
    if ($imageRate -gt 3.2) {
        throw "SPOT average image upstream rate exceeded 3.2/s: $imageRate"
    }

    return [pscustomobject][ordered]@{
        transport_started_delta = $transportDelta
        transport_success_delta = $successDelta
        image_upstream_delta = $imageDelta
        counter_window_elapsed_seconds = $counterWindowElapsedSeconds
        transport_rate_per_sec = $transportRate
        image_upstream_rate_per_sec = $imageRate
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
    if ([int]$FieldSummary.event_trigger_monitor_error_count -ne 0) {
        [void]$holds.Add("trigger-monitor-error")
    }
    if ($FieldSummary.packet_direction_preflight -ne "passed") {
        [void]$holds.Add("packet-direction-preflight")
    }
    if ($FieldSummary.framing_analysis_status -ne "completed") {
        [void]$holds.Add("framing-analysis-incomplete")
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

    if ($FramingSummary.schema_version -ne "spot-http-framing-evidence-v5") {
        [void]$holds.Add("framing-schema-mismatch")
    }
    if (
        [bool]$FramingSummary.capture_coverage.overwrite_detected -or
        $FramingSummary.capture_coverage.status -ne "capture-window-retained"
    ) {
        [void]$holds.Add("packet-capture-window-incomplete")
    }

    $tcp = $FramingSummary.tcp_connection_summary
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
        [void]$holds.Add("syn-retransmission-observed")
    }

    $reuse = $tcp.same_four_tuple_reuse
    if ([int]$reuse.under_60000_ms_count -ne 0) {
        [void]$hardFailures.Add("same-four-tuple-reuse-under-60s")
    }
    if (
        [int]$reuse.observed_count -gt 0 -and
        [double]$reuse.interval_ms_min -lt 75000.0
    ) {
        [void]$hardFailures.Add("same-four-tuple-reuse-under-75s")
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
        source_port_transport_failure_count = 0
        source_port_bind_collision_count = 0
        source_port_image_failure_count = 0
        source_port_temperature_failure_count = 0
        source_port_internal_temperature_failure_count = 0
        source_port_diagnostic_failure_count = 0
        request_budget_within_target = $true
        request_budget_total_background_max_per_sec = 6.0
        image_upstream_request_count = 5
        image_refresh_success_count = 5
        image_refresh_failure_count = 0
        image_cache_clock_anomaly_count = 0
    }
    $snapshot = ConvertTo-SafeImageSnapshot -Image $image
    Assert-ImageGate -Image $snapshot -Stage "self-test"

    $field = [pscustomobject]@{
        status = "COMPLETED"
        event_trigger_detected = $false
        event_trigger_monitor_error_count = 0
        packet_direction_preflight = "passed"
        framing_analysis_status = "completed"
        windows_tcp_ipv4_evidence_status = "completed"
        packet_payload_artifacts_retained = $false
        observation_elapsed_seconds = 7200
        required_evidence_missing = @()
    }
    $framing = [pscustomobject]@{
        schema_version = "spot-http-framing-evidence-v5"
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
                observed_count = 1
                interval_ms_min = 75000
                under_60000_ms_count = 0
            }
        }
        server_close_counts = [pscustomobject]@{ reset = 0 }
    }
    $packet = Test-PacketEvidence -FieldSummary $field -FramingSummary $framing
    if ($packet.hard_failures.Count -ne 0 -or $packet.evidence_holds.Count -ne 0) {
        throw "self-test valid packet evidence was rejected"
    }
    $framing.tcp_connection_summary.same_four_tuple_reuse.interval_ms_min = 74999
    $packet = Test-PacketEvidence -FieldSummary $field -FramingSummary $framing
    if ("same-four-tuple-reuse-under-75s" -notin $packet.hard_failures) {
        throw "self-test short reuse interval was not rejected"
    }

    $before = [pscustomobject]@{
        observed_at = "2026-08-21T20:12:04.2365692+09:00"
        backend_pid = 10
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
        electron_path = "C:\Program Files\SmartFactory\smart-factory.exe"
        image = [pscustomobject]@{
            source_port_transport_started_count = 21426
            source_port_transport_success_count = 21426
            image_upstream_request_count = 9986
        }
    }
    $deltas = Assert-PostflightDeltas -Before $before -After $after
    if (
        [math]::Abs(
            [double]$deltas.counter_window_elapsed_seconds - 59.4678005
        ) -gt 0.0001 -or
        [double]$deltas.transport_rate_per_sec -ne 5.5829 -or
        [double]$deltas.image_upstream_rate_per_sec -ne 2.7578
    ) {
        throw "self-test counter-window rate calculation mismatch"
    }
    $after.image.source_port_transport_started_count = 21452
    $after.image.source_port_transport_success_count = 21452
    $rateLimitRejected = $false
    try {
        Assert-PostflightDeltas -Before $before -After $after | Out-Null
    } catch {
        $rateLimitRejected = $_.Exception.Message -like (
            "SPOT average transport rate exceeded 6/s:*"
        )
    }
    if (-not $rateLimitRejected) {
        throw "self-test transport rate limit was not enforced"
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
            -Phase "postflight-runtime") -cne "SPOT_120M_ROLLBACK_REQUIRED"
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
$canaryEvidenceBase = Join-Path $evidenceRoot "canary-120m"
$controlRoot = Join-Path `
    $evidenceRoot `
    ("canary-control-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Path $controlRoot -Force | Out-Null

$phase = "preflight"
$collectionStarted = $false
try {
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

    $before = Get-InstalledState `
        -Identity $identity `
        -IntegrityModulePath $integrityModulePath `
        -ConfigPath $configPath `
        -Stage "120m preflight"
    $before | ConvertTo-Json -Depth 10 |
        Set-Content -LiteralPath (Join-Path $controlRoot "canary-preflight.json") -Encoding UTF8

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

    $phase = "postflight-runtime"
    $after = Get-InstalledState `
        -Identity $identity `
        -IntegrityModulePath $integrityModulePath `
        -ConfigPath $configPath `
        -Stage "120m postflight"
    $after | ConvertTo-Json -Depth 10 |
        Set-Content -LiteralPath (Join-Path $controlRoot "canary-postflight.json") -Encoding UTF8
    $deltas = Assert-PostflightDeltas `
        -Before $before `
        -After $after
    $phase = "evidence-evaluation"
    $packet = Test-PacketEvidence `
        -FieldSummary $fieldSummary `
        -FramingSummary $framingSummary

    foreach (
        $collectorHold in @(
            Get-CollectorEvidenceHolds `
                -FieldSummary $fieldSummary `
                -CollectorExitCode $collectorExitCode
        )
    ) {
        $packet.evidence_holds += $collectorHold
    }

    $operatorEligible = Test-OperatorVisualConfirmationEligible `
        -FieldSummary $fieldSummary
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
    } elseif (@($packet.evidence_holds).Count -gt 0) {
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
        version = $after.version
        build_commit = $after.build_git_commit
        backend_pid = $after.backend_pid
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
