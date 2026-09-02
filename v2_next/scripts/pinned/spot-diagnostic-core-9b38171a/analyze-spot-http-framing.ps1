[CmdletBinding()]
param(
    [string]$InputPath = "",

    [string]$EventsOutputPath = "",

    [string]$SummaryOutputPath = "",

    [DateTimeOffset]$CaptureStartedAt = [DateTimeOffset]::Now,

    [DateTimeOffset]$CaptureEndedAt = [DateTimeOffset]::MinValue,

    [DateTimeOffset]$AnalysisWindowStartedAt = [DateTimeOffset]::MinValue,

    [DateTimeOffset]$AnalysisWindowEndedAt = [DateTimeOffset]::MinValue,

    [string]$ClockCalibrationPath = "",

    [ValidateRange(0, [long]::MaxValue)]
    [long]$CaptureFileSizeBytes = 0,

    [ValidateRange(0, 4096)]
    [int]$CircularCaptureMaxFileSizeMB = 0,

    [ValidateRange(1, 65535)]
    [int]$ServerPort = 80,

    [switch]$SelfTest
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$script:MaximumHeaderBytes = 16 * 1024
$script:SequenceModulus = [int64]4294967296
$script:DuplicatePacketWindowMilliseconds = 10.0
$script:MaximumSortableTargetPacketCount = 1000000

function Get-BigEndianUInt16 {
    param(
        [byte[]]$Bytes,
        [int]$Offset
    )

    return ([int]$Bytes[$Offset] -shl 8) -bor [int]$Bytes[$Offset + 1]
}

function Get-BigEndianUInt32 {
    param(
        [byte[]]$Bytes,
        [int]$Offset
    )

    return [uint32](
        ([uint32]$Bytes[$Offset] -shl 24) -bor
        ([uint32]$Bytes[$Offset + 1] -shl 16) -bor
        ([uint32]$Bytes[$Offset + 2] -shl 8) -bor
        [uint32]$Bytes[$Offset + 3]
    )
}

function Get-EndianUInt16 {
    param(
        [byte[]]$Bytes,
        [int]$Offset,
        [bool]$LittleEndian
    )

    if ($LittleEndian) {
        return [int]$Bytes[$Offset] -bor ([int]$Bytes[$Offset + 1] -shl 8)
    }
    return Get-BigEndianUInt16 -Bytes $Bytes -Offset $Offset
}

function Get-EndianUInt32 {
    param(
        [byte[]]$Bytes,
        [int]$Offset,
        [bool]$LittleEndian
    )

    if ($LittleEndian) {
        return [uint32](
            [uint32]$Bytes[$Offset] -bor
            ([uint32]$Bytes[$Offset + 1] -shl 8) -bor
            ([uint32]$Bytes[$Offset + 2] -shl 16) -bor
            ([uint32]$Bytes[$Offset + 3] -shl 24)
        )
    }
    return Get-BigEndianUInt32 -Bytes $Bytes -Offset $Offset
}

function Read-ExactBytes {
    param(
        [IO.BinaryReader]$Reader,
        [int]$Count
    )

    $bytes = $Reader.ReadBytes($Count)
    if ($bytes.Length -ne $Count) {
        throw "Packet capture ended inside a pcapng block."
    }
    return [byte[]]$bytes
}

function Get-SequenceDelta {
    param(
        [uint32]$Sequence,
        [uint32]$BaseSequence
    )

    $delta = [int64]$Sequence - [int64]$BaseSequence
    if ($delta -lt -2147483648) {
        $delta += $script:SequenceModulus
    } elseif ($delta -gt 2147483647) {
        $delta -= $script:SequenceModulus
    }
    return $delta
}

function Get-RequestKind {
    param([byte[]]$Payload)

    if ($null -eq $Payload -or $Payload.Length -eq 0) {
        return "unknown"
    }
    $text = [Text.Encoding]::ASCII.GetString($Payload)
    if ($text -match '^GET\s+/image\.jpg(?:\?|\s)') {
        return "image"
    }
    if ($text -match '^GET\s+/output\?p=temperature(?:&|\s)') {
        return "temperature"
    }
    if ($text -match '^GET\s+/(?:control|scan\.cgi)(?:\?|\s)') {
        return "control"
    }
    if ($text -match '^GET\s+/output(?:\?|\s)') {
        return "diagnostic"
    }
    return "unknown"
}

function Get-PacketRecord {
    param(
        [byte[]]$Bytes,
        [int]$TargetServerPort
    )

    if ($null -eq $Bytes -or $Bytes.Length -lt 54) {
        return $null
    }

    $networkOffset = 14
    $etherType = Get-BigEndianUInt16 -Bytes $Bytes -Offset 12
    $vlanDepth = 0
    while ($etherType -in @(0x8100, 0x88A8) -and $vlanDepth -lt 2) {
        if ($Bytes.Length -lt ($networkOffset + 4)) {
            return $null
        }
        $etherType = Get-BigEndianUInt16 -Bytes $Bytes -Offset ($networkOffset + 2)
        $networkOffset += 4
        $vlanDepth += 1
    }
    if ($etherType -ne 0x0800 -or $Bytes.Length -lt ($networkOffset + 20)) {
        return $null
    }

    $version = [int]($Bytes[$networkOffset] -shr 4)
    $ipHeaderLength = [int](($Bytes[$networkOffset] -band 0x0F) * 4)
    if ($version -ne 4 -or $ipHeaderLength -lt 20 -or
        $Bytes.Length -lt ($networkOffset + $ipHeaderLength)) {
        return $null
    }
    if ($Bytes[$networkOffset + 9] -ne 6) {
        return $null
    }
    $fragmentField = Get-BigEndianUInt16 -Bytes $Bytes -Offset ($networkOffset + 6)
    if (($fragmentField -band 0x1FFF) -ne 0) {
        return $null
    }

    $totalLength = Get-BigEndianUInt16 -Bytes $Bytes -Offset ($networkOffset + 2)
    $tcpOffset = $networkOffset + $ipHeaderLength
    if ($Bytes.Length -lt ($tcpOffset + 20)) {
        return $null
    }
    $sourcePort = Get-BigEndianUInt16 -Bytes $Bytes -Offset $tcpOffset
    $destinationPort = Get-BigEndianUInt16 -Bytes $Bytes -Offset ($tcpOffset + 2)
    if ($sourcePort -ne $TargetServerPort -and $destinationPort -ne $TargetServerPort) {
        return $null
    }

    $tcpHeaderLength = [int](($Bytes[$tcpOffset + 12] -shr 4) * 4)
    if ($tcpHeaderLength -lt 20 -or $Bytes.Length -lt ($tcpOffset + $tcpHeaderLength)) {
        return $null
    }
    $payloadOffset = $tcpOffset + $tcpHeaderLength
    $wirePayloadLength = [Math]::Max(0, $totalLength - $ipHeaderLength - $tcpHeaderLength)
    $capturedPayloadLength = [Math]::Min(
        $wirePayloadLength,
        [Math]::Max(0, $Bytes.Length - $payloadOffset)
    )
    $payload = [byte[]]@()
    if ($capturedPayloadLength -gt 0) {
        $payload = [byte[]]$Bytes[$payloadOffset..($payloadOffset + $capturedPayloadLength - 1)]
    }

    $flags = [int]$Bytes[$tcpOffset + 13]
    $sourceAddress = [BitConverter]::ToString(
        [byte[]]$Bytes[($networkOffset + 12)..($networkOffset + 15)]
    )
    $destinationAddress = [BitConverter]::ToString(
        [byte[]]$Bytes[($networkOffset + 16)..($networkOffset + 19)]
    )
    $isInbound = $sourcePort -eq $TargetServerPort
    $clientAddress = if ($isInbound) { $destinationAddress } else { $sourceAddress }
    $clientPort = if ($isInbound) { $destinationPort } else { $sourcePort }

    return [pscustomobject]@{
        FlowKey = "{0}:{1}" -f $clientAddress, $clientPort
        IsInbound = $isInbound
        Sequence = Get-BigEndianUInt32 -Bytes $Bytes -Offset ($tcpOffset + 4)
        Syn = (($flags -band 0x02) -ne 0)
        Ack = (($flags -band 0x10) -ne 0)
        Fin = (($flags -band 0x01) -ne 0)
        Rst = (($flags -band 0x04) -ne 0)
        WirePayloadLength = $wirePayloadLength
        CapturedPayload = $payload
        CapturedPayloadTruncated = ($capturedPayloadLength -lt $wirePayloadLength)
    }
}

function New-FlowState {
    param([string]$FlowKey)

    return [pscustomobject]@{
        FlowKey = $FlowKey
        InitialSynSequence = $null
        FirstSynAt = $null
        SynCount = 0
        SynAckCount = 0
        HandshakeAckObserved = $false
        RequestKind = "unknown"
        RequestPayloadObserved = $false
        ResponseBaseSequence = $null
        ResponseStartedAt = $null
        ResponseCaptureOrdinal = 0L
        PacketOrderSensitiveResponseObserved = $false
        PacketOrderSensitiveResponseAt = $null
        PacketOrderSensitiveCaptureOrdinalDelta = $null
        PacketOrderSensitiveTimestampLeadMilliseconds = $null
        LastObservedAt = $null
        ServerCloseKind = "not_observed"
        ClientCloseKind = "not_observed"
        Intervals = [Collections.Generic.List[object]]::new()
        CapturedSegments = [Collections.Generic.Dictionary[int64, byte[]]]::new()
    }
}

function Set-FlowLastObservedAt {
    param(
        [object]$Flow,
        [string]$ObservedAt
    )

    $candidate = [DateTimeOffset]::Parse(
        $ObservedAt,
        [Globalization.CultureInfo]::InvariantCulture
    )
    if ($null -eq $Flow.LastObservedAt) {
        $Flow.LastObservedAt = $candidate.ToString("o")
        return
    }
    $current = [DateTimeOffset]::Parse(
        [string]$Flow.LastObservedAt,
        [Globalization.CultureInfo]::InvariantCulture
    )
    if ($candidate -gt $current) {
        $Flow.LastObservedAt = $candidate.ToString("o")
    }
}

function Set-CloseKind {
    param(
        [object]$Flow,
        [bool]$FromServer,
        [bool]$Fin,
        [bool]$Rst
    )

    if (-not $Fin -and -not $Rst) {
        return
    }
    $property = if ($FromServer) { "ServerCloseKind" } else { "ClientCloseKind" }
    if ($Rst) {
        $Flow.$property = "reset"
    } elseif ($Flow.$property -ne "reset") {
        $Flow.$property = "fin"
    }
}

function Get-HeaderEvidence {
    param([object]$Flow)

    $buffer = [Collections.Generic.List[byte]]::new()
    $nextOffset = [int64]0
    foreach ($entry in @($Flow.CapturedSegments.GetEnumerator() | Sort-Object Key)) {
        $start = [int64]$entry.Key
        $segment = [byte[]]$entry.Value
        if ($start -gt $nextOffset) {
            break
        }
        $skip = [int][Math]::Max(0, $nextOffset - $start)
        for ($index = $skip; $index -lt $segment.Length; $index += 1) {
            if ($buffer.Count -ge $script:MaximumHeaderBytes) {
                break
            }
            $buffer.Add($segment[$index])
            $nextOffset += 1
        }
        if ($buffer.Count -ge $script:MaximumHeaderBytes) {
            break
        }
    }

    $headerEnd = -1
    for ($index = 0; $index -le ($buffer.Count - 4); $index += 1) {
        if ($buffer[$index] -eq 13 -and $buffer[$index + 1] -eq 10 -and
            $buffer[$index + 2] -eq 13 -and $buffer[$index + 3] -eq 10) {
            $headerEnd = $index + 4
            break
        }
    }
    if ($headerEnd -lt 0) {
        return [pscustomobject]@{
            HeaderComplete = $false
            HeaderLength = $null
            HttpVersion = "unknown"
            StatusCode = $null
            ContentLengthPresent = $null
            DeclaredContentLength = $null
            TransferEncoding = "unknown"
            Framing = "unknown"
            CapturedContiguousBytes = [byte[]]$buffer.ToArray()
        }
    }

    $headerBytes = [byte[]]$buffer.GetRange(0, $headerEnd).ToArray()
    $headerText = [Text.Encoding]::ASCII.GetString($headerBytes)
    $lines = @($headerText -split "`r`n")
    $httpVersion = "unknown"
    $statusCode = $null
    if ($lines.Count -gt 0 -and $lines[0] -match '^HTTP/(?<version>1\.[01])\s+(?<status>\d{3})(?:\s|$)') {
        $httpVersion = "HTTP/{0}" -f $Matches.version
        $statusCode = [int]$Matches.status
    }

    $contentLengthValues = [Collections.Generic.List[string]]::new()
    $transferEncodingValues = [Collections.Generic.List[string]]::new()
    foreach ($line in $lines | Select-Object -Skip 1) {
        $separatorIndex = $line.IndexOf(':')
        if ($separatorIndex -lt 1) {
            continue
        }
        $name = $line.Substring(0, $separatorIndex)
        $value = $line.Substring($separatorIndex + 1)
        if ($name.Trim() -ieq 'Content-Length') {
            $contentLengthValues.Add($value.Trim())
        } elseif ($name.Trim() -ieq 'Transfer-Encoding') {
            $transferEncodingValues.Add($value.Trim())
        }
    }

    $declaredContentLength = $null
    if ($contentLengthValues.Count -gt 0) {
        $parsedLength = [int64]0
        $allSame = @($contentLengthValues | Select-Object -Unique).Count -eq 1
        if ($allSame -and [int64]::TryParse($contentLengthValues[0], [ref]$parsedLength) -and
            $parsedLength -ge 0) {
            $declaredContentLength = $parsedLength
        }
    }
    $transferEncoding = "none"
    if ($transferEncodingValues.Count -gt 0) {
        $combined = ($transferEncodingValues -join ',').ToLowerInvariant()
        $transferEncoding = if ($combined -match '(^|,)\s*chunked\s*(,|$)') { "chunked" } else { "other" }
    }
    $framing = if ($transferEncoding -eq "chunked") {
        "chunked"
    } elseif ($contentLengthValues.Count -gt 0) {
        "content_length"
    } elseif ($httpVersion -in @("HTTP/1.0", "HTTP/1.1")) {
        "close_delimited"
    } else {
        "unknown"
    }

    return [pscustomobject]@{
        HeaderComplete = $true
        HeaderLength = $headerEnd
        HttpVersion = $httpVersion
        StatusCode = $statusCode
        ContentLengthPresent = ($contentLengthValues.Count -gt 0)
        DeclaredContentLength = $declaredContentLength
        TransferEncoding = $transferEncoding
        Framing = $framing
        CapturedContiguousBytes = [byte[]]$buffer.ToArray()
    }
}

function Get-ContiguousWireEnd {
    param([object]$Flow)

    $end = [int64]0
    foreach ($interval in @($Flow.Intervals | Sort-Object Start, End)) {
        if ([int64]$interval.Start -gt $end) {
            break
        }
        if ([int64]$interval.End -gt $end) {
            $end = [int64]$interval.End
        }
    }
    return $end
}

function Test-CompleteChunkedBody {
    param([byte[]]$Body)

    $offset = 0
    while ($offset -lt $Body.Length) {
        $lineEnd = -1
        for ($index = $offset; $index -lt ($Body.Length - 1); $index += 1) {
            if ($Body[$index] -eq 13 -and $Body[$index + 1] -eq 10) {
                $lineEnd = $index
                break
            }
        }
        if ($lineEnd -lt 0) {
            return $false
        }
        $sizeText = [Text.Encoding]::ASCII.GetString($Body, $offset, $lineEnd - $offset).Split(';')[0]
        $size = [int64]0
        if (-not [int64]::TryParse(
            $sizeText,
            [Globalization.NumberStyles]::HexNumber,
            [Globalization.CultureInfo]::InvariantCulture,
            [ref]$size
        )) {
            return $false
        }
        $offset = $lineEnd + 2
        if ($size -eq 0) {
            return ($offset + 2 -le $Body.Length -and
                $Body[$offset] -eq 13 -and $Body[$offset + 1] -eq 10)
        }
        if ($size -gt [int]::MaxValue -or $offset + [int]$size + 2 -gt $Body.Length) {
            return $false
        }
        $offset += [int]$size
        if ($Body[$offset] -ne 13 -or $Body[$offset + 1] -ne 10) {
            return $false
        }
        $offset += 2
    }
    return $false
}

function Get-BodyCompletion {
    param(
        [object]$Flow,
        [object]$Header
    )

    if (-not $Header.HeaderComplete) {
        return [pscustomobject]@{ Complete = $null; Basis = "unknown" }
    }
    $contiguousWireEnd = Get-ContiguousWireEnd -Flow $Flow
    if ($Header.Framing -eq "content_length") {
        if ($null -eq $Header.DeclaredContentLength) {
            return [pscustomobject]@{ Complete = $null; Basis = "invalid_content_length" }
        }
        $requiredEnd = [int64]$Header.HeaderLength + [int64]$Header.DeclaredContentLength
        if ($contiguousWireEnd -ge $requiredEnd) {
            return [pscustomobject]@{ Complete = $true; Basis = "content_length" }
        }
        if ($Flow.ServerCloseKind -in @("fin", "reset")) {
            return [pscustomobject]@{ Complete = $false; Basis = "content_length" }
        }
        return [pscustomobject]@{ Complete = $null; Basis = "content_length" }
    }
    if ($Header.Framing -eq "chunked") {
        $captured = [byte[]]$Header.CapturedContiguousBytes
        if ($captured.Length -gt [int]$Header.HeaderLength) {
            $body = [byte[]]$captured[[int]$Header.HeaderLength..($captured.Length - 1)]
            if (Test-CompleteChunkedBody -Body $body) {
                return [pscustomobject]@{ Complete = $true; Basis = "chunked_terminator" }
            }
        }
        return [pscustomobject]@{ Complete = $null; Basis = "chunked_capture_incomplete" }
    }
    if ($Header.Framing -eq "close_delimited") {
        if ($Flow.ServerCloseKind -eq "fin") {
            return [pscustomobject]@{ Complete = $true; Basis = "peer_fin" }
        }
        if ($Flow.ServerCloseKind -eq "reset") {
            return [pscustomobject]@{ Complete = $false; Basis = "peer_reset" }
        }
        return [pscustomobject]@{ Complete = $null; Basis = "peer_close_not_observed" }
    }
    return [pscustomobject]@{ Complete = $null; Basis = "unknown" }
}

function Add-Count {
    param(
        [hashtable]$Table,
        [string]$Key
    )

    if (-not $Table.ContainsKey($Key)) {
        $Table[$Key] = 0
    }
    $Table[$Key] = [int]$Table[$Key] + 1
}

function Get-NearestRankPercentile {
    param(
        [double[]]$Values,
        [ValidateRange(0, 1)]
        [double]$Percentile
    )

    if ($null -eq $Values -or $Values.Count -eq 0) {
        return $null
    }
    $sorted = @($Values | Sort-Object)
    $index = [Math]::Ceiling($Percentile * $sorted.Count) - 1
    $index = [Math]::Max(0, [Math]::Min($sorted.Count - 1, $index))
    return [Math]::Round([double]$sorted[$index], 3)
}

function Get-IntervalSummary {
    param([double[]]$Values)

    $intervals = @($Values | ForEach-Object { [double]$_ })
    return [ordered]@{
        observed_count = $intervals.Count
        interval_ms_min = if ($intervals.Count -eq 0) {
            $null
        } else {
            [Math]::Round(
                [double](($intervals | Measure-Object -Minimum).Minimum),
                3
            )
        }
        interval_ms_p05 = Get-NearestRankPercentile -Values $intervals -Percentile 0.05
        interval_ms_p50 = Get-NearestRankPercentile -Values $intervals -Percentile 0.50
        interval_ms_p95 = Get-NearestRankPercentile -Values $intervals -Percentile 0.95
        interval_ms_max = if ($intervals.Count -eq 0) {
            $null
        } else {
            [Math]::Round(
                [double](($intervals | Measure-Object -Maximum).Maximum),
                3
            )
        }
        under_1000_ms_count = @($intervals | Where-Object { $_ -lt 1000 }).Count
        under_5000_ms_count = @($intervals | Where-Object { $_ -lt 5000 }).Count
        under_60000_ms_count = @($intervals | Where-Object { $_ -lt 60000 }).Count
        under_75000_ms_count = @($intervals | Where-Object { $_ -lt 75000 }).Count
    }
}

function Read-ClockCalibration {
    param([string]$Path)

    $result = [ordered]@{
        status = "unavailable"
        anchors = @()
        frequency = $null
        wall_elapsed_ms = $null
        monotonic_elapsed_ms = $null
        wall_monotonic_drift_ms = $null
        timestamp_regression_count = 0
    }
    if ([string]::IsNullOrWhiteSpace($Path) -or
        -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $result
    }

    $anchors = [Collections.Generic.List[object]]::new()
    foreach ($line in [IO.File]::ReadLines($Path)) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        $row = $line | ConvertFrom-Json
        if ($row.schema_version -ne "spot-canary-clock-anchor-v1") {
            throw "Clock calibration schema is invalid."
        }
        $frequency = [double]$row.monotonic_frequency
        if ($frequency -le 0) {
            throw "Clock calibration frequency is invalid."
        }
        if ($null -ne $result.frequency -and [double]$result.frequency -ne $frequency) {
            throw "Clock calibration frequency changed during observation."
        }
        $result.frequency = $frequency
        $anchors.Add([pscustomobject]@{
            Wall = [DateTimeOffset]::Parse(
                [string]$row.wall_clock_at,
                [Globalization.CultureInfo]::InvariantCulture
            )
            MonotonicMilliseconds = (
                [double]$row.monotonic_ticks * 1000.0 / $frequency
            )
        })
    }
    if ($anchors.Count -lt 2) {
        $result.status = "insufficient-anchors"
        $result.anchors = @($anchors)
        return $result
    }

    for ($index = 1; $index -lt $anchors.Count; $index += 1) {
        if ($anchors[$index].Wall -le $anchors[$index - 1].Wall -or
            $anchors[$index].MonotonicMilliseconds -le
                $anchors[$index - 1].MonotonicMilliseconds) {
            $result.timestamp_regression_count =
                [int]$result.timestamp_regression_count + 1
        }
    }
    $first = $anchors[0]
    $last = $anchors[$anchors.Count - 1]
    $wallElapsed = ($last.Wall - $first.Wall).TotalMilliseconds
    $monotonicElapsed = (
        $last.MonotonicMilliseconds - $first.MonotonicMilliseconds
    )
    $result.anchors = @($anchors)
    $result.wall_elapsed_ms = [Math]::Round($wallElapsed, 3)
    $result.monotonic_elapsed_ms = [Math]::Round($monotonicElapsed, 3)
    $result.wall_monotonic_drift_ms = [Math]::Round(
        $wallElapsed - $monotonicElapsed,
        3
    )
    $result.status = if ([int]$result.timestamp_regression_count -eq 0) {
        "complete"
    } else {
        "invalid-regression"
    }
    return $result
}

