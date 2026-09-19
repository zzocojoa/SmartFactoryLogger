# Fixed 17-file development cleanup; no top-level actions.
Set-StrictMode -Version Latest
function Get-BuildIntermediatePaths([string]$Repo) {
    foreach($unit in @('SmartFactoryBackend','spot-temperature-v25-qa\work\validate_csv_v2_shadow')){
        $names=@('PYZ-00.pyz','base_library.zip','localpycs\struct.pyc','localpycs\pyimod04_pywin32.pyc','localpycs\pyimod03_ctypes.pyc','localpycs\pyimod02_importers.pyc','localpycs\pyimod01_archive.pyc')
        if($unit-ceq'SmartFactoryBackend'){$names+=@('SmartFactoryBackend.exe','SmartFactoryBackend.pkg')}else{$names+='validate_csv_v2_shadow.pkg'}
        foreach($name in $names){Join-Path (Join-Path $Repo ('backend\build\'+$unit)) $name}
    }
}
function Get-BuildIntermediateRecords($Review,[string]$Repo) {
    if($Review.id-cne'5db89818-a464-4c8b-a534-0b5ada299072'-or$Review.state-cne'REVIEW_COMPLETE_AWAITING_EXACT_DELETE_APPROVAL'){throw 'Exact approved review required'}
    $allowed=@(Get-BuildIntermediatePaths $Repo);$seen=@{};$bytes=0L
    $files=@($Review.records|Where-Object decision -CEQ 'DELETE_CANDIDATE_NOT_AUTHORIZED')
    foreach($f in $files){
        if($f.path-cnotin$allowed-or[IO.Path]::GetFullPath($f.path)-cne$f.path-or$seen.ContainsKey($f.path)-or$f.sha256-cnotmatch'^[A-F0-9]{64}$'-or$f.bytes-lt0){throw 'Unapproved/duplicate intermediate'}
        $seen[$f.path]=$true;$bytes+=[long]$f.bytes
    }
    if($files.Count-ne17-or$seen.Count-ne17-or$bytes-ne36648177){throw 'Approved count/bytes differs'}
    return $files
}
function Get-BuildLiveUse([string]$ReaderText) {
    # Reuse the reviewed read-only registration block, without opening its exclusive file handles twice.
    $startMarker='    $counts=@{processes=';$endMarker='    foreach($r in $records)'
    $start=$ReaderText.IndexOf($startMarker,[StringComparison]::Ordinal)
    $end=$ReaderText.IndexOf($endMarker,[StringComparison]::Ordinal)
    if($start-lt0-or$end-le$start-or$ReaderText.LastIndexOf($startMarker,[StringComparison]::Ordinal)-ne$start){throw 'Reviewed registration block differs'}
    $block=$ReaderText.Substring($start,$end-$start)+"`n"+'return @{at=[DateTimeOffset]::UtcNow.ToString("o");counts=$counts;matches=$hits.ToArray()}'
    return & ([scriptblock]::Create($block))
}
function Remove-BuildIntermediatePinned($Source,[IO.Stream]$Journal,[Collections.Generic.List[object]]$Confirmed) {
    $r=$Source.record
    Assert-DistMetadata (Get-DistMetadata $r.path) $r.metadata
    if([SflCleanupNativeV1]::Identity($Source.stream.SafeFileHandle,$r.path,$false)-cne$Source.identity-or(Get-DistHash $Source.stream)-cne$r.sha256){throw 'Pinned intermediate identity/content changed'}
    [SflCleanupNativeV1]::NoAlternateStreams($r.path,$false)
    Write-DistEvent $Journal @{event='DELETE_INTENT';path=$r.path;sha256=$r.sha256;identity=$Source.identity}
    [SflCleanupNativeV1]::MarkFile($Source.stream);$Source.stream.Dispose();$Confirmed.Add($r)
    if([IO.File]::Exists($r.path)){throw 'Deleted path remains; preserve pending transaction'}
    Write-DistEvent $Journal @{event='DELETED';path=$r.path;sha256=$r.sha256;bytes=$r.bytes}
}
function Write-BuildCleanupIndex([System.Text.Json.JsonDocument]$Document,$Audit,[string]$Path,[string]$ExpectedHash) {
    if($Audit.kind-cne'DESKTOP_BUILD_INTERMEDIATE_CLEANUP'-or$Audit.state-cnotin@('PREPARED','COMPLETE')-or$Audit.files.Count-ne17-or$Audit.preserved_files.Count-ne14){throw 'Invalid build transaction'}
    $prior=@($Document.RootElement.GetProperty('audits').EnumerateArray()|Where-Object {$_.GetProperty('id').GetString()-ceq$Audit.id})
    if($Audit.state-ceq'PREPARED'-and$prior.Count){throw 'Duplicate preparation'}
    if($Audit.state-ceq'COMPLETE'-and($prior.Count-ne1-or$prior[0].GetProperty('state').GetString()-cne'PREPARED')){throw 'Completion requires PREPARED'}
    $complete=$Audit.state-ceq'COMPLETE';$gone=@{};$keep=@{}
    foreach($f in $Audit.files){if($gone.ContainsKey($f.path)){throw 'Duplicate delete record'};$gone[$f.path]=$true}
    foreach($f in $Audit.preserved_files){if($gone.ContainsKey($f.path)-or$keep.ContainsKey($f.path)){throw 'Overlapping preserved record'};$keep[$f.path]=$true}
    $out=[IO.File]::Open(($Path+'.writing'),'CreateNew','Write','None');$writer=[System.Text.Json.Utf8JsonWriter]::new($out);$at=[DateTimeOffset]::UtcNow.ToString('o')
    function Small($Value){$d=[System.Text.Json.JsonDocument]::Parse(($Value|ConvertTo-Json -Depth 70 -Compress));try{$d.RootElement.WriteTo($writer)}finally{$d.Dispose()}}
    try {
        $writer.WriteStartObject()
        foreach($p in $Document.RootElement.EnumerateObject()){
            $writer.WritePropertyName($p.Name)
            switch($p.Name){
                'updated_at' {$writer.WriteStringValue($at)}
                'audits' {$writer.WriteStartArray();$found=$false;foreach($a in $p.Value.EnumerateArray()){if($a.GetProperty('id').GetString()-ceq$Audit.id){Small $Audit;$found=$true}else{$a.WriteTo($writer)}};if(-not$found){Small $Audit};$writer.WriteEndArray()}
                'history' {$writer.WriteStartArray();foreach($e in $p.Value.EnumerateArray()){$e.WriteTo($writer)};Small @{at=$at;kind=$Audit.kind;audit_id=$Audit.id;state=$Audit.state;deleted_files=$(if($complete){17}else{0});deleted_bytes=$(if($complete){36648177}else{0});deleted_directories=0;existing_acl_writes=0;remote_server_operations=0};$writer.WriteEndArray()}
                'files' {
                    if(-not$complete){$p.Value.WriteTo($writer);break}
                    $writer.WriteStartArray();$count=0
                    foreach($f in $p.Value.EnumerateArray()){$name=$f.GetProperty('path').GetString();if($gone.ContainsKey($name)){$count++;continue};if($keep.ContainsKey($name)){$v=$f.GetRawText()|ConvertFrom-Json -AsHashtable;$v.state='PROTECT_BUILD_DIAGNOSTIC_EVIDENCE';Small $v}else{$f.WriteTo($writer)}}
                    if($count-ne17){throw 'Exactly 17 indexed removals required'};$writer.WriteEndArray()
                }
                'roots' {
                    if(-not$complete){$p.Value.WriteTo($writer);break}
                    $writer.WriteStartArray();$count=0
                    foreach($r in $p.Value.EnumerateArray()){if($r.GetProperty('path').GetString()-ceq$Audit.inventory_root){$count++;$v=$r.GetRawText()|ConvertFrom-Json;if($v.file_count-ne31-or$v.bytes-ne39762146){throw 'Prior build root totals differ'};$v.file_count-=17;$v.bytes-=36648177;Small $v}else{$r.WriteTo($writer)}}
                    if($count-ne1){throw 'Exactly one build root required'};$writer.WriteEndArray()
                }
                'summary' {if(-not$complete){$p.Value.WriteTo($writer);break};$v=$p.Value.GetRawText()|ConvertFrom-Json;$v.files-=17;$v.bytes-=36648177;$v.deleted_files+=17;$v.deleted_bytes+=36648177;Small $v}
                'validation' {Small @{at=$at;state=$(if($complete){'BUILD_INTERMEDIATE_CLEANUP_VERIFIED_GLOBAL_RECHECK_PENDING'}else{'BUILD_INTERMEDIATE_TRANSACTION_PENDING'});prior_global_validation=($p.Value.GetRawText()|ConvertFrom-Json -Depth 70)}}
                default {$p.Value.WriteTo($writer)}
            }
        }
        $writer.WriteEndObject();$writer.Flush();$out.Flush($true)
    }finally{$writer.Dispose();$out.Dispose()}
    $check=[IO.File]::Open($Path,'Open','Read','Read');try{if((Get-DistHash $check)-cne$ExpectedHash){throw 'Concurrent management change; preserve .writing'}}finally{$check.Dispose()}
    [IO.File]::Move(($Path+'.writing'),$Path,$true)
}
