Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSVersion.Major-lt7){throw 'PowerShell 7 required'}
$count=0
function Check([bool]$Value,[string]$Name){if(-not$Value){throw $Name};$script:count++}
function Reject([scriptblock]$Action,[string]$Name){$caught=$false;try{&$Action}catch{$caught=$true};Check $caught $Name}
foreach($name in @('stage-extraction-cleanup-core.ps1','remove-stage-extraction-duplicates.ps1')){
    $errors=$null;[void][Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$null,[ref]$errors)
    Check ($errors.Count-eq0) ($name+' syntax: '+(@($errors|ForEach-Object {$_.Message})-join'; '))
}
. (Join-Path $PSScriptRoot 'dist-migration-core.ps1')
. (Join-Path $PSScriptRoot 'stage-extraction-cleanup-core.ps1')
[Text.Encoding]::RegisterProvider([Text.CodePagesEncodingProvider]::Instance)
foreach($encoding in @([Text.UTF8Encoding]::new($false,$true),[Text.Encoding]::GetEncoding(949),[Text.Encoding]::Unicode)){
    $text='한글 v26stage-tests-r4';$s=[IO.MemoryStream]::new([byte[]]($encoding.GetPreamble()+$encoding.GetBytes($text)))
    try{Check ((Read-StageReference $s).text-ceq$text) ('Reference encoding '+$encoding.WebName)}finally{$s.Dispose()}
}
$s=[IO.MemoryStream]::new([byte[]]@(239,187,191,255))
try{Reject {Read-StageReference $s} 'Corrupt declared UTF8 fails closed'}finally{$s.Dispose()}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
function Review {
    $rows=@(foreach($n in @(4,5)){foreach($i in 0..31){
        $bytes=if($i-eq0){165646902}else{1}
        [pscustomobject]@{path=(Join-Path $repo ('.tmp\v26stage-tests-r'+$n+'\actual-transfer\kit\f'+$i));bytes=$bytes;sha256=('A'*64);content_verified_this_review=$true;decision='CANDIDATE_EXACT_TEST_EXTRACTION_PENDING_DELETE_REVIEW';retained_copy=[pscustomobject]@{path=(Join-Path $repo ('artifacts\v1026-server-stage-20260911-r'+($n-3)+'\transfer-files\kit\f'+$i));bytes=$bytes;sha256=('A'*64)}}
    }})
    return [pscustomobject]@{id='dde4f1ce-375f-4be5-84a8-18b47bcf2745';kind='ARTIFACTS_TMP_READONLY_CLASSIFICATION';files=$rows}
}
$review=Review;$records=@(Get-StageCleanupRecords $review $repo);Check ($records.Count-eq64) 'Valid fixed contract'
$r=Review;$r.files=$r.files[1..63];Reject {Get-StageCleanupRecords $r $repo} 'Missing source blocks'
$r=Review;$r.files[0].path=Join-Path $repo '.tmp\other\f';Reject {Get-StageCleanupRecords $r $repo} 'Outside source blocks'
$r=Review;$r.files[0].retained_copy.path=$r.files[32].retained_copy.path;Reject {Get-StageCleanupRecords $r $repo} 'Cross revision keeper blocks'
$r=Review;$r.files[0].sha256='B'*64;Reject {Get-StageCleanupRecords $r $repo} 'Keeper hash mismatch blocks'
$r=Review;$r.files[0].path=$r.files[1].path;Reject {Get-StageCleanupRecords $r $repo} 'Duplicate target blocks'
$r=Review;$r.files[0].content_verified_this_review=$false;Reject {Get-StageCleanupRecords $r $repo} 'Unverified file blocks'
$r=Review;$r.files[0].path=$r.files[0].path+'\..\outside';Reject {Get-StageCleanupRecords $r $repo} 'Traversal blocks'
$r=Review;$r.files[0].bytes++;$r.files[0].retained_copy.bytes++;Reject {Get-StageCleanupRecords $r $repo} 'Byte total changes block'
$before=@{files=@('a','b','test-result.json');directories=@('root','empty')}
Assert-StageMembership $before @{files=@('test-result.json');directories=@('root','empty')} @('a','b');Check $true 'Exact files retired; directories remain'
Reject {Assert-StageMembership $before @{files=@('test-result.json');directories=@('root')} @('a','b')} 'Empty directory removal blocks'
Reject {Assert-StageMembership $before @{files=@('b');directories=@('root','empty')} @('a')} 'Test receipt disappearance blocks'
$fixture=Join-Path $repo ('artifacts\stage-cleanup-test-'+[Guid]::NewGuid().ToString('N'))
if(-not$fixture.StartsWith((Join-Path $repo 'artifacts')+'\',[StringComparison]::Ordinal)){throw 'Fixture boundary'}
[void][IO.Directory]::CreateDirectory($fixture)
$p=Join-Path $fixture 'index.json'
$rows=@($records|ForEach-Object {@{path=$_.path;bytes=$_.bytes}})+@($records|ForEach-Object {@{path=$_.keeper;bytes=$_.bytes;state='KEEP'}})+@(@{path='outside';bytes=12})
$sample=@{host='fixture';updated_at='before';audits=@(@{id='unrelated';state='PRESERVE'});history=@();files=$rows;roots=@(@{path=(Join-Path $repo '.tmp');file_count=100;bytes=500000000});summary=@{files=129;bytes=662587744;deleted_files=7;deleted_bytes=123};validation=@{state='OLD'};large_number=9223372036854775806}
$out=[IO.File]::Open($p,'CreateNew','Write','None');try{$out.Write([Text.Encoding]::UTF8.GetBytes(($sample|ConvertTo-Json -Depth 20 -Compress)))}finally{$out.Dispose()}
$a=[ordered]@{id='fixture';kind='DESKTOP_STAGE_EXTRACTION_CLEANUP';state='PREPARED';files=$records;inventory_root=(Join-Path $repo '.tmp')}
function WriteFixture {
    $s=[IO.File]::OpenRead($p);try{$h=Get-DistHash $s;$s.Position=0;$d=[System.Text.Json.JsonDocument]::Parse($s)}finally{$s.Dispose()}
    try{Write-StageIndex $d $a $p $h}finally{$d.Dispose()}
    return [IO.File]::ReadAllText($p)|ConvertFrom-Json -Depth 40
}
$v=WriteFixture
Check ($v.files.Count-eq129-and$v.summary.deleted_files-eq7-and$v.audits[-1].state-ceq'PREPARED') 'Pending intent does not claim deletion'
Check ($v.audits[0].state-ceq'PRESERVE'-and$v.history[-1].deleted_files-eq0) 'Unrelated audit retained'
$a.state='COMPLETE';$v=WriteFixture
Check ($v.files.Count-eq65-and$v.summary.files-eq65-and$v.summary.deleted_files-eq71-and$v.summary.deleted_bytes-eq331293989) '64 exact deletions accounted'
Check (@($v.files|Where-Object {$_.PSObject.Properties['state']-and$_.state-ceq'PROTECT_STAGE_EXTRACTION_KEEPER'}).Count-eq64) 'All keepers explicitly protected'
Check ($v.roots[0].file_count-eq36-and$v.roots[0].bytes-eq168706134) 'Only selected inventory root adjusted'
Check ($v.large_number-eq9223372036854775806-and$v.audits.Count-eq2-and$v.history.Count-eq2) 'Integer precision and preparation history retained'
Check ($v.validation.state-ceq'STAGE_EXTRACTION_VERIFIED_GLOBAL_RECHECK_PENDING') 'No false global verification claim'
$s=[IO.File]::OpenRead($p);try{$d=[System.Text.Json.JsonDocument]::Parse($s)}finally{$s.Dispose()}
try{Reject {Write-StageIndex $d $a $p ('0'*64)} 'Concurrent index hash blocks replacement'}finally{$d.Dispose()}
Check (([IO.File]::ReadAllText($p)|ConvertFrom-Json).history.Count-eq2) 'Failed CAS preserves index'
Write-Host ('[PASS] '+$count+' stage cleanup checks; fixture='+$fixture+'; managed_candidates_changed=0')
