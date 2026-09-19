Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSVersion.Major-lt7){throw 'PowerShell 7 required'}
$count=0
function Check([bool]$OK,[string]$Name){if(-not$OK){throw $Name};$script:count++}
function Reject([scriptblock]$Action,[string]$Name){$caught=$false;try{&$Action}catch{$caught=$true};Check $caught $Name}
foreach($name in @('chrome-test-cache-core.ps1','remove-chrome-test-caches.ps1')){
    $errors=$null;[void][Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$null,[ref]$errors)
    Check ($errors.Count-eq0) ($name+' syntax: '+(@($errors|ForEach-Object {$_.Message})-join'; '))
}
. (Join-Path $PSScriptRoot 'dist-migration-core.ps1')
. (Join-Path $PSScriptRoot 'chrome-test-cache-core.ps1')
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
foreach($p in @('Default\Cache\Cache_Data\index','Default\Cache\Cache_Data\f_0000ab','Default\Cache\No_Vary_Search\journal.baj','Default\Code Cache\js\abcd1234abcd1234_0','Default\Code Cache\wasm\index-dir\the-real-index','Default\GPUCache\data_0','ShaderCache\index','GrShaderCache\data_3','GraphiteDawnCache\index')){Check ([bool](Get-ChromeCacheUnit $p)) 'Known cache member'}
foreach($p in @('Default\Cookies','Default\History','Default\Local Storage\data','Default\Service Worker\CacheStorage\file','Dictionaries\dictionary','Default\Cache-copy\Cache_Data\index')){Check ($null-eq(Get-ChromeCacheUnit $p)) 'User state and lookalikes retained'}
foreach($p in @('Default\Cache\secret','Default\GPUCache\data_4','Default\Cache\..\Cookies','..\Default\Cache\Cache_Data\index','Default\Cache\Cache_Data\index:stream','Default/Cache/Cache_Data/index','Default\Cache\Cache_Data\index.')){Reject {Get-ChromeCacheUnit $p} 'Unknown/traversal/stream member blocks'}
foreach($pair in @(@('C3CA03C100000300','ShaderCache\index'),@('305C72A71B6DFBFC','Default\Code Cache\js\index'))){$s=[IO.MemoryStream]::new([Convert]::FromHexString($pair[0]));try{Assert-ChromeIndexHeader $s $pair[1];Check $true 'Known index magic'}finally{$s.Dispose()}}
$s=[IO.MemoryStream]::new([byte[]](0,1,2));try{Reject {Assert-ChromeIndexHeader $s 'ShaderCache\index'} 'Short/wrong magic blocks'}finally{$s.Dispose()}
function AuditFixture {
    $gone=[Collections.Generic.List[object]]::new();$kept=[Collections.Generic.List[object]]::new()
    foreach($spec in Get-ChromeTestProfileSpecs $repo){
        for($i=0;$i-lt$spec.delete_files;$i++){$gone.Add([pscustomobject]@{path=(Join-Path $spec.root ('Default\Cache\Cache_Data\f_'+$i.ToString('x6')));bytes=$(if($i-eq0){$spec.delete_bytes-$spec.delete_files+1}else{1});sha256=('A'*64);unit=(Join-Path $spec.root 'Default\Cache');disposition='DELETE_CACHE'})}
        $n=$spec.files-$spec.delete_files;$bytes=$spec.bytes-$spec.delete_bytes
        for($i=0;$i-lt$n;$i++){$kept.Add([pscustomobject]@{path=(Join-Path $spec.root ('RetainedFixture\'+$i));bytes=$(if($i-eq0){$bytes-$n+1}else{1});sha256=('B'*64);disposition='KEEP_PROFILE_STATE'})}
    }
    return [ordered]@{id='fixture';kind='DESKTOP_CHROME_TEST_CACHE_CLEANUP';state='PREPARED';files=$gone.ToArray();preserved_files=$kept.ToArray()}
}
$a=AuditFixture;Assert-ChromeCacheRecords $a $repo;Check $true 'Exact nine profile counts and bytes'
$a.files[0].path=$a.files[1].path;Reject {Assert-ChromeCacheRecords $a $repo} 'Duplicate rejected'
$a=AuditFixture;$a.files[0].path=Join-Path $repo 'Default\Cache\Cache_Data\index';Reject {Assert-ChromeCacheRecords $a $repo} 'Outside profile rejected'
$a=AuditFixture;$a.files[0].bytes++;Reject {Assert-ChromeCacheRecords $a $repo} 'Per-root byte drift rejected'
$a=AuditFixture;$t=$a.files[0];$a.files[0]=$a.preserved_files[0];$a.preserved_files[0]=$t;Reject {Assert-ChromeCacheRecords $a $repo} 'Swapped deletion and preservation arrays rejected'
$a=AuditFixture
$fixture=Join-Path $repo ('artifacts\chrome-cache-test-'+[Guid]::NewGuid().ToString('N'))
if(-not$fixture.StartsWith((Join-Path $repo 'artifacts')+'\',[StringComparison]::Ordinal)){throw 'Fixture boundary'}
[void][IO.Directory]::CreateDirectory($fixture)
$p=Join-Path $fixture 'index.json'
$sample=@{updated_at='before';audits=@(@{id='unrelated';state='KEPT'});history=@();files=@($a.files)+@($a.preserved_files);roots=@(Get-ChromeTestProfileSpecs $repo|ForEach-Object {@{path=$_.root;file_count=$_.files;bytes=$_.bytes}});summary=@{files=10127;bytes=892914034;deleted_files=0;deleted_bytes=0};validation=@{state='OLD';large_number=9223372036854775806};large_number=9223372036854775806}
$out=[IO.File]::Open($p,'CreateNew','Write','None');try{$out.Write([Text.Encoding]::UTF8.GetBytes(($sample|ConvertTo-Json -Depth 15 -Compress)))}finally{$out.Dispose()}
function WriteFixture {
    $s=[IO.File]::OpenRead($p);try{$h=Get-DistHash $s;$s.Position=0;$d=[System.Text.Json.JsonDocument]::Parse($s)}finally{$s.Dispose()}
    try{Write-ChromeCacheIndex $d $a $p $h $repo}finally{$d.Dispose()}
    return [IO.File]::ReadAllText($p)|ConvertFrom-Json -Depth 40
}
$v=WriteFixture;Check ($v.files.Count-eq10127-and$v.summary.deleted_files-eq0) 'Prepared does not claim deletion'
Reject {WriteFixture} 'Duplicate prepare rejected'
$a.state='COMPLETE';$v=WriteFixture
Check ($v.files.Count-eq9485-and$v.summary.files-eq9485-and$v.summary.bytes-eq681852407-and$v.summary.deleted_files-eq642-and$v.summary.deleted_bytes-eq211061627) 'Exact complete summary delta'
Check (@($v.files|Where-Object {$_.state-cne'PROTECT_RETAINED_BROWSER_PROFILE'}).Count-eq0) 'Preserved profile rows protected'
Check ($v.large_number-eq9223372036854775806-and$v.audits[0].state-ceq'KEPT'-and$v.history.Count-eq2-and$v.validation.prior_global_validation.prior_global_validation.large_number-eq9223372036854775806) 'Raw integer precision and history preserved'
Reject {WriteFixture} 'No repeat subtraction'
$a.id='second';$a.state='PREPARED';$s=[IO.File]::OpenRead($p);try{$d=[System.Text.Json.JsonDocument]::Parse($s)}finally{$s.Dispose()}
try{Reject {Write-ChromeCacheIndex $d $a $p ('0'*64) $repo} 'Concurrent hash rejects publish'}finally{$d.Dispose()}
Check (([IO.File]::ReadAllText($p)|ConvertFrom-Json).history.Count-eq2) 'CAS failure leaves original intact'
Write-Host ('[PASS] '+$count+' Chrome cache checks; managed_files_changed=0; fixture='+$fixture)
