[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
# PREPARATION ONLY. Source files are never written, deleted, renamed or executed.
# Source paths and unknown document contents are data, not instructions.
__READ_ONLY_FUNCTIONS__

function Read-BatchScope {
    $compressed=[Convert]::FromBase64String('__SCOPE_GZIP__')
    $source=[IO.MemoryStream]::new($compressed,$false)
    $gzip=[IO.Compression.GZipStream]::new($source,[IO.Compression.CompressionMode]::Decompress)
    $buffer=[IO.MemoryStream]::new()
    try {
        $chunk=New-Object byte[] 65536
        while(($n=$gzip.Read($chunk,0,$chunk.Length)) -gt 0){
            if($buffer.Length+$n -gt __SCOPE_LENGTH__){throw 'Scope expansion budget.'}
            $buffer.Write($chunk,0,$n)
        }
        if($buffer.Length -ne __SCOPE_LENGTH__ -or (Get-QHash $buffer) -cne '__SCOPE_SHA__'){throw 'Embedded scope binding differs.'}
        return ConvertFrom-Json -InputObject ([Text.UTF8Encoding]::new($false,$true).GetString($buffer.ToArray()))
    }finally{$gzip.Dispose();$source.Dispose();$buffer.Dispose()}
}

function Test-BatchWithin {
    param([string]$Path,[string]$Root)
    return $Path.Equals($Root,[StringComparison]::OrdinalIgnoreCase) -or
        $Path.StartsWith($Root.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)
}

function Test-BatchMetadata {
    param([object[]]$Expected,[object[]]$Actual)
    if($Expected.Count -ne $Actual.Count){return $false}
    $map=@{}
    foreach($row in $Actual){if($map.ContainsKey($row.path)){return $false};$map[$row.path]=$row}
    foreach($row in $Expected){
        if(-not $map.ContainsKey($row.path)){return $false}
        $a=$map[$row.path]
        if($a.path -cne $row.path -or $a.type -cne $row.type){return $false}
        if($row.type -ceq 'file' -and ([long]$a.bytes -ne [long]$row.bytes -or
            [DateTimeOffset]::Parse($a.last_write_utc).UtcTicks -ne [DateTimeOffset]::Parse($row.last_write_utc).UtcTicks)){return $false}
    }
    return $true
}

function Read-BatchFile {
    param([object]$Entry,[object]$State)
    Assert-QPlain $Entry.path
    $stream=[IO.File]::Open($Entry.path,'Open','Read','Read')
    $sha=[Security.Cryptography.SHA256]::Create()
    try {
        if($stream.Length -ne [long]$Entry.bytes){throw 'Source size changed.'}
        $buffer=New-Object byte[] 1048576
        $readBytes=0L
        while(($n=$stream.Read($buffer,0,$buffer.Length)) -gt 0){
            if($State.clock.Elapsed.TotalSeconds -gt 1200){throw 'Hash time budget.'}
            $readBytes+=$n;$State.bytes_read+=$n
            if($readBytes -gt [long]$Entry.bytes -or $State.bytes_read -gt 6GB){throw 'Hash byte budget.'}
            $null=$sha.TransformBlock($buffer,0,$n,$buffer,0)
            if($State.clock.Elapsed.TotalSeconds-$State.last_progress -gt 5){
                Write-Host ('[HASH] files='+$State.files_done+'/'+$State.total_files+' read_GiB='+[Math]::Round($State.bytes_read/1GB,2)+' elapsed_s='+[int]$State.clock.Elapsed.TotalSeconds)
                $State.last_progress=$State.clock.Elapsed.TotalSeconds
            }
        }
        $null=$sha.TransformFinalBlock($buffer,0,0)
        if($readBytes -ne [long]$Entry.bytes){throw 'Source truncated.'}
        $info=[IO.FileInfo]::new($Entry.path)
        Assert-QPlain $Entry.path
        if($info.Length -ne [long]$Entry.bytes -or $info.LastWriteTimeUtc.Ticks -ne [DateTimeOffset]::Parse($Entry.last_write_utc).UtcTicks){throw 'Source metadata changed.'}
        return [pscustomobject]@{group=$Entry.group;path=$Entry.path;length=$readBytes;
            sha256=[BitConverter]::ToString($sha.Hash).Replace('-','');last_write_utc=$Entry.last_write_utc}
    }finally{$sha.Dispose();$stream.Dispose()}
}

function Get-BatchZipLayout {
    param([IO.Compression.ZipArchive]$Zip)
    if($Zip.Entries.Count -gt 10000){throw 'Archive entries budget.'}
    $files=@{};$seen=@{}
    foreach($entry in $Zip.Entries){
        $name=$entry.FullName.Replace('/','\');$dir=$name.EndsWith('\')
        if($dir){$name=$name.Substring(0,$name.Length-1)}
        Assert-QRelative $name
        $kind=($entry.ExternalAttributes -shr 16) -band 0xF000
        if($seen.ContainsKey($name) -or $name.Length -gt 259 -or
            $kind -notin @(0,0x8000,0x4000) -or ($entry.ExternalAttributes -band 0x400) -ne 0 -or
            ($kind -eq 0x4000 -and -not $dir) -or ($kind -eq 0x8000 -and $dir) -or
            (($entry.ExternalAttributes -band 0x10) -ne 0 -and -not $dir)){throw 'Ambiguous archive path/type.'}
        $seen[$name]=$true
        if($dir){if($entry.Length -ne 0){throw 'Nonempty archive directory.'};continue}
        if($entry.Length -gt 1GB){throw 'Archive entry too large.'}
        $files[$name]=[pscustomobject]@{name=$name;entry=$entry.FullName;length=[long]$entry.Length;source=$entry}
    }
    foreach($name in @($seen.Keys)){
        $parent=[IO.Path]::GetDirectoryName($name)
        while(-not [string]::IsNullOrEmpty($parent)){
            if($files.ContainsKey($parent)){throw 'Archive file/directory conflict.'}
            $parent=[IO.Path]::GetDirectoryName($parent)
        }
    }
    return ,$files
}

function Read-BatchArchiveHash {
    param([IO.Stream]$Stream,[long]$Length,[object]$State)
    if($Stream.Length -ne $Length){throw 'Archive length changed.'}
    $Stream.Position=0;$sha=[Security.Cryptography.SHA256]::Create();$read=0L
    try {
        $buffer=New-Object byte[] 1048576
        while(($n=$Stream.Read($buffer,0,$buffer.Length)) -gt 0){
            $read+=$n;$State.rehashed_zip_bytes+=$n
            if($read -gt $Length -or $State.rehashed_zip_bytes -gt 6GB -or $State.clock.Elapsed.TotalSeconds -gt 1500){throw 'Archive rehash budget.'}
            $null=$sha.TransformBlock($buffer,0,$n,$buffer,0)
            if($State.clock.Elapsed.TotalSeconds-$State.last_progress -gt 5){
                Write-Host ('[ZIP REHASH] read_GiB='+[Math]::Round($State.rehashed_zip_bytes/1GB,2)+' elapsed_s='+[int]$State.clock.Elapsed.TotalSeconds)
                $State.last_progress=$State.clock.Elapsed.TotalSeconds
            }
        }
        $null=$sha.TransformFinalBlock($buffer,0,0)
        if($read -ne $Length){throw 'Archive truncated.'}
        return [BitConverter]::ToString($sha.Hash).Replace('-','')
    }finally{$sha.Dispose()}
}

function Find-BatchZipMapping {
    param([object]$Group,[object[]]$Files,[hashtable]$Layout)
    if($Files.Count -eq 0){return}
    $leaf=[IO.Path]::GetFileName($Group.path)
    foreach($prefix in @('',($leaf+'\'))){
        $mapping=[Collections.Generic.List[object]]::new()
        foreach($file in $Files){
            if(-not $file.path.StartsWith($Group.path+'\',[StringComparison]::OrdinalIgnoreCase)){break}
            $relative=$file.path.Substring($Group.path.Length+1);$key=$prefix+$relative
            if(-not $Layout.ContainsKey($key)){break}
            $entry=$Layout[$key]
            if($entry.name -cne $key -or [long]$entry.length -ne [long]$file.length){break}
            $mapping.Add([pscustomobject]@{relative_path=$relative;path=$file.path;length=$file.length;sha256=$file.sha256;zip_entry=$entry.entry})
        }
        if($mapping.Count -eq $Files.Count){return ,$mapping.ToArray()}
    }
}

function Read-BatchZipEntryHash {
    param([object]$Entry,[object]$State)
    $stream=$Entry.Open();$sha=[Security.Cryptography.SHA256]::Create();$read=0L
    try {
        $buffer=New-Object byte[] 65536
        while(($n=$stream.Read($buffer,0,$buffer.Length)) -gt 0){
            $read+=$n;$State.expanded_bytes+=$n
            if($read -gt $Entry.Length -or $State.expanded_bytes -gt 8GB -or $State.clock.Elapsed.TotalSeconds -gt 1500){throw 'ZIP expansion/time budget.'}
            $null=$sha.TransformBlock($buffer,0,$n,$buffer,0)
            if($State.clock.Elapsed.TotalSeconds-$State.last_progress -gt 5){
                Write-Host ('[ZIP HASH] expanded_GiB='+[Math]::Round($State.expanded_bytes/1GB,2)+' elapsed_s='+[int]$State.clock.Elapsed.TotalSeconds)
                $State.last_progress=$State.clock.Elapsed.TotalSeconds
            }
        }
        $null=$sha.TransformFinalBlock($buffer,0,0)
        if($read -ne $Entry.Length){throw 'Truncated ZIP entry.'}
        return [BitConverter]::ToString($sha.Hash).Replace('-','')
    }finally{$sha.Dispose();$stream.Dispose()}
}

function Write-BatchNew {
    param([string]$Path,[byte[]]$Bytes)
    $s=[IO.File]::Open($Path,'CreateNew','Write','None')
    try{$s.Write($Bytes,0,$Bytes.Length);$s.Flush($true)}finally{$s.Dispose()}
}

function Assert-BatchPrivate {
    param([string]$Path)
    Assert-QPlain $Path
    $acl=[IO.Directory]::GetAccessControl($Path)
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if(-not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin @('S-1-5-18','S-1-5-32-544') -or $rules.Count -ne 2){throw 'Existing SFLOps owner/DACL differs; no ACL repair.'}
    $seen=@{}
    foreach($r in $rules){
        $sid=$r.IdentityReference.Value
        if($sid -notin @('S-1-5-18','S-1-5-32-544') -or $seen.ContainsKey($sid) -or
            $r.AccessControlType -ne 'Allow' -or $r.FileSystemRights -ne 'FullControl' -or
            [int]$r.InheritanceFlags -ne 3 -or [int]$r.PropagationFlags -ne 0){throw 'Existing SFLOps rules differ; no ACL repair.'}
        $seen[$sid]=$true
    }
}

$savedBatchPath=$env:PATH;$savedBatchModules=$env:PSModulePath
$output=$null
try {
    $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    if(-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
        $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
        [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native -or
        -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Use native administrator x64 Windows PowerShell 5.1.'}
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
    $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    Add-Type -AssemblyName System.IO.Compression
    $scope=Read-BatchScope
    if($scope.schema -cne 'sfl-batch-prepare-scope-v1' -or $scope.input_sha256 -cne '28E8C42D1395D1240DFDB4413135A3EA40BFA01FD8BF5D4AB7ADDE4EC4A6B1AD' -or
        $scope.groups.Count -ne 366 -or @($scope.entries|Where-Object type -CEQ 'file').Count -ne 959){throw 'Scope contract differs.'}
    foreach($group in $scope.groups){foreach($keep in $scope.protected_paths){if((Test-BatchWithin $group.path $keep) -or (Test-BatchWithin $keep $group.path)){throw 'Protected scope overlap.'}}}
    Assert-BatchPrivate 'C:\ProgramData\SFLOps'
    Assert-BatchPrivate 'C:\ProgramData\SFLOps\inventory'
    $output='C:\ProgramData\SFLOps\inventory\batch-plan-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
    if(Test-Path -LiteralPath $output){throw 'Output collision.'}
    $null=[IO.Directory]::CreateDirectory($output)
    Assert-QPlain $output
    Write-Host ('[OUTPUT] '+$output)
    Write-Host '[1/5] Preparation only: 366 groups / 959 files. No deletion, move, ACL repair, product API, installer or restart.'
    $state=@{clock=[Diagnostics.Stopwatch]::StartNew();last_progress=0;bytes_read=0L;rehashed_zip_bytes=0L;expanded_bytes=0L;files_done=0;total_files=959}
    $issues=[Collections.Generic.List[object]]::new();$hashes=[Collections.Generic.List[object]]::new()
    $groupResults=[Collections.Generic.List[object]]::new();$complete=@{};$byGroup=@{}
    foreach($entry in $scope.entries){if(-not $byGroup.ContainsKey([int]$entry.group)){$byGroup[[int]$entry.group]=[Collections.Generic.List[object]]::new()};$byGroup[[int]$entry.group].Add($entry)}
    Write-Host '[2/5] Compare current candidate metadata and hash their bytes once. Changed or unreadable groups are preserved; continue other groups.'
    foreach($group in $scope.groups){
        $start=$hashes.Count;$status='HASHED_METADATA_MATCH';$id=[int]$group.id
        try {
            if($state.clock.Elapsed.TotalSeconds -gt 1200){throw 'Group time budget.'}
            $expected=@($byGroup[$id].ToArray());$actual=[Collections.Generic.List[object]]::new()
            Assert-QPlain $group.path
            if([IO.Directory]::Exists($group.path)){
                $actual.Add([pscustomobject]@{path=$group.path;type='directory';bytes=$null;last_write_utc=$null})
                $tree=Get-QTree $group.path -MaxDepth 30 -MaxEntries 5000 -Seconds 15
                if(-not $tree.complete){throw 'Candidate tree incomplete.'}
                foreach($row in $tree.rows){$actual.Add([pscustomobject]@{path=$row.path;type=$(if($row.directory){'directory'}else{'file'});bytes=$row.length;last_write_utc=[DateTime]::new($row.write_ticks,[DateTimeKind]::Utc).ToString('o')})}
            }else{
                $f=[IO.FileInfo]::new($group.path)
                $actual.Add([pscustomobject]@{path=$group.path;type='file';bytes=$f.Length;last_write_utc=$f.LastWriteTimeUtc.ToString('o')})
            }
            if(-not (Test-BatchMetadata $expected $actual.ToArray())){throw 'Candidate metadata changed.'}
            foreach($entry in $expected){if($entry.type -ceq 'file'){$hashes.Add((Read-BatchFile $entry $state));$state.files_done++}}
            $complete[$id]=$true
        }catch{
            $status='PRESERVE_CHANGED_UNREADABLE_OR_LIMIT'
            if($hashes.Count -gt $start){$hashes.RemoveRange($start,$hashes.Count-$start)}
            $issues.Add([pscustomobject]@{phase='source';group=$id;path=$group.path;error_type=$_.Exception.GetType().Name;reason='metadata, read or time budget failed; preserve whole group'})
        }
        $groupResults.Add([pscustomobject]@{id=$id;path=$group.path;status=$status;deletion_authorized=$false})
        if(($groupResults.Count%25) -eq 0){Write-Host ('[GROUP] '+$groupResults.Count+'/366 files_hashed='+$hashes.Count+' elapsed_s='+[int]$state.clock.Elapsed.TotalSeconds)}
    }
    Write-Host '[3/5] Compare ZIP entries only when a complete folder has matching relative paths and lengths. No archive extraction.'
    $proofs=[Collections.Generic.List[object]]::new();$zipCoverage=[Collections.Generic.List[object]]::new();$mapped=@{};$filesByGroup=@{}
    foreach($f in $hashes){if(-not $filesByGroup.ContainsKey([int]$f.group)){$filesByGroup[[int]$f.group]=[Collections.Generic.List[object]]::new()};$filesByGroup[[int]$f.group].Add($f)}
    $folders=@($scope.groups|Where-Object {$complete.ContainsKey([int]$_.id) -and $filesByGroup.ContainsKey([int]$_.id) -and @($byGroup[[int]$_.id]|Where-Object type -CEQ 'directory').Count -gt 0})
    foreach($zipFile in @($hashes|Where-Object {$_.path.EndsWith('.zip',[StringComparison]::OrdinalIgnoreCase)})){
        $stream=$null;$zip=$null;$zipStatus='LAYOUT_READ';$pending=[Collections.Generic.List[object]]::new()
        try {
            if($state.clock.Elapsed.TotalSeconds -gt 1500){throw 'Archive time budget.'}
            Assert-QPlain $zipFile.path
            $stream=[IO.File]::Open($zipFile.path,'Open','Read','Read')
            if((Read-BatchArchiveHash $stream $zipFile.length $state) -cne $zipFile.sha256){throw 'ZIP changed since hashing.'}
            $stream.Position=0;$zip=[IO.Compression.ZipArchive]::new($stream,'Read',$true)
            $layout=Get-BatchZipLayout $zip;$entryHashes=@{}
            foreach($group in $folders){
                $id=[int]$group.id
                if($mapped.ContainsKey($id) -or (Test-BatchWithin $zipFile.path $group.path)){continue}
                $mapping=Find-BatchZipMapping $group $filesByGroup[$id].ToArray() $layout
                if($null -eq $mapping){continue}
                $matches=$true
                foreach($m in $mapping){
                    $key=$m.zip_entry.Replace('/','\')
                    if(-not $entryHashes.ContainsKey($key)){$entryHashes[$key]=Read-BatchZipEntryHash $layout[$key].source $state}
                    if($entryHashes[$key] -cne $m.sha256){$matches=$false;break}
                }
                if($matches){$pending.Add([pscustomobject]@{group=$id;path=$group.path;retain_zip=$zipFile.path;retain_zip_group=$zipFile.group;retain_zip_sha256=$zipFile.sha256;files=@($mapping);logical_bytes=[long](($mapping|Measure-Object length -Sum).Sum);deletion_authorized=$false})}
            }
            foreach($p in $pending){$proofs.Add($p);$mapped[[int]$p.group]=$true}
        }catch{
            $zipStatus='PRESERVE_ARCHIVE_UNREADABLE_UNSAFE_OR_LIMIT'
            $issues.Add([pscustomobject]@{phase='archive';group=$zipFile.group;path=$zipFile.path;error_type=$_.Exception.GetType().Name;reason='no proof accepted from this archive'})
        }finally{if($null -ne $zip){$zip.Dispose()};if($null -ne $stream){$stream.Dispose()}}
        $zipCoverage.Add([pscustomobject]@{path=$zipFile.path;status=$zipStatus})
        if(($zipCoverage.Count%20) -eq 0){Write-Host ('[ZIP] checked='+$zipCoverage.Count+' complete_folder_matches='+$proofs.Count)}
    }
    Write-Host '[4/5] Bounded process/service/startup/task, shortcut and retained-text reference leads. No raw command lines or source text are exported.'
    $needles=@($scope.groups|ForEach-Object {$_.path;[IO.Path]::GetFileName($_.path)}|Sort-Object -Unique)
    $systemRefs=Get-QSystemReferences $needles
    $fileRefs=Get-QFileReferences $needles $scope.reference_scopes
    $duplicateSets=@($hashes|Group-Object { [string]$_.length+':'+$_.sha256 }|Where-Object Count -gt 1|ForEach-Object {
        [pscustomobject]@{length=$_.Group[0].length;sha256=$_.Group[0].sha256;paths=@($_.Group.path);deletion_authorized=$false;meaning='same primary-stream bytes only; no retained-copy choice or reference clearance'}
    })
    $keeperGroups=@{};foreach($p in $proofs){$keeperGroups[[int]$p.retain_zip_group]=$true}
    $proposals=@($proofs|ForEach-Object {
        $p=$_;$leaf=[IO.Path]::GetFileName($p.path)
        $hits=@(@($systemRefs.hits)+@($fileRefs.hits)|Where-Object {$_.matched_names -icontains $p.path -or $_.matched_names -icontains $leaf})
        [pscustomobject]@{group=$p.group;path=$p.path;files=$p.files;logical_bytes=$p.logical_bytes;retain_zip=$p.retain_zip;
            retain_zip_sha256=$p.retain_zip_sha256;reference_lead_count=$hits.Count;
            contains_retained_zip_for_another_group=$keeperGroups.ContainsKey([int]$p.group);
            status=$(if($keeperGroups.ContainsKey([int]$p.group)){'HOLD_RETAINED_ZIP_DEPENDENCY'}elseif($hits.Count -gt 0){'HOLD_REFERENCE_LEAD_REVIEW'}else{'CONTENT_MATCH_REQUIRES_FINAL_REVIEW'});deletion_authorized=$false}
    })
    Write-Host '[5/5] Write one combined preparation result and checksum. No deletion authorization or final YES prompt.'
    $result=[pscustomobject][ordered]@{
        schema_version='sfl-cleanup-batch-preparation-v1';result='BATCH_PREPARATION_COMPLETE_NOT_DELETE_AUTHORIZED';recorded_at=[DateTimeOffset]::Now.ToString('o')
        input_inventory_sha256=$scope.input_sha256;scope_sha256='__SCOPE_SHA__';candidate_groups=366;candidate_files=959
        newly_excluded_groups=$scope.new_exclusions;protected_paths=$scope.protected_paths;groups=$groupResults.ToArray()
        files_hashed=$hashes.Count;primary_bytes_read=$state.bytes_read;rehashed_zip_bytes=$state.rehashed_zip_bytes;expanded_zip_bytes=$state.expanded_bytes
        file_hashes=$hashes.ToArray();same_bytes_sets=$duplicateSets;archive_backed_folder_proposals=$proposals;zip_coverage=$zipCoverage.ToArray()
        system_references=$systemRefs;file_references=$fileRefs;issues=$issues.ToArray();elapsed_seconds=[Math]::Round($state.clock.Elapsed.TotalSeconds,1)
        source_writes_performed=$false;deletion_performed=$false;move_performed=$false;acl_repair_performed=$false;app_restart_performed=$false;product_api_queries=$false;deletion_authorized=$false
        limitations=@('Metadata/hashes are non-atomic across files; no proof of current non-use or future immutability.',
            'No alternate-stream, hard-link, allocated-space or hostile ancestor-replacement integrity gate; these results cannot authorize deletion.',
            'ZIP comparison covers mapped primary file bytes, not ACLs, streams or all filesystem metadata. Retained ZIPs must not be deleted with their matching folders.',
            'All reference hits are conservative leads, not active-use findings; relative/dynamic/binary/custom references may be missed. Coverage gaps are reported, not cleared.',
            'Unique or unmapped content remains preserved. No observation or operating approval. Final deletion requires fresh handle-bound checks and exact approved targets.')
    }
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($result|ConvertTo-Json -Depth 18))
    $target=Join-Path $output 'batch-plan.json';Write-BatchNew $target $bytes
    $verify=[IO.File]::Open($target,'Open','Read','Read')
    try{$resultHash=Get-QHash $verify}finally{$verify.Dispose()}
    $memory=[IO.MemoryStream]::new($bytes,$false)
    try{if((Get-QHash $memory) -cne $resultHash){throw 'Result re-read mismatch.'}}finally{$memory.Dispose()}
    Write-BatchNew ($target+'.sha256.txt') ([Text.Encoding]::ASCII.GetBytes($resultHash+"`n"))
    Write-Host ('[RESULT] '+$target);Write-Host ('[SHA256] '+$resultHash)
    Write-Host ('[SUMMARY] hashed_files='+$hashes.Count+' duplicate_byte_sets='+$duplicateSets.Count+' archive_backed_groups='+$proposals.Count+' preserved_issues='+$issues.Count)
    Write-Host '[DONE] Return batch-plan.json and its SHA256 sidecar. PRIVATE metadata. Nothing deleted; no automatic retry.'
}catch{Write-Host ('[HOLD] Preparation stopped. Preserve output: '+$output+'. No cleanup retry, ACL repair or app changes.');throw}
finally{$env:PATH=$savedBatchPath;$env:PSModulePath=$savedBatchModules}
