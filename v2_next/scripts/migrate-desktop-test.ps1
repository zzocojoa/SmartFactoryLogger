[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$ExpectedIndexSha256,
    [Parameter(Mandatory)][string]$MigrationId,
    [ValidateSet('desktop-test','desktop-smartfactory','desktop-release','transfer-0695a0f-r1','transfer-0695a0f-r2','transfer-0695a0f-r3')][string]$Collection='desktop-test',
    [switch]$VerifyArchivesOnly
)
# Local PowerShell 7 only. Copy -> verify -> durable mapping -> remove exact source files.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function AssertPlain([string]$Path) {
    $full=[IO.Path]::GetFullPath($Path);$node=[IO.FileInfo]::new($full)
    while($null-ne$node){
        if(([IO.File]::GetAttributes($node.FullName)-band[IO.FileAttributes]::ReparsePoint)-ne 0){throw "Reparse boundary: $full"}
        if($node-is[IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
    }
    return $full
}
function StreamHash([IO.Stream]$Stream) {
    $sha=[Security.Cryptography.SHA256]::Create()
    try{if($Stream.CanSeek){$Stream.Position=0};return [BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-','')}finally{$sha.Dispose()}
}
function AclSignature($Acl) {
    $sidType=[Security.Principal.SecurityIdentifier]
    $rows=@($Acl.GetAccessRules($true,$true,$sidType)|ForEach-Object {
        $_.IdentityReference.Value+'|'+[int]$_.FileSystemRights+'|'+[int]$_.AccessControlType+'|'+[int]$_.InheritanceFlags+'|'+[int]$_.PropagationFlags
    }|Sort-Object)
    return $Acl.GetOwner($sidType).Value+';'+$Acl.GetGroup($sidType).Value+';'+($rows-join';')
}
function AssertFlatInventory([string]$Root,$Entries,[string]$Side) {
    [void](AssertPlain $Root)
    $children=@(Get-ChildItem -LiteralPath $Root -Force)
    if($children.Count-ne$Entries.Count){throw 'Source/destination inventory count changed'}
    $names=@{}
    foreach($f in $Entries){
        if($f.name-cne[IO.Path]::GetFileName($f.name)-or$names.ContainsKey($f.name)){throw 'Unsafe or duplicate leaf name'}
        if([IO.Path]::GetFullPath($f.$Side)-ine(Join-Path $Root $f.name)){throw 'File outside the exact migration boundary'}
        $names[$f.name]=$f
    }
    foreach($c in $children){
        if($c.PSIsContainer-or($c.Attributes-band[IO.FileAttributes]::ReparsePoint)-or-not$names.ContainsKey($c.Name)){throw 'Unexpected directory, link or file'}
        if($c.Length-ne$names[$c.Name].bytes){throw 'File size changed'}
    }
}
function CopyVerifiedFile($Record) {
    [void](AssertPlain $Record.source);[void](AssertPlain ([IO.Path]::GetDirectoryName($Record.destination)))
    if(Test-Path -LiteralPath $Record.destination){throw 'Destination exists; never overwrite evidence'}
    $original=Get-Item -LiteralPath $Record.source -Force
    $sourceAcl=Get-Acl -LiteralPath $Record.source
    [IO.File]::Copy($Record.source,$Record.destination,$false)
    [IO.File]::SetCreationTimeUtc($Record.destination,$original.CreationTimeUtc)
    [IO.File]::SetLastWriteTimeUtc($Record.destination,$original.LastWriteTimeUtc)
    [IO.File]::SetAttributes($Record.destination,$original.Attributes)
    if((AclSignature $sourceAcl)-cne(AclSignature (Get-Acl -LiteralPath $Record.destination))){throw 'Copy would change effective file access; preserve both locations'}
    if(@(Get-Item -LiteralPath $Record.destination -Stream '*'|Where-Object Stream -ne ':$DATA').Count){throw 'Unexpected destination alternate stream'}
    $pin=[IO.File]::Open($Record.destination,'Open','Read','Read')
    try{
        if($pin.Length-ne$Record.bytes-or(StreamHash $pin)-cne$Record.sha256){throw 'Copied content differs'}
        return $pin
    }catch{$pin.Dispose();throw}
}
function AssertChildPath([string]$Path,[string]$Root,[bool]$AllowRoot=$false) {
    $full=[IO.Path]::GetFullPath($Path);$base=[IO.Path]::GetFullPath($Root).TrimEnd('\')
    if(($AllowRoot-and$full-ieq$base)-or$full.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)){return $full}
    throw 'Path escapes the exact collection boundary'
}
function DestinationRelative([string]$Name,[string]$SelectedCollection) {
    if($SelectedCollection-ceq'desktop-release'){
        $parts=$Name.Split('\')
        if($parts[0]-ceq'spot_connecttimeout_field_kit_077b6b1c_rebuilt_20260727'){$parts[0]='kit-077b6b1'}
        return $parts-join'\'
    }
    return $Name
}
function AssertTreeInventory([string]$Root,$Files,$Directories,[string]$Side,[string]$SelectedCollection='desktop-test') {
    [void](AssertPlain $Root)
    $expected=@{}
    foreach($d in $Directories){
        if(-not$d.$Side){continue}
        $full=AssertChildPath $d.$Side $Root $true
        if($expected.ContainsKey($full)){throw 'Duplicate planned directory'}
        $expected[$full]=[pscustomobject]@{directory=$true;bytes=0}
    }
    foreach($f in $Files){
        if(-not$f.$Side){continue}
        $full=AssertChildPath $f.$Side $Root
        $relative=if($Side-ceq'destination'){DestinationRelative $f.name $SelectedCollection}else{$f.name}
        if([IO.Path]::IsPathRooted($relative)-or$full-ine[IO.Path]::GetFullPath((Join-Path $Root $relative))){throw 'File relative mapping mismatch'}
        if($expected.ContainsKey($full)){throw 'Duplicate planned file'}
        $expected[$full]=[pscustomobject]@{directory=$false;bytes=$f.bytes}
    }
    $stack=[Collections.Generic.Stack[string]]::new();$stack.Push($Root);$seen=@{}
    while($stack.Count){
        $current=$stack.Pop();[void](AssertPlain $current)
        $node=Get-Item -LiteralPath $current -Force
        if(-not$expected.ContainsKey($current)-or$seen.ContainsKey($current)){throw 'Unexpected tree entry'}
        $want=$expected[$current]
        if($node.PSIsContainer-ne$want.directory){throw 'Tree entry type changed'}
        if($node.PSIsContainer){foreach($child in @(Get-ChildItem -LiteralPath $current -Force)){$stack.Push($child.FullName)}}
        elseif($node.Length-ne$want.bytes){throw 'Tree entry size changed'}
        $seen[$current]=$true
    }
    if($seen.Count-ne$expected.Count){throw 'Tree inventory incomplete'}
}
function VerifyArchiveEntry($Record,[IO.Stream]$ZipStream) {
    $ZipStream.Position=0
    $zip=[IO.Compression.ZipArchive]::new($ZipStream,[IO.Compression.ZipArchiveMode]::Read,$true)
    try{
        $entries=@($zip.Entries|Where-Object FullName -ceq $Record.retained_archive.entry)
        if($entries.Count-ne 1-or$entries[0].Length-ne$Record.bytes){throw 'Archive member is missing, ambiguous or changed'}
        $entry=$entries[0]
        if((($entry.ExternalAttributes-shr 16)-band 0xF000)-eq 0xA000-or($entry.ExternalAttributes-band 0x400)-ne 0){throw 'Archive member is a link'}
        $stream=$entry.Open()
        try{if((StreamHash $stream)-cne$Record.sha256){throw 'Archive member content differs'}}finally{$stream.Dispose()}
    }finally{$zip.Dispose()}
}
function AssertArchiveMappings($Files,[string]$Source,[string]$Destination) {
    $copies=@{}
    foreach($f in $Files){
        if($f.action-cne'COPY'){continue}
        if($copies.ContainsKey($f.source)){throw 'Ambiguous keeper source'}
        $copies[$f.source]=$f
    }
    foreach($f in $Files){
        if($f.action-ceq'COPY'){
            if($null-ne$f.retained_archive-or-not$f.destination-or($f.PSObject.Properties['retained_file']-and$null-ne$f.retained_file)){throw 'Invalid retained file mapping'}
            continue
        }
        if($f.action-ceq'FILE_DUPLICATE'){
            if($null-ne$f.destination-or$null-ne$f.retained_archive-or$null-eq$f.retained_file){throw 'Invalid duplicate mapping'}
            [void](AssertChildPath $f.retained_file.path $Destination)
            $keeper=$copies[$f.retained_file.source]
            if($null-eq$keeper-or$keeper.destination-ine$f.retained_file.path-or$keeper.sha256-cne$f.sha256-or$keeper.bytes-ne$f.bytes-or$f.retained_file.sha256-cne$f.sha256-or$f.retained_file.bytes-ne$f.bytes-or[IO.Path]::GetFileName($keeper.source)-ine[IO.Path]::GetFileName($f.source)){throw 'File keeper differs, is absent, or is a duplicate chain'}
            continue
        }
        if($f.action-cne'ARCHIVE_DUPLICATE'-or$null-ne$f.destination-or$null-eq$f.retained_archive){throw 'Unsupported migration action'}
        [void](AssertChildPath $f.source $Source)
        [void](AssertChildPath $f.retained_archive.path $Destination)
        $keeper=$copies[$f.retained_archive.source]
        if($null-eq$keeper-or$keeper.destination-ine$f.retained_archive.path-or$keeper.sha256-cne$f.retained_archive.sha256){throw 'Archive keeper is not exactly one retained file'}
    }
}
function ReferencesCollection([string]$Reference,[string]$Source) {
    return $Reference.Replace('/','\')-match('(?i)'+[regex]::Escape($Source)+'(?=$|[\\/"''\s])')
}
function AssertCollectionMappings($Files,$Directories,[string]$Source,[string]$Destination,[string]$SelectedCollection='desktop-test') {
    foreach($f in $Files){
        [void](AssertChildPath $f.source $Source)
        if([IO.Path]::GetRelativePath($Source,$f.source)-cne$f.name){throw 'Unnormalized relative file mapping'}
        if($f.destination){
            [void](AssertChildPath $f.destination $Destination)
            if($f.destination-ine(Join-Path $Destination (DestinationRelative $f.name $SelectedCollection))){throw 'Copy destination differs from its planned relative path'}
        }
    }
    foreach($d in $Directories){
        [void](AssertChildPath $d.source $Source $true)
        if($d.destination){
            [void](AssertChildPath $d.destination $Destination $true)
            $relative=[IO.Path]::GetRelativePath($Source,$d.source)
            $expected=if($relative-ceq'.'){$Destination}else{Join-Path $Destination (DestinationRelative $relative $SelectedCollection)}
            if($d.destination-ine$expected){throw 'Directory mapping changed'}
        }
    }
}
if($PSVersionTable.PSVersion.Major-lt 7){throw 'Development PC PowerShell 7 required; do not run on the server'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$registry=Join-Path $repo 'verification-files.local.json'
$sourceLeaf=switch($Collection){
    'desktop-test'{'test'}
    'desktop-smartfactory'{'SmartFactory'}
    'desktop-release'{'SmartFactoryLogger_Release'}
    'transfer-0695a0f-r1'{'SmartFactoryLogger_Transfer_0695a0f_20260806'}
    'transfer-0695a0f-r2'{'SmartFactoryLogger_Transfer_0695a0f_20260806_R2'}
    'transfer-0695a0f-r3'{'SmartFactoryLogger_Transfer_0695a0f_20260806_R3'}
}
$kind=switch($Collection){
    'desktop-test'{'DESKTOP_TEST_MIGRATION'}
    'desktop-smartfactory'{'DESKTOP_SMARTFACTORY_MIGRATION'}
    'desktop-release'{'DESKTOP_RELEASE_MIGRATION'}
    'transfer-0695a0f-r1'{'DESKTOP_TRANSFER_0695A0F_R1_MIGRATION'}
    'transfer-0695a0f-r2'{'DESKTOP_TRANSFER_0695A0F_R2_MIGRATION'}
    'transfer-0695a0f-r3'{'DESKTOP_TRANSFER_0695A0F_R3_MIGRATION'}
}
$source=Join-Path ([Environment]::GetFolderPath('UserProfile')) ('Desktop\'+$sourceLeaf)
$parent=Join-Path $repo 'artifacts\server-evidence'
$destination=Join-Path $parent $Collection
[void](AssertPlain $registry);[void](AssertPlain (Join-Path $repo 'artifacts'))
if((Get-FileHash -LiteralPath $registry -Algorithm SHA256).Hash-cne$ExpectedIndexSha256){throw 'Management file hash mismatch'}
$index=Get-Content -LiteralPath $registry -Raw|ConvertFrom-Json
if($index.host-ine[Environment]::MachineName-or$index.workspace-ine$repo){throw 'Wrong host/workspace'}
$matches=@($index.migrations|Where-Object id -ceq $MigrationId)
if($matches.Count-ne 1){throw 'Exactly one migration required'}
$migration=$matches[0]
if($migration.kind-cne$kind-or$migration.source-ine$source-or$migration.destination-ine$destination){throw 'Unapproved migration mapping'}
$maxFiles=if($Collection-ceq'desktop-release'){15000}else{5000}
if(-not$migration.files.Count-or$migration.files.Count-gt$maxFiles){throw 'Unexpected migration size'}
$archiveFiles=@();$fileDuplicates=@();$copyFiles=@($migration.files)
if($Collection-cne'desktop-test'){
    AssertArchiveMappings $migration.files $source $destination
    $archiveFiles=@($migration.files|Where-Object action -ceq 'ARCHIVE_DUPLICATE')
    $copyFiles=@($migration.files|Where-Object action -ceq 'COPY')
    $fileDuplicates=@($migration.files|Where-Object action -ceq 'FILE_DUPLICATE')
    $directories=@($migration.directories)
}else{$directories=@([pscustomobject]@{source=$source;destination=$destination;original_sddl=$null})}
AssertCollectionMappings $migration.files $directories $source $destination $Collection
if(@($copyFiles|Where-Object {$_.destination.Length-gt 259}).Count){throw 'Destination exceeds tested local path budget'}
if($VerifyArchivesOnly){
    if($migration.state-cne'COMPLETE'-or$archiveFiles.Count-eq 0){throw 'Completed archive migration required'}
    $verifyPins=@{}
    try{
        foreach($f in $archiveFiles){
            if(Test-Path -LiteralPath $f.source){throw 'Deleted duplicate reappeared'}
            if(Test-Path -LiteralPath (Join-Path $destination $f.name)){throw 'Duplicate extraction reappeared in archive collection'}
            $zipPath=$f.retained_archive.path;[void](AssertPlain $zipPath)
            if(-not$verifyPins.ContainsKey($zipPath)){$verifyPins[$zipPath]=[IO.File]::Open($zipPath,'Open','Read','Read')}
            if((StreamHash $verifyPins[$zipPath])-cne$f.retained_archive.sha256){throw 'Retained ZIP differs'}
            VerifyArchiveEntry $f $verifyPins[$zipPath]
        }
        Write-Host ('[VERIFIED ARCHIVE MEMBERS] '+$archiveFiles.Count)
    }finally{foreach($pin in $verifyPins.Values){$pin.Dispose()}}
    return
}
if($migration.state-cne'PLANNED'){throw 'Migration already attempted; no automatic retry'}
[void](AssertPlain $source)
if(Test-Path -LiteralPath $destination){throw 'Destination already exists'}
if(Test-Path -LiteralPath $parent){[void](AssertPlain $parent)}
AssertTreeInventory $source $migration.files $directories 'source' $Collection
$sourceAcl=Get-Acl -LiteralPath $source
$sourceSignature=AclSignature $sourceAcl
$sourcePins=@{};$copyPins=@{};$started=$false
function SaveRegistry {
    $index.updated_at=[DateTimeOffset]::Now.ToString('o');[void](AssertPlain $registry)
    if((Get-FileHash -LiteralPath $registry -Algorithm SHA256).Hash-cne$script:registryVersion){throw 'Concurrent registry change; preserve files'}
    $staging=$registry+'.writing';$stream=[IO.File]::Open($staging,'CreateNew','Write','None')
    try{$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($index|ConvertTo-Json -Depth 35 -Compress));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
    [IO.File]::Move($staging,$registry,$true)
    $script:registryVersion=(Get-FileHash -LiteralPath $registry -Algorithm SHA256).Hash
}
$script:registryVersion=$ExpectedIndexSha256
try {
    $readCount=0
    foreach($f in $migration.files){
        [void](AssertPlain $f.source)
        if(@(Get-Item -LiteralPath $f.source -Stream '*'|Where-Object Stream -ne ':$DATA').Count){throw 'Alternate streams require separate preservation review'}
        $pin=[IO.File]::Open($f.source,'Open','Read','Read');$sourcePins[$f.source]=$pin
        if($pin.Length-ne$f.bytes-or(StreamHash $pin)-cne$f.sha256){throw 'Source changed since plan'}
        if($Collection-cne'desktop-test'){
            $original=Get-Item -LiteralPath $f.source -Force
            $f.original_sddl=(Get-Acl -LiteralPath $f.source).Sddl
            $f.creation_time_utc=$original.CreationTimeUtc.ToString('o');$f.last_write_time_utc=$original.LastWriteTimeUtc.ToString('o');$f.attributes=[int]$original.Attributes
        }
        $readCount++
        if($readCount%500-eq 0){Write-Host ('[SOURCE VERIFIED] '+$readCount+'/'+$migration.files.Count)}
    }
    foreach($d in $directories){$d.original_sddl=(Get-Acl -LiteralPath $d.source).Sddl}
    foreach($f in $archiveFiles){VerifyArchiveEntry $f $sourcePins[$f.retained_archive.source]}
    # Inspect registrations without printing command lines or secrets.
    $references=[Collections.Generic.List[string]]::new()
    foreach($p in @(Get-CimInstance Win32_Process)){if($p.ProcessId-ne$PID){$references.Add([string]$p.CommandLine);$references.Add([string]$p.ExecutablePath)}}
    foreach($s in @(Get-CimInstance Win32_Service)){$references.Add([string]$s.PathName)}
    foreach($t in @(Get-ScheduledTask)){foreach($a in $t.Actions){foreach($field in @('Execute','Arguments','WorkingDirectory')){if($a.PSObject.Properties[$field]){$references.Add([string]$a.$field)}}}}
    $shell=New-Object -ComObject WScript.Shell
    try{
        foreach($base in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('StartMenu'),[Environment]::GetFolderPath('CommonStartMenu'))){
            if(-not[IO.Directory]::Exists($base)){continue}
            foreach($lnk in @(Get-ChildItem -LiteralPath $base -Filter '*.lnk' -File -Recurse)){
                $shortcut=$shell.CreateShortcut($lnk.FullName);$references.Add([string]$shortcut.TargetPath);$references.Add([string]$shortcut.Arguments);$references.Add([string]$shortcut.WorkingDirectory)
            }
        }
    }finally{[void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)}
    foreach($reference in $references){if(ReferencesCollection $reference $source){throw 'Source is in use or registered; no files moved'}}
    $required=($copyFiles|Measure-Object bytes -Sum).Sum+512MB
    if([IO.DriveInfo]::new([IO.Path]::GetPathRoot($destination)).AvailableFreeSpace-lt$required){throw 'Insufficient copy capacity'}
    Write-Host ('[VERIFIED] '+$migration.files.Count+' files; copy='+$copyFiles.Count+'; archive duplicates='+$archiveFiles.Count+'; file duplicates='+$fileDuplicates.Count+'; bytes='+($migration.files|Measure-Object bytes -Sum).Sum+'; ACL will not be broadened.')
    if(-not$PSCmdlet.ShouldProcess($source,('Copy and verify all evidence, record mapping, then remove originals; destination='+$destination))){return}
    $migration.source_sddl=$sourceAcl.Sddl;$migration.state='COPYING'
    SaveRegistry;$started=$true
    if(-not(Test-Path -LiteralPath $parent)){[void](New-Item -ItemType Directory -Path $parent)}
    [void](AssertPlain $parent)
    # Freeze each retained directory's original grants before copying private bytes.
    foreach($d in @($directories|Where-Object destination|Sort-Object {$_.destination.Length})){
        [void](AssertChildPath $d.destination $destination $true)
        [void](AssertPlain ([IO.Path]::GetDirectoryName($d.destination)))
        if(Test-Path -LiteralPath $d.destination){throw 'Directory appeared at destination'}
        [void](New-Item -ItemType Directory -Path $d.destination)
        $protectedAcl=Get-Acl -LiteralPath $d.source
        if($protectedAcl.Sddl-cne$d.original_sddl){throw 'Source ACL changed'}
        $before=AclSignature $protectedAcl
        $protectedAcl.SetAccessRuleProtection($true,$true)
        Set-Acl -LiteralPath $d.destination -AclObject $protectedAcl
        [void](AssertPlain $d.destination)
        if((AclSignature (Get-Acl -LiteralPath $d.destination))-cne$before){throw 'Destination grants differ from source'}
    }
    $migration.destination_sddl=(Get-Acl -LiteralPath $destination).Sddl
    foreach($f in $copyFiles){
        $copyPins[$f.destination]=CopyVerifiedFile $f
        $f.state='COPY_VERIFIED';$migration.copy_verified_count++
        if($migration.copy_verified_count%100-eq 0){Write-Host ('[COPY VERIFIED] '+$migration.copy_verified_count+'/'+$copyFiles.Count)}
    }
    foreach($f in $archiveFiles){VerifyArchiveEntry $f $copyPins[$f.retained_archive.path];$f.state='ARCHIVE_VERIFIED'}
    foreach($f in $fileDuplicates){
        $pin=$copyPins[$f.retained_file.path]
        if($null-eq$pin-or$pin.Length-ne$f.bytes-or(StreamHash $pin)-cne$f.sha256){throw 'Retained file content differs'}
        $f.state='DUPLICATE_VERIFIED'
    }
    AssertTreeInventory $source $migration.files $directories 'source' $Collection
    AssertTreeInventory $destination $copyFiles $directories 'destination' $Collection
    if((AclSignature (Get-Acl -LiteralPath $source))-cne$sourceSignature){throw 'Source directory access changed'}
    $migration.state='COPIED_VERIFIED';SaveRegistry
    # Mapping is durable and every destination is pinned read-only before originals are removed.
    $migration.state='REMOVING_SOURCES';SaveRegistry
    foreach($f in $migration.files){
        [void](AssertPlain $f.source)
        if((StreamHash $sourcePins[$f.source])-cne$f.sha256){throw 'Source changed before removal'}
        if($f.destination){
            [void](AssertPlain $f.destination)
            if((StreamHash $copyPins[$f.destination])-cne$f.sha256){throw 'Copy changed before removal'}
        }elseif($f.action-ceq'FILE_DUPLICATE'){
            [void](AssertPlain $f.retained_file.path)
            if((StreamHash $copyPins[$f.retained_file.path])-cne$f.sha256){throw 'Duplicate keeper changed before removal'}
        }else{[void](AssertPlain $f.retained_archive.path);VerifyArchiveEntry $f $copyPins[$f.retained_archive.path]}
        $sourcePins[$f.source].Dispose()
        Remove-Item -LiteralPath $f.source -Force
        $f.state=if($f.destination){'MIGRATED'}elseif($f.action-ceq'FILE_DUPLICATE'){'FILE_DUPLICATE_REMOVED'}else{'ARCHIVE_DUPLICATE_REMOVED'};$migration.source_removed_count++
        if($migration.source_removed_count%500-eq 0){Write-Host ('[SOURCE REMOVED] '+$migration.source_removed_count+'/'+$migration.files.Count)}
    }
    foreach($d in @($directories|Sort-Object {$_.source.Length} -Descending)){
        [void](AssertChildPath $d.source $source $true);[void](AssertPlain $d.source)
        if(@(Get-ChildItem -LiteralPath $d.source -Force).Count){throw 'New files appeared; leave source directory intact'}
        Remove-Item -LiteralPath $d.source -Force
    }
    AssertTreeInventory $destination $copyFiles $directories 'destination' $Collection
    $migration.state='COMPLETE'
    $allDuplicates=@($archiveFiles)+@($fileDuplicates)
    $duplicateBytes=if($allDuplicates.Count){($allDuplicates|Measure-Object bytes -Sum).Sum}else{0}
    $index.history=@($index.history)+[pscustomobject]@{at=[DateTimeOffset]::Now.ToString('o');kind='LOCAL_EVIDENCE_MIGRATION';state='COMPLETE';migration_id=$MigrationId;source=$source;destination=$destination;migrated_files=$copyFiles.Count;migrated_bytes=($copyFiles|Measure-Object bytes -Sum).Sum;deleted_files=$allDuplicates.Count;deleted_bytes=$duplicateBytes;original_contents_edited=$false;remote_server_operations=0}
    SaveRegistry
    [pscustomobject]@{result=($kind+'_COMPLETE');copied_files=$copyFiles.Count;duplicate_files_removed=$allDuplicates.Count;duplicate_bytes=$duplicateBytes;destination=$destination;source_removed=$true;acl_preserved=$true}|ConvertTo-Json
}catch{
    if($started){$migration.state='PARTIAL_STOPPED';$migration.error=$_.Exception.Message;SaveRegistry}
    throw
}finally{
    foreach($pin in $sourcePins.Values){$pin.Dispose()}
    foreach($pin in $copyPins.Values){$pin.Dispose()}
}
