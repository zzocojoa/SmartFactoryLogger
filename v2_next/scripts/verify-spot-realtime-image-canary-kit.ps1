[CmdletBinding()]
param(
    [string]$KitRoot = "",

    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$expectedPackageFiles = @(
    "SPOT_REALTIME_IMAGE_CANARY_120M_GUIDE.md",
    "analyze-spot-http-framing.ps1",
    "backend_bundle_integrity.psm1",
    "canary_kit_files_sha256.txt",
    "canary_kit_identity.json",
    "collect-spot-connecttimeout-evidence.ps1",
    "collect_operational_observability.ps1",
    "invoke-spot-realtime-image-canary-120m.ps1",
    "monitor-spot-connecttimeout-trigger.ps1",
    "operator_attestation_15m.json",
    "run-spot-realtime-image-canary-120m-as-admin.cmd",
    "verify-spot-realtime-image-canary-kit.ps1"
) | Sort-Object
$manifestFileName = "canary_kit_files_sha256.txt"
$expectedManifestFiles = @(
    $expectedPackageFiles | Where-Object { $_ -ne $manifestFileName }
) | Sort-Object

if ([string]::IsNullOrWhiteSpace($KitRoot)) {
    $KitRoot = $PSScriptRoot
}
if (-not (Test-Path -LiteralPath $KitRoot -PathType Container)) {
    throw "The extracted v1.0.22 server-validation kit folder was not found."
}
$resolvedKitRoot = (Resolve-Path -LiteralPath $KitRoot).Path
$manifestPath = Join-Path $resolvedKitRoot $manifestFileName
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "canary_kit_files_sha256.txt is missing. Do not run the canary."
}

$rows = @()
$seenNames = @{}
foreach ($line in Get-Content -LiteralPath $manifestPath -Encoding ascii) {
    if ([string]::IsNullOrWhiteSpace($line)) {
        continue
    }
    if ($line -notmatch "^(?<hash>[A-Fa-f0-9]{64})  (?<name>[^\\/]+)$") {
        throw "The canary kit hash manifest format is invalid."
    }
    $name = [string]$Matches.name
    if ($seenNames.ContainsKey($name)) {
        throw "Duplicate canary kit manifest file: $name"
    }
    $seenNames[$name] = $true
    $rows += [pscustomobject]@{
        Name = $name
        ExpectedSha256 = ([string]$Matches.hash).ToUpperInvariant()
    }
}

$manifestNames = @($rows.Name | Sort-Object)
if (($manifestNames -join "`n") -cne ($expectedManifestFiles -join "`n")) {
    throw "The canary kit hash manifest file list is not approved."
}
$actualFiles = @(
    Get-ChildItem -LiteralPath $resolvedKitRoot -File |
        Select-Object -ExpandProperty Name |
        Sort-Object
)
if (($actualFiles -join "`n") -cne ($expectedPackageFiles -join "`n")) {
    throw "The canary kit contains a missing or unexpected file."
}

$results = foreach ($row in $rows) {
    $path = Join-Path $resolvedKitRoot $row.Name
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    [pscustomobject]@{
        FileName = $row.Name
        Match = $actual -ceq $row.ExpectedSha256
        Sha256 = $actual
    }
}
if (@($results | Where-Object { -not $_.Match }).Count -ne 0) {
    throw "A canary kit file SHA-256 does not match. Do not run the canary."
}

$identity = Get-Content `
    -LiteralPath (Join-Path $resolvedKitRoot "canary_kit_identity.json") `
    -Raw |
    ConvertFrom-Json
