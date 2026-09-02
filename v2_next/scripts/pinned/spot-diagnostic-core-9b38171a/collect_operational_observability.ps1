param(
  [string]$ApiBase = "http://127.0.0.1:8000",
  [int]$Samples = 60,
  [ValidateRange(0, 10800)]
  [int]$DurationSec = 0,
  [int]$IntervalSec = 60,
  [ValidateRange(1, 3600)]
  [int]$MemoryStateIntervalSec = 30,
  [ValidateRange(1, 3600)]
  [int]$MemoryDetailsIntervalSec = 60,
  [int]$TimeoutSec = 10,
  [string]$OutputRoot = ".\.tmp_operational_observability",
  [ValidateRange(1, 60)]
  [int]$NormalEndpointIntervalSec = 5,
  [switch]$StopOnNewSpotConnectTimeout,
  [string]$CaptureStopSignalPath = "",
  [string]$TriggerMonitorPath = "",
  [ValidateRange(1, 600000)]
  [int]$DetectionLatencyWarningMs = 5000,
  [switch]$SelfTest
)

$ErrorActionPreference = "Stop"

function Join-ApiUrl {
  param(
    [string]$Base,
    [string]$Path
  )

  $normalizedBase = $Base.TrimEnd("/")
  if ($Path.StartsWith("/")) {
    return "$normalizedBase$Path"
  }
  return "$normalizedBase/$Path"
}

function Read-ResponseBody {
  param([object]$Response)

  if ($null -eq $Response) {
    return ""
  }

  try {
    $stream = $Response.GetResponseStream()
    if ($null -eq $stream) {
      return ""
    }
    $reader = [System.IO.StreamReader]::new($stream)
    try {
      return $reader.ReadToEnd()
    } finally {
      $reader.Dispose()
      $stream.Dispose()
    }
  } catch {
    return ""
  }
}

function Invoke-ReadOnlyEndpoint {
  param(
    [string]$Uri,
    [int]$Timeout
  )

  try {
    $response = Invoke-WebRequest -Uri $Uri -Method Get -TimeoutSec $Timeout -UseBasicParsing
    return [ordered]@{
      ok = $true
      status_code = [int]$response.StatusCode
      body = [string]$response.Content
      error = $null
    }
  } catch {
    $statusCode = 0
    $body = ""
    if ($_.Exception.Response) {
      try {
        $statusCode = [int]$_.Exception.Response.StatusCode
      } catch {
        $statusCode = 0
      }
      $body = Read-ResponseBody -Response $_.Exception.Response
    }
    return [ordered]@{
      ok = $false
      status_code = $statusCode
      body = $body
      error = $_.Exception.GetType().Name
    }
  }
}

function ConvertFrom-JsonOrNull {
  param([string]$Text)

  if ([string]::IsNullOrWhiteSpace($Text)) {
    return $null
  }
  try {
    return $Text | ConvertFrom-Json
  } catch {
    return $null
  }
}

function Get-PropertyValue {
  param(
    [object]$Object,
    [string]$Name
  )

  if ($null -eq $Object) {
    return $null
  }
  if ($Object -is [System.Collections.IDictionary]) {
    if ($Object.Contains($Name)) {
      return $Object[$Name]
    }
    return $null
  }
  $property = $Object.PSObject.Properties[$Name]
  if ($null -eq $property) {
    return $null
  }
  return $property.Value
}

function Get-PositiveRepeatCount {
  param([object]$Value)

  $repeat = 1
  if ($null -ne $Value) {
    try {
      $repeat = [int]$Value
    } catch {
      $repeat = 1
    }
  }
  return [Math]::Max(1, $repeat)
}

function Get-SpotConnectTimeoutTriggerState {
  param([object]$Body)

  $itemCount = 0
  $repeatTotal = 0
  $latestErrorAt = $null
  foreach ($item in @((Get-PropertyValue -Object $Body -Name "items"))) {
    if ($null -eq $item) {
      continue
    }
    $source = [string](Get-PropertyValue -Object $item -Name "source")
    $errorType = [string](Get-PropertyValue -Object $item -Name "error_type")
    if ($source -cne "spot_image" -or $errorType -cne "ConnectTimeout") {
      continue
    }

    $itemCount += 1
    $repeatTotal += Get-PositiveRepeatCount -Value (
      Get-PropertyValue -Object $item -Name "repeat"
    )
    $timeText = [string](Get-PropertyValue -Object $item -Name "time_iso")
    $parsedTime = [DateTimeOffset]::MinValue
    if ([DateTimeOffset]::TryParse($timeText, [ref]$parsedTime)) {
      if ($null -eq $latestErrorAt -or $parsedTime -gt $latestErrorAt) {
        $latestErrorAt = $parsedTime
      }
    }
  }

  return [pscustomobject]@{
    ItemCount = $itemCount
    RepeatTotal = $repeatTotal
    LatestErrorAt = $latestErrorAt
  }
}

function ConvertTo-CompactErrorPollRecord {
  param(
    [object]$Envelope,
    [object]$Body,
    [object]$TriggerState,
    [string]$BodySha256
  )

  $summary = Get-PropertyValue -Object $Body -Name "summary"
  return [ordered]@{
    schema_version = "observability-error-poll-compact-v1"
    sample = [int](Get-PropertyValue -Object $Envelope -Name "sample")
    collected_at = Get-PropertyValue -Object $Envelope -Name "collected_at"
    response_status = Get-PropertyValue -Object $Envelope -Name "status_code"
    ok = [bool](Get-PropertyValue -Object $Envelope -Name "ok")
    error = Get-PropertyValue -Object $Envelope -Name "error"
    body_sha256 = $BodySha256
    queue_size = Get-PropertyValue -Object $summary -Name "queue_size"
    repeat_total = Get-PropertyValue -Object $summary -Name "repeat_total"
    spot_connecttimeout_item_count = if ($null -eq $TriggerState) {
      $null
    } else {
      [int]$TriggerState.ItemCount
    }
    spot_connecttimeout_repeat_total = if ($null -eq $TriggerState) {
      $null
    } else {
      [int]$TriggerState.RepeatTotal
    }
    spot_connecttimeout_latest_error_at = if ($null -eq $TriggerState -or
      $null -eq $TriggerState.LatestErrorAt) {
      $null
    } else {
      $TriggerState.LatestErrorAt.ToString("o")
    }
  }
}

function Test-ShouldPersistErrorSnapshot {
  param(
    [bool]$ResponseOk,
    [string]$BodySha256,
    [string]$LastPersistedBodySha256
  )

  return (
    $ResponseOk -and
    -not [string]::IsNullOrWhiteSpace($BodySha256) -and
    $BodySha256 -cne $LastPersistedBodySha256
  )
}

function Test-NewSpotConnectTimeout {
  param(
    [object]$Baseline,
    [object]$Current
  )

  if ($null -eq $Baseline -or $null -eq $Current) {
    return $false
  }
  if ([int]$Current.RepeatTotal -gt [int]$Baseline.RepeatTotal) {
    return $true
  }
  if ([int]$Current.ItemCount -gt [int]$Baseline.ItemCount) {
    return $true
  }
  if ($null -ne $Current.LatestErrorAt -and
      ($null -eq $Baseline.LatestErrorAt -or
       $Current.LatestErrorAt -gt $Baseline.LatestErrorAt)) {
    return $true
  }
  return $false
}

function Write-CaptureStopSignal {
  param(
    [string]$Path,
    [string]$StopReason,
    [bool]$TriggerDetected,
    [object]$Baseline,
    [object]$Current,
    [object]$TriggerDetectedAt,
    [datetime]$CollectionEndedAt
  )

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return
  }
  $fullPath = [IO.Path]::GetFullPath($Path)
  $parent = Split-Path -Parent $fullPath
  if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw "The capture stop signal parent folder does not exist."
  }
  if (Test-Path -LiteralPath $fullPath) {
    throw "The capture stop signal path already exists."
  }

  $detectedAt = if ($null -eq $TriggerDetectedAt) {
    $null
  } else {
    [DateTimeOffset]$TriggerDetectedAt
  }
  $baselineErrorAt = if ($null -eq $Baseline) {
    $null
  } else {
    $Baseline.LatestErrorAt
  }
  $errorAt = if ($null -eq $Current -or
    $null -eq $Current.LatestErrorAt -or
    ($null -ne $baselineErrorAt -and
      $Current.LatestErrorAt -le $baselineErrorAt)) {
    $null
  } else {
    [DateTimeOffset]$Current.LatestErrorAt
  }
  $detectionLatencyMs = if ($null -eq $detectedAt -or $null -eq $errorAt) {
    $null
  } else {
    [Math]::Max(0, [Math]::Round(($detectedAt - $errorAt).TotalMilliseconds, 1))
  }
  $baselineRepeat = if ($null -eq $Baseline) { 0 } else { [int]$Baseline.RepeatTotal }
  $currentRepeat = if ($null -eq $Current) { $baselineRepeat } else { [int]$Current.RepeatTotal }
  $signal = [ordered]@{
    schema_version = "spot-connecttimeout-capture-stop-v1"
    stop_reason = $StopReason
    trigger_detected = $TriggerDetected
    trigger_source = if ($TriggerDetected) { "spot_image" } else { $null }
    trigger_error_type = if ($TriggerDetected) { "ConnectTimeout" } else { $null }
    trigger_detected_at = if ($null -eq $detectedAt) { $null } else { $detectedAt.ToString("o") }
    trigger_error_at = if ($null -eq $errorAt) { $null } else { $errorAt.ToString("o") }
    trigger_detection_latency_ms = $detectionLatencyMs
    baseline_repeat_total = $baselineRepeat
    observed_repeat_total = $currentRepeat
    repeat_delta = [Math]::Max(0, $currentRepeat - $baselineRepeat)
    collection_ended_at = $CollectionEndedAt.ToString("o")
  }
  $temporaryPath = "$fullPath.tmp"
  $signal | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath $temporaryPath -Encoding UTF8
  Move-Item -LiteralPath $temporaryPath -Destination $fullPath
}

