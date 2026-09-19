# Only the seven already classified, development-only Electron profiles.
Set-StrictMode -Version Latest
function Get-TestCacheSpecs([string]$Repo) {
    foreach($r in @(@('isolation','54JQVf'),@('isolation','BlDyJT'),@('isolation','FC51gr'),@('optimization','L6rPQy'),@('optimization','phfxUN'),@('optimization','tSoLDE'),@('optimization','xwjcf4'))){
        $group=Join-Path $Repo ('artifacts\operator-emphasis-'+$r[0]+'-20260910')
        $profile=Join-Path $group ('run-'+$r[1]+'\electron-profile')
        foreach($u in @('Cache','Code Cache','Dictionaries','GPUCache','DawnGraphiteCache','DawnWebGPUCache')){
            if($r[1]-ceq'BlDyJT'-and$u-in@('GPUCache','DawnGraphiteCache','DawnWebGPUCache')){continue}
            $names=switch($u){
                'Cache' {@('Cache_Data\data_0','Cache_Data\data_1','Cache_Data\data_2','Cache_Data\data_3','Cache_Data\f_000001','Cache_Data\index','No_Vary_Search\journal.baj','No_Vary_Search\snapshot.baf')}
                'Code Cache' {@('js\index','js\index-dir\the-real-index','wasm\index','wasm\index-dir\the-real-index')}
                'Dictionaries' {@('ko-3-0.bdic')}
                default {@('data_0','data_1','data_2','data_3','index')}
            }
            $bytes=switch($u){'Cache'{13381488};'Code Cache'{144};'Dictionaries'{11476456};default{557424}}
            [pscustomobject]@{group=$group;profile=$profile;unit=(Join-Path $profile $u);category=$u;names=@($names);count=@($names).Count;bytes=[long]$bytes}
        }
    }
}
function Get-TestCacheRecords($Review,[string]$Repo) {
    if($Review.id-cne'cd1e6296-a5bd-46fa-9f61-94ff47cff16f'-or$Review.kind-cne'LARGE_ARTIFACTS_READONLY_REVIEW_V1'){throw 'Wrong cache classification'}
    $files=@($Review.files|Where-Object {$_.decision-ceq'HOLD_TEST_CACHE_UNIT_AND_LIVE_USE_REVIEW'})
    if($files.Count-ne181){throw 'Exactly 181 classified cache members required'}
    $specs=@(Get-TestCacheSpecs $Repo);$allowed=@{};$counts=@{};$sizes=@{};$seen=@{}
    foreach($s in $specs){$counts[$s.unit]=0;$sizes[$s.unit]=0L;foreach($n in $s.names){$allowed[(Join-Path $s.unit $n)]=$s}}
    foreach($f in $files){
        if(-not$allowed.ContainsKey($f.path)-or$seen.ContainsKey($f.path)-or[IO.Path]::GetFullPath($f.path)-cne$f.path){throw 'Outside/noncanonical/duplicate cache member'}
        $s=$allowed[$f.path]
        if($f.path-cne(Join-Path $s.unit ([IO.Path]::GetRelativePath($s.unit,$f.path)))-or$f.cache_unit-cne$s.category-or$f.bytes-lt0){throw 'Cache category differs'}
        $seen[$f.path]=$true;$counts[$s.unit]++;$sizes[$s.unit]+=[long]$f.bytes
    }
    foreach($s in $specs){if($counts[$s.unit]-ne$s.count-or$sizes[$s.unit]-ne$s.bytes){throw 'Whole-cache-unit count/bytes differs'}}
    return $files
}
function Assert-TestCacheTimestamp($Metadata,[string]$Snapshot) {
    $parts=$Snapshot.Split('|')
    if($parts.Count-ne7-or[long]$parts[0]-ne$Metadata.bytes-or
       (([long]$Metadata.last_write_utc_ticks-621355968000000000L)*100).ToString()-cne$parts[1]-or
       (([long]$Metadata.creation_utc_ticks-621355968000000000L)*100).ToString()-cne$parts[3]){throw 'Cache metadata changed since classification'}
}
function Remove-TestCachePinned($Source,[IO.Stream]$Journal,[Collections.Generic.List[object]]$Confirmed) {
    $r=$Source.record
    Assert-DistMetadata (Get-DistMetadata $r.path) $r.metadata
    if([SflCleanupNativeV1]::Identity($Source.stream.SafeFileHandle,$r.path,$false)-cne$Source.identity-or(Get-DistHash $Source.stream)-cne$r.sha256){throw 'Pinned cache identity/content changed'}
    [SflCleanupNativeV1]::NoAlternateStreams($r.path,$false)
    Write-DistEvent $Journal @{event='DELETE_INTENT';path=$r.path;identity=$Source.identity;sha256=$r.sha256;unit=$r.unit;reason='REGENERABLE_ISOLATED_TEST_CACHE'}
    [SflCleanupNativeV1]::MarkFile($Source.stream);$Source.stream.Dispose()
    $Confirmed.Add($r)
    if([IO.File]::Exists($r.path)){throw 'Deletion pending/replaced; preserve all remaining files'}
    Write-DistEvent $Journal @{event='DELETED';path=$r.path;sha256=$r.sha256;unit=$r.unit}
}

