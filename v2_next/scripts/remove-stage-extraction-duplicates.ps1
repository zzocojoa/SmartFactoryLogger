[CmdletBinding()]
param([Parameter(Mandatory)][ValidatePattern('^[0-9A-F]{64}$')][string]$ExpectedIndexSha256,[switch]$Execute)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not$IsWindows-or$PSVersionTable.PSVersion.Major-lt7-or-not[Environment]::Is64BitProcess-or[Environment]::MachineName-cne'DESKTOP-SS5CURC'){throw 'Development host / Windows x64 PowerShell 7 required'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if($repo-cne'C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next'){throw 'Fixed workspace required'}
$index=Join-Path $repo 'verification-files.local.json'
$pins=[Collections.Generic.List[IDisposable]]::new();$guards=@{};$sources=@{};$keepers=@{};$outside=@{};$boundaries=@{}
$confirmed=[Collections.Generic.List[object]]::new();$document=$null;$indexStream=$null;$journal=$null;$audit=$null;$phase='bootstrap'
try {
    $tooling=[Collections.Generic.List[object]]::new()
    foreach($name in @('server-path-audit\cleanup-archive-core.ps1','dist-migration-core.ps1','stage-extraction-cleanup-core.ps1')){
        $p=Join-Path $PSScriptRoot $name;$s=[IO.File]::Open($p,'Open','Read','Read');$pins.Add($s)
        $reader=[IO.StreamReader]::new($s,[Text.UTF8Encoding]::new($false,$true),$false,4096,$true)
        try{$text=$reader.ReadToEnd()}finally{$reader.Dispose()}
        if($name.StartsWith('server-path-audit')){
            $ast=[Management.Automation.Language.Parser]::ParseInput($text,[ref]$null,[ref]$null)
            $fn=$ast.Find({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-ceq'Initialize-CleanupNative'},$false)
            . ([scriptblock]::Create($fn.Extent.Text));Initialize-CleanupNative
        }else{. ([scriptblock]::Create($text))}
        $tooling.Add(@{path=$p;sha256=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash})
    }
    Add-DistGuard $PSScriptRoot $guards
    $indexStream=[SflCleanupNativeV1]::OpenFile($index,$false)
    if((Get-DistHash $indexStream)-cne$ExpectedIndexSha256){throw 'External management hash differs'}
    $indexStream.Position=0;$document=[System.Text.Json.JsonDocument]::Parse($indexStream)
    $root=$document.RootElement
    if($root.GetProperty('host').GetString()-cne[Environment]::MachineName-or$root.GetProperty('workspace').GetString()-cne$repo){throw 'Management host/workspace differs'}
    foreach($p in $root.GetProperty('plans').EnumerateArray()){if($p.GetProperty('state').GetString()-cne'COMPLETE'){throw 'Prior cleanup plan incomplete'}}
    foreach($m in $root.GetProperty('migrations').EnumerateArray()){if($m.GetProperty('state').GetString()-cne'COMPLETE'){throw 'Prior migration incomplete'}}
    $review=$null
    foreach($a in $root.GetProperty('audits').EnumerateArray()){
        $kind=$a.GetProperty('kind').GetString()
        if($kind-ceq'DESKTOP_STAGE_EXTRACTION_CLEANUP'){throw 'Stage cleanup already recorded; no automatic rerun'}
        if($kind-in@('DESKTOP_DIST_PROTECTED_CI_MIGRATION','DESKTOP_DEPENDENCY_ACL_REPAIR')-and$a.GetProperty('state').GetString()-cne'COMPLETE'){throw 'Prior transaction incomplete'}
        if($a.GetProperty('id').GetString()-ceq'dde4f1ce-375f-4be5-84a8-18b47bcf2745'){$review=$a.GetRawText()|ConvertFrom-Json -Depth 70}
    }
    if($null-eq$review){throw 'Classification missing'}
    $files=@(Get-StageCleanupRecords $review $repo)
    $indexed=@{};foreach($f in $root.GetProperty('files').EnumerateArray()){$indexed[$f.GetProperty('path').GetString()]=$f.GetProperty('bytes').GetInt64()}
    foreach($f in $files){if(-not$indexed.ContainsKey($f.path)-or$indexed[$f.path]-ne$f.bytes-or-not$indexed.ContainsKey($f.keeper)-or$indexed[$f.keeper]-ne$f.bytes){throw 'Management membership differs'}}
    $phase='source-keeper-check';Write-Host '[1/5] Pin and hash all 64 sources and their retained revision-specific copies. No deletion yet.'
    foreach($f in $files){
        $src=Open-DistSource $f $true $guards;$sources[$f.path]=$src;$pins.Add($src.stream);$f.metadata=[pscustomobject](Get-DistMetadata $f.path)
        $kr=[pscustomobject]@{path=$f.keeper;bytes=$f.bytes;sha256=$f.sha256;metadata=$null}
        $kp=Open-DistSource $kr $false $guards;$pins.Add($kp.stream)
        $keepers[$f.keeper]=[pscustomobject]@{path=$f.keeper;stream=$kp.stream;identity=$kp.identity;bytes=$f.bytes;sha256=$f.sha256;metadata=[pscustomobject](Get-DistMetadata $f.keeper)}
    }
    $witnesses=@{};foreach($f in $review.files){if($f.PSObject.Properties['content_verified_this_review']-and$f.content_verified_this_review){$witnesses[$f.path]=$f}}
    foreach($n in @(4,5)){
        $base=Join-Path $repo ('.tmp\v26stage-tests-r'+$n)
        $delivery=Join-Path $repo ('artifacts\v1026-server-stage-20260911-r'+($n-3))
        foreach($b in @($base,$delivery)){
            $tree=Get-DistTree $b;$boundaries[$b]=$tree
            $previous=@($review.files|Where-Object {$_.path.StartsWith($b+'\',[StringComparison]::Ordinal)})
            if($previous.Count-ne$tree.files.Count-or@($previous|Where-Object {$_.path-cnotin$tree.files}).Count){throw 'Reviewed evidence boundary membership changed'}
            foreach($d in $tree.directories){Add-DistGuard $d $guards;[SflCleanupNativeV1]::NoAlternateStreams($d,$true)}
            foreach($p in $tree.files){
                if($sources.ContainsKey($p)-or$keepers.ContainsKey($p)){continue}
                $s=[SflCleanupNativeV1]::OpenFile($p,$false);$pins.Add($s);[SflCleanupNativeV1]::NoAlternateStreams($p,$false)
                $hash=Get-DistHash $s
                if($witnesses.ContainsKey($p)-and($witnesses[$p].sha256-cne$hash-or$witnesses[$p].bytes-ne$s.Length)){throw 'Previously verified evidence changed'}
                $outside[$p]=@{path=$p;stream=$s;sha256=$hash;metadata=[pscustomobject](Get-DistMetadata $p)}
            }
        }
        $actual=Get-DistTree (Join-Path $base 'actual-transfer')
        $wanted=@($files|Where-Object {$_.path.StartsWith((Join-Path $base 'actual-transfer')+'\',[StringComparison]::Ordinal)})
        if($actual.files.Count-ne32-or@($wanted|Where-Object {$_.path-cnotin$actual.files}).Count){throw 'Source tree membership differs'}
    }
    $acl=@{};foreach($p in $guards.Keys){$acl[$p]=(Get-Acl -LiteralPath $p).Sddl}
    $phase='usage-review';Write-Host '[2/5] Recheck readable live references and repository consumers; preserve test receipts and delivery sets.'
    $usage=Get-StageUse
    $referenceRecords=[Collections.Generic.List[object]]::new()
    $referencePaths=[Collections.Generic.List[string]]::new()
    foreach($b in @((Join-Path $repo 'scripts'),(Join-Path $repo 'docs'),[IO.Path]::GetFullPath((Join-Path $repo '..\.github\workflows')))){
        foreach($p in (Get-DistTree $b).files){if($p-match'\.(ps1|psm1|cjs|js|md|json|yaml|yml)$'){$referencePaths.Add($p)}}
    }
    foreach($name in @('README.md','AGENTS.md','package.json')){$referencePaths.Add((Join-Path $repo $name))}
    foreach($p in $referencePaths){
        # These named tools describe the approved mapping; they are not consumers of extracted product files.
        $metadataTool=[IO.Path]::GetFileName($p)-in@('review-artifacts-temp.cjs','review-artifacts-temp.test.cjs','stage-extraction-cleanup-core.ps1','stage-extraction-cleanup.test.ps1','remove-stage-extraction-duplicates.ps1','manage-verification-files.cjs','stage-extraction-cleanup.test.cjs')
        $s=[SflCleanupNativeV1]::OpenFile($p,$false);$pins.Add($s)
        if($s.Length-gt5MB){throw 'Reference read exceeds bound'}
        $hash=Get-DistHash $s;$decoded=Read-StageReference $s
        if(-not$metadataTool-and$decoded.text-match'(?i)v26stage-tests-r[45]'){throw 'Repository references a selected extraction parent; review required'}
        $referenceRecords.Add(@{path=$p;sha256=$hash;encoding=$decoded.encoding;mapping_metadata_only=$metadataTool})
    }
    if(-not$Execute){Write-Host ('[PREFLIGHT PASS] 64 files / 331293866 bytes; keepers=64; boundary_files='+$outside.Count+'; repository_files='+$referenceRecords.Count+'; deleted_files=0');$usage|ConvertTo-Json -Depth 8 -Compress;return}
    $phase='publish-intent';Write-Host '[3/5] Publish a new journal and pending management record before any source deletion.'
    $id=[Guid]::NewGuid().ToString();$journalPath=Join-Path $repo ('artifacts\stage-extraction-cleanup-'+$id+'.jsonl')
    Add-DistGuard ([IO.Path]::GetDirectoryName($journalPath)) $guards
    $fa=[Security.AccessControl.FileSecurity]::new();$fa.SetAccessRuleProtection($true,$false)
    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User;$fa.SetOwner($sid)
    foreach($value in @($sid.Value,'S-1-5-18','S-1-5-32-544')|Select-Object -Unique){$fa.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($value),'FullControl','Allow'))}
    $journal=[IO.FileSystemAclExtensions]::Create([IO.FileInfo]::new($journalPath),'CreateNew','FullControl','Read',65536,'WriteThrough',$fa)
    $audit=[ordered]@{id=$id;kind='DESKTOP_STAGE_EXTRACTION_CLEANUP';state='PREPARED';at=[DateTimeOffset]::UtcNow.ToString('o');classification_id=$review.id;authority='User approved only the 64 duplicate files in r4/r5 actual-transfer; retain all directories, test receipts and both delivery revisions.';original_index_sha256=$ExpectedIndexSha256;inventory_root=(Join-Path $repo '.tmp');files=$files;journal_path=$journalPath;tooling=$tooling.ToArray();live_reference_check=$usage;repository_reference_check=$referenceRecords.ToArray();boundaries=$boundaries;existing_directory_acl=$acl;preserved_files=@($outside.Values|ForEach-Object {@{path=$_.path;sha256=$_.sha256;metadata=$_.metadata}});deleted_files=0;deleted_bytes=0;deleted_directories=0;existing_acl_writes=0;remote_server_operations=0}
    Write-DistEvent $journal @{event='PLAN';audit=$audit}
    $indexStream.Dispose();$indexStream=$null
    Write-StageIndex $document $audit $index $ExpectedIndexSha256
    $document.Dispose();$indexStream=[SflCleanupNativeV1]::OpenFile($index,$false);$pendingHash=Get-DistHash $indexStream
    $indexStream.Position=0;$document=[System.Text.Json.JsonDocument]::Parse($indexStream)
    $phase='remove-exact-files';Write-Host '[4/5] Delete only 64 pinned duplicate files; no directory or existing ACL changes.'
    foreach($f in $files){
        Assert-DistMetadata (Get-DistMetadata $f.path) $f.metadata
        Assert-DistMetadata (Get-DistMetadata $f.keeper) $keepers[$f.keeper].metadata
        Remove-DistPinned $sources[$f.path] $keepers[$f.keeper] $journal $confirmed
    }
    $phase='postcheck';Write-Host '[5/5] Verify source absence, retained hashes, unchanged outside files/directories; reconcile management history.'
    foreach($f in $files){if(Test-Path -LiteralPath $f.path){throw 'Source still exists'};if((Get-DistHash $keepers[$f.keeper].stream)-cne$f.sha256){throw 'Keeper hash changed'}}
    foreach($b in $boundaries.Keys){Assert-StageMembership $boundaries[$b] (Get-DistTree $b) @($files.path)}
    foreach($p in $acl.Keys){if((Get-Acl -LiteralPath $p).Sddl-cne$acl[$p]){throw 'Existing directory ACL changed'}}
    foreach($v in $outside.Values){Assert-DistMetadata (Get-DistMetadata $v.path) $v.metadata;if((Get-DistHash $v.stream)-cne$v.sha256){throw 'Outside hash changed'}}
    foreach($v in $keepers.Values){Assert-DistMetadata (Get-DistMetadata $v.path) $v.metadata}
    if($confirmed.Count-ne64){throw 'Confirmation count differs'}
    $audit.state='COMPLETE';$audit.deleted_files=64;$audit.deleted_bytes=331293866;$audit.completed_at=[DateTimeOffset]::UtcNow.ToString('o')
    Write-DistEvent $journal @{event='COMPLETE';audit_id=$id;deleted_files=64;deleted_bytes=331293866;keepers_verified=64;directories_deleted=0;existing_acl_writes=0}
    $journal.Flush($true);$audit.journal_sha256=Get-DistHash $journal
    $indexStream.Dispose();$indexStream=$null
    Write-StageIndex $document $audit $index $pendingHash
    $check=[IO.File]::OpenRead($index);try{$newHash=Get-DistHash $check}finally{$check.Dispose()}
    [pscustomobject]@{state='COMPLETE';deleted_files=64;logical_bytes_freed=331293866;retained_hashes_verified=64;deleted_directories=0;existing_acl_writes=0;remote_server_operations=0;audit_id=$id;journal_path=$journalPath;index_sha256=$newHash}|ConvertTo-Json -Compress
}catch {
    if($null-ne$journal){try{Write-DistEvent $journal @{event='HOLD';phase=$phase;confirmed_deleted_files=$confirmed.Count;confirmed_paths=@($confirmed.path)}}catch{Write-Warning 'Journal update failed; pending index remains the recovery anchor'}}
    Write-Host ('[HOLD] phase='+$phase+' confirmed_deleted_files='+$confirmed.Count+'. Preserve journal/index/.writing. No automatic retry, restore, ACL change or additional deletion.')
    throw
}finally{
    if($null-ne$journal){$journal.Dispose()};if($null-ne$indexStream){$indexStream.Dispose()};if($null-ne$document){$document.Dispose()}
    foreach($s in $pins){$s.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}
}
