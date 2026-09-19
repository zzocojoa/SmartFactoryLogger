# Exact six-tree development cleanup; import existing read-only/native primitives separately.
Set-StrictMode -Version Latest
function Get-AttestationSpecs([string]$Repo) {
    $rows=@(
        @(1,'verify_extract_attempt2','package_attempt2',12,4963177),
        @(2,'verify_extract','package',18,9881026),
        @(3,'verify_extract','package',24,19655538),
        @(4,'verify_extract','package',30,39123763),
        @(5,'verify_extract','package',36,77984184),
        @(5,'expand_archive_verify','package',36,77984184)
    )
    foreach($r in $rows){
        $base=Join-Path $Repo ('.tmp\internal_extended_running_state_attestation_r'+$r[0])
        [pscustomobject]@{base=$base;source=(Join-Path $base $r[1]);keeper=(Join-Path $base $r[2]);count=[int]$r[3];bytes=[long]$r[4]}
    }
}
function Get-AttestationCleanupRecords($Review,[string]$Repo) {
    if($Review.id-cne'cd1e6296-a5bd-46fa-9f61-94ff47cff16f'-or$Review.kind-cne'LARGE_ARTIFACTS_READONLY_REVIEW_V1'){throw 'Wrong classification'}
    $files=@($Review.files|Where-Object {$_.decision-ceq'CANDIDATE_EXACT_VERIFICATION_EXTRACTION'})
    if($files.Count-ne156){throw 'Exactly 156 approved files required'}
    $specs=@(Get-AttestationSpecs $Repo);$seen=@{};$keepers=@{};$counts=@{};$sizes=@{};$result=[Collections.Generic.List[object]]::new()
    foreach($s in $specs){$counts[$s.source]=0;$sizes[$s.source]=0L}
    foreach($f in $files){
        $matches=@($specs|Where-Object {$f.path.StartsWith($_.source+'\',[StringComparison]::Ordinal)})
        if($matches.Count-ne1-or$seen.ContainsKey($f.path)-or[IO.Path]::GetFullPath($f.path)-cne$f.path){throw 'Outside/noncanonical/duplicate source'}
        $s=$matches[0];$name=$f.path.Substring($s.source.Length+1)
        if($name-match'(^|\\)\.\.?($|\\)|[:/]|[ .](\\|$)'){throw 'Unsafe relative source'}
        $keeper=Join-Path $s.keeper $name
        if(-not$f.content_verified_this_review-or$f.retained_copy.path-cne$keeper-or$f.retained_copy.bytes-ne$f.bytes-or$f.retained_copy.sha256-cne$f.sha256-or$f.sha256-cnotmatch'^[0-9A-F]{64}$'-or$f.bytes-lt0){throw 'Keeper revision/content differs'}
        if($keepers.ContainsKey($keeper)-and($keepers[$keeper].sha256-cne$f.sha256-or$keepers[$keeper].bytes-ne$f.bytes)){throw 'Shared keeper content differs'}
        $seen[$f.path]=$true;$keepers[$keeper]=$f;$counts[$s.source]++;$sizes[$s.source]+=$f.bytes
        $result.Add([pscustomobject]@{path=$f.path;bytes=[long]$f.bytes;sha256=$f.sha256;keeper=$keeper;metadata=$null})
    }
    foreach($s in $specs){if($counts[$s.source]-ne$s.count-or$sizes[$s.source]-ne$s.bytes){throw 'Approved tree count/bytes differs'}}
    if($keepers.Count-ne120){throw 'Exactly 120 distinct retained files required'}
    return $result.ToArray()
}

function Get-AttestationUse {
    $hits=[Collections.Generic.List[object]]::new()
    $counts=@{processes=0;unreadable_process_command_lines=0;services=0;tasks=0;shortcuts=0;skipped_links=0}
    function Inspect([string]$Value,[string]$Kind,[string]$Id){
        if($Value-match'(?i)internal_extended_running_state_attestation_r[1-5]'){$hits.Add(@{kind=$Kind;id=$Id})}
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

function Write-AttestationIndex([System.Text.Json.JsonDocument]$Document,$Audit,[string]$Path,[string]$ExpectedHash) {
    if($Audit.state-cnotin@('PREPARED','COMPLETE')-or$Audit.kind-cne'DESKTOP_ATTESTATION_EXTRACTION_CLEANUP'-or$Audit.files.Count-ne156){throw 'Invalid transaction'}
    $prior=@($Document.RootElement.GetProperty('audits').EnumerateArray()|Where-Object {$_.GetProperty('id').GetString()-ceq$Audit.id})
    if($Audit.state-ceq'PREPARED'-and$prior.Count){throw 'Transaction already exists'}
    if($Audit.state-ceq'COMPLETE'-and($prior.Count-ne1-or$prior[0].GetProperty('state').GetString()-cne'PREPARED')){throw 'Completion requires one pending transaction'}
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
                    Small @{at=$at;kind=$Audit.kind;audit_id=$Audit.id;state=$Audit.state;deleted_files=$(if($complete){156}else{0});deleted_bytes=$(if($complete){229591872}else{0});deleted_directories=0;existing_acl_writes=0;remote_server_operations=0}
                    $writer.WriteEndArray()
                }
                'files' {
                    if(-not$complete){$p.Value.WriteTo($writer);break}
                    $writer.WriteStartArray()
                    foreach($f in $p.Value.EnumerateArray()){
                        $name=$f.GetProperty('path').GetString()
                        if($gone.ContainsKey($name)){continue}
                        if($keepers.ContainsKey($name)){$v=$f.GetRawText()|ConvertFrom-Json -AsHashtable;$v.state='PROTECT_ATTESTATION_EXTRACTION_KEEPER';Small $v}else{$f.WriteTo($writer)}
                    };$writer.WriteEndArray()
                }
                'roots' {
                    if(-not$complete){$p.Value.WriteTo($writer);break}
                    $writer.WriteStartArray()
                    foreach($r in $p.Value.EnumerateArray()){
                        if($r.GetProperty('path').GetString()-ceq$Audit.inventory_root){$v=$r.GetRawText()|ConvertFrom-Json;$v.file_count-=156;$v.bytes-=229591872;Small $v}else{$r.WriteTo($writer)}
                    };$writer.WriteEndArray()
                }
                'summary' {
                    if(-not$complete){$p.Value.WriteTo($writer);break}
                    $v=$p.Value.GetRawText()|ConvertFrom-Json;$v.files-=156;$v.bytes-=229591872;$v.deleted_files+=156;$v.deleted_bytes+=229591872;Small $v
                }
                'validation' {Small @{at=$at;state=$(if($complete){'ATTESTATION_EXTRACTION_VERIFIED_GLOBAL_RECHECK_PENDING'}else{'ATTESTATION_EXTRACTION_TRANSACTION_PENDING'});prior_global_validation=($p.Value.GetRawText()|ConvertFrom-Json -Depth 70)}}
                default {$p.Value.WriteTo($writer)}
            }
        }
        $writer.WriteEndObject();$writer.Flush();$out.Flush($true)
    }finally{$writer.Dispose();$out.Dispose()}
    $check=[IO.File]::Open($Path,'Open','Read','Read')
    try{if((Get-DistHash $check)-cne$ExpectedHash){throw 'Concurrent management change; preserve .writing and journal'}}finally{$check.Dispose()}
    [IO.File]::Move(($Path+'.writing'),$Path,$true)
}