function Convert-WallTimeToMonotonicMilliseconds {
    param(
        [DateTimeOffset]$WallTime,
        [object]$Calibration
    )

    if ($null -eq $Calibration -or $Calibration.status -ne "complete") {
        return $null
    }
    $anchors = @($Calibration.anchors)
    $left = $anchors[0]
    $right = $anchors[1]
    if ($WallTime -ge $anchors[$anchors.Count - 1].Wall) {
        $left = $anchors[$anchors.Count - 2]
        $right = $anchors[$anchors.Count - 1]
    } else {
        for ($index = 1; $index -lt $anchors.Count; $index += 1) {
            if ($WallTime -le $anchors[$index].Wall) {
                $left = $anchors[$index - 1]
                $right = $anchors[$index]
                break
            }
        }
    }
    $wallSpan = ($right.Wall - $left.Wall).TotalMilliseconds
    if ($wallSpan -le 0) {
        return $null
    }
    $monotonicSpan = (
        $right.MonotonicMilliseconds - $left.MonotonicMilliseconds
    )
    return [double](
        $left.MonotonicMilliseconds +
        (($WallTime - $left.Wall).TotalMilliseconds * $monotonicSpan / $wallSpan)
    )
}

function Initialize-MeasurementContext {
    param(
        [hashtable]$Context,
        [DateTimeOffset]$WindowStartedAt,
        [DateTimeOffset]$WindowEndedAt,
        [string]$CalibrationPath
    )

    $Context.AnalysisWindowStartedAt = $WindowStartedAt
    $Context.AnalysisWindowEndedAt = $WindowEndedAt
    $Context.AnalysisExcludedBeforeCount = 0
    $Context.AnalysisExcludedAfterCount = 0
    $Context.InterfacePacketCounts = @{}
    $Context.InterfaceLastPacketAt = @{}
    $Context.InterfaceTimestampRegressionCount = 0
    $Context.InterfaceTimestampRegressionMaxMilliseconds = 0.0
    $Context.InitialSynCaptureLastAtByFlowKey = @{}
    $Context.InitialSynTimestampRegressionCount = 0
    $Context.InitialSynTimestampRegressionMaxMilliseconds = 0.0
    $Context.PacketOrderingPolicy = "capture-order"
    $Context.TimestampOrderCorrectionApplied = $false
    $Context.SortableTargetPacketCount = 0
    $Context.DuplicatePacketCount = 0
    $Context.DuplicateInitialSynCount = 0
    $Context.RecentPacketFingerprint = @{}
    $Context.ClientToServerRstCount = 0
    $Context.ServerToClientRstCount = 0
    $Context.LastOriginalInitialSynAtByFlowKey = @{}
    $Context.SameFourTupleOriginalIntervalsMs =
        [Collections.Generic.List[double]]::new()
    $Context.LastCalibratedInitialSynMsByFlowKey = @{}
    $Context.SameFourTupleCalibratedIntervalsMs =
        [Collections.Generic.List[double]]::new()
    $Context.ClockCalibration = Read-ClockCalibration -Path $CalibrationPath
}

