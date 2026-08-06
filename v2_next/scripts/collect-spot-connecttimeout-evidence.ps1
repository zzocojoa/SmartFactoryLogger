<#
.HISTORICAL_SCOPE
    Source for the 2026-07-21 15-minute runtime-error-root-cause-validation
    field kit. This is not the later commit-bound 120-minute trigger kit and
    must not be used as a current release promotion gate.
#>
[CmdletBinding()]
param(
    [ValidateRange(5, 60)]
    [int]$ObservationMinutes = 15,

    [string]$ApiBase = "http://127.0.0.1:8000",

    [string]$SpotIp = "",

    [string]$ConfigPath = "",

    [string]$EvidenceBase = "",

    [string]$CollectorPath = "",

    [switch]$PreflightOnly,

    [switch]$SelfTest
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Write-Stage {
    param([string]$Message)
    Write-Host ""
    Write-Host ("[STEP] {0}" -f $Message) -ForegroundColor Cyan
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
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

function Invoke-SelfTest {
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

        $rawRoot = Join-Path $tempRoot 'raw'
        New-Item -ItemType Directory -Path $rawRoot | Out-Null
        'evidence' | Set-Content -LiteralPath (Join-Path $rawRoot 'sample.txt') -Encoding ascii
        $hashPath = Join-Path $tempRoot 'hash.csv'
        New-RawHashManifest -RawRoot $rawRoot -OutputPath $hashPath
        $hashRow = Import-Csv -LiteralPath $hashPath -Encoding utf8
        if ($hashRow.relative_path -ne 'sample.txt' -or $hashRow.sha256 -notmatch '^[a-f0-9]{64}$') {
            throw 'Self-test failed: hash manifest.'
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

        Write-Output 'SELF_TEST_PASS'
    } finally {
        $resolvedTempRoot = [IO.Path]::GetFullPath($tempRoot)
        if (-not $resolvedTempRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Unsafe self-test cleanup path.'
        }
        Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force
    }
}

if ($SelfTest) {
    Invoke-SelfTest
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

Write-Stage 'Preflight safety checks'
if (-not (Test-IsAdministrator)) {
    throw 'Administrator PowerShell is required. Use the administrator CMD launcher.'
}
if (-not (Test-Path -LiteralPath $CollectorPath -PathType Leaf)) {
    throw 'collect_operational_observability.ps1 is missing from this folder.'
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
$runFailure = $null
$startedAt = Get-Date
$endedAt = $null
$etlPath = Join-Path $networkRoot 'spot_tcp.etl'
$pcapPath = Join-Path $networkRoot 'spot_tcp.pcapng'
$packetTextPath = Join-Path $networkRoot 'spot_tcp_brief.txt'
$directionProbeSeconds = 10
$directionProbeEtlPath = Join-Path $networkRoot 'pktmon_direction_probe.etl'
$directionProbeTextPath = Join-Path $networkRoot 'pktmon_direction_probe.txt'
$directionProbeStatus = 'not_started'
$directionProbeOutboundCount = 0
$directionProbeInboundCount = 0
$pingPath = Join-Path $networkRoot 'ping_spot.jsonl'
$nicBeforePath = Join-Path $networkRoot 'nic_before.csv'
$nicAfterPath = Join-Path $networkRoot 'nic_after.csv'

$timeline = [ordered]@{
    run_id = $runId
    started_at_kst = $startedAt.ToString('o')
    observation_minutes = $ObservationMinutes
    switch_log_instruction = 'Save server-side and SPOT-side switch port counters and link events for the same interval.'
}
$timeline | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $timelinePath -Encoding utf8

$scriptHash = Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256
$collectorHash = Get-FileHash -LiteralPath $CollectorPath -Algorithm SHA256
$manifest = [ordered]@{
    run_id = $runId
    started_at_kst = $startedAt.ToString('o')
    status = 'RUNNING'
    observation_minutes = $ObservationMinutes
    backend = 'localhost'
    spot_target = 'configured-target-redacted'
    app_restart_performed = $false
    settings_changed = $false
    error_queue_cleared = $false
    image_load_test_performed = $false
    collection_script_sha256 = $scriptHash.Hash.ToLowerInvariant()
    observability_collector_sha256 = $collectorHash.Hash.ToLowerInvariant()
    packet_direction_probe_seconds = $directionProbeSeconds
    packet_direction_preflight = $directionProbeStatus
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $rawManifestPath -Encoding utf8

Write-Stage 'Save switch start counters'
Write-Host ('Save RX/TX, error, discard, CRC, and link state for the server and SPOT switch ports. Start: {0}' -f $startedAt.ToString('yyyy-MM-dd HH:mm:ss K')) -ForegroundColor Yellow
Read-Host 'Press Enter after saving the switch start counters'

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

    Write-Stage 'Start SPOT TCP packet capture'
    Invoke-PktmonCommand -Arguments @(
        'start', '--capture', '--comp', 'nics', '--pkt-size', '128',
        '--file-name', $etlPath, '--file-size', '256', '--log-mode', 'circular'
    ) -LogPath (Join-Path $networkRoot 'pktmon_start.txt') | Out-Null
    $pktmonStarted = $true

    Write-Stage 'Start one-second ping logging'
    $pingJob = Start-Job -ArgumentList $SpotIp, $pingPath -ScriptBlock {
        param($Target, $OutputPath)
        while ($true) {
            $at = Get-Date
            $watch = [Diagnostics.Stopwatch]::StartNew()
            & ping.exe -n 1 -w 900 $Target *> $null
            $code = $LASTEXITCODE
            $watch.Stop()
            [ordered]@{
                at_kst = $at.ToString('o')
                success = ($code -eq 0)
                elapsed_ms = [math]::Round($watch.Elapsed.TotalMilliseconds, 1)
            } | ConvertTo-Json -Compress | Add-Content -LiteralPath $OutputPath -Encoding utf8
            $remaining = 1000 - [int]$watch.Elapsed.TotalMilliseconds
            if ($remaining -gt 0) {
                Start-Sleep -Milliseconds $remaining
            }
        }
    }

    Write-Stage ('Collect app, TCP, and ping evidence for {0} minutes' -f $ObservationMinutes)
    Write-Host 'Keep the normal screen unchanged. Do not add tabs, repeatedly refresh, or run image load tests.' -ForegroundColor Yellow
    Write-Host 'If an error appears, do not click it. Record the exact time.' -ForegroundColor Yellow
    $samples = $ObservationMinutes * 12
    & $CollectorPath `
        -ApiBase $ApiBase `
        -Samples $samples `
        -IntervalSec 5 `
        -TimeoutSec 3 `
        -OutputRoot $appRoot 2>&1 |
        Tee-Object -FilePath (Join-Path $appRoot 'collector_console.txt')
    Write-Host '[PROGRESS] Timed app, TCP, and ping collection is complete. Stopping capture safely.' -ForegroundColor Green
} catch {
    $runFailure = $_
} finally {
    $endedAt = Get-Date

    if ($null -ne $pingJob) {
        Stop-Job -Job $pingJob -ErrorAction SilentlyContinue
        Receive-Job -Job $pingJob -ErrorAction SilentlyContinue | Out-Null
        Remove-Job -Job $pingJob -Force -ErrorAction SilentlyContinue
    }

    if ($pktmonStarted) {
        Invoke-PktmonCommand -Arguments @('stop') `
            -LogPath (Join-Path $networkRoot 'pktmon_stop.txt') -AllowFailure | Out-Null
        $pktmonStarted = $false
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
}

Write-Stage 'Convert packets and collect events, logs, and hashes'
Write-Host '[PROGRESS] Finalization 1/4: convert packet capture files. Duration depends on capture size.' -ForegroundColor Cyan
if (Test-Path -LiteralPath $etlPath -PathType Leaf) {
    Invoke-PktmonCommand -Arguments @('etl2pcap', $etlPath, '--out', $pcapPath) `
        -LogPath (Join-Path $networkRoot 'pktmon_etl2pcap.txt') -AllowFailure | Out-Null
    Invoke-PktmonCommand -Arguments @('etl2txt', $etlPath, '--out', $packetTextPath, '--brief', '--timestamp') `
        -LogPath (Join-Path $networkRoot 'pktmon_etl2txt.txt') -AllowFailure | Out-Null
}

Write-Host '[PROGRESS] Finalization 2/4: calculate NIC deltas and collect Windows/application logs.' -ForegroundColor Cyan
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
Write-Host '[PROGRESS] Finalization 3/4: redact network identifiers and assemble sanitized evidence.' -ForegroundColor Cyan
if (Test-Path -LiteralPath $packetTextPath -PathType Leaf) {
    $packetText = Get-Content -LiteralPath $packetTextPath -Raw -Encoding utf8
    Protect-Text -Text $packetText -TargetIp $SpotIp -ServerIps $serverIps |
        Set-Content -LiteralPath (Join-Path $sanitizedRoot 'spot_tcp_brief_redacted.txt') -Encoding utf8
}
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
if ($null -ne $collectorSession) {
    $collectorSanitized = Join-Path $collectorSession.FullName 'sanitized'
    if (Test-Path -LiteralPath $collectorSanitized -PathType Container) {
        Copy-Item -LiteralPath $collectorSanitized -Destination (Join-Path $sanitizedRoot 'app_observability') `
            -Recurse -Force
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

$requiredEvidenceMissing = @()
if (-not (Test-Path -LiteralPath $etlPath -PathType Leaf)) {
    $requiredEvidenceMissing += 'packet-etl'
}
if (-not (Test-Path -LiteralPath $pcapPath -PathType Leaf)) {
    $requiredEvidenceMissing += 'packet-pcap'
}
if (-not (Test-Path -LiteralPath $packetTextPath -PathType Leaf)) {
    $requiredEvidenceMissing += 'packet-text'
}
if ($pingRows.Count -eq 0) {
    $requiredEvidenceMissing += 'ping-samples'
}
if ($null -eq $collectorSession) {
    $requiredEvidenceMissing += 'app-observability'
}
if ($directionProbeStatus -ne 'passed') {
    $requiredEvidenceMissing += 'packet-direction-preflight'
}
if ($null -eq $runFailure -and $requiredEvidenceMissing.Count -gt 0) {
    $runFailure = [System.InvalidOperationException]::new(
        ('Required evidence is missing: {0}' -f ($requiredEvidenceMissing -join ', '))
    )
}
$failureType = $null
if ($null -ne $runFailure) {
    if ($runFailure -is [System.Management.Automation.ErrorRecord]) {
        $failureType = $runFailure.Exception.GetType().Name
    } else {
        $failureType = $runFailure.GetType().Name
    }
}

$manifest.status = if ($null -eq $runFailure) { 'COLLECTED' } else { 'FAILED' }
$manifest['ended_at_kst'] = $endedAt.ToString('o')
$manifest['failure_type'] = $failureType
$manifest['pktmon_filter_cleanup'] = $filterCleanupStatus
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $rawManifestPath -Encoding utf8

$safeSummary = [ordered]@{
    run_id = $runId
    status = $manifest.status
    started_at_kst = $startedAt.ToString('o')
    ended_at_kst = $endedAt.ToString('o')
    observation_minutes_requested = $ObservationMinutes
    ping_samples = $pingRows.Count
    ping_successes = $pingSuccesses
    ping_failures = $pingFailures
    packet_etl_created = (Test-Path -LiteralPath $etlPath -PathType Leaf)
    packet_pcap_created = (Test-Path -LiteralPath $pcapPath -PathType Leaf)
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
    raw_private_location = 'Retained in the same run folder on the real server.'
}
$safeSummary | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $sanitizedRoot 'field_collection_summary.json') -Encoding utf8

@"
SPOT switch log drop location

Run start: $($startedAt.ToString('yyyy-MM-dd HH:mm:ss K'))
Run end: $($endedAt.ToString('yyyy-MM-dd HH:mm:ss K'))

Save the following evidence for the same interval in switch_logs_drop_here:
- Server-side and SPOT-side switch port identifiers
- Start and end RX/TX packet counters
- Start and end error, discard, drop, and CRC counters
- Link up/down, speed/duplex, STP, and VLAN events
- Device reboot or service events when available
"@ | Set-Content -LiteralPath (Join-Path $switchRoot 'switch_log_request.txt') -Encoding utf8

Write-Host '[PROGRESS] Finalization 4/4: calculate hashes and create the sanitized sharing ZIP.' -ForegroundColor Cyan
New-RawHashManifest -RawRoot $rawRoot -OutputPath (Join-Path $sanitizedRoot 'raw_file_sha256.csv')

$sanitizedZip = Join-Path $evidenceRoot ("{0}_sanitized_share.zip" -f $runId)
Compress-Archive -Path (Join-Path $sanitizedRoot '*') -DestinationPath $sanitizedZip -Force
$zipHash = Get-FileHash -LiteralPath $sanitizedZip -Algorithm SHA256
$zipHash.Hash.ToLowerInvariant() |
    Set-Content -LiteralPath (Join-Path $evidenceRoot 'sanitized_share_sha256.txt') -Encoding ascii
Write-Host '[PROGRESS] Finalization complete. Save the switch end counters when prompted.' -ForegroundColor Green

Write-Stage 'Save switch end counters'
Write-Host ('Save the switch end counters and link events now. End: {0}' -f $endedAt.ToString('yyyy-MM-dd HH:mm:ss K')) -ForegroundColor Yellow
Write-Host ('Private raw folder on the server: {0}' -f $rawRoot) -ForegroundColor Yellow
Write-Host ('Sanitized ZIP for sharing: {0}' -f $sanitizedZip) -ForegroundColor Green

if ($null -ne $runFailure) {
    throw ('Collection failed. The raw folder was retained. Error type: {0}' -f $failureType)
}

Write-Host '[DONE] Evidence collection completed. The application and settings were not changed.' -ForegroundColor Green
