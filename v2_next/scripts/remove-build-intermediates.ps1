[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedIndexSha256,
    [Parameter(Mandatory)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedManagerSha256,
    [Parameter(Mandatory)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedCoreSha256,
    [switch]$Execute
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not$IsWindows-or$PSVersionTable.PSVersion.Major-lt7-or[Environment]::MachineName-cne'DESKTOP-SS5CURC'){throw 'Fixed development host / PowerShell 7 required'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$index=Join-Path $repo 'verification-files.local.json';$boundary=Join-Path $repo 'backend\build'
$pins=[Collections.Generic.List[IDisposable]]::new();$guards=@{};$held=@{};$confirmed=[Collections.Generic.List[object]]::new()
$document=$null;$indexStream=$null;$journal=$null;$journalPath=$null;$phase='bootstrap';$prepared=$false
function BootstrapHash([IO.Stream]$Stream){$Stream.Position=0;return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Stream))}
function PinnedText([IO.Stream]$Stream){$Stream.Position=0;$r=[IO.StreamReader]::new($Stream,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true);try{return $r.ReadToEnd()}finally{$r.Dispose()}}
try {
    $indexStream=[IO.File]::Open($index,'Open','Read','Read')
    if((BootstrapHash $indexStream)-cne$ExpectedIndexSha256){throw 'Management hash changed'}
    $indexStream.Position=0;$document=[System.Text.Json.JsonDocument]::Parse($indexStream)
    if($document.RootElement.GetProperty('workspace').GetString()-cne$repo-or$document.RootElement.GetProperty('host').GetString()-cne[Environment]::MachineName){throw 'Management host/workspace differs'}
    foreach($name in @('plans','migrations')){foreach($a in $document.RootElement.GetProperty($name).EnumerateArray()){if($a.GetProperty('state').GetString()-cne'COMPLETE'){throw 'Existing transaction pending'}}}
    $reviews=@($document.RootElement.GetProperty('audits').EnumerateArray()|Where-Object {$_.GetProperty('id').GetString()-ceq'5db89818-a464-4c8b-a534-0b5ada299072'})
    if($reviews.Count-ne1){throw 'Exact review missing'}
    if(@($document.RootElement.GetProperty('audits').EnumerateArray()|Where-Object {$_.GetProperty('kind').GetString()-ceq'DESKTOP_BUILD_INTERMEDIATE_CLEANUP'}).Count){throw 'Cleanup already recorded; no automatic retry'}
    $review=$reviews[0].GetRawText()|ConvertFrom-Json -Depth 70
    $witnesses=@{};foreach($w in $review.source_witnesses){$witnesses[$w.path]=$w}
    foreach($relative in @('server-path-audit\cleanup-archive-core.ps1','dist-migration-core.ps1','build-intermediate-cleanup-core.ps1')){
        $p=Join-Path $PSScriptRoot $relative;$s=[IO.File]::Open($p,'Open','Read','Read');$pins.Add($s)
        $expected=if($relative-ceq'build-intermediate-cleanup-core.ps1'){$ExpectedCoreSha256}else{$witnesses[$p].sha256}
        if((BootstrapHash $s)-cne$expected){throw 'Cleanup primitive hash differs'}
        $text=PinnedText $s
        if($relative-ceq'server-path-audit\cleanup-archive-core.ps1'){
            $tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseInput($text,[ref]$tokens,[ref]$errors)
            $fn=@($ast.FindAll({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-ceq'Initialize-CleanupNative'},$false))
            if($errors.Count-or$fn.Count-ne1){throw 'Native primitive syntax differs'}
            . ([scriptblock]::Create($fn[0].Extent.Text));Initialize-CleanupNative
        }else{. ([scriptblock]::Create($text))}
    }
    Add-DistGuard $boundary $guards;Add-DistGuard ([IO.Path]::GetDirectoryName($index)) $guards
    [SflCleanupNativeV1]::Identity($indexStream.SafeFileHandle,$index,$false)|Out-Null
    [SflCleanupNativeV1]::NoAlternateStreams($index,$false)
    $files=@(Get-BuildIntermediateRecords $review $repo);$deleteSet=@{};foreach($f in $files){$deleteSet[$f.path]=$true}
    $phase='preflight';Write-Host '[1/5] Recheck exactly 17 intermediate files, 14 build-history files and both retained outputs.'
    $tree=Get-DistTree $boundary
    if($tree.files.Count-ne31-or@(Compare-Object @($review.live_check.files.path) $tree.files).Count){throw 'Build membership changed'}
    foreach($d in $review.live_check.directories){Add-DistGuard $d.path $guards;[SflCleanupNativeV1]::NoAlternateStreams($d.path,$true);if((Get-Acl -LiteralPath $d.path).Sddl-cne$d.sddl){throw 'Build directory ACL changed'}}
    foreach($r in $review.live_check.files){
        $probe=[IO.File]::Open($r.path,'Open','Read','None')
        try{if([SflCleanupNativeV1]::Identity($probe.SafeFileHandle,$r.path,$false)-cne$r.identity){throw 'Build file identity changed'}}finally{$probe.Dispose()}
        $record=@{path=$r.path;bytes=[long]$r.metadata.bytes;sha256=$r.sha256;metadata=$r.metadata}
        $opened=Open-DistSource $record ($deleteSet.ContainsKey($r.path)) $guards;$pins.Add($opened.stream);$held[$r.path]=$opened
        if($opened.identity-cne$r.identity){throw 'Build identity changed after exclusive probe'}
    }
    $toolNames=@('build-intermediate-cleanup-core.ps1','remove-build-intermediates.ps1','build-intermediate-cleanup.test.ps1','build-intermediate-cleanup.test.cjs')
    $expectedSources=@{};foreach($p in $witnesses.Keys){$expectedSources[$p]=$true}
    foreach($name in $toolNames){$expectedSources[(Join-Path $PSScriptRoot $name)]=$true}
    # Detect newly added consumers in the same source scope used by the approved review.
    $currentSources=@{};foreach($p in $witnesses.Keys){$currentSources[$p]=$true}
    foreach($base in @('scripts','docs','..\.github\workflows')){
        $sourceTree=Get-DistTree ([IO.Path]::GetFullPath((Join-Path $repo $base)))
        foreach($p in $sourceTree.files){if($p-match'\.(ps1|psm1|cjs|mjs|js|py|md|json|ya?ml|cmd|bat)$'){$currentSources[$p]=$true}}
    }
    $tracked=(& git --no-optional-locks -c core.fsmonitor=false ls-files -z)-join "`n"
    if($LASTEXITCODE-ne0){throw 'Tracked source inventory failed'}
    foreach($relative in $tracked.Split([char]0)){
        if($relative-match'^(backend|frontend)/'-and$relative-match'\.(py|spec|js|cjs|mjs|tsx?|json|toml|ini|cfg|ya?ml|ps1|cmd|bat)$'-and$relative-notmatch'^frontend/public/'){$currentSources[[IO.Path]::GetFullPath((Join-Path $repo $relative))]=$true}
        if($relative-and$deleteSet.ContainsKey([IO.Path]::GetFullPath((Join-Path $repo $relative)))){throw 'Intermediate is tracked'}
    }
    if(@(Compare-Object @($expectedSources.Keys) @($currentSources.Keys)).Count){throw 'New/unreviewed source membership differs'}
    $sourceChanges=[Collections.Generic.List[object]]::new();$tooling=[Collections.Generic.List[object]]::new()
    $allPreserved=@($review.retained_output_files)+@($review.source_witnesses)
    foreach($f in $allPreserved){
        Add-DistGuard ([IO.Path]::GetDirectoryName($f.path)) $guards
        $s=[SflCleanupNativeV1]::OpenFile($f.path,$false);$pins.Add($s);[SflCleanupNativeV1]::NoAlternateStreams($f.path,$false)
        $expected=$f.sha256
        if($f.path-ceq(Join-Path $PSScriptRoot 'manage-verification-files.cjs')){$expected=$ExpectedManagerSha256;$sourceChanges.Add(@{path=$f.path;before=$f.sha256;after=$expected;reason='Add pending-transaction and preserved-build-evidence guards only'})}
        if((Get-DistHash $s)-cne$expected){throw ('Preserved file hash differs: '+$f.path)}
        $held[$f.path]=@{stream=$s;identity=[SflCleanupNativeV1]::Identity($s.SafeFileHandle,$f.path,$false);record=@{path=$f.path;sha256=$expected;metadata=(Get-DistMetadata $f.path)}}
    }
    foreach($name in $toolNames){
        $p=Join-Path $PSScriptRoot $name;$s=[SflCleanupNativeV1]::OpenFile($p,$false);$pins.Add($s)
        $r=@{path=$p;sha256=(Get-DistHash $s);metadata=(Get-DistMetadata $p)};$tooling.Add($r)
        $held[$p]=@{stream=$s;identity=[SflCleanupNativeV1]::Identity($s.SafeFileHandle,$p,$false);record=$r}
    }
    $outputTrees=@{}
    foreach($base in @('backend\dist\SmartFactoryBackend','dist\spot-temperature-v25-qa')){
        $root=Join-Path $repo $base;$t=Get-DistTree $root;$outputTrees[$root]=$t
        $expected=@($review.retained_output_files|Where-Object {$_.path.StartsWith($root+'\',[StringComparison]::Ordinal)}|ForEach-Object path)
        if(@(Compare-Object $expected $t.files).Count){throw 'Retained output membership differs'}
        foreach($d in $t.directories){Add-DistGuard $d $guards}
    }
    $directoryAcls=@($guards.Keys|ForEach-Object {@{path=$_;sddl=(Get-Acl -LiteralPath $_).Sddl}})
    Write-Host '[2/5] Recheck observable process/service/task/shortcut use. No app or build will be launched.'
    $live=Get-BuildLiveUse (PinnedText $held[(Join-Path $PSScriptRoot 'read-build-intermediate-use.ps1')].stream)
    if($live.matches.Count){throw 'Live build-use reference found'}
    if(-not$Execute){[ordered]@{state='PREFLIGHT_PASS';files=17;bytes=36648177;preserved_build_files=14;retained_output_files=1457;deleted_files=0;live_counts=$live.counts}|ConvertTo-Json -Compress;return}
    $phase='prepare';$id=[Guid]::NewGuid().ToString();$journalPath=Join-Path $repo ('artifacts\build-intermediate-cleanup-'+$id+'.jsonl')
    Add-DistGuard ([IO.Path]::GetDirectoryName($journalPath)) $guards
    $acl=[Security.AccessControl.FileSecurity]::new();$acl.SetAccessRuleProtection($true,$false)
    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User;$acl.SetOwner($sid)
    foreach($value in @($sid.Value,'S-1-5-18','S-1-5-32-544')|Select-Object -Unique){$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($value),'FullControl','Allow'))}
    $journal=[IO.FileSystemAclExtensions]::Create([IO.FileInfo]::new($journalPath),'CreateNew','FullControl','Read',65536,'WriteThrough',$acl)
    $audit=[ordered]@{id=$id;kind='DESKTOP_BUILD_INTERMEDIATE_CLEANUP';state='PREPARED';at=[DateTimeOffset]::UtcNow.ToString('o');source_audit_id=$review.id;original_index_sha256=$ExpectedIndexSha256;inventory_root=$boundary;
        authorization='Explicit user approval for the reviewed 17 development intermediates only';files=@($files|ForEach-Object {$held[$_.path].record});preserved_files=$review.preserved_build_files;retained_output_files=$review.retained_output_files;source_witnesses=$review.source_witnesses;source_changes=$sourceChanges.ToArray();tooling=$tooling.ToArray();live_check=$live;directory_acls=$directoryAcls;
        restore_policy=$review.restore_policy;limitations=$review.limitations;deleted_files=0;deleted_bytes=0;deleted_directories=0;existing_acl_writes=0;remote_server_operations=0;journal_path=$journalPath;journal_sha256=$null}
    Write-DistEvent $journal @{event='PLAN';audit=$audit}
    Write-Host '[3/5] Publish durable PREPARED audit before deleting any file.'
    $indexStream.Dispose();$indexStream=$null
    Write-BuildCleanupIndex $document $audit $index $ExpectedIndexSha256;$prepared=$true;$document.Dispose()
    $indexStream=[IO.File]::Open($index,'Open','Read','Read');$pendingHash=Get-DistHash $indexStream;$indexStream.Position=0;$document=[System.Text.Json.JsonDocument]::Parse($indexStream)
    $phase='delete';Write-Host '[4/5] Delete only the 17 verified open file handles; keep every directory and retained file.'
    foreach($f in $files){Remove-BuildIntermediatePinned $held[$f.path] $journal $confirmed}
    $phase='postcheck';$after=Get-DistTree $boundary
    if(@(Compare-Object @($review.preserved_build_files.path) $after.files).Count-or@(Compare-Object $tree.directories $after.directories).Count){throw 'Post-delete build membership differs'}
    foreach($p in $held.Keys){if($deleteSet.ContainsKey($p)){if([IO.File]::Exists($p)){throw 'Deleted path reappeared'};continue};$h=$held[$p];Assert-DistMetadata (Get-DistMetadata $p) $h.record.metadata;if((Get-DistHash $h.stream)-cne$h.record.sha256-or[SflCleanupNativeV1]::Identity($h.stream.SafeFileHandle,$p,$false)-cne$h.identity){throw 'Retained file changed'}}
    foreach($root in $outputTrees.Keys){$t=Get-DistTree $root;if(@(Compare-Object $outputTrees[$root].files $t.files).Count-or@(Compare-Object $outputTrees[$root].directories $t.directories).Count){throw 'Retained output tree changed'}}
    foreach($d in $directoryAcls){if((Get-Acl -LiteralPath $d.path).Sddl-cne$d.sddl){throw 'Existing directory ACL changed'}}
    if($confirmed.Count-ne17){throw 'Confirmed deletion count differs'}
    $audit.state='COMPLETE';$audit.deleted_files=17;$audit.deleted_bytes=36648177;$audit.at=[DateTimeOffset]::UtcNow.ToString('o')
    Write-DistEvent $journal @{event='COMPLETE';id=$id;deleted_files=17;deleted_bytes=36648177;preserved_build_files=14;retained_output_files=1457;deleted_directories=0;existing_acl_writes=0}
    $journal.Flush($true);$audit.journal_sha256=Get-DistHash $journal
    $phase='publish-completion';Write-Host '[5/5] Publish completion audit and exact ledger deltas.'
    $indexStream.Dispose();$indexStream=$null;Write-BuildCleanupIndex $document $audit $index $pendingHash
    $indexStream=[IO.File]::Open($index,'Open','Read','Read');$finalHash=Get-DistHash $indexStream
    [ordered]@{state='COMPLETE';id=$id;deleted_files=17;deleted_bytes=36648177;preserved_build_files=14;retained_output_files=1457;deleted_directories=0;existing_acl_writes=0;journal=$journalPath;journal_sha256=$audit.journal_sha256;index_sha256=$finalHash}|ConvertTo-Json -Compress
}catch{
    if($null-ne$journal){try{Write-DistEvent $journal @{event='HOLD';phase=$phase;confirmed_deletions=$confirmed.Count;prepared=$prepared}}catch{}}
    Write-Host ('[HOLD] phase='+$phase+' confirmed_deletions='+$confirmed.Count+' Preserve index/journal/.writing. No automatic retry or rollback.')
    throw
}finally{
    if($null-ne$document){$document.Dispose()};if($null-ne$indexStream){$indexStream.Dispose()};if($null-ne$journal){$journal.Dispose()}
    foreach($s in $pins){$s.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}
}
