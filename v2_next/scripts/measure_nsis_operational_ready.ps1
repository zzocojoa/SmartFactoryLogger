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

function Get-ObjectPropertyValue {
    param(
        [object]$InputObject,
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

function Get-Utf8Sha256 {
    param([string]$Text)

    $encoding = New-Object System.Text.UTF8Encoding($false)
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $encoding.GetBytes($Text)
        $hash = $hasher.ComputeHash($bytes)
        return ([System.BitConverter]::ToString($hash)).Replace("-", "")
    } finally {
        $hasher.Dispose()
    }
}

function Test-SafeBundleRelativePath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }
    if ($Path.Contains("\") -or $Path.Contains(":")) {
        return $false
    }
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $false
    }
    $segments = @($Path.Split("/"))
    if ($segments.Count -eq 0) {
        return $false
    }
    foreach ($segment in $segments) {
        if ([string]::IsNullOrWhiteSpace($segment) -or $segment -eq "." -or $segment -eq "..") {
            return $false
        }
    }
    return $true
}

function Test-BackendBundleIntegrity {
    param([string]$BackendRoot)

    $errors = New-Object System.Collections.Generic.List[string]
    $missingFiles = New-Object System.Collections.Generic.List[string]
    $unexpectedFiles = New-Object System.Collections.Generic.List[string]
    $mismatchFiles = New-Object System.Collections.Generic.List[string]
    $invalidPaths = New-Object System.Collections.Generic.List[string]
    $expectedBundleSha256 = ""
    $actualBundleSha256 = ""
    $buildGitCommit = ""
    $schemaVersion = ""
    $packagingMode = ""
    $expectedFileCount = 0
    $actualFileCount = 0
    $verifiedFileCount = 0
    $manifestPath = Join-Path $BackendRoot "bundle-manifest.json"

    if (-not (Test-Path -LiteralPath $BackendRoot -PathType Container)) {
        [void]$errors.Add("backend-root-missing")
    } elseif (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        [void]$errors.Add("manifest-missing")
    }

    $manifest = $null
    if ($errors.Count -eq 0) {
        try {
            $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        } catch {
            [void]$errors.Add("manifest-invalid-json")
        }
    }

    if ($null -ne $manifest) {
        $schemaVersion = [string](Get-ObjectPropertyValue $manifest "schema_version")
        $packagingMode = [string](Get-ObjectPropertyValue $manifest "packaging_mode")
        $buildGitCommit = [string](Get-ObjectPropertyValue $manifest "build_git_commit")
        $expectedBundleSha256 = [string](Get-ObjectPropertyValue $manifest "bundle_sha256")
        $declaredFileCount = Get-ObjectPropertyValue $manifest "file_count"
        if ($null -ne $declaredFileCount) {
            $expectedFileCount = [int]$declaredFileCount
        }

        if ($schemaVersion -ne "smartfactory-backend-bundle-v1") {
            [void]$errors.Add("schema-version-invalid")
        }
        if ($packagingMode -ne "onedir") {
            [void]$errors.Add("packaging-mode-invalid")
        }
        if ($buildGitCommit -notmatch '^[0-9a-f]{40}$') {
            [void]$errors.Add("build-git-commit-invalid")
        }
        if ($expectedBundleSha256 -notmatch '^[0-9A-Fa-f]{64}$') {
            [void]$errors.Add("bundle-sha256-invalid")
        }

        $rootFullPath = (Get-Item -LiteralPath $BackendRoot).FullName.TrimEnd("\")
        $rootPrefix = $rootFullPath + "\"
        $manifestFullPath = (Get-Item -LiteralPath $manifestPath).FullName
        $actualRelativePaths = [string[]]@(
            Get-ChildItem -LiteralPath $rootFullPath -Recurse -File |
                Where-Object { $_.FullName -ne $manifestFullPath } |
                ForEach-Object {
                    $_.FullName.Substring($rootPrefix.Length).Replace("\", "/")
                }
        )
        [System.Array]::Sort($actualRelativePaths, [System.StringComparer]::Ordinal)
        $actualFileCount = $actualRelativePaths.Count

        $manifestEntries = @(Get-ObjectPropertyValue $manifest "files")
        $expectedSet = @{}
        $entryPaths = New-Object System.Collections.Generic.List[string]
        $actualAggregateLines = New-Object System.Collections.Generic.List[string]
        foreach ($entry in $manifestEntries) {
            $relativePath = [string](Get-ObjectPropertyValue $entry "path")
            if (-not (Test-SafeBundleRelativePath $relativePath)) {
                [void]$invalidPaths.Add($relativePath)
                continue
            }
            if ($expectedSet.ContainsKey($relativePath)) {
                [void]$invalidPaths.Add($relativePath)
                continue
            }
            $expectedSet[$relativePath] = $true
            [void]$entryPaths.Add($relativePath)

            $nativeRelativePath = $relativePath.Replace("/", "\")
            $candidatePath = [System.IO.Path]::GetFullPath((Join-Path $rootFullPath $nativeRelativePath))
            if (-not $candidatePath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                [void]$invalidPaths.Add($relativePath)
                continue
            }
            if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) {
                [void]$missingFiles.Add($relativePath)
                continue
            }

            $actualFile = Get-Item -LiteralPath $candidatePath
            $actualSha256 = (Get-FileHash -LiteralPath $candidatePath -Algorithm SHA256).Hash.ToUpperInvariant()
            $expectedLength = [int64](Get-ObjectPropertyValue $entry "length")
            $expectedSha256 = [string](Get-ObjectPropertyValue $entry "sha256")
            if ($actualFile.Length -ne $expectedLength -or $actualSha256 -ne $expectedSha256) {
                [void]$mismatchFiles.Add($relativePath)
            } else {
                $verifiedFileCount++
            }
            [void]$actualAggregateLines.Add("$relativePath`t$($actualFile.Length)`t$actualSha256")
        }

        if ($expectedFileCount -ne $manifestEntries.Count) {
            [void]$errors.Add("manifest-file-count-invalid")
        }
        $sortedEntryPaths = [string[]]$entryPaths.ToArray()
        [System.Array]::Sort($sortedEntryPaths, [System.StringComparer]::Ordinal)
        if (($sortedEntryPaths -join "`n") -ne ($entryPaths.ToArray() -join "`n")) {
            [void]$errors.Add("manifest-file-order-invalid")
        }
        foreach ($relativePath in $actualRelativePaths) {
            if (-not $expectedSet.ContainsKey($relativePath)) {
                [void]$unexpectedFiles.Add($relativePath)
            }
        }
        if ($missingFiles.Count -eq 0 -and $invalidPaths.Count -eq 0) {
            $aggregatePayload = ($actualAggregateLines.ToArray() -join "`n") + "`n"
            $actualBundleSha256 = Get-Utf8Sha256 -Text $aggregatePayload
        }
        if ($actualBundleSha256 -ne $expectedBundleSha256) {
            [void]$errors.Add("bundle-sha256-mismatch")
        }
    }

    $ok = (
        $errors.Count -eq 0 -and
        $missingFiles.Count -eq 0 -and
        $unexpectedFiles.Count -eq 0 -and
        $mismatchFiles.Count -eq 0 -and
        $invalidPaths.Count -eq 0 -and
        $expectedFileCount -eq $actualFileCount -and
        $verifiedFileCount -eq $expectedFileCount
    )
    return [pscustomobject][ordered]@{
        ok                     = $ok
        manifest_path          = $manifestPath
        schema_version         = $schemaVersion
        packaging_mode         = $packagingMode
        build_git_commit       = $buildGitCommit
        expected_bundle_sha256 = $expectedBundleSha256
        actual_bundle_sha256   = $actualBundleSha256
        expected_file_count    = $expectedFileCount
        actual_file_count      = $actualFileCount
        verified_file_count    = $verifiedFileCount
        missing_files          = @($missingFiles.ToArray())
        unexpected_files       = @($unexpectedFiles.ToArray())
        mismatch_files         = @($mismatchFiles.ToArray())
        invalid_paths          = @($invalidPaths.ToArray())
        errors                 = @($errors.ToArray())
    }
}

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
        "renderer.first-data-snapshot",
        "renderer.first-live-data",
        "renderer.dashboard-ready",
        "renderer.dashboard-operational-ready"
    )
}