function Register-CaptureOrderMeasurement {
    param(
        [hashtable]$Context,
        [object]$Packet,
        [DateTimeOffset]$Observed,
        [int]$InterfaceId
    )

    $interfaceKey = [string]$InterfaceId
    if (-not $Context.InterfacePacketCounts.ContainsKey($interfaceKey)) {
        $Context.InterfacePacketCounts[$interfaceKey] = 0
    }
    $Context.InterfacePacketCounts[$interfaceKey] =
        [int64]$Context.InterfacePacketCounts[$interfaceKey] + 1
    if ($Context.InterfaceLastPacketAt.ContainsKey($interfaceKey)) {
        $previous = [DateTimeOffset]$Context.InterfaceLastPacketAt[$interfaceKey]
        if ($Observed -lt $previous) {
            $regressionMs = ($previous - $Observed).TotalMilliseconds
            $Context.InterfaceTimestampRegressionCount =
                [int64]$Context.InterfaceTimestampRegressionCount + 1
            $Context.InterfaceTimestampRegressionMaxMilliseconds = [Math]::Max(
                [double]$Context.InterfaceTimestampRegressionMaxMilliseconds,
                [double]$regressionMs
            )
        }
    }
    $Context.InterfaceLastPacketAt[$interfaceKey] = $Observed

    $initialSyn = -not $Packet.IsInbound -and $Packet.Syn -and -not $Packet.Ack
    if (-not $initialSyn) {
        return
    }

    Register-OriginalInitialSyn `
        -Context $Context `
        -FlowKey $Packet.FlowKey `
        -Observed $Observed
    if ($Context.InitialSynCaptureLastAtByFlowKey.ContainsKey($Packet.FlowKey)) {
        $previousSyn = [DateTimeOffset](
            $Context.InitialSynCaptureLastAtByFlowKey[$Packet.FlowKey]
        )
        if ($Observed -lt $previousSyn) {
            $regressionMs = ($previousSyn - $Observed).TotalMilliseconds
            $Context.InitialSynTimestampRegressionCount =
                [int64]$Context.InitialSynTimestampRegressionCount + 1
            $Context.InitialSynTimestampRegressionMaxMilliseconds = [Math]::Max(
                [double]$Context.InitialSynTimestampRegressionMaxMilliseconds,
                [double]$regressionMs
            )
        }
    }
    $Context.InitialSynCaptureLastAtByFlowKey[$Packet.FlowKey] = $Observed
}

function Register-OriginalInitialSyn {
    param(
        [hashtable]$Context,
        [string]$FlowKey,
        [DateTimeOffset]$Observed
    )

    if ($Context.LastOriginalInitialSynAtByFlowKey.ContainsKey($FlowKey)) {
        $previous = [DateTimeOffset]$Context.LastOriginalInitialSynAtByFlowKey[$FlowKey]
        $intervalMs = ($Observed - $previous).TotalMilliseconds
        if ($intervalMs -ge 0) {
            $Context.SameFourTupleOriginalIntervalsMs.Add([double]$intervalMs)
        }
    }
    if (-not $Context.LastOriginalInitialSynAtByFlowKey.ContainsKey($FlowKey) -or
        $Observed -gt
            [DateTimeOffset]$Context.LastOriginalInitialSynAtByFlowKey[$FlowKey]) {
        $Context.LastOriginalInitialSynAtByFlowKey[$FlowKey] = $Observed
    }
}

function Register-InitialSyn {
    param(
        [hashtable]$Context,
        [string]$FlowKey,
        [string]$ObservedAt,
        [bool]$IsRetransmission
    )

    if ($IsRetransmission) {
        return
    }
    $observed = [DateTimeOffset]::Parse(
        $ObservedAt,
        [Globalization.CultureInfo]::InvariantCulture
    )
    if ($Context.LastInitialSynAtByFlowKey.ContainsKey($FlowKey)) {
        $previous = [DateTimeOffset]$Context.LastInitialSynAtByFlowKey[$FlowKey]
        $intervalMs = ($observed - $previous).TotalMilliseconds
        if ($intervalMs -ge 0) {
            $Context.SameFourTupleReuseIntervalsMs.Add([double]$intervalMs)
        }
        if ($observed -le $previous) {
            return
        }
    }
    $Context.LastInitialSynAtByFlowKey[$FlowKey] = $observed

    $calibrated = Convert-WallTimeToMonotonicMilliseconds `
        -WallTime $observed `
        -Calibration $Context.ClockCalibration
    if ($null -ne $calibrated) {
        if ($Context.LastCalibratedInitialSynMsByFlowKey.ContainsKey($FlowKey)) {
            $previousCalibrated = [double](
                $Context.LastCalibratedInitialSynMsByFlowKey[$FlowKey]
            )
            $calibratedInterval = [double]$calibrated - $previousCalibrated
            if ($calibratedInterval -ge 0) {
                $Context.SameFourTupleCalibratedIntervalsMs.Add(
                    [double]$calibratedInterval
                )
            }
        }
        $Context.LastCalibratedInitialSynMsByFlowKey[$FlowKey] = [double]$calibrated
    }
}

function Get-FlowCompletionReason {
    param(
        [object]$Flow,
        [string]$Reason
    )

    if ($Reason -eq "source_port_reused") {
        return "source-port-reused"
    }
    if ($Reason -eq "capture_end") {
        return "capture-end"
    }
    if ($Flow.ClientCloseKind -eq "reset") {
        return "client-reset"
    }
    if ($Flow.ServerCloseKind -eq "reset") {
        return "server-reset"
    }
    if ($Flow.ClientCloseKind -eq "fin" -or $Flow.ServerCloseKind -eq "fin") {
        return "fin-close"
    }
    return "closed-other"
}

function Update-CaptureTimeState {
    param(
        [hashtable]$Context,
        [string]$ObservedAt,
        [bool]$Inbound
    )

    $observed = [DateTimeOffset]::Parse(
        $ObservedAt,
        [Globalization.CultureInfo]::InvariantCulture
    )
    if ($null -eq $Context.FirstPacketAt -or $observed -lt $Context.FirstPacketAt) {
        $Context.FirstPacketAt = $observed
    }
    if ($null -eq $Context.LastPacketAt -or $observed -gt $Context.LastPacketAt) {
        $Context.LastPacketAt = $observed
    }
    $directionProperty = if ($Inbound) {
        "FirstInboundPacketAt"
    } else {
        "FirstOutboundPacketAt"
    }
    if ($null -eq $Context[$directionProperty] -or
        $observed -lt $Context[$directionProperty]) {
        $Context[$directionProperty] = $observed
    }
}

function Resolve-CaptureCoverage {
    param([hashtable]$Context)

    if ([bool]$Context.CaptureCoverageResolved) {
        return
    }

    $limitBytes = [int64]$Context.CircularCaptureMaxBytes
    $fileSizeBytes = [int64]$Context.CaptureFileSizeBytes
    $limitReached = (
        $limitBytes -gt 0 -and
        $fileSizeBytes -ge [int64][Math]::Floor($limitBytes * 0.98)
    )
    $prefixGapSeconds = if ($null -eq $Context.FirstPacketAt) {
        $null
    } else {
        [Math]::Round(
            ($Context.FirstPacketAt - $Context.CaptureStartedAtDeclared).TotalSeconds,
            3
        )
    }
    $suffixGapSeconds = if ($null -eq $Context.LastPacketAt -or
        $Context.CaptureEndedAtDeclared -eq [DateTimeOffset]::MinValue) {
        $null
    } else {
        [Math]::Round(
            ($Context.CaptureEndedAtDeclared - $Context.LastPacketAt).TotalSeconds,
            3
        )
    }
    $prefixMissing = (
        $null -eq $Context.FirstPacketAt -or
        ($null -ne $prefixGapSeconds -and $prefixGapSeconds -gt 5)
    )
    $overwriteDetected = $limitReached -and $prefixMissing
    $candidateCounts = $Context.CapturePrefixCandidateOriginalOutcomeCounts
    $candidateTotal = [int]$Context.CapturePrefixIssueCandidateCount

    if ($overwriteDetected) {
        $Context.CaptureOverwriteUnresolvedCount = $candidateTotal
    } else {
        $Context.FailedConnectionAttemptCount += [int]$candidateCounts["failed"]
        $Context.RequestNoResponseAfterHandshakeCount += [int]$candidateCounts[
            "request_no_response_after_handshake"
        ]
    }
    foreach ($event in @($Context.ConnectIssueEvents)) {
        if ($event.outcome -ne "capture_prefix_unresolved_candidate") {
            continue
        }
        $event.outcome = if ($overwriteDetected) {
            "capture-overwrite-unresolved"
        } else {
            [string]$event.capture_prefix_candidate_original_outcome
        }
    }

    $continuousBidirectionalStartAt = if (
        $null -eq $Context.FirstInboundPacketAt -or
        $null -eq $Context.FirstOutboundPacketAt
    ) {
        $null
    } elseif ($Context.FirstInboundPacketAt -gt $Context.FirstOutboundPacketAt) {
        $Context.FirstInboundPacketAt
    } else {
        $Context.FirstOutboundPacketAt
    }
    $coverageStatus = if ($null -eq $Context.FirstPacketAt) {
        "no-target-packets"
    } elseif ($overwriteDetected) {
        "capture-overwrite-detected"
    } elseif ($prefixMissing) {
        "capture-prefix-incomplete"
    } elseif ($null -ne $suffixGapSeconds -and $suffixGapSeconds -gt 5) {
        "capture-suffix-incomplete"
    } else {
        "capture-window-retained"
    }

    $Context.CircularLimitReached = $limitReached
    $Context.CaptureOverwriteDetected = $overwriteDetected
    $Context.CaptureCoverageStatus = $coverageStatus
    $Context.CapturePrefixGapSeconds = $prefixGapSeconds
    $Context.CaptureSuffixGapSeconds = $suffixGapSeconds
    $Context.ContinuousBidirectionalStartAt = $continuousBidirectionalStartAt
    $Context.CaptureCoverageResolved = $true
}

function Write-AnalysisSummary {
    param(
        [hashtable]$Context,
        [string]$SummaryPath
    )

    $reuseIntervals = @(
        $Context.SameFourTupleReuseIntervalsMs |
            ForEach-Object { [double]$_ }
    )
    $originalReuseIntervals = @(
        $Context.SameFourTupleOriginalIntervalsMs |
            ForEach-Object { [double]$_ }
    )
    $calibratedReuseIntervals = @(
        $Context.SameFourTupleCalibratedIntervalsMs |
            ForEach-Object { [double]$_ }
    )
    $interfacePacketCounts = @(
        foreach ($interfaceId in @($Context.InterfacePacketCounts.Keys | Sort-Object)) {
            [ordered]@{
                interface_ordinal = [int]$interfaceId
                packet_count = [int64]$Context.InterfacePacketCounts[$interfaceId]
            }
        }
    )
    $summary = [ordered]@{
        schema_version = "spot-http-framing-evidence-v10"
        source_format = $Context.SourceFormat
        packet_payload_retained = $false
        analysis_window = [ordered]@{
            policy = "observation-start-to-observation-end"
            started_at = if (
                $Context.AnalysisWindowStartedAt -eq [DateTimeOffset]::MinValue
            ) { $null } else { $Context.AnalysisWindowStartedAt.ToString("o") }
            ended_at = if (
                $Context.AnalysisWindowEndedAt -eq [DateTimeOffset]::MinValue
            ) { $null } else { $Context.AnalysisWindowEndedAt.ToString("o") }
            excluded_before_count = [int64]$Context.AnalysisExcludedBeforeCount
            excluded_after_count = [int64]$Context.AnalysisExcludedAfterCount
        }
        packet_measurement = [ordered]@{
            interface_count = $interfacePacketCounts.Count
            interface_packet_counts = $interfacePacketCounts
            duplicate_detection_window_ms = $script:DuplicatePacketWindowMilliseconds
            duplicate_packet_count = [int64]$Context.DuplicatePacketCount
            duplicate_initial_syn_count = [int64]$Context.DuplicateInitialSynCount
            timestamp_regression_count = [int64](
                $Context.InterfaceTimestampRegressionCount +
                [int]$Context.ClockCalibration.timestamp_regression_count
            )
            timestamp_regression_max_ms = [Math]::Round(
                [double]$Context.InterfaceTimestampRegressionMaxMilliseconds,
                3
            )
            initial_syn_timestamp_regression_count =
                [int64]$Context.InitialSynTimestampRegressionCount
            initial_syn_timestamp_regression_max_ms = [Math]::Round(
                [double]$Context.InitialSynTimestampRegressionMaxMilliseconds,
                3
            )
            timestamp_ordering_policy = [string]$Context.PacketOrderingPolicy
            timestamp_order_correction_applied =
                [bool]$Context.TimestampOrderCorrectionApplied
            timestamp_order_sensitive_response_candidates =
                [int]$Context.PacketOrderSensitiveResponseCandidateCount
            sortable_target_packet_count =
                [int64]$Context.SortableTargetPacketCount
            sortable_target_packet_limit =
                [int64]$script:MaximumSortableTargetPacketCount
            client_to_server_rst_count = [int64]$Context.ClientToServerRstCount
            server_to_client_rst_count = [int64]$Context.ServerToClientRstCount
            rst_total = [int64](
                $Context.ClientToServerRstCount + $Context.ServerToClientRstCount
            )
            clock_calibration = [ordered]@{
                status = [string]$Context.ClockCalibration.status
                anchor_count = @($Context.ClockCalibration.anchors).Count
                wall_elapsed_ms = $Context.ClockCalibration.wall_elapsed_ms
                monotonic_elapsed_ms = $Context.ClockCalibration.monotonic_elapsed_ms
                wall_monotonic_drift_ms = (
                    $Context.ClockCalibration.wall_monotonic_drift_ms
                )
            }
            privacy = "aggregate-only; interface ordinals, addresses, and ports are not serialized"
        }
        capture_coverage = [ordered]@{
            status = $Context.CaptureCoverageStatus
            capture_started_at_declared = $Context.CaptureStartedAtDeclared.ToString("o")
            capture_ended_at_declared = if (
                $Context.CaptureEndedAtDeclared -eq [DateTimeOffset]::MinValue
            ) {
                $null
            } else {
                $Context.CaptureEndedAtDeclared.ToString("o")
            }
            retained_first_packet_at = if ($null -eq $Context.FirstPacketAt) {
                $null
            } else {
                $Context.FirstPacketAt.ToString("o")
            }
            retained_last_packet_at = if ($null -eq $Context.LastPacketAt) {
                $null
            } else {
                $Context.LastPacketAt.ToString("o")
            }
            retained_first_inbound_packet_at = if (
                $null -eq $Context.FirstInboundPacketAt
            ) {
                $null
            } else {
                $Context.FirstInboundPacketAt.ToString("o")
            }
            retained_first_outbound_packet_at = if (
                $null -eq $Context.FirstOutboundPacketAt
            ) {
                $null
            } else {
                $Context.FirstOutboundPacketAt.ToString("o")
            }
            continuous_bidirectional_start_at = if (
                $null -eq $Context.ContinuousBidirectionalStartAt
            ) {
                $null
            } else {
                $Context.ContinuousBidirectionalStartAt.ToString("o")
            }
            prefix_gap_seconds = $Context.CapturePrefixGapSeconds
            suffix_gap_seconds = $Context.CaptureSuffixGapSeconds
            capture_file_size_bytes = [int64]$Context.CaptureFileSizeBytes
            circular_limit_bytes = [int64]$Context.CircularCaptureMaxBytes
            circular_limit_reached = [bool]$Context.CircularLimitReached
            overwrite_detected = [bool]$Context.CaptureOverwriteDetected
            outcome_policy = if ([bool]$Context.CaptureOverwriteDetected) {
                "pre-continuity missing responses are capture-overwrite-unresolved"
            } else {
                "connection outcomes are based on retained packets"
            }
        }
        events_total = [int]$Context.EventIndex
        header_complete = [int]$Context.HeaderCompleteCount
        header_incomplete = [int]$Context.HeaderIncompleteCount
        request_kind_counts = [ordered]@{} + $Context.RequestKindCounts
        http_version_counts = [ordered]@{} + $Context.HttpVersionCounts
        framing_counts = [ordered]@{} + $Context.FramingCounts
        body_complete_counts = [ordered]@{} + $Context.BodyCompleteCounts
        server_close_counts = [ordered]@{} + $Context.ServerCloseCounts
        tcp_connection_summary = [ordered]@{
            connection_attempts_total = [int]$Context.ConnectionAttemptCount
            syn_packets_total = [int]$Context.SynPacketCount
            syn_retransmissions_total = [int]$Context.SynRetransmissionCount
            syn_ack_packets_total = [int]$Context.SynAckPacketCount
            syn_ack_observed_attempts = [int]$Context.SynAckAttemptCount
            handshake_completed_attempts = [int]$Context.HandshakeCompletedCount
            failed_connection_attempts = [int]$Context.FailedConnectionAttemptCount
            pre_handshake_failed_attempts = (
                [int]$Context.FailedConnectionAttemptCount
            )
            pre_handshake_failure_attribution = (
                "packet-only-not-product-attributable"
            )
            pre_handshake_failure_corroboration_policy = (
                "requires-observation-window-app-failure-counter-or-event-delta"
            )
            capture_overwrite_unresolved_attempts = [int]$Context.CaptureOverwriteUnresolvedCount
            capture_prefix_issue_candidates = [int]$Context.CapturePrefixIssueCandidateCount
            no_response_after_handshake_attempts = (
                [int]$Context.RequestNoResponseAfterHandshakeCount
            )
            no_response_definition = (
                "handshake-complete-with-outbound-request-payload-and-no-response"
            )
            request_no_response_after_handshake_attempts = (
                [int]$Context.RequestNoResponseAfterHandshakeCount
            )
            packet_order_sensitive_no_response_attempts = (
                [int]$Context.PacketOrderSensitiveNoResponseCount
            )
            packet_order_sensitive_no_response_policy = (
                "timestamp-and-capture-order-disagreement-is-evidence-hold"
            )
            handshake_only_without_request_attempts = (
                [int]$Context.HandshakeOnlyWithoutRequestCount
            )
            handshake_only_at_capture_end = (
                [int]$Context.HandshakeOnlyAtCaptureEndCount
            )
            unresolved_after_handshake_at_capture_end = [int]$Context.UnresolvedAfterHandshakeCount
            unresolved_attempts_at_capture_end = [int]$Context.UnresolvedConnectionAttemptCount
            reset_before_response_attempts = [int]$Context.ResetBeforeResponseCount
            capture_partial_flows = [int]$Context.CapturePartialFlowCount
            connect_issue_completion_reason_counts = (
                [ordered]@{} + $Context.ConnectIssueCompletionReasonCounts
            )
            rst_packets = [ordered]@{
                client_to_server = [int64]$Context.ClientToServerRstCount
                server_to_client = [int64]$Context.ServerToClientRstCount
                total = [int64](
                    $Context.ClientToServerRstCount + $Context.ServerToClientRstCount
                )
            }
            same_four_tuple_reuse = [ordered]@{
                original = (Get-IntervalSummary -Values $originalReuseIntervals)
                duplicate_removed = (Get-IntervalSummary -Values $reuseIntervals)
                monotonic_corrected = (
                    Get-IntervalSummary -Values $calibratedReuseIntervals
                )
                ordering_policy = if (
                    $Context.PacketOrderingPolicy -ceq "timestamp-sorted-stable-v1"
                ) {
                    "timestamp-sorted-per-four-tuple-v1"
                } else {
                    "capture-order"
                }
                measurement_integrity_status = if (
                    $Context.PacketOrderingPolicy -cne "timestamp-sorted-stable-v1"
                ) {
                    "packet-order-unresolved"
                } elseif ($Context.ClockCalibration.status -cne "complete") {
                    "clock-calibration-incomplete"
                } else {
                    "complete"
                }
                calibration_status = [string]$Context.ClockCalibration.status
                privacy = "aggregate-only; addresses and ports are not serialized"
            }
        }
        connect_issue_events = @($Context.ConnectIssueEvents)
        connect_issue_events_truncated = [bool]$Context.ConnectIssueEventsTruncated
        limitations = @(
            "chunked completion is unknown when the terminator is outside the packet snapshot",
            "a circular pktmon file can omit early packets; detected prefix loss is classified as capture-overwrite-unresolved",
            "a single SYN without a later packet at capture end is unresolved rather than a confirmed failure",
            "a failed pre-handshake packet attempt requires observation-window app failure counter or event corroboration before product attribution",
            "pcapng target packets are processed in stable timestamp order; original capture-order regressions remain aggregate evidence",
            "an inbound response that sorts before its SYN but follows that SYN in capture order is classified as packet-order-sensitive evidence hold"
        )
    }
    $summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $SummaryPath -Encoding utf8
    return $summary
}

function Complete-FlowAnalysis {
    param(
        [object]$Flow,
        [hashtable]$Context,
        [ValidateSet("closed", "source_port_reused", "capture_end")]
        [string]$Reason
    )

    if ([int]$Flow.SynCount -gt 0) {
        $Context.ConnectionAttemptCount = [int]$Context.ConnectionAttemptCount + 1
        $Context.SynPacketCount = [int]$Context.SynPacketCount + [int]$Flow.SynCount
        $retransmissions = [Math]::Max(0, [int]$Flow.SynCount - 1)
        $Context.SynRetransmissionCount = [int]$Context.SynRetransmissionCount + $retransmissions
        $Context.SynAckPacketCount = [int]$Context.SynAckPacketCount + [int]$Flow.SynAckCount
        if ([int]$Flow.SynAckCount -gt 0) {
            $Context.SynAckAttemptCount = [int]$Context.SynAckAttemptCount + 1
        }
        $handshakeCompleted = [bool]$Flow.HandshakeAckObserved -or
            $null -ne $Flow.ResponseBaseSequence
        if ($handshakeCompleted) {
            $Context.HandshakeCompletedCount = [int]$Context.HandshakeCompletedCount + 1
        }

        $resetBeforeResponse = (
            $null -eq $Flow.ResponseBaseSequence -and
            (
                $Flow.ServerCloseKind -eq "reset" -or
                $Flow.ClientCloseKind -eq "reset"
            )
        )
        if ($resetBeforeResponse) {
            $Context.ResetBeforeResponseCount = [int]$Context.ResetBeforeResponseCount + 1
        }

        $issueOutcome = $null
        if ($null -eq $Flow.ResponseBaseSequence) {
            if ($handshakeCompleted) {
                if ([bool]$Flow.RequestPayloadObserved) {
                    if ([bool]$Flow.PacketOrderSensitiveResponseObserved) {
                        $issueOutcome = "packet_order_sensitive_no_response_unresolved"
                        $Context.PacketOrderSensitiveNoResponseCount = (
                            [int]$Context.PacketOrderSensitiveNoResponseCount + 1
                        )
                    } elseif ($Reason -eq "capture_end") {
                        $issueOutcome = "unresolved_after_handshake_capture_end"
                        $Context.UnresolvedAfterHandshakeCount = (
                            [int]$Context.UnresolvedAfterHandshakeCount + 1
                        )
                    } else {
                        $issueOutcome = "request_no_response_after_handshake"
                        $Context.RequestNoResponseAfterHandshakeCount = (
                            [int]$Context.RequestNoResponseAfterHandshakeCount + 1
                        )
                    }
                } elseif ($Reason -eq "capture_end") {
                    $issueOutcome = "handshake_only_at_capture_end"
                    $Context.HandshakeOnlyAtCaptureEndCount = (
                        [int]$Context.HandshakeOnlyAtCaptureEndCount + 1
                    )
                } else {
                    $issueOutcome = "handshake_only_without_request"
                    $Context.HandshakeOnlyWithoutRequestCount = (
                        [int]$Context.HandshakeOnlyWithoutRequestCount + 1
                    )
                }
            } elseif ($resetBeforeResponse -or
                $Reason -eq "closed" -or
                $Reason -eq "source_port_reused" -or
                ($retransmissions -gt 0 -and [int]$Flow.SynAckCount -eq 0)) {
                $issueOutcome = "failed"
                $Context.FailedConnectionAttemptCount = [int]$Context.FailedConnectionAttemptCount + 1
            } elseif ($Reason -eq "capture_end") {
                $issueOutcome = "unresolved_capture_end"
                $Context.UnresolvedConnectionAttemptCount = [int]$Context.UnresolvedConnectionAttemptCount + 1
            }
        }

        $candidateOriginalOutcome = $null
        if ($issueOutcome -in @(
                "failed",
                "request_no_response_after_handshake"
            )) {
            $flowLastObservedAt = if ($null -eq $Flow.LastObservedAt) {
                $null
            } else {
                [DateTimeOffset]::Parse(
                    [string]$Flow.LastObservedAt,
                    [Globalization.CultureInfo]::InvariantCulture
                )
            }
            $isCapturePrefixCandidate = (
                $null -eq $Context.FirstInboundPacketAt -or
                ($null -ne $flowLastObservedAt -and
                    $flowLastObservedAt -lt $Context.FirstInboundPacketAt)
            )
            if ($isCapturePrefixCandidate) {
                if ($issueOutcome -eq "failed") {
                    $Context.FailedConnectionAttemptCount = [Math]::Max(
                        0,
                        [int]$Context.FailedConnectionAttemptCount - 1
                    )
                } else {
                    $Context.RequestNoResponseAfterHandshakeCount = [Math]::Max(
                        0,
                        [int]$Context.RequestNoResponseAfterHandshakeCount - 1
                    )
                }
                $candidateOriginalOutcome = $issueOutcome
                $Context.CapturePrefixIssueCandidateCount += 1
                $Context.CapturePrefixCandidateOriginalOutcomeCounts[
                    $candidateOriginalOutcome
                ] += 1
                $issueOutcome = "capture_prefix_unresolved_candidate"
            }
        }

        if ($null -ne $issueOutcome) {
            $completionReason = Get-FlowCompletionReason `
                -Flow $Flow `
                -Reason $Reason
            Add-Count `
                -Table $Context.ConnectIssueCompletionReasonCounts `
                -Key $completionReason
            if ($Context.ConnectIssueEvents.Count -lt 1000) {
                $Context.ConnectIssueEvents.Add([pscustomobject][ordered]@{
                    event_index = $Context.ConnectIssueEvents.Count + 1
                    first_syn_at_local = $Flow.FirstSynAt
                    last_observed_at_local = $Flow.LastObservedAt
                    syn_packets = [int]$Flow.SynCount
                    syn_retransmissions = $retransmissions
                    syn_ack_observed = ([int]$Flow.SynAckCount -gt 0)
                    handshake_ack_observed = [bool]$Flow.HandshakeAckObserved
                    request_kind = $Flow.RequestKind
                    outbound_request_payload_observed = [bool]$Flow.RequestPayloadObserved
                    inbound_response_payload_observed = ($null -ne $Flow.ResponseBaseSequence)
                    server_close_kind = $Flow.ServerCloseKind
                    client_close_kind = $Flow.ClientCloseKind
                    reset_before_response = $resetBeforeResponse
                    completion_reason = $completionReason
                    outcome = $issueOutcome
                    capture_prefix_candidate_original_outcome = $candidateOriginalOutcome
                    packet_order_sensitive_response_candidate =
                        [bool]$Flow.PacketOrderSensitiveResponseObserved
                    response_candidate_timestamp_at_local =
                        $Flow.PacketOrderSensitiveResponseAt
                    response_candidate_capture_ordinal_delta =
                        $Flow.PacketOrderSensitiveCaptureOrdinalDelta
                    response_candidate_timestamp_lead_ms =
                        $Flow.PacketOrderSensitiveTimestampLeadMilliseconds
                })
            } else {
                $Context.ConnectIssueEventsTruncated = $true
            }
        }
    } else {
        $Context.CapturePartialFlowCount = [int]$Context.CapturePartialFlowCount + 1
    }

    Write-FlowEvidence -Flow $Flow -Context $Context
}

function Write-FlowEvidence {
    param(
        [object]$Flow,
        [hashtable]$Context
    )

    if ($null -eq $Flow.ResponseBaseSequence) {
        return
    }
    $header = Get-HeaderEvidence -Flow $Flow
    $completion = Get-BodyCompletion -Flow $Flow -Header $header
    $Context.EventIndex = [int]$Context.EventIndex + 1
    $bodyComplete = if ($null -eq $completion.Complete) { "unknown" } elseif ($completion.Complete) { "true" } else { "false" }
    $event = [ordered]@{
        event_index = $Context.EventIndex
        response_started_at_local = $Flow.ResponseStartedAt
        last_observed_at_local = $Flow.LastObservedAt
        request_kind = $Flow.RequestKind
        http_version = $header.HttpVersion
        status_code = $header.StatusCode
        header_complete = [bool]$header.HeaderComplete
        content_length_present = $header.ContentLengthPresent
        transfer_encoding = $header.TransferEncoding
        framing = $header.Framing
        body_complete = $bodyComplete
        body_completion_basis = $completion.Basis
        server_close_kind = $Flow.ServerCloseKind
        client_close_kind = $Flow.ClientCloseKind
    }
    $Context.Writer.WriteLine(($event | ConvertTo-Json -Compress))
    Add-Count -Table $Context.RequestKindCounts -Key $Flow.RequestKind
    Add-Count -Table $Context.HttpVersionCounts -Key $header.HttpVersion
    Add-Count -Table $Context.FramingCounts -Key $header.Framing
    Add-Count -Table $Context.BodyCompleteCounts -Key $bodyComplete
    Add-Count -Table $Context.ServerCloseCounts -Key $Flow.ServerCloseKind
    if ($header.HeaderComplete) {
        $Context.HeaderCompleteCount = [int]$Context.HeaderCompleteCount + 1
    } else {
        $Context.HeaderIncompleteCount = [int]$Context.HeaderIncompleteCount + 1
    }
}

function Convert-RecordTime {
    param(
        [string]$TimestampText,
        [hashtable]$Context
    )

    if ($TimestampText -notmatch '^(?<hour>\d{2}):(?<minute>\d{2}):(?<second>\d{2})\.(?<fraction>\d+)$') {
        throw "Pktmon packet timestamp is invalid."
    }
    $fraction = $Matches.fraction
    if ($fraction.Length -gt 7) {
        $fraction = $fraction.Substring(0, 7)
    }
    $fraction = $fraction.PadRight(7, '0')
    $wholeSeconds = (
        [int64]$Matches.hour * 3600 +
        [int64]$Matches.minute * 60 +
        [int64]$Matches.second
    )
    $ticks = $wholeSeconds * [TimeSpan]::TicksPerSecond + [int64]$fraction
    $time = [TimeSpan]::FromTicks($ticks)
    if ($null -ne $Context.LastTime -and $time -lt ($Context.LastTime - [TimeSpan]::FromHours(12))) {
        $Context.CaptureDate = ([datetime]$Context.CaptureDate).AddDays(1)
    }
    $Context.LastTime = $time
    $localDateTime = ([datetime]$Context.CaptureDate).Date.Add($time)
    return [DateTimeOffset]::new($localDateTime, $Context.Offset).ToString("o")
}

function Add-PacketToAnalysis {
    param(
        [byte[]]$Bytes,
        [string]$ObservedAt,
        [hashtable]$Context,
        [int]$TargetServerPort,
        [int]$InterfaceId = 0,
        [object]$PacketRecord = $null,
        [int64]$CaptureOrdinal = 0,
        [switch]$CaptureOrderAlreadyMeasured
    )

    $packet = if ($null -eq $PacketRecord) {
        Get-PacketRecord -Bytes $Bytes -TargetServerPort $TargetServerPort
    } else {
        $PacketRecord
    }
    if ($null -eq $packet) {
        return
    }
    $observed = [DateTimeOffset]::Parse(
        $ObservedAt,
        [Globalization.CultureInfo]::InvariantCulture
    )
    if ($Context.AnalysisWindowStartedAt -ne [DateTimeOffset]::MinValue -and
        $observed -lt $Context.AnalysisWindowStartedAt) {
        $Context.AnalysisExcludedBeforeCount =
            [int64]$Context.AnalysisExcludedBeforeCount + 1
        return
    }
    if ($Context.AnalysisWindowEndedAt -ne [DateTimeOffset]::MinValue -and
        $observed -gt $Context.AnalysisWindowEndedAt) {
        $Context.AnalysisExcludedAfterCount =
            [int64]$Context.AnalysisExcludedAfterCount + 1
        return
    }

    $initialSyn = -not $packet.IsInbound -and $packet.Syn -and -not $packet.Ack
    if (-not $CaptureOrderAlreadyMeasured) {
        Register-CaptureOrderMeasurement `
            -Context $Context `
            -Packet $packet `
            -Observed $observed `
            -InterfaceId $InterfaceId
    }
    $fingerprint = (
        "{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}" -f
            $packet.FlowKey,
            [bool]$packet.IsInbound,
            [uint32]$packet.Sequence,
            [bool]$packet.Syn,
            [bool]$packet.Ack,
            [bool]$packet.Fin,
            [bool]$packet.Rst,
            [int]$packet.WirePayloadLength
    )
    if ($Context.RecentPacketFingerprint.ContainsKey($fingerprint)) {
        $previousFingerprint = $Context.RecentPacketFingerprint[$fingerprint]
        $duplicateGapMs = [Math]::Abs(
            ($observed - [DateTimeOffset]$previousFingerprint.ObservedAt).TotalMilliseconds
        )
        if ([int]$previousFingerprint.InterfaceId -ne $InterfaceId -and
            $duplicateGapMs -le $script:DuplicatePacketWindowMilliseconds) {
            $Context.DuplicatePacketCount = [int64]$Context.DuplicatePacketCount + 1
            if ($initialSyn) {
                $Context.DuplicateInitialSynCount =
                    [int64]$Context.DuplicateInitialSynCount + 1
            }
            return
        }
    }
    $Context.RecentPacketFingerprint[$fingerprint] = [pscustomobject]@{
        InterfaceId = $InterfaceId
        ObservedAt = $observed
    }

    if ($packet.Rst) {
        if ($packet.IsInbound) {
            $Context.ServerToClientRstCount =
                [int64]$Context.ServerToClientRstCount + 1
        } else {
            $Context.ClientToServerRstCount =
                [int64]$Context.ClientToServerRstCount + 1
        }
    }
    Update-CaptureTimeState `
        -Context $Context `
        -ObservedAt $ObservedAt `
        -Inbound ([bool]$packet.IsInbound)

    if ($initialSyn) {
        $isRetransmission = $false
        $packetOrderSensitiveResponse = $null
        if ($Context.Flows.ContainsKey($packet.FlowKey)) {
            $existingFlow = $Context.Flows[$packet.FlowKey]
            $isRetransmission = (
                $null -ne $existingFlow.InitialSynSequence -and
                [uint32]$existingFlow.InitialSynSequence -eq [uint32]$packet.Sequence -and
                $null -eq $existingFlow.ResponseBaseSequence -and
                $existingFlow.ServerCloseKind -eq "not_observed" -and
                $existingFlow.ClientCloseKind -eq "not_observed"
            )
            if (-not $isRetransmission) {
                if ([int]$existingFlow.SynCount -eq 0 -and
                    $null -ne $existingFlow.ResponseBaseSequence -and
                    $CaptureOrdinal -gt 0 -and
                    [int64]$existingFlow.ResponseCaptureOrdinal -gt
                        $CaptureOrdinal) {
                    $responseAt = [DateTimeOffset]::Parse(
                        [string]$existingFlow.ResponseStartedAt,
                        [Globalization.CultureInfo]::InvariantCulture
                    )
                    $packetOrderSensitiveResponse = [pscustomobject]@{
                        ObservedAt = [string]$existingFlow.ResponseStartedAt
                        CaptureOrdinalDelta = (
                            [int64]$existingFlow.ResponseCaptureOrdinal -
                            $CaptureOrdinal
                        )
                        TimestampLeadMilliseconds = [Math]::Round(
                            ($observed - $responseAt).TotalMilliseconds,
                            3
                        )
                    }
                    $Context.PacketOrderSensitiveResponseCandidateCount = (
                        [int]$Context.PacketOrderSensitiveResponseCandidateCount + 1
                    )
                }
                Complete-FlowAnalysis `
                    -Flow $existingFlow `
                    -Context $Context `
                    -Reason "source_port_reused"
                $Context.Flows.Remove($packet.FlowKey)
            }
        }
        Register-InitialSyn `
            -Context $Context `
            -FlowKey $packet.FlowKey `
            -ObservedAt $ObservedAt `
            -IsRetransmission $isRetransmission
        if (-not $Context.Flows.ContainsKey($packet.FlowKey)) {
            $Context.Flows[$packet.FlowKey] = New-FlowState -FlowKey $packet.FlowKey
        }
        if ($null -ne $packetOrderSensitiveResponse) {
            $Context.Flows[$packet.FlowKey].PacketOrderSensitiveResponseObserved =
                $true
            $Context.Flows[$packet.FlowKey].PacketOrderSensitiveResponseAt =
                $packetOrderSensitiveResponse.ObservedAt
            $Context.Flows[$packet.FlowKey].PacketOrderSensitiveCaptureOrdinalDelta =
                $packetOrderSensitiveResponse.CaptureOrdinalDelta
            $Context.Flows[$packet.FlowKey].PacketOrderSensitiveTimestampLeadMilliseconds =
                $packetOrderSensitiveResponse.TimestampLeadMilliseconds
        }
    }
    if (-not $Context.Flows.ContainsKey($packet.FlowKey)) {
        if ($packet.WirePayloadLength -eq 0 -and
            -not $initialSyn) {
            return
        }
        $Context.Flows[$packet.FlowKey] = New-FlowState -FlowKey $packet.FlowKey
    }
    $flow = $Context.Flows[$packet.FlowKey]
    Set-FlowLastObservedAt -Flow $flow -ObservedAt $ObservedAt
    if ($initialSyn) {
        if ($null -eq $flow.InitialSynSequence) {
            $flow.InitialSynSequence = [uint32]$packet.Sequence
            $flow.FirstSynAt = $ObservedAt
        }
        $flow.SynCount = [int]$flow.SynCount + 1
    }
    if ($packet.IsInbound -and $packet.Syn -and $packet.Ack) {
        $flow.SynAckCount = [int]$flow.SynAckCount + 1
    }
    if (-not $packet.IsInbound -and -not $packet.Syn -and $packet.Ack -and
        [int]$flow.SynAckCount -gt 0) {
        $flow.HandshakeAckObserved = $true
    }
    Set-CloseKind -Flow $flow -FromServer $packet.IsInbound -Fin $packet.Fin -Rst $packet.Rst

    if (-not $packet.IsInbound -and $packet.WirePayloadLength -gt 0) {
        $flow.RequestPayloadObserved = $true
        if ($packet.CapturedPayload.Length -gt 0 -and
            $flow.RequestKind -eq "unknown") {
            $flow.RequestKind = Get-RequestKind -Payload $packet.CapturedPayload
        }
    }
    if ($packet.IsInbound -and $packet.WirePayloadLength -gt 0) {
        if ($null -eq $flow.ResponseBaseSequence) {
            $flow.ResponseBaseSequence = [uint32]$packet.Sequence
            $flow.ResponseStartedAt = $ObservedAt
            $flow.ResponseCaptureOrdinal = $CaptureOrdinal
        }
        $relativeStart = Get-SequenceDelta `
            -Sequence ([uint32]$packet.Sequence) `
            -BaseSequence ([uint32]$flow.ResponseBaseSequence)
        if ($relativeStart -ge 0) {
            $flow.Intervals.Add([pscustomobject]@{
                Start = $relativeStart
                End = $relativeStart + [int64]$packet.WirePayloadLength
            })
            if ($packet.CapturedPayload.Length -gt 0 -and
                $relativeStart -lt $script:MaximumHeaderBytes -and
                -not $flow.CapturedSegments.ContainsKey($relativeStart)) {
                $remaining = [int]($script:MaximumHeaderBytes - $relativeStart)
                $take = [Math]::Min($packet.CapturedPayload.Length, $remaining)
                $flow.CapturedSegments[$relativeStart] = [byte[]]$packet.CapturedPayload[0..($take - 1)]
            }
        }
    }
    $flowClosed = $packet.Rst -or (
        $flow.ServerCloseKind -ne "not_observed" -and
        $flow.ClientCloseKind -ne "not_observed"
    )
    if ($flowClosed) {
        Complete-FlowAnalysis -Flow $flow -Context $Context -Reason "closed"
        $Context.Flows.Remove($packet.FlowKey)
    }
}

function Convert-PktmonHexEvidence {
    param(
        [string]$SourcePath,
        [string]$EventPath,
        [string]$SummaryPath,
        [DateTimeOffset]$StartedAt,
        [DateTimeOffset]$EndedAt = [DateTimeOffset]::MinValue,
        [DateTimeOffset]$WindowStartedAt = [DateTimeOffset]::MinValue,
        [DateTimeOffset]$WindowEndedAt = [DateTimeOffset]::MinValue,
        [string]$CalibrationPath = "",
        [long]$FileSizeBytes = 0,
        [int]$CircularMaxFileSizeMB = 0,
        [int]$TargetServerPort
    )

    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
        throw "Pktmon hex input was not found."
    }
    foreach ($outputPath in @($EventPath, $SummaryPath)) {
        $parent = Split-Path -Parent $outputPath
        if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
    }

    $writer = [IO.StreamWriter]::new($EventPath, $false, [Text.UTF8Encoding]::new($false))
    $context = @{
        SourceFormat = "pktmon-etl2txt-hex"
        Writer = $writer
        Flows = @{}
        EventIndex = 0
        HeaderCompleteCount = 0
        HeaderIncompleteCount = 0
        RequestKindCounts = @{}
        HttpVersionCounts = @{}
        FramingCounts = @{}
        BodyCompleteCounts = @{}
        ServerCloseCounts = @{}
        ConnectionAttemptCount = 0
        SynPacketCount = 0
        SynRetransmissionCount = 0
        SynAckPacketCount = 0
        SynAckAttemptCount = 0
        HandshakeCompletedCount = 0
        FailedConnectionAttemptCount = 0
        RequestNoResponseAfterHandshakeCount = 0
        PacketOrderSensitiveNoResponseCount = 0
        PacketOrderSensitiveResponseCandidateCount = 0
        HandshakeOnlyWithoutRequestCount = 0
        HandshakeOnlyAtCaptureEndCount = 0
        UnresolvedAfterHandshakeCount = 0
        UnresolvedConnectionAttemptCount = 0
        ResetBeforeResponseCount = 0
        CapturePartialFlowCount = 0
        ConnectIssueEvents = [Collections.Generic.List[object]]::new()
        ConnectIssueEventsTruncated = $false
        ConnectIssueCompletionReasonCounts = @{}
        LastInitialSynAtByFlowKey = @{}
        SameFourTupleReuseIntervalsMs = [Collections.Generic.List[double]]::new()
        CaptureStartedAtDeclared = $StartedAt
        CaptureEndedAtDeclared = $EndedAt
        CaptureFileSizeBytes = [int64]$FileSizeBytes
        CircularCaptureMaxBytes = [int64]$CircularMaxFileSizeMB * 1MB
        FirstPacketAt = $null
        LastPacketAt = $null
        FirstInboundPacketAt = $null
        FirstOutboundPacketAt = $null
        ContinuousBidirectionalStartAt = $null
        CapturePrefixGapSeconds = $null
        CaptureSuffixGapSeconds = $null
        CircularLimitReached = $false
        CaptureOverwriteDetected = $false
        CaptureCoverageStatus = "pending"
        CaptureCoverageResolved = $false
        CaptureOverwriteUnresolvedCount = 0
        CapturePrefixIssueCandidateCount = 0
        CapturePrefixCandidateOriginalOutcomeCounts = @{
            failed = 0
            request_no_response_after_handshake = 0
        }
        CaptureDate = $StartedAt.Date
        Offset = $StartedAt.Offset
        LastTime = $null
    }
    Initialize-MeasurementContext `
        -Context $context `
        -WindowStartedAt $WindowStartedAt `
        -WindowEndedAt $WindowEndedAt `
        -CalibrationPath $CalibrationPath
    $currentTimestamp = $null
    $currentBytes = [Collections.Generic.List[byte]]::new()
    try {
        foreach ($line in [IO.File]::ReadLines($SourcePath)) {
            if ($line -match '^(?<time>\d{2}:\d{2}:\d{2}\.\d+)\s+PktGroupId\b') {
                if ($null -ne $currentTimestamp -and $currentBytes.Count -gt 0) {
                    $observedAt = Convert-RecordTime -TimestampText $currentTimestamp -Context $context
                    Add-PacketToAnalysis `
                        -Bytes ([byte[]]$currentBytes.ToArray()) `
                        -ObservedAt $observedAt `
                        -Context $context `
                        -TargetServerPort $TargetServerPort
                }
                $currentTimestamp = $Matches.time
                $currentBytes.Clear()
                continue
            }
            if ($null -ne $currentTimestamp -and $line -match '^\s*0x[0-9a-fA-F]+:\s*(?<hex>.*)$') {
                foreach ($match in [regex]::Matches($Matches.hex, '(?i)\b[0-9a-f]{4}\b')) {
                    $word = $match.Value
                    $currentBytes.Add([Convert]::ToByte($word.Substring(0, 2), 16))
                    $currentBytes.Add([Convert]::ToByte($word.Substring(2, 2), 16))
                }
            }
        }
        if ($null -ne $currentTimestamp -and $currentBytes.Count -gt 0) {
            $observedAt = Convert-RecordTime -TimestampText $currentTimestamp -Context $context
            Add-PacketToAnalysis `
                -Bytes ([byte[]]$currentBytes.ToArray()) `
                -ObservedAt $observedAt `
                -Context $context `
                -TargetServerPort $TargetServerPort
        }
        foreach ($flow in @($context.Flows.Values)) {
            Complete-FlowAnalysis -Flow $flow -Context $context -Reason "capture_end"
        }
        Resolve-CaptureCoverage -Context $context
    } finally {
        $writer.Dispose()
    }

    return Write-AnalysisSummary -Context $context -SummaryPath $SummaryPath
}

function Convert-PcapngEvidence {
    param(
        [string]$SourcePath,
        [string]$EventPath,
        [string]$SummaryPath,
        [DateTimeOffset]$StartedAt,
        [DateTimeOffset]$EndedAt = [DateTimeOffset]::MinValue,
        [DateTimeOffset]$WindowStartedAt = [DateTimeOffset]::MinValue,
        [DateTimeOffset]$WindowEndedAt = [DateTimeOffset]::MinValue,
        [string]$CalibrationPath = "",
        [long]$FileSizeBytes = 0,
        [int]$CircularMaxFileSizeMB = 0,
        [int]$TargetServerPort
    )

    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
        throw "Pcapng input was not found."
    }
    foreach ($outputPath in @($EventPath, $SummaryPath)) {
        $parent = Split-Path -Parent $outputPath
        if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
    }
    $writer = [IO.StreamWriter]::new($EventPath, $false, [Text.UTF8Encoding]::new($false))
    $context = @{
        SourceFormat = "pcapng"
        Writer = $writer
        Flows = @{}
        EventIndex = 0
        HeaderCompleteCount = 0
        HeaderIncompleteCount = 0
        RequestKindCounts = @{}
        HttpVersionCounts = @{}
        FramingCounts = @{}
        BodyCompleteCounts = @{}
        ServerCloseCounts = @{}
        ConnectionAttemptCount = 0
        SynPacketCount = 0
        SynRetransmissionCount = 0
        SynAckPacketCount = 0
        SynAckAttemptCount = 0
        HandshakeCompletedCount = 0
        FailedConnectionAttemptCount = 0
        RequestNoResponseAfterHandshakeCount = 0
        PacketOrderSensitiveNoResponseCount = 0
        PacketOrderSensitiveResponseCandidateCount = 0
        HandshakeOnlyWithoutRequestCount = 0
        HandshakeOnlyAtCaptureEndCount = 0
        UnresolvedAfterHandshakeCount = 0
        UnresolvedConnectionAttemptCount = 0
        ResetBeforeResponseCount = 0
        CapturePartialFlowCount = 0
        ConnectIssueEvents = [Collections.Generic.List[object]]::new()
        ConnectIssueEventsTruncated = $false
        ConnectIssueCompletionReasonCounts = @{}
        LastInitialSynAtByFlowKey = @{}
        SameFourTupleReuseIntervalsMs = [Collections.Generic.List[double]]::new()
        CaptureStartedAtDeclared = $StartedAt
        CaptureEndedAtDeclared = $EndedAt
        CaptureFileSizeBytes = [int64]$FileSizeBytes
        CircularCaptureMaxBytes = [int64]$CircularMaxFileSizeMB * 1MB
        FirstPacketAt = $null
        LastPacketAt = $null
        FirstInboundPacketAt = $null
        FirstOutboundPacketAt = $null
        ContinuousBidirectionalStartAt = $null
        CapturePrefixGapSeconds = $null
        CaptureSuffixGapSeconds = $null
        CircularLimitReached = $false
        CaptureOverwriteDetected = $false
        CaptureCoverageStatus = "pending"
        CaptureCoverageResolved = $false
        CaptureOverwriteUnresolvedCount = 0
        CapturePrefixIssueCandidateCount = 0
        CapturePrefixCandidateOriginalOutcomeCounts = @{
            failed = 0
            request_no_response_after_handshake = 0
        }
    }
    Initialize-MeasurementContext `
        -Context $context `
        -WindowStartedAt $WindowStartedAt `
        -WindowEndedAt $WindowEndedAt `
        -CalibrationPath $CalibrationPath
    $interfaces = [Collections.Generic.List[object]]::new()
    $targetPackets = [Collections.Generic.List[object]]::new()
    $captureOrdinal = 0L
    $littleEndian = $true
    $nextProgressPercent = 10
    $stream = [IO.File]::Open($SourcePath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $reader = [IO.BinaryReader]::new($stream)
    try {
        while ($reader.BaseStream.Position -lt $reader.BaseStream.Length) {
            $header = Read-ExactBytes -Reader $reader -Count 8
            $typeAsLittleEndian = Get-EndianUInt32 -Bytes $header -Offset 0 -LittleEndian $true
            if ($typeAsLittleEndian -eq [uint32]0x0A0D0D0A) {
                $byteOrderMagic = Read-ExactBytes -Reader $reader -Count 4
                if ([BitConverter]::ToString($byteOrderMagic) -eq "4D-3C-2B-1A") {
                    $littleEndian = $true
                } elseif ([BitConverter]::ToString($byteOrderMagic) -eq "1A-2B-3C-4D") {
                    $littleEndian = $false
                } else {
                    throw "Pcapng section byte order is invalid."
                }
                $blockLength = [int](Get-EndianUInt32 -Bytes $header -Offset 4 -LittleEndian $littleEndian)
                if ($blockLength -lt 28 -or ($blockLength % 4) -ne 0) {
                    throw "Pcapng section block length is invalid."
                }
                $remainder = Read-ExactBytes -Reader $reader -Count ($blockLength - 12)
                $trailerLength = Get-EndianUInt32 `
                    -Bytes $remainder `
                    -Offset ($remainder.Length - 4) `
                    -LittleEndian $littleEndian
                if ($trailerLength -ne $blockLength) {
                    throw "Pcapng section block trailer is invalid."
                }
                $interfaces.Clear()
                continue
            }

            $blockType = Get-EndianUInt32 -Bytes $header -Offset 0 -LittleEndian $littleEndian
            $blockLength = [int](Get-EndianUInt32 -Bytes $header -Offset 4 -LittleEndian $littleEndian)
            if ($blockLength -lt 12 -or ($blockLength % 4) -ne 0) {
                throw "Pcapng block length is invalid."
            }
            $remainder = Read-ExactBytes -Reader $reader -Count ($blockLength - 8)
            $trailerLength = Get-EndianUInt32 `
                -Bytes $remainder `
                -Offset ($remainder.Length - 4) `
                -LittleEndian $littleEndian
            if ($trailerLength -ne $blockLength) {
                throw "Pcapng block trailer is invalid."
            }
            $bodyLength = $remainder.Length - 4
            $body = if ($bodyLength -gt 0) {
                [byte[]]$remainder[0..($bodyLength - 1)]
            } else {
                [byte[]]@()
            }

            if ($blockType -eq 1) {
                if ($body.Length -lt 8) {
                    throw "Pcapng interface block is truncated."
                }
                $timestampResolution = [uint64]1000000
                $optionOffset = 8
                while ($optionOffset + 4 -le $body.Length) {
                    $optionCode = Get-EndianUInt16 -Bytes $body -Offset $optionOffset -LittleEndian $littleEndian
                    $optionLength = Get-EndianUInt16 -Bytes $body -Offset ($optionOffset + 2) -LittleEndian $littleEndian
                    $optionOffset += 4
                    if ($optionCode -eq 0) {
                        break
                    }
                    if ($optionOffset + $optionLength -gt $body.Length) {
                        throw "Pcapng interface option is truncated."
                    }
                    if ($optionCode -eq 9 -and $optionLength -eq 1) {
                        $resolutionValue = [int]$body[$optionOffset]
                        if (($resolutionValue -band 0x80) -ne 0) {
                            $timestampResolution = [uint64][Math]::Pow(2, ($resolutionValue -band 0x7F))
                        } else {
                            $timestampResolution = [uint64][Math]::Pow(10, $resolutionValue)
                        }
                    }
                    $optionOffset += (($optionLength + 3) -band -4)
                }
                $interfaces.Add([pscustomobject]@{
                    LinkType = Get-EndianUInt16 -Bytes $body -Offset 0 -LittleEndian $littleEndian
                    TimestampResolution = $timestampResolution
                })
                continue
            }

            if ($blockType -ne 6 -or $body.Length -lt 20) {
                continue
            }
            $interfaceId = [int](Get-EndianUInt32 -Bytes $body -Offset 0 -LittleEndian $littleEndian)
            if ($interfaceId -lt 0 -or $interfaceId -ge $interfaces.Count) {
                throw "Pcapng packet refers to an unknown interface."
            }
            $interface = $interfaces[$interfaceId]
            if ([int]$interface.LinkType -ne 1) {
                continue
            }
            $capturedLength = [int](Get-EndianUInt32 -Bytes $body -Offset 12 -LittleEndian $littleEndian)
            if ($capturedLength -lt 0 -or $capturedLength -gt ($body.Length - 20)) {
                throw "Pcapng packet data is truncated."
            }
            if ($capturedLength -eq 0) {
                continue
            }
            $packetBytes = [byte[]]$body[20..(20 + $capturedLength - 1)]
            $timestampHigh = [uint64](Get-EndianUInt32 -Bytes $body -Offset 4 -LittleEndian $littleEndian)
            $timestampLow = [uint64](Get-EndianUInt32 -Bytes $body -Offset 8 -LittleEndian $littleEndian)
            $timestampRaw = $timestampHigh * [uint64]4294967296 + $timestampLow
            $resolution = [uint64]$interface.TimestampResolution
            if ($resolution -eq 0) {
                throw "Pcapng timestamp resolution is invalid."
            }
            $wholeSeconds = [int64]($timestampRaw / $resolution)
            $remainderUnits = [uint64]($timestampRaw % $resolution)
            $fractionTicks = [int64](
                ([decimal]$remainderUnits * [TimeSpan]::TicksPerSecond) / [decimal]$resolution
            )
            $packetTime = [DateTimeOffset]::FromUnixTimeSeconds($wholeSeconds)
            $packetTime = $packetTime.AddTicks($fractionTicks)
            $packetTime = $packetTime.ToOffset($StartedAt.Offset)
            $observedAt = $packetTime.ToString("o")
            $packet = Get-PacketRecord `
                -Bytes $packetBytes `
                -TargetServerPort $TargetServerPort
            if ($null -ne $packet) {
                if ($WindowStartedAt -ne [DateTimeOffset]::MinValue -and
                    $packetTime -lt $WindowStartedAt) {
                    $context.AnalysisExcludedBeforeCount =
                        [int64]$context.AnalysisExcludedBeforeCount + 1
                } elseif ($WindowEndedAt -ne [DateTimeOffset]::MinValue -and
                    $packetTime -gt $WindowEndedAt) {
                    $context.AnalysisExcludedAfterCount =
                        [int64]$context.AnalysisExcludedAfterCount + 1
                } else {
                    $captureOrdinal += 1
                    Register-CaptureOrderMeasurement `
                        -Context $context `
                        -Packet $packet `
                        -Observed $packetTime `
                        -InterfaceId $interfaceId
                    $targetPackets.Add([pscustomobject]@{
                        ObservedAt = $observedAt
                        ObservedTicks = [int64]$packetTime.UtcTicks
                        InterfaceId = $interfaceId
                        CaptureOrdinal = $captureOrdinal
                        Packet = $packet
                    })
                    if ($targetPackets.Count -gt
                        $script:MaximumSortableTargetPacketCount) {
                        throw (
                            "Pcapng target packet sort limit exceeded: {0}" -f
                                $script:MaximumSortableTargetPacketCount
                        )
                    }
                }
            }
            $progressPercent = [int][Math]::Floor(
                ($reader.BaseStream.Position * 100.0) / $reader.BaseStream.Length
            )
            if ($progressPercent -ge $nextProgressPercent) {
                Write-Host (
                    "[PROGRESS] PCAP read {0}% complete; target packets buffered={1}" -f `
                        $nextProgressPercent,
                        $targetPackets.Count
                ) -ForegroundColor Cyan
                while ($nextProgressPercent -le $progressPercent) {
                    $nextProgressPercent += 10
                }
            }
        }
        $context.PacketOrderingPolicy = "timestamp-sorted-stable-v1"
        $context.TimestampOrderCorrectionApplied =
            [int64]$context.InterfaceTimestampRegressionCount -gt 0
        $context.SortableTargetPacketCount = $targetPackets.Count
        $orderedTargetPackets = @(
            $targetPackets |
                Sort-Object ObservedTicks, CaptureOrdinal
        )
        $processedPacketCount = 0
        $nextProcessingPercent = 10
        foreach ($targetPacket in $orderedTargetPackets) {
            Add-PacketToAnalysis `
                -ObservedAt $targetPacket.ObservedAt `
                -Context $context `
                -TargetServerPort $TargetServerPort `
                -InterfaceId ([int]$targetPacket.InterfaceId) `
                -PacketRecord $targetPacket.Packet `
                -CaptureOrdinal ([int64]$targetPacket.CaptureOrdinal) `
                -CaptureOrderAlreadyMeasured
            $processedPacketCount += 1
            $processingPercent = if ($orderedTargetPackets.Count -eq 0) {
                100
            } else {
                [int][Math]::Floor(
                    $processedPacketCount * 100.0 / $orderedTargetPackets.Count
                )
            }
            if ($processingPercent -ge $nextProcessingPercent) {
                Write-Host (
                    "[PROGRESS] Timestamp-ordered analysis {0}% complete; finalized events={1}; active flows={2}" -f `
                        $nextProcessingPercent,
                        $context.EventIndex,
                        $context.Flows.Count
                ) -ForegroundColor Cyan
                while ($nextProcessingPercent -le $processingPercent) {
                    $nextProcessingPercent += 10
                }
            }
        }
        foreach ($flow in @($context.Flows.Values)) {
            Complete-FlowAnalysis -Flow $flow -Context $context -Reason "capture_end"
        }
        Resolve-CaptureCoverage -Context $context
    } finally {
        $reader.Dispose()
        $writer.Dispose()
    }

    return Write-AnalysisSummary -Context $context -SummaryPath $SummaryPath
}

