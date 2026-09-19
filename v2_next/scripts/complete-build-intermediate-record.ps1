# One exact receipt-publication recovery. Never delete/rebuild any product or intermediate file.
[CmdletBinding()]
param([switch]$Execute)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not$IsWindows-or$PSVersionTable.PSVersion.Major-lt7-or[Environment]::MachineName-cne'DESKTOP-SS5CURC'){throw 'Fixed development host required'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'));$index=Join-Path $repo 'verification-files.local.json';$staged=$index+'.writing'
$pendingHash='167B866588018B1001E10E92B81063A392E4867BF37A82B0EBF019DB13EFF105'
$stagedHash='A774EE6209BFF01DDAD8B1757A30AE313BC12878155411EEB0E0D1BB627CDF6F'
$journalHash='9A0D2562D12B0E277BCF04CD269533471CDAB90F4B9FC5ECF0AFBF41BB3CCDDF'
$id='7068a342-72f1-4c18-9ce5-071db1310b3f'
. (Join-Path $PSScriptRoot 'dist-migration-core.ps1')
. (Join-Path $PSScriptRoot 'build-intermediate-cleanup-core.ps1')
$native=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'server-path-audit\cleanup-archive-core.ps1'))
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseInput($native,[ref]$tokens,[ref]$errors)
$fn=$ast.Find({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-ceq'Initialize-CleanupNative'},$false)
. ([scriptblock]::Create($fn.Extent.Text));Initialize-CleanupNative
$guards=@{};$pins=[Collections.Generic.List[IDisposable]]::new();$before=$null;$after=$null;$currentStream=$null;$stageStream=$null;$journal=$null
try{
    Add-DistGuard $repo $guards
    $currentStream=[SflCleanupNativeV1]::OpenFile($index,$false)
    $stageStream=[SflCleanupNativeV1]::OpenFile($staged,$true)
    if((Get-DistHash $currentStream)-cne$pendingHash-or(Get-DistHash $stageStream)-cne$stagedHash){throw 'Exact pending/staged pins differ'}
    $currentStream.Position=0;$before=[System.Text.Json.JsonDocument]::Parse($currentStream)
    $stageStream.Position=0;$after=[System.Text.Json.JsonDocument]::Parse($stageStream)
    $raw=@($after.RootElement.GetProperty('audits').EnumerateArray()|Where-Object {$_.GetProperty('id').GetString()-ceq$id})
    $prior=@($before.RootElement.GetProperty('audits').EnumerateArray()|Where-Object {$_.GetProperty('id').GetString()-ceq$id})
    if($raw.Count-ne1-or$prior.Count-ne1-or$prior[0].GetProperty('state').GetString()-cne'PREPARED'){throw 'Exact pending audit required'}
    $audit=$raw[0].GetRawText()|ConvertFrom-Json -Depth 70 -AsHashtable
    if($audit.state-cne'COMPLETE'-or$audit.deleted_files-ne17-or$audit.deleted_bytes-ne36648177-or$audit.files.Count-ne17-or$audit.preserved_files.Count-ne14-or$audit.retained_output_files.Count-ne1457){throw 'Staged completed scope differs'}
    $allowed=@(Get-BuildIntermediatePaths $repo)
    if(@(Compare-Object $allowed @($audit.files.path)).Count){throw 'Deletion allowlist differs'}
    foreach($p in $allowed){if(Test-Path -LiteralPath $p){throw 'Deleted intermediate exists; no automatic deletion'}}
    # Compare all unmodified large sections directly, preserving numeric values and historical records.
    foreach($p in $before.RootElement.EnumerateObject()){
        if($p.Name-in@('updated_at','audits','history','files','roots','summary','validation')){continue}
        if($p.Value.GetRawText()-cne$after.RootElement.GetProperty($p.Name).GetRawText()){throw 'Unrelated index section differs'}
    }
    $ba=$before.RootElement.GetProperty('audits');$aa=$after.RootElement.GetProperty('audits')
    if($ba.GetArrayLength()-ne21-or$aa.GetArrayLength()-ne21){throw 'Audit count differs'}
    for($i=0;$i-lt20;$i++){if($ba[$i].GetRawText()-cne$aa[$i].GetRawText()){throw 'Historical audit changed'}}
    $bh=$before.RootElement.GetProperty('history');$ah=$after.RootElement.GetProperty('history')
    if($bh.GetArrayLength()-ne38-or$ah.GetArrayLength()-ne39){throw 'History count differs'}
    for($i=0;$i-lt38;$i++){if($bh[$i].GetRawText()-cne$ah[$i].GetRawText()){throw 'Historical event changed'}}
    $summary=$after.RootElement.GetProperty('summary')
    if($summary.GetProperty('files').GetInt64()-ne41330-or$summary.GetProperty('bytes').GetInt64()-ne21858958769-or$summary.GetProperty('deleted_files').GetInt64()-ne165021-or$summary.GetProperty('deleted_bytes').GetInt64()-ne10642762289){throw 'Staged ledger delta differs'}
    Write-Host '[RECONCILE 1/3] Verify 17 absent paths and all preserved build/output/source hashes. No additional payload deletion.'
    foreach($f in @($audit.preserved_files)+@($audit.retained_output_files)+@($audit.source_witnesses)){
        Add-DistGuard ([IO.Path]::GetDirectoryName($f.path)) $guards
        $s=[SflCleanupNativeV1]::OpenFile($f.path,$false);$pins.Add($s);[SflCleanupNativeV1]::NoAlternateStreams($f.path,$false)
        $expected=$f.sha256;$changes=@($audit.source_changes|Where-Object path -CEQ $f.path)
        if($changes.Count){if($changes.Count-ne1){throw 'Source transition ambiguous'};$expected=$changes[0].after}
        if((Get-DistHash $s)-cne$expected){throw 'Preserved hash differs'}
        if($f.ContainsKey('metadata')){Assert-DistMetadata (Get-DistMetadata $f.path) $f.metadata}
    }
    $t=Get-DistTree $audit.inventory_root
    if(@(Compare-Object @($audit.preserved_files.path) $t.files).Count){throw 'Preserved build membership differs'}
    foreach($base in @('backend\dist\SmartFactoryBackend','dist\spot-temperature-v25-qa')){
        $root=Join-Path $repo $base;$t=Get-DistTree $root;$expected=@($audit.retained_output_files|Where-Object {$_.path.StartsWith($root+'\',[StringComparison]::Ordinal)}|ForEach-Object path)
        if(@(Compare-Object $expected $t.files).Count){throw 'Output membership differs'}
    }
    foreach($d in $audit.directory_acls){if((Get-Acl -LiteralPath $d.path).Sddl-cne$d.sddl){throw 'Existing ACL changed'}}
    $journalPath=Join-Path $repo ('artifacts\build-intermediate-cleanup-'+$id+'.jsonl')
    if($audit.journal-cne$journalPath){throw 'Journal path differs'}
    $journal=[IO.File]::Open($journalPath,'Open','ReadWrite','Read')
    if((Get-DistHash $journal)-cne$journalHash){throw 'Journal hash differs'}
    $journal.Position=0;$r=[IO.StreamReader]::new($journal,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
    try{$lines=$r.ReadToEnd().TrimEnd().Split("`n")}finally{$r.Dispose()}
    $events=@($lines|ForEach-Object {$_|ConvertFrom-Json})
    if($events.Count-ne37-or$events[0].event-cne'PLAN'-or$events[35].event-cne'COMPLETE'-or$events[36].event-cne'HOLD'){throw 'Exact event history differs'}
    $deleted=@($events|Where-Object event -CEQ 'DELETED')
    if($deleted.Count-ne17-or@(Compare-Object @($deleted.path) $allowed).Count){throw 'Deletion receipt membership differs'}
    for($i=0;$i-lt17;$i++){if($events[1+2*$i].event-cne'DELETE_INTENT'-or$events[1+2*$i].path-cne$events[2+2*$i].path){throw 'Intent/deleted sequence differs'}}
    $toolRepairs=@();foreach($name in @('remove-build-intermediates.ps1','build-intermediate-cleanup.test.ps1')){
        $p=Join-Path $PSScriptRoot $name;$old=@($audit.tooling|Where-Object path -CEQ $p)
        if($old.Count-ne1){throw 'Original tooling record missing'}
        $s=[SflCleanupNativeV1]::OpenFile($p,$false);$pins.Add($s)
        $toolRepairs+=@{path=$p;before=$old[0].sha256;after=(Get-DistHash $s);reason='Correct journal_path schema and distinguish publication phase; add regression checks'}
    }
    if(-not$Execute){Write-Host '[PASS] Exact reconciliation preflight; no index/journal writes and no additional deletion.';return}
    Write-Host '[RECONCILE 2/3] Append recovery evidence and correct only the new audit journal reference.'
    $reconciliation=@{at=[DateTimeOffset]::UtcNow.ToString('o');prior_pending_index_sha256=$pendingHash;prior_staged_index_sha256=$stagedHash;prior_journal_sha256=$journalHash;additional_payload_deletions=0;verified_absent=17;verified_preserved_build=14;verified_outputs=1457;publication_failure='Windows access denied during final overwrite rename; original locker not established. Fresh DELETE-access probes subsequently succeeded without ACL changes.';tool_repairs=$toolRepairs}
    $journal.Position=$journal.Length;Write-DistEvent $journal @{event='PUBLICATION_RECONCILIATION_VERIFIED';evidence=$reconciliation}
    $audit.journal_path=$journalPath;$audit.journal_sha256=Get-DistHash $journal;$audit.publication_reconciliation=$reconciliation
    $destination=$index+'.reconciled';$out=[IO.File]::Open($destination,'CreateNew','Write','None');$writer=[System.Text.Json.Utf8JsonWriter]::new($out)
    try{
        $writer.WriteStartObject()
        foreach($p in $after.RootElement.EnumerateObject()){
            $writer.WritePropertyName($p.Name)
            if($p.Name-ceq'audits'){
                $writer.WriteStartArray();foreach($a in $p.Value.EnumerateArray()){
                    if($a.GetProperty('id').GetString()-ceq$id){$small=[System.Text.Json.JsonDocument]::Parse(($audit|ConvertTo-Json -Depth 70 -Compress));try{$small.RootElement.WriteTo($writer)}finally{$small.Dispose()}}else{$a.WriteTo($writer)}
                };$writer.WriteEndArray()
            }else{$p.Value.WriteTo($writer)}
        };$writer.WriteEndObject();$writer.Flush();$out.Flush($true)
    }finally{$writer.Dispose();$out.Dispose()}
    if((Get-DistHash $currentStream)-cne$pendingHash-or(Get-DistHash $stageStream)-cne$stagedHash){throw 'Concurrent pending/staged change'}
    $currentStream.Dispose();$currentStream=$null
    Write-Host '[RECONCILE 3/3] Publish verified completion once; consume only its superseded staging file.'
    [IO.File]::Move($destination,$index,$true)
    $check=[IO.File]::Open($index,'Open','Read','Read');try{$finalHash=Get-DistHash $check}finally{$check.Dispose()}
    # This is the script-created uncommitted completion copy, not another managed cleanup candidate.
    [SflCleanupNativeV1]::MarkFile($stageStream);$stageStream.Dispose();$stageStream=$null
    [ordered]@{state='COMPLETE';audit_id=$id;deleted_payload_files=17;deleted_payload_bytes=36648177;additional_payload_deletions=0;preserved_build_files=14;retained_output_files=1457;index_sha256=$finalHash;journal_sha256=$audit.journal_sha256;superseded_staging_copy_consumed=$true}|ConvertTo-Json -Compress
}finally{
    if($null-ne$currentStream){$currentStream.Dispose()};if($null-ne$stageStream){$stageStream.Dispose()};if($null-ne$journal){$journal.Dispose()}
    if($null-ne$before){$before.Dispose()};if($null-ne$after){$after.Dispose()};foreach($s in $pins){$s.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}
}
