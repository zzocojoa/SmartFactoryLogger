[CmdletBinding()]
param([Parameter(Mandatory)][ValidatePattern('^[0-9A-F]{64}$')][string]$ExpectedIndexSha256,[switch]$Execute)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not$IsWindows-or$PSVersionTable.PSVersion.Major-lt7-or-not[Environment]::Is64BitProcess-or[Environment]::MachineName-cne'DESKTOP-SS5CURC'){throw 'Development host / Windows x64 PowerShell 7 required'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if($repo-cne'C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next'){throw 'Fixed workspace required'}
$index=Join-Path $repo 'verification-files.local.json'
$pins=[Collections.Generic.List[IDisposable]]::new();$guards=@{};$sources=@{};$outside=@{};$boundaries=@{}
$confirmed=[Collections.Generic.List[object]]::new();$document=$null;$indexStream=$null;$journal=$null;$audit=$null;$phase='bootstrap'
try {
    $tooling=[Collections.Generic.List[object]]::new()
    foreach($name in @('server-path-audit\cleanup-archive-core.ps1','dist-migration-core.ps1','stage-extraction-cleanup-core.ps1','isolated-test-cache-core.ps1')){
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
    $self=[IO.File]::Open($PSCommandPath,'Open','Read','Read');$pins.Add($self)
    $tooling.Add(@{path=$PSCommandPath;sha256=(Get-DistHash $self)})
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
        if($kind-ceq'DESKTOP_ISOLATED_TEST_CACHE_CLEANUP'){throw 'Isolated cache cleanup already recorded; no automatic rerun'}
        if($kind-in@('DESKTOP_ATTESTATION_EXTRACTION_CLEANUP','DESKTOP_STAGE_EXTRACTION_CLEANUP','DESKTOP_DIST_PROTECTED_CI_MIGRATION','DESKTOP_DEPENDENCY_ACL_REPAIR')-and$a.GetProperty('state').GetString()-cne'COMPLETE'){throw 'Prior transaction incomplete'}
        if($a.GetProperty('id').GetString()-ceq'cd1e6296-a5bd-46fa-9f61-94ff47cff16f'){$review=$a.GetRawText()|ConvertFrom-Json -Depth 70}
    }
    if($null-eq$review){throw 'Classification missing'}
    $candidates=@(Get-TestCacheRecords $review $repo)
    $specs=@(Get-TestCacheSpecs $repo)
    $files=[Collections.Generic.List[object]]::new()
    $indexed=@{};foreach($f in $root.GetProperty('files').EnumerateArray()){$indexed[$f.GetProperty('path').GetString()]=$f.GetProperty('bytes').GetInt64()}
    foreach($f in $candidates){if(-not$indexed.ContainsKey($f.path)-or$indexed[$f.path]-ne$f.bytes){throw 'Management membership differs'}}
    $phase='cache-check';Write-Host '[1/5] Pin 181 cache files in 39 complete units; no deletion yet.'
    foreach($f in $candidates){
        Add-DistGuard ([IO.Path]::GetDirectoryName($f.path)) $guards
        $s=[SflCleanupNativeV1]::OpenFile($f.path,$true);$pins.Add($s)
        [SflCleanupNativeV1]::NoAlternateStreams($f.path,$false)
        $meta=[pscustomobject](Get-DistMetadata $f.path)
        if(($meta.attributes-band[IO.FileAttributes]'ReadOnly,ReparsePoint,Offline,Encrypted,SparseFile,Compressed')-ne0){throw 'Unsupported cache attributes'}
        Assert-TestCacheTimestamp $meta $f.snapshot
        $hash=Get-DistHash $s
        if($s.Length-ne$f.bytes-or($f.PSObject.Properties['sha256']-and$f.sha256-cne$hash)){throw 'Previously recorded cache bytes/hash changed'}
        $unit=@($specs|Where-Object {$f.path.StartsWith($_.unit+'\',[StringComparison]::Ordinal)})
        if($unit.Count-ne1){throw 'Cache unit boundary differs'}
        $record=[pscustomobject]@{path=$f.path;bytes=[long]$f.bytes;sha256=$hash;metadata=$meta;unit=$unit[0].unit;category=$f.cache_unit}
        $files.Add($record)
        $sources[$f.path]=[pscustomobject]@{stream=$s;record=$record;identity=[SflCleanupNativeV1]::Identity($s.SafeFileHandle,$f.path,$false)}
    }
    $witnesses=@{};foreach($f in $review.files){if($f.PSObject.Properties['content_verified_this_review']-and$f.content_verified_this_review){$witnesses[$f.path]=$f}}
    foreach($w in $review.source_witnesses){$witnesses[$w.path]=$w}
    foreach($b in @($specs.group|Select-Object -Unique)){
        $tree=Get-DistTree $b;$boundaries[$b]=$tree
        $previous=@($review.files|Where-Object {$_.path.StartsWith($b+'\',[StringComparison]::Ordinal)})
        if($previous.Count-ne$tree.files.Count-or@($previous|Where-Object {$_.path-cnotin$tree.files}).Count){throw 'Reviewed evidence boundary membership changed'}
        foreach($d in $tree.directories){Add-DistGuard $d $guards;[SflCleanupNativeV1]::NoAlternateStreams($d,$true)}
        foreach($p in $tree.files){
            if($sources.ContainsKey($p)){continue}
            $s=[SflCleanupNativeV1]::OpenFile($p,$false);$pins.Add($s);[SflCleanupNativeV1]::NoAlternateStreams($p,$false)
            $hash=Get-DistHash $s
            if($witnesses.ContainsKey($p)-and$witnesses[$p].sha256-cne$hash){throw 'Previously verified evidence/producer changed'}
            $outside[$p]=@{path=$p;stream=$s;sha256=$hash;metadata=[pscustomobject](Get-DistMetadata $p)}
        }
    }
    foreach($spec in $specs){
        $actual=Get-DistTree $spec.unit
        $wanted=@($files|Where-Object {$_.unit-ceq$spec.unit})
        if($actual.files.Count-ne$spec.count-or@($wanted|Where-Object {$_.path-cnotin$actual.files}).Count){throw 'Whole cache unit membership differs'}
    }
    $producerRecords=[Collections.Generic.List[object]]::new()
    foreach($b in @($specs.group|Select-Object -Unique)){
        foreach($name in @('build-and-run.cjs','electron-main.cjs')){
            $p=Join-Path $b $name
            if(-not$witnesses.ContainsKey($p)-or-not$outside.ContainsKey($p)-or$witnesses[$p].sha256-cne$outside[$p].sha256){throw 'Historical producer witness differs'}
            $decoded=Read-StageReference $outside[$p].stream
            $compact=$decoded.text.Replace(' ','')
            if($name-ceq'build-and-run.cjs'-and-not$compact.Contains("fs.mkdtempSync(path.join(__dirname,'run-'))")){throw 'Fresh-run producer contract differs'}
            if($name-ceq'electron-main.cjs'-and-not$compact.Contains("app.setPath('userData',path.join(out,'electron-profile'))")){throw 'Isolated profile producer differs'}
            $producerRecords.Add(@{path=$p;sha256=$outside[$p].sha256;executed=$false})
        }
    }
    # All completed-run receipt dependencies are outside the cache; no benchmark is rerun.
    $receiptRecords=[Collections.Generic.List[object]]::new()
    foreach($v in $outside.Values){
        if([IO.Path]::GetFileName($v.path)-cne'completion-receipt.json'){continue}
        $receipt=(Read-StageReference $v.stream).text|ConvertFrom-Json
        $base=[IO.Path]::GetDirectoryName($v.path)
        foreach($pair in @(@('measurements.json','measurementSha256'),@('source-manifest.json','manifestSha256'))){
            $p=Join-Path $base $pair[0]
            if(-not$outside.ContainsKey($p)-or$outside[$p].sha256-cne$receipt.($pair[1])){throw 'Completed measurement/manifest hash differs'}
        }
        if($receipt.childExitCode-ne0){throw 'Receipt child exit differs'}
        $receiptRecords.Add(@{path=$v.path;sha256=$v.sha256;status=$receipt.status;measurement_and_manifest_hashes_verified=$true})
    }
    if($receiptRecords.Count-ne2){throw 'Expected two historical completion receipts'}
    $acl=@{};foreach($p in $guards.Keys){$acl[$p]=(Get-Acl -LiteralPath $p).Sddl}
    $phase='usage-review';Write-Host '[2/5] Recheck readable live references and repository consumers; preserve measurement evidence and non-cache profile state.'
    $usage=Get-TestCacheUse
    $referenceRecords=[Collections.Generic.List[object]]::new()
    $referencePaths=[Collections.Generic.List[string]]::new()
    foreach($b in @((Join-Path $repo 'scripts'),(Join-Path $repo 'docs'),[IO.Path]::GetFullPath((Join-Path $repo '..\.github\workflows')))){
        foreach($p in (Get-DistTree $b).files){if($p-match'\.(ps1|psm1|cjs|js|md|json|yaml|yml)$'){$referencePaths.Add($p)}}
    }
    foreach($name in @('README.md','AGENTS.md','package.json')){$referencePaths.Add((Join-Path $repo $name))}
    foreach($p in $referencePaths){
        # These named tools describe the approved mapping; they are not consumers of extracted product files.
        $metadataTool=[IO.Path]::GetFileName($p)-in@('review-artifacts-temp.cjs','review-artifacts-temp.test.cjs','stage-extraction-cleanup-core.ps1','stage-extraction-cleanup.test.ps1','remove-stage-extraction-duplicates.ps1','manage-verification-files.cjs','stage-extraction-cleanup.test.cjs','review-large-verification-files.cjs','review-large-verification-files.test.cjs','attestation-extraction-cleanup-core.ps1','attestation-extraction-cleanup.test.ps1','attestation-extraction-cleanup.test.cjs','remove-attestation-extraction-duplicates.ps1','isolated-test-cache-core.ps1','isolated-test-cache.test.ps1','isolated-test-cache.test.cjs','remove-isolated-test-cache.ps1')
        $s=[SflCleanupNativeV1]::OpenFile($p,$false);$pins.Add($s)
        if($s.Length-gt5MB){throw 'Reference read exceeds bound'}
        $hash=Get-DistHash $s;$decoded=Read-StageReference $s
        if(-not$metadataTool-and$decoded.text-match'(?i)operator-emphasis-(isolation|optimization)-20260910|run-(54JQVf|BlDyJT|FC51gr|L6rPQy|phfxUN|tSoLDE|xwjcf4)'){throw 'Repository references a selected extraction parent; review required'}
        $referenceRecords.Add(@{path=$p;sha256=$hash;encoding=$decoded.encoding;mapping_metadata_only=$metadataTool})
    }
    if(-not$Execute){Write-Host ('[PREFLIGHT PASS] 181 files / 184040248 bytes; units=39; preserved_files='+$outside.Count+'; repository_files='+$referenceRecords.Count+'; deleted_files=0');$usage|ConvertTo-Json -Depth 8 -Compress;return}
    $phase='publish-intent';Write-Host '[3/5] Publish a new journal and pending management record before any source deletion.'
    $id=[Guid]::NewGuid().ToString();$journalPath=Join-Path $repo ('artifacts\isolated-test-cache-cleanup-'+$id+'.jsonl')
    Add-DistGuard ([IO.Path]::GetDirectoryName($journalPath)) $guards
    $fa=[Security.AccessControl.FileSecurity]::new();$fa.SetAccessRuleProtection($true,$false)
    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User;$fa.SetOwner($sid)
    foreach($value in @($sid.Value,'S-1-5-18','S-1-5-32-544')|Select-Object -Unique){$fa.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($value),'FullControl','Allow'))}
    $journal=[IO.FileSystemAclExtensions]::Create([IO.FileInfo]::new($journalPath),'CreateNew','FullControl','Read',65536,'WriteThrough',$fa)
    $audit=[ordered]@{id=$id;kind='DESKTOP_ISOLATED_TEST_CACHE_CLEANUP';state='PREPARED';at=[DateTimeOffset]::UtcNow.ToString('o');classification_id=$review.id;authority='User approved review then deletion of the approximately 184MB isolated test cache. Only 181 fixed files in 39 complete cache units of seven known test profiles. Preserve all non-cache files and directories.';restore_policy='No cache byte backup. Rerunning the retained harness creates a fresh profile and regenerates cache/downloadable assets; exact historical cache bytes and warm-cache state cannot be restored. No harness is run here.';original_index_sha256=$ExpectedIndexSha256;inventory_root=(Join-Path $repo 'artifacts');files=$files.ToArray();units=$specs;journal_path=$journalPath;tooling=$tooling.ToArray();live_reference_check=$usage;repository_reference_check=$referenceRecords.ToArray();producer_evidence=$producerRecords.ToArray();completed_receipts=$receiptRecords.ToArray();boundaries=$boundaries;existing_directory_acl=$acl;preserved_files=@($outside.Values|ForEach-Object {@{path=$_.path;sha256=$_.sha256;metadata=$_.metadata}});deleted_files=0;deleted_bytes=0;deleted_directories=0;existing_acl_writes=0;remote_server_operations=0}
    Write-DistEvent $journal @{event='PLAN';audit=$audit}
    $indexStream.Dispose();$indexStream=$null
    Write-TestCacheIndex $document $audit $index $ExpectedIndexSha256
    $document.Dispose();$indexStream=[SflCleanupNativeV1]::OpenFile($index,$false);$pendingHash=Get-DistHash $indexStream
    $indexStream.Position=0;$document=[System.Text.Json.JsonDocument]::Parse($indexStream)
    $phase='remove-exact-files';Write-Host '[4/5] Delete only 181 pinned cache files; all directories, non-cache state and existing ACLs remain.'
    foreach($f in $files){
        Remove-TestCachePinned $sources[$f.path] $journal $confirmed
    }
    $phase='postcheck';Write-Host '[5/5] Verify source absence, preserved evidence hashes, unchanged outside files/directories; reconcile management history.'
    foreach($f in $files){if(Test-Path -LiteralPath $f.path){throw 'Cache file still exists'}}
    foreach($b in $boundaries.Keys){Assert-StageMembership $boundaries[$b] (Get-DistTree $b) @($files.path)}
    foreach($p in $acl.Keys){if((Get-Acl -LiteralPath $p).Sddl-cne$acl[$p]){throw 'Existing directory ACL changed'}}
    foreach($v in $outside.Values){Assert-DistMetadata (Get-DistMetadata $v.path) $v.metadata;if((Get-DistHash $v.stream)-cne$v.sha256){throw 'Outside hash changed'}}
    if($confirmed.Count-ne181){throw 'Confirmation count differs'}
    $audit.state='COMPLETE';$audit.deleted_files=181;$audit.deleted_bytes=184040248;$audit.completed_at=[DateTimeOffset]::UtcNow.ToString('o')
    Write-DistEvent $journal @{event='COMPLETE';audit_id=$id;deleted_files=181;deleted_bytes=184040248;preserved_files_verified=$outside.Count;directories_deleted=0;existing_acl_writes=0}
    $journal.Flush($true);$audit.journal_sha256=Get-DistHash $journal
    $indexStream.Dispose();$indexStream=$null
    Write-TestCacheIndex $document $audit $index $pendingHash
    $check=[IO.File]::OpenRead($index);try{$newHash=Get-DistHash $check}finally{$check.Dispose()}
    [pscustomobject]@{state='COMPLETE';deleted_files=181;logical_bytes_freed=184040248;preserved_hashes_verified=$outside.Count;deleted_directories=0;existing_acl_writes=0;remote_server_operations=0;audit_id=$id;journal_path=$journalPath;index_sha256=$newHash}|ConvertTo-Json -Compress
}catch {
    if($null-ne$journal){try{Write-DistEvent $journal @{event='HOLD';phase=$phase;confirmed_deleted_files=$confirmed.Count;confirmed_paths=@($confirmed.path)}}catch{Write-Warning 'Journal update failed; pending index remains the recovery anchor'}}
    Write-Host ('[HOLD] phase='+$phase+' confirmed_deleted_files='+$confirmed.Count+'. Preserve journal/index/.writing. No automatic retry, restore, ACL change or additional deletion.')
    throw
}finally{
    if($null-ne$journal){$journal.Dispose()};if($null-ne$indexStream){$indexStream.Dispose()};if($null-ne$document){$document.Dispose()}
    foreach($s in $pins){$s.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}
}
