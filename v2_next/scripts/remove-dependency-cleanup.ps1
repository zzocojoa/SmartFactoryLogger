[CmdletBinding(SupportsShouldProcess,ConfirmImpact='High')]
param([Parameter(Mandatory)][string]$ExpectedIndexSha256)
# Development PC only. The approved manifest is fixed; no recursive or wildcard removal.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function PlainPath([string]$Path) {
    $full=[IO.Path]::GetFullPath($Path);$node=[IO.FileInfo]::new($full)
    while($null-ne$node){
        if(([IO.File]::GetAttributes($node.FullName)-band[IO.FileAttributes]::ReparsePoint)-ne 0){throw 'Reparse boundary'}
        if($node-is[IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
    }
    return $full
}
function ChildPath([string]$Root,[string]$Relative) {
    if(-not$Relative-or$Relative.Contains('\')-or$Relative-match'(^|/)\.{0,2}(/|$)|[\x00-\x1f:]'){throw 'Noncanonical relative path'}
    $full=[IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if(-not$full.StartsWith($Root+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Child outside boundary'}
    return $full
}
function StreamHash([IO.Stream]$Stream) {
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$Stream.Position=0;return [Convert]::ToHexString($sha.ComputeHash($Stream))}finally{$sha.Dispose()}
}
function NsMatches([long]$Ticks,[string]$Nanoseconds) {
    return (([Numerics.BigInteger]$Ticks-[Numerics.BigInteger]621355968000000000)*100).ToString()-ceq$Nanoseconds
}
function SecurityDescriptor([string]$Path) {
    $acl=Get-Acl -LiteralPath $Path
    AssertTrustedAcl $acl
    return $acl.Sddl
}
function AssertTrustedAcl($Acl) {
    $trusted=@('S-1-5-18','S-1-5-32-544',[Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
    if($Acl.GetOwner([Security.Principal.SecurityIdentifier]).Value-cnotin$trusted){throw 'Untrusted owner'}
    foreach($rule in $Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
        # Write data/append/EA/attributes/delete-child/delete/DACL/owner, not read/synchronize.
        if($rule.AccessControlType-eq'Allow'-and($rule.PropagationFlags-band[Security.AccessControl.PropagationFlags]::InheritOnly)-eq 0-and$rule.IdentityReference.Value-cnotin$trusted-and([int]$rule.FileSystemRights-band 0xD0156)-ne 0){throw 'Untrusted write permission'}
    }
}
function InlineEvidence($Resolutions) {
    $found=@($Resolutions|Where-Object {$_.Contains('evidence')-and$null-ne$_['evidence']})
    if($found.Count-ne 1){throw 'Historical inline evidence missing'}
    return $found[0]['evidence']
}
function NoStreams([string]$Path) {
    if(@(Get-Item -LiteralPath ('\\?\'+$Path) -Stream '*' -ErrorAction Stop|Where-Object Stream -ne ':$DATA').Count){throw 'Named stream requires review'}
}
function ReadMetadata([string]$Path,$Record) {
    [void](PlainPath $Path)
    $item=Get-Item -LiteralPath $Path -Force
    if($item.PSIsContainer-or$item.Length-ne$Record.bytes-or-not(NsMatches $item.LastWriteTimeUtc.Ticks $Record.mtime_ns)-or-not(NsMatches $item.CreationTimeUtc.Ticks $Record.birthtime_ns)){throw 'File metadata changed'}
    if(([int]$item.Attributes-band(0x400-bor0x1000-bor0x4000)) -ne 0){throw 'Unsupported reparse/offline/encrypted attribute'}
    NoStreams $Path
    return @{attributes=[int]$item.Attributes;sddl=(SecurityDescriptor $Path);creation_ticks=$item.CreationTimeUtc.Ticks.ToString();write_ticks=$item.LastWriteTimeUtc.Ticks.ToString()}
}
function AssertMetadata($Actual,$Expected) {
    foreach($key in @('attributes','sddl','creation_ticks','write_ticks')){if([string]$Actual[$key]-cne[string]$Expected[$key]){throw 'Execution metadata changed'}}
}
function JournalOffset([string]$Json,[string]$Key,[string]$Prefix,[int]$Count) {
    $marker='"'+$Key+'":"'+$Prefix+':'
    $offset=$Json.IndexOf($marker,[StringComparison]::Ordinal)
    if($offset-lt 0-or$Json.IndexOf($marker,$offset+1,[StringComparison]::Ordinal)-ge 0){throw 'Journal marker is not unique'}
    $start=$offset+$marker.Length
    if($Json.Substring($start,$Count)-cne('P'*$Count)-or$Json[$start+$Count]-cne'"'){throw 'Unexpected journal state buffer'}
    return [long][Text.Encoding]::UTF8.GetByteCount($Json.Substring(0,$start))
}
function JournalTransition([IO.Stream]$Stream,[long]$Offset,[int]$Index,[int]$Count,[char]$From,[char]$To) {
    if($Index-lt 0-or$Index-ge$Count-or-not(($From-ceq'P'-and$To-ceq'R')-or($From-ceq'R'-and$To-ceq'D'))){throw 'Invalid journal transition'}
    $position=$Offset+$Index
    if($position-lt 0-or$position-ge$Stream.Length){throw 'Journal write outside file'}
    $Stream.Position=$position
    if($Stream.ReadByte()-ne[int]$From){throw 'Journal state differs'}
    $Stream.Position=$position;$Stream.WriteByte([byte][int]$To)
    if($Stream-is[IO.FileStream]){$Stream.Flush($true)}else{$Stream.Flush()}
}
function SaveIndex($Index,[string]$Path,[string]$ExpectedHash) {
    [void](PlainPath $Path)
    $text=$Index|ConvertTo-Json -Depth 60 -Compress
    $writing=$Path+'.writing';$out=[IO.File]::Open($writing,'CreateNew','Write','None')
    try{$bytes=[Text.UTF8Encoding]::new($false).GetBytes($text);$out.Write($bytes,0,$bytes.Length);$out.Flush($true)}finally{$out.Dispose()}
    if((Get-FileHash -LiteralPath $Path).Hash-cne$ExpectedHash){throw 'Concurrent registry change; preserve writing file'}
    [IO.File]::Move($writing,$Path,$true)
    return $text
}
function ReadGit([string[]]$Arguments) {
    $output=& git --no-optional-locks -c core.fsmonitor=false -C $checkout @Arguments
    if($LASTEXITCODE-ne 0){throw 'Read-only Git check failed'}
    return $output
}
function CheckGit {
    if([string](ReadGit @('rev-parse','HEAD'))-cne'bfd9be785f7a87aa4150445945861a54bca98f33'-or@(ReadGit @('status','--porcelain=v1','--untracked-files=all')).Count){throw 'Historical source checkout changed'}
}
function CheckUsage {
    $result=(& (Join-Path $PSScriptRoot 'read-dependency-use.ps1'))|ConvertFrom-Json -AsHashtable
    if($result.matches.Count){throw 'Registered or running reference found'}
    return $result
}
function CheckTree([string]$Root,$ExpectedFiles,$ExpectedDirs) {
    [void](PlainPath $Root)
    $foundFiles=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $foundDirs=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $stack=[Collections.Generic.Stack[string]]::new();$stack.Push($Root)
    while($stack.Count){
        $dir=$stack.Pop();[void]$foundDirs.Add($dir)
        foreach($item in [IO.DirectoryInfo]::new($dir).EnumerateFileSystemInfos()){
            if(($item.Attributes-band[IO.FileAttributes]::ReparsePoint)-ne 0){throw 'Tree contains a reparse entry'}
            if($item-is[IO.DirectoryInfo]){$stack.Push($item.FullName)}else{[void]$foundFiles.Add($item.FullName)}
        }
    }
    if(-not$foundFiles.SetEquals($ExpectedFiles)-or-not$foundDirs.SetEquals($ExpectedDirs)){throw 'Exact tree membership changed'}
}

if($PSVersionTable.PSVersion.Major-lt 7-or[Environment]::MachineName-cne'DESKTOP-SS5CURC'){throw 'Fixed development host and PowerShell 7 required'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'));$registry=Join-Path $repo 'verification-files.local.json'
[void](PlainPath $registry)
if((Get-FileHash -LiteralPath $registry).Hash-cne$ExpectedIndexSha256){throw 'External registry hash differs'}
$index=[IO.File]::ReadAllText($registry)|ConvertFrom-Json -AsHashtable
if($index.host-cne[Environment]::MachineName-or$index.workspace-cne$repo){throw 'Registry host/workspace differs'}
if(@($index.audits|Where-Object {$_.kind-ceq'DESKTOP_DEPENDENCY_ACL_PREFLIGHT_HOLD'-and$_.state-ceq'HOLD_ACL_TRUST_UNRESOLVED'}).Count){throw 'Unresolved ACL preflight HOLD; separate review required before retry'}
if(@($index.plans|Where-Object state -cne 'COMPLETE').Count-or@($index.migrations|Where-Object state -cne 'COMPLETE').Count){throw 'Existing operation incomplete'}
$matches=@($index.audits|Where-Object id -ceq '31bd411f-0c64-469c-91ed-f5c3acae335f')
if($matches.Count-ne 1){throw 'Exact approved plan missing'}
$plan=$matches[0]
if($plan.kind-cne'DESKTOP_BUILDS_DEPENDENCY_CLEANUP_PLAN'-or$plan.state-cne'PLAN_COMPLETE_AWAITING_APPROVAL'-or$plan.Contains('cleanup')){throw 'Plan is not new; no automatic retry'}
$checkout=Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Desktop\SmartFactoryLogger_Builds\spot-tcp-connection-reuse-remediation_bfd9be7\source'
$runRoot=Join-Path $repo '.tmp\dep-428c970f-1f0e-4127-802c-7b4ba9d621c0'
$rootMap=[ordered]@{
    'old-node'=(Join-Path $checkout 'v2_next\node_modules');'old-frontend'=(Join-Path $checkout 'v2_next\frontend\node_modules')
    'old-python'=(Join-Path $checkout 'v2_next\backend\.venv');'old-browsers'=(Join-Path $checkout 'v2_next\backend\browsers')
    'test-node'=(Join-Path $runRoot 'node\node_modules');'test-frontend'=(Join-Path $runRoot 'frontend\node_modules')
    'test-python'=(Join-Path $runRoot 'venv');'test-node-cache'=(Join-Path $runRoot 'temp\node-compile-cache')
}
if($plan.checkout-cne$checkout-or$plan.keep_root-cne$runRoot-or$plan.roots.Count-ne 8-or$plan.files.Count-ne 152043-or[long]($plan.files|Measure-Object bytes -Sum).Sum-ne 3267552016-or$plan.keep_files.Count-ne 4092){throw 'Approved counts or locations changed'}
$run=@($index.audits|Where-Object id -ceq $plan.reinstall_audit_id)[0]
$e=InlineEvidence $run.gap_review.resolutions
$files=[Collections.Generic.List[string]]::new();$dirs=[Collections.Generic.List[string]]::new();$seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach($root in $plan.roots){
    if(-not$rootMap.Contains($root.id)-or$root.root-cne$rootMap[$root.id]){throw 'Unapproved root mapping'}
    foreach($relative in $root.directories){$dir=if($relative){ChildPath $root.root $relative}else{$root.root};if(-not$seen.Add($dir)){throw 'Repeated directory'};$dirs.Add($dir)}
}
foreach($record in $plan.files){
    if(-not$rootMap.Contains($record.root_id)){throw 'Unapproved file root'}
    $file=ChildPath $rootMap[$record.root_id] $record.relative
    if(-not$seen.Add($file)){throw 'Repeated candidate path'};$files.Add($file)
}
$dirs=@($dirs|Sort-Object Length -Descending)
$pins=[Collections.Generic.List[IO.FileStream]]::new();$keepPins=[Collections.Generic.List[IO.FileStream]]::new()
$meta=[Collections.Generic.List[object]]::new();$sddls=[Collections.Generic.List[string]]::new();$sddlIds=@{}
$dirMeta=@{};$journal=$null;$begun=$false;$completed=$false;$phase='preflight';$processed=0;$deleted=0;$deletedBytes=0L;$deletedDirs=0
$clock=[Diagnostics.Stopwatch]::StartNew();$lastProgress=0
function Progress([string]$Phase,[int]$Count){
    if($clock.Elapsed.TotalSeconds-$script:lastProgress-ge 25){Write-Host "[PROGRESS] $Phase count=$Count elapsed=$($clock.Elapsed.ToString('hh\:mm\:ss'))";$script:lastProgress=$clock.Elapsed.TotalSeconds}
}
try {
    Write-Host '[1/5] Exact scope, clean source, current references and complete file inventory.'
    CheckGit;$usageBefore=CheckUsage
    $tracked=[Collections.Generic.HashSet[string]]::new([string[]]@(ReadGit @('ls-files')),[StringComparer]::Ordinal)
    $ignored=[Collections.Generic.HashSet[string]]::new([string[]]@(ReadGit @('ls-files','--others','--ignored','--exclude-standard')),[StringComparer]::Ordinal)
    foreach($root in $plan.roots){
        $rootFiles=[string[]]@($files|Where-Object {$_.StartsWith($root.root+'\',[StringComparison]::OrdinalIgnoreCase)})
        $rootDirs=[string[]]@($dirs|Where-Object {$_-ieq$root.root-or$_.StartsWith($root.root+'\',[StringComparison]::OrdinalIgnoreCase)})
        CheckTree $root.root $rootFiles $rootDirs
    }
    foreach($dir in $dirs){[void](PlainPath $dir);NoStreams $dir;$dirMeta[$dir]=SecurityDescriptor $dir}
    Write-Host '[2/5] Pin candidate files exclusively; verify SHA256, timestamps, ACLs and named streams. No deletion yet.'
    for($i=0;$i-lt$files.Count;$i++){
        $record=$plan.files[$i];$file=$files[$i]
        if($record.root_id.StartsWith('old-')){
            $relative=$file.Substring($checkout.Length+1).Replace('\','/')
            if($tracked.Contains($relative)-or-not$ignored.Contains($relative)){throw 'Tracked or no longer ignored candidate'}
        }
        $m=ReadMetadata $file $record
        $pin=[IO.FileStream]::new($file,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None,1,[IO.FileOptions]::SequentialScan);$pins.Add($pin)
        if($pin.Length-ne$record.bytes-or(StreamHash $pin)-cne$record.sha256){throw 'Candidate hash differs'}
        AssertMetadata (ReadMetadata $file $record) $m
        if(-not$sddlIds.ContainsKey($m.sddl)){$sddlIds[$m.sddl]=$sddls.Count;$sddls.Add($m.sddl)}
        $meta.Add(@{attributes=$m.attributes;sddl_id=$sddlIds[$m.sddl];creation_ticks=$m.creation_ticks;write_ticks=$m.write_ticks})
        $processed++;Progress 'candidate-preflight' $processed
    }
    Write-Host '[3/5] Verify and hold all recovery records and source/package witnesses. No deletion yet.'
    $keepers=[Collections.Generic.List[object]]::new()
    foreach($record in $plan.keep_files){$keepers.Add(@{path=(ChildPath $runRoot $record.relative);record=$record})}
    foreach($record in $plan.source_anchors){if(-not$record.path.StartsWith($checkout+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Source witness outside checkout'};$keepers.Add(@{path=$record.path;record=$record})}
    foreach($entry in $keepers){
        if($seen.Contains($entry.path)){throw 'Keeper overlaps candidate'}
        [void](PlainPath $entry.path)
        $pin=[IO.FileStream]::new($entry.path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read,1,[IO.FileOptions]::SequentialScan);$keepPins.Add($pin)
        if($pin.Length-ne$entry.record.bytes-or(StreamHash $pin)-cne$entry.record.sha256){throw 'Keeper changed'}
        Progress 'keeper-verification' $keepPins.Count
    }
    $buffer=[IO.MemoryStream]::new([Convert]::FromBase64String($e.content))
    try{if($buffer.Length-ne$e.bytes-or(StreamHash $buffer)-cne$e.sha256){throw 'Historical inline evidence changed'}}finally{$buffer.Dispose()}
    $usagePredelete=CheckUsage;CheckGit
    if((Get-FileHash -LiteralPath $registry).Hash-cne$ExpectedIndexSha256){throw 'Concurrent registry update'}
    Write-Host "[VERIFIED] files=$($files.Count) bytes=3267552016 directories=$($dirs.Count) keep=$($keepers.Count). All file contents remain unchanged."
    if(-not$PSCmdlet.ShouldProcess('Eight exact approved development dependency roots','Permanently delete pinned manifest files and their empty recorded directories')){return}
    $cleanupId=[Guid]::NewGuid().ToString();$fileStates=[char[]]('P'*$files.Count);$dirStates=[char[]]('P'*$dirs.Count)
    $cleanup=@{id=$cleanupId;kind='LOCAL_DEPENDENCY_DELETE';state='DELETING';started_at=[DateTimeOffset]::Now.ToString('o');completed_at=$null;authority='User approved the exact eight-root 152043-file / 3267552016-byte proposal in this task on 2026-09-16.';original_registry_sha256=$ExpectedIndexSha256;deleted_files=0;deleted_bytes=0L;deleted_directories=0;source_writes=0;remote_server_operations=0;file_states=($cleanupId+':'+(-join$fileStates));directory_states=($cleanupId+':'+(-join$dirStates));directory_order=$dirs;file_metadata=@($meta.ToArray());sddl_pool=@($sddls.ToArray());directory_sddl=$dirMeta;usage_before=$usageBefore;usage_predelete=$usagePredelete;kept_files_verified=0;error=$null;journal_contract='Index into plan.files / directory_order. P=pending, R=durable deletion request, D=durable absence confirmed. R after interruption is ambiguous and requires manual reconciliation. Never resume automatically.';use_limit='Process metadata and global shell current directories are not completely observable; every candidate is held with FileShare.None before deletion. No forced process shutdown or permission changes.'}
    $plan.cleanup=$cleanup;$plan.deletion_approved=$true
    $event=@{kind='LOCAL_DEPENDENCY_DELETE';audit_id=$plan.id;cleanup_id=$cleanupId;at=$cleanup.started_at;state='DELETING';deleted_files=0;deleted_bytes=0L;deleted_directories=0;remote_server_operations=0}
    $index.history=@($index.history)+$event;$index.updated_at=$cleanup.started_at
    $serialized=SaveIndex $index $registry $ExpectedIndexSha256;$begun=$true
    $fileOffset=JournalOffset $serialized 'file_states' $cleanupId $files.Count;$dirOffset=JournalOffset $serialized 'directory_states' $cleanupId $dirs.Count
    $journal=[IO.File]::Open($registry,'Open','ReadWrite','None');$serialized=$null
    $phase='file-delete';Write-Host '[4/5] Durable per-file deletion; no recursive removal and no cleanup of other roots.'
    for($i=0;$i-lt$files.Count;$i++){
        $file=$files[$i];$record=$plan.files[$i];$expected=$meta[$i].Clone();$expected.sddl=$sddls[$expected.sddl_id]
        AssertMetadata (ReadMetadata $file $record) $expected
        if((StreamHash $pins[$i])-cne$record.sha256){throw 'Pinned content changed before removal'}
        JournalTransition $journal $fileOffset $i $files.Count 'P' 'R';$fileStates[$i]='R'
        $pins[$i].Dispose()
        Remove-Item -LiteralPath $file -Force -ErrorAction Stop -Confirm:$false
        if(Test-Path -LiteralPath $file){throw 'Removed file still present'}
        JournalTransition $journal $fileOffset $i $files.Count 'R' 'D';$fileStates[$i]='D';$deleted++;$deletedBytes+=[long]$record.bytes
        Progress 'file-delete' $deleted
    }
    $phase='empty-directory-delete'
    for($i=0;$i-lt$dirs.Count;$i++){
        $dir=$dirs[$i];[void](PlainPath $dir);NoStreams $dir
        if((SecurityDescriptor $dir)-cne$dirMeta[$dir]-or[IO.Directory]::GetFileSystemEntries($dir).Count){throw 'Directory changed or not empty'}
        JournalTransition $journal $dirOffset $i $dirs.Count 'P' 'R';$dirStates[$i]='R'
        Remove-Item -LiteralPath $dir -Force -ErrorAction Stop -Confirm:$false
        if(Test-Path -LiteralPath $dir){throw 'Removed directory still present'}
        JournalTransition $journal $dirOffset $i $dirs.Count 'R' 'D';$dirStates[$i]='D';$deletedDirs++;Progress 'empty-directory-delete' $deletedDirs
    }
    $phase='post-verification';Write-Host '[5/5] Recheck all preserved recovery records, original source and absence of exact targets.'
    for($i=0;$i-lt$keepers.Count;$i++){
        [void](PlainPath $keepers[$i].path)
        if((StreamHash $keepPins[$i])-cne$keepers[$i].record.sha256){throw 'Preserved file changed'}
    }
    foreach($root in $rootMap.Values){if(Test-Path -LiteralPath $root){throw 'Target root still exists'}}
    CheckGit;$completed=$true;$cleanup.kept_files_verified=$keepers.Count
} catch {
    Write-Host "[HOLD] phase=$phase verified=$processed deleted=$deleted directories=$deletedDirs. Preserve the registry and remaining files; no automatic retry." -ForegroundColor Yellow
    if($begun){$cleanup.error=$_.Exception.Message}
    throw
} finally {
    $finalVersion=$null
    if($null-ne$journal){try{$finalVersion=StreamHash $journal}finally{$journal.Dispose()}}
    foreach($pin in $pins){$pin.Dispose()};foreach($pin in $keepPins){$pin.Dispose()}
    if($begun){
        $cleanup.file_states=$cleanupId+':'+(-join$fileStates);$cleanup.directory_states=$cleanupId+':'+(-join$dirStates)
        $cleanup.state=if($completed){'COMPLETE'}else{'PARTIAL_STOPPED'};$cleanup.deleted_files=$deleted;$cleanup.deleted_bytes=$deletedBytes;$cleanup.deleted_directories=$deletedDirs
        $cleanup.completed_at=[DateTimeOffset]::Now.ToString('o');$event.state=$cleanup.state;$event.deleted_files=$deleted;$event.deleted_bytes=$deletedBytes;$event.deleted_directories=$deletedDirs
        $index.updated_at=$cleanup.completed_at
        if($null-eq$finalVersion){throw 'No held registry version for finalization; preserve durable journal'}
        [void](SaveIndex $index $registry $finalVersion)
        Write-Host ('[RESULT] '+(@{state=$cleanup.state;deleted_files=$deleted;deleted_bytes=$deletedBytes;deleted_directories=$deletedDirs;kept_files_verified=$cleanup.kept_files_verified;remote_server_operations=0}|ConvertTo-Json -Compress))
    }
}
