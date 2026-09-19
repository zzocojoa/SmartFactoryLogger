Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSVersion.Major-lt7){throw 'PowerShell 7 required'}
$count=0
function Check([bool]$OK,[string]$Name){if(-not$OK){throw $Name};$script:count++}
function Reject([scriptblock]$Action,[string]$Name){$caught=$false;try{&$Action}catch{$caught=$true};Check $caught $Name}
foreach($name in @('isolated-test-cache-core.ps1','remove-isolated-test-cache.ps1')){
    $errors=$null;[void][Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$null,[ref]$errors)
    Check ($errors.Count-eq0) ($name+' syntax: '+(@($errors|ForEach-Object {$_.Message})-join'; '))
}
. (Join-Path $PSScriptRoot 'dist-migration-core.ps1')
. (Join-Path $PSScriptRoot 'stage-extraction-cleanup-core.ps1')
. (Join-Path $PSScriptRoot 'isolated-test-cache-core.ps1')
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
function Review {
    $rows=@(foreach($s in Get-TestCacheSpecs $repo){$i=0;foreach($n in $s.names){
        [pscustomobject]@{path=(Join-Path $s.unit $n);bytes=$(if($i-eq0){$s.bytes-$s.count+1}else{1});cache_unit=$s.category;decision='HOLD_TEST_CACHE_UNIT_AND_LIVE_USE_REVIEW';sha256=('A'*64);unit=$s.unit;category=$s.category};$i++
    }})
    return [pscustomobject]@{id='cd1e6296-a5bd-46fa-9f61-94ff47cff16f';kind='LARGE_ARTIFACTS_READONLY_REVIEW_V1';files=$rows}
}
$specs=@(Get-TestCacheSpecs $repo);$r=Review;$records=@(Get-TestCacheRecords $r $repo)
Check ($records.Count-eq181-and$specs.Count-eq39) '181 files / 39 whole units'
Check (@($specs.profile|Select-Object -Unique).Count-eq7) 'Seven fixed isolated profiles'
$r=Review;$r.files=$r.files[1..180];Reject {Get-TestCacheRecords $r $repo} 'Partial unit blocks'
$r=Review;$r.files[0].path=$r.files[1].path;Reject {Get-TestCacheRecords $r $repo} 'Duplicate blocks'
foreach($change in @('run-other','..\escape','AppData\Roaming')){
    $r=Review;$r.files[0].path=$r.files[0].path.Replace('run-54JQVf',$change);Reject {Get-TestCacheRecords $r $repo} 'Other profile/traversal blocks'
}
$r=Review;$r.files[0].path+=':ads';Reject {Get-TestCacheRecords $r $repo} 'Named stream blocks'
$r=Review;$r.files[0].cache_unit='Local Storage';Reject {Get-TestCacheRecords $r $repo} 'Persistent data category blocks'
$r=Review;$r.files[0].bytes++;Reject {Get-TestCacheRecords $r $repo} 'Changed cache bytes block'
$r=Review;$r.files[0].path=$r.files[0].path.Replace('Cache_Data\data_0','Custom Dictionary');Reject {Get-TestCacheRecords $r $repo} 'Unknown cache child blocks'
$meta=@{bytes=12;last_write_utc_ticks='638000000000000000';creation_utc_ticks='638000000000000001'}
$snapshot='12|1664403200000000000|0|1664403200000000100|1|2|1'
Assert-TestCacheTimestamp $meta $snapshot;Check $true 'Exact Windows timestamps accepted'
$meta.bytes++;Reject {Assert-TestCacheTimestamp $meta $snapshot} 'Changed classified metadata blocks'
$fixture=Join-Path $repo ('artifacts\isolated-cache-test-'+[Guid]::NewGuid().ToString('N'))
if(-not$fixture.StartsWith((Join-Path $repo 'artifacts')+'\',[StringComparison]::Ordinal)){throw 'Fixture boundary'}
[void][IO.Directory]::CreateDirectory($fixture)
function NewFixture([string]$Name,[string]$Content){$p=Join-Path $fixture $Name;$s=[IO.File]::Open($p,'CreateNew','Write','None');try{$s.Write([Text.Encoding]::UTF8.GetBytes($Content))}finally{$s.Dispose()};return $p}
$preserved=@(@{path='settings-fixture';bytes=10;sha256=('B'*64)})
$rows=@($records|ForEach-Object {@{path=$_.path;bytes=$_.bytes}})+$preserved
$sample=@{updated_at='before';audits=@(@{id='unrelated';state='KEPT'});history=@();files=$rows;roots=@(@{path=(Join-Path $repo 'artifacts');file_count=182;bytes=184040258});summary=@{files=182;bytes=184040258;deleted_files=0;deleted_bytes=0};validation=@{state='OLD'};large_number=9223372036854775806}
$p=NewFixture 'index.json' ($sample|ConvertTo-Json -Depth 20 -Compress)
$a=[ordered]@{id='fixture';kind='DESKTOP_ISOLATED_TEST_CACHE_CLEANUP';state='PREPARED';files=$records;preserved_files=$preserved;inventory_root=(Join-Path $repo 'artifacts')}
function WriteFixture {
    $s=[IO.File]::OpenRead($p);try{$h=Get-DistHash $s;$s.Position=0;$d=[System.Text.Json.JsonDocument]::Parse($s)}finally{$s.Dispose()}
    try{Write-TestCacheIndex $d $a $p $h}finally{$d.Dispose()}
    return [IO.File]::ReadAllText($p)|ConvertFrom-Json -Depth 40
}
$v=WriteFixture;Check ($v.files.Count-eq182-and$v.summary.deleted_files-eq0) 'Pending intent claims no deletion'
Reject {WriteFixture} 'Duplicate PREPARED blocks'
$a.state='COMPLETE';$v=WriteFixture
Check ($v.files.Count-eq1-and$v.summary.files-eq1-and$v.summary.bytes-eq10-and$v.summary.deleted_files-eq181-and$v.summary.deleted_bytes-eq184040248) 'Exact cache subtraction'
Check ($v.files[0].state-ceq'PROTECT_ISOLATED_TEST_EVIDENCE'-and$v.roots[0].file_count-eq1) 'Noncache evidence remains protected'
Check ($v.large_number-eq9223372036854775806-and$v.audits[0].state-ceq'KEPT'-and$v.history.Count-eq2) 'Precision and unrelated history preserved'
Reject {WriteFixture} 'Repeated completion cannot subtract twice'
$a.id='second';$a.state='PREPARED';$s=[IO.File]::OpenRead($p);try{$d=[System.Text.Json.JsonDocument]::Parse($s)}finally{$s.Dispose()}
try{Reject {Write-TestCacheIndex $d $a $p ('0'*64)} 'Concurrent index hash blocks replacement'}finally{$d.Dispose()}
Check (([IO.File]::ReadAllText($p)|ConvertFrom-Json).history.Count-eq2) 'CAS failure preserves original'
$native=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'server-path-audit\cleanup-archive-core.ps1') -Raw
$ast=[Management.Automation.Language.Parser]::ParseInput($native,[ref]$null,[ref]$null)
$fn=$ast.Find({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-ceq'Initialize-CleanupNative'},$false)
. ([scriptblock]::Create($fn.Extent.Text));Initialize-CleanupNative
$guards=@{};$pins=[Collections.Generic.List[IDisposable]]::new()
try {
    $source=NewFixture 'synthetic-cache.bin' 'fixture-only'
    $s=[IO.File]::OpenRead($source);try{$hash=Get-DistHash $s}finally{$s.Dispose()}
    $r=[pscustomobject]@{path=$source;bytes=12;sha256=$hash;metadata=[pscustomobject](Get-DistMetadata $source);unit=$fixture}
    $held=Open-DistSource $r $true $guards;$pins.Add($held.stream)
    $j=[IO.File]::Open((Join-Path $fixture 'journal.jsonl'),'CreateNew','Write','Read');$pins.Add($j)
    $done=[Collections.Generic.List[object]]::new()
    Reject {[IO.File]::WriteAllText($source,'bad')} 'Held cache rejects writes'
    Reject {[IO.Directory]::Move($fixture,$fixture+'-moved')} 'Ancestor cannot be renamed'
    $identity=$held.identity;$held.identity='wrong';Reject {Remove-TestCachePinned $held $j $done} 'Identity mismatch blocks deletion';$held.identity=$identity
    $closed=[IO.MemoryStream]::new();$closed.Dispose();Reject {Remove-TestCachePinned $held $closed $done} 'Intent write failure preserves source'
    Check ([IO.File]::Exists($source)-and$done.Count-eq0) 'Precommit errors do not delete'
    Remove-TestCachePinned $held $j $done
    Check (-not[IO.File]::Exists($source)-and$done.Count-eq1) 'Only fixture cache deleted'
    $j.Dispose();$events=@(Get-Content -LiteralPath (Join-Path $fixture 'journal.jsonl')|ForEach-Object {$_|ConvertFrom-Json})
    Check ($events.Count-eq2-and$events[0].event-ceq'DELETE_INTENT'-and$events[1].event-ceq'DELETED') 'Durable intent precedes delete receipt'
    $late=NewFixture 'synthetic-late-failure.bin' 'fixture-only'
    $lr=[pscustomobject]@{path=$late;bytes=12;sha256=$hash;metadata=[pscustomobject](Get-DistMetadata $late);unit=$fixture}
    $ls=Open-DistSource $lr $true $guards;$pins.Add($ls.stream)
    $j2=[IO.File]::Open((Join-Path $fixture 'late-journal.jsonl'),'CreateNew','Write','Read');$pins.Add($j2)
    $saved=(Get-Command Write-DistEvent).ScriptBlock
    function Write-DistEvent($Journal,$Record){if($Record.event-ceq'DELETED'){throw 'Synthetic late receipt failure'};&$saved $Journal $Record}
    try {
        Reject {Remove-TestCachePinned $ls $j2 $done} 'Late receipt error propagates'
        Check ($done.Count-eq2-and-not[IO.File]::Exists($late)) 'Irreversible action counted even if post-receipt fails'
    }finally{Set-Item -LiteralPath Function:Write-DistEvent -Value $saved}
}finally{foreach($s in $pins){$s.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}}
Write-Host ('[PASS] '+$count+' isolated cache checks; managed_files_changed=0; fixture='+$fixture)
