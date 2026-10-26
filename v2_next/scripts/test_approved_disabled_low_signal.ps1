param([Parameter(Mandatory = $true)][string]$PolicyPath)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$qa = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'qa_spot_temperature_v25.ps1') -Raw
$begin = $qa.IndexOf('# BEGIN QA METADATA HELPERS')
$end = $qa.IndexOf('# END QA METADATA HELPERS')
if ($begin -lt 0 -or $end -le $begin) { throw 'QA helper markers missing' }
. ([scriptblock]::Create($qa.Substring($begin, $end - $begin)))
$hash = (Get-FileHash -LiteralPath $PolicyPath -Algorithm SHA256).Hash.ToLowerInvariant()
$policy = Read-ApprovedReleasePolicy -Path $PolicyPath -ExpectedSha256 $hash
$snapshot = [pscustomobject]@{
    build_git_commit = $policy.candidate.build_commit
    low_signal_alarm_enabled = $false
    low_signal_comparator_verified = $false
    low_signal_comparator_configured_verified = $false
    config_drift_detected = $false
    config_operator_verified = $true
    config_attestation_status = 'verified'
    spot_config_fingerprint_sha256 = $policy.candidate.config_fingerprint_sha256
    spot_config_verified_fingerprint_sha256 = $policy.candidate.config_fingerprint_sha256
}
$count = 0
function Assert-Scope([object]$Value, [object]$PolicyObject, [string]$Build, [bool]$Expected) {
    $actual = Test-ApprovedDisabledLowSignalScope -Snapshot $Value -Policy $PolicyObject -RuntimeBuild $Build
    if ($actual -ne $Expected) { throw "Scope mismatch: $actual != $Expected" }
    $script:count++
}
Assert-Scope $snapshot $policy $policy.candidate.build_commit $true
Assert-Scope $snapshot $null $policy.candidate.build_commit $false
Assert-Scope $snapshot $policy ('a' * 40) $false
foreach ($key in @('low_signal_alarm_enabled', 'low_signal_comparator_verified',
    'low_signal_comparator_configured_verified', 'config_drift_detected')) {
    foreach ($value in @($true, 'false', 0, $null)) {
        $copy = $snapshot | ConvertTo-Json | ConvertFrom-Json
        $copy.$key = $value
        Assert-Scope $copy $policy $policy.candidate.build_commit $false
    }
    $copy = $snapshot | ConvertTo-Json | ConvertFrom-Json
    $copy.PSObject.Properties.Remove($key)
    Assert-Scope $copy $policy $policy.candidate.build_commit $false
}
foreach ($key in @('config_operator_verified', 'config_attestation_status',
    'spot_config_fingerprint_sha256', 'spot_config_verified_fingerprint_sha256', 'build_git_commit')) {
    $copy = $snapshot | ConvertTo-Json | ConvertFrom-Json
    $copy.PSObject.Properties.Remove($key)
    Assert-Scope $copy $policy $policy.candidate.build_commit $false
}
foreach ($pair in @(@($PolicyPath, ('0' * 64)), @('', $hash), @($PolicyPath, ''))) {
    $rejected = $false
    try { $null = Read-ApprovedReleasePolicy -Path $pair[0] -ExpectedSha256 $pair[1] }
    catch { $rejected = $true }
    if (-not $rejected) { throw 'Unpinned policy was accepted' }
    $count++
}
if ($null -ne (Read-ApprovedReleasePolicy -Path '' -ExpectedSha256 '')) { throw 'Default QA scope changed' }
$count++
[pscustomobject]@{status='PASS'; checks=$count; policy_sha256=$hash; app_calls=0; physical_test='NOT_TESTED'} | ConvertTo-Json
