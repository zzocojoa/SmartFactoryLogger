# Fixed development-host cleanup contract; no top-level filesystem changes.
Set-StrictMode -Version Latest
function Read-StageReference([IO.Stream]$Stream) {
    if($Stream.Length-gt5MB){throw 'Reference read exceeds bound'}
    $Stream.Position=0;$memory=[IO.MemoryStream]::new()
    try{$Stream.CopyTo($memory);$bytes=$memory.ToArray()}finally{$memory.Dispose()}
    $skip=0;$page=65001
    if($bytes.Length-ge4-and$bytes[0]-eq255-and$bytes[1]-eq254-and$bytes[2]-eq0-and$bytes[3]-eq0){$skip=4;$page=12000}
    elseif($bytes.Length-ge4-and$bytes[0]-eq0-and$bytes[1]-eq0-and$bytes[2]-eq254-and$bytes[3]-eq255){$skip=4;$page=12001}
    elseif($bytes.Length-ge3-and$bytes[0]-eq239-and$bytes[1]-eq187-and$bytes[2]-eq191){$skip=3}
    elseif($bytes.Length-ge2-and$bytes[0]-eq255-and$bytes[1]-eq254){$skip=2;$page=1200}
    elseif($bytes.Length-ge2-and$bytes[0]-eq254-and$bytes[1]-eq255){$skip=2;$page=1201}
    $encoding=[Text.Encoding]::GetEncoding($page,[Text.EncoderFallback]::ExceptionFallback,[Text.DecoderFallback]::ExceptionFallback)
    try{return @{text=$encoding.GetString($bytes,$skip,$bytes.Length-$skip);encoding=$encoding.WebName}}
    catch [Text.DecoderFallbackException] {
        if($skip){throw 'Invalid BOM-declared reference encoding'}
        [Text.Encoding]::RegisterProvider([Text.CodePagesEncodingProvider]::Instance)
        $legacy=[Text.Encoding]::GetEncoding(949,[Text.EncoderFallback]::ExceptionFallback,[Text.DecoderFallback]::ExceptionFallback)
        return @{text=$legacy.GetString($bytes);encoding='windows-949'}
    }
}
function Get-StageCleanupRecords($Review,[string]$Repo) {
    if($Review.id-cne'dde4f1ce-375f-4be5-84a8-18b47bcf2745'-or$Review.kind-cne'ARTIFACTS_TMP_READONLY_CLASSIFICATION'){throw 'Wrong classification'}
    $files=@($Review.files|Where-Object {$_.decision-ceq'CANDIDATE_EXACT_TEST_EXTRACTION_PENDING_DELETE_REVIEW'})
    if($files.Count-ne64){throw 'Exactly 64 approved files required'}
    $seen=@{};$counts=@{4=0;5=0};$sizes=@{4=0L;5=0L};$bytes=0L;$result=[Collections.Generic.List[object]]::new()
    foreach($f in $files){
        $revision=0;$name=$null
        foreach($n in @(4,5)){
            $base=Join-Path $Repo ('.tmp\v26stage-tests-r'+$n+'\actual-transfer')
            if($f.path.StartsWith($base+'\',[StringComparison]::Ordinal)){$revision=$n;$name=$f.path.Substring($base.Length+1)}
        }
        if(-not$revision-or$name-match'(^|\\)\.\.?($|\\)|[:/]|[ .](\\|$)' -or [IO.Path]::GetFullPath($f.path)-cne$f.path-or$seen.ContainsKey($f.path)){throw 'Noncanonical/duplicate/outside approved source'}
        $keeper=Join-Path $Repo ('artifacts\v1026-server-stage-20260911-r'+($revision-3)+'\transfer-files\'+$name)
        if(-not$f.content_verified_this_review-or$f.retained_copy.path-cne$keeper-or$f.retained_copy.bytes-ne$f.bytes-or$f.retained_copy.sha256-cne$f.sha256-or$f.sha256-cnotmatch'^[0-9A-F]{64}$'-or$f.bytes-lt0){throw 'Keeper revision/content differs'}
        $seen[$f.path]=$true;$counts[$revision]++;$sizes[$revision]+=$f.bytes;$bytes+=$f.bytes
        $result.Add([pscustomobject]@{path=$f.path;bytes=[long]$f.bytes;sha256=$f.sha256;keeper=$keeper;metadata=$null})
    }
    if($counts[4]-ne32-or$counts[5]-ne32-or$sizes[4]-ne165646933-or$sizes[5]-ne165646933-or$bytes-ne331293866){throw 'Approved tree count/bytes differs'}
    return $result.ToArray()
}
function Assert-StageMembership($Before,$After,[string[]]$Removed=@()) {
    $gone=@{};foreach($p in $Removed){$gone[$p]=$true}
    $expected=@($Before.files|Where-Object {-not$gone.ContainsKey($_)})
    if($expected.Count-ne$After.files.Count-or$Before.directories.Count-ne$After.directories.Count){throw 'Boundary membership changed'}
    foreach($p in $expected){if($p-cnotin$After.files){throw 'Outside file changed membership'}}
    foreach($p in $Before.directories){if($p-cnotin$After.directories){throw 'Directory changed membership'}}
}
function Get-StageUse {
    $hits=[Collections.Generic.List[object]]::new()
    $counts=@{processes=0;unreadable_process_command_lines=0;services=0;tasks=0;shortcuts=0;skipped_links=0}
    function Inspect([string]$Value,[string]$Kind,[string]$Id){
        if($Value-match'(?i)v26stage-tests-r[45]'){$hits.Add(@{kind=$Kind;id=$Id})}
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
    return @{at=[DateTimeOffset]::UtcNow.ToString('o');counts=$counts;matches=@();coverage='Readable process, service, task and Desktop/Start Menu shortcut references. Unreadable processes, custom relative launch contexts and global read handles are not fully observable. All source/keeper handles additionally deny concurrent writes/deletes.'}
}
function Write-StageIndex([System.Text.Json.JsonDocument]$Document,$Audit,[string]$Path,[string]$ExpectedHash) {
    $complete=$Audit.state-ceq'COMPLETE';$gone=@{};$keepers=@{}
    foreach($f in $Audit.files){$gone[$f.path]=$true;$keepers[$f.keeper]=$true}
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
                    Small @{at=$at;kind=$Audit.kind;audit_id=$Audit.id;state=$Audit.state;deleted_files=$(if($complete){64}else{0});deleted_bytes=$(if($complete){331293866}else{0});deleted_directories=0;existing_acl_writes=0;remote_server_operations=0}
                    $writer.WriteEndArray()
                }
                'files' {
                    if(-not$complete){$p.Value.WriteTo($writer);break}
                    $writer.WriteStartArray()
                    foreach($f in $p.Value.EnumerateArray()){
                        $name=$f.GetProperty('path').GetString()
                        if($gone.ContainsKey($name)){continue}
                        if($keepers.ContainsKey($name)){$v=$f.GetRawText()|ConvertFrom-Json -AsHashtable;$v.state='PROTECT_STAGE_EXTRACTION_KEEPER';Small $v}else{$f.WriteTo($writer)}
                    };$writer.WriteEndArray()
                }
                'roots' {
                    if(-not$complete){$p.Value.WriteTo($writer);break}
                    $writer.WriteStartArray()
                    foreach($r in $p.Value.EnumerateArray()){
                        if($r.GetProperty('path').GetString()-ceq$Audit.inventory_root){$v=$r.GetRawText()|ConvertFrom-Json;$v.file_count-=64;$v.bytes-=331293866;Small $v}else{$r.WriteTo($writer)}
                    };$writer.WriteEndArray()
                }
                'summary' {
                    if(-not$complete){$p.Value.WriteTo($writer);break}
                    $v=$p.Value.GetRawText()|ConvertFrom-Json;$v.files-=64;$v.bytes-=331293866;$v.deleted_files+=64;$v.deleted_bytes+=331293866;Small $v
                }
                'validation' {Small @{at=$at;state=$(if($complete){'STAGE_EXTRACTION_VERIFIED_GLOBAL_RECHECK_PENDING'}else{'STAGE_EXTRACTION_TRANSACTION_PENDING'});prior_global_validation=($p.Value.GetRawText()|ConvertFrom-Json -Depth 70)}}
                default {$p.Value.WriteTo($writer)}
            }
        }
        $writer.WriteEndObject();$writer.Flush();$out.Flush($true)
    }finally{$writer.Dispose();$out.Dispose()}
    $check=[IO.File]::Open($Path,'Open','Read','Read')
    try{if((Get-DistHash $check)-cne$ExpectedHash){throw 'Concurrent management change; preserve .writing and journal'}}finally{$check.Dispose()}
    [IO.File]::Move(($Path+'.writing'),$Path,$true)
}