if (
    $identity.schema_version -cne "spot-realtime-image-v1022-canary-kit-v2" -or
    $identity.classification -cne "PRIVATE_UNSIGNED_INTERNAL_CANARY_ONLY" -or
    [bool]$identity.production_promotion_allowed -or
    $identity.product.version -cne "1.0.22" -or
    $identity.product.build_git_commit -cne
        "5cc34b4fffd70195ec7fdd9d27acf4880cecbd80" -or
    $identity.product.release_kit_folder -cne
        "spot-realtime-image-performance-v1.0.22-5cc34b4" -or
    $identity.product.release_identity_file -cne "release_identity.json" -or
    $identity.product.release_identity_sha256 -cne
        "3AB24AE19B127C3344DE59A345E668ED429B77D29F5C2BE8EE032B7B15262F32" -or
    $identity.product.installer_sha256 -cne
        "77577ABB08BD901365B2D366B5ABAF101217E90B8AA5F2E9CB47971FF03123E2" -or
    $identity.product.app_asar_sha256 -cne
        "B13909D1A6067E94EC945750C82F17948FC597D3A29060323E807193650F0327" -or
    $identity.product.backend_bundle_sha256 -cne
        "E171DF1C3EB3C8DB78700E95913E87E7B1EE95460990F6B342AD4E0165448C2C" -or
    [int]$identity.product.backend_bundle_file_count -ne 1501 -or
    $identity.product.source_port_policy_version -cne
        "spot-source-port-quarantine-v3" -or
    [double]$identity.product.source_port_minimum_required_reuse_interval_seconds -ne
        75.0 -or
    [double]$identity.product.source_port_quarantine_safety_margin_seconds -ne
        2.0 -or
    [double]$identity.product.source_port_quarantine_seconds -ne 77.0 -or
    [int]$identity.product.source_port_pool_capacity -ne 768 -or
    [int]$identity.product.source_port_minimum_required_pool_capacity -ne 462 -or
    $identity.product.config_sha256 -cne
        "6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E" -or
    $identity.rollback.version -cne "1.0.20" -or
    $identity.rollback.build_git_commit -cne
        "cd8cfa649203494cf087206cf656dc2197107ea1" -or
    $identity.rollback.installer_file -cne
        "smart-factory-logger-v2 Setup 1.0.20.exe" -or
    $identity.rollback.installer_sha256 -cne
        "F3C52902EFA2081A5060D4CD2C579E8B20B9DBA2DE34E174C946390BEDA0DE19" -or
    $identity.rollback.baseline_preinstall_summary_file -cne
        "preinstall-summary.json" -or
    $identity.rollback.baseline_health_file -cne "health-before.json" -or
    $identity.diagnostic_core.source_commit -cne
        "8ec69b31ba6ba8cadc6c6360a9ea18dbed54cf96" -or
    $identity.diagnostic_core.source_identity -cne
        "spot-connecttimeout-trigger-field-kit-v7" -or
    $identity.diagnostic_core.framing_schema -cne
        "spot-http-framing-evidence-v7" -or
    $identity.diagnostic_core.observation_boundary_schema -cne
        "spot-canary-observation-boundary-v1" -or
    $identity.diagnostic_core.packet_timestamp_ordering_policy -cne
        "timestamp-sorted-stable-v1" -or
    $identity.diagnostic_core.same_four_tuple_reuse_ordering_policy -cne
        "timestamp-sorted-per-four-tuple-v1" -or
    $identity.diagnostic_core.packet_timing_uncertainty_policy -cne
        "evidence-hold" -or
    $identity.diagnostic_core.trigger_monitor_error_event_schema -cne
        "spot-trigger-monitor-error-event-raw-v1" -or
    $identity.diagnostic_core.trigger_monitor_integrity_policy -cne
        "recovered-errors-within-detection-threshold-are-complete" -or
    $identity.diagnostic_core.trigger_monitor_completion_policy -cne
        "observer-deadline-atomic-request" -or
    $identity.diagnostic_core.trigger_monitor_completion_request_schema -cne
        "spot-trigger-monitor-completion-request-v1" -or
    [int]$identity.diagnostic_core.trigger_monitor_completion_request_grace_seconds -ne
        30 -or
    $identity.diagnostic_core.parent_capture_stop_signal_policy -cne
        "nonblocking-poll-and-five-second-fail-closed" -or
    [int]$identity.diagnostic_core.capture_stop_signal_observation_max_delay_seconds -ne
        5 -or
    $identity.diagnostic_core.postprocess_state_schema -cne
        "spot-canary-postprocess-state-v1" -or
    -not [bool]$identity.diagnostic_core.product_request_behavior_changed -or
    [int]$identity.canary.maximum_observation_minutes -ne 120 -or
    [int]$identity.canary.post_trigger_capture_seconds -ne 75 -or
    [int]$identity.canary.progress_interval_seconds -ne 30 -or
    $identity.canary.progress_source -cne "local-clock-and-process-state-only" -or
    -not [bool]$identity.canary.stop_on_new_spot_connecttimeout -or
    -not [bool]$identity.canary.same_four_tuple_minimum_75s_required -or
    $identity.canary.required_source_port_policy_version -cne
        "spot-source-port-quarantine-v3" -or
    [double]$identity.canary.source_port_minimum_required_reuse_interval_seconds -ne
        75.0 -or
    [double]$identity.canary.source_port_quarantine_safety_margin_seconds -ne
        2.0 -or
    [double]$identity.canary.source_port_quarantine_seconds -ne 77.0 -or
    [int]$identity.canary.source_port_pool_capacity -ne 768 -or
    [int]$identity.canary.source_port_minimum_required_pool_capacity -ne 462 -or
    -not [bool]$identity.canary.packet_capture_full_window_required -or
    $identity.canary.counter_rate_window -cne
        "observation-start-to-observation-end" -or
    $identity.canary.postprocess_failure_policy -cne
        "separate-evidence-hold" -or
    [int]$identity.canary.observation_end_snapshot_max_delay_seconds -ne 5 -or
    $identity.canary.historical_failure_counter_policy -cne
        "stable-preflight-baseline-and-zero-canary-delta" -or
    $identity.canary.general_request_event_drop_policy -cne
        "bounded-journal-eviction-observability-only" -or
    [int]$identity.canary.historical_failure_stability_seconds -ne 30 -or
    [int]$identity.canary.historical_failure_progress_interval_seconds -ne 10 -or
    $identity.canary.collector_failure_without_runtime_hard_gate -cne
        "evidence-hold" -or
    $identity.prerequisite_15m.result -cne "PENDING_SERVER_VALIDATION" -or
    [bool]$identity.prerequisite_15m.full_120m_allowed -or
    @($identity.prerequisite_15m.evidence_files).Count -ne 0 -or
    [bool]$identity.contains_installer -or
    [bool]$identity.contains_product_binary -or
    [bool]$identity.changes_application_or_settings -or
    [bool]$identity.restarts_application -or
    [bool]$identity.clears_error_queue
) {
    throw "The canary kit identity is not the approved v1.0.22 validation contract."
}
if ($identity.tooling_source_commit -notmatch "^[0-9a-f]{40}$") {
    throw "The canary tooling source commit is invalid."
}

