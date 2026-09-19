[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$TransferZip,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedZipSha256,
    [Parameter(Mandatory=$true)][long]$ExpectedZipLength,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedManifestSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
# @INTEGRITY_FUNCTIONS@
# @STAGE_FUNCTIONS@
$pins=[Collections.Generic.List[IO.FileStream]]::new()
$clock=[Diagnostics.Stopwatch]::StartNew()
$stage=$null; $archive=$null
$savedPath=$env:PATH; $savedModules=$env:PSModulePath
function Stage-Progress {
    param([int]$Step,[string]$Message)
    Write-Host ('[V1026 STAGE] step='+$Step+'/6 elapsed='+$clock.Elapsed.ToString('hh\:mm\:ss')+' '+$Message)
}
try {
    $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
        $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
        [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native -or
        -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Use administrator native x64 Windows PowerShell 5.1.' }
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
    $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    Stage-Progress 1 'Verify externally pinned transfer; no installer or observation will run.'
    if ([IO.Path]::GetFullPath($TransferZip) -ine ('C:\Users\user\Desktop\SmartFactory\'+[IO.Path]::GetFileName($TransferZip))) { throw 'Use the approved desktop transfer directory.' }
    Assert-EvidencePlainPath $TransferZip
    $zipPin=[IO.File]::Open($TransferZip,'Open','Read','Read'); $pins.Add($zipPin)
    if ($zipPin.Length -ne $ExpectedZipLength -or (Get-EvidenceStreamHash $zipPin) -cne $ExpectedZipSha256) { throw 'Transfer bytes differ from external pins.' }
    $zipPin.Position=0; $archive=[IO.Compression.ZipArchive]::new($zipPin,'Read',$true)
    $manifestEntries=@($archive.Entries | Where-Object FullName -CEQ 'transfer-manifest.json')
    if ($manifestEntries.Count -ne 1 -or $manifestEntries[0].Length -gt 100000) { throw 'Transfer manifest missing/oversized.' }
    $input=$manifestEntries[0].Open(); $buffer=[IO.MemoryStream]::new()
    try {
        $chunk=New-Object byte[] 8192
        while (($n=$input.Read($chunk,0,$chunk.Length)) -gt 0) {
            if ($buffer.Length+$n -gt 100000) { throw 'Manifest expansion too large.' }
            $buffer.Write($chunk,0,$n)
        }
        if ($buffer.Length -ne $manifestEntries[0].Length -or (Get-EvidenceStreamHash $buffer) -cne $ExpectedManifestSha256) { throw 'External manifest binding differs.' }
        $manifest=ConvertFrom-Json -InputObject ([Text.UTF8Encoding]::new($false,$true).GetString($buffer.ToArray()))
    } finally { $input.Dispose(); $buffer.Dispose() }
    Assert-StageContract $manifest
    $entries=@($manifest.files)+@([pscustomobject]@{name='transfer-manifest.json';length=$manifestEntries[0].Length;sha256=$ExpectedManifestSha256})
    $null=Test-VerifiedEvidenceZip -Path $TransferZip -Entries $entries -ExpectedSha256 $ExpectedZipSha256
    Stage-Progress 2 'Read current v1.0.25 identity/config only; no image endpoint queries.'
    $before=Get-StageRuntime
    $health=Get-StageLocalJson 'health'
    if ((Get-StageRequired $health 'app_version') -cne '1.0.25' -or
        (Get-StageRequired (Get-StageRequired $health 'spot_temperature') 'build_git_commit') -cne 'a203baf62b544d38072a32d71ef411c7cf8b6490') { throw 'Expected current v1.0.25 identity not reported.' }
    $status=Select-StageStatus (Get-StageLocalJson 'api/spot/config')
    $configPath='C:\Users\user\AppData\Roaming\SmartFactoryLogger\config.ini'
    Assert-EvidencePlainPath $configPath
    $configFact=Get-StageMutableConfigFact $configPath
    $rollbackPath='C:\ProgramData\SFL-76B317D0A2901C6EFC649404211C8109\SmartFactoryLogger_v1.0.25_a203baf_unsigned_internal_20260909T012500Z\smart-factory-logger-v2 Setup 1.0.25.exe'
    Assert-EvidencePlainPath $rollbackPath
    $rollbackPin=[IO.File]::Open($rollbackPath,'Open','Read','Read'); $pins.Add($rollbackPin)
    if ($rollbackPin.Length -ne 150709821 -or (Get-EvidenceStreamHash $rollbackPin) -cne '9EE81CD9B809275B7E49E1441CBBF11C2B7BBC1E2A372A7D7163E4DCFFE6ADA1') { throw 'Existing recovery candidate bytes differ.' }
    Assert-StageSameRuntime $before (Get-StageRuntime)
    Stage-Progress 3 'Create a new administrator/SYSTEM-only staging root and verify all extracted files.'
    $programData=[Environment]::GetFolderPath([Environment+SpecialFolder]::CommonApplicationData)
    if ($programData -ine 'C:\ProgramData') { throw 'Unexpected server ProgramData location.' }
    $disk=[IO.DriveInfo]::new('C:\')
    if ($disk.AvailableFreeSpace -lt 2GB) { throw 'At least 2 GiB free space is required for staging.' }
    $stage=Join-Path $programData ('SFL26S-'+[guid]::NewGuid().ToString('N'))
    New-StageProtectedRoot $stage
    $payload=Join-Path $stage 'payload'
    Expand-StageArchiveNew -ZipPath $TransferZip -Destination $payload -Entries $entries -ExpectedSha256 $ExpectedZipSha256
    foreach ($entry in $entries) {
        $path=Join-Path $payload $entry.name.Replace('/','\')
        Assert-EvidencePlainPath $path
        $pin=[IO.File]::Open($path,'Open','Read','Read'); $pins.Add($pin)
        if ($pin.Length -ne $entry.length -or (Get-EvidenceStreamHash $pin) -cne $entry.sha256) { throw 'Protected payload changed.' }
    }
    Assert-StageProtectedRoot $stage
    Stage-Progress 4 'Verify release identity and the disabled Canary kit; no collection starts.'
    $kit=Join-Path $payload 'kit'; $release=Join-Path $payload 'release'
    Import-Module (Join-Path $kit 'v1026_release_identity_integrity.psm1') -Force
    $releaseCheck=Test-V1026ReleaseCandidate $release
    $kitManifest=@($manifest.files | Where-Object name -CEQ 'kit/canary_kit_files_sha256.json')
    if ($kitManifest.Count -ne 1) { throw 'Canary manifest binding missing.' }
    & $native -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $kit 'verify-spot-realtime-image-canary-kit.ps1') -KitRoot $kit -ExpectedManifestSha256 $kitManifest[0].sha256
    if ($LASTEXITCODE -ne 0) { throw 'Protected Canary static integrity check failed.' }
    Stage-Progress 5 'Recheck runtime/config continuity and publish a separate staging receipt.'
    $after=Get-StageRuntime; Assert-StageSameRuntime $before $after
    $configAfter=Get-StageMutableConfigFact $configPath
    if ($configAfter.length -ne $configFact.length -or $configAfter.sha256 -cne $configFact.sha256) { throw 'Config changed during staging.' }
    Assert-StageProtectedRoot $stage
    $result=[ordered]@{
        schema_version='v1026-static-stage-result-v1';result='V1026_TRANSFER_STAGED_RUNTIME_RECORDED_NOT_INSTALL_READY'
        recorded_at=[DateTimeOffset]::Now.ToString('o');elapsed_seconds=[Math]::Round($clock.Elapsed.TotalSeconds,1)
        transfer_sha256=$ExpectedZipSha256;transfer_manifest_sha256=$ExpectedManifestSha256
        product_commit=$manifest.product_commit;tooling_commit=$manifest.tooling_commit;helper_status='HASH_BOUND_LOCAL_PREPARATION_NOT_COMMITTED'
        protected_stage_root=$stage;release_root=$release;canary_root=$kit;verified_payload_files=$entries.Count
        release_check=$releaseCheck;current_runtime_before=$before;current_runtime_after=$after
        current_version='1.0.25';current_commit='a203baf62b544d38072a32d71ef411c7cf8b6490';config=$configFact
        local_image_status_snapshot=$status;runtime_installed_tree_verified=$false;current_health_approved=$false
        recovery_installer_path=$rollbackPath;recovery_installer_sha256='9EE81CD9B809275B7E49E1441CBBF11C2B7BBC1E2A372A7D7163E4DCFFE6ADA1'
        recovery_operational_suitability='REQUIRES_FRESH_SERVER_CONFIG_DATA_AND_INCIDENT_REVIEW'
        deployment_context='COMMERCIAL_FACTORY_DEVELOPER_MANAGED_INTERNAL_DEVELOPMENT_ONLY'
        installation_ready=$false;installation_authorized=$false;installation_started=$false;application_restart_performed=$false
        product_changes_made=$false;automatic_rollback_performed=$false;observation_started=$false;packet_capture_started=$false
        added_spot_image_requests=$false;full_120m_allowed=$false;production_promotion_allowed=$false
        next_action='REVIEW_CURRENT_BASELINE_AND_RECOVERY_THEN_PREPARE_INSTALL_HELPER'
        limitation='One local status snapshot only; no liveness sample, token audit, installed tree/data backup validation or operating approval. Normal local request logs may be written by the running app.'
    }
    $resultPath=Join-Path $stage 'preflight-result.json'
    $fact=Write-EvidenceJsonNew $resultPath $result
    $verify=Get-EvidenceFileFact $resultPath
    if ($verify.sha256 -cne $fact.sha256) { throw 'Receipt reopen verification failed.' }
    Write-StageBytesNew ($resultPath+'.sha256.txt') ([Text.Encoding]::ASCII.GetBytes($fact.sha256+"`n"))
    Stage-Progress 6 'Staging complete. Installation and observation remain blocked.'
    Write-Host ('[RESULT] '+$resultPath)
    Write-Host ('[SHA256] '+$fact.sha256)
    $result | ConvertTo-Json -Depth 12
} catch {
    Write-Host ('[HOLD] Preserve output and any new staging directory: '+$stage)
    Write-Host '[HOLD] No automatic retry, deletion, installation, restart, rollback or observation.'
    throw
} finally {
    if ($null -ne $archive) { $archive.Dispose() }
    foreach ($pin in $pins) { $pin.Dispose() }
    $env:PATH=$savedPath; $env:PSModulePath=$savedModules
}