function Write-TriggerMonitorCompletionRequest {
  param(
    [string]$Path,
    [datetime]$ObservationEndedAt
  )

  $fullPath = [IO.Path]::GetFullPath($Path)
  $parent = Split-Path -Parent $fullPath
  if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw "The trigger monitor completion request parent folder does not exist."
  }
  if (Test-Path -LiteralPath $fullPath) {
    throw "The trigger monitor completion request already exists."
  }
  $request = [ordered]@{
    schema_version = "spot-trigger-monitor-completion-request-v1"
    request_id = [guid]::NewGuid().ToString("N")
    requested_at = [DateTimeOffset]::Now.ToString("o")
    observation_ended_at = ([DateTimeOffset]$ObservationEndedAt).ToString("o")
    reason = "observation-deadline-reached"
    request_source = "child-normal-observer-deadline"
  }
  $temporaryPath = "{0}.{1}.tmp" -f $fullPath, [guid]::NewGuid().ToString("N")
  try {
    $request | ConvertTo-Json -Depth 4 |
      Set-Content -LiteralPath $temporaryPath -Encoding UTF8
    Move-Item -LiteralPath $temporaryPath -Destination $fullPath
  } finally {
    if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
      Remove-Item -LiteralPath $temporaryPath -Force
    }
  }
  return [pscustomobject]$request
}