function Add-BigEndianUInt16 {
    param(
        [Collections.Generic.List[byte]]$Buffer,
        [int]$Value
    )
    $Buffer.Add([byte](($Value -shr 8) -band 0xFF))
    $Buffer.Add([byte]($Value -band 0xFF))
}

function Add-BigEndianUInt32 {
    param(
        [Collections.Generic.List[byte]]$Buffer,
        [uint32]$Value
    )
    $Buffer.Add([byte](($Value -shr 24) -band 0xFF))
    $Buffer.Add([byte](($Value -shr 16) -band 0xFF))
    $Buffer.Add([byte](($Value -shr 8) -band 0xFF))
    $Buffer.Add([byte]($Value -band 0xFF))
}

function New-SelfTestPacket {
    param(
        [bool]$Inbound,
        [uint32]$Sequence,
        [int]$Flags,
        [byte[]]$Payload,
        [int]$ClientPort = 50000
    )

    $sourcePort = if ($Inbound) { 80 } else { $ClientPort }
    $destinationPort = if ($Inbound) { $ClientPort } else { 80 }
    $sourceAddress = if ($Inbound) { [byte[]]@(192, 0, 2, 10) } else { [byte[]]@(198, 51, 100, 20) }
    $destinationAddress = if ($Inbound) { [byte[]]@(198, 51, 100, 20) } else { [byte[]]@(192, 0, 2, 10) }
    $bytes = [Collections.Generic.List[byte]]::new()
    for ($index = 0; $index -lt 12; $index += 1) {
        $bytes.Add(0)
    }
    Add-BigEndianUInt16 -Buffer $bytes -Value 0x0800
    $bytes.Add(0x45)
    $bytes.Add(0)
    Add-BigEndianUInt16 -Buffer $bytes -Value (40 + $Payload.Length)
    Add-BigEndianUInt16 -Buffer $bytes -Value 1
    Add-BigEndianUInt16 -Buffer $bytes -Value 0x4000
    $bytes.Add(64)
    $bytes.Add(6)
    Add-BigEndianUInt16 -Buffer $bytes -Value 0
    foreach ($value in $sourceAddress) {
        $bytes.Add([byte]$value)
    }
    foreach ($value in $destinationAddress) {
        $bytes.Add([byte]$value)
    }
    Add-BigEndianUInt16 -Buffer $bytes -Value $sourcePort
    Add-BigEndianUInt16 -Buffer $bytes -Value $destinationPort
    Add-BigEndianUInt32 -Buffer $bytes -Value $Sequence
    Add-BigEndianUInt32 -Buffer $bytes -Value 0
    $bytes.Add(0x50)
    $bytes.Add([byte]$Flags)
    Add-BigEndianUInt16 -Buffer $bytes -Value 65535
    Add-BigEndianUInt16 -Buffer $bytes -Value 0
    Add-BigEndianUInt16 -Buffer $bytes -Value 0
    if ($Payload.Length -gt 0) {
        foreach ($value in $Payload) {
            $bytes.Add([byte]$value)
        }
    }
    return [byte[]]$bytes.ToArray()
}