function Get-RequiredBackendProgressStages {
    return @(
        "lifespan_begin",
        "csv_logger_ready",
        "config_sync_ready",
        "config_watch_ready",
        "plc_service_ready",
        "comm_metrics_ready",
        "memory_service_ready",
        "spot_poll_ready",
        "lifespan_complete"
    )
}

function Get-BackendProgressStages {
    param([object[]]$Events)

    return @(
        $Events |
            Where-Object { $_.event -eq "backend.startup-progress" } |
            ForEach-Object {
                Get-EventPayloadValue -EventItem $_ -Name "stage"
            } |
            Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } |
            Sort-Object -Unique
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

function Resolve-DiagnosticBudgetStatus {
    param(
        [object]$OperationalTimeout,
        [object]$OperationalReady
    )

    if ($null -eq $OperationalTimeout) {
        return "WITHIN_DIAGNOSTIC_BUDGET"
    }
    if ($null -ne $OperationalReady) {
        return "RECOVERED_AFTER_DIAGNOSTIC_TIMEOUT"
    }
    return "DIAGNOSTIC_TIMEOUT_NOT_RECOVERED"
}

function Resolve-PerformanceStatus {
    param(
        [object]$OperationalReady,
        [object]$LauncherObservedMs,
        [double]$BudgetMs = 30000.0
    )

    if (
        $null -eq $OperationalReady -or
        $null -eq $LauncherObservedMs -or
        $null -eq $OperationalReady.PSObject.Properties["elapsed_ms"]
    ) {
        return "NOT_MEASURED"
    }

    if (
        [double]$OperationalReady.elapsed_ms -le $BudgetMs -and
        [double]$LauncherObservedMs -le $BudgetMs
    ) {
        return "PASS"
    }
    return "FAIL"
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
        [pscustomobject]@{ event = "renderer.first-data-snapshot" },
        [pscustomobject]@{ event = "renderer.first-live-data" },
        [pscustomobject]@{ event = "renderer.dashboard-ready" },
        [pscustomobject]@{ event = "renderer.dashboard-operational-ready"; elapsed_ms = 5000.0 }
    )
    foreach ($BackendStage in (Get-RequiredBackendProgressStages)) {
        $FixtureEvents += [pscustomobject]@{
            event = "backend.startup-progress"
            payload = [pscustomobject]@{ stage = $BackendStage }
        }
    }
    $Missing = @(Get-MissingMilestones -Events $FixtureEvents -Required (Get-RequiredMilestones))
    if ($Missing.Count -ne 0) {
        throw "Fixture milestone validation failed."
    }
    $FixtureBackendStages = @(Get-BackendProgressStages -Events $FixtureEvents)
    $MissingBackendStages = @(
        Get-RequiredBackendProgressStages |
            Where-Object { $FixtureBackendStages -notcontains $_ }
    )
    if ($MissingBackendStages.Count -ne 0) {
        throw "Fixture backend progress stage validation failed."
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

    $ReadyFixture = [pscustomobject]@{
        event = "renderer.dashboard-operational-ready"; elapsed_ms = 5000.0
    }
    if ((Resolve-MeasurementStatus "READY" $ReadyFixture 0 "raf") -ne "PASS") {
        throw "Fixture PASS classification failed."
    }
    if ((Resolve-MeasurementStatus "OPERATIONAL_TIMEOUT" $null 1 $null) -ne "OPERATIONAL_TIMEOUT") {
        throw "Fixture timeout classification failed."
    }
    if ((Resolve-MeasurementStatus "MULTIPLE_STARTUP_SESSIONS" $null 8 $null) -ne "CONTAMINATED") {
        throw "Fixture contamination classification failed."
    }
    $TimeoutFixture = [pscustomobject]@{ event = "renderer.dashboard-operational-timeout" }
    if ((Resolve-DiagnosticBudgetStatus $TimeoutFixture $ReadyFixture) -ne "RECOVERED_AFTER_DIAGNOSTIC_TIMEOUT") {
        throw "Fixture delayed recovery classification failed."
    }
    if ((Resolve-DiagnosticBudgetStatus $TimeoutFixture $null) -ne "DIAGNOSTIC_TIMEOUT_NOT_RECOVERED") {
        throw "Fixture unrecovered diagnostic timeout classification failed."
    }
    if ((Resolve-PerformanceStatus $ReadyFixture 5100.0) -ne "PASS") {
        throw "Fixture performance PASS classification failed."
    }
    $LateReadyFixture = [pscustomobject]@{
        event = "renderer.dashboard-operational-ready"; elapsed_ms = 35000.0
    }
    if ((Resolve-PerformanceStatus $LateReadyFixture 35100.0) -ne "FAIL") {
        throw "Fixture performance FAIL classification failed."
    }
    if ((Resolve-PerformanceStatus $null $null) -ne "NOT_MEASURED") {
        throw "Fixture performance not-measured classification failed."
    }

    $BundleFixtureRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
        "smartfactory-bundle-selftest-" + [System.Guid]::NewGuid().ToString("N")
    )
    try {
        $InternalFixtureRoot = Join-Path $BundleFixtureRoot "_internal"
        New-Item -ItemType Directory -Path $InternalFixtureRoot -Force | Out-Null
        [System.IO.File]::WriteAllText(
            (Join-Path $BundleFixtureRoot "SmartFactoryBackend.exe"),
            "fixture-executable",
            (New-Object System.Text.UTF8Encoding($false))
        )
        [System.IO.File]::WriteAllText(
            (Join-Path $InternalFixtureRoot "runtime.txt"),
            "fixture-runtime",
            (New-Object System.Text.UTF8Encoding($false))
        )

        $FixturePaths = [string[]]@(
            "SmartFactoryBackend.exe",
            "_internal/runtime.txt"
        )
        [System.Array]::Sort($FixturePaths, [System.StringComparer]::Ordinal)
        $FixtureEntries = New-Object System.Collections.Generic.List[object]
        $FixtureAggregateLines = New-Object System.Collections.Generic.List[string]
        foreach ($FixturePath in $FixturePaths) {
            $FixtureNativePath = $FixturePath.Replace("/", "\")
            $FixtureFullPath = Join-Path $BundleFixtureRoot $FixtureNativePath
            $FixtureFile = Get-Item -LiteralPath $FixtureFullPath
            $FixtureSha = (Get-FileHash -LiteralPath $FixtureFullPath -Algorithm SHA256).Hash.ToUpperInvariant()
            [void]$FixtureEntries.Add([ordered]@{
                path   = $FixturePath
                length = [int64]$FixtureFile.Length
                sha256 = $FixtureSha
            })
            [void]$FixtureAggregateLines.Add("$FixturePath`t$($FixtureFile.Length)`t$FixtureSha")
        }
        $FixtureAggregatePayload = ($FixtureAggregateLines.ToArray() -join "`n") + "`n"
        $FixtureManifest = [ordered]@{
            schema_version   = "smartfactory-backend-bundle-v1"
            packaging_mode   = "onedir"
            build_git_commit = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            file_count       = $FixtureEntries.Count
            bundle_sha256    = Get-Utf8Sha256 -Text $FixtureAggregatePayload
            files            = $FixtureEntries.ToArray()
        }
        $FixtureManifestPath = Join-Path $BundleFixtureRoot "bundle-manifest.json"
        [System.IO.File]::WriteAllText(
            $FixtureManifestPath,
            ($FixtureManifest | ConvertTo-Json -Depth 5) + "`n",
            (New-Object System.Text.UTF8Encoding($false))
        )

        $FixtureIntegrity = Test-BackendBundleIntegrity -BackendRoot $BundleFixtureRoot
        if (-not $FixtureIntegrity.ok) {
            throw "Fixture backend bundle integrity validation failed."
        }
        Add-Content -LiteralPath (Join-Path $InternalFixtureRoot "runtime.txt") -Value "tampered"
        $TamperedIntegrity = Test-BackendBundleIntegrity -BackendRoot $BundleFixtureRoot
        if ($TamperedIntegrity.ok -or @($TamperedIntegrity.mismatch_files) -notcontains "_internal/runtime.txt") {
            throw "Fixture backend bundle tamper detection failed."
        }
    } finally {
        Remove-Item -LiteralPath $BundleFixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
    }

    [pscustomobject][ordered]@{
        status               = "PASS"
        parser               = "PASS"
        session_correlation  = "PASS"
        milestone_validation = "PASS"
        failure_classification = "PASS"
        bundle_integrity     = "PASS"
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
$BackendBundleRoot = Join-Path (Split-Path -Parent $ResolvedExePath) "resources\backend"
$BackendBundleIntegrity = Test-BackendBundleIntegrity -BackendRoot $BackendBundleRoot
if (-not $BackendBundleIntegrity.ok) {
    [pscustomobject][ordered]@{
        status                  = "BUNDLE_INTEGRITY_FAILED"
        functional_status       = "BUNDLE_INTEGRITY_FAILED"
        performance_status      = "NOT_MEASURED"
        performance_budget_ms   = 30000.0
        exe_path                = $ResolvedExePath
        backend_bundle          = $BackendBundleIntegrity
        message                 = "Installed backend bundle does not match its integrity manifest."
    } | ConvertTo-Json -Depth 7
    exit 3
}
$ContaminatingProcesses = @(Get-ContaminatingProcesses)
if ($ContaminatingProcesses.Count -gt 0) {
    [pscustomobject][ordered]@{
        status                  = "CONTAMINATED"
        functional_status       = "CONTAMINATED"
        performance_status      = "NOT_MEASURED"
        performance_budget_ms   = 30000.0
        exe_path                = $ResolvedExePath
        backend_bundle          = $BackendBundleIntegrity
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
$BackendProgressStages = @(Get-BackendProgressStages -Events $SelectedEvents)
$MissingBackendProgressStages = @(
    Get-RequiredBackendProgressStages |
        Where-Object { $BackendProgressStages -notcontains $_ }
)
$BackendReady = Get-StartupEvent -Events $SelectedEvents -Name "renderer.backend-health-ready"
$FirstDataSnapshot = Get-StartupEvent -Events $SelectedEvents -Name "renderer.first-data-snapshot"
$FirstLiveData = Get-StartupEvent -Events $SelectedEvents -Name "renderer.first-live-data"
$DashboardReady = Get-StartupEvent -Events $SelectedEvents -Name "renderer.dashboard-ready"
$OperationalTimeout = Get-StartupEvent -Events $SelectedEvents -Name "renderer.dashboard-operational-timeout"
$OperationalReady = Get-StartupEvent -Events $SelectedEvents -Name "renderer.dashboard-operational-ready"
$ReadyStrategy = Get-EventPayloadValue -EventItem $OperationalReady -Name "ready_strategy"

if ($TerminalReason -eq "TIMEOUT" -and $null -ne $OperationalTimeout) {
    $TerminalReason = "OPERATIONAL_TIMEOUT"
}

$DiagnosticBudgetStatus = Resolve-DiagnosticBudgetStatus `
    -OperationalTimeout $OperationalTimeout `
    -OperationalReady $OperationalReady

$Status = Resolve-MeasurementStatus `
    -TerminalReason $TerminalReason `
    -OperationalReady $OperationalReady `
    -MissingMilestoneCount ($MissingMilestones.Count + $MissingBackendProgressStages.Count) `
    -ReadyStrategy $ReadyStrategy

$OperationalReadyTimestampUtc = $null
$LauncherObservedMs = $null
if ($null -ne $OperationalReady) {
    $OperationalReadyTimestampUtc = [string]$OperationalReady.timestamp_utc
    $ReadyTimestamp = [DateTimeOffset]::Parse($OperationalReadyTimestampUtc)
    $LauncherObservedMs = [math]::Round(($ReadyTimestamp - $StartedAtUtc).TotalMilliseconds, 1)
}

$PerformanceBudgetMs = 30000.0
$PerformanceStatus = Resolve-PerformanceStatus `
    -OperationalReady $OperationalReady `
    -LauncherObservedMs $LauncherObservedMs `
    -BudgetMs $PerformanceBudgetMs

$Result = [pscustomobject][ordered]@{
    status                                  = $Status
    functional_status                       = $Status
    performance_status                      = $PerformanceStatus
    performance_budget_ms                   = $PerformanceBudgetMs
    terminal_reason                         = $TerminalReason
    exe_path                                = $ResolvedExePath
    process_id                              = $LaunchedProcess.Id
    startup_session_id                      = $SelectedSessionId
    started_at_utc                          = $StartedAtUtc.ToString("o")
    operational_ready_timestamp_utc         = $OperationalReadyTimestampUtc
    timeout_sec                             = $TimeoutSec
    log_path                                = $SelectedLogPath
    backend_bundle                          = $BackendBundleIntegrity
    backend_health_ready_elapsed_ms         = if ($null -eq $BackendReady) { $null } else { $BackendReady.elapsed_ms }
    first_data_snapshot_elapsed_ms           = if ($null -eq $FirstDataSnapshot) { $null } else { $FirstDataSnapshot.elapsed_ms }
    first_live_data_elapsed_ms               = if ($null -eq $FirstLiveData) { $null } else { $FirstLiveData.elapsed_ms }
    dashboard_ready_elapsed_ms               = if ($null -eq $DashboardReady) { $null } else { $DashboardReady.elapsed_ms }
    operational_ready_elapsed_ms             = if ($null -eq $OperationalReady) { $null } else { $OperationalReady.elapsed_ms }
    launcher_observed_operational_ready_ms   = $LauncherObservedMs
    ready_strategy                          = $ReadyStrategy
    operational_timeout_observed            = $null -ne $OperationalTimeout
    operational_timeout_elapsed_ms           = if ($null -eq $OperationalTimeout) { $null } else { $OperationalTimeout.elapsed_ms }
    operational_timeout_budget_ms            = Get-EventPayloadValue -EventItem $OperationalTimeout -Name "timeout_ms"
    operational_timeout_missing_gates       = Get-EventPayloadValue -EventItem $OperationalTimeout -Name "missing_gates"
    diagnostic_budget_status                 = $DiagnosticBudgetStatus
    backend_progress_stages                  = $BackendProgressStages
    missing_backend_progress_stages          = $MissingBackendProgressStages
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
