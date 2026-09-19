param([Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*') { throw 'Use PS 5.1.' }
. (Join-Path $PSScriptRoot 'transfer-binding-r2.ps1')
Import-Module (Join-Path (Split-Path -Parent $PSScriptRoot) 'canary-v1026\evidence_zip_integrity.psm1') -Force
Assert-EvidencePlainPath $OutputRoot
if (Test-Path -LiteralPath $OutputRoot) { throw 'Existing fixture preserved.' }
$root=[IO.Path]::GetFullPath($OutputRoot)
$null=[IO.Directory]::CreateDirectory($root)
$checks=[Collections.Generic.List[string]]::new()
function Check { param([bool]$Ok,[string]$Name) if (-not $Ok) { throw ('FAIL: '+$Name) }; $checks.Add($Name) }
function Reject {
    param([scriptblock]$Action,[string]$Pattern,[string]$Name)
    $message=''
    try { & $Action | Out-Null } catch { $message=$_.Exception.Message }
    Check ($message -match $Pattern) ($Name+': '+$message)
}
function Write-New {
    param([string]$Path,[byte[]]$Bytes)
    $s=[IO.File]::Open($Path,'CreateNew','Write','None')
    try { $s.Write($Bytes,0,$Bytes.Length) } finally { $s.Dispose() }
}
function Commit-Fixture {
    param([string]$Repo,[string]$Message)
    $null=Invoke-TransferGit $Repo @('add','--all')
    $null=Invoke-TransferGit $Repo @('-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
        '-c','commit.gpgsign=false','commit','--quiet','-m',$Message)
}
# A fresh, shallow checkout has no old baseline commit but has its exact Canary tree.
$original=Invoke-TransferGit $PSScriptRoot @('rev-parse','--show-toplevel')
$archive=Join-Path $root 'source.zip'
$null=Invoke-TransferGit $original @('archive','--format=zip',('--output='+$archive),'HEAD','v2_next/scripts/canary-v1026')
Add-Type -AssemblyName System.IO.Compression.FileSystem
$seed=Join-Path $root 'seed'
[IO.Compression.ZipFile]::ExtractToDirectory($archive,$seed)
$null=Invoke-TransferGit $seed @('init','--quiet')
$null=Invoke-TransferGit $seed @('config','core.autocrlf','false')
$null=Invoke-TransferGit $seed @('config','core.hooksPath',(Join-Path $root 'no-hooks'))
Commit-Fixture $seed 'Synthetic Canary baseline'
Write-New (Join-Path $seed 'unrelated.txt') ([Text.Encoding]::UTF8.GetBytes('Unrelated new commit'))
Commit-Fixture $seed 'Include unrelated committed work'
$checkout=Join-Path $root 'checkout'
$null=Invoke-TransferGit $root @('clone','--quiet','--no-local','--depth','1',$seed,$checkout)
$null=Invoke-TransferGit $checkout @('config','core.hooksPath',(Join-Path $root 'no-hooks'))
$source=Join-Path $checkout 'v2_next\scripts\canary-v1026'
$binding=Get-TransferSourceBinding $source
Check ($binding.head -cne 'c03f7c76ff6e75bfe330275ac0fa01326f357261') 'New checkout HEAD accepted'
Check ((Invoke-TransferGit $checkout @('rev-parse','--is-shallow-repository')) -ceq 'true') 'Shallow checkout requires no baseline history'
Check ($binding.canary_tree -ceq 'df4ebc25261b78f355bad5f52884a18a77ba66b9') 'Exact Canary tree retained'
Check ($binding.names.Count -eq 11) 'Exact committed membership'
$snapshot=@(foreach ($name in $binding.names) {
    $fact=Get-EvidenceFileFact (Join-Path $source $name)
    [pscustomobject]@{name=$name;length=$fact.length;sha256=$fact.sha256}
})
$receipt=[pscustomobject]@{
    schema_version='v1026-canary-offline-build-v1';result='V1026_CANARY_PORT_OFFLINE_VERIFIED'
    tooling_parent_commit=$binding.head;port_regression=[pscustomobject]@{tests_passed=71}
    loopback_integration_passed=$true;server_execution_authorized=$false;observation_started=$false
    full_120m_allowed=$false;production_promotion_allowed=$false
    tooling_source_snapshot=[pscustomobject]@{entries=$snapshot}
}
$goodPath=Join-Path $root 'receipt.json'
$good=Write-EvidenceJsonNew $goodPath $receipt
$null=Read-TransferCanaryReceipt $goodPath $good.sha256 $source $binding
Check $true 'Current HEAD receipt accepted'
Reject { Read-TransferCanaryReceipt $goodPath ('0'*64) $source $binding } 'SHA256 differs' 'External receipt hash required'
$caseNumber=0
function Reject-Receipt {
    param([scriptblock]$Edit,[string]$Pattern,[string]$Name)
    $script:caseNumber++
    $changed=($receipt | ConvertTo-Json -Depth 20) | ConvertFrom-Json
    & $Edit $changed
    $badPath=Join-Path $root ('bad-'+$script:caseNumber+'.json')
    $fact=Write-EvidenceJsonNew $badPath $changed
    Reject { Read-TransferCanaryReceipt $badPath $fact.sha256 $source $binding } $Pattern $Name
}
Reject-Receipt {param($r) $r.tooling_parent_commit='c03f7c76ff6e75bfe330275ac0fa01326f357261'} 'current-HEAD' 'Stale receipt rejected'
Reject-Receipt {param($r) $r.result='V1026_CANARY_OFFLINE_CI_PASS'} 'OfflineCi' 'Synthetic CI receipt rejected'
Reject-Receipt {param($r) $r.loopback_integration_passed='true'} 'release-review' 'String boolean rejected'
Reject-Receipt {param($r) $r.port_regression.tests_passed='71'} 'release-review' 'String test count rejected'
foreach ($flag in @('server_execution_authorized','observation_started','full_120m_allowed','production_promotion_allowed')) {
    Reject-Receipt {param($r) $r.$flag=$true} 'boolean false' ('Approval rejected: '+$flag)
    Reject-Receipt {param($r) $r.$flag='false'} 'boolean false' ('String false rejected: '+$flag)
}
Reject-Receipt {param($r) $r.tooling_source_snapshot.entries[0].sha256='0'*64} 'bytes differ' 'Snapshot hash rejected'
Reject-Receipt {param($r) $r.tooling_source_snapshot.entries[0].length++} 'bytes differ' 'Snapshot length rejected'
Reject-Receipt {param($r) $r.tooling_source_snapshot.entries=@($r.tooling_source_snapshot.entries | Select-Object -Skip 1)} 'membership' 'Snapshot omission rejected'
Reject-Receipt {param($r) $r.tooling_source_snapshot.entries+=@($r.tooling_source_snapshot.entries[0])} 'membership' 'Snapshot duplicate rejected'
Reject-Receipt {param($r) $r.tooling_source_snapshot.entries[0].name='../escape'} 'membership' 'Snapshot traversal rejected'

$extra=Join-Path $source 'untracked.txt'
Write-New $extra ([Text.Encoding]::UTF8.GetBytes('fixture extra'))
Reject { Get-TransferSourceBinding $source } 'clean' 'Untracked source rejected'
# Explicit single-file move within this new fixture; keep evidence, no recursive cleanup.
Move-Item -LiteralPath $extra -Destination (Join-Path $root 'retained-untracked.txt')
$ignore=Join-Path $checkout '.git\info\exclude'
[IO.File]::AppendAllText($ignore,"`nignored.tmp`n")
$extra=Join-Path $source 'ignored.tmp'
Write-New $extra ([Text.Encoding]::UTF8.GetBytes('ignored fixture extra'))
$cleanBinding=Get-TransferSourceBinding $source
Reject { Read-TransferCanaryReceipt $goodPath $good.sha256 $source $cleanBinding } 'membership' 'Ignored extra rejected'
Move-Item -LiteralPath $extra -Destination (Join-Path $root 'retained-ignored.tmp')

$changedPath=Join-Path $source 'README.md'
$originalBytes=[IO.File]::ReadAllBytes($changedPath)
[IO.File]::AppendAllText($changedPath,"`nfixture change`n")
Reject { Get-TransferSourceBinding $source } 'clean' 'Dirty tracked source rejected'
$null=Invoke-TransferGit $checkout @('add','--','v2_next/scripts/canary-v1026/README.md')
Reject { Get-TransferSourceBinding $source } 'clean' 'Staged source rejected'
# Fixture restoration only; the real checkout/index is never modified.
[IO.File]::WriteAllBytes($changedPath,$originalBytes)
$null=Invoke-TransferGit $checkout @('add','--','v2_next/scripts/canary-v1026/README.md')
$null=Invoke-TransferGit $checkout @('update-index','--assume-unchanged','v2_next/scripts/canary-v1026/README.md')
[IO.File]::AppendAllText($changedPath,"`nconcealed fixture change`n")
Reject { Get-TransferSourceBinding $source } 'working bytes' 'Assume-unchanged cannot conceal changed source'
$null=Invoke-TransferGit $checkout @('update-index','--no-assume-unchanged','v2_next/scripts/canary-v1026/README.md')
Commit-Fixture $checkout 'Deliberate changed Canary tree'
Reject { Get-TransferSourceBinding $source } 'tree differs' 'Changed committed tree rejected'

Assert-TransferHistoricalInputs $PSScriptRoot
Check $true 'Historical helper/contract/launcher/guide bytes unchanged'
Check ((Get-EvidenceFileFact (Join-Path $PSScriptRoot 'build-transfer.ps1')).sha256 -ceq
    '8DBD3911AE7602BBD7660F6ABDF2C099E63E8F5B29BD32B24DCA64B67D47E384') 'Historical builder preserved'
[pscustomobject]@{result='V1026_TRANSFER_R2_BINDING_TEST_PASS';assertions=$checks.Count
    server_execution=$false;real_release_packaging_tested=$false;fixture_root=$root} | ConvertTo-Json
