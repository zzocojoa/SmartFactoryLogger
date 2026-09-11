[CmdletBinding()]
param(
    [string]$ControllerPath = "",

    [string]$CollectorPath = "",

    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-FunctionStringConstants {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$FunctionName
    )

    $tokens = $null
    $errors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile(
        $Path,
        [ref]$tokens,
        [ref]$errors
    )
    if (@($errors).Count -ne 0) {
        throw "PowerShell parse failed: $Path"
    }

    $functions = @(
        $ast.FindAll(
            {
                param($node)
                $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
                    $node.Name -ceq $FunctionName
            },
            $true
        )
    )
    if ($functions.Count -ne 1) {
        throw (
            "Expected exactly one function named $FunctionName in $Path; " +
            "found=$($functions.Count)"
        )
    }

    return @(
        $functions[0].Body.FindAll(
            {
                param($node)
                $node -is [Management.Automation.Language.StringConstantExpressionAst]
            },
            $true
        ) |
            ForEach-Object { [string]$_.Value } |
            Where-Object { $_ -cmatch '^[a-z][a-z0-9_]+$' } |
            Select-Object -Unique
    )
}

function Assert-ObservationCounterCoverage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Controller,

        [Parameter(Mandatory = $true)]
        [string]$Collector
    )

    foreach ($path in @($Controller, $Collector)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required contract source is missing: $path"
        }
    }

    $required = @(
        Get-FunctionStringConstants `
            -Path $Controller `
            -FunctionName "Get-CumulativeFailureCounterNames" |
            Where-Object { $_ -cne "image_cache_clock_anomaly_count" } |
            Sort-Object -Unique
    )
    $collected = @(
        Get-FunctionStringConstants `
            -Path $Collector `
            -FunctionName "Get-SafeSpotImageSnapshot" |
            Sort-Object -Unique
    )
    $missing = @(
        $required | Where-Object { $_ -cnotin $collected }
    )

    if ($required.Count -eq 0) {
        throw "The controller observation failure-counter contract is empty."
    }
    if ($missing.Count -ne 0) {
        throw (
            "Collector observation boundary omits required counters: " +
            ($missing -join ", ")
        )
    }

    return [pscustomobject][ordered]@{
        result = "V1026_CANARY_OBSERVATION_COUNTER_CONTRACT_PASS"
        required_counter_count = $required.Count
        collected_counter_count = $collected.Count
        missing_counters = @()
        controller_path = [IO.Path]::GetFullPath($Controller)
        collector_path = [IO.Path]::GetFullPath($Collector)
    }
}

function Invoke-ObservationCounterContractSelfTest {
    $tempRoot = Join-Path `
        ([IO.Path]::GetTempPath()) `
        ("sfl-counter-contract-{0}" -f [guid]::NewGuid().ToString("N"))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $controllerFixture = Join-Path $tempRoot "controller.ps1"
        $collectorFixture = Join-Path $tempRoot "collector.ps1"
        $utf8 = New-Object Text.UTF8Encoding($false)
        [IO.File]::WriteAllText(
            $controllerFixture,
            @'
function Get-CumulativeFailureCounterNames {
    return @('counter_alpha', 'counter_beta', 'image_cache_clock_anomaly_count')
}
'@,
            $utf8
        )
        [IO.File]::WriteAllText(
            $collectorFixture,
            @'
function Get-SafeSpotImageSnapshot {
    foreach ($name in @('counter_alpha')) { $null = $name }
}
'@,
            $utf8
        )

        $rejected = $false
        try {
            Assert-ObservationCounterCoverage `
                -Controller $controllerFixture `
                -Collector $collectorFixture | Out-Null
        }
        catch {
            $rejected = $_.Exception.Message -cmatch 'counter_beta'
        }
        if (-not $rejected) {
            throw "Self-test accepted a collector with a missing required counter."
        }

        [IO.File]::WriteAllText(
            $collectorFixture,
            @'
function Get-SafeSpotImageSnapshot {
    foreach ($name in @('counter_alpha', 'counter_beta')) { $null = $name }
}
'@,
            $utf8
        )
        Assert-ObservationCounterCoverage `
            -Controller $controllerFixture `
            -Collector $collectorFixture | Out-Null
    }
    finally {
        if (Test-Path -LiteralPath $tempRoot -PathType Container) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }

    Write-Output "V1026_CANARY_OBSERVATION_COUNTER_CONTRACT_SELF_TEST_PASS"
}

if ($SelfTest) {
    Invoke-ObservationCounterContractSelfTest
    exit 0
}

if ([string]::IsNullOrWhiteSpace($ControllerPath)) {
    $ControllerPath = Join-Path `
        $PSScriptRoot `
        "invoke-spot-realtime-image-canary-120m.ps1"
}
if ([string]::IsNullOrWhiteSpace($CollectorPath)) {
    $CollectorPath = Join-Path `
        $PSScriptRoot `
        "collect-spot-connecttimeout-evidence.ps1"
}

$coverage = Assert-ObservationCounterCoverage `
    -Controller $ControllerPath `
    -Collector $CollectorPath
$required = @(Get-FunctionStringConstants -Path $ControllerPath -FunctionName "Get-CumulativeFailureCounterNames" |
    Where-Object { $_ -cne "image_cache_clock_anomaly_count" } | Sort-Object)
$expectedRequired = @(
    "source_port_pool_acquire_wait_count", "source_port_pool_exhaustion_count",
    "source_port_reuse_violation_count", "source_port_transport_failure_count",
    "source_port_bind_retry_exhaustion_count", "source_port_image_failure_count",
    "source_port_temperature_failure_count", "source_port_internal_temperature_failure_count",
    "source_port_diagnostic_failure_count", "source_port_connection_test_failure_count",
    "source_port_request_failure_event_count_total", "source_port_request_failure_event_drop_count",
    "image_refresh_failure_count"
) | Sort-Object
if (($required -join "|") -cne ($expectedRequired -join "|") -or
    $coverage.required_counter_count -ne 13 -or $coverage.collected_counter_count -ne 33) {
    throw "v1026 requires the exact 13 failure counters and 33 collected fields."
}
$coverage
