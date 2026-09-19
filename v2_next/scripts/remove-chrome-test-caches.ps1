[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9A-F]{64}$')][string]$ExpectedIndexSha256,
    [Parameter(Mandatory)][ValidatePattern('^[0-9A-F]{64}$')][string]$ExpectedCoreSha256,
    [switch]$Execute
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not$IsWindows-or$PSVersionTable.PSVersion.Major-lt7-or-not[Environment]::Is64BitProcess-or[Environment]::MachineName-cne'DESKTOP-SS5CURC'){throw 'Development host / Windows x64 PowerShell 7 required'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if($repo-cne'C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next'){throw 'Fixed development workspace required'}
$index=Join-Path $repo 'verification-files.local.json'
$pins=[Collections.Generic.List[IDisposable]]::new();$guards=@{};$sources=@{};$retained=@{};$boundaries=@{}
$confirmed=[Collections.Generic.List[object]]::new();$document=$null;$indexStream=$null;$journal=$null;$phase='bootstrap'
try{
    $dependencies=[ordered]@{
        'server-path-audit\cleanup-archive-core.ps1'='CD9F2387581C52FA9A26EC6E217909919F472CB5DF9853C2E96A2A368FF40A28'
        'dist-migration-core.ps1'='D5A3F7A6861C0708BA88C1FE29B3AF9361ED6459D5CADC6D9A86E9B70CFF6DE8'
        'stage-extraction-cleanup-core.ps1'='151921D8F2E13101861C16BB65D838E5612AE287FF217E8D78FBD3E3A9F34D43'
        'isolated-test-cache-core.ps1'='F520C58427C83EA44734344066BD1E34001F290460609EDF89CE3010DEA20814'
        'chrome-test-cache-core.ps1'=$ExpectedCoreSha256
    }
    $tooling=[Collections.Generic.List[object]]::new()
    foreach($name in $dependencies.Keys){
        $p=Join-Path $PSScriptRoot $name;$s=[IO.File]::Open($p,'Open','Read','Read');$pins.Add($s)
        $sha=[Security.Cryptography.SHA256]::Create();try{$hash=[Convert]::ToHexString($sha.ComputeHash($s))}finally{$sha.Dispose()}
        if($hash-cne$dependencies[$name]){throw 'Pinned dependency changed'}
        $s.Position=0;$reader=[IO.StreamReader]::new($s,[Text.UTF8Encoding]::new($false,$true),$false,4096,$true)
        try{$text=$reader.ReadToEnd()}finally{$reader.Dispose()}
        if($name.StartsWith('server-path-audit')){
            $ast=[Management.Automation.Language.Parser]::ParseInput($text,[ref]$null,[ref]$null)
            $fn=$ast.Find({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-ceq'Initialize-CleanupNative'},$false)
            . ([scriptblock]::Create($fn.Extent.Text));Initialize-CleanupNative
        }else{. ([scriptblock]::Create($text))}
        $tooling.Add(@{path=$p;sha256=$hash})
    }
    $self=[IO.File]::Open($PSCommandPath,'Open','Read','Read');$pins.Add($self);$tooling.Add(@{path=$PSCommandPath;sha256=(Get-DistHash $self)})
    Add-DistGuard $PSScriptRoot $guards
    $indexStream=[SflCleanupNativeV1]::OpenFile($index,$false)
    if((Get-DistHash $indexStream)-cne$ExpectedIndexSha256){throw 'External management hash differs'}
    $indexStream.Position=0;$document=[System.Text.Json.JsonDocument]::Parse($indexStream);$root=$document.RootElement
    if($root.GetProperty('host').GetString()-cne[Environment]::MachineName-or$root.GetProperty('workspace').GetString()-cne$repo){throw 'Management host/workspace differs'}
    foreach($p in $root.GetProperty('plans').EnumerateArray()){if($p.GetProperty('state').GetString()-cne'COMPLETE'){throw 'Prior cleanup plan incomplete'}}
    foreach($m in $root.GetProperty('migrations').EnumerateArray()){if($m.GetProperty('state').GetString()-cne'COMPLETE'){throw 'Prior migration incomplete'}}
    foreach($a in $root.GetProperty('audits').EnumerateArray()){
        $kind=$a.GetProperty('kind').GetString()
        if($kind-ceq'DESKTOP_CHROME_TEST_CACHE_CLEANUP'){throw 'Chrome cache transaction already recorded; never rerun deletion'}
        if($kind-in@('DESKTOP_BUILD_INTERMEDIATE_CLEANUP','DESKTOP_ISOLATED_TEST_CACHE_CLEANUP','DESKTOP_ATTESTATION_EXTRACTION_CLEANUP','DESKTOP_STAGE_EXTRACTION_CLEANUP','DESKTOP_DIST_PROTECTED_CI_MIGRATION','DESKTOP_DEPENDENCY_ACL_REPAIR')-and$a.GetProperty('state').GetString()-cne'COMPLETE'){throw 'Prior transaction incomplete'}
    }
    $specs=@(Get-ChromeTestProfileSpecs $repo);$indexed=@{}
    foreach($f in $root.GetProperty('files').EnumerateArray()){$indexed[$f.GetProperty('path').GetString()]=$f}
    $phase='repository-reference-review';Write-Host '[REFERENCES] Check and pin bounded repository references before the full profile inventory.'
    $references=[Collections.Generic.List[object]]::new();$referencePaths=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach($base in @((Join-Path $repo 'scripts'),(Join-Path $repo 'docs'),[IO.Path]::GetFullPath((Join-Path $repo '..\.github\workflows')))){
        foreach($p in (Get-DistTree $base).files){if($p-match'\.(ps1|psm1|cjs|mjs|js|py|md|json|yaml|yml|cmd|bat)$'){[void]$referencePaths.Add($p)}}
    }
    foreach($f in [IO.DirectoryInfo]::new($repo).EnumerateFiles()){
        if($f.Extension-match'^\.(ps1|psm1|cjs|mjs|js|py|md|txt|cmd|bat)$'-or$f.Name-ceq'package.json'){[void]$referencePaths.Add($f.FullName)}
    }
    foreach($p in $referencePaths){
        $name=[IO.Path]::GetFileName($p)
        $metadataTool=[IO.Path]::GetDirectoryName($p)-ceq$PSScriptRoot-and$name-in@('chrome-test-cache-core.ps1','remove-chrome-test-caches.ps1','chrome-test-cache.test.ps1','chrome-test-cache.test.cjs','manage-verification-files.cjs','finalize-verification-retention.cjs','finalize-verification-retention.test.cjs','review-large-verification-files.cjs','review-large-verification-files.test.cjs')
        $s=[SflCleanupNativeV1]::OpenFile($p,$false);$pins.Add($s)
        if($s.Length-gt5MB){
            if($p-cne(Join-Path $repo '.tmp_preview_qa_only_err.txt')-or$s.Length-gt6MB){throw ('Reference read exceeds bound: '+$name)}
            # This previously inventoried QA error log is 5,311,664 bytes. Only its read bound differs.
            $reader=[IO.StreamReader]::new($s,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
            try{$decoded=@{text=$reader.ReadToEnd();encoding=$reader.CurrentEncoding.WebName}}finally{$reader.Dispose()}
        }else{$decoded=Read-StageReference $s}
        if(-not$metadataTool-and$decoded.text-match'(?i)\.tmp_chrome_'){throw ('Repository Chrome profile reference requires review: '+$name)}
        $references.Add(@{path=$p;sha256=(Get-DistHash $s);encoding=$decoded.encoding;mapping_metadata_only=$metadataTool})
    }
    $files=[Collections.Generic.List[object]]::new();$keepers=[Collections.Generic.List[object]]::new();$checked=0
    $phase='profile-pinning';Write-Host '[1/5] Verify nine exact development profiles and hash all 10,127 files. No deletion yet.'
    foreach($spec in $specs){
        $tree=Get-DistTree $spec.root;$boundaries[$spec.root]=$tree
        if($tree.files.Count-ne$spec.files){throw 'Profile membership count changed'}
        $listed=@($indexed.Keys|Where-Object {$_.StartsWith($spec.root+'\',[StringComparison]::Ordinal)})
        if($listed.Count-ne$spec.files-or@($listed|Where-Object {$_-cnotin$tree.files}).Count){throw 'Indexed profile membership differs'}
        if(-not[IO.File]::Exists((Join-Path $spec.root 'Local State'))-or-not[IO.File]::Exists((Join-Path $spec.root 'Default\Preferences'))){throw 'Profile identity files missing'}
        foreach($d in @($spec.root)+@($tree.directories)){Add-DistGuard $d $guards;[SflCleanupNativeV1]::NoAlternateStreams($d,$true)}
        foreach($p in $tree.files){
            $relative=$p.Substring($spec.root.Length+1);$unit=Get-ChromeCacheUnit $relative
            # Exclusive probe detects even read-only users; the durable handle then denies writes/deletes.
            $probe=[IO.File]::Open($p,'Open','Read','None')
            try{$probeIdentity=[SflCleanupNativeV1]::Identity($probe.SafeFileHandle,$p,$false)}finally{$probe.Dispose()}
            $s=[SflCleanupNativeV1]::OpenFile($p,[bool]$unit);$pins.Add($s)
            $identity=[SflCleanupNativeV1]::Identity($s.SafeFileHandle,$p,$false)
            if($identity-cne$probeIdentity){throw 'File replaced after exclusive probe'}
            [SflCleanupNativeV1]::NoAlternateStreams($p,$false)
            $meta=[pscustomobject](Get-DistMetadata $p)
            if(($meta.attributes-band[IO.FileAttributes]'ReparsePoint,Offline,Encrypted,SparseFile,Compressed')-ne0-or($unit-and($meta.attributes-band[IO.FileAttributes]::ReadOnly)-ne0)){throw 'Unsupported profile attributes'}
            $old=$indexed[$p]
            if($old.GetProperty('bytes').GetInt64()-ne$s.Length){throw 'Profile bytes changed since classification'}
            $mtime=([long]$meta.last_write_utc_ticks-621355968000000000L)/10000.0
            if([Math]::Abs($old.GetProperty('mtime_ms').GetDouble()-$mtime)-gt0.001){throw 'Profile modification time changed'}
            $hash=Get-DistHash $s
            if($unit){
                if($relative-ceq($unit+'\index')-or$relative-ceq'Default\Cache\Cache_Data\index'-or$relative-cmatch'^Default\\Code Cache\\(js|wasm)\\index$'){Assert-ChromeIndexHeader $s $relative}
                $record=[pscustomobject]@{path=$p;bytes=$s.Length;sha256=$hash;metadata=$meta;unit=(Join-Path $spec.root $unit);disposition='DELETE_CACHE'}
                $files.Add($record);$sources[$p]=[pscustomobject]@{stream=$s;identity=$identity;record=$record}
            }else{
                $keepers.Add([pscustomobject]@{path=$p;bytes=$s.Length;sha256=$hash;disposition='KEEP_PROFILE_STATE'})
                $retained[$p]=@{stream=$s;metadata=$meta;sha256=$hash}
            }
            $checked++;if($checked%1000-eq0){Write-Host ('[HASH] '+$checked+'/10127')}
        }
    }
    $audit=[ordered]@{id=[Guid]::NewGuid().ToString();kind='DESKTOP_CHROME_TEST_CACHE_CLEANUP';state='PREPARED';files=$files.ToArray();preserved_files=$keepers.ToArray()}
    Assert-ChromeCacheRecords $audit $repo
    foreach($b in $boundaries.Keys){Assert-StageMembership $boundaries[$b] (Get-DistTree $b) @()}
    $acl=@{};foreach($p in $guards.Keys){$acl[$p]=(Get-Acl -LiteralPath $p).Sddl}
    $phase='usage-review';Write-Host '[2/5] Recheck process/service/task/shortcut use. Repository references remain pinned.'
    $usage=Get-ChromeTestLiveUse $specs
    if(-not$Execute){Write-Host '[PREFLIGHT PASS] delete=642 / 211061627 bytes; preserve=9485 / 681852407 bytes; deleted=0';return}
    $phase='publish-intent';Write-Host '[3/5] Publish durable intent and pending management record before deletion.'
    $journalPath=Join-Path $repo ('artifacts\chrome-test-cache-cleanup-'+$audit.id+'.jsonl')
    Add-DistGuard ([IO.Path]::GetDirectoryName($journalPath)) $guards
    $fa=[Security.AccessControl.FileSecurity]::new();$fa.SetAccessRuleProtection($true,$false)
    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User;$fa.SetOwner($sid)
    foreach($value in @($sid.Value,'S-1-5-18','S-1-5-32-544')|Select-Object -Unique){$fa.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($value),'FullControl','Allow'))}
    $journal=[IO.FileSystemAclExtensions]::Create([IO.FileInfo]::new($journalPath),'CreateNew','FullControl','Read',65536,'WriteThrough',$fa)
    $audit.at=[DateTimeOffset]::UtcNow.ToString('o');$audit.original_index_sha256=$ExpectedIndexSha256
    $audit.authority='User approved defining scope then deletion. Nine fixed repository-local development profiles; only 642 proven regenerable cache members in 72 units. Whole-profile disposal is NOT established.'
    $audit.restore_policy='No byte backup of deleted caches; later browser use can rebuild caches but cannot restore exact historical cache contents or warm-cache benchmark state. All 9485 non-cache files remain unchanged. No browser is launched here.'
    $audit.evidence=@{profile_layout_and_index_magic_verified=$true;profile_producer_not_established=$true;cache_documentation='https://www.chromium.org/developers/design-documents/network-stack/disk-cache/';profile_documentation='https://chromium.googlesource.com/chromium/src/+/main/docs/user_data_dir.md'}
    $audit.profiles=$specs;$audit.tooling=$tooling.ToArray();$audit.repository_reference_check=$references.ToArray();$audit.live_reference_check=$usage
    $audit.journal_path=$journalPath;$audit.journal_sha256=$null;$audit.deleted_files=0;$audit.deleted_bytes=0;$audit.deleted_directories=0;$audit.existing_acl_writes=0;$audit.remote_server_operations=0
    $audit.existing_directory_acl=$acl
    Write-DistEvent $journal @{event='PLAN';audit=$audit}
    $indexStream.Dispose();$indexStream=$null
    Write-ChromeCacheIndex $document $audit $index $ExpectedIndexSha256 $repo
    $document.Dispose();$indexStream=[SflCleanupNativeV1]::OpenFile($index,$false);$pendingHash=Get-DistHash $indexStream
    $indexStream.Position=0;$document=[System.Text.Json.JsonDocument]::Parse($indexStream)
    $phase='remove-exact-files';Write-Host '[4/5] Delete only the 642 pinned cache files; retain every directory and non-cache file.'
    foreach($f in $files){Remove-TestCachePinned $sources[$f.path] $journal $confirmed;if($confirmed.Count%100-eq0){Write-Host ('[DELETED] '+$confirmed.Count+'/642')}}
    $phase='postcheck';Write-Host '[5/5] Verify absence, all 9485 preserved hashes/metadata, membership and existing directory ACLs.'
    foreach($f in $files){if(Test-Path -LiteralPath $f.path){throw 'Deleted cache reappeared'}}
    foreach($b in $boundaries.Keys){Assert-StageMembership $boundaries[$b] (Get-DistTree $b) @($files.path)}
    foreach($p in $acl.Keys){if((Get-Acl -LiteralPath $p).Sddl-cne$acl[$p]){throw 'Existing directory ACL changed'}}
    $verified=0
    foreach($p in $retained.Keys){$v=$retained[$p];Assert-DistMetadata (Get-DistMetadata $p) $v.metadata;if((Get-DistHash $v.stream)-cne$v.sha256){throw 'Retained profile hash changed'};$verified++;if($verified%2000-eq0){Write-Host ('[PRESERVED] '+$verified+'/9485')}}
    if($confirmed.Count-ne642){throw 'Deletion confirmation count differs'}
    $audit.state='COMPLETE';$audit.deleted_files=642;$audit.deleted_bytes=211061627;$audit.completed_at=[DateTimeOffset]::UtcNow.ToString('o')
    Write-DistEvent $journal @{event='COMPLETE';audit_id=$audit.id;deleted_files=642;deleted_bytes=211061627;preserved_files_verified=9485;deleted_directories=0;existing_acl_writes=0}
    $journal.Flush($true);$audit.journal_sha256=Get-DistHash $journal
    $phase='publish-completion';$indexStream.Dispose();$indexStream=$null
    Write-ChromeCacheIndex $document $audit $index $pendingHash $repo
    $check=[IO.File]::OpenRead($index);try{$newHash=Get-DistHash $check}finally{$check.Dispose()}
    [pscustomobject]@{state='COMPLETE';deleted_files=642;logical_bytes_freed=211061627;preserved_files_verified=9485;deleted_directories=0;existing_acl_writes=0;remote_server_operations=0;audit_id=$audit.id;journal_path=$journalPath;index_sha256=$newHash}|ConvertTo-Json -Compress
}catch{
    if($null-ne$journal){try{Write-DistEvent $journal @{event='HOLD';phase=$phase;confirmed_deleted_files=$confirmed.Count;confirmed_paths=@($confirmed.path)}}catch{Write-Warning 'Journal write failed; preserve pending index'}}
    Write-Host ('[HOLD] phase='+$phase+' confirmed_deleted_files='+$confirmed.Count+'. Preserve journal/index/.writing; no automatic retry, ACL change or further deletion.')
    throw
}finally{
    if($null-ne$journal){$journal.Dispose()};if($null-ne$indexStream){$indexStream.Dispose()};if($null-ne$document){$document.Dispose()}
    foreach($s in $pins){$s.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}
}