function Invoke-TriggerSelfTest {
  $historical = [pscustomobject]@{
    items = @(
      [pscustomobject]@{
        source = "spot_image"
        error_type = "ConnectTimeout"
        repeat = 112
        time_iso = "2026-07-23T12:21:32+00:00"
      },
      [pscustomobject]@{
        source = "plc_driver"
        error_type = ""
        repeat = 43
        time_iso = "2026-07-23T01:52:38+00:00"
      }
    )
  }
  $same = Get-SpotConnectTimeoutTriggerState -Body $historical
  $baseline = Get-SpotConnectTimeoutTriggerState -Body $historical
  if (Test-NewSpotConnectTimeout -Baseline $baseline -Current $same) {
    throw "Self-test failed: historical errors triggered collection."
  }

  $repeatIncrease = [pscustomobject]@{
    items = @(
      [pscustomobject]@{
        source = "spot_image"
        error_type = "ConnectTimeout"
        repeat = 113
        time_iso = "2026-07-23T12:21:32+00:00"
      }
    )
  }
  $repeatState = Get-SpotConnectTimeoutTriggerState -Body $repeatIncrease
  if (-not (Test-NewSpotConnectTimeout -Baseline $baseline -Current $repeatState)) {
    throw "Self-test failed: repeat increase was not detected."
  }

  $queueRollover = [pscustomobject]@{
    items = @(
      [pscustomobject]@{
        source = "spot_image"
        error_type = "ConnectTimeout"
        repeat = 1
        time_iso = "2026-07-23T13:00:00+00:00"
      }
    )
  }
  $rolloverState = Get-SpotConnectTimeoutTriggerState -Body $queueRollover
  if (-not (Test-NewSpotConnectTimeout -Baseline $baseline -Current $rolloverState)) {
    throw "Self-test failed: a later error after queue rollover was not detected."
  }

  $compactEnvelope = [ordered]@{
    sample = 42
    collected_at = "2026-07-23T13:00:01+00:00"
    status_code = 200
    ok = $true
    error = $null
  }
  $compactBody = [pscustomobject]@{
    items = @(
      [pscustomobject]@{
        source = "spot_image"
        error_type = "ConnectTimeout"
        repeat = 113
        message = "must-not-be-retained-in-compact-poll"
      }
    )
    summary = [pscustomobject]@{
      queue_size = 1
      repeat_total = 113
    }
  }
  $compactHash = ("a" * 64)
  $compactRecord = ConvertTo-CompactErrorPollRecord `
    -Envelope $compactEnvelope `
    -Body $compactBody `
    -TriggerState $repeatState `
    -BodySha256 $compactHash
  $compactJson = $compactRecord | ConvertTo-Json -Compress
  if ($compactJson -match "must-not-be-retained" -or
      $compactJson -match '"items"' -or
      $compactRecord.body_sha256 -cne $compactHash) {
    throw "Self-test failed: compact error polling retained a full error item."
  }
  if (Test-ShouldPersistErrorSnapshot `
      -ResponseOk $true `
      -BodySha256 $compactHash `
      -LastPersistedBodySha256 $compactHash) {
    throw "Self-test failed: unchanged error body requested a full snapshot."
  }
  if (-not (Test-ShouldPersistErrorSnapshot `
      -ResponseOk $true `
      -BodySha256 ("b" * 64) `
      -LastPersistedBodySha256 $compactHash)) {
    throw "Self-test failed: changed error body did not request a full snapshot."
  }
  if (Test-ShouldPersistErrorSnapshot `
      -ResponseOk $false `
      -BodySha256 ("b" * 64) `
      -LastPersistedBodySha256 $compactHash) {
    throw "Self-test failed: failed error poll requested a full snapshot."
  }

  $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
  $tempRoot = Join-Path $tempBase ("sfl-trigger-selftest-{0}" -f [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $tempRoot | Out-Null
  try {
    $signalPath = Join-Path $tempRoot "capture_stop_signal.json"
    $detectedAt = [DateTimeOffset]::Parse("2026-07-23T13:00:01+00:00")
    Write-CaptureStopSignal `
      -Path $signalPath `
      -StopReason "spot-connect-timeout-detected" `
      -TriggerDetected $true `
      -Baseline $baseline `
      -Current $rolloverState `
      -TriggerDetectedAt $detectedAt `
      -CollectionEndedAt $detectedAt.LocalDateTime
    $signal = Get-Content -LiteralPath $signalPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not [bool]$signal.trigger_detected -or
        $signal.stop_reason -ne "spot-connect-timeout-detected" -or
        [int]$signal.repeat_delta -ne 0 -or
        $null -eq $signal.trigger_detection_latency_ms) {
      throw "Self-test failed: capture stop signal contract."
    }
    $completionPath = Join-Path $tempRoot "completion_request.json"
    $completion = Write-TriggerMonitorCompletionRequest `
      -Path $completionPath `
      -ObservationEndedAt $detectedAt.LocalDateTime
    $completionEvidence = Get-Content `
      -LiteralPath $completionPath `
      -Raw `
      -Encoding UTF8 |
      ConvertFrom-Json
    if ($completionEvidence.schema_version -cne
        "spot-trigger-monitor-completion-request-v1" -or
        $completionEvidence.request_id -cne $completion.request_id -or
        $completionEvidence.reason -cne "observation-deadline-reached") {
      throw "Self-test failed: trigger monitor completion request contract."
    }
  } finally {
    $resolvedTempRoot = [IO.Path]::GetFullPath($tempRoot)
    if (-not $resolvedTempRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
      throw "Unsafe trigger self-test cleanup path."
    }
    Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force
  }

  Write-Output (
    "TRIGGER_SELF_TEST_PASS historical=false repeat=true rollover=true " +
    "signal=true compact_poll=true changed_snapshot=true completion_request=true"
  )
}

function Get-ObjectEntries {
  param([object]$Object)

  if ($null -eq $Object) {
    return @()
  }
  if ($Object -is [System.Collections.IDictionary]) {
    return @(
      $Object.GetEnumerator() | ForEach-Object {
        [pscustomobject][ordered]@{
          Name = [string]$_.Key
          Value = $_.Value
        }
      }
    )
  }
  return @($Object.PSObject.Properties)
}

function ConvertTo-SafeErrorItem {
  param([object]$Item)

  return [ordered]@{
    time_iso = Get-PropertyValue -Object $Item -Name "time_iso"
    source = Get-PropertyValue -Object $Item -Name "source"
    error_type = Get-PropertyValue -Object $Item -Name "error_type"
    message = Get-PropertyValue -Object $Item -Name "message"
    status_code = Get-PropertyValue -Object $Item -Name "status_code"
    path = Get-PropertyValue -Object $Item -Name "path"
    level = Get-PropertyValue -Object $Item -Name "level"
    repeat = Get-PropertyValue -Object $Item -Name "repeat"
  }
}

function ConvertTo-SafeErrorSample {
  param([object]$Envelope)

  $body = ConvertFrom-JsonOrNull -Text ([string]$Envelope.body)
  $items = @()
  foreach ($item in @((Get-PropertyValue -Object $body -Name "items"))) {
    if ($null -ne $item) {
      $items += ConvertTo-SafeErrorItem -Item $item
    }
  }
  return [ordered]@{
    sample = [int](Get-PropertyValue -Object $Envelope -Name "sample")
    collected_at = Get-PropertyValue -Object $Envelope -Name "collected_at"
    response_status = Get-PropertyValue -Object $Envelope -Name "status_code"
    summary = Get-PropertyValue -Object $body -Name "summary"
    items = $items
  }
}

function ConvertTo-SafeStatsSample {
  param(
    [object]$Envelope,
    [int]$SampleIndex
  )

  $body = ConvertFrom-JsonOrNull -Text ([string]$Envelope.body)
  $pollingPaths = [ordered]@{}
  $paths = Get-PropertyValue -Object (Get-PropertyValue -Object $body -Name "polling") -Name "paths"
  if ($null -ne $paths) {
    foreach ($pathProperty in (Get-ObjectEntries -Object $paths)) {
      $item = $pathProperty.Value
      $pollingPaths[$pathProperty.Name] = [ordered]@{
        count = Get-PropertyValue -Object $item -Name "count"
        requests_per_sec = Get-PropertyValue -Object $item -Name "requests_per_sec"
        avg_latency_ms = Get-PropertyValue -Object $item -Name "avg_latency_ms"
        error_rate = Get-PropertyValue -Object $item -Name "error_rate"
        http_4xx_count = Get-PropertyValue -Object $item -Name "http_4xx_count"
        http_5xx_count = Get-PropertyValue -Object $item -Name "http_5xx_count"
        success_count = Get-PropertyValue -Object $item -Name "success_count"
        failure_count = Get-PropertyValue -Object $item -Name "failure_count"
        stale_count = Get-PropertyValue -Object $item -Name "stale_count"
        avg_age_sec = Get-PropertyValue -Object $item -Name "avg_age_sec"
      }
    }
  }

  return [ordered]@{
    sample = $SampleIndex
    collected_at = Get-PropertyValue -Object $Envelope -Name "collected_at"
    response_status = Get-PropertyValue -Object $Envelope -Name "status_code"
    total_http_5xx_count = Get-PropertyValue -Object $body -Name "total_http_5xx_count"
    total_http_4xx_count = Get-PropertyValue -Object $body -Name "total_http_4xx_count"
    error_count = Get-PropertyValue -Object $body -Name "error_count"
    window = Get-PropertyValue -Object $body -Name "window"
    errors = Get-PropertyValue -Object $body -Name "errors"
    polling_paths = $pollingPaths
  }
}

function New-Sha256Text {
  param([string]$Text)

  if ([string]::IsNullOrWhiteSpace($Text)) {
    return $null
  }
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $hashBytes = $sha.ComputeHash($bytes)
    return ([System.BitConverter]::ToString($hashBytes)).Replace("-", "").ToLowerInvariant()
  } finally {
    $sha.Dispose()
  }
}

function Get-PathLeafOrNull {
  param([object]$PathValue)

  if ($null -eq $PathValue) {
    return $null
  }
  $text = [string]$PathValue
  if ([string]::IsNullOrWhiteSpace($text)) {
    return $null
  }
  $normalized = $text.Trim().TrimEnd([char[]]@('\', '/'))
  if ([string]::IsNullOrWhiteSpace($normalized)) {
    return $null
  }
  $leaf = Split-Path -Leaf $normalized
  if ([string]::IsNullOrWhiteSpace($leaf)) {
    return $normalized
  }
  return $leaf
}

function ConvertTo-SafeImageCaptureStatus {
  param([object]$ImageCapture)

  if ($null -eq $ImageCapture) {
    return $null
  }

  return [ordered]@{
    enabled = Get-PropertyValue -Object $ImageCapture -Name "enabled"
    mode = Get-PropertyValue -Object $ImageCapture -Name "mode"
    queue_size = Get-PropertyValue -Object $ImageCapture -Name "queue_size"
    queue_capacity = Get-PropertyValue -Object $ImageCapture -Name "queue_capacity"
    enqueued_count = Get-PropertyValue -Object $ImageCapture -Name "enqueued_count"
    written_count = Get-PropertyValue -Object $ImageCapture -Name "written_count"
    dropped_count = Get-PropertyValue -Object $ImageCapture -Name "dropped_count"
    failure_count = Get-PropertyValue -Object $ImageCapture -Name "failure_count"
    last_enqueue_at = Get-PropertyValue -Object $ImageCapture -Name "last_enqueue_at"
    last_write_at = Get-PropertyValue -Object $ImageCapture -Name "last_write_at"
    last_error_at = Get-PropertyValue -Object $ImageCapture -Name "last_error_at"
    last_error_code = Get-PropertyValue -Object $ImageCapture -Name "last_error_code"
  }
}

function ConvertTo-SafeSpotImageFactManifest {
  param([object]$Manifest)

  if ($null -eq $Manifest) {
    return $null
  }

  $factPath = Get-PropertyValue -Object $Manifest -Name "fact_path"
  $captureRoot = Get-PropertyValue -Object $Manifest -Name "capture_root"

  return [ordered]@{
    enabled = Get-PropertyValue -Object $Manifest -Name "enabled"
    mode = Get-PropertyValue -Object $Manifest -Name "mode"
    fact_basename = Get-PathLeafOrNull -PathValue $factPath
    fact_path_sha256 = New-Sha256Text -Text ([string]$factPath)
    capture_root_basename = Get-PathLeafOrNull -PathValue $captureRoot
    capture_root_sha256 = New-Sha256Text -Text ([string]$captureRoot)
    row_count = Get-PropertyValue -Object $Manifest -Name "row_count"
    sha256 = Get-PropertyValue -Object $Manifest -Name "sha256"
    written = Get-PropertyValue -Object $Manifest -Name "written"
    dropped = Get-PropertyValue -Object $Manifest -Name "dropped"
    failure = Get-PropertyValue -Object $Manifest -Name "failure"
    last_write_at = Get-PropertyValue -Object $Manifest -Name "last_write_at"
    path_values_redacted = $true
  }
}

function ConvertTo-SafeSpotConfigSample {
  param([object]$Envelope)

  $body = ConvertFrom-JsonOrNull -Text ([string]$Envelope.body)
  return [ordered]@{
    sample = Get-PropertyValue -Object $Envelope -Name "sample"
    collected_at = Get-PropertyValue -Object $Envelope -Name "collected_at"
    response_status = Get-PropertyValue -Object $Envelope -Name "status_code"
    image_capture = ConvertTo-SafeImageCaptureStatus -ImageCapture (Get-PropertyValue -Object $body -Name "image_capture")
    spot_image_fact_manifest = ConvertTo-SafeSpotImageFactManifest -Manifest (
      Get-PropertyValue -Object $body -Name "spot_image_fact_manifest"
    )
  }
}

function New-RawHashManifest {
  param(
    [string]$RawRoot,
    [string]$SanitizedRoot
  )

  $rawRootFull = (Resolve-Path -LiteralPath $RawRoot).Path.TrimEnd([char[]]@('\', '/'))
  $items = @(Get-ChildItem -LiteralPath $RawRoot -Recurse -File | Sort-Object FullName | ForEach-Object {
    $relativePath = $_.FullName.Substring($rawRootFull.Length).TrimStart([char[]]@('\', '/')) -replace "\\", "/"
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
    [pscustomobject][ordered]@{
      basename = $_.Name
      relative_path = $relativePath
      sha256 = $hash.Hash.ToLowerInvariant()
      size = [int64]$_.Length
    }
  })

  $txtPath = Join-Path $SanitizedRoot "raw_file_sha256.txt"
  $csvPath = Join-Path $SanitizedRoot "raw_file_sha256.csv"
  $jsonPath = Join-Path $SanitizedRoot "raw_file_sha256.json"

  $txtLines = @("basename`trelative_path`tsha256`tsize")
  foreach ($item in $items) {
    $txtLines += "$($item.basename)`t$($item.relative_path)`t$($item.sha256)`t$($item.size)"
  }
  $txtLines | Set-Content -LiteralPath $txtPath -Encoding UTF8
  if ($items.Count -gt 0) {
    $items | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8
  } else {
    "basename,relative_path,sha256,size" | Set-Content -LiteralPath $csvPath -Encoding UTF8
  }
  $items | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

  return $items
}