$attestation = Get-Content `
    -LiteralPath (Join-Path $resolvedKitRoot "operator_attestation_15m.json") `
    -Raw |
    ConvertFrom-Json
if (
    $attestation.schema_version -cne "spot-operator-visual-attestation-v1" -or
    $attestation.product_version -cne "1.0.22" -or
    $attestation.build_git_commit -cne
        "5cc34b4fffd70195ec7fdd9d27acf4880cecbd80" -or
    $attestation.evidence_kind -cne "pending-server-validation" -or
    $attestation.status -cne "PENDING" -or
    $null -ne $attestation.continuous_spot_image_refresh -or
    $null -ne $attestation.screen_error_observed
) {
    throw "The pending v1.0.22 15-minute attestation contract is invalid."
}

$collectorSource = Get-Content `
    -LiteralPath (Join-Path $resolvedKitRoot "collect-spot-connecttimeout-evidence.ps1") `
    -Raw
if (
    $collectorSource -notmatch "ProgressIntervalSeconds = 30" -or
    $collectorSource -notmatch "\[CANARY PROGRESS\]" -or
    $collectorSource -notmatch "local clock/process only; no added SPOT requests" -or
    $collectorSource -notmatch "spot-canary-observation-boundary-v1" -or
    $collectorSource -notmatch "canary-observation-start.json" -or
    $collectorSource -notmatch "canary-observation-end.json" -or
    $collectorSource -notmatch "Wait-CollectorStopSignal" -or
    $collectorSource -notmatch "capture-stop-signal-observed-within-5s" -or
    $collectorSource -notmatch "canary-postprocess-state.json" -or
    $collectorSource -notmatch "boundary_signal_nonblocking=true"
) {
    throw "The canary progress contract is missing."
}
$analyzerSource = Get-Content `
    -LiteralPath (Join-Path $resolvedKitRoot "analyze-spot-http-framing.ps1") `
    -Raw
if (
    $analyzerSource -notmatch "spot-http-framing-evidence-v7" -or
    $analyzerSource -notmatch "duplicate_initial_syn_count" -or
    $analyzerSource -notmatch "monotonic_corrected" -or
    $analyzerSource -notmatch "timestamp-sorted-stable-v1" -or
    $analyzerSource -notmatch "initial_syn_timestamp_regression_max_ms" -or
    $analyzerSource -notmatch "excluded_before_count" -or
    $analyzerSource -notmatch "excluded_after_count"
) {
    throw "The packet measurement v7 contract is missing."
}
$monitorSource = Get-Content `
    -LiteralPath (Join-Path $resolvedKitRoot "monitor-spot-connecttimeout-trigger.ps1") `
    -Raw
if (
    $monitorSource -notmatch "spot-trigger-monitor-error-event-raw-v1" -or
    $monitorSource -notmatch
        "complete-recovered-transient-errors" -or
    $monitorSource -notmatch
        "recovered-errors-within-detection-threshold-are-complete"
) {
    throw "The trigger monitor recoverability evidence contract is missing."
}

if (-not $Quiet) {
    $results | Format-Table -AutoSize
    Write-Host (
        "[PASS] v1.0.22 server-validation kit identity and SHA-256 values are valid."
    ) -ForegroundColor Green
}