function Get-TestCacheUse {
    $hits=[Collections.Generic.List[object]]::new()
    $counts=@{processes=0;unreadable_process_command_lines=0;services=0;tasks=0;shortcuts=0;skipped_links=0}
    function Inspect([string]$Value,[string]$Kind,[string]$Id){
        if($Value-match'(?i)operator-emphasis-(isolation|optimization)-20260910|run-(54JQVf|BlDyJT|FC51gr|L6rPQy|phfxUN|tSoLDE|xwjcf4)'){$hits.Add(@{kind=$Kind;id=$Id})}
    }
    foreach($item in @(Get-CimInstance Win32_Process)){
        if($item.ProcessId-eq$PID){continue};$counts.processes++
        if([string]::IsNullOrWhiteSpace($item.CommandLine)){$counts.unreadable_process_command_lines++}
        Inspect ([string]$item.CommandLine) 'process' ([string]$item.ProcessId)
        Inspect ([string]$item.ExecutablePath) 'process' ([string]$item.ProcessId)
    }
    foreach($item in @(Get-CimInstance Win32_Service)){$counts.services++;Inspect ([string]$item.PathName) 'service' $item.Name}
    foreach($item in @(Get-ScheduledTask)){
        $counts.tasks++
        foreach($action in $item.Actions){foreach($field in @('Execute','Arguments','WorkingDirectory')){
            if($action.PSObject.Properties[$field]){Inspect ([string]$action.$field) 'task' $item.TaskName}
        }}
    }
    $shell=New-Object -ComObject WScript.Shell
    try {
        foreach($base in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('StartMenu'),[Environment]::GetFolderPath('CommonStartMenu'))){
            if(-not[IO.Directory]::Exists($base)){continue}
            $pending=[Collections.Generic.Stack[string]]::new();$pending.Push($base)
            while($pending.Count){foreach($child in [IO.DirectoryInfo]::new($pending.Pop()).EnumerateFileSystemInfos()){
                if(($child.Attributes-band[IO.FileAttributes]::ReparsePoint)-ne0){$counts.skipped_links++;continue}
                if($child-is[IO.DirectoryInfo]){$pending.Push($child.FullName);continue}
                if($child.Extension-ine'.lnk'){continue}
                $counts.shortcuts++;$s=$shell.CreateShortcut($child.FullName)
                try {Inspect $s.TargetPath 'shortcut' $child.Name;Inspect $s.Arguments 'shortcut' $child.Name;Inspect $s.WorkingDirectory 'shortcut' $child.Name}
                finally {[void][Runtime.InteropServices.Marshal]::ReleaseComObject($s)}
            }}
        }
    }finally{[void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)}
    if($hits.Count){throw ('Active references found; matches='+$hits.Count)}
    return @{at=[DateTimeOffset]::UtcNow.ToString('o');counts=$counts;matches=@();coverage='Readable process, service, task and Desktop/Start Menu shortcut references. Unreadable processes, custom relative launch contexts and global read handles are not fully observable. Cache files and all preserved profile/evidence files additionally deny concurrent writes/deletes.'}
}


