param(
  [string]$ApiBase = "http://127.0.0.1:8000",
  [int]$Samples = 60,
  [int]$IntervalSec = 60,
  [int]$TimeoutSec = 10,
  [string]$OutputRoot = ".\.tmp_operational_observability"
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
    collected_at = Get-Date -Format "o"
    response_status = Get-PropertyValue -Object $Envelope -Name "status_code"
    total_http_5xx_count = Get-PropertyValue -Object $body -Name "total_http_5xx_count"
    total_http_4xx_count = Get-PropertyValue -Object $body -Name "total_http_4xx_count"
    error_count = Get-PropertyValue -Object $body -Name "error_count"
    window = Get-PropertyValue -Object $body -Name "window"
    errors = Get-PropertyValue -Object $body -Name "errors"
    polling_paths = $pollingPaths
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

  if ($sample -lt $Samples -and $IntervalSec -gt 0) {
    Start-Sleep -Seconds $IntervalSec
  }
}

$statsSamples = @()
$errorSamples = @()
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
    summary = Get-PropertyValue -Object $body -Name "summary"
    items = $items
  }
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
  analysis = $runAnalysis
  raw_hash_manifest = @($hashManifest)
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
