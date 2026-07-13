param(
    [string]$BackendBaseUrl = "http://127.0.0.1:8000",
    [string]$ConfigPath = "",
    [string]$LogPath = "",
    [string]$MetadataPath = "",
    [string]$OperatorId = "",
    [switch]$Confirm
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    if (-not [string]::IsNullOrWhiteSpace($env:SFL_CONFIG_PATH)) {
        $ConfigPath = $env:SFL_CONFIG_PATH
    } else {
        $ConfigPath = Join-Path $env:APPDATA "SmartFactoryLogger\config.ini"
    }
}
$ConfigPath = [System.IO.Path]::GetFullPath($ConfigPath)
$backend = $BackendBaseUrl.TrimEnd("/")

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
        }
    }
    $candidates.Add((Join-Path $env:APPDATA "SmartFactoryLogger\logs\test_data"))
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
    param([string[]]$Directories)
    $found = New-Object "System.Collections.Generic.List[object]"
    foreach ($directory in $Directories) {
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
            continue
        }
        Get-ChildItem -LiteralPath $directory -Filter "Factory_Integrated_Log_v2_*.metadata.json" `
            -File -ErrorAction SilentlyContinue | ForEach-Object { $found.Add($_) }
    }
    return $found | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function Read-TextFilePreservingEncoding {
    param([string]$Path)
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $encoding = $null
    $preambleLength = 0
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $encoding = New-Object System.Text.UTF8Encoding($true)
        $preambleLength = 3
    } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        $encoding = New-Object System.Text.UnicodeEncoding($false, $true)
        $preambleLength = 2
    } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
        $encoding = New-Object System.Text.UnicodeEncoding($true, $true)
        $preambleLength = 2
    } else {
        try {
            $strictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)
            $null = $strictUtf8.GetString($bytes)
            $encoding = New-Object System.Text.UTF8Encoding($false)
        } catch [System.Text.DecoderFallbackException] {
            $encoding = [System.Text.Encoding]::GetEncoding(949)
        }
    }
    $text = $encoding.GetString($bytes, $preambleLength, $bytes.Length - $preambleLength)
    return [pscustomobject]@{
        Text = $text
        Encoding = $encoding
    }
}

function Set-IniSectionValues {
    param(
        [string]$Text,
        [string]$Section,
        [System.Collections.IDictionary]$Values
    )
    $newline = if ($Text.Contains("`r`n")) { "`r`n" } elseif ($Text.Contains("`n")) { "`n" } else { "`r`n" }
    $endsWithNewline = $Text.EndsWith("`r`n") -or $Text.EndsWith("`n") -or $Text.EndsWith("`r")
    $lines = [System.Collections.Generic.List[string]]::new()
    [regex]::Split($Text, "`r`n|`n|`r") | ForEach-Object { [void]$lines.Add($_) }
    if ($endsWithNewline -and $lines.Count -gt 0 -and $lines[$lines.Count - 1] -eq "") {
        $lines.RemoveAt($lines.Count - 1)
    }

    $sectionIndexes = @()
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index].Trim() -match "^\[(.+)\]$" -and $Matches[1] -ieq $Section) {
            $sectionIndexes += $index
        }
    }
    if ($sectionIndexes.Count -ne 1) {
        throw "config.ini must contain exactly one [$Section] section; found $($sectionIndexes.Count)."
    }

    $sectionStart = [int]$sectionIndexes[0]
    $sectionEnd = $lines.Count
    for ($index = $sectionStart + 1; $index -lt $lines.Count; $index++) {
        if ($lines[$index].Trim() -match "^\[.+\]$") {
            $sectionEnd = $index
            break
        }
    }

    foreach ($entry in $Values.GetEnumerator()) {
        $key = [string]$entry.Key
        $value = [string]$entry.Value
        $keyMatchIndexes = @()
        for ($index = $sectionStart + 1; $index -lt $sectionEnd; $index++) {
            if ($lines[$index] -match "^\s*([^#;][^=]*?)\s*=.*$" -and $Matches[1].Trim() -ieq $key) {
                $keyMatchIndexes += $index
            }
        }
        if ($keyMatchIndexes.Count -gt 1) {
            throw "config.ini contains duplicate [$Section] $key entries. Resolve them manually first."
        }
        $replacement = "$key = $value"
        if ($keyMatchIndexes.Count -eq 1) {
            $lines[[int]$keyMatchIndexes[0]] = $replacement
        } else {
            $lines.Insert($sectionEnd, $replacement)
            $sectionEnd++
        }
    }
    $result = [string]::Join($newline, $lines)
    if ($endsWithNewline) {
        $result += $newline
    }
    return $result
}

Write-Host ""
Write-Host "SPOT Temperature v2.5 config attestation" -ForegroundColor Cyan
Write-Host "This tool updates only the four [SPOT] attestation fields after validation."
Write-Host ""

$backendRunning = $false
try {
    $null = Invoke-RestMethod -Uri "$backend/health" -Method Get -TimeoutSec 3
    $backendRunning = $true
} catch {
    $backendRunning = $false
}
if ($backendRunning) {
    throw "SmartFactoryLogger is still running. Close it normally, wait until it is fully closed, then retry."
}
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw "config.ini was not found: $ConfigPath"
}

$metadataFile = $null
if (-not [string]::IsNullOrWhiteSpace($MetadataPath)) {
    $resolvedMetadataPath = [System.IO.Path]::GetFullPath($MetadataPath)
    if (-not (Test-Path -LiteralPath $resolvedMetadataPath -PathType Leaf)) {
        throw "Metadata file was not found: $resolvedMetadataPath"
    }
    $metadataFile = Get-Item -LiteralPath $resolvedMetadataPath
} else {
    $directories = Get-LogDirectoryCandidates -ExplicitLogPath $LogPath -SettingsPath $ConfigPath
    $metadataFile = Find-LatestMetadata -Directories $directories
}
if ($null -eq $metadataFile) {
    throw "No Factory_Integrated_Log_v2_*.metadata.json file was found. Run the v2.5 app once and close it normally first."
}

$metadata = Get-Content -LiteralPath $metadataFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
$schema = Get-ObjectProperty $metadata "schema_metadata"
$snapshot = Get-ObjectProperty $metadata "spot_configuration_snapshot"
if ([string](Get-ObjectProperty $schema "active_schema_version" "") -ne "2.5.0") {
    throw "Latest metadata is not schema 2.5.0: $($metadataFile.Name)"
}
if (-not (Convert-ToBoolean (Get-ObjectProperty $schema "csv_v2_temperature_hardening_enabled" $false))) {
    throw "Latest metadata does not have temperature hardening enabled."
}
$fingerprint = [string](Get-ObjectProperty $snapshot "spot_config_fingerprint_sha256" "")
if ($fingerprint -notmatch "^[0-9a-f]{64}$") {
    throw "Latest metadata does not contain a valid SPOT config fingerprint."
}
$buildCommit = [string](Get-ObjectProperty $snapshot "build_git_commit" "")
if ($buildCommit -notmatch "^[0-9a-f]{40}$") {
    throw "Latest metadata does not contain a valid packaged build commit."
}
$driftDetected = Convert-ToBoolean (Get-ObjectProperty $snapshot "config_drift_detected" $false)
$driftFields = @(
    Get-ObjectProperty $snapshot "config_drift_fields" @() |
        ForEach-Object { [string]$_ }
)
$attestationStatus = [string](Get-ObjectProperty $snapshot "config_attestation_status" "")
if ($driftDetected) {
    $blockingDriftFields = @(
        $driftFields | Where-Object { $_ -ne "spot_config_fingerprint_sha256" }
    )
    $isFingerprintOnlyReattestation = (
        $driftFields.Count -eq 1 -and
        $driftFields[0] -eq "spot_config_fingerprint_sha256" -and
        $attestationStatus -eq "fingerprint_mismatch"
    )
    if (-not $isFingerprintOnlyReattestation -or $blockingDriftFields.Count -gt 0) {
        $driftSummary = if ($driftFields.Count -gt 0) { $driftFields -join ", " } else { "unknown" }
        throw "Latest metadata reports blocking config drift: $driftSummary"
    }
    Write-Host "[INFO] Build/config fingerprint changed; explicit operator re-attestation is allowed." -ForegroundColor Yellow
} elseif ($driftFields.Count -gt 0) {
    throw "Latest metadata has inconsistent config drift fields."
}
$readbackStatus = [string](Get-ObjectProperty $snapshot "device_config_readback_status" "")
if ($readbackStatus -notin @("matched", "not_supported")) {
    throw "Device readback status does not allow attestation: $readbackStatus"
}
if (-not (Convert-ToBoolean (Get-ObjectProperty $snapshot "low_signal_comparator_configured_verified" $false))) {
    throw "low_signal_comparator_verified was not configured true before this metadata was created."
}

if ([string]::IsNullOrWhiteSpace($OperatorId)) {
    $OperatorId = Read-Host "Operator ID (letters, numbers, dot, underscore, hyphen)"
}
$OperatorId = $OperatorId.Trim()
if ($OperatorId -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$") {
    throw "Invalid operator ID. Use only letters, numbers, dot, underscore, or hyphen."
}

Write-Host "Metadata: $($metadataFile.FullName)"
Write-Host "Build commit: $buildCommit"
Write-Host "SPOT model: $([string](Get-ObjectProperty $snapshot 'spot_model_info' 'unknown'))"
Write-Host "SPOT app mode: $([string](Get-ObjectProperty $snapshot 'spot_app_mode' 'unknown'))"
Write-Host "Low Signal alarm enabled: $([string](Get-ObjectProperty $snapshot 'low_signal_alarm_enabled' 'unknown'))"
Write-Host "Low Signal threshold: $([string](Get-ObjectProperty $snapshot 'low_signal_threshold_pc' 'unknown')) %"
Write-Host "Low Signal comparator: $([string](Get-ObjectProperty $snapshot 'low_signal_comparator' 'unknown'))"
Write-Host "Fingerprint: $fingerprint"
Write-Host ""
if (-not $Confirm) {
    $answer = Read-Host "Type CONFIRM to attest that these settings match the inspected SPOT device"
    if ($answer -cne "CONFIRM") {
        throw "Attestation cancelled. config.ini was not changed."
    }
}

$verifiedAt = [DateTime]::UtcNow.ToString("o")
$attestationValues = [ordered]@{
    config_operator_verified = "true"
    config_verified_at = $verifiedAt
    config_verified_by = $OperatorId
    config_verified_fingerprint_sha256 = $fingerprint
}
$configFile = Read-TextFilePreservingEncoding -Path $ConfigPath
$updatedText = Set-IniSectionValues -Text $configFile.Text -Section "SPOT" -Values $attestationValues
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = "$ConfigPath.backup-v25-attestation-$stamp"
$tempPath = "$ConfigPath.v25-attestation.tmp"
Copy-Item -LiteralPath $ConfigPath -Destination $backupPath -ErrorAction Stop
try {
    [System.IO.File]::WriteAllText($tempPath, $updatedText, $configFile.Encoding)
    Move-Item -LiteralPath $tempPath -Destination $ConfigPath -Force
} catch {
    if (Test-Path -LiteralPath $tempPath) {
        Remove-Item -LiteralPath $tempPath -Force
    }
    Copy-Item -LiteralPath $backupPath -Destination $ConfigPath -Force
    throw
}

Write-Host ""
Write-Host "ATTESTATION APPLIED" -ForegroundColor Green
Write-Host "Config: $ConfigPath"
Write-Host "Backup: $backupPath"
Write-Host "Verified at: $verifiedAt"
Write-Host ""
Write-Host "Start SmartFactoryLogger, wait for the SPOT temperature, then run:"
Write-Host ".\qa_spot_temperature_v25.cmd" -ForegroundColor Cyan
