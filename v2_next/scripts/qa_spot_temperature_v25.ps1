param(
    [string]$BackendBaseUrl = "http://127.0.0.1:8000",
    [string]$ConfigPath = "",
    [string]$LogPath = "",
    [int]$ObservationSeconds = 60,
    [int]$SampleIntervalSeconds = 5,
    [string]$OutputPath = "",
    [switch]$SkipStopPrompt,
    [int]$GracefulShutdownTimeoutSeconds = 330
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backend = $BackendBaseUrl.TrimEnd("/")
$checks = New-Object "System.Collections.Generic.List[object]"
$warnings = New-Object "System.Collections.Generic.List[string]"
$samples = New-Object "System.Collections.Generic.List[object]"
$attestationCanBeApplied = $false
$operatorShutdownRequested = $false

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    if (-not [string]::IsNullOrWhiteSpace($env:SFL_CONFIG_PATH)) {
        $ConfigPath = $env:SFL_CONFIG_PATH
    } else {
        $ConfigPath = Join-Path $env:APPDATA "SmartFactoryLogger\config.ini"
    }
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputPath = Join-Path $env:TEMP "sfl-spot-temperature-v25-qa-$stamp.json"
}
$ObservationSeconds = [math]::Max(5, $ObservationSeconds)
$SampleIntervalSeconds = [math]::Max(1, $SampleIntervalSeconds)
$GracefulShutdownTimeoutSeconds = [math]::Max(30, $GracefulShutdownTimeoutSeconds)

function Test-BackendReachable {
    try {
        $null = Invoke-RestMethod -Uri "$backend/health" -Method Get -TimeoutSec 2
        return $true
    } catch {
        return $false
    }
}

# BEGIN QA SHUTDOWN HELPERS
function Invoke-OperatorShutdownCheckpoint {
    param(
        [int]$TimeoutSeconds,
        [int]$PollIntervalSeconds = 2,
        [int]$ConsecutiveFailuresRequired = 3,
        [scriptblock]$ReachabilityProbe = { Test-BackendReachable },
        [scriptblock]$ProductProcessProbe = {
            $backendProcesses = @(
                Get-Process -Name "SmartFactoryBackend" -ErrorAction SilentlyContinue
            )
            $electronProcesses = @(
                Get-Process -Name "smart-factory" -ErrorAction SilentlyContinue
            )
            return ($backendProcesses.Count + $electronProcesses.Count) -gt 0
        },
        [scriptblock]$PromptAction = {
            Write-Host "[ACTION] Close SmartFactoryLogger with the window X button." -ForegroundColor Yellow
            Write-Host "Do not use Task Manager and do not stop SmartFactoryBackend.exe directly."
            [void](Read-Host "After closing the SmartFactoryLogger window, press Enter to continue")
        },
        [scriptblock]$SleepAction = {
            param([int]$Seconds)
            Start-Sleep -Seconds $Seconds
        }
    )

    $requiredFailures = [math]::Max(1, $ConsecutiveFailuresRequired)
    $reachable = [bool](& $ReachabilityProbe)
    $productProcessPresent = [bool](& $ProductProcessProbe)
    $operatorRequested = $false
    if ($reachable -or $productProcessPresent) {
        & $PromptAction
        $operatorRequested = $true
    }

    $consecutiveFailures = if (-not $reachable -and -not $productProcessPresent) {
        1
    } else {
        0
    }
    if ($consecutiveFailures -ge $requiredFailures) {
        return [PSCustomObject]@{
            backend_stopped = $true
            operator_shutdown_requested = $operatorRequested
            consecutive_unreachable_count = $consecutiveFailures
        }
    }

    $deadline = (Get-Date).AddSeconds([math]::Max(0, $TimeoutSeconds))
    while ((Get-Date) -lt $deadline) {
        & $SleepAction ([math]::Max(0, $PollIntervalSeconds))
        $reachable = [bool](& $ReachabilityProbe)
        $productProcessPresent = [bool](& $ProductProcessProbe)
        if (-not $reachable -and -not $productProcessPresent) {
            $consecutiveFailures += 1
        } else {
            $consecutiveFailures = 0
        }
        if ($consecutiveFailures -ge $requiredFailures) {
            return [PSCustomObject]@{
                backend_stopped = $true
                operator_shutdown_requested = $operatorRequested
                consecutive_unreachable_count = $consecutiveFailures
            }
        }
    }

    return [PSCustomObject]@{
        backend_stopped = $false
        operator_shutdown_requested = $operatorRequested
        consecutive_unreachable_count = $consecutiveFailures
    }
}
# END QA SHUTDOWN HELPERS

# BEGIN QA METADATA HELPERS
function Get-ObjectProperty {
    param(
        [object]$Object,
        [string]$Name,
        [object]$Default = $null
    )
    if ($null -eq $Object) {
        return $Default
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value) {
        return $Default
    }
    return $property.Value
}

