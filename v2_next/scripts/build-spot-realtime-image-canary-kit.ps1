[CmdletBinding()]
param(
    [string]$OutputRoot = "",

    [string]$ExpectedCommit = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$diagnosticCoreCommit = "077b6b1c45b7bf6023d89ba13ecaa54d22acbe70"

function Invoke-GitText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepositoryRoot,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = @(& git -C $RepositoryRoot @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "git command failed: git $($Arguments -join ' ')"
    }
    return ($output | Out-String).Trim()
}

function Assert-SafeTemporaryPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$TemporaryBase
    )

    $fullPath = [IO.Path]::GetFullPath($Path)
    $fullBase = [IO.Path]::GetFullPath($TemporaryBase).TrimEnd("\") + "\"
    if (-not $fullPath.StartsWith(
        $fullBase,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to clean an unexpected temporary path."
    }
}

function Add-CanaryProgressContract {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CollectorPath
    )

    $source = [IO.File]::ReadAllText($CollectorPath)
    $parameterNeedle = @'
    [int]$PostTriggerCaptureSeconds = 75,

    [switch]$PreflightOnly,
'@
    $parameterReplacement = @'
    [int]$PostTriggerCaptureSeconds = 75,

    [ValidateRange(10, 300)]
    [int]$ProgressIntervalSeconds = 30,

    [switch]$PreflightOnly,
'@
    if (-not $source.Contains($parameterNeedle)) {
        throw "Historical collector parameter insertion point was not found."
    }
    $source = $source.Replace($parameterNeedle, $parameterReplacement)

    $loopNeedle = @'
        while ($true) {
            Receive-CollectorJobOutput -Job $collectorJob -ConsolePath $collectorConsolePath
'@
    $loopReplacement = @'
        $progressStartedAt = Get-Date
        $lastProgressAt = $progressStartedAt.AddSeconds(-$ProgressIntervalSeconds)
        while ($true) {
            $progressNow = Get-Date
            if (($progressNow - $lastProgressAt).TotalSeconds -ge $ProgressIntervalSeconds) {
                $progressElapsedSeconds = [Math]::Max(
                    0,
                    ($progressNow - $progressStartedAt).TotalSeconds
                )
                $progressRemainingSeconds = [Math]::Max(
                    0,
                    $observationPlan.DurationSeconds - $progressElapsedSeconds
                )
                $progressPercent = [Math]::Min(
                    100,
                    [Math]::Round(
                        100 * $progressElapsedSeconds / $observationPlan.DurationSeconds,
                        1
                    )
                )
                $progressBackend = @(
                    Get-Process -Name "SmartFactoryBackend" -ErrorAction SilentlyContinue
                )
                $progressBackendAlive = $progressBackend.Count -eq 1
                $progressBackendPid = if ($progressBackendAlive) {
                    $progressBackend[0].Id
                } else {
                    "unavailable"
                }
                Write-Host (
                    "[CANARY PROGRESS] stage=observing elapsed={0} remaining={1} " +
                    "percent={2} backend_pid={3} backend_alive={4} checked_at={5}; " +
                    "local clock/process only; no added SPOT requests" -f
                        ([TimeSpan]::FromSeconds($progressElapsedSeconds).ToString("hh\:mm\:ss")),
                        ([TimeSpan]::FromSeconds($progressRemainingSeconds).ToString("hh\:mm\:ss")),
                        $progressPercent,
                        $progressBackendPid,
                        $progressBackendAlive,
                        $progressNow.ToString("yyyy-MM-dd HH:mm:ss K")
                ) -ForegroundColor Cyan
                $lastProgressAt = $progressNow
            }
            Receive-CollectorJobOutput -Job $collectorJob -ConsolePath $collectorConsolePath
'@
    if (-not $source.Contains($loopNeedle)) {
        throw "Historical collector progress insertion point was not found."
    }
    $source = $source.Replace($loopNeedle, $loopReplacement)
    if (
        ([regex]::Matches($source, "ProgressIntervalSeconds = 30")).Count -ne 1 -or
        ([regex]::Matches($source, "\[CANARY PROGRESS\]")).Count -ne 1
    ) {
        throw "The canary progress patch was not applied exactly once."
    }

    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($CollectorPath, $source, $utf8)
}

function Invoke-CanarySelfTests {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StagingRoot,

        [Parameter(Mandatory = $true)]
        [string]$IntegrationTestPath
    )

    & powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $StagingRoot "analyze-spot-http-framing.ps1") `
        -SelfTest
    if ($LASTEXITCODE -ne 0) {
        throw "SPOT framing analyzer self-test failed."
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $StagingRoot "monitor-spot-connecttimeout-trigger.ps1") `
        -SelfTest
    if ($LASTEXITCODE -ne 0) {
        throw "SPOT trigger monitor self-test failed."
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $StagingRoot "collect_operational_observability.ps1") `
        -SelfTest
    if ($LASTEXITCODE -ne 0) {
        throw "Operational collector self-test failed."
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $StagingRoot "collect-spot-connecttimeout-evidence.ps1") `
        -SelfTest `
        -ObservationMinutes 120 `
        -StopOnNewSpotConnectTimeout `
        -PostTriggerCaptureSeconds 75 `
        -ProgressIntervalSeconds 30 `
        -FramingAnalyzerPath (Join-Path $StagingRoot "analyze-spot-http-framing.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "SPOT field collector self-test failed."
    }
    & python.exe $IntegrationTestPath
    if ($LASTEXITCODE -ne 0) {
        throw "SPOT trigger integration test failed."
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $StagingRoot "invoke-spot-realtime-image-canary-120m.ps1") `
        -SelfTest
    if ($LASTEXITCODE -ne 0) {
        throw "v1.0.21 canary controller self-test failed."
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$gitRoot = Invoke-GitText `
    -RepositoryRoot $projectRoot `
    -Arguments @("rev-parse", "--show-toplevel")
$toolingCommit = Invoke-GitText `
    -RepositoryRoot $gitRoot `
    -Arguments @("rev-parse", "HEAD")
if ($toolingCommit -notmatch "^[0-9a-f]{40}$") {
    throw "The canary tooling source commit is invalid."
}
if (
    -not [string]::IsNullOrWhiteSpace($ExpectedCommit) -and
    $toolingCommit -cne $ExpectedCommit.ToLowerInvariant()
) {
    throw "HEAD $toolingCommit does not match expected commit $ExpectedCommit."
}
$dirtyTracked = Invoke-GitText `
    -RepositoryRoot $gitRoot `
    -Arguments @("status", "--porcelain", "--untracked-files=no")
if (-not [string]::IsNullOrWhiteSpace($dirtyTracked)) {
    throw "Tracked files are modified. Commit and re-run the canary kit build."
}
Invoke-GitText `
    -RepositoryRoot $gitRoot `
    -Arguments @("cat-file", "-e", "$diagnosticCoreCommit^{commit}") |
    Out-Null

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $projectRoot "artifacts"
}
$outputRootFull = [IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $outputRootFull -Force | Out-Null

$currentSources = [ordered]@{
    "backend_bundle_integrity.psm1" = Join-Path $PSScriptRoot "backend_bundle_integrity.psm1"
    "invoke-spot-realtime-image-canary-120m.ps1" = Join-Path $PSScriptRoot "invoke-spot-realtime-image-canary-120m.ps1"
    "run-spot-realtime-image-canary-120m-as-admin.cmd" = Join-Path $PSScriptRoot "run-spot-realtime-image-canary-120m-as-admin.cmd"
    "verify-spot-realtime-image-canary-kit.ps1" = Join-Path $PSScriptRoot "verify-spot-realtime-image-canary-kit.ps1"
    "SPOT_REALTIME_IMAGE_CANARY_120M_GUIDE.md" = Join-Path $projectRoot "docs\04-deploy\spot-realtime-image-v1021-canary-120m.md"
}
foreach ($path in $currentSources.Values) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "A current canary source file is missing: $path"
    }
    $gitRootPrefix = [IO.Path]::GetFullPath($gitRoot).TrimEnd("\") + "\"
    $fullSourcePath = [IO.Path]::GetFullPath($path)
    if (-not $fullSourcePath.StartsWith(
        $gitRootPrefix,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "A current canary source is outside the repository: $path"
    }
    $relativePath = $fullSourcePath.Substring($gitRootPrefix.Length).Replace("\", "/")
    Invoke-GitText `
        -RepositoryRoot $gitRoot `
        -Arguments @("ls-files", "--error-unmatch", "--", $relativePath) |
        Out-Null
}

$corePaths = @(
    "v2_next/scripts/analyze-spot-http-framing.ps1",
    "v2_next/scripts/collect_operational_observability.ps1",
    "v2_next/scripts/collect-spot-connecttimeout-evidence.ps1",
    "v2_next/scripts/monitor-spot-connecttimeout-trigger.ps1",
    "v2_next/scripts/test_spot_connecttimeout_trigger_collector.py"
)
$generatedAt = [DateTimeOffset]::UtcNow
$kitName = "SmartFactoryLogger_SPOT_Realtime_Image_v1021_Canary_{0}_{1}" -f `
    $toolingCommit.Substring(0, 8),
    $generatedAt.ToString("yyyyMMdd_HHmmssZ")
$kitFolder = Join-Path $outputRootFull $kitName
$zipPath = "$kitFolder.zip"
$zipHashPath = "$zipPath.sha256.txt"
foreach ($target in @($kitFolder, $zipPath, $zipHashPath)) {
    if (Test-Path -LiteralPath $target) {
        throw "A canary kit output already exists: $target"
    }
}

$temporaryBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$temporaryRoot = Join-Path `
    $temporaryBase `
    ("sfl-v1021-canary-{0}" -f [guid]::NewGuid().ToString("N"))
$stagingRoot = Join-Path $temporaryRoot "staging"
$archiveRoot = Join-Path $temporaryRoot "archive"
$verificationRoot = Join-Path $temporaryRoot "verify"
try {
    New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null
    $coreArchive = Join-Path $temporaryRoot "diagnostic-core.zip"
    & git -C $gitRoot archive `
        --format=zip `
        "--output=$coreArchive" `
        $diagnosticCoreCommit `
        @corePaths
    if ($LASTEXITCODE -ne 0) {
        throw "Could not export the fixed diagnostic core commit."
    }
    Expand-Archive -LiteralPath $coreArchive -DestinationPath $archiveRoot

    foreach ($relativePath in $corePaths | Where-Object { $_ -like "*.ps1" }) {
        Copy-Item `
            -LiteralPath (Join-Path $archiveRoot $relativePath.Replace("/", "\")) `
            -Destination (Join-Path $stagingRoot (Split-Path -Leaf $relativePath))
    }
    $integrationTestPath = Join-Path `
        $archiveRoot `
        "v2_next\scripts\test_spot_connecttimeout_trigger_collector.py"
    Add-CanaryProgressContract `
        -CollectorPath (Join-Path $stagingRoot "collect-spot-connecttimeout-evidence.ps1")

    foreach ($entry in $currentSources.GetEnumerator()) {
        Copy-Item -LiteralPath $entry.Value -Destination (Join-Path $stagingRoot $entry.Key)
    }

    $attestation = [ordered]@{
        schema_version = "spot-operator-visual-attestation-v1"
        evidence_kind = "human-attestation"
        product_version = "1.0.21"
        build_git_commit = "5971fc4fbdeec07ef65681a945319f0ae12d55cb"
        observation_date_kst = "2026-08-21"
        observation_start_kst = "19:13"
        observation_end_kst = "19:28"
        observation_duration_minutes = 15
        continuous_spot_image_refresh = $true
        screen_error_observed = $false
        statement = "SPOT video refreshed continuously for the complete interval and no screen error was observed."
        source = "user-provided confirmation in the active Codex task"
        machine_generated = $false
    }
    $attestation | ConvertTo-Json -Depth 5 |
        Set-Content `
            -LiteralPath (Join-Path $stagingRoot "operator_attestation_15m.json") `
            -Encoding UTF8

    $evidenceFiles = @(
        [ordered]@{ file = "backend-integrity-after-install.json"; sha256 = "6D077E7944C5670A6990862209C6D7A10935E13B01D920AF3D270538A5147058" },
        [ordered]@{ file = "health-after-15m.json"; sha256 = "9CD044E41D5A42AA72F94275B18AC1CBDB786AA44C5BCD0E836CF6772B883322" },
        [ordered]@{ file = "health-before-15m.json"; sha256 = "12653336422E897764C47069F7CAE5F2C876B8B27591CDF7D52AB6ED6F982021" },
        [ordered]@{ file = "postinstall-bundle-gate.json"; sha256 = "E42CF3126CD5CC42F38918D0E64CF9C302A860FB00DD8B8030B676EF20147994" },
        [ordered]@{ file = "preinstall-summary.json"; sha256 = "06F076A09D7D659B88A92959769CD1528802EC08E3C0A13F35A6A8329FF32138" },
        [ordered]@{ file = "spot-15m.json"; sha256 = "464BF0A540133C5165B7E550430EDA9EDAA07FA866481B43FAD2B0392016A4F8" },
        [ordered]@{ file = "spot-config-image-after-15m.json"; sha256 = "1859E0E79C7D24348132B93B8D2EBFA50FBD0166762F7A4F1A16B41C15A6D100" },
        [ordered]@{ file = "spot-config-image-before-15m.json"; sha256 = "7E7486908045EF4898F44CA474816C647EAC1C5619EAADA6B3DA6445E5C87342" }
    )
    $identity = [ordered]@{
        schema_version = "spot-realtime-image-v1021-canary-kit-v1"
        kit_name = $kitName
        generated_at_utc = $generatedAt.ToString("o")
        tooling_source_commit = $toolingCommit
        classification = "PRIVATE_UNSIGNED_INTERNAL_CANARY_ONLY"
        production_promotion_allowed = $false
        product = [ordered]@{
            version = "1.0.21"
            build_git_commit = "5971fc4fbdeec07ef65681a945319f0ae12d55cb"
            release_kit_folder = "spot-realtime-image-performance-v1.0.21-5971fc4"
            installer_file = "smart-factory-logger-v2 Setup 1.0.21.exe"
            installer_sha256 = "01CF544C999FB21FADB7F36965DC35FB9E8AEE36D1EEBD3319A1EB7296AD191A"
            app_asar_sha256 = "50734BC222DF943A2DC6605E35EDEA0AD600C909A0A32E4ADEFF2A2A0952C048"
            backend_bundle_sha256 = "B818383DF7B035DC73C86E57F0080489B287C958086C8E2C426639C0622CB094"
            backend_bundle_file_count = 1385
            config_sha256 = "6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E"
        }
        rollback = [ordered]@{
            version = "1.0.16"
            installer_file = "smart-factory-logger-v2.Setup.1.0.16.exe"
            installer_sha256 = "42A076B37ADA66CEAEE816128A1FC67C40CCD1C5417F9BDED5E885478974F615"
        }
        prerequisite_15m = [ordered]@{
            result = "PASS"
            evidence_relative_path = "server-evidence\20260821-190022"
            observation_date_kst = "2026-08-21"
            observation_start_kst = "19:13"
            observation_end_kst = "19:28"
            operator_attestation_file = "operator_attestation_15m.json"
            evidence_files = $evidenceFiles
        }
        diagnostic_core = [ordered]@{
            source_commit = $diagnosticCoreCommit
            source_identity = "spot-connecttimeout-trigger-field-kit-v4"
            framing_schema = "spot-http-framing-evidence-v5"
            controlled_delta = "30-second local clock/process progress output only"
            product_request_behavior_changed = $false
        }
        canary = [ordered]@{
            maximum_observation_minutes = 120
            stop_on_new_spot_connecttimeout = $true
            post_trigger_capture_seconds = 75
            progress_interval_seconds = 30
            progress_source = "local-clock-and-process-state-only"
            progress_adds_spot_or_backend_requests = $false
            packet_capture_circular_limit_mb = 1024
            packet_payload_retained_in_share = $false
            same_four_tuple_minimum_75s_required = $true
            packet_capture_full_window_required = $true
            backend_pid_must_remain_constant = $true
            request_budget_max_per_second = 6.0
        }
        contains_installer = $false
        contains_product_binary = $false
        changes_application_or_settings = $false
        restarts_application = $false
        clears_error_queue = $false
        actual_server_execution_performed = $false
    }
    $identity | ConvertTo-Json -Depth 8 |
        Set-Content `
            -LiteralPath (Join-Path $stagingRoot "canary_kit_identity.json") `
            -Encoding UTF8

    Invoke-CanarySelfTests `
        -StagingRoot $stagingRoot `
        -IntegrationTestPath $integrationTestPath

    $manifestPath = Join-Path $stagingRoot "canary_kit_files_sha256.txt"
    $manifestLines = foreach (
        $file in Get-ChildItem -LiteralPath $stagingRoot -File |
            Where-Object { $_.Name -ne "canary_kit_files_sha256.txt" } |
            Sort-Object Name
    ) {
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        "$hash  $($file.Name)"
    }
    $manifestLines | Set-Content -LiteralPath $manifestPath -Encoding ascii

    & powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $stagingRoot "verify-spot-realtime-image-canary-kit.ps1") `
        -KitRoot $stagingRoot `
        -Quiet
    if ($LASTEXITCODE -ne 0) {
        throw "The staged v1.0.21 canary kit failed verification."
    }

    Copy-Item -LiteralPath $stagingRoot -Destination $kitFolder -Recurse
    Compress-Archive -Path (Join-Path $kitFolder "*") -DestinationPath $zipPath
    $zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
    $zipHash | Set-Content -LiteralPath $zipHashPath -Encoding ascii

    New-Item -ItemType Directory -Path $verificationRoot -Force | Out-Null
    Expand-Archive -LiteralPath $zipPath -DestinationPath $verificationRoot
    & powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $verificationRoot "verify-spot-realtime-image-canary-kit.ps1") `
        -KitRoot $verificationRoot `
        -Quiet
    if ($LASTEXITCODE -ne 0) {
        throw "The extracted v1.0.21 canary ZIP failed verification."
    }
    $recordedZipHash = (Get-Content -LiteralPath $zipHashPath -Raw).Trim()
    $recomputedZipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
    if (
        $recordedZipHash -cne $zipHash -or
        $recomputedZipHash -cne $zipHash
    ) {
        throw "The v1.0.21 canary ZIP SHA-256 verification failed."
    }

    Write-Output "kit_folder=$kitFolder"
    Write-Output "kit_zip=$zipPath"
    Write-Output "kit_sha256_file=$zipHashPath"
    Write-Output "kit_sha256=$zipHash"
    Write-Output "tooling_source_commit=$toolingCommit"
    Write-Output "diagnostic_core_source_commit=$diagnosticCoreCommit"
    Write-Output "package_file_count=12"
    Write-Output "progress_interval_seconds=30"
    Write-Output "progress_adds_spot_or_backend_requests=false"
    Write-Output "SPOT_REALTIME_IMAGE_V1021_CANARY_KIT_BUILD_PASS"
} finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Assert-SafeTemporaryPath `
            -Path $temporaryRoot `
            -TemporaryBase $temporaryBase
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}
