# Fixed, non-default development profiles. Importing this file makes no filesystem changes.
Set-StrictMode -Version Latest
function Get-ChromeTestProfileSpecs([string]$Repo){
    foreach($v in @(
        @('.tmp_chrome_cdp_settings_lazy',1340,127982227,66,22073437),
        @('.tmp_chrome_profile_dashboard_qa_role_a',420,38875766,71,22067409),
        @('.tmp_chrome_profile_dashboard_qa_role_a_2',184,35288341,50,21373680),
        @('.tmp_chrome_profile_dashboard_qa_role_a_cdp',1315,56594689,71,22066977),
        @('.tmp_chrome_profile_dashboard_qa_role_a_cdp_2',1315,56594247,71,22066977),
        @('.tmp_chrome_profile_grafana_lazy_qa',1390,136348598,105,30223500),
        @('.tmp_chrome_profile_grafana_split',1347,130643906,71,24694429),
        @('.tmp_chrome_profile_scene_surface',1503,209899652,71,24421781),
        @('.tmp_chrome_profile_settings_lazy',1313,100686608,66,22073437)
    )){[pscustomobject]@{root=(Join-Path $Repo $v[0]);files=[int]$v[1];bytes=[long]$v[2];delete_files=[int]$v[3];delete_bytes=[long]$v[4]}}
}
function Get-ChromeCacheUnits{return @('Default\Cache','Default\Code Cache','Default\GPUCache','Default\DawnWebGPUCache','Default\DawnGraphiteCache','ShaderCache','GrShaderCache','GraphiteDawnCache')}
function Get-ChromeCacheUnit([string]$Relative){
    if($Relative-match'[:/]|(^|\\)\.\.?($|\\)|[ .](\\|$)'){throw 'Noncanonical profile member'}
    foreach($unit in (Get-ChromeCacheUnits)){
        if(-not$Relative.StartsWith($unit+'\',[StringComparison]::Ordinal)){continue}
        $leaf=$Relative.Substring($unit.Length+1)
        $valid=switch($unit){
            'Default\Cache'{$leaf-cmatch'^(Cache_Data\\(index|data_[0-3]|f_[0-9a-f]{6})|No_Vary_Search\\(journal\.baj|snapshot\.baf))$'}
            'Default\Code Cache'{$leaf-cmatch'^(js|wasm)\\(index|index-dir\\the-real-index|[0-9a-f]{16}_[01])$'}
            default{$leaf-cmatch'^(index|data_[0-3])$'}
        }
        if(-not$valid){throw 'Unknown member inside cache unit; preserve whole unit'}
        return $unit
    }
    return $null
}
function Assert-ChromeCacheRecords($Audit,[string]$Repo){
    if($Audit.kind-cne'DESKTOP_CHROME_TEST_CACHE_CLEANUP'-or$Audit.state-cnotin@('PREPARED','COMPLETE')-or$Audit.files.Count-ne642-or$Audit.preserved_files.Count-ne9485){throw 'Fixed transaction count/kind differs'}
    foreach($f in $Audit.files){if($f.disposition-cne'DELETE_CACHE'){throw 'Deletion array disposition differs'}}
    foreach($f in $Audit.preserved_files){if($f.disposition-cne'KEEP_PROFILE_STATE'){throw 'Preservation array disposition differs'}}
    $specs=@(Get-ChromeTestProfileSpecs $Repo);$seen=@{};$counts=@{};$bytes=@{};$keptCounts=@{};$keptBytes=@{}
    foreach($s in $specs){$counts[$s.root]=0;$bytes[$s.root]=0L;$keptCounts[$s.root]=0;$keptBytes[$s.root]=0L}
    foreach($f in @($Audit.files)+@($Audit.preserved_files)){
        $profileMatches=@($specs|Where-Object {$f.path.StartsWith($_.root+'\',[StringComparison]::Ordinal)})
        if($profileMatches.Count-ne1-or[IO.Path]::GetFullPath($f.path)-cne$f.path-or$seen.ContainsKey($f.path)-or$f.sha256-cnotmatch'^[A-F0-9]{64}$'-or$f.bytes-lt0){throw 'Unsafe/duplicate/outside record'}
        $seen[$f.path]=$true;$s=$profileMatches[0];$unit=Get-ChromeCacheUnit ($f.path.Substring($s.root.Length+1))
        if($f.disposition-ceq'DELETE_CACHE'){
            if(-not$unit-or$f.unit-cne(Join-Path $s.root $unit)){throw 'Deletion not a fixed cache member'}
            $counts[$s.root]++;$bytes[$s.root]+=[long]$f.bytes
        }elseif($f.disposition-ceq'KEEP_PROFILE_STATE'){
            if($unit){throw 'Partial cache unit not allowed'};$keptCounts[$s.root]++;$keptBytes[$s.root]+=[long]$f.bytes
        }else{throw 'Unknown disposition'}
    }
    foreach($s in $specs){if($counts[$s.root]-ne$s.delete_files-or$bytes[$s.root]-ne$s.delete_bytes-or$keptCounts[$s.root]-ne($s.files-$s.delete_files)-or$keptBytes[$s.root]-ne($s.bytes-$s.delete_bytes)){throw 'Per-profile count/byte boundary differs'}}
}
function Assert-ChromeIndexHeader([IO.Stream]$Stream,[string]$Relative){
    $Stream.Position=0;$b=New-Object byte[] 8;$read=$Stream.Read($b,0,8)
    if($read-ne8){throw 'Short cache index'}
    $prefix=[Convert]::ToHexString($b)
    if($Relative-cmatch'^Default\\Code Cache\\(js|wasm)\\index$'){
        if($prefix-cne'305C72A71B6DFBFC'){throw 'Unexpected simple-cache index magic'}
    }elseif($prefix-cne'C3CA03C100000300'){throw 'Unexpected block-cache index magic/version'}
}
function Get-ChromeTestLiveUse([object[]]$Specs){
    $counts=@{processes=0;unreadable_process_command_lines=0;services=0;tasks=0;shortcuts=0;skipped_links=0};$hits=[Collections.Generic.List[object]]::new()
    function Inspect([string]$Text,[string]$Kind,[string]$Id){foreach($s in $Specs){if($Text.IndexOf([IO.Path]::GetFileName($s.root),[StringComparison]::OrdinalIgnoreCase)-ge0){$hits.Add(@{kind=$Kind;id=$Id;profile=[IO.Path]::GetFileName($s.root)})}}}
    foreach($p in @(Get-CimInstance Win32_Process)){
        if($p.ProcessId-eq$PID){continue};$counts.processes++
        if([string]::IsNullOrWhiteSpace($p.CommandLine)){$counts.unreadable_process_command_lines++;if($p.Name-match'^(chrome|msedge|chromium|electron)\.exe$'){throw 'Unreadable Chromium process; no deletion'}}
        Inspect ([string]$p.CommandLine) 'process' ([string]$p.ProcessId)
    }
    foreach($s in @(Get-CimInstance Win32_Service)){$counts.services++;Inspect ([string]$s.PathName) 'service' $s.Name}
    foreach($t in @(Get-ScheduledTask)){$counts.tasks++;foreach($a in $t.Actions){foreach($f in @('Execute','Arguments','WorkingDirectory')){if($a.PSObject.Properties[$f]){Inspect ([string]$a.$f) 'task' $t.TaskName}}}}
    $shell=New-Object -ComObject WScript.Shell
    try{foreach($base in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('CommonDesktopDirectory'),[Environment]::GetFolderPath('StartMenu'),[Environment]::GetFolderPath('CommonStartMenu'))){
        if(-not[IO.Directory]::Exists($base)){continue};$stack=[Collections.Generic.Stack[string]]::new();$stack.Push($base)
        while($stack.Count){foreach($child in [IO.DirectoryInfo]::new($stack.Pop()).EnumerateFileSystemInfos()){
            if(($child.Attributes-band[IO.FileAttributes]::ReparsePoint)-ne0){$counts.skipped_links++;continue}
            if($child-is[IO.DirectoryInfo]){$stack.Push($child.FullName);continue};if($child.Extension-ine'.lnk'){continue}
            $counts.shortcuts++;$link=$shell.CreateShortcut($child.FullName)
            try{Inspect $link.TargetPath 'shortcut' $child.Name;Inspect $link.Arguments 'shortcut' $child.Name;Inspect $link.WorkingDirectory 'shortcut' $child.Name}finally{[void][Runtime.InteropServices.Marshal]::ReleaseComObject($link)}
        }}
    }}finally{[void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)}
    if($hits.Count){throw ('Profile use detected; sanitized matches='+($hits.ToArray()|ConvertTo-Json -Compress))}
    return @{at=[DateTimeOffset]::UtcNow.ToString('o');counts=$counts;matches=@();coverage='Readable processes, service/task commands and Desktop/Start Menu shortcuts; not every external/relative consumer. All profile files additionally held against writes/deletion.'}
}
function Write-ChromeCacheIndex([System.Text.Json.JsonDocument]$Document,$Audit,[string]$Path,[string]$ExpectedHash,[string]$Repo){
    Assert-ChromeCacheRecords $Audit $Repo
    $prior=@($Document.RootElement.GetProperty('audits').EnumerateArray()|Where-Object {$_.GetProperty('id').GetString()-ceq$Audit.id})
    if(($Audit.state-ceq'PREPARED'-and$prior.Count)-or($Audit.state-ceq'COMPLETE'-and($prior.Count-ne1-or$prior[0].GetProperty('state').GetString()-cne'PREPARED'))){throw 'Invalid transaction transition'}
    $complete=$Audit.state-ceq'COMPLETE';$gone=@{};$keep=@{};$roots=@{}
    foreach($f in $Audit.files){$gone[$f.path]=$true};foreach($f in $Audit.preserved_files){$keep[$f.path]=$true};foreach($s in (Get-ChromeTestProfileSpecs $Repo)){$roots[$s.root]=$s}
    $out=[IO.File]::Open(($Path+'.writing'),'CreateNew','Write','None');$w=[System.Text.Json.Utf8JsonWriter]::new($out);$at=[DateTimeOffset]::UtcNow.ToString('o')
    function Small($Value){$d=[System.Text.Json.JsonDocument]::Parse(($Value|ConvertTo-Json -Depth 60 -Compress));try{$d.RootElement.WriteTo($w)}finally{$d.Dispose()}}
    try{$w.WriteStartObject();foreach($p in $Document.RootElement.EnumerateObject()){$w.WritePropertyName($p.Name);switch($p.Name){
        'updated_at'{$w.WriteStringValue($at)}
        'audits'{$w.WriteStartArray();$found=$false;foreach($a in $p.Value.EnumerateArray()){if($a.GetProperty('id').GetString()-ceq$Audit.id){Small $Audit;$found=$true}else{$a.WriteTo($w)}};if(-not$found){Small $Audit};$w.WriteEndArray()}
        'history'{$w.WriteStartArray();foreach($v in $p.Value.EnumerateArray()){$v.WriteTo($w)};Small @{at=$at;kind=$Audit.kind;audit_id=$Audit.id;state=$Audit.state;deleted_files=$(if($complete){642}else{0});deleted_bytes=$(if($complete){211061627}else{0});deleted_directories=0;existing_acl_writes=0};$w.WriteEndArray()}
        'files'{if(-not$complete){$p.Value.WriteTo($w);break};$removed=0;$preserved=0;$w.WriteStartArray();foreach($f in $p.Value.EnumerateArray()){$name=$f.GetProperty('path').GetString();if($gone.ContainsKey($name)){$removed++;continue};if($keep.ContainsKey($name)){$preserved++;$v=$f.GetRawText()|ConvertFrom-Json -AsHashtable;$v.state='PROTECT_RETAINED_BROWSER_PROFILE';Small $v}else{$f.WriteTo($w)}};if($removed-ne642-or$preserved-ne9485){throw 'Ledger membership delta differs'};$w.WriteEndArray()}
        'roots'{if(-not$complete){$p.Value.WriteTo($w);break};$count=0;$w.WriteStartArray();foreach($r in $p.Value.EnumerateArray()){$name=$r.GetProperty('path').GetString();if($roots.ContainsKey($name)){$count++;$s=$roots[$name];$v=$r.GetRawText()|ConvertFrom-Json;if($v.file_count-ne$s.files-or$v.bytes-ne$s.bytes){throw 'Prior root totals differ'};$v.file_count-=$s.delete_files;$v.bytes-=$s.delete_bytes;Small $v}else{$r.WriteTo($w)}};if($count-ne9){throw 'Nine indexed roots required'};$w.WriteEndArray()}
        'summary'{if(-not$complete){$p.Value.WriteTo($w);break};$v=$p.Value.GetRawText()|ConvertFrom-Json;$v.files-=642;$v.bytes-=211061627;$v.deleted_files+=642;$v.deleted_bytes+=211061627;Small $v}
        'validation'{$w.WriteStartObject();$w.WriteString('state',$(if($complete){'CHROME_CACHE_SCOPED_VERIFIED_GLOBAL_RECHECK_PENDING'}else{'CHROME_CACHE_TRANSACTION_PENDING'}));$w.WritePropertyName('prior_global_validation');$p.Value.WriteTo($w);$w.WriteEndObject()}
        default{$p.Value.WriteTo($w)}
    }};$w.WriteEndObject();$w.Flush();$out.Flush($true)}finally{$w.Dispose();$out.Dispose()}
    $s=[IO.File]::Open($Path,'Open','Read','Read');try{if((Get-DistHash $s)-cne$ExpectedHash){throw 'Concurrent index change; preserve .writing'}}finally{$s.Dispose()}
    [IO.File]::Move(($Path+'.writing'),$Path,$true)
}