function Write-SelfTestRecord {
    param(
        [IO.StreamWriter]$Writer,
        [int]$Index,
        [string]$Time,
        [byte[]]$Bytes
    )

    $recordLine = "{0} PktGroupId {1}, PktNumber 1, OriginalSize {2}, LoggedSize {2}" -f `
        @($Time, $Index, $Bytes.Length)
    $Writer.WriteLine($recordLine)
    for ($offset = 0; $offset -lt $Bytes.Length; $offset += 16) {
        $count = [Math]::Min(16, $Bytes.Length - $offset)
        $groups = [Collections.Generic.List[string]]::new()
        for ($index = 0; $index -lt $count; $index += 2) {
            if ($index + 1 -lt $count) {
                $word = "{0:x2}{1:x2}" -f @(
                    $Bytes[$offset + $index],
                    $Bytes[$offset + $index + 1]
                )
                $groups.Add($word)
            } else {
                $groups.Add(("{0:x2}00" -f $Bytes[$offset + $index]))
            }
        }
        $hexLine = "`t0x{0:x4}:  {1}" -f @($offset, ($groups -join ' '))
        $Writer.WriteLine($hexLine)
    }
}

function Write-SelfTestPcapng {
    param(
        [string]$Path,
        [object[]]$Packets
    )

    $stream = [IO.File]::Open($Path, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $writer = [IO.BinaryWriter]::new($stream)
    try {
        $writer.Write([uint32]0x0A0D0D0A)
        $writer.Write([uint32]28)
        $writer.Write([uint32]0x1A2B3C4D)
        $writer.Write([uint16]1)
        $writer.Write([uint16]0)
        $writer.Write([int64]-1)
        $writer.Write([uint32]28)

        $maximumInterfaceId = 0
        foreach ($packet in $Packets) {
            $property = $packet.PSObject.Properties['InterfaceId']
            if ($null -ne $property) {
                $maximumInterfaceId = [Math]::Max(
                    $maximumInterfaceId,
                    [int]$property.Value
                )
            }
        }
        for ($interfaceId = 0; $interfaceId -le $maximumInterfaceId; $interfaceId += 1) {
            $writer.Write([uint32]1)
            $writer.Write([uint32]20)
            $writer.Write([uint16]1)
            $writer.Write([uint16]0)
            $writer.Write([uint32]512)
            $writer.Write([uint32]20)
        }

        $timestamp = [uint64]1784696400000000
        foreach ($packet in $Packets) {
            $bytes = [byte[]]$packet.Bytes
            $padding = (4 - ($bytes.Length % 4)) % 4
            $blockLength = [uint32](32 + $bytes.Length + $padding)
            $writer.Write([uint32]6)
            $writer.Write($blockLength)
            $interfaceProperty = $packet.PSObject.Properties['InterfaceId']
            $packetInterfaceId = if ($null -eq $interfaceProperty) {
                0
            } else {
                [int]$interfaceProperty.Value
            }
            $writer.Write([uint32]$packetInterfaceId)
            $timestampProperty = $packet.PSObject.Properties['TimestampMicroseconds']
            if ($null -ne $timestampProperty) {
                $timestamp = [uint64]$timestampProperty.Value
            }
            $timestampHigh = [uint32][Math]::Floor([decimal]$timestamp / [decimal]4294967296)
            $timestampLow = [uint32]($timestamp % [uint64]4294967296)
            $writer.Write($timestampHigh)
            $writer.Write($timestampLow)
            $writer.Write([uint32]$bytes.Length)
            $writer.Write([uint32]$bytes.Length)
            $writer.Write($bytes)
            for ($index = 0; $index -lt $padding; $index += 1) {
                $writer.Write([byte]0)
            }
            $writer.Write($blockLength)
            $timestamp += 1000
        }
    } finally {
        $writer.Dispose()
    }
}

function Invoke-SelfTest {
    $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $tempRoot = Join-Path $tempBase ("sfl-framing-selftest-{0}" -f [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    try {
        $input = Join-Path $tempRoot "fixture.txt"
        $events = Join-Path $tempRoot "events.jsonl"
        $summary = Join-Path $tempRoot "summary.json"
        $pcapInput = Join-Path $tempRoot "fixture.pcapng"
        $pcapEvents = Join-Path $tempRoot "pcap_events.jsonl"
        $pcapSummary = Join-Path $tempRoot "pcap_summary.json"
        $overwritePcapInput = Join-Path $tempRoot "overwrite_fixture.pcapng"
        $overwritePcapEvents = Join-Path $tempRoot "overwrite_events.jsonl"
        $overwritePcapSummary = Join-Path $tempRoot "overwrite_summary.json"
        $measurementPcapInput = Join-Path $tempRoot "measurement_fixture.pcapng"
        $measurementPcapEvents = Join-Path $tempRoot "measurement_events.jsonl"
        $measurementPcapSummary = Join-Path $tempRoot "measurement_summary.json"
        $orderSensitivePcapInput = Join-Path $tempRoot "order_sensitive_fixture.pcapng"
        $orderSensitivePcapEvents = Join-Path $tempRoot "order_sensitive_events.jsonl"
        $orderSensitivePcapSummary = Join-Path $tempRoot "order_sensitive_summary.json"
        $clockCalibration = Join-Path $tempRoot "clock_calibration.jsonl"
        $request = [Text.Encoding]::ASCII.GetBytes("GET /image.jpg HTTP/1.1`r`n`r`n")
        $response = [Text.Encoding]::ASCII.GetBytes("HTTP/1.0 200 OK`r`nContent-Length: 4`r`n`r`ndata")
        $packets = @(
            [pscustomobject]@{
                Time = "10:00:00.000000000"
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 1000 -Flags 0x02 -Payload ([byte[]]@())
            },
            [pscustomobject]@{
                Time = "10:00:00.001000000"
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 1000 -Flags 0x02 -Payload ([byte[]]@())
            },
            [pscustomobject]@{
                Time = "10:00:00.002000000"
                Bytes = New-SelfTestPacket -Inbound $true -Sequence 4000 -Flags 0x12 -Payload ([byte[]]@())
            },
            [pscustomobject]@{
                Time = "10:00:00.003000000"
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 1001 -Flags 0x10 -Payload ([byte[]]@())
            },
            [pscustomobject]@{
                Time = "10:00:00.004000000"
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 1001 -Flags 0x18 -Payload $request
            },
            [pscustomobject]@{
                Time = "10:00:00.005000000"
                Bytes = New-SelfTestPacket -Inbound $true -Sequence 5000 -Flags 0x18 -Payload $response
            },
            [pscustomobject]@{
                Time = "10:00:00.004500000"
                Bytes = New-SelfTestPacket `
                    -Inbound $true `
                    -Sequence ([uint32](5000 + $response.Length)) `
                    -Flags 0x04 `
                    -Payload ([byte[]]@())
            },
            [pscustomobject]@{
                Time = "10:00:00.006000000"
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 7000 `
                    -Flags 0x02 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50001
            },
            [pscustomobject]@{
                Time = "10:00:00.007000000"
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 8000 `
                    -Flags 0x02 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50002
            },
            [pscustomobject]@{
                Time = "10:00:00.008000000"
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 8000 `
                    -Flags 0x02 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50002
            },
            [pscustomobject]@{
                Time = "10:00:00.009000000"
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 9000 `
                    -Flags 0x02 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50003
            },
            [pscustomobject]@{
                Time = "10:00:00.010000000"
                Bytes = New-SelfTestPacket `
                    -Inbound $true `
                    -Sequence 12000 `
                    -Flags 0x12 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50003
            },
            [pscustomobject]@{
                Time = "10:00:00.011000000"
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 9001 `
                    -Flags 0x18 `
                    -Payload $request `
                    -ClientPort 50003
            },
            [pscustomobject]@{
                Time = "10:00:00.012000000"
                Bytes = New-SelfTestPacket `
                    -Inbound $true `
                    -Sequence 12001 `
                    -Flags 0x04 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50003
            },
            [pscustomobject]@{
                Time = "10:00:00.012100000"
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 14000 `
                    -Flags 0x02 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50006
            },
            [pscustomobject]@{
                Time = "10:00:00.012200000"
                Bytes = New-SelfTestPacket `
                    -Inbound $true `
                    -Sequence 15000 `
                    -Flags 0x12 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50006
            },
            [pscustomobject]@{
                Time = "10:00:00.012300000"
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 14001 `
                    -Flags 0x10 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50006
            },
            [pscustomobject]@{
                Time = "10:00:00.012400000"
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 16000 `
                    -Flags 0x02 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50006
            },
            [pscustomobject]@{
                Time = "10:00:00.013000000"
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 7100 `
                    -Flags 0x02 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50001
            },
            [pscustomobject]@{
                Time = "10:00:00.014000000"
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 7101 `
                    -Flags 0x04 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50001
            },
            [pscustomobject]@{
                Time = "10:00:00.015000000"
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 13000 `
                    -Flags 0x02 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50005
            }
        )
        $writer = [IO.StreamWriter]::new($input, $false, [Text.UTF8Encoding]::new($false))
        try {
            for ($index = 0; $index -lt $packets.Count; $index += 1) {
                Write-SelfTestRecord `
                    -Writer $writer `
                    -Index ($index + 1) `
                    -Time $packets[$index].Time `
                    -Bytes ([byte[]]$packets[$index].Bytes)
            }
        } finally {
            $writer.Dispose()
        }
        Write-SelfTestPcapng -Path $pcapInput -Packets $packets

        $result = Convert-PktmonHexEvidence `
            -SourcePath $input `
            -EventPath $events `
            -SummaryPath $summary `
            -StartedAt ([DateTimeOffset]"2026-07-23T10:00:00+09:00") `
            -TargetServerPort 80
        if ($result.events_total -ne 1 -or $result.header_complete -ne 1) {
            throw "Self-test failed: event/header counts."
        }
        if ($result.schema_version -ne "spot-http-framing-evidence-v10" -or
            $result.tcp_connection_summary.connection_attempts_total -ne 8 -or
            $result.tcp_connection_summary.syn_packets_total -ne 10 -or
            $result.tcp_connection_summary.syn_retransmissions_total -ne 2 -or
            $result.tcp_connection_summary.syn_ack_packets_total -ne 3 -or
            $result.tcp_connection_summary.handshake_completed_attempts -ne 3 -or
            $result.tcp_connection_summary.failed_connection_attempts -ne 3 -or
            $result.tcp_connection_summary.pre_handshake_failed_attempts -ne 3 -or
            $result.tcp_connection_summary.pre_handshake_failure_attribution -cne
                "packet-only-not-product-attributable" -or
            $result.tcp_connection_summary.pre_handshake_failure_corroboration_policy -cne
                "requires-observation-window-app-failure-counter-or-event-delta" -or
            $result.tcp_connection_summary.no_response_after_handshake_attempts -ne 1 -or
            $result.tcp_connection_summary.no_response_definition -cne
                "handshake-complete-with-outbound-request-payload-and-no-response" -or
            $result.tcp_connection_summary.request_no_response_after_handshake_attempts -ne 1 -or
            $result.tcp_connection_summary.handshake_only_without_request_attempts -ne 1 -or
            $result.tcp_connection_summary.unresolved_after_handshake_at_capture_end -ne 0 -or
            $result.tcp_connection_summary.unresolved_attempts_at_capture_end -ne 2 -or
            $result.tcp_connection_summary.reset_before_response_attempts -ne 2) {
            throw (
                "Self-test failed: TCP connection summary. " +
                ($result.tcp_connection_summary | ConvertTo-Json -Compress -Depth 5)
            )
        }
        $requestResetIssue = @(
            $result.connect_issue_events |
                Where-Object {
                    $_.outcome -eq "request_no_response_after_handshake"
                }
        )
        $handshakeOnly = @(
            $result.connect_issue_events |
                Where-Object {
                    $_.outcome -eq "handshake_only_without_request"
                }
        )
        $completionReasons = $result.tcp_connection_summary.connect_issue_completion_reason_counts
        $reuse = $result.tcp_connection_summary.same_four_tuple_reuse.duplicate_removed
        if ($result.connect_issue_events.Count -ne 7 -or
            @($result.connect_issue_events | Where-Object { $_.outcome -eq "failed" }).Count -ne 3 -or
            @($result.connect_issue_events | Where-Object {
                $_.outcome -eq "unresolved_capture_end"
            }).Count -ne 2 -or
            $requestResetIssue.Count -ne 1 -or
            $handshakeOnly.Count -ne 1 -or
            $handshakeOnly[0].request_kind -ne "unknown" -or
            [bool]$handshakeOnly[0].outbound_request_payload_observed -or
            [bool]$handshakeOnly[0].inbound_response_payload_observed -or
            $handshakeOnly[0].completion_reason -ne "source-port-reused" -or
            $requestResetIssue[0].request_kind -ne "image" -or
            -not [bool]$requestResetIssue[0].outbound_request_payload_observed -or
            [bool]$requestResetIssue[0].inbound_response_payload_observed -or
            $requestResetIssue[0].server_close_kind -ne "reset" -or
            $requestResetIssue[0].client_close_kind -ne "not_observed" -or
            [int]$completionReasons.'source-port-reused' -ne 2 -or
            [int]$completionReasons.'client-reset' -ne 1 -or
            [int]$completionReasons.'server-reset' -ne 1 -or
            [int]$completionReasons.'capture-end' -ne 3 -or
            [int]$reuse.observed_count -ne 2 -or
            [double]$reuse.interval_ms_min -ne 0.3 -or
            [double]$reuse.interval_ms_max -ne 7 -or
            [int]$reuse.under_1000_ms_count -ne 2) {
            throw (
                "Self-test failed: TCP connection issue events. summary={0} events={1}" -f
                    ($result.tcp_connection_summary | ConvertTo-Json -Compress -Depth 8),
                    ($result.connect_issue_events | ConvertTo-Json -Compress -Depth 8)
            )
        }
        $pcapResult = Convert-PcapngEvidence `
            -SourcePath $pcapInput `
            -EventPath $pcapEvents `
            -SummaryPath $pcapSummary `
            -StartedAt ([DateTimeOffset]"2026-07-23T10:00:00+09:00") `
            -TargetServerPort 80
        if ($pcapResult.events_total -ne 1 -or $pcapResult.header_complete -ne 1) {
            throw "Self-test failed: pcapng event/header counts."
        }
        if ($pcapResult.schema_version -ne "spot-http-framing-evidence-v10" -or
            $pcapResult.tcp_connection_summary.connection_attempts_total -ne 8 -or
            $pcapResult.tcp_connection_summary.syn_retransmissions_total -ne 2 -or
            $pcapResult.tcp_connection_summary.failed_connection_attempts -ne 3 -or
            $pcapResult.tcp_connection_summary.pre_handshake_failed_attempts -ne 3 -or
            $pcapResult.tcp_connection_summary.request_no_response_after_handshake_attempts -ne 1 -or
            $pcapResult.tcp_connection_summary.handshake_only_without_request_attempts -ne 1 -or
            $pcapResult.tcp_connection_summary.unresolved_attempts_at_capture_end -ne 2 -or
            [int]$pcapResult.tcp_connection_summary.same_four_tuple_reuse.duplicate_removed.observed_count -ne 2) {
            throw "Self-test failed: pcapng TCP connection summary."
        }

        $measurementBaseMicros = [uint64]1784696400000000
        $measurementPackets = @(
            [pscustomobject]@{
                TimestampMicroseconds = $measurementBaseMicros - 1000000
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 1 -Flags 0x02 `
                    -Payload ([byte[]]@()) -ClientPort 50100
            },
            [pscustomobject]@{
                TimestampMicroseconds = $measurementBaseMicros
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 100 -Flags 0x02 `
                    -Payload ([byte[]]@()) -ClientPort 50100
            },
            [pscustomobject]@{
                TimestampMicroseconds = $measurementBaseMicros
                InterfaceId = 1
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 100 -Flags 0x02 `
                    -Payload ([byte[]]@()) -ClientPort 50100
            },
            [pscustomobject]@{
                TimestampMicroseconds = $measurementBaseMicros + 149011000
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 200 -Flags 0x02 `
                    -Payload ([byte[]]@()) -ClientPort 50100
            },
            [pscustomobject]@{
                TimestampMicroseconds = $measurementBaseMicros + 74011000
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 300 -Flags 0x02 `
                    -Payload ([byte[]]@()) -ClientPort 50100
            },
            [pscustomobject]@{
                TimestampMicroseconds = $measurementBaseMicros + 149000000
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 301 -Flags 0x04 `
                    -Payload ([byte[]]@()) -ClientPort 50100
            },
            [pscustomobject]@{
                TimestampMicroseconds = $measurementBaseMicros + 149020000
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $true -Sequence 900 -Flags 0x04 `
                    -Payload ([byte[]]@()) -ClientPort 50100
            },
            [pscustomobject]@{
                TimestampMicroseconds = $measurementBaseMicros + 151000000
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 400 -Flags 0x02 `
                    -Payload ([byte[]]@()) -ClientPort 50100
            }
        )
        Write-SelfTestPcapng -Path $measurementPcapInput -Packets $measurementPackets
        $measurementWallStart = [DateTimeOffset]::FromUnixTimeSeconds(1784696400)
        @(
            [ordered]@{
                schema_version = 'spot-canary-clock-anchor-v1'
                wall_clock_at = $measurementWallStart.ToString('o')
                monotonic_ticks = 0
                monotonic_frequency = 10000000
            },
            [ordered]@{
                schema_version = 'spot-canary-clock-anchor-v1'
                wall_clock_at = $measurementWallStart.AddSeconds(150).ToString('o')
                monotonic_ticks = 1522500000
                monotonic_frequency = 10000000
            }
        ) | ForEach-Object {
            $_ | ConvertTo-Json -Compress | Add-Content -LiteralPath $clockCalibration -Encoding utf8
        }
        $measurementResult = Convert-PcapngEvidence `
            -SourcePath $measurementPcapInput `
            -EventPath $measurementPcapEvents `
            -SummaryPath $measurementPcapSummary `
            -StartedAt $measurementWallStart `
            -EndedAt $measurementWallStart.AddSeconds(151) `
            -WindowStartedAt $measurementWallStart `
            -WindowEndedAt $measurementWallStart.AddSeconds(150) `
            -CalibrationPath $clockCalibration `
            -TargetServerPort 80
        $measurement = $measurementResult.packet_measurement
        $measurementReuse = $measurementResult.tcp_connection_summary.same_four_tuple_reuse
        if ($measurement.interface_count -ne 2 -or
            $measurement.duplicate_packet_count -ne 1 -or
            $measurement.duplicate_initial_syn_count -ne 1 -or
            $measurement.timestamp_regression_count -ne 1 -or
            [double]$measurement.timestamp_regression_max_ms -ne 75000 -or
            $measurement.initial_syn_timestamp_regression_count -ne 1 -or
            [double]$measurement.initial_syn_timestamp_regression_max_ms -ne 75000 -or
            -not [bool]$measurement.timestamp_order_correction_applied -or
            $measurement.sortable_target_packet_count -ne 6 -or
            $measurement.sortable_target_packet_limit -ne 1000000 -or
            $measurement.client_to_server_rst_count -ne 1 -or
            $measurement.server_to_client_rst_count -ne 1 -or
            $measurementResult.analysis_window.excluded_before_count -ne 1 -or
            $measurementResult.analysis_window.excluded_after_count -ne 1 -or
            $measurement.clock_calibration.status -ne 'complete' -or
            [double]$measurementReuse.original.interval_ms_min -ne 0 -or
            $measurementReuse.ordering_policy -cne
                'timestamp-sorted-per-four-tuple-v1' -or
            $measurementReuse.measurement_integrity_status -cne 'complete' -or
            [double]$measurementReuse.duplicate_removed.interval_ms_min -ne 74011 -or
            [double]$measurementReuse.monotonic_corrected.interval_ms_min -lt 75000) {
            throw (
                'Self-test failed: measurement correction contract. ' +
                ($measurementResult | ConvertTo-Json -Compress -Depth 8)
            )
        }

        $orderSensitiveBaseMicros = [uint64]1788247800000000
        $orderSensitivePackets = @(
            [pscustomobject]@{
                TimestampMicroseconds = $orderSensitiveBaseMicros + 1000000
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 1000 `
                    -Flags 0x02 -Payload ([byte[]]@()) -ClientPort 50110
            },
            [pscustomobject]@{
                TimestampMicroseconds = $orderSensitiveBaseMicros + 1001000
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $true -Sequence 4000 `
                    -Flags 0x12 -Payload ([byte[]]@()) -ClientPort 50110
            },
            [pscustomobject]@{
                TimestampMicroseconds = $orderSensitiveBaseMicros + 1002000
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 1001 `
                    -Flags 0x10 -Payload ([byte[]]@()) -ClientPort 50110
            },
            [pscustomobject]@{
                TimestampMicroseconds = $orderSensitiveBaseMicros + 1003000
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 1001 `
                    -Flags 0x18 -Payload $request -ClientPort 50110
            },
            [pscustomobject]@{
                TimestampMicroseconds = $orderSensitiveBaseMicros + 500000
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $true -Sequence 4001 `
                    -Flags 0x18 -Payload $response -ClientPort 50110
            },
            [pscustomobject]@{
                TimestampMicroseconds = $orderSensitiveBaseMicros + 78000000
                InterfaceId = 0
                Bytes = New-SelfTestPacket -Inbound $false -Sequence 9000 `
                    -Flags 0x02 -Payload ([byte[]]@()) -ClientPort 50110
            }
        )
        Write-SelfTestPcapng `
            -Path $orderSensitivePcapInput `
            -Packets $orderSensitivePackets
        $orderSensitiveStart = [DateTimeOffset]::FromUnixTimeSeconds(1788247800)
        $orderSensitiveResult = Convert-PcapngEvidence `
            -SourcePath $orderSensitivePcapInput `
            -EventPath $orderSensitivePcapEvents `
            -SummaryPath $orderSensitivePcapSummary `
            -StartedAt $orderSensitiveStart `
            -EndedAt $orderSensitiveStart.AddSeconds(80) `
            -TargetServerPort 80
        $orderSensitiveIssues = @(
            $orderSensitiveResult.connect_issue_events |
                Where-Object {
                    $_.outcome -eq
                        "packet_order_sensitive_no_response_unresolved"
                }
        )
        if ($orderSensitiveResult.schema_version -ne
                "spot-http-framing-evidence-v10" -or
            [int]$orderSensitiveResult.packet_measurement.timestamp_regression_count -ne
                1 -or
            [int]$orderSensitiveResult.packet_measurement.timestamp_order_sensitive_response_candidates -ne
                1 -or
            [int]$orderSensitiveResult.tcp_connection_summary.request_no_response_after_handshake_attempts -ne
                0 -or
            [int]$orderSensitiveResult.tcp_connection_summary.packet_order_sensitive_no_response_attempts -ne
                1 -or
            $orderSensitiveResult.tcp_connection_summary.packet_order_sensitive_no_response_policy -cne
                "timestamp-and-capture-order-disagreement-is-evidence-hold" -or
            $orderSensitiveIssues.Count -ne 1 -or
            -not [bool]$orderSensitiveIssues[0].packet_order_sensitive_response_candidate -or
            [int64]$orderSensitiveIssues[0].response_candidate_capture_ordinal_delta -ne
                4 -or
            [double]$orderSensitiveIssues[0].response_candidate_timestamp_lead_ms -ne
                500) {
            throw (
                "Self-test failed: packet-order-sensitive response hold. " +
                ($orderSensitiveResult | ConvertTo-Json -Compress -Depth 8)
            )
        }

        $overwritePrefixPackets = @(
            [pscustomobject]@{
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 9000 `
                    -Flags 0x02 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50004
            },
            [pscustomobject]@{
                Bytes = New-SelfTestPacket `
                    -Inbound $false `
                    -Sequence 9000 `
                    -Flags 0x02 `
                    -Payload ([byte[]]@()) `
                    -ClientPort 50004
            }
        )
        $overwritePackets = @($overwritePrefixPackets + $packets)
        Write-SelfTestPcapng -Path $overwritePcapInput -Packets $overwritePackets
        $overwriteResult = Convert-PcapngEvidence `
            -SourcePath $overwritePcapInput `
            -EventPath $overwritePcapEvents `
            -SummaryPath $overwritePcapSummary `
            -StartedAt ([DateTimeOffset]"2026-07-22T13:50:00+09:00") `
            -EndedAt ([DateTimeOffset]"2026-07-22T14:00:30+09:00") `
            -FileSizeBytes 1MB `
            -CircularMaxFileSizeMB 1 `
            -TargetServerPort 80
        if (-not [bool]$overwriteResult.capture_coverage.overwrite_detected -or
            $overwriteResult.capture_coverage.status -ne "capture-overwrite-detected" -or
            $overwriteResult.tcp_connection_summary.capture_overwrite_unresolved_attempts -ne 1 -or
            $overwriteResult.tcp_connection_summary.failed_connection_attempts -ne 3 -or
            @($overwriteResult.connect_issue_events | Where-Object {
                $_.outcome -eq "capture-overwrite-unresolved"
            }).Count -ne 1) {
            throw (
                "Self-test failed: circular capture overwrite classification. " +
                ($overwriteResult.tcp_connection_summary |
                    ConvertTo-Json -Compress -Depth 5)
            )
        }
        $event = Get-Content -LiteralPath $events -Encoding utf8 | ConvertFrom-Json
        $pcapEvent = Get-Content -LiteralPath $pcapEvents -Encoding utf8 | ConvertFrom-Json
        if ($event.request_kind -ne "image" -or
            $event.http_version -ne "HTTP/1.0" -or
            -not $event.content_length_present -or
            $event.transfer_encoding -ne "none" -or
            $event.body_complete -ne "true" -or
            $event.server_close_kind -ne "reset" -or
            [DateTimeOffset]$event.last_observed_at_local -lt
                [DateTimeOffset]$event.response_started_at_local) {
            throw "Self-test failed: framing classification."
        }
        foreach ($property in @(
            "request_kind",
            "http_version",
            "status_code",
            "content_length_present",
            "transfer_encoding",
            "body_complete",
            "server_close_kind"
        )) {
            if ($pcapEvent.$property -ne $event.$property) {
                throw "Self-test failed: pcapng and text classification differ."
            }
        }
        $serialized = (Get-Content -LiteralPath $events -Raw -Encoding utf8) +
            (Get-Content -LiteralPath $summary -Raw -Encoding utf8) +
            (Get-Content -LiteralPath $pcapEvents -Raw -Encoding utf8) +
            (Get-Content -LiteralPath $pcapSummary -Raw -Encoding utf8)
        foreach ($forbidden in @(
            "/image.jpg",
            "192.0.2.10",
            "198.51.100.20",
            "data",
            '"port"',
            '_port"',
            '"payload"',
            '"headers"'
        )) {
            if ($serialized -match [regex]::Escape($forbidden)) {
                throw "Self-test failed: sensitive packet value was retained."
            }
        }
        Write-Output (
            "SELF_TEST_PASS formats=2 events=1 overwrite_classification=true " +
            "packet_order_sensitive_hold=true payload_retained=false"
        )
    } finally {
        $resolvedTempRoot = [IO.Path]::GetFullPath($tempRoot)
        if (-not $resolvedTempRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Unsafe self-test cleanup path."
        }
        Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force
    }
}

if ($SelfTest) {
    Invoke-SelfTest
    exit 0
}

if ([string]::IsNullOrWhiteSpace($InputPath) -or
    [string]::IsNullOrWhiteSpace($EventsOutputPath) -or
    [string]::IsNullOrWhiteSpace($SummaryOutputPath)) {
    throw "InputPath, EventsOutputPath, and SummaryOutputPath are required."
}

$result = if ([IO.Path]::GetExtension($InputPath) -ieq ".pcapng") {
    Convert-PcapngEvidence `
        -SourcePath $InputPath `
        -EventPath $EventsOutputPath `
        -SummaryPath $SummaryOutputPath `
        -StartedAt $CaptureStartedAt `
        -EndedAt $CaptureEndedAt `
        -WindowStartedAt $AnalysisWindowStartedAt `
        -WindowEndedAt $AnalysisWindowEndedAt `
        -CalibrationPath $ClockCalibrationPath `
        -FileSizeBytes $CaptureFileSizeBytes `
        -CircularMaxFileSizeMB $CircularCaptureMaxFileSizeMB `
        -TargetServerPort $ServerPort
} else {
    Convert-PktmonHexEvidence `
        -SourcePath $InputPath `
        -EventPath $EventsOutputPath `
        -SummaryPath $SummaryOutputPath `
        -StartedAt $CaptureStartedAt `
        -EndedAt $CaptureEndedAt `
        -WindowStartedAt $AnalysisWindowStartedAt `
        -WindowEndedAt $AnalysisWindowEndedAt `
        -CalibrationPath $ClockCalibrationPath `
        -FileSizeBytes $CaptureFileSizeBytes `
        -CircularMaxFileSizeMB $CircularCaptureMaxFileSizeMB `
        -TargetServerPort $ServerPort
}
Write-Output (
    "FRAMING_ANALYSIS_PASS events={0} header_complete={1} header_incomplete={2} coverage={3} overwrite={4} payload_retained=false" -f `
        $result.events_total,
        $result.header_complete,
        $result.header_incomplete,
        $result.capture_coverage.status,
        $result.capture_coverage.overwrite_detected
)
