[CmdletBinding(SupportsShouldProcess,ConfirmImpact='High')]
param([Parameter(Mandatory)][string]$ExpectedIndexSha256,[switch]$RemoveReviewed)
# Review is read-only by default. Removal requires the fixed approved review and external registry hash.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$reviewCmdlet=$PSCmdlet

function AssertPlain([string]$Path) {
    $full=[IO.Path]::GetFullPath($Path);$node=[IO.FileInfo]::new($full)
    while($null-ne$node){
        if(([IO.File]::GetAttributes($node.FullName)-band[IO.FileAttributes]::ReparsePoint)-ne 0){throw 'Linked path rejected'}
        if($node-is[IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
    }
    return $full
}
function GetReviewDecision([string]$Relative) {
    if($Relative.Contains('\')-or$Relative-match'(^|/)\.{1,2}(/|$)|[\x00-\x1f:]'){throw 'Noncanonical review path'}
    if($Relative-cmatch'^v2_next/(?:backend|scripts)/(?:[A-Za-z0-9_]+/)*__pycache__/([A-Za-z0-9_]+)\.cpython-312\.pyc$'){
        return [pscustomobject]@{action='DELETE_CANDIDATE';reason='PYTHON_CACHE_WITH_TRACKED_SOURCE';source_relative=($Relative-replace'/__pycache__/([A-Za-z0-9_]+)\.cpython-312\.pyc$','/$1.py')}
    }
    if($Relative-cmatch'^v2_next/\.mypy_cache/(?:\.gitignore|CACHEDIR\.TAG|3\.12/cache\.db)$'-or$Relative-cmatch'^v2_next/\.ruff_cache/(?:\.gitignore|CACHEDIR\.TAG|0\.15\.15/[0-9]+)$'){
        return [pscustomobject]@{action='DELETE_CANDIDATE';reason='TYPECHECK_OR_LINT_CACHE';source_relative=$null}
    }
    $prefix='v2_next/backend/build/SmartFactoryBackend/'
    if($Relative.StartsWith($prefix,[StringComparison]::Ordinal)){
        $leaf=$Relative.Substring($prefix.Length)
        $evidence=@('warn-SmartFactoryBackend.txt','xref-SmartFactoryBackend.html','Analysis-00.toc','COLLECT-00.toc','EXE-00.toc','PKG-00.toc','PYZ-00.toc')
        $intermediate=@('SmartFactoryBackend.pkg','SmartFactoryBackend.exe','PYZ-00.pyz','base_library.zip','localpycs/struct.pyc','localpycs/pyimod04_pywin32.pyc','localpycs/pyimod03_ctypes.pyc','localpycs/pyimod02_importers.pyc','localpycs/pyimod01_archive.pyc')
        if($leaf-cin$evidence){return [pscustomobject]@{action='KEEP';reason='HISTORICAL_BUILD_DIAGNOSTICS';source_relative=$null}}
        if($leaf-cin$intermediate){return [pscustomobject]@{action='DELETE_CANDIDATE';reason='PYINSTALLER_INTERMEDIATE';source_relative=$null}}
    }
    throw 'File outside the reviewed cache/intermediate allowlist'
}
function HashStream([IO.Stream]$Stream) {
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$Stream.Position=0;return [BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-','')}finally{$sha.Dispose()}
}
function ReadGit([string[]]$Arguments) {
    $output=& git --no-optional-locks -c core.fsmonitor=false -C $checkout @Arguments
    if($LASTEXITCODE-ne 0){throw 'Read-only Git check failed'}
    return $output
}
function AssertRecordMapping($Record,[string]$Root) {
    $decision=GetReviewDecision $Record.relative
    $expected=[IO.Path]::GetFullPath((Join-Path $Root $Record.relative))
    if(-not$expected.StartsWith($Root+'\',[StringComparison]::OrdinalIgnoreCase)-or$Record.file.path-ine$expected-or$Record.action-cne$decision.action-or$Record.reason-cne$decision.reason){throw 'Review mapping or decision differs'}
    if($decision.source_relative){
        if($null-eq$Record.retained_source-or$Record.retained_source.path-ine(Join-Path $Root $decision.source_relative)){throw 'Retained source mapping differs'}
    }elseif($null-ne$Record.retained_source){throw 'Unexpected retained source'}
    return $decision
}
function TimestampMatches([long]$Actual,$Recorded) {
    # Historical JSON numbers passed through Node Number, so only their binary64 precision survives.
    # New records use decimal strings and require exact ticks. No arbitrary time tolerance is used.
    if($Recorded-is[string]){return $Actual.ToString()-ceq$Recorded}
    if($Recorded-is[long]-or$Recorded-is[int]-or$Recorded-is[double]){return [double]$Actual-eq[double]$Recorded}
    return $false
}
function AssertNoRegisteredReferences {
    $refs=[Collections.Generic.List[string]]::new()
    foreach($proc in @(Get-CimInstance Win32_Process)){if($proc.ProcessId-ne$PID){$refs.Add([string]$proc.CommandLine);$refs.Add([string]$proc.ExecutablePath)}}
    foreach($service in @(Get-CimInstance Win32_Service)){$refs.Add([string]$service.PathName)}
    foreach($task in @(Get-ScheduledTask)){foreach($action in $task.Actions){foreach($field in @('Execute','Arguments','WorkingDirectory')){if($action.PSObject.Properties[$field]){$refs.Add([string]$action.$field)}}}}
    $shell=New-Object -ComObject WScript.Shell
    try {
        foreach($base in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('StartMenu'),[Environment]::GetFolderPath('CommonStartMenu'))){
            if(-not[IO.Directory]::Exists($base)){continue}
            foreach($link in @(Get-ChildItem -LiteralPath $base -Filter '*.lnk' -File -Recurse)){
                $shortcut=$shell.CreateShortcut($link.FullName)
                $refs.Add([string]$shortcut.TargetPath);$refs.Add([string]$shortcut.Arguments);$refs.Add([string]$shortcut.WorkingDirectory)
            }
        }
    } finally {[void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)}
    foreach($reference in $refs){if($reference.Replace('/','\').IndexOf($checkout,[StringComparison]::OrdinalIgnoreCase)-ge 0){throw 'Checkout is in use or registered; preserve it'}}
}
function AssertPinnedRecord($Record,[IO.Stream]$Stream) {
    [void](AssertPlain $Record.path)
    $item=Get-Item -LiteralPath $Record.path -Force
    if($item.PSIsContainer-or$Stream.Length-ne$Record.bytes-or(HashStream $Stream)-cne$Record.sha256){throw 'File content differs from review'}
    if($Record.PSObject.Properties['sddl']){
        if(-not(TimestampMatches $item.LastWriteTimeUtc.Ticks $Record.last_write_utc_ticks)-or-not(TimestampMatches $item.CreationTimeUtc.Ticks $Record.creation_utc_ticks)-or[int]$item.Attributes-ne$Record.attributes-or(Get-Acl -LiteralPath $Record.path).Sddl-cne$Record.sddl){throw 'File metadata differs from review'}
    }
    if(@(Get-Item -LiteralPath ('\\?\'+$Record.path) -Stream '*'|Where-Object Stream -ne ':$DATA').Count){throw 'Alternate stream appeared'}
}
function InvokeReviewedRemoval {
    $matches=@($index.audits|Where-Object id -ceq 'aad691e3-f40f-49d4-8124-0d225cedb867')
    if($matches.Count-ne 1){throw 'Exact approved review required'}
    $review=$matches[0]
    if($review.kind-cne'DESKTOP_BUILDS_CACHE_REVIEW'-or$review.state-cne'REVIEWED_NOT_AUTHORIZED_NOT_DELETED'-or$review.checkout-ine$checkout-or$review.head-cne$head-or$review.source_audit_id-cne$audit.id){throw 'Approved review differs'}
    if($review.PSObject.Properties['cleanup']){throw 'Cleanup already attempted; no automatic retry'}
    if($review.records.Count-ne 102){throw 'Reviewed record count changed'}
    $remove=@($review.records|Where-Object action -ceq 'DELETE_CANDIDATE')
    $keep=@($review.records|Where-Object action -ceq 'KEEP')
    if($remove.Count-ne 95-or$keep.Count-ne 7-or($remove.file|Measure-Object bytes -Sum).Sum-ne 35362418-or($keep.file|Measure-Object bytes -Sum).Sum-ne 2826356){throw 'Approved count/bytes changed'}
    $held=@{};$protected=@{};$begun=$false;$version=$ExpectedIndexSha256
    function PinReviewed($Record) {
        $full=[IO.Path]::GetFullPath($Record.path)
        if(-not$full.StartsWith($checkout+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Pinned record escapes checkout'}
        [void](AssertPlain $full)
        if(-not$held.ContainsKey($full)){$held[$full]=[IO.File]::Open($full,'Open','Read','Read')}
        AssertPinnedRecord $Record $held[$full]
    }
    function SaveRemoval {
        [void](AssertPlain $registry)
        if((Get-FileHash -LiteralPath $registry).Hash-cne$script:removalVersion){throw 'Concurrent registry update; preserve state'}
        $index.updated_at=[DateTimeOffset]::Now.ToString('o')
        $writing=$registry+'.writing';$output=[IO.File]::Open($writing,'CreateNew','Write','None')
        try{$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($index|ConvertTo-Json -Depth 35 -Compress));$output.Write($bytes,0,$bytes.Length);$output.Flush($true)}finally{$output.Dispose()}
        [IO.File]::Move($writing,$registry,$true)
        $script:removalVersion=(Get-FileHash -LiteralPath $registry).Hash
    }
    $script:removalVersion=$version
    try {
        $seen=@{}
        foreach($record in $review.records){
            $decision=AssertRecordMapping $record $checkout
            if($seen.ContainsKey($record.relative)-or$tracked.ContainsKey($record.relative)-or-not$ignored.ContainsKey($record.relative)){throw 'Duplicate, tracked or no longer ignored target'}
            $seen[$record.relative]=$true;PinReviewed $record.file
            if($record.action-ceq'KEEP'){$protected[$record.file.path]=$record.file}
            if($decision.source_relative){
                if(-not$tracked.ContainsKey($decision.source_relative)){throw 'Retained Python source is not tracked'}
                PinReviewed $record.retained_source;$protected[$record.retained_source.path]=$record.retained_source
            }
        }
        foreach($record in @($review.git_index,$review.build_spec)){PinReviewed $record;$protected[$record.path]=$record}
        foreach($anchor in $review.source_anchors){
            $record=[pscustomobject]@{path=(Join-Path $checkout $anchor.relative);bytes=(Get-Item -LiteralPath (Join-Path $checkout $anchor.relative)).Length;sha256=$anchor.sha256}
            PinReviewed $record;$protected[$record.path]=$record
        }
        foreach($package in $audit.packages){
            $record=[pscustomobject]@{path=(Join-Path $checkout $package.relative);bytes=$package.bytes;sha256=$package.sha256}
            PinReviewed $record;$protected[$record.path]=$record
        }
        foreach($record in $remove){if($protected.ContainsKey($record.file.path)){throw 'A protected witness is also a deletion target'}}
        AssertNoRegisteredReferences
        if([string](ReadGit @('rev-parse','HEAD'))-cne$head-or@(ReadGit @('status','--porcelain=v1','--untracked-files=all')).Count){throw 'Checkout changed'}
        Write-Host '[VERIFIED] Exact 95 files / 35362418 bytes; 7 diagnostics and source/package witnesses preserved; no directory deletion.'
        if(-not$reviewCmdlet.ShouldProcess($checkout,'Permanently remove only the approved 95 cache/intermediate files')){return}
        $exactMetadata=@($review.records|ForEach-Object {
            $item=Get-Item -LiteralPath $_.file.path -Force
            [pscustomobject]@{path=$_.file.path;creation_utc_ticks=$item.CreationTimeUtc.Ticks.ToString();last_write_utc_ticks=$item.LastWriteTimeUtc.Ticks.ToString()}
        })
        $exactByPath=@{};foreach($metadata in $exactMetadata){$exactByPath[$metadata.path]=$metadata}
        $cleanup=[pscustomobject]@{id=[Guid]::NewGuid().ToString();kind='LOCAL_BUILD_CACHE_DELETE';review_id=$review.id;at=[DateTimeOffset]::Now.ToString('o');state='DELETING';authorized_files=95;authorized_bytes=35362418;deleted_files=0;deleted_bytes=0L;deleted_directories=0;deleted_paths=@();kept_files_verified=0;remote_server_operations=0;error=$null;completed_at=$null;authority='2026-09-16 user approval of the exact 95-file, 33.72 MiB permanent deletion proposal';exact_metadata=$exactMetadata;timestamp_policy='Historical numeric ticks checked at their surviving binary64 precision; current exact string ticks journaled and rechecked before deletion; original review not rewritten.'}
        $review|Add-Member -NotePropertyName cleanup -NotePropertyValue $cleanup
        $index.history=@($index.history)+$cleanup
        SaveRemoval;$begun=$true
        foreach($record in $remove){
            AssertPinnedRecord $record.file $held[$record.file.path]
            $item=Get-Item -LiteralPath $record.file.path -Force;$metadata=$exactByPath[$record.file.path]
            if(-not(TimestampMatches $item.CreationTimeUtc.Ticks $metadata.creation_utc_ticks)-or-not(TimestampMatches $item.LastWriteTimeUtc.Ticks $metadata.last_write_utc_ticks)){throw 'Exact execution timestamp changed'}
            if($record.retained_source){AssertPinnedRecord $record.retained_source $held[$record.retained_source.path]}
            $held[$record.file.path].Dispose();[void]$held.Remove($record.file.path)
            Remove-Item -LiteralPath $record.file.path -Force -ErrorAction Stop
            if(Test-Path -LiteralPath $record.file.path){throw 'Removed file still exists'}
            $cleanup.deleted_paths+= $record.file.path;$cleanup.deleted_files++;$cleanup.deleted_bytes+=[long]$record.file.bytes
            if($cleanup.deleted_files%25-eq 0){SaveRemoval;Write-Host ('[REMOVED] '+$cleanup.deleted_files+'/95')}
        }
        foreach($record in $protected.Values){AssertPinnedRecord $record $held[$record.path]}
        if([string](ReadGit @('rev-parse','HEAD'))-cne$head-or@(ReadGit @('status','--porcelain=v1','--untracked-files=all')).Count){throw 'Source checkout changed'}
        $cleanup.kept_files_verified=$keep.Count;$cleanup.state='COMPLETE';$cleanup.completed_at=[DateTimeOffset]::Now.ToString('o');SaveRemoval
        $cleanup|Select-Object state,deleted_files,deleted_bytes,deleted_directories,kept_files_verified,remote_server_operations|ConvertTo-Json
    }catch{
        if($begun){$cleanup.state='PARTIAL_STOPPED';$cleanup.error=$_.Exception.Message;SaveRemoval}
        throw
    }finally{foreach($pin in $held.Values){$pin.Dispose()}}
}
if($PSVersionTable.PSVersion.Major-lt 7){throw 'Development PC PowerShell 7 required'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$registry=Join-Path $repo 'verification-files.local.json'
[void](AssertPlain $registry)
if((Get-FileHash -LiteralPath $registry).Hash-cne$ExpectedIndexSha256){throw 'Registry hash changed'}
$index=Get-Content -LiteralPath $registry -Raw|ConvertFrom-Json
if($index.host-ine[Environment]::MachineName-or$index.workspace-ine$repo){throw 'Wrong development host/workspace'}
if(@($index.plans|Where-Object state -cne 'COMPLETE').Count-or@($index.migrations|Where-Object state -cne 'COMPLETE').Count){throw 'Unfinished operation'}
$audits=@($index.audits|Where-Object id -ceq '48c1e9fe-4708-43d9-bf67-876199d9ffa8')
if($audits.Count-ne 1){throw 'Exact prior classification required'}
$audit=$audits[0]
$checkout=Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Desktop\SmartFactoryLogger_Builds\spot-tcp-connection-reuse-remediation_bfd9be7\source'
if($audit.checkout-ine$checkout){throw 'Checkout boundary differs'}
[void](AssertPlain $checkout)
$head=[string](ReadGit @('rev-parse','HEAD'))
if($head-cne'bfd9be785f7a87aa4150445945861a54bca98f33'){throw 'Checkout identity differs'}
if(@(ReadGit @('status','--porcelain=v1','--untracked-files=all')).Count){throw 'Checkout is dirty'}
$tracked=@{};foreach($name in @(ReadGit @('ls-files'))){$tracked[$name]=$true}
$ignored=@{};foreach($name in @(ReadGit @('ls-files','--others','--ignored','--exclude-standard'))){$ignored[$name]=$true}
if($RemoveReviewed){InvokeReviewedRemoval;return}
if(@($index.audits|Where-Object kind -ceq 'DESKTOP_BUILDS_CACHE_REVIEW').Count){throw 'Review already recorded; do not overwrite or retry automatically'}
$candidates=@($audit.files|Where-Object classification -cin @('CANDIDATE_REGENERABLE_CACHE','CANDIDATE_REGENERABLE_BUILD_INTERMEDIATE'))
if($candidates.Count-ne 102){throw 'Reviewed scope differs'}
$pins=[Collections.Generic.List[IDisposable]]::new()
$records=[Collections.Generic.List[object]]::new()
function PinRecord([string]$Path) {
    [void](AssertPlain $Path)
    if(-not$Path.StartsWith($checkout+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Checkout escape'}
    $pin=[IO.File]::Open($Path,'Open','Read','Read');$pins.Add($pin)
    $item=Get-Item -LiteralPath $Path -Force
    $streams=@(Get-Item -LiteralPath ('\\?\'+$Path) -Stream '*'|Where-Object Stream -ne ':$DATA'|Select-Object Stream,Length)
    if($streams.Count){throw 'Alternate streams require separate review'}
    return [pscustomobject]@{path=$Path;bytes=$pin.Length;sha256=(HashStream $pin);last_write_utc_ticks=$item.LastWriteTimeUtc.Ticks.ToString();creation_utc_ticks=$item.CreationTimeUtc.Ticks.ToString();attributes=[int]$item.Attributes;sddl=(Get-Acl -LiteralPath $Path).Sddl;named_streams=0}
}
try {
    $gitIndex=PinRecord (Join-Path $checkout '.git\index')
    $seen=@{}
    foreach($candidate in $candidates){
        $relative=[string]$candidate.relative
        if($seen.ContainsKey($relative)-or$tracked.ContainsKey($relative)-or-not$ignored.ContainsKey($relative)){throw 'Duplicate, tracked or no longer ignored candidate'}
        $seen[$relative]=$true
        $decision=GetReviewDecision $relative
        $record=PinRecord (Join-Path $checkout $relative)
        if($record.bytes-ne$candidate.bytes){throw 'Candidate size changed since classification'}
        $source=$null
        if($decision.source_relative){
            if(-not$tracked.ContainsKey($decision.source_relative)){throw 'Python source is not retained by Git'}
            $source=PinRecord (Join-Path $checkout $decision.source_relative)
        }
        $records.Add([pscustomobject]@{relative=$relative;file=$record;action=$decision.action;reason=$decision.reason;retained_source=$source})
    }
    # Metadata/report files in the build directory remain KEEP, even though deploy recreates it.
    $anchors=@($audit.source_anchors|Where-Object relative -cin @('v2_next/scripts/deploy.ps1','v2_next/package.json'))
    foreach($anchor in $anchors){$actual=PinRecord (Join-Path $checkout $anchor.relative);if($actual.sha256-cne$anchor.sha256){throw 'Generating logic changed'}}
    $spec=PinRecord (Join-Path $checkout 'v2_next/backend/build_specs/SmartFactoryBackend.spec')
    AssertNoRegisteredReferences
    if([string](ReadGit @('rev-parse','HEAD'))-cne$head-or@(ReadGit @('status','--porcelain=v1','--untracked-files=all')).Count){throw 'Checkout changed during review'}
    foreach($record in $records){
        $item=Get-Item -LiteralPath $record.file.path -Force
        if($item.LastWriteTimeUtc.Ticks-ne$record.file.last_write_utc_ticks-or(Get-Acl -LiteralPath $record.file.path).Sddl-cne$record.file.sddl){throw 'Candidate metadata changed'}
    }
    $deletable=@($records|Where-Object action -ceq 'DELETE_CANDIDATE');$kept=@($records|Where-Object action -ceq 'KEEP')
    if($deletable.Count-ne 95-or$kept.Count-ne 7){throw 'Reviewed keep/delete split changed'}
    $review=[pscustomobject]@{
        id=[Guid]::NewGuid().ToString();kind='DESKTOP_BUILDS_CACHE_REVIEW';at=[DateTimeOffset]::Now.ToString('o')
        state='REVIEWED_NOT_AUTHORIZED_NOT_DELETED';source_audit_id=$audit.id;checkout=$checkout;head=$head
        reviewed_files=$records.Count;delete_candidate_files=$deletable.Count;delete_candidate_bytes=($deletable.file|Measure-Object bytes -Sum).Sum
        kept_files=$kept.Count;kept_bytes=($kept.file|Measure-Object bytes -Sum).Sum;records=@($records.ToArray())
        source_anchors=$anchors;build_spec=$spec;git_index=$gitIndex;registration_references_found=0
        registration_scope='Observable process executable/command lines, service paths, task actions, Desktop and Start Menu shortcuts; no global handle or shell-CWD proof.'
        source_writes=0;deleted_files=0;moved_files=0;remote_server_operations=0
        restore_policy='Python/lint/type caches regenerate from retained sources/tools. Build intermediates require a new build; exact historical bytes are not guaranteed. Seven build diagnostic/TOC files remain untouched.'
        next_action='Require approval of the exact 95-file list; revalidate hashes, source witnesses, Git, ADS/ACL and use state immediately before removal.'
    }
    if((Get-FileHash -LiteralPath $registry).Hash-cne$ExpectedIndexSha256){throw 'Concurrent registry update'}
    $index.audits=@($index.audits)+$review;$index.updated_at=$review.at
    $index.history=@($index.history)+[pscustomobject]@{at=$review.at;kind=$review.kind;audit_id=$review.id;state=$review.state;deleted_files=0;moved_files=0;remote_server_operations=0}
    $writing=$registry+'.writing';$output=[IO.File]::Open($writing,'CreateNew','Write','None')
    try{$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($index|ConvertTo-Json -Depth 35 -Compress));$output.Write($bytes,0,$bytes.Length);$output.Flush($true)}finally{$output.Dispose()}
    [IO.File]::Move($writing,$registry,$true)
    [pscustomobject]@{review_id=$review.id;state=$review.state;reviewed_files=$review.reviewed_files;delete_candidate_files=$review.delete_candidate_files;delete_candidate_bytes=$review.delete_candidate_bytes;kept_files=$review.kept_files;kept_bytes=$review.kept_bytes;deleted_files=0;index_sha256=(Get-FileHash -LiteralPath $registry).Hash}|ConvertTo-Json
} finally {foreach($pin in $pins){$pin.Dispose()}}
