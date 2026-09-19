Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not$IsWindows-or$PSVersionTable.PSVersion.Major-lt7){throw 'Windows PowerShell 7 required'}
. (Join-Path $PSScriptRoot 'dist-migration-core.ps1')
. (Join-Path $PSScriptRoot 'build-intermediate-cleanup-core.ps1')
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'));$count=0
function Check([bool]$Ok,[string]$Name){if(-not$Ok){throw ('FAIL: '+$Name)};$script:count++}
function Reject([scriptblock]$Action,[string]$Name){$failed=$false;try{& $Action|Out-Null}catch{$failed=$true};Check $failed $Name}
function Clone($Value){return $Value|ConvertTo-Json -Depth 30|ConvertFrom-Json -Depth 30}
function New-FixtureFile([string]$Path,[string]$Text){$s=[IO.File]::Open($Path,'CreateNew','Write','None');try{$b=[Text.Encoding]::UTF8.GetBytes($Text);$s.Write($b,0,$b.Length);$s.Flush($true)}finally{$s.Dispose()}}
$paths=@(Get-BuildIntermediatePaths $repo)
Check ($paths.Count-eq17-and@($paths|Select-Object -Unique).Count-eq17) 'fixed allowlist'
$records=@();for($i=0;$i-lt17;$i++){$records+=@{path=$paths[$i];bytes=$(if($i-eq0){36648161}else{1});sha256=('A'*64);decision='DELETE_CANDIDATE_NOT_AUTHORIZED'}}
$review=@{id='5db89818-a464-4c8b-a534-0b5ada299072';state='REVIEW_COMPLETE_AWAITING_EXACT_DELETE_APPROVAL';records=$records}
Check (@(Get-BuildIntermediateRecords $review $repo).Count-eq17) 'approved records'
foreach($case in @('duplicate','outside','toc','traversal','hash','negative','total','state','id','missing')){
    $r=Clone $review
    switch($case){
        'duplicate'{$r.records[1].path=$r.records[0].path}
        'outside'{$r.records[0].path=Join-Path $repo 'backend\dist\SmartFactoryBackend\SmartFactoryBackend.exe'}
        'toc'{$r.records[0].path=Join-Path $repo 'backend\build\SmartFactoryBackend\Analysis-00.toc'}
        'traversal'{$r.records[0].path=Join-Path $repo 'backend\build\SmartFactoryBackend\..\SmartFactoryBackend\PYZ-00.pyz'}
        'hash'{$r.records[0].sha256='wrong'}
        'negative'{$r.records[0].bytes=-1}
        'total'{$r.records[0].bytes++}
        'state'{$r.state='HOLD'}
        'id'{$r.id='other'}
        'missing'{$r.records=@($r.records|Select-Object -Skip 1)}
    }
    Reject {Get-BuildIntermediateRecords $r $repo} $case
}
$fixture=Join-Path $repo ('.tmp\build-intermediate-cleanup-test-'+[Guid]::NewGuid().ToString('N'))
if(-not$fixture.StartsWith((Join-Path $repo '.tmp')+'\',[StringComparison]::Ordinal)){throw 'Fixture boundary'}
[void](New-Item -ItemType Directory -Path $fixture)
$keep=@();for($i=0;$i-lt14;$i++){$keep+=@{path=(Join-Path $repo ('backend\build\history-'+$i+'.toc'));bytes=$(if($i-eq0){3113956}else{1});sha256=('B'*64);state='OLD'}}
$fixtureIndex=Join-Path $fixture 'index.json'
$before=@{updated_at='old';audits=@(@{id='old';kind='OLD';huge=[long]9223372036854775806});history=@();files=@($records)+@($keep);roots=@(@{path=(Join-Path $repo 'backend\build');file_count=31;bytes=39762146});summary=@{files=31;bytes=39762146;deleted_files=5;deleted_bytes=10};validation=@{state='PRIOR'}}
New-FixtureFile $fixtureIndex ($before|ConvertTo-Json -Depth 30 -Compress)
$a=@{id='fixture';kind='DESKTOP_BUILD_INTERMEDIATE_CLEANUP';state='PREPARED';files=$records;preserved_files=$keep;inventory_root=(Join-Path $repo 'backend\build')}
$s=[IO.File]::OpenRead($fixtureIndex);$pin=Get-DistHash $s;$s.Position=0;$d=[System.Text.Json.JsonDocument]::Parse($s);$s.Dispose()
try{Write-BuildCleanupIndex $d $a $fixtureIndex $pin}finally{$d.Dispose()}
$s=[IO.File]::OpenRead($fixtureIndex);$pin=Get-DistHash $s;$s.Position=0;$d=[System.Text.Json.JsonDocument]::Parse($s);$s.Dispose()
try{
    Check ($d.RootElement.GetProperty('files').GetArrayLength()-eq31) 'PREPARED retains all files'
    Reject {Write-BuildCleanupIndex $d $a $fixtureIndex $pin} 'duplicate preparation'
    $a.state='COMPLETE';Write-BuildCleanupIndex $d $a $fixtureIndex $pin
}finally{$d.Dispose()}
$s=[IO.File]::OpenRead($fixtureIndex);$pin=Get-DistHash $s;$s.Position=0;$d=[System.Text.Json.JsonDocument]::Parse($s);$s.Dispose()
try{
    Check ($d.RootElement.GetProperty('files').GetArrayLength()-eq14) 'only 17 removed'
    Check ($d.RootElement.GetProperty('summary').GetProperty('bytes').GetInt64()-eq3113969) 'byte delta'
    Check ($d.RootElement.GetProperty('summary').GetProperty('deleted_files').GetInt64()-eq22) 'historical deletion total'
    Check ($d.RootElement.GetProperty('audits')[0].GetProperty('huge').GetInt64()-eq9223372036854775806) '64-bit historical token preserved'
    Check (@($d.RootElement.GetProperty('files').EnumerateArray()|Where-Object {$_.GetProperty('state').GetString()-ceq'PROTECT_BUILD_DIAGNOSTIC_EVIDENCE'}).Count-eq14) 'all 14 protected'
    Reject {Write-BuildCleanupIndex $d $a $fixtureIndex $pin} 'double completion rejected'
    $a.id='fixture-cas';$a.state='PREPARED'
    Reject {Write-BuildCleanupIndex $d $a $fixtureIndex ('F'*64)} 'concurrent index mismatch'
    $read=[IO.File]::OpenRead($fixtureIndex);try{Check ((Get-DistHash $read)-ceq$pin) 'CAS leaves current index unchanged'}finally{$read.Dispose()}
}finally{$d.Dispose()}
$native=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'server-path-audit\cleanup-archive-core.ps1'))
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseInput($native,[ref]$tokens,[ref]$errors)
$fn=$ast.Find({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-ceq'Initialize-CleanupNative'},$false)
. ([scriptblock]::Create($fn.Extent.Text));Initialize-CleanupNative
$target=Join-Path $fixture 'synthetic-intermediate.bin';New-FixtureFile $target 'Synthetic generated test content only'
$s=[IO.File]::OpenRead($target);try{$sha=Get-DistHash $s}finally{$s.Dispose()}
$record=@{path=$target;bytes=(Get-Item -LiteralPath $target).Length;sha256=$sha;metadata=(Get-DistMetadata $target)}
$guards=@{};$h=Open-DistSource $record $true $guards;$confirmed=[Collections.Generic.List[object]]::new()
$journalPath=Join-Path $fixture 'events.jsonl';$j=[IO.File]::Open($journalPath,'CreateNew','ReadWrite','Read')
try{
    Reject {$w=[IO.File]::Open($target,'Open','Write','ReadWrite');$w.Dispose()} 'pinned file denies writers'
    $wrong=@{stream=$h.stream;identity='wrong';record=$record}
    Reject {Remove-BuildIntermediatePinned $wrong $j $confirmed} 'identity mismatch preserves file'
    Check ([IO.File]::Exists($target)-and$confirmed.Count-eq0) 'no deletion on invalid identity'
    $closed=[IO.MemoryStream]::new();$closed.Dispose()
    Reject {Remove-BuildIntermediatePinned $h $closed $confirmed} 'no deletion without durable intent'
    Check ([IO.File]::Exists($target)-and$confirmed.Count-eq0) 'failed journal preserves file'
    Remove-BuildIntermediatePinned $h $j $confirmed
    Check (-not[IO.File]::Exists($target)-and$confirmed.Count-eq1) 'exact synthetic handle removed'
}finally{$h.stream.Dispose();$j.Dispose();foreach($g in $guards.Values){$g.handle.Dispose()}}
$events=@([IO.File]::ReadAllLines($journalPath)|ForEach-Object {$_|ConvertFrom-Json})
Check ($events.Count-eq2-and$events[0].event-ceq'DELETE_INTENT'-and$events[1].event-ceq'DELETED') 'durable intent then receipt'
foreach($name in @('remove-build-intermediates.ps1','build-intermediate-cleanup-core.ps1')){$tokens=$null;$errors=$null;[void][Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$tokens,[ref]$errors);Check ($errors.Count-eq0) ($name+' syntax')}
$entry=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'remove-build-intermediates.ps1'))
Check ($entry.Contains('journal_path=$journalPath;journal_sha256=$null')) 'manager journal field contract'
Check ($entry.Contains("`$phase='publish-completion'")) 'publication failure phase distinguished'
Write-Host ('[PASS] '+$count+' build cleanup checks. Only one synthetic fixture file deleted; no managed files changed. Fixture: '+$fixture)
