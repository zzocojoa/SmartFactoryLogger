param(
  [string]$ApiBase = "http://127.0.0.1:8000",
  [ValidateRange(1, 100000)]
  [int]$Samples = 60,
  [ValidateRange(0, 86400)]
  [int]$IntervalSec = 60,
  [ValidateRange(1, 300)]
  [int]$TimeoutSec = 10,
  [string]$OutputRoot = ".\.tmp_operational_observability",
  [ValidateRange(1, 300)]
  [int]$ProgressIntervalSec = 30,
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

function Format-ConsoleDuration {
  param([TimeSpan]$Duration)

  $safeDuration = if ($Duration.TotalSeconds -lt 0) {
    [TimeSpan]::Zero
  } else {
    $Duration
  }
  $totalHours = [math]::Floor($safeDuration.TotalHours)
  return ("{0:00}:{1:00}:{2:00}" -f $totalHours, $safeDuration.Minutes, $safeDuration.Seconds)
}

function Write-CollectionProgress {
  param(
    [int]$CompletedSamples,
    [int]$TotalSamples,
    [int]$SampleIntervalSec,
    [DateTime]$StartedAt,
    [DateTime]$ReportedAt
  )

  $percent = [math]::Floor(($CompletedSamples * 100.0) / $TotalSamples)
  $elapsed = $ReportedAt - $StartedAt
  $completedWaitSeconds = [math]::Max(0, ($CompletedSamples - 1) * $SampleIntervalSec)
  $observedWorkSeconds = [math]::Max(0, $elapsed.TotalSeconds - $completedWaitSeconds)
  $averageWorkSeconds = $observedWorkSeconds / $CompletedSamples
  $estimatedSecondsPerRemainingSample = $SampleIntervalSec + $averageWorkSeconds
  $remainingSeconds = [math]::Max(
    0,
    ($TotalSamples - $CompletedSamples) * $estimatedSecondsPerRemainingSample
  )
  $remaining = [TimeSpan]::FromSeconds($remainingSeconds)
  $estimatedEnd = $ReportedAt.Add($remaining)

  Write-Host (
    "[PROGRESS] samples={0}/{1} ({2}%) elapsed={3} remaining_about={4} collection_eta={5}" -f `
      $CompletedSamples,
      $TotalSamples,
      $percent,
      (Format-ConsoleDuration -Duration $elapsed),
      (Format-ConsoleDuration -Duration $remaining),
      $estimatedEnd.ToString("yyyy-MM-dd HH:mm:ss K")
  ) -ForegroundColor Cyan
}

function Test-CollectionProgressDue {
  param(
    [int]$CompletedSamples,
    [int]$TotalSamples,
    [DateTime]$ReportedAt,
    [DateTime]$LastReportedAt,
    [int]$ProgressIntervalSeconds
  )

  return $CompletedSamples -eq 1 -or
    $CompletedSamples -eq $TotalSamples -or
    ($ReportedAt - $LastReportedAt).TotalSeconds -ge $ProgressIntervalSeconds
}

function Invoke-SelfTest {
  if ((Format-ConsoleDuration -Duration ([TimeSpan]::FromSeconds(-1))) -ne '00:00:00') {
    throw 'Self-test failed: negative duration was not clamped.'
  }
  if ((Format-ConsoleDuration -Duration ([TimeSpan]::FromSeconds(90061))) -ne '25:01:01') {
    throw 'Self-test failed: duration over 24 hours was not formatted correctly.'
  }

  $startedAt = [DateTime]'2026-01-01T00:00:00'
  $firstDue = Test-CollectionProgressDue `
    -CompletedSamples 1 -TotalSamples 4 `
    -ReportedAt $startedAt -LastReportedAt $startedAt `
    -ProgressIntervalSeconds 30
  $middleNotDue = Test-CollectionProgressDue `
    -CompletedSamples 2 -TotalSamples 4 `
    -ReportedAt $startedAt.AddSeconds(29) -LastReportedAt $startedAt `
    -ProgressIntervalSeconds 30
  $middleDue = Test-CollectionProgressDue `
    -CompletedSamples 2 -TotalSamples 4 `
    -ReportedAt $startedAt.AddSeconds(30) -LastReportedAt $startedAt `
    -ProgressIntervalSeconds 30
  $finalDue = Test-CollectionProgressDue `
    -CompletedSamples 4 -TotalSamples 4 `
    -ReportedAt $startedAt.AddSeconds(3) -LastReportedAt $startedAt `
    -ProgressIntervalSeconds 30
  if (-not $firstDue -or $middleNotDue -or -not $middleDue -or -not $finalDue) {
    throw 'Self-test failed: progress cadence decision.'
  }

  $progressText = Write-CollectionProgress `
    -CompletedSamples 2 -TotalSamples 4 -SampleIntervalSec 1 `
    -StartedAt $startedAt -ReportedAt $startedAt.AddSeconds(3) 6>&1 |
      Out-String
  if ($progressText -notmatch 'samples=2/4 \(50%\)' -or
      $progressText -notmatch 'elapsed=00:00:03' -or
      $progressText -notmatch 'remaining_about=') {
    throw 'Self-test failed: progress output.'
  }

  $sensitiveError = [pscustomobject]@{
    time_iso = '2026-01-01T00:00:00Z'
    source = 'plc_driver'
    error_type = 'ValueError'
    message = 'secret payload from C:\Users\operator at 10.1.10.50'
    status_code = 500
    path = 'C:\Users\operator\private\response.bin'
    level = 'error'
    repeat = 1
  }
  $safeError = ConvertTo-SafeErrorItem -Item $sensitiveError
  $safeErrorJson = $safeError | ConvertTo-Json -Compress
  if ($safeErrorJson -match 'secret|C:\\Users|10\.1\.10\.50|response\.bin' -or
      $safeError.message -notmatch '^sha256:[a-f0-9]{64}$' -or
      $safeError.path -notmatch '^sha256:[a-f0-9]{64}$' -or
      -not $safeError.message_redacted -or
      -not $safeError.path_redacted) {
    throw 'Self-test failed: sensitive error fields were not redacted.'
  }
  $safeRouteError = ConvertTo-SafeErrorItem -Item ([pscustomobject]@{
    message = ''; path = '/api/spot/image.jpg'; repeat = 1
  })
  if ($safeRouteError.path -ne '/api/spot/image.jpg' -or $safeRouteError.path_redacted) {
    throw 'Self-test failed: bounded API route was not preserved.'
  }
  $safeSummary = ConvertTo-SafeErrorSummary -Summary ([pscustomobject]@{
    queue_size = 1
    last_error_message = 'secret summary payload at 10.1.10.50'
    path_counts = @{ 'C:\Users\operator\private\response.bin' = 1 }
    top_messages = @(@{ key = 'secret summary payload at 10.1.10.50'; count = 1 })
    top_paths = @(@{ key = 'C:\Users\operator\private\response.bin'; count = 1 })
  })
  $safeSummaryJson = $safeSummary | ConvertTo-Json -Depth 8 -Compress
  if ($safeSummaryJson -match 'secret|10\.1\.10\.50|C:\\Users|response\.bin' -or
      $safeSummary.last_error_message -notmatch '^sha256:[a-f0-9]{64}$' -or
      -not $safeSummary.message_and_path_details_redacted) {
    throw 'Self-test failed: sensitive error summary fields were not redacted.'
  }
  $sensitiveStatsBody = [ordered]@{
    window = [ordered]@{
      window_sec = 60
      top_paths = @([ordered]@{
        path = 'C:\Users\operator\private\stats-route'
        count = 1
      })
    }
    errors = [ordered]@{
      last_error_message = 'secret stats error at 10.1.10.50'
    }
    polling = [ordered]@{
      paths = [ordered]@{
        'C:\Users\operator\private\polling-route' = [ordered]@{ count = 1 }
      }
    }
  }
  $safeStats = ConvertTo-SafeStatsSample -Envelope ([pscustomobject]@{
    body = ($sensitiveStatsBody | ConvertTo-Json -Depth 8 -Compress)
    status_code = 200
  }) -SampleIndex 1
  $safeStatsJson = $safeStats | ConvertTo-Json -Depth 12 -Compress
  if ($safeStatsJson -match 'secret|10\.1\.10\.50|C:\\Users|stats-route|polling-route') {
    throw 'Self-test failed: sensitive stats path or error summary remained.'
  }

  Write-Output 'SELF_TEST_PASS'
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

function Get-SafeFingerprintLabel {
  param([object]$Value)

  $fingerprint = New-Sha256Text -Text ([string]$Value)
  if ($null -eq $fingerprint) {
    return $null
  }
  return 'sha256:{0}' -f $fingerprint
}

function Get-SafePathLabel {
  param([object]$Value)

  $text = [string]$Value
  if ([string]::IsNullOrWhiteSpace($text)) {
    return $null
  }
  $isBoundedApiRoute = $text.Length -le 256 -and
    $text -match '^/[A-Za-z0-9._~!$&''()*+,;=:@%/-]+$' -and
    $text -notmatch '(?:^|/)\.\.(?:/|$)' -and
    $text -notmatch '//'
  if ($isBoundedApiRoute) {
    return $text
  }
  return Get-SafeFingerprintLabel -Value $text
}

function ConvertTo-SafeErrorItem {
  param([object]$Item)

  $messageText = [string](Get-PropertyValue -Object $Item -Name "message")
  $pathText = [string](Get-PropertyValue -Object $Item -Name "path")
  $safeMessage = Get-SafeFingerprintLabel -Value $messageText
  $safePath = Get-SafePathLabel -Value $pathText

  return [ordered]@{
    time_iso = Get-PropertyValue -Object $Item -Name "time_iso"
    source = Get-PropertyValue -Object $Item -Name "source"
    error_type = Get-PropertyValue -Object $Item -Name "error_type"
    message = $safeMessage
    message_redacted = -not [string]::IsNullOrWhiteSpace($messageText)
    status_code = Get-PropertyValue -Object $Item -Name "status_code"
    path = $safePath
    path_redacted = -not [string]::IsNullOrWhiteSpace($pathText) -and $safePath -ne $pathText
    level = Get-PropertyValue -Object $Item -Name "level"
    repeat = Get-PropertyValue -Object $Item -Name "repeat"
  }
}

function ConvertTo-SafeErrorSummary {
  param([object]$Summary)

  if ($null -eq $Summary) {
    return $null
  }
  return [ordered]@{
    queue_size = Get-PropertyValue -Object $Summary -Name "queue_size"
    repeat_total = Get-PropertyValue -Object $Summary -Name "repeat_total"
    last_error_at = Get-PropertyValue -Object $Summary -Name "last_error_at"
    last_error_source = Get-PropertyValue -Object $Summary -Name "last_error_source"
    last_error_message = Get-SafeFingerprintLabel -Value (
      Get-PropertyValue -Object $Summary -Name "last_error_message"
    )
    last_error_repeat = Get-PropertyValue -Object $Summary -Name "last_error_repeat"
    source_counts = Get-PropertyValue -Object $Summary -Name "source_counts"
    source_repeat_counts = Get-PropertyValue -Object $Summary -Name "source_repeat_counts"
    type_counts = Get-PropertyValue -Object $Summary -Name "type_counts"
    status_counts = Get-PropertyValue -Object $Summary -Name "status_counts"
    top_sources = Get-PropertyValue -Object $Summary -Name "top_sources"
    top_types = Get-PropertyValue -Object $Summary -Name "top_types"
    top_statuses = Get-PropertyValue -Object $Summary -Name "top_statuses"
    message_and_path_details_redacted = $true
  }
}

function ConvertTo-SafeWindowMetrics {
  param([object]$Window)

  if ($null -eq $Window) {
    return $null
  }
  $safeTopPaths = @()
  foreach ($item in @((Get-PropertyValue -Object $Window -Name "top_paths"))) {
    if ($null -eq $item) {
      continue
    }
    $safeTopPaths += [ordered]@{
      path = Get-SafePathLabel -Value (Get-PropertyValue -Object $item -Name "path")
      count = Get-PropertyValue -Object $item -Name "count"
      error_rate = Get-PropertyValue -Object $item -Name "error_rate"
      avg_latency_ms = Get-PropertyValue -Object $item -Name "avg_latency_ms"
    }
  }
  return [ordered]@{
    window_sec = Get-PropertyValue -Object $Window -Name "window_sec"
    request_count = Get-PropertyValue -Object $Window -Name "request_count"
    error_count = Get-PropertyValue -Object $Window -Name "error_count"
    http_error_count = Get-PropertyValue -Object $Window -Name "http_error_count"
    http_4xx_count = Get-PropertyValue -Object $Window -Name "http_4xx_count"
    http_5xx_count = Get-PropertyValue -Object $Window -Name "http_5xx_count"
    error_rate = Get-PropertyValue -Object $Window -Name "error_rate"
    avg_latency_ms = Get-PropertyValue -Object $Window -Name "avg_latency_ms"
    p95_latency_ms = Get-PropertyValue -Object $Window -Name "p95_latency_ms"
    requests_per_sec = Get-PropertyValue -Object $Window -Name "requests_per_sec"
    top_paths = $safeTopPaths
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
      $safePath = Get-SafePathLabel -Value $pathProperty.Name
      $pollingPaths[$safePath] = [ordered]@{
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
    collected_at = Get-Date -Format "o"
    response_status = Get-PropertyValue -Object $Envelope -Name "status_code"
    total_http_5xx_count = Get-PropertyValue -Object $body -Name "total_http_5xx_count"
    total_http_4xx_count = Get-PropertyValue -Object $body -Name "total_http_4xx_count"
    error_count = Get-PropertyValue -Object $body -Name "error_count"
    window = ConvertTo-SafeWindowMetrics -Window (Get-PropertyValue -Object $body -Name "window")
    errors = ConvertTo-SafeErrorSummary -Summary (Get-PropertyValue -Object $body -Name "errors")
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

if ($SelfTest) {
  Invoke-SelfTest
  exit 0
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$sessionRoot = Join-Path $OutputRoot "operational_observability_$timestamp"
$rawRoot = Join-Path $sessionRoot "raw"
$sanitizedRoot = Join-Path $sessionRoot "sanitized"
New-Item -ItemType Directory -Path $rawRoot -Force | Out-Null
New-Item -ItemType Directory -Path $sanitizedRoot -Force | Out-Null

$endpoints = @(
  @{ Name = "health"; Path = "/health" },
  @{ Name = "stats"; Path = "/stats" },
  @{ Name = "observability_errors"; Path = "/api/observability/errors?limit=200" },
  @{ Name = "memory_state"; Path = "/api/memory/state" },
  @{ Name = "memory_details"; Path = "/api/memory/details" },
  @{ Name = "spot_config"; Path = "/api/spot/config" }
)

$rawIndex = @()
$collectionStartedAt = Get-Date
$plannedCollectionSeconds = [math]::Max(0, ($Samples - 1) * $IntervalSec)
$plannedCollectionEndAt = $collectionStartedAt.AddSeconds($plannedCollectionSeconds)
$lastProgressAt = [DateTime]::MinValue
Write-Host (
  "[PROGRESS] collection_started={0} planned_collection_end={1} progress_interval={2}s" -f `
    $collectionStartedAt.ToString("yyyy-MM-dd HH:mm:ss K"),
    $plannedCollectionEndAt.ToString("yyyy-MM-dd HH:mm:ss K"),
    $ProgressIntervalSec
) -ForegroundColor Cyan
Write-Host '[PROGRESS] The planned end covers timed sampling. Sanitization and ZIP creation follow.' -ForegroundColor Cyan
for ($sample = 1; $sample -le $Samples; $sample += 1) {
  foreach ($endpoint in $endpoints) {
    $uri = Join-ApiUrl -Base $ApiBase -Path $endpoint.Path
    $result = Invoke-ReadOnlyEndpoint -Uri $uri -Timeout $TimeoutSec
    $rawFile = Join-Path $rawRoot ("sample_{0:d3}_{1}.json" -f $sample, $endpoint.Name)
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
    $envelope | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $rawFile -Encoding UTF8
    $rawIndex += [ordered]@{
      sample = $sample
      endpoint = $endpoint.Name
      relative_path = (Split-Path -Leaf $rawFile)
      status_code = $result.status_code
      ok = $result.ok
    }
  }

  $progressAt = Get-Date
  $progressDue = Test-CollectionProgressDue `
    -CompletedSamples $sample `
    -TotalSamples $Samples `
    -ReportedAt $progressAt `
    -LastReportedAt $lastProgressAt `
    -ProgressIntervalSeconds $ProgressIntervalSec
  if ($progressDue) {
    Write-CollectionProgress `
      -CompletedSamples $sample `
      -TotalSamples $Samples `
      -SampleIntervalSec $IntervalSec `
      -StartedAt $collectionStartedAt `
      -ReportedAt $progressAt
    $lastProgressAt = $progressAt
  }

  if ($sample -lt $Samples -and $IntervalSec -gt 0) {
    Start-Sleep -Seconds $IntervalSec
  }
}

Write-Host '[PROGRESS] Timed sampling complete. Post-processing 1/3: build sanitized summaries and hashes.' -ForegroundColor Cyan
$statsSamples = @()
$errorSamples = @()
$spotConfigSamples = @()
Get-ChildItem -LiteralPath $rawRoot -Filter "sample_*_stats.json" | Sort-Object Name | ForEach-Object {
  $envelope = Get-Content -Raw -Encoding UTF8 -LiteralPath $_.FullName | ConvertFrom-Json
  $sampleIndex = [int]($envelope.sample)
  $statsSamples += ConvertTo-SafeStatsSample -Envelope $envelope -SampleIndex $sampleIndex
}
Get-ChildItem -LiteralPath $rawRoot -Filter "sample_*_observability_errors.json" | Sort-Object Name | ForEach-Object {
  $envelope = Get-Content -Raw -Encoding UTF8 -LiteralPath $_.FullName | ConvertFrom-Json
  $body = ConvertFrom-JsonOrNull -Text ([string]$envelope.body)
  $items = @()
  foreach ($item in @((Get-PropertyValue -Object $body -Name "items"))) {
    if ($null -ne $item) {
      $items += ConvertTo-SafeErrorItem -Item $item
    }
  }
  $errorSamples += [ordered]@{
    sample = [int]$envelope.sample
    response_status = $envelope.status_code
    summary = ConvertTo-SafeErrorSummary -Summary (Get-PropertyValue -Object $body -Name "summary")
    items = $items
  }
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
  sample_count = $Samples
  interval_sec = $IntervalSec
  endpoints = $endpoints | ForEach-Object { $_.Name }
  raw_index = @($rawIndex)
  stats_samples = @($statsSamples)
  error_samples = @($errorSamples)
  spot_config_samples = @($spotConfigSamples)
  analysis = $runAnalysis
  raw_hash_manifest = @($hashManifest)
  sanitization = [ordered]@{
    spot_image_fact_manifest_paths = "fact_path and capture_root are omitted from sanitized summary; basename and SHA-256 are retained."
    observability_error_messages = "Error messages are replaced with SHA-256 fingerprints; non-bounded API paths and message/path summary details are omitted or fingerprinted."
  }
}
$summaryPath = Join-Path $sanitizedRoot "operational_observability_summary.json"
$summary | ConvertTo-Json -Depth 32 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-Host '[PROGRESS] Post-processing 2/3: create the app observability sanitized ZIP.' -ForegroundColor Cyan
$zipPath = Join-Path $sessionRoot "operational_observability_sanitized.zip"
if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}
$sanitizedPathPattern = Join-Path $sanitizedRoot "*"
Compress-Archive -Path $sanitizedPathPattern -DestinationPath $zipPath -Force
Write-Host '[PROGRESS] Post-processing 3/3: app observability export complete.' -ForegroundColor Green

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