function Add-Count {
  param(
    [hashtable]$Map,
    [string]$Key,
    [int]$Count
  )

  $safeKey = if ([string]::IsNullOrWhiteSpace($Key)) { "unknown" } else { $Key }
  if (-not $Map.ContainsKey($safeKey)) {
    $Map[$safeKey] = 0
  }
  $Map[$safeKey] = [int]$Map[$safeKey] + [Math]::Max(1, $Count)
}

function Convert-CountMapToRows {
  param([hashtable]$Map)

  return @(
    $Map.GetEnumerator() |
      Sort-Object @{ Expression = "Value"; Descending = $true }, @{ Expression = "Name"; Descending = $false } |
      ForEach-Object {
        [pscustomobject][ordered]@{
          key = [string]$_.Name
          count = [int]$_.Value
        }
      }
  )
}

function ConvertTo-RunAnalysis {
  param(
    [array]$StatsSamples,
    [array]$ErrorSamples
  )

  $firstStats = $StatsSamples | Select-Object -First 1
  $lastStats = $StatsSamples | Select-Object -Last 1
  $firstErrors = $ErrorSamples | Select-Object -First 1
  $lastErrors = $ErrorSamples | Select-Object -Last 1
  $routeMap = @{}

  foreach ($sample in @($StatsSamples)) {
    $sampleIndex = [int](Get-PropertyValue -Object $sample -Name "sample")
    $pollingPaths = Get-PropertyValue -Object $sample -Name "polling_paths"
    if ($null -eq $pollingPaths) {
      continue
    }
    foreach ($pathProperty in (Get-ObjectEntries -Object $pollingPaths)) {
      $path = [string]$pathProperty.Name
      $item = $pathProperty.Value
      $countValue = Get-PropertyValue -Object $item -Name "http_5xx_count"
      if ($null -eq $countValue) {
        continue
      }
      $count = [int]$countValue
      if ($count -le 0) {
        continue
      }
      if (-not $routeMap.ContainsKey($path)) {
        $routeMap[$path] = [ordered]@{
          path = $path
          max_window_5xx_count = $count
          samples_seen = 1
          first_sample = $sampleIndex
          last_sample = $sampleIndex
        }
      } else {
        $entry = $routeMap[$path]
        if ($count -gt [int]$entry.max_window_5xx_count) {
          $entry.max_window_5xx_count = $count
        }
        $entry.samples_seen = [int]$entry.samples_seen + 1
        $entry.last_sample = $sampleIndex
      }
    }
  }

  $sourceCounts = @{}
  $messageCounts = @{}
  $statusCounts = @{}
  $typeCounts = @{}
  $pathCounts = @{}
  $routeStatusCounts = @{}
  foreach ($item in @((Get-PropertyValue -Object $lastErrors -Name "items"))) {
    if ($null -eq $item) {
      continue
    }
    $repeatValue = Get-PropertyValue -Object $item -Name "repeat"
    $repeat = if ($null -eq $repeatValue) { 1 } else { [int]$repeatValue }
    $sourceKey = [string](Get-PropertyValue -Object $item -Name "source")
    $messageKey = [string](Get-PropertyValue -Object $item -Name "message")
    $statusKey = [string](Get-PropertyValue -Object $item -Name "status_code")
    $typeKey = [string](Get-PropertyValue -Object $item -Name "error_type")
    $pathKey = [string](Get-PropertyValue -Object $item -Name "path")
    Add-Count -Map $sourceCounts -Key $sourceKey -Count $repeat
    Add-Count -Map $messageCounts -Key $messageKey -Count $repeat
    Add-Count -Map $statusCounts -Key $statusKey -Count $repeat
    Add-Count -Map $typeCounts -Key $typeKey -Count $repeat
    Add-Count -Map $pathCounts -Key $pathKey -Count $repeat
    Add-Count -Map $routeStatusCounts -Key "$pathKey $statusKey" -Count $repeat
  }

  return [ordered]@{
    first_total_http_5xx_count = Get-PropertyValue -Object $firstStats -Name "total_http_5xx_count"
    last_total_http_5xx_count = Get-PropertyValue -Object $lastStats -Name "total_http_5xx_count"
    first_error_queue_size = Get-PropertyValue -Object (Get-PropertyValue -Object $firstErrors -Name "summary") -Name "queue_size"
    last_error_queue_size = Get-PropertyValue -Object (Get-PropertyValue -Object $lastErrors -Name "summary") -Name "queue_size"
    observed_5xx_routes = @(
      $routeMap.Values |
        Sort-Object @{ Expression = "max_window_5xx_count"; Descending = $true }, @{ Expression = "path"; Descending = $false }
    )
    final_error_source_counts = @(Convert-CountMapToRows -Map $sourceCounts)
    final_error_message_counts = @(Convert-CountMapToRows -Map $messageCounts)
    final_error_status_counts = @(Convert-CountMapToRows -Map $statusCounts)
    final_error_type_counts = @(Convert-CountMapToRows -Map $typeCounts)
    final_error_path_counts = @(Convert-CountMapToRows -Map $pathCounts)
    final_error_route_status_counts = @(Convert-CountMapToRows -Map $routeStatusCounts)
    final_error_summary = Get-PropertyValue -Object $lastErrors -Name "summary"
  }
}

