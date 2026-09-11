[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [Parameter(Mandatory=$true)][string]$PythonPath,
    [ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedCommit=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$native=Join-Path ([Environment]::SystemDirectory) 'WindowsPowerShell\v1.0\powershell.exe'
if (-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
    $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
    [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native) {
    throw 'Native x64 Windows PowerShell 5.1 required.'
}
$workspace=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$actualCommit=(& git -C $workspace rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $actualCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'Tooling commit unavailable.' }
if ($ExpectedCommit -ne '') {
    if ($actualCommit -cne $ExpectedCommit) { throw 'Tooling checkout commit mismatch.' }
    $dirty=@(& git -C $workspace status --porcelain --untracked-files=all -- scripts/canary-v1026 `
        scripts/pinned/spot-diagnostic-core-9b38171a scripts/backend_bundle_integrity.psm1 `
        ../.gitattributes ../.github/workflows/canary-offline-ci.yml)
    if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw 'ExpectedCommit requires clean CI input files.' }
}
$savedModules=$env:PSModulePath
try {
    $env:PSModulePath=Join-Path ([IO.Path]::GetDirectoryName($native)) 'Modules'
    Import-Module (Join-Path $PSScriptRoot 'evidence_zip_integrity.psm1') -Force -DisableNameChecking
    Assert-EvidencePlainPath $OutputRoot
    if (Test-Path -LiteralPath $OutputRoot) { throw 'CI output must be a new directory; prior results are preserved.' }
    $root=[IO.Path]::GetFullPath($OutputRoot)
    if ($root.StartsWith($PSScriptRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'CI output cannot be inside tooling source.' }
    $null=[IO.Directory]::CreateDirectory($root)
    $builder=Join-Path $PSScriptRoot 'build-canary-kit.ps1'
    $checks=[Collections.Generic.List[string]]::new()
    function Check {
        param([bool]$Ok,[string]$Label)
        if (-not $Ok) { throw ('CI contract failed: '+$Label) }
        $checks.Add($Label)
    }
    function Rejected-Invocation {
        param([string[]]$Argv,[string]$Label)
        $saved=$ErrorActionPreference
        try {
            $ErrorActionPreference='Continue'
            $null=& $native -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass @Argv 2>&1
            $code=$LASTEXITCODE
        } finally { $ErrorActionPreference=$saved }
        Check ($code -ne 0) $Label
    }
    $negativeRoot=Join-Path $root 'negative-output-must-not-exist'
    $missingRelease=Join-Path $root 'missing-installer-candidate'
    Rejected-Invocation @('-File',$builder,'-ReviewOnly','-OfflineCi','-ReleaseKitRoot',$missingRelease,'-OutputRoot',$negativeRoot) 'mixed-mode-rejected'
    Rejected-Invocation @('-File',$builder,'-ReviewOnly','-OutputRoot',$negativeRoot) 'release-root-required'
    Rejected-Invocation @('-File',$builder,'-ReviewOnly','-ReleaseKitRoot',$missingRelease,'-OutputRoot',$negativeRoot) 'missing-release-rejected'
    foreach ($disabledSwitch in @('OfflineCi','ReviewOnly')) {
        $fixture=Join-Path $root ('disabled-'+$disabledSwitch+'.ps1')
        $quotedBuilder=$builder.Replace("'","''"); $quotedOutput=$negativeRoot.Replace("'","''")
        $flags=if ($disabledSwitch -ceq 'OfflineCi') { '-OfflineCi:$false -ReviewOnly' } else { '-OfflineCi -ReviewOnly:$false' }
        $scriptText="& '$quotedBuilder' $flags -OutputRoot '$quotedOutput'"
        $bytes=[Text.UTF8Encoding]::new($false).GetBytes($scriptText)
        $stream=[IO.File]::Open($fixture,'CreateNew','Write','None')
        try { $stream.Write($bytes,0,$bytes.Length) } finally { $stream.Dispose() }
        Rejected-Invocation @('-File',$fixture) ('disabled-'+$disabledSwitch+'-rejected')
    }
    Check (-not (Test-Path -LiteralPath $negativeRoot)) 'negative-modes-no-output-or-pass-receipt'
    Write-Host '[CI] Mode boundary negatives passed. Running identical offline kit regressions.'
    $runs=Join-Path $root 'runs'
    & $native -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $builder `
        -OfflineCi -ReviewOnly -PythonPath $PythonPath -OutputRoot $runs |
        Tee-Object -FilePath (Join-Path $root 'ci-runner.log')
    if ($LASTEXITCODE -ne 0) { throw 'Offline CI builder failed; no runner PASS will be issued.' }
    $receipts=@(Get-ChildItem -LiteralPath $runs -Recurse -File -Filter 'ci-result.json')
    Check ($receipts.Count -eq 1) 'exactly-one-ci-receipt'
    $ci=[IO.File]::ReadAllText($receipts[0].FullName) | ConvertFrom-Json
    Check ($ci.result -ceq 'V1026_CANARY_OFFLINE_CI_PASS' -and
        $ci.fixture_kind -ceq 'SYNTHETIC_TOOLING_ONLY_NOT_RELEASE_VALIDATION') 'ci-not-release-verdict'
    Check ($ci.port_regression.result -ceq 'V1026_CANARY_PORT_REGRESSION_PASS' -and
        $ci.port_regression.tests_passed -ge 71 -and
        $ci.port_regression.tests_passed -eq @($ci.port_regression.tests).Count) 'all-port-regressions-present'
    foreach ($name in @('release_candidate_verified','distribution_package_created','server_context_bound',
        'server_execution_authorized','observation_started','full_120m_allowed','production_promotion_allowed')) {
        Check ($ci.$name -is [bool] -and -not $ci.$name) ('false-'+$name)
    }
    Check ($ci.loopback_integration_passed -is [bool] -and $ci.loopback_integration_passed) 'loopback-integration-passed'
    Check ($ci.tooling_parent_commit -ceq $actualCommit) 'tooling-commit-consistent'
    $forbidden=@(Get-ChildItem -LiteralPath $runs -Recurse -File | Where-Object {
        $_.Name -in @('build-result.json','v1026-canary-review-only.zip','v1026-canary-review-only.zip.sha256.txt')
    })
    Check ($forbidden.Count -eq 0) 'no-release-review-output'
    $zip=Test-VerifiedEvidenceZip -Path $ci.fixture_archive.path -Entries $ci.fixture_archive.entries -ExpectedSha256 $ci.fixture_archive.sha256
    Check ($zip.entry_count -eq 15 -and (Split-Path -Leaf $zip.path) -ceq 'fixture-kit-not-for-distribution.zip') 'fixture-zip-reopened'
    $result=[ordered]@{
        schema_version='v1026-canary-ci-runner-v1'; result='V1026_CANARY_CI_RUNNER_PASS'
        tooling_checked_out_commit=$actualCommit; expected_commit_verified=($ExpectedCommit -ne '')
        checks_passed=$checks.Count; checks=$checks.ToArray(); port_regression_count=$ci.port_regression.tests_passed
        fixture_zip_entries=$zip.entry_count; release_candidate_verified=$false
        server_execution_authorized=$false; observation_started=$false; production_promotion_allowed=$false
    }
    Write-EvidenceJsonNew (Join-Path $root 'ci-runner-result.json') $result | Out-Null
    [pscustomobject]$result | ConvertTo-Json -Depth 5
} finally { $env:PSModulePath=$savedModules }