function Write-TestCacheIndex([System.Text.Json.JsonDocument]$Document,$Audit,[string]$Path,[string]$ExpectedHash) {
    if($Audit.state-cnotin@('PREPARED','COMPLETE')-or$Audit.kind-cne'DESKTOP_ISOLATED_TEST_CACHE_CLEANUP'-or$Audit.files.Count-ne181){throw 'Invalid transaction'}
    $prior=@($Document.RootElement.GetProperty('audits').EnumerateArray()|Where-Object {$_.GetProperty('id').GetString()-ceq$Audit.id})
    if($Audit.state-ceq'PREPARED'-and$prior.Count){throw 'Transaction already exists'}
    if($Audit.state-ceq'COMPLETE'-and($prior.Count-ne1-or$prior[0].GetProperty('state').GetString()-cne'PREPARED')){throw 'Completion requires one pending transaction'}
    $complete=$Audit.state-ceq'COMPLETE';$gone=@{};$keepers=@{}
    foreach($f in $Audit.files){$gone[$f.path]=$true}
    foreach($f in $Audit.preserved_files){$keepers[$f.path]=$true}
    $out=[IO.File]::Open(($Path+'.writing'),'CreateNew','Write','None')
    $writer=[System.Text.Json.Utf8JsonWriter]::new($out);$at=[DateTimeOffset]::UtcNow.ToString('o')
    function Small($Value){$d=[System.Text.Json.JsonDocument]::Parse(($Value|ConvertTo-Json -Depth 70 -Compress));try{$d.RootElement.WriteTo($writer)}finally{$d.Dispose()}}
    try {
        $writer.WriteStartObject()
        foreach($p in $Document.RootElement.EnumerateObject()){
            $writer.WritePropertyName($p.Name)
            switch($p.Name){
                'updated_at' {$writer.WriteStringValue($at)}
                'audits' {
                    $writer.WriteStartArray();$found=$false
                    foreach($a in $p.Value.EnumerateArray()){if($a.GetProperty('id').GetString()-ceq$Audit.id){Small $Audit;$found=$true}else{$a.WriteTo($writer)}}
                    if(-not$found){Small $Audit};$writer.WriteEndArray()
                }
                'history' {
                    $writer.WriteStartArray();foreach($e in $p.Value.EnumerateArray()){$e.WriteTo($writer)}
                    Small @{at=$at;kind=$Audit.kind;audit_id=$Audit.id;state=$Audit.state;deleted_files=$(if($complete){181}else{0});deleted_bytes=$(if($complete){184040248}else{0});deleted_directories=0;existing_acl_writes=0;remote_server_operations=0}
                    $writer.WriteEndArray()
                }
                'files' {
                    if(-not$complete){$p.Value.WriteTo($writer);break}
                    $writer.WriteStartArray()
                    foreach($f in $p.Value.EnumerateArray()){
                        $name=$f.GetProperty('path').GetString()
                        if($gone.ContainsKey($name)){continue}
                        if($keepers.ContainsKey($name)){$v=$f.GetRawText()|ConvertFrom-Json -AsHashtable;$v.state='PROTECT_ISOLATED_TEST_EVIDENCE';Small $v}else{$f.WriteTo($writer)}
                    };$writer.WriteEndArray()
                }
                'roots' {
                    if(-not$complete){$p.Value.WriteTo($writer);break}
                    $writer.WriteStartArray()
                    foreach($r in $p.Value.EnumerateArray()){
                        if($r.GetProperty('path').GetString()-ceq$Audit.inventory_root){$v=$r.GetRawText()|ConvertFrom-Json;$v.file_count-=181;$v.bytes-=184040248;Small $v}else{$r.WriteTo($writer)}
                    };$writer.WriteEndArray()
                }
                'summary' {
                    if(-not$complete){$p.Value.WriteTo($writer);break}
                    $v=$p.Value.GetRawText()|ConvertFrom-Json;$v.files-=181;$v.bytes-=184040248;$v.deleted_files+=181;$v.deleted_bytes+=184040248;Small $v
                }
                'validation' {Small @{at=$at;state=$(if($complete){'ISOLATED_TEST_CACHE_VERIFIED_GLOBAL_RECHECK_PENDING'}else{'ISOLATED_TEST_CACHE_TRANSACTION_PENDING'});prior_global_validation=($p.Value.GetRawText()|ConvertFrom-Json -Depth 70)}}
                default {$p.Value.WriteTo($writer)}
            }
        }
        $writer.WriteEndObject();$writer.Flush();$out.Flush($true)
    }finally{$writer.Dispose();$out.Dispose()}
    $check=[IO.File]::Open($Path,'Open','Read','Read')
    try{if((Get-DistHash $check)-cne$ExpectedHash){throw 'Concurrent management change; preserve .writing and journal'}}finally{$check.Dispose()}
    [IO.File]::Move(($Path+'.writing'),$Path,$true)
}
