[CmdletBinding(DefaultParameterSetName='ReleaseReview')]
param(
    [Parameter(Mandatory=$true,ParameterSetName='ReleaseReview')][string]$ReleaseKitRoot,
    [Parameter(Mandatory=$true,ParameterSetName='OfflineCi')][switch]$OfflineCi,
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [Parameter(Mandatory=$true)][switch]$ReviewOnly,
    [string]$PythonPath=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if (-not $ReviewOnly) { throw 'Only explicit local review builds are supported.' }
if ($PSCmdlet.ParameterSetName -ceq 'OfflineCi' -and -not $OfflineCi) { throw 'OfflineCi must be explicitly enabled.' }
$native = Join-Path ([Environment]::SystemDirectory) 'WindowsPowerShell\v1.0\powershell.exe'
if (-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
    $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) { throw 'Use native x64 Windows PowerShell 5.1.' }
Import-Module (Join-Path $PSScriptRoot 'evidence_zip_integrity.psm1') -Force
Import-Module (Join-Path $PSScriptRoot 'v1026_release_identity_integrity.psm1') -Force
$candidate = $null
if (-not $OfflineCi) { $candidate = Test-V1026ReleaseCandidate $ReleaseKitRoot }
$policy = Get-V1026CanaryPolicy
$parentScripts = Split-Path -Parent $PSScriptRoot
if ($PythonPath -eq '') { $PythonPath=Join-Path (Split-Path -Parent $parentScripts) 'backend\.venv\Scripts\python.exe' }
Assert-EvidencePlainPath $PythonPath
if (-not [IO.File]::Exists($PythonPath)) { throw 'Explicit PythonPath is required for the loopback integration fixture.' }
$coreRoot = Join-Path $parentScripts 'pinned\spot-diagnostic-core-9b38171a'
$corePins = [ordered]@{
    'analyze-spot-http-framing.ps1'='DBDDEB253E69174080243103474F77E34A6275A5F52B81273448C051C1D13A99'
    'collect_operational_observability.ps1'='6D395373A7D2C9B70EA38F6DF681A5ED042D814829D82E0988D4B915672EC94C'
    'collect-spot-connecttimeout-evidence.ps1'='9EF68A3251A74EED7DF3CF0B67D2FB04E7247352CBCF77B18F0597A5C92E9F3B'
    'monitor-spot-connecttimeout-trigger.ps1'='A6D46F9FB979ED2247BA34C436AFA5A59F6EC6D7BDCD95DC4E5D8D069A9837F9'
}
function Write-BytesNew {
    param([string]$Path,[byte[]]$Bytes)
    Assert-EvidencePlainPath $Path
    $writer=[IO.File]::Open($Path,'CreateNew','Write','None')
    try { $writer.Write($Bytes,0,$Bytes.Length); $writer.Flush($true) } finally { $writer.Dispose() }
}
function Replace-Once {
    param([string]$Text,[string]$Old,[string]$New)
    if ([regex]::Matches($Text,[regex]::Escape($Old)).Count -ne 1) { throw 'Pinned collector overlay anchor differs.' }
    return $Text.Replace($Old,$New)
}
function Offline-Test {
    param([string]$Name,[string[]]$Arguments=@('-SelfTest'))
    Write-Host ('[OFFLINE TEST] '+$Name)
    & $native -NoProfile -ExecutionPolicy Bypass -File (Join-Path $kit $Name) @Arguments |
        Tee-Object -FilePath (Join-Path $run ('test-'+$Name+'-'+[guid]::NewGuid().ToString('N').Substring(0,8)+'.log'))
    if ($LASTEXITCODE -ne 0) { throw ('Offline self-test failed: '+$Name) }
}

Assert-EvidencePlainPath $OutputRoot
$output=[IO.Path]::GetFullPath($OutputRoot)
if (-not [IO.Directory]::Exists($output)) { $null=[IO.Directory]::CreateDirectory($output) }
$run=Join-Path $output ('canary-v1026-review-'+[DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8))
$null=[IO.Directory]::CreateDirectory($run)
$sourceSnapshot=New-VerifiedEvidenceZip -SourceRoot $PSScriptRoot -Destination (Join-Path $run 'tooling-source-snapshot.zip')
$kit=Join-Path $run 'kit'
$null=[IO.Directory]::CreateDirectory($kit)
$sourceNames=@('README.md','evidence_zip_integrity.psm1','invoke-spot-realtime-image-canary-120m.ps1',
    'release-pins.json','test-v1026-canary-observation-counter-contract.ps1',
    'v1026_release_identity_integrity.psm1','verify-spot-realtime-image-canary-kit.ps1')
foreach ($name in $sourceNames) {
    $source=Join-Path $PSScriptRoot $name
    $spec=@($sourceSnapshot.entries | Where-Object name -CEQ $name)
    if ($spec.Count -ne 1) { throw 'Source snapshot member missing.' }
    Write-BytesNew (Join-Path $kit $name) ([IO.File]::ReadAllBytes($source))
    $copied=Get-EvidenceFileFact (Join-Path $kit $name)
    if ($copied.sha256 -cne $spec[0].sha256 -or $copied.length -ne $spec[0].length) { throw 'Tooling changed while staging.' }
}
$backendModule=Join-Path $parentScripts 'backend_bundle_integrity.psm1'
$backendFact=Get-EvidenceFileFact $backendModule
if ($backendFact.sha256 -cne '4728B78D8EC97DDF25EEC7F411D0686F66CF4FAE46FC378DB426BE79EDCD2BDD') { throw 'Backend integrity core changed.' }
Write-BytesNew (Join-Path $kit 'backend_bundle_integrity.psm1') ([IO.File]::ReadAllBytes($backendModule))
if ((Get-EvidenceFileFact (Join-Path $kit 'backend_bundle_integrity.psm1')).sha256 -cne $backendFact.sha256) { throw 'Backend integrity core changed during copy.' }
foreach ($item in $corePins.GetEnumerator()) {
    $source=Join-Path $coreRoot $item.Key
    $fact=Get-EvidenceFileFact $source
    if ($fact.sha256 -cne $item.Value) { throw ('Diagnostic core changed: '+$item.Key) }
    $bytes=[IO.File]::ReadAllBytes($source)
    $sha=[Security.Cryptography.SHA256]::Create()
    try { if ([BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-','') -cne $item.Value) { throw 'Core changed during read.' } }
    finally { $sha.Dispose() }
    if ($item.Key -ceq 'collect-spot-connecttimeout-evidence.ps1') {
        $text=[Text.UTF8Encoding]::new($false,$true).GetString($bytes).Replace("`r`n","`n")
        $text=Replace-Once $text "        'source_port_bind_collision_count'," "        'source_port_bind_collision_count',`n        'source_port_bind_retry_exhaustion_count',"
        $old=@'
Compress-Archive -Path (Join-Path $sanitizedRoot '*') -DestinationPath $sanitizedZip -Force
$zipHash = Get-FileHash -LiteralPath $sanitizedZip -Algorithm SHA256
$zipHash.Hash.ToLowerInvariant() |
    Set-Content -LiteralPath (Join-Path $evidenceRoot 'sanitized_share_sha256.txt') -Encoding ascii
'@
        $new=@'
Import-Module (Join-Path $PSScriptRoot 'evidence_zip_integrity.psm1') -Force
$zipReceipt = New-VerifiedEvidenceZip -SourceRoot $sanitizedRoot -Destination $sanitizedZip `
    -ReceiptPath (Join-Path $evidenceRoot 'sanitized-zip-completion.json')
$sidecarBytes = [Text.Encoding]::ASCII.GetBytes($zipReceipt.sha256 + "`n")
$sidecar = [IO.File]::Open((Join-Path $evidenceRoot 'sanitized_share_sha256.txt'),'CreateNew','Write','None')
try { $sidecar.Write($sidecarBytes,0,$sidecarBytes.Length); $sidecar.Flush($true) }
finally { $sidecar.Dispose() }
'@
        $text=Replace-Once $text $old $new
        # SelfTest exits above this anchor. No operational collection may start from a review kit.
        $text=Replace-Once $text 'if ([string]::IsNullOrWhiteSpace($ConfigPath)) {' @'
throw 'V1026_SERVER_LAUNCH_BINDING_REQUIRED: review-only collector; no observation authorized.'
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
'@
        $bytes=[Text.UTF8Encoding]::new($false).GetBytes($text)
    }
    Write-BytesNew (Join-Path $kit $item.Key) $bytes
}
Write-EvidenceJsonNew (Join-Path $kit 'canary_kit_identity.json') $policy | Out-Null
Write-EvidenceJsonNew (Join-Path $kit 'operator_attestation_15m.json') ([ordered]@{
    schema_version='spot-operator-visual-attestation-v1'; evidence_kind='pending-server-validation'
    status='PENDING'; product_version='1.0.26'; build_git_commit=$policy.product.build_git_commit
    observation_recorded=$false; continuous_spot_image_refresh_confirmed=$false; no_new_app_error_confirmed=$false
    machine_generated=$true; statement='Placeholder only. No human observation or historic PASS is asserted.'
}) | Out-Null
$manifest=@(foreach ($name in (Get-EvidenceFileNames $kit)) {
    $fact=Get-EvidenceFileFact (Join-Path $kit $name)
    [pscustomobject]@{name=$name;length=$fact.length;sha256=$fact.sha256}
})
Write-EvidenceJsonNew (Join-Path $kit 'canary_kit_files_sha256.json') $manifest | Out-Null
$savedModules=$env:PSModulePath
try {
    $env:PSModulePath=Join-Path ([IO.Path]::GetDirectoryName($native)) 'Modules'
    foreach ($name in @('analyze-spot-http-framing.ps1','monitor-spot-connecttimeout-trigger.ps1',
        'collect_operational_observability.ps1','collect-spot-connecttimeout-evidence.ps1',
        'invoke-spot-realtime-image-canary-120m.ps1','test-v1026-canary-observation-counter-contract.ps1')) { Offline-Test $name }
    Offline-Test 'collect-spot-connecttimeout-evidence.ps1' @('-SelfTest','-ObservationMinutes','120','-StopOnNewSpotConnectTimeout')
    $manifestHash=(Get-EvidenceFileFact (Join-Path $kit 'canary_kit_files_sha256.json')).sha256
    Offline-Test 'verify-spot-realtime-image-canary-kit.ps1' @('-KitRoot',$kit,'-ExpectedManifestSha256',$manifestHash)
    $regressionText=(& $native -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'test-canary-port.ps1') -KitRoot $kit |
        Tee-Object -FilePath (Join-Path $run 'port-regression.json') | Out-String)
    if ($LASTEXITCODE -ne 0) { throw 'Port regression tests failed.' }
    $regression=$regressionText | ConvertFrom-Json
    if ($regression.result -cne 'V1026_CANARY_PORT_REGRESSION_PASS' -or $regression.tests_passed -lt 71 -or
        $regression.tests_passed -ne @($regression.tests).Count) { throw 'Regression receipt missing or incomplete.' }
    Write-Host ('[PORT REGRESSION] passed='+$regression.tests_passed)
    $integrationRoot=Join-Path $run 'integration-fixture\scripts'
    $null=[IO.Directory]::CreateDirectory($integrationRoot)
    $integrationSource=Join-Path $coreRoot 'test_spot_connecttimeout_trigger_collector.py'
    if ((Get-EvidenceFileFact $integrationSource).sha256 -cne '0706A89D68E84A871A64CD688449EFFE62EE18C72E00D1C267180358D6D55968') { throw 'Integration fixture source differs.' }
    foreach ($name in @('collect_operational_observability.ps1','monitor-spot-connecttimeout-trigger.ps1')) {
        Write-BytesNew (Join-Path $integrationRoot $name) ([IO.File]::ReadAllBytes((Join-Path $kit $name)))
    }
    $integrationPath=Join-Path $integrationRoot 'test_spot_connecttimeout_trigger_collector.py'
    Write-BytesNew $integrationPath ([IO.File]::ReadAllBytes($integrationSource))
    if ((Get-EvidenceFileFact $integrationPath).sha256 -cne '0706A89D68E84A871A64CD688449EFFE62EE18C72E00D1C267180358D6D55968') { throw 'Integration fixture changed during copy.' }
    Write-Host '[OFFLINE INTEGRATION] Dedicated random loopback fixture only; no application/server queries.'
    & $PythonPath $integrationPath | Tee-Object -FilePath (Join-Path $run 'trigger-integration.log')
    if ($LASTEXITCODE -ne 0) { throw 'Loopback trigger integration failed.' }
} finally { $env:PSModulePath=$savedModules }
# Bind the source snapshot used for this uncommitted tooling, not merely its HEAD parent.
$sourceAfter=Get-EvidenceFileNames $PSScriptRoot
if (($sourceAfter -join '|') -cne (@($sourceSnapshot.entries.name) -join '|')) { throw 'Tooling source set changed.' }
foreach ($entry in $sourceSnapshot.entries) {
    $fact=Get-EvidenceFileFact (Join-Path $PSScriptRoot $entry.name)
    if ($fact.sha256 -cne $entry.sha256 -or $fact.length -ne $entry.length) { throw 'Tooling source changed during tests.' }
}
$parentCommit=(& git -C $PSScriptRoot rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $parentCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'Tooling parent commit unavailable.' }
if ($OfflineCi) {
    # Test the identical ZIP implementation without issuing a release-review receipt/package.
    $fixtureZip=New-VerifiedEvidenceZip -SourceRoot $kit -Destination (Join-Path $run 'fixture-kit-not-for-distribution.zip')
    Write-EvidenceJsonNew (Join-Path $run 'ci-result.json') ([ordered]@{
        schema_version='v1026-canary-offline-ci-v1'; result='V1026_CANARY_OFFLINE_CI_PASS'
        recorded_at=[DateTimeOffset]::Now.ToString('o'); tooling_parent_commit=$parentCommit
        tooling_source_snapshot=$sourceSnapshot; fixture_archive=$fixtureZip; kit_root=$kit
        kit_manifest_sha256=$manifestHash; port_regression=$regression; loopback_integration_passed=$true
        fixture_kind='SYNTHETIC_TOOLING_ONLY_NOT_RELEASE_VALIDATION'
        release_candidate_verified=$false; distribution_package_created=$false
        server_context_bound=$false; server_execution_authorized=$false; observation_started=$false
        full_120m_allowed=$false; production_promotion_allowed=$false
    }) | Out-Null
    Write-Host '[CI PASS] Synthetic offline tooling only. No installer validation or distribution package.'
    return
}
$zip=New-VerifiedEvidenceZip -SourceRoot $kit -Destination (Join-Path $run 'v1026-canary-review-only.zip')
Write-BytesNew ($zip.path+'.sha256.txt') ([Text.Encoding]::ASCII.GetBytes($zip.sha256+"`n"))
$result=[ordered]@{
    schema_version='v1026-canary-offline-build-v1'; result='V1026_CANARY_PORT_OFFLINE_VERIFIED'
    recorded_at=[DateTimeOffset]::Now.ToString('o'); product=$candidate
    tooling_status='HASH_BOUND_LOCAL_SOURCE_NOT_COMMITTED'; tooling_parent_commit=$parentCommit
    tooling_source_snapshot=$sourceSnapshot; diagnostic_source_commit='9b38171a00616a732d1aa64853d114c946f3bb78'
    diagnostic_source_pins=$corePins; archive=$zip; kit_root=$kit; kit_manifest_sha256=$manifestHash
    port_regression=$regression; loopback_integration_passed=$true
    server_context_bound=$false; server_execution_authorized=$false; observation_started=$false
    prerequisite_15m='PENDING_SERVER_VALIDATION'; full_120m_allowed=$false; production_promotion_allowed=$false
}
Write-EvidenceJsonNew (Join-Path $run 'build-result.json') $result | Out-Null
Write-Host ('[REVIEW ZIP] '+$zip.path)
Write-Host ('[SHA256] '+$zip.sha256)
Write-Host '[DONE] Offline tooling only. No installation, server preflight or observation performed.'
