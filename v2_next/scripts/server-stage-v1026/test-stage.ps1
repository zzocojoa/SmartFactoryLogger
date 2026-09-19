param([Parameter(Mandatory=$true)][string]$OutputRoot,[string]$TransferBuildResult='')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*') { throw 'Use PS 5.1.' }
$core=Join-Path (Split-Path -Parent $PSScriptRoot) 'canary-v1026\evidence_zip_integrity.psm1'
Import-Module $core -Force
. (Join-Path $PSScriptRoot 'stage-functions.ps1')
Assert-EvidencePlainPath $OutputRoot
if (Test-Path -LiteralPath $OutputRoot) { throw 'Existing fixture output preserved.' }
$root=[IO.Path]::GetFullPath($OutputRoot); $null=[IO.Directory]::CreateDirectory($root)
$passed=[Collections.Generic.List[string]]::new()
function Check { param([bool]$Ok,[string]$Name) if (-not $Ok) { throw ('FAIL: '+$Name) }; $passed.Add($Name) }
function Reject { param([scriptblock]$TestAction,[string]$CheckLabel) $rejected=$false;try { &$TestAction | Out-Null }catch{$rejected=$true};Check $rejected $CheckLabel }
function New-TestZip {
    param([string]$Name,[object[]]$Rows)
    $path=Join-Path $root ($Name+'.zip')
    $stream=[IO.File]::Open($path,'CreateNew','ReadWrite','None'); $zip=$null
    try {
        $zip=[IO.Compression.ZipArchive]::new($stream,'Create',$true)
        foreach ($r in $Rows) {
            $e=$zip.CreateEntry($r.name); if ($r.link) { $e.ExternalAttributes=[int](-1577123840) }
            $s=$e.Open(); try { $bytes=[Text.Encoding]::UTF8.GetBytes($r.text);$s.Write($bytes,0,$bytes.Length) }finally{$s.Dispose()}
        }
    } finally { if ($null -ne $zip) {$zip.Dispose()};$stream.Dispose() }
    return $path
}
$source=Join-Path $root 'source'; $null=[IO.Directory]::CreateDirectory($source)
Write-StageBytesNew (Join-Path $source 'a.txt') ([Text.Encoding]::UTF8.GetBytes('alpha'))
$zip=New-VerifiedEvidenceZip -SourceRoot $source -Destination (Join-Path $root 'valid.zip')
$dest=Join-Path $root 'extracted'
Expand-StageArchiveNew -ZipPath $zip.path -Destination $dest -Entries @($zip.entries) -ExpectedSha256 $zip.sha256
Check ((Get-EvidenceFileFact (Join-Path $dest 'a.txt')).sha256 -ceq $zip.entries[0].sha256) 'valid-reopen-extract-rehash'
Reject { Expand-StageArchiveNew $zip.path $dest @($zip.entries) $zip.sha256 } 'existing-target-rejected'
Check ([IO.File]::ReadAllText((Join-Path $dest 'a.txt')) -ceq 'alpha') 'existing-target-preserved'
Reject { Expand-StageArchiveNew $zip.path (Join-Path $root 'bad-hash') @($zip.entries) ('0'*64) } 'wrong-archive-hash-rejected'
Check (-not [IO.Directory]::Exists((Join-Path $root 'bad-hash'))) 'reject-before-output-creation'
foreach ($case in @(
    @{name='wrong-content';rows=@(@{name='a.txt';text='xxxxx';link=$false})},
    @{name='wrong-size';rows=@(@{name='a.txt';text='alphax';link=$false})},
    @{name='case-change';rows=@(@{name='A.txt';text='alpha';link=$false})},
    @{name='duplicate';rows=@(@{name='a.txt';text='alpha';link=$false},@{name='a.txt';text='alpha';link=$false})},
    @{name='traversal';rows=@(@{name='../a.txt';text='alpha';link=$false})},
    @{name='symlink';rows=@(@{name='a.txt';text='alpha';link=$true})}
)) {
    $bad=New-TestZip $case.name $case.rows
    Reject { Expand-StageArchiveNew $bad (Join-Path $root ('extract-'+$case.name)) @($zip.entries) (Get-EvidenceFileFact $bad).sha256 } ($case.name+'-rejected')
}
foreach ($name in @('../x','C:/x','a\x','NUL.txt','a/..','a./x','a:x')) {
    Reject { Assert-StageEntryName $name } ('unsafe-name-'+$name)
}
$contract=[pscustomobject]@{schema_version='v1026-static-stage-transfer-v1';classification='UNSIGNED_INTERNAL_DEVELOPMENT_STATIC_STAGE_ONLY';
    product_commit='d7a1b20f96711fb07fc7add0867e79ee36506fce';tooling_commit='c03f7c76ff6e75bfe330275ac0fa01326f357261';
    installation_authorized=$false;observation_authorized=$false;production_promotion_allowed=$false;
    files=@(1..14 | ForEach-Object {[pscustomobject]@{name=('release/f'+$_);length=1;sha256=('A'*64)}})+
        @(1..15 | ForEach-Object {[pscustomobject]@{name=('kit/f'+$_);length=1;sha256=('A'*64)}})+
        @([pscustomobject]@{name='server-stage.ps1';length=1;sha256=('A'*64)},[pscustomobject]@{name='SERVER_GUIDE.md';length=1;sha256=('A'*64)})}
