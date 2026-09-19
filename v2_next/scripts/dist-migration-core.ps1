# Narrow transaction primitives. No top-level actions; imported only after external hash verification.
Set-StrictMode -Version Latest
function Get-DistHash([IO.Stream]$Stream) {
    $Stream.Position=0
    $sha=[Security.Cryptography.SHA256]::Create()
    try { return [Convert]::ToHexString($sha.ComputeHash($Stream)) } finally {$sha.Dispose()}
}
function Assert-DistPlain([string]$Path) {
    $node=Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if(($node.Attributes-band[IO.FileAttributes]::ReparsePoint)-ne 0){throw 'Reparse boundary'}
}
function Add-DistGuard([string]$Path,[hashtable]$Guards) {
    $full=[IO.Path]::GetFullPath($Path)
    if($Guards.ContainsKey($full)){return}
    $parent=[IO.Directory]::GetParent($full)
    if($null-ne$parent){Add-DistGuard $parent.FullName $Guards}
    Assert-DistPlain $full
    $handle=[SflCleanupNativeV1]::GuardDirectory($full)
    $Guards[$full]=[pscustomobject]@{handle=$handle;identity=[SflCleanupNativeV1]::Identity($handle,$full,$true)}
}
function Get-DistMetadata([string]$Path) {
    $f=Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    Assert-DistPlain $Path
    return [ordered]@{path=$Path;bytes=$f.Length;creation_utc_ticks=$f.CreationTimeUtc.Ticks.ToString();last_write_utc_ticks=$f.LastWriteTimeUtc.Ticks.ToString();attributes=[int]$f.Attributes;sddl=(Get-Acl -LiteralPath $Path).Sddl}
}
function Assert-DistMetadata($Actual,$Expected) {
    foreach($field in @('path','bytes','creation_utc_ticks','last_write_utc_ticks','attributes','sddl')){
        if([string]$Actual[$field]-cne[string]$Expected.$field){throw ('Source metadata changed: '+$field)}
    }
}
function Open-DistSource($Record,[bool]$Delete,[hashtable]$Guards) {
    Add-DistGuard ([IO.Path]::GetDirectoryName($Record.path)) $Guards
    $stream=[SflCleanupNativeV1]::OpenFile($Record.path,$Delete)
    try {
        [SflCleanupNativeV1]::NoAlternateStreams($Record.path,$false)
        if(((Get-Item -LiteralPath $Record.path -Force).Attributes-band[IO.FileAttributes]'ReadOnly,ReparsePoint,Offline,Encrypted,SparseFile,Compressed')-ne 0){throw 'Unsupported source attributes; preserve file'}
        if($stream.Length-ne$Record.bytes-or(Get-DistHash $stream)-cne$Record.sha256){throw 'Source hash/length changed'}
        if($Record.metadata){Assert-DistMetadata (Get-DistMetadata $Record.path) $Record.metadata}
        return [pscustomobject]@{stream=$stream;identity=[SflCleanupNativeV1]::Identity($stream.SafeFileHandle,$Record.path,$false);record=$Record}
    }catch{$stream.Dispose();throw}
}
function New-DistAcl([bool]$Directory) {
    if($Directory){$acl=[Security.AccessControl.DirectorySecurity]::new();$inherit=[Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'}
    else{$acl=[Security.AccessControl.FileSecurity]::new();$inherit=[Security.AccessControl.InheritanceFlags]::None}
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    foreach($sid in @('S-1-5-18','S-1-5-32-544')){
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl',$inherit,'None','Allow'))
    }
    return $acl
}
function Assert-DistPrivate([string]$Path,[bool]$Directory) {
    Assert-DistPlain $Path
    $a=Get-Acl -LiteralPath $Path
    if(-not$a.AreAccessRulesProtected-or$a.GetOwner([Security.Principal.SecurityIdentifier]).Value-cne'S-1-5-32-544'){throw 'Archive owner/inheritance differs'}
    $r=@($a.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]));$seen=@{}
    foreach($item in $r){
        $sid=$item.IdentityReference.Value
        $inherit=if($Directory){3}else{0}
        if($sid-cnotin@('S-1-5-18','S-1-5-32-544')-or$seen.ContainsKey($sid)-or$item.IsInherited-or
            $item.AccessControlType-ne'Allow'-or$item.FileSystemRights-ne'FullControl'-or[int]$item.InheritanceFlags-ne$inherit-or[int]$item.PropagationFlags-ne 0){throw 'Archive ACL differs'}
        $seen[$sid]=$true
    }
    if($seen.Count-ne 2-or$r.Count-ne 2){throw 'Archive ACL count differs'}
}
function New-DistDirectory([string]$Path,[hashtable]$Guards) {
    if(Test-Path -LiteralPath $Path){throw 'Archive must be new; do not reuse it'}
    Add-DistGuard ([IO.Path]::GetDirectoryName($Path)) $Guards
    [IO.FileSystemAclExtensions]::Create([IO.DirectoryInfo]::new($Path),(New-DistAcl $true))
    Add-DistGuard $Path $Guards
    Assert-DistPrivate $Path $true
}
function New-DistPrivateFile([string]$Path) {
    return [IO.FileSystemAclExtensions]::Create([IO.FileInfo]::new($Path),'CreateNew','FullControl','Read',65536,'WriteThrough',(New-DistAcl $false))
}
function Write-DistEvent([IO.Stream]$Journal,$Record) {
    $b=[Text.UTF8Encoding]::new($false).GetBytes(($Record|ConvertTo-Json -Depth 40 -Compress)+"`n")
    $Journal.Write($b,0,$b.Length);$Journal.Flush($true)
}
function Copy-DistPinned($Source,[string]$Destination) {
    $r=$Source.record
    $writer=New-DistPrivateFile $Destination
    try {$Source.stream.Position=0;$Source.stream.CopyTo($writer);$writer.Flush($true)}finally{$writer.Dispose()}
    if($r.metadata){
        [IO.File]::SetCreationTimeUtc($Destination,[DateTime]::new([long]$r.metadata.creation_utc_ticks,[DateTimeKind]::Utc))
        [IO.File]::SetLastWriteTimeUtc($Destination,[DateTime]::new([long]$r.metadata.last_write_utc_ticks,[DateTimeKind]::Utc))
    }
    Assert-DistPrivate $Destination $false
    if($r.metadata){
        $m=Get-DistMetadata $Destination
        if($m.creation_utc_ticks-cne$r.metadata.creation_utc_ticks-or$m.last_write_utc_ticks-cne$r.metadata.last_write_utc_ticks){throw 'Copied timestamps differ; preserve source'}
    }
    $s=[SflCleanupNativeV1]::OpenFile($Destination,$false)
    try {
        [SflCleanupNativeV1]::NoAlternateStreams($Destination,$false)
        if($s.Length-ne$r.bytes-or(Get-DistHash $s)-cne$r.sha256){throw 'Copied file failed verification; retain source'}
        return [pscustomobject]@{stream=$s;path=$Destination;sha256=$r.sha256;bytes=$r.bytes;identity=[SflCleanupNativeV1]::Identity($s.SafeFileHandle,$Destination,$false)}
    }catch{$s.Dispose();throw}
}
function Remove-DistPinned($Source,$Keeper,[IO.Stream]$Journal,[Collections.Generic.List[object]]$Confirmed) {
    $r=$Source.record
    if($r.keeper-cne$Keeper.path-or$r.sha256-cne$Keeper.sha256-or$r.bytes-ne$Keeper.bytes){throw 'Keeper mapping mismatch'}
    if([SflCleanupNativeV1]::Identity($Source.stream.SafeFileHandle,$r.path,$false)-cne$Source.identity-or
        [SflCleanupNativeV1]::Identity($Keeper.stream.SafeFileHandle,$Keeper.path,$false)-cne$Keeper.identity){throw 'Pinned identity differs'}
    # The verified streams remain open, denying write/delete sharing throughout the transaction.
    [SflCleanupNativeV1]::NoAlternateStreams($r.path,$false)
    Write-DistEvent $Journal @{event='DELETE_INTENT';path=$r.path;identity=$Source.identity;keeper=$Keeper.path;sha256=$r.sha256}
    [SflCleanupNativeV1]::MarkFile($Source.stream)
    $Source.stream.Dispose()
    # Count the irreversible action even if a subsequent receipt write fails.
    $Confirmed.Add($r)
    if([IO.File]::Exists($r.path)){throw 'Deletion pending or path replaced; stop without further deletion'}
    Write-DistEvent $Journal @{event='DELETED';path=$r.path;keeper=$Keeper.path;sha256=$r.sha256}
}
function Assert-DistSums([object[]]$Groups,[hashtable]$Keepers) {
    foreach($g in $Groups){
        $manifest=$Keepers[(Join-Path $g.destination 'SHA256SUMS.txt')]
        $manifest.stream.Position=0;$reader=[IO.StreamReader]::new($manifest.stream,[Text.UTF8Encoding]::new($false,$true),$false,1024,$true)
        try{$lines=$reader.ReadToEnd().Trim()-split'\r?\n'}finally{$reader.Dispose()}
        if($lines.Count-ne 2){throw 'CI checksum count differs'}
        $seen=@{}
        foreach($line in $lines){
            if($line-cnotmatch'^([a-fA-F0-9]{64}) [ *]([^\\/:]+)$'){throw 'CI checksum syntax differs'}
            $name=$Matches[2];$sha=$Matches[1].ToUpperInvariant()
            if($name-in@('.','..')-or$seen.ContainsKey($name)){throw 'CI checksum duplicate/traversal'}
            $seen[$name]=$true;$p=Join-Path $g.destination $name
            if(-not$Keepers.ContainsKey($p)-or$Keepers[$p].sha256-cne$sha){throw 'CI checksum keeper differs'}
        }
        if(@($g.files).Count-ne 3){throw 'CI member count differs'}
    }
}
function Get-DistTree([string]$Root) {
    $stack=[Collections.Generic.Stack[string]]::new();$stack.Push($Root)
    $files=[Collections.Generic.List[string]]::new();$dirs=[Collections.Generic.List[string]]::new()
    while($stack.Count){
        $p=$stack.Pop();Assert-DistPlain $p;$dirs.Add($p)
        foreach($item in [IO.DirectoryInfo]::new($p).EnumerateFileSystemInfos()){
            if(($item.Attributes-band[IO.FileAttributes]::ReparsePoint)-ne 0){throw 'dist link changed'}
            if($item-is[IO.DirectoryInfo]){$stack.Push($item.FullName)}else{$files.Add($item.FullName)}
        }
    }
    return @{files=$files.ToArray();directories=$dirs.ToArray()}
}
function Assert-DistUnchanged($Audit,[string[]]$Removed=@()) {
    $gone=@{};foreach($p in $Removed){$gone[$p]=$true}
    $tree=Get-DistTree $Audit.plan.root
    $expected=@($Audit.outside_files|Where-Object {-not$gone.ContainsKey($_.path)})
    if($tree.files.Count-ne$expected.Count-or$tree.directories.Count-ne$Audit.directories.Count){throw 'dist membership changed'}
    $present=@{};foreach($p in $tree.files){$present[$p]=$true}
    foreach($r in $expected){if(-not$present.ContainsKey($r.path)){throw 'dist file membership differs'};Assert-DistMetadata (Get-DistMetadata $r.path) $r}
    foreach($p in $Audit.directories){if($p-cnotin$tree.directories){throw 'dist directory membership differs'}}
    foreach($b in $Audit.plan.existing_boundaries){if((Get-Acl -LiteralPath $b.path).Sddl-cne$b.sddl){throw 'Existing boundary ACL changed'}}
}
function Write-DistIndexCompletion([System.Text.Json.JsonDocument]$Document,$Audit,[string]$Path,[string]$ExpectedHash) {
    # Stream-copy the large JSON tree: avoid PowerShell's slow, lossy full ConvertFrom-Json.
    $temp=$Path+'.writing';$out=[IO.File]::Open($temp,'CreateNew','Write','None')
    $writer=[System.Text.Json.Utf8JsonWriter]::new($out)
    $removed=@{};foreach($f in $Audit.plan.files){$removed[$f.path]=$true}
    $at=[DateTimeOffset]::UtcNow.ToString('o')
    $event=@{at=$at;kind=$Audit.kind;audit_id=$Audit.id;state='COMPLETE';deleted_files=9;deleted_bytes=744244326;moved_files=12;removed_source_files=21;existing_acl_writes=0;remote_server_operations=0}
    function WriteSmall($Value){$small=[System.Text.Json.JsonDocument]::Parse(($Value|ConvertTo-Json -Depth 60 -Compress));try{$small.RootElement.WriteTo($writer)}finally{$small.Dispose()}}
    try {
        $writer.WriteStartObject()
        foreach($prop in $Document.RootElement.EnumerateObject()){
            $writer.WritePropertyName($prop.Name)
            switch($prop.Name){
                'updated_at' {$writer.WriteStringValue($at)}
                'audits' {$writer.WriteStartArray();foreach($a in $prop.Value.EnumerateArray()){if($a.GetProperty('id').GetString()-ceq$Audit.id){WriteSmall $Audit}else{$a.WriteTo($writer)}};$writer.WriteEndArray()}
                'history' {$writer.WriteStartArray();foreach($e in $prop.Value.EnumerateArray()){$e.WriteTo($writer)};WriteSmall $event;$writer.WriteEndArray()}
                'files' {
                    $writer.WriteStartArray()
                    foreach($f in $prop.Value.EnumerateArray()){if(-not$removed.ContainsKey($f.GetProperty('path').GetString())){$f.WriteTo($writer)}}
                    foreach($g in $Audit.plan.groups){foreach($f in $g.files){WriteSmall @{path=$f.destination;root=$Audit.plan.archive_root;bytes=$f.bytes;state='PROTECT_MIGRATED_CI_RELEASE';original_path=$f.path;migration_sha256=$f.sha256}}}
                    $writer.WriteEndArray()
                }
                'roots' {
                    $writer.WriteStartArray();foreach($r in $prop.Value.EnumerateArray()){
                        if($r.GetProperty('path').GetString()-ceq$Audit.plan.root){$v=$r.GetRawText()|ConvertFrom-Json;$v.file_count-=21;$v.bytes-=2871185450;WriteSmall $v}else{$r.WriteTo($writer)}
                    }
                    WriteSmall @{path=$Audit.plan.archive_root;origin='APPROVED_EXACT_ARCHIVE_MAPPING';state='PROTECTED_EXACT_MEMBERS_VERIFIED';file_count=12;bytes=2126941124;errors=@()};$writer.WriteEndArray()
                }
                'summary' {$v=$prop.Value.GetRawText()|ConvertFrom-Json;$v.files-=9;$v.bytes-=744244326;$v.roots++;$v.deleted_files+=9;$v.deleted_bytes+=744244326;$v.migrated_files+=12;WriteSmall $v}
                'validation' {WriteSmall @{at=$at;state='DIST_TRANSACTION_VERIFIED_GLOBAL_RECHECK_PENDING';dist_source_files_absent=21;dist_archive_hashes_verified=12;prior_global_validation=$prop.Value.GetRawText()|ConvertFrom-Json}}
                default {$prop.Value.WriteTo($writer)}
            }
        }
        $writer.WriteEndObject();$writer.Flush();$out.Flush($true)
    }finally{$writer.Dispose();$out.Dispose()}
    $current=[IO.File]::Open($Path,'Open','Read','Read')
    try{if((Get-DistHash $current)-cne$ExpectedHash){throw 'Concurrent index change; preserve .writing and protected receipt'}}finally{$current.Dispose()}
    [IO.File]::Move($temp,$Path,$true)
}
