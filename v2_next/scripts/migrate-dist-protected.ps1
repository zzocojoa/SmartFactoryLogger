[CmdletBinding()]
param([Parameter(Mandatory)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedIndexSha256,[switch]$Execute)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$repo='C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next'
$indexPath=Join-Path $repo 'verification-files.local.json'
$kind='DESKTOP_DIST_PROTECTED_CI_MIGRATION'
$pins=[Collections.Generic.List[IDisposable]]::new();$guards=@{};$sources=@{};$keepers=@{}
$confirmed=[Collections.Generic.List[object]]::new();$doc=$null;$journal=$null;$audit=$null;$created=0;$indexStream=$null
function Read-PinnedText([string]$Path,[string]$Hash) {
    $node=Get-Item -LiteralPath $Path -Force
    while($null-ne$node){
        if(($node.Attributes-band[IO.FileAttributes]::ReparsePoint)-ne 0){throw 'Tooling/index reparse path'}
        if($node-is[IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
    }
    $s=[IO.File]::Open($Path,'Open','Read','Read');$pins.Add($s)
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$actual=[Convert]::ToHexString($sha.ComputeHash($s))}finally{$sha.Dispose()}
    if($actual-cne$Hash){throw 'Pinned tooling hash differs'}
    $s.Position=0;$r=[IO.StreamReader]::new($s,[Text.UTF8Encoding]::new($false,$true),$false,4096,$true)
    try{return $r.ReadToEnd()}finally{$r.Dispose()}
}
try {
    if(-not$IsWindows-or$PSVersionTable.PSVersion.Major-lt 7-or-not[Environment]::Is64BitProcess-or[Environment]::MachineName-cne'DESKTOP-SS5CURC'){throw 'Development PC, x64 PowerShell 7 required; not the factory server'}
    $admin=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if($Execute-and-not$admin){throw 'ADMINISTRATOR_REQUIRED: no managed file or ACL changed'}
    if(Test-Path -LiteralPath ($indexPath+'.writing')){throw 'Pending registry writer; preserve and review'}
    $indexText=Read-PinnedText $indexPath $ExpectedIndexSha256
    $indexStream=$pins[$pins.Count-1]
    $doc=[System.Text.Json.JsonDocument]::Parse($indexText);$indexText=$null
    if($doc.RootElement.GetProperty('host').GetString()-cne'DESKTOP-SS5CURC'-or$doc.RootElement.GetProperty('workspace').GetString()-cne$repo){throw 'Index host/workspace differs'}
    $matching=@($doc.RootElement.GetProperty('audits').EnumerateArray()|Where-Object {$_.GetProperty('kind').GetString()-ceq$kind})
    if($matching.Count-ne 1){throw 'Exactly one prepared transaction required'}
    $audit=$matching[0].GetRawText()|ConvertFrom-Json -Depth 70
    if($audit.state-cne'PREPARED'-or$audit.prior_review_id-cne'45788395-d10c-4a97-a04c-1049f635942c'){throw 'Already attempted or wrong transaction; no retry'}
    foreach($t in $audit.tooling){
        if(-not$t.path.StartsWith($repo+'\scripts\',[StringComparison]::Ordinal)){throw 'Tooling path outside scripts'}
        $text=Read-PinnedText $t.path $t.sha256
        switch([IO.Path]::GetFileName($t.path)){
            'dist-migration-core.ps1' {. ([scriptblock]::Create($text))}
            'cleanup-archive-core.ps1' {
                $tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseInput($text,[ref]$tokens,[ref]$errors)
                $f=@($ast.FindAll({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-ceq'Initialize-CleanupNative'},$false))
                if($errors.Count-or$f.Count-ne 1){throw 'Native initializer differs'}
                . ([scriptblock]::Create($f[0].Extent.Text));Initialize-CleanupNative
            }
        }
    }
    $plan=$audit.plan;$archive='C:\ProgramData\SFLOps\releases\legacy-ci\dist-45788395-d10c-4a97-a04c-1049f635942c'
    if($plan.root-cne(Join-Path $repo 'dist')-or$plan.archive_root-cne$archive-or$plan.files.Count-ne 21-or$plan.groups.Count-ne 4-or$plan.new_directories.Count-ne 8){throw 'Fixed approved scope differs'}
    $copyRows=@($plan.groups|ForEach-Object {$_.files})
    if($copyRows.Count-ne 12-or($copyRows|Measure-Object bytes -Sum).Sum-ne 2126941124-or($plan.files|Measure-Object bytes -Sum).Sum-ne 2871185450){throw 'Approved size differs'}
    $seen=@{}
    foreach($f in $plan.files){
        if($f.path-cne[IO.Path]::GetFullPath($f.path)-or-not$f.path.StartsWith($plan.root+'\',[StringComparison]::Ordinal)-or
            -not$f.keeper.StartsWith($archive+'\',[StringComparison]::Ordinal)-or$seen.ContainsKey($f.path)){throw 'Invalid approved path'}
        $seen[$f.path]=$true
    }
    foreach($p in $plan.new_directories){if(Test-Path -LiteralPath $p){throw 'Archive already exists; preserve it, no automatic retry'}}
    Add-DistGuard $repo $guards;Add-DistGuard 'C:\ProgramData' $guards
    foreach($b in $plan.existing_boundaries){Add-DistGuard $b.path $guards}
    Write-Host '[1/5] Verify 21 source hashes/streams, unchanged boundaries, references and capacity. No copy/deletion yet.'
    foreach($f in $plan.files){$sources[$f.path]=Open-DistSource $f ([bool]$Execute) $guards}
    foreach($w in $audit.reference_witnesses){
        if($sources.ContainsKey($w.path)){if($sources[$w.path].record.sha256-cne$w.sha256){throw 'Source/reference hash differs'};continue}
        Add-DistGuard ([IO.Path]::GetDirectoryName($w.path)) $guards
        $s=[SflCleanupNativeV1]::OpenFile($w.path,$false);$pins.Add($s)
        if((Get-DistHash $s)-cne$w.sha256){throw 'Reference witness changed; review before cleanup'}
    }
    Assert-DistUnchanged $audit
    $usage=& (Join-Path $repo 'scripts\read-dist-use.ps1')|ConvertFrom-Json
    if($usage.matches.Count){throw 'Active dist reference detected'}
    if([IO.DriveInfo]::new('C:\').AvailableFreeSpace-lt(2126941124+2GB)){throw 'Insufficient space including journal/headroom'}
    if(-not$Execute){Write-Host '[PASS] READ_ONLY_PREFLIGHT. 21 originals present; 0 copy, deletion or ACL write. Administrator required for execution.';return}
    Write-Host '[2/5] Create eight new private archive directories. Existing ACLs are unchanged.'
    foreach($p in $plan.new_directories){New-DistDirectory $p $guards;$created++}
    $journalPath=Join-Path $archive 'journal.jsonl';$journal=New-DistPrivateFile $journalPath
    Write-DistEvent $journal @{event='PLAN';at=[DateTimeOffset]::UtcNow.ToString('o');audit_id=$audit.id;index_sha256=$ExpectedIndexSha256;plan=$plan;usage=$usage}
    Write-Host '[3/5] Copy and verify all 12 CI files and all four checksum manifests.'
    foreach($f in $copyRows){
        $keepers[$f.destination]=Copy-DistPinned $sources[$f.path] $f.destination
        Write-DistEvent $journal @{event='COPY_VERIFIED';source=$f.path;destination=$f.destination;sha256=$f.sha256;bytes=$f.bytes}
    }
    Assert-DistSums $plan.groups $keepers
    Assert-DistUnchanged $audit
    foreach($p in $plan.new_directories){Assert-DistPrivate $p $true}
    Write-DistEvent $journal @{event='ALL_KEEPERS_VERIFIED';files=12;bytes=2126941124;index_maps_already_durable=$true}
    Write-Host '[4/5] Remove only the 12 migrated originals and nine duplicates through their verified open handles.'
    foreach($f in $plan.files){Remove-DistPinned $sources[$f.path] $keepers[$f.keeper] $journal $confirmed}
    Assert-DistUnchanged $audit @($confirmed|ForEach-Object {$_.path})
    foreach($k in $keepers.Values){if((Get-DistHash $k.stream)-cne$k.sha256){throw 'Final keeper hash differs'};Assert-DistPrivate $k.path $false}
    Write-Host '[5/5] Preserve completion receipt and reconcile the single management index.'
    $result=[ordered]@{state='PAYLOAD_COMPLETE';audit_id=$audit.id;at=[DateTimeOffset]::UtcNow.ToString('o');archive_root=$archive;copied_files=12;copied_bytes=2126941124;removed_source_files=21;duplicate_files_removed=9;net_logical_bytes_freed=744244326;deleted_directories=0;existing_acl_writes=0;remote_server_operations=0;files=$plan.files;index_reconciliation='PENDING'}
    $resultPath=Join-Path $archive 'result.json';$r=New-DistPrivateFile $resultPath
    try{$b=[Text.UTF8Encoding]::new($false).GetBytes(($result|ConvertTo-Json -Depth 50 -Compress));$r.Write($b);$r.Flush($true);$resultHash=Get-DistHash $r}finally{$r.Dispose()}
    $audit.state='COMPLETE';$audit.copied_files=12;$audit.removed_source_files=21;$audit.deleted_files=9;$audit.deleted_bytes=744244326;$audit.moved_files=12
    $audit|Add-Member -NotePropertyName completion -NotePropertyValue @{at=$result.at;receipt_path=$resultPath;receipt_sha256=$resultHash;journal_path=$journalPath;created_directories=$created;deleted_directories=0;final_archive_hashes_verified=12;preserved_dist_files=3815}
    Write-DistEvent $journal @{event='PAYLOAD_COMPLETE';receipt=$resultPath;sha256=$resultHash;removed_source_files=21}
    $indexStream.Dispose()
    Write-DistIndexCompletion $doc $audit $indexPath $ExpectedIndexSha256
    Write-DistEvent $journal @{event='INDEX_RECONCILED';audit_id=$audit.id}
    $s=[IO.File]::Open($indexPath,'Open','Read','Read');try{$newHash=Get-DistHash $s}finally{$s.Dispose()}
    [pscustomobject]@{state='COMPLETE';copied_files=12;removed_source_files=21;duplicates_removed=9;net_logical_bytes_freed=744244326;existing_acl_writes=0;deleted_directories=0;archive_root=$archive;result_sha256=$resultHash;index_sha256=$newHash}|ConvertTo-Json -Compress
}catch{
    Write-Host ('[HOLD] '+$_.Exception.Message) -ForegroundColor Yellow
    Write-Host ('[PRESERVE] created_directories='+$created+' confirmed_source_removals='+$confirmed.Count+'. No automatic retry, cleanup or rollback.')
    if($null-ne$journal){try{Write-DistEvent $journal @{event='HOLD';confirmed_removals=@($confirmed|ForEach-Object {$_.path});index_state_may_remain_prepared=$true}}catch{Write-Host '[HOLD] Journal write also failed; preserve all output.'}}
    throw
}finally{
    if($null-ne$journal){$journal.Dispose()}
    foreach($s in $sources.Values){$s.stream.Dispose()};foreach($s in $keepers.Values){$s.stream.Dispose()}
    foreach($p in $pins){$p.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}
    if($null-ne$doc){$doc.Dispose()}
}