Assert-StageContract $contract; Check $true 'valid-contract'
$contract.installation_authorized='false';Reject { Assert-StageContract $contract } 'string-false-rejected';$contract.installation_authorized=$false
$contract.observation_authorized=$true;Reject { Assert-StageContract $contract } 'observation-approval-rejected';$contract.observation_authorized=$false
$contract.files[0].name='release/../x';Reject { Assert-StageContract $contract } 'contract-traversal-rejected';$contract.files[0].name='release/f1'
$contract.files[0].length=[long]180000001;Reject { Assert-StageContract $contract } 'oversize-contract-rejected';$contract.files[0].length=1
$contract.files[1].name='release/f1';Reject { Assert-StageContract $contract } 'duplicate-contract-rejected';$contract.files[1].name='release/f2'
$contract.product_commit='0'*40;Reject { Assert-StageContract $contract } 'wrong-product-commit-rejected'
$config=Join-Path $root 'config.ini';Write-StageBytesNew $config ([Text.Encoding]::UTF8.GetBytes('old'))
$before=Get-StageMutableConfigFact $config
$new=Join-Path $root 'new-config.ini';Write-StageBytesNew $new ([Text.Encoding]::UTF8.GetBytes('new'))
$backup=Join-Path $root 'old-config.ini'
foreach ($p in @($config,$new,$backup)) { if (-not [IO.Path]::GetFullPath($p).StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Fixture replace boundary failed.' } }
[IO.File]::Replace($new,$config,$backup)
$after=Get-StageMutableConfigFact $config
Check ($before.sha256 -cne $after.sha256 -and [IO.File]::ReadAllText($backup) -ceq 'old') 'config-replacement-detected-with-original-preserved'
$writer=[IO.File]::Open($config,'Open','ReadWrite',([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
try { $fact=Get-StageMutableConfigFact $config;Check ($fact.sha256 -ceq $after.sha256) 'shared-config-reader-allows-existing-writer' } finally {$writer.Dispose()}
foreach ($v in @($null,'1788911472.1738272',[decimal]1788911472.1738272)) {
    $selected=Select-StageStatus ([pscustomobject]@{image=[pscustomobject]@{last_success_at=$v}})
    Check ($selected.last_success_at.present -and -not $selected.image_refresh_failure_count.present -and $null -eq $selected.image_refresh_failure_count.value) ('optional-state-no-zero-coercion-'+$passed.Count)
}
Reject { Select-StageStatus ([pscustomobject]@{}) } 'missing-image-object-rejected'
$runtime=[pscustomobject]@{main_pid=1;main_start_utc_ticks=2;backend_pid=3;backend_start_utc_ticks=4}
Assert-StageSameRuntime $runtime $runtime;Check $true 'stable-runtime'
$other=[pscustomobject]@{main_pid=1;main_start_utc_ticks=2;backend_pid=3;backend_start_utc_ticks=5}
Reject { Assert-StageSameRuntime $runtime $other } 'pid-reuse-rejected'
$acl=[Security.AccessControl.DirectorySecurity]::new();$acl.SetAccessRuleProtection($true,$false)
$acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
foreach ($sid in @('S-1-5-32-544','S-1-5-18')) {$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))}
Assert-StageAcl $acl;Check $true 'protected-acl-contract'
$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),'Read','ContainerInherit,ObjectInherit','None','Allow'))
Reject { Assert-StageAcl $acl } 'everyone-acl-rejected'
Reject { Assert-StageProtectedRoot $source } 'ordinary-user-owned-directory-rejected'
Reject { New-StageProtectedRoot $source } 'existing-protected-target-rejected-before-mutation'
if ($TransferBuildResult -ne '') {
    $build=Read-StageJson $TransferBuildResult
    $null=Test-VerifiedEvidenceZip -Path $build.archive.path -Entries @($build.archive.entries) -ExpectedSha256 $build.archive.sha256
    Check ($build.archive.entry_count -eq 32) 'actual-final-32-entry-zip-reopened'
    $full=Join-Path $root 'actual-transfer'
    Expand-StageArchiveNew $build.archive.path $full @($build.archive.entries) $build.archive.sha256
    Check ((Get-EvidenceFileFact (Join-Path $full 'server-stage.ps1')).sha256 -ceq $build.helper.sha256) 'actual-helper-content-extracted'
    $manifest=Read-StageJson (Join-Path $full 'transfer-manifest.json');Assert-StageContract $manifest
    Check $true 'actual-transfer-contract'
    foreach ($file in @((Join-Path $full 'server-stage.ps1'),(Join-Path (Split-Path -Parent $TransferBuildResult) 'START_V1026_STAGE.txt'))) {
        $tokens=$null;$errors=$null;$null=[Management.Automation.Language.Parser]::ParseFile($file,[ref]$tokens,[ref]$errors)
        Check ($errors.Count -eq 0) ('assembled-native-ps51-parse-'+[IO.Path]::GetFileName($file))
    }
    $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    $savedAction=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        $failureOutput=(& $native -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'build-transfer-r2.ps1') `
            -ReleaseRoot (Join-Path $full 'release') -CanaryBuildResult $build.canary_build_result `
            -ExpectedCanaryBuildResultSha256 ('0'*64) -OutputRoot (Join-Path $root 'rejected-build') 2>&1 | Out-String)
        $failureExit=$LASTEXITCODE
    } finally { $ErrorActionPreference=$savedAction }
    Check ($failureExit -ne 0 -and $failureOutput -like '*Canary receipt SHA256 differs*') 'wrong-canary-receipt-pin-rejected'
    Check (-not (Test-Path -LiteralPath (Join-Path $root 'rejected-build'))) 'receipt-pin-rejection-before-build-output'
}
Write-EvidenceJsonNew (Join-Path $root 'test-result.json') ([ordered]@{
    result='V1026_STAGE_LOCAL_FIXTURES_PASS';tests_passed=$passed.Count;tests=$passed.ToArray();
    actual_admin_directory_creation_tested=$false;live_server_queries_performed=$false;server_staging_executed=$false;
    limitation='ACL descriptor validation tested; actual administrator ProgramData creation and factory runtime APIs require the separately executed server stage.'
}) | Out-Null
Write-Host ('[FIXTURE PASS] '+$passed.Count+' checks. No live application/server queries or admin ProgramData writes.')
