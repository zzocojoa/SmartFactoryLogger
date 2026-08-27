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
    throw "The extracted v1.0.21 canary kit folder was not found."
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
    $identity.schema_version -cne "spot-realtime-image-v1021-canary-kit-v3" -or
    $identity.classification -cne "PRIVATE_UNSIGNED_INTERNAL_CANARY_ONLY" -or
    [bool]$identity.production_promotion_allowed -or
    $identity.product.version -cne "1.0.21" -or
    $identity.product.build_git_commit -cne
        "5971fc4fbdeec07ef65681a945319f0ae12d55cb" -or
    $identity.product.installer_sha256 -cne
        "01CF544C999FB21FADB7F36965DC35FB9E8AEE36D1EEBD3319A1EB7296AD191A" -or
    $identity.product.app_asar_sha256 -cne
        "50734BC222DF943A2DC6605E35EDEA0AD600C909A0A32E4ADEFF2A2A0952C048" -or
    $identity.product.backend_bundle_sha256 -cne
        "B818383DF7B035DC73C86E57F0080489B287C958086C8E2C426639C0622CB094" -or
    [int]$identity.product.backend_bundle_file_count -ne 1385 -or
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
        "1f4e0f61622ca6e0865a6e96e23aa1d86cfda3c3" -or
    $identity.diagnostic_core.framing_schema -cne
        "spot-http-framing-evidence-v6" -or
    $identity.diagnostic_core.observation_boundary_schema -cne
        "spot-canary-observation-boundary-v1" -or
    [int]$identity.canary.maximum_observation_minutes -ne 120 -or
    [int]$identity.canary.post_trigger_capture_seconds -ne 75 -or
    [int]$identity.canary.progress_interval_seconds -ne 30 -or
    $identity.canary.progress_source -cne "local-clock-and-process-state-only" -or
    -not [bool]$identity.canary.stop_on_new_spot_connecttimeout -or
    -not [bool]$identity.canary.same_four_tuple_minimum_75s_required -or
    -not [bool]$identity.canary.packet_capture_full_window_required -or
    $identity.canary.counter_rate_window -cne
        "observation-start-to-observation-end" -or
    $identity.canary.postprocess_failure_policy -cne
        "separate-evidence-hold" -or
    [int]$identity.canary.observation_end_snapshot_max_delay_seconds -ne 5 -or
    $identity.canary.historical_failure_counter_policy -cne
        "stable-preflight-baseline-and-zero-canary-delta" -or
    [int]$identity.canary.historical_failure_stability_seconds -ne 30 -or
    [int]$identity.canary.historical_failure_progress_interval_seconds -ne 10 -or
    $identity.canary.collector_failure_without_runtime_hard_gate -cne
        "evidence-hold" -or
    [bool]$identity.contains_installer -or
    [bool]$identity.contains_product_binary -or
    [bool]$identity.changes_application_or_settings -or
    [bool]$identity.restarts_application -or
    [bool]$identity.clears_error_queue
) {
    throw "The canary kit identity is not the approved v1.0.21 contract."
}
if ($identity.tooling_source_commit -notmatch "^[0-9a-f]{40}$") {
    throw "The canary tooling source commit is invalid."
}

$expectedEvidence = [ordered]@{
    "backend-integrity-after-install.json" = "6D077E7944C5670A6990862209C6D7A10935E13B01D920AF3D270538A5147058"
    "health-after-15m.json" = "9CD044E41D5A42AA72F94275B18AC1CBDB786AA44C5BCD0E836CF6772B883322"
    "health-before.json" = "2E16E28BD695B5D9125EF11822E4E10DA2D422E0D1781EE72A623D1EE0A97063"
    "health-before-15m.json" = "12653336422E897764C47069F7CAE5F2C876B8B27591CDF7D52AB6ED6F982021"
    "postinstall-bundle-gate.json" = "E42CF3126CD5CC42F38918D0E64CF9C302A860FB00DD8B8030B676EF20147994"
    "preinstall-summary.json" = "06F076A09D7D659B88A92959769CD1528802EC08E3C0A13F35A6A8329FF32138"
    "spot-15m.json" = "464BF0A540133C5165B7E550430EDA9EDAA07FA866481B43FAD2B0392016A4F8"
    "spot-config-image-after-15m.json" = "1859E0E79C7D24348132B93B8D2EBFA50FBD0166762F7A4F1A16B41C15A6D100"
    "spot-config-image-before-15m.json" = "7E7486908045EF4898F44CA474816C647EAC1C5619EAADA6B3DA6445E5C87342"
}
$identityEvidence = @($identity.prerequisite_15m.evidence_files)
if ($identityEvidence.Count -ne $expectedEvidence.Count) {
    throw "The prerequisite 15-minute evidence file count is invalid."
}
foreach ($entry in $identityEvidence) {
    if (
        -not $expectedEvidence.Contains([string]$entry.file) -or
        $expectedEvidence[[string]$entry.file] -cne ([string]$entry.sha256)
    ) {
        throw "The prerequisite 15-minute evidence identity is invalid."
    }
}

$attestation = Get-Content `
    -LiteralPath (Join-Path $resolvedKitRoot "operator_attestation_15m.json") `
    -Raw |
    ConvertFrom-Json
if (
    $attestation.schema_version -cne "spot-operator-visual-attestation-v1" -or
    $attestation.product_version -cne "1.0.21" -or
    $attestation.observation_date_kst -cne "2026-08-21" -or
    $attestation.observation_start_kst -cne "19:13" -or
    $attestation.observation_end_kst -cne "19:28" -or
    $attestation.continuous_spot_image_refresh -ne $true -or
    $attestation.screen_error_observed -ne $false -or
    $attestation.evidence_kind -cne "human-attestation"
) {
    throw "The 15-minute operator attestation is invalid."
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
    $collectorSource -notmatch "canary-observation-end.json"
) {
    throw "The canary progress contract is missing."
}
$analyzerSource = Get-Content `
    -LiteralPath (Join-Path $resolvedKitRoot "analyze-spot-http-framing.ps1") `
    -Raw
if (
    $analyzerSource -notmatch "spot-http-framing-evidence-v6" -or
    $analyzerSource -notmatch "duplicate_initial_syn_count" -or
    $analyzerSource -notmatch "monotonic_corrected" -or
    $analyzerSource -notmatch "excluded_before_count" -or
    $analyzerSource -notmatch "excluded_after_count"
) {
    throw "The packet measurement v6 contract is missing."
}

if (-not $Quiet) {
    $results | Format-Table -AutoSize
    Write-Host (
        "[PASS] v1.0.21 120-minute canary kit identity and SHA-256 values are valid."
    ) -ForegroundColor Green
}
