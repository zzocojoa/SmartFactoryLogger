Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSVersion.Major-lt7){throw 'PowerShell 7 required'}
$count=0
function Check([bool]$Value,[string]$Name){if(-not$Value){throw $Name};$script:count++}
function Reject([scriptblock]$Action,[string]$Name){$caught=$false;try{&$Action}catch{$caught=$true};Check $caught $Name}
foreach($name in @('attestation-extraction-cleanup-core.ps1','remove-attestation-extraction-duplicates.ps1')){
    $errors=$null;[void][Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$null,[ref]$errors)
    Check ($errors.Count-eq0) ($name+' syntax: '+(@($errors|ForEach-Object {$_.Message})-join'; '))
}
. (Join-Path $PSScriptRoot 'dist-migration-core.ps1')
. (Join-Path $PSScriptRoot 'stage-extraction-cleanup-core.ps1')
. (Join-Path $PSScriptRoot 'attestation-extraction-cleanup-core.ps1')
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
function Review {
    $rows=@(foreach($s in Get-AttestationSpecs $repo){foreach($i in 0..($s.count-1)){
        $bytes=if($i-eq0){$s.bytes-$s.count+1}else{1}
        [pscustomobject]@{path=(Join-Path $s.source ('f'+$i));bytes=$bytes;sha256=('A'*64);content_verified_this_review=$true;decision='CANDIDATE_EXACT_VERIFICATION_EXTRACTION';retained_copy=[pscustomobject]@{path=(Join-Path $s.keeper ('f'+$i));bytes=$bytes;sha256=('A'*64)}}
    }})
    return [pscustomobject]@{id='cd1e6296-a5bd-46fa-9f61-94ff47cff16f';kind='LARGE_ARTIFACTS_READONLY_REVIEW_V1';files=$rows}
}
$r=Review;$records=@(Get-AttestationCleanupRecords $r $repo);Check ($records.Count-eq156) 'Fixed 156-file contract'
Check (@($records.keeper|Select-Object -Unique).Count-eq120) 'R5 shares 36 keepers without dropping sources'
$r=Review;$r.files=$r.files[1..155];Reject {Get-AttestationCleanupRecords $r $repo} 'Missing source blocks'
$r=Review;$r.files[0].path=Join-Path $repo '.tmp\other\f';Reject {Get-AttestationCleanupRecords $r $repo} 'Outside source blocks'
$r=Review;$r.files[0].path=$r.files[1].path;Reject {Get-AttestationCleanupRecords $r $repo} 'Duplicate blocks'
$r=Review;$r.files[0].retained_copy.path=$r.files[12].retained_copy.path;Reject {Get-AttestationCleanupRecords $r $repo} 'Wrong revision keeper blocks'
$r=Review;$r.files[0].path=$r.files[0].path.Replace('verify_extract_attempt2','verify_extract');Reject {Get-AttestationCleanupRecords $r $repo} 'Unapproved earlier attempt blocks'
$r=Review;$r.files[0].sha256='B'*64;Reject {Get-AttestationCleanupRecords $r $repo} 'Source/keeper hash mismatch blocks'
$r=Review;$r.files[120].sha256='B'*64;$r.files[120].retained_copy.sha256='B'*64;Reject {Get-AttestationCleanupRecords $r $repo} 'Shared keeper conflicting content blocks'
$r=Review;$r.files[0].content_verified_this_review=$false;Reject {Get-AttestationCleanupRecords $r $repo} 'Unverified content blocks'
foreach($suffix in @('\..\outside',':ads','.',' ')){
    $r=Review;$r.files[0].path+=$suffix;Reject {Get-AttestationCleanupRecords $r $repo} ('Unsafe suffix blocks: '+$suffix)
}
$r=Review;$r.files[0].bytes++;$r.files[0].retained_copy.bytes++;Reject {Get-AttestationCleanupRecords $r $repo} 'Changed totals block'
$before=@{files=@('source','keeper','output.zip');directories=@('root','empty')}
Assert-StageMembership $before @{files=@('keeper','output.zip');directories=@('root','empty')} @('source');Check $true 'Exact removal preserves all directories'
Reject {Assert-StageMembership $before @{files=@('keeper');directories=@('root','empty')} @('source')} 'ZIP loss blocks'
Reject {Assert-StageMembership $before @{files=@('keeper','output.zip');directories=@('root')} @('source')} 'Directory loss blocks'
$fixture=Join-Path $repo ('artifacts\attestation-cleanup-test-'+[Guid]::NewGuid().ToString('N'))
if(-not$fixture.StartsWith((Join-Path $repo 'artifacts')+'\',[StringComparison]::Ordinal)){throw 'Fixture boundary'}
[void][IO.Directory]::CreateDirectory($fixture)
$p=Join-Path $fixture 'index.json'
$keepers=@{};foreach($f in $records){$keepers[$f.keeper]=@{path=$f.keeper;bytes=$f.bytes;state='KEEP'}}
$rows=@($records|ForEach-Object {@{path=$_.path;bytes=$_.bytes}})+@($keepers.Values)+@(@{path='outside';bytes=12})
$sample=@{host='fixture';updated_at='before';audits=@(@{id='unrelated';state='PRESERVE'});history=@();files=$rows;roots=@(@{path=(Join-Path $repo '.tmp');file_count=277;bytes=500000000});summary=@{files=277;bytes=500000000;deleted_files=7;deleted_bytes=123};validation=@{state='OLD'};large_number=9223372036854775806}
$out=[IO.File]::Open($p,'CreateNew','Write','None');try{$out.Write([Text.Encoding]::UTF8.GetBytes(($sample|ConvertTo-Json -Depth 20 -Compress)))}finally{$out.Dispose()}
$a=[ordered]@{id='fixture';kind='DESKTOP_ATTESTATION_EXTRACTION_CLEANUP';state='PREPARED';files=$records;inventory_root=(Join-Path $repo '.tmp')}
function WriteFixture {
    $s=[IO.File]::OpenRead($p);try{$h=Get-DistHash $s;$s.Position=0;$d=[System.Text.Json.JsonDocument]::Parse($s)}finally{$s.Dispose()}
    try{Write-AttestationIndex $d $a $p $h}finally{$d.Dispose()}
    return [IO.File]::ReadAllText($p)|ConvertFrom-Json -Depth 40
}
$v=WriteFixture
Check ($v.files.Count-eq277-and$v.summary.deleted_files-eq7-and$v.audits[-1].state-ceq'PREPARED') 'Pending intent makes no deletion claim'
Check ($v.audits[0].state-ceq'PRESERVE'-and$v.history[-1].deleted_files-eq0) 'Unrelated history preserved'
Reject {WriteFixture} 'Cannot publish PREPARED twice'
$a.state='COMPLETE';$v=WriteFixture
Check ($v.files.Count-eq121-and$v.summary.files-eq121-and$v.summary.deleted_files-eq163-and$v.summary.deleted_bytes-eq229591995) '156 deletions accounted'
Check (@($v.files|Where-Object {$_.PSObject.Properties['state']-and$_.state-ceq'PROTECT_ATTESTATION_EXTRACTION_KEEPER'}).Count-eq120) 'All 120 distinct keepers protected'
Check ($v.roots[0].file_count-eq121-and$v.roots[0].bytes-eq270408128) 'Selected inventory root adjusted'
Check ($v.large_number-eq9223372036854775806-and$v.audits.Count-eq2-and$v.history.Count-eq2) 'Large integer and other records preserved'
Check ($v.validation.state-ceq'ATTESTATION_EXTRACTION_VERIFIED_GLOBAL_RECHECK_PENDING') 'No global PASS claim'
Reject {WriteFixture} 'Cannot subtract completed transaction again'
$a.id='second-fixture';$a.state='PREPARED'
$s=[IO.File]::OpenRead($p);try{$d=[System.Text.Json.JsonDocument]::Parse($s)}finally{$s.Dispose()}
try{Reject {Write-AttestationIndex $d $a $p ('0'*64)} 'Concurrent index hash blocks replacement'}finally{$d.Dispose()}
Check (([IO.File]::ReadAllText($p)|ConvertFrom-Json).history.Count-eq2) 'Failed CAS keeps original management file'
Write-Host ('[PASS] '+$count+' attestation cleanup checks; fixture='+$fixture+'; managed_candidates_changed=0')