function Save-TriggerMonitorFailureEvidence {
  param(
    [Parameter(Mandatory = $true)]
    [System.Management.Automation.Job]$Job,
    [Parameter(Mandatory = $true)]
    [string]$RawPath,
    [Parameter(Mandatory = $true)]
    [string]$SafePath,
    [Parameter(Mandatory = $true)]
    [string]$ConsolePath,
    [object[]]$MonitorOutput = @(),
    [object[]]$ReceiveErrors = @(),
    [switch]$ReceiveNow
  )

  $capturedOutput = @($MonitorOutput)
  $capturedErrors = @($ReceiveErrors)
  if ($ReceiveNow) {
    $receiveErrorsNow = @()
    $capturedOutput = @(
      Receive-Job `
        -Job $Job `
        -ErrorAction SilentlyContinue `
        -ErrorVariable receiveErrorsNow
    )
    $capturedErrors = @($receiveErrorsNow)
  }
  if ($capturedOutput.Count -gt 0) {
    $capturedOutput | Out-String |
      Set-Content -LiteralPath $ConsolePath -Encoding UTF8
  }

  $jobReason = $Job.JobStateInfo.Reason
  $errorMessages = @(
    if ($null -ne $jobReason -and
        -not [string]::IsNullOrWhiteSpace($jobReason.Message)) {
      [string]$jobReason.Message
    }
    foreach ($record in $capturedErrors) {
      if ($null -ne $record.Exception -and
          -not [string]::IsNullOrWhiteSpace($record.Exception.Message)) {
        [string]$record.Exception.Message
      }
    }
  )
  $reasonCode = if (@(
      $errorMessages | Where-Object { $_ -like '*trigger evidence path exceeds*' }
    ).Count -gt 0) {
    'trigger-evidence-path-too-long'
  } elseif (@(
      $errorMessages | Where-Object { $_ -like '*could not read its baseline*' }
    ).Count -gt 0) {
    'trigger-baseline-read-failed'
  } elseif (@(
      $errorMessages | Where-Object {
        $_ -like '*capture stop signal*' -or $_ -like '*RawRoot*'
      }
    ).Count -gt 0) {
    'trigger-input-contract-failed'
  } else {
    'trigger-monitor-job-failed'
  }

  [ordered]@{
    schema_version = 'spot-connecttimeout-trigger-monitor-failure-raw-v1'
    observed_at = [DateTimeOffset]::Now.ToString('o')
    reason_code = $reasonCode
    job_state = [string]$Job.State
    job_reason_type = if ($null -eq $jobReason) {
      $null
    } else {
      $jobReason.GetType().FullName
    }
    job_reason_message = if ($null -eq $jobReason) {
      $null
    } else {
      [string]$jobReason.Message
    }
    error_records = @(
      foreach ($record in $capturedErrors) {
        [ordered]@{
          exception_type = if ($null -eq $record.Exception) {
            $null
          } else {
            $record.Exception.GetType().FullName
          }
          message = if ($null -eq $record.Exception) {
            [string]$record
          } else {
            [string]$record.Exception.Message
          }
          fully_qualified_error_id = [string]$record.FullyQualifiedErrorId
          script_stack_trace = [string]$record.ScriptStackTrace
        }
      }
    )
    monitor_output = @($capturedOutput | ForEach-Object { [string]$_ })
  } | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath $RawPath -Encoding UTF8

  [ordered]@{
    schema_version = 'spot-connecttimeout-trigger-monitor-failure-v1'
    observed_at = [DateTimeOffset]::Now.ToString('o')
    reason_code = $reasonCode
    job_state = [string]$Job.State
    exception_types = @(
      @(
        if ($null -ne $jobReason) { $jobReason.GetType().FullName }
        foreach ($record in $capturedErrors) {
          if ($null -ne $record.Exception) {
            $record.Exception.GetType().FullName
          }
        }
      ) | Sort-Object -Unique
    )
    raw_detail_retained = $true
    raw_detail_file = 'trigger_monitor_failure_raw.json'
    error_message_retained = $false
  } | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath $SafePath -Encoding UTF8
  return $reasonCode
}

if ($SelfTest) {
  Invoke-TriggerSelfTest
  exit 0
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$sessionRoot = Join-Path $OutputRoot "operational_observability_$timestamp"
$rawRoot = Join-Path $sessionRoot "raw"
$sanitizedRoot = Join-Path $sessionRoot "sanitized"
New-Item -ItemType Directory -Path $rawRoot -Force | Out-Null
New-Item -ItemType Directory -Path $sanitizedRoot -Force | Out-Null

$normalCadenceSec = if ($StopOnNewSpotConnectTimeout) {
  $NormalEndpointIntervalSec
} else {
  0
}
$endpoints = if ($StopOnNewSpotConnectTimeout) {
  @(
    @{ Name = "health"; Path = "/health"; CadenceSec = $normalCadenceSec },
    @{ Name = "stats"; Path = "/stats"; CadenceSec = $normalCadenceSec },
    @{ Name = "spot_config"; Path = "/api/spot/config"; CadenceSec = $normalCadenceSec },
    @{ Name = "memory_state"; Path = "/api/memory/state"; CadenceSec = $MemoryStateIntervalSec },
    @{ Name = "memory_details"; Path = "/api/memory/details"; CadenceSec = $MemoryDetailsIntervalSec }
  )
} else {
  @(
    @{ Name = "health"; Path = "/health"; CadenceSec = 0 },
    @{ Name = "stats"; Path = "/stats"; CadenceSec = 0 },
    @{ Name = "observability_errors"; Path = "/api/observability/errors?limit=200"; CadenceSec = 0 },
    @{ Name = "spot_config"; Path = "/api/spot/config"; CadenceSec = 0 },
    @{ Name = "memory_state"; Path = "/api/memory/state"; CadenceSec = $MemoryStateIntervalSec },
    @{ Name = "memory_details"; Path = "/api/memory/details"; CadenceSec = $MemoryDetailsIntervalSec }
  )
}

$rawIndex = @()
$triggerBaseline = $null
$triggerCurrent = $null
$triggerDetected = $false
$triggerDetectedAt = $null
$triggerMonitorPollCount = 0
$triggerMonitorErrorCount = 0
$triggerMonitorRecoveredErrorCount = 0
$triggerMonitorUnrecoveredErrorCount = 0
$triggerMonitorMaxConsecutiveErrorCount = 0
$triggerMonitorIntegrityStatus = $null
$triggerMonitorIntegrityPolicy = $null
$triggerCompactPollPath = Join-Path $rawRoot "trigger_observability_errors_compact.jsonl"
$triggerCompactPollWriter = $null
$triggerLastPersistedBodySha256 = $null
$triggerLatestFullEnvelope = $null
$triggerChangeSnapshotCount = 0
$triggerFullSnapshotCount = 0
$triggerMonitorSummary = $null
$triggerMonitorJob = $null
$triggerMonitorConsolePath = Join-Path $rawRoot "trigger_monitor_console.txt"
$triggerMonitorSummaryPath = Join-Path $rawRoot "trigger_monitor_summary.json"
$triggerMonitorErrorEventsRawPath = Join-Path `
  $rawRoot `
  "trigger_monitor_error_events_raw.json"
$triggerMonitorFailureRawPath = Join-Path $rawRoot "trigger_monitor_failure_raw.json"
$triggerMonitorFailureSafePath = Join-Path $rawRoot "trigger_monitor_failure.json"
$triggerMonitorCompletionRequestPath = Join-Path `
  $rawRoot `
  "trigger_monitor_completion_request.json"
$collectorProcess = [Diagnostics.Process]::GetCurrentProcess()
$collectorWorkingSetStartBytes = [int64]$collectorProcess.WorkingSet64
$collectorWorkingSetMaxBytes = $collectorWorkingSetStartBytes
if ($StopOnNewSpotConnectTimeout) {
  if ([string]::IsNullOrWhiteSpace($CaptureStopSignalPath)) {
    throw "CaptureStopSignalPath is required in event-trigger mode."
  }
  $signalFullPath = [IO.Path]::GetFullPath($CaptureStopSignalPath)
  $outputRootFullPath = [IO.Path]::GetFullPath($OutputRoot).TrimEnd("\") + "\"
  if (-not $signalFullPath.StartsWith(
      $outputRootFullPath,
      [StringComparison]::OrdinalIgnoreCase
    )) {
    throw "CaptureStopSignalPath must be inside OutputRoot."
  }

  if ([string]::IsNullOrWhiteSpace($TriggerMonitorPath)) {
    $TriggerMonitorPath = Join-Path $PSScriptRoot "monitor-spot-connecttimeout-trigger.ps1"
  }
  if (-not (Test-Path -LiteralPath $TriggerMonitorPath -PathType Leaf)) {
    throw "The dedicated ConnectTimeout trigger monitor is missing."
  }
  $triggerMonitorJob = Start-Job -ScriptBlock {
    param(
      [string]$ScriptPath,
      [string]$WorkerApiBase,
      [int]$WorkerDurationSec,
      [int]$WorkerPollIntervalMs,
      [int]$WorkerTimeoutMs,
      [string]$WorkerRawRoot,
      [string]$WorkerSignalPath,
      [string]$WorkerCompletionRequestPath,
      [int]$WorkerLatencyWarningMs
    )
    & $ScriptPath `
      -ApiBase $WorkerApiBase `
      -DurationSec $WorkerDurationSec `
      -PollIntervalMs $WorkerPollIntervalMs `
      -RequestTimeoutMs $WorkerTimeoutMs `
      -RawRoot $WorkerRawRoot `
      -CaptureStopSignalPath $WorkerSignalPath `
      -CompletionRequestPath $WorkerCompletionRequestPath `
      -DetectionLatencyWarningMs $WorkerLatencyWarningMs
  } -ArgumentList @(
    $TriggerMonitorPath,
    $ApiBase,
    $DurationSec,
    1000,
    1000,
    $rawRoot,
    $CaptureStopSignalPath,
    $triggerMonitorCompletionRequestPath,
    $DetectionLatencyWarningMs
  )
  Write-Host (
    "[TRIGGER] Dedicated one-second error monitor started. Normal app APIs cannot delay its stop signal."
  ) -ForegroundColor Cyan
}
$collectionStartedAt = Get-Date
$collectionDeadlineAt = if ($DurationSec -gt 0) {
  $collectionStartedAt.AddSeconds($DurationSec)
} else {
  $null
}
$nextScheduledAt = $collectionStartedAt
$nextDueByEndpoint = @{}
foreach ($endpoint in $endpoints) {
  if ([int]$endpoint.CadenceSec -gt 0) {
    $nextDueByEndpoint[$endpoint.Name] = $collectionStartedAt
  }
}
$progressEverySamples = if ($IntervalSec -gt 0) {
  [Math]::Max(1, [int][Math]::Ceiling(60.0 / $IntervalSec))
} else {
  1
}
$sample = 0
while ($true) {
  $now = Get-Date
  if ($StopOnNewSpotConnectTimeout) {
    if (Test-Path -LiteralPath $CaptureStopSignalPath -PathType Leaf) {
      break
    }
    if ($null -ne $triggerMonitorJob -and
        $triggerMonitorJob.State -in @("Failed", "Stopped")) {
      $failureReason = Save-TriggerMonitorFailureEvidence `
        -Job $triggerMonitorJob `
        -RawPath $triggerMonitorFailureRawPath `
        -SafePath $triggerMonitorFailureSafePath `
        -ConsolePath $triggerMonitorConsolePath `
        -ReceiveNow
      throw (
        'The dedicated ConnectTimeout trigger monitor stopped unexpectedly. ' +
        "Evidence reason: $failureReason."
      )
    }
  }
  if ($null -ne $collectionDeadlineAt -and $now -ge $collectionDeadlineAt) {
    break
  }
  if ($null -ne $collectionDeadlineAt) {
    $remainingBeforeSampleMs = [int][Math]::Floor(
      ($collectionDeadlineAt - $now).TotalMilliseconds
    )
    if ($remainingBeforeSampleMs -lt 1000) {
      if ($remainingBeforeSampleMs -gt 0) {
        Start-Sleep -Milliseconds $remainingBeforeSampleMs
      }
      break
    }
  }
  if ($DurationSec -eq 0 -and $sample -ge $Samples) {
    break
  }

  $sample += 1
  $sampleStartedAt = Get-Date
  $sampleCompletedEndpoints = 0
  foreach ($endpoint in $endpoints) {
    $cadenceSec = [int]$endpoint.CadenceSec
    if ($cadenceSec -gt 0) {
      $nextDue = [datetime]$nextDueByEndpoint[$endpoint.Name]
      if ($sampleStartedAt -lt $nextDue) {
        continue
      }
      do {
        $nextDue = $nextDue.AddSeconds($cadenceSec)
      } while ($nextDue -le $sampleStartedAt)
      $nextDueByEndpoint[$endpoint.Name] = $nextDue
    }

    $endpointTimeoutSec = $TimeoutSec
    if ($null -ne $collectionDeadlineAt) {
      $remainingBeforeRequest = ($collectionDeadlineAt - (Get-Date)).TotalSeconds
      if ($remainingBeforeRequest -lt 1) {
        break
      }
      $endpointTimeoutSec = [Math]::Max(
        1,
        [Math]::Min($TimeoutSec, [int][Math]::Floor($remainingBeforeRequest))
      )
    }

    $uri = Join-ApiUrl -Base $ApiBase -Path $endpoint.Path
    $result = Invoke-ReadOnlyEndpoint -Uri $uri -Timeout $endpointTimeoutSec
    $rawFile = Join-Path $rawRoot ("sample_{0:d4}_{1}.json" -f $sample, $endpoint.Name)
    $envelope = [ordered]@{
      sample = $sample
      endpoint = $endpoint.Name
      path = $endpoint.Path
      collected_at = Get-Date -Format "o"
      status_code = $result.status_code
      ok = $result.ok
      error = $result.error
      body = $result.body
    }
    $isCompactTriggerPoll = (
      $StopOnNewSpotConnectTimeout -and
      $endpoint.Name -eq "observability_errors"
    )
    if ($isCompactTriggerPoll) {
      $triggerMonitorPollCount += 1
      $triggerBody = if ([bool]$result.ok) {
        ConvertFrom-JsonOrNull -Text ([string]$result.body)
      } else {
        $null
      }
      if ($null -eq $triggerBody) {
        $triggerMonitorErrorCount += 1
      } else {
        $triggerCurrent = Get-SpotConnectTimeoutTriggerState -Body $triggerBody
        $triggerLatestFullEnvelope = $envelope
        $bodySha256 = New-Sha256Text -Text ([string]$result.body)
        $compactRecord = ConvertTo-CompactErrorPollRecord `
          -Envelope $envelope `
          -Body $triggerBody `
          -TriggerState $triggerCurrent `
          -BodySha256 $bodySha256
        $triggerCompactPollWriter.WriteLine(
          ($compactRecord | ConvertTo-Json -Compress)
        )
        $triggerCompactPollWriter.Flush()
        if (Test-ShouldPersistErrorSnapshot `
            -ResponseOk ([bool]$result.ok) `
            -BodySha256 $bodySha256 `
            -LastPersistedBodySha256 $triggerLastPersistedBodySha256) {
          $triggerChangeSnapshotCount += 1
          $changeFile = Join-Path $rawRoot (
            "trigger_change_{0:d4}_observability_errors.json" -f
              $triggerChangeSnapshotCount
          )
          $envelope | ConvertTo-Json -Depth 12 |
            Set-Content -LiteralPath $changeFile -Encoding UTF8
          $triggerLastPersistedBodySha256 = $bodySha256
          $triggerFullSnapshotCount += 1
        }
        if (-not $triggerDetected -and
            (Test-NewSpotConnectTimeout `
              -Baseline $triggerBaseline `
              -Current $triggerCurrent)) {
          $triggerDetected = $true
          $triggerDetectedAt = [DateTimeOffset](Get-Date)
        }
      }
      if ($null -eq $triggerBody) {
        $compactRecord = ConvertTo-CompactErrorPollRecord `
          -Envelope $envelope `
          -Body $null `
          -TriggerState $null `
          -BodySha256 $null
        $triggerCompactPollWriter.WriteLine(
          ($compactRecord | ConvertTo-Json -Compress)
        )
        $triggerCompactPollWriter.Flush()
      }
    } else {
      $envelope | ConvertTo-Json -Depth 12 |
        Set-Content -LiteralPath $rawFile -Encoding UTF8
      $rawIndex += [ordered]@{
        sample = $sample
        endpoint = $endpoint.Name
        relative_path = (Split-Path -Leaf $rawFile)
        status_code = $result.status_code
        ok = $result.ok
      }
    }
    $sampleCompletedEndpoints += 1
    if ($StopOnNewSpotConnectTimeout -and
        (Test-Path -LiteralPath $CaptureStopSignalPath -PathType Leaf)) {
      break
    }
  }

  $collectorProcess.Refresh()
  $collectorWorkingSetMaxBytes = [Math]::Max(
    $collectorWorkingSetMaxBytes,
    [int64]$collectorProcess.WorkingSet64
  )

  $progressNow = Get-Date
  $isFinalFixedSample = $DurationSec -eq 0 -and $sample -eq $Samples
  if ($sample -eq 1 -or $isFinalFixedSample -or ($sample % $progressEverySamples) -eq 0) {
    $elapsed = $progressNow - $collectionStartedAt
    if ($null -ne $collectionDeadlineAt) {
      $percent = [Math]::Round(
        [Math]::Min(100.0, ($elapsed.TotalSeconds * 100.0) / $DurationSec),
        1
      )
      $estimatedEnd = $collectionDeadlineAt
      $progressUnits = "{0} samples" -f $sample
    } else {
      $percent = [Math]::Round(($sample * 100.0) / $Samples, 1)
      $remainingSeconds = [Math]::Max(0, ($Samples - $sample) * $IntervalSec)
      $estimatedEnd = $progressNow.AddSeconds($remainingSeconds)
      $progressUnits = "{0}/{1}" -f $sample, $Samples
    }
    Write-Host (
      "[PROGRESS] observation {0}% ({1}); elapsed={2}; fixed end={3}" -f `
        $percent,
        $progressUnits,
        $elapsed.ToString('hh\:mm\:ss'),
        $estimatedEnd.ToString('yyyy-MM-dd HH:mm:ss K')
    ) -ForegroundColor Cyan
  }

  if ($sampleCompletedEndpoints -eq 0 -and
      -not $StopOnNewSpotConnectTimeout) {
    break
  }
  if ($StopOnNewSpotConnectTimeout -and
      (Test-Path -LiteralPath $CaptureStopSignalPath -PathType Leaf)) {
    Write-Host (
      "[TRIGGER] Dedicated monitor stop signal received. Stopping timed observation safely."
    ) -ForegroundColor Yellow
    break
  }

  if ($IntervalSec -gt 0) {
    $nextScheduledAt = $nextScheduledAt.AddSeconds($IntervalSec)
    $sleepUntil = $nextScheduledAt
    $nowAfterSample = Get-Date
    while ($sleepUntil -le $nowAfterSample) {
      $sleepUntil = $sleepUntil.AddSeconds($IntervalSec)
    }
    $nextScheduledAt = $sleepUntil
    if ($null -ne $collectionDeadlineAt -and $sleepUntil -gt $collectionDeadlineAt) {
      $sleepUntil = $collectionDeadlineAt
    }
    $sleepMilliseconds = [int][Math]::Floor((($sleepUntil - (Get-Date)).TotalMilliseconds))
    if ($sleepMilliseconds -gt 0) {
      Start-Sleep -Milliseconds $sleepMilliseconds
    }
  }
}
$normalObserverEndedAt = Get-Date
$collectionEndedAt = $normalObserverEndedAt
if ($StopOnNewSpotConnectTimeout) {
  if ($null -eq $triggerMonitorJob) {
    throw "The dedicated ConnectTimeout trigger monitor was not started."
  }
  if ($triggerMonitorJob.State -eq "Running" -and
      -not (Test-Path -LiteralPath $CaptureStopSignalPath -PathType Leaf) -and
      -not (Test-Path `
        -LiteralPath $triggerMonitorCompletionRequestPath `
        -PathType Leaf)) {
    try {
      Write-TriggerMonitorCompletionRequest `
        -Path $triggerMonitorCompletionRequestPath `
        -ObservationEndedAt $normalObserverEndedAt |
        Out-Null
    } catch {
      if (-not (Test-Path `
          -LiteralPath $triggerMonitorCompletionRequestPath `
          -PathType Leaf)) {
        throw
      }
    }
  }
  if ($triggerMonitorJob.State -eq "Running") {
    Wait-Job -Job $triggerMonitorJob -Timeout 15 | Out-Null
  }
  $triggerMonitorOutput = @(
    Receive-Job `
      -Job $triggerMonitorJob `
      -ErrorAction SilentlyContinue `
      -ErrorVariable triggerMonitorReceiveErrors
  )
  if ($triggerMonitorOutput.Count -gt 0) {
    $triggerMonitorOutput | Out-String |
      Set-Content -LiteralPath $triggerMonitorConsolePath -Encoding UTF8
  }
  if ($triggerMonitorJob.State -ne "Completed") {
    $monitorState = $triggerMonitorJob.State
    $failureReason = Save-TriggerMonitorFailureEvidence `
      -Job $triggerMonitorJob `
      -RawPath $triggerMonitorFailureRawPath `
      -SafePath $triggerMonitorFailureSafePath `
      -ConsolePath $triggerMonitorConsolePath `
      -MonitorOutput $triggerMonitorOutput `
      -ReceiveErrors $triggerMonitorReceiveErrors
    Stop-Job -Job $triggerMonitorJob -ErrorAction SilentlyContinue
    Remove-Job -Job $triggerMonitorJob -Force -ErrorAction SilentlyContinue
    $triggerMonitorJob = $null
    throw (
      "The dedicated ConnectTimeout trigger monitor did not complete. State: {0}. Evidence reason: {1}." -f
        $monitorState,
        $failureReason
    )
  }
  Remove-Job -Job $triggerMonitorJob -Force -ErrorAction SilentlyContinue
  $triggerMonitorJob = $null

  foreach ($requiredTriggerPath in @(
      $CaptureStopSignalPath,
      $triggerMonitorSummaryPath,
      $triggerCompactPollPath,
      $triggerMonitorErrorEventsRawPath,
      (Join-Path $rawRoot "trigger_baseline_observability_errors.json"),
      (Join-Path $rawRoot "trigger_final_observability_errors.json")
    )) {
    if (-not (Test-Path -LiteralPath $requiredTriggerPath -PathType Leaf)) {
      throw (
        "The dedicated trigger monitor did not create required evidence: {0}" -f
          (Split-Path -Leaf $requiredTriggerPath)
      )
    }
  }

  $triggerSignal = Get-Content `
    -LiteralPath $CaptureStopSignalPath `
    -Raw `
    -Encoding UTF8 |
    ConvertFrom-Json
  $triggerMonitorSummary = Get-Content `
    -LiteralPath $triggerMonitorSummaryPath `
    -Raw `
    -Encoding UTF8 |
    ConvertFrom-Json
  if ($triggerSignal.schema_version -ne "spot-connecttimeout-capture-stop-v1" -or
      $triggerMonitorSummary.schema_version -ne
        "spot-connecttimeout-trigger-monitor-v1") {
    throw "The dedicated trigger monitor evidence contract is invalid."
  }
  if ($triggerSignal.stop_reason -eq "observation-completion-requested") {
    if (-not (Test-Path `
        -LiteralPath $triggerMonitorCompletionRequestPath `
        -PathType Leaf)) {
      throw "The trigger monitor completion request evidence is missing."
    }
    $completionRequest = Get-Content `
      -LiteralPath $triggerMonitorCompletionRequestPath `
      -Raw `
      -Encoding UTF8 |
      ConvertFrom-Json
    if ($completionRequest.schema_version -cne
          "spot-trigger-monitor-completion-request-v1" -or
        $completionRequest.request_id -cne
          $triggerMonitorSummary.completion_request_id -or
        -not [bool]$triggerMonitorSummary.completion_request_observed) {
      throw "The trigger monitor completion request evidence is inconsistent."
    }
  }
  $triggerDetected = [bool]$triggerSignal.trigger_detected
  $triggerDetectedAt = if (
    [string]::IsNullOrWhiteSpace([string]$triggerSignal.trigger_detected_at)
  ) {
    $null
  } else {
    [DateTimeOffset]::Parse([string]$triggerSignal.trigger_detected_at)
  }
  $triggerMonitorPollCount = [int]$triggerMonitorSummary.monitor_poll_count
  $triggerMonitorErrorCount = [int]$triggerMonitorSummary.monitor_error_count
  $triggerMonitorRecoveredErrorCount =
    [int]$triggerMonitorSummary.monitor_recovered_error_count
  $triggerMonitorUnrecoveredErrorCount =
    [int]$triggerMonitorSummary.monitor_unrecovered_error_count
  $triggerMonitorMaxConsecutiveErrorCount =
    [int]$triggerMonitorSummary.monitor_max_consecutive_error_count
  $triggerMonitorIntegrityStatus =
    [string]$triggerMonitorSummary.monitor_integrity_status
  $triggerMonitorIntegrityPolicy =
    [string]$triggerMonitorSummary.monitor_integrity_policy
  $triggerChangeSnapshotCount = [int]$triggerMonitorSummary.change_snapshot_count
  $triggerFullSnapshotCount = [int]$triggerMonitorSummary.full_snapshot_count
  $collectionEndedAt = [DateTimeOffset]::Parse(
    [string]$triggerSignal.collection_ended_at
  ).LocalDateTime

  $baselineEnvelope = Get-Content `
    -LiteralPath (Join-Path $rawRoot "trigger_baseline_observability_errors.json") `
    -Raw `
    -Encoding UTF8 |
    ConvertFrom-Json
  $finalEnvelope = Get-Content `
    -LiteralPath (Join-Path $rawRoot "trigger_final_observability_errors.json") `
    -Raw `
    -Encoding UTF8 |
    ConvertFrom-Json
  $triggerBaseline = Get-SpotConnectTimeoutTriggerState -Body (
    ConvertFrom-JsonOrNull -Text ([string]$baselineEnvelope.body)
  )
  $triggerCurrent = Get-SpotConnectTimeoutTriggerState -Body (
    ConvertFrom-JsonOrNull -Text ([string]$finalEnvelope.body)
  )
  $rawIndex += [ordered]@{
    sample = $sample
    endpoint = "observability_errors"
    relative_path = (Split-Path -Leaf $triggerCompactPollPath)
    status_code = $null
    ok = $triggerMonitorIntegrityStatus.StartsWith(
      "complete-",
      [StringComparison]::Ordinal
    )
    storage = "compact_jsonl"
    logical_poll_count = $triggerMonitorPollCount
    monitor_mode = "dedicated-background-job"
  }
  $rawIndex += [ordered]@{
    sample = $sample
    endpoint = "observability_error_monitor"
    relative_path = (Split-Path -Leaf $triggerMonitorSummaryPath)
    status_code = $null
    ok = $true
    storage = "bounded_summary"
    logical_poll_count = $triggerMonitorPollCount
    monitor_mode = "dedicated-background-job"
  }
  if ([bool]$triggerMonitorSummary.trigger_detection_latency_exceeded) {
    Write-Warning (
      "ConnectTimeout detection latency exceeded the evidence-quality threshold: {0}ms > {1}ms." -f
        $triggerMonitorSummary.trigger_detection_latency_ms,
        $triggerMonitorSummary.trigger_detection_latency_warning_ms
    )
  }
}
$collectorProcess.Refresh()
$collectorWorkingSetEndBytes = [int64]$collectorProcess.WorkingSet64
$collectorWorkingSetMaxBytes = [Math]::Max(
  $collectorWorkingSetMaxBytes,
  $collectorWorkingSetEndBytes
)
$observationStopReason = if ($triggerDetected) {
  "spot-connect-timeout-detected"
} elseif ($null -ne $collectionDeadlineAt -and $collectionEndedAt -ge $collectionDeadlineAt) {
  "deadline-reached-without-trigger"
} elseif ($DurationSec -eq 0 -and $sample -ge $Samples) {
  "sample-limit-reached"
} else {
  "collector-stopped"
}
if (-not $StopOnNewSpotConnectTimeout) {
  Write-CaptureStopSignal `
    -Path $CaptureStopSignalPath `
    -StopReason $observationStopReason `
    -TriggerDetected $triggerDetected `
    -Baseline $triggerBaseline `
    -Current $triggerCurrent `
    -TriggerDetectedAt $triggerDetectedAt `
    -CollectionEndedAt $collectionEndedAt
}

$statsSamples = @()
$errorSamples = @()
$spotConfigSamples = @()
Get-ChildItem -LiteralPath $rawRoot -Filter "sample_*_stats.json" | Sort-Object Name | ForEach-Object {
  $envelope = Get-Content -Raw -Encoding UTF8 -LiteralPath $_.FullName | ConvertFrom-Json
  $sampleIndex = [int]($envelope.sample)
  $statsSamples += ConvertTo-SafeStatsSample -Envelope $envelope -SampleIndex $sampleIndex
}
$errorSnapshotFiles = if ($StopOnNewSpotConnectTimeout) {
  @(
    Get-ChildItem -LiteralPath $rawRoot -File |
      Where-Object {
        $_.Name -eq "trigger_baseline_observability_errors.json" -or
        $_.Name -like "trigger_change_*_observability_errors.json" -or
        $_.Name -eq "trigger_final_observability_errors.json"
      } |
      Sort-Object Name
  )
} else {
  @(
    Get-ChildItem `
      -LiteralPath $rawRoot `
      -Filter "sample_*_observability_errors.json" |
      Sort-Object Name
  )
}
foreach ($errorSnapshotFile in $errorSnapshotFiles) {
  $envelope = Get-Content `
    -Raw `
    -Encoding UTF8 `
    -LiteralPath $errorSnapshotFile.FullName |
    ConvertFrom-Json
  $errorSamples += ConvertTo-SafeErrorSample -Envelope $envelope
}
Get-ChildItem -LiteralPath $rawRoot -Filter "sample_*_spot_config.json" | Sort-Object Name | ForEach-Object {
  $envelope = Get-Content -Raw -Encoding UTF8 -LiteralPath $_.FullName | ConvertFrom-Json
  $spotConfigSamples += ConvertTo-SafeSpotConfigSample -Envelope $envelope
}

$hashManifest = New-RawHashManifest -RawRoot $rawRoot -SanitizedRoot $sanitizedRoot
$runAnalysis = ConvertTo-RunAnalysis -StatsSamples $statsSamples -ErrorSamples $errorSamples

$summary = [ordered]@{
  generated_at = Get-Date -Format "o"
  api_base_label = "configured-target"
  sample_count = $sample
  collection_started_at = $collectionStartedAt.ToString("o")
  collection_deadline_at = if ($null -eq $collectionDeadlineAt) { $null } else { $collectionDeadlineAt.ToString("o") }
  collection_ended_at = $collectionEndedAt.ToString("o")
  collection_elapsed_sec = [Math]::Round(($collectionEndedAt - $collectionStartedAt).TotalSeconds, 3)
  deadline_overrun_ms = if ($null -eq $collectionDeadlineAt) {
    $null
  } else {
    [Math]::Max(
      0,
      [Math]::Round(($collectionEndedAt - $collectionDeadlineAt).TotalMilliseconds, 1)
    )
  }
  deadline_remaining_ms = if ($null -eq $collectionDeadlineAt) {
    $null
  } else {
    [Math]::Max(
      0,
      [Math]::Round(($collectionDeadlineAt - $collectionEndedAt).TotalMilliseconds, 1)
    )
  }
  duration_sec_requested = $DurationSec
  interval_sec = $IntervalSec
  normal_endpoint_interval_sec = $NormalEndpointIntervalSec
  memory_state_interval_sec = $MemoryStateIntervalSec
  memory_details_interval_sec = $MemoryDetailsIntervalSec
  observation_stop_reason = $observationStopReason
  event_trigger = [ordered]@{
    enabled = [bool]$StopOnNewSpotConnectTimeout
    detected = $triggerDetected
    source = if ($triggerDetected) { "spot_image" } else { $null }
    error_type = if ($triggerDetected) { "ConnectTimeout" } else { $null }
    detected_at = if ($null -eq $triggerDetectedAt) {
      $null
    } else {
      $triggerDetectedAt.ToString("o")
    }
    error_at = if ($null -eq $triggerCurrent -or
      $null -eq $triggerCurrent.LatestErrorAt) {
      $null
    } else {
      $triggerCurrent.LatestErrorAt.ToString("o")
    }
    baseline_item_count = if ($null -eq $triggerBaseline) {
      0
    } else {
      [int]$triggerBaseline.ItemCount
    }
    baseline_repeat_total = if ($null -eq $triggerBaseline) {
      0
    } else {
      [int]$triggerBaseline.RepeatTotal
    }
    observed_item_count = if ($null -eq $triggerCurrent) {
      0
    } else {
      [int]$triggerCurrent.ItemCount
    }
    observed_repeat_total = if ($null -eq $triggerCurrent) {
      0
    } else {
      [int]$triggerCurrent.RepeatTotal
    }
    monitor_poll_count = $triggerMonitorPollCount
    monitor_error_count = $triggerMonitorErrorCount
    monitor_recovered_error_count = $triggerMonitorRecoveredErrorCount
    monitor_unrecovered_error_count = $triggerMonitorUnrecoveredErrorCount
    monitor_max_consecutive_error_count =
      $triggerMonitorMaxConsecutiveErrorCount
    monitor_integrity_status = $triggerMonitorIntegrityStatus
    monitor_integrity_policy = $triggerMonitorIntegrityPolicy
    monitor_mode = if ($StopOnNewSpotConnectTimeout) {
      "dedicated-background-job"
    } else {
      $null
    }
    compact_poll_schema = if ($StopOnNewSpotConnectTimeout) {
      "observability-error-poll-compact-v2"
    } else {
      $null
    }
    compact_poll_count = if ($StopOnNewSpotConnectTimeout) {
      $triggerMonitorPollCount
    } else {
      0
    }
    full_snapshot_policy = if ($StopOnNewSpotConnectTimeout) {
      "baseline-change-trigger-final"
    } else {
      "every-sample"
    }
    full_snapshot_count = if ($StopOnNewSpotConnectTimeout) {
      $triggerFullSnapshotCount
    } else {
      $errorSamples.Count
    }
    change_snapshot_count = $triggerChangeSnapshotCount
    detection_latency_ms = if ($null -eq $triggerMonitorSummary) {
      $null
    } else {
      $triggerMonitorSummary.trigger_detection_latency_ms
    }
    detection_latency_warning_ms = if ($null -eq $triggerMonitorSummary) {
      $null
    } else {
      $triggerMonitorSummary.trigger_detection_latency_warning_ms
    }
    detection_quality = if ($null -eq $triggerMonitorSummary) {
      $null
    } else {
      $triggerMonitorSummary.trigger_detection_quality
    }
    detection_latency_exceeded = if ($null -eq $triggerMonitorSummary) {
      $false
    } else {
      [bool]$triggerMonitorSummary.trigger_detection_latency_exceeded
    }
    poll_gap_ms_p95 = if ($null -eq $triggerMonitorSummary) {
      $null
    } else {
      $triggerMonitorSummary.poll_gap_ms_p95
    }
    poll_gap_ms_max = if ($null -eq $triggerMonitorSummary) {
      $null
    } else {
      $triggerMonitorSummary.poll_gap_ms_max
    }
    request_elapsed_ms_p95 = if ($null -eq $triggerMonitorSummary) {
      $null
    } else {
      $triggerMonitorSummary.request_elapsed_ms_p95
    }
    request_elapsed_ms_max = if ($null -eq $triggerMonitorSummary) {
      $null
    } else {
      $triggerMonitorSummary.request_elapsed_ms_max
    }
    normal_observer_ended_at = if ($StopOnNewSpotConnectTimeout) {
      $normalObserverEndedAt.ToString("o")
    } else {
      $null
    }
    normal_observer_stop_latency_ms = if (
      -not $StopOnNewSpotConnectTimeout -or
      $null -eq $collectionEndedAt
    ) {
      $null
    } else {
      [Math]::Max(
        0,
        [Math]::Round(
          ($normalObserverEndedAt - $collectionEndedAt).TotalMilliseconds,
          1
        )
      )
    }
  }
  collector_process = [ordered]@{
    working_set_start_bytes = $collectorWorkingSetStartBytes
    working_set_end_bytes = $collectorWorkingSetEndBytes
    working_set_max_bytes = $collectorWorkingSetMaxBytes
  }
  endpoints = $endpoints | ForEach-Object { $_.Name }
  raw_index = @($rawIndex)
  stats_samples = @($statsSamples)
  error_samples = @($errorSamples)
  spot_config_samples = @($spotConfigSamples)
  analysis = $runAnalysis
  raw_hash_manifest = @($hashManifest)
  sanitization = [ordered]@{
    spot_image_fact_manifest_paths = "fact_path and capture_root are omitted from sanitized summary; basename and SHA-256 are retained."
  }
}
$summaryPath = Join-Path $sanitizedRoot "operational_observability_summary.json"
$summary | ConvertTo-Json -Depth 32 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

$zipPath = Join-Path $sessionRoot "operational_observability_sanitized.zip"
if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}
$sanitizedPathPattern = Join-Path $sanitizedRoot "*"
Compress-Archive -Path $sanitizedPathPattern -DestinationPath $zipPath -Force

$rawHashTxtPath = Join-Path $sanitizedRoot "raw_file_sha256.txt"
$rawHashBadRows = @(
  $hashManifest | Where-Object {
    $hashText = [string]$_.sha256
    $sizeText = [string]$_.size
    [string]::IsNullOrWhiteSpace([string]$_.basename) -or
      [string]::IsNullOrWhiteSpace([string]$_.relative_path) -or
      $hashText -notmatch "^[a-f0-9]{64}$" -or
      $sizeText -notmatch "^\d+$"
  }
)
$observedRoutes = @($runAnalysis["observed_5xx_routes"])
$finalSourceCounts = @($runAnalysis["final_error_source_counts"])
$finalRouteStatusCounts = @($runAnalysis["final_error_route_status_counts"])

Write-Output "raw_dir=$rawRoot"
Write-Output "sanitized_dir=$sanitizedRoot"
Write-Output "sanitized_zip=$zipPath"
Write-Output "summary_json=$summaryPath"
Write-Output "raw_hash_txt=$rawHashTxtPath"
Write-Output "raw_hash_rows=$($hashManifest.Count)"
Write-Output "raw_hash_bad_rows=$($rawHashBadRows.Count)"
Write-Output "observed_5xx_routes_count=$($observedRoutes.Count)"
Write-Output "final_error_source_counts_count=$($finalSourceCounts.Count)"
Write-Output "final_error_route_status_counts_count=$($finalRouteStatusCounts.Count)"
Write-Output "trigger_error_compact_poll_count=$triggerMonitorPollCount"
Write-Output "trigger_error_full_snapshot_count=$triggerFullSnapshotCount"
Write-Output "trigger_error_change_snapshot_count=$triggerChangeSnapshotCount"