function Convert-ToBoolean {
    param([object]$Value)
    if ($Value -is [bool]) {
        return [bool]$Value
    }
    return [string]$Value -match "^(?i:true|1|yes|on)$"
}

function Convert-ToInt64 {
    param([object]$Value)
    $parsed = 0L
    if ($null -ne $Value -and [long]::TryParse([string]$Value, [ref]$parsed)) {
        return $parsed
    }
    return 0L
}

function Add-QaCheck {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Actual,
        [string]$Expected
    )
    $checks.Add([ordered]@{
        name = $Name
        passed = $Passed
        actual = $Actual
        expected = $Expected
    })
    $label = if ($Passed) { "PASS" } else { "FAIL" }
    $color = if ($Passed) { "Green" } else { "Red" }
    Write-Host "[$label] $Name - actual=$Actual; expected=$Expected" -ForegroundColor $color
}

function Add-QaWarning {
    param([string]$Message)
    $warnings.Add($Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Get-IniValue {
    param(
        [string]$Path,
        [string]$Section,
        [string]$Key
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    $inSection = $false
    foreach ($line in Get-Content -LiteralPath $Path -ErrorAction Stop) {
        $trimmed = $line.Trim()
        if ($trimmed -match "^\[(.+)\]$") {
            $inSection = $Matches[1] -ieq $Section
            continue
        }
        if ($inSection -and $trimmed -match "^([^=]+?)\s*=\s*(.*)$") {
            if ($Matches[1].Trim() -ieq $Key) {
                return $Matches[2].Trim()
            }
        }
    }
    return $null
}

function Get-LogDirectoryCandidates {
    param(
        [string]$ExplicitLogPath,
        [string]$SettingsPath
    )
    $candidates = New-Object "System.Collections.Generic.List[string]"
    if (-not [string]::IsNullOrWhiteSpace($ExplicitLogPath)) {
        $candidates.Add($ExplicitLogPath)
    }
    $configured = Get-IniValue -Path $SettingsPath -Section "SETTINGS" -Key "logpath"
    if (-not [string]::IsNullOrWhiteSpace($configured)) {
        if ([System.IO.Path]::IsPathRooted($configured)) {
            $candidates.Add($configured)
        } else {
            $candidates.Add((Join-Path (Join-Path $env:APPDATA "SmartFactoryLogger") $configured))
            $configDirectory = Split-Path -Parent $SettingsPath
            if (-not [string]::IsNullOrWhiteSpace($configDirectory)) {
                $candidates.Add((Join-Path $configDirectory $configured))
            }
            $candidates.Add((Join-Path $repoRoot $configured))
        }
    }
    $candidates.Add((Join-Path $env:APPDATA "SmartFactoryLogger\logs\data"))
    $candidates.Add((Join-Path $env:APPDATA "SmartFactoryLogger\logs"))

    return @(
        $candidates |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            ForEach-Object { [System.IO.Path]::GetFullPath($_) } |
            Select-Object -Unique
    )
}

function Find-LatestMetadata {
    param(
        [string[]]$Directories,
        [string]$ExpectedLoggerServiceInstanceId,
        [string]$ExpectedBuildCommit,
        [long]$ExpectedMinimumSampleSeq,
        [string]$ExpectedCsvFileName
    )
    if (
        [string]::IsNullOrWhiteSpace($ExpectedCsvFileName) -or
        [System.IO.Path]::GetFileName($ExpectedCsvFileName) -ne
            $ExpectedCsvFileName -or
        $ExpectedCsvFileName -notmatch "\.csv$"
    ) {
        return $null
    }
    foreach ($directory in $Directories) {
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
            continue
        }
        $candidates = @(
            Get-ChildItem `
                -LiteralPath $directory `
                -File `
                -Filter "Factory_Integrated_Log_v2_*.metadata.json" `
                -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTimeUtc -Descending
        )
        foreach ($candidate in $candidates) {
            try {
            $metadata = Get-Content -LiteralPath $candidate.FullName -Raw -Encoding UTF8 |
                ConvertFrom-Json
            $schemaMetadata = Get-ObjectProperty $metadata "schema_metadata"
            $configSnapshot = Get-ObjectProperty $metadata "spot_configuration_snapshot"
            $csvCloseout = Get-ObjectProperty $metadata "csv_closeout"
            $loggerServiceInstanceId = [string](
                Get-ObjectProperty $schemaMetadata "logger_service_instance_id" ""
            )
            $schemaBuildCommit = [string](
                Get-ObjectProperty $schemaMetadata "git_commit" ""
            )
            $configBuildCommit = [string](
                Get-ObjectProperty $configSnapshot "build_git_commit" ""
            )
            $closeoutSampleSeq = 0L
            $closeoutSampleSeqValid = [long]::TryParse(
                [string](
                    Get-ObjectProperty `
                        $csvCloseout `
                        "final_persisted_sample_seq" `
                        ""
                ),
                [ref]$closeoutSampleSeq
            )
            $closeoutCsvFileName = [string](
                Get-ObjectProperty $csvCloseout "csv_file_name" ""
            )
            $csvPath = Join-Path $directory $closeoutCsvFileName
            if (
                $loggerServiceInstanceId -eq $ExpectedLoggerServiceInstanceId -and
                $schemaBuildCommit -eq $ExpectedBuildCommit -and
                $configBuildCommit -eq $ExpectedBuildCommit -and
                (Convert-ToBoolean (
                    Get-ObjectProperty $csvCloseout "finalized" $false
                )) -and
                ([string](
                    Get-ObjectProperty $csvCloseout "closeout_reason" ""
                )) -eq "shutdown" -and
                [System.IO.Path]::GetFileName($closeoutCsvFileName) -eq
                    $closeoutCsvFileName -and
                $closeoutCsvFileName -ceq $ExpectedCsvFileName -and
                $closeoutCsvFileName -match "\.csv$" -and
                ([string](
                    Get-ObjectProperty $csvCloseout "logger_service_instance_id" ""
                )) -eq $ExpectedLoggerServiceInstanceId -and
                $closeoutSampleSeqValid -and
                $closeoutSampleSeq -ge $ExpectedMinimumSampleSeq -and
                (Test-Path -LiteralPath $csvPath -PathType Leaf)
            ) {
                return [PSCustomObject]@{
                    file = $candidate
                    metadata = $metadata
                    csv_file = $csvPath
                    csv_final_sample_seq = $closeoutSampleSeq
                    observed_csv_file_name = $closeoutCsvFileName
                }
            }
            } catch {
                continue
            }
        }
    }
    return $null
}
# END QA METADATA HELPERS

function Save-QaArtifact {
    param(
        [string]$Verdict,
        [object]$RuntimeSummary,
        [object]$FileSummary,
        [string]$ValidatorOutput
    )
    $artifact = [ordered]@{
        schema_version = "spot-temperature-v25-qa-v1"
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        verdict = $Verdict
        backend_base_url = $backend
        observation_seconds = $ObservationSeconds
        sample_interval_seconds = $SampleIntervalSeconds
        checks = $checks
        warnings = $warnings
        runtime_summary = $RuntimeSummary
        samples = $samples
        files = $FileSummary
        validator_output = $ValidatorOutput
    }
    $outputDirectory = Split-Path -Parent $OutputPath
    if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
        New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    }
    $artifact | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding utf8
}

Write-Host ""
Write-Host "SPOT Temperature v2.5 one-command QA" -ForegroundColor Cyan
Write-Host "This tool does not change SPOT device or application settings."
Write-Host "It requires a normal UI close to finalize CSV metadata before validation."
Write-Host ""
Write-Host "[1/5] Checking the running backend..." -ForegroundColor Cyan

$initialHealth = $null
try {
    $initialHealth = Invoke-RestMethod -Uri "$backend/health" -Method Get -TimeoutSec 10
    Add-QaCheck -Name "Backend health API" -Passed $true -Actual "reachable" -Expected "reachable"
} catch {
    Add-QaCheck -Name "Backend health API" -Passed $false -Actual $_.Exception.Message -Expected "reachable at $backend/health"
    Save-QaArtifact -Verdict "FAIL" -RuntimeSummary $null -FileSummary $null -ValidatorOutput ""
    Write-Host ""
    Write-Host "FINAL RESULT: FAIL" -ForegroundColor Red
    Write-Host "Start SmartFactoryLogger first, then run this command again."
    Write-Host "Evidence: $OutputPath"
    exit 1
}

$initialSpot = Get-ObjectProperty -Object $initialHealth -Name "spot_temperature"
$initialOperational = Get-ObjectProperty -Object $initialSpot -Name "v2_4_operational"
$expectedLoggerServiceInstanceId = [string](
    Get-ObjectProperty $initialOperational "logger_service_instance_id" ""
)
Add-QaCheck -Name "Runtime mode" -Passed (([string](Get-ObjectProperty $initialHealth "mode")) -eq "REAL") `
    -Actual ([string](Get-ObjectProperty $initialHealth "mode" "missing")) -Expected "REAL"
Add-QaCheck -Name "SPOT diagnostics" -Passed (Convert-ToBoolean (Get-ObjectProperty $initialSpot "diagnostics_available" $false)) `
    -Actual ([string](Get-ObjectProperty $initialSpot "diagnostics_available" "missing")) -Expected "true"
Add-QaCheck -Name "CSV operational logging" -Passed (Convert-ToBoolean (Get-ObjectProperty $initialOperational "enabled" $false)) `
    -Actual ([string](Get-ObjectProperty $initialOperational "enabled" "missing")) -Expected "true"
Add-QaCheck -Name "CSV schema" -Passed (([string](Get-ObjectProperty $initialOperational "schema_version")) -eq "2.5.0") `
    -Actual ([string](Get-ObjectProperty $initialOperational "schema_version" "missing")) -Expected "2.5.0"
Add-QaCheck -Name "Temperature hardening" -Passed (Convert-ToBoolean (Get-ObjectProperty $initialOperational "temperature_hardening_enabled" $false)) `
    -Actual ([string](Get-ObjectProperty $initialOperational "temperature_hardening_enabled" "missing")) -Expected "true"
Add-QaCheck -Name "Observation fact writer" -Passed (Convert-ToBoolean (Get-ObjectProperty $initialOperational "observation_fact_enabled" $false)) `
    -Actual ([string](Get-ObjectProperty $initialOperational "observation_fact_enabled" "missing")) -Expected "true"
Add-QaCheck -Name "Logger service instance" `
    -Passed ($expectedLoggerServiceInstanceId -match "^[0-9a-fA-F-]{32,36}$") `
    -Actual $(if ($expectedLoggerServiceInstanceId) { $expectedLoggerServiceInstanceId } else { "missing" }) `
    -Expected "current logger service instance id"

Write-Host ""
Write-Host "[2/5] Observing SPOT for $ObservationSeconds seconds..." -ForegroundColor Cyan
$sampleCount = [math]::Max(1, [math]::Ceiling($ObservationSeconds / $SampleIntervalSeconds))
for ($index = 0; $index -lt $sampleCount; $index += 1) {
    try {
        $health = Invoke-RestMethod -Uri "$backend/health" -Method Get -TimeoutSec 10
        $spot = Get-ObjectProperty $health "spot_temperature"
        $operational = Get-ObjectProperty $spot "v2_4_operational"
        $samples.Add([ordered]@{
            captured_at = (Get-Date).ToUniversalTime().ToString("o")
            poll_status = [string](Get-ObjectProperty $spot "spot_poll_status" "missing")
            raw_validity = [string](Get-ObjectProperty $spot "spot_raw_validity" "missing")
            source_freshness = [string](Get-ObjectProperty $spot "spot_source_freshness" "missing")
            temperature_value_origin = [string](Get-ObjectProperty $spot "temperature_value_origin" "missing")
            rows_total = Convert-ToInt64 (Get-ObjectProperty $operational "rows_total" 0)
            write_failure_count = Convert-ToInt64 (Get-ObjectProperty $operational "observation_fact_write_failure_count" 0)
        })
    } catch {
        Add-QaWarning "Health sample failed: $($_.Exception.Message)"
    }
    if ($index -lt ($sampleCount - 1)) {
        Start-Sleep -Seconds $SampleIntervalSeconds
    }
}

$initialRows = Convert-ToInt64 (Get-ObjectProperty $initialOperational "rows_total" 0)
try {
    $finalHealth = Invoke-RestMethod -Uri "$backend/health" -Method Get -TimeoutSec 10
    Add-QaCheck -Name "Final backend health sample" -Passed $true -Actual "reachable" -Expected "reachable"
} catch {
    Add-QaCheck -Name "Final backend health sample" -Passed $false -Actual $_.Exception.Message -Expected "reachable"
    $finalHealth = $initialHealth
}
$finalSpot = Get-ObjectProperty $finalHealth "spot_temperature"
$finalOperational = Get-ObjectProperty $finalSpot "v2_4_operational"
$finalLoggerServiceInstanceId = [string](
    Get-ObjectProperty $finalOperational "logger_service_instance_id" ""
)
$expectedBuildCommit = [string](Get-ObjectProperty $finalSpot "build_git_commit" "")
$expectedMinimumSampleSeq = Convert-ToInt64 (
    Get-ObjectProperty $finalOperational "last_sample_seq" 0
)
$expectedCsvFileName = [string](
    Get-ObjectProperty $finalOperational "current_v2_csv_file_name" ""
)
$finalRows = Convert-ToInt64 (Get-ObjectProperty $finalOperational "rows_total" 0)
$successfulPollObserved = @($samples | Where-Object { $_.poll_status -eq "success" }).Count -gt 0
$currentOriginObserved = @($samples | Where-Object { $_.temperature_value_origin -eq "current_observation" }).Count -gt 0
$observedPollStatuses = (($samples.poll_status | Sort-Object -Unique) -join ",")
$observedValueOrigins = (($samples.temperature_value_origin | Sort-Object -Unique) -join ",")
Add-QaCheck -Name "CSV rows increased" -Passed ($finalRows -gt $initialRows) -Actual "$initialRows -> $finalRows" -Expected "increase"
Add-QaCheck -Name "Successful SPOT poll observed" -Passed $successfulPollObserved `
    -Actual $observedPollStatuses -Expected "success"
Add-QaCheck -Name "Current observation observed" -Passed $currentOriginObserved `
    -Actual $observedValueOrigins -Expected "current_observation"
Add-QaCheck -Name "Observation fact write failures" `
    -Passed ((Convert-ToInt64 (Get-ObjectProperty $finalOperational "observation_fact_write_failure_count" 0)) -eq 0) `
    -Actual ([string](Get-ObjectProperty $finalOperational "observation_fact_write_failure_count" "missing")) -Expected "0"
Add-QaCheck -Name "Observation fact link failures" `
    -Passed ((Convert-ToInt64 (Get-ObjectProperty $finalOperational "observation_fact_link_failure_count" 0)) -eq 0) `
    -Actual ([string](Get-ObjectProperty $finalOperational "observation_fact_link_failure_count" "missing")) -Expected "0"
Add-QaCheck -Name "Origin decision mismatches" `
    -Passed ((Convert-ToInt64 (Get-ObjectProperty $finalOperational "origin_decision_mismatch_count" 0)) -eq 0) `
    -Actual ([string](Get-ObjectProperty $finalOperational "origin_decision_mismatch_count" "missing")) -Expected "0"
Add-QaCheck -Name "Value age clock anomalies" `
    -Passed ((Convert-ToInt64 (Get-ObjectProperty $finalOperational "value_age_clock_anomaly_count" 0)) -eq 0) `
    -Actual ([string](Get-ObjectProperty $finalOperational "value_age_clock_anomaly_count" "missing")) -Expected "0"
Add-QaCheck -Name "Logger service instance remained stable" `
    -Passed (
        $expectedLoggerServiceInstanceId -ne "" -and
        $finalLoggerServiceInstanceId -eq $expectedLoggerServiceInstanceId
    ) `
    -Actual "$expectedLoggerServiceInstanceId -> $finalLoggerServiceInstanceId" `
    -Expected "unchanged"
Add-QaCheck -Name "Runtime build commit" `
    -Passed ($expectedBuildCommit -match "^[0-9a-f]{40}$") `
    -Actual $(if ($expectedBuildCommit) { $expectedBuildCommit } else { "missing" }) `
    -Expected "40-character lowercase Git commit"
Add-QaCheck -Name "Final operational sample sequence" `
    -Passed ($expectedMinimumSampleSeq -gt 0) `
    -Actual ([string]$expectedMinimumSampleSeq) `
    -Expected "positive current-session sample_seq"
Add-QaCheck -Name "Current CSV file identity" `
    -Passed (
        $expectedCsvFileName -match
            "^Factory_Integrated_Log_v2_[A-Za-z0-9_.-]+\.csv$"
    ) `
    -Actual $(if ($expectedCsvFileName) { $expectedCsvFileName } else { "missing" }) `
    -Expected "current v2 CSV basename"

if (-not $SkipStopPrompt) {
    Write-Host ""
    Write-Host "[3/5] Finalizing SmartFactoryLogger CSV files safely." -ForegroundColor Yellow
    $shutdownCheckpoint = Invoke-OperatorShutdownCheckpoint `
        -TimeoutSeconds $GracefulShutdownTimeoutSeconds
    $backendStopped = [bool]$shutdownCheckpoint.backend_stopped
    $operatorShutdownRequested = [bool]$shutdownCheckpoint.operator_shutdown_requested
    if ($backendStopped -and -not $operatorShutdownRequested) {
        Add-QaWarning "The backend had already stopped before the operator shutdown step."
    }

    Add-QaCheck -Name "Backend stopped for finalized CSV validation" -Passed $backendStopped `
        -Actual $(if ($backendStopped) {
            if ($operatorShutdownRequested) { "stopped after operator UI shutdown" } else { "already stopped" }
        } else { "still reachable after graceful shutdown timeout" }) `
        -Expected "stopped"
    if (-not $backendStopped) {
        $runtimeSummary = [ordered]@{
            initial_rows_total = $initialRows
            final_rows_total = $finalRows
            sample_count = $samples.Count
            poll_statuses = @($samples.poll_status | Sort-Object -Unique)
            value_origins = @($samples.temperature_value_origin | Sort-Object -Unique)
            # Compatibility field: QA no longer calls the authenticated shutdown API.
            qa_shutdown_requested = $false
            operator_shutdown_requested = $operatorShutdownRequested
        }
        Add-QaWarning "Finalized CSV validation was skipped because the backend is still running."
        Save-QaArtifact -Verdict "FAIL" -RuntimeSummary $runtimeSummary -FileSummary $null -ValidatorOutput ""
        Write-Host ""
        Write-Host "FINAL RESULT: FAIL" -ForegroundColor Red
        Write-Host "SmartFactoryLogger did not finish graceful shutdown within $GracefulShutdownTimeoutSeconds seconds."
        Write-Host "Do not force-kill it. Keep the app closed and provide this evidence file for diagnosis."
        Write-Host "Evidence: $OutputPath"
        exit 1
    }
} else {
    Add-QaWarning "Stop prompt was skipped. Validator may fail if CSV files are still open."
}

Write-Host ""
Write-Host "[4/5] Checking the finalized CSV and config attestation..." -ForegroundColor Cyan
$directories = Get-LogDirectoryCandidates -ExplicitLogPath $LogPath -SettingsPath $ConfigPath
$metadataMatch = Find-LatestMetadata `
    -Directories $directories `
    -ExpectedLoggerServiceInstanceId $expectedLoggerServiceInstanceId `
    -ExpectedBuildCommit $expectedBuildCommit `
    -ExpectedMinimumSampleSeq $expectedMinimumSampleSeq `
    -ExpectedCsvFileName $expectedCsvFileName
$metadataFile = if ($null -ne $metadataMatch) { $metadataMatch.file } else { $null }
$fileSummary = [ordered]@{
    config_path = $ConfigPath
    searched_log_directories = $directories
    expected_logger_service_instance_id = $expectedLoggerServiceInstanceId
    expected_build_commit = $expectedBuildCommit
    expected_minimum_sample_seq = $expectedMinimumSampleSeq
    observed_csv_file_name = $expectedCsvFileName
    log_directory = $null
    metadata_file = $null
    csv_file = $null
    observation_fact_file = $null
    spot_image_fact_final_manifest_file = $null
}
$validatorOutput = ""

if ($null -eq $metadataFile) {
    Add-QaCheck -Name "Current-session metadata sidecar" -Passed $false -Actual "not found" `
        -Expected "sidecar matching the observed logger instance and build commit"
} else {
    try {
        $fileSummary.log_directory = $metadataFile.DirectoryName
        $fileSummary.metadata_file = $metadataFile.FullName
        Add-QaCheck -Name "Current-session metadata sidecar" -Passed $true `
            -Actual $metadataFile.Name -Expected "matching sidecar found"
        $metadataJson = $metadataMatch.metadata
        $schemaMetadata = Get-ObjectProperty $metadataJson "schema_metadata"
        $configSnapshot = Get-ObjectProperty $metadataJson "spot_configuration_snapshot"
        $factManifest = Get-ObjectProperty $metadataJson "spot_observation_fact_manifest"

        Add-QaCheck -Name "Sidecar logger service instance" `
        -Passed (
            ([string](Get-ObjectProperty $schemaMetadata "logger_service_instance_id" "")) -eq
            $expectedLoggerServiceInstanceId
        ) `
        -Actual ([string](Get-ObjectProperty $schemaMetadata "logger_service_instance_id" "missing")) `
        -Expected $expectedLoggerServiceInstanceId
        Add-QaCheck -Name "Sidecar build commit" `
        -Passed (
            ([string](Get-ObjectProperty $schemaMetadata "git_commit" "")) -eq
            $expectedBuildCommit -and
            ([string](Get-ObjectProperty $configSnapshot "build_git_commit" "")) -eq
            $expectedBuildCommit
        ) `
        -Actual (
            "{0}/{1}" -f
                [string](Get-ObjectProperty $schemaMetadata "git_commit" "missing"),
                [string](Get-ObjectProperty $configSnapshot "build_git_commit" "missing")
        ) `
        -Expected "$expectedBuildCommit/$expectedBuildCommit"
        Add-QaCheck -Name "Matching CSV final sample sequence" `
        -Passed ($metadataMatch.csv_final_sample_seq -ge $expectedMinimumSampleSeq) `
        -Actual ([string]$metadataMatch.csv_final_sample_seq) `
        -Expected ">= $expectedMinimumSampleSeq"
        Add-QaCheck -Name "Shutdown CSV file identity" `
        -Passed (
            (Split-Path -Leaf $metadataMatch.csv_file) -match
                "^Factory_Integrated_Log_v2_[A-Za-z0-9_.-]+\.csv$"
        ) `
        -Actual (Split-Path -Leaf $metadataMatch.csv_file) `
        -Expected "current-session shutdown closeout CSV"
        Add-QaCheck -Name "Sidecar schema" `
        -Passed (([string](Get-ObjectProperty $schemaMetadata "active_schema_version")) -eq "2.5.0") `
        -Actual ([string](Get-ObjectProperty $schemaMetadata "active_schema_version" "missing")) -Expected "2.5.0"
        Add-QaCheck -Name "Sidecar hardening flag" `
        -Passed (Convert-ToBoolean (Get-ObjectProperty $schemaMetadata "csv_v2_temperature_hardening_enabled" $false)) `
        -Actual ([string](Get-ObjectProperty $schemaMetadata "csv_v2_temperature_hardening_enabled" "missing")) -Expected "true"
        Add-QaCheck -Name "Config operator verification" `
        -Passed (Convert-ToBoolean (Get-ObjectProperty $configSnapshot "config_operator_verified" $false)) `
        -Actual ([string](Get-ObjectProperty $configSnapshot "config_operator_verified" "missing")) -Expected "true"
        Add-QaCheck -Name "Config attestation status" `
        -Passed (([string](Get-ObjectProperty $configSnapshot "config_attestation_status")) -eq "verified") `
        -Actual ([string](Get-ObjectProperty $configSnapshot "config_attestation_status" "missing")) -Expected "verified"
        Add-QaCheck -Name "Config drift" `
        -Passed (-not (Convert-ToBoolean (Get-ObjectProperty $configSnapshot "config_drift_detected" $true))) `
        -Actual ([string](Get-ObjectProperty $configSnapshot "config_drift_detected" "missing")) -Expected "false"
        $fingerprint = [string](Get-ObjectProperty $configSnapshot "spot_config_fingerprint_sha256" "")
        $verifiedFingerprint = [string](Get-ObjectProperty $configSnapshot "spot_config_verified_fingerprint_sha256" "")
        $configuredComparatorVerified = Convert-ToBoolean `
            (Get-ObjectProperty $configSnapshot "low_signal_comparator_configured_verified" $false)
        $attestationCanBeApplied = (
            ([string](Get-ObjectProperty $configSnapshot "config_attestation_status" "")) -eq "not_requested" -and
            $fingerprint -match "^[0-9a-f]{64}$" -and
            $configuredComparatorVerified -and
            -not (Convert-ToBoolean (Get-ObjectProperty $configSnapshot "config_drift_detected" $true))
        )
        $fingerprintStatus = if ($fingerprint -eq $verifiedFingerprint -and $fingerprint) {
            "matched"
        } else {
            "not matched"
        }
        Add-QaCheck -Name "Config fingerprint match" `
        -Passed ($fingerprint -match "^[0-9a-f]{64}$" -and $fingerprint -eq $verifiedFingerprint) `
        -Actual $fingerprintStatus `
        -Expected "matched"
        Add-QaCheck -Name "Low-signal comparator verification" `
        -Passed (Convert-ToBoolean (Get-ObjectProperty $configSnapshot "low_signal_comparator_verified" $false)) `
        -Actual ([string](Get-ObjectProperty $configSnapshot "low_signal_comparator_verified" "missing")) -Expected "true"
        $readbackStatus = [string](Get-ObjectProperty $configSnapshot "device_config_readback_status" "missing")
        Add-QaCheck -Name "Device readback policy" -Passed ($readbackStatus -in @("matched", "not_supported")) `
        -Actual $readbackStatus -Expected "matched or not_supported"
        Add-QaCheck -Name "Fact manifest enabled" `
        -Passed (Convert-ToBoolean (Get-ObjectProperty $factManifest "enabled" $false)) `
        -Actual ([string](Get-ObjectProperty $factManifest "enabled" "missing")) -Expected "true"
        Add-QaCheck -Name "Fact manifest write failures" `
        -Passed ((Convert-ToInt64 (Get-ObjectProperty $factManifest "write_failure_count" 0)) -eq 0) `
        -Actual ([string](Get-ObjectProperty $factManifest "write_failure_count" "missing")) -Expected "0"
        Add-QaCheck -Name "Fact manifest pending spool" `
        -Passed ((Convert-ToInt64 (Get-ObjectProperty $factManifest "spool_pending_count" 0)) -eq 0) `
        -Actual ([string](Get-ObjectProperty $factManifest "spool_pending_count" "missing")) -Expected "0"

        $csvPath = $metadataMatch.csv_file
        $fileSummary.csv_file = $csvPath
        Add-QaCheck -Name "Matching v2 CSV" -Passed (Test-Path -LiteralPath $csvPath -PathType Leaf) `
        -Actual (Split-Path -Leaf $csvPath) -Expected "found"

        $factRelativePath = [string](Get-ObjectProperty $factManifest "path" "spot_observation_fact.csv")
        $factPath = if ([System.IO.Path]::IsPathRooted($factRelativePath)) {
            $factRelativePath
        } else {
            Join-Path $metadataFile.DirectoryName $factRelativePath
        }
        $fileSummary.observation_fact_file = $factPath
        Add-QaCheck -Name "Observation fact CSV" -Passed (Test-Path -LiteralPath $factPath -PathType Leaf) `
        -Actual (Split-Path -Leaf $factPath) -Expected "found"

        Write-Host ""
        Write-Host "[5/5] Running the repository validator..." -ForegroundColor Cyan
        $validatorScript = Join-Path $repoRoot "scripts\validate_csv_v2_shadow.py"
        $pythonExe = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
        $portableValidatorExe = Join-Path $PSScriptRoot "validate_csv_v2_shadow.exe"
        $validatorArguments = @(
            "--v2", $csvPath,
            "--metadata", $metadataFile.FullName,
            "--spot-observation-fact", $factPath
        )
        $spotImageFactFinalManifestPath = Join-Path $metadataFile.DirectoryName "spot_image_fact_manifest.final.json"
        if (Test-Path -LiteralPath $spotImageFactFinalManifestPath -PathType Leaf) {
            $fileSummary.spot_image_fact_final_manifest_file = $spotImageFactFinalManifestPath
            $validatorArguments += @(
                "--spot-image-fact-final-manifest", $spotImageFactFinalManifestPath
            )
        }
        if (
            (Test-Path -LiteralPath $portableValidatorExe -PathType Leaf) -and
            (Test-Path -LiteralPath $csvPath -PathType Leaf) -and
            (Test-Path -LiteralPath $factPath -PathType Leaf)
        ) {
            $validatorLines = @(& $portableValidatorExe @validatorArguments 2>&1)
            $validatorExitCode = $LASTEXITCODE
            $validatorOutput = $validatorLines -join [Environment]::NewLine
            Add-QaCheck -Name "Full CSV validator" -Passed ($validatorExitCode -eq 0) `
                -Actual "portable_exe_exit_code=$validatorExitCode" -Expected "exit_code=0"
            if ($validatorExitCode -ne 0) {
                Write-Host ($validatorLines | Select-Object -Last 20 | Out-String) -ForegroundColor Red
            }
        } elseif (
            (Test-Path -LiteralPath $validatorScript -PathType Leaf) -and
            (Test-Path -LiteralPath $pythonExe -PathType Leaf) -and
            (Test-Path -LiteralPath $csvPath -PathType Leaf) -and
            (Test-Path -LiteralPath $factPath -PathType Leaf)
        ) {
            $validatorLines = @(& $pythonExe $validatorScript @validatorArguments 2>&1)
            $validatorExitCode = $LASTEXITCODE
            $validatorOutput = $validatorLines -join [Environment]::NewLine
            Add-QaCheck -Name "Full CSV validator" -Passed ($validatorExitCode -eq 0) `
                -Actual "python_exit_code=$validatorExitCode" -Expected "exit_code=0"
            if ($validatorExitCode -ne 0) {
                Write-Host ($validatorLines | Select-Object -Last 20 | Out-String) -ForegroundColor Red
            }
        } else {
            Add-QaCheck -Name "Full CSV validator" -Passed $false -Actual "validator prerequisites missing" `
                -Expected "portable validator EXE or repo Python validator, plus CSV/metadata/fact"
        }
    } catch {
        Add-QaCheck -Name "Finalized artifact inspection" -Passed $false -Actual $_.Exception.Message `
            -Expected "readable finalized metadata, CSV, and observation fact"
    }
}

$failedChecks = @($checks | Where-Object { -not $_.passed })
$verdict = if ($failedChecks.Count -eq 0) { "PASS" } else { "FAIL" }
$runtimeSummary = [ordered]@{
    logger_service_instance_id = $expectedLoggerServiceInstanceId
    build_commit = $expectedBuildCommit
    minimum_sample_seq = $expectedMinimumSampleSeq
    observed_csv_file_name = $expectedCsvFileName
    finalized_csv_file_name = if ($null -ne $metadataMatch) {
        Split-Path -Leaf $metadataMatch.csv_file
    } else {
        ""
    }
    initial_rows_total = $initialRows
    final_rows_total = $finalRows
    sample_count = $samples.Count
    poll_statuses = @($samples.poll_status | Sort-Object -Unique)
    value_origins = @($samples.temperature_value_origin | Sort-Object -Unique)
    # Compatibility field: QA no longer calls the authenticated shutdown API.
    qa_shutdown_requested = $false
    operator_shutdown_requested = $operatorShutdownRequested
}
Save-QaArtifact -Verdict $verdict -RuntimeSummary $runtimeSummary -FileSummary $fileSummary `
    -ValidatorOutput $validatorOutput

Write-Host ""
if ($verdict -eq "PASS") {
    Write-Host "FINAL RESULT: PASS" -ForegroundColor Green
    Write-Host "The v2.5 runtime, attestation, CSV, fact, and validator checks passed."
    Write-Host "You can now close any remaining SmartFactoryLogger window."
} else {
    Write-Host "FINAL RESULT: FAIL" -ForegroundColor Red
    Write-Host "Failed checks:"
    $failedChecks | ForEach-Object { Write-Host " - $($_.name): $($_.actual)" }
    if ($attestationCanBeApplied) {
        Write-Host ""
        Write-Host "NEXT STEP: the v2.5 runtime is ready for config attestation." -ForegroundColor Yellow
        Write-Host "Keep SmartFactoryLogger closed and run:"
        Write-Host ".\apply_spot_temperature_v25_attestation.cmd" -ForegroundColor Cyan
    }
}
Write-Host "Evidence: $OutputPath"
$processExitCode = if ($verdict -eq "PASS") { 0 } else { 1 }
exit $processExitCode
